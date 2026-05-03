# RAG Retrieval System — Architecture Overview

**Version:** v1.0-rag-baseline
**Date:** 2026-03-05
**Tag:** `v1.0-rag-baseline` (commit `826f5f7`)

---

## 1. Project Overview

The RAG (Retrieval-Augmented Generation) subsystem provides structured retrieval of barrier controls and incident records from the Bowtie Risk Analytics corpus. It enables queries like "Which barriers failed during gas release incidents?" by combining semantic vector search with metadata filtering and rank fusion.

The system is designed as a retrieval-only pipeline — it does **not** call an LLM. It produces structured context text suitable for downstream LLM consumption or direct analytical use.

### Key Design Principles

- **Deterministic output** — identical queries produce identical results (no randomness)
- **Backward compatible** — optional components (reranker) do not alter baseline behavior when disabled
- **Reproducible evaluation** — evaluation dataset and results are version-controlled

---

## 2. Dataset Description

The retrieval corpus is built from V2.3 incident JSON files extracted from BSEE and CSB investigation reports.

| Dimension | Count |
|-----------|-------|
| Incidents | 526 |
| Barrier controls | 3,253 |
| Barrier families | 25 distinct |
| PIF dimensions | 12 (people/work/organisation) |
| Evaluation queries | 50 |

### Corpus Construction

V2.3 JSON files are processed by `src/rag/corpus_builder.py` into two CSV document tables:

- **`barrier_documents.csv`** — One row per control: barrier text, family assignment, PIF flags, evidence, incident summary
- **`incident_documents.csv`** — One row per incident: top event, type, operating phase, materials, summary

Barrier families are assigned using rule-based keyword matching from `scripts/association_mining/event_barrier_normalization.py`, dispatching on `(side, barrier_type)` quadrant.

---

## 3. Retrieval Architecture

```
                         User Query
                             |
                    +--------+--------+
                    |                 |
              barrier_query     incident_query
                    |                 |
                    v                 v
          +------------------+  +------------------+
          | SentenceTransf.  |  | SentenceTransf.  |
          | embed(query)     |  | embed(query)     |
          +------------------+  +------------------+
                    |                 |
          +--------v--------+  +-----v-----------+
          | FAISS IndexFlatIP|  | FAISS IndexFlatIP|
          | + metadata mask  |  | (no mask)        |
          | top_k=50         |  | top_k=20         |
          +---------+--------+  +-----+-----------+
                    |                 |
                    +--------+--------+
                             |
                    Pipeline 3: Intersect
                    (barrier.parent_incident IN incident_results)
                             |
                    Pipeline 4: RRF Ranking
                    score = 1/(k+barrier_rank) + 1/(k+incident_rank)
                             |
                    Sort by RRF desc -> top_k=10
                             |
               +-------------+-------------+
               |                           |
          [reranker=None]           [reranker=CrossEncoder]
               |                           |
               v                     Over-retrieve 30
          Final Results              CrossEncoder.predict()
                                     Sort by rerank_score desc
                                     Truncate to top_k=10
                                           |
                                     Final Results
                                           |
                                     ContextBuilder
                                     (structured text, 8000 char max)
                                           |
                                     ExplanationResult
```

### Module Map

| Module | Responsibility | Lines |
|--------|---------------|-------|
| `src/rag/config.py` | All pipeline constants | 25 |
| `src/rag/embeddings/base.py` | `EmbeddingProvider` ABC | 29 |
| `src/rag/embeddings/sentence_transformers_provider.py` | `all-mpnet-base-v2` provider | 28 |
| `src/rag/vector_index.py` | FAISS `IndexFlatIP` wrapper with mask support | 97 |
| `src/rag/corpus_builder.py` | V2.3 JSON -> barrier/incident CSVs | 282 |
| `src/rag/retriever.py` | 4-stage hybrid pipeline + `RetrievalResult` | 176 |
| `src/rag/reranker.py` | `CrossEncoderReranker` post-RRF rescoring | 97 |
| `src/rag/context_builder.py` | Structured text assembly with truncation | 71 |
| `src/rag/rag_agent.py` | `RAGAgent` orchestrator (`from_directory`, `explain`) | 212 |

### Dependency Graph

```
config.py  (constants, no project imports)
    ^
    |
embeddings/base.py  (EmbeddingProvider ABC)
    ^
    |
embeddings/sentence_transformers_provider.py  (all-mpnet-base-v2)
    ^
    |
vector_index.py  (FAISS IndexFlatIP wrapper)
    ^
    |
retriever.py  (HybridRetriever, RetrievalResult)
    ^            ^
    |            |
    |       reranker.py  (CrossEncoderReranker)
    |            ^
    |            |
    +--- rag_agent.py  (RAGAgent orchestrator)
              |
         context_builder.py  (ContextEntry, build_context)
```

