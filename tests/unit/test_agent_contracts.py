from uuid import uuid4

import pytest
from pydantic import ValidationError

from engineering_gateway.domain.agent_contracts import (
    AgentContextRef,
    AgentProposal,
    AgentRole,
    AgentTask,
    AgentTaskKind,
    AgentTaskState,
)


def test_agent_task_is_versioned_and_forbids_unknown_fields() -> None:
    task = AgentTask(
        task_id=uuid4(),
        role=AgentRole.REQUIREMENTS,
        kind=AgentTaskKind.PROPOSE,
        objective="Сформировать предложения по требованиям",
        context=AgentContextRef(workspace_id=uuid4()),
    )

    assert task.contract_version == "1.0"
    assert task.role is AgentRole.REQUIREMENTS

    with pytest.raises(ValidationError):
        AgentTask(
            task_id=uuid4(),
            role=AgentRole.REQUIREMENTS,
            kind=AgentTaskKind.PROPOSE,
            objective="x",
            context=AgentContextRef(),
            approve=True,
        )


def test_agent_task_rejects_wrong_contract_version() -> None:
    with pytest.raises(ValidationError):
        AgentTask(
            task_id=uuid4(),
            contract_version="2.0",
            role=AgentRole.SYSTEM_ARCHITECT,
            kind=AgentTaskKind.ANALYZE,
            objective="x",
            context=AgentContextRef(),
        )


def test_agent_proposal_has_no_approval_capability() -> None:
    proposal = AgentProposal(
        task_id=uuid4(),
        role=AgentRole.REVIEWER,
        state=AgentTaskState.COMPLETED,
        summary="Результат проверки",
    )

    assert "approve" not in proposal.model_fields
    assert proposal.state is AgentTaskState.COMPLETED

    with pytest.raises(ValidationError):
        AgentProposal(
            task_id=uuid4(),
            role=AgentRole.REVIEWER,
            state=AgentTaskState.COMPLETED,
            summary="x",
            approved=True,
        )
