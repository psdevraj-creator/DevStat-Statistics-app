/**
 * Comprehensive Frontend Logger — logs every significant event.
 *
 * Usage:
 *   import { log } from '../utils/logger'
 *   log.api('POST /api/analysis/ttest', { dependent: 'age' })
 *   log.render('KM_graph', { has_series: true })
 *   log.state('outputStore', 'addEntry', { type: 'ttest' })
 *   log.error('Something failed', err)
 */

import logStore from '../stores/logStore'

let seq = 0

function makeEntry(
  type: 'api' | 'render' | 'warning' | 'info',
  source: string,
  message: string,
  detail?: string,
  context?: Record<string, any>,
) {
  seq++
  if (typeof context !== 'object' || context === null) context = {}
  context._seq = seq
  context._ts = Date.now()
  return logStore.addEntry(type, source, message, detail, context)
}

export const log = {
  /** Log an API call — request details */
  api(method: string, url: string, body?: any) {
    makeEntry('info', `${method} ${url}`, 'API_REQ', body ? JSON.stringify(body).slice(0, 1000) : '', {
      method, url, body,
    })
  },

  /** Log an API response */
  apiResp(method: string, url: string, status: number, elapsed: number, data?: any) {
    makeEntry('info', `${method} ${url}`, `API_RESP ${status} (${elapsed}ms)`,
      data ? JSON.stringify(data).slice(0, 1000) : '', { status, elapsed })
  },

  /** Log a render event */
  render(source: string, props: Record<string, any>) {
    makeEntry('render', source, 'RENDER', '', props)
  },

  /** Log a state change */
  state(store: string, action: string, payload?: any) {
    makeEntry('info', store, `STATE ${action}`,
      payload ? JSON.stringify(payload).slice(0, 500) : '', { action, payload })
  },

  /** Log a warning */
  warn(source: string, message: string, context?: Record<string, any>) {
    makeEntry('warning', source, message, '', context)
  },

  /** Log an error */
  error(source: string, err: any, context?: Record<string, any>) {
    const msg = err?.message || err?.toString() || 'Unknown error'
    const stack = err?.stack?.slice(0, 1000) || ''
    makeEntry('api', source, `ERROR: ${msg}`, stack, { ...context, error: String(err) })
  },

  /** Log user action (button click, navigation, input) */
  action(name: string, details?: Record<string, any>) {
    makeEntry('info', 'user_action', name, '', details)
  },

  /** Log a route navigation */
  navigation(from: string, to: string) {
    makeEntry('info', 'navigation', `${from} → ${to}`, '', { from, to })
  },
}
