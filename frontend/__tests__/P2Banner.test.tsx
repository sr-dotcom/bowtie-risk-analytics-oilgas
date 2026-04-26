import { vi, describe, it, expect, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'

// ---------------------------------------------------------------------------
// All vi.mock calls hoisted — order matters
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

vi.mock('@/components/panel/DetailDrawer', () => ({
  default: () => <div data-testid="detail-drawer" />,
}))

vi.mock('@/components/dashboard/DashboardView', () => ({
  default: () => <div data-testid="dashboard-view" />,
}))

vi.mock('@/components/dashboard/ProvenanceStrip', () => ({
  default: () => null,
}))

// Controllable context mock — overridden per describe block via contextOverride
let contextOverride: Record<string, unknown> = {}

vi.mock('@/context/BowtieContext', () => {
  const baseContext = {
    barriers: [],
    predictions: [],
    eventDescription: '',
    setEventDescription: vi.fn(),
    selectedBarrierId: null,
    setSelectedBarrierId: vi.fn(),
    setSelectedTargetBarrierId: vi.fn(),
    setConditioningBarrierId: vi.fn(),
    isAnalyzing: false,
    viewMode: 'diagram',
    setViewMode: vi.fn(),
    loadBSEEExample: vi.fn(),
    conditioningBarrierId: null,
  }
  return {
    BowtieProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    useBowtieContext: () => ({ ...baseContext, ...contextOverride }),
  }
})

import BowtieApp from '@/components/BowtieApp'

function renderApp() {
  let result: ReturnType<typeof render>
  act(() => {
    result = render(<BowtieApp />)
  })
  return result!
}

const UNANALYZED_BARRIER = {
  id: 'b1',
  name: 'PSV',
  side: 'prevention' as const,
  barrier_type: 'Engineering',
  barrierRole: 'Pressure relief',
  line_of_defense: '1st',
  riskLevel: 'unanalyzed' as const,
  top_reasons: [],
  average_cascading_probability: undefined,
}

describe('BowtieApp P2 analyze banner', () => {
  beforeEach(() => {
    contextOverride = {}
  })

  it('hidden in P0 (no event, no barriers)', () => {
    contextOverride = { eventDescription: '', barriers: [] }
    renderApp()
    expect(screen.queryByTestId('p2-analyze-banner')).toBeNull()
  })

  it('hidden in P1 (event set, no barriers)', () => {
    contextOverride = { eventDescription: 'Loss of containment', barriers: [] }
    renderApp()
    expect(screen.queryByTestId('p2-analyze-banner')).toBeNull()
  })

  it('visible in P2 — event + unanalyzed barriers, no analysis running', () => {
    contextOverride = {
      eventDescription: 'Loss of containment',
      barriers: [UNANALYZED_BARRIER],
      isAnalyzing: false,
    }
    renderApp()
    expect(screen.getByTestId('p2-analyze-banner')).toBeTruthy()
  })

  it('banner copy mentions Analyze Barriers', () => {
    contextOverride = {
      eventDescription: 'Loss of containment',
      barriers: [UNANALYZED_BARRIER],
      isAnalyzing: false,
    }
    renderApp()
    expect(screen.getByTestId('p2-analyze-banner').textContent).toContain('Analyze Barriers')
  })

  it('hidden while analysis is running (isAnalyzing=true)', () => {
    contextOverride = {
      eventDescription: 'Loss of containment',
      barriers: [UNANALYZED_BARRIER],
      isAnalyzing: true,
    }
    renderApp()
    expect(screen.queryByTestId('p2-analyze-banner')).toBeNull()
  })

  it('hidden in P3 — at least one barrier has been analyzed', () => {
    contextOverride = {
      eventDescription: 'Loss of containment',
      barriers: [
        UNANALYZED_BARRIER,
        { ...UNANALYZED_BARRIER, id: 'b2', riskLevel: 'red' as const },
      ],
      isAnalyzing: false,
    }
    renderApp()
    expect(screen.queryByTestId('p2-analyze-banner')).toBeNull()
  })

  it('BowtieSVG is rendered alongside the banner (diagram is not replaced)', () => {
    contextOverride = {
      eventDescription: 'Loss of containment',
      barriers: [UNANALYZED_BARRIER],
      isAnalyzing: false,
    }
    renderApp()
    expect(screen.getByTestId('bowtie-svg')).toBeTruthy()
    expect(screen.getByTestId('p2-analyze-banner')).toBeTruthy()
  })
})
