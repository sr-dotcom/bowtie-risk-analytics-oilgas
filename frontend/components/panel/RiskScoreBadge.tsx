'use client'

import type React from 'react'
import type { RiskLevel, RiskBand } from '@/lib/types'

// ---------------------------------------------------------------------------
// Color mapping — bg.accent + border + risk.*Text per UI-CONTEXT §6
// ---------------------------------------------------------------------------

const LEVEL_STYLES: Record<string, React.CSSProperties> = {
  red:        { backgroundColor: '#1A2332', color: '#E74C3C', borderColor: '#C0392B' },
  amber:      { backgroundColor: '#1A2332', color: '#D68910', borderColor: '#996515' },
  green:      { backgroundColor: '#1A2332', color: '#27AE60', borderColor: '#1F6F43' },
  unanalyzed: { backgroundColor: '#151B24', color: '#6B7280', borderColor: '#2A3442' },
}

// ---------------------------------------------------------------------------
// H/M/L label mapping (D-07, Fidel-#34, Fidel-#30)
// ---------------------------------------------------------------------------

const RISK_LEVEL_LABELS: Record<string, { label: string; subtitle: string }> = {
  red:        { label: 'High',   subtitle: 'High reliability concern' },
  amber:      { label: 'Medium', subtitle: 'Moderate reliability concern' },
  green:      { label: 'Low',    subtitle: 'Low reliability concern' },
  unanalyzed: { label: '\u2014', subtitle: 'Not yet assessed' },
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const RISK_BAND_TO_LEVEL: Record<RiskBand, RiskLevel> = {
  HIGH: 'red',
  MEDIUM: 'amber',
  LOW: 'green',
}

interface RiskScoreBadgeProps {
  probability: number
  riskLevel?: RiskLevel
  riskBand?: RiskBand  // cascading mode: maps HIGH/MEDIUM/LOW → riskLevel
}

/**
 * Displays a color-coded H/M/L risk label with historical reliability subtitle.
 *
 * The probability prop is retained for backward compatibility (used by BarrierNode
 * and programmatic consumers) but is NOT rendered in the badge. The riskLevel prop
 * drives all display logic.
 */
export default function RiskScoreBadge({ probability, riskLevel, riskBand }: RiskScoreBadgeProps) {
  const resolvedLevel: RiskLevel = riskBand ? RISK_BAND_TO_LEVEL[riskBand] : (riskLevel ?? 'unanalyzed')
  const levelStyle = LEVEL_STYLES[resolvedLevel] ?? LEVEL_STYLES.unanalyzed
  const levelConfig = RISK_LEVEL_LABELS[resolvedLevel] ?? RISK_LEVEL_LABELS.unanalyzed

  return (
    <div className="flex items-center gap-3 mb-3">
      <span
        className="inline-flex items-center justify-center w-10 h-10 rounded-full text-sm font-bold border-2"
        style={levelStyle}
      >
        {levelConfig.label}
      </span>
      <div>
        <p className="text-sm font-semibold text-[#E8E8E8]">{levelConfig.subtitle}</p>
        <p className="text-xs text-[#9CA3AF]">
          Historical reliability assessment
        </p>
      </div>
    </div>
  )
}
