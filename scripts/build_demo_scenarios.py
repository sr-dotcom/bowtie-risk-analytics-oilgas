#!/usr/bin/env python3
"""Generate demo-scenario JSON fixtures for S05 frontend.

Selects one incident per source_agency (BSEE, CSB, UNKNOWN) from
``data/models/cascading_input/barrier_model_dataset_base_v3.csv`` using
R019 constraints:
  - ≥4 controls after base_v3 LoD lookup
  - both prevention AND mitigation present
  - no lod_industry_standard == 'Other'
  - no lod_numeric == 99

Candidate agency is resolved by joining incident_id → source_agency from
``data/processed/flat_incidents_combined.csv`` (flat takes priority over base_v3).

LoD fields (lod_industry_standard, lod_numeric) sourced EXCLUSIVELY from
base_v3.csv by (incident_id, control_id) lookup — no inline map, no fallback.

Per-candidate accept/reject decisions are printed to stdout for audit trail.
Raises RuntimeError if any agency yields zero R019-passing candidates.

Usage:
    python scripts/build_demo_scenarios.py
    python scripts/build_demo_scenarios.py --out-dir /tmp/scenarios
    python scripts/build_demo_scenarios.py --base-v3 path/to/base_v3.csv
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Optional

import pandas as pd

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
INCIDENTS_DIR = PROJECT_ROOT / "data" / "structured" / "incidents" / "schema_v2_3"
BASE_V3_CSV = PROJECT_ROOT / "data" / "models" / "cascading_input" / "barrier_model_dataset_base_v3.csv"
FLAT_INCIDENTS_CSV = PROJECT_ROOT / "data" / "processed" / "flat_incidents_combined.csv"
DEFAULT_OUT_DIR = PROJECT_ROOT / "data" / "demo_scenarios"

AGENCIES = ("BSEE", "CSB", "UNKNOWN")

BARRIER_STATUS_MAP: dict[str, str] = {
    "worked": "effective",
    "active": "effective",
    "degraded": "degraded",
    "failed": "ineffective",
    "not_installed": "ineffective",
    "bypassed": "ineffective",
    "unknown": "status_unknown",
}


def _sanitize_id(s: str) -> str:
    """Replace non-filesystem-safe chars with underscores."""
    return re.sub(r"[^A-Za-z0-9._\-]", "_", s).strip("_")


def _any_pif_mentioned(pifs: dict) -> bool:
    return any(
        v
        for cat in pifs.values()
        if isinstance(cat, dict)
        for k, v in cat.items()
        if k.endswith("_mentioned") and v is True
    )


def _pif_context(pifs: dict) -> dict:
    """Return only PIFs with _mentioned=True, grouped by category."""
    result: dict[str, dict] = {}
    for cat_name, cat in pifs.items():
        if not isinstance(cat, dict):
            continue
        mentioned = {
            k[:-10]: v  # strip '_mentioned' suffix
            for k, v in cat.items()
            if k.endswith("_mentioned") and v is True
        }
        result[cat_name] = mentioned
    return result


def _build_scenario(
    inc_id: str,
    agency: str,
    json_data: dict,
    lod_lookup: dict[tuple[str, str], dict],
) -> tuple[Optional[dict], Optional[str]]:
    """Build a scenario dict or return (None, reject_reason) if R019 fails."""
    controls_json = json_data.get("bowtie", {}).get("controls", [])

    valid_controls: list[tuple[dict, str, int]] = []
    for c in controls_json:
        cid = c["control_id"]
        key = (inc_id, cid)
        if key not in lod_lookup:
            print(f"  skip  {cid}: not in base_v3")
            continue
        row = lod_lookup[key]
        lod_std = row["lod_industry_standard"]
        lod_num = row["lod_numeric"]
        if lod_std == "Other":
            print(f"  skip  {cid}: lod_industry_standard='Other'")
            continue
        if lod_num == 99:
            print(f"  skip  {cid}: lod_numeric=99")
            continue
        valid_controls.append((c, lod_std, int(lod_num) if pd.notna(lod_num) else None))

    if len(valid_controls) < 4:
        return None, f"only {len(valid_controls)} valid controls after base_v3 lookup, need ≥4"

    sides = {c["side"] for c, _, _ in valid_controls}
    if "prevention" not in sides:
        return None, "no prevention controls after base_v3 lookup"
    if "mitigation" not in sides:
        return None, "no mitigation controls after base_v3 lookup"

    event = json_data.get("event", {})
    context_raw = json_data.get("context", {})
    pifs = json_data.get("pifs", {})
    threats = json_data.get("bowtie", {}).get("threats", [])

    barriers = []
    for c, lod_std, lod_num in valid_controls:
        perf = c.get("performance", {}) or {}
        status = perf.get("barrier_status") or "unknown"
        barrier_condition = BARRIER_STATUS_MAP.get(status, "status_unknown")
        barriers.append(
            {
                "control_id": c["control_id"],
                "name": c.get("name"),
                "barrier_level": c["side"],
                "lod_industry_standard": lod_std,
                "lod_numeric": lod_num,
                "barrier_condition": barrier_condition,
                "barrier_type": c.get("barrier_type"),
                "barrier_role": c.get("barrier_role"),
                "linked_threat_ids": c.get("linked_threat_ids") or [],
                "description": c.get("barrier_role"),
                "line_of_defense": c.get("line_of_defense"),
            }
        )

    scenario_id = f"{agency.lower()}_{_sanitize_id(inc_id)}"
    scenario = {
        "scenario_id": scenario_id,
        "source_agency": agency,
        "incident_id": inc_id,
        "top_event": event.get("top_event"),
        "context": {
            "region": context_raw.get("region"),
            "operator": context_raw.get("operator"),
            "operating_phase": context_raw.get("operating_phase"),
            "materials": context_raw.get("materials"),
        },
        "barriers": barriers,
        "threats": [
            {
                "threat_id": t.get("threat_id"),
                "name": t.get("name"),
                "description": t.get("description"),
            }
            for t in threats
        ],
        "pif_context": _pif_context(pifs),
    }
    return scenario, None


def _select_for_agency(
    agency: str,
    candidate_ids: list[str],
    lod_lookup: dict[tuple[str, str], dict],
    incidents_dir: pathlib.Path,
) -> dict:
    """Return the first R019-passing scenario for this agency (preferred: has top_event + PIFs)."""
    fallback: Optional[dict] = None
    fallback_id: Optional[str] = None

    for inc_id in sorted(candidate_ids):
        json_path = incidents_dir / f"{inc_id}.json"
        if not json_path.exists():
            print(f"reject {inc_id}: JSON file not found at {json_path}")
            continue

        json_data = json.loads(json_path.read_text(encoding="utf-8-sig"))
        print(f"check  {inc_id}:")

        scenario, reject_reason = _build_scenario(inc_id, agency, json_data, lod_lookup)
        if scenario is None:
            print(f"reject {inc_id}: {reject_reason}")
            continue

        has_top_event = bool(scenario.get("top_event"))
        has_pif = _any_pif_mentioned(json_data.get("pifs", {}))

        if has_top_event and has_pif:
            print(f"accept {inc_id}: R019 ✓, top_event ✓, PIF ✓ (preferred)")
            return scenario

        if fallback is None:
            fallback = scenario
            fallback_id = inc_id
            print(f"accept {inc_id}: R019 ✓ (no top_event/PIF preference — held as fallback)")
        else:
            print(f"skip   {inc_id}: R019 ✓ but fallback already found ({fallback_id})")

    if fallback is not None:
        print(f"using fallback for {agency}: {fallback_id}")
        return fallback

    raise RuntimeError(
        f"No R019-passing candidates for agency '{agency}'. "
        "Check base_v3.csv / flat_incidents_combined.csv for schema drift."
    )


def build_demo_scenarios(
    base_v3_path: pathlib.Path = BASE_V3_CSV,
    flat_incidents_path: pathlib.Path = FLAT_INCIDENTS_CSV,
    incidents_dir: pathlib.Path = INCIDENTS_DIR,
    out_dir: pathlib.Path = DEFAULT_OUT_DIR,
) -> list[pathlib.Path]:
    """Generate 3 demo-scenario JSON fixtures, one per agency.

    Returns list of written file paths.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    base = pd.read_csv(base_v3_path)
    flat = pd.read_csv(flat_incidents_path)

    # Build LoD lookup keyed by (incident_id, control_id)
    lod_lookup: dict[tuple[str, str], dict] = {
        (row["incident_id"], row["control_id"]): {
            "lod_industry_standard": row["lod_industry_standard"],
            "lod_numeric": row["lod_numeric"],
        }
        for _, row in base[["incident_id", "control_id", "lod_industry_standard", "lod_numeric"]].iterrows()
    }

    # Resolve agency from flat_incidents (authoritative) joined to base_v3 incident pool
    flat_agency = (
        flat[["incident_id", "source_agency"]]
        .drop_duplicates("incident_id")
        .set_index("incident_id")["source_agency"]
    )
    base_incidents = base["incident_id"].unique()

    # Build per-agency candidate sets
    agency_candidates: dict[str, list[str]] = {a: [] for a in AGENCIES}
    for inc_id in base_incidents:
        agency = flat_agency.get(inc_id, "UNKNOWN")
        if agency not in AGENCIES:
            agency = "UNKNOWN"
        agency_candidates[agency].append(inc_id)

    print(f"Candidate pool sizes: { {a: len(v) for a, v in agency_candidates.items()} }")

    written: list[pathlib.Path] = []
    for agency in AGENCIES:
        print(f"\n=== Processing {agency} ({len(agency_candidates[agency])} candidates) ===")
        candidates = agency_candidates[agency]
        if not candidates:
            raise RuntimeError(
                f"Agency '{agency}' has zero incidents in base_v3 after flat_incidents join. "
                "Check source CSV consistency."
            )

        scenario = _select_for_agency(agency, candidates, lod_lookup, incidents_dir)
        inc_id_safe = _sanitize_id(scenario["incident_id"])
        filename = f"{agency.lower()}_{inc_id_safe}.json"
        out_path = out_dir / filename
        out_path.write_text(json.dumps(scenario, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote  {out_path}")
        written.append(out_path)

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-v3", type=pathlib.Path, default=BASE_V3_CSV, help="Path to barrier_model_dataset_base_v3.csv")
    parser.add_argument("--flat-incidents", type=pathlib.Path, default=FLAT_INCIDENTS_CSV, help="Path to flat_incidents_combined.csv")
    parser.add_argument("--incidents-dir", type=pathlib.Path, default=INCIDENTS_DIR, help="Directory of V2.3 JSON files")
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT_DIR, help="Output directory for fixtures")
    args = parser.parse_args()

    written = build_demo_scenarios(
        base_v3_path=args.base_v3,
        flat_incidents_path=args.flat_incidents,
        incidents_dir=args.incidents_dir,
        out_dir=args.out_dir,
    )
    print(f"\nDone — wrote {len(written)} scenario fixtures:")
    for p in written:
        print(f"  {p}")


if __name__ == "__main__":
    main()
