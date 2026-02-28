#!/usr/bin/env python
"""CLI for running analytics pipeline: flatten + baseline."""
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analytics.flatten import flatten_all
from src.analytics.baseline import run_baseline

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run analytics on structured incidents")
    parser.add_argument(
        "--structured-dir",
        default="data/structured/incidents/schema_v2_3",
        help="Directory containing Schema v2.3 incident JSON files",
    )
    parser.add_argument(
        "--out-dir",
        default="data/derived",
        help="Output directory for derived datasets",
    )
    args = parser.parse_args()

    structured_dir = Path(args.structured_dir)
    out_dir = Path(args.out_dir)

    # Step 1: Flatten controls
    controls_csv = out_dir / "controls.csv"
    n_rows = flatten_all(structured_dir, controls_csv)

    if n_rows == 0:
        logger.warning("No controls to analyze. Exiting.")
        return

    # Step 2: Run baseline analytics
    run_baseline(controls_csv, out_dir)

    logger.info("Analytics pipeline complete.")


if __name__ == "__main__":
    main()
