"""End-to-end ARP4754A governance scenario at the application boundary."""

from uuid import uuid4

import pytest

from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.application.profile_loader import load_profile
from engineering_gateway.domain.audit import ActorType, InMemoryAuditSink
from engineering_gateway.domain.baselines import Baseline
from engineering_gateway.domain.change_control import AuthorizationLevel, ChangeRequest
from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation, ElementKind, RelationType
from engineering_gateway.domain.profiles import StandardProfile
from engineering_gateway.domain.workspaces import WorkspaceState
from engineering_gateway.infrastructure.profile_registry import InMemoryStandardProfileRegistry


@pytest.mark.asyncio
async def test_arp4754a_profile_accepts_requirement_architecture_and_verification_graph(tmp_path):
    profile = load_profile("profiles/arp4754a/1.0/profile.json")
    registry = InMemoryStandardProfileRegistry()
    await registry.register(profile)
    await registry.activate(profile.id, profile.version)

    requirement = EngineeringElement(
        kind=ElementKind.REQUIREMENT,
        type_id="system_requirement",
        name="The system shall provide controlled navigation output.",
        external_system="strictdoc",
        external_id="REQ-001",
        source_uri="strictdoc://REQ-001",
    )
    architecture = EngineeringElement(
        kind=ElementKind.ARCHITECTURE,
        type_id="system_architecture",
        name="Navigation subsystem",
        external_system="capella",
        external_id="CAP-001",
        source_uri="capella://CAP-001",
    )
    verification = EngineeringElement(
        kind=ElementKind.VERIFICATION,
        type_id="verification_activity",
        name="Navigation output verification",
        external_system="strictdoc",
        external_id="VER-001",
        source_uri="strictdoc://VER-001",
    )
    relations = [
        EngineeringRelation(
            source_id=requirement.id,
            relation_type=RelationType.ALLOCATED_TO,
            target_id=architecture.id,
        ),
        EngineeringRelation(
            source_id=requirement.id,
            relation_type=RelationType.VERIFIED_BY,
            target_id=verification.id,
        ),
    ]

    from engineering_gateway.application.validation import DeterministicValidationEngine

    result = DeterministicValidationEngine().validate(
        [requirement, architecture, verification], relations, profile,
        lifecycle_states={requirement.id: "draft"},
    )

    assert result.valid
    assert result.graph_hash
    assert result.profile_id == "arp4754a"
    assert result.profile_version == "1.0"
