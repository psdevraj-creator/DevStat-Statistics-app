/**
 * DevStat API Client
 * Mirrors the backend endpoints at http://127.0.0.1:8150
 */

import axios from 'axios'
import logStore from '../stores/logStore'

const API_BASE = import.meta.env.VITE_API_URL || ''

export const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 120000,
})

// ── Logging interceptors — log EVERY API call ─────────────────────────
api.interceptors.request.use(
  config => {
    const requestId = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    ;(config as any)._logRequestId = requestId
    ;(config as any)._logStartTime = Date.now()

    let body = config.data
    if (typeof body === 'string') {
      try { body = JSON.parse(body) } catch {}
    }
    const bodyStr = body ? JSON.stringify(body).slice(0, 2000) : '(empty)'

    logStore.addEntry('info', `${(config.method || 'GET').toUpperCase()} ${config.url}`, 'REQUEST', bodyStr, {
      requestId,
      method: config.method,
      url: config.url,
      baseURL: config.baseURL,
      headers: { ...config.headers },
    })
    return config
  },
  error => {
    logStore.addEntry('api', 'REQUEST_ERROR', error.message, '', { error: String(error) })
    return Promise.reject(error)
  },
)

api.interceptors.response.use(
  response => {
    const requestId = (response.config as any)._logRequestId || '?'
    const startTime = (response.config as any)._logStartTime || Date.now()
    const elapsed = Date.now() - startTime
    const method = (response.config?.method || 'GET').toUpperCase()
    const url = response.config?.url || 'unknown'

    const respBody = JSON.stringify(response.data).slice(0, 2000)

    logStore.addEntry(
      'info',
      `${method} ${url}`,
      `RESPONSE ${response.status} (${elapsed}ms)`,
      respBody,
      { requestId, status: response.status, elapsed, headers: response.headers },
    )
    return response
  },
  error => {
    const requestId = (error.config as any)?._logRequestId || '?'
    const startTime = (error.config as any)?._logStartTime || Date.now()
    const elapsed = Date.now() - startTime
    const url = error.config?.url || 'unknown'
    const method = (error.config?.method || 'GET').toUpperCase()
    const status = error.response?.status || 0
    const detail =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'Unknown error'
    const respBody = error.response?.data ? JSON.stringify(error.response.data).slice(0, 2000) : ''

    logStore.addEntry(
      'api',
      `${method} ${url}`,
      `HTTP ${status} (${elapsed}ms)`,
      typeof detail === 'string' ? detail : JSON.stringify(detail),
      {
        requestId,
        status,
        elapsed,
        data: error.response?.data,
        body: respBody,
      },
    )
    return Promise.reject(error)
  },
)

// ── Types ──────────────────────────────────────────────────────────────────

export interface DatasetInfo {
  id: string
  name: string
  filename?: string
  rows?: number
  cols?: number
  dirty?: boolean
}

// ── Data endpoints ──────────────────────────────────────────────────────

