"""Tests for src/api/main.py — S03 endpoint suite.

After T03, /predict and /explain are HTTP 410 Gone (GET endpoints).
Cascading endpoints tested in test_api_cascading.py.

Tests:
  test_predict_returns_410_gone       — GET /predict → 410 with migrate_to
  test_explain_returns_410_gone       — GET /explain → 410 with migrate_to
  test_health_returns_200             — GET /health → status=ok + fields present
  test_health_timestamp_iso8601       — /health timestamp is ISO8601 UTC (ops-manual)
  test_health_model_info              — cascading + rag_v2 loaded info
  test_cors_preflight_prod_origin     — OPTIONS preflight from bowtie.gnsr.dev allowed
  test_apriori_rules_returns_200      — GET /apriori-rules → rules list
  test_apriori_rules_empty            — empty state returns []
  test_apriori_rules_schema           — rule fields validated
  test_openapi_schema_endpoints       — new endpoints in OpenAPI, gone endpoints 410
"""
from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.mapping_loader import MappingConfig
from src.rag.config import CONFIDENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client() -> TestClient:
    """TestClient with mocked cascading resources — no real model loading."""

    @asynccontextmanager
    async def noop_lifespan(app):  # type: ignore[type-arg]
        yield

    app = create_app(lifespan_override=noop_lifespan)
    app.state.cascading_predictor = MagicMock()
    app.state.rag_v2_agent = MagicMock()
    app.state.start_time = time.monotonic()
    app.state.rag_corpus_size = 526
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
    app.state.apriori_metadata = {"n_incidents": 723, "generated_at": "2026-04-06T03:37:03"}

    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# 410 Gone tests — /predict and /explain (T03)
# ---------------------------------------------------------------------------

def test_predict_returns_410_gone(client: TestClient) -> None:
    """GET /predict returns 410 Gone with migrate_to=/predict-cascading."""
    resp = client.get("/predict")
    assert resp.status_code == 410
    data = resp.json()
    assert data["error"] == "gone"
    assert data["migrate_to"] == "/predict-cascading"


def test_explain_returns_410_gone(client: TestClient) -> None:
    """GET /explain returns 410 Gone with migrate_to=/explain-cascading."""
    resp = client.get("/explain")
    assert resp.status_code == 410
    data = resp.json()
    assert data["error"] == "gone"
    assert data["migrate_to"] == "/explain-cascading"


# ---------------------------------------------------------------------------
# /health tests
# ---------------------------------------------------------------------------

def test_health_returns_200(client: TestClient) -> None:
    """GET /health returns 200 with status=ok and required fields."""
    resp = client.get("/health")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert "models" in data
    assert "rag" in data
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0.0


def test_health_timestamp_iso8601(client: TestClient) -> None:
    """GET /health timestamp is ISO8601 UTC — ops-manual contract."""
    resp = client.get("/health")
    assert resp.status_code == 200
    ts = resp.json()["timestamp"]
    # Must parse without error and carry timezone info (UTC offset or 'Z').
    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None


def test_cors_preflight_prod_origin(client: TestClient) -> None:
    """OPTIONS preflight from https://bowtie.gnsr.dev receives Allow-Origin header."""
    resp = client.options(
        "/predict-cascading",
        headers={
            "Origin": "https://bowtie.gnsr.dev",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    # CORSMiddleware returns 200 for preflights with matching origin.
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://bowtie.gnsr.dev"


def test_health_model_info(client: TestClient) -> None:
    """GET /health shows cascading and rag_v2 model info."""
    resp = client.get("/health")
    assert resp.status_code == 200

    data = resp.json()
    assert "cascading" in data["models"]
    assert "rag_v2" in data["models"]
    assert data["models"]["cascading"]["loaded"] is True
    assert data["models"]["rag_v2"]["loaded"] is True


# ---------------------------------------------------------------------------
# /apriori-rules tests
# ---------------------------------------------------------------------------

def test_apriori_rules_returns_200(client: TestClient) -> None:
    """GET /apriori-rules returns 200 with rules list containing 1 entry."""
    resp = client.get("/apriori-rules")
    assert resp.status_code == 200
    data = resp.json()
    assert "rules" in data
    assert len(data["rules"]) == 1


def test_apriori_rules_empty_when_no_artifact() -> None:
    """GET /apriori-rules returns rules: [] when no rules loaded at startup."""

    @asynccontextmanager
    async def noop_lifespan(app):  # type: ignore[type-arg]
        yield

    app = create_app(lifespan_override=noop_lifespan)
    app.state.cascading_predictor = None
    app.state.rag_v2_agent = None
    app.state.start_time = time.monotonic()
    app.state.rag_corpus_size = 0
    app.state.apriori_rules = []

    with TestClient(app) as c:
        resp = c.get("/apriori-rules")

    assert resp.status_code == 200
    assert resp.json()["rules"] == []


def test_apriori_rules_schema_validated(client: TestClient) -> None:
    """GET /apriori-rules rules have all 6 required fields with correct types."""
    resp = client.get("/apriori-rules")
    rule = resp.json()["rules"][0]
    assert isinstance(rule["antecedent"], str)
    assert isinstance(rule["consequent"], str)
    assert isinstance(rule["support"], float)
    assert isinstance(rule["confidence"], float)
    assert isinstance(rule["lift"], float)
    assert isinstance(rule["count"], int)


def test_apriori_rules_includes_metadata(client: TestClient) -> None:
    """GET /apriori-rules response includes n_incidents and generated_at from JSON metadata."""
    resp = client.get("/apriori-rules")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["n_incidents"], int)
    assert body["n_incidents"] > 0
    assert isinstance(body["generated_at"], str)
    assert len(body["generated_at"]) > 0


# ---------------------------------------------------------------------------
# OpenAPI schema regression (T03)
# ---------------------------------------------------------------------------

def test_openapi_schema_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenAPI documents new cascading endpoints and GET gone endpoints."""
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

    with TestClient(app) as c:
        resp = c.get("/openapi.json")

    assert resp.status_code == 200
    paths = resp.json()["paths"]

    # New cascading endpoints must be present
    assert "/predict-cascading" in paths
    assert "/rank-targets" in paths
    assert "/explain-cascading" in paths
    assert "post" in paths["/predict-cascading"]
    assert "post" in paths["/rank-targets"]
    assert "post" in paths["/explain-cascading"]

    # Legacy endpoints now gone (GET, not POST)
    assert "/predict" in paths
    assert "/explain" in paths
    assert "get" in paths["/predict"]
    assert "get" in paths["/explain"]
    assert "post" not in paths["/predict"]
    assert "post" not in paths["/explain"]

    # Unchanged endpoints still present
    assert "/health" in paths
    assert "/apriori-rules" in paths
    assert "get" in paths["/health"]
    assert "get" in paths["/apriori-rules"]

    # Spot-check PredictCascadingResponse schema has predictions array
    schema = resp.json().get("components", {}).get("schemas", {})
    assert "PredictCascadingResponse" in schema
    pred_schema = schema["PredictCascadingResponse"]
    assert "predictions" in pred_schema.get("properties", {})
