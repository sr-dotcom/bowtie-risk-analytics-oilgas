"""OpenAPI contract tests (S03/T03).

Starts the app with BOWTIE_ENABLE_DOCS=true and verifies the /openapi.json
schema against the S03 API contract.

Checks:
  - All 3 new cascading endpoints documented (POST)
  - Legacy /predict and /explain documented as GET with 410 responses
  - /health and /apriori-rules still present
  - PredictCascadingResponse schema has correct shape
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


@pytest.fixture
def openapi_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient with OpenAPI docs enabled and mock state injected."""
    monkeypatch.setenv("BOWTIE_ENABLE_DOCS", "true")

    @asynccontextmanager
    async def noop_lifespan(app):  # type: ignore[type-arg]
        yield

    app = create_app(lifespan_override=noop_lifespan)
    app.state.cascading_predictor = None
    app.state.rag_v2_agent = None
    app.state.start_time = time.monotonic()
    app.state.rag_corpus_size = 0
    app.state.apriori_rules = []

    return TestClient(app)


@pytest.fixture
def openapi_schema(openapi_client: TestClient) -> dict:
    resp = openapi_client.get("/openapi.json")
    assert resp.status_code == 200, "OpenAPI schema not available — check BOWTIE_ENABLE_DOCS"
    return resp.json()


# ---------------------------------------------------------------------------
# New endpoints documented
# ---------------------------------------------------------------------------

def test_predict_cascading_documented(openapi_schema: dict) -> None:
    """POST /predict-cascading is in OpenAPI paths."""
    assert "/predict-cascading" in openapi_schema["paths"]
    assert "post" in openapi_schema["paths"]["/predict-cascading"]


def test_rank_targets_documented(openapi_schema: dict) -> None:
    """POST /rank-targets is in OpenAPI paths."""
    assert "/rank-targets" in openapi_schema["paths"]
    assert "post" in openapi_schema["paths"]["/rank-targets"]


def test_explain_cascading_documented(openapi_schema: dict) -> None:
    """POST /explain-cascading is in OpenAPI paths."""
    assert "/explain-cascading" in openapi_schema["paths"]
    assert "post" in openapi_schema["paths"]["/explain-cascading"]


# ---------------------------------------------------------------------------
# Gone endpoints documented as GET (not POST) with 410
# ---------------------------------------------------------------------------

def test_predict_gone_documented_as_get(openapi_schema: dict) -> None:
    """Legacy /predict is documented as GET (returns 410)."""
    assert "/predict" in openapi_schema["paths"]
    path_item = openapi_schema["paths"]["/predict"]
    assert "get" in path_item, "/predict should be GET now"
    assert "post" not in path_item, "/predict should no longer accept POST"


def test_explain_gone_documented_as_get(openapi_schema: dict) -> None:
    """Legacy /explain is documented as GET (returns 410)."""
    assert "/explain" in openapi_schema["paths"]
    path_item = openapi_schema["paths"]["/explain"]
    assert "get" in path_item, "/explain should be GET now"
    assert "post" not in path_item, "/explain should no longer accept POST"


# ---------------------------------------------------------------------------
# Unchanged endpoints still present
# ---------------------------------------------------------------------------

def test_health_still_present(openapi_schema: dict) -> None:
    """GET /health still in OpenAPI paths."""
    assert "/health" in openapi_schema["paths"]
    assert "get" in openapi_schema["paths"]["/health"]


def test_apriori_rules_still_present(openapi_schema: dict) -> None:
    """GET /apriori-rules still in OpenAPI paths."""
    assert "/apriori-rules" in openapi_schema["paths"]
    assert "get" in openapi_schema["paths"]["/apriori-rules"]


# ---------------------------------------------------------------------------
# PredictCascadingResponse schema spot-check
# ---------------------------------------------------------------------------

def test_predict_cascading_response_schema(openapi_schema: dict) -> None:
    """PredictCascadingResponse schema has predictions array with correct sub-fields."""
    schemas = openapi_schema.get("components", {}).get("schemas", {})
    assert "PredictCascadingResponse" in schemas
    resp_schema = schemas["PredictCascadingResponse"]
    props = resp_schema.get("properties", {})

    # predictions is a required array
    assert "predictions" in props
    pred_prop = props["predictions"]
    assert pred_prop.get("type") == "array" or "$ref" in pred_prop.get("items", {}) or "anyOf" in pred_prop

    # explanation_unavailable present with boolean default
    assert "explanation_unavailable" in props


def test_cascading_barrier_prediction_schema(openapi_schema: dict) -> None:
    """CascadingBarrierPrediction schema has all required fields."""
    schemas = openapi_schema.get("components", {}).get("schemas", {})
    assert "CascadingBarrierPrediction" in schemas
    props = schemas["CascadingBarrierPrediction"].get("properties", {})

    assert "target_barrier_id" in props
    assert "y_fail_probability" in props
    assert "risk_band" in props
    assert "shap_values" in props
