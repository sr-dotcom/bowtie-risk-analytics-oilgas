"""Aggregate Schema v2.3 incident JSON files into a single JSON list.

This script is intentionally simple and portable:
- no hard-coded absolute paths
- recursive JSON discovery under the input directory
- deterministic ordering by relative path
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_INPUT_DIR = Path("data/structured/incidents/schema_v2_3")
DEFAULT_OUTPUT_JSON = Path("out/association_mining/incidents_aggregated.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate normalized Schema v2.3 incident JSON files into one list.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=(
            "Root folder containing normalized Schema v2.3 incident JSON files "
            f"(default: {DEFAULT_INPUT_DIR.as_posix()})"
        ),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_OUTPUT_JSON,
        help=(
            "Path to write aggregated JSON list "
            f"(default: {DEFAULT_OUTPUT_JSON.as_posix()})"
        ),
    )
    return parser.parse_args()


def discover_json_files(input_dir: Path) -> list[Path]:
    """Recursively discover candidate incident JSON files."""
    return sorted(
        [
            path
            for path in input_dir.rglob("*.json")
            if path.is_file() and not path.name.startswith(".")
        ],
        key=lambda p: p.as_posix(),
    )


def load_incident(path: Path) -> dict[str, Any] | None:
    """Load one incident JSON payload; return None on invalid payload."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    # Minimal metadata for downstream reproducibility.
    payload.setdefault("incident_id", path.stem)
    payload.setdefault("source_file", path.as_posix())
    return payload


def aggregate(input_dir: Path, output_json: Path) -> int:
    json_files = discover_json_files(input_dir)
    aggregated: list[dict[str, Any]] = []

    for json_file in json_files:
        incident = load_incident(json_file)
        if incident is None:
            continue
        aggregated.append(incident)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(aggregated, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return len(aggregated)


def main() -> None:
    args = parse_args()
    count = aggregate(args.input_dir, args.output_json)
    print(f"Aggregated {count} incident file(s) into {args.output_json}")


if __name__ == "__main__":
    main()