export const datasetApi = {
  /** Upload a data file (CSV, Excel, SPSS .sav, Stata .dta) */
  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/api/data/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  /** List available datasets (single-item in single-dataset mode) */
  list: () => api.get('/api/data/datasets'),

  /** Get dataset info + preview */
  info: () => api.get('/api/data/info'),

  /** Get column names (normalized from ColumnInfo objects to strings) */
  columns: async (datasetId?: string) => {
    const path = datasetId
      ? `/api/data/${encodeURIComponent(datasetId)}/columns`
      : '/api/data/columns'
    const res = await api.get(path)
    const data = res.data
    if (Array.isArray(data) && data.length > 0 && typeof data[0] === 'object') {
      return { ...res, data: data.map((c: any) => c.name || c) }
    }
    return res
  },

  /** Get data preview (first 500 rows) */
  preview: (n = 500) => api.get('/api/data/preview'),

  /** Download as CSV */
  download: () =>
    api.get('/api/data/download', { responseType: 'blob' }),

  /** Clear dataset */
  reset: () => api.delete('/api/data/reset'),

  /** Edit a single cell */
  editCell: (row: number, col: string, value: any) =>
    api.put('/api/data/cell', { row, col, value }),

  /** Batch edit cells */
  editCells: (edits: { row: number; col: string; value: any }[]) =>
    api.put('/api/data/cells/batch', edits),

  /** Insert row(s) */
  insertRow: (index = -1, count = 1) =>
    api.post(`/api/data/row?index=${index}&count=${count}`),

  /** Delete a row */
  deleteRow: (rowIndex: number) =>
    api.delete(`/api/data/row/${rowIndex}`),

  /** Add a column */
  addColumn: (name: string, dtype = 'numeric', defaultValue: any = null) =>
    api.post('/api/data/column', { name, dtype, default_value: defaultValue }),

  /** Delete a column */
  deleteColumn: (colName: string) =>
    api.delete(`/api/data/column/${encodeURIComponent(colName)}`),

  // ── Variable View ────────────────────────────────────────────────

  /** Get all variable metadata (SPSS Variable View) */
  variableView: () => api.get('/api/data/variable-view'),

  /** Update a single variable's metadata */
  updateVariable: (name: string, updates: Record<string, any>) =>
    api.put('/api/data/variable', { name, updates }),

  /** Set value labels for a variable */
  setValueLabels: (column: string, valueLabels: Record<string, string>) =>
    api.put('/api/data/value-labels', { column, value_labels: valueLabels }),

  /** Set missing values for a variable */
  setMissingValues: (column: string, missingValues: any[]) =>
    api.put('/api/data/missing-values', { column, missing_values: missingValues }),

  // ── Compute & Recode ──────────────────────────────────────────────

  /** Compute a new variable from an expression */
  compute: (name: string, expression: string) =>
    api.post('/api/data/compute', { name, expression }),

  /** Preview a computed expression (first 10 values) */
  computePreview: (name: string, expression: string) =>
    api.post('/api/data/compute/preview', { name, expression }),

  /** Recode values in a column */
  recode: (column: string, intoNew: string, mappings: Record<string, any>, rules: any[]) =>
    api.post('/api/data/recode', { column, into_new: intoNew, mappings, rules }),

  // ── Undo / Redo ──────────────────────────────────────────────────

  undo: () => api.post('/api/data/undo'),
  redo: () => api.post('/api/data/redo'),
  undoInfo: () => api.get('/api/data/undo-info'),
}

// ── Analysis endpoints ───────────────────────────────────────────────────

export const descriptiveApi = {
  descriptives: (variablesOrDataset: any, optionsOrVariables?: any, groupByOrOptions?: any, actualGroupBy?: string) => {
    // Backward-compat: if first arg is a string (datasetId), shift args
    if (typeof variablesOrDataset === 'string') {
      return api.post('/api/analysis/descriptive', {
        columns: optionsOrVariables as string[],
        group_col: actualGroupBy,
        options: groupByOrOptions as Record<string, boolean>,
      })
    }
    return api.post('/api/analysis/descriptive', {
      columns: variablesOrDataset as string[],
      group_col: groupByOrOptions as string | undefined,
      options: optionsOrVariables as Record<string, boolean>,
    })
  },
  frequencies: (columnOrDataset: any, column?: any) => {
    if (typeof columnOrDataset === 'string') {
      if (!column) {
        // Single argument: assume it's the column name
        return api.post('/api/analysis/frequencies', { column: columnOrDataset })
      }
      if (Array.isArray(column)) {
        // frequencies(dataset, [vars]) — use first variable
        return api.post('/api/analysis/frequencies', { column: column[0] || columnOrDataset })
      }
      // frequencies(dataset, columnName)
      return api.post('/api/analysis/frequencies', { column })
    }
    return api.post('/api/analysis/frequencies', { column: columnOrDataset })
  },
  crosstabs: (var1OrDataset: any, var2OrVar1?: string, var2?: string) => {
    if (var2 === undefined) {
      return api.post('/api/analysis/crosstab', { row: var1OrDataset, col: var2OrVar1 })
    }
    return api.post('/api/analysis/crosstab', { row: var2OrVar1, col: var2 })
  },
  explore: (variable: string) =>
    api.post('/api/analysis/explore', { column: variable }),
  means: (variable: string, groupBy?: string) =>
    api.post('/api/analysis/means', { dependent: variable, group: groupBy }),
}

