# test_survival.R -- Golden-dataset survival analysis reference script
# Runs Cox-type Kaplan-Meier + log-rank test on golden_data.csv

library(survival)

dat <- read.csv("golden_data.csv")

cat("========================================\n")
cat("TEST: Survival Analysis (Kaplan-Meier + Log-rank)\n")
cat("========================================\n\n")

# Kaplan-Meier estimate by treatment group
fit <- survfit(Surv(time, event) ~ treatment, data = dat)

cat("--- Median survival by group ---\n")
print(fit)
cat("\n")

# Log-rank test
sdiff <- survdiff(Surv(time, event) ~ treatment, data = dat)

cat("--- Log-rank test ---\n")
cat(sprintf("  Chi-squared = %.4f\n", sdiff$chisq))
# p-value from chi-squared distribution with 1 df
pval <- pchisq(sdiff$chisq, df = 1, lower.tail = FALSE)
cat(sprintf("  df          = 1\n"))
cat(sprintf("  p-value     = %.6f\n", pval))
cat("\n")

# Extract median survival per group using summary() approach
sfit <- summary(fit)
cat("--- Median survival (extracted) ---\n")
cat(sprintf("%-20s %-10s %-10s %-10s\n", "Group", "Median", "0.95LCL", "0.95UCL"))
for (i in seq_along(fit$strata)) {
  nm <- names(fit$strata)[i]
  med <- sfit$table[i, "median"]
  lcl <- sfit$table[i, "0.95LCL"]
  ucl <- sfit$table[i, "0.95UCL"]
  med_str <- ifelse(is.na(med), "NA", sprintf("%.3f", med))
  lcl_str <- ifelse(is.na(lcl), "NA", sprintf("%.3f", lcl))
  ucl_str <- ifelse(is.na(ucl), "NA", sprintf("%.3f", ucl))
  cat(sprintf("%-20s %-10s %-10s %-10s\n", nm, med_str, lcl_str, ucl_str))
}

cat("\n========================================\n")
cat("TEST COMPLETE: survival\n")
cat("========================================\n")
