"""Complete MVP-1/MVP-2 profile acceptance chains from the technical specification."""

from pathlib import Path

from engineering_gateway.application.profile_engine import StandardProfileEngine
from engineering_gateway.application.validation import (
    DeterministicValidationEngine,
    ValidationIssueCode,
)
from engineering_gateway.domain.models import (
    ElementKind,
    EngineeringElement,
    EngineeringRelation,
    RelationType,
)
from engineering_gateway.infrastructure.profile_loader import load_standard_profile

ROOT = Path(__file__).resolve().parents[2]
ARP_PROFILE = ROOT / "profiles" / "arp4754a" / "2.0" / "profile.json"
DO_PROFILE = ROOT / "profiles" / "do-178c" / "2.0" / "profile.json"


def _element(kind: ElementKind, type_id: str, external_system: str) -> EngineeringElement:
    return EngineeringElement(
        kind=kind,
        type_id=type_id,
        name=type_id.replace("_", " ").title(),
        external_system=external_system,
        external_id=type_id.upper(),
    )


def _relation(
    source: EngineeringElement,
    relation_type: RelationType,
    target: EngineeringElement,
) -> EngineeringRelation:
    return EngineeringRelation(
        source_id=source.id,
        relation_type=relation_type,
        target_id=target.id,
    )


def _arp_graph() -> tuple[
    list[EngineeringElement],
    list[EngineeringRelation],
    dict[str, EngineeringElement],
]:
    elements = {
        "aircraft_function": _element(ElementKind.ARCHITECTURE, "aircraft_function", "capella"),
        "system_function": _element(ElementKind.ARCHITECTURE, "system_function", "capella"),
        "system_requirement": _element(ElementKind.REQUIREMENT, "system_requirement", "strictdoc"),
        "system_architecture": _element(ElementKind.ARCHITECTURE, "system_architecture", "capella"),
        "software_item": _element(ElementKind.ARCHITECTURE, "software_item", "capella"),
        "hazard": _element(ElementKind.SAFETY, "hazard", "capella"),
        "safety_requirement": _element(ElementKind.REQUIREMENT, "safety_requirement", "strictdoc"),
        "verification_activity": _element(ElementKind.VERIFICATION, "verification_activity", "strictdoc"),
        "verification_evidence": _element(ElementKind.VERIFICATION, "verification_evidence", "git"),
    }
    relations = [
        _relation(elements["system_function"], RelationType.REFINES, elements["aircraft_function"]),
        _relation(elements["system_requirement"], RelationType.DERIVES_FROM, elements["system_function"]),
        _relation(elements["system_requirement"], RelationType.ALLOCATED_TO, elements["system_architecture"]),
        _relation(elements["system_architecture"], RelationType.ALLOCATED_TO, elements["software_item"]),
        _relation(elements["hazard"], RelationType.AFFECTS, elements["system_function"]),
        _relation(elements["safety_requirement"], RelationType.DERIVES_FROM, elements["system_requirement"]),
        _relation(elements["safety_requirement"], RelationType.MITIGATES, elements["hazard"]),
        _relation(elements["safety_requirement"], RelationType.ALLOCATED_TO, elements["system_architecture"]),
        _relation(elements["system_requirement"], RelationType.VERIFIED_BY, elements["verification_activity"]),
        _relation(elements["safety_requirement"], RelationType.VERIFIED_BY, elements["verification_activity"]),
        _relation(elements["verification_activity"], RelationType.VERIFIED_BY, elements["verification_evidence"]),
    ]
    return list(elements.values()), relations, elements


def _do_graph() -> tuple[
    list[EngineeringElement],
    list[EngineeringRelation],
    dict[str, EngineeringElement],
]:
    elements = {
        "system_requirement": _element(ElementKind.REQUIREMENT, "system_requirement", "strictdoc"),
        "software_item": _element(ElementKind.ARCHITECTURE, "software_item", "capella"),
        "high_level_requirement": _element(ElementKind.REQUIREMENT, "high_level_requirement", "strictdoc"),
        "software_architecture": _element(ElementKind.ARCHITECTURE, "software_architecture", "capella"),
        "low_level_requirement": _element(ElementKind.REQUIREMENT, "low_level_requirement", "strictdoc"),
        "source_code": _element(ElementKind.CONFIGURATION, "source_code", "git"),
        "executable": _element(ElementKind.CONFIGURATION, "executable", "git"),
        "verification_case": _element(ElementKind.VERIFICATION, "verification_case", "strictdoc"),
        "verification_result": _element(ElementKind.VERIFICATION, "verification_result", "strictdoc"),
        "evidence": _element(ElementKind.VERIFICATION, "evidence", "git"),
    }
    relations = [
        _relation(elements["high_level_requirement"], RelationType.DERIVES_FROM, elements["system_requirement"]),
        _relation(elements["high_level_requirement"], RelationType.ALLOCATED_TO, elements["software_item"]),
        _relation(elements["low_level_requirement"], RelationType.REFINES, elements["high_level_requirement"]),
        _relation(elements["low_level_requirement"], RelationType.ALLOCATED_TO, elements["software_architecture"]),
        _relation(elements["software_architecture"], RelationType.IMPLEMENTS, elements["source_code"]),
        _relation(elements["source_code"], RelationType.IMPLEMENTS, elements["executable"]),
        _relation(elements["high_level_requirement"], RelationType.VERIFIED_BY, elements["verification_case"]),
        _relation(elements["low_level_requirement"], RelationType.VERIFIED_BY, elements["verification_case"]),
        _relation(elements["verification_case"], RelationType.VERIFIED_BY, elements["verification_result"]),
        _relation(elements["verification_result"], RelationType.VERIFIED_BY, elements["evidence"]),
    ]
    return list(elements.values()), relations, elements


