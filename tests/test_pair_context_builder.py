"""Tests for pair_context_builder."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.rag.pair_context_builder import PairContextResult, build_pair_context
from src.rag.rag_agent import ExplanationResult
from src.rag.retriever import RetrievalResult


def _make_result(incident_id: str = "INC-001", control_id: str = "C-001") -> RetrievalResult:
    return RetrievalResult(
        incident_id=incident_id,
        control_id=control_id,
        barrier_family="overpressurization_gas_discharge_gas_isolation",
        barrier_failed_human=True,
        rrf_score=0.5,
        barrier_rank=1,
        incident_rank=1,
        barrier_sim_score=0.9,
        incident_sim_score=0.8,
    )


def _make_explanation(context_text: str, results: list | None = None) -> ExplanationResult:
    return ExplanationResult(
        context_text=context_text,
        results=results if results is not None else [_make_result()],
    )


def _stub_rag_agent(conditioning_explanation: ExplanationResult, target_explanation: ExplanationResult) -> MagicMock:
    agent = MagicMock()
    agent.explain.side_effect = [conditioning_explanation, target_explanation]
    return agent


_CONDITIONING_BARRIER = {
    "control_id": "C-001",
    "name": "Pressure Safety Valve",
    "barrier_role": "Prevent overpressurization",
    "barrier_type": "engineering",
    "barrier_level": "prevention",
    "lod_industry_standard": "Process Control",
    "barrier_condition": "ineffective",
    "description": "PSV on wellhead",
}

_TARGET_BARRIER = {
    "control_id": "C-002",
    "name": "Emergency Shutdown System",
    "barrier_role": "Shut down process on high pressure",
    "barrier_type": "engineering",
    "barrier_level": "prevention",
    "lod_industry_standard": "Safety Instrumented System",
    "barrier_condition": "degraded",
    "description": "ESD triggers on HH pressure",
}

_INCIDENT_CONTEXT = {
    "top_event": "Loss of Containment",
    "incident_type": "Equipment Failure",
    "operating_phase": "production",
    "materials": ["crude oil", "gas"],
    "summary": "Pressure relief valve failed during production.",
    "recommendations": ["Replace valve annually", "Conduct pressure testing"],
    "pif_value_texts": ["low competence", "inadequate procedures"],
}


class TestBothRetrievalsNonEmpty:
    def test_context_text_contains_both_section_headers(self) -> None:
        """(1) Both retrievals non-empty → context_text has both headers, empty_retrievals == []."""
        conditioning_exp = _make_explanation("Conditioning result text.", results=[_make_result("INC-A", "C-001")])
        target_exp = _make_explanation("Target result text.", results=[_make_result("INC-B", "C-002")])
        agent = _stub_rag_agent(conditioning_exp, target_exp)

        result = build_pair_context(_CONDITIONING_BARRIER, _TARGET_BARRIER, agent, _INCIDENT_CONTEXT)

        assert isinstance(result, PairContextResult)
        assert "## Conditioning Barrier — Similar Failures" in result.context_text
        assert "## Target Barrier — Similar Failures" in result.context_text
        assert "Conditioning result text." in result.context_text
        assert "Target result text." in result.context_text
        assert result.empty_retrievals == []

    def test_conditioning_called_with_barrier_failed_human_true(self) -> None:
        """Conditioning explain call must pass barrier_failed_human=True."""
        conditioning_exp = _make_explanation("cond", results=[_make_result()])
        target_exp = _make_explanation("tgt", results=[_make_result()])
        agent = _stub_rag_agent(conditioning_exp, target_exp)

        build_pair_context(_CONDITIONING_BARRIER, _TARGET_BARRIER, agent, _INCIDENT_CONTEXT)

        first_call_kwargs = agent.explain.call_args_list[0]
        assert first_call_kwargs.kwargs.get("barrier_failed_human") is True

    def test_target_called_without_barrier_failed_human(self) -> None:
        """Target explain call must NOT set barrier_failed_human."""
        conditioning_exp = _make_explanation("cond", results=[_make_result()])
        target_exp = _make_explanation("tgt", results=[_make_result()])
        agent = _stub_rag_agent(conditioning_exp, target_exp)

        build_pair_context(_CONDITIONING_BARRIER, _TARGET_BARRIER, agent, _INCIDENT_CONTEXT)

        second_call_kwargs = agent.explain.call_args_list[1]
        assert "barrier_failed_human" not in second_call_kwargs.kwargs or second_call_kwargs.kwargs.get("barrier_failed_human") is None


class TestConditioningRetrievalEmpty:
    def test_empty_conditioning_sets_sentinel_and_empty_retrievals(self) -> None:
        """(2) Conditioning empty → empty_retrievals == ['conditioning'], sentinel in context."""
        conditioning_exp = _make_explanation("", results=[])
        target_exp = _make_explanation("Target text.", results=[_make_result()])
        agent = _stub_rag_agent(conditioning_exp, target_exp)

        result = build_pair_context(_CONDITIONING_BARRIER, _TARGET_BARRIER, agent, _INCIDENT_CONTEXT)

        assert result.empty_retrievals == ["conditioning"]
        assert "No similar barrier failures found." in result.context_text
        assert "## Conditioning Barrier — Similar Failures" in result.context_text
        assert "Target text." in result.context_text


class TestMissingOptionalFields:
    def test_minimal_barrier_dicts_do_not_raise(self) -> None:
        """(3) Minimal barrier dicts with missing optional fields → no exception."""
        conditioning_exp = _make_explanation("cond", results=[_make_result()])
        target_exp = _make_explanation("tgt", results=[_make_result()])
        agent = _stub_rag_agent(conditioning_exp, target_exp)

        minimal_barrier: dict = {"name": "Valve", "barrier_role": "Isolate"}

        result = build_pair_context(minimal_barrier, minimal_barrier, agent, None)

        assert isinstance(result, PairContextResult)
        assert result.context_text != ""

    def test_none_incident_context_uses_fallbacks(self) -> None:
        """incident_context=None must not raise and never pass None to compose functions."""
        conditioning_exp = _make_explanation("cond", results=[_make_result()])
        target_exp = _make_explanation("tgt", results=[_make_result()])
        agent = _stub_rag_agent(conditioning_exp, target_exp)

        result = build_pair_context(_CONDITIONING_BARRIER, _TARGET_BARRIER, agent, None)

        assert isinstance(result, PairContextResult)
        # incident_query in first explain call should be a non-None string
        first_call = agent.explain.call_args_list[0]
        incident_q = first_call.kwargs.get("incident_query") or first_call.args[1]
        assert incident_q is not None
        assert isinstance(incident_q, str)
