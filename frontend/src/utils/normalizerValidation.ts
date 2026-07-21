/**
 * NormalizedResult schema validation.
 * 
 * Every analyzed result passes through validateNormalizedResult()
 * before reaching the UI. This guarantees the renderer contract:
 *   { tables: any[], charts: any[], narrative: string, warnings: string[] }
 */

import type { NormalizedResult } from './responseNormalizer'

export interface ValidationReport extends NormalizedResult {
  /** True if the result conforms to the renderer contract */
  valid: boolean
  /** Specific field-level validation errors */
  errors: string[]
}

/**
 * Validates a NormalizedResult against the renderer contract.
 * Never throws — always returns a valid-shaped result.
 * 
 * If the input is already valid, it returns as-is with valid=true.
 * If invalid, it coerces fields to correct types and adds errors.
 */
export function validateNormalizedResult(
  result: NormalizedResult,
  context?: string
): ValidationReport {
  const errors: string[] = []
  const prefix = context ? `[${context}] ` : ''

  // ── tables: always an array ────────────────────────────────
  if (!Array.isArray(result.tables)) {
    errors.push(`${prefix}tables must be an array, got ${typeof result.tables}`)
  }

  // ── charts: always an array ────────────────────────────────
  if (!Array.isArray(result.charts)) {
    errors.push(`${prefix}charts must be an array, got ${typeof result.charts}`)
  }

  // ── narrative: always a string ──────────────────────────────
  if (typeof result.narrative !== 'string') {
    errors.push(`${prefix}narrative must be a string, got ${typeof result.narrative}`)
  }

  // ── warnings: always an array (of strings) ──────────────────
  if (!Array.isArray(result.warnings)) {
    errors.push(`${prefix}warnings must be an array, got ${typeof result.warnings}`)
  } else {
    const nonStrings = result.warnings.filter(w => typeof w !== 'string')
    if (nonStrings.length > 0) {
      errors.push(`${prefix}warnings contains ${nonStrings.length} non-string element(s)`)
    }
  }

  // ── Build validated result (coerce types) ───────────────────
  const validated: NormalizedResult & { valid: boolean; errors: string[] } = {
    tables: Array.isArray(result.tables) ? result.tables : [],
    charts: Array.isArray(result.charts) ? result.charts : [],
    narrative: typeof result.narrative === 'string' ? result.narrative : '',
    warnings: Array.isArray(result.warnings)
      ? result.warnings.filter(w => typeof w === 'string')
      : [],
    valid: errors.length === 0,
    errors,
    rawDeprecated: result.rawDeprecated,
  }

  return validated
}
