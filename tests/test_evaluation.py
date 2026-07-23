from evaluation.build_sets import (
    build_discovery_track,
    build_name_lookup_track,
    normalize_text,
)
from evaluation.metrics import (
    aggregate_metrics,
    paired_bootstrap_difference,
    query_metrics,
    weighted_rank_fusion,
)


def test_multi_relevance_metrics_use_first_relevant_rank() -> None:
    metrics = query_metrics(
        ["wrong", "also_wrong", "relevant_b", "relevant_a"],
        {"relevant_a", "relevant_b"},
        cutoffs=(1, 3, 5),
    )

    assert metrics["hit_rate@1"] == 0.0
    assert metrics["hit_rate@3"] == 1.0
    assert metrics["mrr@5"] == 1 / 3


def test_metric_aggregation_averages_queries() -> None:
    result = aggregate_metrics(
        [
            {"hit_rate@1": 1.0, "mrr@5": 1.0},
            {"hit_rate@1": 0.0, "mrr@5": 0.5},
        ]
    )

    assert result == {"hit_rate@1": 0.5, "mrr@5": 0.75}


def test_paired_bootstrap_reports_clear_positive_difference() -> None:
    result = paired_bootstrap_difference(
        [1.0, 0.8, 0.6, 0.9],
        [0.2, 0.1, 0.3, 0.4],
        iterations=500,
        seed=7,
    )

    assert result["mean_difference"] > 0
    assert result["ci_95_lower"] > 0
    assert result["probability_positive"] == 1.0


def test_weighted_rank_fusion_respects_semantic_weight() -> None:
    lexical = [{"id": "lexical"}, {"id": "shared"}]
    semantic = [{"id": "semantic"}, {"id": "shared"}]

    lexical_first = weighted_rank_fusion(
        lexical, semantic, semantic_weight=0.0, rank_constant=60, top_k=3
    )
    semantic_first = weighted_rank_fusion(
        lexical, semantic, semantic_weight=1.0, rank_constant=60, top_k=3
    )

    assert lexical_first[0]["id"] == "lexical"
    assert semantic_first[0]["id"] == "semantic"


def _records():
    records = []
    definitions = (
        ("eat", "cafe", "vietnamese", "Hải Châu"),
        ("eat", "cafe", "vietnamese", "Hải Châu"),
        ("see", "museum", None, "Sơn Trà"),
        ("see", "museum", None, "Sơn Trà"),
        ("stay", "hostel", None, "Ngũ Hành Sơn"),
        ("stay", "hostel", None, "Ngũ Hành Sơn"),
    )
    for position, (place_type, category, cuisine, area) in enumerate(definitions):
        records.append(
            {
                "id": f"place_{position}",
                "type": place_type,
                "name": f"Unique Venue {position}",
                "categories": [category],
                "cuisine": [cuisine] if cuisine else [],
                "area": area,
                "address": None,
                "opening_hours": None,
            }
        )
    return records


def test_discovery_track_has_multiple_relevant_ids_and_no_name_leakage() -> None:
    records = _records()

    queries, rejected = build_discovery_track(records, target_count=6)

    assert len(queries) == 6
    assert rejected == {}
    assert all(query["relevance_count"] >= 2 for query in queries)
    names = {record["id"]: normalize_text(record["name"]) for record in records}
    for query in queries:
        normalized_query = normalize_text(query["query"])
        assert all(
            names[document_id] not in normalized_query
            for document_id in query["relevant_ids"]
        )


def test_name_lookup_track_is_reported_separately() -> None:
    queries = build_name_lookup_track(_records(), target_count=3)

    assert len(queries) == 3
    assert all(query["track"] == "name_lookup" for query in queries)
    assert all(query["constraint_kind"] == "venue_name" for query in queries)
