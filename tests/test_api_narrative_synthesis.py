"""Tests for POST /narrative-synthesis endpoint (T2b).

All tests use a no-op lifespan with a mocked AnthropicProvider injected on
app.state.narrative_provider — no real API key required.
"""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


# ---------------------------------------------------------------------------
# Fixture payload
# ---------------------------------------------------------------------------

VALID_PAYLOAD = {
    "top_barrier_name": "Pressure Safety Valve",
    "top_barrier_risk_band": "HIGH",
    "top_barrier_probability": 0.85,
    "shap_top_features": [
        {"feature": "barrier_type", "value": 0.3, "display_name": "Barrier Type"},
        {"feature": "lod", "value": 0.2, "display_name": "Line of Defense"},
        {"feature": "safety_culture", "value": 0.1, "display_name": "Safety Culture"},
    ],
    "rag_incident_contexts": [
        {
            "incident_id": "INC-001",
            "summary_text": "Pressure relief valve failed during well control operation.",
            "barrier_failure_description": "Valve did not open at set pressure.",
        }
    ],
    "total_barriers": 7,
    "high_risk_count": 2,
    "top_event": "Loss of Containment",
    "similar_incidents_count": 3,
}

_VALID_NARRATIVE = "The pressure safety valve shows elevated failure risk. Hardware barriers of this type have historically underperformed under thermal cycling conditions. Immediate inspection and calibration verification is warranted."


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _noop_lifespan_app(mock_provider: MagicMock | None) -> TestClient:
    @asynccontextmanager
    async def noop_lifespan(app):  # type: ignore[type-arg]
        yield

    app = create_app(lifespan_override=noop_lifespan)
    app.state.cascading_predictor = None
    app.state.rag_v2_agent = None
    app.state.start_time = time.monotonic()
    app.state.rag_corpus_size = 0
    app.state.apriori_rules = []
    app.state.narrative_provider = mock_provider
    return TestClient(app)


@pytest.fixture
def client_narrative() -> TestClient:
    mock_provider = MagicMock()
    mock_provider.model = "claude-haiku-4-5-20251001"
    mock_provider.extract.return_value = _VALID_NARRATIVE
    return _noop_lifespan_app(mock_provider)


@pytest.fixture
def client_no_provider() -> TestClient:
    return _noop_lifespan_app(None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_narrative_synthesis_valid_returns_200(client_narrative: TestClient) -> None:
    response = client_narrative.post("/narrative-synthesis", json=VALID_PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert "narrative" in body
    assert "model" in body
    assert "generated_at" in body
    assert body["narrative"] == _VALID_NARRATIVE
    assert body["model"] == "claude-haiku-4-5-20251001"


def test_narrative_synthesis_missing_top_barrier_returns_422(client_narrative: TestClient) -> None:
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "top_barrier_name"}
    response = client_narrative.post("/narrative-synthesis", json=payload)
    assert response.status_code == 422


def test_narrative_synthesis_timeout_returns_504(client_narrative: TestClient) -> None:
    async def _raise_timeout(*args: object, **kwargs: object) -> object:
        raise asyncio.TimeoutError()

    with patch("src.api.main.asyncio.wait_for", new=_raise_timeout):
        response = client_narrative.post("/narrative-synthesis", json=VALID_PAYLOAD)
    assert response.status_code == 504


def test_narrative_synthesis_empty_response_returns_502(client_narrative: TestClient) -> None:
    client_narrative.app.state.narrative_provider.extract.return_value = "   "
    response = client_narrative.post("/narrative-synthesis", json=VALID_PAYLOAD)
    assert response.status_code == 502
    assert "quality gate" in response.json()["detail"]


def test_narrative_synthesis_over_60_words_returns_502(client_narrative: TestClient) -> None:
    long_narrative = " ".join(["word"] * 80) + "."
    client_narrative.app.state.narrative_provider.extract.return_value = long_narrative
    response = client_narrative.post("/narrative-synthesis", json=VALID_PAYLOAD)
    assert response.status_code == 502
    assert "quality gate" in response.json()["detail"]


def test_narrative_synthesis_degraded_when_no_provider(client_no_provider: TestClient) -> None:
    response = client_no_provider.post("/narrative-synthesis", json=VALID_PAYLOAD)
    assert response.status_code == 503


def test_narrative_synthesis_calls_haiku_model(client_narrative: TestClient) -> None:
    response = client_narrative.post("/narrative-synthesis", json=VALID_PAYLOAD)
    assert response.status_code == 200
    assert response.json()["model"] == "claude-haiku-4-5-20251001"
