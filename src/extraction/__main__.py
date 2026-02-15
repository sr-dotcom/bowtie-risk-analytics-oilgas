"""Standalone entry point: python -m src.extraction"""
import argparse
import logging
from pathlib import Path

from src.extraction.runner import run_extraction_qc


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(
        prog="python -m src.extraction",
        description="Run extraction QC: multi-pass PDF extraction with quality gating",
    )
    parser.add_argument(
        "--pdf-dir",
        required=True,
        help="Directory containing PDF files",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed/text",
        help="Output directory for normalized text files",
    )
    parser.add_argument(
        "--manifest",
        default="data/processed/extraction_manifest.csv",
        help="Path for extraction manifest CSV",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess even if already in manifest",
    )

    args = parser.parse_args()
    run_extraction_qc(
        pdf_dir=Path(args.pdf_dir),
        output_dir=Path(args.output_dir),
        manifest_path=Path(args.manifest),
        force=args.force,
    )


if __name__ == "__main__":
    main()
