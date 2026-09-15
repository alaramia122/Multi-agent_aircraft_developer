"""Adversarial governance scenarios for the Gateway application boundary."""

from pathlib import Path
from uuid import UUID

import pytest

from engineering_gateway.application.change_request_service import ChangeRequestApplicationService
from engineering_gateway.application.gateway_service import Actor, GatewayServiceError
from engineering_gateway.application.governed_gateway_service import (
    GovernedGatewayApplicationService,
)
from engineering_gateway.domain.adapters import ExternalVersion, GitSnapshot
from engineering_gateway.domain.audit import ActorType, InMemoryAuditSink
from engineering_gateway.domain.baselines import Baseline, BaselineRegistry
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.models import (
    ElementKind,
    EngineeringElement,
    EngineeringGraph,
    EngineeringRelation,
    RelationType,
)
from engineering_gateway.domain.workspaces import WorkspaceRegistry, WorkspaceState
from engineering_gateway.infrastructure.profile_loader import load_standard_profile
from engineering_gateway.infrastructure.profile_registry import InMemoryStandardProfileRegistry
from engineering_gateway.infrastructure.workspace_changes import InMemoryWorkspaceChangeSetRepository
from engineering_gateway.infrastructure.workspace_reconciler import AdapterWorkspaceReconciler

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "profiles" / "arp4754a" / "1.0" / "profile.json"


class CanonicalRepository:
    def __init__(self) -> None:
        self.elements = {}
        self.relations = {}

    async def get(self, element_id: UUID):
        return self.elements.get(element_id)

    async def save(self, element):
        self.elements[element.id] = element
        return element

    async def add_relation(self, relation):
        self.relations[relation.id] = relation
        return relation

    async def get_relations(self, element_id: UUID):
        return [
            relation
            for relation in self.relations.values()
            if relation.source_id == element_id or relation.target_id == element_id
        ]

    async def list_graph(self):
        return EngineeringGraph(
            elements=list(self.elements.values()), relations=list(self.relations.values())
        )


class FakeGit:
    async def get_snapshot(self, repository: str, ref: str = "HEAD") -> GitSnapshot:
        return GitSnapshot(repository=repository, commit="feature-commit")

    async def is_ancestor(self, repository: str, ancestor_commit: str, descendant_ref: str) -> bool:
        return True

    async def create_tag(self, repository: str, tag: str, commit: str) -> GitSnapshot:
        return GitSnapshot(repository=repository, commit=commit, tag=tag)


class FakeOpenProject:
    async def create_change_request(self, title: str, description: str) -> str:
        return "CR-1"

    async def update_change_request(self, external_id: str, status: str) -> None:
        return None

    async def get_element(self, external_id: str):
        return None

    async def get_version(self) -> ExternalVersion:
        return ExternalVersion(system="openproject", version="1")


class FakeWorkspaceAdapter:
    def __init__(self, system_name: str) -> None:
        self.system_name = system_name
        self.create_calls = 0

    async def get_element(self, external_id: str):
        return None

    async def get_version(self) -> ExternalVersion:
        return ExternalVersion(system=self.system_name, version="1")

    async def create_workspace(self, workspace_id, source_version, change_set_hash):
        self.create_calls += 1

    async def apply_element(self, workspace_id, element):
        return None

    async def apply_relation(self, workspace_id, relation):
        return None


class InMemoryChangeRequests:
    def __init__(self) -> None:
        self.items = {}

    async def create(self, item):
        self.items[item.id] = item
        return item

    async def get(self, item_id):
        return self.items.get(item_id)

    async def update(self, item):
        self.items[item.id] = item
        return item


