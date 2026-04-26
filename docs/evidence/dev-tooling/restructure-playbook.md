# Restructure Playbook — Pure Portfolio Repos

A portable workflow for converting an in-progress codebase into a
portfolio-grade public repository. Drop this file into any repo's
root or `docs/` directory; Claude Code reads it and executes the
workflow phase by phase, adapting to whatever the actual codebase
contains.

This playbook is opinionated. It encodes the decisions that
mattered when restructuring a real project for a recruiter
audience. It does not try to cover every possible restructure
shape — narrower scope, stronger enforcement.

---

## What this playbook is for

You have a working codebase that grew organically. Audit reports,
screenshots, planning notes, and milestone docs are scattered.
The README is stale or aspirational. Tests pass but documentation
makes claims the code doesn't back. You need to publish this as
a portfolio artifact a recruiter will look at and conclude
"this person knows what they're doing."

This playbook is not for: production services with users,
team projects with active multi-contributor history, repos that
already have a clean structure.

---

## Operating principles

Six principles drive every decision in this playbook. If a
specific instruction below conflicts with one of these, the
principle wins.

1. **Local-only until proven clean.** All restructure work
   happens on a feature branch that is never pushed until the
   final squash-merge. Production stays at the pre-restructure
   commit throughout.

2. **Verification gates between every bucket.** Each phase of
   work commits only after tests, lint, and structural checks
   pass. A failing gate aborts the bucket and is fixed before
   moving on.

3. **Documentation must match code.** Every published number,
   file path, function name, and claim is verified against the
   actual codebase before merge. Documentation drift is the
   most common portfolio failure.

4. **Honest about what's not done.** Every chapter ends with a
   "What this doesn't buy" or "Deferred controls" section.
   Engineers signal trustworthiness by acknowledging gaps, not
   by hiding them.

5. **Squash to one commit on merge.** The restructure branch
   accumulates many commits during execution. The squash-merge
   to main collapses them into one deliberate commit with a
   meaningful message. Public history stays clean.

6. **The repo is one of two artifacts: a current-state portfolio
   and an archive of how it got there.** Keep them separate.
   Mixing them confuses recruiters who want the current state
   and instructors or maintainers who want the history.

---

## Audience model

A portfolio repo serves two readers:

- **The 90-second skim**: a recruiter or hiring manager who clicks
  the GitHub link, reads the top of the README, scans the file
  tree, maybe opens one chapter. They form an opinion in 90
  seconds and move on.

- **The 30-minute deep dive**: an engineer doing a technical
  interview prep, an open-source maintainer evaluating the repo,
  or a course instructor verifying claims. They open multiple
  files, run the code, check the numbers.

Both audiences must be served. The 90-second reader needs a hero
diagram, headline numbers, and a clear chapter index above the
fold. The 30-minute reader needs every claim sourced and every
chapter readable independently.

---

## Phase overview

Six phases. Each has a verification gate. Skip none.

| Phase | What it does | Branch state at end |
|---|---|---|
| 0 | Inventory and plan | Phase 0 branch created |
| 1 | Move and rename files into target structure | Branch has structural commits |
| 2 | Reference cleanup (imports, links, paths) | Branch has reference fixes |
| 3 | Author the journey and root README | Branch has documentation commits |
| 4 | Pre-merge audit (numbers, links, secrets) | Branch is verified clean |
| 5 | Squash-merge to main | Production updated |

Total time: 1-3 days for a small repo (≤500 files), 3-7 days for
a larger codebase. The playbook does not promise speed; it
promises that nothing reaches main without verification.

---

## Phase 0 — Inventory and plan

Before any move happens, produce two artifacts:

1. **An inventory of every file in the repo**, classified into
   one of seven categories:

   - KEEP-PROD: production code (`src/`, `api/`, `frontend/`)
   - KEEP-TEST: tests
   - KEEP-EVAL: evaluation suites and benchmarks
   - KEEP-DOCS-CURRENT: documentation describing current state
   - KEEP-CONFIG: build, deploy, CI configuration
   - KEEP-DATA: corpus, fixtures, indexed data
   - ARCHIVE-EVIDENCE: audit reports, screenshots, planning notes,
     historical milestone submissions
   - DEAD-REMOVE: clearly orphaned files (no references, no tests)
   - AMBIGUOUS: file's role unclear; resolve before Phase 1

