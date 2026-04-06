import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { useEffect, useRef } from 'react'
import { BowtieProvider, useBowtieContext } from '@/context/BowtieContext'
import type { Barrier, PredictResponse } from '@/lib/types'

// ---------------------------------------------------------------------------
// Mock useAnalyzeBarriers at module level — hoisted before component import
// so vitest replaces the module for ALL tests in this file.
// ---------------------------------------------------------------------------

const mockAnalyzeAll = vi.fn()
vi.mock('@/hooks/useAnalyzeBarriers', () => ({
  useAnalyzeBarriers: () => ({ analyzeAll: mockAnalyzeAll }),
}))

// Mock fetchAprioriRules so the AprioriRulesTable inside Drivers & HF tab
// doesn't make real network calls during DashboardView tests.
const mockFetchAprioriRules = vi.hoisted(() => vi.fn())
const mockExplain = vi.hoisted(() => vi.fn())
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual('@/lib/api')
  return { ...actual, fetchAprioriRules: mockFetchAprioriRules, explain: mockExplain }
})

// Import component AFTER vi.mock so the mock is applied
import DashboardView from '@/components/dashboard/DashboardView'

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

const TAB_LABELS = ['Executive Summary', 'Barrier Coverage', 'Incident Trends', 'Risk Matrix', 'Drivers & HF', 'Ranked Barriers']

type BarrierDef = Omit<Barrier, 'id' | 'riskLevel'>

