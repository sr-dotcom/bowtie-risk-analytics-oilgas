"""Manifest models for tracking incident acquisition and text extraction."""
import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class IncidentManifestRow(BaseModel):
    """Row in incidents_manifest_v0.csv (download tracking)."""

    model_config = ConfigDict(extra="ignore")

    source: Literal["csb", "bsee"]
    incident_id: str
    title: str
    date_occurred: Optional[str] = None
    date_report_released: Optional[str] = None
    detail_url: str
    pdf_url: str
    pdf_path: str
    downloaded: bool = False
    retrieved_at: Optional[datetime] = None
    http_status: Optional[int] = None
    content_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    sha256: Optional[str] = None
    error: Optional[str] = None


class TextManifestRow(BaseModel):
    """Row in text_manifest_v0.csv (extraction tracking)."""

    model_config = ConfigDict(extra="ignore")

    source: Literal["csb", "bsee"]
    incident_id: str
    pdf_path: str
    text_path: str
    extracted: bool = False
    extracted_at: Optional[datetime] = None
    extractor: str = "pdfplumber"
    page_count: Optional[int] = None
    char_count: Optional[int] = None
    is_empty: bool = False
    error: Optional[str] = None


def load_incident_manifest(path: Path) -> list[IncidentManifestRow]:
    """Load incident manifest from CSV file."""
    if not path.exists():
        logger.warning(f"Manifest not found: {path}")
        return []

    rows = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row_dict in reader:
            # Convert string booleans
            if "downloaded" in row_dict:
                row_dict["downloaded"] = row_dict["downloaded"].lower() == "true"
            # Convert empty strings to None for optional int fields
            for key in ["http_status", "file_size_bytes"]:
                if key in row_dict and row_dict[key] == "":
                    row_dict[key] = None
                elif key in row_dict and row_dict[key]:
                    row_dict[key] = int(row_dict[key])
            # Parse datetime
            if "retrieved_at" in row_dict and row_dict["retrieved_at"]:
                row_dict["retrieved_at"] = datetime.fromisoformat(
                    row_dict["retrieved_at"]
                )
            elif "retrieved_at" in row_dict:
                row_dict["retrieved_at"] = None
            # Handle empty optional strings
            for key in [
                "date_occurred",
                "date_report_released",
                "content_type",
                "sha256",
                "error",
            ]:
                if key in row_dict and row_dict[key] == "":
                    row_dict[key] = None

            rows.append(IncidentManifestRow(**row_dict))
    return rows


def save_incident_manifest(rows: list[IncidentManifestRow], path: Path) -> None:
    """Save incident manifest to CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(IncidentManifestRow.model_fields.keys())

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row_dict = row.model_dump()
            # Convert datetime to ISO string
            if row_dict["retrieved_at"]:
                row_dict["retrieved_at"] = row_dict["retrieved_at"].isoformat()
            # Convert None to empty string
            row_dict = {k: ("" if v is None else v) for k, v in row_dict.items()}
            # Convert bool to string
            row_dict["downloaded"] = str(row_dict["downloaded"])
            writer.writerow(row_dict)


def load_text_manifest(path: Path) -> list[TextManifestRow]:
    """Load text manifest from CSV file."""
    if not path.exists():
        logger.warning(f"Manifest not found: {path}")
        return []

    rows = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row_dict in reader:
            # Convert string booleans
            for key in ["extracted", "is_empty"]:
                if key in row_dict:
                    row_dict[key] = row_dict[key].lower() == "true"
            # Convert empty strings to None for optional int fields
            for key in ["page_count", "char_count"]:
                if key in row_dict and row_dict[key] == "":
                    row_dict[key] = None
                elif key in row_dict and row_dict[key]:
                    row_dict[key] = int(row_dict[key])
            # Parse datetime
            if "extracted_at" in row_dict and row_dict["extracted_at"]:
                row_dict["extracted_at"] = datetime.fromisoformat(
                    row_dict["extracted_at"]
                )
            elif "extracted_at" in row_dict:
                row_dict["extracted_at"] = None
            # Handle empty optional strings
            if "error" in row_dict and row_dict["error"] == "":
                row_dict["error"] = None

            rows.append(TextManifestRow(**row_dict))
    return rows


def save_text_manifest(rows: list[TextManifestRow], path: Path) -> None:
    """Save text manifest to CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(TextManifestRow.model_fields.keys())

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row_dict = row.model_dump()
            # Convert datetime to ISO string
            if row_dict["extracted_at"]:
                row_dict["extracted_at"] = row_dict["extracted_at"].isoformat()
            # Convert None to empty string
            row_dict = {k: ("" if v is None else v) for k, v in row_dict.items()}
            # Convert bools to string
            row_dict["extracted"] = str(row_dict["extracted"])
            row_dict["is_empty"] = str(row_dict["is_empty"])
            writer.writerow(row_dict)


