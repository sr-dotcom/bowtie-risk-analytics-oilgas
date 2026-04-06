'use client'

import { BarChart, Bar, XAxis, YAxis, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import { useBowtieContext } from '@/context/BowtieContext'
import { CHART_COLORS } from '@/lib/chart-colors'
import { PIF_DISPLAY_NAMES } from '@/lib/types'
import type { PredictResponse } from '@/lib/types'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Incident-level features that are non-actionable — excluded from global SHAP chart.
 *  Matches SHAP_HIDDEN_FEATURES in TopAtRiskBarriers.tsx and DetailPanel.tsx. */
const SHAP_HIDDEN_FEATURES = new Set(['source_agency', 'primary_threat_category'])

/** Display names for all SHAP features: barrier-category + PIF + incident context. */
const FEATURE_DISPLAY_NAMES: Record<string, string> = {
  // Barrier-category features
  source_agency: 'Data Source',
  barrier_family: 'Barrier Family',
  side: 'Pathway Position',
  barrier_type: 'Barrier Type',
  line_of_defense: 'Line of Defense',
  supporting_text_count: 'Evidence Volume',
  // Numeric incident features
  pathway_sequence: 'Pathway Sequence',
  upstream_failure_rate: 'Upstream Failure Rate',
  // Incident-context feature (in hidden set but included for completeness)
  top_event_category: 'Top Event Category',
  // PIF features (from lib/types.ts PIF_DISPLAY_NAMES)
  ...(PIF_DISPLAY_NAMES as Record<string, string>),
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface GlobalShapEntry {
  feature: string
  meanAbsShap: number
  category: 'barrier' | 'incident_context'
}

// ---------------------------------------------------------------------------
// Pure aggregation function
// ---------------------------------------------------------------------------

/**
 * Compute mean |SHAP| per feature across all predictions.
 *
 * @param predictions - Map of barrierId → PredictResponse from BowtieContext.
 * @returns Array of GlobalShapEntry sorted descending by meanAbsShap.
 */
export function buildGlobalShapData(
  predictions: Record<string, PredictResponse>,
): GlobalShapEntry[] {
  const values = Object.values(predictions)
  if (values.length === 0) return []

  const sums: Record<string, number> = {}
  const counts: Record<string, number> = {}
  const categories: Record<string, 'barrier' | 'incident_context'> = {}

  for (const pred of values) {
    for (const shap of pred.model1_shap ?? []) {
      if (SHAP_HIDDEN_FEATURES.has(shap.feature)) continue

      const abs = Math.abs(shap.value)
      sums[shap.feature] = (sums[shap.feature] ?? 0) + abs
      counts[shap.feature] = (counts[shap.feature] ?? 0) + 1
      if (categories[shap.feature] === undefined) {
        categories[shap.feature] = shap.category
      }
    }
  }

  const entries: GlobalShapEntry[] = Object.keys(sums).map((feat) => ({
    feature: FEATURE_DISPLAY_NAMES[feat] ?? feat,
    meanAbsShap: sums[feat] / counts[feat],
    category: categories[feat],
  }))

  return entries.sort((a, b) => b.meanAbsShap - a.meanAbsShap)
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function GlobalShapChart() {
  const { predictions } = useBowtieContext()
  const data = buildGlobalShapData(predictions)

  return (
    <div data-testid="global-shap-chart">
      <h3 className="text-base font-semibold mb-3 text-[#E8ECF4]">Global Feature Importance</h3>

      {data.length === 0 ? (
        <p className="text-sm text-[#5A6178]">
          Run Analyze Barriers to see feature importance
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={Math.max(200, data.length * 32 + 60)}>
          <BarChart
            layout="vertical"
            data={data}
            margin={{ top: 4, right: 24, bottom: 4, left: 0 }}
          >
            <XAxis
              type="number"
              tickFormatter={(v) => (v as number).toFixed(3)}
              tick={{ fontSize: 12, fill: '#8B93A8' }}
              stroke="#2E3348"
            />
            <YAxis
              type="category"
              dataKey="feature"
              width={160}
              tick={{ fontSize: 12, fill: '#8B93A8' }}
              stroke="#2E3348"
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1A1D27',
                border: '1px solid #2E3348',
                borderRadius: '6px',
              }}
              labelStyle={{ color: '#E8ECF4' }}
              itemStyle={{ color: '#8B93A8' }}
              formatter={(val, name) => {
                if (name === 'meanAbsShap' && typeof val === 'number') {
                  return [val.toFixed(4), 'Mean |SHAP|']
                }
                return ['', '']
              }}
            />
            <Bar dataKey="meanAbsShap" isAnimationActive={false}>
              {data.map((entry, i) => (
                <Cell
                  key={i}
                  fill={entry.category === 'barrier' ? CHART_COLORS.cat1 : CHART_COLORS.cat2}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
