content = r'''

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
'''

with open('test_all_endpoints.py', 'a') as f:
    f.write(content)
print("Part 6 done (tests 10b-10e + summary)")
