"""Tests for src/modeling/cascading/data_prep.py.

Regenerates the parquet into a tmp dir and asserts column contract,
row count, label rates, and drop invariants.  Does NOT read from
gitignored data/ paths — the source CSV is in data/models/cascading_input/
(gitignored) so these tests are skipped when the file is absent.
"""

import pytest
import pathlib

# ---------------------------------------------------------------------------
# Conditional skip when the upstream CSV is absent (e.g. fresh clone without
# the source data).
# ---------------------------------------------------------------------------

_BASE_CSV = pathlib.Path("data/models/cascading_input/barrier_model_dataset_base_v3.csv")

pytestmark = pytest.mark.skipif(
    not _BASE_CSV.exists(),
    reason="Source CSV data/models/cascading_input/barrier_model_dataset_base_v3.csv not present",
)


@pytest.fixture(scope="module")
def clean_df(tmp_path_factory):
    """Run prepare_cascading_dataset() once per module into a temp path."""
    import pandas as pd
    from src.modeling.cascading.data_prep import prepare_cascading_dataset

    tmp = tmp_path_factory.mktemp("cascading")
    parquet_path = tmp / "cascading_training.parquet"
    profile_path = tmp / "cascading_training_profile.md"

    df = prepare_cascading_dataset(
        csv_path=_BASE_CSV,
        parquet_path=parquet_path,
        profile_path=profile_path,
    )
    return df, parquet_path, profile_path


# ---------------------------------------------------------------------------
# Row-count and incident-scope tests
# ---------------------------------------------------------------------------


def test_row_count_in_range(clean_df):
    df, *_ = clean_df
    assert 525 <= len(df) <= 535, (
        f"Expected row count in [525, 535], got {len(df)}"
    )


def test_unique_incident_count(clean_df):
    df, *_ = clean_df
    n = df["incident_id"].nunique()
    assert n == 156, f"Expected 156 unique incidents, got {n}"


# ---------------------------------------------------------------------------
# Label-rate tests
# ---------------------------------------------------------------------------


def test_y_fail_mean(clean_df):
    df, *_ = clean_df
    mean = df["y_fail"].mean()
    assert 0.47 <= mean <= 0.50, f"y_fail mean {mean:.4f} out of [0.47, 0.50]"


def test_y_hf_fail_mean(clean_df):
    df, *_ = clean_df
    mean = df["y_hf_fail"].mean()
    assert 0.14 <= mean <= 0.17, f"y_hf_fail mean {mean:.4f} out of [0.14, 0.17]"


# ---------------------------------------------------------------------------
# Row-drop invariants
# ---------------------------------------------------------------------------


def test_no_other_lod(clean_df):
    df, *_ = clean_df
    assert "Other" not in df["lod_industry_standard"].unique(), (
        "'Other' must be dropped from lod_industry_standard"
    )


def test_no_lod_numeric_99(clean_df):
    df, *_ = clean_df
    assert 99 not in df["lod_numeric"].unique(), (
        "lod_numeric == 99 must be dropped"
    )


# ---------------------------------------------------------------------------
# Column contract: forbidden columns
# ---------------------------------------------------------------------------


def test_no_source_agency(clean_df):
    df, *_ = clean_df
    assert "source_agency" not in df.columns


def test_no_mentioned_columns(clean_df):
    df, *_ = clean_df
    mentioned = [c for c in df.columns if c.endswith("_mentioned")]
    assert mentioned == [], f"_mentioned columns must be absent: {mentioned}"


def test_no_control_id(clean_df):
    df, *_ = clean_df
    assert "control_id" not in df.columns


# ---------------------------------------------------------------------------
# Column contract: required columns present
# ---------------------------------------------------------------------------


def test_required_feature_columns_present(clean_df):
    from src.modeling.cascading.data_prep import ENCODED_FEATURES

    df, *_ = clean_df
    missing = [c for c in ENCODED_FEATURES if c not in df.columns]
    assert missing == [], f"Required feature columns missing: {missing}"


def test_labels_present(clean_df):
    df, *_ = clean_df
    assert "y_fail" in df.columns
    assert "y_hf_fail" in df.columns


def test_incident_id_present(clean_df):
    df, *_ = clean_df
    assert "incident_id" in df.columns


# ---------------------------------------------------------------------------
# Value-range checks for categorical features
# ---------------------------------------------------------------------------


def test_lod_numeric_values(clean_df):
    df, *_ = clean_df
    vals = set(df["lod_numeric"].unique())
    assert vals <= {1, 2, 3, 4}, f"Unexpected lod_numeric values: {vals - {1,2,3,4}}"


def test_barrier_condition_values(clean_df):
    df, *_ = clean_df
    valid = {"effective", "degraded", "ineffective", "status_unknown"}
    vals = set(df["barrier_condition"].unique())
    assert vals <= valid, f"Unexpected barrier_condition values: {vals - valid}"


def test_barrier_level_values(clean_df):
    df, *_ = clean_df
    valid = {"prevention", "mitigation"}
    vals = set(df["barrier_level"].unique())
    assert vals <= valid, f"Unexpected barrier_level values: {vals - valid}"


# ---------------------------------------------------------------------------
# Parquet round-trip
# ---------------------------------------------------------------------------


def test_parquet_roundtrip(clean_df):
    """Read the written parquet and check it matches the in-memory df."""
    import pandas as pd

    df, parquet_path, _ = clean_df
    df2 = pd.read_parquet(parquet_path)
    assert len(df2) == len(df)
    assert set(df2.columns) == set(df.columns)


# ---------------------------------------------------------------------------
# Profile markdown written and non-empty
# ---------------------------------------------------------------------------


def test_profile_markdown_exists_and_nonempty(clean_df):
    _, _, profile_path = clean_df
    assert profile_path.exists(), "Profile markdown was not written"
    content = profile_path.read_text(encoding="utf-8")
    assert len(content) > 200, "Profile markdown looks too short"
    assert "530" in content, "Profile should mention the observed 530 row count"
    assert "529" in content, "Profile should reference the original roadmap 529 label"
