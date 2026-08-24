"""DevStat auth router — Firebase-backed, DevStat's OWN project.

Exchanges a Firebase ID token for a DevStat session (profile + licence from
DevStat Firestore). Separate from pubmed's auth.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.services import session_guard
from app.config import ADMIN_EMAILS
from app.services.firebase_store import (  # noqa: F401
    get_user, is_configured, licence_live, update_user, verify_id_token,
)

router = APIRouter()


class TokenBody(BaseModel):
    id_token: str
    device_id: str = ""


def _bearer(authorization: str) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def _session_uid(authorization: str) -> str:
    """Resolve the session token -> uid, enforcing the device/session guard."""
    token = _bearer(authorization)
    parts = token.split(".") if token else []
    if len(parts) != 4:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    uid = parts[0]
    if not session_guard.validate_token(uid, token):
        raise HTTPException(
            status_code=401,
            detail="This session was signed out or signed in on too many devices. Please sign in again.",
        )
    return uid


def _public_user(uid: str) -> Dict[str, Any]:
    u = get_user(uid)
    import time
    until = (u.get("licensed_until") or 0)
    try:
        live = bool(u.get("licensed")) and float(until) > time.time()
    except Exception:
        live = bool(u.get("licensed"))
    return {
        "uid": uid,
        "email": u.get("email"),
        "name": u.get("name"),
        "provider": u.get("provider", "email"),
        "verified": bool(u.get("verified")),
        "plan": u.get("plan", "free"),
        "licensed": live,
        "licensed_until": float(until) if until else None,
        "usage_count": int(u.get("usage_count") or 0),
    }


@router.post("/session")
async def create_session(body: TokenBody) -> Dict[str, Any]:
    if not is_configured():
        raise HTTPException(status_code=503, detail="DevStat Firebase is not configured yet.")
    claims = verify_id_token(body.id_token)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    uid = claims.get("uid")
    if not uid:
        raise HTTPException(status_code=400, detail="Token has no uid.")
    existing = get_user(uid)
    if not existing:
        update_user(uid, {
            "email": claims.get("email") or "",
            "name": claims.get("name") or "",
            "provider": "google" if claims.get("firebase", {}).get("sign_in_provider") == "google.com"
                        else ("phone" if str(claims.get("firebase", {}).get("sign_in_provider", "")).startswith("phone") else "email"),
            "verified": bool(claims.get("email_verified")),
            "plan": "free",
            "licensed": False,
            "usage_count": 0,
            "devices": {},
        })

    # Owner/admin bypass: accounts on the allowlist get a free, permanent
    # licence so you can test the online app without paying.
    email = (claims.get("email") or "").lower()
    if email in ADMIN_EMAILS:
        import time
        update_user(uid, {
            "email": claims.get("email") or "",
            "role": "admin",
            "plan": "admin",
            "licensed": True,
            "licensed_until": int(time.time()) + 10 * 365 * 86400,
        })

    # Enforce the device/concurrent-session guard and mint a signed session token.
    ok, session_token = session_guard.register_device(uid, getattr(body, "device_id", ""))
    if not ok:
        raise HTTPException(status_code=400, detail="A device id is required.")
    result = _public_user(uid)
    result["session_token"] = session_token
    result["max_devices"] = session_guard.max_devices()
    return result


@router.get("/me")
async def me(authorization: str = Header(default="")) -> Dict[str, Any]:
    uid = _session_uid(authorization)
    return _public_user(uid)


@router.post("/logout")
async def logout() -> Dict[str, Any]:
    return {"status": "ok"}
