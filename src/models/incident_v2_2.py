"""Pydantic v2 models for Incident Schema v2.3."""

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------

class SourceInfo(BaseModel):
    """Document source metadata."""

    model_config = ConfigDict(strict=False)

    doc_type: str = Field(default="unknown", description="Type of source document")
    url: Optional[str] = Field(default=None, description="URL of the source document")
    title: str = Field(default="unknown", description="Title of the source document")
    date_published: Optional[str] = Field(
        default=None, description="Publication date (ISO-8601 string or free text)"
    )
    date_occurred: Optional[str] = Field(
        default=None, description="Date the incident occurred"
    )
    timezone: Optional[str] = Field(
        default=None, description="Timezone of the incident"
    )


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

class ContextInfo(BaseModel):
    """Operational context for the incident."""

    model_config = ConfigDict(strict=False)

    region: str = Field(default="unknown", description="Geographic region")
    operator: str = Field(default="unknown", description="Facility operator name")
    operating_phase: str = Field(
        default="unknown", description="Phase of operations during incident"
    )
    materials: list[str] = Field(
        default_factory=list, description="Materials involved"
    )

    @field_validator("operating_phase", mode="before")
    @classmethod
    def _stringify_operating_phase(cls, v: Any) -> str:
        if v is None:
            return "unknown"
        if isinstance(v, str):
            return v.lower().strip()
        if isinstance(v, list):
            return "; ".join(str(x) for x in v).lower()
        if isinstance(v, dict):
            import json as _json
            return _json.dumps(v)
        return str(v).lower()

    @field_validator("materials", mode="before")
    @classmethod
    def _coerce_materials(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, dict):
            # LLM returned object like {"type": "crude oil", ...} — extract non-null string values
            vals = [str(x) for x in v.values() if x is not None and str(x).strip()]
            return vals if vals else []
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return [str(x) for x in v]
        return [str(v)]


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

class EventInfo(BaseModel):
    """Top-level event details."""

    model_config = ConfigDict(strict=False)

    top_event: str = Field(default="unknown", description="Top event classification")
    incident_type: str = Field(default="unknown", description="Incident type")

    @model_validator(mode="before")
    @classmethod
    def _remap_keys(cls, data: Any) -> Any:
        """Remap common LLM key-drift to canonical schema names."""
        if not isinstance(data, dict):
            return data
        # event.type -> event.top_event
        if "type" in data and "top_event" not in data:
            data["top_event"] = data.pop("type")
        # event.description -> event.summary
        if "description" in data and "summary" not in data:
            data["summary"] = data.pop("description")
        # event.category -> event.incident_type
        if "category" in data and "incident_type" not in data:
            data["incident_type"] = data.pop("category")
        return data
    costs: Optional[Union[str, int, float]] = Field(
        default=None, description="Estimated costs"
    )

    @field_validator("top_event", mode="before")
    @classmethod
    def _stringify_top_event(cls, v: Any) -> str:
        if v is None:
            return "unknown"
        if isinstance(v, str):
            return v
        if isinstance(v, list):
            return "; ".join(str(x) for x in v)
        if isinstance(v, dict):
            import json as _json
            return _json.dumps(v)
        return str(v)

    @field_validator("costs", mode="before")
    @classmethod
    def _normalize_costs(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, dict):
            # Empty dict from LLM means "unknown"
            if not v:
                return None
            import json as _json
            return _json.dumps(v)
        return str(v)
    actions_taken: list[str] = Field(
        default_factory=list, description="Actions taken during/after the event"
    )
    summary: str = Field(default="", description="Narrative summary of the event")
    recommendations: list[str] = Field(
        default_factory=list, description="Investigation recommendations"
    )
    key_phrases: list[str] = Field(
        default_factory=list, description="Key phrases extracted from the report"
    )


# ---------------------------------------------------------------------------
# Bowtie elements
# ---------------------------------------------------------------------------

class HazardItem(BaseModel):
    """A hazard in the bowtie diagram."""

    model_config = ConfigDict(strict=False)

    hazard_id: str = Field(..., description="Unique hazard identifier")
    name: str = Field(..., description="Short name of the hazard")
    description: Optional[str] = Field(
        default=None, description="Detailed description"
    )


