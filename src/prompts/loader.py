"""Prompt template loader for incident extraction."""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "prompts" / "extract_incident.md"
_DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "schema" / "incident_schema_v2_3_template.json"


def load_prompt(
    incident_text: str,
    schema_path: Path | None = None,
    prompt_path: Path | None = None,
) -> str:
    """Assemble a complete LLM prompt from template, schema, and incident text.

    Args:
        incident_text: Raw incident narrative text.
        schema_path: Path to JSON schema template. Defaults to assets/schema/incident_schema_v2_3_template.json.
        prompt_path: Path to prompt template. Defaults to assets/prompts/extract_incident.md.

    Returns:
        Fully assembled prompt string with placeholders replaced.

    Raises:
        FileNotFoundError: If prompt or schema file doesn't exist.
        ValueError: If incident_text is empty.
    """
    if not incident_text or not incident_text.strip():
        raise ValueError("incident_text must not be empty")

    prompt_path = prompt_path or _DEFAULT_PROMPT_PATH
    schema_path = schema_path or _DEFAULT_SCHEMA_PATH

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema template not found: {schema_path}")

    prompt_template = prompt_path.read_text(encoding="utf-8")
    schema_template = schema_path.read_text(encoding="utf-8")

    result = prompt_template.replace("{{SCHEMA_TEMPLATE}}", schema_template)
    result = result.replace("{{INCIDENT_TEXT}}", incident_text)

    return result
