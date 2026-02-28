'use client'

import { useCallback, useMemo, useState } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  type NodeMouseHandler,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { useBowtieContext } from '@/context/BowtieContext'
import { buildDagreLayout } from './layout'
import BarrierNode from './BarrierNode'
import TopEventNode from './TopEventNode'
import PathwayView from './PathwayView'

// ---------------------------------------------------------------------------
// CRITICAL: nodeTypes MUST be defined at module scope (outside any component).
// If defined inside a component body, React Flow will infinite re-render on
// every render because the object reference changes. See RESEARCH.md Pitfall 2.
// ---------------------------------------------------------------------------
const nodeTypes = {
  barrier: BarrierNode,
  topEvent: TopEventNode,
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function BowtieFlow() {
  const { barriers, eventDescription, predictions, setSelectedBarrierId, isAnalyzing, selectedBarrierId } =
    useBowtieContext()

  // View mode toggle: 'diagram' (React Flow) or 'pathway' (two-column card grid)
  const [viewMode, setViewMode] = useState<'diagram' | 'pathway'>('diagram')

  // Demo badge dismissal state
  const [showDemoBanner, setShowDemoBanner] = useState(true)

  // Build dagre layout and overlay predictions onto node data
  const { nodes, edges } = useMemo(() => {
    const layout = buildDagreLayout(barriers, eventDescription)

    // Overlay prediction results onto barrier nodes
    const nodesWithPredictions = layout.nodes.map((node) => {
      if (node.type !== 'barrier') return node

      const barrierId = node.data.barrierId as string
      const prediction = predictions[barrierId]
      if (!prediction) return node

      return {
        ...node,
        data: {
          ...node.data,
          probability: prediction.model1_probability,
          // riskLevel is derived from probability in BarrierForm (via setPrediction).
          // Here we reflect the barrier's current riskLevel from context.
        },
      }
    })

    // Sync riskLevel from barriers array (context is the source of truth)
    const barrierMap = new Map(barriers.map((b) => [b.id, b]))
    const finalNodes = nodesWithPredictions.map((node) => {
      if (node.type !== 'barrier') return node
      const barrierId = node.data.barrierId as string
      const barrier = barrierMap.get(barrierId)
      if (!barrier) return node
      return {
        ...node,
        data: {
          ...node.data,
          riskLevel: barrier.riskLevel,
          probability: barrier.probability,
        },
      }
    })

    // Mark selected barrier node
    const withSelection = finalNodes.map((node) => {
      if (node.type !== 'barrier') return node
      const barrierId = node.data.barrierId as string
      return {
        ...node,
        data: {
          ...node.data,
          selected: barrierId === selectedBarrierId,
        },
      }
    })

    return { nodes: withSelection, edges: layout.edges }
  }, [barriers, eventDescription, predictions, selectedBarrierId])

  // Node click handler — sets selectedBarrierId in context
  const onNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      if (node.type === 'barrier') {
        const barrierId = node.data.barrierId as string
        setSelectedBarrierId(barrierId)
      }
    },
    [setSelectedBarrierId],
  )

  // Determine if demo banner should show (only when barriers match demo scenario shape)
  const hasDemoBarriers = barriers.length === 5 && barriers.some((b) => b.name === 'Pressure Relief Valve')

  return (
    <div className="flex-1 h-full relative">
      {/* View toggle (D-10, Fidel-#55, Fidel-#56) */}
      <div className="absolute top-3 right-3 z-20 flex rounded-md overflow-hidden border border-gray-300 shadow-sm">
        <button
          onClick={() => setViewMode('diagram')}
          className={`px-3 py-1 text-xs font-medium transition-colors ${
            viewMode === 'diagram'
              ? 'bg-gray-800 text-white'
              : 'bg-white text-gray-600 hover:bg-gray-100'
          }`}
        >
          Diagram View
        </button>
        <button
          onClick={() => setViewMode('pathway')}
          className={`px-3 py-1 text-xs font-medium transition-colors ${
            viewMode === 'pathway'
              ? 'bg-gray-800 text-white'
              : 'bg-white text-gray-600 hover:bg-gray-100'
          }`}
        >
          Pathway View
        </button>
      </div>

      {/* Demo badge — shown above the diagram on first load with demo scenario */}
      {viewMode === 'diagram' && showDemoBanner && hasDemoBarriers && (
        <div className="absolute top-12 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-md px-3 py-1.5 text-xs text-blue-700 shadow">
          <span>Demo scenario — modify or start fresh</span>
          <button
            onClick={() => setShowDemoBanner(false)}
            className="ml-1 text-blue-400 hover:text-blue-700 font-medium"
            aria-label="Dismiss demo banner"
          >
            ×
          </button>
        </div>
      )}

      {/* Analyzing overlay — pulse effect on barrier nodes when analysis in-flight */}
      {viewMode === 'diagram' && isAnalyzing && (
        <div className="absolute inset-0 z-10 pointer-events-none flex items-end justify-center pb-4">
          <span className="bg-white border border-gray-200 rounded-md px-3 py-1.5 text-xs text-gray-600 shadow animate-pulse">
            Analyzing barriers...
          </span>
        </div>
      )}

      {/* Diagram view — kept mounted to preserve viewport state (Pitfall 3 from RESEARCH.md) */}
      <div className={viewMode === 'diagram' ? 'h-full' : 'hidden'}>
        <ReactFlowProvider>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodeClick={onNodeClick}
            fitView
            proOptions={{ hideAttribution: true }}
            className="bg-gray-50"
          >
            <Background />
            <Controls />
          </ReactFlow>
        </ReactFlowProvider>
      </div>

      {/* Pathway view — two-column barrier card grid */}
      {viewMode === 'pathway' && (
        <PathwayView
          barriers={barriers}
          predictions={predictions}
          selectedBarrierId={selectedBarrierId}
          onBarrierClick={(id) => setSelectedBarrierId(id)}
        />
      )}
    </div>
  )
}
