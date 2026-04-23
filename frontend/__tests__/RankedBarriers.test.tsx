import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { useEffect, useRef } from 'react'
import { BowtieProvider, useBowtieContext } from '@/context/BowtieContext'
import type { Barrier, PredictResponse, ShapValue } from '@/lib/types'

// ---------------------------------------------------------------------------
// Mock explain from @/lib/api — EvidenceSection calls this on mount.
// Use vi.hoisted so the variable is available inside the vi.mock factory,
// which is hoisted to the top of the file before any imports are resolved.
// ---------------------------------------------------------------------------

const mockExplain = vi.hoisted(() => vi.fn())
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual('@/lib/api')
  return { ...actual, explain: mockExplain }
})

// ---------------------------------------------------------------------------
// Import component AFTER vi.mock
// ---------------------------------------------------------------------------

import RankedBarriers, { buildRankedRows } from '@/components/dashboard/RankedBarriers'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_EXPLAIN_RESPONSE = {
  narrative: 'Historical evidence shows pressure relief failures are common.',
  citations: [],
  retrieval_confidence: 0.75,
  model_used: 'claude-haiku',
  recommendations: '',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeBarrier(overrides: Partial<Barrier> = {}): Barrier {
  return {
    id: crypto.randomUUID(),
    name: 'Test Barrier',
    side: 'prevention',
    barrier_type: 'administrative',
    barrier_family: 'procedure',
    line_of_defense: '1',
    barrierRole: 'preventive',
    riskLevel: 'unanalyzed',
    ...overrides,
  }
}

function makePrediction(
  model1_probability: number,
  model1_shap: ShapValue[] = [],
  overrides: Partial<PredictResponse> = {},
): PredictResponse {
  return {
    model1_probability,
    model2_probability: 0,
    model1_shap,
    model2_shap: [],
    model1_base_value: 0.1,
    model2_base_value: 0.1,
    feature_metadata: [],
    degradation_factors: [],
    risk_level: 'Low',
    barrier_type_display: 'Administrative',
    lod_display: '1st',
    barrier_condition_display: 'Nominal',
    ...overrides,
  }
}

type BarrierDef = Omit<Barrier, 'id' | 'riskLevel'>

/** Populates BowtieContext with barriers + predictions then renders children. */
function SetupBarriers({
  barrierDefs,
  predictionsMap,
}: {
  barrierDefs: BarrierDef[]
  predictionsMap?: (barriers: Barrier[]) => Record<string, PredictResponse>
}) {
  const { addBarrier, setPrediction, barriers } = useBowtieContext()
  const loaded = useRef(false)

  useEffect(() => {
    if (loaded.current) return
    loaded.current = true
    barrierDefs.forEach((b) => addBarrier(b))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!predictionsMap || barriers.length === 0) return
    const preds = predictionsMap(barriers)
    Object.entries(preds).forEach(([id, pred]) => setPrediction(id, pred))
  }, [barriers.length]) // eslint-disable-line react-hooks/exhaustive-deps

  return null
}

const BARRIER_DEF: BarrierDef = {
  name: 'Pressure Relief Valve',
  side: 'prevention',
  barrier_type: 'mechanical',
  barrier_family: 'pressure_relief',
  line_of_defense: '1',
  barrierRole: 'preventive',
}

function renderWithContext(
  barrierDefs: BarrierDef[],
  predictionsMap?: (barriers: Barrier[]) => Record<string, PredictResponse>,
) {
  return render(
    <BowtieProvider>
      <SetupBarriers barrierDefs={barrierDefs} predictionsMap={predictionsMap} />
      <RankedBarriers />
    </BowtieProvider>,
  )
}

// ---------------------------------------------------------------------------
// Unit tests: buildRankedRows
// ---------------------------------------------------------------------------

