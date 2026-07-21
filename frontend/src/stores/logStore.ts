/**
 * Log Store — records API errors, rendering failures, and warnings
 * during the user session for later diagnosis.
 *
 * Entries are persisted in ``localStorage`` so they survive page reloads.
 * The store holds up to 200 entries; old entries are trimmed automatically.
 */

export interface LogEntry {
  id: string
  timestamp: string
  type: 'api' | 'render' | 'warning' | 'info'
  source: string
  message: string
  detail?: string
  context?: Record<string, any>
}

type Listener = () => void

const MAX_ENTRIES = 200
const STORAGE_KEY = 'devstat_logs'

class LogStore {
  private entries: LogEntry[] = []
  private listeners: Set<Listener> = new Set()

  constructor() {
    this.load()
  }

  addEntry(
    type: LogEntry['type'],
    source: string,
    message: string,
    detail?: string,
    context?: Record<string, any>,
  ): LogEntry {
    const entry: LogEntry = {
      id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      timestamp: new Date().toISOString(),
      type,
      source,
      message,
      detail,
      context,
    }
    this.entries.push(entry)
    if (this.entries.length > MAX_ENTRIES) {
      this.entries = this.entries.slice(-MAX_ENTRIES)
    }
    this.save()
    this.notify()
    return entry
  }

  getEntries(): LogEntry[] {
    return [...this.entries]
  }

  getByType(type: LogEntry['type']): LogEntry[] {
    return this.entries.filter(e => e.type === type)
  }

  clear(): void {
    this.entries = []
    this.save()
    this.notify()
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  private notify(): void {
    this.listeners.forEach(fn => fn())
  }

  private save(): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.entries))
    } catch { /* storage full or unavailable */ }
  }

  private load(): void {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) {
        this.entries = JSON.parse(raw)
        if (!Array.isArray(this.entries)) this.entries = []
      }
    } catch { this.entries = [] }
  }
}

const logStore = new LogStore()
export default logStore
