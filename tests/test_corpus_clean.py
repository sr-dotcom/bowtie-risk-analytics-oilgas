"""Tests for corpus_v1 noise JSON quarantine."""
import pathlib
import pytest

from src.corpus.clean import move_noise_jsons


def _pdf(d: pathlib.Path, stem: str) -> None:
    (d / f"{stem}.pdf").write_bytes(b"%PDF")


def _json(d: pathlib.Path, stem: str) -> None:
    (d / f"{stem}.json").write_text("{}", encoding="utf-8")


def test_dry_run_returns_noise_list(tmp_path):
    """dry_run=True returns names of noise JSONs without moving them."""
    raw  = tmp_path / "raw_pdfs";       raw.mkdir()
    jsns = tmp_path / "structured_json"; jsns.mkdir()

    _pdf(raw,  "real-incident")
    _json(jsns, "real-incident")              # matches → not noise
    _json(jsns, "Status_Change_Summary_FOO")  # no PDF → noise

    moved = move_noise_jsons(corpus_root=tmp_path, dry_run=True)

    assert moved == ["Status_Change_Summary_FOO.json"]
    # File must still be in original location
    assert (jsns / "Status_Change_Summary_FOO.json").exists()


def test_move_noise_json(tmp_path):
    """Noise JSONs are moved to structured_json_noise/."""
    raw  = tmp_path / "raw_pdfs";       raw.mkdir()
    jsns = tmp_path / "structured_json"; jsns.mkdir()

    _json(jsns, "SCS2")
    _json(jsns, "sample_incident_001")

    moved = move_noise_jsons(corpus_root=tmp_path)

    assert len(moved) == 2
    noise_dir = tmp_path / "structured_json_noise"
    assert (noise_dir / "SCS2.json").exists()
    assert (noise_dir / "sample_incident_001.json").exists()
    # Originals gone
    assert not (jsns / "SCS2.json").exists()
    assert not (jsns / "sample_incident_001.json").exists()


def test_matching_json_not_moved(tmp_path):
    """JSONs with a matching PDF are untouched."""
    raw  = tmp_path / "raw_pdfs";       raw.mkdir()
    jsns = tmp_path / "structured_json"; jsns.mkdir()

    _pdf(raw,  "real-incident")
    _json(jsns, "real-incident")

    moved = move_noise_jsons(corpus_root=tmp_path)
    assert moved == []
    assert (jsns / "real-incident.json").exists()


def test_url_encoded_pdf_matches_decoded_json(tmp_path):
    """URL-encoded PDF stem matches URL-decoded JSON stem correctly."""
    raw  = tmp_path / "raw_pdfs";       raw.mkdir()
    jsns = tmp_path / "structured_json"; jsns.mkdir()

    # PDF has %20 in name; JSON has decoded spaces
    _pdf(raw,  "GC%20478_Murphy%20EV2010R")
    _json(jsns, "GC 478_Murphy EV2010R")   # decoded form

    moved = move_noise_jsons(corpus_root=tmp_path)
    # Should not be moved — stems match after decoding both sides
    assert moved == []
