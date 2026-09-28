"""The transcript is durable and cannot be read through another owner account."""

from uuid import UUID

import pytest

from engineering_gateway.infrastructure.db import Base, Database
from engineering_gateway.infrastructure.project_dialogue import ProjectDialogueStore
from engineering_gateway.infrastructure.project_drafts import ProjectDraftStore


@pytest.mark.asyncio
async def test_project_dialogue_persists_and_is_owner_scoped() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    drafts = ProjectDraftStore(database)
    saved = await drafts.create("owner", "Проект", "Цель тестового проекта", "")
    project_id = UUID(str(saved["id"]))
    dialogue = ProjectDialogueStore(database)
    await dialogue.append_exchange("owner", project_id, "Первый вопрос", "Первый ответ", "res-1")
    await dialogue.append_exchange("owner", project_id, "Второй вопрос", "Второй ответ", "res-2")
    assert [turn["text"] for turn in await ProjectDialogueStore(database).list_for("owner", project_id)] == [
        "Первый вопрос", "Первый ответ", "Второй вопрос", "Второй ответ",
    ]
    assert await dialogue.list_for("other", project_id) == []
    await database.dispose()
