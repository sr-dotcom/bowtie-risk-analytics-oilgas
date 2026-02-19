"""Tests for corpus_v1 Claude extraction (offline, uses StubProvider)."""
import csv
import json
import logging
import pathlib

import pytest

from src.corpus.extract import run_corpus_extraction, _load_incident_text
from src.llm.stub import StubProvider
from src.validation.incident_validator import validate_incident_v23


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


def test_run_corpus_extraction_skips_blank_text(tmp_path, caplog):
    """An all-whitespace text file is skipped with a warning (not an error)."""
    raw_pdfs   = tmp_path / "raw_pdfs";       raw_pdfs.mkdir()
    structured = tmp_path / "structured_json"; structured.mkdir()
    manifests  = tmp_path / "manifests";       manifests.mkdir()
    txt_dir    = tmp_path / "csb_text";        txt_dir.mkdir()

    _make_pdf(raw_pdfs, "blank-incident")
    _make_txt(txt_dir, "blank-incident", content="\n  \n")  # only whitespace

    rows = [{
        "incident_id":       "blank-incident",
        "source_agency":     "CSB",
        "pdf_filename":      "blank-incident.pdf",
        "pdf_path":          str(raw_pdfs / "blank-incident.pdf"),
        "json_path":         "PENDING",
        "extraction_status": "needs_extraction",
    }]
    manifest_path = _write_manifest(manifests, rows)

    with caplog.at_level(logging.WARNING):
        count = run_corpus_extraction(
            manifest_path=manifest_path,
            structured_dir=structured,
            text_search_dirs=[txt_dir],
            provider=StubProvider(),
            delay_seconds=0,
        )

    assert count == 0
    assert list(structured.glob("*.json")) == []
    assert any("blank-incident" in r.message for r in caplog.records)


# ── New cheaper-protocol tests ─────────────────────────────────────────────────


def test_text_limit_truncates_long_text(tmp_path, caplog):
    """Text longer than text_limit is truncated; truncation is logged."""
    raw_pdfs   = tmp_path / "raw_pdfs";       raw_pdfs.mkdir()
    structured = tmp_path / "structured_json"; structured.mkdir()
    manifests  = tmp_path / "manifests";       manifests.mkdir()
    txt_dir    = tmp_path / "csb_text";        txt_dir.mkdir()

    long_text = "A" * 60_000  # 60 k chars, over the 50 k default
    _make_pdf(raw_pdfs, "long-incident")
    _make_txt(txt_dir, "long-incident", content=long_text)

    received: list[str] = []

    class CapturingProvider(StubProvider):
        def extract(self, prompt: str) -> str:
            received.append(prompt)
            return super().extract(prompt)

    rows = [{
        "incident_id":       "long-incident",
        "source_agency":     "CSB",
        "pdf_filename":      "long-incident.pdf",
        "pdf_path":          str(raw_pdfs / "long-incident.pdf"),
        "json_path":         "PENDING",
        "extraction_status": "needs_extraction",
    }]
    manifest_path = _write_manifest(manifests, rows)

    with caplog.at_level(logging.INFO):
        count = run_corpus_extraction(
            manifest_path=manifest_path,
            structured_dir=structured,
            text_search_dirs=[txt_dir],
            provider=CapturingProvider(),
            delay_seconds=0,
            text_limit=50_000,
        )

    assert count == 1
    assert len(received) == 1
    # The 60 k 'A' chars must not appear in the prompt — only 50 k of them do
    assert "A" * 60_000 not in received[0]
    assert any("truncated" in r.message for r in caplog.records)


def test_escalated_provider_used_on_max_tokens(tmp_path):
    """escalated_provider is invoked when primary returns stop_reason=max_tokens."""
    raw_pdfs   = tmp_path / "raw_pdfs";       raw_pdfs.mkdir()
    structured = tmp_path / "structured_json"; structured.mkdir()
    manifests  = tmp_path / "manifests";       manifests.mkdir()
    txt_dir    = tmp_path / "csb_text";        txt_dir.mkdir()

    _make_pdf(raw_pdfs, "csb-truncated")
    _make_txt(txt_dir, "csb-truncated", content="Explosion at plant.")

    class TruncatingProvider(StubProvider):
        """Always reports stop_reason=max_tokens (simulates truncated output)."""
        last_meta: dict = {}

        def extract(self, prompt: str) -> str:
            self.last_meta = {"stop_reason": "max_tokens"}
            return super().extract(prompt)

    escalated_calls: list[int] = []

    class EscalatedProvider(StubProvider):
        def extract(self, prompt: str) -> str:
            escalated_calls.append(1)
            return super().extract(prompt)

    rows = [{
        "incident_id":       "csb-truncated",
        "source_agency":     "CSB",
        "pdf_filename":      "csb-truncated.pdf",
        "pdf_path":          str(raw_pdfs / "csb-truncated.pdf"),
        "json_path":         "PENDING",
        "extraction_status": "needs_extraction",
    }]
    manifest_path = _write_manifest(manifests, rows)

    count = run_corpus_extraction(
        manifest_path=manifest_path,
        structured_dir=structured,
        text_search_dirs=[txt_dir],
        provider=TruncatingProvider(),
        escalated_provider=EscalatedProvider(),
        delay_seconds=0,
        primary_retries=1,
    )

    assert count == 1
    assert len(escalated_calls) >= 1, "escalated_provider should have been called"
    assert (structured / "csb-truncated.json").exists()


