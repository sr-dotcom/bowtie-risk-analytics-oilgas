import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { NarrativeHero, type NarrativeHeroProps } from '@/components/dashboard/NarrativeHero'

// ---------------------------------------------------------------------------
// Mock useNarrativeSynthesis so T2b component tests control hook state
// ---------------------------------------------------------------------------

const mockTrigger = vi.fn()
const mockReset = vi.fn()
let mockSynthState = {
  narrative: null as string | null,
  isLoading: false,
  error: null as 'timeout' | 'quality_gate' | 'unavailable' | 'unknown' | null,
  generatedAt: null as string | null,
}

vi.mock('@/hooks/useNarrativeSynthesis', () => ({
  useNarrativeSynthesis: () => ({
    state: mockSynthState,
    trigger: mockTrigger,
    reset: mockReset,
  }),
}))

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const BASE_PROPS: NarrativeHeroProps = {
  topEvent: 'Loss of containment at compressor station',
  totalBarriers: 7,
  highRiskCount: 2,
  topBarrier: { name: 'Pressure Safety Valve', probability: 0.82 },
  similarIncidentsCount: 5,
  totalRetrievedIncidents: 156,
  hasAnalyzed: true,
}

function renderHero(overrides: Partial<NarrativeHeroProps> = {}) {
  return render(<NarrativeHero {...BASE_PROPS} {...overrides} />)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('NarrativeHero — pre-analysis placeholder', () => {
  it('renders placeholder text when hasAnalyzed is false', () => {
    renderHero({ hasAnalyzed: false })
    expect(screen.getByText('Click Analyze Barriers to generate scenario summary.')).toBeTruthy()
  })

  it('does not render "System narrative" label in placeholder state', () => {
    renderHero({ hasAnalyzed: false })
    expect(screen.queryByText('System narrative')).toBeNull()
  })
})

describe('NarrativeHero — full template', () => {
  it('renders System narrative label and hero testid when analyzed', () => {
    renderHero()
    expect(screen.getByTestId('narrative-hero')).toBeTruthy()
    expect(screen.getByText('System narrative')).toBeTruthy()
  })

  it('renders barrier count, top event, and top barrier name', () => {
    renderHero()
    expect(screen.getByText('7')).toBeTruthy()
    expect(screen.getByText('Loss of containment at compressor station')).toBeTruthy()
    expect(screen.getByText('Pressure Safety Valve')).toBeTruthy()
  })

  it('renders high-risk count and historical incident counts', () => {
    renderHero()
    expect(screen.getByText('2')).toBeTruthy()
    expect(screen.getByText('5')).toBeTruthy()
    expect(screen.getByText('156')).toBeTruthy()
  })
})

describe('NarrativeHero — edge cases', () => {
  it('handles topBarrier === null (no high-risk barriers) — uses alt template', () => {
    renderHero({ topBarrier: null, highRiskCount: 0 })
    expect(
      screen.getByText(/No barriers exceed the high-risk threshold/i),
    ).toBeTruthy()
    expect(screen.queryByText(/weakest link/i)).toBeNull()
  })

  it('handles similarIncidentsCount === 0 — shows no-comparable-incidents clause', () => {
    renderHero({ similarIncidentsCount: 0 })
    expect(
      screen.getByText(/no directly comparable historical incidents were retrieved/i),
    ).toBeTruthy()
  })

  it('handles totalBarriers === 0 — shows add-barriers message', () => {
    renderHero({ totalBarriers: 0, hasAnalyzed: true, topBarrier: null, highRiskCount: 0 })
    expect(
      screen.getByText('Add barriers to this scenario to generate a summary.'),
    ).toBeTruthy()
  })

  it('handles empty topEvent — falls back to "the top event"', () => {
    renderHero({ topEvent: '' })
    expect(screen.getByText('the top event')).toBeTruthy()
  })

  it('handles topEvent with only whitespace — falls back to "the top event"', () => {
    renderHero({ topEvent: '   ' })
    expect(screen.getByText('the top event')).toBeTruthy()
  })

  it('renders long topBarrier.name without error', () => {
    const longName = 'A'.repeat(200)
    renderHero({ topBarrier: { name: longName, probability: 0.9 } })
    expect(screen.getByText(longName)).toBeTruthy()
  })

  it('similarIncidentsCount=2 renders 2 — dedup from 3 snippets across 2 unique incidents', () => {
    // Dedup logic lives in DashboardView: new Set(snippets.map(s=>s.incident_id)).size
    // When 3 snippets come from 2 unique incidents, the prop passed here is 2 not 3
    renderHero({ similarIncidentsCount: 2, totalRetrievedIncidents: 156 })
    const hero = screen.getByTestId('narrative-hero')
    expect(hero.textContent).toMatch(/similar barriers failed in 2/)
    expect(hero.textContent).not.toMatch(/similar barriers failed in 3/)
  })
})

// ---------------------------------------------------------------------------
// T2b — feature flag + synthesis button
// ---------------------------------------------------------------------------

describe('NarrativeHero — T2b feature flag', () => {
  beforeEach(() => {
    // Reset hook mock state before each test
    mockSynthState = { narrative: null, isLoading: false, error: null, generatedAt: null }
    mockTrigger.mockReset()
    mockReset.mockReset()
  })

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_ENABLE_T2B_SYNTHESIS
    vi.useRealTimers()
  })

  it('renders without synthesis button when flag is OFF', () => {
    renderHero()
    expect(screen.queryByTestId('synthesis-button')).toBeNull()
  })

  it('renders synthesis button when flag is ON and hasAnalyzed=true', () => {
    process.env.NEXT_PUBLIC_ENABLE_T2B_SYNTHESIS = 'true'
    renderHero()
    expect(screen.getByTestId('synthesis-button')).toBeTruthy()
    expect(screen.getByTestId('synthesis-button').textContent).toContain('Summarize with AI')
  })

  it('button is disabled when hasAnalyzed is false (flag ON)', () => {
    process.env.NEXT_PUBLIC_ENABLE_T2B_SYNTHESIS = 'true'
    renderHero({ hasAnalyzed: true, topBarrier: null })
    const btn = screen.getByTestId('synthesis-button') as HTMLButtonElement
    expect(btn.disabled).toBe(true)
  })

  it('clicking button calls trigger with synthesis input', () => {
    process.env.NEXT_PUBLIC_ENABLE_T2B_SYNTHESIS = 'true'
    renderHero()
    fireEvent.click(screen.getByTestId('synthesis-button'))
    expect(mockTrigger).toHaveBeenCalledOnce()
  })

  it('success state replaces template body with synthesis narrative', () => {
    process.env.NEXT_PUBLIC_ENABLE_T2B_SYNTHESIS = 'true'
    mockSynthState = { narrative: 'AI generated text.', isLoading: false, error: null, generatedAt: '2026-04-20T00:00:00Z' }
    renderHero()
    expect(screen.getByTestId('narrative-hero').textContent).toContain('AI generated text.')
    // Template phrase should not appear
    expect(screen.queryByText(/weakest link/i)).toBeNull()
  })

  it('error state shows badge and keeps template body visible', () => {
    process.env.NEXT_PUBLIC_ENABLE_T2B_SYNTHESIS = 'true'
    mockSynthState = { narrative: null, isLoading: false, error: 'timeout', generatedAt: null }
    renderHero()
    expect(screen.getByTestId('synthesis-error-badge')).toBeTruthy()
    expect(screen.getByTestId('synthesis-error-badge').textContent).toContain('Synthesis timed out')
    // Template body still visible
    expect(screen.getByTestId('narrative-hero').textContent).toMatch(/weakest link/)
  })

  it('error badge auto-dismisses after 5s', async () => {
    vi.useFakeTimers()
    process.env.NEXT_PUBLIC_ENABLE_T2B_SYNTHESIS = 'true'
    mockSynthState = { narrative: null, isLoading: false, error: 'timeout', generatedAt: null }
    renderHero()
    expect(screen.getByTestId('synthesis-error-badge')).toBeTruthy()

    await act(async () => {
      vi.advanceTimersByTime(5001)
    })

    expect(screen.queryByTestId('synthesis-error-badge')).toBeNull()
  })
})
