"""Deterministic validation of canonical engineering state against a standard profile."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import UUID

from engineering_gateway.domain.models import EngineeringElement, EngineeringGraph, EngineeringRelation, RelationType
from engineering_gateway.domain.profiles import AttributeType, StandardProfile
from engineering_gateway.domain.traceability import TraceabilityGraph


class ValidationIssueCode:
    """Stable machine-readable validation finding codes."""

    UNKNOWN_ELEMENT_TYPE = "UNKNOWN_ELEMENT_TYPE"
    ELEMENT_KIND_MISMATCH = "ELEMENT_KIND_MISMATCH"
    DUPLICATE_ELEMENT_ID = "DUPLICATE_ELEMENT_ID"
    DUPLICATE_EXTERNAL_IDENTITY = "DUPLICATE_EXTERNAL_IDENTITY"
    UNKNOWN_ATTRIBUTE = "UNKNOWN_ATTRIBUTE"
    MISSING_REQUIRED_ATTRIBUTE = "MISSING_REQUIRED_ATTRIBUTE"
    INVALID_ATTRIBUTE_TYPE = "INVALID_ATTRIBUTE_TYPE"
    DANGLING_RELATION = "DANGLING_RELATION"
    FORBIDDEN_RELATION = "FORBIDDEN_RELATION"
    DUPLICATE_RELATION = "DUPLICATE_RELATION"
    MISSING_TRACEABILITY = "MISSING_TRACEABILITY"
    FORBIDDEN_TRACEABILITY = "FORBIDDEN_TRACEABILITY"
    MISSING_VERIFICATION = "MISSING_VERIFICATION"
    INVALID_LIFECYCLE_STATE = "INVALID_LIFECYCLE_STATE"
    INVALID_LIFECYCLE_TRANSITION = "INVALID_LIFECYCLE_TRANSITION"
    MISSING_ARTIFACT = "MISSING_ARTIFACT"


@dataclass(frozen=True)
class ValidationIssue:
    """A deterministic validation finding."""

    code: str
    message: str
    element_id: UUID | None = None
    relation_id: UUID | None = None
    rule_id: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    """Immutable, reproducible result of one validation execution."""

    profile_id: str
    profile_version: str
    graph_hash: str
    issues: tuple[ValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.issues


class DeterministicValidationEngine:
    """Validate canonical state and explicit authoritative validation evidence."""

    def validate(
        self,
        elements: list[EngineeringElement],
        relations: list[EngineeringRelation],
        profile: StandardProfile,
        *,
        attributes: dict[UUID, dict[str, object]] | None = None,
        artifact_evidence: set[tuple[UUID, str]] | frozenset[tuple[UUID, str]] = frozenset(),
        lifecycle_states: dict[UUID, str] | None = None,
        lifecycle_transitions: dict[UUID, tuple[str, str]] | None = None,
    ) -> ValidationResult:
        return self.validate_graph(EngineeringGraph(elements=elements, relations=relations), profile, attributes=attributes, artifact_evidence=artifact_evidence, lifecycle_states=lifecycle_states, lifecycle_transitions=lifecycle_transitions)

    def validate_graph(
        self,
        graph: EngineeringGraph,
        profile: StandardProfile,
        *,
        attributes: dict[UUID, dict[str, object]] | None = None,
        artifact_evidence: set[tuple[UUID, str]] | frozenset[tuple[UUID, str]] = frozenset(),
        lifecycle_states: dict[UUID, str] | None = None,
        lifecycle_transitions: dict[UUID, tuple[str, str]] | None = None,
    ) -> ValidationResult:
        """Validate graph plus explicit evidence without extending the canonical model."""
        issues: list[ValidationIssue] = []
        element_map: dict[UUID, EngineeringElement] = {}
        external_identities: dict[tuple[str, str], UUID] = {}
        type_definitions = {definition.id: definition for definition in profile.element_types}

        for element in graph.elements:
            if element.id in element_map:
                issues.append(ValidationIssue(ValidationIssueCode.DUPLICATE_ELEMENT_ID, f"Element id '{element.id}' occurs more than once", element_id=element.id))
            else:
                element_map[element.id] = element
            identity = (element.external_system, element.external_id)
            previous = external_identities.get(identity)
            if previous is not None and previous != element.id:
                issues.append(ValidationIssue(ValidationIssueCode.DUPLICATE_EXTERNAL_IDENTITY, f"External identity '{element.external_system}:{element.external_id}' is used by multiple elements", element_id=element.id))
            else:
                external_identities[identity] = element.id
            definition = type_definitions.get(element.type_id)
            if definition is None:
                issues.append(ValidationIssue(ValidationIssueCode.UNKNOWN_ELEMENT_TYPE, f"Element type '{element.type_id}' is not defined by the profile", element_id=element.id))
            elif element.kind is not definition.kind:
                issues.append(ValidationIssue(ValidationIssueCode.ELEMENT_KIND_MISMATCH, f"Element type '{element.type_id}' requires kind '{definition.kind}', got '{element.kind}'", element_id=element.id))

        self._validate_attributes(graph, type_definitions, attributes or {}, issues)
        allowed_pairs = {(relation.relation_type, source_type, target_type) for relation in profile.relations for source_type in relation.source_type_ids for target_type in relation.target_type_ids}
        seen_relations: set[tuple[UUID, RelationType, UUID]] = set()
        for relation in graph.relations:
            key = (relation.source_id, relation.relation_type, relation.target_id)
            if key in seen_relations:
                issues.append(ValidationIssue(ValidationIssueCode.DUPLICATE_RELATION, "Identical relation occurs more than once", relation_id=relation.id))
            seen_relations.add(key)
            source = element_map.get(relation.source_id)
            target = element_map.get(relation.target_id)
            if source is None or target is None:
                issues.append(ValidationIssue(ValidationIssueCode.DANGLING_RELATION, "Relation references an element that is not present in the graph", relation_id=relation.id))
                continue
            if (relation.relation_type, source.type_id, target.type_id) not in allowed_pairs:
                issues.append(ValidationIssue(ValidationIssueCode.FORBIDDEN_RELATION, f"Relation '{relation.relation_type}' is not allowed from '{source.type_id}' to '{target.type_id}'", relation_id=relation.id))

        traceability = TraceabilityGraph(graph.elements, graph.relations)
        for gap in traceability.traceability_violations(profile):
            issues.append(ValidationIssue(ValidationIssueCode.FORBIDDEN_TRACEABILITY if gap.forbidden else ValidationIssueCode.MISSING_TRACEABILITY, f"Traceability rule '{gap.rule_id}' is violated for element {gap.source_id}", element_id=gap.source_id, rule_id=gap.rule_id))
        self._validate_verification(graph, profile, element_map, issues)
        self._validate_lifecycle(profile, graph, element_map, lifecycle_states, lifecycle_transitions, issues)
        self._validate_artifacts(profile, graph, artifact_evidence, issues)
        issues.sort(key=_issue_sort_key)
        return ValidationResult(profile_id=profile.id, profile_version=profile.version, graph_hash=graph_hash(graph, profile, attributes=attributes, artifact_evidence=artifact_evidence, lifecycle_states=lifecycle_states, lifecycle_transitions=lifecycle_transitions), issues=tuple(issues))

    @staticmethod
    def _validate_attributes(graph: EngineeringGraph, type_definitions: dict[str, object], attributes: dict[UUID, dict[str, object]], issues: list[ValidationIssue]) -> None:
        for element in graph.elements:
            definition = type_definitions.get(element.type_id)
            if definition is None:
                continue
            definitions = {attribute.id: attribute for attribute in definition.attributes}
            values = attributes.get(element.id, {})
            for attribute_id in sorted(values):
                if attribute_id not in definitions:
                    issues.append(ValidationIssue(ValidationIssueCode.UNKNOWN_ATTRIBUTE, f"Attribute '{attribute_id}' is not defined for element type '{element.type_id}'", element_id=element.id))
            for attribute in definition.attributes:
                if attribute.required and attribute.id not in values:
                    issues.append(ValidationIssue(ValidationIssueCode.MISSING_REQUIRED_ATTRIBUTE, f"Required attribute '{attribute.id}' is missing for element '{element.id}'", element_id=element.id))
                elif attribute.id in values and not _attribute_value_matches(attribute.type, values[attribute.id]):
                    issues.append(ValidationIssue(ValidationIssueCode.INVALID_ATTRIBUTE_TYPE, f"Attribute '{attribute.id}' has an invalid value type for '{attribute.type}'", element_id=element.id))
        for element_id in sorted(set(attributes) - {element.id for element in graph.elements}, key=str):
            issues.append(ValidationIssue(ValidationIssueCode.UNKNOWN_ATTRIBUTE, f"Attributes are supplied for unknown element '{element_id}'", element_id=element_id))

    @staticmethod
    def _validate_verification(graph: EngineeringGraph, profile: StandardProfile, element_map: dict[UUID, EngineeringElement], issues: list[ValidationIssue]) -> None:
        outgoing: dict[UUID, list[EngineeringRelation]] = {}
        for relation in graph.relations:
            outgoing.setdefault(relation.source_id, []).append(relation)
        for rule in profile.verification:
            for element in graph.elements:
                if element.type_id != rule.element_type_id:
                    continue
                satisfied = any(relation.relation_type is rule.required_relation_type and element_map.get(relation.target_id) is not None and element_map[relation.target_id].type_id == rule.verification_type_id for relation in outgoing.get(element.id, ()))
                if not satisfied:
                    issues.append(ValidationIssue(ValidationIssueCode.MISSING_VERIFICATION, f"Verification rule '{rule.id}' requires relation '{rule.required_relation_type}' from element '{element.id}' to type '{rule.verification_type_id}'", element_id=element.id, rule_id=rule.id))

    @staticmethod
    def _validate_lifecycle(profile: StandardProfile, graph: EngineeringGraph, element_map: dict[UUID, EngineeringElement], lifecycle_states: dict[UUID, str] | None, lifecycle_transitions: dict[UUID, tuple[str, str]] | None, issues: list[ValidationIssue]) -> None:
        if profile.lifecycles and lifecycle_states is None:
            for lifecycle in profile.lifecycles:
                for element in graph.elements:
                    if element.type_id == lifecycle.element_type_id:
                        issues.append(ValidationIssue(ValidationIssueCode.INVALID_LIFECYCLE_STATE, f"Lifecycle '{lifecycle.id}' requires explicit state for element '{element.id}'", element_id=element.id, rule_id=lifecycle.id))
        if lifecycle_states is not None:
            for lifecycle in profile.lifecycles:
                for element in graph.elements:
                    if element.type_id == lifecycle.element_type_id and element.id not in lifecycle_states:
                        issues.append(ValidationIssue(ValidationIssueCode.INVALID_LIFECYCLE_STATE, f"Lifecycle '{lifecycle.id}' requires explicit state for element '{element.id}'", element_id=element.id, rule_id=lifecycle.id))
                    elif element.type_id == lifecycle.element_type_id and element.id in lifecycle_states and lifecycle_states[element.id] not in lifecycle.states:
                        issues.append(ValidationIssue(ValidationIssueCode.INVALID_LIFECYCLE_STATE, f"Lifecycle '{lifecycle.id}' does not define state '{lifecycle_states[element.id]}'", element_id=element.id, rule_id=lifecycle.id))
        if lifecycle_transitions is not None:
            for lifecycle in profile.lifecycles:
                for element in graph.elements:
                    transition = lifecycle_transitions.get(element.id)
                    if element.type_id != lifecycle.element_type_id or transition is None:
                        continue
                    source, target = transition
                    if source not in lifecycle.states or target not in lifecycle.states:
                        issues.append(ValidationIssue(ValidationIssueCode.INVALID_LIFECYCLE_TRANSITION, f"Lifecycle '{lifecycle.id}' transition '{source}' -> '{target}' references an unknown state", element_id=element.id, rule_id=lifecycle.id))
                    elif target not in lifecycle.transitions.get(source, []):
                        issues.append(ValidationIssue(ValidationIssueCode.INVALID_LIFECYCLE_TRANSITION, f"Lifecycle '{lifecycle.id}' does not allow transition '{source}' -> '{target}'", element_id=element.id, rule_id=lifecycle.id))
        evidence_ids = set(lifecycle_states or {}) | set(lifecycle_transitions or {})
        for element_id in sorted(evidence_ids - set(element_map), key=str):
            issues.append(ValidationIssue(ValidationIssueCode.INVALID_LIFECYCLE_STATE, f"Lifecycle evidence is supplied for unknown element '{element_id}'", element_id=element_id))

    @staticmethod
    def _validate_artifacts(profile: StandardProfile, graph: EngineeringGraph, artifact_evidence: set[tuple[UUID, str]] | frozenset[tuple[UUID, str]], issues: list[ValidationIssue]) -> None:
        for requirement in profile.artifacts:
            if not requirement.required:
                continue
            for element in graph.elements:
                if element.type_id == requirement.element_type_id and (element.id, requirement.artifact_type) not in artifact_evidence:
                    issues.append(ValidationIssue(ValidationIssueCode.MISSING_ARTIFACT, f"Artifact requirement '{requirement.id}' requires '{requirement.artifact_type}' for element '{element.id}'", element_id=element.id, rule_id=requirement.id))


def _attribute_value_matches(attribute_type: AttributeType, value: object) -> bool:
    if attribute_type is AttributeType.STRING:
        return isinstance(value, str)
    if attribute_type is AttributeType.INTEGER:
        return isinstance(value, int) and not isinstance(value, bool)
    if attribute_type is AttributeType.NUMBER:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if attribute_type is AttributeType.BOOLEAN:
        return isinstance(value, bool)
    return False


def graph_hash(graph: EngineeringGraph, profile: StandardProfile, *, attributes: dict[UUID, dict[str, object]] | None = None, artifact_evidence: set[tuple[UUID, str]] | frozenset[tuple[UUID, str]] = frozenset(), lifecycle_states: dict[UUID, str] | None = None, lifecycle_transitions: dict[UUID, tuple[str, str]] | None = None) -> str:
    """Return a stable SHA-256 fingerprint of all validation inputs."""
    payload = {
        "profile": profile.model_dump(mode="json"),
        "elements": [element.model_dump(mode="json") for element in sorted(graph.elements, key=lambda item: str(item.id))],
        "relations": [relation.model_dump(mode="json") for relation in sorted(graph.relations, key=lambda item: (str(item.source_id), item.relation_type.value, str(item.target_id), str(item.id)))],
        "attributes": sorted([[str(element_id), key, value] for element_id, values in (attributes or {}).items() for key, value in values.items()], key=lambda item: (item[0], item[1], json.dumps(item[2], ensure_ascii=False, sort_keys=True, default=str))),
        "artifact_evidence": sorted([[str(element_id), artifact_type] for element_id, artifact_type in artifact_evidence], key=lambda item: (item[0], item[1])),
        "lifecycle_states": sorted([[str(element_id), state] for element_id, state in (lifecycle_states or {}).items()], key=lambda item: (item[0], item[1])),
        "lifecycle_transitions": sorted([[str(element_id), source, target] for element_id, (source, target) in (lifecycle_transitions or {}).items()], key=lambda item: (item[0], item[1], item[2])),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _issue_sort_key(issue: ValidationIssue) -> tuple[str, str, str, str]:
    return (issue.code, str(issue.element_id or ""), str(issue.relation_id or ""), issue.rule_id or "")


__all__ = ["DeterministicValidationEngine", "ValidationIssue", "ValidationIssueCode", "ValidationResult", "graph_hash"]
