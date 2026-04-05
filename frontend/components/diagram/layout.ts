// No 'use client' — pure utility module, no browser APIs
import type { Node, Edge } from '@xyflow/react'
import type { Barrier } from '@/lib/types'

// ---------------------------------------------------------------------------
// Node dimensions (match the TSX components)
// ---------------------------------------------------------------------------
const BARRIER_W = 130
const BARRIER_H = 40
const THREAT_W = 180
const THREAT_H = 50
const CONSEQUENCE_W = 180
const CONSEQUENCE_H = 50
const TOP_EVENT_W = 180
const TOP_EVENT_H = 90

// ---------------------------------------------------------------------------
// Fixed positions (top-left corner, React Flow coordinate system)
// These create a 1200×700 canvas with the bowtie centered.
// ---------------------------------------------------------------------------

// Threats — far left, stacked vertically
const THREAT_POSITIONS = [
  { x: 30, y: 200 }, // "Equipment overpressure"
  { x: 30, y: 500 }, // "Operator error during transfer"
]

// Top Event — center of the bowtie
// Left handle at (550, 350), right handle at (730, 350)
const TOP_EVENT_POS = { x: 550, y: 305 }

// Consequences — far right, stacked vertically
const CONSEQUENCE_POSITIONS = [
  { x: 970, y: 200 }, // "Gas release / toxic exposure"
  { x: 970, y: 500 }, // "Fire / explosion"
]

// ---------------------------------------------------------------------------
// Handle positions (where edges connect — center of left/right node edges)
// ---------------------------------------------------------------------------

// Threat right handles: rightEdge = x + w, centerY = y + h/2
const THREAT_HANDLES_R = THREAT_POSITIONS.map((p) => ({
  x: p.x + THREAT_W,
  y: p.y + THREAT_H / 2,
}))

// Top event handles
const TE_HANDLE_L = { x: TOP_EVENT_POS.x, y: TOP_EVENT_POS.y + TOP_EVENT_H / 2 }
const TE_HANDLE_R = { x: TOP_EVENT_POS.x + TOP_EVENT_W, y: TOP_EVENT_POS.y + TOP_EVENT_H / 2 }

// Consequence left handles
const CONSEQUENCE_HANDLES_L = CONSEQUENCE_POSITIONS.map((p) => ({
  x: p.x,
  y: p.y + CONSEQUENCE_H / 2,
}))

// ---------------------------------------------------------------------------
// Demo threats and consequences (hardcoded — will be user-enterable later)
// ---------------------------------------------------------------------------

const DEMO_THREATS = [
  { id: 'threat-1', label: 'Equipment overpressure' },
  { id: 'threat-2', label: 'Operator error during transfer' },
]

const DEMO_CONSEQUENCES = [
  { id: 'consequence-1', label: 'Gas release / toxic exposure' },
  { id: 'consequence-2', label: 'Fire / explosion' },
]

// ---------------------------------------------------------------------------
// Layout builder
// ---------------------------------------------------------------------------

function lerp(a: number, b: number, t: number): number {
  return a + t * (b - a)
}

/**
 * Build a BowTieXP-style layout with barriers positioned along diagonal
 * lines from threats → top event → consequences.
 *
 * Prevention barriers sit ON the line from each threat to the top event.
 * Mitigation barriers sit ON the line from the top event, then fan out
 * to each consequence.
 */
