"""Idempotent Elasticsearch indexing command."""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from elasticsearch import Elasticsearch, helpers

from .config import Settings


INDEX_MAPPING: dict[str, Any] = {
    "mappings": {
        "properties": {
            "type": {"type": "keyword"},
            "name": {"type": "text"},
            "description": {"type": "text"},
            "time": {"type": "keyword"},
            "price": {"type": "keyword"},
            "location": {"type": "text"},
            "area": {"type": "keyword"},
            "note": {"type": "text"},
            "id": {"type": "keyword"},
            "full_text": {"type": "text"},
            "vector_search": {
                "type": "dense_vector",
                "dims": 384,
                "index": True,
                "similarity": "cosine",
            },
        }
    }
}


def create_client(settings: Settings) -> Elasticsearch:
    return Elasticsearch(
        settings.elasticsearch_host,
        request_timeout=settings.request_timeout_seconds,
    )


def wait_until_ready(
    client: Elasticsearch, *, timeout_seconds: int, poll_seconds: float = 1.0
) -> None:
    """Wait for Elasticsearch so startup does not race the container."""
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if client.ping():
                return
        except Exception as error:  # Connection errors vary by client transport.
            last_error = error
        time.sleep(poll_seconds)
    detail = f": {last_error}" if last_error else ""
    raise RuntimeError(
        f"Elasticsearch was not ready within {timeout_seconds} seconds{detail}"
    )


def index_is_current(
    client: Elasticsearch, *, index_name: str, expected_count: int
) -> bool:
    if not client.indices.exists(index=index_name):
        return False
    return int(client.count(index=index_name)["count"]) == expected_count


def index_places(
    settings: Settings,
    *,
    skip_if_exists: bool = False,
    batch_size: int = 64,
) -> int:
    """Embed all atomic place records in batches and bulk upsert them."""
    import pandas as pd
    from sentence_transformers import SentenceTransformer

    if not settings.data_path.exists():
        raise FileNotFoundError(f"Dataset not found: {settings.data_path}")

    dataframe = pd.read_csv(settings.data_path)
    required = {
        "id",
        "type",
        "name",
        "description",
        "time",
        "price",
        "location",
        "area",
        "note",
        "full_text",
    }
    missing = sorted(required - set(dataframe.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing)}")
    if dataframe["id"].duplicated().any():
        raise ValueError("Dataset contains duplicate place IDs")

    client = create_client(settings)
    wait_until_ready(client, timeout_seconds=settings.startup_timeout_seconds)

    if skip_if_exists and index_is_current(
        client, index_name=settings.index_name, expected_count=len(dataframe)
    ):
        print(
            f"Index '{settings.index_name}' already contains {len(dataframe)} places; "
            "skipping indexing."
        )
        return 0

    if not client.indices.exists(index=settings.index_name):
        client.indices.create(index=settings.index_name, **INDEX_MAPPING)

    model = SentenceTransformer(settings.embedding_model)
    embeddings = model.encode(
        dataframe["full_text"].astype(str).tolist(),
        batch_size=batch_size,
        show_progress_bar=True,
    )

    actions = []
    for record, embedding in zip(
        dataframe.where(dataframe.notna(), None).to_dict(orient="records"),
        embeddings,
        strict=True,
    ):
        record["vector_search"] = embedding.tolist()
        actions.append(
            {
                "_op_type": "index",
                "_index": settings.index_name,
                "_id": record["id"],
                "_source": record,
            }
        )

    indexed, errors = helpers.bulk(
        client, actions, chunk_size=batch_size, raise_on_error=False
    )
    if errors:
        raise RuntimeError(f"Failed to index {len(errors)} place records")
    client.indices.refresh(index=settings.index_name)
    print(f"Indexed {indexed} places into '{settings.index_name}'.")
    return indexed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-if-exists",
        action="store_true",
        help="Skip embedding when the index already has the dataset row count.",
    )
    parser.add_argument("--batch-size", type=int, default=64)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.batch_size <= 0:
        print("--batch-size must be positive", file=sys.stderr)
        return 2
    try:
        index_places(
            Settings.from_env(),
            skip_if_exists=args.skip_if_exists,
            batch_size=args.batch_size,
        )
    except Exception as error:
        print(f"Indexing failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
