"""OpenProject API v3 adapter for Gateway change requests."""

from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.models import ElementKind, EngineeringElement


class OpenProjectAdapterError(RuntimeError):
    """Raised when an OpenProject API operation cannot be completed."""


@dataclass(frozen=True)
class OpenProjectConfig:
    """Connection and work-package defaults for one OpenProject instance."""

    base_url: str
    api_token: str
    project_id: int
    change_request_type_id: int
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.base_url.strip():
            raise ValueError("base_url must be non-empty")
        if not self.api_token:
            raise ValueError("api_token must be non-empty")
        if self.project_id <= 0:
            raise ValueError("project_id must be positive")
        if self.change_request_type_id <= 0:
            raise ValueError("change_request_type_id must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


class LocalOpenProjectAdapter:
    """OpenProject API v3 adapter.

    OpenProject remains the authoritative source for change-request work packages.
    The Gateway stores only the external identifier and related references.
    """

    system_name = "openproject"

    def __init__(self, config: OpenProjectConfig) -> None:
        self._config = config
        self._base_url = config.base_url.rstrip("/")

    async def get_element(self, external_id: str) -> EngineeringElement | None:
        if not external_id:
            raise ValueError("external_id must be non-empty")
        return await asyncio.to_thread(self._get_element, external_id)

    async def get_version(self) -> ExternalVersion:
        payload = await asyncio.to_thread(self._request_json, "GET", "/api/v3")
        version = payload.get("coreVersion") or payload.get("instanceName")
        if not isinstance(version, str) or not version:
            raise OpenProjectAdapterError("OpenProject root response has no usable version")
        return ExternalVersion(system=self.system_name, version=version)

    async def create_change_request(self, title: str, description: str) -> str:
        if not title.strip():
            raise ValueError("title must be non-empty")
        payload = {
            "_type": "WorkPackage",
            "subject": title,
            "description": {"raw": description},
            "_links": {
                "project": {"href": f"/api/v3/projects/{self._config.project_id}"},
                "type": {
                    "href": f"/api/v3/types/{self._config.change_request_type_id}"
                },
            },
        }
        response = await asyncio.to_thread(
            self._request_json, "POST", "/api/v3/work_packages", payload
        )
        identifier = response.get("id")
        if not isinstance(identifier, int) or identifier <= 0:
            raise OpenProjectAdapterError("OpenProject create response has no numeric id")
        return str(identifier)

    async def update_change_request(self, external_id: str, status: str) -> None:
        if not external_id:
            raise ValueError("external_id must be non-empty")
        if not status.strip():
            raise ValueError("status must be non-empty")
        current = await asyncio.to_thread(
            self._request_json, "GET", f"/api/v3/work_packages/{quote(external_id)}"
        )
        lock_version = current.get("lockVersion")
        if not isinstance(lock_version, int):
            raise OpenProjectAdapterError("OpenProject work package has no lockVersion")
        payload = {
            "lockVersion": lock_version,
            "_links": {"status": {"href": status}},
        }
        await asyncio.to_thread(
            self._request_json,
            "PATCH",
            f"/api/v3/work_packages/{quote(external_id)}",
            payload,
        )

    def _get_element(self, external_id: str) -> EngineeringElement | None:
        try:
            payload = self._request_json(
                "GET", f"/api/v3/work_packages/{quote(external_id)}"
            )
        except OpenProjectAdapterError as exc:
            if exc.args and str(exc).startswith("OpenProject returned HTTP 404"):
                return None
            raise
        identifier = payload.get("id")
        if not isinstance(identifier, int):
            raise OpenProjectAdapterError("OpenProject work package has no numeric id")
        subject = payload.get("subject")
        if not isinstance(subject, str) or not subject:
            subject = f"Work package #{identifier}"
        return EngineeringElement(
            kind=ElementKind.CHANGE,
            type_id="openproject.work_package",
            name=subject,
            external_system=self.system_name,
            external_id=str(identifier),
            source_uri=f"openproject://{self._base_url}/work_packages/{identifier}",
        )

    def _request_json(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        token = base64.b64encode(f"apikey:{self._config.api_token}".encode()).decode()
        request = Request(
            f"{self._base_url}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/hal+json, application/json",
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self._config.timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            raise OpenProjectAdapterError(
                f"OpenProject returned HTTP {exc.code}: {exc.reason}"
            ) from exc
        except URLError as exc:
            raise OpenProjectAdapterError("OpenProject API request failed") from exc
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OpenProjectAdapterError("OpenProject returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise OpenProjectAdapterError("OpenProject returned a non-object JSON response")
        return result


__all__ = ["LocalOpenProjectAdapter", "OpenProjectAdapterError", "OpenProjectConfig"]