---

## 4. Hybrid Retrieval — Phase 1

The baseline retrieval system uses a 4-stage pipeline implemented in `src/rag/retriever.py`.

### Stage 1: Barrier Similarity Search

- Embeds `barrier_query` using `SentenceTransformerProvider` (`all-mpnet-base-v2`, 768-dim, L2-normalized)
- Searches FAISS `IndexFlatIP` (exact inner-product = cosine similarity on normalized vectors)
- Supports optional metadata pre-filtering via boolean mask:
  - `barrier_family` — restrict to a specific family
  - `barrier_failed_human` — filter by human failure involvement
  - `pif_filters` — filter by Performance Influencing Factor flags (12 dimensions)
- Returns top 50 barriers (configurable via `TOP_K_BARRIERS`)

### Stage 2: Incident Similarity Search

- Embeds `incident_query` using the same provider
- Searches a separate FAISS index over incident embeddings
- No metadata filtering applied
- Returns top 20 incidents (configurable via `TOP_K_INCIDENTS`)

### Stage 3: Intersection

- Filters Stage 1 barrier results to only those whose parent incident was also retrieved in Stage 2
- Ensures dual relevance: barrier matches the barrier query AND its parent incident matches the incident query

### Stage 4: Reciprocal Rank Fusion (RRF)

```
rrf_score = 1/(k + barrier_rank) + 1/(k + incident_rank)
```

- `k = 60` (standard RRF constant, configurable via `RRF_K`)
- Barrier and incident ranks are 1-indexed
- Results sorted by RRF score descending
- Truncated to `top_k=10` (configurable via `TOP_K_FINAL`)

### FAISS Index Details

- Index type: `IndexFlatIP` (exact search, no approximation)
- L2 normalization enforced at build time with tolerance `1e-4`
- Masked search uses `faiss.knn()` on the subset of allowed vectors
- Supports save/load for persistence

---

## 5. Cross-Encoder Reranker — Phase 2

An optional post-RRF reranking stage implemented in `src/rag/reranker.py`.

### Model

| Property | Value |
|----------|-------|
| Model | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Parameters | ~22M |
| Architecture | 6-layer Transformer |
| Max sequence length | 512 tokens |
| Batch size | 32 |

### Pipeline Integration

When `reranker` is provided to `RAGAgent`:

1. **Over-retrieve** — Hybrid retriever returns top 30 (instead of top 10) via `TOP_K_RERANK=30`
2. **Build pairs** — Each candidate is paired with a combined query:
   - Query: `f"{barrier_query} {incident_query}"`
   - Passage: `f"Barrier: {name} - {role}\nIncident: {summary}"`
3. **Score** — `CrossEncoder.predict()` scores all pairs in a single batch
4. **Sort** — Candidates sorted by `(-rerank_score, -rrf_score)` (Timsort, stable)
5. **Truncate** — Return top 10 (`FINAL_TOP_K`)

### Activation

The reranker is **disabled by default**. Controlled by dependency injection:

```python
# Without reranker (Phase-1 behavior)
agent = RAGAgent.from_directory(rag_dir, embedding_provider)

# With reranker (Phase-2 behavior)
reranker = CrossEncoderReranker()
agent = RAGAgent.from_directory(rag_dir, embedding_provider, reranker=reranker)
```

When `reranker=None`, the pipeline is identical to Phase 1 — no over-retrieval, no rescoring.

---

## 6. Evaluation Methodology

### Dataset

- 50 evaluation queries covering 25 distinct barrier families
- Queries reflect real oil and gas incident scenarios
- Families span all 4 quadrants: prevention/mitigation x administrative/engineering
- Stored in `data/evaluation/rag_queries.json`

### Metrics

| Metric | Definition |
|--------|-----------|
| **Top-1** | Fraction of queries where expected barrier family appears at rank 1 |
| **Top-5** | Fraction of queries where expected barrier family appears in top 5 |
| **Top-10** | Fraction of queries where expected barrier family appears in top 10 |
| **MRR** | Mean Reciprocal Rank — average of 1/rank for the first correct hit |

### Evaluation Protocol

Both systems evaluated on the same 50 queries:
- **Baseline:** HybridRetriever -> RRF -> top 10
- **Reranked:** HybridRetriever -> RRF -> top 30 -> CrossEncoderReranker -> top 10

