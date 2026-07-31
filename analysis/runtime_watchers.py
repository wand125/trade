from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from analysis.bridge_status_watch import (
    HEARTBEAT_IMPLEMENTATION_VERSION as BRIDGE_STATUS_WATCH_HEARTBEAT_IMPLEMENTATION_VERSION,
    HEARTBEAT_REQUIRED_FIELDS as BRIDGE_STATUS_WATCH_HEARTBEAT_REQUIRED_FIELDS,
)
from analysis.forward_status_watch import (
    HEARTBEAT_IMPLEMENTATION_VERSION as FORWARD_STATUS_WATCH_HEARTBEAT_IMPLEMENTATION_VERSION,
    HEARTBEAT_REQUIRED_FIELDS as FORWARD_STATUS_WATCH_HEARTBEAT_REQUIRED_FIELDS,
)
from analysis.forward_test_watch import (
    HEARTBEAT_IMPLEMENTATION_VERSION as FORWARD_TEST_WATCH_HEARTBEAT_IMPLEMENTATION_VERSION,
    HEARTBEAT_REQUIRED_FIELDS as FORWARD_TEST_WATCH_HEARTBEAT_REQUIRED_FIELDS,
)
from analysis.mt5_tester_status import (
    STATUS_WATCH_HEARTBEAT_IMPLEMENTATION_VERSION,
    STATUS_WATCH_HEARTBEAT_REQUIRED_FIELDS,
)
from analysis.mt5_manual_auto_collect_watch import (
    IMPLEMENTATION_VERSION as MT5_MANUAL_AUTO_COLLECT_WATCH_IMPLEMENTATION_VERSION,
    HEARTBEAT_REQUIRED_FIELDS as MT5_MANUAL_AUTO_COLLECT_WATCH_REQUIRED_FIELDS,
)


DEFAULT_OUTPUT_JSON = "runtime/latest_runtime_watchers.json"
DEFAULT_OUTPUT_MD = "runtime/latest_runtime_watchers.md"
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"
SIGTERM = getattr(signal, "SIGTERM", 15)


@dataclass(frozen=True)
class WatcherSpec:
    name: str
    script: str
    heartbeat: str
    pid_file: str
    log_file: str
    extra_args: tuple[str, ...] = ()

    def command(self, *, interval_seconds: int, python_executable: str) -> list[str]:
        return [
            python_executable,
            self.script,
            "--interval-seconds",
            str(interval_seconds),
            "--heartbeat",
            self.heartbeat,
            "--pid-file",
            self.pid_file,
            *self.extra_args,
        ]


