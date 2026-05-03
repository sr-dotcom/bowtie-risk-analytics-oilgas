# Tech Debt

Items noticed but deliberately NOT fixed in their discovery pass. Each entry records when it was found, what the issue is, and why it was deferred.

---

## 2026-05-03: CI skip-guard gaps — four test files with gitignored-data dependencies

**Found during:** Pre-handoff CI green sweep (iterative exposure via `-x` fail-fast).

**Root cause pattern:** Several test modules guarded on committed ML artifacts
(`xgb_cascade_y_fail_pipeline.joblib`, `barrier_faiss.bin`), but inner tests or
fixtures also read gitignored data files (`data/processed/`, `data/models/evaluation/`).
Because the committed artifacts existed, `pytestmark.skipif` evaluated False and tests
ran — hitting `FileNotFoundError` on the absent gitignored files.

**Files fixed and what was changed:**

- `tests/test_cascading_shap.py` — Added `pytest.skip()` inside `first_pair_row`
  fixture when `data/processed/cascading_training.parquet` is absent. Three parquet-
  dependent tests skip in CI; `test_build_tree_explainer_returns_correct_type` and
  `test_no_shap_files_on_disk` are unaffected.

- `tests/test_cascading_train.py` — Added `@_CV_REPORT_SKIP` decorator to the three
  CV-report tests (`test_cv_report_exists`, `test_cv_report_has_both_targets`,
  `test_cv_report_has_five_fold_rows_per_target`) using `skipif(not _CV_REPORT.exists())`.
  CV report is in gitignored `data/models/evaluation/`.

- `tests/test_rag_s04_integration.py` — Widened `TestS04Integration.skipif` to also
  gate on `_CASCADING_PARQUET.exists()`. `barrier_faiss.bin` is committed but the
  parquet (used in assertion step 7) is gitignored.

- `tests/test_demo_scenarios.py` — Added module-level `pytestmark.skipif` on
  `FLAT_INCIDENTS_CSV.exists()`. The two module fixtures both call `build_demo_scenarios`
  which reads `data/processed/flat_incidents_combined.csv` (gitignored). 34 tests skip
  in CI.

**To run these locally:** `python -m src.pipeline build-combined-exports` (generates
the flat CSVs), `python -m src.modeling.cascading.train` (generates CV report and
evaluation artifacts), `python -m src.modeling.cascading.data_prep` (generates parquet).

---

## 2026-05-03: Bucket-C test followups deferred at v1.0 handoff

**Found during:** Pre-handoff skip-test audit (fa79072 → Bucket A/B/C/D classification).

**Background:** 30 of 45 CI-skipped tests were promoted to CI-passing by converting them from builder-dependent fixtures to committed-fixture or synthetic-data fixtures. Five tests were classified Bucket C and remain skipped on a fresh clone because they test script *behaviour* rather than schema *shape* — requiring proper CI fixture scaffolding to run correctly.

**Tests still skipped on a fresh clone and why:**

| Test | File | Skip condition | Reason skipped |
|------|------|---------------|----------------|
| `test_exactly_three_files` | `test_demo_scenarios.py` | `flat_incidents_combined.csv` absent | Asserts builder emits 3 files; needs real CSV + schema_v2_3 JSONs to run `build_demo_scenarios()` |
| `test_one_file_per_agency` | `test_demo_scenarios.py` | `flat_incidents_combined.csv` absent | Asserts builder covers BSEE/CSB/UNKNOWN; same chain dependency |
| `test_cv_report_exists` | `test_cascading_train.py` | `cascading_cv_report.md` absent | Asserts `train.py` produced its evaluation output file |
| `test_cv_report_has_both_targets` | `test_cascading_train.py` | `cascading_cv_report.md` absent | Verifies CV report content format — should be a unit test of `_write_cv_report()` |
| `test_cv_report_has_five_fold_rows_per_target` | `test_cascading_train.py` | `cascading_cv_report.md` absent | Same — table-structure format check belongs in a unit test |

**Correct fix (medium effort each):**

- `test_exactly_three_files`, `test_one_file_per_agency`: create a synthetic committed CSV + minimal JSON stubs sufficient to drive `build_demo_scenarios()` in a CI-compatible way. Or, since the committed `data/demo_scenarios/*.json` already demonstrate the 3-file/3-agency invariant, delete these tests as redundant.
- `test_cv_report_*`: extract a `_write_cv_report(cv_results, df_pairs, path)` unit test with a synthetic `cv_results` dict written to `tmp_path`. The file format invariant should not require a trained model.

**Note:** `test_pair_context_from_demo_scenario` in `test_rag_s04_integration.py` remains partially Bucket B — the parquet-dependent scope assertion (step 7) could be extracted to allow the main integration body to run in CI. Medium effort; deferred to post-handoff.

---

## 2026-04-20: data/rag/archive/v1/ large binaries in git history

**Found during:** Commit 2 gitignore audit.

