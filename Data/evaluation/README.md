# Retrieval evaluation datasets

The current evaluation has two tracks that must be reported separately:

- `discovery_v1.jsonl`: 120 name-free queries judged by exact structured
  constraints. Every query has 2–100 relevant place IDs.
- `name_lookup_v1.jsonl`: 90 explicit venue-name queries judged by exact
  normalized-name groups.

`manifest_v1.json` fingerprints both tracks and the exact source dataset. The
runner refuses to evaluate an Elasticsearch index whose dataset SHA-256 does
not match the manifest.

Discovery constraints cover category, cuisine, district, category+district,
cuisine+district, and exact 24/7 opening-hours tags. The Eat/See/Stay type
filter simulates the current application UI. Price and subjective intents are
excluded because the real dataset cannot support trustworthy relevance
judgments for them.

The discovery labels are deterministic weak supervision, not human preference
judgments. They measure whether retrieval satisfies an encoded factual facet;
they do not establish that a venue is good, open, affordable, or popular.

## Reproduce

With the fingerprint-matched Elasticsearch index running:

```bash
python -m evaluation.build_sets
python -m evaluation.run_retrieval
```

Outputs:

- `retrieval_summary_v1.json`: aggregate and constraint-level metrics;
- `retrieval_details_v1.jsonl`: per-query ranks and top-five IDs;
- `docs/reports/retrieval_evaluation_v1.md`: human-readable report.
