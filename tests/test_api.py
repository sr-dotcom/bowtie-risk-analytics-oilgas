"""Tests for src/api/main.py — FastAPI /predict, /explain, and /health endpoints.

All tests use mocked BarrierPredictor and BarrierExplainer via a no-op lifespan
fixture. No real model artifacts are required — works in CI without data/models/.

Tests:
  test_predict_valid_returns_200      — full payload, verify response shape
  test_predict_missing_required_field_returns_422 — missing `side` → 422
  test_predict_pif_defaults           — only 4 required barrier categoricals → all optional fields default
  test_health_returns_200             — GET /health → status=ok + fields present
  test_health_model_info              — model1 type=XGBoost, loaded=True
  test_predict_does_not_reload_resources — two requests → __init__ not called again
  test_explain_valid_returns_200      — valid /explain payload → 200 + response shape
  test_explain_missing_required_field_returns_422 — missing barrier_role → 422
  test_explain_with_shap_factors      — shap_factors list → 200, SHAP dict passed
  test_explain_without_shap_factors   — no shap_factors → 200, None passed
  test_explain_confidence_gate_fires  — low confidence → narrative reflects gate
  test_explain_calls_via_to_thread    — verify explainer.explain called once
  test_openapi_schema_has_all_endpoints — /predict, /explain, /health in OpenAPI
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.mapping_loader import MappingConfig
from src.modeling.predict import PredictionResult
from src.rag.explainer import Citation
from src.rag.rag_agent import ExplanationResult
from src.rag.config import CONFIDENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_PREDICT_PAYLOAD: dict = {
    "side": "left",
    "barrier_type": "engineering",
    "line_of_defense": "1",
    "barrier_family": "alarm",
    # source_agency and primary_threat_category are incident-level, optional
    "source_agency": "BSEE",
    "primary_threat_category": "mechanical_failure",
    # 9 active PIF features (fatigue/workload/time_pressure excluded from training scope)
    "pif_competence": 1,
    "pif_communication": 1,
    "pif_situational_awareness": 0,
    "pif_procedures": 1,
    "pif_tools_equipment": 0,
    "pif_safety_culture": 0,
    "pif_management_of_change": 0,
    "pif_supervision": 0,
    "pif_training": 0,
    "supporting_text_count": 3,
    "pathway_sequence": 0,
    "upstream_failure_rate": 0.0,
}

VALID_EXPLAIN_PAYLOAD: dict = {
    "barrier_family": "pressure_relief",
    "barrier_type": "engineering",
    "side": "left",
    "barrier_role": "Pressure relief valve designed to prevent overpressure",
    "event_description": "Loss of containment due to overpressure in separator vessel",
}

_FEATURE_NAMES = [
    {"name": "side", "category": "barrier"},
    {"name": "barrier_type", "category": "barrier"},
    {"name": "line_of_defense", "category": "barrier"},
    {"name": "barrier_family", "category": "barrier"},
    # incident-level categoricals
    {"name": "source_agency", "category": "incident_context"},
    {"name": "primary_threat_category", "category": "incident_context"},
    # 9 active PIF features (fatigue/workload/time_pressure excluded from training scope)
    {"name": "pif_competence", "category": "incident_context"},
    {"name": "pif_communication", "category": "incident_context"},
    {"name": "pif_situational_awareness", "category": "incident_context"},
    {"name": "pif_procedures", "category": "incident_context"},
    {"name": "pif_tools_equipment", "category": "incident_context"},
    {"name": "pif_safety_culture", "category": "incident_context"},
    {"name": "pif_management_of_change", "category": "incident_context"},
    {"name": "pif_supervision", "category": "incident_context"},
    {"name": "pif_training", "category": "incident_context"},
    # numeric
    {"name": "supporting_text_count", "category": "barrier"},
    {"name": "pathway_sequence", "category": "barrier"},
    {"name": "upstream_failure_rate", "category": "barrier"},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_explainer(
    narrative: str = "Evidence narrative text.",
    confidence: float = 0.78,
    recommendations: str = "- Increase inspection frequency.\n- Review maintenance procedures.",
) -> MagicMock:
    """Create a mock BarrierExplainer with a canned ExplanationResult."""
    explainer = MagicMock()
    explainer.explain.return_value = ExplanationResult(
        context_text="context",
        results=[],
        metadata={},
        narrative=narrative,
        citations=[
            Citation(
                incident_id="INC-001",
                control_id="CTL-001",
                barrier_name="Pressure Relief Valve",
                barrier_family="pressure_relief",
                supporting_text="Valve failed to activate during overpressure event.",
                relevance_score=0.82,
                incident_summary="A pressure vessel failure at an offshore platform led to loss of containment.",
            ),
        ],
        retrieval_confidence=confidence,
        model_used="claude-haiku-4-5-20251001",
        recommendations=recommendations,
    )
    return explainer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_predictor() -> MagicMock:
    """Mock BarrierPredictor returning a fixed PredictionResult."""
    predictor = MagicMock()
    predictor.feature_names = _FEATURE_NAMES
    shap_dict = {f["name"]: 0.1 for f in _FEATURE_NAMES}
    predictor.predict.return_value = PredictionResult(
        model1_probability=0.73,
        model2_probability=0.42,
        model1_shap_values=shap_dict,
        model2_shap_values=shap_dict,
        model1_base_value=-0.5,
        model2_base_value=-0.3,
    )
    return predictor


@pytest.fixture
def client(mock_predictor: MagicMock) -> TestClient:
    """TestClient with mocked resources — no real model loading.

    Uses a no-op lifespan so BarrierPredictor.__init__ is never called.
    Injects mocked state directly onto app.state before the client starts.
    """

    @asynccontextmanager
    async def noop_lifespan(app):  # type: ignore[type-arg]
        yield

    app = create_app(lifespan_override=noop_lifespan)
    app.state.predictor = mock_predictor
    app.state.explainer = _make_mock_explainer()
    app.state.start_time = time.monotonic()
    app.state.rag_corpus_size = 3253
    app.state.mapping_config = MappingConfig.load()
    app.state.apriori_rules = [
        {
            "antecedent": "communication",
            "consequent": "procedures",
            "support": 0.072,
            "confidence": 0.732,
            "lift": 1.42,
            "count": 52,
        }
    ]

    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_predict_valid_returns_200(client: TestClient) -> None:
    """POST /predict with valid 18-field payload returns 200 with correct shape."""
    resp = client.post("/predict", json=VALID_PREDICT_PAYLOAD)
    assert resp.status_code == 200

    data = resp.json()

    # Top-level probability fields
    assert "model1_probability" in data
    assert "model2_probability" in data
    assert isinstance(data["model1_probability"], float)
    assert isinstance(data["model2_probability"], float)
    assert data["model1_probability"] == pytest.approx(0.73)
    assert data["model2_probability"] == pytest.approx(0.42)

    # SHAP lists — exactly 18 items each
    assert "model1_shap" in data
    assert "model2_shap" in data
    assert len(data["model1_shap"]) == 18
    assert len(data["model2_shap"]) == 18

    # Each ShapValue has feature, value, category keys
    shap_item = data["model1_shap"][0]
    assert "feature" in shap_item
    assert "value" in shap_item
    assert "category" in shap_item

    # Base values
    assert "model1_base_value" in data
    assert "model2_base_value" in data

    # Feature metadata — exactly 18 items
    assert "feature_metadata" in data
    assert len(data["feature_metadata"]) == 18
    fm_item = data["feature_metadata"][0]
    assert "name" in fm_item
    assert "category" in fm_item

    # Phase 8 fields — process safety terminology
    assert "degradation_factors" in data
    assert isinstance(data["degradation_factors"], list)
    assert "risk_level" in data
    assert data["risk_level"] in ("High", "Medium", "Low")
    assert "barrier_type_display" in data
    assert isinstance(data["barrier_type_display"], str)
    assert "lod_display" in data
    assert isinstance(data["lod_display"], str)
    assert "barrier_condition_display" in data
    assert isinstance(data["barrier_condition_display"], str)


def test_predict_missing_required_field_returns_422(client: TestClient) -> None:
    """POST /predict with missing required field `side` returns 422."""
    payload = {k: v for k, v in VALID_PREDICT_PAYLOAD.items() if k != "side"}
    resp = client.post("/predict", json=payload)
    assert resp.status_code == 422


def test_predict_pif_defaults(client: TestClient, mock_predictor: MagicMock) -> None:
    """POST /predict with only 4 required barrier categoricals defaults all optional fields to 0."""
    minimal_payload = {
        "side": "left",
        "barrier_type": "engineering",
        "line_of_defense": "1",
        "barrier_family": "alarm",
    }
    resp = client.post("/predict", json=minimal_payload)
    assert resp.status_code == 200

    # Verify the predictor was called with defaulted PIFs (9 active features)
    called_features = mock_predictor.predict.call_args[0][0]
    assert called_features["pif_competence"] == 0
    assert called_features["pif_communication"] == 0
    assert called_features["pif_situational_awareness"] == 0
    assert called_features["pif_procedures"] == 0
    assert called_features["pif_tools_equipment"] == 0
    assert called_features["pif_safety_culture"] == 0
    assert called_features["pif_management_of_change"] == 0
    assert called_features["pif_supervision"] == 0
    assert called_features["pif_training"] == 0
    assert called_features["supporting_text_count"] == 0
    # Incident-level categoricals get safe defaults
    assert called_features["source_agency"] == "UNKNOWN"
    assert called_features["primary_threat_category"] == "unknown_threat"

    # Response has 18 SHAP values (matches _FEATURE_NAMES length)
    data = resp.json()
    assert len(data["model1_shap"]) == 18


def test_health_returns_200(client: TestClient) -> None:
    """GET /health returns 200 with status=ok and all required fields."""
    resp = client.get("/health")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "ok"
    assert "models" in data
    assert "model1" in data["models"]
    assert "model2" in data["models"]
    assert "rag" in data
    assert data["rag"]["corpus_size"] == 3253
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0.0


def test_health_model_info(client: TestClient) -> None:
    """GET /health model info has loaded=True and name fields."""
    resp = client.get("/health")
    assert resp.status_code == 200

    data = resp.json()
    model1 = data["models"]["model1"]
    assert model1["loaded"] is True
    assert model1["name"] == "barrier_failure"

    model2 = data["models"]["model2"]
    assert model2["loaded"] is True
    assert model2["name"] == "human_factor"


def test_predict_does_not_reload_resources(
    client: TestClient, mock_predictor: MagicMock
) -> None:
    """Two /predict calls invoke predictor.predict() twice but __init__ never called.

    Resources are loaded once in lifespan — not per-request (D-06, API-04).
    """
    # Make two separate requests
    resp1 = client.post("/predict", json=VALID_PREDICT_PAYLOAD)
    resp2 = client.post("/predict", json=VALID_PREDICT_PAYLOAD)

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    # predict() was called exactly twice — once per request
    assert mock_predictor.predict.call_count == 2

    # BarrierPredictor.__init__ was never invoked (it's a MagicMock, not instantiated)
    # The fixture creates the mock before injecting it — __init__ of the real class
    # was never called. We verify by confirming the mock itself was not re-created.
    assert mock_predictor is client.app.state.predictor  # same object throughout


# ---------------------------------------------------------------------------
# /explain tests (Plan 02 — API-02, API-05)
# ---------------------------------------------------------------------------

def test_explain_valid_returns_200(client: TestClient) -> None:
    """POST /explain with valid payload returns 200 with correct response shape (D-04)."""
    resp = client.post("/explain", json=VALID_EXPLAIN_PAYLOAD)
    assert resp.status_code == 200

    data = resp.json()

    # Required response fields (D-04)
    assert "narrative" in data
    assert "citations" in data
    assert "retrieval_confidence" in data
    assert "model_used" in data

    # Type checks
    assert isinstance(data["narrative"], str)
    assert len(data["narrative"]) > 0
    assert isinstance(data["citations"], list)
    assert len(data["citations"]) == 1
    assert isinstance(data["retrieval_confidence"], float)
    assert isinstance(data["model_used"], str)

    # Phase 8 fields
    assert "recommendations" in data
    assert isinstance(data["recommendations"], str)
    assert len(data["recommendations"]) > 0

    # Citation shape
    citation = data["citations"][0]
    assert citation["incident_id"] == "INC-001"
    assert citation["control_id"] == "CTL-001"
    assert citation["barrier_name"] == "Pressure Relief Valve"
    assert citation["barrier_family"] == "pressure_relief"
    assert isinstance(citation["supporting_text"], str)
    assert isinstance(citation["relevance_score"], float)
    assert "incident_summary" in citation
    assert isinstance(citation["incident_summary"], str)


def test_explain_missing_required_field_returns_422(client: TestClient) -> None:
    """POST /explain without required `barrier_role` returns 422."""
    payload = {k: v for k, v in VALID_EXPLAIN_PAYLOAD.items() if k != "barrier_role"}
    resp = client.post("/explain", json=payload)
    assert resp.status_code == 422


def test_explain_with_shap_factors(client: TestClient) -> None:
    """POST /explain with shap_factors list returns 200 and passes SHAP dict to explainer."""
    payload = {
        **VALID_EXPLAIN_PAYLOAD,
        "shap_factors": [
            {"feature": "barrier_family", "value": 0.45, "category": "barrier"},
            {"feature": "pif_procedures", "value": 0.32, "category": "incident_context"},
        ],
    }
    resp = client.post("/explain", json=payload)
    assert resp.status_code == 200

    # Verify explainer.explain was called with the SHAP dict
    mock_explainer = client.app.state.explainer
    assert mock_explainer.explain.call_count == 1
    call_kwargs = mock_explainer.explain.call_args[1]
    assert call_kwargs.get("shap_factors") == {
        "barrier_family": 0.45,
        "pif_procedures": 0.32,
    }


def test_explain_without_shap_factors(client: TestClient) -> None:
    """POST /explain without shap_factors returns 200 and passes None to explainer."""
    resp = client.post("/explain", json=VALID_EXPLAIN_PAYLOAD)
    assert resp.status_code == 200

    mock_explainer = client.app.state.explainer
    assert mock_explainer.explain.call_count == 1
    call_kwargs = mock_explainer.explain.call_args[1]
    assert call_kwargs.get("shap_factors") is None


def test_explain_risk_level_forwarded(client: TestClient) -> None:
    """POST /explain with risk_level passes it to explainer (Bug #3 fix)."""
    payload = {
        **VALID_EXPLAIN_PAYLOAD,
        "risk_level": "High",
    }
    resp = client.post("/explain", json=payload)
    assert resp.status_code == 200

    mock_explainer = client.app.state.explainer
    call_kwargs = mock_explainer.explain.call_args[1]
    assert call_kwargs.get("risk_level") == "High"


def test_explain_risk_level_defaults_empty(client: TestClient) -> None:
    """POST /explain without risk_level passes empty string to explainer."""
    resp = client.post("/explain", json=VALID_EXPLAIN_PAYLOAD)
    assert resp.status_code == 200

    mock_explainer = client.app.state.explainer
    call_kwargs = mock_explainer.explain.call_args[1]
    assert call_kwargs.get("risk_level") == ""


def test_explain_confidence_gate_fires(mock_predictor: MagicMock) -> None:
    """When explainer returns low confidence + gate narrative, response reflects this."""

    @asynccontextmanager
    async def noop_lifespan(app):  # type: ignore[type-arg]
        yield

    low_conf_explainer = _make_mock_explainer(
        narrative="No matching incidents found.",
        confidence=0.20,
        recommendations="",  # Empty for low-confidence path
    )
    app = create_app(lifespan_override=noop_lifespan)
    app.state.predictor = mock_predictor
    app.state.explainer = low_conf_explainer
    app.state.start_time = time.monotonic()
    app.state.rag_corpus_size = 3253
    app.state.mapping_config = MappingConfig.load()

    with TestClient(app) as c:
        resp = c.post("/explain", json=VALID_EXPLAIN_PAYLOAD)

    assert resp.status_code == 200
    data = resp.json()
    assert data["narrative"] == "No matching incidents found."
    assert data["retrieval_confidence"] < CONFIDENCE_THRESHOLD
    assert data["recommendations"] == ""


def test_explain_calls_via_to_thread(client: TestClient) -> None:
    """Verify /explain uses asyncio.to_thread: explainer.explain called exactly once.

    The TestClient resolves the async coroutine. The primary proof that to_thread
    is used is the grep check in acceptance_criteria. This test verifies the code
    path executes correctly end-to-end with the mock (API-05, D-07).
    """
    resp = client.post("/explain", json=VALID_EXPLAIN_PAYLOAD)
    assert resp.status_code == 200
    mock_explainer = client.app.state.explainer
    # explainer.explain was called exactly once — via asyncio.to_thread
    assert mock_explainer.explain.call_count == 1


# ---------------------------------------------------------------------------
# /apriori-rules tests (S03 — T02)
# ---------------------------------------------------------------------------

def test_apriori_rules_returns_200(client: TestClient) -> None:
    """GET /apriori-rules returns 200 with a rules list containing 1 entry."""
    resp = client.get("/apriori-rules")
    assert resp.status_code == 200

    data = resp.json()
    assert "rules" in data
    assert isinstance(data["rules"], list)
    assert len(data["rules"]) == 1


def test_apriori_rules_empty_when_no_artifact(mock_predictor: MagicMock) -> None:
    """GET /apriori-rules returns rules: [] when app.state.apriori_rules is empty."""

    @asynccontextmanager
    async def noop_lifespan(app):  # type: ignore[type-arg]
        yield

    app = create_app(lifespan_override=noop_lifespan)
    app.state.predictor = mock_predictor
    app.state.explainer = _make_mock_explainer()
    app.state.start_time = time.monotonic()
    app.state.rag_corpus_size = 3253
    app.state.mapping_config = MappingConfig.load()
    app.state.apriori_rules = []

    with TestClient(app) as c:
        resp = c.get("/apriori-rules")

    assert resp.status_code == 200
    assert resp.json() == {"rules": []}


def test_apriori_rules_schema_validated(client: TestClient) -> None:
    """GET /apriori-rules returns rules with all 6 required fields."""
    resp = client.get("/apriori-rules")
    assert resp.status_code == 200

    rule = resp.json()["rules"][0]
    assert "antecedent" in rule
    assert "consequent" in rule
    assert "support" in rule
    assert "confidence" in rule
    assert "lift" in rule
    assert "count" in rule

    # Type checks
    assert isinstance(rule["antecedent"], str)
    assert isinstance(rule["consequent"], str)
    assert isinstance(rule["support"], float)
    assert isinstance(rule["confidence"], float)
    assert isinstance(rule["lift"], float)
    assert isinstance(rule["count"], int)


# ---------------------------------------------------------------------------
# OpenAPI schema regression test (Task 2)
# ---------------------------------------------------------------------------

def test_openapi_schema_has_all_endpoints(
    mock_predictor: MagicMock, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify OpenAPI spec includes /predict, /explain, /health, /apriori-rules."""
    monkeypatch.setenv("BOWTIE_ENABLE_DOCS", "true")

    @asynccontextmanager
    async def noop_lifespan(app):  # type: ignore[type-arg]
        yield

    app = create_app(lifespan_override=noop_lifespan)
    app.state.predictor = mock_predictor
    app.state.explainer = _make_mock_explainer()
    app.state.start_time = time.monotonic()
    app.state.rag_corpus_size = 3253
    app.state.mapping_config = MappingConfig.load()
    app.state.apriori_rules = []

    with TestClient(app) as c:
        resp = c.get("/openapi.json")

    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/predict" in paths
    assert "/explain" in paths
    assert "/health" in paths
    assert "/apriori-rules" in paths
    assert "post" in paths["/predict"]
    assert "post" in paths["/explain"]
    assert "get" in paths["/health"]
    assert "get" in paths["/apriori-rules"]
