"""End-to-end integration test for S03 cascading API (S03/T04).

Starts the app with real artifacts and real RAG v2 corpus.
Full flow: /predict-cascading → pick top-ranked target → /explain-cascading.

Skip conditions:
  - xgb_cascade_y_fail_pipeline.joblib absent (cascading model not trained)
  - data/rag/v2/ absent (RAG v2 corpus not built)
  - sentence_transformers or faiss not installed

Mark: @pytest.mark.integration
"""
from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

_PIPELINE_PATH = Path("data/models/artifacts/xgb_cascade_y_fail_pipeline.joblib")
_RAG_V2_DIR = Path("data/rag/v2")
_BSEE_SCENARIO_PATH = Path("data/demo_scenarios/bsee_eb-165-a-fieldwood-09-may-2015.json")

_ARTIFACTS_MISSING = not _PIPELINE_PATH.exists()
_RAG_V2_MISSING = not _RAG_V2_DIR.exists()

try:
    import sentence_transformers  # noqa: F401
    import faiss  # noqa: F401
    _SENTENCE_TRANSFORMERS_MISSING = False
except ImportError:
    _SENTENCE_TRANSFORMERS_MISSING = True

_SKIP_REASON = (
    "Integration test requires: xgb_cascade_y_fail_pipeline.joblib, "
    "data/rag/v2/, sentence_transformers, faiss"
)
_SKIP = _ARTIFACTS_MISSING or _RAG_V2_MISSING or _SENTENCE_TRANSFORMERS_MISSING


@pytest.mark.integration
@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_s03_full_cascading_flow() -> None:
    """Full S03 flow: /predict-cascading → top-ranked target → /explain-cascading."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app, lifespan

    # Start app with real lifespan (loads actual artifacts)
    app = create_app()  # uses real lifespan
    with TestClient(app) as client:
        # Load BSEE demo scenario
        with open(_BSEE_SCENARIO_PATH, encoding="utf-8") as f:
            scenario = json.load(f)

        conditioning_id = "C-001"

        # ── Step 1: POST /predict-cascading ──────────────────────────────
        predict_payload = {
            "scenario": scenario,
            "conditioning_barrier_id": conditioning_id,
        }
        predict_resp = client.post("/predict-cascading", json=predict_payload)
        assert predict_resp.status_code == 200, f"predict-cascading failed: {predict_resp.text}"

        predict_body = predict_resp.json()
        assert predict_body["explanation_unavailable"] is False
        predictions = predict_body["predictions"]
        assert len(predictions) > 0, "predict-cascading returned no predictions"

        # Each prediction must have the required fields
        for pred in predictions:
            assert "target_barrier_id" in pred
            assert "y_fail_probability" in pred
            assert "risk_band" in pred
            assert pred["risk_band"] in ("HIGH", "MEDIUM", "LOW")
            assert "shap_values" in pred
            assert len(pred["shap_values"]) == 18

        # D016 Branch C: y_hf_fail must not appear anywhere
        assert "y_hf_fail" not in predict_resp.text

        # ── Step 2: POST /explain-cascading for top-ranked target ────────
        top_target_id = predictions[0]["target_barrier_id"]

        explain_payload = {
            "conditioning_barrier_id": conditioning_id,
            "target_barrier_id": top_target_id,
            "bowtie_context": scenario,
        }
        explain_resp = client.post("/explain-cascading", json=explain_payload)
        assert explain_resp.status_code == 200, f"explain-cascading failed: {explain_resp.text}"

        explain_body = explain_resp.json()
        assert "narrative_text" in explain_body
        assert "evidence_snippets" in explain_body
        assert "degradation_context" in explain_body

        dc = explain_body["degradation_context"]
        assert isinstance(dc["pif_mentions"], list)
        assert isinstance(dc["recommendations"], list)
        # D017 validation: at least one recommendation from RAG corpus
        assert len(dc["recommendations"]) >= 1, (
            "degradation_context.recommendations is empty — "
            "D017 requires >=1 recommendation from RAG v2 corpus"
        )
        assert isinstance(dc["barrier_condition"], str)

        # evidence_snippets should be non-empty if RAG retrieval succeeded
        if not explain_body["narrative_unavailable"]:
            assert len(explain_body["evidence_snippets"]) > 0


@pytest.mark.integration
@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_s03_rank_targets_flow() -> None:
    """POST /rank-targets returns sorted barriers without SHAP."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app

    app = create_app()
    with TestClient(app) as client:
        with open(_BSEE_SCENARIO_PATH, encoding="utf-8") as f:
            scenario = json.load(f)

        payload = {"scenario": scenario, "conditioning_barrier_id": "C-001"}
        resp = client.post("/rank-targets", json=payload)
        assert resp.status_code == 200

        body = resp.json()
        ranked = body["ranked_barriers"]
        assert len(ranked) == 6  # 7 barriers minus C-001

        scores = [r["composite_risk_score"] for r in ranked]
        assert scores == sorted(scores, reverse=True), "ranked_barriers not sorted descending"
        for r in ranked:
            assert "shap_values" not in r  # rank-targets must not include SHAP
