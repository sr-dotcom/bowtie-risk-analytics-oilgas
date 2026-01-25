from typing import Optional, Literal
from pydantic import BaseModel, Field

class Threat(BaseModel):
    """
    Represents a potential cause or threat in the Bowtie diagram.
    """
    id: str = Field(..., description="Unique identifier for the threat")
    name: str = Field(..., description="Short name of the threat")
    description: Optional[str] = Field(None, description="Detailed description")


class Barrier(BaseModel):
    """
    Represents a barrier (control) in the Bowtie diagram.
    """
    id: str = Field(..., description="Unique identifier for the barrier")
    name: str = Field(..., description="Name of the barrier")
    description: Optional[str] = Field(None, description="Detailed description")
    type: Literal["prevention", "mitigation"] = Field(..., description="Type of barrier (left or right side)")
    effectiveness: Optional[str] = Field(None, description="Rated effectiveness of the barrier")


class Consequence(BaseModel):
    """
    Represents a consequence (outcome) in the Bowtie diagram.
    """
    id: str = Field(..., description="Unique identifier for the consequence")
    name: str = Field(..., description="Short name of the consequence")
    description: Optional[str] = Field(None, description="Detailed description")
    severity: Optional[str] = Field(None, description="Severity rating")


class Bowtie(BaseModel):
    """
    Represents the full Bowtie diagram structure.
    """
    hazard: str = Field(..., description="The primary hazard")
    top_event: str = Field(..., description="The top event (loss of control)")
    threats: list[Threat] = Field(default_factory=list, description="List of threats")
    barriers: list[Barrier] = Field(default_factory=list, description="List of barriers")
    consequences: list[Consequence] = Field(default_factory=list, description="List of consequences")
