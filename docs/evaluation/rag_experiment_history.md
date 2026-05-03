# RAG Experiment History

**Version:** v1.0-rag-baseline
**Date:** 2026-03-05
**Corpus:** 526 BSEE incidents, 3,253 barrier controls

This document records the research evolution of the RAG retrieval system across three experiments, from baseline hybrid retrieval through cross-encoder reranking to the framework that informed the final design decision.

---

## Experiment 1 — Hybrid Retrieval Baseline

**Branch:** `feature/rag-hybrid-retrieval`
**Commits:** `6eadb6b` through `b4ccd22` (12 commits)
**Status:** Complete

### Objective

Build a retrieval system that, given a natural-language barrier query and incident query, returns the most relevant barrier controls from the V2.3 incident corpus. The system must support structured metadata filtering (barrier family, human failure, PIF dimensions) and produce deterministic, ranked results suitable for downstream LLM context injection.

### Implementation

A 4-stage hybrid retrieval pipeline:

| Stage | Component | Implementation |
|-------|-----------|---------------|
| 1. Embed + Search | Bi-encoder barrier search | `all-mpnet-base-v2` (768-dim, L2-normalized) via FAISS `IndexFlatIP` with optional boolean metadata mask. Top 50 barriers. |
| 2. Embed + Search | Bi-encoder incident search | Same embedding model, separate FAISS index. Top 20 incidents. No metadata filter. |
| 3. Intersect | Dual-relevance filter | Retain only barriers whose parent incident also appeared in the incident results. |
| 4. Rank | Reciprocal Rank Fusion | `score = 1/(60 + barrier_rank) + 1/(60 + incident_rank)`. Sort descending, return top 10. |

Supporting infrastructure:
- **Corpus builder** (`src/rag/corpus_builder.py`) — Converts V2.3 JSON into `barrier_documents.csv` and `incident_documents.csv`. Assigns barrier families via rule-based keyword normalization from `scripts/association_mining/event_barrier_normalization.py`. Extracts 12 PIF flags per incident.
- **Embedding provider** (`src/rag/embeddings/`) — ABC with `SentenceTransformerProvider` implementation. `normalize_embeddings=True` ensures unit vectors for cosine similarity via inner product.
- **Vector index** (`src/rag/vector_index.py`) — FAISS wrapper with L2 normalization validation at build time (tolerance 1e-4). Supports masked search via `faiss.knn()` over subset.
- **Context builder** (`src/rag/context_builder.py`) — Assembles structured markdown from retrieval results with 8,000 character truncation.
- **RAG agent** (`src/rag/rag_agent.py`) — Orchestrator with `from_directory()` factory and `explain()` entry point. Loads CSV metadata and numpy embeddings. Does NOT call an LLM.

### Assessment Approach

Phase-1 was validated through unit and integration tests (no quantitative retrieval metrics yet):

| Test Suite | Tests | Coverage |
|------------|-------|---------|
| `test_rag_embeddings.py` | 4 | Embedding interface, dimension, normalization |
| `test_rag_vector_index.py` | 7 | Index build, search, mask, L2 validation, save/load |
| `test_rag_corpus_builder.py` | 15 | Barrier/incident document construction, PIF extraction, family assignment |
| `test_rag_retriever.py` | 7 | RRF scoring, 4-stage pipeline, metadata filtering, empty results |
| `test_rag_context_builder.py` | 3 | Text assembly, truncation, empty input |
| `test_rag_agent.py` | 8 | Orchestrator wiring, from_directory, explain output |
| `test_rag_integration.py` | 2 | End-to-end pipeline with mock embeddings |

Total: 46 tests, all passing. Full suite: 351 passed.

### Results

Qualitative validation confirmed:
- Metadata filters correctly narrow results (barrier family, PIF flags, human failure)
- Intersection stage ensures dual relevance between barrier and incident queries
- RRF ranking produces stable, deterministic ordering
- Context builder respects character limits and formats structured markdown
- L2 normalization is enforced at index build time — unnormalized vectors rejected

No quantitative retrieval metrics were computed in Experiment 1. This gap motivated Experiment 3.

### Insights

1. **Dual-index architecture works well** — Separate barrier and incident embeddings allow independent filtering while intersection ensures coherent results.
2. **Metadata pre-filtering is essential** — Without barrier family or PIF filters, results are dominated by the most common barrier types.
3. **RRF is a robust rank aggregation method** — Simple, parameter-light (only `k=60`), and does not require score normalization between the two search pipelines.
4. **No quantitative baseline existed** — Without retrieval metrics, it was impossible to measure whether improvements actually improved anything. This became the key motivation for Experiment 3.
5. **Corpus builder is the most complex module** — Barrier family assignment depends on external normalization taxonomy, creating a coupling point that needs monitoring.

