# Bowtie Risk Analytics

Python pipeline, RAG retrieval system, ML modeling layer, FastAPI service, and Next.js dashboard for analyzing oil & gas incidents using the Bowtie risk methodology. Ingests public incident reports (CSB, BSEE), extracts structured risk data via LLM, predicts barrier failure probability with SHAP explainability, retrieves similar barrier failures via hybrid semantic search, and surfaces results through an interactive Bowtie diagram. Current scope: **Loss of Containment** scenarios.

## RAG Retrieval System

A hybrid retrieval pipeline that finds similar barrier controls and incidents from the V2.3 corpus. Combines bi-encoder vector search with metadata filtering and Reciprocal Rank Fusion (RRF) ranking, with an optional cross-encoder reranker.

```
Query (barrier + incident)
         |
    Embed queries (all-mpnet-base-v2, 768-dim)
         |
    +----+----+
    |         |
Barrier     Incident
FAISS       FAISS
top-50      top-20
    |         |
    +----+----+
         |
    Intersection filter
    (dual relevance)
         |
    RRF ranking
    score = 1/(k+r1) + 1/(k+r2)
         |
    Optional: CrossEncoder rerank
    (ms-marco-MiniLM-L-6-v2)
         |
    Context builder
    (structured text, 8000 char max)
         |
    ExplanationResult
```

**Corpus:** 526 incidents, 3,253 barrier controls, 25 barrier families

**Baseline performance (50-query benchmark):**

| Metric | Baseline | With Reranker |
|--------|----------|---------------|
| Top-1  | 0.30     | 0.30          |
| Top-5  | 0.56     | 0.56          |
| Top-10 | 0.62     | 0.60          |
| MRR    | 0.40     | 0.42          |

The cross-encoder reranker is kept **optional** (disabled by default) — the recall bottleneck at the retrieval stage dominates ranking improvements. See [RAG System Overview](docs/rag_system_overview.md) for full architecture details.

### Running the Retrieval System

```python
from src.rag.rag_agent import RAGAgent
from src.rag.embeddings.sentence_transformers_provider import SentenceTransformerProvider

provider = SentenceTransformerProvider()
agent = RAGAgent.from_directory(rag_dir, provider)

result = agent.explain(
    barrier_query="pressure relief valve failed to activate",
    incident_query="gas release during well intervention",
    barrier_family="pressure_safety",      # optional filter
    barrier_failed_human=True,             # optional filter
    pif_filters={"competence": True},      # optional filter
)

print(result.context_text)    # Structured markdown for LLM context
print(result.results)         # Ranked RetrievalResult list
```

To enable the cross-encoder reranker:

```python
from src.rag.reranker import CrossEncoderReranker

reranker = CrossEncoderReranker()
agent = RAGAgent.from_directory(rag_dir, provider, reranker=reranker)
```

### Running the Retrieval Benchmark

```bash
python scripts/evaluate_retrieval.py
```

Results are written to `data/evaluation/results/evaluation_results.json`. See the [Experiment History](docs/rag_experiment_history.md) for methodology and analysis.

### RAG Documentation

| Document | Description |
|----------|-------------|
| [RAG System Overview](docs/rag_system_overview.md) | Full architecture, components, and data requirements |
| [Experiment History](docs/rag_experiment_history.md) | Research evolution across 3 experiments |
| [Phase-2 Evaluation Report](docs/reports/rag_phase2_evaluation.md) | Quantitative results and recommendation |
| [Implementation Audit](docs/reports/rag_phase2_implementation_audit.md) | Design compliance and code quality review |

## ML Modeling

XGBoost + Logistic Regression models predict barrier failure probability from 18 engineered features. Two prediction targets:

- **Model 1** (`label_barrier_failed`): Did the barrier fail to perform? XGBoost F1=0.928 ±0.019 (5-fold GroupKFold CV).
- **Model 2** (`label_barrier_failed_human`): Did the barrier fail *and* human factors contributed? XGBoost F1=0.348 ±0.060.
- **Model 3** (barrier condition, 3-class): XGBoost macro F1=0.588. Separates effective / degraded / ineffective barrier states.

**Features:** 5 categorical (side, barrier_type, line_of_defense, barrier_family, source_agency) + 12 PIF boolean indicators + supporting_text_count. OrdinalEncoder with unknown=-1 for unseen categories. GroupKFold on `incident_id` prevents PIF leakage (PIFs are incident-level, broadcast to all controls in the incident).

**SHAP explainability:** `TreeExplainer` per model with 200-sample background arrays. Per-barrier reason codes returned by `POST /predict`. Top factors mapped to process safety display names via `configs/mappings/pif_to_degradation.yaml`.

