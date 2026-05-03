"""S04 integration test: real v2 corpus + demo scenario pair query.

Requires data/rag/v2/ artifacts produced by scripts/build_rag_v2.py (T01).
Skips gracefully when artifacts or heavy deps are absent.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

sentence_transformers = pytest.importorskip("sentence_transformers")
faiss = pytest.importorskip("faiss")

_V2_BARRIER_BIN = Path("data/rag/v2/barrier_faiss.bin")
_DEMO_SCENARIO = Path("data/demo_scenarios/bsee_eb-165-a-fieldwood-09-may-2015.json")
_CASCADING_PARQUET = Path("data/processed/cascading_training.parquet")


@pytest.mark.integration
@pytest.mark.skipif(
    not _V2_BARRIER_BIN.exists() or not _CASCADING_PARQUET.exists(),
    reason="Run scripts/build_rag_v2.py (T01) and data_prep first; "
           "data/rag/v2/barrier_faiss.bin or data/processed/cascading_training.parquet absent",
)
class TestS04Integration:
    def test_pair_context_from_demo_scenario(self) -> None:
        """Full integration: load v2 corpus, query with demo-scenario pair."""
        import pandas as pd

        from src.rag.embeddings.sentence_transformers_provider import SentenceTransformerProvider
        from src.rag.pair_context_builder import build_pair_context
        from src.rag.rag_agent import RAGAgent

        # (1) Load RAGAgent from v2 directory
        provider = SentenceTransformerProvider()
        agent = RAGAgent.from_directory(Path("data/rag/v2"), provider)

        # (2) Load demo scenario
        with open(_DEMO_SCENARIO, encoding="utf-8") as f:
            scenario = json.load(f)

        barriers = scenario["barriers"]
        ctx = scenario.get("context", {})

        # (3) Pick barriers[0] as conditioning, barriers[1] as target
        conditioning = barriers[0]
        target = barriers[1]

        incident_context = {
            "top_event": scenario.get("top_event", ""),
            "incident_type": "",
            "operating_phase": ctx.get("operating_phase", ""),
            "materials": ctx.get("materials", []),
            "summary": "",
            "recommendations": [],
            "pif_value_texts": [],
        }

        # (4) Call build_pair_context
        result = build_pair_context(conditioning, target, agent, incident_context)

        # (5) context_text is a non-empty string containing both section headers
        assert isinstance(result.context_text, str)
        assert len(result.context_text) > 0
        assert "## Conditioning Barrier" in result.context_text
        assert "## Target Barrier" in result.context_text

        # (6) empty_retrievals == [] (real v2 corpus should return hits)
        assert result.empty_retrievals == [], (
            f"Unexpected empty retrievals: {result.empty_retrievals}"
        )

        # (7) Top conditioning result's incident_id is within the 156-incident scope
        df = pd.read_parquet(str(_CASCADING_PARQUET))
        scope_ids = set(df["incident_id"].unique())
        assert result.conditioning_results, "No conditioning results to check"
        top_conditioning_id = result.conditioning_results[0].incident_id
        assert top_conditioning_id in scope_ids, (
            f"Top conditioning result incident_id '{top_conditioning_id}' "
            f"not in 156-incident cascading scope"
        )

        # (8) At least one retrieved incident's context_text contains D017 sections
        d017_present = (
            "Recommendations:" in result.context_text
            or "Performance-Influencing Factor Notes:" in result.context_text
        )
        assert d017_present, (
            "Neither 'Recommendations:' nor 'Performance-Influencing Factor Notes:' "
            "found in context_text — D017 text did not enter the embedded corpus."
        )
