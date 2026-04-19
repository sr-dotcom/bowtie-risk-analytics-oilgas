# M003: Cascading Pivot — Milestone Description

## Goal

Replace marginal-probability barrier failure Models 1/2/3 with Patrick Hunter + Jeffrey Arnette's pair-feature cascading framing. Deliver a scenario-builder UX where users construct a bowtie, click a barrier to treat it as failed, and see ranked cascading-risk predictions with SHAP explanations and RAG evidence narratives. Demo-ready for May 16 2026 graduation.

## Validation gate — PASSED pre-milestone

Gate ran 2026-04-18 on Patrick's notebook cell 12 holdout (stratified split):
- `y_fail_target` holdout ROC-AUC = **0.8709**
- `y_hf_fail_target` holdout ROC-AUC = **0.8300**

Our S02 includes a mini-gate: re-run training with GroupKFold(5) on `incident_id` (no leakage across train/test). If `y_fail_target` drops below 0.70, S02 stops and we re-discuss. Expected fall is to ~0.75-0.82 range, still well above threshold.

## Training data

- **Authoritative input:** `data/models/cascading_input/barrier_model_dataset_base_v3.csv` (Patrick's curated training set, gitignored)
- **Raw reference:** `data/models/cascading_input/barrier_threat_pairs_for_jeffrey_v2.csv` (gitignored)
- **Notebook reference:** `docs/references/xgb_combined_dual_inference_workflow.ipynb` (committed — port cells 7, 9, 15, 17 verbatim)
- **Rows:** 552 raw → drop 22 with `lod_industry_standard="Other"` + 1 with `lod_numeric=99` → **529 training rows**
- **Incidents:** 156
- **Labels:** `y_fail` 48.7% positive, `y_hf_fail` 15.2% positive

## Encoding (verified from base_v3.csv — UI writes these values directly, no mapping layer)

- `barrier_level`: `prevention` | `mitigation` (lowercase)
- `lod_industry_standard`: 11-category CCPS-aligned:
  - Alarm and Operator Response
  - Structural Integrity
  - Process Control
  - Safety Instrumented Systems
  - Process Containment
  - Protection Systems
  - Pressure Relief Systems
  - Detection Systems
  - Emergency Response
  - Shutdown Systems
  - (No "Other" — dropped from training)
- `lod_numeric`: 1 | 2 | 3 | 4
- `barrier_condition`: `effective` | `degraded` | `ineffective` | `status_unknown`
- At inference: `barrier_condition_cond` always forced to `"ineffective"` (conditioning = failed barrier)

Fidel Comment #56 solved natively — model is trained on the CCPS taxonomy he asked for.

## Scope — 6 slices

### S01 Validation gate
- Status: already PASSED pre-milestone
- Work: document gate results in ADR-004
- Duration: trivial, folds into S06 docs work

### S02 Data pipeline + mini-gate + demo scenarios
- `src/modeling/cascading/build_pair_dataset.py` — reads base_v3.csv, drops 23 invalid rows, applies pair cross-join (notebook cell 7), drops self-pairs, filters `y_fail_cond==1`
- `src/extraction/threat_classifier.py` — 4-class: Environmental, Electrical, Mechanical, Procedural
- Mini-gate task: train `y_fail_target` with GroupKFold(5) on `incident_id` using Patrick's hyperparameters; report AUC; require ≥ 0.70
- Identify 3 demo scenarios from 156-incident corpus (1 BSEE, 1 CSB, 1 UNKNOWN; each with 4+ barriers, mixed prevention/mitigation, no "Other" LoD, no `lod_numeric=99`). Write as scenario-builder form JSON for S05.
- Tests: row counts, label rates, feature distributions, no self-pairs, all `y_fail_cond==1`

### S03 Model training + SHAP + explain
- `src/modeling/cascading/feature_engineering.py` — 18 features
- `src/modeling/cascading/train.py` — Patrick's hyperparameters (n_estimators=400, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, min_child_weight=5); OrdinalEncoder `handle_unknown=use_encoded_value unknown_value=-1`; GroupKFold(5) on `incident_id`; `scale_pos_weight` computed once on full train set
- `src/modeling/cascading/explain.py` — SHAP TreeExplainer for both targets; human-readable feature-name mapping (`lod_industry_standard_target` → "Target barrier type", etc.)
- `src/modeling/cascading/predict.py` — port notebook cells 15 and 17 verbatim
- Artifacts to `data/models/cascading_artifacts/`
- Risk tiers: HIGH ≥ 0.66, MEDIUM ≥ 0.33, LOW < 0.33; verify survive GroupKFold recalibration; update `configs/risk_thresholds.json` if distribution shifts
- Archive old Models 1/2/3 to `data/models/archive/`

### S04 Backend migration
- `POST /predict-cascading` — full bowtie state + conditioning barrier → ranked target predictions with SHAP
- `POST /rank-targets` — bulk ranking variant
- `POST /explain-cascading` — RAG evidence narrative for (conditioning, target) pairs
- `GET /predict` and `GET /explain` → return 410 Gone
- `/health` and `/apriori-rules` unchanged
- RAG corpus rebuilt at 156-incident v2 scope
- Pair-based context builder
- Contract tests per endpoint; RAG eval rerun at v2 scope

### S05 Frontend rebuild (scenario-builder UX)
- DELETE existing dashboard tab structure entirely (Executive Summary, Drivers & HF, Ranked Barriers, Evidence)
- New folders: `frontend/components/builder/`, `diagram/`, `results/`
- **Task sequence (state-first, per pre-slice steer):** ScenarioBuilder parent state → form inputs → delete old tabs → BowtieSVG integration reading from state → click handler + color overlay → results panel
- `<ScenarioBuilder>` parent component owns all form and results state
- Form: Incident Context textarea, fixed "Loss of Containment" top event, barrier list with add/edit/delete, threat list per barrier, validation (pathway_sequence 1-3, lod_numeric 1-4, LoD options filtered by Barrier Level)
- 3 demo scenarios loadable (from S02 JSON output)
- "Generate Bowtie Diagram" button; form locks on click; "Edit" unlocks and clears results panel
- BowtieSVG renders from ScenarioBuilder state (not hard-coded incidents); stays a controlled visual component
- Click barrier → conditioning state, red "ineffective" overlay
- Cascading-risk color overlay on other barriers (HIGH=red, MEDIUM=amber, LOW=green) driven by `/predict-cascading` response
- Render threats on mitigation barriers with "escalation factor" styling (visually distinct; data model unchanged)
- BowTieXP canonical visual language preserved throughout (blue threat borders, red consequence borders, orange/white top-event symbol, gray pathway curves)
- Results panel: ranked target barriers with H/M/L chips (both models side-by-side), SHAP waterfall per selected target, RAG narrative, PIF-as-metadata evidence panel (honest framing for Fidel Comment #45)
- K001 applies: color and state overlays OK; no SVG coordinate edits without manual browser verification
- Vitest coverage for click handler, overlay rendering, form validation, demo-scenario loading

### S06 Docs + deploy
- `docs/decisions/ADR-004-cascading-pivot.md` — D008–D013 captured, validation gate results, PIF removal rationale with honest Fidel #45 framing, one example SHAP waterfall with narrative, base_v3.csv authoritative decision
- README rewrite: new core question, new AUC metrics, scenario-builder UX, 156-incident scope note, 529-row training set
- CLAUDE.md rewrite: cascading module structure, authority correction per D012 (Ageenko=prof, Fidel=evaluator, GNSR=lead, Jeffrey+Patrick=teammates)
- ARCHITECTURE.md: cascading pipeline, new endpoints, deprecated endpoints
- EVALUATION.md: cascading CV metrics, RAG eval at v2 scope
- Archive old Models 1/2/3 artifacts (not delete)
- Demo walkthrough video < 5 min, 2-take policy, scripted against 3 demo scenarios
- Docker rebuild per D007: own server (Ubuntu 24.04) + Docker Compose + Cloudflare Tunnel
- Three containers: API, frontend, nginx
- Deploy + Cloudflare Tunnel smoke test
- Verify 410 on `/predict` and `/explain` in production

## Constraints

- **Architecture Freeze v1** applies (no new dirs under `structured/`, no bypassing `get_controls()`, no writes to L0/L1 from ML code)
- **K001** applies to BowtieSVG.tsx (no auto SVG coordinate edits; color/state overlays permitted)
- **Authority per D012**: Ageenko=professor, Fidel=domain evaluator, GNSR=project lead, Jeffrey+Patrick=teammates (NOT supervisors)
- **PIFs removed** from cascading features per D011; kept as incident metadata in Schema V2.3
- **Model 3 archived**, not deleted, per D009
- **Demo must be accessible** to Fidel and Prof. Ageenko on demo day via Cloudflare Tunnel URL

## Execution mode

Hybrid tool approach:
- S02, S03, S04, S05-A (infrastructure), S06 docs → GSD auto-mode
- S05-B (visual integration), S05-C (visual polish) → Claude Code CLI with Opus 4.7 for visual calls, Sonnet 4.6 for bulk edits
- S06 deploy + smoke test → Claude Code CLI (live system work)
- Demo video recording → manual

Handoffs at slice/phase boundaries only. No mid-task tool switches.

## References

- `BOWTIE_PROJECT_CONTEXT.md` in Claude Project (note: §5.3, §6.4, §6.5, §6.7 contain pre-gate numbers superseded by this milestone description)
- `BOWTIE_M003_ACTION_SHEET.md` in Claude Project (original playbook; superseded where conflicts)
- `M003_PREFLIGHT_PLAN.md` (this milestone's locked pre-flight plan)
- Patrick Hunter & Jeffrey Arnette: notebook + training data (referenced above)

## Success criteria (validation gate at milestone close)

- Both cascading models trained; `y_fail_target` GroupKFold CV AUC ≥ 0.70
- `/predict-cascading`, `/rank-targets`, `/explain-cascading` endpoints pass contract tests
- `/predict` and `/explain` return 410 Gone
- Scenario-builder UI: 3 demo scenarios loadable; generate bowtie works; click-barrier-to-condition triggers cascading risk overlay; SHAP + RAG narrative render
- BowTieXP visual canon preserved
- Docker compose boots all 3 containers; Cloudflare Tunnel URL serves demo
- ADR-004 documents D008–D013 + gate + PIF trade-off
- README, CLAUDE.md, ARCHITECTURE.md, EVALUATION.md reflect April 2026 cascading state
- Demo video recorded
