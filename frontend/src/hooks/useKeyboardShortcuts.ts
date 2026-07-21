/**
 * useKeyboardShortcuts — cross-platform keyboard shortcuts hook
 *
 * Supports Ctrl (Windows/Linux) and Cmd (macOS) modifier detection.
 * Scoped: global (always active), dataset (active when dataset is present),
 * module (active on specific page/sub-view), with input-field exceptions.
 *
 * Usage:
 *   const { shortcuts, showHelp, setShowHelp, getShortcutDisplay, shortcutHelpItems } =
 *     useKeyboardShortcuts(config)
 */

import { useEffect, useState, useCallback, useRef } from 'react'

// ── Types ────────────────────────────────────────────────────────────────

export type ShortcutScope = 'global' | 'dataset' | 'module'

export interface ShortcutAction {
  /** Keyboard combination, e.g. 'Ctrl+S', 'Ctrl+Shift+S', 'F1', '?' */
  keys: string
  /** Scope for scoping behaviour */
  scope: ShortcutScope
  /** Human-readable action label for help modal */
  label: string
  /** Handler function */
  handler: (e: KeyboardEvent) => void
  /** If true, shortcut is disabled (greyed out in help, silently ignored) */
  disabled?: boolean
  /** Optional group label for help modal categorisation */
  group?: string
}

export interface UseKeyboardShortcutsConfig {
  shortcuts: ShortcutAction[]
  /** When true, ALL global shortcuts are suspended (use for modals, etc.) */
  globalSuspend?: boolean
}

export interface UseKeyboardShortcutsReturn {
  /** The full shortcut config (useful for debugging) */
  shortcuts: ShortcutAction[]
  /** Whether the help modal should be visible */
  showHelp: boolean
  /** Toggle help modal visibility */
  setShowHelp: (v: boolean) => void
  /** Get human-readable display string for a shortcut key, e.g. "⌘S" or "Ctrl+S" */
  getShortcutDisplay: (keys: string) => string
  /** Pre-computed help items grouped by scope, ready for rendering */
  shortcutHelpItems: ShortcutHelpGroup[]
}

export interface ShortcutHelpItem {
  keys: string
  keysDisplay: string
  label: string
  scope: ShortcutScope
  disabled: boolean
  group?: string
}

export interface ShortcutHelpGroup {
  scope: ShortcutScope
  scopeLabel: string
  items: ShortcutHelpItem[]
}

// ─── Platform detection ──────────────────────────────────────────────────

function isMac(): boolean {
  if (typeof navigator === 'undefined') return false
  return /Mac|iPod|iPhone|iPad/.test(navigator.platform || '')
}

function getModKey(): 'Ctrl' | '⌘' {
  return isMac() ? '⌘' : 'Ctrl'
}

function getModKeyName(): 'Meta' | 'Control' {
  return isMac() ? 'Meta' : 'Control'
}

// ─── Normalise shorthand keys to event.code / event.key matching ────────

interface ParsedShortcut {
  ctrl: boolean
  shift: boolean
  alt: boolean
  /** Key name for comparison (lowercase for letters, exact for specials) */
  key: string
  /** Original input string */
  original: string
}

function parseShortcut(keys: string): ParsedShortcut {
  const parts = keys.split('+').map(s => s.trim())
  const parsed: ParsedShortcut = {
    ctrl: false,
    shift: false,
    alt: false,
    key: '',
    original: keys,
  }

  for (const part of parts) {
    switch (part) {
      case 'Ctrl':
      case 'Cmd':
        parsed.ctrl = true
        break
      case 'Shift':
        parsed.shift = true
        break
      case 'Alt':
        parsed.alt = true
        break
      default:
        parsed.key = part
    }
  }

  return parsed
}

function eventMatchesShortcut(e: KeyboardEvent, parsed: ParsedShortcut): boolean {
  // Modifier check
  const modKeyName = getModKeyName()
  const ctrlOrCmd = e.getModifierState(modKeyName) || e.ctrlKey
  const shift = e.shiftKey
  const alt = e.altKey

  if (parsed.ctrl && !ctrlOrCmd) return false
  if (parsed.shift && !shift) return false
  if (parsed.alt && !alt) return false
  if (!parsed.ctrl && ctrlOrCmd) return false

  // Key match
  const expectedKey = parsed.key
  if (expectedKey === 'Tab') return e.key === 'Tab'
  if (expectedKey === 'F1') return e.key === 'F1' || e.code === 'F1'
  if (expectedKey === '?') return e.key === '?' || (e.key === '/' && shift)
  if (expectedKey === 'Enter') return e.key === 'Enter'
  if (expectedKey === 'Escape') return e.key === 'Escape'

  // For regular keys, compare lowercase
  return e.key.toLowerCase() === expectedKey.toLowerCase()
}

