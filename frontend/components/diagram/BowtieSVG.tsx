'use client'

import { useState, useMemo } from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Threat {
  id: string
  name: string
  contribution: 'high' | 'medium' | 'low'
}

interface Consequence {
  id: string
  name: string
}

interface BarrierInput {
  id: string
  name: string
  side: 'prevention' | 'mitigation'
  barrier_type: string
  barrier_role?: string
  line_of_defense?: string
  risk_level?: 'Low' | 'Medium' | 'High' | null
  threatId?: string
  consequenceId?: string
}

export interface BowtieSVGProps {
  topEvent: string
  hazardName?: string
  threats: Threat[]
  consequences: Consequence[]
  barriers: BarrierInput[]
  selectedBarrierId: string | null
  onBarrierClick: (barrierId: string) => void
}

// ---------------------------------------------------------------------------
// Constants (BowTieXP visual spec)
// ---------------------------------------------------------------------------

const THREAT_X = 30
const THREAT_W = 200
const THREAT_H = 115
const BARRIER_START_X = 340   // unused after Task 1 — kept for reference
const BARRIER_W = 180
const BARRIER_H = 90
const BARRIER_GAP_X = 30      // unused after Task 1 — kept for reference
const TOP_EVENT_CX = 700
const TOP_EVENT_R = 80
const MIT_START_X = TOP_EVENT_CX + TOP_EVENT_R + 100 // unused after Task 1 — kept for reference
const CONSEQUENCE_X = 1300
const CONSEQUENCE_W = 200
const CONSEQUENCE_H = 90

const BLUE = '#0000EE'
const DARK_BLUE = '#0000CC'
const LINE_COLOR = '#AAA'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function wrapText(text: string, maxChars: number): string[] {
  const words = text.split(' ')
  const lines: string[] = []
  let cur = ''
  for (const w of words) {
    if (cur && (cur + ' ' + w).length > maxChars) {
      lines.push(cur)
      cur = w
    } else {
      cur = cur ? cur + ' ' + w : w
    }
  }
  if (cur) lines.push(cur)
  return lines
}

function typeInfo(t: string): { color: string; label: string } {
  switch (t) {
    case 'engineering':
      return { color: '#3B82F6', label: 'Engineered' }
    case 'administrative':
      return { color: '#94A3B8', label: 'Administrative' }
    case 'ppe':
      return { color: '#22C55E', label: 'Behavioural' }
    case 'active_human':
      return { color: '#14B8A6', label: 'Active Human' }
    case 'active_hw_human':
      return { color: '#6366F1', label: 'HW + Human' }
    default:
      return { color: '#94A3B8', label: t.replace(/_/g, ' ') }
  }
}

function contribInfo(c: 'high' | 'medium' | 'low') {
  switch (c) {
    case 'high':
      return { color: '#DC2626', label: 'High Contribution' }
    case 'medium':
      return { color: '#F59E0B', label: 'Medium Contribution' }
    case 'low':
      return { color: '#F59E0B', label: 'Low Contribution' }
  }
}

function riskColor(level: string | null | undefined): string {
  switch (level) {
    case 'High':
      return '#EF4444'
    case 'Medium':
      return '#F59E0B'
    case 'Low':
      return '#22C55E'
    default:
      return '#94A3B8'
  }
}

/** Cubic bezier S-curve from (x1,y1) to (x2,y2) */
function sCurve(x1: number, y1: number, x2: number, y2: number): string {
  const dx = x2 - x1
  return `M ${x1} ${y1} C ${x1 + dx * 0.25} ${y1}, ${x1 + dx * 0.75} ${y2}, ${x2} ${y2}`
}

// ---------------------------------------------------------------------------
// Layout computation
// ---------------------------------------------------------------------------

interface PositionedThreat extends Threat {
  x: number
  y: number
  cy: number
}
interface PositionedConsequence extends Consequence {
  x: number
  y: number
  cy: number
}
interface PositionedBarrier extends BarrierInput {
  x: number
  y: number
  cy: number
}

