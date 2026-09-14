"""Tests for the governed Gateway application service."""

from uuid import UUID, uuid4

import pytest

from engineering_gateway.application.gateway_service import (
    Actor,
    GatewayApplicationService,
    GatewayServiceError,
)
from engineering_gateway.domain.adapters import ExternalVersion, GitSnapshot
from engineering_gateway.domain.audit import ActorType, InMemoryAuditSink
from engineering_gateway.domain.baselines import Baseline, BaselineRegistry
from engineering_gateway.domain.change_control import (
    AuthorizationLevel,
    ChangeRequest,
    ChangeRequestState,
)
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

    def __init__(self, commit: str = "def456", ancestor: bool = True) -> None:
        self.commit = commit
        self.ancestor = ancestor
        self.tags: list[tuple[str, str, str]] = []

    async def get_snapshot(self, repository: str, ref: str = "HEAD") -> GitSnapshot:
        return GitSnapshot(repository=repository, commit=self.commit, tag=None)

    async def is_ancestor(self, repository: str, ancestor_commit: str, descendant_ref: str) -> bool:
        return self.ancestor

    async def create_tag(self, repository: str, tag: str, commit: str) -> GitSnapshot:
        self.tags.append((repository, tag, commit))
        return GitSnapshot(repository=repository, commit=commit, tag=tag)


class FakeExternalAdapter:
    system_name = "strictdoc"

    async def get_element(self, external_id: str) -> EngineeringElement | None:
        return None

    async def get_version(self) -> ExternalVersion:
        return ExternalVersion(system=self.system_name, version="rev-42")


class InMemoryChangeRequests:
    def __init__(self) -> None:
        self.items: dict[UUID, ChangeRequest] = {}

    async def create(self, change_request: ChangeRequest) -> ChangeRequest:
        self.items[change_request.id] = change_request
        return change_request

    async def get(self, change_request_id: UUID) -> ChangeRequest | None:
        return self.items.get(change_request_id)

    async def update(self, change_request: ChangeRequest) -> ChangeRequest:
        if change_request.id not in self.items:
            raise ValueError("change request does not exist")
        self.items[change_request.id] = change_request
        return change_request


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
    change_requests = InMemoryChangeRequests()
    git = FakeGit()
    gateway = GatewayApplicationService(
        repository,
        profiles,
        audit,
        baselines=baselines,
        change_requests=change_requests,
        workspaces=workspaces,
        git=git,
        external_adapters=(FakeExternalAdapter(),),
    )
    return gateway, audit, baselines, workspaces, git, change_requests


async def make_change_request(
    change_requests: InMemoryChangeRequests, baseline_id: UUID | None = None
) -> ChangeRequest:
    change_request = ChangeRequest(
        external_system="openproject",
        external_id=f"CR-{uuid4()}",
        title="Controlled change",
        source_baseline_id=baseline_id,
    )
    await change_requests.create(change_request)
    return change_request


async def mark_workspace_ready(
    workspace, workspaces: WorkspaceRegistry, change_requests: InMemoryChangeRequests, change_request: ChangeRequest
) -> None:
    ready = workspace.model_copy(
        update={
            "state": WorkspaceState.READY_FOR_APPROVAL,
            "profile_id": "test-profile",
            "profile_version": "1.0",
            "reconciliation_external_versions": (
                ExternalVersion(system="strictdoc", version="rev-42"),
            ),
        }
    )
    await workspaces.update(ready)
    await change_requests.update(
        change_request.model_copy(
            update={
                "state": ChangeRequestState.READY_FOR_APPROVAL,
                "source_baseline_id": ready.source_baseline_id,
                "workspace_id": ready.id,
            }
        )
    )


@pytest.mark.asyncio
async def test_read_is_audited(service, actor_read: Actor) -> None:
    gateway, audit, repository = service
    element = EngineeringElement(
        kind="requirement",
        type_id="requirement",
        name="REQ-1",
        external_system="strictdoc",
        external_id="REQ-1",
    )
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
async def test_workspace_write_requires_configured_active_workspace(service) -> None:
    gateway, _, _ = service
    actor = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    element = EngineeringElement(
        kind="requirement",
        type_id="requirement",
        name="REQ-2",
        external_system="strictdoc",
        external_id="REQ-2",
    )
    with pytest.raises(
        GatewayServiceError, match="workspace/change-request registries are not configured"
    ):
        await gateway.save_workspace_element(actor, element, uuid4())


@pytest.mark.asyncio
async def test_read_actor_cannot_write_workspace(service, actor_read: Actor) -> None:
    gateway, _, _ = service
    element = EngineeringElement(
        kind="requirement",
        type_id="requirement",
        name="REQ-3",
        external_system="strictdoc",
        external_id="REQ-3",
    )
    with pytest.raises(GatewayServiceError, match="only L2"):
        await gateway.save_workspace_element(actor_read, element, uuid4())


@pytest.mark.asyncio
async def test_unknown_profile_is_rejected_and_audited(service, actor_read: Actor) -> None:
    gateway, audit, _ = service
    with pytest.raises(GatewayServiceError, match="was not found"):
        await gateway.validate(actor_read, [], [], "missing", "1.0")
    assert (await audit.list())[-1].result.value == "failure"


@pytest.mark.asyncio
async def test_workspace_requires_existing_change_request(workflow_service) -> None:
    gateway, _, baselines, _, _, _ = workflow_service
    source = await baselines.register(
        Baseline(name="B0", git_repository="repo", git_commit="abc123")
    )
    actor = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    with pytest.raises(GatewayServiceError, match="change request.*not found"):
        await gateway.create_workspace(actor, source.id, uuid4())