class ThreatItem(BaseModel):
    """A threat (cause) in the bowtie diagram."""

    model_config = ConfigDict(strict=False)

    threat_id: str = Field(..., description="Unique threat identifier")
    name: str = Field(..., description="Short name of the threat")
    description: Optional[str] = Field(
        default=None, description="Detailed description"
    )


class ConsequenceItem(BaseModel):
    """A consequence (outcome) in the bowtie diagram."""

    model_config = ConfigDict(strict=False)

    consequence_id: str = Field(..., description="Unique consequence identifier")
    name: str = Field(..., description="Short name of the consequence")
    description: Optional[str] = Field(
        default=None, description="Detailed description"
    )
    severity: Optional[str] = Field(default=None, description="Severity rating")


# ---------------------------------------------------------------------------
# Control sub-models
# ---------------------------------------------------------------------------

class ControlPerformance(BaseModel):
    """Performance attributes of a control/barrier."""

    model_config = ConfigDict(strict=False)

    barrier_status: Literal[
        "active", "degraded", "failed", "bypassed", "not_installed", "unknown"
    ] = Field(default="unknown", description="Current status of the barrier")
    barrier_failed: bool = Field(
        default=False, description="Whether the barrier failed"
    )
    detection_applicable: bool = Field(
        default=False, description="Whether detection is applicable to this barrier"
    )
    detection_mentioned: bool = Field(
        default=False, description="Whether detection was mentioned in the report"
    )
    alarm_applicable: bool = Field(
        default=False, description="Whether an alarm is applicable to this barrier"
    )
    alarm_mentioned: bool = Field(
        default=False, description="Whether an alarm was mentioned in the report"
    )
    manual_intervention_applicable: bool = Field(
        default=False,
        description="Whether manual intervention is applicable to this barrier",
    )
    manual_intervention_mentioned: bool = Field(
        default=False,
        description="Whether manual intervention was mentioned in the report",
    )


class ControlHuman(BaseModel):
    """Human-factors attributes of a control/barrier."""

    model_config = ConfigDict(strict=False)

    human_contribution_value: Optional[str] = Field(
        default=None, description="Description of human contribution"
    )
    human_contribution_mentioned: bool = Field(
        default=False, description="Whether human contribution was mentioned"
    )
    barrier_failed_human: bool = Field(
        default=False,
        description="Whether the barrier failure was due to human factors",
    )
    linked_pif_ids: list[str] = Field(
        default_factory=list,
        description="IDs of linked Performance Influencing Factors",
    )


class ControlEvidence(BaseModel):
    """Evidence supporting a control assessment."""

    model_config = ConfigDict(strict=False)

    supporting_text: list[str] = Field(
        default_factory=list,
        description="Excerpts from the source document supporting this assessment",
    )
    confidence: Literal["high", "medium", "low"] = Field(
        default="low", description="Confidence level of the assessment"
    )


class ControlItem(BaseModel):
    """A single control (barrier) in the bowtie diagram."""

    model_config = ConfigDict(strict=False)

    control_id: str = Field(..., description="Unique control identifier")
    name: str = Field(default="unknown", description="Name of the control")
    side: Literal["prevention", "mitigation"] = Field(
        default="prevention",
        description="Bowtie side: prevention (left) or mitigation (right)",
    )
    barrier_role: str = Field(default="unknown", description="Role of the barrier")
    barrier_type: Literal["engineering", "administrative", "ppe", "unknown"] = Field(
        default="unknown", description="Type of barrier"
    )
    line_of_defense: Literal["1st", "2nd", "3rd", "recovery", "unknown"] = Field(
        default="unknown", description="Line of defense"
    )
    lod_basis: Optional[str] = Field(
        default=None, description="Basis for line-of-defense classification"
    )
    linked_threat_ids: list[str] = Field(
        default_factory=list, description="IDs of linked threats"
    )
    linked_consequence_ids: list[str] = Field(
        default_factory=list, description="IDs of linked consequences"
    )
    performance: ControlPerformance = Field(default_factory=ControlPerformance)
    human: ControlHuman = Field(default_factory=ControlHuman)
    evidence: ControlEvidence = Field(default_factory=ControlEvidence)


# ---------------------------------------------------------------------------
# Bowtie container
# ---------------------------------------------------------------------------

