# Bowtie Risk Analytics — Handover Document

> Authoritative handover artifact for receivers (Todus Advisors team).
> Generated 2026-05-02.
> Read this in conjunction with `KNOWN_ISSUES.md` for the full project context.

---

# Project Summary

Bowtie Risk Analytics is a machine-learning system that predicts process safety barrier failure in oil and gas Loss-of-Containment scenarios, grounded in 156 real incident investigations from the US Bureau of Safety and Environmental Enforcement (BSEE) and the US Chemical Safety Board (CSB). Given a bowtie diagram describing a hazardous scenario — a top event, its threats, its barriers, its consequences — the system predicts which barriers are most likely to fail using a cascading XGBoost model, explains each prediction with SHAP feature attributions, and surfaces similar historical incidents via a 4-stage hybrid RAG pipeline (BM25 + dense embeddings + reranking + RRF fusion).

Built as a UNC Charlotte MS practicum project (graduation May 2026); demoed Apr 27, 2026 to academic supervisor and process safety domain expert evaluator. Currently being prepared for handoff to Todus Advisors for review and potential AWS-platform extension.

# Definition of Done

The handover is "done" when all six conditions hold:

1. **Tests pass on fresh clone** — `pytest` (backend) and `npm test` (frontend) both green from `git clone` + clean install. Specific gate numbers (≥565 backend, ≥192 frontend) are documented in `CLAUDE.md` and `tests/README.md`.
2. **No lint or type errors** — `ruff` clean and `mypy` clean (Python); TypeScript / ESLint clean (frontend).
3. **README and CLAUDE.md current and accurate** — manual review by project lead at handover; no broken file references, no stale install commands, no contradictions with on-disk code.
4. **Demo runs end-to-end on fresh clone** — `git clone && docker compose up` (or `docker compose -f deploy/docker-compose.server.yml up` for the single-container production path on port 8080) produces a working frontend at `localhost:80` with API reachable at `localhost:80/api/health`.
5. **Hosted demo green at handover moment OR fresh-clone fallback verified** — either `bowtie.gnsr.dev` is up and `/health` returns ok at handover, OR project lead has personally re-run condition 4 within 24 hours of handover.
6. **HANDOVER.md and KNOWN_ISSUES.md generated and reviewed** — both docs read end-to-end by project lead before delivery.

# First 30 Minutes for the Receiver

The path that produces a working understanding fastest:

1. **Visit `https://bowtie.gnsr.dev`** (or `https://bowtie-api.gnsr.dev/health` to verify the backend is up). Click "Load BSEE example" in the sidebar, then "Analyze Barriers". Click any barrier in the diagram. Watch the Drivers & HF tab populate. This is the demo that shipped; if you cannot get past this, the rest will not click.
2. **Read `README.md`** for what it does, why it exists, and the journey-chapter index. Read journey chapters 1, 7, and 8 — the problem statement, the deployment topology, and the lessons learned.
3. **Read `KNOWN_ISSUES.md`** (the receiver-facing limitations doc generated at handover) to know what's deferred and why.
4. **For local reproduction:** clone, `python3 -m venv .venv && source .venv/bin/activate && pip install -e .`, then `cp .env.example .env` and add an `ANTHROPIC_API_KEY`. Backend: `uvicorn src.api.main:app --reload --port 8000` (per D004, the API uses a module-level `app` instance, not the `--factory` pattern). Frontend: `cd frontend && npm install && npm run dev`. Open `localhost:3000`.
5. **For Docker reproduction:** `docker compose up --build` brings up the three-service stack (API + frontend + nginx). Open `localhost:80`.
6. **For cascading model internals:** read `src/modeling/cascading/README.md` and `docs/journey/03-cascade-model.md`. The pair-feature construction, the GroupKFold cross-validation methodology, and the SHAP explainability path are all here.
7. **For RAG internals:** read `docs/evaluation/rag_system_overview.md` and `docs/journey/05-rag-retrieval.md`. The 4-stage hybrid pipeline, the domain filter, and the evaluation harness are documented end to end.
8. **For decisions:** `docs/decisions/DECISIONS.md` is the canonical register. Each decision links the constraint that produced it. Cross-reference with `KNOWN_ISSUES.md` Deliberate Deferrals before changing anything in `src/_legacy/`, the threshold files, or the deploy/ topology.

# Architectural Decisions

The full decision register lives at `docs/decisions/DECISIONS.md` (D001 through D020). Key decisions a maintainer should know:

