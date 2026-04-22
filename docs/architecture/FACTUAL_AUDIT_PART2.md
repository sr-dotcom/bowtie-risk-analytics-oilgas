# Factual Audit Part 2 — Claims Beyond Numeric Denominators

**Run date:** 2026-04-21  
**Branch:** `milestone/M003-z2jh4m`  
**HEAD:** `7f42f14` (docs(M004/S01): denominators audit and draft registry)  
**Builds on:** `docs/architecture/DENOMINATORS_AUDIT.md` (commit `7f42f14`)  
**Auditor:** Claude Code CLI — read-only session  
**Scope:** Handoff v1.0 claims in Categories A (gap), B (gap), C, D, E, F, G

---

## Summary

- **Total claims checked:** 49
- **AGREE:** 23
- **DISAGREE:** 15
- **CANNOT VERIFY:** 4
- **NEEDS HUMAN JUDGMENT:** 2
- **SHIPPED-UI:** 7
- **SHIPPED-CODE-ONLY:** 2

---

## Full Ledger

| Claim ID | Claim (compressed) | Verdict | Ground truth | Source path | Notes |
|---|---|---|---|---|---|
| A2 | 4 agencies: BSEE, CSB, PHMSA, TSB across 739 V2.3 JSONs | **DISAGREE** | 3 categories: BSEE=624, CSB=73, UNKNOWN=42. No PHMSA or TSB. | `data/processed/flat_incidents_combined.csv` col `source_agency` | `source.agency` absent from all 739 raw JSONs (by design); inferred via doc_type→URL→path→UNKNOWN. PHMSA/TSB incidents not yet extracted into V2.3. |
| A2a | Cascade subset: 113 BSEE + 43 CSB | **DISAGREE** | 113 BSEE + 19 CSB + 24 UNKNOWN = 156 total. CSB count is 19, not 43. | Cross-ref `data/models/cascading_input/barrier_model_dataset_base_v3.csv` incident_ids → `flat_incidents_combined.csv` source_agency | 24 cascade incidents resolve as UNKNOWN; some may be CSB but cannot be confirmed via current resolution logic. |
| B9 | y_hf_fail metadata artifact exists | **AGREE** | `xgb_cascade_y_hf_fail_metadata.json` and `xgb_cascade_y_hf_fail_pipeline.joblib` both present | `data/models/artifacts/` | `s02b_note: "production surface dropped per D016 Branch C"` |
| B10 | y_hf_fail mean AUC = 0.556 | **AGREE** | `cv_scores.mean = 0.556171` → rounds to 0.556 | `data/models/artifacts/xgb_cascade_y_hf_fail_metadata.json` | |
| B11 | y_hf_fail std = 0.118 | **AGREE** | `cv_scores.std = 0.118248` → rounds to 0.118 | `data/models/artifacts/xgb_cascade_y_hf_fail_metadata.json` | |
| B12 | y_hf_fail fold 3 = 0.401 | **AGREE** | `cv_scores.per_fold[2] = 0.400947` → rounds to 0.401 | `data/models/artifacts/xgb_cascade_y_hf_fail_metadata.json` | |
| C-API-1 | Active endpoints exactly 5: POST /predict-cascading, POST /rank-targets, POST /explain-cascading, GET /apriori-rules, GET /health | **DISAGREE** | 6 active endpoints. Missing from handoff list: `POST /narrative-synthesis`. Full list: GET /health, GET /apriori-rules, POST /predict-cascading, POST /rank-targets, POST /explain-cascading, POST /narrative-synthesis. Plus GET /predict and GET /explain (both 410 Gone). | `src/api/main.py` lines 254–505 | `/narrative-synthesis` is the T2b endpoint (NarrativeSynthesisResponse). |
| C-API-2 | /predict and /explain return 410 Gone with migrate_to field | **AGREE** | Both return `status_code=410` with `GoneResponse(migrate_to=...)`. `/predict` → migrate_to `/predict-cascading`; `/explain` → migrate_to `/explain-cascading` | `src/api/main.py` lines 251–278 | |
| C-API-3 | /explain-cascading response has snippet_count and unique_incident_count fields (D-M004-03 landed) | **DISAGREE** | ExplainCascadingResponse has: `narrative_text`, `evidence_snippets`, `degradation_context`, `narrative_unavailable`. No `snippet_count` or `unique_incident_count` fields. D-M004-03 has **NOT** landed. | `src/api/schemas.py` line 314 | D-M004-03 is a planned addition, not yet implemented. |
| C-API-4 | /apriori-rules response has n_incidents and generated_at top-level fields (D-M004-01 landed) | **DISAGREE** | AprioriRulesResponse has only `rules: list[AprioriRule]`. No `n_incidents` or `generated_at` fields. D-M004-01 has **NOT** landed. | `src/api/schemas.py` line 231 | The actual apriori_rules.json has `n_incidents=723` and `generated_at` but these are not surfaced via the API schema. |
| C-API-5 | BOWTIE_API_KEY fail-closed in non-development | **AGREE** | Startup (line 125): `if os.getenv("BOWTIE_API_KEY") is None and os.getenv("ENVIRONMENT","development") != "development": raise RuntimeError(...)`. `verify_api_key` passthrough only when key unset. | `src/api/main.py` lines 125–203 | Dev environment (default) intentionally open. Production requires key. |
| C-API-6 | GET /health includes model_loaded, rag_loaded, rag_corpus_size | **NEEDS HUMAN JUDGMENT** | HealthResponse has: `status: str`, `models: dict[str, ModelInfo]` (ModelInfo.loaded=bool), `rag: RagInfo` (RagInfo.corpus_size=int), `uptime_seconds: float`. Named fields differ from claim but semantically equivalent. `model_loaded` ≈ `models[*].loaded`, `rag_corpus_size` ≈ `rag.corpus_size`. No flat `rag_loaded` bool exists. | `src/api/schemas.py` lines 47–68 | |
| D-FE-1 | Scenario builder is primary UX (L001), not a 4-tab incident viewer | **NEEDS HUMAN JUDGMENT** | No component named `ScenarioBuilder` exists. Primary UX is `BowtieApp` rendering `BarrierForm` (sidebar) + `BowtieSVG` + `DashboardView`. "Scenario builder" functionality is in `BarrierForm` (barriers + top event entry). BowtieApp comment: "will be user-enterable later" for threats/consequences. 4-tab DashboardView is still present in production render path. | `frontend/components/BowtieApp.tsx`, `frontend/app/page.tsx` | Claim may use "scenario builder" as a UX concept description, not a component name. |
| D-FE-2 | M002 4-tab dashboard components deleted from production render paths | **DISAGREE** | 4-tab DashboardView (Executive Summary, Drivers & HF, Ranked Barriers, Evidence) IS the active production UI. Components are updated/reused for M003 data, not deleted. `BowtieApp.tsx:160`: `<DashboardView />` in active render path. | `frontend/components/BowtieApp.tsx:160`, `frontend/components/dashboard/DashboardView.tsx:19–22` | |
| D-FE-3 | BowtieSVG is custom SVG, not React Flow | **AGREE** | BowtieSVG uses raw SVG elements (`<svg>`, `<rect>`, `<path>`, `<circle>`, `<g>`, `<line>`). No `reactflow` import. | `frontend/components/diagram/BowtieSVG.tsx` | |
| D-FE-4 | Provenance strip component EXISTS in frontend (may be unrendered) | **DISAGREE** | No `Provenance` or `provenance` component file found anywhere in `frontend/components/`. Zero grep hits for "Provenance" or "provenance" in component tree. The spec in UI-CONTEXT.md §10 is not implemented. | `frontend/components/` (recursive search) | Confirmed by prior DENOMINATORS_AUDIT.md F2: provenance strip unimplemented. |
| D-FE-5 | NarrativeHero exists with T2a template rendering | **AGREE** | File exists. Line 252 comment: "Template composition — per UI-CONTEXT.md §9 (T2a path)". Template uses "historical" language at lines 277–298. T2a is the default render path when T2b flag is off. | `frontend/components/dashboard/NarrativeHero.tsx:252–298` | |
| D-FE-6 | T2b flag defaults to OFF in committed env files | **CANNOT VERIFY** | Only committed env file is `.env.example` (root) which contains no `NEXT_PUBLIC_ENABLE_T2B_SYNTHESIS`. The flag exists only in `frontend/.env.local` (gitignored, present locally with `=false`). No production env file commits this value. | `git ls-files` → `.env.example` only. `frontend/.env.local` is gitignored. | The flag is gitignored by convention. Cannot assert a committed production default. |
| D-FE-7 | Frontend Vitest test count = 196 | **AGREE** | `npx vitest list` from `frontend/` collects 196 test cases. | `frontend/__tests__/` | |
| D-FE-8 | Backend pytest test count = 566 collected (565 passing + 1 skipped) | **DISAGREE** | `pytest --collect-only -q tests/` collects **638** tests. Difference of +72 vs claimed 566. | `tests/` | Tests were likely added post-handoff freeze. Claimed 566 matches prior DENOMINATORS_AUDIT count (352 was an earlier snapshot). 638 is current state. |
| D-FE-9 | Dashboard tabs: list actual tab set | **AGREE** | 4 tabs in order: Executive Summary · Drivers & HF · Ranked Barriers · Evidence | `frontend/components/dashboard/DashboardView.tsx:19–22` | |
| E2 | Historical framing (no "AI predicts" / "probability of failure" standalone) | **AGREE / SHIPPED-UI** | NarrativeHero template: "historical data shows {historicalClause}" (line 297–298). No "AI predicts" or standalone probability-of-failure phrasing in template path. Evidence-grounded framing confirmed. | `frontend/components/dashboard/NarrativeHero.tsx:277–298` | |
| E6 | Prevention AND mitigation both accepted | **AGREE / SHIPPED-UI** | BarrierForm state: `const [side, setSide] = useState<'prevention' \| 'mitigation'>('prevention')` with toggle buttons (lines 121–133). BowtieSVG renders both sides (left/right path arrays). | `frontend/components/sidebar/BarrierForm.tsx:42–133`, `frontend/components/diagram/BowtieSVG.tsx` | |
| E9 | HIGH/MED/LOW not raw probability as primary display | **AGREE / SHIPPED-UI** | RankedBarriers primary table column shows categorical pill labels (`PILL_LABELS[row.riskLevel]` = "High"/"Medium"/"Low"). Raw probability shown only in expanded row via `RiskScoreBadge`. | `frontend/components/dashboard/RankedBarriers.tsx:341–413` | Both `riskBandToLevel` (from API `risk_band`) and `configs/risk_thresholds.json` (via API) drive tier classification. |
| E12 | Pathway-aware conditioning barrier | **AGREE / SHIPPED-UI** | (a) Cascade model features include `pathway_sequence_target` and `pathway_sequence_cond`. (b) API `CascadingRequest.conditioning_barrier_id` accepted. (c) "What if fails?" button in RankedBarriers (line 400) sets `conditioningBarrierId`, which re-triggers `/predict-cascading`. | `data/models/artifacts/xgb_cascade_y_fail_metadata.json`, `src/api/schemas.py:247`, `frontend/components/dashboard/RankedBarriers.tsx:384–401` | |
| E30 | Ranking criteria defined and visible to user | **SHIPPED-CODE-ONLY** | Only user-visible text: "All Barriers Ranked by Risk" (h3, line 257). No tooltip, no criteria prose, no methodology reference visible in UI. Code comment (line 70) says "ranked by failure probability" but this is developer-facing only. No CCPS reference, no model card link, no ranking explanation. | `frontend/components/dashboard/RankedBarriers.tsx:257` | Criteria known in code but not surfaced to domain expert. |
| E34 | Industry standards via event.recommendations | **AGREE / SHIPPED-UI** | ContextBuilder `_format_entry` includes `**Recommendations:**` block from `entry.recommendations` (lines 37–38). API `/explain-cascading` populates `DegradationContext.recommendations` from incident metadata (main.py lines 468–495). `EvidenceSection.tsx` line 126 parses `ev.recommendations`. Visible to user. | `src/rag/context_builder.py:37–38`, `src/api/main.py:468–495`, `frontend/components/panel/EvidenceSection.tsx:125–127` | |
| E41 | barrier_status has exactly 6 values | **AGREE** | Schema Literal: `"active", "degraded", "failed", "bypassed", "not_installed", "unknown"` = 6 values. Note: V2.3 conversion changed `active→worked` in CLAUDE.md docs but the Pydantic model retains `"active"`. | `src/models/incident_v23.py:199–201` | UI (DetailPanel/RankedBarriers) does not directly display the barrier_status string from the schema — `risk_band` (HIGH/MEDIUM/LOW) is the UI-facing status indicator. |
| E45 | PIF _value text in RAG context | **DISAGREE** | `context_builder.py` does NOT include PIF `_value` text from the V2.3 `pifs.{people\|work\|organisation}.*._value` fields. `ContextEntry` has `human_contribution_value: str` (from ControlHuman, one field) and `barrier_failed_human: bool` — not the 12 per-incident PIF text strings. D017 **planned** this but the implementation gap remains. | `src/rag/context_builder.py` (full file: no `_value` PIF fields in ContextEntry dataclass) | HIGH SUSPICION claim confirmed. D017 describes future intent ("Corpus builder ingests both") but is not yet executed. |
| E55 | 5-category barrier taxonomy DEFERRED; schema has 4 | **AGREE** | Schema Literal: `"engineering", "administrative", "ppe", "unknown"` = 4 values. `barrier_types.yaml` defines 5 categories (incl. `human_hardware_hybrid` with comment `# Comment #55`) but `human_hardware_hybrid` is NOT in the Pydantic Literal — cannot be stored in V2.3 JSONs. Deferral notice is in `configs/mappings/barrier_types.yaml` header comment and referenced in DECISIONS.md D008. Not a user-facing limitation notice in README. | `src/models/incident_v23.py:247`, `configs/mappings/barrier_types.yaml` | |
| E56 | 11-category CCPS LoD | **AGREE (model)** | `lod_industry_standard` has exactly 11 unique values in training CSV: Alarm and Operator Response · Detection Systems · Emergency Response · Other · Pressure Relief Systems · Process Containment · Process Control · Protection Systems · Safety Instrumented Systems · Shutdown Systems · Structural Integrity. UI status: `CascadingBarrierPrediction` schema does NOT include `lod_display` or `lod_industry_standard`. DetailPanel checks `pred.lod_display` but this field is absent from the cascading prediction schema; falls back to `undefined`. | `data/models/cascading_input/barrier_model_dataset_base_v3.csv` col `lod_industry_standard`, `src/api/schemas.py:CascadingBarrierPrediction` | SHIPPED-CODE-ONLY: 11-category label is in training data but NOT surfaced in /predict-cascading response. |
| E59 | 45 barrier families | **DISAGREE** | Script defines **46** barrier families (46 dict keys with `"key": [...]` pattern). All 46 listed in evidence below. | `scripts/association_mining/event_barrier_normalization.py` (grep: `"([^"]+)"\s*:\s*\[` → 46 matches) | Off by one. Exact count is 46. UI: `barrier_family` field exists in BarrierPrediction (M002) but NOT in `CascadingBarrierPrediction` — families not surfaced in cascading mode. |
| E61 | Full bowtie construction (hazards, threats, top event, consequences, barriers) | **DISAGREE** | Only 2 of 5 inputs are user-enterable: **top event** (text input in BarrierForm line 107–109) and **barriers** (add form). Hazards, threats, consequences are **hardcoded** constants: `DEMO_THREATS`, `DEMO_CONSEQUENCES`, `hazardName="High-pressure gas"`. BowtieApp comment: "Demo threats and consequences (hardcoded — will be user-enterable later)". | `frontend/components/BowtieApp.tsx:14–27, line 218` | |
| E63 | Threats/events/pathways in ranking: top_event_category + threat-linkage features + pathway_sequence | **DISAGREE** | Cascade model features include `pathway_sequence_target/cond` ✓ and threat-class flags `flag_environmental_threat, flag_electrical_failure, flag_procedural_error, flag_mechanical_failure` ✓. **`top_event_category` is NOT in the feature list.** Not in xgb_cascade_y_fail_metadata.json all_features (18 features). | `data/models/artifacts/xgb_cascade_y_fail_metadata.json` `all_features` | 2 of 3 sub-claims verified; top_event_category absent. D008 rationale says "threat-based" was addressed but via threat-class flags, not a top_event_category feature. |
| E64 | Real RAG evidence, not synthetic | **AGREE / SHIPPED-UI** | `src/rag/explainer.py` builds prompt from template substituting `{rag_context}` (retrieved snippets). LLM call via `AnthropicProvider.extract()` takes real snippets as context. No synthetic-only path. | `src/rag/explainer.py:130, 209–230` | |
| F-D-1 | DECISIONS.md has D001–D019, no gaps | **AGREE** | D001–D015 in table format. D016–D019 as `## D0NN —` section headers. All present, no gaps in sequence. | `docs/decisions/DECISIONS.md` | |
| F-D-2 | D-M004-01 through D-M004-06 present in DECISIONS.md | **DISAGREE** | DECISIONS.md ends at **D019**. No D-M004-XX entries exist. The file has 82 lines total. D-M004 decisions appear in handoff as claimed/planned but were **never appended** to DECISIONS.md. | `docs/decisions/DECISIONS.md` (full file, line count 82) | |
| F-D-3 | No D-entry mutated since its first commit | **CANNOT VERIFY** | Only 1 commit for DECISIONS.md in git log: `469bc93 chore(cleanup)`. The entire file was added/touched in one commit. Mutation detection requires at least 2 commits; cannot isolate per-entry history. Structural review shows consistent table then section-header format consistent with append-only — no obvious mutations. | `git log --oneline --follow docs/decisions/DECISIONS.md` | |
| F-D-4 | D019 explicitly supersedes D016 branch definitions | **AGREE** | D019 heading: "S02b branch activation logic corrected to strict total-ordering (**supersedes D016 branch definitions**)". Supersedes clause is verbatim. | `docs/decisions/DECISIONS.md:65` | |
| F-D-5 | D012 authority: Prof Ageenko=supervisor, Fidel=evaluator, GNSR=lead, Jeffrey+Patrick=teammates | **AGREE** | D012 verbatim: "Prof. Ageenko = professor/supervisor; Fidel Ilizastigui Perez = domain expert evaluator; Naga Sathwik Reddy Gona (GNSR) = project lead + primary engineer; Jeffrey Arnette = teammate; Patrick Hunter = teammate" | `docs/decisions/DECISIONS.md:D012 row` | |
| G-AR-1 | L0 never imported by L2 modeling or API code | **AGREE** | Zero references to `data/raw/` in `src/modeling/` or `src/api/`. | `grep -rn "data/raw" src/modeling/ src/api/` → 0 hits | |
| G-AR-2 | Cascading training reads from L2 only | **AGREE** | `data_prep.py` reads `data/models/cascading_input/barrier_model_dataset_base_v3.csv`. `train.py` reads `data/processed/cascading_training.parquet`. Neither touches raw. | `src/modeling/cascading/data_prep.py:78–112`, `src/modeling/cascading/train.py:33, 128` | |
| G-AR-3 | get_controls() is single source of truth for control extraction | **DISAGREE** | `get_controls()` does NOT exist in `src/ingestion/structured.py` (grep returns 0 hits across entire src/). `src/analytics/flatten.py:40` directly accesses `incident.get("bowtie", {}).get("controls", [])`. The CLAUDE.md assertion is outdated or aspirational. | `src/ingestion/structured.py` (no `def get_controls` found), `src/analytics/flatten.py:40` | |
| G-AR-4 | All joblib.dump targets data/models/artifacts/ | **AGREE** | Four joblib.dump call sites: `train.py:265` (logreg_path), `feature_engineering.py:268` (encoder_path), `cascading/hf_recovery.py:408` (`_ARTIFACTS_DIR/xgb_cascade_y_hf_fail_pipeline.joblib`), `cascading/train.py:152` (`_ARTIFACTS_DIR/...`). All resolve to `data/models/artifacts/`. | `src/modeling/train.py:265`, `src/modeling/feature_engineering.py:268`, `src/modeling/cascading/hf_recovery.py:31–408`, `src/modeling/cascading/train.py:34–152` | |
| G-AR-5 | src/_legacy/ still imported by production modules | **AGREE** | **7 import lines across 4 files:** `src/analytics/__init__.py:1` (engine), `src/ingestion/loader.py:3` (incident), `src/pipeline.py:27–29` (incident, bowtie, engine), `src/models/__init__.py:3–4` (incident, bowtie). | `grep -rn "from src._legacy\|import src._legacy" src/ --include='*.py' \| grep -v _legacy/` | Architecture freeze rule says "avoid in active code" — violation exists and is pre-existing. |
| G-AR-6 | SHAP_HIDDEN_FEATURES includes source_agency | **DISAGREE** | `SHAP_HIDDEN_FEATURES = new Set(['primary_threat_category'])` — only one entry, source_agency is **absent**. source_agency was dropped from model features per D005 and does not appear in SHAP output for any model, so no filtering is needed or present. | `frontend/lib/shap-config.ts:13` | The absence is architecturally correct (source_agency is not a feature), but the handoff claim is false. |