2. **A move plan**: for each file, the target path and the reason.
   Verify reference impact for each rename — Python imports,
   Dockerfile COPY directives, CI workflow paths, README links.

Worker prompt template for Phase 0:

```
Task: Phase 0 — Inventory and plan for repository restructure.
READ-ONLY. Zero file modifications.

Read every file in the repo. Classify into seven categories:
KEEP-PROD, KEEP-TEST, KEEP-EVAL, KEEP-DOCS-CURRENT, KEEP-CONFIG,
KEEP-DATA, ARCHIVE-EVIDENCE, DEAD-REMOVE, AMBIGUOUS.

For each AMBIGUOUS file, run grep to find references. If no
references in CI/code/imports, classify ARCHIVE-EVIDENCE or
DEAD-REMOVE based on content. If references exist, classify
KEEP-* based on what consumes it.

Output: /tmp/RESTRUCTURE_INVENTORY.md with the full classification
table.
```

Verification gate: human reviews the inventory before Phase 1
begins. AMBIGUOUS items must all be resolved.

---

## Phase 1 — Move and rename

Create the feature branch off main:

```
git checkout -b branch/restructure-cleanup
```

Execute moves in three buckets, ordered by risk:

**Bucket 1 — Lowest risk.** Documentation, archives, screenshots,
tooling state archival. No imports affected. No tests touched.

- Archive audit reports to
  `docs/evidence/audits/<kebab-case-name>.md`
- Archive screenshots to
  `docs/evidence/screenshots/{current,audit,verification}/`
- Move tooling state (`CLAUDE.md`, IDE config, agent skills) to
  `docs/evidence/dev-tooling/`
- Add tooling paths to `.gitignore`
- Delete dead files identified in Phase 0

**Bucket 2 — Medium risk.** Test reorganization, eval suite
restructure, milestone document renames.

- Subdivide `tests/` into category subdirectories (e.g., `api/`,
  `core/`, `integration/`). Add `__init__.py` per subdirectory.
- Subdivide `eval/` into `runners/`, `cases/`, `results/`,
  `fixtures/`. Atomic with CI workflow updates.
- Rename milestone docs to consistent `M##-kebab-case.md` format.
- Move historical milestone submissions to
  `docs/evidence/milestones/M##/`.

**Bucket 3 — Highest risk.** Production code renames, shim
deletions, function reorganization.

- Remove unused re-export shims (run `grep -rn "from <shim>"`
  first; refuse to delete if any import still depends on it)
- Rename internal modules only when target paths are clearly
  better. Atomic with import updates across the codebase.

Verification gate after each bucket:

```
pytest tests/ -q | tail -3
ruff check . | tail -3
docker compose build  # if applicable
```

If any verification fails, the bucket aborts. Diagnose and fix on
the branch before moving on.

Worker prompt template for Phase 1:

```
Task: Phase 1 Bucket <N> — execute structural moves.
Continue on branch/restructure-cleanup. NO push.

Use /tmp/RESTRUCTURE_PLAN.md (Phase 0 output).

For each move in Bucket <N>:
1. git mv <old> <new>
2. Verify the file lands at the new path
3. Update any references caught by Phase 0 reference-impact
   analysis

After all moves in this bucket:
- pytest tests/ -q (must show same count as before bucket)
- ruff check . (must be clean)
- Single commit with message describing the bucket's scope

Output: list of moves executed, verification results, commit SHA.
```

---

## Phase 2 — Reference cleanup

Even after atomic moves, references drift. Sweep for stale
references across the entire repo:

- Module imports referencing old paths
- README links pointing to renamed files
- Docstring file paths
- CI workflow paths
- Dockerfile COPY directives
- Documentation cross-references

Worker prompt template for Phase 2:

