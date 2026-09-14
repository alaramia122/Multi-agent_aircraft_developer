from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from engineering_gateway.domain.change_control import ChangeRequest, ChangeRequestState
from engineering_gateway.domain.workspaces import Workspace, WorkspaceState
from engineering_gateway.infrastructure.db import Base
from engineering_gateway.infrastructure.metadata_repositories import (
    SqlAlchemyChangeRequestRepository,
    SqlAlchemyWorkspaceRegistry,
)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


@pytest.mark.asyncio
async def test_change_request_repository_rejects_invalid_transition(session) -> None:
    repository = SqlAlchemyChangeRequestRepository(session)
    change_request = ChangeRequest(
        external_system="openproject",
        external_id="CR-1",
        title="Controlled change",
    )
    await repository.create(change_request)

    with pytest.raises(ValueError, match="invalid change-request transition"):
        await repository.update(change_request.model_copy(update={"state": ChangeRequestState.APPROVED}))


@pytest.mark.asyncio
async def test_change_request_repository_allows_governed_transition(session) -> None:
    repository = SqlAlchemyChangeRequestRepository(session)
    change_request = ChangeRequest(
        external_system="openproject",
        external_id="CR-2",
        title="Controlled change",
    )
    await repository.create(change_request)

    updated = await repository.update(
        change_request.model_copy(update={"state": ChangeRequestState.IN_PROGRESS})
    )

    assert updated.state is ChangeRequestState.IN_PROGRESS
    assert (await repository.get(change_request.id)).state is ChangeRequestState.IN_PROGRESS


@pytest.mark.asyncio
async def test_workspace_repository_allows_validation_reset_on_rejection_path(session) -> None:
    repository = SqlAlchemyWorkspaceRegistry(session)
    workspace = Workspace(
        source_baseline_id=uuid4(),
        source_git_commit="abc123",
        change_request_id=uuid4(),
        validation_graph_hash="a" * 64,
        validation_evidence={"graph_hash": "a" * 64},
        state=WorkspaceState.ACTIVE,
    )
    await repository.create(workspace)

    ready = workspace.model_copy(update={"state": WorkspaceState.READY_FOR_APPROVAL})
    await repository.update(ready)
    reset = ready.model_copy(
        update={
            "state": WorkspaceState.ACTIVE,
            "validation_graph_hash": None,
            "validation_evidence": {},
        }
    )

    restored = await repository.update(reset)

    assert restored.state is WorkspaceState.ACTIVE
    assert restored.validation_graph_hash is None
    assert restored.validation_evidence == {}


@pytest.mark.asyncio
async def test_workspace_repository_rejects_validation_evidence_replacement(session) -> None:
    repository = SqlAlchemyWorkspaceRegistry(session)
    workspace = Workspace(
        source_baseline_id=uuid4(),
        source_git_commit="abc123",
        change_request_id=uuid4(),
        validation_graph_hash="a" * 64,
        validation_evidence={"graph_hash": "a" * 64},
        state=WorkspaceState.ACTIVE,
    )
    await repository.create(workspace)

    with pytest.raises(ValueError, match="validation evidence is immutable"):
        await repository.update(
            workspace.model_copy(
                update={
                    "validation_graph_hash": "b" * 64,
                    "validation_evidence": {"graph_hash": "b" * 64},
                }
            )
        )
