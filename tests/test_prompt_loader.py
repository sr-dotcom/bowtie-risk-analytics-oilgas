"""Tests for the prompt template loader."""
from pathlib import Path

import pytest

from src.prompts.loader import load_prompt


def test_load_prompt_substitutes_placeholders() -> None:
    """Both template placeholders are replaced and incident text appears in output."""
    result = load_prompt("test incident text")
    assert "{{SCHEMA_TEMPLATE}}" not in result
    assert "{{INCIDENT_TEXT}}" not in result
    assert "test incident text" in result


def test_load_prompt_contains_schema() -> None:
    """Schema content from the JSON template appears in the assembled prompt."""
    result = load_prompt("test incident text")
    # The schema template contains recognisable keys
    assert "incident_id" in result
    assert "control_id" in result
    assert "barrier_status" in result


def test_load_prompt_empty_text_raises() -> None:
    """Empty string raises ValueError."""
    with pytest.raises(ValueError, match="incident_text must not be empty"):
        load_prompt("")


def test_load_prompt_whitespace_text_raises() -> None:
    """Whitespace-only string raises ValueError."""
    with pytest.raises(ValueError, match="incident_text must not be empty"):
        load_prompt("   \n\t  ")


def test_load_prompt_missing_prompt_file() -> None:
    """Nonexistent prompt path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Prompt template not found"):
        load_prompt(
            "some text",
            prompt_path=Path("/nonexistent/prompt.md"),
        )


def test_load_prompt_missing_schema_file() -> None:
    """Nonexistent schema path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Schema template not found"):
        load_prompt(
            "some text",
            schema_path=Path("/nonexistent/schema.json"),
        )


def test_load_prompt_default_paths() -> None:
    """Calling with just incident_text uses default paths and produces valid output."""
    result = load_prompt("A gas leak occurred at the offshore platform.")
    assert isinstance(result, str)
    assert len(result) > 0
    assert "A gas leak occurred at the offshore platform." in result
    # Should contain content from both the prompt template and the schema
    assert "Bowtie" in result
    assert "schema_version" in result


def test_prompt_contains_enum_constraints() -> None:
    """Assembled prompt must include explicit enum constraint section."""
    result = load_prompt("Some incident text.")
    # Section header
    assert "Enum Constraints" in result
    # Each enum field with its allowed values
    assert "`engineering`, `administrative`, `ppe`, `unknown`" in result
    assert "`1st`, `2nd`, `3rd`, `recovery`, `unknown`" in result
    assert "`active`, `degraded`, `failed`, `bypassed`, `not_installed`, `unknown`" in result
    assert "`high`, `medium`, `low`" in result
    assert "`prevention`, `mitigation`" in result
    # Anti-synonym instruction
    assert "Do not invent new categories" in result


def test_prompt_contains_required_fields_section() -> None:
    """Assembled prompt must include required fields for hazards/threats/consequences."""
    result = load_prompt("Some incident text.")
    assert "Required Fields" in result
    assert "hazard_id" in result
    assert "threat_id" in result
    assert "consequence_id" in result
    assert "H-001" in result
    assert "T-001" in result
    assert "CON-001" in result
