import argparse
import json
import logging
from pathlib import Path
from typing import List, Optional

import requests

from src.ingestion.loader import load_incident_from_text
from src.ingestion.manifests import (
    load_incident_manifest,
    save_incident_manifest,
    save_text_manifest,
)
from src.ingestion.pdf_text import process_incident_manifest
from src.ingestion.sources.csb import discover_csb_incidents, download_csb_pdf
from src.ingestion.sources.bsee import discover_bsee_incidents, download_bsee_pdf
from src.models.incident import Incident
from src.models.bowtie import Bowtie
from src.analytics.engine import calculate_barrier_coverage, identify_gaps
from src.analytics.aggregation import calculate_fleet_metrics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

def load_bowtie(bowtie_path: Path) -> Optional[Bowtie]:
    """Loads a Bowtie definition from a JSON file."""
    if not bowtie_path.exists():
        logger.warning(f"Bowtie definition not found at {bowtie_path}")
        return None

    try:
        data = json.loads(bowtie_path.read_text(encoding='utf-8'))
        return Bowtie(**data)
    except Exception as e:
        logger.error(f"Failed to load Bowtie definition: {e}")
        return None

def process_raw_files(raw_dir: Path, processed_dir: Path, bowtie_path: Optional[Path] = None) -> List[Incident]:
    """
    Reads raw text files, parses incidents, computes analytics, and saves structured JSON.

    Args:
        raw_dir: Directory containing raw text files.
        processed_dir: Directory to save processed JSON files.
        bowtie_path: Path to the reference Bowtie JSON file (optional).

    Returns:
        List of successfully processed Incident objects.
    """
    processed_incidents = []
    all_output_data = []

    if not raw_dir.exists():
        logger.error(f"Raw directory not found: {raw_dir}")
        return []

    processed_dir.mkdir(parents=True, exist_ok=True)

    # Load Bowtie reference if provided
    bowtie = load_bowtie(bowtie_path) if bowtie_path else None
    if bowtie:
        logger.info(f"Loaded Bowtie reference: {bowtie.hazard} -> {bowtie.top_event}")

    for file_path in raw_dir.glob("*.txt"):
        logger.info(f"Processing file: {file_path.name}")

        try:
            content = file_path.read_text(encoding='utf-8')
            # Simple splitter for the sample format (blocks separated by blank lines)
            blocks = content.strip().split('\n\n')

            for block in blocks:
                if not block.strip():
                    continue

                try:
                    incident = load_incident_from_text(block)
                    processed_incidents.append(incident)

                    # Prepare output data
                    output_data = incident.model_dump()

                    # Run analytics if Bowtie is available
                    if bowtie:
                        coverage = calculate_barrier_coverage(incident, bowtie)
                        gaps = identify_gaps(incident, bowtie)

                        output_data["analytics"] = {
                            "coverage": coverage,
                            "gaps": [gap.model_dump() for gap in gaps]
                        }
                        logger.info(f"Analyzed {incident.incident_id}: Coverage={coverage['overall_coverage']:.1%}, Gaps={len(gaps)}")

                    all_output_data.append(output_data)

                    # Save enriched JSON
                    output_file = processed_dir / f"{incident.incident_id}.json"
                    output_file.write_text(json.dumps(output_data, indent=2, default=str), encoding='utf-8')
                    logger.info(f"Saved {incident.incident_id}")

                except ValueError as e:
                    logger.warning(f"Failed to parse block in {file_path.name}: {e}")

        except Exception as e:
            logger.error(f"Error reading file {file_path.name}: {e}")

    # Calculate and save aggregate metrics
    if all_output_data:
        metrics = calculate_fleet_metrics(all_output_data)
        metrics_file = processed_dir / "fleet_metrics.json"
        metrics_file.write_text(json.dumps(metrics, indent=2), encoding='utf-8')
        logger.info(f"Saved fleet metrics to {metrics_file.name}")

    logger.info(f"Pipeline finished. Processed {len(processed_incidents)} incidents.")
    return processed_incidents


