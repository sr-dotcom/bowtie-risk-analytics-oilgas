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
    merge_incident_manifests,
)
from src.ingestion.pdf_text import process_incident_manifest
from src.ingestion.sources.csb import discover_csb_incidents, download_csb_pdf
from src.ingestion.sources.bsee import discover_bsee_incidents, download_bsee_pdf
from src.models.incident import Incident
from src.models.bowtie import Bowtie
from src.analytics.engine import calculate_barrier_coverage, identify_gaps
from src.analytics.aggregation import calculate_fleet_metrics
from src.ingestion.structured import (
    extract_structured,
    generate_run_report,
    load_structured_manifest,
    merge_structured_manifests,
    save_structured_manifest,
)
from src.ingestion.source_ingest import run_ingest
from src.extraction.runner import run_extraction_qc
from src.ingestion.sources.csb_discover import (
    discover_csb,
    write_url_list as csb_write_url_list,
    write_metadata as csb_write_metadata,
)
from src.ingestion.sources.bsee_discover import (
    discover_bsee,
    write_url_list as bsee_write_url_list,
    write_metadata as bsee_write_metadata,
)
from src.ingestion.sources.phmsa_discover import (
    discover_phmsa,
    write_url_list as phmsa_write_url_list,
    write_metadata as phmsa_write_metadata,
)

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

    # Load existing manifest if --append mode
    existing_rows = []
    if args.append and out_path.exists():
        existing_rows = load_incident_manifest(out_path)
        logger.info(f"Loaded {len(existing_rows)} existing rows from {out_path}")

    new_rows = []
    session = requests.Session()
    session.headers["User-Agent"] = "BowtieRiskAnalytics/0.1 (academic research)"

    # Discover CSB incidents
    if args.csb_limit > 0:
        logger.info(f"Discovering up to {args.csb_limit} CSB incidents...")
        for row in discover_csb_incidents(limit=args.csb_limit):
            if args.download:
                row = download_csb_pdf(row, raw_dir, session, timeout=args.timeout)
            new_rows.append(row)

    # Discover BSEE incidents
    if args.bsee_limit > 0:
        logger.info(f"Discovering up to {args.bsee_limit} BSEE incidents...")
        for row in discover_bsee_incidents(limit=args.bsee_limit):
            if args.download:
                row = download_bsee_pdf(row, raw_dir, session, timeout=args.timeout)
            new_rows.append(row)

    # Merge or overwrite
    if args.append and existing_rows:
        rows = merge_incident_manifests(existing_rows, new_rows)
        logger.info(f"Merged {len(existing_rows)} existing + {len(new_rows)} new -> {len(rows)} total")
    else:
        rows = new_rows

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


def cmd_extract_structured(args: argparse.Namespace) -> None:
    """Extract structured Schema v2.3 JSON from text files using LLM."""
    text_dir = Path(args.text_dir)
    out_dir = Path(args.out_dir)
    manifest_path = Path(args.manifest)

    # Select provider via registry
    from src.llm.registry import get_provider
    provider = get_provider(
        args.provider,
        model=args.model,
        max_output_tokens=args.max_output_tokens,
        temperature=args.temperature,
        timeout=args.timeout,
        retries=args.retries,
    )

    rows = extract_structured(
        text_dir,
        out_dir,
        provider,
        provider_name=args.provider,
        model_name=args.model,
        limit=args.limit,
        resume=args.resume,
    )

    # Merge with existing manifest so prior rows are not dropped
    existing_rows = load_structured_manifest(manifest_path)
    merged = merge_structured_manifests(existing_rows, rows)
    save_structured_manifest(merged, manifest_path)
    logger.info(f"Saved {len(merged)} structured extraction results to {manifest_path} "
                f"({len(rows)} new, {len(existing_rows)} prior)")

    extracted = sum(1 for r in rows if r.extracted)
    valid = sum(1 for r in rows if r.valid)
    logger.info(f"Extracted: {extracted}/{len(rows)}, Valid: {valid}/{len(rows)}")

    # Write run report
    if rows:
        report = generate_run_report(rows, args.provider, args.model)
        report_dir = Path(args.out_dir).parent / "run_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        ts = report["generated_at"].replace(":", "-").replace("+", "")
        report_path = report_dir / f"{args.provider}_{ts}.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        logger.info(f"Run report: {report_path} "
                     f"(valid_rate={report['valid_rate']:.1%})")


