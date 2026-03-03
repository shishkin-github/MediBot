from app.router import (
    BUTTON_TO_INSTRUCTION,
    SAFE_FALLBACK_MESSAGE,
    build_master_user_prompt,
    compose_history,
    detect_route,
)


def test_detect_route_reset_start() -> None:
    assert detect_route("/start") == "reset"


def test_detect_route_reset_stop_dialog() -> None:
    assert detect_route("🛑 Завершить диалог с мастером") == "reset"


def test_detect_route_buttons() -> None:
    for button in BUTTON_TO_INSTRUCTION:
        assert detect_route(button) == "button"


def test_detect_route_master_fallback() -> None:
    assert detect_route("любой другой текст") == "master"
    assert detect_route("🧙‍♂️ Поговорить с Мастером") == "master"


def test_build_master_user_prompt() -> None:
    prompt = build_master_user_prompt("User: A\nMaster: B", "Новый вопрос")
    assert "Предыдущая переписка:" in prompt
    assert "User: A\nMaster: B" in prompt
    assert "Текущее сообщение пользователя:Новый вопрос" in prompt


def test_compose_history_without_existing() -> None:
    history = compose_history("", "Привет", "Ответ")
    assert history == "User: Привет\nMaster: Ответ"


def test_compose_history_with_existing() -> None:
    history = compose_history("User: Старый\nMaster: Ответ", "Новый", "Новый ответ")
    assert history == "User: Старый\nMaster: Ответ\nUser: Новый\nMaster: Новый ответ"


def test_fallback_message_is_non_empty() -> None:
    assert SAFE_FALLBACK_MESSAGE.strip() != ""

