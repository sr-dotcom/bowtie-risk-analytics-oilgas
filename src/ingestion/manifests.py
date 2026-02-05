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
