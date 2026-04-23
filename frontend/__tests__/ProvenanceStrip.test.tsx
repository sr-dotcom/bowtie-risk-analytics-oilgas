import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'

// ---------------------------------------------------------------------------
// Mock useHealth — ProvenanceStrip reads model + RAG state from it.
// getDenominatorValue reads configs/denominators.json directly (no mock needed).
// ---------------------------------------------------------------------------

const mockUseHealth = vi.hoisted(() => vi.fn())
vi.mock('@/hooks/useHealth', () => ({
  useHealth: mockUseHealth,
}))

// ---------------------------------------------------------------------------
// Import component AFTER vi.mock
// ---------------------------------------------------------------------------

import ProvenanceStrip from '@/components/dashboard/ProvenanceStrip'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const HEALTH_OK = {
  status: 'ok',
  models: { cascading: { name: 'xgb_cascade_y_fail', loaded: true } },
  rag: { corpus_size: 1161 },
  uptime_seconds: 100,
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ProvenanceStrip — loading state', () => {
  it('renders loading skeleton when health is fetching', () => {
    mockUseHealth.mockReturnValue({ health: null, loading: true, error: null })
    const { container } = render(<ProvenanceStrip />)
    expect(container.textContent?.toLowerCase()).toContain('loading provenance')
  })

  it('does not render provenance lines while loading', () => {
    mockUseHealth.mockReturnValue({ health: null, loading: true, error: null })
    const { container } = render(<ProvenanceStrip />)
    expect(container.textContent).not.toContain('XGBoost cascade')
    expect(container.textContent).not.toContain('hybrid RAG')
  })
})

describe('ProvenanceStrip — normal render', () => {
  beforeEach(() => {
    mockUseHealth.mockReturnValue({ health: HEALTH_OK, loading: false, error: null })
  })

  it('renders Line 1 prediction provenance text', () => {
    const { container } = render(<ProvenanceStrip />)
    expect(container.textContent).toContain('XGBoost cascade')
  })

  it('renders Line 2 evidence provenance text', () => {
    const { container } = render(<ProvenanceStrip />)
    expect(container.textContent).toContain('hybrid RAG')
  })

  it('shows training pair row count from denominators registry (813)', () => {
    const { container } = render(<ProvenanceStrip />)
    // 813 = getDenominatorValue('m003_cascade_training_pair_rows') — not a hardcoded literal
    expect(container.textContent).toContain('813')
  })

  it('shows incident count from denominators registry (156)', () => {
    const { container } = render(<ProvenanceStrip />)
    expect(container.textContent).toContain('156')
  })

  it('shows barrier count formatted with thousands separator (1,161)', () => {
    const { container } = render(<ProvenanceStrip />)
    // 1161 from registry, formatted as "1,161" per §10 spec
    expect(container.textContent).toContain('1,161')
  })

  it('shows AUC formatted to 2 decimal places (0.76 ± 0.07)', () => {
    const { container } = render(<ProvenanceStrip />)
    expect(container.textContent).toContain('0.76')
    expect(container.textContent).toContain('0.07')
  })

  it('shows "View model card →" greyed-out link', () => {
    const { container } = render(<ProvenanceStrip />)
    expect(container.textContent).toContain('View model card →')
  })

  it('does not show any degraded markers when all systems are loaded', () => {
    const { container } = render(<ProvenanceStrip />)
    expect(container.textContent).not.toContain('not loaded')
  })
})

describe('ProvenanceStrip — degraded states', () => {
  it('shows model degraded marker when no model is loaded', () => {
    mockUseHealth.mockReturnValue({
      health: {
        status: 'degraded',
        models: { cascading: { name: 'xgb_cascade_y_fail', loaded: false } },
        rag: { corpus_size: 1161 },
        uptime_seconds: 100,
      },
      loading: false,
      error: null,
    })
    const { container } = render(<ProvenanceStrip />)
    expect(container.textContent).toContain('model not loaded')
  })

  it('shows RAG degraded marker when corpus_size is 0', () => {
    mockUseHealth.mockReturnValue({
      health: {
        status: 'degraded',
        models: { cascading: { name: 'xgb_cascade_y_fail', loaded: true } },
        rag: { corpus_size: 0 },
        uptime_seconds: 100,
      },
      loading: false,
      error: null,
    })
    const { container } = render(<ProvenanceStrip />)
    expect(container.textContent).toContain('RAG not loaded')
  })

  it('shows both degraded markers when health is null after load (error state)', () => {
    mockUseHealth.mockReturnValue({ health: null, loading: false, error: 'Network error' })
    const { container } = render(<ProvenanceStrip />)
    // health is null → modelLoaded=false, ragLoaded=false → both warnings
    expect(container.textContent).toContain('model not loaded')
    expect(container.textContent).toContain('RAG not loaded')
  })
})
