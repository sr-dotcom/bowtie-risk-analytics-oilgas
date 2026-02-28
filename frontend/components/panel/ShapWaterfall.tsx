'use client'

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Cell,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import type { ShapValue } from '@/lib/types'

// ---------------------------------------------------------------------------
// Data transformation
// ---------------------------------------------------------------------------

export interface WaterfallEntry {
  feature: string
  offset: number
  value: number
  raw: number
  category: 'barrier' | 'incident_context' | 'separator'
}

/**
 * Transform raw SHAP values into waterfall chart data entries.
 *
 * Algorithm:
 * 1. Sort by absolute value descending (largest contributors first).
 * 2. Take top 10 features.
 * 3. Split into barrier-category first, then incident_context (SHAP-04).
 * 4. Compute floating bar offsets: positive values float right from running total,
 *    negative values float left (offset = running + value, bar width = |value|).
 *
 * @param shap - Raw SHAP values from the model response.
 * @param baseValue - Model base value (log-odds or probability offset).
 * @returns Waterfall entries with offset + value fields for Recharts stacked bar.
 */
export function buildWaterfallData(
  shap: ShapValue[],
  baseValue: number,
  displayNameMap?: Record<string, string>,
): WaterfallEntry[] {
  if (shap.length === 0) return []

  // Sort by absolute value descending, take top 10
  const sorted = [...shap].sort((a, b) => Math.abs(b.value) - Math.abs(a.value)).slice(0, 10)

  // Group: barrier features first, then incident_context (SHAP-04)
  const barrierFeatures = sorted.filter((s) => s.category === 'barrier')
  const contextFeatures = sorted.filter((s) => s.category === 'incident_context')
  const ordered = [...barrierFeatures, ...contextFeatures]

  let running = baseValue
  return ordered.map((s) => {
    // Positive: bar extends right from running total
    // Negative: bar extends left — offset = running + value (left edge), width = |value|
    const offset = s.value >= 0 ? running : running + s.value
    const entry: WaterfallEntry = {
      feature: displayNameMap?.[s.feature] ?? s.feature,
      offset,
      value: Math.abs(s.value),
      raw: s.value,
      category: s.category,
    }
    running += s.value
    return entry
  })
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface ShapWaterfallProps {
  shap: ShapValue[]
  baseValue: number
  featureDisplayNames?: Record<string, string>  // pif_fatigue -> "Operator Fatigue"
}

export default function ShapWaterfall({ shap, baseValue, featureDisplayNames }: ShapWaterfallProps) {
  const barrierData = buildWaterfallData(
    shap.filter((s) => s.category === 'barrier'),
    baseValue,
    featureDisplayNames,
  )

  // For incident_context, continue the running total from where barrier features left off
  const barrierRunningEnd =
    barrierData.length > 0
      ? barrierData[barrierData.length - 1].offset + barrierData[barrierData.length - 1].value * (barrierData[barrierData.length - 1].raw >= 0 ? 1 : -1)
      : baseValue

  const contextData = buildWaterfallData(
    shap.filter((s) => s.category === 'incident_context'),
    barrierRunningEnd,
    featureDisplayNames,
  )

  // Build full data array with separator if there are context features
  const hasContext = contextData.length > 0
  const data: WaterfallEntry[] = [
    ...barrierData,
    ...(hasContext
      ? [
          {
            feature: '— Degradation Factors —',
            offset: 0,
            value: 0,
            raw: 0,
            category: 'separator' as const,
          },
          ...contextData,
        ]
      : []),
  ]

  if (data.length === 0) {
    return (
      <div className="text-xs text-gray-400 italic py-2">No SHAP values available.</div>
    )
  }

  const chartHeight = Math.max(200, data.length * 36 + 60)

  return (
    <div className="mb-4">
      <h3 className="text-base font-semibold mb-2">Barrier Analysis Factors</h3>
      <p className="text-xs text-gray-500 mb-1">Base rate: {baseValue.toFixed(3)}</p>

      {/* Plain-English summary of top degradation factors (D-08) */}
      {contextData.length > 0 && (
        <p className="text-xs text-gray-600 mb-2" data-testid="degradation-summary">
          Primary degradation factors:{' '}
          {contextData
            .slice(0, 3)
            .map((d) => {
              const strength = d.value > 0.05 ? 'strong' : 'moderate'
              return `${d.feature} (${strength})`
            })
            .join(', ')}
        </p>
      )}

      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          layout="vertical"
          data={data}
          margin={{ top: 4, right: 16, bottom: 4, left: 0 }}
        >
          <XAxis
            type="number"
            tick={{ fontSize: 12 }}
            tickFormatter={(v: number) => v.toFixed(2)}
          />
          <YAxis
            type="category"
            dataKey="feature"
            width={140}
            tick={{ fontSize: 12 }}
          />
          <ReferenceLine x={0} stroke="#d1d5db" strokeDasharray="3 3" />
          <Tooltip
            formatter={(val, name) => {
              if (name === 'value' && typeof val === 'number') {
                return [val.toFixed(4), 'SHAP']
              }
              return ['', '']
            }}
          />
          {/* Transparent spacer bar — sets the floating start position */}
          <Bar dataKey="offset" stackId="a" fill="transparent" isAnimationActive={false} />
          {/* Colored value bar — red for risk-increasing, blue for risk-decreasing */}
          <Bar dataKey="value" stackId="a" isAnimationActive={false}>
            {data.map((entry, i) => {
              if (entry.category === 'separator') {
                return <Cell key={i} fill="transparent" />
              }
              return (
                <Cell
                  key={i}
                  fill={entry.raw >= 0 ? '#ef4444' : '#3b82f6'}
                />
              )
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {hasContext && (
        <p className="text-xs text-gray-400 mt-1 italic">
          Degradation factors from historical incident context
        </p>
      )}
    </div>
  )
}
