# Retrieval evaluation v1

- Run at: `2026-07-23T01:49:08+00:00`
- Dataset fingerprint: `3a0b2feaaac5fc426e41969ca1c8f997717287f929c9a33d09400722fe582518`
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- Candidate depth: **20**
- Discovery queries: **120**
- Name-lookup queries: **90**
- All runs use the Eat/See/Stay type filter supplied by the current UI context.

## Discovery

| Variant | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|
| bm25 | 0.292 | 0.533 | 0.650 | 0.425 |
| hybrid_rrf | 0.608 | 0.767 | 0.833 | 0.693 |
| vector | 0.583 | 0.775 | 0.800 | 0.670 |
| weighted_rrf_semantic_0.3 | 0.508 | 0.750 | 0.817 | 0.627 |
| weighted_rrf_semantic_0.5 | 0.600 | 0.767 | 0.850 | 0.693 |
| weighted_rrf_semantic_0.7 | 0.592 | 0.792 | 0.850 | 0.697 |

Measured winner: **weighted_rrf_semantic_0.7** by MRR@5, then Hit@3/Hit@5 tie-breaks.

## Name Lookup

| Variant | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|
| bm25 | 0.867 | 1.000 | 1.000 | 0.928 |
| hybrid_rrf | 0.944 | 0.978 | 0.989 | 0.963 |
| vector | 0.822 | 0.911 | 0.911 | 0.863 |
| weighted_rrf_semantic_0.3 | 0.956 | 0.978 | 0.989 | 0.969 |
| weighted_rrf_semantic_0.5 | 0.944 | 0.978 | 0.978 | 0.959 |
| weighted_rrf_semantic_0.7 | 0.878 | 0.956 | 0.967 | 0.918 |

Measured winner: **weighted_rrf_semantic_0.3** by MRR@5, then Hit@3/Hit@5 tie-breaks.

## Product decision

The discovery-track winner is **weighted_rrf_semantic_0.7**. Its MRR@5 is 0.697, versus 0.425 for BM25 (+0.272 absolute).

Recommended production strategy: **hybrid_rrf**.
Hybrid RRF robustly beats BM25; the tuned variant does not robustly beat standard RRF.

### Paired bootstrap comparisons (MRR@5)

| Comparison | Mean difference | 95% CI | P(diff > 0) |
|---|---:|---:|---:|
| weighted_rrf_semantic_0.7 vs bm25 | +0.272 | [+0.199, +0.346] | 1.000 |
| weighted_rrf_semantic_0.7 vs hybrid_rrf | +0.004 | [-0.026, +0.028] | 0.617 |
| hybrid_rrf vs bm25 | +0.269 | [+0.200, +0.339] | 1.000 |

This decision is based on the discovery track only. Name lookup is reported separately and is not mixed into the product headline.

## Evaluation boundaries

- Discovery relevance is weakly supervised by exact structured constraints, not human preference judgments.
- Queries about price are excluded because the current real dataset has no fresh price coverage.
- Subjective intents such as best, romantic, or family-friendly are excluded.
- Type filters simulate the current Eat/See/Stay UI context.
- No LLM judge or subjective human preference labels are used in this retrieval evaluation.
- A high score means retrieval satisfies the encoded structured constraint, not that a venue is objectively good or currently open.

## Constraint-level diagnostics

Machine-readable breakdowns for each discovery constraint live in `Data/evaluation/retrieval_summary_v1.json`.
Per-query first relevant ranks and top-five IDs live in `Data/evaluation/retrieval_details_v1.jsonl`.
