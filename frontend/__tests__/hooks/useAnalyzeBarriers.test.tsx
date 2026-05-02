import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useAnalyzeBarriers } from '@/hooks/useAnalyzeBarriers'
import type { Barrier } from '@/lib/types'

// ---------------------------------------------------------------------------
// Mock predictCascading — hoisted before module resolution
// ---------------------------------------------------------------------------

const mockPredictCascading = vi.hoisted(() => vi.fn())

vi.mock('@/lib/api', () => ({
  predictCascading: mockPredictCascading,
}))

// ---------------------------------------------------------------------------
// Mock useBowtieContext so we control barriers / scenario state without a
// full provider tree. These mutable variables are written in beforeEach so
// each test starts from a clean, predictable state.
// ---------------------------------------------------------------------------

const mockSetIsAnalyzing = vi.fn()
const mockSetAnalysisError = vi.fn()
const mockUpdateBarrierCascading = vi.fn()
let mockBarriers: Barrier[] = []
let mockScenario: unknown = null
let mockEventDescription = ''

vi.mock('@/context/BowtieContext', () => ({
  useBowtieContext: () => ({
    barriers: mockBarriers,
    scenario: mockScenario,
    eventDescription: mockEventDescription,
    setIsAnalyzing: mockSetIsAnalyzing,
    setAnalysisError: mockSetAnalysisError,
    updateBarrierCascading: mockUpdateBarrierCascading,
  }),
}))

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const STUB_BARRIERS: Barrier[] = [
  {
    id: 'B-001',
    name: 'Pressure Safety Valve',
    side: 'prevention',
    barrier_type: 'engineering',
    barrier_family: 'pressure_relief',
    line_of_defense: '1',
    barrierRole: 'preventive',
    riskLevel: 'MEDIUM',
  },
  {
    id: 'B-002',
    name: 'Emergency Shutdown System',
    side: 'mitigation',
    barrier_type: 'engineering',
    barrier_family: 'shutdown',
    line_of_defense: '2',
    barrierRole: 'mitigative',
    riskLevel: 'LOW',
  },
]

const STUB_THRESHOLDS = { HIGH: 0.70, MEDIUM: 0.45 }

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useAnalyzeBarriers — null-scenario synthesis regression', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    mockSetIsAnalyzing.mockReset()
    mockSetAnalysisError.mockReset()
    mockUpdateBarrierCascading.mockReset()
    mockPredictCascading.mockReset()

    mockBarriers = [...STUB_BARRIERS]
    mockScenario = null
    mockEventDescription = 'Test loss of containment scenario'

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => STUB_THRESHOLDS }),
    )

    mockPredictCascading.mockResolvedValue({ predictions: [] })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('calls predictCascading when scenario is null but barriers exist', async () => {
    // Regression: the pre-fix hook returned early when scenario was null,
    // so predictCascading was never called for user-built barrier lists.
    const { result } = renderHook(() => useAnalyzeBarriers())

    await act(async () => {
      await result.current.analyzeAll()
    })

    // One request per barrier (N=2 barriers → 2 parallel calls)
    expect(mockPredictCascading).toHaveBeenCalledTimes(STUB_BARRIERS.length)
  })

  it('synthesised scenario maps barrier.id → control_id and barrier.side → barrier_level', async () => {
    // Regression: when synthesising a scenario the hook must preserve the
    // field mapping that the API expects — control_id from barrier.id and
    // barrier_level from barrier.side.
    const { result } = renderHook(() => useAnalyzeBarriers())

    await act(async () => {
      await result.current.analyzeAll()
    })

    // All calls share the same synthesised scenario — inspect the first one.
    const firstCall = mockPredictCascading.mock.calls[0][0]
    const synthBarriers: Array<{ control_id: string; barrier_level: string }> =
      firstCall.scenario.barriers

    for (const original of STUB_BARRIERS) {
      const synth = synthBarriers.find((sb) => sb.control_id === original.id)
      expect(synth, `no synth barrier for id ${original.id}`).toBeDefined()
      expect(synth!.barrier_level).toBe(original.side)
    }
  })
})
