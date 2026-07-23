"""Run the retrieval grid against a fingerprint-matched Elasticsearch index."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_pipeline.build_dataset import _atomic_write
from data_pipeline.quality import load_jsonl
from evaluation.metrics import (
    aggregate_metrics,
    paired_bootstrap_difference,
    query_metrics,
    weighted_rank_fusion,
)
from localguide_assistant.config import Settings
from localguide_assistant.retrieval import PlaceRetriever, reciprocal_rank_fusion


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "Data/evaluation/manifest_v1.json"
DEFAULT_SUMMARY = PROJECT_ROOT / "Data/evaluation/retrieval_summary_v1.json"
DEFAULT_DETAILS = PROJECT_ROOT / "Data/evaluation/retrieval_details_v1.jsonl"
DEFAULT_REPORT = PROJECT_ROOT / "docs/reports/retrieval_evaluation_v1.md"
SEMANTIC_WEIGHTS = (0.3, 0.5, 0.7)
CUTOFFS = (1, 3, 5)


def _load_queries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    queries: list[dict[str, Any]] = []
    for track in ("discovery", "name_lookup"):
        path = PROJECT_ROOT / manifest["tracks"][track]["path"]
        queries.extend(load_jsonl(path))
    return queries


def _document_ids(hits: list[dict[str, Any]]) -> list[str]:
    return [str(hit["id"]) for hit in hits]


def _variant_rankings(
    lexical: list[dict[str, Any]],
    semantic: list[dict[str, Any]],
    *,
    candidate_count: int,
) -> dict[str, list[str]]:
    rankings = {
        "bm25": _document_ids(lexical),
        "vector": _document_ids(semantic),
        "hybrid_rrf": _document_ids(
            reciprocal_rank_fusion(
                lexical, semantic, rank_constant=60, top_k=candidate_count
            )
        ),
    }
    for weight in SEMANTIC_WEIGHTS:
        name = f"weighted_rrf_semantic_{weight:.1f}"
        rankings[name] = _document_ids(
            weighted_rank_fusion(
                lexical,
                semantic,
                semantic_weight=weight,
                rank_constant=60,
                top_k=candidate_count,
            )
        )
    return rankings


def _check_index_fingerprint(
    retriever: PlaceRetriever, manifest: dict[str, Any]
) -> None:
    index_name = retriever.settings.index_name
    if not retriever.es.indices.exists(index=index_name):
        raise RuntimeError(f"Elasticsearch index does not exist: {index_name}")
    mapping = retriever.es.indices.get_mapping(index=index_name)
    indexed_sha256 = (
        mapping.get(index_name, {})
        .get("mappings", {})
        .get("_meta", {})
        .get("dataset_sha256")
    )
    if indexed_sha256 != manifest["dataset_sha256"]:
        raise RuntimeError(
            "Evaluation dataset fingerprint does not match Elasticsearch: "
            f"manifest={manifest['dataset_sha256'][:12]}, "
            f"index={str(indexed_sha256)[:12]}. Re-run the indexer first."
        )


def _aggregate(
    details: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    by_track: dict[str, dict[str, list[dict[str, float]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    by_constraint: dict[str, dict[str, dict[str, list[dict[str, float]]]]] = (
        defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    )
    for detail in details:
        for variant, metrics in detail["metrics"].items():
            by_track[detail["track"]][variant].append(metrics)
            by_constraint[detail["track"]][detail["constraint_kind"]][variant].append(
                metrics
            )
    track_summary = {
        track: {
            variant: aggregate_metrics(metrics)
            for variant, metrics in sorted(variants.items())
        }
        for track, variants in sorted(by_track.items())
    }
    constraint_summary = {
        track: {
            constraint: {
                variant: aggregate_metrics(metrics)
                for variant, metrics in sorted(variants.items())
            }
            for constraint, variants in sorted(constraints.items())
        }
        for track, constraints in sorted(by_constraint.items())
    }
    return track_summary, constraint_summary


def _winner(track_summary: dict[str, Any], track: str) -> str:
    return max(
        track_summary[track],
        key=lambda variant: (
            track_summary[track][variant]["mrr@5"],
            track_summary[track][variant]["hit_rate@3"],
            track_summary[track][variant]["hit_rate@5"],
            variant == "bm25",
        ),
    )


def _metric_values(
    details: list[dict[str, Any]], *, track: str, variant: str, metric: str
) -> list[float]:
    return [
        detail["metrics"][variant][metric]
        for detail in details
        if detail["track"] == track
    ]


def _comparison(
    details: list[dict[str, Any]], *, challenger: str, baseline: str
) -> dict[str, Any]:
    result = paired_bootstrap_difference(
        _metric_values(
            details,
            track="discovery",
            variant=challenger,
            metric="mrr@5",
        ),
        _metric_values(
            details,
            track="discovery",
            variant=baseline,
            metric="mrr@5",
        ),
    )
    return {
        "challenger": challenger,
        "baseline": baseline,
        "metric": "mrr@5",
        **result,
    }


def _recommend_default(
    *, winner: str, winner_vs_rrf: dict[str, Any], rrf_vs_bm25: dict[str, Any]
) -> tuple[str, str]:
    if winner == "bm25":
        return "bm25", "BM25 is the measured discovery winner."
    if winner != "hybrid_rrf" and winner_vs_rrf["ci_95_lower"] > 0:
        return (
            winner,
            "The tuned winner beats standard RRF with a positive paired 95% CI.",
        )
    if rrf_vs_bm25["ci_95_lower"] > 0:
        return (
            "hybrid_rrf",
            "Hybrid RRF robustly beats BM25; the tuned variant does not robustly beat standard RRF.",
        )
    return "bm25", "No hybrid variant shows a robust paired improvement over BM25."


def render_report(summary: dict[str, Any], manifest: dict[str, Any]) -> str:
    lines = [
        "# Retrieval evaluation v1",
        "",
        f"- Run at: `{summary['run']['started_at']}`",
        f"- Dataset fingerprint: `{summary['run']['dataset_sha256']}`",
        f"- Embedding model: `{summary['run']['embedding_model']}`",
        f"- Candidate depth: **{summary['run']['candidate_count']}**",
        f"- Discovery queries: **{summary['run']['track_query_counts']['discovery']}**",
        f"- Name-lookup queries: **{summary['run']['track_query_counts']['name_lookup']}**",
        "- All runs use the Eat/See/Stay type filter supplied by the current UI context.",
        "",
    ]
    for track in ("discovery", "name_lookup"):
        lines.extend(
            [
                f"## {track.replace('_', ' ').title()}",
                "",
                "| Variant | Hit@1 | Hit@3 | Hit@5 | MRR@5 |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for variant, metrics in sorted(summary["tracks"][track].items()):
            lines.append(
                f"| {variant} | {metrics['hit_rate@1']:.3f} | "
                f"{metrics['hit_rate@3']:.3f} | {metrics['hit_rate@5']:.3f} | "
                f"{metrics['mrr@5']:.3f} |"
            )
        winner = summary["winners"][track]
        lines.extend(
            [
                "",
                f"Measured winner: **{winner}** by MRR@5, then Hit@3/Hit@5 tie-breaks.",
                "",
            ]
        )

    discovery_winner = summary["winners"]["discovery"]
    recommended = summary["recommended_default"]["variant"]
    bm25 = summary["tracks"]["discovery"]["bm25"]
    winner_metrics = summary["tracks"]["discovery"][discovery_winner]
    lines.extend(
        [
            "## Product decision",
            "",
            f"The discovery-track winner is **{discovery_winner}**. Its MRR@5 is "
            f"{winner_metrics['mrr@5']:.3f}, versus {bm25['mrr@5']:.3f} for BM25 "
            f"({winner_metrics['mrr@5'] - bm25['mrr@5']:+.3f} absolute).",
            "",
            f"Recommended production strategy: **{recommended}**.",
            summary["recommended_default"]["reason"],
            "",
            "### Paired bootstrap comparisons (MRR@5)",
            "",
            "| Comparison | Mean difference | 95% CI | P(diff > 0) |",
            "|---|---:|---:|---:|",
        ]
    )
    for comparison in summary["comparisons"]["discovery"]:
        lines.append(
            f"| {comparison['challenger']} vs {comparison['baseline']} | "
            f"{comparison['mean_difference']:+.3f} | "
            f"[{comparison['ci_95_lower']:+.3f}, {comparison['ci_95_upper']:+.3f}] | "
            f"{comparison['probability_positive']:.3f} |"
        )
    lines.extend(
        [
            "",
            "This decision is based on the discovery track only. Name lookup is reported separately and is not mixed into the product headline.",
            "",
            "## Evaluation boundaries",
            "",
        ]
    )
    lines.extend(f"- {limitation}" for limitation in manifest["limitations"])
    lines.extend(
        [
            "- No LLM judge or subjective human preference labels are used in this retrieval evaluation.",
            "- A high score means retrieval satisfies the encoded structured constraint, not that a venue is objectively good or currently open.",
            "",
            "## Constraint-level diagnostics",
            "",
            "Machine-readable breakdowns for each discovery constraint live in `Data/evaluation/retrieval_summary_v1.json`.",
            "Per-query first relevant ranks and top-five IDs live in `Data/evaluation/retrieval_details_v1.jsonl`.",
            "",
        ]
    )
    return "\n".join(lines)


def run(
    *,
    manifest_path: Path,
    summary_path: Path,
    details_path: Path,
    report_path: Path,
    candidate_count: int,
    limit_per_track: int | None = None,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    queries = _load_queries(manifest)
    if limit_per_track:
        limited: list[dict[str, Any]] = []
        for track in ("discovery", "name_lookup"):
            limited.extend(
                [query for query in queries if query["track"] == track][
                    :limit_per_track
                ]
            )
        queries = limited

    settings = Settings.from_env()
    retriever = PlaceRetriever(settings)
    _check_index_fingerprint(retriever, manifest)

    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    started = time.perf_counter()
    details: list[dict[str, Any]] = []
    for position, query in enumerate(queries, start=1):
        lexical = retriever.bm25_search(
            query["query"],
            top_k=candidate_count,
            type_filter=query["type_filter"],
        )
        semantic = retriever.vector_search(
            query["query"],
            top_k=candidate_count,
            type_filter=query["type_filter"],
        )
        rankings = _variant_rankings(lexical, semantic, candidate_count=candidate_count)
        relevant_ids = set(query["relevant_ids"])
        metrics = {
            variant: query_metrics(ranking, relevant_ids, cutoffs=CUTOFFS)
            for variant, ranking in rankings.items()
        }
        first_ranks = {
            variant: next(
                (
                    rank
                    for rank, document_id in enumerate(ranking, start=1)
                    if document_id in relevant_ids
                ),
                None,
            )
            for variant, ranking in rankings.items()
        }
        details.append(
            {
                "query_id": query["query_id"],
                "track": query["track"],
                "constraint_kind": query["constraint_kind"],
                "query": query["query"],
                "type_filter": query["type_filter"],
                "relevance_count": query["relevance_count"],
                "metrics": metrics,
                "first_relevant_ranks": first_ranks,
                "top_5_ids": {
                    variant: ranking[:5] for variant, ranking in rankings.items()
                },
            }
        )
        if position % 25 == 0 or position == len(queries):
            print(f"Evaluated {position}/{len(queries)} queries.")

    track_summary, constraint_summary = _aggregate(details)
    track_counts = {
        track: sum(detail["track"] == track for detail in details)
        for track in ("discovery", "name_lookup")
    }
    winners = {
        track: _winner(track_summary, track) for track in ("discovery", "name_lookup")
    }
    winner_vs_bm25 = _comparison(
        details, challenger=winners["discovery"], baseline="bm25"
    )
    winner_vs_rrf = _comparison(
        details, challenger=winners["discovery"], baseline="hybrid_rrf"
    )
    rrf_vs_bm25 = _comparison(details, challenger="hybrid_rrf", baseline="bm25")
    recommended_variant, recommendation_reason = _recommend_default(
        winner=winners["discovery"],
        winner_vs_rrf=winner_vs_rrf,
        rrf_vs_bm25=rrf_vs_bm25,
    )
    summary = {
        "version": 1,
        "run": {
            "started_at": started_at,
            "duration_seconds": round(time.perf_counter() - started, 2),
            "dataset_sha256": manifest["dataset_sha256"],
            "index_name": settings.index_name,
            "embedding_model": settings.embedding_model,
            "candidate_count": candidate_count,
            "track_query_counts": track_counts,
        },
        "tracks": track_summary,
        "by_constraint": constraint_summary,
        "winners": winners,
        "comparisons": {"discovery": [winner_vs_bm25, winner_vs_rrf, rrf_vs_bm25]},
        "recommended_default": {
            "variant": recommended_variant,
            "reason": recommendation_reason,
        },
    }
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    detail_content = "".join(
        json.dumps(detail, ensure_ascii=False, sort_keys=True) + "\n"
        for detail in details
    )
    _atomic_write(details_path, detail_content)
    _atomic_write(report_path, render_report(summary, manifest))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--details", type=Path, default=DEFAULT_DETAILS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--candidate-count", type=int, default=20)
    parser.add_argument("--limit-per-track", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.candidate_count < max(CUTOFFS):
        print(f"--candidate-count must be at least {max(CUTOFFS)}", file=sys.stderr)
        return 2
    if args.limit_per_track is not None and args.limit_per_track <= 0:
        print("--limit-per-track must be positive", file=sys.stderr)
        return 2
    try:
        summary = run(
            manifest_path=args.manifest,
            summary_path=args.summary,
            details_path=args.details,
            report_path=args.report,
            candidate_count=args.candidate_count,
            limit_per_track=args.limit_per_track,
        )
    except Exception as error:
        print(f"Retrieval evaluation failed: {error}", file=sys.stderr)
        return 1
    print(
        "Winners: "
        + ", ".join(
            f"{track}={variant}" for track, variant in summary["winners"].items()
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
