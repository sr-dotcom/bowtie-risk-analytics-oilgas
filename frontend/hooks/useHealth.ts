'use client'

import { useEffect, useState } from 'react'

interface ModelInfo {
  name: string
  loaded: boolean
}

export interface HealthResponse {
  status: string
  models: Record<string, ModelInfo>
  rag: { corpus_size: number }
  uptime_seconds: number
}

export function useHealth(): {
  health: HealthResponse | null
  loading: boolean
  error: string | null
} {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    fetch('/api/health')
      .then((r) => {
        if (!r.ok) throw new Error(`Health check failed: ${r.status}`)
        return r.json() as Promise<HealthResponse>
      })
      .then((h) => {
        if (!cancelled) setHealth(h)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(String(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  return { health, loading, error }
}
