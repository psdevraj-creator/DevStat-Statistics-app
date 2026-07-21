/**
 * KeyboardShortcutsHelp — accessible modal listing all keyboard shortcuts
 *
 * Features:
 * - Search/filter by label or key
 * - Grouped by scope (Global, Dataset, Module)
 * - Platform-appropriate key names (⌘ vs Ctrl)
 * - Focus trap, Esc to close, aria labels
 */

import React, { useEffect, useRef, useState, useCallback } from 'react'
import { Input, Typography } from 'antd'
import { CloseOutlined, SearchOutlined } from '@ant-design/icons'
import type {
  ShortcutHelpItem,
  ShortcutHelpGroup,
} from '../hooks/useKeyboardShortcuts'
import { getShortcutDisplay } from '../hooks/useKeyboardShortcuts'

const { Text } = Typography

// ── Theme colours matching DevStat's design token ───────────────────────

const COLORS = {
  primary: '#005eb8',
  bg: '#fff',
  bgOverlay: 'rgba(0, 0, 0, 0.45)',
  border: '#e2e8f0',
  text: '#1e293b',
  textSecondary: '#64748b',
  highlight: '#eff6ff',
  scopeBadge: {
    global: { bg: '#eff6ff', text: '#005eb8' },
    dataset: { bg: '#f0fdf4', text: '#16a34a' },
    module: { bg: '#fefce8', text: '#ca8a04' },
  },
}

// ── Props ────────────────────────────────────────────────────────────────

interface KeyboardShortcutsHelpProps {
  visible: boolean
  onClose: () => void
  items: ShortcutHelpGroup[]
}

// ── Focus trap hook ─────────────────────────────────────────────────────

function useFocusTrap(active: boolean) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!active) return

    const el = ref.current
    if (!el) return

    // Focus the first focusable element inside the modal
    const focusable = el.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    if (focusable.length > 0) {
      focusable[0].focus()
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return

      const first = focusable[0]
      const last = focusable[focusable.length - 1]

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault()
          last?.focus()
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault()
          first?.focus()
        }
      }
    }

    el.addEventListener('keydown', handleKeyDown)
    return () => el.removeEventListener('keydown', handleKeyDown)
  }, [active])

  return ref
}

// ── Scope badge ─────────────────────────────────────────────────────────

const ScopeBadge: React.FC<{ scope: string }> = ({ scope }) => {
  const c = COLORS.scopeBadge[scope as keyof typeof COLORS.scopeBadge] || COLORS.scopeBadge.global
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        padding: '1px 8px',
        borderRadius: 10,
        background: c.bg,
        color: c.text,
        whiteSpace: 'nowrap',
        letterSpacing: 0.3,
        textTransform: 'uppercase',
      }}
    >
      {scope}
    </span>
  )
}

// ── Key cap rendering ───────────────────────────────────────────────────

const KeyCap: React.FC<{ label: string }> = ({ label }) => {
  // Split by '+' to render each piece as a separate key cap
  const parts = label.split('+')
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, flexWrap: 'wrap' }}>
      {parts.map((part, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span style={{ color: COLORS.textSecondary, fontSize: 13 }}>+</span>}
          <kbd
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              minWidth: 26,
              height: 24,
              padding: '0 6px',
              fontSize: 12,
              fontWeight: 600,
              fontFamily: "'SF Mono', 'Fira Code', 'Consolas', monospace",
              color: COLORS.text,
              background: '#f8fafc',
              border: `1px solid ${COLORS.border}`,
              borderRadius: 4,
              boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
              lineHeight: 1,
            }}
          >
            {part}
          </kbd>
        </React.Fragment>
      ))}
    </span>
  )
}

// ── Component ───────────────────────────────────────────────────────────

