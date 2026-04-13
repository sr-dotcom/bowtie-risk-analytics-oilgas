"""In-memory coercions to normalise raw LLM output to canonical Schema v2.3.

Canonical V2.3 field values (as validated by IncidentV23):
  control.side            : "prevention" | "mitigation"
  control.line_of_defense : "1st" | "2nd" | "3rd" | "recovery" | "unknown"
  control.performance.barrier_status : "active" | "degraded" | "failed" |
                                        "bypassed" | "not_installed" | "unknown"

LLMs sometimes emit the older wire names ("left"/"right", integer LODs,
"worked" etc.).  This module normalises those before the payload is written
to disk, so all stored files are schema-valid without a separate convert-schema
pass.
"""
from __future__ import annotations

from collections import Counter
from typing import Any


def normalize_v23_payload(payload: dict[str, Any]) -> dict[str, int]:
    """Apply in-memory coercions to make a payload conform to Schema v2.3.

    Mutates *payload* in-place and returns a counter dict of coercions applied.
    """
    counts: Counter[str] = Counter()

    # 1) event.incident_type -> str
    event = payload.get("event")
    if isinstance(event, dict):
        it = event.get("incident_type")
        if isinstance(it, list):
            event["incident_type"] = it[0] if len(it) == 1 else "; ".join(str(x) for x in it)
            counts["incident_type_list_to_str"] += 1
        elif it is None or (isinstance(it, str) and not it.strip()):
            event["incident_type"] = "unknown"
            counts["incident_type_empty_to_unknown"] += 1
        elif not isinstance(it, str):
            event["incident_type"] = str(it)
            counts["incident_type_to_str"] += 1

    # 2-5) bowtie.controls[]
    SIDE_MAP = {
        "left": "prevention", "prevention": "prevention", "prevent": "prevention",
        "right": "mitigation", "mitigation": "mitigation", "mitigate": "mitigation", "recovery": "mitigation",
    }
    LOD_INT_MAP = {1: "1st", 2: "2nd", 3: "3rd", 4: "recovery"}
    LOD_ALLOWED = {"1st", "2nd", "3rd", "recovery", "unknown"}
    BS_ALLOWED = {"active", "degraded", "failed", "bypassed", "not_installed", "unknown"}
    BS_SYNONYM: dict[str, str] = {
        "ok": "active", "effective": "active", "in_place": "active",
        "in place": "active", "installed": "active", "worked": "active",
        "partial": "degraded", "weak": "degraded",
        "broken": "failed",
        "not installed": "not_installed", "not_installed": "not_installed",
        "missing": "not_installed",
        "none": "unknown", "na": "unknown", "n-a": "unknown", "n/a": "unknown",
    }

    # Remap generic 'id' keys to typed ID fields in bowtie sub-lists
    bowtie = payload.get("bowtie", {})
    for item in bowtie.get("hazards", []):
        if "id" in item and "hazard_id" not in item:
            item["hazard_id"] = item.pop("id")
            counts["hazard_id_remapped"] += 1
    for item in bowtie.get("threats", []):
        if "id" in item and "threat_id" not in item:
            item["threat_id"] = item.pop("id")
            counts["threat_id_remapped"] += 1
    for item in bowtie.get("consequences", []):
        if "id" in item and "consequence_id" not in item:
            item["consequence_id"] = item.pop("id")
            counts["consequence_id_remapped"] += 1

    controls = payload.get("bowtie", {}).get("controls", [])
    for ctrl in controls:
        # side
        raw_side = str(ctrl.get("side", "")).strip().lower()
        mapped_side = SIDE_MAP.get(raw_side)
        if mapped_side:
            if ctrl.get("side") != mapped_side:
                counts["side_mapped"] += 1
            ctrl["side"] = mapped_side
        else:
            ctrl["side"] = "prevention"
            counts["side_default_prevention"] += 1

        # line_of_defense
        raw_lod = ctrl.get("line_of_defense")
        if isinstance(raw_lod, int):
            ctrl["line_of_defense"] = LOD_INT_MAP.get(raw_lod, "unknown")
            counts["lod_int_to_enum"] += 1
        elif isinstance(raw_lod, str):
            stripped = raw_lod.strip()
            if stripped.isdigit():
                ctrl["line_of_defense"] = LOD_INT_MAP.get(int(stripped), "unknown")
                counts["lod_strnum_to_enum"] += 1
            elif stripped not in LOD_ALLOWED:
                ctrl["line_of_defense"] = "unknown"
                counts["lod_unknown"] += 1
        else:
            ctrl["line_of_defense"] = "unknown"
            counts["lod_missing"] += 1

        # performance.barrier_status  (create default dict if null/missing)
        perf = ctrl.get("performance")
        if not isinstance(perf, dict):
            ctrl["performance"] = {}
            perf = ctrl["performance"]
            counts["performance_created"] += 1
        if isinstance(perf, dict):
            raw_bs = perf.get("barrier_status")
            if isinstance(raw_bs, str):
                bs_lower = raw_bs.strip().lower()
                if bs_lower in BS_ALLOWED:
                    perf["barrier_status"] = bs_lower
                elif bs_lower in BS_SYNONYM:
                    perf["barrier_status"] = BS_SYNONYM[bs_lower]
                    counts["barrier_status_mapped"] += 1
                else:
                    perf["barrier_status"] = "unknown"
                    counts["barrier_status_unknown"] += 1
            else:
                perf["barrier_status"] = "unknown"
                counts["barrier_status_missing"] += 1

        # human.human_contribution_value
        human = ctrl.get("human")
        if isinstance(human, dict):
            hcv = human.get("human_contribution_value")
            if hcv is None:
                human["human_contribution_value"] = "unknown"
                counts["human_value_none_to_unknown"] += 1
            elif isinstance(hcv, list):
                human["human_contribution_value"] = (
                    hcv[0] if len(hcv) == 1 else "; ".join(str(x) for x in hcv)
                )
                counts["human_value_list_to_str"] += 1
            elif not isinstance(hcv, str):
                human["human_contribution_value"] = str(hcv)
                counts["human_value_to_str"] += 1

    return dict(counts)
