"""DevStat billing — Stripe (same account as pubmed; its own £25/yr product).

Uses the SAME Stripe account as pubmed (same STRIPE_SECRET_KEY) but a distinct
£25/year recurring PRODUCT/PRICE created for DevStat (DEVSTAT_STRIPE_PRICE_ID).
Money lands in that shared Stripe account.

On subscription events the licence is written into DevStat's own Firestore
(users/{uid}: licensed, licensed_until). The licence RENEWS automatically each
year (recurring subscription); when the year lapses/cancels, the licence is
deactivated and the user must buy again.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import app.config  # noqa: F401  (loads backend/.env into os.environ)

logger = logging.getLogger("devstat.billing")

FREE_LIMIT = 3  # free analyses before a licence is required


def _env(*names):
    for n in names:
        if os.environ.get(n):
            return os.environ[n]
    return ""


def secret_key() -> str:
    # Shared Stripe account: same secret as pubmed, or an explicit DevStat one.
    return _env("DEVSTAT_STRIPE_SECRET_KEY", "STRIPE_SECRET_KEY")


def price_id() -> str:
    return _env("DEVSTAT_STRIPE_PRICE_ID")


def teaching_price_id() -> str:
    return _env("DEVSTAT_TEACHING_PRICE_ID")


def questionbank_price_id() -> str:
    return _env("DEVSTAT_QB_PRICE_ID")


def webhook_secret() -> str:
    return _env("DEVSTAT_STRIPE_WEBHOOK_SECRET", "STRIPE_WEBHOOK_SECRET")


def construct_event(payload: bytes, signature: str, secret: str) -> dict:
    """Verify a Stripe webhook signature and return the event as a plain dict."""
    import stripe
    stripe.api_key = secret_key()
    try:
        event = stripe.Webhook.construct_event(payload, signature, secret)
        return event.to_dict()
    except Exception as exc:
        raise ValueError(f"Invalid webhook signature: {exc}")


def configured() -> bool:
    return bool(secret_key() and price_id())


def _api():
    import stripe
    stripe.api_key = secret_key()
    return stripe


def create_checkout(uid: str, email: str = "", return_url: str = "", price: str = "") -> str:
    s = _api()
    price = price or price_id()
    if not price:
        raise ValueError("DevStat Stripe price not configured (DEVSTAT_STRIPE_PRICE_ID).")
    session = s.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price, "quantity": 1}],
        success_url=(return_url or "http://127.0.0.1:8150/") + "?paid=1",
        cancel_url=(return_url or "http://127.0.0.1:8150/"),
        client_reference_id=uid,
        subscription_data={"metadata": {"uid": uid, "app": "devstat", "plan": "pro"}},
        customer_email=email or None,
    )
    return session.url


def create_questionbank_checkout(uid: str, email: str = "", qid: str = "", price: str = "") -> str:
    """A one-off £5 checkout that unlocks a single question bank."""
    s = _api()
    price = price or questionbank_price_id()
    if not price:
        raise ValueError("Question banks are not configured (set DEVSTAT_QB_PRICE_ID).")
    session = s.checkout.Session.create(
        mode="payment",
        line_items=[{"price": price, "quantity": 1}],
        success_url="http://127.0.0.1:8150/learning?paid=1",
        cancel_url="http://127.0.0.1:8150/learning",
        client_reference_id=uid,
        metadata={"uid": uid, "app": "devstat", "plan": "qb", "qb_case": qid},
        customer_email=email or None,
    )
    return session.url


def create_teaching_checkout(uid: str, email: str = "", sid: str = "", price: str = "") -> str:
    """A one-off £1 checkout that unlocks a single paid teaching case."""
    s = _api()
    price = price or teaching_price_id()
    if not price:
        raise ValueError("Teaching case purchases are not configured (set DEVSTAT_TEACHING_PRICE_ID).")
    session = s.checkout.Session.create(
        mode="payment",
        line_items=[{"price": price, "quantity": 1}],
        success_url="http://127.0.0.1:8150/teaching?paid=1",
        cancel_url="http://127.0.0.1:8150/teaching",
        client_reference_id=uid,
        metadata={"uid": uid, "app": "devstat", "plan": "case", "teaching_case": sid},
        customer_email=email or None,
    )
    return session.url


def _period_end(sub: dict) -> int:
    """Subscription period end (handles newer Stripe APIs omitting current_period_end)."""
    cpe = sub.get("current_period_end")
    if cpe:
        return int(cpe)
    anchor = int(sub.get("billing_cycle_anchor") or 0)
    if not anchor:
        return int(time.time()) + 365 * 86400
    days = 365  # DevStat yearly licence
    items = sub.get("items") or {}
    for item in (items.get("data") or []):
        rec = (item.get("price") or {}).get("recurring") or {}
        interval = rec.get("interval")
        count = int(rec.get("interval_count") or 1)
        days = {"year": 365 * count, "week": 7 * count, "day": count}.get(interval, 365 * count)
        break
    return anchor + days * 86400


def apply_webhook(event: dict, store) -> None:
    """Apply a Stripe event to DevStat's Firestore licence."""
    etype = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    if etype == "checkout.session.completed":
        uid = data.get("client_reference_id") or (data.get("metadata") or {}).get("uid")
        cust = data.get("customer")
        meta = data.get("metadata") or {}
        if meta.get("teaching_case") and uid:
            # One-off £1 purchase of a single teaching case (nested-map write).
            store.mark_teaching_owned(uid, str(meta["teaching_case"]))
            return
        if meta.get("qb_case") and uid:
            # One-off £5 purchase of a question bank.
            store.mark_questionbank_owned(uid, str(meta["qb_case"]))
            return
        if uid and meta.get("app") in ("devstat", None):
            patch = {"stripe_customer_id": cust or ""}
            store.update_user(uid, patch)
        return

    if etype in ("customer.subscription.created", "customer.subscription.updated"):
        uid = (data.get("metadata") or {}).get("uid")
        if not uid:
            found = store.find_by_customer(data.get("customer") or "")
            uid = found.get("uid") if found else None
        if uid:
            status = data.get("status") or ""
            store.update_user(uid, {
                "licensed": status in ("active", "trialing"),
                "licensed_until": _period_end(data),
                "plan": "pro",
                "stripe_customer_id": data.get("customer") or "",
            })
        return

    if etype == "customer.subscription.deleted":
        uid = (data.get("metadata") or {}).get("uid")
        if not uid:
            found = store.find_by_customer(data.get("customer") or "")
            uid = found.get("uid") if found else None
        if uid:
            store.update_user(uid, {"licensed": False, "licensed_until": None})
        return

    logger.info("Unhandled webhook event type: %s", etype)
