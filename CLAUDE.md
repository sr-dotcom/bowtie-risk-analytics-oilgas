# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bowtie Risk Analytics is a Python pipeline, RAG retrieval system, FastAPI backend, and Next.js 15 frontend for analyzing oil & gas incidents using the Bowtie risk methodology. It ingests public incident reports (CSB, BSEE, PHMSA, TSB), extracts structured risk data via LLM, retrieves similar barrier failures via hybrid semantic search, calculates barrier coverage metrics, and predicts barrier failure risk using trained ML models. Current scope: **Loss of Containment** scenarios.

**Core question this system answers:** "Which barriers in this Bowtie are most likely to be weak or fail, and why?"

**Binary prediction targets:**
- `label_barrier_failed` — barrier did not perform (failed/degraded/not_installed/bypassed). Exclude unknowns from training.
- `label_barrier_failed_human` — barrier failed AND human factors contributed (barrier_failed_human == True). Exclude unknowns.

## Commands

```bash
# Install Python dependencies
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run all tests
pytest

# Run a single test file
pytest tests/test_engine.py

# Pipeline CLI
python -m src.pipeline acquire --csb-limit 20 --bsee-limit 20 --download
python -m src.pipeline extract-text
python -m src.pipeline extract-structured --provider anthropic --model claude-sonnet-4-5-20250929
python -m src.pipeline extract-structured --provider stub --limit 3   # no API key needed
python -m src.pipeline schema-check --incident-dir data/structured/incidents/schema_v2_3
python -m src.pipeline quality-gate --incident-dir data/structured/incidents/schema_v2_3
python -m src.pipeline convert-schema --incident-dir data/structured/incidents/anthropic --out-dir data/structured/incidents/schema_v2_3
python -m src.pipeline build-combined-exports   # produces flat_incidents_combined.csv + controls_combined.csv
python -m src.pipeline discover-source --source csb|bsee|phmsa|tsb
python -m src.pipeline ingest-source --source bsee --url-list configs/sources/bsee/url_list.csv
python -m src.pipeline corpus-manifest
python -m src.pipeline corpus-extract --policy configs/model_policy.yaml
python -m src.pipeline corpus-clean

# Modeling
python -m src.modeling.feature_engineering   # build feature matrix parquet + encoder artifacts
python -m src.modeling.train                 # train LogReg + XGBoost, save to data/models/artifacts/
python -m src.modeling.explain               # generate SHAP values + per-barrier reason codes

# FastAPI backend (development)
uvicorn src.api.main:create_app --factory --reload --port 8000

# Next.js frontend (development)
cd frontend && npm install && npm run dev    # http://localhost:3000

# Docker deployment (full stack)
docker compose up --build                   # starts API + frontend containers

# RAG evaluation
python scripts/evaluate_retrieval.py

# Association mining chain (standalone scripts, not pipeline)
python scripts/association_mining/jsonaggregation.py
python scripts/association_mining/jsonflattening.py
python scripts/association_mining/event_barrier_normalization.py
```

## Architecture

**Data flow:**
```
raw/ → structured/incidents/schema_v2_3/ → processed/ (flat CSVs) → data/models/artifacts/ → FastAPI /predict
                                         → RAG corpus (embeddings + retrieval)          → FastAPI /explain
                                                                                          → Next.js frontend
```

**Key modules:**

### Models & Validation
- `src/models/incident_v23.py` — IncidentV23 Pydantic v2 model (canonical Schema v2.3)
- `src/validation/incident_validator.py` — Pydantic validation
- `src/_legacy/incident.py` — Legacy Incident model (quarantined, do not import directly)
- `src/_legacy/bowtie.py` — Legacy Bowtie model (quarantined, do not import directly)

### Ingestion & Extraction
- `src/ingestion/structured.py` — LLM extraction orchestrator, `get_controls()` (single source of truth for control extraction)
- `src/ingestion/loader.py` — Raw text parsing
- `src/ingestion/manifests.py` — CSV manifest models (download/extraction state tracking)
- `src/ingestion/pdf_text.py` — PDF text extraction via pdfplumber
- `src/ingestion/normalize.py` — V2.2 to V2.3 normalization
- `src/ingestion/source_ingest.py` — Ingest PDFs from URL lists or local directories
- `src/ingestion/sources/` — Source-specific discovery and download (csb, bsee, phmsa, tsb)
- `src/extraction/` — Multi-pass PDF extraction with quality gating
- `src/corpus/` — corpus_v1 management (manifest, extract, clean)

