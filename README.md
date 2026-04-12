# Bowtie Risk Analytics

> **Core question:** Which barriers in this Bowtie are most likely to be weak or fail, and why?

Python pipeline, RAG retrieval, FastAPI backend, and Next.js 15 dashboard for analyzing oil & gas incidents using the Bowtie risk methodology. Ingests public incident reports (CSB, BSEE, PHMSA, TSB), extracts structured risk data via LLM, predicts barrier failure probability with SHAP explainability, retrieves similar barrier failures via hybrid semantic search, and surfaces results through an interactive Bowtie diagram. Current scope: **Loss of Containment** scenarios.

## Architecture

```
PDF reports
    │
    ▼
Python pipeline (acquire → extract-text → extract-structured → convert-schema)
    │
    ▼
739 canonical V2.3 JSON incidents  →  RAG corpus (526 incidents, 3,253 controls)
    │                                       │
    ▼                                       ▼
L2 flat CSVs (4,776 controls)        FAISS vector index
    │                                       │
    ▼                                       │
XGBoost models (3) + SHAP          ←───────┘
    │
    ▼
FastAPI  :8000  (POST /predict, POST /explain, GET /health, GET /apriori-rules)
    │
    ▼
Next.js 15  :3000  (BowtieSVG + 4-tab dashboard + DetailPanel)
    │
    ▼
nginx  :80  (public entry point, reverse proxy)
```

## Models

Three XGBoost models trained on 558 LOC-scoped rows from 739 incidents (5-fold stratified GroupKFold CV):

| Model | Target | Type | CV F1 |
|-------|--------|------|-------|
| Model 1 | `label_barrier_failed` — barrier did not perform | XGBoost binary | **0.928 ±0.019** |
| Model 2 | `label_barrier_failed_human` — failed with human factor | XGBoost binary | **0.348 ±0.060** |
| Model 3 | Barrier condition (effective / degraded / ineffective) | XGBoost 3-class | macro **0.588** |

**Features:** 5 categorical (side, barrier_type, line_of_defense, barrier_family, source_agency) + 12 PIF boolean indicators + supporting_text_count. SHAP `TreeExplainer` returns per-barrier reason codes in log-odds space.

Logistic Regression baselines are trained alongside XGBoost for both binary targets. GroupKFold on `incident_id` prevents PIF leakage.

## Quickstart

### Backend

```bash
# 1. Create virtual environment and install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Copy environment file and set API key (required for /explain endpoint)
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY

# 3. Run Python tests
pytest    # 352 tests passing

# 4. Start the FastAPI server
uvicorn src.api.main:app --reload --port 8000
# Interactive docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev       # http://localhost:3000
npm test          # vitest (13 test files)
```

### Docker (full stack)

```bash
# 1. Copy environment file and set your API key
cp .env.example .env
# ANTHROPIC_API_KEY is optional for /health and /predict, required for /explain

# 2. Build and start all services
docker compose up --build -d

# 3. Visit the app
open http://localhost        # nginx serves Next.js on port 80
# API available at http://localhost/api/health

# Tear down
docker compose down          # stop containers
docker compose down -v       # stop + remove volumes
```

