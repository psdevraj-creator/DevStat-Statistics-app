/**
 * Shared chart-mapping utility — single source of truth for
 * ChartResponse → Plotly traces + layout.
 *
 * Both ChartRenderer and GraphsPage consume this, so the mapping
 * contract is defined once and tested once.
 */

export interface ChartSeries {
  label?: string
  group?: string
  categories?: string[]
  values?: number[]
  errors?: number[]
  bins?: number[]
  counts?: number[]
  x?: number[]
  y?: number[]
}

export interface PlotlyTrace {
  type: string
  x?: any[]
  y?: any[]
  name?: string
  mode?: string
  marker?: any
  error_y?: any
  boxpoints?: string
  text?: string[]
  textposition?: string
  [key: string]: any
}

export interface PlotlyChart {
  traces: PlotlyTrace[]
  layout: Record<string, any>
}

/**
 * Map a ChartResponse `series` array to Plotly traces and layout.
 *
 * @param series   The `series` array from a ChartResponse.
 * @param chartType One of "bar", "histogram", "boxplot", "scatter".
 * @param overrides Optional layout overrides (title, axis labels, etc.).
 */
export function seriesToPlotlyChart(
  series: ChartSeries[],
  chartType: string,
  overrides?: {
    title?: string
    xTitle?: string
    yTitle?: string
    barmode?: 'group' | 'stack' | undefined
    tickangle?: number
  }
): PlotlyChart {
  const ct = (chartType || 'bar').toLowerCase()
  const traces: PlotlyTrace[] = series.map((s) => {
    switch (ct) {
      case 'histogram':
        return {
          type: 'bar',
          x: s.bins || [],
          y: s.counts || [],
          name: s.label || s.group || '',
          text: s.counts ? s.counts.map(String) : undefined,
          textposition: 'none',
        }

      case 'scatter':
        return {
          type: 'scatter',
          mode: 'markers',
          x: s.x || s.categories || [],
          y: s.y || s.values || [],
          name: s.label || s.group || '',
          marker: { color: '#005eb8', size: 8, opacity: 0.75 },
        }

      case 'violin':
        return {
          type: 'violin',
          y: s.values || [],
          name: s.label || s.group || '',
          box: { visible: true },
          meanline: { visible: true },
          fillcolor: 'rgba(0,94,184,0.35)',
          line: { color: '#005eb8' },
        }

      case 'boxplot':
        return {
          type: 'box',
          y: s.values || [],
          name: s.label || s.group || '',
          boxpoints: 'outliers',
          marker: { color: '#005eb8' },
          line: { color: '#003d8b' },
        }

      case 'line':
        return {
          type: 'scatter',
          mode: 'lines',
          x: s.x || s.categories || [],
          y: s.y || s.values || [],
          name: s.label || s.group || '',
          line: { color: '#005eb8', width: 2.5 },
        }

      case 'bar':
      default:
        return {
          type: 'bar',
          x: (s.categories || []).map((c: string) => String(c).trim()),
          y: s.values || [],
          name: s.label || s.group || '',
          marker: { color: '#005eb8', opacity: 0.85, line: { color: '#003d8b', width: 1 } },
          // Only draw error bars when the data actually provides them (default off).
          error_y:
            s.errors && s.errors.length > 0 && s.errors.some((e) => e != null && e > 0)
              ? { type: 'data', array: s.errors, visible: true, color: '#003d8b', thickness: 1.2 }
              : undefined,
        }
    }
  })

  const tickangle =
    overrides?.tickangle ??
    ((traces[0]?.x?.length || 0) > 8 ? -35 : 0)

  const layout: Record<string, any> = {
    title: {
      text: overrides?.title || `${capitalize(ct)} Chart`,
      font: { size: 17, color: '#1a1a2e' },
    },
    font: { family: 'Segoe UI, sans-serif' },
    xaxis: {
      title: overrides?.xTitle || '',
      tickangle,
      automargin: true,
      gridcolor: '#eef2f7',
      zeroline: false,
      showline: true,
      linecolor: '#d7dee8',
    },
    yaxis: {
      title: overrides?.yTitle || 'Value',
      gridcolor: '#eef2f7',
      zeroline: false,
      showline: true,
      linecolor: '#d7dee8',
    },
    barmode:
      ct !== 'scatter' && ct !== 'line' && traces.length > 1
        ? overrides?.barmode || 'group'
        : undefined,
    margin: { l: 64, r: 32, t: 56, b: tickangle !== 0 ? 120 : 64 },
    paper_bgcolor: '#ffffff',
    plot_bgcolor: '#ffffff',
    showlegend: traces.length > 1,
    legend: { orientation: 'h', y: -0.18 },
    hoverlabel: { font: { family: 'Segoe UI, sans-serif', size: 12 } },
  }

  return { traces, layout }
}

function capitalize(s: string): string {
  if (!s) return ''
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export { capitalize }
