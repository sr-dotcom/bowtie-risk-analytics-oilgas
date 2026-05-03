# Contributing

## Development Setup

1.  **Environment**: Python 3.12+ required.
2.  **Dependencies**:
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
3.  **Testing**: Run `pytest` before pushing changes.
4.  **Backend** (FastAPI dev server):
    ```bash
    uvicorn src.api.main:create_app --factory --reload --port 8000
    ```
5.  **Frontend** (Next.js dev server):
    ```bash
    cd frontend && npm install && npm run dev   # http://localhost:3000
    cd frontend && npx vitest                   # frontend unit tests
    ```
6.  **Docker** (full stack):
    ```bash
    cp .env.example .env   # first time only — add ANTHROPIC_API_KEY if needed
    docker compose up --build
    ```

## Code Style

- **Type Hints**: Required for all function definitions.
- **Models**: Use Pydantic v2 for data structures.
- **Formatting**: Follow PEP 8.

## Directory Structure

- `src/models/` -- Pydantic v2 data models (IncidentV23, canonical Schema v2.3).
- `src/ingestion/` -- Data acquisition, PDF text extraction, structured LLM extraction.
- `src/llm/` -- LLM provider abstraction (Stub, Anthropic); model policy ladder.
- `src/prompts/` -- Extraction prompt templates and loader.
- `src/validation/` -- Pydantic-based schema validation.
- `src/analytics/` -- Coverage calculation, flattening, baseline analytics, combined exports.
- `src/modeling/` -- Feature engineering, XGBoost/LogReg training, SHAP explainability, prediction.
- `src/api/` -- FastAPI backend (predict, explain, health, apriori-rules endpoints).
- `src/rag/` -- Hybrid RAG retrieval: embeddings, FAISS index, retriever, context builder, explainer.
- `src/corpus/` -- corpus_v1 management (manifest, extract, clean).
- `src/nlp/` -- Keyword-based LOC scoring.
- `src/_legacy/` -- Quarantined V1 code (do not import in active code).
- `frontend/` -- Next.js 15 frontend (App Router, TypeScript, Tailwind CSS).
- `configs/` -- Source URL lists, model policy YAML, barrier/LOD display name mappings.
- `scripts/` -- Standalone analytics and association mining scripts.
- `docs/` -- ADRs, devlog, architecture docs, plans.
- `tests/` -- Python unit tests (`pytest`).

## Workflow

- Create a feature branch for changes.
- Ensure tests pass locally.
- Update `docs/devlog/DEVLOG.md` with significant progress.
