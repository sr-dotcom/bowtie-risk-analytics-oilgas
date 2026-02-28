'use client'

import { useEffect } from 'react'
import { BowtieProvider, useBowtieContext } from '@/context/BowtieContext'
import BarrierForm from './sidebar/BarrierForm'
import BowtieFlow from './diagram/BowtieFlow'
import DetailPanel from './panel/DetailPanel'
import { DEMO_SCENARIO } from './sidebar/constants'

// ---------------------------------------------------------------------------
// Inner component — must be inside BowtieProvider to access context
// ---------------------------------------------------------------------------

function BowtieAppInner() {
  const { addBarrier, setEventDescription, barriers } = useBowtieContext()

  // Load demo scenario on first mount — only if no barriers exist yet
  useEffect(() => {
    if (barriers.length > 0) return
    setEventDescription(DEMO_SCENARIO.eventDescription)
    DEMO_SCENARIO.barriers.forEach((b) => addBarrier(b))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Empty deps — run once on mount only (D-03)

  return (
    <div className="flex h-screen min-w-[1280px] bg-gray-50">
      {/* Left panel: barrier input form */}
      <aside className="w-80 overflow-y-auto border-r border-gray-200 bg-white flex-shrink-0">
        <BarrierForm />
      </aside>

      {/* Center panel: Bowtie diagram */}
      <main className="flex-1 h-full overflow-hidden">
        <BowtieFlow />
      </main>

      {/* Right panel: barrier detail */}
      <aside className="w-96 overflow-y-auto border-l border-gray-200 bg-white p-4 flex-shrink-0">
        <DetailPanel />
      </aside>
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
