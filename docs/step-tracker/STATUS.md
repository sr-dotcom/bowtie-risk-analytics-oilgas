# Project Status

## Phase 0: Setup
- [x] Project scaffold and dependencies
- [x] Git configuration and hygiene
- [x] Initial documentation (Devlog, decisions)
- [x] End-to-end pipeline verification (Step 0.3)

## Phase 1: Data Pipeline
- [x] Bowtie JSON schema definition
- [x] Incident narrative ingestion
- [ ] Labeling strategy and dataset creation
- [x] Initial data acquisition (CSB/BSEE discovery + download + PDF→text) — DONE (2026-02-05)
- [x] Schema v2.3 normalization (`convert-schema` coercion pass) — DONE (2026-02-09)

## Phase 2: Analytics
- [x] Control coverage computation
- [x] Gap analysis reporting
- [x] Baseline metrics (Per-incident & Aggregate)

## Phase 3: Modeling
- [ ] Baseline model (Logistic Regression)
- [ ] Advanced model (XGBoost)
- [ ] Explainability (SHAP)

## Phase 4: Application
- [x] Streamlit interface (Dashboard KPIs + Incident Explorer)
- [ ] Export functionality
- [ ] Final documentation and demo