---

## Experiment 2 — Cross-Encoder Reranking

**Branch:** `feature/rag-retrieval-improvements`
**Commits:** `7848178` through `6c79528` (5 commits)
**Status:** Complete (kept optional)

### Objective

Determine whether a cross-encoder reranking stage, applied after RRF ranking, improves retrieval precision. Cross-encoders process the full (query, passage) pair jointly, enabling richer semantic matching than bi-encoder similarity alone. The hypothesis was that reranking the top 30 RRF candidates would improve Top-1 accuracy and MRR.

### Implementation

Added `CrossEncoderReranker` as an optional post-RRF stage:

| Component | Detail |
|-----------|--------|
| Model | `cross-encoder/ms-marco-MiniLM-L-6-v2` (22M params, 6-layer Transformer) |
| Max tokens | 512 (model's architectural limit) |
| Batch size | 32 (all 30 candidates fit in one batch) |
| Over-retrieval | Hybrid retriever returns top 30 (instead of 10) when reranker is active |
| Query format | `f"{barrier_query} {incident_query}"` |
| Passage format | `f"Barrier: {name} - {role}\nIncident: {summary}"` |
| Scoring | `CrossEncoder.predict()` returns raw logits per pair |
| Sorting | `(-rerank_score, -rrf_score)` — rerank score primary, RRF tiebreak |
| Output | Top 10 after reranking |

Integration into `RAGAgent.explain()`:

```python
# Over-retrieve when reranker present
retrieve_top_k = TOP_K_RERANK if self._reranker is not None else top_k

results = self._retriever.retrieve(..., top_k=retrieve_top_k)

# Phase-2: Cross-encoder reranking
if self._reranker is not None and results:
    results = self._reranker.rerank(
        barrier_query, incident_query, results, self._barrier_meta, top_k
    )
```

When `reranker=None`, the code path is identical to Experiment 1. Backward compatibility verified by explicit test.

### Assessment Approach

Reranker correctness validated through 11 new tests:

| Test | What It Validates |
|------|------------------|
| `test_rerank_scores_and_sorts` | Score assignment and descending sort order |
| `test_rerank_top_k_truncates` | Output capped at requested top_k |
| `test_rerank_rrf_tiebreak` | Equal rerank scores resolve by higher RRF |
| `test_rerank_empty_candidates` | Empty input returns empty output, no model call |
| `test_rerank_passage_composition` | Query/passage format matches design spec |
| `test_rerank_logs_latency` | Debug log emits `reranker_latency_ms` and `num_candidates` |
| `test_explain_with_reranker_calls_rerank` | Agent wiring invokes reranker with correct arguments |
| `test_explain_without_reranker_unchanged` | Agent without reranker produces Phase-1 output, `rerank_score=None` |
| `test_end_to_end_with_reranker` | Full pipeline integration with mock cross-encoder |
| `test_default_rerank_score_is_none` | `RetrievalResult.rerank_score` defaults to `None` |
| `test_rerank_score_can_be_set` | Explicit assignment works |

All tests mock the cross-encoder model. No real model inference in the test suite.

Full suite after Experiment 2: 362 passed, 1 skipped.

### Results

Quantitative assessment was performed in Experiment 3 (see below). Experiment 2 focused on implementation correctness and architecture validation.

Implementation audit (`docs/reports/rag_phase2_implementation_audit.md`) confirmed:
- All 12 design requirements met (FULLY COMPLIANT)
- No circular dependencies
- Clean separation of responsibilities
- One minor deviation: `RERANKER_ENABLED` config constant defined but unused in code (enablement controlled by dependency injection)

Production readiness score: **8.3/10** — gaps in defensive error handling around model loading and richer observability, neither blocking.

### Insights

1. **Dependency injection > config flag** — Controlling reranker via `reranker=None` parameter proved cleaner than a boolean config flag. The code path is explicitly visible.
2. **Over-retrieval is cheap** — Retrieving 30 instead of 10 from FAISS adds negligible latency. The cost is entirely in cross-encoder inference.
3. **MiniLM-L-6 is extremely lightweight** — 22M params, 29 MB memory overhead, ~5ms average latency. The model choice was correct for this scale.
4. **Passage format matters** — Labeled fields (`Barrier:`, `Incident:`) help the cross-encoder disambiguate the two semantic dimensions. This was Design Option B and proved more structured than raw concatenation.
5. **Metadata lookup duplication** — Both `reranker._find_meta()` and `rag_agent._find_barrier_meta()` implement identical linear scans. Flagged for future extraction into a shared utility.

---

## Experiment 3 — Retrieval Assessment Framework

**Branch:** `feature/rag-retrieval-improvements`
**Commits:** `ab81992` through `a05b94b` (2 commits)
**Status:** Complete

### Objective

Build a reproducible assessment framework to quantitatively compare baseline (Phase-1) and reranked (Phase-2) retrieval pipelines. Answer the question: does cross-encoder reranking improve retrieval quality enough to justify enabling by default?

### Implementation

#### Dataset

50 curated queries stored in `data/evaluation/rag_queries.json`. Each query specifies:

```json
{
  "barrier_query": "pressure safety valve overpressure protection",
  "incident_query": "vessel rupture due to overpressurization",
  "expected_barrier": "overpressurization_gas_discharge_gas_isolation"
}
```

Coverage: 25 distinct barrier families across all 4 quadrants (prevention/mitigation x administrative/engineering). Query pairs designed to reflect real oil and gas incident investigation questions.

#### Harness

`scripts/evaluate_retrieval.py` (522 lines) implements:

1. **Corpus loading** — Reads barrier/incident CSVs and pre-computed embeddings
2. **Agent construction** — Builds baseline agent (no reranker) and reranked agent (with `CrossEncoderReranker`)
3. **Query execution** — Runs all 50 queries through both pipelines
4. **Metric computation** — Top-1, Top-5, Top-10 hit rates and MRR
5. **Per-query delta analysis** — Tracks rank changes per query between systems
6. **Latency benchmarking** — Measures avg, P95, max latency per pipeline
7. **Memory profiling** — RSS before/after agent and model loading
8. **Failure mode tests** — Normal query, no-match query, single-result edge cases
9. **Results export** — Full results to `data/evaluation/results/evaluation_results.json`

Matching criteria: expected `barrier_family` string matches the `barrier_family` field of any result in the top-K.

### Results

#### Retrieval Quality

| Metric | Baseline | Reranked | Delta | % Change |
|--------|----------|----------|-------|----------|
| Top-1  | 0.30     | 0.30     | +0.00 | +0.0%    |
| Top-5  | 0.56     | 0.56     | +0.00 | +0.0%    |
| Top-10 | 0.62     | 0.60     | -0.02 | -3.2%    |
| MRR    | 0.40     | 0.42     | +0.01 | +3.1%    |

#### Per-Query Breakdown

- Improved: 9 queries (reranker moved correct result to higher rank)
- Degraded: 6 queries (reranker pushed correct result lower or out of top 10)
- Unchanged: 15 queries (same rank in both systems)
- Both miss: 20 queries (correct barrier family not in top 10 for either system)

Notable improvements:
| Query | Topic | Rank Change |
|-------|-------|-------------|
| 36 | Communication / crane lift | 5 -> 1 (+4) |
| 27 | Change management | 3 -> 1 (+2) |
| 1 | PSV overpressure | 3 -> 1 (+2) |
| 7 | H2S detection | 4 -> 2 (+2) |

Notable degradations:
| Query | Topic | Rank Change |
|-------|-------|-------------|
| 11 | Fire suppression | 1 -> 5 (-4) |
| 9 | Atmospheric monitoring | 2 -> 5 (-3) |
| 41 | Fluid containment | 10 -> miss (lost) |

#### Performance

| Metric | Baseline | Reranked |
|--------|----------|----------|
| Avg latency | 19 ms | 24 ms (+5 ms) |
| Memory overhead | — | +29 MB |

#### Failure Mode Tests

All 5 passed: normal query, reranked normal query, no-match query, single-result baseline, single-result reranked. System degrades gracefully in all edge cases.

### Insights

1. **Recall is the bottleneck, not ranking** — 40% of queries (20/50) missed in both systems. The reranker cannot improve results that were never retrieved. This is the single most important finding.

2. **MRR +3.1% is below significance threshold** — The pre-defined threshold for enabling the reranker by default was +5% MRR improvement. The observed +3.1% does not clear this bar.

3. **Reranker helps specific query types** — Change management, communication, and overpressurization queries showed significant rank improvements (+2 to +4 positions). These are queries where the barrier/incident semantic distinction is important and the cross-encoder's joint inference adds value.

4. **Reranker can hurt at the margin** — Query 41 (fluid containment) was at rank 10 in baseline and dropped out of top 10 after reranking. Over-retrieval (30 candidates) introduces new candidates that can displace marginal correct results.

5. **Latency overhead is negligible** — +5 ms average with GPU. The MiniLM-L-6 model is effectively free at this corpus scale.

6. **Dataset quality matters** — The 50 queries are hand-curated but may not represent the full distribution of real user queries. Future work should expand the dataset and consider automated query generation.

---

## Decision Summary

Based on the three experiments, the following design decisions were made:

| Decision | Rationale |
|----------|-----------|
| **Keep hybrid retrieval as the default pipeline** | Validated across 362 tests and 50 queries. Stable, deterministic, sub-20ms latency. |
| **Keep cross-encoder reranker as optional** | MRR +3.1% below 5% threshold. Recall bottleneck dominates. Infrastructure preserved for future activation. |
| **Prioritize recall improvements next** | 40% miss rate is the primary limitation. BM25 hybrid search, query expansion, and domain-tuned embeddings are higher-impact than ranking refinements. |
| **Re-assess reranker at 1000+ incidents** | As corpus grows, more candidates per query means more disambiguation opportunity for the cross-encoder. |

---

## Artifact Cross-Reference

| Artifact | Path | Experiment |
|----------|------|------------|
| Hybrid retrieval implementation | `src/rag/retriever.py`, `src/rag/rag_agent.py` | 1 |
| Corpus builder | `src/rag/corpus_builder.py` | 1 |
| Embedding provider | `src/rag/embeddings/` | 1 |
| FAISS vector index | `src/rag/vector_index.py` | 1 |
| Context builder | `src/rag/context_builder.py` | 1 |
| Cross-encoder reranker | `src/rag/reranker.py` | 2 |
| Reranker config | `src/rag/config.py` (lines 18-24) | 2 |
| Implementation audit | `docs/reports/rag_phase2_implementation_audit.md` | 2 |
| Phase-2 design doc | `docs/plans/2026-03-05-rag-phase2-cross-encoder-reranking-design.md` (local-only) | 2 |
| Phase-2 implementation plan | `docs/plans/2026-03-05-rag-phase2-cross-encoder-reranking-plan.md` (local-only) | 2 |
| Query dataset (50 queries) | `data/evaluation/rag_queries.json` | 3 |
| Results JSON | `data/evaluation/results/evaluation_results.json` | 3 |
| Harness script | `scripts/evaluate_retrieval.py` | 3 |
| Assessment report | `docs/reports/rag_phase2_evaluation.md` | 3 |
| System architecture overview | `docs/rag_system_overview.md` | All |

---

## Commit History

### Experiment 1 (Phase-1 Hybrid Retrieval)

```
6eadb6b feat(rag): add config constants
13d6e26 feat(rag): add EmbeddingProvider ABC
ba6b3c5 feat(rag): add SentenceTransformerProvider
de1f426 test(rag): verify barrier family normalization imports
2157667 feat(rag): add barrier family assignment and text composition
df3bc13 feat(rag): add corpus builder for barrier and incident documents
007a3d8 feat(rag): add FAISS IndexFlatIP wrapper with mask support
8fd4536 feat(rag): add 4-stage hybrid retriever with RRF ranking
9b6f4f7 feat(rag): add deterministic context builder
5a2c252 feat(rag): add RAG agent orchestrator
4bee5fd chore: add sentence-transformers and faiss-cpu dependencies
17cab05 test(rag): add end-to-end integration test
b4ccd22 test(rag): add L2 normalization validation test for VectorIndex.build()
```

### Experiment 2 (Phase-2 Cross-Encoder Reranking)

```
ec6df45 docs: add Phase-2 cross-encoder reranking design
8046c19 docs: add Phase-2 cross-encoder reranking implementation plan
7848178 feat(rag): add reranker config constants
a3d102d feat(rag): add rerank_score field to RetrievalResult
8165f5f feat(rag): add CrossEncoderReranker with latency logging
9fbb582 feat(rag): wire CrossEncoderReranker into RAGAgent
6c79528 test(rag): add reranker integration test
```

### Experiment 3 (Assessment Framework)

```
ab81992 add Phase-2 harness, audit, and results report
a05b94b feat(rag): add harness and phase-2 retrieval report
```
