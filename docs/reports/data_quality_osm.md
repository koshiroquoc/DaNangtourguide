# OSM dataset quality report

- Structural/contract status: **PASS**
- Product readiness: **NEEDS ENRICHMENT**
- Dataset: `Data/processed/places_osm_v2.jsonl`
- Retrieved at: `2026-07-21T08:04:58+00:00`
- Records: **2557**
- Source: OpenStreetMap contributors (ODbL 1.0)

## Category coverage

| Type | Records |
|---|---:|
| eat | 1749 |
| see | 142 |
| stay | 666 |

## Gate checks

| Check | Result |
|---|---|
| contract_valid | PASS |
| unique_ids | PASS |
| minimum_total_records | PASS |
| category_coverage | PASS |
| non_synthetic | PASS |
| licensed_source | PASS |

## Product-readiness checks

These checks are deliberately stricter than schema validity.

| Check | Result |
|---|---|
| opening_hours_coverage_at_least_50_percent | GAP |
| price_coverage_at_least_30_percent | GAP |
| manual_verification_coverage_at_least_20_percent | GAP |
| source_edit_within_3_years_at_least_70_percent | GAP |

## Field completeness

| Field | Present | Coverage |
|---|---:|---:|
| description | 2557 | 100.0% |
| address | 751 | 29.4% |
| area | 150 | 5.9% |
| opening_hours | 305 | 11.9% |
| phone | 304 | 11.9% |
| website | 191 | 7.5% |
| source_updated_at | 2557 | 100.0% |
| last_verified_at | 0 | 0.0% |
| price_min_vnd | 0 | 0.0% |

## Description provenance

| Origin | Records |
|---|---:|
| Supplied by source | 35 |
| Deterministically derived from OSM tags | 2522 |

## Source edit age

The OSM edit timestamp is not proof that a business is currently operating; it is only a staleness signal.

| Age at retrieval | Records |
|---|---:|
| 0-1 year | 453 |
| 1-3 years | 863 |
| 3-5 years | 135 |
| Over 5 years | 1106 |
| Unknown | 0 |

## Interpretation

Missing values are kept as `null`; the pipeline does not generate or guess facts.
Generic descriptions are deterministically derived from OSM category tags and labelled as such.
Repeated names are not automatically errors because chains can have multiple locations.
A missing `last_verified_at` means the venue has not been manually verified by this project.
Prices are intentionally absent unless a lawful, attributable source supplies them.
