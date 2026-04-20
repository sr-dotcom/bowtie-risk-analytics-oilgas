'use client'

import { useEffect, useRef } from 'react'
import { BowtieProvider, useBowtieContext } from '@/context/BowtieContext'
import BarrierForm from './sidebar/BarrierForm'
import BowtieSVG from './diagram/BowtieSVG'
import PathwayView from './diagram/PathwayView'
import DetailDrawer from './panel/DetailDrawer'
import { BSEE_DEMO_SCENARIO } from './sidebar/constants'
import type { ScenarioBarrier } from '@/lib/types'
import DashboardView from './dashboard/DashboardView'

// ---------------------------------------------------------------------------
// Demo threats and consequences (hardcoded — will be user-enterable later)
// ---------------------------------------------------------------------------

const DEMO_THREATS = [
  { id: 't1', name: 'Equipment overpressure', contribution: 'high' as const },
  { id: 't2', name: 'Overheating of equipment', contribution: 'medium' as const },
  { id: 't3', name: 'Operator error during transfer', contribution: 'low' as const },
]

const DEMO_CONSEQUENCES = [
  { id: 'c1', name: 'Gas release / toxic exposure' },
  { id: 'c2', name: 'Explosive failure of equipment' },
  { id: 'c3', name: 'Fire / explosion' },
]

// Map context riskLevel to BowtieSVG risk_level
function mapRiskLevel(rl: string): 'Low' | 'Medium' | 'High' | null {
  switch (rl) {
    case 'green': return 'Low'
    case 'amber': return 'Medium'
    case 'red': return 'High'
    default: return null
  }
}

// ---------------------------------------------------------------------------
// Inner component — must be inside BowtieProvider to access context
// ---------------------------------------------------------------------------

// Map a ScenarioBarrier to the Barrier shape expected by addBarrierWithId.
// barrier_family is unused in the cascading flow but is required by the Barrier type.
function scenarioBarrierToBarrier(sb: ScenarioBarrier): Parameters<ReturnType<typeof useBowtieContext>['addBarrierWithId']>[0] {
  return {
    id: sb.control_id,
    name: sb.name,
    side: sb.barrier_level === 'prevention' ? 'prevention' : 'mitigation',
    barrier_type: sb.barrier_type,
    barrier_family: 'other_unknown',
    line_of_defense: sb.line_of_defense ?? '1st',
    barrierRole: sb.barrier_role,
  }
}

