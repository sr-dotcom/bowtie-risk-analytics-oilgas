# RAG v1 Archive

**Archived:** 2026-04-19

## Previous Scope

- **Incidents:** 526 (full corpus at time of v1 build)
- **Barrier controls:** 3,253
- **Source:** `data/evaluation/rag_workspace/` (now moved here)

## Reason for Archival

The canonical serving corpus has moved to `data/rag/v2/`, which is scoped to the
156 incidents in `data/processed/cascading_training.parquet` and includes D017
enhancements: recommendations and PIF value text are now embedded into the
incident documents, increasing semantic coverage for cascading failure queries.

## What Changed (v1 → v2)

| Dimension | v1 | v2 |
|-----------|----|----|
| Incident scope | 526 (all) | 156 (cascading training set) |
| Barrier rows | 3,253 | 1,161 |
| Embed text fields | top_event, type, phase, materials, summary | + recommendations + PIF value text (D017) |
| FAISS indexes | not present in v1 | barrier_faiss.bin + incident_faiss.bin |

## Reproduction

Re-run `python scripts/build_rag_v2.py` to regenerate the v2 artifacts.
The v1 corpus can be reconstructed by running `python -m src.pipeline corpus-extract`
against the full `data/structured/incidents/schema_v2_3/` directory without a scope filter.
