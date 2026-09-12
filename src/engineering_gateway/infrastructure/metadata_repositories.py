"""Persistence implementations for Gateway metadata."""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engineering_gateway.domain.audit import AuditEvent
from engineering_gateway.domain.baselines import Baseline, ExternalSystemVersion
from engineering_gateway.domain.profiles import StandardProfile
from engineering_gateway.infrastructure.metadata_models import (
    AuditEventRecord,
    BaselineRecord,
    StandardProfileRecord,
)


class SqlAlchemyStandardProfileRegistry:
    """Durable Standard Profile registry with immutable version identities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def register(self, profile: StandardProfile) -> None:
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
            )
        )
        await self._session.commit()

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
        self._session.add(
            BaselineRecord(
                id=baseline.id,
                name=baseline.name,
                git_repository=baseline.git_repository,
                git_commit=baseline.git_commit,
                git_tag=baseline.git_tag,
                external_versions=[item.model_dump(mode="json") for item in baseline.external_versions],
            )
        )
        await self._session.commit()
        return baseline

    async def get(self, baseline_id: UUID) -> Baseline | None:
        record = await self._session.get(BaselineRecord, baseline_id)
        return _to_baseline(record) if record else None

    async def list(self) -> list[Baseline]:
        result = await self._session.scalars(select(BaselineRecord).order_by(BaselineRecord.id))
        return [_to_baseline(record) for record in result]


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


class SqlAlchemyAuditSink:
    """Append-only durable audit sink."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, event: AuditEvent) -> None:
        self._session.add(
            AuditEventRecord(
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
                metadata=event.metadata,
            )
        )
        await self._session.commit()
