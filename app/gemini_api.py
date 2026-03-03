from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import httpx


class GeminiAPI:
    _TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(self, api_key: str, model: str, client: httpx.Client) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client

    @property
    def _endpoint(self) -> str:
        encoded_model = quote(self._model, safe="")
        return (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{encoded_model}:generateContent"
        )

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        response = self._send_generate_request(
            self._build_payload(system_prompt, user_prompt, use_system_instruction=True),
        )
        if response.is_success:
            return self._extract_text_or_raise(response.json())

        if self._should_retry_without_system_instruction(response):
            fallback_prompt = (
                "Следуй этой роли и стилю ответа:\n"
                f"{system_prompt}\n\n"
                "Запрос пользователя:\n"
                f"{user_prompt}"
            )
            retry_response = self._send_generate_request(
                self._build_payload(
                    system_prompt="",
                    user_prompt=fallback_prompt,
                    use_system_instruction=False,
                ),
            )
            if retry_response.is_success:
                return self._extract_text_or_raise(retry_response.json())
            raise RuntimeError(self._format_api_error(retry_response))

        raise RuntimeError(self._format_api_error(response))

    def _send_generate_request(self, payload: dict[str, Any]) -> httpx.Response:
        retry_delays_sec = [0.5, 1.0]
        for attempt in range(len(retry_delays_sec) + 1):
            response = self._client.post(
                self._endpoint,
                params={"key": self._api_key},
                json=payload,
            )
            if response.status_code not in self._TRANSIENT_STATUS_CODES:
                return response
            if attempt == len(retry_delays_sec):
                return response
            time.sleep(retry_delays_sec[attempt])
        raise RuntimeError("Unexpected retry loop state.")

    @staticmethod
    def _build_payload(
        system_prompt: str, user_prompt: str, use_system_instruction: bool
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 1,
                "topP": 1,
                "maxOutputTokens": 2048,
            },
        }
        if use_system_instruction and system_prompt.strip():
            payload["system_instruction"] = {
                "parts": [{"text": system_prompt}],
            }
        return payload

    @staticmethod
    def _extract_text_or_raise(response_json: dict[str, Any]) -> str:
        text = GeminiAPI._extract_text(response_json)
        if text == "":
            raise RuntimeError("Gemini returned an empty text response.")
        return text

    @staticmethod
    def _extract_text(response_json: dict[str, Any]) -> str:
        candidates = response_json.get("candidates")
        if not isinstance(candidates, list):
            return ""

        chunks: list[str] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
        return "\n".join(chunks).strip()

    @staticmethod
    def _should_retry_without_system_instruction(response: httpx.Response) -> bool:
        if response.status_code != 400:
            return False
        message = GeminiAPI._extract_error_message(response)
        return "Developer instruction is not enabled" in message

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text[:500]
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message
        return str(payload)[:500]

    @staticmethod
    def _format_api_error(response: httpx.Response) -> str:
        message = GeminiAPI._extract_error_message(response)
        return f"Gemini API error {response.status_code}: {message}"
