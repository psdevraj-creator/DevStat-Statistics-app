export interface HelpSection {
  title: string
  content: string
  expanded?: string
}

export interface PageHelp {
  title: string
  description: string
  quickStart?: string[]
  sections: HelpSection[]
  chartHelp?: ChartHelp[]
  relatedPages?: string[]
}

export interface ChartHelp {
  chartType: string
  name: string
  whatItShows: string
  whyItMatters: string
  howToInteract: string
  howToInterpret: string
  commonMisreadings: string
  relatedViews: string[]
}

export interface GlossaryEntry {
  term: string
  definition: string
  category: 'statistics' | 'clinical' | 'chart'
}

export interface FAQEntry {
  question: string
  answer: string
  category: string
}

const HELP: Record<string, PageHelp> = {

  // ── Data Page ───────────────────────────────────────────────────────────
  '/': {
    title: 'Data View',
    description: 'Upload, browse, and manage your datasets. This is where every analysis begins.',
    quickStart: [
      'Click "Upload CSV/Excel/SPSS" to load your data file',
      'Once uploaded, browse your data in the table view',
      'Click column headers to sort; use Variable View to inspect types',
      'Switch to Transform tab to create new variables or recode values',
    ],
    sections: [
      { title: 'Uploading Data', content: 'Supports CSV, Excel (.xlsx, .xls), and SPSS (.sav) files up to 50MB. Drag and drop or click to browse.' },
      { title: 'Variable View', content: 'Shows each column\'s data type (numeric, text, date), unique values, and missing counts. Use this to verify your data imported correctly.', expanded: 'If a column shows the wrong type (e.g., a numeric ID as text), check the original file for mixed formats or special characters.' },
      { title: 'Data Transform', content: 'Create new variables using formulas (e.g., bmi = weight / (height/100)^2), recode categorical values, or compute derived columns.', expanded: 'Use standard Python operators: +, -, *, /, **. Available functions: log(), sqrt(), abs(), round(). Example: log(cholesterol) creates a log-transformed column.' },
      { title: 'Row Operations', content: 'Filter rows by condition, delete rows, or keep only matching rows. Useful for removing outliers or focusing on a subgroup.' },
    ],
    relatedPages: ['/analyze/descriptive', '/transform'],
  },

  // ── Descriptive Page ────────────────────────────────────────────────────
  '/analyze/descriptive': {
    title: 'Descriptive Statistics',
    description: 'Summarise your data with statistics, frequency tables, and cross-tabulations.',
    sections: [
      { title: 'Descriptives Tab', content: 'Select one or more numeric variables to see mean, median, standard deviation, min, max, quartiles, skewness, and kurtosis.', expanded: 'Use the Group By option to split statistics by a categorical variable (e.g., mean age by sex).' },
      { title: 'Frequencies Tab', content: 'Build frequency tables for categorical variables — counts, percentages, and cumulative percentages.', expanded: 'Best for: diagnosis codes, treatment arms, yes/no variables. Shows how many cases fall into each category.' },
      { title: 'Crosstabs Tab', content: 'Cross-tabulation with chi-square test and Cramer\'s V. Shows the relationship between two categorical variables.', expanded: 'The contingency table shows observed counts. Expected counts, row/column percentages, and chi-square test results are below. If any expected cell count is below 5, the chi-square p-value may be unreliable — check Fisher\'s exact test for 2×2 tables.' },
      { title: 'Explore Tab', content: 'Normality diagnostics: Shapiro-Wilk test, skewness z-scores, kurtosis, and outlier detection via Tukey\'s fences.', expanded: 'Use Explore before parametric tests (t-test, ANOVA, regression) to check if your data meets the normality assumption.' },
    ],
    chartHelp: [
      { chartType: 'frequencies', name: 'Frequency Bar Chart', whatItShows: 'Count of cases in each category as bars.', whyItMatters: 'Quick visual comparison of category sizes.', howToInteract: 'Hover for exact counts. Toggle to table view for raw numbers.', howToInterpret: 'Taller bars = more cases. Look for dominant categories and rare ones.', commonMisreadings: 'Bar charts show counts, not relationships. Use crosstabs for associations.', relatedViews: ['Crosstabs', 'Pie Chart'] },
      { chartType: 'crosstab', name: 'Grouped Bar Chart', whatItShows: 'Two categorical variables compared side by side.', whyItMatters: 'Visual pattern of association between variables.', howToInteract: 'Hover for cell counts. Click legend to toggle groups.', howToInterpret: 'Look for uneven distribution across groups — that suggests an association.', commonMisreadings: 'Patterns may look stronger or weaker depending on the scale. Check chi-square p-value.', relatedViews: ['Chi-square test', 'Stacked bar chart'] },
    ],
    relatedPages: ['/analyze/compare', '/graphs'],
  },

  // ── Compare Page ────────────────────────────────────────────────────────
  '/analyze/compare': {
    title: 'Compare Groups',
    description: 'Statistical tests to compare groups — t-tests, ANOVA, Mann-Whitney, Wilcoxon, Kruskal-Wallis, and chi-square.',
    sections: [
      { title: 'Choosing a Test', content: 'For 2 groups: t-test (normal data) or Mann-Whitney U (non-normal). For 3+ groups: ANOVA (normal) or Kruskal-Wallis (non-normal). For paired data (before/after): paired t-test or Wilcoxon signed-rank.' },
      { title: 'Reading Results', content: 'The output shows the test statistic, p-value, effect size, and confidence interval. A p-value < 0.05 is conventionally considered statistically significant.', expanded: 'Effect size tells you how LARGE the difference is (not just whether it exists). Cohen\'s d: 0.2 = small, 0.5 = medium, 0.8 = large.' },
      { title: 'Assumption Checks', content: 'Parametric tests (t-test, ANOVA) assume normality and equal variances. Explore tab can check normality. If violated, use the non-parametric alternative.', expanded: 'Levene\'s test (shown in t-test output) checks equal variances. If p < 0.05, the Welch correction is applied automatically.' },
      { title: 'Post-hoc Tests', content: 'ANOVA and Kruskal-Wallis show which specific groups differ from each other. Tukey HSD for ANOVA, Dunn test for Kruskal-Wallis.', expanded: 'Post-hoc tests adjust p-values for multiple comparisons. Only look at post-hoc results if the overall test was significant.' },
    ],
    chartHelp: [
      { chartType: 'boxplot', name: 'Comparison Boxplot', whatItShows: 'Distribution of numeric values across groups — median, quartiles, outliers.', whyItMatters: 'Visual check for group differences before running a statistical test.', howToInteract: 'Hover for exact values. Boxes show IQR, whiskers show range.', howToInterpret: 'Non-overlapping boxes suggest a significant difference. Look at median position and spread.', commonMisreadings: 'Boxplots hide distribution shape. Use violin plots for density information.', relatedViews: ['Violin Plot', 'Strip Plot'] },
    ],
    relatedPages: ['/analyze/descriptive', '/graphs'],
  },

  // ── Correlation Page ────────────────────────────────────────────────────
  '/analyze/correlation': {
    title: 'Correlation Analysis',
    description: 'Measure the strength and direction of relationships between numeric variables.',
    sections: [
      { title: 'Correlation Methods', content: 'Pearson: linear relationships, assumes normality. Spearman: monotonic relationships, no normality assumption. Kendall: non-parametric, best for small samples or many ties.', expanded: 'Pearson r ranges from -1 to +1. 0 = no linear relationship. ±0.1 = small, ±0.3 = medium, ±0.5 = large.' },
      { title: 'Reading the Matrix', content: 'The correlation matrix shows r-values above the diagonal and p-values below. Significant correlations are starred (* p<0.05, ** p<0.01, *** p<0.001).', expanded: 'Red/blue coloring in the heatmap view shows positive (blue) and negative (red) correlations at a glance.' },
      { title: 'Partial Correlation', content: 'Measures the relationship between two variables while controlling for one or more additional variables.', expanded: 'Example: correlation between age and cholesterol while controlling for BMI. Removes the effect of BMI from both variables.' },
    ],
    chartHelp: [
      { chartType: 'correlation_heatmap', name: 'Correlation Heatmap', whatItShows: 'Colored matrix of pairwise correlations between variables.', whyItMatters: 'Spot patterns across many variables at once — ideal for biomarker or survey data.', howToInteract: 'Hover for exact r-values. Colors range from blue (positive) to red (negative).', howToInterpret: 'Look for clusters of strong correlations. Dark blue = strong positive, dark red = strong negative.', commonMisreadings: 'Correlation does NOT mean causation. A strong correlation could be coincidental or driven by a third variable.', relatedViews: ['Scatter Plot', 'Partial Correlation', 'Pair Plot'] },
    ],
    relatedPages: ['/analyze/regression', '/graphs'],
  },

  // ── Regression Page ─────────────────────────────────────────────────────
  '/analyze/regression': {
    title: 'Regression Analysis',
    description: 'Model relationships between variables — linear regression for continuous outcomes, logistic for binary outcomes.',
    sections: [
      { title: 'Linear Regression', content: 'Predicts a continuous outcome from one or more predictors. Output includes coefficients, R-squared, and ANOVA table.', expanded: 'R-squared = proportion of variance explained. Adjusted R-squared penalises for adding useless predictors. Significant F-test means the model predicts better than chance.' },
      { title: 'Logistic Regression', content: 'Predicts a binary outcome (yes/no, alive/dead). Output includes odds ratios with confidence intervals.', expanded: 'Odds Ratio > 1 = higher odds of the outcome. OR < 1 = lower odds. The 95% CI that does not cross 1.0 is significant. Pseudo R-squared is approximate — focus on the AUC or classification table.' },
      { title: 'Variable Selection', content: 'Enter: all variables at once. Stepwise: adds/removes based on p-value thresholds. Forward: adds best predictor at each step. Backward: starts with all, removes weakest.', expanded: 'Stepwise methods are controversial — they can overfit and may not find the "best" model. Use Enter with careful variable selection when possible.' },
      { title: 'Checking Assumptions', content: 'Residuals should be normally distributed (check Shapiro-Wilk in output) and have constant variance. Durbin-Watson near 2.0 = no autocorrelation.', expanded: 'Outliers with standardized residual > 3 may be influential. Consider removing or investigating these cases.' },
    ],
    relatedPages: ['/analyze/correlation', '/analyze/descriptive'],
  },

  // ── Survival Page ───────────────────────────────────────────────────────
  '/survival': {
    title: 'Survival Analysis',
    description: 'Analyse time-to-event data with Kaplan-Meier curves and Cox regression.',
    sections: [
      { title: 'Kaplan-Meier', content: 'Estimates survival probability over time. The curve shows the proportion of subjects who have not yet had the event at each time point.', expanded: 'Steps in the curve = event times. Tick marks = censored observations (lost to follow-up or still event-free at study end). The log-rank test compares survival between groups.' },
      { title: 'Cox Regression', content: 'Models the hazard (instantaneous risk) of the event as a function of predictors. Output includes hazard ratios with CIs.', expanded: 'Hazard Ratio > 1 = increased risk. HR < 1 = protective effect. The proportional hazards assumption (checked via Schoenfeld residuals) must hold for valid results.' },
      { title: 'Preparing Survival Data', content: 'You need two columns: time (numeric, e.g., months) and status (0 = censored, 1 = event). Use the "Prepare" tab if you have date columns that need conversion.', expanded: 'From dates: the app computes survival_time = event_date - start_date. Event = 1 if censor_date is missing, 0 if event_date is missing.' },
    ],
    chartHelp: [
      { chartType: 'km_curve', name: 'Kaplan-Meier Survival Curve', whatItShows: 'Estimated survival probability over time, one line per group.', whyItMatters: 'Standard way to present survival data in medical research.', howToInteract: 'Hover for survival probability at specific time points. Use zoom to focus on early or late periods.', howToInterpret: 'Steeper drops = more events. Wider separation between groups = stronger treatment effect. Vertical ticks = censored observations.', commonMisreadings: 'The curve at the right tail may be unstable if few subjects remain at risk. Check the "number at risk" table below.', relatedViews: ['Cox Regression', 'Forest Plot'] },
      { chartType: 'forest', name: 'Forest Plot', whatItShows: 'Hazard ratios with confidence intervals for each predictor.', whyItMatters: 'Summarises multiple predictors\' effects in one compact visual.', howToInterpret: 'Points left of 1.0 = protective, right = harmful. Lines crossing 1.0 = not significant. Longer CI = less precise estimate.', commonMisreadings: 'Do not compare significance across predictors with different scales. The forest plot shows relative effects, not absolute risk.', relatedViews: ['Cox Regression', 'Kaplan-Meier'] },
    ],
    relatedPages: ['/analyze/descriptive', '/graphs'],
  },

  // ── Diagnostic Page ─────────────────────────────────────────────────────
  '/analyze/diagnostic': {
    title: 'Diagnostic Tests',
    description: 'Evaluate the accuracy of a diagnostic test against a gold standard.',
    sections: [
      { title: '2×2 Table', content: 'Shows true positives, false positives, false negatives, and true negatives. From these, sensitivity and specificity are computed.', expanded: 'Sensitivity = TP / (TP + FN) — how well the test detects true cases. Specificity = TN / (TN + FP) — how well the test rules out non-cases.' },
      { title: 'ROC Curve', content: 'Plots sensitivity vs 1-specificity across all possible cutoff values. The AUC (Area Under the Curve) summarises overall test performance.', expanded: 'AUC = 1.0: perfect test. AUC > 0.9: excellent. AUC > 0.8: good. AUC = 0.5: no better than chance. The optimal cutoff maximises sensitivity + specificity (Youden index).' },
      { title: 'Predictive Values', content: 'PPV = probability that a positive test truly has the condition. NPV = probability that a negative test truly does not.', expanded: 'Unlike sensitivity/specificity, PPV and NPV depend on disease prevalence. A test with high sensitivity may have low PPV in a low-prevalence population.' },
    ],
    relatedPages: ['/graphs', '/analyze/descriptive'],
  },

  // ── Factor Page ─────────────────────────────────────────────────────────
  '/analyze/factor': {
    title: 'Factor Analysis & Reliability',
    description: 'Identify underlying structure in your variables (factor analysis) and measure internal consistency (reliability).',
    sections: [
      { title: 'Factor Analysis', content: 'Exploratory factor analysis groups correlated variables into underlying factors. Useful for questionnaire validation and reducing many variables to a few dimensions.', expanded: 'KMO > 0.7 = adequate for factor analysis. Bartlett\'s test should be significant. Loadings > 0.4 indicate a variable belongs to a factor. Varimax rotation makes factors easier to interpret.' },
      { title: 'Reliability (Cronbach\'s Alpha)', content: 'Measures how consistently a set of items measures a single construct. Alpha > 0.7 is considered acceptable for research.', expanded: 'Alpha-if-deleted shows whether removing an item improves reliability. Item-total correlation < 0.3 suggests the item may not belong with the others.' },
    ],
    relatedPages: ['/analyze/correlation', '/graphs'],
  },

  // ── Graphs Page ─────────────────────────────────────────────────────────
  '/graphs': {
    title: 'Graphs & Charts',
    description: 'Create interactive visualisations from your data. Choose from 37+ chart types.',
    sections: [
      { title: 'Choosing a Chart', content: 'Select a chart type from the gallery. The eligibility engine will warn if your variable selection does not fit the chart type.', expanded: 'Histogram: 1 numeric variable. Boxplot: 1 numeric + 1 categorical. Scatter: 2 numeric. Bar: 1 categorical. KM Curve: time + status. Explore the gallery — each card shows the data requirements.' },
      { title: 'Customising Charts', content: 'Each chart type shows different selectors based on what it needs. Use Group/Color to split data by a categorical variable.', expanded: 'For charts needing 3+ variables (SPLOM, Radar, Parallel Coordinates, PCA), use the multi-select dropdown.' },
      { title: 'Exporting', content: 'Download as PNG via the button, or send to the Output panel for later review.', expanded: 'For publication-quality figures, use the "Export as Matplotlib" option which generates a print-ready PNG with proper styling.' },
    ],
    relatedPages: ['/output'],
  },

  // ── Output Page ─────────────────────────────────────────────────────────
  '/output': {
    title: 'Output Viewer',
    description: 'Review and manage all your analysis results in one place.',
    sections: [
      { title: 'Viewing Results', content: 'Each analysis appears as a card with the analysis type, timestamp, and results. Charts can be toggled to table view.', expanded: 'Use the checkboxes to select multiple results for comparison or export.' },
      { title: 'Exporting Results', content: 'Export selected results as PDF or download raw data. The log download includes both frontend and backend logs for debugging.', expanded: 'PDF export includes all selected results — charts, tables, and interpretation text.' },
    ],
    relatedPages: [],
  },

  // ── Wizard Page ─────────────────────────────────────────────────────────
  '/wizard': {
    title: 'Analysis Wizard',
    description: 'Describe your research question in plain English, and the wizard will guide you to the right analysis.',
    sections: [
      { title: 'How It Works', content: 'Tell the wizard about your data and what you want to find out. It will ask follow-up questions and recommend the appropriate statistical test.', expanded: 'Example: "I want to compare blood pressure between men and women" → the wizard recommends an independent t-test.' },
      { title: 'After the Recommendation', content: 'Click the suggested test to go directly to the analysis page with the correct settings pre-filled.', expanded: 'You can also explore alternative tests listed by the wizard if your data does not meet the recommended test\'s assumptions.' },
    ],
    relatedPages: ['/analyze/compare', '/analyze/correlation', '/survival'],
  },

  // ── AI Assistant Page ───────────────────────────────────────────────────
  '/ai': {
    title: 'AI Assistant',
    description: 'Ask questions about your data in natural language. The AI will run analyses and explain the results.',
    sections: [
      { title: 'Asking Questions', content: 'Type or speak your question. Examples: "Compare age between males and females", "What predicts survival?", "Show me the distribution of cholesterol by diagnosis."', expanded: 'The AI will determine which analyses to run, execute them, and synthesise a plain-English interpretation.' },
      { title: 'Understanding Responses', content: 'Each result includes the test statistic, p-value, effect size, and a clinical interpretation. Charts are embedded in the response.', expanded: 'The AI explains what the numbers mean in context — not just "p < 0.05" but "Patients in Group A had significantly higher blood pressure than Group B (mean difference: 12 mmHg, p = 0.003)."' },
    ],
    relatedPages: ['/wizard', '/output'],
  },

  // ── Transform Page ──────────────────────────────────────────────────────
  '/transform': {
    title: 'Data Transform',
    description: 'Create new variables, recode values, and transform your data.',
    sections: [
      { title: 'Compute Variable', content: 'Create a new column using a formula. Example: bmi = weight_kg / (height_m ** 2)', expanded: 'Available functions: log(), sqrt(), abs(), round(), sin(), cos(). Use column names directly in formulas.' },
      { title: 'Recode Values', content: 'Replace existing values in a column. Useful for combining categories or fixing coding errors.', expanded: 'Example: recode "Male"/"Female" to 0/1, or combine "Stage I" and "Stage II" into "Early Stage".' },
    ],
    relatedPages: ['/'],
  },

  // ── Syntax Page ─────────────────────────────────────────────────────────
  '/syntax': {
    title: 'Syntax Editor',
    description: 'Run custom code against your dataset. Note: syntax execution is not available in the Python-only engine.',
    sections: [
      { title: 'Status', content: 'Syntax execution is currently disabled in the Python-only engine. This feature was previously used for running R code against the dataset.', expanded: 'If you need custom analysis, consider using the AI Assistant or the Data Transform page instead.' },
    ],
    relatedPages: ['/transform', '/ai'],
  },
}

