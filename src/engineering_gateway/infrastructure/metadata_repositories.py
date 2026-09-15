"""Persistence implementations for Gateway metadata."""

from collections.abc import Callable
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from engineering_gateway.application.profile_engine import StandardProfileEngine
from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.audit import AuditEvent, AuditResult
from engineering_gateway.domain.baselines import Baseline, ExternalSystemVersion
from engineering_gateway.domain.change_control import ChangeGate, ChangeRequest, ChangeRequestState
from engineering_gateway.domain.profiles import StandardProfile
from engineering_gateway.domain.workspaces import Workspace, WorkspaceGate, WorkspaceState
from engineering_gateway.infrastructure.metadata_models import (
    AuditEventRecord,
    BaselineRecord,
    ChangeRequestRecord,
    StandardProfileRecord,
    WorkspaceRecord,
)


class _TransactionAware:
    def __init__(self, session: AsyncSession, *, autocommit: bool = True) -> None:
        self._session = session
        self._autocommit = autocommit

    async def _persist(self) -> None:
        if self._autocommit:
            await self._session.commit()
        else:
            await self._session.flush()


class SqlAlchemyStandardProfileRegistry(_TransactionAware):
    def __init__(self, session: AsyncSession, *, autocommit: bool = True) -> None:
        super().__init__(session, autocommit=autocommit)

    async def register(self, profile: StandardProfile) -> None:
        StandardProfileEngine.validate_profile(profile)
        existing = await self._session.scalar(
            select(StandardProfileRecord).where(
                StandardProfileRecord.profile_id == profile.id,
                StandardProfileRecord.version == profile.version,
            )
        )
        definition = profile.model_dump(mode="json")
        if existing is not None:
            if existing.definition != definition:
                raise ValueError(f"profile '{profile.id}@{profile.version}' already exists")
            return
        self._session.add(
            StandardProfileRecord(
                id=uuid4(),
                profile_id=profile.id,
                version=profile.version,
                name=profile.name,
                definition=definition,
                active=False,
            )
        )
        await self._persist()

    async def activate(self, profile_id: str, version: str) -> StandardProfile:
        record = await self._session.scalar(
            select(StandardProfileRecord).where(
                StandardProfileRecord.profile_id == profile_id,
                StandardProfileRecord.version == version,
            )
        )
        if record is None:
            raise ValueError(f"profile '{profile_id}@{version}' was not found")
        profile = StandardProfile.model_validate(record.definition)
        StandardProfileEngine.validate_profile(profile)
        record.active = True
        await self._persist()
        return profile

    async def deactivate(self, profile_id: str, version: str) -> None:
        record = await self._session.scalar(
            select(StandardProfileRecord).where(
                StandardProfileRecord.profile_id == profile_id,
                StandardProfileRecord.version == version,
            )
        )
        if record is None:
            raise ValueError(f"profile '{profile_id}@{version}' was not found")
        record.active = False
        await self._persist()

    async def is_active(self, profile_id: str, version: str) -> bool:
        record = await self._session.scalar(
            select(StandardProfileRecord).where(
                StandardProfileRecord.profile_id == profile_id,
                StandardProfileRecord.version == version,
            )
        )
        return bool(record and record.active)

    async def get_active(self) -> list[StandardProfile]:
        result = await self._session.scalars(
            select(StandardProfileRecord)
            .where(StandardProfileRecord.active.is_(True))
            .order_by(StandardProfileRecord.profile_id, StandardProfileRecord.version)
        )
        return [StandardProfile.model_validate(record.definition) for record in result]

    async def get(self, profile_id: str, version: str) -> StandardProfile | None:
        record = await self._session.scalar(
            select(StandardProfileRecord).where(
                StandardProfileRecord.profile_id == profile_id,
                StandardProfileRecord.version == version,
            )
        )
        return StandardProfile.model_validate(record.definition) if record else None

    async def list(self) -> list[StandardProfile]:
        result = await self._session.scalars(
            select(StandardProfileRecord).order_by(
                StandardProfileRecord.profile_id, StandardProfileRecord.version
            )
        )
        return [StandardProfile.model_validate(record.definition) for record in result]


class SqlAlchemyBaselineRegistry(_TransactionAware):
    def __init__(self, session: AsyncSession, *, autocommit: bool = True) -> None:
        super().__init__(session, autocommit=autocommit)

    async def register(self, baseline: Baseline) -> Baseline:
        existing = await self._session.get(BaselineRecord, baseline.id)
        if existing is not None:
            stored = _to_baseline(existing)
            if stored != baseline:
                raise ValueError(f"baseline '{baseline.id}' already exists and is immutable")
            return baseline
        self._session.add(
            BaselineRecord(
                id=baseline.id,
                name=baseline.name,
                git_repository=baseline.git_repository,
                git_commit=baseline.git_commit,
                git_tag=baseline.git_tag,
                external_versions=[
                    item.model_dump(mode="json") for item in baseline.external_versions
                ],
            )
        )
        await self._persist()
        return baseline

    async def get(self, baseline_id: UUID) -> Baseline | None:
        record = await self._session.get(BaselineRecord, baseline_id)
        return _to_baseline(record) if record else None

    async def list(self) -> list[Baseline]:
        result = await self._session.scalars(select(BaselineRecord).order_by(BaselineRecord.id))
        return [_to_baseline(record) for record in result]


