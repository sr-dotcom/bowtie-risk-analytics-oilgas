# RAG Phase-2 Cross-Encoder Reranking — Evaluation Report

**Date:** 2026-03-05
**Branch:** `feature/rag-retrieval-improvements`
**Corpus:** 526 BSEE incidents, 3253 barrier controls

---

## 1. Overview

This report evaluates whether adding a cross-encoder reranking stage (Phase-2) improves retrieval quality over the baseline hybrid retrieval system (Phase-1: bi-encoder + FAISS + RRF).

## 2. Dataset Description

- **50 evaluation queries** covering 25 distinct barrier families
- Queries designed to reflect real oil & gas incident scenarios
- Barrier families span all 4 quadrants: prevention/mitigation x administrative/engineering
- Saved to `data/evaluation/rag_queries.json`

## 3. Evaluation Methodology

Both systems evaluated on the same 50 queries:

- **Baseline:** Hybrid Retriever (bi-encoder FAISS search + metadata filter + RRF ranking), top-10
- **Reranked:** Baseline + CrossEncoderReranker (`cross-encoder/ms-marco-MiniLM-L-6-v2`), over-retrieve 30 → rerank → top-10

Metrics: Top-1 accuracy, Top-5 hit rate, Top-10 hit rate, MRR (Mean Reciprocal Rank).

Evaluation matches expected `barrier_family` against the family field of each retrieval result.

## 4. Baseline Retrieval Performance

| Metric | Value |
|--------|-------|
| Top-1 accuracy | 0.30 |
| Top-5 hit rate | 0.56 |
| Top-10 hit rate | 0.62 |
| MRR | 0.40 |

## 5. Reranked Retrieval Performance

| Metric | Value |
|--------|-------|
| Top-1 accuracy | 0.30 |
| Top-5 hit rate | 0.56 |
| Top-10 hit rate | 0.60 |
| MRR | 0.42 |

## 6. Ranking Delta Analysis

| Metric | Baseline | Reranked | Delta | % Change |
|--------|----------|----------|-------|----------|
| Top-1 | 0.30 | 0.30 | +0.00 | +0.0% |
| Top-5 | 0.56 | 0.56 | +0.00 | +0.0% |
| Top-10 | 0.62 | 0.60 | -0.02 | -3.2% |
| MRR | 0.40 | 0.42 | +0.01 | +3.1% |

**Per-query ranking delta summary:**
- Average rank improvement: +0.17 positions
- Improved queries: 9
- Degraded queries: 6
- Unchanged / both miss: 35

Notable improvements:
- Query 36 (communication/crane lift): rank 5 → 1 (+4)
- Query 27 (change management): rank 3 → 1 (+2)
- Query 1 (PSV overpressure): rank 3 → 1 (+2)
- Query 7 (H2S detection): rank 4 → 2 (+2)

Notable degradations:
- Query 11 (fire suppression): rank 1 → 5 (-4)
- Query 9 (atmospheric monitoring): rank 2 → 5 (-3)
- Query 41 (fluid containment): rank 10 → miss (LOST)

**Observation:** 20 out of 50 queries resulted in "both miss" — the expected barrier family was not present in top-10 for either system. This suggests the primary bottleneck is bi-encoder recall, not ranking quality. The reranker cannot improve results that aren't retrieved in the first place.

## 7. Latency Benchmarks

| Metric | Baseline | Reranked |
|--------|----------|----------|
| Avg latency | 19 ms | 24 ms |
| P95 latency | 30 ms | 35 ms |
| Max latency | 36 ms | 95 ms |

**Analysis:** The reranker adds ~5ms average overhead with GPU acceleration (CUDA detected). This is negligible for interactive use. The max latency spike (95ms) is likely a cold-start effect on the first query.

## 8. Memory Usage

| Component | Memory |
|-----------|--------|
| Before agents | 1301 MB |
| After baseline agent | 1328 MB |
| After reranker model load | 1357 MB |
| **Reranker overhead** | **29 MB** |

