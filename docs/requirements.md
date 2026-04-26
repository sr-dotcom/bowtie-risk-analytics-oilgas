# Requirements

This file is the explicit capability and coverage contract for the project.

## Active

### R017 — Train two XGBoost cascading models (y_fail_target and y_hf_fail_target) from barrier_model_dataset_base_v3.csv (552 → 529 rows across 156 incidents after dropping lod_industry_standard="Other" and lod_numeric=99)
- Class: core-capability
- Status: active
- Description: Train two XGBoost cascading models (y_fail_target and y_hf_fail_target) from barrier_model_dataset_base_v3.csv (552 → 529 rows across 156 incidents after dropping lod_industry_standard="Other" and lod_numeric=99)
- Why it matters: Replaces archived Models 1/2/3 with pathway-aware cascading framing that matches CCPS process-safety methodology (Khakzad 2013, 2018) and directly addresses Fidel Comment #12
- Source: user
- Primary owning slice: M003-z2jh4m/S02
- Supporting slices: M003-z2jh4m/S01
- Validation: unmapped
- Notes: Port notebook cells 7, 9, 15, 17 verbatim from docs/evidence/reference/xgb-combined-dual-inference-workflow.ipynb; use Patrick's exact hyperparameters; artifacts as .joblib pipelines (OrdinalEncoder + XGBClassifier) with metadata JSON sidecars

### R018 — GroupKFold(5) CV on incident_id with y_fail_target AUC ≥ 0.70 as hard gate; S02 mini-gate task halts auto-mode if gate fails
- Class: quality-attribute
- Status: active
- Description: GroupKFold(5) CV on incident_id with y_fail_target AUC ≥ 0.70 as hard gate; S02 mini-gate task halts auto-mode if gate fails
- Why it matters: Prior holdout split (ROC-AUC 0.8709 on y_fail, 0.8300 on y_hf_fail) used Patrick's stratified split; GroupKFold on incident_id is stricter (no pair leakage across folds) and is the scientifically defensible evaluation
- Source: user
- Primary owning slice: M003-z2jh4m/S02
- Supporting slices: none
- Validation: unmapped
- Notes: Expected range 0.75-0.82 on y_fail; if below 0.70, stop auto-mode and surface for human decision. Full training still reports both target AUCs (see D014)

### R020 — Add /predict-cascading, /rank-targets, /explain-cascading to FastAPI with Pydantic request/response schemas and pytest contract tests
- Class: core-capability
- Status: active
- Description: Add /predict-cascading, /rank-targets, /explain-cascading to FastAPI with Pydantic request/response schemas and pytest contract tests
- Why it matters: API is the boundary between the frontend scenario builder and the cascading models + RAG
- Source: user
- Primary owning slice: M003-z2jh4m/S03
- Supporting slices: none
- Validation: unmapped
- Notes: /predict-cascading takes full bowtie + conditioning barrier; returns per-target probabilities + SHAP. /rank-targets returns ordered barriers by failure probability. /explain-cascading returns RAG narrative for a (conditioning, target) pair.

### R021 — /predict and /explain endpoints return HTTP 410 Gone after S03 lands; response body includes pointer to new cascading endpoints
- Class: integration
- Status: active
- Description: /predict and /explain endpoints return HTTP 410 Gone after S03 lands; response body includes pointer to new cascading endpoints
- Why it matters: Clean break from marginal-probability framing; no dual-stack. Only consumer is the Next.js frontend being deleted in S05, so breakage is bounded.
- Source: user
- Primary owning slice: M003-z2jh4m/S03
- Supporting slices: none
- Validation: unmapped
- Notes: Acceptable dev-UI breakage window during S03–S04 (existing frontend calls stale endpoints until S05 deletes it)

### R022 — Rebuild FAISS index on the 156-incident corpus matching the cascading training scope; implement a pair-based context builder that retrieves evidence for (conditioning_barrier, target_barrier) queries; archive v1 FAISS artifacts alongside archived Models 1/2/3
- Class: core-capability
- Status: active
- Description: Rebuild FAISS index on the 156-incident corpus matching the cascading training scope; implement a pair-based context builder that retrieves evidence for (conditioning_barrier, target_barrier) queries; archive v1 FAISS artifacts alongside archived Models 1/2/3
- Why it matters: Evidence narratives must draw from the same scope as the trained model — otherwise training/serving skew for no benefit
- Source: user
- Primary owning slice: M003-z2jh4m/S04
- Supporting slices: none
- Validation: unmapped
- Notes: Archive v1 to data/rag/archive/v1/; current 526-incident corpus discarded for serving