**Reproduce artifacts (4-step process):**

```bash
python -m src.modeling.feature_engineering   # → data/models/artifacts/feature_matrix.parquet
python -m src.modeling.train                 # → xgb_model*.json, logreg_*.joblib
python -m src.modeling.explain               # → shap_background_*.npy, pif_ablation_report.json
python scripts/generate_risk_thresholds.py   # → risk_thresholds.json (p60/p80 cutoffs)
```

All model artifacts are gitignored. See [EVALUATION.md](EVALUATION.md) for full metrics.

## FastAPI Server

A production FastAPI service (`src/api/main.py`) serves ML predictions and RAG evidence narratives. All resources (XGBoost models, SHAP TreeExplainers, RAG index, mapping configs) are loaded once at startup via the async lifespan context and stored on `app.state`.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/predict` | Barrier failure probability + SHAP reason codes for both models. Accepts 18-field feature dict; returns probabilities, SHAP lists, risk level (H/M/L), and degradation factors. |
| `POST` | `/explain` | RAG evidence narrative for a barrier. Retrieves similar historical failures, applies confidence gate (barrier_sim_score ≥ 0.25), then calls Claude Haiku for a narrative + recommendations. Runs in `asyncio.to_thread()` to avoid blocking the event loop. |
| `GET` | `/health` | Service health: loaded model info, RAG corpus size, uptime. |

**Start locally:**

```bash
uvicorn src.api.main:app --reload --port 8000
```

Interactive docs at `http://localhost:8000/docs`.

**Testing without model artifacts:** Pass `lifespan_override` to `create_app()` to inject mocked resources — no real models needed.

## Next.js Frontend

A Next.js 15 App Router dashboard (`frontend/`) visualizes barrier risk predictions on an interactive Bowtie diagram.

**Layout:**

```
┌──────────────┬──────────────────────────┬──────────────────┐
│ Sidebar      │ Bowtie Diagram           │ Detail Panel     │
│ BarrierForm  │ React Flow (nodeTypes at │ Prediction score │
│ Add barriers │ module scope — required) │ SHAP waterfall   │
│ Event desc.  │ Prevention | Top Event   │ RAG evidence     │
│              │          | Mitigation   │ Citations        │
└──────────────┴──────────────────────────┴──────────────────┘
```

**Run locally:**

```bash
cd frontend
npm install
npm run dev      # http://localhost:3000
npm test         # vitest (10 tests)
```

**Key constraints:**
- Tailwind CSS v3 (v4 requires Node 20+; project targets Node 18)
- vitest@2.1.9 pinned (vitest v4 requires Node 20+)
- `nodeTypes` must be defined at module scope in React Flow components — component-scope definition causes infinite re-renders
- `frontend/lib/` must be force-added to git: `git add -f frontend/lib/` (root `.gitignore` has a `lib/` pattern)

## Quickstart

```bash
# 1. Create virtual environment
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run tests
pytest

# 4. Configure Anthropic API key (required for structured extraction)
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY (other keys are optional)
```

## Running with Docker

The full stack (FastAPI backend + Next.js frontend + nginx reverse proxy) can be run with Docker Compose in four steps:

```bash
# 1. Copy environment file and set your API key
cp .env.example .env
# Edit .env — ANTHROPIC_API_KEY is optional for /health and /predict,
# but required for the /explain endpoint (LLM-powered evidence narrative).

# 2. Build images
docker compose build

# 3. Start the stack in the background
docker compose up -d

# 4. Visit the app
open http://localhost        # nginx serves the Next.js UI on port 80
# API is available at http://localhost/api/health
```

Tear down with:

```bash
docker compose down          # stop containers
docker compose down -v       # stop + remove volumes
```

> **Note:** The `api` service uses a 60-second `start_period` healthcheck so the frontend waits
> for the model artifacts to load before serving traffic.

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
python -m src.pipeline quality-gate --incident-dir data/structured/incidents/schema_v2_3

# Generate Schema v2.3 dataset locally (gitignored output; may be missing in a clean clone)
python -m src.pipeline convert-schema --incident-dir data/structured/incidents/anthropic --out-dir data/structured/incidents/schema_v2_3

