from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT


DEFAULT_QUEUE_JSON = "runtime/latest_mt5_manual_test_queue_with_optimization.json"
DEFAULT_QUEUE_LAUNCH_JSON = "runtime/latest_mt5_manual_queue_launch_with_optimization.json"
DEFAULT_BRIDGE_RECOVERY_PLAN_JSON = "runtime/latest_bridge_recovery_plan.json"
DEFAULT_STRATEGY_ANALYSIS_JSON = "runtime/latest_mt5_strategy_tester_analysis.json"
DEFAULT_OUTPUT_JSON = "runtime/latest_mt5_manual_operator_packet_with_optimization.json"
DEFAULT_OUTPUT_MD = "runtime/latest_mt5_manual_operator_packet_with_optimization.md"


def read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def markdown_cell(value: object) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", "<br>")


def queue_step_id(item: dict[str, Any]) -> str:
    return f"{item.get('queue_id', '')}/{item.get('step_label', '')}".strip("/")


def checklist_by_order(queue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = queue.get("execution_checklist")
    checklist = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    return {str(row.get("order") or ""): row for row in checklist}


def operation_cards(queue: dict[str, Any]) -> list[dict[str, Any]]:
    cards = queue.get("operation_cards")
    return [row for row in cards if isinstance(row, dict)] if isinstance(cards, list) else []


def operation_step(card: dict[str, Any], checklist: dict[str, dict[str, Any]]) -> dict[str, Any]:
    launch = checklist.get(str(card.get("order") or ""), {})
    return {
        "order": card.get("order", ""),
        "is_next": card.get("is_next", False),
        "action": card.get("action", ""),
        "queue_step": queue_step_id(card),
        "purpose": card.get("purpose", ""),
        "expert": card.get("expert", ""),
        "symbol": card.get("symbol", ""),
        "period": card.get("period", ""),
        "model": card.get("model", ""),
        "dates": card.get("dates", ""),
        "window_summary": card.get("window_summary", ""),
        "training_range": card.get("training_range", ""),
        "forward_range": card.get("forward_range", ""),
        "tester_window": card.get("tester_window", {}),
        "forward": card.get("forward", ""),
        "forward_mode": card.get("forward_mode", ""),
        "optimization": card.get("optimization_label") or card.get("optimization", ""),
        "optimization_enabled": card.get("optimization_enabled", ""),
        "run_type": card.get("run_type", ""),
        "expected_report_artifact": card.get("expected_report_artifact", ""),
        "report_expectation_note": card.get("report_expectation_note", ""),
        "inputs": card.get("inputs", ""),
        "report": card.get("report", ""),
        "collect_after": card.get("collect_after", ""),
        "collect_command_text": card.get("collect_command_text", ""),
        "collect_status": card.get("collect_status", ""),
        "step_report_status": card.get("step_report_status", ""),
        "step_blocking_reason": card.get("step_blocking_reason", ""),
        "launch_needed": card.get("launch_needed", ""),
        "launch_command_kind": card.get("launch_command_kind") or launch.get("launch_command_kind", ""),
        "launch_command_text": launch.get("launch_command_text", ""),
        "start_after": card.get("start_after", "") or launch.get("manual_run_start_after", ""),
        "fingerprint": card.get("step_fingerprint", ""),
        "expected_artifacts": card.get("expected_artifacts", {}),
    }


def next_launch_step(queue: dict[str, Any]) -> dict[str, Any]:
    handoff = queue.get("operator_handoff") if isinstance(queue.get("operator_handoff"), dict) else {}
    next_step = handoff.get("next_mt5_step") if isinstance(handoff.get("next_mt5_step"), dict) else {}
    return next_step


def queue_step_from_item(item: dict[str, Any]) -> str:
    return queue_step_id(
        {
            "queue_id": item.get("queue_id", ""),
            "step_label": item.get("step_label", ""),
        }
    )


def first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return ""


def collect_command_with_modified_after(command: str, modified_after: str) -> str:
    if not command or not modified_after or "--collect-only" not in command:
        return command
    try:
        parts = shlex.split(command)
    except ValueError:
        return command
    if not parts:
        return command
    if "--csv-modified-after" in parts:
        index = parts.index("--csv-modified-after")
        if index + 1 < len(parts):
            parts[index + 1] = modified_after
        else:
            parts.append(modified_after)
    else:
        parts.extend(["--csv-modified-after", modified_after])
    return shlex.join(parts)


def int_or_zero(value: Any) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def list_text(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def normalized_lookup_key(value: object) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def dict_lookup(value: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in value and value.get(key) not in (None, ""):
            return value.get(key)
    normalized = {normalized_lookup_key(key): item for key, item in value.items()}
    for key in keys:
        normalized_key = normalized_lookup_key(key)
        if normalized_key in normalized and normalized[normalized_key] not in (None, ""):
            return normalized[normalized_key]
    return ""


def split_dates(value: object) -> tuple[str, str]:
    text = str(value or "")
    if "->" not in text:
        return "", ""
    left, right = text.split("->", 1)
    return left.strip(), right.strip()


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


RUN_SHEET_INPUT_FIELDS = (
    ("expert", "Expert"),
    ("symbol", "Symbol"),
    ("period", "Period"),
    ("model", "Model"),
    ("from_date", "From"),
    ("to_date", "To"),
    ("forward", "Forward"),
    ("window_summary", "Window"),
    ("optimization", "Optimization"),
    ("inputs", "Inputs"),
    ("report", "Report"),
)


BACK_FORWARD_STEPS = {"back_forward/backtest", "back_forward/forward"}


def run_sheet_step(
    step: dict[str, Any],
    *,
    quick_input: dict[str, Any] | None = None,
    fallback_quick_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    quick = quick_input if isinstance(quick_input, dict) else {}
    fallback_quick = (
        fallback_quick_input if isinstance(fallback_quick_input, dict) else {}
    )
    dates = first_present(
        dict_lookup(step, "dates", "Dates"),
        dict_lookup(quick, "dates", "Dates"),
    )
    from_date = first_present(
        dict_lookup(step, "from_date", "From", "From date"),
        dict_lookup(quick, "from_date", "From", "From date"),
    )
    to_date = first_present(
        dict_lookup(step, "to_date", "To", "To date"),
        dict_lookup(quick, "to_date", "To", "To date"),
    )
    if (not from_date or not to_date) and dates:
        parsed_from, parsed_to = split_dates(dates)
        from_date = from_date or parsed_from
        to_date = to_date or parsed_to
    expected_artifacts = (
        step.get("expected_artifacts")
        if isinstance(step.get("expected_artifacts"), dict)
        else {}
    )
    return {
        "order": first_present(dict_lookup(step, "order", "Order"), ""),
        "is_next": bool(step.get("is_next")),
        "queue_step": first_present(
            dict_lookup(step, "queue_step", "Queue step"),
            dict_lookup(quick, "queue_step", "Queue step"),
        ),
        "purpose": first_present(
            dict_lookup(step, "purpose", "Purpose"),
            dict_lookup(quick, "purpose", "Purpose"),
        ),
        "expert": first_present(
            dict_lookup(step, "expert", "Expert"),
            dict_lookup(quick, "expert", "Expert"),
            dict_lookup(fallback_quick, "expert", "Expert"),
            "Swing_Evaluation_Trader.ex5",
        ),
        "symbol": first_present(
            dict_lookup(step, "symbol", "Symbol"),
            dict_lookup(quick, "symbol", "Symbol"),
            dict_lookup(fallback_quick, "symbol", "Symbol"),
        ),
        "period": first_present(
            dict_lookup(step, "period", "Period"),
            dict_lookup(quick, "period", "Period"),
            dict_lookup(fallback_quick, "period", "Period"),
        ),
        "model": first_present(
            dict_lookup(step, "model", "Model"),
            dict_lookup(quick, "model", "Model"),
            dict_lookup(fallback_quick, "model", "Model"),
        ),
        "from_date": from_date,
        "to_date": to_date,
        "dates": dates,
        "window_summary": first_present(
            dict_lookup(step, "window_summary", "Window"),
            dict_lookup(quick, "window_summary", "Window"),
        ),
        "training_range": first_present(
            dict_lookup(step, "training_range", "Training range"),
            dict_lookup(quick, "training_range", "Training range"),
        ),
        "forward_range": first_present(
            dict_lookup(step, "forward_range", "Forward range"),
            dict_lookup(quick, "forward_range", "Forward range"),
        ),
        "tester_window": (
            step.get("tester_window")
            if isinstance(step.get("tester_window"), dict)
            else quick.get("tester_window")
            if isinstance(quick.get("tester_window"), dict)
            else {}
        ),
        "forward": first_present(
            dict_lookup(step, "forward", "Forward"),
            dict_lookup(quick, "forward", "Forward"),
        ),
        "forward_mode": first_present(
            dict_lookup(step, "forward_mode", "Forward mode"),
            dict_lookup(quick, "forward_mode", "Forward mode"),
        ),
        "optimization": first_present(
            dict_lookup(step, "optimization", "Optimization", "optimization_label"),
            dict_lookup(quick, "optimization", "Optimization", "optimization_label"),
        ),
        "optimization_enabled": first_present(
            dict_lookup(step, "optimization_enabled", "Optimization enabled"),
            dict_lookup(quick, "optimization_enabled", "Optimization enabled"),
        ),
        "inputs": first_present(
            dict_lookup(step, "inputs", "Inputs"),
            dict_lookup(quick, "inputs", "Inputs"),
        ),
        "report": first_present(
            dict_lookup(step, "report", "Report"),
            dict_lookup(quick, "report", "Report"),
        ),
        "run_type": first_present(
            dict_lookup(step, "run_type", "Run type"),
            dict_lookup(quick, "run_type", "Run type"),
        ),
        "expected_report_artifact": first_present(
            dict_lookup(step, "expected_report_artifact", "Expected report artifact"),
            dict_lookup(quick, "expected_report_artifact", "Expected report artifact"),
        ),
        "report_expectation_note": dict_lookup(
            step, "report_expectation_note", "Report expectation note"
        ),
        "start_after": first_present(
            dict_lookup(step, "start_after", "Start after"),
            dict_lookup(step, "manual_run_start_after", "Manual run start after"),
            dict_lookup(quick, "manual_run_start_after", "Manual run start after"),
        ),
        "collect_after": first_present(
            dict_lookup(step, "collect_after", "Collect after"),
            expected_artifacts.get("agent_csv_modified_after", ""),
        ),
        "collect_status": dict_lookup(step, "collect_status", "Collect status"),
        "step_report_status": dict_lookup(step, "step_report_status", "Step report status"),
        "step_blocking_reason": dict_lookup(step, "step_blocking_reason", "Step blocking reason"),
        "launch_command_kind": first_present(
            dict_lookup(step, "launch_command_kind", "Launch kind"),
            dict_lookup(quick, "launch_kind", "Launch kind"),
        ),
        "launch_command_text": dict_lookup(step, "launch_command_text", "Launch command"),
        "collect_command_text": dict_lookup(step, "collect_command_text", "Collect command"),
        "expected_agent_csv": expected_artifacts.get("agent_csv", ""),
        "expected_run_json": expected_artifacts.get("run_json", ""),
        "expected_report_json": expected_artifacts.get("report_json", ""),
        "fingerprint": first_present(
            dict_lookup(step, "fingerprint", "Fingerprint"),
            dict_lookup(step, "step_fingerprint", "Step fingerprint"),
            dict_lookup(quick, "step_fingerprint", "Step fingerprint"),
        ),
    }


def run_sheet_input_rows(step: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"field": label, "value": str(step.get(key, ""))}
        for key, label in RUN_SHEET_INPUT_FIELDS
    ]


def run_sheet_quick_input(step: dict[str, Any]) -> dict[str, Any]:
    return {
        "queue_step": step.get("queue_step", ""),
        "purpose": step.get("purpose", ""),
        "expert": step.get("expert", ""),
        "symbol": step.get("symbol", ""),
        "period": step.get("period", ""),
        "model": step.get("model", ""),
        "from_date": step.get("from_date", ""),
        "to_date": step.get("to_date", ""),
        "dates": step.get("dates", ""),
        "window_summary": step.get("window_summary", ""),
        "training_range": step.get("training_range", ""),
        "forward_range": step.get("forward_range", ""),
        "tester_window": step.get("tester_window", {}),
        "forward": step.get("forward", ""),
        "forward_mode": step.get("forward_mode", ""),
        "optimization": step.get("optimization", ""),
        "optimization_enabled": step.get("optimization_enabled", ""),
        "inputs": step.get("inputs", ""),
        "report": step.get("report", ""),
        "run_type": step.get("run_type", ""),
        "expected_report_artifact": step.get("expected_report_artifact", ""),
        "manual_run_start_after": step.get("start_after", ""),
        "launch_kind": step.get("launch_command_kind", ""),
    }


def build_run_sheet(
    *,
    queue: dict[str, Any],
    queue_path: str,
    steps: list[dict[str, Any]],
    next_step: dict[str, Any],
    quick_input: dict[str, Any],
    launch_status: dict[str, Any],
    next_operator_action: dict[str, Any],
    collect: dict[str, Any],
) -> dict[str, Any]:
    sheet_next_step = run_sheet_step(next_step, quick_input=quick_input)
    sheet_next_step["quick_input"] = run_sheet_quick_input(sheet_next_step)
    sheet_next_step["input_rows"] = run_sheet_input_rows(sheet_next_step)
    sheet_steps = [
        {
            **run_sheet_step(step, fallback_quick_input=quick_input),
        }
        for step in steps
        if str(step.get("queue_step") or "")
    ]
    for step in sheet_steps:
        step["quick_input"] = run_sheet_quick_input(step)
        step["input_rows"] = run_sheet_input_rows(step)
    back_forward_steps = [
        step for step in sheet_steps if str(step.get("queue_step") or "") in BACK_FORWARD_STEPS
    ]
    launch_state = first_present(
        next_operator_action.get("launch_state"),
        launch_status.get("auto_launch_state", ""),
    )
    launch_blocked_reasons = (
        [str(item) for item in launch_status.get("blocked_reasons", []) if str(item)]
        if isinstance(launch_status.get("blocked_reasons"), list)
        else []
    )
    auto_launch_blocked = bool(
        launch_status.get("blocked") is True
        or launch_state in {"manual_input_required", "auto_launch_blocked"}
        or "running_terminal_blocks_direct_config" in launch_blocked_reasons
    )
    if "running_terminal_blocks_direct_config" in launch_blocked_reasons:
        auto_launch_note = (
            "MT5 is already open; use the manual Strategy Tester input above. "
            "Use the /config command only after closing MT5."
        )
    elif auto_launch_blocked:
        auto_launch_note = "Resolve the launch blocker before using the /config command."
    else:
        auto_launch_note = ""
    return {
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "source_queue": queue_path,
        "queue_generated_at": queue.get("generated_at", ""),
        "status": queue.get("status", ""),
        "next_action": queue.get("next_action", ""),
        "operator_action": next_operator_action.get("action", ""),
        "operator_mode": next_operator_action.get("mode", ""),
        "launch_state": launch_state,
        "next_step": sheet_next_step,
        "next_step_input_rows": run_sheet_input_rows(sheet_next_step),
        "back_forward_steps": back_forward_steps,
        "pending_steps": sheet_steps,
        "commands": {
            "before_mt5_run": collect.get("manual_run_start_mark_command_text", ""),
            "auto_launch": launch_status.get("command_text", ""),
            "auto_launch_blocked": auto_launch_blocked,
            "auto_launch_blocked_reasons": launch_blocked_reasons,
            "auto_launch_note": auto_launch_note,
            "collect_dry_run": collect.get("dry_run_command_text", ""),
            "collect_execute": collect.get("execute_command_text", ""),
            "collect_execute_and_refresh_analysis": collect.get(
                "execute_and_refresh_analysis_command_text", ""
            ),
            "collect_execute_and_refresh_all": collect.get(
                "execute_and_refresh_all_command_text", ""
            ),
        },
    }


def back_forward_step_waiting(step: dict[str, Any]) -> bool:
    status = str(
        step.get("step_report_status")
        or step.get("collect_status")
        or ""
    )
    return bool(status) and status not in {
        "ready",
        "ready_to_collect",
        "collected",
        "collect_executed",
    }


def build_back_forward_quick_start(
    *,
    mt5_run_sheet: dict[str, Any],
    strategy_analysis: dict[str, Any],
    after_mt5: dict[str, Any],
) -> dict[str, Any]:
    steps = (
        mt5_run_sheet.get("back_forward_steps")
        if isinstance(mt5_run_sheet.get("back_forward_steps"), list)
        else []
    )
    back_forward_steps = [step for step in steps if isinstance(step, dict)]
    waiting_steps = [
        step for step in back_forward_steps if back_forward_step_waiting(step)
    ]
    current_step = waiting_steps[0] if waiting_steps else (
        back_forward_steps[0] if back_forward_steps else {}
    )
    quick_inputs = [
        step.get("quick_input") if isinstance(step.get("quick_input"), dict) else run_sheet_quick_input(step)
        for step in back_forward_steps
    ]
    quick_input_by_queue_step = {
        str(quick.get("queue_step") or ""): quick
        for quick in quick_inputs
        if isinstance(quick, dict) and str(quick.get("queue_step") or "")
    }
    collect_command = str(
        strategy_analysis.get("back_forward_decision_collect_command_text")
        or strategy_analysis.get("operator_decision_command_text")
        or ""
    )
    thresholds = first_dict(strategy_analysis.get("back_forward_decision_thresholds"))
    sheet_next_step = (
        mt5_run_sheet.get("next_step")
        if isinstance(mt5_run_sheet.get("next_step"), dict)
        else {}
    )
    completion_steps = [
        {
            "order": step.get("order", ""),
            "queue_step": step.get("queue_step", ""),
            "purpose": step.get("purpose", ""),
            "window_summary": step.get("window_summary", ""),
            "report": step.get("report", ""),
            "expected_report_artifact": step.get("expected_report_artifact", ""),
            "expected_agent_csv": step.get("expected_agent_csv", ""),
            "expected_run_json": step.get("expected_run_json", ""),
            "expected_report_json": step.get("expected_report_json", ""),
            "collect_after": step.get("collect_after") or step.get("start_after", ""),
            "status": step.get("step_report_status") or step.get("collect_status", ""),
        }
        for step in back_forward_steps
    ]
    manual_run_start_after = next(
        (
            str(step.get("start_after") or step.get("collect_after") or "")
            for step in back_forward_steps
            if str(step.get("start_after") or step.get("collect_after") or "")
        ),
        str(sheet_next_step.get("start_after") or sheet_next_step.get("collect_after") or ""),
    )
    completion_summary_parts = [
        f"run {len(back_forward_steps)} Back/Forward Strategy Tester steps",
    ]
    if manual_run_start_after:
        completion_summary_parts.append(
            f"reports and Agent CSV must be newer than {manual_run_start_after}"
        )
    if collect_command:
        completion_summary_parts.append("run the Back/Forward collect command")
    if thresholds:
        threshold_bits = [
            f"{key}={thresholds.get(key)}"
            for key in (
                "min_closed",
                "break_even_pf",
                "break_even_avg_r",
                "degraded_pf_delta",
                "degraded_avg_r_delta",
            )
            if thresholds.get(key) not in (None, "")
        ]
        if threshold_bits:
            completion_summary_parts.append("decision thresholds: " + ", ".join(threshold_bits))
    return {
        "available": bool(back_forward_steps),
        "purpose": "Run Backtest and Forward Test first before optimization or diagnostic rows.",
        "status": (
            "waiting_for_back_forward_reports"
            if waiting_steps
            else "back_forward_reports_ready_or_collected"
            if back_forward_steps
            else "not_available"
        ),
        "step_count": len(back_forward_steps),
        "waiting_step_count": len(waiting_steps),
        "current_step": current_step,
        "current_quick_input": (
            current_step.get("quick_input")
            if isinstance(current_step.get("quick_input"), dict)
            else run_sheet_quick_input(current_step)
            if current_step
            else {}
        ),
        "steps": back_forward_steps,
        "quick_inputs": quick_inputs,
        "quick_input_by_queue_step": quick_input_by_queue_step,
        "backtest_quick_input": quick_input_by_queue_step.get("back_forward/backtest", {}),
        "forward_quick_input": quick_input_by_queue_step.get("back_forward/forward", {}),
        "collect_command_text": collect_command,
        "full_queue_collect_command_text": str(
            after_mt5.get("execute_and_refresh_all_command_text")
            or after_mt5.get("execute_and_refresh_analysis_command_text")
            or after_mt5.get("execute_command_text")
            or ""
        ),
        "dry_run_collect_command_text": str(after_mt5.get("dry_run_command_text") or ""),
        "auto_launch_blocked": bool(
            first_dict(mt5_run_sheet.get("commands")).get("auto_launch_blocked")
        ),
        "auto_launch_note": str(
            first_dict(mt5_run_sheet.get("commands")).get("auto_launch_note") or ""
        ),
        "auto_launch_blocked_reasons": list_text(
            first_dict(mt5_run_sheet.get("commands")).get("auto_launch_blocked_reasons")
        ),
        "completion_criteria": {
            "summary": "; ".join(completion_summary_parts),
            "all_steps_required": True,
            "expected_step_count": len(back_forward_steps),
            "waiting_step_count": len(waiting_steps),
            "manual_run_start_after": manual_run_start_after,
            "collect_command_text": collect_command,
            "decision_thresholds": thresholds,
            "steps": completion_steps,
        },
    }


def summarize_launch_plan(
    launch_plan: dict[str, Any] | None,
    *,
    queue_launch_path: str = "",
) -> dict[str, Any]:
    if not launch_plan:
        return {
            "available": False,
            "queue_launch_json": queue_launch_path,
            "generated_at": "",
            "ok": "",
            "status": "not_available",
            "next_action": "",
            "auto_launch_state": "unknown",
            "selected": "",
            "selected_queue_step": "",
            "selected_matches_queue_handoff": "",
            "launch_command_kind": "",
            "blocked": "",
            "blocked_reasons": [],
            "running_terminal_count": "",
            "command_text": "",
        }
    selected = (
        launch_plan.get("selected_item")
        if isinstance(launch_plan.get("selected_item"), dict)
        else {}
    )
    blocked_reasons = (
        [str(item) for item in launch_plan.get("blocked_reasons", [])]
        if isinstance(launch_plan.get("blocked_reasons"), list)
        else []
    )
    status = str(launch_plan.get("status", ""))
    if "running_terminal_blocks_direct_config" in blocked_reasons:
        auto_launch_state = "manual_input_required"
    elif launch_plan.get("blocked") is True:
        auto_launch_state = "auto_launch_blocked"
    elif status == "planned":
        auto_launch_state = "auto_launch_available"
    elif status == "executed":
        auto_launch_state = "launched_wait_for_report"
    else:
        auto_launch_state = status or "unknown"
    return {
        "available": True,
        "queue_launch_json": queue_launch_path,
        "generated_at": launch_plan.get("generated_at", ""),
        "ok": launch_plan.get("ok", ""),
        "status": status,
        "next_action": launch_plan.get("next_action", ""),
        "auto_launch_state": auto_launch_state,
        "selected": launch_plan.get("selected", ""),
        "selected_queue_step": queue_step_from_item(selected),
        "selected_matches_queue_handoff": launch_plan.get("selected_matches_queue_handoff", ""),
        "launch_command_kind": launch_plan.get("launch_command_kind", ""),
        "blocked": launch_plan.get("blocked", ""),
        "blocked_reasons": blocked_reasons,
        "running_terminal_count": launch_plan.get("running_terminal_count", ""),
        "command_text": launch_plan.get("command_text", ""),
    }


def summarize_bridge_recovery(
    bridge_recovery: dict[str, Any] | None,
    *,
    bridge_recovery_path: str = "",
) -> dict[str, Any]:
    if not bridge_recovery:
        return {
            "available": False,
            "bridge_recovery_json": bridge_recovery_path,
            "generated_at": "",
            "ok": "",
            "status": "not_available",
            "ready_for_mt5_validation": "",
            "next_action": "",
            "blocking_reasons": [],
            "standalone_strategy_tester_allowed": "",
            "strategy_tester_note": "",
            "operator_step": "",
            "verification": "",
            "verification_commands": [],
            "verification_command_count": 0,
            "verification_command_labels": [],
            "mt5_terminal_running": "",
            "mt5_terminal_match_count": "",
            "bridge_log_activity_status": "",
            "snapshot_fresh": "",
            "snapshot_age_seconds": "",
            "last_ea_post_timestamp": "",
            "last_ea_post_age_seconds": "",
            "last_ea_post_path": "",
            "history_request_pending": "",
            "history_request_stale_pending": "",
            "history_request_id": "",
            "history_done_id": "",
            "history_done_matches_request": "",
            "history_data_fresh": "",
            "history_data_stale": "",
            "history_status_server_time": "",
            "history_status_server_time_age_seconds": "",
            "history_status_m1_last_time": "",
            "history_status_m1_last_time_age_seconds": "",
        }
    operator_summary = first_dict(bridge_recovery.get("operator_summary"))
    checks = first_dict(bridge_recovery.get("checks"))
    operation_cards = bridge_recovery.get("operation_cards")
    cards = [item for item in operation_cards if isinstance(item, dict)] if isinstance(operation_cards, list) else []
    next_card = next((item for item in cards if item.get("is_next") is True), cards[0] if cards else {})
    last_ea_post = first_dict(
        operator_summary.get("last_ea_post"),
        checks.get("last_ea_post"),
        next_card.get("last_ea_post"),
    )
    blocking_reasons = (
        operator_summary.get("blocking_reasons")
        if isinstance(operator_summary.get("blocking_reasons"), list)
        else bridge_recovery.get("blocking_reasons")
        if isinstance(bridge_recovery.get("blocking_reasons"), list)
        else []
    )
    verification_commands = command_rows(
        operator_summary.get("next_operation_verification_commands")
    ) or command_rows(next_card.get("verification_commands"))
    return {
        "available": True,
        "bridge_recovery_json": bridge_recovery_path,
        "generated_at": bridge_recovery.get("generated_at", ""),
        "ok": first_present(operator_summary.get("ok"), bridge_recovery.get("ok")),
        "status": first_present(operator_summary.get("status"), bridge_recovery.get("status")),
        "ready_for_mt5_validation": first_present(
            operator_summary.get("ready_for_mt5_validation"),
            bridge_recovery.get("ready_for_mt5_validation"),
        ),
        "next_action": first_present(
            operator_summary.get("next_action"),
            bridge_recovery.get("next_action"),
        ),
        "blocking_reasons": [str(item) for item in blocking_reasons],
        "standalone_strategy_tester_allowed": True,
        "strategy_tester_note": (
            "Standalone Swing_Evaluation_Trader Strategy Tester can run while Bridge "
            "snapshot/history recovery is pending."
        ),
        "operator_step": first_present(
            operator_summary.get("next_operation_operator_step"),
            next_card.get("operator_step"),
        ),
        "verification": first_present(
            operator_summary.get("next_operation_verification"),
            next_card.get("verification"),
        ),
        "verification_commands": verification_commands,
        "verification_command_count": len(verification_commands),
        "verification_command_labels": [row["label"] for row in verification_commands],
        "mt5_terminal_running": first_present(
            operator_summary.get("mt5_terminal_running"),
            checks.get("mt5_terminal_running"),
            next_card.get("mt5_terminal_running"),
        ),
        "mt5_terminal_match_count": first_present(
            operator_summary.get("mt5_terminal_match_count"),
            checks.get("mt5_terminal_match_count"),
            next_card.get("mt5_terminal_match_count"),
        ),
        "bridge_log_activity_status": first_present(
            operator_summary.get("bridge_log_activity_status"),
            checks.get("bridge_log_activity_status"),
        ),
        "snapshot_fresh": first_present(
            operator_summary.get("snapshot_fresh"),
            checks.get("snapshot_fresh"),
        ),
        "snapshot_age_seconds": first_present(
            operator_summary.get("snapshot_age_seconds"),
            checks.get("snapshot_age_seconds"),
        ),
        "last_ea_post_timestamp": last_ea_post.get("timestamp", ""),
        "last_ea_post_age_seconds": first_present(
            operator_summary.get("last_ea_post_age_seconds"),
            last_ea_post.get("age_seconds"),
        ),
        "last_ea_post_path": last_ea_post.get("path", ""),
        "history_request_pending": first_present(
            operator_summary.get("history_request_pending"),
            checks.get("history_request_pending"),
            next_card.get("history_request_pending"),
        ),
        "history_request_stale_pending": first_present(
            operator_summary.get("history_request_stale_pending"),
            checks.get("history_request_stale_pending"),
            next_card.get("history_request_stale_pending"),
        ),
        "history_request_id": first_present(
            operator_summary.get("history_request_id"),
            checks.get("history_request_id"),
            next_card.get("history_request_id"),
        ),
        "history_done_id": first_present(
            operator_summary.get("history_done_id"),
            checks.get("history_done_id"),
            next_card.get("history_done_id"),
        ),
        "history_done_matches_request": first_present(
            operator_summary.get("history_done_matches_request"),
            checks.get("history_done_matches_request"),
            next_card.get("history_done_matches_request"),
        ),
        "history_data_fresh": first_present(
            operator_summary.get("history_data_fresh"),
            checks.get("history_data_fresh"),
            next_card.get("history_data_fresh"),
        ),
        "history_data_stale": first_present(
            operator_summary.get("history_data_stale"),
            checks.get("history_data_stale"),
            next_card.get("history_data_stale"),
        ),
        "history_status_server_time": first_present(
            operator_summary.get("history_status_server_time"),
            checks.get("history_status_server_time"),
            next_card.get("history_status_server_time"),
        ),
        "history_status_server_time_age_seconds": first_present(
            operator_summary.get("history_status_server_time_age_seconds"),
            checks.get("history_status_server_time_age_seconds"),
            next_card.get("history_status_server_time_age_seconds"),
        ),
        "history_status_m1_last_time": first_present(
            operator_summary.get("history_status_m1_last_time"),
            checks.get("history_status_m1_last_time"),
            next_card.get("history_status_m1_last_time"),
        ),
        "history_status_m1_last_time_age_seconds": first_present(
            operator_summary.get("history_status_m1_last_time_age_seconds"),
            checks.get("history_status_m1_last_time_age_seconds"),
            next_card.get("history_status_m1_last_time_age_seconds"),
        ),
    }


def as_text_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def summarize_next_operator_action(
    *,
    next_step: dict[str, Any],
    launch_status: dict[str, Any],
    after_mt5: dict[str, Any],
    ready_to_collect_count: Any,
    waiting_count: Any,
    blocking_reasons: Any,
) -> dict[str, Any]:
    queue_step = str(next_step.get("queue_step") or "")
    purpose = str(next_step.get("purpose") or "")
    quick_input = (
        next_step.get("quick_input") if isinstance(next_step.get("quick_input"), dict) else {}
    )
    launch_state = str(launch_status.get("auto_launch_state") or "")
    launch_blockers = list_text(launch_status.get("blocked_reasons"))
    blockers = list_text(blocking_reasons) + launch_blockers
    ready_count = int_or_zero(ready_to_collect_count)
    wait_count = int_or_zero(waiting_count)
    collect_command = str(
        after_mt5.get("execute_and_refresh_all_command_text")
        or after_mt5.get("execute_and_refresh_analysis_command_text")
        or after_mt5.get("execute_command_text")
        or ""
    )
    dry_run_command = str(after_mt5.get("dry_run_command_text") or "")
    auto_launch_command = str(
        launch_status.get("command_text") or next_step.get("launch_command_text") or ""
    )

    base = {
        "queue_step": queue_step,
        "purpose": purpose,
        "quick_input": quick_input,
        "launch_state": launch_state,
        "ready_to_collect_count": ready_count,
        "waiting_count": wait_count,
        "blocking_reasons": blockers,
        "command_text": "",
        "follow_up_command_text": "",
        "verification": "",
    }
    if ready_count > 0:
        return {
            **base,
            "action": "collect_ready_results",
            "mode": "collect",
            "instruction": (
                "Run the collect command for ready Strategy Tester reports, then refresh "
                "the post-collect analysis."
            ),
            "command_text": collect_command,
            "follow_up_command_text": dry_run_command,
            "verification": "collector status becomes collect_executed and Strategy Tester Analysis refreshes",
        }
    if not queue_step:
        return {
            **base,
            "action": "inspect_manual_queue",
            "mode": "inspect",
            "instruction": "Refresh or inspect the manual Strategy Tester queue; no next MT5 step is selected.",
            "command_text": dry_run_command,
            "verification": "manual queue exposes a next step or ready collect entry",
        }
    if launch_state == "auto_launch_available":
        return {
            **base,
            "action": "auto_launch_selected_step",
            "mode": "auto_launch",
            "instruction": "Run the prepared /config command for the selected Strategy Tester step.",
            "command_text": auto_launch_command,
            "follow_up_command_text": dry_run_command,
            "verification": "selected report and Agent CSV become ready for collect",
        }
    if launch_state == "launched_wait_for_report":
        return {
            **base,
            "action": "wait_for_mt5_report",
            "mode": "wait",
            "instruction": "Wait for MT5 Strategy Tester to finish, then run the collect dry-run.",
            "command_text": dry_run_command,
            "verification": "collect dry-run selects at least one ready entry",
        }
    if launch_state == "manual_input_required" or "running_terminal_blocks_direct_config" in blockers:
        return {
            **base,
            "action": "manual_strategy_tester_input",
            "mode": "manual",
            "instruction": (
                "MT5 is already open; enter the MT5 Input fields in Strategy Tester, "
                "run this step manually, then run the collect dry-run."
            ),
            "command_text": "",
            "follow_up_command_text": dry_run_command,
            "verification": "the expected report and Agent CSV are newer than the collect filter time",
        }
    if launch_status.get("blocked") is True:
        return {
            **base,
            "action": "resolve_launch_blocker",
            "mode": "blocked",
            "instruction": "Resolve the launch blocker before starting the selected MT5 Strategy Tester step.",
            "command_text": "",
            "follow_up_command_text": dry_run_command,
            "verification": "queue launch status becomes planned or manual_input_required",
        }
    if wait_count > 0:
        return {
            **base,
            "action": "manual_strategy_tester_input",
            "mode": "manual",
            "instruction": "Run the selected Strategy Tester step manually, then check collect readiness.",
            "command_text": "",
            "follow_up_command_text": dry_run_command,
            "verification": "collect dry-run selects at least one ready entry",
        }
    return {
        **base,
        "action": "inspect_manual_queue",
        "mode": "inspect",
        "instruction": "Inspect the manual queue state before taking the next MT5 action.",
        "command_text": dry_run_command,
        "verification": "manual queue status explains the next required action",
    }


def summarize_strategy_analysis(
    strategy_analysis: dict[str, Any] | None,
    *,
    strategy_analysis_path: str = "",
) -> dict[str, Any]:
    if not strategy_analysis:
        return {
            "available": False,
            "strategy_analysis_json": strategy_analysis_path,
            "generated_at": "",
            "status": "not_available",
            "adoption_status": "",
            "promotion_decision": "",
            "back_forward_evidence_state": "",
            "back_forward_performance_status": "",
            "back_forward_decision_status": "",
            "back_forward_decision_adoptable": "",
            "back_forward_decision_next_action": "",
            "back_forward_decision_reason": "",
            "back_forward_decision_thresholds": {},
            "back_forward_decision_backtest_trades": "",
            "back_forward_decision_forward_trades": "",
            "back_forward_decision_forward_pf": "",
            "back_forward_decision_forward_avg_r": "",
            "back_forward_decision_forward_pf_delta_vs_backtest": "",
            "back_forward_decision_forward_avg_r_delta_vs_backtest": "",
            "back_forward_decision_collect_command_text": "",
            "back_forward_decision_sample_shortage_recovery": {},
            "back_forward_decision_sample_shortage_recovery_command_text": "",
            "back_forward_decision_sample_shortage_recovery_range_strategy": "",
            "back_forward_decision_sample_shortage_recovery_suggested_from_date": "",
            "back_forward_decision_sample_shortage_recovery_suggested_to_date": "",
            "source_time_refresh_status": "",
            "source_time_issue_labels": [],
            "source_time_candidate_issue_labels": [],
            "source_time_refresh_queue_command_text": "",
            "source_time_collect_refresh_command_text": "",
            "source_time_refresh_analysis_command_text": "",
            "buy_candidate_gap_status": "",
            "buy_candidate_gap_reason": "",
            "buy_candidate_gap_diagnostic_labels": [],
            "buy_candidate_gap_refresh_queue_command_text": "",
            "buy_candidate_gap_collect_refresh_command_text": "",
            "operator_decision_status": "",
            "operator_decision_verdict": "",
            "operator_decision_adoptable": "",
            "operator_decision_primary_blocker": "",
            "operator_decision_primary_reason": "",
            "operator_decision_next_action": "",
            "operator_decision_summary": "",
            "operator_decision_command_text": "",
            "operator_decision_follow_up_command_text": "",
        }
    source_time_plan = first_dict(strategy_analysis.get("source_time_refresh_plan"))
    buy_gap_plan = first_dict(strategy_analysis.get("buy_candidate_gap_plan"))
    operator_decision = first_dict(strategy_analysis.get("operator_decision"))
    adoption = first_dict(strategy_analysis.get("adoption"))
    promotion_gate = first_dict(strategy_analysis.get("promotion_gate"))
    back_forward_run = first_dict(strategy_analysis.get("back_forward_run"))
    back_forward_decision = first_dict(strategy_analysis.get("back_forward_decision"))
    back_forward_decision_thresholds = first_dict(back_forward_decision.get("thresholds"))
    back_forward_recovery = first_dict(back_forward_decision.get("sample_shortage_recovery"))
    return {
        "available": True,
        "strategy_analysis_json": strategy_analysis_path,
        "generated_at": strategy_analysis.get("generated_at", ""),
        "status": first_present(
            strategy_analysis.get("status"),
            strategy_analysis.get("adoption_status"),
            adoption.get("status"),
        ),
        "adoption_status": first_present(
            strategy_analysis.get("adoption_status"),
            adoption.get("status"),
        ),
        "promotion_decision": first_present(
            strategy_analysis.get("promotion_decision"),
            promotion_gate.get("decision"),
        ),
        "back_forward_evidence_state": first_present(
            strategy_analysis.get("back_forward_evidence_state"),
            back_forward_run.get("evidence_state"),
        ),
        "back_forward_performance_status": first_present(
            strategy_analysis.get("back_forward_performance_status"),
            back_forward_run.get("performance_status"),
        ),
        "back_forward_decision_status": first_present(
            strategy_analysis.get("back_forward_decision_status"),
            back_forward_decision.get("status"),
        ),
        "back_forward_decision_adoptable": first_present(
            strategy_analysis.get("back_forward_decision_adoptable"),
            back_forward_decision.get("adoptable"),
        ),
        "back_forward_decision_next_action": first_present(
            strategy_analysis.get("back_forward_decision_next_action"),
            back_forward_decision.get("next_action"),
        ),
        "back_forward_decision_reason": first_present(
            strategy_analysis.get("back_forward_decision_reason"),
            back_forward_decision.get("reason"),
        ),
        "back_forward_decision_thresholds": back_forward_decision_thresholds,
        "back_forward_decision_backtest_trades": first_present(
            strategy_analysis.get("back_forward_decision_backtest_trades"),
            back_forward_decision.get("backtest_trades"),
        ),
        "back_forward_decision_forward_trades": first_present(
            strategy_analysis.get("back_forward_decision_forward_trades"),
            back_forward_decision.get("forward_trades"),
        ),
        "back_forward_decision_forward_pf": first_present(
            strategy_analysis.get("back_forward_decision_forward_pf"),
            back_forward_decision.get("forward_pf"),
        ),
        "back_forward_decision_forward_avg_r": first_present(
            strategy_analysis.get("back_forward_decision_forward_avg_r"),
            back_forward_decision.get("forward_avg_r"),
        ),
        "back_forward_decision_forward_pf_delta_vs_backtest": first_present(
            strategy_analysis.get("back_forward_decision_forward_pf_delta_vs_backtest"),
            back_forward_decision.get("forward_pf_delta_vs_backtest"),
        ),
        "back_forward_decision_forward_avg_r_delta_vs_backtest": first_present(
            strategy_analysis.get("back_forward_decision_forward_avg_r_delta_vs_backtest"),
            back_forward_decision.get("forward_avg_r_delta_vs_backtest"),
        ),
        "back_forward_decision_collect_command_text": first_present(
            strategy_analysis.get("back_forward_decision_collect_command_text"),
            back_forward_decision.get("collect_command_text"),
            back_forward_run.get("recommended_collect_only_command_text"),
        ),
        "back_forward_decision_sample_shortage_recovery": back_forward_recovery,
        "back_forward_decision_sample_shortage_recovery_command_text": first_present(
            strategy_analysis.get("back_forward_decision_sample_shortage_recovery_command_text"),
            back_forward_decision.get("sample_shortage_recovery_command_text"),
            back_forward_recovery.get("command_text"),
        ),
        "back_forward_decision_sample_shortage_recovery_range_strategy": first_present(
            strategy_analysis.get("back_forward_decision_sample_shortage_recovery_range_strategy"),
            back_forward_decision.get("sample_shortage_recovery_range_strategy"),
            back_forward_recovery.get("range_strategy"),
        ),
        "back_forward_decision_sample_shortage_recovery_suggested_from_date": first_present(
            strategy_analysis.get("back_forward_decision_sample_shortage_recovery_suggested_from_date"),
            back_forward_decision.get("sample_shortage_recovery_suggested_from_date"),
            back_forward_recovery.get("suggested_from_date"),
        ),
        "back_forward_decision_sample_shortage_recovery_suggested_to_date": first_present(
            strategy_analysis.get("back_forward_decision_sample_shortage_recovery_suggested_to_date"),
            back_forward_decision.get("sample_shortage_recovery_suggested_to_date"),
            back_forward_recovery.get("suggested_to_date"),
        ),
        "source_time_refresh_status": source_time_plan.get("status", ""),
        "source_time_issue_labels": as_text_list(source_time_plan.get("issue_labels")),
        "source_time_candidate_issue_labels": as_text_list(
            source_time_plan.get("candidate_issue_labels")
        ),
        "source_time_refresh_queue_command_text": source_time_plan.get(
            "refresh_queue_command_text", ""
        ),
        "source_time_collect_refresh_command_text": source_time_plan.get(
            "collect_execute_and_refresh_command_text", ""
        ),
        "source_time_refresh_analysis_command_text": source_time_plan.get(
            "refresh_analysis_command_text", ""
        ),
        "buy_candidate_gap_status": buy_gap_plan.get("status", ""),
        "buy_candidate_gap_reason": buy_gap_plan.get("reason", ""),
        "buy_candidate_gap_diagnostic_labels": as_text_list(
            buy_gap_plan.get("diagnostic_labels")
        ),
        "buy_candidate_gap_refresh_queue_command_text": buy_gap_plan.get(
            "refresh_queue_command_text", ""
        ),
        "buy_candidate_gap_collect_refresh_command_text": buy_gap_plan.get(
            "collect_execute_and_refresh_command_text", ""
        ),
        "operator_decision_status": first_present(
            strategy_analysis.get("operator_decision_status"),
            operator_decision.get("status"),
        ),
        "operator_decision_verdict": first_present(
            strategy_analysis.get("operator_decision_verdict"),
            operator_decision.get("verdict"),
        ),
        "operator_decision_adoptable": first_present(
            strategy_analysis.get("operator_decision_adoptable"),
            operator_decision.get("adoptable"),
        ),
        "operator_decision_primary_blocker": first_present(
            strategy_analysis.get("operator_decision_primary_blocker"),
            operator_decision.get("primary_blocker"),
        ),
        "operator_decision_primary_reason": operator_decision.get("primary_reason", ""),
        "operator_decision_next_action": first_present(
            strategy_analysis.get("operator_decision_next_action"),
            operator_decision.get("next_action"),
        ),
        "operator_decision_summary": operator_decision.get("summary", ""),
        "operator_decision_command_text": first_present(
            strategy_analysis.get("operator_decision_command_text"),
            operator_decision.get("command_text"),
        ),
        "operator_decision_follow_up_command_text": operator_decision.get(
            "follow_up_command_text", ""
        ),
    }


def build_packet(
    queue: dict[str, Any],
    *,
    queue_path: str = DEFAULT_QUEUE_JSON,
    queue_launch: dict[str, Any] | None = None,
    queue_launch_path: str = "",
    bridge_recovery: dict[str, Any] | None = None,
    bridge_recovery_path: str = "",
    strategy_analysis: dict[str, Any] | None = None,
    strategy_analysis_path: str = "",
) -> dict[str, Any]:
    strategy_analysis_status = summarize_strategy_analysis(
        strategy_analysis,
        strategy_analysis_path=strategy_analysis_path,
    )
    if not queue:
        return {
            "ok": False,
            "status": "missing_queue",
            "queue_json": queue_path,
            "generated_at": datetime.now().strftime(TIME_FORMAT),
            "blocking_reasons": ["queue_json_missing_or_invalid"],
            "bridge_recovery": summarize_bridge_recovery(
                bridge_recovery,
                bridge_recovery_path=bridge_recovery_path,
            ),
            "strategy_analysis": strategy_analysis_status,
            "next_operator_before_mt5_command_text": "",
            "next_operator_quick_input": {},
            "next_step_quick_input": {},
            "next_step_operator_summary": "",
            "next_step_summary": "",
            "next_step_collect_filter_summary": "",
        }
    handoff = queue.get("operator_handoff") if isinstance(queue.get("operator_handoff"), dict) else {}
    quick_input = handoff.get("quick_input") if isinstance(handoff.get("quick_input"), dict) else {}
    collect = {
        "dry_run_command_text": handoff.get("dry_run_command_text")
        or handoff.get("collect_check_command_text", ""),
        "manual_run_start_mark_command_text": handoff.get(
            "manual_run_start_mark_command_text", ""
        )
        or queue.get("manual_run_start_mark_command_text", ""),
        "execute_command_text": handoff.get("execute_command_text", ""),
        "execute_and_refresh_analysis_command_text": handoff.get(
            "execute_and_refresh_analysis_command_text", ""
        ),
        "execute_and_refresh_all_command_text": handoff.get(
            "execute_and_refresh_all_command_text", ""
        ),
    }
    checklist = checklist_by_order(queue)
    steps = [operation_step(card, checklist) for card in operation_cards(queue)]
    static_strategy_configs = as_text_list(queue.get("static_strategy_configs"))
    static_candidate_labels = as_text_list(queue.get("static_candidate_labels"))
    next_step = next_launch_step(queue)
    next_order = str(next_step.get("order") or "")
    next_launch = checklist.get(next_order, {})
    next_queue_step = queue_step_id(next_step)
    packet_next_step = {
        "order": next_step.get("order", ""),
        "queue_step": next_queue_step,
        "purpose": quick_input.get("purpose", "") or next_step.get("purpose", ""),
        "summary": handoff.get("next_step_operator_summary", ""),
        "summary_alias": handoff.get("next_step_summary")
        or handoff.get("next_step_operator_summary", ""),
        "collect_filter": handoff.get("next_step_collect_filter_summary", ""),
        "quick_input": quick_input,
        "expert": dict_lookup(quick_input, "expert", "Expert"),
        "symbol": first_present(
            next_step.get("symbol", ""),
            dict_lookup(quick_input, "symbol", "Symbol"),
        ),
        "period": first_present(
            next_step.get("period", ""),
            dict_lookup(quick_input, "period", "Period"),
        ),
        "model": first_present(
            next_step.get("model", ""),
            dict_lookup(quick_input, "model", "Model"),
        ),
        "from_date": dict_lookup(quick_input, "from_date", "From", "From date"),
        "to_date": dict_lookup(quick_input, "to_date", "To", "To date"),
        "launch_command_kind": next_step.get("launch_command_kind")
        or next_launch.get("launch_command_kind", ""),
        "launch_command_text": next_launch.get("launch_command_text", ""),
        "expected_report_artifact": next_step.get("expected_report_artifact", ""),
        "report_expectation_note": next_step.get("report_expectation_note", ""),
        "report": next_step.get("report", ""),
        "inputs": next_step.get("inputs", ""),
        "dates": next_step.get("dates", ""),
        "forward": next_step.get("forward", ""),
        "forward_mode": dict_lookup(quick_input, "forward_mode", "Forward mode"),
        "optimization": next_step.get("optimization_label") or next_step.get("optimization", ""),
        "optimization_enabled": first_present(
            next_step.get("optimization_enabled", ""),
            dict_lookup(quick_input, "optimization_enabled", "Optimization enabled"),
        ),
        "run_type": next_step.get("run_type", ""),
        "start_after": first_present(
            next_step.get("start_after", ""),
            next_step.get("manual_run_start_after", ""),
            dict_lookup(quick_input, "manual_run_start_after", "Manual run start after"),
        ),
        "collect_after": next_step.get("collect_after", ""),
        "fingerprint": next_step.get("step_fingerprint", ""),
    }
    manual_run_start_after = str(
        quick_input.get("manual_run_start_after")
        or next_step.get("manual_run_start_after")
        or next_step.get("collect_modified_after")
        or queue.get("manual_run_start_after_override")
        or ""
    )
    if manual_run_start_after:
        strategy_analysis_status = dict(strategy_analysis_status)
        refreshed_back_forward_collect = collect_command_with_modified_after(
            str(
                strategy_analysis_status.get(
                    "back_forward_decision_collect_command_text", ""
                )
                or ""
            ),
            manual_run_start_after,
        )
        strategy_analysis_status["back_forward_decision_collect_command_text"] = (
            refreshed_back_forward_collect
        )
        if refreshed_back_forward_collect and (
            strategy_analysis_status.get("operator_decision_primary_blocker")
            == "mt5_back_forward_not_executed"
            or strategy_analysis_status.get("operator_decision_next_action")
            == "run_backtest_then_forward_in_mt5_strategy_tester"
            or strategy_analysis_status.get("operator_decision_verdict")
            == "RUN_BACK_FORWARD"
        ):
            strategy_analysis_status["operator_decision_command_text"] = (
                refreshed_back_forward_collect
            )
    launch_status = summarize_launch_plan(queue_launch, queue_launch_path=queue_launch_path)
    bridge_recovery_status = summarize_bridge_recovery(
        bridge_recovery,
        bridge_recovery_path=bridge_recovery_path,
    )
    next_operator_action = summarize_next_operator_action(
        next_step=packet_next_step,
        launch_status=launch_status,
        after_mt5=collect,
        ready_to_collect_count=queue.get("ready_to_collect_count", ""),
        waiting_count=queue.get("waiting_count", ""),
        blocking_reasons=queue.get("blocking_reasons", []),
    )
    mt5_run_sheet = build_run_sheet(
        queue=queue,
        queue_path=queue_path,
        steps=steps,
        next_step=packet_next_step,
        quick_input=quick_input,
        launch_status=launch_status,
        next_operator_action=next_operator_action,
        collect=collect,
    )
    back_forward_quick_start = build_back_forward_quick_start(
        mt5_run_sheet=mt5_run_sheet,
        strategy_analysis=strategy_analysis_status,
        after_mt5=collect,
    )
    run_sheet_commands = first_dict(mt5_run_sheet.get("commands"))
    manual_run_start_effective_after_values = list_text(
        queue.get("manual_run_start_effective_after_values")
    )
    manual_run_start_effective_after = (
        "; ".join(manual_run_start_effective_after_values)
        or manual_run_start_after
        or str(queue.get("manual_run_start_after_override") or "")
    )
    return {
        "ok": True,
        "status": queue.get("status", ""),
        "next_action": queue.get("next_action", ""),
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "queue_json": queue_path,
        "queue_generated_at": queue.get("generated_at", ""),
        "promotion_gate_generated_at": queue.get("promotion_gate_generated_at", ""),
        "promotion_gate_decision": queue.get("promotion_gate_decision", ""),
        "progress_state": handoff.get("progress_state", ""),
        "state": handoff.get("state", ""),
        "manual_run_start_marked": queue.get("manual_run_start_marked", False),
        "manual_run_start_marked_this_run": queue.get(
            "manual_run_start_marked_this_run", False
        ),
        "manual_run_start_preserved": queue.get("manual_run_start_preserved", False),
        "manual_run_start_state_count": queue.get("manual_run_start_state_count", ""),
        "manual_run_start_state_marked_count": queue.get(
            "manual_run_start_state_marked_count", ""
        ),
        "manual_run_start_effective_after": manual_run_start_effective_after,
        "manual_run_start_effective_after_values": manual_run_start_effective_after_values,
        "manual_run_start_after_override": queue.get("manual_run_start_after_override", ""),
        "manual_run_start_mark_command_text": queue.get("manual_run_start_mark_command_text", ""),
        "queue_status": queue.get("status", ""),
        "queue_next_action": queue.get("next_action", ""),
        "entry_count": queue.get("entry_count", ""),
        "step_count": queue.get("step_count", ""),
        "static_strategy_config_count": first_present(
            queue.get("static_strategy_config_count"),
            len(static_strategy_configs),
        ),
        "static_strategy_configs": static_strategy_configs,
        "static_candidate_label_count": first_present(
            queue.get("static_candidate_label_count"),
            len(static_candidate_labels),
        ),
        "static_candidate_labels": static_candidate_labels,
        "waiting_count": queue.get("waiting_count", ""),
        "ready_to_collect_count": queue.get("ready_to_collect_count", ""),
        "next_queue_step": next_queue_step,
        "next_report": packet_next_step.get("report", ""),
        "next_inputs": packet_next_step.get("inputs", ""),
        "next_step": packet_next_step,
        "launch_status": launch_status,
        "bridge_recovery": bridge_recovery_status,
        "strategy_analysis": strategy_analysis_status,
        "next_operator_action": next_operator_action,
        "next_operator_action_name": next_operator_action.get("action", ""),
        "next_operator_mode": next_operator_action.get("mode", ""),
            "next_operator_queue_step": next_operator_action.get("queue_step", ""),
            "next_operator_quick_input": next_operator_action.get("quick_input", {}),
            "next_operator_launch_state": next_operator_action.get("launch_state", ""),
        "next_operator_instruction": next_operator_action.get("instruction", ""),
        "next_operator_command_text": next_operator_action.get("command_text", ""),
        "next_operator_follow_up_command_text": next_operator_action.get(
            "follow_up_command_text", ""
        ),
        "next_operator_verification": next_operator_action.get("verification", ""),
        "auto_launch_command_text": run_sheet_commands.get("auto_launch", ""),
        "auto_launch_command_available": bool(
            run_sheet_commands.get("auto_launch", "")
        ),
        "auto_launch_blocked": run_sheet_commands.get("auto_launch_blocked", ""),
        "auto_launch_blocked_reasons": list_text(
            run_sheet_commands.get("auto_launch_blocked_reasons")
        ),
        "auto_launch_note": run_sheet_commands.get("auto_launch_note", ""),
        "mt5_run_sheet": mt5_run_sheet,
        "back_forward_quick_start": back_forward_quick_start,
        "next_operator_before_mt5_command_text": collect.get(
            "manual_run_start_mark_command_text", ""
        ),
        "next_step_quick_input": quick_input,
        "next_step_operator_summary": packet_next_step.get("summary", ""),
        "next_step_summary": (
            packet_next_step.get("summary_alias")
            or packet_next_step.get("summary", "")
        ),
        "next_step_collect_filter_summary": packet_next_step.get("collect_filter", ""),
        "run_sequence": steps,
        "after_mt5": collect,
        "blocking_reasons": queue.get("blocking_reasons", []),
    }


def format_quick_input_rows(quick_input: dict[str, Any]) -> list[str]:
    if not quick_input:
        return ["| - |  |"]
    return [f"| {markdown_cell(key)} | {markdown_cell(value)} |" for key, value in quick_input.items()]


def format_sequence_rows(steps: list[dict[str, Any]]) -> list[str]:
    if not steps:
        return ["| - |  |  |  |  |  |  |  |  |  |"]
    rows: list[str] = []
    for step in steps:
        marker = "next" if step.get("is_next") else ""
        rows.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(marker),
                    markdown_cell(step.get("order", "")),
                    markdown_cell(step.get("queue_step", "")),
                    markdown_cell(step.get("purpose", "")),
                    markdown_cell(step.get("dates", "")),
                    markdown_cell(step.get("forward", "")),
                    markdown_cell(step.get("optimization", "")),
                    markdown_cell(step.get("inputs", "")),
                    markdown_cell(step.get("report", "")),
                    markdown_cell(step.get("launch_command_kind", "")),
                ]
            )
            + " |"
        )
    return rows


