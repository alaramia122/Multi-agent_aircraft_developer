from uuid import UUID, uuid4

import pytest

from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.models import ElementKind, EngineeringElement, EngineeringGraph
from engineering_gateway.domain.reconciliation import compute_change_set_hash
from engineering_gateway.domain.workspaces import Workspace
from engineering_gateway.infrastructure.workspace_reconciler import AdapterWorkspaceReconciler


class IdempotentAdapter:
    """Test double implementing the workspace adapter idempotency contract."""

    def __init__(
        self,
        system_name: str,
        fail_first_element: bool = False,
        fail_first_version: bool = False,
    ) -> None:
        self.system_name = system_name
        self.fail_first_element = fail_first_element
        self.fail_first_version = fail_first_version
        self.operations: list[str] = []
        self._published: set[tuple[UUID, str]] = set()
        self._elements: set[tuple[UUID, UUID]] = set()

    async def get_element(self, external_id: str) -> EngineeringElement | None:
        return None

    async def get_version(self) -> ExternalVersion:
        if self.fail_first_version:
            self.fail_first_version = False
            raise RuntimeError(f"{self.system_name} version lookup failed")
        self.operations.append("get_version")
        return ExternalVersion(system=self.system_name, version=f"{self.system_name}-rev-1")

    async def create_workspace(
        self, workspace_id: UUID, source_version: str, change_set_hash: str
    ) -> None:
        key = (workspace_id, change_set_hash)
        if key in self._published:
            return
        self._published.add(key)
        self.operations.append("create_workspace")

    async def apply_element(self, workspace_id: UUID, element: EngineeringElement) -> None:
        key = (workspace_id, element.id)
        if key in self._elements:
            return
        if self.fail_first_element:
            self.fail_first_element = False
            raise RuntimeError(f"{self.system_name} publication failed")
        self._elements.add(key)
        self.operations.append("apply_element")

    async def apply_relation(self, workspace_id: UUID, relation) -> None:
        self.operations.append("apply_relation")


def _workspace() -> Workspace:
    return Workspace(
        source_baseline_id=uuid4(),
        source_git_commit="abc123",
        change_request_id=uuid4(),
    )


def _element(system: str, element_id: str) -> EngineeringElement:
    return EngineeringElement(
        id=UUID(element_id),
        kind=ElementKind.ARCHITECTURE,
        type_id="component",
        name="FlightControl",
        external_system=system,
        external_id="COMP-1",
    )


def _changes() -> EngineeringGraph:
    return EngineeringGraph(
        elements=[
            _element("capella", "00000000-0000-0000-0000-000000000001"),
            _element("strictdoc", "00000000-0000-0000-0000-000000000002"),
        ]
    )


@pytest.mark.asyncio
async def test_partial_external_failure_can_be_retried_without_duplicate_publication():
    workspace = _workspace()
    capella = IdempotentAdapter("capella")
    strictdoc = IdempotentAdapter("strictdoc", fail_first_element=True)
    reconciler = AdapterWorkspaceReconciler((capella, strictdoc))
    changes = _changes()
    change_set_hash = compute_change_set_hash(changes)

    with pytest.raises(RuntimeError, match="strictdoc publication failed"):
        await reconciler.reconcile(workspace, changes)

    result = await reconciler.reconcile(workspace, changes)

    assert result == (
        ExternalVersion(system="capella", version="capella-rev-1"),
        ExternalVersion(system="strictdoc", version="strictdoc-rev-1"),
    )
    assert capella.operations == ["create_workspace", "apply_element", "get_version"]
    assert strictdoc.operations == ["create_workspace", "apply_element", "get_version"]
    assert (workspace.id, change_set_hash) in capella._published
    assert (workspace.id, change_set_hash) in strictdoc._published


@pytest.mark.asyncio
async def test_retry_after_version_lookup_failure_does_not_republish_external_changes():
    workspace = _workspace()
    capella = IdempotentAdapter("capella", fail_first_version=True)
    reconciler = AdapterWorkspaceReconciler((capella,))
    changes = EngineeringGraph(
        elements=[_element("capella", "00000000-0000-0000-0000-000000000001")]
    )

    with pytest.raises(RuntimeError, match="version lookup failed"):
        await reconciler.reconcile(workspace, changes)

    result = await reconciler.reconcile(workspace, changes)

    assert result == (ExternalVersion(system="capella", version="capella-rev-1"),)
    assert capella.operations == ["create_workspace", "apply_element", "get_version"]
