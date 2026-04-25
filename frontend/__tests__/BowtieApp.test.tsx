import { vi, describe, it, expect } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

// ---------------------------------------------------------------------------
// vi.mock calls must be placed before component imports so vitest hoisting
// can rewrite them to the top of the compiled module.
// ---------------------------------------------------------------------------

vi.mock('@/components/diagram/BowtieSVG', () => ({
  default: () => <div data-testid="bowtie-svg" />,
}))

vi.mock('@/components/diagram/PathwayView', () => ({
  default: () => <div data-testid="pathway-view" />,
}))

vi.mock('@/components/sidebar/BarrierForm', () => ({
  default: () => <div data-testid="barrier-form" />,
}))

vi.mock('@/components/panel/DetailPanel', () => ({
  default: () => <div data-testid="detail-panel" />,
}))

vi.mock('@/components/dashboard/DashboardView', () => ({
  default: () => <div data-testid="dashboard-view" />,
}))

import BowtieApp from '@/components/BowtieApp'

// ---------------------------------------------------------------------------
// Helper: render BowtieApp and suppress act() warnings from the demo useEffect
// ---------------------------------------------------------------------------
function renderApp() {
  let result: ReturnType<typeof render>
  act(() => {
    result = render(<BowtieApp />)
  })
  return result!
}

describe('BowtieApp mode toggle', () => {
  it('initial render shows diagram mode (empty-state card visible, dashboard-view and pathway-view absent)', () => {
    renderApp()
    expect(screen.getByText('Define your bowtie scenario')).toBeTruthy()
    expect(screen.queryByTestId('bowtie-svg')).toBeNull()
    expect(screen.queryByTestId('dashboard-view')).toBeNull()
    expect(screen.queryByTestId('pathway-view')).toBeNull()
  })

  it('clicking "Analytics" switches to dashboard mode', () => {
    renderApp()
    // In diagram mode the toggle bar is in the center panel — one "Analytics" button
    const analyticsBtn = screen.getByRole('button', { name: 'Analytics' })
    fireEvent.click(analyticsBtn)
    expect(screen.getByTestId('dashboard-view')).toBeTruthy()
    expect(screen.queryByTestId('bowtie-svg')).toBeNull()
  })

  it('in dashboard mode, clicking "Diagram View" switches back to diagram', () => {
    renderApp()
    fireEvent.click(screen.getByRole('button', { name: 'Analytics' }))
    // Now in dashboard mode — top-bar has "Diagram View"
    fireEvent.click(screen.getByRole('button', { name: 'Diagram View' }))
    // Cold state: no event/barriers → empty-state card shown, not BowtieSVG
    expect(screen.getByText('Define your bowtie scenario')).toBeTruthy()
    expect(screen.queryByTestId('dashboard-view')).toBeNull()
  })

  it('clicking "Pathway View" from diagram mode shows PathwayView', () => {
    renderApp()
    fireEvent.click(screen.getByRole('button', { name: 'Pathway View' }))
    expect(screen.getByTestId('pathway-view')).toBeTruthy()
    expect(screen.queryByTestId('bowtie-svg')).toBeNull()
  })

  it('in dashboard mode, clicking "Pathway View" switches to pathway', () => {
    renderApp()
    fireEvent.click(screen.getByRole('button', { name: 'Analytics' }))
    fireEvent.click(screen.getByRole('button', { name: 'Pathway View' }))
    expect(screen.getByTestId('pathway-view')).toBeTruthy()
    expect(screen.queryByTestId('dashboard-view')).toBeNull()
  })

  it('all three mode toggle buttons are present in diagram mode', () => {
    renderApp()
    // In diagram mode the center-panel toggle bar renders exactly one set of 3 buttons
    expect(screen.getByRole('button', { name: 'Diagram View' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Pathway View' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Analytics' })).toBeTruthy()
  })
})
