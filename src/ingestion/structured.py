"""Structured extraction: text -> LLM -> validated JSON."""
import csv
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.llm.base import LLMProvider
from src.prompts.loader import load_prompt
from src.validation.incident_validator import validate_incident_v2_2

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


def merge_structured_manifests(
    existing: list[StructuredManifestRow],
    new: list[StructuredManifestRow],
) -> list[StructuredManifestRow]:
    """Merge manifest rows, upserting by incident_id (new wins)."""
    by_id: dict[str, StructuredManifestRow] = {}
    for row in existing:
        by_id[row.incident_id] = row
    for row in new:
        by_id[row.incident_id] = row
    return list(by_id.values())


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
    raw_dir = base_dir / "raw" / provider_name
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{incident_id}.txt"
    raw_path.write_text(raw, encoding="utf-8")
    return raw_path


def extract_structured(
    text_dir: Path,
    out_dir: Path,
    provider: LLMProvider,
    provider_name: str = "unknown",
    model_name: Optional[str] = None,
    limit: Optional[int] = None,
    resume: bool = False,
) -> list[StructuredManifestRow]:
    """Run structured extraction on all .txt files in text_dir.

    Args:
        text_dir: Directory containing extracted text files.
        out_dir: Directory to write validated JSON files.
        provider: LLM provider instance.
        provider_name: Name of the provider for manifest tracking.
        model_name: Model identifier for manifest tracking.
        limit: Max number of files to process (None = all).
        resume: If True, skip files that already have output JSON.

    Returns:
        List of manifest rows tracking extraction results.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[StructuredManifestRow] = []

    txt_files = sorted(text_dir.glob("*.txt"))
    if not txt_files:
        logger.warning(f"No .txt files found in {text_dir}")
        return rows

    logger.info(f"Processing {len(txt_files)} text files with provider={provider_name}")

    processed = 0
    for txt_path in txt_files:
        incident_id = txt_path.stem
        json_path = out_dir / f"{incident_id}.json"

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

            # Assemble prompt and call LLM
            prompt = load_prompt(text)
            raw_response = provider.extract(prompt)

            # Save raw response
            raw_path = _save_raw_response(
                raw_response, provider_name, incident_id, out_dir.parent,
            )
            row.raw_response_path = str(raw_path)

            # Parse JSON from response
            try:
                payload = _parse_llm_json(raw_response)
            except json.JSONDecodeError as parse_err:
                # Write error JSON preserving identifiers
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

            # Override incident_id with filename-based ID
            payload["incident_id"] = incident_id

            # Validate
            is_valid, errors = validate_incident_v2_2(payload)
            row.valid = is_valid
            row.extracted = True
            row.extracted_at = datetime.now(timezone.utc)

            if not is_valid:
                row.validation_errors = "; ".join(errors[:5])  # Cap at 5 errors
                logger.warning(f"{incident_id}: validation failed: {errors[:3]}")
                # Attach errors into payload for downstream visibility
                payload["_validation_errors"] = errors

            # Write JSON regardless (for debugging)
            json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            logger.info(f"{incident_id}: extracted (valid={is_valid})")

        except Exception as e:
            row.error = str(e)[:200]
            logger.error(f"{incident_id}: extraction failed: {e}")

        rows.append(row)
        processed += 1

    return rows
