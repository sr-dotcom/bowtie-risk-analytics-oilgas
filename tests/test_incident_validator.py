"""Tests for the Schema v2.3 incident validator."""

import copy
import json
from pathlib import Path

import pytest

from src.validation.incident_validator import validate_incident_v2_2

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "schema" / "incident_v2_2_template.json"


def _load_template() -> dict:
    """Load the Schema v2.3 template JSON from disk."""
    with open(TEMPLATE_PATH) as f:
        return json.load(f)


def _minimal_valid_doc() -> dict:
    """Build a minimal valid Schema v2.3 document."""
    return {
        "incident_id": "INC-TEST-001",
        "source": {
            "doc_type": "investigation_report",
            "url": None,
            "title": "Test Report",
            "date_published": None,
            "date_occurred": None,
            "timezone": None,
        },
        "context": {
            "region": "Gulf of Mexico",
            "operator": "TestCo",
            "operating_phase": "production",
            "materials": [],
        },
        "event": {
            "top_event": "Loss of Containment",
            "incident_type": "gas_release",
            "costs": None,
            "actions_taken": [],
            "summary": "A test incident.",
            "recommendations": [],
            "key_phrases": [],
        },
        "bowtie": {
            "hazards": [],
            "threats": [],
            "consequences": [],
            "controls": [],
        },
        "pifs": {
            "people": {
                "competence_value": None,
                "competence_mentioned": False,
                "fatigue_value": None,
                "fatigue_mentioned": False,
                "communication_value": None,
                "communication_mentioned": False,
                "situational_awareness_value": None,
                "situational_awareness_mentioned": False,
            },
            "work": {
                "procedures_value": None,
                "procedures_mentioned": False,
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
                "training_value": None,
                "training_mentioned": False,
            },
        },
        "notes": {
            "rules": "JSON output only.",
            "schema_version": "2.3",
        },
    }


