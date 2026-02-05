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
        # Try common formats
        for fmt in ["%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"]:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None
    except Exception:
        return None


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

            # Simple regex-based parsing (avoid BeautifulSoup dependency)
            # Look for investigation links and PDF links
            html = resp.text

            # Find investigation entries
            # Pattern: links to /investigations/detail/... and nearby PDF links
            investigation_pattern = r'href="(/investigations/[^"]+/)"[^>]*>([^<]+)</a>'
            pdf_pattern = r'href="([^"]+\.pdf)"'

            investigations = re.findall(investigation_pattern, html, re.IGNORECASE)
            pdfs = re.findall(pdf_pattern, html, re.IGNORECASE)

            if not investigations and not pdfs:
                logger.info(f"No more investigations found on page {page}")
                break

            # Match investigations with PDFs (simplified approach)
            for detail_path, title in investigations:
                if count >= limit:
                    break

                title = title.strip()
                detail_url = urljoin(CSB_BASE_URL, detail_path)

                # Try to find a PDF for this investigation
                # Look for PDF link that might be associated
                incident_id = _slugify(title) or f"csb-{count + 1}"

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
