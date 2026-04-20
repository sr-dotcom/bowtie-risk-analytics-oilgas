'use client'

import { useState, useEffect } from 'react'
import { useBowtieContext } from '@/context/BowtieContext'
import RiskScoreBadge from './RiskScoreBadge'
import ShapWaterfall from './ShapWaterfall'
import EvidenceSection from './EvidenceSection'
import { SHAP_HIDDEN_FEATURES, FEATURE_DISPLAY_NAMES as BASE_FEATURE_DISPLAY_NAMES } from '@/lib/shap-config'
import { explain } from '@/lib/api'
import type { ExplainRequest } from '@/lib/types'
import type { RiskBand } from '@/lib/types'

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'shap', label: 'SHAP Analysis' },
  { id: 'evidence', label: 'Evidence' },
] as const

type TabId = (typeof TABS)[number]['id']

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DetailPanel() {
  const {
    selectedBarrierId, barriers, predictions, eventDescription,
    setViewMode, setDashboardTab, evidence, setEvidence,
    cascadingPredictions, scenario, selectedTargetBarrierId,
    explanation, explanationLoading,
  } = useBowtieContext()
  const [activeTab, setActiveTab] = useState<TabId>('overview')

  // Derive barrier and pred before hooks so the auto-load effect can reference them.
  const barrier = barriers.find((b) => b.id === selectedBarrierId)
  const pred = selectedBarrierId ? predictions[selectedBarrierId] : undefined

  const isCascadingMode = cascadingPredictions.length > 0 && scenario !== null

  // Pre-load evidence when a barrier with a prediction is selected — by the time
  // the user clicks the Evidence tab the data is already in context.
  // Must sit before any early return to satisfy React's Rules of Hooks.
  useEffect(() => {
    if (!selectedBarrierId || !barrier || !pred || evidence[selectedBarrierId]) return

    let cancelled = false
    const req: ExplainRequest = {
      barrier_family: barrier.barrier_family,
      barrier_type: barrier.barrier_type,
      side: barrier.side,
      barrier_role: barrier.barrierRole,
      event_description: eventDescription,
      shap_factors: pred.model1_shap,
      risk_level: pred.risk_level || '',
    }

    explain(req)
      .then((r) => { if (!cancelled) setEvidence(selectedBarrierId, r) })
      .catch(() => { /* EvidenceSection renders its own error when evidence is absent */ })

    return () => { cancelled = true }
  // pred != null captures the transition from unanalyzed → analyzed without
  // needing the full pred object as a dependency (avoids stale-closure issues).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedBarrierId, pred != null])

  // ---------------------------------------------------------------------------
  // Cascading detail view
  // ---------------------------------------------------------------------------
  if (isCascadingMode && selectedTargetBarrierId) {
    const targetSb = scenario.barriers.find((b) => b.control_id === selectedTargetBarrierId)
    const targetPred = cascadingPredictions.find((p) => p.target_barrier_id === selectedTargetBarrierId)
    const riskBand = targetPred?.risk_band as RiskBand | undefined
    const snippets = explanation?.evidence_snippets ?? []
    const degradation = explanation?.degradation_context

    return (
      <div className="flex flex-col h-full">
        <div className="pb-3">
          <h2 className="text-xl font-semibold mb-1 text-[#E8ECF4]">
            {targetSb?.name ?? selectedTargetBarrierId}
          </h2>
          <p className="text-sm text-[#8B93A8] mb-3">Cascading analysis</p>
        </div>

        <div className="flex-1 overflow-y-auto space-y-4">
          {targetPred && (
            <RiskScoreBadge
              probability={targetPred.y_fail_probability}
              riskBand={riskBand}
            />
          )}

          {targetPred && targetPred.shap_values.length > 0 && (
            <ShapWaterfall cascadingShap={targetPred.shap_values} />
          )}

          {explanationLoading && (
            <p className="text-sm text-[#5A6178] animate-pulse">Loading evidence…</p>
          )}

          {degradation && degradation.pif_mentions.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-[#5A6178] mb-2 uppercase tracking-wider">
                Degradation Factors
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {degradation.pif_mentions.map((m, i) => (
                  <span key={i} className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30">
                    {m}
                  </span>
                ))}
              </div>
            </div>
          )}

          {explanation && !explanation.narrative_unavailable && explanation.narrative_text && (
            <div className="bg-[#1A2332] border-l-4 border-blue-400 p-4 rounded-r-lg">
              <p className="text-xs font-semibold text-[#8B93A8] uppercase tracking-wider mb-1">Analysis</p>
              <p className="text-sm text-[#E8ECF4] leading-relaxed">{explanation.narrative_text}</p>
            </div>
          )}

          {snippets.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-[#E8ECF4] mb-2">
                Similar Incidents ({snippets.length})
              </h4>
              <div className="space-y-2">
                {snippets.map((s, i) => (
                  <div key={`${s.incident_id}-${i}`} className="bg-[#1E2230] rounded-lg p-3 border border-[#2E3348]">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-[#242836] border border-[#2E3348] text-[#8B93A8]">
                        {s.source_agency}
                      </span>
                      <span className="text-xs text-[#5A6178]">{s.incident_id}</span>
                    </div>
                    <p className="text-sm text-[#E8ECF4]">{s.text}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  // State 1: No barrier selected
  if (!selectedBarrierId) {
    return (
      <div className="h-full flex items-start pt-8 justify-center">
        <p className="text-sm text-[#5A6178] text-center px-4">
          Click a barrier node to see its risk analysis.
        </p>
      </div>
    )
  }

  if (!barrier) {
    return (
      <div className="h-full flex items-start pt-8 justify-center">
        <p className="text-sm text-[#5A6178] text-center px-4">
          Click a barrier node to see its risk analysis.
        </p>
      </div>
    )
  }

  // State 2: Barrier selected but not yet analyzed
  if (!pred) {
    return (
      <div className="h-full flex items-start pt-8 justify-center">
        <p className="text-sm text-[#5A6178] text-center px-4">
          Run Analyze Barriers to see risk analysis for this barrier.
        </p>
      </div>
    )
  }

  // State 3: Full analysis view
  const hasModel2 = pred.model2_shap && pred.model2_shap.length > 0

  const featureDisplayNames: Record<string, string> = { ...BASE_FEATURE_DISPLAY_NAMES }
  if (pred.degradation_factors) {
    for (const df of pred.degradation_factors) {
      featureDisplayNames[df.source_feature] = df.factor
    }
  }

  // Build overview factor summary from visible SHAP values
  const visibleShap = pred.model1_shap.filter((s) => !SHAP_HIDDEN_FEATURES.has(s.feature))
  const topFactors = [...visibleShap]
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, 5)

  return (
    <div className="flex flex-col h-full">
      {/* Barrier identity — always visible above tabs */}
      <div className="pb-3">
        <h2 className="text-xl font-semibold mb-1 text-[#E8ECF4]">{barrier.name}</h2>
        <p className="text-sm text-[#8B93A8] mb-3">{barrier.barrierRole}</p>

        {(pred.barrier_type_display || pred.lod_display) && (
          <div className="flex flex-wrap gap-2">
            {pred.barrier_type_display && (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-[#242836] border border-[#2E3348] text-[#8B93A8]">
                {pred.barrier_type_display}
              </span>
            )}
            {pred.lod_display && (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-[#242836] border border-[#2E3348] text-[#8B93A8]">
                {pred.lod_display}
              </span>
            )}
          </div>
        )}

        {/* Cross-link navigation — only when analysis is available */}
        <button
          data-testid="view-full-analysis-btn"
          className="mt-3 px-3 py-1.5 text-xs bg-[#242836] border border-[#2E3348] text-[#8B93A8] hover:text-[#E8ECF4] rounded-md transition-colors"
          onClick={() => {
            setViewMode('dashboard')
            setDashboardTab('ranked-barriers')
            // selectedBarrierId already set — redundant but ensures it persists
          }}
        >
          View Full Analysis
        </button>
      </div>

      {/* Tab bar */}
      <div className="flex bg-[#242836] rounded-t-md border-b border-[#2E3348] flex-shrink-0">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-xs font-medium transition-colors cursor-pointer ${
              activeTab === tab.id
                ? 'text-[#E8ECF4] border-b-2 border-[#3B82F6]'
                : 'text-[#5A6178] hover:text-[#8B93A8]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto pt-4">
        {/* Overview tab */}
        {activeTab === 'overview' && (
          <div className="space-y-4">
            <RiskScoreBadge
              probability={pred.model1_probability}
              riskLevel={barrier.riskLevel}
            />

            {/* Plain-language risk summary */}
            {(() => {
              const topShap = topFactors[0]
              const topName = topShap ? (featureDisplayNames[topShap.feature] ?? topShap.feature) : null
              const rl = barrier.riskLevel
              return (
                <div className="bg-[#0F1117] rounded-lg p-3">
                  <p className="text-sm text-[#8B93A8] leading-relaxed">
                    {rl === 'green' && (
                      <>This barrier has demonstrated <span className="text-green-400 font-medium">historically low failure rates</span> across similar operational contexts in the BSEE/CSB incident database.</>
                    )}
                    {rl === 'amber' && (
                      <>This barrier shows <span className="text-amber-400 font-medium">mixed historical reliability</span> — some similar barriers have failed under comparable conditions.</>
                    )}
                    {rl === 'red' && (
                      <>This barrier has <span className="text-red-400 font-medium">significant historical failure patterns</span> in similar operational contexts. Priority review recommended.</>
                    )}
                    {topName && (
                      <>{' '}Top contributing factor: <span className="text-[#E8ECF4] font-medium">{topName}</span>.</>
                    )}
                  </p>
                </div>
              )
            })()}

            <div>
              <h3 className="text-base font-semibold mb-1 text-[#E8ECF4]">Barrier Analysis Factors</h3>
              <p className="text-xs text-[#5A6178] mb-3">
                Model baseline (avg. across all barriers): {pred.model1_base_value.toFixed(3)}
              </p>

              {topFactors.length > 0 && (
                <div className="space-y-1.5">
                  {topFactors.map((s) => {
                    const name = featureDisplayNames[s.feature] ?? s.feature
                    const isRisk = s.value >= 0
                    return (
                      <div
                        key={s.feature}
                        className="flex items-center justify-between text-xs px-2 py-1.5 rounded bg-[#242836]"
                      >
                        <span className="text-[#E8ECF4] truncate mr-2">{name}</span>
                        <span className={isRisk ? 'text-red-400' : 'text-blue-400'}>
                          {isRisk ? '+' : ''}{s.value.toFixed(3)}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Degradation factors as colored badges */}
              {pred.degradation_factors && pred.degradation_factors.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-xs font-medium text-[#5A6178] mb-2 uppercase tracking-wider">
                    Degradation Factors
                  </h4>
                  <div className="flex flex-wrap gap-1.5">
                    {pred.degradation_factors
                      .filter((df) => !SHAP_HIDDEN_FEATURES.has(df.source_feature))
                      .map((df, i) => {
                        const absContrib = Math.abs(df.contribution)
                        const strength = absContrib >= 0.15 ? 'strong' : absContrib >= 0.05 ? 'moderate' : 'weak'
                        return (
                          <span
                            key={i}
                            className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium ${
                              strength === 'strong'
                                ? 'bg-red-500/15 text-red-400 border border-red-500/30'
                                : strength === 'moderate'
                                ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                                : 'bg-blue-500/15 text-blue-400 border border-blue-500/30'
                            }`}
                          >
                            {df.factor}
                            <span className="ml-1.5 opacity-70 text-[10px]">({strength})</span>
                          </span>
                        )
                      })}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* SHAP Analysis tab */}
        {activeTab === 'shap' && (
          <div className="space-y-1">
            <ShapWaterfall
              shap={pred.model1_shap}
              baseValue={pred.model1_base_value}
              featureDisplayNames={featureDisplayNames}
              hiddenFeatures={SHAP_HIDDEN_FEATURES}
            />

            {hasModel2 && (
              <div className="mt-4 pt-4 border-t border-[#2E3348]">
                <h3 className="text-base font-semibold mb-2 text-[#E8ECF4]">Human Factor Sensitivity</h3>
                <ShapWaterfall
                  shap={pred.model2_shap}
                  baseValue={pred.model2_base_value}
                  featureDisplayNames={featureDisplayNames}
                  hiddenFeatures={SHAP_HIDDEN_FEATURES}
                />
              </div>
            )}
          </div>
        )}

        {/* Evidence tab */}
        {activeTab === 'evidence' && (
          <EvidenceSection
            barrierId={barrier.id}
            barrier={barrier}
            eventDescription={eventDescription}
            prediction={pred}
          />
        )}
      </div>
    </div>
  )
}
