"""Tests for BarrierExplainer -- confidence gate, citations, LLM narrative."""
from __future__ import annotations

import csv
import json

import numpy as np
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.llm.base import LLMProvider
from src.rag.rag_agent import RAGAgent, ExplanationResult
from src.rag.retriever import RetrievalResult


class NarrativeStubProvider(LLMProvider):
    """Test stub that returns a fixed narrative string (NOT JSON).

    Unlike StubProvider (which returns Schema v2.3 JSON for extraction),
    this returns a short plain-text narrative suitable for explainer tests.
    See RESEARCH.md Pitfall 5.
    """

    def __init__(self) -> None:
        self.call_count = 0
        self.last_prompt: str = ""
        self.model = "narrative-stub"

    def extract(self, prompt: str) -> str:
        self.call_count += 1
        self.last_prompt = prompt
        return (
            "Based on similar incidents, this barrier shows elevated risk. "
            "In incident INC-0, a similar training barrier failed due to "
            "inadequate competency verification. The evidence suggests "
            "procedural gaps contributed to barrier degradation."
        )


def _build_agent(tmp_path: Path) -> RAGAgent:
    """Build a RAGAgent from synthetic data (mirrors TestRAGAgent._build_agent pattern)."""
    from src.rag.corpus_builder import BARRIER_DOC_COLUMNS, INCIDENT_DOC_COLUMNS

    # Barrier documents
    barrier_csv = tmp_path / "datasets" / "barrier_documents.csv"
    barrier_csv.parent.mkdir(parents=True)

    barriers = []
    for i in range(6):
        inc_id = f"INC-{i // 2}"
        barriers.append({
            "incident_id": inc_id,
            "control_id": f"C-{i:03d}",
            "barrier_role_match_text": (
                f"Barrier: Control {i}\nRole: Test role\nLOD Basis: Test basis"
            ),
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
            "supporting_text": json.dumps(["Evidence text for control " + str(i)]),
            "confidence": "high",
            "incident_summary": f"Incident {i // 2} summary.",
        })
    with open(barrier_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BARRIER_DOC_COLUMNS)
        writer.writeheader()
        writer.writerows(barriers)

    # Incident documents
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

    # Mock embeddings (deterministic)
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

    return RAGAgent.from_directory(tmp_path, embedding_provider=mock_provider)


def _build_mock_agent_with_scores(sim_scores: list[float]) -> RAGAgent:
    """Build a mock RAGAgent whose explain() returns results with controlled barrier_sim_scores."""
    results = [
        RetrievalResult(
            incident_id=f"INC-{i}",
            control_id=f"C-{i:03d}",
            barrier_family="training",
            barrier_failed_human=True,
            rrf_score=0.03,
            barrier_rank=i + 1,
            incident_rank=i + 1,
            barrier_sim_score=score,
            incident_sim_score=0.5,
        )
        for i, score in enumerate(sim_scores)
    ]
    # Build barrier_meta to support _find_barrier_meta lookups in _build_citations
    barrier_meta = [
        {
            "control_id": f"C-{i:03d}",
            "incident_id": f"INC-{i}",
            "barrier_role_match_text": f"Barrier: Test Barrier {i}\nRole: Test role\nLOD Basis: Basis",
            "barrier_family": "training",
            "supporting_text": json.dumps([f"Supporting text {i}"]),
        }
        for i in range(len(sim_scores))
    ]
    explanation_result = ExplanationResult(
        context_text="Some retrieved context text.",
        results=results,
        metadata={"top_k": 10},
    )
    mock_agent = MagicMock(spec=RAGAgent)
    mock_agent.explain.return_value = explanation_result
    mock_agent._find_barrier_meta.side_effect = lambda r: next(
        (m for m in barrier_meta if m["control_id"] == r.control_id), {}
    )
    return mock_agent


class TestBarrierExplainerNarrative:
    """Tests for narrative generation when confidence gate passes."""

    def test_explain_returns_narrative(self, tmp_path):
        """explain() returns ExplanationResult with non-empty narrative when sim_scores >= 0.25."""
        stub = NarrativeStubProvider()
        mock_agent = _build_mock_agent_with_scores([0.80, 0.75, 0.70])

        from src.rag.explainer import BarrierExplainer
        explainer = BarrierExplainer(rag_agent=mock_agent, llm_provider=stub)
        result = explainer.explain(
            barrier_query="Safety training for valve operations",
            incident_query="Valve failure due to operator error",
        )

        assert isinstance(result, ExplanationResult)
        assert len(result.narrative) > 0
        assert result.model_used != "none"
        assert result.model_used == "narrative-stub"

    def test_explain_without_shap(self, tmp_path):
        """explain() with shap_factors=None still returns a valid narrative."""
        stub = NarrativeStubProvider()
        mock_agent = _build_mock_agent_with_scores([0.80])

        from src.rag.explainer import BarrierExplainer
        explainer = BarrierExplainer(rag_agent=mock_agent, llm_provider=stub)
        result = explainer.explain(
            barrier_query="Pressure relief valve training",
            incident_query="Overpressure event",
            shap_factors=None,
        )

        assert isinstance(result, ExplanationResult)
        assert len(result.narrative) > 0
        assert stub.call_count == 1

    def test_confidence_gate_passes_llm_called(self):
        """When best barrier_sim_score >= 0.25, LLM.extract() is called exactly once."""
        stub = NarrativeStubProvider()
        mock_agent = _build_mock_agent_with_scores([0.80, 0.60, 0.40])

        from src.rag.explainer import BarrierExplainer
        explainer = BarrierExplainer(rag_agent=mock_agent, llm_provider=stub)
        result = explainer.explain(
            barrier_query="Training barrier",
            incident_query="Incident query",
        )

        assert stub.call_count == 1
        assert result.model_used != "none"


