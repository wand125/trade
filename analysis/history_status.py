from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT


EXPECTED_BARS_PER_HOUR = {
    "M1": 60,
    "M5": 12,
    "M15": 4,
    "M30": 2,
}


def history_status(
    history_path: str | Path,
    *,
    done_path: str | Path | None = None,
    min_coverage_ratio: float = 0.98,
) -> dict[str, Any]:
    payload = load_json(history_path)
    hours = int(payload.get("history_hours", 0) or 0)
    top_level_bars = payload.get("bars") if isinstance(payload.get("bars"), list) else []
    raw_timeframes = payload.get("timeframes") if isinstance(payload.get("timeframes"), dict) else {}

    timeframes: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for timeframe, per_hour in EXPECTED_BARS_PER_HOUR.items():
        obj = raw_timeframes.get(timeframe)
        bars = obj.get("bars") if isinstance(obj, dict) and isinstance(obj.get("bars"), list) else []
        expected = hours * per_hour if hours > 0 else 0
        ratio = (len(bars) / expected) if expected else 0.0
        complete = expected > 0 and ratio >= min_coverage_ratio
        if not bars:
            warnings.append(f"{timeframe} full bars are missing; do not use top-level bars as a replacement")
        elif expected and not complete:
            warnings.append(f"{timeframe} has only {len(bars)} bars; expected about {expected}")
        timeframes[timeframe] = {
            "bars": len(bars),
            "expected_bars": expected,
            "coverage_ratio": round(ratio, 4) if expected else 0.0,
            "complete": complete,
            "first_time": str(bars[0].get("time", "")) if bars else "",
            "last_time": str(bars[-1].get("time", "")) if bars else "",
        }

    m1_count = int(timeframes.get("M1", {}).get("bars") or 0)
    if top_level_bars and m1_count and len(top_level_bars) < m1_count:
        warnings.append(
            f"top-level bars has {len(top_level_bars)} rows and is a compact preview; "
            "use timeframes.M1.bars for full history"
        )
    elif top_level_bars and not raw_timeframes:
        warnings.append("history has only top-level bars; full multi-timeframe data is missing")

    done = done_status(done_path) if done_path else None
    if done and done.get("exists"):
        done_bars = done.get("bars", {})
        if isinstance(done_bars, dict):
            for timeframe, status in timeframes.items():
                done_count = done_bars.get(timeframe)
                if done_count is not None and int(done_count) != int(status.get("bars") or 0):
                    warnings.append(
                        f"{timeframe} count differs from done file: history={status.get('bars')} done={done_count}"
                    )

    ok = all(bool(status["complete"]) for status in timeframes.values())
    return {
        "ok": ok,
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "path": str(history_path),
        "symbol": payload.get("symbol"),
        "server_time": payload.get("server_time"),
        "history_hours": hours,
        "top_level_bars": len(top_level_bars),
        "analysis_bar_source": "timeframes.M1.bars",
        "timeframes": timeframes,
        "done": done,
        "warnings": warnings,
    }


def done_status(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {"exists": False}
    done_path = Path(path)
    if not done_path.exists():
        return {"exists": False, "path": str(done_path)}
    payload = load_json(done_path)
    return {
        "exists": True,
        "path": str(done_path),
        "id": payload.get("id"),
        "hours": payload.get("hours"),
        "source_server_time": payload.get("source_server_time"),
        "bars": payload.get("bars") if isinstance(payload.get("bars"), dict) else {},
    }


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def format_history_status_markdown(status: dict[str, Any]) -> str:
    lines = [
        "# History Status",
        "",
        f"- OK: {status.get('ok')}",
        f"- Path: {status.get('path')}",
        f"- Symbol: {status.get('symbol')}",
        f"- Server time: {status.get('server_time')}",
        f"- History hours: {status.get('history_hours')}",
        f"- Top-level bars: {status.get('top_level_bars')} (compact preview)",
        f"- Analysis bar source: {status.get('analysis_bar_source')}",
        "",
        "## Timeframes",
        "",
        "| timeframe | bars | expected | coverage | complete | first | last |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    timeframes = status.get("timeframes", {})
    if isinstance(timeframes, dict):
        for timeframe in EXPECTED_BARS_PER_HOUR:
            row = timeframes.get(timeframe, {})
            if not isinstance(row, dict):
                continue
            lines.append(
                "| {timeframe} | {bars} | {expected_bars} | {coverage_ratio} | {complete} | {first_time} | {last_time} |".format(
                    timeframe=timeframe,
                    **row,
                )
            )
    done = status.get("done")
    if isinstance(done, dict) and done.get("exists"):
        lines.extend(
            [
                "",
                "## Done File",
                "",
                f"- Path: {done.get('path')}",
                f"- ID: {done.get('id')}",
                f"- Hours: {done.get('hours')}",
                f"- Source server time: {done.get('source_server_time')}",
                f"- Bars: {json.dumps(done.get('bars', {}), ensure_ascii=False)}",
            ]
        )
    lines.extend(["", "## Warnings", ""])
    warnings = status.get("warnings")
    if isinstance(warnings, list) and warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate MT5 history JSON counts and clarify compact vs full bars.")
    parser.add_argument("--history", default="runtime/latest_history_168h.json")
    parser.add_argument("--done", default="runtime/history_request.done.json")
    parser.add_argument("--min-coverage-ratio", type=float, default=0.98)
    parser.add_argument("--output-json", default="runtime/latest_history_status.json")
    parser.add_argument("--output-md", default="runtime/latest_history_status.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    status = history_status(
        args.history,
        done_path=args.done,
        min_coverage_ratio=args.min_coverage_ratio,
    )
    write_json(args.output_json, status)
    write_text(args.output_md, format_history_status_markdown(status))
    print(json.dumps(status, ensure_ascii=False, indent=2))
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_md}")
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
