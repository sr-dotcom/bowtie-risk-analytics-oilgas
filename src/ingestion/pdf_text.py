"""PDF text extraction using pdfplumber."""
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pdfplumber

from src.ingestion.manifests import TextManifestRow, IncidentManifestRow

logger = logging.getLogger(__name__)


def extract_text_from_pdf(
    pdf_path: Path,
    text_path: Path,
) -> tuple[str, int, int, Optional[str]]:
    """
    Extract text from PDF using pdfplumber.

    Args:
        pdf_path: Path to input PDF file.
        text_path: Path to output text file.

    Returns:
        Tuple of (text_content, page_count, char_count, error_or_none)
    """
    if not pdf_path.exists():
        return "", 0, 0, "PDF not found"

    # Ensure output directory exists
    text_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            pages_text = []

            for i, page in enumerate(pdf.pages):
                try:
                    text = page.extract_text() or ""
                    # Strip trailing whitespace per page
                    pages_text.append(text.rstrip())
                except Exception as e:
                    logger.warning(f"Page {i + 1} extraction failed: {e}")
                    pages_text.append("")

            full_text = "\n\n".join(pages_text)
            char_count = len(full_text)

            # Write to text file
            text_path.write_text(full_text, encoding="utf-8")

            return full_text, page_count, char_count, None

    except Exception as e:
        logger.warning(f"Failed to extract text from {pdf_path}: {e}")
        return "", 0, 0, str(e)


def _compute_text_path(pdf_path_str: str) -> str:
    """
    Convert PDF path to text path.

    Example: csb/pdfs/report.pdf -> csb/text/report.txt
    """
    # Normalize to forward slashes for consistency
    normalized = pdf_path_str.replace("\\", "/")
    parts = normalized.split("/")

    # Find and replace 'pdfs' with 'text'
    for i, part in enumerate(parts):
        if part == "pdfs":
            parts[i] = "text"
            break

    # Change extension
    result = "/".join(parts)
    if result.endswith(".pdf"):
        result = result[:-4] + ".txt"
    return result


def process_incident_manifest(
    incident_manifest: list[IncidentManifestRow],
    base_dir: Path,
) -> list[TextManifestRow]:
    """
    Process all downloaded PDFs from incident manifest.

    Args:
        incident_manifest: List of incident manifest rows.
        base_dir: Base directory for PDF and text files.

    Returns:
        List of text manifest rows.
    """
    text_rows = []

    for row in incident_manifest:
        if not row.downloaded:
            continue

        pdf_path = base_dir / row.pdf_path
        text_rel_path = _compute_text_path(row.pdf_path)
        text_path = base_dir / text_rel_path

        _, page_count, char_count, error = extract_text_from_pdf(pdf_path, text_path)

        text_row = TextManifestRow(
            source=row.source,
            incident_id=row.incident_id,
            pdf_path=row.pdf_path,
            text_path=text_rel_path,
            extracted=(error is None),
            extracted_at=datetime.now(timezone.utc),
            extractor="pdfplumber",
            page_count=page_count,
            char_count=char_count,
            is_empty=(char_count == 0),
            error=error,
        )
        text_rows.append(text_row)

        if error:
            logger.warning(f"{row.incident_id}: extraction failed - {error}")
        elif char_count == 0:
            logger.warning(f"{row.incident_id}: extracted 0 chars (scanned PDF?)")
        else:
            logger.info(f"{row.incident_id}: {page_count} pages, {char_count} chars")

    return text_rows
