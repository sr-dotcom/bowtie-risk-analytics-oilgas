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

Interactive bowtie diagram; click a barrier to drill into risk factors and evidence.

---

## Production access

Live hosted demo:

- **Frontend:** https://bowtie.gnsr.dev
- **API base:** https://bowtie-api.gnsr.dev
- **Health check:** https://bowtie-api.gnsr.dev/health

What you'll find: an interactive bowtie diagram, a ranked-barriers dashboard, SHAP-based explanations per barrier, and retrieved evidence from BSEE and CSB incident reports.

---

## The journey

The system was built in stages. Each chapter documents one decision boundary — what the problem was, what we tried, what worked, and what we'd do differently.

1. [Chapter 1 — The Problem](docs/journey/01-the-problem.md)
2. [Chapter 2 — From Investigation Reports to Training Rows](docs/journey/02-corpus-design.md)
3. [Chapter 3 — Pair Features and the Cascade](docs/journey/03-cascade-model.md)
4. [Chapter 4 — Two Explanation Signals](docs/journey/04-explainability-signals.md)
5. [Chapter 5 — Retrieval, Scoping, and the Domain Filter](docs/journey/05-rag-retrieval.md)
6. [Chapter 6 — Two Entry Paths and Four Implicit States](docs/journey/06-frontend-ux.md)
7. [Chapter 7 — Self-Hosted Deployment and Its Trade-Offs](docs/journey/07-deployment.md)
8. [Chapter 8 — Lessons Learned](docs/journey/08-lessons-learned.md)

---

## Architecture

- **Backend:** FastAPI (Python 3.10+) — cascading prediction endpoints, hybrid RAG retrieval
- **Frontend:** Next.js 15 + React + TypeScript — interactive bowtie diagram, dashboard, drill-down panel
- **ML:** XGBoost cascading model with SHAP explainability
- **Retrieval:** SentenceTransformers embeddings + FAISS + 4-stage hybrid pipeline
- **LLM:** Claude Haiku for RAG narrative synthesis

See CLAUDE.md for deeper technical details and the decision register for the design decision log.

---

## Other documentation

- CLAUDE.md — engineering notes, conventions, gotchas
- docs/decisions/DECISIONS.md — architectural decision register (D001–D021)
- docs/knowledge/KNOWLEDGE.md — durable lessons and rules (K-entries, L-entries)
- docs/journey/ — eight chapters above, in narrative form
- tests/README.md, data/evaluation/README.md, scripts/README.md, src/modeling/cascading/README.md — sub-area documentation

---

## Repository structure
src/           backend (Python): cascading model, RAG pipeline, FastAPI endpoints
frontend/      frontend (Next.js + React): bowtie diagram, dashboard, drill-down
scripts/       one-shot utilities (corpus build, model retraining, verification)
tests/         pytest suite (backend) + Vitest (frontend)
data/          datasets (raw + processed + model artifacts) — see data/README.md for tiering
configs/       risk thresholds, model configuration
deploy/        Dockerfiles, docker-compose, server-side ops references
docs/          architecture notes, decision log, journey chapters, evidence archive
archive/       superseded artifacts preserved for provenance

---

## Local development

Requirements: Python 3.10+, Node 20+, npm.

```bash
git clone https://github.com/sr-dotcom/bowtie-risk-analytics-oilgas.git
cd bowtie-risk-analytics-oilgas

# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env  # add your ANTHROPIC_API_KEY

# Frontend
cd frontend && npm install && cd ..

# Run (two terminals)
uvicorn src.api.main:create_app --factory --reload --port 8000
cd frontend && npm run dev

# Open http://localhost:3000
```

Docker-compose path is documented in CLAUDE.md for parity with the hosted deployment.

---

## Team

- Naga Sathwik Reddy Gona
- Patrick Hunter
- Jeffrey Arnette
- Nithin Sai Kumar Bandarupalli

Academic supervisor: Dr. Ilieva Ageenko (UNC Charlotte)

---

## License

MIT — see [LICENSE](LICENSE).