def format_run_sheet_input_rows(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["| - |  |"]
    return [
        f"| {markdown_cell(row.get('field', ''))} | {markdown_cell(row.get('value', ''))} |"
        for row in rows
    ]


def format_run_sheet_step_rows(steps: list[dict[str, Any]]) -> list[str]:
    if not steps:
        return ["| - |  |  |  |  |  |  |  |  |"]
    rows: list[str] = []
    for step in steps:
        rows.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(step.get("order", "")),
                    markdown_cell(step.get("queue_step", "")),
                    markdown_cell(step.get("purpose", "")),
                    markdown_cell(step.get("dates", "")),
                    markdown_cell(step.get("forward", "")),
                    markdown_cell(step.get("window_summary", "")),
                    markdown_cell(step.get("optimization", "")),
                    markdown_cell(step.get("inputs", "")),
                    markdown_cell(step.get("report", "")),
                    markdown_cell(
                        step.get("step_report_status", "")
                        or step.get("collect_status", "")
                    ),
                ]
            )
            + " |"
        )
    return rows


def format_back_forward_quick_start_rows(steps: list[dict[str, Any]]) -> list[str]:
    if not steps:
        return ["| - |  |  |  |  |  |  |  |"]
    rows: list[str] = []
    for step in steps:
        rows.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(step.get("order", "")),
                    markdown_cell(step.get("purpose", "")),
                    markdown_cell(step.get("dates", "")),
                    markdown_cell(step.get("forward", "")),
                    markdown_cell(step.get("window_summary", "")),
                    markdown_cell(step.get("inputs", "")),
                    markdown_cell(step.get("report", "")),
                    markdown_cell(
                        step.get("step_report_status", "")
                        or step.get("collect_status", "")
                    ),
                ]
            )
            + " |"
        )
    return rows


