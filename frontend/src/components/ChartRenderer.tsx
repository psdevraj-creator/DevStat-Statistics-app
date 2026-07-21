import React from 'react'
import { Card, Button, Space, Typography } from 'antd'
import { BarChartOutlined, TableOutlined } from '@ant-design/icons'
import Plot from '../utils/plotlyWrap'
import { seriesToPlotlyChart } from '../utils/chartMapping'
import logStore from '../stores/logStore'

// Runtime guard: verify imports are callable components/functions, not objects

const { Text } = Typography

interface ChartRendererProps {
  /** The chart data object from the backend */
  data: any
  /** Optional title override */
  title?: string
  /** Show table/chart toggle */
  showToggle?: boolean
}

const plotlyConfig = {
  displayModeBar: true, displaylogo: false, responsive: true,
  modeBarButtonsToRemove: ['sendDataToCloud', 'lasso2d', 'select2d'],
  toImageButtonOptions: { format: 'png', filename: 'devstat-chart', width: 1200, height: 800 },
}

/**
 * ChartRenderer
 *
 * Renders backend API response data as a Plotly chart.
 *
 * **Dispatch order** (contract-based with heuristic fallback):
 *   1. ``data.chart_type`` discriminator — preferred path, populated by
 *      backend Pydantic models (FrequencyResponse, ChartResponse, Crosstab).
 *   2. Shape heuristics — fallback when ``chart_type`` is absent (legacy
 *      responses or debug payloads).
 *
 * Supported chart_type values:
 *   - ``"frequencies"`` → bar chart (``{table: [...]}``)
 *   - ``"histogram"``   → histogram (``{series: [{bins, counts}]}``)
 *   - ``"boxplot"``     → box plot
 *   - ``"scatter"``     → scatter plot
 *   - ``"bar"``         → bar chart (``{series: [{categories, values}]}``)
 *   - ``"crosstab"``    → grouped bar (``{table, row, col, ...}``)
 *
 * Falls back to JSON dump when neither discriminator nor heuristic matches.
 */
