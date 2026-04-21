'use client'

import { useState, useCallback } from 'react'
import type { NarrativeSynthesisInput } from '@/lib/types'

export type { NarrativeSynthesisInput }

export interface NarrativeSynthesisState {
  narrative: string | null
  isLoading: boolean
  error: 'timeout' | 'quality_gate' | 'unavailable' | 'unknown' | null
  generatedAt: string | null
}

const INITIAL_STATE: NarrativeSynthesisState = {
  narrative: null,
  isLoading: false,
  error: null,
  generatedAt: null,
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useNarrativeSynthesis(): {
  state: NarrativeSynthesisState
  trigger: (input: NarrativeSynthesisInput) => Promise<void>
  reset: () => void
} {
  const [state, setState] = useState<NarrativeSynthesisState>(INITIAL_STATE)

  const trigger = useCallback(async (input: NarrativeSynthesisInput): Promise<void> => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }))

    try {
      const controller = new AbortController()
      // 15s client timeout — longer than backend's 10s so backend 504 is reachable
      const timeoutId = setTimeout(() => controller.abort(), 15000)

      const res = await fetch('/api/narrative-synthesis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
        signal: controller.signal,
      })
      clearTimeout(timeoutId)

      if (res.ok) {
        const data = await res.json() as { narrative: string; model: string; generated_at: string }
        setState({
          narrative: data.narrative,
          isLoading: false,
          error: null,
          generatedAt: data.generated_at,
        })
      } else if (res.status === 504) {
        setState({ narrative: null, isLoading: false, error: 'timeout', generatedAt: null })
      } else if (res.status === 502) {
        setState({ narrative: null, isLoading: false, error: 'quality_gate', generatedAt: null })
      } else if (res.status === 503) {
        setState({ narrative: null, isLoading: false, error: 'unavailable', generatedAt: null })
      } else {
        setState({ narrative: null, isLoading: false, error: 'unknown', generatedAt: null })
      }
    } catch {
      setState({ narrative: null, isLoading: false, error: 'unknown', generatedAt: null })
    }
  }, [])

  const reset = useCallback((): void => {
    setState(INITIAL_STATE)
  }, [])

  return { state, trigger, reset }
}
