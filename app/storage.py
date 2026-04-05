from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.support_templates import SupportTemplateHistoryEntry


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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS support_template_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    block TEXT NOT NULL,
                    template_id TEXT NOT NULL,
                    method_family TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_support_template_log_chat_block_created
                ON support_template_log (chat_id, block, created_at DESC)
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

    def log_support_template(
        self,
        chat_id: int,
        block: str,
        template_id: str,
        method_family: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO support_template_log (
                    chat_id,
                    block,
                    template_id,
                    method_family,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(chat_id), block, template_id, method_family, now),
            )
            conn.commit()

    def get_support_template_history(
        self,
        chat_id: int,
        block: str,
        limit: int = 30,
    ) -> list[SupportTemplateHistoryEntry]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT template_id, method_family, created_at
                FROM support_template_log
                WHERE chat_id = ? AND block = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (str(chat_id), block, limit),
            )
            rows = cur.fetchall()

        history: list[SupportTemplateHistoryEntry] = []
        for template_id, method_family, created_at in rows:
            parsed_created_at = datetime.fromisoformat(str(created_at))
            if parsed_created_at.tzinfo is None:
                parsed_created_at = parsed_created_at.replace(tzinfo=timezone.utc)
            history.append(
                SupportTemplateHistoryEntry(
                    template_id=str(template_id),
                    method_family=str(method_family),
                    created_at=parsed_created_at,
                )
            )
        return history