The `api` service uses a 60-second `start_period` healthcheck so the frontend waits for model artifacts to load before serving traffic.

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/predict` | Barrier failure probability + SHAP reason codes for both models. Returns probabilities, top SHAP contributors, risk level (H/M/L). |
| `POST` | `/explain` | RAG evidence narrative for a barrier. Retrieves similar historical failures, then calls Claude to generate a narrative + recommendations. Runs via `asyncio.to_thread()`. |
| `GET` | `/health` | Service status: loaded model info, RAG corpus size, uptime. |
| `GET` | `/apriori-rules` | Pre-computed Apriori barrier co-failure association rules. |

## Project Structure

```
src/
  models/          Pydantic v2 data models (IncidentV23, Schema v2.3)
  ingestion/       PDF acquisition, text extraction, LLM structured extraction
  llm/             LLM provider abstraction (Stub, Anthropic, OpenAI, Gemini)
  prompts/         Extraction prompt templates and loader
  validation/      Pydantic-based schema validation
  analytics/       Flattening, coverage scoring, baseline aggregation
  modeling/        Feature engineering, XGBoost training, SHAP explain, predict
    feature_engineering.py  Build feature matrix parquet + encoder artifacts
    train.py               Train all three models
    explain.py             Generate SHAP values + per-barrier reason codes
    predict.py             BarrierPredictor: load artifacts once, serve predictions
  api/             FastAPI application
    main.py        App factory + lifespan resource loading
    schemas.py     Pydantic request/response schemas
    mapping_loader.py  Barrier type / LOD display name mappings
  rag/             RAG retrieval system
    config.py          Pipeline constants
    embeddings/        EmbeddingProvider ABC + SentenceTransformer (all-mpnet-base-v2)
    vector_index.py    FAISS IndexFlatIP wrapper with mask support
    corpus_builder.py  V2.3 JSON → barrier/incident document CSVs
    retriever.py       4-stage hybrid retrieval (filter → FAISS → intersect → RRF)
    reranker.py        Optional cross-encoder reranker (ms-marco-MiniLM-L-6-v2)
    context_builder.py Structured context text assembly (8000 char max)
    rag_agent.py       RAGAgent.from_directory() + explain() orchestrator
    explainer.py       BarrierExplainer: RAG context + SHAP → LLM narrative
  pipeline.py      CLI entry point (15+ subcommands)
  _legacy/         Quarantined V1 code (do not import)

frontend/
  components/
    BowtieApp.tsx         Root application component
    diagram/BowtieSVG.tsx Interactive SVG bowtie diagram
    dashboard/
      DashboardView.tsx   4-tab dashboard (Executive Summary | Drivers & HF | Ranked Barriers | Evidence)
      DriversHF.tsx       Global SHAP chart, PIF prevalence, Apriori rules table
      RankedBarriers.tsx  Barriers ranked by failure risk
    panel/DetailPanel.tsx Per-barrier SHAP waterfall + RAG evidence
  context/          React context for bowtie state, predictions, scenario management
  hooks/            useAnalyzeBarriers (batch /predict), useBowtieContext
  __tests__/        Vitest unit tests (13 test files)

data/
  raw/<source>/                    # L0: PDFs + extracted text
  structured/incidents/schema_v2_3/ # L1: 739 canonical V2.3 JSONs
  processed/                       # L2: flat_incidents_combined.csv, controls_combined.csv
  models/artifacts/                # Trained model artifacts (gitignored)
  evaluation/                      # RAG evaluation dataset + results (committed)

docs/
  architecture/    Architecture freeze docs and contracts
  devlog/          DEVLOG.md — session-by-session progress
  reports/         Evaluation and audit reports
  decisions/       Architecture Decision Records

scripts/           Evaluation harness, association mining, deliverable scripts
tests/             Python unit tests (pytest, 352 passing)
configs/           Source URL lists, model policy YAML, mapping configs
```

## RAG Retrieval System

Hybrid retrieval pipeline combining bi-encoder vector search with metadata filtering and Reciprocal Rank Fusion (RRF) ranking.

**Corpus (RAG eval subset):** 526 incidents, 3,253 barrier controls, 25 barrier families

**Baseline performance (50-query benchmark):**

| Metric | Baseline |
|--------|----------|
| Top-1  | 0.30 |
| Top-5  | 0.56 |
| Top-10 | 0.62 |
| MRR    | 0.40 |

**4-stage pipeline:** metadata filter → dual FAISS (barrier + incident indexes) → intersection → RRF ranking. Optional cross-encoder reranker (ms-marco-MiniLM-L-6-v2) disabled by default — the recall bottleneck at retrieval dominates ranking improvements.

```python
from src.rag.rag_agent import RAGAgent
from src.rag.embeddings.sentence_transformers_provider import SentenceTransformerProvider

provider = SentenceTransformerProvider()
agent = RAGAgent.from_directory(rag_dir, provider)

result = agent.explain(
    barrier_query="pressure relief valve failed to activate",
    incident_query="gas release during well intervention",
    barrier_family="pressure_safety",
    barrier_failed_human=True,
)
print(result.context_text)   # structured markdown ready for LLM context
```

## Pipeline Commands

```bash
# Discover and download incident PDFs
python -m src.pipeline acquire --csb-limit 20 --bsee-limit 20 --download

