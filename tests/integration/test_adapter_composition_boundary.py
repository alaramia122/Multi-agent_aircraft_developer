"""Integration-level contracts for external adapter composition."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engineering_gateway.infrastructure.adapter_composition import (
    AdapterCompositionError,
    ExternalAdapterSet,
)
from engineering_gateway.infrastructure.workspace_reconciler import AdapterWorkspaceReconciler


class _WorkspaceAdapter(SimpleNamespace):
    async def create_workspace(self, workspace_id, source_version, change_set_hash):
        return None

    async def apply_element(self, workspace_id, element):
        return None

    async def apply_relation(self, workspace_id, relation):
        return None

    async def get_element(self, external_id):
        return None

    async def get_version(self):
        return SimpleNamespace(system=self.system_name, version="test")


@pytest.mark.asyncio
async def test_composed_workspace_adapter_is_the_reconciler_mutation_boundary() -> None:
    capella = _WorkspaceAdapter(system_name="capella")
    adapters = ExternalAdapterSet(workspace_adapters=(capella,))

    reconciler = AdapterWorkspaceReconciler(adapters.as_workspace_adapters())

    assert adapters.as_read_adapters() == (capella,)
    assert reconciler._adapters == {"capella": capella}


def test_composition_does_not_allow_two_authoritative_capabilities_for_one_system() -> None:
    read = SimpleNamespace(system_name="strictdoc")
    workspace = _WorkspaceAdapter(system_name="strictdoc")

    with pytest.raises(AdapterCompositionError):
        ExternalAdapterSet(
            read_adapters=(read,),
            workspace_adapters=(workspace,),
        )
