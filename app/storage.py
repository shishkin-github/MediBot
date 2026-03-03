from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class DialogStorage:
    def __init__(self, sqlite_path: str) -> None:
        self._db_path = Path(sqlite_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dialog_memory (
                    chat_id TEXT PRIMARY KEY,
                    history TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def get_history(self, chat_id: int) -> str:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT history FROM dialog_memory WHERE chat_id = ?",
                (str(chat_id),),
            )
            row = cur.fetchone()
            if row is None:
                return ""
            return str(row[0])

    def upsert_history(self, chat_id: int, history: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO dialog_memory (chat_id, history, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    history = excluded.history,
                    updated_at = excluded.updated_at
                """,
                (str(chat_id), history, now),
            )
            conn.commit()

    def delete_history(self, chat_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM dialog_memory WHERE chat_id = ?",
                (str(chat_id),),
            )
            conn.commit()

