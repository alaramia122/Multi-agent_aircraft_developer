"""Governed read-only tool adapters for explicitly configured Gateway capabilities."""

from __future__ import annotations

from typing import Any

from engineering_gateway.domain.adapters import GitAdapter
from engineering_gateway.domain.tool_registry import ToolDescriptor


class GitSnapshotToolAdapter:
    """Expose a fixed configured Git repository snapshot as a read-only tool."""

    def __init__(self, git: GitAdapter, repository_root: str | None) -> None:
        if repository_root is None or not repository_root.strip():
            raise ValueError("a configured Git repository root is required")
        self._git = git
        self._repository_root = repository_root

    async def execute(
        self, tool: ToolDescriptor, operation: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        if tool.tool_id != "gateway.git.snapshot":
            raise ValueError("Git snapshot adapter received an unexpected tool descriptor")
        if operation != "snapshot":
            raise ValueError("unsupported Git snapshot operation")
        unexpected = set(arguments) - {"ref"}
        if unexpected:
            raise ValueError(f"unsupported Git snapshot arguments: {', '.join(sorted(unexpected))}")
        ref = arguments.get("ref", "HEAD")
        if not isinstance(ref, str) or not ref.strip() or len(ref) > 256:
            raise ValueError("ref must be a non-empty string of at most 256 characters")
        snapshot = await self._git.get_snapshot(self._repository_root, ref.strip())
        return snapshot.model_dump(mode="json")


__all__ = ["GitSnapshotToolAdapter"]
