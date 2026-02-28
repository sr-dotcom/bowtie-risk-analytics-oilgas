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

export default function TopEventNode({ data }: NodeProps<TopEventNodeType>) {
  return (
    <div className="rounded-lg bg-gray-800 text-white p-4 shadow-lg w-[180px] text-center nodrag">
      <p className="text-sm font-semibold leading-tight">{data.label}</p>

      {/* Left handle: receives edges from prevention barriers */}
      <Handle type="target" position={Position.Left} />
      {/* Right handle: sends edges to mitigation barriers */}
      <Handle type="source" position={Position.Right} />
    </div>
  )
}
