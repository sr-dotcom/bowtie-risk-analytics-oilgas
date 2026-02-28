"""Process safety terminology mapping loader.

Loads YAML mapping files at API startup and provides frozen config.
Pattern follows src/llm/model_policy.py — YAML + frozen dataclass.

Mappings translate internal encoder values and feature names to
process-safety-standard terminology for API responses and frontend display.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class MappingConfig:
    """Frozen configuration holding all process safety terminology mappings.

    Loaded once at API startup via ``MappingConfig.load()`` and stored on
    ``app.state.mapping_config``.  Provides lookup helpers that fall back
    to the raw value when a key is not found in the mapping.
    """

    barrier_types: dict[str, dict[str, str]]
    lod_categories: dict[str, dict[str, str]]
    pif_to_degradation: dict[str, str]
    barrier_condition: dict[str, dict[str, str]]
    risk_thresholds: dict[str, float]

    @staticmethod
    def load(
        mappings_dir: str | Path = "configs/mappings",
        thresholds_path: str | Path = "data/models/artifacts/risk_thresholds.json",
    ) -> MappingConfig:
        """Load all mapping configs from YAML files and risk thresholds JSON.

        Args:
            mappings_dir: Directory containing barrier_types.yaml,
                lod_categories.yaml, pif_to_degradation.yaml,
                barrier_condition.yaml.
            thresholds_path: Path to risk_thresholds.json for H/M/L computation.

        Returns:
            Frozen MappingConfig instance.

        Raises:
            FileNotFoundError: If any YAML or JSON file is missing.
        """
        p = Path(mappings_dir)
        bt = yaml.safe_load((p / "barrier_types.yaml").read_text(encoding="utf-8"))
        lod = yaml.safe_load((p / "lod_categories.yaml").read_text(encoding="utf-8"))
        pif = yaml.safe_load((p / "pif_to_degradation.yaml").read_text(encoding="utf-8"))
        bc = yaml.safe_load((p / "barrier_condition.yaml").read_text(encoding="utf-8"))

        t = Path(thresholds_path)
        thresholds = json.loads(t.read_text(encoding="utf-8"))

        return MappingConfig(
            barrier_types=bt.get("barrier_types", {}),
            lod_categories=lod.get("lod_categories", {}),
            pif_to_degradation=pif.get("pif_to_degradation", {}),
            barrier_condition=bc.get("barrier_condition", {}),
            risk_thresholds={"p80": thresholds["p80"], "p60": thresholds["p60"]},
        )

    def get_barrier_type_display(self, encoder_value: str) -> str:
        """Map barrier_type encoder value to process safety display name.

        Args:
            encoder_value: Raw encoder value (e.g. ``"administrative"``).

        Returns:
            Display name, or the raw value if not mapped.
        """
        entry = self.barrier_types.get(encoder_value)
        return entry["display_name"] if entry else encoder_value

    def get_lod_display(self, encoder_value: str) -> str:
        """Map line_of_defense encoder value to process safety display name.

        Args:
            encoder_value: Raw encoder value (e.g. ``"1st"``).

        Returns:
            Display name, or the raw value if not mapped.
        """
        entry = self.lod_categories.get(encoder_value)
        return entry["display_name"] if entry else encoder_value

    def get_degradation_factor(self, pif_field: str) -> str:
        """Map a pif_* feature name to a degradation factor display name.

        Args:
            pif_field: Internal feature name (e.g. ``"pif_fatigue"``).

        Returns:
            Degradation factor name, or the raw field name if not mapped.
        """
        return self.pif_to_degradation.get(pif_field, pif_field)

    def get_barrier_condition_display(self, barrier_status: str) -> str:
        """Map barrier_status to process safety condition characterization (Fidel-#59).

        Args:
            barrier_status: Internal status value (worked/failed/degraded/etc.).

        Returns:
            Process safety display name, or the raw value if not mapped.
        """
        entry = self.barrier_condition.get(barrier_status)
        return entry["display_name"] if entry else barrier_status

    def compute_risk_level(self, probability: float) -> str:
        """Compute High/Medium/Low risk level from model probability.

        Uses p80 and p60 percentile thresholds from risk_thresholds.json:
        - probability >= p80 -> "High"
        - probability >= p60 -> "Medium"
        - otherwise          -> "Low"

        Args:
            probability: Model 1 barrier failure probability (0.0 to 1.0).

        Returns:
            One of ``"High"``, ``"Medium"``, ``"Low"``.
        """
        if probability >= self.risk_thresholds["p80"]:
            return "High"
        if probability >= self.risk_thresholds["p60"]:
            return "Medium"
        return "Low"