- **D001** — Move V1 legacy code to `src/_legacy/`, do not delete. Removed only when all production imports are migrated. Status: legacy still imported by 14 production files across 9 modules at handover; deletion deferred to M005.
- **D006** — Risk thresholds calibrated at p60=0.45, p80=0.70 for HIGH/MEDIUM/LOW tiering. Canonical file: `configs/risk_thresholds.json`. Reproducible per retrain. Do not edit `data/models/artifacts/risk_thresholds.json` directly.
- **D007** — Self-hosted Ubuntu mini-PC + Docker + Cloudflare Tunnel chosen over Streamlit Community Cloud. Architecture is a two-process stack (FastAPI + Next.js) that Streamlit Cloud cannot host. Documented fallback: `docker compose up` from any host with Docker installed reproduces the stack.
- **D008** — Pivot from single-stage barrier prediction (M001/M002) to cascading pair-feature model (M003). Result: GroupKFold AUC 0.763 ± 0.066 on `y_fail_target`.
- **D011** — Performance Influencing Factors (PIFs) excluded from cascading model features. Retained as incident metadata in Schema V2.3 and surfaced in RAG narrative output (D018, D020).
- **D012** — Authority structure: Naga Sathwik Reddy Gona = project lead and primary engineer. Patrick Hunter, Jeffrey Arnette, Nithin Sai Kumar Bandarupalli = teammates with equal contribution. Dr. Ilieva Ageenko = academic supervisor. Fidel Ilizastigui Perez = process safety domain expert evaluator.
- **D016 / D019** — Pre-registered branch-activation logic for `y_hf_fail` secondary target. Result was AUC 0.556 ± 0.118 — below the 0.60 floor — so Branch C was activated and the `y_hf_fail` model is not surfaced in production. Decision logic was tested under unambiguous results; borderline cases untested.
- **D017** — RAG corpus scope expanded to include PIF `_value` text + event recommendations. Domain filter (`OIL_GAS_AGENCY_ALLOWLIST`) added to eliminate cross-domain retrieval (e.g., chemical-plant incidents surfacing for offshore oil/gas queries).

The journey chapters at `docs/journey/01–08` provide narrative context for these decisions.

# Deliberate Deferrals — DO NOT "FIX"

These are not bugs. Each is a deliberate engineering choice with a documented constraint or trade-off. A future maintainer "fixing" any of these without revisiting the underlying constraint will introduce a regression.

- **DEFERRED**: Mobile-specific responsive layout work — desktop-only is the M003 product surface. The system intentionally does not provide mobile breakpoints; a maintainer adding mobile rules anywhere in the frontend is doing post-M003 work, not fixing a defect. Documented in `docs/tech-debt.md`. Scope: M005+.
- **DEFERRED**: `src/_legacy/` deletion at `src/_legacy/**` — 14 imports across 9 production files reference modules in this directory. Deletion will break runtime. Migration path is M005 work (4-8 hours). Scope: M005.
- **DEFERRED**: PIF Prevalence chart in Drivers & HF tab at `frontend/components/dashboard/DriversHF*` — intentionally cut from M003 scope per audit Q2; reinstatement requires retrieval-side aggregation. Scope: M005+.
- **DEFERRED**: GHA-built per-service images vs. production combined image — `.github/workflows/deploy.yml:build-api` and `:build-frontend` build and push to GHCR but the production stack pulls a combined `:latest` built from root `Dockerfile`. Asymmetry is documented in `KNOWN_ISSUES.md` §2.2 and `docs/journey/07-deployment.md`. Scope: future infra cleanup, not handover.
- **DEFERRED**: `data/rag/archive/v1/` retains ~16 MB of legacy embeddings/datasets in git history — `git rm --cached` would untrack going forward but not reduce history size. Actual cleanup requires `git filter-repo` rewrite + force-push coordination. Scope: planned LFS migration.
- **DEFERRED**: SHAP TreeExplainer is not serialized — recreated at API startup from the trained XGBoost model. The pattern lives in `src/modeling/cascading/predict.py` and `src/modeling/explain.py`. TreeExplainer cannot be safely serialized via joblib/pickle. Do not introduce serialization helpers in either module. Scope: never.
- **DEFERRED**: `BarrierExplainer` calls LLM via `asyncio.to_thread()` in `src/api/main.py` — `AnthropicProvider.extract()` is blocking (`requests.post`); the FastAPI endpoint wraps it in `asyncio.to_thread()` to avoid blocking the event loop. Do not refactor to bare `await` — the underlying provider is not async-native. Scope: never (until provider becomes async-native).
- **DEFERRED**: `production docker-compose.server.yml` pulls `:latest` without pinning at `deploy/docker-compose.server.yml` — any rebuild on the server pulls whatever `:latest` resolves to. For production-grade pin, replace with the demo tag `v1.0-apr27-demo` (or future release tag) and rebuild. Scope: future infra cleanup, not handover.
- **DEFERRED**: `bowtie-deploy.gnsr.dev` Cloudflare Tunnel route not yet added at `.github/workflows/deploy.yml:trigger-deploy` — step runs with `continue-on-error: true` so it does not fail the workflow. Manual `ssh gmk ./deploy.sh` is the reliable deploy path. Scope: 15-minute UI configuration, future.
- **DEFERRED**: `risk_thresholds.json` exists in two locations — canonical at `configs/risk_thresholds.json` per D006, and as training output at `data/models/artifacts/risk_thresholds.json` (gitignored, reproducible per-retrain). Do NOT manually edit the artifacts copy without promoting to configs. Documented in `data/README.md`. Scope: documentation only.
- **DEFERRED**: Fidel Comment #55 — 5-category barrier-type taxonomy expansion. Implementation requires LLM re-extraction of all 739 incidents (cost-significant). Cannot be cherry-picked without breaking the cascade feature contract. Scope: M005+.
- **DEFERRED**: `y_hf_fail` secondary target dropped from production per D016 Branch C. Sample-size ceiling (56/156 incidents carry HF positives) is the cause, not feature engineering. Re-attempt only if corpus grows materially (e.g., adding PHMSA + TSB at full barrier-level detail). Scope: post-corpus-expansion.
- **DEFERRED**: Scenario builder is fully user-built per L001 — no incident-viewer mode. Pre-loaded BSEE example available via sidebar; M002 four-tab dashboard removed and must not be reintroduced. Scope: M005+ for full edit-mode UX.

