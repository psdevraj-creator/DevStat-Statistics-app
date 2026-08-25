"""DevStat Desktop Edition — local licence sync for offline analysis.

The Desktop Edition keeps accounts/subscription online (the SPA routes /api/auth
and /api/license to the live Cloud Run app). These endpoints are the LOCAL half:
the SPA pushes the online licence status into a small local store so analysis can
keep working fully offline (and re-lock when the subscription lapses).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app import state as _state
from app.services import desktop_licence

router = APIRouter(prefix="", tags=["Desktop Edition"])


class SyncLicenceBody(BaseModel):
    licensed: bool = False
    licensed_until: Optional[str] = None


@router.get("/licence-status")
async def licence_status() -> Dict[str, Any]:
    uid = _state.get_uid()
    if not uid:
        return {"ok": False, "reason": "Not signed in."}
    return {"ok": True, **desktop_licence.status(uid)}


@router.post("/sync-licence")
async def sync_licence(body: SyncLicenceBody) -> Dict[str, Any]:
    uid = _state.get_uid()
    if not uid:
        return {"ok": False, "reason": "Not signed in."}
    return {"ok": True, **desktop_licence.sync_licence(uid, body.licensed, body.licensed_until)}


@router.post("/shutdown")
async def shutdown() -> Dict[str, Any]:
    """Desktop Edition: the user closed the app window. Exit the engine so no
    stale process holds the port. Reached via `navigator.sendBeacon` on window
    close (reliable even without a normal response)."""
    import threading
    threading.Thread(target=lambda: __import__("os")._exit(0), daemon=True).start()
    return {"ok": True, "shutting_down": True}
