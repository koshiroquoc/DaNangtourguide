"""Local feedback persistence. Request tracing is added in a later phase."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings


class FeedbackStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                request_id TEXT PRIMARY KEY,
                timestamp_utc TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                feedback TEXT NOT NULL CHECK (feedback IN ('like', 'dislike')),
                source_ids_json TEXT NOT NULL
            )
            """
        )
        return connection

    def record(
        self,
        *,
        request_id: str,
        question: str,
        answer: str,
        feedback: str,
        sources: list[dict[str, Any]],
    ) -> None:
        if feedback not in {"like", "dislike"}:
            raise ValueError("feedback must be 'like' or 'dislike'")
        source_ids = [source.get("id") for source in sources]
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO feedback (
                    request_id, timestamp_utc, question, answer, feedback,
                    source_ids_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    datetime.now(timezone.utc).isoformat(),
                    question,
                    answer,
                    feedback,
                    json.dumps(source_ids, ensure_ascii=False),
                ),
            )


def get_feedback_store() -> FeedbackStore:
    return FeedbackStore(Settings.from_env().feedback_db_path)
