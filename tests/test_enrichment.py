import json
from pathlib import Path

from data_pipeline.enrichment import apply_enrichment, match_listings
from data_pipeline.osm import normalize_response
from data_pipeline.wikivoyage import extract_listings


FIXTURES = Path(__file__).parent / "fixtures"


def page_fixture():
    return {
        "title": "Da Nang",
        "wikitext": (FIXTURES / "wikivoyage_sample.wiki").read_text(encoding="utf-8"),
        "revision_id": 123,
        "revision_at": "2026-07-20T00:00:00Z",
        "retrieved_at": "2026-07-21T00:00:00+00:00",
        "source_url": "https://en.wikivoyage.org/w/index.php?title=Da_Nang&oldid=123",
        "history_url": "https://en.wikivoyage.org/w/index.php?title=Da_Nang&action=history",
        "source_license": "CC-BY-SA-4.0",
        "attribution": "Wikivoyage contributors to Da Nang; see page history",
    }


def osm_places():
    payload = json.loads(
        (FIXTURES / "overpass_sample.json").read_text(encoding="utf-8")
    )
    return normalize_response(payload, retrieved_at="2026-07-21T00:00:00+00:00")


def test_wikivoyage_parser_keeps_facts_and_omits_prose() -> None:
    listings = extract_listings(page_fixture())

    assert len(listings) == 2
    restaurant = next(item for item in listings if item["type"] == "eat")
    assert restaurant["opening_hours"] == "06:00-21:00"
    assert restaurant["price_text"] == "40,000-60,000 VND"
    assert "content" not in restaurant
    assert all("This prose" not in str(value) for value in restaurant.values())


def test_enrichment_applies_fresh_nulls_with_field_provenance() -> None:
    places = osm_places()
    listings = extract_listings(page_fixture())
    matches = match_listings(places, listings)

    enriched, events = apply_enrichment(places, listings, matches)

    restaurant = next(item for item in enriched if item["type"] == "eat")
    assert restaurant["price_text"] == "40,000-60,000 VND"
    assert restaurant["phone"] == "+84 236 123 456"
    assert restaurant["field_provenance"]["price_text"]["source_revision"] == 123
    assert restaurant["last_verified_at"] is None
    assert any(event["action"] == "applied" for event in events)


def test_stale_price_and_address_are_not_applied() -> None:
    places = osm_places()
    listings = extract_listings(page_fixture())
    matches = match_listings(places, listings)

    enriched, events = apply_enrichment(places, listings, matches)

    hotel = next(item for item in enriched if item["type"] == "stay")
    assert hotel["price_text"] is None
    assert hotel["address"] is None
    assert hotel["website"] == "https://example.org/hotel"
    stale_fields = {
        event["field"]
        for event in events
        if event["place_id"] == hotel["id"] and event["action"] == "rejected_stale"
    }
    assert stale_fields == {"address", "price_text"}


def test_missing_listing_lastedit_never_uses_page_revision_as_freshness() -> None:
    places = osm_places()
    listings = extract_listings(page_fixture())
    restaurant_listing = next(item for item in listings if item["type"] == "eat")
    restaurant_listing["source_updated_at"] = None
    matches = match_listings(places, listings)

    enriched, events = apply_enrichment(places, listings, matches)

    restaurant = next(item for item in enriched if item["type"] == "eat")
    assert restaurant["price_text"] is None
    assert restaurant["phone"] is None
    assert {
        event["field"]
        for event in events
        if event["place_id"] == restaurant["id"]
        and event["action"] == "rejected_unknown_age"
    } == {"phone", "price_text"}
