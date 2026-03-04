"""corpus_v1 manifest builder.

Scans corpus_v1/raw_pdfs/ and corpus_v1/structured_json/ to produce
a corpus_v1_manifest.csv with one row per PDF.
"""
import csv
import pathlib
import urllib.parse
from typing import Any

CORPUS_V1_ROOT = pathlib.Path("data/corpus_v1")
BSEE_PDFS_DIR  = pathlib.Path("data/raw/bsee/pdf")

_MANIFEST_COLUMNS = [
    "incident_id",
    "source_agency",
    "pdf_filename",
    "pdf_path",
    "json_path",
    "extraction_status",
]


def _bsee_stems() -> set[str]:
    """Return URL-decoded stems of every PDF in the canonical BSEE directory."""
    if not BSEE_PDFS_DIR.exists():
        return set()
    return {urllib.parse.unquote(f.stem) for f in BSEE_PDFS_DIR.glob("*.pdf")}


def build_manifest() -> list[dict[str, Any]]:
    """Cross-reference raw_pdfs/ vs structured_json/ and return manifest rows.

    Each row has keys: incident_id, source_agency, pdf_filename, pdf_path,
    json_path, extraction_status.
    """
    raw_pdfs   = CORPUS_V1_ROOT / "raw_pdfs"
    structured = CORPUS_V1_ROOT / "structured_json"

    if not raw_pdfs.exists():
        return []

    bsee = _bsee_stems()
    json_by_stem = {
        urllib.parse.unquote(f.stem): f
        for f in structured.glob("*.json")
    } if structured.exists() else {}

    rows: list[dict[str, Any]] = []
    for pdf in sorted(raw_pdfs.glob("*.pdf")):
        stem   = urllib.parse.unquote(pdf.stem)
        agency = "BSEE" if stem in bsee else "CSB"
        json_f = json_by_stem.get(stem)

        rows.append({
            "incident_id":       stem,
            "source_agency":     agency,
            "pdf_filename":      pdf.name,
            "pdf_path":          str(pdf),
            "json_path":         str(json_f) if json_f else "PENDING",
            "extraction_status": "ready" if json_f else "needs_extraction",
        })
    return rows


def write_manifest(
    rows: list[dict[str, Any]],
    out_path: pathlib.Path,
) -> pathlib.Path:
    """Write rows to a CSV file at out_path.  Returns out_path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return out_path