def _normalize_v23_payload(payload: dict) -> dict[str, int]:
    """Apply in-memory coercions to make a payload conform to Schema v2.3.

    Returns a counter dict of coercions applied.
    """
    from collections import Counter

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
        "right": "mitigation", "mitigation": "mitigation", "mitigate": "mitigation",
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

        # performance.barrier_status
        perf = ctrl.get("performance")
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


def cmd_convert_schema(args: argparse.Namespace) -> None:
    """Load incident JSON, apply v2.3 coercions, and write normalised output."""
    from collections import Counter

    incident_dir = Path(args.incident_dir)
    out_dir = Path(args.out_dir)
    if not incident_dir.exists():
        logger.warning(f"Incident directory not found: {incident_dir}")
        return

    json_files = sorted(incident_dir.glob("*.json"))
    if not json_files:
        logger.warning(f"No JSON files found in {incident_dir}")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    totals: Counter[str] = Counter()

    for json_path in json_files:
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            logger.error(f"Skipping {json_path.name}: {exc}")
            continue

        file_counts = _normalize_v23_payload(payload)
        for k, v in file_counts.items():
            totals[k] += v

        dst = out_dir / json_path.name
        dst.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info(f"Converted {len(json_files)} files -> {out_dir}")
    if totals:
        logger.info("Coercion summary:")
        for k, v in totals.most_common():
            logger.info(f"  {k}: {v}")


def cmd_schema_check(args: argparse.Namespace) -> None:
    """Validate extracted JSON files against Schema v2.3."""
    from src.validation.incident_validator import validate_incident_v2_2

    incident_dir = Path(args.incident_dir)
    if not incident_dir.exists():
        logger.warning(f"Incident directory not found: {incident_dir}")
        return

    json_files = sorted(incident_dir.glob("*.json"))
    if not json_files:
        logger.warning(f"No JSON files found in {incident_dir}")
        return

    invalid_files: list[tuple[Path, list[str]]] = []
    for json_path in json_files:
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            invalid_files.append((json_path, [f"JSON decode error: {exc}"]))
            continue

        is_valid, errors = validate_incident_v2_2(payload)
        if not is_valid:
            invalid_files.append((json_path, errors))

    valid_count = len(json_files) - len(invalid_files)
    logger.info(f"Schema check: {valid_count}/{len(json_files)} valid in {incident_dir}")

    if invalid_files:
        for json_path, errors in invalid_files:
            logger.error(f"Invalid: {json_path} ({len(errors)} errors)")
            for err in errors[:5]:
                logger.error(f"  - {err}")
        raise SystemExit(1)


def cmd_quality_gate(args: argparse.Namespace) -> None:
    """Run quality gate metrics on structured extraction results."""
    from src.ingestion.structured import compute_quality_gate
    incident_dir = Path(args.incident_dir)
    if not incident_dir.exists():
        logger.warning(f"Incident directory not found: {incident_dir}")
        return
    gate = compute_quality_gate(incident_dir)
    print(json.dumps(gate, indent=2))
    logger.info(f"Quality gate: {gate.get('total', 0)} incidents, "
                f"{gate.get('has_controls_pct', 0)}% with controls, "
                f"{gate.get('has_summary_pct', 0)}% with summary")


def cmd_extract_qc(args: argparse.Namespace) -> None:
    """Run extraction QC: multi-pass PDF extraction with quality gating."""
    run_extraction_qc(
        pdf_dir=Path(args.pdf_dir),
        output_dir=Path(args.output_dir),
        manifest_path=Path(args.manifest),
        force=args.force,
    )


