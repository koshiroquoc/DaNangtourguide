from pathlib import Path

import pytest

from localguide_assistant.config import PROJECT_ROOT, Settings


def test_settings_use_local_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ELASTICSEARCH_HOST",
        "ELASTICSEARCH_INDEX",
        "EMBEDDING_MODEL",
        "GENERATION_MODEL",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "DATA_PATH",
        "FEEDBACK_DB_PATH",
        "STARTUP_TIMEOUT_SECONDS",
        "REQUEST_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env()

    assert settings.elasticsearch_host == "http://localhost:9200"
    assert settings.index_name == "places_danang_v2"
    assert (
        settings.data_path == PROJECT_ROOT / "Data/processed/places_enriched_v2.jsonl"
    )
    assert settings.feedback_db_path == PROJECT_ROOT / "grafana_data/chat_log.db"


def test_settings_accept_container_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ELASTICSEARCH_HOST", "http://elasticsearch:9200/")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("FEEDBACK_DB_PATH", str(tmp_path / "feedback.db"))

    settings = Settings.from_env()

    assert settings.elasticsearch_host == "http://elasticsearch:9200"
    assert settings.google_api_key == "test-key"
    assert settings.feedback_db_path == tmp_path / "feedback.db"


def test_settings_reject_non_positive_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STARTUP_TIMEOUT_SECONDS", "0")
    with pytest.raises(ValueError, match="STARTUP_TIMEOUT_SECONDS"):
        Settings.from_env()
