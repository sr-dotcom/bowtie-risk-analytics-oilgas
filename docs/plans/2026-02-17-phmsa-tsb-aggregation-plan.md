# PHMSA + TSB Ingestion & Combined Aggregation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add PHMSA (skeleton) and TSB Canada (HTML scrape) source ingestion, then produce combined flat CSVs aggregating all sources for downstream NLP.

**Architecture:** Extend existing `src/ingestion/sources/` pattern. PHMSA is a skeleton-only module (no real CSV yet). TSB is a full HTML scrape → narrative extract → LLM pipeline. A new `src/analytics/build_combined_exports.py` walks all structured JSON and produces two combined CSVs. All new CLI subcommands wired into `src/pipeline.py`.

**Tech Stack:** Python 3.10+, Pydantic v2, BeautifulSoup4, requests, csv, existing extraction/LLM pipeline.

**Constraints:** No git commit/push. No changes to `.claude/` or `docs/plans/`. All tests offline.

---

## Task 1: PHMSA Ingest Skeleton — Tests

**Files:**
- Create: `tests/test_phmsa_ingest.py`

**Step 1: Write the failing tests**

```python
"""Tests for PHMSA bulk CSV ingest skeleton. All offline."""
import csv
import logging
from pathlib import Path

import pytest


class TestPhmsaIngestSkeleton:
    """PHMSA ingest skeleton: header inspection + graceful no-op."""

    def test_skeleton_warns_on_missing_csv(self, tmp_path: Path, caplog) -> None:
        from src.ingestion.sources.phmsa_ingest import ingest_phmsa_csv

        manifest_path = tmp_path / "manifest.csv"
        missing_csv = tmp_path / "does_not_exist.csv"

        with caplog.at_level(logging.WARNING):
            rows = ingest_phmsa_csv(
                csv_path=missing_csv,
                output_dir=tmp_path / "out",
                manifest_path=manifest_path,
            )

        assert rows == []
        assert "not found" in caplog.text.lower() or "does not exist" in caplog.text.lower()

    def test_skeleton_inspects_headers(self, tmp_path: Path, caplog) -> None:
        from src.ingestion.sources.phmsa_ingest import ingest_phmsa_csv

        csv_path = tmp_path / "incidents.csv"
        csv_path.write_text(
            "REPORT_NUMBER,INCIDENT_DATE,NARRATIVE,CITY,STATE\n"
            "RPT-001,2024-01-15,A leak occurred,Houston,TX\n"
        )
        manifest_path = tmp_path / "manifest.csv"

        with caplog.at_level(logging.INFO):
            rows = ingest_phmsa_csv(
                csv_path=csv_path,
                output_dir=tmp_path / "out",
                manifest_path=manifest_path,
            )

        # Skeleton reports headers but doesn't map yet
        assert "REPORT_NUMBER" in caplog.text or "report_number" in caplog.text.lower()
        assert "mapping" in caplog.text.lower() or "recognized" in caplog.text.lower()

    def test_skeleton_warns_unknown_headers(self, tmp_path: Path, caplog) -> None:
        from src.ingestion.sources.phmsa_ingest import ingest_phmsa_csv

        csv_path = tmp_path / "weird.csv"
        csv_path.write_text("FOO,BAR,BAZ\nval1,val2,val3\n")
        manifest_path = tmp_path / "manifest.csv"

        with caplog.at_level(logging.WARNING):
            rows = ingest_phmsa_csv(
                csv_path=csv_path,
                output_dir=tmp_path / "out",
                manifest_path=manifest_path,
            )

        # Graceful no-op: empty manifest, no exception
        assert rows == []
        assert "mapping requires real csv" in caplog.text.lower() or "unrecognized" in caplog.text.lower()

    def test_manifest_schema(self, tmp_path: Path) -> None:
        from src.ingestion.sources.phmsa_ingest import PHMSA_MANIFEST_COLUMNS

        required = {"doc_id", "incident_id", "json_path", "valid", "provider", "error", "created_at"}
        assert required.issubset(set(PHMSA_MANIFEST_COLUMNS))
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_phmsa_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ingestion.sources.phmsa_ingest'`

---

## Task 2: PHMSA Ingest Skeleton — Implementation

**Files:**
- Create: `src/ingestion/sources/phmsa_ingest.py`

**Step 1: Write minimal implementation**