**Issue:** Three large binary files were committed before the `/data/*` gitignore rule covered them:
- `data/rag/archive/v1/embeddings/barrier_embeddings.npy` — 9.5MB
- `data/rag/archive/v1/embeddings/incident_embeddings.npy` — 1.5MB
- `data/rag/archive/v1/datasets/barrier_documents.csv` — 3.9MB
- `data/rag/archive/v1/datasets/incident_documents.csv` — 906KB

**Why deferred:** `git rm --cached` would untrack them going forward but NOT reduce repo history size. Actual cleanup requires a `git filter-repo` rewrite, which rewrites all commit SHAs and requires force-push coordination with all contributors. Risk outweighs benefit until a planned M004 LFS migration.

**Fix when:** M004 infra pass, or before any public open-sourcing. Use `git filter-repo --path data/rag/archive/v1/embeddings/ --invert-paths` and migrate to Git LFS.

---

## 2026-04-20: SPRINT_ANALYSIS_VISUAL_DEPLOY.md:Zone.Identifier at repo root

**Found during:** Commit 1 inventory.

**Issue:** A file named `SPRINT_ANALYSIS_VISUAL_DEPLOY.md:Zone.Identifier` exists at the repo root. This is a Windows NTFS alternate data stream stub created when copying a file into WSL. It is untracked (caught by the `*:Zone.Identifier` gitignore rule) and harmless, but visually clutters `ls`.

**Why deferred:** The `*:Zone.Identifier` rule already prevents it from being committed. Deleting it is a one-liner (`rm 'SPRINT_ANALYSIS_VISUAL_DEPLOY.md:Zone.Identifier'`) but is out of scope for a documentation-only commit pass.

**Fix when:** Next time the repo root is touched for non-documentation reasons.

---

- Python test environment drift: 19 pre-existing pytest failures (shap/xgboost ImportErrors). Not regressions, environment issue. Resolve before defense: `pip install -e .` in clean venv, verify `pytest tests/ -q` returns 0 failures. Logged 2026-04-20.

- T1 defect: sidebar does not auto-collapse to 48px icon strip when drill-down opens (UI-CONTEXT.md §8 viewport handling). Currently all three regions (sidebar 360px, bowtie, drill-down 420px) open simultaneously, reducing bowtie canvas below the 1200px §8 minimum on <1920px viewports. Fix scope: sidebar collapsed-state, auto-collapse on drill-down open, expand-closes-drilldown rule. Defer until T5 polish pass. Logged 2026-04-20.

- T2b: feature flag is render-guard only — `process.env.NEXT_PUBLIC_ENABLE_T2B_SYNTHESIS` is checked at render time but the synthesis button subtree is included in the JS bundle. Hoist to `dynamic(() => import(...), { ssr: false })` behind the flag to tree-shake the button in production if bundle size becomes a concern in M004.

- T2b: word/sentence count quality gate uses naive `str.split()` and `.count('.')` splitting. Replace with spaCy sentence segmentation or an abbreviation-aware regex in M004 when false-positive rejection (e.g. abbreviations like "B.V.") becomes observable.

- T2b: NarrativeHero identifies the top barrier by `.name` string when building the synthesis input. Switch to `control_id` as the stable identity key once the cascading API surfaces it in the `/predict-cascading` response shape.

- T2b/auth: endpoint rate-limiting deferred. Current protection is the `BOWTIE_API_KEY` header (one shared key). Add per-IP or per-key rate limiting (e.g. slowapi or Nginx upstream) in M004 before any public deployment.

- UX: Executive Summary hero shows `barriers.length` (all barriers including the conditioning barrier), while Ranked Barriers correctly excludes the conditioning barrier from its list — causing "7 barriers" vs "6 of 6 barriers" on the same dashboard. Fix: pass `total_barriers = barriers.length - 1` (excluding conditioning) to the hero, or add a parenthetical "(+ 1 conditioning)" note. Defer to T5 polish.

- UX: Two incident counts visible on same dashboard — "156 comparable incidents" in hero (RAG v2 corpus) and "174 real BSEE/CSB incidents" in Assessment Basis / Drivers & HF (M002 LOC training scope). Both numbers are correct for their contexts but a reader sees inconsistency. Fix: label clarification — hero denominator should read "from the 156-incident retrieval corpus"; Drivers & HF note should read "from 174 LOC-scoped training incidents". Alternatively consolidate to a single narrative dataset in M004 when RAG and training corpora are unified.
---

## M005-NN — Remove `_legacy` imports from active code (closes D001 exit condition)

Status: Deferred to M005. Effort estimate: 4–8 hours.

Three production modules currently import from `src/_legacy/` per D001:

- `src/pipeline.py`
- `src/analytics/__init__.py`
- `src/models/__init__.py`

Total scope: 14 imports across 9 production files (analyzed during AUDIT_TRIAGE F006). The legacy coverage analysis these imports support must be either (a) verified still functional and migrated to non-legacy modules, or (b) confirmed retired and the call sites removed.

D001 exit condition: "removed only when all production imports are migrated." Until this work lands, CLAUDE.md sections on `_legacy` carry exception clauses naming the 3 retained import sites.

References: AUDIT_TRIAGE F006, DECISIONS.md D001, CLAUDE.md exception notes (lines 160, 219, 320).
