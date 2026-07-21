"""Fetch and normalize tourism places from OpenStreetMap via Overpass."""

from __future__ import annotations

import json
import math
import re
import urllib.parse
import urllib.request
import unicodedata
from datetime import datetime, timezone
from typing import Any, Iterable

from .schema import PLACE_FIELDS, SCHEMA_VERSION


DEFAULT_BBOX = (15.90, 107.90, 16.25, 108.35)
DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_USER_AGENT = "DaNangTourGuide-data-pipeline/2.0 (research project)"

EAT_AMENITIES = {
    "bar",
    "cafe",
    "fast_food",
    "food_court",
    "ice_cream",
    "pub",
    "restaurant",
}
STAY_TOURISM = {"apartment", "guest_house", "hostel", "hotel", "motel", "resort"}
SEE_TOURISM = {
    "aquarium",
    "artwork",
    "attraction",
    "gallery",
    "museum",
    "theme_park",
    "viewpoint",
    "zoo",
}
SEE_NATURAL = {"beach", "cave_entrance", "peak", "spring"}

CATEGORY_ALIASES = {
    "restaurant": "restaurant nhà hàng",
    "cafe": "cafe coffee cà phê",
    "fast_food": "fast food đồ ăn nhanh",
    "food_court": "food court khu ẩm thực",
    "hotel": "hotel khách sạn",
    "hostel": "hostel nhà nghỉ",
    "guest_house": "guest house nhà khách",
    "resort": "resort khu nghỉ dưỡng",
    "attraction": "attraction điểm tham quan",
    "museum": "museum bảo tàng",
    "gallery": "gallery phòng trưng bày",
    "viewpoint": "viewpoint điểm ngắm cảnh",
    "beach": "beach bãi biển",
    "peak": "peak đỉnh núi",
}


def build_overpass_query(bbox: tuple[float, float, float, float]) -> str:
    south, west, north, east = bbox
    bounds = f"{south},{west},{north},{east}"
    return f"""[out:json][timeout:180];
(
  nwr["name"]["amenity"~"^(restaurant|cafe|fast_food|food_court|ice_cream|bar|pub)$"]({bounds});
  nwr["name"]["tourism"~"^(hotel|hostel|guest_house|motel|apartment|resort|attraction|museum|gallery|viewpoint|theme_park|zoo|aquarium|artwork)$"]({bounds});
  nwr["name"]["historic"]({bounds});
  nwr["name"]["natural"~"^(beach|peak|spring|cave_entrance)$"]({bounds});
);
out center meta;"""


def fetch_overpass(
    *,
    bbox: tuple[float, float, float, float] = DEFAULT_BBOX,
    endpoint: str = DEFAULT_OVERPASS_URL,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout_seconds: int = 240,
) -> dict[str, Any]:
    """Fetch a bounded, read-only Overpass response using a unique User-Agent."""
    payload = urllib.parse.urlencode({"data": build_overpass_query(bbox)}).encode()
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"User-Agent": user_agent, "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned or None


def _split_tag(value: str | None) -> list[str]:
    if not value:
        return []
    return sorted({item.strip() for item in value.split(";") if item.strip()})


def _place_type(tags: dict[str, str]) -> str | None:
    amenity = tags.get("amenity")
    tourism = tags.get("tourism")
    if amenity in EAT_AMENITIES:
        return "eat"
    if tourism in STAY_TOURISM:
        return "stay"
    if tourism in SEE_TOURISM or tags.get("natural") in SEE_NATURAL:
        return "see"
    if tags.get("historic") and tags.get("historic") != "no":
        return "see"
    return None


def _coordinates(element: dict[str, Any]) -> tuple[float | None, float | None]:
    latitude = element.get("lat")
    longitude = element.get("lon")
    if latitude is None or longitude is None:
        center = element.get("center", {})
        latitude = center.get("lat")
        longitude = center.get("lon")
    if latitude is None or longitude is None:
        return None, None
    return float(latitude), float(longitude)


def _address(tags: dict[str, str]) -> str | None:
    street = _clean(tags.get("addr:street") or tags.get("addr:place"))
    number = _clean(tags.get("addr:housenumber"))
    first = " ".join(part for part in (number, street) if part)
    parts = [
        first or None,
        _clean(
            tags.get("addr:quarter") or tags.get("addr:suburb") or tags.get("addr:ward")
        ),
        _clean(tags.get("addr:district")),
        _clean(tags.get("addr:city")),
    ]
    unique: list[str] = []
    for part in parts:
        if part and part.casefold() not in {value.casefold() for value in unique}:
            unique.append(part)
    return ", ".join(unique) or None


def _categories(tags: dict[str, str]) -> list[str]:
    values = [
        tags.get("amenity"),
        tags.get("tourism"),
        tags.get("historic"),
        tags.get("natural"),
    ]
    return sorted({value for value in values if value and value != "yes"})


