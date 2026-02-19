# Corpus V1 Build Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Produce `data/corpus_v1/manifests/corpus_v1_manifest.csv`, quarantine 66 noise JSONs into `structured_json_noise/`, and extract the 48 missing CSB PDFs into `structured_json/` using Claude only.

**Architecture:** New `src/corpus/` package (manifest, clean, extract modules) with three corresponding CLI subcommands added to `src/pipeline.py`. CSB text is read from `data/raw/csb/text/` (all 48 have pre-extracted `.txt` files — no PDF parsing needed). After extraction, in-place `convert-schema` pass promotes all 48 new JSONs to V2.3.

**Tech Stack:** Python 3.10+, Pydantic v2, existing `AnthropicProvider` + `load_prompt` + `_parse_llm_json`, argparse subcommands, `pytest` with `tmp_path`.

---

## Pre-flight checks

```bash
# From repo root, venv active
python -m pytest -q --tb=no   # must show 306 passed
python -m src.pipeline --help  # verify CLI loads
```

---

## Task 1: corpus manifest builder

### Scope

Create `src/corpus/manifest.py` with a pure function `build_manifest()` and `write_manifest()`, and register a `corpus-manifest` subcommand in `src/pipeline.py`.

**Files:**
- Create: `src/corpus/__init__.py`
- Create: `src/corpus/manifest.py`
- Create: `tests/test_corpus_manifest.py`
- Modify: `src/pipeline.py` (two spots: import + subparser registration)

---

**Step 1.1 — Create the empty package**

```bash
touch src/corpus/__init__.py
```

---

**Step 1.2 — Write failing tests first**

Create `tests/test_corpus_manifest.py`:

```python
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
```

**Step 1.3 — Run tests to confirm they fail**

```bash
python -m pytest tests/test_corpus_manifest.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.corpus.manifest'`

---

**Step 1.4 — Implement `src/corpus/manifest.py`**

```python
"""corpus_v1 manifest builder.

Scans corpus_v1/raw_pdfs/ and corpus_v1/structured_json/ to produce
a corpus_v1_manifest.csv with one row per PDF.
"""
import csv
import pathlib
import urllib.parse
from typing import Any

CORPUS_V1_ROOT = pathlib.Path("data/corpus_v1")
BSEE_PDFS_DIR  = pathlib.Path("data/raw/bsee/pdfs")

_MANIFEST_COLUMNS = [
    "incident_id",
    "source_agency",
    "pdf_filename",
    "pdf_path",
    "json_path",
    "extraction_status",
]


def _bsee_stems() -> set[str]:
    """Return URL-decoded stems of every PDF in the canonical BSEE directory."""
    if not BSEE_PDFS_DIR.exists():
        return set()
    return {urllib.parse.unquote(f.stem) for f in BSEE_PDFS_DIR.glob("*.pdf")}


def build_manifest() -> list[dict[str, Any]]:
    """Cross-reference raw_pdfs/ vs structured_json/ and return manifest rows.

    Each row has keys: incident_id, source_agency, pdf_filename, pdf_path,
    json_path, extraction_status.
    """
    raw_pdfs      = CORPUS_V1_ROOT / "raw_pdfs"
    structured    = CORPUS_V1_ROOT / "structured_json"

    bsee = _bsee_stems()
    json_by_stem  = {
        urllib.parse.unquote(f.stem): f
        for f in structured.glob("*.json")
    }

    rows: list[dict[str, Any]] = []
    for pdf in sorted(raw_pdfs.glob("*.pdf")):
        stem   = urllib.parse.unquote(pdf.stem)
        agency = "BSEE" if stem in bsee else "CSB"
        json_f = json_by_stem.get(stem)

        rows.append({
            "incident_id":       stem,
            "source_agency":     agency,
            "pdf_filename":      pdf.name,
            "pdf_path":          str(pdf),
            "json_path":         str(json_f) if json_f else "PENDING",
            "extraction_status": "ready" if json_f else "needs_extraction",
        })
    return rows


def write_manifest(
    rows: list[dict[str, Any]],
    out_path: pathlib.Path,
) -> pathlib.Path:
    """Write rows to a CSV file at out_path.  Returns out_path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return out_path
```

