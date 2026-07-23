import json
from pathlib import Path

from data_pipeline.legacy import parse_vnd_price
from data_pipeline.osm import deduplicate_records, normalize_response
from data_pipeline.quality import assess_records
from data_pipeline.schema import PLACE_FIELDS, validate_record


FIXTURE = Path(__file__).parent / "fixtures/overpass_sample.json"
RETRIEVED_AT = "2026-07-21T12:00:00+00:00"


def sample_records():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return normalize_response(payload, retrieved_at=RETRIEVED_AT)


def test_osm_normalization_preserves_provenance_and_unknowns() -> None:
    records = sample_records()

    assert len(records) == 3
    restaurant = next(record for record in records if record["type"] == "eat")
    assert tuple(restaurant) == PLACE_FIELDS
    assert restaurant["address"] == "12 Đường Mẫu, Hải Châu"
    assert restaurant["price_min_vnd"] is None
    assert restaurant["last_verified_at"] is None
    assert restaurant["source_url"].endswith("/node/101")
    assert restaurant["source_license"] == "ODbL-1.0"
    assert restaurant["description_origin"] == "derived_from_tags"
    assert restaurant["is_synthetic"] is False
    assert validate_record(restaurant) == []


def test_same_name_nearby_geometry_is_deduplicated() -> None:
    first = sample_records()[0]
    duplicate = {**first, "id": "osm_way_999", "source_id": "way/999"}

    assert len(deduplicate_records([first, duplicate])) == 1


def test_field_provenance_requires_source_metadata() -> None:
    record = {
        **sample_records()[0],
        "field_provenance": {"address": {"source": "Unknown"}},
    }

    errors = validate_record(record)

    assert any("field_provenance.address missing" in error for error in errors)


def test_legacy_price_parser_does_not_use_usd_approximation() -> None:
    assert parse_vnd_price("35k VND (~1.4$)") == (35_000, 35_000)
    assert parse_vnd_price("100k-200k VND") == (100_000, 200_000)
    assert parse_vnd_price("Free") == (None, None)


def test_quality_gate_accepts_valid_minimum_coverage() -> None:
    templates = {record["type"]: record for record in sample_records()}
    records = []
    for place_type, count in {"eat": 65, "see": 15, "stay": 20}.items():
        for position in range(count):
            records.append(
                {
                    **templates[place_type],
                    "id": f"{place_type}_{position}",
                    "source_id": f"node/{place_type}_{position}",
                    "name": f"{templates[place_type]['name']} {position}",
                }
            )

    report = assess_records(records)

    assert report["status"] == "pass"
    assert report["record_count"] == 100
    assert report["checks"]["non_synthetic"] is True
    assert report["description_provenance"]["from_source"] == 15
    assert report["product_readiness"] == "needs_enrichment"
