'use client'

import { useState, useRef, useCallback } from 'react'
import { predictCascading, rankTargets } from '@/lib/api'
import type { BarrierPrediction, CascadingRequest, RankedBarrier, Scenario } from '@/lib/types'

// ---------------------------------------------------------------------------
// State union
// ---------------------------------------------------------------------------

export type AnalysisState =
  | { status: 'idle' }
  | { status: 'loading' }
  | {
      status: 'success'
      predictions: BarrierPrediction[]
      ranked: RankedBarrier[]
      explanationAvailable: boolean
    }
  | { status: 'error'; message: string }

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Fires /predict-cascading and /rank-targets in parallel, then merges results.
 * Debounced at 300ms to prevent rapid conditioning-barrier clicks from
 * flooding the backend.
 *
 * Designed to be called inside BowtieProvider (no useBowtieContext dependency).
 */
export function useAnalyzeCascading(): {
  analyze: (scenario: Scenario, conditioningBarrierId: string) => void
  state: AnalysisState
} {
  const [state, setState] = useState<AnalysisState>({ status: 'idle' })
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const analyze = useCallback((scenario: Scenario, conditioningBarrierId: string) => {
    if (timerRef.current) clearTimeout(timerRef.current)

    timerRef.current = setTimeout(async () => {
      setState({ status: 'loading' })
      try {
        const req: CascadingRequest = { scenario, conditioning_barrier_id: conditioningBarrierId }
        const [predictRes, rankRes] = await Promise.all([
          predictCascading(req),
          rankTargets(req),
        ])

        // Sort predictions by composite_risk_score from ranking, falling back to
        // y_fail_probability when a target_barrier_id is missing from ranked list.
        const rankMap = new Map(
          rankRes.ranked_barriers.map((r) => [r.target_barrier_id, r.composite_risk_score]),
        )
        const sorted = [...predictRes.predictions].sort((a, b) => {
          const scoreA = rankMap.get(a.target_barrier_id) ?? a.y_fail_probability
          const scoreB = rankMap.get(b.target_barrier_id) ?? b.y_fail_probability
          return scoreB - scoreA
        })

        setState({
          status: 'success',
          predictions: sorted,
          ranked: rankRes.ranked_barriers,
          explanationAvailable: !predictRes.explanation_unavailable,
        })
      } catch (err) {
        setState({
          status: 'error',
          message: err instanceof Error ? err.message : String(err),
        })
      }
    }, 300)
  }, [])

  return { analyze, state }
}
