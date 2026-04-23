import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { Barrier, ExplainCascadingResponse, PredictResponse, ShapValue } from '@/lib/types'

// ---------------------------------------------------------------------------
// Mock useBowtieContext — EvidenceSection reads explanation state from context.
// vi.hoisted ensures the mock variable is available inside the factory before
// imports are resolved.
// ---------------------------------------------------------------------------

const mockUseBowtieContext = vi.hoisted(() => vi.fn())
vi.mock('@/context/BowtieContext', async () => {
  const actual = await vi.importActual('@/context/BowtieContext')
  return { ...actual, useBowtieContext: mockUseBowtieContext }
})

// ---------------------------------------------------------------------------
// Import component AFTER vi.mock
// ---------------------------------------------------------------------------

import EvidenceSection from '@/components/panel/EvidenceSection'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeExplainCascadingResponse(
  overrides: Partial<ExplainCascadingResponse> = {},
): ExplainCascadingResponse {
  return {
    narrative_text: 'Historical evidence shows pressure relief failures are common.',
    evidence_snippets: [],
    degradation_context: {
      pif_mentions: [],
      recommendations: [],
      barrier_condition: 'nominal',
    },
    narrative_unavailable: false,
    snippet_count: 0,
    unique_incident_count: 0,
    ...overrides,
  }
}

function makeContextState(overrides: Record<string, unknown> = {}) {
  return {
    conditioningBarrierId: 'B-cond-001',
    explanation: null,
    explanationLoading: false,
    explanationError: null,
    narrativeUnavailable: false,
    ...overrides,
  }
}