**Step 1.5 — Run tests to confirm they pass**

```bash
python -m pytest tests/test_corpus_manifest.py -v
```

Expected: 5 passed.

---

**Step 1.6 — Add `corpus-manifest` subcommand to `src/pipeline.py`**

At the top of `src/pipeline.py`, add to imports:

```python
from src.corpus.manifest import build_manifest, write_manifest, CORPUS_V1_ROOT
```

Add the `cmd_` function before `main()`:

```python
def cmd_corpus_manifest(args: argparse.Namespace) -> None:
    """Build or refresh corpus_v1_manifest.csv."""
    rows = build_manifest()
    out  = CORPUS_V1_ROOT / "manifests" / "corpus_v1_manifest.csv"
    write_manifest(rows, out)
    ready  = sum(1 for r in rows if r["extraction_status"] == "ready")
    pending = sum(1 for r in rows if r["extraction_status"] == "needs_extraction")
    logger.info(f"Manifest written → {out}  ({ready} ready, {pending} needs_extraction)")
```

Inside `main()`, after the last `add_parser` block (before `parser.parse_args()`):

```python
    p_cm = subparsers.add_parser(
        "corpus-manifest",
        help="Build/refresh data/corpus_v1/manifests/corpus_v1_manifest.csv",
    )
    p_cm.set_defaults(func=cmd_corpus_manifest)
```

**Step 1.7 — Smoke-test the CLI**

```bash
python -m src.pipeline corpus-manifest
```

Expected: log line like `Manifest written → data/corpus_v1/manifests/corpus_v1_manifest.csv  (100 ready, 48 needs_extraction)`

```bash
head -3 data/corpus_v1/manifests/corpus_v1_manifest.csv
```

Expected: header row + at least two data rows with correct columns.

---

**Step 1.8 — Run full test suite**

```bash
python -m pytest -q --tb=short
```

Expected: ≥311 passed (306 existing + 5 new), 0 failures.

---

**Step 1.9 — Commit**

```bash
git add src/corpus/__init__.py src/corpus/manifest.py tests/test_corpus_manifest.py src/pipeline.py
git commit -m "feat: add corpus-manifest subcommand (Task 1)"
```

---

## Task 2: quarantine noise JSONs

### Scope

Move JSONs whose URL-decoded stem has no matching PDF in `raw_pdfs/` into `structured_json_noise/`. Implement as `src/corpus/clean.py` + `corpus-clean` subcommand. Supports `--dry-run`.

**Files:**
- Create: `src/corpus/clean.py`
- Create: `tests/test_corpus_clean.py`
- Modify: `src/pipeline.py`

---

**Step 2.1 — Write failing tests**

Create `tests/test_corpus_clean.py`:

```python
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
    raw  = tmp_path / "raw_pdfs";      raw.mkdir()
    jsns = tmp_path / "structured_json"; jsns.mkdir()

    _pdf(raw,  "real-incident")
    _json(jsns, "real-incident")   # matches → not noise
    _json(jsns, "Status_Change_Summary_FOO")  # no PDF → noise

    moved = move_noise_jsons(corpus_root=tmp_path, dry_run=True)

    assert moved == ["Status_Change_Summary_FOO.json"]
    # File must still be in original location
    assert (jsns / "Status_Change_Summary_FOO.json").exists()


def test_move_noise_json(tmp_path):
    """Noise JSONs are moved to structured_json_noise/."""
    raw  = tmp_path / "raw_pdfs";      raw.mkdir()
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
    raw  = tmp_path / "raw_pdfs";      raw.mkdir()
    jsns = tmp_path / "structured_json"; jsns.mkdir()

    _pdf(raw,  "real-incident")
    _json(jsns, "real-incident")

    moved = move_noise_jsons(corpus_root=tmp_path)
    assert moved == []
    assert (jsns / "real-incident.json").exists()


def test_url_encoded_pdf_matches_decoded_json(tmp_path):
    """URL-encoded PDF stem matches URL-decoded JSON stem correctly."""
    raw  = tmp_path / "raw_pdfs";      raw.mkdir()
    jsns = tmp_path / "structured_json"; jsns.mkdir()

    # PDF has %20 in name; JSON has spaces
    _pdf(raw,  "GC%20478_Murphy%20EV2010R")
    _json(jsns, "GC 478_Murphy EV2010R")   # decoded form

    moved = move_noise_jsons(corpus_root=tmp_path)
    # Should not be moved — stems match after decoding
    assert moved == []
```

