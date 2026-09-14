"""End-to-end in-memory ARP4754A governed workflow."""

from pathlib import Path
from uuid import uuid4

import pytest

from engineering_gateway.application.change_request_service import ChangeRequestApplicationService
from engineering_gateway.application.governed_gateway_service import GovernedGatewayApplicationService
from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.domain.adapters import ExternalVersion, GitSnapshot
from engineering_gateway.domain.audit import ActorType, InMemoryAuditSink
from engineering_gateway.domain.baselines import Baseline, BaselineRegistry
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.models import ElementKind, EngineeringElement, EngineeringGraph, EngineeringRelation, RelationType
from engineering_gateway.domain.reconciliation import compute_change_set_hash
from engineering_gateway.domain.workspaces import WorkspaceRegistry, WorkspaceState
from engineering_gateway.infrastructure.profile_loader import load_standard_profile
from engineering_gateway.infrastructure.profile_registry import InMemoryStandardProfileRegistry
from engineering_gateway.infrastructure.workspace_changes import InMemoryWorkspaceChangeSetRepository


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
        return [r for r in self.relations.values() if r.source_id == element_id or r.target_id == element_id]

    async def list_graph(self):
        return EngineeringGraph(elements=list(self.elements.values()), relations=list(self.relations.values()))


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


class FakeReconciler:
    async def reconcile(self, workspace, changes):
        return (ExternalVersion(system="strictdoc", version="strictdoc-1"), ExternalVersion(system="capella", version="capella-1"))


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
    from engineering_gateway.domain.change_control import ChangeRequest

    class Changes:
        def __init__(self):
            self.items = {}
        async def create(self, item):
            self.items[item.id] = item
            return item
        async def get(self, item_id):
            return self.items.get(item_id)
        async def update(self, item):
            self.items[item.id] = item
            return item

    change_requests = Changes()
    change_service = ChangeRequestApplicationService(change_requests, FakeOpenProject(), audit)
    engineer = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    reviewer = Actor("reviewer", ActorType.HUMAN, AuthorizationLevel.L3_APPROVE)

    source = await baselines.register(Baseline(name="B0", git_repository="repo", git_commit="abc123"))
    cr = await change_service.create_change_request(engineer, "Navigation change", "Controlled ARP4754A change", source)
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
        workspace_reconciler=FakeReconciler(),
    )
    workspace = await gateway.create_workspace(engineer, source.id, cr.id, git_ref="feature/navigation")

    requirement = EngineeringElement(kind=ElementKind.REQUIREMENT, type_id="system_requirement", name="REQ-001", external_system="strictdoc", external_id="REQ-001")
    architecture = EngineeringElement(kind=ElementKind.ARCHITECTURE, type_id="system_architecture", name="Navigation subsystem", external_system="capella", external_id="CAP-001")
    verification = EngineeringElement(kind=ElementKind.VERIFICATION, type_id="verification_activity", name="Verify navigation", external_system="strictdoc", external_id="VER-001")
    for element in (requirement, architecture, verification):
        await gateway.save_workspace_element(engineer, element, workspace.id)
    await gateway.add_workspace_relation(engineer, EngineeringRelation(source_id=requirement.id, relation_type=RelationType.ALLOCATED_TO, target_id=architecture.id), workspace.id)
    await gateway.add_workspace_relation(engineer, EngineeringRelation(source_id=requirement.id, relation_type=RelationType.VERIFIED_BY, target_id=verification.id), workspace.id)

    validation = await gateway.prepare_for_approval(engineer, workspace.id, profile_id="arp4754a", profile_version="1.0", lifecycle_states={requirement.id: "draft"})
    assert validation.valid
    assert (await workspaces.get(workspace.id)).state is WorkspaceState.READY_FOR_APPROVAL
    assert (await workspaces.get(workspace.id)).validation_graph_hash == validation.graph_hash

    reconciliation = await gateway.reconcile_workspace(engineer, workspace.id)
    assert reconciliation.change_set_hash == compute_change_set_hash(await workspace_changes.get_changes(workspace.id))
    assert (await workspaces.get(workspace.id)).reconciled

    baseline = await gateway.approve_workspace(reviewer, workspace.id)
    assert baseline.git_commit == "def456"
    assert baseline.git_tag == f"baseline-{workspace.id}"
    assert (await workspaces.get(workspace.id)).state is WorkspaceState.APPROVED

    with pytest.raises(Exception):
        await gateway.save_workspace_element(engineer, requirement, workspace.id)
