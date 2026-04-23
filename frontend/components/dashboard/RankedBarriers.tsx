'use client'

import { useState, useEffect, Fragment } from 'react'
import type React from 'react'
import { Info } from 'lucide-react'
import { useBowtieContext } from '@/context/BowtieContext'
import { getDenominatorValue } from '@/lib/denominators'
import riskThresholds from '@/public/risk_thresholds.json'
import { SHAP_HIDDEN_FEATURES, FEATURE_DISPLAY_NAMES } from './TopAtRiskBarriers'
import RiskScoreBadge from '@/components/panel/RiskScoreBadge'
import ShapWaterfall from '@/components/panel/ShapWaterfall'
import EvidenceSection from '@/components/panel/EvidenceSection'
import type {
  BarrierPrediction,
  Barrier,
  PredictResponse,
  RiskLevel,
  ScenarioBarrier,
} from '@/lib/types'

// ---------------------------------------------------------------------------
// Ranking criteria tooltip — all values from denominators.json + risk_thresholds.json
// ---------------------------------------------------------------------------

const _p60 = riskThresholds.p60.toFixed(2)
const _p80 = riskThresholds.p80.toFixed(2)
const _aucMean = Number(getDenominatorValue('cascade_model_cv_auc_mean')).toFixed(2)
const _aucStd = Number(getDenominatorValue('cascade_model_cv_auc_std')).toFixed(2)
const _incidents = getDenominatorValue('rag_corpus_incidents')
const _pairRows = getDenominatorValue('m003_cascade_training_pair_rows')

const RANKING_CRITERIA_TOOLTIP = [
  `Ranked by predicted failure probability from the M003 cascading XGBoost model`,
  `trained on ${_incidents} BSEE+CSB incidents (${_pairRows} pair-feature rows).`,
  ``,
  `Risk tiers per D006 thresholds:`,
  `  LOW    < ${_p60}`,
  `  MEDIUM ≥ ${_p60} and < ${_p80}`,
  `  HIGH   ≥ ${_p80}`,
  ``,
  `5-fold GroupKFold CV AUC: ${_aucMean} ± ${_aucStd}`,
  `(fold range 0.65–0.85, fold 4 floor 0.65 published not hidden)`,
].join('\n')

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
  /** control_id if from cascading mode, else barrier UUID */
  isCascading: boolean
}

type SortDir = 'asc' | 'desc'

// ---------------------------------------------------------------------------
// Risk level helpers
// ---------------------------------------------------------------------------

const PILL_STYLES: Record<RiskLevel, React.CSSProperties> = {
  red:        { backgroundColor: '#1A2332', color: '#E74C3C', border: '1px solid #C0392B' },
  amber:      { backgroundColor: '#1A2332', color: '#D68910', border: '1px solid #996515' },
  green:      { backgroundColor: '#1A2332', color: '#27AE60', border: '1px solid #1F6F43' },
  unanalyzed: { backgroundColor: '#151B24', color: '#6B7280', border: '1px solid #2A3442' },
}

const PILL_LABELS: Record<RiskLevel, string> = {
  red: 'High',
  amber: 'Medium',
  green: 'Low',
  unanalyzed: '—',
}

function riskBandToLevel(band: 'HIGH' | 'MEDIUM' | 'LOW'): RiskLevel {
  if (band === 'HIGH') return 'red'
  if (band === 'MEDIUM') return 'amber'
  return 'green'
}

// ---------------------------------------------------------------------------
// Pure functions
// ---------------------------------------------------------------------------

/**
 * Build all analyzed barrier rows from the old marginal-model predictions,
 * ranked by failure probability then sorted by the given key/direction.
 *
 * @deprecated Used by old /predict flow. Removed in S05a/T06.
 */
export function buildRankedRows(
  barriers: Barrier[],
  predictions: Record<string, PredictResponse>,
  sortKey: keyof RankedRow,
  sortDir: SortDir,
): RankedRow[] {
  const analyzed = barriers.filter((b) => predictions[b.id] !== undefined)
  const byProbability = [...analyzed].sort(
    (a, b) => predictions[b.id].model1_probability - predictions[a.id].model1_probability,
  )
  const rows: RankedRow[] = byProbability.map((barrier, idx) => {
    const pred = predictions[barrier.id]
    const probability = pred.model1_probability
    const visibleShap = (pred.model1_shap ?? []).filter(
      (s) => !SHAP_HIDDEN_FEATURES.has(s.feature),
    )
    const sortedShap = [...visibleShap].sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    const topShap = sortedShap.length > 0 ? sortedShap[0] : null
    const topFactor = topShap ? (FEATURE_DISPLAY_NAMES[topShap.feature] ?? topShap.feature) : '—'
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
      isCascading: false,
    }
  })
  return [...rows].sort((a, b) => {
    const aVal = a[sortKey]; const bVal = b[sortKey]
    if (aVal === null && bVal === null) return 0
    if (aVal === null) return sortDir === 'asc' ? 1 : -1
    if (bVal === null) return sortDir === 'asc' ? -1 : 1
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return sortDir === 'asc' ? aVal - bVal : bVal - aVal
    }
    const aStr = String(aVal).toLowerCase(); const bStr = String(bVal).toLowerCase()
    if (aStr < bStr) return sortDir === 'asc' ? -1 : 1
    if (aStr > bStr) return sortDir === 'asc' ? 1 : -1
    return 0
  })
}

