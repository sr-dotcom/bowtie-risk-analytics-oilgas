import pytest
from pathlib import Path
import tempfile
from datetime import datetime, timezone

from src.ingestion.pdf_text import extract_text_from_pdf, process_incident_manifest
from src.ingestion.manifests import IncidentManifestRow, TextManifestRow


class TestExtractTextFromPdf:
    def test_nonexistent_file_returns_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "nonexistent.pdf"
            text_path = Path(tmpdir) / "output.txt"

            text, page_count, char_count, error = extract_text_from_pdf(
                pdf_path, text_path
            )

            assert text == ""
            assert page_count == 0
            assert char_count == 0
            assert error == "PDF not found"
            assert not text_path.exists()

    def test_creates_output_directory(self):
        # This test uses a minimal valid PDF if available
        # For now, test the directory creation logic
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "test.pdf"
            text_path = Path(tmpdir) / "nested" / "deep" / "output.txt"

            # Create a minimal PDF-like file (will fail extraction but test dir creation)
            pdf_path.write_bytes(b"%PDF-1.4 minimal")

            text, page_count, char_count, error = extract_text_from_pdf(
                pdf_path, text_path
            )

            # Should attempt extraction (may fail on invalid PDF, that's fine)
            # The key is it shouldn't crash on missing parent dirs
            assert text_path.parent.exists()


class TestProcessIncidentManifest:
    def test_skips_not_downloaded(self):
        rows = [
            IncidentManifestRow(
                source="csb",
                incident_id="test-1",
                title="Test",
                detail_url="",
                pdf_url="",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=False,
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = process_incident_manifest(rows, Path(tmpdir))
            assert len(result) == 0

    def test_generates_correct_text_path(self):
        # Test path transformation logic
        rows = [
            IncidentManifestRow(
                source="csb",
                incident_id="test-1",
                title="Test",
                detail_url="",
                pdf_url="",
                pdf_path="csb/pdfs/test-report.pdf",
                downloaded=True,
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            # Create the PDF file (minimal content)
            pdf_full = base_dir / "csb" / "pdfs" / "test-report.pdf"
            pdf_full.parent.mkdir(parents=True)
            pdf_full.write_bytes(b"%PDF-1.4 minimal")

            result = process_incident_manifest(rows, base_dir)

            assert len(result) == 1
            assert result[0].text_path == "csb/text/test-report.txt"
            assert result[0].source == "csb"
            assert result[0].incident_id == "test-1"
