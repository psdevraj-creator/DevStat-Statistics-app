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
import threading
import time
from pathlib import Path
from typing import Any, Dict

import app.config  # noqa: F401  (loads backend/.env into os.environ)

logger = logging.getLogger("devstat.firebase")

_admin_app = None
_firestore = None
_auth = None

# Free tier: each sign-in account gets this many analyses + this many charts
# before a £25/year licence is required. Separate pools.
FREE_ANALYSES = 5
FREE_CHARTS = 5
FREE_LIMIT = FREE_ANALYSES  # kept for backward-compat callers

# Fail-closed in-memory safety net. Because the online app runs on a single
# Cloud Run instance (`max-instances 1`), an in-machine per-user counter is a
# reliable backstop: if Firestore is ever unreachable (or the guest_trial /
# user writes are denied by rules), a free account still cannot exceed its
# 5 analyses / 5 charts — it never silently gets unlimited free compute.
_mem_usage: Dict[str, Dict[str, int]] = {}
_mem_licence: Dict[str, bool] = {}
_mem_lock = threading.Lock()


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


# ---------------------------------------------------------------------------
# Firestore REST access (cross-project). The app runs on GCP project
# "devstat-499409" but Firestore/Auth live in the SEPARATE Firebase project
# "devstat-fb-789999". The google-cloud-firestore client's project resolution is
# unreliable on Cloud Run (it can fall back to the runtime project -> 400
# "Invalid database id (default)"). The Firestore REST API accepts "(default)"
# and the SA's project is honoured, so we drive Firestore over REST here.
# ---------------------------------------------------------------------------

import base64
import urllib.error
import urllib.parse
import urllib.request

import google.auth.transport.requests as _ga_req
import google.oauth2.service_account as _ga_sac

_rest_token = None
_rest_token_exp = 0


def _sa_info() -> dict:
    sa = _service_account()
    if isinstance(sa, str) and sa.strip().startswith("{"):
        return json.loads(sa)
    return json.loads(Path(sa).read_text(encoding="utf-8"))


def _firebase_project() -> str:
    return (_env("DEVSTAT_FIREBASE_PROJECT_ID") or _sa_info().get("project_id") or "")


def _rest_bearer() -> str:
    global _rest_token, _rest_token_exp
    if _rest_token and time.time() < _rest_token_exp - 120:
        return _rest_token
    cred = _ga_sac.Credentials.from_service_account_info(
        _sa_info(), scopes=["https://www.googleapis.com/auth/cloud-platform"])
    cred.refresh(_ga_req.Request())
    _rest_token = cred.token
    _rest_token_exp = time.time() + 3600
    return _rest_token


def _doc_url(collection: str, docid: str) -> str:
    base = "https://firestore.googleapis.com/v1/projects/{}/databases/(default)/documents"
    base = base.format(_firebase_project())
    return "{}/{}/{}".format(base, urllib.parse.quote(str(collection), safe=""),
                             urllib.parse.quote(str(docid), safe=""))


def _rest_call(method: str, url: str, body: dict | None = None, timeout: int = 20):
    req = urllib.request.Request(url, method=method, headers={
        "Authorization": "Bearer " + _rest_bearer(), "Content-Type": "application/json"})
    if body is not None:
        req.data = json.dumps(body).encode("utf-8")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            data = {}
        return e.code, data


def _fields_to_dict(fields: dict) -> dict:
    out = {}
    for k, v in (fields or {}).items():
        if "stringValue" in v:
            out[k] = v["stringValue"]
        elif "booleanValue" in v:
            out[k] = v["booleanValue"]
        elif "integerValue" in v:
            out[k] = int(v["integerValue"])
        elif "doubleValue" in v:
            out[k] = float(v["doubleValue"])
        elif "mapValue" in v:
            out[k] = _fields_to_dict(v["mapValue"].get("fields", {}))
        elif "nullValue" in v:
            out[k] = None
        else:
            out[k] = None
    return out


