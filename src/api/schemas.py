"""Pydantic request/response models for the Bowtie Risk Analytics API.

All models use ConfigDict(strict=False) per project convention.
Schema decisions are from 05-CONTEXT.md:
  D-01: PredictRequest — 18 fields matching feature_names.json
  D-02: PredictResponse — probabilities + SHAP per model + feature_metadata
  D-03: ExplainRequest — barrier_role and event_description for dual-axis RAG
  D-04: ExplainResponse — narrative, citations, retrieval_confidence, model_used
  D-08: HealthResponse — status, models dict, rag info, uptime_seconds
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Prediction schemas (D-01, D-02)
# ---------------------------------------------------------------------------

class PredictRequest(BaseModel):
    """POST /predict request body — 18 barrier/incident feature fields (D-01).

    Feature layout matches feature_names.json (18 features, derived from the
    558-row training scope):
      Barrier categoricals (4 required): side, barrier_type, line_of_defense,
        barrier_family.
      Incident-level categoricals (2 with defaults): source_agency,
        primary_threat_category.
      PIF booleans (9, all default 0): pif_* features (fatigue/workload/
        time_pressure excluded from training scope).
      Numeric (3 with defaults): supporting_text_count, pathway_sequence,
        upstream_failure_rate.

    Callers that omit source_agency get "UNKNOWN".
    Callers that omit primary_threat_category get "unknown_threat" (maps to
    the encoder's unknown-value fallback).
    """

    model_config = ConfigDict(strict=False)

    # Barrier-level categoricals (required)
    side: str = Field(..., max_length=50)
    barrier_type: str = Field(..., max_length=200)
    line_of_defense: str = Field(..., max_length=50)
    barrier_family: str = Field(..., max_length=200)

    # Incident-level categoricals (optional — safe defaults for API callers)
    source_agency: str = Field("UNKNOWN", max_length=100)
    primary_threat_category: str = Field("unknown_threat", max_length=200)

    # PIF boolean fields — 9 active features (default 0)
    # pif_fatigue, pif_workload, pif_time_pressure excluded from training scope
    pif_competence: int = Field(0, ge=0, le=1)
    pif_communication: int = Field(0, ge=0, le=1)
    pif_situational_awareness: int = Field(0, ge=0, le=1)
    pif_procedures: int = Field(0, ge=0, le=1)
    pif_tools_equipment: int = Field(0, ge=0, le=1)
    pif_safety_culture: int = Field(0, ge=0, le=1)
    pif_management_of_change: int = Field(0, ge=0, le=1)
    pif_supervision: int = Field(0, ge=0, le=1)
    pif_training: int = Field(0, ge=0, le=1)

    # Numeric features (default 0)
    supporting_text_count: int = Field(0, ge=0, le=1000)
    pathway_sequence: int = Field(0, ge=0, le=100)
    upstream_failure_rate: float = Field(0.0, ge=0.0, le=1.0)


class ShapValue(BaseModel):
    """A single SHAP feature contribution (D-02)."""

    feature: str
    value: float
    category: str  # "barrier" or "incident_context"


class FeatureMetadata(BaseModel):
    """Feature name with its category from feature_names.json (D-02)."""

    name: str
    category: str


class DegradationFactor(BaseModel):
    """A PIF mapped to process-safety degradation factor terminology (D-03).

    Used in PredictResponse.degradation_factors to translate internal pif_*
    feature names to domain-standard process safety display names.
    """

    factor: str           # Display name from pif_to_degradation.yaml (e.g., "Operator Fatigue")
    source_feature: str   # Original pif_* field name (e.g., "pif_fatigue") — for frontend correlation
    contribution: float   # SHAP value (same as ShapValue.value)
    description: str = "" # Optional description


class PredictResponse(BaseModel):
    """POST /predict response body (D-02, Phase 8 extensions).

    Contains probabilities + SHAP values for both models, plus feature metadata.
    model1 = barrier failure prediction.
    model2 = human factor sensitivity prediction.

    Phase 8 additions (Fidel review):
      degradation_factors — PIF SHAP values mapped to process safety names
      risk_level — High/Medium/Low from probability thresholds
      barrier_type_display — Mapped display name from barrier_types.yaml
      lod_display — Mapped display name from lod_categories.yaml
      barrier_condition_display — Mapped display name from barrier_condition.yaml (Fidel-#59)
    """

    model1_probability: float
    model2_probability: float
    model1_shap: list[ShapValue]
    model2_shap: list[ShapValue]
    model1_base_value: float
    model2_base_value: float
    feature_metadata: list[FeatureMetadata]
    # Phase 8 — process safety terminology (Fidel-#6, #9, #12, #34, #59, #63)
    degradation_factors: list[DegradationFactor] = []
    risk_level: str = ""              # "High" | "Medium" | "Low"
    barrier_type_display: str = ""    # Mapped display name from barrier_types.yaml
    lod_display: str = ""             # Mapped display name from lod_categories.yaml
    barrier_condition_display: str = ""  # Mapped display name from barrier_condition.yaml (Fidel-#59)


# ---------------------------------------------------------------------------
# Explanation schemas (D-03, D-04) — used in Plan 02 /explain endpoint
# ---------------------------------------------------------------------------

class ExplainRequest(BaseModel):
    """POST /explain request body (D-03).

    barrier_role and event_description feed the dual-axis RAG retrieval.
    shap_factors is optional SHAP enrichment for the LLM prompt.
    """

    model_config = ConfigDict(strict=False)

    barrier_family: str = Field(..., max_length=200)
    barrier_type: str = Field(..., max_length=200)
    side: str = Field(..., max_length=50)
    barrier_role: str = Field(..., max_length=2000)
    event_description: str = Field(..., max_length=5000)
    shap_factors: list[ShapValue] | None = Field(None, max_length=50)
    risk_level: str = Field("", max_length=20)


class CitationResponse(BaseModel):
    """A single evidence citation in /explain response (D-04)."""

    incident_id: str
    control_id: str
    barrier_name: str
    barrier_family: str
    supporting_text: str
    relevance_score: float
    incident_summary: str = ""  # Incident-level summary for "Similar Incidents" display


class ExplainResponse(BaseModel):
    """POST /explain response body (D-04).

    Mirrors ExplanationResult from src/rag/explainer.py.
    """

    narrative: str
    citations: list[CitationResponse]
    retrieval_confidence: float
    model_used: str
    recommendations: str = ""  # Phase 8 (D-12): empty for low-confidence path


# ---------------------------------------------------------------------------
# Health schemas (D-08)
# ---------------------------------------------------------------------------

class ModelInfo(BaseModel):
    """Info about a single loaded ML model (D-08)."""

    name: str
    loaded: bool


class RagInfo(BaseModel):
    """Info about the loaded RAG corpus (D-08)."""

    corpus_size: int


class HealthResponse(BaseModel):
    """GET /health response body (D-08)."""

    status: str
    models: dict[str, ModelInfo]
    rag: RagInfo
    uptime_seconds: float


# ---------------------------------------------------------------------------
# Error schema (Claude's discretion — standard error body)
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Standard error response body."""

    error: str
    detail: str = ""


# ---------------------------------------------------------------------------
# Apriori co-failure rules schemas (S03)
# ---------------------------------------------------------------------------

class AprioriRule(BaseModel):
    """A single Apriori association rule between barrier families (S03)."""

    model_config = ConfigDict(strict=False)

    antecedent: str
    consequent: str
    support: float
    confidence: float
    lift: float
    count: int


class AprioriRulesResponse(BaseModel):
    """GET /apriori-rules response body (S03)."""

    rules: list[AprioriRule]
    n_incidents: int = 0
    generated_at: str = ""


# ---------------------------------------------------------------------------
# Cascading prediction schemas (S03/T02)
# ---------------------------------------------------------------------------

class CascadingRequest(BaseModel):
    """POST /predict-cascading and /rank-targets request body."""

    model_config = ConfigDict(strict=False)

    scenario: dict  # full bowtie config per data/demo_scenarios/*.json shape
    conditioning_barrier_id: str


class CascadingShapValue(BaseModel):
    """A single SHAP value from the cascading model (distinct from /predict ShapValue)."""

    feature: str
    value: float
    display_name: str = ""


class CascadingBarrierPrediction(BaseModel):
    """Per-target barrier prediction from the cascading model."""

    target_barrier_id: str
    y_fail_probability: float
    risk_band: Literal["HIGH", "MEDIUM", "LOW"]
    shap_values: list[CascadingShapValue]


class PredictCascadingResponse(BaseModel):
    """POST /predict-cascading response body."""

    predictions: list[CascadingBarrierPrediction]
    explanation_unavailable: bool = False


class RankedBarrier(BaseModel):
    """Lightweight ranked barrier entry (no SHAP) for /rank-targets."""

    target_barrier_id: str
    composite_risk_score: float


class RankTargetsResponse(BaseModel):
    """POST /rank-targets response body."""

    ranked_barriers: list[RankedBarrier]


class ExplainCascadingRequest(BaseModel):
    """POST /explain-cascading request body."""

    model_config = ConfigDict(strict=False)

    conditioning_barrier_id: str
    target_barrier_id: str
    bowtie_context: dict  # full scenario


class EvidenceSnippet(BaseModel):
    """A single evidence snippet from RAG retrieval."""

    incident_id: str
    source_agency: str
    text: str
    score: float


class DegradationContext(BaseModel):
    """Degradation context extracted from RAG results and scenario PIF data."""

    pif_mentions: list[str]
    recommendations: list[str]
    barrier_condition: str


class ExplainCascadingResponse(BaseModel):
    """POST /explain-cascading response body."""

    narrative_text: str
    evidence_snippets: list[EvidenceSnippet]
    degradation_context: DegradationContext
    narrative_unavailable: bool = False


class GoneResponse(BaseModel):
    """HTTP 410 Gone response body for deprecated endpoints."""

    error: Literal["gone"] = "gone"
    migrate_to: str


# ---------------------------------------------------------------------------
# Narrative synthesis schemas (T2b)
# ---------------------------------------------------------------------------

class ShapFeature(BaseModel):
    """A single SHAP feature for the narrative synthesis prompt."""

    model_config = ConfigDict(strict=False)

    feature: str
    value: float
    display_name: str = ""


class IncidentContext(BaseModel):
    """A single historical incident context for the narrative synthesis prompt.

    summary_text and barrier_failure_description are trimmed in validators
    so the LLM prompt stays within budget regardless of caller input length.
    """

    model_config = ConfigDict(strict=False)

    incident_id: str
    summary_text: str = ""
    barrier_failure_description: str = ""

    @field_validator("summary_text", mode="before")
    @classmethod
    def _trim_summary(cls, v: object) -> str:
        return str(v)[:500] if v else ""

    @field_validator("barrier_failure_description", mode="before")
    @classmethod
    def _trim_description(cls, v: object) -> str:
        return str(v)[:200] if v else ""


class NarrativeSynthesisRequest(BaseModel):
    """POST /narrative-synthesis request body (T2b)."""

    model_config = ConfigDict(strict=False)

    top_barrier_name: str = Field(max_length=200)
    top_barrier_risk_band: Literal["HIGH", "MEDIUM", "LOW"]
    top_barrier_probability: float
    shap_top_features: list[ShapFeature]
    rag_incident_contexts: list[IncidentContext]
    total_barriers: int
    high_risk_count: int
    top_event: str = Field(max_length=200)
    similar_incidents_count: int


class NarrativeSynthesisResponse(BaseModel):
    """POST /narrative-synthesis response body (T2b)."""

    narrative: str
    model: str
    generated_at: datetime
