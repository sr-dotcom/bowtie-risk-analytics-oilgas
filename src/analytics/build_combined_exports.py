"""Combined aggregation exports across all incident sources.

Builds flat_incidents_combined.csv and controls_combined.csv by scanning
all JSON files under an incidents directory (any subdirectory depth).

source_agency resolution (four-tier priority):
  1. Explicit JSON field: source.agency / source.publisher / source.report_source
  2. doc_type / document_type keyword inference (BSEE accident reports, CSB rec reports)
  3. URL domain (csb.gov / bsee.gov / tsb.gc.ca / phmsa.dot.gov)
  4. First path segment matching a known source: csb, bsee, tsb, phmsa
  5. "UNKNOWN"

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

# Canonical source identifiers (for path-segment fallback).
_KNOWN_SOURCES: frozenset[str] = frozenset({"csb", "bsee", "tsb", "phmsa"})

# doc_type substrings → agency (checked in order, case-insensitive).
# More-specific strings come first to avoid false matches.
_DOC_TYPE_RULES: list[tuple[str, str]] = [
    ("bsee", "BSEE"),
    ("accident investigation", "BSEE"),  # BSEE EV2010R forms
    ("csb", "CSB"),
    ("recommendation status change", "CSB"),  # CSB rec-tracking reports
    ("tsb", "TSB"),
    ("phmsa", "PHMSA"),
]

# URL domain substrings → agency.
_URL_DOMAIN_RULES: list[tuple[str, str]] = [
    ("csb.gov", "CSB"),
    ("bsee.gov", "BSEE"),
    ("tsb.gc.ca", "TSB"),
    ("phmsa.dot.gov", "PHMSA"),
]

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


def _infer_from_doc_type(doc_type: str) -> str:
    """Return agency from doc_type string, or empty string if not recognised."""
    dt = doc_type.lower()
    for substring, agency in _DOC_TYPE_RULES:
        if substring in dt:
            return agency
    return ""


def _infer_from_url(url: str) -> str:
    """Return agency from a URL string, or empty string if not recognised."""
    u = url.lower()
    for domain, agency in _URL_DOMAIN_RULES:
        if domain in u:
            return agency
    return ""


def resolve_source_agency(data: dict[str, Any], path_hint: str) -> str:
    """Resolve source agency with four-tier priority.

    Tier 1 — explicit JSON fields: source.agency / source.publisher /
              source.report_source
    Tier 2 — doc_type / document_type keyword inference
    Tier 3 — URL domain match (csb.gov, bsee.gov, tsb.gc.ca, phmsa.dot.gov)
    Tier 4 — path segment matching known sources (csb, bsee, tsb, phmsa)
    Tier 5 — "UNKNOWN"

    Args:
        data: Parsed incident JSON dict.
        path_hint: Full or partial file path — all segments are scanned in
                   tier 4.

    Returns:
        Agency string in uppercase, or "UNKNOWN".
    """
    src = data.get("source", {})

    # Tier 1: explicit agency fields
    for field in ("agency", "publisher", "report_source"):
        val = src.get(field, "")
        if val:
            return str(val)

    # Tier 2: doc_type / document_type keyword inference
    doc_type = src.get("doc_type", "") or src.get("document_type", "")
    if doc_type:
        inferred = _infer_from_doc_type(str(doc_type))
        if inferred:
            return inferred

    # Tier 3: URL domain
    url = src.get("url", "") or src.get("document_url", "")
    if url and str(url).lower() not in ("", "null", "unknown", "none"):
        inferred = _infer_from_url(str(url))
        if inferred:
            return inferred

    # Tier 4: path segment
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
