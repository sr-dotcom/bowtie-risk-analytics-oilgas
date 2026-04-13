'use client'

import { useState, useMemo } from 'react'

// ---------------------------------------------------------------------------
// Types (unchanged — same props interface)
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
// Visual constants — BowTieXP standard
// ---------------------------------------------------------------------------

const FONT = '"Segoe UI", Arial, sans-serif'

const TOP_EVENT_R = 50
const HAZARD_W = 140
const HAZARD_H = 40
const THREAT_W = 120
const THREAT_H = 48
const CONSEQUENCE_W = 120
const CONSEQUENCE_H = 48
const BAR_W = 32
const BAR_H = 72
const PADDING = 40
const THREAT_COL_W = 130
const TOP_EVENT_COL_W = 120
const CONSEQUENCE_COL_W = 130

// ---------------------------------------------------------------------------
// Color helpers
// ---------------------------------------------------------------------------

function riskFill(level: string | null | undefined): string {
  switch (level) {
    case 'High':
      return '#F44336'
    case 'Medium':
      return '#FFC107'
    case 'Low':
      return '#4CAF50'
    default:
      return '#9E9E9E'
  }
}

// ---------------------------------------------------------------------------
// Text wrapping
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

// ---------------------------------------------------------------------------
// Layout engine
// ---------------------------------------------------------------------------

interface PositionedThreat extends Threat {
  cx: number
  cy: number
}

interface PositionedConsequence extends Consequence {
  cx: number
  cy: number
}

interface PositionedBarrier extends BarrierInput {
  barX: number
  barY: number
  cy: number
  pathwayY: number
}

