"""Inference module for barrier risk analytics.

Provides BarrierPredictor — a class that loads all model artifacts once at
startup and returns SHAP-augmented predictions for both models.

Design decisions (from CONTEXT.md):
  D-13: BarrierPredictor.__init__ loads all artifacts once (for API lifespan)
  D-14: predict(features_dict) accepts raw unencoded feature dict, encodes
        internally using the saved OrdinalEncoder
  D-15: Returns PredictionResult with 6 fields (probabilities + SHAP per model)
  D-09/SHAP-03: SHAP values from the two models are ALWAYS separate dicts
  SHAP-04: PIF features labeled as 'incident_context' via category field
  Pitfall 3: TreeExplainer is NEVER serialized — recreated from model + .npy

Usage::

    predictor = BarrierPredictor()  # loads once at API startup
    result = predictor.predict({
        'side': 'left',
        'barrier_type': 'engineering',
        'line_of_defense': '1',
        'barrier_family': 'alarm',
        'source_agency': 'BSEE',
        'pif_competence': 1,
        ...
        'supporting_text_count': 3,
    })
    print(result.model1_probability)   # float in [0, 1]
    print(result.model1_shap_values)   # dict[str, float], 18 keys
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import shap
import xgboost as xgb

from src.modeling.feature_engineering import (
    ARTIFACTS_DIR,
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    PIF_FEATURES,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PredictionResult dataclass
# ---------------------------------------------------------------------------

@dataclass
class PredictionResult:
    """Inference result for a single barrier.

    Probabilities are in [0, 1] range.
    SHAP values for XGBoost models are in log-odds space (margin output).
    model1 = barrier failure prediction (label_barrier_failed).
    model2 = human factor sensitivity prediction (label_barrier_failed_human).
    SHAP values from the two models are ALWAYS separate (per D-09, SHAP-03).
    """

    model1_probability: float
    model2_probability: float
    model1_shap_values: dict[str, float]
    model2_shap_values: dict[str, float]
    model1_base_value: float
    model2_base_value: float


# ---------------------------------------------------------------------------
# BarrierPredictor class
# ---------------------------------------------------------------------------

class BarrierPredictor:
    """Loads all models once at startup; thread-safe for read-only inference.

    Phase 5 API instantiates this once via lifespan. predict() is called
    per-request with raw (unencoded) feature dicts.

    Artifacts loaded from ``artifacts_dir``:
      - encoder.joblib            -- OrdinalEncoder for categorical features
      - feature_names.json        -- ordered list-of-dicts [{name, category}]
      - xgb_model1.json           -- XGBoost barrier failure model
      - xgb_model2.json           -- XGBoost human factor sensitivity model
      - shap_background_model1.npy -- background array for TreeExplainer 1
      - shap_background_model2.npy -- background array for TreeExplainer 2

    TreeExplainer is recreated from model + background at init (never deserialized
    directly — see Pitfall 3 in RESEARCH.md).

    Args:
        artifacts_dir: Path to data/models/artifacts/ with all saved artifacts.
            Defaults to ARTIFACTS_DIR from feature_engineering.py.
    """

    def __init__(self, artifacts_dir: Path = ARTIFACTS_DIR) -> None:
        artifacts_dir = Path(artifacts_dir)

        # Load OrdinalEncoder — used to encode raw categorical strings at inference (D-14)
        self._encoder = joblib.load(artifacts_dir / "encoder.joblib")
        logger.debug("OrdinalEncoder loaded from %s", artifacts_dir / "encoder.joblib")

        # Load feature names in upgraded list-of-dicts format (D-08, SHAP-04)
        with open(artifacts_dir / "feature_names.json") as f:
            self._feature_names_raw: list[dict[str, str]] = json.load(f)

        # Handle both flat list (legacy) and list-of-dicts (Phase 3+)
        if self._feature_names_raw and isinstance(self._feature_names_raw[0], dict):
            self._feature_names: list[str] = [f["name"] for f in self._feature_names_raw]
        else:
            # Legacy: flat list — wrap into expected dict format
            self._feature_names = list(self._feature_names_raw)  # type: ignore[arg-type]
            self._feature_names_raw = [{"name": n, "category": "barrier"} for n in self._feature_names]

        logger.debug("Feature names loaded: %d features", len(self._feature_names))

        # Load XGBoost models (native JSON — version-stable serialization)
        self._xgb1 = xgb.XGBClassifier()
        self._xgb1.load_model(str(artifacts_dir / "xgb_model1.json"))

        self._xgb2 = xgb.XGBClassifier()
        self._xgb2.load_model(str(artifacts_dir / "xgb_model2.json"))

        logger.debug("XGBoost models loaded: model1 + model2")

        # Recreate TreeExplainers from model + background array.
        # NEVER deserialize TreeExplainer objects directly (Pitfall 3 from RESEARCH.md).
        bg1: np.ndarray = np.load(str(artifacts_dir / "shap_background_model1.npy"))
        bg2: np.ndarray = np.load(str(artifacts_dir / "shap_background_model2.npy"))

        self._expl1 = shap.TreeExplainer(self._xgb1, data=bg1)
        self._expl2 = shap.TreeExplainer(self._xgb2, data=bg2)

        logger.info(
            "BarrierPredictor loaded: %d features, XGBoost models + TreeExplainers ready",
            len(self._feature_names),
        )

    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    @property
    def feature_names(self) -> list[dict[str, str]]:
        """Return feature names with category metadata (SHAP-04).

        PIF features have category='incident_context'.
        Barrier features (categoricals + numeric) have category='barrier'.

        Returns:
            List of dicts: [{"name": str, "category": str}, ...]
        """
        return self._feature_names_raw

    # -----------------------------------------------------------------------
    # Predict
    # -----------------------------------------------------------------------

    def predict(self, features_dict: dict[str, Any]) -> PredictionResult:
        """Predict barrier failure probability and SHAP values for both models.

        Accepts raw (unencoded) feature dict. Categorical features are encoded
        internally using the loaded OrdinalEncoder (D-14). Unknown categorical
        values are handled gracefully via handle_unknown='use_encoded_value'
        with unknown_value=-1.

        Args:
            features_dict: Dict mapping feature name -> raw value. Categoricals
                should be strings (e.g. 'side': 'left'). PIFs should be 0/1
                integers. Numeric should be int/float.

                Missing PIFs default to 0.
                Missing numeric features default to 0.
                Missing categorical features default to "unknown".

        Returns:
            PredictionResult with:
              - model1_probability, model2_probability: float in [0, 1]
              - model1_shap_values, model2_shap_values: dict[str, float] — ALWAYS separate
              - model1_base_value, model2_base_value: float (log-odds base)
        """
        # Build a single-row array in canonical column order
        row_values: list[Any] = []
        for name in self._feature_names:
            if name in CATEGORICAL_FEATURES:
                row_values.append(features_dict.get(name, "unknown"))
            elif name in PIF_FEATURES:
                row_values.append(int(features_dict.get(name, 0)))
            else:
                # Numeric (supporting_text_count etc.)
                row_values.append(float(features_dict.get(name, 0)))

        # Encode categorical columns using the saved OrdinalEncoder
        n_cat = len(CATEGORICAL_FEATURES)
        cat_raw = [[row_values[i] for i in range(n_cat)]]
        cat_encoded: np.ndarray = self._encoder.transform(cat_raw)

        # Assemble numeric row: [encoded_categoricals, PIF_ints, numeric]
        non_cat_values = row_values[n_cat:]
        X_row: np.ndarray = np.concatenate(
            [cat_encoded[0].astype(float), np.array(non_cat_values, dtype=float)]
        ).reshape(1, -1)

        # ----------------------------------------------------------------
        # Model 1 inference — SEPARATE from Model 2 (D-09, SHAP-03)
        # ----------------------------------------------------------------
        prob1 = float(self._xgb1.predict_proba(X_row)[0, 1])
        shap_vals1: np.ndarray = self._expl1.shap_values(X_row)[0]  # shape (n_features,)
        shap_dict1: dict[str, float] = {
            name: float(v)
            for name, v in zip(self._feature_names, shap_vals1)
        }
        base1 = float(self._expl1.expected_value)

        # ----------------------------------------------------------------
        # Model 2 inference — completely separate (SHAP-03)
        # ----------------------------------------------------------------
        prob2 = float(self._xgb2.predict_proba(X_row)[0, 1])
        shap_vals2: np.ndarray = self._expl2.shap_values(X_row)[0]  # shape (n_features,)
        shap_dict2: dict[str, float] = {
            name: float(v)
            for name, v in zip(self._feature_names, shap_vals2)
        }
        base2 = float(self._expl2.expected_value)

        return PredictionResult(
            model1_probability=prob1,
            model2_probability=prob2,
            model1_shap_values=shap_dict1,
            model2_shap_values=shap_dict2,
            model1_base_value=base1,
            model2_base_value=base2,
        )
