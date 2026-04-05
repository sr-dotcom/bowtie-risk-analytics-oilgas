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
// Risk color hex values for dark-themed nodes
// ---------------------------------------------------------------------------

const RISK_COLORS: Record<string, string> = {
  red: '#EF4444',
  amber: '#F59E0B',
  green: '#22C55E',
  unanalyzed: '#2E3348',
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const HIDDEN_HANDLE = { opacity: 0, width: 1, height: 1 } as const

export default function BarrierNode({ data }: NodeProps<BarrierNodeType>) {
  const analyzed = data.riskLevel && data.riskLevel !== 'unanalyzed'
  const riskColor = RISK_COLORS[data.riskLevel] ?? RISK_COLORS.unanalyzed

  const leftColor = data.selected ? '#3B82F6' : riskColor

  return (
    <div
      className="cursor-pointer nodrag hover:brightness-125 transition-all duration-150"
      style={{
        backgroundColor: '#1A1D27',
        borderLeft: `2px solid ${leftColor}`,
        borderTop: '1px solid #2E3348',
        borderRight: '1px solid #2E3348',
        borderBottom: '1px solid #2E3348',
        borderRadius: 2,
        padding: '4px 8px',
        minWidth: 120,
        maxWidth: 160,
        boxShadow: data.selected
          ? '0 0 0 1px rgba(59,130,246,0.4)'
          : 'none',
      }}
    >
      <p className="font-medium leading-snug" style={{ color: '#E8ECF4', fontSize: 11 }}>
        {data.label}
      </p>

      {analyzed && (
        <p className="font-medium" style={{ color: riskColor, fontSize: 10, lineHeight: 1.2 }}>
          {RISK_LEVEL_LABELS[data.riskLevel] ?? ''}
        </p>
      )}

      <Handle type="target" position={Position.Left} style={HIDDEN_HANDLE} />
      <Handle type="source" position={Position.Right} style={HIDDEN_HANDLE} />
    </div>
  )
}