### R023 — SHAP TreeExplainer instantiated in-memory at inference from the trained XGBClassifier (NOT persisted); human-readable feature names surfaced in /predict-cascading and /explain-cascading responses
- Class: failure-visibility
- Status: active
- Description: SHAP TreeExplainer instantiated in-memory at inference from the trained XGBClassifier (NOT persisted); human-readable feature names surfaced in /predict-cascading and /explain-cascading responses
- Why it matters: SHAP waterfall in the UI is the primary per-barrier explanation surface; feature names must be human-readable for Fidel's review
- Source: user
- Primary owning slice: M003-z2jh4m/S03
- Supporting slices: M003-z2jh4m/S02
- Validation: unmapped
- Notes: Per project gotcha — SHAP TreeExplainer must NOT be serialized (joblib/pickle); always recreate from loaded model

### R024 — Delete Executive Summary, Drivers & HF, Ranked Barriers, Evidence tabs. Build blank-form scenario builder: user declares incident context + top event (Loss of Containment), adds barriers with attributes + threats, clicks "Generate Bowtie Diagram," then clicks any barrier to treat it as failed (conditioning). Remaining barriers receive HIGH/MED/LOW cascading-risk color overlays, a SHAP waterfall shows per-target attribution, and a RAG narrative explains using 156-incident corpus evidence. Results panel includes a "Human Factors Context" subsection surfacing PIFs from the source incident when scenario maps to a known incident.
- Class: primary-user-loop
- Status: active
- Description: Delete Executive Summary, Drivers & HF, Ranked Barriers, Evidence tabs. Build blank-form scenario builder: user declares incident context + top event (Loss of Containment), adds barriers with attributes + threats, clicks "Generate Bowtie Diagram," then clicks any barrier to treat it as failed (conditioning). Remaining barriers receive HIGH/MED/LOW cascading-risk color overlays, a SHAP waterfall shows per-target attribution, and a RAG narrative explains using 156-incident corpus evidence. Results panel includes a "Human Factors Context" subsection surfacing PIFs from the source incident when scenario maps to a known incident.
- Why it matters: Existing 4-tab dashboard answers "which barriers in this incident failed?" — a backward-looking incident viewer. Scenario builder answers "given this configuration and a failure, what's cascading risk?" — a forward-looking design tool. Completely different product.
- Source: user
- Primary owning slice: M003-z2jh4m/S05
- Supporting slices: M003-z2jh4m/S01, M003-z2jh4m/S03, M003-z2jh4m/S04
- Validation: unmapped
- Notes: S05 task sequence is state-first: <ScenarioBuilder> parent → form components → delete old tabs → BowtieSVG integration → click handler + overlay → results panel. Never start with SVG. Never delete old tabs before ScenarioBuilder is stable. PIF surface satisfies D011's metadata-retention intent.

### R025 — Blue threat borders, red consequence borders, orange/white top-event, gray pathway curves preserved through UI rewrite
- Class: constraint
- Status: active
- Description: Blue threat borders, red consequence borders, orange/white top-event, gray pathway curves preserved through UI rewrite
- Why it matters: Industry-recognized visual convention; Fidel and external evaluators expect BowTieXP-style visuals
- Source: user
- Primary owning slice: M003-z2jh4m/S05
- Supporting slices: none
- Validation: unmapped
- Notes: Reference docs/reference/BOWTIE_SVG_SPEC.md and docs/evidence/reference/bowtie-reference-v4.html

### R026 — BowtieSVG coordinate edits require incremental manual browser verification under Claude Code CLI — never auto-executed. Color overlays, fill/stroke state changes, and interaction state are permitted without manual gate.
- Class: constraint
- Status: active
- Description: BowtieSVG coordinate edits require incremental manual browser verification under Claude Code CLI — never auto-executed. Color overlays, fill/stroke state changes, and interaction state are permitted without manual gate.
- Why it matters: K001 is a persistent project rule (see .gsd/KNOWLEDGE.md); violations historically caused broken SVG layouts that needed hours to debug
- Source: user
- Primary owning slice: M003-z2jh4m/S05
- Supporting slices: none
- Validation: unmapped
- Notes: Encoded in D015 — S05 is a human-led slice; GSD plans but does not dispatch S05 execution

