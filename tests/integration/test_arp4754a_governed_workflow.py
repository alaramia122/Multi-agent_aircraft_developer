"""End-to-end in-memory ARP4754A governed workflow."""

from pathlib import Path

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
from engineering_gateway.domain.reconciliation import compute_change_set_hash
from engineering_gateway.domain.workspaces import WorkspaceRegistry, WorkspaceState
from engineering_gateway.infrastructure.profile_loader import load_standard_profile
from engineering_gateway.infrastructure.profile_registry import InMemoryStandardProfileRegistry
from engineering_gateway.infrastructure.workspace_changes import (
    InMemoryWorkspaceChangeSetRepository,
)
from engineering_gateway.infrastructure.workspace_reconciler import AdapterWorkspaceReconciler

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "profiles" / "arp4754a" / "1.0" / "profile.json"


class CanonicalRepository:
    def __init__(self) -> None:
        self.elements = {}
        self.relations = {}

    async def get(self, element_id):
        return self.elements.get(element_id)

    async def save(self, element):
        self.elements[element.id] = element
        return element

    async def add_relation(self, relation):
        self.relations[relation.id] = relation
        return relation

    async def get_relations(self, element_id):
        return [
            r
            for r in self.relations.values()
            if r.source_id == element_id or r.target_id == element_id
        ]

    async def list_graph(self):
        return EngineeringGraph(
            elements=list(self.elements.values()), relations=list(self.relations.values())
        )


class FakeGit:
    system_name = "git"

    async def get_snapshot(self, repository: str, ref: str = "HEAD") -> GitSnapshot:
        return GitSnapshot(repository=repository, commit="def456")

    async def is_ancestor(self, repository: str, ancestor_commit: str, descendant_ref: str) -> bool:
        return True

    async def create_tag(self, repository: str, tag: str, commit: str) -> GitSnapshot:
        return GitSnapshot(repository=repository, commit=commit, tag=tag)


class FakeOpenProject:
    system_name = "openproject"

    async def create_change_request(self, title: str, description: str) -> str:
        return "42"

    async def update_change_request(self, external_id: str, status: str) -> None:
        return None

    async def get_element(self, external_id: str):
        return None

    async def get_version(self) -> ExternalVersion:
        return ExternalVersion(system=self.system_name, version="openproject-1")


class FakeWorkspaceAdapter:
    def __init__(self, system_name: str) -> None:
        self.system_name = system_name
        self.created = []
        self.elements = []
        self.relations = []

    async def get_element(self, external_id: str):
        return None

    async def get_version(self) -> ExternalVersion:
        return ExternalVersion(system=self.system_name, version=f"{self.system_name}-rev-1")

    async def get_workspace_version(self, workspace_id) -> ExternalVersion:
        return await self.get_version()

    async def create_workspace(self, workspace_id, source_version, change_set_hash):
        self.created.append((workspace_id, source_version, change_set_hash))

    async def apply_element(self, workspace_id, element):
        self.elements.append(element)

    async def apply_relation(self, workspace_id, relation):
        self.relations.append(relation)


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


@pytest.mark.asyncio
async def test_arp4754a_full_governed_workflow():
    profile = load_standard_profile(PROFILE)
    profiles = InMemoryStandardProfileRegistry()
    await profiles.register(profile)
    await profiles.activate(profile.id, profile.version)

    audit = InMemoryAuditSink()
    canonical = CanonicalRepository()
    workspace_changes = InMemoryWorkspaceChangeSetRepository(canonical)
    baselines = BaselineRegistry()
    workspaces = WorkspaceRegistry()
    change_requests = InMemoryChangeRequests()
    change_service = ChangeRequestApplicationService(change_requests, FakeOpenProject(), audit)
    engineer = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    reviewer = Actor("reviewer", ActorType.HUMAN, AuthorizationLevel.L3_APPROVE)

    source = await baselines.register(
        Baseline(name="B0", git_repository="repo", git_commit="abc123")
    )
    cr = await change_service.create_change_request(
        engineer, "Navigation change", "Controlled ARP4754A change", source
    )

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
        workspace_changes=workspace_changes,
        git=FakeGit(),
        external_adapters=(FakeOpenProject(),),
        workspace_reconciler=reconciler,
    )
    workspace = await gateway.create_workspace(
        engineer, source.id, cr.id, git_ref="feature/navigation"
    )

    requirement = EngineeringElement(
        kind=ElementKind.REQUIREMENT,
        type_id="system_requirement",
        name="REQ-001",
        external_system="strictdoc",
        external_id="REQ-001",
    )
    architecture = EngineeringElement(
        kind=ElementKind.ARCHITECTURE,
        type_id="system_architecture",
        name="Navigation subsystem",
        external_system="capella",
        external_id="CAP-001",
    )
    verification = EngineeringElement(
        kind=ElementKind.VERIFICATION,
        type_id="verification_activity",
        name="Verify navigation",
        external_system="strictdoc",
        external_id="VER-001",
    )
    for element in (requirement, architecture, verification):
        await gateway.save_workspace_element(engineer, element, workspace.id)
    allocation = EngineeringRelation(
        source_id=requirement.id, relation_type=RelationType.ALLOCATED_TO, target_id=architecture.id
    )
    verification_relation = EngineeringRelation(
        source_id=requirement.id, relation_type=RelationType.VERIFIED_BY, target_id=verification.id
    )
    await gateway.add_workspace_relation(engineer, allocation, workspace.id)
    await gateway.add_workspace_relation(engineer, verification_relation, workspace.id)

    validation = await gateway.prepare_for_approval(
        engineer,
        workspace.id,
        profile_id="arp4754a",
        profile_version="1.0",
        lifecycle_states={requirement.id: "draft"},
    )
    assert validation.valid
    stored = await workspaces.get(workspace.id)
    assert stored is not None and stored.state is WorkspaceState.READY_FOR_APPROVAL
    assert stored.validation_graph_hash == validation.graph_hash
    assert stored.validation_evidence["lifecycle_states"][str(requirement.id)] == "draft"

    reconciliation = await gateway.reconcile_workspace(engineer, workspace.id)
    expected_hash = compute_change_set_hash(await workspace_changes.get_changes(workspace.id))
    assert reconciliation.change_set_hash == expected_hash
    assert set(version.system for version in reconciliation.external_versions) == {
        "strictdoc",
        "capella",
    }
    assert strictdoc.created == [(workspace.id, "abc123", expected_hash)]
    assert capella.created == [(workspace.id, "abc123", expected_hash)]
    assert strictdoc.elements == [requirement, verification]
    assert capella.elements == [architecture]
    assert strictdoc.relations == [verification_relation]
    assert capella.relations == [allocation]

    baseline = await gateway.approve_workspace(reviewer, workspace.id)
    assert baseline.git_commit == "def456"
    assert baseline.git_tag == f"baseline-{workspace.id}"
    assert {v.system for v in baseline.external_versions} == {"strictdoc", "capella"}
    stored = await workspaces.get(workspace.id)
    assert stored is not None and stored.state is WorkspaceState.APPROVED

    with pytest.raises(GatewayServiceError, match="workspace is not active"):
        await gateway.save_workspace_element(engineer, requirement, workspace.id)
