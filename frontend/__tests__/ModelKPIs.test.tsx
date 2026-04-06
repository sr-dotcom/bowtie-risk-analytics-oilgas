import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { buildKpiCards } from '@/components/dashboard/ModelKPIs'
import ModelKPIs from '@/components/dashboard/ModelKPIs'
import { BowtieProvider } from '@/context/BowtieContext'

// ---------------------------------------------------------------------------
// buildKpiCards unit tests
// ---------------------------------------------------------------------------

describe('buildKpiCards', () => {
  it('returns exactly 4 items', () => {
    expect(buildKpiCards()).toHaveLength(4)
  })

  it('first card has label "Barrier Failure F1" and value "0.928"', () => {
    const cards = buildKpiCards()
    expect(cards[0].label).toBe('Barrier Failure F1')
    expect(cards[0].value).toBe('0.928')
  })

  it('all cards have subtitle containing "5-fold CV"', () => {
    const cards = buildKpiCards()
    for (const card of cards) {
      expect(card.subtitle).toContain('5-fold CV')
    }
  })

  it('model1 cards (index 0,1) have category "model1" and model2 cards (index 2,3) have category "model2"', () => {
    const cards = buildKpiCards()
    expect(cards[0].category).toBe('model1')
    expect(cards[1].category).toBe('model1')
    expect(cards[2].category).toBe('model2')
    expect(cards[3].category).toBe('model2')
  })
})

// ---------------------------------------------------------------------------
// ModelKPIs component render test
// ---------------------------------------------------------------------------

describe('ModelKPIs component', () => {
  it('renders with data-testid "model-kpis"', () => {
    render(
      <BowtieProvider>
        <ModelKPIs />
      </BowtieProvider>,
    )
    expect(screen.getByTestId('model-kpis')).toBeDefined()
  })
})