def _dict_to_fields(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = {"mapValue": {"fields": _dict_to_fields(v)}}
        elif isinstance(v, bool):
            out[k] = {"booleanValue": v}
        elif isinstance(v, int):
            out[k] = {"integerValue": str(v)}
        elif isinstance(v, float):
            out[k] = {"doubleValue": v}
        elif isinstance(v, str):
            out[k] = {"stringValue": v}
        elif v is None:
            out[k] = {"nullValue": None}
        else:
            out[k] = {"stringValue": str(v)}
    return out


def _doc_patch(collection: str, docid: str, fields: dict) -> bool:
    field_paths = [
        "updateMask.fieldPaths=" + urllib.parse.quote(k, safe="._")
        for k in fields.keys()
    ]
    url = _doc_url(collection, docid) + "?" + "&".join(field_paths)
    st, _ = _rest_call("PATCH", url, {"fields": _dict_to_fields(fields)})
    return st in (200, 201)


def _doc_get(collection: str, docid: str) -> dict | None:
    st, data = _rest_call("GET", _doc_url(collection, docid))
    if st == 200:
        return _fields_to_dict(data.get("fields", {}))
    return None


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
        project_id = _env("DEVSTAT_FIREBASE_PROJECT_ID", "FIREBASE_PROJECT_ID") or (
            sa.get("project_id") if isinstance(sa, dict) else None)
        if not firebase_admin._apps:
            _admin_app = firebase_admin.initialize_app(
                credentials.Certificate(sa),
                {"projectId": project_id or None},
            )
        _auth = fb_auth
        # Bind the Firestore client EXPLICITLY to the service-account project.
        # On Cloud Run, `firestore.client()` can otherwise resolve the project
        # from the runtime (the GCP project where the app runs, e.g.
        # devstat-499409) instead of the Firebase project (devstat-fb-789999),
        # which fails every read/write with "400 Invalid database id (default)".
        import google.cloud.firestore as gcf
        import google.oauth2.service_account as _sac
        # BIND FIRESTORE DIRECTLY TO THE SA PROJECT. On Cloud Run this app runs on
        # GCP project "devstat-499409" while Firestore lives in the SEPARATE
        # Firebase project "devstat-fb-789999". Using the runtime/ADC credential
        # (firebase_admin.get_app().credential.get_credential()) makes the client
        # hit devstat-499409, which has no Firestore -> "Invalid database id
        # (default)". Building the SA credential explicitly and pinning the project
        # is what makes cross-project Firestore work (pubmed works only because its
        # app and Firestore share one project).
        # Firestore is accessed over the REST API (see the REST helpers above) so
        # we only initialise firebase_admin for AUTH here.
        _auth = fb_auth
        _firestore = None
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
    if not uid:
        return {}
    ok, _ = _init()
    if not ok:
        return {}
    try:
        return _doc_get("users", uid) or {}
    except Exception as exc:
        logger.warning("get_user failed: %s", exc)
        return {}


_admin_memo: set = set()


def is_admin(uid) -> bool:
    """Owner/admin allowlist (ADMIN_EMAILS) — free permanent licence, owns everything."""
    if not uid:
        return False
    if uid in _admin_memo:
        return True
    from app.config import ADMIN_EMAILS
    admins = {str(e).strip().lower() for e in ADMIN_EMAILS if e}
    if not admins:
        return False
    try:
        email = str((get_user(uid) or {}).get("email", "")).strip().lower()
    except Exception:
        return False
    if email in admins:
        _admin_memo.add(uid)
        return True
    return False


def update_user(uid: str, patch: dict) -> None:
    if not uid:
        return
    ok, _ = _init()
    if not ok:
        return
    try:
        _doc_patch("users", uid, {k: v for k, v in patch.items()})
    except Exception as exc:
        logger.warning("update_user failed: %s", exc)


def mark_teaching_owned(uid: str, sid: str) -> None:
    _mark_owned_field(uid, "teaching_owned", sid)


def mark_questionbank_owned(uid: str, qid: str) -> None:
    _mark_owned_field(uid, "qb_owned", qid)


def _mark_owned_field(uid: str, field: str, item: str) -> None:
    """Record that a user owns an item in an owned-map field (read-modify-write)."""
    if not uid or not item:
        return
    ok, _ = _init()
    if not ok:
        return
    try:
        existing = _doc_get("users", uid) or {}
        owned = dict(existing.get(field) or {})
        owned[str(item)] = True
        _doc_patch("users", uid, {field: owned})
    except Exception as exc:
        logger.warning("mark_%s failed: %s", field, exc)


def find_by_customer(customer_id: str) -> dict:
    """Find a user profile by their Stripe customer id ({} if none/missing)."""
    if not customer_id:
        return {}
    ok, _ = _init()
    if not ok:
        return {}
    try:
        url = "https://firestore.googleapis.com/v1/projects/{}/databases/(default)/documents:runQuery".format(
            _firebase_project())
        body = {"structuredQuery": {"from": [{"collectionId": "users"}],
                                    "where": {"fieldFilter": {"field": {"fieldPath": "stripe_customer_id"},
                                                              "op": "EQUAL", "value": {"stringValue": customer_id}}},
                                    "limit": 1}}
        st, data = _rest_call("POST", url, body)
        if st != 200:
            return {}
        for r in data or []:
            doc = (r.get("document") or {}).get("fields")
            if doc:
                d = _fields_to_dict(doc)
                d["uid"] = d.get("uid") or (r.get("document") or {}).get("name", "").rsplit("/", 1)[-1]
                return d
        return {}
    except Exception as exc:
        logger.warning("find_by_customer failed: %s", exc)
        return {}


def _fs():
    """Firestore is accessed over REST; return None (kept for compatibility)."""
    return None


def _mem_trial(key: str, kind: str) -> int:
    with _mem_lock:
        d = _mem_usage.get(key)
        return int(d.get(kind) or 0) if d else 0


def _mem_trial_set(key: str, kind: str, used: int) -> None:
    with _mem_lock:
        d = _mem_usage.setdefault(key, {})
        d[kind] = used


def _trial_doc_id(key: str) -> str:
    """Firestore document id for an identity (device or ip) usage counter."""
    return key.replace("/", "_")


def _trial_read(key: str, kind: str):
    """Read an identity's used count from Firestore (int) or None if unavailable."""
    try:
        d = _doc_get("usage", _trial_doc_id(key)) or {}
        return int(d.get(kind) or 0)
    except Exception as exc:
        logger.warning("trial read failed (%s): %s", key, exc)
        return None


def _trial_used(key: str, kind: str) -> int:
    """Fail-closed used count for one identity (device OR ip). Never under-counts:
    takes the max of the in-memory and Firestore counters."""
    mem = _mem_trial(key, kind)
    ok, _ = _init()
    if not ok:
        return mem
    fs = _trial_read(key, kind)
    if fs is None:
        return mem
    used = max(mem, fs)
    _mem_trial_set(key, kind, used)
    return used


def _trial_incr(key: str, kind: str) -> int:
    """Bump one identity counter: always in-memory, best-effort to Firestore."""
    used = _mem_trial(key, kind) + 1
    _mem_trial_set(key, kind, used)
    ok, _ = _init()
    if ok:
        try:
            _doc_patch("usage", _trial_doc_id(key), {kind: used})
        except Exception as exc:
            logger.warning("trial incr failed (%s): %s", key, exc)
    return used


def _paywall_reason() -> str:
    return (
        "You've had a lovely free run of it! ✨ That's your 5 analyses and 5 charts — "
        "well done, you really know your way around this. If you'd like to keep going, "
        "it's just £25 a year — like one pub lunch, or a coffee a week, for the whole "
        "year of unlimited number-crunching. Whenever you're ready."
    )


def trial_check_and_consume(device: str, ip: str, kind: str) -> Dict[str, Any]:
    """Apply the free-tier gate bound to the PHYSICAL machine (device) AND the IP
    address — NOT to the session. A compute call is charged to BOTH identities;
    if EITHER has exhausted its allowance it is blocked. Fail-closed: if Firestore
    is unreachable the in-memory counters still cap the free tier.
    """
    limit = FREE_ANALYSES if kind == "analysis" else FREE_CHARTS
    identities = []
    if device:
        identities.append("device|" + device)
    if ip:
        identities.append("ip|" + ip)
    if not identities:
        return {"blocked": True, "action_type": "account",
                "reason": "We couldn't see your device or address. Please sign in and try again."}
    for ident in identities:
        if _trial_used(ident, kind) >= limit:
            return {"blocked": True, "action_type": "subscription",
                    "reason": _paywall_reason(), "identity": ident,
                    "used": _trial_used(ident, kind), "limit": limit}
    for ident in identities:
        _trial_incr(ident, kind)
    return {"blocked": False, "identities": identities}


def trial_status(device: str, ip: str) -> Dict[str, Any]:
    """Free-tier usage snapshot (analyses + charts) for this machine+IP."""
    out = {"used_analyses": 0, "used_charts": 0,
           "analyses_left": FREE_ANALYSES, "charts_left": FREE_CHARTS,
           "requires_subscription": False}
    identities = []
    if device:
        identities.append("device|" + device)
    if ip:
        identities.append("ip|" + ip)
    for ident in identities:
        a = _trial_used(ident, "analysis")
        c = _trial_used(ident, "chart")
        if a > out["used_analyses"]:
            out["used_analyses"] = a
        if c > out["used_charts"]:
            out["used_charts"] = c
    out["analyses_left"] = max(0, FREE_ANALYSES - out["used_analyses"])
    out["charts_left"] = max(0, FREE_CHARTS - out["used_charts"])
    out["requires_subscription"] = (out["used_analyses"] >= FREE_ANALYSES or out["used_charts"] >= FREE_CHARTS)
    return out


def free_limit() -> int:
    return FREE_ANALYSES


def licence_live(uid: str) -> bool:
    """True when a paid (£25/yr) licence is active and not yet expired.

    Fail-closed with an in-memory cache: once a uid is seen as licensed it stays
    protected for the life of the worker even if Firestore blips. If Firestore is
    unreachable and we have no cached decision, we return False (treated as free,
    so the trial counters still apply) rather than granting unlimited access.
    """
    if not uid:
        return False
    if is_admin(uid):
        with _mem_lock:
            _mem_licence[uid] = True
        return True
    with _mem_lock:
        cached = _mem_licence.get(uid)
    ok, _ = _init()
    if ok:
        try:
            u = _doc_get("users", uid) or {}
        except Exception as exc:
            logger.warning("licence_live firestore failed: %s", exc)
            u = None
        if u is not None:
            if not u.get("licensed"):
                live = False
            else:
                until = u.get("licensed_until")
                try:
                    live = bool(until) and float(until) > time.time()
                except Exception:
                    live = bool(u.get("licensed"))
            with _mem_lock:
                _mem_licence[uid] = live
            return live
    with _mem_lock:
        return bool(_mem_licence.get(uid, False))


# ---------------------------------------------------------------------------
# Per-user dataset persistence (real isolation + cross-instance persistence).
# A user's dataset is stored on their own Firestore doc (users/{uid}) so no
# account can ever see another account's data, and it survives instance
# restarts / scale-to-zero on Cloud Run.
# ---------------------------------------------------------------------------


def save_user_dataset(uid: str, csv: str, filename: str = "", meta: str = "{}") -> bool:
    if not uid:
        return False
    ok, _ = _init()
    if not ok:
        return False
    try:
        _doc_patch("users", uid, {
            "dataset_csv": csv, "dataset_filename": filename, "dataset_meta": meta,
            "dataset_updated_at": __import__("time").time(),
        })
        return True
    except Exception as exc:
        logger.warning("save_user_dataset failed: %s", exc)
        return False


def load_user_dataset(uid: str) -> dict:
    if not uid:
        return {"csv": "", "filename": "", "meta": "{}"}
    try:
        d = _doc_get("users", uid) or {}
        return {"csv": d.get("dataset_csv", ""), "filename": d.get("dataset_filename", ""),
                "meta": d.get("dataset_meta", "{}")}
    except Exception as exc:
        logger.warning("load_user_dataset failed: %s", exc)
        return {"csv": "", "filename": "", "meta": "{}"}


def clear_user_dataset(uid: str) -> None:
    if not uid:
        return
    ok, _ = _init()
    if not ok:
        return
    try:
        _doc_patch("users", uid, {"dataset_csv": "", "dataset_filename": "", "dataset_meta": "{}"})
    except Exception as exc:
        logger.warning("clear_user_dataset failed: %s", exc)