function makeBarrier(overrides: Partial<Barrier> = {}): Barrier {
  return {
    id: 'b-test-001',
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

function makePrediction(overrides: Partial<PredictResponse> = {}): PredictResponse {
  return {
    model1_probability: 0.5,
    model2_probability: 0.2,
    model1_shap: [] as ShapValue[],
    model2_shap: [] as ShapValue[],
    model1_base_value: 0.1,
    model2_base_value: 0.1,
    feature_metadata: [],
    degradation_factors: [],
    risk_level: 'Medium',
    barrier_type_display: 'Administrative',
    lod_display: '1st',
    barrier_condition_display: 'Nominal',
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// Render helper — no BowtieProvider needed since useBowtieContext is mocked
// ---------------------------------------------------------------------------

const DEFAULT_BARRIER = makeBarrier()
const DEFAULT_PREDICTION = makePrediction()

function renderEvidenceSection(
  barrierId: string = DEFAULT_BARRIER.id,
  barrier: Barrier = DEFAULT_BARRIER,
  prediction: PredictResponse = DEFAULT_PREDICTION,
) {
  return render(
    <EvidenceSection
      barrierId={barrierId}
      barrier={barrier}
      eventDescription="Pipeline rupture at compressor station"
      prediction={prediction}
    />,
  )
}

// ---------------------------------------------------------------------------
// Tests — guard clause (no conditioning barrier)
// ---------------------------------------------------------------------------

describe('EvidenceSection — guard clause', () => {
  it('shows placeholder when conditioningBarrierId is null', () => {
    mockUseBowtieContext.mockReturnValue(makeContextState({ conditioningBarrierId: null }))
    renderEvidenceSection()
    expect(
      screen.getByText(/Click a barrier.*conditioning context/i),
    ).toBeTruthy()
  })

  it('does not render the Evidence header when no conditioning barrier is set', () => {
    mockUseBowtieContext.mockReturnValue(makeContextState({ conditioningBarrierId: null }))
    renderEvidenceSection()
    expect(screen.queryByText('Evidence')).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Tests — loading and error states
// ---------------------------------------------------------------------------

describe('EvidenceSection — loading and error states', () => {
  it('shows spinner when explanationLoading is true', () => {
    mockUseBowtieContext.mockReturnValue(makeContextState({ explanationLoading: true }))
    renderEvidenceSection()
    expect(screen.getByText('Loading evidence...')).toBeTruthy()
  })

  it('shows error message when explanationError is set', () => {
    mockUseBowtieContext.mockReturnValue(
      makeContextState({ explanationError: 'Cascading explanation failed: 500 Internal Server Error' }),
    )
    renderEvidenceSection()
    expect(screen.getByText(/Cascading explanation failed/i)).toBeTruthy()
  })

  it('shows no-data placeholder when explanation is null (after conditioning set)', () => {
    mockUseBowtieContext.mockReturnValue(makeContextState({ explanation: null }))
    renderEvidenceSection()
    expect(screen.getByText(/Select a barrier.*Analyze/i)).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// Tests — confidence dot
// ---------------------------------------------------------------------------

describe('EvidenceSection — confidence dot', () => {
  beforeEach(() => {
    mockUseBowtieContext.mockReturnValue(
      makeContextState({
        explanation: makeExplainCascadingResponse({ unique_incident_count: 3 }),
      }),
    )
  })

  it('renders confidence-dot testid when explanation loads', () => {
    renderEvidenceSection()
    expect(screen.getByTestId('confidence-dot')).toBeTruthy()
  })

  it('confidence dot is green when unique_incident_count > 0 and narrative is available', () => {
    mockUseBowtieContext.mockReturnValue(
      makeContextState({
        explanation: makeExplainCascadingResponse({ unique_incident_count: 3 }),
        narrativeUnavailable: false,
      }),
    )
    renderEvidenceSection()
    expect(screen.getByTestId('confidence-dot').className).toContain('bg-[#1F6F43]')
  })

  it('confidence dot is amber when unique_incident_count === 0 and narrative is available', () => {
    mockUseBowtieContext.mockReturnValue(
      makeContextState({
        explanation: makeExplainCascadingResponse({
          unique_incident_count: 0,
          narrative_text: 'Some analysis text.',
        }),
        narrativeUnavailable: false,
      }),
    )
    renderEvidenceSection()
    expect(screen.getByTestId('confidence-dot').className).toContain('bg-[#996515]')
  })

  it('confidence dot is red when narrativeUnavailable is true', () => {
    mockUseBowtieContext.mockReturnValue(
      makeContextState({
        explanation: makeExplainCascadingResponse({ narrative_unavailable: true }),
        narrativeUnavailable: true,
      }),
    )
    renderEvidenceSection()
    expect(screen.getByTestId('confidence-dot').className).toContain('bg-[#C0392B]')
  })
})

// ---------------------------------------------------------------------------
// Tests — narrative rendering and low confidence banner
// ---------------------------------------------------------------------------

describe('EvidenceSection — narrative and low confidence', () => {
  it('renders narrative_text when explanation is available and narrative is not unavailable', () => {
    const narrative = 'Historical evidence shows pressure relief failures are common.'
    mockUseBowtieContext.mockReturnValue(
      makeContextState({
        explanation: makeExplainCascadingResponse({
          narrative_text: narrative,
          unique_incident_count: 2,
        }),
        narrativeUnavailable: false,
      }),
    )
    renderEvidenceSection()
    expect(screen.getByText(narrative)).toBeTruthy()
    expect(screen.queryByText(/low confidence/i)).toBeNull()
  })

  it('shows amber banner when narrativeUnavailable is true', () => {
    mockUseBowtieContext.mockReturnValue(
      makeContextState({
        explanation: makeExplainCascadingResponse({ narrative_unavailable: true }),
        narrativeUnavailable: true,
      }),
    )
    renderEvidenceSection()
    expect(screen.getByText(/No matching incidents found.*low confidence/i)).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// Tests — recommendations cards (degradation_context.recommendations string[])
// ---------------------------------------------------------------------------

describe('EvidenceSection — recommendations cards', () => {
  it('renders recommendations section when degradation_context.recommendations is non-empty', () => {
    mockUseBowtieContext.mockReturnValue(
      makeContextState({
        explanation: makeExplainCascadingResponse({
          unique_incident_count: 2,
          degradation_context: {
            pif_mentions: [],
            recommendations: [
              'Inspect relief valve quarterly',
              'Train operators on pressure limits',
              'Install redundant shutdown',
            ],
            barrier_condition: 'degraded',
          },
        }),
      }),
    )
    renderEvidenceSection()
    expect(screen.getByText('Recommendations')).toBeTruthy()
  })

  it('each recommendation renders in its own card (count matches array length)', () => {
    mockUseBowtieContext.mockReturnValue(
      makeContextState({
        explanation: makeExplainCascadingResponse({
          unique_incident_count: 2,
          degradation_context: {
            pif_mentions: [],
            recommendations: ['First recommendation', 'Second recommendation', 'Third recommendation'],
            barrier_condition: 'degraded',
          },
        }),
      }),
    )
    renderEvidenceSection()
    expect(document.querySelectorAll('.border-blue-500').length).toBe(3)
  })

  it('each card has border-blue-500 class', () => {
    mockUseBowtieContext.mockReturnValue(
      makeContextState({
        explanation: makeExplainCascadingResponse({
          unique_incident_count: 2,
          degradation_context: {
            pif_mentions: [],
            recommendations: ['Check valve integrity', 'Review maintenance log'],
            barrier_condition: 'degraded',
          },
        }),
      }),
    )
    renderEvidenceSection()
    const cards = document.querySelectorAll('.border-blue-500')
    expect(cards.length).toBeGreaterThan(0)
    cards.forEach((card) => expect(card.className).toContain('border-blue-500'))
  })

  it('card text content renders the recommendation string verbatim (no list-marker stripping needed)', () => {
    mockUseBowtieContext.mockReturnValue(
      makeContextState({
        explanation: makeExplainCascadingResponse({
          unique_incident_count: 2,
          degradation_context: {
            pif_mentions: [],
            recommendations: ['Inspect relief valve quarterly'],
            barrier_condition: 'degraded',
          },
        }),
      }),
    )
    renderEvidenceSection()
    expect(screen.getByText('Inspect relief valve quarterly')).toBeTruthy()
  })

  it('renders no recommendation section when recommendations is empty array', () => {
    mockUseBowtieContext.mockReturnValue(
      makeContextState({
        explanation: makeExplainCascadingResponse({
          unique_incident_count: 2,
          degradation_context: { pif_mentions: [], recommendations: [], barrier_condition: 'nominal' },
        }),
      }),
    )
    renderEvidenceSection()
    expect(screen.queryByText('Recommendations')).toBeNull()
    expect(document.querySelectorAll('.border-blue-500').length).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// Tests — Similar Incidents uses API-sourced unique_incident_count
// ---------------------------------------------------------------------------

describe('EvidenceSection — Similar Incidents count', () => {
  it('uses unique_incident_count for the label, not snippets.length or local Set dedup', () => {
    // 5 snippets from 4+ distinct incidents, but unique_incident_count=2 per API
    mockUseBowtieContext.mockReturnValue(
      makeContextState({
        explanation: makeExplainCascadingResponse({
          unique_incident_count: 2,
          snippet_count: 5,
          evidence_snippets: [
            { incident_id: 'INC-001', source_agency: 'CSB', text: 'text1', score: 0.9 },
            { incident_id: 'INC-001', source_agency: 'CSB', text: 'text2', score: 0.8 },
            { incident_id: 'INC-002', source_agency: 'BSEE', text: 'text3', score: 0.7 },
            { incident_id: 'INC-003', source_agency: 'BSEE', text: 'text4', score: 0.6 },
            { incident_id: 'INC-004', source_agency: 'CSB', text: 'text5', score: 0.5 },
          ],
        }),
      }),
    )
    renderEvidenceSection()
    // Label must show API-sourced unique_incident_count=2, not snippet_count=5 or Set-dedup=4
    expect(screen.getByText(/Similar Incidents \(2\)/)).toBeTruthy()
  })
})
