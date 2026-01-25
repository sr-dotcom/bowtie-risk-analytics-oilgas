from typing import List, Dict, Any
import statistics

def calculate_fleet_metrics(incidents_data: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculates aggregate metrics across a list of processed incidents.

    Args:
        incidents_data: List of incident dictionaries containing 'analytics' data.

    Returns:
        Dictionary of aggregate metrics.
    """
    if not incidents_data:
        return {
            "total_incidents": 0,
            "average_prevention_coverage": 0.0,
            "average_mitigation_coverage": 0.0,
            "average_overall_coverage": 0.0
        }

    total_incidents = len(incidents_data)

    # Extract coverage scores, defaulting to 0.0 if missing (though pipeline should ensure they exist)
    prev_scores = []
    mit_scores = []
    overall_scores = []

    for inc in incidents_data:
        analytics = inc.get("analytics", {})
        coverage = analytics.get("coverage", {})

        prev_scores.append(coverage.get("prevention_coverage", 0.0))
        mit_scores.append(coverage.get("mitigation_coverage", 0.0))
        overall_scores.append(coverage.get("overall_coverage", 0.0))

    return {
        "total_incidents": total_incidents,
        "average_prevention_coverage": statistics.mean(prev_scores) if prev_scores else 0.0,
        "average_mitigation_coverage": statistics.mean(mit_scores) if mit_scores else 0.0,
        "average_overall_coverage": statistics.mean(overall_scores) if overall_scores else 0.0
    }
