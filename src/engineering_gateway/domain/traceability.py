"""Deterministic traceability graph services."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation, RelationType
from engineering_gateway.domain.profiles import StandardProfile


class TraceabilityGapType(StrEnum):
    """Deterministic diagnostic categories for traceability defects."""

    MISSING_REQUIRED = "missing_required"
    FORBIDDEN_PRESENT = "forbidden_present"
    WRONG_RELATION_TYPE = "wrong_relation_type"
    WRONG_TARGET_TYPE = "wrong_target_type"
    DANGLING_SOURCE = "dangling_source"
    DANGLING_TARGET = "dangling_target"


@dataclass(frozen=True)
class TraceabilityGap:
    """A deterministic traceability defect for a canonical graph."""

    rule_id: str
    source_id: UUID
    target_type_id: str
    relation_type: RelationType
    gap_type: TraceabilityGapType = TraceabilityGapType.MISSING_REQUIRED
    target_id: UUID | None = None

    @property
    def forbidden(self) -> bool:
        """Backward-compatible indication of a forbidden edge."""
        return self.gap_type is TraceabilityGapType.FORBIDDEN_PRESENT


class TraceabilityGraph:
    """Query and diagnose canonical graph relations without owning engineering data."""

    def __init__(
        self, elements: list[EngineeringElement], relations: list[EngineeringRelation]
    ) -> None:
        self._elements = {element.id: element for element in elements}
        self._relations = list(relations)

    @property
    def elements(self) -> tuple[EngineeringElement, ...]:
        return tuple(self._elements.values())

    @property
    def relations(self) -> tuple[EngineeringRelation, ...]:
        return tuple(self._relations)

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

    def reachable(self, source_id: UUID, relation_type: RelationType | None = None) -> set[UUID]:
        """Return all element IDs reachable from ``source_id`` by directed edges."""
        visited: set[UUID] = set()
        pending = [source_id]
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            pending.extend(
                relation.target_id
                for relation in self.outgoing(current, relation_type)
                if relation.target_id not in visited and relation.target_id in self._elements
            )
        visited.discard(source_id)
        return visited

    def ancestors(self, target_id: UUID, relation_type: RelationType | None = None) -> set[UUID]:
        """Return all element IDs that can reach ``target_id`` by directed edges."""
        visited: set[UUID] = set()
        pending = [target_id]
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            pending.extend(
                relation.source_id
                for relation in self.incoming(current, relation_type)
                if relation.source_id not in visited and relation.source_id in self._elements
            )
        visited.discard(target_id)
        return visited

    def traceability_violations(self, profile: StandardProfile) -> list[TraceabilityGap]:
        """Return deterministic missing, forbidden and malformed traceability findings."""
        violations: list[TraceabilityGap] = []
        for rule in profile.traceability:
            for source in self._elements.values():
                if source.type_id != rule.source_type_id:
                    continue

                outgoing = self.outgoing(source.id)
                matching = [
                    relation
                    for relation in outgoing
                    if relation.relation_type == rule.relation_type
                    and self._elements.get(relation.target_id) is not None
                    and self._elements[relation.target_id].type_id == rule.target_type_id
                ]

                if rule.required:
                    if matching:
                        continue
                    same_relation = [
                        relation
                        for relation in outgoing
                        if relation.relation_type == rule.relation_type
                    ]
                    if any(relation.target_id not in self._elements for relation in same_relation):
                        violations.extend(
                            TraceabilityGap(
                                rule_id=rule.id,
                                source_id=source.id,
                                target_type_id=rule.target_type_id,
                                relation_type=rule.relation_type,
                                gap_type=TraceabilityGapType.DANGLING_TARGET,
                                target_id=relation.target_id,
                            )
                            for relation in same_relation
                            if relation.target_id not in self._elements
                        )
                    elif same_relation:
                        violations.extend(
                            TraceabilityGap(
                                rule_id=rule.id,
                                source_id=source.id,
                                target_type_id=rule.target_type_id,
                                relation_type=rule.relation_type,
                                gap_type=TraceabilityGapType.WRONG_TARGET_TYPE,
                                target_id=relation.target_id,
                            )
                            for relation in same_relation
                        )
                    elif any(
                        relation.target_id in self._elements
                        and self._elements[relation.target_id].type_id == rule.target_type_id
                        for relation in outgoing
                    ):
                        violations.extend(
                            TraceabilityGap(
                                rule_id=rule.id,
                                source_id=source.id,
                                target_type_id=rule.target_type_id,
                                relation_type=rule.relation_type,
                                gap_type=TraceabilityGapType.WRONG_RELATION_TYPE,
                                target_id=relation.target_id,
                            )
                            for relation in outgoing
                            if relation.target_id in self._elements
                            and self._elements[relation.target_id].type_id == rule.target_type_id
                            and relation.relation_type != rule.relation_type
                        )
                    else:
                        violations.append(
                            TraceabilityGap(
                                rule_id=rule.id,
                                source_id=source.id,
                                target_type_id=rule.target_type_id,
                                relation_type=rule.relation_type,
                                gap_type=TraceabilityGapType.MISSING_REQUIRED,
                            )
                        )
                elif matching:
                    violations.extend(
                        TraceabilityGap(
                            rule_id=rule.id,
                            source_id=source.id,
                            target_type_id=rule.target_type_id,
                            relation_type=rule.relation_type,
                            gap_type=TraceabilityGapType.FORBIDDEN_PRESENT,
                            target_id=relation.target_id,
                        )
                        for relation in matching
                    )

        for relation in self._relations:
            if relation.source_id not in self._elements:
                violations.append(
                    TraceabilityGap(
                        rule_id="graph-integrity",
                        source_id=relation.source_id,
                        target_type_id="<unknown>",
                        relation_type=relation.relation_type,
                        gap_type=TraceabilityGapType.DANGLING_SOURCE,
                        target_id=relation.target_id,
                    )
                )
            if relation.target_id not in self._elements:
                violations.append(
                    TraceabilityGap(
                        rule_id="graph-integrity",
                        source_id=relation.source_id,
                        target_type_id="<unknown>",
                        relation_type=relation.relation_type,
                        gap_type=TraceabilityGapType.DANGLING_TARGET,
                        target_id=relation.target_id,
                    )
                )
        return violations

    def missing_required(self, profile: StandardProfile) -> list[TraceabilityGap]:
        """Backward-compatible query for missing required traceability."""
        return [
            gap
            for gap in self.traceability_violations(profile)
            if gap.gap_type is TraceabilityGapType.MISSING_REQUIRED
        ]


__all__ = ["TraceabilityGap", "TraceabilityGapType", "TraceabilityGraph"]
