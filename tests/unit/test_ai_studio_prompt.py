"""AI Studio must not silently return an incomplete response to a human."""

import httpx
import pytest

from engineering_gateway.infrastructure.ai_studio_prompt import AiStudioUnavailable, YandexPromptClient


@pytest.mark.asyncio
async def test_model_continues_token_limited_answer(monkeypatch) -> None:
    calls = []

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def get(self, *args, **kwargs):
            return httpx.Response(200, json={"access_token": "test"}, request=httpx.Request("GET", "https://example.test"))
        async def post(self, *args, **kwargs):
            calls.append(kwargs["json"])
            finished = len(calls) == 2
            return httpx.Response(200, json={
                "id": str(len(calls)), "status": "completed" if finished else "incomplete",
                "incomplete_details": None if finished else {"reason": "max_output_tokens"},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "конец" if finished else "начало "}]}],
            }, request=httpx.Request("POST", "https://example.test"))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    answer = await YandexPromptClient("folder", "model").answer("запрос")
    assert answer["answer"] == "начало конец"
    assert calls[0]["max_output_tokens"] == 4000
    assert calls[0]["store"] is False


@pytest.mark.asyncio
async def test_model_refuses_unfinished_non_token_response(monkeypatch) -> None:
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def get(self, *args, **kwargs):
            return httpx.Response(200, json={"access_token": "test"}, request=httpx.Request("GET", "https://example.test"))
        async def post(self, *args, **kwargs):
            return httpx.Response(200, json={
                "status": "incomplete", "incomplete_details": {"reason": "content_filter"},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "часть"}]}],
            }, request=httpx.Request("POST", "https://example.test"))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    with pytest.raises(AiStudioUnavailable):
        await YandexPromptClient("folder", "model").answer("запрос")
