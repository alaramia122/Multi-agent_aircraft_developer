from uuid import uuid4

from engineering_gateway.application.validation import DeterministicValidationEngine, ValidationIssueCode, graph_hash
from engineering_gateway.domain.models import ElementKind, EngineeringElement, EngineeringGraph, EngineeringRelation, RelationType
from engineering_gateway.domain.profiles import ElementTypeDefinition, RelationDefinition, StandardProfile, TraceabilityRule, VerificationRule


def make_element(type_id: str, kind: ElementKind) -> EngineeringElement:
    return EngineeringElement(kind=kind, type_id=type_id, name=type_id, external_system="test", external_id=str(uuid4()))


def make_profile() -> StandardProfile:
    return StandardProfile(
        id="validation-profile", version="1", name="Validation profile",
        element_types=[
            ElementTypeDefinition(id="requirement", kind=ElementKind.REQUIREMENT),
            ElementTypeDefinition(id="architecture", kind=ElementKind.ARCHITECTURE),
        ],
        relations=[RelationDefinition(
            id="satisfies", relation_type=RelationType.SATISFIES,
            source_type_ids=["requirement"], target_type_ids=["architecture"],
        )],
        traceability=[TraceabilityRule(
            id="required-satisfaction", source_type_id="requirement",
            relation_type=RelationType.SATISFIES, target_type_id="architecture",
        )],
    )


def test_unknown_element_type_is_reported() -> None:
    element = make_element("unknown", ElementKind.REQUIREMENT)
    result = DeterministicValidationEngine().validate([element], [], make_profile())
    assert [issue.code for issue in result.issues] == [ValidationIssueCode.UNKNOWN_ELEMENT_TYPE]
    assert not result.valid


def test_element_kind_mismatch_is_reported() -> None:
    element = make_element("architecture", ElementKind.REQUIREMENT)
    result = DeterministicValidationEngine().validate([element], [], make_profile())
    assert any(issue.code == ValidationIssueCode.ELEMENT_KIND_MISMATCH for issue in result.issues)


def test_dangling_relation_is_reported() -> None:
    source = make_element("requirement", ElementKind.REQUIREMENT)
    relation = EngineeringRelation(source_id=source.id, relation_type=RelationType.SATISFIES, target_id=uuid4())
    result = DeterministicValidationEngine().validate([source], [relation], make_profile())
    assert any(issue.code == ValidationIssueCode.DANGLING_RELATION for issue in result.issues)


def test_forbidden_relation_is_reported() -> None:
    source = make_element("requirement", ElementKind.REQUIREMENT)
    target = make_element("architecture", ElementKind.ARCHITECTURE)
    relation = EngineeringRelation(source_id=source.id, relation_type=RelationType.DERIVES_FROM, target_id=target.id)
    result = DeterministicValidationEngine().validate([source, target], [relation], make_profile())
    assert any(issue.code == ValidationIssueCode.FORBIDDEN_RELATION for issue in result.issues)


def test_missing_required_traceability_is_reported() -> None:
    source = make_element("requirement", ElementKind.REQUIREMENT)
    result = DeterministicValidationEngine().validate([source], [], make_profile())
    assert any(issue.code == ValidationIssueCode.MISSING_TRACEABILITY for issue in result.issues)


def test_valid_graph_has_no_issues() -> None:
    source = make_element("requirement", ElementKind.REQUIREMENT)
    target = make_element("architecture", ElementKind.ARCHITECTURE)
    relation = EngineeringRelation(source_id=source.id, relation_type=RelationType.SATISFIES, target_id=target.id)
    result = DeterministicValidationEngine().validate([source, target], [relation], make_profile())
    assert result.valid
    assert result.issues == ()


def test_duplicate_relation_is_reported() -> None:
    source = make_element("requirement", ElementKind.REQUIREMENT)
    target = make_element("architecture", ElementKind.ARCHITECTURE)
    relations = [
        EngineeringRelation(source_id=source.id, relation_type=RelationType.SATISFIES, target_id=target.id),
        EngineeringRelation(source_id=source.id, relation_type=RelationType.SATISFIES, target_id=target.id),
    ]
    result = DeterministicValidationEngine().validate([source, target], relations, make_profile())
    assert any(issue.code == ValidationIssueCode.DUPLICATE_RELATION for issue in result.issues)