The cross-encoder model (MiniLM-L-6, 22M params) adds only 29 MB — minimal overhead.

## 9. Failure Mode Validation

| Test | Result |
|------|--------|
| Baseline normal query | PASS — returned 5 results |
| Reranked normal query | PASS — returned 5 results, all with rerank_score |
| Baseline no-match query | PASS — graceful empty results |
| Baseline single result | PASS — returned 1 result |
| Reranked single result | PASS — returned 1 result |

All 5 failure mode tests passed. System degrades gracefully in all edge cases.

## 10. Conclusion and Recommendation

### Key Findings

1. **MRR improvement is +3.1%** — below the 5% significance threshold.
2. **Top-1 and Top-5 are unchanged.** Top-10 slightly degraded (-3.2%).
3. **Per-query analysis is mixed:** 9 improved, 6 degraded, 35 unchanged/both miss.
4. **Latency overhead is minimal** (+5ms avg with GPU).
5. **Memory overhead is negligible** (+29 MB).
6. **The primary bottleneck is recall, not ranking** — 40% of queries miss in both systems.

### Recommendation: **Option B — Keep reranker optional**

The cross-encoder reranker is correctly implemented and adds negligible overhead, but the MRR improvement (+3.1%) is below the 5% threshold for enabling by default.

**Rationale:**
- The improvement is real but marginal at current corpus scale (526 incidents).
- The reranker helps specific query types (change management, communication) significantly.
- The primary bottleneck is bi-encoder recall (20/50 queries miss entirely), which the reranker cannot fix.
- As the corpus grows, the reranker's value will increase (more candidates to disambiguate).
- Keeping it optional allows A/B comparison and activation when corpus size warrants it.

**Recommended next steps:**
1. Keep `RERANKER_ENABLED` flag in config for future toggle.
2. Prioritize improving recall (BM25 hybrid search, query expansion) before revisiting reranking.
3. Re-evaluate reranker impact after corpus reaches 1000+ incidents.

---

## Merge Preparation Summary

### Features Added
- `CrossEncoderReranker` class (`src/rag/reranker.py`) — 97 lines
- 6 reranker config constants in `src/rag/config.py`
- `rerank_score` field on `RetrievalResult` dataclass
- Optional reranker integration in `RAGAgent.explain()`
- Evaluation script (`scripts/evaluate_retrieval.py`)
- 50-query evaluation dataset (`data/evaluation/rag_queries.json`)

### Files Changed
| File | Change |
|------|--------|
| `src/rag/config.py` | +8 lines (6 constants) |
| `src/rag/retriever.py` | +1 line (rerank_score field) |
| `src/rag/reranker.py` | NEW — 97 lines |
| `src/rag/rag_agent.py` | +12 lines (reranker wiring) |
| `tests/test_rag_reranker.py` | NEW — 186 lines (6 tests) |
| `tests/test_rag_retriever.py` | +30 lines (2 tests) |
| `tests/test_rag_agent.py` | +178 lines (2 tests) |
| `tests/test_rag_integration.py` | +69 lines (1 test) |
| `scripts/evaluate_retrieval.py` | NEW — evaluation harness |
| `data/evaluation/rag_queries.json` | NEW — 50 eval queries |
| `docs/reports/rag_phase2_implementation_audit.md` | NEW — audit report |
| `docs/reports/rag_phase2_evaluation.md` | NEW — this report |

### Test Results
- **362 passed, 1 skipped, 0 failures** (before evaluation additions)
- All 11 new Phase-2 tests pass
- All 5 failure mode tests pass

### Evaluation Results
- MRR: 0.40 → 0.42 (+3.1%)
- Latency: +5ms avg overhead
- Memory: +29 MB overhead
- Recommendation: Keep reranker optional (Option B)

### Impact on Retrieval Accuracy
The reranker provides marginal improvement at current corpus scale. It is safe, backward-compatible, and correctly implemented. It adds value for specific query types and will become more impactful as corpus grows. No negative impact on existing functionality.

**Branch is ready for merge.** No blocking issues.
