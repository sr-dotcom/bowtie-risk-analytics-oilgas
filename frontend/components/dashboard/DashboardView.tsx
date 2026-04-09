'use client'

import { useState, useEffect, useRef } from 'react'
import { useBowtieContext } from '@/context/BowtieContext'
import { useAnalyzeBarriers } from '@/hooks/useAnalyzeBarriers'
import RiskDistributionChart, { buildRiskDistribution } from './RiskDistributionChart'
import TopAtRiskBarriers from './TopAtRiskBarriers'
import ScenarioContext from './ScenarioContext'
import GlobalShapChart, { PifPrevalenceChart, AprioriRulesTable } from './DriversHF'
import RankedBarriers from './RankedBarriers'
import EvidenceView from './EvidenceView'

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

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DashboardView() {
  const [activeTab, setActiveTab] = useState<TabId>('executive-summary')
  const { barriers, predictions, isAnalyzing, dashboardTab, setDashboardTab } = useBowtieContext()

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

  return (
    <div className="w-full bg-[#0F1117] min-h-screen flex flex-col">
      {/* Tab bar */}
      <div className="flex bg-[#242836] rounded-t-md border-b border-[#2E3348] flex-shrink-0">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-xs font-medium transition-colors cursor-pointer ${
              activeTab === tab.id
                ? 'text-[#E8ECF4] border-b-2 border-[#3B82F6]'
                : 'text-[#5A6178] hover:text-[#8B93A8]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Loading indicator — visible while batch /predict is running */}
      {isAnalyzing && (
        <div data-testid="analyzing-skeleton" className="px-8 pt-4 space-y-2">
          <div className="h-2 bg-[#242836] rounded animate-pulse w-3/4" />
          <div className="h-2 bg-[#242836] rounded animate-pulse w-1/2" />
        </div>
      )}

      {/* Tab content */}
      <div className="flex-1 p-8">
        {activeTab === 'executive-summary' && (
          <>
            {/* Scenario header */}
            <ScenarioContext />

            {/* Risk Posture + Analysis Overview */}
            {(() => {
              const overallRisk =
                counts.high > 0 ? 'high' : counts.medium > 0 ? 'medium' : 'low'
              return (
                <div className="grid grid-cols-2 gap-4 mt-6">
                  {/* Scenario Risk Posture */}
                  <div className="bg-[#242836] rounded-lg p-5 border border-[#2E3348]">
                    <h3 className="text-xs font-medium text-[#5A6178] mb-3 uppercase tracking-wider">
                      Scenario Risk Posture
                    </h3>
                    <div className="flex items-center gap-4">
                      <div className={`w-16 h-16 rounded-full flex items-center justify-center text-lg font-bold flex-shrink-0 ${
                        overallRisk === 'high'
                          ? 'bg-red-500/20 text-red-400 ring-2 ring-red-500/40'
                          : overallRisk === 'medium'
                          ? 'bg-amber-500/20 text-amber-400 ring-2 ring-amber-500/40'
                          : 'bg-green-500/20 text-green-400 ring-2 ring-green-500/40'
                      }`}>
                        {overallRisk === 'high' ? 'H' : overallRisk === 'medium' ? 'M' : 'L'}
                      </div>
                      <div>
                        <p className="text-base font-semibold text-[#E8ECF4]">
                          {overallRisk === 'high' ? 'High Risk' : overallRisk === 'medium' ? 'Elevated Risk' : 'Controlled Risk'}
                        </p>
                        <p className="text-xs text-[#5A6178] mt-0.5">
                          {counts.high} high · {counts.medium} medium · {counts.low} low risk barriers
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Analysis Overview */}
                  <div className="bg-[#242836] rounded-lg p-5 border border-[#2E3348]">
                    <h3 className="text-xs font-medium text-[#5A6178] mb-3 uppercase tracking-wider">
                      Analysis Overview
                    </h3>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <p className="text-2xl font-bold text-[#E8ECF4]">{barriers.length}</p>
                        <p className="text-xs text-[#5A6178]">Barriers analyzed</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-[#E8ECF4]">
                          {barriers.filter((b) => b.side === 'prevention').length} / {barriers.filter((b) => b.side === 'mitigation').length}
                        </p>
                        <p className="text-xs text-[#5A6178]">Prevention / Mitigation</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-[#E8ECF4]">174</p>
                        <p className="text-xs text-[#5A6178]">Reference incidents</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-[#E8ECF4]">558</p>
                        <p className="text-xs text-[#5A6178]">Barrier observations</p>
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
            <div className="mt-6 bg-[#242836] rounded-lg p-4 border border-[#2E3348]">
              <h3 className="text-sm font-semibold text-[#E8ECF4] mb-2">Assessment Basis</h3>
              <p className="text-sm text-[#8B93A8] leading-relaxed">
                Historical reliability assessment based on analysis of{' '}
                <span className="text-[#E8ECF4] font-medium">174 real BSEE/CSB incidents</span>{' '}
                with{' '}
                <span className="text-[#E8ECF4] font-medium">558 barrier observations</span>{' '}
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
              <PifPrevalenceChart />
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
