'use client'

import { useBowtieContext } from '@/context/BowtieContext'
import RiskScoreBadge from '@/components/panel/RiskScoreBadge'
import { SHAP_HIDDEN_FEATURES, FEATURE_DISPLAY_NAMES } from '@/lib/shap-config'
import type { BarrierPrediction, Barrier, PredictResponse, RankedBarrier, ScenarioBarrier, ShapValue } from '@/lib/types'

// Re-export for downstream consumers (RankedBarriers imports from here)
export { SHAP_HIDDEN_FEATURES, FEATURE_DISPLAY_NAMES }

// ---------------------------------------------------------------------------
// Pure function
// ---------------------------------------------------------------------------

export interface AtRiskBarrierEntry {
  barrier: Barrier
  probability: number
  topFactor: ShapValue | null
}

export interface CascadingAtRiskEntry {
  control_id: string
  name: string
  probability: number
  riskBand: 'HIGH' | 'MEDIUM' | 'LOW'
  topFactor: string | null
}

/**
 * Build top-N barriers from cascading predictions ranked by composite_risk_score.
 *
 * @param cascadingPredictions - BarrierPrediction[] from BowtieContext.
 * @param ranked               - RankedBarrier[] composite scores from rank-targets.
 * @param scenarioBarriers     - Scenario barrier metadata for names.
 * @param n                    - Max entries to return (default 3).
 */
export function buildTopCascadingBarriers(
  cascadingPredictions: BarrierPrediction[],
  ranked: RankedBarrier[],
  scenarioBarriers: ScenarioBarrier[],
  n = 3,
): CascadingAtRiskEntry[] {
  if (cascadingPredictions.length === 0) return []

  const nameMap = new Map(scenarioBarriers.map((b) => [b.control_id, b.name]))
  const predMap = new Map(cascadingPredictions.map((p) => [p.target_barrier_id, p]))

  // Sort by composite_risk_score (from ranked) if available, else by y_fail_probability
  const sorted = ranked.length > 0
    ? [...ranked]
        .sort((a, b) => b.composite_risk_score - a.composite_risk_score)
        .slice(0, n)
        .map((r) => predMap.get(r.target_barrier_id))
        .filter(Boolean) as BarrierPrediction[]
    : [...cascadingPredictions]
        .sort((a, b) => b.y_fail_probability - a.y_fail_probability)
        .slice(0, n)

  return sorted.map((p) => {
    const topShap = p.shap_values.length > 0
      ? [...p.shap_values].sort((a, b) => Math.abs(b.value) - Math.abs(a.value))[0]
      : null
    return {
      control_id: p.target_barrier_id,
      name: nameMap.get(p.target_barrier_id) ?? p.target_barrier_id,
      probability: p.y_fail_probability,
      riskBand: p.risk_band,
      topFactor: topShap?.display_name ?? topShap?.feature ?? null,
    }
  })
}

/**
 * Build the top-N barriers ranked by failure probability descending.
 *
 * @param barriers   - All barriers from BowtieContext.
 * @param predictions - Map of barrierId → PredictResponse from BowtieContext.
 * @param n          - Max entries to return (default 5).
 * @returns Sorted array of AtRiskBarrierEntry, length ≤ n.
 */
export function buildTopAtRiskBarriers(
  barriers: Barrier[],
  predictions: Record<string, PredictResponse>,
  n = 5,
): AtRiskBarrierEntry[] {
  // Filter to only analyzed barriers
  const analyzed = barriers.filter((b) => predictions[b.id] !== undefined)

  // Sort descending by model1_probability
  const sorted = [...analyzed].sort(
    (a, b) => predictions[b.id].model1_probability - predictions[a.id].model1_probability,
  )

  // Take top n
  const top = sorted.slice(0, n)

  return top.map((barrier) => {
    const pred = predictions[barrier.id]
    const probability = pred.model1_probability

    // Find top SHAP factor: exclude hidden features, sort by |value| desc, take first
    const visibleShap = (pred.model1_shap ?? []).filter(
      (s) => !SHAP_HIDDEN_FEATURES.has(s.feature),
    )
    const sortedShap = [...visibleShap].sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    const topFactor = sortedShap.length > 0 ? sortedShap[0] : null

    return { barrier, probability, topFactor }
  })
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const RISK_BAND_LEVEL: Record<'HIGH' | 'MEDIUM' | 'LOW', 'red' | 'amber' | 'green'> = {
  HIGH: 'red',
  MEDIUM: 'amber',
  LOW: 'green',
}

export default function TopAtRiskBarriers() {
  const { barriers, predictions, cascadingPredictions, cascadingRanked, scenario } = useBowtieContext()
  const isCascadingMode = cascadingPredictions.length > 0 && scenario !== null

  const cascadingItems = isCascadingMode
    ? buildTopCascadingBarriers(cascadingPredictions, cascadingRanked, scenario.barriers, 3)
    : []

  const legacyItems = buildTopAtRiskBarriers(barriers, predictions, 5)

  const isEmpty = isCascadingMode ? cascadingItems.length === 0 : legacyItems.length === 0

  return (
    <div data-testid="top-at-risk-barriers">
      <h3 className="text-base font-semibold mb-3 text-[#E8E8E8]">Top Barriers by Avg Cascade Risk</h3>

      {isEmpty ? (
        <p className="text-sm text-[#6B7280]">
          {isCascadingMode
            ? 'No cascading predictions available'
            : 'Run Analyze Barriers to compute Average Cascading Risk'}
        </p>
      ) : isCascadingMode ? (
        <div>
          {cascadingItems.map((item) => (
            <div key={item.control_id} className="bg-[#151B24] rounded-lg p-3 mb-2">
              <p className="text-base font-semibold text-[#E8E8E8] mb-2">{item.name}</p>
              <RiskScoreBadge
                probability={item.probability}
                riskLevel={RISK_BAND_LEVEL[item.riskBand]}
              />
              {item.topFactor && (
                <div className="flex items-center justify-between text-xs mt-1">
                  <span className="text-[#9CA3AF] truncate mr-2">{item.topFactor}</span>
                  <span className="text-xs text-[#6B7280]">
                    {(item.probability * 100).toFixed(0)}% failure risk
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div>
          {legacyItems.map((item) => {
            const featureName = item.topFactor
              ? (FEATURE_DISPLAY_NAMES[item.topFactor.feature] ?? item.topFactor.feature)
              : null
            const isPositive = item.topFactor ? item.topFactor.value >= 0 : false

            return (
              <div key={item.barrier.id} className="bg-[#151B24] rounded-lg p-3 mb-2">
                <p className="text-base font-semibold text-[#E8E8E8] mb-2">{item.barrier.name}</p>
                <RiskScoreBadge probability={item.probability} riskLevel={item.barrier.riskLevel} />
                {item.topFactor && featureName && (
                  <div className="flex items-center justify-between text-xs mt-1">
                    <span className="text-[#9CA3AF] truncate mr-2">{featureName}</span>
                    <span style={{ color: isPositive ? '#E74C3C' : '#2C5F7F' }}>
                      {isPositive ? '+' : ''}{item.topFactor.value.toFixed(3)}
                    </span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
