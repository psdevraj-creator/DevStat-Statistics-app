import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../api/client'

export interface EligibilityResult {
  eligible: boolean
  blocked: boolean
  reason?: string
  details?: string
  suggested_alternatives?: string[]
  alternative_ranked?: {
    preferred: string[]
    acceptable: string[]
    advanced: string[]
  }
  help_terms?: string[]
}

export interface EligibilityParams {
  analysis: string
  var_types?: Record<string, string>
  n_groups?: number
  n_items?: number
  n_vars?: number
  n_rows?: number
  n_x_categories?: number
  n_y_categories?: number
  has_time?: boolean
  has_event?: boolean
  is_paired?: boolean
}

const EMPTY: EligibilityResult = { eligible: true, blocked: false }

export function useEligibilityCheck(params: EligibilityParams | null): EligibilityResult {
  const [result, setResult] = useState<EligibilityResult>(EMPTY)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()
  const lastKeyRef = useRef('')

  useEffect(() => {
    if (!params) {
      setResult(EMPTY)
      return
    }

    const key = JSON.stringify(params)
    if (key === lastKeyRef.current) return
    lastKeyRef.current = key

    if (timerRef.current) clearTimeout(timerRef.current)

    timerRef.current = setTimeout(async () => {
      try {
        const res = await api.post('/api/eligibility/check', params)
        setResult(res.data || EMPTY)
      } catch {
        setResult(EMPTY)
      }
    }, 200)

    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [params])

  return result
}