// ─── Build display string ────────────────────────────────────────────────

const DISPLAY_OVERRIDES: Record<string, string> = {
  Tab: 'Tab',
  F1: 'F1',
  '?': 'Shift+/',
  Enter: 'Enter',
  Escape: 'Esc',
}

export function getShortcutDisplay(keys: string): string {
  const parsed = parseShortcut(keys)
  const parts: string[] = []

  if (parsed.ctrl && isMac()) {
    // macOS display: ⌘ prefix
    if (parsed.shift) parts.push('⇧')
    if (parsed.alt) parts.push('⌥')
    parts.push('⌘')
    parts.push(DISPLAY_OVERRIDES[parsed.key] || parsed.key)
  } else {
    // Windows/Linux: Ctrl+ prefix
    parts.push(getModKey())
    if (parsed.shift) parts.push('Shift')
    if (parsed.alt) parts.push('Alt')
    parts.push(DISPLAY_OVERRIDES[parsed.key] || parsed.key.toUpperCase())
  }

  return parts.join('+')
}

// ─── Scope helpers ───────────────────────────────────────────────────────

const SCOPE_LABELS: Record<ShortcutScope, string> = {
  global: 'Global',
  dataset: 'Dataset',
  module: 'Module',
}

const SCOPE_ORDER: ShortcutScope[] = ['global', 'dataset', 'module']

// ─── Hook ────────────────────────────────────────────────────────────────

export function useKeyboardShortcuts(
  config: UseKeyboardShortcutsConfig
): UseKeyboardShortcutsReturn {
  const { shortcuts, globalSuspend = false } = config
  const [showHelp, setShowHelp] = useState(false)
  const parsedRef = useRef<Map<string, ParsedShortcut>>(new Map())

  // Pre-parse once when shortcuts change
  useEffect(() => {
    const map = new Map<string, ParsedShortcut>()
    for (const s of shortcuts) {
      map.set(s.keys, parseShortcut(s.keys))
    }
    parsedRef.current = map
  }, [shortcuts])

  // ── Keydown handler ──────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Help shortcut (? or F1) is always active regardless of suspend
      const isHelp = e.key === 'F1' || e.key === '?' || (e.key === '/' && e.shiftKey)
      if (isHelp) {
        e.preventDefault()
        setShowHelp(prev => !prev)
        return
      }

      // If global suspend is active, skip ALL shortcuts (except help)
      if (globalSuspend) return

      // Check if focus is inside an input/textarea — skip global shortcuts
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase()
      const isInput = tag === 'input' || tag === 'textarea' || tag === 'select'
      const isContentEditable = (e.target as HTMLElement)?.isContentEditable

      for (const shortcut of shortcuts) {
        // Skip disabled shortcuts silently
        if (shortcut.disabled) continue

        // For the help shortcut, we already handled it above
        if (shortcut.keys === '?' || shortcut.keys === 'F1') continue

        const parsed = parsedRef.current.get(shortcut.keys)
        if (!parsed) continue

        if (!eventMatchesShortcut(e, parsed)) continue

        // Scope checking
        if (shortcut.scope === 'global' && (isInput || isContentEditable)) {
          // Skip global shortcuts when focus is in an input field
          continue
        }

        e.preventDefault()
        e.stopPropagation()
        shortcut.handler(e)
        return
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [shortcuts, globalSuspend])

  // ── Build help items ─────────────────────────────────────────────────
  const shortcutHelpItems: ShortcutHelpGroup[] = (() => {
    const grouped = new Map<ShortcutScope, ShortcutHelpItem[]>()
    for (const scope of SCOPE_ORDER) grouped.set(scope, [])

    for (const s of shortcuts) {
      const item: ShortcutHelpItem = {
        keys: s.keys,
        keysDisplay: getShortcutDisplay(s.keys),
        label: s.label,
        scope: s.scope,
        disabled: s.disabled ?? false,
        group: s.group,
      }
      const arr = grouped.get(s.scope)!
      arr.push(item)
    }

    return SCOPE_ORDER
      .filter(scope => (grouped.get(scope)?.length ?? 0) > 0)
      .map(scope => ({
        scope,
        scopeLabel: SCOPE_LABELS[scope],
        items: grouped.get(scope)!,
      }))
  })()

  return {
    shortcuts,
    showHelp,
    setShowHelp,
    getShortcutDisplay,
    shortcutHelpItems,
  }
}

export default useKeyboardShortcuts
