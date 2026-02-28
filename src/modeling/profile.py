"""Data reconnaissance profiler for barrier risk analytics.

Loads controls_combined.csv and flat_incidents_combined.csv, validates column
integrity, derives binary labels per the Model 1 and Model 2 definitions,
reports PIF sparsity and point-biserial correlations, and writes a
machine-readable JSON artifact for consumption by Phase 2 (Feature Engineering).

Usage::

    python -m src.modeling.profile           # writes to default REPORT_PATH
    python -m src.modeling.profile           # exit 0 on success, 1 on error
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import pointbiserialr

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants (importable by tests and Phase 2 code)
# ---------------------------------------------------------------------------

CONTROLS_CSV = Path("data/processed/controls_combined.csv")
INCIDENTS_CSV = Path("data/processed/flat_incidents_combined.csv")
REPORT_PATH = Path("data/models/evaluation/data_recon_report.json")

# The 12 PIF _mentioned boolean columns in flat_incidents_combined.csv.
# Order matches PeoplePifs, WorkPifs, OrganisationPifs field order.
PIF_MENTIONED_COLS: list[str] = [
    "incident__pifs__people__competence_mentioned",
    "incident__pifs__people__fatigue_mentioned",
    "incident__pifs__people__communication_mentioned",
    "incident__pifs__people__situational_awareness_mentioned",
    "incident__pifs__work__procedures_mentioned",
    "incident__pifs__work__workload_mentioned",
    "incident__pifs__work__time_pressure_mentioned",
    "incident__pifs__work__tools_equipment_mentioned",
    "incident__pifs__organisation__safety_culture_mentioned",
    "incident__pifs__organisation__management_of_change_mentioned",
    "incident__pifs__organisation__supervision_mentioned",
    "incident__pifs__organisation__training_mentioned",
]

# Warning thresholds for positive-class rate (per D-05).
POSITIVE_RATE_LOWER: float = 0.03
POSITIVE_RATE_UPPER: float = 0.25


# ---------------------------------------------------------------------------
# Helper: JSON serializer for numpy types
# ---------------------------------------------------------------------------

def _numpy_serializer(obj: Any) -> Any:
    """Convert numpy scalar/array types to Python-native JSON-serializable types."""
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# ---------------------------------------------------------------------------
# Main profiling function
# ---------------------------------------------------------------------------

def run_profile(
    controls_path: Path = CONTROLS_CSV,
    incidents_path: Path = INCIDENTS_CSV,
    out_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    """Run data reconnaissance profile and write JSON artifact.

    Loads both CSVs, validates column integrity, derives Model 1 and Model 2
    binary labels (excluding unknowns), computes PIF sparsity and point-biserial
    correlations, and writes a machine-readable JSON report.

    Args:
        controls_path: Path to controls_combined.csv.
        incidents_path: Path to flat_incidents_combined.csv.
        out_path: Output path for data_recon_report.json.

    Returns:
        Report dict (identical content to the written JSON).

    Raises:
        FileNotFoundError: If either CSV does not exist.
    """
    controls_path = Path(controls_path)
    incidents_path = Path(incidents_path)
    out_path = Path(out_path)

    # ------------------------------------------------------------------
    # Section A: Load CSVs
    # ------------------------------------------------------------------
    if not controls_path.exists():
        raise FileNotFoundError(
            f"Controls CSV not found: {controls_path}. "
            "Run: python -m src.pipeline build-combined-exports"
        )
    if not incidents_path.exists():
        raise FileNotFoundError(
            f"Incidents CSV not found: {incidents_path}. "
            "Run: python -m src.pipeline build-combined-exports"
        )

    controls = pd.read_csv(controls_path)
    incidents = pd.read_csv(incidents_path)
    logger.info("Loaded %d controls, %d incidents", len(controls), len(incidents))

    # ------------------------------------------------------------------
    # Section B: Controls column integrity
    # ------------------------------------------------------------------
    controls_null_counts: dict[str, int] = {
        col: int(n)
        for col, n in controls.isnull().sum().items()
        if n > 0
    }

    def _to_native_dict(series_counts: "pd.Series") -> dict[str, Any]:
        """Convert value_counts Series to native-Python dict."""
        return {str(k): int(v) for k, v in series_counts.items()}

    def _sorted_unique(series: "pd.Series") -> list[str]:
        return sorted([str(v) for v in series.dropna().unique()])

    controls_section: dict[str, Any] = {
        "path": str(controls_path),
        "total_rows": int(len(controls)),
        "columns": list(controls.columns),
        "null_counts": controls_null_counts,
        "barrier_status_distribution": _to_native_dict(
            controls["barrier_status"].value_counts()
        ),
        "side_values": _sorted_unique(controls["side"]),
        "barrier_type_values": _sorted_unique(controls["barrier_type"]),
        "line_of_defense_values": _sorted_unique(controls["line_of_defense"]),
    }
    if "source_agency" in controls.columns:
        controls_section["source_agency_values"] = _sorted_unique(
            controls["source_agency"]
        )

    # ------------------------------------------------------------------
    # Section C: Incidents column integrity
    # ------------------------------------------------------------------
    incidents_null_counts: dict[str, int] = {
        col: int(n)
        for col, n in incidents.isnull().sum().items()
        if n > 0
    }

    incidents_section: dict[str, Any] = {
        "path": str(incidents_path),
        "total_rows": int(len(incidents)),
        "columns": list(incidents.columns),
        "null_counts": incidents_null_counts,
        "unique_incident_ids": int(incidents["incident_id"].nunique()),
    }

    # ------------------------------------------------------------------
    # Section D: Join check
    # ------------------------------------------------------------------
    controls_ids: set[str] = set(controls["incident_id"].astype(str).unique())
    incidents_ids: set[str] = set(incidents["incident_id"].astype(str).unique())

    orphan_incidents: list[str] = sorted(incidents_ids - controls_ids)
    orphan_controls: list[str] = sorted(controls_ids - incidents_ids)

    join_check: dict[str, Any] = {
        "incident_ids_in_controls": int(len(controls_ids)),
        "incident_ids_in_incidents": int(len(incidents_ids)),
        "matched_ids": int(len(controls_ids & incidents_ids)),
        "orphan_incidents": orphan_incidents,
        "orphan_controls": orphan_controls,
    }

    # ------------------------------------------------------------------
    # Section E: Label derivation (per D-04)
    # ------------------------------------------------------------------
    mask_known = controls["barrier_status"] != "unknown"
    df_known = controls[mask_known].copy()
    training_eligible = int(len(df_known))
    excluded_unknown = int(len(controls) - len(df_known))

    # Model 1: barrier did not perform (broad signal)
    _did_not_perform = df_known["barrier_status"].isin(
        ["failed", "degraded", "not_installed", "bypassed"]
    )
    df_known["label_model1"] = _did_not_perform

    # Model 2: did not perform AND human factors contributed (narrow + PIFs)
    # NOTE: barrier_failed_human can be True/False or string "True"/"False"
    # Coerce to bool safely.
    _hf_raw = df_known["barrier_failed_human"]
    if _hf_raw.dtype == object:
        _hf_bool = _hf_raw.map(lambda v: str(v).strip().lower() == "true")
    else:
        _hf_bool = _hf_raw.astype(bool)
    df_known["label_model2"] = _did_not_perform & _hf_bool

    def _label_stats(
        label_col: "pd.Series",
        description: str,
    ) -> dict[str, Any]:
        n_positive = int(label_col.sum())
        positive_rate = float(n_positive / training_eligible) if training_eligible > 0 else 0.0
        warnings: list[str] = []
        if positive_rate < POSITIVE_RATE_LOWER:
            warnings.append(
                f"positive_rate {positive_rate:.3f} below lower threshold {POSITIVE_RATE_LOWER}"
            )
        if positive_rate > POSITIVE_RATE_UPPER:
            warnings.append(
                f"positive_rate {positive_rate:.3f} exceeds upper threshold {POSITIVE_RATE_UPPER}"
            )
        return {
            "description": description,
            "n_total": training_eligible,
            "n_positive": n_positive,
            "positive_rate": round(positive_rate, 6),
            "warnings": warnings,
        }

    labels_section: dict[str, Any] = {
        "training_eligible": training_eligible,
        "excluded_unknown": excluded_unknown,
        "model1": _label_stats(
            df_known["label_model1"],
            "barrier_status in {failed, degraded, not_installed, bypassed}",
        ),
        "model2": _label_stats(
            df_known["label_model2"],
            "did_not_perform AND barrier_failed_human == True",
        ),
    }

    # ------------------------------------------------------------------
    # Section F: PIF sparsity and correlations (per D-07)
    # ------------------------------------------------------------------
    # Merge training-eligible controls with incident-level PIF columns.
    pif_cols_present = [c for c in PIF_MENTIONED_COLS if c in incidents.columns]
    merged = df_known.merge(
        incidents[["incident_id"] + pif_cols_present],
        on="incident_id",
        how="left",
    )

    label1_arr = merged["label_model1"].astype(int).to_numpy()
    label2_arr = merged["label_model2"].astype(int).to_numpy()

    pif_report: dict[str, dict[str, float]] = {}
    for col in PIF_MENTIONED_COLS:
        short_name = col.split("__")[-1]  # e.g. "competence_mentioned"
        if col in merged.columns:
            pif_bool = merged[col].infer_objects(copy=False).fillna(False).astype(bool)
            sparsity = float(pif_bool.mean())
            pif_int = pif_bool.astype(int).to_numpy()

            # Point-biserial correlation; replace NaN if constant column.
            try:
                corr1, p1 = pointbiserialr(pif_int, label1_arr)
                corr1 = 0.0 if (corr1 != corr1) else float(corr1)  # NaN check
                p1 = 1.0 if (p1 != p1) else float(p1)
            except Exception:
                corr1, p1 = 0.0, 1.0

            try:
                corr2, p2 = pointbiserialr(pif_int, label2_arr)
                corr2 = 0.0 if (corr2 != corr2) else float(corr2)
                p2 = 1.0 if (p2 != p2) else float(p2)
            except Exception:
                corr2, p2 = 0.0, 1.0
        else:
            # Column missing from CSV — record zeros
            sparsity, corr1, p1, corr2, p2 = 0.0, 0.0, 1.0, 0.0, 1.0

        pif_report[short_name] = {
            "sparsity": round(sparsity, 6),
            "corr_model1": round(corr1, 6),
            "p_value_model1": round(p1, 6),
            "corr_model2": round(corr2, 6),
            "p_value_model2": round(p2, 6),
        }

    # ------------------------------------------------------------------
    # Section G: Assemble and write report
    # ------------------------------------------------------------------
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "controls": controls_section,
        "incidents": incidents_section,
        "join_check": join_check,
        "labels": labels_section,
        "pif_report": pif_report,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=_numpy_serializer)
    logger.info("Profile written to %s", out_path)

    # ------------------------------------------------------------------
    # Section H: Console output (per D-02, D-03)
    # ------------------------------------------------------------------
    _print_summary(report, training_eligible, excluded_unknown, controls, out_path)

    return report


# ---------------------------------------------------------------------------
# Console output helper
# ---------------------------------------------------------------------------

def _print_summary(
    report: dict[str, Any],
    training_eligible: int,
    excluded_unknown: int,
    controls: "pd.DataFrame",
    out_path: Path = REPORT_PATH,
) -> None:
    """Print a human-readable summary of the profiling results."""
    print()
    print("=" * 60)
    print("  Data Reconnaissance Profile")
    print("=" * 60)

    # Controls summary
    ctrl = report["controls"]
    print(f"\n[Controls]  {ctrl['total_rows']} total rows")
    print(f"  Training eligible : {training_eligible}")
    print(f"  Excluded (unknown): {excluded_unknown}")
    print()
    print("  barrier_status distribution:")
    for status, count in sorted(
        ctrl["barrier_status_distribution"].items(),
        key=lambda kv: kv[1],
        reverse=True,
    ):
        pct = 100.0 * count / ctrl["total_rows"]
        print(f"    {status:<20s}  {count:>5d}  ({pct:5.1f}%)")

    # Label distribution
    labels = report["labels"]
    print()
    print("[Labels]")
    for model_key in ("model1", "model2"):
        m = labels[model_key]
        print(
            f"  {model_key}: n_positive={m['n_positive']}/{m['n_total']}  "
            f"rate={m['positive_rate']:.4f}",
            end="",
        )
        if m["warnings"]:
            for w in m["warnings"]:
                print(f"  WARNING: {w}", end="")
        print()

    # PIF sparsity table (sorted by sparsity desc)
    pif_report = report["pif_report"]
    print()
    print(f"[PIF Sparsity & Correlations]  ({len(pif_report)} dimensions)")
    print(
        f"  {'PIF dimension':<42s}  {'sparsity':>8s}  {'corr_m1':>8s}  {'corr_m2':>8s}"
    )
    print("  " + "-" * 74)
    for short_name, entry in sorted(
        pif_report.items(), key=lambda kv: kv[1]["sparsity"], reverse=True
    ):
        print(
            f"  {short_name:<42s}  {entry['sparsity']:>8.4f}  "
            f"{entry['corr_model1']:>8.4f}  {entry['corr_model2']:>8.4f}"
        )

    # Join check
    jc = report["join_check"]
    print()
    print("[Join Check]")
    print(f"  Matched incident IDs: {jc['matched_ids']}")
    if jc["orphan_incidents"]:
        print(f"  Orphan incidents (in incidents but not controls): {len(jc['orphan_incidents'])}")
    if jc["orphan_controls"]:
        print(f"  Orphan controls (in controls but not incidents): {len(jc['orphan_controls'])}")

    print()
    print(f"  Report written to: {out_path}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        run_profile()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
