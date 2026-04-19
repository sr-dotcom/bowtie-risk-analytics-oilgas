"""Standalone SHAP sanity-check script for S03 reviewers.

Usage:
    python scripts/verify_cascading_shap.py

Loads the y_fail pipeline + metadata, builds a SHAP TreeExplainer in-memory,
computes shap values for the first row of the pair dataset, and prints a
``top_5:`` line with the 5 features of largest absolute SHAP contribution.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

# Allow running as `python scripts/verify_cascading_shap.py` from project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_ARTIFACTS_DIR = Path("data/models/artifacts")
_PARQUET_PATH = Path("data/processed/cascading_training.parquet")


def main() -> None:
    pipeline_path = _ARTIFACTS_DIR / "xgb_cascade_y_fail_pipeline.joblib"
    meta_path = _ARTIFACTS_DIR / "xgb_cascade_y_fail_metadata.json"

    pipeline = joblib.load(pipeline_path)
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    all_features: list[str] = metadata["all_features"]

    from src.modeling.cascading.pair_builder import build_pair_dataset
    from src.modeling.cascading.shap_probe import build_tree_explainer, compute_shap_for_record

    df = pd.read_parquet(_PARQUET_PATH)
    df_pairs, _cat, _num, _feats = build_pair_dataset(df)

    first_row = df_pairs.iloc[0][all_features].to_dict()
    explainer = build_tree_explainer(pipeline)
    sv, feat_names = compute_shap_for_record(pipeline, explainer, first_row, all_features)

    abs_sv = np.abs(sv)
    top5_idx = np.argsort(abs_sv)[::-1][:5]
    top5 = [(feat_names[i], round(float(sv[i]), 6)) for i in top5_idx]

    print(f"top_5: {top5}")
    print(f"expected_value: {explainer.expected_value}")
    print(f"shap_sum: {sv.sum():.6f}")


if __name__ == "__main__":
    main()
