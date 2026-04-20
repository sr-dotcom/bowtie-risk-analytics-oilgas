'use client'

import { useMemo } from 'react'

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
// Layout constants — extracted exactly from bowtie-reference-v4.html
// ---------------------------------------------------------------------------

const CW = 1800
const THREAT_W = 150
const THREAT_H = 70
const BARRIER_W = 130
const BARRIER_H = 75
const CONS_W = 150
const CONS_H = 70
const TOP_EVENT_R = 80
const PADDING = 60
const BARRIER_TAB_OVERHANG = 11
const ROW_H = 160
const HAZARD_W = 180
const HAZARD_H = 55
const STEM_GAP = 30

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function wrapText(text: string, maxChars: number, maxLines: number): string[] {
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
  if (lines.length > maxLines) {
    const truncated = lines.slice(0, maxLines)
    truncated[maxLines - 1] = truncated[maxLines - 1].slice(0, maxChars - 3) + '...'
    return truncated
  }
  return lines
}

function riskBadge(level: string): { color: string; letter: string } {
  switch (level) {
    case 'High':
      return { color: '#F44336', letter: 'H' }
    case 'Medium':
      return { color: '#FF9800', letter: 'M' }
    case 'Low':
      return { color: '#4CAF50', letter: 'L' }
    default:
      return { color: '#999', letter: '?' }
  }
}

// ---------------------------------------------------------------------------
// Layout engine — mirrors bowtie-reference-v4.html exactly
// ---------------------------------------------------------------------------

interface LayoutResult {
  CH: number
  cx: number
  cy: number
  hazardX: number
  hazardY: number
  threatPositions: Array<{
    cy: number
    barrierXs: number[]
  }>
  consPositions: Array<{
    cy: number
    barrierXs: number[]
  }>
  leftConnects: Array<{ x: number; y: number }>
  rightConnects: Array<{ x: number; y: number }>
  prevByThreat: Map<string, BarrierInput[]>
  mitByConsequence: Map<string, BarrierInput[]>
}

