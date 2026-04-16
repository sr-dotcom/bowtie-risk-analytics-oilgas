import sys
"""Tests for source discovery adapters (CSB, BSEE, PHMSA). All offline."""
import csv
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.ingestion.sources.csb_discover import (
    _score_pdf_href,
    discover_csb,
    parse_detail_page,
    parse_listing_page,
    write_metadata,
    write_url_list,
)
from src.ingestion.sources.bsee_discover import (
    discover_bsee,
    parse_bsee_listing,
    write_url_list as bsee_write_url_list,
    write_metadata as bsee_write_metadata,
)
from src.ingestion.sources.phmsa_discover import (
    discover_phmsa,
    parse_phmsa_page,
    parse_phmsa_incident_csv,
    write_url_list as phmsa_write_url_list,
    write_metadata as phmsa_write_metadata,
)


# ── CSB HTML fixtures ───────────────────────────────────────────────────

CSB_LISTING_HTML = """
<html><body>
<nav>
  <a href="/investigations/">Investigations</a>
  <a href="/about/">About</a>
</nav>
<div class="investigation-list">
  <div class="card">
    <a href="/acme-refinery-fire-2024/">
      <p><strong>Acme Refinery Fire</strong></p>
      <p><strong>Final Report Released On:</strong> 01/15/2024</p>
    </a>
    <a href="/acme-refinery-fire-2024/">full Investigation details</a>
  </div>
  <div class="card">
    <a href="/beta-chemical-release/">
      <p><strong>Beta Chemical Release</strong></p>
    </a>
    <a href="/beta-chemical-release/">full Investigation details</a>
  </div>
  <div class="card">
    <a href="/acme-refinery-fire-2024/">
      <p>Duplicate card</p>
    </a>
    <a href="/acme-refinery-fire-2024/">full Investigation details</a>
  </div>
</div>
</body></html>
"""

CSB_DETAIL_HTML = """
<html><body>
<h1>Acme Refinery Fire</h1>
<p><strong>Final Report Released On:</strong> 01/15/2024</p>
<a href="/file.aspx?DocumentId=6304">FINAL REPORT: Acme Refinery Fire Investigation Report</a>
<a href="/file.aspx?DocumentId=6303">FINAL REPORT: Appendix A - Supporting Data</a>
<a href="/assets/recommendation/Status_Change_Summary_EPA_(Acme_R4).pdf">Status Change Summary</a>
</body></html>
"""

CSB_DETAIL_NO_PDF = """
<html><body>
<h1>No PDF Here</h1>
<p>This investigation has no report yet.</p>
</body></html>
"""


# ── BSEE HTML fixture ───────────────────────────────────────────────────

BSEE_LISTING_HTML = """
<html><body>
<table>
  <tr>
    <td><a href="/sites/bsee.gov/files/reports/gom-2024-001.pdf">GOM District Report 2024-001</a></td>
    <td>2024-03-15</td>
  </tr>
  <tr>
    <td><a href="/sites/bsee.gov/files/reports/gom-2023-042.pdf">GOM District Report 2023-042</a></td>
    <td>2023-11-01</td>
  </tr>
  <tr>
    <td><a href="/sites/bsee.gov/files/reports/gom-2024-001.pdf">Duplicate Link</a></td>
  </tr>
</table>
</body></html>
"""


# ── PHMSA HTML fixture ──────────────────────────────────────────────────

PHMSA_DATA_HTML = """
<html><body>
<h2>Pipeline Incident Data</h2>
<ul>
  <li><a href="/data/pipeline-incidents-2023.csv">Pipeline Incidents 2023 (CSV)</a></li>
  <li><a href="/data/pipeline-incidents-2022.xlsx">Pipeline Incidents 2022 (XLSX)</a></li>
  <li><a href="/docs/some-guide.pdf">Safety Guide (PDF)</a></li>
</ul>
</body></html>
"""


# ═══════════════════════════════════════════════════════════════════════
# CSB tests
# ═══════════════════════════════════════════════════════════════════════


