"""Tests for extraction manifest model and I/O."""
import tempfile
from pathlib import Path

import pytest

from src.extraction.manifest import (
    ExtractionManifestRow,
    save_manifest,
    load_manifest,
)


class TestExtractionManifestRow:
    def test_ok_row(self) -> None:
        row = ExtractionManifestRow(
            doc_id="test-001",
            pdf_path="bsee/pdfs/test.pdf",
            text_path="text/test-001.txt",
            extractor_used="pymupdf",
            text_len=5000,
            alpha_ratio=0.82,
            cid_ratio=0.0,
            whitespace_ratio=0.15,
            lang_guess="unknown",
            extraction_status="OK",
            fail_reason=None,
            extracted_at="2026-02-14T12:00:00",
        )
        assert row.extraction_status == "OK"
        assert row.fail_reason is None

    def test_failed_row(self) -> None:
        row = ExtractionManifestRow(
            doc_id="test-002",
            pdf_path="bsee/pdfs/bad.pdf",
            text_path="",
            extractor_used="pymupdf",
            text_len=50,
            alpha_ratio=0.1,
            cid_ratio=0.5,
            whitespace_ratio=0.8,
            lang_guess="unknown",
            extraction_status="EXTRACTION_FAILED",
            fail_reason="CID_ENCODING_GIBBERISH",
            extracted_at="2026-02-14T12:00:00",
        )
        assert row.extraction_status == "EXTRACTION_FAILED"
        assert row.fail_reason == "CID_ENCODING_GIBBERISH"


class TestManifestIO:
    def test_round_trip(self) -> None:
        rows = [
            ExtractionManifestRow(
                doc_id="doc-001",
                pdf_path="pdfs/a.pdf",
                text_path="text/doc-001.txt",
                extractor_used="pymupdf",
                text_len=3000,
                alpha_ratio=0.80,
                cid_ratio=0.001,
                whitespace_ratio=0.12,
                lang_guess="unknown",
                extraction_status="OK",
                fail_reason=None,
                extracted_at="2026-02-14T10:00:00",
            ),
            ExtractionManifestRow(
                doc_id="doc-002",
                pdf_path="pdfs/b.pdf",
                text_path="",
                extractor_used="pdfminer",
                text_len=100,
                alpha_ratio=0.30,
                cid_ratio=0.20,
                whitespace_ratio=0.50,
                lang_guess="unknown",
                extraction_status="EXTRACTION_FAILED",
                fail_reason="LOW_ALPHA_GIBBERISH",
                extracted_at="2026-02-14T10:01:00",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.csv"
            save_manifest(rows, path)
            loaded = load_manifest(path)

        assert len(loaded) == 2
        assert loaded[0].doc_id == "doc-001"
        assert loaded[0].extraction_status == "OK"
        assert loaded[0].alpha_ratio == 0.80
        assert loaded[1].doc_id == "doc-002"
        assert loaded[1].extraction_status == "EXTRACTION_FAILED"
        assert loaded[1].fail_reason == "LOW_ALPHA_GIBBERISH"

    def test_load_nonexistent_returns_empty(self) -> None:
        result = load_manifest(Path("/nonexistent/manifest.csv"))
        assert result == []
