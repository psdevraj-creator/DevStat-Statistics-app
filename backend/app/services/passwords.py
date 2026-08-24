"""Password hashing and verification for DevStat auth.

Uses PBKDF2-HMAC-SHA256 (stdlib only — no external deps). Format:
``salt_hex$digest_hex``. A random salt is generated per password; timing-safe
comparison is used on verify.
"""
import hashlib
import hmac
import secrets

_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS
    )
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except (ValueError, AttributeError):
        return False
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS
    )
    return hmac.compare_digest(dk.hex(), digest)
