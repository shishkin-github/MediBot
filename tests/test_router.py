from app.router import (
    MAIN_MENU_TEXT,
    MASTER_ENTRY_TEXT,
    SAFE_FALLBACK_MESSAGE,
    build_master_user_prompt,
    compose_history,
    detect_route,
    is_crisis_message,
)
from app.support_templates import BUTTON_TEMPLATE_BLOCKS


def test_detect_route_crisis() -> None:
    assert detect_route("Я хочу умереть") == "crisis"


def test_detect_route_reset_start() -> None:
    assert detect_route("/start") == "reset"


def test_detect_route_reset_stop_dialog() -> None:
    assert detect_route("🛑 Завершить диалог с мастером") == "reset"


def test_detect_route_buttons() -> None:
    for button in BUTTON_TEMPLATE_BLOCKS:
        assert detect_route(button) == "button"


def test_detect_route_master_fallback() -> None:
    assert detect_route("любой другой текст") == "master"
    assert detect_route(MASTER_ENTRY_TEXT) == "master"


def test_is_crisis_message_false_for_regular_message() -> None:
    assert is_crisis_message("Мне тревожно, но я хочу просто выговориться") is False


def test_build_master_user_prompt() -> None:
    prompt = build_master_user_prompt("User: A\nMaster: B", "Новый вопрос")
    assert "Предыдущая переписка:" in prompt
    assert "User: A\nMaster: B" in prompt
    assert "Текущее сообщение пользователя:\nНовый вопрос" in prompt


def test_build_master_user_prompt_uses_placeholder_for_empty_history() -> None:
    prompt = build_master_user_prompt("", "Новый вопрос")
    assert "Истории пока нет" in prompt


def test_compose_history_without_existing() -> None:
    history = compose_history("", "Привет", "Ответ.")
    assert history == "User: Привет\nMaster: Ответ"


def test_compose_history_with_existing() -> None:
    history = compose_history("User: Старый\nMaster: Ответ", "Новый", "Новый ответ.")
    assert history == "User: Старый\nMaster: Ответ\nUser: Новый\nMaster: Новый ответ"


def test_fallback_message_is_non_empty_and_without_terminal_dot() -> None:
    assert SAFE_FALLBACK_MESSAGE.strip() != ""
    assert not SAFE_FALLBACK_MESSAGE.endswith(".")


def test_main_menu_text_without_terminal_dot() -> None:
    assert not MAIN_MENU_TEXT.endswith(".")