Matching criteria: expected `barrier_family` matches the `barrier_family` field of retrieval results.

---

## 7. Evaluation Results

| Metric | Baseline | Reranked | Delta | % Change |
|--------|----------|----------|-------|----------|
| Top-1  | 0.30     | 0.30     | +0.00 | +0.0%    |
| Top-5  | 0.56     | 0.56     | +0.00 | +0.0%    |
| Top-10 | 0.62     | 0.60     | -0.02 | -3.2%    |
| MRR    | 0.40     | 0.42     | +0.01 | +3.1%    |

### Per-Query Analysis

- Improved queries: 9
- Degraded queries: 6
- Unchanged / both miss: 35

Notable improvements:
- Query 36 (communication/crane lift): rank 5 -> 1 (+4 positions)
- Query 27 (change management): rank 3 -> 1 (+2)
- Query 1 (PSV overpressure): rank 3 -> 1 (+2)

Notable degradations:
- Query 11 (fire suppression): rank 1 -> 5 (-4)
- Query 41 (fluid containment): rank 10 -> miss (lost from top-10)

---

## 8. Performance Metrics

### Latency

| Metric | Baseline | Reranked | Overhead |
|--------|----------|----------|----------|
| Avg    | 19 ms    | 24 ms    | +5 ms   |
| P95    | 77 ms    | 35 ms    | -42 ms* |
| Max    | 169 ms   | 95 ms    | -74 ms* |

*P95/Max improvement in reranked runs is a measurement artifact (warm cache). The meaningful metric is avg overhead: **+5 ms**.

### Memory

| Component | Size |
|-----------|------|
| Before agents | 1,301 MB |
| After baseline agent load | 1,328 MB (+27 MB) |
| After reranker model load | 1,357 MB (+29 MB) |
| **Total reranker overhead** | **29 MB** |

---

## 9. Bottleneck Analysis

```
Query -> [Bi-Encoder Recall] -> [Intersection] -> [RRF Ranking] -> [Reranking]
              ^                                                         ^
              |                                                         |
         PRIMARY BOTTLENECK                                   MARGINAL GAIN
         40% of queries miss                                  MRR +3.1%
         in both systems                                      below 5% threshold
```

**Finding:** 20 out of 50 queries (40%) returned no correct result in top 10 for either system. The reranker cannot improve results that were never retrieved.

### Root Cause Breakdown

| Issue | Impact | Evidence |
|-------|--------|----------|
| Bi-encoder semantic gap | HIGH | Barrier embedding text ("Barrier: X / Role: Y / LOD: Z") may not capture all retrieval-relevant semantics |
| Small corpus | MODERATE | 526 incidents may not contain relevant examples for all 25 query barrier families |
| Single embedding model | MODERATE | `all-mpnet-base-v2` is a general-purpose model, not domain-tuned for oil and gas terminology |
| Intersection filter | LOW | Reduces candidate pool but ensures dual relevance |

---

## 10. Final Design Decision

**Cross-encoder reranker is kept optional (disabled by default).**

### Rationale

1. MRR improvement (+3.1%) is below the 5% significance threshold
2. Top-1 and Top-5 are unchanged; Top-10 slightly degraded (-3.2%)
3. The primary bottleneck is recall (40% complete miss rate), not ranking
4. Latency and memory overhead are negligible (+5 ms, +29 MB)
5. Infrastructure is in place for future activation when corpus grows

### Configuration

```python
# src/rag/config.py
RERANKER_ENABLED = True     # Flag for future A/B toggle (currently unused in code)
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANKER_MAX_LENGTH = 512
RERANKER_BATCH_SIZE = 32
TOP_K_RERANK = 30           # Over-retrieval depth when reranker active
FINAL_TOP_K = 10            # Output size after reranking
```

---

## 11. Modeling Team Data Requirements

For teams building on top of the RAG retrieval layer:

### Input Format

```python
from src.rag.rag_agent import RAGAgent

result = agent.explain(
    barrier_query="pressure relief valve failed to activate",
    incident_query="gas release during well intervention",
    barrier_family="pressure_safety",     # optional filter
    barrier_failed_human=True,            # optional filter
    pif_filters={"competence": True},     # optional filter
    top_k=10,
    max_context_chars=8000,
)
```

### Output Format

`ExplanationResult` contains:

| Field | Type | Description |
|-------|------|-------------|
| `context_text` | `str` | Structured markdown text (max 8000 chars) for LLM context window |
| `results` | `list[RetrievalResult]` | Ranked list with scores, IDs, metadata |
| `metadata` | `dict` | Query parameters and result count |

