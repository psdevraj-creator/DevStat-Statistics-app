# DevStat Golden Dataset Verification Document

## Purpose

This document defines the **golden dataset** and **reference R scripts** used to
verify that the DevStat backend produces statistically correct output. Each
reference script reads the same known dataset, runs a standard R analysis, and
prints numeric results. DevStat's output should match these values (within
floating-point tolerance) for the same dataset and analysis.

---

## Reference Dataset

**File:** `backend/r/tests/golden_data.csv`

| id | age | sex    | bmi  | treatment | responded | time | event |
|----|-----|--------|------|-----------|-----------|------|-------|
|  1 |  45 | Male   | 28.5 | Control   | 0         | 12.3 | 0     |
|  2 |  52 | Female | 32.1 | Treatment | 1         |  8.7 | 1     |
|  3 |  38 | Female | 24.7 | Control   | 0         | 15.2 | 0     |
|  4 |  61 | Male   | 29.8 | Treatment | 1         |  6.4 | 1     |
|  5 |  44 | Male   | 26.3 | Control   | 1         | 10.5 | 0     |
|  6 |  53 | Female | 31.2 | Treatment | 0         |  9.1 | 1     |
|  7 |  47 | Female | 23.9 | Control   | 0         | 14.8 | 0     |
|  8 |  59 | Male   | 33.5 | Treatment | 1         |  7.2 | 1     |
|  9 |  41 | Female | 27.1 | Control   | 0         | 11.6 | 0     |
| 10 |  56 | Male   | 30.4 | Treatment | 1         |  5.9 | 1     |

**Size:** 10 observations, 8 columns.

**Treatment arms:** `Control` (5 obs) and `Treatment` (5 obs).

**Censoring:** All control subjects are censored (`event = 0`);
all treatment subjects experience the event (`event = 1`).

---

## Test Family 1: Survival Analysis

### R function
`survfit()` + `survdiff()` from the **survival** package.

### Reference script
`backend/r/tests/test_survival.R`

### Expected key values

| Metric                             | Value        |
|------------------------------------|--------------|
| Control median survival            | NA (no events) |
| Treatment median survival          | 7.200        |
| Treatment 95% LCL                  | 6.400        |
| Treatment 95% UCL                  | NA           |
| Log-rank chi-squared               | 9.7007       |
| Log-rank df                        | 1            |
| Log-rank p-value                   | 0.001842     |

### How to compare with DevStat output
1. Run the equivalent analysis in DevStat on the same `golden_data.csv` dataset.
2. Check that median survival times per group match within ±0.05.
3. Check that the log-rank chi-squared matches within ±0.01.
4. Check that the log-rank p-value matches within ±0.0001.

### DevStat output record

| Metric                             | DevStat Value | Match? |
|------------------------------------|---------------|--------|
| Control median survival            |               |        |
| Treatment median survival          |               |        |
| Log-rank chi-squared               |               |        |
| Log-rank p-value                   |               |        |

---

## Test Family 2: Regression

### R functions
- `lm()` for linear regression (age ~ bmi + sex)
- `glm(..., family = binomial)` for logistic regression (responded ~ bmi)

### Reference script
`backend/r/tests/test_regression.R`

### Expected key values

#### Linear model: `age ~ bmi + sex`

| Term        | Estimate   | Std. Error | t value | p-value   |
|-------------|------------|------------|---------|-----------|
| (Intercept) | -0.489316  | 16.200498  | -0.0302 | 0.976748  |
| bmi         |  1.679472  |  0.576570  |  2.9129 | 0.022568  |
| sexMale     |  3.609004  |  3.503821  |  1.0300 | 0.337270  |

| Metric           | Value      |
|------------------|------------|
| R-squared        | 0.643935   |
| Adj. R-squared   | 0.542202   |
| F-statistic      | 6.3297     |
| F (df num, den)  | 2, 7       |
| F p-value        | 0.026937   |

#### Logistic model: `responded ~ bmi`

| Term        | Estimate   | Std. Error | z value | p-value   |
|-------------|------------|------------|---------|-----------|
| (Intercept) | -13.151881 |  8.601160  | -1.5291 | 0.126244  |
| bmi         |   0.456598 |  0.296464  |  1.5401 | 0.123525  |

| Metric            | Value      |
|-------------------|------------|
| Null deviance     | 13.8629    |
| Null df           | 9          |
| Residual deviance | 10.4950    |
| Residual df       | 8          |

