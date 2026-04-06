import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
  buildGlobalShapData,
} from '@/components/dashboard/DriversHF'
import type { GlobalShapEntry } from '@/components/dashboard/DriversHF'
import { BowtieProvider } from '@/context/BowtieContext'
import GlobalShapChart from '@/components/dashboard/DriversHF'
import type { PredictResponse, ShapValue } from '@/lib/types'

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

  it('excludes source_agency and primary_threat_category', () => {
    const pred = makePrediction([
      makeShap('source_agency', 0.99),
      makeShap('primary_threat_category', 0.8),
      makeShap('barrier_type', 0.2),
    ])
    const result = buildGlobalShapData({ b1: pred })
    const features = result.map((e: GlobalShapEntry) => e.feature)
    expect(features).not.toContain('Data Source')
    expect(features).not.toContain('source_agency')
    expect(features).not.toContain('primary_threat_category')
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
