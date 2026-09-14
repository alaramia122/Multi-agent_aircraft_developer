from uuid import uuid4

import pytest

from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.models import EngineeringElement, EngineeringGraph, EngineeringRelation, ElementKind, RelationType
from engineering_gateway.domain.reconciliation import WorkspaceReconciliationError, compute_change_set_hash
from engineering_gateway.domain.workspaces import Workspace
from engineering_gateway.infrastructure.workspace_reconciler import AdapterWorkspaceReconciler


class FakeCanonical:
    def __init__(self, elements):
        self.elements = elements

    async def get(self, element_id):
        return self.elements.get(element_id)

    async def save(self, element):
        return element

    async def add_relation(self, relation):
        return relation

    async def get_relations(self, element_id):
        return []

    async def list_graph(self):
        return EngineeringGraph(elements=list(self.elements.values()), relations=[])


class FakeAdapter:
    def __init__(self, system_name):
        self.system_name = system_name
        self.created = []
        self.elements = []
        self.relations = []

    async def get_element(self, external_id):
        return None

    async def get_version(self):
        return ExternalVersion(system=self.system_name, version="rev-1")

    async def create_workspace(self, workspace_id, source_version, change_set_hash):
        self.created.append((workspace_id, source_version, change_set_hash))

    async def apply_element(self, workspace_id, element):
        self.elements.append(element)

    async def apply_relation(self, workspace_id, relation):
        self.relations.append(relation)


@pytest.mark.asyncio
async def test_relation_to_unchanged_canonical_endpoint_is_routed_to_source_adapter():
    source = EngineeringElement(
        kind=ElementKind.ARCHITECTURE,
        type_id="component",
        name="Changed",
        external_system="capella",
        external_id="COMP-1",
    )
    target = EngineeringElement(
        kind=ElementKind.ARCHITECTURE,
        type_id="component",
        name="Existing",
        external_system="capella",
        external_id="COMP-2",
    )
    relation = EngineeringRelation(
        source_id=source.id,
        relation_type=RelationType.DEPENDS_ON,
        target_id=target.id,
    )
    adapter = FakeAdapter("capella")
    reconciler = AdapterWorkspaceReconciler((adapter,), FakeCanonical({target.id: target}))
    workspace = Workspace(
        source_baseline_id=uuid4(),
        source_git_commit="abc123",
        change_request_id=uuid4(),
    )
    changes = EngineeringGraph(elements=[source], relations=[relation])

    versions = await reconciler.reconcile(workspace, changes)

    assert versions == (ExternalVersion(system="capella", version="rev-1"),)
    assert adapter.elements == [source]
    assert adapter.relations == [relation]
    assert adapter.created == [(workspace.id, "abc123", compute_change_set_hash(changes))]


@pytest.mark.asyncio
async def test_same_change_set_produces_same_idempotency_key_on_retry():
    source = EngineeringElement(
        kind=ElementKind.ARCHITECTURE,
        type_id="component",
        name="Changed",
        external_system="capella",
        external_id="COMP-1",
    )
    changes = EngineeringGraph(elements=[source])
    adapter = FakeAdapter("capella")
    reconciler = AdapterWorkspaceReconciler((adapter,), FakeCanonical({}))
    workspace = Workspace(
        source_baseline_id=uuid4(),
        source_git_commit="abc123",
        change_request_id=uuid4(),
    )

    await reconciler.reconcile(workspace, changes)
    await reconciler.reconcile(workspace, changes)

    assert adapter.created[0][2] == adapter.created[1][2]
    assert adapter.created[0][0] == adapter.created[1][0] == workspace.id


@pytest.mark.asyncio
async def test_relation_with_unresolved_endpoint_is_rejected():
    source = EngineeringElement(
        kind=ElementKind.ARCHITECTURE,
        type_id="component",
        name="Changed",
        external_system="capella",
        external_id="COMP-1",
    )
    relation = EngineeringRelation(
        source_id=source.id,
        relation_type=RelationType.DEPENDS_ON,
        target_id=uuid4(),
    )
    reconciler = AdapterWorkspaceReconciler((FakeAdapter("capella"),), FakeCanonical({}))
    workspace = Workspace(
        source_baseline_id=uuid4(),
        source_git_commit="abc123",
        change_request_id=uuid4(),
    )

    with pytest.raises(WorkspaceReconciliationError, match="unknown endpoint"):
        await reconciler.reconcile(workspace, EngineeringGraph(elements=[source], relations=[relation]))


@pytest.mark.asyncio
async def test_adapter_without_workspace_operations_is_rejected_before_mutation():
    element = EngineeringElement(
        kind=ElementKind.REQUIREMENT,
        type_id="requirement",
        name="REQ-1",
        external_system="strictdoc",
        external_id="REQ-1",
    )
    read_only_adapter = type(
        "ReadOnlyAdapter",
        (),
        {"system_name": "strictdoc", "get_element": lambda self, external_id: None, "get_version": lambda self: None},
    )()
    reconciler = AdapterWorkspaceReconciler((read_only_adapter,), FakeCanonical({}))
    workspace = Workspace(
        source_baseline_id=uuid4(),
        source_git_commit="abc123",
        change_request_id=uuid4(),
    )

    with pytest.raises(WorkspaceReconciliationError, match="does not implement required operations"):
        await reconciler.reconcile(workspace, EngineeringGraph(elements=[element]))
