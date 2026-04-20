"""Tests for cascading API endpoints: /predict-cascading, /rank-targets, /explain-cascading.

Uses mocked CascadingPredictor and RAGAgent via no-op lifespan — no real artifacts needed.
"""
from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.modeling.cascading.predict import (
    BarrierPrediction,
    PredictionResult,
    RankedBarrier,
    RankingResult,
    ShapEntry,
)
from src.rag.rag_agent import ExplanationResult
from src.rag.retriever import RetrievalResult


# ---------------------------------------------------------------------------
# Demo scenario payload (BSEE Fieldwood)
# ---------------------------------------------------------------------------

with open("data/demo_scenarios/bsee_eb-165-a-fieldwood-09-may-2015.json", encoding="utf-8") as _f:
    _BSEE_SCENARIO = json.load(_f)

VALID_CASCADING_PAYLOAD = {
    "scenario": _BSEE_SCENARIO,
    "conditioning_barrier_id": "C-001",
}

EXPLAIN_PAYLOAD = {
    "conditioning_barrier_id": "C-001",
    "target_barrier_id": "C-002",
    "bowtie_context": _BSEE_SCENARIO,
}

_SHAP_ENTRIES = [ShapEntry(feature=f"feat_{i}", value=0.05) for i in range(18)]
_MOCK_PREDICTIONS = [
    BarrierPrediction(
        target_barrier_id="C-002",
        y_fail_probability=0.72,
        risk_band="HIGH",
        shap_values=_SHAP_ENTRIES,
    ),
    BarrierPrediction(
        target_barrier_id="C-003",
        y_fail_probability=0.38,
        risk_band="LOW",
        shap_values=_SHAP_ENTRIES,
    ),
]

_MOCK_RETRIEVAL_RESULT = RetrievalResult(
    incident_id="INC-001",
    control_id="CTL-001",
    barrier_family="pressure_relief",
    barrier_failed_human=True,
    rrf_score=0.031,
    barrier_rank=1,
    incident_rank=2,
    barrier_sim_score=0.88,
    incident_sim_score=0.75,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_mock_predictor() -> MagicMock:
    predictor = MagicMock()
    predictor.predict.return_value = PredictionResult(predictions=_MOCK_PREDICTIONS)
    predictor.rank.return_value = RankingResult(
        ranked_barriers=[
            RankedBarrier(target_barrier_id="C-002", composite_risk_score=0.72),
            RankedBarrier(target_barrier_id="C-003", composite_risk_score=0.38),
        ]
    )
    return predictor


def _make_mock_rag_v2() -> MagicMock:
    rag = MagicMock()
    rag.explain.return_value = ExplanationResult(
        context_text="## Conditioning Barrier\n\nContext text here.\n\n## Target Barrier\n\nMore text.",
        results=[_MOCK_RETRIEVAL_RESULT],
    )
    rag._incident_meta = {
        "INC-001": {
            "source_agency": "BSEE",
            "recommendations": '["Improve inspection frequency", "Update procedures"]',
        }
    }
    return rag


@pytest.fixture
def client() -> TestClient:
    @asynccontextmanager
    async def noop_lifespan(app):  # type: ignore[type-arg]
        yield

    app = create_app(lifespan_override=noop_lifespan)
    app.state.cascading_predictor = _make_mock_predictor()
    app.state.rag_v2_agent = _make_mock_rag_v2()
    app.state.start_time = time.monotonic()
    app.state.rag_corpus_size = 526
    app.state.apriori_rules = []
    return TestClient(app)


@pytest.fixture
def client_no_predictor() -> TestClient:
    """Client where cascading_predictor is None (graceful degradation)."""
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


# ---------------------------------------------------------------------------
# /predict-cascading tests
# ---------------------------------------------------------------------------

def test_predict_cascading_valid_returns_200(client: TestClient) -> None:
    response = client.post("/predict-cascading", json=VALID_CASCADING_PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert "predictions" in body
    assert body["explanation_unavailable"] is False
    assert len(body["predictions"]) == 2
    first = body["predictions"][0]
    assert first["target_barrier_id"] == "C-002"
    assert first["y_fail_probability"] == pytest.approx(0.72)
    assert first["risk_band"] == "HIGH"
    assert isinstance(first["shap_values"], list)
    assert len(first["shap_values"]) == 18


def test_predict_cascading_missing_conditioning_id_returns_422(client: TestClient) -> None:
    payload = {"scenario": _BSEE_SCENARIO}  # missing conditioning_barrier_id
    response = client.post("/predict-cascading", json=payload)
    assert response.status_code == 422


def test_predict_cascading_nonexistent_barrier_id_returns_400(client: TestClient) -> None:
    payload = {
        "scenario": _BSEE_SCENARIO,
        "conditioning_barrier_id": "C-NONEXISTENT",
    }
    response = client.post("/predict-cascading", json=payload)
    assert response.status_code == 400
    assert "C-NONEXISTENT" in response.json()["detail"]


def test_predict_cascading_degraded_when_no_predictor(client_no_predictor: TestClient) -> None:
    response = client_no_predictor.post("/predict-cascading", json=VALID_CASCADING_PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert body["predictions"] == []
    assert body["explanation_unavailable"] is True


def test_predict_cascading_no_y_hf_fail_in_response(client: TestClient) -> None:
    """D016 Branch C: y_hf_fail must not appear anywhere in the API response."""
    response = client.post("/predict-cascading", json=VALID_CASCADING_PAYLOAD)
    assert "y_hf_fail" not in response.text


# ---------------------------------------------------------------------------
# /rank-targets tests
# ---------------------------------------------------------------------------

def test_rank_targets_valid_returns_200(client: TestClient) -> None:
    response = client.post("/rank-targets", json=VALID_CASCADING_PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert "ranked_barriers" in body
    assert len(body["ranked_barriers"]) == 2
    first = body["ranked_barriers"][0]
    assert first["target_barrier_id"] == "C-002"
    assert first["composite_risk_score"] == pytest.approx(0.72)


def test_rank_targets_missing_conditioning_id_returns_422(client: TestClient) -> None:
    payload = {"scenario": _BSEE_SCENARIO}
    response = client.post("/rank-targets", json=payload)
    assert response.status_code == 422


def test_rank_targets_nonexistent_barrier_id_returns_400(client: TestClient) -> None:
    payload = {
        "scenario": _BSEE_SCENARIO,
        "conditioning_barrier_id": "GHOST",
    }
    response = client.post("/rank-targets", json=payload)
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# /explain-cascading tests
# ---------------------------------------------------------------------------

def test_explain_cascading_valid_returns_200(client: TestClient) -> None:
    response = client.post("/explain-cascading", json=EXPLAIN_PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert "narrative_text" in body
    assert "evidence_snippets" in body
    assert "degradation_context" in body
    dc = body["degradation_context"]
    assert isinstance(dc["pif_mentions"], list)
    assert isinstance(dc["recommendations"], list)
    assert isinstance(dc["barrier_condition"], str)


def test_explain_cascading_missing_field_returns_422(client: TestClient) -> None:
    payload = {"conditioning_barrier_id": "C-001"}  # missing target and context
    response = client.post("/explain-cascading", json=payload)
    assert response.status_code == 422


def test_explain_cascading_degraded_when_no_rag(client_no_predictor: TestClient) -> None:
    response = client_no_predictor.post("/explain-cascading", json=EXPLAIN_PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert body["narrative_unavailable"] is True