**Step 2.2 — Run tests to confirm failure**

```bash
python -m pytest tests/test_corpus_clean.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.corpus.clean'`

---

**Step 2.3 — Implement `src/corpus/clean.py`**

```python
"""corpus_v1 noise JSON quarantine.

Moves JSONs in structured_json/ that have no matching PDF in raw_pdfs/
into structured_json_noise/.
"""
import pathlib
import shutil
import urllib.parse

from src.corpus.manifest import CORPUS_V1_ROOT


def move_noise_jsons(
    corpus_root: pathlib.Path | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Move JSON files with no matching PDF to structured_json_noise/.

    Args:
        corpus_root: Override the default CORPUS_V1_ROOT (useful for tests).
        dry_run: If True, return the list without moving anything.

    Returns:
        List of filenames that were (or would be) moved.
    """
    root       = corpus_root or CORPUS_V1_ROOT
    raw_pdfs   = root / "raw_pdfs"
    structured = root / "structured_json"
    noise_dir  = root / "structured_json_noise"

    pdf_stems = {
        urllib.parse.unquote(f.stem)
        for f in raw_pdfs.glob("*.pdf")
    }

    moved: list[str] = []
    for json_f in sorted(structured.glob("*.json")):
        stem = urllib.parse.unquote(json_f.stem)
        if stem not in pdf_stems:
            if not dry_run:
                noise_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(json_f), noise_dir / json_f.name)
            moved.append(json_f.name)

    return moved
```

**Step 2.4 — Run tests to confirm they pass**

```bash
python -m pytest tests/test_corpus_clean.py -v
```

Expected: 4 passed.

---

**Step 2.5 — Add `corpus-clean` subcommand to `src/pipeline.py`**

Add import at top:

```python
from src.corpus.clean import move_noise_jsons
```

Add `cmd_` function before `main()`:

```python
def cmd_corpus_clean(args: argparse.Namespace) -> None:
    """Quarantine noise JSONs (no matching PDF) into structured_json_noise/."""
    moved = move_noise_jsons(dry_run=args.dry_run)
    action = "Would move" if args.dry_run else "Moved"
    for name in moved:
        logger.info(f"  {action}: {name}")
    logger.info(f"{action} {len(moved)} noise JSON(s).")
```

Add subparser in `main()`:

```python
    p_cc = subparsers.add_parser(
        "corpus-clean",
        help="Move no-match JSONs from structured_json/ to structured_json_noise/",
    )
    p_cc.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be moved without moving anything",
    )
    p_cc.set_defaults(func=cmd_corpus_clean)
```

**Step 2.6 — Dry-run check, then execute**

```bash
python -m src.pipeline corpus-clean --dry-run
```

Expected: lists 66 filenames like `Status_Change_Summary_ACC_...json`, `SCS2.json`, etc.

```bash
python -m src.pipeline corpus-clean
```

Expected: `Moved 66 noise JSON(s).`

```bash
ls data/corpus_v1/structured_json_noise/ | wc -l
# Expected: 66
ls data/corpus_v1/structured_json/ | wc -l
# Expected: 100
```

---

**Step 2.7 — Refresh manifest**

```bash
python -m src.pipeline corpus-manifest
```

Expected log: `100 ready, 48 needs_extraction`

---

**Step 2.8 — Run full test suite**

```bash
python -m pytest -q --tb=short
```

Expected: ≥315 passed, 0 failures.

---

**Step 2.9 — Commit**

```bash
git add src/corpus/clean.py tests/test_corpus_clean.py src/pipeline.py
git commit -m "feat: add corpus-clean subcommand; quarantine 66 noise JSONs (Task 2)"
```

---

