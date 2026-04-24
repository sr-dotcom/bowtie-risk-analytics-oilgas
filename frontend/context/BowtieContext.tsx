'use client'

import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import type {
  BarrierPrediction,
  Barrier,
  ExplainCascadingResponse,
  ExplainResponse,
  PifFlags,
  PredictResponse,
  RankedBarrier,
  RiskLevel,
  Scenario,
} from '@/lib/types'
import { DEFAULT_PIF_FLAGS } from '@/lib/types'
import { useAnalyzeCascading, type AnalysisState } from '@/hooks/useAnalyzeCascading'
import { useExplainCascading } from '@/hooks/useExplainCascading'

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

interface BowtieState {
  // ── Legacy barrier state (old /predict flow) ──
  eventDescription: string
  barriers: Barrier[]
  predictions: Record<string, PredictResponse>
  selectedBarrierId: string | null
  evidence: Record<string, ExplainResponse>
  isAnalyzing: boolean
  analysisError: string | null
  pifFlags: PifFlags
  /** viewMode controls which top-level view is rendered */
  viewMode: 'diagram' | 'pathway' | 'dashboard'
  dashboardTab: string | null
  analyticsTab: string

  setEventDescription: (v: string) => void
  addBarrier: (b: Omit<Barrier, 'id' | 'riskLevel'>) => void
  addBarrierWithId: (b: Omit<Barrier, 'riskLevel'>) => void
  removeBarrier: (id: string) => void
  updateBarrierRisk: (id: string, riskLevel: RiskLevel, probability: number) => void
  updateBarrierCascading: (
    id: string,
    avgProb: number,
    riskLevel: RiskLevel,
    topReasons: { feature: string; value: number; display_name: string }[],
  ) => void
  setPrediction: (id: string, pred: PredictResponse) => void
  setSelectedBarrierId: (id: string | null) => void
  setEvidence: (id: string, ev: ExplainResponse) => void
  setIsAnalyzing: (v: boolean) => void
  setAnalysisError: (v: string | null) => void
  setPifFlags: (flags: PifFlags) => void
  togglePif: (key: keyof PifFlags) => void
  setViewMode: (v: 'diagram' | 'pathway' | 'dashboard') => void
  setDashboardTab: (tab: string | null) => void
  setAnalyticsTab: (tab: string) => void

  // ── Cascading state (new /predict-cascading flow — S05a/T04) ──
  scenario: Scenario | null
  conditioningBarrierId: string | null
  selectedTargetBarrierId: string | null
  cascadingPredictions: BarrierPrediction[]
  cascadingRanked: RankedBarrier[]
  cascadingAnalysisState: AnalysisState
  explanation: ExplainCascadingResponse | null
  explanationLoading: boolean
  explanationError: string | null
  narrativeUnavailable: boolean

  setScenario: (s: Scenario | null) => void
  setConditioningBarrierId: (id: string | null) => void
  setSelectedTargetBarrierId: (id: string | null) => void
  clearCascading: () => void
}

