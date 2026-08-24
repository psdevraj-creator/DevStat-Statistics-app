"""DevStat Firebase store — its OWN Firebase project (separate from pubmed).

Authentication lives in Firebase Auth; each user's profile + licence lives in
Cloud Firestore under ``users/{uid}``:
    { email, name, provider, plan, licensed, licensed_until, usage_count,
      stripe_customer_id }

You check this data at console.firebase.google.com -> your DevStat project ->
Authentication (accounts) and Firestore (profiles/licences). It is a different
project/database to pubmed's.

Uses the Firebase Admin SDK, imported lazily and fail-soft: if the service
account or package is not present yet, DevStat still boots and reports "not
configured". Set DEVSTAT_FIREBASE_SERVICE_ACCOUNT to a path (or JSON) for a
fresh project to go live.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import app.config  # noqa: F401  (loads backend/.env into os.environ)

logger = logging.getLogger("devstat.firebase")

_admin_app = None
_firestore = None
_auth = None

FREE_LIMIT = 3  # free analyses before a licence is required


def _env(*names):
    for n in names:
        if os.environ.get(n):
            return os.environ[n]
    return ""


def _service_account():
    raw = _env("DEVSTAT_FIREBASE_SERVICE_ACCOUNT", "FIREBASE_SERVICE_ACCOUNT")
    if not raw:
        return None
    p = Path(raw.strip())
    return str(p) if p.exists() else raw.strip()


def _init():
    """Initialise firebase_admin once, from config. Returns (ok, detail)."""
    global _admin_app, _firestore, _auth
    if _auth is not None:
        return True, "ready"
    sa = _service_account()
    if not sa:
        return False, "DevStat Firebase is not configured (set DEVSTAT_FIREBASE_SERVICE_ACCOUNT)."
    try:
        import firebase_admin
        from firebase_admin import auth as fb_auth
        from firebase_admin import credentials, firestore as fb_firestore
    except Exception as exc:  # package missing
        return False, f"firebase_admin is not installed: {exc}"
    try:
        # credentials.Certificate needs a DICT (or a file path). When the SA is
        # supplied as an inline JSON string (e.g. via a Cloud Run env var),
        # parse it into a dict first.
        import json as _json
        if isinstance(sa, str) and sa.strip().startswith("{"):
            sa = _json.loads(sa)
        if not firebase_admin._apps:
            _admin_app = firebase_admin.initialize_app(
                credentials.Certificate(sa),
                {"projectId": _env("DEVSTAT_FIREBASE_PROJECT_ID", "FIREBASE_PROJECT_ID") or None},
            )
        _auth = fb_auth
        _firestore = fb_firestore.client()
        return True, "ready"
    except Exception as exc:
        logger.warning("Firebase init failed: %s", exc)
        return False, f"Firebase init failed: {exc}"


def is_configured() -> bool:
    ok, _ = _init()
    return ok


def verify_id_token(id_token: str):
    """Verify a Firebase ID token, returning the decoded user dict or None."""
    ok, _ = _init()
    if not ok or not id_token or _auth is None:
        return None
    try:
        return _auth.verify_id_token(id_token)
    except Exception as exc:
        logger.warning("ID token verification failed: %s", exc)
        return None


def get_user(uid: str) -> dict:
    """Return the Firestore profile for a user (dict, or {} if unavailable)."""
    if not _firestore:
        ok, _ = _init()
        if not ok:
            return {}
    try:
        snap = _firestore.collection("users").document(uid).get()
        return snap.to_dict() or {}
    except Exception as exc:
        logger.warning("get_user failed: %s", exc)
        return {}


def update_user(uid: str, patch: dict) -> None:
    if not _firestore:
        ok, _ = _init()
        if not ok:
            return
    try:
        _firestore.collection("users").document(uid).set(patch, merge=True)
    except Exception as exc:
        logger.warning("update_user failed: %s", exc)


def find_by_customer(customer_id: str) -> dict:
    """Find a user profile by their Stripe customer id ({} if none/missing)."""
    if not customer_id:
        return {}
    if not _firestore:
        ok, _ = _init()
        if not ok:
            return {}
    try:
        q = _firestore.collection("users").where("stripe_customer_id", "==", customer_id).limit(1).get()
        for doc in q:  # Firestore query returns an iterable of DocumentSnapshot
            d = doc.to_dict() or {}
            d["uid"] = d.get("uid") or doc.id
            return d
        return {}
    except Exception as exc:
        logger.warning("find_by_customer failed: %s", exc)
        return {}


def bump_usage(uid: str) -> int:
    """Increment usage_count, returning the new count (non-crashing on no-Firebase)."""
    u = get_user(uid)
    n = int(u.get("usage_count") or 0) + 1
    update_user(uid, {"usage_count": n})
    return n


def free_limit() -> int:
    return FREE_LIMIT


def licence_live(uid: str) -> bool:
    """True when a paid (£25/yr) licence is active and not yet expired."""
    u = get_user(uid)
    if not u.get("licensed"):
        return False
    until = u.get("licensed_until")
    try:
        return bool(until) and float(until) > time.time()
    except Exception:
        return bool(u.get("licensed"))


# ---------------------------------------------------------------------------
# Per-user dataset persistence (real isolation + cross-instance persistence).
# A user's dataset is stored on their own Firestore doc (users/{uid}) so no
# account can ever see another account's data, and it survives instance
# restarts / scale-to-zero on Cloud Run.
# ---------------------------------------------------------------------------


def save_user_dataset(uid: str, csv: str, filename: str = "", meta: str = "{}") -> bool:
    if not uid or not _firestore:
        ok, _ = _init()
        if not ok:
            return False
    try:
        _firestore.collection("users").document(uid).set({
            "dataset_csv": csv,
            "dataset_filename": filename,
            "dataset_meta": meta,
            "dataset_updated_at": __import__("time").time(),
        }, merge=True)
        return True
    except Exception as exc:
        logger.warning("save_user_dataset failed: %s", exc)
        return False


def load_user_dataset(uid: str) -> dict:
    if not uid or not _firestore:
        return {"csv": "", "filename": "", "meta": "{}"}
    try:
        snap = _firestore.collection("users").document(uid).get()
        d = snap.to_dict() or {}
        return {"csv": d.get("dataset_csv", ""), "filename": d.get("dataset_filename", ""),
                "meta": d.get("dataset_meta", "{}")}
    except Exception as exc:
        logger.warning("load_user_dataset failed: %s", exc)
        return {"csv": "", "filename": "", "meta": "{}"}


def clear_user_dataset(uid: str) -> None:
    if not uid or not _firestore:
        ok, _ = _init()
        if not ok:
            return
    try:
        _firestore.collection("users").document(uid).set({
            "dataset_csv": "", "dataset_filename": "", "dataset_meta": "{}",
        }, merge=True)
    except Exception as exc:
        logger.warning("clear_user_dataset failed: %s", exc)


# ---------------------------------------------------------------------------
# Guest trial limit — 3 analyses per machine/IP, LIFETIME (not per session).
# Stored in Firestore at guest_trial/{device_key} so it survives reloads and is
# never reset when the user reopens the web app. A signed-in user is exempt.
# ---------------------------------------------------------------------------
FREE_TRIAL_LIMIT = 3


def guest_trial_status(device_key: str) -> dict:
    if not device_key or not _firestore:
        ok, _ = _init()
        if not ok:
            return {"used": 0, "limit": FREE_TRIAL_LIMIT, "eligible": True}
    try:
        snap = _firestore.collection("guest_trial").document(device_key).get()
        d = snap.to_dict() or {}
        used = int(d.get("count") or 0)
        return {"used": used, "limit": FREE_TRIAL_LIMIT, "eligible": used < FREE_TRIAL_LIMIT}
    except Exception as exc:
        logger.warning("guest_trial_status failed: %s", exc)
        # Fail-open on temporary errors so we never break a legitimate search.
        return {"used": 0, "limit": FREE_TRIAL_LIMIT, "eligible": True}


def guest_trial_consume(device_key: str) -> dict:
    """Increment and return trial status. Fail-open on store errors."""
    if not device_key or not _firestore:
        ok, _ = _init()
        if not ok:
            return {"used": 0, "limit": FREE_TRIAL_LIMIT, "eligible": True}
    try:
        import firebase_admin
        import time as _t
        doc = _firestore.collection("guest_trial").document(device_key)
        try:
            doc.update({"count": firebase_admin.firestore.Increment(1), "updated_at": _t.time()})
        except Exception:
            doc.set({"count": 1, "updated_at": _t.time(), "device_key": device_key}, merge=True)
        snap = doc.get()
        used = int(snap.to_dict().get("count") or 0)
    except Exception as exc:
        logger.warning("guest_trial_consume failed: %s", exc)
        used = 0
    return {"used": used, "limit": FREE_TRIAL_LIMIT, "eligible": used <= FREE_TRIAL_LIMIT}
