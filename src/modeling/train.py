"""Model training pipeline for barrier risk analytics.

Trains LogReg and XGBoost classifiers for two prediction targets:
  - Model 1: label_barrier_failed (barrier did not perform)
  - Model 2: label_barrier_failed_human (barrier failed with human factor contribution)

Uses GroupKFold cross-validation on incident_id to prevent data leakage.
Evaluation metrics: F1-minority, MCC, Precision, Recall — never accuracy.

Artifacts saved to data/models/artifacts/:
  - logreg_model1.joblib, logreg_model2.joblib
  - xgb_model1.json, xgb_model2.json

Evaluation report saved to data/models/evaluation/training_report.json.

Usage::

    python -m src.modeling.train   # trains on default artifact paths
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
)
from xgboost import XGBClassifier

from src.modeling.feature_engineering import (
    ARTIFACTS_DIR,
    CATEGORICAL_FEATURES,
    FEATURE_MATRIX_PATH,
    NUMERIC_FEATURES,
    PIF_FEATURES,
    get_group_kfold_splits,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

EVALUATION_DIR = Path("data/models/evaluation")
TRAINING_REPORT_PATH = EVALUATION_DIR / "training_report.json"

# Ordered mapping: model key -> target column
_TARGETS: dict[str, str] = {
    "model1": "label_barrier_failed",
    "model2": "label_barrier_failed_human",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_fold_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, float]:
    """Compute per-fold evaluation metrics.

    Args:
        y_true: Ground-truth binary labels.
        y_pred: Predicted binary labels.

    Returns:
        Dict with f1_minority, mcc, precision, recall (all pos_label=1).
    """
    return {
        "f1_minority": float(f1_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "mcc": float(matthews_corrcoef(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, pos_label=1, zero_division=0)),
    }


def _aggregate_folds(folds: list[dict[str, float]]) -> tuple[dict[str, float], dict[str, float]]:
    """Compute mean and std of metrics across folds.

    Args:
        folds: List of per-fold metric dicts.

    Returns:
        Tuple of (mean_dict, std_dict).
    """
    if not folds:
        return {}, {}
    keys = list(folds[0].keys())
    mean_dict = {k: float(np.mean([f[k] for f in folds])) for k in keys}
    std_dict = {k: float(np.std([f[k] for f in folds])) for k in keys}
    return mean_dict, std_dict


# ---------------------------------------------------------------------------
# Main training function
# ---------------------------------------------------------------------------

def train_models(
    feature_matrix_path: Path = FEATURE_MATRIX_PATH,
    artifacts_dir: Path = ARTIFACTS_DIR,
    evaluation_dir: Path = EVALUATION_DIR,
    n_estimators: int = 300,
    max_depth: int = 4,
    learning_rate: float = 0.05,
    logreg_max_iter: int = 1000,
    logreg_C: float = 1.0,
) -> dict[str, Any]:
    """Train LogReg and XGBoost classifiers for both prediction targets.

    Performs 5-fold GroupKFold CV (no group leakage on incident_id), evaluates
    using F1-minority, MCC, Precision, and Recall per fold, then retrains on
    the full dataset to save final artifacts.

    Args:
        feature_matrix_path: Path to feature_matrix.parquet.
        artifacts_dir: Directory for saved model artifacts.
        evaluation_dir: Directory for training_report.json.
        n_estimators: XGBoost number of boosting rounds.
        max_depth: XGBoost max tree depth.
        learning_rate: XGBoost learning rate (eta).
        logreg_max_iter: LogReg maximum number of solver iterations.
        logreg_C: LogReg inverse regularization strength.

    Returns:
        Dict keyed by model_key (e.g. 'logreg_model1') with:
          - 'folds': list of per-fold metric dicts
          - 'mean': dict of mean metrics across folds
          - 'std': dict of std metrics across folds

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

    # ------------------------------------------------------------------
    # Step 1: Load feature matrix
    # ------------------------------------------------------------------
    df = pd.read_parquet(feature_matrix_path)
    logger.info("Loaded feature matrix: %d rows, %d columns", len(df), len(df.columns))

    # ------------------------------------------------------------------
    # Step 2: Read feature column order from feature_names.json
    # ------------------------------------------------------------------
    feature_names_path = artifacts_dir / "feature_names.json"
    if feature_names_path.exists():
        with open(feature_names_path) as f:
            feature_names_raw = json.load(f)
        # Handle both flat list (legacy) and list-of-dicts (Phase 3+)
        if feature_names_raw and isinstance(feature_names_raw[0], dict):
            feature_cols: list[str] = [entry["name"] for entry in feature_names_raw]
        else:
            feature_cols = feature_names_raw
    else:
        # Fallback: use module constants in canonical order
        feature_cols = CATEGORICAL_FEATURES + PIF_FEATURES + NUMERIC_FEATURES
        logger.warning(
            "feature_names.json not found at %s; using module constant order", feature_names_path
        )

    logger.info("Feature columns (%d): %s", len(feature_cols), feature_cols)

    # ------------------------------------------------------------------
    # Step 3: Build X and groups arrays (shared across both targets)
    # ------------------------------------------------------------------
    X: np.ndarray = df[feature_cols].to_numpy(dtype=float)
    groups: np.ndarray = df["incident_id"].to_numpy()

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    evaluation_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Step 4: Train for each target
    # ------------------------------------------------------------------
    for target_suffix, target_col in _TARGETS.items():
        logger.info("=" * 60)
        logger.info("Training for target: %s", target_col)
        logger.info("=" * 60)

        y: np.ndarray = df[target_col].to_numpy()
        n_positive = int(y.sum())
        n_negative = int((y == 0).sum())
        n_total = len(y)
        logger.info(
            "  %s: %d positive (%.1f%%), %d negative",
            target_col, n_positive, 100.0 * n_positive / n_total, n_negative,
        )

        # Compute scale_pos_weight from data — not hardcoded (D-02, D-03)
        if n_positive == 0:
            scale_pos_weight = 1.0
            logger.warning("No positive examples for %s — scale_pos_weight=1.0", target_col)
        else:
            scale_pos_weight = n_negative / n_positive
        logger.info("  scale_pos_weight=%.4f", scale_pos_weight)

        # Get GroupKFold splits
        splits = get_group_kfold_splits(X, y, groups, n_splits=5)

        # ------------------------------------------------------------------
        # Logistic Regression (class_weight='balanced')
        # ------------------------------------------------------------------
        logreg_key = f"logreg_{target_suffix}"
        lr_folds: list[dict[str, float]] = []

        for fold_idx, (train_idx, test_idx) in enumerate(splits):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            lr = LogisticRegression(
                class_weight="balanced",
                solver="lbfgs",
                max_iter=logreg_max_iter,
                C=logreg_C,
                random_state=42,
            )
            lr.fit(X_train, y_train)
            y_pred = lr.predict(X_test)
            fold_metrics = _compute_fold_metrics(y_test, y_pred)
            lr_folds.append(fold_metrics)
            logger.info(
                "  LogReg fold %d/%d: F1=%.3f MCC=%.3f",
                fold_idx + 1, len(splits), fold_metrics["f1_minority"], fold_metrics["mcc"],
            )

        lr_mean, lr_std = _aggregate_folds(lr_folds)
        results[logreg_key] = {"folds": lr_folds, "mean": lr_mean, "std": lr_std}
        logger.info(
            "  LogReg CV mean F1=%.3f±%.3f MCC=%.3f±%.3f",
            lr_mean.get("f1_minority", 0), lr_std.get("f1_minority", 0),
            lr_mean.get("mcc", 0), lr_std.get("mcc", 0),
        )

        # Retrain LogReg on full data and save artifact
        lr_final = LogisticRegression(
            class_weight="balanced",
            solver="lbfgs",
            max_iter=logreg_max_iter,
            C=logreg_C,
            random_state=42,
        )
        lr_final.fit(X, y)
        logreg_path = artifacts_dir / f"logreg_{target_suffix}.joblib"
        joblib.dump(lr_final, logreg_path)
        logger.info("  LogReg artifact saved: %s", logreg_path)

        # ------------------------------------------------------------------
        # XGBoost (scale_pos_weight from data, eval_metric in constructor per 3.0 API)
        # ------------------------------------------------------------------
        xgb_key = f"xgboost_{target_suffix}"
        xgb_folds: list[dict[str, float]] = []

        for fold_idx, (train_idx, test_idx) in enumerate(splits):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            # CRITICAL: eval_metric in constructor (NOT in fit()) — XGBoost 3.0 breaking change
            xgb = XGBClassifier(
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
            xgb.fit(X_train, y_train)
            y_pred = xgb.predict(X_test)
            fold_metrics = _compute_fold_metrics(y_test, y_pred)
            xgb_folds.append(fold_metrics)
            logger.info(
                "  XGBoost fold %d/%d: F1=%.3f MCC=%.3f",
                fold_idx + 1, len(splits), fold_metrics["f1_minority"], fold_metrics["mcc"],
            )

        xgb_mean, xgb_std = _aggregate_folds(xgb_folds)
        results[xgb_key] = {"folds": xgb_folds, "mean": xgb_mean, "std": xgb_std}
        logger.info(
            "  XGBoost CV mean F1=%.3f±%.3f MCC=%.3f±%.3f",
            xgb_mean.get("f1_minority", 0), xgb_std.get("f1_minority", 0),
            xgb_mean.get("mcc", 0), xgb_std.get("mcc", 0),
        )

        # Retrain XGBoost on full data and save artifact (XGBoost native JSON)
        xgb_final = XGBClassifier(
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
        xgb_final.fit(X, y)
        xgb_path = artifacts_dir / f"xgb_{target_suffix}.json"
        xgb_final.save_model(str(xgb_path))
        logger.info("  XGBoost artifact saved: %s", xgb_path)

    # ------------------------------------------------------------------
    # Step 5: Write training_report.json
    # ------------------------------------------------------------------
    report_path = evaluation_dir / "training_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    logger.info("Training report written: %s", report_path)

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        results = train_models()
        print("\n=== Training Summary ===")
        for model_key, model_results in results.items():
            mean = model_results.get("mean", {})
            std = model_results.get("std", {})
            print(
                f"  {model_key}: F1={mean.get('f1_minority', 0):.3f}±{std.get('f1_minority', 0):.3f}"
                f" MCC={mean.get('mcc', 0):.3f}±{std.get('mcc', 0):.3f}"
                f" P={mean.get('precision', 0):.3f} R={mean.get('recall', 0):.3f}"
            )
        print(f"\nTraining report: {TRAINING_REPORT_PATH}")
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
