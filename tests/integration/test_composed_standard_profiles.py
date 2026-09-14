"""Executable composition test for multiple independent Standard Profiles."""

from pathlib import Path

from engineering_gateway.application.profile_engine import StandardProfileEngine
from engineering_gateway.application.validation import DeterministicValidationEngine
from engineering_gateway.domain.models import (
    ElementKind,
    EngineeringElement,
    EngineeringRelation,
    RelationType,
)
from engineering_gateway.infrastructure.profile_loader import load_standard_profile

ROOT = Path(__file__).resolve().parents[2]
ARP_PROFILE = ROOT / "profiles" / "arp4754a" / "1.0" / "profile.json"
DO_PROFILE = ROOT / "profiles" / "do-178c" / "1.0" / "profile.json"


def test_arp4754a_and_do_178c_profiles_compose_without_gateway_changes():
    arp = load_standard_profile(ARP_PROFILE)
    do178 = load_standard_profile(DO_PROFILE)
    composed = StandardProfileEngine.compose(
        (arp, do178),
        id="arp4754a-do-178c",
        version="1.0",
        name="ARP4754A + DO-178C executable vertical slice",
    )

    StandardProfileEngine.validate_profile(composed)
    assert set(composed.metadata["composed_from"]) == {"arp4754a@1.0", "do-178c@1.0"}
    assert {definition.id for definition in composed.element_types} >= {
        "system_requirement",
        "system_architecture",
        "verification_activity",
        "high_level_requirement",
        "low_level_requirement",
        "software_design",
        "source_code",
        "verification_case",
    }

    requirement = EngineeringElement(
        kind=ElementKind.REQUIREMENT,
        type_id="system_requirement",
        name="SYS-001",
        external_system="strictdoc",
        external_id="SYS-001",
    )
    architecture = EngineeringElement(
        kind=ElementKind.ARCHITECTURE,
        type_id="system_architecture",
        name="System architecture",
        external_system="capella",
        external_id="SYS-ARCH-001",
    )
    system_verification = EngineeringElement(
        kind=ElementKind.VERIFICATION,
        type_id="verification_activity",
        name="System verification",
        external_system="strictdoc",
        external_id="SYS-VER-001",
    )
    hlr = EngineeringElement(
        kind=ElementKind.REQUIREMENT,
        type_id="high_level_requirement",
        name="HLR-001",
        external_system="strictdoc",
        external_id="HLR-001",
    )
    llr = EngineeringElement(
        kind=ElementKind.REQUIREMENT,
        type_id="low_level_requirement",
        name="LLR-001",
        external_system="strictdoc",
        external_id="LLR-001",
    )
    design = EngineeringElement(
        kind=ElementKind.ARCHITECTURE,
        type_id="software_design",
        name="Software design",
        external_system="capella",
        external_id="SW-DES-001",
    )
    code = EngineeringElement(
        kind=ElementKind.CONFIGURATION,
        type_id="source_code",
        name="flight_control.c",
        external_system="git",
        external_id="src/flight_control.c",
    )
    software_verification = EngineeringElement(
        kind=ElementKind.VERIFICATION,
        type_id="verification_case",
        name="TC-001",
        external_system="strictdoc",
        external_id="TC-001",
    )
    elements = [
        requirement,
        architecture,
        system_verification,
        hlr,
        llr,
        design,
        code,
        software_verification,
    ]
    relations = [
        EngineeringRelation(
            source_id=requirement.id,
            relation_type=RelationType.ALLOCATED_TO,
            target_id=architecture.id,
        ),
        EngineeringRelation(
            source_id=requirement.id,
            relation_type=RelationType.VERIFIED_BY,
            target_id=system_verification.id,
        ),
        EngineeringRelation(source_id=llr.id, relation_type=RelationType.REFINES, target_id=hlr.id),
        EngineeringRelation(
            source_id=llr.id, relation_type=RelationType.ALLOCATED_TO, target_id=design.id
        ),
        EngineeringRelation(
            source_id=design.id, relation_type=RelationType.IMPLEMENTS, target_id=code.id
        ),
        EngineeringRelation(
            source_id=llr.id,
            relation_type=RelationType.VERIFIED_BY,
            target_id=software_verification.id,
        ),
    ]
    states = {
        requirement.id: "draft",
        hlr.id: "reviewed",
        llr.id: "reviewed",
        system_verification.id: "draft",
        software_verification.id: "accepted",
    }

    result = DeterministicValidationEngine().validate(
        elements,
        relations,
        composed,
        lifecycle_states=states,
    )
    assert result.valid
    assert result.profile_id == "arp4754a-do-178c"
    assert result.profile_version == "1.0"
    assert len(result.graph_hash) == 64
