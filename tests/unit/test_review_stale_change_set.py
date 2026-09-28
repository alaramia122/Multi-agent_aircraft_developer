"""A reviewer cannot endorse evidence for a changed external publication."""

from uuid import uuid4

import pytest

from engineering_gateway.application.gateway_service import Actor, GatewayServiceError
from engineering_gateway.application.governed_gateway_service import GovernedGatewayApplicationService
from engineering_gateway.domain.audit import ActorType
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.models import ElementKind, EngineeringElement, EngineeringGraph
from engineering_gateway.domain.workspaces import Workspace, WorkspaceState


@pytest.mark.asyncio
async def test_review_rejects_changed_set_after_reconciliation():
    workspace_id = uuid4()
    workspace = Workspace(
        id=workspace_id, source_baseline_id=uuid4(), source_git_commit="source",
        change_request_id=uuid4(), state=WorkspaceState.READY_FOR_APPROVAL,
        validation_graph_hash="a" * 64, reconciled=True,
        reconciled_change_set_hash="b" * 64,
        validation_evidence={"prepared_by_actor_id": "preparer"},
    )

    class Workspaces:
        async def get(self, _workspace_id):
            return workspace

    class Changes:
        async def get_changes(self, _workspace_id):
            return EngineeringGraph(elements=[EngineeringElement(
                kind=ElementKind.REQUIREMENT, type_id="system_requirement", name="Changed",
                external_system="strictdoc", external_id="REQ-1",
            )])

    service = object.__new__(GovernedGatewayApplicationService)
    service._uow = None
    service._workspaces = Workspaces()
    service._workspace_changes = Changes()
    service._review_reader = object()
    actor = Actor("reviewer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    with pytest.raises(GatewayServiceError, match="stale for the current change-set"):
        await service.record_independent_review(
            actor, workspace_id, accepted=True, reason="checked", evidence_uri="git:review",
        )
