import { describe, it, expect, vi } from 'vitest'
import { render, screen, act } from '@testing-library/react'

// ---------------------------------------------------------------------------
// Mock @/lib/api at module level — hoisted before component import so vitest
// replaces the module for ALL tests in this file (mirrors DashboardView.test.tsx).
// ---------------------------------------------------------------------------

const mockFetchAprioriRules = vi.hoisted(() => vi.fn())
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual('@/lib/api')
  return { ...actual, fetchAprioriRules: mockFetchAprioriRules }
})

// Import components AFTER vi.mock so the mock is applied
import {
  buildGlobalShapData,
  buildPifPrevalenceData,
  buildCascadingContextFactors,
  PifPrevalenceChart,
  PIF_CATEGORY,
  AprioriRulesTable,
  sortRules,
} from '@/components/dashboard/DriversHF'
import type { GlobalShapEntry, PifPrevalenceEntry } from '@/components/dashboard/DriversHF'
import { BowtieProvider } from '@/context/BowtieContext'
import GlobalShapChart from '@/components/dashboard/DriversHF'
import type { AprioriRule, Barrier, PredictResponse, ShapValue } from '@/lib/types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makePrediction(model1_shap: ShapValue[]): PredictResponse {
  return {
    model1_probability: 0.5,
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

function makeShap(
  feature: string,
  value: number,
  category: 'barrier' | 'incident_context' = 'barrier',
): ShapValue {
  return { feature, value, category }
}

// ---------------------------------------------------------------------------
// buildGlobalShapData tests
// ---------------------------------------------------------------------------

describe('buildGlobalShapData', () => {
  it('returns [] for empty predictions', () => {
    expect(buildGlobalShapData({})).toEqual([])
  })

  it('returns sorted array descending by meanAbsShap', () => {
    const pred = makePrediction([
      makeShap('barrier_type', 0.1),
      makeShap('barrier_family', 0.5),
      makeShap('line_of_defense', 0.3),
    ])
    const result = buildGlobalShapData({ b1: pred })
    expect(result).toHaveLength(3)
    expect(result[0].meanAbsShap).toBeGreaterThanOrEqual(result[1].meanAbsShap)
    expect(result[1].meanAbsShap).toBeGreaterThanOrEqual(result[2].meanAbsShap)
    // Verify barrier_family is first (largest |value|)
    expect(result[0].feature).toBe('Barrier Family')
  })

  it('excludes primary_threat_category (source_agency removed from model)', () => {
    const pred = makePrediction([
      makeShap('primary_threat_category', 0.8), // hidden — should be excluded
      makeShap('barrier_type', 0.2),            // visible — should appear as display name
    ])
    const result = buildGlobalShapData({ b1: pred })
    const features = result.map((e: GlobalShapEntry) => e.feature)
    expect(features).not.toContain('primary_threat_category')
    expect(features).not.toContain('Threat Category')
    expect(features).toContain('Barrier Type')
  })

  it('computes mean correctly across multiple barriers', () => {
    const pred1 = makePrediction([makeShap('barrier_type', 0.2)])
    const pred2 = makePrediction([makeShap('barrier_type', 0.4)])
    const result = buildGlobalShapData({ b1: pred1, b2: pred2 })
    expect(result).toHaveLength(1)
    expect(result[0].meanAbsShap).toBeCloseTo(0.3)
  })

  it('uses display names for features', () => {
    const pred = makePrediction([makeShap('side', 0.3)])
    const result = buildGlobalShapData({ b1: pred })
    expect(result[0].feature).toBe('Pathway Position')
  })

  it('assigns category correctly', () => {
    const pred = makePrediction([
      makeShap('barrier_type', 0.3, 'barrier'),
      makeShap('top_event_category', 0.2, 'incident_context'),
    ])
    const result = buildGlobalShapData({ b1: pred })
    const barrierEntry = result.find((e: GlobalShapEntry) => e.feature === 'Barrier Type')
    const contextEntry = result.find((e: GlobalShapEntry) => e.feature === 'Top Event Category')
    expect(barrierEntry?.category).toBe('barrier')
    expect(contextEntry?.category).toBe('incident_context')
  })

  it('H-4: returns [] when predictions empty and no barriers provided', () => {
    expect(buildGlobalShapData({})).toEqual([])
  })

  it('H-4: aggregates from top_reasons when predictions is empty', () => {
    const barriers: Barrier[] = [
      {
        id: 'b1', name: 'B1', side: 'prevention', barrier_type: 'admin', barrier_family: 'proc',
        line_of_defense: '1', barrierRole: 'preventive', riskLevel: 'red',
        average_cascading_probability: 0.85,
        top_reasons: [
          { feature: 'lod_industry_standard_target', value: 0.4, display_name: '' },
          { feature: 'barrier_level_target', value: 0.2, display_name: '' },
        ],
      },
      {
        id: 'b2', name: 'B2', side: 'mitigation', barrier_type: 'tech', barrier_family: 'proc',
        line_of_defense: '2', barrierRole: 'mitigative', riskLevel: 'amber',
        average_cascading_probability: 0.5,
        top_reasons: [
          { feature: 'lod_industry_standard_target', value: 0.3, display_name: '' },
          { feature: 'flag_mechanical_failure', value: 0.1, display_name: '' },
        ],
      },
    ]
    const result = buildGlobalShapData({}, barriers)
    expect(result.length).toBeGreaterThan(0)
    // lod_industry_standard_target appears twice — should be first (highest mean |SHAP|)
    const first = result[0]
    expect(first.feature).toBe('Target LoD category')
    expect(first.meanAbsShap).toBeCloseTo(0.35) // (0.4 + 0.3) / 2
  })
})

// ---------------------------------------------------------------------------
// buildCascadingContextFactors tests
// ---------------------------------------------------------------------------

describe('buildCascadingContextFactors', () => {
  function makeAnalyzedBarrier(
    id: string,
    probability: number,
    topReasons: { feature: string; value: number }[],
  ): Barrier {
    return {
      id,
      name: `Barrier ${id}`,
      side: 'prevention',
      barrier_type: 'admin',
      barrier_family: 'proc',
      line_of_defense: '1',
      barrierRole: 'preventive',
      riskLevel: 'red',
      average_cascading_probability: probability,
      top_reasons: topReasons.map((r) => ({ ...r, display_name: '' })),
    }
  }

  it('returns [] when no barriers have average_cascading_probability', () => {
    const barriers: Barrier[] = [
      { id: 'b1', name: 'B1', side: 'prevention', barrier_type: 'admin', barrier_family: 'proc', line_of_defense: '1', barrierRole: 'preventive', riskLevel: 'unanalyzed' },
    ]
    expect(buildCascadingContextFactors(barriers)).toEqual([])
  })

  it('returns [] when analyzed barriers have no top_reasons', () => {
    const b = makeAnalyzedBarrier('b1', 0.7, [])
    expect(buildCascadingContextFactors([b])).toEqual([])
  })

  it('prevalence = 1.0 when feature appears in every analyzed barrier', () => {
    const b1 = makeAnalyzedBarrier('b1', 0.8, [{ feature: 'flag_mechanical_failure', value: 0.3 }])
    const b2 = makeAnalyzedBarrier('b2', 0.6, [{ feature: 'flag_mechanical_failure', value: 0.2 }])
    const result = buildCascadingContextFactors([b1, b2])
    const entry = result.find((e) => e.featureKey === 'flag_mechanical_failure')
    expect(entry?.prevalence).toBeCloseTo(1.0)
  })

  it('prevalence = 0.5 when feature appears in 1 out of 2 analyzed barriers', () => {
    const b1 = makeAnalyzedBarrier('b1', 0.8, [{ feature: 'flag_mechanical_failure', value: 0.3 }])
    const b2 = makeAnalyzedBarrier('b2', 0.6, [{ feature: 'barrier_level_target', value: 0.2 }])
    const result = buildCascadingContextFactors([b1, b2])
    const entry = result.find((e) => e.featureKey === 'flag_mechanical_failure')
    expect(entry?.prevalence).toBeCloseTo(0.5)
  })

  it('deduplicates feature within the same barrier (counted at most once per barrier)', () => {
    // feature appears twice in b1's top_reasons — should count as 1 occurrence, not 2
    const b1 = makeAnalyzedBarrier('b1', 0.9, [
      { feature: 'lod_industry_standard_target', value: 0.4 },
      { feature: 'lod_industry_standard_target', value: 0.1 },
    ])
    const b2 = makeAnalyzedBarrier('b2', 0.5, [{ feature: 'barrier_level_target', value: 0.2 }])
    const result = buildCascadingContextFactors([b1, b2])
    const entry = result.find((e) => e.featureKey === 'lod_industry_standard_target')
    // 1 barrier out of 2 — prevalence should be 0.5, not 1.0
    expect(entry?.prevalence).toBeCloseTo(0.5)
  })

  it('sorts descending by prevalence', () => {
    const b1 = makeAnalyzedBarrier('b1', 0.9, [
      { feature: 'flag_mechanical_failure', value: 0.4 },
      { feature: 'barrier_level_target', value: 0.2 },
    ])
    const b2 = makeAnalyzedBarrier('b2', 0.5, [
      { feature: 'flag_mechanical_failure', value: 0.3 },
    ])
    const result = buildCascadingContextFactors([b1, b2])
    for (let i = 0; i < result.length - 1; i++) {
      expect(result[i].prevalence).toBeGreaterThanOrEqual(result[i + 1].prevalence)
    }
    expect(result[0].featureKey).toBe('flag_mechanical_failure')
  })

  it('uses getFeatureDisplayName to resolve human labels', () => {
    const b = makeAnalyzedBarrier('b1', 0.8, [{ feature: 'lod_industry_standard_target', value: 0.4 }])
    const result = buildCascadingContextFactors([b])
    expect(result[0].feature).toBe('Target LoD category')
    expect(result[0].featureKey).toBe('lod_industry_standard_target')
  })

  it('excludes barriers without average_cascading_probability from the analysis', () => {
    const analyzed = makeAnalyzedBarrier('b1', 0.8, [{ feature: 'flag_mechanical_failure', value: 0.4 }])
    const unanalyzed: Barrier = {
      id: 'b2', name: 'B2', side: 'prevention', barrier_type: 'admin', barrier_family: 'proc',
      line_of_defense: '1', barrierRole: 'preventive', riskLevel: 'unanalyzed',
      top_reasons: [{ feature: 'flag_mechanical_failure', value: 0.9, display_name: '' }],
    }
    const result = buildCascadingContextFactors([analyzed, unanalyzed])
    const entry = result.find((e) => e.featureKey === 'flag_mechanical_failure')
    // Only 1 analyzed barrier, and it has the feature — prevalence = 1.0, not 0.5
    expect(entry?.prevalence).toBeCloseTo(1.0)
  })
})

// ---------------------------------------------------------------------------
// GlobalShapChart render tests
// ---------------------------------------------------------------------------

describe('GlobalShapChart', () => {
  it('renders with data-testid global-shap-chart', () => {
    render(
      <BowtieProvider>
        <GlobalShapChart />
      </BowtieProvider>,
    )
    expect(screen.getByTestId('global-shap-chart')).toBeTruthy()
  })

  it('shows empty state message when no predictions', () => {
    render(
      <BowtieProvider>
        <GlobalShapChart />
      </BowtieProvider>,
    )
    expect(screen.getByText(/Run Analyze Barriers/i)).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// buildPifPrevalenceData tests
// ---------------------------------------------------------------------------

describe('buildPifPrevalenceData', () => {
  it('returns [] for empty predictions', () => {
    expect(buildPifPrevalenceData({})).toEqual([])
  })

  it('counts only PIFs appearing in globally-sorted top-3 by |SHAP|', () => {
    // 5 SHAP values: top-3 are barrier_family(0.9), side(0.8), pif_competence(0.7)
    // pif_procedures(0.4) and pif_training(0.1) are outside the top 3
    const pred = makePrediction([
      makeShap('barrier_family', 0.9),
      makeShap('side', 0.8),
      makeShap('pif_competence', 0.7),
      makeShap('pif_procedures', 0.4),
      makeShap('pif_training', 0.1),
    ])
    const result = buildPifPrevalenceData({ b1: pred })
    const competence = result.find((e: PifPrevalenceEntry) => e.featureKey === 'pif_competence')
    const procedures = result.find((e: PifPrevalenceEntry) => e.featureKey === 'pif_procedures')
    const training = result.find((e: PifPrevalenceEntry) => e.featureKey === 'pif_training')
    expect(competence?.prevalence).toBeGreaterThan(0)
    expect(procedures?.prevalence).toBe(0)
    expect(training?.prevalence).toBe(0)
  })

  it('prevalence is a fraction (0–1): PIF in top-3 of 1 out of 2 predictions = 0.5', () => {
    // pred1: pif_competence is in top-3 (value 0.8)
    const pred1 = makePrediction([
      makeShap('pif_competence', 0.8),
      makeShap('barrier_type', 0.1),
      makeShap('side', 0.05),
    ])
    // pred2: pif_competence is NOT in top-3 (value 0.01, others dominate)
    const pred2 = makePrediction([
      makeShap('barrier_family', 0.9),
      makeShap('line_of_defense', 0.7),
      makeShap('barrier_type', 0.6),
      makeShap('pif_competence', 0.01),
    ])
    const result = buildPifPrevalenceData({ b1: pred1, b2: pred2 })
    const competence = result.find((e: PifPrevalenceEntry) => e.featureKey === 'pif_competence')
    expect(competence?.prevalence).toBeCloseTo(0.5)
  })

  it('returns all 9 PIFs when predictions exist (even those at 0 prevalence)', () => {
    const pred = makePrediction([makeShap('barrier_type', 0.5)])
    const result = buildPifPrevalenceData({ b1: pred })
    expect(result).toHaveLength(9)
  })

  it('assigns correct categories from PIF_CATEGORY', () => {
    const pred = makePrediction([makeShap('barrier_type', 0.5)])
    const result = buildPifPrevalenceData({ b1: pred })
    const competence = result.find((e: PifPrevalenceEntry) => e.featureKey === 'pif_competence')
    const procedures = result.find((e: PifPrevalenceEntry) => e.featureKey === 'pif_procedures')
    const safetyCulture = result.find((e: PifPrevalenceEntry) => e.featureKey === 'pif_safety_culture')
    expect(competence?.category).toBe('People')
    expect(procedures?.category).toBe('Work')
    expect(safetyCulture?.category).toBe('Organisation')
  })

  it('sorts descending by prevalence', () => {
    // pif_competence in top-3 for both predictions; pif_procedures in top-3 for one
    const pred1 = makePrediction([
      makeShap('pif_competence', 0.9),
      makeShap('pif_procedures', 0.8),
      makeShap('side', 0.1),
    ])
    const pred2 = makePrediction([
      makeShap('pif_competence', 0.9),
      makeShap('barrier_type', 0.8),
      makeShap('barrier_family', 0.7),
    ])
    const result = buildPifPrevalenceData({ b1: pred1, b2: pred2 })
    for (let i = 0; i < result.length - 1; i++) {
      expect(result[i].prevalence).toBeGreaterThanOrEqual(result[i + 1].prevalence)
    }
  })
})

// ---------------------------------------------------------------------------
// PifPrevalenceChart render tests
// ---------------------------------------------------------------------------

describe('PifPrevalenceChart', () => {
  it('renders with data-testid pif-prevalence-chart', () => {
    render(
      <BowtieProvider>
        <PifPrevalenceChart />
      </BowtieProvider>,
    )
    expect(screen.getByTestId('pif-prevalence-chart')).toBeTruthy()
  })

  it('shows empty state message when no predictions', () => {
    render(
      <BowtieProvider>
        <PifPrevalenceChart />
      </BowtieProvider>,
    )
    expect(screen.getByText(/Run Analyze Barriers/i)).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// sortRules pure function tests
// ---------------------------------------------------------------------------

const SAMPLE_RULES: AprioriRule[] = [
  { antecedent: 'safety_valve', consequent: 'blowout_preventer', support: 0.10, confidence: 0.80, lift: 3.5, count: 72 },
  { antecedent: 'blowout_preventer', consequent: 'emergency_shutdown_isolation', support: 0.15, confidence: 0.60, lift: 2.1, count: 108 },
  { antecedent: 'emergency_shutdown_isolation', consequent: 'control_room', support: 0.08, confidence: 0.70, lift: 4.2, count: 58 },
]

describe('sortRules', () => {
  it('sorts by confidence descending', () => {
    const result = sortRules(SAMPLE_RULES, 'confidence', 'desc')
    expect(result[0].confidence).toBeGreaterThanOrEqual(result[1].confidence)
    expect(result[1].confidence).toBeGreaterThanOrEqual(result[2].confidence)
    expect(result[0].confidence).toBe(0.80)
  })

  it('sorts by support ascending', () => {
    const result = sortRules(SAMPLE_RULES, 'support', 'asc')
    expect(result[0].support).toBeLessThanOrEqual(result[1].support)
    expect(result[1].support).toBeLessThanOrEqual(result[2].support)
    expect(result[0].support).toBe(0.08)
  })

  it('sorts by lift descending', () => {
    const result = sortRules(SAMPLE_RULES, 'lift', 'desc')
    expect(result[0].lift).toBeGreaterThanOrEqual(result[1].lift)
    expect(result[1].lift).toBeGreaterThanOrEqual(result[2].lift)
    expect(result[0].lift).toBe(4.2)
  })
})

// ---------------------------------------------------------------------------
// AprioriRulesTable render tests
// ---------------------------------------------------------------------------

describe('AprioriRulesTable', () => {
  it('renders data-testid apriori-rules-table after data loads', async () => {
    mockFetchAprioriRules.mockResolvedValue({ rules: SAMPLE_RULES, n_incidents: 723, generated_at: '2026-04-06T03:37:03Z' })
    await act(async () => {
      render(<AprioriRulesTable />)
    })
    expect(screen.getByTestId('apriori-rules-table')).toBeTruthy()
  })

  it('shows loading state while fetch is pending', () => {
    // Never-resolving promise keeps the component in the loading state
    mockFetchAprioriRules.mockReturnValue(new Promise(() => {}))
    render(<AprioriRulesTable />)
    expect(screen.getByText('Loading co-failure rules...')).toBeTruthy()
  })

  it('renders n_incidents from API response in description text', async () => {
    mockFetchAprioriRules.mockResolvedValue({ rules: SAMPLE_RULES, n_incidents: 999, generated_at: '2026-01-01T00:00:00Z' })
    await act(async () => {
      render(<AprioriRulesTable />)
    })
    expect(screen.getByText(/999/)).toBeTruthy()
  })
})
