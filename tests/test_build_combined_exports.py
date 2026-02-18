"""Tests for combined aggregation exports. All offline, inline fixtures."""
import csv
import json
import logging
from pathlib import Path

import pytest

# ── Inline V2.3 fixtures ─────────────────────────────────────────────────────

FIXTURE_CSB = {
    "incident_id": "CSB-2024-001",
    "source": {
        "agency": "CSB",
        "doc_type": "investigation_report",
        "url": "https://csb.gov/report",
        "title": "Refinery Fire",
        "date_published": "2024-06-01",
        "date_occurred": "2024-01-15",
    },
    "context": {"region": "Texas", "operator": "Acme Corp"},
    "event": {
        "top_event": "Loss of Containment",
        "incident_type": "fire",
        "summary": "A fire broke out at the refinery.",
    },
    "bowtie": {
        "controls": [
            {
                "control_id": "CB_1",
                "name": "Pressure Relief Valve",
                "side": "left",
                "barrier_role": "prevent",
                "barrier_type": "engineering",
                "line_of_defense": 1,
                "lod_basis": "design",
                "linked_threat_ids": ["TH_1"],
                "linked_consequence_ids": [],
                "performance": {"barrier_status": "failed", "barrier_failed": True},
                "human": {
                    "human_contribution_value": "none",
                    "barrier_failed_human": False,
                },
                "evidence": {"confidence": "high", "supporting_text": ["text1"]},
            }
        ],
    },
    "pifs": {},
    "notes": {"schema_version": "2.3"},
}

FIXTURE_PHMSA = {
    "incident_id": "PHMSA-RPT-001",
    "source": {
        "agency": "PHMSA",
        "date_occurred": "2024-03-20",
    },
    "context": {"region": "Oklahoma", "operator": "PipeCo"},
    "event": {
        "top_event": "Not Found",
        "incident_type": "Not Found",
        "summary": "Pipeline incident reported via PHMSA bulk data.",
    },
    "bowtie": {"controls": []},
    "pifs": {},
    "notes": {},
}

FIXTURE_NO_AGENCY = {
    "incident_id": "UNKNOWN-001",
    "source": {"url": "https://example.com"},
    "context": {},
    "event": {
        "top_event": "Explosion",
        "incident_type": "explosion",
        "summary": "An explosion.",
    },
    "bowtie": {"controls": []},
    "pifs": {},
    "notes": {},
}


