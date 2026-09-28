"""Tests for adapter-set wiring in the Gateway composition root."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engineering_gateway.infrastructure.adapter_composition import ExternalAdapterSet
from engineering_gateway.infrastructure.gateway_context import governed_gateway_context


@pytest.mark.asyncio
async def test_governed_context_builds_reconciler_from_workspace_adapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The preferred adapter-set path wires workspace adapters into reconciliation."""
    import engineering_gateway.infrastructure.gateway_context as gateway_context_module

    session = object()
    captured: dict[str, object] = {}

    class FakeSessionContext:
        async def __aenter__(self) -> object:
            return session

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    class FakeDatabase:
        def session_factory(self) -> FakeSessionContext:
            return FakeSessionContext()

    workspace_adapter = SimpleNamespace(system_name="capella")
    adapter_set = ExternalAdapterSet(workspace_adapters=(workspace_adapter,))

    class FakeReconciler:
        def __init__(self, adapters, *, canonical, baselines) -> None:
            captured["adapters"] = adapters
            captured["canonical"] = canonical
            captured["baselines"] = baselines

    class FakeService:
        def __init__(self, **kwargs) -> None:
            captured["service_reconciler"] = kwargs["workspace_reconciler"]

    monkeypatch.setattr(gateway_context_module, "AdapterWorkspaceReconciler", FakeReconciler)
    monkeypatch.setattr(gateway_context_module, "GovernedGatewayApplicationService", FakeService)
    monkeypatch.setattr(
        gateway_context_module,
        "PostgresReconciliationCoordinator",
        lambda provided_session: ("coordinator", provided_session),
    )

    async with governed_gateway_context(FakeDatabase(), adapter_set=adapter_set):
        pass

    assert captured["adapters"] == (workspace_adapter,)
    assert captured["service_reconciler"].__class__ is FakeReconciler
    assert captured["canonical"] is not None
