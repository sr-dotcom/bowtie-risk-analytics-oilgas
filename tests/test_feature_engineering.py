"""Tests for src/modeling/feature_engineering.py.

Tests cover:
- build_feature_matrix() produces expected columns
- Label derivation from barrier_status (NOT barrier_failed column)
- Unknown barrier_status rows are excluded
- barrier_family column populated
- OrdinalEncoder encoding of known/unknown categories
- feature_names.json contract (no metadata/label columns)
- encoder.joblib roundtrip
- PIF boolean columns present as 0/1 integers
- supporting_text_count present as numeric
- Orphan incidents produce zero rows
- GroupKFold splits with no group leakage (FEAT-04)
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from src.modeling.feature_engineering import get_group_kfold_splits, CATEGORICAL_FEATURES

# ---------------------------------------------------------------------------
# Helper: synthetic CSV writer
# ---------------------------------------------------------------------------

_CONTROLS_COLUMNS = [
    "incident_id", "control_id", "name", "side", "barrier_role",
    "barrier_type", "line_of_defense", "lod_basis", "linked_threat_ids",
    "linked_consequence_ids", "barrier_status", "barrier_failed",
    "human_contribution_value", "barrier_failed_human", "confidence",
    "supporting_text_count", "source_agency", "provider_bucket", "json_path",
    "pathway_sequence", "upstream_failure_rate",
]

_INCIDENTS_PIF_COLS = [
    "incident__pifs__people__competence_mentioned",
    "incident__pifs__people__fatigue_mentioned",
    "incident__pifs__people__communication_mentioned",
    "incident__pifs__people__situational_awareness_mentioned",
    "incident__pifs__work__procedures_mentioned",
    "incident__pifs__work__workload_mentioned",
    "incident__pifs__work__time_pressure_mentioned",
    "incident__pifs__work__tools_equipment_mentioned",
    "incident__pifs__organisation__safety_culture_mentioned",
    "incident__pifs__organisation__management_of_change_mentioned",
    "incident__pifs__organisation__supervision_mentioned",
    "incident__pifs__organisation__training_mentioned",
]


def _make_test_csvs(tmp_path: Path) -> tuple[Path, Path]:
    """Write synthetic controls and incidents CSVs to tmp_path.

    Returns:
        Tuple of (controls_path, incidents_path).

    Test data layout:
    - inc_1: 2 controls (failed+hf_true, active+hf_false)
    - inc_2: 1 control (degraded+hf_true)
    - inc_3: 1 control (unknown - should be excluded)
    - inc_4: 1 control (not_installed+hf_false)
    - inc_5: 1 control (bypassed+hf_true)
    - inc_6: 1 control (worked+hf_false)
    - orphan_inc: no controls
    """
    controls_rows = [
        # incident_id, control_id, name, side, barrier_role, barrier_type,
        # line_of_defense, lod_basis, linked_threat_ids, linked_consequence_ids,
        # barrier_status, barrier_failed, human_contribution_value, barrier_failed_human,
        # confidence, supporting_text_count, source_agency, provider_bucket, json_path,
        # pathway_sequence, upstream_failure_rate
        [
            "inc_1", "c1", "Emergency Shutdown", "prevention", "detection",
            "engineering", "1st", None, None, None,
            "failed", True, "high", True,
            "high", 3, "BSEE", "bsee", "path/a.json", 1, 0.0,
        ],
        [
            "inc_1", "c2", "Safety Valve", "prevention", "safeguard",
            "engineering", "2nd", None, None, None,
            "active", False, "none", False,
            "medium", 1, "BSEE", "bsee", "path/a.json", 2, 1.0,
        ],
        [
            "inc_2", "c3", "Training Program", "mitigation", "mitigation",
            "administrative", "recovery", None, None, None,
            "degraded", True, "medium", True,
            "medium", 2, "CSB", "csb", "path/b.json", 1, 0.0,
        ],
        [
            "inc_3", "c4", "PPE", "prevention", "protection",
            "ppe", "1st", None, None, None,
            "unknown", False, "low", False,
            "low", 0, "BSEE", "bsee", "path/c.json", 1, 0.0,
        ],
        [
            "inc_4", "c5", "Blowout Preventer", "prevention", "containment",
            "engineering", "3rd", None, None, None,
            "not_installed", False, "none", False,
            "high", 4, "BSEE", "bsee", "path/d.json", 1, 0.0,
        ],
        [
            "inc_5", "c6", "Spill Response", "mitigation", "recovery",
            "administrative", "recovery", None, None, None,
            "bypassed", False, "medium", True,
            "medium", 1, "CSB", "csb", "path/e.json", 1, 0.5,
        ],
        [
            "inc_6", "c7", "Alarm System", "prevention", "detection",
            "engineering", "1st", None, None, None,
            "worked", False, "none", False,
            "high", 2, "BSEE", "bsee", "path/f.json", 1, 0.0,
        ],
    ]

    controls_df = pd.DataFrame(controls_rows, columns=_CONTROLS_COLUMNS)

    # Build incidents CSV: incident_id + primary_threat_category + 12 PIF _mentioned booleans
    _INCIDENTS_COLUMNS = ["incident_id", "primary_threat_category"] + _INCIDENTS_PIF_COLS
    incidents_rows = [
        ["inc_1", "equipment_failure"] + [True] + [False] * 11,
        ["inc_2", "process_deviation"] + [False] * 12,
        ["inc_3", "equipment_failure"] + [False] * 12,
        ["inc_4", "equipment_failure"] + [False] * 12,
        ["inc_5", "process_deviation"] + [True, False, True] + [False] * 9,
        ["inc_6", "equipment_failure"] + [False] * 12,
        ["orphan_inc", "equipment_failure"] + [False] * 12,
    ]
    incidents_df = pd.DataFrame(incidents_rows, columns=_INCIDENTS_COLUMNS)

    controls_path = tmp_path / "controls.csv"
    incidents_path = tmp_path / "incidents.csv"
    controls_df.to_csv(controls_path, index=False)
    incidents_df.to_csv(incidents_path, index=False)
    return controls_path, incidents_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def csvs(tmp_path):
    """Return (controls_path, incidents_path, artifacts_dir)."""
    controls_path, incidents_path = _make_test_csvs(tmp_path)
    artifacts_dir = tmp_path / "artifacts"
    return controls_path, incidents_path, artifacts_dir


@pytest.fixture
def feature_df(csvs):
    """Run build_feature_matrix and return the DataFrame."""
    from src.modeling.feature_engineering import build_feature_matrix

    controls_path, incidents_path, artifacts_dir = csvs
    return build_feature_matrix(controls_path, incidents_path, artifacts_dir)


# ---------------------------------------------------------------------------
# Test 1: Output DataFrame has expected columns
# ---------------------------------------------------------------------------

def test_output_has_expected_columns(feature_df):
    """build_feature_matrix returns a DataFrame with all required columns."""
    from src.modeling.feature_engineering import (
        CATEGORICAL_FEATURES,
        PIF_FEATURES,
        NUMERIC_FEATURES,
        METADATA_COLUMNS,
        LABEL_COLUMNS,
    )
    expected_cols = set(
        METADATA_COLUMNS + CATEGORICAL_FEATURES + PIF_FEATURES + NUMERIC_FEATURES + LABEL_COLUMNS
    )
    assert expected_cols.issubset(set(feature_df.columns)), (
        f"Missing columns: {expected_cols - set(feature_df.columns)}"
    )


# ---------------------------------------------------------------------------
# Test 2: Unknown barrier_status rows are excluded
# ---------------------------------------------------------------------------

def test_unknown_barrier_status_excluded(feature_df):
    """Rows with barrier_status == 'unknown' are excluded from output."""
    # inc_3 has barrier_status='unknown'; should not appear
    assert "inc_3" not in feature_df["incident_id"].values, (
        "inc_3 (barrier_status='unknown') should be excluded"
    )


def test_row_count_excludes_unknown(feature_df):
    """Output has exactly 6 rows (7 total - 1 unknown - 0 orphan controls)."""
    assert len(feature_df) == 6, f"Expected 6 rows, got {len(feature_df)}"


# ---------------------------------------------------------------------------
# Test 3: label_barrier_failed derived from barrier_status
# ---------------------------------------------------------------------------

def test_label_barrier_failed_for_failed_status(feature_df):
    """label_barrier_failed == 1 when barrier_status is 'failed'."""
    row = feature_df[feature_df["control_id"] == "c1"]
    assert len(row) == 1
    assert row.iloc[0]["label_barrier_failed"] == 1


def test_label_barrier_failed_for_active_status(feature_df):
    """label_barrier_failed == 0 when barrier_status is 'active'."""
    row = feature_df[feature_df["control_id"] == "c2"]
    assert len(row) == 1
    assert row.iloc[0]["label_barrier_failed"] == 0


def test_label_barrier_failed_for_degraded_status(feature_df):
    """label_barrier_failed == 1 when barrier_status is 'degraded'."""
    row = feature_df[feature_df["control_id"] == "c3"]
    assert len(row) == 1
    assert row.iloc[0]["label_barrier_failed"] == 1


def test_label_barrier_failed_for_not_installed_and_bypassed(feature_df):
    """label_barrier_failed == 1 for not_installed and bypassed."""
    not_installed = feature_df[feature_df["control_id"] == "c5"]
    bypassed = feature_df[feature_df["control_id"] == "c6"]
    assert not_installed.iloc[0]["label_barrier_failed"] == 1
    assert bypassed.iloc[0]["label_barrier_failed"] == 1


def test_label_barrier_failed_for_worked_status(feature_df):
    """label_barrier_failed == 0 when barrier_status is 'worked'."""
    row = feature_df[feature_df["control_id"] == "c7"]
    assert len(row) == 1
    assert row.iloc[0]["label_barrier_failed"] == 0


# ---------------------------------------------------------------------------
# Test 4: label_barrier_failed_human requires both conditions
# ---------------------------------------------------------------------------

def test_label_barrier_failed_human_requires_both_conditions(feature_df):
    """label_barrier_failed_human == 1 only when both label_barrier_failed and barrier_failed_human are True."""
    # c1: barrier_status=failed, barrier_failed_human=True => 1
    c1 = feature_df[feature_df["control_id"] == "c1"].iloc[0]
    assert c1["label_barrier_failed_human"] == 1

    # c2: barrier_status=active (label_barrier_failed=0) => 0
    c2 = feature_df[feature_df["control_id"] == "c2"].iloc[0]
    assert c2["label_barrier_failed_human"] == 0

    # c5: barrier_status=not_installed, barrier_failed_human=False => 0
    c5 = feature_df[feature_df["control_id"] == "c5"].iloc[0]
    assert c5["label_barrier_failed_human"] == 0

    # c6: barrier_status=bypassed, barrier_failed_human=True => 1
    c6 = feature_df[feature_df["control_id"] == "c6"].iloc[0]
    assert c6["label_barrier_failed_human"] == 1


# ---------------------------------------------------------------------------
# Test 5: barrier_family column is populated
# ---------------------------------------------------------------------------

def test_barrier_family_column_populated(feature_df):
    """barrier_family column has no null/empty values."""
    assert feature_df["barrier_family"].notna().all(), "barrier_family has null values"
    assert (feature_df["barrier_family"] != "").all(), "barrier_family has empty strings"


# ---------------------------------------------------------------------------
# Test 6: OrdinalEncoder encodes known categories
# ---------------------------------------------------------------------------

def test_ordinal_encoder_known_categories(feature_df):
    """Known categorical values encode to non-negative integers."""
    from src.modeling.feature_engineering import CATEGORICAL_FEATURES

    for col in CATEGORICAL_FEATURES:
        encoded_vals = feature_df[col]
        # All values should be numeric integers
        assert pd.api.types.is_integer_dtype(encoded_vals) or pd.api.types.is_float_dtype(encoded_vals), (
            f"{col} should be numeric after encoding"
        )
        # Known values should be >= 0 (unknown would be -1)
        # Most rows use known categories
        known_rows = feature_df[feature_df["incident_id"].isin(["inc_1", "inc_2"])]
        if len(known_rows) > 0:
            assert (known_rows[col] >= 0).all(), (
                f"{col} has negative values for known categories"
            )


# ---------------------------------------------------------------------------
# Test 7: feature_names.json contract
# ---------------------------------------------------------------------------

def test_feature_names_json_excludes_metadata_and_labels(csvs, tmp_path):
    """feature_names.json does NOT contain incident_id, control_id, or label columns."""
    from src.modeling.feature_engineering import build_feature_matrix

    controls_path, incidents_path, artifacts_dir = csvs
    build_feature_matrix(controls_path, incidents_path, artifacts_dir)

    feature_names_path = artifacts_dir / "feature_names.json"
    assert feature_names_path.exists(), "feature_names.json not created"

    with open(feature_names_path) as f:
        feature_names_raw = json.load(f)

    # Support both formats: flat list (legacy) or list-of-dicts (Phase 3+)
    if feature_names_raw and isinstance(feature_names_raw[0], dict):
        feature_names = [f["name"] for f in feature_names_raw]
    else:
        feature_names = feature_names_raw

    assert "incident_id" not in feature_names, "incident_id should not be in feature_names"
    assert "control_id" not in feature_names, "control_id should not be in feature_names"
    assert "label_barrier_failed" not in feature_names, "label should not be in feature_names"
    assert "label_barrier_failed_human" not in feature_names, "label should not be in feature_names"


def test_feature_names_json_contains_expected_features(csvs):
    """feature_names.json contains side, barrier_family, pif_competence, supporting_text_count."""
    from src.modeling.feature_engineering import build_feature_matrix

    controls_path, incidents_path, artifacts_dir = csvs
    build_feature_matrix(controls_path, incidents_path, artifacts_dir)

    with open(artifacts_dir / "feature_names.json") as f:
        feature_names_raw = json.load(f)

    # Support both formats: flat list (legacy) or list-of-dicts (Phase 3+)
    if feature_names_raw and isinstance(feature_names_raw[0], dict):
        feature_names = [f["name"] for f in feature_names_raw]
    else:
        feature_names = feature_names_raw

    assert "side" in feature_names
    assert "barrier_family" in feature_names
    assert "pif_competence" in feature_names
    assert "supporting_text_count" in feature_names
    assert len(feature_names) == 17, f"Expected 17 features, got {len(feature_names)}"


# ---------------------------------------------------------------------------
# Test 8: encoder.joblib roundtrip
# ---------------------------------------------------------------------------

def test_encoder_joblib_roundtrip(csvs):
    """encoder.joblib can be loaded and used to transform new data."""
    from src.modeling.feature_engineering import build_feature_matrix

    controls_path, incidents_path, artifacts_dir = csvs
    build_feature_matrix(controls_path, incidents_path, artifacts_dir)

    encoder_path = artifacts_dir / "encoder.joblib"
    assert encoder_path.exists(), "encoder.joblib not created"

    encoder = joblib.load(encoder_path)

    # Verify encoder has one category array per categorical feature.
    n_cat = len(CATEGORICAL_FEATURES)
    assert len(encoder.categories_) == n_cat, f"Encoder should have {n_cat} category arrays"

    # Test unknown categories map to -1.
    unknown_row = [["new_side", "new_type", "4th", "new_family", "NEW_AGENCY"]]
    encoded_unk = encoder.transform(unknown_row)
    assert encoded_unk.shape == (1, n_cat), f"Shape mismatch: {encoded_unk.shape}"
    assert (encoded_unk == -1).all(), "All unknowns should encode to -1"


# ---------------------------------------------------------------------------
# Test 9: metadata columns in DataFrame but not in feature_names
# ---------------------------------------------------------------------------

def test_metadata_columns_in_dataframe_not_in_feature_names(csvs):
    """incident_id and control_id are in the output DataFrame but NOT in feature_names.json."""
    from src.modeling.feature_engineering import build_feature_matrix

    controls_path, incidents_path, artifacts_dir = csvs
    df = build_feature_matrix(controls_path, incidents_path, artifacts_dir)

    assert "incident_id" in df.columns, "incident_id should be in DataFrame"
    assert "control_id" in df.columns, "control_id should be in DataFrame"

    with open(artifacts_dir / "feature_names.json") as f:
        feature_names_raw = json.load(f)

    # Support both formats: flat list (legacy) or list-of-dicts (Phase 3+)
    if feature_names_raw and isinstance(feature_names_raw[0], dict):
        feature_names = [f["name"] for f in feature_names_raw]
    else:
        feature_names = feature_names_raw

    assert "incident_id" not in feature_names
    assert "control_id" not in feature_names


# ---------------------------------------------------------------------------
# Test 10: PIF columns present as 0/1 integers
# ---------------------------------------------------------------------------

def test_pif_columns_present_as_integers(feature_df):
    """All 12 PIF features are present as 0/1 integer columns."""
    from src.modeling.feature_engineering import PIF_FEATURES

    for pif_col in PIF_FEATURES:
        assert pif_col in feature_df.columns, f"Missing PIF column: {pif_col}"
        unique_vals = set(feature_df[pif_col].unique())
        assert unique_vals.issubset({0, 1}), (
            f"PIF column {pif_col} has non-binary values: {unique_vals}"
        )


def test_pif_join_propagation(feature_df):
    """PIF columns correctly propagate from incident to its controls."""
    # inc_1 has competence_mentioned=True -> pif_competence should be 1 for inc_1 rows
    inc_1_rows = feature_df[feature_df["incident_id"] == "inc_1"]
    assert (inc_1_rows["pif_competence"] == 1).all(), (
        "pif_competence should be 1 for inc_1 controls"
    )

    # inc_2 has all PIFs=False -> pif_competence should be 0
    inc_2_rows = feature_df[feature_df["incident_id"] == "inc_2"]
    assert (inc_2_rows["pif_competence"] == 0).all(), (
        "pif_competence should be 0 for inc_2 controls"
    )


# ---------------------------------------------------------------------------
# Test 11: supporting_text_count as numeric feature
# ---------------------------------------------------------------------------

def test_supporting_text_count_present_as_numeric(feature_df):
    """supporting_text_count is present as a numeric (integer) feature."""
    assert "supporting_text_count" in feature_df.columns
    assert pd.api.types.is_integer_dtype(feature_df["supporting_text_count"]) or \
           pd.api.types.is_float_dtype(feature_df["supporting_text_count"]), (
        "supporting_text_count should be numeric"
    )


# ---------------------------------------------------------------------------
# Test 12: Orphan incidents produce zero rows
# ---------------------------------------------------------------------------

def test_orphan_incidents_produce_zero_rows(feature_df):
    """incident_id 'orphan_inc' (no controls) produces no rows in output."""
    orphan_rows = feature_df[feature_df["incident_id"] == "orphan_inc"]
    assert len(orphan_rows) == 0, (
        f"orphan_inc should produce 0 rows, got {len(orphan_rows)}"
    )


# ---------------------------------------------------------------------------
# Test 13: GroupKFold splits — FEAT-04
# ---------------------------------------------------------------------------

class TestGroupKFoldSplits:
    """Tests for get_group_kfold_splits (FEAT-04)."""

    def test_returns_n_splits_folds(self):
        """get_group_kfold_splits returns exactly n_splits folds."""
        X = np.array([[1, 2], [3, 4], [5, 6], [7, 8], [9, 10], [11, 12]])
        y = np.array([0, 1, 0, 1, 0, 1])
        groups = np.array(["A", "B", "C", "D", "E", "F"])
        splits = get_group_kfold_splits(X, y, groups, n_splits=3)
        assert len(splits) == 3

    def test_five_folds_default(self):
        """Default n_splits=5 produces 5 folds."""
        X = np.zeros((10, 2))
        y = np.zeros(10)
        groups = np.array(["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"])
        splits = get_group_kfold_splits(X, y, groups)
        assert len(splits) == 5

    def test_no_group_leakage(self):
        """No incident_id appears in both train and test for any fold."""
        # 4 incidents, each with 2-3 controls
        groups = np.array(["inc1", "inc1", "inc1", "inc2", "inc2",
                           "inc3", "inc3", "inc4", "inc4", "inc4"])
        X = np.random.rand(10, 3)
        y = np.array([1, 0, 1, 0, 1, 0, 1, 0, 1, 0])
        splits = get_group_kfold_splits(X, y, groups, n_splits=2)
        for train_idx, test_idx in splits:
            train_groups = set(groups[train_idx])
            test_groups = set(groups[test_idx])
            assert train_groups.isdisjoint(test_groups), (
                f"Group leakage: {train_groups & test_groups}"
            )

    def test_complete_coverage(self):
        """Every row appears in exactly one test fold."""
        n = 15
        X = np.zeros((n, 2))
        y = np.zeros(n)
        groups = np.array([f"g{i}" for i in range(n)])
        splits = get_group_kfold_splits(X, y, groups, n_splits=5)
        all_test = np.concatenate([test_idx for _, test_idx in splits])
        assert sorted(all_test) == list(range(n))

    def test_same_group_same_partition(self):
        """All rows with the same incident_id land in the same partition."""
        groups = np.array(["A", "A", "A", "B", "B", "C", "C", "C", "C", "D"])
        X = np.zeros((10, 2))
        y = np.zeros(10)
        splits = get_group_kfold_splits(X, y, groups, n_splits=2)
        for train_idx, test_idx in splits:
            for g in ["A", "B", "C", "D"]:
                g_indices = np.where(groups == g)[0]
                in_train = np.isin(g_indices, train_idx).all()
                in_test = np.isin(g_indices, test_idx).all()
                assert in_train or in_test, (
                    f"Group {g} split across train/test"
                )

    def test_returns_numpy_arrays(self):
        """Train and test indices are numpy arrays."""
        X = np.zeros((6, 2))
        y = np.zeros(6)
        groups = np.array(["A", "B", "C", "D", "E", "F"])
        splits = get_group_kfold_splits(X, y, groups, n_splits=3)
        for train_idx, test_idx in splits:
            assert isinstance(train_idx, np.ndarray)
            assert isinstance(test_idx, np.ndarray)
