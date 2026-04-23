/**
 * CrossLink.test.tsx
 *
 * End-to-end tests for bidirectional cross-link navigation:
 *   - "View on Diagram" (RankedBarriers → diagram view)
 *   - "View Full Analysis" (DetailPanel → dashboard ranked-barriers tab)
 *   - DashboardView consuming dashboardTab from context
 *   - RankedBarriers auto-expanding selectedBarrierId on mount
 *
 * Mounts REAL components inside BowtieProvider — no component mocks.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { useEffect } from 'react'
import { BowtieProvider, useBowtieContext } from '@/context/BowtieContext'
import type { Barrier, PredictResponse, ShapValue } from '@/lib/types'

// ---------------------------------------------------------------------------
// Module-level mocks (hoisted before component imports)
// ---------------------------------------------------------------------------

// RankedBarriers (inside DashboardView) can trigger explain via EvidenceSection
const mockExplain = vi.hoisted(() => vi.fn())

// DashboardView imports useAnalyzeBarriers — mock to prevent real API calls
const mockAnalyzeAll = vi.hoisted(() => vi.fn())
vi.mock('@/hooks/useAnalyzeBarriers', () => ({
  useAnalyzeBarriers: () => ({ analyzeAll: mockAnalyzeAll }),
}))

// AprioriRulesTable (inside DashboardView Drivers & HF tab) makes network calls
const mockFetchAprioriRules = vi.hoisted(() => vi.fn())
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual('@/lib/api')
  return { ...actual, explain: mockExplain, fetchAprioriRules: mockFetchAprioriRules }
})

// ---------------------------------------------------------------------------
// Component imports AFTER vi.mock declarations
// ---------------------------------------------------------------------------

import RankedBarriers from '@/components/dashboard/RankedBarriers'
import DetailPanel from '@/components/panel/DetailPanel'
import DashboardView from '@/components/dashboard/DashboardView'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeShap(feature: string, value: number): ShapValue {
  return { feature, value, category: 'barrier' }
}

const BARRIER_DEF: Omit<Barrier, 'id' | 'riskLevel'> = {
  name: 'Pressure Relief Valve',
  side: 'prevention',
  barrier_type: 'engineering',
  barrier_family: 'pressure_relief',
  line_of_defense: '1st',
  barrierRole: 'prevent overpressure',
}

const BARRIER: Barrier = {
  id: 'xlink-b001',
  name: 'Pressure Relief Valve',
  side: 'prevention',
  barrier_type: 'engineering',
  barrier_family: 'pressure_relief',
  line_of_defense: '1st',
  barrierRole: 'prevent overpressure',
  riskLevel: 'red',
  probability: 0.82,
}

const PREDICTION: PredictResponse = {
  model1_probability: 0.82,
  model2_probability: 0.3,
  model1_shap: [makeShap('barrier_family', 0.25), makeShap('side', 0.1)],
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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * ContextSpy: renders key context values as testid spans for assertion.
 */
function ContextSpy() {
  const { viewMode, dashboardTab } = useBowtieContext()
  return (
    <div>
      <span data-testid="ctx-viewMode">{viewMode}</span>
      <span data-testid="ctx-dashboardTab">{dashboardTab ?? '__null__'}</span>
    </div>
  )
}

/**
 * Sets selectedBarrierId in context on mount (before children render) so
 * DetailPanel sees a selected barrier without requiring a click.
 */
