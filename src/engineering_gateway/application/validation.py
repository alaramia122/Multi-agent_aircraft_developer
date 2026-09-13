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
    """Validate canonical state using only deterministic profile rules.

    The engine validates information represented by the canonical model and explicit
    validation evidence. It never infers lifecycle state or artifact existence from
    arbitrary element metadata.
    """

    def validate(
        self,
        elements: list[EngineeringElement],
        relations: list[EngineeringRelation],
        profile: StandardProfile,
    ) -> ValidationResult:
        return self.validate_graph(EngineeringGraph(elements=elements, relations=relations), profile)

    def validate_graph(
        self,
        graph: EngineeringGraph,
        profile: StandardProfile,
        *,
        artifact_evidence: set[tuple[UUID, str]] | frozenset[tuple[UUID, str]] = frozenset(),
        lifecycle_states: dict[UUID, str] | None = None,
    ) -> ValidationResult:
        """Validate graph plus explicit artifact/lifecycle evidence.

        ``artifact_evidence`` contains ``(element_id, artifact_type)`` pairs proven
        to exist by an authoritative adapter. ``lifecycle_states`` contains explicit
        Gateway-owned lifecycle state, when such a contract is available. Neither is
        guessed from ``EngineeringElement``.
        """
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

        self._validate_verification(graph, profile, element_map, issues)
        self._validate_lifecycle(profile, graph, element_map, lifecycle_states, issues)
        self._validate_artifacts(profile, graph, artifact_evidence, issues)

        issues.sort(key=_issue_sort_key)
        return ValidationResult(
            profile_id=profile.id,
            profile_version=profile.version,
            graph_hash=graph_hash(graph, profile, artifact_evidence=artifact_evidence, lifecycle_states=lifecycle_states),
            issues=tuple(issues),
        )

    @staticmethod
    def _validate_verification(
        graph: EngineeringGraph,
        profile: StandardProfile,
        element_map: dict[UUID, EngineeringElement],
        issues: list[ValidationIssue],
    ) -> None:
        outgoing: dict[UUID, list[EngineeringRelation]] = {}
        for relation in graph.relations:
            outgoing.setdefault(relation.source_id, []).append(relation)
        for rule in profile.verification:
            for element in graph.elements:
                if element.type_id != rule.element_type_id:
                    continue
                satisfied = any(
                    relation.relation_type is rule.required_relation_type
                    and element_map.get(relation.target_id) is not None
                    and element_map[relation.target_id].type_id == rule.verification_type_id
                    for relation in outgoing.get(element.id, ())
                )
                if not satisfied:
                    issues.append(ValidationIssue(
                        ValidationIssueCode.MISSING_VERIFICATION,
                        f"Verification rule '{rule.id}' requires relation '{rule.required_relation_type}' from element '{element.id}' to type '{rule.verification_type_id}'",
                        element_id=element.id,
                        rule_id=rule.id,
                    ))

    @staticmethod
    def _validate_lifecycle(
        profile: StandardProfile,
        graph: EngineeringGraph,
        element_map: dict[UUID, EngineeringElement],
        lifecycle_states: dict[UUID, str] | None,
        issues: list[ValidationIssue],
    ) -> None:
        if lifecycle_states is None:
            return
        for lifecycle in profile.lifecycles:
            for element in graph.elements:
                if element.type_id != lifecycle.element_type_id or element.id not in lifecycle_states:
                    continue
                state = lifecycle_states[element.id]
                if state not in lifecycle.states:
                    issues.append(ValidationIssue(
                        ValidationIssueCode.INVALID_LIFECYCLE_STATE,
                        f"Lifecycle '{lifecycle.id}' does not define state '{state}'",
                        element_id=element.id,
                        rule_id=lifecycle.id,
                    ))
        unknown_ids = set(lifecycle_states) - set(element_map)
        for element_id in sorted(unknown_ids, key=str):
            issues.append(ValidationIssue(
                ValidationIssueCode.INVALID_LIFECYCLE_STATE,
                f"Lifecycle state is supplied for unknown element '{element_id}'",
                element_id=element_id,
            ))

    @staticmethod
    def _validate_artifacts(
        profile: StandardProfile,
        graph: EngineeringGraph,
        artifact_evidence: set[tuple[UUID, str]] | frozenset[tuple[UUID, str]],
        issues: list[ValidationIssue],
    ) -> None:
        for requirement in profile.artifacts:
            if not requirement.required:
                continue
            for element in graph.elements:
                if element.type_id == requirement.element_type_id and (element.id, requirement.artifact_type) not in artifact_evidence:
                    issues.append(ValidationIssue(
                        ValidationIssueCode.MISSING_ARTIFACT,
                        f"Artifact requirement '{requirement.id}' requires '{requirement.artifact_type}' for element '{element.id}'",
                        element_id=element.id,
                        rule_id=requirement.id,
                    ))


def graph_hash(
    graph: EngineeringGraph,
    profile: StandardProfile,
    *,
    artifact_evidence: set[tuple[UUID, str]] | frozenset[tuple[UUID, str]] = frozenset(),
    lifecycle_states: dict[UUID, str] | None = None,
) -> str:
    """Return a stable SHA-256 fingerprint of all validation inputs."""
    payload = {
        "profile": profile.model_dump(mode="json"),
        "elements": [element.model_dump(mode="json") for element in sorted(graph.elements, key=lambda item: str(item.id))],
        "relations": [relation.model_dump(mode="json") for relation in sorted(
            graph.relations,
            key=lambda item: (str(item.source_id), item.relation_type.value, str(item.target_id), str(item.id)),
        )],
        "artifact_evidence": sorted(
            [[str(element_id), artifact_type] for element_id, artifact_type in artifact_evidence],
            key=lambda item: (item[0], item[1]),
        ),
        "lifecycle_states": sorted(
            [[str(element_id), state] for element_id, state in (lifecycle_states or {}).items()],
            key=lambda item: (item[0], item[1]),
        ),
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
