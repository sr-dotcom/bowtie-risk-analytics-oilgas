"""4-stage hybrid retrieval pipeline: filter -> search -> intersect -> RRF."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.rag.embeddings.base import EmbeddingProvider
from src.rag.vector_index import VectorIndex


@dataclass
class RetrievalResult:
    """Single result from hybrid retrieval."""

    incident_id: str
    control_id: str
    barrier_family: str
    barrier_failed_human: bool
    rrf_score: float
    barrier_rank: int
    incident_rank: int
    barrier_sim_score: float
    incident_sim_score: float


def rrf_score(barrier_rank: int, incident_rank: int, k: int = 60) -> float:
    """Reciprocal Rank Fusion score. Ranks are 1-indexed."""
    return 1.0 / (k + barrier_rank) + 1.0 / (k + incident_rank)


class HybridRetriever:
    """4-stage hybrid retrieval pipeline."""

    def __init__(
        self,
        barrier_embeddings: np.ndarray,
        incident_embeddings: np.ndarray,
        barrier_incident_ids: list[str],
        incident_ids: list[str],
        barrier_families: list[str],
        barrier_failed_humans: list[bool],
        barrier_pif_flags: list[dict[str, bool]],
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._barrier_emb = barrier_embeddings
        self._incident_emb = incident_embeddings
        self._barrier_incident_ids = barrier_incident_ids
        self._incident_ids = incident_ids
        self._barrier_families = barrier_families
        self._barrier_failed_humans = barrier_failed_humans
        self._barrier_pif_flags = barrier_pif_flags
        self._provider = embedding_provider

        self._barrier_index = VectorIndex.build(barrier_embeddings)
        self._incident_index = VectorIndex.build(incident_embeddings)

    def _build_barrier_mask(
        self,
        barrier_family: str | None,
        barrier_failed_human: bool | None,
        pif_filters: dict[str, bool] | None,
    ) -> np.ndarray | None:
        """Build a boolean mask for barrier pre-filtering."""
        n = len(self._barrier_incident_ids)
        mask = np.ones(n, dtype=bool)
        active = False

        if barrier_family is not None:
            active = True
            for i in range(n):
                if self._barrier_families[i] != barrier_family:
                    mask[i] = False

        if barrier_failed_human is not None:
            active = True
            for i in range(n):
                if self._barrier_failed_humans[i] != barrier_failed_human:
                    mask[i] = False

        if pif_filters:
            active = True
            for i in range(n):
                flags = self._barrier_pif_flags[i]
                for pif_name, required in pif_filters.items():
                    if flags.get(pif_name, False) != required:
                        mask[i] = False
                        break

        return mask if active else None

    def retrieve(
        self,
        barrier_query: str,
        incident_query: str,
        *,
        barrier_family: str | None = None,
        barrier_failed_human: bool | None = None,
        pif_filters: dict[str, bool] | None = None,
        top_k_barriers: int = 50,
        top_k_incidents: int = 20,
        top_k: int = 10,
    ) -> list[RetrievalResult]:
        """Run the 4-stage hybrid retrieval pipeline.

        Pipeline 1: Barrier similarity search (with metadata filter)
        Pipeline 2: Incident similarity search
        Pipeline 3: Intersection filter
        Pipeline 4: RRF Top-K ranking
        """
        # Embed queries
        barrier_q = self._provider.embed(barrier_query)
        incident_q = self._provider.embed(incident_query)

        # Pipeline 1: Barrier search with optional mask
        mask = self._build_barrier_mask(
            barrier_family, barrier_failed_human, pif_filters
        )
        b_scores, b_indices = self._barrier_index.search(
            barrier_q, top_k=top_k_barriers, mask=mask
        )
        if len(b_indices) == 0:
            return []

        # Pipeline 2: Incident search (no filter)
        i_scores, i_indices = self._incident_index.search(
            incident_q, top_k=top_k_incidents
        )

        # Pipeline 3: Intersection
        retrieved_incident_ids = {
            self._incident_ids[idx] for idx in i_indices
        }
        # Build incident rank lookup (1-indexed)
        incident_rank_map: dict[str, tuple[int, float]] = {}
        for rank, (idx, score) in enumerate(zip(i_indices, i_scores), start=1):
            iid = self._incident_ids[idx]
            if iid not in incident_rank_map:
                incident_rank_map[iid] = (rank, float(score))

        # Filter barriers whose parent incident was retrieved
        candidates: list[tuple[int, int, float, str]] = []
        for barrier_rank, (b_idx, b_score) in enumerate(
            zip(b_indices, b_scores), start=1
        ):
            parent_iid = self._barrier_incident_ids[b_idx]
            if parent_iid in retrieved_incident_ids:
                candidates.append(
                    (int(b_idx), barrier_rank, float(b_score), parent_iid)
                )

        if not candidates:
            return []

        # Pipeline 4: RRF ranking
        results: list[RetrievalResult] = []
        for b_idx, barrier_rank, b_score, parent_iid in candidates:
            i_rank, i_score = incident_rank_map[parent_iid]
            results.append(
                RetrievalResult(
                    incident_id=parent_iid,
                    control_id="",  # populated by caller from metadata
                    barrier_family=self._barrier_families[b_idx],
                    barrier_failed_human=self._barrier_failed_humans[b_idx],
                    rrf_score=rrf_score(barrier_rank, i_rank),
                    barrier_rank=barrier_rank,
                    incident_rank=i_rank,
                    barrier_sim_score=b_score,
                    incident_sim_score=i_score,
                )
            )

        results.sort(key=lambda r: r.rrf_score, reverse=True)
        return results[:top_k]
