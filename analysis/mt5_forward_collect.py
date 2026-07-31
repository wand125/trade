from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT
from analysis.mt5_forward_report import load_mt5_csv, summarize_mt5_forward, write_json, write_markdown


DEFAULT_FILENAME = "swing_evaluation_trades.csv"


def default_source_roots() -> list[Path]:
    mt5_base = (
        Path.home()
        / "Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5"
    )
    return [
        mt5_base / "MQL5/Files",
        mt5_base / "Tester",
    ]


def discover_csvs(source_roots: list[str | Path], *, filename: str = DEFAULT_FILENAME) -> list[Path]:
    candidates: list[Path] = []
    for raw_root in source_roots:
        root = Path(raw_root).expanduser()
        if not root.exists():
            continue
        if root.is_file():
            if root.name == filename:
                candidates.append(root)
            continue
        candidates.extend(path for path in root.rglob(filename) if path.is_file())
    return sorted(set(candidates), key=lambda path: path.stat().st_mtime, reverse=True)


def collect_latest_mt5_forward(
    *,
    source_roots: list[str | Path] | None = None,
    filename: str = DEFAULT_FILENAME,
    destination: str | Path = "runtime/mt5_forward/swing_evaluation_trades.csv",
    output_json: str | Path = "runtime/latest_mt5_forward_report.json",
    output_md: str | Path = "runtime/latest_mt5_forward_report.md",
    collect_status_json: str | Path = "runtime/latest_mt5_forward_collect.json",
    min_closed: int = 30,
    min_pf: float = 1.2,
    max_losing_streak: int = 20,
) -> dict[str, Any]:
    roots = [Path(root).expanduser() for root in (source_roots or default_source_roots())]
    candidates = discover_csvs(roots, filename=filename)
    if not candidates:
        status = {
            "ok": False,
            "generated_at": datetime.now().strftime(TIME_FORMAT),
            "reason": f"no {filename} found",
            "searched_roots": [str(root) for root in roots],
            "candidates": [],
        }
        write_collect_status(collect_status_json, status)
        return status

    selected = candidates[0]
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if selected.resolve() != destination_path.resolve():
        shutil.copy2(selected, destination_path)

    rows = load_mt5_csv(destination_path)
    summary = summarize_mt5_forward(
        rows,
        min_closed=min_closed,
        min_pf=min_pf,
        max_losing_streak_limit=max_losing_streak,
    )
    write_json(output_json, summary, rows)
    write_markdown(output_md, summary)

    status = {
        "ok": True,
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "selected": str(selected),
        "destination": str(destination_path),
        "output_json": str(output_json),
        "output_md": str(output_md),
        "source_mtime": datetime.fromtimestamp(selected.stat().st_mtime).strftime(TIME_FORMAT),
        "candidates": [candidate_info(path) for path in candidates[:10]],
        "summary": {
            "closed": summary["overall"]["closed"],
            "pf": summary["overall"]["pf"],
            "max_losing_streak": summary["overall"]["max_losing_streak"],
            "ready_for_demo_review": summary["ready_for_demo_review"],
        },
    }
    write_collect_status(collect_status_json, status)
    return status


def candidate_info(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path),
        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime(TIME_FORMAT),
        "size": stat.st_size,
    }


def write_collect_status(path: str | Path, status: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect the latest MT5 Strategy Tester forward CSV and summarize it.")
    parser.add_argument("--source-root", action="append", default=None, help="MT5 Files or Tester root. Can be repeated.")
    parser.add_argument("--filename", default=DEFAULT_FILENAME)
    parser.add_argument("--destination", default="runtime/mt5_forward/swing_evaluation_trades.csv")
    parser.add_argument("--output-json", default="runtime/latest_mt5_forward_report.json")
    parser.add_argument("--output-md", default="runtime/latest_mt5_forward_report.md")
    parser.add_argument("--collect-status-json", default="runtime/latest_mt5_forward_collect.json")
    parser.add_argument("--min-closed", type=int, default=30)
    parser.add_argument("--min-pf", type=float, default=1.2)
    parser.add_argument("--max-losing-streak", type=int, default=20)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    status = collect_latest_mt5_forward(
        source_roots=args.source_root,
        filename=args.filename,
        destination=args.destination,
        output_json=args.output_json,
        output_md=args.output_md,
        collect_status_json=args.collect_status_json,
        min_closed=args.min_closed,
        min_pf=args.min_pf,
        max_losing_streak=args.max_losing_streak,
    )
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
