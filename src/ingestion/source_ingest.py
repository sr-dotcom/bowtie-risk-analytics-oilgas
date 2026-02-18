"""Generic source ingestion: URL list or local PDFs → text extraction → manifest."""
import hashlib
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from src.ingestion.manifests import (
    SourceManifestRow,
    load_source_manifest,
    save_source_manifest,
)
from src.ingestion.pdf_text import extract_text_from_pdf

logger = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _doc_id_from_path(pdf_path: Path) -> str:
    """Derive a deterministic doc_id from a PDF filename."""
    return pdf_path.stem


def _load_url_list(url_list_path: Path) -> list[dict[str, str]]:
    """Load a URL list CSV with columns: url, doc_id (optional)."""
    import csv

    entries: list[dict[str, str]] = []
    with open(url_list_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("url", "").strip()
            if not url:
                continue
            doc_id = row.get("doc_id", "").strip()
            if not doc_id:
                # Derive from URL filename
                doc_id = Path(url.split("?")[0].split("#")[0]).stem
            entries.append({"url": url, "doc_id": doc_id})
    return entries


def _download_pdf(
    url: str, dest: Path, timeout: int = 60
) -> tuple[bool, Optional[str], Optional[str]]:
    """Download a PDF from a URL.

    Returns:
        (success, sha256_or_none, error_or_none)
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        session = requests.Session()
        session.headers["User-Agent"] = "BowtieRiskAnalytics/0.1 (academic research)"
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        sha = _sha256(dest)
        return True, sha, None
    except Exception as e:
        return False, None, str(e)


def ingest_from_url_list(
    url_list_path: Path,
    source: str,
    output_root: Path,
    existing_rows: list[SourceManifestRow],
    force: bool = False,
    timeout: int = 60,
) -> list[SourceManifestRow]:
    """Download PDFs from a URL list and extract text.

    Args:
        url_list_path: Path to CSV with url, doc_id columns.
        source: Source identifier (e.g. "phmsa").
        output_root: Root output directory (e.g. data/raw/phmsa/).
        existing_rows: Previously processed manifest rows.
        force: Re-process even if already done.
        timeout: Download timeout in seconds.

    Returns:
        List of SourceManifestRow for all processed items.
    """
    entries = _load_url_list(url_list_path)
    pdf_dir = output_root / "pdf"
    text_dir = output_root / "text"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    existing_by_id = {r.doc_id: r for r in existing_rows if r.source == source}
    results: list[SourceManifestRow] = []

    for entry in entries:
        doc_id = entry["doc_id"]
        url = entry["url"]

        # Check resumability
        prev = existing_by_id.get(doc_id)
        text_path = text_dir / f"{doc_id}.txt"
        if not force and prev and prev.status == "ok" and text_path.exists():
            logger.info(f"Skipping {doc_id}: already processed")
            results.append(prev)
            continue

        pdf_dest = pdf_dir / f"{doc_id}.pdf"
        pdf_rel = str(pdf_dest.relative_to(output_root))
        text_rel = str(text_path.relative_to(output_root))

        # Download
        ok, sha, err = _download_pdf(url, pdf_dest, timeout=timeout)
        if not ok:
            logger.warning(f"{doc_id}: download failed - {err}")
            results.append(SourceManifestRow(
                source=source,
                doc_id=doc_id,
                pdf_path=pdf_rel,
                text_path=text_rel,
                url=url,
                downloaded_at=datetime.now(timezone.utc),
                sha256=None,
                status="error",
                error=err,
            ))
            continue

        # Extract text
        _, page_count, char_count, text_err = extract_text_from_pdf(
            pdf_dest, text_path
        )
        status = "ok" if text_err is None else "error"

        results.append(SourceManifestRow(
            source=source,
            doc_id=doc_id,
            pdf_path=pdf_rel,
            text_path=text_rel,
            url=url,
            downloaded_at=datetime.now(timezone.utc),
            sha256=sha,
            status=status,
            error=text_err,
        ))
        logger.info(f"{doc_id}: {status} ({char_count} chars)")

    return results


def ingest_from_pdf_dir(
    pdf_input_dir: Path,
    source: str,
    output_root: Path,
    existing_rows: list[SourceManifestRow],
    force: bool = False,
) -> list[SourceManifestRow]:
    """Ingest PDFs from a local directory: copy to output and extract text.

    Args:
        pdf_input_dir: Directory containing PDF files.
        source: Source identifier (e.g. "phmsa").
        output_root: Root output directory (e.g. data/raw/phmsa/).
        existing_rows: Previously processed manifest rows.
        force: Re-process even if already done.

    Returns:
        List of SourceManifestRow for all processed items.
    """
    pdf_dir = output_root / "pdf"
    text_dir = output_root / "text"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    existing_by_id = {r.doc_id: r for r in existing_rows if r.source == source}
    results: list[SourceManifestRow] = []

    pdf_files = sorted(pdf_input_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDF files found in {pdf_input_dir}")
        return results

    for pdf_file in pdf_files:
        doc_id = _doc_id_from_path(pdf_file)
        text_path = text_dir / f"{doc_id}.txt"
        pdf_dest = pdf_dir / f"{doc_id}.pdf"
        pdf_rel = str(pdf_dest.relative_to(output_root))
        text_rel = str(text_path.relative_to(output_root))

        # Check resumability
        prev = existing_by_id.get(doc_id)
        if not force and prev and prev.status == "ok" and text_path.exists():
            logger.info(f"Skipping {doc_id}: already processed")
            results.append(prev)
            continue

        # Copy PDF to output dir (skip if same file)
        try:
            if pdf_dest.resolve() != pdf_file.resolve():
                shutil.copy2(pdf_file, pdf_dest)
        except Exception as e:
            logger.warning(f"{doc_id}: copy failed - {e}")
            results.append(SourceManifestRow(
                source=source,
                doc_id=doc_id,
                pdf_path=pdf_rel,
                text_path=text_rel,
                downloaded_at=datetime.now(timezone.utc),
                status="error",
                error=f"copy failed: {e}",
            ))
            continue

        sha = _sha256(pdf_dest)

        # Extract text
        _, page_count, char_count, text_err = extract_text_from_pdf(
            pdf_dest, text_path
        )
        status = "ok" if text_err is None else "error"

        results.append(SourceManifestRow(
            source=source,
            doc_id=doc_id,
            pdf_path=pdf_rel,
            text_path=text_rel,
            downloaded_at=datetime.now(timezone.utc),
            sha256=sha,
            status=status,
            error=text_err,
        ))
        logger.info(f"{doc_id}: {status} ({char_count} chars)")

    return results


def run_ingest(
    source: str,
    output_root: Path,
    url_list: Optional[Path] = None,
    input_pdf_dir: Optional[Path] = None,
    force: bool = False,
    timeout: int = 60,
) -> list[SourceManifestRow]:
    """Run the full ingestion pipeline.

    At least one of url_list or input_pdf_dir must be provided.

    Args:
        source: Source identifier.
        output_root: Root output directory.
        url_list: Path to URL list CSV (optional).
        input_pdf_dir: Path to local PDF directory (optional).
        force: Re-process even if already done.
        timeout: Download timeout in seconds.

    Returns:
        All manifest rows (existing + new).
    """
    if not url_list and not input_pdf_dir:
        raise ValueError("At least one of --url-list or --input-pdf-dir is required")

    manifest_path = output_root / "manifest.csv"
    existing_rows = load_source_manifest(manifest_path)
    logger.info(f"Loaded {len(existing_rows)} existing manifest rows")

    results: list[SourceManifestRow] = []

    if url_list:
        rows = ingest_from_url_list(
            url_list, source, output_root, existing_rows, force=force, timeout=timeout
        )
        results.extend(rows)

    if input_pdf_dir:
        rows = ingest_from_pdf_dir(
            input_pdf_dir, source, output_root, existing_rows, force=force
        )
        results.extend(rows)

    # Merge: new results overwrite existing by doc_id
    merged_by_id: dict[str, SourceManifestRow] = {}
    for row in existing_rows:
        merged_by_id[row.doc_id] = row
    for row in results:
        merged_by_id[row.doc_id] = row
    merged = list(merged_by_id.values())

    save_source_manifest(merged, manifest_path)
    logger.info(f"Saved {len(merged)} manifest rows to {manifest_path}")

    ok_count = sum(1 for r in merged if r.status == "ok")
    err_count = sum(1 for r in merged if r.status == "error")
    logger.info(f"Summary: {ok_count} ok, {err_count} errors, {len(merged)} total")

    return merged
