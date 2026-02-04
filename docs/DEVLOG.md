# Dev Log

## 2026-02-01 - Initial Setup
Set up the project structure with `src/`, `tests/`, and `data/` directories.
Added Pydantic models for incident data and basic tests.
Configured gitignore to exclude local env files.

## 2026-02-02 - Proposal Updates
Updated the proposal based on feedback:
- Narrowed MVP scope to "Loss of Containment" scenarios only.
- Will focus on Logistic Regression vs XGBoost for the model comparison.
- Added SHAP/reason codes for explainability.
- Target dataset size: ~200 labeled examples.

## Next Steps
- Implement JSON schema validation for Bowtie data.
- Build the initial data ingestion pipeline.