---

## Detailed Findings for Disagreements

### DISAGREE #1 — A2 (Source Agency Count)

**Claim source:** Handoff v1.0 §3 / CLAUDE.md "4 source agencies: BSEE, CSB, PHMSA, TSB"  
**Claim verbatim:** "Exactly 4 source agencies across all 739 V2.3 JSONs: BSEE, CSB, PHMSA, TSB"  
**Ground truth:** 3 resolved categories — BSEE: 624, CSB: 73, UNKNOWN: 42. Total: 739. No PHMSA or TSB incidents exist in `data/structured/incidents/schema_v2_3/`.  
**Evidence:** `data/processed/flat_incidents_combined.csv` `source_agency` column; all 739 V2.3 JSON `source.agency` fields are absent (confirmed by Python scan — 739/739 return "MISSING" for `source.agency`). Source resolution falls back to path/doc_type logic, producing only BSEE/CSB/UNKNOWN.  
**Suspected cause:** PHMSA and TSB appear in `configs/sources/` discovery config but have not been extracted to V2.3 JSON yet. Architecture supports 4 sources; only 2 are populated.  
**Demo-day impact:** LOW — this claim doesn't appear in the demo UI. Background documentation accuracy only.  
**Recommended action:** Update handoff v1.1 to say "2 active agencies (BSEE + CSB); PHMSA/TSB configured but not yet extracted."

