# Development Log

## Overview
This log tracks significant development progress for the Bowtie Risk Analytics project.

---

## Entries

### 2026-02-01 — Phase 0: Repo setup, hygiene, and reproducibility
- Initialized a reproducible project scaffold (src/, tests/, docs/, data/) and verified baseline tests.
- Enforced repo hygiene: excluded local-only tooling and non-shareable files from version control.
- Created and published the GitHub repository with a clean main branch history.

Validation:
- pytest -q passes
- main branch contains only intended tracked artifacts
- confirmed push to GitHub (main tracking origin/main)

## 2026-02-02 — Step 0.0 Proposal feedback incorporation check
- Verified instructor feedback has been incorporated into Proposal v2:
  - Primary target anchored on barrier health / barrier failure risk
  - MVP scope narrowed to single scenario (Loss of Containment)
  - MVP model comparison limited to Logistic Regression (baseline) and XGBoost (improved)
  - Explainability prioritized (coefficients/SHAP + reason codes); RAG positioned as supporting evidence layer
  - Dataset target size aligned to instructor guidance (~150–250 labeled examples) with cross-validation
- Follow-up: make demo accessibility explicit (hosted-first demo target + local fallback) to match instructor evaluation constraints.

---

*Add new entries above this line*
