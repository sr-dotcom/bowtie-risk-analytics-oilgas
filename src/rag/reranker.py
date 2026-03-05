"""Cross-encoder reranker for post-RRF candidate re-scoring."""
from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np
from sentence_transformers import CrossEncoder

from src.rag.config import FINAL_TOP_K, RERANKER_BATCH_SIZE, RERANKER_MAX_LENGTH, RERANKER_MODEL
from src.rag.retriever import RetrievalResult

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Re-score retrieval candidates using a cross-encoder model."""

    def __init__(
        self,
        model_name: str = RERANKER_MODEL,
        max_length: int = RERANKER_MAX_LENGTH,
        batch_size: int = RERANKER_BATCH_SIZE,
    ) -> None:
        self._model = CrossEncoder(model_name, max_length=max_length)
        self._batch_size = batch_size

    def _build_passage(
        self, candidate: RetrievalResult, barrier_metadata: list[dict[str, Any]]
    ) -> str:
        """Build labeled passage from barrier metadata."""
        meta = self._find_meta(candidate, barrier_metadata)
        barrier_text = meta.get("barrier_role_match_text", "")
        lines = barrier_text.split("\n")
        name = lines[0].replace("Barrier: ", "") if len(lines) > 0 else ""
        role = lines[1].replace("Role: ", "") if len(lines) > 1 else ""
        summary = meta.get("incident_summary", "")
        return f"Barrier: {name} — {role}\nIncident: {summary}"

    def _find_meta(
        self, candidate: RetrievalResult, barrier_metadata: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Find barrier metadata matching a candidate."""
        for meta in barrier_metadata:
            if (
                meta["incident_id"] == candidate.incident_id
                and meta.get("barrier_family") == candidate.barrier_family
            ):
                return meta
        return {}

    def rerank(
        self,
        barrier_query: str,
        incident_query: str,
        candidates: list[RetrievalResult],
        barrier_metadata: list[dict[str, Any]],
        top_k: int = FINAL_TOP_K,
    ) -> list[RetrievalResult]:
        """Re-score candidates with cross-encoder and return top-K.

        Args:
            barrier_query: Barrier search query text.
            incident_query: Incident search query text.
            candidates: RRF-ranked retrieval results to re-score.
            barrier_metadata: Full barrier metadata list for passage building.
            top_k: Number of results to return after reranking.

        Returns:
            Reranked list sorted by rerank_score desc, rrf_score desc tiebreak.
        """
        if not candidates:
            return []

        query = f"{barrier_query} {incident_query}"
        pairs: list[tuple[str, str]] = []
        for c in candidates:
            passage = self._build_passage(c, barrier_metadata)
            pairs.append((query, passage))

        t0 = time.perf_counter()
        scores = self._model.predict(pairs, batch_size=self._batch_size)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        logger.debug(
            "reranker_latency_ms=%.1f num_candidates=%d",
            elapsed_ms,
            len(candidates),
        )

        for c, score in zip(candidates, scores):
            c.rerank_score = float(score)

        candidates.sort(key=lambda r: (-r.rerank_score, -r.rrf_score))
        return candidates[:top_k]