export const compareApi = {
  ttest: (column: string, group: string) =>
    api.post('/api/analysis/ttest', { test_type: 'independent', dependent: [column], group }),
  ttestPaired: (var1: string, var2: string) =>
    api.post('/api/analysis/ttest-paired', { variable1: var1, variable2: var2 }),
  anova: (column: string, group: string) =>
    api.post('/api/analysis/anova', { test_type: 'anova', dependent: [column], group }),
  chisquare: (col1: string, col2: string) =>
    api.post('/api/analysis/chisquare', { row: col1, col: col2 }),
  // Non-parametric
  npMannWhitney: (dependent: string, group: string) =>
    api.post('/api/analysis/np-mannwhitney', { dependent, group }),
  npWilcoxon: (var1: string, var2: string) =>
    api.post('/api/analysis/np-wilcoxon', { variable1: var1, variable2: var2 }),
  npKruskalWallis: (dependent: string, group: string) =>
    api.post('/api/analysis/np-kruskalwallis', { dependent, group }),
  npFriedman: (variables: string[]) =>
    api.post('/api/analysis/np-friedman', { variables }),
  npSign: (var1: string, var2: string) =>
    api.post('/api/analysis/np-sign', { variable1: var1, variable2: var2 }),
  npMcNemar: (var1: string, var2: string) =>
    api.post('/api/analysis/np-mcnemar', { variable1: var1, variable2: var2 }),
  npChiSquare: (column: string) =>
    api.post('/api/analysis/np-chisquare', { column }),
  npBinomial: (column: string, testProp = 0.5) =>
    api.post('/api/analysis/np-binomial', { column, test_proportion: testProp }),
  npRuns: (column: string) =>
    api.post('/api/analysis/np-runs', { column }),
  npKS: (column: string) =>
    api.post('/api/analysis/np-ks', { column }),

  // ── Backward-compat shim ──
  /** @deprecated Use individual methods directly */
  runTest: (datasetOrTestType: any, testTypeOrVariables?: any, variablesOrOptions?: any, optionsArg?: any) => {
    // Backward-compat: if called as runTest(dataset, testType, variables, options)
    if (optionsArg !== undefined) {
      return compareApi.runTest(testTypeOrVariables, variablesOrOptions, optionsArg)
    }
    const endpoints: Record<string, string> = {
      independent_ttest: '/api/analysis/ttest',
      paired_ttest: '/api/analysis/ttest-paired',
      mann_whitney: '/api/analysis/np-mannwhitney',
      wilcoxon: '/api/analysis/np-wilcoxon',
      anova: '/api/analysis/anova',
      kruskal_wallis: '/api/analysis/np-kruskalwallis',
      chi_square: '/api/analysis/chisquare',
    }
    const testType = datasetOrTestType as string
    const variables = testTypeOrVariables as any
    const options = variablesOrOptions as any || {}
    return api.post(endpoints[testType] || '/api/analysis/ttest', { ...variables, ...options })
  },
}

export const correlationApi = {
  run: (variablesOrDataset: any, methodOrVariables?: any, actualMethod?: string) => {
    if (Array.isArray(variablesOrDataset)) {
      return api.post('/api/analysis/correlation', { columns: variablesOrDataset, method: methodOrVariables || 'pearson' })
    }
    // Three args: (dataset, variables, method)
    return api.post('/api/analysis/correlation', { columns: methodOrVariables as string[], method: actualMethod || 'pearson' })
  },
  partial: (variables: string[], control: string[], method = 'pearson') =>
    api.post('/api/analysis/partial-correlation', { columns: variables, control, method }),
}

export const regressionApi = {
  linear: (dependent: string, independent: string[]) =>
    api.post('/api/analysis/linear-regression', { dependent, independents: independent, method: 'enter', family: 'linear' }),
  logistic: (dependent: string, independent: string[]) =>
    api.post('/api/analysis/logistic-regression', { dependent, independents: independent, method: 'enter', family: 'logistic' }),
  multinomial: (dependent: string, independent: string[]) =>
    api.post('/api/analysis/multinomial-logistic', { dependent, independent }),
  ordinal: (dependent: string, independent: string[]) =>
    api.post('/api/analysis/ordinal-regression', { dependent, independent }),
  curvefit: (dependent: string, independent: string, models: string[]) =>
    api.post('/api/analysis/curvefit', { dependent, independent, models }),

  // ── Backward-compat shim ──
  /** @deprecated Use linear/logistic directly */
  run: (dataset: string, activeTab: string, dependent: string, independents: string[], method: string) => {
    const endpoint = activeTab === 'logistic' ? '/api/analysis/logistic-regression' : '/api/analysis/linear-regression'
    return api.post(endpoint, { dependent, independents, method: method || 'enter', family: activeTab === 'logistic' ? 'logistic' : 'linear' })
  },
}

