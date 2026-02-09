"""Validation utilities for Schema v2.3 incident payloads."""

from typing import Any

from pydantic import ValidationError

from src.models.incident_v2_2 import IncidentV2_2


def validate_incident_v2_2(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate a dict against the Schema v2.3 incident schema.

    Returns:
        Tuple of (is_valid, list_of_error_messages).
    """
    try:
        IncidentV2_2.model_validate(payload)
        return True, []
    except ValidationError as e:
        errors = []
        for err in e.errors():
            loc = " -> ".join(str(x) for x in err["loc"])
            errors.append(f"{loc}: {err['msg']}")
        return False, errors