```python
"""PHMSA bulk CSV ingest skeleton.

PHMSA publishes bulk tabular data (no per-incident PDFs). This module
provides header inspection and a stub mapping path. Full column mapping
will be added once a real PHMSA CSV is downloaded and headers confirmed.
"""
import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Known PHMSA CSV column names (case-insensitive matching)
KNOWN_COLUMNS: dict[str, list[str]] = {
    "id": ["report_number", "report number", "reportnumber", "id"],
    "date": ["incident_date", "incident date", "date", "iyear"],
    "narrative": ["narrative", "description", "summary"],
    "city": ["city", "location_city"],
    "state": ["state", "location_state"],
    "operator": ["operator_name", "operator"],
    "commodity": ["commodity_released_type", "commodity"],
    "volume": [
        "unintentional_release_bbls",
        "net_loss_barrels",
        "total_release_volume",
    ],
}

PHMSA_MANIFEST_COLUMNS: list[str] = [
    "doc_id",
    "incident_id",
    "json_path",
    "valid",
    "provider",
    "error",
    "created_at",
]


def _match_headers(
    file_headers: list[str],
) -> dict[str, Optional[str]]:
    """Match file headers against known PHMSA columns.

    Returns dict mapping logical name -> matched file header (or None).
    """
    lower_headers = {h.lower().strip(): h for h in file_headers}
    matched: dict[str, Optional[str]] = {}
    for logical, candidates in KNOWN_COLUMNS.items():
        matched[logical] = None
        for c in candidates:
            if c in lower_headers:
                matched[logical] = lower_headers[c]
                break
    return matched


def ingest_phmsa_csv(
    csv_path: Path,
    output_dir: Path,
    manifest_path: Path,
    limit: Optional[int] = None,
) -> list[dict]:
    """Inspect a PHMSA bulk CSV and report mapping status.

    This is a skeleton: it reads headers, reports which known columns
    were recognized, and returns an empty manifest. Full row-level
    mapping will be added once a real CSV is available and headers are
    confirmed.

    Args:
        csv_path: Path to PHMSA bulk incident CSV.
        output_dir: Directory for output JSON (unused in skeleton).
        manifest_path: Path for structured manifest CSV (written empty).
        limit: Max rows to inspect (default: all).

    Returns:
        Empty list (skeleton — no rows mapped yet).
    """
    if not csv_path.exists():
        logger.warning(f"PHMSA CSV not found: {csv_path}")
        return []

    try:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            file_headers = list(reader.fieldnames or [])
    except Exception as e:
        logger.warning(f"Failed to read PHMSA CSV headers: {e}")
        return []

    if not file_headers:
        logger.warning("PHMSA CSV has no headers")
        return []

    matched = _match_headers(file_headers)
    recognized = {k: v for k, v in matched.items() if v is not None}
    missing = {k for k, v in matched.items() if v is None}

    logger.info(
        f"PHMSA CSV headers ({len(file_headers)} columns): {file_headers}"
    )
    logger.info(f"Recognized columns: {recognized}")

    if not recognized:
        logger.warning(
            "No recognized PHMSA columns found. "
            "Mapping requires real CSV with known headers "
            f"(expected any of: {list(KNOWN_COLUMNS.keys())}). "
            "Returning empty manifest."
        )
        return []

    if "id" not in recognized or "narrative" not in recognized:
        logger.warning(
            f"Missing critical columns (id and/or narrative). "
            f"Recognized so far: {recognized}. Missing: {missing}. "
            "Mapping requires real CSV — returning empty manifest."
        )
        return []

    # Count rows for reporting
    row_count = 0
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for _ in reader:
            row_count += 1
            if limit and row_count >= limit:
                break

    logger.info(
        f"PHMSA CSV: {row_count} rows inspected, "
        f"{len(recognized)}/{len(KNOWN_COLUMNS)} columns recognized. "
        "Full mapping not yet implemented — returning empty manifest."
    )

    # Write empty manifest with correct schema
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PHMSA_MANIFEST_COLUMNS)
        writer.writeheader()

    return []
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/test_phmsa_ingest.py -v`
Expected: 4 passed

**Step 3: Run full suite to check no regressions**

Run: `pytest -q`
Expected: All existing tests still pass.

---

## Task 3: PHMSA CLI Wiring

**Files:**
- Modify: `src/pipeline.py` (add `ingest-phmsa` subcommand)

**Step 1: Add import at top of `src/pipeline.py`** (after line 46)

```python
from src.ingestion.sources.phmsa_ingest import ingest_phmsa_csv
```

**Step 2: Add command handler function** (before `_DISCOVER_ADAPTERS` at line 498)

```python
def cmd_ingest_phmsa(args: argparse.Namespace) -> None:
    """Ingest PHMSA bulk CSV (skeleton: header inspection only)."""
    csv_path = Path(args.csv_path)
    output_dir = Path(args.output_dir)
    manifest_path = Path(args.manifest)
    rows = ingest_phmsa_csv(
        csv_path=csv_path,
        output_dir=output_dir,
        manifest_path=manifest_path,
        limit=args.limit,
    )
    logger.info(f"PHMSA ingest: {len(rows)} rows mapped")
```

**Step 3: Add subparser** (after `p_ingest.set_defaults(func=cmd_ingest_source)` block, before `discover-source`)

