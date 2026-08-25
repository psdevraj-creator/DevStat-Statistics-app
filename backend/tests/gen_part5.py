content = r'''

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
'''

with open('test_all_endpoints.py', 'a') as f:
    f.write(content)
print("Part 5 done (tests 8-10a)")
