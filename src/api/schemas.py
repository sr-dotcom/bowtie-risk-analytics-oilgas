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

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Prediction schemas (D-01, D-02)
# ---------------------------------------------------------------------------

class PredictRequest(BaseModel):
    """POST /predict request body — 18 barrier feature fields (D-01).

    The 5 categorical fields are required strings.
    The 12 PIF boolean fields default to 0.
    supporting_text_count defaults to 0.
    """

    model_config = ConfigDict(strict=False)

    # Categorical barrier features (required)
    side: str
    barrier_type: str
    line_of_defense: str
    barrier_family: str
    source_agency: str

    # PIF boolean fields (default 0 — may be absent in partial requests)
    pif_competence: int = 0
    pif_fatigue: int = 0
    pif_communication: int = 0
    pif_situational_awareness: int = 0
    pif_procedures: int = 0
    pif_workload: int = 0
    pif_time_pressure: int = 0
    pif_tools_equipment: int = 0
    pif_safety_culture: int = 0
    pif_management_of_change: int = 0
    pif_supervision: int = 0
    pif_training: int = 0

    # Numeric feature
    supporting_text_count: int = 0


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

    barrier_family: str
    barrier_type: str
    side: str
    barrier_role: str           # text for RAG barrier query
    event_description: str      # text for RAG incident query
    shap_factors: list[ShapValue] | None = None  # optional SHAP enrichment
    risk_level: str = ""        # optional H/M/L context from /predict result


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

    type: str
    path: str
    loaded: bool


class RagInfo(BaseModel):
    """Info about the loaded RAG corpus (D-08)."""

    corpus_size: int
    threshold: float


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
