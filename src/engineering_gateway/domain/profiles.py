"""Declarative standard-profile domain model.

Profiles describe engineering semantics and governance rules without coupling the
Gateway core to a particular standard. Multiple profiles can be composed.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from engineering_gateway.domain.models import ElementKind, RelationType


class AttributeType(StrEnum):
    """Supported scalar attribute types in a profile definition."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"


class AttributeDefinition(BaseModel):
    """Definition of a profile-defined element attribute."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type: AttributeType
    required: bool = False
    description: str | None = None


class ElementTypeDefinition(BaseModel):
    """Profile-defined semantic type for a canonical engineering element."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: ElementKind
    attributes: list[AttributeDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_attributes(self) -> "ElementTypeDefinition":
        ids = [attribute.id for attribute in self.attributes]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate attributes in element type '{self.id}'")
        return self


class RelationDefinition(BaseModel):
    """Allowed typed relation between profile element types."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    relation_type: RelationType
    source_type_ids: list[str] = Field(min_length=1)
    target_type_ids: list[str] = Field(min_length=1)


class LifecycleDefinition(BaseModel):
    """Lifecycle states and allowed transitions for a profile element type."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    element_type_id: str = Field(min_length=1)
    states: list[str] = Field(min_length=1)
    transitions: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_transitions(self) -> "LifecycleDefinition":
        states = set(self.states)
        if len(states) != len(self.states):
            raise ValueError(f"duplicate lifecycle states in '{self.id}'")
        invalid = {
            target
            for targets in self.transitions.values()
            for target in targets
            if target not in states
        }
        invalid.update(source for source in self.transitions if source not in states)
        if invalid:
            raise ValueError(f"lifecycle '{self.id}' references unknown states: {sorted(invalid)}")
        return self


class ArtifactRequirement(BaseModel):
    """Artifact that must exist for an element type under a profile."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    element_type_id: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    required: bool = True


class TraceabilityRule(BaseModel):
    """Required or forbidden traceability edge between element types."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    source_type_id: str = Field(min_length=1)
    relation_type: RelationType
    target_type_id: str = Field(min_length=1)
    required: bool = True


class VerificationRule(BaseModel):
    """Declarative verification constraint associated with an element type."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    element_type_id: str = Field(min_length=1)
    required_relation_type: RelationType
    verification_type_id: str = Field(min_length=1)


class StandardProfile(BaseModel):
    """Complete, versioned, declarative standard profile."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    element_types: list[ElementTypeDefinition] = Field(default_factory=list)
    relations: list[RelationDefinition] = Field(default_factory=list)
    lifecycles: list[LifecycleDefinition] = Field(default_factory=list)
    artifacts: list[ArtifactRequirement] = Field(default_factory=list)
    traceability: list[TraceabilityRule] = Field(default_factory=list)
    verification: list[VerificationRule] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "StandardProfile":
        for name in (
            "element_types",
            "relations",
            "lifecycles",
            "artifacts",
            "traceability",
            "verification",
        ):
            definitions = getattr(self, name)
            ids = [item.id for item in definitions]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate ids in profile {name}")
        element_type_ids = {item.id for item in self.element_types}
        for relation in self.relations:
            unknown = (
                set(relation.source_type_ids) | set(relation.target_type_ids)
            ) - element_type_ids
            if unknown:
                raise ValueError(
                    f"relation '{relation.id}' references unknown types: {sorted(unknown)}"
                )
        for definition in self.lifecycles:
            if definition.element_type_id not in element_type_ids:
                raise ValueError(f"lifecycle '{definition.id}' references unknown element type")
        for artifact in self.artifacts:
            if artifact.element_type_id not in element_type_ids:
                raise ValueError(f"artifact '{artifact.id}' references unknown element type")
        return self
