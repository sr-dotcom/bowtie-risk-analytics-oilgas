"""Tests for corpus_v1 Claude extraction (offline, uses StubProvider)."""
import csv
import json
import logging
import pathlib

import pytest

from src.corpus.extract import run_corpus_extraction, _load_incident_text
from src.llm.stub import StubProvider


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_pdf(dir_: pathlib.Path, stem: str) -> None:
    (dir_ / f"{stem}.pdf").write_bytes(b"%PDF")


def _make_txt(dir_: pathlib.Path, stem: str, content: str = "Incident text.") -> None:
    (dir_ / f"{stem}.txt").write_text(content, encoding="utf-8")


def _make_json(dir_: pathlib.Path, stem: str) -> None:
    (dir_ / f"{stem}.json").write_text('{"incident_id": "x"}', encoding="utf-8")


def _write_manifest(manifests_dir: pathlib.Path, rows: list[dict]) -> pathlib.Path:
    out = manifests_dir / "corpus_v1_manifest.csv"
    fields = ["incident_id", "source_agency", "pdf_filename", "pdf_path",
              "json_path", "extraction_status"]
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return out


# ── tests ─────────────────────────────────────────────────────────────────────

def test_load_incident_text_from_text_dir(tmp_path):
    """_load_incident_text() finds .txt file in the text_search_dirs."""
    txt_dir = tmp_path / "text"
    txt_dir.mkdir()
    _make_txt(txt_dir, "csb-explosion", content="Explosion occurred.")

    result = _load_incident_text("csb-explosion", text_search_dirs=[txt_dir])
    assert result == "Explosion occurred."


def test_load_incident_text_missing_raises(tmp_path):
    """_load_incident_text() raises FileNotFoundError if no text file found."""
    with pytest.raises(FileNotFoundError, match="csb-missing"):
        _load_incident_text("csb-missing", text_search_dirs=[tmp_path])


def test_run_corpus_extraction_writes_json(tmp_path):
    """run_corpus_extraction() calls provider and writes JSON to structured_json/."""
    raw_pdfs   = tmp_path / "raw_pdfs";       raw_pdfs.mkdir()
    structured = tmp_path / "structured_json"; structured.mkdir()
    manifests  = tmp_path / "manifests";       manifests.mkdir()
    txt_dir    = tmp_path / "csb_text";        txt_dir.mkdir()

    _make_pdf(raw_pdfs, "csb-explosion")
    _make_txt(txt_dir,  "csb-explosion", content="Big explosion at plant.")

    rows = [{
        "incident_id":       "csb-explosion",
        "source_agency":     "CSB",
        "pdf_filename":      "csb-explosion.pdf",
        "pdf_path":          str(raw_pdfs / "csb-explosion.pdf"),
        "json_path":         "PENDING",
        "extraction_status": "needs_extraction",
    }]
    manifest_path = _write_manifest(manifests, rows)

    run_corpus_extraction(
        manifest_path=manifest_path,
        structured_dir=structured,
        text_search_dirs=[txt_dir],
        provider=StubProvider(),
        delay_seconds=0,
    )

    out_json = structured / "csb-explosion.json"
    assert out_json.exists(), "JSON not written to structured_json/"
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_run_corpus_extraction_skips_ready(tmp_path):
    """Already-ready entries are skipped (resume behaviour)."""
    raw_pdfs   = tmp_path / "raw_pdfs";       raw_pdfs.mkdir()
    structured = tmp_path / "structured_json"; structured.mkdir()
    manifests  = tmp_path / "manifests";       manifests.mkdir()

    _make_pdf(raw_pdfs,   "bsee-incident")
    _make_json(structured, "bsee-incident")

    rows = [{
        "incident_id":       "bsee-incident",
        "source_agency":     "BSEE",
        "pdf_filename":      "bsee-incident.pdf",
        "pdf_path":          str(raw_pdfs / "bsee-incident.pdf"),
        "json_path":         str(structured / "bsee-incident.json"),
        "extraction_status": "ready",
    }]
    manifest_path = _write_manifest(manifests, rows)

    call_count = {"n": 0}

    class CountingProvider(StubProvider):
        def extract(self, prompt: str) -> str:
            call_count["n"] += 1
            return super().extract(prompt)

    run_corpus_extraction(
        manifest_path=manifest_path,
        structured_dir=structured,
        text_search_dirs=[],
        provider=CountingProvider(),
        delay_seconds=0,
    )
    assert call_count["n"] == 0, "Provider should not be called for ready entries"


def test_run_corpus_extraction_error_logged(tmp_path, caplog):
    """Extraction errors are logged and do not abort the loop."""
    raw_pdfs   = tmp_path / "raw_pdfs";       raw_pdfs.mkdir()
    structured = tmp_path / "structured_json"; structured.mkdir()
    manifests  = tmp_path / "manifests";       manifests.mkdir()

    _make_pdf(raw_pdfs, "missing-text-file")

    rows = [{
        "incident_id":       "missing-text-file",
        "source_agency":     "CSB",
        "pdf_filename":      "missing-text-file.pdf",
        "pdf_path":          str(raw_pdfs / "missing-text-file.pdf"),
        "json_path":         "PENDING",
        "extraction_status": "needs_extraction",
    }]
    manifest_path = _write_manifest(manifests, rows)

    with caplog.at_level(logging.ERROR):
        run_corpus_extraction(
            manifest_path=manifest_path,
            structured_dir=structured,
            text_search_dirs=[],
            provider=StubProvider(),
            delay_seconds=0,
        )

    assert any("missing-text-file" in r.message for r in caplog.records)
    assert list(structured.glob("*.json")) == []
