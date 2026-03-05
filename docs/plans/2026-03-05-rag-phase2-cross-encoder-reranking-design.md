# RAG Phase-2: Cross-Encoder Reranking Design

**Date:** 2026-03-05
**Branch:** `feature/rag-hybrid-retrieval`
**Prerequisite:** Phase-1 hybrid retrieval system (complete, 351 tests passing)

---

## Goal

Improve retrieval accuracy by adding a cross-encoder reranking stage after the existing RRF ranking. The reranker re-scores the top candidates using full (query, passage) pair inference, producing more semantically precise rankings than bi-encoder similarity alone.

## Decision Context

- **Corpus size:** ~147 incidents, ~500–800 barriers (small enough that reranking 30 candidates is nearly free)
- **Cross-encoder reranking** is the highest-impact Phase-2 improvement at this scale
- **BM25 hybrid search** deferred — evaluate after measuring reranking impact
- **Query expansion** deferred — revisit if recall issues emerge with larger corpus

## Architecture

### Current Pipeline (Phase-1)

```
query → embed → FAISS search → metadata filter → intersection → RRF rank → top-K → context assembly
```

### Phase-2 Pipeline

```
query → embed → FAISS search → metadata filter → intersection → RRF rank → top-N candidates → cross-encoder rerank → final top-K → context assembly
```

The reranker is an **additive stage** inserted inside `RAGAgent.explain()`, between `retriever.retrieve()` and `build_context()`. The retriever itself is unchanged.

### Data Flow

```
RAGAgent.explain()
  ├─ retriever.retrieve(top_k=TOP_K_RERANK)    # over-retrieve (default 30)
  ├─ reranker.rerank(query, candidates, top_k)  # cross-encoder rescore → final 10
  └─ build_context(reranked_results)
```

If no reranker is configured (or `RERANKER_ENABLED = False`), the pipeline behaves identically to Phase-1.

## Scoring Strategy

**Concatenated query vs concatenated passage** (Option B from design discussion):

- **Query:** `f"{barrier_query} {incident_query}"`
- **Passage:** `f"Barrier: {barrier_name} — {barrier_role}\nIncident: {incident_summary}"`

Labels (`Barrier:`, `Incident:`) added to passage fields for cross-encoder disambiguation.

**Sorting:** Primary sort by `rerank_score` descending, tie-break by `rrf_score` descending.

## Config Constants

Added to `src/rag/config.py`:

```python
RERANKER_ENABLED = True
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANKER_MAX_LENGTH = 512
RERANKER_BATCH_SIZE = 32
TOP_K_RERANK = 30
FINAL_TOP_K = 10
```

## New Module: `src/rag/reranker.py`

```python
class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str = RERANKER_MODEL,
        max_length: int = RERANKER_MAX_LENGTH,
        batch_size: int = RERANKER_BATCH_SIZE,
    ) -> None: ...

    def rerank(
        self,
        barrier_query: str,
        incident_query: str,
        candidates: list[RetrievalResult],
        barrier_metadata: list[dict],
        top_k: int = FINAL_TOP_K,
    ) -> list[RetrievalResult]: ...
```

**Internals:**
- Builds `(query, passage)` pairs for each candidate
- Calls `cross_encoder.predict()` in batches of `batch_size`
- Passage truncated to `max_length` tokens (handled by CrossEncoder tokenizer)
- Attaches `rerank_score` to each `RetrievalResult`
- Sorts by `rerank_score` desc, `rrf_score` desc tie-break
- Logs `reranker_latency_ms` and `num_candidates` at debug level
- Returns top-K results

## Changes to Existing Modules

### `src/rag/retriever.py` — `RetrievalResult`

Add one optional field (backward compatible):

```python
rerank_score: float | None = None
```

### `src/rag/rag_agent.py` — `RAGAgent`

- `__init__()` accepts optional `reranker: CrossEncoderReranker | None`
- `from_directory()` accepts optional `reranker` param
- `explain()` checks `self._reranker is not None`:
  - Yes: over-retrieve with `top_k=TOP_K_RERANK`, call `reranker.rerank()`, pass reranked results to `build_context()`
  - No: identical behavior to Phase-1

### `src/rag/config.py`

Add 6 new constants (listed above).

## Dependencies

`sentence-transformers` (already installed) includes `CrossEncoder` — no new pip package needed.

## Testing Strategy

| Test File | Coverage |
|-----------|----------|
| `tests/test_rag_reranker.py` (new) | Mock `CrossEncoder.predict()`, verify scoring, sorting, batching, config flag toggle, latency logging |
| `tests/test_rag_integration.py` (modify) | Add test path exercising reranking with mock cross-encoder |
| Backward compat | Verify `RAGAgent` without reranker produces identical results to Phase-1 |

## Files Summary

| File | Change |
|------|--------|
| `src/rag/reranker.py` | **New** — `CrossEncoderReranker` |
| `src/rag/config.py` | Add 6 constants |
| `src/rag/retriever.py` | Add `rerank_score` field to `RetrievalResult` |
| `src/rag/rag_agent.py` | Wire reranker into `explain()` and `from_directory()` |
| `tests/test_rag_reranker.py` | **New** — unit tests |
| `tests/test_rag_integration.py` | Add reranker integration path |

## Future Considerations

- **BM25 hybrid search:** Evaluate after measuring cross-encoder impact. Would add a parallel BM25 retrieval signal fused into RRF.
- **Query expansion:** Revisit if recall issues emerge with larger corpus.
- **Observability:** Latency logging included from day one. Structured metrics (Prometheus/etc.) can wrap the debug logs later.
