# tests

Pytest suite for the Python backend, plus Vitest specs for the Next.js frontend. Backend tests live here; frontend tests live under `frontend/__tests__/` and `frontend/tests-e2e/`.

**Backend gate:** ≥565 passing (current: 626).
**Frontend gate:** ≥192 passing (current: 250).

**Fresh-clone prerequisite:** `pip install -r requirements.txt`, then `python -m src.modeling.cascading.data_prep && python -m src.modeling.cascading.train` to generate model artifacts from the tracked training input. `test_demo_scenarios` (~34 tests) will still error on fresh clone — its fixture requires `data/processed/flat_incidents_combined.csv`, which is built from the gitignored structured incident JSONs. These errors are expected and excluded from the gate count.

Run:

```bash
pytest                          # backend
cd frontend && npm test         # frontend (Vitest)
```

Cascading-model coverage focuses on pair-feature construction, branch-activation logic (D016, D019), and the `/predict-cascading` + `/explain-cascading` contracts. RAG coverage exercises the 4-stage hybrid pipeline (D017).

See [Chapter 3 — Pair Features and the Cascade](../docs/journey/03-cascade-model.md) and [Chapter 5 — Retrieval, Scoping, and the Domain Filter](../docs/journey/05-rag-retrieval.md) for what these tests are protecting.