def default_watcher_specs(
    *, mt5_manual_auto_collect_execute_ready: bool = False
) -> tuple[WatcherSpec, ...]:
    mt5_manual_auto_collect_extra_args = (
        "--queue",
        "runtime/latest_mt5_manual_test_queue_with_optimization.json",
        "--collect-output-json",
        "runtime/latest_mt5_manual_collect_with_optimization.json",
        "--collect-output-md",
        "runtime/latest_mt5_manual_collect_with_optimization.md",
        "--queue-launch-json",
        "runtime/latest_mt5_manual_queue_launch_with_optimization.json",
        "--queue-launch-md",
        "runtime/latest_mt5_manual_queue_launch_with_optimization.md",
        "--operator-packet-json",
        "runtime/latest_mt5_manual_operator_packet_with_optimization.json",
        "--operator-packet-md",
        "runtime/latest_mt5_manual_operator_packet_with_optimization.md",
        "--bridge-recovery-plan-json",
        "runtime/latest_bridge_recovery_plan.json",
        "--strategy-analysis-json",
        "runtime/latest_mt5_strategy_tester_analysis.json",
        "--output-json",
        "runtime/latest_mt5_manual_auto_collect_watch.json",
        "--output-md",
        "runtime/latest_mt5_manual_auto_collect_watch.md",
        "--max-runs",
        "0",
    )
    if mt5_manual_auto_collect_execute_ready:
        mt5_manual_auto_collect_extra_args = (
            *mt5_manual_auto_collect_extra_args,
            "--execute-ready",
        )
    return (
        WatcherSpec(
            name="bridge_status",
            script="analysis/bridge_status_watch.py",
            heartbeat="runtime/bridge_status_watch_heartbeat.json",
            pid_file="runtime/bridge_status_watch.pid",
            log_file="runtime/bridge_status_watch.log",
            extra_args=(
                "--output-json",
                "runtime/latest_bridge_status.json",
                "--output-md",
                "runtime/latest_bridge_status.md",
                "--refresh-history-status",
                "--history-json",
                "runtime/latest_history_168h.json",
                "--history-done",
                "runtime/history_request.done.json",
                "--history-status",
                "runtime/latest_history_status.json",
                "--history-status-md",
                "runtime/latest_history_status.md",
                "--recovery-output-json",
                "runtime/latest_bridge_recovery_plan.json",
                "--recovery-output-md",
                "runtime/latest_bridge_recovery_plan.md",
            ),
        ),
        WatcherSpec(
            name="mt5_tester_status",
            script="analysis/mt5_tester_status_watch.py",
            heartbeat="runtime/mt5_tester_status_watch_heartbeat_current.json",
            pid_file="runtime/mt5_tester_status_watch_current.pid",
            log_file="runtime/mt5_tester_status_watch_current.log",
            extra_args=(
                "--back-forward-run",
                "runtime/latest_mt5_back_forward_run.json",
                "--manual-test-queue",
                "runtime/latest_mt5_manual_test_queue.json",
                "--manual-queue-launch",
                "runtime/latest_mt5_manual_queue_launch.json",
                "--manual-collect-run",
                "runtime/latest_mt5_manual_collect_run.json",
                "--manual-test-queue-with-optimization",
                "runtime/latest_mt5_manual_test_queue_with_optimization.json",
                "--manual-queue-launch-with-optimization",
                "runtime/latest_mt5_manual_queue_launch_with_optimization.json",
                "--manual-collect-with-optimization",
                "runtime/latest_mt5_manual_collect_with_optimization.json",
                "--manual-operator-packet-with-optimization",
                "runtime/latest_mt5_manual_operator_packet_with_optimization.json",
                "--bridge-recovery-plan",
                "runtime/latest_bridge_recovery_plan.json",
                "--output-json",
                "runtime/latest_mt5_tester_status.json",
                "--output-md",
                "runtime/latest_mt5_tester_status.md",
            ),
        ),
        WatcherSpec(
            name="mt5_manual_auto_collect",
            script="analysis/mt5_manual_auto_collect_watch.py",
            heartbeat="runtime/mt5_manual_auto_collect_watch_heartbeat.json",
            pid_file="runtime/mt5_manual_auto_collect_watch.pid",
            log_file="runtime/mt5_manual_auto_collect_watch.log",
            extra_args=mt5_manual_auto_collect_extra_args,
        ),
        WatcherSpec(
            name="forward_test",
            script="analysis/forward_test_watch.py",
            heartbeat="runtime/forward_test_watch_heartbeat.json",
            pid_file="runtime/forward_test_watch.pid",
            log_file="runtime/forward_test_watch.log",
            extra_args=(
                "--signal",
                "runtime/latest_signal.json",
                "--ledger",
                "runtime/forward_tests.jsonl",
                "--history",
                "runtime/latest_history_168h.json",
                "--summary-json",
                "runtime/latest_forward_test.json",
                "--summary-md",
                "runtime/latest_forward_test.md",
                "--status-json",
                "runtime/latest_forward_test_status.json",
                "--status-md",
                "runtime/latest_forward_test_status.md",
            ),
        ),
        WatcherSpec(
            name="forward_status",
            script="analysis/forward_status_watch.py",
            heartbeat="runtime/forward_status_watch_heartbeat.json",
            pid_file="runtime/forward_status_watch.pid",
            log_file="runtime/forward_status_watch.log",
            extra_args=(
                "--signal",
                "runtime/latest_signal.json",
                "--ledger",
                "runtime/forward_tests.jsonl",
                "--output-json",
                "runtime/latest_forward_test_status.json",
                "--output-md",
                "runtime/latest_forward_test_status.md",
            ),
        ),
    )


