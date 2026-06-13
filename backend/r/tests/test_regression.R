# test_regression.R -- Golden-dataset regression reference script
# Linear model: age ~ bmi + sex
# Logistic model: responded ~ bmi

dat <- read.csv("golden_data.csv")

cat("========================================\n")
cat("TEST: Linear Regression (lm)\n")
cat("========================================\n\n")

lm_fit <- lm(age ~ bmi + sex, data = dat)

cat("--- Call ---\n")
print(lm_fit$call)
cat("\n")

coef_lm <- coef(summary(lm_fit))
cat("--- Coefficients ---\n")
cat(sprintf("%-15s %-12s %-12s %-12s %-12s\n",
            "Term", "Estimate", "Std.Error", "t.value", "p.value"))
for (i in seq_len(nrow(coef_lm))) {
  cat(sprintf("%-15s %-12.6f %-12.6f %-12.4f %-12.6f\n",
              rownames(coef_lm)[i],
              coef_lm[i, "Estimate"],
              coef_lm[i, "Std. Error"],
              coef_lm[i, "t value"],
              coef_lm[i, "Pr(>|t|)"]))
}

cat("\n--- Model summary ---\n")
rsq <- summary(lm_fit)$r.squared
adj_rsq <- summary(lm_fit)$adj.r.squared
fstat <- summary(lm_fit)$fstatistic
fpval <- pf(fstat[1], fstat[2], fstat[3], lower.tail = FALSE)
cat(sprintf("  R-squared       = %.6f\n", rsq))
cat(sprintf("  Adj. R-squared  = %.6f\n", adj_rsq))
cat(sprintf("  F-statistic     = %.4f on %d and %d DF\n", fstat[1], fstat[2], fstat[3]))
cat(sprintf("  F p-value       = %.6f\n", fpval))

cat("\n========================================\n")
cat("TEST: Logistic Regression (glm, binomial)\n")
cat("========================================\n\n")

glm_fit <- glm(responded ~ bmi, data = dat, family = binomial)

cat("--- Call ---\n")
print(glm_fit$call)
cat("\n")

coef_glm <- coef(summary(glm_fit))
cat("--- Coefficients ---\n")
cat(sprintf("%-15s %-12s %-12s %-12s %-12s\n",
            "Term", "Estimate", "Std.Error", "z.value", "p.value"))
for (i in seq_len(nrow(coef_glm))) {
  cat(sprintf("%-15s %-12.6f %-12.6f %-12.4f %-12.6f\n",
              rownames(coef_glm)[i],
              coef_glm[i, "Estimate"],
              coef_glm[i, "Std. Error"],
              coef_glm[i, "z value"],
              coef_glm[i, "Pr(>|z|)"]))
}

cat("\n--- Deviance ---\n")
cat(sprintf("  Null deviance     = %.4f on %d df\n",
            glm_fit$null.deviance, glm_fit$df.null))
cat(sprintf("  Residual deviance = %.4f on %d df\n",
            glm_fit$deviance, glm_fit$df.residual))

cat("\n========================================\n")
cat("TEST COMPLETE: regression\n")
cat("========================================\n")
