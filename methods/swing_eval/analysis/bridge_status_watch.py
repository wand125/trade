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


HEARTBEAT_IMPLEMENTATION_VERSION = 9
DEFAULT_PID_FILE = "runtime/bridge_status_watch.pid"
DEFAULT_HEARTBEAT = "runtime/bridge_status_watch_heartbeat.json"
HEARTBEAT_REQUIRED_FIELDS: tuple[str, ...] = (
    "generated_at",
    "ok",
    "status",
    "operational_status",
    "health_ok",
    "config_ok",
    "config_history_request_id",
    "bridge_process_running",
    "mt5_terminal_running",
    "ea_attention_required",
    "ea_attention_reason",
    "ea_liveness_signal",
    "config_get_recent_but_ea_post_stale",
    "snapshot_fresh",
    "history_request_stale_pending",
    "history_request_id",
    "history_done_id",
    "history_done_matches_request",
    "history_status_refresh_enabled",
    "history_status_refresh_status",
    "history_status_refresh_returncode",
    "history_status_ok",
    "history_status_generated_at",
    "history_status_server_time",
    "history_status_m1_bars",
    "history_status_m1_last_time",
    "history_status_done_id",
    "bridge_log_activity_status",
    "bridge_log_ea_liveness_signal",
    "bridge_log_config_get_recent",
    "bridge_log_ea_post_recent",
    "bridge_log_config_get_recent_but_ea_post_stale",
    "bridge_log_last_ea_post_at",
    "bridge_log_last_ea_post_age_seconds",
    "recovery_plan_status",
    "recovery_plan_ready_for_mt5_validation",
    "recovery_plan_bridge_required_for_standalone_tester",
    "recovery_plan_standalone_strategy_tester_allowed",
    "recovery_plan_standalone_strategy_tester_note",
    "recovery_plan_blocking_reasons",
    "recovery_plan_next_action",
    "recovery_plan_operation_cards",
    "recovery_plan_operation_card_count",
    "recovery_plan_next_operation_action",
    "recovery_plan_next_operation_area",
    "recovery_plan_next_operation_target",
    "recovery_plan_next_operation_verification",
    "recovery_plan_next_operation_verification_commands",
    "recovery_plan_next_operation_verification_command_count",
    "recovery_plan_next_operation_verification_command_labels",
    "recovery_plan_operator_summary",
    "recovery_plan_operator_summary_status",
    "recovery_plan_operator_summary_ready_for_mt5_validation",
    "recovery_plan_operator_summary_bridge_required_for_standalone_tester",
    "recovery_plan_operator_summary_standalone_strategy_tester_allowed",
    "recovery_plan_operator_summary_standalone_strategy_tester_note",
    "recovery_plan_operator_summary_blocking_reasons",
    "recovery_plan_operator_summary_next_action",
    "recovery_plan_operator_summary_next_operation_action",
    "recovery_plan_operator_summary_next_operation_area",
    "recovery_plan_operator_summary_next_operation_target",
    "recovery_plan_operator_summary_next_operation_operator_step",
    "recovery_plan_operator_summary_next_operation_verification",
    "recovery_plan_operator_summary_next_operation_verification_commands",
    "recovery_plan_operator_summary_next_operation_verification_command_count",
    "recovery_plan_operator_summary_next_operation_verification_command_labels",
    "recovery_plan_operator_summary_mt5_terminal_running",
    "recovery_plan_operator_summary_bridge_log_activity_status",
    "recovery_plan_operator_summary_ea_liveness_signal",
    "recovery_plan_operator_summary_config_get_recent_but_ea_post_stale",
    "recovery_plan_operator_summary_last_ea_post_age_seconds",
    "recovery_plan_operator_summary_snapshot_fresh",
    "recovery_plan_operator_summary_history_request_id",
    "recovery_plan_operator_summary_history_done_id",
    "recovery_plan_operator_summary_history_done_matches_request",
    "recovery_plan_operator_summary_history_data_fresh",
    "recovery_plan_operator_summary_history_data_stale",
    "recovery_plan_operator_summary_history_status_server_time",
    "recovery_plan_operator_summary_history_status_server_time_age_seconds",
    "recovery_plan_operator_summary_history_status_m1_last_time",
    "recovery_plan_operator_summary_history_status_m1_last_time_age_seconds",
    "pid_file_enabled",
    "heartbeat_enabled",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Periodically refresh MT5 AI Bridge status files.")
    parser.add_argument("--state-dir", default="runtime")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--http-timeout-seconds", type=float, default=3.0)
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    parser.add_argument("--max-history-request-pending-seconds", type=int, default=180)
    parser.add_argument("--output-json", default="runtime/latest_bridge_status.json")
    parser.add_argument("--output-md", default="runtime/latest_bridge_status.md")
    parser.add_argument("--history-json", default="runtime/latest_history_168h.json")
    parser.add_argument("--history-done", default="runtime/history_request.done.json")
    parser.add_argument("--history-status", default="runtime/latest_history_status.json")
    parser.add_argument("--history-status-md", default="runtime/latest_history_status.md")
    parser.add_argument(
        "--refresh-history-status",
        action="store_true",
        help="Refresh methods/swing_eval/analysis/history_status.py before bridge_recovery_plan.py reads latest_history_status.",
    )
    parser.add_argument("--recovery-output-json", default="runtime/latest_bridge_recovery_plan.json")
    parser.add_argument("--recovery-output-md", default="runtime/latest_bridge_recovery_plan.md")
    parser.add_argument(
        "--skip-recovery-plan",
        action="store_true",
        help="Do not refresh bridge_recovery_plan.py after bridge_status.py.",
    )
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
        help="Do not overwrite the pid file. Useful for one-shot heartbeat refreshes while a daemon watcher is running.",
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
    source = Path(path)
    if not source.exists():
        return {}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    health = payload.get("health") if isinstance(payload.get("health"), dict) else {}
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    config_payload = config.get("payload") if isinstance(config.get("payload"), dict) else {}
    process = payload.get("process") if isinstance(payload.get("process"), dict) else {}
    mt5_terminal = payload.get("mt5_terminal") if isinstance(payload.get("mt5_terminal"), dict) else {}
    ea_attention = payload.get("ea_attention") if isinstance(payload.get("ea_attention"), dict) else {}
    snapshot = payload.get("latest_snapshot") if isinstance(payload.get("latest_snapshot"), dict) else {}
    history = payload.get("history_request") if isinstance(payload.get("history_request"), dict) else {}
    request = history.get("request") if isinstance(history.get("request"), dict) else {}
    done = history.get("done") if isinstance(history.get("done"), dict) else {}
    bridge_log = payload.get("bridge_log") if isinstance(payload.get("bridge_log"), dict) else {}
    activity = bridge_log.get("activity") if isinstance(bridge_log.get("activity"), dict) else {}
    last_ea_post = activity.get("last_ea_post") if isinstance(activity.get("last_ea_post"), dict) else {}
    last_snapshot_post = (
        activity.get("last_snapshot_post") if isinstance(activity.get("last_snapshot_post"), dict) else {}
    )
    last_history_chunk_post = (
        activity.get("last_history_chunk_post")
        if isinstance(activity.get("last_history_chunk_post"), dict)
        else {}
    )
    last_config_get = activity.get("last_config_get") if isinstance(activity.get("last_config_get"), dict) else {}
    return {
        "status_ok": payload.get("ok"),
        "operational_status": payload.get("operational_status", ""),
        "next_action": payload.get("next_action", ""),
        "health_ok": health.get("ok"),
        "health_status": health.get("status"),
        "config_ok": config.get("ok"),
        "config_status": config.get("status"),
        "config_history_hours": config_payload.get("history_hours"),
        "config_history_request_id": config_payload.get("history_request_id", ""),
        "bridge_process_running": process.get("running"),
        "bridge_process_match_count": process.get("match_count"),
        "mt5_terminal_running": mt5_terminal.get("running"),
        "mt5_terminal_match_count": mt5_terminal.get("match_count"),
        "ea_attention_required": ea_attention.get("required"),
        "ea_attention_reason": ea_attention.get("reason", ""),
        "ea_liveness_signal": ea_attention.get("ea_liveness_signal", ""),
        "config_get_recent_but_ea_post_stale": ea_attention.get(
            "config_get_recent_but_ea_post_stale",
            "",
        ),
        "snapshot_fresh": snapshot.get("fresh"),
        "snapshot_age_seconds": snapshot.get("age_seconds"),
        "snapshot_server_time": snapshot.get("server_time", ""),
        "history_request_pending": history.get("pending"),
        "history_request_stale_pending": history.get("stale_pending"),
        "history_request_pending_age_seconds": history.get("pending_age_seconds"),
        "history_request_id": request.get("id", ""),
        "history_done_id": done.get("id", ""),
        "history_done_matches_request": history.get("done_matches_request"),
        "bridge_log_age_seconds": bridge_log.get("age_seconds"),
        "bridge_log_activity_status": activity.get("status", ""),
        "bridge_log_ea_liveness_signal": activity.get("ea_liveness_signal", ""),
        "bridge_log_config_get_recent": activity.get("config_get_recent", ""),
        "bridge_log_ea_post_recent": activity.get("ea_post_recent", ""),
        "bridge_log_config_get_recent_but_ea_post_stale": activity.get(
            "config_get_recent_but_ea_post_stale",
            "",
        ),
        "bridge_log_ea_post_count": activity.get("ea_post_count"),
        "bridge_log_last_ea_post_at": last_ea_post.get("timestamp", ""),
        "bridge_log_last_ea_post_age_seconds": last_ea_post.get("age_seconds"),
        "bridge_log_last_snapshot_post_at": last_snapshot_post.get("timestamp", ""),
        "bridge_log_last_snapshot_post_age_seconds": last_snapshot_post.get("age_seconds"),
        "bridge_log_last_history_chunk_post_at": last_history_chunk_post.get("timestamp", ""),
        "bridge_log_last_history_chunk_post_age_seconds": last_history_chunk_post.get("age_seconds"),
        "bridge_log_last_config_get_at": last_config_get.get("timestamp", ""),
        "bridge_log_last_config_get_age_seconds": last_config_get.get("age_seconds"),
    }


def load_recovery_plan_snapshot(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {"recovery_plan_exists": False}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"recovery_plan_exists": True, "recovery_plan_parse_error": True}
    if not isinstance(payload, dict):
        return {"recovery_plan_exists": True, "recovery_plan_parse_error": True}
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    operation_cards = payload.get("operation_cards") if isinstance(payload.get("operation_cards"), list) else []
    operation_card_dicts = [card for card in operation_cards if isinstance(card, dict)]
    next_card = next((card for card in operation_card_dicts if card.get("is_next") is True), {})
    operator_summary = (
        payload.get("operator_summary") if isinstance(payload.get("operator_summary"), dict) else {}
    )
    raw_verification_commands = (
        next_card.get("verification_commands") if isinstance(next_card.get("verification_commands"), list) else []
    )
    verification_commands = [command for command in raw_verification_commands if isinstance(command, dict)]
    verification_command_labels = [
        str(command.get("label", "")) for command in verification_commands if command.get("label")
    ]
    raw_operator_verification_commands = (
        operator_summary.get("next_operation_verification_commands")
        if isinstance(operator_summary.get("next_operation_verification_commands"), list)
        else []
    )
    operator_verification_commands = [
        command for command in raw_operator_verification_commands if isinstance(command, dict)
    ]
    operator_verification_command_labels = [
        str(command.get("label", "")) for command in operator_verification_commands if command.get("label")
    ]
    return {
        "recovery_plan_exists": True,
        "recovery_plan_ok": payload.get("ok"),
        "recovery_plan_status": payload.get("status", ""),
        "recovery_plan_ready_for_mt5_validation": payload.get("ready_for_mt5_validation"),
        "recovery_plan_bridge_required_for_standalone_tester": payload.get(
            "bridge_required_for_standalone_tester"
        ),
        "recovery_plan_standalone_strategy_tester_allowed": payload.get(
            "standalone_strategy_tester_allowed"
        ),
        "recovery_plan_standalone_strategy_tester_note": payload.get(
            "standalone_strategy_tester_note", ""
        ),
        "recovery_plan_blocking_reasons": (
            payload.get("blocking_reasons") if isinstance(payload.get("blocking_reasons"), list) else []
        ),
        "recovery_plan_next_action": payload.get("next_action", ""),
        "recovery_plan_operation_cards": operation_card_dicts,
        "recovery_plan_operation_card_count": len(operation_card_dicts),
        "recovery_plan_next_operation_card": next_card,
        "recovery_plan_next_operation_action": next_card.get("action", ""),
        "recovery_plan_next_operation_area": next_card.get("area", ""),
        "recovery_plan_next_operation_purpose": next_card.get("purpose", ""),
        "recovery_plan_next_operation_target": next_card.get("target", ""),
        "recovery_plan_next_operation_verification": next_card.get("verification", ""),
        "recovery_plan_next_operation_verification_commands": verification_commands,
        "recovery_plan_next_operation_verification_command_count": len(verification_commands),
        "recovery_plan_next_operation_verification_command_labels": verification_command_labels,
        "recovery_plan_operator_summary": operator_summary,
        "recovery_plan_operator_summary_status": operator_summary.get("status", ""),
        "recovery_plan_operator_summary_ready_for_mt5_validation": operator_summary.get(
            "ready_for_mt5_validation"
        ),
        "recovery_plan_operator_summary_bridge_required_for_standalone_tester": (
            operator_summary.get("bridge_required_for_standalone_tester")
        ),
        "recovery_plan_operator_summary_standalone_strategy_tester_allowed": (
            operator_summary.get("standalone_strategy_tester_allowed")
        ),
        "recovery_plan_operator_summary_standalone_strategy_tester_note": operator_summary.get(
            "standalone_strategy_tester_note", ""
        ),
        "recovery_plan_operator_summary_blocking_reasons": (
            operator_summary.get("blocking_reasons")
            if isinstance(operator_summary.get("blocking_reasons"), list)
            else []
        ),
        "recovery_plan_operator_summary_next_action": operator_summary.get("next_action", ""),
        "recovery_plan_operator_summary_next_operation_action": operator_summary.get(
            "next_operation_action", ""
        ),
        "recovery_plan_operator_summary_next_operation_area": operator_summary.get(
            "next_operation_area", ""
        ),
        "recovery_plan_operator_summary_next_operation_target": operator_summary.get(
            "next_operation_target", ""
        ),
        "recovery_plan_operator_summary_next_operation_operator_step": operator_summary.get(
            "next_operation_operator_step", ""
        ),
        "recovery_plan_operator_summary_next_operation_verification": operator_summary.get(
            "next_operation_verification", ""
        ),
        "recovery_plan_operator_summary_next_operation_verification_commands": operator_verification_commands,
        "recovery_plan_operator_summary_next_operation_verification_command_count": len(
            operator_verification_commands
        ),
        "recovery_plan_operator_summary_next_operation_verification_command_labels": (
            operator_verification_command_labels
        ),
        "recovery_plan_operator_summary_mt5_terminal_running": operator_summary.get(
            "mt5_terminal_running"
        ),
        "recovery_plan_operator_summary_bridge_log_activity_status": operator_summary.get(
            "bridge_log_activity_status", ""
        ),
        "recovery_plan_operator_summary_ea_liveness_signal": operator_summary.get(
            "ea_liveness_signal", ""
        ),
        "recovery_plan_operator_summary_config_get_recent_but_ea_post_stale": (
            operator_summary.get("config_get_recent_but_ea_post_stale", "")
        ),
        "recovery_plan_operator_summary_last_ea_post_age_seconds": operator_summary.get(
            "last_ea_post_age_seconds"
        ),
        "recovery_plan_operator_summary_snapshot_fresh": operator_summary.get("snapshot_fresh"),
        "recovery_plan_operator_summary_history_request_id": operator_summary.get(
            "history_request_id", ""
        ),
        "recovery_plan_operator_summary_history_done_id": operator_summary.get("history_done_id", ""),
        "recovery_plan_operator_summary_history_done_matches_request": operator_summary.get(
            "history_done_matches_request"
        ),
        "recovery_plan_operator_summary_history_data_fresh": operator_summary.get(
            "history_data_fresh"
        ),
        "recovery_plan_operator_summary_history_data_stale": operator_summary.get(
            "history_data_stale"
        ),
        "recovery_plan_operator_summary_history_status_server_time": operator_summary.get(
            "history_status_server_time", ""
        ),
        "recovery_plan_operator_summary_history_status_server_time_age_seconds": operator_summary.get(
            "history_status_server_time_age_seconds", ""
        ),
        "recovery_plan_operator_summary_history_status_m1_last_time": operator_summary.get(
            "history_status_m1_last_time", ""
        ),
        "recovery_plan_operator_summary_history_status_m1_last_time_age_seconds": operator_summary.get(
            "history_status_m1_last_time_age_seconds", ""
        ),
        "recovery_plan_bridge_status_loaded": checks.get("bridge_status_loaded"),
        "recovery_plan_bridge_process_running": checks.get("bridge_process_running"),
        "recovery_plan_mt5_terminal_running": checks.get("mt5_terminal_running"),
        "recovery_plan_snapshot_fresh": checks.get("snapshot_fresh"),
        "recovery_plan_history_request_stale_pending": checks.get("history_request_stale_pending"),
        "recovery_plan_history_done_matches_request": checks.get("history_done_matches_request"),
        "recovery_plan_ea_liveness_signal": checks.get("ea_liveness_signal", ""),
        "recovery_plan_config_get_recent_but_ea_post_stale": checks.get(
            "config_get_recent_but_ea_post_stale",
            "",
        ),
        "recovery_plan_history_data_fresh": checks.get("history_data_fresh"),
        "recovery_plan_history_data_stale": checks.get("history_data_stale"),
        "recovery_plan_history_status_server_time": checks.get("history_status_server_time", ""),
        "recovery_plan_history_status_server_time_age_seconds": checks.get(
            "history_status_server_time_age_seconds", ""
        ),
        "recovery_plan_history_status_m1_last_time": checks.get("history_status_m1_last_time", ""),
        "recovery_plan_history_status_m1_last_time_age_seconds": checks.get(
            "history_status_m1_last_time_age_seconds", ""
        ),
        "recovery_plan_last_ea_post_age_seconds": (
            checks.get("last_ea_post", {}).get("age_seconds")
            if isinstance(checks.get("last_ea_post"), dict)
            else None
        ),
    }


def load_history_status_snapshot(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {"history_status_exists": False}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"history_status_exists": True, "history_status_parse_error": True}
    if not isinstance(payload, dict):
        return {"history_status_exists": True, "history_status_parse_error": True}
    timeframes = payload.get("timeframes") if isinstance(payload.get("timeframes"), dict) else {}
    m1 = timeframes.get("M1") if isinstance(timeframes.get("M1"), dict) else {}
    done = payload.get("done") if isinstance(payload.get("done"), dict) else {}
    return {
        "history_status_exists": True,
        "history_status_ok": payload.get("ok"),
        "history_status_generated_at": payload.get("generated_at", ""),
        "history_status_path": payload.get("path", ""),
        "history_status_symbol": payload.get("symbol", ""),
        "history_status_server_time": payload.get("server_time", ""),
        "history_status_history_hours": payload.get("history_hours"),
        "history_status_m1_bars": m1.get("bars"),
        "history_status_m1_expected_bars": m1.get("expected_bars"),
        "history_status_m1_complete": m1.get("complete"),
        "history_status_m1_last_time": m1.get("last_time", ""),
        "history_status_done_exists": done.get("exists"),
        "history_status_done_id": done.get("id", ""),
        "history_status_done_source_server_time": done.get("source_server_time", ""),
    }


def write_heartbeat(path: str | Path, payload: dict[str, Any]) -> None:
    if not str(path):
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def heartbeat_runtime_status(
    bridge_returncode: int,
    history_returncode: int | None,
    recovery_returncode: int | None,
    *,
    history_enabled: bool,
    recovery_enabled: bool,
) -> str:
    accepted_bridge_returncodes = {0, 2}
    accepted_history_returncodes = {0, 1, None}
    accepted_recovery_returncodes = {0, 2, None}
    if bridge_returncode not in accepted_bridge_returncodes:
        return "error"
    if history_enabled and history_returncode not in accepted_history_returncodes:
        return "error"
    if recovery_enabled and recovery_returncode not in accepted_recovery_returncodes:
        return "error"
    return "ok"


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
            "methods/swing_eval/analysis/bridge_status.py",
            "--state-dir",
            args.state_dir,
            "--base-url",
            args.base_url,
            "--http-timeout-seconds",
            str(args.http_timeout_seconds),
            "--max-snapshot-age-seconds",
            str(args.max_snapshot_age_seconds),
            "--max-history-request-pending-seconds",
            str(args.max_history_request_pending_seconds),
            "--output-json",
            args.output_json,
            "--output-md",
            args.output_md,
        ]
        result = subprocess.run(command, text=True, capture_output=True)
        status_finished_epoch = time.time()
        history_result: subprocess.CompletedProcess[str] | None = None
        history_command: list[str] = []
        history_finished_epoch = status_finished_epoch
        if args.refresh_history_status:
            history_command = [
                sys.executable,
                "methods/swing_eval/analysis/history_status.py",
                "--history",
                args.history_json,
                "--done",
                args.history_done,
                "--output-json",
                args.history_status,
                "--output-md",
                args.history_status_md,
            ]
            history_result = subprocess.run(history_command, text=True, capture_output=True)
            history_finished_epoch = time.time()
        recovery_result: subprocess.CompletedProcess[str] | None = None
        recovery_command: list[str] = []
        if not args.skip_recovery_plan:
            recovery_command = [
                sys.executable,
                "methods/swing_eval/analysis/bridge_recovery_plan.py",
                "--bridge-status",
                args.output_json,
                "--history-status",
                args.history_status,
                "--output-json",
                args.recovery_output_json,
                "--output-md",
                args.recovery_output_md,
            ]
            recovery_result = subprocess.run(recovery_command, text=True, capture_output=True)
        finished_epoch = time.time()
        finished_at = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
        status = heartbeat_runtime_status(
            result.returncode,
            history_result.returncode if history_result is not None else None,
            recovery_result.returncode if recovery_result is not None else None,
            history_enabled=args.refresh_history_status,
            recovery_enabled=not args.skip_recovery_plan,
        )
        heartbeat = {
            "schema_version": 1,
            "implementation_version": HEARTBEAT_IMPLEMENTATION_VERSION,
            "snapshot_required_keys": list(HEARTBEAT_REQUIRED_FIELDS),
            "ok": status != "error",
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "generated_at": finished_at,
            "started_epoch": round(started_epoch, 3),
            "finished_epoch": round(finished_epoch, 3),
            "elapsed_seconds": round(finished_epoch - started_epoch, 3),
            "bridge_status_elapsed_seconds": round(status_finished_epoch - started_epoch, 3),
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-2000:],
            "stderr_tail": result.stderr[-2000:],
            "history_status_refresh_enabled": args.refresh_history_status,
            "history_status_refresh_status": "refreshed" if history_result is not None else "not_requested",
            "history_status_refresh_returncode": history_result.returncode if history_result is not None else None,
            "history_status_refresh_elapsed_seconds": (
                round(history_finished_epoch - status_finished_epoch, 3) if history_result is not None else None
            ),
            "history_status_refresh_stdout_tail": (
                history_result.stdout[-2000:] if history_result is not None else ""
            ),
            "history_status_refresh_stderr_tail": (
                history_result.stderr[-2000:] if history_result is not None else ""
            ),
            "recovery_plan_enabled": not args.skip_recovery_plan,
            "recovery_plan_returncode": recovery_result.returncode if recovery_result is not None else None,
            "recovery_plan_stdout_tail": recovery_result.stdout[-2000:] if recovery_result is not None else "",
            "recovery_plan_stderr_tail": recovery_result.stderr[-2000:] if recovery_result is not None else "",
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
            "output_json": args.output_json,
            "output_md": args.output_md,
            "history_status": args.history_status,
            "history_json": args.history_json,
            "history_done": args.history_done,
            "history_status_md": args.history_status_md,
            "recovery_output_json": args.recovery_output_json,
            "recovery_output_md": args.recovery_output_md,
            "command": command,
            "history_status_refresh_command": history_command,
            "recovery_plan_command": recovery_command,
        }
        heartbeat.update(load_status_snapshot(args.output_json))
        heartbeat.update(load_history_status_snapshot(args.history_status))
        if not args.skip_recovery_plan:
            heartbeat.update(load_recovery_plan_snapshot(args.recovery_output_json))
        write_heartbeat(heartbeat_path, heartbeat)
        runs += 1
        if args.max_runs > 0 and runs >= args.max_runs:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
