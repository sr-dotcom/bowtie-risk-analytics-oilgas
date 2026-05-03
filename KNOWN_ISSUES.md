# Bowtie Risk Analytics — Known Issues

> Authoritative list of open defects, deferred decisions, architectural caveats, domain-data caveats, and post-handover cleanup history. Generated 2026-05-02.
> 
> Read this in conjunction with `HANDOVER.md` for the full project context.

---


This document is the single source of truth for known defects, architectural caveats, operational risks, domain constraints, and deferred work for the Bowtie Risk Analytics system at handoff. It supersedes the pre-demo `POST_DEMO_FIX_LIST.md` snapshot. Where a finding has been resolved, the resolving commit is cited; where it remains open, severity and recommended scope are stated.

**Audience:** anyone reviewing, reusing, or extending this codebase after the practicum demo.
**Snapshot anchor:** `branch/restructure-cleanup` @ `595978d` · tag `v1.0-apr27-demo` @ `592bfa9`.
**Audit basis:** `docs/audits/HOSTED_DEMO_AUDIT_2026-04-24.md` + `docs/audits/LIVE_AUDIT_CHROME_2026-04-24.md` + `docs/audits/STATUS_ADDENDUM.md` (current-state map).

---

## 1. Defects still open

Five items remain open from the two audits. None block the recommended demo path. All are documented in `docs/tech-debt.md` with priority and effort estimates.

| # | Defect | Severity | Scope |
|---|---|---|---|
| 1.1 | Mobile layout broken at viewports < 768 px (sidebar covers SVG; bowtie diagram invisible). Desktop-only system. | High | M005+ — multi-hour responsive rebuild |
| 1.2 | PIF Prevalence chart absent from Drivers & HF tab. Intentional for M003 scope per audit Q2. | Medium | M005+ — reinstatement requires retrieval-side aggregation |
| 1.3 | SVG container aspect ratio mismatch on certain viewports. Cosmetic. | Low | Optional polish |
| 1.4 | SHAP y-axis labels wrap to 3 lines on long feature names. Cosmetic; readable. | Low | Optional polish |
| 1.5 | L-1 through L-10 from `LIVE_AUDIT_CHROME_2026-04-24.md` — design-spec / accessibility conformance items. None user-blocking. | Low | Iterative |

The recommended demo path (Diagram view → barrier click → Analyze Barriers → Ranked Barriers → SHAP detail panel) is end-to-end working on desktop. Drivers & HF tab works after a barrier is clicked but is partially empty before that.

---

## 2. Architectural caveats

These are choices that work as intended but carry constraints a future maintainer should understand before refactoring.

### 2.1 Production deployment uses combined `:latest` image; GHA-built per-service images are unused

The GHA workflow (`.github/workflows/deploy.yml`) builds two images — `ghcr.io/sr-dotcom/bowtie-risk-analytics-oilgas-api:latest` and `-frontend:latest` — using `deploy/Dockerfile.api` and `deploy/Dockerfile.frontend`. These get pushed on every push to main.

Production (`deploy/docker-compose.server.yml`) pulls `ghcr.io/sr-dotcom/bowtie-risk-analytics-oilgas:latest` — a **combined** single-container image built from the root `Dockerfile`. The per-service GHA images are never consumed by the production stack.

This asymmetry is documented in `docs/journey/07-deployment.md`. Manual `ssh gmk ./deploy.sh` builds the combined image on the server itself. Future cleanup: either align the GHA workflow to build the combined image, or refactor the server to consume per-service images.

### 2.2 Three Dockerfile sets coexist with explicit purpose

| File | Purpose |
|---|---|
| Root `Dockerfile` | Combined two-stage production build → produces `:latest` consumed by server |
| `deploy/Dockerfile.api` + `deploy/Dockerfile.frontend` + `docker-compose.yml` | Local development three-service stack (Docker DNS, port 80) |
| `deploy/Dockerfile.api` + `deploy/Dockerfile.frontend` | Production canonical, built/pushed by GHA — see 2.1 caveat |
| Root `nginx/nginx.conf` | DEV / HISTORICAL — header self-labels |
| `deploy/nginx.conf` | PRODUCTION CANONICAL — header self-labels |

Each file's header comment explicitly identifies its role and references the others. See `deploy/README.md` for usage.

### 2.3 `src/_legacy/` is actively imported by production code

