# Enrichment and verification report

- Built at: `2026-07-21T19:29:52+00:00`
- Base records: **2557**
- Wikivoyage factual listings extracted: **78**
- High-confidence matches: **28**
- Places receiving at least one fresh field: **7**
- Manual verification queue: **200**
- Structural status: **PASS**
- Product readiness: **NEEDS ENRICHMENT**

## Matching policy

A match requires compatible product type, coordinates within 400 m, and a high name/distance score.
Each listing and OSM place can be used at most once. Ambiguous or coordinate-free listings are not applied.

## Field actions

| Field | Applied | Rejected as stale | Rejected: age unknown | Primary kept |
|---|---:|---:|---:|---:|
| address | 7 | 2 | 2 | 14 |
| opening_hours | 0 | 2 | 0 | 2 |
| phone | 0 | 7 | 0 | 5 |
| price_text | 0 | 14 | 0 | 0 |

## Safety rules

- Enrichment fills nulls only; it never overwrites an existing primary fact.
- TTL: price 180 days, opening hours 1 year, phone/website 2 years, address 5 years.
- `last_verified_at` remains null because a wiki revision is not manual verification.
- Wikivoyage prose (`content`) is intentionally not copied; only structured listing facts are retained.
- Every applied field stores its own source URL, revision, license, retrieval time, update time, and match score.

## Queue interpretation

The 200-place queue is balanced across eat/see/stay and ranked by missing high-impact fields,
attributable-source matches, and stale enrichment candidates. It is a curation workload, not a popularity ranking.

## Licensing

- Base data: © OpenStreetMap contributors, ODbL 1.0.
- Overlay: Wikivoyage contributors, CC BY-SA 4.0; author attribution is preserved through the immutable revision and page-history links.