def format_back_forward_quick_input_rows(quick_inputs: list[dict[str, Any]]) -> list[str]:
    if not quick_inputs:
        return ["| - |  |  |  |  |  |  |  |  |  |  |  |"]
    rows: list[str] = []
    for quick in quick_inputs:
        if not isinstance(quick, dict):
            continue
        rows.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(quick.get("queue_step", "")),
                    markdown_cell(quick.get("purpose", "")),
                    markdown_cell(quick.get("expert", "")),
                    markdown_cell(quick.get("symbol", "")),
                    markdown_cell(quick.get("period", "")),
                    markdown_cell(quick.get("model", "")),
                    markdown_cell(quick.get("from_date", "")),
                    markdown_cell(quick.get("to_date", "")),
                    markdown_cell(quick.get("forward", "")),
                    markdown_cell(quick.get("window_summary", "")),
                    markdown_cell(quick.get("inputs", "")),
                    markdown_cell(quick.get("report", "")),
                ]
            )
            + " |"
        )
    return rows if rows else ["| - |  |  |  |  |  |  |  |  |  |  |  |"]


def format_back_forward_completion_rows(criteria: dict[str, Any]) -> list[str]:
    steps = criteria.get("steps") if isinstance(criteria.get("steps"), list) else []
    if not steps:
        return ["| - |  |  |  |  |  |  |  |"]
    rows: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        rows.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(step.get("order", "")),
                    markdown_cell(step.get("queue_step", "")),
                    markdown_cell(step.get("purpose", "")),
                    markdown_cell(step.get("report", "")),
                    markdown_cell(step.get("expected_report_artifact", "")),
                    markdown_cell(step.get("expected_agent_csv", "")),
                    markdown_cell(step.get("collect_after", "")),
                    markdown_cell(step.get("status", "")),
                ]
            )
            + " |"
        )
    return rows if rows else ["| - |  |  |  |  |  |  |  |"]