describe('buildRankedRows', () => {
  it('returns empty array when no barriers', () => {
    expect(buildRankedRows([], {}, 'rank', 'asc')).toEqual([])
  })

  it('returns empty array when no predictions', () => {
    const b = makeBarrier()
    expect(buildRankedRows([b], {}, 'rank', 'asc')).toEqual([])
  })

  it('assigns rank 1 to the highest-probability barrier', () => {
    const b1 = makeBarrier({ name: 'Low' })
    const b2 = makeBarrier({ name: 'High' })
    const preds = {
      [b1.id]: makePrediction(0.2),
      [b2.id]: makePrediction(0.8),
    }
    const rows = buildRankedRows([b1, b2], preds, 'rank', 'asc')
    expect(rows[0].rank).toBe(1)
    expect(rows[0].name).toBe('High')
  })

  it('sorts by probability descending when sortKey=probability, sortDir=desc', () => {
    const b1 = makeBarrier({ name: 'A' })
    const b2 = makeBarrier({ name: 'B' })
    const b3 = makeBarrier({ name: 'C' })
    const preds = {
      [b1.id]: makePrediction(0.3),
      [b2.id]: makePrediction(0.9),
      [b3.id]: makePrediction(0.6),
    }
    const rows = buildRankedRows([b1, b2, b3], preds, 'probability', 'desc')
    expect(rows[0].probability).toBeGreaterThan(rows[1].probability)
    expect(rows[1].probability).toBeGreaterThan(rows[2].probability)
  })

  it('sorts by name ascending when sortKey=name, sortDir=asc', () => {
    const b1 = makeBarrier({ name: 'Zebra' })
    const b2 = makeBarrier({ name: 'Alpha' })
    const preds = {
      [b1.id]: makePrediction(0.5),
      [b2.id]: makePrediction(0.4),
    }
    const rows = buildRankedRows([b1, b2], preds, 'name', 'asc')
    expect(rows[0].name).toBe('Alpha')
    expect(rows[1].name).toBe('Zebra')
  })

  it('sets condition from barrier_condition_display when present', () => {
    const b = makeBarrier()
    const pred = makePrediction(0.5)
    pred.barrier_condition_display = 'Degraded'
    const rows = buildRankedRows([b], { [b.id]: pred }, 'rank', 'asc')
    expect(rows[0].condition).toBe('Degraded')
  })

  it('falls back condition to — when barrier_condition_display is null', () => {
    const b = makeBarrier()
    const pred = makePrediction(0.5)
    pred.barrier_condition_display = undefined as unknown as string
    const rows = buildRankedRows([b], { [b.id]: pred }, 'rank', 'asc')
    expect(rows[0].condition).toBe('—')
  })
})

// ---------------------------------------------------------------------------
// Component tests: RankedBarriers rendering (SetupBarriers helper pattern)
// ---------------------------------------------------------------------------