function computeLayout(
  threats: Threat[],
  consequences: Consequence[],
  barriers: BarrierInput[],
): LayoutResult {
  const numThreats = Math.max(threats.length, 1)
  const numCons = Math.max(consequences.length, 1)
  const numRows = Math.max(numThreats, numCons)
  const contentH = (numRows + 1) * ROW_H
  const cx = CW / 2
  const contentCy = contentH / 2

  // Vertical positions (relative to content area)
  const threatCenterYRel = (i: number) => (contentH / (numThreats + 1)) * (i + 1)
  const consCenterYRel = (j: number) => (contentH / (numCons + 1)) * (j + 1)

  // Hazard position (relative)
  const hazardYRel = contentCy - TOP_EVENT_R - STEM_GAP - HAZARD_H

  // Bounding box — offset so topmost element sits at y=12
  const topMostRel = Math.min(
    hazardYRel,
    threatCenterYRel(0) - THREAT_H / 2 - BARRIER_TAB_OVERHANG,
  )
  const bottomMostRel = Math.max(
    contentCy + TOP_EVENT_R,
    threatCenterYRel(numThreats - 1) + THREAT_H / 2 + BARRIER_TAB_OVERHANG,
    consCenterYRel(numCons - 1) + CONS_H / 2,
  )
  const yOffset = 12 - topMostRel

  // Final absolute positions
  const cy = contentCy + yOffset
  const threatCenterY = (i: number) => threatCenterYRel(i) + yOffset
  const consCenterY = (j: number) => consCenterYRel(j) + yOffset
  const hazardY = hazardYRel + yOffset
  const hazardX = cx - HAZARD_W / 2
  const CH = bottomMostRel + yOffset + 20

  // Fan connection points around the circle perimeter
  function fanAngles(count: number, flipSign: boolean): number[] {
    if (count === 1) return [0]
    return Array.from({ length: count }, (_, i) => {
      const angle = 50 - (100 / (count - 1)) * i
      return flipSign ? -angle : angle
    })
  }

  const leftAngles = fanAngles(numThreats, false)
  const rightAngles = fanAngles(numCons, true)

  const leftConnects = leftAngles.map((a) => {
    const rad = ((180 + a) * Math.PI) / 180
    return { x: cx + TOP_EVENT_R * Math.cos(rad), y: cy + TOP_EVENT_R * Math.sin(rad) }
  })
  const rightConnects = rightAngles.map((a) => {
    const rad = (a * Math.PI) / 180
    return { x: cx + TOP_EVENT_R * Math.cos(rad), y: cy + TOP_EVENT_R * Math.sin(rad) }
  })

  // Group barriers by threat/consequence
  const prev = barriers.filter((b) => b.side === 'prevention')
  const mit = barriers.filter((b) => b.side === 'mitigation')

  const prevByThreat = new Map<string, BarrierInput[]>()
  for (const t of threats) prevByThreat.set(t.id, [])
  for (const b of prev) {
    if (b.threatId && prevByThreat.has(b.threatId)) {
      prevByThreat.get(b.threatId)!.push(b)
    } else {
      console.warn(`[BowtieSVG] Prevention barrier "${b.name}" (${b.id}) has no matching threatId "${b.threatId}" — skipped`)
    }
  }

  const mitByConsequence = new Map<string, BarrierInput[]>()
  for (const c of consequences) mitByConsequence.set(c.id, [])
  for (const b of mit) {
    if (b.consequenceId && mitByConsequence.has(b.consequenceId)) {
      mitByConsequence.get(b.consequenceId)!.push(b)
    } else {
      console.warn(`[BowtieSVG] Mitigation barrier "${b.name}" (${b.id}) has no matching consequenceId "${b.consequenceId}" — skipped`)
    }
  }

  // Barrier X positions within zones
  const threatX = PADDING
  const consX = CW - PADDING - CONS_W

  const prevZoneStart = threatX + THREAT_W + 30
  const prevZoneEnd = Math.min(
    prevZoneStart + (cx - TOP_EVENT_R - 80 - prevZoneStart) * 0.85,
    cx - TOP_EVENT_R - 80,
  )
  const mitZoneStart = cx + TOP_EVENT_R + 80
  const mitZoneEnd = Math.min(
    mitZoneStart + (consX - 30 - mitZoneStart) * 0.85,
    consX - 30,
  )

  function barrierXPositions(zoneStart: number, zoneEnd: number, count: number): number[] {
    const positions: number[] = []
    for (let k = 0; k < count; k++) {
      positions.push(
        zoneStart + ((zoneEnd - zoneStart) / (count + 1)) * (k + 1) - BARRIER_W / 2,
      )
    }
    return positions
  }

  const threatPositions = threats.map((t, i) => ({
    cy: threatCenterY(i),
    barrierXs: barrierXPositions(
      prevZoneStart,
      prevZoneEnd,
      prevByThreat.get(t.id)?.length ?? 0,
    ),
  }))

  const consPositions = consequences.map((c, j) => ({
    cy: consCenterY(j),
    barrierXs: barrierXPositions(
      mitZoneStart,
      mitZoneEnd,
      mitByConsequence.get(c.id)?.length ?? 0,
    ),
  }))

  return {
    CH,
    cx,
    cy,
    hazardX,
    hazardY,
    threatPositions,
    consPositions,
    leftConnects,
    rightConnects,
    prevByThreat,
    mitByConsequence,
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
  const layout = useMemo(
    () => computeLayout(threats, consequences, barriers),
    [threats, consequences, barriers],
  )

  const {
    CH,
    cx,
    cy,
    hazardX,
    hazardY,
    threatPositions,
    consPositions,
    leftConnects,
    rightConnects,
    prevByThreat,
    mitByConsequence,
  } = layout

  const threatX = PADDING
  const consX = CW - PADDING - CONS_W
  const hazardLabel = hazardName || 'Hazard'
  const topEventLines = wrapText(topEvent, 18, 4)

  // Highest risk level among barriers linked to a consequence
  function consRiskLevel(consId: string): string | null {
    const linked = mitByConsequence.get(consId)
    if (!linked) return null
    const levels = linked.map((b) => b.risk_level).filter(Boolean) as string[]
    if (levels.includes('High')) return 'High'
    if (levels.includes('Medium')) return 'Medium'
    if (levels.includes('Low')) return 'Low'
    return null
  }

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        overflow: 'auto',
        background: '#E8E8E8',
        position: 'relative',
      }}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox={`0 0 ${CW} ${CH}`}
        preserveAspectRatio="xMidYMid meet"
        style={{ display: 'block', width: '100%', height: '100%' }}
      >
        <defs>
          <radialGradient id="topEventGrad" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#FF8C00" />
            <stop offset="100%" stopColor="#CC2200" />
          </radialGradient>
          <radialGradient id="threatGrad" cx="50%" cy="50%" r="70%">
            <stop offset="0%" stopColor="#2979FF" />
            <stop offset="100%" stopColor="#0D47A1" />
          </radialGradient>
          <radialGradient id="consequenceGrad" cx="50%" cy="50%" r="70%">
            <stop offset="0%" stopColor="#FF1744" />
            <stop offset="100%" stopColor="#B71C1C" />
          </radialGradient>
          <pattern
            id="hazardStripe"
            width="14.14"
            height="14.14"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <rect width="7.07" height="14.14" fill="#FFD700" />
            <rect x="7.07" width="7.07" height="14.14" fill="#000" />
          </pattern>
          <style>{`text { font-family: Arial, Helvetica, sans-serif; dominant-baseline: central; text-anchor: middle; }`}</style>
        </defs>

        {/* Canvas background */}
        <rect x="0" y="0" width={CW} height={CH} fill="#E8E8E8" />

        {/* ============ PATHWAY LINES ============ */}

        {/* Prevention side */}
        {threatPositions.map((tp, i) => {
          if (tp.barrierXs.length === 0 && leftConnects[i]) {
            const lc = leftConnects[i]
            return (
              <path
                key={`prev-path-${i}`}
                d={`M ${threatX + THREAT_W + 14},${tp.cy} L ${lc.x},${lc.y}`}
                fill="none"
                stroke="#111"
                strokeWidth={1.5}
              />
            )
          }
          if (!leftConnects[i]) return null
          const lc = leftConnects[i]
          let d = `M ${threatX + THREAT_W + 14},${tp.cy}`
          for (const bx of tp.barrierXs) {
            d += ` L ${bx},${tp.cy} L ${bx + BARRIER_W},${tp.cy}`
          }
          d += ` L ${lc.x},${lc.y}`

          return <path key={`prev-path-${i}`} d={d} fill="none" stroke="#111" strokeWidth={1.5} />
        })}

        {/* Mitigation side */}
        {consPositions.map((cp, j) => {
          if (!rightConnects[j]) return null
          const rc = rightConnects[j]

          if (cp.barrierXs.length === 0) {
            return (
              <path
                key={`mit-path-${j}`}
                d={`M ${rc.x},${rc.y} L ${consX - 14},${cp.cy}`}
                fill="none"
                stroke="#111"
                strokeWidth={1.5}
              />
            )
          }

          let d = `M ${rc.x},${rc.y}`
          for (const bx of cp.barrierXs) {
            d += ` L ${bx},${cp.cy} L ${bx + BARRIER_W},${cp.cy}`
          }
          d += ` L ${consX - 14},${cp.cy}`

          return <path key={`mit-path-${j}`} d={d} fill="none" stroke="#111" strokeWidth={1.5} />
        })}

        {/* ============ TOP EVENT ============ */}
        <circle cx={cx} cy={cy} r={TOP_EVENT_R} fill="url(#topEventGrad)" />
        {/* Connector squares on left and right of circle */}
        <rect x={cx - TOP_EVENT_R - 4} y={cy - 4} width={8} height={8} fill="#fff" stroke="#333" strokeWidth={1.5} />
        <rect x={cx + TOP_EVENT_R - 4} y={cy - 4} width={8} height={8} fill="#fff" stroke="#333" strokeWidth={1.5} />
        {/* White inner rectangle */}
        <rect x={cx - 70} y={cy - 40} width={140} height={80} rx={4} fill="#fff" stroke="#333" strokeWidth={1.5} />
        {/* Top event text */}
        {topEventLines.map((line, i) => {
          const lineH = 18
          const startY = cy - ((topEventLines.length - 1) * lineH) / 2
          return (
            <text
              key={`te-${i}`}
              x={cx}
              y={startY + i * lineH}
              fontSize={13}
              fontWeight="bold"
              fill="#111"
            >
              {line}
            </text>
          )
        })}

        {/* ============ HAZARD ============ */}
        <line x1={cx} y1={hazardY + HAZARD_H} x2={cx} y2={cy - TOP_EVENT_R} stroke="#000" strokeWidth={1.5} />
        <rect x={hazardX} y={hazardY} width={HAZARD_W} height={HAZARD_H} rx={4} fill="url(#hazardStripe)" />
        <rect x={hazardX + 8} y={hazardY + 8} width={HAZARD_W - 16} height={HAZARD_H - 16} rx={2} fill="#fff" />
        <text x={cx} y={hazardY + HAZARD_H / 2} fontSize={12} fontWeight="bold" fill="#000">
          {hazardLabel}
        </text>

        {/* ============ THREAT BOXES ============ */}
        {threats.map((t, i) => {
          const tp = threatPositions[i]
          const ty = tp.cy - THREAT_H / 2
          const nameLines = wrapText(t.name, 14, 3)
          const textStartY = tp.cy - ((nameLines.length - 1) * 17) / 2
          return (
            <g key={`threat-${t.id}`}>
              <rect
                x={threatX}
                y={ty}
                width={THREAT_W}
                height={THREAT_H}
                rx={14}
                fill="url(#threatGrad)"
                stroke="#0A3880"
                strokeWidth={2}
              />
              {nameLines.map((line, li) => (
                <text
                  key={li}
                  x={threatX + THREAT_W / 2}
                  y={textStartY + li * 17}
                  fontSize={13}
                  fontWeight="bold"
                  fill="#fff"
                >
                  {line}
                </text>
              ))}
              {/* Gray connector tab on right edge */}
              <rect
                x={threatX + THREAT_W}
                y={tp.cy - 14}
                width={14}
                height={28}
                rx={5}
                fill="#555"
                stroke="#333"
                strokeWidth={1}
              />
            </g>
          )
        })}

        {/* ============ CONSEQUENCE BOXES ============ */}
        {consequences.map((c, j) => {
          const cp = consPositions[j]
          const cyPos = cp.cy - CONS_H / 2
          const nameLines = wrapText(c.name, 14, 3)
          const textStartY = cp.cy - ((nameLines.length - 1) * 17) / 2
          const rl = consRiskLevel(c.id)

          return (
            <g key={`cons-${c.id}`}>
              <rect
                x={consX}
                y={cyPos}
                width={CONS_W}
                height={CONS_H}
                rx={14}
                fill="url(#consequenceGrad)"
                stroke="#7f0000"
                strokeWidth={2}
              />
              {/* Gray connector tab on left edge */}
              <rect
                x={consX - 14}
                y={cp.cy - 14}
                width={14}
                height={28}
                rx={5}
                fill="#555"
                stroke="#333"
                strokeWidth={1}
              />
              {nameLines.map((line, li) => (
                <text
                  key={li}
                  x={consX + CONS_W / 2}
                  y={textStartY + li * 17}
                  fontSize={13}
                  fontWeight="bold"
                  fill="#fff"
                >
                  {line}
                </text>
              ))}
              {/* Risk badge — white pill with colored border + letter */}
              {rl && (() => {
                const badge = riskBadge(rl)
                const badgeX = consX + CONS_W - 6
                const badgeY = cyPos + CONS_H - 6
                return (
                  <>
                    <rect
                      x={badgeX - 11}
                      y={badgeY - 9}
                      width={22}
                      height={18}
                      rx={9}
                      fill="#fff"
                      stroke={badge.color}
                      strokeWidth={2}
                    />
                    <text
                      x={badgeX}
                      y={badgeY}
                      fontSize={11}
                      fontWeight="bold"
                      fill={badge.color}
                    >
                      {badge.letter}
                    </text>
                  </>
                )
              })()}
            </g>
          )
        })}

        {/* ============ PREVENTION BARRIERS ============ */}
        {threats.map((t, i) => {
          const tp = threatPositions[i]
          const bs = prevByThreat.get(t.id) ?? []
          return bs.map((b, k) => {
            const bx = tp.barrierXs[k]
            if (bx === undefined) return null
            const by = tp.cy - BARRIER_H / 2
            return renderBarrier(b, bx, by, tp.cy, selectedBarrierId, onBarrierClick)
          })
        })}

        {/* ============ MITIGATION BARRIERS ============ */}
        {consequences.map((c, j) => {
          const cp = consPositions[j]
          const bs = mitByConsequence.get(c.id) ?? []
          return bs.map((b, k) => {
            const bx = cp.barrierXs[k]
            if (bx === undefined) return null
            const by = cp.cy - BARRIER_H / 2
            return renderBarrier(b, bx, by, cp.cy, selectedBarrierId, onBarrierClick)
          })
        })}
      </svg>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Barrier rendering — extracted as helper to share between prevention/mitigation
