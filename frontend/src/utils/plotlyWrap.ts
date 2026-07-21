/**
 * Compatibility wrapper for react-plotly.js
 *
 * react-plotly.js v3.0.0 has ESM exports but Vite's dev server sometimes
 * resolves it as a CJS shim (``{default: Component, __esModule: true}``).
 * This wrapper handles both resolution modes so Plot is always a component.
 *
 * If neither resolution path yields a callable component, the app throws
 * immediately with a descriptive error so the mis-resolution is caught at
 * module load time rather than surfacing as React error #130 later.
 */
import PlotlyModule from 'react-plotly.js'

function resolvePlot(): any {
  if (PlotlyModule == null) {
    throw new Error(
      '[plotlyWrap] react-plotly.js resolved to null/undefined. ' +
      'Check that the package is installed: npm ls react-plotly.js'
    )
  }

  // Direct function export (prod build with proper ESM)
  if (typeof PlotlyModule === 'function') {
    return PlotlyModule
  }

  // CJS shim wrapper (dev server): { default: Component, __esModule: true }
  if (
    typeof PlotlyModule === 'object' &&
    PlotlyModule !== null &&
    typeof (PlotlyModule as any).default === 'function'
  ) {
    return (PlotlyModule as any).default
  }

  // Neither path worked — fail loudly with diagnostics
  const keys = Object.keys(PlotlyModule as object)
  const sampleValue =
    keys.length > 0
      ? typeof (PlotlyModule as any)[keys[0]]
      : '(no enumerable keys)'

  throw new Error(
    '[plotlyWrap] Cannot resolve react-plotly.js as a callable component.\n' +
    '  Module type:      ' + typeof PlotlyModule + '\n' +
    '  Module keys:      ' + (keys.length ? keys.join(', ') : '(none)') + '\n' +
    '  First key type:   ' + sampleValue + '\n' +
    '  Has default?:     ' + ('default' in (PlotlyModule as object)) + '\n' +
    '  Default type:     ' + typeof (PlotlyModule as any).default + '\n' +
    '  Likely cause: react-plotly.js module resolution mismatch.\n' +
    '  Check: npm ls react-plotly.js && npm ls plotly.js\n' +
    '  The project expects react-plotly.js@^3.0.0 and plotly.js@^3.6.0.'
  )
}

const Plot = resolvePlot()
export default Plot