### LLM Providers
- `src/llm/base.py` — LLM provider ABC
- `src/llm/anthropic_provider.py` — Anthropic Claude (default production provider)
- `src/llm/stub.py` — StubProvider for testing (no API key needed)
- `src/llm/model_policy.py` — YAML-driven model ladder (haiku to sonnet escalation)
- `src/llm/registry.py` — Provider registry

### Analytics
- `src/analytics/flatten.py` — V2.3 controls to flat CSV (CONTROLS_CSV_COLUMNS: 16 columns)
- `src/analytics/build_combined_exports.py` — Combined flat_incidents + controls CSVs across all sources
- `src/analytics/control_coverage_v0.py` — Coverage score from flat controls
- `src/analytics/aggregation.py` — Fleet-wide metric aggregation
- `src/analytics/baseline.py` — Pandas-based summary analytics
- `src/nlp/loc_scoring.py` — Keyword-based Loss of Containment scoring (LOC_v1, frozen)

### Modeling (ML pipeline)
- `src/modeling/feature_engineering.py` — Join controls + incidents CSVs, derive binary labels, encode features, output feature matrix parquet + encoder.joblib
- `src/modeling/train.py` — LogReg + XGBoost, stratified 5-fold GroupKFold CV, save artifacts to data/models/artifacts/
- `src/modeling/explain.py` — SHAP values + per-barrier reason codes via TreeExplainer
- `src/modeling/predict.py` — BarrierPredictor: loads all artifacts once at startup, returns SHAP-augmented predictions for both models
- `src/modeling/profile.py` — Data profiling and label distribution analysis

### FastAPI Backend
- `src/api/main.py` — FastAPI application factory; lifespan loads all ML resources once at startup
- `src/api/schemas.py` — Pydantic request/response schemas for all endpoints
- `src/api/mapping_loader.py` — Barrier type / LOD display name mappings from configs/

**API endpoints:**
- `POST /predict` — barrier failure probability + SHAP reason codes (both models)
- `POST /explain` — RAG evidence narrative for a barrier (calls AnthropicProvider via asyncio.to_thread)
- `GET /health` — service status with loaded model artifact info
- `GET /apriori-rules` — pre-computed Apriori co-failure association rules

### RAG Retrieval System
- `src/rag/config.py` — Pipeline constants
- `src/rag/embeddings/` — EmbeddingProvider ABC + SentenceTransformer implementation (all-mpnet-base-v2)
- `src/rag/vector_index.py` — FAISS IndexFlatIP wrapper with mask support
- `src/rag/corpus_builder.py` — V2.3 JSON to barrier/incident document CSVs, barrier family assignment, PIF extraction
- `src/rag/retriever.py` — 4-stage hybrid retrieval (metadata filter, dual FAISS, intersection, RRF ranking)
- `src/rag/reranker.py` — Optional cross-encoder reranker (ms-marco-MiniLM-L-6-v2)
- `src/rag/context_builder.py` — Structured context text assembly (8000 char max)
- `src/rag/rag_agent.py` — RAGAgent orchestrator (from_directory, explain)
- `src/rag/explainer.py` — BarrierExplainer: wires RAG context + SHAP reason codes to LLM for evidence narrative

### Next.js Frontend
- `frontend/` — Next.js 15 application (App Router, TypeScript, Tailwind CSS)
- `frontend/components/BowtieApp.tsx` — Root application component
- `frontend/components/diagram/BowtieSVG.tsx` — Interactive SVG bowtie diagram with barrier click/hover
- `frontend/components/dashboard/DashboardView.tsx` — 4-tab dashboard: Executive Summary, Drivers & HF, Ranked Barriers, Evidence
- `frontend/components/dashboard/DriversHF.tsx` — Global SHAP chart, PIF prevalence chart, Apriori rules table
- `frontend/components/dashboard/RankedBarriers.tsx` — Barriers ranked by failure risk
- `frontend/components/panel/DetailPanel.tsx` — Per-barrier detail panel with SHAP waterfall + RAG evidence
- `frontend/context/` — React context for bowtie state, predictions, and scenario management
- `frontend/hooks/` — Custom hooks: useAnalyzeBarriers (batch /predict calls), useBowtieContext
- `frontend/__tests__/` — Vitest unit tests for all major components