_DISCOVER_ADAPTERS: dict[str, tuple] = {
    "csb": (discover_csb, csb_write_url_list, csb_write_metadata),
    "bsee": (discover_bsee, bsee_write_url_list, bsee_write_metadata),
    "phmsa": (discover_phmsa, phmsa_write_url_list, phmsa_write_metadata),
}


def cmd_discover_source(args: argparse.Namespace) -> None:
    """Discover incident report PDF URLs from a public source."""
    source = args.source
    if source not in _DISCOVER_ADAPTERS:
        logger.error(
            f"Unknown source: {source}. "
            f"Available: {', '.join(sorted(_DISCOVER_ADAPTERS))}"
        )
        raise SystemExit(1)

    discover_fn, write_urls_fn, write_meta_fn = _DISCOVER_ADAPTERS[source]

    out_path = Path(args.out) if args.out else Path(f"data/sources/{source}/url_list.csv")
    base_url = args.base_url
    kwargs: dict = {"timeout": args.timeout, "sleep": args.sleep}
    if base_url:
        kwargs["base_url"] = base_url
    if args.limit is not None:
        kwargs["limit"] = args.limit

    logger.info(f"Discovering {source} reports...")
    try:
        results = discover_fn(**kwargs)
    except Exception as e:
        logger.error(f"Discovery failed for {source}: {e}")
        raise SystemExit(1)

    if not results:
        logger.info(f"No results found for {source}. URL list will be header-only.")

    write_urls_fn(results, out_path)
    logger.info(f"Wrote {len(results)} entries to {out_path}")

    meta_path = out_path.parent / f"{out_path.stem}_metadata{out_path.suffix}"
    write_meta_fn(results, meta_path)
    logger.info(f"Wrote metadata to {meta_path}")


def cmd_ingest_source(args: argparse.Namespace) -> None:
    """Ingest PDFs from a URL list or local directory."""
    output_root = Path(args.output_root) if args.output_root else Path(f"data/raw/{args.source}")
    url_list = Path(args.url_list) if args.url_list else None
    input_pdf_dir = Path(args.input_pdf_dir) if args.input_pdf_dir else None

    rows = run_ingest(
        source=args.source,
        output_root=output_root,
        url_list=url_list,
        input_pdf_dir=input_pdf_dir,
        force=args.force,
        timeout=args.timeout,
    )
    ok = sum(1 for r in rows if r.status == "ok")
    logger.info(f"Ingestion complete: {ok}/{len(rows)} ok")


