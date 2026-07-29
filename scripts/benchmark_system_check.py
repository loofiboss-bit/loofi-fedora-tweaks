#!/usr/bin/env python3
"""Benchmark the explicit read-only System Check against v19 release budgets."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "loofi-fedora-tweaks"
DEFAULT_REPORT = ROOT / "docs" / "reports" / "V19_PHASE6_CHECK_BENCHMARK.json"
sys.path.insert(0, str(SOURCE))

from core.system_check.service import SystemCheckService  # noqa: E402

SOURCE_MEDIAN_BUDGETS_MS = {
    "state-integrity": 250.0,
    "maintenance": 1200.0,
    "storage-reclaim": 500.0,
    "action-center": 250.0,
    "pending-reboot": 250.0,
}
TOTAL_MEDIAN_BUDGET_MS = 3500.0


def benchmark(
    runs: int,
    *,
    release_label: str = "v19 Steward working tree (metadata v18.0.0 Haven)",
) -> dict[str, Any]:
    if runs < 1:
        raise ValueError("runs must be positive")
    records: list[dict[str, Any]] = []
    for index in range(runs):
        service = SystemCheckService()
        started = time.monotonic()
        result = service.run(persist=False)
        records.append(
            {
                "run": index + 1,
                "state": result.state,
                "atomic": result.atomic,
                "wall_ms": round((time.monotonic() - started) * 1000.0, 3),
                "source_durations_ms": {
                    source: round(duration, 3)
                    for source, duration in result.source_durations_ms
                },
                "source_errors": [
                    error.to_dict() for error in result.source_errors
                ],
            }
        )

    source_medians = {
        source: round(
            statistics.median(
                record["source_durations_ms"][source]
                for record in records
                if source in record["source_durations_ms"]
            ),
            3,
        )
        for source in SOURCE_MEDIAN_BUDGETS_MS
    }
    total_median = round(
        statistics.median(record["wall_ms"] for record in records),
        3,
    )
    errors: list[str] = []
    for source, budget in SOURCE_MEDIAN_BUDGETS_MS.items():
        if source_medians[source] > budget:
            errors.append(
                f"{source} median {source_medians[source]:.3f} ms exceeds "
                f"{budget:.3f} ms"
            )
    if total_median > TOTAL_MEDIAN_BUDGET_MS:
        errors.append(
            f"total median {total_median:.3f} ms exceeds "
            f"{TOTAL_MEDIAN_BUDGET_MS:.3f} ms"
        )
    if any(record["state"] not in {"completed", "partial"} for record in records):
        errors.append("a measured check did not produce a readable terminal result")

    return {
        "schema_version": 1,
        "release": release_label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs": records,
        "source_medians_ms": source_medians,
        "source_median_budgets_ms": SOURCE_MEDIAN_BUDGETS_MS,
        "total_median_ms": total_median,
        "total_median_budget_ms": TOTAL_MEDIAN_BUDGET_MS,
        "persist": False,
        "status": "passed" if not errors else "failed",
        "errors": errors,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--release-label",
        default="v19 Steward working tree (metadata v18.0.0 Haven)",
        help="evidence label stored in the generated report",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = benchmark(args.runs, release_label=args.release_label)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "System Check median: "
        f"{payload['total_median_ms']:.3f} ms / "
        f"{payload['total_median_budget_ms']:.3f} ms"
    )
    for source, duration in payload["source_medians_ms"].items():
        print(
            f"- {source}: {duration:.3f} ms / "
            f"{payload['source_median_budgets_ms'][source]:.3f} ms"
        )
    for error in payload["errors"]:
        print(f"[system-check-benchmark] ERROR: {error}")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