## Task 3: Claude extraction for 48 CSB PDFs

### Scope

Implement `src/corpus/extract.py` with a `run_corpus_extraction()` function. Reads `needs_extraction` rows from the manifest, loads pre-extracted text from `data/raw/csb/text/`, calls `AnthropicProvider`, parses JSON, writes to `structured_json/`. After all 48 are done, runs the existing `convert-schema` pass in-place to normalise to V2.3. Manifest is refreshed last.

All 48 missing PDFs are CSB investigation reports. Confirmed: all 48 have matching `.txt` files in `data/raw/csb/text/`.

**Files:**
- Create: `src/corpus/extract.py`
- Create: `tests/test_corpus_extract.py`
- Modify: `src/pipeline.py`

**Key imports to use:**

```python
from src.ingestion.structured import _parse_llm_json   # JSON extraction from LLM response
from src.prompts.loader import load_prompt              # assembles full prompt
from src.llm.base import LLMProvider                    # ABC for type hints
from src.llm.anthropic_provider import AnthropicProvider
from src.llm.stub import StubProvider                   # for tests
```

---

**Step 3.1 — Inspect StubProvider interface**

Before writing tests, verify the stub's signature:

```bash
grep -n "class StubProvider\|def extract" src/llm/stub.py
```

Expected: `def extract(self, prompt: str) -> str` returning a hard-coded JSON string.

---

**Step 3.2 — Write failing tests**

Create `tests/test_corpus_extract.py`:

```python
"""Tests for corpus_v1 Claude extraction (offline, uses StubProvider)."""
import csv
import json
import pathlib

import pytest

from src.corpus.extract import run_corpus_extraction, _load_incident_text
from src.corpus.manifest import build_manifest, write_manifest
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


def test_run_corpus_extraction_writes_json(tmp_path, monkeypatch):
    """run_corpus_extraction() calls provider and writes JSON to structured_json/."""
    # Set up corpus_v1 layout
    raw_pdfs    = tmp_path / "raw_pdfs";       raw_pdfs.mkdir()
    structured  = tmp_path / "structured_json"; structured.mkdir()
    manifests   = tmp_path / "manifests";       manifests.mkdir()
    txt_dir     = tmp_path / "csb_text";        txt_dir.mkdir()

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

    provider = StubProvider()

    run_corpus_extraction(
        manifest_path=manifest_path,
        structured_dir=structured,
        text_search_dirs=[txt_dir],
        provider=provider,
    )

    out_json = structured / "csb-explosion.json"
    assert out_json.exists(), "JSON not written to structured_json/"
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_run_corpus_extraction_skips_ready(tmp_path, monkeypatch):
    """Already-ready entries are skipped (resume behaviour)."""
    raw_pdfs   = tmp_path / "raw_pdfs";       raw_pdfs.mkdir()
    structured = tmp_path / "structured_json"; structured.mkdir()
    manifests  = tmp_path / "manifests";       manifests.mkdir()

    _make_pdf(raw_pdfs,   "bsee-incident")
    _make_json(structured, "bsee-incident")   # already extracted

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
    )
    assert call_count["n"] == 0, "Provider should not be called for ready entries"


def test_run_corpus_extraction_error_logged(tmp_path, caplog):
    """Extraction errors are logged and do not abort the loop."""
    import logging
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
            text_search_dirs=[],   # nowhere to find text
            provider=StubProvider(),
        )

    assert any("missing-text-file" in r.message for r in caplog.records)
    # Output dir should be empty — error did not crash the loop
    assert list(structured.glob("*.json")) == []
```

**Step 3.3 — Run tests to confirm failure**

```bash
python -m pytest tests/test_corpus_extract.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.corpus.extract'`

---

**Step 3.4 — Implement `src/corpus/extract.py`**

