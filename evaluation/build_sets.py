"""Build leakage-resistant discovery and name-lookup retrieval tracks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

from data_pipeline.build_dataset import _atomic_write
from data_pipeline.quality import load_jsonl


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_ROOT / "Data/processed/places_enriched_v2.jsonl"
DEFAULT_DISCOVERY = PROJECT_ROOT / "Data/evaluation/discovery_v1.jsonl"
DEFAULT_NAME_LOOKUP = PROJECT_ROOT / "Data/evaluation/name_lookup_v1.jsonl"
DEFAULT_MANIFEST = PROJECT_ROOT / "Data/evaluation/manifest_v1.json"

AREA_ALIASES = {
    "hai chau": "Hải Châu",
    "son tra": "Sơn Trà",
    "ngu hanh son": "Ngũ Hành Sơn",
    "thanh khe": "Thanh Khê",
    "lien chieu": "Liên Chiểu",
    "cam le": "Cẩm Lệ",
}
GENERIC_NAMES = {
    "apartment",
    "apartments",
    "bar",
    "beach",
    "cafe",
    "coffee",
    "guest house",
    "hostel",
    "hotel",
    "motel",
    "restaurant",
    "resort",
}
FOOD_NOUN_CUISINES = {
    "asian",
    "indian",
    "international",
    "italian",
    "japanese",
    "korean",
    "local",
    "mexican",
    "regional",
    "thai",
    "vietnamese",
}


def normalize_text(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    )
    return " ".join(re.findall(r"[a-z0-9]+", ascii_value.casefold()))


def canonical_area(record: dict[str, Any]) -> str | None:
    text = normalize_text(
        " ".join((record.get("area") or "", record.get("address") or ""))
    )
    for alias, canonical in AREA_ALIASES.items():
        if alias in text:
            return canonical
    return None


def cuisine_phrase(cuisine: str) -> str:
    label = cuisine.replace("_", " ")
    if cuisine == "coffee_shop":
        return "coffee"
    if cuisine in FOOD_NOUN_CUISINES:
        return f"{label} food"
    return label


def _identifier(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha1(value.encode()).hexdigest()[:12]}"


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    content = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    _atomic_write(path, content)
    return hashlib.sha256(content.encode()).hexdigest()


def _query_leaks_name(
    query: str, relevant_ids: list[str], records_by_id: dict[str, dict[str, Any]]
) -> bool:
    normalized_query = normalize_text(query)
    for document_id in relevant_ids:
        normalized_name = normalize_text(records_by_id[document_id]["name"])
        if len(normalized_name) >= 5 and normalized_name in normalized_query:
            return True
    return False


def _candidate(
    *,
    query: str,
    place_type: str,
    relevant_ids: list[str],
    constraint_kind: str,
    facets: dict[str, Any],
) -> dict[str, Any]:
    identity = json.dumps(
        [query, place_type, relevant_ids, constraint_kind], ensure_ascii=False
    )
    return {
        "query_id": _identifier("discovery", identity),
        "track": "discovery",
        "query": query,
        "type_filter": place_type,
        "relevant_ids": relevant_ids,
        "relevance_count": len(relevant_ids),
        "constraint_kind": constraint_kind,
        "facets": facets,
        "judgment_method": "deterministic_structured_constraints",
    }


def _records_matching(
    records: list[dict[str, Any]], predicate: Callable[[dict[str, Any]], bool]
) -> list[str]:
    return sorted(record["id"] for record in records if predicate(record))


def discovery_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    category_counts = Counter(
        (record["type"], category)
        for record in records
        for category in record["categories"]
    )
    cuisine_counts = Counter(
        cuisine for record in records for cuisine in record["cuisine"]
    )

    category_templates = {
        "eat": (
            "Where can I find {label} places in Da Nang?",
            "Recommend a {label} option in Da Nang.",
        ),
        "see": (
            "Where can I visit a {label} in Da Nang?",
            "Recommend a {label} to see in Da Nang.",
        ),
        "stay": (
            "Where can I stay at a {label} in Da Nang?",
            "Recommend a {label} for a Da Nang trip.",
        ),
    }
    for (place_type, category), count in sorted(category_counts.items()):
        if not 2 <= count <= 100:
            continue
        relevant_ids = _records_matching(
            records,
            lambda record, t=place_type, c=category: record["type"] == t
            and c in record["categories"],
        )
        label = category.replace("_", " ")
        for template in category_templates[place_type]:
            candidates.append(
                _candidate(
                    query=template.format(label=label),
                    place_type=place_type,
                    relevant_ids=relevant_ids,
                    constraint_kind="category",
                    facets={"category": category},
                )
            )

    for cuisine, count in sorted(cuisine_counts.items()):
        if not 2 <= count <= 60:
            continue
        relevant_ids = _records_matching(
            records, lambda record, c=cuisine: c in record["cuisine"]
        )
        label = cuisine_phrase(cuisine)
        for template in (
            "Where can I find a place serving {label} in Da Nang?",
            "Recommend somewhere for {label}.",
        ):
            candidates.append(
                _candidate(
                    query=template.format(label=label),
                    place_type="eat",
                    relevant_ids=relevant_ids,
                    constraint_kind="cuisine",
                    facets={"cuisine": cuisine},
                )
            )

    areas = sorted({area for record in records if (area := canonical_area(record))})
    categories = sorted(
        {category for record in records for category in record["categories"]}
    )
    cuisines = sorted({cuisine for record in records for cuisine in record["cuisine"]})

    for area in areas:
        for place_type in ("eat", "see", "stay"):
            relevant_ids = _records_matching(
                records,
                lambda record, a=area, t=place_type: record["type"] == t
                and canonical_area(record) == a,
            )
            if 2 <= len(relevant_ids) <= 60:
                noun = {"eat": "food", "see": "attractions", "stay": "places to stay"}[
                    place_type
                ]
                candidates.append(
                    _candidate(
                        query=f"Recommend {noun} in {area}.",
                        place_type=place_type,
                        relevant_ids=relevant_ids,
                        constraint_kind="area_type",
                        facets={"area": area},
                    )
                )

        for category in categories:
            relevant_records = [
                record
                for record in records
                if category in record["categories"] and canonical_area(record) == area
            ]
            if not relevant_records:
                continue
            place_type = relevant_records[0]["type"]
            relevant_ids = sorted(record["id"] for record in relevant_records)
            if 2 <= len(relevant_ids) <= 40:
                candidates.append(
                    _candidate(
                        query=f"Where can I find {category.replace('_', ' ')} options in {area}?",
                        place_type=place_type,
                        relevant_ids=relevant_ids,
                        constraint_kind="category_area",
                        facets={"category": category, "area": area},
                    )
                )

        for cuisine in cuisines:
            relevant_ids = _records_matching(
                records,
                lambda record, a=area, c=cuisine: c in record["cuisine"]
                and canonical_area(record) == a,
            )
            if 2 <= len(relevant_ids) <= 40:
                candidates.append(
                    _candidate(
                        query=f"Where can I get {cuisine_phrase(cuisine)} in {area}?",
                        place_type="eat",
                        relevant_ids=relevant_ids,
                        constraint_kind="cuisine_area",
                        facets={"cuisine": cuisine, "area": area},
                    )
                )

    for place_type in ("eat", "see", "stay"):
        relevant_ids = _records_matching(
            records,
            lambda record, t=place_type: record["type"] == t
            and str(record.get("opening_hours", "")).strip() == "24/7",
        )
        if 2 <= len(relevant_ids) <= 60:
            candidates.append(
                _candidate(
                    query={
                        "eat": "Which food places are open 24 hours?",
                        "see": "Which attractions are open 24 hours?",
                        "stay": "Which places to stay operate 24 hours?",
                    }[place_type],
                    place_type=place_type,
                    relevant_ids=relevant_ids,
                    constraint_kind="opening_hours_24_7",
                    facets={"opening_hours": "24/7"},
                )
            )
    return candidates


def _balanced_select(
    rows: list[dict[str, Any]], *, target_count: int
) -> list[dict[str, Any]]:
    quotas = {
        "eat": round(target_count * 0.4),
        "see": round(target_count * 0.3),
        "stay": target_count - round(target_count * 0.4) - round(target_count * 0.3),
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["type_filter"]].append(row)
    selected: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for place_type, group in grouped.items():
        ordered = sorted(
            group,
            key=lambda row: (
                row["constraint_kind"],
                row["relevance_count"],
                row["query_id"],
            ),
        )
        selected.extend(ordered[: quotas.get(place_type, 0)])
        remaining.extend(ordered[quotas.get(place_type, 0) :])
    if len(selected) < target_count:
        selected.extend(
            sorted(remaining, key=lambda row: row["query_id"])[
                : target_count - len(selected)
            ]
        )
    return sorted(selected, key=lambda row: row["query_id"])


def build_discovery_track(
    records: list[dict[str, Any]], *, target_count: int
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    records_by_id = {record["id"]: record for record in records}
    seen_queries: set[str] = set()
    accepted: list[dict[str, Any]] = []
    rejected = Counter()
    for candidate in discovery_candidates(records):
        normalized_query = normalize_text(candidate["query"])
        if normalized_query in seen_queries:
            rejected["duplicate_query"] += 1
            continue
        if not 2 <= candidate["relevance_count"] <= 100:
            rejected["invalid_relevance_count"] += 1
            continue
        if _query_leaks_name(
            candidate["query"], candidate["relevant_ids"], records_by_id
        ):
            rejected["venue_name_leakage"] += 1
            continue
        seen_queries.add(normalized_query)
        accepted.append(candidate)
    return _balanced_select(accepted, target_count=target_count), dict(rejected)


def build_name_lookup_track(
    records: list[dict[str, Any]], *, target_count: int
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        normalized_name = normalize_text(record["name"])
        if len(normalized_name) < 5 or normalized_name in GENERIC_NAMES:
            continue
        grouped[(record["type"], normalized_name)].append(record)

    candidates: list[dict[str, Any]] = []
    for (place_type, normalized_name), group in grouped.items():
        display_name = sorted(record["name"] for record in group)[0]
        template = (
            "What information do you have about {name}?"
            if int(hashlib.sha1(normalized_name.encode()).hexdigest(), 16) % 2
            else "Find {name} in Da Nang."
        )
        query = template.format(name=display_name)
        relevant_ids = sorted(record["id"] for record in group)
        candidates.append(
            {
                "query_id": _identifier("lookup", f"{place_type}|{normalized_name}"),
                "track": "name_lookup",
                "query": query,
                "type_filter": place_type,
                "relevant_ids": relevant_ids,
                "relevance_count": len(relevant_ids),
                "constraint_kind": "venue_name",
                "facets": {"name": display_name},
                "judgment_method": "exact_normalized_name",
            }
        )
    return _balanced_select(candidates, target_count=target_count)


def build(
    *,
    dataset_path: Path,
    discovery_path: Path,
    name_lookup_path: Path,
    manifest_path: Path,
    discovery_count: int,
    name_lookup_count: int,
) -> dict[str, Any]:
    records = load_jsonl(dataset_path)
    discovery, rejected = build_discovery_track(records, target_count=discovery_count)
    name_lookup = build_name_lookup_track(records, target_count=name_lookup_count)
    if len(discovery) < discovery_count:
        raise RuntimeError(
            f"Only {len(discovery)} valid discovery queries; requested {discovery_count}"
        )
    if len(name_lookup) < name_lookup_count:
        raise RuntimeError(
            f"Only {len(name_lookup)} name queries; requested {name_lookup_count}"
        )
    discovery_sha = _write_jsonl(discovery_path, discovery)
    lookup_sha = _write_jsonl(name_lookup_path, name_lookup)
    manifest = {
        "version": 1,
        "dataset_path": str(dataset_path.relative_to(PROJECT_ROOT)),
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "tracks": {
            "discovery": {
                "path": str(discovery_path.relative_to(PROJECT_ROOT)),
                "query_count": len(discovery),
                "sha256": discovery_sha,
                "type_counts": dict(
                    sorted(Counter(row["type_filter"] for row in discovery).items())
                ),
                "constraint_counts": dict(
                    sorted(Counter(row["constraint_kind"] for row in discovery).items())
                ),
                "rejected_candidates": rejected,
                "venue_name_leakage_count": 0,
            },
            "name_lookup": {
                "path": str(name_lookup_path.relative_to(PROJECT_ROOT)),
                "query_count": len(name_lookup),
                "sha256": lookup_sha,
                "type_counts": dict(
                    sorted(Counter(row["type_filter"] for row in name_lookup).items())
                ),
            },
        },
        "limitations": [
            "Discovery relevance is weakly supervised by exact structured constraints, not human preference judgments.",
            "Queries about price are excluded because the current real dataset has no fresh price coverage.",
            "Subjective intents such as best, romantic, or family-friendly are excluded.",
            "Type filters simulate the current Eat/See/Stay UI context.",
        ],
    }
    _atomic_write(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--discovery-output", type=Path, default=DEFAULT_DISCOVERY)
    parser.add_argument("--name-output", type=Path, default=DEFAULT_NAME_LOOKUP)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--discovery-count", type=int, default=120)
    parser.add_argument("--name-count", type=int, default=90)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.discovery_count <= 0 or args.name_count <= 0:
        print("Track counts must be positive", file=sys.stderr)
        return 2
    try:
        manifest = build(
            dataset_path=args.dataset,
            discovery_path=args.discovery_output,
            name_lookup_path=args.name_output,
            manifest_path=args.manifest,
            discovery_count=args.discovery_count,
            name_lookup_count=args.name_count,
        )
    except Exception as error:
        print(f"Evaluation set build failed: {error}", file=sys.stderr)
        return 1
    print(
        f"Built {manifest['tracks']['discovery']['query_count']} discovery and "
        f"{manifest['tracks']['name_lookup']['query_count']} name-lookup queries."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
