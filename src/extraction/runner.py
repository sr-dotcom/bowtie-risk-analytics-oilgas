"""Orchestrator for extraction QC pipeline."""
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.extraction.extractor import extract_text
from src.extraction.manifest import ExtractionManifestRow, load_manifest, save_manifest
from src.extraction.normalize import normalize_text
from src.extraction.quality_gate import evaluate

logger = logging.getLogger(__name__)


def run_extraction_qc(
    pdf_dir: Path,
    output_dir: Path,
    manifest_path: Path,
    force: bool = False,
) -> list[ExtractionManifestRow]:
    """Run extraction QC on all PDFs in a directory.

    For each PDF:
    1. Extract text (multi-pass fallback)
    2. Run quality gate
    3. If passed, normalize text and write to output_dir
    4. Record result in manifest

    Args:
        pdf_dir: Directory containing PDF files.
        output_dir: Directory for normalized text output.
        manifest_path: Path for extraction manifest CSV.
        force: If True, reprocess even if already in manifest.

    Returns:
        List of all manifest rows (existing + new).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load existing manifest for resumability
    existing = load_manifest(manifest_path)
    existing_ids = {r.doc_id for r in existing}

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        logger.warning(f"No PDFs found in {pdf_dir}")
        return existing

    new_rows: list[ExtractionManifestRow] = []
    skipped = 0

    for pdf_path in pdfs:
        doc_id = pdf_path.stem

        if not force and doc_id in existing_ids:
            skipped += 1
            continue

        # 1. Extract
        result = extract_text(pdf_path)

        # Handle extraction error (all extractors failed)
        if result.error and not result.text:
            row = ExtractionManifestRow(
                doc_id=doc_id,
                pdf_path=str(pdf_path.name),
                text_path="",
                extractor_used=result.extractor_used,
                text_len=0,
                alpha_ratio=0.0,
                cid_ratio=0.0,
                whitespace_ratio=0.0,
                extraction_status="EXTRACTION_FAILED",
                fail_reason=f"EXTRACTOR_ERROR: {result.error}",
                extracted_at=datetime.now(timezone.utc).isoformat(),
            )
            new_rows.append(row)
            logger.warning(f"{doc_id}: extraction error — {result.error}")
            continue

        # 2. Quality gate
        qg = evaluate(result.text)

        if not qg.valid:
            row = ExtractionManifestRow(
                doc_id=doc_id,
                pdf_path=str(pdf_path.name),
                text_path="",
                extractor_used=result.extractor_used,
                text_len=qg.metrics.get("text_len", 0),
                alpha_ratio=qg.metrics.get("alpha_ratio", 0.0),
                cid_ratio=qg.metrics.get("cid_ratio", 0.0),
                whitespace_ratio=qg.metrics.get("whitespace_ratio", 0.0),
                extraction_status="EXTRACTION_FAILED",
                fail_reason=qg.fail_reason,
                extracted_at=datetime.now(timezone.utc).isoformat(),
            )
            new_rows.append(row)
            logger.info(f"{doc_id}: FAILED — {qg.fail_reason}")
            continue

        # 3. Normalize and write
        normalized = normalize_text(result.text)
        text_rel = f"{doc_id}.txt"
        text_path = output_dir / text_rel
        text_path.write_text(normalized, encoding="utf-8")

        row = ExtractionManifestRow(
            doc_id=doc_id,
            pdf_path=str(pdf_path.name),
            text_path=text_rel,
            extractor_used=result.extractor_used,
            text_len=qg.metrics["text_len"],
            alpha_ratio=qg.metrics["alpha_ratio"],
            cid_ratio=qg.metrics["cid_ratio"],
            whitespace_ratio=qg.metrics["whitespace_ratio"],
            extraction_status="OK",
            fail_reason=None,
            extracted_at=datetime.now(timezone.utc).isoformat(),
        )
        new_rows.append(row)
        logger.info(f"{doc_id}: OK ({result.extractor_used}, {qg.metrics['text_len']} chars)")

    # Merge: replace existing rows for reprocessed docs, keep others
    if force:
        new_ids = {r.doc_id for r in new_rows}
        merged = [r for r in existing if r.doc_id not in new_ids] + new_rows
    else:
        merged = existing + new_rows

    save_manifest(merged, manifest_path)

    # Summary
    ok_count = sum(1 for r in merged if r.extraction_status == "OK")
    fail_count = sum(1 for r in merged if r.extraction_status == "EXTRACTION_FAILED")

    logger.info(f"\n===== Extraction QC Summary =====")
    logger.info(f"  Total PDFs found   : {len(pdfs)}")
    logger.info(f"  Skipped (existing) : {skipped}")
    logger.info(f"  Processed          : {len(new_rows)}")
    logger.info(f"  OK                 : {ok_count}")
    logger.info(f"  EXTRACTION_FAILED  : {fail_count}")

    if fail_count > 0:
        from collections import Counter
        reasons = Counter(
            r.fail_reason for r in merged if r.extraction_status == "EXTRACTION_FAILED"
        )
        for reason, count in reasons.most_common():
            logger.info(f"    {reason}: {count}")

    return merged
