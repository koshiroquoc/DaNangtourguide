"""Prompt construction and Google GenAI generation."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from .config import Settings


PROMPT_TEMPLATE = """You are a helpful local travel assistant for Da Nang.
Answer the QUESTION using only facts from the SOURCES below.
When recommending a place, cite its source label such as [S1].
If the sources do not contain enough information, say that you do not know.

QUESTION:
{question}

SOURCES:
{sources}
"""


def build_prompt(query: str, search_results: list[dict[str, Any]]) -> str:
    """Create a source-labelled grounding prompt."""
    entries = []
    for position, result in enumerate(search_results, start=1):
        entries.append(
            "\n".join(
                [
                    f"[S{position}]",
                    f"Name: {result.get('name', '')}",
                    f"Type: {result.get('type', '')}",
                    f"Description: {result.get('description', '')}",
                    f"Time: {result.get('time', '')}",
                    f"Price: {result.get('price', '')}",
                    f"Location: {result.get('location', '')}",
                    f"Area: {result.get('area', '')}",
                    f"Note: {result.get('note', '')}",
                ]
            )
        )
    return PROMPT_TEMPLATE.format(question=query.strip(), sources="\n\n".join(entries))


class GoogleGenerator:
    """Small adapter around the supported Google GenAI SDK."""

    def __init__(
        self, settings: Settings, *, client: Any | None = None
    ) -> None:
        if not settings.google_api_key:
            raise RuntimeError(
                "Missing GOOGLE_API_KEY (or GEMINI_API_KEY). Add it to .env "
                "or the runtime environment."
            )
        self.settings = settings
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.settings.google_api_key)
        return self._client

    def generate(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.settings.generation_model,
            contents=prompt,
        )
        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("The generation model returned an empty response")
        return text.strip()


@lru_cache(maxsize=1)
def get_generator() -> GoogleGenerator:
    return GoogleGenerator(Settings.from_env())
