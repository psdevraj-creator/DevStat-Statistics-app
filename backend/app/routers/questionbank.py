"""DevStat Question-bank router.

Endpoints:
  GET  /api/questionbank/list          -> bank metadata (owned/licensed flags)
  GET  /api/questionbank/{id}          -> full bank (100 questions) if owned
  POST /api/questionbank/{id}/load     -> load the bank's synthetic dataset
  GET  /api/questionbank/owned         -> ids the signed-in user owns
  POST /api/questionbank/checkout/{id} -> £5 Stripe checkout (only if subscribed)

Rule: banks cost £5 and are purchasable ONLY by subscribed (licensed) users; a
subscriber still has to buy each bank. Guests and non-subscribers cannot.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

import app.state as _state
from app.services import billing
from app.services.firebase_store import get_user, licence_live, is_admin
from app.questionbank import list_packs as _list_banks

router = APIRouter(prefix="/questionbank", tags=["Question Bank"])

_DATASET_DIR = Path(__file__).resolve().parent.parent / "teaching" / "datasets"

_LOCK = ("This question bank costs £5 and is for subscribers. Subscribe (£25/yr), "
         "then buy the bank for £5 to unlock it.")


def _owned_set(uid: str) -> dict:
    u = get_user(uid) or {}
    return u.get("qb_owned") or {}


def _owns(uid: str, qid: str) -> bool:
    if uid and is_admin(uid):
        return True
    return bool((_owned_set(uid) or {}).get(qid))


@router.get("/list")
async def list_banks() -> Dict[str, Any]:
    uid = _state.get_uid()
    admin = bool(uid and is_admin(uid))
    owned = _owned_set(uid) if uid else {}
    out = []
    for b in _list_banks():
        out.append({**b, "owned": bool(admin or owned.get(b["id"])), "licensed": bool(uid and (admin or licence_live(uid)))})
    return {"banks": out}


@router.get("/owned")
async def owned() -> Dict[str, Any]:
    uid = _state.get_uid()
    return {"owned": list((_owned_set(uid) or {}).keys()) if uid else []}


@router.get("/{qid}")
async def get_bank(qid: str) -> Dict[str, Any]:
    from app.questionbank import get_pack
    p = get_pack(qid)
    if not p:
        raise HTTPException(status_code=404, detail="Question bank not found.")
    uid = _state.get_uid()
    accessible = p["price_cents"] == 0 or (uid and _owns(uid, qid))
    if not accessible:
        return {"id": p["id"], "title": p["title"], "blurb": p["blurb"], "emoji": p["emoji"],
                "price_cents": p["price_cents"], "locked": True, "locked_reason": _LOCK, "questions": []}
    return p


@router.post("/{qid}/load")
async def load_bank(qid: str) -> Dict[str, Any]:
    from app.questionbank import get_pack
    p = get_pack(qid)
    if not p:
        raise HTTPException(status_code=404, detail="Question bank not found.")
    uid = _state.get_uid()
    if p["price_cents"] > 0:
        if not uid:
            raise HTTPException(status_code=401, detail="Please sign in to use this bank.")
        if not _owns(uid, qid):
            raise HTTPException(status_code=402, detail={"blocked": True, "action_type": "subscription",
                                                         "reason": _LOCK, "details": "Subscribe (£25/yr), then buy this bank for £5."})
    fp = _DATASET_DIR / p["dataset_file"]
    if not fp.exists():
        raise HTTPException(status_code=500, detail="Question-bank dataset missing.")
    import pandas as pd
    _state.set_current_data(pd.read_csv(fp))
    _state.init_variable_metadata(_state.current_data)
    from app.state import set_current_filename
    set_current_filename(p["dataset_file"])
    return {"id": p["id"], "title": p["title"], "rows": 0, "cols": 0, "questions": len(p["questions"])}


@router.post("/checkout/{qid}")
async def checkout(qid: str) -> Dict[str, Any]:
    from app.questionbank import get_pack
    p = get_pack(qid)
    if not p or p["price_cents"] == 0:
        raise HTTPException(status_code=404, detail="No purchasable bank with that id.")
    uid = _state.get_uid()
    if not uid:
        raise HTTPException(status_code=401, detail="Please sign in to buy a question bank.")
    if not licence_live(uid):
        raise HTTPException(status_code=402, detail={"blocked": True, "action_type": "subscription",
            "reason": "Question banks are only for subscribers. Create a £25/year licence first, then this £5 bank is yours.",
            "details": "Subscribe (£25/yr), then buy this bank for £5."})
    if _owns(uid, qid):
        return {"already_owned": True, "url": ""}
    email = (get_user(uid) or {}).get("email") or ""
    from app.services import pricing
    pid = pricing.stripe_price_id(pricing.tier_for_ip(_state.get_client_ip()), "qb")
    try:
        url = billing.create_questionbank_checkout(uid, email, qid, price=pid or "")
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"url": url}
