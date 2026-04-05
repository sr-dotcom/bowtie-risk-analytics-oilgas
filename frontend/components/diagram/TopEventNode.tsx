'use client'

import { Handle, Position } from '@xyflow/react'
import type { NodeProps, Node } from '@xyflow/react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type TopEventNodeData = {
  label: string
}

export type TopEventNodeType = Node<TopEventNodeData, 'topEvent'>

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const HIDDEN_HANDLE = { opacity: 0, width: 1, height: 1 } as const

export default function TopEventNode({ data }: NodeProps<TopEventNodeType>) {
  return (
    <div
      className="w-[180px] text-center nodrag"
      style={{
        backgroundColor: '#1A1D27',
        border: '2px solid #F59E0B',
        borderRadius: 6,
        padding: '12px 16px',
      }}
    >
      <p style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#F59E0B', marginBottom: 4 }}>
        Top Event
      </p>
      <p style={{ fontSize: 13, fontWeight: 400, lineHeight: 1.3, color: '#E8ECF4' }}>
        {data.label}
      </p>

      <Handle type="target" position={Position.Left} style={HIDDEN_HANDLE} />
      <Handle type="source" position={Position.Right} style={HIDDEN_HANDLE} />
    </div>
  )
}
