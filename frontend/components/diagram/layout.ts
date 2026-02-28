// No 'use client' — pure utility module, no browser APIs
import dagre from '@dagrejs/dagre'
import type { Node, Edge } from '@xyflow/react'
import type { Barrier } from '@/lib/types'

const NODE_WIDTH = 160
const NODE_HEIGHT = 60
const TOP_EVENT_WIDTH = 180
const TOP_EVENT_HEIGHT = 70

/**
 * Build a dagre LR layout from the barriers list and event description.
 *
 * Prevention barriers are placed left of the top event; mitigation barriers
 * are placed right. Dagre positions are center-based, so we subtract half
 * the node dimensions to get the top-left origin that React Flow expects.
 *
 * @param barriers - Current barrier list from BowtieContext.
 * @param eventDescription - Label for the center top-event node.
 * @returns { nodes, edges } ready to pass to <ReactFlow>.
 */
export function buildDagreLayout(
  barriers: Barrier[],
  eventDescription: string,
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'LR', ranksep: 80, nodesep: 40 })

  // Register top event node (slightly larger than barrier nodes)
  const topEventId = 'top-event'
  g.setNode(topEventId, { width: TOP_EVENT_WIDTH, height: TOP_EVENT_HEIGHT })

  // Register each barrier node and its edge to/from top event
  barriers.forEach((b) => {
    g.setNode(b.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
    if (b.side === 'prevention') {
      // Prevention: barrier → top event
      g.setEdge(b.id, topEventId)
    } else {
      // Mitigation: top event → barrier
      g.setEdge(topEventId, b.id)
    }
  })

  dagre.layout(g)

  // Top event node — subtract half dimensions (dagre gives center coordinates)
  const topEventPos = g.node(topEventId)
  const topEventNode: Node = {
    id: topEventId,
    type: 'topEvent',
    position: {
      x: topEventPos.x - TOP_EVENT_WIDTH / 2,
      y: topEventPos.y - TOP_EVENT_HEIGHT / 2,
    },
    data: { label: eventDescription || 'Top Event' },
  }

  // Barrier nodes
  const barrierNodes: Node[] = barriers.map((b) => {
    const pos = g.node(b.id)
    return {
      id: b.id,
      type: 'barrier',
      position: {
        x: pos.x - NODE_WIDTH / 2,
        y: pos.y - NODE_HEIGHT / 2,
      },
      data: {
        label: b.name,
        riskLevel: b.riskLevel ?? 'unanalyzed',
        probability: b.probability,
        barrierId: b.id,
      },
    }
  })

  // Edges
  const edges: Edge[] = barriers.map((b) => ({
    id: `e-${b.id}`,
    source: b.side === 'prevention' ? b.id : topEventId,
    target: b.side === 'prevention' ? topEventId : b.id,
    type: 'smoothstep',
  }))

  return {
    nodes: [topEventNode, ...barrierNodes],
    edges,
  }
}
