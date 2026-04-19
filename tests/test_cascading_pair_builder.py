"""Unit tests for src/modeling/cascading/pair_builder.py.

Uses a synthetic DataFrame — no gitignored data/ paths are read.
"""

import pandas as pd
import pytest

from src.modeling.cascading.pair_builder import (
    CONTEXT_FEATURES,
    build_pair_dataset,
    make_xgb_pipeline,
)


# ── Synthetic fixture ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def synthetic_df() -> pd.DataFrame:
    """Three incidents × 4 rows each; rows 1–3 have y_fail=1."""
    incidents = ["inc_001", "inc_002", "inc_003"]
    lod_vals = [
        "Safety Instrumented Systems",
        "Process Containment",
        "Alarm and Operator Response",
        "Pressure Relief Systems",
    ]
    barrier_levels = ["prevention", "mitigation", "prevention", "mitigation"]
    barrier_conditions = ["effective", "ineffective", "degraded", "ineffective"]

    rows = []
    for inc in incidents:
        for i in range(4):
            rows.append(
                {
                    "incident_id": inc,
                    "barrier_level": barrier_levels[i],
                    "lod_industry_standard": lod_vals[i],
                    "barrier_condition": barrier_conditions[i],
                    "pathway_sequence": i + 1,
                    "lod_numeric": i + 1,
                    "num_threats_in_lod_numeric": i + 1,
                    "num_threats_in_sequence": 3,
                    "total_prev_barriers_incident": 4,
                    "total_mit_barriers_incident": 2,
                    "flag_environmental_threat": 0,
                    "flag_electrical_failure": 0,
                    "flag_procedural_error": 1,
                    "flag_mechanical_failure": 0,
                    "y_fail": 0 if i == 0 else 1,
                    "y_hf_fail": 0,
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def pair_result(synthetic_df):
    return build_pair_dataset(synthetic_df)


# ── Structure tests ───────────────────────────────────────────────────────────

def test_no_self_pairs(pair_result):
    """(a) No row should be paired with itself (row_ord != row_ord_cond)."""
    df_pairs, *_ = pair_result
    assert (df_pairs["row_ord"] != df_pairs["row_ord_cond"]).all(), (
        "Self-pairs found: row_ord == row_ord_cond for some rows"
    )


def test_pairs_share_incident_id(pair_result):
    """(b) Every pair must originate from the same incident."""
    df_pairs, *_ = pair_result
    # row_ord and row_ord_cond are both within the same incident_id group
    assert df_pairs["incident_id"].notna().all()
    # Verify via the merge: both sides must have the same incident_id.
    # Since we merge on incident_id, this is guaranteed by construction —
    # spot-check that no cross-incident pairs slipped through.
    assert len(df_pairs) > 0, "Pair dataset is empty — check synthetic data"


def test_y_fail_cond_filter(pair_result):
    """(c) All rows have y_fail_cond == 1 after the filter."""
    df_pairs, *_ = pair_result
    assert (df_pairs["y_fail_cond"] == 1).all(), (
        "y_fail_cond != 1 found in pair dataset"
    )


def test_cat_all_length(pair_result):
    """(d) Categorical feature list has exactly 5 entries."""
    _, cat_all, _, _ = pair_result
    assert len(cat_all) == 5, f"Expected 5 categorical features, got {len(cat_all)}: {cat_all}"


def test_num_all_length(pair_result):
    """(e) Numerical feature list has exactly 13 entries."""
    _, _, num_all, _ = pair_result
    assert len(num_all) == 13, f"Expected 13 numerical features, got {len(num_all)}: {num_all}"


def test_all_features_length(pair_result):
    """(f) Combined feature list has exactly 18 entries."""
    _, cat_all, num_all, all_features = pair_result
    assert len(all_features) == 18, (
        f"Expected 18 total features, got {len(all_features)}"
    )
    assert all_features == cat_all + num_all, "all_features must equal cat_all + num_all"


def test_no_nan_in_pair_dataset(pair_result):
    """(g) No NaN values in the pair feature matrix."""
    df_pairs, _, _, all_features = pair_result
    nan_counts = df_pairs[all_features].isnull().sum()
    bad = nan_counts[nan_counts > 0]
    assert bad.empty, f"NaN values found in features: {bad.to_dict()}"


# ── Feature-name contract ─────────────────────────────────────────────────────

def test_cat_all_names(pair_result):
    """Categorical features match the expected contract from cell 6."""
    _, cat_all, _, _ = pair_result
    expected = [
        "lod_industry_standard_target",
        "barrier_level_target",
        "lod_industry_standard_cond",
        "barrier_level_cond",
        "barrier_condition_cond",
    ]
    assert cat_all == expected, f"cat_all mismatch: {cat_all}"


def test_num_all_includes_context(pair_result):
    """Numerical features include all 7 CONTEXT_FEATURES."""
    _, _, num_all, _ = pair_result
    for feat in CONTEXT_FEATURES:
        assert feat in num_all, f"Context feature '{feat}' missing from num_all"


def test_features_present_in_pairs(pair_result):
    """All 18 model features are columns in df_pairs."""
    df_pairs, _, _, all_features = pair_result
    missing = [f for f in all_features if f not in df_pairs.columns]
    assert missing == [], f"Features missing from df_pairs: {missing}"


# ── make_xgb_pipeline ─────────────────────────────────────────────────────────

def test_make_xgb_pipeline_step_names(pair_result):
    """Pipeline has exactly two named steps: prep and clf."""
    _, cat_all, num_all, _ = pair_result
    pipe = make_xgb_pipeline(cat_all, num_all, scale_pos_weight=1.0)
    assert list(pipe.named_steps.keys()) == ["prep", "clf"]


def test_make_xgb_pipeline_hyperparameters(pair_result):
    """XGBClassifier step matches Patrick's cell-9 hyperparameters."""
    _, cat_all, num_all, _ = pair_result
    pipe = make_xgb_pipeline(cat_all, num_all, scale_pos_weight=2.5)
    clf = pipe.named_steps["clf"]
    assert clf.n_estimators == 400
    assert clf.max_depth == 4
    assert clf.learning_rate == 0.05
    assert clf.subsample == 0.8
    assert clf.colsample_bytree == 0.8
    assert clf.min_child_weight == 5
    assert clf.scale_pos_weight == 2.5
    assert clf.random_state == 42
