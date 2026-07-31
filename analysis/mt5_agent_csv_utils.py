from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from analysis.mt5_forward_report import server_datetime


def summarize_csv_source_time(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    rows = 0
    close_rows = 0
    close_rows_with_server_time = 0
    event_counts: dict[str, int] = {}
    first: datetime | None = None
    last: datetime | None = None
    try:
        with source.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                rows += 1
                event = str(row.get("event") or "").lower()
                event_counts[event] = event_counts.get(event, 0) + 1
                if event != "close":
                    continue
                close_rows += 1
                moment = server_datetime(row)
                if moment is None:
                    continue
                close_rows_with_server_time += 1
                first = moment if first is None or moment < first else first
                last = moment if last is None or moment > last else last
    except OSError as exc:
        return {
            "ok": False,
            "reason": str(exc),
            "rows": rows,
            "close_rows": close_rows,
            "close_rows_with_server_time": close_rows_with_server_time,
            "close_rows_without_server_time": max(close_rows - close_rows_with_server_time, 0),
            "first_server_time": "",
            "last_server_time": "",
            "event_counts": event_counts,
        }
    span_days = None
    if first is not None and last is not None:
        span_days = round((last - first).total_seconds() / 86400.0, 4)
    return {
        "ok": True,
        "rows": rows,
        "close_rows": close_rows,
        "close_rows_with_server_time": close_rows_with_server_time,
        "close_rows_without_server_time": close_rows - close_rows_with_server_time,
        "first_server_time": first.strftime("%Y.%m.%d %H:%M:%S") if first else "",
        "last_server_time": last.strftime("%Y.%m.%d %H:%M:%S") if last else "",
        "span_days": span_days,
        "event_counts": dict(sorted(event_counts.items())),
    }


def combined_source_time_coverage(files: list[dict[str, Any]]) -> dict[str, Any]:
    close_rows = 0
    with_server_time = 0
    without_server_time = 0
    first: datetime | None = None
    last: datetime | None = None
    for item in files:
        summary = item.get("source_time")
        if not isinstance(summary, dict):
            continue
        close_rows += int(summary.get("close_rows") or 0)
        with_server_time += int(summary.get("close_rows_with_server_time") or 0)
        without_server_time += int(summary.get("close_rows_without_server_time") or 0)
        first_moment = server_datetime({"server_time": str(summary.get("first_server_time") or "")})
        last_moment = server_datetime({"server_time": str(summary.get("last_server_time") or "")})
        if first_moment is not None:
            first = first_moment if first is None or first_moment < first else first
        if last_moment is not None:
            last = last_moment if last is None or last_moment > last else last
    span_days = None
    if first is not None and last is not None:
        span_days = round((last - first).total_seconds() / 86400.0, 4)
    return {
        "close_rows": close_rows,
        "close_rows_with_server_time": with_server_time,
        "close_rows_without_server_time": without_server_time,
        "first_server_time": first.strftime("%Y.%m.%d %H:%M:%S") if first else "",
        "last_server_time": last.strftime("%Y.%m.%d %H:%M:%S") if last else "",
        "span_days": span_days,
    }