def test_external_identity_collision_is_reported() -> None:
    first = make_element("requirement", ElementKind.REQUIREMENT)
    second = first.model_copy(update={"id": uuid4()})
    result = DeterministicValidationEngine().validate([first, second], [], make_profile())
    assert any(issue.code == ValidationIssueCode.DUPLICATE_EXTERNAL_IDENTITY for issue in result.issues)


def test_forbidden_traceability_is_reported() -> None:
    source = make_element("requirement", ElementKind.REQUIREMENT)
    target = make_element("architecture", ElementKind.ARCHITECTURE)
    relation = EngineeringRelation(source_id=source.id, relation_type=RelationType.SATISFIES, target_id=target.id)
    profile = make_profile().model_copy(update={
        "traceability": [TraceabilityRule(
            id="forbidden", source_type_id="requirement",
            relation_type=RelationType.SATISFIES, target_type_id="architecture", required=False,
        )]
    })
    result = DeterministicValidationEngine().validate([source, target], [relation], profile)
    assert any(issue.code == ValidationIssueCode.FORBIDDEN_TRACEABILITY for issue in result.issues)


def test_missing_verification_is_reported() -> None:
    profile = make_profile().model_copy(update={
        "element_types": make_profile().element_types + [
            ElementTypeDefinition(id="verification", kind=ElementKind.VERIFICATION),
        ],
        "relations": make_profile().relations + [RelationDefinition(
            id="verified-by", relation_type=RelationType.VERIFIED_BY,
            source_type_ids=["requirement"], target_type_ids=["verification"],
        )],
        "verification": [VerificationRule(
            id="requirement-verification", element_type_id="requirement",
            required_relation_type=RelationType.VERIFIED_BY, verification_type_id="verification",
        )],
    })
    source = make_element("requirement", ElementKind.REQUIREMENT)
    result = DeterministicValidationEngine().validate([source], [], profile)
    assert any(issue.code == ValidationIssueCode.MISSING_VERIFICATION for issue in result.issues)


def test_verification_relation_satisfies_rule() -> None:
    profile = make_profile().model_copy(update={
        "element_types": make_profile().element_types + [
            ElementTypeDefinition(id="verification", kind=ElementKind.VERIFICATION),
        ],
        "relations": make_profile().relations + [RelationDefinition(
            id="verified-by", relation_type=RelationType.VERIFIED_BY,
            source_type_ids=["requirement"], target_type_ids=["verification"],
        )],
        "verification": [VerificationRule(
            id="requirement-verification", element_type_id="requirement",
            required_relation_type=RelationType.VERIFIED_BY, verification_type_id="verification",
        )],
    })
    source = make_element("requirement", ElementKind.REQUIREMENT)
    architecture = make_element("architecture", ElementKind.ARCHITECTURE)
    verification = make_element("verification", ElementKind.VERIFICATION)
    relations = [
        EngineeringRelation(source_id=source.id, relation_type=RelationType.SATISFIES, target_id=architecture.id),
        EngineeringRelation(source_id=source.id, relation_type=RelationType.VERIFIED_BY, target_id=verification.id),
    ]
    result = DeterministicValidationEngine().validate([source, architecture, verification], relations, profile)
    assert not any(issue.code == ValidationIssueCode.MISSING_VERIFICATION for issue in result.issues)


def test_graph_hash_is_stable_under_input_order() -> None:
    source = make_element("requirement", ElementKind.REQUIREMENT)
    target = make_element("architecture", ElementKind.ARCHITECTURE)
    relation = EngineeringRelation(source_id=source.id, relation_type=RelationType.SATISFIES, target_id=target.id)
    profile = make_profile()
    first = EngineeringGraph(elements=[source, target], relations=[relation])
    second = EngineeringGraph(elements=[target, source], relations=[relation])
    assert graph_hash(first, profile) == graph_hash(second, profile)


def test_validation_result_contains_graph_hash() -> None:
    source = make_element("requirement", ElementKind.REQUIREMENT)
    result = DeterministicValidationEngine().validate([source], [], make_profile())
    assert len(result.graph_hash) == 64
