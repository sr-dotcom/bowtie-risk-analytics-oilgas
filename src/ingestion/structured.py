"""Structured extraction: text -> LLM -> validated JSON."""
import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from typing import Any, Callable, Optional

from pydantic import BaseModel, ConfigDict

from src.llm.base import LLMProvider
from src.models.incident_v23 import IncidentV23
from src.prompts.loader import load_prompt
from src.validation.incident_validator import validate_incident_v23

logger = logging.getLogger(__name__)


class StructuredManifestRow(BaseModel):
    """Tracks structured extraction results."""
    model_config = ConfigDict(extra="ignore")

    incident_id: str
    source_text_path: str
    output_json_path: str
    provider: str
    model: Optional[str] = None
    extracted: bool = False
    extracted_at: Optional[datetime] = None
    valid: bool = False
    validation_errors: Optional[str] = None
    error: Optional[str] = None
    raw_response_path: Optional[str] = None


def load_structured_manifest(path: Path) -> list[StructuredManifestRow]:
    """Load structured extraction manifest from CSV."""
    if not path.exists():
        return []

    rows: list[StructuredManifestRow] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row_dict in reader:
            # Convert string booleans
            for key in ("extracted", "valid"):
                if key in row_dict:
                    row_dict[key] = row_dict[key].lower() == "true"
            # Parse datetime
            if "extracted_at" in row_dict and row_dict["extracted_at"]:
                row_dict["extracted_at"] = datetime.fromisoformat(
                    row_dict["extracted_at"]
                )
            elif "extracted_at" in row_dict:
                row_dict["extracted_at"] = None
            # Handle empty optional strings → None
            for key in ("model", "validation_errors", "error", "raw_response_path"):
                if key in row_dict and row_dict[key] == "":
                    row_dict[key] = None
            rows.append(StructuredManifestRow(**row_dict))
    return rows


def _manifest_key(row: StructuredManifestRow) -> tuple[str, str]:
    """Composite key for manifest upsert: (incident_id, provider)."""
    return (row.incident_id, row.provider)


def merge_structured_manifests(
    existing: list[StructuredManifestRow],
    new: list[StructuredManifestRow],
) -> list[StructuredManifestRow]:
    """Merge manifest rows, upserting by (incident_id, provider). New wins."""
    by_key: dict[tuple[str, str], StructuredManifestRow] = {}
    for row in existing:
        by_key[_manifest_key(row)] = row
    for row in new:
        by_key[_manifest_key(row)] = row
    return list(by_key.values())


