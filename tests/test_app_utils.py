
import pytest
import json
from pathlib import Path
from src.app.utils import load_processed_incidents, load_fleet_metrics

@pytest.fixture
def mock_processed_dir(tmp_path):
    """Creates a temporary directory with mock processed data."""
    # Create incident file
    incident_data = {
        "incident_id": "INC-1",
        "description": "Test incident",
        "analytics": {
            "coverage": {"overall_coverage": 0.5},
            "gaps": []
        }
    }
    (tmp_path / "INC-1.json").write_text(json.dumps(incident_data), encoding='utf-8')

    # Create metrics file
    metrics_data = {
        "total_incidents": 1,
        "average_overall_coverage": 0.5
    }
    (tmp_path / "fleet_metrics.json").write_text(json.dumps(metrics_data), encoding='utf-8')

    return tmp_path

class TestAppUtils:
    """Test cases for Streamlit app utilities."""

    def test_load_processed_incidents(self, mock_processed_dir):
        """Test loading incident files from directory."""
        incidents = load_processed_incidents(mock_processed_dir)
        assert len(incidents) == 1
        assert incidents[0]["incident_id"] == "INC-1"
        assert incidents[0]["analytics"]["coverage"]["overall_coverage"] == 0.5

    def test_load_fleet_metrics(self, mock_processed_dir):
        """Test loading aggregate metrics."""
        metrics = load_fleet_metrics(mock_processed_dir)
        assert metrics["total_incidents"] == 1
        assert metrics["average_overall_coverage"] == 0.5

    def test_load_empty_dir(self, tmp_path):
        """Test loading from empty directory."""
        incidents = load_processed_incidents(tmp_path)
        assert len(incidents) == 0