```
Task: Phase 2 — Reference cleanup after structural moves.
Continue on branch/restructure-cleanup. NO push.

For each renamed module/file in Phase 1:
1. grep -rn "<old-path>" . --exclude-dir=.git --exclude-dir=.venv
2. Update each occurrence to the new path
3. Verify no production behavior changed

Specific targets:
- README.md path references
- All .md files in docs/
- src/, api/ docstrings mentioning file paths
- .github/workflows/*.yml step paths
- Dockerfile COPY directives

Verification:
- pytest tests/ -q (clean)
- grep -rn "<every-old-path>" should return zero matches outside
  docs/evidence/ archive

Single commit at end. Output: list of files modified, before/after
grep counts.
```

Verification gate: zero stale references in published surface
(everything outside `docs/evidence/`).

---

## Phase 3 — Author documentation

Two layers of documentation, with a clear distinction:

**Journey chapters** (`docs/journey/NN-kebab-case.md`): a
narrative of how the system was built, written in current state.
Reader-friendly. Recruiter-grade. Each chapter stands alone.

**Evidence archive** (`docs/evidence/`): historical artifacts as
produced. Audit reports, original course submissions, planning
documents, screenshots from earlier states, retired tooling.

Never mix these. A journey chapter that includes "this was changed
later" breaks the reader's flow. An evidence file that's been
edited to read like a journey chapter loses its archival value.

### Chapter list (adapt for project)

A pure portfolio playbook does not prescribe specific chapters —
project domain dictates the content. The shape stays consistent:

- 1-3 foundation chapters (what problem, who it serves, what
  decisions shaped the design)
- 3-5 engineering chapters (architecture, data, evaluation,
  the technical centerpieces)
- 2-4 operational chapters (security, deployment, cost,
  observability)
- 1 lessons-learned chapter (what would change, what held up)

Each chapter:

- Opens with concrete framing of what it covers
- Uses themed Mermaid diagrams (locked theme, see Appendix A)
- Cites real files with paths (`src/foo.py:42` style)
- Ends with "What this buys" + "What this doesn't buy" sections

### Root README

Above the fold (visible without scroll on GitHub):

- Project name + tagline (12 words)
- Disclaimer block if the project uses third-party trademarks
- Hero Mermaid diagram (system overview)
- Live demo link

Below the fold:

- Headline numbers (every value sourced from a real file)
- Codebase map (table of `path → what's there`)
- Journey chapter index
- Local run instructions (must actually work — verify by running)
- Stack inventory
- Authors + license + disclaimer link

### Sub-READMEs

Each subdirectory with non-obvious purpose gets a brief README
(30-80 lines max):

- `tests/README.md` — test layout and how to run
- `eval/README.md` — eval suites, runners, results
- `eval/cases/README.md`, `eval/results/README.md` — file-by-file
- `docs/README.md` — documentation map
- `docs/evidence/README.md` and per-subdirectory README files

### Numbers come from files, not memory

For every number in the documentation:

- Test counts → `pytest tests/ -q` live
- Evaluation scores → JSON result files committed to repo
- Corpus stats → metadata files
- Coverage percentages → coverage report files
- Performance numbers → load test result files

Do not type a number you didn't read from a file. The audit gate
in Phase 4 will catch this, but better to never write the wrong
number in the first place.

Worker prompt template for Phase 3 (one chapter):

```
Task: Author docs/journey/<N>-<topic>.md.
Continue on branch/restructure-cleanup. NO push.

Source verification first — read these to ground every claim:
[list real files relevant to this chapter]

Chapter structure:
[list real sections with real source files for each]

Use locked Mermaid theme (see Appendix A in playbook).

Every file path cited must exist. Every number must come from
a real file. No invented benchmarks. No paraphrased prose
that drifts from the source.

End with "What this buys" / "What this doesn't buy".

Single commit. Output: SHA, file size, section headers, list of
verbatim quotes from source files used.
```

Verification gate: each chapter committed only after `head -30`
spot check by human and `grep` confirmation that cited file paths
exist.

---

## Phase 4 — Pre-merge audit

