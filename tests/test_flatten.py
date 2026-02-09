import json
import pytest
import tempfile
from pathlib import Path
from src.analytics.flatten import flatten_controls, flatten_all


def _make_incident(incident_id: str = "TEST-001", n_controls: int = 2) -> dict:
    """Build a minimal Schema v2.3 incident dict with controls."""
    controls = []
    for i in range(n_controls):
        controls.append({
            "control_id": f"C-{i+1:03d}",
            "name": f"Control {i+1}",
            "side": "prevention" if i % 2 == 0 else "mitigation",
            "barrier_role": "detect",
            "barrier_type": "engineering",
            "line_of_defense": "1st",
            "lod_basis": None,
            "linked_threat_ids": ["T-001"],
            "linked_consequence_ids": [],
            "performance": {
                "barrier_status": "active" if i == 0 else "failed",
                "barrier_failed": i != 0,
                "detection_applicable": True,
                "detection_mentioned": True,
                "alarm_applicable": False,
                "alarm_mentioned": False,
                "manual_intervention_applicable": False,
                "manual_intervention_mentioned": False,
            },
            "human": {
                "human_contribution_value": None,
                "human_contribution_mentioned": False,
                "barrier_failed_human": False,
                "linked_pif_ids": [],
            },
            "evidence": {
                "supporting_text": ["Evidence text"],
                "confidence": "medium",
            },
        })
    return {
        "incident_id": incident_id,
        "bowtie": {"hazards": [], "threats": [], "consequences": [], "controls": controls},
    }


class TestFlattenControls:
    def test_basic_flatten(self):
        incident = _make_incident(n_controls=2)
        rows = flatten_controls(incident)
        assert len(rows) == 2
        assert rows[0]["incident_id"] == "TEST-001"
        assert rows[0]["control_id"] == "C-001"
        assert rows[1]["control_id"] == "C-002"

    def test_linked_ids_comma_joined(self):
        incident = _make_incident(n_controls=1)
        incident["bowtie"]["controls"][0]["linked_threat_ids"] = ["T-001", "T-002"]
        rows = flatten_controls(incident)
        assert rows[0]["linked_threat_ids"] == "T-001,T-002"

    def test_supporting_text_count(self):
        incident = _make_incident(n_controls=1)
        incident["bowtie"]["controls"][0]["evidence"]["supporting_text"] = ["a", "b", "c"]
        rows = flatten_controls(incident)
        assert rows[0]["supporting_text_count"] == 3

    def test_no_controls(self):
        incident = {"incident_id": "EMPTY", "bowtie": {"controls": []}}
        rows = flatten_controls(incident)
        assert rows == []


class TestFlattenAll:
    def test_flatten_all_writes_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            struct_dir = Path(tmpdir) / "structured"
            struct_dir.mkdir()
            out_csv = Path(tmpdir) / "controls.csv"

            incident = _make_incident(n_controls=2)
            (struct_dir / "TEST-001.json").write_text(json.dumps(incident))

            n = flatten_all(struct_dir, out_csv)
            assert n == 2
            assert out_csv.exists()

            import csv
            with open(out_csv, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 2

    def test_flatten_all_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            struct_dir = Path(tmpdir) / "structured"
            struct_dir.mkdir()
            out_csv = Path(tmpdir) / "controls.csv"
            n = flatten_all(struct_dir, out_csv)
            assert n == 0

    def test_flatten_all_multiple_incidents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            struct_dir = Path(tmpdir) / "structured"
            struct_dir.mkdir()
            out_csv = Path(tmpdir) / "controls.csv"

            for i in range(3):
                inc = _make_incident(f"INC-{i:03d}", n_controls=1)
                (struct_dir / f"INC-{i:03d}.json").write_text(json.dumps(inc))

            n = flatten_all(struct_dir, out_csv)
            assert n == 3
