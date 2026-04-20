# Scripts

One-shot utilities and maintenance tools. Each is runnable from the repo root with the project venv active.

## Corpus / data

- `build_rag_v2.py` — builds the RAG v2 corpus (barrier + incident documents, embeddings, FAISS indexes). Scoped to the 156-incident cascading training set. Outputs to `data/rag/v2/`.
- `build_demo_scenarios.py` — constructs demo scenario JSONs under `data/demo_scenarios/` from specific BSEE/CSB incident IDs.
- `extract_threat_barrier_pairs.py` — extracts threat-barrier pair rows from the V2.3 incident corpus for cascading model data prep.

## Model lifecycle

- `retrain_from_parquet.py` — retrains the cascading XGBoost model from `data/processed/cascading_training.parquet`. Writes updated artifacts to `data/models/artifacts/`.
- `verify_cascading_shap.py` — loads the trained y_fail pipeline and prints top-5 SHAP features for a sample input. Used to quickly sanity-check SHAP output after a retrain.
- `generate_risk_thresholds.py` — calibrates HIGH/MEDIUM/LOW risk tier cutoffs and writes `configs/risk_thresholds.json` (D006).
- `generate_apriori_rules.py` — mines co-failure association rules from the controls CSV and writes `data/models/artifacts/apriori_rules.json`.

## Evaluation

- `evaluate_retrieval.py` — runs the 50-query RAG retrieval benchmark and reports Top-k / MRR metrics.

## Association mining

- `association_mining/jsonaggregation.py` — JSON to aggregated incidents (standalone, not part of main pipeline)
- `association_mining/jsonflattening.py` — aggregated to flat barrier rows
- `association_mining/event_barrier_normalization.py` — 4-quadrant barrier family assignment (45 families)

## Archived scripts

- `archive/generate_audit_report.py` — generated ENGINEERING_AUDIT reports (superseded)
- `archive/generate_audit_docx.py` — Word document variant (superseded)
- `archive/generate_lessons_learned.py` — lessons-learned doc generation (superseded)

Run all scripts from the repo root with the virtual environment active:

```bash
source .venv/bin/activate
python3 scripts/<script_name>.py
```
