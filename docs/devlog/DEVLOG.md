# Dev Log

## 2026-02-18 — corpus_v1 extraction finalized + main merge hardening

### Implemented
- Finalized corpus_v1: 148 public incident PDFs (CSB+BSEE) with 147 Schema v2.3 canonical structured JSON outputs; macondo remains a permanent skip due to blank/scanned text.
- Stabilized and reduced extraction cost via cheap default protocol (Haiku primary, `--text-limit 50000`, retry + escalation to 16000 only when needed; Sonnet fallback reserved), plus blank-text guard, throttling, and higher timeout.
- Enforced normalize-to-v2.3 before write, and verified convert-schema is idempotent across corpus_v1.
- Removed schema naming drift (`IncidentV2_2` → `IncidentV23`) while keeping compatibility aliases.

### Why
- Needed a reproducible, canonical evaluation corpus and a stable extraction pipeline that avoids silent failures, schema drift, and unnecessary spend.

### Learned
- Token limits and rate limits are the dominant batch failure modes; deterministic guards and escalation paths make extraction predictable.
- Normalizing to the canonical schema at write-time prevents recurring conversion debt.
- Merge-time import resolution can reveal hidden local WIP; missing types must be committed to keep main reliable.

### Went wrong + fix
- During merge, `source_ingest.py` imported `SourceManifestRow` that only existed in a local stash (uncommitted WIP). Recovered stash and committed `SourceManifestRow` to main to resolve the import cleanly.

### Validated
- pytest green (327/327); corpus-manifest shows 147 ready / 1 permanent skip (macondo); corpus-clean `--dry-run` shows 0 moves; origin/main pushed.

---

## 2026-02-18 — Schema V2.3 Canonicalisation + Identifier Rename

Hardened the pipeline so all stored JSON is always canonical Schema v2.3.

### Normalise-before-write (corpus-extract)
- `src/ingestion/normalize.py` (new): `normalize_v23_payload()` extracted from
  `pipeline.py` into its own importable module; also fixes `performance: null`
  controls (previously silently skipped).
- `corpus/extract.py` now calls `normalize_v23_payload()` + `validate_incident_v23()`
  after every LLM extraction, before writing to disk. Validation failure logs a
  WARNING but does not discard the file.
- `convert-schema` remains available for backfills of older corpora.

### Corpus backfill
- `data/corpus_v1/structured_json/` (147 files): 1 file fixed (bp-husky C-016
  had `performance: null`; normalised to `barrier_status: "unknown"`).
- `data/structured/incidents/anthropic/` (166 files): 3 files fixed (side field
  was missing/unknown, defaulted to `"prevention"`).
- All other provider buckets (gemini, openai, schema_v2_3, stub): already canonical.

### Identifier rename (pure mechanical, no behaviour change)
The Python schema is **v2.3**. Legacy `v2_2` identifiers were renamed:

| Old name | New name | Location |
|---|---|---|
| `IncidentV2_2` | `IncidentV23` | `src/models/incident_v23.py` |
| `validate_incident_v2_2` | `validate_incident_v23` | `src/validation/incident_validator.py` |

**Backwards-compat aliases kept for one release cycle:**
```python
# src/models/incident_v23.py
IncidentV2_2 = IncidentV23

# src/validation/incident_validator.py
validate_incident_v2_2 = validate_incident_v23
```
The asset file `assets/schema/incident_v2_2_template.json` is intentionally
unchanged (filename is not a Python identifier).

**327 tests passing.**

---

## 2026-02-18 — corpus_v1 Complete

Built and extracted the `corpus_v1` evaluation corpus:

- **148 PDFs** in `data/corpus_v1/raw_pdfs/` (100 BSEE + 48 CSB)
- **147 Claude JSONs** in `data/corpus_v1/structured_json/` (V2.2 schema via `extract_incident.md` prompt)
- **1 permanent skip**: `macondo-blowout-and-explosion` — scanned image PDF, pdfplumber extracts nothing
- **66 noise JSONs** quarantined to `structured_json_noise/` (Status_Change_Summary, sample stubs, etc.)
- **Manifest**: `data/corpus_v1/manifests/corpus_v1_manifest.csv` — 147 ready, 1 needs_extraction

**Cheaper extraction protocol implemented** (`corpus-extract` v2):
- Primary: `claude-haiku-4-5-20251001` (8192 output tokens) — ~5× cheaper than Sonnet
- Escalation: same model, 16000 output tokens — triggered for complex JSON responses
- Fallback: `claude-sonnet-4-6` (16000 tokens) — never needed; Haiku handled all 19 PDFs
- Input truncation: 50k char default (~12.5k tokens) — applied to 15/20 large PDFs
- Dynamic rate-limit delay based on truncated text size; 30s floor
- Retry up to 3× within primary before escalating
- Run 4 cost estimate: ~$0.45 for 19 PDFs (28 minutes total)

