"""BSEE investigation discovery: find report PDF URLs from BSEE website.

Separates HTML fetching from parsing so tests can run offline.
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

BSEE_BASE_URL = "https://www.bsee.gov"
BSEE_DISTRICT_URL = (
    f"{BSEE_BASE_URL}/what-we-do/incident-investigations/"
    "offshore-incident-investigations/district-investigation-reports"
)
BSEE_PANEL_URL = (
    f"{BSEE_BASE_URL}/what-we-do/incident-investigations/"
    "offshore-incident-investigations/panel-investigation-reports"
)
USER_AGENT = "BowtieRiskAnalytics/0.1 (academic research)"


def _slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text[:80]


# ── HTML parsing (no network) ───────────────────────────────────────────


def parse_bsee_listing(html: str, base_url: str = BSEE_BASE_URL) -> list[dict]:
    """Extract PDF link records from a BSEE listing page.

    Returns list of dicts with keys: doc_id, url, title, date, page_url, source.
    """
    pdf_pattern = re.compile(r'href="([^"]+\.pdf)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    seen_urls: set[str] = set()
    results: list[dict] = []

    for m in pdf_pattern.finditer(html):
        href = m.group(1)
        link_text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        pdf_url = urljoin(base_url, href)

        if pdf_url in seen_urls:
            continue
        seen_urls.add(pdf_url)

        filename = href.split("/")[-1]
        name = filename.rsplit(".", 1)[0] if "." in filename else filename
        doc_id = _slugify(name) or f"bsee-{hash(pdf_url) % 10000}"
        title = link_text if link_text else doc_id

        # Try to extract year from filename
        year_match = re.search(r"(\d{4})", href)
        date = f"{year_match.group(1)}-01-01" if year_match else ""

        results.append({
            "doc_id": doc_id,
            "url": pdf_url,
            "title": title,
            "date": date,
            "page_url": "",  # filled by caller with the listing page URL
            "source": "bsee",
        })

    return results


# ── Network-aware discovery ─────────────────────────────────────────────


def discover_bsee(
    base_url: str = BSEE_BASE_URL,
    limit: Optional[int] = None,
    timeout: int = 30,
    sleep: float = 0.5,
) -> list[dict]:
    """Discover BSEE investigation report PDF URLs.

    Scrapes both district and panel investigation report pages.

    Args:
        base_url: BSEE website root URL.
        limit: Max reports to return (None = unlimited).
        timeout: HTTP request timeout.
        sleep: Delay between requests.

    Returns:
        List of dicts with keys: doc_id, url, title, date, page_url, source.
    """
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    district_url = (
        f"{base_url}/what-we-do/incident-investigations/"
        "offshore-incident-investigations/district-investigation-reports"
    )
    panel_url = (
        f"{base_url}/what-we-do/incident-investigations/"
        "offshore-incident-investigations/panel-investigation-reports"
    )

    all_results: list[dict] = []
    seen_ids: set[str] = set()

    for page_url in [district_url, panel_url]:
        if limit is not None and len(all_results) >= limit:
            break

        logger.info(f"Fetching BSEE listing: {page_url}")
        try:
            resp = session.get(page_url, timeout=timeout)
            if resp.status_code != 200:
                logger.warning(f"BSEE page returned {resp.status_code}: {page_url}")
                continue
        except requests.RequestException as e:
            logger.error(f"Failed to fetch BSEE page: {e}")
            continue

        records = parse_bsee_listing(resp.text, base_url)
        for rec in records:
            if limit is not None and len(all_results) >= limit:
                break
            if rec["doc_id"] in seen_ids:
                continue
            seen_ids.add(rec["doc_id"])
            rec["page_url"] = page_url
            all_results.append(rec)

        if sleep > 0:
            time.sleep(sleep)

    logger.info(f"Discovered {len(all_results)} BSEE reports")
    return all_results


# ── CSV writers (shared pattern) ────────────────────────────────────────


def write_url_list(results: list[dict], out_path: Path) -> None:
    """Write url_list.csv (doc_id,url)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["doc_id", "url"])
        writer.writeheader()
        for r in results:
            writer.writerow({"doc_id": r["doc_id"], "url": r["url"]})


def write_metadata(results: list[dict], out_path: Path) -> None:
    """Write metadata CSV."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["doc_id", "title", "date", "page_url", "url", "source"]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in fields})
