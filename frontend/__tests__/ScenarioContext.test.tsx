import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { buildScenarioSummary } from '@/components/dashboard/ScenarioContext'
import ScenarioContext from '@/components/dashboard/ScenarioContext'
import { BowtieProvider } from '@/context/BowtieContext'
import type { Barrier, PredictResponse } from '@/lib/types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeBarrier(id: string): Barrier {
  return {
    id,
    name: `Barrier ${id}`,
    side: 'prevention',
    barrier_type: 'administrative',
    barrier_family: 'procedure',
    line_of_defense: '1',
    barrierRole: 'preventive',
    riskLevel: 'unanalyzed',
  }
}

function makePrediction(): PredictResponse {
  return {
    model1_probability: 0.5,
    model2_probability: 0.3,
    model1_shap: [],
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

// ---------------------------------------------------------------------------
// buildScenarioSummary unit tests
// ---------------------------------------------------------------------------

describe('buildScenarioSummary', () => {
  it('returns 0 barriers and 0 analyzed for empty inputs', () => {
    const result = buildScenarioSummary([], {}, '')
    expect(result.totalBarriers).toBe(0)
    expect(result.analyzedBarriers).toBe(0)
  })

  it('counts total barriers correctly when no predictions exist', () => {
    const barriers = [makeBarrier('b1'), makeBarrier('b2'), makeBarrier('b3')]
    const result = buildScenarioSummary(barriers, {}, '')
    expect(result.totalBarriers).toBe(3)
    expect(result.analyzedBarriers).toBe(0)
  })

  it('counts analyzed barriers by matching prediction keys to barrier ids', () => {
    const barriers = [makeBarrier('b1'), makeBarrier('b2'), makeBarrier('b3')]
    const predictions: Record<string, PredictResponse> = {
      b1: makePrediction(),
      b3: makePrediction(),
    }
    const result = buildScenarioSummary(barriers, predictions, '')
    expect(result.totalBarriers).toBe(3)
    expect(result.analyzedBarriers).toBe(2)
  })

  it('passes through eventDescription unchanged', () => {
    const desc = 'Gas release from high-pressure pipeline'
    const result = buildScenarioSummary([], {}, desc)
    expect(result.eventDescription).toBe(desc)
  })
})

// ---------------------------------------------------------------------------
// ScenarioContext component render test
// ---------------------------------------------------------------------------

describe('ScenarioContext component', () => {
  it('renders with data-testid "scenario-context"', () => {
    render(
      <BowtieProvider>
        <ScenarioContext />
      </BowtieProvider>,
    )
    expect(screen.getByTestId('scenario-context')).toBeDefined()
  })
})
