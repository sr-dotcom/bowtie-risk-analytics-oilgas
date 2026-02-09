"""Stub LLM provider for testing without API keys."""
import json
from src.llm.base import LLMProvider


class StubProvider(LLMProvider):
    """Returns a fixed valid Schema v2.3 incident JSON for testing."""

    def extract(self, prompt: str) -> str:
        """Return a sample Schema v2.3 incident JSON."""
        sample = {
            "incident_id": "STUB-001",
            "source": {
                "doc_type": "investigation_report",
                "url": None,
                "title": "Stub Incident Report",
                "date_published": None,
                "date_occurred": None,
                "timezone": None
            },
            "context": {
                "region": "Gulf of Mexico",
                "operator": "Stub Operator",
                "operating_phase": "production",
                "materials": ["hydrocarbon"]
            },
            "event": {
                "top_event": "Loss of Containment",
                "incident_type": "gas_release",
                "costs": None,
                "actions_taken": ["Emergency shutdown activated"],
                "summary": "Stub incident for testing purposes.",
                "recommendations": ["Review maintenance procedures"],
                "key_phrases": ["loss of containment", "gas release"]
            },
            "bowtie": {
                "hazards": [{"hazard_id": "H-001", "name": "Hydrocarbon release", "description": "Uncontrolled release of hydrocarbons"}],
                "threats": [{"threat_id": "T-001", "name": "Corrosion", "description": "Internal corrosion of piping"}],
                "consequences": [{"consequence_id": "CON-001", "name": "Fire", "description": "Ignition of released gas", "severity": "major"}],
                "controls": [{
                    "control_id": "C-001",
                    "name": "Gas detection system",
                    "side": "prevention",
                    "barrier_role": "detect",
                    "barrier_type": "engineering",
                    "line_of_defense": "1st",
                    "lod_basis": None,
                    "linked_threat_ids": ["T-001"],
                    "linked_consequence_ids": [],
                    "performance": {
                        "barrier_status": "active",
                        "barrier_failed": False,
                        "detection_applicable": True,
                        "detection_mentioned": True,
                        "alarm_applicable": True,
                        "alarm_mentioned": False,
                        "manual_intervention_applicable": False,
                        "manual_intervention_mentioned": False
                    },
                    "human": {
                        "human_contribution_value": None,
                        "human_contribution_mentioned": False,
                        "barrier_failed_human": False,
                        "linked_pif_ids": []
                    },
                    "evidence": {
                        "supporting_text": ["Gas detection system was operational at time of incident"],
                        "confidence": "medium"
                    }
                }]
            },
            "pifs": {
                "people": {
                    "competence_value": None, "competence_mentioned": False,
                    "fatigue_value": None, "fatigue_mentioned": False,
                    "communication_value": None, "communication_mentioned": False,
                    "situational_awareness_value": None, "situational_awareness_mentioned": False
                },
                "work": {
                    "procedures_value": None, "procedures_mentioned": False,
                    "workload_value": None, "workload_mentioned": False,
                    "time_pressure_value": None, "time_pressure_mentioned": False,
                    "tools_equipment_value": None, "tools_equipment_mentioned": False
                },
                "organisation": {
                    "safety_culture_value": None, "safety_culture_mentioned": False,
                    "management_of_change_value": None, "management_of_change_mentioned": False,
                    "supervision_value": None, "supervision_mentioned": False,
                    "training_value": None, "training_mentioned": False
                }
            },
            "notes": {
                "rules": "Stub output for testing.",
                "schema_version": "2.3"
            }
        }
        return json.dumps(sample, indent=2)