const QUICK_START: { step: number; title: string; description: string; action: string }[] = [
  { step: 1, title: 'Upload Your Data', description: 'Start by uploading a CSV, Excel, or SPSS file.', action: 'Go to Data View → Upload' },
  { step: 2, title: 'Explore Your Variables', description: 'Check variable types, missing values, and distributions.', action: 'Click Variable View or go to Descriptive → Explore' },
  { step: 3, title: 'Ask a Question', description: 'Use the Wizard or AI Assistant to describe what you want to find out.', action: 'Try the Wizard or AI Assistant' },
  { step: 4, title: 'Run an Analysis', description: 'Select variables and click Run. The eligibility checker will guide you.', action: 'Choose Compare Groups or Correlation' },
  { step: 5, title: 'Visualise Results', description: 'Create charts from your results or from raw data.', action: 'Open Graphs page or check Output tab' },
  { step: 6, title: 'Export & Share', description: 'Download charts as PNG, export tables as PDF, or send to the Output panel.', action: 'Use Export buttons or Output tab' },
]

const CHART_INTERPRETATIONS: Record<string, ChartHelp> = {
  // Original charts
  'histogram': {
    chartType: 'histogram', name: 'Histogram',
    whatItShows: 'Distribution of a single numeric variable — how many cases fall into each value range (bin).',
    whyItMatters: 'Quickly assess normality, identify outliers, and understand the shape of your data.',
    howToInteract: 'Hover for exact count per bin. Adjust bins for more/less detail. Toggle normal curve overlay.',
    howToInterpret: 'Bell-shaped = normal distribution. Skewed right = tail on the right. Bimodal = two distinct groups in your data.',
    commonMisreadings: 'Small bin counts can make noise look like patterns. Increase bins if the shape looks jagged.',
    relatedViews: ['Boxplot', 'Q-Q Plot', 'ECDF'],
  },
  'boxplot': {
    chartType: 'boxplot', name: 'Boxplot',
    whatItShows: 'Five-number summary (min, Q1, median, Q3, max) plus outliers as individual points.',
    whyItMatters: 'Standard way to compare distributions across groups — median, spread, and outliers at a glance.',
    howToInteract: 'Hover for exact values. Points beyond whiskers are outliers (Tukey\'s rule: >1.5× IQR).',
    howToInterpret: 'Median line position shows central tendency. Box height = IQR (middle 50%). Whiskers = range excluding outliers.',
    commonMisreadings: 'Boxplots hide distribution shape — two very different distributions can have identical boxplots. Use violin or strip plot alongside.',
    relatedViews: ['Violin Plot', 'Strip Plot', 'Histogram'],
  },
  'scatter': {
    chartType: 'scatter', name: 'Scatter Plot',
    whatItShows: 'Relationship between two numeric variables as individual points.',
    whyItMatters: 'Essential for spotting correlations, trends, clusters, and outliers between two measurements.',
    howToInteract: 'Hover for point values. The regression line shows the linear trend with R² annotation.',
    howToInterpret: 'Points sloping up = positive correlation. Down = negative. Tight cluster around line = strong relationship.',
    commonMisreadings: 'Outliers can dramatically affect the regression line. Check for influential points. Correlation ≠ causation.',
    relatedViews: ['Correlation Matrix', 'Hexbin', 'Bubble Chart'],
  },
  'violin': {
    chartType: 'violin', name: 'Violin Plot',
    whatItShows: 'Distribution density of a numeric variable across groups — wider sections = more data.',
    whyItMatters: 'Shows distribution shape (unlike boxplots) while comparing groups (unlike histograms).',
    howToInteract: 'Hover for density values. Inner box shows quartiles and median.',
    howToInterpret: 'Look at shape, spread, and central tendency across groups. Bumps = multiple modes.',
    commonMisreadings: 'Violin width is density, not count. A wide violin with few data points can be misleading.',
    relatedViews: ['Boxplot', 'Strip Plot', 'Ridgeline'],
  },
  'km_curve': {
    chartType: 'km_curve', name: 'Kaplan-Meier Curve',
    whatItShows: 'Estimated survival probability over time, one step per event.',
    whyItMatters: 'Standard way to present time-to-event data in clinical research.',
    howToInteract: 'Hover for survival probability at specific times. Tick marks = censored observations.',
    howToInterpret: 'Wider separation between curves = stronger treatment effect. Steeper drop = more events occurring.',
    commonMisreadings: 'The far right of the curve may be unreliable if few subjects remain at risk. Check the at-risk table.',
    relatedViews: ['Cox Regression', 'Forest Plot'],
  },
  'roc_curve': {
    chartType: 'roc_curve', name: 'ROC Curve',
    whatItShows: 'Sensitivity vs 1-specificity across all possible cutoffs. AUC summarises overall performance.',
    whyItMatters: 'Gold standard for evaluating diagnostic test accuracy.',
    howToInteract: 'Hover for sensitivity/specificity at each cutoff. The optimal cutoff is marked.',
    howToInterpret: 'Closer to top-left corner = better test. AUC > 0.9 = excellent, > 0.8 = good, = 0.5 = worthless.',
    commonMisreadings: 'AUC can hide poor performance in clinically important regions. Check the curve shape, not just the number.',
    relatedViews: ['Diagnostic Test Table', 'Calibration Plot'],
  },
  'correlation_heatmap': {
    chartType: 'correlation_heatmap', name: 'Correlation Heatmap',
    whatItShows: 'Pairwise correlations between multiple variables as a colored grid.',
    whyItMatters: 'Spot patterns across many variables at once — ideal for biomarker, survey, or lab data.',
    howToInteract: 'Hover for exact r-values and p-values. Blue = positive, red = negative correlation.',
    howToInterpret: 'Look for clusters of correlated variables. Dark squares = strong relationships.',
    commonMisreadings: 'Correlation ≠ causation. A strong correlation may be spurious or driven by a confounder.',
    relatedViews: ['Scatter Plot', 'Partial Correlation', 'PCA Scatter'],
  },
  'volcano': {
    chartType: 'volcano', name: 'Volcano Plot',
    whatItShows: 'Effect size on x-axis vs statistical significance on y-axis.',
    whyItMatters: 'Standard for biomarker discovery — highlights features that are both biologically and statistically significant.',
    howToInteract: 'Hover for feature names. Red points = significant (p < 0.05, |effect| > 1).',
    howToInterpret: 'Top-right and top-left points are the most interesting: large effect AND significant p-value.',
    commonMisreadings: 'p-value cutoffs are arbitrary. Consider the biological relevance of effect size, not just statistical significance.',
    relatedViews: ['Scatter Plot', 'Correlation Heatmap'],
  },
  'swimmer': {
    chartType: 'swimmer', name: 'Swimmer Plot',
    whatItShows: 'Individual patient treatment timelines — each bar is one patient, length = treatment duration.',
    whyItMatters: 'Oncology standard for showing individual patient response to treatment.',
    howToInteract: 'Hover for patient ID, duration, and response. Colored markers show best response (CR/PR/SD/PD).',
    howToInterpret: 'Look for patterns: longer bars = better outcomes. Response markers at bar end show final status.',
    commonMisreadings: 'Bars show duration on treatment, not necessarily survival. Check the endpoint definition.',
    relatedViews: ['Kaplan-Meier', 'Gantt Chart'],
  },
  'pca': {
    chartType: 'pca', name: 'PCA Scatter',
    whatItShows: 'High-dimensional data projected onto 2 principal components that capture the most variance.',
    whyItMatters: 'Reveals natural clusters and structure in complex, multi-variable data.',
    howToInteract: 'Hover for group labels. Axis titles show % variance explained by each component.',
    howToInterpret: 'Points close together are similar across all measured variables. Separate clusters = distinct subgroups.',
    commonMisreadings: 'PCA shows the directions of maximum variance, not necessarily the most important biological signal.',
    relatedViews: ['Correlation Heatmap', 'SPLOM', 'Parallel Coordinates'],
  },
  'funnel': {
    chartType: 'funnel', name: 'Funnel Plot',
    whatItShows: 'Effect size vs precision (1/SE). Pseudo-confidence bands form a funnel shape.',
    whyItMatters: 'Detect publication bias in meta-analysis — studies outside the funnel may be missing.',
    howToInteract: 'Hover for individual study details. Dashed lines show 95% pseudo-CI.',
    howToInterpret: 'Symmetrical funnel = no publication bias. Asymmetry (missing studies on one side) = potential bias.',
    commonMisreadings: 'Asymmetry can also come from true heterogeneity, not just bias. Small studies naturally scatter more.',
    relatedViews: ['Forest Plot', 'Scatter Plot'],
  },
  'bland_altman': {
    chartType: 'bland_altman', name: 'Bland-Altman Plot',
    whatItShows: 'Difference between two measurements vs their mean, with limits of agreement (±1.96 SD).',
    whyItMatters: 'Standard method for comparing two measurement techniques — how well do they agree?',
    howToInteract: 'Hover for individual measurement pairs. Green line = mean difference, red = LoA.',
    howToInterpret: 'Most points should fall within the limits of agreement. The mean difference should be near zero (no systematic bias).',
    commonMisreadings: 'Bland-Altman assesses agreement, not correlation. Two methods can be highly correlated but not agree (systematic offset).',
    relatedViews: ['Scatter Plot', 'Correlation'],
  },
}