const ChartRenderer: React.FC<ChartRendererProps> = ({ data: rawData, title, showToggle = true }) => {
  const [viewMode, setViewMode] = React.useState<'chart' | 'table'>('chart')
  // Normalise: R auto-unbox can turn a 1-row data.frame into an object
  const data = React.useMemo(() => {
    if (!rawData) return rawData
    const d = { ...rawData }
    if (d.table != null && !Array.isArray(d.table)) d.table = [d.table]
    if (d.series != null && !Array.isArray(d.series)) d.series = [d.series]
    return d
  }, [rawData])

  if (!data) return null

  const buildPlotly = (): { traces: any[]; layout: any } | null => {
    const ct = data.chart_type as string | undefined

    // ── Contract-based dispatch (preferred) ────────────────────────────
    if (ct) {
      switch (ct) {
        case 'frequencies':
          return frequenciesToPlotly()
        case 'bar':
        case 'histogram':
        case 'boxplot':
        case 'scatter':
          return chartSeriesToPlotly(ct)
        case 'crosstab':
          return crosstabToPlotly()
        default:
          // Unknown chart_type — try heuristics below
          break
      }
    }

    // ── Heuristic fallback (legacy / debug payloads) ───────────────────
    return heuristicDispatch()
  }

  // ── chart_type-aware renderers ──────────────────────────────────────

  const frequenciesToPlotly = () => {
    const rows = data.table
    if (!rows || !Array.isArray(rows) || rows.length === 0) {
      logStore.addEntry('render', 'ChartRenderer', 'frequenciesToPlotly: no table data', '', { chart_type: data.chart_type, has_table: !!data.table })
      return null
    }
    const categories = rows.map((r: any) => String(r.value ?? '').trim())
    const counts = rows.map((r: any) => r.count ?? 0)
    const limit = Math.min(categories.length, 30)
    const truncated = categories.length > limit
    const maxCount = Math.max(...counts)
    return {
      traces: [{
        type: 'bar' as const,
        x: categories.slice(0, limit),
        y: counts.slice(0, limit),
        marker: {
          color: counts.slice(0, limit).map((c: number) =>
            c === maxCount ? '#005eb8' : '#7eb8da'
          ),
        },
        text: counts.slice(0, limit).map(String),
        textposition: 'outside' as const,
        name: data.column || 'Frequency',
      }],
      layout: {
        title: title || `Frequency: ${data.column || ''}`,
        xaxis: { title: data.column || 'Value', tickangle: categories.length > 8 ? -45 : 0, automargin: true },
        yaxis: { title: 'Count' },
        margin: { l: 60, r: 30, t: 50, b: categories.length > 8 ? 120 : 60 },
        annotations: truncated ? [{
          text: `Showing top ${limit} of ${categories.length} categories`,
          x: 0.5, y: -0.2, xref: 'paper', yref: 'paper',
          showarrow: false, font: { size: 10, color: '#94a3b8' },
        }] : [],
      },
    }
  }

  const chartSeriesToPlotly = (ct: string) => {
    if (!data.series || !Array.isArray(data.series) || data.series.length === 0) return null
    const { traces, layout } = seriesToPlotlyChart(data.series, ct, {
      title: title || undefined,
      xTitle: data.category_col || data.column || undefined,
      yTitle: data.value_col || undefined,
    })
    return { traces, layout }
  }

  const crosstabToPlotly = () => {
    // Crosstab response: { table: [[...]], row, col, ... }
    if (!data.row || !data.col) return null
    const tbl = data.table
    if (!Array.isArray(tbl) || tbl.length < 2) return null
    const [header, ...body] = tbl
    const colLabels = (header as any[]).slice(1).map(String)
    const rowLabels = body.map((r: any[]) => String(r[0]))
    const traces = colLabels.map((cl: string, ci: number) => ({
      type: 'bar' as const,
      x: rowLabels,
      y: body.map((r: any[]) => Number(r[ci + 1]) || 0),
      name: cl,
    }))
    return {
      traces,
      layout: {
        title: title || `Crosstab: ${data.row} × ${data.col}`,
        xaxis: { title: data.row },
        yaxis: { title: 'Count' },
        barmode: 'group' as const,
      },
    }
  }

  const heuristicDispatch = () => {
    // ── Frequencies: { table: [{value, count, percent, ...}] } ──
    if (data.table && Array.isArray(data.table) && data.table.length > 0 && data.table[0]?.value !== undefined) {
      return frequenciesToPlotly()
    }
    // ── Charts API: { series: [{categories, values, label, errors}] } ──
    if (data.series && Array.isArray(data.series) && data.series.length > 0) {
      return chartSeriesToPlotly(data.chart_type || 'bar')
    }
    // ── Raw categories + values ──
    if (data.categories && data.values) {
      return {
        traces: [{ type: 'bar' as const, x: data.categories.map((c: string) => String(c).trim()), y: data.values, name: 'Value' }],
        layout: { title: title || 'Chart', xaxis: { title: 'Category' }, yaxis: { title: 'Value' } },
      }
    }
    // ── Crosstabs: { row, col, ... } with crosstab_table or table ──
    if ((data.crosstab_table || data.table) && data.row && data.col) {
      return crosstabToPlotly()
    }
    return null
  }

  const plotly = buildPlotly()
  const hasTable = data.table && Array.isArray(data.table)

  const renderTable = () => {
    if (!hasTable) return null
    return (
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ background: '#f1f5f9', borderBottom: '2px solid #e2e8f0' }}>
            {Object.keys(data.table[0] || {}).map(key => (
              <th key={key} style={{ padding: '8px 12px', textAlign: 'left', textTransform: 'uppercase', fontSize: 11, color: '#64748b' }}>
                {key.replace(/_/g, ' ')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.table.map((row: any, i: number) => (
            <tr key={i} style={{ borderBottom: '1px solid #e2e8f0' }}>
              {Object.values(row).map((val: any, j: number) => (
                <td key={j} style={{ padding: '6px 12px' }}>
                  {val !== null && val !== undefined ? String(val) : '-'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    )
  }

  if (!plotly && !hasTable) {
    // No renderable chart shape found — show a clean message, not raw JSON
    return (
      <Card size="small" style={{ background: '#fafbfc', textAlign: 'center', padding: 32 }}>
        <Text type="secondary">
          {data?.chart_type
            ? `Chart type "${data.chart_type}" is not yet supported by the renderer.`
            : 'Unable to render chart from the provided data.'}
        </Text>
        <div style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            Expected: chart_type + series, or table array with value/count keys.
          </Text>
        </div>
      </Card>
    )
  }

  return (
    <div>
      {showToggle && (
        <div style={{ marginBottom: 12, display: 'flex', gap: 8 }}>
          <Button
            size="small"
            type={viewMode === 'chart' ? 'primary' : 'default'}
            icon={<BarChartOutlined />}
            onClick={() => setViewMode('chart')}
          >
            Chart
          </Button>
          <Button
            size="small"
            type={viewMode === 'table' ? 'primary' : 'default'}
            icon={<TableOutlined />}
            onClick={() => setViewMode('table')}
          >
            Table
          </Button>
        </div>
      )}

      {viewMode === 'chart' && plotly && (
        <Card size="small" style={{ background: '#fafbfc', maxWidth: 850, marginLeft: 'auto', marginRight: 'auto' }}>
          <Plot
            data={plotly.traces}
            layout={{
              ...plotly.layout,
              font: { family: 'Inter, sans-serif' },
              paper_bgcolor: '#fff',
              plot_bgcolor: '#fafbfc',
              autosize: true,
              height: 400,
            }}
            config={plotlyConfig}
            useResizeHandler
            style={{ width: '100%' }}
          />
        </Card>
      )}

      {viewMode === 'table' && (
        <Card size="small">
          {renderTable()}
        </Card>
      )}
    </div>
  )
}

export default ChartRenderer
