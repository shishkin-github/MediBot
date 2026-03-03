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

