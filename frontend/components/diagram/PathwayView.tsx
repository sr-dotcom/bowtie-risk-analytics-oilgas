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
  unanalyzed: 'bg-[#242836] text-[#5A6178]',
}

const RISK_STRIPE_COLORS: Record<string, string> = {
  red: 'border-l-red-500',
  amber: 'border-l-amber-400',
  green: 'border-l-green-500',
  unanalyzed: 'border-l-[#2E3348]',
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

  const stripeColor = RISK_STRIPE_COLORS[riskLevel] ?? RISK_STRIPE_COLORS.unanalyzed

  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left rounded-lg border border-l-4 p-3 transition-all duration-150 hover:shadow-md ${stripeColor} ${
        isSelected
          ? 'border-blue-400 ring-2 ring-blue-400 bg-[#242836]'
          : 'border-[#2E3348] bg-[#1A1D27] hover:bg-[#242836]'
      }`}
    >
      <div className="flex items-center justify-between mb-1">
        <p className="text-sm font-semibold truncate pr-2 text-[#E8ECF4]">{barrier.name}</p>
        {label && (
          <span className={`text-xs font-bold px-2 py-0.5 rounded-full whitespace-nowrap ${badgeColor}`}>
            {label}
          </span>
        )}
      </div>
      <p className="text-xs text-[#8B93A8] truncate">{barrier.barrierRole}</p>
      <div className="flex gap-1.5 mt-1.5">
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#2E3348] text-[#5A6178]">
          {barrier.barrier_type}
        </span>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#2E3348] text-[#5A6178]">
          LOD {barrier.line_of_defense}
        </span>
      </div>
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
    <div className="h-full overflow-y-auto p-4 pt-14 bg-[#0F1117]">
      <div className="grid grid-cols-2 gap-6">
        {/* Prevention column */}
        <div>
          <h3 className="text-sm font-bold text-[#E8ECF4] uppercase tracking-wide mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#6366F1]" />
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
              <p className="text-xs text-[#5A6178] italic">No prevention barriers defined.</p>
            )}
          </div>
        </div>

        {/* Mitigation column */}
        <div>
          <h3 className="text-sm font-bold text-[#E8ECF4] uppercase tracking-wide mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#F97316]" />
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
              <p className="text-xs text-[#5A6178] italic">No mitigation barriers defined.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
