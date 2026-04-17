#!/usr/bin/env python3
"""Extract threat-barrier pairs from incident JSONs for Jeffrey's association mining.

Reads normalized_dfV3.csv (Patrick's base dataset) and the incident JSON files
referenced by each row's json_path. Produces a 1-to-N mapping of barriers to
threats, guaranteeing every barrier gets at least one threat.

Mapping strategy:
  1. EXPLICIT — barrier has linked_threat_ids in the JSON → use those
  2. SIDE-INFERRED — barrier has no linked_threat_ids:
       prevention barriers → all threats in that incident
       mitigation barriers → all threats in that incident
       (mitigation barriers relate to consequences, but threats flow through
        the top event to consequences, so all threats are relevant)
  3. TOP-EVENT-ONLY — incident has zero threats defined → create a
       synthetic "top_event" threat from the event info so the barrier
       still gets a row

Usage:
    python3 extract_threat_barrier_pairs.py                          # defaults
    python3 extract_threat_barrier_pairs.py --base normalized_dfV3.csv --out pairs.csv
    python3 extract_threat_barrier_pairs.py --project-root /path/to/repo

Output columns:
    incident_id, control_id, control_name, barrier_level, barrier_type,
    barrier_family, threat_id, threat_name, threat_description, mapping_method
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def load_incident_json(json_path: Path) -> dict:
    """Load and return a single incident JSON, handling BOM encoding."""
    raw = json_path.read_bytes()
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    return json.loads(raw)


def extract_threats(incident: dict) -> list[dict]:
    """Return list of {threat_id, name, description} from the bowtie."""
    bowtie = incident.get("bowtie", {})
    threats = bowtie.get("threats", [])
    return [
        {
            "threat_id": t.get("threat_id", ""),
            "name": t.get("name", "unknown"),
            "description": t.get("description", ""),
        }
        for t in threats
    ]


def extract_controls_with_links(incident: dict) -> dict[str, list[str]]:
    """Return {control_id: [linked_threat_ids]} for every control in the bowtie."""
    bowtie = incident.get("bowtie", {})
    controls = bowtie.get("controls", [])
    return {
        c.get("control_id", ""): c.get("linked_threat_ids", [])
        for c in controls
    }


def get_top_event_name(incident: dict) -> str:
    """Best-effort top-event name for the synthetic fallback threat."""
    event = incident.get("event", {})
    return (
        event.get("top_event")
        or event.get("event_description")
        or event.get("incident_type")
        or "Loss of Containment"
    )


# ── main logic ───────────────────────────────────────────────────────────────

def build_pairs(
    base_csv: Path,
    project_root: Path,
) -> tuple[list[dict], dict]:
    """Build threat-barrier pair rows from the base CSV + incident JSONs.

    Returns (pair_rows, stats_dict).
    """
    # Read base dataset
    with open(base_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        barriers = list(reader)
    log.info("Loaded %d barriers from %s", len(barriers), base_csv.name)

    # Group barriers by incident (preserves order)
    incidents: dict[str, list[dict]] = {}
    for row in barriers:
        iid = row["incident_id"]
        incidents.setdefault(iid, []).append(row)
    log.info("Unique incidents: %d", len(incidents))

    # Cache loaded JSONs
    json_cache: dict[str, dict] = {}
    pair_rows: list[dict] = []
    stats = {
        "explicit": 0,
        "side_inferred": 0,
        "top_event_only": 0,
        "json_missing": 0,
        "json_errors": 0,
        "total_barriers": len(barriers),
        "total_pairs": 0,
    }

    for iid, barrier_rows in incidents.items():
        # Resolve JSON path — try relative to project root
        raw_json_path = barrier_rows[0]["json_path"].strip()
        json_path = project_root / raw_json_path
        if not json_path.exists():
            # Try alternative path patterns
            alt = project_root / "data" / "structured" / "incidents" / "schema_v2_3" / Path(raw_json_path).name
            if alt.exists():
                json_path = alt
            else:
                log.warning("JSON not found for %s: %s", iid, json_path)
                stats["json_missing"] += 1
                # Still produce rows with synthetic threat so no barrier is dropped
                for br in barrier_rows:
                    pair_rows.append({
                        "incident_id": iid,
                        "control_id": br["control_id"],
                        "control_name": br["control_name_raw"],
                        "barrier_level": br["barrier_level"],
                        "barrier_type": br["barrier_type"],
                        "barrier_family": br["barrier_family"],
                        "threat_id": "T-UNKNOWN",
                        "threat_name": "Unknown (JSON not found)",
                        "threat_description": "",
                        "mapping_method": "json_missing",
                    })
                    stats["top_event_only"] += 1
                continue

        # Load JSON (cached)
        if iid not in json_cache:
            try:
                json_cache[iid] = load_incident_json(json_path)
            except Exception as e:
                log.error("Failed to load %s: %s", json_path, e)
                stats["json_errors"] += 1
                for br in barrier_rows:
                    pair_rows.append({
                        "incident_id": iid,
                        "control_id": br["control_id"],
                        "control_name": br["control_name_raw"],
                        "barrier_level": br["barrier_level"],
                        "barrier_type": br["barrier_type"],
                        "barrier_family": br["barrier_family"],
                        "threat_id": "T-ERROR",
                        "threat_name": f"Error loading JSON: {e}",
                        "threat_description": "",
                        "mapping_method": "json_error",
                    })
                continue

        incident = json_cache[iid]
        threats = extract_threats(incident)
        control_links = extract_controls_with_links(incident)
        top_event = get_top_event_name(incident)

        for br in barrier_rows:
            cid = br["control_id"]
            linked_ids = control_links.get(cid, [])

            if linked_ids and threats:
                # Strategy 1: EXPLICIT — barrier has linked_threat_ids
                threat_lookup = {t["threat_id"]: t for t in threats}
                matched = False
                for tid in linked_ids:
                    t = threat_lookup.get(tid)
                    if t:
                        pair_rows.append({
                            "incident_id": iid,
                            "control_id": cid,
                            "control_name": br["control_name_raw"],
                            "barrier_level": br["barrier_level"],
                            "barrier_type": br["barrier_type"],
                            "barrier_family": br["barrier_family"],
                            "threat_id": t["threat_id"],
                            "threat_name": t["name"],
                            "threat_description": t.get("description", ""),
                            "mapping_method": "explicit",
                        })
                        stats["explicit"] += 1
                        matched = True
                    else:
                        log.debug(
                            "Barrier %s/%s links to threat %s but threat not in bowtie",
                            iid, cid, tid,
                        )

                if matched:
                    continue
                # Fall through to inference if none of the linked IDs matched

            if threats:
                # Strategy 2: SIDE-INFERRED — no explicit link, assign all threats
                for t in threats:
                    pair_rows.append({
                        "incident_id": iid,
                        "control_id": cid,
                        "control_name": br["control_name_raw"],
                        "barrier_level": br["barrier_level"],
                        "barrier_type": br["barrier_type"],
                        "barrier_family": br["barrier_family"],
                        "threat_id": t["threat_id"],
                        "threat_name": t["name"],
                        "threat_description": t.get("description", ""),
                        "mapping_method": "side_inferred",
                    })
                    stats["side_inferred"] += 1
            else:
                # Strategy 3: TOP-EVENT-ONLY — incident has no threats at all
                pair_rows.append({
                    "incident_id": iid,
                    "control_id": cid,
                    "control_name": br["control_name_raw"],
                    "barrier_level": br["barrier_level"],
                    "barrier_type": br["barrier_type"],
                    "barrier_family": br["barrier_family"],
                    "threat_id": "T-TOP",
                    "threat_name": top_event,
                    "threat_description": "Synthetic — incident had no explicit threats",
                    "mapping_method": "top_event_only",
                })
                stats["top_event_only"] += 1

    stats["total_pairs"] = len(pair_rows)
    return pair_rows, stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract threat-barrier pairs for Jeffrey's association mining model.",
    )
    parser.add_argument(
        "--base",
        default="normalized_dfV3.csv",
        help="Path to Patrick's base barrier dataset (default: normalized_dfV3.csv)",
    )
    parser.add_argument(
        "--out",
        default="data/exports/barrier_threat_pairs.csv",
        help="Output CSV path (default: data/exports/barrier_threat_pairs.csv)",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory (default: current directory)",
    )
    args = parser.parse_args()

    base_csv = Path(args.base)
    out_csv = Path(args.out)
    project_root = Path(args.project_root)

    if not base_csv.exists():
        log.error("Base CSV not found: %s", base_csv)
        sys.exit(1)

    pair_rows, stats = build_pairs(base_csv, project_root)

    # Verify guarantee: every (incident_id, control_id) in base has ≥1 pair
    with open(base_csv, newline="", encoding="utf-8-sig") as f:
        base_keys = {(r["incident_id"], r["control_id"]) for r in csv.DictReader(f)}
    pair_keys = {(r["incident_id"], r["control_id"]) for r in pair_rows}
    missing = base_keys - pair_keys
    if missing:
        log.error("GUARANTEE VIOLATED: %d barriers have no threat pair!", len(missing))
        for iid, cid in sorted(missing)[:10]:
            log.error("  Missing: %s / %s", iid, cid)
        sys.exit(1)

    # Write output
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "incident_id", "control_id", "control_name",
        "barrier_level", "barrier_type", "barrier_family",
        "threat_id", "threat_name", "threat_description",
        "mapping_method",
    ]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(pair_rows)

    # Report
    log.info("─" * 60)
    log.info("RESULTS")
    log.info("─" * 60)
    log.info("  Base barriers:      %d", stats["total_barriers"])
    log.info("  Output pairs:       %d", stats["total_pairs"])
    log.info("  Explicit links:     %d", stats["explicit"])
    log.info("  Side-inferred:      %d", stats["side_inferred"])
    log.info("  Top-event-only:     %d", stats["top_event_only"])
    log.info("  JSON missing:       %d", stats["json_missing"])
    log.info("  JSON errors:        %d", stats["json_errors"])
    log.info("  Coverage:           %d / %d barriers (%.1f%%)",
             len(pair_keys), len(base_keys),
             100.0 * len(pair_keys) / len(base_keys) if base_keys else 0)
    log.info("─" * 60)
    log.info("Written to: %s", out_csv)


if __name__ == "__main__":
    main()
