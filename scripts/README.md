# scripts

One-shot utilities for corpus building, model training, and verification. Not part of the runtime API — run manually during development or when regenerating artifacts.

Common tasks:

```bash
python scripts/build_rag_v2.py        # rebuild RAG corpus from Schema V2.3 JSONs
python -m src.modeling.cascading.train  # retrain cascading model (writes data/models/artifacts/)
```

Most scripts are idempotent and safe to re-run; check the script's docstring for inputs and outputs. Verification scripts under `scripts/verify_*.py` exercise specific contracts (model loading, RAG corpus integrity, schema conformance) and exit non-zero on failure.

See [Chapter 2 — From Investigation Reports to Training Rows](../docs/journey/02-corpus-design.md) for corpus-build context and [Chapter 7 — Self-Hosted Deployment and Its Trade-Offs](../docs/journey/07-deployment.md) for what runs where.