const BowtieContext = createContext<BowtieState | null>(null)

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function BowtieProvider({
  children,
  initialBarriers = [],
  initialPredictions = {},
  initialViewMode = 'diagram',
  initialDashboardTab = null,
  initialSelectedBarrierId = null,
  initialScenario = null,
  initialCascadingPredictions = [],
}: {
  children: ReactNode
  initialBarriers?: Barrier[]
  initialPredictions?: Record<string, PredictResponse>
  initialViewMode?: 'diagram' | 'pathway' | 'dashboard'
  initialDashboardTab?: string | null
  initialSelectedBarrierId?: string | null
  initialScenario?: Scenario | null
  initialCascadingPredictions?: BarrierPrediction[]
}) {
  // ── Legacy state ──
  const [eventDescription, setEventDescription] = useState<string>('')
  const [barriers, setBarriers] = useState<Barrier[]>(initialBarriers)
  const [predictions, setPredictions] = useState<Record<string, PredictResponse>>(initialPredictions)
  const [selectedBarrierId, setSelectedBarrierId] = useState<string | null>(initialSelectedBarrierId)
  const [evidenceMap, setEvidenceMap] = useState<Record<string, ExplainResponse>>({})
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [pifFlags, setPifFlags] = useState<PifFlags>({ ...DEFAULT_PIF_FLAGS })
  const [viewMode, setViewMode] = useState<'diagram' | 'pathway' | 'dashboard'>(initialViewMode)
  const [dashboardTab, setDashboardTab] = useState<string | null>(initialDashboardTab)
  const [analyticsTab, setAnalyticsTab] = useState<string>('executive-summary')

  // ── Cascading state ──
  const [scenario, setScenario] = useState<Scenario | null>(initialScenario)
  const [conditioningBarrierId, setConditioningBarrierId] = useState<string | null>(null)
  const [selectedTargetBarrierId, setSelectedTargetBarrierId] = useState<string | null>(null)

  const { analyze, state: cascadingAnalysisState } = useAnalyzeCascading()

  // Derive flat arrays from analysis state for convenience
  const cascadingPredictions =
    cascadingAnalysisState.status === 'success'
      ? cascadingAnalysisState.predictions
      : initialCascadingPredictions

  const cascadingRanked =
    cascadingAnalysisState.status === 'success' ? cascadingAnalysisState.ranked : []

  // Fire cascading analysis whenever conditioningBarrierId or scenario changes.
  useEffect(() => {
    if (conditioningBarrierId && scenario) {
      analyze(scenario, conditioningBarrierId)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conditioningBarrierId, scenario])

  const {
    explanation,
    loading: explanationLoading,
    error: explanationError,
    narrativeUnavailable,
  } = useExplainCascading(conditioningBarrierId, selectedTargetBarrierId, scenario)

  // ── Legacy helpers ──

  function togglePif(key: keyof PifFlags): void {
    setPifFlags((prev) => ({ ...prev, [key]: prev[key] === 1 ? 0 : 1 }))
  }

  function addBarrier(b: Omit<Barrier, 'id' | 'riskLevel'>): void {
    const newBarrier: Barrier = { ...b, id: crypto.randomUUID(), riskLevel: 'unanalyzed' }
    setBarriers((prev) => [...prev, newBarrier])
  }

  function addBarrierWithId(b: Omit<Barrier, 'riskLevel'>): void {
    const newBarrier: Barrier = { ...b, riskLevel: 'unanalyzed' }
    setBarriers((prev) => [...prev, newBarrier])
  }

  function updateBarrierRisk(id: string, riskLevel: RiskLevel, probability: number): void {
    setBarriers((prev) =>
      prev.map((b) => (b.id === id ? { ...b, riskLevel, probability } : b)),
    )
  }

  function updateBarrierCascading(
    id: string,
    avgProb: number,
    riskLevel: RiskLevel,
    topReasons: { feature: string; value: number; display_name: string }[],
  ): void {
    setBarriers((prev) =>
      prev.map((b) =>
        b.id === id
          ? { ...b, riskLevel, probability: avgProb, average_cascading_probability: avgProb, top_reasons: topReasons }
          : b,
      ),
    )
  }

  function removeBarrier(id: string): void {
    setBarriers((prev) => prev.filter((b) => b.id !== id))
    setPredictions((prev) => { const next = { ...prev }; delete next[id]; return next })
    setEvidenceMap((prev) => { const next = { ...prev }; delete next[id]; return next })
    setSelectedBarrierId((prev) => (prev === id ? null : prev))
  }

  function setPrediction(id: string, pred: PredictResponse): void {
    setPredictions((prev) => ({ ...prev, [id]: pred }))
  }

  function setEvidence(id: string, ev: ExplainResponse): void {
    setEvidenceMap((prev) => ({ ...prev, [id]: ev }))
  }

  function clearCascading(): void {
    setConditioningBarrierId(null)
    setSelectedTargetBarrierId(null)
  }

  return (
    <BowtieContext.Provider
      value={{
        // Legacy
        eventDescription,
        barriers,
        predictions,
        selectedBarrierId,
        evidence: evidenceMap,
        isAnalyzing,
        analysisError,
        pifFlags,
        viewMode,
        dashboardTab,
        analyticsTab,
        setEventDescription,
        addBarrier,
        addBarrierWithId,
        removeBarrier,
        updateBarrierRisk,
        updateBarrierCascading,
        setPrediction,
        setSelectedBarrierId,
        setEvidence,
        setIsAnalyzing,
        setAnalysisError,
        setPifFlags,
        togglePif,
        setViewMode,
        setDashboardTab,
        setAnalyticsTab,
        // Cascading
        scenario,
        conditioningBarrierId,
        selectedTargetBarrierId,
        cascadingPredictions,
        cascadingRanked,
        cascadingAnalysisState,
        explanation,
        explanationLoading,
        explanationError,
        narrativeUnavailable,
        setScenario,
        setConditioningBarrierId,
        setSelectedTargetBarrierId,
        clearCascading,
      }}
    >
      {children}
    </BowtieContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useBowtieContext(): BowtieState {
  const ctx = useContext(BowtieContext)
  if (!ctx) throw new Error('useBowtieContext must be used within BowtieProvider')
  return ctx
}
