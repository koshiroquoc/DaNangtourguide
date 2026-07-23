"""Match open-data listings and apply only fresh, non-conflicting facts."""

from __future__ import annotations

import copy
import csv
import math
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .schema import with_optional_defaults


FIELD_TTL_DAYS = {
    "address": 5 * 365,
    "opening_hours": 365,
    "phone": 2 * 365,
    "website": 2 * 365,
    "price_text": 180,
}
HIGH_IMPACT_FIELDS = ("price_text", "opening_hours", "address", "phone", "website")
STOPWORDS = {
    "da",
    "nang",
    "quan",
    "nha",
    "hang",
    "khach",
    "san",
    "hotel",
    "restaurant",
    "resort",
    "hostel",
    "cafe",
}


def _normalized_tokens(value: str) -> list[str]:
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    )
    tokens = re.findall(r"[a-z0-9]+", ascii_value.casefold())
    meaningful = [token for token in tokens if token not in STOPWORDS]
    return meaningful or tokens


def name_similarity(first: str, second: str) -> float:
    first_tokens = _normalized_tokens(first)
    second_tokens = _normalized_tokens(second)
    first_text = " ".join(first_tokens)
    second_text = " ".join(second_tokens)
    sequence = SequenceMatcher(None, first_text, second_text).ratio()
    union = set(first_tokens) | set(second_tokens)
    jaccard = len(set(first_tokens) & set(second_tokens)) / len(union) if union else 0
    return max(sequence, jaccard)


def distance_meters(first: dict[str, Any], second: dict[str, Any]) -> float:
    if any(
        item is None
        for item in (
            first.get("latitude"),
            first.get("longitude"),
            second.get("latitude"),
            second.get("longitude"),
        )
    ):
        return math.inf
    radius = 6_371_000.0
    first_lat = math.radians(float(first["latitude"]))
    second_lat = math.radians(float(second["latitude"]))
    delta_lat = second_lat - first_lat
    delta_lon = math.radians(float(second["longitude"]) - float(first["longitude"]))
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(first_lat) * math.cos(second_lat) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(haversine))


