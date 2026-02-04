from datetime import date as dt
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class Incident(BaseModel):
    """
    Oil and gas incident data model.
    """
    incident_id: str
    date: Optional[dt] = None
    location: Optional[str] = None
    facility_type: Optional[str] = None

    incident_type: Optional[str] = None
    severity: Optional[str] = None
    description: str

    # Bowtie components
    hazard: Optional[str] = None
    top_event: Optional[str] = None
    causes: List[str] = Field(default_factory=list)
    consequences: List[str] = Field(default_factory=list)
    prevention_barriers: List[str] = Field(default_factory=list)
    mitigation_barriers: List[str] = Field(default_factory=list)

    # Impact
    injuries: Optional[int] = Field(None, ge=0)
    fatalities: Optional[int] = Field(None, ge=0)
    environmental_impact: Optional[str] = None

    source: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "incident_id": "INC-2024-001",
                "date": "2024-01-15",
                "location": "Gulf of Mexico",
                "facility_type": "Offshore Platform",
                "incident_type": "Gas Release",
                "severity": "Major",
                "description": "Uncontrolled gas release from wellhead...",
                "hazard": "Hydrocarbon Release",
                "top_event": "Loss of Containment",
                "causes": ["Equipment failure", "Corrosion"],
                "consequences": ["Fire", "Platform evacuation"],
                "injuries": 2,
                "fatalities": 0,
                "source": "BSEE Investigation Report"
            }
        }
    )
