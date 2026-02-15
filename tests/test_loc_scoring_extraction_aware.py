"""Tests for extraction-aware LOC scoring."""
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.nlp.loc_scoring import score_text, run_with_extraction_manifest


def _make_extraction_manifest(path: Path) -> None:
    """Write a test extraction manifest."""
    rows = [
        {
            "doc_id": "good-001",
            "pdf_path": "pdfs/good.pdf",
            "text_path": "good-001.txt",
            "extractor_used": "pymupdf",
            "text_len": 5000,
            "alpha_ratio": 0.82,
            "cid_ratio": 0.0,
            "whitespace_ratio": 0.15,
            "lang_guess": "unknown",
            "extraction_status": "OK",
            "fail_reason": "",
            "extracted_at": "2026-02-14T12:00:00",
        },
        {
            "doc_id": "bad-002",
            "pdf_path": "pdfs/bad.pdf",
            "text_path": "",
            "extractor_used": "pymupdf",
            "text_len": 50,
            "alpha_ratio": 0.1,
            "cid_ratio": 0.5,
            "whitespace_ratio": 0.8,
            "lang_guess": "unknown",
            "extraction_status": "EXTRACTION_FAILED",
            "fail_reason": "CID_ENCODING_GIBBERISH",
            "extracted_at": "2026-02-14T12:00:00",
        },
        {
            "doc_id": "bad-003",
            "pdf_path": "pdfs/empty.pdf",
            "text_path": "",
            "extractor_used": "none",
            "text_len": 0,
            "alpha_ratio": 0.0,
            "cid_ratio": 0.0,
            "whitespace_ratio": 0.0,
            "lang_guess": "unknown",
            "extraction_status": "EXTRACTION_FAILED",
            "fail_reason": "EMPTY_TEXT",
            "extracted_at": "2026-02-14T12:00:00",
        },
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


class TestRunWithExtractionManifest:
    def test_failed_extraction_not_scored_as_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = tmp_path / "extraction_manifest.csv"
            text_dir = tmp_path / "text"
            text_dir.mkdir()
            output_path = tmp_path / "scored.csv"

            _make_extraction_manifest(manifest_path)

            # Write text file for the OK document
            (text_dir / "good-001.txt").write_text(
                "The chemical release occurred at the oil refinery facility. " * 20,
                encoding="utf-8",
            )

            df = run_with_extraction_manifest(
                manifest_path=manifest_path,
                text_dir=text_dir,
                output_path=output_path,
            )

            assert len(df) == 3

            # Good doc should be scored
            good = df[df["doc_id"] == "good-001"].iloc[0]
            assert good["final_label"] in ("TRUE", "FALSE")
            assert pd.notna(good["loc_score"])
            assert good["extraction_status"] == "OK"

            # Bad docs should be EXTRACTION_FAILED, NOT False
            for doc_id in ("bad-002", "bad-003"):
                bad = df[df["doc_id"] == doc_id].iloc[0]
                assert bad["final_label"] == "EXTRACTION_FAILED"
                assert bad["extraction_status"] == "EXTRACTION_FAILED"
                assert pd.isna(bad["loc_score"]) or bad["loc_score"] == ""

    def test_output_csv_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = tmp_path / "extraction_manifest.csv"
            text_dir = tmp_path / "text"
            text_dir.mkdir()
            output_path = tmp_path / "scored.csv"

            _make_extraction_manifest(manifest_path)
            (text_dir / "good-001.txt").write_text(
                "The release of gas at the refinery caused an explosion. " * 20,
                encoding="utf-8",
            )

            run_with_extraction_manifest(manifest_path, text_dir, output_path)

            assert output_path.exists()
            result = pd.read_csv(output_path)
            assert "final_label" in result.columns
            assert "extraction_status" in result.columns
            assert "fail_reason" in result.columns

    def test_no_false_label_for_failed_extraction(self) -> None:
        """Critical: no EXTRACTION_FAILED row should ever have final_label=FALSE."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = tmp_path / "extraction_manifest.csv"
            text_dir = tmp_path / "text"
            text_dir.mkdir()
            output_path = tmp_path / "scored.csv"

            _make_extraction_manifest(manifest_path)
            (text_dir / "good-001.txt").write_text(
                "The chemical release occurred at the oil refinery facility. " * 20,
                encoding="utf-8",
            )

            df = run_with_extraction_manifest(manifest_path, text_dir, output_path)

            failed_rows = df[df["extraction_status"] == "EXTRACTION_FAILED"]
            assert len(failed_rows) == 2
            # CRITICAL: None of the failed rows should be labeled FALSE
            assert not (failed_rows["final_label"] == "FALSE").any()
            # They should all be EXTRACTION_FAILED
            assert (failed_rows["final_label"] == "EXTRACTION_FAILED").all()
