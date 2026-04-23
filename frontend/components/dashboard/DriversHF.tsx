'use client'

import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Cell, Tooltip, ResponsiveContainer, LabelList } from 'recharts'
import { useBowtieContext } from '@/context/BowtieContext'
import { CHART_COLORS } from '@/lib/chart-colors'
import { SHAP_HIDDEN_FEATURES, FEATURE_DISPLAY_NAMES } from '@/lib/shap-config'
import { PIF_DISPLAY_NAMES } from '@/lib/types'
import type { AprioriRule, DegradationContext, PifFlags, PredictResponse } from '@/lib/types'
import { fetchAprioriRules } from '@/lib/api'
import { formatBarrierFamily } from '@/lib/format'

// ---------------------------------------------------------------------------
// Constants (imported from @/lib/shap-config — single source of truth)
// ---------------------------------------------------------------------------

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
      <h3 className="text-base font-semibold mb-3 text-[#E8E8E8]">Global Feature Importance</h3>

      {data.length === 0 ? (
        <p className="text-sm text-[#6B7280]">
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
              tick={{ fontSize: 12, fill: '#9CA3AF' }}
              stroke="#2A3442"
            />
            <YAxis
              type="category"
              dataKey="feature"
              width={160}
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
                if (name === 'meanAbsShap' && typeof val === 'number') {
                  return [val.toFixed(4), 'Mean |SHAP|']
                }
                return ['', '']
              }}
            />
            <Bar dataKey="meanAbsShap" isAnimationActive={false}>
              <LabelList
                dataKey="meanAbsShap"
                position="right"
                formatter={(v: unknown) => typeof v === 'number' ? v.toFixed(3) : String(v ?? '')}
                style={{ fontSize: 10, fill: '#9CA3AF' }}
              />
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

// ---------------------------------------------------------------------------
// PIF Prevalence Chart
// ---------------------------------------------------------------------------

/** Maps each PIF key to its human-factors category. */
export const PIF_CATEGORY: Record<keyof PifFlags, 'People' | 'Work' | 'Organisation'> = {
  pif_competence: 'People',
  pif_communication: 'People',
  pif_situational_awareness: 'People',
  pif_supervision: 'People',
  pif_training: 'People',
  pif_procedures: 'Work',
  pif_tools_equipment: 'Work',
  pif_safety_culture: 'Organisation',
  pif_management_of_change: 'Organisation',
}

/** Bar fill colors per HF category. */
export const CATEGORY_COLORS: Record<'People' | 'Work' | 'Organisation', string> = {
  People: CHART_COLORS.cat3,        // #F5B740 amber
  Work: CHART_COLORS.cat5,          // #F97316 orange
  Organisation: CHART_COLORS.cat4,  // #8B5CF6 purple
}

export interface PifPrevalenceEntry {
  feature: string
  featureKey: string
  prevalence: number
  category: 'People' | 'Work' | 'Organisation'
}

/**
 * Compute how often each PIF is a top-3 SHAP driver (by |value|) across all
 * predictions. Returns all 9 PIF keys, sorted descending by prevalence.
 *
 * @param predictions - Map of barrierId → PredictResponse from BowtieContext.
 */
export function buildPifPrevalenceData(
  predictions: Record<string, PredictResponse>,
): PifPrevalenceEntry[] {
  const values = Object.values(predictions)
  if (values.length === 0) return []

  const counts: Partial<Record<keyof PifFlags, number>> = {}

  for (const pred of values) {
    // Sort all SHAP entries by |value| descending and take the top 3
    const top3 = [...(pred.model1_shap ?? [])]
      .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
      .slice(0, 3)

    for (const entry of top3) {
      if (entry.feature.startsWith('pif_') && entry.feature in PIF_CATEGORY) {
        const key = entry.feature as keyof PifFlags
        counts[key] = (counts[key] ?? 0) + 1
      }
    }
  }

  const total = values.length
  const pifKeys = Object.keys(PIF_DISPLAY_NAMES) as Array<keyof PifFlags>

  const result: PifPrevalenceEntry[] = pifKeys.map((key) => ({
    feature: PIF_DISPLAY_NAMES[key],
    featureKey: key,
    prevalence: (counts[key] ?? 0) / total,
    category: PIF_CATEGORY[key],
  }))

  return result.sort((a, b) => b.prevalence - a.prevalence)
}

