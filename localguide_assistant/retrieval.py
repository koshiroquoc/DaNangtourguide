"""Side-effect-free lexical, dense, and hybrid retrieval."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable

from elasticsearch import Elasticsearch

from .config import Settings


SOURCE_FIELDS = [
    "schema_version",
    "id",
    "name",
    "name_vi",
    "name_en",
    "description",
    "description_origin",
    "address",
    "area",
    "latitude",
    "longitude",
    "categories",
    "cuisine",
    "opening_hours",
    "phone",
    "website",
    "price_min_vnd",
    "price_max_vnd",
    "price_currency",
    "source",
    "source_url",
    "source_license",
    "source_updated_at",
    "retrieved_at",
    "last_verified_at",
    "is_synthetic",
    "type",
]
VALID_TYPES = {"eat", "see", "stay"}


def _validate_query(query: str) -> str:
    query = query.strip()
    if not query:
        raise ValueError("Query must not be empty")
    return query


def _type_filter(type_filter: str | None) -> dict[str, Any] | None:
    if type_filter is None:
        return None
    if type_filter not in VALID_TYPES:
        raise ValueError(f"Unknown place type: {type_filter}")
    return {"term": {"type": type_filter}}


def _format_hits(response: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for hit in response["hits"]["hits"]:
        source = hit["_source"]
        result = {field: source.get(field) for field in SOURCE_FIELDS}
        result["score"] = hit.get("_score", 0.0)
        results.append(result)
    return results


def reciprocal_rank_fusion(
    lexical_hits: Iterable[dict[str, Any]],
    semantic_hits: Iterable[dict[str, Any]],
    *,
    rank_constant: int = 60,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Fuse rankings without mixing incompatible raw score scales."""
    if rank_constant < 0:
        raise ValueError("rank_constant must be non-negative")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    fused: dict[str, dict[str, Any]] = {}
    for score_name, hits in (
        ("lexical_score", lexical_hits),
        ("semantic_score", semantic_hits),
    ):
        for rank, hit in enumerate(hits, start=1):
            doc_id = str(hit["id"])
            item = fused.setdefault(
                doc_id,
                {
                    **hit,
                    "lexical_score": 0.0,
                    "semantic_score": 0.0,
                    "rrf_score": 0.0,
                },
            )
            item[score_name] = float(hit.get("score", 0.0))
            item["rrf_score"] += 1.0 / (rank_constant + rank)

    return sorted(fused.values(), key=lambda item: item["rrf_score"], reverse=True)[
        :top_k
    ]


class PlaceRetriever:
    """Retrieve places while lazily creating expensive clients and models."""

    def __init__(
        self,
        settings: Settings,
        *,
        es_client: Elasticsearch | None = None,
        embedding_model: Any | None = None,
    ) -> None:
        self.settings = settings
        self._es_client = es_client
        self._embedding_model = embedding_model

    @property
    def es(self) -> Elasticsearch:
        if self._es_client is None:
            self._es_client = Elasticsearch(
                self.settings.elasticsearch_host,
                request_timeout=self.settings.request_timeout_seconds,
            )
        return self._es_client

    @property
    def embedding_model(self) -> Any:
        if self._embedding_model is None:
            from sentence_transformers import SentenceTransformer

            self._embedding_model = SentenceTransformer(self.settings.embedding_model)
        return self._embedding_model

    def bm25_search(
        self, query: str, *, top_k: int = 5, type_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Run BM25 against the natural-language query."""
        query = _validate_query(query)
        filters = [filter_query] if (filter_query := _type_filter(type_filter)) else []
        response = self.es.search(
            index=self.settings.index_name,
            size=top_k,
            query={
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": [
                                    "name^3",
                                    "name_vi^3",
                                    "name_en^3",
                                    "description^2",
                                    "address",
                                    "categories^2",
                                    "cuisine^2",
                                    "full_text",
                                ],
                                "operator": "or",
                                "type": "most_fields",
                            }
                        }
                    ],
                    "filter": filters,
                }
            },
            source_includes=SOURCE_FIELDS,
        )
        return _format_hits(response)

    def vector_search(
        self, query: str, *, top_k: int = 5, type_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Run the existing exact cosine search with an unmodified query."""
        query = _validate_query(query)
        filter_query = _type_filter(type_filter)
        inner_query: dict[str, Any]
        if filter_query:
            inner_query = {"bool": {"filter": [filter_query]}}
        else:
            inner_query = {"match_all": {}}

        query_vector = self.embedding_model.encode(query).tolist()
        response = self.es.search(
            index=self.settings.index_name,
            size=top_k,
            query={
                "script_score": {
                    "query": inner_query,
                    "script": {
                        "source": (
                            "cosineSimilarity(params.query_vector, "
                            "'vector_search') + 1.0"
                        ),
                        "params": {"query_vector": query_vector},
                    },
                }
            },
            source_includes=SOURCE_FIELDS,
        )
        return _format_hits(response)

    def hybrid_search(
        self,
        query: str,
        *,
        top_k: int = 5,
        rank_constant: int = 60,
        type_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Combine lexical and semantic candidates with RRF."""
        candidate_count = max(top_k * 2, top_k)
        lexical = self.bm25_search(
            query, top_k=candidate_count, type_filter=type_filter
        )
        semantic = self.vector_search(
            query, top_k=candidate_count, type_filter=type_filter
        )
        return reciprocal_rank_fusion(
            lexical, semantic, rank_constant=rank_constant, top_k=top_k
        )


@lru_cache(maxsize=1)
def get_retriever() -> PlaceRetriever:
    """Return one process-local retriever without doing work at import time."""
    return PlaceRetriever(Settings.from_env())
