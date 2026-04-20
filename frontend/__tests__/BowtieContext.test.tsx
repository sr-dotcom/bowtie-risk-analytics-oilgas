import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act, waitFor } from '@testing-library/react'
import { useEffect, useRef } from 'react'
import { BowtieProvider, useBowtieContext } from '@/context/BowtieContext'
import type { BarrierPrediction, Scenario } from '@/lib/types'

// ---------------------------------------------------------------------------
// Mock cascading API functions — hoisted before component imports
// ---------------------------------------------------------------------------

const mockPredictCascading = vi.hoisted(() => vi.fn())
const mockRankTargets = vi.hoisted(() => vi.fn())
const mockExplainCascading = vi.hoisted(() => vi.fn())

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual('@/lib/api')
  return {
    ...actual,
    predictCascading: mockPredictCascading,
    rankTargets: mockRankTargets,
    explainCascading: mockExplainCascading,
  }
})

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const STUB_SCENARIO: Scenario = {
  scenario_id: 'test-001',
  source_agency: 'BSEE',
  incident_id: 'test-001',
  top_event: 'Loss of containment',
  barriers: [
    {
      control_id: 'C-001',
      name: 'Pressure Safety Valve',
      barrier_level: 'prevention',
      barrier_condition: 'ineffective',
      barrier_type: 'engineering',
      barrier_role: 'Prevent overpressurization',
    },
    {
      control_id: 'C-002',
      name: 'Emergency Shutdown System',
      barrier_level: 'prevention',
      barrier_condition: 'effective',
      barrier_type: 'engineering',
      barrier_role: 'Isolate on high pressure',
    },
  ],
  threats: [{ threat_id: 'T-001', name: 'Overpressurization', description: null }],
}

const STUB_PREDICTIONS: BarrierPrediction[] = [
  {
    target_barrier_id: 'C-002',
    y_fail_probability: 0.82,
    risk_band: 'HIGH',
    shap_values: [{ feature: 'barrier_type', value: 0.3, display_name: 'Engineering' }],
  },
]

const STUB_CASCADING_RESPONSE = {
  predictions: STUB_PREDICTIONS,
  explanation_unavailable: false,
}

const STUB_RANK_RESPONSE = {
  ranked_barriers: [{ target_barrier_id: 'C-002', composite_risk_score: 0.9 }],
}

const STUB_EXPLAIN_RESPONSE = {
  narrative_text: 'Test narrative',
  evidence_snippets: [],
  degradation_context: { pif_mentions: [], recommendations: [], barrier_condition: 'ineffective' },
  narrative_unavailable: false,
}

// ---------------------------------------------------------------------------
// Test component that exposes context state for assertions
// ---------------------------------------------------------------------------

function ContextSpy({
  onState,
}: {
  onState: (state: ReturnType<typeof useBowtieContext>) => void
}) {
  const state = useBowtieContext()
  useEffect(() => { onState(state) })
  return null
}

/** Helper: sets conditioning + scenario in a single act */
function SetupCascading({
  scenario,
  conditioningId,
}: {
  scenario: Scenario
  conditioningId: string
}) {
  const { setScenario, setConditioningBarrierId } = useBowtieContext()
  const done = useRef(false)
  useEffect(() => {
    if (done.current) return
    done.current = true
    setScenario(scenario)
    setConditioningBarrierId(conditioningId)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('BowtieContext — cascading state (S05a/T04)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockPredictCascading.mockResolvedValue(STUB_CASCADING_RESPONSE)
    mockRankTargets.mockResolvedValue(STUB_RANK_RESPONSE)
    mockExplainCascading.mockResolvedValue(STUB_EXPLAIN_RESPONSE)
  })

  it('cascadingPredictions is empty by default', () => {
    const spy = vi.fn()
    render(
      <BowtieProvider>
        <ContextSpy onState={spy} />
      </BowtieProvider>,
    )
    expect(spy.mock.calls[0][0].cascadingPredictions).toHaveLength(0)
  })

  it('setting conditioningBarrierId + scenario fires predict-cascading and populates predictions', async () => {
    const spy = vi.fn()
    await act(async () => {
      render(
        <BowtieProvider>
          <SetupCascading scenario={STUB_SCENARIO} conditioningId="C-001" />
          <ContextSpy onState={spy} />
        </BowtieProvider>,
      )
    })

    // Wait for the debounced analyze + async API calls; assertions inside waitFor throw on
    // failure so waitFor retries until they pass (standard React Testing Library pattern).
    await waitFor(
      () => {
        const lastState = spy.mock.calls[spy.mock.calls.length - 1][0]
        expect(lastState.cascadingPredictions).toHaveLength(1)
        expect(lastState.cascadingPredictions[0].target_barrier_id).toBe('C-002')
        expect(mockPredictCascading).toHaveBeenCalledOnce()
        expect(mockRankTargets).toHaveBeenCalledOnce()
      },
      { timeout: 1000 },
    )
  })

  it('setting selectedTargetBarrierId fires explain-cascading and populates explanation', async () => {
    const spy = vi.fn()
    await act(async () => {
      render(
        <BowtieProvider initialScenario={STUB_SCENARIO}>
          <ContextSpy onState={spy} />
        </BowtieProvider>,
      )
    })

    // Set conditioning + target together
    const { setConditioningBarrierId, setSelectedTargetBarrierId } =
      spy.mock.calls[spy.mock.calls.length - 1][0]

    await act(async () => {
      setConditioningBarrierId('C-001')
      setSelectedTargetBarrierId('C-002')
    })

    await waitFor(
      () => {
        const lastState = spy.mock.calls[spy.mock.calls.length - 1][0]
        return lastState.explanation !== null
      },
      { timeout: 1000 },
    )

    const lastState = spy.mock.calls[spy.mock.calls.length - 1][0]
    expect(lastState.explanation?.narrative_text).toBe('Test narrative')
    expect(mockExplainCascading).toHaveBeenCalledOnce()
  })

  it('clearCascading resets conditioningBarrierId and selectedTargetBarrierId', async () => {
    const spy = vi.fn()
    await act(async () => {
      render(
        <BowtieProvider initialScenario={STUB_SCENARIO}>
          <ContextSpy onState={spy} />
        </BowtieProvider>,
      )
    })

    const { setConditioningBarrierId, setSelectedTargetBarrierId, clearCascading } =
      spy.mock.calls[spy.mock.calls.length - 1][0]

    await act(async () => {
      setConditioningBarrierId('C-001')
      setSelectedTargetBarrierId('C-002')
    })

    await act(async () => {
      clearCascading()
    })

    const lastState = spy.mock.calls[spy.mock.calls.length - 1][0]
    expect(lastState.conditioningBarrierId).toBeNull()
    expect(lastState.selectedTargetBarrierId).toBeNull()
  })

  it('initialScenario and initialCascadingPredictions are reflected in initial state', () => {
    const spy = vi.fn()
    render(
      <BowtieProvider
        initialScenario={STUB_SCENARIO}
        initialCascadingPredictions={STUB_PREDICTIONS}
      >
        <ContextSpy onState={spy} />
      </BowtieProvider>,
    )
    const state = spy.mock.calls[0][0]
    expect(state.scenario?.scenario_id).toBe('test-001')
    expect(state.cascadingPredictions).toHaveLength(1)
  })
})
