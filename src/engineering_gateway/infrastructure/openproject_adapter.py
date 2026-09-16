"""OpenProject API v3 adapter for Gateway change requests."""

from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.models import ElementKind, EngineeringElement


class OpenProjectAdapterError(RuntimeError):
    """Raised when an OpenProject API operation cannot be completed."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class OpenProjectConfig:
    """Connection and work-package defaults for one OpenProject instance."""

    base_url: str
    api_token: str
    project_id: int
    change_request_type_id: int
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        base_url = self.base_url.strip()
        if not base_url:
            raise ValueError("base_url must be non-empty")
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        if parsed.query or parsed.fragment:
            raise ValueError("base_url must not contain a query or fragment")
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
        self._base_url = config.base_url.strip().rstrip("/")

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

    async def create_change_request(
        self, title: str, description: str, idempotency_key: str | None = None
    ) -> str:
        if not title.strip():
            raise ValueError("title must be non-empty")
        if idempotency_key is not None and not idempotency_key.strip():
            raise ValueError("idempotency_key must be non-empty when provided")

        subject = title
        if idempotency_key:
            subject = f"[{idempotency_key}] {title}"
            existing = await asyncio.to_thread(self._find_by_subject, subject)
            if existing is not None:
                return existing

        payload = {
            "_type": "WorkPackage",
            "subject": subject,
            "description": {"raw": description},
            "_links": {
                "project": {"href": f"/api/v3/projects/{self._config.project_id}"},
                "type": {"href": f"/api/v3/types/{self._config.change_request_type_id}"},
            },
        }
        try:
            response = await asyncio.to_thread(
                self._request_json, "POST", "/api/v3/work_packages", payload
            )
        except OpenProjectAdapterError as exc:
            if idempotency_key and exc.status_code == 409:
                existing = await asyncio.to_thread(self._find_by_subject, subject)
                if existing is not None:
                    return existing
            raise
        identifier = response.get("id")
        if not isinstance(identifier, int) or identifier <= 0:
            raise OpenProjectAdapterError("OpenProject create response has no numeric id")
        return str(identifier)

    async def update_change_request(self, external_id: str, status_href: str) -> None:
        if not external_id:
            raise ValueError("external_id must be non-empty")
        if not status_href.strip():
            raise ValueError("status_href must be non-empty")
        if not status_href.startswith("/api/v3/statuses/"):
            raise ValueError("status_href must be an OpenProject status API href")
        current = await asyncio.to_thread(
            self._request_json, "GET", f"/api/v3/work_packages/{quote(external_id, safe='')}"
        )
        lock_version = current.get("lockVersion")
        if not isinstance(lock_version, int):
            raise OpenProjectAdapterError("OpenProject work package has no lockVersion")
        current_status = self._status_href(current)
        if current_status == status_href:
            return
        update_href = self._update_href(current, external_id)
        payload = {
            "lockVersion": lock_version,
            "_links": {"status": {"href": status_href}},
        }
        try:
            await asyncio.to_thread(self._request_json, "PATCH", update_href, payload)
        except OpenProjectAdapterError as exc:
            if exc.status_code != 409:
                raise
            # Another writer may have advanced lockVersion between GET and PATCH.
            # Re-read once; if it already reached the requested state the operation
            # is complete, otherwise retry exactly once with the fresh lockVersion.
            current = await asyncio.to_thread(
                self._request_json,
                "GET",
                f"/api/v3/work_packages/{quote(external_id, safe='')}",
            )
            lock_version = current.get("lockVersion")
            if not isinstance(lock_version, int):
                raise OpenProjectAdapterError(
                    "OpenProject work package has no lockVersion after conflict"
                )
            if self._status_href(current) == status_href:
                return
            update_href = self._update_href(current, external_id)
            retry_payload = {
                "lockVersion": lock_version,
                "_links": {"status": {"href": status_href}},
            }
            await asyncio.to_thread(self._request_json, "PATCH", update_href, retry_payload)

    def _find_by_subject(self, subject: str) -> str | None:
        filters = json.dumps(
            [{"subject": {"operator": "=", "values": [subject]}}],
            separators=(",", ":"),
        )
        query = urlencode({"filters": filters, "pageSize": "2"})
        response = self._request_json(
            "GET",
            f"/api/v3/projects/{self._config.project_id}/work_packages?{query}",
        )
        embedded = response.get("_embedded")
        if not isinstance(embedded, dict):
            raise OpenProjectAdapterError("OpenProject collection has no _embedded object")
        elements = embedded.get("elements")
        if not isinstance(elements, list):
            raise OpenProjectAdapterError("OpenProject collection has no elements list")
        if len(elements) > 1:
            raise OpenProjectAdapterError(
                "multiple OpenProject work packages match the idempotency key"
            )
        if not elements:
            return None
        identifier = elements[0].get("id") if isinstance(elements[0], dict) else None
        if not isinstance(identifier, int) or identifier <= 0:
            raise OpenProjectAdapterError("OpenProject idempotency lookup returned an invalid id")
        return str(identifier)

    @staticmethod
    def _status_href(payload: dict[str, Any]) -> str | None:
        links = payload.get("_links")
        if not isinstance(links, dict):
            return None
        status = links.get("status")
        if not isinstance(status, dict):
            return None
        href = status.get("href")
        return href if isinstance(href, str) else None

    @staticmethod
    def _update_href(payload: dict[str, Any], external_id: str) -> str:
        links = payload.get("_links")
        if isinstance(links, dict):
            update = links.get("update")
            if isinstance(update, dict):
                href = update.get("href")
                method = update.get("method")
                if isinstance(href, str) and href and method in (None, "patch", "PATCH"):
                    return href
        return f"/api/v3/work_packages/{quote(external_id, safe='')}"

    def _get_element(self, external_id: str) -> EngineeringElement | None:
        try:
            payload = self._request_json(
                "GET", f"/api/v3/work_packages/{quote(external_id, safe='')}"
            )
        except OpenProjectAdapterError as exc:
            if exc.status_code == 404:
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
                f"OpenProject returned HTTP {exc.code}: {exc.reason}", status_code=exc.code
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