class BowtieV2(BaseModel):
    """Full bowtie diagram structure for Schema v2.3."""

    model_config = ConfigDict(strict=False)

    hazards: list[HazardItem] = Field(
        default_factory=list, description="List of hazards"
    )
    threats: list[ThreatItem] = Field(
        default_factory=list, description="List of threats"
    )
    consequences: list[ConsequenceItem] = Field(
        default_factory=list, description="List of consequences"
    )
    controls: list[ControlItem] = Field(
        default_factory=list, description="List of controls/barriers"
    )


# ---------------------------------------------------------------------------
# Performance Influencing Factors (PIFs)
# ---------------------------------------------------------------------------

class PeoplePifs(BaseModel):
    """People-related Performance Influencing Factors."""

    model_config = ConfigDict(strict=False)

    competence_value: Optional[str] = Field(default=None)
    competence_mentioned: bool = Field(default=False)
    fatigue_value: Optional[str] = Field(default=None)
    fatigue_mentioned: bool = Field(default=False)
    communication_value: Optional[str] = Field(default=None)
    communication_mentioned: bool = Field(default=False)
    situational_awareness_value: Optional[str] = Field(default=None)
    situational_awareness_mentioned: bool = Field(default=False)


class WorkPifs(BaseModel):
    """Work-related Performance Influencing Factors."""

    model_config = ConfigDict(strict=False)

    procedures_value: Optional[str] = Field(default=None)
    procedures_mentioned: bool = Field(default=False)
    workload_value: Optional[str] = Field(default=None)
    workload_mentioned: bool = Field(default=False)
    time_pressure_value: Optional[str] = Field(default=None)
    time_pressure_mentioned: bool = Field(default=False)
    tools_equipment_value: Optional[str] = Field(default=None)
    tools_equipment_mentioned: bool = Field(default=False)


class OrganisationPifs(BaseModel):
    """Organisation-related Performance Influencing Factors."""

    model_config = ConfigDict(strict=False)

    safety_culture_value: Optional[str] = Field(default=None)
    safety_culture_mentioned: bool = Field(default=False)
    management_of_change_value: Optional[str] = Field(default=None)
    management_of_change_mentioned: bool = Field(default=False)
    supervision_value: Optional[str] = Field(default=None)
    supervision_mentioned: bool = Field(default=False)
    training_value: Optional[str] = Field(default=None)
    training_mentioned: bool = Field(default=False)


class PifsInfo(BaseModel):
    """All Performance Influencing Factors grouped by category."""

    model_config = ConfigDict(strict=False)

    people: PeoplePifs = Field(default_factory=PeoplePifs)
    work: WorkPifs = Field(default_factory=WorkPifs)
    organisation: OrganisationPifs = Field(default_factory=OrganisationPifs)


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

class NotesInfo(BaseModel):
    """Schema metadata and extraction rules."""

    model_config = ConfigDict(strict=False)

    rules: str = Field(
        default="JSON output only. mentioned fields must be evidence-based. Use null for unknown values.",
        description="Extraction rules for the LLM",
    )
    schema_version: str = Field(
        default="2.3", description="Schema version identifier"
    )


# ---------------------------------------------------------------------------
# Top-level incident model
# ---------------------------------------------------------------------------

class IncidentV2_2(BaseModel):
    """Complete Schema v2.3 incident record."""

    model_config = ConfigDict(strict=False)

    incident_id: str = Field(..., description="Unique incident identifier")
    source: SourceInfo = Field(default_factory=SourceInfo)
    context: ContextInfo = Field(default_factory=ContextInfo)
    event: EventInfo = Field(default_factory=EventInfo)
    bowtie: BowtieV2 = Field(default_factory=BowtieV2)
    pifs: PifsInfo = Field(default_factory=PifsInfo)
    notes: NotesInfo = Field(default_factory=NotesInfo)

    @model_validator(mode="before")
    @classmethod
    def _remap_top_level(cls, data: Any) -> Any:
        """Move misplaced top-level controls into bowtie.controls."""
        if not isinstance(data, dict):
            return data
        if "controls" in data and "bowtie" in data:
            bt = data["bowtie"]
            if isinstance(bt, dict) and not bt.get("controls"):
                bt["controls"] = data.pop("controls")
        elif "controls" in data and "bowtie" not in data:
            data["bowtie"] = {"controls": data.pop("controls")}
        return data