def _description(
    tags: dict[str, str], categories: list[str], cuisine: list[str]
) -> tuple[str | None, str]:
    supplied = _clean(tags.get("description:en") or tags.get("description"))
    if supplied:
        return supplied, "source"
    facts = [
        CATEGORY_ALIASES.get(category, category.replace("_", " "))
        for category in categories
    ]
    if cuisine:
        facts.append(
            "cuisine: " + ", ".join(item.replace("_", " ") for item in cuisine)
        )
    return "; ".join(facts) or None, "derived_from_tags"


def _full_text(record: dict[str, Any]) -> str:
    values: list[str] = []
    for field in (
        "name",
        "name_vi",
        "name_en",
        "description",
        "address",
        "area",
        "opening_hours",
    ):
        if record.get(field):
            values.append(str(record[field]))
    values.extend(
        CATEGORY_ALIASES.get(value, value.replace("_", " "))
        for value in record["categories"]
    )
    values.extend(value.replace("_", " ") for value in record["cuisine"])
    return " ".join(dict.fromkeys(values))


def normalize_element(
    element: dict[str, Any], *, retrieved_at: str
) -> dict[str, Any] | None:
    """Convert one OSM element to the v2 contract without inventing missing facts."""
    tags = element.get("tags") or {}
    place_type = _place_type(tags)
    name = _clean(tags.get("name"))
    latitude, longitude = _coordinates(element)
    if not place_type or not name or latitude is None or longitude is None:
        return None

    element_type = str(element["type"])
    element_id = str(element["id"])
    categories = _categories(tags)
    cuisine = _split_tag(_clean(tags.get("cuisine")))
    area = _clean(
        tags.get("addr:district")
        or tags.get("addr:suburb")
        or tags.get("addr:quarter")
        or tags.get("addr:ward")
    )
    description, description_origin = _description(tags, categories, cuisine)
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id": f"osm_{element_type}_{element_id}",
        "type": place_type,
        "name": name,
        "name_vi": _clean(tags.get("name:vi")),
        "name_en": _clean(tags.get("name:en")),
        "description": description,
        "description_origin": description_origin,
        "latitude": latitude,
        "longitude": longitude,
        "address": _address(tags),
        "area": area,
        "categories": categories,
        "cuisine": cuisine,
        "opening_hours": _clean(tags.get("opening_hours")),
        "phone": _clean(tags.get("contact:phone") or tags.get("phone")),
        "website": _clean(tags.get("contact:website") or tags.get("website")),
        "price_min_vnd": None,
        "price_max_vnd": None,
        "price_currency": "VND",
        "source": "OpenStreetMap",
        "source_id": f"{element_type}/{element_id}",
        "source_url": f"https://www.openstreetmap.org/{element_type}/{element_id}",
        "source_license": "ODbL-1.0",
        "source_updated_at": _clean(element.get("timestamp")),
        "retrieved_at": retrieved_at,
        "last_verified_at": None,
        "is_synthetic": False,
        "full_text": "",
    }
    record["full_text"] = _full_text(record)
    return {field: record[field] for field in PLACE_FIELDS}


def normalize_response(
    payload: dict[str, Any], *, retrieved_at: str | None = None
) -> list[dict[str, Any]]:
    timestamp = (
        retrieved_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    )
    records = [
        record
        for element in payload.get("elements", [])
        if (record := normalize_element(element, retrieved_at=timestamp)) is not None
    ]
    return deduplicate_records(records)


def _normalized_name(value: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", ascii_name.casefold())


def _distance_meters(first: dict[str, Any], second: dict[str, Any]) -> float:
    latitude_scale = 111_320.0
    average_latitude = math.radians((first["latitude"] + second["latitude"]) / 2)
    dx = (
        (first["longitude"] - second["longitude"])
        * latitude_scale
        * math.cos(average_latitude)
    )
    dy = (first["latitude"] - second["latitude"]) * latitude_scale
    return math.hypot(dx, dy)


def _completeness(record: dict[str, Any]) -> int:
    return sum(
        bool(record.get(field))
        for field in (
            "description",
            "address",
            "area",
            "opening_hours",
            "phone",
            "website",
            "name_vi",
            "name_en",
        )
    )


def deduplicate_records(
    records: Iterable[dict[str, Any]], *, radius_meters: float = 80.0
) -> list[dict[str, Any]]:
    """Collapse same-name OSM geometries that refer to the same nearby venue."""
    selected: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: (-_completeness(item), item["id"])):
        duplicate = next(
            (
                existing
                for existing in selected
                if existing["type"] == record["type"]
                and _normalized_name(existing["name"])
                == _normalized_name(record["name"])
                and _distance_meters(existing, record) <= radius_meters
            ),
            None,
        )
        if duplicate is None:
            selected.append(record)
    return sorted(
        selected, key=lambda item: (item["type"], item["name"].casefold(), item["id"])
    )
