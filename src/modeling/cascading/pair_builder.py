"""Build pair dataset for cascading XGBoost training.

Ported from Patrick's build_pair_dataset (cell 7 of
docs/references/xgb_combined_dual_inference_workflow.ipynb).

Adaptation: the S01 parquet omits control_id, so a synthetic in-incident
row ordinal (df.groupby("incident_id").cumcount()) is inserted before the
copy/rename/merge step and used as the self-pair exclusion key instead of
``control_id != control_id_cond``.
"""

from __future__ import annotations

import xgboost as xgb
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

# ── Feature contracts (must match cell 6 of the reference notebook) ──────────

BARRIER_FEATURES_TARGET: list[str] = [
    "barrier_level",
    "lod_industry_standard",
    "pathway_sequence",
    "lod_numeric",
    "num_threats_in_lod_numeric",
]

BARRIER_FEATURES_COND: list[str] = [
    "barrier_level",
    "lod_industry_standard",
    "barrier_condition",
    "pathway_sequence",
    "lod_numeric",
    "num_threats_in_lod_numeric",
]

CONTEXT_FEATURES: list[str] = [
    "total_prev_barriers_incident",
    "total_mit_barriers_incident",
    "num_threats_in_sequence",
    "flag_environmental_threat",
    "flag_electrical_failure",
    "flag_procedural_error",
    "flag_mechanical_failure",
]

LABEL_COLS: list[str] = ["y_fail", "y_hf_fail"]

ALL_RAW_FEATURES: list[str] = sorted(set(BARRIER_FEATURES_TARGET + BARRIER_FEATURES_COND))

# flag_communication_breakdown is in the parquet but NOT in any feature list —
# it is dropped implicitly by projecting to KEEP_COLS.
KEEP_COLS: list[str] = (
    ["incident_id"] + ALL_RAW_FEATURES + CONTEXT_FEATURES + LABEL_COLS
)


def build_pair_dataset(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str], list[str], list[str]]:
    """Rebuild the pair dataset from a single-barrier DataFrame.

    Parameters
    ----------
    df:
        Raw barrier rows (e.g. from cascading_training.parquet).  Only
        columns listed in KEEP_COLS are used; extras are silently ignored.

    Returns
    -------
    df_pairs : pd.DataFrame
        Cross-joined barrier pairs within each incident with y_fail_cond==1
        filter applied and self-pairs excluded.
    cat_all : list[str]
        Categorical feature names fed to OrdinalEncoder (5 features).
    num_all : list[str]
        Numerical feature names passed through unchanged (13 features).
    all_features : list[str]
        cat_all + num_all, 18 features total — the model input contract.
    """
    df_clean = (
        df[KEEP_COLS]
        .dropna(subset=ALL_RAW_FEATURES + CONTEXT_FEATURES + LABEL_COLS)
        .copy()
        .reset_index(drop=True)
    )

    # Synthetic row ordinal per incident — replaces control_id self-exclusion.
    df_clean["row_ord"] = df_clean.groupby("incident_id").cumcount()

    tgt = df_clean.copy()
    cond = df_clean.copy()

    # Target side: rename barrier target features and labels to _target suffix.
    tgt = tgt.rename(
        columns={c: f"{c}_target" for c in BARRIER_FEATURES_TARGET + LABEL_COLS}
    )

    # Conditioning side: rename barrier cond features and labels to _cond suffix.
    cond = cond.rename(columns={c: f"{c}_cond" for c in BARRIER_FEATURES_COND})
    cond = cond.rename(columns={"y_fail": "y_fail_cond", "y_hf_fail": "y_hf_fail_cond"})
    cond = cond.rename(columns={"row_ord": "row_ord_cond"})

    # Inner join on incident_id; context features come only from the target side.
    df_pairs = tgt.merge(
        cond.drop(columns=CONTEXT_FEATURES),
        on="incident_id",
        how="inner",
    )

    # Exclude self-pairs using the row ordinal (row_ord from tgt side).
    df_pairs = df_pairs[df_pairs["row_ord"] != df_pairs["row_ord_cond"]].copy()

    # Keep only pairs where the conditioning barrier actually failed.
    df_pairs = df_pairs[df_pairs["y_fail_cond"] == 1].reset_index(drop=True)

    # ── Named feature groups (2 + 3 + 3 + 3 + 7 = 18) ────────────────────────
    cat_target: list[str] = [
        "lod_industry_standard_target",
        "barrier_level_target",
    ]
    num_target: list[str] = [
        "pathway_sequence_target",
        "lod_numeric_target",
        "num_threats_in_lod_numeric_target",
    ]
    cat_cond: list[str] = [
        "lod_industry_standard_cond",
        "barrier_level_cond",
        "barrier_condition_cond",
    ]
    num_cond: list[str] = [
        "pathway_sequence_cond",
        "lod_numeric_cond",
        "num_threats_in_lod_numeric_cond",
    ]
    cat_context: list[str] = []
    num_context: list[str] = CONTEXT_FEATURES.copy()

    cat_all = cat_target + cat_cond + cat_context
    num_all = num_target + num_cond + num_context
    all_features = cat_all + num_all

    return df_pairs, cat_all, num_all, all_features


def make_xgb_pipeline(
    cat_all: list[str],
    num_all: list[str],
    scale_pos_weight: float = 1.0,
) -> Pipeline:
    """Build sklearn Pipeline with OrdinalEncoder + XGBClassifier.

    Hyperparameters match Patrick's cell 9 exactly:
    n_estimators=400, max_depth=4, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
    eval_metric="logloss", random_state=42, n_jobs=-1.
    """
    prep = ColumnTransformer(
        [
            (
                "cat_ord",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value",
                    unknown_value=-1,
                ),
                cat_all,
            ),
            ("num_pass", "passthrough", num_all),
        ]
    )

    clf = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )

    return Pipeline([("prep", prep), ("clf", clf)])
