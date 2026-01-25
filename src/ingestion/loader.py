import re
from datetime import datetime
from typing import Optional
from src.models.incident import Incident

def load_incident_from_text(text: str) -> Incident:
    """
    Parses a raw text block into an Incident model.

    Expected format (keys are case-insensitive):
    ID: <value>
    Date: YYYY-MM-DD
    Description: <value>

    Args:
        text: Raw text containing incident details.

    Returns:
        Incident: Populated incident model.

    Raises:
        ValueError: If required fields (ID, Description) are missing.
    """
    # Simple line-based parsing
    lines = text.strip().split('\n')
    data = {}

    current_key = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for Key: Value pattern
        match = re.match(r'^([A-Za-z\s]+):\s*(.*)', line)
        if match:
            key = match.group(1).lower().strip()
            value = match.group(2).strip()
            data[key] = value
            current_key = key
        elif current_key and current_key == 'description':
            # Append continuation lines to description
            data['description'] += " " + line

    if 'id' not in data:
        raise ValueError("Missing required field: ID")

    if 'description' not in data:
        raise ValueError("Missing required field: Description")

    incident_date = None
    if 'date' in data:
        try:
            incident_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            # For now, just ignore invalid dates or let it be None
            pass

    # Parse lists (comma-separated)
    prevention_barriers = [b.strip() for b in data.get('prevention barriers', '').split(',') if b.strip()]
    mitigation_barriers = [b.strip() for b in data.get('mitigation barriers', '').split(',') if b.strip()]

    return Incident(
        incident_id=data['id'],
        date=incident_date,
        description=data['description'],
        prevention_barriers=prevention_barriers,
        mitigation_barriers=mitigation_barriers
    )
