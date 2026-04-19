"""Tests for R023: SHAP TreeExplainer in-memory smoke test.

Verifies:
  (a) build_tree_explainer returns a shap.TreeExplainer instance.
  (b) compute_shap_for_record returns a 1-D array of length 18.
  (c) Returned feature names match metadata["all_features"] exactly.
  (d) No shap/explainer files exist under data/models/artifacts/.
  (e) SHAP values are in margin (log-odds) space.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
import shap

_ARTIFACTS_DIR = Path("data/models/artifacts")
_PARQUET_PATH = Path("data/processed/cascading_training.parquet")
_PIPELINE_PATH = _ARTIFACTS_DIR / "xgb_cascade_y_fail_pipeline.joblib"
_META_PATH = _ARTIFACTS_DIR / "xgb_cascade_y_fail_metadata.json"

# ---------------------------------------------------------------------------
# Skip guard — artifacts are gitignored; skip if not present.
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not _PIPELINE_PATH.exists() or not _META_PATH.exists(),
    reason="T02 artifacts not present (run python -m src.modeling.cascading.train first)",
)


@pytest.fixture(scope="module")
def pipeline():
    return joblib.load(_PIPELINE_PATH)


@pytest.fixture(scope="module")
def metadata():
    return json.loads(_META_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def first_pair_row(metadata):
    """Return the first row of the pair dataset as a plain dict."""
    from src.modeling.cascading.pair_builder import build_pair_dataset

    df = pd.read_parquet(_PARQUET_PATH)
    df_pairs, _cat, _num, all_features = build_pair_dataset(df)
    return df_pairs.iloc[0][all_features].to_dict()


# ---------------------------------------------------------------------------
# (a) build_tree_explainer returns shap.TreeExplainer
# ---------------------------------------------------------------------------


def test_build_tree_explainer_returns_correct_type(pipeline):
    from src.modeling.cascading.shap_probe import build_tree_explainer

    explainer = build_tree_explainer(pipeline)
    assert isinstance(explainer, shap.TreeExplainer), (
        f"Expected shap.TreeExplainer, got {type(explainer)}"
    )


# ---------------------------------------------------------------------------
# (b) compute_shap_for_record returns length-18 array
# ---------------------------------------------------------------------------


def test_shap_values_length(pipeline, metadata, first_pair_row):
    from src.modeling.cascading.shap_probe import build_tree_explainer, compute_shap_for_record

    explainer = build_tree_explainer(pipeline)
    all_features = metadata["all_features"]
    sv, feat_names = compute_shap_for_record(pipeline, explainer, first_pair_row, all_features)

    expected_len = len(all_features)
    assert sv.ndim == 1, f"Expected 1-D shap_values, got shape {sv.shape}"
    assert len(sv) == expected_len, (
        f"shap_values length {len(sv)} != expected {expected_len} (all_features)"
    )


# ---------------------------------------------------------------------------
# (c) Returned feature names match metadata["all_features"] exactly
# ---------------------------------------------------------------------------


def test_feature_names_match_metadata(pipeline, metadata, first_pair_row):
    from src.modeling.cascading.shap_probe import build_tree_explainer, compute_shap_for_record

    explainer = build_tree_explainer(pipeline)
    all_features = metadata["all_features"]
    _sv, feat_names = compute_shap_for_record(pipeline, explainer, first_pair_row, all_features)

    assert feat_names == all_features, (
        "Returned feature names do not match metadata all_features.\n"
        f"Diff: {[f for f in all_features if f not in feat_names]}"
    )


# ---------------------------------------------------------------------------
# (d) No shap/explainer artefacts written to disk
# ---------------------------------------------------------------------------


def test_no_shap_files_on_disk():
    # R023 bans serialising the cascading TreeExplainer.  Pre-existing
    # shap_background_model*.npy belong to the original pipeline and are not
    # subject to this check — scope the scan to cascade-specific names only.
    shap_files = (
        list(_ARTIFACTS_DIR.glob("*cascade*shap*"))
        + list(_ARTIFACTS_DIR.glob("*cascade*explainer*"))
        + list(_ARTIFACTS_DIR.glob("*shap*cascade*"))
        + list(_ARTIFACTS_DIR.glob("*explainer*cascade*"))
    )
    assert shap_files == [], (
        "R023 serialisation ban violated — cascading shap/explainer file(s) found: "
        + str([str(p) for p in shap_files])
    )


# ---------------------------------------------------------------------------
# (e) Values in margin (log-odds) space
# ---------------------------------------------------------------------------


def test_shap_values_are_margin_space(pipeline, metadata, first_pair_row):
    from src.modeling.cascading.shap_probe import build_tree_explainer, compute_shap_for_record

    explainer = build_tree_explainer(pipeline)
    all_features = metadata["all_features"]
    sv, _ = compute_shap_for_record(pipeline, explainer, first_pair_row, all_features)

    # Sanity: expected_value is a finite log-odds, not a probability near [0,1].
    ev = float(
        explainer.expected_value[1]
        if hasattr(explainer.expected_value, "__len__")
        else explainer.expected_value
    )
    assert abs(ev) < 10, f"expected_value {ev:.4f} outside sanity bound ±10 (log-odds space)"

    # Additive check: shap_values.sum() + expected_value ≈ model margin output.
    prep = pipeline.named_steps["prep"]
    clf = pipeline.named_steps["clf"]
    row_df = pd.DataFrame([first_pair_row])[all_features]
    X_prep = prep.transform(row_df)

    margin_out = float(clf.predict(X_prep, output_margin=True)[0])
    shap_approx = float(sv.sum()) + ev
    assert abs(shap_approx - margin_out) < 1e-4, (
        f"SHAP sum+bias {shap_approx:.6f} != model margin {margin_out:.6f} "
        f"(diff={abs(shap_approx - margin_out):.2e})"
    )
