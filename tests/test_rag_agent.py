# tests/test_rag_agent.py
import json
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from src.rag.rag_agent import RAGAgent, ExplanationResult


class TestRAGAgent:
    def _build_agent(self, tmp_path):
        """Build a RAGAgent from synthetic data."""
        import csv

        # Barrier documents
        barrier_csv = tmp_path / "datasets" / "barrier_documents.csv"
        barrier_csv.parent.mkdir(parents=True)

        from src.rag.corpus_builder import BARRIER_DOC_COLUMNS
        barriers = []
        for i in range(6):
            inc_id = f"INC-{i // 2}"
            barriers.append({
                "incident_id": inc_id,
                "control_id": f"C-{i:03d}",
                "barrier_role_match_text": f"Barrier: Control {i}\nRole: Test role\nLOD Basis: Test basis",
                "barrier_family": "training" if i % 2 == 0 else "monitoring",
                "barrier_type": "administrative",
                "side": "prevention",
                "line_of_defense": "1st",
                "barrier_status": "failed" if i % 2 == 0 else "active",
                "barrier_failed": str(i % 2 == 0),
                "barrier_failed_human": str(i % 3 == 0),
                "human_contribution_value": "high" if i % 2 == 0 else "",
                "pif_competence": "True",
                "pif_fatigue": "False",
                "pif_communication": str(i % 2 == 0),
                "pif_situational_awareness": "False",
                "pif_procedures": "True",
                "pif_workload": "False",
                "pif_time_pressure": "False",
                "pif_tools_equipment": "False",
                "pif_safety_culture": "False",
                "pif_management_of_change": "False",
                "pif_supervision": "False",
                "pif_training": "True",
                "supporting_text": json.dumps(["Evidence text"]),
                "confidence": "high",
                "incident_summary": f"Incident {i // 2} summary.",
            })
        with open(barrier_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=BARRIER_DOC_COLUMNS)
            writer.writeheader()
            writer.writerows(barriers)

        # Incident documents
        incident_csv = tmp_path / "datasets" / "incident_documents.csv"
        from src.rag.corpus_builder import INCIDENT_DOC_COLUMNS
        incidents = []
        for i in range(3):
            incidents.append({
                "incident_id": f"INC-{i}",
                "incident_embed_text": f"Top Event: Event {i}\nSummary: Incident {i}",
                "top_event": f"Event {i}",
                "incident_type": "Equipment Failure",
                "operating_phase": "production",
                "materials": json.dumps(["oil"]),
                "region": "Gulf of Mexico",
                "operator": f"Operator {i}",
                "summary": f"Incident {i} summary.",
                "recommendations": json.dumps(["Fix it"]),
            })
        with open(incident_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=INCIDENT_DOC_COLUMNS)
            writer.writeheader()
            writer.writerows(incidents)

        # Mock embeddings (use random but deterministic)
        rng = np.random.default_rng(42)
        barrier_emb = rng.standard_normal((6, 8)).astype(np.float32)
        barrier_emb /= np.linalg.norm(barrier_emb, axis=1, keepdims=True)
        incident_emb = rng.standard_normal((3, 8)).astype(np.float32)
        incident_emb /= np.linalg.norm(incident_emb, axis=1, keepdims=True)

        (tmp_path / "embeddings").mkdir(parents=True, exist_ok=True)
        np.save(tmp_path / "embeddings" / "barrier_embeddings.npy", barrier_emb)
        np.save(tmp_path / "embeddings" / "incident_embeddings.npy", incident_emb)

        # Mock embedding provider
        mock_provider = MagicMock()
        mock_provider.embed.return_value = barrier_emb[0]
        mock_provider.dimension = 8

        agent = RAGAgent.from_directory(tmp_path, embedding_provider=mock_provider)
        return agent

    def test_explain_returns_result(self, tmp_path):
        agent = self._build_agent(tmp_path)
        result = agent.explain(
            barrier_query="safety training",
            incident_query="valve failure",
        )
        assert isinstance(result, ExplanationResult)
        assert isinstance(result.context_text, str)
        assert isinstance(result.results, list)
        assert result.metadata["top_k"] == 10

    def test_explain_with_filters(self, tmp_path):
        agent = self._build_agent(tmp_path)
        result = agent.explain(
            barrier_query="training",
            incident_query="failure",
            barrier_family="training",
            top_k=3,
        )
        assert isinstance(result, ExplanationResult)
        assert result.metadata["barrier_family"] == "training"

    def test_explain_context_text_not_empty(self, tmp_path):
        agent = self._build_agent(tmp_path)
        result = agent.explain(
            barrier_query="training",
            incident_query="failure",
        )
        assert len(result.context_text) > 0


