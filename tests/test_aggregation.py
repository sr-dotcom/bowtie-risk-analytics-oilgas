
import pytest
from src.analytics.aggregation import calculate_fleet_metrics

class TestAggregation:
    """Test cases for fleet-wide analytics aggregation."""

    def test_calculate_fleet_metrics(self):
        """Test calculation of average coverage across multiple incidents."""
        incidents_data = [
            {
                "incident_id": "1",
                "analytics": {
                    "coverage": {
                        "prevention_coverage": 1.0,
                        "mitigation_coverage": 0.0,
                        "overall_coverage": 0.5
                    },
                    "gaps": [{"id": "B2"}]
                }
            },
            {
                "incident_id": "2",
                "analytics": {
                    "coverage": {
                        "prevention_coverage": 0.0,
                        "mitigation_coverage": 0.0,
                        "overall_coverage": 0.0
                    },
                    "gaps": [{"id": "B1"}, {"id": "B2"}]
                }
            }
        ]

        metrics = calculate_fleet_metrics(incidents_data)

        # Avg Prevention: (1.0 + 0.0) / 2 = 0.5
        # Avg Mitigation: (0.0 + 0.0) / 2 = 0.0
        # Avg Overall: (0.5 + 0.0) / 2 = 0.25

        assert metrics["average_prevention_coverage"] == 0.5
        assert metrics["average_mitigation_coverage"] == 0.0
        assert metrics["average_overall_coverage"] == 0.25
        assert metrics["total_incidents"] == 2