Before squash-merge, run nine independent gates:

1. **Re-baseline evaluation suites.** Re-run every evaluation
   (tests, golden, retrieval, RAGAS-equivalent) against current
   branch tip. Numbers in published documentation must match.

2. **Tests + lint clean.** `pytest`, `ruff check`, type checker.
   All green.

3. **Build artifacts produced cleanly.** `docker compose build`
   succeeds.

4. **Health endpoint or smoke test passes.** Run the artifact;
   confirm basic functionality.

5. **Internal link audit.** Every `[text](path)` markdown link
   resolves to a real file in the repo.

6. **Secret audit.** Working tree and squash diff both clean of
   API keys, tokens, credentials.

7. **Number consistency across files.** For each canonical metric,
   sweep every published file and verify all references match (or
   are deliberately labeled as historical).

8. **DRAFT marker scan.** Every `DRAFT`, `TODO`, `FIXME`, `TBD`,
   `XXX` outside evidence archive must be resolved.

9. **Image/screenshot resolution.** Every `![alt](path)` reference
   points to an existing file.

Worker prompt template for Phase 4:

```
Task: Phase 4 — Pre-merge audit gate.
Continue on branch/restructure-cleanup. NO push, NO merge.

Run all 9 gates. Read-only — do NOT auto-fix.

For each gate, report PASS/FAIL with evidence.

Special handling for Gate 7 (number consistency):
- Identify canonical source for each metric (live test run,
  result JSON file, etc.)
- Sweep every .md file outside docs/evidence/
- Classify each occurrence as MATCHES_CANONICAL, STALE, or
  HISTORICAL (deliberate before/after comparison)
- Report STALE occurrences for human triage; never auto-fix

Output: 9-gate pass/fail table, list of every issue found,
final verdict (READY FOR MERGE / NOT READY).
```

If any gate fails, fix on the branch and re-run that gate. Do not
proceed to Phase 5 until all 9 gates pass.

### Common Phase 4 findings

What to expect:

- **Eval drift.** Numbers in chapters cite an older measurement.
  Either re-run and update, or label as historical and add the
  current number alongside.

- **Documentation overclaim.** The chapter says "we use X" but
  the code uses Y. Either change the code or the chapter; do not
  ship the discrepancy.

- **Production bugs surfaced by audit.** Pre-merge auditing
  sometimes catches real bugs (a substring collision, an unused
  code path, an inconsistent constant). Fix them as part of the
  audit, not after.

- **Non-reproducible measurements.** A number measured against
  a state that no longer exists (a previous index, an older
  dependency version) cannot be re-verified. Replace with a
  current measurement; document the change.

---

## Phase 5 — Squash-merge to main

Three things must be true:

1. All 9 Phase 4 gates pass.
2. Squash commit message drafted and reviewed.
3. Operator is in a monitoring window — production rebuild and
   smoke test happen within 10 minutes of push.

Worker prompt template for Phase 5:

```
Task: Phase 5 — Squash-merge branch/restructure-cleanup to main.

PRE-CHECK:
  git checkout main
  git pull origin main
  git rev-parse HEAD  # capture pre-merge SHA for rollback

EXECUTE:
  git merge --squash branch/restructure-cleanup
  git status  # review staged changes

Commit with the prepared message (provided by human in this
prompt).

  git push origin main

Monitor production rebuild:
  watch -n 30 "curl -sI https://<production-url> | head -3"

Stop after deploy completes (~5 min for typical Docker + tunnel
setup). Confirm health endpoint responds.

If deploy breaks production:
  git revert HEAD
  git push origin main

Output: pre-merge SHA, post-merge SHA, deploy timing, smoke test
result.
```

Post-merge verification by human (not worker):

- Visit production URL in browser
- Confirm key UI elements render
- Run one query end-to-end
- Verify any disclaimer banners or legal posture appears
- Check that internal links work

If anything is broken: revert immediately. The branch is preserved
and can be repaired and re-merged.

---

## Appendix A — Locked Mermaid theme

Every Mermaid diagram in the journey uses this theme block:

