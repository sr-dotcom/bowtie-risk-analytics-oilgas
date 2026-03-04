# Codebase Structure

**Analysis Date:** 2026-02-27

## Directory Layout

```
bowtie-risk-analytics-oilgas/
├── src/                           # Core application code (Python package)
│   ├── pipeline.py                # CLI entry point: 10+ subcommands
│   ├── ingestion/                 # Incident discovery, download, text extraction
│   │   ├── sources/               # Source-specific adapters (CSB, BSEE, PHMSA, TSB)
│   │   ├── loader.py              # Parse raw text → Incident model
│   │   ├── manifests.py           # Manifest models + CSV I/O
│   │   ├── pdf_text.py            # PDF → text via pdfplumber
│   │   ├── structured.py          # LLM structured extraction orchestrator
│   │   └── normalize.py           # V2.2 → V2.3 schema conversion
│   ├── extraction/                # Multi-pass PDF extraction + quality gate
│   │   ├── extractor.py           # Fallback chain (PyMuPDF → pdfminer → OCR)
│   │   ├── quality_gate.py        # Text quality evaluation
│   │   ├── runner.py              # Extract + QC orchestrator
│   │   ├── manifest.py            # Extraction manifest model
│   │   └── normalize.py           # Text post-processing
│   ├── models/                    # Pydantic v2 data models
│   │   ├── incident.py            # Legacy Incident model
│   │   ├── incident_v23.py        # Canonical Schema v2.3 (8 top-level keys)
│   │   ├── bowtie.py              # Bowtie diagram structure
│   │   ├── incident_v2_2.py       # Schema v2.2 (legacy)
│   │   └── __init__.py
│   ├── analytics/                 # Incident analysis and metrics
│   │   ├── engine.py              # Pure: calculate_barrier_coverage, identify_gaps
│   │   ├── aggregation.py         # Fleet-level metrics (mean coverage, totals)
│   │   ├── flatten.py             # Controls → flat CSV export
│   │   ├── baseline.py            # Pandas-based summary analytics
│   │   ├── build_combined_exports.py  # Multi-source flat CSV builder
│   │   └── __init__.py
│   ├── llm/                       # LLM provider abstraction
│   │   ├── base.py                # LMProvider abstract base class
│   │   ├── anthropic_provider.py  # Anthropic Messages API HTTP impl
│   │   ├── registry.py            # Provider factory: get_provider(name)
│   │   ├── model_policy.py        # YAML-driven model ladder config
│   │   ├── stub.py                # Stub provider for testing
│   │   └── __init__.py
│   ├── validation/                # Schema validation
│   │   ├── incident_validator.py  # validate_incident_v23()
│   │   └── __init__.py
│   ├── prompts/                   # LLM prompt templates
│   │   ├── loader.py              # load_prompt() — assemble schema + text
│   │   └── __init__.py
│   ├── corpus/                    # corpus_v1 management + extraction
│   │   ├── manifest.py            # Corpus manifest: build/read/write
│   │   ├── extract.py             # Corpus extraction with model ladder
│   │   ├── clean.py               # Quarantine non-incident JSONs
│   │   └── __init__.py
│   ├── nlp/                       # NLP utilities
│   │   ├── loc_scoring.py         # Keyword-based Loss of Containment scoring
│   │   └── __init__.py
│   ├── app/                       # Streamlit dashboard
│   │   ├── main.py                # Dashboard entry point
│   │   ├── utils.py               # Data loading from data/processed/
│   │   └── __init__.py
│   ├── __init__.py
│   └── __pycache__
├── data/                          # Data directories (gitignored except samples/)
│   ├── raw/                       # Downloaded PDFs and extracted text
│   │   ├── csb/                   # CSB source
│   │   │   ├── pdfs/              # PDF files
│   │   │   └── text/              # Extracted text files
│   │   └── bsee/                  # BSEE source
│   │       ├── pdfs/              # PDF files
│   │       └── text/              # Extracted text files
│   ├── structured/                # LLM extraction outputs
│   │   ├── anthropic/             # Claude extractions (JSON)
│   │   ├── gemini/                # Gemini extractions (if used)
│   │   ├── openai/                # GPT extractions (if used)
│   │   ├── schema_v2_3/           # Final normalized JSONs
│   │   ├── misc/                  # Non-incident JSONs
│   │   └── run_reports/           # Extraction run reports
│   ├── processed/                 # Pipeline output (analytics ready)
│   │   ├── incidents/             # Incident JSON files with analytics
│   │   └── metrics.json           # Fleet-level metrics
│   ├── interim/                   # Temporary processing artifacts
│   ├── derived/                   # Derived datasets (summaries, exports)
│   ├── corpus_v1/                 # corpus_v1 dataset (147 PDFs + JSONs)
│   │   ├── raw_pdfs/              # 148 original PDFs (flat)
│   │   ├── structured_json/       # 147 Claude v2.2 JSONs
│   │   ├── structured_json_noise/ # 66 quarantined non-incident JSONs
│   │   └── manifests/             # corpus_v1_manifest.csv
│   ├── sources/                   # Source URL manifests
│   ├── manifests/                 # Pipeline manifests (CSV)
│   │   ├── incidents_manifest.csv      # Download tracking
│   │   ├── text_manifest.csv           # Text extraction tracking
│   │   └── structured_manifest.csv     # LLM extraction tracking
│   └── sample/                    # Sample files (bowtie_loc.json, etc.) — committed
├── tests/                         # Pytest suite (325+ tests)
│   ├── test_*.py                  # Test files matching test_*.py pattern
│   ├── __init__.py
│   └── __pycache__
├── configs/                       # Application configuration
│   ├── model_policy.yaml          # Claude model ladder + escalation policy
│   └── sources/                   # Source-specific configs (if needed)
├── assets/                        # Static assets
│   ├── prompts/                   # LLM prompt templates
│   │   └── extract_incident.md    # Main extraction prompt ({{SCHEMA_TEMPLATE}}, {{INCIDENT_TEXT}})
│   └── schema/                    # JSON schema templates
│       └── incident_v2_2_template.json  # Schema reference for LLM
├── docs/                          # Documentation
│   ├── devlog/                    # Development log
│   │   └── DEVLOG.md              # Progress tracking
│   ├── decisions/                 # Architecture decision records
│   │   └── ADR-index.md           # Decision index
│   ├── step-tracker/              # Project status tracking
│   │   └── STATUS.md              # Current status checkpoint
│   └── [other docs]
├── scripts/                       # Utility scripts
├── .planning/                     # GSD planning output (generated)
│   └── codebase/                  # Codebase analysis documents
│       ├── ARCHITECTURE.md        # Architecture analysis
│       └── STRUCTURE.md           # Directory structure & conventions
├── requirements.txt               # Python dependencies (pinned)
├── pyproject.toml                 # Project metadata + build config
├── CLAUDE.md                      # Project instructions for Claude
├── README.md                      # Project overview
├── CONTRIBUTING.md                # Contribution guidelines
├── .env.example                   # Environment variable template
└── .gitignore                     # Version control exclusions
```

