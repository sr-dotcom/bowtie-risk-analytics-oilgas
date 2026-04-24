import { describe, it, expect } from 'vitest'
import {
  buildTopAtRiskBarriers,
  buildAverageRiskItems,
  SHAP_HIDDEN_FEATURES,
} from '@/components/dashboard/TopAtRiskBarriers'
import type { Barrier, PredictResponse, ShapValue } from '@/lib/types'

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
    barrier_condition_display: '',
  }
}

function makeShap(feature: string, value: number): ShapValue {
  return { feature, value, category: 'barrier' }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('SHAP_HIDDEN_FEATURES', () => {
  it('contains primary_threat_category (source_agency removed from model)', () => {
    expect(SHAP_HIDDEN_FEATURES.has('primary_threat_category')).toBe(true)
    // source_agency is no longer in the model — not needed in the hidden set
    expect(SHAP_HIDDEN_FEATURES.has('source_agency')).toBe(false)
  })
})

describe('buildTopAtRiskBarriers', () => {
  it('returns [] for empty barriers array', () => {
    expect(buildTopAtRiskBarriers([], {})).toEqual([])
  })

  it('returns [] when no barriers have predictions', () => {
    const barriers = [makeBarrier(), makeBarrier()]
    expect(buildTopAtRiskBarriers(barriers, {})).toEqual([])
  })

  it('returns all 3 barriers sorted by probability descending when 3 have predictions', () => {
    const b1 = makeBarrier({ name: 'B1' })
    const b2 = makeBarrier({ name: 'B2' })
    const b3 = makeBarrier({ name: 'B3' })
    const predictions = {
      [b1.id]: makePrediction(0.4),
      [b2.id]: makePrediction(0.9),
      [b3.id]: makePrediction(0.6),
    }
    const result = buildTopAtRiskBarriers([b1, b2, b3], predictions)
    expect(result).toHaveLength(3)
    expect(result[0].barrier.name).toBe('B2')
    expect(result[1].barrier.name).toBe('B3')
    expect(result[2].barrier.name).toBe('B1')
  })

  it('returns top 5 only when 7 barriers have predictions', () => {
    const barriers = Array.from({ length: 7 }, (_, i) =>
      makeBarrier({ name: `B${i}` }),
    )
    const predictions: Record<string, PredictResponse> = {}
    barriers.forEach((b, i) => {
      predictions[b.id] = makePrediction(i * 0.1)
    })
    const result = buildTopAtRiskBarriers(barriers, predictions)
    expect(result).toHaveLength(5)
    // Highest probability should be first (barrier at index 6 has 0.6)
    expect(result[0].probability).toBeCloseTo(0.6)
  })

  it('correctly identifies the top SHAP factor by highest absolute value', () => {
    const b = makeBarrier()
    const shap: ShapValue[] = [
      makeShap('barrier_type', 0.05),
      makeShap('barrier_family', -0.3),
      makeShap('supporting_text_count', 0.1),
    ]
    const predictions = { [b.id]: makePrediction(0.7, shap) }
    const result = buildTopAtRiskBarriers([b], predictions)
    expect(result[0].topFactor?.feature).toBe('barrier_family')
    expect(result[0].topFactor?.value).toBe(-0.3)
  })

  it('excludes hidden features (primary_threat_category) from top factor selection', () => {
    const b = makeBarrier()
    const shap: ShapValue[] = [
      makeShap('primary_threat_category', 0.8), // hidden — should be excluded
      makeShap('barrier_type', 0.2),            // visible — should win
    ]
    const predictions = { [b.id]: makePrediction(0.5, shap) }
    const result = buildTopAtRiskBarriers([b], predictions)
    expect(result[0].topFactor?.feature).toBe('barrier_type')
  })

  it('returns topFactor null when model1_shap is empty', () => {
    const b = makeBarrier()
    const predictions = { [b.id]: makePrediction(0.5, []) }
    const result = buildTopAtRiskBarriers([b], predictions)
    expect(result[0].topFactor).toBeNull()
  })

  it('returns topFactor null when all shap entries are hidden', () => {
    const b = makeBarrier()
    const shap: ShapValue[] = [
      makeShap('primary_threat_category', 0.8), // the only hidden feature in the model
    ]
    const predictions = { [b.id]: makePrediction(0.5, shap) }
    const result = buildTopAtRiskBarriers([b], predictions)
    expect(result[0].topFactor).toBeNull()
  })

  it('probability field matches model1_probability from prediction', () => {
    const b = makeBarrier()
    const predictions = { [b.id]: makePrediction(0.734) }
    const result = buildTopAtRiskBarriers([b], predictions)
    expect(result[0].probability).toBe(0.734)
  })

  it('ignores barriers without predictions even when some barriers are analyzed', () => {
    const b1 = makeBarrier({ name: 'Analyzed' })
    const b2 = makeBarrier({ name: 'Unanalyzed' })
    const predictions = { [b1.id]: makePrediction(0.5) }
    const result = buildTopAtRiskBarriers([b1, b2], predictions)
    expect(result).toHaveLength(1)
    expect(result[0].barrier.name).toBe('Analyzed')
  })
})

// ---------------------------------------------------------------------------
// H-2: buildAverageRiskItems — analyzeAll() path
// ---------------------------------------------------------------------------

describe('buildAverageRiskItems', () => {
  it('returns [] when no barriers have average_cascading_probability', () => {
    const barriers = [makeBarrier(), makeBarrier()]
    expect(buildAverageRiskItems(barriers)).toEqual([])
  })

  it('sorts by average_cascading_probability descending', () => {
    const barriers = [
      makeBarrier({ name: 'Low', riskLevel: 'green', average_cascading_probability: 0.2 }),
      makeBarrier({ name: 'High', riskLevel: 'red', average_cascading_probability: 0.85 }),
      makeBarrier({ name: 'Mid', riskLevel: 'amber', average_cascading_probability: 0.55 }),
    ]
    const result = buildAverageRiskItems(barriers)
    expect(result[0].name).toBe('High')
    expect(result[1].name).toBe('Mid')
    expect(result[2].name).toBe('Low')
  })

  it('maps RiskLevel to riskBand correctly', () => {
    const barriers = [
      makeBarrier({ riskLevel: 'red', average_cascading_probability: 0.9 }),
      makeBarrier({ riskLevel: 'amber', average_cascading_probability: 0.5 }),
      makeBarrier({ riskLevel: 'green', average_cascading_probability: 0.2 }),
    ]
    const result = buildAverageRiskItems(barriers)
    expect(result[0].riskBand).toBe('HIGH')
    expect(result[1].riskBand).toBe('MEDIUM')
    expect(result[2].riskBand).toBe('LOW')
  })

  it('respects n limit (default 3)', () => {
    const barriers = Array.from({ length: 7 }, (_, i) =>
      makeBarrier({ average_cascading_probability: 0.1 * (i + 1) }),
    )
    expect(buildAverageRiskItems(barriers)).toHaveLength(3)
    expect(buildAverageRiskItems(barriers, 5)).toHaveLength(5)
  })

  it('uses display_name as topFactor when present, falls back to feature name', () => {
    const b1 = makeBarrier({
      average_cascading_probability: 0.7,
      top_reasons: [{ feature: 'lod_industry_standard_target', value: 0.3, display_name: 'Target LoD category' }],
    })
    const b2 = makeBarrier({
      average_cascading_probability: 0.5,
      top_reasons: [{ feature: 'barrier_level_target', value: 0.2, display_name: '' }],
    })
    const result = buildAverageRiskItems([b1, b2])
    expect(result[0].topFactor).toBe('Target LoD category')
    expect(result[1].topFactor).toBe('barrier_level_target')
  })

  it('excludes barriers without average_cascading_probability', () => {
    const barriers = [
      makeBarrier({ name: 'NoAvg' }),
      makeBarrier({ name: 'HasAvg', average_cascading_probability: 0.6 }),
    ]
    const result = buildAverageRiskItems(barriers)
    expect(result).toHaveLength(1)
    expect(result[0].name).toBe('HasAvg')
  })
})
