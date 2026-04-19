"""Artifact verification tests for cascading train.py.

Must be run AFTER `python -m src.modeling.cascading.train`.
Skipped automatically when the joblib artifacts are absent (e.g. CI without data).
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

_FAIL_JOBLIB = pathlib.Path("data/models/artifacts/xgb_cascade_y_fail_pipeline.joblib")
_HF_FAIL_JOBLIB = pathlib.Path("data/models/artifacts/xgb_cascade_y_hf_fail_pipeline.joblib")
_FAIL_META = pathlib.Path("data/models/artifacts/xgb_cascade_y_fail_metadata.json")
_HF_FAIL_META = pathlib.Path("data/models/artifacts/xgb_cascade_y_hf_fail_metadata.json")
_CV_REPORT = pathlib.Path("data/models/evaluation/cascading_cv_report.md")

pytestmark = pytest.mark.skipif(
    not _FAIL_JOBLIB.exists() or not _HF_FAIL_JOBLIB.exists(),
    reason="cascading pipeline artifacts not present — run `python -m src.modeling.cascading.train` first",
)

# ── (a) Pipeline file existence + structure ───────────────────────────────────


def test_y_fail_pipeline_loads():
    import joblib
    from sklearn.pipeline import Pipeline

    pipe = joblib.load(_FAIL_JOBLIB)
    assert isinstance(pipe, Pipeline), "y_fail artifact is not a sklearn Pipeline"
    assert list(pipe.named_steps.keys()) == ["prep", "clf"], (
        f"Expected steps ['prep', 'clf'], got {list(pipe.named_steps.keys())}"
    )


def test_y_hf_fail_pipeline_loads():
    import joblib
    from sklearn.pipeline import Pipeline

    pipe = joblib.load(_HF_FAIL_JOBLIB)
    assert isinstance(pipe, Pipeline), "y_hf_fail artifact is not a sklearn Pipeline"
    assert list(pipe.named_steps.keys()) == ["prep", "clf"], (
        f"Expected steps ['prep', 'clf'], got {list(pipe.named_steps.keys())}"
    )


# ── (b) XGBClassifier hyperparameter assertions ───────────────────────────────


@pytest.mark.parametrize("joblib_path", [_FAIL_JOBLIB, _HF_FAIL_JOBLIB])
def test_xgb_hyperparameters_match_patrick_cell9(joblib_path: pathlib.Path):
    import joblib
    import xgboost as xgb

    pipe = joblib.load(joblib_path)
    clf = pipe.named_steps["clf"]
    assert isinstance(clf, xgb.XGBClassifier), f"clf is {type(clf)}, expected XGBClassifier"

    params = clf.get_params()
    assert params["n_estimators"] == 400, f"n_estimators={params['n_estimators']}, expected 400"
    assert params["max_depth"] == 4, f"max_depth={params['max_depth']}, expected 4"
    assert params["learning_rate"] == pytest.approx(0.05), f"learning_rate={params['learning_rate']}"
    assert params["subsample"] == pytest.approx(0.8), f"subsample={params['subsample']}"
    assert params["colsample_bytree"] == pytest.approx(0.8), f"colsample_bytree={params['colsample_bytree']}"
    assert params["min_child_weight"] == 5, f"min_child_weight={params['min_child_weight']}, expected 5"


# ── (c) predict_proba returns valid 2-column probability array ────────────────


@pytest.mark.parametrize("joblib_path", [_FAIL_JOBLIB, _HF_FAIL_JOBLIB])
def test_predict_proba_sums_to_one(joblib_path: pathlib.Path):
    import joblib
    import pandas as pd
    from src.modeling.cascading.pair_builder import (
        CONTEXT_FEATURES,
    )

    pipe = joblib.load(joblib_path)

    # Synthetic pair row: use string placeholders for cat features, 0.0 for num.
    # OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1) handles unknown cats.
    row = {
        "lod_industry_standard_target": "regulatory",
        "barrier_level_target": "passive",
        "lod_industry_standard_cond": "regulatory",
        "barrier_level_cond": "passive",
        "barrier_condition_cond": "normal",
        "pathway_sequence_target": 1.0,
        "lod_numeric_target": 1.0,
        "num_threats_in_lod_numeric_target": 1.0,
        "pathway_sequence_cond": 1.0,
        "lod_numeric_cond": 1.0,
        "num_threats_in_lod_numeric_cond": 1.0,
    }
    for feat in CONTEXT_FEATURES:
        row[feat] = 0.0

    X_syn = pd.DataFrame([row])
    proba = pipe.predict_proba(X_syn)

    assert proba.shape == (1, 2), f"Expected shape (1, 2), got {proba.shape}"
    assert abs(proba.sum(axis=1)[0] - 1.0) <= 1e-9, (
        f"predict_proba row sums to {proba.sum(axis=1)[0]}, expected 1.0"
    )


# ── (d) Metadata JSON completeness ────────────────────────────────────────────

_REQUIRED_METADATA_KEYS = {
    "model_name", "target", "model_type", "categorical_features",
    "numerical_features", "all_features", "risk_tier_thresholds",
    "training_rows", "positive_rate", "scale_pos_weight",
    "patrick_hyperparameters", "cv_scores",
}


@pytest.mark.parametrize(
    "meta_path,expected_target",
    [
        (_FAIL_META, "y_fail_target"),
        (_HF_FAIL_META, "y_hf_fail_target"),
    ],
)
def test_metadata_keys_and_feature_count(
    meta_path: pathlib.Path, expected_target: str
):
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    missing = _REQUIRED_METADATA_KEYS - set(meta.keys())
    assert not missing, f"Metadata missing keys: {missing}"

    assert meta["target"] == expected_target, (
        f"target={meta['target']}, expected {expected_target}"
    )
    assert len(meta["all_features"]) == 18, (
        f"all_features length={len(meta['all_features'])}, expected 18"
    )
    assert len(meta["categorical_features"]) == 5, (
        f"categorical_features length={len(meta['categorical_features'])}, expected 5"
    )
    assert len(meta["numerical_features"]) == 13, (
        f"numerical_features length={len(meta['numerical_features'])}, expected 13"
    )


# ── (e) cascading_cv_report.md content ───────────────────────────────────────


def test_cv_report_exists():
    assert _CV_REPORT.exists(), f"CV report not found at {_CV_REPORT}"


def test_cv_report_has_both_targets():
    content = _CV_REPORT.read_text(encoding="utf-8")
    assert "y_fail_target" in content, "CV report missing y_fail_target section"
    assert "y_hf_fail_target" in content, "CV report missing y_hf_fail_target section"


def test_cv_report_has_five_fold_rows_per_target():
    content = _CV_REPORT.read_text(encoding="utf-8")
    # Split on target sections; count table data rows in each.
    sections = content.split("## ")
    target_sections = [s for s in sections if s.startswith("y_fail_target") or s.startswith("y_hf_fail_target")]
    assert len(target_sections) == 2, (
        f"Expected 2 target sections, found {len(target_sections)}"
    )
    for section in target_sections:
        fold_rows = [
            ln for ln in section.splitlines()
            if ln.startswith("| ") and ln.strip().endswith("|")
            and "Fold" not in ln and "---" not in ln
        ]
        assert len(fold_rows) == 5, (
            f"Section '{section[:30]}...' has {len(fold_rows)} fold rows, expected 5"
        )
