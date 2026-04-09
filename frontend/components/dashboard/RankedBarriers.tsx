'use client'

import { useState, useEffect, Fragment } from 'react'
import { useBowtieContext } from '@/context/BowtieContext'
import { SHAP_HIDDEN_FEATURES, FEATURE_DISPLAY_NAMES } from './TopAtRiskBarriers'
import RiskScoreBadge from '@/components/panel/RiskScoreBadge'
import ShapWaterfall from '@/components/panel/ShapWaterfall'
import EvidenceSection from '@/components/panel/EvidenceSection'
import type { Barrier, PredictResponse, RiskLevel } from '@/lib/types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface RankedRow {
  rank: number
  barrierId: string
  name: string
  riskLevel: RiskLevel
  probability: number
  condition: string
  topFactor: string
  topFactorValue: number | null
  barrierType: string
  lod: string
  side: string
}

type SortDir = 'asc' | 'desc'

// ---------------------------------------------------------------------------
// Risk level pill color mapping (small inline badge)
// ---------------------------------------------------------------------------

const PILL_COLORS: Record<RiskLevel, string> = {
  red: 'bg-red-500 text-white',
  amber: 'bg-amber-400 text-gray-900',
  green: 'bg-green-500 text-white',
  unanalyzed: 'bg-[#2E3348] text-[#5A6178]',
}

const PILL_LABELS: Record<RiskLevel, string> = {
  red: 'High',
  amber: 'Medium',
  green: 'Low',
  unanalyzed: '—',
}

// ---------------------------------------------------------------------------
// Pure function
// ---------------------------------------------------------------------------

/**
 * Build all analyzed barrier rows, ranked by failure probability, then sorted
 * by the given key/direction.
 *
 * @param barriers    - All barriers from BowtieContext.
 * @param predictions - Map of barrierId → PredictResponse from BowtieContext.
 * @param sortKey     - Column key to sort by.
 * @param sortDir     - Sort direction ('asc' | 'desc').
 * @returns Sorted array of RankedRow.
 */
export function buildRankedRows(
  barriers: Barrier[],
  predictions: Record<string, PredictResponse>,
  sortKey: keyof RankedRow,
  sortDir: SortDir,
): RankedRow[] {
  // Filter to only analyzed barriers
  const analyzed = barriers.filter((b) => predictions[b.id] !== undefined)

  // Sort descending by model1_probability to assign stable rank
  const byProbability = [...analyzed].sort(
    (a, b) => predictions[b.id].model1_probability - predictions[a.id].model1_probability,
  )

  // Build rows with rank assigned from probability-sorted order
  const rows: RankedRow[] = byProbability.map((barrier, idx) => {
    const pred = predictions[barrier.id]
    const probability = pred.model1_probability

    // Find top SHAP factor: exclude hidden features, sort by |value| desc, take first
    const visibleShap = (pred.model1_shap ?? []).filter(
      (s) => !SHAP_HIDDEN_FEATURES.has(s.feature),
    )
    const sortedShap = [...visibleShap].sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    const topShap = sortedShap.length > 0 ? sortedShap[0] : null

    const topFactor = topShap
      ? (FEATURE_DISPLAY_NAMES[topShap.feature] ?? topShap.feature)
      : '—'
    const topFactorValue = topShap ? topShap.value : null

    return {
      rank: idx + 1,
      barrierId: barrier.id,
      name: barrier.name,
      riskLevel: barrier.riskLevel,
      probability,
      condition: pred.barrier_condition_display || PILL_LABELS[barrier.riskLevel] || '—',
      topFactor,
      topFactorValue,
      barrierType: pred.barrier_type_display ?? barrier.barrier_type,
      lod: pred.lod_display ?? barrier.line_of_defense,
      side: barrier.side,
    }
  })

  // Re-sort by the requested key/direction
  return [...rows].sort((a, b) => {
    const aVal = a[sortKey]
    const bVal = b[sortKey]

    if (aVal === null && bVal === null) return 0
    if (aVal === null) return sortDir === 'asc' ? 1 : -1
    if (bVal === null) return sortDir === 'asc' ? -1 : 1

    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return sortDir === 'asc' ? aVal - bVal : bVal - aVal
    }

    const aStr = String(aVal).toLowerCase()
    const bStr = String(bVal).toLowerCase()
    if (aStr < bStr) return sortDir === 'asc' ? -1 : 1
    if (aStr > bStr) return sortDir === 'asc' ? 1 : -1
    return 0
  })
}

// ---------------------------------------------------------------------------
// Column definitions
// ---------------------------------------------------------------------------

interface Column {
  key: keyof RankedRow
  label: string
  className?: string
}

