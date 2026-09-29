"""Human-authored project briefs, before any engineering baseline exists."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from engineering_gateway.infrastructure.db import Base, Database
from engineering_gateway.infrastructure.metadata_models import WorkspaceRecord


class ProjectDraftRecord(Base):
    __tablename__ = "project_drafts"
    __table_args__ = (Index("ix_project_drafts_author_created", "author_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    author_id: Mapped[str] = mapped_column(String(512), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def project_data(record: ProjectDraftRecord) -> dict[str, object]:
    return {
        "id": str(record.id), "name": record.name, "goal": record.goal,
        "constraints": record.constraints, "author_id": record.author_id,
        "source": "human_input", "source_hash": record.source_hash,
        "version": record.version, "created_at": record.created_at.replace(tzinfo=UTC).isoformat(),
        "state": "draft", "baseline_id": None, "workspaces": [],
    }


async def with_workspaces(
    session: AsyncSession, records: list[ProjectDraftRecord],
) -> list[dict[str, object]]:
    """Attach only workspaces linked to drafts owned by the requested author."""
    if not records:
        return []
    workspaces = await session.scalars(
        select(WorkspaceRecord).where(
            WorkspaceRecord.project_draft_id.in_(record.id for record in records)
        ).order_by(WorkspaceRecord.id)
    )
    by_project: dict[UUID, list[dict[str, object]]] = {record.id: [] for record in records}
    for workspace in workspaces:
        if workspace.project_draft_id is not None:
            by_project[workspace.project_draft_id].append({
                "id": str(workspace.id), "state": workspace.state,
                "change_request_id": str(workspace.change_request_id),
                "source_git_commit": workspace.source_git_commit,
            })
    result = []
    for record in records:
        data = project_data(record)
        data["workspaces"] = by_project[record.id]
        result.append(data)
    return result


class ProjectDraftStore:
    def __init__(self, database: Database):
        self.database = database

    async def create(self, author_id: str, name: str, goal: str, constraints: str) -> dict[str, object]:
        content = {"name": name, "goal": goal, "constraints": constraints}
        digest = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True,
                                           separators=(",", ":")).encode()).hexdigest()
        record = ProjectDraftRecord(
            id=uuid4(), author_id=author_id, **content, source_hash=digest,
            version=1, created_at=datetime.now(UTC),
        )
        async with self.database.session() as session:
            session.add(record)
            await session.commit()
        return project_data(record)

    async def list_for(self, author_id: str) -> list[dict[str, object]]:
        async with self.database.session() as session:
            results = await session.scalars(
                select(ProjectDraftRecord).where(ProjectDraftRecord.author_id == author_id)
                .order_by(ProjectDraftRecord.created_at.desc(), ProjectDraftRecord.id.desc())
            )
            return await with_workspaces(session, list(results))

    async def get_for(self, author_id: str, project_id: UUID) -> dict[str, object] | None:
        async with self.database.session() as session:
            record = await session.get(ProjectDraftRecord, project_id)
            if record is None or record.author_id != author_id:
                return None
            return (await with_workspaces(session, [record]))[0]
