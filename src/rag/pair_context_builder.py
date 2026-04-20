"""Build dual-query RAG context for (conditioning, target) barrier pairs."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.rag import corpus_builder
from src.rag.rag_agent import ExplanationResult, RAGAgent

logger = logging.getLogger(__name__)

_NO_RESULTS_SENTINEL = "No similar barrier failures found."


@dataclass
class PairContextResult:
    """Result of a dual-barrier RAG context build."""

    context_text: str
    conditioning_results: list
    target_results: list
    empty_retrievals: list[str] = field(default_factory=list)


def build_pair_context(
    conditioning_barrier: dict[str, Any],
    target_barrier: dict[str, Any],
    rag_agent: RAGAgent,
    incident_context: dict[str, Any] | None = None,
) -> PairContextResult:
    """Build merged RAG context for a (conditioning, target) barrier pair.

    Runs two separate RAGAgent.explain() calls — one per barrier — with a
    shared incident_query composed from incident_context. Does NOT call an LLM.

    Args:
        conditioning_barrier: Barrier dict (demo-scenario shape) assumed failed.
        target_barrier: Barrier dict (demo-scenario shape) being predicted.
        rag_agent: Loaded RAGAgent instance.
        incident_context: Optional dict with top_event, incident_type,
            operating_phase, materials (list), summary, recommendations (list),
            pif_value_texts (list). Missing keys fall back to empty strings/lists.

    Returns:
        PairContextResult with merged context_text and per-side results.
    """
    ctx = incident_context or {}

    # Extract incident fields — never pass None to compose_incident_text
    top_event: str = ctx.get("top_event") or ""
    incident_type: str = ctx.get("incident_type") or ""
    operating_phase: str = ctx.get("operating_phase") or ""
    raw_materials = ctx.get("materials") or []
    materials: list[str] = list(raw_materials) if isinstance(raw_materials, list) else []
    summary: str = ctx.get("summary") or ""
    raw_recs = ctx.get("recommendations") or []
    recommendations: list[str] = list(raw_recs) if isinstance(raw_recs, list) else []
    raw_pivals = ctx.get("pif_value_texts") or []
    pif_value_texts: list[str] = list(raw_pivals) if isinstance(raw_pivals, list) else []

    incident_query = corpus_builder.compose_incident_text(
        top_event=top_event,
        incident_type=incident_type,
        operating_phase=operating_phase,
        materials=materials,
        summary=summary,
        recommendations=recommendations,
        pif_value_texts=pif_value_texts,
    )

    # Build barrier queries
    conditioning_query = corpus_builder.compose_barrier_text(
        name=conditioning_barrier.get("name", ""),
        barrier_role=conditioning_barrier.get("barrier_role", ""),
        lod_basis=(
            conditioning_barrier.get("lod_industry_standard")
            or conditioning_barrier.get("lod_basis")
        ),
    )
    target_query = corpus_builder.compose_barrier_text(
        name=target_barrier.get("name", ""),
        barrier_role=target_barrier.get("barrier_role", ""),
        lod_basis=(
            target_barrier.get("lod_industry_standard")
            or target_barrier.get("lod_basis")
        ),
    )

    # Retrieve — conditioning assumes failed (human factor filter on)
    conditioning_result: ExplanationResult = rag_agent.explain(
        barrier_query=conditioning_query,
        incident_query=incident_query,
        barrier_failed_human=True,
    )
    target_result: ExplanationResult = rag_agent.explain(
        barrier_query=target_query,
        incident_query=incident_query,
    )

    # Detect empty retrievals
    empty_retrievals: list[str] = []
    if not conditioning_result.results:
        empty_retrievals.append("conditioning")
    if not target_result.results:
        empty_retrievals.append("target")

    if empty_retrievals:
        logger.warning(
            "Empty RAG retrievals for pair (%s / %s): %s",
            conditioning_barrier.get("control_id", "?"),
            target_barrier.get("control_id", "?"),
            empty_retrievals,
        )

    # Build merged context text
    conditioning_body = conditioning_result.context_text or _NO_RESULTS_SENTINEL
    target_body = target_result.context_text or _NO_RESULTS_SENTINEL

    context_text = (
        f"## Conditioning Barrier — Similar Failures\n\n{conditioning_body}\n\n"
        f"## Target Barrier — Similar Failures\n\n{target_body}"
    )

    return PairContextResult(
        context_text=context_text,
        conditioning_results=conditioning_result.results,
        target_results=target_result.results,
        empty_retrievals=empty_retrievals,
    )
