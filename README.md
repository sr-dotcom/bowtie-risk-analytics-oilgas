# Bowtie Risk Analytics

Python pipeline and Streamlit dashboard for analyzing oil & gas incidents using the Bowtie risk methodology. Ingests public incident reports (CSB, BSEE), extracts structured risk data via LLM, and calculates barrier coverage metrics. Current scope: **Loss of Containment** scenarios.

## Quickstart

```bash
# 1. Create virtual environment
python -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run tests
pytest

# 4. Configure Anthropic API key (required for structured extraction)
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY (other keys are optional)
```

## Pipeline Commands

The pipeline is driven by `python -m src.pipeline` with these subcommands:

```bash
# Discover and download incident PDFs
python -m src.pipeline acquire --csb-limit 20 --bsee-limit 20 --download

# Extract text from downloaded PDFs
python -m src.pipeline extract-text

# Structured extraction via LLM (requires API key in .env)
python -m src.pipeline extract-structured --provider anthropic --model claude-sonnet-4-5-20250929

# Run with stub provider (no API key needed, for testing)
python -m src.pipeline extract-structured --provider stub --limit 3

# Quality gate metrics on extracted JSON
python -m src.pipeline quality-gate --incident-dir data/structured/incidents/anthropic

# Generate Schema v2.3 dataset locally (gitignored output; may be missing in a clean clone)
python -m src.pipeline convert-schema --incident-dir data/structured/incidents/anthropic --out-dir data/structured/incidents/schema_v2_3

# Legacy analytics pipeline
python -m src.pipeline process
```

Use `--help` on any subcommand for full options. Key flags:
- `--resume` — skip already-extracted files on re-runs
- `--limit N` — process at most N files
- `--provider {stub,openai,anthropic,gemini}` — LLM provider selection

## Output Directory Contract

All data artifacts are produced locally and **not committed to the repository**.
Reproduce them by running the pipeline commands above.
The `data/structured/incidents/schema_v2_3` folder is a local, gitignored output directory and may be absent in a clean clone; generate it with the convert-schema command above.

```
data/
  raw/
    incidents_manifest_v0.csv    # Acquisition manifest
    csb/                         # CSB PDFs + text/
    bsee/                        # BSEE PDFs + text/
  structured/
    incidents/<provider>/        # Validated V2.2 JSON per incident
    incidents/schema_v2_3/       # Local gitignored Schema v2.3 outputs (generate via convert-schema)
    raw/<provider>/              # Raw LLM responses
    structured_manifest.csv      # Extraction tracking manifest
    run_reports/                  # Per-run summary reports
  processed/                     # Legacy pipeline output
  derived/                       # Flattened controls CSV + baseline analytics
```

## Project Structure

```
src/
  models/          Pydantic v2 data models (Incident, Bowtie, V2.2 schema)
  ingestion/       Data acquisition, PDF text extraction, structured LLM extraction
  llm/             LLM provider abstraction (Stub, OpenAI, Anthropic, Gemini)
  prompts/         Extraction prompt templates and loader
  validation/      Pydantic-based schema validation
  analytics/       Coverage calculation, gap analysis, flattening, baseline
  app/             Streamlit dashboard
  pipeline.py      CLI entry point

assets/
  schema/          V2.2 JSON schema and template
  prompts/         Extraction prompt markdown

docs/
  decisions/       Architecture Decision Records (ADRs)
  devlog/          Development log
  step-tracker/    Phase-by-phase project status
  meetings/        Meeting notes
  handoff/         Historical planning documents

tests/             Unit tests (pytest)
scripts/           Standalone analytics CLI
```

## LLM Provider Policy

| Tier | Provider | Flag | Status |
|------|----------|------|--------|
| **Default** | Anthropic Claude Sonnet (`claude-sonnet-4-5-20250929`) | `--provider anthropic` | Recommended; used for all production extraction runs |
| Testing | Stub | `--provider stub` | No API key needed; returns fixed JSON for dev/CI |
| Optional | OpenAI | `--provider openai` | Experimental; kept for benchmarking and fallback |
| Optional | Google Gemini | `--provider gemini` | Experimental; kept for benchmarking and fallback |

The structured extraction stage is designed to run with **Anthropic only**. OpenAI and
Gemini providers are maintained for comparison benchmarks but are not required for
pipeline completion. Acquisition, text extraction, and quality gate stages do not
require any LLM API key.

## Environment Variables

| Variable | Status | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | **Required for LLM extraction** | Default provider for structured extraction |
| `OPENAI_API_KEY` | Optional | Only needed with `--provider openai` |
| `GEMINI_API_KEY` | Optional | Only needed with `--provider gemini` |

See `.env.example` for the template.

## Development

- Python 3.10+, type hints required on all functions
- Pydantic v2 for all data models
- Run `pytest` before pushing changes
- See `CONTRIBUTING.md` for full guidelines
- Progress tracked in `docs/devlog/DEVLOG.md`
- Architecture decisions in `docs/decisions/ADR-index.md`
