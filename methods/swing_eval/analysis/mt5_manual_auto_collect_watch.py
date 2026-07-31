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

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT
from analysis.mt5_manual_test_queue import DEFAULT_OUTPUT_JSON_WITH_OPTIMIZATION
from analysis.mt5_manual_test_queue import DEFAULT_COLLECT_OUTPUT_JSON_WITH_OPTIMIZATION
from analysis.mt5_manual_test_queue import DEFAULT_COLLECT_OUTPUT_MD_WITH_OPTIMIZATION
from analysis.mt5_manual_operator_packet import (
    DEFAULT_BRIDGE_RECOVERY_PLAN_JSON,
    DEFAULT_OUTPUT_JSON as DEFAULT_OPERATOR_PACKET_JSON,
    DEFAULT_OUTPUT_MD as DEFAULT_OPERATOR_PACKET_MD,
    DEFAULT_STRATEGY_ANALYSIS_JSON,
    build_packet as build_operator_packet,
    format_markdown as format_operator_packet_markdown,
    read_json as read_operator_queue,
    summarize_next_operator_action,
)


SCHEMA_VERSION = 1
IMPLEMENTATION_VERSION = 19
DEFAULT_OUTPUT_JSON = "runtime/latest_mt5_manual_auto_collect_watch.json"
DEFAULT_OUTPUT_MD = "runtime/latest_mt5_manual_auto_collect_watch.md"
DEFAULT_HEARTBEAT = "runtime/mt5_manual_auto_collect_watch_heartbeat.json"
DEFAULT_PID_FILE = "runtime/mt5_manual_auto_collect_watch.pid"
DEFAULT_QUEUE_LAUNCH_JSON_WITH_OPTIMIZATION = (
    "runtime/latest_mt5_manual_queue_launch_with_optimization.json"
)
DEFAULT_QUEUE_LAUNCH_MD_WITH_OPTIMIZATION = (
    "runtime/latest_mt5_manual_queue_launch_with_optimization.md"
)
HEARTBEAT_REQUIRED_FIELDS = (
    "schema_version",
    "implementation_version",
    "generated_at",
    "started_epoch",
    "finished_epoch",
    "elapsed_seconds",
    "watcher_pid",
    "pid_file",
    "pid_file_enabled",
    "pid_file_written",
    "heartbeat_enabled",
    "run_index",
    "max_runs",
    "continuous",
    "ok",
    "status",
    "next_action",
    "queue",
    "collect_output_json",
    "collect_dry_run_command_text",
    "collect_execute_command_text",
    "execute_ready",
    "ready_to_execute",
    "ready_for_collect_execute",
    "selected_count",
    "ready_entry_count",
    "waiting_count",
    "invalid_count",
    "queue_launch_json",
    "queue_launch_md",
    "queue_launch_refresh",
    "queue_launch_refresh_detached",
    "bridge_recovery_plan_json",
    "strategy_analysis_json",
    "operator_packet_json",
    "operator_packet_md",
    "operator_packet_refresh",
    "operator_packet_manual_run_start_mark_command_text",
    "operator_packet_manual_run_start_mark_command_available",
    "operator_packet_auto_launch_command_text",
    "operator_packet_auto_launch_command_available",
    "operator_packet_auto_launch_blocked",
    "operator_packet_auto_launch_blocked_reasons",
    "operator_packet_auto_launch_note",
    "operator_packet_strategy_source_time_refresh_status",
    "operator_packet_strategy_source_time_issue_labels",
    "operator_packet_strategy_source_time_candidate_issue_labels",
    "operator_packet_strategy_source_time_refresh_analysis_command_text",
    "operator_packet_strategy_source_time_refresh_analysis_command_available",
    "operator_packet_strategy_buy_candidate_gap_status",
    "operator_packet_strategy_buy_candidate_gap_reason",
    "operator_packet_strategy_buy_candidate_gap_diagnostic_labels",
    "operator_packet_strategy_buy_candidate_gap_collect_refresh_command_text",
    "operator_packet_strategy_buy_candidate_gap_collect_refresh_command_available",
    "operator_packet_strategy_back_forward_decision_status",
    "operator_packet_strategy_back_forward_decision_next_action",
    "operator_packet_strategy_back_forward_decision_collect_command_text",
    "operator_packet_strategy_back_forward_decision_sample_shortage_recovery_command_text",
    "operator_packet_strategy_back_forward_decision_sample_shortage_recovery_range_strategy",
    "operator_packet_strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date",
    "operator_packet_strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date",
    "operator_packet_strategy_operator_decision_status",
    "operator_packet_strategy_operator_decision_verdict",
    "operator_packet_strategy_operator_decision_adoptable",
    "operator_packet_strategy_operator_decision_primary_blocker",
    "operator_packet_strategy_operator_decision_primary_reason",
    "operator_packet_strategy_operator_decision_next_action",
    "operator_packet_strategy_operator_decision_summary",
    "operator_packet_strategy_operator_decision_command_text",
    "operator_packet_strategy_operator_decision_follow_up_command_text",
    "operator_packet_bridge_verification_commands",
    "operator_packet_bridge_verification_command_count",
    "operator_packet_bridge_verification_command_labels",
    "dry_run",
    "execution",
)


