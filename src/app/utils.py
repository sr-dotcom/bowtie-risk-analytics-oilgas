import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Configure logger
logger = logging.getLogger(__name__)

def load_data(processed_dir: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Loads incidents and metrics from the processed directory."""
    incidents = []
    metrics = {
        "total_incidents": 0,
        "average_prevention_coverage": 0.0,
        "average_mitigation_coverage": 0.0,
        "average_overall_coverage": 0.0
    }

    if not processed_dir.exists():
        return incidents, metrics

    # Load incidents
    for file_path in processed_dir.glob("INC-*.json"):
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
            incidents.append(data)
        except Exception as e:
            logger.warning(f"Failed to load incident from {file_path}: {e}")

    # Load metrics
    metrics_file = processed_dir / "fleet_metrics.json"
    if metrics_file.exists():
        try:
            metrics = json.loads(metrics_file.read_text(encoding='utf-8'))
        except Exception as e:
            logger.warning(f"Failed to load metrics from {metrics_file}: {e}")

    return sorted(incidents, key=lambda x: x.get("incident_id", "")), metrics
