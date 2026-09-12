"""Deterministic traceability graph services."""

from dataclasses import dataclass
from uuid import UUID

from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation, RelationType
from engineering_gateway.domain.profiles import StandardProfile, TraceabilityRule


@dataclass(frozen=True)
class TraceabilityGap:
    """A missing required traceability edge."""

    rule_id: str
    source_id: UUID
    target_type_id: str
    relation_type: RelationType


class TraceabilityGraph:
    """Query canonical graph relations without owning engineering data."""

    def __init__(self, elements: list[EngineeringElement], relations: list[EngineeringRelation]) -> None:
        self._elements = {element.id: element for element in elements}
        self._relations = list(relations)

    def outgoing(self, source_id: UUID, relation_type: RelationType | None = None) -> list[EngineeringRelation]:
        return [
            relation
            for relation in self._relations
            if relation.source_id == source_id
            and (relation_type is None or relation.relation_type == relation_type)
        ]

    def incoming(self, target_id: UUID, relation_type: RelationType | None = None) -> list[EngineeringRelation]:
        return [
            relation
            for relation in self._relations
            if relation.target_id == target_id
            and (relation_type is None or relation.relation_type == relation_type)
        ]

    def missing_required(self, profile: StandardProfile) -> list[TraceabilityGap]:
        gaps: list[TraceabilityGap] = []
        for rule in profile.traceability:
            if not rule.required:
                continue
            for source in self._elements.values():
                if source.type_id != rule.source_type_id:
                    continue
                satisfied = any(
                    relation.relation_type == rule.relation_type
                    and self._elements.get(relation.target_id) is not None
                    and self._elements[relation.target_id].type_id == rule.target_type_id
                    for relation in self.outgoing(source.id, rule.relation_type)
                )
                if not satisfied:
                    gaps.append(
                        TraceabilityGap(
                            rule_id=rule.id,
                            source_id=source.id,
                            target_type_id=rule.target_type_id,
                            relation_type=rule.relation_type,
                        )
                    )
        return gaps


__all__ = ["TraceabilityGap", "TraceabilityGraph"]
