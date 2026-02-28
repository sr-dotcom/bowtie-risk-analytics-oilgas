"""Tests for src/modeling/explain.py — SHAP background arrays and PIF ablation study.

Tests use synthetic data in tmp_path only. Production artifacts are NOT required.
All XGBoost models are tiny (n_estimators=5) for speed.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
import xgboost as xgb
from sklearn.linear_model import LogisticRegression

from src.modeling.feature_engineering import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    PIF_FEATURES,
)


# ---------------------------------------------------------------------------
# Synthetic artifact factory
# ---------------------------------------------------------------------------

def _make_test_artifacts(tmp_path: Path):
    """Create minimal model artifacts in tmp_path for testing."""
    rng = np.random.default_rng(42)
    n = 50
    n_features = len(CATEGORICAL_FEATURES) + len(PIF_FEATURES) + len(NUMERIC_FEATURES)  # 18
    X = rng.random((n, n_features))
    y = rng.integers(0, 2, size=n)
    groups = np.array([f"g{i // 3}" for i in range(n)])

    # Train and save tiny XGBoost models
    xgb_model = xgb.XGBClassifier(
        n_estimators=5, max_depth=2,
        eval_metric="logloss", random_state=42,
    )
    xgb_model.fit(X, y)
    xgb_model.save_model(str(tmp_path / "xgb_model1.json"))
    xgb_model.save_model(str(tmp_path / "xgb_model2.json"))

    # Train and save tiny LogReg model
    lr_model = LogisticRegression(max_iter=50, random_state=42)
    lr_model.fit(X, y)
    joblib.dump(lr_model, tmp_path / "logreg_model1.joblib")
    joblib.dump(lr_model, tmp_path / "logreg_model2.joblib")

    # Save feature matrix parquet
    feature_names_flat = CATEGORICAL_FEATURES + PIF_FEATURES + NUMERIC_FEATURES
    data = {name: X[:, i] for i, name in enumerate(feature_names_flat)}
    data["incident_id"] = [f"inc_{i // 3}" for i in range(n)]
    data["control_id"] = [f"ctrl_{i}" for i in range(n)]
    data["label_barrier_failed"] = y
    # label_barrier_failed_human: ensure at least a few positives and negatives
    y2 = (y & rng.integers(0, 2, size=n)).astype(int)
    if y2.sum() == 0:
        y2[0] = 1
    if (y2 == 0).sum() == 0:
        y2[-1] = 0
    data["label_barrier_failed_human"] = y2
    pd.DataFrame(data).to_parquet(tmp_path / "feature_matrix.parquet", index=False)

    # Save feature_names.json in upgraded list-of-dicts format
    feature_names_dicts = [
        {"name": name, "category": "incident_context" if name in PIF_FEATURES else "barrier"}
        for name in feature_names_flat
    ]
    with open(tmp_path / "feature_names.json", "w") as f:
        json.dump(feature_names_dicts, f)

    return X, y, groups


# ---------------------------------------------------------------------------
# Tests: build_shap_backgrounds
# ---------------------------------------------------------------------------

def test_build_shap_backgrounds_saves_npy(tmp_path):
    """SHAP background .npy files are created for both models."""
    from src.modeling.explain import build_shap_backgrounds

    _make_test_artifacts(tmp_path)
    eval_dir = tmp_path / "evaluation"
    eval_dir.mkdir()

    build_shap_backgrounds(
        feature_matrix_path=tmp_path / "feature_matrix.parquet",
        artifacts_dir=tmp_path,
        bg_size=20,
        random_state=42,
    )

    bg1 = tmp_path / "shap_background_model1.npy"
    bg2 = tmp_path / "shap_background_model2.npy"
    assert bg1.exists(), "shap_background_model1.npy must exist"
    assert bg2.exists(), "shap_background_model2.npy must exist"


def test_build_shap_backgrounds_shape(tmp_path):
    """Background arrays have shape (bg_size, n_features) for both models."""
    from src.modeling.explain import build_shap_backgrounds

    _make_test_artifacts(tmp_path)

    n_features = len(CATEGORICAL_FEATURES) + len(PIF_FEATURES) + len(NUMERIC_FEATURES)
    build_shap_backgrounds(
        feature_matrix_path=tmp_path / "feature_matrix.parquet",
        artifacts_dir=tmp_path,
        bg_size=20,
        random_state=42,
    )

    bg1 = np.load(tmp_path / "shap_background_model1.npy")
    bg2 = np.load(tmp_path / "shap_background_model2.npy")
    assert bg1.shape == (20, n_features), f"Expected (20, {n_features}), got {bg1.shape}"
    assert bg2.shape == (20, n_features), f"Expected (20, {n_features}), got {bg2.shape}"


def test_tree_explainer_shape_model1(tmp_path):
    """SHAP-01: TreeExplainer for Model 1 produces shap_values of shape (n_samples, n_features)."""
    import shap

    from src.modeling.explain import build_shap_backgrounds

    X, y, _ = _make_test_artifacts(tmp_path)
    n_features = X.shape[1]
    build_shap_backgrounds(
        feature_matrix_path=tmp_path / "feature_matrix.parquet",
        artifacts_dir=tmp_path,
        bg_size=10,
        random_state=42,
    )

    # Load background and recreate TreeExplainer
    bg = np.load(tmp_path / "shap_background_model1.npy")
    model = xgb.XGBClassifier()
    model.load_model(str(tmp_path / "xgb_model1.json"))
    explainer = shap.TreeExplainer(model, data=bg)

    test_X = X[:5]
    shap_vals = explainer.shap_values(test_X)
    assert shap_vals.shape == (5, n_features), (
        f"Expected (5, {n_features}), got {shap_vals.shape}"
    )


def test_tree_explainer_shape_model2(tmp_path):
    """SHAP-02: TreeExplainer for Model 2 produces shap_values of shape (n_samples, n_features)."""
    import shap

    from src.modeling.explain import build_shap_backgrounds

    X, y, _ = _make_test_artifacts(tmp_path)
    n_features = X.shape[1]
    build_shap_backgrounds(
        feature_matrix_path=tmp_path / "feature_matrix.parquet",
        artifacts_dir=tmp_path,
        bg_size=10,
        random_state=42,
    )

    bg = np.load(tmp_path / "shap_background_model2.npy")
    model = xgb.XGBClassifier()
    model.load_model(str(tmp_path / "xgb_model2.json"))
    explainer = shap.TreeExplainer(model, data=bg)

    test_X = X[:5]
    shap_vals = explainer.shap_values(test_X)
    assert shap_vals.shape == (5, n_features), (
        f"Expected (5, {n_features}), got {shap_vals.shape}"
    )


def test_tree_explainer_expected_value_scalar(tmp_path):
    """TreeExplainer.expected_value is a scalar float for binary XGBoost."""
    import shap

    from src.modeling.explain import build_shap_backgrounds

    X, y, _ = _make_test_artifacts(tmp_path)
    build_shap_backgrounds(
        feature_matrix_path=tmp_path / "feature_matrix.parquet",
        artifacts_dir=tmp_path,
        bg_size=10,
        random_state=42,
    )

    bg = np.load(tmp_path / "shap_background_model1.npy")
    model = xgb.XGBClassifier()
    model.load_model(str(tmp_path / "xgb_model1.json"))
    explainer = shap.TreeExplainer(model, data=bg)

    ev = explainer.expected_value
    # For binary classification, expected_value is a scalar float
    assert isinstance(float(ev), float), f"expected_value should be scalar float, got {type(ev)}"


def test_linear_explainer_produces_shap_values(tmp_path):
    """LinearExplainer for LogReg produces shap_values with correct shape."""
    import shap

    X, y, _ = _make_test_artifacts(tmp_path)
    n_features = X.shape[1]
    lr_model = joblib.load(tmp_path / "logreg_model1.joblib")

    # Create LinearExplainer with background data
    explainer = shap.LinearExplainer(lr_model, X[:10])
    shap_vals = explainer.shap_values(X[:5])
    # LinearExplainer returns (n_samples, n_features)
    assert shap_vals.shape == (5, n_features), (
        f"Expected (5, {n_features}), got {shap_vals.shape}"
    )


# ---------------------------------------------------------------------------
# Tests: run_pif_ablation
# ---------------------------------------------------------------------------

def test_ablation_report_structure(tmp_path):
    """SHAP-05: pif_ablation_report.json is created with correct top-level keys."""
    from src.modeling.explain import run_pif_ablation

    _make_test_artifacts(tmp_path)
    eval_dir = tmp_path / "evaluation"
    eval_dir.mkdir()

    report = run_pif_ablation(
        feature_matrix_path=tmp_path / "feature_matrix.parquet",
        artifacts_dir=tmp_path,
        evaluation_dir=eval_dir,
        n_estimators=5,
        max_depth=2,
        learning_rate=0.1,
    )

    report_path = eval_dir / "pif_ablation_report.json"
    assert report_path.exists(), "pif_ablation_report.json must be created"

    with open(report_path) as f:
        data = json.load(f)

    assert "description" in data, "Report must have 'description'"
    assert "advisory_only" in data, "Report must have 'advisory_only'"
    assert data["advisory_only"] is True, "advisory_only must be True (D-11)"
    assert "model1_label_barrier_failed" in data, "Report must have model1_label_barrier_failed"
    assert "model2_label_barrier_failed_human" in data, "Report must have model2_label_barrier_failed_human"


def test_ablation_report_has_both_feature_sets(tmp_path):
    """Ablation report has 'full_features' and 'non_pif_features' sections with correct metrics."""
    from src.modeling.explain import run_pif_ablation

    _make_test_artifacts(tmp_path)
    eval_dir = tmp_path / "evaluation"
    eval_dir.mkdir()

    run_pif_ablation(
        feature_matrix_path=tmp_path / "feature_matrix.parquet",
        artifacts_dir=tmp_path,
        evaluation_dir=eval_dir,
        n_estimators=5,
        max_depth=2,
        learning_rate=0.1,
    )

    with open(eval_dir / "pif_ablation_report.json") as f:
        data = json.load(f)

    for model_key in ["model1_label_barrier_failed", "model2_label_barrier_failed_human"]:
        model_data = data[model_key]
        assert "full_features" in model_data, f"{model_key} must have 'full_features'"
        assert "non_pif_features" in model_data, f"{model_key} must have 'non_pif_features'"
        assert "pif_impact" in model_data, f"{model_key} must have 'pif_impact'"

        for feat_set in ["full_features", "non_pif_features"]:
            metrics = model_data[feat_set]
            assert "f1_minority_mean" in metrics, f"{model_key}.{feat_set} must have f1_minority_mean"
            assert "f1_minority_std" in metrics, f"{model_key}.{feat_set} must have f1_minority_std"
            assert "mcc_mean" in metrics, f"{model_key}.{feat_set} must have mcc_mean"
            assert "mcc_std" in metrics, f"{model_key}.{feat_set} must have mcc_std"

        # pif_impact is one of: improved, degraded, neutral
        assert model_data["pif_impact"] in {"improved", "degraded", "neutral"}, (
            f"pif_impact must be improved/degraded/neutral, got {model_data['pif_impact']}"
        )