class TestDisambiguation:
    """D-12 regression: two same-family barriers in one incident must return different metadata."""

    def _build_agent_same_family(self, tmp_path):
        """Build a RAGAgent where INC-0 has two barriers with the SAME family but different control_ids."""
        import csv
        from src.rag.corpus_builder import BARRIER_DOC_COLUMNS, INCIDENT_DOC_COLUMNS

        barrier_csv = tmp_path / "datasets" / "barrier_documents.csv"
        barrier_csv.parent.mkdir(parents=True)

        # Two barriers in INC-0 both with barrier_family="training" but control_ids C-000 and C-001
        barriers = [
            {
                "incident_id": "INC-0",
                "control_id": "C-000",
                "barrier_role_match_text": "Barrier: Control A\nRole: Role A\nLOD Basis: Basis A",
                "barrier_family": "training",
                "barrier_type": "administrative",
                "side": "prevention",
                "line_of_defense": "1st",
                "barrier_status": "failed",
                "barrier_failed": "True",
                "barrier_failed_human": "True",
                "human_contribution_value": "high",
                "pif_competence": "True",
                "pif_fatigue": "False",
                "pif_communication": "True",
                "pif_situational_awareness": "False",
                "pif_procedures": "True",
                "pif_workload": "False",
                "pif_time_pressure": "False",
                "pif_tools_equipment": "False",
                "pif_safety_culture": "False",
                "pif_management_of_change": "False",
                "pif_supervision": "False",
                "pif_training": "True",
                "supporting_text": '["Evidence A"]',
                "confidence": "high",
                "incident_summary": "Incident 0 summary.",
            },
            {
                "incident_id": "INC-0",
                "control_id": "C-001",
                "barrier_role_match_text": "Barrier: Control B\nRole: Role B\nLOD Basis: Basis B",
                "barrier_family": "training",  # SAME family as C-000
                "barrier_type": "administrative",
                "side": "prevention",
                "line_of_defense": "2nd",
                "barrier_status": "active",
                "barrier_failed": "False",
                "barrier_failed_human": "False",
                "human_contribution_value": "",
                "pif_competence": "False",
                "pif_fatigue": "False",
                "pif_communication": "False",
                "pif_situational_awareness": "False",
                "pif_procedures": "True",
                "pif_workload": "False",
                "pif_time_pressure": "False",
                "pif_tools_equipment": "False",
                "pif_safety_culture": "False",
                "pif_management_of_change": "False",
                "pif_supervision": "False",
                "pif_training": "True",
                "supporting_text": '["Evidence B"]',
                "confidence": "medium",
                "incident_summary": "Incident 0 summary.",
            },
        ]
        with open(barrier_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=BARRIER_DOC_COLUMNS)
            writer.writeheader()
            writer.writerows(barriers)

        incident_csv = tmp_path / "datasets" / "incident_documents.csv"
        incidents = [
            {
                "incident_id": "INC-0",
                "incident_embed_text": "Top Event: Event 0\nSummary: Incident 0",
                "top_event": "Event 0",
                "incident_type": "Equipment Failure",
                "operating_phase": "production",
                "materials": '["oil"]',
                "region": "Gulf of Mexico",
                "operator": "Operator 0",
                "summary": "Incident 0 summary.",
                "recommendations": '["Fix it"]',
            }
        ]
        with open(incident_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=INCIDENT_DOC_COLUMNS)
            writer.writeheader()
            writer.writerows(incidents)

        rng = np.random.default_rng(42)
        barrier_emb = rng.standard_normal((2, 8)).astype(np.float32)
        barrier_emb /= np.linalg.norm(barrier_emb, axis=1, keepdims=True)
        incident_emb = rng.standard_normal((1, 8)).astype(np.float32)
        incident_emb /= np.linalg.norm(incident_emb, axis=1, keepdims=True)

        (tmp_path / "embeddings").mkdir(parents=True, exist_ok=True)
        np.save(tmp_path / "embeddings" / "barrier_embeddings.npy", barrier_emb)
        np.save(tmp_path / "embeddings" / "incident_embeddings.npy", incident_emb)

        mock_provider = MagicMock()
        mock_provider.embed.return_value = barrier_emb[0]
        mock_provider.dimension = 8

        return RAGAgent.from_directory(tmp_path, embedding_provider=mock_provider)

    def test_find_barrier_meta_disambiguation(self, tmp_path):
        """D-12: _find_barrier_meta must return DIFFERENT metadata for two same-family barriers."""
        from src.rag.retriever import RetrievalResult

        agent = self._build_agent_same_family(tmp_path)

        result_a = RetrievalResult(
            incident_id="INC-0",
            control_id="C-000",
            barrier_family="training",
            barrier_failed_human=True,
            rrf_score=0.03,
            barrier_rank=1,
            incident_rank=1,
            barrier_sim_score=0.9,
            incident_sim_score=0.8,
        )
        result_b = RetrievalResult(
            incident_id="INC-0",
            control_id="C-001",
            barrier_family="training",  # same family
            barrier_failed_human=False,
            rrf_score=0.02,
            barrier_rank=2,
            incident_rank=1,
            barrier_sim_score=0.8,
            incident_sim_score=0.8,
        )

        meta_a = agent._find_barrier_meta(result_a)
        meta_b = agent._find_barrier_meta(result_b)

        assert meta_a["control_id"] != meta_b["control_id"], (
            "Same-family barriers in same incident must return different metadata"
        )
        assert meta_a["control_id"] == "C-000"
        assert meta_b["control_id"] == "C-001"


