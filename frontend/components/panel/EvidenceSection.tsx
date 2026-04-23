'use client'

import { useEffect, useState } from 'react'
import { Loader2, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react'
import { explain } from '@/lib/api'
import { useBowtieContext } from '@/context/BowtieContext'
import type { Barrier, ExplainRequest, ExplainResponse, PredictResponse } from '@/lib/types'
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
 * Loads RAG evidence on-demand per barrier click (D-15).
 *
 * Evidence is cached in BowtieContext so re-clicking the same barrier
 * does not trigger a second /explain call.
 */
export default function EvidenceSection({
  barrierId,
  barrier,
  eventDescription,
  prediction,
}: EvidenceSectionProps) {
  const { evidence, setEvidence } = useBowtieContext()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [narrativeExpanded, setNarrativeExpanded] = useState(false)
  const [citationsExpanded, setCitationsExpanded] = useState(false)

  // Load evidence on mount or when barrierId changes (D-15: on-demand per click)
  useEffect(() => {
    // Skip if already cached
    if (evidence[barrierId]) return

    const req: ExplainRequest = {
      barrier_family: barrier.barrier_family,
      barrier_type: barrier.barrier_type,
      side: barrier.side,
      barrier_role: barrier.barrierRole,
      event_description: eventDescription,
      shap_factors: prediction.model1_shap,
      risk_level: prediction.risk_level || '',  // Bug #3 fix: pass prediction context
    }

    setLoading(true)
    setError(null)

    explain(req)
      .then((response: ExplainResponse) => {
        setEvidence(barrierId, response)
      })
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : String(err)
        if (process.env.NODE_ENV !== 'production') console.error('[EvidenceSection] explain failed for barrier', barrierId, message)
        setError(`Evidence retrieval failed: ${message}`)
      })
      .finally(() => {
        setLoading(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [barrierId]) // Re-run only when barrier changes

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-[#6B7280] py-2">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span>Loading evidence...</span>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="flex items-start gap-2 text-sm py-2" style={{ color: '#E74C3C' }}>
        <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
        <span>{error}</span>
      </div>
    )
  }

  const ev = evidence[barrierId]

  // Not yet loaded (should only flash briefly before loading kicks in)
  if (!ev) {
    return (
      <div className="text-xs text-[#6B7280] italic py-2">
        Select a barrier and click Analyze to load evidence.
      </div>
    )
  }

  // Confidence gate: low confidence narrative from RAG-02
  const isLowConfidence =
    ev.retrieval_confidence < 0.4 ||
    ev.narrative.toLowerCase().includes('no matching incidents found')

  // Derive confidence dot color from retrieval_confidence threshold
  const confidenceDotClass =
    ev.retrieval_confidence >= 0.7
      ? 'bg-[#1F6F43]'
      : ev.retrieval_confidence >= 0.4
        ? 'bg-[#996515]'
        : 'bg-[#C0392B]'

  // Parse recommendations string into individual cards
  const recommendationCards = ev.recommendations
    ? ev.recommendations
        .split('\n')
        .map((line) => line.replace(/^[-*] /, '').trim())
        .filter((line) => line.length > 0)
    : []

  // Key findings: first 2 sentences of narrative
  const keyFindings = isLowConfidence ? '' : extractFirstSentences(ev.narrative, 2)

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
          {keyFindings && keyFindings !== ev.narrative.trim() ? (
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
                  <SimpleMarkdown content={ev.narrative} className="text-sm text-[#9CA3AF] leading-relaxed" />
                </div>
              </div>
            </>
          ) : (
            /* Short narrative — render directly */
            <SimpleMarkdown content={ev.narrative} className="text-sm text-[#9CA3AF] leading-relaxed mb-3" />
          )}
        </>
      )}

      {/* Recommendations (D-12, Fidel-#2) — per-card rendering, always visible */}
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

      {/* Similar Incidents — collapsible, collapsed by default */}
      {ev.citations.length > 0 && (
        <div>
          <button
            onClick={() => setCitationsExpanded((v) => !v)}
            className="flex items-center gap-1 text-sm font-semibold text-[#E8E8E8] hover:text-[#9CA3AF] transition-colors mb-1"
          >
            {citationsExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            {/* Use unique_incident_count, not snippets.length, for domain-expert-facing label */}
            Similar Incidents ({new Set(ev.citations.map(c => c.incident_id)).size})
          </button>
          {citationsExpanded && (
            <div className="space-y-2 mt-1">
              {ev.citations.map((c, i) => (
                <div
                  key={`${c.incident_id}-${i}`}
                  className="bg-[#1C2430] rounded-lg p-3 border border-[#2A3442] hover:bg-[#2A3442] transition-colors"
                >
                  <p className="text-xs font-medium text-[#6B7280]">
                    {c.incident_id} — {c.barrier_name}
                  </p>
                  <p className="text-sm text-[#E8E8E8] mt-0.5">{c.incident_summary || c.supporting_text}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
