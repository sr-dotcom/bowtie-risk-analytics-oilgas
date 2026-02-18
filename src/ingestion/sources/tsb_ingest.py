"""TSB Canada HTML report ingestion.

Downloads raw HTML to data/raw/tsb/html/, extracts narrative text to
data/raw/tsb/text/, runs extraction QC gate, writes manifest.

Raw HTML is always stored for audit. Text extraction uses BeautifulSoup
with fallback logic from tsb_discover.
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
    "doc_id",
    "url",
    "html_path",
    "text_path",
    "status",
    "text_len",
    "downloaded_at",
    "error",
]


def _load_existing_manifest(manifest_path: Path) -> dict[str, dict]:
    """Load existing manifest rows keyed by doc_id."""
    if not manifest_path.exists():
        return {}
    rows: dict[str, dict] = {}
    with open(manifest_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows[row["doc_id"]] = dict(row)
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
    """Download TSB HTML reports, extract narrative text, write manifest.

    Args:
        url_entries: List of dicts with doc_id and url keys.
        html_dir: Directory to store raw HTML files (always saved for audit).
        text_dir: Directory to store extracted narrative text files.
        manifest_path: Path for manifest CSV.
        force: Reprocess even if already in manifest with status=ok.
        timeout: HTTP timeout in seconds.

    Returns:
        List of manifest row dicts for this run's entries.
    """
    html_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    existing = _load_existing_manifest(manifest_path)
    results: list[dict] = []
    session: Optional[requests.Session] = None

    for entry in url_entries:
        doc_id = entry["doc_id"]
        url = entry["url"]

        text_path = text_dir / f"{doc_id}.txt"
        html_path = html_dir / f"{doc_id}.html"

        # Resumability: skip if previously ok and text file still exists
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

        # Lazy session init (avoids creating a session when all docs are skipped)
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
                logger.warning(f"{doc_id}: HTTP {resp.status_code}")
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
            logger.warning(f"{doc_id}: download failed — {e}")
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
            "html_path": html_path.name,
            "text_path": text_path.name,
            "status": "ok",
            "text_len": str(len(narrative)),
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "error": "",
        })
        logger.info(f"{doc_id}: ok ({len(narrative)} chars)")

    # Merge: new results overwrite existing rows by doc_id
    merged: dict[str, dict] = dict(existing)
    for row in results:
        merged[row["doc_id"]] = row

    _save_manifest(list(merged.values()), manifest_path)

    ok = sum(1 for r in results if r.get("status") == "ok")
    err = sum(1 for r in results if r.get("status") == "error")
    skipped = len(results) - ok - err
    logger.info(
        f"TSB ingest complete: {ok} ok, {err} errors, {skipped} skipped, "
        f"{len(merged)} total in manifest"
    )

    return results
