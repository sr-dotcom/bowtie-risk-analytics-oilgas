'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { explainCascading } from '@/lib/api'
import type { ExplainCascadingResponse, Scenario } from '@/lib/types'

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Fires /explain-cascading when all three inputs are non-null.
 * Cancels any in-flight request via AbortController when inputs change.
 *
 * Designed to be called inside BowtieProvider (no useBowtieContext dependency).
 *
 * @param conditioningBarrierId - The barrier assumed to have failed.
 * @param targetBarrierId       - The barrier being inspected.
 * @param scenario              - Full scenario context for the backend.
 */
export function useExplainCascading(
  conditioningBarrierId: string | null,
  targetBarrierId: string | null,
  scenario: Scenario | null,
): {
  explanation: ExplainCascadingResponse | null
  loading: boolean
  error: string | null
  narrativeUnavailable: boolean
} {
  const [explanation, setExplanation] = useState<ExplainCascadingResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!conditioningBarrierId || !targetBarrierId || !scenario) return

    // Cancel any in-flight request before firing a new one.
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)
    setExplanation(null)

    explainCascading(
      {
        conditioning_barrier_id: conditioningBarrierId,
        target_barrier_id: targetBarrierId,
        bowtie_context: scenario,
      },
      controller.signal,
    )
      .then((result) => {
        if (!controller.signal.aborted) {
          setExplanation(result)
          setLoading(false)
        }
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : String(err))
          setLoading(false)
        }
      })

    return () => {
      controller.abort()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conditioningBarrierId, targetBarrierId])

  const narrativeUnavailable = explanation?.narrative_unavailable ?? false

  return { explanation, loading, error, narrativeUnavailable }
}
