/**
 * Enhanced Output Store — tree-structured analysis output with persistence.
 * 
 * Stores analysis results with hierarchical organization:
 *   Session (root)
 *     ├── Descriptive Analyses
 *     │     ├── Frequencies: diagnosis
 *     │     └── Descriptives: age, bmi
 *     ├── Group Comparisons
 *     │     ├── T-test: age ~ sex
 *     │     └── ANOVA: age ~ diagnosis
 *     └── Survival Analysis
 *           ├── Kaplan-Meier
 *           └── Cox Regression
 */

import { TreeNode } from 'antd/es/tree-select'
import logStore from './logStore'

function logStoreOp(action: string, detail: string, data?: any) {
  logStore.addEntry('info', 'outputStore', `${action}: ${detail}`, data ? JSON.stringify(data).slice(0, 500) : '')
}

export interface OutputEntry {
  id: string
  type: string  // frequencies, ttest, anova, kaplan_meier, etc.
  category: string  // descriptive, compare, regression, survival, diagnostic, correlation, graph
  title: string
  result: any
  chart_data?: any
  interpretation?: string
  timestamp: string
  parent_id?: string   // for tree hierarchy
}

export interface OutputNode {
  key: string
  title: string
  type?: string  // 'category' | 'entry'
  entry?: OutputEntry
  children?: OutputNode[]
}

type Listener = () => void

class OutputStore {
  private entries: OutputEntry[] = []
  private selectedIds: Set<string> = new Set()
  private compareMode = false
  private highlightId: string | null = null
  private listeners: Set<Listener> = new Set()

  // Category tree structure
  readonly categories: Record<string, { label: string; icon: string }> = {
    data: { label: 'Data', icon: 'TableOutlined' },
    descriptive: { label: 'Descriptive', icon: 'FundOutlined' },
    compare: { label: 'Comparisons', icon: 'ExperimentOutlined' },
    nonparametric: { label: 'Nonparametric', icon: 'ExperimentOutlined' },
    regression: { label: 'Regression', icon: 'NodeIndexOutlined' },
    survival: { label: 'Survival', icon: 'ApartmentOutlined' },
    correlation: { label: 'Correlation', icon: 'NodeIndexOutlined' },
    diagnostic: { label: 'Diagnostic', icon: 'ExperimentOutlined' },
    factor: { label: 'Factor Analysis', icon: 'RadarChartOutlined' },
    graph: { label: 'Graphs', icon: 'BarChartOutlined' },
  }

  getEntries(): OutputEntry[] {
    return [...this.entries]
  }

  getEntry(id: string): OutputEntry | undefined {
    return this.entries.find(e => e.id === id)
  }

  addEntry(typeOrCat: string, title: string, result: any): OutputEntry {
    logStoreOp('addEntry', `${typeOrCat}: ${title}`, { hasResult: !!result, resultKeys: result ? Object.keys(result).slice(0, 10) : [] })
    // Determine category from endpoint type
    const categoryMap: Record<string, string> = {
      frequencies: 'descriptive',
      descriptive: 'descriptive',
      crosstab: 'descriptive',
      explore: 'descriptive',
      means: 'descriptive',
      ttest: 'compare',
      'ttest-paired': 'compare',
      anova: 'compare',
      'anova-twoway': 'compare',
      chisquare: 'compare',
      'np-mannwhitney': 'nonparametric',
      'np-wilcoxon': 'nonparametric',
      'np-kruskalwallis': 'nonparametric',
      'np-friedman': 'nonparametric',
      'np-sign': 'nonparametric',
      'np-mcnemar': 'nonparametric',
      'np-chisquare': 'nonparametric',
      'np-binomial': 'nonparametric',
      'np-runs': 'nonparametric',
      'np-ks': 'nonparametric',
      correlation: 'correlation',
      'partial-correlation': 'correlation',
      'linear-regression': 'regression',
      'logistic-regression': 'regression',
      'kaplan-meier': 'survival',
      'cox-regression': 'survival',
      'cox-predict': 'survival',
      diagnostic: 'diagnostic',
      roc: 'diagnostic',
      factor: 'factor',
      reliability: 'factor',
    }

    // If the type is already a top-level category, use it directly
    const knownCategories = new Set(['data', 'descriptive', 'compare', 'nonparametric',
      'regression', 'survival', 'diagnostic', 'correlation', 'factor', 'graph'])
    const category = knownCategories.has(typeOrCat) ? typeOrCat : (categoryMap[typeOrCat] || 'descriptive')

    const entry: OutputEntry = {
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
      type: typeOrCat,
      category,
      title,
      result,
      timestamp: new Date().toLocaleTimeString(),
    }

    this.entries = [entry, ...this.entries]
    this.highlightId = entry.id
    this.notify()
    return entry
  }