function computeLayout(
  threats: Threat[],
  consequences: Consequence[],
  barriers: BarrierInput[],
) {
  const rows = Math.max(threats.length, consequences.length, 1)
  const H = rows * 300 + 100
  const CY = H / 2

  // Vertical distribution for a set of boxes
  function spreadY(count: number, boxH: number): number[] {
    if (count <= 0) return []
    if (count === 1) return [CY - boxH / 2]
    const totalSpace = H - 160
    const slot = totalSpace / count
    return Array.from({ length: count }, (_, i) => 80 + i * slot + (slot - boxH) / 2)
  }

  const tPos: PositionedThreat[] = threats.map((t, i) => {
    const ys = spreadY(threats.length, THREAT_H)
    return { ...t, x: THREAT_X, y: ys[i], cy: ys[i] + THREAT_H / 2 }
  })

  const cPos: PositionedConsequence[] = consequences.map((c, i) => {
    const ys = spreadY(consequences.length, CONSEQUENCE_H)
    return { ...c, x: CONSEQUENCE_X, y: ys[i], cy: ys[i] + CONSEQUENCE_H / 2 }
  })

  // Group prevention barriers by threat (round-robin if no threatId)
  const prev = barriers.filter((b) => b.side === 'prevention')
  const mit = barriers.filter((b) => b.side === 'mitigation')

  const prevByThreat = new Map<string, BarrierInput[]>()
  for (const t of threats) prevByThreat.set(t.id, [])

  for (const b of prev) {
    if (b.threatId && prevByThreat.has(b.threatId)) {
      prevByThreat.get(b.threatId)!.push(b)
    } else if (threats.length > 0) {
      // Find threat with fewest barriers
      let minId = threats[0].id
      let minN = Infinity
      for (const [id, bs] of prevByThreat) {
        if (bs.length < minN) {
          minN = bs.length
          minId = id
        }
      }
      prevByThreat.get(minId)!.push(b)
    }
  }

  // Position prevention barriers along each threat → top-event pathway.
  // For each threat, divide the horizontal space [threat_right, top_event_left_tangent]
  // into (n+1) equal segments; barrier j sits at segment (j+1).
  // Y is linearly interpolated along the straight line from threat cy to CY at that X.
  const bPos: PositionedBarrier[] = []

  const prevStartX = THREAT_X + THREAT_W          // 230 — threat right edge
  const prevEndX   = TOP_EVENT_CX - TOP_EVENT_R   // 620 — top-event left tangent

  for (const tp of tPos) {
    const bs = prevByThreat.get(tp.id) ?? []
    const n = bs.length
    if (n === 0) continue

    const segW = (prevEndX - prevStartX) / (n + 1)

    for (let j = 0; j < n; j++) {
      const bCenterX = prevStartX + (j + 1) * segW
      const bx       = bCenterX - BARRIER_W / 2
      const tParam   = (bCenterX - prevStartX) / (prevEndX - prevStartX)
      const bCenterY = tp.cy + tParam * (CY - tp.cy)
      const by       = bCenterY - BARRIER_H / 2
      bPos.push({ ...bs[j], x: bx, y: by, cy: bCenterY })
    }
  }

  // Position mitigation barriers fanning out toward consequences.
  // Assign round-robin to consequences, then distribute each group along
  // the straight line from top-event right tangent to its consequence.
  const mitStartX = TOP_EVENT_CX + TOP_EVENT_R   // 780
  const mitEndX   = CONSEQUENCE_X                // 1300

  const mitByConsequence = new Map<string, BarrierInput[]>()
  for (const c of consequences) mitByConsequence.set(c.id, [])

  // Round-robin assignment (or single bucket if no consequences)
  if (cPos.length > 0) {
    for (let j = 0; j < mit.length; j++) {
      const targetId = cPos[j % cPos.length].id
      mitByConsequence.get(targetId)!.push(mit[j])
    }
  }

  for (const cp of cPos) {
    const bs = mitByConsequence.get(cp.id) ?? []
    const n  = bs.length
    if (n === 0) continue

    const segW = (mitEndX - mitStartX) / (n + 1)

    for (let j = 0; j < n; j++) {
      const bCenterX = mitStartX + (j + 1) * segW
      const bx       = bCenterX - BARRIER_W / 2
      const tParam   = (bCenterX - mitStartX) / (mitEndX - mitStartX)
      const bCenterY = CY + tParam * (cp.cy - CY)
      const by       = bCenterY - BARRIER_H / 2
      bPos.push({ ...bs[j], x: bx, y: by, cy: bCenterY })
    }
  }

  return { H, CY, tPos, cPos, bPos, prevByThreat, mitByConsequence }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const HAZARD_W = 160
const HAZARD_H = 40

export default function BowtieSVG({
  topEvent,
  hazardName,
  threats,
  consequences,
  barriers,
  selectedBarrierId,
  onBarrierClick,
}: BowtieSVGProps) {
  const [zoom, setZoom] = useState(1)

  const layout = useMemo(
    () => computeLayout(threats, consequences, barriers),
    [threats, consequences, barriers],
  )

  const { H, CY, tPos, cPos, bPos, prevByThreat, mitByConsequence } = layout

  // Top event text lines
  const teLines = wrapText(topEvent, 12)

  // ---- Build pathway curves ----
  const paths: Array<{ d: string }> = []

  // Prevention pathways: threat → barriers → top event
  for (const tp of tPos) {
    const bs = (prevByThreat.get(tp.id) ?? [])
      .map((b) => bPos.find((bp) => bp.id === b.id))
      .filter(Boolean) as PositionedBarrier[]

    // Sorted by x position
    bs.sort((a, b) => a.x - b.x)

    if (bs.length === 0) {
      // Direct: threat right edge → top event left tangent
      const tx = TOP_EVENT_CX - TOP_EVENT_R
      paths.push({ d: sCurve(THREAT_X + THREAT_W, tp.cy, tx, CY) })
    } else {
      // Threat → first barrier
      paths.push({
        d: sCurve(THREAT_X + THREAT_W, tp.cy, bs[0].x, bs[0].cy),
      })
      // Between consecutive barriers
      for (let i = 0; i < bs.length - 1; i++) {
        paths.push({
          d: sCurve(bs[i].x + BARRIER_W, bs[i].cy, bs[i + 1].x, bs[i + 1].cy),
        })
      }
      // Last barrier → top event left tangent
      const last = bs[bs.length - 1]
      const dx = TOP_EVENT_CX - (last.x + BARRIER_W)
      const dy = CY - last.cy
      const dist = Math.sqrt(dx * dx + dy * dy)
      const tx = TOP_EVENT_CX - TOP_EVENT_R * (dx / dist)
      const ty = CY - TOP_EVENT_R * (dy / dist)
      paths.push({ d: sCurve(last.x + BARRIER_W, last.cy, tx, ty) })
    }
  }

  // Mitigation pathways: one chain per consequence (mirrors prevention side)
  for (const cp of cPos) {
    const bs = (mitByConsequence.get(cp.id) ?? [])
      .map((b) => bPos.find((bp) => bp.id === b.id))
      .filter(Boolean) as PositionedBarrier[]

    bs.sort((a, b) => a.x - b.x)

    if (bs.length === 0) {
      // Direct: top event right tangent → consequence
      paths.push({ d: sCurve(TOP_EVENT_CX + TOP_EVENT_R, CY, cp.x, cp.cy) })
    } else {
      // Top event → first barrier left edge
      paths.push({ d: sCurve(TOP_EVENT_CX + TOP_EVENT_R, CY, bs[0].x, bs[0].cy) })
      // Between consecutive barriers
      for (let i = 0; i < bs.length - 1; i++) {
        paths.push({
          d: sCurve(bs[i].x + BARRIER_W, bs[i].cy, bs[i + 1].x, bs[i + 1].cy),
        })
      }
      // Last barrier right edge → consequence
      const last = bs[bs.length - 1]
      paths.push({ d: sCurve(last.x + BARRIER_W, last.cy, cp.x, cp.cy) })
    }
  }

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        overflow: 'auto',
        background: '#E0E0E0',
        position: 'relative',
      }}
    >
      <div
        style={{
          transform: `scale(${zoom})`,
          transformOrigin: '0 0',
          minWidth: 1600,
        }}
      >
        <svg
          viewBox={`0 0 1600 ${H}`}
          width="100%"
          style={{ fontFamily: 'Arial, sans-serif', display: 'block' }}
        >
          <defs>
            <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="barrier-shadow" x="-5%" y="-5%" width="110%" height="110%">
              <feDropShadow dx="1" dy="1" stdDeviation="2" floodOpacity="0.15" />
            </filter>
            <pattern id="hazard-stripes" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="5" height="10" fill="#FFD600" />
              <rect x="5" width="5" height="10" fill="#222" />
            </pattern>
          </defs>

          {/* ===== LAYER 1: Pathway curves ===== */}
          {paths.map((p, i) => (
            <path
              key={`path-${i}`}
              d={p.d}
              stroke={LINE_COLOR}
              strokeWidth={2}
              fill="none"
            />
          ))}

          {/* ===== LAYER 2: Barrier blocks (stripe integrated) ===== */}
          {bPos.map((b) => {
            const ti = typeInfo(b.barrier_type)
            const nameLines = wrapText(b.name, 22)
            const isSelected = b.id === selectedBarrierId
            return (
              <g
                key={`b-${b.id}`}
                style={{ cursor: 'pointer' }}
                onClick={() => onBarrierClick(b.id)}
              >
                {/* Selection glow — behind everything */}
                {isSelected && (
                  <rect
                    x={b.x - 4}
                    y={b.y - 4}
                    width={BARRIER_W + 8}
                    height={BARRIER_H + 8}
                    fill="none"
                    stroke="#3B82F6"
                    strokeWidth={2.5}
                    rx={3}
                    opacity={0.6}
                    filter="url(#glow)"
                  />
                )}
                {/* White barrier body */}
                <rect
                  x={b.x}
                  y={b.y}
                  width={BARRIER_W}
                  height={BARRIER_H}
                  fill="white"
                  stroke={isSelected ? '#3B82F6' : '#999'}
                  strokeWidth={isSelected ? 1.5 : 0.5}
                  filter="url(#barrier-shadow)"
                />
                {/* Status indicator — 3 small rects at top of barrier */}
                {[0, 1, 2].map((idx) => (
                  <rect
                    key={`ind-${idx}`}
                    x={b.x + 8 + idx * 16}
                    y={b.y + 4}
                    width={12}
                    height={8}
                    fill={riskColor(b.risk_level)}
                    rx={1}
                  />
                ))}
                {/* Row 1: Name */}
                {nameLines.map((line, li) => (
                  <text
                    key={li}
                    x={b.x + 8}
                    y={b.y + 26 + li * 15}
                    fill={BLUE}
                    fontSize={13}
                    fontWeight={700}
                  >
                    {line}
                  </text>
                ))}
                {/* Separator 1 */}
                <line
                  x1={b.x}
                  y1={b.y + 24 + nameLines.length * 15}
                  x2={b.x + BARRIER_W}
                  y2={b.y + 24 + nameLines.length * 15}
                  stroke="#DDD"
                  strokeWidth={0.5}
                />
                {/* Row 2: Role (underlined) */}
                {b.barrier_role && (
                  <text
                    x={b.x + 8}
                    y={b.y + 38 + nameLines.length * 15}
                    fill={BLUE}
                    fontSize={11}
                    textDecoration="underline"
                  >
                    {b.barrier_role}
                  </text>
                )}
                {/* Separator 2 */}
                <line
                  x1={b.x}
                  y1={b.y + BARRIER_H - 22}
                  x2={b.x + BARRIER_W}
                  y2={b.y + BARRIER_H - 22}
                  stroke="#DDD"
                  strokeWidth={0.5}
                />
                {/* Row 3: Type indicator */}
                <rect
                  x={b.x + 8}
                  y={b.y + BARRIER_H - 18}
                  width={12}
                  height={12}
                  fill={ti.color}
                  rx={1}
                />
                <text
                  x={b.x + 24}
                  y={b.y + BARRIER_H - 8}
                  fill={BLUE}
                  fontSize={10}
                >
                  {ti.label}
                </text>
              </g>
            )
          })}

          {/* ===== LAYER 4: Threat boxes ===== */}
          {tPos.map((t) => {
            const ci = contribInfo(t.contribution)
            const nameLines = wrapText(t.name, 18)
            return (
              <g key={`t-${t.id}`}>
                <rect
                  x={t.x}
                  y={t.y}
                  width={THREAT_W}
                  height={THREAT_H}
                  fill="#1565C0"
                  stroke="#0D47A1"
                  strokeWidth={1.5}
                />
                {nameLines.map((line, li) => (
                  <text
                    key={li}
                    x={t.x + THREAT_W / 2}
                    y={t.y + 24 + li * 18}
                    textAnchor="middle"
                    fill="white"
                    fontSize={15}
                    fontWeight={700}
                  >
                    {line}
                  </text>
                ))}
                {/* Contribution badge */}
                <rect
                  x={t.x + 20}
                  y={t.y + THREAT_H - 30}
                  width={14}
                  height={14}
                  fill={ci.color}
                  rx={1}
                />
                <text
                  x={t.x + 40}
                  y={t.y + THREAT_H - 18}
                  fill="white"
                  fontSize={11}
                  fontWeight={700}
                >
                  {ci.label}
                </text>
              </g>
            )
          })}

          {/* ===== LAYER 5a: Hazard box above top event ===== */}
          {(() => {
            const hx = TOP_EVENT_CX - HAZARD_W / 2
            const hy = CY - TOP_EVENT_R - 60 - HAZARD_H
            const hLabel = hazardName || 'Hazard'
            return (
              <g>
                <rect
                  x={hx}
                  y={hy}
                  width={HAZARD_W}
                  height={HAZARD_H}
                  fill="url(#hazard-stripes)"
                  stroke="#222"
                  strokeWidth={1.5}
                  rx={2}
                />
                <text
                  x={TOP_EVENT_CX}
                  y={hy + HAZARD_H / 2 + 5}
                  textAnchor="middle"
                  fill="#222"
                  fontSize={13}
                  fontWeight={700}
                >
                  {hLabel}
                </text>
                <line
                  x1={TOP_EVENT_CX}
                  y1={hy + HAZARD_H}
                  x2={TOP_EVENT_CX}
                  y2={CY - TOP_EVENT_R}
                  stroke="#666"
                  strokeWidth={1.5}
                />
              </g>
            )
          })()}

          {/* ===== LAYER 5b: Top Event ===== */}
          <circle
            cx={TOP_EVENT_CX}
            cy={CY}
            r={TOP_EVENT_R}
            fill="#FF6B00"
            stroke="#CC5500"
            strokeWidth={2}
          />
          {teLines.slice(0, 3).map((line, i) => (
            <text
              key={`te-${i}`}
              x={TOP_EVENT_CX}
              y={CY - 12 + i * 16}
              textAnchor="middle"
              fill="white"
              fontSize={13}
              fontWeight={700}
            >
              {line}
            </text>
          ))}
          <text
            x={TOP_EVENT_CX}
            y={CY + 34}
            textAnchor="middle"
            fill="rgba(255,255,255,0.7)"
            fontSize={9}
          >
            (Top Event)
          </text>

          {/* ===== LAYER 6: Consequence boxes ===== */}
          {cPos.map((c) => {
            const nameLines = wrapText(c.name, 20)
            return (
              <g key={`c-${c.id}`}>
                <rect
                  x={c.x}
                  y={c.y}
                  width={CONSEQUENCE_W}
                  height={CONSEQUENCE_H}
                  fill="#C62828"
                  stroke="#B71C1C"
                  strokeWidth={1.5}
                />
                {nameLines.map((line, li) => (
                  <text
                    key={li}
                    x={c.x + CONSEQUENCE_W / 2}
                    y={c.y + 24 + li * 18}
                    textAnchor="middle"
                    fill="white"
                    fontSize={14}
                    fontWeight={700}
                  >
                    {line}
                  </text>
                ))}
              </g>
            )
          })}
        </svg>
      </div>

      {/* Zoom controls */}
      <div
        style={{
          position: 'absolute',
          bottom: 16,
          left: 16,
          display: 'flex',
          gap: 4,
        }}
      >
        {[
          { label: '+', fn: () => setZoom((z) => Math.min(z + 0.1, 2)) },
          { label: '\u2212', fn: () => setZoom((z) => Math.max(z - 0.1, 0.5)) },
          {
            label: '\u2b1c',
            fn: () => setZoom(1),
          },
        ].map((btn) => (
          <button
            key={btn.label}
            onClick={btn.fn}
            style={{
              width: 32,
              height: 32,
              border: '1px solid #D1D5DB',
              borderRadius: 4,
              background: 'white',
              cursor: 'pointer',
              fontSize: 16,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#374151',
            }}
          >
            {btn.label}
          </button>
        ))}
      </div>
    </div>
  )
}
