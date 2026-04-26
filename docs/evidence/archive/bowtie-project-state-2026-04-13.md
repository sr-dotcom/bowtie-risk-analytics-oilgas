# Bowtie Risk Analytics — Project State (April 13, 2026)

## What Is Complete

### ML Models (LOC + engineering scoped, 558 rows, 174 incidents)
- Model 1: Binary barrier failure — F1=0.928, MCC=0.793
- Model 2: Human factor sensitivity — F1=0.348, MCC=0.266 (honest: 11.3% positive rate)
- Model 3: Multiclass barrier condition (effective/degraded/ineffective) — F1_macro=0.588
- GroupKFold on incident_id, PIF ablation complete, Logistic Regression baselines trained

### API (FastAPI)
- POST /predict — barrier failure probability + SHAP reason codes (both models)
- POST /explain — RAG evidence narrative via Claude Haiku
- GET /health — model load status, RAG corpus size, uptime
- GET /apriori-rules — 16 Apriori co-failure rules
- Phase 8 terminology mappings applied at response time
- asyncio.to_thread() wraps Anthropic calls

### Frontend (Next.js 15)
- BowtieSVG: pure SVG, BowTieXP visual spec, S-curve pathways, zoom, click handlers
- 4-tab dashboard: Executive Summary, Drivers & HF, Ranked Barriers, Evidence
- SHAP hidden feature filter: source_agency and primary_threat_category excluded from all UI surfaces
- Batch /predict on dashboard mount, /explain on demand per barrier

### Infrastructure
- Docker Compose: 3 services (api, frontend, nginx)
- nginx: /api/ proxied to FastAPI with 120s LLM timeout
- 54 Python test files, 352 passing, mocked lifespan — no artifacts needed in CI

### Domain Alignment
- All 14 Fidel domain comments addressed (Phase 8)
- 16 Apriori co-failure rules integrated and displayed
- LOC scoping correct

## What Is Left

| Area | Status | Notes |
|---|---|---|
| Deployment | Not done | Docker builds locally. Server available. Final step. |
| Model 2 F1 | 0.348 | Known — sparse human-factor labels |
| RAG recall Top-1 | 0.30 | Known — documented in EVALUATION.md |
| Apriori rules | Fixed April 13 | Now committed to data/evaluation/ |
