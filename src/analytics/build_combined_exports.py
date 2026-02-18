"""Combined aggregation exports across all incident sources.

Builds flat_incidents_combined.csv and controls_combined.csv by scanning
all JSON files under an incidents directory (any subdirectory depth).

source_agency resolution priority:
  1. data["source"]["agency"]  (JSON field — most authoritative)
  2. First path segment matching a known source: csb, bsee, tsb, phmsa
  3. "UNKNOWN"

provider_bucket is always the immediate parent directory name and is written
as a separate column so provider/format subfolders remain visible.
"""
import csv
import json
import logging
from pathlib import Path
from typing import Any

from src.analytics.flatten import CONTROLS_CSV_COLUMNS, flatten_controls

logger = logging.getLogger(__name__)

# Canonical source identifiers — only these are valid fallback values.
_KNOWN_SOURCES: frozenset[str] = frozenset({"csb", "bsee", "tsb", "phmsa"})

FLAT_INCIDENT_COLUMNS = [
    "incident_id",
    "source_agency",
    "provider_bucket",
    "incident__source__date_occurred",
    "incident__context__region",
    "incident__context__operator",
    "incident__event__top_event",
    "incident__event__incident_type",
    "incident__event__summary",
    "json_path",
]

COMBINED_CONTROLS_COLUMNS = CONTROLS_CSV_COLUMNS + [
    "source_agency",
    "provider_bucket",
    "json_path",
]


def resolve_source_agency(data: dict[str, Any], path_hint: str) -> str:
    """Resolve source agency with three-tier priority.

    Args:
        data: Parsed incident JSON dict.
        path_hint: Full or partial file path — all segments are scanned for
                   a known source identifier (csb, bsee, tsb, phmsa).

    Returns:
        Agency string in uppercase, or "UNKNOWN".
    """
    agency = data.get("source", {}).get("agency", "")
    if agency:
        return str(agency)

    for segment in Path(path_hint).parts:
        if segment.lower() in _KNOWN_SOURCES:
            return segment.upper()

    return "UNKNOWN"


def build_flat_incidents(incidents_dir: Path, out_path: Path) -> int:
    """Build flat incidents CSV from all JSON files under incidents_dir.

    Recurses into subdirectories. Malformed JSON files are skipped with a
    WARNING log. Always writes the output file (header-only if no incidents).

    Args:
        incidents_dir: Root directory containing incident JSON files.
        out_path: Output CSV path.

    Returns:
        Number of incidents successfully written.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for jf in sorted(incidents_dir.rglob("*.json")):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Skipping {jf.name}: {e}")
            continue

        agency = resolve_source_agency(data, str(jf))
        source = data.get("source", {})
        context = data.get("context", {})
        event = data.get("event", {})

        rows.append({
            "incident_id": data.get("incident_id", ""),
            "source_agency": agency,
            "provider_bucket": jf.parent.name,
            "incident__source__date_occurred": source.get("date_occurred", ""),
            "incident__context__region": context.get("region", ""),
            "incident__context__operator": context.get("operator", ""),
            "incident__event__top_event": event.get("top_event", ""),
            "incident__event__incident_type": event.get("incident_type", ""),
            "incident__event__summary": event.get("summary", ""),
            "json_path": str(jf),
        })

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FLAT_INCIDENT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Wrote {len(rows)} incident rows to {out_path}")
    return len(rows)


def build_controls_combined(incidents_dir: Path, out_path: Path) -> int:
    """Build combined controls CSV from all JSON files under incidents_dir.

    Reuses flatten_controls() and appends source_agency, provider_bucket,
    and json_path columns. Malformed JSON files are skipped with a WARNING log.

    Args:
        incidents_dir: Root directory containing incident JSON files.
        out_path: Output CSV path.

    Returns:
        Total number of control rows written.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []

    for jf in sorted(incidents_dir.rglob("*.json")):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Skipping {jf.name}: {e}")
            continue

        agency = resolve_source_agency(data, str(jf))
        bucket = jf.parent.name
        json_path_str = str(jf)

        for row in flatten_controls(data):
            row["source_agency"] = agency
            row["provider_bucket"] = bucket
            row["json_path"] = json_path_str
            all_rows.append(row)

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COMBINED_CONTROLS_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)

    logger.info(f"Wrote {len(all_rows)} control rows to {out_path}")
    return len(all_rows)


def build_all(incidents_dir: Path, output_dir: Path) -> tuple[int, int]:
    """Build all combined export CSVs.

    Args:
        incidents_dir: Root directory containing incident JSON files.
        output_dir: Directory to write output CSVs.

    Returns:
        Tuple of (incident_count, control_count).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    incident_count = build_flat_incidents(
        incidents_dir, output_dir / "flat_incidents_combined.csv"
    )
    control_count = build_controls_combined(
        incidents_dir, output_dir / "controls_combined.csv"
    )
    return incident_count, control_count
