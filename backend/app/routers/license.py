"""DevStat license router — Stripe billing (same account as pubmed) + the
free-tier usage report. Licence is £25/year, renewable each year; when it lapses
the user must buy again. Free accounts get 5 analyses + 5 charts (bound to the
machine+IP identity, not the session).

Firestore (DevStat own project) stores per-user licence state; Stripe (same
account as pubmed, own £25/yr price) is the payment source.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException, Request

from app.services import billing, firebase_store as store
from app.services import session_guard, pricing
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


def _status(uid: str, device: str = "", ip: str = "") -> Dict[str, Any]:
    from app.services.firebase_store import trial_status
    live = licence_live(uid) if uid else False
    ts = trial_status(device, ip)
    u = store.get_user(uid)
    return {
        "licensed": live,
        "plan": "pro" if live else "free",
        "licensed_until": u.get("licensed_until"),
        "remaining_free": -1 if live else min(ts["analyses_left"], ts["charts_left"]),
        "free_limit": store.free_limit(),
        "usage_count": ts["used_analyses"],
        "used_analyses": ts["used_analyses"],
        "used_charts": ts["used_charts"],
        "analyses_left": -1 if live else ts["analyses_left"],
        "charts_left": -1 if live else ts["charts_left"],
        "requires_subscription": (not live) and ts["requires_subscription"],
        "price_gbp_per_year": 25,
    }


@router.get("/license/status")
async def status(request: Request, authorization: str = Header(default="")) -> Dict[str, Any]:
    uid = _require_uid(authorization)
    return _status(uid, request.headers.get("x-devstat-device", ""),
                   (request.client.host if request.client else ""))


@router.post("/license/use")
async def use(request: Request, authorization: str = Header(default="")) -> Dict[str, Any]:
    # Reports the machine+IP free-tier usage. Actual analysis consumption is
    # charged by the dispatcher gate; this endpoint is a read-only snapshot.
    uid = _require_uid(authorization)
    return _status(uid, request.headers.get("x-devstat-device", ""),
                   (request.client.host if request.client else ""))


@router.post("/license/checkout")
async def checkout(authorization: str = Header(default="")) -> Dict[str, Any]:
    uid = _require_uid(authorization)
    if not billing.configured():
        raise HTTPException(status_code=503, detail="Billing not configured (DEVSTAT_STRIPE_PRICE_ID).")
    email = store.get_user(uid).get("email") or ""
    import app.state as _st
    pid = pricing.stripe_price_id(pricing.tier_for_ip(_st.get_client_ip()), "sub")
    try:
        url = billing.create_checkout(uid, email, price=pid or "")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe checkout failed: {exc}")
    return {"url": url}


@router.get("/pricing")
async def pricing_info() -> Dict[str, Any]:
    """Return the region-adjusted GBP prices for this client's location."""
    import app.state as _st
    return pricing.region_status(_st.get_client_ip())


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
