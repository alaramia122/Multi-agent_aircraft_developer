"""Regression test for the OpenProject create idempotency race."""

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


def _adapter() -> LocalOpenProjectAdapter:
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


@pytest.mark.asyncio
async def test_create_change_request_recovers_from_concurrent_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_urlopen(request: Request, timeout: float) -> _Response:
        calls.append(request.method)
        if request.method == "GET":
            return _response({"_embedded": {"elements": [{"id": 321}]}})
        raise HTTPError(request.full_url, 409, "conflict", {}, io.BytesIO())

    monkeypatch.setattr(
        "engineering_gateway.infrastructure.openproject_adapter.urlopen", fake_urlopen
    )

    identifier = await _adapter().create_change_request(
        "Change title", "Change details", idempotency_key="CR-123"
    )

    assert identifier == "321"
    assert calls == ["GET", "POST", "GET"]
