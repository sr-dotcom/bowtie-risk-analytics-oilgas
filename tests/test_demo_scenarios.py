"""Tests for demo-scenario fixture generation (T02).

Regenerates fixtures into a tmp dir from real CSV/JSON sources and asserts
R019 constraints plus structural shape requirements from the S01→S05 boundary spec.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from scripts.build_demo_scenarios import (
    BASE_V3_CSV,
    FLAT_INCIDENTS_CSV,
    INCIDENTS_DIR,
    build_demo_scenarios,
)

REQUIRED_TOP_LEVEL_KEYS = {
    "scenario_id",
    "source_agency",
    "incident_id",
    "top_event",
    "context",
    "barriers",
    "threats",
    "pif_context",
}
REQUIRED_CONTEXT_KEYS = {"region", "operator", "operating_phase", "materials"}
REQUIRED_BARRIER_KEYS = {
    "control_id",
    "name",
    "barrier_level",
    "lod_industry_standard",
    "lod_numeric",
    "barrier_condition",
    "barrier_type",
    "barrier_role",
    "linked_threat_ids",
    "description",
    "line_of_defense",
}


@pytest.fixture(scope="module")
def scenarios(tmp_path_factory: pytest.TempPathFactory) -> list[dict]:
    """Regenerate all 3 fixtures into a temp dir and return parsed JSON dicts."""
    out = tmp_path_factory.mktemp("demo_scenarios")
    written = build_demo_scenarios(
        base_v3_path=BASE_V3_CSV,
        flat_incidents_path=FLAT_INCIDENTS_CSV,
        incidents_dir=INCIDENTS_DIR,
        out_dir=out,
    )
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(written)]


@pytest.fixture(scope="module")
def scenario_files(tmp_path_factory: pytest.TempPathFactory) -> list[pathlib.Path]:
    """Return written file paths for file-level checks."""
    out = tmp_path_factory.mktemp("demo_scenarios_files")
    return sorted(
        build_demo_scenarios(
            base_v3_path=BASE_V3_CSV,
            flat_incidents_path=FLAT_INCIDENTS_CSV,
            incidents_dir=INCIDENTS_DIR,
            out_dir=out,
        )
    )


# ── File-level ────────────────────────────────────────────────────────────────

def test_exactly_three_files(scenario_files: list[pathlib.Path]) -> None:
    assert len(scenario_files) == 3


def test_one_file_per_agency(scenarios: list[dict]) -> None:
    agencies = sorted(s["source_agency"] for s in scenarios)
    assert agencies == ["BSEE", "CSB", "UNKNOWN"]


def test_scenario_ids_unique(scenarios: list[dict]) -> None:
    ids = [s["scenario_id"] for s in scenarios]
    assert len(ids) == len(set(ids)), f"Duplicate scenario_id found: {ids}"


# ── Top-level shape ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("key", sorted(REQUIRED_TOP_LEVEL_KEYS))
def test_required_top_level_keys(scenarios: list[dict], key: str) -> None:
    for s in scenarios:
        assert key in s, f"Missing key '{key}' in scenario {s.get('scenario_id')}"


def test_context_is_object_with_required_keys(scenarios: list[dict]) -> None:
    for s in scenarios:
        ctx = s["context"]
        assert isinstance(ctx, dict)
        for k in REQUIRED_CONTEXT_KEYS:
            assert k in ctx, f"Missing context key '{k}' in {s['scenario_id']}"


def test_pif_context_is_object(scenarios: list[dict]) -> None:
    for s in scenarios:
        assert isinstance(s["pif_context"], dict), f"pif_context not a dict in {s['scenario_id']}"


def test_barriers_is_list(scenarios: list[dict]) -> None:
    for s in scenarios:
        assert isinstance(s["barriers"], list)


def test_threats_is_list(scenarios: list[dict]) -> None:
    for s in scenarios:
        assert isinstance(s["threats"], list)


# ── R019 barrier constraints ──────────────────────────────────────────────────

def test_at_least_four_barriers(scenarios: list[dict]) -> None:
    for s in scenarios:
        n = len(s["barriers"])
        assert n >= 4, f"{s['scenario_id']} has only {n} barriers, need ≥4"


def test_prevention_barriers_present(scenarios: list[dict]) -> None:
    for s in scenarios:
        levels = {b["barrier_level"] for b in s["barriers"]}
        assert "prevention" in levels, f"{s['scenario_id']} missing prevention barriers"


def test_mitigation_barriers_present(scenarios: list[dict]) -> None:
    for s in scenarios:
        levels = {b["barrier_level"] for b in s["barriers"]}
        assert "mitigation" in levels, f"{s['scenario_id']} missing mitigation barriers"


def test_no_other_lod_industry_standard(scenarios: list[dict]) -> None:
    for s in scenarios:
        for b in s["barriers"]:
            assert b["lod_industry_standard"] != "Other", (
                f"{s['scenario_id']} barrier {b['control_id']} has lod_industry_standard='Other'"
            )


def test_no_lod_numeric_99(scenarios: list[dict]) -> None:
    for s in scenarios:
        for b in s["barriers"]:
            assert b["lod_numeric"] != 99, (
                f"{s['scenario_id']} barrier {b['control_id']} has lod_numeric=99"
            )


def test_lod_fields_nonnull_on_every_barrier(scenarios: list[dict]) -> None:
    """Proves base_v3 lookup populated LoD fields (not synthesized/null)."""
    for s in scenarios:
        for b in s["barriers"]:
            assert b["lod_industry_standard"] is not None, (
                f"{s['scenario_id']} barrier {b['control_id']} has null lod_industry_standard"
            )
            assert b["lod_numeric"] is not None, (
                f"{s['scenario_id']} barrier {b['control_id']} has null lod_numeric"
            )


# ── Barrier shape ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("key", sorted(REQUIRED_BARRIER_KEYS))
def test_barrier_required_keys(scenarios: list[dict], key: str) -> None:
    for s in scenarios:
        for b in s["barriers"]:
            assert key in b, (
                f"Barrier {b.get('control_id')} in {s['scenario_id']} missing key '{key}'"
            )


def test_barrier_level_values(scenarios: list[dict]) -> None:
    valid = {"prevention", "mitigation"}
    for s in scenarios:
        for b in s["barriers"]:
            assert b["barrier_level"] in valid, (
                f"Invalid barrier_level '{b['barrier_level']}' in {s['scenario_id']}"
            )


def test_linked_threat_ids_is_list(scenarios: list[dict]) -> None:
    for s in scenarios:
        for b in s["barriers"]:
            assert isinstance(b["linked_threat_ids"], list)