/**
 * Build ranked rows from cascading predictions + scenario barrier metadata.
 * Barriers are ordered by y_fail_probability (already sorted by BowtieContext
 * via composite_risk_score from rank-targets).
 */
export function buildCascadingRankedRows(
  cascadingPredictions: BarrierPrediction[],
  scenarioBarriers: ScenarioBarrier[],
  conditioningBarrierId: string,
  sortKey: keyof RankedRow,
  sortDir: SortDir,
): RankedRow[] {
  const barrierMap = new Map(scenarioBarriers.map((b) => [b.control_id, b]))

  const rows: RankedRow[] = cascadingPredictions
    .filter((p) => p.target_barrier_id !== conditioningBarrierId)
    .map((p, idx) => {
      const sb = barrierMap.get(p.target_barrier_id)
      const topShap = p.shap_values.length > 0
        ? [...p.shap_values].sort((a, b) => Math.abs(b.value) - Math.abs(a.value))[0]
        : null
      return {
        rank: idx + 1,
        barrierId: p.target_barrier_id,
        name: sb?.name ?? p.target_barrier_id,
        riskLevel: riskBandToLevel(p.risk_band),
        probability: p.y_fail_probability,
        condition: sb?.barrier_condition ?? '—',
        topFactor: topShap?.display_name ?? topShap?.feature ?? '—',
        topFactorValue: topShap?.value ?? null,
        barrierType: sb?.barrier_type ?? '—',
        lod: sb?.line_of_defense ?? '—',
        side: sb?.barrier_level ?? '—',
        isCascading: true,
      }
    })

  return [...rows].sort((a, b) => {
    const aVal = a[sortKey]; const bVal = b[sortKey]
    if (aVal === null && bVal === null) return 0
    if (aVal === null) return sortDir === 'asc' ? 1 : -1
    if (bVal === null) return sortDir === 'asc' ? -1 : 1
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return sortDir === 'asc' ? aVal - bVal : bVal - aVal
    }
    const aStr = String(aVal).toLowerCase(); const bStr = String(bVal).toLowerCase()
    if (aStr < bStr) return sortDir === 'asc' ? -1 : 1
    if (aStr > bStr) return sortDir === 'asc' ? 1 : -1
    return 0
  })
}

// ---------------------------------------------------------------------------
// Column definitions
// ---------------------------------------------------------------------------

interface Column { key: keyof RankedRow; label: string; className?: string }

