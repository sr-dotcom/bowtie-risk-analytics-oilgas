'use client'

import { useEffect, useState } from 'react'
import { Loader2, AlertCircle } from 'lucide-react'
import { explain } from '@/lib/api'
import { useBowtieContext } from '@/context/BowtieContext'
import type { Barrier, ExplainRequest, ExplainResponse, PredictResponse } from '@/lib/types'

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
        console.error('[EvidenceSection] explain failed for barrier', barrierId, message)
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
      <div className="flex items-center gap-2 text-sm text-gray-500 py-2">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span>Loading evidence...</span>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="flex items-start gap-2 text-sm text-red-600 py-2">
        <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
        <span>{error}</span>
      </div>
    )
  }

  const ev = evidence[barrierId]

  // Not yet loaded (should only flash briefly before loading kicks in)
  if (!ev) {
    return (
      <div className="text-xs text-gray-400 italic py-2">
        Select a barrier and click Analyze to load evidence.
      </div>
    )
  }

  // Confidence gate: low confidence narrative from RAG-02
  const isLowConfidence =
    ev.retrieval_confidence < 0.4 ||
    ev.narrative.toLowerCase().includes('no matching incidents found')

  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold mb-2">Evidence</h3>

      {isLowConfidence ? (
        <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-2">
          No matching incidents found. The model has low confidence in retrieved context for this
          barrier.
        </p>
      ) : (
        <p className="text-sm text-gray-700 leading-relaxed mb-3">{ev.narrative}</p>
      )}

      {/* Recommendations (D-12, Fidel-#2) */}
      {ev.recommendations && ev.recommendations.length > 0 && (
        <div className="mt-3">
          <h4 className="text-sm font-semibold mb-1">Recommendations</h4>
          <div className="text-sm text-gray-700 bg-blue-50 border border-blue-100 rounded-md p-3 space-y-1">
            {ev.recommendations.split('\n').filter(line => line.trim()).map((line, i) => (
              <p key={i}>{line}</p>
            ))}
          </div>
        </div>
      )}

      {ev.citations.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold mb-1">Similar Incidents</h4>
          <div className="space-y-2">
            {ev.citations.map((c, i) => (
              <div
                key={`${c.incident_id}-${i}`}
                className="bg-white rounded-md border border-gray-100 p-2 hover:bg-gray-50 transition-colors"
              >
                <p className="text-xs font-medium text-gray-600">
                  {c.incident_id} — {c.barrier_name}
                </p>
                <p className="text-sm text-gray-700 mt-0.5">{c.incident_summary || c.supporting_text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
