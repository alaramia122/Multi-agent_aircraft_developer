"""Tests for the governed Gateway application service."""

from uuid import UUID, uuid4

import pytest

from engineering_gateway.application.gateway_service import Actor, GatewayApplicationService, GatewayServiceError
from engineering_gateway.domain.adapters import ExternalVersion, GitSnapshot
from engineering_gateway.domain.audit import ActorType, InMemoryAuditSink
from engineering_gateway.domain.baselines import Baseline, BaselineRegistry
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation
from engineering_gateway.domain.workspaces import WorkspaceRegistry, WorkspaceState
from engineering_gateway.infrastructure.profile_registry import InMemoryStandardProfileRegistry


class FakeRepository:
    def __init__(self) -> None:
        self.elements: dict[UUID, EngineeringElement] = {}
        self.relations: list[EngineeringRelation] = []

    async def get(self, element_id: UUID) -> EngineeringElement | None:
        return self.elements.get(element_id)

    async def save(self, element: EngineeringElement) -> EngineeringElement:
        self.elements[element.id] = element
        return element

    async def add_relation(self, relation: EngineeringRelation) -> EngineeringRelation:
        self.relations.append(relation)
        return relation

    async def get_relations(self, element_id: UUID) -> list[EngineeringRelation]:
        return [r for r in self.relations if r.source_id == element_id or r.target_id == element_id]


class FakeGit:
    system_name = "git"

    def __init__(self, commit: str = "def456") -> None:
        self.commit = commit
        self.tags: list[tuple[str, str, str]] = []

    async def get_snapshot(self, repository: str, ref: str = "HEAD") -> GitSnapshot:
        return GitSnapshot(repository=repository, commit=self.commit, tag=None)

    async def create_tag(self, repository: str, tag: str, commit: str) -> GitSnapshot:
        self.tags.append((repository, tag, commit))
        return GitSnapshot(repository=repository, commit=commit, tag=tag)


class FakeExternalAdapter:
    system_name = "strictdoc"

    async def get_element(self, external_id: str) -> EngineeringElement | None:
        return None

    async def get_version(self) -> ExternalVersion:
        return ExternalVersion(system=self.system_name, version="rev-42")


@pytest.fixture
def actor_read() -> Actor:
    return Actor("human-reader", ActorType.HUMAN, AuthorizationLevel.L0_READ)


@pytest.fixture
def actor_ai() -> Actor:
    return Actor("agent", ActorType.AI, AuthorizationLevel.L3_APPROVE)


@pytest.fixture
def service():
    audit = InMemoryAuditSink()
    repository = FakeRepository()
    profiles = InMemoryStandardProfileRegistry()
    return GatewayApplicationService(repository, profiles, audit), audit, repository


@pytest.fixture
async def workflow_service():
    audit = InMemoryAuditSink()
    repository = FakeRepository()
    profiles = InMemoryStandardProfileRegistry()
    baselines = BaselineRegistry()
    workspaces = WorkspaceRegistry()
    git = FakeGit()
    gateway = GatewayApplicationService(
        repository, profiles, audit, baselines=baselines, workspaces=workspaces,
        git=git, external_adapters=(FakeExternalAdapter(),),
    )
    return gateway, audit, baselines, workspaces, git


@pytest.mark.asyncio
async def test_read_is_audited(service, actor_read: Actor) -> None:
    gateway, audit, repository = service
    element = EngineeringElement(kind="requirement", type_id="requirement", name="REQ-1", external_system="strictdoc", external_id="REQ-1")
    await repository.save(element)
    result = await gateway.get_element(actor_read, element.id)
    assert result == element
    assert (await audit.list())[-1].action == "get_element"


@pytest.mark.asyncio
async def test_ai_cannot_approve(service, actor_ai: Actor) -> None:
    gateway, audit, _ = service
    with pytest.raises(GatewayServiceError, match="human L3 approver"):
        await gateway.approve(actor_ai, uuid4())
    assert (await audit.list())[-1].result.value == "denied"


@pytest.mark.asyncio
async def test_l2_workspace_write_is_audited(service) -> None:
    gateway, audit, _ = service
    actor = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    workspace_id = uuid4()
    element = EngineeringElement(kind="requirement", type_id="requirement", name="REQ-2", external_system="strictdoc", external_id="REQ-2")
    result = await gateway.save_workspace_element(actor, element, workspace_id)
    assert result == element
    assert (await audit.list())[-1].action == "save_workspace_element"


