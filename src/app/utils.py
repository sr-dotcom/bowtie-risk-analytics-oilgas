import json
from pathlib import Path
from typing import List, Dict, Any

def load_processed_incidents(processed_dir: Path) -> List[Dict[str, Any]]:
    """
    Loads all processed incident JSON files from the directory.

    Args:
        processed_dir: Directory containing JSON files.

    Returns:
        List of incident dictionaries.
    """
    incidents = []
    if not processed_dir.exists():
        return incidents

    for file_path in processed_dir.glob("INC-*.json"):
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
            incidents.append(data)
        except Exception as e:
            # Skip invalid files silently or log if we had a logger configured here
            pass

    return sorted(incidents, key=lambda x: x.get("incident_id", ""))

def load_fleet_metrics(processed_dir: Path) -> Dict[str, Any]:
    """
    Loads the fleet metrics JSON file.

    Args:
        processed_dir: Directory containing JSON files.

    Returns:
        Dictionary of metrics or default zero values.
    """
    metrics_file = processed_dir / "fleet_metrics.json"
    if not metrics_file.exists():
        return {
            "total_incidents": 0,
            "average_prevention_coverage": 0.0,
            "average_mitigation_coverage": 0.0,
            "average_overall_coverage": 0.0
        }

    try:
        return json.loads(metrics_file.read_text(encoding='utf-8'))
    except Exception:
        return {
            "total_incidents": 0,
            "average_prevention_coverage": 0.0,
            "average_mitigation_coverage": 0.0,
            "average_overall_coverage": 0.0
        }
