from __future__ import annotations

from typing import Any, Optional

import httpx


class TelegramAPI:
    def __init__(self, token: str, client: httpx.Client) -> None:
        self._token = token
        self._client = client

    @property
    def _base_url(self) -> str:
        return f"https://api.telegram.org/bot{self._token}"

    def _post(self, method: str, payload: dict[str, Any]) -> Any:
        response = self._client.post(f"{self._base_url}/{method}", json=payload)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error at {method}: {data}")
        return data.get("result")

    def get_updates(self, offset: Optional[int], timeout: int) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            payload["offset"] = offset

        result = self._post("getUpdates", payload)
        if isinstance(result, list):
            return result
        return []

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        result = self._post("sendMessage", payload)
        if not isinstance(result, dict):
            raise RuntimeError("Unexpected Telegram sendMessage response payload.")
        return result

    def send_audio(
        self,
        chat_id: int,
        file_id: str,
        caption: Optional[str] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "audio": file_id,
        }
        if caption:
            payload["caption"] = caption
        result = self._post("sendAudio", payload)
        if not isinstance(result, dict):
            raise RuntimeError("Unexpected Telegram sendAudio response payload.")
        return result