### Pipeline Orchestration
- `src/pipeline.py` — CLI entry point with 15+ subcommands
- `src/prompts/loader.py` — Extraction prompt loader with template substitution

### Association Mining (standalone scripts)
- `scripts/association_mining/jsonaggregation.py` — JSON to aggregated incidents
- `scripts/association_mining/jsonflattening.py` — Aggregated to flat barrier rows
- `scripts/association_mining/event_barrier_normalization.py` — 4-quadrant barrier family assignment (45 families)

### V1 Legacy Code (quarantined)
V1 files have been moved to `src/_legacy/` but are still imported by 3 production modules per D001 (src/pipeline.py, src/analytics/__init__.py, src/models/__init__.py — load-bearing for legacy coverage analysis until M005 cleanup; see docs/tech-debt.md for the cleanup tracker):
- `src/_legacy/incident.py` — Legacy Incident model (replaced by IncidentV23)
- `src/_legacy/bowtie.py` — Legacy Bowtie model
- `src/_legacy/engine.py` — Legacy barrier coverage engine (replaced by analytics/flatten.py)
- `src/_legacy/main.py` — Legacy Streamlit app entry point (replaced by Next.js frontend)
- `src/_legacy/utils.py` — Legacy data loading utilities

## Data Directories

```
data/
  raw/<source>/             # L0: Ingested PDFs + extracted text (bsee, csb, phmsa, tsb)
  structured/
    incidents/schema_v2_3/  # L1: 739 canonical V2.3 JSONs (SINGLE SOURCE OF TRUTH)
  processed/                # L2: Analytics-ready flat exports
    flat_incidents_combined.csv   # 739 rows, includes 12 PIF _mentioned columns
    controls_combined.csv         # 4,776 rows, 16+ columns per control
  models/
    artifacts/              # Trained model artifacts (gitignored, reproduce via train.py)
      feature_matrix.parquet    # Full feature matrix (4,688 eligible rows)
      feature_names.json        # Ordered feature name list (committed)
      encoder.joblib            # OrdinalEncoder fitted on training data
      logreg_model1.joblib      # LogReg for label_barrier_failed
      logreg_model2.joblib      # LogReg for label_barrier_failed_human
      xgb_model1.json           # XGBoost for label_barrier_failed (F1=0.928)
      xgb_model2.json           # XGBoost for label_barrier_failed_human (F1=0.348)
      xgb_model3.json           # XGBoost 3-class barrier condition (macro F1=0.588)
    evaluation/             # Training reports + data recon (gitignored)
  corpus_v1/                # Frozen V2.2 corpus (147 incidents, self-contained)
  evaluation/               # RAG evaluation dataset + results (committed)

out/
  association_mining/       # Script-only outputs (not consumed by pipeline)
```

**Layer isolation:** L0 never reads L1/L2. L1 reads L0 only. L2 reads L1 only. Models consume from L2 only.

