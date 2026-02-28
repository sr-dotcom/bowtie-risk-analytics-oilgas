
import pytest
from src.models.bowtie import Bowtie, Threat, Barrier, Consequence
from src.models.incident import Incident
from src.analytics.engine import calculate_barrier_coverage, identify_gaps

@pytest.fixture
def sample_bowtie():
    return Bowtie(
        hazard="Hydrocarbon",
        top_event="Loss of Containment",
        threats=[Threat(id="T1", name="Corrosion")],
        consequences=[Consequence(id="C1", name="Fire")],
        barriers=[
            Barrier(id="B1", name="Coating", type="prevention"),
            Barrier(id="B2", name="Sprinkler", type="mitigation")
        ]
    )

@pytest.fixture
def sample_incident():
    return Incident(
        incident_id="INC-1",
        description="Leak due to corrosion. Coating was present.",
        prevention_barriers=["Coating"],
        mitigation_barriers=[]
    )

class TestAnalytics:
    """Test cases for Bowtie analytics engine."""

    def test_calculate_barrier_coverage(self, sample_bowtie, sample_incident):
        """Test calculation of barrier coverage percentages."""
        metrics = calculate_barrier_coverage(sample_incident, sample_bowtie)

        # B1 (Coating) is present, B2 (Sprinkler) is missing
        # Prevention: 1/1 = 100%
        # Mitigation: 0/1 = 0%
        # Overall: 1/2 = 50%

        assert metrics["prevention_coverage"] == 1.0
        assert metrics["mitigation_coverage"] == 0.0
        assert metrics["overall_coverage"] == 0.5

    def test_identify_gaps(self, sample_bowtie, sample_incident):
        """Test identification of missing barriers."""
        gaps = identify_gaps(sample_incident, sample_bowtie)

        assert len(gaps) == 1
        assert gaps[0].name == "Sprinkler"
        assert gaps[0].type == "mitigation"
