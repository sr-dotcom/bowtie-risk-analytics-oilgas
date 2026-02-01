# Development Log

## Overview
This log tracks significant development progress for the Bowtie Risk Analytics project.

---

## Entries

### 2026-02-01 — Phase 0: Repo setup, hygiene, and reproducibility
- Initialized a reproducible project scaffold (src/, tests/, docs/, data/) and verified baseline tests.
- Enforced repo hygiene: local-only tooling and non-shareable files are excluded from version control.
- Published a clean initial GitHub history on main (single root commit) and validated remote sync.
Validation:
- pytest -q passes
- main branch contains only clean tracked artifacts (no local-only tooling)
- local HEAD matches origin/main

---

*Add new entries above this line*
