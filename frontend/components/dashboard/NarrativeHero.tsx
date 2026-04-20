'use client'

import { useMemo } from 'react'
import type { ReactNode } from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface NarrativeHeroProps {
  topEvent: string
  totalBarriers: number
  highRiskCount: number
  topBarrier: {
    name: string
    probability: number
  } | null
  similarIncidentsCount: number
  totalRetrievedIncidents: number
  hasAnalyzed: boolean
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function NarrativeHero(props: NarrativeHeroProps) {
  const body = useMemo(() => composeNarrative(props), [props])

  if (!props.hasAnalyzed) {
    return (
      <div
        data-testid="narrative-hero"
        className="w-full"
        style={{
          background: 'var(--bg-accent)',
          borderLeft: '3px solid var(--risk-high)',
          borderRadius: '0 4px 4px 0',
          padding: '20px 24px',
          color: 'var(--text-tertiary)',
          fontSize: 13,
          lineHeight: 1.65,
        }}
      >
        Click Analyze Barriers to generate scenario summary.
      </div>
    )
  }

  return (
    <div
      data-testid="narrative-hero"
      className="w-full"
      style={{
        background: 'var(--bg-accent)',
        borderLeft: '3px solid var(--risk-high)',
        borderRadius: '0 4px 4px 0',
        padding: '20px 24px',
      }}
    >
      <div
        style={{
          fontSize: 13,
          fontWeight: 400,
          color: 'var(--text-secondary)',
          marginBottom: 8,
        }}
      >
        System narrative
      </div>
      <div
        style={{
          fontSize: 16,
          fontWeight: 400,
          color: 'var(--text-primary)',
          lineHeight: 1.65,
        }}
      >
        {body}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Template composition — per UI-CONTEXT.md §9 (T2a path)
// ---------------------------------------------------------------------------

function composeNarrative(p: NarrativeHeroProps): ReactNode {
  const resolvedEvent = p.topEvent.trim() || 'the top event'

  if (p.totalBarriers === 0) {
    return 'Add barriers to this scenario to generate a summary.'
  }

  const barrierNoun = p.totalBarriers === 1 ? 'barrier' : 'barriers'
  const highRiskNoun = p.highRiskCount === 1 ? 'is high-risk' : 'are high-risk'

  if (!p.topBarrier) {
    return (
      <>
        This scenario has{' '}
        <strong style={{ fontWeight: 500 }}>{p.totalBarriers}</strong>{' '}
        {barrierNoun} defending against{' '}
        <strong style={{ fontWeight: 500 }}>{resolvedEvent}</strong>. No barriers
        exceed the high-risk threshold at current LoD settings.
      </>
    )
  }

  const historicalClause =
    p.similarIncidentsCount === 0
      ? 'no directly comparable historical incidents were retrieved'
      : (
          <>
            similar barriers failed in{' '}
            <strong style={{ fontWeight: 500 }}>{p.similarIncidentsCount}</strong> of{' '}
            <strong style={{ fontWeight: 500 }}>{p.totalRetrievedIncidents}</strong>{' '}
            comparable incidents
          </>
        )

  return (
    <>
      This scenario has{' '}
      <strong style={{ fontWeight: 500 }}>{p.totalBarriers}</strong>{' '}
      {barrierNoun} defending against{' '}
      <strong style={{ fontWeight: 500 }}>{resolvedEvent}</strong>.{' '}
      <strong style={{ fontWeight: 500 }}>{p.highRiskCount}</strong> {highRiskNoun}.
      The weakest link is{' '}
      <strong style={{ fontWeight: 500 }}>{p.topBarrier.name}</strong> — historical
      data shows {historicalClause}.
    </>
  )
}
