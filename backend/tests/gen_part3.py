content = r'''

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
'''

with open('test_all_endpoints.py', 'a') as f:
    f.write(content)
print("Part 3 done (tests 0-4)")