def cmd_acquire(args: argparse.Namespace) -> None:
    """Acquire incident metadata and optionally download PDFs."""
    out_path = Path(args.out)
    raw_dir = out_path.parent

    rows = []
    session = requests.Session()
    session.headers["User-Agent"] = "BowtieRiskAnalytics/0.1 (academic research)"

    # Discover CSB incidents
    if args.csb_limit > 0:
        logger.info(f"Discovering up to {args.csb_limit} CSB incidents...")
        for row in discover_csb_incidents(limit=args.csb_limit):
            if args.download:
                row = download_csb_pdf(row, raw_dir, session, timeout=args.timeout)
            rows.append(row)

    # Discover BSEE incidents
    if args.bsee_limit > 0:
        logger.info(f"Discovering up to {args.bsee_limit} BSEE incidents...")
        for row in discover_bsee_incidents(limit=args.bsee_limit):
            if args.download:
                row = download_bsee_pdf(row, raw_dir, session, timeout=args.timeout)
            rows.append(row)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_incident_manifest(rows, out_path)
    logger.info(f"Saved {len(rows)} incidents to {out_path}")

    downloaded = sum(1 for r in rows if r.downloaded)
    logger.info(f"Downloaded: {downloaded}/{len(rows)}")


def cmd_extract_text(args: argparse.Namespace) -> None:
    """Extract text from downloaded PDFs."""
    manifest_path = Path(args.manifest)
    out_path = Path(args.out)
    raw_dir = manifest_path.parent

    incident_rows = load_incident_manifest(manifest_path)
    downloaded_rows = [r for r in incident_rows if r.downloaded]

    logger.info(f"Extracting text from {len(downloaded_rows)} PDFs...")
    text_rows = process_incident_manifest(downloaded_rows, raw_dir)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_text_manifest(text_rows, out_path)
    logger.info(f"Saved {len(text_rows)} text manifest rows to {out_path}")

    extracted = sum(1 for r in text_rows if r.extracted)
    empty = sum(1 for r in text_rows if r.is_empty)
    logger.info(f"Extracted: {extracted}/{len(text_rows)}, Empty: {empty}")


def cmd_process(args: argparse.Namespace) -> None:
    """Original pipeline behavior (for backwards compat)."""
    raw_dir = BASE_DIR / "data" / "raw"
    processed_dir = BASE_DIR / "data" / "processed"
    bowtie_path = BASE_DIR / "data" / "sample" / "bowtie_loc.json"
    process_raw_files(raw_dir, processed_dir, bowtie_path)


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        prog="python -m src.pipeline", description="Bowtie Risk Analytics pipeline"
    )
    subparsers = parser.add_subparsers(dest="command")

    # acquire subcommand
    p_acquire = subparsers.add_parser(
        "acquire", help="Discover and download incident PDFs"
    )
    p_acquire.add_argument(
        "--csb-limit", type=int, default=20, help="Max CSB incidents to discover"
    )
    p_acquire.add_argument(
        "--bsee-limit", type=int, default=20, help="Max BSEE incidents to discover"
    )
    p_acquire.add_argument(
        "--out",
        default="data/raw/incidents_manifest_v0.csv",
        help="Output manifest path",
    )
    p_acquire.add_argument(
        "--download", action="store_true", help="Download PDFs after discovery"
    )
    p_acquire.add_argument(
        "--timeout", type=int, default=30, help="Download timeout in seconds"
    )
    p_acquire.set_defaults(func=cmd_acquire)

    # extract-text subcommand
    p_extract = subparsers.add_parser("extract-text", help="Extract text from PDFs")
    p_extract.add_argument(
        "--manifest",
        default="data/raw/incidents_manifest_v0.csv",
        help="Input incidents manifest",
    )
    p_extract.add_argument(
        "--out",
        default="data/raw/text_manifest_v0.csv",
        help="Output text manifest path",
    )
    p_extract.set_defaults(func=cmd_extract_text)

    # process subcommand (original behavior)
    p_process = subparsers.add_parser("process", help="Run analytics pipeline")
    p_process.set_defaults(func=cmd_process)

    args = parser.parse_args()

    if args.command is None:
        # Default: original behavior (backwards compat)
        cmd_process(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