export const survivalApi = {
  kaplanMeier: (timeOrDataset: any, statusOrTime?: string, statusOrGroup?: string, actualFactor?: string) => {
    if (actualFactor !== undefined) {
      return api.post('/api/analysis/kaplan-meier', { time_col: statusOrTime, status_col: statusOrGroup, factors: actualFactor ? [actualFactor] : [], model_type: 'kaplan-meier' })
    }
    if (statusOrGroup !== undefined) {
      return api.post('/api/analysis/kaplan-meier', { time_col: statusOrTime, status_col: statusOrGroup, model_type: 'kaplan-meier' })
    }
    return api.post('/api/analysis/kaplan-meier', { time_col: timeOrDataset, status_col: statusOrTime, model_type: 'kaplan-meier' })
  },
  coxRegression: (timeOrDataset: any, statusOrTime?: string, covariatesOrStatus?: any, actualCovariates?: string[]) => {
    if (actualCovariates !== undefined) {
      return api.post('/api/analysis/cox-regression', { time_col: statusOrTime, status_col: covariatesOrStatus, covariates: actualCovariates, model_type: 'cox' })
    }
    return api.post('/api/analysis/cox-regression', { time_col: timeOrDataset, status_col: statusOrTime, covariates: covariatesOrStatus || [], model_type: 'cox' })
  },
  lifeTables: (time: string, status: string) =>
    api.post('/api/analysis/life-tables', { time, status }),
  univariateSurvival: (time: string, status: string, variables: string[]) =>
    api.post('/api/analysis/univariate-survival', { time, status, variables }),
  aft: (time: string, status: string, covariates: string[], distribution = 'weibull') =>
    api.post('/api/analysis/aft', { time, status, covariates, distribution }),

  /** Get forest plot data from Cox model coefficients.
   *  Pass the ``data.coefficients`` array returned by ``coxRegression()``. */
  forestPlot: (coefficients: any[]) =>
    api.post('/api/analysis/cox-forest', { coefficients }),

  /** Get predicted survival curves from Cox model */
  predictSurvival: (time_col: string, status_col: string, covariates: string[]) =>
    api.post('/api/analysis/cox-predict', { time_col, status_col, covariates, model_type: 'cox' }),

  /** Get adjusted survival curves stratified by exposure variable(s) */
  adjustedSurvival: (time_col: string, status_col: string, exposure: string, adjusters: string[], adjuster_values?: Record<string, string>, exposure2?: string) =>
    api.post('/api/analysis/cox-adjusted-survival', { time_col, status_col, exposure, adjusters, adjuster_values, exposure2 }),
}

export const diagnosticApi = {
  run: (testColOrDataset: any, goldColOrTest?: string, cutoffOrGold?: any, actualCutoff?: any) => {
    if (actualCutoff !== undefined) {
      // run(dataset, test, gold, positiveCode)
      return api.post('/api/analysis/diagnostic', { test_col: goldColOrTest, gold_col: cutoffOrGold, positive_code: typeof actualCutoff === 'string' ? actualCutoff : 1 })
    }
    if (cutoffOrGold !== undefined) {
      return api.post('/api/analysis/diagnostic', { test_col: goldColOrTest, gold_col: cutoffOrGold, positive_code: 1 })
    }
    return api.post('/api/analysis/diagnostic', { test_col: testColOrDataset, gold_col: goldColOrTest, positive_code: 1 })
  },
  roc: (testCol: string, goldCol: string) =>
    api.post('/api/analysis/roc', { test_col: testCol, gold_col: goldCol }),
}

