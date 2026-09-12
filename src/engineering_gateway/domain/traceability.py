"""Deterministic traceability graph services."""

from dataclasses import dataclass
from uuid import UUID

from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation, RelationType
from engineering_gateway.domain.profiles import StandardProfile


@dataclass(frozen=True)
class TraceabilityGap:
    """A traceability rule violation for a canonical element."""

    rule_id: str
    source_id: UUID
    target_type_id: str
    relation_type: RelationType
    forbidden: bool = False


class TraceabilityGraph:
    """Query canonical graph relations without owning engineering data."""

    def __init__(self, elements: list[EngineeringElement], relations: list[EngineeringRelation]) -> None:
        self._elements = {element.id: element for element in elements}
        self._relations = list(relations)

    def outgoing(
        self, source_id: UUID, relation_type: RelationType | None = None
    ) -> list[EngineeringRelation]:
        return [
            relation
            for relation in self._relations
            if relation.source_id == source_id
            and (relation_type is None or relation.relation_type == relation_type)
        ]

    def incoming(
        self, target_id: UUID, relation_type: RelationType | None = None
    ) -> list[EngineeringRelation]:
        return [
            relation
            for relation in self._relations
            if relation.target_id == target_id
            and (relation_type is None or relation.relation_type == relation_type)
        ]

    def traceability_violations(self, profile: StandardProfile) -> list[TraceabilityGap]:
        """Return missing required and present forbidden traceability edges.

        In a profile rule, ``required=True`` means at least one matching edge must exist;
        ``required=False`` means the matching edge is forbidden. This convention keeps
        the declarative rule model compact and makes validation deterministic.
        """
        violations: list[TraceabilityGap] = []
        for rule in profile.traceability:
            for source in self._elements.values():
                if source.type_id != rule.source_type_id:
                    continue
                matching = [
                    relation
                    for relation in self.outgoing(source.id, rule.relation_type)
                    if (
                        self._elements.get(relation.target_id) is not None
                        and self._elements[relation.target_id].type_id == rule.target_type_id
                    )
                ]
                if rule.required and not matching:
                    violations.append(
                        TraceabilityGap(
                            rule_id=rule.id,
                            source_id=source.id,
                            target_type_id=rule.target_type_id,
                            relation_type=rule.relation_type,
                        )
                    )
                elif not rule.required and matching:
                    violations.extend(
                        TraceabilityGap(
                            rule_id=rule.id,
                            source_id=source.id,
                            target_type_id=rule.target_type_id,
                            relation_type=rule.relation_type,
                            forbidden=True,
                        )
                        for _ in matching
                    )
        return violations

    def missing_required(self, profile: StandardProfile) -> list[TraceabilityGap]:
        """Backward-compatible query for missing required traceability."""
        return [
            gap for gap in self.traceability_violations(profile) if not gap.forbidden
        ]


__all__ = ["TraceabilityGap", "TraceabilityGraph"]