class TestExplanationResultFields:
    """Tests for ExplanationResult new fields (backward-compatible defaults)."""

    def test_explanation_result_backward_compat(self):
        """Old positional/keyword-only construction must still work with safe defaults."""
        result = ExplanationResult(context_text="x", results=[], metadata={})
        assert result.narrative == ""
        assert result.citations == []
        assert result.retrieval_confidence == 0.0
        assert result.model_used == ""

    def test_explanation_result_new_fields(self):
        """New fields can be populated explicitly."""
        result = ExplanationResult(
            context_text="some context",
            results=[],
            metadata={"key": "value"},
            narrative="The barrier failed due to X.",
            citations=["cite1", "cite2"],
            retrieval_confidence=0.8,
            model_used="claude-test-model",
        )
        assert result.narrative == "The barrier failed due to X."
        assert result.citations == ["cite1", "cite2"]
        assert result.retrieval_confidence == 0.8
        assert result.model_used == "claude-test-model"

    def test_explanation_result_partial_new_fields(self):
        """Partially specifying new fields uses defaults for omitted ones."""
        result = ExplanationResult(
            context_text="ctx",
            results=[],
            retrieval_confidence=0.72,
        )
        assert result.retrieval_confidence == 0.72
        assert result.narrative == ""
        assert result.citations == []
        assert result.model_used == ""