```python
# ingest-phmsa subcommand
p_phmsa = subparsers.add_parser(
    "ingest-phmsa",
    help="Ingest PHMSA bulk CSV (skeleton: header inspection only)",
)
p_phmsa.add_argument(
    "--csv-path", required=True, help="Path to PHMSA bulk incident CSV"
)
p_phmsa.add_argument(
    "--output-dir",
    default="data/structured/incidents/phmsa",
    help="Output directory for V2.3 JSON files",
)
p_phmsa.add_argument(
    "--manifest",
    default="data/manifests/structured_manifest_phmsa.csv",
    help="Path for structured manifest CSV",
)
p_phmsa.add_argument(
    "--limit", type=int, default=None, help="Max rows to process"
)
p_phmsa.set_defaults(func=cmd_ingest_phmsa)
```

**Step 4: Verify CLI wiring**

Run: `python -m src.pipeline ingest-phmsa --help`
Expected: Shows help with `--csv-path`, `--output-dir`, `--manifest`, `--limit` arguments.

Run: `pytest -q`
Expected: All tests pass.

---

## Task 4: TSB Discovery — Tests

**Files:**
- Create: `tests/test_tsb_discover.py`

**Step 1: Write the failing tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tsb_discover.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ingestion.sources.tsb_discover'`

---

## Task 5: TSB Discovery — Implementation

**Files:**
- Create: `src/ingestion/sources/tsb_discover.py`

**Step 1: Write implementation**

```python
"""TSB Canada pipeline investigation discovery adapter.

Scrapes the Transportation Safety Board of Canada (tsb.gc.ca) for
pipeline investigation reports. Scope: pipeline domain only (initial).

Pattern follows CSB/BSEE discoverers:
  discover_tsb() → parse_listing_page() → parse_detail_page()
  → write_url_list() / write_metadata()
"""
import csv
import logging
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

TSB_BASE_URL = "https://www.tsb.gc.ca"
TSB_PIPELINE_LISTING = (
    "https://www.tsb.gc.ca/eng/reports/pipeline/index.html"
)
USER_AGENT = "BowtieRiskAnalytics/0.1 (academic research)"

# Regex to extract report IDs like P23H0001 from URLs
_REPORT_ID_RE = re.compile(r"[/\\]?(p\d{2}[a-z]\d{4})", re.IGNORECASE)


def doc_id_from_url(url: str) -> str:
    """Extract a deterministic, human-readable doc_id from a TSB URL.

    Looks for report ID pattern (e.g. P23H0001) in the URL path.
    Falls back to the last path segment stem.
    """
    m = _REPORT_ID_RE.search(url)
    if m:
        return m.group(1).upper()
    # Fallback: last path segment without extension
    path = url.split("?")[0].split("#")[0].rstrip("/")
    segment = path.split("/")[-1]
    stem = segment.rsplit(".", 1)[0] if "." in segment else segment
    return stem.upper() if stem else "TSB_UNKNOWN"


def extract_narrative_from_html(html: str) -> str:
    """Extract narrative text from TSB report HTML.

    Primary: content inside <main> tag.
    Fallback: <body> with <header>, <nav>, <footer> stripped.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # Remove script and style elements
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    # Try <main> first
    main = soup.find("main")
    if main:
        # Remove nav within main if present
        for nav in main.find_all("nav"):
            nav.decompose()
        return main.get_text(separator="\n", strip=True)

    # Fallback: body with nav/header/footer removed
    body = soup.find("body")
    if not body:
        return soup.get_text(separator="\n", strip=True)

    for tag in body.find_all(["header", "nav", "footer"]):
        tag.decompose()

    return body.get_text(separator="\n", strip=True)


def save_raw_html(html: str, path: Path) -> None:
    """Save raw HTML to disk for audit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def parse_listing_page(html: str, base_url: str = TSB_BASE_URL) -> list[dict]:
    """Parse a TSB listing page to extract report URLs and metadata.

    Returns list of dicts: doc_id, url, title, date, page_url, source, domain.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    results: list[dict] = []
    seen: set[str] = set()

    # Find all links that look like pipeline report URLs
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/reports/pipeline/" not in href.lower():
            continue

        full_url = urljoin(base_url, href)
        doc_id = doc_id_from_url(full_url)

        if doc_id in seen:
            continue
        seen.add(doc_id)

        # Extract title from link text
        title = a_tag.get_text(strip=True)

        # Try to find adjacent date
        date_str = ""
        date_el = a_tag.find_next(class_="date")
        if date_el:
            date_str = date_el.get_text(strip=True)
        if not date_str:
            date_el = a_tag.find_next("span", class_="date")
            if date_el:
                date_str = date_el.get_text(strip=True)

        results.append({
            "doc_id": doc_id,
            "url": full_url,
            "title": title,
            "date": date_str,
            "page_url": TSB_PIPELINE_LISTING,
            "source": "tsb",
            "domain": "pipeline",
        })

    return results


def parse_detail_page(html: str) -> dict:
    """Parse a TSB report detail page.

    Returns dict with key 'narrative' containing extracted text.
    """
    narrative = extract_narrative_from_html(html)
    return {"narrative": narrative}


def discover_tsb(
    base_url: str = TSB_BASE_URL,
    limit: Optional[int] = None,
    timeout: int = 30,
    sleep: float = 1.0,
) -> list[dict]:
    """Discover TSB pipeline investigation reports.

    Fetches the pipeline listing page and extracts report URLs.

    Args:
        base_url: TSB website base URL.
        limit: Max reports to discover.
        timeout: HTTP timeout in seconds.
        sleep: Delay between requests (polite crawling).

    Returns:
        List of dicts: doc_id, url, title, date, page_url, source, domain.
    """
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    listing_url = f"{base_url}/eng/reports/pipeline/index.html"
    logger.info(f"Fetching TSB pipeline listing: {listing_url}")

    try:
        resp = session.get(listing_url, timeout=timeout)
        if resp.status_code != 200:
            logger.warning(f"TSB listing returned {resp.status_code}")
            return []
    except requests.RequestException as e:
        logger.error(f"Failed to fetch TSB listing: {e}")
        return []

    results = parse_listing_page(resp.text, base_url)

    if limit is not None:
        results = results[:limit]

    logger.info(f"Discovered {len(results)} TSB pipeline reports")
    return results


# ── CSV writers ─────────────────────────────────────────────────────────


def write_url_list(results: list[dict], out_path: Path) -> None:
    """Write url_list.csv (doc_id, url)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["doc_id", "url"])
        writer.writeheader()
        for r in results:
            writer.writerow({"doc_id": r["doc_id"], "url": r["url"]})


def write_metadata(results: list[dict], out_path: Path) -> None:
    """Write metadata CSV with domain label."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["doc_id", "title", "date", "page_url", "url", "source", "domain"]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in fields})
```

