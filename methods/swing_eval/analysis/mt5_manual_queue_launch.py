from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path

if Path(sys.path[0] if sys.path else "").resolve() == Path(__file__).resolve().parent:
    sys.path.pop(0)

import subprocess
from datetime import datetime
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT
from analysis.mt5_manual_collect import refresh_queue_from_sources
from analysis.mt5_manual_test_queue import (
    DEFAULT_BACK_FORWARD_RUN,
    DEFAULT_BUY_NEXT_ACTION_RUN,
    DEFAULT_PROMOTION_GATE,
    DEFAULT_SELL_NEXT_ACTION_RUN,
    build_queue as build_manual_test_queue,
    format_markdown as format_manual_test_queue_markdown,
    manual_run_start_state_from_queue,
    static_strategy_config_state_from_queue,
)
from analysis.mt5_compile import default_wineprefix, mt5_root_to_drive_c
from analysis.mt5_tester_run import discover_running_terminal_processes


DEFAULT_QUEUE = "runtime/latest_mt5_manual_test_queue.json"
DEFAULT_OUTPUT_JSON = "runtime/latest_mt5_manual_queue_launch.json"
DEFAULT_OUTPUT_MD = "runtime/latest_mt5_manual_queue_launch.md"


def load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def checklist_items(queue: dict[str, Any]) -> list[dict[str, Any]]:
    items = queue.get("execution_checklist")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def launchable_items(queue: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in checklist_items(queue)
        if str(item.get("launch_command_kind") or "")
        and (item.get("launch_command") or item.get("launch_command_text"))
    ]


def queue_progress_metrics(queue: dict[str, Any]) -> dict[str, Any]:
    entries = queue.get("entries") if isinstance(queue.get("entries"), list) else []
    available_entries = [
        entry for entry in entries if isinstance(entry, dict) and entry.get("available") is True
    ]
    checklist = checklist_items(queue)
    completed_ids = compact_list(queue.get("completed_entry_ids"))
    return {
        "queue_entry_count": queue.get("entry_count", len(available_entries)),
        "queue_total_entry_count": queue.get("total_entry_count", len(entries)),
        "queue_stale_entry_count": queue.get("stale_entry_count", ""),
        "queue_completed_count": queue.get("completed_count", len(completed_ids)),
        "queue_completed_entry_count": queue.get("completed_entry_count", len(completed_ids)),
        "queue_completed_entry_ids": completed_ids,
        "queue_step_count": queue.get("step_count", len(checklist)),
        "queue_ready_to_collect_count": queue.get("ready_to_collect_count", ""),
        "queue_waiting_count": queue.get("waiting_count", ""),
        "queue_step_report_ready_count": queue.get("step_report_ready_count", ""),
        "queue_step_waiting_report_count": queue.get("step_waiting_report_count", ""),
        "queue_step_launch_needed_count": queue.get("step_launch_needed_count", ""),
        "queue_all_collect_ready": queue.get("all_collect_ready", ""),
        "queue_blocking_reasons": (
            queue.get("blocking_reasons") if isinstance(queue.get("blocking_reasons"), list) else []
        ),
    }


def step_launch_needed(item: dict[str, Any]) -> bool:
    if item.get("launch_needed") is False:
        return False
    if item.get("step_report_ready") is True:
        return False
    return True


def compact_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item not in (None, "")]


