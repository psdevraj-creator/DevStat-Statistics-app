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
  const traces: PlotlyTrace[] = series.map((s) => {
    switch (chartType) {
      case 'histogram':
        return {
          type: 'bar',
          x: s.bins || [],
          y: s.counts || [],
          name: s.label || s.group || '',
        }

      case 'scatter':
        return {
          type: 'scatter',
          mode: 'markers',
          x: s.x || s.categories || [],
          y: s.y || s.values || [],
          name: s.label || s.group || '',
        }

      case 'boxplot':
        return {
          type: 'box',
          y: s.values || [],
          name: s.label || s.group || '',
          boxpoints: 'outliers',
        }

      case 'bar':
      default:
        return {
          type: 'bar',
          x: (s.categories || []).map((c: string) => String(c).trim()),
          y: s.values || [],
          name: s.label || s.group || '',
          error_y:
            s.errors && s.errors.length > 0
              ? { type: 'data', array: s.errors, visible: true }
              : undefined,
        }
    }
  })

  const tickangle =
    overrides?.tickangle ??
    ((traces[0]?.x?.length || 0) > 8 ? -45 : 0)

  const layout: Record<string, any> = {
    title: overrides?.title || `${capitalize(chartType)} Chart`,
    xaxis: {
      title: overrides?.xTitle || '',
      tickangle,
      automargin: true,
    },
    yaxis: { title: overrides?.yTitle || 'Value' },
    barmode:
      chartType !== 'scatter' && traces.length > 1
        ? overrides?.barmode || 'group'
        : undefined,
    margin: { l: 60, r: 30, t: 50, b: tickangle !== 0 ? 120 : 60 },
  }

  return { traces, layout }
}

function capitalize(s: string): string {
  if (!s) return ''
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export { capitalize }