**Step 2: Run tests**

Run: `pytest tests/test_tsb_discover.py -v`
Expected: All passed.

**Step 3: Check no regressions**

Run: `pytest -q`
Expected: All tests pass.

---

## Task 6: TSB CLI Wiring (discover-source --source tsb)

**Files:**
- Modify: `src/pipeline.py`

**Step 1: Add import** (after phmsa_discover imports, ~line 46)

```python
from src.ingestion.sources.tsb_discover import (
    discover_tsb,
    write_url_list as tsb_write_url_list,
    write_metadata as tsb_write_metadata,
)
```

**Step 2: Add TSB to `_DISCOVER_ADAPTERS`** (at ~line 498)

```python
_DISCOVER_ADAPTERS: dict[str, tuple] = {
    "csb": (discover_csb, csb_write_url_list, csb_write_metadata),
    "bsee": (discover_bsee, bsee_write_url_list, bsee_write_metadata),
    "phmsa": (discover_phmsa, phmsa_write_url_list, phmsa_write_metadata),
    "tsb": (discover_tsb, tsb_write_url_list, tsb_write_metadata),
}
```

**Step 3: Add "tsb" to choices** in the `discover-source` subparser (~line 779)

Change:
```python
choices=["csb", "bsee", "phmsa"],
```
To:
```python
choices=["csb", "bsee", "phmsa", "tsb"],
```

**Step 4: Verify**

Run: `python -m src.pipeline discover-source --source tsb --help`
Expected: Shows help, no import errors.

Run: `pytest -q`
Expected: All tests pass.

---

## Task 7: TSB Ingest — Tests

**Files:**
- Create: `tests/test_tsb_ingest.py`

**Step 1: Write the failing tests**

```python
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
            {"doc_id": "P23H0001", "url": "https://tsb.gc.ca/eng/reports/pipeline/2023/p23h0001/p23h0001.html"},
        ]

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = _MOCK_HTML
        mock_resp.content = _MOCK_HTML.encode("utf-8")

        with patch("src.ingestion.sources.tsb_ingest.requests.Session") as MockSession:
            session_inst = MockSession.return_value
            session_inst.get.return_value = mock_resp

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
        text = text_file.read_text(encoding="utf-8")
        assert "natural gas release" in text

        # Manifest written
        assert manifest_path.exists()
        with open(manifest_path, "r") as f:
            reader = csv.DictReader(f)
            mrows = list(reader)
        assert len(mrows) == 1


class TestTsbIngestResumable:
    def test_second_run_skips(self, tmp_path: Path, caplog) -> None:
        from src.ingestion.sources.tsb_ingest import ingest_tsb_html

        html_dir = tmp_path / "html"
        text_dir = tmp_path / "text"
        manifest_path = tmp_path / "manifest.csv"

        url_entries = [
            {"doc_id": "P23H0001", "url": "https://tsb.gc.ca/eng/reports/pipeline/2023/p23h0001/p23h0001.html"},
        ]

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = _MOCK_HTML
        mock_resp.content = _MOCK_HTML.encode("utf-8")

        with patch("src.ingestion.sources.tsb_ingest.requests.Session") as MockSession:
            session_inst = MockSession.return_value
            session_inst.get.return_value = mock_resp

            # First run
            rows1 = ingest_tsb_html(
                url_entries=url_entries,
                html_dir=html_dir,
                text_dir=text_dir,
                manifest_path=manifest_path,
            )

        assert len(rows1) == 1

        # Second run — should skip, no network call
        with caplog.at_level(logging.INFO):
            rows2 = ingest_tsb_html(
                url_entries=url_entries,
                html_dir=html_dir,
                text_dir=text_dir,
                manifest_path=manifest_path,
            )

        assert len(rows2) == 1
        assert rows2[0]["status"] == "ok"
        # Manifest row count stable
        with open(manifest_path, "r") as f:
            reader = csv.DictReader(f)
            mrows = list(reader)
        assert len(mrows) == 1
        # Skip message present
        assert "skip" in caplog.text.lower()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tsb_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ingestion.sources.tsb_ingest'`

