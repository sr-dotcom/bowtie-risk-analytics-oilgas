import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { predictCascading, rankTargets, explainCascading } from '@/lib/api'
import type {
  BarrierPrediction,
  CascadingRequest,
  DegradationContext,
  EvidenceSnippet,
  ExplainCascadingRequest,
  ExplainCascadingResponse,
  PredictCascadingResponse,
  RankTargetsResponse,
  Scenario,
} from '@/lib/types'
import PREDICT_CASCADING_FIXTURE from './fixtures/predict_cascading_response.json'

// ---------------------------------------------------------------------------
// Minimal stub scenario matching data/demo_scenarios/*.json shape
// ---------------------------------------------------------------------------

const STUB_SCENARIO: Scenario = {
  scenario_id: 'test-scenario-001',
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
      linked_threat_ids: ['T-001'],
      line_of_defense: '1st',
    },
    {
      control_id: 'C-002',
      name: 'Emergency Shutdown System',
      barrier_level: 'prevention',
      barrier_condition: 'effective',
      barrier_type: 'engineering',
      barrier_role: 'Isolate on high pressure signal',
      linked_threat_ids: ['T-001'],
      line_of_defense: '1st',
    },
  ],
  threats: [{ threat_id: 'T-001', name: 'Overpressurization', description: null }],
}

const STUB_REQUEST: CascadingRequest = {
  scenario: STUB_SCENARIO,
  conditioning_barrier_id: 'C-001',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeJsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

// ---------------------------------------------------------------------------
// Type shape verification against fixture
// ---------------------------------------------------------------------------

describe('PredictCascadingResponse fixture type shapes', () => {
  it('fixture has top-level predictions array and explanation_unavailable flag', () => {
    const fixture = PREDICT_CASCADING_FIXTURE as PredictCascadingResponse
    expect(Array.isArray(fixture.predictions)).toBe(true)
    expect(typeof fixture.explanation_unavailable).toBe('boolean')
  })

  it('each prediction has required BarrierPrediction fields', () => {
    const fixture = PREDICT_CASCADING_FIXTURE as PredictCascadingResponse
    for (const pred of fixture.predictions) {
      const p = pred as BarrierPrediction
      expect(typeof p.target_barrier_id).toBe('string')
      expect(typeof p.y_fail_probability).toBe('number')
      expect(['HIGH', 'MEDIUM', 'LOW']).toContain(p.risk_band)
      expect(Array.isArray(p.shap_values)).toBe(true)
    }
  })

  it('each shap_value has feature, value, and display_name', () => {
    const fixture = PREDICT_CASCADING_FIXTURE as PredictCascadingResponse
    for (const pred of fixture.predictions) {
      for (const sv of pred.shap_values) {
        expect(typeof sv.feature).toBe('string')
        expect(typeof sv.value).toBe('number')
        expect(typeof sv.display_name).toBe('string')
      }
    }
  })
})

// ---------------------------------------------------------------------------
// predictCascading
// ---------------------------------------------------------------------------

describe('predictCascading', () => {
  beforeEach(() => {
    vi.spyOn(global, 'fetch')
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('POSTs to /api/predict-cascading with correct body', async () => {
    const mockFetch = vi.mocked(global.fetch)
    mockFetch.mockResolvedValueOnce(makeJsonResponse(PREDICT_CASCADING_FIXTURE))

    await predictCascading(STUB_REQUEST)

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/predict-cascading',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(STUB_REQUEST),
      }),
    )
  })

  it('returns a PredictCascadingResponse matching the fixture shape', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(makeJsonResponse(PREDICT_CASCADING_FIXTURE))

    const result = await predictCascading(STUB_REQUEST)
    expect(result.predictions).toHaveLength(2)
    expect(result.predictions[0].target_barrier_id).toBe('C-002')
    expect(result.predictions[0].risk_band).toBe('HIGH')
    expect(result.explanation_unavailable).toBe(false)
  })

  it('throws on non-OK response', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(new Response('error', { status: 500 }))
    await expect(predictCascading(STUB_REQUEST)).rejects.toThrow('Cascading prediction failed: 500')
  })
})

// ---------------------------------------------------------------------------
// rankTargets
// ---------------------------------------------------------------------------