def read_pid(path: str | Path) -> int | None:
    source = Path(path)
    if not source.exists():
        return None
    try:
        text = source.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def process_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_time_value(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    for fmt in (TIME_FORMAT, "%Y.%m.%d %H:%M"):
        try:
            return datetime.strptime(text, fmt).timestamp()
        except ValueError:
            continue
    return None


def heartbeat_summary(path: str | Path, *, now_epoch: float, max_age_seconds: int) -> dict[str, Any]:
    payload = load_json(path)
    if not payload:
        return {
            "exists": False,
            "fresh": False,
            "age_seconds": None,
            "max_age_seconds": max_age_seconds,
        }
    finished_epoch = parse_time_value(payload.get("finished_epoch"))
    if finished_epoch is None:
        finished_epoch = parse_time_value(payload.get("finished_at"))
    age_seconds = round(max(0.0, now_epoch - finished_epoch), 1) if finished_epoch is not None else None
    fresh = bool(age_seconds is not None and age_seconds <= max_age_seconds)
    return {
        "exists": True,
        "fresh": fresh,
        "age_seconds": age_seconds,
        "max_age_seconds": max_age_seconds,
        "missing_required_fields": [],
        "expected_implementation_version": "",
        "implementation_version_mismatch": "",
        "watcher_pid": payload.get("watcher_pid", ""),
        "pid_file": payload.get("pid_file", ""),
        "pid_file_written": payload.get("pid_file_written", ""),
        "continuous": payload.get("continuous", ""),
        "run_index": payload.get("run_index", ""),
        "finished_at": payload.get("finished_at", ""),
        "finished_epoch": payload.get("finished_epoch", ""),
        "elapsed_seconds": payload.get("elapsed_seconds", ""),
        "returncode": payload.get("returncode", ""),
        "schema_version": payload.get("schema_version", ""),
        "implementation_version": payload.get("implementation_version", ""),
        "status_refresh_phase": payload.get("status_refresh_phase", ""),
        "operational_status": payload.get("operational_status", ""),
        "status": payload.get("status", ""),
        "execute_ready": payload.get("execute_ready", ""),
    }


def heartbeat_schema_expectation(spec: WatcherSpec) -> tuple[tuple[str, ...], int | str] | None:
    if spec.name == "mt5_tester_status":
        return (
            STATUS_WATCH_HEARTBEAT_REQUIRED_FIELDS,
            STATUS_WATCH_HEARTBEAT_IMPLEMENTATION_VERSION,
        )
    if spec.name == "bridge_status":
        return (
            BRIDGE_STATUS_WATCH_HEARTBEAT_REQUIRED_FIELDS,
            BRIDGE_STATUS_WATCH_HEARTBEAT_IMPLEMENTATION_VERSION,
        )
    if spec.name == "mt5_manual_auto_collect":
        return (
            MT5_MANUAL_AUTO_COLLECT_WATCH_REQUIRED_FIELDS,
            MT5_MANUAL_AUTO_COLLECT_WATCH_IMPLEMENTATION_VERSION,
        )
    if spec.name == "forward_test":
        return (
            FORWARD_TEST_WATCH_HEARTBEAT_REQUIRED_FIELDS,
            FORWARD_TEST_WATCH_HEARTBEAT_IMPLEMENTATION_VERSION,
        )
    if spec.name == "forward_status":
        return (
            FORWARD_STATUS_WATCH_HEARTBEAT_REQUIRED_FIELDS,
            FORWARD_STATUS_WATCH_HEARTBEAT_IMPLEMENTATION_VERSION,
        )
    return None


def heartbeat_schema_status(spec: WatcherSpec, heartbeat_path: str | Path) -> dict[str, Any]:
    expectation = heartbeat_schema_expectation(spec)
    if expectation is None:
        return {
            "checked": False,
            "ok": True,
            "missing_required_fields": [],
            "expected_implementation_version": "",
            "implementation_version_mismatch": False,
            "issues": [],
        }
    required_fields, expected_implementation_version = expectation
    payload = load_json(heartbeat_path)
    if not payload:
        return {
            "checked": True,
            "ok": False,
            "missing_required_fields": list(required_fields),
            "expected_implementation_version": expected_implementation_version,
            "implementation_version_mismatch": True,
            "issues": ["heartbeat_schema_missing"],
        }
    missing = [field for field in required_fields if field not in payload]
    implementation_version = payload.get("implementation_version", "")
    implementation_mismatch = implementation_version != expected_implementation_version
    issues: list[str] = []
    if implementation_mismatch:
        issues.append(
            "implementation_version_mismatch:"
            f"{implementation_version}->{expected_implementation_version}"
        )
    if missing:
        issues.append("missing_required_fields:" + ",".join(missing))
    return {
        "checked": True,
        "ok": not issues,
        "missing_required_fields": missing,
        "expected_implementation_version": expected_implementation_version,
        "implementation_version_mismatch": implementation_mismatch,
        "issues": issues,
    }


def optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def heartbeat_pid_matches(heartbeat: dict[str, Any], pid: int | None) -> bool | None:
    heartbeat_pid = optional_int(heartbeat.get("watcher_pid"))
    if heartbeat_pid is None or pid is None:
        return None
    return heartbeat_pid == pid


def heartbeat_daemon_status(heartbeat: dict[str, Any], pid: int | None) -> dict[str, Any]:
    pid_matches = heartbeat_pid_matches(heartbeat, pid)
    pid_file_written = heartbeat.get("pid_file_written")
    continuous = heartbeat.get("continuous")
    issues: list[str] = []
    if pid_matches is False:
        issues.append("heartbeat_pid_mismatch")
    if pid_file_written is False:
        issues.append("heartbeat_written_by_oneshot")
    if continuous is False:
        issues.append("heartbeat_not_continuous")
    return {
        "pid_matches": pid_matches,
        "pid_file_written": pid_file_written,
        "continuous": continuous,
        "issues": issues,
        "ok": not issues,
    }


def heartbeat_mode_status(
    spec: WatcherSpec,
    heartbeat: dict[str, Any],
    *,
    mt5_manual_auto_collect_execute_ready: bool,
) -> dict[str, Any]:
    if spec.name != "mt5_manual_auto_collect":
        return {"checked": False, "ok": True, "issues": []}
    actual = heartbeat.get("execute_ready")
    if actual not in (True, False):
        return {"checked": True, "ok": True, "issues": [], "actual_execute_ready": actual}
    expected = bool(mt5_manual_auto_collect_execute_ready)
    if bool(actual) == expected:
        return {
            "checked": True,
            "ok": True,
            "issues": [],
            "actual_execute_ready": bool(actual),
            "expected_execute_ready": expected,
        }
    return {
        "checked": True,
        "ok": False,
        "issues": [f"execute_ready_mode_mismatch:{bool(actual)}->{expected}"],
        "actual_execute_ready": bool(actual),
        "expected_execute_ready": expected,
    }


def runtime_watcher_manager_command(
    *,
    watcher_name: str,
    interval_seconds: int,
    python_executable: str,
    restart: bool = False,
    max_heartbeat_age_seconds: int | None = None,
    mt5_manual_auto_collect_execute_ready: bool = False,
) -> list[str]:
    command = [
        python_executable,
        "analysis/runtime_watchers.py",
        "--only",
        watcher_name,
        "--interval-seconds",
        str(interval_seconds),
    ]
    if restart:
        command.append("--restart")
    if max_heartbeat_age_seconds:
        command.extend(["--max-heartbeat-age-seconds", str(max_heartbeat_age_seconds)])
    if watcher_name == "mt5_manual_auto_collect" and mt5_manual_auto_collect_execute_ready:
        command.append("--mt5-manual-auto-collect-execute-ready")
    return command


def manage_watcher(
    spec: WatcherSpec,
    *,
    interval_seconds: int,
    python_executable: str,
    restart: bool = False,
    dry_run: bool = False,
    now_epoch: float | None = None,
    max_heartbeat_age_seconds: int | None = None,
    mt5_manual_auto_collect_execute_ready: bool = False,
) -> dict[str, Any]:
    effective_now = time.time() if now_epoch is None else now_epoch
    heartbeat_max_age = max_heartbeat_age_seconds or interval_seconds * 3
    command = spec.command(interval_seconds=interval_seconds, python_executable=python_executable)
    start_manager_command = runtime_watcher_manager_command(
        watcher_name=spec.name,
        interval_seconds=interval_seconds,
        python_executable=python_executable,
        restart=False,
        max_heartbeat_age_seconds=max_heartbeat_age_seconds,
        mt5_manual_auto_collect_execute_ready=mt5_manual_auto_collect_execute_ready,
    )
    restart_manager_command = runtime_watcher_manager_command(
        watcher_name=spec.name,
        interval_seconds=interval_seconds,
        python_executable=python_executable,
        restart=True,
        max_heartbeat_age_seconds=max_heartbeat_age_seconds,
        mt5_manual_auto_collect_execute_ready=mt5_manual_auto_collect_execute_ready,
    )
    pid = read_pid(spec.pid_file)
    alive = process_alive(pid)
    stale_pid_file = pid is not None and not alive
    heartbeat = heartbeat_summary(
        spec.heartbeat,
        now_epoch=effective_now,
        max_age_seconds=heartbeat_max_age,
    )
    schema_status = heartbeat_schema_status(spec, spec.heartbeat)
    heartbeat["missing_required_fields"] = schema_status["missing_required_fields"]
    heartbeat["expected_implementation_version"] = schema_status["expected_implementation_version"]
    heartbeat["implementation_version_mismatch"] = schema_status["implementation_version_mismatch"]
    daemon_status = heartbeat_daemon_status(heartbeat, pid)
    mode_status = heartbeat_mode_status(
        spec,
        heartbeat,
        mt5_manual_auto_collect_execute_ready=mt5_manual_auto_collect_execute_ready,
    )
    row: dict[str, Any] = {
        "name": spec.name,
        "script": spec.script,
        "pid_file": spec.pid_file,
        "pid": pid,
        "was_running": alive,
        "heartbeat": spec.heartbeat,
        "heartbeat_summary": heartbeat,
        "heartbeat_daemon": daemon_status,
        "heartbeat_mode": mode_status,
        "heartbeat_schema": schema_status,
        "heartbeat_status": heartbeat.get("status", ""),
        "heartbeat_fresh": heartbeat.get("fresh", False),
        "heartbeat_age_seconds": heartbeat.get("age_seconds"),
        "heartbeat_watcher_pid": heartbeat.get("watcher_pid", ""),
        "heartbeat_pid_matches": daemon_status.get("pid_matches"),
        "pid_file_written": daemon_status.get("pid_file_written", ""),
        "continuous": daemon_status.get("continuous", ""),
        "run_index": heartbeat.get("run_index", ""),
        "finished_at": heartbeat.get("finished_at", ""),
        "returncode": heartbeat.get("returncode", ""),
        "operational_status": heartbeat.get("operational_status", ""),
        "implementation_version": heartbeat.get("implementation_version", ""),
        "expected_implementation_version": schema_status.get(
            "expected_implementation_version", ""
        ),
        "schema_ok": schema_status.get("ok", False),
        "missing_required_fields": schema_status.get("missing_required_fields", []),
        "missing_required_field_count": len(
            schema_status.get("missing_required_fields", [])
        ),
        "status_refresh_phase": heartbeat.get("status_refresh_phase", ""),
        "execute_ready": heartbeat.get("execute_ready", ""),
        "log_file": spec.log_file,
        "command": command,
        "command_text": subprocess.list2cmdline(command),
        "start_command": start_manager_command,
        "start_command_text": subprocess.list2cmdline(start_manager_command),
        "restart_command": restart_manager_command,
        "restart_command_text": subprocess.list2cmdline(restart_manager_command),
        "tail_log_command_text": subprocess.list2cmdline(["tail", "-200", spec.log_file]),
        "dry_run": dry_run,
        "restart": restart,
        "stale_pid_file": stale_pid_file,
        "status": "",
        "started_pid": "",
        "stopped_pid": "",
        "error": "",
    }

    if alive and not restart:
        if heartbeat.get("fresh") is True:
            if not daemon_status["ok"]:
                row["status"] = "running_heartbeat_not_daemon"
                row["error"] = ", ".join(str(issue) for issue in daemon_status["issues"])
            elif not schema_status["ok"]:
                row["status"] = "running_heartbeat_incompatible"
                row["error"] = ", ".join(str(issue) for issue in schema_status["issues"])
            elif not mode_status["ok"]:
                row["status"] = "running_heartbeat_mode_mismatch"
                row["error"] = ", ".join(str(issue) for issue in mode_status["issues"])
            else:
                row["status"] = "already_running"
        elif heartbeat.get("exists") is True:
            row["status"] = "running_heartbeat_stale"
            row["error"] = (
                f"heartbeat stale: age_seconds={heartbeat.get('age_seconds')} "
                f"max_age_seconds={heartbeat.get('max_age_seconds')}"
            )
        else:
            row["status"] = "running_heartbeat_missing"
            row["error"] = "heartbeat missing while pid is running"
        return row

    if alive and restart:
        row["stopped_pid"] = pid
        if not dry_run:
            try:
                os.kill(pid, SIGTERM)
            except ProcessLookupError:
                pass
            except OSError as exc:
                row["status"] = "error"
                row["error"] = str(exc)
                return row

    if dry_run:
        if alive and restart:
            row["status"] = "would_restart"
        elif stale_pid_file:
            row["status"] = "stale_pid_would_start"
            row["error"] = f"pid file points to non-running process: {pid}"
        else:
            row["status"] = "would_start"
        return row

    try:
        Path(spec.log_file).parent.mkdir(parents=True, exist_ok=True)
        log_handle = Path(spec.log_file).open("ab")
        try:
            process = subprocess.Popen(
                command,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        finally:
            log_handle.close()
    except OSError as exc:
        row["status"] = "error"
        row["error"] = str(exc)
        return row

    row["started_pid"] = process.pid
    row["status"] = "restarted" if alive and restart else "started"
    return row


def selected_specs(names: str, specs: tuple[WatcherSpec, ...]) -> tuple[WatcherSpec, ...]:
    if not names:
        return specs
    wanted = {name.strip() for name in names.split(",") if name.strip()}
    known = {spec.name for spec in specs}
    unknown = sorted(wanted - known)
    if unknown:
        raise ValueError("unknown watcher name(s): " + ", ".join(unknown))
    return tuple(spec for spec in specs if spec.name in wanted)


def build_runtime_watchers_summary(
    *,
    specs: tuple[WatcherSpec, ...] | None = None,
    interval_seconds: int = 60,
    python_executable: str | None = None,
    restart: bool = False,
    dry_run: bool = False,
    now_epoch: float | None = None,
    max_heartbeat_age_seconds: int | None = None,
    mt5_manual_auto_collect_execute_ready: bool = False,
) -> dict[str, Any]:
    specs = (
        default_watcher_specs(
            mt5_manual_auto_collect_execute_ready=mt5_manual_auto_collect_execute_ready
        )
        if specs is None
        else specs
    )
    python_executable = python_executable or sys.executable
    effective_now = time.time() if now_epoch is None else now_epoch
    heartbeat_max_age = max_heartbeat_age_seconds or interval_seconds * 3
    generated_at = datetime.fromtimestamp(effective_now).strftime(TIME_FORMAT)
    rows = [
        manage_watcher(
            spec,
            interval_seconds=interval_seconds,
            python_executable=python_executable,
            restart=restart,
            dry_run=dry_run,
            now_epoch=effective_now,
            max_heartbeat_age_seconds=heartbeat_max_age,
            mt5_manual_auto_collect_execute_ready=mt5_manual_auto_collect_execute_ready,
        )
        for spec in specs
    ]
    errors = [row for row in rows if row.get("status") == "error"]
    action_required_watchers = [
        row
        for row in rows
        if row.get("status")
        in {
            "would_start",
            "would_restart",
            "stale_pid_would_start",
        }
    ]
    stale_watchers = [
        row
        for row in rows
        if row.get("status")
        in {
            "running_heartbeat_stale",
            "running_heartbeat_missing",
            "running_heartbeat_not_daemon",
            "running_heartbeat_incompatible",
            "running_heartbeat_mode_mismatch",
        }
    ]
    return {
        "ok": not errors and not stale_watchers and not action_required_watchers,
        "generated_at": generated_at,
        "interval_seconds": interval_seconds,
        "max_heartbeat_age_seconds": heartbeat_max_age,
        "restart": restart,
        "dry_run": dry_run,
        "mt5_manual_auto_collect_execute_ready": mt5_manual_auto_collect_execute_ready,
        "watcher_count": len(rows),
        "errors": errors,
        "action_required_watcher_count": len(action_required_watchers),
        "action_required_watchers": action_required_watchers,
        "stale_watcher_count": len(stale_watchers),
        "stale_watchers": stale_watchers,
        "watchers": rows,
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Runtime Watchers",
        "",
        f"- Generated at: {payload.get('generated_at', '')}",
        f"- OK: {payload.get('ok')}",
        f"- Interval seconds: {payload.get('interval_seconds', '')}",
        f"- Max heartbeat age seconds: {payload.get('max_heartbeat_age_seconds', '')}",
        f"- Action required watcher count: {payload.get('action_required_watcher_count', 0)}",
        f"- Stale watcher count: {payload.get('stale_watcher_count', 0)}",
        f"- Restart: {payload.get('restart')}",
        f"- Dry run: {payload.get('dry_run')}",
        f"- MT5 manual auto collect execute ready: {payload.get('mt5_manual_auto_collect_execute_ready')}",
        "",
        "| watcher | status | heartbeat status | pid | started | heartbeat | log | fresh | age sec | daemon pid | pid ok | continuous | pid file written | impl | expected impl | schema ok | missing keys | phase | run index | finished | restart |",
        "|---|---|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|",
    ]
    for row in payload.get("watchers", []):
        heartbeat = row.get("heartbeat_summary") if isinstance(row.get("heartbeat_summary"), dict) else {}
        daemon = row.get("heartbeat_daemon") if isinstance(row.get("heartbeat_daemon"), dict) else {}
        schema = row.get("heartbeat_schema") if isinstance(row.get("heartbeat_schema"), dict) else {}
        lines.append(
            "| {name} | {status} | {heartbeat_status} | {pid} | {started} | {heartbeat_path} | {log_file} | {fresh} | {age} | {heartbeat_pid} | {pid_ok} | {continuous} | {pid_file_written} | {implementation_version} | {expected_implementation_version} | {schema_ok} | {missing_key_count} | {phase} | {run_index} | {finished} | `{restart_command}` |".format(
                name=row.get("name", ""),
                status=row.get("status", ""),
                heartbeat_status=heartbeat.get("status", ""),
                pid=row.get("pid") or "",
                started=row.get("started_pid") or "",
                heartbeat_path=row.get("heartbeat", ""),
                log_file=row.get("log_file", ""),
                fresh=heartbeat.get("fresh", ""),
                age=heartbeat.get("age_seconds", ""),
                heartbeat_pid=heartbeat.get("watcher_pid", ""),
                pid_ok=daemon.get("pid_matches", ""),
                continuous=heartbeat.get("continuous", ""),
                pid_file_written=heartbeat.get("pid_file_written", ""),
                implementation_version=heartbeat.get("implementation_version", ""),
                expected_implementation_version=schema.get("expected_implementation_version", ""),
                schema_ok=schema.get("ok", ""),
                missing_key_count=len(schema.get("missing_required_fields", [])),
                phase=heartbeat.get("status_refresh_phase", ""),
                run_index=heartbeat.get("run_index", ""),
                finished=heartbeat.get("finished_at", ""),
                restart_command=row.get("restart_command_text", ""),
            )
        )
    lines.extend(["", "## Commands", ""])
    for row in payload.get("watchers", []):
        lines.append(
            f"- {row.get('name', '')}: start=`{row.get('start_command_text', '')}`; "
            f"restart=`{row.get('restart_command_text', '')}`; "
            f"log=`{row.get('tail_log_command_text', '')}`; "
            f"watcher=`{row.get('command_text', '')}`"
        )
    errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []
    if errors:
        lines.extend(["", "## Errors", ""])
        for row in errors:
            lines.append(f"- {row.get('name', '')}: {row.get('error', '')}")
    action_required_watchers = (
        payload.get("action_required_watchers")
        if isinstance(payload.get("action_required_watchers"), list)
        else []
    )
    if action_required_watchers:
        lines.extend(["", "## Action Required Watchers", ""])
        for row in action_required_watchers:
            detail = row.get("error") or row.get("command_text", "")
            lines.append(f"- {row.get('name', '')}: {row.get('status', '')}; {detail}")
    stale_watchers = payload.get("stale_watchers") if isinstance(payload.get("stale_watchers"), list) else []
    if stale_watchers:
        lines.extend(["", "## Stale Watchers", ""])
        for row in stale_watchers:
            lines.append(f"- {row.get('name', '')}: {row.get('error', '')}")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], *, output_json: str | Path, output_md: str | Path) -> None:
    json_path = Path(output_json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path = Path(output_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(format_markdown(payload), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start and summarize runtime watcher processes.")
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--only", default="", help="Comma-separated watcher names to manage.")
    parser.add_argument("--restart", action="store_true", help="Restart watchers that are already running.")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without starting or stopping processes.")
    parser.add_argument(
        "--max-heartbeat-age-seconds",
        type=int,
        default=0,
        help="Heartbeat freshness threshold. Defaults to interval*3.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used to start watchers.")
    parser.add_argument(
        "--mt5-manual-auto-collect-execute-ready",
        action="store_true",
        help=(
            "Start mt5_manual_auto_collect with --execute-ready so ready MT5 Strategy "
            "Tester reports are collected and post-collect analysis is refreshed."
        ),
    )
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.interval_seconds < 5:
        raise SystemExit("--interval-seconds must be >= 5")
    specs = selected_specs(
        args.only,
        default_watcher_specs(
            mt5_manual_auto_collect_execute_ready=args.mt5_manual_auto_collect_execute_ready
        ),
    )
    payload = build_runtime_watchers_summary(
        specs=specs,
        interval_seconds=args.interval_seconds,
        python_executable=args.python,
        restart=args.restart,
        dry_run=args.dry_run,
        max_heartbeat_age_seconds=args.max_heartbeat_age_seconds or None,
        mt5_manual_auto_collect_execute_ready=args.mt5_manual_auto_collect_execute_ready,
    )
    write_outputs(payload, output_json=args.output_json, output_md=args.output_md)
    print(
        json.dumps(
            {
                "ok": payload["ok"],
                "watcher_count": payload["watcher_count"],
                "output_json": str(args.output_json),
                "output_md": str(args.output_md),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
