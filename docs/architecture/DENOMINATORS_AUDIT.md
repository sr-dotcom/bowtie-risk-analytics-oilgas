# Denominators Audit — M004/S01

**Audit date:** 2026-04-21  
**Branch:** `milestone/M003-z2jh4m` at `bd029a4`  
**Auditor flag:** `NEXT_PUBLIC_ENABLE_T2B_SYNTHESIS=false` (production surface; T2b synthesis button hidden)

---

## Audit Table

| Claim ID | Surface | Component:Line | Displayed Text | Claimed Value | Source File | Source Value | Match? | Reproducible? | Scope Description | Reconciles With |
|----------|---------|----------------|----------------|---------------|-------------|--------------|--------|---------------|-------------------|-----------------|
| C01 | Narrative Hero | NarrativeHero.tsx:269–272 | "This scenario has **N** barriers" | Runtime — `totalBarriers` prop = `barriers.length` | API response / BowtieContext | N/A | N/A | N/A | Count of barriers in current user scenario | C05 |
| C02 | Narrative Hero | NarrativeHero.tsx:295 | "**N** is/are high-risk" | Runtime — `highRiskCount` prop = barriers with riskLevel==='red' | API response / BowtieContext | N/A | N/A | N/A | Count of barriers above HIGH threshold (p≥0.70) | C09 |
| C03 | Narrative Hero | NarrativeHero.tsx:284–287 | "similar barriers failed in **N** of…" | Runtime — `similarIncidentsCount` = `new Set(evidence_snippets.map(s => s.incident_id)).size` | `/explain-cascading` response | N/A | N/A | N/A | Unique incidents among RAG-retrieved snippets for the top barrier | C04, C18 |
| C04 | Narrative Hero | DashboardView.tsx:29,107 | "…of **156** comparable incidents" | 156 — hardcoded `RAG_CORPUS_INCIDENTS = 156` | `data/rag/v2/datasets/incident_documents.csv` | **156 rows** | **YES** | YES — `scripts/build_rag_v2.py` regenerates from cascading corpus | Unique incidents in RAG v2 corpus | C03, C30 |
| C05 | Executive Summary — Analysis Overview KPI | DashboardView.tsx:158–159 | "**N** Barriers analyzed" | Runtime — `barriers.length` | BowtieContext | N/A | N/A | N/A | Count of barriers in current scenario | C01 |
| C06 | Executive Summary — Analysis Overview KPI | DashboardView.tsx:163–164 | "**N / M** Prevention / Mitigation" | Runtime — prevention/mitigation split | BowtieContext | N/A | N/A | N/A | Per-scenario prevention vs mitigation count | — |
| C07 | Executive Summary — Analysis Overview KPI | DashboardView.tsx:27,168–169 | "**174** Reference incidents" | 174 — hardcoded `TRAINING_INCIDENTS = 174` | `data/models/artifacts/feature_matrix.parquet` | **174 unique incident_ids** | **YES** | YES — `python -m src.modeling.feature_engineering` regenerates feature_matrix.parquet | Unique incidents in M002 LOC-scoped training set (XGBoost M002, not cascade M003) | C10 |
| C08 | Executive Summary — Analysis Overview KPI | DashboardView.tsx:28,172–173 | "**558** Barrier observations" | 558 — hardcoded `TRAINING_BARRIERS = 558` | `data/models/artifacts/feature_matrix.parquet` | **558 rows** | **YES** | YES — `python -m src.modeling.feature_engineering` | LOC-scoped barrier rows used for M002 model training | C11 |
| C09 | Executive Summary — Risk Posture card | DashboardView.tsx:145 | "**N** high · **N** medium · **N** low risk barriers" | Runtime — `counts.high / counts.medium / counts.low` from `buildRiskDistribution(barriers)` | BowtieContext | N/A | N/A | N/A | Per-scenario barrier risk level counts | C02 |
| C10 | Executive Summary — Assessment Basis | DashboardView.tsx:192 | "…analysis of **174 real BSEE/CSB incidents**…" | 174 — same as C07 (`TRAINING_INCIDENTS`) | `data/models/artifacts/feature_matrix.parquet` | **174 unique incident_ids** | **YES** | YES | Same as C07 — M002 training incidents | C07 |
| C11 | Executive Summary — Assessment Basis | DashboardView.tsx:194 | "…with **558 barrier observations**…" | 558 — same as C08 (`TRAINING_BARRIERS`) | `data/models/artifacts/feature_matrix.parquet` | **558 rows** | **YES** | YES | Same as C08 — M002 training barrier rows | C08 |
| C12 | BowtieSVG — per-barrier SHAP block | BowtieSVG.tsx:685–708 | `+N.NN` / `-N.NN` SHAP value labels (top 2 per barrier) | Runtime — `b.top_reasons[0..1].value.toFixed(2)` | `/predict-cascading` response | N/A | N/A | N/A | SHAP log-odds contribution from cascade model for this barrier pair | C28 |
| C13 | Ranked Barriers — header | RankedBarriers.tsx:311–312 | "Showing **N** of **M** barriers" | Runtime — filteredRows.length / rows.length | BowtieContext cascadingPredictions | N/A | N/A | N/A | Per-scenario filtered vs total barrier count | — |
| C14 | Ranked Barriers — per-row | RankedBarriers.tsx:363–378 | Risk pill label + probability column | Runtime — `p.y_fail_probability`, `p.risk_band` | `/predict-cascading` or `/rank-targets` response | N/A | N/A | N/A | Per-barrier-pair cascade failure probability | — |
| C15 | Ranked Barriers — SHAP factor | RankedBarriers.tsx:371–374 | `+N.NNN` / `-N.NNN` SHAP value | Runtime — `row.topFactorValue.toFixed(3)` | `/predict-cascading` response | N/A | N/A | N/A | Top SHAP log-odds contribution | C12 |
| C16 | Drivers & HF — Apriori table description | DriversHF.tsx:458–460 | "Based on Apriori analysis of **174** BSEE/CSB incident investigations." | 174 — hardcoded string literal (NOT a constant reference — raw text in JSX) | `data/evaluation/apriori_rules.json` → `metadata.n_incidents` | **723** | **NO — MISMATCH** | UNKNOWN (no regeneration script path confirmed) | Incidents analysed to generate the Apriori co-failure rules on disk | C07 [wrong reuse] |
| C17 | Drivers & HF — Apriori table rows | DriversHF.tsx:495–499 | confidence%, support%, lift, count per rule | Runtime — from `/apriori-rules` endpoint → `data/evaluation/apriori_rules.json` | `data/evaluation/apriori_rules.json` | 16 rules | N/A | UNKNOWN | Co-failure rule statistics from Apriori analysis of 723 incidents | — |
| C18 | Drivers & HF — Global SHAP chart | DriversHF.tsx:95–96 | Mean \|SHAP\| bar values (e.g. `0.123`) | Runtime — `buildGlobalShapData(predictions)` | BowtieContext | N/A | N/A | N/A | Mean absolute SHAP value per feature across current scenario barriers | — |
| C19 | Drivers & HF — PIF prevalence | DriversHF.tsx:263–265 | Prevalence percentage bars (e.g. `45%`) | Runtime — `buildPifPrevalenceData(predictions)` | BowtieContext | N/A | N/A | N/A | Fraction of barriers for which each PIF is a top-3 SHAP driver | — |
| C20 | Evidence tab | EvidenceView.tsx:130–131 | "Similar Incidents (**N**)" | Runtime — `snippets.length` (raw snippet count, not deduped by incident) | `/explain-cascading` response | N/A | N/A | N/A | Count of evidence snippets returned by RAG for the selected barrier | C03 [different dedup logic] |
| C21 | Evidence tab — per-snippet | EvidenceView.tsx:145 | "score: **N.NN**" | Runtime — `s.score.toFixed(2)` | `/explain-cascading` response | N/A | N/A | N/A | RRF retrieval score for this snippet | — |
| C22 | Provenance strip — Line 1 | **NOT IMPLEMENTED** | "Predictions: XGBoost cascade · **813** rows from **156** BSEE+CSB incidents · 5-fold CV AUC **0.76** ± **0.07**" | Specified in UI-CONTEXT.md §10; no frontend component renders it | `data/models/artifacts/xgb_cascade_y_fail_metadata.json` | training_rows=813, cv_scores mean=0.763, std=0.066 | N/A — not rendered | NO (813 pair-matrix ephemeral; spec values traceable) | M003 cascade model training provenance | — |
| C23 | Provenance strip — Line 2 | **NOT IMPLEMENTED** | "Evidence: hybrid RAG · **1,161** barriers · **156** incidents · 4-stage retrieval" | Specified in UI-CONTEXT.md §10; no frontend component renders it | `data/rag/v2/datasets/barrier_documents.csv`, `incident_documents.csv` | 1161 rows, 156 rows | N/A — not rendered | YES | RAG v2 corpus extent | C04 |
| C24 | Drill-down panel — model baseline | DetailPanel.tsx:292 | "Model baseline (avg. across all barriers): **N.NNN**" | Runtime — `pred.model1_base_value.toFixed(3)` | `/predict` or `/predict-cascading` response | N/A | N/A | N/A | SHAP base value (log-odds) from the loaded XGBoost model | — |
| C25 | Drill-down panel — risk score | DetailPanel.tsx (RiskScoreBadge) | Probability percentage display | Runtime — `pred.model1_probability` or `targetPred.y_fail_probability` | API response | N/A | N/A | N/A | Per-barrier failure probability | C14 |
| C26 | Drill-down panel — SHAP factors | DetailPanel.tsx:297–312 | Factor name + `+N.NNN` / `-N.NNN` | Runtime — top SHAP values | API response | N/A | N/A | N/A | Per-barrier SHAP contributions | C12, C15 |
| C27 | Drill-down panel — Similar Incidents | DetailPanel.tsx:130–131 | "Similar Incidents (**N**)" | Runtime — `snippets.length` | `/explain-cascading` response | N/A | N/A | N/A | Raw snippet count (not deduped) | C20 |

