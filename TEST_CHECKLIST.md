# DevStat — Manual Test Checklist

**Dataset:** `C:\Users\dell 7390\OneDrive\Desktop\Desktop files\DevStat\test_dataset.csv` (120 rows, 28 columns)
**Goal:** Test every feature end-to-end on both desktop and Cloud Run.

---

## 1. DATA UPLOAD

### 1.1 Upload CSV
- [ ] Click **Data → Data View** in the top menu
- [ ] Click the **Upload** button (top-left, file icon)
- [ ] Select `C:\Users\dell 7390\OneDrive\Desktop\Desktop files\DevStat\test_dataset.csv`
- [ ] **Expected:** Table loads with 120 rows and 28 columns. Patient IDs show in first column.

### 1.2 Dataset info
- [ ] After upload, check the status bar at the bottom
- [ ] **Expected:** Shows "120 rows × 28 columns" and the filename

### 1.3 Upload Excel (.xlsx)
- [ ] Open the file in Excel, save a copy as `test_dataset.xlsx` in `C:\Users\dell 7390\OneDrive\Desktop\Desktop files\DevStat\`
- [ ] Click **Reset** (trash icon) to clear data
- [ ] Upload the `.xlsx` file
- [ ] **Expected:** Same 120 rows load correctly

### 1.4 Upload SPSS (.sav) — *if available*
- [ ] Skip if you don't have SPSS/ haven export
- [ ] **Expected:** Data loads with variable labels preserved

### 1.5 Invalid file
- [ ] Click **Upload**, select a `.txt` or `.pdf` file
- [ ] **Expected:** Red error message: "Unsupported file extension"

---

## 2. DATA VIEW (Grid)

### 2.1 Scroll
- [ ] Scroll horizontally to see all 28 columns
- [ ] Scroll vertically past row 100
- [ ] **Expected:** Smooth scrolling, column headers stay fixed

### 2.2 Sort
- [ ] Click the **age** column header → click again to toggle asc/desc
- [ ] **Expected:** Ages sort ascending (18 → 98), then descending

### 2.3 Filter
- [ ] Hover over **gender** column → click filter icon (funnel)
- [ ] Select only "Female" → Apply
- [ ] **Expected:** Only female patients shown (about half)
- [ ] Clear filter

### 2.4 Pagination
- [ ] Check page controls at bottom of grid
- [ ] Change page size to 50
- [ ] **Expected:** Shows 50 rows per page, page 1/3 total

### 2.5 Edit a cell
- [ ] Double-click row 1, **age** column
- [ ] Change value from X to `999`
- [ ] Press Enter
- [ ] **Expected:** Value changes to 999. Undo button activates.
- [ ] Change it back manually or use Undo

### 2.6 Undo / Redo
- [ ] Click **Undo** button (left arrow, bottom toolbar)
- [ ] **Expected:** Age reverts to original value
- [ ] Click **Redo** (right arrow)
- [ ] **Expected:** Age changes back to 999

### 2.7 Add a row
- [ ] Click **Add Row** button (+ icon)
- [ ] **Expected:** New empty row appears at bottom (row 121)

### 2.8 Delete a row
- [ ] Click row 121 to select it
- [ ] Click **Delete Row** (trash icon)
- [ ] **Expected:** Row 121 removed, back to 120 rows

### 2.9 Add a column
- [ ] Click **Add Column** button
- [ ] Enter name: `test_col`, type: `Numeric`, default: `0`
- [ ] **Expected:** New column appears at end, all values = 0

### 2.10 Delete a column
- [ ] Right-click **test_col** header → Delete Column
- [ ] **Expected:** Column removed, back to 28 columns

---

## 3. VARIABLE VIEW (SPSS-style metadata)

### 3.1 Open Variable View
- [ ] Click **Variable View** tab (next to Data View at bottom)
- [ ] **Expected:** Table with one row per variable: Name, Type, Width, Decimals, Label, etc.

### 3.2 Set variable label
- [ ] Click **age** row → **Label** column → type `Patient age at admission (years)`
- [ ] Click elsewhere to save
- [ ] **Expected:** Label saved. Hover over "age" column header in Data View → tooltip shows label.

### 3.3 Set value labels
- [ ] Click **gender** row → **Value Labels** column
- [ ] Enter: `1 = Male` on line 1, `2 = Female` on line 2
- [ ] Click elsewhere to save
- [ ] **Expected:** In Data View, gender column shows labels instead of raw text

### 3.4 Change measure type
- [ ] Click **pain_score** row → **Measure** dropdown → change from "Scale" to "Ordinal"
- [ ] **Expected:** pain_score is now treated as ordinal in analyses

### 3.5 Missing values
- [ ] Click **bmi** row → **Missing** column → enter `99`
- [ ] Go to Data View → edit any **bmi** cell to `99`
- [ ] **Expected:** That cell now appears as empty (treated as missing)

### 3.6 Variable roles
- [ ] Click **patient_id** row → **Role** dropdown → change to "None"
- [ ] **Expected:** patient_id excluded from analyses

---

## 4. TRANSFORM (SPSS Transform menu)

### 4.1 Compute variable
- [ ] Click **Transform** in the menu (or **Data → Transform**)
- [ ] Click **Compute Variable**
- [ ] Name: `bmi_category`, Expression: `if(bmi < 18.5, 'Underweight', if(bmi < 25, 'Normal', if(bmi < 30, 'Overweight', 'Obese')))`
- [ ] **Or simpler:** Expression: `bmi / 10`
- [ ] Click **Compute**
- [ ] **Expected:** New column `bmi_category` appears in Data View

### 4.2 Compute preview
- [ ] In Compute Variable, enter expression: `age * 2 + 10`
- [ ] Click **Preview**
- [ ] **Expected:** Shows 10 sample values without creating the column

### 4.3 Recode (into same variable)
- [ ] Click **Recode**
- [ ] Source: `pain_score`, Target: leave blank (same variable)
- [ ] Mapping: `0→0`, `1→1`, `2→2`, `3→3`, `4→4`, `5→5`, `6→3`, `7→3`, `8→4`, `9→4`, `10→5`
- [ ] Click **Recode**
- [ ] **Expected:** pain_score values 6-10 are collapsed into 3-5

### 4.4 Recode (into new variable)
- [ ] Click **Recode**
- [ ] Source: `age`, Target (new): `age_group`
- [ ] Mapping: `18-40→Young`, `41-60→Middle`, `61-85→Senior`
- [ ] Click **Recode**
- [ ] **Expected:** New column `age_group` with categories

### 4.5 Rank cases
- [ ] Click **Rank Cases**
- [ ] Variable: `bmi`, Rank Type: `Rank`, Suffix: `_rank`
- [ ] Click **Run**
- [ ] **Expected:** New column `bmi_rank` with ranked values (1-120)
- [ ] Try again with Rank Type = `NTile (Quartiles)`, N = 4
- [ ] **Expected:** New column divides BMI into quartiles (1-4)

### 4.6 Count occurrences
- [ ] Click **Count Occurrences**
- [ ] Target: `smoker_count`, Variables: `smoking_status`, Values to count: `Smoker`
- [ ] Click **Run**
- [ ] **Expected:** New column with 1 for smokers, 0 for others

### 4.7 Sort cases
- [ ] Click **Sort Cases**
- [ ] Key 1: `age` Ascending, Key 2: `bmi` Descending
- [ ] Click **Sort**
- [ ] **Expected:** Data sorted by age ascending, then BMI descending
- [ ] Check row 1 → youngest patient, row 120 → oldest patient

### 4.8 Select If (filter)
- [ ] Click **Select If**
- [ ] Mode: `Filter`, Expression: `age >= 40 and bmi < 30`
- [ ] Click **Run**
- [ ] **Expected:** Only patients age ≥40 AND BMI <30 remain (check approximate count)
- [ ] Undo or re-upload to restore full dataset

### 4.9 Split File
- [ ] Click **Split File**
- [ ] State: `On`, Group by: `gender`
- [ ] Click **Apply**
- [ ] **Expected:** Subsequent analyses will be split by gender (two tables)
- [ ] Turn Split File **Off** when done testing

### 4.10 Weight Cases
- [ ] Click **Weight Cases**
- [ ] State: `On`, Weight variable: `followup_months`
- [ ] Click **Apply**
- [ ] **Expected:** Analyses now weighted by followup_months
- [ ] Turn Weighting **Off** when done

### 4.11 Aggregate
- [ ] Click **Aggregate**
- [ ] Group by: `treatment_group`
- [ ] Add aggregate: `age` → `mean`, `bmi` → `mean`
- [ ] Click **Run**
- [ ] **Expected:** New dataset with 3 rows (Drug A, Drug B, Placebo) with mean age and BMI per group

---

## 5. DESCRIPTIVE STATISTICS

Let's re-upload `test_dataset.csv` to restore original data for remaining tests.

### 5.1 Descriptives
- [ ] Click **Analyze → Descriptive**
- [ ] Select columns: `age`, `bmi`, `systolic_bp`, `cholesterol`, `hemoglobin`
- [ ] Check options: Mean, Std Dev, Min, Max, Skewness, Kurtosis
- [ ] Click **Run**
- [ ] **Expected:** Table with N, Mean, Std Dev, Min, Max for all 5 variables
- [ ] **Verify:** Age mean should be ~50, Cholesterol mean ~5.2

### 5.2 Descriptives by group
- [ ] Add **gender** as Group By
- [ ] Click **Run**
- [ ] **Expected:** Two tables — one for Male, one for Female

### 5.3 Frequencies
- [ ] Click **Analyze → Frequencies** (or in Descriptive, click Frequencies)
- [ ] Column: `smoking_status`
- [ ] Click **Run**
- [ ] **Expected:** Table showing count and % for each smoking category
- [ ] **Verify:** Non-smokers should be most common (~50%), Smokers smallest

### 5.4 Frequencies — with chart
- [ ] Run Frequencies on `blood_type`
- [ ] Check "Show bar chart"
- [ ] **Expected:** Frequency table + bar chart showing A, B, AB, O distribution

### 5.5 Crosstabs
- [ ] Click **Crosstabs** (in Descriptive menu)
- [ ] Row: `gender`, Column: `smoking_status`
- [ ] Click **Run**
- [ ] **Expected:** Contingency table with counts and percentages, plus Chi-square test result
- [ ] **Verify:** Chi-square p-value should be >0.05 (no strong association)

### 5.6 Crosstabs with expected counts
- [ ] Run Crosstabs on `treatment_group` × `outcome`
- [ ] **Expected:** 3×2 table. Check if Drug A has more "Improved" than Placebo

### 5.7 Explore (normality)
- [ ] Click **Explore**
- [ ] Variable: `bmi`, Group by: `gender`
- [ ] Check "Normality plots with tests"
- [ ] Click **Run**
- [ ] **Expected:** Descriptive stats per group, Shapiro-Wilk test, Q-Q plots, boxplots

### 5.8 Means
- [ ] Click **Means**
- [ ] Dependent: `systolic_bp`, Independent: `treatment_group`
- [ ] Click **Run**
- [ ] **Expected:** Mean SBP per treatment group with confidence intervals

---

## 6. COMPARE MEANS

### 6.1 Independent t-test
- [ ] Click **Analyze → Compare Means**
- [ ] Test type: **Independent t-test**
- [ ] Dependent: `bmi`, Group: `gender`
- [ ] Click **Run**
- [ ] **Expected:** Two tables — group stats (mean BMI Male vs Female) + t-test result
- [ ] **Verify:** Check if p-value < 0.05 (BMI may differ by gender)

### 6.2 Paired t-test
- [ ] Click **Paired t-test**
- [ ] Variable 1: `systolic_bp`, Variable 2: `diastolic_bp`
- [ ] Click **Run**
- [ ] **Expected:** Paired t-test comparing SBP vs DBP. p-value should be ~0.000 (they're different measures)

### 6.3 One-way ANOVA
- [ ] Click **ANOVA** (in Compare Means menu)
- [ ] Dependent: `cholesterol`, Factor: `treatment_group`
- [ ] Click **Run**
- [ ] **Expected:** ANOVA table with F-statistic, df, p-value. Post-hoc tests (Tukey) if significant.
- [ ] **Verify:** Check if any treatment group differs in cholesterol

### 6.4 One-way ANOVA with post-hoc
- [ ] Same as above, ensure "Tukey post-hoc" is checked
- [ ] **Expected:** If ANOVA significant, pairwise comparison table

### 6.5 Mann-Whitney U (non-parametric)
- [ ] Click **Non-parametric Tests → Mann-Whitney U**
- [ ] Dependent: `pain_score`, Group: `gender`
- [ ] Click **Run**
- [ ] **Expected:** Mann-Whitney U statistic + p-value

### 6.6 Wilcoxon Signed-Rank
- [ ] Click **Non-parametric Tests → Wilcoxon Signed-Rank**
- [ ] Variable 1: `anxiety_score`, Variable 2: `depression_score`
- [ ] Click **Run**
- [ ] **Expected:** Wilcoxon test comparing anxiety vs depression scores

### 6.7 Kruskal-Wallis
- [ ] Click **Non-parametric Tests → Kruskal-Wallis**
- [ ] Dependent: `quality_of_life`, Group: `exercise_freq`
- [ ] Click **Run**
- [ ] **Expected:** Kruskal-Wallis H statistic + p-value
- [ ] **Verify:** Quality of life likely differs by exercise frequency

### 6.8 Chi-square test
- [ ] Click **Chi-square Test** (in Compare Means menu)
- [ ] Row: `treatment_group`, Column: `outcome`
- [ ] Click **Run**
- [ ] **Expected:** 3×2 contingency table + Chi-square test + Cramer's V
- [ ] **Verify:** Check if treatment is associated with outcome

### 6.9 Friedman test
- [ ] Click **Non-parametric Tests → Friedman**
- [ ] Variables: `anxiety_score`, `depression_score`, `pain_score`
- [ ] Click **Run**
- [ ] **Expected:** Friedman test comparing all 3 variables

### 6.10 McNemar test
- [ ] Click **Non-parametric Tests → McNemar**
- [ ] Variable 1: `diabetes`, Variable 2: create a new binary column first
- [ ] Or use two binary columns if available
- [ ] **Expected:** McNemar test for paired binary data

### 6.11 Binomial test
- [ ] Click **Non-parametric Tests → Binomial Test**
- [ ] Column: `gender`, Test proportion: 0.5
- [ ] Click **Run**
- [ ] **Expected:** Binomial test — checks if gender split differs from 50/50

### 6.12 Runs test
- [ ] Click **Non-parametric Tests → Runs Test**
- [ ] Column: `age`
- [ ] Click **Run**
- [ ] **Expected:** Wald-Wolfowitz runs test for randomness of age sequence

### 6.13 One-sample KS test
- [ ] Click **Non-parametric Tests → KS Test**
- [ ] Column: `bmi`
- [ ] Click **Run**
- [ ] **Expected:** Kolmogorov-Smirnov test for normality. p > 0.05 if BMI is normal

---

## 7. CORRELATION

### 7.1 Pearson correlation
- [ ] Click **Analyze → Correlation**
- [ ] Columns: `age`, `bmi`, `systolic_bp`, `cholesterol`, `hemoglobin`
- [ ] Method: `Pearson`
- [ ] Click **Run**
- [ ] **Expected:** Correlation matrix (5×5) with r values and p-values
- [ ] **Verify:** Age and SBP should be positively correlated (r ~0.3-0.5)

### 7.2 Spearman correlation
- [ ] Same columns, Method: `Spearman`
- [ ] Click **Run**
- [ ] **Expected:** Spearman rank-order correlation matrix

### 7.3 Partial correlation
- [ ] Click **Partial Correlation**
- [ ] Columns: `age`, `systolic_bp`, Control: `bmi`
- [ ] Click **Run**
- [ ] **Expected:** Partial correlation between age and SBP controlling for BMI

---

## 8. REGRESSION

### 8.1 Linear regression
- [ ] Click **Analyze → Regression → Linear Regression**
- [ ] Dependent: `systolic_bp`, Independents: `age`, `bmi`, `cholesterol`, `hemoglobin`
- [ ] Click **Run**
- [ ] **Expected:** Model summary (R²), ANOVA table, coefficients with p-values
- [ ] **Verify:** Age should be a significant predictor of SBP (p < 0.05)

### 8.2 Logistic regression
- [ ] Click **Analyze → Regression → Logistic Regression**
- [ ] Dependent: `diabetes` (binary: Yes/No)
- [ ] Covariates: `age`, `bmi`, `cholesterol`, `smoking_status`
- [ ] Click **Run**
- [ ] **Expected:** Logistic regression output — odds ratios, Wald statistics, p-values
- [ ] **Verify:** BMI likely predicts diabetes (higher BMI = higher odds)

### 8.3 Mixed model
- [ ] Click **Analyze → Regression → Mixed Model**
- [ ] Dependent: `quality_of_life`, Fixed: `age`, `bmi`
- [ ] Random: (skip if no repeated measures variable available)
- [ ] Click **Run**
- [ ] **Expected:** Mixed model fixed effects table

---

## 9. SURVIVAL ANALYSIS

### 9.1 Survival prep (create time + status columns)
- [ ] Go to **Data → Compute** or use Survival Prep feature
- [ ] If Survival Prep exists: Start: `admission_date`, Event: `discharge_date`, Censor: leave blank
- [ ] Create time column: `survival_days` = `followup_months * 30.44`
- [ ] Status column: `event_occurred` (already exists)

### 9.2 Kaplan-Meier
- [ ] Click **Survival → Kaplan-Meier**
- [ ] Time: `followup_months`, Status: `event_occurred`
- [ ] Factor: `treatment_group`
- [ ] Click **Run**
- [ ] **Expected:** Kaplan-Meier survival curve(s), median survival table, log-rank test
- [ ] **Verify:** Higher followup_months = lower survival; groups may differ slightly

### 9.3 Cox regression
- [ ] Click **Survival → Cox Regression**
- [ ] Time: `followup_months`, Status: `event_occurred`
- [ ] Covariates: `age`, `bmi`, `treatment_group`
- [ ] Click **Run**
- [ ] **Expected:** Cox model — hazard ratios, confidence intervals, p-values
- [ ] **Verify:** Older age should increase hazard (HR > 1)

---

## 10. DIAGNOSTIC TESTS

### 10.1 Create a test column
- [ ] Go to **Data → Compute**
- [ ] Name: `predicted_risk`, Expression: `0.1 + 0.3 * (age / 100) + 0.2 * (bmi / 40) + 0.3 * (cholesterol / 10)`
- [ ] Click **Compute**
- [ ] **Expected:** New column `predicted_risk` (values 0.1-0.9)

### 10.2 Convert predicted risk to binary
- [ ] Compute another column: `test_positive` = `if(predicted_risk > 0.4, 1, 0)`
- [ ] **Expected:** Binary column (1 = high risk, 0 = low risk)

### 10.3 Diagnostic test
- [ ] Click **Analyze → Diagnostic Test**
- [ ] Test: `test_positive`, Gold Standard: `diabetes` (encode Yes=1, No=0 first if needed)
- [ ] Or use: Test = `pain_score > 5` (encoded), Gold = `event_occurred`
- [ ] Click **Run**
- [ ] **Expected:** 2×2 table (TP, FP, FN, TN) with sensitivity, specificity, PPV, NPV, accuracy

### 10.4 ROC curve
- [ ] Click **ROC Curve**
- [ ] Test: (continuous variable like `predicted_risk` or `age`)
- [ ] Gold: `event_occurred`
- [ ] Click **Run**
- [ ] **Expected:** ROC curve plot with AUC value
- [ ] **Verify:** AUC > 0.5 (better than random)

---

## 11. FACTOR ANALYSIS & RELIABILITY

### 11.1 Factor analysis
- [ ] Click **Analyze → Factor Analysis**
- [ ] Columns: `age`, `bmi`, `systolic_bp`, `cholesterol`, `hemoglobin`, `creatinine`, `quality_of_life`
- [ ] Number of factors: `2`, Rotation: `Varimax`
- [ ] Click **Run**
- [ ] **Expected:** KMO, Bartlett's test, factor loadings table, variance explained
- [ ] **Verify:** KMO should be > 0.5, Bartlett's test significant

### 11.2 Reliability (Cronbach's alpha)
- [ ] Click **Analyze → Reliability**
- [ ] Columns: `anxiety_score`, `depression_score`, `pain_score`, `quality_of_life`
- [ ] Click **Run**
- [ ] **Expected:** Cronbach's alpha value + item statistics
- [ ] **Verify:** Alpha may be low since these aren't the same construct (~0.3-0.5)

---

## 12. CLUSTER ANALYSIS

### 12.1 K-means clustering
- [ ] Click **Analyze → Cluster Analysis**
- [ ] Columns: `age`, `bmi`, `systolic_bp`, `cholesterol`
- [ ] Method: `kmeans`, Clusters: `3`
- [ ] Click **Run**
- [ ] **Expected:** Cluster centroids table, cluster membership counts
- [ ] **Verify:** 3 clusters with distinct profiles (e.g., young/low BP, middle, older/high BP)

### 12.2 Hierarchical clustering
- [ ] Same columns, Method: `hierarchical`, Clusters: `3`
- [ ] Click **Run**
- [ ] **Expected:** Dendrogram + cluster assignments

---

## 13. POWER ANALYSIS

### 13.1 Power for t-test
- [ ] Click **Analyze → Descriptive → Power Analysis**
- [ ] Test: `t-test`, Effect size: `0.5`, Power: `0.8`, Alpha: `0.05`
- [ ] Click **Run**
- [ ] **Expected:** Required sample size (N) for 80% power to detect d=0.5
- [ ] **Verify:** N should be ~128 (64 per group)

### 13.2 Power for ANOVA
- [ ] Test: `ANOVA`, Effect size: `0.25`, Power: `0.8`, Alpha: `0.05`, Groups: `3`
- [ ] Click **Run**
- [ ] **Expected:** Total sample size needed for one-way ANOVA

### 13.3 Power for correlation
- [ ] Test: `Correlation`, Effect size: `0.3`, Power: `0.8`, Alpha: `0.05`
- [ ] Click **Run**
- [ ] **Expected:** Sample size needed to detect r=0.3

---

## 14. CHARTS & GRAPHS

### 14.1 Histogram
- [ ] Click **Graphs** in the top menu
- [ ] Select **Histogram**
- [ ] Variable: `age`, Bins: `15`
- [ ] Click **Generate**
- [ ] **Expected:** Histogram of age distribution (should show roughly uniform 18-85)

### 14.2 Boxplot
- [ ] Select **Boxplot**
- [ ] Variable: `bmi`, Group: `gender`
- [ ] Click **Generate**
- [ ] **Expected:** Side-by-side boxplots comparing BMI by gender

### 14.3 Scatter plot
- [ ] Select **Scatter**
- [ ] X: `age`, Y: `systolic_bp`
- [ ] Click **Generate**
- [ ] **Expected:** Scatter plot with upward trend (older = higher BP)

### 14.4 Bar chart
- [ ] Select **Bar Chart**
- [ ] Category: `smoking_status`
- [ ] Click **Generate**
- [ ] **Expected:** Bar chart of smoking status frequencies

### 14.5 Scatter with groups
- [ ] Select **Scatter**
- [ ] X: `bmi`, Y: `cholesterol`, Group: `diabetes`
- [ ] Click **Generate**
- [ ] **Expected:** Colored scatter by diabetes status

### 14.6 ROC curve (chart version)
- [ ] Scroll to **ROC Curve** in Graphs menu
- [ ] Test: `age`, Gold: `event_occurred`
- [ ] Click **Generate**
- [ ] **Expected:** ROC curve with AUC annotation

### 14.7 KM curve (chart version)
- [ ] Select **KM Curve** in Graphs menu
- [ ] Time: `followup_months`, Status: `event_occurred`, Group: `treatment_group`
- [ ] Click **Generate**
- [ ] **Expected:** Kaplan-Meier survival curves by treatment group

### 14.8 Violin plot
- [ ] Variable: `quality_of_life`, Group: `exercise_freq`
- [ ] Click **Generate**
- [ ] **Expected:** Violin plots showing QoL distribution by exercise frequency

### 14.9 Q-Q plot
- [ ] Select **Q-Q Plot**
- [ ] Variable: `bmi`, Distribution: `Normal`
- [ ] Click **Generate**
- [ ] **Expected:** Q-Q plot — points should roughly follow the diagonal line

### 14.10 Heatmap (correlation)
- [ ] Select **Correlation Heatmap**
- [ ] Columns: `age`, `bmi`, `systolic_bp`, `cholesterol`, `hemoglobin`
- [ ] Method: `Pearson`
- [ ] Click **Generate**
- [ ] **Expected:** Colored correlation matrix heatmap

### 14.11 Advanced charts (pick 3)
- [ ] Test any of: **Swimmer Plot**, **Forest Plot**, **Bland-Altman**, **Parallel Coordinates**, **Radar Chart**, **Sankey Diagram**, **Waterfall Chart**, **Funnel Plot**, **Pareto Chart**, **Cleveland Dot Plot**, **Lollipop Chart**, **Dumbbell Plot**

---

## 15. OUTPUT & EXPORT

### 15.1 Output viewer
- [ ] Click **Output** in the menu
- [ ] **Expected:** List of all analyses you've run so far with timestamps

### 15.2 Export results as PDF
- [ ] In Output, click **Export PDF** (or while viewing any analysis result)
- [ ] **Expected:** PDF download with formatted results

### 15.3 Download data as CSV
- [ ] Click **Download** → **CSV**
- [ ] **Expected:** CSV file download of current dataset

### 15.4 Download data as Excel
- [ ] Click **Download** → **Excel**
- [ ] **Expected:** .xlsx file download with formatting

---

## 16. SYNTAX (SPSS-style command log)

### 16.1 View syntax
- [ ] Click **Syntax** in the menu
- [ ] **Expected:** Shows SPSS-style syntax commands for the analyses you've run

### 16.2 Run from syntax
- [ ] Type a command: `DESCRIPTIVES age bmi cholesterol.`
- [ ] Click **Run**
- [ ] **Expected:** Runs the analysis and shows result

---

## 17. WIZARD

### 17.1 Test suggestion wizard
- [ ] Click **Wizard** in the menu
- [ ] Answer the questions to find the right test
- [ ] **Expected:** Interactive guide suggesting appropriate statistical tests
- [ ] Try: "Compare two groups" path → should suggest t-test/Mann-Whitney

---

## 18. CLOUD RUN SPECIFIC TESTS *(if deployed)*

### 18.1 Privacy notice
- [ ] Visit `/api/health` in your browser
- [ ] **Expected:** `"cloud_run": true` and `"privacy_notice"` with data retention message

### 18.2 Cross-user isolation
- [ ] Open the app in two different browsers (e.g., Chrome + Edge)
- [ ] In Browser A: Upload `test_dataset.csv`
- [ ] In Browser B: Refresh the page
- [ ] **Expected:** Browser B shows NO data (not A's data). Browser A still has data.

### 18.3 /api/logs disabled
- [ ] Visit `https://[your-url].run.app/api/logs`
- [ ] **Expected:** `{"available": false, "logs": "Logs disabled on Cloud Run (privacy)."}`

### 18.4 Zero data retention
- [ ] Wait ~15 minutes with no activity (or scale to zero)
- [ ] Reload the page
- [ ] **Expected:** No data persists (fresh start)

---

## SUMMARY

| Section | Tests | Passed |
|---------|-------|--------|
| 1. Data Upload | 5 | ☐ |
| 2. Data View | 10 | ☐ |
| 3. Variable View | 6 | ☐ |
| 4. Transform | 11 | ☐ |
| 5. Descriptive | 8 | ☐ |
| 6. Compare Means | 13 | ☐ |
| 7. Correlation | 3 | ☐ |
| 8. Regression | 3 | ☐ |
| 9. Survival | 3 | ☐ |
| 10. Diagnostic | 4 | ☐ |
| 11. Factor/Reliability | 2 | ☐ |
| 12. Cluster | 2 | ☐ |
| 13. Power Analysis | 3 | ☐ |
| 14. Charts | 11 | ☐ |
| 15. Output/Export | 4 | ☐ |
| 16. Syntax | 2 | ☐ |
| 17. Wizard | 1 | ☐ |
| 18. Cloud Run | 4 | ☐ |
| **Total** | **95** | **___/95** |
