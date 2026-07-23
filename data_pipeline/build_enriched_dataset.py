"""Build a provenance-aware enrichment overlay and a 200-place review queue."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .build_dataset import _atomic_write, write_jsonl
from .enrichment import (
    apply_enrichment,
    build_verification_queue,
    match_listings,
    write_queue,
)
from .quality import assess_records, load_jsonl
from .wikivoyage import PAGE_TITLE, extract_listings, fetch_page


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = PROJECT_ROOT / "Data/processed/places_osm_v2.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "Data/processed/places_enriched_v2.jsonl"
DEFAULT_OVERLAY = PROJECT_ROOT / "Data/enrichment/wikivoyage_da_nang_v1.jsonl"
DEFAULT_METADATA = PROJECT_ROOT / "Data/processed/places_enriched_v2.meta.json"
DEFAULT_QUEUE = PROJECT_ROOT / "Data/curation/verification_queue_v1.csv"
DEFAULT_REPORT = PROJECT_ROOT / "docs/reports/enrichment_report.md"


def _field_counts(events: list[dict[str, Any]], action: str) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                event["field"] for event in events if event["action"] == action
            ).items()
        )
    )


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Enrichment and verification report",
        "",
        f"- Built at: `{summary['built_at']}`",
        f"- Base records: **{summary['base_record_count']}**",
        f"- Wikivoyage factual listings extracted: **{summary['listing_count']}**",
        f"- High-confidence matches: **{summary['match_count']}**",
        f"- Places receiving at least one fresh field: **{summary['enriched_place_count']}**",
        f"- Manual verification queue: **{summary['queue_count']}**",
        f"- Structural status: **{summary['quality_status'].upper()}**",
        f"- Product readiness: **{summary['product_readiness'].replace('_', ' ').upper()}**",
        "",
        "## Matching policy",
        "",
        "A match requires compatible product type, coordinates within 400 m, and a high name/distance score.",
        "Each listing and OSM place can be used at most once. Ambiguous or coordinate-free listings are not applied.",
        "",
        "## Field actions",
        "",
        "| Field | Applied | Rejected as stale | Rejected: age unknown | Primary kept |",
        "|---|---:|---:|---:|---:|",
    ]
    fields = sorted(
        set(summary["applied_fields"])
        | set(summary["stale_fields"])
        | set(summary["unknown_age_fields"])
        | set(summary["primary_kept_fields"])
    )
    for field in fields:
        lines.append(
            f"| {field} | {summary['applied_fields'].get(field, 0)} | "
            f"{summary['stale_fields'].get(field, 0)} | "
            f"{summary['unknown_age_fields'].get(field, 0)} | "
            f"{summary['primary_kept_fields'].get(field, 0)} |"
        )
    lines.extend(
        [
            "",
            "## Safety rules",
            "",
            "- Enrichment fills nulls only; it never overwrites an existing primary fact.",
            "- TTL: price 180 days, opening hours 1 year, phone/website 2 years, address 5 years.",
            "- `last_verified_at` remains null because a wiki revision is not manual verification.",
            "- Wikivoyage prose (`content`) is intentionally not copied; only structured listing facts are retained.",
            "- Every applied field stores its own source URL, revision, license, retrieval time, update time, and match score.",
            "",
            "## Queue interpretation",
            "",
            "The 200-place queue is balanced across eat/see/stay and ranked by missing high-impact fields,",
            "attributable-source matches, and stale enrichment candidates. It is a curation workload, not a popularity ranking.",
            "",
            "## Licensing",
            "",
            "- Base data: © OpenStreetMap contributors, ODbL 1.0.",
            "- Overlay: Wikivoyage contributors, CC BY-SA 4.0; author attribution is preserved through the immutable revision and page-history links.",
            "",
        ]
    )
    return "\n".join(lines)


def build(
    *,
    base_path: Path,
    output_path: Path,
    overlay_path: Path,
    metadata_path: Path,
    queue_path: Path,
    report_path: Path,
    target_count: int = 200,
    input_wikitext: Path | None = None,
) -> dict[str, Any]:
    places = load_jsonl(base_path)
    if input_wikitext:
        built_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        page = {
            "title": PAGE_TITLE,
            "wikitext": input_wikitext.read_text(encoding="utf-8"),
            "revision_id": 0,
            "revision_at": built_at,
            "retrieved_at": built_at,
            "source_url": "fixture://wikivoyage/Da_Nang",
            "history_url": "fixture://wikivoyage/Da_Nang/history",
            "source_license": "CC-BY-SA-4.0",
            "attribution": "Wikivoyage fixture contributors",
        }
    else:
        page = fetch_page(title=PAGE_TITLE)
        built_at = page["retrieved_at"]

    listings = extract_listings(page)
    matches = match_listings(places, listings)
    enriched, events = apply_enrichment(places, listings, matches)
    queue = build_verification_queue(
        enriched, listings, matches, events, target_count=target_count
    )
    quality = assess_records(enriched)
    if quality["status"] != "pass":
        raise RuntimeError("Enriched dataset failed structural quality gates")

    output_sha256 = write_jsonl(output_path, enriched)
    overlay_sha256 = write_jsonl(overlay_path, listings)
    write_queue(queue_path, queue)
    enriched_place_ids = {
        event["place_id"] for event in events if event["action"] == "applied"
    }
    summary = {
        "schema_version": 2,
        "built_at": built_at,
        "base_dataset": str(base_path.relative_to(PROJECT_ROOT)),
        "base_dataset_sha256": hashlib.sha256(base_path.read_bytes()).hexdigest(),
        "output_dataset": str(output_path.relative_to(PROJECT_ROOT)),
        "output_dataset_sha256": output_sha256,
        "overlay_dataset": str(overlay_path.relative_to(PROJECT_ROOT)),
        "overlay_dataset_sha256": overlay_sha256,
        "base_record_count": len(places),
        "listing_count": len(listings),
        "match_count": len(matches),
        "enriched_place_count": len(enriched_place_ids),
        "queue_count": len(queue),
        "queue_type_counts": dict(
            sorted(Counter(row["type"] for row in queue).items())
        ),
        "applied_fields": _field_counts(events, "applied"),
        "stale_fields": _field_counts(events, "rejected_stale"),
        "unknown_age_fields": _field_counts(events, "rejected_unknown_age"),
        "primary_kept_fields": _field_counts(events, "kept_primary"),
        "quality_status": quality["status"],
        "product_readiness": quality["product_readiness"],
        "wikivoyage": {
            key: page[key]
            for key in (
                "title",
                "revision_id",
                "revision_at",
                "retrieved_at",
                "source_url",
                "history_url",
                "source_license",
                "attribution",
            )
        },
    }
    _atomic_write(
        metadata_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(report_path, render_report(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overlay", type=Path, default=DEFAULT_OVERLAY)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--target-count", type=int, default=200)
    parser.add_argument("--input-wikitext", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.target_count <= 0:
        print("--target-count must be positive", file=sys.stderr)
        return 2
    try:
        summary = build(
            base_path=args.base,
            output_path=args.output,
            overlay_path=args.overlay,
            metadata_path=args.metadata,
            queue_path=args.queue,
            report_path=args.report,
            target_count=args.target_count,
            input_wikitext=args.input_wikitext,
        )
    except Exception as error:
        print(f"Enrichment build failed: {error}", file=sys.stderr)
        return 1
    print(
        f"Extracted {summary['listing_count']} listings, matched {summary['match_count']}, "
        f"enriched {summary['enriched_place_count']} places, queued {summary['queue_count']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
