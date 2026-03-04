# Architecture

**Analysis Date:** 2026-02-27

## Pattern Overview

**Overall:** Layered pipeline with CLI orchestration

**Key Characteristics:**
- Multi-stage ingestion and processing pipeline (discover → download → extract → structure → validate → analytics)
- Pluggable LLM provider abstraction with fallback chains
- Pydantic v2 models for strict schema validation
- Manifest-based resumability across all pipeline stages
- Data-driven policy configuration for model selection
- Pure function analytics engine with separation of concerns

## Layers

**Ingestion Layer:**
- Purpose: Discover, download, and extract raw incident data from multiple sources
- Location: `src/ingestion/`
- Contains: Source adapters (CSB, BSEE, PHMSA, TSB), PDF download logic, manifest tracking
- Depends on: HTTP client (requests), manifest models, PDF text extractors
- Used by: Pipeline CLI orchestrator
- Key modules:
  - `src/ingestion/sources/` — source-specific discovery and download adapters
  - `src/ingestion/pdf_text.py` — PDF → text extraction via pdfplumber
  - `src/ingestion/manifests.py` — manifest models for tracking state across all stages

**Text Extraction Layer:**
- Purpose: Multi-pass PDF text extraction with fallback chain and quality gating
- Location: `src/extraction/`
- Contains: PyMuPDF → pdfminer → OCR fallback chain, quality gate evaluation, text normalization
- Depends on: PDF libraries (fitz, pdfminer, pytesseract), manifest tracking
- Used by: Pipeline CLI, corpus extraction pipeline
- Key modules:
  - `src/extraction/extractor.py` — fallback extraction chain with error handling
  - `src/extraction/quality_gate.py` — text quality evaluation (alpha ratio, CID detection)
  - `src/extraction/runner.py` — orchestrates full extraction-to-qc pipeline

**Structured Extraction Layer:**
- Purpose: LLM-driven extraction of incident data into Schema v2.3 JSON
- Location: `src/ingestion/structured.py`, `src/corpus/extract.py`
- Contains: LLM provider routing, prompt assembly, JSON parsing, validation, manifest tracking
- Depends on: LLM providers, prompt loader, Schema v2.3 models, validation
- Used by: Pipeline CLI, corpus extraction
- Key concepts:
  - `extract_structured()` — main entry point with provider selection
  - Model ladder in `src/corpus/extract.py` — deterministic policy-driven model escalation
  - `_parse_llm_json()` — robust JSON extraction from LLM responses (3-strategy fallback)

**LLM Provider Layer:**
- Purpose: Abstract LLM provider interface with HTTP implementation
- Location: `src/llm/`
- Contains: Provider ABC, Anthropic HTTP implementation, registry for provider lookup, model policy
- Depends on: HTTP client (requests), config loading (YAML)
- Used by: Structured extraction layer, corpus extraction
- Key modules:
  - `src/llm/base.py` — abstract LLMProvider class
  - `src/llm/anthropic_provider.py` — Anthropic Messages API with retry logic
  - `src/llm/registry.py` — provider factory with env var validation
  - `src/llm/model_policy.py` — YAML-driven model selection policy

**Schema & Validation Layer:**
- Purpose: Data model definition and validation
- Location: `src/models/`, `src/validation/`
- Contains: Pydantic v2 models (Incident, IncidentV23, Bowtie, etc.), strict validators
- Depends on: Pydantic v2, schema remapping logic
- Used by: All processing layers for data binding
- Key modules:
  - `src/models/incident_v23.py` — canonical Schema v2.3 (7 top-level keys: incident_id, source, context, event, bowtie, pifs, notes)
  - `src/models/bowtie.py` — Bowtie diagram model (threats, barriers, consequences)
  - `src/validation/incident_validator.py` — V2.3 Pydantic validation

**Analytics Layer:**
- Purpose: Incident analysis and metric computation
- Location: `src/analytics/`
- Contains: Barrier coverage calculation, gap identification, fleet aggregation, CSV flattening
- Depends on: Models, pure functions
- Used by: Pipeline CLI, dashboard data loading
- Key modules:
  - `src/analytics/engine.py` — pure functions: `calculate_barrier_coverage()`, `identify_gaps()`
  - `src/analytics/aggregation.py` — fleet-level metrics aggregation
  - `src/analytics/flatten.py` — controls → tabular CSV (used for exports)
  - `src/analytics/build_combined_exports.py` — multi-source flat export builder

