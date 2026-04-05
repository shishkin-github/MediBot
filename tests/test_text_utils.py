from app.text_utils import normalize_ui_text, sanitize_model_text


def test_sanitize_model_text_removes_thinking_artifacts() -> None:
    text = "<think>hidden</think>\nThought: hidden line\nОбычный ответ."
    assert sanitize_model_text(text) == "Обычный ответ."


def test_normalize_ui_text_removes_only_terminal_dot() -> None:
    assert normalize_ui_text("Первая фраза. Вторая фраза.") == "Первая фраза. Вторая фраза"
    assert normalize_ui_text("Вопрос?") == "Вопрос?"
