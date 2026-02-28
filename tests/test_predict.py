"""Tests for src/modeling/predict.py — BarrierPredictor and PredictionResult.

Tests use synthetic artifacts in tmp_path only. Production artifacts are NOT
required. All XGBoost models are tiny (n_estimators=5) for speed.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
import xgboost as xgb
from sklearn.preprocessing import OrdinalEncoder

from src.modeling.feature_engineering import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    PIF_FEATURES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def predictor_artifacts(tmp_path: Path):
    """Create all artifacts needed by BarrierPredictor in tmp_path.

    Returns (tmp_path, cat_values) where cat_values is the dict of valid
    category strings per categorical column.
    """
    rng = np.random.default_rng(42)
    n = 50
    feature_names_flat = CATEGORICAL_FEATURES + PIF_FEATURES + NUMERIC_FEATURES

    # Categorical string values for encoder fitting
    cat_values = {
        "side": ["left", "right"],
        "barrier_type": ["engineering", "administrative", "ppe"],
        "line_of_defense": ["1", "2", "3"],
        "barrier_family": ["alarm", "valve", "training_program"],
        "source_agency": ["BSEE", "CSB"],
    }

    # Fit encoder on string categories
    encoder = OrdinalEncoder(
        handle_unknown="use_encoded_value",
        unknown_value=-1,
        dtype=int,
    )
    # Build 20 training rows for encoder (string values)
    encoder_rows = []
    for _ in range(20):
        row = [rng.choice(v) for v in cat_values.values()]
        encoder_rows.append(row)
    encoder.fit(pd.DataFrame(encoder_rows, columns=CATEGORICAL_FEATURES))
    joblib.dump(encoder, tmp_path / "encoder.joblib")

    # Build integer-encoded training data (X) for model training
    X = np.zeros((n, len(feature_names_flat)), dtype=float)
    for i, col in enumerate(CATEGORICAL_FEATURES):
        X[:, i] = rng.integers(0, len(cat_values[col]), size=n)
    # PIF features (indices 5-16)
    for i in range(len(CATEGORICAL_FEATURES), len(CATEGORICAL_FEATURES) + len(PIF_FEATURES)):
        X[:, i] = rng.integers(0, 2, size=n)
    # Numeric (last column)
    X[:, -1] = rng.integers(0, 10, size=n)

    y1 = rng.integers(0, 2, size=n)
    y2 = y1 & rng.integers(0, 2, size=n)
    # Ensure y2 has at least one positive and one negative
    if y2.sum() == 0:
        y2[0] = 1
    if (y2 == 0).sum() == 0:
        y2[-1] = 0

    # Train and save XGBoost models
    for suffix, y in [("model1", y1), ("model2", y2)]:
        xgb_model = xgb.XGBClassifier(
            n_estimators=5,
            max_depth=2,
            eval_metric="logloss",
            random_state=42,
        )
        xgb_model.fit(X, y)
        xgb_model.save_model(str(tmp_path / f"xgb_{suffix}.json"))

    # Save SHAP background arrays
    bg_idx = rng.choice(n, size=min(20, n), replace=False)
    for suffix in ["model1", "model2"]:
        np.save(str(tmp_path / f"shap_background_{suffix}.npy"), X[bg_idx])

    # Save upgraded feature_names.json (list-of-dicts per D-08)
    feature_names_dicts = [
        {"name": name, "category": "incident_context" if name in PIF_FEATURES else "barrier"}
        for name in feature_names_flat
    ]
    with open(tmp_path / "feature_names.json", "w") as f:
        json.dump(feature_names_dicts, f)

    return tmp_path, cat_values


def _make_raw_features(cat_values: dict[str, list[str]], rng=None) -> dict:
    """Build a raw (unencoded) feature dict from cat_values."""
    if rng is None:
        rng = np.random.default_rng(99)
    return {
        "side": str(rng.choice(cat_values["side"])),
        "barrier_type": str(rng.choice(cat_values["barrier_type"])),
        "line_of_defense": str(rng.choice(cat_values["line_of_defense"])),
        "barrier_family": str(rng.choice(cat_values["barrier_family"])),
        "source_agency": str(rng.choice(cat_values["source_agency"])),
        "pif_competence": 1,
        "pif_fatigue": 0,
        "pif_communication": 1,
        "pif_situational_awareness": 0,
        "pif_procedures": 1,
        "pif_workload": 0,
        "pif_time_pressure": 0,
        "pif_tools_equipment": 0,
        "pif_safety_culture": 0,
        "pif_management_of_change": 1,
        "pif_supervision": 0,
        "pif_training": 0,
        "supporting_text_count": 3,
    }


# ---------------------------------------------------------------------------
# Tests: PredictionResult dataclass
# ---------------------------------------------------------------------------

def test_prediction_result_fields():
    """PredictionResult dataclass has all 6 required fields (D-15)."""
    from src.modeling.predict import PredictionResult

    result = PredictionResult(
        model1_probability=0.7,
        model2_probability=0.3,
        model1_shap_values={"side": 0.1, "barrier_type": -0.05},
        model2_shap_values={"side": 0.2, "barrier_type": -0.02},
        model1_base_value=-1.5,
        model2_base_value=-0.8,
    )
    assert hasattr(result, "model1_probability")
    assert hasattr(result, "model2_probability")
    assert hasattr(result, "model1_shap_values")
    assert hasattr(result, "model2_shap_values")
    assert hasattr(result, "model1_base_value")
    assert hasattr(result, "model2_base_value")
    assert result.model1_probability == 0.7
    assert result.model2_probability == 0.3
    assert result.model1_base_value == -1.5


def test_prediction_result_separate_shap():
    """SHAP-03: model1_shap_values and model2_shap_values are distinct dict objects."""
    from src.modeling.predict import PredictionResult

    d1 = {"side": 0.1}
    d2 = {"side": 0.2}
    result = PredictionResult(
        model1_probability=0.5,
        model2_probability=0.4,
        model1_shap_values=d1,
        model2_shap_values=d2,
        model1_base_value=0.0,
        model2_base_value=0.0,
    )
    assert result.model1_shap_values is not result.model2_shap_values, (
        "SHAP-03: shap_values from two models must be separate dict objects"
    )


# ---------------------------------------------------------------------------
# Tests: BarrierPredictor initialization
# ---------------------------------------------------------------------------

def test_barrier_predictor_loads_artifacts(predictor_artifacts):
    """D-13: BarrierPredictor(tmp_path) initializes without error."""
    from src.modeling.predict import BarrierPredictor

    tmp_path, _ = predictor_artifacts
    predictor = BarrierPredictor(artifacts_dir=tmp_path)
    assert predictor is not None


def test_barrier_predictor_has_feature_names(predictor_artifacts):
    """BarrierPredictor.feature_names returns list of dicts (D-08, SHAP-04)."""
    from src.modeling.predict import BarrierPredictor

    tmp_path, _ = predictor_artifacts
    predictor = BarrierPredictor(artifacts_dir=tmp_path)

    feature_names = predictor.feature_names
    assert isinstance(feature_names, list), "feature_names must be a list"
    assert len(feature_names) > 0, "feature_names must not be empty"
    assert isinstance(feature_names[0], dict), "feature_names entries must be dicts"
    assert "name" in feature_names[0], "Each entry must have 'name'"
    assert "category" in feature_names[0], "Each entry must have 'category'"


# ---------------------------------------------------------------------------
# Tests: predict() method
# ---------------------------------------------------------------------------

def test_predict_accepts_raw_dict(predictor_artifacts):
    """D-14: predict() accepts a raw (unencoded) feature dict and returns PredictionResult."""
    from src.modeling.predict import BarrierPredictor, PredictionResult

    tmp_path, cat_values = predictor_artifacts
    predictor = BarrierPredictor(artifacts_dir=tmp_path)

    raw = _make_raw_features(cat_values)
    result = predictor.predict(raw)

    assert isinstance(result, PredictionResult), (
        f"predict() must return PredictionResult, got {type(result)}"
    )


def test_predict_probabilities_in_range(predictor_artifacts):
    """Probabilities from both models are in [0, 1]."""
    from src.modeling.predict import BarrierPredictor

    tmp_path, cat_values = predictor_artifacts
    predictor = BarrierPredictor(artifacts_dir=tmp_path)

    raw = _make_raw_features(cat_values)
    result = predictor.predict(raw)

    assert 0.0 <= result.model1_probability <= 1.0, (
        f"model1_probability out of range: {result.model1_probability}"
    )
    assert 0.0 <= result.model2_probability <= 1.0, (
        f"model2_probability out of range: {result.model2_probability}"
    )


def test_predict_shap_values_are_dicts(predictor_artifacts):
    """SHAP values from both models are dicts with float values."""
    from src.modeling.predict import BarrierPredictor

    tmp_path, cat_values = predictor_artifacts
    predictor = BarrierPredictor(artifacts_dir=tmp_path)

    raw = _make_raw_features(cat_values)
    result = predictor.predict(raw)

    assert isinstance(result.model1_shap_values, dict), (
        f"model1_shap_values must be dict, got {type(result.model1_shap_values)}"
    )
    assert isinstance(result.model2_shap_values, dict), (
        f"model2_shap_values must be dict, got {type(result.model2_shap_values)}"
    )

    # All values must be float
    for key, val in result.model1_shap_values.items():
        assert isinstance(val, float), f"SHAP value for {key} must be float, got {type(val)}"
    for key, val in result.model2_shap_values.items():
        assert isinstance(val, float), f"SHAP value for {key} must be float, got {type(val)}"


def test_predict_shap_keys_match_feature_names(predictor_artifacts):
    """SHAP values dict has exactly 18 keys matching feature names."""
    from src.modeling.predict import BarrierPredictor

    tmp_path, cat_values = predictor_artifacts
    predictor = BarrierPredictor(artifacts_dir=tmp_path)

    expected_names = [f["name"] for f in predictor.feature_names]
    raw = _make_raw_features(cat_values)
    result = predictor.predict(raw)

    assert sorted(result.model1_shap_values.keys()) == sorted(expected_names), (
        "model1_shap_values keys must match feature_names"
    )
    assert sorted(result.model2_shap_values.keys()) == sorted(expected_names), (
        "model2_shap_values keys must match feature_names"
    )


def test_predict_result_shap_values_separate(predictor_artifacts):
    """SHAP-03: predict() returns model1_shap_values and model2_shap_values as different objects."""
    from src.modeling.predict import BarrierPredictor

    tmp_path, cat_values = predictor_artifacts
    predictor = BarrierPredictor(artifacts_dir=tmp_path)

    raw = _make_raw_features(cat_values)
    result = predictor.predict(raw)

    assert result.model1_shap_values is not result.model2_shap_values, (
        "SHAP-03: model1_shap_values and model2_shap_values must be separate objects"
    )


def test_predict_unknown_category_no_crash(predictor_artifacts):
    """Unknown categorical values do not raise; predict() returns valid PredictionResult."""
    from src.modeling.predict import BarrierPredictor, PredictionResult

    tmp_path, cat_values = predictor_artifacts
    predictor = BarrierPredictor(artifacts_dir=tmp_path)

    raw = _make_raw_features(cat_values)
    raw["side"] = "NEVER_SEEN_CATEGORY"
    raw["barrier_type"] = "ALSO_NEVER_SEEN"

    # Should not raise
    result = predictor.predict(raw)
    assert isinstance(result, PredictionResult), (
        "predict() must handle unknown categories gracefully"
    )
    assert 0.0 <= result.model1_probability <= 1.0
    assert 0.0 <= result.model2_probability <= 1.0


def test_feature_names_category_field(predictor_artifacts):
    """SHAP-04: feature_names property returns dicts with category field.

    PIF features have category='incident_context'.
    Barrier features have category='barrier'.
    """
    from src.modeling.predict import BarrierPredictor

    tmp_path, _ = predictor_artifacts
    predictor = BarrierPredictor(artifacts_dir=tmp_path)

    feature_names = predictor.feature_names
    name_to_category = {entry["name"]: entry["category"] for entry in feature_names}

    # All PIF features must have category 'incident_context'
    for pif_name in PIF_FEATURES:
        assert pif_name in name_to_category, f"PIF feature {pif_name} not in feature_names"
        assert name_to_category[pif_name] == "incident_context", (
            f"SHAP-04: PIF feature {pif_name} must have category='incident_context', "
            f"got '{name_to_category[pif_name]}'"
        )

    # Categorical and numeric features must have category 'barrier'
    for cat_name in CATEGORICAL_FEATURES + NUMERIC_FEATURES:
        assert cat_name in name_to_category, f"Feature {cat_name} not in feature_names"
        assert name_to_category[cat_name] == "barrier", (
            f"Feature {cat_name} must have category='barrier', "
            f"got '{name_to_category[cat_name]}'"
        )


def test_predict_base_values_are_floats(predictor_artifacts):
    """model1_base_value and model2_base_value are Python floats."""
    from src.modeling.predict import BarrierPredictor

    tmp_path, cat_values = predictor_artifacts
    predictor = BarrierPredictor(artifacts_dir=tmp_path)

    raw = _make_raw_features(cat_values)
    result = predictor.predict(raw)

    assert isinstance(result.model1_base_value, float), (
        f"model1_base_value must be float, got {type(result.model1_base_value)}"
    )
    assert isinstance(result.model2_base_value, float), (
        f"model2_base_value must be float, got {type(result.model2_base_value)}"
    )
