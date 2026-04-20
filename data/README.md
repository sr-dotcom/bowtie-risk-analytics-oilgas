# Data

Project datasets. Tiered by role and persistence policy.

## Tiers

### 1. Raw (immutable source of truth, in git)

- `data/raw/bsee/` — BSEE accident investigation PDFs and their manifest
- `data/raw/csb/` — CSB investigation reports
- Raw sources are committed for reproducibility. Do not modify.

### 2. Structured (extraction outputs, in git)

- `data/structured/incidents/schema_v2_3/` — 739 extracted incident JSONs in schema v2.3 (canonical)

### 3. Processed (model-ready, in git)

- `data/processed/cascading_training.parquet` — cascading model training set (530 rows, 156 incidents)
- `data/processed/flat_incidents_combined.csv` — flattened incident records for analytics
- `data/processed/flat_controls_v23_canonical_575.csv` — flattened controls (canonical 575 subset)
- `data/processed/controls_combined.csv` — full controls export (4,776 rows)

Small processed files stay in git. Large non-authoritative files are archived under `archive/` rather than committed at scale.

### 4. Model artifacts (gitignored — reproduce locally)

`data/models/artifacts/` is gitignored. Only `data/models/artifacts/feature_names.json` is tracked. Artifacts are reproduced locally via `scripts/retrain_from_parquet.py`.

- `xgb_cascade_y_fail_pipeline.joblib` (~470KB) — M003 cascading model
- `xgb_cascade_y_hf_fail_pipeline.joblib` — M003 y_hf_fail model (retained, not surfaced per D016)
- `xgb_model1.json` / `xgb_model2.json` — M002 single-barrier models (legacy)
- `logreg_model1.joblib` / `logreg_model2.joblib` — M002 logistic regression baselines
- `encoder.joblib` — M002 categorical encoder
- `feature_names.json` (**tracked**) — ordered feature list
- `apriori_rules.json` — co-failure rules (Jeffrey, M002)
- `shap_background_model1.npy` / `shap_background_model2.npy` — SHAP baseline samples
- See `data/models/artifacts/README.md` (local-only, also gitignored) for retraining steps.

### 5. RAG corpus (in git)

- `data/rag/v2/datasets/{barrier,incident}_documents.csv` — RAG v2 source documents (1,161 barriers, 156 incidents)
- `data/rag/v2/embeddings/` — precomputed embeddings
- `data/rag/v2/*_faiss.bin` — FAISS indexes
- `data/rag/archive/v1/` — v1 RAG corpus (archived; embedded and indexed files from the 526-incident eval corpus)

### 6. Demo scenarios (in git)

- `data/demo_scenarios/*.json` — hand-curated scenarios for demo and evaluation

### 7. Evaluation (in git)

- `data/evaluation/` — RAG evaluation dataset + benchmark results

## Rebuilding

Most processed data can be rebuilt from raw + scripts. See `scripts/README.md` for the build scripts.
