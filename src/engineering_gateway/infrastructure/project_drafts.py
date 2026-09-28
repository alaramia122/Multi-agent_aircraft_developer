"""Human-authored project briefs, before any engineering baseline exists."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from engineering_gateway.infrastructure.db import Base, Database


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
        "state": "draft", "baseline_id": None,
    }


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
            return [project_data(record) for record in results]

    async def get_for(self, author_id: str, project_id: UUID) -> dict[str, object] | None:
        async with self.database.session() as session:
            record = await session.get(ProjectDraftRecord, project_id)
            return project_data(record) if record is not None and record.author_id == author_id else None
