# tests/test_rag_integration.py
"""End-to-end integration test for the RAG hybrid retrieval pipeline.

Uses synthetic V2.3 JSON incidents to test the full flow:
  JSON -> corpus_builder -> embeddings -> FAISS index -> retriever -> context
"""
import json
import numpy as np
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.rag.corpus_builder import build_barrier_documents, build_incident_documents
from src.rag.rag_agent import RAGAgent, ExplanationResult


def _make_incident(incident_id: str, top_event: str, barrier_name: str) -> dict:
    return {
        "incident_id": incident_id,
        "source": {"doc_type": "test", "url": None, "title": "Test", "date_published": None, "date_occurred": None, "timezone": None},
        "context": {"region": "Test Region", "operator": "Test Op", "operating_phase": "production", "materials": ["oil"]},
        "event": {
            "top_event": top_event,
            "incident_type": "Equipment Failure",
            "costs": None,
            "actions_taken": [],
            "summary": f"Incident involving {top_event.lower()}.",
            "recommendations": [],
            "key_phrases": [],
        },
        "bowtie": {
            "hazards": [], "threats": [], "consequences": [],
            "controls": [{
                "control_id": "C-001",
                "name": barrier_name,
                "side": "prevention",
                "barrier_role": "Prevent failure",
                "barrier_type": "engineering",
                "line_of_defense": "1st",
                "lod_basis": "Primary protection",
                "linked_threat_ids": [],
                "linked_consequence_ids": [],
                "performance": {"barrier_status": "failed", "barrier_failed": True,
                    "detection_applicable": False, "detection_mentioned": False,
                    "alarm_applicable": False, "alarm_mentioned": False,
                    "manual_intervention_applicable": False, "manual_intervention_mentioned": False},
                "human": {"human_contribution_value": "high", "human_contribution_mentioned": True,
                    "barrier_failed_human": True, "linked_pif_ids": []},
                "evidence": {"supporting_text": ["Test evidence"], "confidence": "high"},
            }],
        },
        "pifs": {
            "people": {"competence_value": "low", "competence_mentioned": True,
                "fatigue_value": None, "fatigue_mentioned": False,
                "communication_value": None, "communication_mentioned": False,
                "situational_awareness_value": None, "situational_awareness_mentioned": False},
            "work": {"procedures_value": None, "procedures_mentioned": False,
                "workload_value": None, "workload_mentioned": False,
                "time_pressure_value": None, "time_pressure_mentioned": False,
                "tools_equipment_value": None, "tools_equipment_mentioned": False},
            "organisation": {"safety_culture_value": None, "safety_culture_mentioned": False,
                "management_of_change_value": None, "management_of_change_mentioned": False,
                "supervision_value": None, "supervision_mentioned": False,
                "training_value": None, "training_mentioned": False},
        },
        "notes": {"rules": "test", "schema_version": "2.3"},
    }


class TestRAGIntegration:
    def test_end_to_end(self, tmp_path):
        # 1. Create JSON incidents
        json_dir = tmp_path / "incidents"
        json_dir.mkdir()
        for i, (event, barrier) in enumerate([
            ("Pressure vessel rupture", "Pressure Safety Valve"),
            ("Gas leak from flange", "Flange Inspection Program"),
            ("Crane dropped load", "Lift Plan Procedure"),
        ]):
            path = json_dir / f"inc_{i}.json"
            path.write_text(json.dumps(_make_incident(f"INC-{i}", event, barrier)))

        # 2. Build corpus
        rag_dir = tmp_path / "rag"
        datasets_dir = rag_dir / "datasets"
        datasets_dir.mkdir(parents=True)
        b_count = build_barrier_documents(json_dir, datasets_dir / "barrier_documents.csv")
        i_count = build_incident_documents(json_dir, datasets_dir / "incident_documents.csv")
        assert b_count == 3
        assert i_count == 3

        # 3. Generate mock embeddings (deterministic)
        rng = np.random.default_rng(42)
        dim = 8
        barrier_emb = rng.standard_normal((b_count, dim)).astype(np.float32)
        barrier_emb /= np.linalg.norm(barrier_emb, axis=1, keepdims=True)
        incident_emb = rng.standard_normal((i_count, dim)).astype(np.float32)
        incident_emb /= np.linalg.norm(incident_emb, axis=1, keepdims=True)

        emb_dir = rag_dir / "embeddings"
        emb_dir.mkdir()
        np.save(emb_dir / "barrier_embeddings.npy", barrier_emb)
        np.save(emb_dir / "incident_embeddings.npy", incident_emb)

        # 4. Create RAG agent with mock provider
        mock_provider = MagicMock()
        mock_provider.embed.return_value = barrier_emb[0]
        mock_provider.dimension = dim

        agent = RAGAgent.from_directory(rag_dir, embedding_provider=mock_provider)

        # 5. Run explain
        result = agent.explain(
            barrier_query="pressure safety valve prevent overpressure",
            incident_query="pressure vessel rupture gas release",
            top_k=3,
        )

        assert isinstance(result, ExplanationResult)
        assert len(result.context_text) > 0
        assert "Similar Barrier Failures" in result.context_text
        assert result.metadata["result_count"] >= 0
        assert result.metadata["top_k"] == 3
