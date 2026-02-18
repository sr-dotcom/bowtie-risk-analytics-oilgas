"""Tests for generic source ingestion scaffold."""
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.ingestion.manifests import (
    SourceManifestRow,
    load_source_manifest,
    save_source_manifest,
)
from src.ingestion.pdf_text import extract_text_from_pdf
from src.ingestion.source_ingest import (
    _doc_id_from_path,
    _sha256,
    ingest_from_pdf_dir,
    run_ingest,
)


# ── helpers ──────────────────────────────────────────────────────────────


def _make_pdf_with_text(path: Path, text: str = "hello") -> None:
    """Generate a tiny PDF containing *text* using reportlab."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 720, text)
    c.save()


# ── manifest round-trip ─────────────────────────────────────────────────


class TestSourceManifestRoundTrip:
    def test_save_and_load(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "manifest.csv"
        rows = [
            SourceManifestRow(
                source="phmsa",
                doc_id="DOC_001",
                pdf_path="pdf/DOC_001.pdf",
                text_path="text/DOC_001.txt",
                url="https://example.com/report.pdf",
                downloaded_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                sha256="abc123",
                status="ok",
            ),
            SourceManifestRow(
                source="phmsa",
                doc_id="DOC_002",
                pdf_path="pdf/DOC_002.pdf",
                text_path="text/DOC_002.txt",
                status="error",
                error="download failed",
            ),
        ]
        save_source_manifest(rows, manifest_path)

        loaded = load_source_manifest(manifest_path)
        assert len(loaded) == 2

        r0 = loaded[0]
        assert r0.source == "phmsa"
        assert r0.doc_id == "DOC_001"
        assert r0.status == "ok"
        assert r0.sha256 == "abc123"
        assert r0.url == "https://example.com/report.pdf"
        assert r0.downloaded_at is not None

        r1 = loaded[1]
        assert r1.status == "error"
        assert r1.error == "download failed"
        assert r1.sha256 is None
        assert r1.url is None

    def test_load_nonexistent_returns_empty(self, tmp_path: Path) -> None:
        assert load_source_manifest(tmp_path / "nope.csv") == []


# ── PDF text extraction ─────────────────────────────────────────────────


class TestPdfTextExtraction:
    def test_extract_text_returns_hello(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "sample.pdf"
        text_path = tmp_path / "sample.txt"
        _make_pdf_with_text(pdf_path, "hello")

        text, page_count, char_count, error = extract_text_from_pdf(
            pdf_path, text_path
        )
        assert error is None
        assert page_count == 1
        assert "hello" in text
        assert char_count > 0
        assert text_path.exists()
        assert "hello" in text_path.read_text()

    def test_extract_nonexistent_pdf(self, tmp_path: Path) -> None:
        text, pages, chars, err = extract_text_from_pdf(
            tmp_path / "no.pdf", tmp_path / "no.txt"
        )
        assert err is not None
        assert chars == 0


# ── resumable behaviour ─────────────────────────────────────────────────


class TestResumable:
    def test_skip_already_processed(self, tmp_path: Path) -> None:
        """If manifest has status=ok and text file exists, skip."""
        source = "test"
        output_root = tmp_path / "output"
        input_dir = tmp_path / "input_pdfs"
        input_dir.mkdir()

        # Create a PDF in the input dir
        _make_pdf_with_text(input_dir / "DOC_001.pdf", "hello")

        # First run: should process
        rows1 = ingest_from_pdf_dir(
            input_dir, source, output_root, existing_rows=[], force=False
        )
        assert len(rows1) == 1
        assert rows1[0].status == "ok"

        # Second run with existing rows: should skip
        rows2 = ingest_from_pdf_dir(
            input_dir, source, output_root, existing_rows=rows1, force=False
        )
        assert len(rows2) == 1
        assert rows2[0].status == "ok"
        # It should be the same row object (not re-processed)
        assert rows2[0].doc_id == rows1[0].doc_id

    def test_force_reprocesses(self, tmp_path: Path) -> None:
        """With --force, re-process even if already done."""
        source = "test"
        output_root = tmp_path / "output"
        input_dir = tmp_path / "input_pdfs"
        input_dir.mkdir()

        _make_pdf_with_text(input_dir / "DOC_001.pdf", "hello")

        rows1 = ingest_from_pdf_dir(
            input_dir, source, output_root, existing_rows=[], force=False
        )
        old_ts = rows1[0].downloaded_at

        # Force re-process
        rows2 = ingest_from_pdf_dir(
            input_dir, source, output_root, existing_rows=rows1, force=True
        )
        assert len(rows2) == 1
        assert rows2[0].status == "ok"
        # Should have a new timestamp
        assert rows2[0].downloaded_at >= old_ts

    def test_skip_requires_text_file(self, tmp_path: Path) -> None:
        """If manifest says ok but text file is missing, re-process."""
        source = "test"
        output_root = tmp_path / "output"
        input_dir = tmp_path / "input_pdfs"
        input_dir.mkdir()

        _make_pdf_with_text(input_dir / "DOC_001.pdf", "hello")

        # First run
        rows1 = ingest_from_pdf_dir(
            input_dir, source, output_root, existing_rows=[], force=False
        )
        assert rows1[0].status == "ok"

        # Delete the text file
        text_file = output_root / "text" / "DOC_001.txt"
        text_file.unlink()

        # Second run should re-process because text file is missing
        rows2 = ingest_from_pdf_dir(
            input_dir, source, output_root, existing_rows=rows1, force=False
        )
        assert len(rows2) == 1
        assert rows2[0].status == "ok"
        assert text_file.exists()


# ── run_ingest end-to-end ────────────────────────────────────────────────


class TestRunIngest:
    def test_end_to_end_pdf_dir(self, tmp_path: Path) -> None:
        input_dir = tmp_path / "pdfs"
        input_dir.mkdir()
        _make_pdf_with_text(input_dir / "report_alpha.pdf", "alpha content")
        _make_pdf_with_text(input_dir / "report_beta.pdf", "beta content")

        output_root = tmp_path / "out"
        rows = run_ingest(
            source="phmsa",
            output_root=output_root,
            input_pdf_dir=input_dir,
        )

        assert len(rows) == 2
        assert all(r.status == "ok" for r in rows)
        assert all(r.source == "phmsa" for r in rows)

        # Manifest was written
        manifest = output_root / "manifest.csv"
        assert manifest.exists()
        loaded = load_source_manifest(manifest)
        assert len(loaded) == 2

        # Text files were created
        for r in rows:
            text_file = output_root / r.text_path
            assert text_file.exists()
            assert len(text_file.read_text()) > 0

    def test_raises_without_input(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="At least one"):
            run_ingest(source="x", output_root=tmp_path)


# ── utility functions ────────────────────────────────────────────────────


class TestUtilities:
    def test_doc_id_from_path(self) -> None:
        assert _doc_id_from_path(Path("report_001.pdf")) == "report_001"
        assert _doc_id_from_path(Path("/a/b/c/my-file.pdf")) == "my-file"

    def test_sha256(self, tmp_path: Path) -> None:
        f = tmp_path / "test.bin"
        f.write_bytes(b"hello")
        h = _sha256(f)
        assert len(h) == 64
        assert h == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
