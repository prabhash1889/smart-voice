from __future__ import annotations

import sqlite3
import os
from pathlib import Path

try:
    from platformdirs import user_data_dir
except ModuleNotFoundError:
    user_data_dir = None

from smartvoice.core.models import WorkflowResult


class HistoryStore:
    def __init__(self, db_path: Path | None = None, limit: int = 100) -> None:
        self.db_path = db_path or self._default_db_path()
        self.limit = limit
        self._init_db()

    def _default_db_path(self) -> Path:
        if user_data_dir is not None:
            return Path(user_data_dir("SmartVoice", "SmartVoice")) / "history.sqlite3"
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "SmartVoice" / "history.sqlite3"

    def _connect(self) -> sqlite3.Connection:
        self._ensure_parent()
        return sqlite3.connect(self.db_path)

    def _ensure_parent(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            self.db_path = Path.cwd() / ".smartvoice" / "history.sqlite3"
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    final_text TEXT NOT NULL,
                    audio_duration_ms INTEGER NOT NULL,
                    error TEXT
                )
                """
            )

    def save(self, result: WorkflowResult) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO transcripts (
                    created_at, mode, raw_text, final_text, audio_duration_ms, error
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    result.created_at.isoformat(),
                    result.mode,
                    result.raw_text,
                    result.final_text,
                    result.audio_duration_ms,
                    result.error,
                ),
            )
            conn.execute(
                """
                DELETE FROM transcripts
                WHERE id NOT IN (
                    SELECT id FROM transcripts ORDER BY id DESC LIMIT ?
                )
                """,
                (self.limit,),
            )

    def recent(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM transcripts ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_success(self) -> dict | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM transcripts
                WHERE error IS NULL AND final_text != ''
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        return dict(row) if row else None

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM transcripts")