# Known Issues

Every other previously-flagged issue from the Apr 24 audits has been verified RESOLVED via live demo testing on 2026-05-02. The single remaining known issue at handover:

- **ISSUE** [high]: Mobile layout broken at viewports < 768 px at `frontend/app/**` — sidebar covers SVG; bowtie diagram invisible. Documented in `docs/tech-debt.md`. Acceptable given desktop-only M003 scope, but explicit so receiver does not assume mobile responsiveness exists.

# Looks Bad But Is Fine

These are findings the audit flagged that were rejected after triage as not requiring action. Documented here so a future auditor doesn't re-raise them.

- **F018 — Audit flagged a circular-dependency risk between `src/modeling/explain.py` and `src/modeling/feature_engineering.py`.** No cycle exists today. If a future change introduced one, Python's import system raises ImportError at import time — the safeguard is mechanical and immediate. Preventive documentation provides no additional safety beyond what Python already enforces.
- **F019 — Audit flagged the "kept for one release cycle" comment on the `validate_incident_v2_2` alias as stale.** This is the same line of code as F009 (above, FIX), which deletes the alias entirely. When the alias is deleted, the comment goes with it. F019 is closed by F009's fix — no separate work needed.
- **Drivers & HF tab Section 2 dynamically swaps content based on selection state** — cold view shows scenario-level Context Factors Prevalence chart; click view shows barrier-specific Degradation Context (RAG-driven). Both states are fully populated; the content changes by design. The Apr-24 audit framing of "DriversHF charts require barrier click to populate" was inaccurate — verified live on 2026-05-02.
# Out of Scope

Constraints that follow from the modeling approach and corpus, not bugs to be fixed:

- **Loss of Containment scope only** — training corpus is 156 BSEE + CSB incidents, US-regulatory record. System does not generalize to non-LOC top events (e.g., toxic release, mechanical failure outside containment) or non-US incident reporting regimes.
- **Domain expertise applied through review, not embodied in code** — CCPS taxonomy mapping, threshold calibration, and corpus scope are enforced by code; their domain meaning lives in `docs/decisions/DECISIONS.md` and review by Fidel Ilizastigui Perez. A maintainer without process-safety context can make changes the code cannot flag as domain-incorrect.
- **High availability, multi-region, staged rollout** — single self-hosted server with explicit single-point-of-failure per D007. Local Docker Compose fallback documented.
- **Production-grade observability** — structured logging exists; distributed tracing, drift monitoring, and runtime error capture (e.g., Sentry) are not installed.
- **Real-time retraining or scheduled corpus refresh** — corpus is frozen at 156 incidents for M003. Pipeline is reproducible per `scripts/build_rag_v2.py` and `scripts/retrain_from_parquet.py`, but no scheduler.
- **API rate limiting per-user / per-key** — single shared `BOWTIE_API_KEY` is the protection at API layer. Per-IP / per-key rate limiting deferred to before any public deployment.