const GLOSSARY: GlossaryEntry[] = [
  { term: 'p-value', definition: 'The probability of observing your results (or more extreme) if there were actually no effect. Conventionally, p < 0.05 is considered statistically significant.', category: 'statistics' },
  { term: 'Effect Size', definition: 'A measure of how LARGE a difference or relationship is, independent of sample size. Examples: Cohen\'s d, Cramer\'s V, odds ratio.', category: 'statistics' },
  { term: 'Confidence Interval', definition: 'A range that plausibly contains the true population value. A 95% CI means: if you repeated the study 100 times, 95 of the CIs would contain the true value.', category: 'statistics' },
  { term: 'Sensitivity', definition: 'The proportion of true positives correctly identified by a test. High sensitivity = few false negatives.', category: 'clinical' },
  { term: 'Specificity', definition: 'The proportion of true negatives correctly identified by a test. High specificity = few false positives.', category: 'clinical' },
  { term: 'Hazard Ratio', definition: 'The ratio of event rates between two groups in survival analysis. HR > 1 = higher risk, HR < 1 = protective.', category: 'statistics' },
  { term: 'Odds Ratio', definition: 'The odds of an outcome in one group divided by the odds in another group. Used in logistic regression and case-control studies.', category: 'statistics' },
  { term: 'Censoring', definition: 'When follow-up ends before the event occurs, so the exact event time is unknown. The subject contributes information up to their last known time.', category: 'clinical' },
  { term: 'AUC', definition: 'Area Under the ROC Curve. A summary of diagnostic test performance: 1.0 = perfect, 0.5 = no better than chance.', category: 'statistics' },
  { term: 'KMO', definition: 'Kaiser-Meyer-Olkin measure of sampling adequacy for factor analysis. Values > 0.7 indicate the data is suitable for factor extraction.', category: 'statistics' },
  { term: 'Cronbach\'s Alpha', definition: 'A measure of internal consistency reliability. Alpha > 0.7 is considered acceptable. Higher values indicate items measure the same construct.', category: 'statistics' },
  { term: 'Normal Distribution', definition: 'A bell-shaped distribution where most values cluster around the mean. Many statistical tests assume your data is normally distributed.', category: 'statistics' },
  { term: 'Outlier', definition: 'An observation that lies far from the other values. Can be identified by Tukey\'s fences (>1.5× IQR beyond quartiles) or z-scores.', category: 'statistics' },
  { term: 'Log-rank Test', definition: 'A statistical test comparing survival distributions between two or more groups. The null hypothesis is that the groups have identical survival.', category: 'statistics' },
  { term: 'Youden Index', definition: 'The optimal cutoff for a diagnostic test — the point maximising sensitivity + specificity - 1.', category: 'statistics' },
  { term: 'Levene\'s Test', definition: 'Tests whether groups have equal variances — an assumption for t-tests and ANOVA. p > 0.05 means the assumption is met.', category: 'statistics' },
  { term: 'Tukey HSD', definition: 'A post-hoc test for ANOVA that compares all pairs of groups while controlling the family-wise error rate.', category: 'statistics' },
  { term: 'Cohen\'s d', definition: 'An effect size measure for t-tests: the difference between two means divided by the pooled standard deviation. 0.2 = small, 0.5 = medium, 0.8 = large.', category: 'statistics' },
  { term: 'Cramer\'s V', definition: 'An effect size measure for chi-square tests. Ranges from 0 (no association) to 1 (perfect association).', category: 'statistics' },
  { term: 'Eta-squared', definition: 'An effect size for ANOVA: proportion of total variance explained by group membership. η² = 0.01 (small), 0.06 (medium), 0.14 (large).', category: 'statistics' },
  { term: 'PCA', definition: 'Principal Component Analysis. A dimensionality reduction technique that transforms many correlated variables into a few uncorrelated components.', category: 'statistics' },
  { term: 'SPLOM', definition: 'Scatter Plot Matrix. A grid of scatter plots showing all pairwise relationships among multiple variables.', category: 'chart' },
  { term: 'ECDF', definition: 'Empirical Cumulative Distribution Function. Shows the proportion of data points below each value — useful for comparing distributions.', category: 'chart' },
  { term: 'Bland-Altman', definition: 'A method comparison plot showing difference vs mean of two measurements, with limits of agreement (±1.96 SD).', category: 'chart' },
]