### R027 — `docker compose up` brings up API + frontend + nginx containers; Cloudflare Tunnel serves a public demo URL per D007
- Class: launchability
- Status: active
- Description: `docker compose up` brings up API + frontend + nginx containers; Cloudflare Tunnel serves a public demo URL per D007
- Why it matters: Demo-day deliverable; evaluator access requires a public URL
- Source: user
- Primary owning slice: M003-z2jh4m/S06
- Supporting slices: none
- Validation: unmapped
- Notes: nginx config in nginx/nginx.conf and deploy/nginx.conf already exist; Cloudflare Tunnel setup is manual per D015

### R028 — Write ADR-004 capturing D008–D013 rationale with one SHAP waterfall example; update README, CLAUDE.md, ARCHITECTURE.md, EVALUATION.md to reflect cascading pair-feature model and scenario-builder UI
- Class: continuity
- Status: active
- Description: Write ADR-004 capturing D008–D013 rationale with one SHAP waterfall example; update README, CLAUDE.md, ARCHITECTURE.md, EVALUATION.md to reflect cascading pair-feature model and scenario-builder UI
- Why it matters: Documentation debt after a major pivot misleads every future reader (AI tools and humans alike); ADR is the historical record for why we pivoted
- Source: user
- Primary owning slice: M003-z2jh4m/S06
- Supporting slices: none
- Validation: unmapped
- Notes: All M001/M002 docs still reference 3 XGBoost models, 4-tab dashboard, 526-incident corpus — must all be updated

### R029 — Demo walkthrough video < 5 min, scripted against the three demo scenarios (BSEE, CSB, UNKNOWN)
- Class: launchability
- Status: active
- Description: Demo walkthrough video < 5 min, scripted against the three demo scenarios (BSEE, CSB, UNKNOWN)
- Why it matters: Fallback if Cloudflare Tunnel fails on demo day (per D007 mitigation); also stands alone as asynchronous evaluator artifact
- Source: user
- Primary owning slice: M003-z2jh4m/S06
- Supporting slices: none
- Validation: unmapped
- Notes: Manual recording; not GSD-dispatchable (per D015)

