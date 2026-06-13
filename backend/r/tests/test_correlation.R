# test_correlation.R -- Golden-dataset correlation reference script
# Pearson correlation: age vs bmi

dat <- read.csv("golden_data.csv")

cat("========================================\n")
cat("TEST: Pearson Correlation (cor.test)\n")
cat("========================================\n\n")

ct <- cor.test(dat$age, dat$bmi, method = "pearson")

cat(sprintf("  Method          = %s\n", ct$method))
cat(sprintf("  Variables       = age and bmi\n"))
cat(sprintf("  N               = %d\n", nrow(dat)))
cat(sprintf("  Correlation (r) = %.6f\n", ct$estimate))
cat(sprintf("  t-statistic     = %.4f\n", ct$statistic))
cat(sprintf("  df              = %d\n", ct$parameter))
cat(sprintf("  p-value         = %.6f\n", ct$p.value))
cat(sprintf("  95%% CI          = [%.6f, %.6f]\n",
            ct$conf.int[1], ct$conf.int[2]))

cat("\n--- Quick interpretation ---\n")
r <- ct$estimate
cat(sprintf("  r = %.3f indicates ", r))
if (abs(r) < 0.1) { cat("negligible")
} else if (abs(r) < 0.3) { cat("weak")
} else if (abs(r) < 0.5) { cat("moderate")
} else if (abs(r) < 0.7) { cat("strong")
} else { cat("very strong") }
if (r > 0) { cat(" positive") } else { cat(" negative") }
cat(" correlation.\n")

cat("\n========================================\n")
cat("TEST COMPLETE: correlation\n")
cat("========================================\n")