function SelectBarrier({ barrierId }: { barrierId: string }) {
  const { setSelectedBarrierId } = useBowtieContext()
  useEffect(() => {
    setSelectedBarrierId(barrierId)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

// ---------------------------------------------------------------------------
// Test 1: "View on Diagram" in RankedBarriers calls setViewMode('diagram')
// ---------------------------------------------------------------------------

describe('CrossLink — View on Diagram', () => {
  beforeEach(() => {
    mockExplain.mockClear()
    mockExplain.mockResolvedValue({
      narrative: 'No evidence.',
      citations: [],
      retrieval_confidence: 0.5,
      model_used: 'stub',
      recommendations: '',
    })
    mockAnalyzeAll.mockClear()
    mockFetchAprioriRules.mockClear()
  })

  it('clicking "View on Diagram" in an expanded RankedBarriers row sets viewMode to "diagram"', async () => {
    render(
      <BowtieProvider
        initialBarriers={[BARRIER]}
        initialPredictions={{ [BARRIER.id]: PREDICTION }}
        initialViewMode="dashboard"
      >
        <RankedBarriers />
        <ContextSpy />
      </BowtieProvider>,
    )

    // Initial state: dashboard
    expect(screen.getByTestId('ctx-viewMode').textContent).toBe('dashboard')

    // Find and click the barrier row to expand it
    const row = screen.getByText('Pressure Relief Valve').closest('tr')!
    fireEvent.click(row)

    // Expanded row should be visible with the "View on Diagram" button
    expect(screen.getByTestId('ranked-row-expanded')).toBeTruthy()
    const btn = screen.getByTestId('view-on-diagram-btn')
    expect(btn).toBeTruthy()

    // Click the cross-link button
    fireEvent.click(btn)

    // Context should now reflect 'diagram'
    expect(screen.getByTestId('ctx-viewMode').textContent).toBe('diagram')
  })
})

// ---------------------------------------------------------------------------
// Test 2: "View Full Analysis" in DetailPanel sets viewMode + dashboardTab
// ---------------------------------------------------------------------------

describe('CrossLink — View Full Analysis', () => {
  beforeEach(() => {
    mockExplain.mockClear()
    mockAnalyzeAll.mockClear()
    mockFetchAprioriRules.mockClear()
  })

  it('clicking "View Full Analysis" in DetailPanel sets viewMode to "dashboard" and dashboardTab to "ranked-barriers"', () => {
    render(
      <BowtieProvider
        initialBarriers={[BARRIER]}
        initialPredictions={{ [BARRIER.id]: PREDICTION }}
        initialViewMode="diagram"
      >
        {/* SelectBarrier sets selectedBarrierId so DetailPanel renders the analysis view */}
        <SelectBarrier barrierId={BARRIER.id} />
        <DetailPanel />
        <ContextSpy />
      </BowtieProvider>,
    )

    // DetailPanel should render the "View Full Analysis" button once barrier + pred are available
    const btn = screen.getByTestId('view-full-analysis-btn')
    expect(btn).toBeTruthy()

    // Verify initial context state
    expect(screen.getByTestId('ctx-viewMode').textContent).toBe('diagram')
    expect(screen.getByTestId('ctx-dashboardTab').textContent).toBe('__null__')

    // Click the button
    fireEvent.click(btn)

    // Both context fields must update
    expect(screen.getByTestId('ctx-viewMode').textContent).toBe('dashboard')
    expect(screen.getByTestId('ctx-dashboardTab').textContent).toBe('ranked-barriers')
  })
})

// ---------------------------------------------------------------------------
// Test 3: DashboardView consumes dashboardTab and switches to ranked-barriers
// ---------------------------------------------------------------------------

describe('CrossLink — DashboardView consumes dashboardTab', () => {
  beforeEach(() => {
    mockAnalyzeAll.mockClear()
    mockFetchAprioriRules.mockResolvedValue({ rules: [], n_incidents: 0, generated_at: '' })
    mockExplain.mockClear()
    mockExplain.mockResolvedValue({
      narrative: '',
      citations: [],
      retrieval_confidence: 0,
      model_used: 'stub',
      recommendations: '',
    })
  })

  it('DashboardView switches to ranked-barriers tab when initialDashboardTab is "ranked-barriers"', async () => {
    await act(async () => {
      render(
        <BowtieProvider
          initialBarriers={[BARRIER]}
          initialPredictions={{ [BARRIER.id]: PREDICTION }}
          initialDashboardTab="ranked-barriers"
        >
          <DashboardView />
          <ContextSpy />
        </BowtieProvider>,
      )
    })

    // The ranked-barriers tab content should be visible (RankedBarriers renders its testid)
    expect(screen.getByTestId('ranked-barriers-table')).toBeTruthy()

    // DashboardView should have consumed (cleared) dashboardTab
    expect(screen.getByTestId('ctx-dashboardTab').textContent).toBe('__null__')
  })
})

// ---------------------------------------------------------------------------
// Test 4: RankedBarriers auto-expands selectedBarrierId on mount
// ---------------------------------------------------------------------------

describe('CrossLink — RankedBarriers auto-expands on mount', () => {
  beforeEach(() => {
    mockExplain.mockClear()
    mockExplain.mockResolvedValue({
      narrative: '',
      citations: [],
      retrieval_confidence: 0,
      model_used: 'stub',
      recommendations: '',
    })
    mockAnalyzeAll.mockClear()
    mockFetchAprioriRules.mockClear()
  })

  it('auto-expands the row matching selectedBarrierId without any manual click', () => {
    // initialSelectedBarrierId seeds selectedBarrierId at construction time so
    // RankedBarriers' mount-only useEffect([]) sees the value immediately.
    render(
      <BowtieProvider
        initialBarriers={[BARRIER]}
        initialPredictions={{ [BARRIER.id]: PREDICTION }}
        initialViewMode="dashboard"
        initialSelectedBarrierId={BARRIER.id}
      >
        <RankedBarriers />
      </BowtieProvider>,
    )

    // The expanded row testid should be present without clicking
    expect(screen.getByTestId('ranked-row-expanded')).toBeTruthy()
  })
})
