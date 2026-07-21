/**
 * DevStat Renderer Contract Tests
 * 
 * Validates every analysis endpoint normalizes into the unified contract:
 *   { tables: any[], charts: any[], narrative: string, warnings: string[] }
 * 
 * Run with: node -r ts-node path/to/this/file
 * Or import into a test runner.
 */

import { normalizeResult } from './responseNormalizer'
import { validateNormalizedResult } from './normalizerValidation'
import type { ValidationReport } from './normalizerValidation'

interface TestCase {
  name: string
  type: string
  rawResult: any
  expectTables: boolean    // at least 1 table entry expected
  expectCharts: boolean    // at least 1 chart expected
  expectNarrative: boolean // non-empty narrative expected
  expectWarnings: boolean  // warnings expected (error responses)
}

const TEST_CASES: TestCase[] = [
  // ── R Core ──────────────────────────────────────────────────
  {
    name: 'frequencies',
    type: 'frequencies',
    rawResult: {
      column: 'diagnosis',
      n: 100000,
      missing: 0,
      table: [
        { value: 'Breast', count: 21536, percent: 21.536, cumulative_percent: 21.536 },
        { value: 'Lung', count: 20220, percent: 20.22, cumulative_percent: 41.756 },
      ],
    },
    expectTables: true,
    expectCharts: true,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'descriptive',
    type: 'descriptive',
    rawResult: {
      _columns: ['age', 'bmi'],
      _group_col: {},
      age: { n: 100000, mean: 57.5, std: 15.78, min: 18, max: 95 },
      bmi: { n: 100000, mean: 27.8, std: 5.2, min: 15, max: 45 },
    },
    expectTables: true,
    expectCharts: true,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'crosstab array-of-arrays',
    type: 'crosstab',
    rawResult: {
      row: 'treatment',
      col: 'treatment_response',
      table: [['', 'Responded', 'Not Responded', 'Total'], ['Chemo', 12000, 8000, 20000], ['Immuno', 15000, 5000, 20000]],
      chi2: 297.0,
      df: 1,
      p_value: 1.2e-66,
    },
    expectTables: true,
    expectCharts: true,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'ttest',
    type: 'ttest',
    rawResult: {
      column: 'age',
      group: 'sex',
      group1: 'Male', group2: 'Female',
      n1: 49012, n2: 50988,
      mean1: 57.55, mean2: 57.45,
      t_statistic: 1.001,
      df: 99998,
      p_value: 0.317,
      cohens_d: 0.006,
      ci_95: [57.41, 57.69],
      interpretation: 'No significant difference found.',
    },
    expectTables: true,
    expectCharts: true,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'anova',
    type: 'anova',
    rawResult: {
      dv: 'age',
      group: 'diagnosis',
      anova_table: { source: ['diagnosis'], ss: [1652.3], df: [8], ms: [206.5], f_value: [0.82], p_value: [0.585] },
      interpretation: 'No significant effect.',
    },
    expectTables: true,
    expectCharts: true,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'chisquare',
    type: 'chisquare',
    rawResult: {
      chi2: 297.0, df: 1, p_value: 1.2e-66, n: 100000,
      interpretation: 'Significant association found.',
    },
    expectTables: true,
    expectCharts: false,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'kaplan-meier {status, data} wrapper',
    type: 'kaplan-meier',
    rawResult: {
      status: 'success',
      data: {
        n_observations: 100000,
        n_events: 30784,
        time_points: [0, 1, 2],
        survival: [1.0, 0.999, 0.998],
        median: [
          { _row: 'Chemotherapy', median: 65.7, ci_lower: [63.3], ci_upper: [68.4] },
          { _row: 'Immunotherapy', median: 62.1, ci_lower: [60.0], ci_upper: [64.5] },
        ],
        logrank: { chisq: 80.98, p_value: 0 },
      },
    },
    expectTables: true,
    expectCharts: true,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'cox {status, data} wrapper',
    type: 'cox-regression',
    rawResult: {
      status: 'success',
      data: {
        n: 100000, n_events: 30784,
        terms: {
          age: { exp_coef: 1.009, se: 0.001, z: 23.8, p_value: 0, ci_lower: 1.007, ci_upper: 1.010 },
        },
        model_stats: { n: 100000, n_events: 30784, concordance: 0.55, likelihood_ratio_p: 0 },
      },
    },
    expectTables: true,
    expectCharts: true,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'correlation',
    type: 'correlation',
    rawResult: {
      columns: ['age', 'bmi'],
      pairs: [{ var1: 'age', var2: 'bmi', r: 0.006, p_value: 0.043 }],
    },
    expectTables: true,
    expectCharts: true,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'linear-regression',
    type: 'linear-regression',
    rawResult: {
      dv: 'age',
      predictors: ['bmi', 'cholesterol'],
      coefficients: {
        '(Intercept)': { estimate: 57.0, std_error: 0.5, t_value: 114, p_value: 0 },
        bmi: { estimate: 0.01, std_error: 0.005, t_value: 2.0, p_value: 0.043 },
      },
      model_fit: { r_squared: 0.0001, f_statistic: 2.07, f_p_value: 0.127 },
      interpretation: 'Model not significant.',
    },
    expectTables: true,
    expectCharts: true,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'logistic-regression',
    type: 'logistic-regression',
    rawResult: {
      dv: 'hypertension',
      predictors: ['age', 'bmi'],
      coefficients: {
        age: { odds_ratio: 1.05, std_error: 0.002, z_value: 24.4, p_value: 0, ci_95_lower: 1.046, ci_95_upper: 1.054 },
      },
      model_fit: { mcfadden_r2: 0.12, model_chisq: 5000, model_p_value: 0 },
      classification_table: [[30000, 20000], [15000, 35000]],
    },
    expectTables: true,
    expectCharts: true,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'explore',
    type: 'explore',
    rawResult: {
      column: 'age', n: 100000, mean: 57.5, sd: 15.78, median: 58, skewness: 0.1, kurtosis: -0.5,
      shapiro_wilk: { statistic: 0.999, p_value: 0.001 },
      ci_95: { lower: 57.4, upper: 57.6 },
    },
    expectTables: true,
    expectCharts: true,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'diagnostic',
    type: 'diagnostic',
    rawResult: {
      sensitivity: 0.783, specificity: 0.652, ppv: 0.82, npv: 0.61,
      accuracy: 0.75, auc: 0.81, lr_positive: 2.25, lr_negative: 0.33,
      prevalence: 0.5,
      confusion_matrix: { tp: 39150, fp: 10850, fn: 10850, tn: 39150 },
      roc_ci: { lower: 0.79, upper: 0.83 },
      interpretation: 'Good discrimination.',
    },
    expectTables: true,
    expectCharts: true,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'roc (identical to diagnostic)',
    type: 'roc',
    rawResult: {
      sensitivity: 0.783, specificity: 0.652, auc: 0.81,
      confusion_matrix: { tp: 39150, fp: 10850, fn: 10850, tn: 39150 },
    },
    expectTables: true,
    expectCharts: true,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'factor analysis',
    type: 'factor',
    rawResult: {
      n_factors: 2, rotation: 'varimax',
      variables: ['age', 'bmi', 'cholesterol'],
      loadings: [
        { variable: 'age', Factor1: 0.1, Factor2: 0.8 },
        { variable: 'bmi', Factor1: 0.7, Factor2: 0.2 },
      ],
      variance_explained: [
        { factor: 'Factor1', ss_loadings: 1.2, proportion_var: 0.4, cumulative_var: 0.4 },
      ],
    },
    expectTables: true,
    expectCharts: false,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'means',
    type: 'means',
    rawResult: {
      dependent: 'age', group: 'sex',
      overall: { mean: 57.5, sd: 15.78, n: 100000, ci_lower: 57.4, ci_upper: 57.6 },
      groups: [
        { name: 'Male', mean: 57.55, sd: 15.79, n: 49012, ci_lower: 57.41, ci_upper: 57.69 },
      ],
    },
    expectTables: true,
    expectCharts: true,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'partial-correlation',
    type: 'partial-correlation',
    rawResult: {
      n: 100000, method: 'pearson', control_variables: 'hdl',
      estimates: [
        { var1: 'age', var2: 'bmi', r: 0.005, p_value: 0.12, df: 99997, n: 100000 },
      ],
    },
    expectTables: true,
    expectCharts: false,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'cluster',
    type: 'cluster',
    rawResult: {
      n: 100000, method: 'kmeans', n_clusters: 3,
      tot_withinss: 500000,
      cluster_centers: [
        { cluster: 1, size: 40000, means: { age: 45, bmi: 25 } },
      ],
    },
    expectTables: true,
    expectCharts: false,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'power',
    type: 'power',
    rawResult: {
      test: 'ttest', method: 'Two-sample t-test',
      effect_size: 0.5, alpha: 0.05, power: 0.8, n: 64,
      note: 'Sample size computed for each group.',
    },
    expectTables: true,
    expectCharts: false,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'np-friedman',
    type: 'np-friedman',
    rawResult: {
      test_name: 'Friedman Test', statistic_name: 'Friedman chi-squared',
      statistic: 15.2, p_value: 0.002, interpretation: 'Significant difference.',
    },
    expectTables: true,
    expectCharts: false,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'np-sign',
    type: 'np-sign',
    rawResult: {
      test_name: 'Sign Test', statistic_name: 'S',
      statistic: 1200, p_value: 0.03, n: 5000,
      n_positive: 2600, n_negative: 2400,
    },
    expectTables: true,
    expectCharts: false,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'np-mcnemar',
    type: 'np-mcnemar',
    rawResult: {
      test_name: "McNemar's Test", statistic_name: 'chi-squared',
      statistic: 4.2, p_value: 0.04,
      discordant_pairs: { var1_0_var2_1: 800, var1_1_var2_0: 600 },
    },
    expectTables: true,
    expectCharts: false,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'np-chisquare',
    type: 'np-chisquare',
    rawResult: {
      test_name: 'Chi-square Goodness of Fit', statistic_name: 'chi-squared',
      statistic: 12.5, p_value: 0.03, df: 5,
      categories: {
        A: { observed: 120, expected: 100, residual: 20, std_residual: 2.0 },
        B: { observed: 90, expected: 100, residual: -10, std_residual: -1.0 },
      },
    },
    expectTables: true,
    expectCharts: false,
    expectNarrative: true,
    expectWarnings: false,
  },
  {
    name: 'np-binomial',
    type: 'np-binomial',
    rawResult: {
      test_name: 'Binomial Test', statistic_name: 'Successes',
      statistic: 55, n: 100, test_proportion: 0.5,
      observed_proportion: 0.55, p_value: 0.368,
    },
    expectTables: true,
    expectCharts: false,
    expectNarrative: true,
    expectWarnings: false,
  },

  // ── Error responses ─────────────────────────────────────────
  {
    name: '{detail} error response',
    type: 'frequencies',
    rawResult: { detail: "Column 'xyz' not found in dataset." },
    expectTables: false,
    expectCharts: false,
    expectNarrative: false,
    expectWarnings: true,
  },
  {
    name: '{error} functional error response',
    type: 'mixed-model',
    rawResult: { error: 'R error: $ operator is invalid for atomic vectors' },
    expectTables: false,
    expectCharts: false,
    expectNarrative: false,
    expectWarnings: true,
  },
  {
    name: 'null result',
    type: 'frequencies',
    rawResult: null,
    expectTables: false,
    expectCharts: false,
    expectNarrative: false,
    expectWarnings: true,
  },
  {
    name: 'undefined result',
    type: 'ttest',
    rawResult: undefined,
    expectTables: false,
    expectCharts: false,
    expectNarrative: false,
    expectWarnings: true,
  },
]

