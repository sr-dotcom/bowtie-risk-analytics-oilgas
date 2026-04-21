import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useNarrativeSynthesis } from '@/hooks/useNarrativeSynthesis'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const VALID_INPUT = {
  top_barrier_name: 'PSV',
  top_barrier_risk_band: 'HIGH' as const,
  top_barrier_probability: 0.85,
  shap_top_features: [],
  rag_incident_contexts: [],
  total_barriers: 5,
  high_risk_count: 2,
  top_event: 'Loss of Containment',
  similar_incidents_count: 3,
}

const SUCCESS_RESPONSE = {
  narrative: 'The barrier shows elevated risk.',
  model: 'claude-haiku-4-5-20251001',
  generated_at: '2026-04-20T00:00:00.000Z',
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useNarrativeSynthesis', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('initial state has all null values and isLoading=false', () => {
    const { result } = renderHook(() => useNarrativeSynthesis())
    expect(result.current.state.narrative).toBeNull()
    expect(result.current.state.isLoading).toBe(false)
    expect(result.current.state.error).toBeNull()
    expect(result.current.state.generatedAt).toBeNull()
  })

  it('200 response sets narrative and generatedAt, clears error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => SUCCESS_RESPONSE,
    }))

    const { result } = renderHook(() => useNarrativeSynthesis())
    await act(async () => {
      await result.current.trigger(VALID_INPUT)
    })

    expect(result.current.state.narrative).toBe(SUCCESS_RESPONSE.narrative)
    expect(result.current.state.generatedAt).toBe(SUCCESS_RESPONSE.generated_at)
    expect(result.current.state.error).toBeNull()
    expect(result.current.state.isLoading).toBe(false)
  })

  it('504 response sets error=timeout', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 504 }))

    const { result } = renderHook(() => useNarrativeSynthesis())
    await act(async () => {
      await result.current.trigger(VALID_INPUT)
    })

    expect(result.current.state.error).toBe('timeout')
    expect(result.current.state.narrative).toBeNull()
    expect(result.current.state.isLoading).toBe(false)
  })

  it('502 response sets error=quality_gate', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 502 }))

    const { result } = renderHook(() => useNarrativeSynthesis())
    await act(async () => {
      await result.current.trigger(VALID_INPUT)
    })

    expect(result.current.state.error).toBe('quality_gate')
    expect(result.current.state.narrative).toBeNull()
  })

  it('reset() returns to initial state after a successful trigger', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => SUCCESS_RESPONSE,
    }))

    const { result } = renderHook(() => useNarrativeSynthesis())
    await act(async () => {
      await result.current.trigger(VALID_INPUT)
    })
    expect(result.current.state.narrative).not.toBeNull()

    act(() => {
      result.current.reset()
    })

    expect(result.current.state.narrative).toBeNull()
    expect(result.current.state.error).toBeNull()
    expect(result.current.state.isLoading).toBe(false)
    expect(result.current.state.generatedAt).toBeNull()
  })
})
