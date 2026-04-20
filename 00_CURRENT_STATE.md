# M003 Current State

Milestone: **M003-z2jh4m** — Cascading Pair-Feature Model + Scenario-Builder UI

## Slice Status

| Slice | Status | Commit |
|-------|--------|--------|
| S01 | ✓ | (prior milestone work) |
| S02 | ✓ | (prior milestone work) |
| S02b | ✓ | bb912c2 |
| S04 | ✓ | 9cd3a86 |
| **S03** | **✓** | 363dfdf (T01), c5cb13b (T02+T03), see T04 commit below |
| S05a | NEXT | — |

## S03 — Cascading API Endpoints

**T01** (`363dfdf`) — `src/modeling/cascading/predict.py`: CascadingPredictor with predict/rank/explain.  
**T02+T03** (`c5cb13b`) — Three new endpoints (POST /predict-cascading, /rank-targets, /explain-cascading) + 410 Gone for legacy /predict and /explain.  
**T04** — Integration test + API contract doc.

### What shipped in S03

- `CascadingPredictor` inference module: derives 18 cascade-pair features from demo-scenario JSON, runs the trained `xgb_cascade_y_fail_pipeline.joblib`, computes SHAP via `shap_probe.compute_shap_for_record`. Sorted predictions, risk bands from `configs/risk_thresholds.json` (p60=0.45, p80=0.70).
- Three new FastAPI endpoints loaded from RAGAgent v2 + CascadingPredictor (lifespan, graceful degradation).
- `/predict` and `/explain` converted to GET → HTTP 410 Gone with `migrate_to` hints.
- 44 new tests (13 T01 + 11 T02 + 9 T03 + 2 integration).
- `docs/api_contract.md` with curl examples, graceful degradation contract, error codes.
- D016 Branch C enforced: `y_hf_fail_probability` absent from all public API surfaces.

## Key Artifacts

| Artifact | Path |
|----------|------|
| Cascading pipeline | `data/models/artifacts/xgb_cascade_y_fail_pipeline.joblib` |
| Cascade metadata | `data/models/artifacts/xgb_cascade_y_fail_metadata.json` |
| Risk thresholds | `configs/risk_thresholds.json` |
| RAG v2 corpus | `data/rag/v2/` |
| API contract | `docs/api_contract.md` |
