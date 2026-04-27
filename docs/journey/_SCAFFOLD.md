# Journey Chapter Scaffold
# Phase 3a output — authoring contract for Phase 3b
# Ratified by GNSR: 2026-04-26
# Committed to: docs/journey/_SCAFFOLD.md

---

## Decisions baked in

All 8 open questions from the Phase 3a draft have been resolved. The following
verdicts are locked into this scaffold. Phase 3b authoring begins from this state.

| Q# | Question | Verdict |
|----|----------|---------|
| Q1 | 813 vs 530 training rows | Lead with 813 pair-feature training rows; footnote 530 single-barrier rows with construction explanation |
| Q2 | Where is ≥2 barriers enforced? | Nowhere explicitly — design-implicit in pair-feature loop. Do NOT use label "K-CASCADE-001" in chapters. Cite as implicit constraint (predict.py:248–250) |
| Q3 | Cross-domain RAG bug narrative | HYBRID: CCCLI scaffolds 4 sections (corpus design assumption / observed failure / diagnosis / fix); GNSR writes diagnosis+fix paragraphs (~300–400 words) |
| Q4 | PIF ablation M002 vs M003 | Cite M002 ablation as historical context for retaining PIFs in M003. Frame honestly: "we did not run a fresh M003 ablation due to same sample-size constraints that drove the cascade pivot" |
| Q5 | BOWTIE_DIAGRAM_SPEC.md current? | File does not exist. Drop reference. Cite BowtieSVG.tsx + feat(diagram) commit history directly |
| Q6 | deploy.yml — what does it do? | Verified: GHA builds + pushes to ghcr.io + fires webhook. Webhook is production trigger. SSH is manual fallback. continue-on-error: true is residual flag |
| Q7 | Chapter order preference | Current order (Ch 3 cascade before Ch 5 RAG) confirmed. No reorder |
| Q8 | D012 in lessons-learned | Skip D012 publicly. Chapter 8 focuses on engineering substance (D008 cascade pivot, D016 Branch C, RAG miss rate, LOC scope). D012 stays internal in DECISIONS.md |

---

## Audience

**Primary:** Dr. Ilieva Ageenko (faculty supervisor, UNC Charlotte MS practicum) and
Fidel Ilizastigui Perez (process safety domain expert evaluator). Submission for
graduation May 2026, practicum presentation Apr 27.

**Secondary:** Future recruiters encountering this repo as a portfolio artifact
post-graduation.

**Tone:** Reader-friendly narrative written in current state, not past-tense lab
report. Each chapter stands alone. Cites real files and verified numbers. Fidel
reads for domain rigor (CCPS methodology, LOD taxonomy, prevention vs. mitigation).
Prof. Ageenko reads for research process and engineering judgment.

---

## Reading order

1. `01-the-problem.md` — Why barrier failure prediction matters; domain vocabulary
2. `02-corpus-design.md` — How 739 incidents became training data via LLM extraction
3. `03-cascade-model.md` — The pair-feature XGBoost architecture and the D008 pivot
4. `04-explainability-signals.md` — SHAP + Apriori as two complementary explanation layers
5. `05-rag-retrieval.md` — 4-stage hybrid RAG, cross-domain scoping, 3 experiments
6. `06-frontend-ux.md` — BowtieSVG, P0/P1/P2/P3 state machine, cascading UX
7. `07-deployment.md` — Docker, Cloudflare Tunnel, live demo architecture
8. `08-lessons-learned.md` — What worked, what didn't, what would change

---

## Chapter 1: The Problem

- **Filename:** `docs/journey/01-the-problem.md`
- **Summary:** Process safety barriers in oil and gas operations are not just yes/no
  controls — they exist in layers, they degrade, and they fail in sequences. This
  chapter introduces the Bowtie risk methodology, explains why "which barrier is most
  likely to fail?" is a tractable ML question, and establishes the CCPS-aligned domain
  vocabulary that every subsequent chapter relies on. It defines Loss of Containment
  as the project's scope, explains prevention vs. mitigation, LOD tiers, and why the
  traditional Bowtie diagram (static, manually assessed) is insufficient for
  identifying latent cascade risks.