describe('RankedBarriers component', () => {
  beforeEach(() => {
    mockExplain.mockClear()
    mockExplain.mockResolvedValue(MOCK_EXPLAIN_RESPONSE)
  })

  it('shows empty-state text when no analyzed barriers', () => {
    render(
      <BowtieProvider>
        <RankedBarriers />
      </BowtieProvider>,
    )
    expect(screen.getByText(/No analyzed barriers yet/)).toBeTruthy()
  })

  it('renders ranked-barriers-table testid', () => {
    render(
      <BowtieProvider>
        <RankedBarriers />
      </BowtieProvider>,
    )
    expect(screen.getByTestId('ranked-barriers-table')).toBeTruthy()
  })

  it('renders a data row for each analyzed barrier', async () => {
    renderWithContext([BARRIER_DEF, { ...BARRIER_DEF, name: 'Second Barrier' }], (barriers) => ({
      [barriers[0].id]: makePrediction(0.7),
      [barriers[1].id]: makePrediction(0.4),
    }))

    // Wait for state to propagate
    await screen.findByText('Pressure Relief Valve')
    expect(screen.getByText('Second Barrier')).toBeTruthy()
  })

  it('does not render expanded row before any click', async () => {
    renderWithContext([BARRIER_DEF], (barriers) => ({
      [barriers[0].id]: makePrediction(0.6),
    }))
    await screen.findByText('Pressure Relief Valve')
    expect(screen.queryByTestId('ranked-row-expanded')).toBeNull()
  })

  it('shows expanded row with load-evidence-btn after clicking a row', async () => {
    renderWithContext([BARRIER_DEF], (barriers) => ({
      [barriers[0].id]: makePrediction(0.6),
    }))
    const row = await screen.findByText('Pressure Relief Valve')
    fireEvent.click(row.closest('tr')!)
    expect(screen.getByTestId('ranked-row-expanded')).toBeTruthy()
    expect(screen.getByTestId('load-evidence-btn')).toBeTruthy()
  })

  it('collapses expanded row on second click of same row', async () => {
    renderWithContext([BARRIER_DEF], (barriers) => ({
      [barriers[0].id]: makePrediction(0.6),
    }))
    const row = await screen.findByText('Pressure Relief Valve')
    const tr = row.closest('tr')!
    fireEvent.click(tr)
    expect(screen.getByTestId('ranked-row-expanded')).toBeTruthy()
    fireEvent.click(tr)
    expect(screen.queryByTestId('ranked-row-expanded')).toBeNull()
  })

  it('mounts EvidenceSection only after Load Evidence button is clicked', async () => {
    renderWithContext([BARRIER_DEF], (barriers) => ({
      [barriers[0].id]: makePrediction(0.6),
    }))
    const row = await screen.findByText('Pressure Relief Valve')
    fireEvent.click(row.closest('tr')!)

    // Load Evidence button is present, EvidenceSection not yet mounted
    expect(screen.getByTestId('load-evidence-btn')).toBeTruthy()
    expect(screen.queryByText('Loading evidence...')).toBeNull()
    expect(screen.queryByText(MOCK_EXPLAIN_RESPONSE.narrative)).toBeNull()

    // Click Load Evidence button — EvidenceSection mounts and starts fetching
    await act(async () => {
      fireEvent.click(screen.getByTestId('load-evidence-btn'))
    })

    // Evidence button gone; EvidenceSection is mounted (shows narrative after resolve)
    expect(screen.queryByTestId('load-evidence-btn')).toBeNull()
  })

  it('Load Evidence button click does not collapse the expanded row (stopPropagation)', async () => {
    renderWithContext([BARRIER_DEF], (barriers) => ({
      [barriers[0].id]: makePrediction(0.6),
    }))
    const row = await screen.findByText('Pressure Relief Valve')
    fireEvent.click(row.closest('tr')!)
    await act(async () => {
      fireEvent.click(screen.getByTestId('load-evidence-btn'))
    })
    // Row still expanded after clicking Load Evidence
    expect(screen.getByTestId('ranked-row-expanded')).toBeTruthy()
  })

  it('only one row is expanded at a time (clicking another collapses the first)', async () => {
    renderWithContext(
      [BARRIER_DEF, { ...BARRIER_DEF, name: 'Second Barrier' }],
      (barriers) => ({
        [barriers[0].id]: makePrediction(0.7),
        [barriers[1].id]: makePrediction(0.4),
      }),
    )

    const first = await screen.findByText('Pressure Relief Valve')
    fireEvent.click(first.closest('tr')!)
    expect(screen.getAllByTestId('ranked-row-expanded')).toHaveLength(1)

    const second = screen.getByText('Second Barrier')
    fireEvent.click(second.closest('tr')!)
    // Still only one expanded row (the second one now)
    expect(screen.getAllByTestId('ranked-row-expanded')).toHaveLength(1)
  })
})

// ---------------------------------------------------------------------------
// Component tests: initialBarriers + initialPredictions pattern with
// sub-component content verification (RiskScoreBadge, ShapWaterfall, evidence)
// ---------------------------------------------------------------------------

// Fixtures matching task plan spec
const BARRIER_WITH_ID: Barrier = {
  id: 'b-001',
  name: 'Pressure Relief Valve',
  side: 'prevention',
  barrier_type: 'engineering',
  barrier_family: 'pressure_relief',
  line_of_defense: '1st',
  barrierRole: 'prevent overpressure',
  riskLevel: 'red',
  probability: 0.85,
}

