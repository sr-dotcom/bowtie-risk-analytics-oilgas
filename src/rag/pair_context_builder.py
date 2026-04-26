"""Build dual-query RAG context for (conditioning, target) barrier pairs."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from src.rag import corpus_builder
from src.rag.context_builder import ContextEntry, build_context
from src.rag.rag_agent import ExplanationResult, RAGAgent
from src.rag.retriever import RetrievalResult

logger = logging.getLogger(__name__)

_NO_RESULTS_SENTINEL = "No similar barrier failures found."

# ---------------------------------------------------------------------------
# Domain filter — restrict retrieval to oil & gas incidents
# ---------------------------------------------------------------------------

# Primary: agency-based allowlist (forward-compatible; current corpus has no agency field)
OIL_GAS_AGENCY_ALLOWLIST: frozenset[str] = frozenset({"BSEE", "TSB", "PHMSA"})

# Fallback: case-insensitive region substring match when agency is absent
OIL_GAS_REGION_KEYWORDS: frozenset[str] = frozenset({"gulf", "offshore", "north sea", "alaska"})


def _is_oil_gas_incident(incident_id: str, incident_meta: dict[str, Any]) -> bool:
    """Return True if the incident belongs to the oil & gas domain.

    Fails open: unknown incidents (not in meta, or meta store is not a real
    dict) pass through unchanged. Only incidents positively identified as
    non-oil-gas (known agency not in allowlist, OR known region with no keyword
    match) are removed.

    Agency field takes priority (exact allowlist match). Falls back to region
    keyword substring matching when agency is absent — handles current corpus
    where incident_documents.csv carries no agency column.
    """
    if not isinstance(incident_meta, dict):
        return True  # meta store unavailable — pass through
    meta = incident_meta.get(incident_id)
    if not isinstance(meta, dict):
        return True  # unknown incident — pass through
    agency = (meta.get("agency") or "").strip().upper()
    if agency:
        return agency in OIL_GAS_AGENCY_ALLOWLIST
    region = (meta.get("region") or "").lower()
    if not region:
        return True  # no geo info — pass through
    return any(kw in region for kw in OIL_GAS_REGION_KEYWORDS)


def _dedup_by_incident(results: list[RetrievalResult]) -> list[RetrievalResult]:
    """Keep only the highest-RRF result per incident_id, preserving original order."""
    best: dict[str, RetrievalResult] = {}
    for r in results:
        if r.incident_id not in best or r.rrf_score > best[r.incident_id].rrf_score:
            best[r.incident_id] = r
    seen: set[str] = set()
    deduped: list[RetrievalResult] = []
    for r in results:
        if r.incident_id not in seen and best[r.incident_id] is r:
            seen.add(r.incident_id)
            deduped.append(r)
    return deduped


def _rebuild_context_for_filtered(
    results: list[RetrievalResult],
    rag_agent: RAGAgent,
) -> str:
    """Rebuild context text from a domain-filtered result list.

    Mirrors the ContextEntry assembly in RAGAgent.explain() so that
    context_text in PairContextResult only contains oil & gas incidents.
    """
    entries: list[ContextEntry] = []
    for r in results:
        b_meta = rag_agent._find_barrier_meta(r)
        i_meta = rag_agent._incident_meta.get(r.incident_id, {})

        supporting_text: list[str] = []
        raw = b_meta.get("supporting_text", "[]")
        try:
            supporting_text = json.loads(raw) if raw else []
        except (json.JSONDecodeError, TypeError):
            supporting_text = []

        barrier_text = b_meta.get("barrier_role_match_text", "")
        lines_bt = barrier_text.split("\n")
        barrier_name = lines_bt[0].replace("Barrier: ", "") if lines_bt else ""
        barrier_role = lines_bt[1].replace("Role: ", "") if len(lines_bt) > 1 else ""
        lod_basis = lines_bt[2].replace("LOD Basis: ", "") if len(lines_bt) > 2 else ""

        incident_recommendations: list[str] = []
        raw_recs = i_meta.get("recommendations", "[]")
        try:
            parsed = json.loads(raw_recs) if raw_recs else []
            if isinstance(parsed, list):
                incident_recommendations = [str(x) for x in parsed if x]
        except (json.JSONDecodeError, TypeError):
            pass

        pif_tags: dict[str, list[str]] | None = None
        raw_pif = i_meta.get("pif_tags_json")
        if raw_pif:
            try:
                pif_tags = json.loads(raw_pif)
            except (json.JSONDecodeError, TypeError):
                pass

        entries.append(ContextEntry(
            incident_id=r.incident_id,
            control_id=b_meta.get("control_id", r.control_id),
            barrier_name=barrier_name,
            barrier_family=r.barrier_family,
            side=b_meta.get("side", ""),
            barrier_status=b_meta.get("barrier_status", ""),
            barrier_role=barrier_role,
            lod_basis=lod_basis,
            barrier_failed_human=r.barrier_failed_human,
            human_contribution_value=b_meta.get("human_contribution_value", ""),
            supporting_text=supporting_text,
            incident_summary=b_meta.get("incident_summary", i_meta.get("summary", "")),
            rrf_score=r.rrf_score,
            barrier_rank=r.barrier_rank,
            incident_rank=r.incident_rank,
            recommendations=incident_recommendations,
            pif_tags=pif_tags,
        ))

    return build_context(entries)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class PairContextResult:
    """Result of a dual-barrier RAG context build."""

    context_text: str
    conditioning_results: list
    target_results: list
    empty_retrievals: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------


def build_pair_context(
    conditioning_barrier: dict[str, Any],
    target_barrier: dict[str, Any],
    rag_agent: RAGAgent,
    incident_context: dict[str, Any] | None = None,
) -> PairContextResult:
    """Build merged RAG context for a (conditioning, target) barrier pair.

    Runs two separate RAGAgent.explain() calls — one per barrier — with a
    shared incident_query composed from incident_context. Does NOT call an LLM.
    Post-filters both result sets to oil & gas incidents only.

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

    # Domain filter: keep only oil & gas incidents in both result sets
    incident_meta_store: dict[str, Any] = getattr(rag_agent, "_incident_meta", {})

    pre_cond = len(conditioning_result.results)
    pre_tgt = len(target_result.results)

    filtered_cond = [
        r for r in conditioning_result.results
        if _is_oil_gas_incident(r.incident_id, incident_meta_store)
    ]
    filtered_tgt = [
        r for r in target_result.results
        if _is_oil_gas_incident(r.incident_id, incident_meta_store)
    ]

    removed_cond = pre_cond - len(filtered_cond)
    removed_tgt = pre_tgt - len(filtered_tgt)
    if removed_cond or removed_tgt:
        logger.debug(
            "Domain filter removed %d conditioning / %d target results for pair (%s / %s)",
            removed_cond,
            removed_tgt,
            conditioning_barrier.get("control_id", "?"),
            target_barrier.get("control_id", "?"),
        )

    # Per-incident dedup: keep highest-RRF result per incident_id
    pre_dedup_cond = len(filtered_cond)
    pre_dedup_tgt = len(filtered_tgt)
    filtered_cond = _dedup_by_incident(filtered_cond)
    filtered_tgt = _dedup_by_incident(filtered_tgt)
    deduped_cond = pre_dedup_cond - len(filtered_cond)
    deduped_tgt = pre_dedup_tgt - len(filtered_tgt)
    if deduped_cond or deduped_tgt:
        logger.debug(
            "Incident dedup removed %d conditioning / %d target duplicates for pair (%s / %s)",
            deduped_cond,
            deduped_tgt,
            conditioning_barrier.get("control_id", "?"),
            target_barrier.get("control_id", "?"),
        )

    # Detect empty retrievals after domain filter
    empty_retrievals: list[str] = []
    if not filtered_cond:
        empty_retrievals.append("conditioning")
    if not filtered_tgt:
        empty_retrievals.append("target")

    if empty_retrievals:
        logger.warning(
            "Empty RAG retrievals after domain filter for pair (%s / %s): %s",
            conditioning_barrier.get("control_id", "?"),
            target_barrier.get("control_id", "?"),
            empty_retrievals,
        )

    # Build merged context text.
    # When filtering removed results, rebuild from the filtered set so the LLM
    # prompt never contains non-oil-gas incident text. When nothing was removed,
    # use the pre-built context_text from RAGAgent.explain() directly (faster,
    # and preserves the original text for test stubs that lack real metadata).
    if removed_cond or deduped_cond:
        conditioning_body = _rebuild_context_for_filtered(filtered_cond, rag_agent) or _NO_RESULTS_SENTINEL
    else:
        conditioning_body = conditioning_result.context_text or _NO_RESULTS_SENTINEL

    if removed_tgt or deduped_tgt:
        target_body = _rebuild_context_for_filtered(filtered_tgt, rag_agent) or _NO_RESULTS_SENTINEL
    else:
        target_body = target_result.context_text or _NO_RESULTS_SENTINEL

    context_text = (
        f"## Conditioning Barrier — Similar Failures\n\n{conditioning_body}\n\n"
        f"## Target Barrier — Similar Failures\n\n{target_body}"
    )

    return PairContextResult(
        context_text=context_text,
        conditioning_results=filtered_cond,
        target_results=filtered_tgt,
        empty_retrievals=empty_retrievals,
    )
