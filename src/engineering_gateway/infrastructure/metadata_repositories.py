"""Persistence implementations for Gateway metadata."""

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

    def __init__(self, session) -> None:
        self._session = session

    async def register(self, profile: StandardProfile) -> None:
        existing = await self._session.scalar(
            __import__("sqlalchemy").select(StandardProfileRecord).where(
                StandardProfileRecord.profile_id == profile.id,
                StandardProfileRecord.version == profile.version,
            )
        )
        if existing is not None:
            if existing.definition != profile.model_dump(mode="json"):
                raise ValueError(f"profile '{profile.id}@{profile.version}' already exists")
            return
        self._session.add(
            StandardProfileRecord(
                id=__import__("uuid").uuid4(),
                profile_id=profile.id,
                version=profile.version,
                name=profile.name,
                definition=profile.model_dump(mode="json"),
            )
        )
        await self._session.commit()


class SqlAlchemyBaselineRegistry:
    """Durable immutable baseline registry."""

    def __init__(self, session) -> None:
        self._session = session

    async def register(self, baseline: Baseline) -> Baseline:
        existing = await self._session.get(BaselineRecord, baseline.id)
        if existing is not None:
            if _baseline_payload(existing) != baseline.model_dump(mode="json"):
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


def _baseline_payload(record: BaselineRecord) -> dict:
    return {
        "id": record.id,
        "name": record.name,
        "git_repository": record.git_repository,
        "git_commit": record.git_commit,
        "git_tag": record.git_tag,
        "external_versions": record.external_versions,
    }


class SqlAlchemyAuditSink:
    """Append-only durable audit sink."""

    def __init__(self, session) -> None:
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
