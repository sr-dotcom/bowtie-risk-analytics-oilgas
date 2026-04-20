import pytest
from src.rag.corpus_builder import assign_barrier_family, compose_barrier_text
from scripts.association_mining.event_barrier_normalization import (
    normalize_control_name,
    normalize_for_family,
    _match_family,
    _QUADRANT_DISPATCH,
    PREVENTION_ADMIN_FAMILIES,
    PREVENTION_ENGINEERING_FAMILIES,
    MITIGATION_ADMIN_FAMILIES,
    MITIGATION_ENGINEERING_FAMILIES,
)


class TestBarrierFamilyNormalization:
    """Verify normalization functions from event_barrier_normalization.py
    are importable and produce expected results for RAG corpus building."""

    def test_normalize_control_name_basic(self):
        result = normalize_control_name("PTW - Permit to Work")
        assert "permit to work" in result
        assert "ptw" not in result  # expanded

    def test_normalize_for_family_combines(self):
        result = normalize_for_family("ESD Valve procedure for shutdown")
        assert "emergency shutdown" in result  # esd expanded

    def test_prevention_admin_training(self):
        text = normalize_for_family("safety training program for operators")
        family = _match_family(text, PREVENTION_ADMIN_FAMILIES, "other_admin")
        assert family == "training"

    def test_prevention_eng_pressure_relief(self):
        text = normalize_for_family("pressure safety valve psv on wellhead")
        family = _match_family(text, PREVENTION_ENGINEERING_FAMILIES, "other_engineering")
        assert family == "overpressurization_gas_discharge_gas_isolation"

    def test_mitigation_admin_evacuation(self):
        text = normalize_for_family("muster point evacuation procedure")
        family = _match_family(text, MITIGATION_ADMIN_FAMILIES, "other_admin")
        assert family == "evacuation_muster_shelter_exclusion_access_control"

    def test_mitigation_eng_fire_protection(self):
        text = normalize_for_family("deluge fire suppression system")
        family = _match_family(text, MITIGATION_ENGINEERING_FAMILIES, "other_engineering")
        assert family == "active_fire_protection_firefighting"

    def test_quadrant_dispatch_keys(self):
        assert ("prevention", "administrative") in _QUADRANT_DISPATCH
        assert ("prevention", "engineering") in _QUADRANT_DISPATCH
        assert ("mitigation", "administrative") in _QUADRANT_DISPATCH
        assert ("mitigation", "engineering") in _QUADRANT_DISPATCH

    def test_ppe_fallback(self):
        # ppe has no quadrant taxonomy, should get other_ppe
        dispatch_key = ("prevention", "ppe")
        assert dispatch_key not in _QUADRANT_DISPATCH

    def test_unknown_text_gets_other(self):
        text = normalize_for_family("completely unrelated concept xyz")
        family = _match_family(text, PREVENTION_ADMIN_FAMILIES, "other_admin")
        assert family == "other_admin"


class TestAssignBarrierFamily:
    def test_prevention_admin(self):
        result = assign_barrier_family(
            name="Safety Training Program",
            barrier_role="Train operators on procedures",
            side="prevention",
            barrier_type="administrative",
        )
        assert result == "training"

    def test_prevention_engineering(self):
        result = assign_barrier_family(
            name="Pressure Safety Valve",
            barrier_role="Prevent overpressure",
            side="prevention",
            barrier_type="engineering",
        )
        assert result == "overpressurization_gas_discharge_gas_isolation"

    def test_mitigation_engineering(self):
        result = assign_barrier_family(
            name="Deluge System",
            barrier_role="Suppress fire",
            side="mitigation",
            barrier_type="engineering",
        )
        assert result == "active_fire_protection_firefighting"

    def test_ppe_gets_other_ppe(self):
        result = assign_barrier_family(
            name="Hard Hat",
            barrier_role="Protect head",
            side="prevention",
            barrier_type="ppe",
        )
        assert result == "other_ppe"

    def test_unknown_type_gets_other_unknown(self):
        result = assign_barrier_family(
            name="Mystery Barrier",
            barrier_role="Unknown role",
            side="prevention",
            barrier_type="unknown",
        )
        assert result == "other_unknown"


class TestComposeBarrierText:
    def test_all_fields_present(self):
        result = compose_barrier_text(
            name="ESD Valve",
            barrier_role="Emergency isolation",
            lod_basis="First line automated shutdown",
        )
        assert result == (
            "Barrier: ESD Valve\n"
            "Role: Emergency isolation\n"
            "LOD Basis: First line automated shutdown"
        )

    def test_missing_lod_basis(self):
        result = compose_barrier_text(
            name="ESD Valve",
            barrier_role="Emergency isolation",
            lod_basis=None,
        )
        assert result == (
            "Barrier: ESD Valve\n"
            "Role: Emergency isolation\n"
            "LOD Basis: N/A"
        )

    def test_empty_strings(self):
        result = compose_barrier_text(name="", barrier_role="", lod_basis="")
        assert "Barrier: " in result
        assert "Role: " in result
        assert "LOD Basis: " in result


