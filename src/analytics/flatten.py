"""Flatten Schema v2.3 incident controls into a tabular CSV dataset."""
import csv
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONTROLS_CSV_COLUMNS = [
    "incident_id",
    "control_id",
    "name",
    "side",
    "barrier_role",
    "barrier_type",
    "line_of_defense",
    "lod_basis",
    "linked_threat_ids",
    "linked_consequence_ids",
    "barrier_status",
    "barrier_failed",
    "human_contribution_value",
    "barrier_failed_human",
    "confidence",
    "supporting_text_count",
]


def flatten_controls(incident: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten controls from a single Schema v2.3 incident dict into flat rows.

    Args:
        incident: Parsed Schema v2.3 incident JSON.

    Returns:
        List of flat dicts, one per control.
    """
    incident_id = incident.get("incident_id", "unknown")
    controls = incident.get("bowtie", {}).get("controls", [])
    rows = []

    for ctrl in controls:
        perf = ctrl.get("performance", {})
        human = ctrl.get("human", {})
        evidence = ctrl.get("evidence", {})

        rows.append({
            "incident_id": incident_id,
            "control_id": ctrl.get("control_id", ""),
            "name": ctrl.get("name", ""),
            "side": ctrl.get("side", ""),
            "barrier_role": ctrl.get("barrier_role", ""),
            "barrier_type": ctrl.get("barrier_type", ""),
            "line_of_defense": ctrl.get("line_of_defense", ""),
            "lod_basis": ctrl.get("lod_basis", ""),
            "linked_threat_ids": ",".join(ctrl.get("linked_threat_ids", [])),
            "linked_consequence_ids": ",".join(ctrl.get("linked_consequence_ids", [])),
            "barrier_status": perf.get("barrier_status", ""),
            "barrier_failed": perf.get("barrier_failed", False),
            "human_contribution_value": human.get("human_contribution_value", ""),
            "barrier_failed_human": human.get("barrier_failed_human", False),
            "confidence": evidence.get("confidence", ""),
            "supporting_text_count": len(evidence.get("supporting_text", [])),
        })

    return rows


def flatten_all(structured_dir: Path, out_path: Path) -> int:
    """Flatten controls from all Schema v2.3 JSON files into a single CSV.

    Args:
        structured_dir: Directory containing Schema v2.3 incident JSON files.
        out_path: Output CSV path.

    Returns:
        Total number of control rows written.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []

    json_files = sorted(structured_dir.glob("*.json"))
    if not json_files:
        logger.warning(f"No JSON files found in {structured_dir}")
        return 0

    for jf in json_files:
        try:
            incident = json.loads(jf.read_text(encoding="utf-8"))
            rows = flatten_controls(incident)
            all_rows.extend(rows)
            logger.info(f"Flattened {len(rows)} controls from {jf.name}")
        except Exception as e:
            logger.error(f"Error processing {jf.name}: {e}")

    if not all_rows:
        logger.warning("No controls found across all incidents")
        return 0

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CONTROLS_CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)

    logger.info(f"Wrote {len(all_rows)} control rows to {out_path}")
    return len(all_rows)
