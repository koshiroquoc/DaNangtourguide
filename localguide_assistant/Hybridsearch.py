"""Compatibility API backed by the side-effect-free application modules."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from localguide_assistant.generation import build_prompt
from localguide_assistant.logging_db import get_feedback_store
from localguide_assistant.retrieval import get_retriever, reciprocal_rank_fusion
from localguide_assistant.service import get_rag_service


def bm25_search(
    query: str, top_k: int = 5, type_filter: str | None = None
) -> list[dict[str, Any]]:
    return get_retriever().bm25_search(
        query, top_k=top_k, type_filter=type_filter
    )


def vector_search(
    query: str, top_k: int = 5, type_filter: str | None = None
) -> list[dict[str, Any]]:
    return get_retriever().vector_search(
        query, top_k=top_k, type_filter=type_filter
    )


def hybrid_search(
    query: str,
    top_k: int = 5,
    k_rrf: int = 60,
    type_filter: str | None = None,
) -> list[dict[str, Any]]:
    return get_retriever().hybrid_search(
        query,
        top_k=top_k,
        rank_constant=k_rrf,
        type_filter=type_filter,
    )


def rag(query: str, type_filter: str | None = None, top_k: int = 3) -> str:
    return get_rag_service().ask(
        query, type_filter=type_filter, top_k=top_k
    ).answer


def log_feedback(question: str, answer: str, feedback: str) -> None:
    """Compatibility helper for older Streamlit versions."""
    import uuid

    get_feedback_store().record(
        request_id=str(uuid.uuid4()),
        question=question,
        answer=answer,
        feedback=feedback,
        sources=[],
    )


__all__ = [
    "bm25_search",
    "build_prompt",
    "hybrid_search",
    "log_feedback",
    "rag",
    "reciprocal_rank_fusion",
    "vector_search",
]
