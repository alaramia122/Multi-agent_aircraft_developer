"""Deterministic validation of canonical engineering state against a standard profile."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import UUID

from engineering_gateway.domain.models import EngineeringElement, EngineeringGraph, EngineeringRelation, RelationType
from engineering_gateway.domain.profiles import StandardProfile
from engineering_gateway.domain.traceability import TraceabilityGraph


class ValidationIssueCode:
    """Stable machine-readable validation finding codes."""

    UNKNOWN_ELEMENT_TYPE = "UNKNOWN_ELEMENT_TYPE"
    ELEMENT_KIND_MISMATCH = "ELEMENT_KIND_MISMATCH"
    DUPLICATE_ELEMENT_ID = "DUPLICATE_ELEMENT_ID"
    DUPLICATE_EXTERNAL_IDENTITY = "DUPLICATE_EXTERNAL_IDENTITY"
    DANGLING_RELATION = "DANGLING_RELATION"
    FORBIDDEN_RELATION = "FORBIDDEN_RELATION"
    DUPLICATE_RELATION = "DUPLICATE_RELATION"
    MISSING_TRACEABILITY = "MISSING_TRACEABILITY"
    FORBIDDEN_TRACEABILITY = "FORBIDDEN_TRACEABILITY"
    MISSING_VERIFICATION = "MISSING_VERIFICATION"
    INVALID_LIFECYCLE_STATE = "INVALID_LIFECYCLE_STATE"


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
    """Validate canonical state using only deterministic profile rules."""

    def validate(
        self,
        elements: list[EngineeringElement],
        relations: list[EngineeringRelation],
        profile: StandardProfile,
    ) -> ValidationResult:
        return self.validate_graph(EngineeringGraph(elements=elements, relations=relations), profile)

    def validate_graph(self, graph: EngineeringGraph, profile: StandardProfile) -> ValidationResult:
        issues: list[ValidationIssue] = []
        element_map: dict[UUID, EngineeringElement] = {}
        external_identities: dict[tuple[str, str], UUID] = {}
        type_definitions = {definition.id: definition for definition in profile.element_types}

        for element in graph.elements:
            if element.id in element_map:
                issues.append(ValidationIssue(
                    ValidationIssueCode.DUPLICATE_ELEMENT_ID,
                    f"Element id '{element.id}' occurs more than once",
                    element_id=element.id,
                ))
            else:
                element_map[element.id] = element

            identity = (element.external_system, element.external_id)
            previous = external_identities.get(identity)
            if previous is not None and previous != element.id:
                issues.append(ValidationIssue(
                    ValidationIssueCode.DUPLICATE_EXTERNAL_IDENTITY,
                    f"External identity '{element.external_system}:{element.external_id}' is used by multiple elements",
                    element_id=element.id,
                ))
            else:
                external_identities[identity] = element.id

            definition = type_definitions.get(element.type_id)
            if definition is None:
                issues.append(ValidationIssue(
                    ValidationIssueCode.UNKNOWN_ELEMENT_TYPE,
                    f"Element type '{element.type_id}' is not defined by the profile",
                    element_id=element.id,
                ))
            elif element.kind is not definition.kind:
                issues.append(ValidationIssue(
                    ValidationIssueCode.ELEMENT_KIND_MISMATCH,
                    f"Element type '{element.type_id}' requires kind '{definition.kind}', got '{element.kind}'",
                    element_id=element.id,
                ))

        allowed_pairs = {
            (relation.relation_type, source_type, target_type)
            for relation in profile.relations
            for source_type in relation.source_type_ids
            for target_type in relation.target_type_ids
        }
        seen_relations: set[tuple[UUID, RelationType, UUID]] = set()
        for relation in graph.relations:
            key = (relation.source_id, relation.relation_type, relation.target_id)
            if key in seen_relations:
                issues.append(ValidationIssue(
                    ValidationIssueCode.DUPLICATE_RELATION,
                    "Identical relation occurs more than once",
                    relation_id=relation.id,
                ))
            seen_relations.add(key)
            source = element_map.get(relation.source_id)
            target = element_map.get(relation.target_id)
            if source is None or target is None:
                issues.append(ValidationIssue(
                    ValidationIssueCode.DANGLING_RELATION,
                    "Relation references an element that is not present in the graph",
                    relation_id=relation.id,
                ))
                continue
            if (relation.relation_type, source.type_id, target.type_id) not in allowed_pairs:
                issues.append(ValidationIssue(
                    ValidationIssueCode.FORBIDDEN_RELATION,
                    f"Relation '{relation.relation_type}' is not allowed from '{source.type_id}' to '{target.type_id}'",
                    relation_id=relation.id,
                ))

        traceability = TraceabilityGraph(graph.elements, graph.relations)
        for gap in traceability.traceability_violations(profile):
            issues.append(ValidationIssue(
                ValidationIssueCode.FORBIDDEN_TRACEABILITY if gap.forbidden else ValidationIssueCode.MISSING_TRACEABILITY,
                f"Traceability rule '{gap.rule_id}' is violated for element {gap.source_id}",
                element_id=gap.source_id,
                rule_id=gap.rule_id,
            ))

        for rule in profile.verification:
            for element in graph.elements:
                if element.type_id != rule.element_type_id:
                    continue
                verified = any(
                    relation.source_id == element.id
                    and relation.relation_type is rule.required_relation_type
                    and (target := element_map.get(relation.target_id)) is not None
                    and target.type_id == rule.verification_type_id
                    for relation in graph.relations
                )
                if not verified:
                    issues.append(ValidationIssue(
                        ValidationIssueCode.MISSING_VERIFICATION,
                        f"Verification rule '{rule.id}' requires relation '{rule.required_relation_type}' to '{rule.verification_type_id}'",
                        element_id=element.id,
                        rule_id=rule.id,
                    ))

        # Lifecycle state is intentionally not guessed from EngineeringElement: the
        # canonical model contains no lifecycle-state attribute. Lifecycle validation
        # will become executable when lifecycle state is represented by an explicit
        # Gateway contract rather than hidden metadata.
        issues.sort(key=_issue_sort_key)
        return ValidationResult(
            profile_id=profile.id,
            profile_version=profile.version,
            graph_hash=graph_hash(graph, profile),
            issues=tuple(issues),
        )


def graph_hash(graph: EngineeringGraph, profile: StandardProfile) -> str:
    """Return a stable SHA-256 fingerprint of graph and exact profile definition."""
    payload = {
        "profile": profile.model_dump(mode="json"),
        "elements": [element.model_dump(mode="json") for element in sorted(graph.elements, key=lambda item: str(item.id))],
        "relations": [relation.model_dump(mode="json") for relation in sorted(
            graph.relations,
            key=lambda item: (str(item.source_id), item.relation_type.value, str(item.target_id), str(item.id)),
        )],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def _issue_sort_key(issue: ValidationIssue) -> tuple[str, str, str, str]:
    return (issue.code, str(issue.element_id or ""), str(issue.relation_id or ""), issue.rule_id or "")


__all__ = [
    "DeterministicValidationEngine",
    "ValidationIssue",
    "ValidationIssueCode",
    "ValidationResult",
    "graph_hash",
]
