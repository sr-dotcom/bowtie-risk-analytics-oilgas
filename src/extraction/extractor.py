"""Multi-pass PDF text extraction with fallback chain."""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of PDF text extraction."""

    text: str
    extractor_used: str
    page_count: int
    error: Optional[str]


def _try_pymupdf(pdf_path: Path) -> ExtractionResult:
    """Extract text using PyMuPDF (fitz)."""
    import fitz

    doc = fitz.open(str(pdf_path))
    pages = []
    for page in doc:
        pages.append(page.get_text())
    text = "\n\n".join(pages)
    page_count = len(doc)
    doc.close()
    return ExtractionResult(
        text=text, extractor_used="pymupdf", page_count=page_count, error=None
    )


def _try_pdfminer(pdf_path: Path) -> ExtractionResult:
    """Extract text using pdfminer.six."""
    from pdfminer.high_level import extract_text as pdfminer_extract
    from pdfminer.pdfpage import PDFPage

    # Count pages
    with open(pdf_path, "rb") as f:
        page_count = sum(1 for _ in PDFPage.get_pages(f))

    text = pdfminer_extract(str(pdf_path))
    return ExtractionResult(
        text=text, extractor_used="pdfminer", page_count=page_count, error=None
    )


def _try_ocr(pdf_path: Path) -> ExtractionResult:
    """Extract text using OCR (pytesseract + pdf2image)."""
    from pdf2image import convert_from_path
    import pytesseract

    images = convert_from_path(str(pdf_path))
    pages = []
    for img in images:
        pages.append(pytesseract.image_to_string(img))
    text = "\n\n".join(pages)
    return ExtractionResult(
        text=text, extractor_used="ocr", page_count=len(images), error=None
    )


# Ordered fallback chain
_EXTRACTORS = [
    ("pymupdf", _try_pymupdf),
    ("pdfminer", _try_pdfminer),
    ("ocr", _try_ocr),
]


def extract_text(pdf_path: Path) -> ExtractionResult:
    """Extract text from PDF using fallback chain.

    Tries PyMuPDF first, then pdfminer, then OCR (if available).
    Each extractor is attempted; if it raises an exception, the next
    is tried. OCR is optional — ImportError is caught gracefully.
    """
    if not pdf_path.exists():
        return ExtractionResult(
            text="", extractor_used="none", page_count=0, error=f"File not found: {pdf_path}"
        )

    errors: list[str] = []

    for name, fn in _EXTRACTORS:
        try:
            result = fn(pdf_path)
            return result
        except ImportError:
            logger.debug(f"{name}: not available (missing dependency)")
            errors.append(f"{name}: missing dependency")
        except Exception as e:
            logger.debug(f"{name}: failed — {e}")
            errors.append(f"{name}: {e}")

    return ExtractionResult(
        text="",
        extractor_used="none",
        page_count=0,
        error="; ".join(errors),
    )
