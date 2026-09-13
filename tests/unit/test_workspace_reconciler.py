from uuid import uuid4

import pytest

from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.models import EngineeringElement, EngineeringGraph, EngineeringRelation, ElementKind, RelationType
from engineering_gateway.domain.reconciliation import WorkspaceReconciliationError
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

    async def create_workspace(self, workspace_id, source_version):
        self.created.append((workspace_id, source_version))

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

    versions = await reconciler.reconcile(workspace, EngineeringGraph(elements=[source], relations=[relation]))

    assert versions == (ExternalVersion(system="capella", version="rev-1"),)
    assert adapter.elements == [source]
    assert adapter.relations == [relation]
    assert adapter.created == [(workspace.id, "abc123")]


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
