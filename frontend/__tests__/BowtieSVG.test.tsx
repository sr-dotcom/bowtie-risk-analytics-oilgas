import { vi, describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import BowtieSVG from '@/components/diagram/BowtieSVG'

const THREATS = [
  { id: 't1', name: 'Overpressure', contribution: 'high' as const },
  { id: 't2', name: 'Overheating', contribution: 'medium' as const },
  { id: 't3', name: 'Operator error', contribution: 'low' as const },
]
const CONSEQUENCES = [
  { id: 'c1', name: 'Gas release' },
  { id: 'c2', name: 'Explosion' },
]

const BASE_PROPS = {
  topEvent: '',
  hazardName: 'High-pressure gas',
  threats: THREATS,
  consequences: CONSEQUENCES,
  barriers: [],
  selectedBarrierId: null,
  onBarrierClick: vi.fn(),
}

describe('BowtieSVG P1 prompt', () => {
  it('hidden when topEvent is empty (P0 — empty state)', () => {
    render(<BowtieSVG {...BASE_PROPS} topEvent="" barriers={[]} />)
    expect(screen.queryByTestId('p1-barrier-prompt')).toBeNull()
  })

  it('visible when topEvent is set and barriers are empty (P1)', () => {
    render(<BowtieSVG {...BASE_PROPS} topEvent="Loss of containment" barriers={[]} />)
    expect(screen.getByTestId('p1-barrier-prompt')).toBeTruthy()
  })

  it('contains left-pointing arrow and sidebar copy', () => {
    render(<BowtieSVG {...BASE_PROPS} topEvent="Loss of containment" barriers={[]} />)
    const prompt = screen.getByTestId('p1-barrier-prompt')
    expect(prompt.textContent).toContain('←')
    expect(prompt.textContent).toContain('sidebar')
  })

  it('hidden when barriers are present (P2/P3 — barriers added)', () => {
    const barrier = {
      id: 'b1',
      name: 'PSV',
      side: 'prevention' as const,
      barrier_type: 'Engineering',
      barrier_role: 'Pressure relief',
      line_of_defense: '1st',
      risk_level: null,
      top_reasons: [],
      average_cascading_probability: undefined,
      threatId: 't1',
      consequenceId: undefined,
    }
    render(
      <BowtieSVG {...BASE_PROPS} topEvent="Loss of containment" barriers={[barrier]} />,
    )
    expect(screen.queryByTestId('p1-barrier-prompt')).toBeNull()
  })
})
