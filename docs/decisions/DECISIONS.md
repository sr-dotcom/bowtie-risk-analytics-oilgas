# Decisions Register

<!-- Append-only. Never edit or remove existing rows.
     To reverse a decision, add a new row that supersedes it.
     Read this file at the start of any planning or research phase. -->

| # | When | Scope | Decision | Choice | Rationale | Revisable? | Made By |
|---|------|-------|----------|--------|-----------|------------|---------|
| D001 | M001 | arch | Legacy V1 code disposition | Move to src/_legacy/ rather than delete | pipeline.py still imports V1 models at module level; deleting would require deeper refactor. Quarantine preserves functionality while removing confusion. | Yes — when pipeline.py legacy imports are fully removed | human |
| D002 | M002 | convention | README structure and content hierarchy | Lead with core question, then architecture overview, model metrics, dual quickstart, project structure, condensed RAG subsection, What's Left section | README is the landing page for evaluators. Core question + model metrics + interactive diagram are the strongest selling points. RAG is a subsystem, not the value proposition. | No | human |
| D003 | M002 | data | docs/handoff/ JSON removal strategy | Forward-delete only — git rm, no history rewrite | Deadline in 16 days. History rewrite is risky and the 22MB in pack files is acceptable for evaluators who won't inspect them. | No | human |
| D004 | M002 | convention | FastAPI quickstart command in README | `python -m uvicorn src.api.main:app --port 8000 --reload` (module-level app instance, not `create_app --factory`) | `src/api/main.py` exposes both `create_app()` factory and a module-level `app = create_app()`. The `--factory` flag works but is non-standard; the direct `app` reference is simpler, widely understood, and avoids uvicorn factory mode complexity. Override issued 2026-04-12 to enforce this. Supersedes any prior docs referencing `--factory`. | No | human |
| D005 | post-M002 | modeling | Retrained models on 17 features (dropped source_agency) | 17 features, no source_agency | source_agency was proxying data origin rather than risk signal; dropping improved cross-fold stability. Final: Model 1 F1=0.922, Model 2 F1=0.353 MCC=0.266. Artifacts in data/models/artifacts/. | Yes — retrain if new data sources added | human |
| D006 | post-M002 | modeling | Risk thresholds recalibrated for inference regime | p60=0.45, p80=0.70 | Prior thresholds (p60=0.9801) were calibrated pre-scoping and no longer aligned with the 17-feature model's probability distribution. New values set via Model 1 validation-set quantiles. Stored in configs/risk_thresholds.json (tracked in git, survives container rebuilds). | Yes — must recalibrate on every retrain | human |
| D007 | post-M002 | deploy | Deployment target overrides professor's Streamlit Cloud spec | Own server (Ubuntu 24.04) + Docker + Cloudflare Tunnel | Next.js + FastAPI stack is incompatible with Streamlit Community Cloud. Single-point-of-failure risk on demo day acknowledged — mitigation: record walkthrough video as fallback, keep docker compose runnable locally. | Yes — fall back to recorded demo if tunnel fails | human |
| D008 | 2026-04-17 | arch | Pivot to cascading pair-feature model | Adopt Patrick Hunter + Jeffrey Arnette pair-feature framing; deprecate Models 1/2/3; replace with two cascading XGBoost models (y_fail_target, y_hf_fail_target) | Team consensus 2026-04-17; addresses Fidel Comments #12 (pathway-aware), #56 (11-category LoD taxonomy, model trained natively on CCPS-aligned categories), #63 (threat-based); matches process safety methodology (CCPS Khakzad 2013, 2018); better dashboard UX. Supersedes D005 feature contract. Validation gate PASSED 2026-04-18: y_fail_target holdout AUC=0.8709, y_hf_fail_target AUC=0.8300 on Patrick's notebook cell 12 stratified split (our GroupKFold CV in S03 will recalibrate). Training base: barrier_model_dataset_base_v3.csv, 552 rows, 156 incidents. | Yes — if GroupKFold CV in S03 drops AUC below 0.65, revisit | human |
| D009 | 2026-04-17 | modeling | Drop Model 3 (barrier condition multiclass) from M003 scope | Remove from M003; archive artifacts to data/models/archive/; do not carry forward | One narrative is cleaner than two during pivot; ~10h maintenance cost we don't have in 29-day window; Model 3 orthogonal to cascading story; easy to re-enable from archive if a use case surfaces | Yes — re-enable from archive if needed | human |
| D010 | 2026-04-17 | data | Handling of labeled-row filter for cascading training | Use barrier_model_dataset_base_v3.csv directly (Patrick's curated training set, 552 rows, 156 incidents) as S02 input; skip reconstruction from pairs_v2 + pairs_old join | Patrick provided base_v3.csv with labels, all derived features (pathway_sequence, lod_numeric, num_threats_*, flag_*), barrier_condition pre-computed, and expert-mapped lod_industry_standard. Reconstructing from raw CSVs reproduces his pipeline but adds risk of divergence. For S02, use base_v3.csv as authoritative input; document reconstruction recipe as reference for reproducibility only. Supersedes CONTEXT.md §6.7 recipe. | Yes — reconstruct from raw if base_v3 becomes stale | human |
| D011 | 2026-04-17 | modeling | Remove PIFs from cascading model features | Drop all 12 Performance Influencing Factor booleans from feature set; keep them in Schema V2.3 as incident metadata; not used as model features | Team accepts Patrick's hypothesis that cascading relationships are structural (barrier type, pathway, LoD, threat class) rather than HF-state-dependent; PIFs recoverable from schema for future analysis; contradicts D005 feature contract which included 9 PIFs (superseded). Weakens story on Fidel Comment #45 — acknowledged in ADR. | Yes — re-add as features if SHAP ablation in S03 demands | human |
| D012 | 2026-04-17 | team | Authority structure correction | Prof. Ageenko = professor/supervisor; Fidel Ilizastigui Perez = domain expert evaluator; Naga Sathwik Reddy Gona (GNSR) = project lead + primary engineer; Jeffrey Arnette = teammate; Patrick Hunter = teammate | Prior docs (CLAUDE.md implicit framing, Claude web UI project instructions, Risk_R_D_Pod.docx feedback style) incorrectly positioned Jeffrey as practicum advisor/professor; his feedback was peer opinion in professor-voice, not supervisor directive; correction propagated to CLAUDE.md, .gsd/PROJECT.md, Claude web UI project instructions, and Compass knowledge entries | No — permanent correction of prior documentation error | human |
| D013 | 2026-04-17 | process | Use GSD v2 full-project template for M003 | /gsd start full-project as milestone opener; /gsd auto for continuous execution through S02-S06; /gsd steer for corrections; /gsd knowledge for persistent rules; /gsd capture for fire-and-forget thoughts during auto-mode | M003 spans data+model+API+RAG+frontend+docs layers; GSD v2 structured milestone+slice+auto-mode workflow with fresh 200k context per task, crash recovery, adaptive replanning fits better than /gsd discuss or ad-hoc; S01 validation gate handled as manual pre-M003 check (PASSED 2026-04-18); S02-S06 sequential and automatable | Yes — revert to manual if GSD workflow blocks flow | human |
| D014 | M003/S02 | modeling | S02 reports both cascading target AUCs; weak y_hf_fail triggers post-S02 API-shape decision | Full training produces and reports GroupKFold(5) AUC for both y_fail_target and y_hf_fail_target. The mini-gate blocks progression only on y_fail_target ≥ 0.70. If y_hf_fail_target AUC < 0.65, flag it but do not block S02 completion — the decision of whether to expose y_hf_fail in /predict-cascading response becomes a post-S02 human decision. | Secondary target is harder (15.2% vs 48.7% prevalence). Transparent reporting with explicit human escalation beats silent acceptance of a weak model or blocking the whole milestone on it. | Yes — re-decide post-S02 based on measured y_hf_fail AUC | collaborative |
| D015 | M003/S05+S06 | process | S05 and S06 are human-led slices executed under Claude Code CLI | GSD writes S05/S06 plans and must-haves during Plan phase but does NOT auto-dispatch execution tasks. S05 visual-integration and polish runs under Claude Code CLI with Opus 4.7 for vision-sensitive SVG work. S06 docker build, Cloudflare Tunnel setup, smoke testing, and demo video recording are manual + Claude Code CLI. User manually marks UAT checklist at slice completion and GSD advances. Handoffs at slice/phase boundaries only — never mid-task. | K001 protects BowtieSVG coordinate changes from auto-execution (requires incremental browser verification). Docker deploy, Cloudflare Tunnel, and demo video are external-environment actions not suitable for GSD dispatch. Splitting planning (GSD) from execution (Claude Code CLI) preserves GSD planning value while respecting K001 and deploy-boundary constraints. | No — K001 and deploy boundary constraints are fixed | human |
## D016 — 2026-04-19 — y_hf_fail production surface gated on S02b empirical result

**Supersedes:** earlier D016 draft ("drop y_hf_fail"), and D014 reporting-only stance for y_hf_fail.

**Decision:** Production disposition for `y_hf_fail_target` determined by S02b experiment result via three pre-declared branches. No post-hoc judgment:

- **Branch A** — mean AUC ≥ 0.70 AND no fold < 0.60 → ship as full probability, same UI treatment as y_fail.
- **Branch B** — mean AUC 0.60–0.70 OR any fold 0.55–0.60 → ship as risk tier only (HIGH / MEDIUM / LOW) with moderate-confidence badge, no raw probability exposed.
- **Branch C** — mean AUC < 0.60 → drop from production API/UI surface. Retain artifacts on disk for M004 reference. Layer B Degradation Context carries HF alone.

**Rationale:** S02 GroupKFold measured y_hf_fail AUC 0.5562 ± 0.1182 (fold 3 = 0.4009) with current feature set. Root cause is sample-size ceiling (56/156 incidents carry HF positives). D011 dropped PIFs from features; D018 reverses D011 for y_hf_fail only. S02b tests whether PIF re-inclusion + incident-level HF aggregate feature recover generalization.

**Reversible:** only by new D-entry superseding, per rule 15.

**Source:** team debate (6/6 approve), user ruling 2026-04-19.


## D017 — 2026-04-19 — S04 RAG scope expanded: PIF _value text + event.recommendations

**Decision:** S04 RAG rebuild ingests two Schema V2.3 fields previously unused — `pifs.{people|work|organisation}.*._value` text blocks (PIF context descriptions) and `event.recommendations` (real incident-investigation recommendations). Corpus builder ingests both; context builder surfaces them in `/explain-cascading` narrative output.

**Rationale:** Addresses Fidel Comment #34 (recommendations surfaced) and Comment #45 (degradation factors) together. Closes pre-existing Gap #34 from 21_DOMAIN_EXPERT_Gap_Analysis.docx, unresolved in M002.

**Applies regardless of S02b outcome** — useful in all three D016 branches.

**Reversible:** only by new D-entry.

**Source:** team debate (6/6 approve), user ruling 2026-04-19.


## D018 — 2026-04-19 — D011 partially reversed for y_hf_fail target only

**Decision:** 12 PIF boolean `_mentioned` flags re-included as features for `y_hf_fail_target` model training in S02b. `y_fail_target` feature set unchanged — PIFs remain excluded per D011 original rationale.

**Rationale:** D011 excluded PIFs on the hypothesis that cascading relationships are structural not HF-state-dependent. Hypothesis validated for y_fail (AUC 0.76 without PIFs). Hypothesis untested for y_hf_fail specifically. HRA literature (THERP, CREAM, SLIM) treats PIFs as contextual multipliers on HEP — when the target itself is HF-specific, direct PIF inclusion may recover signal.

**Supersedes:** D011 partially (y_hf_fail feature set only).

**Source:** team debate (6/6 approve), user ruling 2026-04-19.


## D019 — 2026-04-20 — S02b branch activation logic corrected to strict total-ordering (supersedes D016 branch definitions)

**Supersedes:** D016 branch B definition ("mean AUC 0.60–0.70 OR any fold 0.55–0.60"), which left cases like (mean AUC ≥ 0.70 with any fold < 0.55) with no branch activating (undefined behavior).

**Decision:** Replace D016 branch definitions with a strict total-ordering rule making Branch C the catch-all. Evaluate in order; first match wins. Interval lower bounds are closed (≥ 0.70 means 0.70 qualifies, ≥ 0.60 means 0.60 qualifies):

- **Branch A** activates iff mean AUC ≥ 0.70 AND every fold AUC ≥ 0.60.
- **Branch B** activates iff Branch A did not activate AND mean AUC ≥ 0.60 AND every fold AUC ≥ 0.55.
- **Branch C** activates in ALL other cases (catch-all — covers e.g. mean AUC ≥ 0.70 with any fold < 0.55, mean AUC in [0.60, 0.70) with any fold < 0.55, and mean AUC < 0.60).

**Three branches are mutually exclusive and exhaustive** — exactly one always fires.

**Rationale:** Prior Branch B definition had a gap: it did not cover (mean AUC ≥ 0.70 AND any fold < 0.55), leaving code with undefined behavior. Strict total-ordering with catch-all Branch C eliminates the gap. All five S02b pytest assertions (a)-(e) also verify mutual exclusivity via regex line-count == 1 on `^Activated branch: [ABC]$`.

**Applied in:** `S02b-PLAN.md` (T03 section), `S02b/tasks/T03-PLAN.md`, `M003-z2jh4m-ROADMAP.md` (S02b boundary, S02b→S03 contract).

**Reversible:** only by new D-entry superseding, per rule 15.

**Source:** user ruling 2026-04-20.