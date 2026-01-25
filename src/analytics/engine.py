from typing import List, Dict, Any
from src.models.bowtie import Bowtie, Barrier
from src.models.incident import Incident

def calculate_barrier_coverage(incident: Incident, bowtie: Bowtie) -> Dict[str, float]:
    """
    Calculates the percentage of Bowtie barriers present in the incident.

    Args:
        incident: The incident data with identified barriers.
        bowtie: The reference Bowtie diagram.

    Returns:
        Dictionary with coverage metrics (0.0 to 1.0).
    """
    def _calc_coverage(incident_barriers: List[str], bowtie_barriers: List[Barrier]) -> float:
        if not bowtie_barriers:
            return 0.0

        # Match by name (assuming exact match for now, simple string comparison)
        # In a real system, this might use IDs or fuzzy matching
        present_count = 0
        bowtie_names = [b.name.lower() for b in bowtie_barriers]

        for ib in incident_barriers:
            if ib.lower() in bowtie_names:
                present_count += 1

        # Cap at 1.0 even if duplicates exist in incident data
        return min(1.0, present_count / len(bowtie_barriers))

    # Filter bowtie barriers by type
    prev_barriers = [b for b in bowtie.barriers if b.type == "prevention"]
    mit_barriers = [b for b in bowtie.barriers if b.type == "mitigation"]

    prevention_cov = _calc_coverage(incident.prevention_barriers, prev_barriers)
    mitigation_cov = _calc_coverage(incident.mitigation_barriers, mit_barriers)

    # Overall coverage (all barriers)
    all_incident_barriers = incident.prevention_barriers + incident.mitigation_barriers
    overall_cov = _calc_coverage(all_incident_barriers, bowtie.barriers)

    return {
        "prevention_coverage": prevention_cov,
        "mitigation_coverage": mitigation_cov,
        "overall_coverage": overall_cov
    }

def identify_gaps(incident: Incident, bowtie: Bowtie) -> List[Barrier]:
    """
    Identifies barriers defined in the Bowtie that were NOT present in the incident.

    Args:
        incident: The incident data.
        bowtie: The reference Bowtie.

    Returns:
        List of Barrier objects that are considered 'gaps'.
    """
    gaps = []

    # Normalize incident barrier names for comparison
    incident_barrier_names = set(
        b.lower() for b in (incident.prevention_barriers + incident.mitigation_barriers)
    )

    for barrier in bowtie.barriers:
        if barrier.name.lower() not in incident_barrier_names:
            gaps.append(barrier)

    return gaps
