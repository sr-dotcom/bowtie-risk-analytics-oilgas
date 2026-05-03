"""Build cascading_training.parquet from Patrick's base_v3 CSV.

Applies two documented row drops (lod_industry_standard == 'Other' OR
lod_numeric == 99) and enforces the column contract: only encoded
features + y_fail + y_hf_fail + incident_id are written to the output.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Union

import pandas as pd

# ---------------------------------------------------------------------------
# Column contract
# ---------------------------------------------------------------------------

# Identifier / label columns retained in the output parquet.
_ID_COLS: list[str] = ["incident_id"]
_LABEL_COLS: list[str] = ["y_fail", "y_hf_fail"]

# Encoded feature columns retained in the output parquet.  Derived from
# Patrick's BARRIER_FEATURES_TARGET, BARRIER_FEATURES_COND, and
# CONTEXT_FEATURES in the reference notebook
# (docs/evidence/reference/xgb-combined-dual-inference-workflow.ipynb).
ENCODED_FEATURES: list[str] = [
    # Barrier position / taxonomy
    "barrier_level",
    "lod_industry_standard",
    "lod_numeric",
    "barrier_condition",
    "pathway_sequence",
    # Threat-count features (num_threats_*)
    "num_threats_in_lod_numeric",
    "num_threats_in_sequence",
    # Incident-level context features (total_*)
    "total_prev_barriers_incident",
    "total_mit_barriers_incident",
    # Flag features (flag_*)
    "flag_environmental_threat",
    "flag_electrical_failure",
    "flag_procedural_error",
    "flag_mechanical_failure",
    "flag_communication_breakdown",
]

OUTPUT_COLS: list[str] = _ID_COLS + _LABEL_COLS + ENCODED_FEATURES

# Columns present in base_v3 that are explicitly dropped at this boundary.
# Serves as the reference list for the "unexpected survivor" fast-fail guard.
_KNOWN_DROP_COLS: frozenset[str] = frozenset(
    [
        "control_id",
        "barrier_type_ps",
        "barrier_role_norm",
        "source_agency",
        "provider_bucket",
        "supporting_text_count",
        "total_failed_incident",
        "total_hf_failed_incident",
        "is_degradation_control",
        "hf_contrib_binary",
        "barrier_failed_expert",
        "barrier_failed_human_expert",
        "barrier_failed_rule",
        "failed_mismatch",
        "barrier_status",
        "barrier_type",
        "line_of_defense",
        "barrier_family",
        "incident_has_threat_data",
    ]
)

# Defaults (override via function parameters or __main__)
_DEFAULT_CSV = Path("data/models/cascading_input/barrier_model_dataset_base_v3.csv")
_DEFAULT_PARQUET = Path("data/processed/cascading_training.parquet")
_DEFAULT_PROFILE = Path("data/models/evaluation/cascading_training_profile.md")


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def prepare_cascading_dataset(
    csv_path: Union[str, Path] = _DEFAULT_CSV,
    parquet_path: Union[str, Path] = _DEFAULT_PARQUET,
    profile_path: Union[str, Path] = _DEFAULT_PROFILE,
) -> pd.DataFrame:
    """Load base_v3 CSV, apply documented drops, enforce column contract.

    Returns the cleaned DataFrame (also written to *parquet_path*).

    Raises
    ------
    FileNotFoundError
        If *csv_path* does not exist.
    ValueError
        If unexpected columns are found in the source CSV or any required
        column is missing after drops.
    """
    csv_path = Path(csv_path)
    parquet_path = Path(parquet_path)
    profile_path = Path(profile_path)

    if not csv_path.exists():
        raise FileNotFoundError(f"Source CSV not found: {csv_path}")

    df_raw = pd.read_csv(csv_path)
    n_raw = len(df_raw)

    # ------------------------------------------------------------------
    # Fast-fail guard: unexpected columns
    # ------------------------------------------------------------------
    known_cols = frozenset(OUTPUT_COLS) | _KNOWN_DROP_COLS
    unexpected = sorted(set(df_raw.columns) - known_cols)
    if unexpected:
        raise ValueError(
            f"Unexpected columns in source CSV (not in keep or drop list): "
            f"{unexpected}. Update OUTPUT_COLS or _KNOWN_DROP_COLS in data_prep.py."
        )

    # Also verify required output columns are present in the source
    missing_required = sorted(set(OUTPUT_COLS) - set(df_raw.columns))
    if missing_required:
        raise ValueError(
            f"Required columns missing from source CSV: {missing_required}"
        )

    # ------------------------------------------------------------------
    # Row drops
    # ------------------------------------------------------------------
    mask_other = df_raw["lod_industry_standard"] == "Other"
    mask_99 = df_raw["lod_numeric"] == 99
    mask_both = mask_other & mask_99
    mask_drop = mask_other | mask_99

    n_other = int(mask_other.sum())
    n_99 = int(mask_99.sum())
    n_overlap = int(mask_both.sum())
    n_drop = int(mask_drop.sum())

    df = df_raw[~mask_drop].copy().reset_index(drop=True)
    n_clean = len(df)

    # ------------------------------------------------------------------
    # Column contract enforcement
    # ------------------------------------------------------------------
    # Drop _mentioned PIF columns (safety net — none expected in base_v3,
    # but guard against upstream CSV changes).
    pif_cols = [c for c in df.columns if c.endswith("_mentioned")]
    if pif_cols:
        df = df.drop(columns=pif_cols)

    # Drop source_agency if still present (explicit boundary rule).
    if "source_agency" in df.columns:
        df = df.drop(columns=["source_agency"])

    # Select exactly the output columns.
    df = df[OUTPUT_COLS].copy()

    # Final contract assertion (belt-and-suspenders).
    extra_cols = sorted(set(df.columns) - set(OUTPUT_COLS))
    if extra_cols:
        raise ValueError(
            f"Column contract violation — unexpected columns in output: {extra_cols}"
        )

    # ------------------------------------------------------------------
    # Emit
    # ------------------------------------------------------------------
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(parquet_path, engine="pyarrow", index=False)

    profile_path.parent.mkdir(parents=True, exist_ok=True)
    _write_profile(
        profile_path,
        df=df,
        n_raw=n_raw,
        n_other=n_other,
        n_99=n_99,
        n_overlap=n_overlap,
        n_drop=n_drop,
        n_clean=n_clean,
    )

    print(f"cascading_training.parquet: {n_clean} rows × {len(df.columns)} cols")
    print(f"  incident_id uniques : {df['incident_id'].nunique()}")
    print(f"  y_fail rate         : {df['y_fail'].mean():.4f}")
    print(f"  y_hf_fail rate      : {df['y_hf_fail'].mean():.4f}")
    print(f"  Profile → {profile_path}")

    return df


# ---------------------------------------------------------------------------
# Profile writer
# ---------------------------------------------------------------------------


def _write_profile(
    path: Path,
    *,
    df: pd.DataFrame,
    n_raw: int,
    n_other: int,
    n_99: int,
    n_overlap: int,
    n_drop: int,
    n_clean: int,
) -> None:
    """Write the Markdown data-profile to *path*."""

    lod_cats = sorted(df["lod_industry_standard"].unique())
    lod_numeric_vals = sorted(df["lod_numeric"].unique())
    barrier_conds = sorted(df["barrier_condition"].unique())
    barrier_levels = sorted(df["barrier_level"].unique())

    # Null counts
    null_lines = ""
    for col in df.columns:
        n_null = int(df[col].isna().sum())
        null_lines += f"| `{col}` | {n_null} |\n"

    lines = [
        "# cascading_training.parquet — Data Profile",
        "",
        "> Generated by `src/modeling/cascading/data_prep.py`  ",
        "> Source: `data/models/cascading_input/barrier_model_dataset_base_v3.csv`",
        "",
        "## Drop Audit",
        "",
        "| Filter condition | Rows matching |",
        "|---|---|",
        f"| Raw source rows | {n_raw} |",
        f"| `lod_industry_standard == 'Other'` | {n_other} |",
        f"| `lod_numeric == 99` | {n_99} |",
        f"| Overlap (both conditions) | {n_overlap} |",
        f"| Union dropped (\\|Other\\| + \\|99\\| − overlap) | {n_drop} |",
        f"| **Rows after drop** | **{n_clean}** |",
        "",
        "### 530-vs-529 Note",
        "",
        "The original roadmap label for this step was '529 rows'. The actual",
        "observed survivor count is **530**. The discrepancy arises because the",
        "two drop conditions overlap on exactly one row: a barrier record where",
        "`lod_industry_standard == 'Other'` AND `lod_numeric == 99` simultaneously.",
        f"The union of both drop masks therefore removes {n_drop} rows "
        f"(not {n_other} + {n_99} = {n_other + n_99}),"
        f" yielding {n_clean} survivors instead of the expected 529.",
        "",
        "## Shape & Label Rates",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Rows | {n_clean} |",
        f"| Columns | {len(df.columns)} |",
        f"| Unique `incident_id` | {df['incident_id'].nunique()} |",
        f"| `y_fail` mean | {df['y_fail'].mean():.4f} |",
        f"| `y_hf_fail` mean | {df['y_hf_fail'].mean():.4f} |",
        "",
        "## Column Contract",
        "",
        "The parquet contains **only** the columns listed below (encoded",
        "features + labels + `incident_id`). `source_agency`, PIF `_mentioned`",
        "booleans, and all other provenance / raw-label columns are dropped at",
        "this boundary (D011, R032, rules 31–33).",
        "",
        "**Dropped columns (not present in parquet):** `control_id`, `source_agency`,",
        "`barrier_type_ps`, `barrier_role_norm`, `provider_bucket`,",
        "`supporting_text_count`, `total_failed_incident`, `total_hf_failed_incident`,",
        "`is_degradation_control`, `hf_contrib_binary`, `barrier_failed_expert`,",
        "`barrier_failed_human_expert`, `barrier_failed_rule`, `failed_mismatch`,",
        "`barrier_status`, `barrier_type`, `line_of_defense`, `barrier_family`,",
        "`incident_has_threat_data`",
        "",
        "## Null Counts",
        "",
        "| Column | Null count |",
        "|---|---|",
        null_lines.rstrip(),
        "",
        "## Feature Cardinalities",
        "",
        f"**`lod_industry_standard`** ({len(lod_cats)} categories, 'Other' excluded):",
        "",
    ]

    for cat in lod_cats:
        lines.append(f"- `{cat}`")

    lines += [
        "",
        f"**`lod_numeric`** — values present: {lod_numeric_vals}",
        "",
        f"**`barrier_condition`** — values present: {barrier_conds}",
        "",
        f"**`barrier_level`** — values present: {barrier_levels}",
        "",
        "## Numeric Feature Summary",
        "",
    ]

    num_cols = [
        "pathway_sequence",
        "num_threats_in_lod_numeric",
        "num_threats_in_sequence",
        "total_prev_barriers_incident",
        "total_mit_barriers_incident",
    ]
    flag_cols = [c for c in df.columns if c.startswith("flag_")]

    lines += [
        "| Column | min | max | mean |",
        "|---|---|---|---|",
    ]
    for col in num_cols:
        if col in df.columns:
            lines.append(
                f"| `{col}` | {df[col].min()} | {df[col].max()} | {df[col].mean():.3f} |"
            )

    lines += [
        "",
        "**Flag columns (fraction == 1):**",
        "",
        "| Column | fraction True |",
        "|---|---|",
    ]
    for col in flag_cols:
        if col in df.columns:
            lines.append(f"| `{col}` | {df[col].mean():.3f} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# __main__ entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build cascading_training.parquet from Patrick's base_v3 CSV"
    )
    parser.add_argument(
        "--csv",
        default=str(_DEFAULT_CSV),
        help="Path to barrier_model_dataset_base_v3.csv",
    )
    parser.add_argument(
        "--out",
        default=str(_DEFAULT_PARQUET),
        help="Output parquet path",
    )
    parser.add_argument(
        "--profile",
        default=str(_DEFAULT_PROFILE),
        help="Output profile markdown path",
    )
    args = parser.parse_args()

    prepare_cascading_dataset(
        csv_path=args.csv,
        parquet_path=args.out,
        profile_path=args.profile,
    )
    sys.exit(0)
