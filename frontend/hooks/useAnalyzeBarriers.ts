'use client'

import { useBowtieContext } from '@/context/BowtieContext'
import { predictCascading } from '@/lib/api'
import { mapProbabilityToRiskLevel } from '@/lib/riskScore'
import { getFeatureDisplayName } from '@/lib/shap-config'
import type { BarrierPrediction, RiskThresholds } from '@/lib/types'

// ---------------------------------------------------------------------------
// useAnalyzeBarriers — Average Cascading Risk (S05b/2.5)
//
// Replaces the dead /predict endpoint. For each barrier in the scenario,
// fires /predict-cascading with that barrier as the conditioner (N parallel
// requests). Aggregates each barrier's y_fail_probability across the N-1
// runs where it is a TARGET (not the conditioner) by taking the mean.
// That mean is "Average Cascading Risk" — a portfolio-level metric layered
// on top of the cascading API (see docs/api_contract.md for methodology).
// ---------------------------------------------------------------------------

export function useAnalyzeBarriers(): { analyzeAll: () => Promise<void> } {
  const {
    barriers,
    scenario,
    setIsAnalyzing,
    setAnalysisError,
    updateBarrierCascading,
  } = useBowtieContext()

  async function analyzeAll(): Promise<void> {
    if (barriers.length === 0 || !scenario) return

    setIsAnalyzing(true)
    setAnalysisError(null)

    try {
      // Load risk thresholds from public dir (D006 thresholds: p60=0.45, p80=0.70)
      const thresholdsRes = await fetch('/risk_thresholds.json')
      const thresholds: RiskThresholds = await thresholdsRes.json()

      // N parallel /predict-cascading calls — one per barrier as conditioner.
      // barrier.id === scenario barrier control_id (ensured by addBarrierWithId loading).
      const runs = await Promise.all(
        barriers.map((b) =>
          predictCascading({ scenario, conditioning_barrier_id: b.id })
            .then((res) => ({ conditionerId: b.id, predictions: res.predictions }))
            .catch(() => ({ conditionerId: b.id, predictions: [] as BarrierPrediction[] }))
        )
      )

      // Aggregate per barrier: collect target predictions across all other runs
      for (const b of barriers) {
        const targetPreds = runs
          .filter((r) => r.conditionerId !== b.id)
          .flatMap((r) => r.predictions.filter((p) => p.target_barrier_id === b.id))

        if (targetPreds.length === 0) continue

        // Mean y_fail_probability across N-1 conditioning scenarios
        const avgProb =
          targetPreds.reduce((sum, p) => sum + p.y_fail_probability, 0) / targetPreds.length

        // SHAP from the run with the highest y_fail_probability (most informative cascade)
        const topRun = targetPreds.reduce((best, p) =>
          p.y_fail_probability > best.y_fail_probability ? p : best,
        )
        const topReasons = [...topRun.shap_values]
          .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
          .slice(0, 2)
          .map((sv) => ({
            feature: sv.feature,
            value: sv.value,
            display_name: getFeatureDisplayName(sv.feature) || sv.display_name || sv.feature,
          }))

        const riskLevel = mapProbabilityToRiskLevel(avgProb, thresholds)
        updateBarrierCascading(b.id, avgProb, riskLevel, topReasons)
      }
    } catch (err) {
      setAnalysisError(
        'Backend unavailable. Start the FastAPI server at localhost:8000 and try again.',
      )
      if (process.env.NODE_ENV !== 'production') console.error('Analysis error:', err)
    } finally {
      setIsAnalyzing(false)
    }
  }

  return { analyzeAll }
}
