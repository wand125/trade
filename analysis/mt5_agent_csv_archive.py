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
from analysis.mt5_agent_csv_utils import combined_source_time_coverage, summarize_csv_source_time
from analysis.mt5_compile_status import default_mt5_root
from analysis.mt5_tester_optimization_report import discover_tester_csvs
from analysis.mt5_tester_run import archive_existing_tester_csvs, archive_run_id_value


DEFAULT_OUTPUT_JSON = "runtime/latest_mt5_agent_csv_archive.json"
DEFAULT_OUTPUT_MD = "runtime/latest_mt5_agent_csv_archive.md"
DEFAULT_ARCHIVE_ROOT = "runtime/mt5_agent_csv_archive"
DEFAULT_FILENAME = "swing_evaluation_trades.csv"


def preview_agent_csv_archive(
    *,
    mt5_root: str | Path,
    archive_root: str | Path,
    filename: str = DEFAULT_FILENAME,
    run_id: str | None = None,
    include_source_time: bool = False,
) -> dict[str, Any]:
    mt5 = Path(mt5_root).expanduser()
    tester_root = mt5 / "Tester"
    archive_base = Path(archive_root).expanduser()
    archive_run_id = archive_run_id_value(run_id)
    archive_dir = archive_base / archive_run_id
    csvs = discover_tester_csvs([tester_root], filename=filename, since_minutes=0)
    files: list[dict[str, Any]] = []
    for source in csvs:
        stat = source.stat()
        try:
            relative = source.relative_to(tester_root)
        except ValueError:
            relative = Path(source.name)
        item = {
            "source": str(source),
            "planned_archive": str(archive_dir / relative),
            "agent": next((parent.name for parent in source.parents if parent.name.startswith("Agent-")), ""),
            "mtime": datetime.fromtimestamp(stat.st_mtime).strftime(TIME_FORMAT),
            "size": stat.st_size,
        }
        if include_source_time:
            item["source_time"] = summarize_csv_source_time(source)
        files.append(item)
    payload = {
        "ok": True,
        "execute": False,
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "mt5_root": str(mt5),
        "tester_root": str(tester_root),
        "archive_root": str(archive_base),
        "run_id": archive_run_id,
        "planned_archive_dir": str(archive_dir),
        "filename": filename,
        "count": len(files),
        "files": files,
    }
    if include_source_time:
        payload["include_source_time"] = True
        payload["source_time_coverage"] = combined_source_time_coverage(files)
    return payload


def archive_agent_csvs(
    *,
    mt5_root: str | Path,
    archive_root: str | Path,
    filename: str = DEFAULT_FILENAME,
    execute: bool = False,
    run_id: str | None = None,
    include_source_time: bool = False,
) -> dict[str, Any]:
    if not execute:
        return preview_agent_csv_archive(
            mt5_root=mt5_root,
            archive_root=archive_root,
            filename=filename,
            run_id=run_id,
            include_source_time=include_source_time,
        )
    payload = archive_existing_tester_csvs(
        mt5_root=mt5_root,
        archive_root=archive_root,
        filename=filename,
        run_id=run_id,
    )
    payload["execute"] = True
    payload["archive_root"] = str(Path(archive_root).expanduser())
    return payload


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# MT5 Agent CSV Archive",
        "",
        f"- Generated at: {payload.get('generated_at')}",
        f"- Execute: {payload.get('execute')}",
        f"- MT5 root: {payload.get('mt5_root', '')}",
        f"- Tester root: {payload.get('tester_root', '')}",
        f"- Archive root: {payload.get('archive_root', '')}",
        f"- Run ID: {payload.get('run_id', '')}",
        f"- Count: {payload.get('count')}",
    ]
    coverage = payload.get("source_time_coverage")
    if isinstance(coverage, dict):
        lines.extend(
            [
                "",
                "## Source Time Coverage",
                "",
                f"- Close rows: {coverage.get('close_rows')}",
                f"- With server_time: {coverage.get('close_rows_with_server_time')}",
                f"- Without server_time: {coverage.get('close_rows_without_server_time')}",
                f"- First/last server_time: {coverage.get('first_server_time', '')} / {coverage.get('last_server_time', '')}",
                f"- Span days: {coverage.get('span_days')}",
            ]
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            "| agent | size | mtime | source | archive |",
            "|---|---:|---|---|---|",
        ]
    )
    files = payload.get("files")
    if isinstance(files, list):
        for item in files:
            if not isinstance(item, dict):
                continue
            archive = item.get("archive", item.get("planned_archive", ""))
            source_time = item.get("source_time") if isinstance(item.get("source_time"), dict) else {}
            source_time_text = ""
            if source_time:
                source_time_text = (
                    f" close={source_time.get('close_rows')} "
                    f"{source_time.get('first_server_time', '')}/{source_time.get('last_server_time', '')}"
                )
            lines.append(
                f"| {item.get('agent', '')} | {item.get('size', '')} | {item.get('mtime', '')} | "
                f"{item.get('source', '')}{source_time_text} | {archive} |"
            )
    return "\n".join(lines) + "\n"


def write_outputs(json_path: str | Path, md_path: str | Path, payload: dict[str, Any]) -> None:
    output_json = Path(json_path)
    output_md = Path(md_path)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(format_markdown(payload), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview or archive MT5 Tester Agent CSV logs before a clean run.")
    parser.add_argument("--mt5-root", default=str(default_mt5_root()))
    parser.add_argument("--archive-root", default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--filename", default=DEFAULT_FILENAME)
    parser.add_argument("--run-id", default="", help="Archive subdirectory name. Defaults to current timestamp.")
    parser.add_argument("--execute", action="store_true", help="Move files. Without this flag, only preview targets.")
    parser.add_argument(
        "--include-source-time",
        action="store_true",
        help="Scan CSV contents and include close server_time coverage in dry-run preview output.",
    )
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = archive_agent_csvs(
            mt5_root=args.mt5_root,
            archive_root=args.archive_root,
            filename=args.filename,
            execute=args.execute,
            run_id=args.run_id or None,
            include_source_time=args.include_source_time,
        )
    except ValueError as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    write_outputs(args.output_json, args.output_md, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