> **Operational note:** The webhook bearer token used by `.github/workflows/deploy.yml:trigger-deploy` was visible in CLI session output during initial deploy. It was never committed to git (verified via `git log -S` history scan). Rotation is recommended for the project lead's own server but is not action-required for a receiver standing up their own infrastructure.

# Recommendations for Cleanup

Three Phase 3 cleanup batches are scoped for the receiver (or a future contributor) to execute:

**Batch 1 — low-risk file moves and tooling installs (no fact-gather needed):**
- Archive 7 STALE plans to `docs/archive/plans/` and `docs/archive/handoff/`
- Archive `00_CURRENT_STATE.md` to `docs/archive/state/`
- Delete `SESSION_REPORT.md` (single-session log; redundant with git history)
- Create `docs/archive/README.md` (one paragraph: "historical artifacts preserved for provenance")
- Audit `docs/decisions/ADR-index.md` against on-disk file set; remove dead references or replace with "see DECISIONS.md D-NN" pointers
- Confirm `docs/decisions/DECISIONS.md` register is current up through D020 (no drift from commit-message references)
- **Install `ruff`** — add to `pyproject.toml` `[project.optional-dependencies] dev`. Configure under `[tool.ruff]` (line-length 100, target Python 3.12). Run first pass; fix or `# noqa` findings. Required for DoD Item 2.
- **Install `mypy`** — add to `pyproject.toml` `[project.optional-dependencies] dev`. Configure under `[tool.mypy]` with `strict_optional = true` minimum. Run first pass; fix or `# type: ignore[code]` findings. Required for DoD Item 2.
- **Verify TypeScript strict mode** — check `frontend/tsconfig.json` for `"strict": true`. If absent, enable + fix first-pass findings. ESLint default config from Next.js 16 should already pass.
- **Document lint/type commands** — update `CLAUDE.md` and `tests/README.md` so receiver knows the canonical invocations: `ruff check src tests scripts`, `mypy src`, `cd frontend && npx tsc --noEmit && npx eslint`.

**Batch 2 — verifications and small cleanups (fact-gather first):**
Run these eight commands and use output to drive batch decisions:
1. `git check-ignore -v archive/legacy_quarantine/`
2. `ls -R archive/legacy_quarantine/ | head -40`
3. `grep -rn "archive/legacy_quarantine" src/ scripts/ tests/`
4. `git ls-files | grep -E '(skills-lock|verification_screenshots_2026-04-25)'`
5. `grep -rn "archive/2026-04-20" --include="*.py" --include="*.md" --include="*.sh"`
6. `grep -rn "cascading_input" src/ scripts/ tests/ --include="*.py"`
7. `ls -la data/models/cascading_input/`
8. `git check-ignore -v data/models/cascading_input/`

Then resolve:
- `skills-lock.json`: if tracked → `git rm` + add to `.gitignore`. If untracked → verify gitignore line.
- `verification_screenshots_2026-04-25/`: if tracked → move to `docs/evidence/screenshots/2026-04-25/`. If untracked → leave.
- `archive/legacy_quarantine/`: revisit once (1)–(3) above are done. Decision DEFERRED.
- `archive/2026-04-20-project-root-cleanup/`: if grep is clean → `git mv` to `docs/archive/project-root-cleanup-2026-04-20/`.
- `data/models/cascading_input/`: revisit once (6)–(8) above are done. Decision DEFERRED — risk is fresh-clone breakage if pipeline expects this path and gitignore swallows it.
- **DEFERRED**: `vite <=6.4.1` path-traversal CVE (GHSA-4w7w-66w2-5vf9) in optimized-deps `.map` handling — dev-server only, not in production runtime. Surfaced as a remaining moderate after B.2 cleared the postcss + esbuild chains via `package.json` overrides. Fix requires bumping `@vitejs/plugin-react@4.7.0` off `vite@5`, which cascades peer-dep upgrades with uncertain breakage. Production builds and runtime are unaffected. Scope: when `@vitejs/plugin-react` ships a vite-6-compatible release, re-evaluate.

**Batch 3 — doc updates:**
- Add a paragraph to `data/README.md` documenting `risk_thresholds.json` canonical-vs-training-output relationship per D006.
- Update root `README.md` Python version requirement to `3.12` (current text says `3.10+`; pyproject says `>=3.12`).

