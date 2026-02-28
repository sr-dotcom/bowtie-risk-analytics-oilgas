'use client'

import { useState, useEffect } from 'react'
import { Plus, Trash2, Loader2, AlertCircle } from 'lucide-react'

import { useBowtieContext } from '@/context/BowtieContext'
import { predict } from '@/lib/api'
import { mapProbabilityToRiskLevel } from '@/lib/riskScore'
import type { PredictRequest, RiskThresholds, PifFlags } from '@/lib/types'
import { PIF_DISPLAY_NAMES } from '@/lib/types'
import {
  BARRIER_TYPES,
  BARRIER_FAMILIES,
  LINE_OF_DEFENSE,
  SOURCE_AGENCY_DEFAULT,
} from './constants'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function BarrierForm() {
  const {
    eventDescription,
    setEventDescription,
    barriers,
    addBarrier,
    removeBarrier,
    updateBarrierRisk,
    predictions,
    setPrediction,
    isAnalyzing,
    setIsAnalyzing,
    analysisError,
    setAnalysisError,
    setSelectedBarrierId,
    pifFlags,
    togglePif,
  } = useBowtieContext()

  // --------------------------------------------------------------------------
  // Prevention barrier form state
  // --------------------------------------------------------------------------
  const [prevName, setPrevName] = useState('')
  const [prevType, setPrevType] = useState('')
  const [prevFamily, setPrevFamily] = useState('')
  const [prevRole, setPrevRole] = useState('')
  const [prevLod, setPrevLod] = useState('')

  // --------------------------------------------------------------------------
  // Mitigation barrier form state
  // --------------------------------------------------------------------------
  const [mitName, setMitName] = useState('')
  const [mitType, setMitType] = useState('')
  const [mitFamily, setMitFamily] = useState('')
  const [mitRole, setMitRole] = useState('')
  const [mitLod, setMitLod] = useState('')

  // --------------------------------------------------------------------------
  // Error auto-dismiss
  // --------------------------------------------------------------------------
  useEffect(() => {
    if (!analysisError) return
    const timer = setTimeout(() => setAnalysisError(null), 5000)
    return () => clearTimeout(timer)
  }, [analysisError, setAnalysisError])

  // --------------------------------------------------------------------------
  // Add prevention barrier
  // --------------------------------------------------------------------------
  function handleAddPrevention() {
    const name = prevName.trim()
    if (!name) return
    addBarrier({
      name,
      side: 'prevention',
      barrier_type: prevType || 'unknown',
      barrier_family: prevFamily || 'other_unknown',
      line_of_defense: prevLod || 'unknown',
      barrierRole: prevRole.trim(),
    })
    setPrevName('')
    setPrevType('')
    setPrevFamily('')
    setPrevRole('')
    setPrevLod('')
  }

  // --------------------------------------------------------------------------
  // Add mitigation barrier
  // --------------------------------------------------------------------------
  function handleAddMitigation() {
    const name = mitName.trim()
    if (!name) return
    addBarrier({
      name,
      side: 'mitigation',
      barrier_type: mitType || 'unknown',
      barrier_family: mitFamily || 'other_unknown',
      line_of_defense: mitLod || 'unknown',
      barrierRole: mitRole.trim(),
    })
    setMitName('')
    setMitType('')
    setMitFamily('')
    setMitRole('')
    setMitLod('')
  }

  // --------------------------------------------------------------------------
  // Analyze barriers — call /predict for all prevention barriers in parallel
  // --------------------------------------------------------------------------
  async function handleAnalyze() {
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
          // PIFs from context pifFlags state (Bug #2 fix)
          pif_competence: pifFlags.pif_competence,
          pif_fatigue: pifFlags.pif_fatigue,
          pif_communication: pifFlags.pif_communication,
          pif_situational_awareness: pifFlags.pif_situational_awareness,
          pif_procedures: pifFlags.pif_procedures,
          pif_workload: pifFlags.pif_workload,
          pif_time_pressure: pifFlags.pif_time_pressure,
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

  // --------------------------------------------------------------------------
  // New Scenario — clear all state
  // --------------------------------------------------------------------------
  function handleNewScenario() {
    // Remove all barriers
    barriers.forEach((b) => removeBarrier(b.id))
    setEventDescription('')
    setSelectedBarrierId(null)
    setAnalysisError(null)
  }

  const canAnalyze = barriers.length > 0 && !isAnalyzing

  return (
    <div className="w-80 overflow-y-auto border-r border-gray-200 p-4 bg-white h-full flex flex-col">

      {/* Event Description */}
      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
          Top Event
        </label>
        <textarea
          value={eventDescription}
          onChange={(e) => setEventDescription(e.target.value)}
          placeholder="Describe the top event (e.g., Loss of containment)"
          className="w-full rounded-md border border-gray-300 p-2 text-sm resize-none h-20 focus:ring-2 focus:ring-blue-400 focus:border-transparent outline-none"
        />
      </div>

      {/* Add Prevention Barrier */}
      <div className="mt-4">
        <h3 className="text-base font-semibold mb-2">Add Prevention Barrier</h3>

        <input
          type="text"
          value={prevName}
          onChange={(e) => setPrevName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAddPrevention()}
          placeholder="Barrier name"
          className="w-full rounded-md border border-gray-300 p-2 text-sm mb-2 focus:ring-2 focus:ring-blue-400 focus:border-transparent outline-none"
        />

        <select
          value={prevType}
          onChange={(e) => setPrevType(e.target.value)}
          className="w-full rounded-md border border-gray-300 p-2 text-sm mb-2 bg-white focus:ring-2 focus:ring-blue-400 focus:border-transparent outline-none"
        >
          <option value="">Select type...</option>
          {BARRIER_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        <select
          value={prevFamily}
          onChange={(e) => setPrevFamily(e.target.value)}
          className="w-full rounded-md border border-gray-300 p-2 text-sm mb-2 bg-white focus:ring-2 focus:ring-blue-400 focus:border-transparent outline-none"
        >
          <option value="">Select family...</option>
          {BARRIER_FAMILIES.map((f) => (
            <option key={f} value={f}>
              {f.replace(/_/g, ' ')}
            </option>
          ))}
        </select>

        <input
          type="text"
          value={prevRole}
          onChange={(e) => setPrevRole(e.target.value)}
          placeholder="Barrier role description"
          className="w-full rounded-md border border-gray-300 p-2 text-sm mb-2 focus:ring-2 focus:ring-blue-400 focus:border-transparent outline-none"
        />

        <select
          value={prevLod}
          onChange={(e) => setPrevLod(e.target.value)}
          className="w-full rounded-md border border-gray-300 p-2 text-sm mb-2 bg-white focus:ring-2 focus:ring-blue-400 focus:border-transparent outline-none"
        >
          <option value="">Select LOD...</option>
          {LINE_OF_DEFENSE.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>

        <button
          onClick={handleAddPrevention}
          className="w-full rounded-md bg-gray-100 text-gray-700 py-2 text-sm font-medium hover:bg-gray-200 active:bg-gray-300 flex items-center justify-center gap-1.5"
        >
          <Plus size={14} />
          Add Prevention Barrier
        </button>
      </div>

      {/* Add Mitigation Barrier */}
      <div className="mt-4">
        <h3 className="text-base font-semibold mb-2">Add Mitigation Barrier</h3>

        <input
          type="text"
          value={mitName}
          onChange={(e) => setMitName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAddMitigation()}
          placeholder="Barrier name"
          className="w-full rounded-md border border-gray-300 p-2 text-sm mb-2 focus:ring-2 focus:ring-blue-400 focus:border-transparent outline-none"
        />

        <select
          value={mitType}
          onChange={(e) => setMitType(e.target.value)}
          className="w-full rounded-md border border-gray-300 p-2 text-sm mb-2 bg-white focus:ring-2 focus:ring-blue-400 focus:border-transparent outline-none"
        >
          <option value="">Select type...</option>
          {BARRIER_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        <select
          value={mitFamily}
          onChange={(e) => setMitFamily(e.target.value)}
          className="w-full rounded-md border border-gray-300 p-2 text-sm mb-2 bg-white focus:ring-2 focus:ring-blue-400 focus:border-transparent outline-none"
        >
          <option value="">Select family...</option>
          {BARRIER_FAMILIES.map((f) => (
            <option key={f} value={f}>
              {f.replace(/_/g, ' ')}
            </option>
          ))}
        </select>

        <input
          type="text"
          value={mitRole}
          onChange={(e) => setMitRole(e.target.value)}
          placeholder="Barrier role description"
          className="w-full rounded-md border border-gray-300 p-2 text-sm mb-2 focus:ring-2 focus:ring-blue-400 focus:border-transparent outline-none"
        />

        <select
          value={mitLod}
          onChange={(e) => setMitLod(e.target.value)}
          className="w-full rounded-md border border-gray-300 p-2 text-sm mb-2 bg-white focus:ring-2 focus:ring-blue-400 focus:border-transparent outline-none"
        >
          <option value="">Select LOD...</option>
          {LINE_OF_DEFENSE.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>

        <button
          onClick={handleAddMitigation}
          className="w-full rounded-md bg-gray-100 text-gray-700 py-2 text-sm font-medium hover:bg-gray-200 active:bg-gray-300 flex items-center justify-center gap-1.5"
        >
          <Plus size={14} />
          Add Mitigation Barrier
        </button>
      </div>

      {/* Barrier List */}
      {barriers.length > 0 ? (
        <div className="mt-4">
          <h3 className="text-base font-semibold mb-1">Barriers</h3>
          <div className="space-y-0.5">
            {barriers.map((b) => {
              const pred = predictions[b.id]
              return (
                <div
                  key={b.id}
                  className="flex items-center justify-between py-1.5 px-2 rounded text-sm hover:bg-gray-50"
                >
                  <span className="truncate flex-1">{b.name}</span>
                  <span className="text-xs text-gray-400 mr-2">
                    {b.side === 'prevention' ? 'L' : 'R'}
                  </span>
                  {b.riskLevel && b.riskLevel !== 'unanalyzed' && (
                    <span className={`text-xs font-medium mr-2 ${
                      b.riskLevel === 'red' ? 'text-red-500' :
                      b.riskLevel === 'amber' ? 'text-amber-500' :
                      'text-green-500'
                    }`}>
                      {b.riskLevel === 'red' ? 'High' : b.riskLevel === 'amber' ? 'Medium' : 'Low'}
                    </span>
                  )}
                  <button
                    onClick={() => removeBarrier(b.id)}
                    className="text-gray-400 hover:text-red-500 transition-colors"
                    title="Remove barrier"
                    aria-label="Remove barrier"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      ) : (
        <div className="mt-4 text-center py-6">
          <p className="text-sm text-gray-400 font-medium">No barriers added yet</p>
          <p className="text-xs text-gray-400 mt-1">
            Add prevention barriers on the left to build your Bowtie diagram.
          </p>
        </div>
      )}

      {/* Human Factors (PIFs) */}
      <div className="mt-4">
        <h3 className="text-base font-semibold mb-1">Human Factors</h3>
        <p className="text-xs text-gray-400 mb-2">Check factors relevant to this scenario</p>
        <div className="space-y-0.5 max-h-48 overflow-y-auto">
          {(Object.keys(PIF_DISPLAY_NAMES) as (keyof PifFlags)[]).map((key) => (
            <label
              key={key}
              className="flex items-center gap-2 py-1 px-2 rounded text-sm hover:bg-gray-50 cursor-pointer select-none"
            >
              <input
                type="checkbox"
                checked={pifFlags[key] === 1}
                onChange={() => togglePif(key)}
                className="rounded border-gray-300 text-blue-500 focus:ring-blue-400 h-3.5 w-3.5"
              />
              <span className="text-gray-700">{PIF_DISPLAY_NAMES[key]}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Spacer to push buttons to bottom */}
      <div className="flex-1" />

      {/* Analyze Barriers button */}
      <div className="mt-4 space-y-2">
        {canAnalyze ? (
          <button
            onClick={handleAnalyze}
            className="w-full rounded-md bg-blue-500 text-white py-2.5 text-sm font-medium hover:bg-blue-600 active:bg-blue-700 flex items-center justify-center gap-2"
          >
            {isAnalyzing ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Analyzing barriers...
              </>
            ) : (
              'Analyze Barriers'
            )}
          </button>
        ) : isAnalyzing ? (
          <button
            disabled
            className="w-full rounded-md bg-blue-400 text-white py-2.5 text-sm font-medium flex items-center justify-center gap-2 cursor-not-allowed opacity-75"
          >
            <Loader2 size={14} className="animate-spin" />
            Analyzing barriers...
          </button>
        ) : (
          <button
            disabled
            className="w-full rounded-md bg-gray-300 text-gray-400 py-2.5 text-sm font-medium cursor-not-allowed"
            title="Add at least one barrier to analyze."
          >
            Analyze Barriers
          </button>
        )}

        {/* New Scenario button */}
        <button
          onClick={handleNewScenario}
          className="w-full rounded-md border border-gray-300 text-gray-600 py-2 text-sm hover:bg-gray-50"
        >
          New Scenario
        </button>
      </div>

      {/* Error toast — fixed bottom-right per UI-SPEC Interaction States */}
      {analysisError && (
        <div className="fixed bottom-4 right-4 bg-red-50 border border-red-200 rounded-md p-3 text-sm text-red-700 shadow z-50">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} />
            <span>{analysisError}</span>
          </div>
        </div>
      )}
    </div>
  )
}