describe('rankTargets', () => {
  beforeEach(() => {
    vi.spyOn(global, 'fetch')
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('POSTs to /api/rank-targets', async () => {
    const mockFetch = vi.mocked(global.fetch)
    const body: RankTargetsResponse = {
      ranked_barriers: [{ target_barrier_id: 'C-002', composite_risk_score: 0.9 }],
    }
    mockFetch.mockResolvedValueOnce(makeJsonResponse(body))

    await rankTargets(STUB_REQUEST)
    expect(mockFetch).toHaveBeenCalledWith('/api/rank-targets', expect.objectContaining({ method: 'POST' }))
  })

  it('returns ranked_barriers array with target_barrier_id and composite_risk_score', async () => {
    const body: RankTargetsResponse = {
      ranked_barriers: [
        { target_barrier_id: 'C-002', composite_risk_score: 0.9 },
        { target_barrier_id: 'C-003', composite_risk_score: 0.4 },
      ],
    }
    vi.mocked(global.fetch).mockResolvedValueOnce(makeJsonResponse(body))

    const result = await rankTargets(STUB_REQUEST)
    expect(result.ranked_barriers).toHaveLength(2)
    expect(result.ranked_barriers[0].target_barrier_id).toBe('C-002')
    expect(result.ranked_barriers[0].composite_risk_score).toBe(0.9)
  })
})

// ---------------------------------------------------------------------------
// explainCascading
// ---------------------------------------------------------------------------

const STUB_EXPLAIN_RESPONSE: ExplainCascadingResponse = {
  narrative_text: 'Historical data shows this barrier type commonly fails in cascading scenarios.',
  evidence_snippets: [
    { incident_id: 'bsee-2015-001', source_agency: 'BSEE', text: 'PSV failed to lift at set pressure.', score: 0.85 },
  ],
  degradation_context: {
    pif_mentions: ['Procedures', 'Situational Awareness'],
    recommendations: ['Verify PSV calibration quarterly', 'Review MOC for pressure changes'],
    barrier_condition: 'ineffective',
  },
  narrative_unavailable: false,
}

describe('explainCascading', () => {
  beforeEach(() => {
    vi.spyOn(global, 'fetch')
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('POSTs to /api/explain-cascading with correct body', async () => {
    const mockFetch = vi.mocked(global.fetch)
    mockFetch.mockResolvedValueOnce(makeJsonResponse(STUB_EXPLAIN_RESPONSE))

    const req: ExplainCascadingRequest = {
      conditioning_barrier_id: 'C-001',
      target_barrier_id: 'C-002',
      bowtie_context: STUB_SCENARIO,
    }
    await explainCascading(req)

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/explain-cascading',
      expect.objectContaining({ method: 'POST', body: JSON.stringify(req) }),
    )
  })

  it('returns ExplainCascadingResponse with narrative_text, evidence_snippets, degradation_context', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(makeJsonResponse(STUB_EXPLAIN_RESPONSE))

    const result = await explainCascading({
      conditioning_barrier_id: 'C-001',
      target_barrier_id: 'C-002',
      bowtie_context: STUB_SCENARIO,
    })
    expect(result.narrative_text).toBe(STUB_EXPLAIN_RESPONSE.narrative_text)
    expect(result.evidence_snippets).toHaveLength(1)
    expect(result.evidence_snippets[0].incident_id).toBe('bsee-2015-001')
    expect(result.degradation_context.pif_mentions).toContain('Procedures')
    expect(result.narrative_unavailable).toBe(false)
  })

  it('passes AbortSignal to fetch when provided', async () => {
    const mockFetch = vi.mocked(global.fetch)
    mockFetch.mockResolvedValueOnce(makeJsonResponse(STUB_EXPLAIN_RESPONSE))
    const controller = new AbortController()

    await explainCascading(
      { conditioning_barrier_id: 'C-001', target_barrier_id: 'C-002', bowtie_context: STUB_SCENARIO },
      controller.signal,
    )
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/explain-cascading',
      expect.objectContaining({ signal: controller.signal }),
    )
  })

  it('throws on non-OK response', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(new Response('', { status: 503 }))
    await expect(
      explainCascading({ conditioning_barrier_id: 'C-001', target_barrier_id: 'C-002', bowtie_context: STUB_SCENARIO }),
    ).rejects.toThrow('Cascading explanation failed: 503')
  })
})