class SqlAlchemyChangeRequestRepository(_TransactionAware):
    def __init__(self, session: AsyncSession, *, autocommit: bool = True) -> None:
        super().__init__(session, autocommit=autocommit)

    async def create(self, change_request: ChangeRequest) -> ChangeRequest:
        if await self.get(change_request.id) is not None:
            raise ValueError(f"change request '{change_request.id}' already exists")
        self._session.add(
            ChangeRequestRecord(
                id=change_request.id,
                external_system=change_request.external_system,
                external_id=change_request.external_id,
                title=change_request.title,
                state=change_request.state.value,
                source_baseline_id=change_request.source_baseline_id,
                workspace_id=change_request.workspace_id,
            )
        )
        await self._persist()
        return change_request

    async def get(self, change_request_id: UUID) -> ChangeRequest | None:
        record = await self._session.get(ChangeRequestRecord, change_request_id)
        return _to_change_request(record) if record else None

    async def update(self, change_request: ChangeRequest) -> ChangeRequest:
        record = await self._session.get(ChangeRequestRecord, change_request.id)
        if record is None:
            raise ValueError(f"change request '{change_request.id}' does not exist")
        current_state = ChangeRequestState(record.state)
        if current_state is not change_request.state:
            ChangeGate.require_transition(current_state, change_request.state)
        record.state = change_request.state.value
        record.source_baseline_id = change_request.source_baseline_id
        record.workspace_id = change_request.workspace_id
        await self._persist()
        return change_request


class SqlAlchemyWorkspaceRegistry(_TransactionAware):
    def __init__(self, session: AsyncSession, *, autocommit: bool = True) -> None:
        super().__init__(session, autocommit=autocommit)

    async def create(self, workspace: Workspace) -> Workspace:
        if await self.get(workspace.id) is not None:
            raise ValueError(f"workspace '{workspace.id}' already exists")
        self._session.add(
            WorkspaceRecord(
                id=workspace.id,
                version=workspace.version,
                source_baseline_id=workspace.source_baseline_id,
                source_git_commit=workspace.source_git_commit,
                change_request_id=workspace.change_request_id,
                git_ref=workspace.git_ref,
                profile_id=workspace.profile_id,
                profile_version=workspace.profile_version,
                validation_graph_hash=workspace.validation_graph_hash,
                validation_evidence=workspace.validation_evidence,
                reconciled=workspace.reconciled,
                reconciled_change_set_hash=workspace.reconciled_change_set_hash,
                reconciliation_external_versions=[
                    item.model_dump(mode="json")
                    for item in workspace.reconciliation_external_versions
                ],
                state=workspace.state.value,
            )
        )
        await self._persist()
        return workspace

    async def get(self, workspace_id: UUID) -> Workspace | None:
        record = await self._session.get(WorkspaceRecord, workspace_id)
        return _to_workspace(record) if record else None

    async def update(self, workspace: Workspace) -> Workspace:
        record = await self._session.get(WorkspaceRecord, workspace.id)
        if record is None:
            raise ValueError(f"workspace '{workspace.id}' does not exist")
        if record.version != workspace.version:
            raise ValueError(
                f"workspace '{workspace.id}' was modified concurrently; reload before updating"
            )
        if (
            record.source_baseline_id != workspace.source_baseline_id
            or record.source_git_commit != workspace.source_git_commit
            or record.change_request_id != workspace.change_request_id
            or record.git_ref != workspace.git_ref
        ):
            raise ValueError("workspace origin and Git reference are immutable")
        if record.profile_id is not None and record.profile_id != workspace.profile_id:
            raise ValueError("workspace validation profile is immutable once bound")
        if (
            record.profile_version is not None
            and record.profile_version != workspace.profile_version
        ):
            raise ValueError("workspace validation profile is immutable once bound")
        current_state = WorkspaceState(record.state)
        resetting_validation = (
            record.validation_graph_hash is not None
            and workspace.validation_graph_hash is None
            and not workspace.validation_evidence
            and workspace.state is WorkspaceState.ACTIVE
        )
        if (
            record.validation_graph_hash is not None
            and record.validation_graph_hash != workspace.validation_graph_hash
            and not resetting_validation
        ):
            raise ValueError("validation evidence is immutable once bound outside active reset")
        if record.validation_evidence != workspace.validation_evidence and not resetting_validation:
            raise ValueError("validation evidence is immutable once bound outside active reset")
        if (
            record.reconciled
            and not workspace.reconciled
            and current_state is not WorkspaceState.ACTIVE
        ) and workspace.state is not WorkspaceState.ACTIVE:
            raise ValueError(
                "workspace reconciliation evidence is immutable outside active engineering"
            )
        if (
            record.reconciled
            and workspace.reconciled
            and (
                record.reconciled_change_set_hash != workspace.reconciled_change_set_hash
                or record.reconciliation_external_versions
                != [
                    item.model_dump(mode="json")
                    for item in workspace.reconciliation_external_versions
                ]
            )
        ):
            raise ValueError(
                "reconciliation evidence cannot be replaced without returning to active engineering"
            )
        if not workspace.reconciled and (
            workspace.reconciled_change_set_hash is not None
            or workspace.reconciliation_external_versions
        ):
            raise ValueError("reconciliation evidence must be cleared together")
        if current_state is not workspace.state:
            WorkspaceGate.require_transition(current_state, workspace.state)

        result = await self._session.execute(
            update(WorkspaceRecord)
            .where(
                WorkspaceRecord.id == workspace.id,
                WorkspaceRecord.version == workspace.version,
            )
            .values(
                profile_id=workspace.profile_id,
                profile_version=workspace.profile_version,
                validation_graph_hash=workspace.validation_graph_hash,
                validation_evidence=workspace.validation_evidence,
                reconciled=workspace.reconciled,
                reconciled_change_set_hash=workspace.reconciled_change_set_hash,
                reconciliation_external_versions=[
                    item.model_dump(mode="json")
                    for item in workspace.reconciliation_external_versions
                ],
                state=workspace.state.value,
                version=WorkspaceRecord.version + 1,
            )
        )
        if result.rowcount != 1:
            raise ValueError(
                f"workspace '{workspace.id}' was modified concurrently; reload before updating"
            )
        await self._persist()
        return workspace.model_copy(update={"version": workspace.version + 1})


