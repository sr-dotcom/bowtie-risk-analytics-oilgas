/**
 * Single source of truth for SHAP feature display names and hidden feature set.
 *
 * Import from this module in DetailPanel, TopAtRiskBarriers, DriversHF, RankedBarriers
 * instead of duplicating these constants.
 */

import { PIF_DISPLAY_NAMES } from '@/lib/types'

/** Incident-level features that are non-actionable — excluded from SHAP charts.
 *  source_agency was removed from the model (users always default to UNKNOWN).
 *  primary_threat_category is a legitimate feature but non-actionable for end users. */
export const SHAP_HIDDEN_FEATURES = new Set(['primary_threat_category'])

/** Display names for all SHAP features: barrier-category + PIF + numeric. */
export const FEATURE_DISPLAY_NAMES: Record<string, string> = {
  // Barrier-category features
  barrier_family: 'Barrier Family',
  side: 'Pathway Position',
  barrier_type: 'Barrier Type',
  line_of_defense: 'Line of Defense',
  primary_threat_category: 'Threat Category',
  supporting_text_count: 'Evidence Volume',
  // Numeric incident features
  pathway_sequence: 'Pathway Sequence',
  upstream_failure_rate: 'Upstream Failure Rate',
  // Not in the current feature set but kept for display-name completeness
  top_event_category: 'Top Event Category',
  // PIF features (from lib/types.ts PIF_DISPLAY_NAMES)
  ...(PIF_DISPLAY_NAMES as Record<string, string>),
}

/** Display names for cascading model features (conditioner/target pairs). */
export const CASCADING_FEATURE_DISPLAY_NAMES: Record<string, string> = {
  barrier_condition_cond: 'Barrier condition (conditioner)',
  barrier_condition_target: 'Barrier condition',
  lod_numeric_cond: 'Line of defense (conditioner)',
  lod_numeric_target: 'Line of defense',
  barrier_level_cond: 'Pathway (conditioner)',
  barrier_level_target: 'Pathway',
  lod_industry_standard_cond: 'Industry standard LOD (conditioner)',
  lod_industry_standard_target: 'Industry standard LOD',
  barrier_type_cond: 'Barrier type (conditioner)',
  barrier_type_target: 'Barrier type',
}

/** Look up a human-readable display name for any SHAP feature (legacy or cascading). */
export function getFeatureDisplayName(feature: string): string | null {
  return FEATURE_DISPLAY_NAMES[feature] ?? CASCADING_FEATURE_DISPLAY_NAMES[feature] ?? null
}