---

## Task 8: TSB Ingest — Implementation

**Files:**
- Create: `src/ingestion/sources/tsb_ingest.py`

**Step 1: Write implementation**

```python
"""TSB Canada HTML report ingestion.

Downloads raw HTML → extracts narrative text → writes manifest.
Raw HTML is always stored for audit. Text extraction uses
BeautifulSoup with fallback logic from tsb_discover.
"""
import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from src.ingestion.sources.tsb_discover import (
    extract_narrative_from_html,
    save_raw_html,
)

logger = logging.getLogger(__name__)

USER_AGENT = "BowtieRiskAnalytics/0.1 (academic research)"

TSB_MANIFEST_COLUMNS = [
    "doc_id", "url", "html_path", "text_path",
    "status", "text_len", "downloaded_at", "error",
]


def _load_existing_manifest(manifest_path: Path) -> dict[str, dict]:
    """Load existing manifest rows keyed by doc_id."""
    if not manifest_path.exists():
        return {}
    rows: dict[str, dict] = {}
    with open(manifest_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows[row["doc_id"]] = row
    return rows


def _save_manifest(rows: list[dict], manifest_path: Path) -> None:
    """Write manifest CSV."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TSB_MANIFEST_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in TSB_MANIFEST_COLUMNS})


def ingest_tsb_html(
    url_entries: list[dict[str, str]],
    html_dir: Path,
    text_dir: Path,
    manifest_path: Path,
    force: bool = False,
    timeout: int = 30,
) -> list[dict]:
    """Download TSB HTML reports, extract text, write manifest.

    Args:
        url_entries: List of dicts with doc_id and url keys.
        html_dir: Directory to store raw HTML files.
        text_dir: Directory to store extracted text files.
        manifest_path: Path for manifest CSV.
        force: Reprocess even if already in manifest.
        timeout: HTTP timeout in seconds.

    Returns:
        List of manifest row dicts.
    """
    html_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    existing = _load_existing_manifest(manifest_path)
    results: list[dict] = []

    session: Optional[requests.Session] = None

    for entry in url_entries:
        doc_id = entry["doc_id"]
        url = entry["url"]

        html_path = html_dir / f"{doc_id}.html"
        text_path = text_dir / f"{doc_id}.txt"

        # Resumability check
        prev = existing.get(doc_id)
        if (
            not force
            and prev
            and prev.get("status") == "ok"
            and text_path.exists()
        ):
            logger.info(f"Skipping {doc_id}: already processed")
            results.append(prev)
            continue

        # Lazy session init (avoids creating session when all skipped)
        if session is None:
            session = requests.Session()
            session.headers["User-Agent"] = USER_AGENT

        # Download HTML
        try:
            resp = session.get(url, timeout=timeout)
            if resp.status_code != 200:
                results.append({
                    "doc_id": doc_id,
                    "url": url,
                    "html_path": "",
                    "text_path": "",
                    "status": "error",
                    "text_len": "0",
                    "downloaded_at": datetime.now(timezone.utc).isoformat(),
                    "error": f"HTTP {resp.status_code}",
                })
                continue
        except Exception as e:
            results.append({
                "doc_id": doc_id,
                "url": url,
                "html_path": "",
                "text_path": "",
                "status": "error",
                "text_len": "0",
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            })
            continue

        html_content = resp.text

        # Always store raw HTML for audit
        save_raw_html(html_content, html_path)

        # Extract narrative text
        narrative = extract_narrative_from_html(html_content)
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(narrative, encoding="utf-8")

        results.append({
            "doc_id": doc_id,
            "url": url,
            "html_path": str(html_path.name),
            "text_path": str(text_path.name),
            "status": "ok",
            "text_len": str(len(narrative)),
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "error": "",
        })
        logger.info(f"{doc_id}: ok ({len(narrative)} chars)")

    # Merge: update existing with new results
    merged: dict[str, dict] = dict(existing)
    for row in results:
        merged[row["doc_id"]] = row

    _save_manifest(list(merged.values()), manifest_path)

    ok = sum(1 for r in results if r.get("status") == "ok")
    skipped = sum(1 for r in results if r == existing.get(r.get("doc_id", "")))
    logger.info(f"TSB ingest: {ok} ok, {len(results) - ok} errors/skipped, {len(merged)} total in manifest")

    return results
```

**Step 2: Run tests**

Run: `pytest tests/test_tsb_ingest.py -v`
Expected: All passed.