def test_fallback_provider_used_after_primary_and_escalated_fail(tmp_path):
    """fallback_provider is used when primary and escalated both raise errors."""
    raw_pdfs   = tmp_path / "raw_pdfs";       raw_pdfs.mkdir()
    structured = tmp_path / "structured_json"; structured.mkdir()
    manifests  = tmp_path / "manifests";       manifests.mkdir()
    txt_dir    = tmp_path / "csb_text";        txt_dir.mkdir()

    _make_pdf(raw_pdfs, "csb-hard")
    _make_txt(txt_dir, "csb-hard", content="Big complex incident.")

    class FailingProvider(StubProvider):
        def extract(self, prompt: str) -> str:
            raise RuntimeError("API error")

    fallback_calls: list[int] = []

    class FallbackProvider(StubProvider):
        def extract(self, prompt: str) -> str:
            fallback_calls.append(1)
            return super().extract(prompt)

    rows = [{
        "incident_id":       "csb-hard",
        "source_agency":     "CSB",
        "pdf_filename":      "csb-hard.pdf",
        "pdf_path":          str(raw_pdfs / "csb-hard.pdf"),
        "json_path":         "PENDING",
        "extraction_status": "needs_extraction",
    }]
    manifest_path = _write_manifest(manifests, rows)

    count = run_corpus_extraction(
        manifest_path=manifest_path,
        structured_dir=structured,
        text_search_dirs=[txt_dir],
        provider=FailingProvider(),
        escalated_provider=FailingProvider(),
        fallback_provider=FallbackProvider(),
        delay_seconds=0,
        primary_retries=1,
    )

    assert count == 1
    assert len(fallback_calls) >= 1, "fallback_provider should have been called"
    assert (structured / "csb-hard.json").exists()


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


# ── V2.3 normalisation guardrail tests ────────────────────────────────────────


def test_extracted_json_validates_as_v23(tmp_path):
    """Written JSON must pass validate_incident_v23 (canonical V2.3 check)."""
    raw_pdfs   = tmp_path / "raw_pdfs";       raw_pdfs.mkdir()
    structured = tmp_path / "structured_json"; structured.mkdir()
    manifests  = tmp_path / "manifests";       manifests.mkdir()
    txt_dir    = tmp_path / "csb_text";        txt_dir.mkdir()

    _make_pdf(raw_pdfs, "csb-validate")
    _make_txt(txt_dir,  "csb-validate", content="Explosion at chemical plant.")

    rows = [{
        "incident_id":       "csb-validate",
        "source_agency":     "CSB",
        "pdf_filename":      "csb-validate.pdf",
        "pdf_path":          str(raw_pdfs / "csb-validate.pdf"),
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

    out_json = structured / "csb-validate.json"
    assert out_json.exists(), "JSON not written"
    data = json.loads(out_json.read_text(encoding="utf-8"))
    is_valid, errors = validate_incident_v23(data)
    assert is_valid, f"Written JSON failed V2.3 validation: {errors[:3]}"


def test_normalization_applied_to_v23_wire_values(tmp_path):
    """LLM output using V2.3 wire values (side=left, lod=int) is normalised."""
    raw_pdfs   = tmp_path / "raw_pdfs";       raw_pdfs.mkdir()
    structured = tmp_path / "structured_json"; structured.mkdir()
    manifests  = tmp_path / "manifests";       manifests.mkdir()
    txt_dir    = tmp_path / "csb_text";        txt_dir.mkdir()

    _make_pdf(raw_pdfs, "csb-wire")
    _make_txt(txt_dir,  "csb-wire", content="Pipeline rupture incident.")

    class WireFormatProvider(StubProvider):
        """Returns JSON with V2.3 wire names: side=left, lod=int, status=worked."""
        def extract(self, prompt: str) -> str:
            import copy, json as _json
            sample = _json.loads(super().extract(prompt))
            for ctrl in sample.get("bowtie", {}).get("controls", []):
                ctrl["side"] = "left"
                ctrl["line_of_defense"] = 1
                ctrl.setdefault("performance", {})["barrier_status"] = "worked"
            return _json.dumps(sample)

    rows = [{
        "incident_id":       "csb-wire",
        "source_agency":     "CSB",
        "pdf_filename":      "csb-wire.pdf",
        "pdf_path":          str(raw_pdfs / "csb-wire.pdf"),
        "json_path":         "PENDING",
        "extraction_status": "needs_extraction",
    }]
    manifest_path = _write_manifest(manifests, rows)

    run_corpus_extraction(
        manifest_path=manifest_path,
        structured_dir=structured,
        text_search_dirs=[txt_dir],
        provider=WireFormatProvider(),
        delay_seconds=0,
    )

    out_json = structured / "csb-wire.json"
    assert out_json.exists()
    data = json.loads(out_json.read_text(encoding="utf-8"))

    controls = data.get("bowtie", {}).get("controls", [])
    assert len(controls) >= 1, "Expected at least one control"
    ctrl = controls[0]
    assert ctrl["side"] == "prevention",   f"side not normalised: {ctrl['side']}"
    assert ctrl["line_of_defense"] == "1st", f"lod not normalised: {ctrl['line_of_defense']}"
    assert ctrl["performance"]["barrier_status"] == "active", (
        f"barrier_status not normalised: {ctrl['performance']['barrier_status']}"
    )
    # And the whole payload must still validate
    is_valid, errors = validate_incident_v23(data)
    assert is_valid, f"Normalised JSON failed V2.3 validation: {errors[:3]}"
