"""Data contract shared by data builders and the Elasticsearch indexer."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse


SCHEMA_VERSION = 2
VALID_PLACE_TYPES = {"eat", "see", "stay"}
PLACE_FIELDS = (
    "schema_version",
    "id",
    "type",
    "name",
    "name_vi",
    "name_en",
    "description",
    "description_origin",
    "latitude",
    "longitude",
    "address",
    "area",
    "categories",
    "cuisine",
    "opening_hours",
    "phone",
    "website",
    "price_min_vnd",
    "price_max_vnd",
    "price_currency",
    "source",
    "source_id",
    "source_url",
    "source_license",
    "source_updated_at",
    "retrieved_at",
    "last_verified_at",
    "is_synthetic",
    "full_text",
)


def _valid_iso_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate_record(record: dict[str, Any]) -> list[str]:
    """Return human-readable contract violations for one place record."""
    errors: list[str] = []
    missing = [field for field in PLACE_FIELDS if field not in record]
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
        return errors

    if record["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not isinstance(record["id"], str) or not record["id"].strip():
        errors.append("id must be a non-empty string")
    if record["type"] not in VALID_PLACE_TYPES:
        errors.append("type must be eat, see, or stay")
    if not isinstance(record["name"], str) or not record["name"].strip():
        errors.append("name must be a non-empty string")
    if record["description_origin"] not in {"source", "derived_from_tags"}:
        errors.append("description_origin must be source or derived_from_tags")

    for field, low, high in (
        ("latitude", -90.0, 90.0),
        ("longitude", -180.0, 180.0),
    ):
        value = record[field]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{field} must be numeric")
        elif not low <= float(value) <= high:
            errors.append(f"{field} is outside the valid range")

    for field in ("categories", "cuisine"):
        if not isinstance(record[field], list) or not all(
            isinstance(item, str) for item in record[field]
        ):
            errors.append(f"{field} must be a list of strings")

    for field in ("price_min_vnd", "price_max_vnd"):
        value = record[field]
        if value is not None and (not isinstance(value, int) or value < 0):
            errors.append(f"{field} must be a non-negative integer or null")
    minimum = record["price_min_vnd"]
    maximum = record["price_max_vnd"]
    if minimum is not None and maximum is not None and minimum > maximum:
        errors.append("price_min_vnd cannot exceed price_max_vnd")

    if not record["source"]:
        errors.append("source must be present")
    if not record["source_id"]:
        errors.append("source_id must be present")
    if not record["source_license"]:
        errors.append("source_license must be present")
    source_url = record["source_url"]
    if source_url and urlparse(source_url).scheme not in {"http", "https"}:
        errors.append("source_url must be an HTTP(S) URL or null")
    if not _valid_iso_datetime(record["retrieved_at"]):
        errors.append("retrieved_at must be an ISO-8601 datetime")
    for field in ("source_updated_at", "last_verified_at"):
        if record[field] is not None and not _valid_iso_datetime(record[field]):
            errors.append(f"{field} must be an ISO-8601 datetime or null")
    if not isinstance(record["is_synthetic"], bool):
        errors.append("is_synthetic must be boolean")
    if not isinstance(record["full_text"], str) or not record["full_text"].strip():
        errors.append("full_text must be a non-empty string")
    return errors
