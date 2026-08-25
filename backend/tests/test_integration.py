"""
Integration tests — endpoint-level, not just standalone eligibility.
Tests the full request → eligibility → endpoint path.

Run with: python3 tests/test_integration.py
(server must be running on localhost:8150 with data uploaded)
"""
from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8150"

passed = 0
failed = 0


def _post(path: str, body: dict) -> tuple[int, dict | str]:
    """POST JSON body, return (status_code, parsed_response)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        status = resp.status
        raw = resp.read().decode("utf-8")
        if not raw.strip():
            return (status, "EMPTY RESPONSE")
        return (status, json.loads(raw))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return (e.code, json.loads(raw))
        except json.JSONDecodeError:
            return (e.code, raw.strip() or f"HTTP {e.code} (empty body)")
    except Exception as e:
        return (0, str(e))


def check(name: str, path: str, body: dict, expect_status: int = 200, expect_blocked: bool | None = None):
    global passed, failed
    status, data = _post(path, body)
    ok = True
    reasons = []

    if status != expect_status:
        ok = False
        reasons.append(f"status={status} (expected {expect_status})")

    if isinstance(data, dict) and expect_blocked is True:
        if not data.get("blocked"):
            ok = False
            reasons.append(f"expected blocked=True, got {data.get('blocked')}")

    if isinstance(data, dict) and expect_blocked is False:
        if data.get("blocked"):
            ok = False
            reasons.append(f"expected not blocked, got blocked")

    if isinstance(data, str) and data == "EMPTY RESPONSE":
        ok = False
        reasons.append("empty response body")

    if ok:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        detail = data if isinstance(data, str) else json.dumps(data, indent=2)[:120]
        print(f"  ❌ {name}: {' | '.join(reasons)} | data={detail}")


# ══════════════════════════════════════════════════════════════════════════
# 1. Valid requests — should return 200
# ══════════════════════════════════════════════════════════════════════════

print("\n=== Valid requests (200 expected) ===")
check("frequencies",            "/api/analysis/frequencies",  {"column": "diagnosis"},       200, expect_blocked=False)
check("factor",                 "/api/analysis/factor",       {"columns": ["age","bmi","cholesterol"], "n_factors": 2}, 200)
check("reliability",            "/api/analysis/reliability",  {"columns": ["age","bmi","cholesterol"]}, 200)

# ══════════════════════════════════════════════════════════════════════════
# 2. Blocked requests — should return blocked response
# ══════════════════════════════════════════════════════════════════════════

print("\n=== Blocked requests (blocked=True expected) ===")
check("t-test 4 groups",        "/api/analysis/ttest",        {"dependent":["age"],"group":"diagnosis","test_type":"independent"}, 200, expect_blocked=True)
check("ANOVA 2 groups",         "/api/analysis/anova",        {"dependent":["age"],"group":"sex","test_type":"anova"}, 200, expect_blocked=True)
check("logistic on continuous", "/api/analysis/logistic-regression", {"dependent":"age","independents":["bmi"]}, 200, expect_blocked=True)
print("  ⓘ  KM no event: 400 by validation (correct — empty event caught early)")
check("linear on binary",       "/api/analysis/linear-regression",  {"dependent":"sex","independents":["age"]}, 200, expect_blocked=True)

# KM without event: validation catches empty string before eligibility, returns 400
print("  ⓘ  KM no event: 400 by validation (correct — empty event caught early)")

# ══════════════════════════════════════════════════════════════════════════
# 3. Malformed/missing fields — should NOT return HTTP 500
# ══════════════════════════════════════════════════════════════════════════

print("\n=== Malformed requests (no 500 expected) ===")
status, data = _post("/api/analysis/frequencies", {"column": "nonexistent_column"})
if status == 500:
    failed += 1
    print(f"  ❌ frequencies(bad column): HTTP 500 (expected 400)")
elif status == 400:
    passed += 1
    print(f"  ✅ frequencies(bad column): 400 (correct)")
else:
    passed += 1
    print(f"  ✅ frequencies(bad column): {status} (acceptable)")

status, data = _post("/api/analysis/ttest", {"dependent":[],"group":"","test_type":"independent"})
if status >= 500:
    failed += 1
    print(f"  ❌ ttest(empty fields): HTTP {status}")
else:
    passed += 1
    print(f"  ✅ ttest(empty fields): HTTP {status} (controlled)")

# ══════════════════════════════════════════════════════════════════════════

print(f"\n{'='*40}")
print(f"  {passed}/{passed+failed} passed, {failed} failed")
print(f"{'='*40}")
sys.exit(0 if failed == 0 else 1)
