"""Tests for extraction QC runner (orchestrator)."""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.extraction.runner import run_extraction_qc
from src.extraction.manifest import load_manifest
from src.extraction.extractor import ExtractionResult


def _mock_extract(pdf_path: Path) -> ExtractionResult:
    """Mock extractor that returns deterministic text based on filename."""
    name = pdf_path.stem
    if "bad" in name:
        return ExtractionResult(
            text="(cid:1)(cid:2)(cid:3)(cid:4)(cid:5) gibberish",
            extractor_used="pymupdf",
            page_count=1,
            error=None,
        )
    if "empty" in name:
        return ExtractionResult(
            text="", extractor_used="pymupdf", page_count=0, error="Empty PDF"
        )
    return ExtractionResult(
        text="The chemical release occurred at the refinery facility. " * 20,
        extractor_used="pymupdf",
        page_count=3,
        error=None,
    )


class TestRunExtractionQC:
    @patch("src.extraction.runner.extract_text", side_effect=_mock_extract)
    def test_processes_pdfs_and_writes_manifest(self, mock_ext) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pdf_dir = tmp_path / "pdfs"
            pdf_dir.mkdir()
            output_dir = tmp_path / "output"
            manifest_path = tmp_path / "manifest.csv"

            # Create fake PDF files (content doesn't matter — extractor is mocked)
            (pdf_dir / "good_report.pdf").write_bytes(b"%PDF-fake")
            (pdf_dir / "bad_encoded.pdf").write_bytes(b"%PDF-fake")
            (pdf_dir / "empty_doc.pdf").write_bytes(b"%PDF-fake")

            rows = run_extraction_qc(pdf_dir, output_dir, manifest_path)

            assert len(rows) == 3

            ok_rows = [r for r in rows if r.extraction_status == "OK"]
            failed_rows = [r for r in rows if r.extraction_status == "EXTRACTION_FAILED"]

            assert len(ok_rows) == 1
            assert len(failed_rows) == 2

            # Check that text file was written for OK row
            for r in ok_rows:
                text_file = output_dir / r.text_path
                assert text_file.exists()
                assert len(text_file.read_text(encoding="utf-8")) > 0

            # Check manifest was written
            assert manifest_path.exists()
            loaded = load_manifest(manifest_path)
            assert len(loaded) == 3

    @patch("src.extraction.runner.extract_text", side_effect=_mock_extract)
    def test_resumable_skips_existing(self, mock_ext) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pdf_dir = tmp_path / "pdfs"
            pdf_dir.mkdir()
            output_dir = tmp_path / "output"
            manifest_path = tmp_path / "manifest.csv"

            (pdf_dir / "good_report.pdf").write_bytes(b"%PDF-fake")

            # First run
            rows1 = run_extraction_qc(pdf_dir, output_dir, manifest_path)
            assert len(rows1) == 1

            # Second run — should skip (already processed)
            rows2 = run_extraction_qc(pdf_dir, output_dir, manifest_path)
            assert len(rows2) == 1  # Returns existing rows

            # With force — should reprocess
            rows3 = run_extraction_qc(pdf_dir, output_dir, manifest_path, force=True)
            assert len(rows3) == 1
