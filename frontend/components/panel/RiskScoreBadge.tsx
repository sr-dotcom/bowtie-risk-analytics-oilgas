'use client'

import type { RiskLevel } from '@/lib/types'

// ---------------------------------------------------------------------------
// Color mapping per UI-SPEC Color section
// ---------------------------------------------------------------------------

const levelColors: Record<string, string> = {
  red: 'bg-red-500 text-white',
  amber: 'bg-amber-400 text-gray-900',
  green: 'bg-green-500 text-white',
  unanalyzed: 'bg-gray-300 text-gray-600',
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

interface RiskScoreBadgeProps {
  probability: number
  riskLevel: RiskLevel
}

/**
 * Displays a color-coded H/M/L risk label with historical reliability subtitle.
 *
 * The probability prop is retained for backward compatibility (used by BarrierNode
 * and programmatic consumers) but is NOT rendered in the badge. The riskLevel prop
 * drives all display logic.
 */
export default function RiskScoreBadge({ probability, riskLevel }: RiskScoreBadgeProps) {
  const colorClass = levelColors[riskLevel] ?? levelColors.unanalyzed
  const levelConfig = RISK_LEVEL_LABELS[riskLevel] ?? RISK_LEVEL_LABELS.unanalyzed

  return (
    <div className="flex items-center gap-3 mb-3">
      <span
        className={`inline-flex items-center justify-center w-10 h-10 rounded-full text-sm font-bold ${colorClass}`}
      >
        {levelConfig.label}
      </span>
      <div>
        <p className="text-sm font-semibold">{levelConfig.subtitle}</p>
        <p className="text-xs text-gray-500">
          Historical reliability assessment
        </p>
      </div>
    </div>
  )
}
