import json
import sqlite3

import pytest

from localguide_assistant.logging_db import FeedbackStore


def test_feedback_is_stored_once_by_request_id(tmp_path) -> None:
    database_path = tmp_path / "feedback.db"
    store = FeedbackStore(database_path)

    store.record(
        request_id="request-1",
        question="Where should I eat?",
        answer="Try this place [S1].",
        feedback="like",
        sources=[{"id": "eat_001"}],
    )

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT request_id, feedback, source_ids_json FROM feedback"
        ).fetchone()
    assert row == ("request-1", "like", json.dumps(["eat_001"]))


def test_feedback_value_is_validated(tmp_path) -> None:
    store = FeedbackStore(tmp_path / "feedback.db")
    with pytest.raises(ValueError, match="feedback"):
        store.record(
            request_id="request-1",
            question="question",
            answer="answer",
            feedback="maybe",
            sources=[],
        )