export const graphApi = {
  histogram: (columnOrDataset: any, variableOrBins?: any, binsArg?: number) => {
    if (binsArg !== undefined) {
      return api.post('/api/charts/histogram', { column: variableOrBins, bins: binsArg })
    }
    if (typeof variableOrBins === 'number') {
      return api.post('/api/charts/histogram', { column: columnOrDataset, bins: variableOrBins })
    }
    return api.post('/api/charts/histogram', { column: columnOrDataset, bins: 20 })
  },
  boxplot: (columnOrDataset: any, groupOrColumn?: string, actualGroup?: string) => {
    if (actualGroup !== undefined) {
      return api.post('/api/charts/boxplot', { column: groupOrColumn, group_col: actualGroup })
    }
    return api.post('/api/charts/boxplot', { column: columnOrDataset, group_col: groupOrColumn })
  },
  scatter: (col1OrDataset: any, col2OrCol1?: string, actualCol2?: string) => {
    if (actualCol2 !== undefined) {
      return api.post('/api/charts/scatter', { x_col: col2OrCol1, y_col: actualCol2 })
    }
    return api.post('/api/charts/scatter', { x_col: col1OrDataset, y_col: col2OrCol1 })
  },
  bar: (column: string) =>
    api.post('/api/charts/bar', { category_col: column }),
  /** @deprecated Use bar() */
  barChart: (dataset: string, column: string) =>
    api.post('/api/charts/bar', { category_col: column }),
  rocCurve: async (testColOrDataset: any, goldColOrTest?: string, posCodeOrGold?: string, actualPosCode?: string) => {
    let res: any
    if (actualPosCode !== undefined) {
      res = await api.post('/api/charts/roc-curve', { test_col: goldColOrTest, gold_col: posCodeOrGold, positive_code: actualPosCode })
    } else if (posCodeOrGold !== undefined) {
      res = await api.post('/api/charts/roc-curve', { test_col: goldColOrTest, gold_col: posCodeOrGold })
    } else {
      res = await api.post('/api/charts/roc-curve', { test_col: testColOrDataset, gold_col: goldColOrTest })
    }
    // Transform backend coordinates → Plotly traces
    const data = res.data
    if (data.coordinates) {
      return { ...res, data: { traces: [{
        type: 'scatter',
        mode: 'lines',
        name: 'ROC Curve',
        x: [0, ...data.coordinates.map((c: any) => 1 - c.fpr), 1],
        y: [0, ...data.coordinates.map((c: any) => c.tpr), 1],
        line: { shape: 'spline' },
      }, {
        type: 'scatter',
        mode: 'lines',
        name: 'Reference',
        x: [0, 1],
        y: [0, 1],
        line: { dash: 'dash', color: '#94a3b8' },
      }], layout: { title: `ROC Curve${data.auc ? ` (AUC = ${data.auc.toFixed(3)})` : ''}`, xaxis: { title: '1 - Specificity' }, yaxis: { title: 'Sensitivity', range: [0, 1] } }}}
    }
    return res
  },
  kmCurve: async (timeOrDataset: any, statusOrTime?: string, groupOrStatus?: string, actualGroup?: string) => {
    let res: any
    if (actualGroup !== undefined) {
      res = await api.post('/api/charts/km-curve', { time_col: statusOrTime, status_col: groupOrStatus, group_col: actualGroup })
    } else if (groupOrStatus !== undefined) {
      res = await api.post('/api/charts/km-curve', { time_col: statusOrTime, status_col: groupOrStatus })
    } else {
      res = await api.post('/api/charts/km-curve', { time_col: timeOrDataset, status_col: statusOrTime })
    }
    // Transform backend series → Plotly traces
    const data = res.data
    if (data.series) {
      const lr = data.log_rank_test
      const medians = data.median_survival || []
      let subtitle = ''
      if (lr && lr.p != null) {
        subtitle = `Log-rank: χ² = ${Number(lr.statistic).toFixed(2)}, p = ${lr.p < 0.001 ? '<0.001' : Number(lr.p).toFixed(4)}`
      } else {
        const medStr = medians.map((m: any) => `${m.group}: ${m.median != null ? Number(m.median).toFixed(2) : 'N/A'}`).join('; ')
        if (medStr) subtitle = `Median survival: ${medStr}`
      }
      const titleText = ['Kaplan-Meier Survival Curve']
      if (subtitle) titleText.push(`<br><span style="font-size:13px;font-weight:normal;color:#64748b">${subtitle}</span>`)
      return { ...res, data: { traces: data.series.map((s: any) => ({
        type: 'scatter',
        mode: 'lines',
        name: s.group || 'All',
        x: s.x,
        y: s.y,
        line: { shape: 'hv' },
      })), layout: { title: { text: titleText.join(''), font: { size: 16 } }, xaxis: { title: 'Time' }, yaxis: { title: 'Survival Probability', range: [0, 1] } }}}
    }
    return res
  },
  violin: (dataset: string, column: string, groupCol?: string) =>
    api.post('/api/charts/violin', { column, group_col: groupCol }),
  strip: (dataset: string, column: string, groupCol?: string) =>
    api.post('/api/charts/strip', { column, group_col: groupCol }),
  ecdf: (dataset: string, column: string, groupCol?: string) =>
    api.post('/api/charts/ecdf', { column, group_col: groupCol }),
  qq: (dataset: string, column: string, dist = 'norm') =>
    api.post('/api/charts/qq', { column, dist }),
  pareto: (dataset: string, catCol: string, valCol: string) =>
    api.post('/api/charts/pareto', { category_col: catCol, value_col: valCol }),
  clevelandDot: (dataset: string, catCol: string, valCol: string) =>
    api.post('/api/charts/cleveland-dot', { category_col: catCol, value_col: valCol }),
  lollipop: (dataset: string, catCol: string, valCol: string) =>
    api.post('/api/charts/lollipop', { category_col: catCol, value_col: valCol }),
  dumbbell: (dataset: string, catCol: string, preCol: string, postCol: string) =>
    api.post('/api/charts/dumbbell', { category_col: catCol, pre_col: preCol, post_col: postCol }),
  splom: (dataset: string, columns: string[], groupCol?: string) =>
    api.post('/api/charts/splom', { columns, group_col: groupCol }),
  controlChart: (dataset: string, valCol: string, timeCol?: string) =>
    api.post('/api/charts/control-chart', { value_col: valCol, time_col: timeCol }),
  runChart: (dataset: string, valCol: string, timeCol?: string) =>
    api.post('/api/charts/run-chart', { value_col: valCol, time_col: timeCol }),
  gantt: (dataset: string, taskCol: string, startCol: string, endCol: string) =>
    api.post('/api/charts/gantt', { task_col: taskCol, start_col: startCol, end_col: endCol }),
  calendarHeatmap: (dataset: string, dateCol: string, valCol: string) =>
    api.post('/api/charts/calendar-heatmap', { date_col: dateCol, value_col: valCol }),
  parallelCoords: (dataset: string, columns: string[], colorCol?: string) =>
    api.post('/api/charts/parallel-coordinates', { columns, color_col: colorCol }),
  radar: (dataset: string, catCol: string, valCols: string[]) =>
    api.post('/api/charts/radar', { category_col: catCol, value_cols: valCols }),
  treemap: (dataset: string, catCol: string, valCol: string, parentCol?: string) =>
    api.post('/api/charts/treemap', { category_col: catCol, value_col: valCol, parent_col: parentCol }),
  sankey: (dataset: string, srcCol: string, tgtCol: string, valCol?: string) =>
    api.post('/api/charts/sankey', { source_col: srcCol, target_col: tgtCol, value_col: valCol }),
  waterfall: (dataset: string, catCol: string, valCol: string) =>
    api.post('/api/charts/waterfall', { category_col: catCol, value_col: valCol }),
  funnel: (dataset: string, effectCol: string, precisionCol: string) =>
    api.post('/api/charts/funnel', { effect_col: effectCol, precision_col: precisionCol }),
  blandAltman: (dataset: string, col1: string, col2: string) =>
    api.post('/api/charts/bland-altman', { col1, col2 }),
  forest: (dataset: string, labelCol: string, estCol: string, loCol: string, hiCol: string) =>
    api.post('/api/charts/forest', { label_col: labelCol, estimate_col: estCol, ci_lower_col: loCol, ci_upper_col: hiCol }),
  correlationHeatmap: (dataset: string, columns: string[], method = 'pearson') =>
    api.post('/api/charts/correlation-heatmap', { columns, method }),
  swimmer: (dataset: string, patientCol: string, startCol: string, endCol: string, responseCol?: string) =>
    api.post('/api/charts/swimmer', { patient_col: patientCol, start_col: startCol, end_col: endCol, response_col: responseCol }),
  volcano: (dataset: string, effectCol: string, pvalueCol: string, labelCol?: string) =>
    api.post('/api/charts/volcano', { effect_col: effectCol, pvalue_col: pvalueCol, label_col: labelCol }),
  ridgeline: (dataset: string, valCol: string, groupCol: string) =>
    api.post('/api/charts/ridgeline', { value_col: valCol, group_col: groupCol }),
  bubble: (dataset: string, xCol: string, yCol: string, sizeCol: string, groupCol?: string) =>
    api.post('/api/charts/bubble', { x_col: xCol, y_col: yCol, size_col: sizeCol, group_col: groupCol }),
  calibration: (dataset: string, predCol: string, actualCol: string) =>
    api.post('/api/charts/calibration', { predicted_col: predCol, actual_col: actualCol }),
  pca: (dataset: string, columns: string[], groupCol?: string) =>
    api.post('/api/charts/pca', { columns, group_col: groupCol }),
  correlationNetwork: (dataset: string, columns: string[], threshold = 0.3) =>
    api.post('/api/charts/correlation-network', { columns, threshold }),
  monthlyTrend: (dataset: string, dateCol: string, valCol: string) =>
    api.post('/api/charts/monthly-trend', { date_col: dateCol, value_col: valCol }),
  aeHeatmap: (dataset: string, patientCol: string, eventCol: string, gradeCol?: string) =>
    api.post('/api/charts/ae-heatmap', { patient_col: patientCol, event_col: eventCol, grade_col: gradeCol }),
}