# ── Builder tests ─────────────────────────────────────────────────

import json
import tempfile
from src.rag.corpus_builder import build_barrier_documents, build_incident_documents


def _make_v23_incident(incident_id: str = "TEST-001") -> dict:
    """Build a minimal V2.3 incident dict for testing."""
    return {
        "incident_id": incident_id,
        "source": {
            "doc_type": "Accident Investigation Report",
            "url": None,
            "title": "Test Report",
            "date_published": "2024-01-01",
            "date_occurred": "2024-01-01",
            "timezone": None,
        },
        "context": {
            "region": "Gulf of Mexico",
            "operator": "Test Operator",
            "operating_phase": "production",
            "materials": ["crude oil", "gas"],
        },
        "event": {
            "top_event": "Loss of Containment",
            "incident_type": "Equipment Failure",
            "costs": None,
            "actions_taken": [],
            "summary": "A valve failed causing a release of crude oil.",
            "recommendations": ["Replace valve", "Update procedure"],
            "key_phrases": [],
        },
        "bowtie": {
            "hazards": [{"hazard_id": "H-001", "name": "Pressurized system", "description": None}],
            "threats": [{"threat_id": "T-001", "name": "Valve failure", "description": None}],
            "consequences": [{"consequence_id": "CON-001", "name": "Oil spill", "description": None, "severity": None}],
            "controls": [
                {
                    "control_id": "C-001",
                    "name": "Pressure Safety Valve",
                    "side": "prevention",
                    "barrier_role": "Prevent overpressure",
                    "barrier_type": "engineering",
                    "line_of_defense": "1st",
                    "lod_basis": "Primary pressure protection",
                    "linked_threat_ids": ["T-001"],
                    "linked_consequence_ids": ["CON-001"],
                    "performance": {
                        "barrier_status": "failed",
                        "barrier_failed": True,
                        "detection_applicable": True,
                        "detection_mentioned": True,
                        "alarm_applicable": False,
                        "alarm_mentioned": False,
                        "manual_intervention_applicable": False,
                        "manual_intervention_mentioned": False,
                    },
                    "human": {
                        "human_contribution_value": "high",
                        "human_contribution_mentioned": True,
                        "barrier_failed_human": True,
                        "linked_pif_ids": ["PIF-001"],
                    },
                    "evidence": {
                        "supporting_text": ["The PSV was not tested", "Maintenance overdue"],
                        "confidence": "high",
                    },
                },
                {
                    "control_id": "C-002",
                    "name": "Training Program",
                    "side": "prevention",
                    "barrier_role": "Train operators on valve inspection",
                    "barrier_type": "administrative",
                    "line_of_defense": "2nd",
                    "lod_basis": "Competence assurance for maintenance",
                    "linked_threat_ids": ["T-001"],
                    "linked_consequence_ids": [],
                    "performance": {
                        "barrier_status": "degraded",
                        "barrier_failed": False,
                        "detection_applicable": False,
                        "detection_mentioned": False,
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
                        "supporting_text": [],
                        "confidence": "low",
                    },
                },
            ],
        },
        "pifs": {
            "people": {
                "competence_value": "low",
                "competence_mentioned": True,
                "fatigue_value": None,
                "fatigue_mentioned": False,
                "communication_value": "poor",
                "communication_mentioned": True,
                "situational_awareness_value": None,
                "situational_awareness_mentioned": False,
            },
            "work": {
                "procedures_value": "inadequate",
                "procedures_mentioned": True,
                "workload_value": None,
                "workload_mentioned": False,
                "time_pressure_value": None,
                "time_pressure_mentioned": False,
                "tools_equipment_value": None,
                "tools_equipment_mentioned": False,
            },
            "organisation": {
                "safety_culture_value": None,
                "safety_culture_mentioned": False,
                "management_of_change_value": None,
                "management_of_change_mentioned": False,
                "supervision_value": None,
                "supervision_mentioned": False,
                "training_value": "inadequate",
                "training_mentioned": True,
            },
        },
        "notes": {"rules": "JSON output only.", "schema_version": "2.3"},
    }