class TestCsbParseListingPage:
    def test_extracts_investigation_cards(self) -> None:
        cards = parse_listing_page(CSB_LISTING_HTML)
        slugs = [path.strip("/") for path, _ in cards]
        assert "acme-refinery-fire-2024" in slugs
        assert "beta-chemical-release" in slugs

    def test_deduplicates(self) -> None:
        cards = parse_listing_page(CSB_LISTING_HTML)
        assert len(cards) == 2  # duplicate acme card collapsed

    def test_excludes_denylist(self) -> None:
        cards = parse_listing_page(CSB_LISTING_HTML)
        slugs = [path.strip("/") for path, _ in cards]
        assert "investigations" not in slugs
        assert "about" not in slugs

    def test_empty_html(self) -> None:
        assert parse_listing_page("<html><body></body></html>") == []


class TestCsbParseDetailPage:
    def test_extracts_pdf_url(self) -> None:
        info = parse_detail_page(CSB_DETAIL_HTML, "https://www.csb.gov")
        assert info["pdf_url"] == "https://www.csb.gov/file.aspx?DocumentId=6304"

    def test_extracts_title(self) -> None:
        info = parse_detail_page(CSB_DETAIL_HTML)
        assert info["title"] == "Acme Refinery Fire"

    def test_extracts_date(self) -> None:
        info = parse_detail_page(CSB_DETAIL_HTML)
        assert info["date"] == "2024-01-15"

    def test_no_pdf(self) -> None:
        info = parse_detail_page(CSB_DETAIL_NO_PDF)
        assert info["pdf_url"] is None

    def test_prefers_final_report_keyword(self) -> None:
        html = """
        <a href="/file-library/appendix.pdf">Appendix</a>
        <a href="/file-library/final-report.pdf">Report</a>
        """
        info = parse_detail_page(html, "https://www.csb.gov")
        assert "final-report.pdf" in info["pdf_url"]


class TestCsbPdfScoring:
    """Regression tests: parse_detail_page must prefer DocumentId final report
    links and must NOT pick recommendation/status-change-summary PDFs."""

    # Realistic detail page: DocumentId final report + recommendation PDFs
    _DETAIL_WITH_DOCUMENTID = """
    <html><body>
    <h1>Acme Chemical Explosion</h1>
    <p><strong>Final Report Released On:</strong> 03/10/2023</p>
    <a href="/assets/recommendation/Status_Change_Summary_EPA_(Acme_R4).pdf">Status Change Summary</a>
    <a href="/assets/recommendation/SCS2.pdf">SCS2</a>
    <a href="/file.aspx?DocumentId=6304">FINAL REPORT: Acme Chemical Explosion Investigation Report</a>
    <a href="/file.aspx?DocumentId=6303">FINAL REPORT: Appendix A</a>
    <a href="/assets/recommendation/Status_Change_Summary_OSHA_(Acme_R1).pdf">Status Change Summary OSHA</a>
    </body></html>
    """

    # Page with only non-recommendation .pdf links (no DocumentId) — tier 2
    _DETAIL_WITH_GOOD_PDF = """
    <html><body>
    <h1>Beta Plant Fire</h1>
    <a href="/assets/recommendation/SCS3.pdf">SCS3</a>
    <a href="/file-library/Beta-Final-Investigation-Report.pdf">Final Report</a>
    <a href="/assets/recommendation/Status_Change_Summary_OSHA.pdf">SCS OSHA</a>
    </body></html>
    """

    # Detail page with ONLY recommendation PDFs
    _DETAIL_ONLY_RECOMMENDATIONS = """
    <html><body>
    <h1>Gamma Plant Leak</h1>
    <a href="/assets/recommendation/Status_Change_Summary_Gamma.pdf">SCS</a>
    <a href="/assets/recommendation/SCS5.pdf">SCS5</a>
    </body></html>
    """

    def test_picks_documentid_over_recommendation(self) -> None:
        info = parse_detail_page(self._DETAIL_WITH_DOCUMENTID, "https://www.csb.gov")
        assert info["pdf_url"] is not None
        assert "file.aspx?DocumentId=6304" in info["pdf_url"]
        assert "/assets/recommendation/" not in info["pdf_url"]

    def test_picks_main_report_not_appendix(self) -> None:
        info = parse_detail_page(self._DETAIL_WITH_DOCUMENTID, "https://www.csb.gov")
        # Should be 6304 (main), not 6303 (appendix)
        assert "DocumentId=6304" in info["pdf_url"]

    def test_tier2_pdf_over_recommendation(self) -> None:
        info = parse_detail_page(self._DETAIL_WITH_GOOD_PDF, "https://www.csb.gov")
        assert info["pdf_url"] is not None
        assert "Final-Investigation-Report" in info["pdf_url"]
        assert "/assets/recommendation/" not in info["pdf_url"]

    def test_only_recommendations_still_returns_something(self) -> None:
        """If only bad PDFs exist, pick one rather than returning None."""
        info = parse_detail_page(self._DETAIL_ONLY_RECOMMENDATIONS, "https://www.csb.gov")
        assert info["pdf_url"] is not None
        assert info["pdf_url"].endswith(".pdf")

    def test_score_function_penalties(self) -> None:
        assert _score_pdf_href("/assets/recommendation/SCS2.pdf") < 0
        assert _score_pdf_href("/assets/recommendation/Status_Change_Summary_X.pdf") < 0
        assert _score_pdf_href("/file-library/final-report.pdf") > 0
        good = _score_pdf_href("/file-library/final-investigation-report.pdf")
        bad = _score_pdf_href("/assets/recommendation/Status_Change_Summary_Report.pdf")
        assert good > bad