async def _gateway():
    profile = load_standard_profile(PROFILE)
    profiles = InMemoryStandardProfileRegistry()
    await profiles.register(profile)
    await profiles.activate(profile.id, profile.version)

    canonical = CanonicalRepository()
    audit = InMemoryAuditSink()
    baselines = BaselineRegistry()
    workspaces = WorkspaceRegistry()
    change_requests = InMemoryChangeRequests()
    changes = InMemoryWorkspaceChangeSetRepository(canonical)
    openproject = FakeOpenProject()
    change_service = ChangeRequestApplicationService(change_requests, openproject, audit)
    strictdoc = FakeWorkspaceAdapter("strictdoc")
    capella = FakeWorkspaceAdapter("capella")
    reconciler = AdapterWorkspaceReconciler((strictdoc, capella), canonical)
    gateway = GovernedGatewayApplicationService(
        canonical,
        profiles,
        audit,
        baselines=baselines,
        change_requests=change_requests,
        workspaces=workspaces,
        workspace_changes=changes,
        git=FakeGit(),
        external_adapters=(openproject,),
        workspace_reconciler=reconciler,
    )
    engineer = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    reviewer = Actor("reviewer", ActorType.HUMAN, AuthorizationLevel.L3_APPROVE)
    ai = Actor("agent", ActorType.AI, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    source = await baselines.register(
        Baseline(name="B0", git_repository="repo", git_commit="baseline-commit")
    )
    change_request = await change_service.create_change_request(
        engineer, "Controlled change", "Adversarial governance test", source
    )
    workspace = await gateway.create_workspace(engineer, source.id, change_request.id)

    requirement = EngineeringElement(
        kind=ElementKind.REQUIREMENT,
        type_id="system_requirement",
        name="REQ-1",
        external_system="strictdoc",
        external_id="REQ-1",
    )
    architecture = EngineeringElement(
        kind=ElementKind.ARCHITECTURE,
        type_id="system_architecture",
        name="ARCH-1",
        external_system="capella",
        external_id="ARCH-1",
    )
    verification = EngineeringElement(
        kind=ElementKind.VERIFICATION,
        type_id="verification_activity",
        name="VER-1",
        external_system="strictdoc",
        external_id="VER-1",
    )
    for element in (requirement, architecture, verification):
        await gateway.save_workspace_element(engineer, element, workspace.id)

    await gateway.add_workspace_relation(
        engineer,
        EngineeringRelation(
            source_id=requirement.id,
            relation_type=RelationType.ALLOCATED_TO,
            target_id=architecture.id,
        ),
        workspace.id,
    )
    await gateway.add_workspace_relation(
        engineer,
        EngineeringRelation(
            source_id=requirement.id,
            relation_type=RelationType.VERIFIED_BY,
            target_id=verification.id,
        ),
        workspace.id,
    )
    await gateway.prepare_for_approval(
        engineer,
        workspace.id,
        profile_id="arp4754a",
        profile_version="1.0",
        lifecycle_states={requirement.id: "draft"},
    )
    await gateway.reconcile_workspace(engineer, workspace.id)
    return gateway, workspaces, change_requests, workspace.id, reviewer, ai, strictdoc, capella


@pytest.mark.asyncio
async def test_ai_cannot_approve_ready_workspace():
    gateway, _, _, workspace_id, _, ai, _, _ = await _gateway()

    with pytest.raises(GatewayServiceError, match="L3"):
        await gateway.approve_workspace(ai, workspace_id)


@pytest.mark.asyncio
async def test_rejection_clears_evidence_and_reopen_requires_new_preparation():
    gateway, workspaces, change_requests, workspace_id, reviewer, _, strictdoc, capella = await _gateway()

    await gateway.reject_workspace(reviewer, workspace_id, "Architecture review rejected")

    workspace = await workspaces.get(workspace_id)
    assert workspace is not None
    change_request = await change_requests.get(workspace.change_request_id)
    assert workspace.state is WorkspaceState.ACTIVE
    assert workspace.validation_graph_hash is None
    assert not workspace.reconciled
    assert workspace.reconciled_change_set_hash is None
    assert not workspace.reconciliation_external_versions
    assert change_request is not None
    assert change_request.state.value == "rejected"

    engineer = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    await gateway.reopen_workspace(engineer, workspace_id)
    change_request = await change_requests.get(workspace.change_request_id)
    assert change_request is not None
    assert change_request.state.value == "in_progress"

    with pytest.raises(GatewayServiceError, match="ready for approval"):
        await gateway.reconcile_workspace(engineer, workspace_id)
    assert strictdoc.create_calls == 1
    assert capella.create_calls == 1


@pytest.mark.asyncio
async def test_rejection_requires_human_l3():
    gateway, _, _, workspace_id, _, ai, _, _ = await _gateway()

    with pytest.raises(GatewayServiceError, match="human L3"):
        await gateway.reject_workspace(ai, workspace_id, "not authorized")
