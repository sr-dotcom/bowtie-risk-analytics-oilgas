"""GroupKFold(5) quality gate on y_fail_target.

Run as:  python -m src.modeling.cascading.mini_gate

Exits 0 when mean AUC ≥ 0.70 and every fold AUC ≥ 0.60 (R018).
Exits 1 otherwise — halts auto-mode.

Writes:  data/models/evaluation/cascading_mini_gate_report.md
Prints:  mean AUC to stdout.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from src.modeling.cascading.pair_builder import (
    build_pair_dataset,
    make_xgb_pipeline,
)

_PARQUET_PATH = Path("data/processed/cascading_training.parquet")
_REPORT_PATH = Path("data/models/evaluation/cascading_mini_gate_report.md")

_AUC_MEAN_THRESHOLD = 0.70
_AUC_FOLD_FLOOR = 0.60
_N_SPLITS = 5


def run_mini_gate(
    parquet_path: Path = _PARQUET_PATH,
    report_path: Path = _REPORT_PATH,
) -> tuple[list[float], float, float, bool]:
    """Run GroupKFold(5) gate on y_fail_target.

    Returns
    -------
    fold_aucs, mean_auc, std_auc, passed
    """
    df = pd.read_parquet(parquet_path)
    df_pairs, cat_all, num_all, all_features = build_pair_dataset(df)

    X = df_pairs[all_features].copy()
    y = df_pairs["y_fail_target"].copy()
    groups = df_pairs["incident_id"].values

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
    passed = mean_auc >= _AUC_MEAN_THRESHOLD and all(
        a >= _AUC_FOLD_FLOOR for a in fold_aucs
    )

    _write_report(fold_aucs, mean_auc, std_auc, passed, report_path)
    return fold_aucs, mean_auc, std_auc, passed


def _write_report(
    fold_aucs: list[float],
    mean_auc: float,
    std_auc: float,
    passed: bool,
    report_path: Path,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Cascading Mini-Gate Report (y_fail_target)",
        "",
        f"Gate thresholds: mean AUC ≥ {_AUC_MEAN_THRESHOLD}, "
        f"per-fold floor ≥ {_AUC_FOLD_FLOOR}",
        "",
        "| Fold | AUC   |",
        "|------|-------|",
    ]
    for i, auc in enumerate(fold_aucs, start=1):
        flag = "" if auc >= _AUC_FOLD_FLOOR else " ⚠ below floor"
        lines.append(f"| {i:<4} | {auc:.4f}{flag} |")

    lines += [
        "",
        f"Mean AUC: {mean_auc:.4f} ± {std_auc:.4f}",
        "",
        f"Verdict: {'PASS' if passed else 'FAIL'}",
    ]

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    fold_aucs, mean_auc, std_auc, passed = run_mini_gate()
    print(f"Mean AUC (y_fail_target, GroupKFold-5): {mean_auc:.4f}")
    if not passed:
        print(
            f"GATE FAILED: mean={mean_auc:.4f} (need ≥{_AUC_MEAN_THRESHOLD}), "
            f"folds={[f'{a:.4f}' for a in fold_aucs]}",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"Gate passed: {mean_auc:.4f} ± {std_auc:.4f}")


if __name__ == "__main__":
    main()
