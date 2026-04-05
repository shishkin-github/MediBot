from __future__ import annotations

import logging
from typing import Literal

from app.config import Config
from app.gemini_api import GeminiAPI
from app.storage import DialogStorage
from app.support_templates import BUTTON_TEMPLATE_BLOCKS, BUTTON_TO_BLOCK, choose_support_template
from app.telegram_api import TelegramAPI
from app.text_utils import normalize_ui_text

RouteName = Literal["crisis", "reset", "button", "master"]

RESET_TEXTS = {
    "/start",
    "🛑 Завершить диалог с мастером",
}

MASTER_ENTRY_TEXT = "🧙‍♂️ Поговорить с Мастером"

MAIN_MENU_TEXT = "Вы вернулись в главное меню. Выберите, что чувствует ваша душа"
MASTER_ENTRY_MESSAGE = "Я рядом. Напиши, что сейчас с тобой происходит, и я отвечу коротко и бережно"

MAIN_MENU_MARKUP = {
    "keyboard": [
        [{"text": "💭 Мне тяжело"}, {"text": "🌫 Я потерял себя"}],
        [{"text": "💔 Я ничего не хочу"}, {"text": "🌿 Хочу почувствовать покой"}],
        [{"text": "💫 Хочу вспомнить смысл"}, {"text": "📿 Получить практику"}],
        [{"text": MASTER_ENTRY_TEXT}],
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False,
    "is_persistent": True,
}

STOP_DIALOG_MARKUP = {
    "keyboard": [
        [{"text": "🛑 Завершить диалог с мастером"}],
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False,
}

MASTER_SYSTEM_PROMPT = (
    "Ты — Мастер-психолог-эзотерик. Отвечай мягко, глубоко и бережно. "
    "Давай 2-4 короткие фразы без внутреннего рассуждения, без списка из множества шагов, "
    "с одним ясным вопросом или одной опорой в конце"
)

SAFE_FALLBACK_MESSAGE = (
    "Сейчас мне трудно подобрать слова. "
    "Напиши мне ещё раз через несколько секунд"
)

_CRISIS_MARKERS = (
    "хочу умереть",
    "не хочу жить",
    "покончить с собой",
    "совершить самоубийство",
    "убить себя",
    "навредить себе",
    "причинить себе боль",
    "порезать себя",
    "суицид",
    "самоубий",
    "self harm",
    "kill myself",
    "suicide",
)


def is_crisis_message(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _CRISIS_MARKERS)


def detect_route(text: str) -> RouteName:
    if is_crisis_message(text):
        return "crisis"
    if text in RESET_TEXTS:
        return "reset"
    if text in BUTTON_TEMPLATE_BLOCKS:
        return "button"
    return "master"


def build_master_user_prompt(history: str, current_text: str) -> str:
    history_block = history.strip() or "Истории пока нет"
    return (
        f"Предыдущая переписка:\n{history_block}\n\n"
        f"Текущее сообщение пользователя:\n{current_text.strip()}"
    )


def compose_history(existing_history: str, user_text: str, master_reply: str) -> str:
    normalized_user_text = user_text.strip()
    normalized_reply = normalize_ui_text(master_reply)
    new_block = f"User: {normalized_user_text}\nMaster: {normalized_reply}"
    base = existing_history.strip()
    if base == "":
        return new_block
    return f"{base}\n{new_block}"


class BotRouter:
    def __init__(
        self,
        telegram: TelegramAPI,
        gemini: GeminiAPI,
        storage: DialogStorage,
        config: Config,
        logger: logging.Logger,
    ) -> None:
        self._telegram = telegram
        self._gemini = gemini
        self._storage = storage
        self._config = config
        self._logger = logger

    def handle_update(self, update: dict) -> None:
        message = update.get("message")
        if not isinstance(message, dict):
            return
        text = message.get("text")
        chat = message.get("chat")
        if not isinstance(chat, dict) or not isinstance(text, str):
            return
        chat_id = chat.get("id")
        if not isinstance(chat_id, int):
            return
        self.handle_message(chat_id, text)

    def handle_message(self, chat_id: int, text: str) -> None:
        route = detect_route(text)
        if route == "crisis":
            self._handle_crisis(chat_id)
            return
        if route == "reset":
            self._handle_reset(chat_id)
            return
        if route == "button":
            self._handle_button(chat_id, text)
            return
        self._handle_master(chat_id, text)

    def _handle_crisis(self, chat_id: int) -> None:
        self._send_message(
            chat_id=chat_id,
            text=self._config.crisis_support_message,
        )

    def _handle_reset(self, chat_id: int) -> None:
        self._send_message(
            chat_id=chat_id,
            text=MAIN_MENU_TEXT,
            reply_markup=MAIN_MENU_MARKUP,
        )
        self._storage.delete_history(chat_id)

    def _handle_button(self, chat_id: int, button_text: str) -> None:
        block = BUTTON_TO_BLOCK[button_text]
        history = self._storage.get_support_template_history(chat_id, block)
        template = choose_support_template(block=block, history=history)
        self._storage.log_support_template(
            chat_id=chat_id,
            block=block,
            template_id=template.id,
            method_family=template.method_family,
        )
        self._send_message(chat_id, template.text)

        if not self._config.audio_enabled:
            return
        file_id = self._get_audio_file_id(button_text)
        if file_id is None:
            self._logger.warning("Audio is enabled but file_id is not set for: %s", button_text)
            return
        try:
            self._telegram.send_audio(chat_id=chat_id, file_id=file_id)
        except Exception:
            self._logger.exception("Failed to send audio for button: %s", button_text)

    def _handle_master(self, chat_id: int, user_text: str) -> None:
        if user_text == MASTER_ENTRY_TEXT:
            self._send_message(
                chat_id=chat_id,
                text=MASTER_ENTRY_MESSAGE,
                reply_markup=STOP_DIALOG_MARKUP,
            )
            return

        history = self._storage.get_history(chat_id)
        prompt = build_master_user_prompt(history, user_text)
        reply = self._ask_gemini(
            system_prompt=MASTER_SYSTEM_PROMPT,
            user_prompt=prompt,
            context_name="master_reply",
        )
        updated_history = compose_history(history, user_text, reply)
        self._storage.upsert_history(chat_id, updated_history)
        self._send_message(
            chat_id=chat_id,
            text=reply,
            reply_markup=STOP_DIALOG_MARKUP,
        )

    def _send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict | None = None,
    ) -> None:
        self._telegram.send_message(
            chat_id=chat_id,
            text=normalize_ui_text(text),
            reply_markup=reply_markup,
        )

    def _ask_gemini(self, system_prompt: str, user_prompt: str, context_name: str) -> str:
        try:
            return normalize_ui_text(self._gemini.generate_text(system_prompt, user_prompt))
        except Exception:
            self._logger.exception("Gemini generation failed in %s.", context_name)
            return normalize_ui_text(SAFE_FALLBACK_MESSAGE)

    def _get_audio_file_id(self, button_text: str) -> str | None:
        config_field = {
            "💭 Мне тяжело": "audio_id_heavy",
            "🌫 Я потерял себя": "audio_id_lost",
            "💔 Я ничего не хочу": "audio_id_nothing",
            "💫 Хочу вспомнить смысл": "audio_id_meaning",
            "📿 Получить практику": "audio_id_practice",
            "🌿 Хочу почувствовать покой": "audio_id_calm",
        }.get(button_text)
        if config_field is None:
            return None
        value = getattr(self._config, config_field, None)
        if isinstance(value, str) and value.strip():
            return value
        return None
