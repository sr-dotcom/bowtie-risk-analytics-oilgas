# Changelog

All notable changes to Bowtie Risk Analytics are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v1.0] — 2026-05-02

Released. See the GitHub Release page for full release notes.

- Post-demo cleanup merged to `main`: 14 commits on `branch/restructure-cleanup` (D.1–D.5, B.1–B.7)
- `HANDOVER.md` and `KNOWN_ISSUES.md` generated as receiver-facing artifacts
- `src/modeling/cascading/barrier_model_dataset_base_v3.csv` tracked per Patrick's permission
- CI green on `main` — 7 test-file ignores in `ci.yml`, Bucket-A/B/C skip guards hardened
- ruff lint clean (active source); vitest 4.x upgrade; 6 of 7 npm audit CVEs cleared
- Structured-logging discipline across 5 hot-path modules; `hf_recovery.py` archived
- D001 `_legacy` import policy documented with explicit exception clauses in `CLAUDE.md`

---

## [v1.0-apr27-demo] — 2026-04-27

Final presentation demo cut (tag `v1.0-apr27-demo`, commit `592bfa9`). Demoed to
Prof. Ilieva Ageenko (academic supervisor) and Fidel Ilizastigui Perez (domain expert).

- End-to-end demo path verified: Load BSEE example → Analyze Barriers → barrier click → Drivers & HF
- RAG evidence narrative working via `/explain-cascading`
- SHAP waterfall chart rendered per barrier
- Apriori co-failure rules relabeled 174 → 723 (correct training corpus count)
- Dashboard cold-load redesign: placeholder state on initial load, populates on barrier click
- Ranking criterion tooltip added; provenance strip added to evidence cards

---

## M004 — Reconciliation sprint — 2026-04-22 to 2026-04-26

Audit-driven factual reconciliation following Playwright + Chrome DevTools live audits.
~10 commits. Decision markers: D016 branch activation, D019 strict-ordering correction, D020 PIF negative flags.

- D016/D019: pre-registered branch activation logic for `y_hf_fail` finalized — Branch C activated (AUC 0.556 ± 0.118, below 0.60 floor); `y_hf_fail` model not surfaced in production
- D020: PIF negative-flag tags surfaced in RAG retrieval context and frontend `PIFTags` component
- Cascade payload bug fixed — user-built scenarios now correctly populate `/predict-cascading` request
- Structured logging added to silent hot-path modules (`pair_builder`, `predict`, `context_builder`, etc.)
- GHA deploy.yml trigger branches cleaned; `continue-on-error: true` on webhook step documented

---

## M003 — Cascading model pivot — 2026-04-17 to 2026-04-21

Pivot from single-barrier Models 1/2/3 to cascading pair-feature XGBoost. Decision markers: D008–D015.

- D008: cascade model adopted — 18-feature barrier-pair vectors, GroupKFold(5) CV
- `y_fail_target` AUC: **0.763 ± 0.066** (fold floor 0.651). Replaces M002 Model 1 (F1=0.928 single-barrier)
- D009: Model 3 (barrier condition multiclass) dropped from M003 scope; archived
- D011: PIFs excluded from `y_fail` features (structural-features-only hypothesis validated)
- D017: RAG v2 corpus rebuilt (156-incident scope, PIF `_value` text + event recommendations ingested)
- New API endpoints: `POST /predict-cascading`, `POST /rank-targets`, `POST /explain-cascading`
- Prior `GET /predict` and `GET /explain` deprecated → 410 Gone
- `configs/risk_thresholds.json` (D006) becomes cross-boundary single source of truth for HIGH/MEDIUM/LOW tiers
- Frontend: `useAnalyzeCascading`, `useExplainCascading` hooks; `BowtieContext` orchestrates cascading state

---

## M002 — Initial modeling — 2026-03 to 2026-04-16

Three single-barrier XGBoost models, 4-stage hybrid RAG retrieval, Next.js 15 dashboard.

- Feature engineering pipeline: 17-feature matrix from controls + incidents CSV (D005 — `source_agency` dropped)
- Model 1 (`label_barrier_failed`) F1=0.922 ± 0.019; Model 2 (`label_barrier_failed_human`) F1=0.353
- SHAP TreeExplainer wired to both models; per-barrier reason codes generated at prediction time
- Risk thresholds recalibrated (D006): p60=0.45, p80=0.70 from validation-set quantiles
- 4-stage hybrid RAG: metadata filter → dual FAISS (barrier + incident) → intersection → RRF fusion
- RAG v1 baseline (50-query benchmark): Top-1=0.30, Top-5=0.56, Top-10=0.62, MRR=0.40
- FastAPI backend (`POST /predict`, `POST /explain`, `GET /health`, `GET /apriori-rules`)
- Next.js 15 dashboard: 4-tab view (Executive Summary, Drivers & HF, Ranked Barriers, Evidence)
- D007: Self-hosted Ubuntu mini-PC + Docker + Cloudflare Tunnel chosen over Streamlit Community Cloud
- Architecture freeze v1 declared 2026-03-04

---

## M001 — Data pipeline — 2026-02 to 2026-03

Ingestion, schema canonicalization, RAG v1 corpus, pipeline CLI.

- BSEE/CSB/PHMSA/TSB source discovery and PDF ingestion (`src/ingestion/sources/`)
- LLM-driven structured extraction: Haiku primary, Sonnet fallback, ~$0.45 / 20 PDFs
- Schema V2.3 canonicalization (7 top-level keys; `side`: prevention/mitigation → left/right; `barrier_status`: active → worked)
- 739 canonical V2.3 JSONs in `data/structured/incidents/schema_v2_3/`
- `corpus_v1`: 147 schema V2.3 JSONs from 148 BSEE+CSB PDFs (1 permanent skip: macondo scanned image)
- RAG v1 corpus: 526 incidents, 3,253 barrier controls, 25 barrier families; SentenceTransformer `all-mpnet-base-v2`
- D001: V1 legacy code quarantined to `src/_legacy/`; 14 production imports deferred to M005 migration
- Pipeline CLI with 15+ subcommands (`acquire`, `extract-text`, `extract-structured`, `schema-check`, `quality-gate`, etc.)