const COLUMNS: Column[] = [
  { key: 'rank', label: '#', className: 'w-10 text-center' },
  { key: 'name', label: 'Barrier Name', className: 'min-w-[160px]' },
  { key: 'riskLevel', label: 'Risk Level', className: 'w-24 text-center' },
  { key: 'condition', label: 'Condition', className: 'min-w-[120px]' },
  { key: 'topFactor', label: 'Top SHAP Factor', className: 'min-w-[140px]' },
  { key: 'barrierType', label: 'Type', className: 'min-w-[100px]' },
  { key: 'lod', label: 'LOD', className: 'w-16 text-center' },
  { key: 'side', label: 'Side', className: 'w-24 text-center' },
]

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RankedBarriers() {
  const { barriers, predictions, setSelectedBarrierId, selectedBarrierId, setViewMode, eventDescription } = useBowtieContext()
  const [sortKey, setSortKey] = useState<keyof RankedRow>('rank')
  const [sortDir, setSortDir] = useState<SortDir>('asc')
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null)

  // Auto-expand the selected barrier row on mount (e.g. arriving from "View Full Analysis")
  useEffect(() => {
    if (selectedBarrierId) setExpandedRowId(selectedBarrierId)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  const [showEvidence, setShowEvidence] = useState<Record<string, boolean>>({})
  const [filterSide, setFilterSide] = useState<string>('all')
  const [filterRiskLevel, setFilterRiskLevel] = useState<string>('all')
  const [filterType, setFilterType] = useState<string>('all')

  const rows = buildRankedRows(barriers, predictions, sortKey, sortDir)

  const filteredRows = rows.filter((row) => {
    if (filterSide !== 'all' && row.side !== filterSide) return false
    if (filterRiskLevel !== 'all' && row.riskLevel !== filterRiskLevel) return false
    if (filterType !== 'all' && row.barrierType !== filterType) return false
    return true
  })

  const typeOptions = Array.from(new Set(rows.map((r) => r.barrierType))).sort()

  function handleHeaderClick(key: keyof RankedRow) {
    if (key === sortKey) {
      // Toggle direction
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  return (
    <div data-testid="ranked-barriers-table" className="overflow-x-auto">
      <h3 className="text-base font-semibold mb-3 text-[#E8ECF4]">All Barriers Ranked by Risk</h3>

      <div className="flex gap-3 mb-4 items-center flex-wrap">
        <select
          data-testid="filter-side"
          value={filterSide}
          onChange={(e) => setFilterSide(e.target.value)}
          className={`bg-[#242836] border border-[#2E3348] text-xs rounded px-2 py-1 ${filterSide !== 'all' ? 'text-[#E8ECF4]' : 'text-[#8B93A8]'}`}
        >
          <option value="all">All Sides</option>
          <option value="prevention">Prevention</option>
          <option value="mitigation">Mitigation</option>
        </select>
        <select
          data-testid="filter-risk-level"
          value={filterRiskLevel}
          onChange={(e) => setFilterRiskLevel(e.target.value)}
          className={`bg-[#242836] border border-[#2E3348] text-xs rounded px-2 py-1 ${filterRiskLevel !== 'all' ? 'text-[#E8ECF4]' : 'text-[#8B93A8]'}`}
        >
          <option value="all">All Risk Levels</option>
          <option value="red">High</option>
          <option value="amber">Medium</option>
          <option value="green">Low</option>
        </select>
        <select
          data-testid="filter-type"
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className={`bg-[#242836] border border-[#2E3348] text-xs rounded px-2 py-1 ${filterType !== 'all' ? 'text-[#E8ECF4]' : 'text-[#8B93A8]'}`}
        >
          <option value="all">All Types</option>
          {typeOptions.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {rows.length === 0 ? (
        <p className="text-sm text-[#5A6178]">No analyzed barriers yet</p>
      ) : (
        <>
          <p data-testid="filter-result-count" className="text-xs text-[#8B93A8] mb-3">
            Showing {filteredRows.length} of {rows.length} barriers
          </p>
          <table className="w-full text-sm border-collapse bg-[#1A1D27]">
          <thead>
            <tr className="bg-[#242836] border-b border-[#2E3348]">
              {COLUMNS.map((col) => {
                const isActive = col.key === sortKey
                const indicator = isActive ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''
                return (
                  <th
                    key={col.key}
                    className={`px-3 py-2 text-left text-xs font-medium text-[#8B93A8] cursor-pointer select-none whitespace-nowrap ${col.className ?? ''}`}
                    onClick={() => handleHeaderClick(col.key)}
                  >
                    {col.label}
                    {isActive && (
                      <span className="ml-1 text-[#E8ECF4]">{sortDir === 'asc' ? '▲' : '▼'}</span>
                    )}
                    {!isActive && indicator}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => {
              const isPositive = row.topFactorValue !== null && row.topFactorValue >= 0
              const pillColor = PILL_COLORS[row.riskLevel]
              const pillLabel = PILL_LABELS[row.riskLevel]

              return (
                <Fragment key={row.barrierId}>
                  <tr
                    className="border-b border-[#2E3348] hover:bg-[#242836] cursor-pointer text-[#E8ECF4] transition-colors"
                    onClick={() => {
                      setExpandedRowId((prev) => (prev === row.barrierId ? null : row.barrierId))
                      setSelectedBarrierId(row.barrierId)
                    }}
                  >
                    {/* Rank */}
                    <td className="px-3 py-2 text-center text-[#8B93A8] font-mono">{row.rank}</td>

                    {/* Barrier Name */}
                    <td className="px-3 py-2 font-medium">{row.name}</td>

                    {/* Risk Level pill */}
                    <td className="px-3 py-2 text-center">
                      <span
                        className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full ${pillColor}`}
                      >
                        {pillLabel}
                      </span>
                    </td>

                    {/* Condition */}
                    <td className="px-3 py-2 text-[#8B93A8]">{row.condition}</td>

                    {/* Top SHAP Factor */}
                    <td className="px-3 py-2">
                      <span className="text-[#8B93A8] mr-2">{row.topFactor}</span>
                      {row.topFactorValue !== null && (
                        <span
                          className={`text-xs font-mono ${isPositive ? 'text-red-400' : 'text-blue-400'}`}
                        >
                          {isPositive ? '+' : ''}
                          {row.topFactorValue.toFixed(3)}
                        </span>
                      )}
                    </td>

                    {/* Barrier Type */}
                    <td className="px-3 py-2 text-[#8B93A8]">{row.barrierType}</td>

                    {/* LOD */}
                    <td className="px-3 py-2 text-center text-[#8B93A8]">{row.lod}</td>

                    {/* Side */}
                    <td className="px-3 py-2 text-center">
                      <span
                        className={`text-xs ${row.side === 'prevention' ? 'text-blue-300' : 'text-amber-300'}`}
                      >
                        {row.side === 'prevention' ? 'Prevention' : 'Mitigation'}
                      </span>
                    </td>
                  </tr>

                  {expandedRowId === row.barrierId && predictions[row.barrierId] && (
                    <tr key={`${row.barrierId}-expanded`} data-testid="ranked-row-expanded">
                      <td colSpan={COLUMNS.length} className="px-4 py-4 bg-[#1E2130] border-b border-[#2E3348]">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          {/* Column 1: RiskScoreBadge */}
                          <div>
                            <RiskScoreBadge
                              probability={row.probability}
                              riskLevel={row.riskLevel}
                            />
                          </div>
                          {/* Column 2: ShapWaterfall */}
                          <div className="md:col-span-2">
                            <ShapWaterfall
                              shap={predictions[row.barrierId].model1_shap}
                              baseValue={predictions[row.barrierId].model1_base_value}
                              featureDisplayNames={FEATURE_DISPLAY_NAMES}
                              hiddenFeatures={SHAP_HIDDEN_FEATURES}
                            />
                          </div>
                        </div>
                        {/* Evidence gating */}
                        <div className="mt-3 border-t border-[#2E3348] pt-3">
                          {showEvidence[row.barrierId] ? (
                            <EvidenceSection
                              barrierId={row.barrierId}
                              barrier={barriers.find((b) => b.id === row.barrierId)!}
                              eventDescription={eventDescription}
                              prediction={predictions[row.barrierId]}
                            />
                          ) : (
                            <button
                              data-testid="load-evidence-btn"
                              className="px-3 py-1.5 text-sm bg-[#3B82F6] hover:bg-[#2563EB] text-white rounded-md transition-colors"
                              onClick={(e) => {
                                e.stopPropagation()
                                setShowEvidence((prev) => ({ ...prev, [row.barrierId]: true }))
                              }}
                            >
                              Load Evidence
                            </button>
                          )}
                        </div>

                        {/* Cross-link navigation */}
                        <div className="mt-3 border-t border-[#2E3348] pt-3">
                          <button
                            data-testid="view-on-diagram-btn"
                            className="px-3 py-1.5 text-xs bg-[#242836] border border-[#2E3348] text-[#8B93A8] hover:text-[#E8ECF4] rounded-md transition-colors"
                            onClick={(e) => {
                              e.stopPropagation()
                              setViewMode('diagram')
                            }}
                          >
                            View on Diagram
                          </button>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
        </>
      )}
    </div>
  )
}