Run: `pytest -q`
Expected: All tests pass.

---

## Task 9: Combined Exports — Tests

**Files:**
- Create: `tests/test_build_combined_exports.py`

**Step 1: Write the failing tests**

```python
"""Tests for combined aggregation exports. All offline, inline fixtures."""
import csv
import json
from pathlib import Path

import pytest

# ── Inline V2.3 fixtures ────────────────────────────────────────────

FIXTURE_CSB = {
    "incident_id": "CSB-2024-001",
    "source": {
        "agency": "CSB",
        "doc_type": "investigation_report",
        "url": "https://csb.gov/report",
        "title": "Refinery Fire",
        "date_published": "2024-06-01",
        "date_occurred": "2024-01-15",
    },
    "context": {"region": "Texas", "operator": "Acme Corp"},
    "event": {
        "top_event": "Loss of Containment",
        "incident_type": "fire",
        "summary": "A fire broke out at the refinery.",
    },
    "bowtie": {
        "controls": [
            {
                "control_id": "CB_1",
                "name": "Pressure Relief Valve",
                "side": "left",
                "barrier_role": "prevent",
                "barrier_type": "engineering",
                "line_of_defense": 1,
                "lod_basis": "design",
                "linked_threat_ids": ["TH_1"],
                "linked_consequence_ids": [],
                "performance": {"barrier_status": "failed", "barrier_failed": True},
                "human": {"human_contribution_value": "none", "barrier_failed_human": False},
                "evidence": {"confidence": "high", "supporting_text": ["text1"]},
            }
        ],
    },
    "pifs": {},
    "notes": {"schema_version": "2.3"},
}

FIXTURE_PHMSA = {
    "incident_id": "PHMSA-RPT-001",
    "source": {
        "agency": "PHMSA",
        "date_occurred": "2024-03-20",
    },
    "context": {"region": "Oklahoma", "operator": "PipeCo"},
    "event": {
        "top_event": "Not Found",
        "incident_type": "Not Found",
        "summary": "Pipeline incident reported via PHMSA bulk data.",
    },
    "bowtie": {"controls": []},
    "pifs": {},
    "notes": {},
}

FIXTURE_NO_AGENCY = {
    "incident_id": "UNKNOWN-001",
    "source": {"url": "https://example.com"},
    "context": {},
    "event": {"top_event": "Explosion", "incident_type": "explosion", "summary": "An explosion."},
    "bowtie": {"controls": []},
    "pifs": {},
    "notes": {},
}


def _write_fixture(base_dir: Path, subdir: str, filename: str, data: dict) -> Path:
    """Write a JSON fixture to base_dir/subdir/filename."""
    d = base_dir / subdir
    d.mkdir(parents=True, exist_ok=True)
    p = d / filename
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


class TestFlatIncidentsCombined:
    def test_correct_columns_and_rows(self, tmp_path: Path) -> None:
        from src.analytics.build_combined_exports import build_flat_incidents

        incidents_dir = tmp_path / "incidents"
        _write_fixture(incidents_dir, "csb", "CSB-2024-001.json", FIXTURE_CSB)
        _write_fixture(incidents_dir, "phmsa", "PHMSA-RPT-001.json", FIXTURE_PHMSA)

        out_path = tmp_path / "flat.csv"
        count = build_flat_incidents(incidents_dir, out_path)

        assert count == 2
        with open(out_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        # Check Patrick's exact column names
        assert "incident__event__top_event" in reader.fieldnames
        assert "incident__event__incident_type" in reader.fieldnames
        assert "incident__event__summary" in reader.fieldnames
        assert "source_agency" in reader.fieldnames
        assert "json_path" in reader.fieldnames

    def test_source_agency_from_json(self, tmp_path: Path) -> None:
        from src.analytics.build_combined_exports import build_flat_incidents

        incidents_dir = tmp_path / "incidents"
        _write_fixture(incidents_dir, "csb", "CSB-2024-001.json", FIXTURE_CSB)
        out_path = tmp_path / "flat.csv"
        build_flat_incidents(incidents_dir, out_path)

        with open(out_path, "r") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["source_agency"] == "CSB"


class TestControlsCombined:
    def test_has_source_agency_and_json_path(self, tmp_path: Path) -> None:
        from src.analytics.build_combined_exports import build_controls_combined

        incidents_dir = tmp_path / "incidents"
        _write_fixture(incidents_dir, "csb", "CSB-2024-001.json", FIXTURE_CSB)

        out_path = tmp_path / "controls.csv"
        count = build_controls_combined(incidents_dir, out_path)

        assert count == 1
        with open(out_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert "source_agency" in reader.fieldnames
        assert "json_path" in reader.fieldnames
        assert rows[0]["source_agency"] == "CSB"


class TestSourceAgencyPriority:
    def test_json_field_wins(self, tmp_path: Path) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        data = {"source": {"agency": "CSB"}}
        assert resolve_source_agency(data, "some_dir") == "CSB"

    def test_dir_name_fallback(self, tmp_path: Path) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        data = {"source": {"url": "https://example.com"}}
        assert resolve_source_agency(data, "phmsa") == "PHMSA"

    def test_unknown_fallback(self, tmp_path: Path) -> None:
        from src.analytics.build_combined_exports import resolve_source_agency

        data = {}
        assert resolve_source_agency(data, "") == "UNKNOWN"


class TestMalformedJsonSkipped:
    def test_corrupt_json_skipped(self, tmp_path: Path, caplog) -> None:
        import logging
        from src.analytics.build_combined_exports import build_flat_incidents

        incidents_dir = tmp_path / "incidents"
        _write_fixture(incidents_dir, "csb", "CSB-2024-001.json", FIXTURE_CSB)
        # Write corrupt JSON
        bad_path = incidents_dir / "csb" / "BAD.json"
        bad_path.write_text("{invalid json", encoding="utf-8")

        out_path = tmp_path / "flat.csv"
        with caplog.at_level(logging.WARNING):
            count = build_flat_incidents(incidents_dir, out_path)

        # Good file still processed
        assert count == 1
        assert "BAD.json" in caplog.text


class TestEmptyDir:
    def test_empty_produces_header_only(self, tmp_path: Path) -> None:
        from src.analytics.build_combined_exports import build_flat_incidents

        incidents_dir = tmp_path / "incidents"
        incidents_dir.mkdir()
        out_path = tmp_path / "flat.csv"
        count = build_flat_incidents(incidents_dir, out_path)

        assert count == 0
        assert out_path.exists()
        with open(out_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 0
        assert "incident_id" in reader.fieldnames
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_build_combined_exports.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.analytics.build_combined_exports'`

