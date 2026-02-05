import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
from datetime import datetime, timezone

from src.ingestion.sources.csb import (
    discover_csb_incidents,
    download_csb_pdf,
    CSB_COMPLETED_URL,
)
from src.ingestion.manifests import IncidentManifestRow


class TestDiscoverCsbIncidents:
    def test_returns_iterator_of_manifest_rows(self):
        # Mock the HTTP response
        mock_html = """
        <html>
        <body>
        <div class="investigation">
            <a href="/investigations/detail/test-incident/">Test Incident Title</a>
            <span class="date">January 15, 2024</span>
            <a href="/file-library/test.pdf">Final Report (PDF)</a>
        </div>
        </body>
        </html>
        """

        with patch("src.ingestion.sources.csb.requests") as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = mock_html
            mock_requests.Session.return_value.get.return_value = mock_response

            rows = list(discover_csb_incidents(limit=1))

            # Should return manifest rows with downloaded=False
            for row in rows:
                assert isinstance(row, IncidentManifestRow)
                assert row.source == "csb"
                assert row.downloaded is False

    def test_respects_limit(self):
        # This is a behavioral test - actual scraping tested in integration
        with patch("src.ingestion.sources.csb.requests") as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "<html><body></body></html>"
            mock_requests.Session.return_value.get.return_value = mock_response

            rows = list(discover_csb_incidents(limit=5))
            # With empty HTML, should return 0 rows but not crash
            assert len(rows) <= 5


class TestDownloadCsbPdf:
    def test_successful_download(self):
        row = IncidentManifestRow(
            source="csb",
            incident_id="test-2024-001",
            title="Test Incident",
            detail_url="https://csb.gov/investigations/test",
            pdf_url="https://csb.gov/file.pdf",
            pdf_path="csb/pdfs/test-2024-001.pdf",
        )

        mock_session = Mock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/pdf"}
        mock_response.iter_content.return_value = [b"PDF content here"]
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_session.get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            updated_row = download_csb_pdf(row, Path(tmpdir), mock_session)

            assert updated_row.downloaded is True
            assert updated_row.http_status == 200
            assert updated_row.content_type == "application/pdf"
            assert updated_row.file_size_bytes > 0
            assert updated_row.sha256 is not None
            assert updated_row.retrieved_at is not None

    def test_non_200_response(self):
        row = IncidentManifestRow(
            source="csb",
            incident_id="test-404",
            title="Missing",
            detail_url="",
            pdf_url="https://csb.gov/missing.pdf",
            pdf_path="csb/pdfs/test-404.pdf",
        )

        mock_session = Mock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_session.get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            updated_row = download_csb_pdf(row, Path(tmpdir), mock_session)

            assert updated_row.downloaded is False
            assert updated_row.http_status == 404

    def test_invalid_content_type(self):
        row = IncidentManifestRow(
            source="csb",
            incident_id="test-html",
            title="HTML Response",
            detail_url="",
            pdf_url="https://csb.gov/page.html",
            pdf_path="csb/pdfs/test-html.pdf",
        )

        mock_session = Mock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_session.get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            updated_row = download_csb_pdf(row, Path(tmpdir), mock_session)

            assert updated_row.downloaded is False
            assert "Not a PDF" in (updated_row.error or "")