def match_listings(
    places: list[dict[str, Any]], listings: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Greedily accept only high-confidence coordinate-and-name matches."""
    candidates: list[dict[str, Any]] = []
    for listing in listings:
        if listing.get("latitude") is None or listing.get("longitude") is None:
            continue
        for place in places:
            if place["type"] != listing["type"]:
                continue
            distance = distance_meters(place, listing)
            if distance > 400:
                continue
            similarity = name_similarity(place["name"], listing["name"])
            score = 0.75 * similarity + 0.25 * max(0.0, 1.0 - distance / 400)
            if (similarity >= 0.58 and distance <= 200 and score >= 0.68) or (
                similarity >= 0.9 and distance <= 400
            ):
                candidates.append(
                    {
                        "place_id": place["id"],
                        "listing_id": listing["id"],
                        "score": round(score, 4),
                        "name_similarity": round(similarity, 4),
                        "distance_meters": round(distance, 1),
                    }
                )
    matched_places: set[str] = set()
    matched_listings: set[str] = set()
    matches: list[dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda item: item["score"], reverse=True):
        if (
            candidate["place_id"] in matched_places
            or candidate["listing_id"] in matched_listings
        ):
            continue
        matched_places.add(candidate["place_id"])
        matched_listings.add(candidate["listing_id"])
        matches.append(candidate)
    return matches


def _age_days(updated_at: str, retrieved_at: str) -> int:
    updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    retrieved = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    return max(0, (retrieved - updated).days)


def apply_enrichment(
    places: list[dict[str, Any]],
    listings: list[dict[str, Any]],
    matches: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fill nulls only when the matched source field is inside its TTL."""
    listing_by_id = {listing["id"]: listing for listing in listings}
    match_by_place = {match["place_id"]: match for match in matches}
    events: list[dict[str, Any]] = []
    enriched: list[dict[str, Any]] = []
    for original in places:
        place = with_optional_defaults(copy.deepcopy(original))
        match = match_by_place.get(place["id"])
        if not match:
            enriched.append(place)
            continue
        listing = listing_by_id[match["listing_id"]]
        applied_fields: list[str] = []
        for field, ttl_days in FIELD_TTL_DAYS.items():
            value = listing.get(field)
            if value in {None, ""}:
                continue
            if place.get(field) not in {None, ""}:
                events.append(
                    {
                        "place_id": place["id"],
                        "listing_id": listing["id"],
                        "field": field,
                        "action": "kept_primary",
                        "reason": "primary field already present",
                    }
                )
                continue
            if not listing.get("source_updated_at"):
                events.append(
                    {
                        "place_id": place["id"],
                        "listing_id": listing["id"],
                        "field": field,
                        "action": "rejected_unknown_age",
                        "reason": "listing has no field-level lastedit date",
                    }
                )
                continue
            age_days = _age_days(listing["source_updated_at"], listing["retrieved_at"])
            if age_days > ttl_days:
                events.append(
                    {
                        "place_id": place["id"],
                        "listing_id": listing["id"],
                        "field": field,
                        "action": "rejected_stale",
                        "reason": f"{age_days} days old; TTL is {ttl_days}",
                    }
                )
                continue
            place[field] = value
            place["field_provenance"][field] = {
                "source": listing["source"],
                "source_url": listing["source_url"],
                "source_history_url": listing["source_history_url"],
                "source_license": listing["source_license"],
                "source_revision": listing["source_revision"],
                "source_updated_at": listing["source_updated_at"],
                "retrieved_at": listing["retrieved_at"],
                "match_score": match["score"],
            }
            applied_fields.append(field)
            events.append(
                {
                    "place_id": place["id"],
                    "listing_id": listing["id"],
                    "field": field,
                    "action": "applied",
                    "reason": "fresh matched field filled a null",
                }
            )
        if applied_fields:
            place["enrichment_sources"].append(
                {
                    "source": listing["source"],
                    "source_url": listing["source_url"],
                    "source_history_url": listing["source_history_url"],
                    "source_license": listing["source_license"],
                    "source_revision": listing["source_revision"],
                    "attribution": listing["attribution"],
                    "fields": applied_fields,
                }
            )
            additions = [str(place[field]) for field in applied_fields if place[field]]
            place["full_text"] = " ".join(
                dict.fromkeys([place["full_text"], *additions])
            )
        enriched.append(place)
    return enriched, events


def build_verification_queue(
    places: list[dict[str, Any]],
    listings: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    events: list[dict[str, Any]],
    *,
    target_count: int = 200,
) -> list[dict[str, Any]]:
    """Build a balanced heuristic queue; this is not a popularity ranking."""
    match_by_place = {match["place_id"]: match for match in matches}
    listing_by_id = {listing["id"]: listing for listing in listings}
    rejected_by_place: dict[str, list[str]] = {}
    for event in events:
        if event["action"] in {"rejected_stale", "rejected_unknown_age"}:
            rejected_by_place.setdefault(event["place_id"], []).append(event["field"])

    rows: list[dict[str, Any]] = []
    for place in places:
        missing = [field for field in HIGH_IMPACT_FIELDS if not place.get(field)]
        match = match_by_place.get(place["id"])
        listing = listing_by_id[match["listing_id"]] if match else None
        gap_score = sum(
            {
                "price_text": 3,
                "opening_hours": 3,
                "address": 2,
                "phone": 1,
                "website": 1,
            }[field]
            for field in missing
        )
        priority = (
            gap_score
            + (15 if match else 0)
            + 2 * len(rejected_by_place.get(place["id"], []))
        )
        if place.get("description_origin") == "source":
            priority += 2
        rows.append(
            {
                "priority_score": priority,
                "id": place["id"],
                "type": place["type"],
                "name": place["name"],
                "address": place.get("address") or "",
                "primary_source_url": place.get("source_url") or "",
                "source_updated_at": place.get("source_updated_at") or "",
                "missing_fields": ";".join(missing),
                "stale_enrichment_fields": ";".join(
                    sorted(set(rejected_by_place.get(place["id"], [])))
                ),
                "wikivoyage_listing_id": listing["id"] if listing else "",
                "wikivoyage_source_url": listing["source_url"] if listing else "",
                "match_score": match["score"] if match else "",
                "queue_basis": "heuristic gaps + attributable-source match; not popularity",
            }
        )

    quotas = {"eat": 80, "see": 50, "stay": 70}
    if target_count != sum(quotas.values()):
        quotas = {
            "eat": round(target_count * 0.4),
            "see": round(target_count * 0.25),
            "stay": target_count
            - round(target_count * 0.4)
            - round(target_count * 0.25),
        }
    selected: list[dict[str, Any]] = []
    for place_type, quota in quotas.items():
        candidates = [row for row in rows if row["type"] == place_type]
        selected.extend(
            sorted(
                candidates,
                key=lambda row: (
                    -int(row["priority_score"]),
                    row["name"].casefold(),
                    row["id"],
                ),
            )[:quota]
        )
    return sorted(
        selected,
        key=lambda row: (
            -int(row["priority_score"]),
            row["type"],
            row["name"].casefold(),
        ),
    )


def write_queue(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("Verification queue is empty")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