---

## Task 10: Combined Exports — Implementation

**Files:**
- Create: `src/analytics/build_combined_exports.py`

**Step 1: Write implementation**

```python
"""Build combined flat CSV exports across all sources.

Walks data/structured/incidents/ (all subdirectories), reads V2.3 JSON,
and produces:
  - flat_incidents_combined.csv  (one row per incident)
  - controls_combined.csv        (one row per control per incident)
"""
import csv
import json
import logging
from pathlib import Path
from typing import Any

from src.analytics.flatten import flatten_controls, CONTROLS_CSV_COLUMNS

logger = logging.getLogger(__name__)

INCIDENT_CSV_COLUMNS = [
    "incident_id",
    "source_agency",
    "incident__event__top_event",
    "incident__event__incident_type",
    "incident__event__summary",
    "source__date_occurred",
    "source__date_published",
    "context__region",
    "context__operator",
    "json_path",
]

CONTROLS_COMBINED_COLUMNS = CONTROLS_CSV_COLUMNS + ["source_agency", "json_path"]


def resolve_source_agency(data: dict[str, Any], dir_name: str) -> str:
    """Resolve source agency with priority: JSON field > dir name > UNKNOWN."""
    agency = data.get("source", {}).get("agency")
    if agency:
        return str(agency)
    if dir_name:
        return dir_name.upper()
    return "UNKNOWN"


def _collect_json_files(incidents_dir: Path) -> list[tuple[Path, str]]:
    """Collect all JSON files under incidents_dir with their parent dir name.

    Returns list of (json_path, dir_name) tuples.
    """
    results: list[tuple[Path, str]] = []
    if not incidents_dir.exists():
        return results

    # Files directly in incidents_dir (no subdirectory)
    for f in sorted(incidents_dir.glob("*.json")):
        results.append((f, ""))

    # Files in subdirectories
    for subdir in sorted(incidents_dir.iterdir()):
        if subdir.is_dir():
            for f in sorted(subdir.glob("*.json")):
                results.append((f, subdir.name))

    return results


def _load_incident(json_path: Path) -> dict[str, Any] | None:
    """Load and return a V2.3 incident JSON, or None on error."""
    try:
        text = json_path.read_text(encoding="utf-8-sig")
        return json.loads(text)
    except Exception as e:
        logger.warning(f"Skipping malformed JSON {json_path.name}: {e}")
        return None


def build_flat_incidents(incidents_dir: Path, out_path: Path) -> int:
    """Build flat_incidents_combined.csv from all JSON under incidents_dir.

    Returns number of incident rows written.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json_files = _collect_json_files(incidents_dir)

    rows: list[dict[str, Any]] = []
    for json_path, dir_name in json_files:
        data = _load_incident(json_path)
        if data is None:
            continue

        event = data.get("event", {})
        source = data.get("source", {})
        context = data.get("context", {})

        rows.append({
            "incident_id": data.get("incident_id", ""),
            "source_agency": resolve_source_agency(data, dir_name),
            "incident__event__top_event": event.get("top_event", ""),
            "incident__event__incident_type": event.get("incident_type", ""),
            "incident__event__summary": event.get("summary", ""),
            "source__date_occurred": source.get("date_occurred", ""),
            "source__date_published": source.get("date_published", ""),
            "context__region": context.get("region", ""),
            "context__operator": context.get("operator", ""),
            "json_path": str(json_path),
        })

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=INCIDENT_CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Wrote {len(rows)} incidents to {out_path}")
    return len(rows)


def build_controls_combined(incidents_dir: Path, out_path: Path) -> int:
    """Build controls_combined.csv from all JSON under incidents_dir.

    Reuses flatten_controls() and adds source_agency + json_path.

    Returns number of control rows written.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json_files = _collect_json_files(incidents_dir)

    all_rows: list[dict[str, Any]] = []
    for json_path, dir_name in json_files:
        data = _load_incident(json_path)
        if data is None:
            continue

        agency = resolve_source_agency(data, dir_name)
        control_rows = flatten_controls(data)

        for row in control_rows:
            row["source_agency"] = agency
            row["json_path"] = str(json_path)
            all_rows.append(row)

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CONTROLS_COMBINED_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)

    logger.info(f"Wrote {len(all_rows)} control rows to {out_path}")
    return len(all_rows)


def build_all(
    incidents_dir: Path = Path("data/structured/incidents"),
    incidents_out: Path = Path("data/structured/aggregated/flat_incidents_combined.csv"),
    controls_out: Path = Path("data/derived/controls_combined.csv"),
) -> None:
    """Build all combined exports and print summary."""
    incident_count = build_flat_incidents(incidents_dir, incidents_out)
    control_count = build_controls_combined(incidents_dir, controls_out)

    # Per-source breakdown
    if incidents_out.exists():
        import pandas as pd
        df = pd.read_csv(incidents_out)
        counts = df["source_agency"].value_counts().to_dict()
        logger.info(f"Per-source counts: {counts}")

    print(f"Incidents: {incident_count} rows → {incidents_out}")
    print(f"Controls:  {control_count} rows → {controls_out}")
```

