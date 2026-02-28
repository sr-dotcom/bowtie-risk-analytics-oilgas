"""PHMSA incident discovery adapter.

PHMSA (Pipeline and Hazardous Materials Safety Administration) publishes
bulk incident data CSVs but does NOT reliably provide per-incident PDF
report links.  This adapter:

1. Downloads the PHMSA incident summary CSV (or reads a local copy).
2. Extracts incident metadata (id, date, description, location).
3. Generates a *candidates* metadata CSV for manual enrichment.
4. Writes an empty (or minimal) url_list.csv — users add PDF links later.

Limitations:
- PHMSA bulk data CSVs contain incident metadata but rarely direct PDF links.
- Some incidents reference NTSB or state reports that may have PDFs.
- The adapter outputs candidates for manual or semi-automated enrichment.
"""
import csv
import logging
import re
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# PHMSA bulk data page (pipeline incidents)
PHMSA_BASE_URL = "https://www.phmsa.dot.gov"
PHMSA_DATA_URL = (
    "https://www.phmsa.dot.gov/data-and-statistics/pipeline/data-and-statistics-overview"
)
USER_AGENT = "BowtieRiskAnalytics/0.1 (academic research)"


def _slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text[:80]


# ── Parsing (no network) ────────────────────────────────────────────────


def parse_phmsa_page(html: str, base_url: str = PHMSA_BASE_URL) -> list[dict]:
    """Extract downloadable CSV/XLSX links from the PHMSA data page.

    Returns list of dicts with keys: doc_id, url, title, date, page_url, source.
    These are *data file* links (not individual report PDFs).
    """
    # Look for links to CSV, XLSX, or ZIP data files
    link_pattern = re.compile(
        r'href="([^"]+\.(?:csv|xlsx|zip))"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    results: list[dict] = []
    seen: set[str] = set()

    for m in link_pattern.finditer(html):
        href = m.group(1)
        link_text = re.sub(r"<[^>]+>", "", m.group(2)).strip()

        from urllib.parse import urljoin
        full_url = urljoin(base_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)

        filename = href.split("/")[-1]
        doc_id = _slugify(filename.rsplit(".", 1)[0]) if "." in filename else _slugify(filename)

        results.append({
            "doc_id": doc_id,
            "url": full_url,
            "title": link_text or filename,
            "date": "",
            "page_url": PHMSA_DATA_URL,
            "source": "phmsa",
        })

    return results


def parse_phmsa_incident_csv(csv_path: Path, limit: Optional[int] = None) -> list[dict]:
    """Parse a PHMSA incident data CSV into candidate records.

    PHMSA CSVs have varying column names. We look for common fields:
    - REPORT_NUMBER / report_number
    - INCIDENT_DATE / iyear
    - LOCATION / city + state
    - NARRATIVE / DESCRIPTION

    Returns list of dicts: doc_id, url (empty), title, date, page_url, source.
    """
    results: list[dict] = []

    try:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            fieldnames = [fn.lower().strip() for fn in (reader.fieldnames or [])]

            # Map common column names
            id_col = None
            for candidate in ["report_number", "report number", "reportnumber", "id"]:
                if candidate in fieldnames:
                    id_col = candidate
                    break

            date_col = None
            for candidate in ["incident_date", "incident date", "date", "iyear"]:
                if candidate in fieldnames:
                    date_col = candidate
                    break

            desc_col = None
            for candidate in ["narrative", "description", "summary"]:
                if candidate in fieldnames:
                    desc_col = candidate
                    break

            # Build a normalised key map: lower -> original
            key_map = {}
            if reader.fieldnames:
                for fn in reader.fieldnames:
                    key_map[fn.lower().strip()] = fn

            for i, row in enumerate(reader):
                if limit is not None and len(results) >= limit:
                    break

                # Access by original key
                report_id = row.get(key_map.get(id_col, ""), "") if id_col else f"phmsa-{i:05d}"
                report_id = report_id.strip() if report_id else f"phmsa-{i:05d}"
                doc_id = _slugify(report_id) if report_id else f"phmsa-{i:05d}"

                date_val = ""
                if date_col and key_map.get(date_col):
                    date_val = row.get(key_map[date_col], "").strip()

                title = ""
                if desc_col and key_map.get(desc_col):
                    raw_title = row.get(key_map[desc_col], "").strip()
                    title = raw_title[:200] if raw_title else ""

                results.append({
                    "doc_id": doc_id,
                    "url": "",  # PHMSA does not provide per-incident PDF links
                    "title": title or f"PHMSA incident {report_id}",
                    "date": date_val,
                    "page_url": PHMSA_DATA_URL,
                    "source": "phmsa",
                })

    except Exception as e:
        logger.error(f"Failed to parse PHMSA CSV {csv_path}: {e}")

    return results


# ── Network-aware discovery ─────────────────────────────────────────────


def discover_phmsa(
    base_url: str = PHMSA_BASE_URL,
    limit: Optional[int] = None,
    timeout: int = 30,
    sleep: float = 0.5,
) -> list[dict]:
    """Discover PHMSA incident data links.

    Since PHMSA does not provide per-incident PDF links reliably, this
    adapter scrapes the PHMSA data overview page for bulk data file
    download links (CSV/XLSX/ZIP).

    For per-incident records, use ``parse_phmsa_incident_csv()`` on a
    downloaded bulk CSV, which produces a candidates list for manual
    enrichment with PDF links.

    Returns:
        List of dicts with keys: doc_id, url, title, date, page_url, source.
        May be empty if no downloadable data files are found.
    """
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    data_url = f"{base_url}/data-and-statistics/pipeline/data-and-statistics-overview"
    logger.info(f"Fetching PHMSA data page: {data_url}")

    try:
        resp = session.get(data_url, timeout=timeout)
        if resp.status_code != 200:
            logger.warning(f"PHMSA page returned {resp.status_code}")
            return []
    except requests.RequestException as e:
        logger.error(f"Failed to fetch PHMSA page: {e}")
        return []

    results = parse_phmsa_page(resp.text, base_url)

    if limit is not None:
        results = results[:limit]

    if not results:
        logger.info(
            "No downloadable data file links found on PHMSA page. "
            "PHMSA does not provide stable per-incident PDF links. "
            "Consider downloading bulk CSV data manually from: "
            f"{data_url}"
        )

    logger.info(f"Discovered {len(results)} PHMSA data links")
    return results


# ── CSV writers ─────────────────────────────────────────────────────────


def write_url_list(results: list[dict], out_path: Path) -> None:
    """Write url_list.csv (doc_id,url). Only includes rows with non-empty URLs."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with_urls = [r for r in results if r.get("url")]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["doc_id", "url"])
        writer.writeheader()
        for r in with_urls:
            writer.writerow({"doc_id": r["doc_id"], "url": r["url"]})
    if not with_urls:
        logger.info(
            f"url_list.csv at {out_path} is empty (header only). "
            "PHMSA does not provide per-incident PDF links. "
            "Add links manually or use bulk CSV for candidate enrichment."
        )


def write_metadata(results: list[dict], out_path: Path) -> None:
    """Write metadata/candidates CSV."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["doc_id", "title", "date", "page_url", "url", "source"]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in fields})
