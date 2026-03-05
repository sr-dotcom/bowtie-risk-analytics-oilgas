# src/rag/corpus_builder.py
"""Build RAG retrieval document tables from V2.3 incident JSON files."""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from scripts.association_mining.event_barrier_normalization import (
    normalize_for_family,
    _QUADRANT_DISPATCH,
)

logger = logging.getLogger(__name__)

# ── Text composition ──────────────────────────────────────────────


def compose_barrier_text(
    name: str, barrier_role: str, lod_basis: str | None
) -> str:
    """Compose structured barrier embedding text."""
    return (
        f"Barrier: {name}\n"
        f"Role: {barrier_role}\n"
        f"LOD Basis: {lod_basis or 'N/A'}"
    )


def compose_incident_text(
    top_event: str,
    incident_type: str,
    operating_phase: str,
    materials: list[str],
    summary: str,
) -> str:
    """Compose structured incident embedding text."""
    materials_str = ", ".join(materials) if materials else "N/A"
    return (
        f"Top Event: {top_event}\n"
        f"Incident Type: {incident_type}\n"
        f"Operating Phase: {operating_phase}\n"
        f"Materials: {materials_str}\n"
        f"Summary: {summary}"
    )


# ── Barrier family assignment ─────────────────────────────────────


def assign_barrier_family(
    name: str, barrier_role: str, side: str, barrier_type: str
) -> str:
    """Assign a barrier family using the normalization taxonomy.

    Uses the rule-based keyword matching from
    scripts/association_mining/event_barrier_normalization.py.
    """
    norm_text = normalize_for_family(f"{name} {barrier_role}")
    side_norm = side.strip().lower()
    type_norm = barrier_type.strip().lower()

    dispatch_key = (side_norm, type_norm)
    assign_fn = _QUADRANT_DISPATCH.get(dispatch_key)
    if assign_fn is not None:
        return assign_fn(norm_text)
    return f"other_{type_norm}"