def test_arp4754a_v2_validates_complete_mvp1_chain() -> None:
    profile = load_standard_profile(ARP_PROFILE)
    StandardProfileEngine.validate_profile(profile)
    elements, relations, by_type = _arp_graph()

    result = DeterministicValidationEngine().validate(
        elements,
        relations,
        profile,
        lifecycle_states={
            by_type["system_requirement"].id: "reviewed",
            by_type["safety_requirement"].id: "reviewed",
            by_type["verification_evidence"].id: "accepted",
        },
    )

    assert result.valid
    assert profile.metadata["profile_role"] == "complete_mvp1_acceptance_chain"


def test_arp4754a_v2_reports_five_distinct_chain_gaps() -> None:
    profile = load_standard_profile(ARP_PROFILE)
    elements, relations, by_type = _arp_graph()

    result = DeterministicValidationEngine().validate(
        elements,
        relations[5:],
        profile,
        lifecycle_states={
            by_type["system_requirement"].id: "reviewed",
            by_type["safety_requirement"].id: "reviewed",
            by_type["verification_evidence"].id: "accepted",
        },
    )

    missing_rules = {
        issue.rule_id
        for issue in result.issues
        if issue.code == ValidationIssueCode.MISSING_TRACEABILITY
    }
    assert {
        "arp-system-function-has-aircraft-parent",
        "arp-system-requirement-has-function-parent",
        "arp-system-requirement-has-architecture-allocation",
        "arp-architecture-has-software-allocation",
        "arp-hazard-has-functional-effect",
    }.issubset(missing_rules)


def test_do178c_v2_validates_complete_mvp2_chain() -> None:
    profile = load_standard_profile(DO_PROFILE)
    StandardProfileEngine.validate_profile(profile)
    elements, relations, by_type = _do_graph()

    result = DeterministicValidationEngine().validate(
        elements,
        relations,
        profile,
        lifecycle_states={
            by_type["high_level_requirement"].id: "reviewed",
            by_type["low_level_requirement"].id: "reviewed",
            by_type["verification_case"].id: "accepted",
            by_type["verification_result"].id: "accepted",
            by_type["evidence"].id: "accepted",
        },
    )

    assert result.valid
    assert profile.metadata["profile_role"] == "complete_mvp2_acceptance_chain"


def test_do178c_v2_reports_five_distinct_chain_gaps() -> None:
    profile = load_standard_profile(DO_PROFILE)
    elements, relations, by_type = _do_graph()

    result = DeterministicValidationEngine().validate(
        elements,
        relations[5:],
        profile,
        lifecycle_states={
            by_type["high_level_requirement"].id: "reviewed",
            by_type["low_level_requirement"].id: "reviewed",
            by_type["verification_case"].id: "accepted",
            by_type["verification_result"].id: "accepted",
            by_type["evidence"].id: "accepted",
        },
    )

    missing_rules = {
        issue.rule_id
        for issue in result.issues
        if issue.code == ValidationIssueCode.MISSING_TRACEABILITY
    }
    assert {
        "do-hlr-has-system-source",
        "do-hlr-has-software-allocation",
        "do-llr-has-hlr-parent",
        "do-llr-has-architecture-allocation",
        "do-architecture-has-source",
    }.issubset(missing_rules)


def test_complete_arp4754a_and_do178c_profiles_compose_deterministically() -> None:
    arp = load_standard_profile(ARP_PROFILE)
    do178c = load_standard_profile(DO_PROFILE)

    composed = StandardProfileEngine.compose(
        [arp, do178c],
        id="arp4754a-do-178c",
        version="2.0",
        name="Complete system and software lifecycle",
    )

    assert set(composed.metadata["composed_from"]) == {"arp4754a@2.0", "do-178c@2.0"}
    assert {definition.id for definition in composed.element_types} >= {
        "aircraft_function",
        "system_requirement",
        "software_item",
        "high_level_requirement",
        "evidence",
    }
