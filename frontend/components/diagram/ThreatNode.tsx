'use client'

import { Handle, Position } from '@xyflow/react'
import type { NodeProps, Node } from '@xyflow/react'

export type ThreatNodeData = {
  label: string
}

export type ThreatNodeType = Node<ThreatNodeData, 'threat'>

const HIDDEN_HANDLE = { opacity: 0, width: 1, height: 1 } as const

export default function ThreatNode({ data }: NodeProps<ThreatNodeType>) {
  return (
    <div
      className="w-[180px] text-center nodrag"
      style={{
        backgroundColor: '#F59E0B',
        color: '#1A1D27',
        borderRadius: 4,
        padding: '8px 12px',
      }}
    >
      <p style={{ fontSize: 12, fontWeight: 700, lineHeight: 1.3 }}>{data.label}</p>
      <Handle type="source" position={Position.Right} style={HIDDEN_HANDLE} />
    </div>
  )
}