def main():
    """Main entry point with CLI argument parsing."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

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
    p_acquire.add_argument(
        "--append",
        action="store_true",
        help="Merge with existing manifest instead of overwriting",
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

    # extract-structured subcommand
    p_struct = subparsers.add_parser(
        "extract-structured",
        help="Extract structured Schema v2.3 JSON from text using LLM",
    )
    p_struct.add_argument(
        "--text-dir",
        default="data/raw",
        help="Directory containing extracted text files (scans subdirs)",
    )
    p_struct.add_argument(
        "--out-dir",
        default="data/structured/incidents",
        help="Output directory for structured JSON",
    )
    p_struct.add_argument(
        "--manifest",
        default="data/structured/structured_manifest.csv",
        help="Output manifest path",
    )
    p_struct.add_argument(
        "--provider",
        default="stub",
        choices=["stub", "openai", "anthropic", "gemini"],
        help="LLM provider to use",
    )
    p_struct.add_argument(
        "--model", default=None, help="Model identifier (e.g. gpt-4o, claude-sonnet-4-5-20250929)"
    )
    p_struct.add_argument(
        "--max-output-tokens", type=int, default=4096, help="Max output tokens for LLM"
    )
    p_struct.add_argument(
        "--temperature", type=float, default=0.0, help="Sampling temperature"
    )
    p_struct.add_argument(
        "--timeout", type=int, default=120, help="LLM request timeout in seconds"
    )
    p_struct.add_argument(
        "--retries", type=int, default=2, help="Retry count on transient failures"
    )
    p_struct.add_argument(
        "--limit", type=int, default=None, help="Max number of files to process"
    )
    p_struct.add_argument(
        "--resume", action="store_true", help="Skip files with existing output JSON"
    )
    p_struct.set_defaults(func=cmd_extract_structured)

    # convert-schema subcommand
    p_convert = subparsers.add_parser(
        "convert-schema",
        help="Normalise extracted JSON to conform to Schema v2.3",
    )
    p_convert.add_argument(
        "--incident-dir",
        required=True,
        help="Source directory with extracted JSON files",
    )
    p_convert.add_argument(
        "--out-dir",
        required=True,
        help="Destination directory for normalised JSON",
    )
    p_convert.set_defaults(func=cmd_convert_schema)

    # schema-check subcommand
    p_schema = subparsers.add_parser(
        "schema-check", help="Validate extracted JSON against Schema v2.3"
    )
    p_schema.add_argument(
        "--incident-dir",
        default="data/structured/incidents/schema_v2_3",
        help="Directory with extracted JSON files",
    )
    p_schema.set_defaults(func=cmd_schema_check)

    # quality-gate subcommand
    p_qg = subparsers.add_parser(
        "quality-gate", help="Report quality metrics on structured extractions"
    )
    p_qg.add_argument(
        "--incident-dir",
        default="data/structured/incidents/schema_v2_3",
        help="Directory with extracted JSON files",
    )
    p_qg.set_defaults(func=cmd_quality_gate)

    # extract-qc subcommand
    p_eqc = subparsers.add_parser(
        "extract-qc",
        help="Run extraction QC: multi-pass PDF extraction with quality gating",
    )
    p_eqc.add_argument(
        "--pdf-dir",
        required=True,
        help="Directory containing PDF files",
    )
    p_eqc.add_argument(
        "--output-dir",
        default="data/processed/text",
        help="Output directory for normalized text files",
    )
    p_eqc.add_argument(
        "--manifest",
        default="data/processed/extraction_manifest.csv",
        help="Path for extraction manifest CSV",
    )
    p_eqc.add_argument(
        "--force",
        action="store_true",
        help="Reprocess all PDFs even if already in manifest",
    )
    p_eqc.set_defaults(func=cmd_extract_qc)

    # ingest-source subcommand
    p_ingest = subparsers.add_parser(
        "ingest-source",
        help="Ingest PDFs from URL list or local directory into text + manifest",
    )
    p_ingest.add_argument(
        "--source", required=True, help="Source identifier (e.g. phmsa)"
    )
    p_ingest.add_argument(
        "--url-list",
        default=None,
        help="Path to CSV with url,doc_id columns",
    )
    p_ingest.add_argument(
        "--input-pdf-dir",
        default=None,
        help="Path to directory containing local PDF files",
    )
    p_ingest.add_argument(
        "--output-root",
        default=None,
        help="Output root directory (default: data/raw/<source>/)",
    )
    p_ingest.add_argument(
        "--force",
        action="store_true",
        help="Re-process items even if already completed",
    )
    p_ingest.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Download timeout in seconds (for URL mode)",
    )
    p_ingest.set_defaults(func=cmd_ingest_source)

    # discover-source subcommand
    p_discover = subparsers.add_parser(
        "discover-source",
        help="Discover incident report PDF URLs from a public source",
    )
    p_discover.add_argument(
        "--source",
        required=True,
        choices=["csb", "bsee", "phmsa"],
        help="Source to discover (csb, bsee, phmsa)",
    )
    p_discover.add_argument(
        "--out",
        default=None,
        help="Output url_list CSV path (default: data/sources/<source>/url_list.csv)",
    )
    p_discover.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of reports to discover",
    )
    p_discover.add_argument(
        "--base-url",
        default=None,
        help="Override base URL for the source website",
    )
    p_discover.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP request timeout in seconds",
    )
    p_discover.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Delay between requests in seconds (polite crawling)",
    )
    p_discover.set_defaults(func=cmd_discover_source)

    args = parser.parse_args()

    if args.command is None:
        # Default: original behavior (backwards compat)
        cmd_process(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
