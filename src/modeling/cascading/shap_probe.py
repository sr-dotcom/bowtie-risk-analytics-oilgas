"""SHAP TreeExplainer helpers for cascading XGBoost pipelines.

R023 contract: TreeExplainer is ALWAYS built in-memory from a loaded
pipeline; it is NEVER serialised to disk.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import shap
from sklearn.pipeline import Pipeline


def build_tree_explainer(pipeline: Pipeline) -> shap.TreeExplainer:
    """Extract XGBClassifier from pipeline and build a TreeExplainer.

    The explainer operates in margin (log-odds) space by default for
    XGBClassifier — this is SHAP's default for tree models and gives
    additive feature contributions in log-odds units.

    Parameters
    ----------
    pipeline:
        Fitted sklearn Pipeline with steps "prep" (ColumnTransformer) and
        "clf" (XGBClassifier).

    Returns
    -------
    shap.TreeExplainer
        In-memory explainer bound to the XGBClassifier.  Never serialise.
    """
    clf = pipeline.named_steps["clf"]
    return shap.TreeExplainer(clf)


def compute_shap_for_record(
    pipeline: Pipeline,
    explainer: shap.TreeExplainer,
    input_record_dict: dict,
    all_features: list[str],
) -> tuple[np.ndarray, list[str]]:
    """Compute SHAP values for a single record.

    Feature names come from caller-supplied `all_features` (loaded from the
    metadata JSON sidecar) — NOT from `model.feature_names_in_`, which may be
    None after a joblib round-trip through ColumnTransformer.

    Parameters
    ----------
    pipeline:
        Fitted pipeline (prep + clf).
    explainer:
        TreeExplainer already bound to pipeline's clf step.
    input_record_dict:
        A dict (or dict-like) with keys matching `all_features`.  A single
        row is expected.
    all_features:
        Ordered list of feature names from the metadata JSON `all_features`
        key.  Length must match the preprocessed matrix width (18).

    Returns
    -------
    shap_values_1d : np.ndarray, shape (n_features,)
        SHAP values for the positive class (index 1) in margin space.
    feature_names : list[str]
        `all_features` passed through unchanged — order-preserving.
    """
    prep = pipeline.named_steps["prep"]

    # Build a single-row DataFrame in the correct feature order.
    row_df = pd.DataFrame([input_record_dict])[all_features]

    # Transform through the preprocessor only (OrdinalEncoder + passthrough).
    X_prep = prep.transform(row_df)

    # shap_values returns shape (n_samples, n_features) for binary XGB.
    sv = explainer.shap_values(X_prep)
    shap_values_1d = np.asarray(sv[0])  # first (and only) row

    return shap_values_1d, list(all_features)
