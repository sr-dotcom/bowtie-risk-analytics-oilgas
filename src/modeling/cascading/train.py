"""Full pipeline training for cascading XGBoost models.

Run as:  python -m src.modeling.cascading.train

Trains both targets (y_fail_target, y_hf_fail_target) using the full pair
dataset — no holdout; CV is reported separately.  Artifacts are written
atomically (after successful fit) to avoid partial state.

Produces:
  data/models/artifacts/xgb_cascade_y_fail_pipeline.joblib
  data/models/artifacts/xgb_cascade_y_hf_fail_pipeline.joblib
  data/models/artifacts/xgb_cascade_y_fail_metadata.json
  data/models/artifacts/xgb_cascade_y_hf_fail_metadata.json
  data/models/evaluation/cascading_cv_report.md
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from src.modeling.cascading.pair_builder import (
    build_pair_dataset,
    make_xgb_pipeline,
)

_PARQUET_PATH = Path("data/processed/cascading_training.parquet")
_ARTIFACTS_DIR = Path("data/models/artifacts")
_EVAL_DIR = Path("data/models/evaluation")

_N_SPLITS = 5
_RISK_TIER_THRESHOLDS = {"HIGH": 0.66, "MEDIUM": 0.33, "LOW": 0.33}

# Patrick's cell-9 hyperparameters — stored here for metadata JSON provenance.
_PATRICK_HYPERPARAMETERS: dict = {
    "n_estimators": 400,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "eval_metric": "logloss",
    "random_state": 42,
    "n_jobs": -1,
}

TARGETS: list[str] = ["y_fail_target", "y_hf_fail_target"]


def _stem(target: str) -> str:
    """Strip _target suffix: y_fail_target → y_fail."""
    return target.removesuffix("_target")


def _run_cv(
    X: pd.DataFrame,
    y: pd.Series,
    groups: np.ndarray,
    cat_all: list[str],
    num_all: list[str],
) -> tuple[list[float], float, float]:
    """GroupKFold(5) CV; returns (fold_aucs, mean_auc, std_auc)."""
    gkf = GroupKFold(n_splits=_N_SPLITS)
    fold_aucs: list[float] = []

    for train_idx, test_idx in gkf.split(X, y, groups=groups):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        spw = (1 - y_train.mean()) / y_train.mean()
        pipe = make_xgb_pipeline(cat_all, num_all, scale_pos_weight=spw)
        pipe.fit(X_train, y_train)

        proba = pipe.predict_proba(X_test)[:, 1]
        auc = float(roc_auc_score(y_test, proba))
        fold_aucs.append(auc)

    mean_auc = float(np.mean(fold_aucs))
    std_auc = float(np.std(fold_aucs))
    return fold_aucs, mean_auc, std_auc


def _write_cv_report(
    cv_results: dict[str, tuple[list[float], float, float]],
    df_pairs: pd.DataFrame,
    report_path: Path,
) -> None:
    lines = ["# Cascading CV Report", ""]
    for target, (fold_aucs, mean_auc, std_auc) in cv_results.items():
        y = df_pairs[target]
        lines += [
            f"## {target}",
            "",
            f"- training_rows: {len(df_pairs)}",
            f"- positive_rate: {y.mean():.4f}",
            "",
            "| Fold | AUC    |",
            "|------|--------|",
        ]
        for i, auc in enumerate(fold_aucs, start=1):
            lines.append(f"| {i:<4} | {auc:.4f} |")
        lines += [
            "",
            f"Mean AUC: {mean_auc:.4f} ± {std_auc:.4f}",
            "",
        ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def train_and_save(
    parquet_path: Path = _PARQUET_PATH,
    artifacts_dir: Path = _ARTIFACTS_DIR,
    eval_dir: Path = _EVAL_DIR,
) -> dict[str, dict]:
    """Train both cascading pipelines, write all artifacts.

    Returns a dict keyed by target name with training metadata for each.
    """
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    eval_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(parquet_path)
    df_pairs, cat_all, num_all, all_features = build_pair_dataset(df)
    X = df_pairs[all_features].copy()
    groups = df_pairs["incident_id"].values

    cv_results: dict[str, tuple[list[float], float, float]] = {}
    summaries: dict[str, dict] = {}

    for target in TARGETS:
        y = df_pairs[target].copy()
        stem = _stem(target)

        print(f"[train] {target}: running GroupKFold({_N_SPLITS}) CV...")
        fold_aucs, mean_auc, std_auc = _run_cv(X, y, groups, cat_all, num_all)
        cv_results[target] = (fold_aucs, mean_auc, std_auc)
        print(f"[train] {target}: CV AUC {mean_auc:.4f} ± {std_auc:.4f}, folds={[f'{a:.4f}' for a in fold_aucs]}")

        scale_pos_weight = float((1 - y.mean()) / y.mean())
        pipe = make_xgb_pipeline(cat_all, num_all, scale_pos_weight=scale_pos_weight)
        print(f"[train] {target}: fitting on all {len(X)} pair rows...")
        pipe.fit(X, y)

        # Atomic dump after successful fit only.
        joblib_path = artifacts_dir / f"xgb_cascade_{stem}_pipeline.joblib"
        joblib.dump(pipe, joblib_path)
        print(f"[train] {target}: saved {joblib_path}")

        metadata: dict = {
            "model_name": f"xgb_cascade_{stem}",
            "target": target,
            "model_type": "XGBClassifier",
            "categorical_features": cat_all,
            "numerical_features": num_all,
            "all_features": all_features,
            "risk_tier_thresholds": _RISK_TIER_THRESHOLDS,
            "training_rows": int(len(X)),
            "positive_rate": float(y.mean()),
            "scale_pos_weight": scale_pos_weight,
            "patrick_hyperparameters": _PATRICK_HYPERPARAMETERS,
            "cv_scores": {
                "per_fold": [round(a, 6) for a in fold_aucs],
                "mean": round(mean_auc, 6),
                "std": round(std_auc, 6),
            },
        }
        meta_path = artifacts_dir / f"xgb_cascade_{stem}_metadata.json"
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        print(f"[train] {target}: metadata saved to {meta_path}")

        summaries[target] = metadata

    _write_cv_report(cv_results, df_pairs, eval_dir / "cascading_cv_report.md")
    print("[train] cascading_cv_report.md written")

    return summaries


def main() -> None:
    summaries = train_and_save()
    for target, meta in summaries.items():
        cv = meta["cv_scores"]
        print(
            f"[done] {target}: AUC {cv['mean']:.4f} ± {cv['std']:.4f}  "
            f"(training_rows={meta['training_rows']}, positive_rate={meta['positive_rate']:.4f})"
        )


if __name__ == "__main__":
    main()