/** Horizontal bar chart showing PIF prevalence in top-3 SHAP drivers. */
export function PifPrevalenceChart() {
  const { predictions } = useBowtieContext()
  const data = buildPifPrevalenceData(predictions)

  return (
    <div data-testid="pif-prevalence-chart">
      <h3 className="text-base font-semibold mb-3 text-[#E8E8E8]">PIF Prevalence in Top Drivers</h3>

      {data.length === 0 ? (
        <p className="text-sm text-[#6B7280]">
          Run Analyze Barriers to see PIF prevalence
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
              domain={[0, 1]}
              tickFormatter={(v) => `${((v as number) * 100).toFixed(0)}%`}
              tick={{ fontSize: 12, fill: '#9CA3AF' }}
              stroke="#2A3442"
            />
            <YAxis
              type="category"
              dataKey="feature"
              width={160}
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
                if (name === 'prevalence' && typeof val === 'number') {
                  return [`${(val * 100).toFixed(1)}%`, 'Prevalence']
                }
                return ['', '']
              }}
            />
            <Bar dataKey="prevalence" isAnimationActive={false}>
              <LabelList
                dataKey="prevalence"
                position="right"
                formatter={(v: unknown) => typeof v === 'number' ? `${(v * 100).toFixed(0)}%` : String(v ?? '')}
                style={{ fontSize: 10, fill: '#9CA3AF' }}
              />
              {data.map((entry, i) => (
                <Cell
                  key={i}
                  fill={CATEGORY_COLORS[entry.category]}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Degradation Context Panel (S05a/T05 — D016 Branch C)
// Replaces the PIF Prevalence section when a drill-down explanation is
// available from useExplainCascading. Falls back to PifPrevalenceChart
// when no barrier is selected.
// ---------------------------------------------------------------------------

/**
 * Shows pif_mentions + recommendations from the current drill-down explanation.
 * Renders the old PifPrevalenceChart as fallback when no explanation is loaded.
 */
export function DegradationContextPanel() {
  const { explanation, selectedTargetBarrierId, scenario } = useBowtieContext()

  const targetName = selectedTargetBarrierId && scenario
    ? (scenario.barriers.find((b) => b.control_id === selectedTargetBarrierId)?.name
        ?? selectedTargetBarrierId)
    : null

  if (!explanation) {
    if (selectedTargetBarrierId) {
      return (
        <div data-testid="degradation-context-panel">
          <h3 className="text-base font-semibold mb-3 text-[#E8E8E8]">
            Degradation Context (from similar incidents)
          </h3>
          <p className="text-sm text-[#6B7280] animate-pulse">Loading degradation context…</p>
        </div>
      )
    }
    return (
      <div data-testid="degradation-context-panel">
        <h3 className="text-base font-semibold mb-3 text-[#E8E8E8]">
          Degradation Context (from similar incidents)
        </h3>
        <p className="text-sm text-[#6B7280]">Select a barrier to see degradation context.</p>
      </div>
    )
  }

  const { pif_mentions, recommendations, barrier_condition } = explanation.degradation_context

  return (
    <div data-testid="degradation-context-panel">
      <h3 className="text-base font-semibold mb-3 text-[#E8E8E8]">
        Degradation Context (from similar incidents)
      </h3>
      {targetName && (
        <p className="text-xs text-[#9CA3AF] mb-3">
          Target barrier: <span className="text-[#E8E8E8] font-medium">{targetName}</span>
          {' '}— condition: <span style={{ color: '#D68910' }}>{barrier_condition}</span>
        </p>
      )}

      {pif_mentions.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-medium text-[#6B7280] mb-2 uppercase tracking-wider">
            Performance-Influencing Factors
          </p>
          <div className="flex flex-wrap gap-2">
            {pif_mentions.map((pif, i) => (
              <span
                key={i}
                className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30"
              >
                {pif}
              </span>
            ))}
          </div>
        </div>
      )}

      {recommendations.length > 0 && (
        <div>
          <p className="text-xs font-medium text-[#6B7280] mb-2 uppercase tracking-wider">
            Recommendations
          </p>
          <div className="space-y-1.5">
            {recommendations.map((rec, i) => (
              <div
                key={i}
                className="bg-[#1C2430] border-l-2 border-blue-500 rounded-md px-3 py-2 text-xs text-[#9CA3AF]"
              >
                {rec}
              </div>
            ))}
          </div>
        </div>
      )}

      {pif_mentions.length === 0 && recommendations.length === 0 && (
        <p className="text-sm text-[#6B7280]">No degradation context available for this barrier.</p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Apriori Co-failure Rules Table
// ---------------------------------------------------------------------------

export type SortKey = 'confidence' | 'support' | 'lift'
export type SortDir = 'asc' | 'desc'

/**
 * Sort a copy of `rules` by `key` in direction `dir`.
 * Pure function — does not mutate the input array.
 */
export function sortRules(rules: AprioriRule[], key: SortKey, dir: SortDir): AprioriRule[] {
  return [...rules].sort((a, b) => dir === 'desc' ? b[key] - a[key] : a[key] - b[key])
}

/**
 * Table of Apriori co-failure association rules with client-side sorting.
 * Data is fetched independently via fetchAprioriRules (no BowtieContext dependency).
 * S04 will compose this component into the Drivers & HF tab.
 */
export function AprioriRulesTable() {
  const [rules, setRules] = useState<AprioriRule[]>([])
  const [nIncidents, setNIncidents] = useState<number>(0)
  const [generatedAt, setGeneratedAt] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('confidence')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  useEffect(() => {
    let cancelled = false
    fetchAprioriRules()
      .then((data) => {
        if (!cancelled) {
          setRules(data.rules)
          setNIncidents(data.n_incidents)
          setGeneratedAt(data.generated_at)
          setLoading(false)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err))
          setLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [])

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  if (loading) return (
    <div data-testid="apriori-rules-table" className="bg-[#151B24] rounded-lg p-4">
      <p className="text-sm text-[#9CA3AF] animate-pulse">Loading co-failure rules...</p>
    </div>
  )
  if (error) return (
    <div className="bg-[#151B24] rounded-lg p-4">
      <span className="text-sm" style={{ color: '#E74C3C' }}>Error: {error}</span>
    </div>
  )

  const sorted = sortRules(rules, sortKey, sortDir)

  const headerClass = 'cursor-pointer select-none px-3 py-2 text-left text-xs font-semibold text-[#9CA3AF] uppercase tracking-wider hover:text-[#E8E8E8] transition-colors'
  const cellClass = 'px-3 py-2 text-sm text-[#E8E8E8]'
  const dimCellClass = 'px-3 py-2 text-sm text-[#9CA3AF]'

  return (
    <div data-testid="apriori-rules-table" className="bg-[#151B24] rounded-lg overflow-hidden">
      <div className="px-4 pt-3 pb-2">
        <h3 className="text-base font-semibold mb-1 text-[#E8E8E8]">
          Co-failure Association Rules
        </h3>
        <p className="text-sm text-[#6B7280]">
          When the antecedent barrier family fails in an incident, the consequent barrier family
          also fails with the shown confidence. Based on Apriori analysis of {nIncidents} incident
          investigations{generatedAt ? ` (generated ${new Date(generatedAt).toLocaleDateString()})` : ''}.

        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="border-b border-[#2A3442]">
            <tr>
              <th className={headerClass}>Antecedent</th>
              <th className={headerClass}>Consequent</th>
              <th
                className={`${headerClass}${sortKey === 'confidence' ? ' text-[#E8E8E8]' : ''}`}
                onClick={() => handleSort('confidence')}
              >
                Confidence {sortKey === 'confidence' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
              </th>
              <th
                className={`${headerClass}${sortKey === 'support' ? ' text-[#E8E8E8]' : ''}`}
                onClick={() => handleSort('support')}
              >
                Support {sortKey === 'support' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
              </th>
              <th
                className={`${headerClass}${sortKey === 'lift' ? ' text-[#E8E8E8]' : ''}`}
                onClick={() => handleSort('lift')}
              >
                Lift {sortKey === 'lift' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
              </th>
              <th className={headerClass}>Count</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((rule, i) => (
              <tr key={`${rule.antecedent}-${rule.consequent}`} className="border-b border-[#2A3442] hover:bg-[#2A3442] transition-colors">
                <td className={cellClass}>{formatBarrierFamily(rule.antecedent)}</td>
                <td className={cellClass}>{formatBarrierFamily(rule.consequent)}</td>
                <td className={dimCellClass}>{(rule.confidence * 100).toFixed(1)}%</td>
                <td className={dimCellClass}>{(rule.support * 100).toFixed(1)}%</td>
                <td className={dimCellClass}>{rule.lift.toFixed(2)}</td>
                <td className={dimCellClass}>{rule.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
