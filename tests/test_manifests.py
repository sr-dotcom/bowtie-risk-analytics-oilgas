import pytest
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import csv

from src.ingestion.manifests import (
    IncidentManifestRow,
    TextManifestRow,
    load_incident_manifest,
    save_incident_manifest,
    load_text_manifest,
    save_text_manifest,
)


class TestIncidentManifestRow:
    def test_create_minimal(self):
        row = IncidentManifestRow(
            source="csb",
            incident_id="2023-01-I-TX",
            title="Test Incident",
            detail_url="https://csb.gov/investigations/test",
            pdf_url="https://csb.gov/file.pdf",
            pdf_path="csb/pdfs/2023-01-I-TX.pdf",
        )
        assert row.source == "csb"
        assert row.downloaded is False
        assert row.sha256 is None

    def test_source_literal_validation(self):
        with pytest.raises(ValueError):
            IncidentManifestRow(
                source="invalid",
                incident_id="test",
                title="Test",
                detail_url="",
                pdf_url="",
                pdf_path="",
            )

    def test_full_row(self):
        now = datetime.now(timezone.utc)
        row = IncidentManifestRow(
            source="bsee",
            incident_id="BSEE-2024-001",
            title="Offshore Incident",
            date_occurred="2024-01-15",
            date_report_released="2024-06-01",
            detail_url="https://bsee.gov/report",
            pdf_url="https://bsee.gov/report.pdf",
            pdf_path="bsee/pdfs/BSEE-2024-001.pdf",
            downloaded=True,
            retrieved_at=now,
            http_status=200,
            content_type="application/pdf",
            file_size_bytes=12345,
            sha256="abc123",
        )
        assert row.downloaded is True
        assert row.retrieved_at == now

    def test_extra_fields_ignored(self):
        row = IncidentManifestRow(
            source="csb",
            incident_id="test",
            title="Test",
            detail_url="",
            pdf_url="",
            pdf_path="",
            unknown_field="ignored",
        )
        assert not hasattr(row, "unknown_field")


class TestTextManifestRow:
    def test_create_minimal(self):
        row = TextManifestRow(
            source="csb",
            incident_id="2023-01-I-TX",
            pdf_path="csb/pdfs/2023-01-I-TX.pdf",
            text_path="csb/text/2023-01-I-TX.txt",
        )
        assert row.extracted is False
        assert row.extractor == "pdfplumber"
        assert row.is_empty is False

    def test_full_row(self):
        now = datetime.now(timezone.utc)
        row = TextManifestRow(
            source="csb",
            incident_id="test",
            pdf_path="csb/pdfs/test.pdf",
            text_path="csb/text/test.txt",
            extracted=True,
            extracted_at=now,
            extractor="pdfplumber",
            page_count=10,
            char_count=5000,
            is_empty=False,
            error=None,
        )
        assert row.page_count == 10
        assert row.char_count == 5000


class TestManifestIO:
    def test_save_and_load_incident_manifest(self):
        rows = [
            IncidentManifestRow(
                source="csb",
                incident_id="test-1",
                title="Test 1",
                detail_url="https://example.com/1",
                pdf_url="https://example.com/1.pdf",
                pdf_path="csb/pdfs/test-1.pdf",
                downloaded=True,
                http_status=200,
            ),
            IncidentManifestRow(
                source="bsee",
                incident_id="test-2",
                title="Test 2",
                detail_url="https://example.com/2",
                pdf_url="https://example.com/2.pdf",
                pdf_path="bsee/pdfs/test-2.pdf",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "manifest.csv"
            save_incident_manifest(rows, path)

            assert path.exists()

            loaded = load_incident_manifest(path)
            assert len(loaded) == 2
            assert loaded[0].incident_id == "test-1"
            assert loaded[0].downloaded is True
            assert loaded[1].source == "bsee"

    def test_save_and_load_text_manifest(self):
        now = datetime.now(timezone.utc)
        rows = [
            TextManifestRow(
                source="csb",
                incident_id="test-1",
                pdf_path="csb/pdfs/test-1.pdf",
                text_path="csb/text/test-1.txt",
                extracted=True,
                extracted_at=now,
                page_count=5,
                char_count=1000,
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "text_manifest.csv"
            save_text_manifest(rows, path)

            loaded = load_text_manifest(path)
            assert len(loaded) == 1
            assert loaded[0].extracted is True
            assert loaded[0].page_count == 5

    def test_load_nonexistent_returns_empty(self):
        result = load_incident_manifest(Path("/nonexistent/path.csv"))
        assert result == []

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "nested" / "manifest.csv"
            save_incident_manifest([], path)
            assert path.exists()