def _get_merge_key(row: IncidentManifestRow) -> tuple[str, str]:
    """
    Get the merge key for deduplication.

    Key is (source, pdf_url), or fallback to (source, incident_id) if pdf_url is empty.
    """
    if row.pdf_url:
        return (row.source, row.pdf_url)
    return (row.source, row.incident_id)


def _compare_rows(a: IncidentManifestRow, b: IncidentManifestRow) -> int:
    """
    Compare two rows to determine winner.

    Returns:
        -1 if a wins, 1 if b wins, 0 if tie.

    Priority rules:
    1. downloaded=True beats downloaded=False
    2. retrieved_at newer beats older
    3. sha256 present beats missing
    4. file_size_bytes larger beats smaller
    5. otherwise tie (existing wins)
    """
    # Rule 1: downloaded=True beats False
    if a.downloaded and not b.downloaded:
        return -1
    if b.downloaded and not a.downloaded:
        return 1

    # Rule 2: newer retrieved_at beats older
    if a.retrieved_at and b.retrieved_at:
        if a.retrieved_at > b.retrieved_at:
            return -1
        if b.retrieved_at > a.retrieved_at:
            return 1
    elif a.retrieved_at and not b.retrieved_at:
        return -1
    elif b.retrieved_at and not a.retrieved_at:
        return 1

    # Rule 3: sha256 present beats missing
    if a.sha256 and not b.sha256:
        return -1
    if b.sha256 and not a.sha256:
        return 1

    # Rule 4: larger file_size_bytes beats smaller
    if a.file_size_bytes is not None and b.file_size_bytes is not None:
        if a.file_size_bytes > b.file_size_bytes:
            return -1
        if b.file_size_bytes > a.file_size_bytes:
            return 1
    elif a.file_size_bytes is not None and b.file_size_bytes is None:
        return -1
    elif b.file_size_bytes is not None and a.file_size_bytes is None:
        return 1

    # Rule 5: tie
    return 0


def _enrich_winner(
    winner: IncidentManifestRow, loser: IncidentManifestRow
) -> IncidentManifestRow:
    """
    Enrich winner with missing descriptive fields from loser.

    Descriptive fields that can be enriched:
    - title, date_occurred, date_report_released, detail_url, pdf_path

    State fields are NOT enriched (kept strictly from winner):
    - downloaded, retrieved_at, http_status, content_type, file_size_bytes, sha256, error
    """
    updates = {}

    # Enrich missing title
    if not winner.title and loser.title:
        updates["title"] = loser.title

    # Enrich missing dates
    if not winner.date_occurred and loser.date_occurred:
        updates["date_occurred"] = loser.date_occurred
    if not winner.date_report_released and loser.date_report_released:
        updates["date_report_released"] = loser.date_report_released

    # Enrich missing detail_url
    if not winner.detail_url and loser.detail_url:
        updates["detail_url"] = loser.detail_url

    # Enrich missing pdf_path
    if not winner.pdf_path and loser.pdf_path:
        updates["pdf_path"] = loser.pdf_path

    if updates:
        return winner.model_copy(update=updates)
    return winner


def merge_incident_manifests(
    existing: list[IncidentManifestRow],
    new: list[IncidentManifestRow],
) -> list[IncidentManifestRow]:
    """
    Merge existing and new manifest rows, deduplicating by key.

    Key is (source, pdf_url), or fallback to (source, incident_id) if pdf_url is empty.

    Conflict resolution picks a winner by priority:
    1. downloaded=True beats downloaded=False
    2. retrieved_at newer beats older
    3. sha256 present beats missing
    4. file_size_bytes larger beats smaller
    5. existing wins on tie

    Winner is enriched with missing descriptive fields from loser.

    Args:
        existing: Existing manifest rows (from file).
        new: Newly discovered rows.

    Returns:
        Merged and deduplicated list of rows.
    """
    # Build index of existing rows by key
    by_key: dict[tuple[str, str], IncidentManifestRow] = {}

    for row in existing:
        key = _get_merge_key(row)
        by_key[key] = row

    # Merge new rows
    for row in new:
        key = _get_merge_key(row)

        if key in by_key:
            existing_row = by_key[key]
            comparison = _compare_rows(existing_row, row)

            if comparison <= 0:
                # Existing wins or tie - enrich existing from new
                by_key[key] = _enrich_winner(existing_row, row)
            else:
                # New wins - enrich new from existing
                by_key[key] = _enrich_winner(row, existing_row)
        else:
            by_key[key] = row

    return list(by_key.values())
