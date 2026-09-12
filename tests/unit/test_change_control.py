from uuid import uuid4

import pytest

from engineering_gateway.domain.change_control import (
    AuthorizationLevel,
    ChangeGate,
    ChangeGateError,
    ChangeRequest,
    ChangeRequestState,
)


def test_l2_can_modify_existing_workspace() -> None:
    ChangeGate.require_workspace_modification(AuthorizationLevel.L2_MODIFY_WORKSPACE, uuid4())


def test_l1_cannot_modify_workspace() -> None:
    with pytest.raises(ChangeGateError):
        ChangeGate.require_workspace_modification(AuthorizationLevel.L1_PROPOSE, uuid4())


def test_modification_requires_workspace() -> None:
    with pytest.raises(ChangeGateError, match="active workspace"):
        ChangeGate.require_workspace_modification(AuthorizationLevel.L2_MODIFY_WORKSPACE, None)


def test_ai_cannot_approve_even_at_l3() -> None:
    with pytest.raises(ChangeGateError, match="human L3"):
        ChangeGate.require_approval(AuthorizationLevel.L3_APPROVE, actor_is_ai=True)


def test_non_l3_cannot_approve() -> None:
    with pytest.raises(ChangeGateError):
        ChangeGate.require_approval(AuthorizationLevel.L2_MODIFY_WORKSPACE)


def test_human_l3_can_approve() -> None:
    ChangeGate.require_approval(AuthorizationLevel.L3_APPROVE)


def test_baseline_change_requires_workspace_from_same_baseline() -> None:
    baseline = uuid4()
    workspace = uuid4()
    ChangeGate.require_new_workspace_for_baseline_change(baseline, workspace, baseline)

    with pytest.raises(ChangeGateError):
        ChangeGate.require_new_workspace_for_baseline_change(baseline, None, baseline)

    with pytest.raises(ChangeGateError):
        ChangeGate.require_new_workspace_for_baseline_change(baseline, workspace, uuid4())


def test_change_request_defaults_to_open() -> None:
    request = ChangeRequest(
        external_system="openproject",
        external_id="CR-1",
        title="Update requirement",
    )

    assert request.state == ChangeRequestState.OPEN