**Presentation Layer:**
- Purpose: Web dashboard for incident exploration
- Location: `src/app/`
- Contains: Streamlit app, data loading utilities
- Depends on: Streamlit, analytics layer output
- Used by: End users
- Key modules:
  - `src/app/main.py` — Streamlit dashboard entry point
  - `src/app/utils.py` — data loading from `data/processed/`

**Orchestration Layer:**
- Purpose: CLI command dispatcher and pipeline sequencing
- Location: `src/pipeline.py`
- Contains: Multi-subcommand CLI (acquire, extract-text, extract-structured, process, convert-schema, build-combined-exports, etc.)
- Depends on: All layers
- Used by: End users via `python -m src.pipeline`

## Data Flow

**Incident Discovery & Acquisition:**
1. User runs `python -m src.pipeline discover-source --source csb|bsee|phmsa|tsb`
2. Source adapter (e.g., `src/ingestion/sources/csb_discover.py`) queries agency website/API
3. Incident metadata (URL, title, date) written to URL manifest
4. User runs `python -m src.pipeline ingest-source --url-file FILE` to download PDFs
5. Download logic writes to `data/raw/{source}/pdfs/`, tracks in `IncidentManifestRow`

**Text Extraction:**
1. User runs `python -m src.pipeline extract-text`
2. Reads `IncidentManifestRow` manifest
3. For each PDF: `pdf_text.py::extract_text_from_pdf()` → pdfplumber
4. Writes text to `data/raw/{source}/text/`, tracks in `TextManifestRow`

**Structured Extraction (LLM):**
1. User runs `python -m src.pipeline extract-structured` (or `corpus-extract`)
2. Loads incident text from `data/raw/{source}/text/`
3. Assembles prompt: schema template + incident text via `src/prompts/loader.py`
4. Provider selected via registry, calls `extract()` → LLM → raw response
5. `_parse_llm_json()` extracts JSON from response (markdown fences, brace extraction)
6. Parses into `IncidentV23` model with strict validation
7. Writes JSON to `data/structured/anthropic/` (provider-bucketed), tracks in `StructuredManifestRow`
8. Corpus extraction adds model ladder: haiku → claude-sonnet with policy-driven escalation on failure

**Schema Validation & Conversion:**
1. For legacy V2.2 JSONs: `python -m src.pipeline convert-schema` normalizes to V2.3
2. `src/ingestion/normalize.py::normalize_v23_payload()` applies field remappings (side, barrier_status, IDs)
3. Validates against `IncidentV23` schema

**Analytics Computation:**
1. User runs `python -m src.pipeline process` (legacy) or analytics code loads JSON directly
2. Incident objects bound to Pydantic models
3. Pure functions compute:
   - `calculate_barrier_coverage()` — prevention/mitigation/overall coverage (0.0–1.0)
   - `identify_gaps()` — barriers in reference Bowtie but missing in incident
4. Results embedded in output JSON

**Export & Flattening:**
1. User runs `python -m src.pipeline build-combined-exports`
2. Loads all V2.3 JSON files from multiple provider buckets
3. Extracts controls via `get_controls()` (single source of truth for control access)
4. Flattens to two CSVs:
   - `flat_incidents_combined.csv` — one row per incident with metadata
   - `controls_combined.csv` — one row per control with performance metrics

**Dashboard Rendering:**
1. User runs `streamlit run src/app/main.py`
2. `src/app/utils.py::load_data()` reads from `data/processed/`
3. Loads incident JSONs and metrics
4. Renders KPIs, incident explorer, barrier analysis

**State Management:**
- **Manifests (CSV-based):** Track progress across pipeline stages
  - `IncidentManifestRow` — download state
  - `TextManifestRow` — extraction state
  - `StructuredManifestRow` — LLM extraction state
  - `ConvertedManifestRow` — schema conversion state
- **Upserting:** Manifests merged by composite key (incident_id, provider) allowing resumability
- **JSON as source of truth:** V2.3 incident JSONs are canonical; re-reading applies transformations

## Key Abstractions

**LLMProvider:**
- Purpose: Abstract provider interface for swappable LLM backends
- Examples: `src/llm/base.py`, `src/llm/anthropic_provider.py`, `src/llm/stub.py`
- Pattern: ABC with single `extract(prompt: str) -> str` method; registry lookup via `get_provider(name)`
- Used by: Structured extraction orchestrator

