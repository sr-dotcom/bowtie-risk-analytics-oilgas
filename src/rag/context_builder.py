"""Assemble retrieval results into structured LLM context text."""
from __future__ import annotations

from dataclasses import dataclass


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


def _format_entry(entry: ContextEntry, result_num: int) -> str:
    """Format a single result entry."""
    evidence_lines = "\n".join(f'- "{t}"' for t in entry.supporting_text) if entry.supporting_text else "- N/A"
    human_failed = "Yes" if entry.barrier_failed_human else "No"

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
    )


def build_context(
    entries: list[ContextEntry],
    max_context_chars: int = 8000,
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