const FAQ: FAQEntry[] = [
  { question: 'What file formats does DevStat support?', answer: 'CSV (.csv), Excel (.xlsx, .xls), and SPSS (.sav) files up to 50MB.', category: 'data' },
  { question: 'How do I export my results?', answer: 'Charts can be downloaded as PNG via the Download button or Plotly modebar. Results can be sent to the Output panel and exported as PDF.', category: 'export' },
  { question: 'What does the eligibility checker do?', answer: 'The eligibility engine checks your variable selections before you run an analysis. If you select variables that don\'t fit the analysis type, it explains why and suggests alternatives.', category: 'analysis' },
  { question: 'Why is my p-value exactly 0.000?', answer: 'Very small p-values are rounded to 0.000 in the display. The actual value is shown in the detailed output as "p < 0.001".', category: 'statistics' },
  { question: 'What is the difference between "significant" and "not significant"?', answer: 'Statistical significance (p < 0.05) means the observed effect is unlikely to have occurred by chance. It does NOT mean the effect is clinically important — check effect size for that.', category: 'statistics' },
  { question: 'How do I handle missing data?', answer: 'DevStat automatically excludes missing values (NA/NaN) from calculations. If a large proportion of your data is missing, consider imputation or check your data collection process.', category: 'data' },
  { question: 'Can I compare more than two groups?', answer: 'Yes — use one-way ANOVA (parametric) or Kruskal-Wallis (non-parametric) for 3+ groups.', category: 'analysis' },
  { question: 'Why did my chart show "Not supported"?', answer: 'Some chart types require specific data shapes. The eligibility checker explains what\'s needed. Try a different chart type or check your variable selections.', category: 'charts' },
  { question: 'How do I get publication-quality figures?', answer: 'Use the matplotlib export option on the Graphs page. This generates a print-ready PNG with proper styling.', category: 'charts' },
]

