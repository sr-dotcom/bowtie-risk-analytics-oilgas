"""Tests for src.modeling.profile — data reconnaissance profiler.

All tests are fully offline and use synthetic in-memory CSVs written to
tmp_path. No dependency on production data files.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.modeling.profile import PIF_MENTIONED_COLS, run_profile

# ---------------------------------------------------------------------------
# Helpers and fixtures
# ---------------------------------------------------------------------------

_CONTROLS_COLS = [
    "incident_id",
    "control_id",
    "name",
    "side",
    "barrier_role",
    "barrier_type",
    "line_of_defense",
    "lod_basis",
    "linked_threat_ids",
    "linked_consequence_ids",
    "barrier_status",
    "barrier_failed",
    "human_contribution_value",
    "barrier_failed_human",
    "confidence",
    "supporting_text_count",
    "source_agency",
    "provider_bucket",
    "json_path",
]

_INCIDENTS_EXTRA_COLS = [
    "source_agency",
    "provider_bucket",
    "incident__source__date_occurred",
    "incident__context__region",
    "incident__context__operator",
    "incident__event__top_event",
    "incident__event__incident_type",
    "incident__event__summary",
    "json_path",
]


def _make_test_csvs(tmp_path: Path) -> tuple[Path, Path]:
    """Create synthetic controls and incidents CSVs for testing.

    Controls (5 rows):
        INC-001 / C-001 — failed,   barrier_failed_human=True   → model1=1, model2=1
        INC-001 / C-002 — active,   barrier_failed_human=False  → model1=0, model2=0
        INC-002 / C-003 — degraded, barrier_failed_human=True   → model1=1, model2=1
        INC-002 / C-004 — bypassed, barrier_failed_human=False  → model1=1, model2=0
        INC-003 / C-005 — unknown,  barrier_failed_human=False  → excluded

    Training eligible: 4  (C-001..C-004)
    Model 1 positives: 3  (C-001, C-003, C-004)  → rate=0.75
    Model 2 positives: 2  (C-001, C-003)          → rate=0.50

    Incidents (3 rows) with all 12 PIF _mentioned columns set to varied values.
    """
    controls_rows = [
        {
            "incident_id": "INC-001", "control_id": "C-001", "name": "Valve Check",
            "side": "prevention", "barrier_role": "prevent", "barrier_type": "engineering",
            "line_of_defense": "1st", "lod_basis": "", "linked_threat_ids": "",
            "linked_consequence_ids": "", "barrier_status": "failed",
            "barrier_failed": True, "human_contribution_value": "direct",
            "barrier_failed_human": True, "confidence": "high",
            "supporting_text_count": 2, "source_agency": "BSEE",
            "provider_bucket": "bucket1", "json_path": "path1.json",
        },
        {
            "incident_id": "INC-001", "control_id": "C-002", "name": "Alarm System",
            "side": "mitigation", "barrier_role": "mitigate", "barrier_type": "engineering",
            "line_of_defense": "2nd", "lod_basis": "", "linked_threat_ids": "",
            "linked_consequence_ids": "", "barrier_status": "active",
            "barrier_failed": False, "human_contribution_value": "none",
            "barrier_failed_human": False, "confidence": "high",
            "supporting_text_count": 1, "source_agency": "BSEE",
            "provider_bucket": "bucket1", "json_path": "path1.json",
        },
        {
            "incident_id": "INC-002", "control_id": "C-003", "name": "Procedures",
            "side": "prevention", "barrier_role": "prevent", "barrier_type": "administrative",
            "line_of_defense": "1st", "lod_basis": "", "linked_threat_ids": "",
            "linked_consequence_ids": "", "barrier_status": "degraded",
            "barrier_failed": True, "human_contribution_value": "contributing",
            "barrier_failed_human": True, "confidence": "medium",
            "supporting_text_count": 1, "source_agency": "CSB",
            "provider_bucket": "bucket2", "json_path": "path2.json",
        },
        {
            "incident_id": "INC-002", "control_id": "C-004", "name": "Safety Valve",
            "side": "mitigation", "barrier_role": "mitigate", "barrier_type": "engineering",
            "line_of_defense": "1st", "lod_basis": "", "linked_threat_ids": "",
            "linked_consequence_ids": "", "barrier_status": "bypassed",
            "barrier_failed": True, "human_contribution_value": "direct",
            "barrier_failed_human": False, "confidence": "high",
            "supporting_text_count": 3, "source_agency": "CSB",
            "provider_bucket": "bucket2", "json_path": "path2.json",
        },
        {
            "incident_id": "INC-003", "control_id": "C-005", "name": "Inspection",
            "side": "prevention", "barrier_role": "prevent", "barrier_type": "administrative",
            "line_of_defense": "2nd", "lod_basis": "", "linked_threat_ids": "",
            "linked_consequence_ids": "", "barrier_status": "unknown",
            "barrier_failed": False, "human_contribution_value": "none",
            "barrier_failed_human": False, "confidence": "low",
            "supporting_text_count": 0, "source_agency": "BSEE",
            "provider_bucket": "bucket1", "json_path": "path3.json",
        },
    ]

    # Build incidents rows with all 12 PIF _mentioned columns
    # INC-001: 6 True, 6 False; INC-002: 8 True, 4 False; INC-003: all False
    pif_values_by_incident = {
        "INC-001": [True, False, True, False, True, False, True, False, True, False, True, False],
        "INC-002": [True, True, True, True, True, True, True, True, False, False, False, False],
        "INC-003": [False] * 12,
    }

    incident_rows = []
    for inc_id, pif_vals in pif_values_by_incident.items():
        row: dict = {"incident_id": inc_id}
        # Extra context columns
        for col in _INCIDENTS_EXTRA_COLS:
            row[col] = "test_value"
        # PIF mentioned columns
        for col, val in zip(PIF_MENTIONED_COLS, pif_vals):
            row[col] = val
        incident_rows.append(row)

    controls_df = pd.DataFrame(controls_rows)
    incidents_df = pd.DataFrame(incident_rows)

    controls_path = tmp_path / "controls.csv"
    incidents_path = tmp_path / "incidents.csv"

    controls_df.to_csv(controls_path, index=False)
    incidents_df.to_csv(incidents_path, index=False)

    return controls_path, incidents_path


@pytest.fixture
def profile_result(tmp_path: Path) -> tuple[dict, Path]:
    """Run profile with standard 5-row controls / 3-row incidents fixture.

    Returns (report_dict, out_path).
    """
    controls_path, incidents_path = _make_test_csvs(tmp_path)
    out_path = tmp_path / "report.json"
    report = run_profile(controls_path, incidents_path, out_path)
    return report, out_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_run_profile_produces_json(tmp_path: Path) -> None:
    """run_profile writes a JSON file at the specified output path."""
    controls_path, incidents_path = _make_test_csvs(tmp_path)
    out_path = tmp_path / "output.json"

    assert not out_path.exists(), "File should not exist before run"
    run_profile(controls_path, incidents_path, out_path)
    assert out_path.exists(), "JSON artifact was not created"


def test_report_has_required_keys(profile_result: tuple) -> None:
    """JSON artifact contains all required top-level keys."""
    report, out_path = profile_result
    required_keys = {
        "schema_version",
        "generated_at",
        "controls",
        "incidents",
        "join_check",
        "labels",
        "pif_report",
    }
    assert set(report.keys()) >= required_keys, (
        f"Missing keys: {required_keys - set(report.keys())}"
    )


def test_label_derivation_excludes_unknowns(profile_result: tuple) -> None:
    """Controls with barrier_status='unknown' are excluded from label counts."""
    report, _ = profile_result
    # 5 total controls, 1 with barrier_status=unknown → 4 training eligible
    assert report["labels"]["model1"]["n_total"] == 4, (
        f"Expected n_total=4, got {report['labels']['model1']['n_total']}"
    )


def test_label_derivation_model1(profile_result: tuple) -> None:
    """Model 1 positive count matches expected value for synthetic data.

    C-001 (failed), C-003 (degraded), C-004 (bypassed) → 3 positives out of 4 eligible.
    """
    report, _ = profile_result
    m1 = report["labels"]["model1"]
    assert m1["n_positive"] == 3, f"Expected n_positive=3, got {m1['n_positive']}"
    assert abs(m1["positive_rate"] - 0.75) < 1e-4, (
        f"Expected positive_rate≈0.75, got {m1['positive_rate']}"
    )


def test_label_derivation_model2(profile_result: tuple) -> None:
    """Model 2 requires both did_not_perform AND barrier_failed_human==True.

    C-001 (failed, hf=True) and C-003 (degraded, hf=True) → 2 positives.
    C-004 (bypassed) is excluded because barrier_failed_human=False.
    """
    report, _ = profile_result
    m2 = report["labels"]["model2"]
    assert m2["n_positive"] == 2, f"Expected n_positive=2, got {m2['n_positive']}"


def test_warning_flag_above_threshold(profile_result: tuple) -> None:
    """When positive rate > 0.25, warnings list is non-empty.

    Synthetic data has rate=0.75 for Model 1 — well above 0.25 threshold.
    """
    report, _ = profile_result
    warnings = report["labels"]["model1"]["warnings"]
    assert len(warnings) >= 1, "Expected at least one warning when rate=0.75 > 0.25"
    assert any("exceeds upper threshold" in w for w in warnings), (
        f"Expected 'exceeds upper threshold' in warnings: {warnings}"
    )


def test_warning_flag_below_threshold(tmp_path: Path) -> None:
    """When positive rate < 0.03, warnings list is non-empty."""
    # Build 100-row controls where only 1 is positive (rate=0.01 < 0.03)
    rows = []
    for i in range(99):
        rows.append({
            "incident_id": f"INC-{i:03d}", "control_id": f"C-{i:03d}",
            "name": "Safe Barrier", "side": "prevention", "barrier_role": "prevent",
            "barrier_type": "engineering", "line_of_defense": "1st", "lod_basis": "",
            "linked_threat_ids": "", "linked_consequence_ids": "",
            "barrier_status": "active", "barrier_failed": False,
            "human_contribution_value": "none", "barrier_failed_human": False,
            "confidence": "high", "supporting_text_count": 1,
            "source_agency": "CSB", "provider_bucket": "b1", "json_path": "p.json",
        })
    # One positive row
    rows.append({
        "incident_id": "INC-100", "control_id": "C-100",
        "name": "Failed Barrier", "side": "prevention", "barrier_role": "prevent",
        "barrier_type": "engineering", "line_of_defense": "1st", "lod_basis": "",
        "linked_threat_ids": "", "linked_consequence_ids": "",
        "barrier_status": "failed", "barrier_failed": True,
        "human_contribution_value": "direct", "barrier_failed_human": True,
        "confidence": "high", "supporting_text_count": 2,
        "source_agency": "CSB", "provider_bucket": "b1", "json_path": "p.json",
    })

    controls_path = tmp_path / "controls_sparse.csv"
    incidents_path = tmp_path / "incidents_sparse.csv"
    out_path = tmp_path / "report_sparse.json"

    pd.DataFrame(rows).to_csv(controls_path, index=False)

    # Minimal incidents with all PIF columns set to False
    incident_ids = list({r["incident_id"] for r in rows})
    inc_rows = []
    for inc_id in incident_ids:
        row: dict = {"incident_id": inc_id}
        for col in PIF_MENTIONED_COLS:
            row[col] = False
        inc_rows.append(row)
    pd.DataFrame(inc_rows).to_csv(incidents_path, index=False)

    report = run_profile(controls_path, incidents_path, out_path)
    warnings = report["labels"]["model1"]["warnings"]
    assert len(warnings) >= 1, "Expected at least one warning when rate=0.01 < 0.03"
    assert any("below lower threshold" in w for w in warnings), (
        f"Expected 'below lower threshold' in warnings: {warnings}"
    )


def test_pif_report_has_12_entries(profile_result: tuple) -> None:
    """pif_report dict has exactly 12 keys — one per PIF _mentioned dimension."""
    report, _ = profile_result
    assert len(report["pif_report"]) == 12, (
        f"Expected 12 PIF entries, got {len(report['pif_report'])}"
    )


def test_pif_report_has_correlation_fields(profile_result: tuple) -> None:
    """Each PIF entry has sparsity, corr_model1, corr_model2 and they are floats."""
    report, _ = profile_result
    for short_name, entry in report["pif_report"].items():
        assert "sparsity" in entry, f"Missing 'sparsity' for {short_name}"
        assert "corr_model1" in entry, f"Missing 'corr_model1' for {short_name}"
        assert "corr_model2" in entry, f"Missing 'corr_model2' for {short_name}"
        assert isinstance(entry["sparsity"], float), (
            f"sparsity for {short_name} is {type(entry['sparsity'])}, expected float"
        )
        assert isinstance(entry["corr_model1"], float), (
            f"corr_model1 for {short_name} is {type(entry['corr_model1'])}, expected float"
        )
        assert isinstance(entry["corr_model2"], float), (
            f"corr_model2 for {short_name} is {type(entry['corr_model2'])}, expected float"
        )


def test_json_roundtrip_no_type_error(profile_result: tuple) -> None:
    """JSON artifact can be round-tripped through json.loads without TypeError.

    Confirms all values are JSON-native types (no numpy scalars left in report).
    """
    _, out_path = profile_result
    raw_text = out_path.read_text(encoding="utf-8")
    loaded = json.loads(raw_text)
    # Re-serialise — proves all values are JSON-serialisable without custom encoder
    re_serialised = json.dumps(loaded)
    assert len(re_serialised) > 0
    # Round-trip back to dict
    final = json.loads(re_serialised)
    assert "schema_version" in final
