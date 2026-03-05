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
