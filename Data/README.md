# Data sources and licensing

## Default dataset: OpenStreetMap snapshot

`processed/places_osm_v2.jsonl` is a normalized snapshot of named food,
tourism, historic, and selected natural features in the Da Nang travel area.
It was built through the public Overpass API by `python -m
data_pipeline.build_dataset`.

- Source: [OpenStreetMap](https://www.openstreetmap.org/)
- Attribution: © OpenStreetMap contributors
- License: [Open Data Commons Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
- OSM copyright and attribution guidance: [openstreetmap.org/copyright](https://www.openstreetmap.org/copyright)
- Build metadata: `processed/places_osm_v2.meta.json`
- Quality report: `../docs/reports/data_quality_osm.md`

Passing the structural quality gates means the snapshot is valid, attributable,
and indexable. It does not mean the data is product-ready. The separate
product-readiness checks currently expose gaps in verification, prices,
opening hours, and source recency.

The bounding box is intentionally a Da Nang visitor region rather than a
claim about current administrative boundaries. Each record retains its OSM
element URL, element edit timestamp, retrieval timestamp, and license.

Missing facts remain `null`. In particular, OSM does not provide reliable
price coverage. The project does not invent a price or treat an OSM edit
timestamp as proof that a venue is currently operating.

## Legacy synthetic baseline

`data_danang_ok.csv` and the other original CSV files are retained unchanged.
The project owner confirmed that this material was generated rather than
collected from attributable venue sources. It is therefore useful only as a
legacy retrieval/evaluation baseline and must not be represented as verified
travel information.

To run that controlled baseline, explicitly set:

```bash
DATA_PATH=Data/data_danang_ok.csv ELASTICSEARCH_INDEX=places_danang_legacy \
python -m localguide_assistant.indexer
```

## Why Google Places is not the committed source

Google Places is useful for live product enrichment, but its content storage
and caching restrictions make it a poor fit for a reproducible dataset stored
in this repository. See the official [Google Maps Platform policies](https://developers.google.com/maps/documentation/places/web-service/policies).
It can be added later as an optional runtime provider with its own billing,
attribution, and retention controls; it is not mixed into this snapshot.

## Refreshing the snapshot

```bash
python -m data_pipeline.build_dataset
python -m data_pipeline.validate_dataset
python -m pytest -q
```

The builder writes the JSONL file, SHA-256 metadata, and quality report
atomically. A failed quality gate leaves no new default dataset behind.