def queue_operator_handoff(queue: dict[str, Any]) -> dict[str, Any]:
    handoff = queue.get("operator_handoff") if isinstance(queue.get("operator_handoff"), dict) else {}
    if not handoff:
        return {}
    next_step = handoff.get("next_mt5_step") if isinstance(handoff.get("next_mt5_step"), dict) else {}
    quick_input = handoff.get("quick_input") if isinstance(handoff.get("quick_input"), dict) else {}
    return {
        "state": handoff.get("state", ""),
        "status": handoff.get("status", ""),
        "next_action": handoff.get("next_action", ""),
        "collect_ready": handoff.get("collect_ready", ""),
        "ready_entry_ids": compact_list(handoff.get("ready_entry_ids")),
        "waiting_entry_ids": compact_list(handoff.get("waiting_entry_ids")),
        "completed_entry_ids": compact_list(handoff.get("completed_entry_ids")),
        "stale_entry_ids": compact_list(handoff.get("stale_entry_ids")),
        "next_queue_step": handoff.get("next_queue_step", ""),
        "next_mt5_step": next_step,
        "quick_input": quick_input,
        "next_step_operator_summary": handoff.get("next_step_operator_summary", ""),
        "next_step_summary": (
            handoff.get("next_step_summary")
            or handoff.get("next_step_operator_summary", "")
        ),
        "next_step_collect_filter_summary": handoff.get("next_step_collect_filter_summary", ""),
        "dry_run_command_text": handoff.get("dry_run_command_text", ""),
        "execute_command_text": handoff.get("execute_command_text", ""),
        "execute_and_refresh_analysis_command_text": handoff.get(
            "execute_and_refresh_analysis_command_text", ""
        ),
        "execute_and_refresh_all_command_text": handoff.get(
            "execute_and_refresh_all_command_text", ""
        ),
        "execute_and_refresh_full_analysis_command_text": (
            handoff.get("execute_and_refresh_full_analysis_command_text")
            or handoff.get("execute_and_refresh_all_command_text", "")
        ),
    }


def queue_entry_source(queue: dict[str, Any], entry_id: str, default_path: str) -> str:
    entries = queue.get("entries") if isinstance(queue.get("entries"), list) else []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("id") or "") == entry_id and entry.get("source_json"):
            return str(entry.get("source_json") or "")
    return default_path


def manual_queue_can_mark_start(queue: dict[str, Any]) -> bool:
    entries = queue.get("entries") if isinstance(queue.get("entries"), list) else []
    return any(
        isinstance(entry, dict)
        and str(entry.get("id") or "")
        in {"back_forward", "score_weight_sell", "score_weight_buy"}
        and entry.get("source_json")
        for entry in entries
    )


def mt5_root_from_queue(queue: dict[str, Any]) -> str:
    for item in checklist_items(queue):
        mt5_config = str(item.get("mt5_config") or "")
        if not mt5_config:
            continue
        parts = Path(mt5_config).parts
        if "MQL5" not in parts:
            continue
        mql5_index = parts.index("MQL5")
        if mql5_index <= 0:
            continue
        return str(Path(*parts[:mql5_index]))
    return ""


def wine_path_from_queue(queue: dict[str, Any]) -> str:
    for item in checklist_items(queue):
        command = item.get("launch_command")
        if isinstance(command, list) and command and isinstance(command[0], str):
            return str(command[0])
    return ""


def launch_environment(queue: dict[str, Any]) -> tuple[dict[str, str], str, str]:
    env = os.environ.copy()
    mt5_root = mt5_root_from_queue(queue)
    wineprefix = default_wineprefix()
    if mt5_root:
        try:
            wineprefix = mt5_root_to_drive_c(Path(mt5_root).expanduser()).parent
        except ValueError:
            wineprefix = default_wineprefix()
    env["WINEPREFIX"] = str(Path(wineprefix).expanduser())
    return env, mt5_root, env["WINEPREFIX"]