### How to compare with DevStat output
1. Run the equivalent linear and logistic regressions in DevStat on `golden_data.csv`.
2. For each coefficient, verify estimates match within ±0.005 and p-values
   match to at least 3 significant figures.
3. Verify R-squared and deviance values match.

### DevStat output record

#### Linear model

| Term        | DevStat Estimate | DevStat p-value | Match? |
|-------------|------------------|-----------------|--------|
| (Intercept) |                  |                 |        |
| bmi         |                  |                 |        |
| sexMale     |                  |                 |        |

| Metric     | DevStat Value | Match? |
|------------|---------------|--------|
| R-squared  |               |        |
| F p-value  |               |        |

#### Logistic model

| Term        | DevStat Estimate | DevStat p-value | Match? |
|-------------|------------------|-----------------|--------|
| (Intercept) |                  |                 |        |
| bmi         |                  |                 |        |

---

## Test Family 3: Correlation

### R function
`cor.test(x, y, method = "pearson")`

### Reference script
`backend/r/tests/test_correlation.R`

### Expected key values

| Metric          | Value            |
|-----------------|------------------|
| Variables       | age and bmi      |
| N               | 10               |
| Pearson's r     |  0.768094        |
| t-statistic     |  3.3927          |
| df              |  8               |
| p-value         |  0.009461        |
| 95% CI lower    |  0.268147        |
| 95% CI upper    |  0.942106        |

### How to compare with DevStat output
1. Run Pearson correlation in DevStat on `golden_data.csv` (age vs bmi).
2. Verify r matches within ±0.005.
3. Verify p-value matches to at least 3 significant figures.
4. Verify CI endpoints match within ±0.01.

### DevStat output record

| Metric          | DevStat Value | Match? |
|-----------------|---------------|--------|
| Pearson's r     |               |        |
| t-statistic     |               |        |
| df              |               |        |
| p-value         |               |        |
| 95% CI lower    |               |        |
| 95% CI upper    |               |        |

---

## Test Family 4: ANOVA

### R function
`aov(age ~ treatment, data = dat)`

### Reference script
`backend/r/tests/test_anova.R`

### Expected key values

| Source      | Df | Sum Sq   | Mean Sq  | F value  | p-value   |
|-------------|----|----------|----------|----------|-----------|
| treatment   |  1 | 435.6000 | 435.6000 | 32.0294  | 0.000476  |
| Residuals   |  8 | 108.8000 |  13.6000 |          |           |

**Group means:**

| Group    | N  | Mean   | SD     |
|----------|----|--------|--------|
| Control  |  5 | 43.00  | 3.536  |
| Treatment|  5 | 56.20  | 3.834  |

### How to compare with DevStat output
1. Run one-way ANOVA in DevStat on `golden_data.csv` (age ~ treatment).
2. Verify F-statistic matches within ±0.05.
3. Verify p-value matches to at least 3 significant figures.
4. Verify group means and SDs match within ±0.05.

### DevStat output record

| Source      | DevStat F | DevStat p-value | Match? |
|-------------|-----------|-----------------|--------|
| treatment   |           |                 |        |

| Group    | DevStat Mean | DevStat SD | Match? |
|----------|--------------|------------|--------|
| Control  |              |            |        |
| Treatment|              |            |        |

---

## Results Summary Table

| Test                     | Key Statistic     | R Reference Value | DevStat Value | Pass? |
|--------------------------|-------------------|-------------------|---------------|-------|
| Survival (log-rank)      | chi-squared       | 9.7007            |               |       |
| Survival (log-rank)      | p-value           | 0.001842          |               |       |
| Survival (median)        | Treatment median  | 7.200             |               |       |
| Linear regression        | bmi coeff         | 1.679472          |               |       |
| Linear regression        | R-squared         | 0.643935          |               |       |
| Logistic regression      | bmi coeff         | 0.456598          |               |       |
| Logistic regression      | Residual deviance | 10.4950           |               |       |
| Pearson correlation      | r                 | 0.768094          |               |       |
| Pearson correlation      | p-value           | 0.009461          |               |       |
| ANOVA                    | F (treatment)     | 32.0294           |               |       |
| ANOVA                    | p-value           | 0.000476          |               |       |

---

## Execution Instructions

To regenerate reference values at any time:

```bash
cd backend/r/tests/
"Rscript" test_survival.R
"Rscript" test_regression.R
"Rscript" test_correlation.R
"Rscript" test_anova.R
```

No additional R packages beyond **survival** (part of base R) are required.
The `survival` package is loaded by `library(survival)` and is included with
all standard R installations.
