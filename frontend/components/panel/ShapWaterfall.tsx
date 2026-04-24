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
import type { ShapValue, CascadingShapValue } from '@/lib/types'
import { getFeatureDisplayName } from '@/lib/shap-config'

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
  shap?: ShapValue[]
  baseValue?: number
  featureDisplayNames?: Record<string, string>  // pif_fatigue -> "Operator Fatigue"
  hiddenFeatures?: Set<string>  // Feature names to exclude from the chart
  cascadingShap?: CascadingShapValue[]  // cascading mode: use display_name, treat all as 'barrier'
}

export default function ShapWaterfall({ shap, baseValue = 0, featureDisplayNames, hiddenFeatures, cascadingShap }: ShapWaterfallProps) {
  // Cascading mode: convert CascadingShapValue[] → ShapValue[] treating all as 'barrier'
  if (cascadingShap && cascadingShap.length > 0) {
    const converted: ShapValue[] = cascadingShap.map((s) => ({
      feature: s.feature,
      value: s.value,
      category: 'barrier' as const,
    }))
    const displayNames: Record<string, string> = {}
    for (const s of cascadingShap) {
      // display_name from the API defaults to "" — fall back to the shap-config lookup
      displayNames[s.feature] = s.display_name || getFeatureDisplayName(s.feature)
    }
    const data = buildWaterfallData(converted, 0, displayNames)
    if (data.length === 0) {
      return <div className="text-xs text-[#6B7280] italic py-2">No SHAP values available.</div>
    }
    const chartHeight = Math.max(160, data.length * 36 + 60)
    return (
      <div className="mb-4">
        <h3 className="text-base font-semibold mb-2 text-[#E8E8E8]">Cascade Risk Factors</h3>
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart layout="vertical" data={data} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
            <XAxis type="number" tick={{ fontSize: 12, fill: '#9CA3AF' }} tickFormatter={(v: number) => v.toFixed(2)} stroke="#2A3442" />
            <YAxis type="category" dataKey="feature" width={185} tick={{ fontSize: 12, fill: '#9CA3AF' }} stroke="#2A3442" />
            <ReferenceLine x={0} stroke="#2A3442" strokeDasharray="3 3" />
            <Tooltip contentStyle={{ backgroundColor: '#151B24', border: '1px solid #2A3442', borderRadius: '6px' }} labelStyle={{ color: '#E8E8E8' }} itemStyle={{ color: '#9CA3AF' }} formatter={(val, name) => name === 'value' && typeof val === 'number' ? [val.toFixed(4), 'SHAP'] : ['', '']} />
            <Bar dataKey="offset" stackId="a" fill="transparent" isAnimationActive={false} />
            <Bar dataKey="value" stackId="a" isAnimationActive={false}>
              {data.map((entry, i) => <Cell key={i} fill={entry.raw >= 0 ? '#ef4444' : '#3b82f6'} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    )
  }

  const resolvedShap = shap ?? []
  const visible = hiddenFeatures
    ? resolvedShap.filter((s) => !hiddenFeatures.has(s.feature))
    : resolvedShap

  const barrierData = buildWaterfallData(
    visible.filter((s) => s.category === 'barrier'),
    baseValue,
    featureDisplayNames,
  )

  // For incident_context, continue the running total from where barrier features left off
  const barrierRunningEnd =
    barrierData.length > 0
      ? barrierData[barrierData.length - 1].offset + barrierData[barrierData.length - 1].value * (barrierData[barrierData.length - 1].raw >= 0 ? 1 : -1)
      : baseValue

  const contextData = buildWaterfallData(
    visible.filter((s) => s.category === 'incident_context'),
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
      <div className="text-xs text-[#6B7280] italic py-2">No SHAP values available.</div>
    )
  }

  const chartHeight = Math.max(200, data.length * 36 + 60)

  return (
    <div className="mb-4">
      <h3 className="text-base font-semibold mb-2 text-[#E8E8E8]">Barrier Analysis Factors</h3>
      <p className="text-xs text-[#9CA3AF] mb-1">Base rate: {baseValue.toFixed(3)}</p>

      {/* Plain-English summary of top degradation factors (D-08) */}
      {contextData.length > 0 && (
        <p className="text-xs text-[#9CA3AF] mb-2" data-testid="degradation-summary">
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
            tick={{ fontSize: 12, fill: '#9CA3AF' }}
            tickFormatter={(v: number) => v.toFixed(2)}
            stroke="#2A3442"
          />
          <YAxis
            type="category"
            dataKey="feature"
            width={185}
            tick={{ fontSize: 12, fill: '#9CA3AF' }}
            stroke="#2A3442"
          />
          <ReferenceLine x={0} stroke="#2A3442" strokeDasharray="3 3" />
          <Tooltip
            contentStyle={{ backgroundColor: '#151B24', border: '1px solid #2A3442', borderRadius: '6px' }}
            labelStyle={{ color: '#E8E8E8' }}
            itemStyle={{ color: '#9CA3AF' }}
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
        <p className="text-xs text-[#6B7280] mt-1 italic">
          Degradation factors from historical incident context
        </p>
      )}
    </div>
  )
}