def _write_fixture(base_dir: Path, subdir: str, filename: str, data: dict) -> Path:
    """Write a JSON fixture to base_dir/subdir/filename."""
    d = base_dir / subdir
    d.mkdir(parents=True, exist_ok=True)
    p = d / filename
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestFlatIncidentsCombined:
    def test_correct_columns_and_rows(self, tmp_path: Path) -> None:
        from src.analytics.build_combined_exports import build_flat_incidents

        incidents_dir = tmp_path / "incidents"
        _write_fixture(incidents_dir, "csb", "CSB-2024-001.json", FIXTURE_CSB)
        _write_fixture(incidents_dir, "phmsa", "PHMSA-RPT-001.json", FIXTURE_PHMSA)

        out_path = tmp_path / "flat.csv"
        count = build_flat_incidents(incidents_dir, out_path)

        assert count == 2
        with open(out_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert "incident__event__top_event" in reader.fieldnames
        assert "incident__event__incident_type" in reader.fieldnames
        assert "incident__event__summary" in reader.fieldnames
        assert "source_agency" in reader.fieldnames
        assert "provider_bucket" in reader.fieldnames
        assert "json_path" in reader.fieldnames

    def test_source_agency_from_json_field(self, tmp_path: Path) -> None:
        from src.analytics.build_combined_exports import build_flat_incidents

        incidents_dir = tmp_path / "incidents"
        _write_fixture(incidents_dir, "csb", "CSB-2024-001.json", FIXTURE_CSB)
        out_path = tmp_path / "flat.csv"
        build_flat_incidents(incidents_dir, out_path)

        with open(out_path, "r") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["source_agency"] == "CSB"


class TestControlsCombined:
    def test_has_source_agency_and_json_path(self, tmp_path: Path) -> None:
        from src.analytics.build_combined_exports import build_controls_combined

        incidents_dir = tmp_path / "incidents"
        _write_fixture(incidents_dir, "csb", "CSB-2024-001.json", FIXTURE_CSB)

        out_path = tmp_path / "controls.csv"
        count = build_controls_combined(incidents_dir, out_path)

        assert count == 1
        with open(out_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert "source_agency" in reader.fieldnames
        assert "provider_bucket" in reader.fieldnames
        assert "json_path" in reader.fieldnames
        assert rows[0]["source_agency"] == "CSB"
        assert rows[0]["provider_bucket"] == "csb"


class TestSourceAgencyPriority:
    def test_json_field_wins(self) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        data = {"source": {"agency": "CSB"}}
        assert resolve_source_agency(data, "some_dir") == "CSB"

    def test_dir_name_fallback(self) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        data = {"source": {"url": "https://example.com"}}
        assert resolve_source_agency(data, "phmsa") == "PHMSA"

    def test_unknown_fallback(self) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        data = {}
        assert resolve_source_agency(data, "") == "UNKNOWN"

    def test_path_segment_wins(self) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        # known source buried under provider/format subdirs — scanned from path
        data = {}
        assert resolve_source_agency(
            data, "data/structured/incidents/bsee/openai/BSEE-001.json"
        ) == "BSEE"

    def test_non_source_path_gives_unknown(self) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        # no known source segment — provider/format dirs must NOT become agency
        data = {}
        assert resolve_source_agency(
            data, "data/structured/incidents/anthropic/schema_v2_3/INC-001.json"
        ) == "UNKNOWN"


class TestDocTypeAndUrlInference:
    """Verify doc_type keyword inference and URL-domain fallback."""

    def test_bsee_explicit_prefix(self) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        data = {"source": {"doc_type": "BSEE Accident Investigation Report"}}
        assert resolve_source_agency(data, "") == "BSEE"

    def test_bsee_accident_investigation_generic(self) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        # Uppercase variant used by gemini/openai extractions
        data = {"source": {"doc_type": "ACCIDENT INVESTIGATION REPORT"}}
        assert resolve_source_agency(data, "") == "BSEE"

    def test_csb_explicit_prefix(self) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        data = {"source": {"doc_type": "CSB Investigation Report"}}
        assert resolve_source_agency(data, "") == "CSB"

    def test_csb_recommendation_status_change(self) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        data = {"source": {"doc_type": "Investigation Report Recommendation Status Change"}}
        assert resolve_source_agency(data, "") == "CSB"

    def test_document_type_v23_field(self) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        # V2.3 canary files use document_type instead of doc_type
        data = {"source": {"document_type": "BSEE Accident Investigation Report"}}
        assert resolve_source_agency(data, "") == "BSEE"

    def test_url_csb_gov(self) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        data = {"source": {"url": "https://www.csb.gov/reports/123"}}
        assert resolve_source_agency(data, "") == "CSB"

    def test_url_bsee_gov(self) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        data = {"source": {"url": "https://www.bsee.gov/incident/456"}}
        assert resolve_source_agency(data, "") == "BSEE"

    def test_agency_field_beats_doc_type(self) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        # Explicit agency field takes priority over doc_type inference
        data = {"source": {"agency": "TSB", "doc_type": "BSEE Accident Investigation Report"}}
        assert resolve_source_agency(data, "") == "TSB"

    def test_ambiguous_doc_type_gives_unknown(self) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        # Generic / stub doc_types must NOT produce a false positive
        for dt in ("investigation_report", "report", "unknown", "incident report"):
            data = {"source": {"doc_type": dt}}
            result = resolve_source_agency(data, "")
            assert result == "UNKNOWN", f"Expected UNKNOWN for doc_type={dt!r}, got {result!r}"


class TestMalformedJsonSkipped:
    def test_corrupt_json_skipped(self, tmp_path: Path, caplog) -> None:
        from src.analytics.build_combined_exports import build_flat_incidents

        incidents_dir = tmp_path / "incidents"
        _write_fixture(incidents_dir, "csb", "CSB-2024-001.json", FIXTURE_CSB)
        bad_path = incidents_dir / "csb" / "BAD.json"
        bad_path.write_text("{invalid json", encoding="utf-8")

        out_path = tmp_path / "flat.csv"
        with caplog.at_level(logging.WARNING):
            count = build_flat_incidents(incidents_dir, out_path)

        assert count == 1
        assert "BAD.json" in caplog.text


class TestEmptyDir:
    def test_empty_produces_header_only(self, tmp_path: Path) -> None:
        from src.analytics.build_combined_exports import build_flat_incidents

        incidents_dir = tmp_path / "incidents"
        incidents_dir.mkdir()
        out_path = tmp_path / "flat.csv"
        count = build_flat_incidents(incidents_dir, out_path)

        assert count == 0
        assert out_path.exists()
        with open(out_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 0
        assert "incident_id" in reader.fieldnames
