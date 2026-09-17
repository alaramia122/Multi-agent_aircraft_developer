"""Deployment readiness checks for the Gateway process and integrations."""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import httpx
from sqlalchemy import text

from engineering_gateway.config import Settings
from engineering_gateway.infrastructure.db import Database

CheckStatus = Literal["ready", "disabled", "not_ready"]
SCHEMA_VERSION = 14


@dataclass(frozen=True)
class ReadinessCheck:
    """One named readiness result."""

    name: str
    status: CheckStatus
    detail: str


@dataclass(frozen=True)
class ReadinessReport:
    """Stable readiness response suitable for health endpoints."""

    ready: bool
    checks: tuple[ReadinessCheck, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "status": "ready" if self.ready else "not_ready",
            "checks": [asdict(check) for check in self.checks],
        }


async def _database_check(database: Database) -> ReadinessCheck:
    try:
        async with database.session() as session:
            await session.execute(text("SELECT 1"))
            result = await session.execute(
                text("SELECT version FROM gateway_schema_version WHERE id = TRUE")
            )
            version = result.scalar_one_or_none()
        if version != SCHEMA_VERSION:
            return ReadinessCheck(
                "postgresql",
                "not_ready",
                f"schema version {version!r} does not match required {SCHEMA_VERSION}",
            )
        return ReadinessCheck("postgresql", "ready", f"schema version {SCHEMA_VERSION}")
    except Exception as exc:  # noqa: BLE001 - health probes must convert failures to status
        return ReadinessCheck("postgresql", "not_ready", type(exc).__name__)


def _git_repository_check(path: str) -> ReadinessCheck:
    candidate = Path(path)
    if not candidate.exists():
        return ReadinessCheck("git.repository", "not_ready", f"path does not exist: {candidate}")
    git_metadata = candidate / ".git"
    if not git_metadata.exists():
        return ReadinessCheck("git.repository", "not_ready", f"Git metadata is missing: {git_metadata}")
    return ReadinessCheck("git.repository", "ready", str(candidate))


def _path_check(name: str, path: str | None) -> ReadinessCheck:
    if not path:
        return ReadinessCheck(name, "not_ready", "path is not configured")
    candidate = Path(path)
    if candidate.exists():
        return ReadinessCheck(name, "ready", str(candidate))
    return ReadinessCheck(name, "not_ready", f"path does not exist: {candidate}")


def _executable_check(name: str, executable: str | None) -> ReadinessCheck:
    if not executable:
        return ReadinessCheck(name, "not_ready", "executable is not configured")
    resolved = shutil.which(executable)
    if resolved:
        return ReadinessCheck(name, "ready", resolved)
    candidate = Path(executable)
    if candidate.is_file():
        return ReadinessCheck(name, "ready", str(candidate))
    return ReadinessCheck(name, "not_ready", f"executable is not available: {executable}")


async def _http_endpoint_check(name: str, url: str | None) -> ReadinessCheck:
    if not url:
        return ReadinessCheck(name, "not_ready", "endpoint is not configured")
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.get(url.rstrip("/") + "/")
        if response.status_code < 500:
            return ReadinessCheck(name, "ready", f"HTTP {response.status_code}")
        return ReadinessCheck(name, "not_ready", f"HTTP {response.status_code}")
    except httpx.HTTPError as exc:
        return ReadinessCheck(name, "not_ready", type(exc).__name__)


async def check_readiness(database: Database, configuration: Settings) -> ReadinessReport:
    """Evaluate process-critical and explicitly enabled integration prerequisites."""

    checks: list[ReadinessCheck] = [await _database_check(database)]

    if configuration.identity.enabled:
        checks.append(
            ReadinessCheck(
                "identity",
                "not_ready",
                "upstream authentication layer is not connected to the trusted claims boundary",
            )
        )
    else:
        checks.append(ReadinessCheck("identity", "disabled", "external identity mapping is disabled"))

    if configuration.git.enabled:
        checks.append(_git_repository_check(configuration.git.repository_root))
    else:
        checks.append(ReadinessCheck("git", "disabled", "Git integration is disabled"))

    if configuration.strictdoc.enabled:
        checks.append(_executable_check("strictdoc.executable", configuration.strictdoc.executable))
        checks.append(_path_check("strictdoc.project", configuration.strictdoc.project_path))
    else:
        checks.append(ReadinessCheck("strictdoc", "disabled", "StrictDoc integration is disabled"))

    if configuration.capella.enabled:
        checks.append(_executable_check("capella.executable", configuration.capella.executable))
        checks.append(_path_check("capella.project", configuration.capella.project_path))
    else:
        checks.append(ReadinessCheck("capella", "disabled", "Capella integration is disabled"))

    if configuration.openproject.enabled:
        checks.append(await _http_endpoint_check("openproject", configuration.openproject.base_url))
    else:
        checks.append(ReadinessCheck("openproject", "disabled", "OpenProject integration is disabled"))

    if configuration.object_storage.enabled:
        checks.append(await _http_endpoint_check("object_storage", configuration.object_storage.endpoint_url))
    else:
        checks.append(ReadinessCheck("object_storage", "disabled", "Object Storage integration is disabled"))

    ready = all(check.status in {"ready", "disabled"} for check in checks)
    return ReadinessReport(ready=ready, checks=tuple(checks))
