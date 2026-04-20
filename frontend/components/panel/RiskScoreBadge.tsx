'use client'

import type { RiskLevel, RiskBand } from '@/lib/types'

// ---------------------------------------------------------------------------
// Color mapping per UI-SPEC Color section
// ---------------------------------------------------------------------------

const levelColors: Record<string, string> = {
  red: 'bg-red-500 text-white',
  amber: 'bg-amber-400 text-gray-900',
  green: 'bg-green-500 text-white',
  unanalyzed: 'bg-[#242836] text-[#5A6178]',
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
  const colorClass = levelColors[resolvedLevel] ?? levelColors.unanalyzed
  const levelConfig = RISK_LEVEL_LABELS[resolvedLevel] ?? RISK_LEVEL_LABELS.unanalyzed

  return (
    <div className="flex items-center gap-3 mb-3">
      <span
        className={`inline-flex items-center justify-center w-10 h-10 rounded-full text-sm font-bold ${colorClass}`}
      >
        {levelConfig.label}
      </span>
      <div>
        <p className="text-sm font-semibold text-[#E8ECF4]">{levelConfig.subtitle}</p>
        <p className="text-xs text-[#8B93A8]">
          Historical reliability assessment
        </p>
      </div>
    </div>
  )
}