- **Sources:**
  - `docs/architecture/ARCHITECTURE.md` (overview, core question)
  - `CLAUDE.md` §"Project Overview" and §"Binary prediction targets"
  - `configs/mappings/lod_categories.yaml` (11-category LOD taxonomy)
  - `configs/mappings/barrier_types.yaml` (5-category barrier type mapping)
  - `docs/decisions/DECISIONS.md` D008 rationale (Fidel Comments #12, #56, #63 —
    pathway-aware, CCPS methodology)
  - `src/models/incident_v23.py` (schema vocabulary)
- **Numbers to verify:**
  - 739 canonical incidents in `data/structured/incidents/schema_v2_3/` [ARCHITECTURE.md, CLAUDE.md]
  - 4,776 controls in `data/processed/controls_combined.csv` [CLAUDE.md]
  - 4 source agencies: CSB, BSEE, PHMSA, TSB [ARCHITECTURE.md ingestion section]
  - 25 barrier families [ARCHITECTURE.md, rag_system_overview.md]
  - 11 LOD categories [verify COUNT against `configs/mappings/lod_categories.yaml` before citing]
- **Wordcount estimate:** 500–700 words
- **Why this chapter for THIS project:** A process safety audience (Fidel) will
  immediately evaluate whether the Bowtie framing is used correctly. This chapter
  establishes that the author understands barrier layers, prevention/mitigation
  asymmetry, and LOD tiers as domain concepts — not just as ML features. A generic ML
  portfolio chapter would start with the data; this one starts with why the domain
  makes the problem tractable.
- **Author mode:** GNSR-WRITES — domain vocabulary and "why this problem matters"
  require the author's voice and domain understanding. CCCLI verifies numbers and
  checks that LOD/barrier-type names match the YAML configs.

---

## Chapter 2: Corpus Design — Turning Investigation Reports into Training Data

- **Filename:** `docs/journey/02-corpus-design.md`
- **Summary:** Public incident investigation reports (BSEE, CSB) are unstructured
  PDFs written for regulatory audiences. This chapter explains why BSEE and CSB were
  chosen over PHMSA and TSB for the LOC scope, how LLM extraction (Claude Haiku →
  Claude Sonnet escalation) was used to pull structured Bowtie data from prose
  narratives, and how Schema V2.3 provides the canonical data contract for everything
  downstream. Key engineering choices: the two-pass extraction ladder (cheap model
  first, escalate on quality gate failure), the `get_controls()` function as the
  single source of truth for control extraction, and why the LOC domain filter was
  applied before modeling.
