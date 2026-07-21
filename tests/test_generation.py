from pathlib import Path
from types import SimpleNamespace

import pytest

from localguide_assistant.config import Settings
from localguide_assistant.generation import GoogleGenerator, build_prompt


def make_settings(api_key: str | None) -> Settings:
    return Settings(
        elasticsearch_host="http://example:9200",
        index_name="places",
        embedding_model="embedding-model",
        generation_model="generation-model",
        google_api_key=api_key,
        data_path=Path("data.csv"),
        feedback_db_path=Path("feedback.db"),
        startup_timeout_seconds=1,
        request_timeout_seconds=1,
    )


def test_prompt_labels_sources_for_citations() -> None:
    prompt = build_prompt(
        "Where should I eat?",
        [
            {"name": "First", "type": "eat"},
            {"name": "Second", "type": "eat"},
        ],
    )
    assert "[S1]" in prompt
    assert "[S2]" in prompt
    assert "Where should I eat?" in prompt


def test_generator_fails_early_when_key_is_missing() -> None:
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        GoogleGenerator(make_settings(None))


def test_generator_uses_configured_model() -> None:
    calls = []

    class Models:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(text=" Grounded answer [S1]. ")

    client = SimpleNamespace(models=Models())
    generator = GoogleGenerator(make_settings("test-key"), client=client)

    answer = generator.generate("prompt")

    assert answer == "Grounded answer [S1]."
    assert calls == [{"model": "generation-model", "contents": "prompt"}]