# Recommendations for Cleanup §B — Audit-driven Phase 3 batches

A 19-finding tech-debt audit (F001–F019) was conducted and triaged. Result: **17 FIX, 0 DEFER, 2 REJECT**. The 17 fixes cluster into 7 logical commits below, executed in order. Each batch must be followed by `pytest -q` (≥565 passing) and `cd frontend && npm test -- --run` (≥192) before proceeding.

The two REJECTs (F018 circular-dependency comment, F019 deprecated-alias comment) are documented in §Looks Bad But Is Fine below.

**Batch B.1 — quick wins (`chore: ruff autofix + dead code removal + CORS default cleanup`):**
- F011: delete unused `MappingConfig` import from `src/api/main.py:38` (ruff autofix)
- F012: delete unused `TOP_K_RERANK`, `FINAL_TOP_K` from `scripts/evaluate_retrieval.py:30` (ruff autofix)
- F013: delete unused `sys` from `scripts/build_demo_scenarios.py:32` (ruff autofix)
- F014: remove `f` prefix from 4 empty f-strings in `src/modeling/cascading/data_prep.py:231,232,250,257` (ruff autofix)
- F009: delete dead `validate_incident_v2_2 = validate_incident_v23` alias from `src/validation/incident_validator.py:28` (zero callers verified by audit)
- F016: in `src/api/main.py:244-245`, change CORS default from `"https://bowtie.gnsr.dev,http://localhost:3000"` to `"http://localhost:3000"`. In `.env.example`, document the production hostname as a starter example, not a hardcoded code fallback.

Run `python3 -m ruff check src/ scripts/ --fix` for F011–F014. Manual edits for F009, F016.

**Batch B.2 — npm CVE clearance (`chore(deps): postcss override + vitest 4.x upgrade — clear all 7 npm CVEs`):**
- F001 Chain A: add `"overrides": { "postcss": ">=8.5.10" }` to `frontend/package.json`. Run `npm install`. Verify `npm audit` clears the postcss + next entries. Verify `npm run build` passes.
- F001 Chain B: upgrade `vitest` to `4.1.5` (semver major). Run `npm install`. Run frontend test suite — gate ≥ 192 passing.
- **Phase 3 fallback if Chain B breaks tests:** roll back vitest to current version, accept the 5 dev-dep warnings, retag F001 as PARTIAL-FIX with Chain B documented in the **Deliberate Deferrals** section above.

**Batch B.3 — fresh-clone fix for cascading training input (`feat: track curated training input + add fresh-clone guard`):**
- F002 part 1: `git add -f data/models/cascading_input/barrier_model_dataset_base_v3.csv` (the `-f` is required because parent path is currently caught by `/data/*` gitignore)
- F002 part 2: add gitignore allow-line near existing `data/` exceptions: `!/data/models/cascading_input/` with comment `# Cascading training input — tracked per Patrick's OK to publish`
- F002 part 3: add FileNotFoundError guard to `src/modeling/cascading/data_prep.py:78`:
  ```python
  if not _DEFAULT_CSV.exists():
      raise FileNotFoundError(
          f"Training input not found: {_DEFAULT_CSV}\n"
          "Expected to be tracked in git. Run `git lfs pull` if your clone "
          "used LFS, or re-clone the repo. The file is committed at this path."
      )
  ```
- F002 part 4: update CLAUDE.md Prerequisites section: add a one-line bullet noting that `data/models/cascading_input/barrier_model_dataset_base_v3.csv` ships with the repo and is required for `data_prep.py` to run.

**Batch B.4 — structured logging discipline (`refactor: structured logging discipline`):**
- Pre-step (30 seconds): confirm existing logger convention via `grep -nE 'logging.getLogger' src/api/main.py src/llm/anthropic_provider.py`. Match the pattern found; default to `logger = logging.getLogger(__name__)` if no precedent.
- F003: add `import logging` + `logger = logging.getLogger(__name__)` to top of each: `src/modeling/cascading/predict.py`, `src/modeling/cascading/pair_builder.py`, `src/rag/vector_index.py`, `src/rag/retriever.py`, `src/rag/context_builder.py`. Replace any `print()` with `logger.debug()`.
- F004: in `src/api/main.py`, change `logger.error(...)` to `logger.exception(...)` at lines 385, 448, 581. Lines 136, 147, 347 already correct.
- F005: in `src/ingestion/structured.py` (lines ~248, 306, 346, 357) and `src/corpus/extract.py` (lines ~150, 200), each `except Exception` block must call `logger.exception(...)` not `logger.error(...)`.
- F007: in `src/modeling/explain.py:348-376`, add `logger = logging.getLogger(__name__)` (logging already imported line 22). Replace 10+ `print()` statements with `logger.info()` or `logger.debug()`.
- F008: in `src/modeling/cascading/mini_gate.py` lines ~111-119, replace `print()` with `logging`. Leave `data_prep.py` and `train.py` print statements alone (CLI-primary; `__main__` invocation acceptable).

