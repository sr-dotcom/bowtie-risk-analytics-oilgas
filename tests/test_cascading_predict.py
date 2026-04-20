"""Tests for src/modeling/cascading/predict.py (S03/T01).

Skips artifact-dependent tests gracefully when joblib pipeline is absent.
D016 Branch C: asserts y_hf_fail_probability never appears in any output.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

_PIPELINE_PATH = Path("data/models/artifacts/xgb_cascade_y_fail_pipeline.joblib")
_ARTIFACTS_MISSING = not _PIPELINE_PATH.exists()

BSEE_SCENARIO_PATH = Path("data/demo_scenarios/bsee_eb-165-a-fieldwood-09-may-2015.json")

RISK_BAND_CASES = [
    (0.00, "LOW"),
    (0.44, "LOW"),
    (0.45, "MEDIUM"),
    (0.69, "MEDIUM"),
    (0.70, "HIGH"),
    (0.99, "HIGH"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_bsee_scenario() -> dict:
    with open(BSEE_SCENARIO_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_ARTIFACTS_MISSING, reason="xgb_cascade_y_fail_pipeline.joblib not present")
def test_load_cascading_predictor_returns_predictor() -> None:
    """load_cascading_predictor returns a CascadingPredictor with expected attributes."""
    from src.modeling.cascading.predict import CascadingPredictor, load_cascading_predictor

    predictor = load_cascading_predictor(Path("data/models/artifacts"))
    assert isinstance(predictor, CascadingPredictor)
    assert predictor._all_features  # non-empty feature list
    assert predictor._thresholds.get("p60") == 0.45
    assert predictor._thresholds.get("p80") == 0.70


@pytest.mark.skipif(_ARTIFACTS_MISSING, reason="xgb_cascade_y_fail_pipeline.joblib not present")
def test_predict_bsee_scenario_c001_conditioning() -> None:
    """predict() on BSEE scenario with C-001 conditioning returns non-empty predictions."""
    from src.modeling.cascading.predict import load_cascading_predictor

    predictor = load_cascading_predictor(Path("data/models/artifacts"))
    scenario = _load_bsee_scenario()

    result = predictor.predict(scenario, conditioning_barrier_id="C-001")

    assert result.predictions, "predict() returned empty predictions"
    # C-001 is the conditioning barrier — must not appear as a target
    target_ids = [p.target_barrier_id for p in result.predictions]
    assert "C-001" not in target_ids
    # BSEE scenario has 7 barriers; conditioning excluded → 6 targets
    assert len(result.predictions) == 6


@pytest.mark.skipif(_ARTIFACTS_MISSING, reason="xgb_cascade_y_fail_pipeline.joblib not present")
@pytest.mark.parametrize("probability,expected_band", RISK_BAND_CASES)
def test_risk_band_mapping(probability: float, expected_band: str) -> None:
    """Risk band maps probabilities to LOW/MEDIUM/HIGH per configs/risk_thresholds.json."""
    from src.modeling.cascading.predict import _risk_band

    thresholds = {"p60": 0.45, "p80": 0.70}
    assert _risk_band(probability, thresholds) == expected_band


@pytest.mark.skipif(_ARTIFACTS_MISSING, reason="xgb_cascade_y_fail_pipeline.joblib not present")
def test_predict_results_are_sorted_descending() -> None:
    """predict() returns predictions sorted by y_fail_probability descending."""
    from src.modeling.cascading.predict import load_cascading_predictor

    predictor = load_cascading_predictor(Path("data/models/artifacts"))
    scenario = _load_bsee_scenario()
    result = predictor.predict(scenario, "C-001")

    probs = [p.y_fail_probability for p in result.predictions]
    assert probs == sorted(probs, reverse=True)


@pytest.mark.skipif(_ARTIFACTS_MISSING, reason="xgb_cascade_y_fail_pipeline.joblib not present")
def test_rank_returns_lighter_result_without_shap() -> None:
    """rank() returns RankingResult with composite_risk_score but no shap_values field."""
    from src.modeling.cascading.predict import load_cascading_predictor, RankingResult

    predictor = load_cascading_predictor(Path("data/models/artifacts"))
    scenario = _load_bsee_scenario()
    result = predictor.rank(scenario, "C-001")

    assert isinstance(result, RankingResult)
    assert result.ranked_barriers
    for rb in result.ranked_barriers:
        assert 0.0 <= rb.composite_risk_score <= 1.0
        assert not hasattr(rb, "shap_values"), "rank() should not include SHAP values"


@pytest.mark.skipif(_ARTIFACTS_MISSING, reason="xgb_cascade_y_fail_pipeline.joblib not present")
def test_explain_single_pair_returns_shap_entries() -> None:
    """explain() for a specific pair returns PairExplanationResult with 18 SHAP entries."""
    from src.modeling.cascading.predict import load_cascading_predictor

    predictor = load_cascading_predictor(Path("data/models/artifacts"))
    scenario = _load_bsee_scenario()

    result = predictor.explain(scenario, "C-001", "C-002")

    assert result.target_barrier_id == "C-002"
    assert 0.0 <= result.y_fail_probability <= 1.0
    assert len(result.shap_values) == 18  # all_features count


@pytest.mark.skipif(_ARTIFACTS_MISSING, reason="xgb_cascade_y_fail_pipeline.joblib not present")
def test_y_hf_fail_not_in_any_output() -> None:
    """D016 Branch C: y_hf_fail_probability must not appear anywhere in predict() output."""
    from src.modeling.cascading.predict import load_cascading_predictor

    predictor = load_cascading_predictor(Path("data/models/artifacts"))
    scenario = _load_bsee_scenario()
    result = predictor.predict(scenario, "C-001")

    # Serialize to dict and check no y_hf_fail key exists anywhere
    result_str = json.dumps(dataclasses.asdict(result))
    assert "y_hf_fail" not in result_str, "D016 violation: y_hf_fail appears in predict() output"


@pytest.mark.skipif(_ARTIFACTS_MISSING, reason="xgb_cascade_y_fail_pipeline.joblib not present")
def test_predict_unknown_barrier_id_raises_value_error() -> None:
    """predict() raises ValueError when conditioning_barrier_id not found in scenario."""
    from src.modeling.cascading.predict import load_cascading_predictor

    predictor = load_cascading_predictor(Path("data/models/artifacts"))
    scenario = _load_bsee_scenario()

    with pytest.raises(ValueError, match="NONEXISTENT"):
        predictor.predict(scenario, "NONEXISTENT")
