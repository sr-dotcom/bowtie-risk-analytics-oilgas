"""corpus_v1 Claude extraction for needs_extraction entries.

Reads corpus_v1_manifest.csv, skips entries with extraction_status=ready,
loads incident text, calls the provider, writes JSON to structured_json/.
"""
import csv
import json
import logging
import pathlib
import time
from typing import Sequence

from src.ingestion.structured import _parse_llm_json
from src.llm.base import LLMProvider
from src.prompts.loader import load_prompt

logger = logging.getLogger(__name__)

# Default text search dirs (checked in order)
_DEFAULT_TEXT_DIRS: list[pathlib.Path] = [
    pathlib.Path("data/raw/csb/text"),
    pathlib.Path("data/raw/bsee/text"),
]


def _load_incident_text(
    incident_id: str,
    text_search_dirs: Sequence[pathlib.Path],
) -> str:
    """Return text content for incident_id, searching dirs in order.

    Raises:
        FileNotFoundError: if no .txt file is found in any search dir.
    """
    for d in text_search_dirs:
        candidate = d / f"{incident_id}.txt"
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"No text file found for '{incident_id}' in: {list(text_search_dirs)}"
    )


def run_corpus_extraction(
    manifest_path: pathlib.Path,
    structured_dir: pathlib.Path,
    text_search_dirs: Sequence[pathlib.Path] | None,
    provider: LLMProvider,
    delay_seconds: float = 15.0,
) -> int:
    """Extract JSONs for all needs_extraction rows in the manifest.

    Args:
        manifest_path: Path to corpus_v1_manifest.csv.
        structured_dir: Where to write output JSON files.
        text_search_dirs: Ordered list of dirs to search for .txt files.
                          Defaults to CSB then BSEE text dirs.
        provider: LLM provider to call.
        delay_seconds: Seconds to sleep between API calls (rate limit guard).
                       Default 15 s keeps well within 30 k tokens/min.

    Returns:
        Number of incidents successfully extracted.
    """
    if text_search_dirs is None:
        text_search_dirs = _DEFAULT_TEXT_DIRS

    structured_dir.mkdir(parents=True, exist_ok=True)

    with manifest_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    pending = [r for r in rows if r["extraction_status"] == "needs_extraction"]
    logger.info(f"corpus-extract: {len(pending)} entries to process.")

    extracted = 0
    for row in pending:
        incident_id = row["incident_id"]
        out_path    = structured_dir / f"{incident_id}.json"

        if out_path.exists():
            logger.info(f"  {incident_id}: already present, skipping.")
            continue

        try:
            text = _load_incident_text(incident_id, text_search_dirs)
        except Exception as exc:
            logger.error(f"  {incident_id}: extraction failed — {exc}")
            continue

        if not text.strip():
            logger.warning(f"  {incident_id}: text file is blank, skipping.")
            continue

        try:
            prompt = load_prompt(incident_text=text)
            raw    = provider.extract(prompt)
            data   = _parse_llm_json(raw)
        except Exception as exc:
            logger.error(f"  {incident_id}: extraction failed — {exc}")
            continue

        out_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"  {incident_id}: extracted OK → {out_path.name}")
        extracted += 1

        if delay_seconds > 0:
            # Dynamic wait: rate limit is 30k input tokens/min.
            # Estimate ~4 chars per token; budget 65 s per 30k-token window.
            text_tokens_est = len(text) / 4
            rate_limit_wait = (text_tokens_est / 30_000) * 65
            actual_wait = max(delay_seconds, rate_limit_wait)
            logger.info(
                f"  Waiting {actual_wait:.0f}s (est. {text_tokens_est:.0f} tokens)."
            )
            time.sleep(actual_wait)

    logger.info(f"corpus-extract: done. {extracted}/{len(pending)} extracted.")
    return extracted