Watch stderr during test run for any unexpected log output (Python's lastResort handler may surface previously-silent warnings — investigate if observed).

**Batch B.5 — D001 contradiction fix (`docs: resolve D001 _legacy import contradiction in CLAUDE.md + add M005 backlog item`):**
- F006 part 1: edit `CLAUDE.md` `_legacy` section to add the exception sentence:
  > Exception: `src/pipeline.py`, `src/analytics/__init__.py`, and `src/models/__init__.py` retain `_legacy` imports per D001 until the legacy coverage analysis is removed. Tracked as M005 backlog item; see `KNOWN_ISSUES.md` Deliberate Deferrals for receiver-side context.
- F006 part 2: add a new entry to the M005 backlog (location: `docs/plans/M005-backlog.md` or similar; if no such file exists, create one):
  > **M005-NN — Remove `_legacy` imports from `pipeline.py`, `analytics/__init__.py`, `models/__init__.py`** (closes D001 exit condition). Effort: 4–8 hours. Touches: 14 imports across 9 production files. Verify legacy coverage analysis still functions or is intentionally retired before removal.

**Batch B.6 — hf_recovery archival (`refactor: move hf_recovery.py to archive/disabled-experiments/ (D016 honored, src/ kept clean)`):**
- F015 part 1: create `archive/disabled-experiments/` if it doesn't exist
- F015 part 2: `git mv src/modeling/cascading/hf_recovery.py archive/disabled-experiments/hf_recovery.py`
- F015 part 3: add `archive/disabled-experiments/README.md` (or update existing archive README) noting:
  > `hf_recovery.py` — implements y_hf_fail Branch C path. Disabled per D016 (AUC 0.556 below 0.60 floor). Retained as runnable reference per D016; moved here from `src/modeling/cascading/` per F015 (TRIAGE 2026-05-02) to keep active source tree clean. Restorable via `git mv archive/disabled-experiments/hf_recovery.py src/modeling/cascading/`.
- F015 part 4: verify no active code imports `hf_recovery` post-move (`grep -rn "hf_recovery" src/ tests/ scripts/` should be empty after move; if any imports remain, those are dead too and should be removed in the same commit).

**Batch B.7 — type tightening + test-skip warning (`chore: tighten lifespan_override type + add cascade-artifact-missing test warning`):**
- F010: in `src/api/main.py:213`, change `def create_app(lifespan_override: Any = None) -> FastAPI:` to `def create_app(lifespan_override: Optional[Callable[..., AsyncContextManager[None]]] = None) -> FastAPI:`. Add to imports: `from typing import Optional, Callable` and `from contextlib import AsyncContextManager`.
- F017: add or update `tests/conftest.py` with a session-scoped fixture that emits a loud warning at the start of every pytest run if `data/models/artifacts/xgb_cascade_y_fail_pipeline.joblib` is absent:
  ```python
  import pytest
  from pathlib import Path
  import warnings

  @pytest.fixture(scope="session", autouse=True)
  def _warn_on_missing_cascade_artifacts():
      artifact = Path("data/models/artifacts/xgb_cascade_y_fail_pipeline.joblib")
      if not artifact.exists():
          warnings.warn(
              f"\n\n  WARNING: 7 cascade prediction tests will skip — "
              f"`{artifact}` not found.\n"
              "  Run `python -m src.modeling.cascading.train` to generate the artifact.\n",
              UserWarning,
              stacklevel=1,
          )
  ```
  Update `tests/README.md` to document the artifact prerequisite explicitly.


---

## About this document

Generated 2026-05-02 from the internal handover-prep protocol. The full triage and decision history is preserved in repo branches and commit messages on `branch/restructure-cleanup` (14 cleanup commits, all behind `git log v1.0-apr27-demo..HEAD`).

For deeper context, read in this order: `README.md`, `CLAUDE.md`, this `HANDOVER.md`, `KNOWN_ISSUES.md`, then `docs/journey/01–08`.