  setHighlight(id: string | null): void {
    this.highlightId = id
    this.notify()
  }

  consumeHighlight(): string | null {
    const id = this.highlightId
    this.highlightId = null
    return id
  }

  /** Build tree nodes from stored entries for the outline pane */
  buildTreeNodes(): OutputNode[] {
    const grouped: Record<string, OutputEntry[]> = {}
    for (const entry of this.entries) {
      const cat = entry.category || 'descriptive'
      if (!grouped[cat]) grouped[cat] = []
      grouped[cat].push(entry)
    }

    const nodes: OutputNode[] = []
    for (const [cat, catEntries] of Object.entries(grouped)) {
      const catInfo = this.categories[cat] || { label: cat, icon: 'FileTextOutlined' }
      nodes.push({
        key: `cat-${cat}`,
        title: catInfo.label,
        type: 'category',
        children: catEntries.map(entry => ({
          key: entry.id,
          title: entry.title.length > 40 ? entry.title.slice(0, 40) + '…' : entry.title,
          type: 'entry' as const,
          entry,
        })),
      })
    }
    return nodes
  }

  getSelectedIds(): string[] {
    return [...this.selectedIds]
  }

  getSelectedEntries(): OutputEntry[] {
    return this.getSelectedIds().map(id => this.getEntry(id)).filter(Boolean) as OutputEntry[]
  }

  isCompareMode(): boolean {
    return this.compareMode
  }

  isSelected(id: string): boolean {
    return this.selectedIds.has(id)
  }

  appendResult(opts: { type: string; title: string; data: any; status: string }): OutputEntry {
    logStoreOp('appendResult', `${opts.type}: ${opts.title}`, { status: opts.status })
    return this.addEntry(opts.type, opts.title, { data: opts.data, status: opts.status })
  }

  removeEntry(id: string): void {
    logStoreOp('removeEntry', id)
    this.entries = this.entries.filter(e => e.id !== id)
    this.notify()
  }

  clearAll(): void {
    logStoreOp('clearAll', `count=${this.entries.length}`)
    this.entries = []
    this.notify()
  }

  toggleSelect(id: string): void {
    if (this.selectedIds.has(id)) this.selectedIds.delete(id)
    else this.selectedIds.add(id)
    logStoreOp('toggleSelect', id, { selected: this.selectedIds.has(id) })
    this.notify()
  }

  clearSelection(): void {
    logStoreOp('clearSelection', `had=${this.selectedIds.size}`)
    this.selectedIds.clear()
    this.notify()
  }

  selectAll(): void {
    logStoreOp('selectAll', `count=${this.entries.length}`)
    this.entries.forEach(e => this.selectedIds.add(e.id))
    this.notify()
  }

  setCompareMode(v: boolean): void {
    logStoreOp('setCompareMode', String(v))
    this.compareMode = v
    if (!v) this.selectedIds.clear()
    this.notify()
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  private notify(): void {
    this.listeners.forEach(fn => fn())
  }
}

const outputStore = new OutputStore()
export default outputStore