The directory name suggests deletable code; it is not. Fourteen imports across nine production files reference modules in `src/_legacy/`. Migration to non-legacy paths is M005 work (estimated 4–8 hours). **Do not delete or aggressively refactor this directory before the migration is complete.**

### 2.4 `data/rag/archive/v1/` retains ~16 MB of legacy embeddings/datasets in git history

Three `.npy` and two `.csv` files were committed before the `/data/*` gitignore rule covered them. `git rm --cached` would untrack going forward but not reduce history size. Actual cleanup requires `git filter-repo` rewrite, which forces all commit SHAs to change. Deferred to a planned LFS migration.

### 2.5 SHAP TreeExplainer is recreated at prediction time, not serialized

By design — TreeExplainer cannot be safely serialized via joblib/pickle. Loaded from the trained XGBoost model at API startup. Documented in `CLAUDE.md` Gotchas section. Do not introduce serialization helpers.

### 2.6 `BarrierExplainer` calls LLM via `asyncio.to_thread()`

`AnthropicProvider.extract()` is blocking (`requests.post`); the FastAPI `/explain-cascading` endpoint wraps it in `asyncio.to_thread()` to avoid blocking the event loop. Do not refactor to bare `await` — the underlying provider is not async-native.

---

## 3. Operational caveats

These are real-world deployment risks and configuration requirements that are not visible from the codebase alone.

### 3.1 Webhook bearer token (project-lead operational note)

A bearer token used by `.github/workflows/deploy.yml:trigger-deploy` was visible in CLI session output during initial deploy setup. The token was never committed to git history (verified via `git log -S` historical scan).

This is a project-lead operational concern for the legacy self-hosted deployment, not an action required of receivers. Receivers standing up their own infrastructure (AWS or otherwise) will use their own credentials and need not consider this token. The legacy server-side rotation is GNSR's to handle on the gnsr.dev hosting if/when relevant.


### 3.2 Live `.env` is server-only

The live `.env` (mode 600) on `/opt/projects/bowtie-analytics/.env` contains real `ANTHROPIC_API_KEY`. Only `.env.example` ships in the repo. Replicating production requires populating `.env` from the example template with valid keys.


### 3.4 `deploy.sh` and webhook compose live on the server, not in the repo

The reliable production deploy path is `ssh gmk ./deploy.sh`, where `deploy.sh` lives at `/opt/projects/bowtie-analytics/deploy.sh` on the server. The webhook listener compose lives at `/opt/projects/webhook-bowtie/docker-compose.yml`.

These files are not currently in the repo. Reproducing the deploy on a fresh server requires recreating them following the steps in `deploy/README.md` (server bootstrap section) or referring to internal handoff notes.

### 3.5 Production stack pulls `:latest` without pinning

`deploy/docker-compose.server.yml` references `ghcr.io/sr-dotcom/bowtie-risk-analytics-oilgas:latest`. Any rebuild on the server pulls whatever `:latest` resolves to at that moment. There is no rollback to a known-good tagged image without changing the compose file. For a production-grade pin, replace `:latest` with the demo tag `v1.0-apr27-demo` (or a future release tag) and rebuild.

### 3.6 Cloudflare Tunnel is a single point of failure

Public access to `bowtie.gnsr.dev` and `bowtie-api.gnsr.dev` depends on the `cloudflared` daemon on the server. Documented fallback (D007): local `docker compose up` from any machine with Docker installed serves the same stack on `localhost:8080` (or `:3000` + `:8000` for the dev configuration).

### 3.7 `bowtie-deploy.gnsr.dev` route not yet added

The GHA `trigger-deploy` step POSTs to `https://bowtie-deploy.gnsr.dev/hooks/bowtie-analytics`. The Cloudflare Tunnel route for that hostname has not been added. The step runs with `continue-on-error: true` so it does not fail the workflow. Manual `ssh gmk ./deploy.sh` is the reliable deploy path until the route is added (15-minute UI configuration).

---

### 3.8 vite path-traversal CVE in `.map` handling (dev-only)

GHSA-4w7w-66w2-5vf9 — `vite <=6.4.1` exposes `.map` files via path traversal in optimized-deps handling. **Dev-server only**: production builds and runtime are unaffected. Surfaced as a residual after the B.2 npm audit cleanup (postcss + esbuild CVEs cleared via `package.json` overrides; this one remains because the fix requires bumping `@vitejs/plugin-react@4.7.0` off `vite@5`, cascading peer-dep upgrades with uncertain breakage).

A future maintainer running `npm run dev` should be aware. When `@vitejs/plugin-react` ships a `vite@6+`-compatible release, re-evaluate.