### RetrievalResult Fields

| Field | Type | Description |
|-------|------|-------------|
| `incident_id` | `str` | Parent incident identifier |
| `control_id` | `str` | Barrier control identifier |
| `barrier_family` | `str` | Normalized barrier family name |
| `barrier_failed_human` | `bool` | Whether human failure was involved |
| `rrf_score` | `float` | Reciprocal Rank Fusion score |
| `barrier_rank` | `int` | Rank in barrier similarity search |
| `incident_rank` | `int` | Rank in incident similarity search |
| `barrier_sim_score` | `float` | Cosine similarity (barrier) |
| `incident_sim_score` | `float` | Cosine similarity (incident) |
| `rerank_score` | `float or None` | Cross-encoder score (None if reranker disabled) |

### Required Data Files

```
rag_dir/
  datasets/
    barrier_documents.csv      # Built by corpus_builder
    incident_documents.csv     # Built by corpus_builder
  embeddings/
    barrier_embeddings.npy     # Pre-computed, L2-normalized
    incident_embeddings.npy    # Pre-computed, L2-normalized
```

---

## 12. Future Improvements

### Priority 1 — Improve Recall (addresses 40% miss rate)

| Improvement | Expected Impact | Complexity |
|-------------|----------------|------------|
| BM25 hybrid search (sparse + dense) | HIGH — captures exact keyword matches that bi-encoder misses | MODERATE |
| Query expansion (synonyms, acronyms) | MODERATE — oil and gas terminology has many variants | LOW |
| Domain-tuned embedding model | HIGH — fine-tune on incident/barrier pairs | HIGH |

### Priority 2 — Corpus Growth

| Improvement | Expected Impact | Complexity |
|-------------|----------------|------------|
| Ingest PHMSA pipeline incidents | MODERATE — adds pipeline-specific barriers | LOW |
| Ingest TSB transportation incidents | MODERATE — cross-domain barrier patterns | LOW |
| Re-evaluate reranker at 1000+ incidents | Reranker value increases with more candidates to disambiguate | LOW |

### Priority 3 — System Hardening

| Improvement | Expected Impact | Complexity |
|-------------|----------------|------------|
| Try/except around model loading with Phase-1 fallback | Prevents startup crash if model download fails | LOW |
| Extract shared `_find_meta()` utility | Reduces code duplication between reranker and agent | LOW |
| Add `RerankerProtocol` for type safety | Enables alternative reranker implementations | LOW |
| Real-model smoke test (`@pytest.mark.slow`) | Catches tokenizer/model compatibility issues | LOW |

---

## Test Coverage Summary

| Test File | Tests | Coverage Area |
|-----------|-------|--------------|
| `tests/test_rag_embeddings.py` | 4 | Embedding provider interface |
| `tests/test_rag_vector_index.py` | 7 | FAISS index build, search, mask, L2 validation |
| `tests/test_rag_corpus_builder.py` | 15 | Barrier/incident document construction |
| `tests/test_rag_retriever.py` | 9 | 4-stage hybrid pipeline, RRF scoring |
| `tests/test_rag_reranker.py` | 6 | Cross-encoder scoring, sorting, edge cases |
| `tests/test_rag_context_builder.py` | 3 | Text assembly and truncation |
| `tests/test_rag_agent.py` | 10 | Orchestrator wiring, with/without reranker |
| `tests/test_rag_integration.py` | 3 | End-to-end pipeline integration |
| **Total** | **57** | All RAG modules |

**Full test suite: 362 passed, 1 skipped, 0 failures.**

---

## Artifact Inventory

| Artifact | Path | Purpose |
|----------|------|---------|
| Evaluation queries | `data/evaluation/rag_queries.json` | 50 curated queries |
| Evaluation results | `data/evaluation/results/evaluation_results.json` | Full metric results |
| Evaluation report | `docs/reports/rag_phase2_evaluation.md` | Analysis and recommendation |
| Implementation audit | `docs/reports/rag_phase2_implementation_audit.md` | Design compliance review |
| Phase-2 design | `docs/plans/2026-03-05-rag-phase2-cross-encoder-reranking-design.md` (local-only) | Reranker design document |
| Phase-2 plan | `docs/plans/2026-03-05-rag-phase2-cross-encoder-reranking-plan.md` (local-only) | Implementation plan |
| Evaluation script | `scripts/evaluate_retrieval.py` | Automated evaluation harness |
| This document | `docs/rag_system_overview.md` | System architecture overview |