def format_back_forward_launch_command_lines(
    quick_start: dict[str, Any],
) -> list[str]:
    steps = quick_start.get("steps") if isinstance(quick_start.get("steps"), list) else []
    blocked = bool(quick_start.get("auto_launch_blocked"))
    lines: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        command = str(step.get("launch_command_text") or "")
        if not command:
            continue
        label = (
            f"Step {step.get('order', '')} {step.get('purpose', '')} "
            + ("auto launch after closing MT5" if blocked else "auto launch")
        ).strip()
        lines.append(f"- {label}: `{markdown_cell(command)}`")
    return lines


def command_line_if_present(label: str, command: object) -> list[str]:
    text = str(command or "")
    if not text:
        return []
    return [f"- {label}: `{markdown_cell(text)}`"]


def auto_launch_command_lines(command: object, *, commands: dict[str, Any]) -> list[str]:
    text = str(command or "")
    if not text:
        return []
    blocked = bool(commands.get("auto_launch_blocked"))
    note = str(commands.get("auto_launch_note") or "")
    blocked_reasons = [
        str(item)
        for item in commands.get("auto_launch_blocked_reasons", [])
        if str(item)
    ] if isinstance(commands.get("auto_launch_blocked_reasons"), list) else []
    if not blocked:
        return command_line_if_present("Auto launch selected step", text)
    lines = ["- Auto launch selected step: blocked"]
    if blocked_reasons:
        lines[0] += f" ({', '.join(blocked_reasons)})"
    if note:
        lines[0] += f"; {note}"
    lines.append(f"- Auto launch command after closing MT5: `{markdown_cell(text)}`")
    return lines


