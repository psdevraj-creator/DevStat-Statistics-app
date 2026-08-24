"""DevStat license router — Stripe billing (same account as pubmed) + the
3-free-calls gate. Licence is £25/year, renewable each year; when it lapses the
user must buy again.

Firestore (DevStat own project) stores per-user licence state; Stripe (same
account as pubmed, own £25/yr price) is the payment source.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException, Request

from app.services import billing, firebase_store as store
from app.services import session_guard
from app.services.firebase_store import licence_live

router = APIRouter()


def _bearer(authorization: str) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def _require_uid(authorization: str) -> str:
    """Resolve the signed DevStat session token -> uid (with device guard)."""
    token = _bearer(authorization)
    parts = token.split(".") if token else []
    if len(parts) != 4:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    uid = parts[0]
    if not session_guard.validate_token(uid, token):
        raise HTTPException(status_code=401,
                            detail="This session was signed out or signed in on too many devices. Please sign in again.")
    return uid


def _status(uid: str) -> Dict[str, Any]:
    live = licence_live(uid) if uid else False
    u = store.get_user(uid)
    used = int(u.get("usage_count") or 0)
    limit = store.free_limit()
    remaining = -1 if live else max(0, limit - used)
    return {
        "licensed": live,
        "plan": "pro" if live else "free",
        "licensed_until": u.get("licensed_until"),
        "remaining_free": remaining,
        "free_limit": limit,
        "usage_count": used,
        "requires_subscription": (not live and used >= limit),
        "price_gbp_per_year": 25,
    }


@router.get("/license/status")
async def status(authorization: str = Header(default="")) -> Dict[str, Any]:
    uid = _require_uid(authorization)
    return _status(uid)


@router.post("/license/use")
async def use(authorization: str = Header(default="")) -> Dict[str, Any]:
    uid = _require_uid(authorization)
    live = licence_live(uid) if uid else False
    if not live and uid:
        used = store.bump_usage(uid)
    else:
        used = int(store.get_user(uid).get("usage_count") or 0)
    return _status(uid)


@router.post("/license/checkout")
async def checkout(authorization: str = Header(default="")) -> Dict[str, Any]:
    uid = _require_uid(authorization)
    if not billing.configured():
        raise HTTPException(status_code=503, detail="Billing not configured (DEVSTAT_STRIPE_PRICE_ID).")
    email = store.get_user(uid).get("email") or ""
    try:
        url = billing.create_checkout(uid, email)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe checkout failed: {exc}")
    return {"url": url}


@router.post("/license/webhook")
async def webhook(request: Request) -> Dict[str, Any]:
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    secret = billing.webhook_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="Webhook secret not configured.")
    try:
        event = billing.construct_event(payload, sig, secret)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    billing.apply_webhook(event, store)
    return {"received": True}