---

## Surfaces with No Static Numeric Claims

- **BowtieSVG risk badges (H/M/L letters)** — categorical, not numeric
- **RiskScoreBadge ring** — visual only; the number shown is runtime probability (C25)
- **ScenarioContext** — text description, no numbers
- **DegradationContextPanel** — PIF tags and recommendation text, no static numbers

---

## Findings

### F1 — Mismatch: Apriori "174" vs actual source "723" (Claim C16)

`DriversHF.tsx:459` contains a hardcoded string: `"Based on Apriori analysis of 174 BSEE/CSB incident investigations."` The number 174 is a raw text literal — not the constant `TRAINING_INCIDENTS`.

The actual source file (`data/evaluation/apriori_rules.json`) has `metadata.n_incidents: 723`. The 174 from `TRAINING_INCIDENTS` refers to the M002 LOC-scoped training set (feature_matrix.parquet, 174 unique incidents), which is a different dataset with a different scope and purpose from the Apriori analysis.

**Effect:** Every visitor to the Drivers & HF tab sees a citation that is wrong by a factor of ~4×. The claim is that co-failure rules were derived from 174 incidents; they were actually derived from 723 incidents.

**Resolution required before demo.** See Decision A in M004-kickoff.md.

---

### F2 — 813 pair-matrix is not on disk (Claims C22/C23 — provenance strip)

