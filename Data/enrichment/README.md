# Wikivoyage factual overlay

`wikivoyage_da_nang_v1.jsonl` contains structured listing fields extracted
from an immutable revision of the English Wikivoyage Da Nang guide. It does
not copy listing prose (`content`). Exact revision, history, retrieval, and
license metadata are recorded in every row and in the enriched dataset
metadata.

- Source: [Da Nang – Wikivoyage](https://en.wikivoyage.org/wiki/Da_Nang)
- Authors: Wikivoyage contributors; use the page history link stored in the
  overlay for attribution details.
- License: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- API: MediaWiki Action API

The overlay is not treated as live truth. Field-level `lastedit` dates are
checked against TTL rules before any null is filled. A recent page revision
never substitutes for a missing listing `lastedit` date.

The enriched output contains material governed by both the OSM and Wikivoyage
licenses. Keeping the overlay and per-field provenance separate makes the
origin clear; downstream redistribution must continue to satisfy the
applicable attribution and share-alike terms.