const HIGH_RISK_PREDICTION: PredictResponse = {
  model1_probability: 0.85,
  model2_probability: 0.3,
  model1_shap: [{ feature: 'barrier_family', value: 0.3, category: 'barrier' }],
  model2_shap: [],
  model1_base_value: 0.5,
  model2_base_value: 0.2,
  feature_metadata: [],
  degradation_factors: [],
  risk_level: 'High',
  barrier_type_display: 'Engineering',
  lod_display: '1st',
  barrier_condition_display: 'Likely Degraded',
}

const SECOND_BARRIER: Barrier = {
  id: 'b-002',
  name: 'Emergency Shutdown Valve',
  side: 'mitigation',
  barrier_type: 'engineering',
  barrier_family: 'emergency_shutdown',
  line_of_defense: '2nd',
  barrierRole: 'isolate process',
  riskLevel: 'amber',
  probability: 0.55,
}

const MEDIUM_RISK_PREDICTION: PredictResponse = {
  model1_probability: 0.55,
  model2_probability: 0.2,
  model1_shap: [{ feature: 'barrier_family', value: 0.15, category: 'barrier' }],
  model2_shap: [],
  model1_base_value: 0.4,
  model2_base_value: 0.2,
  feature_metadata: [],
  degradation_factors: [],
  risk_level: 'Medium',
  barrier_type_display: 'Engineering',
  lod_display: '2nd',
  barrier_condition_display: 'Partially Degraded',
}

function renderWithInitial(
  barriers: Barrier[] = [BARRIER_WITH_ID],
  predictions: Record<string, PredictResponse> = { 'b-001': HIGH_RISK_PREDICTION },
) {
  return render(
    <BowtieProvider initialBarriers={barriers} initialPredictions={predictions}>
      <RankedBarriers />
    </BowtieProvider>,
  )
}

