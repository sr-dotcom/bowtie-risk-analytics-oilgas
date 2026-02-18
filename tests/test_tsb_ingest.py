"""Tests for TSB HTML ingestion. All offline, mocked HTTP."""
import csv
import logging
from pathlib import Path
from unittest.mock import patch, Mock

import pytest


# Minimal TSB report HTML for testing
_MOCK_HTML = """
<html><body>
<main>
  <h1>Pipeline Report P23H0001</h1>
  <div class="report-body">
    <p>A natural gas release occurred at a compressor station in Alberta.
    The release was caused by a valve failure. Workers evacuated the area
    and emergency services responded within thirty minutes of the initial
    alarm. The investigation found multiple contributing factors including
    inadequate maintenance procedures and missing safety barriers.</p>
  </div>
</main>
</body></html>
"""


class TestTsbIngestSmoke:
    def test_smoke_limit_1(self, tmp_path: Path) -> None:
        from src.ingestion.sources.tsb_ingest import ingest_tsb_html

        html_dir = tmp_path / "html"
        text_dir = tmp_path / "text"
        manifest_path = tmp_path / "manifest.csv"

        url_entries = [
            {
                "doc_id": "P23H0001",
                "url": "https://tsb.gc.ca/eng/reports/pipeline/2023/p23h0001/p23h0001.html",
            },
        ]

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = _MOCK_HTML

        with patch("src.ingestion.sources.tsb_ingest.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_resp

            rows = ingest_tsb_html(
                url_entries=url_entries,
                html_dir=html_dir,
                text_dir=text_dir,
                manifest_path=manifest_path,
            )

        assert len(rows) == 1
        assert rows[0]["doc_id"] == "P23H0001"
        assert rows[0]["status"] == "ok"

        # Raw HTML stored for audit
        assert (html_dir / "P23H0001.html").exists()

        # Text file created
        text_file = text_dir / "P23H0001.txt"
        assert text_file.exists()
        assert "natural gas release" in text_file.read_text(encoding="utf-8")

        # Manifest written with 1 row
        assert manifest_path.exists()
        with open(manifest_path, "r") as f:
            mrows = list(csv.DictReader(f))
        assert len(mrows) == 1


class TestTsbIngestResumable:
    def test_second_run_skips(self, tmp_path: Path, caplog) -> None:
        from src.ingestion.sources.tsb_ingest import ingest_tsb_html

        html_dir = tmp_path / "html"
        text_dir = tmp_path / "text"
        manifest_path = tmp_path / "manifest.csv"

        url_entries = [
            {
                "doc_id": "P23H0001",
                "url": "https://tsb.gc.ca/eng/reports/pipeline/2023/p23h0001/p23h0001.html",
            },
        ]

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = _MOCK_HTML

        with patch("src.ingestion.sources.tsb_ingest.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_resp
            rows1 = ingest_tsb_html(
                url_entries=url_entries,
                html_dir=html_dir,
                text_dir=text_dir,
                manifest_path=manifest_path,
            )

        assert len(rows1) == 1

        # Second run — no network patch needed; should skip based on manifest
        with caplog.at_level(logging.INFO):
            rows2 = ingest_tsb_html(
                url_entries=url_entries,
                html_dir=html_dir,
                text_dir=text_dir,
                manifest_path=manifest_path,
            )

        # Status preserved
        assert len(rows2) == 1
        assert rows2[0]["status"] == "ok"

        # Manifest row count stable (no duplicates)
        with open(manifest_path, "r") as f:
            mrows = list(csv.DictReader(f))
        assert len(mrows) == 1

        # Skip message present in logs
        assert "skip" in caplog.text.lower()
