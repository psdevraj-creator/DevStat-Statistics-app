# test_anova.R -- Golden-dataset ANOVA reference script
# One-way ANOVA: age ~ treatment

dat <- read.csv("golden_data.csv")

cat("========================================\n")
cat("TEST: One-way ANOVA (aov)\n")
cat("========================================\n\n")

aov_fit <- aov(age ~ treatment, data = dat)

cat("--- Model summary ---\n")
s <- summary(aov_fit)
print(s)

# Extract values from the summary for clean reporting
s_table <- s[[1]]
treatment_row <- s_table[1, ]
residuals_row <- s_table[2, ]

cat("\n--- Extracted ANOVA table ---\n")
cat(sprintf("%-15s %-10s %-12s %-12s %-12s %-12s\n",
            "Source", "Df", "Sum Sq", "Mean Sq", "F value", "p-value"))
cat(sprintf("%-15s %-10d %-12.4f %-12.4f %-12.4f %-12.6f\n",
            "treatment",
            treatment_row$Df,
            treatment_row$`Sum Sq`,
            treatment_row$`Mean Sq`,
            treatment_row$`F value`,
            treatment_row$`Pr(>F)`))
cat(sprintf("%-15s %-10d %-12.4f %-12.4f\n",
            "Residuals",
            residuals_row$Df,
            residuals_row$`Sum Sq`,
            residuals_row$`Mean Sq`))

cat("\n--- Group means ---\n")
means <- tapply(dat$age, dat$treatment, mean)
sds   <- tapply(dat$age, dat$treatment, sd)
ns    <- tapply(dat$age, dat$treatment, length)
cat(sprintf("%-15s %-8s %-10s %-8s\n", "Group", "N", "Mean", "SD"))
for (grp in names(means)) {
  cat(sprintf("%-15s %-8d %-10.2f %-8.3f\n", grp, ns[grp], means[grp], sds[grp]))
}

cat("\n========================================\n")
cat("TEST COMPLETE: anova\n")
cat("========================================\n")
