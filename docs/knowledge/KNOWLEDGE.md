# Knowledge

Reusable insights, gotchas, and patterns surfaced during milestones.

---

## M001: Repo Alignment and Cleanup (2026-04-12)

### Git index state vs disk state are not the same
Before running `git rm --cached` on a file, verify with `git ls-files <path>` that it is actually tracked. Files listed in a plan as "git-tracked" may be untracked (disk-only). The ls-files output is authoritative; assumptions from directory listings are not.

### git mv is the correct tool for legacy quarantine
When moving files to a quarantine directory (like `src/_legacy/`), use `git mv` rather than `cp + rm`. This preserves rename history in `git log --follow` and `git blame`, making it possible to trace a file's full history across the move.

### Fix internal cross-references before external callers
When moving a package to a new location, fix all internal imports within the moved files first (e.g., engine.py's imports of bowtie.py and incident.py), before updating external callers. Otherwise the package is broken twice: once from broken internals and once from broken externals.

### Proactively add .gitignore patterns for future directories
If a slice creates a directory that should not appear in git, add the .gitignore pattern in the same or an earlier slice — before the directory is ever created. This avoids a two-step commit pattern and ensures the pattern is committed before the directory appears.

### Test pass counts are environment-dependent — verify zero regressions, not absolute counts
When optional packages (xgboost, faiss-cpu, shap) or gitignored data artifacts (model files) are missing, pytest pass counts can vary significantly between environments (352 vs 449 in M001). The meaningful metric is zero regressions vs the pre-change baseline in the same environment, not an absolute count from a different environment.

### Always read the source before writing documentation
Task plans and requirements can contain stale counts (e.g., "7-tab dashboard" when the actual TABS array has 4 tabs). Before writing any documentation, verify the current state by reading the actual source files. Accuracy trumps plan compliance.

### Verify untracked files before assuming they need git rm
SPRINT_5_BOWTIEXP_MATCH.md was listed in the plan as needing `git rm --cached` but was actually never tracked. Running `git rm --cached` on an untracked file would error. Always check `git ls-files <file>` first.

---

## M002: GitHub Presentation Layer (2026-04-12)

### Verify source files before writing documentation — task plans contain stale facts
Tab counts, service counts, uvicorn invocation syntax, and component names in task plans are often copied from earlier planning sessions and may be stale. Before writing any documentation, read the actual source files: `frontend/components/dashboard/DashboardView.tsx` for tab count, `docker-compose.yml` for service count, `src/api/main.py` for the correct uvicorn invocation. Catch this at write time, not review time.

### Parenthetical reconciliation is sufficient for numeric discrepancies between docs
When two documents cite different counts for the same entity (e.g., 526 in EVALUATION.md vs 739 in README.md), a parenthetical clarification in the older document is sufficient — "(subset of 739 canonical — filtered to incidents with RAG-quality barrier text)". No need to restructure either document; the parenthetical carries full explanatory weight.

### git rm --cached vs git rm is a load-bearing distinction for data blobs
For large data files or local config files that should stay on disk but be removed from tracking, always use `git rm --cached` (forward-delete only). Use plain `git rm` only for completed planning artifacts that are truly obsolete and should be removed from disk. Conflating the two risks destroying work that may still be needed locally.

### Atomic hygiene commits minimize verification overhead
Batching all related hygiene changes (.gitignore additions, index cleanups, file deletions) into one commit means verification is a single `git ls-files` call, not four separate checks across four commits. One commit to check, not four.

### Explicit preservation checks are required after bulk rm operations
After `git rm --cached -r` on a directory, immediately run `git ls-files <keep-file1> <keep-file2> | wc -l` and confirm the count matches expectations. Do not assume preservation files survived a bulk operation without checking — the cost of the check is low; the cost of silently losing a file is high.

| K001 | global | "Never auto-execute SVG coordinate changes in BowtieSVG.tsx — these require incremental browser verification and must be done manually with Claude Code CLI" | — | manual |

| K002 | global | K001: BowtieSVG coordinate changes must never be auto-executed. Incremental manual browser verification required between each SVG coordinate edit. Color overlays and interaction state changes are permitted without this gate. | — | manual |

| L001 | The M003 UX is a scenario builder (blank form, user constructs bowtie, clicks a barrier as conditioning, sees ranked cascading predictions) — not an incident viewer. Existing dashboard tab structure (Executive Summary, Drivers and HF, Ranked Barriers, Evidence) is deleted entirely. Do not preserve or reference it in new code. | — | — | global |

| K003 | global | Scenario-builder UI must render threats on mitigation barriers with distinct "escalation factor" styling (visually different from threats on prevention barriers). Data model identical; styling differs per CCPS convention. | — | manual |

| K004 | global | Cascading model code lives in `src/modeling/cascading/` subfolder. Do not modify files at `src/modeling/*.py` (those are the archived Models 1/2/3 training code). Cascading work goes into a new subfolder only. | — | manual |

| K005 | M003-z2jh4m/S01 | Scenario-builder UI must render threats on mitigation barriers with distinct "escalation factor" styling (visually different from threats on prevention barriers). Data model identical; styling differs per CCPS convention. | — | manual |

| K006 | M003-z2jh4m/S01 | Cascading model code lives in src/modeling/cascading/ subfolder. Do not modify files at src/modeling/*.py (those are archived Models 1/2/3 training code). Cascading work goes into a new subfolder only. | — | manual |

---

## M003: Cascading Pair-Feature Model + Scenario-Builder UI (2026-04-19)

### Patrick's CONTEXT_FEATURES are not marked in the CSV by prefix — consult reference notebook
S01 task T01 includes `total_prev_barriers_incident` and `total_mit_barriers_incident` as encoded features despite not matching the num_threats_* or flag_* prefix patterns used elsewhere. These are Patrick's CONTEXT_FEATURES from cell 6 of `docs/evidence/reference/xgb-combined-dual-inference-workflow.ipynb` and are required by S02's pair-building step. When porting feature sets from reference notebooks, consult the notebook's feature list directly rather than inferring from column-naming patterns. Include legitimate context features even if they don't match the regex patterns defined in the slice plan.

### Check for overlapping drop conditions early in data-prep
S01 task T01 drops rows where `lod_industry_standard == 'Other'` OR `lod_numeric == 99`. The two conditions overlapped on exactly one row, resulting in 530 survivors instead of the expected 529 (22 drops + 1 drop with overlap = 22 total). When designing drop audit logic, use set-union semantics and document the overlap explicitly in the profile. A simple before/after count without overlap analysis can hide this gotcha.

### git check-ignore behavior with negation rules — use git add --dry-run instead
T02 task plan verification tried `git check-ignore -v data/demo_scenarios/sample.json; test $? -eq 1` assuming exit code 1 signals "not ignored". However, git check-ignore returns exit 0 when the last matching rule is a negation (e.g., `!/data/demo_scenarios/**`), even though the file IS unignored. For reliable verification, use `git add --dry-run <files>` to confirm files are stageable; this is the authoritative test for trackability.

### Node ESM scripts should resolve paths relative to __dirname, not CWD
T03 task copy-demo-scenarios.mjs resolves the source path `../../data/demo_scenarios` relative to __dirname (computed from import.meta.url), not the current working directory. This is robust across different npm command invocation contexts — if someone runs `npm run prebuild` from a different directory, the script still finds the right source. Always use __dirname for file I/O in Node scripts, not process.cwd().