class TestIncidentValidatorV2_2:
    """Tests for validate_incident_v2_2."""

    def test_valid_minimal_doc(self) -> None:
        """A minimal valid document should pass validation."""
        doc = _minimal_valid_doc()
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is True
        assert errors == []

    def test_missing_incident_id(self) -> None:
        """Removing incident_id (a required field) should fail validation."""
        doc = _minimal_valid_doc()
        del doc["incident_id"]
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is False
        assert len(errors) >= 1
        assert any("incident_id" in e for e in errors)

    def test_wrong_barrier_status_enum(self) -> None:
        """An invalid barrier_status value should fail validation."""
        doc = _minimal_valid_doc()
        doc["bowtie"]["controls"] = [
            {
                "control_id": "C-001",
                "name": "test",
                "side": "prevention",
                "barrier_role": "detect",
                "barrier_type": "engineering",
                "line_of_defense": "1st",
                "lod_basis": None,
                "linked_threat_ids": [],
                "linked_consequence_ids": [],
                "performance": {
                    "barrier_status": "INVALID_STATUS",
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
            }
        ]
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is False
        assert any("barrier_status" in e for e in errors)

    def test_wrong_side_enum(self) -> None:
        """An invalid side value should fail validation."""
        doc = _minimal_valid_doc()
        doc["bowtie"]["controls"] = [
            {
                "control_id": "C-001",
                "name": "test",
                "side": "INVALID_SIDE",
                "barrier_role": "detect",
                "barrier_type": "engineering",
                "line_of_defense": "1st",
                "lod_basis": None,
                "linked_threat_ids": [],
                "linked_consequence_ids": [],
                "performance": {
                    "barrier_status": "active",
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
            }
        ]
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is False
        assert any("side" in e for e in errors)

    def test_wrong_confidence_enum(self) -> None:
        """An invalid confidence value should fail validation."""
        doc = _minimal_valid_doc()
        doc["bowtie"]["controls"] = [
            {
                "control_id": "C-001",
                "name": "test",
                "side": "prevention",
                "barrier_role": "detect",
                "barrier_type": "engineering",
                "line_of_defense": "1st",
                "lod_basis": None,
                "linked_threat_ids": [],
                "linked_consequence_ids": [],
                "performance": {
                    "barrier_status": "active",
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
                    "confidence": "INVALID_CONFIDENCE",
                },
            }
        ]
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is False
        assert any("confidence" in e for e in errors)

    def test_readable_error_messages(self) -> None:
        """Error messages should be human-readable strings."""
        doc = _minimal_valid_doc()
        del doc["incident_id"]
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is False
        for err in errors:
            assert isinstance(err, str)
            assert len(err) > 0
            # Should contain a location indicator
            assert "incident_id" in err

    def test_top_event_list_becomes_string(self) -> None:
        """LLM returning a list for top_event should be coerced to string."""
        doc = _minimal_valid_doc()
        doc["event"]["top_event"] = ["Loss of Containment", "Fire"]
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is True, f"top_event as list failed: {errors}"

    def test_top_event_number_becomes_string(self) -> None:
        doc = _minimal_valid_doc()
        doc["event"]["top_event"] = 42
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is True, f"top_event as number failed: {errors}"

    def test_operating_phase_dict_becomes_string(self) -> None:
        """LLM returning a dict for operating_phase should be coerced to string."""
        doc = _minimal_valid_doc()
        doc["context"]["operating_phase"] = {"phase": "production", "sub": "startup"}
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is True, f"operating_phase as dict failed: {errors}"

    def test_operating_phase_string_unchanged(self) -> None:
        doc = _minimal_valid_doc()
        doc["context"]["operating_phase"] = "drilling"
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is True

    def test_materials_string_becomes_list(self) -> None:
        """LLM returning a bare string for materials should be wrapped in list."""
        doc = _minimal_valid_doc()
        doc["context"]["materials"] = "crude oil"
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is True, f"materials as string failed: {errors}"

    def test_materials_null_becomes_empty_list(self) -> None:
        doc = _minimal_valid_doc()
        doc["context"]["materials"] = None
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is True, f"materials as null failed: {errors}"

    def test_numeric_costs_accepted(self) -> None:
        """Numeric costs (int, float) should be normalized to str and pass."""
        for value in [1500000, 1.5e6, "1500000", 0, None]:
            doc = _minimal_valid_doc()
            doc["event"]["costs"] = value
            is_valid, errors = validate_incident_v2_2(doc)
            assert is_valid is True, f"costs={value!r} failed: {errors}"

    def test_costs_empty_dict_becomes_none(self) -> None:
        """Gemini returns {} for costs when unknown — coerce to None."""
        doc = _minimal_valid_doc()
        doc["event"]["costs"] = {}
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is True, f"costs={{}} failed: {errors}"

    def test_costs_nonempty_dict_stringified(self) -> None:
        """Non-empty dict costs should be preserved as JSON string."""
        doc = _minimal_valid_doc()
        doc["event"]["costs"] = {"amount": 500000, "currency": "USD"}
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is True, f"costs dict failed: {errors}"

    def test_materials_empty_dict_becomes_empty_list(self) -> None:
        """Gemini returns {} for materials — coerce to []."""
        doc = _minimal_valid_doc()
        doc["context"]["materials"] = {}
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is True, f"materials={{}} failed: {errors}"

    def test_materials_dict_with_values_extracts_strings(self) -> None:
        """Gemini returns {type: 'crude oil', quantity: None} — extract non-null values."""
        doc = _minimal_valid_doc()
        doc["context"]["materials"] = {"type": "crude oil", "quantity": None, "unit": None}
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is True, f"materials dict failed: {errors}"

    def test_operating_phase_uppercased_normalized(self) -> None:
        """DRILLING should be normalized to drilling."""
        doc = _minimal_valid_doc()
        doc["context"]["operating_phase"] = "DRILLING"
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is True, f"operating_phase DRILLING failed: {errors}"

    def test_event_type_remapped_to_top_event(self) -> None:
        """LLM returning event.type instead of event.top_event should be remapped."""
        doc = _minimal_valid_doc()
        doc["event"] = {"type": "Fire", "summary": "A fire."}
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is True, f"event.type remap failed: {errors}"

    def test_event_description_remapped_to_summary(self) -> None:
        """LLM returning event.description instead of event.summary should be remapped."""
        doc = _minimal_valid_doc()
        doc["event"] = {"description": "An explosion occurred.", "top_event": "Explosion"}
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is True, f"event.description remap failed: {errors}"

    def test_top_level_controls_moved_to_bowtie(self) -> None:
        """Top-level controls array should be moved into bowtie.controls."""
        doc = _minimal_valid_doc()
        doc["controls"] = [{"control_id": "C-001", "name": "alarm"}]
        doc["bowtie"] = {"hazards": [], "threats": [], "consequences": [], "controls": []}
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is True, f"top-level controls remap failed: {errors}"

    def test_full_template_validates(self) -> None:
        """The full template JSON file should pass validation."""
        doc = _load_template()
        is_valid, errors = validate_incident_v2_2(doc)
        assert is_valid is True, f"Template validation failed: {errors}"
        assert errors == []
