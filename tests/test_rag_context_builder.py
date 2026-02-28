# tests/test_rag_context_builder.py
import json
import pytest
from src.rag.context_builder import build_context, ContextEntry


class TestBuildContext:
    def _make_entry(self, rank: int = 1) -> ContextEntry:
        return ContextEntry(
            incident_id="INC-001",
            control_id="C-001",
            barrier_name="Pressure Safety Valve",
            barrier_family="overpressurization_gas_discharge_gas_isolation",
            side="prevention",
            barrier_status="failed",
            barrier_role="Prevent overpressure",
            lod_basis="Primary pressure protection",
            barrier_failed_human=True,
            human_contribution_value="high",
            supporting_text=["The PSV was not tested", "Maintenance overdue"],
            incident_summary="A valve failed causing release.",
            rrf_score=0.032,
            barrier_rank=rank,
            incident_rank=3,
        )

    def test_single_result(self):
        entries = [self._make_entry()]
        text = build_context(entries)
        assert "## Similar Barrier Failures" in text
        assert "Pressure Safety Valve" in text
        assert "Prevent overpressure" in text
        assert "The PSV was not tested" in text
        assert "A valve failed" in text
        assert "RRF:" in text

    def test_multiple_results(self):
        entries = [self._make_entry(rank=1), self._make_entry(rank=2)]
        text = build_context(entries)
        assert "### Result 1" in text
        assert "### Result 2" in text

    def test_truncation(self):
        entries = [self._make_entry(rank=i) for i in range(1, 20)]
        text = build_context(entries, max_context_chars=500)
        assert len(text) <= 600  # allow some slack for header
        assert "### Result 19" not in text

    def test_empty_input(self):
        text = build_context([])
        assert "No similar barrier failures found" in text
