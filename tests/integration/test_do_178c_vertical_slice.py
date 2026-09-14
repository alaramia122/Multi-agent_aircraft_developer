"""Executable DO-178C profile vertical slice."""

from pathlib import Path

import pytest

from engineering_gateway.application.validation import DeterministicValidationEngine
from engineering_gateway.domain.models import (
    ElementKind,
    EngineeringElement,
    EngineeringGraph,
    EngineeringRelation,
    RelationType,
)
from engineering_gateway.infrastructure.profile_loader import load_standard_profile

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "profiles" / "do-178c" / "1.0" / "profile.json"


@pytest.mark.parametrize("invalid", [False, True])
def test_do_178c_lifecycle_and_traceability(invalid: bool) -> None:
    profile = load_standard_profile(PROFILE)
    engine = DeterministicValidationEngine()

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
        name="Design-001",
        external_system="capella",
        external_id="DES-001",
    )
    code = EngineeringElement(
        kind=ElementKind.CONFIGURATION,
        type_id="source_code",
        name="module.c",
        external_system="git",
        external_id="src/module.c",
    )
    verification = EngineeringElement(
        kind=ElementKind.VERIFICATION,
        type_id="verification_case",
        name="TC-001",
        external_system="strictdoc",
        external_id="TC-001",
    )
    elements = [hlr, llr, design, code, verification]
    relations = [
        EngineeringRelation(source_id=llr.id, relation_type=RelationType.REFINES, target_id=hlr.id),
        EngineeringRelation(
            source_id=llr.id, relation_type=RelationType.ALLOCATED_TO, target_id=design.id
        ),
        EngineeringRelation(
            source_id=design.id, relation_type=RelationType.IMPLEMENTS, target_id=code.id
        ),
        EngineeringRelation(
            source_id=llr.id, relation_type=RelationType.VERIFIED_BY, target_id=verification.id
        ),
    ]

    lifecycle_states = {
        hlr.id: "reviewed",
        llr.id: "reviewed",
        verification.id: "accepted",
    }
    if invalid:
        lifecycle_states[llr.id] = "approved"
        relations = relations[:-1]

    result = engine.validate_graph(
        EngineeringGraph(elements=elements, relations=relations),
        profile,
        lifecycle_states=lifecycle_states,
    )

    assert result.valid is (not invalid)
    if invalid:
        assert any(issue.code == "MISSING_VERIFICATION" for issue in result.issues)
