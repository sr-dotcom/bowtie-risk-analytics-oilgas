"""Lightweight smoke test for association mining scripts.

Creates a temporary incident JSON, runs aggregation and flattening scripts,
and validates basic output shape.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SAMPLE_INCIDENT = {
    "incident_id": "smoke-001",
    "bowtie": {
        "controls": [
            {
                "control_id": "C-1",
                "name": "Gas detector",
                "side": "left",
                "barrier_role": "preventive",
                "barrier_type": "engineering",
                "line_of_defense": "1",
                "lod_basis": "primary",
                "linked_threat_ids": ["T-1"],
                "linked_consequence_ids": ["Q-1"],
                "performance": {"barrier_status": "effective", "barrier_failed": False},
                "human": {"human_contribution_value": "none", "barrier_failed_human": False},
                "evidence": {"confidence": "high", "supporting_text": ["example"]},
            }
        ]
    },
}


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_dir = tmp_path / "schema_v2_3"
        input_dir.mkdir(parents=True, exist_ok=True)

        (input_dir / "incident.json").write_text(json.dumps(SAMPLE_INCIDENT), encoding="utf-8")

        agg_json = tmp_path / "incidents_aggregated.json"
        flat_csv = tmp_path / "incidents_flat.csv"

        subprocess.run(
            [
                sys.executable,
                "scripts/association_mining/jsonaggregation.py",
                "--input-dir",
                str(input_dir),
                "--output-json",
                str(agg_json),
            ],
            check=True,
        )

        payload = json.loads(agg_json.read_text(encoding="utf-8"))
        assert isinstance(payload, list) and payload, "Aggregated output should be a non-empty JSON list"

        subprocess.run(
            [
                sys.executable,
                "scripts/association_mining/jsonflattening.py",
                "--input-json",
                str(agg_json),
                "--output-csv",
                str(flat_csv),
            ],
            check=True,
        )

        with flat_csv.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        assert len(rows) >= 2, "CSV should include header and at least one data row"

        # --- Step 3: Normalize barrier families ---
        norm_csv = tmp_path / "normalized_df.csv"

        subprocess.run(
            [
                sys.executable,
                "scripts/association_mining/event_barrier_normalization.py",
                "--input-csv",
                str(flat_csv),
                "--output-csv",
                str(norm_csv),
            ],
            check=True,
        )

        assert norm_csv.exists(), "normalized_df.csv should be created"

        with norm_csv.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            norm_header = reader.fieldnames
            norm_rows = list(reader)

        assert norm_header is not None, "normalized CSV should have a header"
        assert "barrier_family" in norm_header, "barrier_family column must exist"
        assert "barrier_level" in norm_header, "barrier_level column must exist"

        assert len(norm_rows) >= 1, "normalized CSV should have at least one data row"

        allowed_levels = {"prevention", "mitigation"}
        for row in norm_rows:
            assert row["barrier_level"] in allowed_levels, (
                f"barrier_level must be prevention or mitigation, got {row['barrier_level']!r}"
            )

    print("association_mining smoke test passed")


if __name__ == "__main__":
    main()
