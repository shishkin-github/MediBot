from app.text_utils import extract_final_model_reply, normalize_ui_text, sanitize_model_text


def test_sanitize_model_text_removes_thinking_artifacts() -> None:
    text = "<think>hidden</think>\nThought: hidden line\nОбычный ответ."
    assert sanitize_model_text(text) == "Обычный ответ."


def test_normalize_ui_text_removes_only_terminal_dot() -> None:
    assert normalize_ui_text("Первая фраза. Вторая фраза.") == "Первая фраза. Вторая фраза"
    assert normalize_ui_text("Вопрос?") == "Вопрос?"
    assert normalize_ui_text("*Финальная фраза.*") == "*Финальная фраза*"


def test_extract_final_model_reply_prefers_final_answer_tag() -> None:
    text = (
        "Role: assistant\n"
        "<final_answer>Приветствую тебя в пространстве тишины и смыслов.</final_answer>\n"
        "extra"
    )
    assert extract_final_model_reply(text) == "Приветствую тебя в пространстве тишины и смыслов."


def test_extract_final_model_reply_strips_prompt_leakage_and_keeps_user_facing_text() -> None:
    leaked = """
*   Role: Master-psychologist-esotericist.
*   Style: Soft, deep, mindful.
*   Draft 1: Приветствую тебя. Я здесь.

"Приветствую тебя в этом пространстве тишины и смыслов. Какая нить твоей души просит внимания сегодня? О чем шепчет твое сердце, когда шум внешнего мира затихает?"
Приветствую тебя в этом пространстве тишины и смыслов. Какая нить твоей души просит внимания сегодня? О чем шепчет твое сердце, когда шум внешнего мира затихает?
"""
    assert (
        normalize_ui_text(leaked)
        == "Приветствую тебя в этом пространстве тишины и смыслов. Какая нить твоей души просит внимания сегодня? О чем шепчет твое сердце, когда шум внешнего мира затихает?"
    )


def test_extract_final_model_reply_keeps_final_practice_block_from_leaked_response() -> None:
    leaked = """
*   Persona: "Voice of the Soul".
*   Tone: Soft, short, deep, pastoral, warm.
*   Internal Monologue:
        "Your tiredness is not a sin."

Твоя усталость — это не слабость и не вина. Это не пустота, которую нужно срочно заполнить делами. Это тихий шепот твоей сути, просящий тишины.

Не ищи самобичевания там, где нужно сострадание. Ты — не инструмент, ты — живое. Позволь себе просто быть, когда нет сил идти.

*Практика: Сделай 3 глубоких вдоха и на выдохе осознанно сбрось напряжение в плечах. Опусти их вниз.*
"""
    assert (
        normalize_ui_text(leaked)
        == "Твоя усталость — это не слабость и не вина. Это не пустота, которую нужно срочно заполнить делами. Это тихий шепот твоей сути, просящий тишины.\n\nНе ищи самобичевания там, где нужно сострадание. Ты — не инструмент, ты — живое. Позволь себе просто быть, когда нет сил идти.\n\n*Практика: Сделай 3 глубоких вдоха и на выдохе осознанно сбрось напряжение в плечах. Опусти их вниз*"
    )