def parse_json_stdout(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return payload if isinstance(payload, dict) else {}


def tail_text(value: str, *, limit: int = 2000) -> str:
    return value[-limit:] if len(value) > limit else value


def write_json_file(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text_file(path: str | Path, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def collect_command(
    *,
    queue: str,
    collect_output_json: str,
    collect_output_md: str,
    execute: bool,
    refresh_post_collect_analysis: bool,
) -> list[str]:
    command = [
        sys.executable,
        "methods/swing_eval/analysis/mt5_manual_collect.py",
        "--queue",
        queue,
        "--output-json",
        collect_output_json,
        "--output-md",
        collect_output_md,
    ]
    if execute:
        command.append("--execute")
        if refresh_post_collect_analysis:
            command.append("--refresh-post-collect-analysis")
    return command


def command_text(command: list[str]) -> str:
    return " ".join(str(item) for item in command)


def text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def command_rows(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, dict):
            command = str(item.get("command", "")).strip()
            label = str(item.get("label", "")).strip() or f"command_{index}"
        else:
            command = str(item).strip()
            label = f"command_{index}"
        if command:
            rows.append({"label": label, "command": command})
    return rows


def packet_auto_launch_summary(packet: dict[str, Any]) -> dict[str, Any]:
    mt5_run_sheet = (
        packet.get("mt5_run_sheet") if isinstance(packet.get("mt5_run_sheet"), dict) else {}
    )
    commands = (
        mt5_run_sheet.get("commands")
        if isinstance(mt5_run_sheet.get("commands"), dict)
        else {}
    )
    return {
        "auto_launch_command_text": commands.get("auto_launch", ""),
        "auto_launch_command_available": bool(commands.get("auto_launch")),
        "auto_launch_blocked": commands.get("auto_launch_blocked", ""),
        "auto_launch_blocked_reasons": (
            commands.get("auto_launch_blocked_reasons")
            if isinstance(commands.get("auto_launch_blocked_reasons"), list)
            else []
        ),
        "auto_launch_note": commands.get("auto_launch_note", ""),
    }


def queue_launch_command(
    *,
    queue: str,
    queue_launch_json: str,
    queue_launch_md: str,
    detached: bool = False,
) -> list[str]:
    command = [
        sys.executable,
        "methods/swing_eval/analysis/mt5_manual_queue_launch.py",
        "--queue",
        queue,
        "--output-json",
        queue_launch_json,
        "--output-md",
        queue_launch_md,
    ]
    if detached:
        command.append("--detached")
    return command


def completed_collect_process(returncode: int) -> bool:
    return returncode in (0, 2)


def completed_status_process(returncode: int) -> bool:
    return returncode in (0, 2)


def process_summary(result: subprocess.CompletedProcess[str], payload: dict[str, Any]) -> dict[str, Any]:
    queue_refresh = payload.get("queue_refresh") if isinstance(payload.get("queue_refresh"), dict) else {}
    return {
        "command": list(result.args) if isinstance(result.args, (list, tuple)) else result.args,
        "returncode": result.returncode,
        "completed": completed_collect_process(result.returncode),
        "ok": completed_collect_process(result.returncode),
        "status": payload.get("status", ""),
        "next_action": payload.get("next_action", ""),
        "selected_count": payload.get("selected_count", ""),
        "ready_entry_count": payload.get("ready_entry_count", ""),
        "waiting_count": payload.get("waiting_count", ""),
        "invalid_count": payload.get("invalid_count", ""),
        "queue_refresh_status": payload.get("queue_refresh_status") or queue_refresh.get("status", ""),
        "queue_refresh_ok": payload.get("queue_refresh_ok")
        if payload.get("queue_refresh_ok") not in (None, "")
        else queue_refresh.get("ok", ""),
        "stdout_tail": tail_text(result.stdout or ""),
        "stderr_tail": tail_text(result.stderr or ""),
        "summary": payload,
    }


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def ready_to_execute(summary: dict[str, Any]) -> bool:
    return (
        summary.get("status") == "ready_for_collect_execute"
        and int_value(summary.get("selected_count")) > 0
        and int_value(summary.get("invalid_count")) == 0
    )


def refresh_operator_packet(
    *,
    queue: str,
    operator_packet_json: str = "",
    operator_packet_md: str = "",
    queue_launch_json: str = "",
    bridge_recovery_plan_json: str = "",
    strategy_analysis_json: str = "",
) -> dict[str, Any]:
    if not operator_packet_json and not operator_packet_md:
        return {
            "enabled": False,
            "ok": "",
            "status": "not_requested",
            "queue": queue,
            "output_json": operator_packet_json,
            "output_md": operator_packet_md,
            "next_queue_step": "",
            "next_operator_action": "",
            "next_operator_mode": "",
            "next_operator_instruction": "",
            "next_operator_command_text": "",
            "next_operator_before_mt5_command_text": "",
            "next_operator_follow_up_command_text": "",
            "manual_run_start_mark_command_text": "",
            "auto_launch_command_text": "",
            "auto_launch_command_available": False,
            "auto_launch_blocked": "",
            "auto_launch_blocked_reasons": [],
            "auto_launch_note": "",
            "step_count": "",
            "static_strategy_config_count": "",
            "static_strategy_configs": [],
            "static_candidate_label_count": "",
            "static_candidate_labels": [],
            "launch_state": "",
            "bridge_recovery_plan_json": bridge_recovery_plan_json,
            "strategy_analysis_json": strategy_analysis_json,
            "bridge_status": "",
            "bridge_ready_for_mt5_validation": "",
            "standalone_strategy_tester_allowed": "",
            "bridge_verification_commands": [],
            "bridge_verification_command_count": 0,
            "bridge_verification_command_labels": [],
            "strategy_status": "",
            "strategy_back_forward_decision_status": "",
            "strategy_back_forward_decision_adoptable": "",
            "strategy_back_forward_decision_next_action": "",
            "strategy_back_forward_decision_collect_command_text": "",
            "strategy_back_forward_decision_sample_shortage_recovery_command_text": "",
            "strategy_back_forward_decision_sample_shortage_recovery_range_strategy": "",
            "strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date": "",
            "strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date": "",
            "strategy_operator_decision_status": "",
            "strategy_operator_decision_verdict": "",
            "strategy_operator_decision_adoptable": "",
            "strategy_operator_decision_primary_blocker": "",
            "strategy_operator_decision_primary_reason": "",
            "strategy_operator_decision_next_action": "",
            "strategy_operator_decision_summary": "",
            "strategy_operator_decision_command_text": "",
            "strategy_operator_decision_follow_up_command_text": "",
            "strategy_source_time_refresh_status": "",
            "strategy_source_time_issue_labels": [],
            "strategy_source_time_candidate_issue_labels": [],
            "strategy_source_time_refresh_analysis_command_text": "",
            "strategy_buy_candidate_gap_status": "",
            "strategy_buy_candidate_gap_reason": "",
            "strategy_buy_candidate_gap_diagnostic_labels": [],
            "strategy_buy_candidate_gap_collect_refresh_command_text": "",
            "error": "",
        }
    try:
        queue_payload = read_operator_queue(queue)
        queue_launch_payload = read_operator_queue(queue_launch_json) if queue_launch_json else {}
        bridge_recovery_payload = (
            read_operator_queue(bridge_recovery_plan_json) if bridge_recovery_plan_json else {}
        )
        strategy_analysis_payload = (
            read_operator_queue(strategy_analysis_json) if strategy_analysis_json else {}
        )
        packet = build_operator_packet(
            queue_payload,
            queue_path=queue,
            queue_launch=queue_launch_payload,
            queue_launch_path=queue_launch_json,
            bridge_recovery=bridge_recovery_payload,
            bridge_recovery_path=bridge_recovery_plan_json,
            strategy_analysis=strategy_analysis_payload,
            strategy_analysis_path=strategy_analysis_json,
        )
        if operator_packet_json:
            write_json_file(operator_packet_json, packet)
        if operator_packet_md:
            write_text_file(operator_packet_md, format_operator_packet_markdown(packet))
        launch_status = (
            packet.get("launch_status") if isinstance(packet.get("launch_status"), dict) else {}
        )
        bridge_recovery = (
            packet.get("bridge_recovery") if isinstance(packet.get("bridge_recovery"), dict) else {}
        )
        strategy_analysis = (
            packet.get("strategy_analysis")
            if isinstance(packet.get("strategy_analysis"), dict)
            else {}
        )
        next_operator_action = (
            packet.get("next_operator_action")
            if isinstance(packet.get("next_operator_action"), dict)
            else {}
        )
        after_mt5 = packet.get("after_mt5") if isinstance(packet.get("after_mt5"), dict) else {}
        auto_launch = packet_auto_launch_summary(packet)
        manual_run_start_mark_command = str(
            after_mt5.get("manual_run_start_mark_command_text")
            or packet.get("manual_run_start_mark_command_text")
            or ""
        )
        bridge_verification_commands = command_rows(bridge_recovery.get("verification_commands"))
        return {
            "enabled": True,
            "ok": packet.get("ok") is True,
            "status": packet.get("status", ""),
            "queue": queue,
            "output_json": operator_packet_json,
            "output_md": operator_packet_md,
            "next_queue_step": packet.get("next_queue_step", ""),
            "next_operator_action": next_operator_action.get("action", ""),
            "next_operator_mode": next_operator_action.get("mode", ""),
            "next_operator_quick_input": next_operator_action.get("quick_input", {}),
            "next_operator_instruction": next_operator_action.get("instruction", ""),
            "next_operator_command_text": next_operator_action.get("command_text", ""),
            "next_operator_before_mt5_command_text": manual_run_start_mark_command,
            "next_operator_follow_up_command_text": next_operator_action.get(
                "follow_up_command_text",
                "",
            ),
            "manual_run_start_mark_command_text": manual_run_start_mark_command,
            **auto_launch,
            "step_count": packet.get("step_count", ""),
            "static_strategy_config_count": packet.get("static_strategy_config_count", ""),
            "static_strategy_configs": (
                packet.get("static_strategy_configs")
                if isinstance(packet.get("static_strategy_configs"), list)
                else []
            ),
            "static_candidate_label_count": packet.get("static_candidate_label_count", ""),
            "static_candidate_labels": (
                packet.get("static_candidate_labels")
                if isinstance(packet.get("static_candidate_labels"), list)
                else []
            ),
            "launch_state": launch_status.get("auto_launch_state", ""),
            "bridge_recovery_plan_json": bridge_recovery_plan_json,
            "strategy_analysis_json": strategy_analysis_json,
            "bridge_status": bridge_recovery.get("status", ""),
            "bridge_ready_for_mt5_validation": bridge_recovery.get("ready_for_mt5_validation", ""),
            "standalone_strategy_tester_allowed": bridge_recovery.get(
                "standalone_strategy_tester_allowed",
                "",
            ),
            "bridge_verification_commands": bridge_verification_commands,
            "bridge_verification_command_count": len(bridge_verification_commands),
            "bridge_verification_command_labels": [
                row["label"] for row in bridge_verification_commands
            ],
            "strategy_status": strategy_analysis.get("status", ""),
            "strategy_back_forward_decision_status": strategy_analysis.get(
                "back_forward_decision_status",
                "",
            ),
            "strategy_back_forward_decision_adoptable": strategy_analysis.get(
                "back_forward_decision_adoptable",
                "",
            ),
            "strategy_back_forward_decision_next_action": strategy_analysis.get(
                "back_forward_decision_next_action",
                "",
            ),
            "strategy_back_forward_decision_collect_command_text": strategy_analysis.get(
                "back_forward_decision_collect_command_text",
                "",
            ),
            "strategy_back_forward_decision_sample_shortage_recovery_command_text": (
                strategy_analysis.get(
                    "back_forward_decision_sample_shortage_recovery_command_text",
                    "",
                )
            ),
            "strategy_back_forward_decision_sample_shortage_recovery_range_strategy": (
                strategy_analysis.get(
                    "back_forward_decision_sample_shortage_recovery_range_strategy",
                    "",
                )
            ),
            "strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date": (
                strategy_analysis.get(
                    "back_forward_decision_sample_shortage_recovery_suggested_from_date",
                    "",
                )
            ),
            "strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date": (
                strategy_analysis.get(
                    "back_forward_decision_sample_shortage_recovery_suggested_to_date",
                    "",
                )
            ),
            "strategy_operator_decision_status": strategy_analysis.get(
                "operator_decision_status",
                "",
            ),
            "strategy_operator_decision_verdict": strategy_analysis.get(
                "operator_decision_verdict",
                "",
            ),
            "strategy_operator_decision_adoptable": strategy_analysis.get(
                "operator_decision_adoptable",
                "",
            ),
            "strategy_operator_decision_primary_blocker": strategy_analysis.get(
                "operator_decision_primary_blocker",
                "",
            ),
            "strategy_operator_decision_primary_reason": strategy_analysis.get(
                "operator_decision_primary_reason",
                "",
            ),
            "strategy_operator_decision_next_action": strategy_analysis.get(
                "operator_decision_next_action",
                "",
            ),
            "strategy_operator_decision_summary": strategy_analysis.get(
                "operator_decision_summary",
                "",
            ),
            "strategy_operator_decision_command_text": strategy_analysis.get(
                "operator_decision_command_text",
                "",
            ),
            "strategy_operator_decision_follow_up_command_text": strategy_analysis.get(
                "operator_decision_follow_up_command_text",
                "",
            ),
            "strategy_source_time_refresh_status": strategy_analysis.get(
                "source_time_refresh_status",
                "",
            ),
            "strategy_source_time_issue_labels": text_list(
                strategy_analysis.get("source_time_issue_labels")
            ),
            "strategy_source_time_candidate_issue_labels": text_list(
                strategy_analysis.get("source_time_candidate_issue_labels")
            ),
            "strategy_source_time_refresh_analysis_command_text": strategy_analysis.get(
                "source_time_refresh_analysis_command_text",
                "",
            ),
            "strategy_buy_candidate_gap_status": strategy_analysis.get(
                "buy_candidate_gap_status",
                "",
            ),
            "strategy_buy_candidate_gap_reason": strategy_analysis.get(
                "buy_candidate_gap_reason",
                "",
            ),
            "strategy_buy_candidate_gap_diagnostic_labels": text_list(
                strategy_analysis.get("buy_candidate_gap_diagnostic_labels")
            ),
            "strategy_buy_candidate_gap_collect_refresh_command_text": strategy_analysis.get(
                "buy_candidate_gap_collect_refresh_command_text",
                "",
            ),
            "error": "",
        }
    except Exception as exc:  # pragma: no cover - defensive status payload
        return {
            "enabled": True,
            "ok": False,
            "status": "operator_packet_refresh_failed",
            "queue": queue,
            "output_json": operator_packet_json,
            "output_md": operator_packet_md,
            "next_queue_step": "",
            "next_operator_action": "",
            "next_operator_mode": "",
            "next_operator_instruction": "",
            "next_operator_command_text": "",
            "next_operator_before_mt5_command_text": "",
            "next_operator_follow_up_command_text": "",
            "manual_run_start_mark_command_text": "",
            "auto_launch_command_text": "",
            "auto_launch_command_available": False,
            "auto_launch_blocked": "",
            "auto_launch_blocked_reasons": [],
            "auto_launch_note": "",
            "step_count": "",
            "static_strategy_config_count": "",
            "static_strategy_configs": [],
            "static_candidate_label_count": "",
            "static_candidate_labels": [],
            "launch_state": "",
            "bridge_recovery_plan_json": bridge_recovery_plan_json,
            "strategy_analysis_json": strategy_analysis_json,
            "bridge_status": "",
            "bridge_ready_for_mt5_validation": "",
            "standalone_strategy_tester_allowed": "",
            "bridge_verification_commands": [],
            "bridge_verification_command_count": 0,
            "bridge_verification_command_labels": [],
            "strategy_status": "",
            "strategy_back_forward_decision_status": "",
            "strategy_back_forward_decision_adoptable": "",
            "strategy_back_forward_decision_next_action": "",
            "strategy_back_forward_decision_collect_command_text": "",
            "strategy_back_forward_decision_sample_shortage_recovery_command_text": "",
            "strategy_back_forward_decision_sample_shortage_recovery_range_strategy": "",
            "strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date": "",
            "strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date": "",
            "strategy_operator_decision_status": "",
            "strategy_operator_decision_verdict": "",
            "strategy_operator_decision_adoptable": "",
            "strategy_operator_decision_primary_blocker": "",
            "strategy_operator_decision_primary_reason": "",
            "strategy_operator_decision_next_action": "",
            "strategy_operator_decision_summary": "",
            "strategy_operator_decision_command_text": "",
            "strategy_operator_decision_follow_up_command_text": "",
            "strategy_source_time_refresh_status": "",
            "strategy_source_time_issue_labels": [],
            "strategy_source_time_candidate_issue_labels": [],
            "strategy_source_time_refresh_analysis_command_text": "",
            "strategy_buy_candidate_gap_status": "",
            "strategy_buy_candidate_gap_reason": "",
            "strategy_buy_candidate_gap_diagnostic_labels": [],
            "strategy_buy_candidate_gap_collect_refresh_command_text": "",
            "error": f"{type(exc).__name__}: {exc}",
        }


def refresh_queue_launch(
    *,
    queue: str,
    queue_launch_json: str = "",
    queue_launch_md: str = "",
) -> dict[str, Any]:
    existing_payload = read_operator_queue(queue_launch_json) if queue_launch_json else {}
    detached = existing_payload.get("detached") is True
    if not queue_launch_json and not queue_launch_md:
        return {
            "enabled": False,
            "completed": "",
            "ok": "",
            "status": "not_requested",
            "queue": queue,
            "output_json": queue_launch_json,
            "output_md": queue_launch_md,
            "next_action": "",
            "blocked": "",
            "blocked_reasons": [],
            "launch_command_kind": "",
            "detached": detached,
            "process_pid": "",
            "running_terminal_count": "",
            "selected_matches_queue_handoff": "",
            "returncode": "",
            "stdout_tail": "",
            "stderr_tail": "",
            "summary": {},
        }
    command = queue_launch_command(
        queue=queue,
        queue_launch_json=queue_launch_json,
        queue_launch_md=queue_launch_md,
        detached=detached,
    )
    result = subprocess.run(command, text=True, capture_output=True)
    stdout_payload = parse_json_stdout(result.stdout or "")
    file_payload = read_operator_queue(queue_launch_json) if queue_launch_json else {}
    payload = file_payload or stdout_payload
    completed = completed_status_process(result.returncode)
    return {
        "enabled": True,
        "command": command,
        "completed": completed,
        "ok": completed,
        "status": payload.get("status", ""),
        "queue": queue,
        "output_json": queue_launch_json,
        "output_md": queue_launch_md,
        "next_action": payload.get("next_action", ""),
        "blocked": payload.get("blocked", ""),
        "blocked_reasons": (
            payload.get("blocked_reasons") if isinstance(payload.get("blocked_reasons"), list) else []
        ),
        "launch_command_kind": payload.get("launch_command_kind", ""),
        "detached": payload.get("detached", detached),
        "process_pid": payload.get("process_pid", ""),
        "running_terminal_count": payload.get("running_terminal_count", ""),
        "selected_matches_queue_handoff": payload.get("selected_matches_queue_handoff", ""),
        "returncode": result.returncode,
        "stdout_tail": tail_text(result.stdout or ""),
        "stderr_tail": tail_text(result.stderr or ""),
        "summary": payload,
    }


def collect_once(
    *,
    queue: str,
    collect_output_json: str,
    collect_output_md: str,
    execute_ready: bool,
    refresh_post_collect_analysis: bool = True,
    run_index: int = 1,
    queue_launch_json: str = "",
    queue_launch_md: str = "",
    bridge_recovery_plan_json: str = "",
    strategy_analysis_json: str = "",
    operator_packet_json: str = "",
    operator_packet_md: str = "",
) -> dict[str, Any]:
    started_epoch = time.time()
    started_at = datetime.now().strftime(TIME_FORMAT)
    dry_command = collect_command(
        queue=queue,
        collect_output_json=collect_output_json,
        collect_output_md=collect_output_md,
        execute=False,
        refresh_post_collect_analysis=False,
    )
    execute_collect_command = collect_command(
        queue=queue,
        collect_output_json=collect_output_json,
        collect_output_md=collect_output_md,
        execute=True,
        refresh_post_collect_analysis=refresh_post_collect_analysis,
    )
    dry_result = subprocess.run(dry_command, text=True, capture_output=True)
    dry_payload = parse_json_stdout(dry_result.stdout or "")
    dry_summary = process_summary(dry_result, dry_payload)
    dry_completed = completed_collect_process(dry_result.returncode)
    queue_launch_refresh = refresh_queue_launch(
        queue=queue,
        queue_launch_json=queue_launch_json,
        queue_launch_md=queue_launch_md,
    )
    operator_packet_refresh = refresh_operator_packet(
        queue=queue,
        operator_packet_json=operator_packet_json,
        operator_packet_md=operator_packet_md,
        queue_launch_json=queue_launch_json,
        bridge_recovery_plan_json=bridge_recovery_plan_json,
        strategy_analysis_json=strategy_analysis_json,
    )
    source_time_analysis_command = str(
        operator_packet_refresh.get("strategy_source_time_refresh_analysis_command_text") or ""
    )
    source_time_refresh_status = str(
        operator_packet_refresh.get("strategy_source_time_refresh_status") or ""
    )
    source_time_issue_labels = text_list(
        operator_packet_refresh.get("strategy_source_time_issue_labels")
    )
    source_time_candidate_issue_labels = text_list(
        operator_packet_refresh.get("strategy_source_time_candidate_issue_labels")
    )
    buy_gap_collect_command = str(
        operator_packet_refresh.get("strategy_buy_candidate_gap_collect_refresh_command_text") or ""
    )
    buy_gap_status = str(operator_packet_refresh.get("strategy_buy_candidate_gap_status") or "")
    buy_gap_reason = str(operator_packet_refresh.get("strategy_buy_candidate_gap_reason") or "")
    buy_gap_diagnostic_labels = text_list(
        operator_packet_refresh.get("strategy_buy_candidate_gap_diagnostic_labels")
    )
    back_forward_collect_command = str(
        operator_packet_refresh.get("strategy_back_forward_decision_collect_command_text") or ""
    )
    back_forward_recovery_command = str(
        operator_packet_refresh.get(
            "strategy_back_forward_decision_sample_shortage_recovery_command_text"
        )
        or ""
    )
    bridge_verification_commands = command_rows(
        operator_packet_refresh.get("bridge_verification_commands")
    )
    ready = dry_completed and ready_to_execute(dry_payload)
    if ready and operator_packet_json:
        packet_payload = read_operator_queue(operator_packet_json)
        if packet_payload:
            ready_count = (
                dry_payload.get("selected_count")
                or dry_payload.get("ready_entry_count")
                or packet_payload.get("ready_to_collect_count")
                or 1
            )
            next_operator_action = summarize_next_operator_action(
                next_step=(
                    packet_payload.get("next_step")
                    if isinstance(packet_payload.get("next_step"), dict)
                    else {}
                ),
                launch_status=(
                    packet_payload.get("launch_status")
                    if isinstance(packet_payload.get("launch_status"), dict)
                    else {}
                ),
                after_mt5=(
                    packet_payload.get("after_mt5")
                    if isinstance(packet_payload.get("after_mt5"), dict)
                    else {}
                ),
                ready_to_collect_count=ready_count,
                waiting_count=dry_payload.get("waiting_count", ""),
                blocking_reasons=dry_payload.get("blocking_reasons", []),
            )
            packet_payload["next_operator_action"] = next_operator_action
            packet_payload["next_operator_action_name"] = next_operator_action.get("action", "")
            packet_payload["next_operator_mode"] = next_operator_action.get("mode", "")
            packet_payload["next_operator_queue_step"] = next_operator_action.get("queue_step", "")
            packet_payload["next_operator_quick_input"] = next_operator_action.get(
                "quick_input", {}
            )
            packet_payload["next_operator_launch_state"] = next_operator_action.get("launch_state", "")
            packet_payload["next_operator_instruction"] = next_operator_action.get("instruction", "")
            packet_payload["next_operator_command_text"] = next_operator_action.get("command_text", "")
            packet_payload["next_operator_follow_up_command_text"] = next_operator_action.get(
                "follow_up_command_text",
                "",
            )
            packet_payload["next_operator_verification"] = next_operator_action.get(
                "verification", ""
            )
            write_json_file(operator_packet_json, packet_payload)
            if operator_packet_md:
                write_text_file(operator_packet_md, format_operator_packet_markdown(packet_payload))
            operator_packet_refresh = {
                **operator_packet_refresh,
                "next_operator_action": next_operator_action.get("action", ""),
                "next_operator_mode": next_operator_action.get("mode", ""),
                "next_operator_instruction": next_operator_action.get("instruction", ""),
                "next_operator_command_text": next_operator_action.get("command_text", ""),
                "next_operator_before_mt5_command_text": operator_packet_refresh.get(
                    "next_operator_before_mt5_command_text", ""
                ),
                "next_operator_follow_up_command_text": next_operator_action.get(
                    "follow_up_command_text",
                    "",
                ),
            }
    execution: dict[str, Any] = {
        "enabled": execute_ready,
        "attempted": False,
        "command": [],
        "returncode": "",
        "completed": False,
        "ok": "",
        "status": "not_requested" if not execute_ready else "not_ready",
        "next_action": "",
        "selected_count": "",
        "waiting_count": "",
        "invalid_count": "",
        "stdout_tail": "",
        "stderr_tail": "",
        "summary": {},
    }

    if ready and execute_ready:
        execute_command = execute_collect_command
        execute_result = subprocess.run(execute_command, text=True, capture_output=True)
        execute_payload = parse_json_stdout(execute_result.stdout or "")
        execution = process_summary(execute_result, execute_payload)
        execution["enabled"] = True
        execution["attempted"] = True

    if not dry_completed:
        status = "dry_run_failed"
        next_action = "inspect_manual_collect_dry_run_error"
        ok = False
    elif ready and execute_ready:
        status = str(execution.get("status") or "collect_execute_failed")
        next_action = str(execution.get("next_action") or "refresh_mt5_tester_status_after_collect")
        ok = execution.get("returncode") == 0 and status == "collect_executed"
        if not ok:
            status = "collect_execute_failed"
            next_action = "inspect_manual_collect_execution_errors"
    elif ready:
        status = "ready_for_collect_execute"
        next_action = "run_with_execute_ready_or_manual_collect_execute"
        ok = True
    else:
        status = str(dry_payload.get("status") or "waiting_for_ready_collect_entries")
        next_action = str(dry_payload.get("next_action") or "run_manual_strategy_tester_steps_and_wait_for_reports")
        ok = True
    if operator_packet_refresh.get("enabled") is True and operator_packet_refresh.get("ok") is not True:
        ok = False
        if status not in ("dry_run_failed", "collect_execute_failed"):
            status = "operator_packet_refresh_failed"
            next_action = "inspect_mt5_manual_operator_packet_refresh"
    if queue_launch_refresh.get("enabled") is True and queue_launch_refresh.get("ok") is not True:
        ok = False
        if status not in ("dry_run_failed", "collect_execute_failed", "operator_packet_refresh_failed"):
            status = "queue_launch_refresh_failed"
            next_action = "inspect_mt5_manual_queue_launch_refresh"

    finished_epoch = time.time()
    finished_at = datetime.now().strftime(TIME_FORMAT)
    manual_run_start_mark_command = str(
        operator_packet_refresh.get("manual_run_start_mark_command_text")
        or operator_packet_refresh.get("next_operator_before_mt5_command_text")
        or ""
    )
    auto_launch_command = str(operator_packet_refresh.get("auto_launch_command_text") or "")
    auto_launch_blocked_reasons = (
        operator_packet_refresh.get("auto_launch_blocked_reasons")
        if isinstance(operator_packet_refresh.get("auto_launch_blocked_reasons"), list)
        else []
    )
    selected_count = dry_summary.get("selected_count", "")
    ready_entry_count = dry_summary.get("ready_entry_count", "")
    waiting_count = dry_summary.get("waiting_count", "")
    invalid_count = dry_summary.get("invalid_count", "")
    return {
        "schema_version": SCHEMA_VERSION,
        "implementation_version": IMPLEMENTATION_VERSION,
        "generated_at": finished_at,
        "started_at": started_at,
        "started_epoch": started_epoch,
        "finished_at": finished_at,
        "finished_epoch": finished_epoch,
        "elapsed_seconds": round(finished_epoch - started_epoch, 3),
        "run_index": run_index,
        "ok": ok,
        "status": status,
        "next_action": next_action,
        "queue": queue,
        "collect_output_json": collect_output_json,
        "collect_output_md": collect_output_md,
        "collect_dry_run_command_text": command_text(dry_command),
        "collect_execute_command_text": command_text(execute_collect_command),
        "execute_ready": execute_ready,
        "refresh_post_collect_analysis": refresh_post_collect_analysis,
        "ready_to_execute": ready,
        "ready_for_collect_execute": ready,
        "selected_count": selected_count,
        "ready_entry_count": ready_entry_count,
        "waiting_count": waiting_count,
        "invalid_count": invalid_count,
        "queue_launch_json": queue_launch_json,
        "queue_launch_md": queue_launch_md,
        "queue_launch_refresh": queue_launch_refresh,
        "queue_launch_refresh_detached": queue_launch_refresh.get("detached", ""),
        "bridge_recovery_plan_json": bridge_recovery_plan_json,
        "strategy_analysis_json": strategy_analysis_json,
        "operator_packet_json": operator_packet_json,
        "operator_packet_md": operator_packet_md,
        "operator_packet_refresh": operator_packet_refresh,
        "operator_packet_manual_run_start_mark_command_text": manual_run_start_mark_command,
        "operator_packet_manual_run_start_mark_command_available": bool(
            manual_run_start_mark_command
        ),
        "operator_packet_auto_launch_command_text": auto_launch_command,
        "operator_packet_auto_launch_command_available": bool(auto_launch_command),
        "operator_packet_auto_launch_blocked": operator_packet_refresh.get(
            "auto_launch_blocked", ""
        ),
        "operator_packet_auto_launch_blocked_reasons": auto_launch_blocked_reasons,
        "operator_packet_auto_launch_note": operator_packet_refresh.get("auto_launch_note", ""),
        "operator_packet_strategy_source_time_refresh_status": source_time_refresh_status,
        "operator_packet_strategy_source_time_issue_labels": source_time_issue_labels,
        "operator_packet_strategy_source_time_candidate_issue_labels": (
            source_time_candidate_issue_labels
        ),
        "operator_packet_strategy_source_time_refresh_analysis_command_text": (
            source_time_analysis_command
        ),
        "operator_packet_strategy_source_time_refresh_analysis_command_available": bool(
            source_time_analysis_command
        ),
        "operator_packet_strategy_buy_candidate_gap_status": buy_gap_status,
        "operator_packet_strategy_buy_candidate_gap_reason": buy_gap_reason,
        "operator_packet_strategy_buy_candidate_gap_diagnostic_labels": (
            buy_gap_diagnostic_labels
        ),
        "operator_packet_strategy_buy_candidate_gap_collect_refresh_command_text": (
            buy_gap_collect_command
        ),
        "operator_packet_strategy_buy_candidate_gap_collect_refresh_command_available": bool(
            buy_gap_collect_command
        ),
        "operator_packet_strategy_back_forward_decision_status": operator_packet_refresh.get(
            "strategy_back_forward_decision_status",
            "",
        ),
        "operator_packet_strategy_back_forward_decision_next_action": operator_packet_refresh.get(
            "strategy_back_forward_decision_next_action",
            "",
        ),
        "operator_packet_strategy_back_forward_decision_collect_command_text": (
            back_forward_collect_command
        ),
        "operator_packet_strategy_back_forward_decision_sample_shortage_recovery_command_text": (
            back_forward_recovery_command
        ),
        "operator_packet_strategy_back_forward_decision_sample_shortage_recovery_range_strategy": (
            operator_packet_refresh.get(
                "strategy_back_forward_decision_sample_shortage_recovery_range_strategy",
                "",
            )
        ),
        "operator_packet_strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date": (
            operator_packet_refresh.get(
                "strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date",
                "",
            )
        ),
        "operator_packet_strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date": (
            operator_packet_refresh.get(
                "strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date",
                "",
            )
        ),
        "operator_packet_strategy_operator_decision_status": operator_packet_refresh.get(
            "strategy_operator_decision_status",
            "",
        ),
        "operator_packet_strategy_operator_decision_verdict": operator_packet_refresh.get(
            "strategy_operator_decision_verdict",
            "",
        ),
        "operator_packet_strategy_operator_decision_adoptable": operator_packet_refresh.get(
            "strategy_operator_decision_adoptable",
            "",
        ),
        "operator_packet_strategy_operator_decision_primary_blocker": operator_packet_refresh.get(
            "strategy_operator_decision_primary_blocker",
            "",
        ),
        "operator_packet_strategy_operator_decision_primary_reason": operator_packet_refresh.get(
            "strategy_operator_decision_primary_reason",
            "",
        ),
        "operator_packet_strategy_operator_decision_next_action": operator_packet_refresh.get(
            "strategy_operator_decision_next_action",
            "",
        ),
        "operator_packet_strategy_operator_decision_summary": operator_packet_refresh.get(
            "strategy_operator_decision_summary",
            "",
        ),
        "operator_packet_strategy_operator_decision_command_text": operator_packet_refresh.get(
            "strategy_operator_decision_command_text",
            "",
        ),
        "operator_packet_strategy_operator_decision_follow_up_command_text": operator_packet_refresh.get(
            "strategy_operator_decision_follow_up_command_text",
            "",
        ),
        "operator_packet_bridge_verification_commands": bridge_verification_commands,
        "operator_packet_bridge_verification_command_count": len(bridge_verification_commands),
        "operator_packet_bridge_verification_command_labels": [
            row["label"] for row in bridge_verification_commands
        ],
        "dry_run": dry_summary,
        "execution": execution,
    }


def format_markdown(report: dict[str, Any]) -> str:
    dry_run = report.get("dry_run") if isinstance(report.get("dry_run"), dict) else {}
    queue_launch = (
        report.get("queue_launch_refresh")
        if isinstance(report.get("queue_launch_refresh"), dict)
        else {}
    )
    execution = report.get("execution") if isinstance(report.get("execution"), dict) else {}
    operator_refresh = (
        report.get("operator_packet_refresh")
        if isinstance(report.get("operator_packet_refresh"), dict)
        else {}
    )
    bridge_verification_commands = (
        operator_refresh.get("bridge_verification_commands")
        if isinstance(operator_refresh.get("bridge_verification_commands"), list)
        else []
    )
    bridge_verification_command_text = "; ".join(
        f"{markdown_cell(row.get('label', ''))}: `{markdown_cell(row.get('command', ''))}`"
        for row in bridge_verification_commands
        if isinstance(row, dict)
    )
    lines = [
        "# MT5 Manual Auto Collect Watch",
        "",
        f"- Generated at: {report.get('generated_at', '')}",
        f"- Status: {report.get('status', '')}",
        f"- OK: {report.get('ok')}",
        f"- Next action: {report.get('next_action', '')}",
        f"- Queue: `{markdown_cell(report.get('queue', ''))}`",
        f"- Collect output: `{markdown_cell(report.get('collect_output_json', ''))}`",
        f"- Collect dry-run command: `{markdown_cell(report.get('collect_dry_run_command_text', ''))}`",
        f"- Collect execute command: `{markdown_cell(report.get('collect_execute_command_text', ''))}`",
        f"- Execute ready: {report.get('execute_ready')}",
        f"- Ready to execute: {report.get('ready_to_execute')}",
        f"- Ready for collect execute: {report.get('ready_for_collect_execute')}",
        (
            "- Counts: "
            f"selected={report.get('selected_count', '')}, "
            f"waiting={report.get('waiting_count', '')}, "
            f"invalid={report.get('invalid_count', '')}"
        ),
        f"- Queue launch: `{markdown_cell(report.get('queue_launch_json', ''))}`",
        f"- Bridge recovery plan: `{markdown_cell(report.get('bridge_recovery_plan_json', ''))}`",
        f"- Strategy analysis: `{markdown_cell(report.get('strategy_analysis_json', ''))}`",
        f"- Operator packet: `{markdown_cell(report.get('operator_packet_json', ''))}`",
        (
            "- Operator manual run start mark command available: "
            f"{report.get('operator_packet_manual_run_start_mark_command_available')}"
        ),
        (
            "- Operator manual run start mark command: "
            f"`{markdown_cell(report.get('operator_packet_manual_run_start_mark_command_text', ''))}`"
        ),
        (
            "- Operator auto launch command available: "
            f"{report.get('operator_packet_auto_launch_command_available')}"
        ),
        (
            "- Operator auto launch blocked: "
            f"{report.get('operator_packet_auto_launch_blocked')}"
        ),
        (
            "- Operator auto launch blockers: "
            f"{', '.join(str(item) for item in report.get('operator_packet_auto_launch_blocked_reasons', []))}"
        ),
        f"- Operator auto launch note: {markdown_cell(report.get('operator_packet_auto_launch_note', ''))}",
        (
            "- Operator auto launch command after closing MT5: "
            f"`{markdown_cell(report.get('operator_packet_auto_launch_command_text', ''))}`"
        ),
        (
            "- Operator source-time analysis command available: "
            f"{report.get('operator_packet_strategy_source_time_refresh_analysis_command_available')}"
        ),
        (
            "- Operator BUY diagnostic collect command available: "
            f"{report.get('operator_packet_strategy_buy_candidate_gap_collect_refresh_command_available')}"
        ),
        (
            "- Operator Back/Forward sample shortage recovery command available: "
            f"{bool(report.get('operator_packet_strategy_back_forward_decision_sample_shortage_recovery_command_text'))}"
        ),
        (
            "- Operator Back/Forward sample shortage recovery range: "
            f"{report.get('operator_packet_strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date', '')}"
            f"..{report.get('operator_packet_strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date', '')}"
        ),
        "",
        "## Dry Run",
        "",
        f"- Return code: {dry_run.get('returncode', '')}",
        f"- Status: {dry_run.get('status', '')}",
        f"- Selected: {dry_run.get('selected_count', '')}",
        f"- Waiting: {dry_run.get('waiting_count', '')}",
        f"- Invalid: {dry_run.get('invalid_count', '')}",
        f"- Next action: {dry_run.get('next_action', '')}",
        f"- Command: `{markdown_cell(' '.join(str(item) for item in dry_run.get('command', [])) if isinstance(dry_run.get('command'), list) else dry_run.get('command', ''))}`",
        "",
        "## Queue Launch",
        "",
        f"- Enabled: {queue_launch.get('enabled', '')}",
        f"- OK: {queue_launch.get('ok', '')}",
        f"- Status: {queue_launch.get('status', '')}",
        f"- Next action: {queue_launch.get('next_action', '')}",
        f"- Blocked: {queue_launch.get('blocked', '')}",
        f"- Blocked reasons: {', '.join(str(item) for item in queue_launch.get('blocked_reasons', []))}",
        f"- Launch kind: {queue_launch.get('launch_command_kind', '')}",
        f"- Detached: {queue_launch.get('detached', '')}",
        f"- Process PID: {queue_launch.get('process_pid', '')}",
        f"- Running terminal count: {queue_launch.get('running_terminal_count', '')}",
        f"- Output JSON: `{markdown_cell(queue_launch.get('output_json', ''))}`",
        f"- Output MD: `{markdown_cell(queue_launch.get('output_md', ''))}`",
        "",
        "## Operator Packet",
        "",
        f"- Enabled: {operator_refresh.get('enabled', '')}",
        f"- OK: {operator_refresh.get('ok', '')}",
        f"- Status: {operator_refresh.get('status', '')}",
        f"- Next queue step: {operator_refresh.get('next_queue_step', '')}",
        f"- Next operator action: {operator_refresh.get('next_operator_action', '')}",
        f"- Next operator mode: {operator_refresh.get('next_operator_mode', '')}",
        f"- Next operator instruction: {markdown_cell(operator_refresh.get('next_operator_instruction', ''))}",
        f"- Next operator command: `{markdown_cell(operator_refresh.get('next_operator_command_text', ''))}`",
        f"- Before MT5 run: `{markdown_cell(operator_refresh.get('next_operator_before_mt5_command_text', ''))}`",
        f"- Next operator follow-up: `{markdown_cell(operator_refresh.get('next_operator_follow_up_command_text', ''))}`",
        f"- Auto launch blocked: {operator_refresh.get('auto_launch_blocked', '')}",
        f"- Auto launch blockers: {', '.join(str(item) for item in operator_refresh.get('auto_launch_blocked_reasons', []))}",
        f"- Auto launch note: {markdown_cell(operator_refresh.get('auto_launch_note', ''))}",
        f"- Auto launch command after closing MT5: `{markdown_cell(operator_refresh.get('auto_launch_command_text', ''))}`",
        f"- Step count: {operator_refresh.get('step_count', '')}",
        f"- Static strategy configs: {operator_refresh.get('static_strategy_config_count', '')}",
        f"- Static candidate labels: {operator_refresh.get('static_candidate_label_count', '')}",
        f"- Launch state: {operator_refresh.get('launch_state', '')}",
        f"- Bridge status: {operator_refresh.get('bridge_status', '')}",
        f"- Bridge ready for MT5 validation: {operator_refresh.get('bridge_ready_for_mt5_validation', '')}",
        f"- Standalone Strategy Tester allowed: {operator_refresh.get('standalone_strategy_tester_allowed', '')}",
        f"- Bridge verification commands: {bridge_verification_command_text}",
        f"- Strategy status: {operator_refresh.get('strategy_status', '')}",
        (
            "- Strategy operator decision: "
            f"verdict={operator_refresh.get('strategy_operator_decision_verdict', '')}; "
            f"status={operator_refresh.get('strategy_operator_decision_status', '')}; "
            f"adoptable={operator_refresh.get('strategy_operator_decision_adoptable', '')}; "
            f"blocker={operator_refresh.get('strategy_operator_decision_primary_blocker', '')}; "
            f"next={operator_refresh.get('strategy_operator_decision_next_action', '')}"
        ),
        f"- Strategy operator command: `{markdown_cell(operator_refresh.get('strategy_operator_decision_command_text', ''))}`",
        f"- Strategy Back/Forward decision: {operator_refresh.get('strategy_back_forward_decision_status', '')}; next={operator_refresh.get('strategy_back_forward_decision_next_action', '')}",
        f"- Strategy Back/Forward collect: `{markdown_cell(operator_refresh.get('strategy_back_forward_decision_collect_command_text', ''))}`",
        f"- Strategy source-time refresh: {operator_refresh.get('strategy_source_time_refresh_status', '')}",
        f"- Strategy source-time analysis refresh: `{markdown_cell(operator_refresh.get('strategy_source_time_refresh_analysis_command_text', ''))}`",
        f"- Strategy BUY gap: {operator_refresh.get('strategy_buy_candidate_gap_status', '')}",
        f"- Strategy BUY collect: `{markdown_cell(operator_refresh.get('strategy_buy_candidate_gap_collect_refresh_command_text', ''))}`",
        f"- Output JSON: `{markdown_cell(operator_refresh.get('output_json', ''))}`",
        f"- Output MD: `{markdown_cell(operator_refresh.get('output_md', ''))}`",
        "",
        "## Execution",
        "",
        f"- Enabled: {execution.get('enabled', '')}",
        f"- Attempted: {execution.get('attempted', '')}",
        f"- Return code: {execution.get('returncode', '')}",
        f"- Status: {execution.get('status', '')}",
        f"- Selected: {execution.get('selected_count', '')}",
        f"- Next action: {execution.get('next_action', '')}",
    ]
    if execution.get("command"):
        command = execution.get("command")
        command_text = " ".join(str(item) for item in command) if isinstance(command, list) else str(command)
        lines.append(f"- Command: `{markdown_cell(command_text)}`")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch the MT5 manual Strategy Tester queue and optionally collect ready reports."
    )
    parser.add_argument("--queue", default=DEFAULT_OUTPUT_JSON_WITH_OPTIMIZATION)
    parser.add_argument("--collect-output-json", default=DEFAULT_COLLECT_OUTPUT_JSON_WITH_OPTIMIZATION)
    parser.add_argument("--collect-output-md", default=DEFAULT_COLLECT_OUTPUT_MD_WITH_OPTIMIZATION)
    parser.add_argument("--queue-launch-json", default=DEFAULT_QUEUE_LAUNCH_JSON_WITH_OPTIMIZATION)
    parser.add_argument("--queue-launch-md", default=DEFAULT_QUEUE_LAUNCH_MD_WITH_OPTIMIZATION)
    parser.add_argument(
        "--no-refresh-queue-launch",
        dest="refresh_queue_launch",
        action="store_false",
        help="Do not refresh the next MT5 Strategy Tester launch dry-run status.",
    )
    parser.add_argument("--operator-packet-json", default=DEFAULT_OPERATOR_PACKET_JSON)
    parser.add_argument("--operator-packet-md", default=DEFAULT_OPERATOR_PACKET_MD)
    parser.add_argument("--bridge-recovery-plan-json", default=DEFAULT_BRIDGE_RECOVERY_PLAN_JSON)
    parser.add_argument("--strategy-analysis-json", default=DEFAULT_STRATEGY_ANALYSIS_JSON)
    parser.add_argument(
        "--no-refresh-operator-packet",
        dest="refresh_operator_packet",
        action="store_false",
        help="Do not refresh the one-step MT5 manual operator packet after collect dry-run.",
    )
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument(
        "--heartbeat",
        default="",
        help=(
            "Heartbeat path. Defaults to the shared daemon heartbeat only for "
            "--max-runs 0; one-shot runs do not overwrite it unless this is explicit."
        ),
    )
    parser.add_argument(
        "--pid-file",
        default="",
        help=(
            "PID file path. Defaults to the shared daemon PID only for --max-runs 0; "
            "one-shot runs do not overwrite it unless this is explicit."
        ),
    )
    parser.add_argument("--skip-pid-file-write", action="store_true")
    parser.add_argument("--execute-ready", action="store_true", help="Execute ready collect-only commands.")
    parser.add_argument(
        "--no-refresh-post-collect-analysis",
        dest="refresh_post_collect_analysis",
        action="store_false",
        help="Do not refresh Promotion Gate, Strategy Tester Analysis, and Spec Coverage after collect.",
    )
    parser.set_defaults(refresh_post_collect_analysis=True)
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    parser.add_argument("--max-runs", type=int, default=1, help="0 means run forever.")
    parser.set_defaults(refresh_queue_launch=True)
    parser.set_defaults(refresh_operator_packet=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.interval_seconds < 5:
        raise SystemExit("--interval-seconds must be >= 5")
    continuous = args.max_runs == 0
    heartbeat_path = args.heartbeat or (DEFAULT_HEARTBEAT if continuous else "")
    pid_file_path = args.pid_file or (DEFAULT_PID_FILE if continuous else "")
    pid_file_written = False
    if pid_file_path and not args.skip_pid_file_write:
        Path(pid_file_path).parent.mkdir(parents=True, exist_ok=True)
        Path(pid_file_path).write_text(str(os.getpid()) + "\n", encoding="utf-8")
        pid_file_written = True
    runs = 0
    last_report: dict[str, Any] = {}
    while True:
        last_report = collect_once(
            queue=args.queue,
            collect_output_json=args.collect_output_json,
            collect_output_md=args.collect_output_md,
            execute_ready=args.execute_ready,
            refresh_post_collect_analysis=args.refresh_post_collect_analysis,
            run_index=runs + 1,
            queue_launch_json=args.queue_launch_json if args.refresh_queue_launch else "",
            queue_launch_md=args.queue_launch_md if args.refresh_queue_launch else "",
            bridge_recovery_plan_json=(
                args.bridge_recovery_plan_json if args.refresh_operator_packet else ""
            ),
            strategy_analysis_json=(
                args.strategy_analysis_json if args.refresh_operator_packet else ""
            ),
            operator_packet_json=args.operator_packet_json if args.refresh_operator_packet else "",
            operator_packet_md=args.operator_packet_md if args.refresh_operator_packet else "",
        )
        last_report.update(
            {
                "watcher_pid": os.getpid(),
                "pid_file": pid_file_path,
                "pid_file_enabled": bool(pid_file_path),
                "pid_file_written": pid_file_written,
                "max_runs": args.max_runs,
                "continuous": continuous,
                "heartbeat": heartbeat_path,
                "heartbeat_enabled": bool(heartbeat_path),
                "snapshot_required_keys": list(HEARTBEAT_REQUIRED_FIELDS),
            }
        )
        write_json_file(args.output_json, last_report)
        write_text_file(args.output_md, format_markdown(last_report))
        if heartbeat_path:
            write_json_file(heartbeat_path, last_report)
        runs += 1
        if args.max_runs > 0 and runs >= args.max_runs:
            print(json.dumps(last_report, ensure_ascii=False, indent=2))
            return 0 if last_report.get("ok") is True else 2
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
