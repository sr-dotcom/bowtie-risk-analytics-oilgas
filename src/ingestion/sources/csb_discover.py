"""CSB investigation discovery: find report PDF URLs from the CSB website.

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

CSB_BASE_URL = "https://www.csb.gov"
CSB_COMPLETED_URL = f"{CSB_BASE_URL}/investigations/completed-investigations/"
USER_AGENT = "BowtieRiskAnalytics/0.1 (academic research)"

# Slugs in root-level hrefs that are NOT investigation detail pages.
_SLUG_DENYLIST = frozenset({
    "investigations", "completed-investigations", "current-investigations",
    "data-quality", "data-quality-", "about", "recommendations", "videos", "news",
})


def _slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text[:80]


def _parse_csb_date(date_str: str) -> Optional[str]:
    """Parse CSB date formats to YYYY-MM-DD."""
    if not date_str:
        return None
    for fmt in ["%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d"]:
        try:
            return __import__("datetime").datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ── HTML parsing (no network) ───────────────────────────────────────────


def parse_listing_page(html: str) -> list[tuple[str, str]]:
    """Extract ``(detail_path, title)`` pairs from a CSB listing page.

    Uses the "full investigation details" CTA pattern, falling back to
    ``<h3>``-based matching for simpler markup (test fixtures).
    """
    cta_pattern = re.compile(r"full\s+investigation\s+details", re.IGNORECASE)
    cta_positions = [m.start() for m in cta_pattern.finditer(html)]

    href_pattern = re.compile(r'href="(/[^"/]+/)"', re.IGNORECASE)
    seen: set[str] = set()
    results: list[tuple[str, str]] = []

    if cta_positions:
        for pos in cta_positions:
            window = html[max(0, pos - 2000):pos]
            for m in href_pattern.finditer(window):
                path = m.group(1)
                slug = path.strip("/")
                if slug.startswith("investigations") or len(slug) < 3:
                    continue
                if slug in _SLUG_DENYLIST or slug in seen:
                    continue
                seen.add(slug)
                title = slug.replace("-", " ").strip("- ").title()
                results.append((path, title))
    else:
        h3_pat = re.compile(
            r'<a\s[^>]*href="(/[^"/]+/)"[^>]*>.*?<h3[^>]*>(.*?)</h3>',
            re.DOTALL | re.IGNORECASE,
        )
        for m in h3_pat.finditer(html):
            path, title = m.group(1), m.group(2).strip()
            slug = path.strip("/")
            if slug in _SLUG_DENYLIST or slug in seen:
                continue
            seen.add(slug)
            results.append((path, title))

    return results


def _score_pdf_href(href: str) -> int:
    """Score a PDF href for likelihood of being a final investigation report.

    Higher is better.  Negative scores indicate recommendation / status-change
    documents that are NOT suitable for narrative extraction.
    """
    lower = href.lower()
    score = 0

    # Penalties for known "bad" patterns
    if "/assets/recommendation/" in lower:
        score -= 10
    if "status_change_summary" in lower:
        score -= 8
    if re.search(r"/scs[^/]*\.pdf$", lower):
        score -= 8

    # Bonuses for "good" keywords
    if "final" in lower:
        score += 3
    if "investigation" in lower:
        score += 2
    if "report" in lower:
        score += 1

    return score


def _extract_document_links(html: str) -> list[tuple[str, str]]:
    """Extract ``(href, anchor_text)`` for all ``<a>`` tags in *html*.

    Captures both simple and multi-line anchor tags.
    """
    return re.findall(
        r'<a\s[^>]*?href="([^"]+)"[^>]*?>(.*?)</a>',
        html,
        re.IGNORECASE | re.DOTALL,
    )


def parse_detail_page(html: str, base_url: str = CSB_BASE_URL) -> dict:
    """Extract the best report URL, title, and date from a CSB detail page.

    Priority order:
    1. Final Report DocumentId links  (``/file.aspx?DocumentId=\\d+``)
    2. Non-recommendation .pdf links  (scored by keyword relevance)
    3. Recommendation / status-change .pdf links (last resort, with warning)

    Returns dict with keys: pdf_url, title, date (all optional/nullable).
    """
    result: dict[str, Optional[str]] = {"pdf_url": None, "title": None, "date": None}

    # Title from <h1>
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    if h1:
        result["title"] = re.sub(r"<[^>]+>", "", h1.group(1)).strip()

    # Date
    date_match = re.search(
        r"Final Report Released On:\s*</strong>\s*(\d{2}/\d{2}/\d{4})", html
    )
    if not date_match:
        date_match = re.search(r"(\w+ \d{1,2}, \d{4})", html)
    if date_match:
        result["date"] = _parse_csb_date(date_match.group(1))

    # ── Tier 1: DocumentId final-report links ───────────────────────────
    all_links = _extract_document_links(html)
    doc_id_pat = re.compile(r"/file\.aspx\?DocumentId=\d+", re.IGNORECASE)

    final_report_links: list[tuple[str, str]] = []  # (href, anchor_text)
    for href, text in all_links:
        clean_text = re.sub(r"<[^>]+>", "", text).strip()
        if doc_id_pat.search(href) or "final report" in clean_text.lower():
            if doc_id_pat.search(href) or doc_id_pat.search(href):
                final_report_links.append((href, clean_text))
            elif href.lower().endswith(".pdf"):
                final_report_links.append((href, clean_text))

    if final_report_links:
        # Prefer the main report (not appendix) among DocumentId links
        main_reports = [
            (h, t) for h, t in final_report_links
            if "appendix" not in t.lower()
        ]
        best_href = (main_reports or final_report_links)[0][0]
        result["pdf_url"] = urljoin(base_url, best_href)
        return result

    # ── Tier 2 & 3: .pdf links, scored ──────────────────────────────────
    pdf_hrefs = re.findall(r'href="([^"]+\.pdf)"', html, re.IGNORECASE)
    if not pdf_hrefs:
        return result

    scored = [(href, _score_pdf_href(href)) for href in pdf_hrefs]
    scored.sort(key=lambda x: x[1], reverse=True)

    best_href, best_score = scored[0]
    if best_score < 0:
        logger.warning(
            f"Only recommendation/status-change PDFs found; "
            f"selecting best available: {best_href}"
        )
    result["pdf_url"] = urljoin(base_url, best_href)

    return result


# ── Network-aware discovery ─────────────────────────────────────────────


def discover_csb(
    base_url: str = CSB_BASE_URL,
    limit: Optional[int] = None,
    timeout: int = 30,
    sleep: float = 0.5,
) -> list[dict]:
    """Discover CSB investigation report PDF URLs.

    Args:
        base_url: CSB website root URL.
        limit: Max investigations to return (None = unlimited).
        timeout: HTTP request timeout.
        sleep: Delay between requests (polite crawling).

    Returns:
        List of dicts with keys: doc_id, url, title, date, page_url, source.
    """
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    completed_url = f"{base_url}/investigations/completed-investigations/"
    results: list[dict] = []
    seen_ids: set[str] = set()
    page = 1

    while True:
        if limit is not None and len(results) >= limit:
            break

        url = f"{completed_url}?pg={page}"
        logger.info(f"Fetching CSB listing page {page}: {url}")

        try:
            resp = session.get(url, timeout=timeout)
            if resp.status_code != 200:
                logger.warning(f"CSB page {page} returned {resp.status_code}")
                break
        except requests.RequestException as e:
            logger.error(f"Failed to fetch CSB page {page}: {e}")
            break

        cards = parse_listing_page(resp.text)
        if not cards:
            logger.info(f"No more investigations on page {page}")
            break

        for detail_path, listing_title in cards:
            if limit is not None and len(results) >= limit:
                break

            slug = detail_path.strip("/")
            if slug in seen_ids:
                continue
            seen_ids.add(slug)

            detail_url = urljoin(base_url, detail_path)

            if sleep > 0:
                time.sleep(sleep)

            try:
                detail_resp = session.get(detail_url, timeout=timeout)
                if detail_resp.status_code != 200:
                    logger.warning(f"Detail page {detail_url} returned {detail_resp.status_code}")
                    continue
            except requests.RequestException as e:
                logger.warning(f"Failed to fetch detail {detail_url}: {e}")
                continue

            info = parse_detail_page(detail_resp.text, base_url)
            if not info["pdf_url"]:
                logger.warning(f"No PDF found for {slug}")
                continue

            doc_id = _slugify(slug)
            results.append({
                "doc_id": doc_id,
                "url": info["pdf_url"],
                "title": info.get("title") or listing_title,
                "date": info.get("date") or "",
                "page_url": detail_url,
                "source": "csb",
            })
            logger.info(f"Discovered CSB: {doc_id}")

        page += 1

    return results


# ── CSV writers ─────────────────────────────────────────────────────────


def write_url_list(results: list[dict], out_path: Path) -> None:
    """Write url_list.csv (doc_id,url)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["doc_id", "url"])
        writer.writeheader()
        for r in results:
            writer.writerow({"doc_id": r["doc_id"], "url": r["url"]})


def write_metadata(results: list[dict], out_path: Path) -> None:
    """Write metadata CSV with extra columns."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["doc_id", "title", "date", "page_url", "url", "source"]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in fields})
