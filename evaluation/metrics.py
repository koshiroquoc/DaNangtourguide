"""Multi-relevance retrieval metrics and rank-fusion helpers."""

from __future__ import annotations

import random
from typing import Any, Iterable


def first_relevant_rank(
    retrieved_ids: Iterable[str], relevant_ids: set[str], *, cutoff: int
) -> int | None:
    if cutoff <= 0:
        raise ValueError("cutoff must be positive")
    for rank, document_id in enumerate(retrieved_ids, start=1):
        if rank > cutoff:
            break
        if document_id in relevant_ids:
            return rank
    return None


def query_metrics(
    retrieved_ids: list[str], relevant_ids: set[str], *, cutoffs: tuple[int, ...]
) -> dict[str, float]:
    if not relevant_ids:
        raise ValueError("relevant_ids must not be empty")
    metrics: dict[str, float] = {}
    for cutoff in cutoffs:
        rank = first_relevant_rank(retrieved_ids, relevant_ids, cutoff=cutoff)
        metrics[f"hit_rate@{cutoff}"] = 1.0 if rank is not None else 0.0
        metrics[f"mrr@{cutoff}"] = 1.0 / rank if rank is not None else 0.0
    return metrics


def aggregate_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        raise ValueError("Cannot aggregate an empty evaluation")
    keys = rows[0].keys()
    return {key: round(sum(row[key] for row in rows) / len(rows), 4) for key in keys}


def paired_bootstrap_difference(
    challenger: list[float],
    baseline: list[float],
    *,
    iterations: int = 5_000,
    seed: int = 42,
) -> dict[str, float]:
    """Estimate a paired 95% CI for the mean per-query metric difference."""
    if len(challenger) != len(baseline) or not challenger:
        raise ValueError("Paired samples must be non-empty and have equal length")
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    differences = [first - second for first, second in zip(challenger, baseline)]
    generator = random.Random(seed)
    sample_count = len(differences)
    bootstrapped = sorted(
        sum(differences[generator.randrange(sample_count)] for _ in range(sample_count))
        / sample_count
        for _ in range(iterations)
    )
    lower = bootstrapped[int(0.025 * (iterations - 1))]
    upper = bootstrapped[int(0.975 * (iterations - 1))]
    probability_positive = sum(value > 0 for value in bootstrapped) / iterations
    return {
        "mean_difference": round(sum(differences) / sample_count, 4),
        "ci_95_lower": round(lower, 4),
        "ci_95_upper": round(upper, 4),
        "probability_positive": round(probability_positive, 4),
        "iterations": iterations,
    }


def weighted_rank_fusion(
    lexical_hits: Iterable[dict[str, Any]],
    semantic_hits: Iterable[dict[str, Any]],
    *,
    semantic_weight: float,
    rank_constant: int = 60,
    top_k: int = 20,
) -> list[dict[str, Any]]:
    """Weighted RRF without mixing incomparable Elasticsearch score scales."""
    if not 0 <= semantic_weight <= 1:
        raise ValueError("semantic_weight must be between 0 and 1")
    if rank_constant < 0:
        raise ValueError("rank_constant must be non-negative")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    fused: dict[str, dict[str, Any]] = {}
    for weight, label, hits in (
        (1.0 - semantic_weight, "lexical_rank", lexical_hits),
        (semantic_weight, "semantic_rank", semantic_hits),
    ):
        for rank, hit in enumerate(hits, start=1):
            document_id = str(hit["id"])
            item = fused.setdefault(
                document_id,
                {
                    **hit,
                    "lexical_rank": None,
                    "semantic_rank": None,
                    "fusion_score": 0.0,
                },
            )
            item[label] = rank
            item["fusion_score"] += weight / (rank_constant + rank)
    return sorted(
        fused.values(),
        key=lambda item: (-item["fusion_score"], str(item["id"])),
    )[:top_k]
