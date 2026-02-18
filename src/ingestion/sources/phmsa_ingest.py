"""PHMSA bulk CSV ingest skeleton.

PHMSA publishes bulk tabular data (no per-incident PDFs). This module
provides header inspection and a stub mapping path. Full column mapping
will be added once a real PHMSA CSV is downloaded and headers confirmed.
"""
import csv
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Known PHMSA CSV column names (case-insensitive matching)
KNOWN_COLUMNS: dict[str, list[str]] = {
    "id": ["report_number", "report number", "reportnumber", "id"],
    "date": ["incident_date", "incident date", "date", "iyear"],
    "narrative": ["narrative", "description", "summary"],
    "city": ["city", "location_city"],
    "state": ["state", "location_state"],
    "operator": ["operator_name", "operator"],
    "commodity": ["commodity_released_type", "commodity"],
    "volume": [
        "unintentional_release_bbls",
        "net_loss_barrels",
        "total_release_volume",
    ],
}

PHMSA_MANIFEST_COLUMNS: list[str] = [
    "doc_id",
    "incident_id",
    "json_path",
    "valid",
    "provider",
    "error",
    "created_at",
]


def _match_headers(
    file_headers: list[str],
) -> dict[str, Optional[str]]:
    """Match file headers against known PHMSA columns.

    Returns dict mapping logical name -> matched file header (or None).
    """
    lower_headers = {h.lower().strip(): h for h in file_headers}
    matched: dict[str, Optional[str]] = {}
    for logical, candidates in KNOWN_COLUMNS.items():
        matched[logical] = None
        for c in candidates:
            if c in lower_headers:
                matched[logical] = lower_headers[c]
                break
    return matched


def ingest_phmsa_csv(
    csv_path: Path,
    output_dir: Path,
    manifest_path: Path,
    limit: Optional[int] = None,
) -> list[dict]:
    """Inspect a PHMSA bulk CSV and report mapping status.

    This is a skeleton: it reads headers, reports which known columns
    were recognized, and returns an empty manifest. Full row-level
    mapping will be added once a real CSV is available and headers are
    confirmed.

    Args:
        csv_path: Path to PHMSA bulk incident CSV.
        output_dir: Directory for output JSON (unused in skeleton).
        manifest_path: Path for structured manifest CSV (written empty).
        limit: Max rows to inspect (default: all).

    Returns:
        Empty list (skeleton — no rows mapped yet).
    """
    if not csv_path.exists():
        logger.warning(f"PHMSA CSV not found: {csv_path}")
        return []

    try:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            file_headers = list(reader.fieldnames or [])
    except Exception as e:
        logger.warning(f"Failed to read PHMSA CSV headers: {e}")
        return []

    if not file_headers:
        logger.warning("PHMSA CSV has no headers")
        return []

    matched = _match_headers(file_headers)
    recognized = {k: v for k, v in matched.items() if v is not None}
    missing = {k for k, v in matched.items() if v is None}

    logger.info(
        f"PHMSA CSV headers ({len(file_headers)} columns): {file_headers}"
    )
    logger.info(f"Recognized columns: {recognized}")

    if not recognized:
        logger.warning(
            "No recognized PHMSA columns found. "
            "Mapping requires real CSV with known headers "
            f"(expected any of: {list(KNOWN_COLUMNS.keys())}). "
            "Returning empty manifest."
        )
        return []

    if "id" not in recognized or "narrative" not in recognized:
        logger.warning(
            f"Missing critical columns (id and/or narrative). "
            f"Recognized so far: {recognized}. Missing: {missing}. "
            "Mapping requires real CSV — returning empty manifest."
        )
        return []

    # Count rows for reporting
    row_count = 0
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for _ in reader:
            row_count += 1
            if limit and row_count >= limit:
                break

    logger.info(
        f"PHMSA CSV: {row_count} rows inspected, "
        f"{len(recognized)}/{len(KNOWN_COLUMNS)} columns recognized. "
        "Full mapping not yet implemented — returning empty manifest."
    )

    # Write empty manifest with correct schema
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PHMSA_MANIFEST_COLUMNS)
        writer.writeheader()

    return []
