import json
import argparse
from pathlib import Path


def parse_args(default_input: Path, default_output: Path):
    parser = argparse.ArgumentParser(
        description="Aggregate incident-level JSON files into a single incidents.json file"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=default_input,
        help=f"Directory containing incident JSON files (default: {default_input})"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output,
        help=f"Output aggregated JSON file (default: {default_output})"
    )
    return parser.parse_args()


def aggregate_incidents(input_dir: Path, out_path: Path):
    incidents = []

    for fp in sorted(input_dir.rglob("*.json")):
        try:
            obj = json.loads(fp.read_text(encoding="utf-8"))
            obj["_source_file"] = str(fp)
            incidents.append(obj)
        except Exception as e:
            print(f"Skipping {fp}: {e}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(incidents, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Wrote {len(incidents)} incidents → {out_path}")


if __name__ == "__main__":
    # ---- Resolve project-relative defaults ----
    BASE_DIR = Path(__file__).resolve().parent
    PROJECT_ROOT = BASE_DIR.parent

    DEFAULT_INPUT_DIR = (
        PROJECT_ROOT
        / "data"
        / "structured"
        / "incidents"
        / "schema_v2_3"
    )

    DEFAULT_OUTPUT_PATH = (
        PROJECT_ROOT
        / "data"
        / "processed"
        / "incidents.json"
    )

    args = parse_args(
        default_input=DEFAULT_INPUT_DIR,
        default_output=DEFAULT_OUTPUT_PATH
    )

    aggregate_incidents(
        input_dir=args.input_dir.resolve(),
        out_path=args.output.resolve()
    )