```python
"""corpus_v1 Claude extraction for needs_extraction entries.

Reads corpus_v1_manifest.csv, skips entries with extraction_status=ready,
loads incident text, calls the provider, writes JSON to structured_json/.
"""
import csv
import json
import logging
import pathlib
from typing import Sequence

from src.ingestion.structured import _parse_llm_json
from src.llm.base import LLMProvider
from src.prompts.loader import load_prompt

logger = logging.getLogger(__name__)

# Default text search dirs (checked in order)
_DEFAULT_TEXT_DIRS: list[pathlib.Path] = [
    pathlib.Path("data/raw/csb/text"),
    pathlib.Path("data/raw/bsee/text"),
]


def _load_incident_text(
    incident_id: str,
    text_search_dirs: Sequence[pathlib.Path],
) -> str:
    """Return text content for incident_id, searching dirs in order.

    Raises:
        FileNotFoundError: if no .txt file is found in any search dir.
    """
    for d in text_search_dirs:
        candidate = d / f"{incident_id}.txt"
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"No text file found for '{incident_id}' in: {list(text_search_dirs)}"
    )


def run_corpus_extraction(
    manifest_path: pathlib.Path,
    structured_dir: pathlib.Path,
    text_search_dirs: Sequence[pathlib.Path] | None,
    provider: LLMProvider,
) -> int:
    """Extract JSONs for all needs_extraction rows in the manifest.

    Args:
        manifest_path: Path to corpus_v1_manifest.csv.
        structured_dir: Where to write output JSON files.
        text_search_dirs: Ordered list of dirs to search for .txt files.
                          Defaults to CSB then BSEE text dirs.
        provider: LLM provider to call.

    Returns:
        Number of incidents successfully extracted.
    """
    if text_search_dirs is None:
        text_search_dirs = _DEFAULT_TEXT_DIRS

    structured_dir.mkdir(parents=True, exist_ok=True)

    with manifest_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    pending = [r for r in rows if r["extraction_status"] == "needs_extraction"]
    logger.info(f"corpus-extract: {len(pending)} entries to process.")

    extracted = 0
    for row in pending:
        incident_id = row["incident_id"]
        out_path    = structured_dir / f"{incident_id}.json"

        if out_path.exists():
            logger.info(f"  {incident_id}: already present, skipping.")
            continue

        try:
            text   = _load_incident_text(incident_id, text_search_dirs)
            prompt = load_prompt(incident_text=text)
            raw    = provider.extract(prompt)
            data   = _parse_llm_json(raw)
        except Exception as exc:
            logger.error(f"  {incident_id}: extraction failed — {exc}")
            continue

        out_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"  {incident_id}: extracted OK → {out_path.name}")
        extracted += 1

    logger.info(f"corpus-extract: done. {extracted}/{len(pending)} extracted.")
    return extracted
```

**Step 3.5 — Run tests to confirm they pass**

```bash
python -m pytest tests/test_corpus_extract.py -v
```

Expected: 4 passed.

---

**Step 3.6 — Add `corpus-extract` subcommand to `src/pipeline.py`**

Add import at top:

```python
from src.corpus.extract import run_corpus_extraction, _DEFAULT_TEXT_DIRS
from src.llm.registry import get_provider
```

Check `src/llm/registry.py` first:

```bash
grep -n "def get_provider\|def build_provider" src/llm/registry.py | head -5
```

Use whichever function instantiates `AnthropicProvider` from CLI args. If no registry function fits, construct directly:

```python
from src.llm.anthropic_provider import AnthropicProvider
```

Add `cmd_` function before `main()`:

```python
def cmd_corpus_extract(args: argparse.Namespace) -> None:
    """Extract missing CSB JSONs for corpus_v1 using Claude (Anthropic)."""
    from src.llm.anthropic_provider import AnthropicProvider
    from src.corpus.extract import run_corpus_extraction, _DEFAULT_TEXT_DIRS

    corpus_root   = Path("data/corpus_v1")
    manifest_path = corpus_root / "manifests" / "corpus_v1_manifest.csv"
    structured    = corpus_root / "structured_json"

    if not manifest_path.exists():
        logger.error(f"Manifest not found: {manifest_path}  Run corpus-manifest first.")
        return

    provider = AnthropicProvider(model=args.model)
    run_corpus_extraction(
        manifest_path=manifest_path,
        structured_dir=structured,
        text_search_dirs=None,   # uses _DEFAULT_TEXT_DIRS
        provider=provider,
    )
    logger.info("Run corpus-manifest to refresh extraction_status.")
```