def save_structured_manifest(rows: list[StructuredManifestRow], path: Path) -> None:
    """Save structured extraction manifest to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(StructuredManifestRow.model_fields.keys())

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row_dict = row.model_dump()
            if row_dict["extracted_at"]:
                row_dict["extracted_at"] = row_dict["extracted_at"].isoformat()
            row_dict = {k: ("" if v is None else v) for k, v in row_dict.items()}
            row_dict["extracted"] = str(row_dict["extracted"])
            row_dict["valid"] = str(row_dict["valid"])
            writer.writerow(row_dict)


def _parse_llm_json(raw: str) -> dict:
    """Extract JSON from LLM response with fallback strategies.

    1. Try ``json.loads`` on the stripped response.
    2. Strip markdown fences and retry.
    3. Extract the first ``{...}`` block via brace-matching and retry.

    Raises:
        json.JSONDecodeError: If all strategies fail.
    """
    text = raw.strip()

    # Strategy 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        try:
            return json.loads("\n".join(lines))
        except json.JSONDecodeError:
            pass

    # Strategy 3: extract first {...} block (brace-balanced)
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    return json.loads(candidate)  # let it raise if still bad

    raise json.JSONDecodeError("No JSON object found in LLM response", text, 0)


def _save_raw_response(
    raw: str, provider_name: str, incident_id: str, base_dir: Path,
) -> Path:
    """Persist the raw LLM response text and return the path."""
    raw_dir = base_dir / "debug_llm_responses" / provider_name
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{incident_id}.txt"
    raw_path.write_text(raw, encoding="utf-8")
    return raw_path


def extract_structured(
    text_dir: Path,
    out_dir: Path,
    provider: Optional[LLMProvider] = None,
    provider_name: str = "unknown",
    model_name: Optional[str] = None,
    limit: Optional[int] = None,
    resume: bool = False,
    text_limit: int = 0,
    _ladder_fn: Optional[Callable] = None,
) -> list[StructuredManifestRow]:
    """Run structured extraction on all .txt files in text_dir.

    Args:
        text_dir: Directory containing extracted text files.
        out_dir: Directory to write validated JSON files.
        provider: LLM provider instance (ignored when _ladder_fn is set).
        provider_name: Name of the provider for manifest tracking.
        model_name: Model identifier for manifest tracking.
        limit: Max number of files to process (None = all).
        resume: If True, skip files that already have output JSON.
        text_limit: Truncate text to this many chars before building the prompt
            (0 = no limit).  Matches corpus-extract --text-limit behaviour.
        _ladder_fn: Optional policy-driven ladder callable
            ``(incident_id, prompt, *, policy_path) -> (dict|None, bool, str|None)``.
            When set, replaces the single-provider extraction path with a
            multi-model ladder; every file still produces a manifest row.

    Returns:
        List of manifest rows tracking extraction results.
    """
    provider_out_dir = out_dir / provider_name
    provider_out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[StructuredManifestRow] = []

    # Scan directory and all subdirectories for .txt files
    txt_files = sorted(text_dir.rglob("*.txt"))
    if not txt_files:
        logger.warning(f"No .txt files found in {text_dir} (checked subdirs too)")
        return rows

    logger.info(f"Processing {len(txt_files)} text files with provider={provider_name}")

    processed = 0
    for txt_path in txt_files:
        incident_id = txt_path.stem
        json_path = provider_out_dir / f"{incident_id}.json"

        # Resume: skip already-extracted files
        if resume and json_path.exists():
            logger.info(f"{incident_id}: already extracted, skipping (--resume)")
            continue

        # Limit guard
        if limit is not None and processed >= limit:
            logger.info(f"Reached --limit={limit}, stopping.")
            break

        row = StructuredManifestRow(
            incident_id=incident_id,
            source_text_path=str(txt_path),
            output_json_path=str(json_path),
            provider=provider_name,
            model=model_name,
        )

        try:
            text = txt_path.read_text(encoding="utf-8")
            if not text.strip():
                row.error = "Empty text file"
                rows.append(row)
                processed += 1
                continue

            # Optional text truncation (mirrors corpus-extract --text-limit)
            if text_limit > 0 and len(text) > text_limit:
                logger.info(
                    f"{incident_id}: text truncated {len(text)} → {text_limit} chars"
                )
                text = text[:text_limit]

            # Assemble prompt
            prompt = load_prompt(text)

            # ── Extraction: ladder path or single-provider path ───────────────
            payload: Optional[dict] = None

            if _ladder_fn is not None:
                # Policy-driven model ladder — hard safety net, never raises
                try:
                    data, _truncated, model_used = _ladder_fn(incident_id, prompt)
                    row.model = model_used
                    payload = data
                except Exception as exc:
                    logger.exception(
                        f"{incident_id}: ladder raised unexpected error — {exc}"
                    )
                    payload = None

                if payload is None:
                    error_payload = {
                        "incident_id": incident_id,
                        "errors": ["ladder: all models failed or raised error"],
                    }
                    json_path.write_text(
                        json.dumps(error_payload, indent=2), encoding="utf-8"
                    )
                    row.extracted = True
                    row.extracted_at = datetime.now(timezone.utc)
                    row.valid = False
                    row.validation_errors = "ladder: all models failed"
                    rows.append(row)
                    processed += 1
                    logger.warning(f"{incident_id}: ladder failed — recorded in manifest")
                    continue

            else:
                # Single-provider path (backward-compatible)
                raw_response = provider.extract(prompt)  # type: ignore[union-attr]

                # Save raw response
                raw_path = _save_raw_response(
                    raw_response, provider_name, incident_id, out_dir.parent,
                )
                row.raw_response_path = str(raw_path)

                # Parse JSON from response (with one retry on parse failure)
                parse_err = None
                for _parse_attempt in range(2):
                    try:
                        payload = _parse_llm_json(raw_response)
                        break
                    except json.JSONDecodeError as e:
                        parse_err = e
                        if _parse_attempt == 0:
                            logger.warning(
                                f"{incident_id}: JSON parse failed, retrying with full prompt"
                            )
                            _STRICT_SUFFIX = (
                                "\n\nCRITICAL: Return ONLY a single valid JSON object. "
                                "No prose, no markdown fences, no explanation."
                            )
                            try:
                                raw_response = provider.extract(  # type: ignore[union-attr]
                                    prompt + _STRICT_SUFFIX
                                )
                                raw_path = _save_raw_response(
                                    raw_response, provider_name, incident_id,
                                    out_dir.parent,
                                )
                                row.raw_response_path = str(raw_path)
                            except Exception:
                                break  # retry failed, fall through

                if payload is None:
                    error_payload = {
                        "incident_id": incident_id,
                        "errors": [f"JSON parse error: {parse_err}"],
                        "raw": raw_response[:2000],
                    }
                    json_path.write_text(
                        json.dumps(error_payload, indent=2), encoding="utf-8",
                    )
                    row.extracted = True
                    row.extracted_at = datetime.now(timezone.utc)
                    row.valid = False
                    row.validation_errors = f"JSON parse error: {parse_err}"
                    rows.append(row)
                    processed += 1
                    logger.warning(f"{incident_id}: JSON parse failed: {parse_err}")
                    continue

            # ── Both paths converge here with payload set ─────────────────────
            # Override incident_id with filename-based ID
            payload["incident_id"] = incident_id

            # Validate
            is_valid, errors = validate_incident_v23(payload)
            row.valid = is_valid
            row.extracted = True
            row.extracted_at = datetime.now(timezone.utc)

            if not is_valid:
                row.validation_errors = "; ".join(errors[:5])  # Cap at 5 errors
                logger.warning(f"{incident_id}: validation failed: {errors[:3]}")
                payload["_validation_errors"] = errors

            # Round-trip through model to fill in all defaults/missing sections
            try:
                model = IncidentV23.model_validate(payload)
                out_payload = model.model_dump(mode="json")
            except Exception:
                # If model_validate fails, fall back to raw payload
                out_payload = payload

            # Preserve validation errors in output for debugging
            if "_validation_errors" in payload:
                out_payload["_validation_errors"] = payload["_validation_errors"]

            json_path.write_text(json.dumps(out_payload, indent=2), encoding="utf-8")
            logger.info(f"{incident_id}: extracted (valid={is_valid})")

        except Exception as e:
            row.error = str(e)[:200]
            logger.exception(f"{incident_id}: extraction failed: {e}")

        rows.append(row)
        processed += 1

    return rows


def generate_run_report(
    rows: list[StructuredManifestRow],
    provider_name: str,
    model_name: Optional[str] = None,
) -> dict[str, Any]:
    """Build a summary report dict from extraction manifest rows.

    Returns:
        Dict with totals, valid/invalid/parse_failed counts,
        and top validation error prefixes.
    """
    total = len(rows)
    extracted = sum(1 for r in rows if r.extracted)
    valid = sum(1 for r in rows if r.valid)
    invalid = sum(1 for r in rows if r.extracted and not r.valid)
    parse_failed = sum(
        1 for r in rows
        if r.validation_errors and r.validation_errors.startswith("JSON parse error")
    )
    errored = sum(1 for r in rows if r.error and not r.extracted)

    # Top validation errors by message prefix (first 60 chars)
    error_counter: Counter[str] = Counter()
    for r in rows:
        if r.validation_errors:
            for msg in r.validation_errors.split("; "):
                prefix = msg[:60]
                error_counter[prefix] += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider_name,
        "model": model_name,
        "total": total,
        "extracted": extracted,
        "valid": valid,
        "invalid": invalid,
        "parse_failed": parse_failed,
        "errored": errored,
        "valid_rate": round(valid / total, 3) if total else 0.0,
        "top_validation_errors": [
            {"message": msg, "count": cnt}
            for msg, cnt in error_counter.most_common(10)
        ],
    }


def compute_quality_gate(incident_dir: Path) -> dict[str, Any]:
    """Compute quality metrics over extracted incident JSON files.

    Returns:
        Dict with counts, percentages, and controls_count distribution
        (min, p50, p90, max).
    """
    json_files = sorted(incident_dir.glob("*.json"))
    total = len(json_files)
    if total == 0:
        return {"total": 0}

    has_controls = 0
    has_summary = 0
    has_pifs = 0
    has_hazards = 0
    has_threats = 0
    has_consequences = 0
    controls_counts: list[int] = []

    for jp in json_files:
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        bt = data.get("bowtie", {})
        n_controls = len(bt.get("controls", []))
        controls_counts.append(n_controls)
        if n_controls > 0:
            has_controls += 1
        if bt.get("hazards"):
            has_hazards += 1
        if bt.get("threats"):
            has_threats += 1
        if bt.get("consequences"):
            has_consequences += 1

        ev = data.get("event", {})
        if ev.get("summary"):
            has_summary += 1

        pifs = data.get("pifs", {})
        # pifs present if any *_mentioned field is True
        if not isinstance(pifs, dict):
            pifs_present = False
        else:
            pifs_present = any(
                v for cat in pifs.values() if isinstance(cat, dict)
                for k, v in cat.items() if k.endswith("_mentioned")
            )
        if pifs_present:
            has_pifs += 1

    def _pct(n: int) -> float:
        return round(n / total * 100, 1)

    def _percentile(data: list[int], pct: float) -> float:
        """Compute percentile without numpy."""
        if not data:
            return 0.0
        s = sorted(data)
        k = (len(s) - 1) * pct / 100.0
        f = int(k)
        c = f + 1 if f + 1 < len(s) else f
        return s[f] + (k - f) * (s[c] - s[f])

    return {
        "total": total,
        "has_controls": has_controls,
        "has_controls_pct": _pct(has_controls),
        "has_summary": has_summary,
        "has_summary_pct": _pct(has_summary),
        "has_pifs": has_pifs,
        "has_pifs_pct": _pct(has_pifs),
        "has_hazards": has_hazards,
        "has_hazards_pct": _pct(has_hazards),
        "has_threats": has_threats,
        "has_threats_pct": _pct(has_threats),
        "has_consequences": has_consequences,
        "has_consequences_pct": _pct(has_consequences),
        "controls_count_min": min(controls_counts) if controls_counts else 0,
        "controls_count_p50": round(_percentile(controls_counts, 50), 1),
        "controls_count_p90": round(_percentile(controls_counts, 90), 1),
        "controls_count_max": max(controls_counts) if controls_counts else 0,
    }