**New CLI commands**: `corpus-manifest`, `corpus-clean`, `corpus-extract --model --fallback-model --delay --text-limit`

**325 tests passing.**

## 2026-02-01 - Initial Setup
Set up the project structure with `src/`, `tests/`, and `data/` directories.
Added Pydantic models for incident data and basic tests.
Configured gitignore to exclude local env files.

## 2026-02-02 - Proposal Updates
Updated the proposal based on feedback:
- Narrowed MVP scope to "Loss of Containment" scenarios only.
- Will focus on Logistic Regression vs XGBoost for the model comparison.
- Added SHAP/reason codes for explainability.
- Target dataset size: ~200 labeled examples.

## Next Steps
- Implement JSON schema validation for Bowtie data.
- Build the initial data ingestion pipeline.

## 2026-02-04 - Phase 1 & 2 Implementation
Implemented core data foundation and analytics engine:
- **Schema**: Defined Pydantic models for `Incident`, `Threat`, `Barrier`, `Consequence`, and `Bowtie`.
- **Ingestion**: Created a text loader to parse raw incident narratives and extract barrier information.
- **Analytics**: Implemented logic to calculate barrier coverage (prevention/mitigation) and identify gaps against a reference Bowtie.
- **Pipeline**: Built an end-to-end processing script (`src/pipeline.py`) that orchestrates ingestion and analytics.
- **Verification**: Validated the pipeline with sample data and a "Loss of Containment" Bowtie definition.

## 2026-02-04 - Streamlit MVP & App Hardening
Implemented Streamlit MVP and stabilized end-to-end demo flow:
- Added app data-loading utilities and tests to reliably read pipeline outputs.
- Built Streamlit dashboard KPIs and an Incident Explorer for per-incident barrier coverage and gap details.
- Hardened the UI against missing optional fields in incident JSON (safe defaults, no KeyErrors).
- Updated .gitignore to prevent committing local planning artifacts.

Verification:
- Unit tests pass (`pytest`)
- Pipeline runs successfully (`python -m src.pipeline`)
- Streamlit renders dashboard and incident explorer (`streamlit run src/app/main.py`)

## 2026-02-05 — Step 1.2.2: Initial Data Acquisition (CSB/BSEE)

Implemented a manifest-driven acquisition workflow for public incident reports:
- Added incident/text manifest models with CSV load/save utilities.
- Implemented CSB and BSEE discovery + PDF download with streaming and SHA256 hashing.
- Added PDF-to-text extraction using pdfplumber and a text manifest for extraction results.
- Extended the pipeline CLI with `acquire` and `extract-text` subcommands while preserving the original `process` behavior.
- Added unit tests for manifests, sources, PDF extraction, and CLI parsing.

Validation:
- `pytest -q` passes.
- CLI smoke tests: `python -m src.pipeline --help`, `python -m src.pipeline acquire --help`, acquisition + download + extract-text run end-to-end.

## 2026-02-07 — Multi-provider LLM Extraction Pipeline

Implemented a provider registry and HTTP-based LLM providers for structured incident extraction.

### Environment Variables

| Variable | Provider | Required when |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI (gpt-4o, etc.) | `--provider openai` |
| `ANTHROPIC_API_KEY` | Anthropic (Claude) | `--provider anthropic` |
| `GEMINI_API_KEY` | Google Gemini | `--provider gemini` |
| *(none)* | Stub (testing) | `--provider stub` (default) |

### Bakeoff Commands (3 incidents)

```bash
# Stub (no key needed — for testing)
python -m src.pipeline extract-structured --provider stub --limit 3

# OpenAI
export OPENAI_API_KEY="<YOUR_KEY>"
python -m src.pipeline extract-structured --provider openai --model gpt-4o --limit 3

# Anthropic
export ANTHROPIC_API_KEY="<YOUR_KEY>"
python -m src.pipeline extract-structured --provider anthropic --model claude-sonnet-4-5-20250929 --limit 3

# Gemini
export GEMINI_API_KEY="<YOUR_KEY>"
python -m src.pipeline extract-structured --provider gemini --model gemini-2.0-flash --limit 3
```

### Output Locations

| Artifact | Path |
|---|---|
| Structured JSON | `data/structured/incidents/schema_v2_3/<incident_id>.json` |
| Raw LLM response | `data/structured/raw/<provider>/<incident_id>.txt` |
| Extraction manifest | `data/structured/structured_manifest.csv` |

Use `--resume` to skip already-extracted incidents on re-runs. The manifest is upserted by `incident_id`, so prior rows are preserved across runs.

## 2026-02-09 — Schema v2.3 Normalization (`convert-schema`)

Added a `convert-schema` pipeline subcommand that applies in-memory coercions to LLM extraction outputs before writing normalized Schema v2.3 JSON.

