"""CSB (Chemical Safety Board) incident source."""
import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urljoin

import requests

from src.ingestion.manifests import IncidentManifestRow

logger = logging.getLogger(__name__)

CSB_BASE_URL = "https://www.csb.gov"
CSB_COMPLETED_URL = f"{CSB_BASE_URL}/investigations/completed-investigations/"

USER_AGENT = "BowtieRiskAnalytics/0.1 (academic research)"


def _slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text[:50]


def _parse_csb_date(date_str: str) -> Optional[str]:
    """Parse CSB date format to YYYY-MM-DD."""
    if not date_str:
        return None
    try:
        for fmt in ["%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d"]:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None
    except Exception:
        return None


# Slugs that appear in root-level hrefs but are NOT investigation detail pages.
_SLUG_DENYLIST = frozenset({
    "investigations",
    "completed-investigations",
    "current-investigations",
    "data-quality",
    "data-quality-",
    "about",
    "recommendations",
    "videos",
    "news",
})


def _extract_investigation_cards(html: str) -> list[tuple[str, str]]:
    """Return ``(href_path, title)`` pairs for investigation cards.

    Live CSB listing pages include a "full investigation details" CTA link
    inside each card.  We locate each CTA occurrence and search a window
    before it for root-level ``<a href="/<slug>/">`` links that are *not*
    under ``/investigations/``.

    Falls back to ``<h3>``-based matching for alternative markup / tests.

    A deny-list filters out remaining non-incident slugs.
    """
    cta_pattern = re.compile(r"full\s+investigation\s+details", re.IGNORECASE)
    cta_positions = [m.start() for m in cta_pattern.finditer(html)]

    href_pattern = re.compile(r'href="(/[^"/]+/)"', re.IGNORECASE)
    seen: set[str] = set()
    results: list[tuple[str, str]] = []

    if cta_positions:
        # CTA-based extraction: look in a 2000-char window before each CTA
        for pos in cta_positions:
            window_start = max(0, pos - 2000)
            window = html[window_start:pos]

            for m in href_pattern.finditer(window):
                path = m.group(1)
                slug = path.strip("/")

                if slug.startswith("investigations"):
                    continue
                if len(slug) < 3:
                    continue
                if slug in _SLUG_DENYLIST:
                    continue
                if slug in seen:
                    continue
                seen.add(slug)

                title = slug.replace("-", " ").strip("- ").title()
                results.append((path, title))
    else:
        # Fallback: <h3>-based extraction (tests, alternative markup)
        h3_pattern = re.compile(
            r'<a\s[^>]*href="(/[^"/]+/)"[^>]*>.*?<h3[^>]*>(.*?)</h3>',
            re.DOTALL | re.IGNORECASE,
        )
        for m in h3_pattern.finditer(html):
            path = m.group(1)
            title = m.group(2).strip()
            slug = path.strip("/")
            if slug in _SLUG_DENYLIST:
                continue
            if slug in seen:
                continue
            seen.add(slug)
            results.append((path, title))

    return results


