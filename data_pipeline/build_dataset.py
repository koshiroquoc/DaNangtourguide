"""Build the real-world Da Nang dataset from OpenStreetMap."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .osm import DEFAULT_BBOX, DEFAULT_OVERPASS_URL, fetch_overpass, normalize_response
from .quality import assess_records, render_markdown


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "Data/processed/places_osm_v2.jsonl"
DEFAULT_METADATA = PROJECT_ROOT / "Data/processed/places_osm_v2.meta.json"
DEFAULT_REPORT = PROJECT_ROOT / "docs/reports/data_quality_osm.md"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> str:
    content = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        for record in records
    )
    _atomic_write(path, content)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build(
    *,
    bbox: tuple[float, float, float, float],
    endpoint: str,
    output_path: Path,
    metadata_path: Path,
    report_path: Path,
    input_json: Path | None = None,
) -> dict[str, Any]:
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if input_json:
        payload = json.loads(input_json.read_text(encoding="utf-8"))
        origin = str(input_json)
    else:
        payload = fetch_overpass(bbox=bbox, endpoint=endpoint)
        origin = endpoint
    records = normalize_response(payload, retrieved_at=retrieved_at)
    report = assess_records(records)
    if report["status"] != "pass":
        raise RuntimeError(
            "Dataset failed quality gates: "
            + ", ".join(name for name, passed in report["checks"].items() if not passed)
        )

    digest = write_jsonl(output_path, records)
    metadata = {
        "schema_version": 2,
        "dataset_sha256": digest,
        "record_count": len(records),
        "retrieved_at": retrieved_at,
        "bbox": list(bbox),
        "source": "OpenStreetMap",
        "source_origin": origin,
        "source_license": "ODbL-1.0",
        "attribution": "© OpenStreetMap contributors",
        "quality_status": report["status"],
        "product_readiness": report["product_readiness"],
    }
    _atomic_write(
        metadata_path,
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(
        report_path,
        render_markdown(
            report,
            dataset_path=str(output_path.relative_to(PROJECT_ROOT)),
            retrieved_at=retrieved_at,
        ),
    )
    return metadata


def _bbox(value: str) -> tuple[float, float, float, float]:
    try:
        result = tuple(float(item.strip()) for item in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("bbox must contain four numbers") from error
    if len(result) != 4:
        raise argparse.ArgumentTypeError("bbox must be south,west,north,east")
    south, west, north, east = result
    if south >= north or west >= east:
        raise argparse.ArgumentTypeError("bbox south/west must be below north/east")
    return result  # type: ignore[return-value]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bbox", type=_bbox, default=DEFAULT_BBOX, help="south,west,north,east"
    )
    parser.add_argument("--endpoint", default=DEFAULT_OVERPASS_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--input-json",
        type=Path,
        help="Use a saved Overpass response instead of the network",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        metadata = build(
            bbox=args.bbox,
            endpoint=args.endpoint,
            output_path=args.output,
            metadata_path=args.metadata,
            report_path=args.report,
            input_json=args.input_json,
        )
    except Exception as error:
        print(f"Dataset build failed: {error}", file=sys.stderr)
        return 1
    print(
        f"Built {metadata['record_count']} records ({metadata['dataset_sha256'][:12]}...)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
