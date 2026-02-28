'use client'

import type { Barrier, PredictResponse, RiskLevel } from '@/lib/types'

// ---------------------------------------------------------------------------
// Risk level badge config (same as BarrierNode)
// ---------------------------------------------------------------------------

const RISK_LEVEL_LABELS: Record<string, string> = {
  red: 'High',
  amber: 'Medium',
  green: 'Low',
  unanalyzed: '',
}

const RISK_LEVEL_COLORS: Record<string, string> = {
  red: 'bg-red-500 text-white',
  amber: 'bg-amber-400 text-gray-900',
  green: 'bg-green-500 text-white',
  unanalyzed: 'bg-gray-200 text-gray-500',
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PathwayViewProps {
  barriers: Barrier[]
  predictions: Record<string, PredictResponse>
  selectedBarrierId: string | null
  onBarrierClick: (id: string) => void
}

// ---------------------------------------------------------------------------
// Barrier Card sub-component
// ---------------------------------------------------------------------------

function BarrierCard({
  barrier,
  prediction,
  isSelected,
  onClick,
}: {
  barrier: Barrier
  prediction?: PredictResponse
  isSelected: boolean
  onClick: () => void
}) {
  const riskLevel: RiskLevel = barrier.riskLevel
  const label = RISK_LEVEL_LABELS[riskLevel] ?? ''
  const badgeColor = RISK_LEVEL_COLORS[riskLevel] ?? RISK_LEVEL_COLORS.unanalyzed

  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left rounded-lg border p-3 transition-all duration-150 hover:shadow-md ${
        isSelected
          ? 'border-blue-400 ring-2 ring-blue-400 bg-blue-50'
          : 'border-gray-200 bg-white hover:bg-gray-50'
      }`}
    >
      <div className="flex items-center justify-between mb-1">
        <p className="text-sm font-semibold truncate pr-2">{barrier.name}</p>
        {label && (
          <span className={`text-xs font-bold px-2 py-0.5 rounded-full whitespace-nowrap ${badgeColor}`}>
            {label}
          </span>
        )}
      </div>
      <p className="text-xs text-gray-500 truncate">{barrier.barrierRole}</p>
      <p className="text-xs text-gray-400 mt-0.5">{barrier.line_of_defense} LoD</p>
    </button>
  )
}

// ---------------------------------------------------------------------------
// PathwayView Component
// ---------------------------------------------------------------------------

export default function PathwayView({
  barriers,
  predictions,
  selectedBarrierId,
  onBarrierClick,
}: PathwayViewProps) {
  const preventionBarriers = barriers.filter((b) => b.side === 'prevention')
  const mitigationBarriers = barriers.filter((b) => b.side === 'mitigation')

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="grid grid-cols-2 gap-6">
        {/* Prevention column */}
        <div>
          <h3 className="text-sm font-bold text-gray-700 uppercase tracking-wide mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-500" />
            Prevention Pathway
          </h3>
          <div className="space-y-2">
            {preventionBarriers.length > 0 ? (
              preventionBarriers.map((b) => (
                <BarrierCard
                  key={b.id}
                  barrier={b}
                  prediction={predictions[b.id]}
                  isSelected={b.id === selectedBarrierId}
                  onClick={() => onBarrierClick(b.id)}
                />
              ))
            ) : (
              <p className="text-xs text-gray-400 italic">No prevention barriers defined.</p>
            )}
          </div>
        </div>

        {/* Mitigation column */}
        <div>
          <h3 className="text-sm font-bold text-gray-700 uppercase tracking-wide mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-orange-500" />
            Mitigation Pathway
          </h3>
          <div className="space-y-2">
            {mitigationBarriers.length > 0 ? (
              mitigationBarriers.map((b) => (
                <BarrierCard
                  key={b.id}
                  barrier={b}
                  prediction={predictions[b.id]}
                  isSelected={b.id === selectedBarrierId}
                  onClick={() => onBarrierClick(b.id)}
                />
              ))
            ) : (
              <p className="text-xs text-gray-400 italic">No mitigation barriers defined.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