def discover_csb_incidents(limit: int = 20) -> Iterator[IncidentManifestRow]:
    """
    Scrape CSB completed investigations to discover incidents.

    Args:
        limit: Maximum number of incidents to discover.

    Yields:
        IncidentManifestRow objects with downloaded=False.
    """
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    pdf_pattern = r'href="([^"]+\.pdf)"'
    seen_ids: set[str] = set()
    count = 0
    page = 1

    while count < limit:
        url = f"{CSB_COMPLETED_URL}?pg={page}"
        logger.info(f"Fetching CSB page {page}: {url}")

        try:
            resp = session.get(url, timeout=30)
            if resp.status_code != 200:
                logger.warning(f"CSB page {page} returned {resp.status_code}")
                break

            html = resp.text
            investigations = _extract_investigation_cards(html)

            if not investigations:
                logger.info(f"No more investigations found on page {page}")
                break

            for detail_path, title in investigations:
                if count >= limit:
                    break

                # Derive incident_id from the URL slug (stable, unique)
                incident_id = detail_path.strip("/")

                # Deduplicate across pages
                if incident_id in seen_ids:
                    continue
                seen_ids.add(incident_id)

                detail_url = urljoin(CSB_BASE_URL, detail_path)

                # Fetch detail page to get PDF link
                try:
                    detail_resp = session.get(detail_url, timeout=30)
                    if detail_resp.status_code == 200:
                        detail_pdfs = re.findall(pdf_pattern, detail_resp.text)
                        # Look for "final report" or similar
                        pdf_url = None
                        for pdf_href in detail_pdfs:
                            if any(
                                kw in pdf_href.lower()
                                for kw in ["final", "report", "investigation"]
                            ):
                                pdf_url = urljoin(CSB_BASE_URL, pdf_href)
                                break
                        if not pdf_url and detail_pdfs:
                            pdf_url = urljoin(CSB_BASE_URL, detail_pdfs[0])

                        if pdf_url:
                            # Extract date if available
                            date_match = re.search(
                                r"Final Report Released On:\s*</strong>\s*(\d{2}/\d{2}/\d{4})",
                                detail_resp.text,
                            )
                            if not date_match:
                                # Fallback to any date pattern
                                date_match = re.search(
                                    r"(\w+ \d{1,2}, \d{4})", detail_resp.text
                                )
                            date_occurred = (
                                _parse_csb_date(date_match.group(1))
                                if date_match
                                else None
                            )

                            pdf_filename = pdf_url.split("/")[-1]
                            if not pdf_filename.endswith(".pdf"):
                                pdf_filename = f"{incident_id}.pdf"

                            yield IncidentManifestRow(
                                source="csb",
                                incident_id=incident_id,
                                title=title,
                                date_occurred=date_occurred,
                                detail_url=detail_url,
                                pdf_url=pdf_url,
                                pdf_path=f"csb/pdfs/{pdf_filename}",
                            )
                            count += 1
                            logger.info(f"Discovered CSB incident: {incident_id}")

                except requests.RequestException as e:
                    logger.warning(f"Failed to fetch detail page {detail_url}: {e}")
                    continue

            page += 1

        except requests.RequestException as e:
            logger.error(f"Failed to fetch CSB page {page}: {e}")
            break


def download_csb_pdf(
    row: IncidentManifestRow,
    base_dir: Path,
    session: requests.Session,
    timeout: int = 30,
) -> IncidentManifestRow:
    """
    Download PDF for a single CSB incident.

    Args:
        row: Incident manifest row with pdf_url.
        base_dir: Base directory for downloads.
        session: Requests session to use.
        timeout: Request timeout in seconds.

    Returns:
        Updated IncidentManifestRow with download status.
    """
    pdf_full_path = base_dir / row.pdf_path
    pdf_full_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with session.get(row.pdf_url, stream=True, timeout=timeout) as resp:
            updated = {
                "retrieved_at": datetime.now(timezone.utc),
                "http_status": resp.status_code,
                "content_type": resp.headers.get("Content-Type", ""),
            }

            if resp.status_code != 200:
                return row.model_copy(update={**updated, "downloaded": False})

            # Validate PDF content type
            content_type = updated["content_type"].lower()
            is_pdf = "pdf" in content_type or row.pdf_url.lower().endswith(".pdf")

            if not is_pdf:
                return row.model_copy(
                    update={
                        **updated,
                        "downloaded": False,
                        "error": f"Not a PDF: {content_type}",
                    }
                )

            # Stream to disk with incremental hash
            sha = hashlib.sha256()
            size = 0

            with open(pdf_full_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    sha.update(chunk)
                    size += len(chunk)

            return row.model_copy(
                update={
                    **updated,
                    "downloaded": True,
                    "file_size_bytes": size,
                    "sha256": sha.hexdigest(),
                }
            )

    except requests.RequestException as e:
        logger.warning(f"Failed to download {row.incident_id}: {e}")
        return row.model_copy(
            update={
                "retrieved_at": datetime.now(timezone.utc),
                "downloaded": False,
                "error": str(e),
            }
        )
