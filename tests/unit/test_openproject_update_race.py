"""Regression coverage for OpenProject optimistic-lock update races."""

from __future__ import annotations

import io
import json
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from engineering_gateway.infrastructure.openproject_adapter import (
    LocalOpenProjectAdapter,
    OpenProjectConfig,
)


class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def _response(payload: dict[str, object]) -> _Response:
    return _Response(json.dumps(payload).encode("utf-8"))


def _adapter() -> LocalOpenProjectAdapter:
    return LocalOpenProjectAdapter(
        OpenProjectConfig(
            base_url="https://openproject.example",
            api_token="token",
            project_id=7,
            change_request_type_id=4,
        )
    )


@pytest.mark.asyncio
async def test_update_change_request_recovers_from_optimistic_lock_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object | None]] = []

    def fake_urlopen(request: Request, timeout: float) -> _Response:
        del timeout
        payload = json.loads(request.data.decode("utf-8")) if request.data else None
        calls.append((request.method, payload))
        if request.method == "GET":
            if len(calls) == 1:
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
            return _response(
                {
                    "id": 9,
                    "lockVersion": 13,
                    "_links": {"status": {"href": "/api/v3/statuses/2"}},
                }
            )
        if len(calls) == 2:
            raise HTTPError(request.full_url, 409, "conflict", {}, io.BytesIO())
        return _response({"id": 9, "lockVersion": 14})

    monkeypatch.setattr(
        "engineering_gateway.infrastructure.openproject_adapter.urlopen", fake_urlopen
    )

    await _adapter().update_change_request("9", "/api/v3/statuses/3")

    assert [method for method, _ in calls] == ["GET", "PATCH", "GET", "PATCH"]
    assert calls[1][1] == {
        "lockVersion": 12,
        "_links": {"status": {"href": "/api/v3/statuses/3"}},
    }
    assert calls[3][1] == {
        "lockVersion": 13,
        "_links": {"status": {"href": "/api/v3/statuses/3"}},
    }


@pytest.mark.asyncio
async def test_update_change_request_treats_concurrent_matching_update_as_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_urlopen(request: Request, timeout: float) -> _Response:
        del timeout
        calls.append(request.method)
        if request.method == "GET":
            if len(calls) == 1:
                return _response(
                    {
                        "id": 9,
                        "lockVersion": 12,
                        "_links": {"status": {"href": "/api/v3/statuses/2"}},
                    }
                )
            return _response(
                {
                    "id": 9,
                    "lockVersion": 13,
                    "_links": {"status": {"href": "/api/v3/statuses/3"}},
                }
            )
        raise HTTPError(request.full_url, 409, "conflict", {}, io.BytesIO())

    monkeypatch.setattr(
        "engineering_gateway.infrastructure.openproject_adapter.urlopen", fake_urlopen
    )

    await _adapter().update_change_request("9", "/api/v3/statuses/3")

    assert calls == ["GET", "PATCH", "GET"]
