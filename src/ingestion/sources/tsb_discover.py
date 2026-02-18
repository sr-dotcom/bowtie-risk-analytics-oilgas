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
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

TSB_BASE_URL = "https://www.tsb.gc.ca"
TSB_PIPELINE_LISTING = "https://www.tsb.gc.ca/eng/reports/pipeline/index.html"
USER_AGENT = "BowtieRiskAnalytics/0.1 (academic research)"

# Matches TSB report IDs like P23H0001 anywhere in a URL path segment
_REPORT_ID_RE = re.compile(r"/(p\d{2}[a-z]\d{4})/", re.IGNORECASE)


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

    # Remove script and style elements globally
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    # Try <main> first
    main = soup.find("main")
    if main:
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

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/reports/pipeline/" not in href.lower():
            continue

        full_url = urljoin(base_url, href)
        doc_id = doc_id_from_url(full_url)

        if doc_id in seen:
            continue
        seen.add(doc_id)

        title = a_tag.get_text(strip=True)

        # Find adjacent date span
        date_str = ""
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
    return {"narrative": extract_narrative_from_html(html)}


def discover_tsb(
    base_url: str = TSB_BASE_URL,
    limit: Optional[int] = None,
    timeout: int = 30,
    sleep: float = 1.0,
) -> list[dict]:
    """Discover TSB pipeline investigation reports.

    Fetches the TSB pipeline listing page and extracts report URLs.

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
            logger.warning(f"TSB listing returned HTTP {resp.status_code}")
            return []
    except requests.RequestException as e:
        logger.error(f"Failed to fetch TSB listing: {e}")
        return []

    results = parse_listing_page(resp.text, base_url)

    if limit is not None:
        results = results[:limit]

    logger.info(f"Discovered {len(results)} TSB pipeline reports")
    return results


# ── CSV writers ──────────────────────────────────────────────────────────────


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
