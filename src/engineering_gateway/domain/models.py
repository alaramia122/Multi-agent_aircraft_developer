"""Initial canonical-domain contracts.

These types intentionally contain stable Gateway concepts rather than vendor-specific
StrictDoc, Capella or OpenProject representations.
"""

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ElementKind(StrEnum):
    """Canonical Engineering Element categories defined by active profiles."""

    REQUIREMENT = "requirement"
    ARCHITECTURE = "architecture"
    SAFETY = "safety"
    VERIFICATION = "verification"
    CHANGE = "change"
    CONFIGURATION = "configuration"
    GOVERNANCE = "governance"


class EngineeringElement(BaseModel):
    """A Gateway reference to an engineering element.

    The Gateway keeps identity and external references. It does not copy the source
    system's complete engineering object into this model.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    kind: ElementKind
    type_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    external_system: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    source_uri: str | None = None
