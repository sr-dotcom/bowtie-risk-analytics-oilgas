"""Tests for corpus_v1 manifest builder."""
import csv
import pathlib
import urllib.parse

import pytest

from src.corpus.manifest import build_manifest, write_manifest, CORPUS_V1_ROOT


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_pdf(dir_: pathlib.Path, name: str) -> pathlib.Path:
    p = dir_ / name
    p.write_bytes(b"%PDF-1.4")
    return p


def _make_json(dir_: pathlib.Path, name: str) -> pathlib.Path:
    p = dir_ / name
    p.write_text("{}", encoding="utf-8")
    return p


# ── tests ─────────────────────────────────────────────────────────────────────

def test_build_manifest_ready(tmp_path, monkeypatch):
    """PDF with a matching JSON → extraction_status=ready."""
    raw_pdfs = tmp_path / "raw_pdfs"
    raw_pdfs.mkdir()
    structured = tmp_path / "structured_json"
    structured.mkdir()

    _make_pdf(raw_pdfs, "incident-alpha.pdf")
    _make_json(structured, "incident-alpha.json")

    monkeypatch.setattr("src.corpus.manifest.CORPUS_V1_ROOT", tmp_path)

    rows = build_manifest()
    assert len(rows) == 1
    row = rows[0]
    assert row["incident_id"] == "incident-alpha"
    assert row["extraction_status"] == "ready"
    assert row["json_path"] != "PENDING"


def test_build_manifest_needs_extraction(tmp_path, monkeypatch):
    """PDF with no matching JSON → extraction_status=needs_extraction, json_path=PENDING."""
    raw_pdfs = tmp_path / "raw_pdfs"
    raw_pdfs.mkdir()
    (tmp_path / "structured_json").mkdir()

    _make_pdf(raw_pdfs, "incident-beta.pdf")

    monkeypatch.setattr("src.corpus.manifest.CORPUS_V1_ROOT", tmp_path)

    rows = build_manifest()
    assert len(rows) == 1
    assert rows[0]["extraction_status"] == "needs_extraction"
    assert rows[0]["json_path"] == "PENDING"


def test_build_manifest_url_encoded_stem(tmp_path, monkeypatch):
    """URL-encoded PDF filename decodes correctly as incident_id."""
    raw_pdfs = tmp_path / "raw_pdfs"
    raw_pdfs.mkdir()
    (tmp_path / "structured_json").mkdir()
    # Filename with %20 (space)
    _make_pdf(raw_pdfs, "02-May-2024_GC%20478_Murphy%20EV2010R.pdf")

    monkeypatch.setattr("src.corpus.manifest.CORPUS_V1_ROOT", tmp_path)

    rows = build_manifest()
    assert rows[0]["incident_id"] == "02-May-2024_GC 478_Murphy EV2010R"


def test_source_agency_bsee_inferred(tmp_path, monkeypatch, tmp_path_factory):
    """Stems found in bsee_pdfs_dir → BSEE; others → CSB."""
    raw_pdfs = tmp_path / "raw_pdfs"
    raw_pdfs.mkdir()
    (tmp_path / "structured_json").mkdir()

    bsee_dir = tmp_path_factory.mktemp("bsee_pdfs")
    _make_pdf(bsee_dir, "bsee-report.pdf")
    _make_pdf(raw_pdfs, "bsee-report.pdf")     # same stem
    _make_pdf(raw_pdfs, "csb-explosion.pdf")   # different stem

    monkeypatch.setattr("src.corpus.manifest.CORPUS_V1_ROOT", tmp_path)
    monkeypatch.setattr("src.corpus.manifest.BSEE_PDFS_DIR", bsee_dir)

    rows = {r["incident_id"]: r for r in build_manifest()}
    assert rows["bsee-report"]["source_agency"] == "BSEE"
    assert rows["csb-explosion"]["source_agency"] == "CSB"


def test_write_manifest_creates_csv(tmp_path, monkeypatch):
    """write_manifest() writes well-formed CSV with correct columns."""
    (tmp_path / "raw_pdfs").mkdir()
    (tmp_path / "structured_json").mkdir()
    (tmp_path / "manifests").mkdir()

    monkeypatch.setattr("src.corpus.manifest.CORPUS_V1_ROOT", tmp_path)

    rows = [
        {
            "incident_id": "test-incident",
            "source_agency": "CSB",
            "pdf_filename": "test-incident.pdf",
            "pdf_path": "data/corpus_v1/raw_pdfs/test-incident.pdf",
            "json_path": "PENDING",
            "extraction_status": "needs_extraction",
        }
    ]
    out = write_manifest(rows, tmp_path / "manifests" / "corpus_v1_manifest.csv")
    assert out.exists()

    with out.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        written = list(reader)

    assert written[0]["extraction_status"] == "needs_extraction"
    assert set(written[0].keys()) == {
        "incident_id", "source_agency", "pdf_filename",
        "pdf_path", "json_path", "extraction_status",
    }
