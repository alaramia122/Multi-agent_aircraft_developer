"""Composition primitives for the Gateway's external-system adapters.

The composition layer owns wiring and uniqueness checks only. Governance remains in
application services, while adapter implementations remain responsible for their
native integration protocols.
"""

from __future__ import annotations

from dataclasses import dataclass

from engineering_gateway.domain.adapters import GitAdapter, ReadAdapter, WorkspaceAdapter
from engineering_gateway.infrastructure.capella_adapter import LocalCapellaAdapter
from engineering_gateway.infrastructure.git_adapter import LocalGitAdapter
from engineering_gateway.infrastructure.openproject_adapter import LocalOpenProjectAdapter
from engineering_gateway.infrastructure.strictdoc_adapter import LocalStrictDocAdapter
from engineering_gateway.infrastructure.strictdoc_workspace_adapter import (
    LocalStrictDocWorkspaceAdapter,
)


class AdapterCompositionError(ValueError):
    """Raised when the configured external adapter set is inconsistent."""


@dataclass(frozen=True)
class ExternalAdapterSet:
    """Explicit collection of adapters supplied to the Gateway composition root.

    A system may have separate read and workspace adapters, but there must be only
    one effective adapter per system for each capability. This prevents ambiguous
    routing while still allowing StrictDoc's read-only CLI adapter to be replaced by
    its workspace-capable bridge adapter.
    """

    read_adapters: tuple[ReadAdapter, ...] = ()
    workspace_adapters: tuple[WorkspaceAdapter, ...] = ()

    def __post_init__(self) -> None:
        self._validate_unique(self.read_adapters, "read")
        self._validate_unique(self.workspace_adapters, "workspace")

    @staticmethod
    def _validate_unique(adapters: tuple[object, ...], capability: str) -> None:
        names: list[str] = []
        for adapter in adapters:
            name = getattr(adapter, "system_name", "")
            if not isinstance(name, str) or not name.strip():
                raise AdapterCompositionError(
                    f"{capability} adapter must expose a non-empty system_name"
                )
            if name in names:
                raise AdapterCompositionError(
                    f"duplicate {capability} adapter for system '{name}'"
                )
            names.append(name)

    def as_read_adapters(self) -> tuple[ReadAdapter, ...]:
        """Return adapters for application-level external reads."""
        return self.read_adapters

    def as_workspace_adapters(self) -> tuple[WorkspaceAdapter, ...]:
        """Return adapters capable of workspace reconciliation."""
        return self.workspace_adapters


@dataclass(frozen=True)
class LocalAdapterConfig:
    """Concrete local integration set used by a deployment composition root."""

    git: LocalGitAdapter | None = None
    strictdoc: LocalStrictDocAdapter | LocalStrictDocWorkspaceAdapter | None = None
    capella: LocalCapellaAdapter | None = None
    openproject: LocalOpenProjectAdapter | None = None


def compose_external_adapters(config: LocalAdapterConfig) -> ExternalAdapterSet:
    """Build a deterministic adapter set from explicitly constructed adapters.

    The function deliberately does not read environment variables or construct
    secrets. Connection/configuration parsing belongs to the application's runtime
    configuration layer; this function only establishes the dependency graph.
    """
    read: list[ReadAdapter] = []
    workspace: list[WorkspaceAdapter] = []

    for adapter in (config.strictdoc, config.capella, config.openproject):
        if adapter is not None:
            read.append(adapter)

    if isinstance(config.strictdoc, LocalStrictDocWorkspaceAdapter):
        workspace.append(config.strictdoc)
    if config.capella is not None:
        workspace.append(config.capella)

    return ExternalAdapterSet(tuple(read), tuple(workspace))


__all__ = [
    "AdapterCompositionError",
    "ExternalAdapterSet",
    "LocalAdapterConfig",
    "compose_external_adapters",
]
