# Dev Log

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
