import json

import httpx
import pytest

from app.gemini_api import GeminiAPI


def test_gemma_4_payload_uses_fast_generation_profile_without_thinking() -> None:
    captured_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        captured_payloads.append(payload)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "Короткий ответ."}]}}
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    api = GeminiAPI(api_key="k", model="gemma-4-26b-a4b-it", client=client)

    result = api.generate_text("system prompt", "user prompt")

    assert result == "Короткий ответ"
    assert len(captured_payloads) == 1
    payload = captured_payloads[0]
    assert payload["generationConfig"] == {
        "temperature": 1,
        "topP": 0.95,
        "topK": 64,
        "maxOutputTokens": 384,
    }
    assert "thinkingConfig" not in payload["generationConfig"]
    assert payload["system_instruction"] == {"parts": [{"text": "system prompt"}]}


def test_gemini_retries_without_system_instruction_for_legacy_gemma_models() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        payload = json.loads(request.content.decode("utf-8"))

        if calls["count"] == 1:
            assert "system_instruction" in payload
            return httpx.Response(
                400,
                json={
                    "error": {
                        "code": 400,
                        "message": "Developer instruction is not enabled for models/gemma-3-12b-it",
                        "status": "INVALID_ARGUMENT",
                    }
                },
            )

        assert "system_instruction" not in payload
        assert "Следуй этой роли и стилю ответа" in payload["contents"][0]["parts"][0]["text"]
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "Тестовый ответ."}],
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    api = GeminiAPI(api_key="k", model="gemma-3-12b-it", client=client)

    result = api.generate_text("system prompt", "user prompt")
    assert result == "Тестовый ответ"
    assert calls["count"] == 2


def test_gemini_sanitizes_thinking_blocks_and_final_dot() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "<think>hidden</think>\nОтвет без внутреннего рассуждения."
                                }
                            ]
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    api = GeminiAPI(api_key="k", model="gemma-4-26b-a4b-it", client=client)

    assert api.generate_text("system prompt", "user prompt") == "Ответ без внутреннего рассуждения"


def test_gemini_raises_runtime_error_with_sanitized_message() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": 400,
                    "message": "Bad request reason",
                    "status": "INVALID_ARGUMENT",
                }
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    api = GeminiAPI(api_key="k", model="gemma-4-26b-a4b-it", client=client)

    with pytest.raises(RuntimeError) as exc:
        api.generate_text("system prompt", "user prompt")

    text = str(exc.value)
    assert "Gemini API error 400" in text
    assert "Bad request reason" in text
    assert "https://" not in text


def test_gemini_retries_transient_errors() -> None:
    calls = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3:
            return httpx.Response(
                503,
                json={
                    "error": {
                        "code": 503,
                        "message": "High demand",
                        "status": "UNAVAILABLE",
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "Ответ после retry."}]}}
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    api = GeminiAPI(api_key="k", model="gemma-4-26b-a4b-it", client=client)

    result = api.generate_text("system prompt", "user prompt")
    assert result == "Ответ после retry"
    assert calls["count"] == 3
