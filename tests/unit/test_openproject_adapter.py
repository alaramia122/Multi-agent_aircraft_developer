"""Tests for the OpenProject adapter boundary."""

from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from engineering_gateway.infrastructure.openproject_adapter import (
    LocalOpenProjectAdapter,
    OpenProjectAdapterError,
    OpenProjectConfig,
)


@pytest.fixture
def adapter() -> LocalOpenProjectAdapter:
    return LocalOpenProjectAdapter(
        OpenProjectConfig(
            base_url="https://openproject.example",
            api_token="token",
            project_id=7,
            change_request_type_id=4,
        )
    )


def _response(payload: dict[str, object]) -> io.BytesIO:
    response = io.BytesIO(json.dumps(payload).encode("utf-8"))
    response.__enter__ = lambda: response  # type: ignore[attr-defined]
    response.__exit__ = lambda *_: None  # type: ignore[attr-defined]
    return response


@pytest.mark.asyncio
async def test_get_element_maps_work_package(
    adapter: LocalOpenProjectAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_urlopen(request: Request, timeout: float) -> io.BytesIO:
        assert request.full_url.endswith("/api/v3/work_packages/123")
        assert timeout == 30.0
        return _response({"id": 123, "subject": "Approve change"})

    monkeypatch.setattr(
        "engineering_gateway.infrastructure.openproject_adapter.urlopen", fake_urlopen
    )

    element = await adapter.get_element("123")

    assert element is not None
    assert element.kind.value == "change"
    assert element.external_id == "123"
    assert element.name == "Approve change"


@pytest.mark.asyncio
async def test_create_change_request_sends_project_and_type_links(
    adapter: LocalOpenProjectAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request: Request, timeout: float) -> io.BytesIO:
        captured["method"] = request.method
        captured["body"] = json.loads(request.data.decode("utf-8")) if request.data else None
        return _response({"id": 321})

    monkeypatch.setattr(
        "engineering_gateway.infrastructure.openproject_adapter.urlopen", fake_urlopen
    )

    identifier = await adapter.create_change_request("Change title", "Change details")

    assert identifier == "321"
    assert captured["method"] == "POST"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["subject"] == "Change title"
    assert body["_links"]["project"]["href"] == "/api/v3/projects/7"
    assert body["_links"]["type"]["href"] == "/api/v3/types/4"


@pytest.mark.asyncio
async def test_update_change_request_uses_lock_version(
    adapter: LocalOpenProjectAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, dict[str, object] | None]] = []

    def fake_urlopen(request: Request, timeout: float) -> io.BytesIO:
        payload = json.loads(request.data.decode("utf-8")) if request.data else None
        calls.append((request.method, payload))
        if request.method == "GET":
            return _response({"id": 9, "lockVersion": 12})
        return _response({"id": 9, "lockVersion": 13})

    monkeypatch.setattr(
        "engineering_gateway.infrastructure.openproject_adapter.urlopen", fake_urlopen
    )

    await adapter.update_change_request("9", "/api/v3/statuses/3")

    assert calls[0] == ("GET", None)
    assert calls[1] == (
        "PATCH",
        {"lockVersion": 12, "_links": {"status": {"href": "/api/v3/statuses/3"}}},
    )


@pytest.mark.asyncio
async def test_get_element_returns_none_on_404(
    adapter: LocalOpenProjectAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_urlopen(request: Request, timeout: float) -> None:
        raise HTTPError(request.full_url, 404, "missing", {}, io.BytesIO())

    monkeypatch.setattr(
        "engineering_gateway.infrastructure.openproject_adapter.urlopen", fake_urlopen
    )

    assert await adapter.get_element("404") is None


@pytest.mark.asyncio
async def test_update_change_request_rejects_missing_lock_version(
    adapter: LocalOpenProjectAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "engineering_gateway.infrastructure.openproject_adapter.urlopen",
        lambda *_args, **_kwargs: _response({"id": 9}),
    )

    with pytest.raises(OpenProjectAdapterError, match="lockVersion"):
        await adapter.update_change_request("9", "/api/v3/statuses/3")
