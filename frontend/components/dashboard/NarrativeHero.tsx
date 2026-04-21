'use client'

import { useMemo, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { useNarrativeSynthesis } from '@/hooks/useNarrativeSynthesis'
import type { NarrativeSynthesisInput } from '@/hooks/useNarrativeSynthesis'

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
  /** Top barrier SHAP factors — up to 3, from cascading model (T2b). */
  shapTopFeatures?: Array<{ feature: string; value: number; display_name?: string }>
  /** Evidence snippets from /explain-cascading response (T2b). */
  evidenceSnippets?: Array<{ incident_id: string; text: string; source_agency: string }>
}

const ERROR_LABELS: Record<string, string> = {
  timeout: 'Synthesis timed out',
  quality_gate: 'Synthesis unavailable',
  unavailable: 'Synthesis offline',
  unknown: 'Synthesis failed',
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function NarrativeHero(props: NarrativeHeroProps) {
  const synthEnabled = process.env.NEXT_PUBLIC_ENABLE_T2B_SYNTHESIS === 'true'
  const { state: synthState, trigger, reset } = useNarrativeSynthesis()
  const [badgeDismissed, setBadgeDismissed] = useState(false)

  const templateBody = useMemo(() => composeNarrative(props), [props])

  // Reset synthesis when the top barrier identity changes
  const topBarrierName = props.topBarrier?.name ?? null
  useEffect(() => {
    reset()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topBarrierName])

  // Auto-dismiss error badge 5s after it appears
  useEffect(() => {
    if (!synthState.error) {
      setBadgeDismissed(false)
      return
    }
    setBadgeDismissed(false)
    const timer = setTimeout(() => setBadgeDismissed(true), 5000)
    return () => clearTimeout(timer)
  }, [synthState.error])

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

  const canSynthesize = synthEnabled && props.hasAnalyzed && props.topBarrier !== null
  const showSynthesisBody = synthState.narrative !== null
  const errorLabel = synthState.error && !badgeDismissed ? ERROR_LABELS[synthState.error] : null

  function handleSynthesize(): void {
    if (!props.topBarrier) return

    // Derive up to 3 unique-by-incident_id contexts from evidence snippets
    const seen = new Set<string>()
    const ragContexts: NarrativeSynthesisInput['rag_incident_contexts'] = []
    for (const snippet of props.evidenceSnippets ?? []) {
      if (!seen.has(snippet.incident_id) && ragContexts.length < 3) {
        seen.add(snippet.incident_id)
        ragContexts.push({
          incident_id: snippet.incident_id,
          summary_text: snippet.text,
          barrier_failure_description: '',
        })
      }
    }

    const prob = props.topBarrier.probability
    const riskBand: 'HIGH' | 'MEDIUM' | 'LOW' =
      prob >= 0.6 ? 'HIGH' : prob >= 0.3 ? 'MEDIUM' : 'LOW'

    trigger({
      top_barrier_name: props.topBarrier.name,
      top_barrier_risk_band: riskBand,
      top_barrier_probability: prob,
      shap_top_features: (props.shapTopFeatures ?? []).slice(0, 3).map((f) => ({
        feature: f.feature,
        value: f.value,
        display_name: f.display_name ?? f.feature,
      })),
      rag_incident_contexts: ragContexts,
      total_barriers: props.totalBarriers,
      high_risk_count: props.highRiskCount,
      top_event: props.topEvent,
      similar_incidents_count: props.similarIncidentsCount,
    })
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
        position: 'relative',
      }}
    >
      {/* Header row */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 8,
        }}
      >
        <div
          style={{
            fontSize: 13,
            fontWeight: 400,
            color: 'var(--text-secondary)',
          }}
        >
          System narrative
        </div>

        {/* T2b synthesis controls — only when flag is ON */}
        {synthEnabled && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {errorLabel && (
              <span
                data-testid="synthesis-error-badge"
                style={{
                  fontSize: 11,
                  textTransform: 'uppercase' as const,
                  letterSpacing: 1,
                  color: 'var(--risk-medium-text)',
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--risk-medium)',
                  borderRadius: 2,
                  padding: '4px 8px',
                }}
              >
                {errorLabel}
              </span>
            )}
            {!showSynthesisBody && (
              <button
                data-testid="synthesis-button"
                onClick={handleSynthesize}
                disabled={!canSynthesize || synthState.isLoading}
                style={{
                  background: 'transparent',
                  border: '1px solid var(--border-default)',
                  color: 'var(--text-secondary)',
                  padding: '6px 12px',
                  fontSize: 12,
                  fontWeight: 500,
                  borderRadius: 4,
                  cursor: !canSynthesize || synthState.isLoading ? 'not-allowed' : 'pointer',
                  opacity: !canSynthesize || synthState.isLoading ? 0.5 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                {synthState.isLoading ? (
                  <>
                    <span
                      data-testid="synthesis-loading-dot"
                      style={{
                        display: 'inline-block',
                        width: 14,
                        height: 14,
                        border: '2px solid transparent',
                        borderTopColor: 'var(--accent-primary)',
                        borderRadius: '50%',
                      }}
                    />
                    Synthesizing...
                  </>
                ) : (
                  '✨ Summarize with AI'
                )}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Narrative body — synthesis or template */}
      <div
        style={{
          fontSize: 16,
          fontWeight: 400,
          color: 'var(--text-primary)',
          lineHeight: 1.65,
        }}
      >
        {showSynthesisBody ? synthState.narrative : templateBody}
      </div>

      {/* Synthesis metadata line */}
      {showSynthesisBody && synthState.generatedAt && (
        <div
          data-testid="synthesis-metadata"
          style={{
            fontSize: 13,
            color: 'var(--text-tertiary)',
            marginTop: 8,
          }}
        >
          AI synthesis · {relativeTime(synthState.generatedAt)}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function relativeTime(isoString: string): string {
  const diffMs = Date.now() - new Date(isoString).getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  return `${diffMin}m ago`
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
