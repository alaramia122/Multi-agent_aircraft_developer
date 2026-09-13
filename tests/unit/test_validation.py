from uuid import uuid4

from engineering_gateway.application.validation import DeterministicValidationEngine, ValidationIssueCode, graph_hash
from engineering_gateway.domain.models import ElementKind, EngineeringElement, EngineeringGraph, EngineeringRelation, RelationType
from engineering_gateway.domain.profiles import AttributeDefinition, AttributeType, ElementTypeDefinition, LifecycleDefinition, RelationDefinition, StandardProfile, TraceabilityRule, VerificationRule, ArtifactRequirement


def make_element(type_id: str, kind: ElementKind) -> EngineeringElement:
    return EngineeringElement(kind=kind, type_id=type_id, name=type_id, external_system="test", external_id=str(uuid4()))


def make_profile() -> StandardProfile:
    return StandardProfile(
        id="validation-profile", version="1", name="Validation profile",
        element_types=[
            ElementTypeDefinition(id="requirement", kind=ElementKind.REQUIREMENT),
            ElementTypeDefinition(id="architecture", kind=ElementKind.ARCHITECTURE),
        ],
        relations=[RelationDefinition(id="satisfies", relation_type=RelationType.SATISFIES, source_type_ids=["requirement"], target_type_ids=["architecture"])],
        traceability=[TraceabilityRule(id="required-satisfaction", source_type_id="requirement", relation_type=RelationType.SATISFIES, target_type_id="architecture")],
    )


def test_unknown_element_type_is_reported() -> None:
    result = DeterministicValidationEngine().validate([make_element("unknown", ElementKind.REQUIREMENT)], [], make_profile())
    assert [issue.code for issue in result.issues] == [ValidationIssueCode.UNKNOWN_ELEMENT_TYPE]
    assert not result.valid


def test_element_kind_mismatch_is_reported() -> None:
    result = DeterministicValidationEngine().validate([make_element("architecture", ElementKind.REQUIREMENT)], [], make_profile())
    assert any(issue.code == ValidationIssueCode.ELEMENT_KIND_MISMATCH for issue in result.issues)


def test_dangling_relation_is_reported() -> None:
    source = make_element("requirement", ElementKind.REQUIREMENT)
    relation = EngineeringRelation(source_id=source.id, relation_type=RelationType.SATISFIES, target_id=uuid4())
    result = DeterministicValidationEngine().validate([source], [relation], make_profile())
    assert any(issue.code == ValidationIssueCode.DANGLING_RELATION for issue in result.issues)


def test_forbidden_relation_is_reported() -> None:
    source, target = make_element("requirement", ElementKind.REQUIREMENT), make_element("architecture", ElementKind.ARCHITECTURE)
    relation = EngineeringRelation(source_id=source.id, relation_type=RelationType.DERIVES_FROM, target_id=target.id)
    result = DeterministicValidationEngine().validate([source, target], [relation], make_profile())
    assert any(issue.code == ValidationIssueCode.FORBIDDEN_RELATION for issue in result.issues)


def test_missing_required_traceability_is_reported() -> None:
    result = DeterministicValidationEngine().validate([make_element("requirement", ElementKind.REQUIREMENT)], [], make_profile())
    assert any(issue.code == ValidationIssueCode.MISSING_TRACEABILITY for issue in result.issues)


def test_valid_graph_has_no_issues() -> None:
    source, target = make_element("requirement", ElementKind.REQUIREMENT), make_element("architecture", ElementKind.ARCHITECTURE)
    relation = EngineeringRelation(source_id=source.id, relation_type=RelationType.SATISFIES, target_id=target.id)
    result = DeterministicValidationEngine().validate([source, target], [relation], make_profile())
    assert result.valid and result.issues == ()


def test_duplicate_relation_is_reported() -> None:
    source, target = make_element("requirement", ElementKind.REQUIREMENT), make_element("architecture", ElementKind.ARCHITECTURE)
    relation = EngineeringRelation(source_id=source.id, relation_type=RelationType.SATISFIES, target_id=target.id)
    result = DeterministicValidationEngine().validate([source, target], [relation, relation.model_copy(update={"id": uuid4()})], make_profile())
    assert any(issue.code == ValidationIssueCode.DUPLICATE_RELATION for issue in result.issues)


def test_external_identity_collision_is_reported() -> None:
    first = make_element("requirement", ElementKind.REQUIREMENT)
    second = first.model_copy(update={"id": uuid4()})
    result = DeterministicValidationEngine().validate([first, second], [], make_profile())
    assert any(issue.code == ValidationIssueCode.DUPLICATE_EXTERNAL_IDENTITY for issue in result.issues)


def test_forbidden_traceability_is_reported() -> None:
    source, target = make_element("requirement", ElementKind.REQUIREMENT), make_element("architecture", ElementKind.ARCHITECTURE)
    relation = EngineeringRelation(source_id=source.id, relation_type=RelationType.SATISFIES, target_id=target.id)
    profile = make_profile().model_copy(update={"traceability": [TraceabilityRule(id="forbidden", source_type_id="requirement", relation_type=RelationType.SATISFIES, target_type_id="architecture", required=False)]})
    result = DeterministicValidationEngine().validate([source, target], [relation], profile)
    assert any(issue.code == ValidationIssueCode.FORBIDDEN_TRACEABILITY for issue in result.issues)


def verification_profile() -> StandardProfile:
    base = make_profile()
    return base.model_copy(update={
        "element_types": base.element_types + [ElementTypeDefinition(id="verification", kind=ElementKind.VERIFICATION)],
        "relations": base.relations + [RelationDefinition(id="verified-by", relation_type=RelationType.VERIFIED_BY, source_type_ids=["requirement"], target_type_ids=["verification"])],
        "verification": [VerificationRule(id="requirement-verification", element_type_id="requirement", required_relation_type=RelationType.VERIFIED_BY, verification_type_id="verification")],
    })


