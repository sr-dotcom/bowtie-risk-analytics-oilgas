'use client'

import { BarChart, Bar, XAxis, YAxis, Cell, Tooltip, ResponsiveContainer, LabelList } from 'recharts'
import { CHART_COLORS } from '@/lib/chart-colors'
import type { Barrier } from '@/lib/types'

// ---------------------------------------------------------------------------
// Types & data transformation
// ---------------------------------------------------------------------------

export interface RiskCounts {
  high: number
  medium: number
  low: number
}

/**
 * Count barriers by risk level bucket.
 * Barriers with riskLevel 'unanalyzed' are excluded from counts.
 *
 * @param barriers - Array of Barrier objects from BowtieContext.
 * @returns RiskCounts with high/medium/low tallies.
 */
export function buildRiskDistribution(barriers: Barrier[]): RiskCounts {
  const counts: RiskCounts = { high: 0, medium: 0, low: 0 }
  for (const b of barriers) {
    if (b.riskLevel === 'red') counts.high++
    else if (b.riskLevel === 'amber') counts.medium++
    else if (b.riskLevel === 'green') counts.low++
    // 'unanalyzed' is intentionally excluded
  }
  return counts
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface RiskDistributionChartProps {
  counts: RiskCounts
}

export default function RiskDistributionChart({ counts }: RiskDistributionChartProps) {
  const data = [
    { name: 'High', count: counts.high, fill: CHART_COLORS.riskHigh },
    { name: 'Medium', count: counts.medium, fill: CHART_COLORS.riskMedium },
    { name: 'Low', count: counts.low, fill: CHART_COLORS.riskLow },
  ]

  return (
    <div data-testid="risk-distribution-chart">
      <h3 className="text-base font-semibold mb-3 text-[#E8E8E8]">Barrier Risk Distribution</h3>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart
          layout="vertical"
          data={data}
          margin={{ top: 4, right: 24, bottom: 4, left: 0 }}
        >
          <XAxis
            type="number"
            allowDecimals={false}
            tick={{ fontSize: 12, fill: '#9CA3AF' }}
            stroke="#2A3442"
          />
          <YAxis
            type="category"
            dataKey="name"
            width={60}
            tick={{ fontSize: 12, fill: '#9CA3AF' }}
            stroke="#2A3442"
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#151B24',
              border: '1px solid #2A3442',
              borderRadius: '6px',
            }}
            labelStyle={{ color: '#E8E8E8' }}
            itemStyle={{ color: '#9CA3AF' }}
            formatter={(val, name) => {
              if (name === 'count' && typeof val === 'number') {
                return [val, 'Barriers']
              }
              return ['', '']
            }}
          />
          <Bar dataKey="count" isAnimationActive={false}>
            <LabelList
              dataKey="count"
              position="right"
              style={{ fontSize: 11, fill: '#9CA3AF' }}
            />
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