## 4. Domain and data caveats

These constraints follow from the corpus and the modeling approach. They are fixed properties of the M003 system, not bugs.

### 4.1 Loss-of-Containment scope is the corpus, not the universe

Training corpus: 156 BSEE + CSB incident investigations, US-regulatory record. The system does not generalize to non-LOC top events (toxic release, mechanical failure outside containment) or to non-US incident reporting regimes. The LOC scoping rationale is explained in `docs/journey/01-the-problem.md` and `02-corpus-design.md`.

### 4.2 Fidel Comment #55 — 5-category barrier taxonomy — deferred

Comment #55 calls for a richer barrier-type taxonomy than what the system currently uses. Implementing it requires LLM re-extraction of all 739 incidents (cost-significant). Documented as M005+ work. Cannot be cherry-picked into M003 without breaking the cascade feature contract.

### 4.3 `y_hf_fail` secondary target dropped from production

Per `DECISIONS.md` D016 Branch C: the human-factors-conditioned cascade model produced GroupKFold AUC 0.556 ± 0.118 with one fold at 0.401. Below the pre-registered 0.60 floor. The model artifacts remain on disk for M004+ reference but are not surfaced via the API or UI.

Root cause is sample-size ceiling (56/156 incidents carry HF positives), not feature engineering. Not recoverable at current corpus volume. Re-attempt only if corpus grows materially (e.g., adding PHMSA + TSB at full barrier-level detail).

### 4.4 `y_fail` model honest performance bounds

Cascade `y_fail_target` GroupKFold AUC: 0.763 ± 0.066. The fold-4 floor is 0.651 — that is the honest worst-case generalization figure, not a reason to retrain. Pre-registered branch logic (D016/D019) has been tested under unambiguous results only; borderline cases (e.g., a 0.59 vs 0.60 threshold call) have not been encountered in practice. Discipline is easier under favorable results.

### 4.5 Domain expertise is applied through review, not embodied in code

The CCPS taxonomy mapping, threshold calibration, and corpus scope are enforced by code; their meaning is in the domain. A future engineer without process safety context can change the taxonomy mapping, recalibrate thresholds, or expand the retrieval corpus in ways the system cannot flag as domain-incorrect. This is documented in `docs/journey/08-lessons-learned.md` and named here for explicit handoff awareness.

### 4.6 Performance Influencing Factors (PIFs) are excluded from `y_fail` features

D011 dropped PIFs from the cascade `y_fail` feature set. They remain in Schema V2.3 as incident metadata and are surfaced in RAG narrative output (D018, D020). Re-introducing PIFs as model features would require revisiting D011's structural-features-only hypothesis.

### 4.7 Scenario builder is fully user-built

Per L001: the system has no incident-viewer mode. The user constructs the bowtie from a blank canvas — top event, threats, barriers, consequences — then conditions on a barrier to drive cascade predictions. Pre-loaded BSEE example is available via the sidebar. The M002 four-tab dashboard has been removed and must not be reintroduced.

---

## 5. Deferred to M005 and beyond

Not regressions; deliberate M003 scope-fence outcomes.

| Item | Status | Reference |
|---|---|---|
| `src/_legacy/` migration | Deferred (4–8 h) | §2.3 |
| Mobile responsive layout | Deferred (multi-hour) | §1.1 |
| PIF Prevalence chart reinstatement | Deferred (intentional M003 cut) | §1.2 |
| Scenario-builder UX expansion (L001 full edit) | Deferred (multi-hour) | §4.7 |
| Fidel Comment #55 — 5-category barrier taxonomy | Deferred (LLM re-extraction cost) | §4.2 |
| LFS migration for `data/rag/archive/v1/` | Deferred (history rewrite required) | §2.4 |
| `bowtie-deploy.gnsr.dev` Cloudflare route + Uptime Kuma monitor | Deferred (15 min UI work) | §3.7 |
| Production-grade tag pinning in `docker-compose.server.yml` | Deferred (15 min) | §3.5 |
| Comment #56 (`lod_display`) UI completion | Partial (per CURRENT_STATE) | tech-debt |
| T2b narrative-synthesis improvements (rate limit, stable IDs, sentence segmentation) | Deferred (M004 scope) | tech-debt |

---

## 6. Tooling — status (installed and pending)

Code-quality, security, and ML-observability tooling that the project would benefit from but has not yet integrated. Install order is documented in `TOOLING_ROADMAP.md` (handoff-only document, not in repo). Current state:

