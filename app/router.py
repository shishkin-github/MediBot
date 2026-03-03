from __future__ import annotations

import logging
from typing import Literal

from app.config import Config
from app.gemini_api import GeminiAPI
from app.storage import DialogStorage
from app.telegram_api import TelegramAPI

RouteName = Literal["reset", "button", "master"]

RESET_TEXTS = {
    "/start",
    "🛑 Завершить диалог с мастером",
}

MAIN_MENU_TEXT = "Вы вернулись в главное меню. Выберите, что чувствует ваша душа"

MAIN_MENU_MARKUP = {
    "keyboard": [
        [{"text": "💭 Мне тяжело"}, {"text": "🌫 Я потерял себя"}],
        [{"text": "💔 Я ничего не хочу"}, {"text": "🌿 Хочу почувствовать покой"}],
        [{"text": "💫 Хочу вспомнить смысл"}, {"text": "📿 Получить практику"}],
        [{"text": "🧙‍♂️ Поговорить с Мастером"}],
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

VOICE_SYSTEM_PROMPT = (
    "Ты — “Голос Души”. Отвечай мягко, коротко и глубоко. "
    "Стиль — пасторский, тёплый. Ты не учишь, а возвращаешь к себе"
)

MASTER_SYSTEM_PROMPT = (
    "Ты — Мастер-психолог-эзотерик. Твой стиль — мягкий, глубокий, осознанный. "
    "Веди к осознанию через вопросы и метафоры. Ответы 2-5 фраз"
)

SAFE_FALLBACK_MESSAGE = (
    "Сейчас мне трудно подобрать слова. "
    "Напиши мне ещё раз через несколько секунд."
)

BUTTON_TO_INSTRUCTION: dict[str, str] = {
    "💭 Мне тяжело": (
        "Инструкция: Ответь человеку, которому эмоционально тяжело. "
        "Дай дыхание, опору, ощущение присутствия рядом. "
        "Пример тона: «Не убегай от того, что чувствуешь. Просто дыши рядом со мной. "
        "Ты не один.» В конце обязательно предложи практику: "
        "1. Медленный вдох. 2. Внимание в область груди. 3. Скажи: “Я здесь”."
    ),
    "🌫 Я потерял себя": (
        "Инструкция: Дай человеку почувствовать, что он не потерян — он просто устал. "
        "Пример тона: «Ты не потерял себя. Ты просто давно не слушал своё сердце. "
        "Оно тихое… но оно здесь.» В конце предложи практику: "
        "Положи ладонь на грудь и подожди 5 секунд."
    ),
    "💔 Я ничего не хочу": (
        "Инструкция: Дай разрешение быть в состоянии усталости. Сними вину. "
        "Пример тона: «Когда нет желания — это не пустота. Это душа просит отдыха.» "
        "В конце предложи практику: Сделай 3 сброса напряжения в плечах."
    ),
    "🌿 Хочу почувствовать покой": (
        "Инструкция: Дай образ покоя и лёгкую телесную практику. "
        "Пример тона: «Положи руку на сердце. Сделай один тёплый вдох. "
        "Вот это — твой покой. Он никогда не уходил.»"
    ),
    "💫 Хочу вспомнить смысл": (
        "Инструкция: Посели искру. Не объясняй, не рассуждай — дай почувствовать. "
        "Пример тона: «Закрой глаза и спроси себя: “Что во мне ещё живое?” "
        "Это и есть начало смысла.» В конце предложи практику: "
        "Записать одно слово, которое откликается."
    ),
    "📿 Получить практику": (
        "Инструкция: Дай короткую практику (до 40 секунд). "
        "Должно быть действие, не теория. Пример структуры: "
        "Мини-практика “Возврат к центру”. 1. Почувствуй ступни. "
        "2. Вдох — внимание под грудью. 3. Выдох — отпусти всё ненужное. "
        "4. Скажи: “Я здесь.”"
    ),
}

BUTTON_TO_AUDIO_FIELD = {
    "💭 Мне тяжело": "audio_id_heavy",
    "🌫 Я потерял себя": "audio_id_lost",
    "💔 Я ничего не хочу": "audio_id_nothing",
    "💫 Хочу вспомнить смысл": "audio_id_meaning",
    "📿 Получить практику": "audio_id_practice",
    "🌿 Хочу почувствовать покой": "audio_id_calm",
}


def detect_route(text: str) -> RouteName:
    if text in RESET_TEXTS:
        return "reset"
    if text in BUTTON_TO_INSTRUCTION:
        return "button"
    return "master"


def build_master_user_prompt(history: str, current_text: str) -> str:
    return (
        f"Предыдущая переписка:\n{history}\n\n"
        f"Текущее сообщение пользователя:{current_text}"
    )


def compose_history(existing_history: str, user_text: str, master_reply: str) -> str:
    new_block = f"User: {user_text}\nMaster: {master_reply}"
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
        if route == "reset":
            self._handle_reset(chat_id)
            return
        if route == "button":
            self._handle_button(chat_id, text)
            return
        self._handle_master(chat_id, text)

    def _handle_reset(self, chat_id: int) -> None:
        self._telegram.send_message(
            chat_id,
            MAIN_MENU_TEXT,
            reply_markup=MAIN_MENU_MARKUP,
        )
        self._storage.delete_history(chat_id)

    def _handle_button(self, chat_id: int, button_text: str) -> None:
        instruction = BUTTON_TO_INSTRUCTION[button_text]
        reply = self._ask_gemini(
            system_prompt=VOICE_SYSTEM_PROMPT,
            user_prompt=instruction,
            context_name="button_reply",
        )
        self._telegram.send_message(chat_id, reply)

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
        history = self._storage.get_history(chat_id)
        prompt = build_master_user_prompt(history, user_text)
        reply = self._ask_gemini(
            system_prompt=MASTER_SYSTEM_PROMPT,
            user_prompt=prompt,
            context_name="master_reply",
        )
        updated_history = compose_history(history, user_text, reply)
        self._storage.upsert_history(chat_id, updated_history)
        self._telegram.send_message(
            chat_id=chat_id,
            text=reply,
            reply_markup=STOP_DIALOG_MARKUP,
        )

    def _ask_gemini(self, system_prompt: str, user_prompt: str, context_name: str) -> str:
        try:
            return self._gemini.generate_text(system_prompt, user_prompt)
        except Exception:
            self._logger.exception("Gemini generation failed in %s.", context_name)
            return SAFE_FALLBACK_MESSAGE

    def _get_audio_file_id(self, button_text: str) -> str | None:
        config_field = BUTTON_TO_AUDIO_FIELD.get(button_text)
        if config_field is None:
            return None
        value = getattr(self._config, config_field, None)
        if isinstance(value, str) and value.strip():
            return value
        return None

