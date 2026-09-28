"""Durable, owner-scoped Alice transcript associated with a human project brief."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from engineering_gateway.infrastructure.db import Base, Database


class ProjectDialogueRecord(Base):
    __tablename__ = "project_dialogue"
    __table_args__ = (Index("ix_project_dialogue_project_created", "project_id", "created_at", "id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("project_drafts.id"), nullable=False)
    author_id: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    response_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def turn_data(record: ProjectDialogueRecord) -> dict[str, str]:
    return {"id": str(record.id), "role": record.role, "text": record.text,
            "created_at": record.created_at.replace(tzinfo=UTC).isoformat()}


class ProjectDialogueStore:
    def __init__(self, database: Database):
        self.database = database

    async def list_for(self, author_id: str, project_id: UUID) -> list[dict[str, str]]:
        async with self.database.session() as session:
            records = await session.scalars(select(ProjectDialogueRecord).where(
                ProjectDialogueRecord.author_id == author_id,
                ProjectDialogueRecord.project_id == project_id,
            ).order_by(ProjectDialogueRecord.created_at, ProjectDialogueRecord.id))
            return [turn_data(record) for record in records]

    async def append_exchange(self, author_id: str, project_id: UUID, message: str,
                              answer: str, response_id: str) -> None:
        timestamp = datetime.now(UTC)
        async with self.database.session() as session:
            session.add_all([
                ProjectDialogueRecord(id=uuid4(), project_id=project_id, author_id=author_id,
                                      role="user", text=message, created_at=timestamp),
                ProjectDialogueRecord(id=uuid4(), project_id=project_id, author_id=author_id,
                                      role="assistant", text=answer, response_id=response_id,
                                      created_at=timestamp + timedelta(microseconds=1)),
            ])
            await session.commit()