The UI-CONTEXT.md §10 provenance strip specifies "813 rows from 156 BSEE+CSB incidents" as Line 1. The 813 figure is correctly sourced (`xgb_cascade_y_fail_metadata.json` `training_rows`). However:

- The 813-row pair-feature training matrix was generated ephemerally by `src/modeling/cascading/pair_builder.py` and not persisted to disk.
- The current `cascading_training.parquet` has 530 rows (single-barrier, not pair-feature).
- The base input CSV (`data/models/cascading_input/barrier_model_dataset_base_v3.csv`) has 552 rows.
- None of these reconstitute the exact 813-row matrix.

The model **cannot be exactly reproduced** from committed artifacts — `pair_builder.py` run against the current 552-row CSV will not produce 813 rows (the base data has since evolved).

Additionally: **the provenance strip is not implemented in any frontend component.** The spec exists in UI-CONTEXT.md §10 but no `.tsx` file renders it. The 813 number does not appear in the production UI at all currently.

---

### F3 — Scope mismatch on same screen: C07/C10 (174, M002) vs C04 (156, M003 cascade)

The Executive Summary tab shows both:
- "Reference incidents: **174**" (Analysis Overview KPI card, from M002 feature_matrix)  
- "…of **156** comparable incidents" (Narrative Hero denominator, from RAG v2 / M003 cascade corpus)

These are correct for their respective scopes — M002 trained on 174 incidents; M003/RAG uses 156 — but they appear on the same tab with no label distinguishing which corpus each refers to. A domain expert reads both numbers in the same view and sees inconsistency.

