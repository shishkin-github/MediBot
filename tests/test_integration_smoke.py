import json
import logging
from pathlib import Path

import httpx

from app.config import Config
from app.gemini_api import GeminiAPI
from app.main import process_updates_once
from app.router import BotRouter, SAFE_FALLBACK_MESSAGE
from app.storage import DialogStorage
from app.support_templates import BUTTON_TO_BLOCK, SUPPORT_TEMPLATES
from app.telegram_api import TelegramAPI


def _make_config(tmp_path: Path, audio_enabled: bool = False) -> Config:
    return Config(
        telegram_bot_token="test-token",
        gemini_api_key="test-gemini-key",
        gemini_model="gemma-4-26b-a4b-it",
        crisis_support_message=(
            "Мне важно отнестись к этому серьёзно. Если есть риск, что ты можешь навредить себе или кому-то ещё, пожалуйста, сразу обратись к человеку рядом"
        ),
        http_proxy=None,
        https_proxy=None,
        sqlite_path=str(tmp_path / "medibot.db"),
        poll_timeout_sec=30,
        poll_retry_delay_sec=2.0,
        audio_enabled=audio_enabled,
        audio_id_heavy=None,
        audio_id_lost=None,
        audio_id_nothing=None,
        audio_id_meaning=None,
        audio_id_practice=None,
        audio_id_calm=None,
    )


def test_smoke_button_template_send_message_cycle_without_gemini(tmp_path: Path) -> None:
    calls: dict[str, object] = {
        "gemini": 0,
        "send_message": 0,
        "sent_text": "",
    }
    button_text = "💭 Мне тяжело"
    expected_texts = {
        template.text for template in SUPPORT_TEMPLATES[BUTTON_TO_BLOCK[button_text]]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        path = request.url.path

        if host == "api.telegram.org" and path.endswith("/getUpdates"):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": [
                        {
                            "update_id": 100,
                            "message": {"chat": {"id": 42}, "text": button_text},
                        }
                    ],
                },
            )

        if host == "generativelanguage.googleapis.com":
            calls["gemini"] = int(calls["gemini"]) + 1
            raise AssertionError("Support buttons must not call Gemini")

        if host == "api.telegram.org" and path.endswith("/sendMessage"):
            calls["send_message"] = int(calls["send_message"]) + 1
            payload = json.loads(request.content.decode("utf-8"))
            calls["sent_text"] = payload["text"]
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    config = _make_config(tmp_path)
    storage = DialogStorage(config.sqlite_path)
    logger = logging.getLogger("test-smoke-button")

    telegram = TelegramAPI(config.telegram_bot_token, client)
    gemini = GeminiAPI(config.gemini_api_key, config.gemini_model, client)
    router = BotRouter(telegram, gemini, storage, config, logger)

    new_offset = process_updates_once(
        telegram=telegram,
        router=router,
        offset=None,
        timeout=0,
        logger=logger,
    )

    assert new_offset == 101
    assert calls["gemini"] == 0
    assert calls["send_message"] == 1
    assert calls["sent_text"] in expected_texts
    assert not str(calls["sent_text"]).endswith(".")
    assert storage.get_history(42) == ""
    assert storage.get_support_template_history(42, "heavy")


def test_smoke_master_gemini_error_fallback_message_and_continue(tmp_path: Path) -> None:
    calls: dict[str, object] = {
        "gemini": 0,
        "send_message": 0,
        "sent_text": "",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        path = request.url.path

        if host == "api.telegram.org" and path.endswith("/getUpdates"):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": [
                        {
                            "update_id": 200,
                            "message": {"chat": {"id": 77}, "text": "Расскажи что-то"},
                        }
                    ],
                },
            )

        if host == "generativelanguage.googleapis.com":
            calls["gemini"] = int(calls["gemini"]) + 1
            return httpx.Response(500, json={"error": "boom"})

        if host == "api.telegram.org" and path.endswith("/sendMessage"):
            calls["send_message"] = int(calls["send_message"]) + 1
            payload = json.loads(request.content.decode("utf-8"))
            calls["sent_text"] = payload["text"]
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 2}})

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    config = _make_config(tmp_path)
    storage = DialogStorage(config.sqlite_path)
    logger = logging.getLogger("test-fallback")

    telegram = TelegramAPI(config.telegram_bot_token, client)
    gemini = GeminiAPI(config.gemini_api_key, config.gemini_model, client)
    router = BotRouter(telegram, gemini, storage, config, logger)

    new_offset = process_updates_once(
        telegram=telegram,
        router=router,
        offset=None,
        timeout=0,
        logger=logger,
    )

    assert new_offset == 201
    assert calls["gemini"] == 3
    assert calls["send_message"] == 1
    assert calls["sent_text"] == SAFE_FALLBACK_MESSAGE
    assert not str(calls["sent_text"]).endswith(".")
    assert SAFE_FALLBACK_MESSAGE in storage.get_history(77)


def test_smoke_crisis_message_bypasses_gemini_and_history(tmp_path: Path) -> None:
    calls: dict[str, object] = {
        "gemini": 0,
        "send_message": 0,
        "sent_text": "",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        path = request.url.path

        if host == "api.telegram.org" and path.endswith("/getUpdates"):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": [
                        {
                            "update_id": 300,
                            "message": {"chat": {"id": 88}, "text": "Я хочу умереть"},
                        }
                    ],
                },
            )

        if host == "generativelanguage.googleapis.com":
            calls["gemini"] = int(calls["gemini"]) + 1
            raise AssertionError("Crisis messages must not call Gemini")

        if host == "api.telegram.org" and path.endswith("/sendMessage"):
            calls["send_message"] = int(calls["send_message"]) + 1
            payload = json.loads(request.content.decode("utf-8"))
            calls["sent_text"] = payload["text"]
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 3}})

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    config = _make_config(tmp_path)
    storage = DialogStorage(config.sqlite_path)
    logger = logging.getLogger("test-crisis")

    telegram = TelegramAPI(config.telegram_bot_token, client)
    gemini = GeminiAPI(config.gemini_api_key, config.gemini_model, client)
    router = BotRouter(telegram, gemini, storage, config, logger)

    new_offset = process_updates_once(
        telegram=telegram,
        router=router,
        offset=None,
        timeout=0,
        logger=logger,
    )

    assert new_offset == 301
    assert calls["gemini"] == 0
    assert calls["send_message"] == 1
    assert calls["sent_text"] == config.crisis_support_message
    assert not str(calls["sent_text"]).endswith(".")
    assert storage.get_history(88) == ""
