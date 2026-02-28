"""Generate risk_thresholds.json from training prediction distribution.

Loads the feature matrix and both XGBoost models, runs model1 predictions over
all training rows, then computes 80th and 60th percentile cutoffs. These
thresholds are used by the frontend to map barrier failure probabilities to
red/amber/green risk levels.

Usage::

    python scripts/generate_risk_thresholds.py

Writes ``data/models/artifacts/risk_thresholds.json``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from src.modeling.feature_engineering import (
    ARTIFACTS_DIR,
    FEATURE_MATRIX_PATH,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_PATH = ARTIFACTS_DIR / "risk_thresholds.json"


def load_feature_matrix(path: Path) -> pd.DataFrame:
    """Load the feature matrix parquet file.

    Args:
        path: Path to the feature_matrix.parquet file.

    Returns:
        DataFrame with all rows from the feature matrix.

    Raises:
        FileNotFoundError: If the feature matrix file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Feature matrix not found at {path}. "
            "Run: python -m src.modeling.feature_engineering"
        )
    df = pd.read_parquet(path)
    logger.info("Loaded feature matrix: %d rows, %d columns", len(df), len(df.columns))
    return df


def load_model1(artifacts_dir: Path) -> xgb.XGBClassifier:
    """Load the XGBoost model1 (barrier failure prediction).

    Args:
        artifacts_dir: Directory containing xgb_model1.json.

    Returns:
        Loaded XGBClassifier instance.

    Raises:
        FileNotFoundError: If the model file does not exist.
    """
    model_path = artifacts_dir / "xgb_model1.json"
    if not model_path.exists():
        raise FileNotFoundError(
            f"XGBoost model1 not found at {model_path}. "
            "Run: python -m src.modeling.train"
        )
    model = xgb.XGBClassifier()
    model.load_model(str(model_path))
    logger.info("Loaded XGBoost model1 from %s", model_path)
    return model



def encode_and_predict(
    df: pd.DataFrame,
    model: xgb.XGBClassifier,
) -> np.ndarray:
    """Run model1 predictions on all rows of the feature matrix.

    The feature matrix already contains OrdinalEncoded integer values for
    categorical features (written by feature_engineering.py). We only need
    to drop metadata/label columns and pass the numeric array to predict_proba.

    Column order in the feature matrix (excluding metadata + labels) matches
    the training order: categoricals first, then PIFs, then numeric.

    Args:
        df: Feature matrix DataFrame (includes metadata and label columns).
        model: Loaded XGBClassifier (model1).

    Returns:
        1D array of model1 failure probabilities, one per row.
    """
    # Drop metadata and label columns — keep only model input features
    drop_cols = [
        c for c in [
            "incident_id", "control_id",
            "label_barrier_failed", "label_barrier_failed_human",
        ]
        if c in df.columns
    ]
    feature_df = df.drop(columns=drop_cols)
    logger.info("Using %d rows, %d features", len(feature_df), len(feature_df.columns))

    X: np.ndarray = feature_df.values.astype(float)
    logger.info("Feature matrix assembled: shape %s", X.shape)

    # Predict probabilities (column 1 = positive class probability)
    probabilities: np.ndarray = model.predict_proba(X)[:, 1]
    logger.info(
        "Predictions computed: min=%.4f, max=%.4f, mean=%.4f",
        probabilities.min(),
        probabilities.max(),
        probabilities.mean(),
    )
    return probabilities


def compute_thresholds(probabilities: np.ndarray) -> dict[str, object]:
    """Compute percentile cutoffs from the training prediction distribution.

    Args:
        probabilities: 1D array of model1 predictions over training data.

    Returns:
        Dict with p80, p60, total_predictions, and description fields.
    """
    p80 = float(np.percentile(probabilities, 80))
    p60 = float(np.percentile(probabilities, 60))
    total = int(len(probabilities))

    logger.info(
        "Thresholds: p60=%.4f, p80=%.4f (n=%d)", p60, p80, total
    )

    return {
        "p80": p80,
        "p60": p60,
        "total_predictions": total,
        "description": (
            "Percentile cutoffs from model1 training predictions. "
            "Top 20% (>=p80) = red, middle 40% (p60..p80) = amber, "
            "bottom 40% (<p60) = green."
        ),
    }


def write_thresholds(thresholds: dict[str, object], output_path: Path) -> None:
    """Write threshold dict to JSON file.

    Args:
        thresholds: Dict with p80, p60, total_predictions, description.
        output_path: Destination path for the JSON file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(thresholds, f, indent=2)
    logger.info("Written to %s", output_path)


def main() -> None:
    """Generate risk_thresholds.json from training predictions."""
    logger.info("=== generate_risk_thresholds.py ===")

    df = load_feature_matrix(FEATURE_MATRIX_PATH)
    model1 = load_model1(ARTIFACTS_DIR)

    probabilities = encode_and_predict(df, model1)
    thresholds = compute_thresholds(probabilities)
    write_thresholds(thresholds, OUTPUT_PATH)

    print(
        f"OK: p60={thresholds['p60']:.4f}, p80={thresholds['p80']:.4f}, "
        f"n={thresholds['total_predictions']}"
    )


if __name__ == "__main__":
    main()