export const outputApi = {
  list: () => api.get('/api/output'),
  clear: () => api.delete('/api/output'),
  exportPdf: (options: { type?: string; title?: string; content?: any; columns?: string[]; rows?: number }) =>
    api.post('/api/output/export/pdf', options, { responseType: 'blob' }),
}

// ── New Analysis endpoints ───────────────────────────────────────────────

export const factorApi = {
  factorAnalysis: (columns: string[], nFactors = 2, rotation = 'varimax') =>
    api.post('/api/analysis/factor', { columns, n_factors: nFactors, rotation }),
  reliability: (columns: string[]) =>
    api.post('/api/analysis/reliability', { columns }),
}

export const anovaApi = {
  twoway: (dependent: string, factor1: string, factor2: string) =>
    api.post('/api/analysis/anova-twoway', { dependent, factor1, factor2 }),
}

export const exportApi = {
  excel: (columns?: string[]) =>
    api.post('/api/data/download/excel', { columns }, { responseType: 'blob' }),
  pdf: (options: { type?: string; title?: string; content?: any; columns?: string[]; rows?: number }) =>
    api.post('/api/output/export/pdf', options, { responseType: 'blob' }),
  sav: () => api.post('/api/data/download/sav', {}, { responseType: 'blob' }),
  dta: () => api.post('/api/data/download/dta', {}, { responseType: 'blob' }),
  xpt: () => api.post('/api/data/download/xpt', {}, { responseType: 'blob' }),
  multiformat: (format: string) =>
    api.post('/api/data/download/multiformat', { format }, { responseType: 'blob' }),
}