## Directory Purposes

**src/**
- Purpose: Core application code (single package root)
- Contains: All Python modules organized by function (ingestion, analytics, llm, etc.)
- Key files: `pipeline.py` is CLI entry point

**src/ingestion/**
- Purpose: Incident discovery, download, and text extraction
- Contains: Source adapters, PDF downloading, text extraction, manifest tracking
- Key files: `sources/`, `manifests.py`, `pdf_text.py`, `structured.py`

**src/extraction/**
- Purpose: Multi-pass PDF extraction with quality gating
- Contains: Fallback extraction chain, quality evaluation, normalization
- Key files: `extractor.py` (fallback logic), `runner.py` (orchestrator)

**src/models/**
- Purpose: Pydantic v2 data models for validation and serialization
- Contains: Incident models (V2.2, V2.3, legacy), Bowtie, manifest models
- Key files: `incident_v23.py` (canonical Schema v2.3)

**src/analytics/**
- Purpose: Incident analysis, metric computation, CSV export
- Contains: Barrier coverage calculation, aggregation, flattening
- Key files: `engine.py` (pure functions), `flatten.py`, `build_combined_exports.py`

**src/llm/**
- Purpose: Abstract LLM provider interface and implementations
- Contains: Provider ABC, Anthropic HTTP impl, registry, model policy
- Key files: `base.py` (ABC), `anthropic_provider.py`, `registry.py`

**src/validation/**
- Purpose: Schema validation utilities
- Contains: Pydantic-based validation for V2.3 incidents
- Key files: `incident_validator.py`

**src/prompts/**
- Purpose: LLM prompt template management
- Contains: Prompt assembly with schema and incident text substitution
- Key files: `loader.py` (load_prompt function)

**src/corpus/**
- Purpose: corpus_v1 dataset management and LLM extraction
- Contains: Manifest building, extraction with model ladder, noise quarantine
- Key files: `extract.py` (model ladder), `manifest.py`, `clean.py`

**src/nlp/**
- Purpose: NLP utilities for incident analysis
- Contains: Keyword-based Loss of Containment scoring
- Key files: `loc_scoring.py`

**src/app/**
- Purpose: Streamlit web dashboard
- Contains: Dashboard page, data loading utilities
- Key files: `main.py` (entry point), `utils.py` (load_data function)

**data/raw/**, **data/structured/**, **data/processed//**
- Purpose: Data at different pipeline stages (gitignored except data/sample/)
- raw/: Downloaded PDFs and extracted text
- structured/: LLM extraction outputs (provider-bucketed: anthropic/, gemini/, openai/)
- processed/: Analytics-ready JSON and metrics

**data/corpus_v1/**
- Purpose: corpus_v1 dataset (147 PDFs + extractions)
- Contains: raw_pdfs/ (flat), structured_json/ (v2.2 JSONs), manifests/
- Used for: Large-scale testing and baseline comparison

**tests/**
- Purpose: Pytest test suite (325+ tests)
- Contains: test_*.py files matching test discovery pattern
- Pattern: One test file per module (e.g., test_engine.py, test_anthropic_provider.py)

**configs/**
- Purpose: Application configuration files
- Contains: YAML model policy for LLM ladder selection
- Key files: `model_policy.yaml` (default_model, fallback_models, escalation policy)

**assets/**
- Purpose: Static assets (prompts, schemas)
- Contains: LLM prompt templates and JSON schema references
- Key files: `prompts/extract_incident.md`, `schema/incident_v2_2_template.json`

**docs/**
- Purpose: Project documentation and decision records
- Contains: Development log, architecture decision records, status tracking
- Key files: `devlog/DEVLOG.md`, `decisions/ADR-index.md`, `step-tracker/STATUS.md`

## Key File Locations

**Entry Points:**
- `src/pipeline.py` — CLI orchestrator (python -m src.pipeline)
- `src/app/main.py` — Streamlit dashboard (streamlit run src/app/main.py)

**Configuration:**
- `configs/model_policy.yaml` — LLM model ladder and escalation triggers
- `.env` — Runtime environment variables (ANTHROPIC_API_KEY, etc.)
- `requirements.txt` — Python dependencies

**Core Logic:**
- `src/ingestion/structured.py` — LLM extraction orchestrator
- `src/extraction/extractor.py` — Multi-pass PDF extraction
- `src/analytics/engine.py` — Barrier coverage calculation
- `src/ingestion/manifests.py` — Manifest models and CSV I/O
- `src/llm/registry.py` — Provider factory and selection

**Testing:**
- `tests/` — All test files (pytest discovers test_*.py pattern)
- `tests/test_extract_structured.py` — Structured extraction tests
- `tests/test_corpus_extract.py` — Corpus extraction tests
- `tests/test_incident_validator.py` — Schema validation tests

**Data Models:**
- `src/models/incident_v23.py` — Canonical Schema v2.3 (8 top-level keys)
- `src/models/bowtie.py` — Bowtie structure
- `src/ingestion/manifests.py` — Manifest models (IncidentManifestRow, TextManifestRow, etc.)

## Naming Conventions

**Files:**
- Module files: `lowercase_with_underscores.py` (e.g., `incident_validator.py`, `pdf_text.py`)
- Test files: `test_*.py` matching module name (e.g., `test_incident_validator.py`)
- Package dirs: `lowercase` (e.g., `src/ingestion/`, `src/extraction/`)
- Config files: `snake_case.yaml` (e.g., `model_policy.yaml`)

**Functions:**
- Private helpers: `_leading_underscore` (e.g., `_parse_llm_json`, `_manifest_key`)
- Public functions: `lowercase_with_underscores` (e.g., `calculate_barrier_coverage`, `load_prompt`)

**Variables:**
- Constants: `UPPERCASE_WITH_UNDERSCORES` (e.g., `_DEFAULT_MODEL`, `_RETRYABLE_STATUS_CODES`)
- Class attributes: `lowercase_with_underscores`
- Local variables: `lowercase_with_underscores`

**Types:**
- Pydantic models: `PascalCase` (e.g., `Incident`, `IncidentV23`, `StructuredManifestRow`)
- Enums: `PascalCase` or `Literal` types (e.g., `side: Literal["left", "right"]`)
- Type hints: Full type hints required on all functions (enforced)

**Directories:**
- By function: `src/analytics/`, `src/ingestion/`, `src/extraction/` (lowercase)
- By source: `data/raw/csb/`, `data/raw/bsee/` (source agency names)
- Provider buckets: `data/structured/anthropic/`, `data/structured/gemini/` (provider names)

## Where to Add New Code

**New Feature (e.g., new source adapter):**
- Primary code: `src/ingestion/sources/{source_name}.py` for discovery/download logic
- Registration: Add to `_DISCOVER_ADAPTERS` in `src/pipeline.py`
- Tests: `tests/test_sources_{source_name}.py`
- Config update: Add rules to `_DOC_TYPE_RULES` in `src/analytics/build_combined_exports.py` if needed

**New Module/Package:**
- Implementation: Create under `src/{domain}/` following existing layer pattern
- Module files: `src/{domain}/{module_name}.py`
- Tests: `tests/test_{domain}_{module_name}.py` or `tests/test_{module_name}.py`
- Imports: Follow existing pattern (explicit imports from src.*, no relative imports)

**New Analytics Function:**
- Location: Add to `src/analytics/engine.py` if pure calculation, or `src/analytics/{purpose}.py` for domain-specific logic
- Signature: Full type hints required (`def func(arg: Type) -> ReturnType:`)
- Tests: `tests/test_analytics.py` or `tests/test_{purpose}.py`
- Export: Add to module if public, or keep private with `_leading_underscore`

**Utilities/Helpers:**
- Shared helpers: `src/nlp/`, `src/validation/` for cross-module utilities
- Inline helpers: Use `_helper()` prefix for module-private functions
- Tests: Create focused test file if non-trivial (e.g., `tests/test_loc_scoring.py`)

**New Command/CLI Subcommand:**
- Location: `src/pipeline.py` — add function + argparse subcommand
- Pattern: `def cmd_{name}(args) -> None` dispatches to layer-specific orchestrators
- Help text: Required in argparse definition
- Tests: `tests/test_pipeline_cli.py` if testing CLI parsing/dispatch

**New Pydantic Model:**
- Location: `src/models/` — add to appropriate file or create `{domain}.py`
- Pattern: Inherit from BaseModel, use `ConfigDict(strict=False)` for flexible parsing
- Validation: Use `@field_validator` or `@model_validator` for custom logic
- Tests: `tests/test_models.py` or domain-specific test file

## Special Directories

**data/structured/**
- Purpose: LLM extraction outputs organized by provider bucket
- Generated: Yes (written by `extract_structured`, corpus extraction)
- Committed: No (.gitignored)
- Structure: `{provider}/{incident_id}.json` (provider = anthropic, gemini, openai, schema_v2_3)
- Note: Provider-bucketed to allow multi-provider testing; schema_v2_3/ is final normalized output

**data/processed/**
- Purpose: Pipeline output ready for analytics/dashboard
- Generated: Yes (written by process subcommand)
- Committed: No (.gitignored)
- Structure: `incidents/{incident_id}.json`, `metrics.json`
- Used by: `src/app/main.py` for dashboard data loading

**data/sample/**
- Purpose: Sample files for testing (committed to repo)
- Generated: No (hand-curated)
- Committed: Yes
- Files: `bowtie_loc.json` (sample Bowtie), other fixtures
- Used by: Tests for hardcoded reference data

**data/corpus_v1/**
- Purpose: corpus_v1 dataset (147 PDFs + extractions)
- Generated: No (pre-built external dataset)
- Committed: No (data/.gitignore excludes it; available via download)
- Used for: Large-scale testing, baseline comparisons
- Key: `manifests/corpus_v1_manifest.csv` — tracks ready/needs_extraction state

**.planning/codebase/**
- Purpose: GSD codebase analysis output
- Generated: Yes (written by /gsd:map-codebase)
- Committed: No (.gitignore)
- Contents: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, STACK.md, INTEGRATIONS.md, CONCERNS.md (as applicable)

---

*Structure analysis: 2026-02-27*
