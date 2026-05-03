#!/usr/bin/env python3
"""RAG Phase-2 evaluation: compare baseline (RRF) vs reranked retrieval.

Runs 50 evaluation queries against both systems and reports:
  - Top-1/5/10 accuracy, MRR
  - Per-query ranking deltas
  - Latency benchmarks (avg, p95, max)
  - Memory footprint
  - Failure mode validation

Usage:
    python scripts/evaluate_retrieval.py --json-dir <path> [--output-dir <path>]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rag.config import TOP_K_RERANK, FINAL_TOP_K
from src.rag.corpus_builder import build_barrier_documents, build_incident_documents
from src.rag.rag_agent import RAGAgent, ExplanationResult
from src.rag.retriever import RetrievalResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EVAL_QUERIES_PATH = Path("data/evaluation/rag_queries.json")


def load_queries(path: Path = EVAL_QUERIES_PATH) -> list[dict[str, str]]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _find_rank(results: list[RetrievalResult], expected: str) -> int | None:
    """Return 1-indexed rank of the first result matching expected_barrier family."""
    for i, r in enumerate(results, start=1):
        if r.barrier_family == expected:
            return i
    return None


def _top_k_hit(rank: int | None, k: int) -> bool:
    return rank is not None and rank <= k


def _reciprocal_rank(rank: int | None) -> float:
    return 1.0 / rank if rank is not None else 0.0


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(
    ranks: list[int | None],
) -> dict[str, float]:
    n = len(ranks)
    top1 = sum(1 for r in ranks if _top_k_hit(r, 1)) / n
    top5 = sum(1 for r in ranks if _top_k_hit(r, 5)) / n
    top10 = sum(1 for r in ranks if _top_k_hit(r, 10)) / n
    mrr = sum(_reciprocal_rank(r) for r in ranks) / n
    return {"top1": top1, "top5": top5, "top10": top10, "mrr": mrr}


# ---------------------------------------------------------------------------
# Build RAG infrastructure
# ---------------------------------------------------------------------------

def build_rag_dir(json_dir: Path, rag_dir: Path) -> tuple[int, int]:
    """Build corpus CSVs and embeddings for evaluation."""
    datasets_dir = rag_dir / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)

    b_count = build_barrier_documents(json_dir, datasets_dir / "barrier_documents.csv")
    i_count = build_incident_documents(json_dir, datasets_dir / "incident_documents.csv")
    return b_count, i_count


def build_embeddings(
    rag_dir: Path, b_count: int, i_count: int, provider: Any
) -> None:
    """Generate embeddings using the embedding provider."""
    import csv

    emb_dir = rag_dir / "embeddings"
    emb_dir.mkdir(parents=True, exist_ok=True)

    barrier_csv = rag_dir / "datasets" / "barrier_documents.csv"
    incident_csv = rag_dir / "datasets" / "incident_documents.csv"

    # Barrier embeddings
    barrier_texts: list[str] = []
    with open(barrier_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            barrier_texts.append(row["barrier_role_match_text"])

    print(f"Embedding {len(barrier_texts)} barriers...")
    barrier_embs = []
    for i, text in enumerate(barrier_texts):
        barrier_embs.append(provider.embed(text))
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(barrier_texts)}")
    barrier_emb = np.array(barrier_embs, dtype=np.float32)
    np.save(emb_dir / "barrier_embeddings.npy", barrier_emb)

    # Incident embeddings
    incident_texts: list[str] = []
    with open(incident_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            incident_texts.append(row["incident_embed_text"])

    print(f"Embedding {len(incident_texts)} incidents...")
    incident_embs = []
    for text in incident_texts:
        incident_embs.append(provider.embed(text))
    incident_emb = np.array(incident_embs, dtype=np.float32)
    np.save(emb_dir / "incident_embeddings.npy", incident_emb)

    print(f"Embeddings saved: barriers={barrier_emb.shape}, incidents={incident_emb.shape}")


# ---------------------------------------------------------------------------
# Evaluation runners
# ---------------------------------------------------------------------------

def run_evaluation(
    agent: RAGAgent,
    queries: list[dict[str, str]],
    top_k: int = 10,
    label: str = "System",
) -> tuple[list[int | None], list[float]]:
    """Run queries, return (ranks, latencies_ms)."""
    ranks: list[int | None] = []
    latencies: list[float] = []

    for q in queries:
        t0 = time.perf_counter()
        result = agent.explain(
            barrier_query=q["barrier_query"],
            incident_query=q["incident_query"],
            top_k=top_k,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

        rank = _find_rank(result.results, q["expected_barrier"])
        ranks.append(rank)

    return ranks, latencies


def run_failure_tests(
    agent_baseline: RAGAgent,
    agent_reranked: RAGAgent | None,
) -> list[dict[str, Any]]:
    """Run failure mode tests, return list of test results."""
    results: list[dict[str, Any]] = []

    # Test 1: baseline with normal query
    try:
        r = agent_baseline.explain(
            barrier_query="pressure safety valve",
            incident_query="overpressure",
            top_k=5,
        )
        results.append({
            "test": "baseline_normal_query",
            "passed": isinstance(r, ExplanationResult),
            "detail": f"returned {len(r.results)} results",
        })
    except Exception as e:
        results.append({"test": "baseline_normal_query", "passed": False, "detail": str(e)})

    # Test 2: reranked with normal query
    if agent_reranked:
        try:
            r = agent_reranked.explain(
                barrier_query="pressure safety valve",
                incident_query="overpressure",
                top_k=5,
            )
            results.append({
                "test": "reranked_normal_query",
                "passed": isinstance(r, ExplanationResult) and all(
                    x.rerank_score is not None for x in r.results
                ),
                "detail": f"returned {len(r.results)} results, all with rerank_score",
            })
        except Exception as e:
            results.append({"test": "reranked_normal_query", "passed": False, "detail": str(e)})

    # Test 3: empty-ish query (unlikely to match much)
    try:
        r = agent_baseline.explain(
            barrier_query="xyznonexistent",
            incident_query="xyznonexistent",
            top_k=5,
        )
        results.append({
            "test": "baseline_no_match_query",
            "passed": isinstance(r, ExplanationResult),
            "detail": f"returned {len(r.results)} results (graceful)",
        })
    except Exception as e:
        results.append({"test": "baseline_no_match_query", "passed": False, "detail": str(e)})

    # Test 4: single result request
    try:
        r = agent_baseline.explain(
            barrier_query="training",
            incident_query="incident",
            top_k=1,
        )
        results.append({
            "test": "baseline_single_result",
            "passed": isinstance(r, ExplanationResult) and len(r.results) <= 1,
            "detail": f"returned {len(r.results)} result(s)",
        })
    except Exception as e:
        results.append({"test": "baseline_single_result", "passed": False, "detail": str(e)})

    # Test 5: reranked single result
    if agent_reranked:
        try:
            r = agent_reranked.explain(
                barrier_query="training",
                incident_query="incident",
                top_k=1,
            )
            results.append({
                "test": "reranked_single_result",
                "passed": isinstance(r, ExplanationResult) and len(r.results) <= 1,
                "detail": f"returned {len(r.results)} result(s)",
            })
        except Exception as e:
            results.append({"test": "reranked_single_result", "passed": False, "detail": str(e)})

    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def format_metrics(metrics: dict[str, float], label: str) -> str:
    return (
        f"{label}:\n"
        f"  top1:  {metrics['top1']:.2f}\n"
        f"  top5:  {metrics['top5']:.2f}\n"
        f"  top10: {metrics['top10']:.2f}\n"
        f"  mrr:   {metrics['mrr']:.2f}\n"
    )


def format_latency(latencies: list[float], label: str) -> str:
    arr = np.array(latencies)
    return (
        f"{label} latency:\n"
        f"  avg: {arr.mean():.0f} ms\n"
        f"  p95: {np.percentile(arr, 95):.0f} ms\n"
        f"  max: {arr.max():.0f} ms\n"
    )


def ranking_delta_analysis(
    queries: list[dict[str, str]],
    baseline_ranks: list[int | None],
    reranked_ranks: list[int | None],
) -> str:
    lines: list[str] = []
    improvements = 0
    degradations = 0
    deltas: list[int] = []

    for i, q in enumerate(queries):
        br = baseline_ranks[i]
        rr = reranked_ranks[i]

        br_str = str(br) if br is not None else "miss"
        rr_str = str(rr) if rr is not None else "miss"

        if br is not None and rr is not None:
            delta = br - rr
            deltas.append(delta)
            if delta > 0:
                improvements += 1
                sign = f"+{delta}"
            elif delta < 0:
                degradations += 1
                sign = str(delta)
            else:
                sign = "0"
        elif br is None and rr is not None:
            improvements += 1
            sign = "NEW HIT"
        elif br is not None and rr is None:
            degradations += 1
            sign = "LOST"
        else:
            sign = "both miss"

        lines.append(
            f"  Query {i+1:2d} | expected: {q['expected_barrier']:50s} | "
            f"baseline: {br_str:>4s} | reranked: {rr_str:>4s} | delta: {sign}"
        )

    avg_delta = np.mean(deltas) if deltas else 0.0

    summary = (
        f"\nRanking Delta Summary:\n"
        f"  Average rank improvement: {avg_delta:+.2f}\n"
        f"  Improved queries: {improvements}\n"
        f"  Degraded queries: {degradations}\n"
        f"  Unchanged/both miss: {len(queries) - improvements - degradations}\n"
    )

    return "\n".join(lines) + "\n" + summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="RAG Phase-2 retrieval evaluation")
    parser.add_argument(
        "--json-dir", type=Path, required=True,
        help="Directory containing V2.3 incident JSON files",
    )
    parser.add_argument(
        "--rag-dir", type=Path, default=Path("data/evaluation/rag_workspace"),
        help="Working directory for RAG artifacts",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/evaluation/results"),
        help="Output directory for evaluation results",
    )
    parser.add_argument(
        "--skip-embeddings", action="store_true",
        help="Skip embedding generation (use existing)",
    )
    parser.add_argument(
        "--skip-reranker", action="store_true",
        help="Skip reranker evaluation (baseline only)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load queries
    queries = load_queries()
    print(f"Loaded {len(queries)} evaluation queries")

    # Build corpus
    print("\n=== Building corpus ===")
    b_count, i_count = build_rag_dir(args.json_dir, args.rag_dir)
    print(f"Barriers: {b_count}, Incidents: {i_count}")

    if b_count == 0 or i_count == 0:
        print("ERROR: No barriers or incidents found. Check --json-dir.")
        sys.exit(1)

    # Build embeddings
    if not args.skip_embeddings:
        print("\n=== Building embeddings ===")
        from src.rag.embeddings.sentence_transformers_provider import (
            SentenceTransformerProvider,
        )
        provider = SentenceTransformerProvider()
        build_embeddings(args.rag_dir, b_count, i_count, provider)
    else:
        from src.rag.embeddings.sentence_transformers_provider import (
            SentenceTransformerProvider,
        )
        provider = SentenceTransformerProvider()
        print("Skipping embedding generation (using existing)")

    # Memory baseline before reranker
    import psutil
    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss / 1024 / 1024

    # Build baseline agent (no reranker)
    print("\n=== Building baseline agent ===")
    agent_baseline = RAGAgent.from_directory(
        args.rag_dir, embedding_provider=provider
    )
    mem_after_baseline = process.memory_info().rss / 1024 / 1024

    # Build reranked agent
    agent_reranked = None
    mem_after_reranker = mem_after_baseline
    if not args.skip_reranker:
        print("\n=== Building reranked agent ===")
        from src.rag.reranker import CrossEncoderReranker
        reranker = CrossEncoderReranker()
        mem_after_reranker = process.memory_info().rss / 1024 / 1024
        agent_reranked = RAGAgent.from_directory(
            args.rag_dir, embedding_provider=provider, reranker=reranker
        )

    # Run baseline evaluation
    print("\n=== Running baseline evaluation ===")
    baseline_ranks, baseline_latencies = run_evaluation(
        agent_baseline, queries, top_k=10, label="Baseline"
    )
    baseline_metrics = compute_metrics(baseline_ranks)

    # Run reranked evaluation
    reranked_ranks: list[int | None] = []
    reranked_latencies: list[float] = []
    reranked_metrics: dict[str, float] = {}
    if agent_reranked:
        print("\n=== Running reranked evaluation ===")
        reranked_ranks, reranked_latencies = run_evaluation(
            agent_reranked, queries, top_k=10, label="Reranked"
        )
        reranked_metrics = compute_metrics(reranked_ranks)

    # Run failure tests
    print("\n=== Running failure tests ===")
    failure_results = run_failure_tests(agent_baseline, agent_reranked)

    # Print results
    print("\n" + "=" * 60)
    print("RETRIEVAL EVALUATION RESULTS")
    print("=" * 60)

    print(f"\nCorpus: {b_count} barriers, {i_count} incidents")
    print(f"Queries: {len(queries)}")

    print(f"\n{format_metrics(baseline_metrics, 'Baseline')}")
    if reranked_metrics:
        print(format_metrics(reranked_metrics, "Reranked"))

        # Delta
        print("Improvement:")
        for k in ["top1", "top5", "top10", "mrr"]:
            delta = reranked_metrics[k] - baseline_metrics[k]
            pct = (delta / baseline_metrics[k] * 100) if baseline_metrics[k] > 0 else 0
            print(f"  {k}: {delta:+.2f} ({pct:+.1f}%)")

    print(f"\n{format_latency(baseline_latencies, 'Baseline')}")
    if reranked_latencies:
        print(format_latency(reranked_latencies, "Reranked"))

    print(f"\nMemory footprint:")
    print(f"  Before agents: {mem_before:.0f} MB")
    print(f"  After baseline: {mem_after_baseline:.0f} MB")
    if not args.skip_reranker:
        print(f"  After reranker load: {mem_after_reranker:.0f} MB")
        print(f"  Reranker overhead: {mem_after_reranker - mem_after_baseline:.0f} MB")

    if reranked_ranks:
        print("\n--- Per-Query Ranking Deltas ---")
        delta_text = ranking_delta_analysis(queries, baseline_ranks, reranked_ranks)
        print(delta_text)

    print("\n--- Failure Tests ---")
    all_passed = True
    for ft in failure_results:
        status = "PASS" if ft["passed"] else "FAIL"
        if not ft["passed"]:
            all_passed = False
        print(f"  [{status}] {ft['test']}: {ft['detail']}")

    # Save results JSON
    output = {
        "corpus": {"barriers": b_count, "incidents": i_count},
        "queries": len(queries),
        "baseline": {
            "metrics": baseline_metrics,
            "latency_avg_ms": float(np.mean(baseline_latencies)),
            "latency_p95_ms": float(np.percentile(baseline_latencies, 95)),
            "latency_max_ms": float(np.max(baseline_latencies)),
        },
        "memory": {
            "before_agents_mb": mem_before,
            "after_baseline_mb": mem_after_baseline,
            "after_reranker_mb": mem_after_reranker,
            "reranker_overhead_mb": mem_after_reranker - mem_after_baseline,
        },
        "failure_tests": failure_results,
        "failure_tests_all_passed": all_passed,
    }
    if reranked_metrics:
        output["reranked"] = {
            "metrics": reranked_metrics,
            "latency_avg_ms": float(np.mean(reranked_latencies)),
            "latency_p95_ms": float(np.percentile(reranked_latencies, 95)),
            "latency_max_ms": float(np.max(reranked_latencies)),
        }
        output["improvement"] = {
            k: reranked_metrics[k] - baseline_metrics[k]
            for k in ["top1", "top5", "top10", "mrr"]
        }

    results_path = args.output_dir / "evaluation_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {results_path}")


if __name__ == "__main__":
    main()
