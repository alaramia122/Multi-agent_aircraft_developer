"""Durable SQLAlchemy-backed registry for external tool descriptors."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from engineering_gateway.domain.audit import AuditEvent
from engineering_gateway.domain.tool_registry import (
    ToolDescriptor,
    ToolLifecycleState,
    ToolPermission,
    ToolTrustLevel,
)
from engineering_gateway.infrastructure.db import Database
from engineering_gateway.infrastructure.metadata_models import ToolRegistryRecord
from engineering_gateway.infrastructure.metadata_repositories import SqlAlchemyAuditSink


class SqlAlchemyToolRegistry:
    """Persist tool metadata in PostgreSQL; never stores executable code."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def register_persisted(self, tool: ToolDescriptor) -> ToolDescriptor:
        definition = tool.model_dump(mode="json")
        async with self._database.session_factory() as session:
            existing = await session.get(ToolRegistryRecord, tool.tool_id)
            if existing is not None:
                if self._to_descriptor(existing) != tool:
                    raise ValueError(f"tool '{tool.tool_id}' already exists with a different definition")
                return tool
            session.add(
                ToolRegistryRecord(
                    tool_id=tool.tool_id,
                    contract_version=tool.contract_version,
                    name=tool.name,
                    description=tool.description,
                    trust_level=tool.trust_level.value,
                    permissions=definition["permissions"],
                    project_scoped=tool.project_scoped,
                    enabled=tool.enabled,
                    lifecycle_state=tool.lifecycle_state.value,
                    configuration_schema=tool.configuration_schema,
                )
            )
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError(f"tool '{tool.tool_id}' was concurrently registered") from exc
        return tool

    async def transition_persisted(
        self, tool_id: str, expected_state: ToolLifecycleState, updated: ToolDescriptor
    ) -> ToolDescriptor:
        if updated.tool_id != tool_id:
            raise ValueError("tool lifecycle transition cannot change tool_id")
        async with self._database.session_factory() as session:
            record = await session.scalar(
                select(ToolRegistryRecord)
                .where(ToolRegistryRecord.tool_id == tool_id)
                .with_for_update()
            )
            if record is None:
                raise ValueError(f"tool '{tool_id}' was not found")
            if record.lifecycle_state != expected_state.value:
                raise ValueError(
                    f"tool '{tool_id}' lifecycle state changed: expected "
                    f"{expected_state.value}, found {record.lifecycle_state}"
                )
            definition = updated.model_dump(mode="json")
            record.contract_version = updated.contract_version
            record.name = updated.name
            record.description = updated.description
            record.trust_level = updated.trust_level.value
            record.permissions = definition["permissions"]
            record.project_scoped = updated.project_scoped
            record.enabled = updated.enabled
            record.lifecycle_state = updated.lifecycle_state.value
            record.configuration_schema = updated.configuration_schema
            await session.commit()
        return updated

    async def get_persisted(self, tool_id: str) -> ToolDescriptor | None:
        async with self._database.session_factory() as session:
            record = await session.get(ToolRegistryRecord, tool_id)
            return self._to_descriptor(record) if record is not None else None

    async def list_persisted(
        self, *, enabled_only: bool = False
    ) -> tuple[ToolDescriptor, ...]:
        async with self._database.session_factory() as session:
            statement = select(ToolRegistryRecord).order_by(ToolRegistryRecord.tool_id)
            if enabled_only:
                statement = statement.where(ToolRegistryRecord.enabled.is_(True))
            records = await session.scalars(statement)
            return tuple(self._to_descriptor(record) for record in records)

    async def list_available_persisted(
        self, *, minimum_trust: ToolTrustLevel, enabled_only: bool = True
    ) -> tuple[ToolDescriptor, ...]:
        levels = list(ToolTrustLevel)
        minimum_index = levels.index(minimum_trust)
        tools = await self.list_persisted(enabled_only=enabled_only)
        return tuple(
            tool for tool in tools
            if levels.index(tool.trust_level) >= minimum_index
        )

    @staticmethod
    def _to_descriptor(record: ToolRegistryRecord) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id=record.tool_id,
            contract_version=record.contract_version,
            name=record.name,
            description=record.description,
            trust_level=ToolTrustLevel(record.trust_level),
            permissions=tuple(ToolPermission.model_validate(item) for item in record.permissions),
            project_scoped=record.project_scoped,
            enabled=record.enabled,
            lifecycle_state=ToolLifecycleState(record.lifecycle_state),
            configuration_schema=record.configuration_schema,
        )


class SqlAlchemyToolAuditSink:
    """Write tool invocation audit events in independent durable transactions."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def record(self, event: AuditEvent) -> None:
        async with self._database.session_factory() as session:
            sink = SqlAlchemyAuditSink(session, autocommit=True)
            await sink.record(event)


__all__ = ["SqlAlchemyToolAuditSink", "SqlAlchemyToolRegistry"]
