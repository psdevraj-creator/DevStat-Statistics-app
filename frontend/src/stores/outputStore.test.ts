import { describe, it, expect } from 'vitest'
import outputStore from './outputStore'

describe('OutputStore', () => {
  it('addEntry stores an entry with correct category', () => {
    outputStore.addEntry('ttest', 'T-test: age ~ sex', { p: 0.03 })
    const entries = outputStore.getEntries()
    expect(entries.length).toBeGreaterThanOrEqual(1)
    const entry = entries[0]
    expect(entry.type).toBe('ttest')
    expect(entry.category).toBe('compare')
    expect(entry.title).toBe('T-test: age ~ sex')
  })

  it('addEntry with reliability type stores under factor category', () => {
    outputStore.clearAll()
    outputStore.addEntry('reliability', 'Cronbach Alpha', { alpha: 0.85 })
    const entries = outputStore.getEntries()
    const entry = entries[0]
    expect(entry.category).toBe('factor')
  })

  it('appendResult stores entry with ai_assistant type', () => {
    outputStore.clearAll()
    outputStore.appendResult({ type: 'ai_assistant', title: 'Test result', data: { p: 0.01 }, status: 'success' })
    const entries = outputStore.getEntries()
    expect(entries.length).toBe(1)
    expect(entries[0].type).toBe('ai_assistant')
    expect(entries[0].title).toBe('Test result')
  })

  it('clearAll removes all entries', () => {
    outputStore.clearAll()
    const entries = outputStore.getEntries()
    expect(entries.length).toBe(0)
  })
})