function computeLayout(
  threats: Threat[],
  consequences: Consequence[],
  barriers: BarrierInput[],
) {
  const threatCount = Math.max(threats.length, 1)
  const consCount = Math.max(consequences.length, 1)

  // Group barriers by side
  const prevBarriers = barriers.filter((b) => b.side === 'prevention')
  const mitBarriers = barriers.filter((b) => b.side === 'mitigation')

  // Assign prevention barriers to threats
  const prevByThreat = new Map<string, BarrierInput[]>()
  for (const t of threats) prevByThreat.set(t.id, [])
  for (const b of prevBarriers) {
    if (b.threatId && prevByThreat.has(b.threatId)) {
      prevByThreat.get(b.threatId)!.push(b)
    } else if (threats.length > 0) {
      let minId = threats[0].id
      let minN = Infinity
      for (const [id, bs] of prevByThreat) {
        if (bs.length < minN) { minN = bs.length; minId = id }
      }
      prevByThreat.get(minId)!.push(b)
    }
  }

  // Assign mitigation barriers to consequences (round-robin)
  const mitByCons = new Map<string, BarrierInput[]>()
  for (const c of consequences) mitByCons.set(c.id, [])
  if (consequences.length > 0) {
    for (let j = 0; j < mitBarriers.length; j++) {
      const targetId = consequences[j % consequences.length].id
      mitByCons.get(targetId)!.push(mitBarriers[j])
    }
  }

  // Compute max barrier counts per side
  let maxLeftBarriers = 0
  for (const bs of prevByThreat.values()) maxLeftBarriers = Math.max(maxLeftBarriers, bs.length)
  let maxRightBarriers = 0
  for (const bs of mitByCons.values()) maxRightBarriers = Math.max(maxRightBarriers, bs.length)

  const leftBarrierZoneW = Math.max(60, maxLeftBarriers * 50)
  const rightBarrierZoneW = Math.max(60, maxRightBarriers * 50)

  const canvasWidth =
    PADDING + THREAT_COL_W + leftBarrierZoneW + TOP_EVENT_COL_W +
    rightBarrierZoneW + CONSEQUENCE_COL_W + PADDING

  const canvasHeight = Math.max(
    300,
    Math.max(threatCount, consCount) * 100 + 80,
  )

  const topEventCX = PADDING + THREAT_COL_W + leftBarrierZoneW + TOP_EVENT_COL_W / 2
  const topEventCY = canvasHeight / 2

  // Vertical spread
  function spreadY(count: number): number[] {
    const ys: number[] = []
    for (let i = 0; i < count; i++) {
      ys.push(40 + ((canvasHeight - 80) / (count + 1)) * (i + 1))
    }
    return ys
  }

  const threatYs = spreadY(threats.length)
  const consYs = spreadY(consequences.length)

  const tPos: PositionedThreat[] = threats.map((t, i) => ({
    ...t,
    cx: PADDING + THREAT_COL_W / 2,
    cy: threatYs[i],
  }))

  const cPos: PositionedConsequence[] = consequences.map((c, i) => ({
    ...c,
    cx: canvasWidth - PADDING - CONSEQUENCE_COL_W / 2,
    cy: consYs[i],
  }))

  // Position barriers on pathways
  const bPos: PositionedBarrier[] = []

  const leftZoneStart = PADDING + THREAT_COL_W
  const leftZoneEnd = leftZoneStart + leftBarrierZoneW
  const rightZoneStart = leftZoneEnd + TOP_EVENT_COL_W
  const rightZoneEnd = rightZoneStart + rightBarrierZoneW

  for (const tp of tPos) {
    const bs = prevByThreat.get(tp.id) ?? []
    const n = bs.length
    if (n === 0) continue
    const spacing = leftBarrierZoneW / (n + 1)
    for (let k = 0; k < n; k++) {
      const centerX = leftZoneStart + spacing * (k + 1)
      bPos.push({
        ...bs[k],
        barX: centerX - BAR_W / 2,
        barY: tp.cy - BAR_H / 2,
        cy: tp.cy,
        pathwayY: tp.cy,
      })
    }
  }

  for (const cp of cPos) {
    const bs = mitByCons.get(cp.id) ?? []
    const n = bs.length
    if (n === 0) continue
    const spacing = rightBarrierZoneW / (n + 1)
    for (let k = 0; k < n; k++) {
      const centerX = rightZoneStart + spacing * (k + 1)
      bPos.push({
        ...bs[k],
        barX: centerX - BAR_W / 2,
        barY: cp.cy - BAR_H / 2,
        cy: cp.cy,
        pathwayY: cp.cy,
      })
    }
  }

  return {
    canvasWidth,
    canvasHeight,
    topEventCX,
    topEventCY,
    tPos,
    cPos,
    bPos,
    prevByThreat,
    mitByCons,
    leftZoneEnd,
    rightZoneStart,
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

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

  const {
    canvasWidth,
    canvasHeight,
    topEventCX,
    topEventCY,
    tPos,
    cPos,
    bPos,
    prevByThreat,
    mitByCons,
    leftZoneEnd,
    rightZoneStart,
  } = layout

  const teLines = wrapText(topEvent, 10)
  const hazardLabel = hazardName || 'Hazard'
  const hazardX = topEventCX - HAZARD_W / 2
  const hazardY = topEventCY - TOP_EVENT_R - 12 - HAZARD_H

  // Build two-segment pathway lines
  const pathLines: Array<{ d: string }> = []

  // Prevention side: threat right edge → horizontal to leftZoneEnd → diagonal to top event center
  for (const tp of tPos) {
    const threatRightX = tp.cx + THREAT_W / 2
    const d = `M ${threatRightX},${tp.cy} L ${leftZoneEnd},${tp.cy} L ${topEventCX},${topEventCY}`
    pathLines.push({ d })
  }

  // Mitigation side: top event center → diagonal to rightZoneStart → horizontal to consequence left edge
  for (const cp of cPos) {
    const consLeftX = cp.cx - CONSEQUENCE_W / 2
    const d = `M ${topEventCX},${topEventCY} L ${rightZoneStart},${cp.cy} L ${consLeftX},${cp.cy}`
    pathLines.push({ d })
  }

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        overflow: 'auto',
        background: '#FFFFFF',
        position: 'relative',
      }}
    >
      <div
        style={{
          transform: `scale(${zoom})`,
          transformOrigin: '0 0',
          minWidth: canvasWidth,
        }}
      >
        <svg
          viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}
          width="100%"
          style={{ fontFamily: FONT, display: 'block' }}
        >
          <defs>
            <pattern
              id="hazard-stripes"
              width="10"
              height="10"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)"
            >
              <rect width="5" height="10" fill="#FFC107" />
              <rect x="5" width="5" height="10" fill="#000" />
            </pattern>
          </defs>

          {/* Layer 1: Background */}
          <rect width={canvasWidth} height={canvasHeight} fill="#FFFFFF" />

          {/* Layer 2: Pathway lines */}
          {pathLines.map((p, i) => (
            <path
              key={`path-${i}`}
              d={p.d}
              stroke="#333333"
              strokeWidth={1.5}
              fill="none"
            />
          ))}

          {/* Layer 3: Hazard connecting line */}
          <line
            x1={topEventCX}
            y1={hazardY + HAZARD_H}
            x2={topEventCX}
            y2={topEventCY - TOP_EVENT_R}
            stroke="#333333"
            strokeWidth={1.5}
          />

          {/* Layer 4: Hazard box */}
          <rect
            x={hazardX}
            y={hazardY}
            width={HAZARD_W}
            height={HAZARD_H}
            fill="url(#hazard-stripes)"
            stroke="#F57F17"
            strokeWidth={2}
          />
          <text
            x={topEventCX}
            y={hazardY + HAZARD_H / 2 + 5}
            textAnchor="middle"
            fill="#000"
            fontSize={12}
            fontWeight={700}
          >
            {hazardLabel}
          </text>

          {/* Layer 5: Top event circle */}
          <circle
            cx={topEventCX}
            cy={topEventCY}
            r={TOP_EVENT_R}
            fill="#D32F2F"
            stroke="#B71C1C"
            strokeWidth={2}
          />
          {teLines.slice(0, 4).map((line, i) => {
            const totalLines = Math.min(teLines.length, 4)
            const lineH = 15
            const blockH = totalLines * lineH
            const startY = topEventCY - blockH / 2 + lineH / 2
            return (
              <text
                key={`te-${i}`}
                x={topEventCX}
                y={startY + i * lineH}
                textAnchor="middle"
                dominantBaseline="central"
                fill="white"
                fontSize={13}
                fontWeight={700}
              >
                {line}
              </text>
            )
          })}

          {/* Layer 6: Threat boxes */}
          {tPos.map((t) => {
            const lines = wrapText(t.name, 12)
            const tx = t.cx - THREAT_W / 2
            const ty = t.cy - THREAT_H / 2
            return (
              <g key={`t-${t.id}`}>
                <rect
                  x={tx}
                  y={ty}
                  width={THREAT_W}
                  height={THREAT_H}
                  fill="#1976D2"
                  stroke="#0D47A1"
                  strokeWidth={1.5}
                  rx={2}
                />
                {lines.map((line, li) => {
                  const totalLines = lines.length
                  const lineH = 14
                  const blockH = totalLines * lineH
                  const startY = t.cy - blockH / 2 + lineH / 2
                  return (
                    <text
                      key={li}
                      x={t.cx}
                      y={startY + li * lineH}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fill="white"
                      fontSize={11}
                      fontWeight={600}
                    >
                      {line}
                    </text>
                  )
                })}
              </g>
            )
          })}

          {/* Layer 7: Consequence boxes */}
          {cPos.map((c) => {
            const lines = wrapText(c.name, 12)
            const cx = c.cx - CONSEQUENCE_W / 2
            const cy = c.cy - CONSEQUENCE_H / 2
            return (
              <g key={`c-${c.id}`}>
                <rect
                  x={cx}
                  y={cy}
                  width={CONSEQUENCE_W}
                  height={CONSEQUENCE_H}
                  fill="#D32F2F"
                  stroke="#B71C1C"
                  strokeWidth={1.5}
                  rx={2}
                />
                {lines.map((line, li) => {
                  const totalLines = lines.length
                  const lineH = 14
                  const blockH = totalLines * lineH
                  const startY = c.cy - blockH / 2 + lineH / 2
                  return (
                    <text
                      key={li}
                      x={c.cx}
                      y={startY + li * lineH}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fill="white"
                      fontSize={11}
                      fontWeight={600}
                    >
                      {line}
                    </text>
                  )
                })}
              </g>
            )
          })}

          {/* Layer 8: Barrier bars */}
          {bPos.map((b) => {
            const isSelected = b.id === selectedBarrierId
            const fill = riskFill(b.risk_level)
            return (
              <g
                key={`b-${b.id}`}
                style={{ cursor: 'pointer' }}
                onClick={() => onBarrierClick(b.id)}
              >
                {isSelected && (
                  <rect
                    x={b.barX - 3}
                    y={b.barY - 3}
                    width={BAR_W + 6}
                    height={BAR_H + 6}
                    fill="none"
                    stroke="#FF6F00"
                    strokeWidth={3}
                    rx={2}
                  />
                )}
                <rect
                  x={b.barX}
                  y={b.barY}
                  width={BAR_W}
                  height={BAR_H}
                  fill={fill}
                  stroke="#616161"
                  strokeWidth={1}
                />
              </g>
            )
          })}

          {/* Layer 9: Barrier name labels below bars */}
          {bPos.map((b) => {
            const lines = wrapText(b.name, 8)
            const labelX = b.barX + BAR_W / 2
            const labelY = b.barY + BAR_H + 14
            return lines.map((line, li) => (
              <text
                key={`bl-${b.id}-${li}`}
                x={labelX}
                y={labelY + li * 11}
                textAnchor="middle"
                fill="#333333"
                fontSize={9}
              >
                {line}
              </text>
            ))
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
          { label: '\u2b1c', fn: () => setZoom(1) },
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
