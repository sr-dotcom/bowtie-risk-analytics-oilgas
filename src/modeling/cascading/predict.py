"""Inference module for the cascading XGBoost barrier-failure model (S03/T01).

Exposes three public methods:
  CascadingPredictor.predict  — ranked predictions + SHAP for all non-conditioning barriers
  CascadingPredictor.rank     — ranked predictions without SHAP (lighter, for hover/preview)
  CascadingPredictor.explain  — SHAP for a single (conditioning, target) pair

D016 Branch C: y_hf_fail is NOT exposed on any public interface. The
xgb_cascade_y_fail_pipeline.joblib models y_fail only.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import joblib
import pandas as pd

from src.modeling.cascading.pair_builder import (
    BARRIER_FEATURES_COND,
    BARRIER_FEATURES_TARGET,
    CONTEXT_FEATURES,
)
from src.modeling.cascading.shap_probe import build_tree_explainer, compute_shap_for_record

# Re-export the constants so callers can reference the feature contract.
__all__ = [
    "CascadingPredictor",
    "load_cascading_predictor",
    "ShapEntry",
    "BarrierPrediction",
    "PredictionResult",
    "RankedBarrier",
    "RankingResult",
    "PairExplanationResult",
    "BARRIER_FEATURES_TARGET",
    "BARRIER_FEATURES_COND",
    "CONTEXT_FEATURES",
]

_THRESHOLDS_PATH = Path("configs/risk_thresholds.json")


# ---------------------------------------------------------------------------
# Public result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ShapEntry:
    """SHAP value for one feature in the cascading model."""
    feature: str
    value: float


@dataclass
class BarrierPrediction:
    """Prediction for one target barrier given a failed conditioning barrier."""
    target_barrier_id: str
    y_fail_probability: float
    risk_band: Literal["HIGH", "MEDIUM", "LOW"]
    shap_values: list[ShapEntry]


@dataclass
class PredictionResult:
    """Full prediction output: all non-conditioning barriers, sorted by risk."""
    predictions: list[BarrierPrediction]


@dataclass
class RankedBarrier:
    """Lightweight ranking entry (no SHAP) for fast preview."""
    target_barrier_id: str
    composite_risk_score: float


@dataclass
class RankingResult:
    """Lightweight ranking output for all non-conditioning barriers."""
    ranked_barriers: list[RankedBarrier]


@dataclass
class PairExplanationResult:
    """SHAP explanation for a single (conditioning, target) barrier pair."""
    target_barrier_id: str
    y_fail_probability: float
    shap_values: list[ShapEntry]


# ---------------------------------------------------------------------------
# Feature construction helpers
# ---------------------------------------------------------------------------

def _risk_band(probability: float, thresholds: dict[str, float]) -> Literal["HIGH", "MEDIUM", "LOW"]:
    """Map a probability to risk band using configs/risk_thresholds.json cutpoints."""
    if probability >= thresholds["p80"]:
        return "HIGH"
    elif probability >= thresholds["p60"]:
        return "MEDIUM"
    return "LOW"


def _flag_features_from_scenario(scenario: dict[str, Any]) -> dict[str, int]:
    """Derive binary flag features from scenario threat names and pif_context.

    Best-effort approximation for inference — the training flags came from
    full incident text; here we use threat descriptions and PIFs as proxies.
    """
    threats = scenario.get("threats", [])
    threat_text = " ".join(t.get("name", "").lower() for t in threats)
    pif = scenario.get("pif_context", {})
    work_pif = pif.get("work", {})

    return {
        "flag_environmental_threat": int(any(
            kw in threat_text for kw in ["environmental", "spill", "flood", "structural", "corrosion", "leak"]
        )),
        "flag_electrical_failure": int(any(
            kw in threat_text for kw in ["electrical", "ignition", "spark", "power", "fire"]
        )),
        "flag_procedural_error": int(
            bool(work_pif.get("procedures"))
            or any(kw in threat_text for kw in ["procedure", "operator error", "human"])
        ),
        "flag_mechanical_failure": int(
            bool(work_pif.get("tools_equipment"))
            or any(kw in threat_text for kw in ["mechanical", "equipment", "pump", "valve", "rupture", "pressure"])
        ),
    }


def _build_pair_features(
    conditioning: dict[str, Any],
    target: dict[str, Any],
    scenario: dict[str, Any],
) -> dict[str, Any]:
    """Build the 18-feature dict for a (conditioning, target) barrier pair.

    Feature contract mirrors the training pipeline's all_features list:
      cat (5): lod_industry_standard_{target,cond}, barrier_level_{target,cond}, barrier_condition_cond
      num (13): pathway_sequence_{target,cond}, lod_numeric_{target,cond},
                num_threats_in_lod_numeric_{target,cond}, total_prev_barriers_incident,
                total_mit_barriers_incident, num_threats_in_sequence, flag_* (4)

    barrier_condition_cond is forced to "ineffective" — the conditioning barrier
    is assumed to have already failed (training-time convention).
    """
    barriers = scenario.get("barriers", [])
    threats = scenario.get("threats", [])

    # Scenario-level statistics
    prev_count = sum(1 for b in barriers if b.get("barrier_level") == "prevention")
    mit_count = sum(1 for b in barriers if b.get("barrier_level") == "mitigation")

    # pathway_sequence: 0-based ordinal position in the barriers list
    barrier_ids = [b.get("control_id") for b in barriers]
    target_id = target.get("control_id")
    cond_id = conditioning.get("control_id")
    target_idx = barrier_ids.index(target_id) if target_id in barrier_ids else 0
    cond_idx = barrier_ids.index(cond_id) if cond_id in barrier_ids else 0

    # num_threats_in_lod_numeric: unique threats linked to all barriers at same lod_numeric
    target_lod = target.get("lod_numeric", 0)
    cond_lod = conditioning.get("lod_numeric", 0)
    target_lod_threats: set[str] = set()
    cond_lod_threats: set[str] = set()
    for b in barriers:
        if b.get("lod_numeric") == target_lod:
            target_lod_threats.update(b.get("linked_threat_ids", []))
        if b.get("lod_numeric") == cond_lod:
            cond_lod_threats.update(b.get("linked_threat_ids", []))

    flags = _flag_features_from_scenario(scenario)

    return {
        # Target features
        "lod_industry_standard_target": target.get("lod_industry_standard", ""),
        "barrier_level_target": target.get("barrier_level", ""),
        "pathway_sequence_target": target_idx,
        "lod_numeric_target": float(target_lod),
        "num_threats_in_lod_numeric_target": len(target_lod_threats),
        # Conditioning features — barrier_condition forced to "ineffective"
        "lod_industry_standard_cond": conditioning.get("lod_industry_standard", ""),
        "barrier_level_cond": conditioning.get("barrier_level", ""),
        "barrier_condition_cond": "ineffective",
        "pathway_sequence_cond": cond_idx,
        "lod_numeric_cond": float(cond_lod),
        "num_threats_in_lod_numeric_cond": len(cond_lod_threats),
        # Incident-level context
        "total_prev_barriers_incident": prev_count,
        "total_mit_barriers_incident": mit_count,
        "num_threats_in_sequence": len(threats),
        **flags,
    }


# ---------------------------------------------------------------------------
# Predictor
# ---------------------------------------------------------------------------

class CascadingPredictor:
    """Inference interface for the cascading XGBoost barrier-failure model."""

    def __init__(
        self,
        pipeline: Any,
        metadata: dict[str, Any],
        thresholds: dict[str, float],
    ) -> None:
        self._pipeline = pipeline
        self._metadata = metadata
        self._thresholds = thresholds
        self._all_features: list[str] = metadata["all_features"]
        self._explainer = build_tree_explainer(pipeline)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_barrier_by_id(self, scenario: dict[str, Any], barrier_id: str) -> dict[str, Any]:
        for b in scenario.get("barriers", []):
            if b.get("control_id") == barrier_id:
                return b
        raise ValueError(f"Barrier '{barrier_id}' not found in scenario")

    def _predict_proba(self, features: dict[str, Any]) -> float:
        row_df = pd.DataFrame([features])[self._all_features]
        return float(self._pipeline.predict_proba(row_df)[0, 1])

    def _shap_entries(self, features: dict[str, Any]) -> list[ShapEntry]:
        sv_1d, feat_names = compute_shap_for_record(
            self._pipeline, self._explainer, features, self._all_features
        )
        return [ShapEntry(feature=feat_names[i], value=float(sv_1d[i])) for i in range(len(feat_names))]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(self, scenario: dict[str, Any], conditioning_barrier_id: str) -> PredictionResult:
        """Predict barrier failure for all non-conditioning barriers, sorted by risk."""
        conditioning = self._get_barrier_by_id(scenario, conditioning_barrier_id)
        predictions: list[BarrierPrediction] = []

        for barrier in scenario.get("barriers", []):
            if barrier.get("control_id") == conditioning_barrier_id:
                continue
            features = _build_pair_features(conditioning, barrier, scenario)
            prob = self._predict_proba(features)
            shap_entries = self._shap_entries(features)
            predictions.append(BarrierPrediction(
                target_barrier_id=barrier["control_id"],
                y_fail_probability=prob,
                risk_band=_risk_band(prob, self._thresholds),
                shap_values=shap_entries,
            ))

        predictions.sort(key=lambda p: p.y_fail_probability, reverse=True)
        return PredictionResult(predictions=predictions)

    def rank(self, scenario: dict[str, Any], conditioning_barrier_id: str) -> RankingResult:
        """Rank all non-conditioning barriers by failure probability (no SHAP)."""
        conditioning = self._get_barrier_by_id(scenario, conditioning_barrier_id)
        ranked: list[RankedBarrier] = []

        for barrier in scenario.get("barriers", []):
            if barrier.get("control_id") == conditioning_barrier_id:
                continue
            features = _build_pair_features(conditioning, barrier, scenario)
            prob = self._predict_proba(features)
            ranked.append(RankedBarrier(
                target_barrier_id=barrier["control_id"],
                composite_risk_score=prob,
            ))

        ranked.sort(key=lambda r: r.composite_risk_score, reverse=True)
        return RankingResult(ranked_barriers=ranked)

    def explain(
        self,
        scenario: dict[str, Any],
        conditioning_barrier_id: str,
        target_barrier_id: str,
    ) -> PairExplanationResult:
        """Compute SHAP for a single (conditioning, target) barrier pair."""
        conditioning = self._get_barrier_by_id(scenario, conditioning_barrier_id)
        target = self._get_barrier_by_id(scenario, target_barrier_id)
        features = _build_pair_features(conditioning, target, scenario)
        prob = self._predict_proba(features)
        shap_entries = self._shap_entries(features)
        return PairExplanationResult(
            target_barrier_id=target_barrier_id,
            y_fail_probability=prob,
            shap_values=shap_entries,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def load_cascading_predictor(artifacts_dir: Path) -> CascadingPredictor:
    """Load CascadingPredictor from disk artifacts.

    Loads:
      {artifacts_dir}/xgb_cascade_y_fail_pipeline.joblib
      {artifacts_dir}/xgb_cascade_y_fail_metadata.json
      configs/risk_thresholds.json  (relative to CWD)
    """
    pipeline = joblib.load(artifacts_dir / "xgb_cascade_y_fail_pipeline.joblib")

    with open(artifacts_dir / "xgb_cascade_y_fail_metadata.json", encoding="utf-8") as f:
        metadata = json.load(f)

    with open(_THRESHOLDS_PATH, encoding="utf-8") as f:
        thresholds = json.load(f)

    return CascadingPredictor(pipeline=pipeline, metadata=metadata, thresholds=thresholds)
