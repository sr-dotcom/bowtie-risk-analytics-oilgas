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
}

const BowtieContext = createContext<BowtieState | null>(null)

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function BowtieProvider({ children }: { children: ReactNode }) {
  const [eventDescription, setEventDescription] = useState<string>('')
  const [barriers, setBarriers] = useState<Barrier[]>([])
  const [predictions, setPredictions] = useState<Record<string, PredictResponse>>({})
  const [selectedBarrierId, setSelectedBarrierId] = useState<string | null>(null)
  const [evidenceMap, setEvidenceMap] = useState<Record<string, ExplainResponse>>({})
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [pifFlags, setPifFlags] = useState<PifFlags>({ ...DEFAULT_PIF_FLAGS })

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
