'use client'

import { useState, useEffect } from 'react'
import { useBowtieContext } from '@/context/BowtieContext'
import EvidenceSection from '@/components/panel/EvidenceSection'
import SimpleMarkdown from '@/components/ui/SimpleMarkdown'
import type { RiskLevel } from '@/lib/types'

// ---------------------------------------------------------------------------
// Risk label mapping (inline — mirrors RankedBarriers badge labels)
// ---------------------------------------------------------------------------

const PILL_LABELS: Record<RiskLevel, string> = {
  red: 'High',
  amber: 'Medium',
  green: 'Low',
  unanalyzed: 'Pending',
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function EvidenceView() {
  const {
    barriers,
    predictions,
    eventDescription,
    explanation,
    explanationLoading,
    explanationError,
    cascadingPredictions,
    scenario,
    selectedTargetBarrierId,
    setSelectedTargetBarrierId,
  } = useBowtieContext()

  const isCascadingMode = cascadingPredictions.length > 0 && scenario !== null

  // Legacy: barriers that have a prediction result
  const analyzedBarriers = barriers.filter((b) => predictions[b.id])

  const [legacySelectedId, setLegacySelectedId] = useState<string | null>(
    analyzedBarriers[0]?.id ?? null,
  )

  // Reset legacy selection when the analyzed set changes
  useEffect(() => {
    if (analyzedBarriers.length === 0) { setLegacySelectedId(null); return }
    const stillValid = analyzedBarriers.some((b) => b.id === legacySelectedId)
    if (!stillValid) setLegacySelectedId(analyzedBarriers[0].id)
  }, [analyzedBarriers.length]) // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------------------
  // Cascading Evidence View
  // ---------------------------------------------------------------------------

  if (isCascadingMode) {
    const snippets = explanation?.evidence_snippets ?? []
    const targetName = selectedTargetBarrierId
      ? (scenario.barriers.find((b) => b.control_id === selectedTargetBarrierId)?.name
          ?? selectedTargetBarrierId)
      : null

    return (
      <div className="w-full" data-testid="evidence-view">
        {/* Barrier selector from scenario */}
        <div className="mb-6">
          <label
            htmlFor="evidence-cascading-select"
            className="block text-xs font-medium text-[#6B7280] mb-1"
          >
            Select target barrier
          </label>
          <select
            id="evidence-cascading-select"
            value={selectedTargetBarrierId ?? ''}
            onChange={(e) => setSelectedTargetBarrierId(e.target.value || null)}
            className="w-full bg-[#151B24] border border-[#2A3442] rounded-md px-3 py-2 text-sm text-[#E8E8E8] focus:outline-none focus:ring-1 focus:ring-[#2C5F7F]"
          >
            <option value="">— Select barrier —</option>
            {cascadingPredictions.map((p) => {
              const sb = scenario.barriers.find((b) => b.control_id === p.target_barrier_id)
              return (
                <option key={p.target_barrier_id} value={p.target_barrier_id}>
                  {sb?.name ?? p.target_barrier_id} ({p.risk_band})
                </option>
              )
            })}
          </select>
        </div>

        {!selectedTargetBarrierId && (
          <p className="text-sm text-[#6B7280]">Select a barrier above to view evidence.</p>
        )}

        {selectedTargetBarrierId && explanationLoading && (
          <p className="text-sm text-[#6B7280] animate-pulse">Loading evidence…</p>
        )}

        {selectedTargetBarrierId && explanationError && (
          <p className="text-sm" style={{ color: '#E74C3C' }}>Evidence retrieval failed: {explanationError}</p>
        )}

        {selectedTargetBarrierId && explanation && (
          <div className="space-y-4">
            {/* Narrative */}
            {!explanation.narrative_unavailable && explanation.narrative_text && (
              <div className="bg-[#1A2332] border-l-4 border-[#2C5F7F] p-4 rounded-r-lg">
                <p className="text-xs font-semibold text-[#9CA3AF] uppercase tracking-wider mb-1">
                  Analysis
                </p>
                <SimpleMarkdown content={explanation.narrative_text} className="text-sm text-[#E8E8E8] leading-relaxed" />
              </div>
            )}
            {explanation.narrative_unavailable && (
              <p
                className="text-sm rounded-md p-2"
                style={{ color: '#D68910', backgroundColor: '#1A2332', borderLeft: '3px solid #996515' }}
              >
                Evidence unavailable for this barrier combination.
              </p>
            )}

            {/* Evidence snippets */}
            {snippets.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-[#E8E8E8] mb-2">
                  Similar Incidents ({snippets.length})
                </h4>
                <div className="space-y-2">
                  {snippets.map((s, i) => (
                    <div
                      key={`${s.incident_id}-${i}`}
                      className="bg-[#1C2430] rounded-lg p-3 border border-[#2A3442]"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-[#151B24] border border-[#2A3442] text-[#9CA3AF]">
                          {s.source_agency}
                        </span>
                        <span className="text-xs text-[#6B7280]">{s.incident_id}</span>
                        <span className="ml-auto text-xs text-[#6B7280]">
                          score: {s.score.toFixed(2)}
                        </span>
                      </div>
                      <p className="text-sm text-[#E8E8E8]">{s.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Legacy Evidence View (old /explain endpoint)
  // ---------------------------------------------------------------------------

  const legacyBarrier = analyzedBarriers.find((b) => b.id === legacySelectedId) ?? null
  const legacyPrediction = legacySelectedId ? predictions[legacySelectedId] : null

  return (
    <div className="w-full" data-testid="evidence-view">
      {analyzedBarriers.length === 0 ? (
        <div className="flex items-center justify-center py-16">
          <p className="text-sm text-[#6B7280]">Run analysis to view barrier evidence</p>
        </div>
      ) : (
        <>
          <div className="mb-6">
            <label
              htmlFor="evidence-barrier-select"
              className="block text-xs font-medium text-[#6B7280] mb-1"
            >
              Select barrier
            </label>
            <select
              id="evidence-barrier-select"
              value={legacySelectedId ?? ''}
              onChange={(e) => setLegacySelectedId(e.target.value || null)}
              className="w-full bg-[#151B24] border border-[#2A3442] rounded-md px-3 py-2 text-sm text-[#E8E8E8] focus:outline-none focus:ring-1 focus:ring-[#2C5F7F]"
            >
              {analyzedBarriers.map((barrier) => (
                <option key={barrier.id} value={barrier.id}>
                  {barrier.name} ({PILL_LABELS[barrier.riskLevel]})
                </option>
              ))}
            </select>
          </div>

          {legacyBarrier && legacyPrediction && (
            <EvidenceSection
              barrierId={legacyBarrier.id}
              barrier={legacyBarrier}
              eventDescription={eventDescription}
              prediction={legacyPrediction}
            />
          )}
        </>
      )}
    </div>
  )
}