@pytest.mark.asyncio
async def test_read_actor_cannot_write_workspace(service, actor_read: Actor) -> None:
    gateway, audit, _ = service
    element = EngineeringElement(kind="requirement", type_id="requirement", name="REQ-3", external_system="strictdoc", external_id="REQ-3")
    with pytest.raises(GatewayServiceError, match="only L2"):
        await gateway.save_workspace_element(actor_read, element, uuid4())
    assert (await audit.list())[-1].result.value == "denied"


@pytest.mark.asyncio
async def test_unknown_profile_is_rejected_and_audited(service, actor_read: Actor) -> None:
    gateway, audit, _ = service
    with pytest.raises(GatewayServiceError, match="was not found"):
        await gateway.validate(actor_read, [], [], "missing", "1.0")
    assert (await audit.list())[-1].result.value == "failure"


@pytest.mark.asyncio
async def test_workspace_must_originate_from_existing_baseline(workflow_service) -> None:
    gateway, _, _, _, _ = workflow_service
    actor = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    with pytest.raises(GatewayServiceError, match="was not found"):
        await gateway.create_workspace(actor, uuid4(), uuid4())


@pytest.mark.asyncio
async def test_workspace_creation_records_source_baseline(workflow_service) -> None:
    gateway, audit, baselines, workspaces, _ = workflow_service
    source = await baselines.register(Baseline(name="B0", git_repository="repo", git_commit="abc123"))
    actor = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    workspace = await gateway.create_workspace(actor, source.id, uuid4(), git_ref="feature/change-1")
    assert workspace.source_baseline_id == source.id
    assert workspace.git_ref == "feature/change-1"
    assert await workspaces.get(workspace.id) == workspace
    assert (await audit.list())[-1].action == "create_workspace"


@pytest.mark.asyncio
async def test_only_active_workspace_can_be_modified(workflow_service) -> None:
    gateway, _, baselines, workspaces, _ = workflow_service
    source = await baselines.register(Baseline(name="B0", git_repository="repo", git_commit="abc123"))
    actor = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    workspace = await gateway.create_workspace(actor, source.id, uuid4())
    await workspaces.update(workspace.model_copy(update={"state": WorkspaceState.READY_FOR_APPROVAL}))
    element = EngineeringElement(kind="requirement", type_id="requirement", name="REQ", external_system="strictdoc", external_id="REQ")
    with pytest.raises(GatewayServiceError, match="not active"):
        await gateway.save_workspace_element(actor, element, workspace.id)


@pytest.mark.asyncio
async def test_ai_cannot_approve_workspace(workflow_service, actor_ai: Actor) -> None:
    gateway, _, baselines, workspaces, _ = workflow_service
    source = await baselines.register(Baseline(name="B0", git_repository="repo", git_commit="abc123"))
    workspace = await gateway.create_workspace(Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE), source.id, uuid4())
    await workspaces.update(workspace.model_copy(update={"state": WorkspaceState.READY_FOR_APPROVAL}))
    with pytest.raises(GatewayServiceError, match="human L3 approver"):
        await gateway.approve_workspace(actor_ai, workspace.id)


@pytest.mark.asyncio
async def test_approve_workspace_derives_new_baseline_from_authoritative_snapshots(workflow_service) -> None:
    gateway, _, baselines, workspaces, git = workflow_service
    source = await baselines.register(Baseline(name="B0", git_repository="repo", git_commit="abc123"))
    workspace = await gateway.create_workspace(Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE), source.id, uuid4(), git_ref="feature/change-1")
    await workspaces.update(workspace.model_copy(update={"state": WorkspaceState.READY_FOR_APPROVAL}))
    registered = await gateway.approve_workspace(Actor("reviewer", ActorType.HUMAN, AuthorizationLevel.L3_APPROVE), workspace.id)
    assert registered.git_commit == "def456"
    assert registered.git_tag == f"baseline-{workspace.id}"
    assert registered.external_versions[0].system == "strictdoc"
    assert registered.external_versions[0].version == "rev-42"
    assert git.tags == [("repo", f"baseline-{workspace.id}", "def456")]
    assert (await workspaces.get(workspace.id)).state is WorkspaceState.APPROVED
    assert await baselines.get(registered.id) == registered


@pytest.mark.asyncio
async def test_approval_does_not_accept_caller_supplied_baseline(workflow_service) -> None:
    gateway, _, baselines, workspaces, _ = workflow_service
    source = await baselines.register(Baseline(name="B0", git_repository="repo", git_commit="abc123"))
    workspace = await gateway.create_workspace(Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE), source.id, uuid4())
    await workspaces.update(workspace.model_copy(update={"state": WorkspaceState.READY_FOR_APPROVAL}))
    result = await gateway.approve_workspace(Actor("reviewer", ActorType.HUMAN, AuthorizationLevel.L3_APPROVE), workspace.id)
    assert result.git_commit != "attacker-controlled-commit"
