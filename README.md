# Bowtie Risk Analytics for Oil & Gas

A machine-learning system that predicts process safety barrier failure in oil & gas operations, grounded in real incident investigations from the US Bureau of Safety and Environmental Enforcement (BSEE) and the US Chemical Safety Board (CSB).

**Status:** MS practicum project, UNC Charlotte, graduation May 2026. Not a production system.

---

## What it does

Given a bowtie diagram describing a hazardous scenario (a top event, its threats, its barriers, its consequences), the system:

1. **Predicts which barriers are most likely to fail** using a cascading XGBoost model trained on 156 historical incidents.
2. **Explains each prediction** with SHAP feature attributions over 18 pair-features.
3. **Retrieves similar historical incidents** via a hybrid 4-stage RAG pipeline (BM25 + dense embeddings + reranking + RRF fusion).
4. **Surfaces investigator findings** — real recommendations from BSEE and CSB reports.

Interactive bowtie diagram, click a barrier to drill into risk factors and evidence.

---

## Architecture

- **Backend:** FastAPI (Python 3.10+) — cascading prediction endpoints, hybrid RAG retrieval
- **Frontend:** Next.js 15 + React + TypeScript — interactive bowtie diagram, dashboard, drill-down panel
- **ML:** XGBoost cascading model with SHAP explainability
- **Retrieval:** SentenceTransformers embeddings + FAISS + 4-stage hybrid pipeline
- **LLM:** Claude Haiku for RAG narrative synthesis

See `CLAUDE.md` for deeper technical details and `docs/decisions/DECISIONS.md` for the design decision log.

---

## Quick start

Requirements: Python 3.10+, Node 20+, npm.

```bash
# Backend
git clone https://github.com/sr-dotcom/bowtie-risk-analytics-oilgas.git
cd bowtie-risk-analytics-oilgas
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env  # add your ANTHROPIC_API_KEY

# Frontend
cd frontend
npm install
cd ..

# Run
uvicorn src.api.main:create_app --factory --reload --port 8000  # in one terminal
cd frontend && npm run dev                                        # in another
# Open http://localhost:3000
```

---

## Project structure

```
src/           backend (Python): cascading model, RAG pipeline, FastAPI endpoints
frontend/      frontend (Next.js + React): bowtie diagram, dashboard, drill-down
scripts/       one-shot utilities (corpus build, model retraining, verification)
tests/         pytest suite (backend) + Vitest (frontend)
data/          datasets (raw + processed + model artifacts) — see data/README.md for tiering
configs/       risk thresholds, model configuration
docs/          architecture notes, decision log, knowledge base
archive/       superseded artifacts preserved for provenance
```

---

## Credits

Project lead / primary engineer: Naga Sathwik Reddy Gona (GNSR)  
Academic supervisor: Prof. Dima Ageenko (UNC Charlotte)  
Domain expert reviewer: Fidel Ilizastigui Perez  
Team: Patrick Hunter (cascading model development), Jeffrey Arnette (co-failure association mining)

---

## License

MIT — see [LICENSE](LICENSE).