class TestBuildBarrierDocuments:
    def test_builds_from_json_dir(self, tmp_path):
        json_dir = tmp_path / "incidents"
        json_dir.mkdir()
        incident = _make_v23_incident()
        (json_dir / "test.json").write_text(json.dumps(incident), encoding="utf-8")

        out_csv = tmp_path / "barrier_documents.csv"
        count = build_barrier_documents(json_dir, out_csv)

        assert count == 2
        assert out_csv.exists()

        import csv as csv_mod
        with open(out_csv, encoding="utf-8") as f:
            reader = csv_mod.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["incident_id"] == "TEST-001"
        assert rows[0]["control_id"] == "C-001"
        assert "Barrier: Pressure Safety Valve" in rows[0]["barrier_role_match_text"]
        assert "Role: Prevent overpressure" in rows[0]["barrier_role_match_text"]
        assert rows[0]["barrier_family"] != ""
        assert rows[0]["barrier_failed"] == "True"
        assert rows[0]["barrier_failed_human"] == "True"
        assert rows[0]["pif_competence"] == "True"
        assert rows[0]["pif_communication"] == "True"
        assert rows[0]["pif_fatigue"] == "False"
        assert rows[0]["pif_procedures"] == "True"
        assert rows[0]["pif_training"] == "True"
        assert "The PSV was not tested" in rows[0]["supporting_text"]
        assert "A valve failed" in rows[0]["incident_summary"]

    def test_empty_dir_returns_zero(self, tmp_path):
        json_dir = tmp_path / "empty"
        json_dir.mkdir()
        out_csv = tmp_path / "barrier_documents.csv"
        count = build_barrier_documents(json_dir, out_csv)
        assert count == 0


class TestBuildIncidentDocuments:
    def test_builds_from_json_dir(self, tmp_path):
        json_dir = tmp_path / "incidents"
        json_dir.mkdir()
        incident = _make_v23_incident()
        (json_dir / "test.json").write_text(json.dumps(incident), encoding="utf-8")

        out_csv = tmp_path / "incident_documents.csv"
        count = build_incident_documents(json_dir, out_csv)

        assert count == 1
        assert out_csv.exists()

        import csv as csv_mod
        with open(out_csv, encoding="utf-8") as f:
            reader = csv_mod.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["incident_id"] == "TEST-001"
        assert "Top Event: Loss of Containment" in rows[0]["incident_embed_text"]
        assert "Operating Phase: production" in rows[0]["incident_embed_text"]
        assert "Materials: crude oil, gas" in rows[0]["incident_embed_text"]
        assert rows[0]["top_event"] == "Loss of Containment"
        assert rows[0]["operating_phase"] == "production"
        assert "A valve failed" in rows[0]["summary"]

    def test_incident_embed_text_contains_recommendation(self, tmp_path):
        """D017: recommendation text must appear in embed text."""
        json_dir = tmp_path / "incidents"
        json_dir.mkdir()
        incident = _make_v23_incident()
        (json_dir / "test.json").write_text(json.dumps(incident), encoding="utf-8")

        out_csv = tmp_path / "incident_documents.csv"
        build_incident_documents(json_dir, out_csv)

        import csv as csv_mod
        with open(out_csv, encoding="utf-8") as f:
            rows = list(csv_mod.DictReader(f))
        assert "Replace valve" in rows[0]["incident_embed_text"]

    def test_incident_embed_text_contains_pif_value(self, tmp_path):
        """D017: PIF _value text must appear in embed text."""
        json_dir = tmp_path / "incidents"
        json_dir.mkdir()
        incident = _make_v23_incident()
        (json_dir / "test.json").write_text(json.dumps(incident), encoding="utf-8")

        out_csv = tmp_path / "incident_documents.csv"
        build_incident_documents(json_dir, out_csv)

        import csv as csv_mod
        with open(out_csv, encoding="utf-8") as f:
            rows = list(csv_mod.DictReader(f))
        # The fixture has competence_value="low", communication_value="poor",
        # procedures_value="inadequate", training_value="inadequate"
        assert "low" in rows[0]["incident_embed_text"]


class TestIncidentIdFilter:
    def test_filter_restricts_to_scope(self, tmp_path):
        """incident_id_filter must exclude incidents not in the set."""
        json_dir = tmp_path / "incidents"
        json_dir.mkdir()
        for iid in ("INC-001", "INC-002", "INC-003"):
            inc = _make_v23_incident(iid)
            (json_dir / f"{iid}.json").write_text(json.dumps(inc), encoding="utf-8")

        out_csv = tmp_path / "incident_documents.csv"
        count = build_incident_documents(json_dir, out_csv, incident_id_filter={"INC-001", "INC-003"})

        assert count == 2
        import csv as csv_mod
        with open(out_csv, encoding="utf-8") as f:
            rows = list(csv_mod.DictReader(f))
        ids = {r["incident_id"] for r in rows}
        assert ids == {"INC-001", "INC-003"}
