"""Tests for demo-scenario fixtures (R019 schema/constraint checks).

Bucket B tests (schema + R019 constraints) run against the 3 committed
fixtures in data/demo_scenarios/ — no gitignored data required.

Bucket C tests (builder behaviour: test_exactly_three_files,
test_one_file_per_agency) are preserved with function-level skipif gated
on flat_incidents_combined.csv.  See tech-debt.md 2026-05-03 entry.
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

_DEMO_SCENARIOS_DIR = pathlib.Path(__file__).parent.parent / "data" / "demo_scenarios"

# Reusable mark applied only to the two Bucket C tests.
_bucket_c_skip = pytest.mark.skipif(
    not FLAT_INCIDENTS_CSV.exists(),
    reason="flat_incidents_combined.csv not present (gitignored processed data); "
           "run `python -m src.pipeline build-combined-exports` first. "
           "See tech-debt.md 2026-05-03 entry.",
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
def scenarios() -> list[dict]:
    """Load the 3 committed demo scenario fixtures from data/demo_scenarios/."""
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(_DEMO_SCENARIOS_DIR.glob("*.json"))
    ]


@pytest.fixture(scope="module")
def scenario_files(tmp_path_factory: pytest.TempPathFactory) -> list[pathlib.Path]:
    """Regenerate fixtures via builder — used only by Bucket C tests."""
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

@_bucket_c_skip
def test_exactly_three_files(scenario_files: list[pathlib.Path]) -> None:
    assert len(scenario_files) == 3


@_bucket_c_skip
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