### R030 — Every phase (research, planning, execution, completion, validation) routes through the configured claude-code/* models — never direct Anthropic API
- Class: constraint
- Status: active
- Description: Every phase (research, planning, execution, completion, validation) routes through the configured claude-code/* models — never direct Anthropic API
- Why it matters: Direct third-party API auth is blocked in the working environment; claude-code provider routing is the verified working path
- Source: user
- Primary owning slice: M003-z2jh4m (all slices)
- Supporting slices: none
- Validation: unmapped
- Notes: Policy requirement AND practical requirement

### R031 — UI writes the 11-category CCPS LoD taxonomy values directly to the model — no mapping layer. Categories: Alarm and Operator Response, Structural Integrity, Process Control, Safety Instrumented Systems, Process Containment, Protection Systems, Pressure Relief Systems, Detection Systems, Emergency Response, Shutdown Systems, and one more in configs/mappings/lod_categories.yaml. "Other" is excluded at training time.
- Class: constraint
- Status: active
- Description: UI writes the 11-category CCPS LoD taxonomy values directly to the model — no mapping layer. Categories: Alarm and Operator Response, Structural Integrity, Process Control, Safety Instrumented Systems, Process Containment, Protection Systems, Pressure Relief Systems, Detection Systems, Emergency Response, Shutdown Systems, and one more in configs/mappings/lod_categories.yaml. "Other" is excluded at training time.
- Why it matters: Directly addresses Fidel Comment #56; removes a class of mapping bugs; aligns model features with domain taxonomy
- Source: user
- Primary owning slice: M003-z2jh4m/S01
- Supporting slices: M003-z2jh4m/S05
- Validation: unmapped
- Notes: Feature value flows: UI select → form state → /predict-cascading request body → model input (no intermediate remap)

## Validated

### R001 — Delete SPRINT_1-5 md files and DASHBOARD_SPRINT.md from repo root
- Class: core-capability
- Status: validated
- Description: Delete SPRINT_1-5 md files and DASHBOARD_SPRINT.md from repo root
- Why it matters: Stale planning docs clutter root and mislead AI tools reading the repo
- Source: user
- Primary owning slice: M001/S01
- Supporting slices: none
- Validation: validated
- Notes: Verified via `git ls-files | grep -iE 'SPRINT_|DASHBOARD_SPRINT'` returning empty

### R002 — Remove all Zone.Identifier files (4 git-tracked + disk cleanup) and add gitignore pattern
- Class: quality-attribute
- Status: validated
- Description: Remove all Zone.Identifier files (4 git-tracked + disk cleanup) and add gitignore pattern
- Why it matters: 132K Windows alternate data stream files clutter disk; 4 are git-tracked
- Source: user
- Primary owning slice: M001/S01
- Supporting slices: none
- Validation: validated
- Notes: `git ls-files | grep -i Zone.Identifier` returns empty; `*:Zone.Identifier` pattern in .gitignore

### R003 — Delete .vite/ directory and add .vite/ to .gitignore
- Class: quality-attribute
- Status: validated
- Description: Delete .vite/ directory and add .vite/ to .gitignore
- Why it matters: Build cache artifact should not be in version control
- Source: user
- Primary owning slice: M001/S01
- Supporting slices: none
- Validation: validated
- Notes: `test ! -d .vite` exits 0; `.vite/` pattern in .gitignore

### R004 — Move src/models/incident.py, src/models/bowtie.py, src/analytics/engine.py, src/app/main.py, src/app/utils.py to src/_legacy/
- Class: core-capability
- Status: validated
- Description: Move src/models/incident.py, src/models/bowtie.py, src/analytics/engine.py, src/app/main.py, src/app/utils.py to src/_legacy/
- Why it matters: V1 dead code confuses AI tools and developers reading the codebase
- Source: user
- Primary owning slice: M001/S02
- Supporting slices: none
- Validation: validated
- Notes: All 5 files present in src/_legacy/ with __init__.py; originals removed

### R005 — Update imports in pipeline.py, ingestion/loader.py, models/__init__.py, analytics/__init__.py, and 5 test files to use src._legacy paths
- Class: core-capability
- Status: validated
- Description: Update imports in pipeline.py, ingestion/loader.py, models/__init__.py, analytics/__init__.py, and 5 test files to use src._legacy paths
- Why it matters: Imports must follow moved files to keep tests green
- Source: user
- Primary owning slice: M001/S02
- Supporting slices: none
- Validation: validated
- Notes: 352 tests pass post-refactor with zero regressions

### R006 — Add src/_legacy/ pattern to .gitignore so legacy code stays out of future diffs
- Class: quality-attribute
- Status: validated
- Description: Add src/_legacy/ pattern to .gitignore so legacy code stays out of future diffs
- Why it matters: Legacy code should not appear in future diffs or AI context
- Source: user
- Primary owning slice: M001/S01
- Supporting slices: none
- Validation: validated
- Notes: `grep -q 'src/_legacy/' .gitignore` exits 0

### R007 — Full rewrite of CLAUDE.md covering FastAPI backend, Next.js 15 frontend, 3 XGBoost models, SHAP explainability, 4-tab dashboard, Docker deployment
- Class: core-capability
- Status: validated
- Description: Full rewrite of CLAUDE.md covering FastAPI backend, Next.js 15 frontend, 3 XGBoost models, SHAP explainability, 4-tab dashboard, Docker deployment
- Why it matters: CLAUDE.md describes actual project state for AI tools
- Source: user
- Primary owning slice: M001/S03
- Supporting slices: none
- Validation: validated
- Notes: Verified: FastAPI, src/_legacy, 558, BowtieSVG, 352 all present

### R008 — Run pytest after every slice; zero regressions vs baseline
- Class: constraint
- Status: validated
- Description: Run pytest after every slice; zero regressions vs baseline
- Why it matters: Repo hygiene must not break existing functionality
- Source: user
- Primary owning slice: M001/S01
- Supporting slices: M001/S02, M001/S03
- Validation: validated
- Notes: 352 pass in worktree venv; 449 with full packages. Zero regressions across all 3 slices.

### R009 — README.md rewrite: lead with core question, architecture overview, model metrics, dual quickstart, project structure, condensed RAG subsection, What's Left section
- Class: core-capability
- Status: validated
- Description: README.md rewrite: lead with core question, architecture overview, model metrics, dual quickstart, project structure, condensed RAG subsection, What's Left section
- Why it matters: README is the landing page — 80% of impact for hiring managers, professor, and domain expert evaluator
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: none
- Validation: validated
- Notes: M003 will supersede portions (cascading model, scenario-builder UI)

### R010 — CONTRIBUTING.md rewrite covering FastAPI + Next.js + Docker dev workflows
- Class: core-capability
- Status: validated
- Description: CONTRIBUTING.md rewrite covering FastAPI + Next.js + Docker dev workflows
- Why it matters: Current CONTRIBUTING.md references Streamlit and doesn't cover the actual development stack
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: none
- Validation: validated
- Notes: Must include frontend testing guidance (Vitest), Docker compose workflow, Python test commands

### R011 — ARCHITECTURE.md corrected: BowtieSVG not BowtieFlow, no React Flow references, accurate component names
- Class: core-capability
- Status: validated
- Description: ARCHITECTURE.md corrected: BowtieSVG not BowtieFlow, no React Flow references, accurate component names
- Why it matters: Misleads readers about the frontend implementation
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: none
- Validation: validated
- Notes: M003/S06 will update for cascading + scenario-builder

### R012 — .mcp.json removed from git tracking and added to .gitignore
- Class: quality-attribute
- Status: validated
- Description: .mcp.json removed from git tracking and added to .gitignore
- Why it matters: Contains hardcoded absolute paths
- Source: user
- Primary owning slice: M002/S03
- Supporting slices: none
- Validation: validated
- Notes: git rm --cached .mcp.json + add .mcp.json to .gitignore

### R013 — docs/handoff/v23_canonical_575/ JSON data removed (forward-delete only)
- Class: quality-attribute
- Status: validated
- Description: docs/handoff/v23_canonical_575/ JSON data removed (forward-delete only)
- Why it matters: 22MB of JSON bloats every clone
- Source: user
- Primary owning slice: M002/S03
- Supporting slices: none
- Validation: validated
- Notes: 579 tracked files removed.

### R014 — .gitignore updated with .mcp.json, skills-lock.json, .agents/, docs/handoff/v23_canonical_575/ patterns; deduplicate existing .gsd patterns
- Class: quality-attribute
- Status: validated
- Description: .gitignore updated with .mcp.json, skills-lock.json, .agents/, docs/handoff/v23_canonical_575/ patterns; deduplicate existing .gsd patterns
- Why it matters: Prevents re-committing local config and large data files
- Source: user
- Primary owning slice: M002/S03
- Supporting slices: none
- Validation: validated
- Notes: Clean

### R015 — docs/plans/, docs/step-tracker/, docs/meetings/ cleaned from git index and disk
- Class: quality-attribute
- Status: validated
- Description: docs/plans/, docs/step-tracker/, docs/meetings/ cleaned from git index and disk
- Why it matters: Completed planning artifacts clutter the repo
- Source: user
- Primary owning slice: M002/S03
- Supporting slices: none
- Validation: validated
- Notes: Removed from both index and disk

### R016 — EVALUATION.md corpus numbers consistent with README
- Class: quality-attribute
- Status: validated
- Description: EVALUATION.md corpus numbers consistent with README
- Why it matters: Inconsistent numbers between README and EVALUATION.md undermines credibility
- Source: inferred
- Primary owning slice: M002/S02
- Supporting slices: none
- Validation: validated
- Notes: M003/S06 will update to 156-incident v2 scope

### R019 — S01 produces three scenario JSON fixtures (1 BSEE, 1 CSB, 1 UNKNOWN source; each ≥4 barriers, mixed prevention+mitigation, no "Other" LoD, no lod_numeric=99, rich textual descriptions for RAG). S05 exposes a scenario picker in the scenario-builder UI that populates the form from any of the three fixtures.
- Class: core-capability
- Status: validated
- Description: S01 produces three scenario JSON fixtures (1 BSEE, 1 CSB, 1 UNKNOWN source; each ≥4 barriers, mixed prevention+mitigation, no "Other" LoD, no lod_numeric=99, rich textual descriptions for RAG). S05 exposes a scenario picker in the scenario-builder UI that populates the form from any of the three fixtures.
- Why it matters: Demo artifacts for recorded video and live walkthrough; user-facing criterion is a working picker, not files on disk
- Source: user
- Primary owning slice: M003-z2jh4m/S01
- Supporting slices: M003-z2jh4m/S05
- Validation: S01 task T02 produces three JSON fixtures in data/demo_scenarios/ (BSEE, CSB, UNKNOWN). Each has ≥4 barriers, mixed prevention+mitigation sides, no Other LoD, no lod_numeric=99, and substantive textual descriptions. All three fixtures pass pytest suite (34 tests). Demonstrated: BSEE `eb-165-a-fieldwood-09-may-2015` (7 barriers), CSB `arkema-inc-chemical-plant-fire-` (5 barriers), UNKNOWN `caribbean-petroleum-corporation-capeco-refinery-tank-explosion-and-fire` (5 barriers). S05 picker will consume these JSON files from frontend/public/demo-scenarios/ populated by npm prebuild script.
- Notes: Generate in data/demo_scenarios/; build-time npm script copies to frontend/public/demo-scenarios/ during next build; S05 fetches static JSON from /demo-scenarios/

### R032 — Drop all 12 Performance Influencing Factor booleans from the cascading feature set per D011; keep them in Schema V2.3 and surface them in the UI "Human Factors Context" subsection per R024
- Class: constraint
- Status: validated
- Description: Drop all 12 Performance Influencing Factor booleans from the cascading feature set per D011; keep them in Schema V2.3 and surface them in the UI "Human Factors Context" subsection per R024
- Why it matters: D011 rationale: cascading relationships are structural (barrier type, pathway, LoD, threat class) rather than HF-state-dependent; but PIFs remain useful as incident metadata for Fidel's review
- Source: user
- Primary owning slice: M003-z2jh4m/S02
- Supporting slices: M003-z2jh4m/S05
- Validation: S01 task T01 enforces the column contract at the S01→S02 boundary: the cascading_training.parquet drops all 12 PIF _mentioned boolean columns (competence_mentioned, fatigue_mentioned, communication_mentioned, situational_awareness_mentioned, procedures_mentioned, workload_mentioned, time_pressure_mentioned, tools_equipment_mentioned, safety_culture_mentioned, management_of_change_mentioned, supervision_mentioned, training_mentioned) per D011. The parquet contains only encoded features + y_fail + y_hf_fail + incident_id (17 columns). PIF metadata is retained in V2.3 JSON incident records and flows to demo-scenario fixtures (T02) for S05's Human Factors Context subsection per R024; it is NOT passed to S02 modeling.
- Notes: Feature set = 17 engineered features minus source_agency minus 12 PIFs; exact count finalized during S02 feature engineering per Patrick's notebook

## Out of Scope

### R033 — Keep old marginal-probability Models 1/2/3 loadable and serve-able alongside new cascading models
- Class: anti-feature
- Status: out-of-scope
- Description: Keep old marginal-probability Models 1/2/3 loadable and serve-able alongside new cascading models
- Why it matters: Clean break is explicitly chosen over dual-stack; maintaining two modeling frames during a 29-day window is costly and semantically confusing
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Artifacts archived (not deleted) per D009 for optional future re-enablement; not served

### R034 — Keep current FAISS index and serving path for 526-incident v1 corpus
- Class: anti-feature
- Status: out-of-scope
- Description: Keep current FAISS index and serving path for 526-incident v1 corpus
- Why it matters: Training/serving skew — evidence should come from the same scope as the trained model
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: v1 FAISS artifacts archived to data/rag/archive/v1/ for reproducibility only

### R035 — Keep Executive Summary, Drivers & HF, Ranked Barriers, Evidence tabs
- Class: anti-feature
- Status: out-of-scope
- Description: Keep Executive Summary, Drivers & HF, Ranked Barriers, Evidence tabs
- Why it matters: Scenario builder and 4-tab dashboard answer fundamentally different questions; maintaining both creates product ambiguity
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Deleted in S05

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | core-capability | validated | M001/S01 | none | validated |
| R002 | quality-attribute | validated | M001/S01 | none | validated |
| R003 | quality-attribute | validated | M001/S01 | none | validated |
| R004 | core-capability | validated | M001/S02 | none | validated |
| R005 | core-capability | validated | M001/S02 | none | validated |
| R006 | quality-attribute | validated | M001/S01 | none | validated |
| R007 | core-capability | validated | M001/S03 | none | validated |
| R008 | constraint | validated | M001/S01 | M001/S02, M001/S03 | validated |
| R009 | core-capability | validated | M002/S01 | none | validated |
| R010 | core-capability | validated | M002/S02 | none | validated |
| R011 | core-capability | validated | M002/S02 | none | validated |
| R012 | quality-attribute | validated | M002/S03 | none | validated |
| R013 | quality-attribute | validated | M002/S03 | none | validated |
| R014 | quality-attribute | validated | M002/S03 | none | validated |
| R015 | quality-attribute | validated | M002/S03 | none | validated |
| R016 | quality-attribute | validated | M002/S02 | none | validated |
| R017 | core-capability | active | M003-z2jh4m/S02 | M003-z2jh4m/S01 | unmapped |
| R018 | quality-attribute | active | M003-z2jh4m/S02 | none | unmapped |
| R019 | core-capability | validated | M003-z2jh4m/S01 | M003-z2jh4m/S05 | S01 task T02 produces three JSON fixtures in data/demo_scenarios/ (BSEE, CSB, UNKNOWN). Each has ≥4 barriers, mixed prevention+mitigation sides, no Other LoD, no lod_numeric=99, and substantive textual descriptions. All three fixtures pass pytest suite (34 tests). Demonstrated: BSEE `eb-165-a-fieldwood-09-may-2015` (7 barriers), CSB `arkema-inc-chemical-plant-fire-` (5 barriers), UNKNOWN `caribbean-petroleum-corporation-capeco-refinery-tank-explosion-and-fire` (5 barriers). S05 picker will consume these JSON files from frontend/public/demo-scenarios/ populated by npm prebuild script. |
| R020 | core-capability | active | M003-z2jh4m/S03 | none | unmapped |
| R021 | integration | active | M003-z2jh4m/S03 | none | unmapped |
| R022 | core-capability | active | M003-z2jh4m/S04 | none | unmapped |
| R023 | failure-visibility | active | M003-z2jh4m/S03 | M003-z2jh4m/S02 | unmapped |
| R024 | primary-user-loop | active | M003-z2jh4m/S05 | M003-z2jh4m/S01, M003-z2jh4m/S03, M003-z2jh4m/S04 | unmapped |
| R025 | constraint | active | M003-z2jh4m/S05 | none | unmapped |
| R026 | constraint | active | M003-z2jh4m/S05 | none | unmapped |
| R027 | launchability | active | M003-z2jh4m/S06 | none | unmapped |
| R028 | continuity | active | M003-z2jh4m/S06 | none | unmapped |
| R029 | launchability | active | M003-z2jh4m/S06 | none | unmapped |
| R030 | constraint | active | M003-z2jh4m (all slices) | none | unmapped |
| R031 | constraint | active | M003-z2jh4m/S01 | M003-z2jh4m/S05 | unmapped |
| R032 | constraint | validated | M003-z2jh4m/S02 | M003-z2jh4m/S05 | S01 task T01 enforces the column contract at the S01→S02 boundary: the cascading_training.parquet drops all 12 PIF _mentioned boolean columns (competence_mentioned, fatigue_mentioned, communication_mentioned, situational_awareness_mentioned, procedures_mentioned, workload_mentioned, time_pressure_mentioned, tools_equipment_mentioned, safety_culture_mentioned, management_of_change_mentioned, supervision_mentioned, training_mentioned) per D011. The parquet contains only encoded features + y_fail + y_hf_fail + incident_id (17 columns). PIF metadata is retained in V2.3 JSON incident records and flows to demo-scenario fixtures (T02) for S05's Human Factors Context subsection per R024; it is NOT passed to S02 modeling. |
| R033 | anti-feature | out-of-scope | none | none | n/a |
| R034 | anti-feature | out-of-scope | none | none | n/a |
| R035 | anti-feature | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 14
- Mapped to slices: 14
- Validated: 18 (R001, R002, R003, R004, R005, R006, R007, R008, R009, R010, R011, R012, R013, R014, R015, R016, R019, R032)
- Unmapped active requirements: 0