// ---------------------------------------------------------------------------

function renderBarrier(
  b: BarrierInput,
  bx: number,
  by: number,
  rowCy: number,
  selectedBarrierId: string | null,
  onBarrierClick: (id: string) => void,
) {
  const isSelected = b.id === selectedBarrierId
  const riskColor = b.risk_level ? riskBadge(b.risk_level).color : '#333'
  const nameLines = wrapText(b.name, 13, 3)
  const textStartY = BARRIER_H / 2 - ((nameLines.length - 1) * 15) / 2

  return (
    <g
      key={`barrier-${b.id}`}
      transform={`translate(${bx}, ${by})`}
      style={{ cursor: 'pointer' }}
      onClick={() => onBarrierClick(b.id)}
    >
      {/* Selection highlight */}
      {isSelected && (
        <rect
          x={-3}
          y={-BARRIER_TAB_OVERHANG - 3}
          width={BARRIER_W + 6}
          height={BARRIER_H + BARRIER_TAB_OVERHANG * 2 + 6}
          fill="none"
          stroke="#2979FF"
          strokeWidth={3}
          rx={4}
        />
      )}
      {/* Barrier box */}
      <rect
        x={0}
        y={0}
        width={BARRIER_W}
        height={BARRIER_H}
        fill="#fff"
        stroke={isSelected ? '#2979FF' : riskColor}
        strokeWidth={isSelected ? 2.5 : (b.risk_level ? 2.5 : 1.5)}
      />
      {/* Top connector tabs */}
      <rect x={30} y={-BARRIER_TAB_OVERHANG} width={16} height={22} rx={4} fill="#444" stroke="#222" strokeWidth={1} />
      <rect x={80} y={-BARRIER_TAB_OVERHANG} width={16} height={22} rx={4} fill="#444" stroke="#222" strokeWidth={1} />
      {/* Bottom connector tab */}
      <rect x={57} y={BARRIER_H - BARRIER_TAB_OVERHANG} width={16} height={22} rx={4} fill="#444" stroke="#222" strokeWidth={1} />
      {/* Text */}
      {nameLines.map((line, li) => (
        <text
          key={li}
          x={BARRIER_W / 2}
          y={textStartY + li * 15}
          fontSize={11}
          fontWeight="bold"
          fill="#000"
        >
          {line}
        </text>
      ))}
    </g>
  )
}
