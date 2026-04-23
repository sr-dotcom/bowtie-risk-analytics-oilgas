'use client'

import { useState, useEffect, useRef } from 'react'
import { useBowtieContext } from '@/context/BowtieContext'
import { useAnalyzeBarriers } from '@/hooks/useAnalyzeBarriers'
import RiskDistributionChart, { buildRiskDistribution } from './RiskDistributionChart'
import TopAtRiskBarriers from './TopAtRiskBarriers'
import ScenarioContext from './ScenarioContext'
import GlobalShapChart, { PifPrevalenceChart, AprioriRulesTable, DegradationContextPanel } from './DriversHF'
import RankedBarriers from './RankedBarriers'
import EvidenceView from './EvidenceView'
import { NarrativeHero } from './NarrativeHero'

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const TABS = [
  { id: 'executive-summary', label: 'Executive Summary' },
  { id: 'drivers-hf', label: 'Drivers & HF' },
  { id: 'ranked-barriers', label: 'Ranked Barriers' },
  { id: 'evidence', label: 'Evidence' },
] as const

type TabId = (typeof TABS)[number]['id']

const TRAINING_INCIDENTS = 174
const TRAINING_BARRIERS = 558
const RAG_CORPUS_INCIDENTS = 156

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DashboardView() {
  const [activeTab, setActiveTab] = useState<TabId>('executive-summary')
  const { barriers, predictions, isAnalyzing, dashboardTab, setDashboardTab, cascadingPredictions, eventDescription, explanation } = useBowtieContext()

  // Consume dashboardTab from context: switch active tab then clear to avoid re-triggering
  useEffect(() => {
    if (dashboardTab) {
      setActiveTab(dashboardTab as TabId)
      setDashboardTab(null)
    }
  }, [dashboardTab, setDashboardTab])
  const { analyzeAll } = useAnalyzeBarriers()

  const autoTriggered = useRef(false)
  useEffect(() => {
    if (autoTriggered.current) return
    const hasUnanalyzed = barriers.some((b) => !predictions[b.id])
    if (barriers.length > 0 && hasUnanalyzed && !isAnalyzing) {
      autoTriggered.current = true
      analyzeAll()
    }
  }, [barriers.length]) // eslint-disable-line react-hooks/exhaustive-deps

  const counts = buildRiskDistribution(barriers)

  const hasAnalyzed = barriers.some((b) => b.average_cascading_probability !== undefined)
  const highRiskCount = barriers.filter((b) => b.riskLevel === 'red').length
  const topBarrier = barriers
    .filter((b) => b.average_cascading_probability !== undefined)
    .sort((a, b) => (b.average_cascading_probability ?? 0) - (a.average_cascading_probability ?? 0))[0] ?? null
  const heroTopBarrier = topBarrier
    ? { name: topBarrier.name, probability: topBarrier.average_cascading_probability ?? 0 }
    : null

  return (
    <div className="w-full bg-[#0F1419] min-h-screen flex flex-col">
      {/* Tab bar */}
      <div className="flex bg-[#151B24] rounded-t-md border-b border-[#2A3442] flex-shrink-0">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-xs font-medium transition-colors cursor-pointer ${
              activeTab === tab.id
                ? 'text-[#E8E8E8] border-b-2 border-[#2C5F7F]'
                : 'text-[#6B7280] hover:text-[#9CA3AF]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Loading indicator — visible while batch /predict is running */}
      {isAnalyzing && (
        <div data-testid="analyzing-skeleton" className="px-8 pt-4 space-y-2">
          <div className="h-2 bg-[#151B24] rounded animate-pulse w-3/4" />
          <div className="h-2 bg-[#151B24] rounded animate-pulse w-1/2" />
        </div>
      )}

      {/* Tab content */}
      <div className="flex-1 p-8">
        {activeTab === 'executive-summary' && (
          <>
            {/* Narrative hero — §9, above KPI cards */}
            <NarrativeHero
              topEvent={eventDescription}
              totalBarriers={barriers.length}
              highRiskCount={highRiskCount}
              topBarrier={heroTopBarrier}
              similarIncidentsCount={explanation?.unique_incident_count ?? 0}
              totalRetrievedIncidents={RAG_CORPUS_INCIDENTS}
              hasAnalyzed={hasAnalyzed}
              shapTopFeatures={topBarrier?.top_reasons?.slice(0, 3) ?? []}
              evidenceSnippets={explanation?.evidence_snippets ?? []}
            />

            {/* Scenario header */}
            <ScenarioContext />

            {/* Risk Posture + Analysis Overview */}
            {(() => {
              const overallRisk =
                counts.high > 0 ? 'high' : counts.medium > 0 ? 'medium' : 'low'
              return (
                <div className="grid grid-cols-2 gap-4 mt-6">
                  {/* Scenario Risk Posture */}
                  <div className="bg-[#151B24] rounded-lg p-5 border border-[#2A3442]">
                    <h3 className="text-xs font-medium text-[#6B7280] mb-3 uppercase tracking-wider">
                      Scenario Risk Posture
                    </h3>
                    <div className="flex items-center gap-4">
                      <div
                        className="w-16 h-16 rounded-full flex items-center justify-center text-lg font-bold flex-shrink-0 border-2"
                        style={
                          overallRisk === 'high'
                            ? { backgroundColor: '#1A2332', color: '#E74C3C', borderColor: '#C0392B' }
                            : overallRisk === 'medium'
                            ? { backgroundColor: '#1A2332', color: '#D68910', borderColor: '#996515' }
                            : { backgroundColor: '#1A2332', color: '#27AE60', borderColor: '#1F6F43' }
                        }
                      >
                        {overallRisk === 'high' ? 'H' : overallRisk === 'medium' ? 'M' : 'L'}
                      </div>
                      <div>
                        <p className="text-base font-semibold text-[#E8E8E8]">
                          {overallRisk === 'high' ? 'High Risk' : overallRisk === 'medium' ? 'Elevated Risk' : 'Controlled Risk'}
                        </p>
                        <p className="text-xs text-[#6B7280] mt-0.5">
                          {counts.high} high · {counts.medium} medium · {counts.low} low risk barriers
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Analysis Overview */}
                  <div className="bg-[#151B24] rounded-lg p-5 border border-[#2A3442]">
                    <h3 className="text-xs font-medium text-[#6B7280] mb-3 uppercase tracking-wider">
                      Analysis Overview
                    </h3>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <p className="text-2xl font-bold text-[#E8E8E8]">{barriers.length}</p>
                        <p className="text-xs text-[#6B7280]">Barriers analyzed</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-[#E8E8E8]">
                          {barriers.filter((b) => b.side === 'prevention').length} / {barriers.filter((b) => b.side === 'mitigation').length}
                        </p>
                        <p className="text-xs text-[#6B7280]">Prevention / Mitigation</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-[#E8E8E8]">{TRAINING_INCIDENTS}</p>
                        <p className="text-xs text-[#6B7280]">Reference incidents</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-[#E8E8E8]">{TRAINING_BARRIERS}</p>
                        <p className="text-xs text-[#6B7280]">Barrier observations</p>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })()}

            {/* Risk Distribution (secondary) */}
            <div className="mt-6">
              <RiskDistributionChart counts={counts} />
            </div>
            <div className="mt-6">
              <TopAtRiskBarriers />
            </div>
            <div className="mt-6 bg-[#151B24] rounded-lg p-4 border border-[#2A3442]">
              <h3 className="text-sm font-semibold text-[#E8E8E8] mb-2">Assessment Basis</h3>
              <p className="text-sm text-[#9CA3AF] leading-relaxed">
                Historical reliability assessment based on analysis of{' '}
                <span className="text-[#E8E8E8] font-medium">{TRAINING_INCIDENTS} real BSEE/CSB incidents</span>{' '}
                with{' '}
                <span className="text-[#E8E8E8] font-medium">{TRAINING_BARRIERS} barrier observations</span>{' '}
                from Loss of Containment events in oil &amp; gas operations.
                Barrier failure patterns identified using XGBoost with SHAP explainability,
                validated through 5-fold cross-validation.
              </p>
            </div>
          </>
        )}
        {activeTab === 'drivers-hf' && (
          <>
            <GlobalShapChart />
            <div className="mt-6">
              {/* D016 Branch C: show Degradation Context when cascading predictions available */}
              {cascadingPredictions.length > 0 ? <DegradationContextPanel /> : <PifPrevalenceChart />}
            </div>
            <div className="mt-6">
              <AprioriRulesTable />
            </div>
          </>
        )}
        {activeTab === 'ranked-barriers' && <RankedBarriers />}
        {activeTab === 'evidence' && <EvidenceView />}

      </div>
    </div>
  )
}
