import random
from datetime import datetime, timedelta, timezone

from app.support_templates import (
    SUPPORT_TEMPLATES,
    SupportTemplateHistoryEntry,
    choose_support_template,
)


def _entry(template_id: str, method_family: str, days_ago: int) -> SupportTemplateHistoryEntry:
    return SupportTemplateHistoryEntry(
        template_id=template_id,
        method_family=method_family,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )


def test_choose_support_template_avoids_recent_ids_and_last_method_and_cooldown() -> None:
    history = [
        _entry("MH_01", "grounding", 1),
        _entry("MH_02", "breathing", 2),
        _entry("MH_03", "self_compassion", 3),
        _entry("MH_04", "attention_shift", 4),
        _entry("MH_05", "body_regulation", 5),
        _entry("MH_06", "grounding", 6),
        _entry("MH_07", "journaling", 7),
    ]

    template = choose_support_template(
        block="heavy",
        history=history,
        rng=random.Random(0),
        now=datetime.now(timezone.utc),
    )

    assert template.id not in {"MH_01", "MH_02", "MH_03", "MH_04", "MH_05", "MH_06", "MH_07"}
    assert template.method_family != "grounding"


def test_choose_support_template_relaxes_to_last_three_when_pool_is_empty() -> None:
    now = datetime.now(timezone.utc)
    history = [
        SupportTemplateHistoryEntry(
            template_id=template.id,
            method_family=template.method_family,
            created_at=now - timedelta(days=1),
        )
        for template in SUPPORT_TEMPLATES["practice"]
    ]

    chosen = choose_support_template(
        block="practice",
        history=history,
        rng=random.Random(0),
        now=now,
    )

    recent_three = {entry.template_id for entry in history[:3]}
    assert chosen.id not in recent_three


def test_support_template_texts_are_normalized_for_ui() -> None:
    for templates in SUPPORT_TEMPLATES.values():
        for template in templates:
            assert not template.text.endswith(".")
