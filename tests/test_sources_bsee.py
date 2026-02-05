import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import tempfile

from src.ingestion.sources.bsee import (
    discover_bsee_incidents,
    download_bsee_pdf,
    BSEE_DISTRICT_URL,
)
from src.ingestion.manifests import IncidentManifestRow


class TestDiscoverBseeIncidents:
    def test_returns_iterator_of_manifest_rows(self):
        mock_html = """
        <html>
        <body>
        <table>
            <tr>
                <td><a href="/reports/incident-2024.pdf">Incident Report 2024</a></td>
                <td>2024-01-15</td>
            </tr>
        </table>
        </body>
        </html>
        """

        with patch("src.ingestion.sources.bsee.requests") as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = mock_html
            mock_requests.Session.return_value.get.return_value = mock_response

            rows = list(discover_bsee_incidents(limit=1))

            for row in rows:
                assert isinstance(row, IncidentManifestRow)
                assert row.source == "bsee"
                assert row.downloaded is False


class TestDownloadBseePdf:
    def test_successful_download(self):
        row = IncidentManifestRow(
            source="bsee",
            incident_id="bsee-2024-001",
            title="BSEE Incident",
            detail_url="https://bsee.gov/reports",
            pdf_url="https://bsee.gov/report.pdf",
            pdf_path="bsee/pdfs/bsee-2024-001.pdf",
        )

        mock_session = Mock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/pdf"}
        mock_response.iter_content.return_value = [b"BSEE PDF content"]
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_session.get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            updated_row = download_bsee_pdf(row, Path(tmpdir), mock_session)

            assert updated_row.downloaded is True
            assert updated_row.http_status == 200
            assert updated_row.sha256 is not None

    def test_request_exception(self):
        import requests as req

        row = IncidentManifestRow(
            source="bsee",
            incident_id="bsee-error",
            title="Error Test",
            detail_url="",
            pdf_url="https://bsee.gov/error.pdf",
            pdf_path="bsee/pdfs/bsee-error.pdf",
        )

        mock_session = Mock()
        mock_session.get.side_effect = req.RequestException("Connection failed")

        with tempfile.TemporaryDirectory() as tmpdir:
            updated_row = download_bsee_pdf(row, Path(tmpdir), mock_session)

            assert updated_row.downloaded is False
            assert updated_row.error is not None
            assert "Connection failed" in updated_row.error