def test_missing_verification_is_reported() -> None:
    source = make_element("requirement", ElementKind.REQUIREMENT)
    result = DeterministicValidationEngine().validate([source], [], verification_profile())
    assert any(issue.code == ValidationIssueCode.MISSING_VERIFICATION for issue in result.issues)


def test_verification_relation_satisfies_rule() -> None:
    profile = verification_profile()
    source, architecture, verification = make_element("requirement", ElementKind.REQUIREMENT), make_element("architecture", ElementKind.ARCHITECTURE), make_element("verification", ElementKind.VERIFICATION)
    relations = [EngineeringRelation(source_id=source.id, relation_type=RelationType.SATISFIES, target_id=architecture.id), EngineeringRelation(source_id=source.id, relation_type=RelationType.VERIFIED_BY, target_id=verification.id)]
    result = DeterministicValidationEngine().validate([source, architecture, verification], relations, profile)
    assert not any(issue.code == ValidationIssueCode.MISSING_VERIFICATION for issue in result.issues)


def attribute_profile() -> StandardProfile:
    return StandardProfile(id="attribute-profile", version="1", name="Attributes", element_types=[ElementTypeDefinition(id="requirement", kind=ElementKind.REQUIREMENT, attributes=[AttributeDefinition(id="priority", type=AttributeType.INTEGER, required=True), AttributeDefinition(id="safety", type=AttributeType.BOOLEAN)])])


def test_required_and_typed_attributes_are_validated() -> None:
    element = make_element("requirement", ElementKind.REQUIREMENT)
    profile = attribute_profile()
    missing = DeterministicValidationEngine().validate([element], [], profile)
    assert any(issue.code == ValidationIssueCode.MISSING_REQUIRED_ATTRIBUTE for issue in missing.issues)
    valid = DeterministicValidationEngine().validate([element], [], profile, attributes={element.id: {"priority": 1, "safety": True}})
    assert not valid.issues


def test_invalid_and_unknown_attributes_are_reported() -> None:
    element = make_element("requirement", ElementKind.REQUIREMENT)
    result = DeterministicValidationEngine().validate([element], [], attribute_profile(), attributes={element.id: {"priority": True, "other": "x"}})
    assert any(issue.code == ValidationIssueCode.INVALID_ATTRIBUTE_TYPE for issue in result.issues)
    assert any(issue.code == ValidationIssueCode.UNKNOWN_ATTRIBUTE for issue in result.issues)


def lifecycle_profile() -> StandardProfile:
    return StandardProfile(id="lifecycle-profile", version="1", name="Lifecycle", element_types=[ElementTypeDefinition(id="requirement", kind=ElementKind.REQUIREMENT)], lifecycles=[LifecycleDefinition(id="requirement-lifecycle", element_type_id="requirement", states=["draft", "approved"], transitions={"draft": ["approved"]})])


def test_lifecycle_state_and_transition_are_validated() -> None:
    element = make_element("requirement", ElementKind.REQUIREMENT)
    profile = lifecycle_profile()
    bad_state = DeterministicValidationEngine().validate([element], [], profile, lifecycle_states={element.id: "unknown"})
    assert any(issue.code == ValidationIssueCode.INVALID_LIFECYCLE_STATE for issue in bad_state.issues)
    bad_transition = DeterministicValidationEngine().validate([element], [], profile, lifecycle_states={element.id: "approved"}, lifecycle_transitions={element.id: ("approved", "draft")})
    assert any(issue.code == ValidationIssueCode.INVALID_LIFECYCLE_TRANSITION for issue in bad_transition.issues)
    good = DeterministicValidationEngine().validate([element], [], profile, lifecycle_states={element.id: "approved"}, lifecycle_transitions={element.id: ("draft", "approved")})
    assert not good.issues


def test_required_artifact_is_validated_from_explicit_evidence() -> None:
    element = make_element("requirement", ElementKind.REQUIREMENT)
    profile = attribute_profile().model_copy(update={"artifacts": [ArtifactRequirement(id="req-spec", element_type_id="requirement", artifact_type="specification")]})
    missing = DeterministicValidationEngine().validate([element], [], profile, attributes={element.id: {"priority": 1}})
    assert any(issue.code == ValidationIssueCode.MISSING_ARTIFACT for issue in missing.issues)
    valid = DeterministicValidationEngine().validate([element], [], profile, attributes={element.id: {"priority": 1}}, artifact_evidence={(element.id, "specification")})
    assert not valid.issues


def test_validation_hash_changes_when_evidence_changes() -> None:
    element = make_element("requirement", ElementKind.REQUIREMENT)
    profile = attribute_profile()
    first = DeterministicValidationEngine().validate([element], [], profile, attributes={element.id: {"priority": 1}})
    second = DeterministicValidationEngine().validate([element], [], profile, attributes={element.id: {"priority": 2}})
    assert first.graph_hash != second.graph_hash


def test_graph_hash_is_stable_under_input_order() -> None:
    source, target = make_element("requirement", ElementKind.REQUIREMENT), make_element("architecture", ElementKind.ARCHITECTURE)
    relation = EngineeringRelation(source_id=source.id, relation_type=RelationType.SATISFIES, target_id=target.id)
    profile = make_profile()
    assert graph_hash(EngineeringGraph(elements=[source, target], relations=[relation]), profile) == graph_hash(EngineeringGraph(elements=[target, source], relations=[relation]), profile)


def test_validation_result_contains_graph_hash() -> None:
    result = DeterministicValidationEngine().validate([make_element("requirement", ElementKind.REQUIREMENT)], [], make_profile())
    assert len(result.graph_hash) == 64
