"""Flatten aggregated incidents into barrier/control tabular rows.

Input is expected to be a JSON list of incident objects produced by jsonaggregation.py.
Output CSV is stable and intentionally narrow for association-mining workflows.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

DEFAULT_INPUT_JSON = Path("out/association_mining/incidents_aggregated.json")
DEFAULT_OUTPUT_CSV = Path("out/association_mining/incidents_flat.csv")

CSV_COLUMNS = [
    "incident_id",
    "control_id",
    "control_name",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Flatten aggregated incident JSON into control-level CSV rows.",
    )
    parser.add_argument(
        "--input-json",
        type=Path,
        default=DEFAULT_INPUT_JSON,
        help=f"Aggregated incident JSON list (default: {DEFAULT_INPUT_JSON.as_posix()})",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=DEFAULT_OUTPUT_CSV,
        help=f"Output CSV path (default: {DEFAULT_OUTPUT_CSV.as_posix()})",
    )
    parser.add_argument(
        "--output-xlsx",
        type=Path,
        default=None,
        help="Optional output Excel path. If omitted, Excel is not written.",
    )
    return parser.parse_args()


def _stringify_list(value: Any) -> str:
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    return ""


def flatten_incident(incident: dict[str, Any]) -> list[dict[str, Any]]:
    """Produce one row per control.

    Assumptions:
    - Controls are in incident['bowtie']['controls'].
    - Missing optional fields are emitted as empty values.
    - One CSV row represents one barrier/control observation for one incident.
    """
    incident_id = incident.get("incident_id", "unknown")
    controls = incident.get("bowtie", {}).get("controls", [])
    rows: list[dict[str, Any]] = []

    for ctrl in controls:
        if not isinstance(ctrl, dict):
            continue

        performance = ctrl.get("performance", {}) if isinstance(ctrl.get("performance"), dict) else {}
        human = ctrl.get("human", {}) if isinstance(ctrl.get("human"), dict) else {}
        evidence = ctrl.get("evidence", {}) if isinstance(ctrl.get("evidence"), dict) else {}

        rows.append(
            {
                "incident_id": incident_id,
                "control_id": ctrl.get("control_id", ""),
                "control_name": ctrl.get("name", ""),
                "side": ctrl.get("side", ""),
                "barrier_role": ctrl.get("barrier_role", ""),
                "barrier_type": ctrl.get("barrier_type", ""),
                "line_of_defense": ctrl.get("line_of_defense", ""),
                "lod_basis": ctrl.get("lod_basis", ""),
                "linked_threat_ids": _stringify_list(ctrl.get("linked_threat_ids")),
                "linked_consequence_ids": _stringify_list(ctrl.get("linked_consequence_ids")),
                "barrier_status": performance.get("barrier_status", ""),
                "barrier_failed": performance.get("barrier_failed", False),
                "human_contribution_value": human.get("human_contribution_value", ""),
                "barrier_failed_human": human.get("barrier_failed_human", False),
                "confidence": evidence.get("confidence", ""),
                "supporting_text_count": len(evidence.get("supporting_text", []))
                if isinstance(evidence.get("supporting_text"), list)
                else 0,
            }
        )

    return rows


def flatten(input_json: Path, output_csv: Path, output_xlsx: Path | None = None) -> int:
    incidents = json.loads(input_json.read_text(encoding="utf-8"))
    if not isinstance(incidents, list):
        raise ValueError("Input JSON must be a list of incident objects")

    rows: list[dict[str, Any]] = []
    for incident in incidents:
        if isinstance(incident, dict):
            rows.extend(flatten_incident(incident))

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    if output_xlsx is not None:
        output_xlsx.parent.mkdir(parents=True, exist_ok=True)
        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("pandas is required for --output-xlsx") from exc

        pd.DataFrame(rows, columns=CSV_COLUMNS).to_excel(output_xlsx, index=False)

    return len(rows)


def main() -> None:
    args = parse_args()
    row_count = flatten(args.input_json, args.output_csv, args.output_xlsx)
    print(f"Flattened {row_count} control row(s) to {args.output_csv}")
    if args.output_xlsx is not None:
        print(f"Wrote Excel output to {args.output_xlsx}")


if __name__ == "__main__":
    main()
