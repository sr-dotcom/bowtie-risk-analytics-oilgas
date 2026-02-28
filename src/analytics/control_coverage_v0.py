"""Control coverage + gaps analytics (v0) from Schema v2.3 flattened controls.

Inputs:
- Flat controls CSV produced by src.analytics.flatten.flatten_all()

Outputs:
- control_coverage_v0.csv: per-incident coverage metrics
- control_gaps_v0.csv: per-control gap rows
- gap_rollups_v0.csv: aggregated gap counts by key dimensions
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


GAP_STATUSES = {"failed", "bypassed", "not_installed", "unknown", ""}

def list_incident_ids_from_structured_dir(structured_dir: Path) -> list[str]:
    """Return incident_ids inferred from structured_json filenames."""
    if not structured_dir.exists():
        return []
    return sorted([p.stem for p in structured_dir.glob("*.json")])



@dataclass(frozen=True)
class CoverageOutputs:
    coverage_csv: Path
    gaps_csv: Path
    rollups_csv: Path


def _norm_status(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip().lower()
    return s


def compute_coverage_and_gaps_from_flat(
    flat_controls_csv: Path,
    out_dir: Path,
    structured_dir: Path | None = None,
) -> CoverageOutputs:
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(flat_controls_csv)

    # Normalize key columns
    df["barrier_status"] = df["barrier_status"].map(_norm_status)
    df["confidence"] = df.get("confidence", "").fillna("").astype(str).str.strip().str.lower()
    df["supporting_text_count"] = df.get("supporting_text_count", 0).fillna(0).astype(int)

    # Basic per-incident counts
    total = df.groupby("incident_id").size().rename("controls_total")

    # Count statuses
    status_counts = (
        df.pivot_table(
            index="incident_id",
            columns="barrier_status",
            values="control_id",
            aggfunc="count",
            fill_value=0,
        )
        .rename_axis(None, axis=1)
    )

    # Ensure expected status columns exist
    for col in ["active", "degraded", "failed", "not_installed", "bypassed", "unknown", ""]:
        if col not in status_counts.columns:
            status_counts[col] = 0

    # Evidence metrics
    with_text = (
        df.assign(_has_text=df["supporting_text_count"] > 0)
          .groupby("incident_id")["_has_text"].sum()
          .rename("controls_with_supporting_text")
    )
    high_conf = (
        df.assign(_high=df["confidence"] == "high")
          .groupby("incident_id")["_high"].sum()
          .rename("controls_with_high_confidence")
    )

    # Assemble coverage table
    cov = pd.concat([total, status_counts, with_text, high_conf], axis=1).fillna(0)

    # Ensure incidents with 0 controls are included (v0 expects one row per incident)
    if structured_dir is None:
        structured_dir = Path("data/structured/incidents/schema_v2_3")
    all_incidents = list_incident_ids_from_structured_dir(structured_dir)
    if all_incidents:
        cov = cov.reindex(all_incidents, fill_value=0)

    cov = cov.rename(columns={
        "": "blank_status",
        "active": "controls_active",
        "degraded": "controls_degraded",
        "failed": "controls_failed",
        "not_installed": "controls_not_installed",
        "bypassed": "controls_bypassed",
        "unknown": "controls_unknown",
    })

    # Coverage score v0: (active + 0.5*degraded) / total
    cov["coverage_score_v0"] = 0.0
    nonzero = cov["controls_total"] > 0
    cov.loc[nonzero, "coverage_score_v0"] = (
        (cov.loc[nonzero, "controls_active"] + 0.5 * cov.loc[nonzero, "controls_degraded"])
        / cov.loc[nonzero, "controls_total"]
    )

    cov = cov.reset_index().sort_values(["coverage_score_v0", "controls_total"], ascending=[True, False])

    # Build gaps table (row-level)
    df["is_gap_status"] = df["barrier_status"].isin(GAP_STATUSES)
    df["is_gap_evidence"] = df["supporting_text_count"] <= 0
    gaps = df[df["is_gap_status"] | df["is_gap_evidence"]].copy()

    # Keep a clean set of columns for gaps export (stable schema)
    keep_cols = [
        "incident_id",
        "control_id",
        "name",
        "side",
        "barrier_role",
        "barrier_type",
        "line_of_defense",
        "lod_basis",
        "barrier_status",
        "barrier_failed",
        "human_contribution_value",
        "barrier_failed_human",
        "confidence",
        "supporting_text_count",
    ]
    for c in keep_cols:
        if c not in gaps.columns:
            gaps[c] = ""
    gaps = gaps[keep_cols].sort_values(["incident_id", "barrier_status", "barrier_type", "name"])

    # Rollups: tidy schema (no NaNs)
    def _rollup(col: str, label: str) -> pd.DataFrame:
        g = (
            gaps.groupby(col)
                .size()
                .rename("gap_count")
                .reset_index()
                .sort_values("gap_count", ascending=False)
        )
        g.insert(0, "rollup", label)
        g.insert(1, "dimension", col)
        g = g.rename(columns={col: "value"})
        return g

    rollups = pd.concat([
        _rollup("barrier_type", "by_barrier_type"),
        _rollup("barrier_role", "by_barrier_role"),
        _rollup("side", "by_side"),
        _rollup("line_of_defense", "by_line_of_defense"),
        _rollup("name", "by_control_name"),
    ], ignore_index=True)
    # Write outputs
    coverage_csv = out_dir / "control_coverage_v0.csv"
    gaps_csv = out_dir / "control_gaps_v0.csv"
    rollups_csv = out_dir / "gap_rollups_v0.csv"

    cov.to_csv(coverage_csv, index=False)
    gaps.to_csv(gaps_csv, index=False)
    rollups.to_csv(rollups_csv, index=False)

    return CoverageOutputs(coverage_csv=coverage_csv, gaps_csv=gaps_csv, rollups_csv=rollups_csv)