class TestCsbDiscoverOffline:
    def test_discover_with_mocked_requests(self) -> None:
        with patch("src.ingestion.sources.csb_discover.requests") as mock_req:
            session = Mock(headers={})
            mock_req.Session.return_value = session

            # Page 1 listing -> 2 cards; Page 2 listing -> empty (stops)
            empty_html = "<html><body></body></html>"
            session.get.side_effect = [
                Mock(status_code=200, text=CSB_LISTING_HTML),   # listing p1
                Mock(status_code=200, text=CSB_DETAIL_HTML),    # detail acme
                Mock(status_code=200, text=CSB_DETAIL_HTML),    # detail beta
                Mock(status_code=200, text=empty_html),         # listing p2
            ]

            results = discover_csb(limit=10, sleep=0)
            assert len(results) == 2
            assert all(r["source"] == "csb" for r in results)
            assert all(r["url"] for r in results)  # non-empty URLs
            assert all(r["doc_id"] for r in results)

    def test_limit_respected(self) -> None:
        with patch("src.ingestion.sources.csb_discover.requests") as mock_req:
            session = Mock(headers={})
            mock_req.Session.return_value = session
            session.get.side_effect = [
                Mock(status_code=200, text=CSB_LISTING_HTML),
                Mock(status_code=200, text=CSB_DETAIL_HTML),
            ]
            results = discover_csb(limit=1, sleep=0)
            assert len(results) == 1

    def test_handles_network_error(self) -> None:
        with patch("src.ingestion.sources.csb_discover.requests") as mock_req:
            import requests as real_requests
            session = Mock(headers={})
            mock_req.Session.return_value = session
            mock_req.RequestException = real_requests.RequestException
            session.get.side_effect = real_requests.RequestException("timeout")
            results = discover_csb(limit=5, sleep=0)
            assert results == []

    def test_doc_id_stability(self) -> None:
        """Same HTML should produce same doc_ids every time."""
        with patch("src.ingestion.sources.csb_discover.requests") as mock_req:
            session = Mock(headers={})
            mock_req.Session.return_value = session

            def make_responses():
                return [
                    Mock(status_code=200, text=CSB_LISTING_HTML),
                    Mock(status_code=200, text=CSB_DETAIL_HTML),
                    Mock(status_code=200, text=CSB_DETAIL_HTML),
                    Mock(status_code=200, text="<html></html>"),
                ]

            session.get.side_effect = make_responses()
            r1 = discover_csb(limit=10, sleep=0)

            session.get.side_effect = make_responses()
            r2 = discover_csb(limit=10, sleep=0)

            assert [r["doc_id"] for r in r1] == [r["doc_id"] for r in r2]