---

### DISAGREE #2 — A2a (Cascade Subset Agency Breakdown)

**Claim source:** Handoff v1.0 §4  
**Claim verbatim:** "113 BSEE + 43 CSB"  
**Ground truth:** 113 BSEE + 19 CSB + 24 UNKNOWN = 156 total.  
**Evidence:** Cross-reference `barrier_model_dataset_base_v3.csv` incident IDs against `flat_incidents_combined.csv` `source_agency`. 24 cascade incidents resolve as UNKNOWN.  
**Suspected cause:** Some Patrick-curated incidents (base_v3.csv) have file paths that don't match the BSEE/CSB path-segment heuristics → UNKNOWN. The "43 CSB" may have counted UNKNOWN incidents as CSB.  
**Demo-day impact:** LOW — cascade subset breakdown doesn't appear in demo UI.  
**Recommended action:** Confirm post-Apr-27 by auditing the 24 UNKNOWN cascade incidents manually.

---

### DISAGREE #3 — C-API-1 (Active Endpoint Count)

**Claim source:** Handoff v1.0 §7 API Surface  
**Claim verbatim:** "Active endpoints exactly: POST /predict-cascading, POST /rank-targets, POST /explain-cascading, GET /apriori-rules, GET /health"  
**Ground truth:** 6 active endpoints. Missing: `POST /narrative-synthesis` (NarrativeSynthesisResponse, line 505 in main.py). Confirmed by `@app.post`/`@app.get` decorator scan.  
**Evidence:** `src/api/main.py` lines 254–505 — 5 named endpoints + 2 deprecated (410) + 1 unlisted (`/narrative-synthesis`).  
**Suspected cause:** T2b synthesis endpoint was added during S05/S06 development after handoff was frozen, or was considered internal/non-public.  
**Demo-day impact:** LOW — narrator is unlikely to enumerate endpoint names verbally. Internal inconsistency.  
**Recommended action:** Add `/narrative-synthesis` to handoff v1.1 endpoint table.

