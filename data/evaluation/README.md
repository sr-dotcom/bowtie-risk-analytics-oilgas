# data/evaluation

Held-out evaluation artifacts for the cascading model and RAG retrieval. Tracked in git (small, deterministic) so reviewers can reproduce reported metrics without running the full pipeline.

Contents:

- Cascading-model CV fold predictions and AUC summaries (`y_fail` and `y_hf_fail` targets)
- RAG retrieval evaluation set: queries, expected incident IDs, recall@k traces
- SHAP feature-importance snapshots used in journey chapters

The cascading-model eval set drove the D016 → D019 branch-activation rules and the D018 partial reversal of D011 for `y_hf_fail`. RAG eval set scoped the D017 corpus expansion (PIF `_value` text + event recommendations).

See [Chapter 3 — Pair Features and the Cascade](../../docs/journey/03-cascade-model.md), [Chapter 4 — Two Explanation Signals](../../docs/journey/04-explainability-signals.md), and [Chapter 5 — Retrieval, Scoping, and the Domain Filter](../../docs/journey/05-rag-retrieval.md).
