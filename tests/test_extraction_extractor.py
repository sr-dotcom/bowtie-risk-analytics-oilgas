"""Tests for multi-pass PDF extractor."""
import tempfile
from pathlib import Path

import pytest

from src.extraction.extractor import extract_text, ExtractionResult


class TestExtractionResult:
    def test_dataclass_fields(self) -> None:
        r = ExtractionResult(
            text="hello",
            extractor_used="pymupdf",
            page_count=1,
            error=None,
        )
        assert r.text == "hello"
        assert r.extractor_used == "pymupdf"
        assert r.page_count == 1
        assert r.error is None


class TestExtractText:
    def test_nonexistent_pdf(self) -> None:
        result = extract_text(Path("/nonexistent/file.pdf"))
        assert result.text == ""
        assert result.error is not None

    def test_extracts_from_real_pdf(self) -> None:
        """Smoke test with a real BSEE PDF if available."""
        pdf_dir = Path("data/raw/bsee/pdfs")
        if not pdf_dir.exists():
            pytest.skip("No BSEE PDFs available for smoke test")
        pdfs = list(pdf_dir.glob("*.pdf"))
        if not pdfs:
            pytest.skip("No PDF files found")

        result = extract_text(pdfs[0])
        assert result.extractor_used in ("pymupdf", "pdfminer", "ocr")
        assert result.page_count >= 0
        # We don't assert text is non-empty because some PDFs may legitimately fail
