"""Feature engineering for barrier risk analytics.

Joins controls_combined.csv and flat_incidents_combined.csv, derives both
binary label columns from barrier_status, assigns barrier_family via the
existing taxonomy, OrdinalEncodes 5 categorical features, and writes the
feature matrix parquet + feature_names.json + encoder.joblib artifacts.

Usage::

    python -m src.modeling.feature_engineering   # writes to default artifact paths
    # exit 0 on success, 1 on FileNotFoundError
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import OrdinalEncoder

from src.rag.corpus_builder import assign_barrier_family

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants (importable by tests and Phase 3 training code)
# ---------------------------------------------------------------------------

CONTROLS_CSV = Path("data/processed/controls_combined.csv")
INCIDENTS_CSV = Path("data/processed/flat_incidents_combined.csv")
ARTIFACTS_DIR = Path("data/models/artifacts")
FEATURE_MATRIX_PATH = ARTIFACTS_DIR / "feature_matrix.parquet"
FEATURE_NAMES_PATH = ARTIFACTS_DIR / "feature_names.json"
ENCODER_PATH = ARTIFACTS_DIR / "encoder.joblib"

# Five categorical features to OrdinalEncode (per D-01, D-02, D-03).
CATEGORICAL_FEATURES: list[str] = [
    "side",
    "barrier_type",
    "line_of_defense",
    "barrier_family",
    "source_agency",
]

# Twelve PIF features (short names for feature matrix columns).
PIF_FEATURES: list[str] = [
    "pif_competence",
    "pif_fatigue",
    "pif_communication",
    "pif_situational_awareness",
    "pif_procedures",
    "pif_workload",
    "pif_time_pressure",
    "pif_tools_equipment",
    "pif_safety_culture",
    "pif_management_of_change",
    "pif_supervision",
    "pif_training",
]

# Mapping from long incident CSV PIF column names to short feature names.
_PIF_COL_MAP: dict[str, str] = {
    "incident__pifs__people__competence_mentioned": "pif_competence",
    "incident__pifs__people__fatigue_mentioned": "pif_fatigue",
    "incident__pifs__people__communication_mentioned": "pif_communication",
    "incident__pifs__people__situational_awareness_mentioned": "pif_situational_awareness",
    "incident__pifs__work__procedures_mentioned": "pif_procedures",
    "incident__pifs__work__workload_mentioned": "pif_workload",
    "incident__pifs__work__time_pressure_mentioned": "pif_time_pressure",
    "incident__pifs__work__tools_equipment_mentioned": "pif_tools_equipment",
    "incident__pifs__organisation__safety_culture_mentioned": "pif_safety_culture",
    "incident__pifs__organisation__management_of_change_mentioned": "pif_management_of_change",
    "incident__pifs__organisation__supervision_mentioned": "pif_supervision",
    "incident__pifs__organisation__training_mentioned": "pif_training",
}

# Numeric features (present in controls CSV).
NUMERIC_FEATURES: list[str] = ["supporting_text_count"]

# Non-PIF features (categorical + numeric) — 6 features for ablation baseline (D-11).
NON_PIF_FEATURES: list[str] = CATEGORICAL_FEATURES + NUMERIC_FEATURES

# Metadata columns: present in output DataFrame but NOT in feature_names.json.
METADATA_COLUMNS: list[str] = ["incident_id", "control_id"]

# Label columns: present in output DataFrame but NOT in feature_names.json.
LABEL_COLUMNS: list[str] = ["label_barrier_failed", "label_barrier_failed_human"]

# barrier_status values that indicate the barrier did not perform.
_DID_NOT_PERFORM_STATUSES: list[str] = [
    "failed",
    "degraded",
    "not_installed",
    "bypassed",
]


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def build_feature_matrix(
    controls_path: Path = CONTROLS_CSV,
    incidents_path: Path = INCIDENTS_CSV,
    artifacts_dir: Path = ARTIFACTS_DIR,
) -> pd.DataFrame:
    """Build the feature matrix from controls and incidents CSVs.

    Joins controls with incident-level PIF columns, derives both binary label
    columns from barrier_status (NOT from the barrier_failed CSV column),
    assigns barrier_family via the normalization taxonomy, OrdinalEncodes 5
    categorical features, and writes three artifacts:
    - feature_matrix.parquet: training-ready feature matrix
    - feature_names.json: locked column ordering contract for training/inference
    - encoder.joblib: fitted OrdinalEncoder for inference reuse

    Args:
        controls_path: Path to controls_combined.csv.
        incidents_path: Path to flat_incidents_combined.csv.
        artifacts_dir: Directory for output artifacts.

    Returns:
        DataFrame with METADATA_COLUMNS + feature_names + LABEL_COLUMNS.

    Raises:
        FileNotFoundError: If either CSV does not exist.
    """
    controls_path = Path(controls_path)
    incidents_path = Path(incidents_path)
    artifacts_dir = Path(artifacts_dir)

    # ------------------------------------------------------------------
    # Step 1: Load CSVs
    # ------------------------------------------------------------------
    if not controls_path.exists():
        raise FileNotFoundError(
            f"Controls CSV not found: {controls_path}. "
            "Run: python -m src.pipeline build-combined-exports"
        )
    if not incidents_path.exists():
        raise FileNotFoundError(
            f"Incidents CSV not found: {incidents_path}. "
            "Run: python -m src.pipeline build-combined-exports"
        )

    controls = pd.read_csv(controls_path)
    incidents = pd.read_csv(incidents_path)
    logger.info("Loaded %d controls, %d incidents", len(controls), len(incidents))

    # ------------------------------------------------------------------
    # Step 2: Exclude unknowns (per D-06)
    # ------------------------------------------------------------------
    n_total = len(controls)
    mask_known = controls["barrier_status"] != "unknown"
    df = controls[mask_known].copy()
    n_excluded = n_total - len(df)
    logger.info(
        "Excluded %d rows with barrier_status='unknown' (%d remaining)",
        n_excluded,
        len(df),
    )

    # ------------------------------------------------------------------
    # Step 3: Derive labels (per D-05)
    # CRITICAL: derive from barrier_status, NOT from barrier_failed column
    # ------------------------------------------------------------------
    _did_not_perform = df["barrier_status"].isin(_DID_NOT_PERFORM_STATUSES)
    df["label_barrier_failed"] = _did_not_perform.astype(int)

    # Coerce barrier_failed_human to bool safely (can be string "True"/"False").
    _hf_raw = df["barrier_failed_human"]
    if _hf_raw.dtype == object:
        _hf_bool = _hf_raw.map(lambda v: str(v).strip().lower() == "true")
    else:
        _hf_bool = _hf_raw.astype(bool)

    df["label_barrier_failed_human"] = (_did_not_perform & _hf_bool).astype(int)

    # ------------------------------------------------------------------
    # Step 4: Assign barrier_family
    # ------------------------------------------------------------------
    def _safe_assign_family(row: "pd.Series") -> str:
        name = str(row["name"]) if pd.notna(row["name"]) else ""
        barrier_role = str(row["barrier_role"]) if pd.notna(row.get("barrier_role")) else ""
        side = str(row["side"]) if pd.notna(row["side"]) else ""
        barrier_type = str(row["barrier_type"]) if pd.notna(row["barrier_type"]) else ""
        return assign_barrier_family(name, barrier_role, side, barrier_type)

    logger.info("Assigning barrier_family for %d rows...", len(df))
    df["barrier_family"] = df.apply(_safe_assign_family, axis=1)

    # ------------------------------------------------------------------
    # Step 5: Join with incidents (left-join to attach PIF columns)
    # ------------------------------------------------------------------
    pif_long_cols = list(_PIF_COL_MAP.keys())
    pif_cols_present = [c for c in pif_long_cols if c in incidents.columns]

    incidents_pif = incidents[["incident_id"] + pif_cols_present].copy()
    df = df.merge(incidents_pif, on="incident_id", how="left")

    # Rename long PIF column names to short names.
    rename_map = {long: short for long, short in _PIF_COL_MAP.items() if long in df.columns}
    df = df.rename(columns=rename_map)

    # Ensure all PIF features exist (fill missing short-name columns with 0).
    for pif_col in PIF_FEATURES:
        if pif_col not in df.columns:
            df[pif_col] = 0

    # ------------------------------------------------------------------
    # Step 6: Coerce PIF booleans to 0/1 integers
    # ------------------------------------------------------------------
    for pif_col in PIF_FEATURES:
        df[pif_col] = (
            df[pif_col].infer_objects(copy=False).fillna(False).astype(int)
        )

    # ------------------------------------------------------------------
    # Step 7: Fill NaN in supporting_text_count
    # ------------------------------------------------------------------
    df["supporting_text_count"] = (
        df["supporting_text_count"].fillna(0).astype(int)
    )

    # ------------------------------------------------------------------
    # Step 8: Encode categoricals (per D-01, D-02, D-03)
    # ------------------------------------------------------------------
    # Fill NaN in categorical columns with "unknown" before encoding.
    for cat_col in CATEGORICAL_FEATURES:
        if cat_col in df.columns:
            df[cat_col] = df[cat_col].fillna("unknown").astype(str)
        else:
            df[cat_col] = "unknown"

    encoder = OrdinalEncoder(
        handle_unknown="use_encoded_value",
        unknown_value=-1,
        dtype=int,
    )
    df[CATEGORICAL_FEATURES] = encoder.fit_transform(df[CATEGORICAL_FEATURES])

    # ------------------------------------------------------------------
    # Step 9: Build feature_names list (locked contract — list-of-dicts format per D-07, D-08)
    # ------------------------------------------------------------------
    feature_names_flat: list[str] = CATEGORICAL_FEATURES + PIF_FEATURES + NUMERIC_FEATURES
    feature_names_dicts: list[dict[str, str]] = []
    for name in feature_names_flat:
        if name in PIF_FEATURES:
            feature_names_dicts.append({"name": name, "category": "incident_context"})
        else:
            feature_names_dicts.append({"name": name, "category": "barrier"})

    # ------------------------------------------------------------------
    # Step 10: Save artifacts
    # ------------------------------------------------------------------
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    feature_names_path = artifacts_dir / "feature_names.json"
    encoder_path = artifacts_dir / "encoder.joblib"
    parquet_path = artifacts_dir / "feature_matrix.parquet"

    with open(feature_names_path, "w", encoding="utf-8") as f:
        json.dump(feature_names_dicts, f, indent=2)
    logger.info("feature_names.json written to %s", feature_names_path)

    joblib.dump(encoder, encoder_path)
    logger.info("encoder.joblib written to %s", encoder_path)

    output_df = df[METADATA_COLUMNS + feature_names_flat + LABEL_COLUMNS].copy()
    output_df.to_parquet(parquet_path, index=False)
    logger.info("feature_matrix.parquet written to %s", parquet_path)

    # ------------------------------------------------------------------
    # Step 11: Log summary
    # ------------------------------------------------------------------
    n_rows = len(output_df)
    n_label1_pos = int(output_df["label_barrier_failed"].sum())
    n_label2_pos = int(output_df["label_barrier_failed_human"].sum())
    logger.info(
        "Feature matrix: %d rows, %d features",
        n_rows,
        len(feature_names_flat),
    )
    logger.info(
        "  label_barrier_failed: %d positive (%.1f%%)",
        n_label1_pos,
        100.0 * n_label1_pos / n_rows if n_rows > 0 else 0.0,
    )
    logger.info(
        "  label_barrier_failed_human: %d positive (%.1f%%)",
        n_label2_pos,
        100.0 * n_label2_pos / n_rows if n_rows > 0 else 0.0,
    )

    return output_df


# ---------------------------------------------------------------------------
# GroupKFold utility
# ---------------------------------------------------------------------------

def get_group_kfold_splits(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    n_splits: int = 5,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Return GroupKFold train/test index splits.

    Ensures no group (incident_id) appears in both train and test
    for any fold. Per D-08, D-09 from Phase 2 context.

    Args:
        X: Feature matrix of shape (n_samples, n_features).
        y: Label array of shape (n_samples,).
        groups: Group identifiers (incident_id) of shape (n_samples,).
        n_splits: Number of folds (default 5).

    Returns:
        List of (train_indices, test_indices) tuples, one per fold.
    """
    gkf = GroupKFold(n_splits=n_splits)
    return [(train_idx, test_idx) for train_idx, test_idx in gkf.split(X, y, groups)]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        df = build_feature_matrix()
        print(f"Feature matrix: {len(df)} rows, {len(df.columns)} columns")
        print(f"  label_barrier_failed: {df['label_barrier_failed'].sum()} positive")
        print(f"  label_barrier_failed_human: {df['label_barrier_failed_human'].sum()} positive")
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
