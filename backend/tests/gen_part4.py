content = r'''

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
'''

with open('test_all_endpoints.py', 'a') as f:
    f.write(content)
print("Part 4 done (tests 5-7)")
