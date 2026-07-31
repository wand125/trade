from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.dry_run_command import load_optional_json
from analysis.forward_test import (
    append_record,
    evaluate_records,
    format_markdown,
    format_status_markdown,
    forward_status,
    read_records,
    record_from_signal,
    summarize_forward,
    summarize_record,
    write_records,
    write_summary,
)
from analysis.market_data import TIME_FORMAT, load_history


HEARTBEAT_IMPLEMENTATION_VERSION = 5
DEFAULT_PID_FILE = "runtime/forward_test_watch.pid"
DEFAULT_HEARTBEAT = "runtime/forward_test_watch_heartbeat.json"
HEARTBEAT_REQUIRED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "implementation_version",
    "snapshot_required_keys",
    "generated_at",
    "ok",
    "status",
    "returncode",
    "started_at",
    "finished_at",
    "started_epoch",
    "finished_epoch",
    "elapsed_seconds",
    "next_run_in_seconds",
    "watcher_pid",
    "pid_file",
    "pid_file_enabled",
    "pid_file_written",
    "heartbeat_enabled",
    "run_index",
    "max_runs",
    "continuous",
    "record_result",
    "evaluation_result",
    "paths",
    "counts",
    "signal",
    "summary",
)


def refresh_forward_test_watch(
    *,
    signal_path: str | Path = "runtime/latest_signal.json",
    ledger_path: str | Path = "runtime/forward_tests.jsonl",
    history_path: str | Path = "runtime/latest_history_168h.json",
    summary_json: str | Path = "runtime/latest_forward_test.json",
    summary_md: str | Path = "runtime/latest_forward_test.md",
    status_json: str | Path = "runtime/latest_forward_test_status.json",
    status_md: str | Path = "runtime/latest_forward_test_status.md",
    heartbeat_path: str | Path = "runtime/forward_test_watch_heartbeat.json",
    max_hold_minutes: int = 60,
    next_run_in_seconds: int = 60,
    watcher_pid: int | None = None,
    pid_file: str | Path | None = None,
    pid_file_enabled: bool = True,
    pid_file_written: bool = True,
    run_index: int = 1,
    max_runs: int = 1,
    continuous: bool = False,
) -> dict[str, Any]:
    started_epoch = time.time()
    started_at = datetime.now().strftime(TIME_FORMAT)
    signal = load_optional_json(signal_path)
    records_before = read_records(ledger_path)

    record_result = "missing_signal"
    preview: dict[str, Any] | None = None
    if isinstance(signal, dict):
        preview = record_from_signal(signal)
        record_result = append_record(ledger_path, preview)

    records_after_record = read_records(ledger_path)
    evaluation_result = "history_missing"
    evaluated_records: list[dict[str, Any]] = records_after_record
    history = Path(history_path)
    if history.exists():
        loaded = load_history(history)
        evaluated_records = evaluate_records(
            records_after_record,
            loaded.bars("M1"),
            max_hold_minutes=max_hold_minutes,
        )
        evaluation_result = "evaluated"
        if Path(ledger_path).exists() or evaluated_records:
            write_records(ledger_path, evaluated_records)

    summary = summarize_forward(evaluated_records)
    write_summary(summary_json, summary, evaluated_records)
    write_text(summary_md, format_markdown(summary))

    status = forward_status(signal=signal, records=evaluated_records, ledger_path=ledger_path)
    write_json(status_json, status)
    write_text(status_md, format_status_markdown(status))

    finished_epoch = time.time()
    finished_at = datetime.now().strftime(TIME_FORMAT)
    heartbeat = {
        "schema_version": 2,
        "implementation_version": HEARTBEAT_IMPLEMENTATION_VERSION,
        "snapshot_required_keys": list(HEARTBEAT_REQUIRED_FIELDS),
        "ok": True,
        "status": "ok",
        "returncode": 0,
        "generated_at": finished_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "started_epoch": round(started_epoch, 3),
        "finished_epoch": round(finished_epoch, 3),
        "elapsed_seconds": round(finished_epoch - started_epoch, 3),
        "record_result": record_result,
        "evaluation_result": evaluation_result,
        "next_run_in_seconds": next_run_in_seconds,
        "watcher_pid": watcher_pid if watcher_pid is not None else os.getpid(),
        "pid_file": str(pid_file) if pid_file is not None else "",
        "pid_file_enabled": pid_file_enabled,
        "pid_file_written": pid_file_written,
        "heartbeat": str(heartbeat_path) if heartbeat_path else "",
        "heartbeat_enabled": bool(heartbeat_path),
        "run_index": run_index,
        "max_runs": max_runs,
        "continuous": continuous,
        "paths": {
            "signal": str(signal_path),
            "ledger": str(ledger_path),
            "history": str(history_path),
            "summary_json": str(summary_json),
            "summary_md": str(summary_md),
            "status_json": str(status_json),
            "status_md": str(status_md),
        },
        "counts": {
            "records_before": len(records_before),
            "records_after_record": len(records_after_record),
            "records_after_evaluate": len(evaluated_records),
            "closed": summary.get("closed"),
            "open": summary.get("open"),
            "ignored": summary.get("ignored"),
        },
        "signal": {
            "present": isinstance(signal, dict),
            "preview": summarize_record(preview) if isinstance(preview, dict) else None,
            "action": signal.get("action") if isinstance(signal, dict) else None,
            "score": signal.get("score") if isinstance(signal, dict) else None,
            "reason": signal.get("reason") if isinstance(signal, dict) else None,
        },
        "summary": summary,
    }
    if heartbeat_path:
        write_json(heartbeat_path, heartbeat)
    return heartbeat


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def write_error_heartbeat(
    path: str | Path,
    *,
    started_at: str,
    started_epoch: float | None = None,
    error: BaseException,
    next_run_in_seconds: int,
    watcher_pid: int | None = None,
    pid_file: str | Path | None = None,
    pid_file_enabled: bool = True,
    pid_file_written: bool = True,
    run_index: int = 1,
    max_runs: int = 1,
    continuous: bool = False,
) -> None:
    if not str(path):
        return
    finished_epoch = time.time()
    started_epoch = finished_epoch if started_epoch is None else started_epoch
    finished_at = datetime.now().strftime(TIME_FORMAT)
    write_json(
        path,
        {
            "schema_version": 2,
            "implementation_version": HEARTBEAT_IMPLEMENTATION_VERSION,
            "snapshot_required_keys": list(HEARTBEAT_REQUIRED_FIELDS),
            "ok": False,
            "status": "error",
            "returncode": 1,
            "generated_at": finished_at,
            "started_at": started_at,
            "finished_at": finished_at,
            "started_epoch": round(started_epoch, 3),
            "finished_epoch": round(finished_epoch, 3),
            "elapsed_seconds": round(finished_epoch - started_epoch, 3),
            "error": str(error),
            "traceback_tail": traceback.format_exc()[-4000:],
            "next_run_in_seconds": next_run_in_seconds,
            "watcher_pid": watcher_pid if watcher_pid is not None else os.getpid(),
            "pid_file": str(pid_file) if pid_file is not None else "",
            "pid_file_enabled": pid_file_enabled,
            "pid_file_written": pid_file_written,
            "heartbeat": str(path) if path else "",
            "heartbeat_enabled": bool(path),
            "run_index": run_index,
            "max_runs": max_runs,
            "continuous": continuous,
        },
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Periodically record, evaluate, and summarize forward-test signals.")
    parser.add_argument("--signal", default="runtime/latest_signal.json")
    parser.add_argument("--ledger", default="runtime/forward_tests.jsonl")
    parser.add_argument("--history", default="runtime/latest_history_168h.json")
    parser.add_argument("--summary-json", default="runtime/latest_forward_test.json")
    parser.add_argument("--summary-md", default="runtime/latest_forward_test.md")
    parser.add_argument("--status-json", default="runtime/latest_forward_test_status.json")
    parser.add_argument("--status-md", default="runtime/latest_forward_test_status.md")
    parser.add_argument("--max-hold-minutes", type=int, default=60)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--max-runs", type=int, default=0, help="Stop after this many refreshes. 0 means run forever.")
    parser.add_argument(
        "--pid-file",
        default="",
        help=(
            "PID file path. Defaults to the shared daemon PID only for --max-runs 0; "
            "one-shot runs do not overwrite it unless this is explicit."
        ),
    )
    parser.add_argument(
        "--skip-pid-file-write",
        action="store_true",
        help="Do not overwrite the pid file. Useful for one-shot record/evaluate refreshes while a daemon watcher is running.",
    )
    parser.add_argument(
        "--heartbeat",
        default="",
        help=(
            "Heartbeat path. Defaults to the shared daemon heartbeat only for --max-runs 0; "
            "one-shot runs do not overwrite it unless this is explicit."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.interval_seconds < 5:
        raise SystemExit("--interval-seconds must be >= 5")
    if args.max_hold_minutes <= 0:
        raise SystemExit("--max-hold-minutes must be > 0")

    continuous = args.max_runs == 0
    heartbeat_path = args.heartbeat or (DEFAULT_HEARTBEAT if continuous else "")
    pid_file_path = args.pid_file or (DEFAULT_PID_FILE if continuous else "")
    pid_file_written = bool(pid_file_path) and not args.skip_pid_file_write

    if pid_file_written:
        Path(pid_file_path).parent.mkdir(parents=True, exist_ok=True)
        Path(pid_file_path).write_text(str(os.getpid()) + "\n", encoding="utf-8")

    runs = 0
    last_returncode = 0
    while True:
        started_epoch = time.time()
        started_at = datetime.now().strftime(TIME_FORMAT)
        try:
            heartbeat = refresh_forward_test_watch(
                signal_path=args.signal,
                ledger_path=args.ledger,
                history_path=args.history,
                summary_json=args.summary_json,
                summary_md=args.summary_md,
                status_json=args.status_json,
                status_md=args.status_md,
                heartbeat_path=heartbeat_path,
                max_hold_minutes=args.max_hold_minutes,
                next_run_in_seconds=args.interval_seconds,
                watcher_pid=os.getpid(),
                pid_file=pid_file_path,
                pid_file_enabled=bool(pid_file_path),
                pid_file_written=pid_file_written,
                run_index=runs + 1,
                max_runs=args.max_runs,
                continuous=continuous,
            )
            print(json.dumps(heartbeat, ensure_ascii=False, indent=2))
            last_returncode = 0
        except Exception as exc:  # pragma: no cover - exercised through operational heartbeat.
            write_error_heartbeat(
                heartbeat_path,
                started_at=started_at,
                started_epoch=started_epoch,
                error=exc,
                next_run_in_seconds=args.interval_seconds,
                watcher_pid=os.getpid(),
                pid_file=pid_file_path,
                pid_file_enabled=bool(pid_file_path),
                pid_file_written=pid_file_written,
                run_index=runs + 1,
                max_runs=args.max_runs,
                continuous=continuous,
            )
            print(f"forward_test_watch failed: {exc}", file=sys.stderr)
            last_returncode = 1

        runs += 1
        if args.max_runs > 0 and runs >= args.max_runs:
            return last_returncode
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
