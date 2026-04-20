"""S02b: y_hf_fail signal recovery experiment + D016 branch activation.

Runs two feature-set variants for ``y_hf_fail_target`` with frozen Patrick
hyperparameters and GroupKFold(5) CV, then applies the pre-declared D016
branches (A/B/C) to the best variant and emits recovery artifacts.

``y_fail_target`` is NOT touched — its pipeline and metadata from S02 must
remain byte-identical.

Run as:  python -m src.modeling.cascading.hf_recovery
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
_INCIDENTS_CSV = Path("data/processed/flat_incidents_combined.csv")
_ARTIFACTS_DIR = Path("data/models/artifacts")
_EVAL_DIR = Path("data/models/evaluation")

_N_SPLITS = 5

_RISK_TIER_THRESHOLDS = {"HIGH": 0.66, "MEDIUM": 0.33, "LOW": 0.33}

# Patrick hyperparameters — frozen, identical across both variants.
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

# 12 PIF boolean _mentioned features, short names (per S02b plan).
_PIF_PEOPLE = [
    "competence_mentioned",
    "fatigue_mentioned",
    "communication_mentioned",
    "situational_awareness_mentioned",
]
_PIF_WORK = [
    "procedures_mentioned",
    "workload_mentioned",
    "time_pressure_mentioned",
    "tools_equipment_mentioned",
]
_PIF_ORGANISATION = [
    "safety_culture_mentioned",
    "management_of_change_mentioned",
    "supervision_mentioned",
    "training_mentioned",
]
_PIF_COLUMNS: list[str] = _PIF_PEOPLE + _PIF_WORK + _PIF_ORGANISATION

# Mapping from flat_incidents_combined.csv prefixed names → short names.
_PIF_RENAME: dict[str, str] = {
    **{f"incident__pifs__people__{c}": c for c in _PIF_PEOPLE},
    **{f"incident__pifs__work__{c}": c for c in _PIF_WORK},
    **{f"incident__pifs__organisation__{c}": c for c in _PIF_ORGANISATION},
}


def _load_pif_table() -> pd.DataFrame:
    """Return (incident_id, 12 PIF booleans as int 0/1) — one row per incident.

    Raises loudly if any of the 12 expected PIF columns is absent from the
    source CSV or if any incident_id shows inconsistent PIF values across
    rows (no silent fallback, per D010/D018).
    """
    df = pd.read_csv(_INCIDENTS_CSV)
    prefixed = list(_PIF_RENAME.keys())
    missing = [c for c in prefixed if c not in df.columns]
    if missing:
        raise ValueError(
            f"flat_incidents_combined.csv missing PIF columns: {missing}"
        )
    pif = df[["incident_id"] + prefixed].rename(columns=_PIF_RENAME).copy()
    for c in _PIF_COLUMNS:
        pif[c] = pif[c].astype(bool).astype(int)
    # Per-incident consistency: nunique>1 on any PIF column means conflict.
    grp = pif.groupby("incident_id")[_PIF_COLUMNS].nunique()
    conflicts = grp[(grp > 1).any(axis=1)]
    if not conflicts.empty:
        raise ValueError(
            "Inconsistent per-incident PIF values for incidents: "
            f"{list(conflicts.index)}"
        )
    pif = pif.drop_duplicates(subset="incident_id").reset_index(drop=True)
    return pif


def _build_enriched_pairs(
    add_aggregate: bool,
) -> tuple[pd.DataFrame, list[str], list[str], list[str]]:
    """Build pair dataset + left-join PIFs; optionally add pif_count aggregate.

    Returns (df_pairs, cat_all, num_all_extended, all_features_extended).
    Categorical features are unchanged at 5.
    """
    df = pd.read_parquet(_PARQUET_PATH)
    df_pairs, cat_all, num_all, _all_features = build_pair_dataset(df)

    pif = _load_pif_table()
    if add_aggregate:
        pif["pif_count_in_incident"] = (
            pif[_PIF_COLUMNS].sum(axis=1).astype(int)
        )

    before = len(df_pairs)
    df_pairs = df_pairs.merge(pif, on="incident_id", how="left")
    if len(df_pairs) != before:
        raise ValueError(
            f"left-join on incident_id changed row count: {before} → "
            f"{len(df_pairs)}"
        )
    nulls = df_pairs[_PIF_COLUMNS].isna().sum()
    if (nulls > 0).any():
        missing_ids = (
            df_pairs.loc[df_pairs[_PIF_COLUMNS[0]].isna(), "incident_id"]
            .unique()
            .tolist()
        )
        raise ValueError(
            f"{len(missing_ids)} pair incident_ids missing PIF rows in "
            f"flat_incidents_combined.csv: {missing_ids[:5]}..."
        )

    extra_num = list(_PIF_COLUMNS)
    if add_aggregate:
        extra_num.append("pif_count_in_incident")
    num_all_ext = num_all + extra_num
    all_features_ext = cat_all + num_all_ext
    return df_pairs, cat_all, num_all_ext, all_features_ext


def _run_cv(
    X: pd.DataFrame,
    y: pd.Series,
    groups: np.ndarray,
    cat_all: list[str],
    num_all: list[str],
) -> tuple[list[float], float, float]:
    """GroupKFold(5) CV with per-fold scale_pos_weight from training fold only."""
    gkf = GroupKFold(n_splits=_N_SPLITS)
    fold_aucs: list[float] = []
    for tr_idx, te_idx in gkf.split(X, y, groups=groups):
        X_tr, X_te = X.iloc[tr_idx], X.iloc[te_idx]
        y_tr, y_te = y.iloc[tr_idx], y.iloc[te_idx]
        spw = float((1 - y_tr.mean()) / y_tr.mean())
        pipe = make_xgb_pipeline(cat_all, num_all, scale_pos_weight=spw)
        pipe.fit(X_tr, y_tr)
        proba = pipe.predict_proba(X_te)[:, 1]
        fold_aucs.append(float(roc_auc_score(y_te, proba)))
    return fold_aucs, float(np.mean(fold_aucs)), float(np.std(fold_aucs))


def _write_variant_report(
    variant_letter: str,
    variant_label: str,
    all_features: list[str],
    fold_aucs: list[float],
    mean_auc: float,
    std_auc: float,
    training_rows: int,
    positive_rate: float,
    n_features: int,
    out_path: Path,
) -> None:
    lines = [
        f"# S02b Variant {variant_letter} CV Report",
        "",
        f"- variant: {variant_letter} ({variant_label})",
        "- target: y_hf_fail_target",
        f"- training_rows: {training_rows}",
        f"- positive_rate: {positive_rate:.4f}",
        f"- n_features: {n_features}",
        "",
        "## Per-fold AUC",
        "",
        "| Fold | AUC    |",
        "|------|--------|",
    ]
    for i, a in enumerate(fold_aucs, start=1):
        lines.append(f"| {i:<4} | {a:.4f} |")
    lines += ["", f"Mean AUC: {mean_auc:.4f} ± {std_auc:.4f}", ""]
    lines += ["## Features", ""]
    for f in all_features:
        lines.append(f"- {f}")
    lines += ["", "## Hyperparameters (Patrick, frozen)", ""]
    for k, v in _PATRICK_HYPERPARAMETERS.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _variant_result(
    df_pairs: pd.DataFrame,
    cat_all: list[str],
    num_all: list[str],
    all_features: list[str],
    fold_aucs: list[float],
    mean_auc: float,
    std_auc: float,
    n_features: int,
    positive_rate: float,
) -> dict:
    return {
        "per_fold": fold_aucs,
        "mean": mean_auc,
        "std": std_auc,
        "n_features": n_features,
        "cat_all": cat_all,
        "num_all": num_all,
        "all_features": all_features,
        "df_pairs": df_pairs,
        "training_rows": int(len(df_pairs)),
        "positive_rate": positive_rate,
    }


def train_variant_a() -> dict:
    """Variant A: structural baseline + 12 PIF boolean _mentioned flags. 30 features."""
    df_pairs, cat_all, num_all, all_features = _build_enriched_pairs(
        add_aggregate=False
    )
    if len(all_features) != 30:
        raise ValueError(
            f"Variant A expected 30 features, got {len(all_features)}"
        )
    X = df_pairs[all_features].copy()
    y = df_pairs["y_hf_fail_target"].copy()
    groups = df_pairs["incident_id"].values
    fold_aucs, mean_auc, std_auc = _run_cv(X, y, groups, cat_all, num_all)
    _EVAL_DIR.mkdir(parents=True, exist_ok=True)
    _write_variant_report(
        "A",
        "structural + 12 PIF booleans",
        all_features,
        fold_aucs,
        mean_auc,
        std_auc,
        training_rows=int(len(df_pairs)),
        positive_rate=float(y.mean()),
        n_features=30,
        out_path=_EVAL_DIR / "s02b_variant_A_cv.md",
    )
    return _variant_result(
        df_pairs, cat_all, num_all, all_features,
        fold_aucs, mean_auc, std_auc, 30, float(y.mean()),
    )


def train_variant_b() -> dict:
    """Variant B: Variant A + pif_count_in_incident aggregate. 31 features."""
    df_pairs, cat_all, num_all, all_features = _build_enriched_pairs(
        add_aggregate=True
    )
    if len(all_features) != 31:
        raise ValueError(
            f"Variant B expected 31 features, got {len(all_features)}"
        )
    X = df_pairs[all_features].copy()
    y = df_pairs["y_hf_fail_target"].copy()
    groups = df_pairs["incident_id"].values
    fold_aucs, mean_auc, std_auc = _run_cv(X, y, groups, cat_all, num_all)
    _EVAL_DIR.mkdir(parents=True, exist_ok=True)
    _write_variant_report(
        "B",
        "structural + 12 PIF booleans + pif_count_in_incident aggregate",
        all_features,
        fold_aucs,
        mean_auc,
        std_auc,
        training_rows=int(len(df_pairs)),
        positive_rate=float(y.mean()),
        n_features=31,
        out_path=_EVAL_DIR / "s02b_variant_B_cv.md",
    )
    return _variant_result(
        df_pairs, cat_all, num_all, all_features,
        fold_aucs, mean_auc, std_auc, 31, float(y.mean()),
    )


def _select_best_variant(a: dict, b: dict) -> tuple[str, dict, str]:
    """Return (winner_letter, winner_dict, rationale)."""
    if a["mean"] > b["mean"]:
        return (
            "A", a,
            f"Variant A mean AUC {a['mean']:.4f} > Variant B mean AUC {b['mean']:.4f}",
        )
    if b["mean"] > a["mean"]:
        return (
            "B", b,
            f"Variant B mean AUC {b['mean']:.4f} > Variant A mean AUC {a['mean']:.4f}",
        )
    # Tie on mean → lower std wins.
    if a["std"] <= b["std"]:
        return (
            "A", a,
            f"Mean AUC tied at {a['mean']:.4f}; Variant A lower std "
            f"({a['std']:.4f} <= {b['std']:.4f})",
        )
    return (
        "B", b,
        f"Mean AUC tied at {a['mean']:.4f}; Variant B lower std "
        f"({b['std']:.4f} < {a['std']:.4f})",
    )


def _branch_for(winner: dict) -> tuple[str, str]:
    """Apply D016 strict total ordering. Returns (branch_letter, rule_description)."""
    mean_auc = winner["mean"]
    folds = winner["per_fold"]
    if mean_auc >= 0.70 and all(f >= 0.60 for f in folds):
        return "A", "mean AUC >= 0.70 AND every fold AUC >= 0.60"
    if mean_auc >= 0.60 and all(f >= 0.55 for f in folds):
        return (
            "B",
            "mean AUC >= 0.60 AND every fold AUC >= 0.55 (Branch A did not qualify)",
        )
    return (
        "C",
        "catch-all — best variant did not meet Branch A or Branch B thresholds",
    )


def _emit_recovery_report(
    variant_a: dict,
    variant_b: dict,
    winner_letter: str,
    winner_rationale: str,
    branch_letter: str,
    branch_rule: str,
) -> Path:
    lines = ["# S02b HF Signal Recovery Report", ""]
    # Section 1: Variant A metrics
    lines += ["## 1. Variant A Metrics", ""]
    lines += [f"- n_features: {variant_a['n_features']}", ""]
    lines += ["| Fold | AUC    |", "|------|--------|"]
    for i, f in enumerate(variant_a["per_fold"], start=1):
        lines.append(f"| {i:<4} | {f:.4f} |")
    lines += ["", f"Mean AUC: {variant_a['mean']:.4f} ± {variant_a['std']:.4f}", ""]
    # Section 2: Variant B metrics
    lines += ["## 2. Variant B Metrics", ""]
    lines += [f"- n_features: {variant_b['n_features']}", ""]
    lines += ["| Fold | AUC    |", "|------|--------|"]
    for i, f in enumerate(variant_b["per_fold"], start=1):
        lines.append(f"| {i:<4} | {f:.4f} |")
    lines += ["", f"Mean AUC: {variant_b['mean']:.4f} ± {variant_b['std']:.4f}", ""]
    # Section 3: Best variant selection
    lines += [
        "## 3. Best Variant Selection",
        "",
        f"Winner: Variant {winner_letter}",
        f"Rationale: {winner_rationale}",
        "",
    ]
    # Section 4: Branch activation — single-line regex-matchable statement.
    lines += [
        "## 4. Branch Activation",
        "",
        f"Activated branch: {branch_letter}",
        f"Rule applied: {branch_rule}",
        "",
    ]
    out = _EVAL_DIR / "s02b_hf_recovery_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _apply_branch(
    branch_letter: str,
    winner_letter: str,
    winner: dict,
) -> None:
    """Replace pipeline+metadata for A/B; metadata-only annotation for C."""
    meta_path = _ARTIFACTS_DIR / "xgb_cascade_y_hf_fail_metadata.json"
    pipe_path = _ARTIFACTS_DIR / "xgb_cascade_y_hf_fail_pipeline.joblib"

    if branch_letter in ("A", "B"):
        cat_all = winner["cat_all"]
        num_all = winner["num_all"]
        all_features = winner["all_features"]
        df_pairs = winner["df_pairs"]
        X = df_pairs[all_features].copy()
        y = df_pairs["y_hf_fail_target"].copy()
        spw = float((1 - y.mean()) / y.mean())
        pipe = make_xgb_pipeline(cat_all, num_all, scale_pos_weight=spw)
        pipe.fit(X, y)
        joblib.dump(pipe, pipe_path)
        meta = {
            "model_name": "xgb_cascade_y_hf_fail",
            "target": "y_hf_fail_target",
            "model_type": "XGBClassifier",
            "categorical_features": cat_all,
            "numerical_features": num_all,
            "all_features": all_features,
            "risk_tier_thresholds": _RISK_TIER_THRESHOLDS,
            "training_rows": int(len(X)),
            "positive_rate": float(y.mean()),
            "scale_pos_weight": spw,
            "patrick_hyperparameters": _PATRICK_HYPERPARAMETERS,
            "cv_scores": {
                "per_fold": [round(a, 6) for a in winner["per_fold"]],
                "mean": round(winner["mean"], 6),
                "std": round(winner["std"], 6),
            },
            "s02b_branch": branch_letter,
            "s02b_variant": winner_letter,
            "s02b_feature_source": "base_v3_pif_booleans",
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    else:
        # Branch C: do NOT touch the joblib. Append-only metadata annotation.
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["s02b_branch"] = "C"
        meta["s02b_note"] = (
            "production surface dropped per D016 Branch C; "
            "retained for M004 reference"
        )
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def decision_gate(
    variant_a: dict | None = None,
    variant_b: dict | None = None,
) -> dict:
    """T03: read both variants, pick winner, activate D016 branch, write artifacts."""
    if variant_a is None:
        variant_a = train_variant_a()
    if variant_b is None:
        variant_b = train_variant_b()

    for fname in ("s02b_variant_A_cv.md", "s02b_variant_B_cv.md"):
        if not (_EVAL_DIR / fname).exists():
            raise FileNotFoundError(
                f"Required variant CV report missing: {fname}"
            )

    winner_letter, winner, winner_rationale = _select_best_variant(
        variant_a, variant_b
    )
    branch_letter, branch_rule = _branch_for(winner)
    _emit_recovery_report(
        variant_a, variant_b,
        winner_letter, winner_rationale,
        branch_letter, branch_rule,
    )
    _apply_branch(branch_letter, winner_letter, winner)

    return {
        "winner": winner_letter,
        "winner_rationale": winner_rationale,
        "branch": branch_letter,
        "branch_rule": branch_rule,
        "variant_a": {
            "per_fold": variant_a["per_fold"],
            "mean": variant_a["mean"],
            "std": variant_a["std"],
        },
        "variant_b": {
            "per_fold": variant_b["per_fold"],
            "mean": variant_b["mean"],
            "std": variant_b["std"],
        },
    }


def main() -> None:
    a = train_variant_a()
    print(
        f"[s02b] Variant A: mean AUC {a['mean']:.4f} ± {a['std']:.4f}  "
        f"folds={[f'{x:.4f}' for x in a['per_fold']]}"
    )
    b = train_variant_b()
    print(
        f"[s02b] Variant B: mean AUC {b['mean']:.4f} ± {b['std']:.4f}  "
        f"folds={[f'{x:.4f}' for x in b['per_fold']]}"
    )
    result = decision_gate(a, b)
    print(f"[s02b] Winner: Variant {result['winner']} — {result['winner_rationale']}")
    print(f"[s02b] Activated branch: {result['branch']}")
    print(f"[s02b] Rule: {result['branch_rule']}")


if __name__ == "__main__":
    main()
