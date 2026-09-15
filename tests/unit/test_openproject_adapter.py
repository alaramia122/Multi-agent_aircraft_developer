"""Tests for the OpenProject adapter boundary."""

from __future__ import annotations

import io
import json
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from engineering_gateway.infrastructure.openproject_adapter import (
    LocalOpenProjectAdapter,
    OpenProjectAdapterError,
    OpenProjectConfig,
)


class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


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


def _response(payload: dict[str, object]) -> _Response:
    return _Response(json.dumps(payload).encode("utf-8"))


def test_openproject_config_rejects_non_http_url() -> None:
    with pytest.raises(ValueError, match="absolute HTTP\(S\) URL"):
        OpenProjectConfig("ftp://openproject.example", "token", 7, 4)


def test_openproject_config_rejects_query_or_fragment() -> None:
    with pytest.raises(ValueError, match="query or fragment"):
        OpenProjectConfig("https://openproject.example/api?tenant=1", "token", 7, 4)


def test_openproject_config_accepts_reverse_proxy_path() -> None:
    config = OpenProjectConfig("https://openproject.example/openproject/", "token", 7, 4)
    assert config.base_url.endswith("/")


@pytest.mark.asyncio
async def test_get_element_maps_work_package(
    adapter: LocalOpenProjectAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_urlopen(request: Request, timeout: float) -> _Response:
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

    def fake_urlopen(request: Request, timeout: float) -> _Response:
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
async def test_create_change_request_returns_existing_id_for_idempotency_key(
    adapter: LocalOpenProjectAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def fake_urlopen(request: Request, timeout: float) -> _Response:
        calls.append(request.method)
        if request.method == "GET":
            return _response({"_embedded": {"elements": [{"id": 321}]}})
        return _response({"id": 999})

    monkeypatch.setattr(
        "engineering_gateway.infrastructure.openproject_adapter.urlopen", fake_urlopen
    )

    identifier = await adapter.create_change_request(
        "Change title", "Change details", idempotency_key="CR-123"
    )

    assert identifier == "321"
    assert calls == ["GET"]


@pytest.mark.asyncio
async def test_create_change_request_uses_idempotency_marker_when_missing(
    adapter: LocalOpenProjectAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[tuple[str, object]] = []

    def fake_urlopen(request: Request, timeout: float) -> _Response:
        captured.append((request.method, request.data))
        if request.method == "GET":
            return _response({"_embedded": {"elements": []}})
        return _response({"id": 322})

    monkeypatch.setattr(
        "engineering_gateway.infrastructure.openproject_adapter.urlopen", fake_urlopen
    )

    identifier = await adapter.create_change_request(
        "Change title", "Change details", idempotency_key="CR-123"
    )

    assert identifier == "322"
    assert [method for method, _ in captured] == ["GET", "POST"]
    body = json.loads(captured[1][1].decode("utf-8"))
    assert body["subject"] == "[CR-123] Change title"


@pytest.mark.asyncio
async def test_update_change_request_uses_lock_version_and_hypermedia_update_link(
    adapter: LocalOpenProjectAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_urlopen(request: Request, timeout: float) -> _Response:
        payload = json.loads(request.data.decode("utf-8")) if request.data else None
        calls.append((request.method, request.full_url, payload))
        if request.method == "GET":
            return _response(
                {
                    "id": 9,
                    "lockVersion": 12,
                    "_links": {
                        "status": {"href": "/api/v3/statuses/2"},
                        "update": {"href": "/api/v3/work_packages/9", "method": "patch"},
                    },
                }
            )
        return _response({"id": 9, "lockVersion": 13})

    monkeypatch.setattr(
        "engineering_gateway.infrastructure.openproject_adapter.urlopen", fake_urlopen
    )

    await adapter.update_change_request("9", "/api/v3/statuses/3")

    assert calls[0] == (
        "GET",
        "https://openproject.example/api/v3/work_packages/9",
        None,
    )
    assert calls[1] == (
        "PATCH",
        "https://openproject.example/api/v3/work_packages/9",
        {"lockVersion": 12, "_links": {"status": {"href": "/api/v3/statuses/3"}}},
    )


@pytest.mark.asyncio
async def test_update_change_request_is_idempotent_when_status_already_matches(
    adapter: LocalOpenProjectAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def fake_urlopen(request: Request, timeout: float) -> _Response:
        calls.append(request.method)
        return _response(
            {
                "id": 9,
                "lockVersion": 12,
                "_links": {"status": {"href": "/api/v3/statuses/3"}},
            }
        )

    monkeypatch.setattr(
        "engineering_gateway.infrastructure.openproject_adapter.urlopen", fake_urlopen
    )

    await adapter.update_change_request("9", "/api/v3/statuses/3")

    assert calls == ["GET"]


@pytest.mark.asyncio
async def test_update_change_request_rejects_status_name_instead_of_href(
    adapter: LocalOpenProjectAdapter,
) -> None:
    with pytest.raises(ValueError, match="status_href"):
        await adapter.update_change_request("9", "Approved")


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
