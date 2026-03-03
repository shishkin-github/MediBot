from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise ValueError(f"Environment variable {name} is required.")
    return value


def _parse_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got: {raw}") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be >= 0, got: {parsed}")
    return parsed


def _parse_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        parsed = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got: {raw}") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be >= 0, got: {parsed}")
    return parsed


def _parse_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be boolean-like, got: {raw}")


def _optional_env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return value


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    gemini_api_key: str
    gemini_model: str
    http_proxy: Optional[str]
    https_proxy: Optional[str]
    sqlite_path: str
    poll_timeout_sec: int
    poll_retry_delay_sec: float
    audio_enabled: bool
    audio_id_heavy: Optional[str]
    audio_id_lost: Optional[str]
    audio_id_nothing: Optional[str]
    audio_id_meaning: Optional[str]
    audio_id_practice: Optional[str]
    audio_id_calm: Optional[str]

    @property
    def proxy_url(self) -> Optional[str]:
        return self.https_proxy or self.http_proxy

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv(override=False)

        http_proxy = _optional_env("HTTP_PROXY")
        https_proxy = _optional_env("HTTPS_PROXY")
        if http_proxy and https_proxy and http_proxy != https_proxy:
            raise ValueError(
                "HTTP_PROXY and HTTPS_PROXY must match for a single proxy setup."
            )
        if http_proxy and not https_proxy:
            https_proxy = http_proxy
        if https_proxy and not http_proxy:
            http_proxy = https_proxy

        return cls(
            telegram_bot_token=_require_env("TELEGRAM_BOT_TOKEN"),
            gemini_api_key=_require_env("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemma-3-12b-it"),
            http_proxy=http_proxy,
            https_proxy=https_proxy,
            sqlite_path=os.getenv("SQLITE_PATH", "/data/medibot.db"),
            poll_timeout_sec=_parse_int("POLL_TIMEOUT_SEC", 30),
            poll_retry_delay_sec=_parse_float("POLL_RETRY_DELAY_SEC", 2.0),
            audio_enabled=_parse_bool("AUDIO_ENABLED", False),
            audio_id_heavy=_optional_env("AUDIO_ID_HEAVY"),
            audio_id_lost=_optional_env("AUDIO_ID_LOST"),
            audio_id_nothing=_optional_env("AUDIO_ID_NOTHING"),
            audio_id_meaning=_optional_env("AUDIO_ID_MEANING"),
            audio_id_practice=_optional_env("AUDIO_ID_PRACTICE"),
            audio_id_calm=_optional_env("AUDIO_ID_CALM"),
        )

