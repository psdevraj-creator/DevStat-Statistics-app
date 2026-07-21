import type { OutputEntry } from '../stores/outputStore'

export interface NormalizedResult {
  tables: any[]
  charts: any[]
  narrative: string
  warnings: string[]
  rawDeprecated: any
  _blocked?: any
}

function fmtInterpretation(val: any): string {
  if (typeof val === 'string') return val
  if (val === null || val === undefined) return ''
  return String(val)
}

function isObject(v: any): boolean {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

/** Extract a metadata table from any result object */
function extractTable(data: any, type: string): any[] {
  if (!data) return []

  // Per-column descriptives: {_columns: [...], col: {n, mean, ...}}
  if (data._columns && Array.isArray(data._columns)) {
    return data._columns.map((col: string) => {
      const stats = data[col] || {}
      return { Variable: col, ...stats, _key: col }
    })
  }

  // Means: {overall, groups: [{name, mean, sd, n, ci_lower, ci_upper}]}
  if (data.groups && Array.isArray(data.groups) && data.groups.length > 0) {
    const rows = data.groups.map((g: any, i: number) => ({
      Group: g.name || `Group ${i}`,
      N: g.n,
      Mean: g.mean,
      SD: g.sd,
      'CI Lower': g.ci_lower,
      'CI Upper': g.ci_upper,
      _key: `g${i}`,
    }))
    if (data.overall) rows.unshift({ Group: 'Overall', N: data.overall.n, Mean: data.overall.mean, SD: data.overall.sd, 'CI Lower': data.overall.ci_lower, 'CI Upper': data.overall.ci_upper, _key: 'overall' })
    return rows
  }

  // Mixed Model: {fixed_effects: [{term, estimate, std_error, t_value, p_value}]}
  if (data.fixed_effects && Array.isArray(data.fixed_effects)) {
    return data.fixed_effects.map((fe: any, i: number) => ({ Term: fe.term || fe.name || `term${i}`, Estimate: fe.estimate, 'Std Error': fe.std_error, 't value': fe.t_value, 'p value': fe.p_value, _key: `fe${i}` }))
  }

  // Cluster: {cluster_centers: [{cluster, size, means}]}
  if (data.cluster_centers && Array.isArray(data.cluster_centers)) {
    return data.cluster_centers.map((cc: any, i: number) => {
      const row: any = { Cluster: cc.cluster || i + 1, Size: cc.size, _key: `cc${i}` }
      if (cc.means && typeof cc.means === 'object') Object.assign(row, cc.means)
      return row
    })
  }

  // Kaplan-Meier median survival
  if (data.median_survival && Array.isArray(data.median_survival)) {
    const rows = data.median_survival.map((m: any, i: number) => ({
      Group: m.group || `Group ${i}`,
      Median: m.median,
      'CI Lower': m.ci_lower,
      'CI Upper': m.ci_upper,
      _key: `med${i}`,
    }))
    if (data.chisq !== undefined && data.chisq !== null) {
      rows.push({ Group: 'Log-rank χ²', Median: data.chisq, 'CI Lower': '', 'CI Upper': '', _key: 'chisq' })
    }
    if (data.p_value !== undefined && data.p_value !== null) {
      rows.push({ Group: 'p-value', Median: data.p_value, 'CI Lower': '', 'CI Upper': '', _key: 'pval' })
    }
    return rows
  }

  // Crosstab: list-of-arrays format [["", "col1", "col2"], ["row1", 5, 3]]
  if (Array.isArray(data) && data.length > 0 && Array.isArray(data[0])) {
    const headers = data[0] as string[]
    const rows = data.slice(1).map((row: any[], i: number) => {
      const obj: any = { _key: `row${i}` }
      headers.forEach((h: string, j: number) => { obj[h || 'row_label'] = row[j] })
      return obj
    })
    return rows
  }

  // Series-based with top-level metadata
  const metaKeys = ['n', 'p_value', 'chi2', 'chisq', 'df', 't_statistic', 'F', 'cohens_d', 'cramers_v', 'r_squared', 'adj_r_squared', 'auc', 'alpha', 'W', 'V', 'effect_size', 'mean', 'sd', 'median', 'n1', 'n2', 'mean1', 'mean2', 'n_total', 'n_events', 'n_censored', 'concordance', 'power', 'sig_level', 'n_obs', 'AIC', 'BIC', 'tot_withinss', 'betweenss', 'n_items', 'n_factors', 'n_groups', 'n_clusters', 'n_discordant', 'n_positive', 'n_negative']
  const row: any = { _key: 'metadata' }
  for (const key of metaKeys) {
    if (data[key] !== undefined && data[key] !== null && data[key] !== '' && !(typeof data[key] === 'number' && isNaN(data[key]))) {
      row[key] = typeof data[key] === 'number' ? Number(Number(data[key]).toFixed(4)) : data[key]
    }
  }
  if (Object.keys(row).length > 1) return [row]

  return []
}

/** Build chart object from chart_type + series */
function buildChart(data: any): any[] {
  if (!data || !data.chart_type || !data.series) return []
  const series = Array.isArray(data.series) ? data.series : [data.series]
  if (series.length === 0) return []
  const chart: any = {
    type: data.chart_type,
    title: data.test || data.chart_type,
    data: { series },
  }
  if (data.chart_type === 'roc_curve' && data.auc) chart.auc = data.auc
  return [chart]
}

function normalizeError(type: string, data: any): NormalizedResult {
  const detail = data?.detail ?? ''
  const errMsg = data?.error ?? data?.message ?? 'Unknown error'
  return { tables: [], charts: [], narrative: '', warnings: [`${type}: ${detail || errMsg}`], rawDeprecated: data }
}

export function normalizeResult(type: string, result: any): NormalizedResult {
  if (!result) {
    return { tables: [], charts: [], narrative: '', warnings: ['No result data'], rawDeprecated: null }
  }

  if (result.blocked === true) {
    return {
      tables: [], charts: [], narrative: result.reason || 'Analysis blocked.',
      warnings: [result.reason || 'Analysis blocked.'], rawDeprecated: result, _blocked: result,
    }
  }

  if (result?.detail || result?.error) {
    return normalizeError(type, result)
  }

  const data = result?.data ?? result?.results ?? result
  const charts = buildChart(data)
  const tables = extractTable(data, type)
  const narrative = fmtInterpretation(data?.interpretation) || charts.map((c: any) => c.title).join(', ')
  const warnings = data?._r_stderr ? [data._r_stderr] : []

  return { tables, charts, narrative, warnings, rawDeprecated: data }
}

export function safeKeys(obj: any): string[] {
  if (obj === null || obj === undefined) return []
  if (typeof obj !== 'object') return []
  return Object.keys(obj)
}

export function toArray(val: any): any[] {
  if (Array.isArray(val)) return val
  if (val === null || val === undefined) return []
  return [val]
}