**Data is gitignored** except data/samples/, data/evaluation/, data/models/artifacts/feature_names.json, and data/models/cascading_input/barrier_model_dataset_base_v3.csv (cascading training input — tracked per Patrick's OK to publish). Reproduce other artifacts via pipeline commands.

**Note:** `data/models/cascading_input/barrier_threat_pairs_for_jeffrey_v2.csv` is Jeffrey's association-mining export, kept locally for analytical work. It is NOT consumed by the current pipeline (data_prep.py uses the v3 file only). Excluded from git via .gitignore; Jeffrey holds the master copy.

**Training scope:** 558 LOC-scoped rows (domain-informed filtering on top of 4,688 training-eligible rows from controls_combined.csv). Filtering selects well-evidenced Loss of Containment controls.

## Architecture Freeze v1

**Status:** FROZEN as of 2026-03-04. Read `docs/architecture/ARCHITECTURE_FREEZE_v1.md` before any structural changes.

**Extension rules for new work:**
- Model artifacts go in `data/models/` (update data_pipeline_contract_v1.md when adding new artifact types)
- Models consume from L2 (`processed/`) or `out/association_mining/`
- Never write to `structured/` or `raw/`
- RAG reads from L1 or L2, never L0
- New modeling code goes in `src/modeling/`

**Forbidden patterns:**
- Do not create dirs under data/structured/incidents/ beyond schema_v2_3/
- Do not bypass get_controls() for control extraction
- Do not store ML/RAG artifacts in structured/ or raw/
- Do not write to out/ from src/pipeline.py
- Do not import from src/_legacy/ in active code — exception: src/pipeline.py, src/analytics/__init__.py, and src/models/__init__.py retain _legacy imports per D001 until the legacy coverage analysis is removed (M005 backlog item; see docs/tech-debt.md)

## Key Schema Fields

**Controls CSV columns (from src/analytics/flatten.py CONTROLS_CSV_COLUMNS):**
incident_id, control_id, name, side, barrier_role, barrier_type, line_of_defense, lod_basis, linked_threat_ids, linked_consequence_ids, barrier_status, barrier_failed, human_contribution_value, barrier_failed_human, confidence, supporting_text_count

**Additional columns in combined exports:** source_agency, provider_bucket, json_path

**Incidents CSV PIF columns (12 _mentioned booleans):**
People: competence_mentioned, fatigue_mentioned, communication_mentioned, situational_awareness_mentioned
Work: procedures_mentioned, workload_mentioned, time_pressure_mentioned, tools_equipment_mentioned
Organisation: safety_culture_mentioned, management_of_change_mentioned, supervision_mentioned, training_mentioned

## Label Derivation (for ML modeling)

```python
barrier_did_not_perform = barrier_status in ('failed', 'degraded', 'not_installed', 'bypassed')
hf_contributed = barrier_failed_human == True
label = 1 if (barrier_did_not_perform and hf_contributed) else 0
# EXCLUDE rows where barrier_status == 'unknown'
```

## Trained Models

Three models are trained and evaluated. All use XGBoost with 5-fold stratified GroupKFold cross-validation:

| Model | Target | Type | F1 (CV) |
|-------|--------|------|---------|
| Model 1 | `label_barrier_failed` — barrier did not perform | XGBoost binary | **0.928 ±0.019** |
| Model 2 | `label_barrier_failed_human` — failed with human factor | XGBoost binary | **0.348 ±0.060** |
| Model 3 | Barrier condition (effective / degraded / ineffective) | XGBoost 3-class | macro F1 **0.588** |

LogReg baselines are trained alongside XGBoost for both binary targets (logreg_model1.joblib, logreg_model2.joblib). Feature importance via SHAP TreeExplainer — values are in log-odds space (margin output). SHAP is NOT serialized; TreeExplainer is recreated from model at prediction time.

## M003 cascading architecture

The current (M003) prediction pipeline uses a cascading pair-feature XGBoost model, replacing the single-barrier Model 1 from M002. Core modules:

- `src/modeling/cascading/pair_builder.py` — constructs 18-feature barrier-pair vectors from a scenario
- `src/modeling/cascading/predict.py` — inference module; loads XGBoost pipeline, emits `y_fail_probability` + `risk_band` + SHAP values
- `src/modeling/cascading/train.py` — training entry point
- `src/modeling/cascading/data_prep.py` — preprocessing
- `src/modeling/cascading/shap_probe.py` — SHAP explainer setup
- `archive/disabled-experiments/hf_recovery.py` — y_hf_fail target support (disabled per D016 Branch C; moved out of active src/ tree per AUDIT_TRIAGE F015)
- `src/modeling/cascading/mini_gate.py` — threshold gating for predictions

Model artifacts live in `data/models/artifacts/xgb_cascade_y_fail_*.{joblib,json}`. Training data: `data/processed/cascading_training.parquet` (156 unique incidents, 530 pair-feature rows current; model metadata records 813 rows from an earlier snapshot).

### API endpoints

- `POST /predict-cascading` — returns `y_fail_probability` + SHAP for every barrier in a scenario, conditioned on a specified barrier
- `POST /rank-targets` — lightweight ranking without SHAP, for quick comparative views
- `POST /explain-cascading` — pairs a prediction with RAG-retrieved evidence (degradation context, similar incidents, narrative synthesis)
- `GET /predict` → 410 Gone (deprecated single-barrier endpoint)
- `GET /explain` → 410 Gone

### RAG v2 corpus

Built by `scripts/build_rag_v2.py`. Scoped to the 156-incident cascading training set. Two document types:

- `data/rag/v2/datasets/barrier_documents.csv` (1,161 barriers)
- `data/rag/v2/datasets/incident_documents.csv` (156 incidents)

Embeddings and FAISS indexes in `data/rag/v2/{embeddings,barrier_faiss.bin,incident_faiss.bin}`.

### Frontend integration

- `frontend/hooks/useAnalyzeCascading.ts` — calls `/predict-cascading`
- `frontend/hooks/useExplainCascading.ts` — calls `/explain-cascading`
- `frontend/context/BowtieContext.tsx` — orchestrates cascading state, fires explain on barrier click

### Cross-boundary risk thresholds

`configs/risk_thresholds.json` (D006) is the single source of truth for HIGH/MEDIUM/LOW tier cutoffs. Both the Python API (`src/modeling/cascading/predict.py`) and the TypeScript frontend hook (`frontend/hooks/useAnalyzeBarriers.ts`) read this file. The cascade model's own `xgb_cascade_y_fail_metadata.json` contains a parallel `risk_tier_thresholds` field — **this field is currently unused**; predict.py reads D006, not the metadata. Do not rely on metadata thresholds.

### Decision register

Design decisions are exported from GSD to `docs/decisions/DECISIONS.md`. Recent keys: D016 (Branch C — y_hf_fail retained but not surfaced), D017 (RAG v2 corpus build), D006 (threshold recalibration).

## Code Conventions

- Python 3.10+, type hints required on all functions
- Pydantic v2 for all data models with ConfigDict(strict=False) for flexible parsing
- PEP 8 formatting
- Tests in tests/ matching test_*.py pattern
- Frontend tests in frontend/__tests__/ using Vitest
- Update docs/devlog/DEVLOG.md with significant progress
- V2.3 JSON files: read with encoding="utf-8-sig", write with encoding="utf-8"

## Gotchas

- **Canonical schema is V2.3** — 7 top-level keys: incident_id, source, context, event, bowtie, pifs, notes
- V2.2 to V2.3 key changes: side prevention to left / mitigation to right; barrier_status active to worked; line_of_defense "1st" to 1 (int)
- source.agency is absent from real JSONs; source_agency resolution uses doc_type, then URL, then path segment, then UNKNOWN
- RAGAgent.explain() returns ExplanationResult with context_text but does NOT call an LLM — it is retrieval only
- BarrierExplainer (src/rag/explainer.py) wraps RAGAgent.explain() + AnthropicProvider and DOES call LLM
- pipeline.py infinite recursion bug in get_sources_root() has been fixed (no longer present)
- **Test count: 352 Python tests passing** (pytest). 9 collection errors + import failures are pre-existing xgboost/faiss/shap environment issues, not regressions in source code. Frontend: 13 Vitest test files.
- FastAPI /explain endpoint calls AnthropicProvider.extract() (blocking requests.post) via asyncio.to_thread() to avoid event-loop blocking — do not refactor to bare await
- SHAP TreeExplainer must NOT be serialized (joblib/pickle); always recreate from the loaded XGBoost model
- All imports of src/_legacy/ must be avoided in active code — exception: 3 production modules (src/pipeline.py, src/analytics/__init__.py, src/models/__init__.py) retain _legacy imports per D001 until the legacy coverage analysis is removed. See docs/tech-debt.md M005 backlog. The legacy module otherwise exists only for historical reference.

## RAG System

**Corpus:** 526 incidents, 3,253 barrier controls, 25 barrier families
**Baseline performance (50-query benchmark):** Top-1=0.30, Top-5=0.56, Top-10=0.62, MRR=0.40
**Tag:** v1.0-rag-baseline

## Docker Deployment

The full stack is containerized for deployment:

```yaml
# docker-compose.yml spins up both services
docker compose up --build

# Individual images
docker build -f Dockerfile.api -t bowtie-api .
docker build -f Dockerfile.frontend -t bowtie-frontend .
```

- `Dockerfile.api` — FastAPI backend; serves on port 8000
- `Dockerfile.frontend` — Next.js 15 frontend; serves on port 3000
- `docker-compose.yml` — Orchestrates API + frontend with service networking

## Session Checkpoint

**Last completed (April 2026):** Full modeling + FastAPI backend + Next.js 15 frontend built and integrated. Three XGBoost models trained (F1=0.928/0.348/0.588). SHAP explainability wired to API. 4-tab Next.js dashboard deployed with BowtieSVG, ranked barriers, SHAP waterfall, and RAG evidence panels. V1 legacy files quarantined to src/_legacy/.

**Current state:** 739 incidents, 4,776 controls, 558 LOC-scoped training rows, 352 Python tests passing, FastAPI + Next.js stack operational, Docker deployment configured.

**Next up:** Deploy to Streamlit Community Cloud / hosting provider.
