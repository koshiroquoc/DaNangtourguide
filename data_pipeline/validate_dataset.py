"""Revalidate an existing v2 JSONL snapshot and refresh its reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .build_dataset import (
    DEFAULT_METADATA,
    DEFAULT_OUTPUT,
    DEFAULT_REPORT,
    _atomic_write,
)
from .quality import assess_records, load_jsonl, render_markdown


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def validate_dataset(
    *, dataset_path: Path, metadata_path: Path, report_path: Path
) -> dict:
    records = load_jsonl(dataset_path)
    report = assess_records(records)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    if metadata.get("dataset_sha256") != digest:
        raise ValueError("Dataset SHA-256 does not match its build metadata")
    retrieved_at = str(metadata["retrieved_at"])
    metadata.update(
        {
            "record_count": len(records),
            "quality_status": report["status"],
            "product_readiness": report["product_readiness"],
        }
    )
    _atomic_write(
        metadata_path,
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(
        report_path,
        render_markdown(
            report,
            dataset_path=str(dataset_path.relative_to(PROJECT_ROOT)),
            retrieved_at=retrieved_at,
        ),
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    try:
        report = validate_dataset(
            dataset_path=args.dataset,
            metadata_path=args.metadata,
            report_path=args.report,
        )
    except Exception as error:
        print(f"Dataset validation failed: {error}", file=sys.stderr)
        return 1
    print(
        f"Validated {report['record_count']} records: "
        f"contract={report['status']}, product={report['product_readiness']}."
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
