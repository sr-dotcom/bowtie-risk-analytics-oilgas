'use client'

import { useState } from 'react'
import { Loader2, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react'
import { useBowtieContext } from '@/context/BowtieContext'
import type { Barrier, PredictResponse } from '@/lib/types'
import SimpleMarkdown from '@/components/ui/SimpleMarkdown'

// ---------------------------------------------------------------------------
// Helper: extract first N sentences from a block of text
// ---------------------------------------------------------------------------

function extractFirstSentences(text: string, n: number): string {
  const sentences = text.match(/[^.!?]+[.!?]+/g) ?? []
  return sentences.slice(0, n).join(' ').trim() || text.slice(0, 200)
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface EvidenceSectionProps {
  barrierId: string
  barrier: Barrier
  eventDescription: string
  prediction: PredictResponse
}

/**
 * Renders RAG evidence for the currently selected barrier.
 * Explanation is sourced from BowtieContext (via useExplainCascading),
 * which calls POST /explain-cascading conditioned on the selected barrier pair.
 */
export default function EvidenceSection({
  barrierId: _barrierId,
  barrier: _barrier,
  eventDescription: _eventDescription,
  prediction: _prediction,
}: EvidenceSectionProps) {
  const {
    conditioningBarrierId,
    explanation,
    explanationLoading,
    explanationError,
    narrativeUnavailable,
  } = useBowtieContext()
  const [narrativeExpanded, setNarrativeExpanded] = useState(false)
  const [citationsExpanded, setCitationsExpanded] = useState(false)

  // No conditioning barrier — user hasn't clicked a conditioning context yet
  if (!conditioningBarrierId) {
    return (
      <div className="text-xs text-[#6B7280] italic py-2">
        Click a barrier in the diagram to set conditioning context, then click Analyze to see
        evidence.
      </div>
    )
  }

  // Loading state
  if (explanationLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-[#6B7280] py-2">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span>Loading evidence...</span>
      </div>
    )
  }

  // Error state
  if (explanationError) {
    return (
      <div className="flex items-start gap-2 text-sm py-2" style={{ color: '#E74C3C' }}>
        <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
        <span>{explanationError}</span>
      </div>
    )
  }

  const ev = explanation

  // Not yet loaded (conditioning barrier set but explanation not yet resolved)
  if (!ev) {
    return (
      <div className="text-xs text-[#6B7280] italic py-2">
        Select a barrier and click Analyze to load evidence.
      </div>
    )
  }

  // narrative_unavailable → amber banner; otherwise render narrative text
  const isLowConfidence = narrativeUnavailable

  // Confidence dot: green = evidence available, amber = no snippets yet available, red = unavailable
  const confidenceDotClass = narrativeUnavailable
    ? 'bg-[#C0392B]'
    : ev.unique_incident_count > 0
      ? 'bg-[#1F6F43]'
      : 'bg-[#996515]'

  // degradation_context.recommendations is already string[] from /explain-cascading
  const recommendationCards = ev.degradation_context?.recommendations ?? []

  // Key findings: first 2 sentences of narrative
  const keyFindings = isLowConfidence ? '' : extractFirstSentences(ev.narrative_text, 2)

  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold mb-2 text-[#E8E8E8]">
        Evidence
        <span
          data-testid="confidence-dot"
          className={`w-2.5 h-2.5 rounded-full inline-block ml-2 ${confidenceDotClass}`}
        />
      </h3>

      {isLowConfidence ? (
        <p
          className="text-sm rounded-md p-2"
          style={{ color: '#D68910', backgroundColor: '#1A2332', borderLeft: '3px solid #996515' }}
        >
          No matching incidents found. The model has low confidence in retrieved context for this
          barrier.
        </p>
      ) : (
        <>
          {/* Key Findings callout — only when narrative is long enough to split */}
          {keyFindings && keyFindings !== ev.narrative_text.trim() ? (
            <>
              <div className="bg-[#1A2332] border-l-4 border-[#2C5F7F] p-4 rounded-r-lg">
                <p className="text-xs font-semibold text-[#9CA3AF] uppercase tracking-wider mb-1">
                  Key Findings
                </p>
                <p className="text-sm text-[#E8E8E8] leading-relaxed">{keyFindings}</p>
              </div>

              {/* Full narrative — collapsible, hidden by default but in DOM */}
              <div>
                <button
                  onClick={() => setNarrativeExpanded((v) => !v)}
                  className="flex items-center gap-1 text-xs text-[#6B7280] hover:text-[#9CA3AF] transition-colors mb-1"
                >
                  {narrativeExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  {narrativeExpanded ? 'Collapse analysis' : 'Read full analysis'}
                </button>
                <div className={narrativeExpanded ? '' : 'hidden'}>
                  <SimpleMarkdown
                    content={ev.narrative_text}
                    className="text-sm text-[#9CA3AF] leading-relaxed"
                  />
                </div>
              </div>
            </>
          ) : (
            /* Short narrative — render directly */
            <SimpleMarkdown
              content={ev.narrative_text}
              className="text-sm text-[#9CA3AF] leading-relaxed mb-3"
            />
          )}
        </>
      )}

      {/* Recommendations — pre-parsed string[] from degradation_context */}
      {recommendationCards.length > 0 && (
        <div className="mt-3">
          <h4 className="text-sm font-semibold mb-1 text-[#E8E8E8]">Recommendations</h4>
          <div className="space-y-2">
            {recommendationCards.map((card, idx) => (
              <div
                key={idx}
                className="bg-[#151B24] border-l-2 border-blue-500 rounded-md p-3"
              >
                <SimpleMarkdown content={card} className="text-sm text-[#9CA3AF]" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Performance Influencing Factors (negative) — D020 */}
      {ev.degradation_context?.pif_tags &&
        Object.values(ev.degradation_context.pif_tags).some((f) => f.length > 0) && (
          <div className="mt-3" data-testid="pif-tags-block">
            <h4 className="text-sm font-semibold mb-1 text-[#E8E8E8]">
              Performance Influencing Factors (negative)
            </h4>
            <div className="space-y-1">
              {(['people', 'work', 'organisation'] as const).map((cat) => {
                const factors = ev.degradation_context?.pif_tags?.[cat]
                if (!factors?.length) return null
                return (
                  <p key={cat} className="text-sm text-[#9CA3AF]">
                    <span className="font-medium text-[#E8E8E8]">
                      {cat.charAt(0).toUpperCase() + cat.slice(1)}:
                    </span>{' '}
                    {factors.map((f) => f.replace(/_/g, ' ')).join(', ')}
                  </p>
                )
              })}
            </div>
          </div>
        )}

      {/* Similar Incidents — unique_incident_count is API-sourced (D-M004-03 + D-M004-10) */}
      {ev.evidence_snippets.length > 0 && (
        <div>
          <button
            onClick={() => setCitationsExpanded((v) => !v)}
            className="flex items-center gap-1 text-sm font-semibold text-[#E8E8E8] hover:text-[#9CA3AF] transition-colors mb-1"
          >
            {citationsExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            Similar Incidents ({ev.unique_incident_count})
          </button>
          {citationsExpanded && (
            <div className="space-y-2 mt-1">
              {ev.evidence_snippets.map((s, i) => (
                <div
                  key={`${s.incident_id}-${i}`}
                  className="bg-[#1C2430] rounded-lg p-3 border border-[#2A3442] hover:bg-[#2A3442] transition-colors"
                >
                  <p className="text-xs font-medium text-[#6B7280]">
                    {s.incident_id} — {s.source_agency}
                  </p>
                  <p className="text-sm text-[#E8E8E8] mt-0.5">{s.text}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