class TestConfidenceGate:
    """Tests for the confidence gate (barrier_sim_score < CONFIDENCE_THRESHOLD)."""

    def test_confidence_gate_fires(self):
        """When all barrier_sim_scores < 0.25, narrative is fallback and LLM NOT called."""
        stub = NarrativeStubProvider()
        mock_agent = _build_mock_agent_with_scores([0.20, 0.15, 0.10])

        from src.rag.explainer import BarrierExplainer
        explainer = BarrierExplainer(rag_agent=mock_agent, llm_provider=stub)
        result = explainer.explain(
            barrier_query="Low confidence barrier query",
            incident_query="Low confidence incident query",
        )

        assert result.narrative == "No matching incidents found."
        assert result.model_used == "none"
        assert stub.call_count == 0
        assert result.citations == []

    def test_no_results_returns_gate_fired(self):
        """When RAGAgent returns empty results list, gate fires (max of empty = 0.0 < 0.25)."""
        stub = NarrativeStubProvider()
        mock_agent = _build_mock_agent_with_scores([])  # empty results

        from src.rag.explainer import BarrierExplainer
        explainer = BarrierExplainer(rag_agent=mock_agent, llm_provider=stub)
        result = explainer.explain(
            barrier_query="No results barrier",
            incident_query="No results incident",
        )

        assert result.narrative == "No matching incidents found."
        assert result.model_used == "none"
        assert stub.call_count == 0
        assert result.retrieval_confidence == 0.0


class TestCitations:
    """Tests for citation structure and content."""

    def test_citations_populated(self):
        """Citations list is non-empty, each Citation has required fields."""
        stub = NarrativeStubProvider()
        mock_agent = _build_mock_agent_with_scores([0.85, 0.75])

        from src.rag.explainer import BarrierExplainer, Citation
        explainer = BarrierExplainer(rag_agent=mock_agent, llm_provider=stub)
        result = explainer.explain(
            barrier_query="Test barrier",
            incident_query="Test incident",
        )

        assert len(result.citations) > 0
        for citation in result.citations:
            assert isinstance(citation, Citation)
            assert citation.incident_id  # non-empty
            assert citation.control_id   # non-empty
            assert citation.relevance_score > 0

    def test_citation_pinned_to_barrier(self):
        """Each citation's control_id matches a RetrievalResult's control_id."""
        stub = NarrativeStubProvider()
        sim_scores = [0.85, 0.75, 0.65]
        mock_agent = _build_mock_agent_with_scores(sim_scores)

        from src.rag.explainer import BarrierExplainer
        explainer = BarrierExplainer(rag_agent=mock_agent, llm_provider=stub)
        result = explainer.explain(
            barrier_query="Test barrier",
            incident_query="Test incident",
        )

        result_control_ids = {r.control_id for r in mock_agent.explain.return_value.results}
        for citation in result.citations:
            assert citation.control_id in result_control_ids, (
                f"Citation control_id {citation.control_id} not in retrieval results"
            )


class TestSHAPIntegration:
    """Tests for SHAP factor integration in the prompt."""

    def test_shap_in_prompt(self):
        """When shap_factors provided, prompt contains 'Model Analysis' and factor names."""
        stub = NarrativeStubProvider()
        mock_agent = _build_mock_agent_with_scores([0.80])

        from src.rag.explainer import BarrierExplainer
        explainer = BarrierExplainer(rag_agent=mock_agent, llm_provider=stub)
        shap_factors = {
            "barrier_family": 0.42,
            "line_of_defense": -0.15,
            "competence_mentioned": 0.08,
        }
        result = explainer.explain(
            barrier_query="Test barrier with SHAP",
            incident_query="Test incident",
            shap_factors=shap_factors,
        )

        assert stub.call_count == 1
        prompt = stub.last_prompt
        assert "Model Analysis" in prompt
        assert "Barrier Family" in prompt
        assert "Line of Defense" in prompt
        # competence_mentioned mapped via pif_to_degradation.yaml or kept as-is
        assert "competence" in prompt.lower()

    def test_no_shap_prompt_has_no_model_analysis(self):
        """When shap_factors=None, prompt does NOT contain 'Model Analysis'."""
        stub = NarrativeStubProvider()
        mock_agent = _build_mock_agent_with_scores([0.80])

        from src.rag.explainer import BarrierExplainer
        explainer = BarrierExplainer(rag_agent=mock_agent, llm_provider=stub)
        result = explainer.explain(
            barrier_query="Test barrier no SHAP",
            incident_query="Test incident",
            shap_factors=None,
        )

        prompt = stub.last_prompt
        assert "Model Analysis" not in prompt
