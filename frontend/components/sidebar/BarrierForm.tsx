'use client'

import { useState, useEffect } from 'react'
import { Plus, Loader2, AlertCircle } from 'lucide-react'

import { useBowtieContext } from '@/context/BowtieContext'
import { useAnalyzeBarriers } from '@/hooks/useAnalyzeBarriers'
import type { PifFlags } from '@/lib/types'
import { PIF_DISPLAY_NAMES } from '@/lib/types'
import {
  BARRIER_TYPES,
  BARRIER_FAMILIES,
  LINE_OF_DEFENSE,
} from './constants'
import { formatBarrierFamily } from '@/lib/format'

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
    predictions,
    isAnalyzing,
    analysisError,
    setAnalysisError,
    setSelectedBarrierId,
    pifFlags,
    togglePif,
    loadBSEEExample,
  } = useBowtieContext()

  const { analyzeAll } = useAnalyzeBarriers()

  // --------------------------------------------------------------------------
  // Unified barrier form state
  // --------------------------------------------------------------------------
  const [side, setSide] = useState<'prevention' | 'mitigation'>('prevention')
  const [name, setName] = useState('')
  const [type, setType] = useState('')
  const [family, setFamily] = useState('')
  const [role, setRole] = useState('')
  const [lod, setLod] = useState('')

  // --------------------------------------------------------------------------
  // Error auto-dismiss
  // --------------------------------------------------------------------------
  useEffect(() => {
    if (!analysisError) return
    const timer = setTimeout(() => setAnalysisError(null), 5000)
    return () => clearTimeout(timer)
  }, [analysisError, setAnalysisError])

  // --------------------------------------------------------------------------
  // Add barrier
  // --------------------------------------------------------------------------
  function handleAddBarrier() {
    const trimmedName = name.trim()
    if (!trimmedName) return
    addBarrier({
      name: trimmedName,
      side,
      barrier_type: type || 'unknown',
      barrier_family: family || 'other_unknown',
      line_of_defense: lod || 'unknown',
      barrierRole: role.trim(),
    })
    setName('')
    setType('')
    setFamily('')
    setRole('')
    setLod('')
  }

  // --------------------------------------------------------------------------
  // Analyze barriers — delegate to shared hook
  // --------------------------------------------------------------------------
  async function handleAnalyze() {
    await analyzeAll()
  }

  // --------------------------------------------------------------------------
  // New Scenario — clear all state
  // --------------------------------------------------------------------------
  function handleNewScenario() {
    barriers.forEach((b) => removeBarrier(b.id))
    setEventDescription('')
    setSelectedBarrierId(null)
    setAnalysisError(null)
  }

  const canAnalyze = barriers.length > 0 && !isAnalyzing

  return (
    <div className="w-80 overflow-y-auto border-r border-[#2A3442] p-4 bg-[#151B24] h-full flex flex-col">

      {/* Event Description */}
      <div>
        <label className="block text-xs font-semibold text-[#9CA3AF] uppercase tracking-wide mb-1">
          Top Event
        </label>
        <textarea
          value={eventDescription}
          onChange={(e) => setEventDescription(e.target.value)}
          placeholder="e.g., Loss of containment of hazardous material"
          className="w-full rounded-md border border-[#2A3442] bg-[#151B24] text-[#E8E8E8] placeholder:text-[#6B7280] p-2 text-sm resize-none h-20 focus:ring-2 focus:ring-[#2C5F7F] focus:border-transparent outline-none"
        />
        <button
          onClick={loadBSEEExample}
          className="mt-1.5 w-full rounded-md border border-[#2A3442] text-[#6B7280] py-1.5 text-xs hover:text-[#9CA3AF] hover:border-[#4B6A82] transition-colors"
        >
          Load BSEE example
        </button>
      </div>

      {/* Unified Add Barrier form */}
      <div className="mt-4">
        <h3 className="text-sm font-semibold text-[#E8E8E8] mb-2">Add Barrier</h3>

        {/* Side toggle */}
        <div className="flex rounded-lg overflow-hidden border border-[#2A3442] mb-3">
          <button
            onClick={() => setSide('prevention')}
            className={`flex-1 px-3 py-1.5 text-xs font-medium transition-colors ${
              side === 'prevention'
                ? 'bg-[#1F4A66] text-[#E8E8E8]'
                : 'bg-[#151B24] text-[#6B7280] hover:text-[#9CA3AF]'
            }`}
          >
            Prevention
          </button>
          <button
            onClick={() => setSide('mitigation')}
            className={`flex-1 px-3 py-1.5 text-xs font-medium transition-colors ${
              side === 'mitigation'
                ? 'bg-[#1F4A66] text-[#E8E8E8]'
                : 'bg-[#151B24] text-[#6B7280] hover:text-[#9CA3AF]'
            }`}
          >
            Mitigation
          </button>
        </div>

        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAddBarrier()}
          placeholder="e.g., Pressure Safety Valve"
          className="w-full rounded-md border border-[#2A3442] bg-[#151B24] text-[#E8E8E8] placeholder:text-[#6B7280] p-2 text-sm mb-2 focus:ring-2 focus:ring-[#2C5F7F] focus:border-transparent outline-none"
        />

        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="w-full rounded-md border border-[#2A3442] bg-[#151B24] text-[#E8E8E8] p-2 text-sm mb-2 focus:ring-2 focus:ring-[#2C5F7F] focus:border-transparent outline-none"
        >
          <option value="">Select type...</option>
          {BARRIER_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>

        <select
          value={family}
          onChange={(e) => setFamily(e.target.value)}
          className="w-full rounded-md border border-[#2A3442] bg-[#151B24] text-[#E8E8E8] p-2 text-sm mb-2 focus:ring-2 focus:ring-[#2C5F7F] focus:border-transparent outline-none"
        >
          <option value="">Select family...</option>
          {BARRIER_FAMILIES.map((f) => (
            <option key={f} value={f}>{formatBarrierFamily(f)}</option>
          ))}
        </select>

        <input
          type="text"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          placeholder="Barrier role description"
          className="w-full rounded-md border border-[#2A3442] bg-[#151B24] text-[#E8E8E8] placeholder:text-[#6B7280] p-2 text-sm mb-2 focus:ring-2 focus:ring-[#2C5F7F] focus:border-transparent outline-none"
        />

        <select
          value={lod}
          onChange={(e) => setLod(e.target.value)}
          className="w-full rounded-md border border-[#2A3442] bg-[#151B24] text-[#E8E8E8] p-2 text-sm mb-2 focus:ring-2 focus:ring-[#2C5F7F] focus:border-transparent outline-none"
        >
          <option value="">Select LOD...</option>
          {LINE_OF_DEFENSE.map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>

        <button
          onClick={handleAddBarrier}
          className="w-full rounded-md bg-[#151B24] text-[#E8E8E8] border border-[#2A3442] py-2 text-sm font-medium hover:bg-[#2A3442] active:bg-[#3A3F52] flex items-center justify-center gap-1.5"
        >
          <Plus size={14} />
          Add {side === 'prevention' ? 'Prevention' : 'Mitigation'} Barrier
        </button>
      </div>

      {/* Barrier List */}
      {barriers.length > 0 ? (
        <div className="mt-4">
          <h3 className="text-base font-semibold mb-1 text-[#E8E8E8]">Barriers</h3>
          <div className="space-y-0.5">
            {barriers.map((b) => (
              <div
                key={b.id}
                className="group flex items-start gap-2 py-1.5 px-2 rounded hover:bg-[#151B24] cursor-pointer transition-colors"
                onClick={() => setSelectedBarrierId(b.id)}
              >
                {/* Risk dot */}
                <span
                  className="mt-1 w-2 h-2 rounded-full flex-shrink-0"
                  style={{
                    backgroundColor:
                      b.riskLevel === 'red'   ? '#C0392B'
                      : b.riskLevel === 'amber' ? '#996515'
                      : b.riskLevel === 'green' ? '#1F6F43'
                      : '#6B7280'
                  }}
                />

                {/* Barrier name — allow wrapping */}
                <span className="text-xs text-[#E8E8E8] leading-tight flex-1">
                  {b.name}
                </span>

                {/* Side indicator */}
                <span className="text-[10px] text-[#6B7280] flex-shrink-0 mt-0.5">
                  {b.side === 'prevention' ? 'P' : 'M'}
                </span>

                {/* Delete — hover only */}
                <button
                  className="opacity-0 group-hover:opacity-100 text-[#6B7280] hover:text-[#E74C3C] transition-opacity flex-shrink-0"
                  onClick={(e) => { e.stopPropagation(); removeBarrier(b.id) }}
                  title="Remove barrier"
                  aria-label="Remove barrier"
                >
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <path d="M9 3L3 9M3 3l6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="mt-4 text-center py-6">
          <p className="text-sm text-[#6B7280] font-medium">No barriers added yet</p>
          <p className="text-xs text-[#6B7280] mt-1">
            Add prevention barriers on the left to build your Bowtie diagram.
          </p>
        </div>
      )}

      {/* Human Factors (PIFs) */}
      <div className="mt-4">
        <h3 className="text-base font-semibold mb-1 text-[#E8E8E8]">Human Factors</h3>
        <p className="text-xs text-[#6B7280] mb-2">Check factors relevant to this scenario</p>
        <div className="space-y-0.5 max-h-48 overflow-y-auto">
          {(Object.keys(PIF_DISPLAY_NAMES) as (keyof PifFlags)[]).map((key) => (
            <label
              key={key}
              className="flex items-center gap-2 py-1 px-2 rounded text-sm hover:bg-[#151B24] cursor-pointer select-none"
            >
              <input
                type="checkbox"
                checked={pifFlags[key] === 1}
                onChange={() => togglePif(key)}
                className="rounded border-[#2A3442] bg-[#151B24] text-[#2C5F7F] focus:ring-[#2C5F7F] h-3.5 w-3.5"
              />
              <span className="text-[#E8E8E8]">{PIF_DISPLAY_NAMES[key]}</span>
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
            className="w-full rounded-md bg-[#2C5F7F] text-[#E8E8E8] py-2.5 text-sm font-medium hover:bg-[#3A7399] active:bg-[#1F4A66] flex items-center justify-center gap-2"
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
            className="w-full rounded-md bg-[#2C5F7F] text-[#E8E8E8] py-2.5 text-sm font-medium flex items-center justify-center gap-2 cursor-not-allowed opacity-75"
          >
            <Loader2 size={14} className="animate-spin" />
            Analyzing barriers...
          </button>
        ) : (
          <button
            disabled
            className="w-full rounded-md bg-[#151B24] text-[#6B7280] py-2.5 text-sm font-medium cursor-not-allowed"
            title="Add at least one barrier to analyze."
          >
            Analyze Barriers
          </button>
        )}

        {/* New Scenario button */}
        <button
          onClick={handleNewScenario}
          className="w-full rounded-md border border-[#2A3442] text-[#9CA3AF] py-2 text-sm hover:bg-[#1C2430]"
        >
          New Scenario
        </button>
      </div>

      {/* Error toast — fixed bottom-right per UI-SPEC Interaction States */}
      {analysisError && (
        <div
          className="fixed bottom-4 right-4 rounded-md p-3 text-sm shadow z-50"
          style={{ backgroundColor: '#151B24', borderLeft: '3px solid #C0392B', color: '#E8E8E8' }}
        >
          <div className="flex items-center gap-2">
            <AlertCircle size={16} />
            <span>{analysisError}</span>
          </div>
        </div>
      )}
    </div>
  )
}
