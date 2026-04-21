# Tech Debt

Items noticed but deliberately NOT fixed in their discovery pass. Each entry records when it was found, what the issue is, and why it was deferred.

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