/** Populates BowtieContext with barriers (and optionally predictions) before rendering. */
function SetupBarriers({
  barrierDefs,
  predictionsToSet,
}: {
  barrierDefs: BarrierDef[]
  predictionsToSet?: Record<string, PredictResponse>
}) {
  const { addBarrier, setPrediction, barriers } = useBowtieContext()
  const loaded = useRef(false)

  useEffect(() => {
    if (loaded.current) return
    loaded.current = true
    barrierDefs.forEach((b) => addBarrier(b))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Once barriers are populated, set predictions by barrier index
  useEffect(() => {
    if (!predictionsToSet || barriers.length === 0) return
    // predictionsToSet keys are indices ("0", "1", …) mapped to barrier positions
    Object.entries(predictionsToSet).forEach(([idxStr, pred]) => {
      const idx = parseInt(idxStr, 10)
      const barrier = barriers[idx]
      if (barrier) setPrediction(barrier.id, pred)
    })
  }, [barriers.length]) // eslint-disable-line react-hooks/exhaustive-deps

  return null
}

/** Populates BowtieContext with isAnalyzing=true. */
function SetupAnalyzing() {
  const { setIsAnalyzing } = useBowtieContext()
  const done = useRef(false)
  useEffect(() => {
    if (done.current) return
    done.current = true
    setIsAnalyzing(true)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

const BARRIER_DEF: BarrierDef = {
  name: 'Test Barrier',
  side: 'prevention',
  barrier_type: 'engineering',
  barrier_family: 'other_unknown',
  line_of_defense: '1st',
  barrierRole: 'test',
}

/** A minimal stub PredictResponse so context.predictions has an entry. */
const STUB_PREDICTION: PredictResponse = {
  model1_probability: 0.2,
  model2_probability: 0.2,
  model1_shap: [],
  model2_shap: [],
  model1_base_value: 0,
  model2_base_value: 0,
  feature_metadata: [],
  degradation_factors: [],
  risk_level: 'Low',
  barrier_type_display: 'Engineering',
  lod_display: '1st Line of Defence',
  barrier_condition_display: 'Likely Effective',
}

function renderDashboard() {
  return render(
    <BowtieProvider>
      <DashboardView />
    </BowtieProvider>,
  )
}

// ---------------------------------------------------------------------------
// Existing tab tests (unchanged)
// ---------------------------------------------------------------------------

describe('DashboardView', () => {
  beforeEach(() => {
    mockAnalyzeAll.mockClear()
    mockFetchAprioriRules.mockResolvedValue([])
    mockExplain.mockResolvedValue({ narrative: 'Test evidence', citations: [], retrieval_confidence: 0.8, model_used: 'stub', recommendations: '' })
  })

  it('renders all 6 tab buttons with correct labels', () => {
    renderDashboard()
    const buttons = screen.getAllByRole('button')
    expect(buttons).toHaveLength(6)
    for (const label of TAB_LABELS) {
      expect(screen.getByRole('button', { name: label })).toBeTruthy()
    }
  })

  it('defaults to Executive Summary tab active', () => {
    renderDashboard()
    const execBtn = screen.getByRole('button', { name: 'Executive Summary' })
    expect(execBtn.className).toContain('border-[#3B82F6]')
    // The Executive Summary tab shows the chart, not a "coming soon" message
    expect(screen.getByTestId('risk-distribution-chart')).toBeTruthy()
  })

  it('clicking Barrier Coverage makes it active and deactivates Executive Summary', () => {
    renderDashboard()
    const barrierBtn = screen.getByRole('button', { name: 'Barrier Coverage' })
    const execBtn = screen.getByRole('button', { name: 'Executive Summary' })

    fireEvent.click(barrierBtn)

    expect(barrierBtn.className).toContain('border-[#3B82F6]')
    expect(execBtn.className).not.toContain('border-[#3B82F6]')
    expect(screen.getByText('Barrier Coverage coming soon')).toBeTruthy()
  })

  it('each non-Executive-Summary, non-DriversHF tab shows the correct coming soon content', () => {
    renderDashboard()
    const comingSoonTabs = TAB_LABELS.filter((l) => l !== 'Executive Summary' && l !== 'Drivers & HF' && l !== 'Ranked Barriers')
    for (const label of comingSoonTabs) {
      fireEvent.click(screen.getByRole('button', { name: label }))
      expect(screen.getByText(`${label} coming soon`)).toBeTruthy()
    }
  })

  it('only one tab content is shown at a time', () => {
    renderDashboard()
    fireEvent.click(screen.getByRole('button', { name: 'Incident Trends' }))

    expect(screen.getByText('Incident Trends coming soon')).toBeTruthy()
    expect(screen.queryByTestId('risk-distribution-chart')).toBeNull()
    expect(screen.queryByText('Barrier Coverage coming soon')).toBeNull()
    expect(screen.queryByText('Risk Matrix coming soon')).toBeNull()
  })

  it('clicking Drivers & HF renders GlobalShapChart and PifPrevalenceChart', async () => {
    await act(async () => {
      renderDashboard()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Drivers & HF' }))
    expect(screen.getByTestId('global-shap-chart')).toBeTruthy()
    expect(screen.getByTestId('pif-prevalence-chart')).toBeTruthy()
  })

  it('clicking Drivers & HF renders AprioriRulesTable once data loads', async () => {
    await act(async () => {
      renderDashboard()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Drivers & HF' }))
    // findByTestId waits for async state (fetchAprioriRules resolves) to settle
    const table = await screen.findByTestId('apriori-rules-table')
    expect(table).toBeTruthy()
  })

  it('clicking Drivers & HF does not show coming soon for that tab', async () => {
    await act(async () => {
      renderDashboard()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Drivers & HF' }))
    expect(screen.queryByText('Drivers & HF coming soon')).toBeNull()
  })

  it('clicking Ranked Barriers renders the ranked barriers table', () => {
    renderDashboard()
    fireEvent.click(screen.getByRole('button', { name: 'Ranked Barriers' }))
    expect(screen.getByTestId('ranked-barriers-table')).toBeTruthy()
  })

  it('Drivers & HF tab is active when clicked', async () => {
    await act(async () => {
      renderDashboard()
    })
    const driversBtn = screen.getByRole('button', { name: 'Drivers & HF' })
    await act(async () => {
      fireEvent.click(driversBtn)
    })
    expect(driversBtn.className).toContain('border-[#3B82F6]')
  })

  it('switching away from Drivers & HF to Barrier Coverage shows coming soon', async () => {
    await act(async () => {
      renderDashboard()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Drivers & HF' }))
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Barrier Coverage' }))
    })
    expect(screen.getByText('Barrier Coverage coming soon')).toBeTruthy()
    expect(screen.queryByTestId('global-shap-chart')).toBeNull()
  })

  it('inactive tabs have the inactive text colour class', () => {
    renderDashboard()
    // With Executive Summary active, the other four should carry the inactive colour
    for (const label of ['Barrier Coverage', 'Incident Trends', 'Risk Matrix', 'Drivers & HF']) {
      const btn = screen.getByRole('button', { name: label })
      expect(btn.className).toContain('text-[#5A6178]')
    }
  })

  it('executive-summary tab shows top-at-risk-barriers component', () => {
    renderDashboard()
    // Executive Summary is the default tab
    expect(screen.getByTestId('top-at-risk-barriers')).toBeTruthy()
  })

  it('executive-summary tab shows model KPIs component', () => {
    renderDashboard()
    expect(screen.getByTestId('model-kpis')).toBeTruthy()
  })

  it('executive-summary tab shows scenario context component', () => {
    renderDashboard()
    expect(screen.getByTestId('scenario-context')).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// Auto-batch /predict tests
// ---------------------------------------------------------------------------

describe('DashboardView auto-batch', () => {
  beforeEach(() => {
    mockAnalyzeAll.mockClear()
    mockFetchAprioriRules.mockResolvedValue([])
    mockExplain.mockResolvedValue({ narrative: 'Test evidence', citations: [], retrieval_confidence: 0.8, model_used: 'stub', recommendations: '' })
  })

  it('calls analyzeAll when barriers exist without predictions', async () => {
    await act(async () => {
      render(
        <BowtieProvider>
          <SetupBarriers barrierDefs={[BARRIER_DEF]} />
          <DashboardView />
        </BowtieProvider>,
      )
    })
    expect(mockAnalyzeAll).toHaveBeenCalledOnce()
  })

  it('does not call analyzeAll when no barriers exist', async () => {
    await act(async () => {
      render(
        <BowtieProvider>
          <DashboardView />
        </BowtieProvider>,
      )
    })
    expect(mockAnalyzeAll).not.toHaveBeenCalled()
  })

  it('does not call analyzeAll when all barriers already have predictions', async () => {
    // Pre-populate both barriers and predictions synchronously via BowtieProvider initial props
    // so no timing race exists between addBarrier and setPrediction useEffects.
    const barrierWithId: Barrier = { ...BARRIER_DEF, id: 'fixed-id-001', riskLevel: 'unanalyzed' }
    await act(async () => {
      render(
        <BowtieProvider
          initialBarriers={[barrierWithId]}
          initialPredictions={{ 'fixed-id-001': STUB_PREDICTION }}
        >
          <DashboardView />
        </BowtieProvider>,
      )
    })
    expect(mockAnalyzeAll).not.toHaveBeenCalled()
  })

  it('shows loading indicator when isAnalyzing is true', async () => {
    await act(async () => {
      render(
        <BowtieProvider>
          <SetupAnalyzing />
          <DashboardView />
        </BowtieProvider>,
      )
    })
    expect(screen.getByTestId('analyzing-skeleton')).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// Ranked Barriers integration tests
// ---------------------------------------------------------------------------

describe('DashboardView — Ranked Barriers integration', () => {
  const INTEGRATION_BARRIER: Barrier = {
    id: 'int-barrier-001',
    name: 'Integration Test Barrier',
    side: 'prevention',
    barrier_type: 'engineering',
    barrier_family: 'pressure_relief',
    line_of_defense: '1st',
    barrierRole: 'test',
    riskLevel: 'unanalyzed',
  }

  const INTEGRATION_PREDICTION: PredictResponse = {
    model1_probability: 0.999,
    model2_probability: 0.8,
    model1_shap: [{ feature: 'barrier_type', value: 0.3, category: 'barrier' }],
    model2_shap: [],
    model1_base_value: 0.5,
    model2_base_value: 0.5,
    feature_metadata: [],
    degradation_factors: [],
    risk_level: 'High',
    barrier_type_display: 'Engineering',
    lod_display: '1st Line of Defence',
    barrier_condition_display: 'Likely Ineffective',
  }

  function SelectedBarrierSpy({ onId }: { onId: (id: string | null) => void }) {
    const { selectedBarrierId } = useBowtieContext()
    useEffect(() => { onId(selectedBarrierId) }, [selectedBarrierId, onId])
    return null
  }

  beforeEach(() => {
    mockAnalyzeAll.mockClear()
    mockFetchAprioriRules.mockResolvedValue([])
    mockExplain.mockResolvedValue({ narrative: 'Test evidence', citations: [], retrieval_confidence: 0.8, model_used: 'stub', recommendations: '' })
  })

  it('clicking a barrier row in Ranked Barriers tab updates selectedBarrierId', async () => {
    const spyFn = vi.fn()
    await act(async () => {
      render(
        <BowtieProvider
          initialBarriers={[INTEGRATION_BARRIER]}
          initialPredictions={{ 'int-barrier-001': INTEGRATION_PREDICTION }}
        >
          <SelectedBarrierSpy onId={spyFn} />
          <DashboardView />
        </BowtieProvider>,
      )
    })

    // Navigate to Ranked Barriers tab
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Ranked Barriers' }))
    })

    // Find and click the barrier row
    await act(async () => {
      const cell = screen.getByText('Integration Test Barrier')
      const row = cell.closest('tr')!
      fireEvent.click(row)
    })

    expect(spyFn).toHaveBeenCalledWith('int-barrier-001')
  })

  it('clicking a barrier row expands the row detail section', async () => {
    await act(async () => {
      render(
        <BowtieProvider
          initialBarriers={[INTEGRATION_BARRIER]}
          initialPredictions={{ 'int-barrier-001': INTEGRATION_PREDICTION }}
        >
          <DashboardView />
        </BowtieProvider>,
      )
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Ranked Barriers' }))
    })

    await act(async () => {
      const cell = screen.getByText('Integration Test Barrier')
      const row = cell.closest('tr')!
      fireEvent.click(row)
    })

    expect(screen.getByTestId('ranked-row-expanded')).toBeTruthy()
  })

  it('expanded row shows ShapWaterfall heading', async () => {
    await act(async () => {
      render(
        <BowtieProvider
          initialBarriers={[INTEGRATION_BARRIER]}
          initialPredictions={{ 'int-barrier-001': INTEGRATION_PREDICTION }}
        >
          <DashboardView />
        </BowtieProvider>,
      )
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Ranked Barriers' }))
    })

    await act(async () => {
      const cell = screen.getByText('Integration Test Barrier')
      const row = cell.closest('tr')!
      fireEvent.click(row)
    })

    // ShapWaterfall renders 'Barrier Analysis Factors' as its heading
    expect(screen.getByText('Barrier Analysis Factors')).toBeTruthy()
  })
})
