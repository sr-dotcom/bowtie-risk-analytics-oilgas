'use client'

import { useState } from 'react'

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const TABS = [
  { id: 'fleet-overview', label: 'Fleet Overview' },
  { id: 'barrier-coverage', label: 'Barrier Coverage' },
  { id: 'incident-trends', label: 'Incident Trends' },
  { id: 'risk-matrix', label: 'Risk Matrix' },
] as const

type TabId = (typeof TABS)[number]['id']

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DashboardView() {
  const [activeTab, setActiveTab] = useState<TabId>('fleet-overview')

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

      {/* Tab content */}
      <div className="flex-1 flex items-center justify-center p-8">
        {TABS.map((tab) =>
          activeTab === tab.id ? (
            <p key={tab.id} className="text-sm text-[#5A6178]">
              {tab.label} coming soon
            </p>
          ) : null
        )}
      </div>
    </div>
  )
}
