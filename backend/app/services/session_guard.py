"""DevStat session guard — industry-standard account-sharing protection.

Prevents the same login from being used on unlimited devices: each account can
be signed in on at most ``DEVSTAT_MAX_DEVICES`` (default 3) devices at once.
When a new device signs in and the cap is reached, the oldest (least recently
used) device is signed out (LRU eviction). Every login mints a signed session
token bound to (uid, device_id, nonce); protected endpoints re-validate it
against the user's Firestore device registry, so a signed-out or evicted
session is instantly rejected (401).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Optional, Tuple

from .firebase_store import get_user, update_user

MAX_DEVICES = int(os.environ.get("DEVSTAT_MAX_DEVICES", "3"))


def _secret() -> str:
    return os.environ.get("DEVSTAT_AUTH_SECRET", "devstat-auth-secret-fallback")


def _hmac(uid: str, device_id: str, nonce: str) -> str:
    return hmac.new(
        _secret().encode("utf-8"),
        f"{uid}|{device_id}|{nonce}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _make_token(uid: str, device_id: str, nonce: str) -> str:
    return f"{uid}.{device_id}.{nonce}.{_hmac(uid, device_id, nonce)}"


def register_device(uid: str, device_id: str) -> Tuple[bool, str]:
    """Register a device sign-in. Returns (ok, session_token).

    Evicts the least-recently-used device when the account is at its cap.
    """
    device_id = (device_id or "").strip()[:64]
    if not device_id:
        return False, ""
    u = get_user(uid) or {}
    devices = dict(u.get("devices") or {})
    now = int(time.time())

    if device_id in devices:
        nonce = devices[device_id].get("nonce") or secrets.token_hex(16)
    else:
        nonce = secrets.token_hex(16)

    if device_id not in devices and len(devices) >= MAX_DEVICES:
        # Kick out the least-recently-used device (LRU).
        oldest = min(devices, key=lambda d: int(devices[d].get("ts", 0)))
        del devices[oldest]

    devices[device_id] = {"nonce": nonce, "ts": now}
    update_user(uid, {"devices": devices})
    return True, _make_token(uid, device_id, nonce)


def validate_token(uid: str, token: str) -> Optional[str]:
    """Return the device_id for a valid token, or None (revoked/invalid)."""
    parts = (token or "").split(".")
    if len(parts) != 4:
        return None
    t_uid, device_id, nonce, sig = parts
    if t_uid != uid:
        return None
    if not hmac.compare_digest(sig, _hmac(t_uid, device_id, nonce)):
        return None
    u = get_user(uid) or {}
    dev = (u.get("devices") or {}).get(device_id)
    if not dev or dev.get("nonce") != nonce:
        return None  # evicted / superseded
    # Touch last-seen.
    dev["ts"] = int(time.time())
    update_user(uid, {"devices": {**u.get("devices", {}), device_id: dev}})
    return device_id


def max_devices() -> int:
    return MAX_DEVICES


def peek_uid(token: str) -> Optional[str]:
    """Return the uid from a token if its signature is valid (no Firestore
    round-trip / no last-seen write). Used by the session middleware to key a
    user's data by uid for isolation."""
    parts = (token or "").split(".")
    if len(parts) != 4:
        return None
    t_uid, device_id, nonce, sig = parts
    if hmac.compare_digest(sig, _hmac(t_uid, device_id, nonce)):
        return t_uid
    return None
