import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
from datetime import datetime, timezone

from src.ingestion.sources.csb import (
    discover_csb_incidents,
    download_csb_pdf,
    _extract_investigation_cards,
    CSB_COMPLETED_URL,
)
from src.ingestion.manifests import IncidentManifestRow


# -- Realistic HTML fixtures matching actual CSB page structure ---------------

# Listing page: nav links + two investigation cards + one duplicate card
_LISTING_HTML = """
<html>
<head><title>Completed Investigations</title></head>
<body>
<nav>
  <a href="/investigations/">Investigations</a>
  <a href="/investigations/completed-investigations/?Type=2">Completed</a>
  <a href="/investigations/data-quality-/">Data Quality</a>
  <a href="/about/">About</a>
</nav>
<div class="investigation-list">
  <div class="card">
    <a href="/acme-refinery-fire-/">
      <img src="/assets/thumb1.jpg" alt="">
      <p><strong>Acme Refinery Fire</strong></p>
      <p><strong>Location:</strong> Houston, TX</p>
      <p><strong>Final Report Released On:</strong> 01/15/2024</p>
    </a>
    <a href="/acme-refinery-fire-/">full Investigation details</a>
  </div>
  <div class="card">
    <a href="/beta-chemical-release-/">
      <img src="/assets/thumb2.jpg" alt="">
      <p><strong>Beta Chemical Release</strong></p>
      <p><strong>Location:</strong> Baton Rouge, LA</p>
    </a>
    <a href="/beta-chemical-release-/">full Investigation details</a>
  </div>
  <div class="card">
    <a href="/acme-refinery-fire-/">
      <img src="/assets/thumb1dup.jpg" alt="">
      <p>Duplicate card on same page</p>
    </a>
    <a href="/acme-refinery-fire-/">full Investigation details</a>
  </div>
</div>
</body>
</html>
"""

# Detail page with a PDF link and a date
_DETAIL_HTML = """
<html><body>
<h1>Acme Refinery Fire</h1>
<p><strong>Final Report Released On:</strong> 01/15/2024</p>
<a href="/file-library/acme-final-report.pdf">Final Report (PDF)</a>
</body></html>
"""


class TestExtractInvestigationCards:
    def test_extracts_only_card_links(self):
        cards = _extract_investigation_cards(_LISTING_HTML)
        slugs = [path.strip("/") for path, _ in cards]
        # Must find the two investigation cards
        assert "acme-refinery-fire-" in slugs
        assert "beta-chemical-release-" in slugs
        # Must NOT include nav/deny-listed slugs
        assert "investigations" not in slugs
        assert "data-quality-" not in slugs
        assert "completed-investigations" not in slugs
        assert "about" not in slugs

    def test_returns_titles(self):
        cards = _extract_investigation_cards(_LISTING_HTML)
        titles = [title for _, title in cards]
        # Titles are derived from slugs (slug.replace("-"," ").title())
        assert len(titles) == 2
        assert all(t for t in titles)  # non-empty

    def test_empty_html_returns_empty(self):
        assert _extract_investigation_cards("<html><body></body></html>") == []


class TestDiscoverCsbIncidents:
    def test_returns_iterator_of_manifest_rows(self):
        with patch("src.ingestion.sources.csb.requests") as mock_requests:
            mock_session = Mock(headers={})
            mock_requests.Session.return_value = mock_session
            mock_empty = Mock(status_code=200, text="<html><body></body></html>")
            mock_session.get.side_effect = [
                Mock(status_code=200, text=_LISTING_HTML),  # listing page 1
                Mock(status_code=200, text=_DETAIL_HTML),   # detail for acme
                Mock(status_code=200, text=_DETAIL_HTML),   # detail for beta
                mock_empty,                                  # listing page 2 (empty)
            ]

            rows = list(discover_csb_incidents(limit=5))

            assert len(rows) == 2
            for row in rows:
                assert isinstance(row, IncidentManifestRow)
                assert row.source == "csb"
                assert row.downloaded is False

    def test_respects_limit(self):
        with patch("src.ingestion.sources.csb.requests") as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "<html><body></body></html>"
            mock_requests.Session.return_value.get.return_value = mock_response

            rows = list(discover_csb_incidents(limit=5))
            assert len(rows) <= 5

    def test_filters_nav_links_and_deduplicates(self):
        """Nav links like /data-quality- must not appear; duplicates must be merged."""
        with patch("src.ingestion.sources.csb.requests") as mock_requests:
            mock_session = Mock(headers={})
            mock_requests.Session.return_value = mock_session

            mock_list_resp = Mock(status_code=200, text=_LISTING_HTML)
            mock_detail_resp = Mock(status_code=200, text=_DETAIL_HTML)
            # empty page 2 to stop pagination
            mock_empty_resp = Mock(status_code=200, text="<html><body></body></html>")
            mock_session.get.side_effect = [
                mock_list_resp,   # listing page 1
                mock_detail_resp, # detail for acme
                mock_detail_resp, # detail for beta
                # acme duplicate is skipped (dedup), so no 3rd detail fetch
                mock_empty_resp,  # listing page 2 (empty → stop)
            ]

            rows = list(discover_csb_incidents(limit=10))

            ids = [r.incident_id for r in rows]
            # Exactly 2 unique incidents
            assert len(ids) == 2
            assert "acme-refinery-fire-" in ids
            assert "beta-chemical-release-" in ids
            # No denied slugs
            assert "data-quality-" not in ids
            assert "data-quality" not in ids
            assert "investigations" not in ids

    def test_incident_id_from_slug_not_title(self):
        """incident_id must come from URL slug, not _slugify(title)."""
        with patch("src.ingestion.sources.csb.requests") as mock_requests:
            mock_session = Mock(headers={})
            mock_requests.Session.return_value = mock_session
            mock_session.get.side_effect = [
                Mock(status_code=200, text=_LISTING_HTML),
                Mock(status_code=200, text=_DETAIL_HTML),
                Mock(status_code=200, text=_DETAIL_HTML),
            ]

            rows = list(discover_csb_incidents(limit=2))
            # incident_ids come from URL slugs, not _slugify(title)
            ids = {r.incident_id for r in rows}
            assert "acme-refinery-fire-" in ids
            assert "beta-chemical-release-" in ids


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
