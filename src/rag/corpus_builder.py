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


# ── PIF extraction ────────────────────────────────────────────────

PIF_FIELDS = [
    ("pif_competence", "people", "competence_mentioned"),
    ("pif_fatigue", "people", "fatigue_mentioned"),
    ("pif_communication", "people", "communication_mentioned"),
    ("pif_situational_awareness", "people", "situational_awareness_mentioned"),
    ("pif_procedures", "work", "procedures_mentioned"),
    ("pif_workload", "work", "workload_mentioned"),
    ("pif_time_pressure", "work", "time_pressure_mentioned"),
    ("pif_tools_equipment", "work", "tools_equipment_mentioned"),
    ("pif_safety_culture", "organisation", "safety_culture_mentioned"),
    ("pif_management_of_change", "organisation", "management_of_change_mentioned"),
    ("pif_supervision", "organisation", "supervision_mentioned"),
    ("pif_training", "organisation", "training_mentioned"),
]


def _extract_pifs(pifs: dict[str, Any]) -> dict[str, bool]:
    """Extract 12 PIF mentioned flags from incident pifs dict."""
    result: dict[str, bool] = {}
    for col_name, category, field in PIF_FIELDS:
        result[col_name] = bool(pifs.get(category, {}).get(field, False))
    return result


# ── Column definitions ────────────────────────────────────────────

BARRIER_DOC_COLUMNS = [
    "incident_id",
    "control_id",
    "barrier_role_match_text",
    "barrier_family",
    "barrier_type",
    "side",
    "line_of_defense",
    "barrier_status",
    "barrier_failed",
    "barrier_failed_human",
    "human_contribution_value",
    "pif_competence",
    "pif_fatigue",
    "pif_communication",
    "pif_situational_awareness",
    "pif_procedures",
    "pif_workload",
    "pif_time_pressure",
    "pif_tools_equipment",
    "pif_safety_culture",
    "pif_management_of_change",
    "pif_supervision",
    "pif_training",
    "supporting_text",
    "confidence",
    "incident_summary",
]

INCIDENT_DOC_COLUMNS = [
    "incident_id",
    "incident_embed_text",
    "top_event",
    "incident_type",
    "operating_phase",
    "materials",
    "region",
    "operator",
    "summary",
    "recommendations",
]


# ── Builders ──────────────────────────────────────────────────────


def _read_incident_json(path: Path) -> dict[str, Any] | None:
    """Read a V2.3 JSON file, handling BOM encoding."""
    try:
        text = path.read_text(encoding="utf-8-sig")
        return json.loads(text)
    except Exception as e:
        logger.error("Failed to read %s: %s", path.name, e)
        return None


def build_barrier_documents(json_dir: Path, out_csv: Path) -> int:
    """Build barrier document table from V2.3 JSON files.

    Returns the number of barrier rows written.
    """
    json_files = sorted(json_dir.glob("*.json"))
    if not json_files:
        logger.warning("No JSON files found in %s", json_dir)
        return 0

    rows: list[dict[str, Any]] = []
    for jf in json_files:
        incident = _read_incident_json(jf)
        if incident is None:
            continue

        incident_id = incident.get("incident_id", "unknown")
        pifs = incident.get("pifs", {})
        pif_flags = _extract_pifs(pifs)
        summary = incident.get("event", {}).get("summary", "")

        for ctrl in incident.get("bowtie", {}).get("controls", []):
            perf = ctrl.get("performance", {})
            human = ctrl.get("human", {})
            evidence = ctrl.get("evidence", {})

            name = ctrl.get("name", "")
            barrier_role = ctrl.get("barrier_role", "")
            lod_basis = ctrl.get("lod_basis")
            side = ctrl.get("side", "unknown")
            barrier_type = ctrl.get("barrier_type", "unknown")

            row: dict[str, Any] = {
                "incident_id": incident_id,
                "control_id": ctrl.get("control_id", ""),
                "barrier_role_match_text": compose_barrier_text(
                    name, barrier_role, lod_basis
                ),
                "barrier_family": assign_barrier_family(
                    name, barrier_role, side, barrier_type
                ),
                "barrier_type": barrier_type,
                "side": side,
                "line_of_defense": ctrl.get("line_of_defense", "unknown"),
                "barrier_status": perf.get("barrier_status", "unknown"),
                "barrier_failed": perf.get("barrier_failed", False),
                "barrier_failed_human": human.get("barrier_failed_human", False),
                "human_contribution_value": human.get(
                    "human_contribution_value", ""
                ),
                "supporting_text": json.dumps(
                    evidence.get("supporting_text", [])
                ),
                "confidence": evidence.get("confidence", "low"),
                "incident_summary": summary,
            }
            row.update(pif_flags)
            rows.append(row)

    if not rows:
        logger.warning("No controls found across incidents in %s", json_dir)
        return 0

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BARRIER_DOC_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Wrote %d barrier document rows to %s", len(rows), out_csv)
    return len(rows)


def build_incident_documents(json_dir: Path, out_csv: Path) -> int:
    """Build incident document table from V2.3 JSON files.

    Returns the number of incident rows written.
    """
    json_files = sorted(json_dir.glob("*.json"))
    if not json_files:
        logger.warning("No JSON files found in %s", json_dir)
        return 0

    rows: list[dict[str, Any]] = []
    for jf in json_files:
        incident = _read_incident_json(jf)
        if incident is None:
            continue

        ctx = incident.get("context", {})
        evt = incident.get("event", {})
        materials = ctx.get("materials", [])
        if not isinstance(materials, list):
            materials = []

        rows.append({
            "incident_id": incident.get("incident_id", "unknown"),
            "incident_embed_text": compose_incident_text(
                top_event=evt.get("top_event", "unknown"),
                incident_type=evt.get("incident_type", "unknown"),
                operating_phase=ctx.get("operating_phase", "unknown"),
                materials=materials,
                summary=evt.get("summary", ""),
            ),
            "top_event": evt.get("top_event", "unknown"),
            "incident_type": evt.get("incident_type", "unknown"),
            "operating_phase": ctx.get("operating_phase", "unknown"),
            "materials": json.dumps(materials),
            "region": ctx.get("region", "unknown"),
            "operator": ctx.get("operator", "unknown"),
            "summary": evt.get("summary", ""),
            "recommendations": json.dumps(evt.get("recommendations", [])),
        })

    if not rows:
        logger.warning("No incidents found in %s", json_dir)
        return 0

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=INCIDENT_DOC_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Wrote %d incident document rows to %s", len(rows), out_csv)
    return len(rows)
