"""Normalize barrier controls into family categories via rule-based classification.

Reads the flat CSV produced by jsonflattening.py, applies text normalization and
domain-specific rule-based family assignment across 4 quadrants (prevention/mitigation
x administrative/engineering), and writes normalized_df.csv.

No external dependencies beyond the Python standard library.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DEFAULT_INPUT_CSV = Path("out/association_mining/incidents_flat.csv")
DEFAULT_OUTPUT_CSV = Path("out/association_mining/normalized_df.csv")

# ---------------------------------------------------------------------------
# Column contracts
# ---------------------------------------------------------------------------

# Required columns from jsonflattening.py output (CSV_COLUMNS in that module).
REQUIRED_INPUT_COLUMNS = frozenset(
    [
        "incident_id",
        "control_id",
        "control_name",
        "side",
        "barrier_role",
        "barrier_type",
        "line_of_defense",
        "lod_basis",
        "linked_threat_ids",
        "linked_consequence_ids",
        "barrier_status",
        "barrier_failed",
        "human_contribution_value",
        "barrier_failed_human",
        "confidence",
        "supporting_text_count",
    ]
)

COMMON_COLS: list[str] = [
    "incident_id",
    "control_id",
    "control_name_raw",
    "control_name_norm",
    "barrier_role_raw",
    "barrier_role_norm",
    "family_match_text_norm",
    "barrier_level",
    "barrier_type",
    "barrier_family",
    "line_of_defense",
    "lod_basis",
    "barrier_status",
    "barrier_failed",
    "human_contribution_value",
    "barrier_failed_human",
    "confidence",
    "supporting_text_count",
]

# ---------------------------------------------------------------------------
# Side mapping  (requirement #4)
# ---------------------------------------------------------------------------

SIDE_MAP: dict[str, str] = {
    "left": "prevention",
    "right": "mitigation",
    "prevention": "prevention",
    "mitigation": "mitigation",
}

# ---------------------------------------------------------------------------
# Barrier type validation
# ---------------------------------------------------------------------------

ALLOWED_BARRIER_TYPES = frozenset(["administrative", "engineering", "ppe", "unknown"])

# ---------------------------------------------------------------------------
# Domain abbreviation expansion
# ---------------------------------------------------------------------------

ABBR_MAP: dict[str, str] = {
    "psv": "pressure safety valve",
    "prv": "pressure relief valve",
    "bop": "blowout preventer",
    "esd": "emergency shutdown",
    "esdv": "emergency shutdown valve",
    "sdv": "shutdown valve",
    "ssv": "surface safety valve",
    "scssv": "surface controlled subsurface safety valve",
    "sssv": "subsurface safety valve",
    "loto": "lockout tagout",
    "jsea": "job safety and environmental analysis",
    "jsa": "job safety analysis",
    "jha": "job hazard analysis",
    "tha": "task hazard analysis",
    "moc": "management of change",
    "ptw": "permit to work",
    "sop": "standard operating procedure",
    "ppe": "personal protective equipment",
    "scba": "self contained breathing apparatus",
    "hvac": "heating ventilation air conditioning",
    "pa": "public address",
    "lel": "lower explosive limit",
    "h2s": "hydrogen sulfide",
    "leo": "lower explosive limit alarm",
    "hse": "health safety environment",
    "api": "american petroleum institute",
    "nfpa": "national fire protection association",
    "osha": "occupational safety health administration",
    "bsee": "bureau of safety environmental enforcement",
    "rmp": "risk management plan",
    "pfd": "process flow diagram",
    "pid": "piping and instrumentation diagram",
    "sil": "safety integrity level",
    "sis": "safety instrumented system",
    "sif": "safety instrumented function",
    "dcs": "distributed control system",
    "plc": "programmable logic controller",
    "gos": "gas on surface",
    "lmrp": "lower marine riser package",
    "eds": "emergency disconnect sequence",
    "uwild": "underwater intervention and latch down",
}

# ---------------------------------------------------------------------------
# Family taxonomies — 4 quadrants
# ---------------------------------------------------------------------------

PREVENTION_ADMIN_FAMILIES: dict[str, list[str]] = {
    "training": [
        "train", "competenc", "certif", "qualif", "skill", "drill",
        "familiariz", "orientat", "awareness",
    ],
    "procedures": [
        "procedure", "sop", "protocol", "checklist", "step-by-step",
        "instruction", "guideline", "work practice", "safe work",
        "standard operating",
    ],
    "change_management": [
        "management of change", "moc", "change control", "change review",
        "modification", "temporary change", "permanent change",
    ],
    "monitoring": [
        "monitor", "surveillance", "inspect", "audit", "check",
        "observation", "watch", "patrol", "tour", "round",
    ],
    "regulatory_and_permits": [
        "permit", "regulat", "compliance", "authori", "approv",
        "license", "certif", "ptw", "hot work permit",
    ],
    "hazard_analysis_prework_checks": [
        "hazard analy", "hazard identif", "jsa", "jha", "jsea", "tha",
        "risk assess", "pre-job", "prejob", "prework", "toolbox talk",
        "safety meeting", "hazop", "what-if",
    ],
    "operating_controls_and_limits": [
        "operating limit", "operating envel", "setpoint", "trip point",
        "alarm setpoint", "operating parameter", "safe operating",
        "operating range", "process limit", "critical parameter",
    ],
    "communication": [
        "communicat", "handover", "hand-over", "shift change",
        "briefing", "debriefing", "reporting", "notification",
        "signal person", "radio",
    ],
    "planning": [
        "plan", "design review", "engineering review", "pre-commissioning",
        "commissioning plan", "decommission",
    ],
    "maintenance": [
        "maintenance", "preventive maintenance", "predictive maintenance",
        "corrective maintenance", "integrity management",
        "reliability", "overhaul", "turnaround",
    ],
}

PREVENTION_ENGINEERING_FAMILIES: dict[str, list[str]] = {
    "overpressurization_gas_discharge_gas_isolation": [
        "pressure relief", "pressure safety", "prv", "psv",
        "blowdown", "flare", "vent", "rupture disc", "rupture disk",
        "burst disc", "burst disk", "pressure control",
        "choke", "backpressure", "overpressure",
        "blowout preventer", "bop", "annular preventer",
        "ram", "shear ram", "blind ram",
        "gas isolation", "valve", "sdv", "esdv", "ssv", "scssv", "sssv",
        "block valve", "wing valve", "master valve", "swab valve",
        "check valve", "shutoff", "shut-off", "isolation",
        "wellhead", "christmas tree", "well control",
    ],
    "fluid_discharge_and_containment": [
        "containment", "bund", "dike", "drain", "sump",
        "spill", "leak", "seal", "gasket", "packing",
        "secondary containment", "drip tray", "catch basin",
        "retention", "curb", "overflow",
    ],
    "prevention_of_ignition": [
        "ignition", "hot work", "classified area", "hazardous area",
        "ex rating", "explosion proof", "intrinsic", "purge",
        "inerting", "nitrogen blanket", "flame arrest",
        "spark", "static", "bonding", "grounding", "earthing",
    ],
    "detection_monitoring_alarms": [
        "detector", "detection", "sensor", "transmitter",
        "alarm", "alert", "annunciat", "indicator", "gauge",
        "analyzer", "monitor", "metering", "flow meter",
        "level switch", "pressure switch", "temperature switch",
        "high level", "low level", "high pressure", "low pressure",
    ],
    "mechanical_integrity": [
        "mechanical integrity", "structural", "corrosion",
        "inspection", "ndt", "non-destructive",
        "thickness", "ultrasonic", "radiograph",
        "hydrostatic", "hydrotest", "pressure test",
        "material select", "metallurg", "fatigue", "creep",
        "weld", "flange", "bolt", "torque", "piping",
    ],
}

MITIGATION_ADMIN_FAMILIES: dict[str, list[str]] = {
    "emergency_shutdown_isolation_depressurization": [
        "emergency shutdown", "esd", "emergency isolat",
        "emergency depressur", "blowdown procedure",
        "emergency procedure", "shutdown procedure",
    ],
    "detection_monitoring_surveillance": [
        "detection", "monitor", "surveillance", "watch",
        "gas test", "atmospheric monitor", "air monitor",
    ],
    "active_intervention_to_stop_release": [
        "intervent", "stop release", "contain release",
        "well kill", "dynamic kill", "bullhead",
        "plug", "cement", "seal",
    ],
    "fire_response_firewatch_ignition_control": [
        "fire response", "fire watch", "firewatch",
        "fire brigade", "fire team", "firefight",
        "fire suppression", "fire extinguish",
    ],
    "evacuation_muster_shelter_exclusion_access_control": [
        "evacuat", "muster", "shelter", "exclusion",
        "access control", "barricade", "perimeter",
        "safety zone", "escape", "assembly point",
    ],
    "medical_response_and_evacuation": [
        "medical", "first aid", "medevac", "paramedic",
        "emt", "ambulance", "triage", "casualty",
    ],
    "environmental_response_cleanup_reporting": [
        "environmental response", "cleanup", "clean-up",
        "spill response", "oil spill", "remediat",
        "environmental report",
    ],
    "incident_command_coordination_and_comms": [
        "incident command", "coordination", "unified command",
        "crisis management", "emergency management",
        "communication", "notification", "alert",
    ],
    "investigation_corrective_action_post_incident_verification": [
        "investigat", "root cause", "corrective action",
        "lessons learned", "post-incident", "after-action",
        "incident review",
    ],
    "supervision_staffing_oversight": [
        "supervis", "oversight", "staffing", "manning",
        "crew", "competent person", "appointed person",
    ],
    "emergency_preparedness_planning_training_drills": [
        "emergency plan", "contingency", "emergency preparedness",
        "emergency drill", "exercise", "tabletop",
        "emergency training", "response plan",
    ],
    "ppe_and_respiratory_protection": [
        "ppe", "personal protective", "respirat",
        "scba", "breathing apparatus", "glove", "goggle",
        "face shield", "hard hat", "helmet", "coverall",
        "fire suit", "fire retard", "flame retard",
    ],
    "permits_controlled_work_during_response": [
        "permit", "controlled work", "hot work",
        "cold work", "confined space", "lockout", "tagout",
        "loto", "isolation", "energy isolat",
    ],
}

MITIGATION_ENGINEERING_FAMILIES: dict[str, list[str]] = {
    "gas_detection_atmospheric_monitoring": [
        "gas detect", "gas monitor", "gas sensor",
        "combustible gas", "toxic gas", "h2s detect",
        "lel detect", "oxygen monitor", "atmospheric",
    ],
    "alarms_general_alarm_pa": [
        "general alarm", "public address", "pa system",
        "alarm system", "siren", "klaxon", "horn",
        "visual alarm", "audible alarm", "beacon",
    ],
    "emergency_shutdown_isolation": [
        "emergency shutdown", "esd", "esdv", "emergency isolat",
        "shutdown system", "safety shutdown",
        "fusible plug", "fusible link",
    ],
    "emergency_disconnect_eds": [
        "emergency disconnect", "eds", "disconnect",
        "lmrp disconnect", "riser disconnect",
    ],
    "well_control_barriers_kill": [
        "well control", "bop", "blowout preventer",
        "kill", "choke", "annular", "ram",
        "shear ram", "capping stack",
    ],
    "pressure_relief_blowdown_flare_disposal": [
        "pressure relief", "prv", "psv", "relief valve",
        "blowdown", "flare", "vent", "disposal",
        "rupture disc", "rupture disk", "burst",
        "thermal relief", "depressur",
    ],
    "ignition_source_control": [
        "ignition control", "ignition source",
        "classified area", "hazardous area",
        "ex-proof", "explosion proof", "intrinsic safety",
        "purge", "inert",
    ],
    "active_fire_protection_firefighting": [
        "fire suppression", "deluge", "sprinkler",
        "foam", "water curtain", "fire pump",
        "fire main", "fire hose", "fire extinguish",
        "halon", "co2 system", "dry chemical",
        "monitor nozzle", "fire cannon",
    ],
    "passive_fire_blast_protection": [
        "passive fire", "firewall", "fire wall",
        "blast wall", "blast barrier", "fire rating",
        "fire resist", "fire proof", "fire insul",
        "intumescent", "fire damper", "fire door",
    ],
    "control_room_habitability_hvac_pressurization": [
        "control room", "habitab", "hvac",
        "pressurization", "air intake", "smoke damper",
        "positive pressure", "safe haven",
    ],
    "emergency_power_backup_utilities": [
        "emergency power", "backup power", "generator",
        "ups", "uninterrupt", "emergency light",
        "battery", "diesel generator",
    ],
    "spill_containment_environmental_mitigation": [
        "spill contain", "boom", "skimmer",
        "absorbent", "dispersant", "oil spill",
        "environmental protect", "bund", "dike",
        "secondary contain",
    ],
    "chemical_release_scrubbing_neutralization": [
        "scrubber", "neutraliz", "chemical treatment",
        "absorber", "acid gas", "caustic",
        "water wash", "quench",
    ],
    "physical_protection_retention_restraints": [
        "guard", "guardrail", "hand rail", "handrail",
        "barrier", "restraint", "safety net",
        "toe board", "fall arrest", "fall protect",
        "lifeline", "anchor point",
    ],
    "emergency_escape_access_rescue_decon": [
        "escape", "egress", "lifeboat", "life raft",
        "rescue", "davit", "life jacket",
        "decontaminat", "decon", "shower",
        "eyewash", "safety shower",
    ],
    "structural_mechanical_integrity_escalation_prevention": [
        "structural integrity", "escalation prevent",
        "fire break", "firebreak", "separation",
        "spacing", "layout", "segregat",
    ],
    "remote_monitoring_intervention_subsea": [
        "rov", "remote operat", "remote monitor",
        "subsea", "subsea intervention", "acoustic",
        "autoshear", "deadman", "amt",
    ],
    "marine_collision_avoidance": [
        "collision avoidance", "radar", "ais",
        "vessel management", "marine traffic",
        "standby vessel", "guard vessel",
        "anchor handling",
    ],
}

# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")


def normalize_control_name(text: str) -> str:
    """Lowercase, expand abbreviations, strip punctuation, collapse whitespace."""
    text = text.lower().strip()
    for abbr, expansion in ABBR_MAP.items():
        text = re.sub(rf"\b{re.escape(abbr)}\b", expansion, text)
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def normalize_for_family(text: str) -> str:
    """Extended normalization for family matching (combines name + role)."""
    return normalize_control_name(text)


# ---------------------------------------------------------------------------
# Rule-based family assignment — 4 quadrants
# ---------------------------------------------------------------------------


def _match_family(
    text: str, taxonomy: dict[str, list[str]], fallback: str,
) -> str:
    """Check *text* against each family's keyword list. First match wins."""
    for family, keywords in taxonomy.items():
        for kw in keywords:
            if kw in text:
                return family
    return fallback


