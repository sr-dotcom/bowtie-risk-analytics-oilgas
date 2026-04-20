// Risk levels (from UI-SPEC risk level color mapping)
export type RiskLevel = 'red' | 'amber' | 'green' | 'unanalyzed'

// ---------------------------------------------------------------------------
// Scenario types — match data/demo_scenarios/*.json shape (S05a/T01)
// ---------------------------------------------------------------------------

export interface ScenarioBarrier {
  control_id: string
  name: string
  barrier_level: string          // "prevention" | "mitigation"
  lod_industry_standard?: string
  lod_numeric?: number
  barrier_condition: string      // "effective" | "degraded" | "ineffective"
  barrier_type: string
  barrier_role: string
  linked_threat_ids?: string[]
  description?: string
  line_of_defense?: string
}

export interface ScenarioThreat {
  threat_id: string
  name: string
  description: string | null
}

export interface Scenario {
  scenario_id: string
  source_agency: string
  incident_id: string
  top_event: string
  context?: {
    region?: string
    operator?: string
    operating_phase?: string
    materials?: string[]
  }
  barriers: ScenarioBarrier[]
  threats: ScenarioThreat[]
  pif_context?: Record<string, Record<string, boolean>>
}

// ---------------------------------------------------------------------------
// Cascading API types — mirroring src/api/schemas.py cascading section (S05a/T01)
// ---------------------------------------------------------------------------

export interface CascadingRequest {
  scenario: Scenario
  conditioning_barrier_id: string
}

export interface CascadingShapValue {
  feature: string
  value: number
  display_name: string
}

export type RiskBand = 'HIGH' | 'MEDIUM' | 'LOW'

export interface BarrierPrediction {
  target_barrier_id: string
  y_fail_probability: number
  risk_band: RiskBand
  shap_values: CascadingShapValue[]
}

export interface PredictCascadingResponse {
  predictions: BarrierPrediction[]
  explanation_unavailable: boolean
}

export interface RankedBarrier {
  target_barrier_id: string
  composite_risk_score: number
}

export interface RankTargetsResponse {
  ranked_barriers: RankedBarrier[]
}

export interface ExplainCascadingRequest {
  conditioning_barrier_id: string
  target_barrier_id: string
  bowtie_context: Scenario
}

export interface EvidenceSnippet {
  incident_id: string
  source_agency: string
  text: string
  score: number
}

export interface DegradationContext {
  pif_mentions: string[]
  recommendations: string[]
  barrier_condition: string
}

export interface ExplainCascadingResponse {
  narrative_text: string
  evidence_snippets: EvidenceSnippet[]
  degradation_context: DegradationContext
  narrative_unavailable: boolean
}

export interface RiskThresholds {
  p80: number
  p60: number
}

// ---------------------------------------------------------------------------
// API request/response types (mirroring src/api/schemas.py exactly)
// ---------------------------------------------------------------------------

export interface PredictRequest {
  // Barrier-level categoricals (required)
  side: string
  barrier_type: string
  line_of_defense: string
  barrier_family: string
  // Incident-level categoricals (optional — backend defaults to 'loss_of_containment' / 'UNKNOWN')
  top_event_category?: string
  source_agency?: string
  // PIF booleans (9 active features — all optional, backend defaults to 0)
  // pif_fatigue, pif_workload, pif_time_pressure excluded from training scope
  pif_competence?: number
  pif_communication?: number
  pif_situational_awareness?: number
  pif_procedures?: number
  pif_tools_equipment?: number
  pif_safety_culture?: number
  pif_management_of_change?: number
  pif_supervision?: number
  pif_training?: number
  // Numeric features (optional — backend defaults to 0)
  supporting_text_count?: number
  primary_threat_category?: number
  pathway_sequence?: number
  upstream_failure_rate?: number
}

export interface ShapValue {
  feature: string
  value: number
  category: 'barrier' | 'incident_context'
}

export interface FeatureMetadata {
  name: string
  category: string
}

export interface DegradationFactor {
  factor: string         // Display name: "Operator Fatigue"
  source_feature: string // Original pif_* key: "pif_fatigue"
  contribution: number   // SHAP value
  description: string    // Optional description
}

export interface PredictResponse {
  model1_probability: number
  model2_probability: number
  model1_shap: ShapValue[]
  model2_shap: ShapValue[]
  model1_base_value: number
  model2_base_value: number
  feature_metadata: FeatureMetadata[]
  // Phase 8: Process safety terminology fields
  degradation_factors: DegradationFactor[]
  risk_level: string              // "High" | "Medium" | "Low"
  barrier_type_display: string    // Mapped display name
  lod_display: string             // Mapped display name
  barrier_condition_display: string  // Mapped barrier condition characterization (Fidel-#59)
}

export interface ExplainRequest {
  barrier_family: string
  barrier_type: string
  side: string
  barrier_role: string
  event_description: string
  shap_factors?: ShapValue[]
  risk_level?: string           // H/M/L context from /predict result
}

export interface CitationResponse {
  incident_id: string
  control_id: string
  barrier_name: string
  barrier_family: string
  supporting_text: string
  relevance_score: number
  incident_summary: string
}

export interface ExplainResponse {
  narrative: string
  citations: CitationResponse[]
  retrieval_confidence: number
  model_used: string
  recommendations: string  // Phase 8 (D-12)
}

// ---------------------------------------------------------------------------
// Frontend-specific types
// ---------------------------------------------------------------------------

// PIF flags — 9 active features matching training scope.
// pif_fatigue, pif_workload, pif_time_pressure excluded (not in training scope).
export interface PifFlags {
  pif_competence: number
  pif_communication: number
  pif_situational_awareness: number
  pif_procedures: number
  pif_tools_equipment: number
  pif_safety_culture: number
  pif_management_of_change: number
  pif_supervision: number
  pif_training: number
}

/** Default PIF values based on training data frequency (top 5 PIFs > 50% prevalence).
 *  procedures=84%, situational_awareness=73%, tools_equipment=67%,
 *  supervision=53%, safety_culture=52% */
export const DEFAULT_PIF_FLAGS: PifFlags = {
  pif_competence: 0,
  pif_communication: 0,
  pif_situational_awareness: 1,
  pif_procedures: 1,
  pif_tools_equipment: 1,
  pif_safety_culture: 1,
  pif_management_of_change: 0,
  pif_supervision: 1,
  pif_training: 0,
}

/** Display names for PIF flags (matches pif_to_degradation.yaml — 9 active features) */
export const PIF_DISPLAY_NAMES: Record<keyof PifFlags, string> = {
  pif_competence: 'Operator Competence',
  pif_communication: 'Communication',
  pif_situational_awareness: 'Situational Awareness',
  pif_procedures: 'Procedures',
  pif_tools_equipment: 'Tools & Equipment',
  pif_safety_culture: 'Safety Culture',
  pif_management_of_change: 'Management of Change',
  pif_supervision: 'Supervision',
  pif_training: 'Training',
}

export interface AprioriRule {
  antecedent: string
  consequent: string
  support: number
  confidence: number
  lift: number
  count: number
}

export interface Barrier {
  id: string
  name: string
  side: 'prevention' | 'mitigation'
  barrier_type: string
  barrier_family: string
  line_of_defense: string
  barrierRole: string
  riskLevel: RiskLevel
  probability?: number
  pathway_sequence?: number
  upstream_failure_rate?: number
}

export interface Threat {
  id: string
  name: string
  description: string
}

export interface Consequence {
  id: string
  name: string
  description: string
  severity?: string  // 'critical' | 'high' | 'medium' | 'low' — optional
}
