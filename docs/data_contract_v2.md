# Place data contract v2

The v2 contract separates searchable content, operational metadata, and
provenance. The canonical field order lives in `data_pipeline/schema.py` and
every JSONL row is validated before indexing.

## Identity and classification

| Field | Meaning |
|---|---|
| `schema_version` | Contract version; currently `2` |
| `id` | Stable project identifier (`osm_<element type>_<element id>`) |
| `type` | Product category: `eat`, `see`, or `stay` |
| `name`, `name_vi`, `name_en` | Display name and optional language variants |
| `categories`, `cuisine` | Source-derived keyword arrays |

## Facts used for retrieval and generation

| Field | Meaning |
|---|---|
| `description` | Source description or a deterministic label made from source tags |
| `description_origin` | `source` or `derived_from_tags` |
| `latitude`, `longitude` | WGS84 coordinates |
| `address`, `area` | Best-effort OSM address fields |
| `opening_hours` | Raw OSM opening-hours expression; never guessed |
| `phone`, `website` | Optional source contacts |
| `price_min_vnd`, `price_max_vnd` | Nullable integer VND values |
| `price_currency` | `VND`; does not imply that a price is known |
| `price_text` | Optional source-native price text; accepted only inside its TTL |
| `full_text` | Deterministic embedding/search text built from factual fields |

## Provenance and freshness

| Field | Meaning |
|---|---|
| `source`, `source_id`, `source_url` | Exact upstream record |
| `source_license` | License identifier for the record |
| `source_updated_at` | Upstream OSM element edit timestamp |
| `retrieved_at` | Snapshot retrieval time |
| `last_verified_at` | Manual project verification time; currently null |
| `is_synthetic` | Explicit synthetic-data marker |
| `field_provenance` | Per-enriched-field URL, revision, license, timestamps, and match score |
| `enrichment_sources` | Attribution records for the fields actually applied |

`source_updated_at` is a useful staleness signal, not evidence that a venue is
open or that every attribute is current. Product claims that need stronger
confidence should require `last_verified_at` or a policy-compliant live source.

The additive enrichment fields remain backward-compatible with the base v2
JSONL. A wiki page revision is not manual verification and never populates
`last_verified_at`.

## Index lifecycle

The index mapping stores the source dataset SHA-256 in Elasticsearch `_meta`.
Startup skips re-embedding only when both record count and fingerprint match.
When the snapshot changes, the derived index is rebuilt so records removed
from the source cannot remain searchable.