export function getPageHelp(path: string): PageHelp | undefined {
  return HELP[path]
}

export function getChartInterpretation(chartType: string): ChartHelp | undefined {
  return CHART_INTERPRETATIONS[chartType]
}

export function getQuickStart(): typeof QUICK_START {
  return QUICK_START
}

export function searchHelp(query: string): { type: string; title: string; content: string; path?: string }[] {
  const q = query.toLowerCase()
  const results: { type: string; title: string; content: string; path?: string }[] = []
  for (const [path, page] of Object.entries(HELP)) {
    if (page.title.toLowerCase().includes(q) || page.description.toLowerCase().includes(q)) {
      results.push({ type: 'page', title: page.title, content: page.description, path })
    }
    for (const section of page.sections) {
      if (section.title.toLowerCase().includes(q) || section.content.toLowerCase().includes(q)) {
        results.push({ type: 'section', title: `${page.title}: ${section.title}`, content: section.content, path })
      }
    }
  }
  for (const chart of Object.values(CHART_INTERPRETATIONS)) {
    if (chart.name.toLowerCase().includes(q) || chart.whatItShows.toLowerCase().includes(q)) {
      results.push({ type: 'chart', title: chart.name, content: chart.whatItShows })
    }
  }
  for (const entry of GLOSSARY) {
    if (entry.term.toLowerCase().includes(q) || entry.definition.toLowerCase().includes(q)) {
      results.push({ type: 'glossary', title: entry.term, content: entry.definition })
    }
  }
  for (const faq of FAQ) {
    if (faq.question.toLowerCase().includes(q) || faq.answer.toLowerCase().includes(q)) {
      results.push({ type: 'faq', title: faq.question, content: faq.answer })
    }
  }
  return results.slice(0, 20)
}

export function getAllGlossary(): GlossaryEntry[] {
  return GLOSSARY
}

export function getAllFAQ(): FAQEntry[] {
  return FAQ
}