```
%%{init: {'theme':'base', 'themeVariables': {
  'primaryColor':'#1e293b',
  'primaryTextColor':'#f1f5f9',
  'primaryBorderColor':'#475569',
  'lineColor':'#94a3b8',
  'secondaryColor':'#0f172a',
  'tertiaryColor':'#334155',
  'fontFamily':'ui-monospace, SFMono-Regular, Menlo, monospace',
  'fontSize':'14px'
}}}%%
```

Class definitions for differentiated nodes (paste into each
diagram):

```
classDef user fill:#0ea5e9,stroke:#0284c7,color:#f0f9ff,stroke-width:2px
classDef edge fill:#334155,stroke:#64748b,color:#f1f5f9
classDef core fill:#0f172a,stroke:#0ea5e9,stroke-width:3px,color:#f0f9ff
classDef data fill:#1e293b,stroke:#475569,color:#f1f5f9
classDef external fill:#1e293b,stroke:#f59e0b,color:#fef3c7
```

Consistency across diagrams is half the visual signal. Default
Mermaid looks identical to every other repo's default Mermaid;
consistent custom theming is the cheap differentiator.

---

## Appendix B — Legal disclaimer surface

If the project references trademarks, third-party data, or
public institutions:

- `DISCLAIMER.md` at repo root with full legal language
- README disclaimer block above all other content
- Per-page banner if there's a live demo
- Data provenance section explaining fair-use rationale

Engineers who proactively address legal posture for a portfolio
project signal judgment recruiters notice.

---

## Appendix C — Roles in the workflow

Three actors. Boundaries do not cross.

- **Operator (human)**: makes decisions, approves commits,
  verifies production after merge. Final authority.
- **Orchestrator (Claude chat)**: writes worker prompts, reviews
  worker output, identifies risks, escalates ambiguity. Does not
  modify code directly.
- **Worker (Claude Code)**: executes worker prompts. Reports
  results with evidence. Does not decide scope.

The three-actor model keeps work moving without any one role
becoming a bottleneck or making decisions outside its scope.

---

## What this playbook does NOT cover

Honest scope:

- **Multi-contributor team workflows.** This assumes a single
  operator. Pull requests, code review, branch protection rules,
  and merge queues are out of scope.

- **Production services with users.** A restructure of a service
  with active users requires zero-downtime considerations and
  database migration handling that this playbook does not address.

- **Repos with build pipelines that produce binary artifacts.**
  This playbook assumes a containerized application; binary
  release engineering is different.

- **Repos older than ~12 months with significant git history.**
  History rewrites become risky at that scale.

- **Monorepos.** This playbook assumes a single coherent project,
  not a monorepo of multiple deployable components.

For these cases, adapt the principles but expect to write
additional procedure.

---

## How to use this playbook on a new project

1. Copy `RESTRUCTURE_PLAYBOOK.md` to the new repo's root or
   `docs/` directory.
2. Open Claude Code in the new project.
3. Tell Claude Code: *"Read RESTRUCTURE_PLAYBOOK.md and execute
   Phase 0 against this repo."*
4. Claude Code reads the playbook, inventories the codebase, and
   produces `/tmp/RESTRUCTURE_INVENTORY.md` adapted to whatever
   it found.
5. Review the inventory. Resolve AMBIGUOUS items.
6. Tell Claude Code to proceed to Phase 1.
7. Verify gates between every bucket. Approve before each next
   phase.
8. After Phase 5 squash-merge, the new repo is portfolio-ready.

The playbook is the same. The codebase is different. Adaptation
happens at the worker level — the orchestrator (Claude chat) and
operator (you) keep the same disciplines.

---

## Closing note

A portfolio repo is a credentials artifact. The work to make it
clean is not separate from "real engineering" — it IS real
engineering. The same discipline that produces a maintainable
service produces a maintainable repository. Every shortcut you
take here is visible to a recruiter who looks carefully.

Build for the engineer who reads the repo in 6 months without
your help. If they can clone, run, and modify the code without
asking you a question, the playbook worked.
