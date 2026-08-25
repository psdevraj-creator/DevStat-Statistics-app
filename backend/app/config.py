import os
from pathlib import Path

# ── Load backend/.env into the environment (no external dependency) ────
# Secrets and config (DEVSTAT_STRIPE_*, DEVSTAT_FIREBASE_*, DEVSTAT_AUTH_*)
# live there so they are available here and to the auth/billing services.
def _load_dotenv() -> None:
    # config.py is at backend/app/config.py -> parent.parent = backend/
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            key, _, value = s.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


_load_dotenv()

PROJECT_NAME = "DevStat - Medical Statistics Software"
VERSION = "1.2.0"
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".sav"}

# ── Analysis engine ─────────────────────────────────────────────────────
DEVSTAT_ENGINE = "py"

# ── Desktop Edition (offline) ───────────────────────────────────────────
# Set by the desktop launcher (DEVSTAT_OFFLINE=1). When on, the app serves the
# Desktop Edition: no Firebase/Stripe, mandatory local registration, and a free
# 5-analysis / 5-chart trial with a machine-bound paid activation key.
OFFLINE = os.environ.get("DEVSTAT_OFFLINE", "") == "1"

# ── Firebase (DevStat own project) ─────────────────────────────────────
FIREBASE_PROJECT_ID = os.environ.get("DEVSTAT_FIREBASE_PROJECT_ID", "")
FIREBASE_SERVICE_ACCOUNT = os.environ.get("DEVSTAT_FIREBASE_SERVICE_ACCOUNT", "")

# ── Billing (Stripe, same account as pubmed) ───────────────────────────
STRIPE_SECRET_KEY = os.environ.get("DEVSTAT_STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID = os.environ.get("DEVSTAT_STRIPE_PRICE_ID", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("DEVSTAT_STRIPE_WEBHOOK_SECRET", "")

# ── Owner / admin accounts (free permanent license for testing) ───────
ADMIN_EMAILS = [
    e.strip().lower()
    for e in os.environ.get("DEVSTAT_ADMIN_EMAILS", "psdevraj@gmail.com").split(",")
    if e.strip()
]
