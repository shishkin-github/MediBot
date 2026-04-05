from pathlib import Path

from app.storage import DialogStorage


def test_storage_get_empty_history(tmp_path: Path) -> None:
    db_path = tmp_path / "medibot.db"
    storage = DialogStorage(str(db_path))
    assert storage.get_history(12345) == ""


def test_storage_upsert_and_read(tmp_path: Path) -> None:
    db_path = tmp_path / "medibot.db"
    storage = DialogStorage(str(db_path))

    storage.upsert_history(12345, "History A")
    assert storage.get_history(12345) == "History A"

    storage.upsert_history(12345, "History B")
    assert storage.get_history(12345) == "History B"


def test_storage_delete_missing_record_does_not_fail(tmp_path: Path) -> None:
    db_path = tmp_path / "medibot.db"
    storage = DialogStorage(str(db_path))

    storage.delete_history(12345)
    assert storage.get_history(12345) == ""


def test_storage_logs_support_templates_in_reverse_chronological_order(tmp_path: Path) -> None:
    db_path = tmp_path / "medibot.db"
    storage = DialogStorage(str(db_path))

    storage.log_support_template(12345, "heavy", "MH_01", "grounding")
    storage.log_support_template(12345, "heavy", "MH_02", "breathing")

    history = storage.get_support_template_history(12345, "heavy")

    assert [entry.template_id for entry in history] == ["MH_02", "MH_01"]
    assert [entry.method_family for entry in history] == ["breathing", "grounding"]


def test_storage_support_template_history_is_scoped_by_block(tmp_path: Path) -> None:
    db_path = tmp_path / "medibot.db"
    storage = DialogStorage(str(db_path))

    storage.log_support_template(12345, "heavy", "MH_01", "grounding")
    storage.log_support_template(12345, "practice", "PR_01", "grounding")

    heavy_history = storage.get_support_template_history(12345, "heavy")
    practice_history = storage.get_support_template_history(12345, "practice")

    assert [entry.template_id for entry in heavy_history] == ["MH_01"]
    assert [entry.template_id for entry in practice_history] == ["PR_01"]
