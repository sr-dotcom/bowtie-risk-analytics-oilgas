'use client'

import { useHealth } from '@/hooks/useHealth'
import { getDenominatorValue } from '@/lib/denominators'

export default function ProvenanceStrip() {
  const { health, loading } = useHealth()

  // All numeric values from configs/denominators.json — no hardcoded literals in component
  const incidents = getDenominatorValue('rag_corpus_incidents') as number
  const barriers = getDenominatorValue('rag_corpus_barriers') as number
  const trainingPairs = getDenominatorValue('m003_cascade_training_pair_rows') as number
  const aucMean = getDenominatorValue('cascade_model_cv_auc_mean') as number
  const aucStd = getDenominatorValue('cascade_model_cv_auc_std') as number

  // Format per UI-CONTEXT.md §10: "AUC 0.76 ± 0.07"
  const aucDisplay = `${Number(aucMean).toFixed(2)} ± ${Number(aucStd).toFixed(2)}`
  // "1,161 barriers" — locale-formatted with thousands separator
  const barriersDisplay = Number(barriers).toLocaleString('en-US')

  if (loading) {
    return (
      <footer className="sticky bottom-0 z-10 flex-shrink-0 text-[11px] leading-[1.4] text-[#6B7280] py-3 px-4 border-t border-[#2A3442] bg-[#151B24]">
        <div>Loading provenance...</div>
      </footer>
    )
  }

  // Model loaded if at least one model entry reports loaded: true
  const modelLoaded =
    health?.models != null && Object.values(health.models).some((m) => m.loaded)

  // RAG loaded if corpus_size is non-zero
  const ragLoaded = (health?.rag?.corpus_size ?? 0) > 0

  return (
    <footer className="sticky bottom-0 z-10 flex-shrink-0 text-[11px] leading-[1.4] text-[#6B7280] py-3 px-4 border-t border-[#2A3442] bg-[#151B24] space-y-1">
      {/* Line 1 — predictions provenance (UI-CONTEXT.md §10) */}
      <div className="flex items-start justify-between gap-4">
        <span>
          Predictions: XGBoost cascade · {trainingPairs} rows from {incidents} BSEE+CSB incidents
          {' · '}5-fold CV AUC {aucDisplay}
          {!modelLoaded && (
            <span className="text-[#E74C3C] ml-2">⚠ model not loaded</span>
          )}
        </span>
        {/* "View model card →" — greyed-out, non-clickable until M004 model card view ships */}
        <span className="flex-shrink-0 opacity-50 cursor-default select-none">
          View model card →
        </span>
      </div>

      {/* Line 2 — evidence provenance (UI-CONTEXT.md §10) */}
      <div>
        Evidence: hybrid RAG · {barriersDisplay} barriers · {incidents} incidents · 4-stage
        retrieval
        {!ragLoaded && (
          <span className="text-[#E74C3C] ml-2">⚠ RAG not loaded</span>
        )}
      </div>
    </footer>
  )
}
