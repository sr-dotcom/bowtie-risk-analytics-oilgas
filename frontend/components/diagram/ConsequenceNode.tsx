'use client'

import { Handle, Position } from '@xyflow/react'
import type { NodeProps, Node } from '@xyflow/react'

export type ConsequenceNodeData = {
  label: string
}

export type ConsequenceNodeType = Node<ConsequenceNodeData, 'consequence'>

const HIDDEN_HANDLE = { opacity: 0, width: 1, height: 1 } as const

export default function ConsequenceNode({ data }: NodeProps<ConsequenceNodeType>) {
  return (
    <div
      className="w-[180px] text-center nodrag"
      style={{
        backgroundColor: '#EF4444',
        color: '#FFFFFF',
        borderRadius: 4,
        padding: '8px 12px',
      }}
    >
      <p style={{ fontSize: 12, fontWeight: 700, lineHeight: 1.3 }}>{data.label}</p>
      <Handle type="target" position={Position.Left} style={HIDDEN_HANDLE} />
    </div>
  )
}
