'use client'

import { BowtieProvider, useBowtieContext } from '@/context/BowtieContext'
import BarrierForm from './sidebar/BarrierForm'
import BowtieSVG from './diagram/BowtieSVG'
import PathwayView from './diagram/PathwayView'
import DetailDrawer from './panel/DetailDrawer'
import DashboardView from './dashboard/DashboardView'
import ProvenanceStrip from './dashboard/ProvenanceStrip'

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

function BowtieAppInner() {
  const {
    barriers,
    predictions,
    eventDescription,
    setEventDescription,
    selectedBarrierId,
    setSelectedBarrierId,
    setSelectedTargetBarrierId,
    setConditioningBarrierId,
    isAnalyzing,
    viewMode,
    setViewMode,
    loadBSEEExample,
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
      <main className="flex-1 h-full overflow-hidden relative flex flex-col">
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

        <div className="flex-1 overflow-hidden">
          {viewMode === 'diagram' ? (
            <div className="h-full w-full bg-[#0F1419] flex flex-col">
              {!eventDescription && barriers.length === 0 ? (
                <div className="h-full w-full flex items-center justify-center">
                  <div className="w-[420px] rounded-lg border border-[#2A3442] bg-[#1C2430] p-8 flex flex-col gap-5">
                    <div>
                      <h2 className="text-base font-semibold text-[#E8E8E8] mb-1">
                        Define your bowtie scenario
                      </h2>
                      <p className="text-sm text-[#9CA3AF]">
                        Enter a Top Event below or load an example to begin.
                      </p>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="canvas-top-event" className="text-xs font-medium text-[#9CA3AF]">
                        Top Event
                      </label>
                      <input
                        id="canvas-top-event"
                        type="text"
                        value={eventDescription}
                        onChange={(e) => setEventDescription(e.target.value)}
                        placeholder="e.g. Loss of containment of hydrocarbons"
                        className="w-full rounded bg-[#0F1419] border border-[#2A3442] px-3 py-2 text-sm text-[#E8E8E8] placeholder-[#4B5563] focus:outline-none focus:border-[#2C5F7F]"
                      />
                    </div>
                    <button
                      onClick={loadBSEEExample}
                      className="w-full rounded px-4 py-2 text-sm font-medium bg-[#1C2430] border border-[#2A3442] text-[#9CA3AF] hover:text-[#E8E8E8] hover:border-[#4B6A82] transition-colors"
                    >
                      Load BSEE example
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  {barriers.length > 0 && barriers.every((b) => b.riskLevel === 'unanalyzed') && !isAnalyzing && (
                    <div
                      className="flex-shrink-0 flex justify-center pt-3 px-3"
                      data-testid="p2-analyze-banner"
                    >
                      <div className="rounded-md border border-[#2A3442] bg-[#1C2430] px-4 py-2 text-sm text-[#9CA3AF]">
                        Click <span className="text-[#E8E8E8] font-medium">Analyze Barriers</span> in the sidebar to see risk assessment
                      </div>
                    </div>
                  )}
                  <div className="flex-1 overflow-hidden p-3">
                    <BowtieSVG
                      topEvent={eventDescription}
                      hazardName="High-pressure gas"
                      threats={DEMO_THREATS}
                      consequences={DEMO_CONSEQUENCES}
                      barriers={svgBarriers}
                      selectedBarrierId={selectedBarrierId}
                      onBarrierClick={handleBarrierClick}
                    />
                  </div>
                </>
              )}
            </div>
          ) : (
            <PathwayView
              barriers={barriers}
              predictions={predictions}
              selectedBarrierId={selectedBarrierId}
              onBarrierClick={setSelectedBarrierId}
            />
          )}
        </div>
        <ProvenanceStrip />
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