def manual_run_start_mark_lines(packet: dict[str, Any], command: object) -> list[str]:
    text = str(command or "")
    marked = bool(packet.get("manual_run_start_marked"))
    effective_after = ", ".join(
        str(item) for item in packet.get("manual_run_start_effective_after_values", [])
    )
    if marked:
        note = "- Before MT5 run: manual run start is already marked"
        if effective_after:
            note += f" for {effective_after}"
        note += "; rerun the command only when starting a fresh MT5 batch."
        lines = [note]
        if text:
            lines.append(f"- Fresh MT5 batch mark command: `{markdown_cell(text)}`")
        return lines
    if text:
        return command_line_if_present("Before MT5 run, mark start", text)
    return ["- Before MT5 run: manual run start is not marked yet."]


def format_markdown(packet: dict[str, Any]) -> str:
    next_step = packet.get("next_step") if isinstance(packet.get("next_step"), dict) else {}
    quick_input = (
        next_step.get("quick_input") if isinstance(next_step.get("quick_input"), dict) else {}
    )
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
    after_mt5 = packet.get("after_mt5") if isinstance(packet.get("after_mt5"), dict) else {}
    mt5_run_sheet = (
        packet.get("mt5_run_sheet")
        if isinstance(packet.get("mt5_run_sheet"), dict)
        else {}
    )
    back_forward_quick_start = (
        packet.get("back_forward_quick_start")
        if isinstance(packet.get("back_forward_quick_start"), dict)
        else {}
    )
    back_forward_completion = (
        back_forward_quick_start.get("completion_criteria")
        if isinstance(back_forward_quick_start.get("completion_criteria"), dict)
        else {}
    )
    run_sheet_commands = (
        mt5_run_sheet.get("commands")
        if isinstance(mt5_run_sheet.get("commands"), dict)
        else {}
    )
    lines = [
        "# MT5 Manual Operator Packet",
        "",
        f"- Generated at: {packet.get('generated_at', '')}",
        f"- Source queue: {packet.get('queue_json', '')}",
        f"- Queue generated at: {packet.get('queue_generated_at', '')}",
        f"- Status: {packet.get('status', '')}",
        f"- Next action: {packet.get('next_action', '')}",
        f"- Progress state: {packet.get('progress_state', '')}",
        f"- Steps: {packet.get('step_count', '')}",
        f"- Static strategy configs: {packet.get('static_strategy_config_count', '')}",
        f"- Static candidate labels: {packet.get('static_candidate_label_count', '')}",
        f"- Manual run start marked: {packet.get('manual_run_start_marked', False)}",
        f"- Manual run start marked this run: {packet.get('manual_run_start_marked_this_run', False)}",
        f"- Manual run start preserved: {packet.get('manual_run_start_preserved', False)}",
        f"- Manual run start state count: {packet.get('manual_run_start_state_count', '')}",
        f"- Manual run start state marked count: {packet.get('manual_run_start_state_marked_count', '')}",
        "- Manual run start effective after values: "
        + ", ".join(
            str(item) for item in packet.get("manual_run_start_effective_after_values", [])
        ),
        f"- Manual run start after override: {packet.get('manual_run_start_after_override', '')}",
    ]
    if packet.get("static_strategy_configs"):
        lines.append(
            "- Static strategy config list: "
            + ", ".join(str(item) for item in packet.get("static_strategy_configs", []))
        )
    if packet.get("static_candidate_labels"):
        lines.append(
            "- Static candidate label list: "
            + ", ".join(str(item) for item in packet.get("static_candidate_labels", []))
        )
    lines.extend(
        [
            f"- Waiting: {packet.get('waiting_count', '')}",
            f"- Ready to collect: {packet.get('ready_to_collect_count', '')}",
            f"- Blocking reasons: {', '.join(str(item) for item in packet.get('blocking_reasons', []))}",
            "",
            "## Back/Forward Quick Start",
            "",
            f"- Status: {markdown_cell(back_forward_quick_start.get('status', ''))}",
            f"- Purpose: {markdown_cell(back_forward_quick_start.get('purpose', ''))}",
            f"- Steps: {markdown_cell(back_forward_quick_start.get('step_count', ''))}",
            f"- Waiting steps: {markdown_cell(back_forward_quick_start.get('waiting_step_count', ''))}",
            f"- Current step: `{markdown_cell(first_dict(back_forward_quick_start.get('current_step')).get('queue_step', ''))}`",
            f"- Auto launch blocked: {markdown_cell(back_forward_quick_start.get('auto_launch_blocked', ''))}",
            f"- Auto launch note: {markdown_cell(back_forward_quick_start.get('auto_launch_note', ''))}",
            "",
            "| order | purpose | dates | forward | window | inputs | report | status |",
            "|---:|---|---|---|---|---|---|---|",
            *format_back_forward_quick_start_rows(
                back_forward_quick_start.get("steps")
                if isinstance(back_forward_quick_start.get("steps"), list)
                else []
            ),
            "",
            "### Back/Forward MT5 Inputs",
            "",
            "| queue step | purpose | expert | symbol | period | model | from | to | forward | window | inputs | report |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
            *format_back_forward_quick_input_rows(
                back_forward_quick_start.get("quick_inputs")
                if isinstance(back_forward_quick_start.get("quick_inputs"), list)
                else []
            ),
            "",
            "### Back/Forward Completion Criteria",
            "",
            f"- Summary: {markdown_cell(back_forward_completion.get('summary', ''))}",
            f"- All steps required: {markdown_cell(back_forward_completion.get('all_steps_required', ''))}",
            f"- Manual run start after: {markdown_cell(back_forward_completion.get('manual_run_start_after', ''))}",
            f"- Expected steps: {markdown_cell(back_forward_completion.get('expected_step_count', ''))}",
            f"- Waiting steps: {markdown_cell(back_forward_completion.get('waiting_step_count', ''))}",
            *command_line_if_present(
                "Completion collect command",
                back_forward_completion.get("collect_command_text", ""),
            ),
            "| order | queue/step | purpose | report | expected | agent csv | collect after | status |",
            "|---:|---|---|---|---|---|---|---|",
            *format_back_forward_completion_rows(back_forward_completion),
            "",
            *format_back_forward_launch_command_lines(back_forward_quick_start),
            *command_line_if_present(
                "After both Back/Forward steps, collect Back/Forward",
                back_forward_quick_start.get("collect_command_text", ""),
            ),
            *command_line_if_present(
                "After collect readiness, refresh full queue analysis",
                back_forward_quick_start.get("full_queue_collect_command_text", ""),
            ),
            *command_line_if_present(
                "Collect dry-run check",
                back_forward_quick_start.get("dry_run_collect_command_text", ""),
            ),
            "",
            "## MT5 Run Sheet",
            "",
            f"- Operator action: {markdown_cell(mt5_run_sheet.get('operator_action', ''))}",
            f"- Mode: {markdown_cell(mt5_run_sheet.get('operator_mode', ''))}",
            f"- Launch state: {markdown_cell(mt5_run_sheet.get('launch_state', ''))}",
            f"- Source queue: `{markdown_cell(mt5_run_sheet.get('source_queue', ''))}`",
            "",
            "### Next MT5 Input",
            "",
            "| field | value |",
            "|---|---|",
            *format_run_sheet_input_rows(
                mt5_run_sheet.get("next_step_input_rows")
                if isinstance(mt5_run_sheet.get("next_step_input_rows"), list)
                else []
            ),
            "",
            "### Back/Forward Steps",
            "",
            "| order | queue/step | purpose | dates | forward | window | optimization | inputs | report | status |",
            "|---:|---|---|---|---|---|---|---|---|---|",
            *format_run_sheet_step_rows(
                mt5_run_sheet.get("back_forward_steps")
                if isinstance(mt5_run_sheet.get("back_forward_steps"), list)
                else []
            ),
            "",
            "### MT5 Run Commands",
            "",
            *manual_run_start_mark_lines(packet, run_sheet_commands.get("before_mt5_run", "")),
            *auto_launch_command_lines(
                run_sheet_commands.get("auto_launch", ""),
                commands=run_sheet_commands,
            ),
            *command_line_if_present(
                "After MT5, collect dry-run",
                run_sheet_commands.get("collect_dry_run", ""),
            ),
            *command_line_if_present(
                "If ready, collect and refresh all",
                run_sheet_commands.get("collect_execute_and_refresh_all", ""),
            ),
            "",
            "## Now",
            "",
        ]
    )
    if next_step.get("queue_step"):
        lines.extend(
            [
                f"- Queue step: `{markdown_cell(next_step.get('queue_step', ''))}`",
                f"- Purpose: {markdown_cell(next_step.get('purpose', ''))}",
                f"- Summary: {markdown_cell(next_step.get('summary', ''))}",
                f"- Collect filter: {markdown_cell(next_step.get('collect_filter', ''))}",
                f"- Launch kind: {markdown_cell(next_step.get('launch_command_kind', ''))}",
                *manual_run_start_mark_lines(
                    packet,
                    after_mt5.get("manual_run_start_mark_command_text", ""),
                ),
            ]
        )
        if next_step.get("launch_command_text"):
            lines.extend(
                auto_launch_command_lines(
                    next_step.get("launch_command_text", ""),
                    commands=run_sheet_commands,
                )
            )
    else:
        lines.append("- No Strategy Tester launch step is currently selected.")
    lines.extend(
        [
            "",
            "## Launch Status",
            "",
            f"- Auto launch state: {markdown_cell(launch_status.get('auto_launch_state', ''))}",
            f"- Queue launch status: {markdown_cell(launch_status.get('status', ''))}",
            f"- Next action: {markdown_cell(launch_status.get('next_action', ''))}",
            f"- Selected step: `{markdown_cell(launch_status.get('selected_queue_step', ''))}`",
            f"- Selected matches handoff: {markdown_cell(launch_status.get('selected_matches_queue_handoff', ''))}",
            f"- Launch kind: {markdown_cell(launch_status.get('launch_command_kind', ''))}",
            f"- Blocked: {markdown_cell(launch_status.get('blocked', ''))}",
            f"- Blocked reasons: {', '.join(str(item) for item in launch_status.get('blocked_reasons', []))}",
            f"- Running terminal count: {markdown_cell(launch_status.get('running_terminal_count', ''))}",
            f"- Queue launch file: `{markdown_cell(launch_status.get('queue_launch_json', ''))}`",
        ]
    )
    lines.extend(
        [
            "",
            "## Bridge Recovery",
            "",
            f"- Status: {markdown_cell(bridge_recovery.get('status', ''))}",
            f"- Ready for MT5 validation: {markdown_cell(bridge_recovery.get('ready_for_mt5_validation', ''))}",
            f"- Next action: {markdown_cell(bridge_recovery.get('next_action', ''))}",
            f"- Blocking reasons: {', '.join(str(item) for item in bridge_recovery.get('blocking_reasons', []))}",
            f"- Standalone Strategy Tester allowed: {markdown_cell(bridge_recovery.get('standalone_strategy_tester_allowed', ''))}",
            f"- Note: {markdown_cell(bridge_recovery.get('strategy_tester_note', ''))}",
            f"- Operator step: {markdown_cell(bridge_recovery.get('operator_step', ''))}",
            f"- Verification: {markdown_cell(bridge_recovery.get('verification', ''))}",
            "- Verification commands: "
            + (
                "; ".join(
                    f"{markdown_cell(row.get('label', ''))}: `{markdown_cell(row.get('command', ''))}`"
                    for row in bridge_recovery.get("verification_commands", [])
                    if isinstance(row, dict)
                )
                if bridge_recovery.get("verification_commands")
                else ""
            ),
            f"- EA POST: {markdown_cell(bridge_recovery.get('bridge_log_activity_status', ''))}; last={markdown_cell(bridge_recovery.get('last_ea_post_timestamp', ''))} age={markdown_cell(bridge_recovery.get('last_ea_post_age_seconds', ''))}s path={markdown_cell(bridge_recovery.get('last_ea_post_path', ''))}",
            f"- History: pending={markdown_cell(bridge_recovery.get('history_request_pending', ''))} stale_pending={markdown_cell(bridge_recovery.get('history_request_stale_pending', ''))} match={markdown_cell(bridge_recovery.get('history_done_matches_request', ''))} data_stale={markdown_cell(bridge_recovery.get('history_data_stale', ''))}",
            f"- Bridge recovery file: `{markdown_cell(bridge_recovery.get('bridge_recovery_json', ''))}`",
        ]
    )
    if strategy_analysis.get("available"):
        strategy_lines = [
            "",
            "## Strategy Evidence",
            "",
            f"- Status: {markdown_cell(strategy_analysis.get('status', ''))}",
            f"- Promotion decision: {markdown_cell(strategy_analysis.get('promotion_decision', ''))}",
            f"- Back/Forward: {markdown_cell(strategy_analysis.get('back_forward_evidence_state', ''))} / {markdown_cell(strategy_analysis.get('back_forward_performance_status', ''))}",
        ]
        if strategy_analysis.get("operator_decision_verdict"):
            strategy_lines.append(
                "- Operator decision: "
                f"verdict={markdown_cell(strategy_analysis.get('operator_decision_verdict', ''))}, "
                f"status={markdown_cell(strategy_analysis.get('operator_decision_status', ''))}, "
                f"adoptable={markdown_cell(strategy_analysis.get('operator_decision_adoptable', ''))}, "
                f"blocker={markdown_cell(strategy_analysis.get('operator_decision_primary_blocker', ''))}"
            )
        if strategy_analysis.get("operator_decision_summary"):
            strategy_lines.append(
                "- Operator decision summary: "
                + markdown_cell(strategy_analysis.get("operator_decision_summary", ""))
            )
        if strategy_analysis.get("operator_decision_command_text"):
            strategy_lines.append(
                "- Operator decision command: `"
                + markdown_cell(strategy_analysis.get("operator_decision_command_text", ""))
                + "`"
            )
        if strategy_analysis.get("back_forward_decision_status"):
            strategy_lines.append(
                "- Back/Forward decision: "
                f"status={markdown_cell(strategy_analysis.get('back_forward_decision_status', ''))}, "
                f"adoptable={markdown_cell(strategy_analysis.get('back_forward_decision_adoptable', ''))}, "
                f"next={markdown_cell(strategy_analysis.get('back_forward_decision_next_action', ''))}"
            )
        if strategy_analysis.get("back_forward_decision_reason"):
            strategy_lines.append(
                "- Back/Forward decision reason: "
                + markdown_cell(strategy_analysis.get("back_forward_decision_reason", ""))
            )
        thresholds = strategy_analysis.get("back_forward_decision_thresholds")
        if isinstance(thresholds, dict) and thresholds:
            threshold_parts = [
                f"{key}={thresholds.get(key)}"
                for key in (
                    "min_closed",
                    "break_even_pf",
                    "break_even_avg_r",
                    "degraded_pf_delta",
                    "degraded_avg_r_delta",
                )
                if thresholds.get(key) not in (None, "")
            ]
            if threshold_parts:
                strategy_lines.append("- Back/Forward decision thresholds: " + ", ".join(threshold_parts))
        metric_parts = []
        for key, label in (
            ("back_forward_decision_backtest_trades", "backtest_trades"),
            ("back_forward_decision_forward_trades", "forward_trades"),
            ("back_forward_decision_forward_pf", "forward_pf"),
            ("back_forward_decision_forward_avg_r", "forward_avg_r"),
            ("back_forward_decision_forward_pf_delta_vs_backtest", "forward_pf_delta"),
            ("back_forward_decision_forward_avg_r_delta_vs_backtest", "forward_avg_r_delta"),
        ):
            value = strategy_analysis.get(key)
            if value not in (None, ""):
                metric_parts.append(f"{label}={value}")
        if metric_parts:
            strategy_lines.append("- Back/Forward decision metrics: " + ", ".join(metric_parts))
        if strategy_analysis.get("back_forward_decision_collect_command_text"):
            strategy_lines.append(
                "- Back/Forward collect: `"
                + markdown_cell(strategy_analysis.get("back_forward_decision_collect_command_text", ""))
                + "`"
            )
        if strategy_analysis.get("back_forward_decision_sample_shortage_recovery_command_text"):
            strategy_lines.append(
                "- Back/Forward sample shortage recovery: "
                f"range_strategy={markdown_cell(strategy_analysis.get('back_forward_decision_sample_shortage_recovery_range_strategy', ''))}, "
                f"suggested={markdown_cell(strategy_analysis.get('back_forward_decision_sample_shortage_recovery_suggested_from_date', ''))}"
                f"..{markdown_cell(strategy_analysis.get('back_forward_decision_sample_shortage_recovery_suggested_to_date', ''))}"
            )
            strategy_lines.append(
                "- Back/Forward extended run: `"
                + markdown_cell(
                    strategy_analysis.get(
                        "back_forward_decision_sample_shortage_recovery_command_text",
                        "",
                    )
                )
                + "`"
            )
        strategy_lines.extend(
            [
                f"- Source-time refresh: {markdown_cell(strategy_analysis.get('source_time_refresh_status', ''))}; labels={', '.join(strategy_analysis.get('source_time_candidate_issue_labels', []))}",
                f"- Source-time queue: `{markdown_cell(strategy_analysis.get('source_time_refresh_queue_command_text', ''))}`",
                f"- Source-time collect: `{markdown_cell(strategy_analysis.get('source_time_collect_refresh_command_text', ''))}`",
                f"- Source-time analysis refresh: `{markdown_cell(strategy_analysis.get('source_time_refresh_analysis_command_text', ''))}`",
                f"- BUY gap: {markdown_cell(strategy_analysis.get('buy_candidate_gap_status', ''))}; labels={', '.join(strategy_analysis.get('buy_candidate_gap_diagnostic_labels', []))}",
                f"- BUY gap reason: {markdown_cell(strategy_analysis.get('buy_candidate_gap_reason', ''))}",
                f"- BUY diagnostic queue: `{markdown_cell(strategy_analysis.get('buy_candidate_gap_refresh_queue_command_text', ''))}`",
                f"- BUY diagnostic collect: `{markdown_cell(strategy_analysis.get('buy_candidate_gap_collect_refresh_command_text', ''))}`",
                f"- Strategy analysis file: `{markdown_cell(strategy_analysis.get('strategy_analysis_json', ''))}`",
            ]
        )
        lines.extend(
            strategy_lines
        )
    lines.extend(
        [
            "",
            "## Next Operator Action",
            "",
            f"- Action: {markdown_cell(first_dict(packet.get('next_operator_action')).get('action', ''))}",
            f"- Mode: {markdown_cell(first_dict(packet.get('next_operator_action')).get('mode', ''))}",
            f"- Instruction: {markdown_cell(first_dict(packet.get('next_operator_action')).get('instruction', ''))}",
            f"- Queue step: `{markdown_cell(first_dict(packet.get('next_operator_action')).get('queue_step', ''))}`",
            f"- Command: `{markdown_cell(first_dict(packet.get('next_operator_action')).get('command_text', ''))}`",
            *manual_run_start_mark_lines(
                packet,
                after_mt5.get("manual_run_start_mark_command_text", ""),
            ),
            f"- Follow-up: `{markdown_cell(first_dict(packet.get('next_operator_action')).get('follow_up_command_text', ''))}`",
            f"- Verification: {markdown_cell(first_dict(packet.get('next_operator_action')).get('verification', ''))}",
            "",
            "## MT5 Input",
            "",
            "| field | value |",
            "|---|---|",
            *format_quick_input_rows(quick_input),
            "",
            "## Run Sequence",
            "",
            "| next | order | queue/step | purpose | dates | forward | optimization | inputs | report | launch |",
            "|---|---:|---|---|---|---|---|---|---|---|",
            *format_sequence_rows(
                packet.get("run_sequence") if isinstance(packet.get("run_sequence"), list) else []
            ),
            "",
            "## After MT5",
            "",
            *manual_run_start_mark_lines(
                packet,
                after_mt5.get("manual_run_start_mark_command_text", ""),
            ),
            f"- First run collect dry-run: `{markdown_cell(after_mt5.get('dry_run_command_text', ''))}`",
            f"- If ready, collect: `{markdown_cell(after_mt5.get('execute_command_text', ''))}`",
            (
                "- Collect and refresh analysis: "
                f"`{markdown_cell(after_mt5.get('execute_and_refresh_analysis_command_text', ''))}`"
            ),
            (
                "- Collect and refresh full analysis: "
                f"`{markdown_cell(after_mt5.get('execute_and_refresh_all_command_text', ''))}`"
            ),
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--queue-launch-json", default=DEFAULT_QUEUE_LAUNCH_JSON)
    parser.add_argument("--bridge-recovery-plan-json", default=DEFAULT_BRIDGE_RECOVERY_PLAN_JSON)
    parser.add_argument("--strategy-analysis-json", default=DEFAULT_STRATEGY_ANALYSIS_JSON)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    queue = read_json(args.queue)
    queue_launch = read_json(args.queue_launch_json) if args.queue_launch_json else {}
    bridge_recovery = (
        read_json(args.bridge_recovery_plan_json) if args.bridge_recovery_plan_json else {}
    )
    strategy_analysis = read_json(args.strategy_analysis_json) if args.strategy_analysis_json else {}
    packet = build_packet(
        queue,
        queue_path=args.queue,
        queue_launch=queue_launch,
        queue_launch_path=args.queue_launch_json,
        bridge_recovery=bridge_recovery,
        bridge_recovery_path=args.bridge_recovery_plan_json,
        strategy_analysis=strategy_analysis,
        strategy_analysis_path=args.strategy_analysis_json,
    )
    write_text(args.output_json, json.dumps(packet, ensure_ascii=False, indent=2) + "\n")
    write_text(args.output_md, format_markdown(packet))
    summary = {
        "ok": packet.get("ok", False),
        "status": packet.get("status", ""),
        "queue_json": args.queue,
        "output_json": args.output_json,
        "output_md": args.output_md,
        "next_queue_step": packet.get("next_queue_step", ""),
        "step_count": packet.get("step_count", ""),
        "manual_run_start_marked": packet.get("manual_run_start_marked", False),
        "manual_run_start_marked_this_run": packet.get(
            "manual_run_start_marked_this_run", False
        ),
        "manual_run_start_preserved": packet.get("manual_run_start_preserved", False),
        "manual_run_start_effective_after_values": packet.get(
            "manual_run_start_effective_after_values", []
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if packet.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