class TestCsbCsvWriters:
    def test_write_url_list(self, tmp_path: Path) -> None:
        results = [
            {"doc_id": "test-1", "url": "https://example.com/1.pdf", "source": "csb"},
            {"doc_id": "test-2", "url": "https://example.com/2.pdf", "source": "csb"},
        ]
        out = tmp_path / "url_list.csv"
        write_url_list(results, out)

        with open(out, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["doc_id"] == "test-1"
        assert rows[0]["url"] == "https://example.com/1.pdf"

    def test_write_metadata(self, tmp_path: Path) -> None:
        results = [
            {
                "doc_id": "t1", "url": "https://x.com/1.pdf",
                "title": "Test", "date": "2024-01-01",
                "page_url": "https://x.com/page", "source": "csb",
            },
        ]
        out = tmp_path / "meta.csv"
        write_metadata(results, out)

        with open(out, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert set(rows[0].keys()) == {"doc_id", "title", "date", "page_url", "url", "source"}


# ═══════════════════════════════════════════════════════════════════════
# BSEE tests
# ═══════════════════════════════════════════════════════════════════════


class TestBseeParseListingPage:
    def test_extracts_pdf_links(self) -> None:
        records = parse_bsee_listing(BSEE_LISTING_HTML, "https://www.bsee.gov")
        assert len(records) == 2  # duplicate collapsed

    def test_doc_id_from_filename(self) -> None:
        records = parse_bsee_listing(BSEE_LISTING_HTML, "https://www.bsee.gov")
        ids = [r["doc_id"] for r in records]
        assert "gom-2024-001" in ids
        assert "gom-2023-042" in ids

    def test_all_have_urls(self) -> None:
        records = parse_bsee_listing(BSEE_LISTING_HTML, "https://www.bsee.gov")
        assert all(r["url"].endswith(".pdf") for r in records)

    def test_empty_html(self) -> None:
        assert parse_bsee_listing("<html></html>") == []


class TestBseeDiscoverOffline:
    def test_discover_mocked(self) -> None:
        with patch("src.ingestion.sources.bsee_discover.requests") as mock_req:
            session = Mock(headers={})
            mock_req.Session.return_value = session
            # district page, then panel page
            session.get.side_effect = [
                Mock(status_code=200, text=BSEE_LISTING_HTML),
                Mock(status_code=200, text="<html></html>"),
            ]
            results = discover_bsee(limit=10, sleep=0)
            assert len(results) == 2
            assert all(r["source"] == "bsee" for r in results)

    def test_limit(self) -> None:
        with patch("src.ingestion.sources.bsee_discover.requests") as mock_req:
            session = Mock(headers={})
            mock_req.Session.return_value = session
            session.get.side_effect = [
                Mock(status_code=200, text=BSEE_LISTING_HTML),
                Mock(status_code=200, text="<html></html>"),
            ]
            results = discover_bsee(limit=1, sleep=0)
            assert len(results) == 1

    def test_handles_error(self) -> None:
        with patch("src.ingestion.sources.bsee_discover.requests") as mock_req:
            import requests as real_requests
            session = Mock(headers={})
            mock_req.Session.return_value = session
            mock_req.RequestException = real_requests.RequestException
            session.get.side_effect = real_requests.RequestException("fail")
            results = discover_bsee(limit=5, sleep=0)
            assert results == []


class TestBseeCsvWriters:
    def test_write_url_list(self, tmp_path: Path) -> None:
        records = [{"doc_id": "b1", "url": "https://bsee.gov/r.pdf"}]
        out = tmp_path / "urls.csv"
        bsee_write_url_list(records, out)
        with open(out) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1


# ═══════════════════════════════════════════════════════════════════════
# PHMSA tests
# ═══════════════════════════════════════════════════════════════════════


class TestPhmsaParsePage:
    def test_extracts_csv_and_xlsx_links(self) -> None:
        records = parse_phmsa_page(PHMSA_DATA_HTML, "https://www.phmsa.dot.gov")
        # Should find .csv and .xlsx but NOT .pdf
        extensions = [r["url"].split(".")[-1] for r in records]
        assert "csv" in extensions
        assert "xlsx" in extensions
        assert "pdf" not in extensions

    def test_deduplicates(self) -> None:
        doubled = PHMSA_DATA_HTML + PHMSA_DATA_HTML
        records = parse_phmsa_page(doubled, "https://www.phmsa.dot.gov")
        assert len(records) == 2  # still only 2 unique links

    def test_empty_html(self) -> None:
        assert parse_phmsa_page("<html></html>") == []


class TestPhmsaIncidentCsv:
    def test_parse_incident_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "incidents.csv"
        csv_path.write_text(
            "REPORT_NUMBER,INCIDENT_DATE,NARRATIVE\n"
            "20240001,2024-01-15,Gas leak at compressor station\n"
            "20240002,2024-02-20,Pipeline rupture near valve\n",
            encoding="utf-8",
        )
        results = parse_phmsa_incident_csv(csv_path)
        assert len(results) == 2
        assert results[0]["doc_id"] == "20240001"
        assert results[0]["url"] == ""  # no PDF links available
        assert "Gas leak" in results[0]["title"]
        assert results[0]["source"] == "phmsa"

    def test_limit(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "incidents.csv"
        csv_path.write_text(
            "REPORT_NUMBER,INCIDENT_DATE,NARRATIVE\n"
            "20240001,2024-01-15,Event A\n"
            "20240002,2024-02-20,Event B\n"
            "20240003,2024-03-10,Event C\n",
            encoding="utf-8",
        )
        results = parse_phmsa_incident_csv(csv_path, limit=2)
        assert len(results) == 2

    def test_missing_columns_graceful(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "weird.csv"
        csv_path.write_text("col_a,col_b\nfoo,bar\n", encoding="utf-8")
        results = parse_phmsa_incident_csv(csv_path)
        assert len(results) == 1
        assert results[0]["doc_id"].startswith("phmsa-")


class TestPhmsaDiscoverOffline:
    def test_discover_mocked(self) -> None:
        with patch("src.ingestion.sources.phmsa_discover.requests") as mock_req:
            session = Mock(headers={})
            mock_req.Session.return_value = session
            session.get.return_value = Mock(status_code=200, text=PHMSA_DATA_HTML)
            results = discover_phmsa(sleep=0)
            assert len(results) == 2
            assert all(r["source"] == "phmsa" for r in results)

    def test_empty_page(self) -> None:
        with patch("src.ingestion.sources.phmsa_discover.requests") as mock_req:
            session = Mock(headers={})
            mock_req.Session.return_value = session
            session.get.return_value = Mock(status_code=200, text="<html></html>")
            results = discover_phmsa(sleep=0)
            assert results == []

    def test_handles_error(self) -> None:
        with patch("src.ingestion.sources.phmsa_discover.requests") as mock_req:
            import requests as real_requests
            session = Mock(headers={})
            mock_req.Session.return_value = session
            mock_req.RequestException = real_requests.RequestException
            session.get.side_effect = real_requests.RequestException("fail")
            results = discover_phmsa(sleep=0)
            assert results == []


class TestPhmsaCsvWriters:
    def test_url_list_excludes_empty_urls(self, tmp_path: Path) -> None:
        records = [
            {"doc_id": "p1", "url": "https://x.com/data.csv"},
            {"doc_id": "p2", "url": ""},  # no URL
        ]
        out = tmp_path / "urls.csv"
        phmsa_write_url_list(records, out)
        with open(out) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1  # only the one with URL

    def test_metadata_includes_all(self, tmp_path: Path) -> None:
        records = [
            {"doc_id": "p1", "url": "", "title": "Incident", "date": "2024",
             "page_url": "https://x.com", "source": "phmsa"},
        ]
        out = tmp_path / "meta.csv"
        phmsa_write_metadata(records, out)
        with open(out) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1


# ═══════════════════════════════════════════════════════════════════════
# CLI dispatch test
# ═══════════════════════════════════════════════════════════════════════


class TestDiscoverSourceCli:
    def test_unknown_source_exits(self) -> None:
        """discover-source with invalid source should exit 1."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "src.pipeline", "discover-source", "--source", "unknown"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
