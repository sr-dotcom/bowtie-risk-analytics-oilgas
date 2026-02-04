from datetime import date
import pytest
from src.models.incident import Incident

class TestIncident:
    def test_create_minimal(self):
        incident = Incident(
            incident_id="INC-001",
            description="Test incident"
        )
        assert incident.incident_id == "INC-001"
        assert incident.causes == []

    def test_full_incident(self):
        incident = Incident(
            incident_id="INC-002",
            date=date(2024, 1, 15),
            location="Gulf of Mexico",
            facility_type="Offshore Platform",
            incident_type="Gas Release",
            severity="Major",
            description="Gas release",
            hazard="Hydrocarbon Release",
            top_event="Loss of Containment",
            causes=["Equipment failure"],
            consequences=["Fire"],
            injuries=2,
            fatalities=0
        )
        assert incident.date == date(2024, 1, 15)
        assert len(incident.causes) == 1
        assert incident.injuries == 2

    def test_serialization(self):
        incident = Incident(
            incident_id="INC-003",
            description="Test serialization"
        )
        json_data = incident.model_dump_json()
        assert "INC-003" in json_data

    def test_validation(self):
        with pytest.raises(ValueError):
            Incident(
                incident_id="INC-005",
                description="Test",
                injuries=-1
            )