def mark_manual_queue_run_start(
    queue: dict[str, Any],
    *,
    queue_path: str | Path,
    generated_at: str,
    promotion_gate: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not queue:
        return queue, {"attempted": False, "status": "queue_missing"}
    if queue.get("manual_run_start_marked") is True:
        return queue, {
            "attempted": False,
            "status": "already_marked",
            "manual_run_start_after": queue.get("manual_run_start_after_override", ""),
        }
    if not manual_queue_can_mark_start(queue):
        return queue, {"attempted": False, "status": "no_source_entries"}
    queue_path_text = str(queue_path)
    effective_promotion_gate = str(promotion_gate or queue.get("promotion_gate_path") or "")
    if not effective_promotion_gate and queue_path_text == DEFAULT_QUEUE:
        effective_promotion_gate = DEFAULT_PROMOTION_GATE
    marked_queue = build_manual_test_queue(
        back_forward_run=queue_entry_source(queue, "back_forward", DEFAULT_BACK_FORWARD_RUN),
        sell_next_action_run=queue_entry_source(
            queue,
            "score_weight_sell",
            DEFAULT_SELL_NEXT_ACTION_RUN,
        ),
        buy_next_action_run=queue_entry_source(queue, "score_weight_buy", DEFAULT_BUY_NEXT_ACTION_RUN),
        promotion_gate=effective_promotion_gate,
        queue_json=queue_path_text,
        generated_at=generated_at,
        mt5_root=mt5_root_from_queue(queue) or None,
        wine_path=wine_path_from_queue(queue) or None,
        static_strategy_configs=queue.get("static_strategy_configs")
        if isinstance(queue.get("static_strategy_configs"), list)
        else [],
        static_candidate_labels=queue.get("static_candidate_labels")
        if isinstance(queue.get("static_candidate_labels"), list)
        else [],
        static_strategy_config_state=static_strategy_config_state_from_queue(queue),
        manual_run_start_state=manual_run_start_state_from_queue(queue),
        manual_run_start_after_override=generated_at,
    )
    marked_queue["queue_json"] = queue_path_text
    output_json = Path(queue_path)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(marked_queue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    output_md = output_json.with_suffix(".md")
    output_md.write_text(format_manual_test_queue_markdown(marked_queue), encoding="utf-8")
    return marked_queue, {
        "attempted": True,
        "status": "marked",
        "manual_run_start_after": generated_at,
        "output_json": str(output_json),
        "output_md": str(output_md),
    }


def selected_matches_handoff(selected: dict[str, Any] | None, handoff: dict[str, Any]) -> bool | str:
    if not selected or not handoff:
        return ""
    next_step = handoff.get("next_mt5_step") if isinstance(handoff.get("next_mt5_step"), dict) else {}
    if not next_step:
        return ""
    return (
        str(selected.get("queue_id") or "") == str(next_step.get("queue_id") or "")
        and str(selected.get("step_label") or "") == str(next_step.get("step_label") or "")
    )


def select_item(
    queue: dict[str, Any],
    *,
    order: int | None = None,
    queue_id: str = "",
    step_label: str = "",
) -> tuple[dict[str, Any] | None, str]:
    items = launchable_items(queue)
    if order is not None:
        for item in items:
            if item.get("order") == order:
                return item, ""
        return None, f"step_order_not_found:{order}"
    if queue_id or step_label:
        for item in items:
            if queue_id and str(item.get("queue_id") or "") != queue_id:
                continue
            if step_label and str(item.get("step_label") or "") != step_label:
                continue
            return item, ""
        parts = []
        if queue_id:
            parts.append(f"queue_id={queue_id}")
        if step_label:
            parts.append(f"step_label={step_label}")
        return None, "step_filter_not_found:" + ",".join(parts)
    if not checklist_items(queue):
        return None, "execution_checklist_empty"
    for item in items:
        if step_launch_needed(item):
            return item, ""
    if items:
        return None, "no_launch_needed_steps"
    return None, "no_launchable_steps"


def command_for_item(item: dict[str, Any]) -> tuple[list[str], str]:
    kind = str(item.get("launch_command_kind") or "")
    if kind == "direct_config":
        command = item.get("launch_command")
        if isinstance(command, list) and all(isinstance(part, str) for part in command):
            return list(command), ""
        text = str(item.get("launch_command_text") or "")
        if text:
            return shlex.split(text), ""
        return [], "missing_direct_config_command"
    if kind == "runner_execute":
        text = str(item.get("launch_command_text") or "")
        if text:
            return shlex.split(text), ""
        return [], "missing_runner_execute_command"
    return [], f"unsupported_launch_command_kind:{kind or 'unknown'}"


def build_launch_plan(
    *,
    queue_path: str | Path = DEFAULT_QUEUE,
    order: int | None = None,
    queue_id: str = "",
    step_label: str = "",
    execute: bool = False,
    allow_running_terminal: bool = False,
    detect_running_terminal: bool = True,
    mark_manual_run_start: bool = True,
    detached: bool = False,
    refresh_queue: bool = False,
    promotion_gate: str = "",
    timeout_seconds: int = 0,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or datetime.now().strftime(TIME_FORMAT)
    queue = load_json(queue_path)
    queue_refresh: dict[str, Any] = {
        "enabled": refresh_queue,
        "ok": "",
        "status": "not_requested",
        "missing_ids": [],
        "refreshed_sources": [],
    }
    if queue and refresh_queue:
        refreshed_queue, queue_refresh = refresh_queue_from_sources(
            queue,
            queue_path=str(queue_path),
            promotion_gate=promotion_gate,
        )
        if queue_refresh.get("ok") is True:
            queue = refreshed_queue
    pre_mark_selected, _ = select_item(queue, order=order, queue_id=queue_id, step_label=step_label)
    mark_result: dict[str, Any] = {
        "attempted": False,
        "status": "not_requested",
        "manual_run_start_after": "",
    }
    if execute and mark_manual_run_start and pre_mark_selected:
        queue, mark_result = mark_manual_queue_run_start(
            queue,
            queue_path=queue_path,
            generated_at=generated,
            promotion_gate=promotion_gate,
        )
    running_processes = discover_running_terminal_processes() if detect_running_terminal else []
    selected, select_error = select_item(queue, order=order, queue_id=queue_id, step_label=step_label)
    handoff = queue_operator_handoff(queue)
    command, command_error = command_for_item(selected) if selected else ([], select_error)
    kind = str((selected or {}).get("launch_command_kind") or "")
    queue_metrics = queue_progress_metrics(queue)
    command_env, command_cwd, command_wineprefix = launch_environment(queue)
    blocked_reasons: list[str] = []
    def add_blocked_reason(reason: str) -> None:
        if reason and reason not in blocked_reasons:
            blocked_reasons.append(reason)

    if not queue:
        add_blocked_reason("queue_missing_or_unreadable")
    if select_error:
        add_blocked_reason(select_error)
    if command_error:
        add_blocked_reason(command_error)
    if (
        selected
        and kind == "direct_config"
        and detect_running_terminal
        and running_processes
        and not allow_running_terminal
    ):
        add_blocked_reason("running_terminal_blocks_direct_config")

    result: dict[str, Any] = {
        "ok": False,
        "generated_at": generated,
        "queue_path": str(queue_path),
        "queue_status": queue.get("status", ""),
        "queue_next_action": queue.get("next_action", ""),
        **queue_metrics,
        "queue_refresh": queue_refresh,
        "queue_refresh_status": queue_refresh.get("status", ""),
        "queue_refresh_ok": queue_refresh.get("ok", ""),
        "queue_refresh_missing_ids": queue_refresh.get("missing_ids", []),
        "queue_operator_handoff": handoff,
        "queue_operator_handoff_state": handoff.get("state", ""),
        "queue_operator_handoff_next_mt5_step": handoff.get("next_mt5_step", {}),
        "queue_operator_handoff_quick_input": handoff.get("quick_input", {}),
        "queue_operator_handoff_next_step_operator_summary": handoff.get(
            "next_step_operator_summary", ""
        ),
        "queue_operator_handoff_next_step_summary": (
            handoff.get("next_step_summary")
            or handoff.get("next_step_operator_summary", "")
        ),
        "queue_operator_handoff_next_step_collect_filter_summary": handoff.get(
            "next_step_collect_filter_summary", ""
        ),
        "queue_operator_handoff_collect_ready": handoff.get("collect_ready", ""),
        "queue_operator_handoff_ready_entry_ids": handoff.get("ready_entry_ids", []),
        "queue_operator_handoff_waiting_entry_ids": handoff.get("waiting_entry_ids", []),
        "queue_operator_handoff_stale_entry_ids": handoff.get("stale_entry_ids", []),
        "queue_operator_handoff_collect_dry_run_command_text": handoff.get(
            "dry_run_command_text", ""
        ),
        "queue_operator_handoff_collect_execute_command_text": handoff.get(
            "execute_command_text", ""
        ),
        "queue_operator_handoff_collect_execute_and_refresh_analysis_command_text": handoff.get(
            "execute_and_refresh_analysis_command_text", ""
        ),
        "queue_operator_handoff_collect_execute_and_refresh_all_command_text": handoff.get(
            "execute_and_refresh_all_command_text", ""
        ),
        "queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text": (
            handoff.get("execute_and_refresh_full_analysis_command_text")
            or handoff.get("execute_and_refresh_all_command_text", "")
        ),
        "execute": execute,
        "detached": detached,
        "allow_running_terminal": allow_running_terminal,
        "detect_running_terminal": detect_running_terminal,
        "mark_manual_run_start": mark_manual_run_start,
        "manual_run_start_mark": mark_result,
        "manual_run_start_mark_status": mark_result.get("status", ""),
        "manual_run_start_mark_attempted": mark_result.get("attempted", False),
        "manual_run_start_after": mark_result.get("manual_run_start_after", ""),
        "running_terminal_count": len(running_processes),
        "running_terminal_processes": running_processes,
        "selected": bool(selected),
        "selected_order": (selected or {}).get("order", ""),
        "selected_queue_id": (selected or {}).get("queue_id", ""),
        "selected_step_label": (selected or {}).get("step_label", ""),
        "selected_queue_step": "/".join(
            part
            for part in (
                str((selected or {}).get("queue_id") or ""),
                str((selected or {}).get("step_label") or ""),
            )
            if part
        ),
        "selected_item": selected or {},
        "selected_step_fingerprint": (selected or {}).get("step_fingerprint", ""),
        "selected_step_config_fingerprint": (selected or {}).get("step_config_fingerprint", ""),
        "selected_step_run_fingerprint": (selected or {}).get("step_run_fingerprint", ""),
        "selected_expected_artifacts": (
            (selected or {}).get("expected_artifacts")
            if isinstance((selected or {}).get("expected_artifacts"), dict)
            else {}
        ),
        "selected_expected_report_artifact": (selected or {}).get("expected_report_artifact", ""),
        "selected_expected_report": (selected or {}).get("report", ""),
        "selected_matches_queue_handoff": selected_matches_handoff(selected, handoff),
        "launch_command_kind": kind,
        "queue_refresh_source_count": queue_refresh.get("source_count", ""),
        "command": command,
        "command_text": shlex.join(command) if command else "",
        "command_cwd": command_cwd,
        "wineprefix": command_wineprefix,
        "timeout_seconds": timeout_seconds,
        "blocked": bool(blocked_reasons),
        "blocked_reasons": blocked_reasons,
        "returncode": "",
        "process_pid": "",
        "stdout_tail": "",
        "stderr_tail": "",
    }
    if blocked_reasons:
        result["status"] = "blocked"
        result["next_action"] = blocked_reasons[0]
        return result
    if not execute:
        result["ok"] = True
        result["status"] = "planned"
        result["next_action"] = "rerun_with_execute_to_launch_selected_step"
        return result

    if detached and kind == "direct_config":
        try:
            process = subprocess.Popen(
                command,
                cwd=command_cwd or None,
                env=command_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            result["status"] = "command_failed"
            result["blocked"] = True
            result["blocked_reasons"] = ["detached_launch_failed"]
            result["stderr_tail"] = str(exc)
            result["next_action"] = "inspect_launch_command_failure"
            return result
        result["ok"] = True
        result["status"] = "launched"
        result["process_pid"] = process.pid
        result["next_action"] = "wait_for_mt5_strategy_tester_report_then_collect"
        return result

    try:
        run_kwargs: dict[str, Any] = {
            "text": True,
            "capture_output": True,
            "timeout": timeout_seconds if timeout_seconds > 0 else None,
        }
        if kind == "direct_config":
            run_kwargs["cwd"] = command_cwd or None
            run_kwargs["env"] = command_env
        completed = subprocess.run(command, **run_kwargs)
    except subprocess.TimeoutExpired as exc:
        result["status"] = "timeout"
        result["blocked"] = True
        result["blocked_reasons"] = ["launch_timeout"]
        result["returncode"] = ""
        result["stdout_tail"] = (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else ""
        result["stderr_tail"] = (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else ""
        result["next_action"] = "inspect_mt5_terminal_or_runner_timeout"
        return result
    result["returncode"] = completed.returncode
    result["stdout_tail"] = (completed.stdout or "")[-2000:]
    result["stderr_tail"] = (completed.stderr or "")[-2000:]
    result["ok"] = completed.returncode == 0
    result["status"] = "executed" if completed.returncode == 0 else "command_failed"
    result["next_action"] = (
        "wait_for_mt5_strategy_tester_report_then_collect"
        if completed.returncode == 0
        else "inspect_launch_command_failure"
    )
    return result


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def list_text(value: object) -> str:
    return ", ".join(compact_list(value))


def format_markdown(payload: dict[str, Any]) -> str:
    item = payload.get("selected_item") if isinstance(payload.get("selected_item"), dict) else {}
    queue_refresh = payload.get("queue_refresh") if isinstance(payload.get("queue_refresh"), dict) else {}
    handoff = (
        payload.get("queue_operator_handoff")
        if isinstance(payload.get("queue_operator_handoff"), dict)
        else {}
    )
    handoff_next = (
        handoff.get("next_mt5_step")
        if isinstance(handoff.get("next_mt5_step"), dict)
        else {}
    )
    lines = [
        "# MT5 Manual Queue Launch",
        "",
        f"- Generated at: {payload.get('generated_at', '')}",
        f"- Status: {payload.get('status', '')}",
        f"- OK: {payload.get('ok')}",
        f"- Execute: {payload.get('execute')}",
        f"- Detached: {payload.get('detached')}",
        f"- Queue: {payload.get('queue_path', '')}",
        f"- Queue status: {payload.get('queue_status', '')}",
        f"- Queue next action: {payload.get('queue_next_action', '')}",
        (
            "- Queue progress: "
            f"entries={payload.get('queue_entry_count', '')}/"
            f"{payload.get('queue_total_entry_count', '')}, "
            f"steps={payload.get('queue_step_count', '')}, "
            f"completed={payload.get('queue_completed_entry_count', '')}, "
            f"ready={payload.get('queue_ready_to_collect_count', '')}, "
            f"waiting={payload.get('queue_waiting_count', '')}, "
            f"step_ready={payload.get('queue_step_report_ready_count', '')}, "
            f"step_waiting={payload.get('queue_step_waiting_report_count', '')}, "
            f"launch_needed={payload.get('queue_step_launch_needed_count', '')}"
        ),
        f"- Queue blocking reasons: {', '.join(str(reason) for reason in payload.get('queue_blocking_reasons', []))}",
        f"- Queue refresh: {queue_refresh.get('status', '')}",
        f"- Queue refresh OK: {queue_refresh.get('ok', '')}",
        f"- Selected: {payload.get('selected')}",
        f"- Selected fingerprint: {payload.get('selected_step_fingerprint', '')}",
        f"- Selected expected report: {payload.get('selected_expected_report', '')}",
        f"- Launch kind: {payload.get('launch_command_kind', '')}",
        f"- Mark manual run start: {payload.get('manual_run_start_mark_status', '')}",
        f"- Manual run start after: {payload.get('manual_run_start_after', '')}",
        f"- Running terminal count: {payload.get('running_terminal_count', '')}",
        f"- Blocked: {payload.get('blocked')}",
        f"- Blocked reasons: {', '.join(str(reason) for reason in payload.get('blocked_reasons', []))}",
        f"- Next action: {payload.get('next_action', '')}",
        "",
    ]
    if handoff:
        lines.extend(
            [
                "## Queue Operator Handoff",
                "",
                f"- State: {handoff.get('state', '')}",
                f"- Status: {handoff.get('status', '')}",
                f"- Next action: {handoff.get('next_action', '')}",
                f"- Collect ready: {handoff.get('collect_ready', '')}",
                f"- Ready entries: {list_text(handoff.get('ready_entry_ids'))}",
                f"- Waiting entries: {list_text(handoff.get('waiting_entry_ids'))}",
                f"- Completed entries: {list_text(handoff.get('completed_entry_ids'))}",
                f"- Stale entries: {list_text(handoff.get('stale_entry_ids'))}",
                f"- Selected matches handoff: {payload.get('selected_matches_queue_handoff', '')}",
                f"- Next step summary: {markdown_cell(handoff.get('next_step_operator_summary', ''))}",
                f"- Collect filter: {markdown_cell(handoff.get('next_step_collect_filter_summary', ''))}",
                (
                    "- Next MT5 step: "
                    f"{handoff_next.get('queue_id', '')}/{handoff_next.get('step_label', '')}, "
                    f"Symbol={handoff_next.get('symbol', '')}, "
                    f"Period={handoff_next.get('period', '')}, "
                    f"Model={handoff_next.get('model', '')}, "
                    f"Dates={handoff_next.get('dates', '')}, "
                    f"Forward={handoff_next.get('forward', '')}, "
                    f"Inputs={handoff_next.get('inputs', '')}, "
                    f"Report={handoff_next.get('report', '')}"
                ),
                "",
                "### Collect Dry Run",
                "",
                "```bash",
                str(handoff.get("dry_run_command_text") or ""),
                "```",
                "",
                "### Collect Execute",
                "",
                "```bash",
                str(handoff.get("execute_command_text") or ""),
                "```",
                "",
                "### Collect Execute + Analysis",
                "",
                "```bash",
                str(handoff.get("execute_and_refresh_analysis_command_text") or ""),
                "```",
                "",
                "### Collect Execute + Full Analysis",
                "",
                "```bash",
                str(handoff.get("execute_and_refresh_all_command_text") or ""),
                "```",
                "",
            ]
        )
    lines.extend(
        [
        "## Selected Step",
        "",
        "| order | queue/step | symbol | period | model | dates | forward | run type | expected report | report note | step report | launch needed | inputs | report | fingerprint |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---:|---|---|---|",
        (
            f"| {item.get('order', '')} | "
            f"{markdown_cell(item.get('queue_id', ''))}/{markdown_cell(item.get('step_label', ''))} | "
            f"{markdown_cell(item.get('symbol', ''))} | "
            f"{markdown_cell(item.get('period', ''))} | "
            f"{markdown_cell(item.get('model', ''))} | "
            f"{markdown_cell(item.get('dates', ''))} | "
            f"{markdown_cell(item.get('forward', ''))} | "
            f"{markdown_cell(item.get('run_type', ''))} | "
            f"{markdown_cell(item.get('expected_report_artifact', ''))} | "
            f"{markdown_cell(item.get('report_expectation_note', ''))} | "
            f"{markdown_cell(item.get('step_report_status', ''))} | "
            f"{item.get('launch_needed', '')} | "
            f"{markdown_cell(item.get('inputs', ''))} | "
            f"{markdown_cell(item.get('report', ''))} | "
            f"{markdown_cell(item.get('step_fingerprint', ''))} |"
        ),
        "",
        "## Command",
        "",
        f"- CWD: `{markdown_cell(payload.get('command_cwd', ''))}`",
        f"- WINEPREFIX: `{markdown_cell(payload.get('wineprefix', ''))}`",
        "",
        "```bash",
        str(payload.get("command_text") or ""),
        "```",
        "",
        ]
    )
    processes = payload.get("running_terminal_processes")
    if isinstance(processes, list) and processes:
        lines.extend(
            [
                "## Running Terminal Processes",
                "",
                "| pid | command |",
                "|---:|---|",
            ]
        )
        for process in processes:
            if not isinstance(process, dict):
                continue
            lines.append(
                f"| {process.get('pid', '')} | {markdown_cell(process.get('command', ''))} |"
            )
        lines.append("")
    if payload.get("execute"):
        lines.extend(
            [
                "## Execution Result",
                "",
                f"- Returncode: {payload.get('returncode', '')}",
                f"- Process PID: {payload.get('process_pid', '')}",
                f"- Stdout tail: {payload.get('stdout_tail', '')}",
                f"- Stderr tail: {payload.get('stderr_tail', '')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or launch one step from the MT5 manual Strategy Tester queue.")
    parser.add_argument("--queue", default=DEFAULT_QUEUE)
    parser.add_argument(
        "--refresh-queue",
        dest="refresh_queue",
        action="store_true",
        default=True,
        help="Refresh source runner readiness and rewrite the queue before selecting the next launch step.",
    )
    parser.add_argument(
        "--no-refresh-queue",
        dest="refresh_queue",
        action="store_false",
        help="Use the queue JSON as-is without refreshing source readiness.",
    )
    parser.add_argument(
        "--promotion-gate",
        default="",
        help="Promotion Gate JSON used when refreshing the manual queue. Defaults to latest_promotion_gate for the default queue.",
    )
    parser.add_argument("--step-order", type=int, default=None)
    parser.add_argument("--queue-id", default="")
    parser.add_argument("--step-label", default="")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--detached",
        action="store_true",
        help=(
            "For direct /config launches, start MT5 and return immediately instead of "
            "waiting for terminal64.exe to exit."
        ),
    )
    parser.add_argument("--allow-running-terminal", action="store_true")
    parser.add_argument("--no-detect-running-terminal", action="store_true")
    parser.add_argument(
        "--no-mark-manual-run-start",
        action="store_true",
        help=(
            "Do not update the queue collect filter timestamp before --execute. "
            "By default, the first executable launch marks the manual run start once."
        ),
    )
    parser.add_argument("--timeout-seconds", type=int, default=0)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--print-full-report", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_launch_plan(
        queue_path=args.queue,
        order=args.step_order,
        queue_id=args.queue_id,
        step_label=args.step_label,
        execute=args.execute,
        allow_running_terminal=args.allow_running_terminal,
        detect_running_terminal=not args.no_detect_running_terminal,
        mark_manual_run_start=not args.no_mark_manual_run_start,
        detached=args.detached,
        refresh_queue=args.refresh_queue,
        promotion_gate=args.promotion_gate,
        timeout_seconds=args.timeout_seconds,
    )
    write_json(args.output_json, payload)
    write_text(args.output_md, format_markdown(payload))
    summary = {
        "ok": payload.get("ok"),
        "status": payload.get("status"),
        "next_action": payload.get("next_action"),
        "selected": payload.get("selected"),
        "queue_entry_count": payload.get("queue_entry_count"),
        "queue_total_entry_count": payload.get("queue_total_entry_count"),
        "queue_step_count": payload.get("queue_step_count"),
        "queue_ready_to_collect_count": payload.get("queue_ready_to_collect_count"),
        "queue_waiting_count": payload.get("queue_waiting_count"),
        "queue_step_report_ready_count": payload.get("queue_step_report_ready_count"),
        "queue_step_waiting_report_count": payload.get("queue_step_waiting_report_count"),
        "queue_step_launch_needed_count": payload.get("queue_step_launch_needed_count"),
        "queue_refresh_status": payload.get("queue_refresh_status"),
        "queue_refresh_ok": payload.get("queue_refresh_ok"),
        "queue_refresh_source_count": payload.get("queue_refresh_source_count"),
        "selected_matches_queue_handoff": payload.get("selected_matches_queue_handoff"),
        "selected_step_fingerprint": payload.get("selected_step_fingerprint"),
        "selected_expected_report_artifact": payload.get("selected_expected_report_artifact"),
        "selected_expected_report": payload.get("selected_expected_report"),
        "queue_operator_handoff_state": payload.get("queue_operator_handoff_state"),
        "queue_operator_handoff_next_mt5_step": payload.get("queue_operator_handoff_next_mt5_step"),
        "launch_command_kind": payload.get("launch_command_kind"),
        "detached": payload.get("detached"),
        "manual_run_start_mark_status": payload.get("manual_run_start_mark_status"),
        "manual_run_start_after": payload.get("manual_run_start_after"),
        "blocked": payload.get("blocked"),
        "blocked_reasons": payload.get("blocked_reasons"),
        "returncode": payload.get("returncode"),
        "process_pid": payload.get("process_pid"),
        "output_json": args.output_json,
        "output_md": args.output_md,
    }
    print(json.dumps(payload if args.print_full_report else summary, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