**Already in place:** GitHub Dependabot alerts, Secret Protection, Push protection (no auto-PRs).

**Installed (Phase 3 cleanup):** `ruff` (Python lint) — installed 2026-05-02, used to clear unused imports + empty f-strings on active source (B.1 batch). The canonical lint invocation is documented in `CLAUDE.md` Commands section.

**Recommended quick wins (pending):** `mypy` (type check) — F010 type tightening on `create_app(lifespan_override=...)` is currently doc-only signal; mypy adoption converts it to enforced spec. Also: `trivy` (container CVE scan), `detect-secrets` pre-commit hook.

**Higher-setup items:** `semgrep` custom rules, `schemathesis` API fuzz tests, `Sentry` runtime error capture.

**ML observability:** `RAGAS` evaluation harness, `Evidently` drift report.

**Intentionally not installed:** CodeQL (would generate triage workload), Dependabot security updates (would auto-PR `torch`/`transformers` upgrades that risk breaking model artifacts).

---

## 7. Phase 3 cleanup commits (since 2026-04-27 demo tag)

Between the demo (`v1.0-apr27-demo`, commit `592bfa9`) and this handover, 14 cleanup commits landed on `branch/restructure-cleanup`. Highlights:

- **Doc archival** (D.1, D.2): completed M001/M002 plans moved to `docs/archive/`, decision register synced through D020, ADR-002 marked superseded by D007, README D-range corrected.
- **Repo hygiene** (D.3, D.4): dead/empty directories removed, gitignore cleaned, untracked artifact policy made explicit (Patrick's curated training input now tracked; Jeffrey's analytical export gitignored with documentation).
- **Code hygiene** (B.1): unused imports + empty f-strings removed via `ruff` (active source only; `_legacy/` and `scripts/archive/` preserved by intent).
- **D001 documentation reality check** (B.5): CLAUDE.md `_legacy` import policy in three places now carries explicit exception clauses naming the 3 retained import sites; M005 cleanup tracker added to `docs/tech-debt.md`.
- **Dead-experiment archival** (B.6): `hf_recovery.py` (y_hf_fail Branch C) + companion test moved to `archive/disabled-experiments/` with restoration documentation; active `src/modeling/cascading/` and `tests/` now contain only active code.
- **Observability** (B.4): structured-logging discipline applied to 5 silent hot-path modules + traceback-preserving `logger.exception` in 4 ingestion/corpus exception handlers.
- **Fresh-clone fix** (B.3): cascading training input CSV (`barrier_model_dataset_base_v3.csv`, 552 rows BSEE+CSB-derived) now tracked in git per Patrick's OK to publish.
- **Type tightening + test-skip surfacing** (B.7): `lifespan_override` precise typing + pytest fixture warns at session start when cascade ML artifacts absent.
- **CVE clearance** (B.2): 6 of 7 npm audit findings cleared via `package.json` overrides + `vitest` major-version upgrade. 1 remaining dev-only CVE (vite path-traversal) deferred per §3.8 above.
- **Doc consistency** (D.5, Phase 4): Python 3.12 + Next.js 16 references aligned across README/CLAUDE/CONTRIBUTING; current test counts updated; dead-link plan-file references annotated as local-only.

Net: 626 backend tests passing, 250 frontend tests passing. No production code paths changed beyond documentation and observability additions; the Phase 3 work is entirely receiver-quality improvements over the demo tag.


## Provenance

Source documents consulted in compiling this list:

- `docs/audits/HOSTED_DEMO_AUDIT_2026-04-24.md` (Playwright Phase 7 audit)
- `docs/audits/LIVE_AUDIT_CHROME_2026-04-24.md` (Live Chrome DevTools audit)
- `docs/audits/STATUS_ADDENDUM.md` (current-state resolution map)
- `docs/tech-debt.md` (engineer-facing tech debt log)
- `docs/journey/07-deployment.md` (deployment architecture and asymmetry)
- `docs/journey/08-lessons-learned.md` (constraint-driven choices, domain dependency)
- `docs/decisions/DECISIONS.md` (D006, D007, D011, D016, D018, D019, D020 — the cited decision IDs)
- `docs/diagnosis/2026-04-27_cascade_payload_bug.md` (post-demo cascade payload fix root cause)

For history of every issue surfaced and triaged: see the audit reports themselves and the post-demo commit log on `branch/restructure-cleanup` from `592bfa9` to `595978d`.
