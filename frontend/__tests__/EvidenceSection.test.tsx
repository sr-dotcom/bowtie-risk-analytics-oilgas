import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { BowtieProvider } from '@/context/BowtieContext'
import type { Barrier, ExplainResponse, PredictResponse, ShapValue } from '@/lib/types'

// ---------------------------------------------------------------------------
// Mock explain from @/lib/api — EvidenceSection calls this on mount.
// vi.hoisted ensures the mock variable is available inside the vi.mock factory,
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

import EvidenceSection from '@/components/panel/EvidenceSection'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

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

function makeExplainResponse(overrides: Partial<ExplainResponse> = {}): ExplainResponse {
  return {
    narrative: 'Historical evidence shows pressure relief failures are common.',
    citations: [],
    retrieval_confidence: 0.75,
    model_used: 'claude-haiku',
    recommendations: '',
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

const DEFAULT_BARRIER = makeBarrier()
const DEFAULT_PREDICTION = makePrediction()

function renderEvidenceSection(
  barrierId: string = DEFAULT_BARRIER.id,
  barrier: Barrier = DEFAULT_BARRIER,
  prediction: PredictResponse = DEFAULT_PREDICTION,
) {
  return render(
    <BowtieProvider>
      <EvidenceSection
        barrierId={barrierId}
        barrier={barrier}
        eventDescription="Pipeline rupture at compressor station"
        prediction={prediction}
      />
    </BowtieProvider>,
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('EvidenceSection — confidence dot', () => {
  beforeEach(() => {
    mockExplain.mockClear()
  })

  it('renders confidence-dot testid when evidence loads', async () => {
    mockExplain.mockResolvedValue(makeExplainResponse({ retrieval_confidence: 0.75 }))
    renderEvidenceSection()
    const dot = await screen.findByTestId('confidence-dot')
    expect(dot).toBeTruthy()
  })

  it('confidence dot has risk-low class for retrieval_confidence >= 0.7', async () => {
    mockExplain.mockResolvedValue(makeExplainResponse({ retrieval_confidence: 0.7 }))
    renderEvidenceSection()
    const dot = await screen.findByTestId('confidence-dot')
    expect(dot.className).toContain('bg-[#1F6F43]')
  })

  it('confidence dot has risk-low class for retrieval_confidence above 0.7', async () => {
    mockExplain.mockResolvedValue(makeExplainResponse({ retrieval_confidence: 0.9 }))
    renderEvidenceSection()
    const dot = await screen.findByTestId('confidence-dot')
    expect(dot.className).toContain('bg-[#1F6F43]')
  })

  it('confidence dot has risk-medium class for retrieval_confidence in [0.4, 0.7)', async () => {
    mockExplain.mockResolvedValue(makeExplainResponse({ retrieval_confidence: 0.55 }))
    renderEvidenceSection()
    const dot = await screen.findByTestId('confidence-dot')
    expect(dot.className).toContain('bg-[#996515]')
  })

  it('confidence dot has risk-medium class at the exact 0.4 boundary', async () => {
    mockExplain.mockResolvedValue(makeExplainResponse({ retrieval_confidence: 0.4 }))
    renderEvidenceSection()
    const dot = await screen.findByTestId('confidence-dot')
    expect(dot.className).toContain('bg-[#996515]')
  })

  it('confidence dot has risk-high class for retrieval_confidence < 0.4', async () => {
    mockExplain.mockResolvedValue(makeExplainResponse({ retrieval_confidence: 0.2 }))
    renderEvidenceSection()
    const dot = await screen.findByTestId('confidence-dot')
    expect(dot.className).toContain('bg-[#C0392B]')
  })
})

describe('EvidenceSection — recommendations cards', () => {
  beforeEach(() => {
    mockExplain.mockClear()
  })

  it('renders recommendations section when recommendations is non-empty multi-line', async () => {
    mockExplain.mockResolvedValue(
      makeExplainResponse({
        retrieval_confidence: 0.8,
        recommendations: '- Inspect relief valve quarterly\n- Train operators on pressure limits\n- Install redundant shutdown',
      }),
    )
    renderEvidenceSection()
    await screen.findByTestId('confidence-dot')
    expect(screen.getByText('Recommendations')).toBeTruthy()
  })

  it('each recommendation line renders in its own card (count matches line count)', async () => {
    mockExplain.mockResolvedValue(
      makeExplainResponse({
        retrieval_confidence: 0.8,
        recommendations: '- First recommendation\n- Second recommendation\n- Third recommendation',
      }),
    )
    renderEvidenceSection()
    await screen.findByTestId('confidence-dot')
    // Three lines → three cards with border-blue-500
    const cards = document.querySelectorAll('.border-blue-500')
    expect(cards.length).toBe(3)
  })

  it('each card has border-blue-500 class', async () => {
    mockExplain.mockResolvedValue(
      makeExplainResponse({
        retrieval_confidence: 0.8,
        recommendations: '- Check valve integrity\n- Review maintenance log',
      }),
    )
    renderEvidenceSection()
    await screen.findByTestId('confidence-dot')
    const cards = document.querySelectorAll('.border-blue-500')
    expect(cards.length).toBeGreaterThan(0)
    cards.forEach((card) => {
      expect(card.className).toContain('border-blue-500')
    })
  })

  it('card text content matches parsed recommendation text (strips list marker)', async () => {
    mockExplain.mockResolvedValue(
      makeExplainResponse({
        retrieval_confidence: 0.8,
        recommendations: '- Inspect relief valve quarterly',
      }),
    )
    renderEvidenceSection()
    await screen.findByTestId('confidence-dot')
    expect(screen.getByText('Inspect relief valve quarterly')).toBeTruthy()
  })

  it('renders no recommendation cards when recommendations is empty string', async () => {
    mockExplain.mockResolvedValue(
      makeExplainResponse({
        retrieval_confidence: 0.8,
        recommendations: '',
      }),
    )
    renderEvidenceSection()
    await screen.findByTestId('confidence-dot')
    expect(document.querySelectorAll('.border-blue-500').length).toBe(0)
    expect(screen.queryByText('Recommendations')).toBeNull()
  })

  it('renders no recommendation cards when recommendations field is missing (undefined)', async () => {
    const response = makeExplainResponse({ retrieval_confidence: 0.8 })
    // Simulate missing field by deleting the key
    delete (response as Partial<ExplainResponse>).recommendations
    mockExplain.mockResolvedValue(response)
    renderEvidenceSection()
    await screen.findByTestId('confidence-dot')
    expect(document.querySelectorAll('.border-blue-500').length).toBe(0)
  })
})

describe('EvidenceSection — low confidence banner and narrative', () => {
  beforeEach(() => {
    mockExplain.mockClear()
  })

  it('low-confidence amber banner renders when retrieval_confidence < 0.4', async () => {
    mockExplain.mockResolvedValue(
      makeExplainResponse({
        retrieval_confidence: 0.2,
        narrative: 'No matching incidents found.',
      }),
    )
    renderEvidenceSection()
    await screen.findByTestId('confidence-dot')
    // The amber warning paragraph
    expect(
      screen.getByText(/No matching incidents found.*low confidence/i),
    ).toBeTruthy()
  })

  it('narrative renders in place of amber banner when confidence is adequate (>= 0.4)', async () => {
    const narrative = 'Historical evidence shows pressure relief failures are common.'
    mockExplain.mockResolvedValue(
      makeExplainResponse({
        retrieval_confidence: 0.6,
        narrative,
      }),
    )
    renderEvidenceSection()
    await screen.findByTestId('confidence-dot')
    expect(screen.getByText(narrative)).toBeTruthy()
    // The amber warning paragraph should NOT appear
    expect(screen.queryByText(/low confidence/i)).toBeNull()
  })

  it('explain API is called exactly once on mount', async () => {
    mockExplain.mockResolvedValue(makeExplainResponse())
    renderEvidenceSection()
    await screen.findByTestId('confidence-dot')
    expect(mockExplain).toHaveBeenCalledOnce()
  })

  it('evidence cached in context is not re-fetched on re-render', async () => {
    mockExplain.mockResolvedValue(makeExplainResponse())
    const { rerender } = renderEvidenceSection()
    await screen.findByTestId('confidence-dot')
    // Re-render without unmounting — should not call explain again
    await act(async () => {
      rerender(
        <BowtieProvider>
          <EvidenceSection
            barrierId={DEFAULT_BARRIER.id}
            barrier={DEFAULT_BARRIER}
            eventDescription="Pipeline rupture at compressor station"
            prediction={DEFAULT_PREDICTION}
          />
        </BowtieProvider>,
      )
    })
    expect(mockExplain).toHaveBeenCalledOnce()
  })
})

describe('EvidenceSection — Similar Incidents dedup count', () => {
  beforeEach(() => {
    mockExplain.mockClear()
  })

  it('renders unique incident count, not raw citation count, in Similar Incidents label', async () => {
    // 3 citations from 2 unique incidents — label should show (2) not (3)
    const citations = [
      { incident_id: 'INC-001', control_id: 'C-1', barrier_name: 'Valve', barrier_family: 'relief', supporting_text: 'text', relevance_score: 0.9, incident_summary: 'summary' },
      { incident_id: 'INC-001', control_id: 'C-2', barrier_name: 'Valve2', barrier_family: 'relief', supporting_text: 'text2', relevance_score: 0.8, incident_summary: 'summary' },
      { incident_id: 'INC-002', control_id: 'C-3', barrier_name: 'Sensor', barrier_family: 'detection', supporting_text: 'text3', relevance_score: 0.7, incident_summary: 'summary' },
    ]
    mockExplain.mockResolvedValue(makeExplainResponse({ retrieval_confidence: 0.8, citations }))
    renderEvidenceSection()
    await screen.findByTestId('confidence-dot')
    expect(screen.getByText(/Similar Incidents \(2\)/)).toBeTruthy()
  })
})