---

### DISAGREE #4 — C-API-3 (ExplainCascadingResponse Fields)

**Claim source:** Handoff v1.0 §7, D-M004-03  
**Claim verbatim:** "/explain-cascading response schema has `snippet_count` and `unique_incident_count` fields"  
**Ground truth:** ExplainCascadingResponse has: `narrative_text`, `evidence_snippets`, `degradation_context`, `narrative_unavailable`. No `snippet_count` or `unique_incident_count`.  
**Evidence:** `src/api/schemas.py:314–321`.  
**Suspected cause:** D-M004-03 was written as a forward intent in M004 planning. It was presented in the handoff as "landed" but the code has not been updated.  
**Demo-day impact:** MEDIUM — if Fidel or Prof Ageenko asks "how many similar incidents were found?", the API doesn't expose the count as a clean field; the frontend counts from `evidence_snippets.length` or deduped incident_ids. The narrative hero shows it correctly but there's no structured field.  
**Recommended action:** Implement D-M004-03 (add fields to response) pre-Apr-24 if the demo will cite these numbers, or label as M004 backlog in handoff.

---

### DISAGREE #5 — C-API-4 (AprioriRulesResponse Fields)

**Claim source:** Handoff v1.0 §7, D-M004-01  
**Claim verbatim:** "/apriori-rules response has `n_incidents` and `generated_at` top-level fields"  
**Ground truth:** `AprioriRulesResponse` has only `rules: list[AprioriRule]`. The actual JSON file has `n_incidents=723` and `generated_at` but these are not in the API schema.  
**Evidence:** `src/api/schemas.py:231–234`.  
**Suspected cause:** D-M004-01 is forward intent; not yet implemented.  
**Demo-day impact:** MEDIUM — if demo shows Apriori table provenance (as per DENOMINATORS_AUDIT F1 fix), the n_incidents value needs to come from the API. Currently it's hardcoded incorrectly as 174 in the frontend (see C16 in DENOMINATORS_AUDIT).  
**Recommended action:** Implement D-M004-01 (add fields to schema, populate from JSON) and fix the DriversHF.tsx 174→723 bug together.

