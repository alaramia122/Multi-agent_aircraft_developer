"""Capella adapter using an external headless bridge command."""

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


class CapellaAdapterError(RuntimeError):
    """Raised when the configured Capella bridge fails or returns invalid data."""


@dataclass(frozen=True)
class CapellaBridgeConfig:
    """Configuration for a headless Capella integration bridge."""

    executable: str
    project_path: str | Path
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if not self.executable.strip():
            raise ValueError("executable must be non-empty")
        if not Path(self.project_path).exists():
            raise ValueError(f"Capella project does not exist: {self.project_path}")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


class LocalCapellaAdapter:
    """Capella integration through a deterministic headless bridge.

    The adapter intentionally does not parse the Capella/EMF model itself. The bridge
    is responsible for using Capella's native EMF/Capella APIs and emits a small,
    versioned JSON protocol consumed by the Gateway.
    """

    system_name = "capella"

    def __init__(self, config: CapellaBridgeConfig) -> None:
        self._config = config

    async def get_element(self, external_id: str) -> EngineeringElement | None:
        if not external_id:
            raise ValueError("external_id must be non-empty")
        response = await self._run("get_element", {"external_id": external_id})
        element = response.get("element")
        return self._parse_element(element) if element is not None else None

    async def get_version(self) -> ExternalVersion:
        response = await self._run("get_version", {})
        version = response.get("version")
        if not isinstance(version, str) or not version:
            raise CapellaAdapterError("Capella bridge returned no version")
        return ExternalVersion(system=self.system_name, version=version)

    async def create_workspace(self, workspace_id: UUID, source_version: str, change_set_hash: str) -> None:
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
            {"workspace_id": str(workspace_id), "element": element.model_dump(mode="json")},
        )

    async def apply_relation(self, workspace_id: UUID, relation: EngineeringRelation) -> None:
        await self._run(
            "apply_relation",
            {"workspace_id": str(workspace_id), "relation": relation.model_dump(mode="json")},
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
            raise CapellaAdapterError("Capella bridge could not be executed") from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown bridge error"
            raise CapellaAdapterError(f"Capella bridge failed: {detail}")
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise CapellaAdapterError("Capella bridge returned invalid JSON") from exc
        if not isinstance(response, dict):
            raise CapellaAdapterError("Capella bridge returned a non-object JSON response")
        if response.get("protocol") != 1:
            raise CapellaAdapterError("unsupported Capella bridge protocol")
        if response.get("ok") is not True:
            message = response.get("error") or "unknown Capella bridge error"
            raise CapellaAdapterError(str(message))
        return response

    @staticmethod
    def _parse_element(value: Any) -> EngineeringElement:
        if not isinstance(value, dict):
            raise CapellaAdapterError("Capella bridge returned an invalid element")
        try:
            return EngineeringElement.model_validate(value)
        except ValueError as exc:
            raise CapellaAdapterError("Capella bridge returned an invalid canonical element") from exc


__all__ = ["CapellaAdapterError", "CapellaBridgeConfig", "LocalCapellaAdapter"]