**Manifest Models:**
- Purpose: Pydantic models tracking pipeline state (CSV-backed)
- Examples: `IncidentManifestRow`, `TextManifestRow`, `StructuredManifestRow`
- Pattern: Pydantic BaseModel with CSV serialization; merged via composite keys
- Used by: All pipeline stages for resumability

**Bowtie Diagram:**
- Purpose: Reference structure for barrier coverage analysis
- Represented by: `src/models/bowtie.py` (hazard, top_event, threats[], barriers[], consequences[])
- Used by: Analytics engine for gap identification

**Schema v2.3:**
- Purpose: Canonical incident representation
- Location: `src/models/incident_v23.py`
- Structure: 8 keys at top level: incident_id, schema_version, source, context, event, bowtie, pifs, notes
- Validation: Strict Pydantic with ConfigDict(strict=False) for flexible parsing + custom validators
- File format: UTF-8 with BOM (`encoding="utf-8-sig"`)

**Model Policy:**
- Purpose: Data-driven control of LLM model selection and escalation
- Location: `configs/model_policy.yaml`, `src/llm/model_policy.py`
- Pattern: YAML config loaded by `ModelPolicy.load()`, used by corpus extraction to implement ladder
- Controls: default_model, fallback_models[], retries_per_model, promote_on triggers

## Entry Points

**CLI Orchestrator:**
- Location: `src/pipeline.py` (entry via `python -m src.pipeline`)
- Subcommands: discover-source, ingest-source, extract-text, extract-structured, process, convert-schema, schema-check, quality-gate, build-combined-exports, corpus-manifest, corpus-clean, corpus-extract, ingest-phmsa, ingest-tsb
- Triggers: User invokes via command line with arguments
- Responsibilities: Parse args, load manifests, dispatch to layer-specific orchestrators, save outputs

**Corpus Extraction Launcher:**
- Location: `src/corpus/extract.py::run_corpus_extraction()`
- Triggers: Called by `corpus-extract` subcommand
- Responsibilities: Load policy, iterate needs_extraction entries, run model ladder, save JSONs

**Streamlit Dashboard:**
- Location: `src/app/main.py` (entry via `streamlit run src/app/main.py`)
- Triggers: User opens dashboard in browser
- Responsibilities: Load processed data, render KPIs and incident explorer

## Error Handling

**Strategy:** Graceful degradation with detailed logging and manifest tracking

**Patterns:**
- **PDF Extraction:** Fallback chain (PyMuPDF → pdfminer → OCR); if all fail, record in manifest with error reason
- **LLM Extraction:** Retry with exponential backoff (1s, 2s, 4s…) on 429/5xx; policy-driven escalation to higher-capacity models on failure types (timeout, schema_validation_failed, invalid_json)
- **JSON Parsing:** Three-strategy fallback (direct parse → strip markdown → brace extraction)
- **Validation:** Pydantic ValidationError caught, error messages flattened to manifest; skips writing invalid JSON
- **Manifest Merge:** Upserts by composite key; resumable on partial failure
- **Logging:** All layers use Python logging with INFO/WARNING/ERROR levels; tracked in manifest for audit

## Cross-Cutting Concerns

**Logging:** Python `logging` module configured at module level
- Format: `'%(asctime)s - %(levelname)s - %(message)s'`
- Levels: INFO for progress, WARNING for non-critical issues, ERROR for failures
- Usage: All modules `logger = logging.getLogger(__name__)`
- Stored in: Manifest error fields, run reports

**Validation:** Multi-stage approach
- Pydantic schema validation on model construction (ConfigDict strict=False allows flexible parsing)
- Custom validators for field coercion (e.g., materials list, operating_phase stringification)
- Post-extraction schema check via `validate_incident_v23()` in manifest tracking
- Quality gate evaluation on text extraction (alpha ratio, CID content detection)

**Authentication:** Environment variable-based
- Anthropic API key: `ANTHROPIC_API_KEY` env var
- Registry enforce-fails on missing env var with helpful error message
- No credentials in code or config files (`.env` gitignored)

**Configuration:** Multiple layers
- CLI args override defaults
- Env vars for API keys
- YAML config for model policy (`configs/model_policy.yaml`)
- Hardcoded defaults in provider implementations (e.g., `_DEFAULT_MODEL` in anthropic_provider.py)

**Resumability:** Manifest-based
- Every stage writes progress to CSV manifest
- Upsert by composite key allows safe re-runs
- Force flag bypasses "already done" checks when needed
- Safe for concurrent runs (single-threaded processing per file)

---

*Architecture analysis: 2026-02-27*
