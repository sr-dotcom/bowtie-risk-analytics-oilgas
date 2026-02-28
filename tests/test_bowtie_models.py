
import pytest
from pydantic import ValidationError
from src.models.bowtie import Threat, Barrier, Consequence, Bowtie

class TestThreat:
    """Test cases for the Threat model."""

    def test_create_valid_threat(self):
        """Test creating a threat with valid data."""
        threat = Threat(
            id="TH-001",
            name="Corrosion",
            description="Internal corrosion of pipeline"
        )
        assert threat.id == "TH-001"
        assert threat.name == "Corrosion"

    def test_threat_requires_id(self):
        """Test that threat ID is required."""
        with pytest.raises(ValidationError):
            Threat(name="Corrosion")


class TestBarrier:
    """Test cases for the Barrier model."""

    def test_create_valid_barrier(self):
        """Test creating a barrier with valid data."""
        barrier = Barrier(
            id="BAR-001",
            name="Pressure Safety Valve",
            type="prevention",
            effectiveness="high"
        )
        assert barrier.id == "BAR-001"
        assert barrier.type == "prevention"

    def test_barrier_type_validation(self):
        """Test that barrier type must be valid."""
        with pytest.raises(ValidationError):
            Barrier(
                id="BAR-002",
                name="Bad Barrier",
                type="invalid_type"
            )


class TestConsequence:
    """Test cases for the Consequence model."""

    def test_create_valid_consequence(self):
        """Test creating a consequence with valid data."""
        consequence = Consequence(
            id="CQ-001",
            name="Fire",
            severity="Major"
        )
        assert consequence.id == "CQ-001"
        assert consequence.severity == "Major"

    def test_consequence_validation(self):
        """Test that consequence ID is required."""
        with pytest.raises(ValidationError):
            Consequence(name="Explosion")


class TestBowtie:
    """Test cases for the full Bowtie model."""

    def test_create_full_bowtie(self):
        """Test creating a full bowtie diagram."""
        bowtie = Bowtie(
            hazard="Hydrocarbon Release",
            top_event="Loss of Containment",
            threats=[
                Threat(id="TH-1", name="Corrosion")
            ],
            consequences=[
                Consequence(id="CQ-1", name="Fire")
            ],
            barriers=[
                Barrier(id="B-1", name="Valve", type="prevention")
            ]
        )
        assert bowtie.hazard == "Hydrocarbon Release"
        assert len(bowtie.threats) == 1
        assert len(bowtie.barriers) == 1

    def test_bowtie_defaults(self):
        """Test that lists default to empty."""
        bowtie = Bowtie(
            hazard="Hazard",
            top_event="Event"
        )
        assert bowtie.threats == []
        assert bowtie.consequences == []

