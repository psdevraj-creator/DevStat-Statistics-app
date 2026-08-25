"""DevStat Teaching mode router.

Endpoints:
  GET  /api/teaching/scenarios            -> list scenario metadata
  GET  /api/teaching/scenarios/{sid}      -> full scenario (steps) if accessible,
                                             otherwise a locked teaser
  POST /api/teaching/scenarios/{sid}/load -> load the dataset into the current
                                             session (free case: guests OK;
                                             paid case: must own it)
  GET  /api/teaching/owned                -> ids the signed-in user owns
  POST /api/teaching/checkout/{sid}       -> one-off £1 Stripe checkout (only if
                                             the user already has a subscription)

Gating rules:
  - The FREE scenario is open to guests and to free accounts.
  - PAID (£1) scenarios are usable only once owned. Buying one requires an
    active £25/yr subscription (licence_live) — you subscribe first, then buy
    individual cases for £1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

import app.state as _state
from app.services import billing
from app.services.firebase_store import get_user, licence_live, is_admin
from app.teaching import scenarios

router = APIRouter(prefix="/teaching", tags=["Teaching"])

_DATASET_DIR = Path(__file__).resolve().parent.parent / "teaching" / "datasets"

_LOCK_REASON = ("This teaching case costs £1 to unlock, for Patrons who already have "
                "a DevStat subscription. Subscribe (£25/yr), then buy this case for £1.")


def _owned_set(uid: str) -> dict:
    u = get_user(uid) or {}
    return u.get("teaching_owned") or {}


def _owns(uid: str, sid: str) -> bool:
    if uid and is_admin(uid):
        return True
    return bool((_owned_set(uid) or {}).get(sid))


@router.get("/scenarios")
async def list_scenarios() -> Dict[str, Any]:
    uid = _state.get_uid()
    admin = bool(uid and is_admin(uid))
    owned = _owned_set(uid) if uid else {}
    out = []
    for s in scenarios.list_scenarios():
        out.append({
            **s,
            "owned": bool(admin or owned.get(s["id"])),
            "licensed": bool(uid and (admin or licence_live(uid))),
        })
    return {"scenarios": out}


@router.get("/scenarios/{sid}")
async def get_scenario(sid: str) -> Dict[str, Any]:
    s = scenarios.get_scenario(sid)
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    uid = _state.get_uid()
    accessible = s["free"] or (uid and _owns(uid, sid))
    if not accessible:
        return {"id": s["id"], "title": s["title"], "blurb": s["blurb"], "emoji": s["emoji"],
                "price_cents": s["price_cents"], "free": False, "locked": True,
                "locked_reason": _LOCK_REASON, "steps": []}
    return s


@router.post("/scenarios/{sid}/load")
async def load_scenario(sid: str) -> Dict[str, Any]:
    s = scenarios.get_scenario(sid)
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    uid = _state.get_uid()
    # Guests may do the FREE case. Paid cases require an account that has
    # actually bought the case (subscription is a prerequisite, not auto-unlock).
    if not s["free"]:
        if not uid:
            raise HTTPException(status_code=401, detail="Please sign in to start this lesson.")
        if not _owns(uid, sid):
            raise HTTPException(status_code=402, detail={
                "blocked": True, "action_type": "subscription",
                "reason": _LOCK_REASON,
                "details": "Subscribe (£25/yr), then buy this case for £1.",
            })
    fp = _DATASET_DIR / s["dataset_file"]
    if not fp.exists():
        raise HTTPException(status_code=500, detail="Scenario dataset file is missing.")
    import pandas as pd
    df = pd.read_csv(fp)
    _state.set_current_data(df)          # clears any prior teaching context
    _state.set_teaching_session(sid, s["free"])
    _state.init_variable_metadata(df)
    return {"id": sid, "title": s["title"], "rows": int(len(df)), "cols": int(len(df.columns)),
            "columns": list(df.columns)}


@router.get("/owned")
async def owned() -> Dict[str, Any]:
    uid = _state.get_uid()
    if not uid:
        return {"owned": []}
    return {"owned": list((_owned_set(uid) or {}).keys())}


@router.post("/checkout/{sid}")
async def checkout(sid: str) -> Dict[str, Any]:
    s = scenarios.get_scenario(sid)
    if not s or s["free"]:
        raise HTTPException(status_code=404, detail="No paid case with that id.")
    uid = _state.get_uid()
    if not uid:
        raise HTTPException(status_code=401, detail="Please sign in to buy a case.")
    # REQUIRE AN ACTIVE SUBSCRIPTION FIRST (the user's rule): £1 cases are only
    # purchasable by Patrons (licensed £25/yr). Non-subscribers cannot buy them.
    if not licence_live(uid):
        raise HTTPException(status_code=402, detail={
            "blocked": True, "action_type": "subscription",
            "reason": "Single cases can only be bought by subscribers. Create a £25/year "
                      "licence first, then this £1 case is yours.",
            "details": "Subscribe (£25/yr), then buy this case for £1.",
        })
    if _owns(uid, sid):
        return {"already_owned": True, "url": ""}
    email = (get_user(uid) or {}).get("email") or ""
    from app.services import pricing
    pid = pricing.stripe_price_id(pricing.tier_for_ip(_state.get_client_ip()), "teach")
    try:
        url = billing.create_teaching_checkout(uid, email, sid, price=pid or "")
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"url": url}
