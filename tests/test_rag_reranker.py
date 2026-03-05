# tests/test_rag_reranker.py
import logging
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from src.rag.reranker import CrossEncoderReranker
from src.rag.retriever import RetrievalResult


def _make_candidate(incident_id: str, barrier_family: str, rrf: float) -> RetrievalResult:
    return RetrievalResult(
        incident_id=incident_id,
        control_id=f"C-{incident_id}",
        barrier_family=barrier_family,
        barrier_failed_human=False,
        rrf_score=rrf,
        barrier_rank=1,
        incident_rank=1,
        barrier_sim_score=0.9,
        incident_sim_score=0.8,
    )


def _make_barrier_meta(incident_id: str, name: str, role: str, summary: str) -> dict:
    return {
        "incident_id": incident_id,
        "barrier_role_match_text": f"Barrier: {name}\nRole: {role}\nLOD Basis: N/A",
        "barrier_family": "training",
        "incident_summary": summary,
    }


class TestCrossEncoderReranker:
    @patch("src.rag.reranker.CrossEncoder")
    def test_rerank_scores_and_sorts(self, mock_ce_cls):
        mock_model = MagicMock()
        # Return scores: candidate 0 gets 0.3, candidate 1 gets 0.9, candidate 2 gets 0.6
        mock_model.predict.return_value = np.array([0.3, 0.9, 0.6])
        mock_ce_cls.return_value = mock_model

        reranker = CrossEncoderReranker(model_name="test-model")

        candidates = [
            _make_candidate("INC-0", "training", 0.03),
            _make_candidate("INC-1", "monitoring", 0.02),
            _make_candidate("INC-2", "training", 0.01),
        ]
        metadata = [
            _make_barrier_meta("INC-0", "Valve", "Prevent", "Valve failure"),
            _make_barrier_meta("INC-1", "Training", "Train", "Training gap"),
            _make_barrier_meta("INC-2", "Alarm", "Alert", "Alarm failure"),
        ]

        results = reranker.rerank(
            barrier_query="safety training",
            incident_query="valve failure",
            candidates=candidates,
            barrier_metadata=metadata,
            top_k=3,
        )

        assert len(results) == 3
        assert results[0].rerank_score == pytest.approx(0.9)
        assert results[1].rerank_score == pytest.approx(0.6)
        assert results[2].rerank_score == pytest.approx(0.3)
        # Verify INC-1 is first (highest rerank score)
        assert results[0].incident_id == "INC-1"

    @patch("src.rag.reranker.CrossEncoder")
    def test_rerank_top_k_truncates(self, mock_ce_cls):
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
        mock_ce_cls.return_value = mock_model

        reranker = CrossEncoderReranker(model_name="test-model")

        candidates = [_make_candidate(f"INC-{i}", "training", 0.03 - i * 0.001) for i in range(5)]
        metadata = [_make_barrier_meta(f"INC-{i}", f"Control {i}", "Role", f"Summary {i}") for i in range(5)]

        results = reranker.rerank(
            barrier_query="query",
            incident_query="query",
            candidates=candidates,
            barrier_metadata=metadata,
            top_k=3,
        )

        assert len(results) == 3

    @patch("src.rag.reranker.CrossEncoder")
    def test_rerank_rrf_tiebreak(self, mock_ce_cls):
        mock_model = MagicMock()
        # Same rerank scores
        mock_model.predict.return_value = np.array([0.5, 0.5])
        mock_ce_cls.return_value = mock_model

        reranker = CrossEncoderReranker(model_name="test-model")

        candidates = [
            _make_candidate("INC-0", "training", 0.01),  # lower RRF
            _make_candidate("INC-1", "training", 0.03),  # higher RRF
        ]
        metadata = [
            _make_barrier_meta("INC-0", "A", "Role", "Summary"),
            _make_barrier_meta("INC-1", "B", "Role", "Summary"),
        ]

        results = reranker.rerank(
            barrier_query="query",
            incident_query="query",
            candidates=candidates,
            barrier_metadata=metadata,
            top_k=2,
        )

        # INC-1 should be first (higher RRF as tiebreak)
        assert results[0].incident_id == "INC-1"

    @patch("src.rag.reranker.CrossEncoder")
    def test_rerank_empty_candidates(self, mock_ce_cls):
        mock_model = MagicMock()
        mock_ce_cls.return_value = mock_model

        reranker = CrossEncoderReranker(model_name="test-model")

        results = reranker.rerank(
            barrier_query="query",
            incident_query="query",
            candidates=[],
            barrier_metadata=[],
            top_k=5,
        )

        assert results == []
        mock_model.predict.assert_not_called()

    @patch("src.rag.reranker.CrossEncoder")
    def test_rerank_passage_composition(self, mock_ce_cls):
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.9])
        mock_ce_cls.return_value = mock_model

        reranker = CrossEncoderReranker(model_name="test-model")

        candidates = [_make_candidate("INC-0", "training", 0.03)]
        metadata = [_make_barrier_meta("INC-0", "PSV", "Prevent overpressure", "Valve ruptured")]

        reranker.rerank(
            barrier_query="safety valve",
            incident_query="pressure release",
            candidates=candidates,
            barrier_metadata=metadata,
            top_k=1,
        )

        # Verify the pairs passed to predict
        call_args = mock_model.predict.call_args[0][0]
        query, passage = call_args[0]
        assert query == "safety valve pressure release"
        assert "Barrier: PSV" in passage
        assert "Prevent overpressure" in passage
        assert "Incident: Valve ruptured" in passage

    @patch("src.rag.reranker.CrossEncoder")
    def test_rerank_logs_latency(self, mock_ce_cls, caplog):
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.5])
        mock_ce_cls.return_value = mock_model

        reranker = CrossEncoderReranker(model_name="test-model")

        candidates = [_make_candidate("INC-0", "training", 0.03)]
        metadata = [_make_barrier_meta("INC-0", "A", "Role", "Summary")]

        with caplog.at_level(logging.DEBUG, logger="src.rag.reranker"):
            reranker.rerank(
                barrier_query="query",
                incident_query="query",
                candidates=candidates,
                barrier_metadata=metadata,
                top_k=1,
            )

        assert any("reranker_latency_ms" in r.message for r in caplog.records)
        assert any("num_candidates" in r.message for r in caplog.records)