def _to_baseline(record: BaselineRecord) -> Baseline:
    return Baseline(
        id=record.id,
        name=record.name,
        git_repository=record.git_repository,
        git_commit=record.git_commit,
        git_tag=record.git_tag,
        external_versions=tuple(
            ExternalSystemVersion.model_validate(item) for item in record.external_versions
        ),
    )


def _to_change_request(record: ChangeRequestRecord) -> ChangeRequest:
    return ChangeRequest(
        id=record.id,
        external_system=record.external_system,
        external_id=record.external_id,
        title=record.title,
        state=ChangeRequestState(record.state),
        source_baseline_id=record.source_baseline_id,
        workspace_id=record.workspace_id,
    )


def _to_workspace(record: WorkspaceRecord) -> Workspace:
    return Workspace(
        id=record.id,
        version=record.version,
        source_baseline_id=record.source_baseline_id,
        source_git_commit=record.source_git_commit,
        change_request_id=record.change_request_id,
        git_ref=record.git_ref,
        profile_id=record.profile_id,
        profile_version=record.profile_version,
        validation_graph_hash=record.validation_graph_hash,
        validation_evidence=record.validation_evidence or {},
        reconciled=record.reconciled,
        reconciled_change_set_hash=record.reconciled_change_set_hash,
        reconciliation_external_versions=tuple(
            ExternalVersion.model_validate(item)
            for item in (record.reconciliation_external_versions or [])
        ),
        state=WorkspaceState(record.state),
    )


class SqlAlchemyAuditSink(_TransactionAware):
    def __init__(
        self,
        session: AsyncSession,
        *,
        autocommit: bool = True,
        independent_session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        super().__init__(session, autocommit=autocommit)
        self._independent_session_factory = independent_session_factory

    @staticmethod
    def _record_model(event: AuditEvent) -> AuditEventRecord:
        return AuditEventRecord(
            id=event.id,
            timestamp=event.timestamp,
            actor_id=event.actor_id,
            actor_type=event.actor_type.value,
            authorization_level=event.authorization_level.value,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            correlation_id=event.correlation_id,
            result=event.result.value,
            reason=event.reason,
            event_metadata=event.metadata,
        )

    async def record(self, event: AuditEvent) -> None:
        if (
            event.result in (AuditResult.FAILURE, AuditResult.DENIED)
            and self._independent_session_factory is not None
        ):
            session_context = self._independent_session_factory()
            async with session_context as independent_session:
                independent_session.add(self._record_model(event))
                await independent_session.commit()
            return
        self._session.add(self._record_model(event))
        await self._persist()
