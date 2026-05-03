"""Assemble retrieval results into structured LLM context text."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.rag.config import MAX_CONTEXT_CHARS

import logging

logger = logging.getLogger(__name__)


@dataclass
class ContextEntry:
    """A single retrieval result with all context fields."""

    incident_id: str
    control_id: str
    barrier_name: str
    barrier_family: str
    side: str
    barrier_status: str
    barrier_role: str
    lod_basis: str
    barrier_failed_human: bool
    human_contribution_value: str
    supporting_text: list[str]
    incident_summary: str
    rrf_score: float
    barrier_rank: int
    incident_rank: int
    recommendations: list[str] = field(default_factory=list)
    pif_tags: dict[str, list[str]] | None = None


def extract_pif_tags(incident: dict[str, Any]) -> dict[str, list[str]] | None:
    """Return negative PIF factors grouped by category.

    Returns {'people': [...], 'work': [...], 'organisation': [...]} where each
    list contains factor names with _value == 'negative'. Returns None if no
    negative PIFs are present.
    """
    pifs = incident.get("pifs") or {}
    out: dict[str, list[str]] = {}
    for category in ("people", "work", "organisation"):
        cat = pifs.get(category) or {}
        negatives = sorted(
            k.replace("_value", "")
            for k, v in cat.items()
            if k.endswith("_value") and v == "negative"
        )
        if negatives:
            out[category] = negatives
    return out or None


def _format_entry(entry: ContextEntry, result_num: int) -> str:
    """Format a single result entry."""
    evidence_lines = "\n".join(f'- "{t}"' for t in entry.supporting_text) if entry.supporting_text else "- N/A"
    human_failed = "Yes" if entry.barrier_failed_human else "No"

    rec_lines = ""
    if entry.recommendations:
        rec_text = "\n".join(f"- {r}" for r in entry.recommendations)
        rec_lines = f"**Recommendations:**\n{rec_text}\n"

    pif_block = ""
    if entry.pif_tags:
        pif_lines = []
        for cat in ("people", "work", "organisation"):
            factors = entry.pif_tags.get(cat)
            if factors:
                names = ", ".join(f.replace("_", " ") for f in factors)
                pif_lines.append(f"- {cat.title()}: {names}")
        if pif_lines:
            pif_block = "**Performance Influencing Factors (negative):**\n" + "\n".join(pif_lines) + "\n"

    return (
        f"### Result {result_num} (RRF: {entry.rrf_score:.4f}, "
        f"Barrier Rank: {entry.barrier_rank}, Incident Rank: {entry.incident_rank})\n"
        f"**Barrier:** {entry.barrier_name}\n"
        f"**Family:** {entry.barrier_family} | Side: {entry.side} | Status: {entry.barrier_status}\n"
        f"**Role:** {entry.barrier_role}\n"
        f"**LOD Basis:** {entry.lod_basis}\n"
        f"**Human Failed:** {human_failed} | Human Contribution: {entry.human_contribution_value or 'N/A'}\n"
        f"**Evidence:**\n{evidence_lines}\n\n"
        f"**Parent Incident:** {entry.incident_id}\n"
        f"**Incident Summary:** {entry.incident_summary}\n"
        f"{rec_lines}"
        f"{pif_block}"
    )


def build_context(
    entries: list[ContextEntry],
    max_context_chars: int = MAX_CONTEXT_CHARS,
) -> str:
    """Build structured context text from retrieval results.

    Drops results from the bottom of the ranked list if the total
    context exceeds max_context_chars.
    """
    if not entries:
        return "## Similar Barrier Failures\n\nNo similar barrier failures found."

    header = "## Similar Barrier Failures\n\n"
    parts: list[str] = []
    total_len = len(header)

    for i, entry in enumerate(entries, start=1):
        block = _format_entry(entry, i)
        if total_len + len(block) > max_context_chars and parts:
            break
        parts.append(block)
        total_len += len(block)

    return header + "\n---\n".join(parts)
