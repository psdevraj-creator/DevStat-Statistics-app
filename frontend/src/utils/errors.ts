/**
 * Format FastAPI validation errors into a user-readable string.
 *
 * FastAPI 422 responses return ``detail`` as an array of field-level
 * errors like ``[{loc: ["body","field"], msg: "..."}]``.  This utility
 * collapses them into a single readable message so the user sees what
 * field is wrong rather than ``[object Object]``.
 */
export function formatApiError(err: any, fallback: string): string {
  // FastAPI 422: detail is an array of {loc, msg}
  const detail = err?.response?.data?.detail
  if (Array.isArray(detail)) {
    const fields = detail
      .map((d: any) => {
        const field = (d.loc || []).slice(1).join('.') || 'body'
        return `${field}: ${d.msg}`
      })
      .join('; ')
    return `${fallback}: ${fields}`
  }

  // Regular string error or HTTPException detail
  if (typeof detail === 'string') {
    return `${fallback}: ${detail}`
  }

  return fallback
}
