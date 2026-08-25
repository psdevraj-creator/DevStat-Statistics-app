"""One-off: wire DevStat's Â£25/yr Stripe billing into your (shared) Stripe account.

Reads STRIPE_SECRET_KEY from the pubmed-search .env (never prints it), creates an
idempotent "DevStat Pro" product + a Â£25/year recurring PRICE, creates a DevStat
webhook endpoint (capturing its signing secret), and writes DevStat's .env files
with DEVSTAT_STRIPE_* keys. Secret VALUES are only written to disk â€” never shown.
"""
import os
import re

ROOT = r"C:\Users\dell 7390\OneDrive\Desktop\Desktop files\DevStat"
PUBMED_ENV = r"C:\Users\dell 7390\OneDrive\Desktop\Website project\pubmed-search\.env"
BACKEND_ENV = os.path.join(ROOT, "backend", ".env")
FRONTEND_ENV = os.path.join(ROOT, "frontend", ".env")  # for VITE_FIREBASE_*

WEBHOOK_URL = "https://devstat-statistics-app-991466352708.europe-west1.run.app/api/license/webhook"
SUBSCRIPTION_EVENTS = [
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
]


def read_key(path, name):
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(rf"^{re.escape(name)}=(.*)$", line.strip())
            if m:
                return m.group(1).strip()
    return ""


def upsert_env(path, pairs):
    """Set key=value lines, preserving existing keys and comments."""
    lines = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
    existing = {}
    order = []
    for i, line in enumerate(lines):
        if line.strip() and not line.strip().startswith("#") and "=" in line:
            k = line.split("=", 1)[0].strip()
            existing[k] = i
            order.append(k)
    for k, v in pairs.items():
        if k in existing:
            lines[existing[k]] = f"{k}={v}"
        else:
            lines.append(f"{k}={v}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def mask(v):
    return v[:6] + "â€¦" + v[-4:] if len(v) > 12 else "****"


def main():
    secret = read_key(PUBMED_ENV, "STRIPE_SECRET_KEY")
    if not secret:
        print("ERROR: no STRIPE_SECRET_KEY in pubmed .env")
        return
    import stripe
    stripe.api_key = secret

    # 1) Idempotent product lookup by metadata
    prod = None
    for p in stripe.Product.list(limit=100).data:
        try:
            if getattr(p.metadata, "app", "") == "devstat":
                prod = p
                break
        except Exception:
            pass
    if not prod:
        prod = stripe.Product.create(
            name="DevStat Pro (1 year)",
            description="DevStat annual licence - medical statistics desktop/web app",
            metadata={"app": "devstat"},
        )
    # 2) Â£25/year recurring price (idempotent by nickname lookup)
    price = None
    for p in stripe.Price.list(limit=100).data:
        if p.product == prod.id and p.recurring and p.recurring.interval == "year":
            price = p
            break
    if not price:
        price = stripe.Price.create(
            product=prod.id,
            unit_amount=2500,          # Â£25.00
            currency="gbp",
            recurring={"interval": "year"},
            nickname="DevStat 1-year",
            metadata={"app": "devstat"},
        )

    # 3) Webhook endpoint (idempotent by URL) -> capture its signing secret
    wh = None
    for e in stripe.WebhookEndpoint.list(limit=100).data:
        if e.url == WEBHOOK_URL:
            wh = e
            break
    wh_secret = ""
    if not wh:
        created = stripe.WebhookEndpoint.create(
            url=WEBHOOK_URL,
            enabled_events=SUBSCRIPTION_EVENTS,
            description="DevStat licence activation",
            metadata={"app": "devstat"},
        )
        # The signing secret is ONLY returned on creation.
        wh_secret = created.secret
    else:
        print("NOTE: webhook already exists; re-use STRIPE_WEBHOOK_SECRET from pubmed .env as fallback.")
        wh_secret = read_key(PUBMED_ENV, "STRIPE_WEBHOOK_SECRET")

    print("DevStat product id :", prod.id)
    print("DevStat price  id  :", price.id, f"(Â£{price.unit_amount/100:.0f}/yr)")
    print("Webhook url        :", WEBHOOK_URL)

    upsert_env(BACKEND_ENV, {
        "DEVSTAT_STRIPE_SECRET_KEY": secret,
        "DEVSTAT_STRIPE_PRICE_ID": price.id,
        "DEVSTAT_STRIPE_WEBHOOK_SECRET": wh_secret or read_key(PUBMED_ENV, "STRIPE_WEBHOOK_SECRET"),
        # DevStat is its OWN Firebase project (filled after you create it).
        "DEVSTAT_FIREBASE_PROJECT_ID": "",
        "DEVSTAT_FIREBASE_SERVICE_ACCOUNT": "",
        "DEVSTAT_AUTH_SECRET": os.urandom(32).hex(),
        "DEVSTAT_MAX_DEVICES": "3",
    })
    print("\nWrote DEVSTAT_STRIPE_* to:", BACKEND_ENV, "(values not shown)")
    print("Secret token mask  : DEVSTAT_STRIPE_SECRET_KEY =", mask(secret))
    print("Frontend VITE_FIREBASE_* go in:", FRONTEND_ENV, "(set after creating the Firebase project)")


if __name__ == "__main__":
    main()