### Coercions applied
- `event.incident_type`: list→str, empty→"unknown"
- `bowtie.controls[].side`: left→prevention, right→mitigation
- `bowtie.controls[].line_of_defense`: int→enum string (1→"1st", etc.)
- `bowtie.controls[].performance.barrier_status`: synonym mapping (worked→active, etc.)
- `bowtie.controls[].human.human_contribution_value`: non-str→str
- Generic `id` keys remapped to `hazard_id`/`threat_id`/`consequence_id`

### Verification
- `schema-check`: 166/166 valid
- `quality-gate`: 98.8% controls, 90.4% PIFs
- `pytest`: 180 passed
- `verify_and_bundle_schema_v2_3.sh`: produces deliverable zip with README, inventory, file list

## 2026-02-18 — PHMSA + TSB Ingestion + Combined Exports

Extended ingestion to two new sources and added cross-source aggregation exports.

### Implemented
- **PHMSA skeleton** (`src/ingestion/sources/phmsa_ingest.py`): header inspection of bulk CSV,
  graceful no-op with WARNING on unrecognised columns; wired as `ingest-phmsa` CLI subcommand.
- **TSB Canada discovery** (`src/ingestion/sources/tsb_discover.py`): scrapes pipeline listing page,
  deterministic `doc_id` via regex `/(p\d{2}[a-z]\d{4})/`; HTML narrative extraction with
  BeautifulSoup `<main>` → body fallback; `discover-source --source tsb` CLI wiring.
- **TSB ingest** (`src/ingestion/sources/tsb_ingest.py`): resumable manifest-driven HTML download,
  always stores raw HTML for audit, lazy session init.
- **Combined exports** (`src/analytics/build_combined_exports.py`):
  `flat_incidents_combined.csv` (one row per incident) and `controls_combined.csv` (one row per
  control) across all sources; `build-combined-exports` CLI subcommand.
- **Four-tier `source_agency` resolution**: explicit JSON field → `doc_type`/`document_type`
  keyword inference → URL domain → path segment → `UNKNOWN`.
- **`provider_bucket` column**: preserves immediate parent directory (anthropic/gemini/openai/etc.)
  as a separate column alongside `source_agency`.

### Why
- Extends data coverage beyond CSB/BSEE to PHMSA (pipeline) and TSB Canada (pipeline) incidents.
- Combined exports enable cross-source fleet analytics without manual merging or re-running
  per-provider flatten passes.
- `source_agency` inference from `doc_type` was required because LLM-extracted JSONs store source
  identity in `doc_type`, not `agency`; `source.agency` is absent from all 514 real files.

### Learned
- `doc_type` is the reliable source-identity field in current extractions. Key discriminators:
  `"accident investigation"` → BSEE; `"recommendation status change"` → CSB; `"csb"` prefix → CSB.
- Provider bucket subdirs (anthropic/gemini/openai/schema_v2_3) must never be promoted to
  `source_agency`; path-segment fallback is limited to the canonical set {csb, bsee, tsb, phmsa}.
- BeautifulSoup4 was missing from `requirements.txt` — added (`beautifulsoup4>=4.12.0`).
- TSB mock tests must patch `src.ingestion.sources.tsb_ingest.requests.Session` (full module path).

### Validated
- 306 tests passing, no regressions.
- `build-combined-exports` on 517 incidents: BSEE=324 (62.7%), CSB=101 (19.5%), UNKNOWN=92 (17.8%).
- UNKNOWN rows are genuine stubs/test files with generic `doc_type` values; no false positives.
- PR merged to main.

## 2026-02-17 — LOC_v1 Definition Freeze

Froze the Loss of Containment scoring definition as LOC_v1, documented in `docs/loc_definition_v1.md`.

### Implemented
- Formal definition of the three keyword tiers (primary, secondary, hazardous context) with exact term lists.
- Extraction gate: documents with `extraction_status != "OK"` are labelled `EXTRACTION_FAILED`, never scored as `LOC=False`.
- Frozen flag rule: `(primary >= 1 AND hazardous >= 1) OR (secondary >= 1 AND hazardous >= 2)`.
- `loc_score` documented as audit-only, not authoritative for classification.

### Why
- Downstream analytics and labeling need a stable, versioned LOC definition.
- Prevents silent false negatives from failed text extractions.
- Cosine similarity was evaluated but dropped for MVP due to low recall on this corpus.

### Learned
- Extraction-awareness is critical: without the gate, failed PDFs silently produce `LOC=False` labels that contaminate downstream metrics.
- Keyword tiers with hazardous-context gating provide good precision for the MVP scope.

### Validated
- Flag rule matches the implementation in `src/nlp/loc_scoring.py:81`.
- All 254 existing tests continue to pass.
- ADR-004 recorded in `docs/decisions/2026-02-17-freeze-loc-v1.md`.

> **Note:** Pipeline commands are run via `python -m src.pipeline <command>` in this environment because console entrypoints (e.g., `corpus-manifest`) are not installed into the venv. Source manifest typing lives in `src/ingestion/manifests.py` (`SourceManifestRow`).
