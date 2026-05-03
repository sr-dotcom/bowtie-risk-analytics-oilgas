# tests

Pytest suite for the Python backend, plus Vitest specs for the Next.js frontend. Backend tests live here; frontend tests live under `frontend/__tests__/` and `frontend/tests-e2e/`.

Backend test gate (post-v1.0, commit 79e0917):
- **CI (no derived artifacts):** ≥ 540 passed, 0 failed
- **Local (full data + fpdf2):** ≥ 549 passed, 0 failed

**Frontend gate (CI and local equal):** ≥ 250 passed, 0 failed

Any commit dropping below either floor is reverted.

**Fresh-clone prerequisite:** `pip install -r requirements.txt`, then `python -m src.modeling.cascading.data_prep && python -m src.modeling.cascading.train` to generate model artifacts from the tracked training input. The `test_demo_scenarios` schema/R019 tests now run against committed fixtures in `data/demo_scenarios/` and pass on a fresh clone. The two builder-behaviour tests (`test_exactly_three_files`, `test_one_file_per_agency`) remain skipped without `flat_incidents_combined.csv`; this is expected and accounted for in the CI floor.

Run:

```bash
pytest                          # backend
cd frontend && npm test         # frontend (Vitest)
```

Cascading-model coverage focuses on pair-feature construction, branch-activation logic (D016, D019), and the `/predict-cascading` + `/explain-cascading` contracts. RAG coverage exercises the 4-stage hybrid pipeline (D017).

See [Chapter 3 — Pair Features and the Cascade](../docs/journey/03-cascade-model.md) and [Chapter 5 — Retrieval, Scoping, and the Domain Filter](../docs/journey/05-rag-retrieval.md) for what these tests are protecting.