# Extract text from downloaded PDFs
python -m src.pipeline extract-text

# Structured extraction via LLM (requires ANTHROPIC_API_KEY in .env)
python -m src.pipeline extract-structured --provider anthropic --model claude-sonnet-4-5-20250929

# Run with stub provider — no API key needed
python -m src.pipeline extract-structured --provider stub --limit 3

# Schema validation and quality gate
python -m src.pipeline schema-check --incident-dir data/structured/incidents/schema_v2_3
python -m src.pipeline quality-gate --incident-dir data/structured/incidents/schema_v2_3

# Convert V2.2 extractions to V2.3
python -m src.pipeline convert-schema --incident-dir data/structured/incidents/anthropic --out-dir data/structured/incidents/schema_v2_3

# Build flat CSV exports (flat_incidents_combined.csv + controls_combined.csv)
python -m src.pipeline build-combined-exports

# Reproduce ML artifacts
python -m src.modeling.feature_engineering   # → feature_matrix.parquet + encoder.joblib
python -m src.modeling.train                 # → xgb_model*.json, logreg_*.joblib
python -m src.modeling.explain               # → SHAP values + per-barrier reason codes

# RAG evaluation
python scripts/evaluate_retrieval.py
```

Use `--help` on any subcommand for full options. Key flags: `--resume`, `--limit N`, `--provider {stub,anthropic,openai,gemini}`.

## Data / Schema

Canonical schema is **V2.3** — 7 top-level keys: `incident_id`, `source`, `context`, `event`, `bowtie`, `pifs`, `notes`.

**Controls CSV columns (16):** `incident_id`, `control_id`, `name`, `side`, `barrier_role`, `barrier_type`, `line_of_defense`, `lod_basis`, `linked_threat_ids`, `linked_consequence_ids`, `barrier_status`, `barrier_failed`, `human_contribution_value`, `barrier_failed_human`, `confidence`, `supporting_text_count`

**PIF columns (12 boolean `_mentioned` flags):**
- People: `competence`, `fatigue`, `communication`, `situational_awareness`
- Work: `procedures`, `workload`, `time_pressure`, `tools_equipment`
- Organisation: `safety_culture`, `management_of_change`, `supervision`, `training`

**Label derivation:**
```python
barrier_did_not_perform = barrier_status in ('failed', 'degraded', 'not_installed', 'bypassed')
label_barrier_failed = 1 if barrier_did_not_perform else 0
label_barrier_failed_human = 1 if (barrier_did_not_perform and barrier_failed_human == True) else 0
# Exclude rows where barrier_status == 'unknown' from training
```

V2.3 JSON files use `encoding="utf-8-sig"` (BOM) on read.

## What's Left

| Area | Status | Notes |
|------|--------|-------|
| Deployment | Not done | No hosting provider configured yet. Docker works locally. |
| Model 2 performance | Low F1 (0.348) | Human-factor label is sparse and noisy; more labeled data needed |
| RAG recall | Top-1 = 0.30 | BM25 hybrid or domain-tuned embeddings would improve recall |
| PHMSA / TSB corpus | Partial | Ingestion pipeline exists; structured extraction not run at scale |
| Auth / multi-user | Not built | Single-user local tool; no auth layer |

## Environment Variables

| Variable | Status | Notes |
|----------|--------|-------|
| `ANTHROPIC_API_KEY` | **Required for /explain** | LLM-powered evidence narrative |
| `OPENAI_API_KEY` | Optional | Only needed with `--provider openai` |
| `GEMINI_API_KEY` | Optional | Only needed with `--provider gemini` |

See `.env.example` for the template.

## LLM Providers

| Provider | Flag | Status |
|----------|------|--------|
| Anthropic Claude Sonnet | `--provider anthropic` | Default; used for all production extraction |
| Stub | `--provider stub` | No API key; returns fixed JSON for dev/CI |
| OpenAI | `--provider openai` | Optional; benchmarking only |
| Google Gemini | `--provider gemini` | Optional; benchmarking only |
