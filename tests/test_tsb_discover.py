"""Tests for TSB Canada discovery adapter. All offline."""
import csv
from pathlib import Path

import pytest

# ── TSB HTML fixtures ────────────────────────────────────────────────

TSB_LISTING_HTML = """
<html><body>
<div class="pipeline-investigations">
  <ul>
    <li>
      <a href="/eng/reports/pipeline/2023/p23h0001/p23h0001.html">
        Pipeline Investigation Report P23H0001
      </a>
      <span class="date">2024-03-15</span>
    </li>
    <li>
      <a href="/eng/reports/pipeline/2022/p22h0044/p22h0044.html">
        Pipeline Investigation Report P22H0044
      </a>
      <span class="date">2023-11-20</span>
    </li>
  </ul>
</div>
</body></html>
"""

TSB_DETAIL_HTML = """
<html><body>
<header><nav>Navigation content</nav></header>
<main>
  <h1>Pipeline Investigation Report P23H0001</h1>
  <div class="report-body">
    <p>On 15 March 2023, a natural gas release occurred at a compressor station
    operated by TransCanada PipeLines Limited near Lethbridge, Alberta.</p>
    <p>The investigation determined that the release was caused by a
    failure of the mainline isolation valve.</p>
  </div>
</main>
<footer>Footer content</footer>
</body></html>
"""

TSB_DETAIL_NO_MAIN_HTML = """
<html><body>
<header><nav>Navigation</nav></header>
<p>The pipeline ruptured near a river crossing causing a significant release
of crude oil.</p>
<footer>Footer</footer>
</body></html>
"""


class TestTsbParseListing:
    def test_extracts_report_urls(self) -> None:
        from src.ingestion.sources.tsb_discover import parse_listing_page

        results = parse_listing_page(TSB_LISTING_HTML)
        assert len(results) == 2
        assert results[0]["doc_id"] == "P23H0001"
        assert "/p23h0001.html" in results[0]["url"]
        assert results[0]["source"] == "tsb"

    def test_extracts_date(self) -> None:
        from src.ingestion.sources.tsb_discover import parse_listing_page

        results = parse_listing_page(TSB_LISTING_HTML)
        assert results[0]["date"] == "2024-03-15"


class TestTsbParseDetail:
    def test_extracts_narrative(self) -> None:
        from src.ingestion.sources.tsb_discover import parse_detail_page

        result = parse_detail_page(TSB_DETAIL_HTML)
        assert "natural gas release" in result["narrative"]
        assert "isolation valve" in result["narrative"]

    def test_strips_nav_and_footer(self) -> None:
        from src.ingestion.sources.tsb_discover import parse_detail_page

        result = parse_detail_page(TSB_DETAIL_HTML)
        assert "Navigation content" not in result["narrative"]
        assert "Footer content" not in result["narrative"]


class TestTsbDocId:
    def test_deterministic(self) -> None:
        from src.ingestion.sources.tsb_discover import doc_id_from_url

        url = "https://www.tsb.gc.ca/eng/reports/pipeline/2023/p23h0001/p23h0001.html"
        id1 = doc_id_from_url(url)
        id2 = doc_id_from_url(url)
        assert id1 == id2

    def test_no_hash_only(self) -> None:
        from src.ingestion.sources.tsb_discover import doc_id_from_url

        url = "https://www.tsb.gc.ca/eng/reports/pipeline/2023/p23h0001/p23h0001.html"
        doc_id = doc_id_from_url(url)
        # Must contain human-readable report ID, not just a hex hash
        assert "P23H0001" in doc_id.upper()


class TestTsbHtmlToText:
    def test_fallback_no_main(self) -> None:
        from src.ingestion.sources.tsb_discover import extract_narrative_from_html

        text = extract_narrative_from_html(TSB_DETAIL_NO_MAIN_HTML)
        assert "pipeline ruptured" in text
        # Nav/footer stripped even in fallback
        assert "Navigation" not in text
        assert "Footer" not in text

    def test_raw_html_stored(self, tmp_path: Path) -> None:
        from src.ingestion.sources.tsb_discover import save_raw_html

        html_path = tmp_path / "raw.html"
        save_raw_html(TSB_DETAIL_HTML, html_path)
        assert html_path.exists()
        assert html_path.read_text(encoding="utf-8") == TSB_DETAIL_HTML


class TestTsbCsvWriters:
    def test_write_url_list(self, tmp_path: Path) -> None:
        from src.ingestion.sources.tsb_discover import write_url_list

        results = [
            {"doc_id": "P23H0001", "url": "https://example.com/p23h0001.html"},
            {"doc_id": "P22H0044", "url": "https://example.com/p22h0044.html"},
        ]
        out_path = tmp_path / "url_list.csv"
        write_url_list(results, out_path)
        assert out_path.exists()
        with open(out_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["doc_id"] == "P23H0001"

    def test_write_metadata(self, tmp_path: Path) -> None:
        from src.ingestion.sources.tsb_discover import write_metadata

        results = [
            {
                "doc_id": "P23H0001",
                "url": "https://example.com/p23h0001.html",
                "title": "Pipeline Report P23H0001",
                "date": "2024-03-15",
                "page_url": "https://tsb.gc.ca/listing",
                "source": "tsb",
                "domain": "pipeline",
            },
        ]
        out_path = tmp_path / "meta.csv"
        write_metadata(results, out_path)
        with open(out_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["domain"] == "pipeline"
