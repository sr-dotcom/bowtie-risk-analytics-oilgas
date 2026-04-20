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

/** Display names for all 18 cascading model features (5 target + 6 cond + 7 context). */
export const CASCADING_FEATURE_DISPLAY_NAMES: Record<string, string> = {
  // Target barrier features
  'lod_industry_standard_target': 'Target LoD category',
  'barrier_level_target': 'Target role',
  'pathway_sequence_target': 'Target pathway position',
  'lod_numeric_target': 'Target LoD tier',
  'num_threats_in_lod_numeric_target': 'Threats at target tier',
  // Conditioning barrier features
  'lod_industry_standard_cond': 'Cond. LoD category',
  'barrier_level_cond': 'Cond. role',
  'barrier_condition_cond': 'Cond. condition',
  'pathway_sequence_cond': 'Cond. pathway position',
  'lod_numeric_cond': 'Cond. LoD tier',
  'num_threats_in_lod_numeric_cond': 'Threats at cond. tier',
  // Incident-level context features
  'total_prev_barriers_incident': 'Prevention barriers in incident',
  'total_mit_barriers_incident': 'Mitigation barriers in incident',
  'num_threats_in_sequence': 'Threats in pathway sequence',
  'flag_environmental_threat': 'Environmental threat present',
  'flag_electrical_failure': 'Electrical failure present',
  'flag_procedural_error': 'Procedural error present',
  'flag_mechanical_failure': 'Mechanical failure present',
}

/** Look up a human-readable display name for any SHAP feature (legacy or cascading).
 *  Falls back to the raw feature name — never returns null or empty string. */
export function getFeatureDisplayName(feature: string): string {
  return FEATURE_DISPLAY_NAMES[feature] ?? CASCADING_FEATURE_DISPLAY_NAMES[feature] ?? feature
}
