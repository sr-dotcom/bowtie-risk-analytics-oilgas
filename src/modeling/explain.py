"""SHAP explainer infrastructure for barrier risk analytics.

Builds SHAP background arrays for both XGBoost models and runs the PIF
ablation study (comparing full 18-feature vs non-PIF 6-feature performance).

TreeExplainer objects are NEVER serialized directly (they contain C++ weak
references that break on deserialization). Instead this module saves:
  - xgb_model{N}.json (trained model)
  - shap_background_model{N}.npy (background sample array)

BarrierPredictor in predict.py recreates the TreeExplainer at load time from
the model + background array.

Usage::

    python -m src.modeling.explain   # builds backgrounds + runs ablation
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from sklearn.metrics import f1_score, matthews_corrcoef

from src.modeling.feature_engineering import (
    ARTIFACTS_DIR,
    FEATURE_MATRIX_PATH,
    FEATURE_NAMES_PATH,
    CATEGORICAL_FEATURES,
    PIF_FEATURES,
    NUMERIC_FEATURES,
    NON_PIF_FEATURES,
    get_group_kfold_splits,
)
from src.modeling.train import EVALUATION_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Default background sample size (per plan: 200, Claude's discretion)
_DEFAULT_BG_SIZE: int = 200


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_shap_backgrounds(
    feature_matrix_path: Path = FEATURE_MATRIX_PATH,
    artifacts_dir: Path = ARTIFACTS_DIR,
    bg_size: int = _DEFAULT_BG_SIZE,
    random_state: int = 42,
) -> None:
    """Build and save SHAP background arrays for both XGBoost models.

    Samples ``min(bg_size, n_rows)`` rows from the feature matrix and saves
    them as ``.npy`` files. Also recreates the TreeExplainer to verify the
    background + model pair produces correct SHAP value shapes.

    TreeExplainer objects are NEVER serialized — this function only saves
    the background arrays. BarrierPredictor recreates the explainer at init.

    Args:
        feature_matrix_path: Path to feature_matrix.parquet.
        artifacts_dir: Directory containing XGBoost model JSON files and
            where background .npy files will be written.
        bg_size: Maximum number of background samples. Defaults to 200.
        random_state: Random seed for reproducible sampling.

    Raises:
        FileNotFoundError: If feature_matrix.parquet does not exist.
    """
    feature_matrix_path = Path(feature_matrix_path)
    artifacts_dir = Path(artifacts_dir)

    if not feature_matrix_path.exists():
        raise FileNotFoundError(
            f"Feature matrix not found: {feature_matrix_path}. "
            "Run: python -m src.modeling.feature_engineering"
        )

    # Load feature matrix and determine column order from feature_names.json
    df = pd.read_parquet(feature_matrix_path)
    feature_names_path = artifacts_dir / "feature_names.json"
    if feature_names_path.exists():
        with open(feature_names_path) as f:
            feature_names_raw = json.load(f)
        # Handle both flat list (legacy) and list-of-dicts (Phase 3+)
        if feature_names_raw and isinstance(feature_names_raw[0], dict):
            feature_cols: list[str] = [entry["name"] for entry in feature_names_raw]
        else:
            feature_cols = list(feature_names_raw)
    else:
        feature_cols = CATEGORICAL_FEATURES + PIF_FEATURES + NUMERIC_FEATURES
        logger.warning(
            "feature_names.json not found at %s; using module constant order",
            feature_names_path,
        )

    X: np.ndarray = df[feature_cols].to_numpy(dtype=float)
    n_rows, n_features = X.shape
    actual_bg = min(bg_size, n_rows)
    logger.info(
        "Feature matrix: %d rows, %d features. Sampling %d background rows.",
        n_rows, n_features, actual_bg,
    )

    rng = np.random.default_rng(random_state)

    for suffix in ("model1", "model2"):
        # Sample background rows
        bg_idx = rng.choice(n_rows, size=actual_bg, replace=False)
        background = X[bg_idx]

        # Save background array as .npy
        bg_path = artifacts_dir / f"shap_background_{suffix}.npy"
        np.save(str(bg_path), background)
        logger.info("Background array saved: %s (shape %s)", bg_path, background.shape)

        # Load corresponding XGBoost model and verify explainer
        model_path = artifacts_dir / f"xgb_{suffix}.json"
        if not model_path.exists():
            logger.warning("XGBoost model not found at %s — skipping verification", model_path)
            continue

        xgb_model = xgb.XGBClassifier()
        xgb_model.load_model(str(model_path))

        # Recreate TreeExplainer — do NOT serialize this object (Pitfall 3 from RESEARCH.md)
        explainer = shap.TreeExplainer(xgb_model, data=background)
        ev = explainer.expected_value
        logger.info(
            "  %s TreeExplainer: expected_value=%.4f, background shape=%s",
            suffix, float(ev), background.shape,
        )

        # Verify SHAP values on 1 sample have correct shape
        sample = X[:1]
        shap_vals = explainer.shap_values(sample)
        assert shap_vals.shape == (1, n_features), (
            f"SHAP values shape mismatch: expected (1, {n_features}), got {shap_vals.shape}"
        )
        logger.info(
            "  %s verification: shap_values(1 sample) shape=%s — OK",
            suffix, shap_vals.shape,
        )


def run_pif_ablation(
    feature_matrix_path: Path = FEATURE_MATRIX_PATH,
    artifacts_dir: Path = ARTIFACTS_DIR,
    evaluation_dir: Path = EVALUATION_DIR,
    n_estimators: int = 300,
    max_depth: int = 4,
    learning_rate: float = 0.05,
) -> dict:
    """Run PIF ablation study: compare full 18-feature vs non-PIF 6-feature performance.

    Trains XGBoost 4 times (2 targets x 2 feature sets) using 5-fold
    GroupKFold CV and records F1-minority and MCC for each.

    Per D-11: this study is advisory only — PIFs always stay in the feature
    set regardless of outcome. The results are saved to pif_ablation_report.json.

    Args:
        feature_matrix_path: Path to feature_matrix.parquet.
        artifacts_dir: Path to artifacts directory (contains feature_names.json).
        evaluation_dir: Directory where pif_ablation_report.json is written.
        n_estimators: XGBoost number of boosting rounds.
        max_depth: XGBoost max tree depth.
        learning_rate: XGBoost learning rate.

    Returns:
        Ablation report dict (same content as pif_ablation_report.json).

    Raises:
        FileNotFoundError: If feature_matrix.parquet does not exist.
    """
    feature_matrix_path = Path(feature_matrix_path)
    artifacts_dir = Path(artifacts_dir)
    evaluation_dir = Path(evaluation_dir)

    if not feature_matrix_path.exists():
        raise FileNotFoundError(
            f"Feature matrix not found: {feature_matrix_path}. "
            "Run: python -m src.modeling.feature_engineering"
        )

    # Load feature matrix
    df = pd.read_parquet(feature_matrix_path)
    logger.info("PIF ablation: loaded %d rows", len(df))

    # Load feature column order from feature_names.json
    feature_names_path = artifacts_dir / "feature_names.json"
    if feature_names_path.exists():
        with open(feature_names_path) as f:
            feature_names_raw = json.load(f)
        if feature_names_raw and isinstance(feature_names_raw[0], dict):
            all_feature_cols: list[str] = [entry["name"] for entry in feature_names_raw]
        else:
            all_feature_cols = list(feature_names_raw)
    else:
        all_feature_cols = CATEGORICAL_FEATURES + PIF_FEATURES + NUMERIC_FEATURES
        logger.warning("feature_names.json not found; using module constant order")

    # Determine non-PIF feature columns (6 features: 5 categoricals + supporting_text_count)
    non_pif_cols: list[str] = [c for c in all_feature_cols if c in NON_PIF_FEATURES]
    logger.info(
        "Feature sets — full: %d cols, non-PIF: %d cols",
        len(all_feature_cols), len(non_pif_cols),
    )

    # Group identifiers for GroupKFold (no incident_id leakage)
    groups = df["incident_id"].to_numpy()

    # Targets: model1 = barrier_failed, model2 = barrier_failed_human
    targets = {
        "model1_label_barrier_failed": "label_barrier_failed",
        "model2_label_barrier_failed_human": "label_barrier_failed_human",
    }

    feature_sets = {
        "full_features": all_feature_cols,
        "non_pif_features": non_pif_cols,
    }

    ablation_results: dict = {}

    for model_key, target_col in targets.items():
        logger.info("=" * 60)
        logger.info("Ablation for target: %s (%s)", model_key, target_col)
        logger.info("=" * 60)

        y: np.ndarray = df[target_col].to_numpy()
        n_positive = int(y.sum())
        n_negative = int((y == 0).sum())
        scale_pos_weight = n_negative / n_positive if n_positive > 0 else 1.0
        logger.info(
            "  %s: %d positive, %d negative, scale_pos_weight=%.4f",
            target_col, n_positive, n_negative, scale_pos_weight,
        )

        model_result: dict = {}

        for feat_set_name, feat_cols in feature_sets.items():
            X_feat: np.ndarray = df[feat_cols].to_numpy(dtype=float)
            splits = get_group_kfold_splits(X_feat, y, groups, n_splits=5)

            fold_f1s: list[float] = []
            fold_mccs: list[float] = []

            for fold_idx, (train_idx, test_idx) in enumerate(splits):
                X_train, X_test = X_feat[train_idx], X_feat[test_idx]
                y_train, y_test = y[train_idx], y[test_idx]

                # CRITICAL: eval_metric in constructor per XGBoost 3.0 API
                xgb_model = xgb.XGBClassifier(
                    n_estimators=n_estimators,
                    max_depth=max_depth,
                    learning_rate=learning_rate,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    scale_pos_weight=scale_pos_weight,
                    eval_metric="logloss",
                    tree_method="hist",
                    random_state=42,
                    n_jobs=-1,
                )
                xgb_model.fit(X_train, y_train)
                y_pred = xgb_model.predict(X_test)

                f1 = float(f1_score(y_test, y_pred, pos_label=1, zero_division=0))
                mcc = float(matthews_corrcoef(y_test, y_pred))
                fold_f1s.append(f1)
                fold_mccs.append(mcc)

                logger.info(
                    "  %s %s fold %d: F1=%.3f MCC=%.3f",
                    feat_set_name, model_key, fold_idx + 1, f1, mcc,
                )

            model_result[feat_set_name] = {
                "f1_minority_mean": float(np.mean(fold_f1s)),
                "f1_minority_std": float(np.std(fold_f1s)),
                "mcc_mean": float(np.mean(fold_mccs)),
                "mcc_std": float(np.std(fold_mccs)),
            }
            logger.info(
                "  %s %s: F1=%.3f±%.3f MCC=%.3f±%.3f",
                feat_set_name, model_key,
                model_result[feat_set_name]["f1_minority_mean"],
                model_result[feat_set_name]["f1_minority_std"],
                model_result[feat_set_name]["mcc_mean"],
                model_result[feat_set_name]["mcc_std"],
            )

        # Determine PIF impact (advisory only — per D-11 PIFs always stay)
        full_f1 = model_result["full_features"]["f1_minority_mean"]
        non_pif_f1 = model_result["non_pif_features"]["f1_minority_mean"]
        delta = full_f1 - non_pif_f1
        if delta > 0.01:
            pif_impact = "improved"
        elif delta < -0.01:
            pif_impact = "degraded"
        else:
            pif_impact = "neutral"

        model_result["pif_impact"] = pif_impact
        logger.info(
            "  %s: PIF impact=%s (full F1=%.3f vs non-PIF F1=%.3f, delta=%.3f)",
            model_key, pif_impact, full_f1, non_pif_f1, delta,
        )
        ablation_results[model_key] = model_result

    # Build final report
    report = {
        "description": "PIF ablation study: full features (18) vs non-PIF features (6)",
        "advisory_only": True,  # Per D-11: PIFs always stay regardless of outcome
        **ablation_results,
    }

    evaluation_dir.mkdir(parents=True, exist_ok=True)
    report_path = evaluation_dir / "pif_ablation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    logger.info("PIF ablation report written: %s", report_path)

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        print("=== Building SHAP Background Arrays ===")
        build_shap_backgrounds()
        print("  shap_background_model1.npy: OK")
        print("  shap_background_model2.npy: OK")

        print("\n=== Running PIF Ablation Study ===")
        report = run_pif_ablation()

        for model_key in ["model1_label_barrier_failed", "model2_label_barrier_failed_human"]:
            if model_key not in report:
                continue
            full = report[model_key]["full_features"]
            non_pif = report[model_key]["non_pif_features"]
            pif_impact = report[model_key]["pif_impact"]
            print(f"\n  {model_key}:")
            print(
                f"    full_features:    F1={full['f1_minority_mean']:.3f}±{full['f1_minority_std']:.3f}"
                f" MCC={full['mcc_mean']:.3f}±{full['mcc_std']:.3f}"
            )
            print(
                f"    non_pif_features: F1={non_pif['f1_minority_mean']:.3f}±{non_pif['f1_minority_std']:.3f}"
                f" MCC={non_pif['mcc_mean']:.3f}±{non_pif['mcc_std']:.3f}"
            )
            print(f"    pif_impact: {pif_impact} (advisory only — PIFs always stay)")

        print(f"\nPIF ablation report: {EVALUATION_DIR / 'pif_ablation_report.json'}")

    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
