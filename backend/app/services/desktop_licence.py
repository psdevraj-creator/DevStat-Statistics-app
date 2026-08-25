"""Desktop Edition — local licence & free-tier store (for OFFLINE analysis).

The Desktop Edition keeps ACCOUNT/login/subscription online (the live Cloud Run
backend), while DATA ANALYSIS runs locally. This module is the LOCAL half of the
licence gate: it records per-account free-tier usage (5 analyses + 5 charts) and a
locally-cached licence flag, so analysis works completely offline after the user
has signed in (token) — and paid users stay unlimited offline too.

Nothing here is authoritative for money; the real licence lives in the online
Firestore. The SPA syncs the online licence status in via ``sync_licence`` after
sign-in so the offline gate matches it.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

FREE_ANALYSES = 5
FREE_CHARTS = 5

_STORE_DIR = Path(os.environ.get("DEVSTAT_OFFLINE_HOME", str(Path.home() / ".devstat")))
_STORE_FILE = _STORE_DIR / "desktop_licence.json"


def _machine_fingerprint() -> str:
    raw = f"{platform.system()}|{platform.machine()}|{socket.gethostname()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _load() -> Dict[str, Any]:
    try:
        return json.loads(_STORE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: Dict[str, Any]) -> None:
    try:
        _STORE_DIR.mkdir(parents=True, exist_ok=True)
        _STORE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _account_key(uid: str) -> str:
    return f"{uid}:{_machine_fingerprint()}"


def _entry(uid: str) -> Dict[str, Any]:
    return _load().get(_account_key(uid), {})


def _licensed_ok(entry: Dict[str, Any]) -> bool:
    until = entry.get("licensed_until")
    if not until:
        return False
    try:
        return datetime.fromisoformat(str(until).replace("Z", "+00:00")) > datetime.now(timezone.utc)
    except Exception:
        return False


def status(uid: str) -> Dict[str, Any]:
    e = _entry(uid)
    used_a = int(e.get("used_analyses", 0))
    used_c = int(e.get("used_charts", 0))
    licensed = _licensed_ok(e)
    return {
        "uid": uid,
        "licensed": licensed,
        "licensed_until": e.get("licensed_until") if licensed else None,
        "used_analyses": used_a,
        "used_charts": used_c,
        "analyses_left": None if licensed else max(0, FREE_ANALYSES - used_a),
        "charts_left": None if licensed else max(0, FREE_CHARTS - used_c),
        "requires_subscription": not licensed and (used_a >= FREE_ANALYSES or used_c >= FREE_CHARTS),
        "free_analyses": FREE_ANALYSES,
        "free_charts": FREE_CHARTS,
    }


def consume(uid: str, kind: str) -> Dict[str, Any]:
    """Increment a local free-tier counter; block at 5/5 unless licensed."""
    data = _load()
    key = _account_key(uid)
    e = dict(data.get(key, {}))
    if _licensed_ok(e):
        return {"blocked": False, "licensed": True}
    col = "used_analyses" if kind == "analysis" else "used_charts"
    limit = FREE_ANALYSES if kind == "analysis" else FREE_CHARTS
    used = int(e.get(col, 0))
    if used >= limit:
        return {
            "blocked": True,
            "licensed": False,
            "used": used,
            "limit": limit,
            "kind": kind,
            "reason": "You've had a lovely free run of it! \u2728 That's your 5 analyses and 5 charts. Activate a licence to keep going.",
            "details": "Upgrade / subscribe online (same account) to unlock unlimited Desktop Edition analysis.",
        }
    e[col] = used + 1
    data[key] = e
    _save(data)
    return {"blocked": False, "licensed": False, "used": used + 1, "limit": limit}


def sync_licence(uid: str, licensed: bool, licensed_until: Optional[str] = None) -> Dict[str, Any]:
    """Sync the online licence status into the local store (called after sign-in)."""
    data = _load()
    key = _account_key(uid)
    e = dict(data.get(key, {}))
    if licensed and licensed_until:
        e["licensed_until"] = licensed_until
    else:
        e.pop("licensed_until", None)
    e["synced_at"] = int(time.time())
    data[key] = e
    _save(data)
    return status(uid)