def assign_prevention_admin_family(text: str) -> str:
    return _match_family(text, PREVENTION_ADMIN_FAMILIES, "other_admin")


def assign_prevention_eng_family(text: str) -> str:
    return _match_family(text, PREVENTION_ENGINEERING_FAMILIES, "other_engineering")


def assign_mitigation_admin_family(text: str) -> str:
    return _match_family(text, MITIGATION_ADMIN_FAMILIES, "other_admin")


def assign_mitigation_eng_family(text: str) -> str:
    return _match_family(text, MITIGATION_ENGINEERING_FAMILIES, "other_engineering")


# Quadrant dispatch: (barrier_level, barrier_type) -> assignment function
_QUADRANT_DISPATCH: dict[tuple[str, str], Any] = {
    ("prevention", "administrative"): assign_prevention_admin_family,
    ("prevention", "engineering"): assign_prevention_eng_family,
    ("mitigation", "administrative"): assign_mitigation_admin_family,
    ("mitigation", "engineering"): assign_mitigation_eng_family,
}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize barrier controls into family categories.",
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=DEFAULT_INPUT_CSV,
        help=f"Flat controls CSV from jsonflattening.py (default: {DEFAULT_INPUT_CSV})",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=DEFAULT_OUTPUT_CSV,
        help=f"Output normalized CSV (default: {DEFAULT_OUTPUT_CSV})",
    )
    parser.add_argument(
        "--use-embeddings",
        action="store_true",
        default=False,
        help="Enable embedding fallback (not implemented in rule-only mode).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------


def _validate_columns(header: list[str]) -> None:
    """Fail fast if required input columns are missing."""
    present = frozenset(header)
    missing = REQUIRED_INPUT_COLUMNS - present
    if missing:
        raise ValueError(
            f"Input CSV is missing required columns: {sorted(missing)}. "
            f"Expected columns from jsonflattening.py: {sorted(REQUIRED_INPUT_COLUMNS)}"
        )


def _resolve_side(raw_side: str, row_num: int, incident_id: str) -> str:
    """Map side value via SIDE_MAP or raise ValueError."""
    key = raw_side.strip().lower()
    mapped = SIDE_MAP.get(key)
    if mapped is None:
        raise ValueError(
            f"Row {row_num} (incident_id={incident_id!r}): "
            f"unknown side value {raw_side!r}. "
            f"Allowed values: {sorted(SIDE_MAP.keys())}"
        )
    return mapped


def _resolve_barrier_type(raw_type: str, row_num: int, incident_id: str) -> str:
    """Validate barrier_type or raise ValueError."""
    normalized = raw_type.strip().lower()
    if normalized not in ALLOWED_BARRIER_TYPES:
        raise ValueError(
            f"Row {row_num} (incident_id={incident_id!r}): "
            f"unknown barrier_type value {raw_type!r}. "
            f"Allowed values: {sorted(ALLOWED_BARRIER_TYPES)}"
        )
    return normalized


def normalize(
    input_csv: Path,
    output_csv: Path,
    *,
    use_embeddings: bool = False,
) -> int:
    """Read flat CSV, apply normalization + family assignment, write output.

    Returns the number of rows written.
    """
    if use_embeddings:
        print(
            "ERROR: Embedding fallback not implemented in rule-only mode. "
            "Use rule-based assignment (omit --use-embeddings).",
            file=sys.stderr,
        )
        sys.exit(1)

    with input_csv.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"Input CSV {input_csv} has no header row")
        _validate_columns(list(reader.fieldnames))

        rows: list[dict[str, Any]] = []
        for row_num, row in enumerate(reader, start=2):  # header is row 1
            incident_id = row["incident_id"]
            barrier_level = _resolve_side(row["side"], row_num, incident_id)
            barrier_type_raw = _resolve_barrier_type(
                row["barrier_type"], row_num, incident_id,
            )

            control_name_raw = row["control_name"]
            barrier_role_raw = row["barrier_role"]

            control_name_norm = normalize_control_name(control_name_raw)
            barrier_role_norm = normalize_control_name(barrier_role_raw)
            family_match_text = normalize_for_family(
                control_name_norm + " " + barrier_role_norm
            )

            # Dispatch to quadrant; ppe/unknown get direct family label.
            dispatch_key = (barrier_level, barrier_type_raw)
            assign_fn = _QUADRANT_DISPATCH.get(dispatch_key)
            if assign_fn is not None:
                barrier_family = assign_fn(family_match_text)
            else:
                # ppe and unknown are allowed but have no quadrant taxonomy.
                barrier_family = f"other_{barrier_type_raw}"

            rows.append(
                {
                    "incident_id": incident_id,
                    "control_id": row["control_id"],
                    "control_name_raw": control_name_raw,
                    "control_name_norm": control_name_norm,
                    "barrier_role_raw": barrier_role_raw,
                    "barrier_role_norm": barrier_role_norm,
                    "family_match_text_norm": family_match_text,
                    "barrier_level": barrier_level,
                    "barrier_type": barrier_type_raw,
                    "barrier_family": barrier_family,
                    "line_of_defense": row["line_of_defense"],
                    "lod_basis": row["lod_basis"],
                    "barrier_status": row["barrier_status"],
                    "barrier_failed": row["barrier_failed"],
                    "human_contribution_value": row["human_contribution_value"],
                    "barrier_failed_human": row["barrier_failed_human"],
                    "confidence": row["confidence"],
                    "supporting_text_count": row["supporting_text_count"],
                }
            )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COMMON_COLS)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def main() -> None:
    args = parse_args()
    row_count = normalize(args.input_csv, args.output_csv, use_embeddings=args.use_embeddings)
    print(f"Normalized {row_count} control row(s) to {args.output_csv}")


if __name__ == "__main__":
    main()
