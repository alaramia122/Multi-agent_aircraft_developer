"""SQLAlchemy models for Gateway-owned governance metadata."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from engineering_gateway.infrastructure.db import Base


class StandardProfileRecord(Base):
    __tablename__ = "standard_profiles"
    __table_args__ = (UniqueConstraint("profile_id", "version", name="uq_standard_profile_identity"), Index("ix_standard_profiles_profile_id", "profile_id"))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(1024), nullable=False)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class BaselineRecord(Base):
    __tablename__ = "baselines"
    __table_args__ = (Index("ix_baselines_git_repository", "git_repository"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(1024), nullable=False)
    git_repository: Mapped[str] = mapped_column(String(2048), nullable=False)
    git_commit: Mapped[str] = mapped_column(String(255), nullable=False)
    git_tag: Mapped[str | None] = mapped_column(String(255))
    external_versions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class ChangeRequestRecord(Base):
    __tablename__ = "change_requests"
    __table_args__ = (UniqueConstraint("external_system", "external_id", name="uq_change_request_external_identity"), Index("ix_change_requests_state", "state"))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    external_system: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    source_baseline_id: Mapped[UUID | None] = mapped_column(Uuid)
    workspace_id: Mapped[UUID | None] = mapped_column(Uuid)


class WorkspaceRecord(Base):
    __tablename__ = "workspaces"
    __table_args__ = (Index("ix_workspaces_source_baseline", "source_baseline_id"), Index("ix_workspaces_change_request", "change_request_id"), Index("ix_workspaces_state", "state"))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    source_baseline_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_git_commit: Mapped[str] = mapped_column(String(255), nullable=False)
    change_request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    git_ref: Mapped[str] = mapped_column(String(2048), nullable=False, default="HEAD")
    profile_id: Mapped[str | None] = mapped_column(String(255))
    profile_version: Mapped[str | None] = mapped_column(String(128))
    validation_graph_hash: Mapped[str | None] = mapped_column(String(64))
    validation_evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reconciled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reconciled_change_set_hash: Mapped[str | None] = mapped_column(String(64))
    reconciliation_external_versions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    state: Mapped[str] = mapped_column(String(64), nullable=False)


class AuditEventRecord(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_timestamp", "timestamp"), Index("ix_audit_events_correlation_id", "correlation_id"), Index("ix_audit_events_target", "target_type", "target_id"))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(512), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    authorization_level: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str] = mapped_column(String(255), nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(Uuid)
    correlation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
