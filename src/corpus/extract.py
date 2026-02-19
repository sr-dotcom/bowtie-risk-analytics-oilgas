"""corpus_v1 Claude extraction for needs_extraction entries.

Reads corpus_v1_manifest.csv, skips entries with extraction_status=ready,
loads incident text, calls the provider, writes JSON to structured_json/.

Retry / escalation strategy
----------------------------
1. Primary provider (haiku, 8192 output tokens) — up to ``primary_retries`` attempts.
   If stop_reason is "max_tokens" OR JSON parsing fails, the attempt is considered
   incomplete and retried.
2. Escalated provider (same model, 16000 output tokens) — if all primary attempts
   fail or are truncated.
3. Fallback provider (sonnet, 16000 output tokens) — if escalated also fails.
"""
import csv
import json
import logging
import pathlib
import time
from typing import Sequence

from src.ingestion.normalize import normalize_v23_payload
from src.ingestion.structured import _parse_llm_json
from src.llm.base import LLMProvider
from src.llm.model_policy import ModelPolicy
from src.prompts.loader import load_prompt
from src.validation.incident_validator import validate_incident_v23

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


def _attempt_extraction(
    incident_id: str,
    prompt: str,
    provider: LLMProvider,
) -> tuple[dict | None, bool]:
    """Single extraction attempt against one provider.

    Returns:
        (data, was_truncated): data is None on API/parse failure;
        was_truncated is True when stop_reason == "max_tokens".
    """
    try:
        raw = provider.extract(prompt)
    except Exception as exc:
        logger.warning(f"  {incident_id}: API call failed — {exc}")
        return None, False

    stop_reason = getattr(provider, "last_meta", {}).get("stop_reason", "end_turn")
    truncated = stop_reason == "max_tokens"

    try:
        data = _parse_llm_json(raw)
        if truncated:
            logger.warning(
                f"  {incident_id}: output hit max_tokens limit — response incomplete"
            )
        return data, truncated
    except Exception as exc:
        logger.warning(f"  {incident_id}: JSON parse failed — {exc}")
        return None, truncated


def run_corpus_extraction(
    manifest_path: pathlib.Path,
    structured_dir: pathlib.Path,
    text_search_dirs: Sequence[pathlib.Path] | None,
    provider: LLMProvider,
    delay_seconds: float = 30.0,
    text_limit: int = 50_000,
    primary_retries: int = 3,
    escalated_provider: LLMProvider | None = None,
    fallback_provider: LLMProvider | None = None,
) -> int:
    """Extract JSONs for all needs_extraction rows in the manifest.

    Args:
        manifest_path:       Path to corpus_v1_manifest.csv.
        structured_dir:      Where to write output JSON files.
        text_search_dirs:    Ordered list of dirs to search for .txt files.
                             Defaults to CSB then BSEE text dirs.
        provider:            Primary LLM provider (e.g. Haiku, 8192 tokens).
        delay_seconds:       Minimum seconds to sleep after each successful
                             API call.  The actual wait is max(delay_seconds,
                             rate_limit_wait) based on estimated input tokens.
                             Default 30 s.
        text_limit:          Truncate incident text to this many characters
                             before building the prompt.  0 = no limit.
                             Default 50 000 chars (~12 500 tokens).
        primary_retries:     Attempts with the primary provider before
                             escalating.  Default 3.
        escalated_provider:  Provider with higher max_output_tokens (e.g.
                             Haiku, 16000).  Used when primary is truncated.
        fallback_provider:   Provider to use when primary + escalated both
                             fail (e.g. Sonnet, 16000).

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

        # ── load text ──────────────────────────────────────────────────────
        try:
            text = _load_incident_text(incident_id, text_search_dirs)
        except Exception as exc:
            logger.error(f"  {incident_id}: extraction failed — {exc}")
            continue

        if not text.strip():
            logger.warning(f"  {incident_id}: text file is blank, skipping.")
            continue

        original_len = len(text)
        if text_limit > 0 and original_len > text_limit:
            text = text[:text_limit]
            logger.info(
                f"  {incident_id}: text truncated {original_len} → {text_limit} chars"
            )

        # ── build prompt ───────────────────────────────────────────────────
        try:
            prompt = load_prompt(incident_text=text)
        except Exception as exc:
            logger.error(f"  {incident_id}: prompt build failed — {exc}")
            continue

        # ── Phase 1: primary provider (haiku, 8192 tokens) ────────────────
        data: dict | None = None
        for attempt in range(1, primary_retries + 1):
            data, truncated = _attempt_extraction(incident_id, prompt, provider)
            if data is not None and not truncated:
                break
            logger.warning(
                f"  {incident_id}: primary attempt {attempt}/{primary_retries} "
                f"incomplete (truncated={truncated})"
            )
            data = None  # discard truncated partial JSON; force retry

        # ── Phase 2: escalated provider (haiku, 16000 tokens) ─────────────
        if data is None and escalated_provider is not None:
            logger.info(f"  {incident_id}: escalating to higher output tokens")
            for attempt in range(1, primary_retries + 1):
                data, truncated = _attempt_extraction(
                    incident_id, prompt, escalated_provider
                )
                if data is not None and not truncated:
                    break
                data = None

        # ── Phase 3: fallback provider (sonnet, 16000 tokens) ─────────────
        if data is None and fallback_provider is not None:
            logger.info(f"  {incident_id}: falling back to Sonnet")
            data, _ = _attempt_extraction(incident_id, prompt, fallback_provider)

        if data is None:
            logger.error(
                f"  {incident_id}: extraction failed after all retries/fallbacks"
            )
            continue

        # ── normalise to canonical V2.3 before writing ─────────────────────
        data["incident_id"] = incident_id
        normalize_v23_payload(data)
        is_valid, val_errors = validate_incident_v23(data)
        if not is_valid:
            logger.warning(
                f"  {incident_id}: schema validation failed after normalisation "
                f"({len(val_errors)} error(s)); writing anyway. "
                f"First error: {val_errors[0] if val_errors else 'unknown'}"
            )

        out_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"  {incident_id}: extracted OK → {out_path.name}")
        extracted += 1

        if delay_seconds > 0:
            # Dynamic wait based on the TRUNCATED text length (reflects actual
            # tokens sent).  Rate limit: 30 k input tokens/min → 65 s/window.
            text_tokens_est = len(text) / 4
            rate_limit_wait = (text_tokens_est / 30_000) * 65
            actual_wait = max(delay_seconds, rate_limit_wait)
            logger.info(
                f"  Waiting {actual_wait:.0f}s (est. {text_tokens_est:.0f} tokens)."
            )
            time.sleep(actual_wait)

    logger.info(f"corpus-extract: done. {extracted}/{len(pending)} extracted.")
    return extracted