---

### DISAGREE #6 — D-FE-2 (M002 Dashboard Deleted)

**Claim source:** Handoff v1.0 §8 Frontend Reality  
**Claim verbatim:** "M002 4-tab dashboard components are deleted from production render paths"  
**Ground truth:** The 4-tab DashboardView (Executive Summary, Drivers & HF, Ranked Barriers, Evidence) IS the active production render. `BowtieApp.tsx:160` renders `<DashboardView />` unconditionally. The components were updated/reused for M003 cascading data, not deleted.  
**Evidence:** `frontend/components/BowtieApp.tsx:11, 160`, `frontend/components/dashboard/DashboardView.tsx:19–22`.  
**Suspected cause:** Handoff conflates "M002 data model replaced" with "M002 UI components deleted". The tab structure persisted; only the data feeding it changed.  
**Demo-day impact:** LOW — the UI works correctly. This is a documentation accuracy issue.  
**Recommended action:** Correct handoff v1.1: say "M002 UI components updated to consume M003 cascade model output."

---

### DISAGREE #7 — D-FE-4 (Provenance Component Existence)

**Claim source:** Handoff v1.0 §8  
**Claim verbatim:** "Provenance strip component EXISTS in frontend (may be unrendered per F2)"  
**Ground truth:** No Provenance or provenance component file found anywhere in `frontend/components/`. Zero grep hits. This confirms DENOMINATORS_AUDIT F2 (provenance strip not implemented in any `.tsx` file).  
**Evidence:** Recursive grep for "Provenance|provenance" in `frontend/components/` → 0 results. File glob for `*Provenance*` → 0 results.  
**Suspected cause:** The provenance strip spec (UI-CONTEXT.md §10) was never built. The component doesn't exist even as an unrendered file.  
**Demo-day impact:** LOW — provenance numbers (813, AUC 0.76) not visible to demo audience.  
**Recommended action:** Either build the provenance strip as an M004 task or remove it from the spec. Update handoff to say "not implemented."

