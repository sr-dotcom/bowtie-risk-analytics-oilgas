'use client'

import { Handle, Position } from '@xyflow/react'
import type { NodeProps, Node } from '@xyflow/react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type BarrierNodeData = {
  label: string
  riskLevel: 'red' | 'amber' | 'green' | 'unanalyzed'
  probability?: number
  barrierId: string
  selected?: boolean
}

export type BarrierNodeType = Node<BarrierNodeData, 'barrier'>

// ---------------------------------------------------------------------------
// H/M/L label mapping for badge text (D-07, Fidel-#34)
// ---------------------------------------------------------------------------

const RISK_LEVEL_LABELS: Record<string, string> = {
  red: 'High',
  amber: 'Medium',
  green: 'Low',
  unanalyzed: '',
}

// ---------------------------------------------------------------------------
// Risk ring color classes per UI-SPEC Color section
// ---------------------------------------------------------------------------

const riskRing: Record<string, string> = {
  red: 'ring-2 ring-red-500',
  amber: 'ring-2 ring-amber-400',
  green: 'ring-2 ring-green-500',
  unanalyzed: 'ring-1 ring-gray-300',
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function BarrierNode({ data }: NodeProps<BarrierNodeType>) {
  const ringClass = data.selected
    ? 'ring-4 ring-blue-400'
    : (riskRing[data.riskLevel] ?? riskRing.unanalyzed)

  return (
    <div
      className={`rounded-md bg-white p-3 shadow ${ringClass} w-[160px] cursor-pointer nodrag hover:shadow-md hover:scale-[1.02] transition-all duration-150`}
    >
      {/* Barrier name */}
      <p className="text-sm font-semibold truncate">{data.label}</p>

      {/* Risk level badge — shows H/M/L after analysis */}
      {data.riskLevel && data.riskLevel !== 'unanalyzed' ? (
        <p className="text-xs text-gray-500 font-medium">
          {RISK_LEVEL_LABELS[data.riskLevel] ?? ''}
        </p>
      ) : (
        /* Loading placeholder area — pulses during analysis (handled by isAnalyzing in BowtieFlow) */
        <p className="text-xs text-transparent select-none">--</p>
      )}

      {/* React Flow handles */}
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
    </div>
  )
}