export const mixedModelApi = {
  run: (dv: string, fixed: string[], random: string[], family = 'gaussian') =>
    api.post('/api/analysis/mixed-model', { dv, fixed, random, family }),
}

export const clusterApi = {
  run: (columns: string[], method = 'kmeans', nClusters = 3) =>
    api.post('/api/analysis/cluster', { columns, method, n_clusters: nClusters }),
}

export const powerApi = {
  run: (params: { test: string; n?: number; effect_size?: number; power?: number; alpha?: number; k?: number }) =>
    api.post('/api/analysis/power', params),
}

export const aiApi = {
  scan: () => api.get('/api/ai/scan'),
  parse: (question: string, maxTests = 5) =>
    api.post('/api/ai/parse', { question, max_tests: maxTests }),
  execute: (plan: any, autoFallback = true) =>
    api.post('/api/ai/execute', { plan, auto_fallback: autoFallback }),
  synthesize: (question: string, results: any[]) =>
    api.post('/api/ai/synthesize', { question, results }),
  analyze: (question: string, autoFallback = true, maxTests = 5) =>
    api.post('/api/ai/analyze', { question, auto_fallback: autoFallback, max_tests: maxTests }),
  history: (limit = 20) => api.get(`/api/ai/history?limit=${limit}`),
  getHistory: (id: string) => api.get(`/api/ai/history/${id}`),
}

export default api