export function buildBowtieLayout(
  barriers: Barrier[],
  eventDescription: string,
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = []
  const edges: Edge[] = []

  const prevBarriers = barriers.filter((b) => b.side === 'prevention')
  const mitBarriers = barriers.filter((b) => b.side === 'mitigation')

  // --- Top Event ---
  nodes.push({
    id: 'top-event',
    type: 'topEvent',
    position: TOP_EVENT_POS,
    data: { label: eventDescription || 'Top Event' },
  })

  // --- Threats ---
  DEMO_THREATS.forEach((t, i) => {
    nodes.push({
      id: t.id,
      type: 'threat',
      position: THREAT_POSITIONS[i],
      data: { label: t.label },
    })
  })

  // --- Consequences ---
  DEMO_CONSEQUENCES.forEach((c, i) => {
    nodes.push({
      id: c.id,
      type: 'consequence',
      position: CONSEQUENCE_POSITIONS[i],
      data: { label: c.label },
    })
  })

  // --- Prevention barriers: distribute across threat pathways ---
  const pathwayCount = DEMO_THREATS.length
  const prevPerPathway = Math.ceil(prevBarriers.length / pathwayCount)

  for (let pathIdx = 0; pathIdx < pathwayCount; pathIdx++) {
    const pathway = prevBarriers.slice(
      pathIdx * prevPerPathway,
      (pathIdx + 1) * prevPerPathway,
    )
    // Interpolation line: threat right handle → top event left handle
    const from = THREAT_HANDLES_R[pathIdx]
    const to = TE_HANDLE_L
    const n = pathway.length

    pathway.forEach((b, bIdx) => {
      // Evenly space: t = 1/(n+1), 2/(n+1), ..., n/(n+1)
      const t = (bIdx + 1) / (n + 1)
      const cx = lerp(from.x, to.x, t)
      const cy = lerp(from.y, to.y, t)

      nodes.push({
        id: b.id,
        type: 'barrier',
        position: { x: cx - BARRIER_W / 2, y: cy - BARRIER_H / 2 },
        data: {
          label: b.name,
          riskLevel: b.riskLevel ?? 'unanalyzed',
          probability: b.probability,
          barrierId: b.id,
        },
      })
    })

    // Edge chain: threat → barrier₁ → barrier₂ → ... → top-event
    const chain = [
      DEMO_THREATS[pathIdx].id,
      ...pathway.map((b) => b.id),
      'top-event',
    ]

    for (let i = 0; i < chain.length - 1; i++) {
      edges.push({
        id: `e-prev-${pathIdx}-${i}`,
        source: chain[i],
        target: chain[i + 1],
        type: 'straight',
        style: { stroke: '#6366F1', strokeWidth: 2.5 },
      })
    }
  }

  // --- Mitigation barriers: center line, then fan to consequences ---
  if (mitBarriers.length > 0) {
    const n = mitBarriers.length

    mitBarriers.forEach((b, bIdx) => {
      // Place along the horizontal center line from TE right handle
      // toward the midpoint between consequences
      const t = (bIdx + 1) / (n + 1)
      const cx = lerp(TE_HANDLE_R.x, CONSEQUENCE_POSITIONS[0].x, t)
      const cy = TE_HANDLE_R.y // stay on center line

      nodes.push({
        id: b.id,
        type: 'barrier',
        position: { x: cx - BARRIER_W / 2, y: cy - BARRIER_H / 2 },
        data: {
          label: b.name,
          riskLevel: b.riskLevel ?? 'unanalyzed',
          probability: b.probability,
          barrierId: b.id,
        },
      })
    })

    // Edge chain: top-event → mit₁ → mit₂ → ...
    const mitChain = ['top-event', ...mitBarriers.map((b) => b.id)]
    for (let i = 0; i < mitChain.length - 1; i++) {
      edges.push({
        id: `e-mit-chain-${i}`,
        source: mitChain[i],
        target: mitChain[i + 1],
        type: 'straight',
        style: { stroke: '#F97316', strokeWidth: 2.5 },
      })
    }

    // Last mitigation barrier → each consequence (fan out)
    const lastMitId = mitBarriers[mitBarriers.length - 1].id
    DEMO_CONSEQUENCES.forEach((c, i) => {
      edges.push({
        id: `e-mit-con-${i}`,
        source: lastMitId,
        target: c.id,
        type: 'straight',
        style: { stroke: '#F97316', strokeWidth: 2.5 },
      })
    })
  } else {
    // No mitigation barriers: top-event → each consequence directly
    DEMO_CONSEQUENCES.forEach((c, i) => {
      edges.push({
        id: `e-te-con-${i}`,
        source: 'top-event',
        target: c.id,
        type: 'straight',
        style: { stroke: '#F97316', strokeWidth: 2.5 },
      })
    })
  }

  return { nodes, edges }
}