---

### DISAGREE #8 — D-FE-8 (pytest Test Count)

**Claim source:** Handoff v1.0 §8  
**Claim verbatim:** "565 passing + 1 skipped = 566 collected"  
**Ground truth:** `pytest --collect-only -q tests/` collects **638 tests**.  
**Evidence:** `python3 -m pytest tests/ --collect-only -q 2>&1 | tail -5` → "638 tests collected in 6.73s".  
**Suspected cause:** Tests were added between handoff freeze and now, OR handoff cited an earlier snapshot (352 passing mentioned in CLAUDE.md, then 565 passing in handoff). The 72-test gap suggests a test-suite expansion.  
**Demo-day impact:** LOW — test count not verbalized at demo. Documentation accuracy.  
**Recommended action:** Update CLAUDE.md and handoff v1.1 with current count (run full pytest to get passing/skip breakdown).

---

### DISAGREE #9 — E45 (PIF _value Text in RAG)

**Claim source:** Handoff v1.0 §13 Fidel Comment Map, D017  
**Claim verbatim:** "E45 #45 PIF _value text in RAG — Shipped"  
**Ground truth:** `src/rag/context_builder.py` `ContextEntry` dataclass does NOT contain any field for PIF `_value` text (the per-incident free-text PIF descriptions like `fatigue._value: "worker had been awake 18h"`). It includes `human_contribution_value: str` (a single field from ControlHuman) and `barrier_failed_human: bool`. The 12 incident-level PIF `_value` strings from `pifs.{people|work|organisation}` are not in the context.  
**Evidence:** Full `src/rag/context_builder.py` content (ContextEntry dataclass fields: incident_id, control_id, barrier_name, barrier_family, side, barrier_status, barrier_role, lod_basis, barrier_failed_human, human_contribution_value, supporting_text, incident_summary, rrf_score, barrier_rank, incident_rank, recommendations).  
**Suspected cause:** D017 was written as a planning decision ("S04 RAG rebuild ingests two Schema V2.3 fields"). S04 was planned but the actual implementation in `corpus_builder.py` and `context_builder.py` was not updated. The decision describes future intent.  
**Demo-day impact:** HIGH — if Fidel (Comment #45 author) asks "can you show me degradation factor context?", the system returns `human_contribution_value` from the control record but not the richer PIF narrative from the incident. The Evidence tab content will appear thinner than promised.  
**Recommended action:** Implement D017 fully before Apr-24: update `ContextEntry` to include PIF `_value` fields, update corpus_builder to extract them, update `_format_entry` to render them.

---

### DISAGREE #10 — E59 (Barrier Family Count)

**Claim source:** Handoff v1.0 §13, CLAUDE.md  
**Claim verbatim:** "45 barrier families"  
**Ground truth:** `scripts/association_mining/event_barrier_normalization.py` defines **46** barrier families. Full list in 46 dict keys (see Evidence).  
**Evidence:** Python scan: `re.findall(r'"([^"]+)"\s*:\s*\[', content)` → 46 matches. First few: active_fire_protection_firefighting, active_intervention_to_stop_release, alarms_general_alarm_pa, change_management, chemical_release_scrubbing_neutralization… Last: well_control_barriers_kill.  
**Suspected cause:** Off-by-one at some point in documentation. 46 is the correct count.  
**Demo-day impact:** LOW — family count not verbalized at demo. CLAUDE.md reference should be updated.  
**Recommended action:** Update handoff v1.1 and CLAUDE.md to read "46 barrier families."

---

### DISAGREE #11 — E61 (Full Bowtie Construction)

**Claim source:** Handoff v1.0 §13 Fidel Comment Map, L001 requirement  
**Claim verbatim:** "Scenario builder UI must accept: hazards, threats, top event, consequences, barriers. Confirm all 5 inputs present."  
**Ground truth:** Only 2 of 5 inputs are user-enterable: **top event** (text input in BarrierForm) and **barriers** (add form). Hazards, threats, consequences are **hardcoded** in `BowtieApp.tsx` with comment "Demo threats and consequences (hardcoded — will be user-enterable later)".  
**Evidence:** `frontend/components/BowtieApp.tsx:14–27` — `DEMO_THREATS`, `DEMO_CONSEQUENCES`, `hazardName="High-pressure gas"` all hardcoded.  
**Suspected cause:** Full bowtie construction was deferred to a future milestone per the comment. Handoff overclaimed the UX completeness.  
**Demo-day impact:** HIGH — if Fidel or Prof Ageenko inputs a real scenario (specific hazard, custom threats), the UI cannot accept those. Demo must use hardcoded threats and consequences. Must be scripted around this limitation.  
**Recommended action:** Either implement dynamic threat/consequence input before Apr-24, or script the demo to use the fixed demo scenario and acknowledge the limitation to the evaluators.

---

### DISAGREE #12 — E63 (top_event_category in Features)

**Claim source:** Handoff v1.0 §13  
**Claim verbatim:** "Feature list includes top_event_category AND threat-linkage features AND pathway_sequence"  
**Ground truth:** Cascade model `all_features` (18 features) includes `pathway_sequence_target/cond` ✓ and threat-class flags (`flag_environmental_threat`, `flag_electrical_failure`, `flag_procedural_error`, `flag_mechanical_failure`) ✓. **`top_event_category` is absent** — not in xgb_cascade_y_fail_metadata.json or y_hf_fail_metadata.json `all_features`.  
**Evidence:** `data/models/artifacts/xgb_cascade_y_fail_metadata.json` `all_features` array (18 entries, no `top_event_category`).  
**Suspected cause:** D008 rationale says Comment #63 (threat-based) is addressed via threat-type flags, not a separate top_event_category feature. The handoff claim overstates.  
**Demo-day impact:** MEDIUM — if questioned about "top event type" as a model input, the answer is "we encode threat class (environmental/electrical/procedural/mechanical), not a separate top-event category." Nuanced but defensible.  
**Recommended action:** Correct handoff claim to: "pathway_sequence AND threat-class flags (4 Boolean flags) AND num_threats_in_sequence."

---

### DISAGREE #13 — F-D-2 (D-M004 Decisions Not Present)

**Claim source:** Handoff v1.0 §14 Decisions Register  
**Claim verbatim:** "D-M004-01 through D-M004-06 are present"  
**Ground truth:** DECISIONS.md has 82 lines and ends at D019 (2026-04-20). No D-M004-XX entries exist.  
**Evidence:** `grep -n "^## D-M004"` → 0 hits. File ends at D019.  
**Suspected cause:** The D-M004-XX decisions were written in GSD planning documents or captured in other files (e.g., M004-kickoff.md mentions "Decision A") but were never appended to the canonical DECISIONS.md register.  
**Demo-day impact:** LOW — evaluators are unlikely to read the decisions register at the demo. Internal traceability gap.  
**Recommended action:** Append D-M004-01 through D-M004-06 to DECISIONS.md before Apr-27. Keep append-only rule.

---

### DISAGREE #14 — G-AR-3 (get_controls() Existence)

**Claim source:** CLAUDE.md, Handoff v1.0 §15 Architecture  
**Claim verbatim:** "get_controls() is single source of truth for control extraction"  
**Ground truth:** `get_controls()` does NOT exist anywhere in `src/ingestion/structured.py` or any other `src/` file. `src/analytics/flatten.py:40` directly accesses `incident.get("bowtie", {}).get("controls", [])`. No single point of control extraction was ever implemented.  
**Evidence:** `grep -rn "def get_controls"` → 0 results across all `src/*.py`.  
**Suspected cause:** The CLAUDE.md instruction was aspirational/architectural guidance rather than reflecting the implemented state. The function was never built; flatten.py bypasses it directly.  
**Demo-day impact:** LOW — internal architecture. No user-facing impact.  
**Recommended action:** Either implement `get_controls()` in structured.py and refactor callers, or remove the claim from CLAUDE.md and handoff.

---

### DISAGREE #15 — G-AR-6 (SHAP_HIDDEN_FEATURES source_agency)

**Claim source:** Handoff v1.0 §15 Architecture  
**Claim verbatim:** "SHAP_HIDDEN_FEATURES constant filters source_agency from UI"  
**Ground truth:** `SHAP_HIDDEN_FEATURES = new Set(['primary_threat_category'])` — only `primary_threat_category` is hidden. `source_agency` is absent from the set. Note: `source_agency` was dropped from model features entirely per D005, so it never appears in SHAP output; no filter is needed.  
**Evidence:** `frontend/lib/shap-config.ts:13`.  
**Suspected cause:** Handoff retained a stale claim from pre-D005 model versions when source_agency was a feature and needed filtering. After D005 dropped it from features, the filter became moot, but the claim was not updated.  
**Demo-day impact:** LOW — no UI impact since source_agency is not in SHAP output anyway.  
**Recommended action:** Update handoff v1.1 claim to: "SHAP_HIDDEN_FEATURES = {primary_threat_category}. source_agency is not a model feature (dropped per D005) and requires no filtering."

---

## Cannot-Verify Items

| Claim ID | Reason |
|---|---|
| D-FE-6 | `NEXT_PUBLIC_ENABLE_T2B_SYNTHESIS` exists only in `frontend/.env.local` (gitignored, present locally as `=false`). No committed env file sets this value. Cannot assert a durable production default from committed artifacts. |
| F-D-3 | DECISIONS.md has only one commit in git log (`469bc93`). Cannot isolate per-entry mutation history without a multi-commit baseline. Structural review is consistent with append-only but cannot be proven. |
| E56 (UI display) | `CascadingBarrierPrediction` schema has no `lod_display` or `lod_industry_standard` field. `DetailPanel.tsx` checks `pred.lod_display` but this will be `undefined` for cascading predictions. Cannot confirm the 11-category label is actually rendered at runtime without UI execution. |
| A2a (UNKNOWN 24) | 24 cascade incidents resolve as UNKNOWN in flat_incidents_combined.csv. Whether these are CSB incidents that failed source resolution vs. genuinely unknown-source incidents cannot be determined from committed artifacts alone. |

---

## Demo-Day Risk Assessment

### HIGH (must resolve pre-Apr-24)

| Claim | Issue | Mitigation |
|---|---|---|
| E45 / D017 | PIF `_value` text not in RAG context. Evidence tab lacks the degradation factor narrative Fidel specifically requested. | Implement D017 (update ContextEntry + corpus_builder + context_builder) before Apr-24. Estimated: 2–3h. |
| E61 / L001 | Hazards, threats, and consequences are hardcoded. Evaluators cannot enter a custom scenario. | Pre-script the demo around the BSEE demo scenario. If evaluators ask to enter a custom scenario, demo the barrier-entry flow only and acknowledge the limitation as "roadmap." |
| C-API-3 / D-M004-03 | snippet_count / unique_incident_count missing from ExplainCascadingResponse. If demo script shows evidence count, this is counted client-side from `evidence_snippets.length` (consistent with prior behavior but not a clean API field). | Low implementation cost; add fields to schema and populate from list length. Or accept the frontend workaround and don't surface these counts in the demo script. |

### MEDIUM (resolve post-Apr-24 for handoff v1.1)

| Claim | Issue |
|---|---|
| C-API-4 / D-M004-01 | `n_incidents` / `generated_at` not in AprioriRulesResponse. Coupled to DENOMINATORS_AUDIT F1 fix (174→723). Should be fixed together before handoff v1.1. |
| F-D-2 | D-M004-01 through D-M004-06 not in DECISIONS.md. Append before v1.1 handoff. |
| A2 / A2a | Agency counts wrong (3 not 4; CSB 19 not 43). Update documentation. |

### LOW (long-tail documentation cleanup)

- C-API-1: Add `/narrative-synthesis` to endpoint table.
- D-FE-2: Correct "M002 4-tab deleted" to "updated/reused."
- D-FE-4: Remove provenance strip component claim (not implemented).
- D-FE-8: Update test count (638 collected, not 566).
- E59: Update barrier family count (46, not 45).
- E63: Remove `top_event_category` from feature list claim.
- G-AR-3: Remove or implement `get_controls()` claim.
- G-AR-6: Update `SHAP_HIDDEN_FEATURES` description.

---

## Cross-References to Denominators Audit

| This Audit | Prior C-ID | Relationship |
|---|---|---|
| D-FE-4 (provenance component absent) | C22 / C23 | Extends: prior audit noted provenance strip unimplemented (F2). This audit confirms no component file exists at all — not just unrendered. |
| C-API-4 (n_incidents not in schema) | C16 / F1 | Extends: C16 identified 174 vs 723 mismatch in DriversHF.tsx. C-API-4 adds: the API also doesn't expose n_incidents, so even a fix to the frontend would need D-M004-01 to source it from the API. Both fixes are required together. |
| D-FE-8 (test count 638 vs 566) | — | No prior C-ID. New finding. |
| E45 (PIF _value not in RAG) | — | No prior C-ID. Audits the backend claim D017 describes as "shipped." |
| F-D-2 (D-M004-XX missing) | — | No prior C-ID. The handoff presents M004 decisions as committed to the register when they have not been appended. |
