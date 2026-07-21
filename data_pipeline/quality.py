"""Validation and human-readable quality reporting for dataset v2."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import PLACE_FIELDS, validate_record


COMPLETENESS_FIELDS = (
    "description",
    "address",
    "area",
    "opening_hours",
    "phone",
    "website",
    "source_updated_at",
    "last_verified_at",
    "price_min_vnd",
)


def assess_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    ids: Counter[str] = Counter()
    names: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    for position, record in enumerate(records, start=1):
        ids[str(record.get("id"))] += 1
        names[str(record.get("name", "")).strip().casefold()] += 1
        type_counts[str(record.get("type"))] += 1
        violations = validate_record(record)
        if violations:
            errors.append(
                {"row": position, "id": record.get("id"), "errors": violations}
            )

    count = len(records)
    completeness = {
        field: {
            "count": sum(
                record.get(field) is not None and record.get(field) != ""
                for record in records
            ),
            "percent": (
                round(
                    100
                    * sum(
                        record.get(field) is not None and record.get(field) != ""
                        for record in records
                    )
                    / count,
                    1,
                )
                if count
                else 0.0
            ),
        }
        for field in COMPLETENESS_FIELDS
    }
    duplicate_ids = sorted(
        value for value, occurrences in ids.items() if occurrences > 1
    )
    repeated_names = sorted(
        value for value, occurrences in names.items() if value and occurrences > 1
    )
    checks = {
        "contract_valid": not errors,
        "unique_ids": not duplicate_ids,
        "minimum_total_records": count >= 100,
        "category_coverage": all(
            type_counts.get(place_type, 0) >= minimum
            for place_type, minimum in {"eat": 40, "see": 15, "stay": 20}.items()
        ),
        "non_synthetic": all(record.get("is_synthetic") is False for record in records),
        "licensed_source": all(record.get("source_license") for record in records),
    }
    source_descriptions = sum(
        record.get("description_origin") == "source" for record in records
    )
    retrieved_values = [
        datetime.fromisoformat(str(record["retrieved_at"]).replace("Z", "+00:00"))
        for record in records
        if record.get("retrieved_at")
    ]
    reference_time = max(retrieved_values) if retrieved_values else None
    freshness = Counter()
    for record in records:
        updated_at = record.get("source_updated_at")
        if not updated_at or reference_time is None:
            freshness["unknown"] += 1
            continue
        updated = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
        age_days = (reference_time - updated).days
        if age_days <= 365:
            freshness["0_to_1_year"] += 1
        elif age_days <= 3 * 365:
            freshness["1_to_3_years"] += 1
        elif age_days <= 5 * 365:
            freshness["3_to_5_years"] += 1
        else:
            freshness["over_5_years"] += 1

    recent_edit_count = freshness["0_to_1_year"] + freshness["1_to_3_years"]
    product_checks = {
        "opening_hours_coverage_at_least_50_percent": completeness["opening_hours"][
            "percent"
        ]
        >= 50.0,
        "price_coverage_at_least_30_percent": completeness["price_min_vnd"]["percent"]
        >= 30.0,
        "manual_verification_coverage_at_least_20_percent": completeness[
            "last_verified_at"
        ]["percent"]
        >= 20.0,
        "source_edit_within_3_years_at_least_70_percent": (
            (100 * recent_edit_count / count) if count else 0.0
        )
        >= 70.0,
    }

    return {
        "status": "pass" if all(checks.values()) else "fail",
        "product_readiness": (
            "ready" if all(product_checks.values()) else "needs_enrichment"
        ),
        "record_count": count,
        "type_counts": dict(sorted(type_counts.items())),
        "checks": checks,
        "product_checks": product_checks,
        "completeness": completeness,
        "description_provenance": {
            "from_source": source_descriptions,
            "derived_from_tags": count - source_descriptions,
        },
        "source_edit_age": dict(freshness),
        "duplicate_ids": duplicate_ids,
        "repeated_name_count": len(repeated_names),
        "sample_repeated_names": repeated_names[:20],
        "contract_errors": errors[:50],
    }


def render_markdown(
    report: dict[str, Any], *, dataset_path: str, retrieved_at: str
) -> str:
    status = "PASS" if report["status"] == "pass" else "FAIL"
    readiness = (
        "READY" if report["product_readiness"] == "ready" else "NEEDS ENRICHMENT"
    )
    lines = [
        "# OSM dataset quality report",
        "",
        f"- Structural/contract status: **{status}**",
        f"- Product readiness: **{readiness}**",
        f"- Dataset: `{dataset_path}`",
        f"- Retrieved at: `{retrieved_at}`",
        f"- Records: **{report['record_count']}**",
        "- Source: OpenStreetMap contributors (ODbL 1.0)",
        "",
        "## Category coverage",
        "",
        "| Type | Records |",
        "|---|---:|",
    ]
    for place_type in ("eat", "see", "stay"):
        lines.append(f"| {place_type} | {report['type_counts'].get(place_type, 0)} |")
    lines.extend(["", "## Gate checks", "", "| Check | Result |", "|---|---|"])
    for check, passed in report["checks"].items():
        lines.append(f"| {check} | {'PASS' if passed else 'FAIL'} |")
    lines.extend(
        [
            "",
            "## Product-readiness checks",
            "",
            "These checks are deliberately stricter than schema validity.",
            "",
            "| Check | Result |",
            "|---|---|",
        ]
    )
    for check, passed in report["product_checks"].items():
        lines.append(f"| {check} | {'PASS' if passed else 'GAP'} |")
    lines.extend(
        [
            "",
            "## Field completeness",
            "",
            "| Field | Present | Coverage |",
            "|---|---:|---:|",
        ]
    )
    for field, metric in report["completeness"].items():
        lines.append(f"| {field} | {metric['count']} | {metric['percent']}% |")
    lines.extend(
        [
            "",
            "## Description provenance",
            "",
            "| Origin | Records |",
            "|---|---:|",
            f"| Supplied by source | {report['description_provenance']['from_source']} |",
            f"| Deterministically derived from OSM tags | {report['description_provenance']['derived_from_tags']} |",
            "",
            "## Source edit age",
            "",
            "The OSM edit timestamp is not proof that a business is currently operating; it is only a staleness signal.",
            "",
            "| Age at retrieval | Records |",
            "|---|---:|",
            f"| 0-1 year | {report['source_edit_age'].get('0_to_1_year', 0)} |",
            f"| 1-3 years | {report['source_edit_age'].get('1_to_3_years', 0)} |",
            f"| 3-5 years | {report['source_edit_age'].get('3_to_5_years', 0)} |",
            f"| Over 5 years | {report['source_edit_age'].get('over_5_years', 0)} |",
            f"| Unknown | {report['source_edit_age'].get('unknown', 0)} |",
        ]
    )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Missing values are kept as `null`; the pipeline does not generate or guess facts.",
            "Generic descriptions are deterministically derived from OSM category tags and labelled as such.",
            "Repeated names are not automatically errors because chains can have multiple locations.",
            "A missing `last_verified_at` means the venue has not been manually verified by this project.",
            "Prices are intentionally absent unless a lawful, attributable source supplies them.",
            "",
        ]
    )
    if report["contract_errors"]:
        lines.extend(
            [
                "## Contract errors",
                "",
                "```json",
                json.dumps(report["contract_errors"], ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"Line {line_number} is not a JSON object")
                records.append(value)
    return records