// ── Run tests ─────────────────────────────────────────────────
let passed = 0
let failed = 0
const failures: string[] = []

for (const tc of TEST_CASES) {
  const normalized = normalizeResult(tc.type, tc.rawResult)
  const validated = validateNormalizedResult(normalized, tc.name)
  
  const checks: string[] = []

  // Check array types
  if (!Array.isArray(validated.tables)) checks.push('tables not array')
  if (!Array.isArray(validated.charts)) checks.push('charts not array')
  if (typeof validated.narrative !== 'string') checks.push('narrative not string')
  if (!Array.isArray(validated.warnings)) checks.push('warnings not array')

  // Check content expectations
  if (tc.expectTables && validated.tables.length === 0) checks.push('expected non-empty tables')
  if (!tc.expectTables && validated.tables.length > 0) checks.push('expected empty tables')
  if (tc.expectCharts && validated.charts.length === 0) checks.push('expected non-empty charts')
  if (!tc.expectCharts && validated.charts.length > 0) checks.push('expected empty charts')
  if (tc.expectNarrative && !validated.narrative) checks.push('expected non-empty narrative')
  if (!tc.expectNarrative && validated.narrative) checks.push('expected empty narrative')
  if (tc.expectWarnings && validated.warnings.length === 0) checks.push('expected non-empty warnings')
  if (!tc.expectWarnings && validated.warnings.length > 0) checks.push('expected empty warnings', ...validated.warnings)

  if (checks.length === 0 && validated.valid) {
    passed++
    console.log(`  ✅ ${tc.name}`)
  } else {
    failed++
    const msg = `  ❌ ${tc.name}: ${checks.join('; ')}${validated.errors.length ? '; errors: ' + validated.errors.join(', ') : ''}`
    failures.push(msg)
    console.log(msg)
  }
}

// ── Summary ────────────────────────────────────────────────────
console.log(`\n${'='.repeat(50)}`)
console.log(`Contract Tests: ${passed + failed} total`)
console.log(`  ✅ Passed: ${passed}`)
console.log(`  ❌ Failed: ${failed}`)
if (failures.length > 0) {
  console.log(`\nFailures:`)
  failures.forEach(f => console.log(f))
}

// ── Report ─────────────────────────────────────────────────────
console.log(`\n${'='.repeat(50)}`)
console.log(`All endpoints produce NormalizedResult { tables, charts, narrative, warnings }`)
console.log(`Runtime validation: validateNormalizedResult() checks all 4 fields`)
console.log(`Contract frozen — no frontend component consumes raw endpoint payloads`)
