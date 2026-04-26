# M004 Kickoff — Corpus Reconciliation

## Entry state
- Branch: `milestone/M003-z2jh4m` at HEAD (T2b dormant)
- Main: last clean state (T2a shipped, T2b not yet merged)
- All tests green (361 backend, 196 frontend)
- No pending work on M003

## Mission
Reconcile all numeric claims shown in the dashboard UI. Demo-critical: the domain expert reads numbers. Inconsistency across tabs reads as "system doesn't know its own data."

## Known denominators (incomplete — audit will expand)
| Number | Source | Used in |
|--------|--------|---------|
| 156 | `data/rag/v2/datasets/incident_documents.csv` unique incident_ids | Hero narrative ("X of 156"), `DashboardView.tsx:29 RAG_CORPUS_INCIDENTS` |
| 174 | Apriori training corpus (source TBD — likely `out/association_mining/` or `/apriori-rules` endpoint) | Drivers & HF tab, Assessment Basis |
| 813 | `xgb_cascade_y_fail_metadata.json` `training_rows` | Provenance strip Line 1 |
| 530 | `data/processed/cascading_training.parquet` current row count | UI-CONTEXT.md §10 notes |
| 739 | `structured/incidents/schema_v2_3/` JSON count | CLAUDE.md session checkpoint |
| 558 | "LOC-scoped training rows" | CLAUDE.md |

## S01 — Audit
Produce `docs/evidence/architecture/denominators-audit.md` listing every numeric claim in every dashboard tab, its source file/line, the disk artifact that produced it, and which other numbers it should agree with.

## S02 — Decisions
For each inconsistency: unify, document, or hide. Output: decision records and reconciliation plan.

## S03 — Execute reconciliation
Code changes per S02 decisions.

## S04 — T2b gate (blocked on S03)
With numbers stable, run the 3-scenario browser gate. Flip flag or ship dark.
