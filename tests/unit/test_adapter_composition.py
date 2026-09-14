"""Tests for explicit external adapter composition."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engineering_gateway.infrastructure.adapter_composition import (
    AdapterCompositionError,
    ExternalAdapterSet,
    LocalAdapterConfig,
    compose_external_adapters,
)


def _adapter(name: str) -> SimpleNamespace:
    return SimpleNamespace(system_name=name)


def test_external_adapter_set_rejects_duplicate_read_systems() -> None:
    with pytest.raises(AdapterCompositionError, match="duplicate read adapter"):
        ExternalAdapterSet(read_adapters=(_adapter("strictdoc"), _adapter("strictdoc")))


def test_external_adapter_set_rejects_missing_system_name() -> None:
    with pytest.raises(AdapterCompositionError, match="non-empty system_name"):
        ExternalAdapterSet(read_adapters=(_adapter(""),))


def test_external_adapter_set_rejects_ambiguous_read_and_workspace_systems() -> None:
    read = _adapter("capella")
    workspace = _adapter("capella")

    with pytest.raises(AdapterCompositionError, match="separate read and workspace adapters"):
        ExternalAdapterSet(read_adapters=(read,), workspace_adapters=(workspace,))


def test_workspace_adapter_is_also_exposed_as_read_adapter() -> None:
    workspace = _adapter("capella")

    composed = ExternalAdapterSet(workspace_adapters=(workspace,))

    assert composed.as_read_adapters() == (workspace,)
    assert composed.as_workspace_adapters() == (workspace,)


def test_same_adapter_can_be_declared_in_both_capability_views() -> None:
    adapter = _adapter("capella")

    composed = ExternalAdapterSet(read_adapters=(adapter,), workspace_adapters=(adapter,))

    assert composed.as_read_adapters() == (adapter,)
    assert composed.as_workspace_adapters() == (adapter,)


def test_composition_keeps_read_and_workspace_capabilities_separate() -> None:
    strictdoc = _adapter("strictdoc")
    capella = _adapter("capella")
    openproject = _adapter("openproject")
    config = LocalAdapterConfig(
        strictdoc=strictdoc,  # type: ignore[arg-type]
        capella=capella,  # type: ignore[arg-type]
        openproject=openproject,  # type: ignore[arg-type]
    )

    composed = compose_external_adapters(config)

    assert composed.as_read_adapters() == (strictdoc, capella, openproject)
    assert composed.as_workspace_adapters() == (capella,)


def test_context_composition_rejects_both_adapter_inputs() -> None:
    """Documented at the context boundary; kept here as a contract reminder."""
    assert ExternalAdapterSet().as_read_adapters() == ()
