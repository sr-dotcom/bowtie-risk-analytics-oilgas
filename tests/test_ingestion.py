
import pytest
from src.ingestion.loader import load_incident_from_text
from src.models.incident import Incident

class TestIngestion:
    """Test cases for data ingestion."""

    def test_load_incident_from_text(self):
        """Test parsing a raw text narrative into an Incident model."""
        raw_text = """
        ID: INC-2024-001
        Date: 2024-01-15
        Description: A gas leak occurred at the north valve station due to corrosion.
        """

        incident = load_incident_from_text(raw_text)

        assert isinstance(incident, Incident)
        assert incident.incident_id == "INC-2024-001"
        assert "gas leak" in incident.description

    def test_load_incident_invalid_format(self):
        """Test that invalid format raises an error."""
        raw_text = "Just some random text without structure."

        with pytest.raises(ValueError):
            load_incident_from_text(raw_text)