The Assessment Basis block compounds this: it says "analysis of **174 real BSEE/CSB incidents**" using `TRAINING_INCIDENTS`, which describes the M002 model, but the dashboard is now running the M003 cascade model (trained on 156 incidents). The Assessment Basis copy is describing the wrong model.

---

### F4 — Snippet count vs unique-incident count used inconsistently (Claims C03 vs C20/C27)

The Narrative Hero uses `new Set(evidence_snippets.map(s => s.incident_id)).size` — deduped by incident_id.

The Evidence tab header (`EvidenceView.tsx:130`) and Drill-down panel (`DetailPanel.tsx:130`) both use `snippets.length` — raw snippet count, not deduped.

If 5 snippets come from 3 incidents: Hero shows "3 of 156"; Evidence tab shows "Similar Incidents (5)". This is technically correct per scope but will confuse a domain expert reading both surfaces.

---

### F5 — Duplicate apriori_rules.json on disk

Two copies of the same file:
- `data/evaluation/apriori_rules.json` — loaded by API (`src/api/main.py:153`)
- `data/models/artifacts/apriori_rules.json` — not loaded by any active code path

Both have identical content (16 rules, `n_incidents: 723`, same `generated_at`). The `data/models/artifacts/` copy is dead weight. Canonical path is `data/evaluation/`.

---

### F6 — ModelKPIs component exists but is not rendered (dead code)

`frontend/components/dashboard/ModelKPIs.tsx` defines 4 KPI cards (F1=0.928, MCC=0.793, F1=0.348, MCC=0.266) that correctly trace to `data/models/evaluation/training_report.json`. However, `ModelKPIs` is **not imported in any active component** — it is dead code and does not appear in the production UI.

These M002 model metrics (from the non-cascade LogReg/XGBoost models) would be misleading on the current dashboard anyway, since the production model is now the M003 cascade XGBoost (CV AUC 0.76 ± 0.07, not F1=0.928).

---

### F7 — T2b vs production render difference (flag-dependent numbers)

When `NEXT_PUBLIC_ENABLE_T2B_SYNTHESIS=true` (dev local), the Narrative Hero renders a "✨ Summarize with AI" button. On synthesis success, the template body (`totalBarriers`, `highRiskCount`, `similarIncidentsCount`, `totalRetrievedIncidents`) is **replaced** by the Haiku-generated synthesis text. The synthesis text may reference numbers inconsistently with what the template would show (e.g., Haiku may state "5 of 156" while the template context has `similarIncidentsCount=3`). This audit covers the production render (flag OFF — template only). T2b synthesized output is non-deterministic and not audited here.

---

## Numeric Summary

| Unique Value | Traced Source | Status |
|-------------|---------------|--------|
| 156 (RAG corpus) | `data/rag/v2/datasets/incident_documents.csv` row count | Verified on disk ✓ |
| 174 (M002 training incidents) | `data/models/artifacts/feature_matrix.parquet` unique incident_ids | Verified on disk ✓ — but misapplied in Apriori description (F1) |
| 558 (M002 training barriers) | `data/models/artifacts/feature_matrix.parquet` row count | Verified on disk ✓ |
| 530 (current cascade parquet) | `data/processed/cascading_training.parquet` row count | Verified on disk ✓ |
| 813 (cascade training pairs) | `data/models/artifacts/xgb_cascade_y_fail_metadata.json` training_rows | Metadata only — source matrix not on disk ✗ |
| 723 (Apriori incidents) | `data/evaluation/apriori_rules.json` metadata.n_incidents | Verified on disk ✓ — not shown in UI |
| 1161 (RAG barriers) | `data/rag/v2/datasets/barrier_documents.csv` row count | Verified on disk ✓ — spec'd for provenance strip, not yet rendered |
| 739 (schema_v2_3 JSONs) | `data/structured/incidents/schema_v2_3/*.json` file count | Verified on disk ✓ — not shown in UI |
| 16 (Apriori rules) | `data/evaluation/apriori_rules.json` rules array length | Verified on disk ✓ — rendered via API (no static claim) |

**Total UI claims audited:** 27 (C01–C27)  
**Static/hardcoded claims:** 9 (C04, C07, C08, C10, C11, C16, C17 header, C22, C23)  
**Runtime/API-derived claims:** 18  
**Static claims with mismatch (Match=NO):** 1 (C16 — Apriori 174 vs 723)  
**Spec'd but unimplemented surfaces:** 1 (provenance strip, C22/C23)
