"""Canonical Gateway domain model.

The canonical model stores stable identity and typed relations between engineering
objects. Source-system-specific data remains in the authoritative external system.
"""

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ElementKind(StrEnum):
    """Broad canonical categories used by profiles."""

    REQUIREMENT = "requirement"
    ARCHITECTURE = "architecture"
    SAFETY = "safety"
    VERIFICATION = "verification"
    CHANGE = "change"
    CONFIGURATION = "configuration"
    GOVERNANCE = "governance"


class RelationType(StrEnum):
    """Typed relations in the cross-system engineering graph."""

    DERIVES_FROM = "derives_from"
    SATISFIES = "satisfies"
    ALLOCATED_TO = "allocated_to"
    VERIFIED_BY = "verified_by"
    MITIGATES = "mitigates"
    AFFECTS = "affects"
    IMPLEMENTS = "implements"
    REFINES = "refines"
    DEPENDS_ON = "depends_on"
    GOVERNS = "governs"


class EngineeringElement(BaseModel):
    """Gateway identity/reference for an engineering object.

    This model deliberately does not mirror the complete object held by StrictDoc,
    Capella, OpenProject or Git.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    kind: ElementKind
    type_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    external_system: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    source_uri: str | None = None


class EngineeringRelation(BaseModel):
    """A directed, typed edge between canonical engineering elements."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    relation_type: RelationType
    target_id: UUID


class EngineeringGraph(BaseModel):
    """A transport model for a set of canonical elements and relations."""

    model_config = ConfigDict(extra="forbid")

    elements: list[EngineeringElement] = Field(default_factory=list)
    relations: list[EngineeringRelation] = Field(default_factory=list)
