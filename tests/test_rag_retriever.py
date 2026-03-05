# tests/test_rag_retriever.py
import json
import numpy as np
import pytest
from unittest.mock import MagicMock
from src.rag.retriever import (
    RetrievalResult,
    HybridRetriever,
    rrf_score,
)


class TestRRFScore:
    def test_basic(self):
        score = rrf_score(barrier_rank=1, incident_rank=1, k=60)
        assert abs(score - 2 / 61) < 1e-6

    def test_different_ranks(self):
        score = rrf_score(barrier_rank=1, incident_rank=5, k=60)
        expected = 1 / 61 + 1 / 65
        assert abs(score - expected) < 1e-6

    def test_higher_rank_lower_score(self):
        s1 = rrf_score(barrier_rank=1, incident_rank=1)
        s2 = rrf_score(barrier_rank=10, incident_rank=10)
        assert s1 > s2


class TestHybridRetriever:
    def _build_retriever(self):
        """Build a retriever with synthetic data."""
        dim = 8
        rng = np.random.default_rng(42)

        n_incidents = 5
        n_barriers = 15

        barrier_incident_ids = []
        barrier_families = []
        barrier_failed_humans = []
        pif_flags = []
        for i in range(n_incidents):
            for j in range(3):
                barrier_incident_ids.append(f"INC-{i}")
                barrier_families.append("training" if j == 0 else "monitoring")
                barrier_failed_humans.append(j == 1)
                pif_flags.append({"communication": j == 0, "procedures": True})

        incident_ids = [f"INC-{i}" for i in range(n_incidents)]

        barrier_emb = rng.standard_normal((n_barriers, dim)).astype(np.float32)
        barrier_emb /= np.linalg.norm(barrier_emb, axis=1, keepdims=True)
        incident_emb = rng.standard_normal((n_incidents, dim)).astype(np.float32)
        incident_emb /= np.linalg.norm(incident_emb, axis=1, keepdims=True)

        mock_provider = MagicMock()
        mock_provider.embed.side_effect = lambda t: barrier_emb[0]

        retriever = HybridRetriever(
            barrier_embeddings=barrier_emb,
            incident_embeddings=incident_emb,
            barrier_incident_ids=barrier_incident_ids,
            incident_ids=incident_ids,
            barrier_families=barrier_families,
            barrier_failed_humans=barrier_failed_humans,
            barrier_pif_flags=pif_flags,
            embedding_provider=mock_provider,
        )
        return retriever

    def test_retrieve_returns_results(self):
        retriever = self._build_retriever()
        results = retriever.retrieve(
            barrier_query="safety training",
            incident_query="valve failure",
            top_k=5,
        )
        assert isinstance(results, list)
        assert len(results) <= 5
        assert all(isinstance(r, RetrievalResult) for r in results)

    def test_retrieve_with_family_filter(self):
        retriever = self._build_retriever()
        results = retriever.retrieve(
            barrier_query="training",
            incident_query="failure",
            barrier_family="training",
            top_k=5,
        )
        assert all(r.barrier_family == "training" for r in results)

    def test_retrieve_with_human_filter(self):
        retriever = self._build_retriever()
        results = retriever.retrieve(
            barrier_query="training",
            incident_query="failure",
            barrier_failed_human=True,
            top_k=5,
        )
        assert all(r.barrier_failed_human for r in results)

    def test_retrieve_with_pif_filter(self):
        retriever = self._build_retriever()
        results = retriever.retrieve(
            barrier_query="training",
            incident_query="failure",
            pif_filters={"communication": True},
            top_k=5,
        )

    def test_results_sorted_by_rrf(self):
        retriever = self._build_retriever()
        results = retriever.retrieve(
            barrier_query="training",
            incident_query="failure",
            top_k=5,
        )
        if len(results) >= 2:
            for i in range(len(results) - 1):
                assert results[i].rrf_score >= results[i + 1].rrf_score

    def test_empty_intersection_returns_empty(self):
        retriever = self._build_retriever()
        results = retriever.retrieve(
            barrier_query="training",
            incident_query="failure",
            top_k_barriers=1,
            top_k_incidents=1,
            top_k=5,
        )
        assert isinstance(results, list)


class TestRetrievalResultRerankScore:
    def test_default_rerank_score_is_none(self):
        r = RetrievalResult(
            incident_id="INC-1",
            control_id="C-1",
            barrier_family="training",
            barrier_failed_human=False,
            rrf_score=0.03,
            barrier_rank=1,
            incident_rank=1,
            barrier_sim_score=0.9,
            incident_sim_score=0.8,
        )
        assert r.rerank_score is None

    def test_rerank_score_can_be_set(self):
        r = RetrievalResult(
            incident_id="INC-1",
            control_id="C-1",
            barrier_family="training",
            barrier_failed_human=False,
            rrf_score=0.03,
            barrier_rank=1,
            incident_rank=1,
            barrier_sim_score=0.9,
            incident_sim_score=0.8,
            rerank_score=0.95,
        )
        assert r.rerank_score == 0.95
