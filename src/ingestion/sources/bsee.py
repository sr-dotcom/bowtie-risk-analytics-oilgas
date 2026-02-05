"""BSEE (Bureau of Safety and Environmental Enforcement) incident source."""
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
    return text[:50]


def _extract_incident_id_from_pdf(pdf_url: str) -> str:
    """Extract incident ID from PDF filename."""
    filename = pdf_url.split("/")[-1]
    # Remove .pdf extension
    name = filename.rsplit(".", 1)[0] if "." in filename else filename
    return _slugify(name) or f"bsee-{hash(pdf_url) % 10000}"


def discover_bsee_incidents(limit: int = 20) -> Iterator[IncidentManifestRow]:
    """
    Scrape BSEE district investigation reports to discover incidents.

    Args:
        limit: Maximum number of incidents to discover.

    Yields:
        IncidentManifestRow objects with downloaded=False.
    """
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    count = 0

    # Scrape district reports page
    logger.info(f"Fetching BSEE district reports: {BSEE_DISTRICT_URL}")

    try:
        resp = session.get(BSEE_DISTRICT_URL, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"BSEE district page returned {resp.status_code}")
            return

        html = resp.text

        # Find PDF links in the page
        pdf_pattern = r'href="([^"]+\.pdf)"[^>]*>([^<]*)</a>'
        matches = re.findall(pdf_pattern, html, re.IGNORECASE)

        seen_urls = set()

        for pdf_href, link_text in matches:
            if count >= limit:
                break

            pdf_url = urljoin(BSEE_BASE_URL, pdf_href)

            # Skip duplicates
            if pdf_url in seen_urls:
                continue
            seen_urls.add(pdf_url)

            # Extract incident info
            incident_id = _extract_incident_id_from_pdf(pdf_url)
            title = link_text.strip() if link_text.strip() else incident_id

            # Try to extract date from filename or link text
            date_match = re.search(r"(\d{4})", pdf_url)
            date_occurred = f"{date_match.group(1)}-01-01" if date_match else None

            pdf_filename = pdf_url.split("/")[-1]

            yield IncidentManifestRow(
                source="bsee",
                incident_id=incident_id,
                title=title,
                date_occurred=date_occurred,
                detail_url=BSEE_DISTRICT_URL,
                pdf_url=pdf_url,
                pdf_path=f"bsee/pdfs/{pdf_filename}",
            )

            count += 1
            logger.info(f"Discovered BSEE incident: {incident_id}")

    except requests.RequestException as e:
        logger.error(f"Failed to fetch BSEE district page: {e}")


def download_bsee_pdf(
    row: IncidentManifestRow,
    base_dir: Path,
    session: requests.Session,
    timeout: int = 30,
) -> IncidentManifestRow:
    """
    Download PDF for a single BSEE incident.

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
