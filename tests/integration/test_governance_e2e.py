"""End-to-end governance flow from change request to immutable baseline."""

from __future__ import annotations

import os
import subprocess
from uuid import UUID, uuid4

import pytest

from engineering_gateway.application.gateway_service import Actor, GatewayServiceError
from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.audit import ActorType
from engineering_gateway.domain.baselines import Baseline
from engineering_gateway.domain.budget import BudgetGate, BudgetLine, BudgetPlan
from engineering_gateway.domain.change_control import (
    AuthorizationLevel,
    ChangeRequest,
    ChangeRequestState,
)
from engineering_gateway.domain.models import ElementKind, EngineeringElement, EngineeringRelation
from engineering_gateway.domain.profiles import ElementTypeDefinition, StandardProfile
from engineering_gateway.domain.workspaces import WorkspaceState
from engineering_gateway.infrastructure.adapter_composition import ExternalAdapterSet
from engineering_gateway.infrastructure.db import Database
from engineering_gateway.infrastructure.gateway_context import governed_gateway_context
from engineering_gateway.infrastructure.git_adapter import LocalGitAdapter
from engineering_gateway.infrastructure.metadata_repositories import (
    SqlAlchemyBaselineRegistry,
    SqlAlchemyChangeRequestRepository,
    SqlAlchemyStandardProfileRegistry,
)


POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL is required for PostgreSQL integration tests",
)


class FakeWorkspaceAdapter:
    """Deterministic authoritative adapter for the governance E2E boundary."""

    system_name = "integration"

    def __init__(self) -> None:
        self.operations: list[str] = []

    async def get_element(self, external_id: str) -> EngineeringElement | None:
        return None

    async def get_version(self) -> ExternalVersion:
        self.operations.append("get_version")
        return ExternalVersion(system=self.system_name, version="integration-rev-1")

    async def create_workspace(
        self, workspace_id: UUID, source_version: str, change_set_hash: str
    ) -> None:
        self.operations.append("create_workspace")

    async def apply_element(self, workspace_id: UUID, element: EngineeringElement) -> None:
        self.operations.append("apply_element")

    async def apply_relation(self, workspace_id: UUID, relation: EngineeringRelation) -> None:
        self.operations.append("apply_relation")