- **Sources:**
  - `src/ingestion/structured.py` (LLM extraction orchestrator, `get_controls()`)
  - `src/ingestion/sources/` (CSB, BSEE, PHMSA, TSB discovery modules)
  - `src/llm/model_policy.py` (Haiku → Sonnet escalation ladder)
  - `src/models/incident_v23.py` (Schema V2.3 Pydantic model)
  - `src/pipeline.py` (CLI entry points)
  - `src/analytics/flatten.py` (CONTROLS_CSV_COLUMNS — 16 columns)
  - `docs/decisions/DECISIONS.md` D010 (Patrick's base_v3.csv choice), D003
    (history rewrite tradeoff)
  - `CLAUDE.md` §"Data Directories", §"Key Schema Fields"
- **Numbers to verify:**
  - 739 canonical V2.3 JSONs [confirmed]
  - 4,776 controls [confirmed]
  - 16 CONTROLS_CSV_COLUMNS [verify against `src/analytics/flatten.py`]
  - 12 PIF _mentioned boolean columns [CLAUDE.md §"Incidents CSV PIF columns"]
  - Extraction cost (~$0.45 per 20 PDFs at Haiku primary) [FLAG: may be stale;
    verify or omit]
- **Wordcount estimate:** 600–800 words
- **Why this chapter for THIS project:** Most ML projects start with a clean dataset.
  This one required building the dataset from scratch using LLMs on unstructured
  regulatory documents. The Haiku → Sonnet escalation ladder and the quality gate
  design are engineering decisions specific to this corpus — a generic "dataset"
  chapter would miss them entirely.
- **Author mode:** HYBRID — GNSR writes the "why BSEE+CSB" rationale, the LOC
  scoping decision, and the tradeoffs in trusting LLM extraction over human
  annotation. CCCLI fills in the extraction pipeline technical details, schema
  migration notes (V2.2→V2.3), and file path references.

---

## Chapter 3: The Cascade Model — From Single-Barrier Prediction to Pair Features

- **Filename:** `docs/journey/03-cascade-model.md`
- **Summary:** The first version of the ML model predicted each barrier
  independently. This chapter explains why that framing was wrong — barriers exist in
  pathways, and a failed prevention barrier changes the risk landscape for every
  downstream mitigation barrier. It documents the D008 pivot (team decision
  2026-04-17) from the M002 three-model design to M003 cascading pair-feature
  XGBoost, explains the 18 pair features (5 target-barrier features + 5
  conditioning-barrier features + 3 context features + 5 scenario flags), how 156
  incidents produce 813 pair-feature training rows via cross-join (from 530
  single-barrier rows before pairing), and what the GroupKFold(5) CV result of
  AUC 0.76 ± 0.07 means for inference. Explains the implicit barrier-count
  constraint: the cascading model requires at least one conditioning barrier and
  at least one target barrier — with a single barrier in the scenario the prediction
  loop is vacuous and the API returns an empty results list.
- **Sources:**
  - `src/modeling/cascading/pair_builder.py` (feature contracts: BARRIER_FEATURES_TARGET,
    BARRIER_FEATURES_COND, CONTEXT_FEATURES)
  - `src/modeling/cascading/data_prep.py` (ENCODED_FEATURES, preprocessing)
  - `src/modeling/cascading/train.py` (training entry point)
  - `src/modeling/cascading/predict.py` (inference at lines 243–262; implicit
    barrier-count constraint at lines 248–250; D016 Branch C note at top)
  - `src/modeling/cascading/mini_gate.py` (threshold gating)
  - `data/models/artifacts/xgb_cascade_y_fail_metadata.json` (model card — training_rows,
    cv_scores, patrick_hyperparameters)
  - `configs/risk_thresholds.json` (D006 thresholds, p60/p80)
  - `docs/decisions/DECISIONS.md` D008 (cascade pivot rationale), D009 (drop Model 3),
    D011 (PIFs dropped from y_fail), D014/D016/D019 (y_hf_fail branch logic → Branch C)
  - `docs/evidence/reference/xgb-combined-dual-inference-workflow.ipynb`
    (Patrick's reference notebook)
- **Numbers to verify:**
  - 18 pair features [verify exact count: BARRIER_FEATURES_TARGET (5) +
    BARRIER_FEATURES_COND (5, includes barrier_condition_cond) + CONTEXT_FEATURES (7,
    includes 4 flag_* columns) — total in metadata.json all_features list = 18]
  - 156 incidents in training set [confirmed metadata JSON + CLAUDE.md]
  - **813 pair-feature training rows** (lead number); footnote: "constructed from 530
    single-barrier rows via prevention→mitigation cross-join" [813 confirmed in
    metadata JSON training_rows; 530 from CLAUDE.md current-state note]
  - CV AUC 0.76 ± 0.07 [confirmed: mean=0.763012, std=0.06612 in metadata JSON]
  - y_hf_fail AUC 0.5562 ± 0.1182 → Branch C [DECISIONS.md D016]
  - Risk thresholds p60=0.45, p80=0.70 [DECISIONS.md D006 — verify against
    `configs/risk_thresholds.json`]
- **Implicit barrier-count constraint (cite in chapter, do NOT use label "K-CASCADE-001"):**
  > "The cascading model requires at least one conditioning barrier and at least one
  > target barrier — with a single barrier in the scenario, the prediction loop is
  > vacuous and the API returns an empty results list. This is implicit in the
  > pair-feature construction (`src/modeling/cascading/predict.py:248–250`) rather
  > than an explicit validation gate."
- **Wordcount estimate:** 700–900 words
- **Why this chapter for THIS project:** The pathway-awareness framing — a failing
  prevention barrier raises cascade risk for downstream mitigations — is specific to
  the Bowtie process safety methodology and directly addresses Fidel's domain review
  comments (CCPS Khakzad 2013, 2018). A generic XGBoost chapter describes the model;
  this chapter explains *why pair features* are the correct inductive bias for this
  domain.
- **Author mode:** HYBRID — GNSR writes the D008 pivot narrative, the rationale for
  dropping y_hf_fail to Branch C (D016), and the tradeoff between richer model and
  interpretability. CCCLI fills in the feature engineering details, cross-join
  construction math, and CV table.

---

## Chapter 4: Explainability — SHAP and Apriori as Complementary Signals

- **Filename:** `docs/journey/04-explainability-signals.md`
- **Summary:** The cascade model tells you *which* barrier is most likely to fail
  given a conditioning failure. This chapter explains the two explanation layers that
  tell you *why*. SHAP TreeExplainer produces per-barrier, per-prediction feature
  attributions in log-odds space — the top-5 SHAP factors drive the waterfall chart
  in the drill-down panel. The Apriori co-failure association rules, derived from the
  full 739-incident corpus (not just the 156 cascading incidents), answer a different
  question: across the fleet, which barrier families tend to fail together? Together,
  SHAP (individual-level) and Apriori (fleet-level) address both "why does this
  barrier score HIGH?" and "which barriers historically co-fail?" The chapter explains
  why the two signals were kept separate rather than merged (different populations,
  different questions) and cites the M002 PIF ablation as the historical evidence base
  for retaining PIFs in the M003 architecture.
- **Sources:**
  - `src/modeling/cascading/shap_probe.py` (TreeExplainer setup)
  - `src/modeling/cascading/predict.py` (ShapEntry, compute_shap_for_record)
  - `scripts/generate_apriori_rules.py` (co-failure mining algorithm)
  - `data/evaluation/apriori_rules.json` (16 rules, support/confidence/lift)
  - `src/api/main.py` (GET /apriori-rules endpoint)
  - `frontend/components/dashboard/DriversHF.tsx` (SHAP chart + Apriori table)
  - `frontend/components/panel/DetailPanel.tsx` (SHAP waterfall in drill-down)
  - `CLAUDE.md` §"Gotchas" (SHAP TreeExplainer must NOT be serialized)
  - `docs/decisions/DECISIONS.md` D011 (PIFs dropped from y_fail features), D018
    (PIFs re-added for y_hf_fail)
  - `docs/evaluation/EVALUATION.md` §"PIF Ablation Study"
- **Numbers to verify:**
  - 16 Apriori rules in `data/evaluation/apriori_rules.json` [confirmed]
  - Top rule: communication → procedures, confidence 0.732, lift 1.423, count 52 [confirmed]
  - PIF ablation (M002): Model 1 neutral (F1 0.885 vs 0.884); Model 2 improved
    (F1 0.696 vs 0.658) [source: EVALUATION.md — M002 numbers]
  - 200-sample SHAP background arrays [EVALUATION.md, ARCHITECTURE.md]
  - Top-5 SHAP factors surfaced in dashboard [verify in DetailPanel.tsx]
- **PIF ablation framing (ratified Q4 verdict — use this language in chapter):**
  > "The M002 ablation provides the strongest available evidence for PIF utility
  > (Model 2 F1 0.696 vs 0.658 with PIFs; Model 1 neutral). When the architecture
  > pivoted to a single M003 cascade model, PIFs were retained based on this prior
  > evidence; we did not run a fresh M003 ablation due to the same sample-size
  > constraints that drove the cascade pivot."
- **Wordcount estimate:** 500–700 words
- **Why this chapter for THIS project:** The separation between per-prediction
  explainability (SHAP) and fleet-level pattern mining (Apriori) is an architectural
  choice specific to this system. Generic ML explainability chapters show SHAP
  waterfall charts; this chapter explains why a process safety evaluator needs *two*
  explanation surfaces. Fidel's Comment #34 (surface investigator recommendations)
  and the Apriori table directly respond to a named domain review comment.
- **Author mode:** HYBRID — GNSR writes the narrative about why two signals were
  needed (process safety domain reasoning). CCCLI fills in the SHAP serialization
  constraint, the Apriori mining algorithm description, and the rule table.

---

## Chapter 5: The RAG Pipeline — From Incident Corpus to Evidence Retrieval

- **Filename:** `docs/journey/05-rag-retrieval.md`
- **Summary:** Barrier risk scores tell an operator *that* a barrier is likely to
  fail. Real incident evidence tells them *how* similar barriers actually failed in
  past accidents. This chapter documents the 4-stage hybrid RAG pipeline (metadata
  filter → dual FAISS → intersection → RRF fusion), the three experiments that
  produced the current design (baseline hybrid, cross-encoder reranking, and the
  retrieval assessment framework), and the key finding: the bottleneck is recall
  (40% miss rate), not ranking. It also documents the RAG v2 corpus scoping decision
  — why the v1 corpus (526 incidents) was replaced by v2 scoped to the 156 cascading
  training incidents, ensuring retrieval is grounded in the same evidence base as
  prediction. The cross-domain scoping story anchors the v1→v2 transition.
- **Sources:**
  - `src/rag/retriever.py` (HybridRetriever, 4-stage pipeline, RRF formula)
  - `src/rag/corpus_builder.py` (barrier/incident document construction)
  - `src/rag/vector_index.py` (FAISS IndexFlatIP, L2 normalization)
  - `src/rag/reranker.py` (CrossEncoderReranker, disabled by default)
  - `src/rag/rag_agent.py` (RAGAgent orchestrator)
  - `src/rag/explainer.py` (BarrierExplainer, confidence gate ≥ 0.25)
  - `scripts/build_rag_v2.py` (v2 corpus build)
  - `scripts/evaluate_retrieval.py` (50-query assessment harness)
  - `data/evaluation/rag_queries.json` (50 curated queries)
  - `docs/evaluation/rag_experiment_history.md` (3 experiments)
  - `docs/evaluation/rag_system_overview.md` (architecture overview)
  - `docs/decisions/DECISIONS.md` D017 (RAG v2 scope: PIF _value text +
    recommendations)
- **Numbers to verify:**
  - RAG v1: 526 incidents, 3,253 barriers, 25 families [rag_system_overview.md,
    EVALUATION.md]
  - RAG v2: 156 incidents, 1,161 barriers [CLAUDE.md, /health endpoint confirmed]
  - Retrieval: Top-1=0.30, Top-5=0.56, Top-10=0.62, MRR=0.40 [confirmed]
  - Reranker: MRR to 0.42 (+3.1%), below 5% threshold [confirmed]
  - 40% miss rate (20/50 queries) [rag_experiment_history.md Experiment 3]
  - Confidence gate: cosine similarity ≥ 0.25 [src/rag/config.py]
  - Embedding model: all-mpnet-base-v2, 768-dim [confirmed]
  - 50 evaluation queries, 25 barrier families [confirmed]
- **Cross-domain narrative section structure (ratified Q3 verdict):**
  This is HYBRID with four named sections. CCCLI scaffolds sections 1 and 2;
  GNSR writes sections 3 and 4 (~300–400 words of GNSR voice):
  1. *Corpus design assumption* (CCCLI): what v1 corpus covered and why it was built
     generically across 526 incidents
  2. *Observed failure* (CCCLI): what retrieval looked like when queried for LOC
     barriers against the full corpus; the structural mismatch
  3. *Diagnosis* (GNSR): why the mismatch occurred — training generality vs retrieval
     specificity; the decision to scope v2 to the 156 cascading training incidents
  4. *Fix* (GNSR): how the 4-stage intersection filter + v2 corpus build resolved it;
     what D017 added (PIF _value text, investigator recommendations)
- **Wordcount estimate:** 700–900 words
- **Why this chapter for THIS project:** The RAG system went through 3 explicit
  experiments with a quantitative assessment framework. The reranker was kept optional
  based on a pre-declared 5% MRR threshold that the measured +3.1% did not clear. The
  v1→v2 corpus scoping decision — motivated by matching the training distribution —
  is an architectural choice specific to this project's cascading model design.
- **Author mode:** HYBRID (cross-domain narrative sections 3–4 are GNSR-WRITES;
  sections 1–2 and all pipeline/evaluation scaffolding are CCCLI-SCAFFOLDS)

---

## Chapter 6: The Frontend — Interactive Bowtie and the P0/P1/P2/P3 State Machine

- **Filename:** `docs/journey/06-frontend-ux.md`
- **Summary:** The system is accessed through a custom interactive SVG bowtie diagram
  built in Next.js 15. This chapter explains two design decisions: why a custom SVG
  (`BowtieSVG.tsx`) was written instead of using React Flow, and how the "cold load"
  state machine guides users through a scenario progressively. The P0/P1/P2/P3 state
  machine — blank (P0), top event set but no barriers (P1, prompt appears), barriers
  added but unanalyzed (P2, grey barriers + analyze banner), conditioning barrier
  selected (P3, cascading predictions active) — prevents dead-end UI states and
  surfaces the right affordance at each step. The chapter also covers K001 (SVG
  coordinate changes require manual browser verification), the debounced 300ms
  cascading trigger, and the implicit barrier-count constraint from the pair-feature
  model.
- **Sources:**
  - `frontend/components/diagram/BowtieSVG.tsx` (SVG rendering; P1 prompt at line 606)
  - `frontend/components/diagram/PathwayView.tsx` (pathway view, unanalyzed styling)
  - `frontend/context/BowtieContext.tsx` (state management, cascading vs legacy flow)
  - `frontend/hooks/useAnalyzeCascading.ts` (debounced 300ms at line 28; parallel
    predict+rank calls)
  - `frontend/hooks/useExplainCascading.ts` (explain-on-barrier-click)
  - `frontend/components/panel/DetailPanel.tsx` (drill-down panel, SHAP waterfall)
  - `frontend/components/dashboard/DriversHF.tsx` (global SHAP chart, Apriori table)
  - `frontend/components/sidebar/BarrierForm.tsx` (canAnalyze gate at line 97:
    `barriers.length > 0`)
  - `docs/knowledge/KNOWLEDGE.md` K001, K002 (SVG coordinate change gate)
  - `docs/decisions/DECISIONS.md` D015 (S05/S06 human-led, K001)
  - Recent commits: `1d58718` (P2 grey barriers + analyze banner),
    `d9f0e39` (P1 partial-state prompt), `a8323bc` (custom SVG replacing React Flow)
- **Numbers to verify:**
  - 19 frontend test files, 248 tests passing [confirmed by vitest run]
  - 300ms debounce on cascading trigger [useAnalyzeCascading.ts:28]
  - `canAnalyze = barriers.length > 0` (≥1 gate in UI) [BarrierForm.tsx:97]
  - BowtieSVG SVG coordinate constants [verify in BowtieSVG.tsx before citing]
- **BowTieXP visual language fidelity (Q5 verdict — no BOWTIE_DIAGRAM_SPEC.md exists):**
  > "The BowTieXP visual language fidelity is documented in git commit history
  > (`feat(diagram)` series, most recently `1d58718`, `d9f0e39`, `a8323bc`). The
  > current SVG specification lives in `frontend/components/diagram/BowtieSVG.tsx`
  > as the canonical source — there is no separate spec document."
- **Implicit barrier-count constraint (cite same as Ch 3, adapted for UX framing):**
  The UI gates on `barriers.length > 0` (≥1 barrier) to enable the Analyze button
  (`BarrierForm.tsx:97`). The deeper constraint — that meaningful cascading predictions
  require at least one conditioning and one target barrier — is implicit in the
  prediction loop (`predict.py:248–250`), not enforced at the UI or API validation
  layer. A single-barrier scenario passes the UI gate and the API returns 200 OK with
  an empty predictions list.
- **Wordcount estimate:** 600–800 words
- **Why this chapter for THIS project:** The BowtieSVG is the primary user-facing
  artifact. The P0/P1/P2/P3 state machine is a UX engineering choice specific to this
  domain — a blank bowtie has no useful predictions; the UI must guide the user to
  build enough context before analysis. A generic Next.js frontend chapter lists
  components; this chapter explains *why* the state machine exists and *what* it
  prevents.
- **Author mode:** HYBRID — GNSR writes the P0/P1/P2 design rationale (progressive
  guidance over blank canvas) and K001 rationale (why manual SVG verification is
  enforced). CCCLI fills in component structure, state management pattern, test
  coverage.

---

## Chapter 7: Deployment — From Code to Live Demo

- **Filename:** `docs/journey/07-deployment.md`
- **Summary:** The system runs on a self-hosted Ubuntu 24.04 server behind a
  Cloudflare Tunnel, reached at `bowtie.gnsr.dev`. This chapter documents the
  three-container Docker stack (nginx, FastAPI/uvicorn, Next.js standalone), the D007
  decision (self-hosting over Streamlit Community Cloud — Next.js + FastAPI is
  incompatible with Streamlit), the demo-day risk management strategy (video recording
  as fallback, local `docker compose` as secondary fallback), the GHA CI/CD pipeline
  that builds and pushes images to ghcr.io then fires a webhook to trigger the server
  to pull and restart, and the key container engineering choices that affect startup
  reliability.
- **Sources:**
  - `deploy/Dockerfile.api` (runtime image, COPY directives, healthcheck)
  - `deploy/Dockerfile.frontend` (standalone Next.js, HOSTNAME env var)
  - `deploy/nginx.conf` (reverse proxy config, /api/ prefix stripping)
  - `deploy/docker-compose.server.yml` (production stack)
  - `docker-compose.yml` (local dev stack)
  - `.github/workflows/deploy.yml` (build-api + build-frontend + trigger-deploy jobs)
  - `.github/workflows/ci.yml` (pytest + vitest on push/PR to main)
  - `docs/architecture/DEPLOYMENT_ENV.md` [read before authoring]
  - `docs/decisions/DECISIONS.md` D007 (self-hosting rationale and risk mitigation)
- **Numbers to verify:**
  - 3 containers: nginx (port 8080), api (port 8000), frontend (port 3000)
    [confirmed in nginx.conf, Dockerfiles]
  - TRANSFORMERS_OFFLINE=1, HF_HUB_OFFLINE=1 in runtime image [confirmed]
  - start_period: 60s for API healthcheck [confirmed in deploy/Dockerfile.api]
  - Image registry: `ghcr.io/sr-dotcom/bowtie-risk-analytics-oilgas-{api,frontend}`
    [confirmed in deploy.yml lines 49–50, 82–83]
- **GHA deploy story (verified Q6 — use this language in chapter):**
  > "GHA (`deploy.yml`) builds and pushes both Docker images to `ghcr.io` on every
  > push to `main`. A third GHA job then POSTs to a webhook at
  > `bowtie-deploy.gnsr.dev` that triggers the server to pull and restart containers
  > — this is the production deploy trigger. SSH-based deploy (`deploy.sh`) is
  > available as a manual fallback. The GHA build jobs and the webhook call are
  > structurally decoupled: `continue-on-error: true` on the webhook step means image
  > publication to ghcr.io and actual deployment are independent events."
- **Wordcount estimate:** 400–600 words
- **Why this chapter for THIS project:** D007 is a real engineering tradeoff (academic
  spec vs production reality), and the demo-day fallback strategy is process-safety
  thinking applied to the demo itself. A generic deployment chapter describes
  infrastructure; this one explains why the prescribed target was overridden and what
  risk management looked like for a live academic demonstration.
- **Author mode:** CCCLI-SCAFFOLDS — most content is technical description (container
  design, nginx config, GHA pipeline). GNSR writes only the D007 decision paragraph
  (~1 short paragraph on why self-hosting was chosen and the
  single-point-of-failure acknowledgment).

---

## Chapter 8: Lessons Learned

- **Filename:** `docs/journey/08-lessons-learned.md`
- **Summary:** A reflective chapter on what the project revealed about building
  ML-backed process safety tools. Three substantive lessons: the D008 cascade model
  pivot (switching ML architecture mid-project after domain expert review) showed that
  domain expertise must precede model design, not follow it; the D016 y_hf_fail Branch
  C outcome (a model that didn't generalize, buried by sample-size ceiling on
  HF-positive incidents) showed the limits of mining from a 156-incident corpus; and
  the RAG 40% miss rate showed that retrieval quality is bounded by corpus coverage,
  not ranking sophistication. The chapter is also honest about what the system cannot
  do: predict novel scenarios not in training; provide precedent for the 40% of
  barrier queries with no historical match; and cover explosion and fatality
  consequence types excluded by the LOC scope.
- **Sources:**
  - `docs/decisions/DECISIONS.md` D008 (cascade pivot), D016/D019 (Branch C)
    — D012 excluded per Q8 verdict
  - `docs/evaluation/EVALUATION.md` (RAG Top-1=0.30, 40% miss rate)
  - `docs/knowledge/KNOWLEDGE.md` (project-wide lessons M001–M003)
  - `docs/evidence/sprint/post-demo-fix-list.md` (known issues as of Apr 25)
  - `docs/tech-debt.md` [read before authoring]
- **Numbers to verify:**
  - y_hf_fail AUC 0.5562, Branch C activated [DECISIONS.md D016]
  - RAG Top-1=0.30, 40% miss rate [confirmed]
  - 156 cascading incidents (LOC scope) [confirmed]
- **Wordcount estimate:** 500–700 words
- **Why this chapter for THIS project:** Prof. Ageenko will evaluate critical
  self-assessment. This chapter must explain *why* y_hf_fail was hard (sample-size
  ceiling), *why* the LOC scope was the right constraint (not arbitrary limitation),
  and what it would take to generalize beyond BSEE/CSB. These require domain
  understanding, not just metrics.
- **Author mode:** GNSR-WRITES — CCCLI contributes only verified numbers and pointers
  to specific decision register entries. The prose is GNSR's.

---

## Cross-cutting elements

### Hero diagram for root README

The README currently has a project structure section and quick start but no single
diagram capturing what the system does end-to-end. The hero diagram should show:

> A horizontal flow: `BSEE/CSB PDFs → Claude LLM Extraction → Schema V2.3 →
> Cascading XGBoost + SHAP → RAG v2 Evidence → Interactive Bowtie Dashboard`.
> Two output lanes: "Which barrier will fail?" (cascade model, risk tier badge) and
> "Why has this barrier type failed before?" (RAG retrieval, evidence narrative).
> Request path overlay: user defines scenario → clicks conditioning barrier →
> `/predict-cascading` + `/explain-cascading` in parallel → SHAP waterfall +
> evidence narrative in drill-down panel.
>
> Adapt the existing layered ASCII in `docs/architecture/ARCHITECTURE.md` into
> a Mermaid flowchart.

### Mermaid diagrams across chapters

| Chapter | Diagram |
|---------|---------|
| Ch 1 | Bowtie topology: threats → prevention barriers → top event → mitigation barriers → consequences. LOD tiers labeled. |
| Ch 2 | Ingestion pipeline: PDF → `extract-text` → `extract-structured` (Haiku → Sonnet) → Schema V2.3 → `build-combined-exports` → controls CSV |
| Ch 3 | Pair-feature construction: two barriers → 18 features → XGBoost → y_fail_probability + SHAP |
| Ch 5 | 4-stage RAG: barrier_query + incident_query → dual FAISS → intersection → RRF → ContextBuilder → LLM narrative |
| Ch 6 | P0/P1/P2/P3 state transitions: blank → top event set → barriers added (unanalyzed) → conditioning selected (predictions live) |

### Sub-READMEs warranted

| Directory | Warrant? | Reason |
|-----------|----------|--------|
| `tests/` | Yes | Flat structure is intentional; document why and how to run with venv |
| `data/evaluation/` | Yes | Committed artifacts; explain what each file is and how to reproduce |
| `scripts/` | Yes | Mix of one-shot utilities and reproducible pipeline steps; document which is which |
| `src/modeling/cascading/` | Yes | Most active ML module; document pair-building contract and feature contracts |
| `frontend/__tests__/` | No | Vitest tests self-document |
| `configs/` | Maybe | If Ch 4 cites YAML mapping files extensively |

---

## Open questions for GNSR

Questions Q1–Q8 are resolved and baked into the chapters above.

9. **Dead reference in docs/requirements.md:93** (NEW — Q9): `docs/requirements.md`
   line 93 references `docs/reference/BOWTIE_SVG_SPEC.md`, which does not exist (same
   family as the BOWTIE_DIAGRAM_SPEC.md non-existence confirmed in Q5). This is a
   dead reference in a current tracked document. Flag for Phase 4 internal-link audit.
   Recommended action: remove the reference from `docs/requirements.md:93`. Do not
   create the file. Defer to post-Apr-27 cleanup; do not touch in this restructure.

10. **K-DEPLOY-06 residual flag** (NEW — Q10): `deploy.yml` still has
    `continue-on-error: true` on the webhook step with the comment "Phase 6 lands the
    Cloudflare route." The Cloudflare route is clearly functional (site is live), so
    this comment is stale. K-DEPLOY-06 status is "residual flag, not ongoing
    limitation." Update `docs/knowledge/KNOWLEDGE.md` K-DEPLOY-06 entry post-Phase-3
    to reflect resolved state. Defer to post-Apr-27 cleanup; do not modify in this
    restructure.

---

## Summary statistics

| | |
|---|---|
| Total chapters | 8 |
| GNSR-WRITES | 2 (Ch 1 — The Problem, Ch 8 — Lessons Learned) |
| CCCLI-SCAFFOLDS | 1 (Ch 7 — Deployment) |
| HYBRID | 5 (Ch 2, 3, 4, 5, 6) |
| Estimated total wordcount | 4,500–6,100 words |
| Open questions remaining | 2 (Q9, Q10 — deferred cleanup items, non-blocking) |
| Numbers to verify before authoring | ~28 specific claims across 8 chapters |