Add subparser in `main()`:

```python
    p_ce = subparsers.add_parser(
        "corpus-extract",
        help="Extract missing corpus_v1 JSONs using Claude (requires ANTHROPIC_API_KEY)",
    )
    p_ce.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Anthropic model ID (default: claude-sonnet-4-6)",
    )
    p_ce.set_defaults(func=cmd_corpus_extract)
```

---

**Step 3.7 — Run full test suite (all tests must still pass)**

```bash
python -m pytest -q --tb=short
```

Expected: ≥319 passed, 0 failures.

---

**Step 3.8 — Commit before running live extraction**

```bash
git add src/corpus/extract.py tests/test_corpus_extract.py src/pipeline.py
git commit -m "feat: add corpus-extract subcommand for 48 CSB PDFs (Task 3)"
```

---

**Step 3.9 — Run live extraction (requires `ANTHROPIC_API_KEY`)**

```bash
# Verify key is set
echo $ANTHROPIC_API_KEY | head -c 8   # should print first 8 chars

# Dry-check: how many entries are pending
python -c "
import csv
rows = list(csv.DictReader(open('data/corpus_v1/manifests/corpus_v1_manifest.csv')))
pending = [r for r in rows if r['extraction_status'] == 'needs_extraction']
print(f'{len(pending)} entries pending')
"
# Expected: 48 entries pending

python -m src.pipeline corpus-extract
```

Expected: ~48 log lines like `csb-explosion: extracted OK → csb-explosion.json`. May take 5–10 minutes at ~10–15s per call.

---

**Step 3.10 — Run schema convert-schema pass (V2.3 normalisation)**

```bash
python -m src.pipeline convert-schema \
  --incident-dir data/corpus_v1/structured_json \
  --out-dir      data/corpus_v1/structured_json
```

This rewrites all 48 new JSONs in-place with V2.3 field normalisations (`side`, `barrier_status`, `line_of_defense`, etc.). The 100 BSEE JSONs are also re-processed but are idempotent.

Expected log: `Converted 148 files -> data/corpus_v1/structured_json` + coercion summary.

---

**Step 3.11 — Refresh manifest**

```bash
python -m src.pipeline corpus-manifest
```

Expected: `148 ready, 0 needs_extraction`

---

**Step 3.12 — Verify corpus completeness**

```bash
python3 -c "
import csv
rows = list(csv.DictReader(open('data/corpus_v1/manifests/corpus_v1_manifest.csv')))
by_status = {}
for r in rows:
    by_status.setdefault(r['extraction_status'], []).append(r['incident_id'])
for k, v in by_status.items():
    print(f'{k}: {len(v)}')
by_agency = {}
for r in rows:
    by_agency.setdefault(r['source_agency'], 0)
    by_agency[r['source_agency']] += 1
for k, v in by_agency.items():
    print(f'  {k}: {v}')
"
```

Expected:
```
ready: 148
  BSEE: 100
  CSB: 48
```

---

**Step 3.13 — Final test suite run**

```bash
python -m pytest -q --tb=short
```

Expected: ≥319 passed, 0 failures.

---

**Step 3.14 — Commit and close**

```bash
git add data/corpus_v1/manifests/corpus_v1_manifest.csv
git commit -m "feat: corpus_v1 complete — 148 PDFs, 148 JSONs, manifest ready"
```

---

## Summary

| Step | Command | Expected outcome |
|------|---------|-----------------|
| Task 1 | `python -m src.pipeline corpus-manifest` | 100 ready, 48 needs_extraction |
| Task 2 | `python -m src.pipeline corpus-clean` | 66 noise JSONs quarantined |
| Task 2b | `python -m src.pipeline corpus-manifest` | confirms 100 ready, 48 pending |
| Task 3 | `python -m src.pipeline corpus-extract` | 48 CSB JSONs extracted |
| Task 3b | `python -m src.pipeline convert-schema ...` | V2.3 normalisation in-place |
| Task 3c | `python -m src.pipeline corpus-manifest` | 148 ready, 0 pending |
