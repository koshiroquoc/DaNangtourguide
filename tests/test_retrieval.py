from pathlib import Path
from typing import Any

from localguide_assistant.config import Settings
from localguide_assistant.retrieval import PlaceRetriever, reciprocal_rank_fusion


def make_settings() -> Settings:
    return Settings(
        elasticsearch_host="http://example:9200",
        index_name="places",
        embedding_model="test-model",
        generation_model="test-generation-model",
        google_api_key="test-key",
        data_path=Path("data.csv"),
        feedback_db_path=Path("feedback.db"),
        startup_timeout_seconds=1,
        request_timeout_seconds=1,
    )


class FakeElasticsearch:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def search(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "hits": {
                "hits": [
                    {
                        "_score": 3.5,
                        "_source": {
                            "id": "eat_001",
                            "name": "Example Place",
                            "type": "eat",
                        },
                    }
                ]
            }
        }


def test_rrf_rewards_documents_present_in_both_rankings() -> None:
    lexical = [{"id": "a", "score": 8.0}, {"id": "b", "score": 7.0}]
    semantic = [{"id": "b", "score": 1.8}, {"id": "c", "score": 1.7}]

    results = reciprocal_rank_fusion(
        lexical, semantic, rank_constant=60, top_k=3
    )

    assert [result["id"] for result in results] == ["b", "a", "c"]
    assert results[0]["lexical_score"] == 7.0
    assert results[0]["semantic_score"] == 1.8


def test_bm25_uses_raw_query_and_filter_context() -> None:
    fake_es = FakeElasticsearch()
    retriever = PlaceRetriever(make_settings(), es_client=fake_es)

    results = retriever.bm25_search(
        "restaurants not spicy under $30", top_k=3, type_filter="eat"
    )

    call = fake_es.calls[0]
    multi_match = call["query"]["bool"]["must"][0]["multi_match"]
    assert multi_match["query"] == "restaurants not spicy under $30"
    assert call["query"]["bool"]["filter"] == [{"term": {"type": "eat"}}]
    assert call["source_includes"] == [
        "id",
        "name",
        "description",
        "time",
        "price",
        "location",
        "area",
        "note",
        "type",
    ]
    assert results[0]["id"] == "eat_001"


def test_invalid_type_is_rejected_before_search() -> None:
    fake_es = FakeElasticsearch()
    retriever = PlaceRetriever(make_settings(), es_client=fake_es)

    try:
        retriever.bm25_search("somewhere nice", type_filter="shop")
    except ValueError as error:
        assert "Unknown place type" in str(error)
    else:
        raise AssertionError("Expected invalid type to be rejected")
    assert fake_es.calls == []