class TestRAGAgentWithReranker:
    def _build_agent_with_reranker(self, tmp_path):
        """Build a RAGAgent with a mock reranker."""
        import csv
        from src.rag.corpus_builder import BARRIER_DOC_COLUMNS, INCIDENT_DOC_COLUMNS
        from src.rag.reranker import CrossEncoderReranker

        barrier_csv = tmp_path / "datasets" / "barrier_documents.csv"
        barrier_csv.parent.mkdir(parents=True)

        barriers = []
        for i in range(6):
            inc_id = f"INC-{i // 2}"
            barriers.append({
                "incident_id": inc_id,
                "control_id": f"C-{i:03d}",
                "barrier_role_match_text": f"Barrier: Control {i}\nRole: Test role\nLOD Basis: Test basis",
                "barrier_family": "training" if i % 2 == 0 else "monitoring",
                "barrier_type": "administrative",
                "side": "prevention",
                "line_of_defense": "1st",
                "barrier_status": "failed" if i % 2 == 0 else "active",
                "barrier_failed": str(i % 2 == 0),
                "barrier_failed_human": str(i % 3 == 0),
                "human_contribution_value": "high" if i % 2 == 0 else "",
                "pif_competence": "True",
                "pif_fatigue": "False",
                "pif_communication": str(i % 2 == 0),
                "pif_situational_awareness": "False",
                "pif_procedures": "True",
                "pif_workload": "False",
                "pif_time_pressure": "False",
                "pif_tools_equipment": "False",
                "pif_safety_culture": "False",
                "pif_management_of_change": "False",
                "pif_supervision": "False",
                "pif_training": "True",
                "supporting_text": json.dumps(["Evidence text"]),
                "confidence": "high",
                "incident_summary": f"Incident {i // 2} summary.",
            })
        with open(barrier_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=BARRIER_DOC_COLUMNS)
            writer.writeheader()
            writer.writerows(barriers)

        incident_csv = tmp_path / "datasets" / "incident_documents.csv"
        incidents = []
        for i in range(3):
            incidents.append({
                "incident_id": f"INC-{i}",
                "incident_embed_text": f"Top Event: Event {i}\nSummary: Incident {i}",
                "top_event": f"Event {i}",
                "incident_type": "Equipment Failure",
                "operating_phase": "production",
                "materials": json.dumps(["oil"]),
                "region": "Gulf of Mexico",
                "operator": f"Operator {i}",
                "summary": f"Incident {i} summary.",
                "recommendations": json.dumps(["Fix it"]),
            })
        with open(incident_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=INCIDENT_DOC_COLUMNS)
            writer.writeheader()
            writer.writerows(incidents)

        rng = np.random.default_rng(42)
        barrier_emb = rng.standard_normal((6, 8)).astype(np.float32)
        barrier_emb /= np.linalg.norm(barrier_emb, axis=1, keepdims=True)
        incident_emb = rng.standard_normal((3, 8)).astype(np.float32)
        incident_emb /= np.linalg.norm(incident_emb, axis=1, keepdims=True)

        (tmp_path / "embeddings").mkdir(parents=True, exist_ok=True)
        np.save(tmp_path / "embeddings" / "barrier_embeddings.npy", barrier_emb)
        np.save(tmp_path / "embeddings" / "incident_embeddings.npy", incident_emb)

        mock_provider = MagicMock()
        mock_provider.embed.return_value = barrier_emb[0]
        mock_provider.dimension = 8

        mock_reranker = MagicMock(spec=CrossEncoderReranker)

        def mock_rerank(barrier_query, incident_query, candidates, barrier_metadata, top_k=10):
            for i, c in enumerate(candidates):
                c.rerank_score = 1.0 - i * 0.1
            candidates.sort(key=lambda r: (-r.rerank_score, -r.rrf_score))
            return candidates[:top_k]
        mock_reranker.rerank.side_effect = mock_rerank

        agent = RAGAgent.from_directory(
            tmp_path, embedding_provider=mock_provider, reranker=mock_reranker
        )
        return agent, mock_reranker

    def test_explain_with_reranker_calls_rerank(self, tmp_path):
        agent, mock_reranker = self._build_agent_with_reranker(tmp_path)
        result = agent.explain(
            barrier_query="training",
            incident_query="failure",
        )
        mock_reranker.rerank.assert_called_once()
        assert isinstance(result, ExplanationResult)

    def test_explain_without_reranker_unchanged(self, tmp_path):
        """Verify Phase-1 behavior when no reranker provided."""
        import csv
        from src.rag.corpus_builder import BARRIER_DOC_COLUMNS, INCIDENT_DOC_COLUMNS

        barrier_csv = tmp_path / "datasets" / "barrier_documents.csv"
        barrier_csv.parent.mkdir(parents=True)
        barriers = []
        for i in range(6):
            inc_id = f"INC-{i // 2}"
            barriers.append({
                "incident_id": inc_id,
                "control_id": f"C-{i:03d}",
                "barrier_role_match_text": f"Barrier: Control {i}\nRole: Test role\nLOD Basis: Test basis",
                "barrier_family": "training" if i % 2 == 0 else "monitoring",
                "barrier_type": "administrative", "side": "prevention",
                "line_of_defense": "1st",
                "barrier_status": "failed" if i % 2 == 0 else "active",
                "barrier_failed": str(i % 2 == 0),
                "barrier_failed_human": str(i % 3 == 0),
                "human_contribution_value": "high" if i % 2 == 0 else "",
                "pif_competence": "True", "pif_fatigue": "False",
                "pif_communication": str(i % 2 == 0),
                "pif_situational_awareness": "False", "pif_procedures": "True",
                "pif_workload": "False", "pif_time_pressure": "False",
                "pif_tools_equipment": "False", "pif_safety_culture": "False",
                "pif_management_of_change": "False", "pif_supervision": "False",
                "pif_training": "True",
                "supporting_text": json.dumps(["Evidence text"]),
                "confidence": "high",
                "incident_summary": f"Incident {i // 2} summary.",
            })
        with open(barrier_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=BARRIER_DOC_COLUMNS)
            writer.writeheader()
            writer.writerows(barriers)
        incident_csv = tmp_path / "datasets" / "incident_documents.csv"
        incidents = []
        for i in range(3):
            incidents.append({
                "incident_id": f"INC-{i}",
                "incident_embed_text": f"Top Event: Event {i}\nSummary: Incident {i}",
                "top_event": f"Event {i}", "incident_type": "Equipment Failure",
                "operating_phase": "production", "materials": json.dumps(["oil"]),
                "region": "Gulf of Mexico", "operator": f"Operator {i}",
                "summary": f"Incident {i} summary.",
                "recommendations": json.dumps(["Fix it"]),
            })
        with open(incident_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=INCIDENT_DOC_COLUMNS)
            writer.writeheader()
            writer.writerows(incidents)

        rng = np.random.default_rng(42)
        barrier_emb = rng.standard_normal((6, 8)).astype(np.float32)
        barrier_emb /= np.linalg.norm(barrier_emb, axis=1, keepdims=True)
        incident_emb = rng.standard_normal((3, 8)).astype(np.float32)
        incident_emb /= np.linalg.norm(incident_emb, axis=1, keepdims=True)

        (tmp_path / "embeddings").mkdir(parents=True, exist_ok=True)
        np.save(tmp_path / "embeddings" / "barrier_embeddings.npy", barrier_emb)
        np.save(tmp_path / "embeddings" / "incident_embeddings.npy", incident_emb)

        mock_provider = MagicMock()
        mock_provider.embed.return_value = barrier_emb[0]
        mock_provider.dimension = 8

        # No reranker
        agent = RAGAgent.from_directory(tmp_path, embedding_provider=mock_provider)
        result = agent.explain(barrier_query="training", incident_query="failure")
        assert isinstance(result, ExplanationResult)
        # All results should have rerank_score == None
        for r in result.results:
            assert r.rerank_score is None