describe('RankedBarriers — initialBarriers/initialPredictions + sub-component content', () => {
  beforeEach(() => {
    mockExplain.mockClear()
    mockExplain.mockResolvedValue(MOCK_EXPLAIN_RESPONSE)
  })

  // (a) Empty state
  it('shows "No analyzed barriers yet" when rendered with no barriers or predictions', () => {
    renderWithInitial([], {})
    expect(screen.getByText(/No analyzed barriers yet/)).toBeTruthy()
  })

  // (b) Renders one row per analyzed barrier
  it('renders exactly one data row for one analyzed barrier', () => {
    renderWithInitial()
    expect(screen.getByText('Pressure Relief Valve')).toBeTruthy()
    expect(screen.queryByText('Emergency Shutdown Valve')).toBeNull()
  })

  // (c) Click row expands section
  it('clicking a row reveals the ranked-row-expanded section', () => {
    renderWithInitial()
    expect(screen.queryByTestId('ranked-row-expanded')).toBeNull()
    fireEvent.click(screen.getByText('Pressure Relief Valve').closest('tr')!)
    expect(screen.getByTestId('ranked-row-expanded')).toBeTruthy()
  })

  // (d) Click same row collapses
  it('clicking the same row a second time collapses the expanded section', () => {
    renderWithInitial()
    const tr = screen.getByText('Pressure Relief Valve').closest('tr')!
    fireEvent.click(tr)
    expect(screen.getByTestId('ranked-row-expanded')).toBeTruthy()
    fireEvent.click(tr)
    expect(screen.queryByTestId('ranked-row-expanded')).toBeNull()
  })

  // (e) RiskScoreBadge text visible in expanded section
  it('expanded section shows "High reliability concern" for a red-level barrier', () => {
    renderWithInitial()
    fireEvent.click(screen.getByText('Pressure Relief Valve').closest('tr')!)
    // RiskScoreBadge renders subtitle text based on riskLevel
    expect(screen.getByText('High reliability concern')).toBeTruthy()
  })

  // (f) ShapWaterfall heading visible in expanded section
  it('expanded section shows "Barrier Analysis Factors" heading from ShapWaterfall', () => {
    renderWithInitial()
    fireEvent.click(screen.getByText('Pressure Relief Valve').closest('tr')!)
    expect(screen.getByText('Barrier Analysis Factors')).toBeTruthy()
  })

  // (g) Load Evidence button visible before click
  it('Load Evidence button is visible in expanded section before clicking it', () => {
    renderWithInitial()
    fireEvent.click(screen.getByText('Pressure Relief Valve').closest('tr')!)
    expect(screen.getByRole('button', { name: 'Load Evidence' })).toBeTruthy()
  })

  // (h) Clicking Load Evidence mounts EvidenceSection (evidence from /explain-cascading via context)
  it('clicking Load Evidence mounts EvidenceSection showing conditioning placeholder', async () => {
    renderWithInitial()
    fireEvent.click(screen.getByText('Pressure Relief Valve').closest('tr')!)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Load Evidence' }))
    })
    // EvidenceSection is mounted; explain() is no longer called — evidence sourced from context
    expect(mockExplain).not.toHaveBeenCalled()
    // No conditioning barrier in this test context → EvidenceSection shows the placeholder
    expect(screen.getByText(/Click a barrier.*conditioning context/i)).toBeTruthy()
  })

  // (i) After Load Evidence, EvidenceSection renders (conditioning placeholder until cascading context set)
  it('EvidenceSection is mounted after Load Evidence click', async () => {
    renderWithInitial()
    fireEvent.click(screen.getByText('Pressure Relief Valve').closest('tr')!)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Load Evidence' }))
    })
    // EvidenceSection is mounted and renders (placeholder shown — no conditioningBarrierId in test context)
    expect(screen.getByText(/Click a barrier.*conditioning context/i)).toBeTruthy()
  })

  // (j) Row switching — expand A, click B → A collapses, B expands
  it('expanding barrier B after A collapses A and shows B expanded', () => {
    renderWithInitial(
      [BARRIER_WITH_ID, SECOND_BARRIER],
      { 'b-001': HIGH_RISK_PREDICTION, 'b-002': MEDIUM_RISK_PREDICTION },
    )
    // Expand first barrier
    fireEvent.click(screen.getByText('Pressure Relief Valve').closest('tr')!)
    expect(screen.getAllByTestId('ranked-row-expanded')).toHaveLength(1)

    // Expand second barrier — first should collapse
    fireEvent.click(screen.getByText('Emergency Shutdown Valve').closest('tr')!)
    expect(screen.getAllByTestId('ranked-row-expanded')).toHaveLength(1)

    // Verify it's the second barrier's content now visible (Moderate concern)
    expect(screen.getByText('Moderate reliability concern')).toBeTruthy()
    expect(screen.queryByText('High reliability concern')).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Component tests: Filter bar — side, risk level, barrier type, result count
// ---------------------------------------------------------------------------

describe('RankedBarriers — filter bar', () => {
  beforeEach(() => {
    mockExplain.mockClear()
    mockExplain.mockResolvedValue(MOCK_EXPLAIN_RESPONSE)
  })

  // (a) Default state: all three selects render with value 'all'
  it('renders three filter selects with default all value', () => {
    renderWithInitial(
      [BARRIER_WITH_ID, SECOND_BARRIER],
      { 'b-001': HIGH_RISK_PREDICTION, 'b-002': MEDIUM_RISK_PREDICTION },
    )
    expect((screen.getByTestId('filter-side') as HTMLSelectElement).value).toBe('all')
    expect((screen.getByTestId('filter-risk-level') as HTMLSelectElement).value).toBe('all')
    expect((screen.getByTestId('filter-type') as HTMLSelectElement).value).toBe('all')
  })

  // (b) Selecting side='prevention' hides mitigation rows
  it('filtering by side=prevention shows prevention barrier and hides mitigation barrier', () => {
    renderWithInitial(
      [BARRIER_WITH_ID, SECOND_BARRIER],
      { 'b-001': HIGH_RISK_PREDICTION, 'b-002': MEDIUM_RISK_PREDICTION },
    )
    fireEvent.change(screen.getByTestId('filter-side'), { target: { value: 'prevention' } })
    expect(screen.getByText('Pressure Relief Valve')).toBeTruthy()
    expect(screen.queryByText('Emergency Shutdown Valve')).toBeNull()
  })

  // (c) Selecting riskLevel='red' shows only high-risk rows
  it('filtering by riskLevel=red shows high-risk barrier and hides medium-risk barrier', () => {
    renderWithInitial(
      [BARRIER_WITH_ID, SECOND_BARRIER],
      { 'b-001': HIGH_RISK_PREDICTION, 'b-002': MEDIUM_RISK_PREDICTION },
    )
    fireEvent.change(screen.getByTestId('filter-risk-level'), { target: { value: 'red' } })
    expect(screen.getByText('Pressure Relief Valve')).toBeTruthy()
    expect(screen.queryByText('Emergency Shutdown Valve')).toBeNull()
  })

  // (d) Selecting barrierType narrows by type — using a distinct type for SECOND_BARRIER
  it('filtering by barrierType=Administrative hides Engineering-type barriers', () => {
    const ADMIN_PREDICTION: PredictResponse = {
      ...MEDIUM_RISK_PREDICTION,
      barrier_type_display: 'Administrative',
    }
    renderWithInitial(
      [BARRIER_WITH_ID, SECOND_BARRIER],
      { 'b-001': HIGH_RISK_PREDICTION, 'b-002': ADMIN_PREDICTION },
    )
    fireEvent.change(screen.getByTestId('filter-type'), { target: { value: 'Engineering' } })
    expect(screen.getByText('Pressure Relief Valve')).toBeTruthy()
    expect(screen.queryByText('Emergency Shutdown Valve')).toBeNull()
  })

  // (e) Result count updates after filtering
  it('result count shows "Showing 1 of 2 barriers" after filtering by side=prevention', () => {
    renderWithInitial(
      [BARRIER_WITH_ID, SECOND_BARRIER],
      { 'b-001': HIGH_RISK_PREDICTION, 'b-002': MEDIUM_RISK_PREDICTION },
    )
    fireEvent.change(screen.getByTestId('filter-side'), { target: { value: 'prevention' } })
    expect(screen.getByTestId('filter-result-count').textContent).toContain('Showing 1 of 2 barriers')
  })

  // (f) Resetting filter to 'all' restores all rows
  it('resetting side filter back to all restores both rows', () => {
    renderWithInitial(
      [BARRIER_WITH_ID, SECOND_BARRIER],
      { 'b-001': HIGH_RISK_PREDICTION, 'b-002': MEDIUM_RISK_PREDICTION },
    )
    // First hide mitigation row
    fireEvent.change(screen.getByTestId('filter-side'), { target: { value: 'prevention' } })
    expect(screen.queryByText('Emergency Shutdown Valve')).toBeNull()
    // Reset to all
    fireEvent.change(screen.getByTestId('filter-side'), { target: { value: 'all' } })
    expect(screen.getByText('Pressure Relief Valve')).toBeTruthy()
    expect(screen.getByText('Emergency Shutdown Valve')).toBeTruthy()
  })

  // (g) Two filters combined — AND logic
  it('combining side=prevention and riskLevel=red shows only the row matching both criteria', () => {
    renderWithInitial(
      [BARRIER_WITH_ID, SECOND_BARRIER],
      { 'b-001': HIGH_RISK_PREDICTION, 'b-002': MEDIUM_RISK_PREDICTION },
    )
    fireEvent.change(screen.getByTestId('filter-side'), { target: { value: 'prevention' } })
    fireEvent.change(screen.getByTestId('filter-risk-level'), { target: { value: 'red' } })
    expect(screen.getByText('Pressure Relief Valve')).toBeTruthy()
    expect(screen.queryByText('Emergency Shutdown Valve')).toBeNull()
    expect(screen.getByTestId('filter-result-count').textContent).toContain('Showing 1 of 2 barriers')
  })
})
