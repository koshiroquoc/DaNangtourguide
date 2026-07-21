"""Application service that orchestrates retrieval and generation."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Protocol


class Retriever(Protocol):
    def hybrid_search(
        self, query: str, *, top_k: int, type_filter: str | None
    ) -> list[dict[str, Any]]: ...


class Generator(Protocol):
    def generate(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class RAGResponse:
    request_id: str
    question: str
    answer: str
    sources: list[dict[str, Any]]
    latency_ms: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RAGService:
    def __init__(self, retriever: Retriever, generator: Generator) -> None:
        self.retriever = retriever
        self.generator = generator

    def ask(
        self, query: str, *, type_filter: str | None = None, top_k: int = 3
    ) -> RAGResponse:
        from .generation import build_prompt

        started = time.perf_counter()
        retrieval_started = time.perf_counter()
        sources = self.retriever.hybrid_search(
            query, top_k=top_k, type_filter=type_filter
        )
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1000

        generation_started = time.perf_counter()
        answer = self.generator.generate(build_prompt(query, sources))
        generation_ms = (time.perf_counter() - generation_started) * 1000

        return RAGResponse(
            request_id=str(uuid.uuid4()),
            question=query.strip(),
            answer=answer,
            sources=sources,
            latency_ms={
                "retrieval": round(retrieval_ms, 2),
                "generation": round(generation_ms, 2),
                "total": round((time.perf_counter() - started) * 1000, 2),
            },
        )


def get_rag_service() -> RAGService:
    from .generation import get_generator
    from .retrieval import get_retriever

    return RAGService(get_retriever(), get_generator())