function BowtieAppInner() {
  const {
    addBarrierWithId,
    setEventDescription,
    setScenario,
    barriers,
    predictions,
    eventDescription,
    selectedBarrierId,
    setSelectedBarrierId,
    setSelectedTargetBarrierId,
    setConditioningBarrierId,
    isAnalyzing,
    viewMode,
    setViewMode,
  } = useBowtieContext()

  function handleBarrierClick(barrierId: string) {
    setSelectedBarrierId(barrierId)
    setSelectedTargetBarrierId(barrierId)

    // Pick conditioner: highest avg cascading risk among other barriers;
    // fall back to first non-clicked barrier if analysis hasn't run yet.
    const analyzed = barriers
      .filter((b) => b.id !== barrierId && b.average_cascading_probability !== undefined)
      .sort((a, b) => (b.average_cascading_probability ?? 0) - (a.average_cascading_probability ?? 0))

    const conditioner = analyzed[0] ?? barriers.find((b) => b.id !== barrierId) ?? null
    if (conditioner) setConditioningBarrierId(conditioner.id)
  }

  // Load demo scenario on first mount.
  // Ref guard prevents React 18 StrictMode double-invocation from adding duplicates.
  const demoLoaded = useRef(false)
  useEffect(() => {
    if (demoLoaded.current || barriers.length > 0) return
    demoLoaded.current = true
    setEventDescription(BSEE_DEMO_SCENARIO.top_event)
    BSEE_DEMO_SCENARIO.barriers.forEach((sb) => addBarrierWithId(scenarioBarrierToBarrier(sb)))
    setScenario(BSEE_DEMO_SCENARIO)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Map barriers from context format to BowtieSVG format
  const prevOnly = barriers.filter((x) => x.side === 'prevention')
  const mitOnly = barriers.filter((x) => x.side === 'mitigation')
  const svgBarriers = barriers.map((b) => {
    // Assign prevention barriers to threats round-robin
    const prevIdx = prevOnly.indexOf(b)
    let threatId: string | undefined
    if (b.side === 'prevention' && prevIdx >= 0 && DEMO_THREATS.length > 0) {
      threatId = DEMO_THREATS[prevIdx % DEMO_THREATS.length].id
    }

    // Assign mitigation barriers to consequences round-robin
    const mitIdx = mitOnly.indexOf(b)
    let consequenceId: string | undefined
    if (b.side === 'mitigation' && mitIdx >= 0 && DEMO_CONSEQUENCES.length > 0) {
      consequenceId = DEMO_CONSEQUENCES[mitIdx % DEMO_CONSEQUENCES.length].id
    }

    return {
      id: b.id,
      name: b.name,
      side: b.side,
      barrier_type: b.barrier_type,
      barrier_role: b.barrierRole,
      line_of_defense: b.line_of_defense,
      risk_level: mapRiskLevel(b.riskLevel),
      top_reasons: b.top_reasons,
      average_cascading_probability: b.average_cascading_probability,
      threatId,
      consequenceId,
    }
  })

  if (viewMode === 'dashboard') {
    return (
      <div className="flex h-screen min-w-[1280px] bg-[#0F1419] flex-col">
        {/* Toggle bar */}
        <div className="flex-shrink-0 flex items-center px-4 py-2 border-b border-[#2A3442] bg-[#151B24]">
          <div className="flex rounded-lg overflow-hidden border border-[#2A3442] bg-[#151B24]">
            <button
              onClick={() => setViewMode('diagram')}
              className="px-3 py-1 text-xs font-medium transition-colors text-[#9CA3AF] hover:text-[#E8E8E8]"
            >
              Diagram View
            </button>
            <button
              onClick={() => setViewMode('pathway')}
              className="px-3 py-1 text-xs font-medium transition-colors text-[#9CA3AF] hover:text-[#E8E8E8]"
            >
              Pathway View
            </button>
            <button
              className="px-3 py-1 text-xs font-medium transition-colors bg-[#2C5F7F] text-[#E8E8E8]"
            >
              Analytics
            </button>
          </div>
        </div>
        {/* Dashboard content */}
        <div className="flex-1 overflow-auto">
          <DashboardView />
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen min-w-[1280px] bg-[#0F1419]">
      {/* Left panel: barrier input form */}
      <aside className="w-80 overflow-y-auto border-r border-[#2A3442] bg-[#151B24] flex-shrink-0">
        <BarrierForm />
      </aside>

      {/* Center panel: Bowtie diagram or pathway view */}
      <main className="flex-1 h-full overflow-hidden relative">
        {/* View toggle */}
        <div className="absolute top-3 right-3 z-20 flex rounded-lg overflow-hidden border border-[#2A3442] bg-[#151B24]">
          <button
            onClick={() => setViewMode('diagram')}
            className={`px-3 py-1 text-xs font-medium transition-colors ${
              viewMode === 'diagram'
                ? 'bg-[#2C5F7F] text-[#E8E8E8]'
                : 'text-[#9CA3AF] hover:text-[#E8E8E8]'
            }`}
          >
            Diagram View
          </button>
          <button
            onClick={() => setViewMode('pathway')}
            className={`px-3 py-1 text-xs font-medium transition-colors ${
              viewMode === 'pathway'
                ? 'bg-[#2C5F7F] text-[#E8E8E8]'
                : 'text-[#9CA3AF] hover:text-[#E8E8E8]'
            }`}
          >
            Pathway View
          </button>
          <button
            onClick={() => setViewMode('dashboard')}
            className="px-3 py-1 text-xs font-medium transition-colors text-[#9CA3AF] hover:text-[#E8E8E8]"
          >
            Analytics
          </button>
        </div>

        {/* Analyzing overlay */}
        {isAnalyzing && (
          <div className="absolute inset-0 z-10 pointer-events-none flex items-end justify-center pb-4">
            <span className="bg-[#151B24] border border-[#2A3442] rounded-md px-3 py-1.5 text-xs text-[#9CA3AF] shadow-lg animate-pulse">
              Analyzing barriers...
            </span>
          </div>
        )}

        {viewMode === 'diagram' ? (
          <BowtieSVG
            topEvent={eventDescription}
            hazardName="High-pressure gas"
            threats={DEMO_THREATS}
            consequences={DEMO_CONSEQUENCES}
            barriers={svgBarriers}
            selectedBarrierId={selectedBarrierId}
            onBarrierClick={handleBarrierClick}
          />
        ) : (
          <PathwayView
            barriers={barriers}
            predictions={predictions}
            selectedBarrierId={selectedBarrierId}
            onBarrierClick={setSelectedBarrierId}
          />
        )}
      </main>

      <DetailDrawer />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Root client component — owns BowtieProvider context boundary
// ---------------------------------------------------------------------------

export default function BowtieApp() {
  return (
    <BowtieProvider>
      <BowtieAppInner />
    </BowtieProvider>
  )
}
