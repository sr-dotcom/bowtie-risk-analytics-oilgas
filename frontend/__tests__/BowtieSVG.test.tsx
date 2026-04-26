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

const UNANALYZED_BARRIER = {
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

const ANALYZED_BARRIER = {
  ...UNANALYZED_BARRIER,
  risk_level: 'High' as const,
  top_reasons: [
    { display_name: 'Corrosion', value: 0.42, direction: 'up' as const },
  ],
}

describe('BowtieSVG P2 — unanalyzed barriers (grey state)', () => {
  it('renders barrier card when risk_level is null', () => {
    render(
      <BowtieSVG {...BASE_PROPS} topEvent="Loss of containment" barriers={[UNANALYZED_BARRIER]} />,
    )
    // barrier card should exist — name text rendered somewhere in the SVG
    expect(document.body.textContent).toContain('PSV')
  })

  it('no SHAP metric block when top_reasons is empty (P2 — unanalyzed)', () => {
    const { container } = render(
      <BowtieSVG {...BASE_PROPS} topEvent="Loss of containment" barriers={[UNANALYZED_BARRIER]} />,
    )
    // Metric block uses a rect with fill="#fff" directly below the barrier body;
    // the display_name text from reasons would appear — confirm it does NOT
    expect(container.querySelector('[data-testid="barrier-metric-b1"]')).toBeNull()
  })

  it('SHAP metric block absent without reasons even when risk_level set (P3 edge)', () => {
    const noReasons = { ...ANALYZED_BARRIER, top_reasons: [] }
    const { container } = render(
      <BowtieSVG {...BASE_PROPS} topEvent="Loss of containment" barriers={[noReasons]} />,
    )
    expect(container.querySelector('[data-testid="barrier-metric-b1"]')).toBeNull()
  })

  it('P2 barrier uses muted border color (no fill="#333" stroke on border rect)', () => {
    const { container } = render(
      <BowtieSVG {...BASE_PROPS} topEvent="Loss of containment" barriers={[UNANALYZED_BARRIER]} />,
    )
    // Find all rect elements and check none use the old dark fallback stroke
    const rects = Array.from(container.querySelectorAll('rect'))
    const darkBorderRects = rects.filter(
      (r) => r.getAttribute('stroke') === '#333' && r.getAttribute('fill') === 'none',
    )
    expect(darkBorderRects.length).toBe(0)
  })
})

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
