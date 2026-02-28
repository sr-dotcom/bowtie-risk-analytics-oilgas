'use client'

import { useBowtieContext } from '@/context/BowtieContext'
import RiskScoreBadge from './RiskScoreBadge'
import ShapWaterfall from './ShapWaterfall'
import EvidenceSection from './EvidenceSection'

// ---------------------------------------------------------------------------
// Static display names for barrier-category SHAP features (not in degradation_factors)
// ---------------------------------------------------------------------------

/** Barrier-category features come from the model but are not mapped via degradation_factors.
 *  These names match the feature_names.json 'barrier' category entries. */
const BARRIER_FEATURE_DISPLAY_NAMES: Record<string, string> = {
  source_agency: 'Data Source',
  barrier_family: 'Barrier Family',
  side: 'Pathway Position',
  barrier_type: 'Barrier Type',
  line_of_defense: 'Line of Defense',
  supporting_text_count: 'Evidence Volume',
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Right-side detail panel — orchestrates risk score badge, SHAP waterfall,
 * and evidence section for the selected barrier.
 *
 * Reads selectedBarrierId, barriers, predictions, and eventDescription from
 * BowtieContext. Evidence loading is delegated to EvidenceSection.
 *
 * States:
 * 1. No barrier selected → empty state copy
 * 2. Barrier selected but no prediction → prompt to analyze
 * 3. Barrier selected with prediction → full analysis view
 */
export default function DetailPanel() {
  const { selectedBarrierId, barriers, predictions, eventDescription } = useBowtieContext()

  // State 1: No barrier selected
  if (!selectedBarrierId) {
    return (
      <div className="h-full flex items-start pt-8 justify-center">
        <p className="text-sm text-gray-400 text-center px-4">
          Click a barrier node to see its risk analysis.
        </p>
      </div>
    )
  }

  const barrier = barriers.find((b) => b.id === selectedBarrierId)

  // Barrier not found in list (edge case: removed while selected)
  if (!barrier) {
    return (
      <div className="h-full flex items-start pt-8 justify-center">
        <p className="text-sm text-gray-400 text-center px-4">
          Click a barrier node to see its risk analysis.
        </p>
      </div>
    )
  }

  const pred = predictions[selectedBarrierId]

  // State 2: Barrier selected but not yet analyzed
  if (!pred) {
    return (
      <div className="h-full flex items-start pt-8 justify-center">
        <p className="text-sm text-gray-400 text-center px-4">
          Run Analyze Barriers to see risk analysis for this barrier.
        </p>
      </div>
    )
  }

  // State 3: Full analysis view
  const hasModel2 = pred.model2_shap && pred.model2_shap.length > 0

  // Build feature display name map: barrier features (static) + PIF features (dynamic from API)
  // Barrier features are not in degradation_factors (API only emits incident_context category)
  const featureDisplayNames: Record<string, string> = { ...BARRIER_FEATURE_DISPLAY_NAMES }
  if (pred.degradation_factors) {
    for (const df of pred.degradation_factors) {
      featureDisplayNames[df.source_feature] = df.factor
    }
  }

  return (
    <div className="space-y-1">
      {/* Barrier identity */}
      <h2 className="text-xl font-semibold mb-1">{barrier.name}</h2>
      <p className="text-sm text-gray-500 mb-3">{barrier.barrierRole}</p>

      {/* Barrier classification metadata (Bug #4 fix) */}
      {(pred.barrier_type_display || pred.lod_display) && (
        <div className="flex flex-wrap gap-2 mb-3">
          {pred.barrier_type_display && (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
              {pred.barrier_type_display}
            </span>
          )}
          {pred.lod_display && (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700">
              {pred.lod_display}
            </span>
          )}
        </div>
      )}

      {/* Risk score badge */}
      <RiskScoreBadge
        probability={pred.model1_probability}
        riskLevel={barrier.riskLevel}
      />

      {/* Model 1 SHAP waterfall — primary risk factors */}
      <ShapWaterfall
        shap={pred.model1_shap}
        baseValue={pred.model1_base_value}
        featureDisplayNames={featureDisplayNames}
      />

      {/* Model 2 SHAP waterfall — human factor sensitivity (SHAP-03: separate section) */}
      {hasModel2 && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <h3 className="text-base font-semibold mb-2">Human Factor Sensitivity</h3>
          <ShapWaterfall
            shap={pred.model2_shap}
            baseValue={pred.model2_base_value}
            featureDisplayNames={featureDisplayNames}
          />
        </div>
      )}

      {/* Evidence section — loads on-demand (D-15) */}
      <div className="mt-4 pt-4 border-t border-gray-200">
        <EvidenceSection
          barrierId={barrier.id}
          barrier={barrier}
          eventDescription={eventDescription}
          prediction={pred}
        />
      </div>
    </div>
  )
}