@pytest.mark.asyncio
async def test_workspace_creation_binds_baseline_and_change_request(workflow_service) -> None:
    gateway, audit, baselines, workspaces, _, change_requests = workflow_service
    source = await baselines.register(
        Baseline(name="B0", git_repository="repo", git_commit="abc123")
    )
    change_request = await make_change_request(change_requests)
    actor = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    workspace = await gateway.create_workspace(
        actor, source.id, change_request.id, git_ref="feature/change-1"
    )
    stored_cr = await change_requests.get(change_request.id)
    assert workspace.source_baseline_id == source.id
    assert workspace.source_git_commit == source.git_commit
    assert workspace.git_ref == "feature/change-1"
    assert stored_cr is not None
    assert stored_cr.state is ChangeRequestState.IN_PROGRESS
    assert stored_cr.source_baseline_id == source.id
    assert stored_cr.workspace_id == workspace.id
    assert await workspaces.get(workspace.id) == workspace
    assert (await audit.list())[-1].action == "create_workspace"


@pytest.mark.asyncio
async def test_only_active_workspace_can_be_modified(workflow_service) -> None:
    gateway, _, baselines, workspaces, _, change_requests = workflow_service
    source = await baselines.register(
        Baseline(name="B0", git_repository="repo", git_commit="abc123")
    )
    change_request = await make_change_request(change_requests)
    actor = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    workspace = await gateway.create_workspace(actor, source.id, change_request.id)
    await workspaces.update(
        workspace.model_copy(update={"state": WorkspaceState.READY_FOR_APPROVAL})
    )
    element = EngineeringElement(
        kind="requirement",
        type_id="requirement",
        name="REQ",
        external_system="strictdoc",
        external_id="REQ",
    )
    with pytest.raises(GatewayServiceError, match="not active"):
        await gateway.save_workspace_element(actor, element, workspace.id)


@pytest.mark.asyncio
async def test_ai_cannot_approve_workspace(workflow_service, actor_ai: Actor) -> None:
    gateway, _, baselines, workspaces, _, change_requests = workflow_service
    source = await baselines.register(
        Baseline(name="B0", git_repository="repo", git_commit="abc123")
    )
    change_request = await make_change_request(change_requests)
    workspace = await gateway.create_workspace(
        Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE),
        source.id,
        change_request.id,
    )
    await mark_workspace_ready(workspace, workspaces, change_requests, change_request)
    with pytest.raises(GatewayServiceError, match="human L3 approver"):
        await gateway.approve_workspace(actor_ai, workspace.id)


@pytest.mark.asyncio
async def test_approval_requires_both_workspace_and_change_request_ready(workflow_service) -> None:
    gateway, _, baselines, workspaces, _, change_requests = workflow_service
    source = await baselines.register(
        Baseline(name="B0", git_repository="repo", git_commit="abc123")
    )
    change_request = await make_change_request(change_requests)
    workspace = await gateway.create_workspace(
        Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE),
        source.id,
        change_request.id,
    )
    await workspaces.update(
        workspace.model_copy(update={"state": WorkspaceState.READY_FOR_APPROVAL})
    )
    with pytest.raises(GatewayServiceError, match="both be ready"):
        await gateway.approve_workspace(
            Actor("reviewer", ActorType.HUMAN, AuthorizationLevel.L3_APPROVE), workspace.id
        )


@pytest.mark.asyncio
async def test_approve_workspace_updates_change_request_and_derives_baseline(
    workflow_service,
) -> None:
    gateway, _, baselines, workspaces, git, change_requests = workflow_service
    source = await baselines.register(
        Baseline(name="B0", git_repository="repo", git_commit="abc123")
    )
    change_request = await make_change_request(change_requests)
    workspace = await gateway.create_workspace(
        Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE),
        source.id,
        change_request.id,
        git_ref="feature/change-1",
    )
    await mark_workspace_ready(workspace, workspaces, change_requests, change_request)
    registered = await gateway.approve_workspace(
        Actor("reviewer", ActorType.HUMAN, AuthorizationLevel.L3_APPROVE), workspace.id
    )
    assert registered.git_commit == "def456"
    assert registered.git_tag == f"baseline-{workspace.id}"
    assert registered.external_versions[0].system == "strictdoc"
    assert registered.external_versions[0].version == "rev-42"
    assert git.tags == [("repo", f"baseline-{workspace.id}", "def456")]
    assert (await workspaces.get(workspace.id)).state is WorkspaceState.APPROVED
    stored_cr = await change_requests.get(change_request.id)
    assert stored_cr is not None
    assert stored_cr.state is ChangeRequestState.APPROVED
    assert stored_cr.workspace_id == workspace.id
    assert await baselines.get(registered.id) == registered


@pytest.mark.asyncio
async def test_approval_rejects_unrelated_git_history(workflow_service) -> None:
    gateway, _, baselines, workspaces, git, change_requests = workflow_service
    source = await baselines.register(
        Baseline(name="B0", git_repository="repo", git_commit="abc123")
    )
    change_request = await make_change_request(change_requests)
    workspace = await gateway.create_workspace(
        Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE),
        source.id,
        change_request.id,
    )
    await mark_workspace_ready(workspace, workspaces, change_requests, change_request)
    git.ancestor = False
    with pytest.raises(GatewayServiceError, match="does not descend"):
        await gateway.approve_workspace(
            Actor("reviewer", ActorType.HUMAN, AuthorizationLevel.L3_APPROVE), workspace.id
        )
