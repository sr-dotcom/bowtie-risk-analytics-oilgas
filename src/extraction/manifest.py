"""Pydantic model and I/O for extraction QC manifest."""
import csv
import logging
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class ExtractionManifestRow(BaseModel):
    """One row in the extraction QC manifest CSV."""

    model_config = ConfigDict(strict=False)

    doc_id: str
    pdf_path: str
    text_path: str
    extractor_used: str
    text_len: int
    alpha_ratio: float
    cid_ratio: float
    whitespace_ratio: float
    lang_guess: str = "unknown"
    extraction_status: Literal["OK", "EXTRACTION_FAILED"]
    fail_reason: Optional[str] = None
    extracted_at: str


def save_manifest(rows: list[ExtractionManifestRow], path: Path) -> None:
    """Write extraction manifest rows to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(ExtractionManifestRow.model_fields.keys())

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row_dict = row.model_dump()
            row_dict = {k: ("" if v is None else v) for k, v in row_dict.items()}
            writer.writerow(row_dict)


def load_manifest(path: Path) -> list[ExtractionManifestRow]:
    """Load extraction manifest from CSV. Returns empty list if file missing."""
    if not path.exists():
        return []

    rows: list[ExtractionManifestRow] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row_dict in reader:
            # Convert numeric fields
            for key in ["text_len"]:
                if key in row_dict and row_dict[key]:
                    row_dict[key] = int(row_dict[key])
            for key in ["alpha_ratio", "cid_ratio", "whitespace_ratio"]:
                if key in row_dict and row_dict[key]:
                    row_dict[key] = float(row_dict[key])
            # Handle empty optional strings
            if row_dict.get("fail_reason", "") == "":
                row_dict["fail_reason"] = None
            rows.append(ExtractionManifestRow(**row_dict))
    return rows