**Step 2: Run tests**

Run: `pytest tests/test_build_combined_exports.py -v`
Expected: All passed.

Run: `pytest -q`
Expected: All tests pass.

---

## Task 11: Combined Exports CLI Wiring

**Files:**
- Modify: `src/pipeline.py`

**Step 1: Add import** (after existing analytics imports)

```python
from src.analytics.build_combined_exports import build_all as build_combined_exports
```

**Step 2: Add command handler** (before `main()`)

```python
def cmd_build_combined_exports(args: argparse.Namespace) -> None:
    """Build combined flat CSV exports across all sources."""
    build_combined_exports(
        incidents_dir=Path(args.incidents_dir),
        incidents_out=Path(args.incidents_out),
        controls_out=Path(args.controls_out),
    )
```

**Step 3: Add subparser** (after `p_discover.set_defaults(func=cmd_discover_source)`, before `args = parser.parse_args()`)

```python
# build-combined-exports subcommand
p_combine = subparsers.add_parser(
    "build-combined-exports",
    help="Build combined flat CSV exports across all sources",
)
p_combine.add_argument(
    "--incidents-dir",
    default="data/structured/incidents",
    help="Root directory with structured JSON subdirectories",
)
p_combine.add_argument(
    "--incidents-out",
    default="data/structured/aggregated/flat_incidents_combined.csv",
    help="Output path for flat incidents CSV",
)
p_combine.add_argument(
    "--controls-out",
    default="data/derived/controls_combined.csv",
    help="Output path for combined controls CSV",
)
p_combine.set_defaults(func=cmd_build_combined_exports)
```

**Step 4: Verify**

Run: `python -m src.pipeline build-combined-exports --help`
Expected: Shows help with `--incidents-dir`, `--incidents-out`, `--controls-out`.

Run: `pytest -q`
Expected: All tests pass.

---

## Task 12: Install BeautifulSoup4

**Files:**
- Modify: `requirements.txt`

**Step 1: Add beautifulsoup4**

Add `beautifulsoup4` to `requirements.txt` (if not already present).

**Step 2: Install**

Run: `pip install beautifulsoup4`

---

## Task 13: Final Verification

**Step 1: Run full test suite**

Run: `pytest -v`
Expected: All tests pass (existing 254 + new tests).

**Step 2: Verify CLI commands**

Run:
```bash
python -m src.pipeline ingest-phmsa --help
python -m src.pipeline discover-source --source tsb --help
python -m src.pipeline build-combined-exports --help
```
Expected: All show help without errors.

**Step 3: List new/modified files**

Run: `git diff --stat && git ls-files --others --exclude-standard`

Expected new files:
- `src/ingestion/sources/phmsa_ingest.py`
- `src/ingestion/sources/tsb_discover.py`
- `src/ingestion/sources/tsb_ingest.py`
- `src/analytics/build_combined_exports.py`
- `tests/test_phmsa_ingest.py`
- `tests/test_tsb_discover.py`
- `tests/test_tsb_ingest.py`
- `tests/test_build_combined_exports.py`

Expected modified files:
- `src/pipeline.py` (imports + 3 new subcommands)
- `requirements.txt` (beautifulsoup4)

No other files modified.