# Legacy analytics pipeline
python -m src.pipeline process
```

Use `--help` on any subcommand for full options. Key flags:
- `--resume` — skip already-extracted files on re-runs
- `--limit N` — process at most N files
- `--provider {stub,openai,anthropic,gemini}` — LLM provider selection

## Data / Schema

We produce normalized incident JSON in **Schema v2.3** format. Local outputs are
stored under `data/structured/incidents/schema_v2_3` (gitignored).

```bash
python -m src.pipeline schema-check --incident-dir data/structured/incidents/schema_v2_3
python -m src.pipeline quality-gate --incident-dir data/structured/incidents/schema_v2_3
```

## Deliverables

To build a shareable deliverable pack locally (not committed), run:

```bash
# Quick: just the zip
bash scripts/make_deliverable_pack.sh --tag schema

# Full audit: validate, convert, bundle with README + inventory
bash scripts/verify_and_bundle_schema_v2_3.sh --tag schema_v2_3_audit
```

The output lands in `out/deliverables/` (gitignored) and includes the zip,
`README.md`, `BUNDLE_INVENTORY.md`, and `FILES.txt`.

## Output Directory Contract (Architecture Freeze v1)

All data artifacts are produced locally and **not committed to the repository**.
Reproduce them by running the pipeline commands above. Tag: `pipeline-freeze-v1`.

**Canonical dataset:** 739 incidents (Schema v2.3), 4,776 controls. Deterministic exports.

```
data/
  raw/<source>/                    # L0: Ingested PDFs + extracted text
    pdf/                           #   Source PDFs (bsee, csb, phmsa, tsb)
    text/                          #   Extracted text
    manifest.csv                   #   Per-source tracking manifest
  structured/
    incidents/schema_v2_3/         # L1: 739 canonical V2.3 JSONs (SINGLE SOURCE OF TRUTH)
    debug_llm_responses/           #   Raw LLM text (forensic only)
    structured_manifest.csv        #   Extraction tracking manifest
    run_reports/                   #   Per-run summary reports
  processed/                       # L2: Analytics-ready flat exports
    flat_incidents_combined.csv    #   739 incident rows
    controls_combined.csv          #   4,776 control rows
```

See `docs/architecture/ARCHITECTURE_FREEZE_v1.md` for full contracts, invariants, and extension rules for RAG/modeling.

## Project Structure

```
src/
  models/          Pydantic v2 data models (Incident, Bowtie, Schema v2.3)
  ingestion/       Data acquisition, PDF text extraction, structured LLM extraction
  llm/             LLM provider abstraction (Stub, OpenAI, Anthropic, Gemini)
  prompts/         Extraction prompt templates and loader
  validation/      Pydantic-based schema validation
  analytics/       Coverage calculation, gap analysis, flattening, baseline
  rag/             RAG retrieval system
    config.py          Pipeline constants
    embeddings/        EmbeddingProvider ABC + SentenceTransformer impl
    vector_index.py    FAISS IndexFlatIP wrapper with mask support
    corpus_builder.py  V2.3 JSON -> barrier/incident document CSVs
    retriever.py       4-stage hybrid retrieval + RRF ranking
    reranker.py        Optional cross-encoder reranker
    context_builder.py Structured context text assembly
    rag_agent.py       Orchestrator (from_directory, explain)
  app/             Streamlit dashboard
  pipeline.py      CLI entry point

assets/
  schema/          Schema v2.3 JSON schema and template
  prompts/         Extraction prompt markdown

data/
  evaluation/      RAG evaluation dataset and results (committed)

docs/
  decisions/       Architecture Decision Records (ADRs)
  reports/         Evaluation and audit reports
  devlog/          Development log
  step-tracker/    Phase-by-phase project status
  meetings/        Meeting notes
  handoff/         Historical planning documents

tests/             Unit tests (pytest, 469+ passing)
scripts/           Standalone analytics CLI + evaluation harness
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

## Future Improvements

| Priority | Area | Improvement |
|----------|------|-------------|
| 1 | Retrieval recall | BM25 hybrid search (sparse + dense) to capture exact keyword matches |
| 1 | Retrieval recall | Query expansion for oil & gas terminology variants |
| 2 | Corpus growth | Ingest PHMSA pipeline and TSB transportation incidents |
| 2 | Retrieval recall | Domain-tuned embedding model (fine-tune on incident/barrier pairs) |
| 3 | Reranker | Re-evaluate cross-encoder impact at 1000+ incidents |
| 3 | Hardening | Graceful fallback if cross-encoder model fails to load |

See the [Experiment History](docs/rag_experiment_history.md) for the full research context behind these priorities.

## Development

- Python 3.10+, type hints required on all functions
- Pydantic v2 for all data models
- Run `pytest` before pushing changes
- See `CONTRIBUTING.md` for full guidelines
- Progress tracked in `docs/devlog/DEVLOG.md`
- Architecture decisions in `docs/decisions/ADR-index.md`
