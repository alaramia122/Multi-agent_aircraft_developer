"""StrictDoc workspace adapter backed by an explicit bridge protocol.

StrictDoc's current documentation exposes a stable CLI and describes a Python API,
but also explicitly notes that the public Python API is not yet documented. The
Gateway therefore does not import StrictDoc internals or invent a REST write API.
Writes are delegated to a separately versioned bridge executable.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation
from engineering_gateway.infrastructure.strictdoc_adapter import LocalStrictDocAdapter


class StrictDocWorkspaceAdapterError(RuntimeError):
    """Raised when the StrictDoc workspace bridge fails its protocol contract."""


@dataclass(frozen=True)
class StrictDocBridgeConfig:
    """Configuration for the isolated StrictDoc workspace bridge."""

    executable: str
    project_path: str | Path
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if not self.executable.strip():
            raise ValueError("executable must be non-empty")
        if not Path(self.project_path).exists():
            raise ValueError(f"StrictDoc project does not exist: {self.project_path}")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


class LocalStrictDocWorkspaceAdapter:
    """Read StrictDoc through the normal adapter and write through a bridge.

    The bridge owns all StrictDoc-native mutation details. Every workspace operation
    carries the Gateway workspace id and deterministic change-set hash, allowing the
    bridge to make retries idempotent without the Gateway depending on StrictDoc's
    undocumented internal Python API.
    """

    system_name = "strictdoc"

    def __init__(self, config: StrictDocBridgeConfig) -> None:
        self._config = config
        self._reader = LocalStrictDocAdapter(
            config.project_path,
            timeout_seconds=config.timeout_seconds,
        )

    async def get_element(self, external_id: str) -> EngineeringElement | None:
        return await self._reader.get_element(external_id)

    async def get_version(self) -> ExternalVersion:
        return await self._reader.get_version()

    async def create_workspace(
        self, workspace_id: UUID, source_version: str, change_set_hash: str
    ) -> None:
        await self._run(
            "create_workspace",
            {
                "workspace_id": str(workspace_id),
                "source_version": source_version,
                "change_set_hash": change_set_hash,
            },
        )

    async def apply_element(self, workspace_id: UUID, element: EngineeringElement) -> None:
        await self._run(
            "apply_element",
            {
                "workspace_id": str(workspace_id),
                "element": element.model_dump(mode="json"),
            },
        )

    async def apply_relation(self, workspace_id: UUID, relation: EngineeringRelation) -> None:
        await self._run(
            "apply_relation",
            {
                "workspace_id": str(workspace_id),
                "relation": relation.model_dump(mode="json"),
            },
        )

    async def _run(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._run_sync, operation, payload)

    def _run_sync(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = {
            "protocol": 1,
            "operation": operation,
            "project_path": str(Path(self._config.project_path).resolve()),
            "payload": payload,
        }
        try:
            result = subprocess.run(
                [self._config.executable],
                input=json.dumps(request),
                check=False,
                capture_output=True,
                text=True,
                timeout=self._config.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise StrictDocWorkspaceAdapterError(
                "StrictDoc workspace bridge could not be executed"
            ) from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown bridge error"
            raise StrictDocWorkspaceAdapterError(f"StrictDoc workspace bridge failed: {detail}")
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise StrictDocWorkspaceAdapterError(
                "StrictDoc workspace bridge returned invalid JSON"
            ) from exc
        if not isinstance(response, dict):
            raise StrictDocWorkspaceAdapterError(
                "StrictDoc workspace bridge returned a non-object JSON response"
            )
        if response.get("protocol") != 1:
            raise StrictDocWorkspaceAdapterError("unsupported StrictDoc bridge protocol")
        if response.get("operation") not in (None, operation):
            raise StrictDocWorkspaceAdapterError(
                "StrictDoc bridge returned an unexpected operation"
            )
        if response.get("ok") is not True:
            message = response.get("error") or "unknown StrictDoc bridge error"
            raise StrictDocWorkspaceAdapterError(str(message))
        return response


__all__ = [
    "LocalStrictDocWorkspaceAdapter",
    "StrictDocBridgeConfig",
    "StrictDocWorkspaceAdapterError",
]
