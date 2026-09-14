"""End-to-end DO-178C governed workflow through the Gateway boundary."""

from pathlib import Path

import pytest

from engineering_gateway.application.change_request_service import ChangeRequestApplicationService
from engineering_gateway.application.governed_gateway_service import GovernedGatewayApplicationService
from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.domain.adapters import ExternalVersion, GitSnapshot
from engineering_gateway.domain.audit import ActorType, InMemoryAuditSink
from engineering_gateway.domain.baselines import Baseline, BaselineRegistry
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.models import ElementKind, EngineeringElement, EngineeringRelation, EngineeringGraph, RelationType
from engineering_gateway.domain.reconciliation import compute_change_set_hash
from engineering_gateway.domain.workspaces import WorkspaceRegistry, WorkspaceState
from engineering_gateway.infrastructure.profile_loader import load_standard_profile
from engineering_gateway.infrastructure.profile_registry import InMemoryStandardProfileRegistry
from engineering_gateway.infrastructure.workspace_changes import InMemoryWorkspaceChangeSetRepository
from engineering_gateway.infrastructure.workspace_reconciler import AdapterWorkspaceReconciler

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "profiles" / "do-178c" / "1.0" / "profile.json"


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
        return GitSnapshot(repository=repository, commit="def178")

    async def is_ancestor(self, repository: str, ancestor_commit: str, descendant_ref: str) -> bool:
        return True

    async def create_tag(self, repository: str, tag: str, commit: str) -> GitSnapshot:
        return GitSnapshot(repository=repository, commit=commit, tag=tag)


class FakeOpenProject:
    system_name = "openproject"

    async def create_change_request(self, title: str, description: str) -> str:
        return "178"

    async def update_change_request(self, external_id: str, status: str) -> None:
        return None

    async def get_element(self, external_id: str):
        return None

    async def get_version(self) -> ExternalVersion:
        return ExternalVersion(system=self.system_name, version="openproject-178")


class FakeWorkspaceAdapter:
    def __init__(self, system_name: str) -> None:
        self.system_name = system_name
        self.created = []
        self.elements = []
        self.relations = []

    async def get_element(self, external_id: str):
        return None

    async def get_version(self) -> ExternalVersion:
        return ExternalVersion(system=self.system_name, version=f"{self.system_name}-rev-178")

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
async def test_do_178c_governed_workflow_reaches_approved_baseline():
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
    engineer = Actor("software-engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    reviewer = Actor("software-reviewer", ActorType.HUMAN, AuthorizationLevel.L3_APPROVE)

    source = await baselines.register(Baseline(name="DO178C-B0", git_repository="software-repo", git_commit="abc178"))
    cr = await change_service.create_change_request(engineer, "Software requirement change", "Controlled DO-178C lifecycle change", source)

    strictdoc = FakeWorkspaceAdapter("strictdoc")
    capella = FakeWorkspaceAdapter("capella")
    git = FakeWorkspaceAdapter("git")
    reconciler = AdapterWorkspaceReconciler((strictdoc, capella, git), canonical)
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
    workspace = await gateway.create_workspace(engineer, source.id, cr.id, git_ref="feature/do-178c")

    hlr = EngineeringElement(kind=ElementKind.REQUIREMENT, type_id="high_level_requirement", name="HLR-178-001", external_system="strictdoc", external_id="HLR-178-001")
    llr = EngineeringElement(kind=ElementKind.REQUIREMENT, type_id="low_level_requirement", name="LLR-178-001", external_system="strictdoc", external_id="LLR-178-001")
    design = EngineeringElement(kind=ElementKind.ARCHITECTURE, type_id="software_design", name="Design-178-001", external_system="capella", external_id="DES-178-001")
    code = EngineeringElement(kind=ElementKind.CONFIGURATION, type_id="source_code", name="module_178.c", external_system="git", external_id="src/module_178.c")
    verification = EngineeringElement(kind=ElementKind.VERIFICATION, type_id="verification_case", name="TC-178-001", external_system="strictdoc", external_id="TC-178-001")
    for element in (hlr, llr, design, code, verification):
        await gateway.save_workspace_element(engineer, element, workspace.id)

    relations = (
        EngineeringRelation(source_id=llr.id, relation_type=RelationType.REFINES, target_id=hlr.id),
        EngineeringRelation(source_id=llr.id, relation_type=RelationType.ALLOCATED_TO, target_id=design.id),
        EngineeringRelation(source_id=design.id, relation_type=RelationType.IMPLEMENTS, target_id=code.id),
        EngineeringRelation(source_id=llr.id, relation_type=RelationType.VERIFIED_BY, target_id=verification.id),
    )
    for relation in relations:
        await gateway.add_workspace_relation(engineer, relation, workspace.id)

    validation = await gateway.prepare_for_approval(
        engineer,
        workspace.id,
        profile_id="do-178c",
        profile_version="1.0",
        lifecycle_states={hlr.id: "reviewed", llr.id: "reviewed", verification.id: "accepted"},
    )
    assert validation.valid
    stored = await workspaces.get(workspace.id)
    assert stored is not None and stored.state is WorkspaceState.READY_FOR_APPROVAL
    assert stored.validation_graph_hash == validation.graph_hash

    reconciliation = await gateway.reconcile_workspace(engineer, workspace.id)
    expected_hash = compute_change_set_hash(await workspace_changes.get_changes(workspace.id))
    assert reconciliation.change_set_hash == expected_hash
    assert {version.system for version in reconciliation.external_versions} == {"strictdoc", "capella", "git"}
    assert strictdoc.created == [(workspace.id, "abc178", expected_hash)]
    assert capella.created == [(workspace.id, "abc178", expected_hash)]
    assert git.created == [(workspace.id, "abc178", expected_hash)]
    assert strictdoc.relations == [relations[0], relations[3]]
    assert capella.relations == [relations[1]]
    assert git.relations == [relations[2]]

    baseline = await gateway.approve_workspace(reviewer, workspace.id)
    assert baseline.git_commit == "def178"
    assert baseline.git_tag == f"baseline-{workspace.id}"
    assert {version.system for version in baseline.external_versions} == {"strictdoc", "capella", "git"}
    stored = await workspaces.get(workspace.id)
    assert stored is not None and stored.state is WorkspaceState.APPROVED
