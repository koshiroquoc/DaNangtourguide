"""Environment-backed configuration for the application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_local_env() -> None:
    """Load a developer .env file without overriding real environment values."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def _positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class Settings:
    """Runtime settings with safe local-development defaults."""

    elasticsearch_host: str
    index_name: str
    embedding_model: str
    generation_model: str
    google_api_key: str | None
    data_path: Path
    feedback_db_path: Path
    startup_timeout_seconds: int
    request_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        _load_local_env()
        return cls(
            elasticsearch_host=os.getenv(
                "ELASTICSEARCH_HOST", "http://localhost:9200"
            ).rstrip("/"),
            index_name=os.getenv("ELASTICSEARCH_INDEX", "places_danang"),
            embedding_model=os.getenv(
                "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
            ),
            generation_model=os.getenv("GENERATION_MODEL", "gemma-3-12b-it"),
            google_api_key=os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY"),
            data_path=Path(
                os.getenv("DATA_PATH", str(PROJECT_ROOT / "Data/data_danang_ok.csv"))
            ).expanduser(),
            feedback_db_path=Path(
                os.getenv(
                    "FEEDBACK_DB_PATH", str(PROJECT_ROOT / "grafana_data/chat_log.db")
                )
            ).expanduser(),
            startup_timeout_seconds=_positive_int("STARTUP_TIMEOUT_SECONDS", 60),
            request_timeout_seconds=_positive_int("REQUEST_TIMEOUT_SECONDS", 30),
        )
