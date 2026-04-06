'use client'

import { useBowtieContext } from '@/context/BowtieContext'
import { predict } from '@/lib/api'
import { mapProbabilityToRiskLevel } from '@/lib/riskScore'
import type { PredictRequest, RiskThresholds } from '@/lib/types'
import { SOURCE_AGENCY_DEFAULT } from '@/components/sidebar/constants'

// ---------------------------------------------------------------------------
// useAnalyzeBarriers
// Shared hook that fires /predict for ALL barriers in parallel and updates
// context state.  Extracted from BarrierForm.handleAnalyze so that
// DashboardView can also trigger analysis on mount (auto-batch).
// ---------------------------------------------------------------------------

export function useAnalyzeBarriers(): { analyzeAll: () => Promise<void> } {
  const {
    barriers,
    pifFlags,
    setIsAnalyzing,
    setAnalysisError,
    setPrediction,
    updateBarrierRisk,
  } = useBowtieContext()

  async function analyzeAll(): Promise<void> {
    if (barriers.length === 0) return

    setIsAnalyzing(true)
    setAnalysisError(null)

    try {
      // Load risk thresholds from public dir
      const thresholdsRes = await fetch('/risk_thresholds.json')
      const thresholds: RiskThresholds = await thresholdsRes.json()

      // Build predict requests for ALL barriers (prevention + mitigation)
      const requests = barriers.map((b) => {
        const req: PredictRequest = {
          side: b.side,
          barrier_type: b.barrier_type,
          line_of_defense: b.line_of_defense,
          barrier_family: b.barrier_family,
          source_agency: SOURCE_AGENCY_DEFAULT,
          // 9 active PIFs from context pifFlags state (Bug #2 fix)
          // pif_fatigue, pif_workload, pif_time_pressure excluded from training scope
          pif_competence: pifFlags.pif_competence,
          pif_communication: pifFlags.pif_communication,
          pif_situational_awareness: pifFlags.pif_situational_awareness,
          pif_procedures: pifFlags.pif_procedures,
          pif_tools_equipment: pifFlags.pif_tools_equipment,
          pif_safety_culture: pifFlags.pif_safety_culture,
          pif_management_of_change: pifFlags.pif_management_of_change,
          pif_supervision: pifFlags.pif_supervision,
          pif_training: pifFlags.pif_training,
          supporting_text_count: 0,
        }
        return { barrier: b, req }
      })

      // Fire all predictions in parallel per D-10
      const results = await Promise.allSettled(
        requests.map(({ req }) => predict(req)),
      )

      results.forEach((result, idx) => {
        const barrier = requests[idx].barrier
        if (result.status === 'fulfilled') {
          const response = result.value
          const riskLevel = mapProbabilityToRiskLevel(response.model1_probability, thresholds)
          // Store full prediction response (SHAP values, etc.) in predictions map
          setPrediction(barrier.id, response)
          // Update barrier's riskLevel + probability so BowtieFlow node colors update
          updateBarrierRisk(barrier.id, riskLevel, response.model1_probability)
        } else {
          setAnalysisError(
            `Prediction failed for ${barrier.name}. Check the server logs and retry.`,
          )
        }
      })
    } catch (err) {
      setAnalysisError(
        'Backend unavailable. Start the FastAPI server at localhost:8000 and try again.',
      )
      console.error('Analysis error:', err)
    } finally {
      setIsAnalyzing(false)
    }
  }

  return { analyzeAll }
}