def _git_commit(repository) -> str:
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(repository)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.email", "integration@example.test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.name", "Integration Test"],
        check=True,
    )
    (repository / "README.md").write_text("integration baseline\\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-m", "initial baseline"],
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.mark.asyncio
async def test_change_request_workspace_validation_reconciliation_and_approval_e2e(tmp_path):
    repository = tmp_path / "engineering.git"
    source_commit = _git_commit(repository)
    database = Database(POSTGRES_TEST_URL)
    profile = StandardProfile(
        id="integration-governance",
        version="1.0.0",
        name="Integration governance profile",
        element_types=[
            ElementTypeDefinition(id="system_requirement", kind=ElementKind.REQUIREMENT),
        ],
    )
    change_request_id = uuid4()
    baseline_id = uuid4()
    adapter = FakeWorkspaceAdapter()

    try:
        async with database.session_factory() as session:
            await SqlAlchemyStandardProfileRegistry(session).register(profile)
            await SqlAlchemyStandardProfileRegistry(session).activate(profile.id, profile.version)
            await SqlAlchemyBaselineRegistry(session).register(
                Baseline(
                    id=baseline_id,
                    name="source-baseline",
                    git_repository=str(repository),
                    git_commit=source_commit,
                )
            )
            await SqlAlchemyChangeRequestRepository(session).create(
                ChangeRequest(
                    id=change_request_id,
                    external_system="openproject",
                    external_id="CR-E2E-1",
                    title="Governance E2E change",
                    state=ChangeRequestState.OPEN,
                    source_baseline_id=baseline_id,
                )
            )

        async with governed_gateway_context(
            database,
            git=LocalGitAdapter(),
            budget_gate=BudgetGate(10_000_000),
            require_independent_review=True,
            adapter_set=ExternalAdapterSet(
                read_adapters=(adapter,), workspace_adapters=(adapter,)
            ),
        ) as service:
            l2 = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
            ai = Actor("agent", ActorType.AI, AuthorizationLevel.L3_APPROVE)
            approver = Actor("approver", ActorType.HUMAN, AuthorizationLevel.L3_APPROVE)

            workspace = await service.create_workspace(l2, baseline_id, change_request_id)
            element = EngineeringElement(
                kind=ElementKind.REQUIREMENT,
                type_id="system_requirement",
                name="Flight control requirement",
                external_system="integration",
                external_id="REQ-E2E-1",
            )
            await service.save_workspace_element(l2, element, workspace.id)

            with pytest.raises(GatewayServiceError, match="budget plan"):
                await service.prepare_for_approval(
                    l2, workspace.id, profile_id=profile.id, profile_version=profile.version
                )

            too_expensive = BudgetPlan(lines=(BudgetLine(
                id="hardware", description="Avionics hardware", quantity=1,
                unit_cost_kopeks=10_000_001, source_uri="git:cost-estimate",
            ),))
            with pytest.raises(GatewayServiceError, match="exceeds limit"):
                await service.prepare_for_approval(
                    l2, workspace.id, profile_id=profile.id,
                    profile_version=profile.version, budget_plan=too_expensive,
                )

            budget = BudgetPlan(lines=(BudgetLine(
                id="hardware", description="Avionics hardware", quantity=1,
                unit_cost_kopeks=9_000_000, source_uri="git:cost-estimate",
            ),), contingency_kopeks=1_000_000)

            prepared = await service.prepare_for_approval(
                l2, workspace.id, profile_id=profile.id, profile_version=profile.version,
                budget_plan=budget,
            )
            assert prepared.valid

            with pytest.raises(GatewayServiceError, match="L3|human"):
                await service.approve_workspace(ai, workspace.id)

            reconciliation = await service.reconcile_workspace(l2, workspace.id)
            assert reconciliation.external_versions == (
                ExternalVersion(system="integration", version="integration-rev-1"),
            )
            assert adapter.operations == ["create_workspace", "apply_element", "get_version"]

            with pytest.raises(GatewayServiceError, match="independent review"):
                await service.approve_workspace(approver, workspace.id)
            reviewer = Actor("reviewer-agent", ActorType.AI, AuthorizationLevel.L1_PROPOSE)
            with pytest.raises(GatewayServiceError, match="independent of the preparer"):
                await service.record_independent_review(
                    l2, workspace.id, accepted=True,
                    reason="self review", evidence_uri="git:review-1",
                )
            await service.record_independent_review(
                reviewer, workspace.id, accepted=False,
                reason="unresolved verification gap", evidence_uri="git:review-2",
            )
            with pytest.raises(GatewayServiceError, match="independent review"):
                await service.approve_workspace(approver, workspace.id)
            await service.record_independent_review(
                reviewer, workspace.id, accepted=True,
                reason="gap closed; evidence checked", evidence_uri="git:review-3",
            )

            baseline = await service.approve_workspace(approver, workspace.id)
            assert baseline.git_commit == source_commit
            assert baseline.git_tag == f"baseline-{workspace.id}"
            assert baseline.external_versions[0].version == "integration-rev-1"

            stored_workspace = await service._workspaces.get(workspace.id)
            assert stored_workspace is not None
            assert stored_workspace.state is WorkspaceState.APPROVED

            with pytest.raises(GatewayServiceError, match="not active"):
                await service.save_workspace_element(l2, element, workspace.id)

            with pytest.raises(ValueError, match="immutable"):
                await service._baselines.register(
                    baseline.model_copy(update={"git_commit": "different-commit"})
                )
    finally:
        await database.dispose()


__all__ = ["test_change_request_workspace_validation_reconciliation_and_approval_e2e"]
