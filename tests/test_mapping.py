"""Tests for src/api/mapping_loader.py — MappingConfig loading and lookups.

Covers:
  - MappingConfig.load() from real YAML + JSON files
  - barrier_type display name lookups (known + fallback)
  - LoD display name lookups
  - PIF to degradation factor mapping (all 12 + specific)
  - barrier_condition display name lookups (Fidel-#59: known + fallback)
  - Risk level computation (High/Medium/Low from probability thresholds)
"""
from __future__ import annotations

import pytest

from src.api.mapping_loader import MappingConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mapping() -> MappingConfig:
    """Load MappingConfig once for the module (real YAML + JSON files)."""
    return MappingConfig.load()


# ---------------------------------------------------------------------------
# MappingConfig.load() smoke test
# ---------------------------------------------------------------------------

def test_mapping_config_loads_successfully(mapping: MappingConfig) -> None:
    """MappingConfig.load() returns a MappingConfig with non-empty dicts."""
    assert isinstance(mapping, MappingConfig)
    assert len(mapping.barrier_types) > 0
    assert len(mapping.lod_categories) > 0
    assert len(mapping.pif_to_degradation) > 0
    assert len(mapping.barrier_condition) > 0
    assert len(mapping.risk_thresholds) > 0


# ---------------------------------------------------------------------------
# Barrier type display
# ---------------------------------------------------------------------------

def test_barrier_type_display_administrative(mapping: MappingConfig) -> None:
    """get_barrier_type_display('administrative') returns display name."""
    assert mapping.get_barrier_type_display("administrative") == "Administrative / Procedural Barrier"


def test_barrier_type_display_unknown_value(mapping: MappingConfig) -> None:
    """get_barrier_type_display('nonexistent') falls back to raw value."""
    assert mapping.get_barrier_type_display("nonexistent") == "nonexistent"


# ---------------------------------------------------------------------------
# LoD display
# ---------------------------------------------------------------------------

def test_lod_display_1st(mapping: MappingConfig) -> None:
    """get_lod_display('1st') returns display name."""
    assert mapping.get_lod_display("1st") == "1st Line of Defense"


# ---------------------------------------------------------------------------
# PIF to degradation factor
# ---------------------------------------------------------------------------

_PIF_FIELDS = [
    "pif_competence",
    "pif_fatigue",
    "pif_communication",
    "pif_situational_awareness",
    "pif_procedures",
    "pif_workload",
    "pif_time_pressure",
    "pif_tools_equipment",
    "pif_safety_culture",
    "pif_management_of_change",
    "pif_supervision",
    "pif_training",
]


def test_pif_to_degradation_all_12(mapping: MappingConfig) -> None:
    """All 12 pif_* keys map to non-empty strings."""
    for pif in _PIF_FIELDS:
        display = mapping.get_degradation_factor(pif)
        assert isinstance(display, str)
        assert len(display) > 0, f"Empty display for {pif}"
        assert display != pif, f"No mapping found for {pif}"


def test_pif_to_degradation_fatigue(mapping: MappingConfig) -> None:
    """get_degradation_factor('pif_fatigue') returns 'Operator Fatigue'."""
    assert mapping.get_degradation_factor("pif_fatigue") == "Operator Fatigue"


# ---------------------------------------------------------------------------
# Barrier condition display (Fidel-#59)
# ---------------------------------------------------------------------------

def test_barrier_condition_display_worked(mapping: MappingConfig) -> None:
    """get_barrier_condition_display('worked') returns 'Barrier Performed'."""
    assert mapping.get_barrier_condition_display("worked") == "Barrier Performed"


def test_barrier_condition_display_failed(mapping: MappingConfig) -> None:
    """get_barrier_condition_display('failed') returns 'Barrier Failed'."""
    assert mapping.get_barrier_condition_display("failed") == "Barrier Failed"


def test_barrier_condition_display_degraded(mapping: MappingConfig) -> None:
    """get_barrier_condition_display('degraded') returns 'Barrier Degraded'."""
    assert mapping.get_barrier_condition_display("degraded") == "Barrier Degraded"


def test_barrier_condition_display_unknown_value(mapping: MappingConfig) -> None:
    """get_barrier_condition_display('nonexistent') falls back to raw value."""
    assert mapping.get_barrier_condition_display("nonexistent") == "nonexistent"


# ---------------------------------------------------------------------------
# Risk level computation
# ---------------------------------------------------------------------------

def test_risk_level_high(mapping: MappingConfig) -> None:
    """probability 0.95 (above p80=0.9358) returns 'High'."""
    assert mapping.compute_risk_level(0.95) == "High"


def test_risk_level_medium(mapping: MappingConfig) -> None:
    """probability 0.90 (between p60=0.8576 and p80=0.9358) returns 'Medium'."""
    assert mapping.compute_risk_level(0.90) == "Medium"


def test_risk_level_low(mapping: MappingConfig) -> None:
    """probability 0.50 (below p60=0.8576) returns 'Low'."""
    assert mapping.compute_risk_level(0.50) == "Low"
