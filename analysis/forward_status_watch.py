from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


HEARTBEAT_IMPLEMENTATION_VERSION = 3
DEFAULT_PID_FILE = "runtime/forward_status_watch.pid"
DEFAULT_HEARTBEAT = "runtime/forward_status_watch_heartbeat.json"
HEARTBEAT_REQUIRED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "implementation_version",
    "snapshot_required_keys",
    "generated_at",
    "ok",
    "status",
    "started_at",
    "finished_at",
    "started_epoch",
    "finished_epoch",
    "elapsed_seconds",
    "returncode",
    "next_run_in_seconds",
    "watcher_pid",
    "pid_file",
    "pid_file_enabled",
    "pid_file_written",
    "heartbeat_enabled",
    "run_index",
    "max_runs",
    "continuous",
    "status_ok",
    "operational_status",
    "ledger_exists",
    "ledger_records",
    "signal_present",
    "signal_recordability",
    "signal_action",
    "closed",
    "open",
    "ignored",
    "pf",
    "avg_r",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Periodically refresh forward-test status files.")
    parser.add_argument("--signal", default="runtime/latest_signal.json")
    parser.add_argument("--ledger", default="runtime/forward_tests.jsonl")
    parser.add_argument("--output-json", default="runtime/latest_forward_test_status.json")
    parser.add_argument("--output-md", default="runtime/latest_forward_test_status.md")
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
        help="Do not overwrite the pid file. Useful for one-shot status refreshes while a daemon watcher is running.",
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


def load_status_snapshot(path: str | Path) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "status_ok": "",
        "operational_status": "",
        "ledger_exists": "",
        "ledger_records": "",
        "signal_present": "",
        "signal_recordability": "",
        "signal_action": "",
        "closed": "",
        "open": "",
        "ignored": "",
        "pf": "",
        "avg_r": "",
    }
    source = Path(path)
    if not source.exists():
        return snapshot
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return snapshot
    if not isinstance(payload, dict):
        return snapshot
    ledger = payload.get("ledger") if isinstance(payload.get("ledger"), dict) else {}
    signal = payload.get("signal") if isinstance(payload.get("signal"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    snapshot.update(
        {
            "status_ok": payload.get("ok"),
            "operational_status": payload.get("operational_status", ""),
            "ledger_exists": ledger.get("exists"),
            "ledger_records": ledger.get("records"),
            "signal_present": signal.get("present"),
            "signal_recordability": signal.get("recordability", ""),
            "signal_action": signal.get("action", ""),
            "closed": summary.get("closed"),
            "open": summary.get("open"),
            "ignored": summary.get("ignored"),
            "pf": summary.get("pf"),
            "avg_r": summary.get("avg_r"),
        }
    )
    return snapshot


def heartbeat_runtime_status(returncode: int) -> str:
    return "ok" if returncode == 0 else "error"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.interval_seconds < 5:
        raise SystemExit("--interval-seconds must be >= 5")

    continuous = args.max_runs == 0
    heartbeat_path = args.heartbeat or (DEFAULT_HEARTBEAT if continuous else "")
    pid_file_path = args.pid_file or (DEFAULT_PID_FILE if continuous else "")
    pid_file_written = bool(pid_file_path) and not args.skip_pid_file_write

    if pid_file_written:
        Path(pid_file_path).parent.mkdir(parents=True, exist_ok=True)
        Path(pid_file_path).write_text(str(os.getpid()) + "\n", encoding="utf-8")

    runs = 0
    while True:
        started_epoch = time.time()
        started_at = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
        command = [
            sys.executable,
            "analysis/forward_test.py",
            "status",
            "--signal",
            args.signal,
            "--ledger",
            args.ledger,
            "--output-json",
            args.output_json,
            "--output-md",
            args.output_md,
        ]
        result = subprocess.run(command, text=True, capture_output=True)
        finished_epoch = time.time()
        finished_at = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
        status = heartbeat_runtime_status(result.returncode)
        heartbeat = {
            "schema_version": 2,
            "implementation_version": HEARTBEAT_IMPLEMENTATION_VERSION,
            "snapshot_required_keys": list(HEARTBEAT_REQUIRED_FIELDS),
            "generated_at": finished_at,
            "ok": status != "error",
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "started_epoch": round(started_epoch, 3),
            "finished_epoch": round(finished_epoch, 3),
            "elapsed_seconds": round(finished_epoch - started_epoch, 3),
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-2000:],
            "stderr_tail": result.stderr[-2000:],
            "next_run_in_seconds": args.interval_seconds,
            "watcher_pid": os.getpid(),
            "pid_file": pid_file_path,
            "pid_file_enabled": bool(pid_file_path),
            "pid_file_written": pid_file_written,
            "heartbeat": heartbeat_path,
            "heartbeat_enabled": bool(heartbeat_path),
            "run_index": runs + 1,
            "max_runs": args.max_runs,
            "continuous": continuous,
        }
        heartbeat.update(load_status_snapshot(args.output_json))
        if heartbeat_path:
            Path(heartbeat_path).parent.mkdir(parents=True, exist_ok=True)
            Path(heartbeat_path).write_text(
                json.dumps(heartbeat, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        runs += 1
        if args.max_runs > 0 and runs >= args.max_runs:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
