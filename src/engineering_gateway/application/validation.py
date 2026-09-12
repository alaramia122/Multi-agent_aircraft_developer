"""Deterministic validation of canonical engineering state against active profiles."""

from dataclasses import dataclass
from uuid import UUID

from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation, RelationType
from engineering_gateway.domain.profiles import StandardProfile
from engineering_gateway.domain.traceability import TraceabilityGraph


@dataclass(frozen=True)
class ValidationIssue:
    """A deterministic validation finding."""

    code: str
    message: str
    element_id: UUID | None = None
    relation_id: UUID | None = None


class DeterministicValidationEngine:
    """Validate invariants that must not depend on LLM judgement."""

    def validate(
        self,
        elements: list[EngineeringElement],
        relations: list[EngineeringRelation],
        profile: StandardProfile,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        element_map = {element.id: element for element in elements}
        type_ids = {definition.id for definition in profile.element_types}

        for element in elements:
            if element.type_id not in type_ids:
                issues.append(
                    ValidationIssue(
                        code="UNKNOWN_ELEMENT_TYPE",
                        message=f"Element type '{element.type_id}' is not defined by the profile",
                        element_id=element.id,
                    )
                )

        allowed_pairs = {
            (relation.relation_type, source_type, target_type)
            for relation in profile.relations
            for source_type in relation.source_type_ids
            for target_type in relation.target_type_ids
        }
        for relation in relations:
            source = element_map.get(relation.source_id)
            target = element_map.get(relation.target_id)
            if source is None or target is None:
                issues.append(
                    ValidationIssue(
                        code="DANGLING_RELATION",
                        message="Relation references an element that is not present in the graph",
                        relation_id=relation.id,
                    )
                )
                continue
            if (relation.relation_type, source.type_id, target.type_id) not in allowed_pairs:
                issues.append(
                    ValidationIssue(
                        code="FORBIDDEN_RELATION",
                        message=(
                            f"Relation '{relation.relation_type}' is not allowed from "
                            f"'{source.type_id}' to '{target.type_id}'"
                        ),
                        relation_id=relation.id,
                    )
                )

        issues.extend(self._traceability_issues(elements, relations, profile))
        return issues

    @staticmethod
    def _traceability_issues(
        elements: list[EngineeringElement],
        relations: list[EngineeringRelation],
        profile: StandardProfile,
    ) -> list[ValidationIssue]:
        graph = TraceabilityGraph(elements, relations)
        return [
            ValidationIssue(
                code="MISSING_TRACEABILITY",
                message=(
                    f"Required traceability '{gap.rule_id}' is missing for element "
                    f"{gap.source_id}"
                ),
                element_id=gap.source_id,
            )
            for gap in graph.missing_required(profile)
        ]


__all__ = ["DeterministicValidationEngine", "ValidationIssue"]
