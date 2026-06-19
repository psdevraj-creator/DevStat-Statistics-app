# DevStat — User Guide & Statistics Manual

*A comprehensive guide to using DevStat and understanding the statistical concepts behind it.*

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Who This App Is For](#2-who-this-app-is-for)
3. [Getting Started](#3-getting-started)
4. [Uploading and Preparing Data](#4-uploading-and-preparing-data)
5. [Understanding Variables and Study Questions](#5-understanding-variables-and-study-questions)
6. [The Analysis Pages](#6-the-analysis-pages)
   - [Data View](#61-data-view)
   - [Descriptive Statistics](#62-descriptive-statistics)
   - [Compare Groups](#63-compare-groups)
   - [Correlation](#64-correlation)
   - [Regression](#65-regression)
   - [Survival Analysis](#66-survival-analysis)
   - [Diagnostic Tests](#67-diagnostic-tests)
   - [Factor Analysis & Reliability](#68-factor-analysis--reliability)
   - [Graphs & Charts](#69-graphs--charts)
7. [Statistical Test Guide](#7-statistical-test-guide)
8. [Interpreting Outputs](#8-interpreting-outputs)
9. [Charts and Visualisations](#9-charts-and-visualisations)
10. [Common Pitfalls](#10-common-pitfalls)
11. [Worked Examples](#11-worked-examples)
12. [Glossary](#12-glossary)
13. [FAQ](#13-faq)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Introduction

DevStat is a desktop medical statistics application that lets you analyse data through a point-and-click interface. It handles the full workflow: importing data, exploring variables, running statistical tests, creating publication-quality charts, and reviewing results.

The app is powered by a Python backend (FastAPI) and an interactive frontend (React with Plotly.js charts). Everything runs locally on your machine — no data is ever sent to external servers.

---

## 2. Who This App Is For

DevStat is designed for:

- **Medical researchers** analysing clinical trial or observational study data
- **Healthcare professionals** evaluating diagnostic tests or patient outcomes
- **Students** learning medical statistics
- **Data analysts** working with health or biomedical datasets

**What you need to know:** Basic familiarity with spreadsheets and your data. The app will guide you through choosing appropriate analyses, but understanding the concepts in this manual will help you make better decisions.

---

## 3. Getting Started

### 3.1 Launching the App

1. Download the latest release zip from the GitHub Releases page
2. Unzip to any folder
3. Double-click `DevStat.exe`
4. Click **Start** — the status changes to "Ready"
5. Click **Open App** — your default browser opens to `http://localhost:8150`

### 3.2 First-Time Workflow

1. **Upload your data** (CSV, Excel, or SPSS file)
2. **Check your variables** in the Variable View
3. **Run a descriptive analysis** to understand your data
4. **Use the Wizard** or pick an analysis from the menu
5. **Review results** in the Output panel
6. **Create charts** on the Graphs page

---

## 4. Uploading and Preparing Data

### Supported Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| CSV | `.csv` | UTF-8 recommended |
| Excel | `.xlsx`, `.xls` | First sheet only |
| SPSS | `.sav` | Variable labels preserved |

### Data Preparation Tips

- **One row per observation** (patient, subject, sample)
- **One column per variable** (age, sex, diagnosis, blood pressure)
- **Missing values** should be blank or `NA` — the app handles them automatically
- **Column names** should be short and meaningful (e.g., `age`, `systolic_bp`, `treatment_arm`)

### Transform Tab

The Transform tab lets you:

- **Compute** new variables using formulas: `bmi = weight / (height/100)^2`
- **Recode** values: combine categories, convert text to numbers
- **Filter** rows based on conditions

---

## 5. Understanding Variables and Study Questions

Before choosing an analysis, identify your variables:

| Variable Type | Description | Examples |
|---------------|-------------|----------|
| **Continuous** | Numeric, can take any value | Age, blood pressure, cholesterol |
| **Binary** | Exactly 2 categories | Yes/No, Male/Female, Alive/Dead |
| **Categorical (Nominal)** | 3+ unordered categories | Blood type, diagnosis, treatment arm |
| **Ordinal** | Ordered categories | Stage I/II/III, Mild/Moderate/Severe |
| **Time-to-event** | Time until an event occurs | Survival months, time to recurrence |

**Key question types:**

| You want to... | Use... |
|----------------|--------|
| Summarise a variable | Descriptive statistics (mean, median, frequency) |
| Compare two groups | t-test or Mann-Whitney U |
| Compare three+ groups | ANOVA or Kruskal-Wallis |
| Measure association | Correlation or chi-square |
| Predict an outcome | Linear or logistic regression |
| Analyse time to event | Kaplan-Meier or Cox regression |
| Evaluate a test | Diagnostic test or ROC curve |

---

## 6. The Analysis Pages

### 6.1 Data View

The starting page. Upload your dataset, browse rows and columns, check variable types, and apply transformations.

**Features:**
- Table view with sortable columns
- Variable View showing data types, unique values, missing counts
- Upload multiple datasets and switch between them
- Download data as Excel or SPSS format

### 6.2 Descriptive Statistics

Summarise your data numerically and visually.

**Descriptives tab:** Mean, median, standard deviation, min, max, quartiles, skewness, kurtosis for numeric variables. Use Group By to split statistics by a categorical variable.

**Frequencies tab:** Counts and percentages for categorical variables. Shows how many cases fall into each category.

**Crosstabs tab:** Cross-tabulation between two categorical variables with chi-square test and Cramer's V. The contingency table shows observed counts, expected counts, and percentages. Fisher's exact test is provided for 2×2 tables.

**Explore tab:** Normality diagnostics — Shapiro-Wilk test, skewness/kurtosis z-scores, and outlier detection via Tukey's fences. Use this before parametric tests to check assumptions.

### 6.3 Compare Groups

Statistical tests for comparing groups.

| Test | When to Use | Assumptions |
|------|-------------|-------------|
| Independent t-test | 2 independent groups, continuous outcome | Normality, equal variances |
| Paired t-test | Same subjects measured twice | Normality of differences |
| Mann-Whitney U | 2 independent groups, non-normal data | Independent groups |
| Wilcoxon Signed-Rank | Paired data, non-normal | Paired observations |
| One-way ANOVA | 3+ independent groups | Normality, equal variances |
| Kruskal-Wallis | 3+ groups, non-normal | Independent groups |
| Chi-square | Two categorical variables | Expected count ≥ 5 per cell |

**How to read results:**
- **p-value** < 0.05: statistically significant (unlikely to have occurred by chance)
- **Effect size** (Cohen's d, η², ε²): how large the difference is
- **Confidence interval**: range that likely contains the true difference

### 6.4 Correlation

Measure the relationship between numeric variables.

**Methods:**
- **Pearson:** linear relationships (assumes normality)
- **Spearman:** monotonic relationships (no normality assumption)
- **Kendall:** non-parametric, best for small samples with ties

**Output:** Correlation matrix showing r-values and p-values. Significant correlations are starred. The heatmap view colours correlations blue (positive) or red (negative).

**Common interpretation:**
- r = 0: no linear relationship
- r = ±0.1: small effect
- r = ±0.3: medium effect
- r = ±0.5: large effect

**Partial correlation** measures the relationship between two variables while controlling for others.

### 6.5 Regression

Model the relationship between predictors and an outcome.

**Linear regression:** Continuous outcome (e.g., blood pressure, cholesterol level).

Key outputs:
- **R-squared:** proportion of variance explained
- **Coefficients:** the change in outcome per unit change in each predictor
- **p-value:** whether each predictor contributes significantly
- **ANOVA table:** overall model significance

**Logistic regression:** Binary outcome (e.g., yes/no, alive/dead).

Key outputs:
- **Odds ratio:** the change in odds of the outcome per unit change in a predictor
- **95% CI:** range for the odds ratio (crossing 1.0 = not significant)
- **Classification table:** how well the model predicts outcomes
- **Pseudo R-squared:** approximate measure of model fit

**Variable selection methods:**
- **Enter:** all variables at once
- **Stepwise:** adds/removes based on statistical criteria
- **Forward/Backward:** directional selection

### 6.6 Survival Analysis

Analyse time-to-event data (e.g., time to death, time to recurrence).

**Kaplan-Meier:** Estimates the survival function over time. The curve shows the proportion of subjects who have not yet had the event at each time point.

- Steps in the curve = event times
- Tick marks = censored observations
- Log-rank test compares survival between groups
- Median survival = time when 50% of subjects have had the event

**Cox regression:** Models the effect of predictors on the hazard (instantaneous risk).

- **Hazard ratio (HR):** > 1 = increased risk, < 1 = protective
- **Proportional hazards assumption:** the effect of predictors should be constant over time
- **Schoenfeld residuals:** check the proportional hazards assumption

### 6.7 Diagnostic Tests

Evaluate the accuracy of a diagnostic test against a gold standard.

**2×2 Table:**
- **Sensitivity:** proportion of true positives correctly identified
- **Specificity:** proportion of true negatives correctly identified
- **PPV:** probability a positive test truly has the condition
- **NPV:** probability a negative test truly does not

**ROC Curve:**
- Plots sensitivity vs 1-specificity across all cutoff values
- **AUC (Area Under the Curve):** overall test performance
  - AUC = 1.0: perfect
  - AUC > 0.9: excellent
  - AUC > 0.8: good
  - AUC = 0.5: no better than chance
- **Youden index:** the optimal cutoff (maximises sensitivity + specificity - 1)

### 6.8 Factor Analysis & Reliability

**Factor analysis:** Identifies underlying dimensions (factors) in a set of measured variables. Useful for questionnaire validation and reducing many variables to a few meaningful constructs.

Key outputs:
- **KMO:** measure of sampling adequacy (> 0.7 = good)
- **Bartlett's test:** tests whether the correlation matrix is suitable for factor analysis
- **Loadings:** how strongly each variable relates to each factor
- **Variance explained:** how much of the total variance each factor accounts for

**Reliability (Cronbach's alpha):** Measures how consistently a set of items measures a single construct.

- α > 0.9: excellent
- α > 0.8: good
- α > 0.7: acceptable
- α > 0.6: questionable
- "Alpha if deleted" shows whether removing an item improves reliability

### 6.9 Graphs & Charts

The Graphs page provides 37+ chart types. The eligibility engine checks your variable selections and warns if they don't fit the chosen chart type.

**Selecting variables:** Each chart type shows different variable selectors. For example:
- Histogram needs 1 numeric variable
- Scatter needs 2 numeric variables
- Boxplot needs 1 numeric + 1 categorical
- Violin, Strip, ECDF need 1 numeric + optional group
- Pareto, Cleveland Dot, Lollipop need 1 category + 1 value
- SPLOM, Parallel Coordinates, PCA need 3+ numeric variables

**Interacting with charts:** Hover for values, zoom with scroll wheel, pan by dragging, download as PNG via the modebar.

**Export options:**
- PNG download (Plotly modebar or Download button)
- Send to Output panel for later review
- Matplotlib export for publication-quality static images

---

## 7. Statistical Test Guide

### Choosing a Test

```
                          ┌─────────────────────────┐
                          │  What is your outcome?  │
                          └──────────┬──────────────┘
                                     │
                   ┌─────────────────┼─────────────────┐
                   │                 │                 │
              Continuous           Binary         Time-to-event
                   │                 │                 │
              ┌────┴────┐       Logistic          Survival
              │         │      Regression         Analysis
          2 groups  3+ groups    (p. 6.7)         (p. 6.6)
              │         │
         ┌────┴────┐    ANOVA /
         │        │   Kruskal-
      Normal  Non-normal  Wallis
         │        │
     t-test  Mann-Whitney
     (p. 6.3)   U (p. 6.3)
```

### Assumptions of Common Tests

| Test | Normality | Equal Variance | Independence |
|------|-----------|---------------|--------------|
| t-test | ✓ | ✓ (Levene's test) | ✓ |
| ANOVA | ✓ | ✓ | ✓ |
| Linear regression | ✓ (residuals) | ✓ | ✓ |
| Mann-Whitney U | ✗ | ✗ | ✓ |
| Kruskal-Wallis | ✗ | ✗ | ✓ |
| Chi-square | ✗ | ✗ | ✓ |
| Pearson correlation | ✓ | ✓ | ✓ |
| Spearman correlation | ✗ | ✗ | ✓ |

### Effect Size Benchmarks

| Measure | Small | Medium | Large |
|---------|-------|--------|-------|
| Cohen's d | 0.2 | 0.5 | 0.8 |
| Pearson's r | 0.1 | 0.3 | 0.5 |
| Eta-squared (η²) | 0.01 | 0.06 | 0.14 |
| Cramer's V | 0.1 | 0.3 | 0.5 |
| Odds Ratio | 1.5 | 2.0 | 3.0 |

---

## 8. Interpreting Outputs

### The p-value

The p-value answers: "If there were actually no effect, how likely would I be to see results this extreme?"

- **p < 0.05:** conventionally considered "statistically significant"
- **p < 0.001:** highly significant
- **p > 0.05:** not statistically significant (but this does NOT mean "no effect")

**Important:** A significant p-value does NOT mean:
- The effect is large (check effect size)
- The result is clinically important (use domain knowledge)
- The finding will replicate (replication studies are needed)

### The Confidence Interval

A 95% confidence interval means: if you repeated the study 100 times, 95 of the intervals would contain the true population value.

- A narrow CI = precise estimate
- A wide CI = imprecise estimate (more data needed)

### The Effect Size

The p-value tells you if an effect exists. The effect size tells you how large it is.

- Always report both p-value AND effect size
- A tiny effect can be "significant" with a large sample
- A large effect can be "non-significant" with a small sample

---

## 9. Charts and Visualisations

### Key Chart Types

| Chart | Best for | Example |
|-------|----------|---------|
| Histogram | Distribution of one numeric variable | Age distribution |
| Boxplot | Comparing distributions across groups | BP by treatment arm |
| Scatter | Relationship between two numeric vars | Age vs cholesterol |
| Violin | Distribution shape across groups | Biomarker by diagnosis |
| Kaplan-Meier | Survival over time | Survival by treatment |
| ROC Curve | Diagnostic test performance | Biomarker accuracy |
| Correlation heatmap | Many pairwise correlations | Lab values matrix |
| Swimmer plot | Individual patient timelines | Oncology response |
| Volcano plot | Biomarker discovery | Effect vs significance |
| Bland-Altman | Method comparison | Two measurement techniques |
| Funnel plot | Publication bias detection | Meta-analysis |

### Interpretation Tips

- **Look at the chart first**, then check the numbers
- **Pattern > p-value** — a clear visual pattern matters more than significance
- **Check the axes** — misleading scales can exaggerate or hide differences
- **Small samples** make charts unreliable (too few data points)
- **Outliers** can dominate the visual impression — check if they're real or errors

---

## 10. Common Pitfalls

1. **Confusing correlation with causation.** Two things that correlate may be related to a third variable, not to each other.

2. **Over-relying on p-values.** A p-value just below 0.05 is not materially different from one just above. Report confidence intervals and effect sizes.

3. **Ignoring assumptions.** Using a t-test on severely non-normal data can give misleading results. Check assumptions first, use non-parametric alternatives if violated.

4. **Multiple comparisons.** Running 20 tests at α = 0.05 means one will be "significant" by chance alone. Use corrections (Bonferroni, Holm) or replication.

5. **Small sample sizes.** A study with n = 10 per group has very low power to detect anything except huge effects.

6. **Survival analysis requires events.** If nobody has the event, you cannot estimate survival. At least 5-10 events per predictor are recommended for Cox regression.

7. **Diagnostic tests depend on prevalence.** A test with 99% sensitivity can have low positive predictive value if the disease is rare.

---

## 11. Worked Examples

### Example 1: Comparing Blood Pressure Between Treatment Groups

**Question:** Is systolic blood pressure different between the treatment and control groups?

**Steps:**
1. Upload data with columns: `systolic_bp`, `treatment_arm`
2. Go to Compare Groups → select "Independent t-test"
3. Set Group variable to `treatment_arm`, Test variable to `systolic_bp`
4. Click Run

**Check assumptions first:** Go to Descriptive → Explore, select `systolic_bp` grouped by `treatment_arm`. Check the Shapiro-Wilk test p-value (> 0.05 = normal).

**If normal:** Use the t-test result. Report: *"Systolic BP was significantly higher in the treatment group (M = 142.3, SD = 12.1) compared to control (M = 135.6, SD = 11.4), t(98) = 2.84, p = 0.005, d = 0.57."*

**If non-normal:** Use Mann-Whitney U instead.

### Example 2: Survival Analysis

**Question:** Does a new drug improve survival compared to standard treatment?

**Steps:**
1. Upload data with columns: `survival_months`, `event_death` (0 = censored, 1 = died), `treatment`
2. Go to Survival → set Time = `survival_months`, Status = `event_death`, Factor = `treatment`
3. Click Run Analysis

**Kaplan-Meier results show:**
- The survival curve for the new drug stays higher
- Median survival: drug = 34 months, standard = 22 months
- Log-rank test: p = 0.003 — significant difference

**Cox regression shows:**
- Hazard ratio for new drug = 0.52 (95% CI: 0.35–0.77)
- Patients on the new drug have 48% lower hazard of death

### Example 3: Diagnostic Test Evaluation

**Question:** How accurate is a new biomarker for detecting cancer?

**Steps:**
1. Upload data with columns: `biomarker_level` (continuous), `cancer` (0 = no, 1 = yes)
2. Go to Diagnostic Tests → set Test = `biomarker_level`, Gold Standard = `cancer`
3. Click Run Analysis

**Results:**
- AUC = 0.87 (95% CI: 0.81–0.93) — good discriminatory ability
- Optimal cutoff = 45.2 (sensitivity = 82%, specificity = 79%)
- The biomarker correctly identifies 82% of cancer patients

---

## 12. Glossary

| Term | Definition |
|------|------------|
| **AUC** | Area Under the ROC Curve. Summary measure of diagnostic test performance. 1.0 = perfect, 0.5 = no better than chance. |
| **Censoring** | When follow-up ends before the event occurs. The subject contributes information up to their last known time. |
| **Cohen's d** | Effect size for t-tests: the difference between two means divided by the pooled standard deviation. |
| **Confidence Interval** | A range that plausibly contains the true population value. A 95% CI means 95 of 100 similar intervals would contain the true value. |
| **Cox Regression** | A regression model for time-to-event data that estimates hazard ratios. |
| **Cramer's V** | Effect size for chi-square tests. Ranges from 0 (no association) to 1 (perfect association). |
| **Cronbach's Alpha** | Measure of internal consistency reliability. Values > 0.7 are considered acceptable. |
| **Effect Size** | A measure of how large a difference or relationship is, independent of sample size. |
| **Hazard Ratio** | The ratio of event rates between two groups in survival analysis. HR > 1 = higher risk. |
| **KMO** | Kaiser-Meyer-Olkin measure of sampling adequacy for factor analysis. Values > 0.7 indicate suitability. |
| **Levene's Test** | Tests whether groups have equal variances — an assumption for t-tests and ANOVA. |
| **Log-rank Test** | A test comparing survival distributions between two or more groups. |
| **Odds Ratio** | The odds of an outcome in one group divided by the odds in another. Used in logistic regression. |
| **p-value** | The probability of observing results at least as extreme if the null hypothesis were true. |
| **PCA** | Principal Component Analysis. A dimensionality reduction technique. |
| **Sensitivity** | Proportion of true positives correctly identified by a diagnostic test. |
| **Specificity** | Proportion of true negatives correctly identified by a diagnostic test. |
| **Youden Index** | The optimal cutoff for a diagnostic test — maximises sensitivity + specificity - 1. |

---

## 13. FAQ

**Q: What file formats does DevStat support?**
A: CSV (.csv), Excel (.xlsx, .xls), and SPSS (.sav) files up to 50 MB.

**Q: Do I need an internet connection?**
A: No. The app runs entirely offline. No data is sent to external servers.

**Q: How do I export my results?**
A: Charts can be downloaded as PNG. Analysis results can be sent to the Output panel and exported as PDF.

**Q: What does the eligibility checker do?**
A: It checks your variable selections before you run an analysis. If the variables don't match the analysis type, it explains why and suggests alternatives.

**Q: Why is my p-value shown as 0.000?**
A: Very small p-values are rounded to 0.000 in the display. The actual value is reported as "p < 0.001".

**Q: How do I handle missing data?**
A: DevStat automatically excludes missing values (NA/NaN) from calculations.

**Q: Can I compare more than two groups?**
A: Yes — use one-way ANOVA (parametric) or Kruskal-Wallis (non-parametric) for 3+ groups.

---

## 14. Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| App won't start | Port 8150 in use | Stop other instances, restart the launcher |
| Charts show nothing | Wrong variable type | Check the eligibility message for guidance |
| Analysis fails | Convergence issue | Try fewer predictors, check for constant columns |
| Upload fails | File too large | Files must be under 50 MB |
| Missing values | Data has blanks | The app handles them, but too many may affect results |
| "Column not found" | Typo or wrong dataset | Check column names in Variable View |
| Slow performance | Large dataset | Use sample_100.csv for testing, limit analysis to 10,000 rows |

---

*This guide was written for DevStat v1.0.0. For the latest version, visit the GitHub repository.*
