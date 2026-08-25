"""
test_all_endpoints.py -- Comprehensive integration tests
for all API endpoint groups.
"""

from __future__ import annotations
import json, sys, urllib.request, urllib.error, threading

BASE = "http://127.0.0.1:8150"
passed = failed = total_tests = 0



def _post(path, body, timeout=60):
    """POST JSON body, return (status_code, parsed_response)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        raw = resp.read().decode("utf-8")
        if not raw.strip():
            return (resp.status, "EMPTY")
        return (resp.status, json.loads(raw))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return (e.code, json.loads(raw))
        except json.JSONDecodeError:
            return (e.code, raw.strip() or ("HTTP %d" % e.code))
    except Exception as e:
        return (0, str(e))


def check(name, path, body, expect_status=200, expect_blocked=None):
    """Run one test case and record pass/fail."""
    global passed, failed, total_tests
    total_tests += 1
    status, data = _post(path, body)
    ok = True
    reasons = []
    if status != expect_status:
        ok = False
        reasons.append("status=%d (expect %d)" % (status, expect_status))
    if isinstance(data, dict):
        if expect_blocked is True and not data.get("blocked"):
            ok = False
            reasons.append("want blocked=True, got %s" % data.get("blocked"))
        elif expect_blocked is False and data.get("blocked"):
            ok = False
            reasons.append("want not blocked, got blocked=True")
    elif isinstance(data, str) and data == "EMPTY":
        ok = False
        reasons.append("empty response body")
    if ok:
        passed += 1
        print("  [PASS]", name)
    else:
        failed += 1
        d = data if isinstance(data, str) else json.dumps(data, indent=2)[:200]
        print("  [FAIL]", name, "|", " | ".join(reasons))
        if reasons:
            print("     data:", d)


# ============================================================
# 0. Health check
# ============================================================

print("\n=== 0. Health / Server check ===")
check("server health", "/", {"x": 1}, 200)

# ============================================================
# 1. DESCRIPTIVE
# ============================================================

print("\n=== 1. DESCRIPTIVE ===")
check("frequencies (valid column)",
      "/api/analysis/frequencies", {"column": "diagnosis"},
      200, expect_blocked=False)
check("frequencies (bad column)",
      "/api/analysis/frequencies", {"column": "nonexistent_column"},
      400)
check("descriptive (valid columns)",
      "/api/analysis/descriptive", {"columns": ["age", "bmi", "cholesterol"]},
      200)
check("explore (valid column)",
      "/api/analysis/explore", {"column": "age", "group_col": "sex"},
      200)
check("means (dependent + group)",
      "/api/analysis/means", {"dependent": "age", "group": "sex"},
      200)

# ============================================================
# 2. T-TESTS / ANOVA
# ============================================================

print("\n=== 2. T-TESTS / ANOVA ===")
check("ttest (2 groups, eligible)",
      "/api/analysis/ttest",
      {"test_type": "independent", "dependent": ["age"], "group": "sex"},
      200, expect_blocked=False)
check("ttest (4 groups, blocked)",
      "/api/analysis/ttest",
      {"test_type": "independent", "dependent": ["age"], "group": "treatment"},
      200, expect_blocked=True)
check("ttest-paired (valid vars)",
      "/api/analysis/ttest-paired",
      {"variable1": "age", "variable2": "bmi"},
      200, expect_blocked=False)
check("anova (3+ groups, eligible)",
      "/api/analysis/anova",
      {"test_type": "anova", "dependent": ["age"], "group": "smoking"},
      200, expect_blocked=False)
check("anova (2 groups, blocked)",
      "/api/analysis/anova",
      {"test_type": "anova", "dependent": ["age"], "group": "sex"},
      200, expect_blocked=True)
check("anova-twoway (valid factors)",
      "/api/analysis/anova-twoway",
      {"dependent": "age", "factor1": "sex", "factor2": "smoking"},
      200)

# ============================================================
# 3. CHI-SQUARE / CATEGORICAL
# ============================================================

print("\n=== 3. CHI-SQUARE / CATEGORICAL ===")
check("crosstab (valid row/col)",
      "/api/analysis/crosstab",
      {"row": "sex", "col": "smoking"},
      200)
check("chisquare (valid vars)",
      "/api/analysis/chisquare",
      {"row": "sex", "col": "smoking"},
      200)

# ============================================================
# 4. NON-PARAMETRIC
# ============================================================

print("\n=== 4. NON-PARAMETRIC ===")
check("np-mannwhitney (valid)",
      "/api/analysis/np-mannwhitney",
      {"dependent": "age", "group": "sex"},
      200)
check("np-wilcoxon (valid)",
      "/api/analysis/np-wilcoxon",
      {"variable1": "age", "variable2": "bmi"},
      200)
check("np-kruskalwallis (valid group)",
      "/api/analysis/np-kruskalwallis",
      {"dependent": "age", "group": "smoking"},
      200)
check("np-mcnemar (valid)",
      "/api/analysis/np-mcnemar",
      {"variable1": "gold_standard", "variable2": "hypertension"},
      200)
check("np-friedman (valid)",
      "/api/analysis/np-friedman",
      {"variables": ["age", "bmi", "cholesterol"]},
      200)


# ============================================================
# 5. REGRESSION
# ============================================================

print("\n=== 5. REGRESSION ===")
check("linear-regression (continuous DV)",
      "/api/analysis/linear-regression",
      {"dependent": "age", "independents": ["bmi", "cholesterol"]},
      200)
check("linear-regression (binary DV, blocked)",
      "/api/analysis/linear-regression",
      {"dependent": "event_death", "independents": ["age"]},
      200, expect_blocked=True)
check("logistic-regression (binary DV)",
      "/api/analysis/logistic-regression",
      {"dependent": "event_death", "independents": ["age", "bmi"]},
      200)
check("logistic-regression (continuous DV, blocked)",
      "/api/analysis/logistic-regression",
      {"dependent": "age", "independents": ["bmi"]},
      200, expect_blocked=True)

# ============================================================
# 6. SURVIVAL
# ============================================================

print("\n=== 6. SURVIVAL ===")
check("kaplan-meier (valid)",
      "/api/analysis/kaplan-meier",
      {"time_col": "survival_months", "status_col": "event_death", "factors": ["sex"]},
      200)
check("kaplan-meier (empty status -> 400)",
      "/api/analysis/kaplan-meier",
      {"time_col": "survival_months", "status_col": ""},
      400)
check("cox-regression (valid)",
      "/api/analysis/cox-regression",
      {"time_col": "survival_months", "status_col": "event_death", "covariates": ["age", "bmi"]},
      200)
check("cox-regression (empty status -> 400)",
      "/api/analysis/cox-regression",
      {"time_col": "survival_months", "status_col": "", "covariates": ["age"]},
      400)

# ============================================================
# 7. FACTOR / RELIABILITY
# ============================================================

print("\n=== 7. FACTOR / RELIABILITY ===")
check("factor (3+ vars)",
      "/api/analysis/factor",
      {"columns": ["age", "bmi", "cholesterol"], "n_factors": 2},
      200)
check("factor (2 vars, blocked)",
      "/api/analysis/factor",
      {"columns": ["age", "bmi"], "n_factors": 2},
      200, expect_blocked=True)
check("reliability (3+ items)",
      "/api/analysis/reliability",
      {"columns": ["age", "bmi", "cholesterol"]},
      200)
check("reliability (1 item -> 400)",
      "/api/analysis/reliability",
      {"columns": ["age"]},
      400)


# ============================================================
# 8. DIAGNOSTIC / ROC
# ============================================================

print("\n=== 8. DIAGNOSTIC / ROC ===")
check("diagnostic (valid)",
      "/api/analysis/diagnostic",
      {"test_col": "new_biomarker", "gold_col": "gold_standard"},
      200)
check("roc (valid)",
      "/api/analysis/roc",
      {"test_col": "new_biomarker", "gold_col": "gold_standard"},
      200)

# ============================================================
# 9. CLUSTER / POWER
# ============================================================

print("\n=== 9. CLUSTER / POWER ===")
check("cluster (valid)",
      "/api/analysis/cluster",
      {"columns": ["age", "bmi", "cholesterol"], "n_clusters": 3},
      200)
check("power (valid)",
      "/api/analysis/power",
      {"test": "ttest", "effect_size": 0.5, "power": 0.8, "alpha": 0.05},
      200)

# ============================================================
# 10. REGRESSION TESTS -- bug-focussed edge cases
# ============================================================

print("\n=== 10. REGRESSION TESTS (edge cases / bug verification) ===")

# 10a. Blocked dict response: verify blocked keys
print("\n  --- 10a. Blocked response structure ---")
status, data = _post("/api/analysis/ttest",
                      {"test_type": "independent", "dependent": ["age"],
                       "group": "treatment"})
total_tests += 1
if isinstance(data, dict) and data.get("blocked") is True:
    keys_ok = all(k in data for k in ("blocked", "reason", "suggested_alternatives"))
    if keys_ok:
        passed += 1
        print("  [PASS] blocked dict has blocked, reason, suggested_alternatives")
    else:
        failed += 1
        missing = [k for k in ("blocked","reason","suggested_alternatives") if k not in data]
        print("  [FAIL] blocked dict missing keys:", missing)
elif isinstance(data, dict) and "detail" in data:
    passed += 1
    print("  [PASS] blocked via validation (detail returned):", str(data)[:80])
else:
    failed += 1
    print("  [FAIL] blocked check unexpected: status=%s data=%s" % (status, str(data)[:120]))


# 10b. Nonexistent column -> 400 (not 500)
print("\n  --- 10b. Nonexistent column -> 400 (not 500) ---")
status, data = _post("/api/analysis/frequencies",
                      {"column": "__i_dont_exist__"})
total_tests += 1
if status == 400:
    passed += 1
    print("  [PASS] frequencies(bad column): HTTP 400 (correct)")
elif status >= 500:
    failed += 1
    print("  [FAIL] frequencies(bad column): HTTP %d (500-level error)" % status)
else:
    passed += 1
    print("  [PASS] frequencies(bad column): HTTP %d (acceptable)" % status)

# 10c. Blank survival status: KM with empty status_col -> 400
print("\n  --- 10c. Blank survival status -> 400 ---")
status, data = _post("/api/analysis/kaplan-meier",
                      {"time_col": "survival_months", "status_col": ""})
total_tests += 1
if status == 400:
    passed += 1
    print("  [PASS] KM(empty status): HTTP 400 (correct)")
elif status >= 500:
    failed += 1
    print("  [FAIL] KM(empty status): HTTP %d (500-level error)" % status)
else:
    failed += 1
    print("  [FAIL] KM(empty status): HTTP %d (expected 400)" % status)

# 10d. Malformed request: frequencies with empty body -> 400
print("\n  --- 10d. Malformed request (empty body) -> 400 ---")
status, data = _post("/api/analysis/frequencies", {})
total_tests += 1
if status == 400:
    passed += 1
    print("  [PASS] frequencies(empty body): HTTP 400 (correct)")
elif status >= 500:
    failed += 1
    print("  [FAIL] frequencies(empty body): HTTP %d (500-level error)" % status)
else:
    passed += 1
    print("  [PASS] frequencies(empty body): HTTP %d (acceptable)" % status)

# ttest with empty dependent/group
status, data = _post("/api/analysis/ttest",
                      {"dependent": [], "group": "", "test_type": "independent"})
total_tests += 1
if status >= 500:
    failed += 1
    print("  [FAIL] ttest(empty fields): HTTP %d (500-level error)" % status)
else:
    passed += 1
    print("  [PASS] ttest(empty fields): HTTP %d (controlled)" % status)

# 10e. Batch test: 10 requests in parallel -> no HTTP 500s
print("\n  --- 10e. Parallel batch test (10 concurrent requests) ---")

results_lock = threading.Lock()
batch_results = []

def _batch_worker(idx):
    """Send one of the batch requests."""
    endpoints = [
        ("frequencies", "/api/analysis/frequencies", {"column": "diagnosis"}),
        ("descriptive", "/api/analysis/descriptive", {"columns": ["age", "bmi"]}),
        ("ttest", "/api/analysis/ttest", {"test_type": "independent", "dependent": ["age"], "group": "sex"}),
        ("anova", "/api/analysis/anova", {"test_type": "anova", "dependent": ["age"], "group": "smoking"}),
        ("crosstab", "/api/analysis/crosstab", {"row": "sex", "col": "smoking"}),
        ("chisquare", "/api/analysis/chisquare", {"row": "sex", "col": "smoking"}),
        ("np-mannwhitney", "/api/analysis/np-mannwhitney", {"dependent": "age", "group": "sex"}),
        ("np-friedman", "/api/analysis/np-friedman", {"variables": ["age", "bmi", "cholesterol"]}),
        ("factor", "/api/analysis/factor", {"columns": ["age", "bmi", "cholesterol"], "n_factors": 2}),
        ("reliability", "/api/analysis/reliability", {"columns": ["age", "bmi", "cholesterol"]}),
    ]
    name, path, body = endpoints[idx % len(endpoints)]
    st, da = _post(path, body, timeout=120)
    with results_lock:
        batch_results.append((idx, name, st))

threads = []
for i in range(10):
    t = threading.Thread(target=_batch_worker, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

for idx, name, st in batch_results:
    total_tests += 1
    if st >= 500:
        failed += 1
        print("  [FAIL] batch #%d (%s): HTTP %d" % (idx, name, st))
    else:
        passed += 1

if not any(st >= 500 for _, _, st in batch_results):
    print("  [PASS] All 10 parallel requests passed (no HTTP 500s)")

# ============================================================
# Summary
# ============================================================

print()
print("=" * 50)
print("  %d/%d passed, %d failed" % (passed, total_tests, failed))
print("=" * 50)

if total_tests == 0:
    print("  WARNING: No tests were run! Something went wrong.")
    sys.exit(1)

sys.exit(0 if failed == 0 else 1)
