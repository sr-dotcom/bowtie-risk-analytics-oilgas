# src/modeling/cascading

The cascading XGBoost model: pair-feature construction, training pipeline, prediction, and SHAP explanations.

The model predicts barrier-failure probability conditioned on the failure state of upstream barriers in the same pathway, rather than treating each barrier independently. Pair features (18 of them) encode upstream-downstream relationships drawn from the 156-incident training set.

Key entry points:

- `train.py` — fits the pipeline, writes `xgb_cascade_y_fail_pipeline.joblib` + metadata
- `predict.py` — `/predict-cascading` endpoint backend
- `explain.py` — SHAP attributions surfaced by `/explain-cascading`

Branch-activation logic for the secondary `y_hf_fail` target follows D019 (strict total-ordering, mutually exclusive). PIFs excluded from `y_fail` features per D011; re-included for `y_hf_fail` per D018.

See [Chapter 3 — Pair Features and the Cascade](../../../docs/journey/03-cascade-model.md) and [Chapter 4 — Two Explanation Signals](../../../docs/journey/04-explainability-signals.md).
