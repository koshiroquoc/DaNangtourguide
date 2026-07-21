"""Idempotent Elasticsearch indexing command."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch, helpers

from .config import Settings


from data_pipeline.schema import PLACE_FIELDS, validate_record


def build_index_mapping(*, vector_dims: int, dataset_sha256: str) -> dict[str, Any]:
    return {
        "mappings": {
            "_meta": {"schema_version": 2, "dataset_sha256": dataset_sha256},
            "properties": {
                "schema_version": {"type": "integer"},
                "type": {"type": "keyword"},
                "name": {"type": "text"},
                "name_vi": {"type": "text"},
                "name_en": {"type": "text"},
                "description": {"type": "text"},
                "description_origin": {"type": "keyword"},
                "latitude": {"type": "double"},
                "longitude": {"type": "double"},
                "location_geo": {"type": "geo_point"},
                "address": {"type": "text"},
                "categories": {"type": "keyword"},
                "cuisine": {"type": "keyword"},
                "opening_hours": {"type": "keyword"},
                "phone": {"type": "keyword"},
                "website": {"type": "keyword", "ignore_above": 2048},
                "price_min_vnd": {"type": "integer"},
                "price_max_vnd": {"type": "integer"},
                "price_currency": {"type": "keyword"},
                "source": {"type": "keyword"},
                "source_id": {"type": "keyword"},
                "source_url": {"type": "keyword", "ignore_above": 2048},
                "source_license": {"type": "keyword"},
                "source_updated_at": {"type": "date"},
                "retrieved_at": {"type": "date"},
                "last_verified_at": {"type": "date"},
                "is_synthetic": {"type": "boolean"},
                # Legacy fields remain mapped so DATA_PATH can still point to the
                # original synthetic CSV for controlled baseline comparisons.
                "time": {"type": "keyword"},
                "price": {"type": "keyword"},
                "location": {"type": "text"},
                "area": {"type": "keyword"},
                "note": {"type": "text"},
                "id": {"type": "keyword"},
                "full_text": {"type": "text"},
                "vector_search": {
                    "type": "dense_vector",
                    "dims": vector_dims,
                    "index": True,
                    "similarity": "cosine",
                },
            },
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
    client: Elasticsearch,
    *,
    index_name: str,
    expected_count: int,
    dataset_sha256: str | None = None,
) -> bool:
    if not client.indices.exists(index=index_name):
        return False
    if int(client.count(index=index_name)["count"]) != expected_count:
        return False
    if dataset_sha256 is None:
        return True
    mapping = client.indices.get_mapping(index=index_name)
    indexed_sha256 = (
        mapping.get(index_name, {})
        .get("mappings", {})
        .get("_meta", {})
        .get("dataset_sha256")
    )
    return indexed_sha256 == dataset_sha256


def _dataset_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_records(path: Path) -> list[dict[str, Any]]:
    """Load contract-v2 JSONL or the legacy CSV baseline."""
    if path.suffix.casefold() == ".jsonl":
        records: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError(f"Dataset line {line_number} is not a JSON object")
                violations = validate_record(record)
                if violations:
                    raise ValueError(
                        f"Dataset line {line_number} violates schema v2: "
                        + "; ".join(violations)
                    )
                records.append({field: record[field] for field in PLACE_FIELDS})
        if not records:
            raise ValueError("Dataset is empty")
        return records

    if path.suffix.casefold() != ".csv":
        raise ValueError("DATA_PATH must point to a .jsonl or .csv file")
    import pandas as pd

    dataframe = pd.read_csv(path)
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
    return dataframe.where(dataframe.notna(), None).to_dict(orient="records")


def index_places(
    settings: Settings,
    *,
    skip_if_exists: bool = False,
    batch_size: int = 64,
) -> int:
    """Embed all atomic place records in batches and bulk upsert them."""
    from sentence_transformers import SentenceTransformer

    if not settings.data_path.exists():
        raise FileNotFoundError(f"Dataset not found: {settings.data_path}")

    records = load_records(settings.data_path)
    identifiers = [str(record["id"]) for record in records]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Dataset contains duplicate place IDs")
    dataset_sha256 = _dataset_sha256(settings.data_path)

    client = create_client(settings)
    wait_until_ready(client, timeout_seconds=settings.startup_timeout_seconds)

    if skip_if_exists and index_is_current(
        client,
        index_name=settings.index_name,
        expected_count=len(records),
        dataset_sha256=dataset_sha256,
    ):
        print(
            f"Index '{settings.index_name}' already contains this {len(records)}-place dataset; "
            "skipping indexing."
        )
        return 0

    model = SentenceTransformer(settings.embedding_model)
    embeddings = model.encode(
        [str(record["full_text"]) for record in records],
        batch_size=batch_size,
        show_progress_bar=True,
    )
    if len(embeddings) == 0:
        raise ValueError("Embedding model returned no vectors")

    # Elasticsearch is derived state. Recreate a stale index so removed source
    # records cannot survive a dataset refresh.
    if client.indices.exists(index=settings.index_name):
        client.indices.delete(index=settings.index_name)
    client.indices.create(
        index=settings.index_name,
        **build_index_mapping(
            vector_dims=len(embeddings[0]), dataset_sha256=dataset_sha256
        ),
    )

    actions = []
    for record, embedding in zip(records, embeddings, strict=True):
        record = dict(record)
        if record.get("latitude") is not None and record.get("longitude") is not None:
            record["location_geo"] = {
                "lat": record["latitude"],
                "lon": record["longitude"],
            }
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
    print(
        f"Indexed {indexed} places into '{settings.index_name}' "
        f"from dataset {dataset_sha256[:12]}...."
    )
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
