"""Prompt construction and Google GenAI generation."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from .config import Settings


PROMPT_TEMPLATE = """You are a helpful local travel assistant for Da Nang.
Answer the QUESTION using only facts from the SOURCES below.
When recommending a place, cite its source label such as [S1].
If the sources do not contain enough information, say that you do not know.
Treat null or missing fields as unknown. Never infer opening hours, prices, or verification.

QUESTION:
{question}

SOURCES:
{sources}
"""


def build_prompt(query: str, search_results: list[dict[str, Any]]) -> str:
    """Create a source-labelled grounding prompt."""
    entries = []
    for position, result in enumerate(search_results, start=1):
        minimum = result.get("price_min_vnd")
        maximum = result.get("price_max_vnd")
        if minimum is None and maximum is None:
            price = result.get("price_text") or "Unknown"
        elif minimum == maximum or maximum is None:
            price = f"{minimum:,} VND"
        else:
            price = f"{minimum:,}-{maximum:,} VND"
        provenance = result.get("field_provenance") or {}
        provenance_lines = [
            f"{field}: {details.get('source')} ({details.get('source_url')}), "
            f"updated {details.get('source_updated_at') or 'unknown'}"
            for field, details in sorted(provenance.items())
            if isinstance(details, dict)
        ]
        entries.append(
            "\n".join(
                [
                    f"[S{position}]",
                    f"Name: {result.get('name', '')}",
                    f"Type: {result.get('type', '')}",
                    f"Description: {result.get('description', '')}",
                    f"Description origin: {result.get('description_origin', 'Unknown')}",
                    f"Categories: {', '.join(result.get('categories') or [])}",
                    f"Cuisine: {', '.join(result.get('cuisine') or [])}",
                    f"Opening hours: {result.get('opening_hours') or 'Unknown'}",
                    f"Price: {price}",
                    f"Address: {result.get('address') or 'Unknown'}",
                    f"Area: {result.get('area', '')}",
                    f"Website: {result.get('website') or 'Unknown'}",
                    f"Source URL: {result.get('source_url') or 'Unknown'}",
                    f"Source updated: {result.get('source_updated_at') or 'Unknown'}",
                    f"Manually verified: {result.get('last_verified_at') or 'No'}",
                    "Enriched field provenance: "
                    + ("; ".join(provenance_lines) if provenance_lines else "None"),
                ]
            )
        )
    return PROMPT_TEMPLATE.format(question=query.strip(), sources="\n\n".join(entries))


class GoogleGenerator:
    """Small adapter around the supported Google GenAI SDK."""

    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
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