const KeyboardShortcutsHelp: React.FC<KeyboardShortcutsHelpProps> = ({
  visible,
  onClose,
  items,
}) => {
  const [filter, setFilter] = useState('')
  const trapRef = useFocusTrap(visible)

  // Reset filter on open
  useEffect(() => {
    if (visible) setFilter('')
  }, [visible])

  // Esc to close
  useEffect(() => {
    if (!visible) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [visible, onClose])

  // Close on overlay click
  const handleOverlayClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) onClose()
    },
    [onClose]
  )

  if (!visible) return null

  const filterLower = filter.toLowerCase().trim()
  const hasFilter = filterLower.length > 0

  // Filter items
  const filteredGroups = items
    .map(group => {
      const filteredItems = hasFilter
        ? group.items.filter(
            item =>
              item.label.toLowerCase().includes(filterLower) ||
              item.keysDisplay.toLowerCase().includes(filterLower) ||
              item.keys.toLowerCase().includes(filterLower)
          )
        : group.items
      return { ...group, items: filteredItems }
    })
    .filter(g => g.items.length > 0)

  const totalShortcuts = items.reduce((sum, g) => sum + g.items.length, 0)
  const filteredCount = filteredGroups.reduce((sum, g) => sum + g.items.length, 0)

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1050,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: COLORS.bgOverlay,
      }}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts help"
    >
      <div
        ref={trapRef}
        style={{
          background: COLORS.bg,
          borderRadius: 12,
          boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
          width: '90%',
          maxWidth: 640,
          maxHeight: '85vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          outline: 'none',
        }}
        role="document"
        tabIndex={-1}
      >
        {/* ── Header ─────────────────────────────────────────────── */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 20px 12px',
            borderBottom: `1px solid ${COLORS.border}`,
          }}
        >
          <Text strong style={{ fontSize: 16, color: COLORS.text }}>
            Keyboard Shortcuts
          </Text>
          <button
            onClick={onClose}
            aria-label="Close shortcuts help"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 4,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 4,
              color: COLORS.textSecondary,
              fontSize: 18,
            }}
            onMouseEnter={e => (e.currentTarget.style.background = '#f1f5f9')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <CloseOutlined />
          </button>
        </div>

        {/* ── Search ─────────────────────────────────────────────── */}
        <div style={{ padding: '12px 20px' }}>
          <Input
            placeholder="Search shortcuts…"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            prefix={<SearchOutlined style={{ color: COLORS.textSecondary }} />}
            allowClear
            aria-label="Filter keyboard shortcuts"
            style={{ borderRadius: 6 }}
          />
        </div>

        {/* ── Shortcuts list ─────────────────────────────────────── */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '0 20px 20px',
          }}
        >
          {hasFilter && (
            <Text
              style={{
                display: 'block',
                fontSize: 12,
                color: COLORS.textSecondary,
                marginBottom: 12,
              }}
            >
              {filteredCount} of {totalShortcuts} shortcuts match
            </Text>
          )}

          {filteredGroups.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '40px 20px',
                color: COLORS.textSecondary,
              }}
            >
              <Text type="secondary">No shortcuts match "{filter}"</Text>
            </div>
          ) : (
            filteredGroups.map(group => (
              <div key={group.scope} style={{ marginBottom: 20 }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    marginBottom: 8,
                  }}
                >
                  <ScopeBadge scope={group.scopeLabel.toLowerCase()} />
                  <Text strong style={{ fontSize: 13, color: COLORS.text }}>
                    {group.scopeLabel}
                  </Text>
                </div>
                <div
                  style={{
                    border: `1px solid ${COLORS.border}`,
                    borderRadius: 8,
                    overflow: 'hidden',
                  }}
                >
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <tbody>
                      {group.items.map((item, idx) => {
                        // Group separator logic: if there's a group label and
                        // this is the first item or the group label changed
                        const showGroupLabel =
                          item.group &&
                          (idx === 0 || group.items[idx - 1]?.group !== item.group)
                        return (
                          <React.Fragment key={`${item.keys}-${idx}`}>
                            {showGroupLabel && (
                              <tr>
                                <td
                                  colSpan={2}
                                  style={{
                                    padding: '4px 12px',
                                    background: '#f8fafc',
                                    borderBottom: `1px solid ${COLORS.border}`,
                                  }}
                                >
                                  <Text
                                    style={{
                                      fontSize: 11,
                                      fontWeight: 600,
                                      color: COLORS.textSecondary,
                                      textTransform: 'uppercase',
                                      letterSpacing: 0.5,
                                    }}
                                  >
                                    {item.group}
                                  </Text>
                                </td>
                              </tr>
                            )}
                            <tr
                              style={{
                                background:
                                  item.disabled
                                    ? '#fafafa'
                                    : idx % 2 === 0
                                    ? '#fff'
                                    : '#fafafa',
                                opacity: item.disabled ? 0.5 : 1,
                              }}
                            >
                              <td
                                style={{
                                  padding: '8px 12px',
                                  borderBottom: `1px solid ${COLORS.border}`,
                                  width: '40%',
                                }}
                              >
                                <KeyCap label={item.keysDisplay} />
                              </td>
                              <td
                                style={{
                                  padding: '8px 12px',
                                  borderBottom: `1px solid ${COLORS.border}`,
                                  color: item.disabled ? COLORS.textSecondary : COLORS.text,
                                  fontSize: 13,
                                }}
                              >
                                {item.label}
                                {item.disabled && (
                                  <Text
                                    style={{
                                      marginLeft: 8,
                                      fontSize: 11,
                                      color: COLORS.textSecondary,
                                    }}
                                  >
                                    (disabled)
                                  </Text>
                                )}
                              </td>
                            </tr>
                          </React.Fragment>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ))
          )}

          {/* ── Footer tip ──────────────────────────────────────── */}
          <div
            style={{
              marginTop: 8,
              padding: '8px 12px',
              background: '#f8fafc',
              borderRadius: 6,
              fontSize: 12,
              color: COLORS.textSecondary,
              lineHeight: 1.5,
            }}
          >
            <Text style={{ fontSize: 12, color: COLORS.textSecondary }}>
              💡 Press <kbd style={kbdInlineStyle}>?</kbd> or <kbd style={kbdInlineStyle}>F1</kbd> at any time to toggle this dialog.
              Press <kbd style={kbdInlineStyle}>Esc</kbd> to close.
            </Text>
          </div>
        </div>
      </div>
    </div>
  )
}

const kbdInlineStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  minWidth: 22,
  height: 20,
  padding: '0 5px',
  fontSize: 11,
  fontWeight: 600,
  fontFamily: "'SF Mono', 'Fira Code', 'Consolas', monospace",
  color: '#1e293b',
  background: '#f8fafc',
  border: '1px solid #e2e8f0',
  borderRadius: 3,
  boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
  lineHeight: 1,
}

export default KeyboardShortcutsHelp
