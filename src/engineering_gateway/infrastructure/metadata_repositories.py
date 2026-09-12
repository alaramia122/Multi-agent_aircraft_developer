"""Persistence implementations for Gateway metadata."""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engineering_gateway.domain.audit import AuditEvent
from engineering_gateway.domain.baselines import Baseline, ExternalSystemVersion
from engineering_gateway.domain.change_control import ChangeRequest, ChangeRequestState
from engineering_gateway.domain.profiles import StandardProfile
from engineering_gateway.domain.workspaces import Workspace, WorkspaceState
from engineering_gateway.infrastructure.metadata_models import (
    AuditEventRecord,
    BaselineRecord,
    ChangeRequestRecord,
    StandardProfileRecord,
    WorkspaceRecord,
)


class SqlAlchemyStandardProfileRegistry:
    """Durable Standard Profile registry with immutable version identities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def register(self, profile: StandardProfile) -> None:
        existing = await self._session.scalar(select(StandardProfileRecord).where(StandardProfileRecord.profile_id == profile.id, StandardProfileRecord.version == profile.version))
        definition = profile.model_dump(mode="json")
        if existing is not None:
            if existing.definition != definition:
                raise ValueError(f"profile '{profile.id}@{profile.version}' already exists")
            return
        self._session.add(StandardProfileRecord(id=uuid4(), profile_id=profile.id, version=profile.version, name=profile.name, definition=definition))
        await self._session.commit()

    async def get(self, profile_id: str, version: str) -> StandardProfile | None:
        record = await self._session.scalar(select(StandardProfileRecord).where(StandardProfileRecord.profile_id == profile_id, StandardProfileRecord.version == version))
        return StandardProfile.model_validate(record.definition) if record else None

    async def list(self) -> list[StandardProfile]:
        result = await self._session.scalars(select(StandardProfileRecord).order_by(StandardProfileRecord.profile_id, StandardProfileRecord.version))
        return [StandardProfile.model_validate(record.definition) for record in result]


class SqlAlchemyBaselineRegistry:
    """Durable immutable baseline registry."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def register(self, baseline: Baseline) -> Baseline:
        existing = await self._session.get(BaselineRecord, baseline.id)
        if existing is not None:
            stored = _to_baseline(existing)
            if stored != baseline:
                raise ValueError(f"baseline '{baseline.id}' already exists and is immutable")
            return baseline
        self._session.add(BaselineRecord(id=baseline.id, name=baseline.name, git_repository=baseline.git_repository, git_commit=baseline.git_commit, git_tag=baseline.git_tag, external_versions=[item.model_dump(mode="json") for item in baseline.external_versions]))
        await self._session.commit()
        return baseline

    async def get(self, baseline_id: UUID) -> Baseline | None:
        record = await self._session.get(BaselineRecord, baseline_id)
        return _to_baseline(record) if record else None

    async def list(self) -> list[Baseline]:
        result = await self._session.scalars(select(BaselineRecord).order_by(BaselineRecord.id))
        return [_to_baseline(record) for record in result]


class SqlAlchemyChangeRequestRepository:
    """Durable Gateway reference store for controlled change requests."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, change_request: ChangeRequest) -> ChangeRequest:
        if await self.get(change_request.id) is not None:
            raise ValueError(f"change request '{change_request.id}' already exists")
        self._session.add(ChangeRequestRecord(
            id=change_request.id, external_system=change_request.external_system,
            external_id=change_request.external_id, title=change_request.title,
            state=change_request.state.value, source_baseline_id=change_request.source_baseline_id,
            workspace_id=change_request.workspace_id,
        ))
        await self._session.commit()
        return change_request

    async def get(self, change_request_id: UUID) -> ChangeRequest | None:
        record = await self._session.get(ChangeRequestRecord, change_request_id)
        return _to_change_request(record) if record else None

    async def update(self, change_request: ChangeRequest) -> ChangeRequest:
        record = await self._session.get(ChangeRequestRecord, change_request.id)
        if record is None:
            raise ValueError(f"change request '{change_request.id}' does not exist")
        record.state = change_request.state.value
        record.source_baseline_id = change_request.source_baseline_id
        record.workspace_id = change_request.workspace_id
        await self._session.commit()
        return change_request


class SqlAlchemyWorkspaceRegistry:
    """Durable Gateway-owned controlled workspace state."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, workspace: Workspace) -> Workspace:
        if await self.get(workspace.id) is not None:
            raise ValueError(f"workspace '{workspace.id}' already exists")
        self._session.add(WorkspaceRecord(id=workspace.id, source_baseline_id=workspace.source_baseline_id,
                                          source_git_commit=workspace.source_git_commit,
                                          change_request_id=workspace.change_request_id,
                                          git_ref=workspace.git_ref, state=workspace.state.value))
        await self._session.commit()
        return workspace

    async def get(self, workspace_id: UUID) -> Workspace | None:
        record = await self._session.get(WorkspaceRecord, workspace_id)
        return _to_workspace(record) if record else None

    async def update(self, workspace: Workspace) -> Workspace:
        record = await self._session.get(WorkspaceRecord, workspace.id)
        if record is None:
            raise ValueError(f"workspace '{workspace.id}' does not exist")
        if (
            record.source_baseline_id != workspace.source_baseline_id
            or record.source_git_commit != workspace.source_git_commit
            or record.change_request_id != workspace.change_request_id
            or record.git_ref != workspace.git_ref
        ):
            raise ValueError("workspace origin and Git reference are immutable")
        current = WorkspaceState(record.state)
        if current is not workspace.state:
            from engineering_gateway.domain.workspaces import WorkspaceGate
            WorkspaceGate.require_transition(current, workspace.state)
        record.state = workspace.state.value
        await self._session.commit()
        return workspace


def _to_baseline(record: BaselineRecord) -> Baseline:
    return Baseline(id=record.id, name=record.name, git_repository=record.git_repository, git_commit=record.git_commit,
                    git_tag=record.git_tag, external_versions=tuple(ExternalSystemVersion.model_validate(item) for item in record.external_versions))


def _to_change_request(record: ChangeRequestRecord) -> ChangeRequest:
    return ChangeRequest(id=record.id, external_system=record.external_system, external_id=record.external_id,
                         title=record.title, state=ChangeRequestState(record.state),
                         source_baseline_id=record.source_baseline_id, workspace_id=record.workspace_id)


def _to_workspace(record: WorkspaceRecord) -> Workspace:
    return Workspace(id=record.id, source_baseline_id=record.source_baseline_id,
                     source_git_commit=record.source_git_commit,
                     change_request_id=record.change_request_id, git_ref=record.git_ref,
                     state=WorkspaceState(record.state))


class SqlAlchemyAuditSink:
    """Append-only durable audit sink."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, event: AuditEvent) -> None:
        self._session.add(AuditEventRecord(id=event.id, timestamp=event.timestamp, actor_id=event.actor_id,
                                           actor_type=event.actor_type.value, authorization_level=event.authorization_level.value,
                                           action=event.action, target_type=event.target_type, target_id=event.target_id,
                                           correlation_id=event.correlation_id, result=event.result.value,
                                           reason=event.reason, metadata=event.metadata))
        await self._session.commit()