const COLUMNS: Column[] = [
  { key: 'rank', label: '#', className: 'w-10 text-center' },
  { key: 'name', label: 'Barrier Name', className: 'min-w-[160px]' },
  { key: 'riskLevel', label: 'Avg Cascade Risk', className: 'w-24 text-center' },
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
  const {
    barriers,
    predictions,
    setSelectedBarrierId,
    selectedBarrierId,
    setViewMode,
    eventDescription,
    cascadingPredictions,
    scenario,
    conditioningBarrierId,
    setConditioningBarrierId,
    setSelectedTargetBarrierId,
  } = useBowtieContext()

  const [sortKey, setSortKey] = useState<keyof RankedRow>('rank')
  const [sortDir, setSortDir] = useState<SortDir>('asc')
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null)

  useEffect(() => {
    if (selectedBarrierId) setExpandedRowId(selectedBarrierId)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const [showEvidence, setShowEvidence] = useState<Record<string, boolean>>({})
  const [filterSide, setFilterSide] = useState<string>('all')
  const [filterRiskLevel, setFilterRiskLevel] = useState<string>('all')
  const [filterType, setFilterType] = useState<string>('all')

  // Use cascading rows when predictions are available, old rows otherwise
  const isCascadingMode = cascadingPredictions.length > 0 && scenario !== null && conditioningBarrierId !== null
  const rows = isCascadingMode
    ? buildCascadingRankedRows(
        cascadingPredictions,
        scenario.barriers,
        conditioningBarrierId,
        sortKey,
        sortDir,
      )
    : buildRankedRows(barriers, predictions, sortKey, sortDir)

  const filteredRows = rows.filter((row) => {
    if (filterSide !== 'all' && row.side !== filterSide) return false
    if (filterRiskLevel !== 'all' && row.riskLevel !== filterRiskLevel) return false
    if (filterType !== 'all' && row.barrierType !== filterType) return false
    return true
  })

  const typeOptions = Array.from(new Set(rows.map((r) => r.barrierType))).sort()

  function handleHeaderClick(key: keyof RankedRow) {
    if (key === sortKey) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  return (
    <div data-testid="ranked-barriers-table" className="overflow-x-auto">
      <h3 className="text-base font-semibold mb-3 text-[#E8E8E8] flex items-center gap-1.5">
        All Barriers Ranked by Risk
        <span title={RANKING_CRITERIA_TOOLTIP} aria-label="Ranking criteria" role="img" className="flex-shrink-0">
          <Info className="w-4 h-4 text-[#6B7280] cursor-help" />
        </span>
      </h3>

      {isCascadingMode && conditioningBarrierId && (
        <div className="mb-3 px-3 py-2 bg-[#1A2332] border-l-4 border-[#D68910] rounded-r-lg">
          <p className="text-xs text-[#9CA3AF]">
            Cascading analysis: assuming{' '}
            <span style={{ color: '#D68910' }} className="font-medium">
              {scenario?.barriers.find((b) => b.control_id === conditioningBarrierId)?.name
                ?? conditioningBarrierId}
            </span>{' '}
            has failed
          </p>
        </div>
      )}

      <div className="flex gap-3 mb-4 items-center flex-wrap">
        <select
          data-testid="filter-side"
          value={filterSide}
          onChange={(e) => setFilterSide(e.target.value)}
          className={`bg-[#151B24] border border-[#2A3442] text-xs rounded px-2 py-1 ${filterSide !== 'all' ? 'text-[#E8E8E8]' : 'text-[#9CA3AF]'}`}
        >
          <option value="all">All Sides</option>
          <option value="prevention">Prevention</option>
          <option value="mitigation">Mitigation</option>
        </select>
        <select
          data-testid="filter-risk-level"
          value={filterRiskLevel}
          onChange={(e) => setFilterRiskLevel(e.target.value)}
          className={`bg-[#151B24] border border-[#2A3442] text-xs rounded px-2 py-1 ${filterRiskLevel !== 'all' ? 'text-[#E8E8E8]' : 'text-[#9CA3AF]'}`}
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
          className={`bg-[#151B24] border border-[#2A3442] text-xs rounded px-2 py-1 ${filterType !== 'all' ? 'text-[#E8E8E8]' : 'text-[#9CA3AF]'}`}
        >
          <option value="all">All Types</option>
          {typeOptions.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      {rows.length === 0 ? (
        <p className="text-sm text-[#6B7280]">No analyzed barriers yet — click Analyze Barriers to compute Average Cascading Risk.</p>
      ) : (
        <>
          <p data-testid="filter-result-count" className="text-xs text-[#9CA3AF] mb-3">
            Showing {filteredRows.length} of {rows.length} barriers
          </p>
          <table className="w-full text-sm border-collapse bg-[#151B24]">
            <thead>
              <tr className="bg-[#151B24] border-b border-[#2A3442]">
                {COLUMNS.map((col) => {
                  const isActive = col.key === sortKey
                  return (
                    <th
                      key={col.key}
                      className={`px-3 py-2 text-left text-xs font-medium text-[#9CA3AF] cursor-pointer select-none whitespace-nowrap ${col.className ?? ''}`}
                      onClick={() => handleHeaderClick(col.key)}
                    >
                      {col.label}
                      {isActive && (
                        <span className="ml-1 text-[#E8E8E8]">{sortDir === 'asc' ? '▲' : '▼'}</span>
                      )}
                    </th>
                  )
                })}
                {/* Extra column for "What if this fails?" button */}
                <th className="px-3 py-2 text-left text-xs font-medium text-[#9CA3AF] w-32">
                  Cascade
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => {
                const isPositive = row.topFactorValue !== null && row.topFactorValue >= 0
                const pillStyle = PILL_STYLES[row.riskLevel]
                const pillLabel = PILL_LABELS[row.riskLevel]
                const isConditioning = row.barrierId === conditioningBarrierId
                const cascadingPred = isCascadingMode
                  ? cascadingPredictions.find((p) => p.target_barrier_id === row.barrierId)
                  : null

                return (
                  <Fragment key={row.barrierId}>
                    <tr
                      className={`border-b border-[#2A3442] hover:bg-[#1C2430] cursor-pointer text-[#E8E8E8] transition-colors ${isConditioning ? 'bg-[#1A2332]' : ''}`}
                      onClick={() => {
                        setExpandedRowId((prev) => (prev === row.barrierId ? null : row.barrierId))
                        if (isCascadingMode) {
                          setSelectedTargetBarrierId(row.barrierId)
                        } else {
                          setSelectedBarrierId(row.barrierId)
                        }
                      }}
                    >
                      <td className="px-3 py-2 text-center text-[#9CA3AF] font-mono">{row.rank}</td>
                      <td className="px-3 py-2 font-medium">{row.name}</td>
                      <td className="px-3 py-2 text-center">
                        <span className="inline-block text-xs font-medium px-2 py-0.5 rounded-full" style={pillStyle}>
                          {pillLabel}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-[#9CA3AF]">{row.condition}</td>
                      <td className="px-3 py-2">
                        <span className="text-[#9CA3AF] mr-2">{row.topFactor}</span>
                        {row.topFactorValue !== null && (
                          <span className="text-xs font-mono" style={{ color: isPositive ? '#E74C3C' : '#2C5F7F' }}>
                            {isPositive ? '+' : ''}{row.topFactorValue.toFixed(3)}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-[#9CA3AF]">{row.barrierType}</td>
                      <td className="px-3 py-2 text-center text-[#9CA3AF]">{row.lod}</td>
                      <td className="px-3 py-2 text-center">
                        <span className="text-xs" style={{ color: row.side === 'prevention' ? '#2C5F7F' : '#D68910' }}>
                          {row.side === 'prevention' ? 'Prevention' : 'Mitigation'}
                        </span>
                      </td>
                      {/* "What if this fails?" button — sets conditioning barrier */}
                      <td className="px-3 py-2 text-center">
                        <button
                          data-testid={`condition-btn-${row.barrierId}`}
                          className={`px-2 py-1 text-xs rounded transition-colors ${
                            isConditioning
                              ? 'bg-amber-500/30 text-amber-300 border border-amber-500/50'
                              : 'bg-[#151B24] border border-[#2A3442] text-[#6B7280] hover:text-[#E8E8E8]'
                          }`}
                          onClick={(e) => {
                            e.stopPropagation()
                            setConditioningBarrierId(
                              isConditioning ? null : row.barrierId,
                            )
                          }}
                        >
                          {isConditioning ? 'Conditioning' : 'What if fails?'}
                        </button>
                      </td>
                    </tr>

                    {expandedRowId === row.barrierId && (
                      <tr key={`${row.barrierId}-expanded`} data-testid="ranked-row-expanded">
                        <td colSpan={COLUMNS.length + 1} className="px-4 py-4 bg-[#1C2430] border-b border-[#2A3442]">
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div>
                              <RiskScoreBadge
                                probability={row.probability}
                                riskLevel={row.riskLevel}
                              />
                            </div>
                            <div className="md:col-span-2">
                              {isCascadingMode && cascadingPred ? (
                                <ShapWaterfall
                                  shap={[]}
                                  cascadingShap={cascadingPred.shap_values}
                                  baseValue={0}
                                />
                              ) : predictions[row.barrierId] ? (
                                <ShapWaterfall
                                  shap={predictions[row.barrierId].model1_shap}
                                  baseValue={predictions[row.barrierId].model1_base_value}
                                  featureDisplayNames={FEATURE_DISPLAY_NAMES}
                                  hiddenFeatures={SHAP_HIDDEN_FEATURES}
                                />
                              ) : null}
                            </div>
                          </div>
                          {/* Evidence section — only old mode (cascading evidence shown in Evidence tab) */}
                          {!isCascadingMode && (
                            <div className="mt-3 border-t border-[#2A3442] pt-3">
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
                                  className="px-3 py-1.5 text-sm bg-[#2C5F7F] hover:bg-[#3A7399] text-[#E8E8E8] rounded-md transition-colors"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    setShowEvidence((prev) => ({ ...prev, [row.barrierId]: true }))
                                  }}
                                >
                                  Load Evidence
                                </button>
                              )}
                            </div>
                          )}
                          {/* Navigation */}
                          <div className="mt-3 border-t border-[#2A3442] pt-3">
                            <button
                              data-testid="view-on-diagram-btn"
                              className="px-3 py-1.5 text-xs bg-[#151B24] border border-[#2A3442] text-[#9CA3AF] hover:text-[#E8E8E8] rounded-md transition-colors"
                              onClick={(e) => { e.stopPropagation(); setViewMode('diagram') }}
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
      <p className="text-xs text-[#6B7280] mt-4 italic">
        Average Cascading Risk: mean failure probability across all single-barrier-failure scenarios.
        See API contract for methodology.
      </p>
    </div>
  )
}
