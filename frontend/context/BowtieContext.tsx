'use client'

import { createContext, useContext, useState, type ReactNode } from 'react'
import type { Barrier, ExplainResponse, PifFlags, PredictResponse, RiskLevel } from '@/lib/types'
import { DEFAULT_PIF_FLAGS } from '@/lib/types'

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

interface BowtieState {
  // State
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
  // Methods
  setEventDescription: (v: string) => void
  addBarrier: (b: Omit<Barrier, 'id' | 'riskLevel'>) => void
  removeBarrier: (id: string) => void
  updateBarrierRisk: (id: string, riskLevel: RiskLevel, probability: number) => void
  setPrediction: (id: string, pred: PredictResponse) => void
  setSelectedBarrierId: (id: string | null) => void
  setEvidence: (id: string, ev: ExplainResponse) => void
  setIsAnalyzing: (v: boolean) => void
  setAnalysisError: (v: string | null) => void
  setPifFlags: (flags: PifFlags) => void
  togglePif: (key: keyof PifFlags) => void
  setViewMode: (v: 'diagram' | 'pathway' | 'dashboard') => void
  setDashboardTab: (tab: string | null) => void
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
}: {
  children: ReactNode
  initialBarriers?: Barrier[]
  initialPredictions?: Record<string, PredictResponse>
  initialViewMode?: 'diagram' | 'pathway' | 'dashboard'
  initialDashboardTab?: string | null
}) {
  const [eventDescription, setEventDescription] = useState<string>('')
  const [barriers, setBarriers] = useState<Barrier[]>(initialBarriers)
  const [predictions, setPredictions] = useState<Record<string, PredictResponse>>(initialPredictions)
  const [selectedBarrierId, setSelectedBarrierId] = useState<string | null>(null)
  const [evidenceMap, setEvidenceMap] = useState<Record<string, ExplainResponse>>({})
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [pifFlags, setPifFlags] = useState<PifFlags>({ ...DEFAULT_PIF_FLAGS })
  const [viewMode, setViewMode] = useState<'diagram' | 'pathway' | 'dashboard'>(initialViewMode)
  const [dashboardTab, setDashboardTab] = useState<string | null>(initialDashboardTab)

  function togglePif(key: keyof PifFlags): void {
    setPifFlags((prev) => ({ ...prev, [key]: prev[key] === 1 ? 0 : 1 }))
  }

  function addBarrier(b: Omit<Barrier, 'id' | 'riskLevel'>): void {
    const newBarrier: Barrier = {
      ...b,
      id: crypto.randomUUID(),
      riskLevel: 'unanalyzed',
    }
    setBarriers((prev) => [...prev, newBarrier])
  }

  function updateBarrierRisk(id: string, riskLevel: RiskLevel, probability: number): void {
    setBarriers((prev) =>
      prev.map((b) => (b.id === id ? { ...b, riskLevel, probability } : b)),
    )
  }

  function removeBarrier(id: string): void {
    setBarriers((prev) => prev.filter((b) => b.id !== id))
    // Also remove cached prediction and evidence for this barrier
    setPredictions((prev) => {
      const next = { ...prev }
      delete next[id]
      return next
    })
    setEvidenceMap((prev) => {
      const next = { ...prev }
      delete next[id]
      return next
    })
    // Deselect if currently selected
    setSelectedBarrierId((prev) => (prev === id ? null : prev))
  }

  function setPrediction(id: string, pred: PredictResponse): void {
    setPredictions((prev) => ({ ...prev, [id]: pred }))
  }

  function setEvidence(id: string, ev: ExplainResponse): void {
    setEvidenceMap((prev) => ({ ...prev, [id]: ev }))
  }

  return (
    <BowtieContext.Provider
      value={{
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
        setEventDescription,
        addBarrier,
        removeBarrier,
        updateBarrierRisk,
        setPrediction,
        setSelectedBarrierId,
        setEvidence,
        setIsAnalyzing,
        setAnalysisError,
        setPifFlags,
        togglePif,
        setViewMode,
        setDashboardTab,
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
