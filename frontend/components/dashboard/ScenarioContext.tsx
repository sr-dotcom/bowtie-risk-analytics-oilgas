'use client'

import { useBowtieContext } from '@/context/BowtieContext'
import type { Barrier, PredictResponse } from '@/lib/types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ScenarioSummary {
  eventDescription: string
  totalBarriers: number
  analyzedBarriers: number
}

// ---------------------------------------------------------------------------
// Pure function
// ---------------------------------------------------------------------------

/**
 * Compute scenario summary from current bowtie state.
 *
 * @param barriers         - All barriers from BowtieContext.
 * @param predictions      - Map of barrierId → PredictResponse from BowtieContext.
 * @param eventDescription - Event description string from BowtieContext.
 * @returns ScenarioSummary with totalBarriers, analyzedBarriers, and eventDescription.
 */
export function buildScenarioSummary(
  barriers: Barrier[],
  predictions: Record<string, PredictResponse>,
  eventDescription: string,
): ScenarioSummary {
  const totalBarriers = barriers.length
  const analyzedBarriers = barriers.filter((b) => predictions[b.id] !== undefined).length
  return { eventDescription, totalBarriers, analyzedBarriers }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ScenarioContext() {
  const { barriers, predictions, eventDescription } = useBowtieContext()
  const summary = buildScenarioSummary(barriers, predictions, eventDescription)

  return (
    <div data-testid="scenario-context">
      <h3 className="text-sm font-semibold text-[#E8ECF4] mb-2">Scenario Context</h3>

      <p className="text-sm text-[#8B93A8] mb-3">
        {summary.eventDescription.trim() !== ''
          ? summary.eventDescription
          : 'No scenario loaded'}
      </p>

      <div className="flex gap-2">
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-[#2E3348] text-[#8B93A8]">
          {summary.totalBarriers} barriers
        </span>
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-[#2E3348] text-[#8B93A8]">
          {summary.analyzedBarriers} analyzed
        </span>
      </div>
    </div>
  )
}
