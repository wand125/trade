from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT
from analysis.mt5_back_forward_run import (
    manual_collect_readiness as static_manual_collect_readiness,
    manual_strategy_tester_step,
    tester_config_plan_metadata,
)
from analysis.mt5_compile import default_wine_path
from analysis.mt5_compile_status import default_mt5_root
from analysis.mt5_next_action_run import select_next_action_plan
from analysis.mt5_tester_optimization_report import estimate_set_passes
from analysis.mt5_tester_run import (
    build_terminal_command,
    resolve_expert_parameters_set,
    tester_config_metadata,
)


DEFAULT_BACK_FORWARD_RUN = "runtime/latest_mt5_back_forward_run.json"
DEFAULT_SELL_NEXT_ACTION_RUN = "runtime/latest_mt5_next_action_run.json"
DEFAULT_BUY_NEXT_ACTION_RUN = "runtime/latest_mt5_next_action_run_buy.json"
DEFAULT_PROMOTION_GATE = "runtime/latest_promotion_gate.json"
DEFAULT_OUTPUT_JSON = "runtime/latest_mt5_manual_test_queue.json"
DEFAULT_OUTPUT_MD = "runtime/latest_mt5_manual_test_queue.md"
DEFAULT_COLLECT_OUTPUT_JSON = "runtime/latest_mt5_manual_collect_run.json"
DEFAULT_COLLECT_OUTPUT_MD = "runtime/latest_mt5_manual_collect_run.md"
DEFAULT_OUTPUT_JSON_WITH_OPTIMIZATION = "runtime/latest_mt5_manual_test_queue_with_optimization.json"
DEFAULT_COLLECT_OUTPUT_JSON_WITH_OPTIMIZATION = "runtime/latest_mt5_manual_collect_with_optimization.json"
DEFAULT_COLLECT_OUTPUT_MD_WITH_OPTIMIZATION = "runtime/latest_mt5_manual_collect_with_optimization.md"
COMPLETED_COLLECT_STATUSES = {"already_collected", "collect_executed"}
DEFAULT_STATIC_OPTIMIZATION_CONFIGS = (
    "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_optimization.ini",
    "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_next_optimization.ini",
)
DEFAULT_STATIC_CANDIDATE_CONFIGS: dict[str, dict[str, str]] = {
    "sell_hour12_m30m15_2025": {
        "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_validation.ini",
        "queue_id": "static_sell_hour12_m30m15_2025",
        "title": "Sell Hour12 M30M15 2025 Annual Validation MT5 Optimization",
        "label": "sell_hour12_m30m15_2025",
        "report_name": "Tester\\Swing_Evaluation_Trader_sell_hour12_m30m15_validation_2025",
        "from_date": "2025.01.01",
        "to_date": "2025.12.31",
        "forward_mode": "3",
        "output_suffix": "sell_hour12_m30m15_validation_2025",
        "run_json": "runtime/latest_mt5_tester_sell_hour12_m30m15_validation_2025_run.json",
        "run_md": "runtime/latest_mt5_tester_sell_hour12_m30m15_validation_2025_run.md",
        "report_json": "runtime/latest_mt5_sell_hour12_m30m15_validation_2025_optimization_report.json",
        "report_md": "runtime/latest_mt5_sell_hour12_m30m15_validation_2025_optimization_report.md",
    },
    "sell_hour12_m30m15_calendar_2025": {
        "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.ini",
        "queue_id": "static_sell_hour12_m30m15_calendar_2025",
        "title": "Sell Hour12 M30M15 Calendar 2025 Annual Validation MT5 Optimization",
        "label": "sell_hour12_m30m15_calendar_2025",
        "report_name": "Tester\\Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation_2025",
        "from_date": "2025.01.01",
        "to_date": "2025.12.31",
        "forward_mode": "3",
        "output_suffix": "sell_hour12_m30m15_calendar_validation_2025",
        "run_json": "runtime/latest_mt5_tester_sell_hour12_m30m15_calendar_validation_2025_run.json",
        "run_md": "runtime/latest_mt5_tester_sell_hour12_m30m15_calendar_validation_2025_run.md",
        "report_json": "runtime/latest_mt5_sell_hour12_m30m15_calendar_validation_2025_optimization_report.json",
        "report_md": (
            "runtime/latest_mt5_sell_hour12_m30m15_calendar_validation_2025_optimization_report.md"
        ),
    },
    "buy_wide_stop_short": {
        "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_wide_stop_validation.ini",
        "queue_id": "static_buy_wide_stop_short",
        "title": "Buy Wide Stop Short-Window Validation MT5 Optimization",
        "label": "buy_wide_stop_short",
        "report_name": "Tester\\Swing_Evaluation_Trader_buy_wide_stop_validation",
        "from_date": "2026.06.30",
        "to_date": "2026.07.08",
        "forward_mode": "3",
        "output_suffix": "buy_wide_stop_validation",
        "run_json": "runtime/latest_mt5_tester_buy_wide_stop_validation_run.json",
        "run_md": "runtime/latest_mt5_tester_buy_wide_stop_validation_run.md",
        "report_json": "runtime/latest_mt5_buy_wide_stop_validation_optimization_report.json",
        "report_md": "runtime/latest_mt5_buy_wide_stop_validation_optimization_report.md",
    },
    "buy_hour03_wide_stop_2025": {
        "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.ini",
        "queue_id": "static_buy_hour03_wide_stop_2025",
        "title": "Buy Hour03 Wide Stop 2025 Annual Validation MT5 Optimization",
        "label": "buy_hour03_wide_stop_2025",
        "report_name": "Tester\\Swing_Evaluation_Trader_buy_hour03_wide_stop_validation_2025",
        "from_date": "2025.01.01",
        "to_date": "2025.12.31",
        "forward_mode": "3",
        "output_suffix": "buy_hour03_wide_stop_validation_2025",
        "run_json": "runtime/latest_mt5_tester_buy_hour03_wide_stop_validation_2025_run.json",
        "run_md": "runtime/latest_mt5_tester_buy_hour03_wide_stop_validation_2025_run.md",
        "report_json": "runtime/latest_mt5_buy_hour03_wide_stop_validation_2025_optimization_report.json",
        "report_md": "runtime/latest_mt5_buy_hour03_wide_stop_validation_2025_optimization_report.md",
    },
    "buy_hour03_wide_stop_calendar_2025": {
        "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.ini",
        "queue_id": "static_buy_hour03_wide_stop_calendar_2025",
        "title": "Buy Hour03 Wide Stop Calendar 2025 Annual Validation MT5 Optimization",
        "label": "buy_hour03_wide_stop_calendar_2025",
        "report_name": "Tester\\Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation_2025",
        "from_date": "2025.01.01",
        "to_date": "2025.12.31",
        "forward_mode": "3",
        "output_suffix": "buy_hour03_wide_stop_calendar_validation_2025",
        "run_json": "runtime/latest_mt5_tester_buy_hour03_wide_stop_calendar_validation_2025_run.json",
        "run_md": "runtime/latest_mt5_tester_buy_hour03_wide_stop_calendar_validation_2025_run.md",
        "report_json": "runtime/latest_mt5_buy_hour03_wide_stop_calendar_validation_2025_optimization_report.json",
        "report_md": (
            "runtime/latest_mt5_buy_hour03_wide_stop_calendar_validation_2025_optimization_report.md"
        ),
    },
}


def load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def collect_status_completed(status: Any) -> bool:
    return str(status or "") in COMPLETED_COLLECT_STATUSES


def entry_collect_completed(entry: dict[str, Any]) -> bool:
    return collect_status_completed(entry.get("collect_status"))


def command_text(manual_plan: dict[str, Any], *, manual_run_start_after: str = "") -> str:
    text = str(
        manual_plan.get("recommended_collect_only_command_text")
        or manual_plan.get("collect_only_command_text")
        or ""
    )
    generated_at = str(manual_run_start_after or manual_plan.get("manual_run_start_after") or "")
    if not text.strip() or not generated_at:
        return text
    try:
        command = shlex.split(text)
    except ValueError:
        return text
    if "--collect-only" not in command:
        return text
    if "--csv-modified-after" in command:
        index = command.index("--csv-modified-after")
        if index + 1 < len(command):
            command[index + 1] = generated_at
        else:
            command.append(generated_at)
        return shlex.join(command)
    return shlex.join([*command, "--csv-modified-after", generated_at])


def refresh_command_text(queue_id: str, source_path: str) -> str:
    if queue_id == "score_weight_sell":
        return (
            "python3 methods/swing_eval/analysis/mt5_next_action_run.py --target score_weight_sample_collection "
            f"--focus-side sell --output-json {shlex.quote(source_path)} "
            f"--output-md {shlex.quote(str(Path(source_path).with_suffix('.md')))}"
        )
    if queue_id == "score_weight_buy":
        return (
            "python3 methods/swing_eval/analysis/mt5_next_action_run.py --target score_weight_sample_collection "
            f"--focus-side buy --output-json {shlex.quote(source_path)} "
            f"--output-md {shlex.quote(str(Path(source_path).with_suffix('.md')))}"
        )
    return ""


def unique_texts(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "")
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def comparable_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def planned_outputs_bundle(
    primary: Any,
    archive_preview: Any,
    follow_up: Any,
    follow_up_archive_preview: Any,
) -> dict[str, dict[str, Any]]:
    return {
        "primary": primary if isinstance(primary, dict) else {},
        "archive_preview": archive_preview if isinstance(archive_preview, dict) else {},
        "follow_up": follow_up if isinstance(follow_up, dict) else {},
        "follow_up_archive_preview": (
            follow_up_archive_preview if isinstance(follow_up_archive_preview, dict) else {}
        ),
    }


def next_action_values_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
    primary = payload.get("primary") if isinstance(payload.get("primary"), dict) else {}
    archive_preview = payload.get("archive_preview") if isinstance(payload.get("archive_preview"), dict) else {}
    follow_up = payload.get("follow_up") if isinstance(payload.get("follow_up"), dict) else {}
    follow_up_archive_preview = (
        payload.get("follow_up_archive_preview")
        if isinstance(payload.get("follow_up_archive_preview"), dict)
        else {}
    )
    return {
        "execution_key": payload.get("execution_key", ""),
        "action_priority": action.get("priority", ""),
        "action_area": action.get("area", ""),
        "action": action.get("action", ""),
        "kind": primary.get("kind", ""),
        "focus_side": primary.get("focus_side", ""),
        "optimization_mode": primary.get("optimization_mode", ""),
        "config": primary.get("config", ""),
        "set": primary.get("set", ""),
        "output_set": primary.get("output_set", ""),
        "agent_csv_archive_run_id": primary.get("agent_csv_archive_run_id", ""),
        "timeout_seconds": primary.get("timeout_seconds", ""),
        "timeout_minutes": primary.get("timeout_minutes", ""),
        "timeout_note": primary.get("timeout_note", ""),
        "optimized_input_count": primary.get("optimized_input_count", ""),
        "estimated_full_factorial_passes": primary.get("estimated_full_factorial_passes", ""),
        "latest_executed_tester_xml_rows": primary.get("latest_executed_tester_xml_rows", ""),
        "evidence_role": primary.get("evidence_role", ""),
        "diagnostic_only": primary.get("diagnostic_only", ""),
        "promotion_evidence": primary.get("promotion_evidence", ""),
        "planned_outputs": planned_outputs_bundle(
            primary.get("planned_outputs", {}),
            archive_preview.get("planned_outputs", {}),
            follow_up.get("planned_outputs", {}),
            follow_up_archive_preview.get("planned_outputs", {}),
        ),
        "primary_planned_outputs": primary.get("planned_outputs", {}),
        "archive_preview_planned_outputs": archive_preview.get("planned_outputs", {}),
        "follow_up_planned_outputs": follow_up.get("planned_outputs", {}),
        "follow_up_archive_preview_planned_outputs": follow_up_archive_preview.get("planned_outputs", {}),
    }


def next_action_values_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
    action = plan.get("action") if isinstance(plan.get("action"), dict) else {}
    primary = plan.get("primary") if isinstance(plan.get("primary"), dict) else {}
    archive_preview = plan.get("archive_preview") if isinstance(plan.get("archive_preview"), dict) else {}
    follow_up = plan.get("follow_up") if isinstance(plan.get("follow_up"), dict) else {}
    follow_up_archive_preview = (
        plan.get("follow_up_archive_preview")
        if isinstance(plan.get("follow_up_archive_preview"), dict)
        else {}
    )
    return {
        "execution_key": plan.get("execution_key", ""),
        "action_priority": action.get("priority", ""),
        "action_area": action.get("area", ""),
        "action": action.get("action", ""),
        "kind": primary.get("kind", ""),
        "focus_side": primary.get("focus_side", ""),
        "optimization_mode": primary.get("optimization_mode", ""),
        "config": primary.get("config", ""),
        "set": primary.get("set", ""),
        "output_set": primary.get("output_set", ""),
        "agent_csv_archive_run_id": primary.get("agent_csv_archive_run_id", ""),
        "timeout_seconds": primary.get("timeout_seconds", ""),
        "timeout_minutes": primary.get("timeout_minutes", ""),
        "timeout_note": primary.get("timeout_note", ""),
        "optimized_input_count": primary.get("optimized_input_count", ""),
        "estimated_full_factorial_passes": primary.get("estimated_full_factorial_passes", ""),
        "latest_executed_tester_xml_rows": primary.get("latest_executed_tester_xml_rows", ""),
        "evidence_role": primary.get("evidence_role", ""),
        "diagnostic_only": primary.get("diagnostic_only", ""),
        "promotion_evidence": primary.get("promotion_evidence", ""),
        "planned_outputs": planned_outputs_bundle(
            primary.get("planned_outputs", {}),
            archive_preview.get("planned_outputs", {}),
            follow_up.get("planned_outputs", {}),
            follow_up_archive_preview.get("planned_outputs", {}),
        ),
        "primary_planned_outputs": primary.get("planned_outputs", {}),
        "archive_preview_planned_outputs": archive_preview.get("planned_outputs", {}),
        "follow_up_planned_outputs": follow_up.get("planned_outputs", {}),
        "follow_up_archive_preview_planned_outputs": follow_up_archive_preview.get("planned_outputs", {}),
    }


def pass_budget_note(step: dict[str, Any], budget: dict[str, Any]) -> str:
    if budget.get("available") is not True:
        return str(budget.get("reason") or "set file not available")
    optimization = str(step.get("optimization") or "").strip().lower()
    run_type = str(step.get("run_type") or "")
    if optimization in {"", "0", "false", "no"} and not run_type.startswith("optimization"):
        return "Single Strategy Tester pass; optimization is disabled."
    return "Full-factorial candidates are an upper bound; MT5 genetic optimization may execute fewer passes."


def step_pass_budget(step: dict[str, Any]) -> dict[str, Any]:
    config_path = str(step.get("config") or "").strip()
    expert_parameters = str(step.get("expert_parameters") or "").strip()
    budget: dict[str, Any] = {
        "available": False,
        "set_file": "",
        "optimized_input_count": "",
        "estimated_full_factorial_passes": "",
        "optimized_input_names": [],
        "reason": "",
        "note": "",
    }
    if not config_path:
        budget["reason"] = "config missing"
        budget["note"] = pass_budget_note(step, budget)
        return budget
    set_file = resolve_expert_parameters_set(
        workspace_root=Path.cwd(),
        config_path=config_path,
        expert_parameters=expert_parameters,
    )
    if set_file is None:
        budget["reason"] = "expert parameters set missing"
        budget["note"] = pass_budget_note(step, budget)
        return budget
    budget["set_file"] = str(set_file)
    if not set_file.exists():
        budget["reason"] = "set file not found"
        budget["note"] = pass_budget_note(step, budget)
        return budget
    try:
        estimate = estimate_set_passes(set_file.read_text(encoding="utf-8"))
    except OSError as exc:
        budget["reason"] = str(exc)
        budget["note"] = pass_budget_note(step, budget)
        return budget
    optimized_inputs = estimate.get("optimized_inputs")
    if not isinstance(optimized_inputs, list):
        optimized_inputs = []
    budget.update(
        {
            "available": True,
            "optimized_input_count": estimate.get("optimized_input_count", 0),
            "estimated_full_factorial_passes": estimate.get(
                "estimated_full_factorial_passes",
                1,
            ),
            "optimized_input_names": [
                str(item.get("name"))
                for item in optimized_inputs
                if isinstance(item, dict) and item.get("name")
            ],
            "reason": "",
        }
    )
    budget["note"] = pass_budget_note(step, budget)
    return budget


def attach_step_pass_budget(step: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(step, dict):
        return step
    enriched = dict(step)
    budget = step_pass_budget(enriched)
    enriched["pass_budget"] = budget
    enriched["pass_budget_available"] = budget.get("available")
    enriched["optimized_input_count"] = budget.get("optimized_input_count", "")
    enriched["estimated_full_factorial_passes"] = budget.get(
        "estimated_full_factorial_passes",
        "",
    )
    return enriched


def attach_steps_pass_budget(steps: list[Any]) -> list[dict[str, Any]]:
    return [attach_step_pass_budget(step) for step in steps if isinstance(step, dict)]


def apply_manual_run_start_to_step(
    step: dict[str, Any],
    *,
    manual_run_start_after: str,
    marked: bool = False,
    collect_status: str = "",
) -> dict[str, Any]:
    updated = dict(step)
    if manual_run_start_after:
        updated["manual_run_start_after"] = manual_run_start_after
        updated["collect_modified_after"] = manual_run_start_after
        artifacts = updated.get("expected_artifacts")
        if isinstance(artifacts, dict):
            artifacts = dict(artifacts)
            artifacts["agent_csv_modified_after"] = manual_run_start_after
            if collect_status:
                artifacts["collect_status"] = collect_status
            updated["expected_artifacts"] = artifacts
    if marked:
        updated["manual_run_start_marked"] = True
    return updated


def apply_manual_run_start_to_steps(
    steps: list[dict[str, Any]],
    *,
    manual_run_start_after: str,
    marked: bool = False,
    collect_status: str = "",
) -> list[dict[str, Any]]:
    return [
        apply_manual_run_start_to_step(
            step,
            manual_run_start_after=manual_run_start_after,
            marked=marked,
            collect_status=collect_status,
        )
        for step in steps
        if isinstance(step, dict)
    ]


def next_action_gate_consistency(payload: dict[str, Any], gate_payload: dict[str, Any]) -> dict[str, Any]:
    runner_generated_at = payload.get("promotion_generated_at") or payload.get("generated_at", "")
    current_generated_at = gate_payload.get("generated_at", "") if gate_payload else ""
    runner_decision = payload.get("promotion_decision") or payload.get("decision", "")
    current_decision = gate_payload.get("decision", "") if gate_payload else ""
    decision_match = bool(runner_decision and current_decision and runner_decision == current_decision)
    target = str(payload.get("target") or "")
    focus_side = str(payload.get("focus_side") or "")
    selected_action_present = False
    selected_action_current = False
    mismatches: list[str] = []

    if gate_payload and target:
        current_plan = select_next_action_plan(gate_payload, target=target, focus_side=focus_side)
        selected_action_present = current_plan.get("found") is True
        if selected_action_present:
            runner_values = next_action_values_from_payload(payload)
            current_values = next_action_values_from_plan(current_plan)
            mismatches = [
                key
                for key, value in runner_values.items()
                if comparable_text(value) != comparable_text(current_values.get(key, ""))
            ]
            selected_action_current = not mismatches

    current_for_execution = bool(
        runner_generated_at
        and current_generated_at
        and decision_match
        and selected_action_present
        and selected_action_current
    )
    stale_reason = ""
    if not gate_payload:
        stale_reason = "missing_current_promotion_gate"
    elif not target:
        stale_reason = "missing_runner_target"
    elif not runner_generated_at:
        stale_reason = "missing_runner_promotion_generated_at"
    elif not current_generated_at:
        stale_reason = "missing_current_promotion_generated_at"
    elif not runner_decision:
        stale_reason = "missing_runner_promotion_decision"
    elif not current_decision:
        stale_reason = "missing_current_promotion_decision"
    elif not decision_match:
        stale_reason = "promotion_gate_decision_mismatch"
    elif not selected_action_present:
        stale_reason = "selected_action_not_found_in_current_gate"
    elif mismatches:
        stale_reason = "selected_action_mismatch"

    return {
        "current_for_execution": current_for_execution,
        "gate_stale_reason": stale_reason,
        "runner_promotion_generated_at": runner_generated_at,
        "current_promotion_generated_at": current_generated_at,
        "runner_promotion_decision": runner_decision,
        "current_promotion_decision": current_decision,
        "selected_action_present": selected_action_present,
        "selected_action_current": selected_action_current,
        "selected_action_mismatches": mismatches,
    }


def static_config_label(config_path: str | Path) -> str:
    stem = Path(config_path).stem
    prefix = "Swing_Evaluation_Trader_"
    if stem.startswith(prefix):
        return stem[len(prefix) :]
    return stem


def static_config_queue_id(config_path: str | Path) -> str:
    label = static_config_label(config_path)
    safe = "".join(char if char.isalnum() or char == "_" else "_" for char in label)
    return f"static_{safe or 'config'}"


def static_config_title(config_path: str | Path, metadata: dict[str, str]) -> str:
    label = static_config_label(config_path).replace("_", " ").title()
    optimization = str(metadata.get("optimization") or "")
    if optimization and optimization != "0":
        if "Optimization" in label:
            return f"MT5 {label}"
        return f"{label} MT5 Optimization"
    return f"{label} MT5 Strategy Test"


def static_config_output_suffix(config_path: str | Path) -> str:
    label = static_config_label(config_path)
    safe = "".join(char if char.isalnum() or char == "_" else "_" for char in label)
    return safe.strip("_") or "static_config"


def static_config_collect_command(
    *,
    config_path: str,
    report_name: str,
    generated_at: str,
    timeout_seconds: int,
    since_minutes: float,
    min_closed: int,
    from_date: str = "",
    to_date: str = "",
    forward_mode: str = "",
    output_suffix: str = "",
    run_json: str = "",
    run_md: str = "",
    report_json: str = "",
    report_md: str = "",
) -> str:
    suffix = output_suffix or static_config_output_suffix(config_path)
    command = [
        "python3",
        "methods/swing_eval/analysis/mt5_tester_run.py",
        "--config",
        config_path,
        "--report-name",
        report_name,
        "--collect-only",
        "--timeout-seconds",
        str(timeout_seconds),
        "--since-minutes",
        str(since_minutes),
        "--min-closed",
        str(min_closed),
        "--sync-expert-parameters-set",
        "--allow-stale-compile",
        "--output-json",
        run_json or f"runtime/latest_mt5_tester_{suffix}_run.json",
        "--output-md",
        run_md or f"runtime/latest_mt5_tester_{suffix}_run.md",
        "--optimization-output-json",
        report_json or f"runtime/latest_mt5_{suffix}_report.json",
        "--optimization-output-md",
        report_md or f"runtime/latest_mt5_{suffix}_report.md",
    ]
    if from_date:
        command.extend(["--from-date", from_date])
    if to_date:
        command.extend(["--to-date", to_date])
    if forward_mode:
        command.extend(["--forward-mode", forward_mode])
    if generated_at:
        command.extend(["--csv-modified-after", generated_at])
    return shlex.join(command)


def static_config_execute_command(
    *,
    config_path: str,
    report_name: str,
    timeout_seconds: int,
    since_minutes: float,
    min_closed: int,
    from_date: str = "",
    to_date: str = "",
    forward_mode: str = "",
    output_suffix: str = "",
    run_json: str = "",
    run_md: str = "",
    report_json: str = "",
    report_md: str = "",
) -> str:
    suffix = output_suffix or static_config_output_suffix(config_path)
    command = [
        "python3",
        "methods/swing_eval/analysis/mt5_tester_run.py",
        "--config",
        config_path,
        "--report-name",
        report_name,
        "--timeout-seconds",
        str(timeout_seconds),
        "--since-minutes",
        str(since_minutes),
        "--min-closed",
        str(min_closed),
        "--sync-expert-parameters-set",
        "--allow-stale-compile",
        "--output-json",
        run_json or f"runtime/latest_mt5_tester_{suffix}_run.json",
        "--output-md",
        run_md or f"runtime/latest_mt5_tester_{suffix}_run.md",
        "--optimization-output-json",
        report_json or f"runtime/latest_mt5_{suffix}_report.json",
        "--optimization-output-md",
        report_md or f"runtime/latest_mt5_{suffix}_report.md",
    ]
    if from_date:
        command.extend(["--from-date", from_date])
    if to_date:
        command.extend(["--to-date", to_date])
    if forward_mode:
        command.extend(["--forward-mode", forward_mode])
    return shlex.join(command)


def static_strategy_config_state_from_queue(queue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    state = queue.get("static_strategy_config_state")
    if isinstance(state, dict):
        result.update(
            {
                str(config): row if isinstance(row, dict) else {}
                for config, row in state.items()
            }
        )
    candidate_state = queue.get("static_candidate_state")
    if isinstance(candidate_state, dict):
        for label, row in candidate_state.items():
            if not isinstance(row, dict):
                row = {}
            text_label = str(label)
            result[text_label] = row
            candidate = DEFAULT_STATIC_CANDIDATE_CONFIGS.get(text_label, {})
            for alias in (
                candidate.get("config", ""),
                candidate.get("queue_id", ""),
            ):
                if alias and alias not in result:
                    result[str(alias)] = row
    entries = queue.get("entries") if isinstance(queue.get("entries"), list) else []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if not str(entry.get("id") or "").startswith("static_"):
            continue
        steps = entry.get("steps") if isinstance(entry.get("steps"), list) else []
        first_step = next((step for step in steps if isinstance(step, dict)), {})
        config = str(first_step.get("config") or entry.get("source_json") or "")
        label = str(first_step.get("label") or "")
        entry_id = str(entry.get("id") or "")
        if not config and not label and not entry_id:
            continue
        state = {
            "manual_run_start_after": entry.get("manual_run_start_after")
            or entry.get("runner_generated_at")
            or entry.get("generated_at")
            or "",
        }
        for key in (config, label, entry_id):
            if key and key not in result:
                result[key] = state
    return result


def manual_run_start_state_from_queue(queue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    stored = queue.get("manual_run_start_state")
    if isinstance(stored, dict):
        for key, row in stored.items():
            if isinstance(row, dict):
                result[str(key)] = row
    entries = queue.get("entries") if isinstance(queue.get("entries"), list) else []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id") or "")
        source_json = str(entry.get("source_json") or "")
        start_after = str(
            entry.get("manual_run_start_after")
            or entry.get("runner_generated_at")
            or entry.get("generated_at")
            or ""
        )
        if not start_after:
            continue
        state = {
            "manual_run_start_after": start_after,
            "source_json": source_json,
            "marked": entry.get("manual_run_start_marked", False),
        }
        for key in (entry_id, source_json):
            if key and key not in result:
                result[key] = state
        if entry_id.startswith("static_"):
            steps = entry.get("steps") if isinstance(entry.get("steps"), list) else []
            first_step = next((step for step in steps if isinstance(step, dict)), {})
            for key in (
                str(first_step.get("config") or ""),
                str(first_step.get("label") or ""),
            ):
                if key and key not in result:
                    result[key] = state
    return result


def manual_run_start_after_from_state(
    state: dict[str, dict[str, Any]] | None,
    *keys: str,
    require_marked: bool = False,
) -> str:
    rows = state if isinstance(state, dict) else {}
    for key in keys:
        if not key:
            continue
        row = rows.get(str(key), {})
        if isinstance(row, dict) and row.get("manual_run_start_after"):
            if require_marked and row.get("marked") is not True:
                continue
            return str(row.get("manual_run_start_after") or "")
    return ""


def static_strategy_config_entry(
    *,
    config_path: str,
    order: int,
    generated_at: str,
    manual_run_start_after: str = "",
    manual_run_start_marked: bool = False,
    mt5_root: str | Path | None = None,
    timeout_seconds: int = 7200,
    since_minutes: float = 240.0,
    min_closed: int = 100,
    overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    source = Path(config_path)
    metadata = tester_config_plan_metadata(source)
    override = overrides if isinstance(overrides, dict) else {}
    start_after = manual_run_start_after or generated_at
    if not source.exists():
        return {
            "order": order,
            "id": override.get("queue_id") or static_config_queue_id(config_path),
            "title": override.get("title") or static_config_title(config_path, metadata),
            "source_json": config_path,
            "available": False,
            "source_available": False,
            "stale_reasons": ["static_config_missing"],
            "refresh_command_text": "",
            "generated_at": generated_at,
            "runner_generated_at": start_after,
            "manual_run_start_after": start_after,
            "manual_run_start_marked": manual_run_start_marked,
            "step_count": 0,
            "steps": [],
            "collect_ready": False,
            "collect_status": "static_config_missing",
            "collect_reason": "static_config_missing",
            "collect_blocking_reasons": ["static_config_missing"],
            "collect_next_action": "fix_static_strategy_tester_config",
            "collect_csv_count": 0,
            "collect_modified_after": start_after,
            "collect_readiness_steps": [],
        }
    label = override.get("label") or static_config_label(config_path)
    report_name = override.get("report_name") or metadata.get("report") or f"Tester\\{source.stem}"
    from_date = override.get("from_date") or metadata.get("base_from_date", "")
    to_date = override.get("to_date") or metadata.get("base_to_date", "")
    forward_mode = override.get("forward_mode") or metadata.get("forward_mode", "")
    suffix = override.get("output_suffix") or static_config_output_suffix(config_path)
    run_json = override.get("run_json") or f"runtime/latest_mt5_tester_{suffix}_run.json"
    run_md = override.get("run_md") or f"runtime/latest_mt5_tester_{suffix}_run.md"
    report_json = override.get("report_json") or f"runtime/latest_mt5_{suffix}_report.json"
    report_md = override.get("report_md") or f"runtime/latest_mt5_{suffix}_report.md"
    step = manual_strategy_tester_step(
        {
            "label": label,
            "config": config_path,
            "expert": metadata.get("expert", ""),
            "symbol": metadata.get("symbol", ""),
            "period": metadata.get("period", ""),
            "model": metadata.get("model", ""),
            "optimization": metadata.get("optimization", ""),
            "base_from_date": metadata.get("base_from_date", ""),
            "base_to_date": metadata.get("base_to_date", ""),
            "effective_from_date": from_date,
            "effective_to_date": to_date,
            "forward_mode": metadata.get("forward_mode", ""),
            "forward_date": metadata.get("forward_date", ""),
            "effective_forward_mode": forward_mode,
            "expert_parameters": metadata.get("expert_parameters", ""),
            "report_name": report_name,
            "run_json": run_json,
            "report_json": report_json,
        },
        order=1,
    )
    steps = apply_manual_run_start_to_steps(
        [attach_step_pass_budget(step)],
        manual_run_start_after=start_after,
        marked=manual_run_start_marked,
    )
    readiness = static_manual_collect_readiness(
        steps=[step],
        mt5_root=mt5_root or default_mt5_root(),
        modified_after=start_after,
        since_minutes=since_minutes,
        min_closed=min_closed,
    )
    execute_command = ""
    if override:
        execute_command = static_config_execute_command(
            config_path=config_path,
            report_name=report_name,
            timeout_seconds=timeout_seconds,
            since_minutes=since_minutes,
            min_closed=min_closed,
            from_date=from_date,
            to_date=to_date,
            forward_mode=forward_mode,
            output_suffix=suffix,
            run_json=run_json,
            run_md=run_md,
            report_json=report_json,
            report_md=report_md,
        )
    return {
        "order": order,
        "id": override.get("queue_id") or static_config_queue_id(config_path),
        "title": override.get("title") or static_config_title(config_path, metadata),
        "source_json": config_path,
        "available": True,
        "source_available": True,
        "current_for_execution": True,
        "gate_stale_reason": "",
        "stale_reasons": [],
        "refresh_command_text": "",
        "generated_at": generated_at,
        "runner_generated_at": start_after,
        "promotion_generated_at": "",
        "runner_promotion_generated_at": "",
        "current_promotion_generated_at": "",
        "promotion_decision": "",
        "current_promotion_decision": "",
        "selected_action_present": "",
        "selected_action_current": "",
        "selected_action_mismatches": [],
        "target": "static_strategy_tester_config",
        "kind": "static_strategy_tester_config",
        "focus_side": "",
        "mode": "",
        "evidence_state": "manual_strategy_tester_plan",
        "dry_run": True,
        "manual_run_start_after": start_after,
        "manual_run_start_marked": manual_run_start_marked,
        "step_count": 1,
        "steps": steps,
        "execute_command_text": execute_command,
        "collect_only_command_text": static_config_collect_command(
            config_path=config_path,
            report_name=report_name,
            generated_at=start_after,
            timeout_seconds=timeout_seconds,
            since_minutes=since_minutes,
            min_closed=min_closed,
            from_date=from_date if override else "",
            to_date=to_date if override else "",
            forward_mode=forward_mode if override else "",
            output_suffix=suffix,
            run_json=run_json,
            run_md=run_md,
            report_json=report_json,
            report_md=report_md,
        ),
        "collect_only_note": (
            "Run this static MT5 Strategy Tester config first, then collect the named Tester report "
            "and fresh Agent CSV."
        ),
        "collect_ready": readiness.get("ready", False),
        "collect_status": readiness.get("status", ""),
        "collect_reason": readiness.get("reason", ""),
        "collect_blocking_reasons": readiness.get("blocking_reasons", []),
        "collect_next_action": readiness.get("next_action", ""),
        "collect_csv_count": readiness.get("csv_count", ""),
        "collect_modified_after": readiness.get("modified_after", start_after),
        "collect_readiness_steps": apply_manual_run_start_to_steps(
            readiness.get("steps", []) if isinstance(readiness.get("steps"), list) else [],
            manual_run_start_after=start_after,
            marked=manual_run_start_marked,
            collect_status=str(readiness.get("status") or ""),
        ),
    }


def queue_entry(
    *,
    queue_id: str,
    title: str,
    source_path: str,
    payload: dict[str, Any],
    order: int,
    promotion_gate_payload: dict[str, Any] | None = None,
    manual_run_start_after_override: str = "",
) -> dict[str, Any]:
    manual_plan = (
        payload.get("manual_strategy_tester")
        if isinstance(payload.get("manual_strategy_tester"), dict)
        else {}
    )
    readiness = (
        payload.get("manual_collect_readiness")
        if isinstance(payload.get("manual_collect_readiness"), dict)
        else {}
    )
    steps = attach_steps_pass_budget(
        manual_plan.get("steps") if isinstance(manual_plan.get("steps"), list) else []
    )
    stale_reasons = []
    consistency = (
        next_action_gate_consistency(payload, promotion_gate_payload or {})
        if payload.get("target") and promotion_gate_payload
        else {}
    )
    current_for_execution = consistency.get("current_for_execution", payload.get("current_for_execution", ""))
    gate_stale_reason = str(consistency.get("gate_stale_reason", payload.get("gate_stale_reason") or ""))
    if current_for_execution is False:
        stale_reasons.append(f"current_for_execution_false:{gate_stale_reason or 'not_current'}")
    available = bool(manual_plan.get("available") and steps and not stale_reasons)
    collect_blocking_reasons = readiness.get("blocking_reasons", [])
    collect_reason = readiness.get("reason", "")
    collect_status = readiness.get("status", "not_available" if not available else "")
    collect_next_action = readiness.get("next_action", "")
    collect_ready = readiness.get("ready", False)
    manual_start_after = str(
        manual_run_start_after_override or manual_plan.get("manual_run_start_after") or ""
    )
    readiness_modified_after = str(readiness.get("modified_after") or "")
    manual_start_marked = bool(manual_run_start_after_override)
    if manual_start_marked and readiness_modified_after != manual_start_after:
        collect_ready = False
        collect_status = "manual_run_start_marked_waiting_report"
        collect_reason = "manual_run_start_marked_after_source_readiness"
        step_labels = [
            str(step.get("label") or "")
            for step in steps
            if isinstance(step, dict) and step.get("label")
        ]
        collect_blocking_reasons = [
            f"{label}:waiting_report" for label in step_labels
        ] + ["agent_csv_missing_or_stale"]
        collect_next_action = "run_manual_strategy_tester_steps_and_wait_for_reports"
    if stale_reasons:
        collect_ready = False
        collect_status = "stale_runner_artifact"
        collect_reason = ", ".join(stale_reasons)
        collect_blocking_reasons = stale_reasons
        collect_next_action = "refresh_next_action_runner_before_manual_strategy_tester"
    normalized_steps = apply_manual_run_start_to_steps(
        steps,
        manual_run_start_after=manual_start_after,
        marked=manual_start_marked,
        collect_status=str(collect_status or ""),
    )
    collect_readiness_steps = apply_manual_run_start_to_steps(
        readiness.get("steps", []) if isinstance(readiness.get("steps"), list) else [],
        manual_run_start_after=manual_start_after,
        marked=manual_start_marked,
        collect_status=str(collect_status or ""),
    )
    return {
        "order": order,
        "id": queue_id,
        "title": title,
        "source_json": source_path,
        "available": available,
        "source_available": bool(manual_plan.get("available") and steps),
        "current_for_execution": current_for_execution,
        "gate_stale_reason": gate_stale_reason,
        "stale_reasons": stale_reasons,
        "refresh_command_text": refresh_command_text(queue_id, source_path) if stale_reasons else "",
        "generated_at": payload.get("generated_at", ""),
        "runner_generated_at": payload.get("runner_generated_at") or payload.get("generated_at", ""),
        "promotion_generated_at": payload.get("promotion_generated_at", ""),
        "runner_promotion_generated_at": consistency.get(
            "runner_promotion_generated_at",
            payload.get("runner_promotion_generated_at", ""),
        ),
        "current_promotion_generated_at": consistency.get(
            "current_promotion_generated_at",
            payload.get("current_promotion_generated_at", ""),
        ),
        "promotion_decision": payload.get("promotion_decision", ""),
        "current_promotion_decision": consistency.get(
            "current_promotion_decision",
            payload.get("current_promotion_decision", ""),
        ),
        "selected_action_present": consistency.get(
            "selected_action_present",
            payload.get("selected_action_present", ""),
        ),
        "selected_action_current": consistency.get(
            "selected_action_current",
            payload.get("selected_action_current", ""),
        ),
        "selected_action_mismatches": consistency.get(
            "selected_action_mismatches",
            payload.get("selected_action_mismatches", []),
        ),
        "target": payload.get("target", ""),
        "kind": payload.get("kind", ""),
        "focus_side": payload.get("focus_side", ""),
        "mode": payload.get("mode", ""),
        "evidence_state": payload.get("evidence_state", ""),
        "dry_run": payload.get("dry_run", ""),
        "manual_run_start_after": manual_start_after,
        "manual_run_start_marked": manual_start_marked,
        "step_count": len(steps),
        "steps": normalized_steps,
        "execute_command_text": str(
            payload.get("execute_command_text")
            or (
                payload.get("execution_hints", {}).get("execute_command_text")
                if isinstance(payload.get("execution_hints"), dict)
                else ""
            )
            or ""
        ),
        "collect_only_command_text": command_text(
            manual_plan,
            manual_run_start_after=manual_start_after,
        ),
        "collect_only_note": manual_plan.get("collect_only_note", ""),
        "collect_ready": collect_ready,
        "collect_status": collect_status,
        "collect_reason": collect_reason,
        "collect_blocking_reasons": collect_blocking_reasons,
        "collect_next_action": collect_next_action,
        "collect_csv_count": readiness.get("csv_count", ""),
        "collect_modified_after": (
            manual_start_after
            if manual_start_marked
            else readiness.get("modified_after", manual_start_after)
        ),
        "collect_readiness_steps": collect_readiness_steps,
    }


def build_queue(
    *,
    back_forward_run: str,
    sell_next_action_run: str,
    buy_next_action_run: str,
    promotion_gate: str = "",
    mt5_root: str | Path | None = None,
    wine_path: str | Path | None = None,
    queue_json: str = DEFAULT_OUTPUT_JSON,
    generated_at: str | None = None,
    static_strategy_configs: list[str] | tuple[str, ...] | None = None,
    static_candidate_labels: list[str] | tuple[str, ...] | None = None,
    static_strategy_config_state: dict[str, dict[str, Any]] | None = None,
    manual_run_start_state: dict[str, dict[str, Any]] | None = None,
    manual_run_start_after_override: str = "",
) -> dict[str, Any]:
    promotion_gate_payload = load_json(promotion_gate) if promotion_gate else {}
    generated = generated_at or datetime.now().strftime(TIME_FORMAT)
    manual_state = manual_run_start_state or {}
    marked_start_after = str(manual_run_start_after_override or "")
    entries = [
        queue_entry(
            queue_id="back_forward",
            title="Backtest + Forward Test",
            source_path=back_forward_run,
            payload=load_json(back_forward_run),
            order=1,
            promotion_gate_payload=promotion_gate_payload,
            manual_run_start_after_override=marked_start_after
            or manual_run_start_after_from_state(
                manual_state,
                "back_forward",
                back_forward_run,
                require_marked=True,
            ),
        ),
        queue_entry(
            queue_id="score_weight_sell",
            title="SELL Score Weight Sample Collection",
            source_path=sell_next_action_run,
            payload=load_json(sell_next_action_run),
            order=2,
            promotion_gate_payload=promotion_gate_payload,
            manual_run_start_after_override=marked_start_after
            or manual_run_start_after_from_state(
                manual_state,
                "score_weight_sell",
                sell_next_action_run,
                require_marked=True,
            ),
        ),
        queue_entry(
            queue_id="score_weight_buy",
            title="BUY Score Weight Sample Collection",
            source_path=buy_next_action_run,
            payload=load_json(buy_next_action_run),
            order=3,
            promotion_gate_payload=promotion_gate_payload,
            manual_run_start_after_override=marked_start_after
            or manual_run_start_after_from_state(
                manual_state,
                "score_weight_buy",
                buy_next_action_run,
                require_marked=True,
            ),
        ),
    ]
    static_configs = unique_texts([str(item) for item in (static_strategy_configs or [])])
    static_candidates = unique_texts([str(item) for item in (static_candidate_labels or [])])
    static_state = static_strategy_config_state or {}
    for config_path in static_configs:
        state = static_state.get(config_path, {}) if isinstance(static_state, dict) else {}
        state_start_after = str(state.get("manual_run_start_after") or "")
        marked_state_start_after = manual_run_start_after_from_state(
            manual_state,
            config_path,
            static_config_queue_id(config_path),
            require_marked=True,
        )
        manual_state_start_after = manual_run_start_after_from_state(
            manual_state,
            config_path,
            static_config_queue_id(config_path),
        )
        start_after = (
            marked_start_after
            or marked_state_start_after
            or state_start_after
            or manual_state_start_after
        )
        entries.append(
            static_strategy_config_entry(
                config_path=config_path,
                order=len(entries) + 1,
                generated_at=generated,
                manual_run_start_after=start_after,
                manual_run_start_marked=bool(marked_start_after or marked_state_start_after),
                mt5_root=mt5_root,
            )
        )
    for candidate_label in static_candidates:
        candidate = DEFAULT_STATIC_CANDIDATE_CONFIGS.get(candidate_label, {})
        config_path = str(candidate.get("config") or "")
        state = static_state.get(candidate_label, {}) if isinstance(static_state, dict) else {}
        queue_id = str(candidate.get("queue_id") or "")
        if not config_path:
            entries.append(
                {
                    "order": len(entries) + 1,
                    "id": f"static_{candidate_label}",
                    "title": f"{candidate_label} MT5 Optimization",
                    "source_json": "",
                    "available": False,
                    "source_available": False,
                    "stale_reasons": ["static_candidate_label_unknown"],
                    "refresh_command_text": "",
                    "generated_at": generated,
                    "runner_generated_at": generated,
                    "manual_run_start_after": marked_start_after or generated,
                    "manual_run_start_marked": bool(marked_start_after),
                    "step_count": 0,
                    "steps": [],
                    "collect_ready": False,
                    "collect_status": "static_candidate_label_unknown",
                    "collect_reason": "static_candidate_label_unknown",
                    "collect_blocking_reasons": ["static_candidate_label_unknown"],
                    "collect_next_action": "fix_static_candidate_label",
                    "collect_csv_count": 0,
                    "collect_modified_after": marked_start_after or generated,
                    "collect_readiness_steps": [],
                }
            )
            continue
        state_start_after = str(state.get("manual_run_start_after") or "")
        marked_state_start_after = manual_run_start_after_from_state(
            manual_state,
            candidate_label,
            config_path,
            queue_id,
            require_marked=True,
        )
        manual_state_start_after = manual_run_start_after_from_state(
            manual_state,
            candidate_label,
            config_path,
            queue_id,
        )
        start_after = (
            marked_start_after
            or marked_state_start_after
            or state_start_after
            or manual_state_start_after
        )
        entries.append(
            static_strategy_config_entry(
                config_path=config_path,
                order=len(entries) + 1,
                generated_at=generated,
                manual_run_start_after=start_after,
                manual_run_start_marked=bool(marked_start_after or marked_state_start_after),
                mt5_root=mt5_root,
                overrides=candidate,
            )
        )
    available_entries = [entry for entry in entries if entry.get("available") is True]
    stale_entries = [entry for entry in entries if entry.get("stale_reasons")]
    completed_entries = [entry for entry in available_entries if entry_collect_completed(entry)]
    ready_entries = [
        entry
        for entry in available_entries
        if entry.get("collect_ready") is True and not entry_collect_completed(entry)
    ]
    waiting_entries = [
        entry
        for entry in available_entries
        if entry.get("collect_ready") is not True and not entry_collect_completed(entry)
    ]
    step_count = sum(int(entry.get("step_count") or 0) for entry in available_entries)
    blocking_reasons = []
    for entry in waiting_entries:
        reasons = entry.get("collect_blocking_reasons")
        if isinstance(reasons, list):
            blocking_reasons.extend(str(reason) for reason in reasons if reason not in (None, ""))
    for entry in stale_entries:
        reasons = entry.get("stale_reasons")
        if isinstance(reasons, list):
            blocking_reasons.extend(
                f"{entry.get('id', '')}:{reason}" for reason in reasons if reason not in (None, "")
            )
    if not available_entries:
        next_action = "refresh_mt5_runner_artifacts"
        status = "missing_manual_strategy_tester_plans"
    elif stale_entries:
        next_action = "refresh_stale_runner_artifacts"
        status = "stale_runner_artifacts"
    elif waiting_entries:
        next_action = "run_manual_strategy_tester_steps_and_wait_for_reports"
        status = "waiting_for_manual_strategy_tester_results"
    elif ready_entries:
        next_action = "run_collect_only_commands"
        status = "ready_to_collect_all"
    elif completed_entries:
        next_action = "refresh_mt5_tester_status_after_collect"
        status = "manual_collect_complete"
    else:
        next_action = "inspect_manual_test_queue"
        status = "inspect_manual_test_queue"
    execution_checklist = build_execution_checklist(
        available_entries,
        mt5_root=mt5_root,
        wine_path=wine_path,
    )
    operation_cards = build_operation_cards(execution_checklist, available_entries)
    step_summary = manual_step_summary(execution_checklist)
    mark_command = manual_run_start_mark_command_text(
        back_forward_run=back_forward_run,
        sell_next_action_run=sell_next_action_run,
        buy_next_action_run=buy_next_action_run,
        promotion_gate=promotion_gate,
        queue_json=queue_json,
        static_strategy_configs=static_configs,
        static_candidate_labels=static_candidates,
    )
    manual_start_state_payload = {
        str(entry.get("id") or ""): {
            "manual_run_start_after": entry.get("manual_run_start_after", ""),
            "source_json": entry.get("source_json", ""),
            "marked": bool(entry.get("manual_run_start_marked") or marked_start_after),
        }
        for entry in entries
        if isinstance(entry, dict) and entry.get("id")
    }
    manual_start_marked_count = sum(
        1
        for row in manual_start_state_payload.values()
        if isinstance(row, dict) and row.get("marked") is True
    )
    manual_start_after_values = unique_texts(
        [
            str(row.get("manual_run_start_after") or "")
            for row in manual_start_state_payload.values()
            if isinstance(row, dict) and row.get("manual_run_start_after")
        ]
    )
    handoff = operator_handoff(
        status=status,
        next_action=next_action,
        next_launch_step=step_summary["next_launch_step"],
        step_summary=step_summary,
        available_entries=available_entries,
        ready_entries=ready_entries,
        waiting_entries=waiting_entries,
        completed_entries=completed_entries,
        stale_entries=stale_entries,
        queue_json=queue_json,
        manual_run_start_mark_command=mark_command,
    )
    return {
        "ok": bool(available_entries) and not stale_entries,
        "generated_at": generated,
        "promotion_gate_path": promotion_gate,
        "promotion_gate_generated_at": promotion_gate_payload.get("generated_at", ""),
        "promotion_gate_decision": promotion_gate_payload.get("decision", ""),
        "promotion_gate_loaded": bool(promotion_gate_payload),
        "static_strategy_configs": static_configs,
        "static_strategy_config_count": len(static_configs),
        "static_candidate_labels": static_candidates,
        "static_candidate_label_count": len(static_candidates),
        "static_strategy_config_state": {
            config_path: {
                "manual_run_start_after": next(
                    (
                        entry.get("manual_run_start_after", "")
                        for entry in entries
                        if entry.get("source_json") == config_path
                    ),
                    generated,
                )
            }
            for config_path in static_configs
        },
        "static_candidate_state": {
            label: {
                "manual_run_start_after": next(
                    (
                        entry.get("manual_run_start_after", "")
                        for entry in entries
                        if entry.get("id") == DEFAULT_STATIC_CANDIDATE_CONFIGS.get(label, {}).get("queue_id")
                    ),
                    generated,
                )
            }
            for label in static_candidates
        },
        "manual_run_start_marked": bool(marked_start_after) or manual_start_marked_count > 0,
        "manual_run_start_marked_this_run": bool(marked_start_after),
        "manual_run_start_after_override": marked_start_after,
        "manual_run_start_state_count": len(manual_start_state_payload),
        "manual_run_start_state_marked_count": manual_start_marked_count,
        "manual_run_start_preserved": not bool(marked_start_after) and manual_start_marked_count > 0,
        "manual_run_start_effective_after_values": manual_start_after_values,
        "manual_run_start_state": manual_start_state_payload,
        "manual_run_start_mark_command_text": mark_command,
        "status": status,
        "next_action": next_action,
        "entry_count": len(available_entries),
        "total_entry_count": len(entries),
        "stale_entry_count": len(stale_entries),
        "step_count": step_count,
        "ready_to_collect_count": len(ready_entries),
        "completed_count": len(completed_entries),
        "completed_entry_count": len(completed_entries),
        "completed_entry_ids": [str(entry.get("id") or "") for entry in completed_entries],
        "waiting_count": len(waiting_entries),
        "waiting_entry_count": len(waiting_entries),
        "step_report_ready_count": step_summary["step_report_ready_count"],
        "step_collect_ready_count": step_summary["step_collect_ready_count"],
        "step_waiting_report_count": step_summary["step_waiting_report_count"],
        "step_launch_needed_count": step_summary["step_launch_needed_count"],
        "step_report_ready_ids": step_summary["step_report_ready_ids"],
        "step_collect_ready_ids": step_summary["step_collect_ready_ids"],
        "step_waiting_report_ids": step_summary["step_waiting_report_ids"],
        "step_launch_needed_ids": step_summary["step_launch_needed_ids"],
        "next_launch_step": step_summary["next_launch_step"],
        "next_queue_step": handoff.get("next_queue_step", ""),
        "next_mt5_step": handoff.get("next_mt5_step", {}),
        "quick_input": handoff.get("quick_input", {}),
        "next_quick_input": handoff.get("next_quick_input", {}),
        "next_step_operator_summary": handoff.get("next_step_operator_summary", ""),
        "next_mt5_step_summary": handoff.get("next_mt5_step_summary", ""),
        "next_step_summary": handoff.get("next_step_summary", ""),
        "next_step_collect_filter_summary": handoff.get(
            "next_step_collect_filter_summary",
            "",
        ),
        "collect_check_command_text": handoff.get("collect_check_command_text", ""),
        "collect_dry_run_command_text": handoff.get("collect_dry_run_command_text", ""),
        "collect_execute_command_text": handoff.get("collect_execute_command_text", ""),
        "collect_execute_and_refresh_analysis_command_text": handoff.get(
            "collect_execute_and_refresh_analysis_command_text",
            "",
        ),
        "collect_execute_and_refresh_all_command_text": handoff.get(
            "collect_execute_and_refresh_all_command_text",
            "",
        ),
        "collect_execute_and_refresh_full_analysis_command_text": handoff.get(
            "collect_execute_and_refresh_full_analysis_command_text",
            "",
        ),
        "operator_handoff": handoff,
        "all_collect_ready": bool(ready_entries) and not waiting_entries,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "strategy_tester_targets": build_strategy_tester_targets(
            execution_checklist,
            available_entries,
        ),
        "operation_cards": operation_cards,
        "execution_checklist": execution_checklist,
        "entries": entries,
    }


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def manual_run_start_guidance_lines(payload: dict[str, Any], *, command: str = "") -> list[str]:
    marked = bool(payload.get("manual_run_start_marked"))
    effective_after_values = payload.get("manual_run_start_effective_after_values")
    if not isinstance(effective_after_values, list):
        effective_after_values = []
    effective_after = ", ".join(str(item) for item in effective_after_values if str(item))
    if marked:
        note = "- Manual run start is already marked"
        if effective_after:
            note += f" for {effective_after}"
        note += "; rerun the mark command only when starting a fresh MT5 batch."
        return [note]
    if command:
        return [
            "- Before starting this step in MT5, run the mark manual run start command once so collection ignores older reports.",
        ]
    return ["- Manual run start is not marked yet; mark it before starting this MT5 batch."]


def truthy(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


STEP_CONFIG_FINGERPRINT_FIELDS = (
    "queue_id",
    "step_label",
    "config",
    "expert",
    "symbol",
    "period",
    "model",
    "from_date",
    "to_date",
    "forward",
    "forward_mode",
    "optimization",
    "optimization_label",
    "inputs",
    "report",
    "run_type",
)
STEP_RUN_FINGERPRINT_FIELDS = (
    *STEP_CONFIG_FINGERPRINT_FIELDS,
    "runner_generated_at",
    "manual_run_start_after",
    "collect_modified_after",
)
QUEUE_STEP_CONFIG_FINGERPRINT_FIELDS = STEP_CONFIG_FINGERPRINT_FIELDS
QUEUE_STEP_RUN_FINGERPRINT_FIELDS = STEP_RUN_FINGERPRINT_FIELDS


def fingerprint_payload(item: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: item.get(field, "") for field in fields}


def stable_fingerprint(item: dict[str, Any], fields: tuple[str, ...]) -> str:
    payload = fingerprint_payload(item, fields)
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def add_step_fingerprints(item: dict[str, Any]) -> dict[str, Any]:
    queue_config_fingerprint = stable_fingerprint(item, QUEUE_STEP_CONFIG_FINGERPRINT_FIELDS)
    queue_run_fingerprint = stable_fingerprint(item, QUEUE_STEP_RUN_FINGERPRINT_FIELDS)
    item["queue_step_config_fingerprint"] = queue_config_fingerprint
    item["queue_step_run_fingerprint"] = queue_run_fingerprint
    item["queue_step_fingerprint"] = queue_run_fingerprint

    source_config_fingerprint = str(item.get("source_step_config_fingerprint") or "")
    source_run_fingerprint = str(item.get("source_step_run_fingerprint") or "")
    source_fingerprint = str(item.get("source_step_fingerprint") or "")
    if source_fingerprint or source_run_fingerprint or source_config_fingerprint:
        item["step_config_fingerprint"] = source_config_fingerprint or queue_config_fingerprint
        item["step_run_fingerprint"] = (
            source_run_fingerprint or source_fingerprint or queue_run_fingerprint
        )
        item["step_fingerprint"] = (
            source_fingerprint or source_run_fingerprint or queue_run_fingerprint
        )
        item["fingerprint_scope"] = "source_step"
    else:
        item["step_config_fingerprint"] = queue_config_fingerprint
        item["step_run_fingerprint"] = queue_run_fingerprint
        item["step_fingerprint"] = queue_run_fingerprint
        item["fingerprint_scope"] = "queue_step"
    return item


def expected_artifacts_for_step(
    *,
    entry: dict[str, Any],
    step: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    return {
        "report": item.get("report", ""),
        "expected_report_artifact": item.get("expected_report_artifact", ""),
        "agent_csv": "swing_evaluation_trades.csv",
        "agent_csv_modified_after": item.get("collect_modified_after")
        or item.get("manual_run_start_after", ""),
        "run_json": step.get("run_json") or step.get("output_json") or "",
        "report_json": step.get("report_json") or step.get("optimization_output_json") or "",
        "collect_status": entry.get("collect_status", ""),
    }


def falsy(value: Any) -> bool:
    if value is False:
        return True
    if isinstance(value, str):
        return value.strip().lower() == "false"
    return False


def step_needs_launch(item: dict[str, Any]) -> bool:
    if truthy(item.get("step_report_ready")):
        return False
    if falsy(item.get("launch_needed")):
        return False
    return bool(item.get("launch_command_kind") or item.get("launch_command_text"))


def compact_step(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "order": item.get("order", ""),
        "queue_id": item.get("queue_id", ""),
        "step_label": item.get("step_label", ""),
        "purpose": strategy_tester_purpose(
            str(item.get("queue_id") or ""),
            str(item.get("step_label") or ""),
        ),
        "expert": item.get("expert", ""),
        "symbol": item.get("symbol", ""),
        "period": item.get("period", ""),
        "model": item.get("model", ""),
        "from_date": item.get("from_date", ""),
        "to_date": item.get("to_date", ""),
        "dates": item.get("dates", ""),
        "window_summary": item.get("window_summary", ""),
        "training_range": item.get("training_range", ""),
        "forward_range": item.get("forward_range", ""),
        "tester_window": item.get("tester_window", {}),
        "forward": item.get("forward", ""),
        "forward_mode": item.get("forward_mode", ""),
        "optimization": item.get("optimization", ""),
        "optimization_label": item.get("optimization_label", ""),
        "optimization_enabled": item.get("optimization_enabled", ""),
        "run_type": item.get("run_type", ""),
        "expected_report_artifact": item.get("expected_report_artifact", ""),
        "pass_budget": item.get("pass_budget", {}),
        "pass_budget_available": item.get("pass_budget_available", ""),
        "optimized_input_count": item.get("optimized_input_count", ""),
        "estimated_full_factorial_passes": item.get("estimated_full_factorial_passes", ""),
        "inputs": item.get("inputs", ""),
        "report": item.get("report", ""),
        "step_report_status": item.get("step_report_status", ""),
        "step_blocking_reason": item.get("step_blocking_reason", ""),
        "launch_needed": item.get("launch_needed", ""),
        "launch_command_kind": item.get("launch_command_kind", ""),
        "launch_command_text": item.get("launch_command_text", ""),
        "config": item.get("config", ""),
        "mt5_config": item.get("mt5_config", ""),
        "manual_run_start_after": item.get("manual_run_start_after", ""),
        "collect_modified_after": item.get("collect_modified_after", ""),
        "step_fingerprint": item.get("step_fingerprint", ""),
        "step_config_fingerprint": item.get("step_config_fingerprint", ""),
        "step_run_fingerprint": item.get("step_run_fingerprint", ""),
        "fingerprint_scope": item.get("fingerprint_scope", ""),
        "source_step_fingerprint": item.get("source_step_fingerprint", ""),
        "source_step_config_fingerprint": item.get("source_step_config_fingerprint", ""),
        "source_step_run_fingerprint": item.get("source_step_run_fingerprint", ""),
        "queue_step_fingerprint": item.get("queue_step_fingerprint", ""),
        "queue_step_config_fingerprint": item.get("queue_step_config_fingerprint", ""),
        "queue_step_run_fingerprint": item.get("queue_step_run_fingerprint", ""),
        "expected_artifacts": item.get("expected_artifacts", {}),
    }


def split_dates(dates: object) -> tuple[str, str]:
    text = str(dates or "").strip()
    if "->" not in text:
        return "", ""
    start, end = text.split("->", 1)
    return start.strip(), end.strip()


def strategy_tester_quick_input(item: dict[str, Any]) -> dict[str, Any]:
    if not item:
        return {}
    queue_id = str(item.get("queue_id") or "")
    step_label = str(item.get("step_label") or "")
    from_date = str(item.get("from_date") or "")
    to_date = str(item.get("to_date") or "")
    if not (from_date or to_date):
        from_date, to_date = split_dates(item.get("dates"))
    return {
        "queue_step": f"{queue_id}/{step_label}".strip("/"),
        "purpose": item.get("purpose") or strategy_tester_purpose(queue_id, step_label),
        "expert": item.get("expert", ""),
        "symbol": item.get("symbol", ""),
        "period": item.get("period", ""),
        "model": item.get("model", ""),
        "from_date": from_date,
        "to_date": to_date,
        "dates": item.get("dates", ""),
        "window_summary": item.get("window_summary", ""),
        "training_range": item.get("training_range", ""),
        "forward_range": item.get("forward_range", ""),
        "tester_window": item.get("tester_window", {}),
        "forward": item.get("forward", ""),
        "forward_mode": item.get("forward_mode", ""),
        "optimization": item.get("optimization", ""),
        "optimization_label": optimization_label_for_item(item),
        "optimization_enabled": item.get("optimization_enabled", ""),
        "inputs": item.get("inputs", ""),
        "report": item.get("report", ""),
        "run_type": item.get("run_type", ""),
        "expected_report_artifact": item.get("expected_report_artifact", ""),
        "estimated_full_factorial_passes": item.get("estimated_full_factorial_passes", ""),
        "optimized_input_count": item.get("optimized_input_count", ""),
        "step_fingerprint": item.get("step_fingerprint", ""),
        "step_config_fingerprint": item.get("step_config_fingerprint", ""),
        "step_run_fingerprint": item.get("step_run_fingerprint", ""),
        "fingerprint_scope": item.get("fingerprint_scope", ""),
        "source_step_fingerprint": item.get("source_step_fingerprint", ""),
        "queue_step_fingerprint": item.get("queue_step_fingerprint", ""),
        "launch_kind": item.get("launch_command_kind", ""),
        "workspace_config": item.get("config", ""),
        "mt5_config": item.get("mt5_config", ""),
        "manual_run_start_after": item.get("manual_run_start_after", ""),
    }


def operator_step_summary(step: dict[str, Any]) -> str:
    if not step:
        return ""
    queue_step = f"{step.get('queue_id', '')}/{step.get('step_label', '')}".strip("/")
    parts = [
        str(step.get("purpose") or strategy_tester_purpose(str(step.get("queue_id") or ""), str(step.get("step_label") or ""))),
        queue_step,
        str(step.get("symbol") or ""),
        str(step.get("period") or ""),
        str(step.get("dates") or ""),
        f"Forward={step.get('forward', '')}",
        f"Optimization={optimization_label_for_item(step)}",
        f"Window={step.get('window_summary', '')}",
        f"Inputs={step.get('inputs', '')}",
        f"Report={step.get('report', '')}",
        f"Expected={step.get('expected_report_artifact', '')}",
        f"Passes={step.get('estimated_full_factorial_passes', '')}",
        f"StartAfter={step.get('manual_run_start_after', '')}",
        f"Fingerprint={step.get('step_fingerprint', '')}",
    ]
    return "; ".join(part for part in parts if part and not part.endswith("="))


def operator_collect_filter_summary(step: dict[str, Any]) -> str:
    if not step:
        return ""
    artifacts = step.get("expected_artifacts") if isinstance(step.get("expected_artifacts"), dict) else {}
    modified_after = (
        artifacts.get("agent_csv_modified_after")
        or step.get("collect_modified_after")
        or step.get("manual_run_start_after")
        or ""
    )
    parts = [
        f"Report={artifacts.get('report') or step.get('report', '')}",
        f"Expected={artifacts.get('expected_report_artifact') or step.get('expected_report_artifact', '')}",
        f"AgentCSV={artifacts.get('agent_csv') or 'swing_evaluation_trades.csv'}",
        f"ModifiedAfter={modified_after}",
        f"RunJSON={artifacts.get('run_json', '')}",
        f"ReportJSON={artifacts.get('report_json', '')}",
    ]
    return "; ".join(part for part in parts if part and not part.endswith("="))


QUICK_INPUT_FIELDS = (
    ("purpose", "Purpose"),
    ("queue_step", "Queue step"),
    ("expert", "Expert"),
    ("symbol", "Symbol"),
    ("period", "Period"),
    ("model", "Model"),
    ("from_date", "From"),
    ("to_date", "To"),
    ("forward", "Forward"),
    ("window_summary", "Window"),
    ("forward_mode", "ForwardMode"),
    ("optimization_label", "Optimization"),
    ("estimated_full_factorial_passes", "Passes"),
    ("inputs", "Inputs"),
    ("report", "Report"),
    ("expected_report_artifact", "Expected output"),
    ("manual_run_start_after", "Start after"),
    ("step_fingerprint", "Run fingerprint"),
    ("launch_kind", "Launch kind"),
)


def format_quick_input_rows(quick_input: object) -> list[str]:
    if not isinstance(quick_input, dict) or not quick_input:
        return ["| - |  |"]
    rows: list[str] = []
    for key, label in QUICK_INPUT_FIELDS:
        value = quick_input.get(key, "")
        if value in (None, "") and key == "forward_mode":
            continue
        rows.append(f"| {markdown_cell(label)} | {markdown_cell(value)} |")
    return rows if rows else ["| - |  |"]


def pass_budget_value(item: dict[str, Any], key: str) -> Any:
    budget = item.get("pass_budget") if isinstance(item.get("pass_budget"), dict) else {}
    return item.get(key, budget.get(key, ""))


def format_pass_budget_rows(checklist: object) -> list[str]:
    if not isinstance(checklist, list) or not checklist:
        return ["| - |  |  |  |  |  |  |  |  |"]
    rows: list[str] = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        budget = item.get("pass_budget") if isinstance(item.get("pass_budget"), dict) else {}
        optimized_names = budget.get("optimized_input_names")
        if not isinstance(optimized_names, list):
            optimized_names = []
        rows.append(
            f"| {item.get('order', '')} | "
            f"{markdown_cell(item.get('queue_id', ''))}/{markdown_cell(item.get('step_label', ''))} | "
            f"{markdown_cell(optimization_label_for_item(item))} | "
            f"{markdown_cell(item.get('inputs', ''))} | "
            f"{budget.get('available', '')} | "
            f"{markdown_cell(pass_budget_value(item, 'optimized_input_count'))} | "
            f"{markdown_cell(pass_budget_value(item, 'estimated_full_factorial_passes'))} | "
            f"{markdown_cell(budget.get('set_file', ''))} | "
            f"{markdown_cell(', '.join(str(name) for name in optimized_names))} | "
            f"{markdown_cell(budget.get('note') or budget.get('reason') or '')} |"
        )
    return rows if rows else ["| - |  |  |  |  |  |  |  |  |"]


def manual_collect_command_text(
    queue_json: str,
    *,
    execute: bool = False,
    refresh_strategy_tester_analysis: bool = False,
    refresh_post_collect_analysis: bool = False,
) -> str:
    execute_flag = " --execute" if execute else ""
    refresh_flag = " --refresh-strategy-tester-analysis" if refresh_strategy_tester_analysis else ""
    full_refresh_flag = " --refresh-post-collect-analysis" if refresh_post_collect_analysis else ""
    if Path(queue_json).name == Path(DEFAULT_OUTPUT_JSON_WITH_OPTIMIZATION).name:
        output_json = DEFAULT_COLLECT_OUTPUT_JSON_WITH_OPTIMIZATION
        output_md = DEFAULT_COLLECT_OUTPUT_MD_WITH_OPTIMIZATION
    else:
        output_json = DEFAULT_COLLECT_OUTPUT_JSON
        output_md = DEFAULT_COLLECT_OUTPUT_MD
    return (
        "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
        f"--queue {shlex.quote(queue_json)}{execute_flag}{refresh_flag}{full_refresh_flag} "
        f"--output-json {output_json} "
        f"--output-md {output_md}"
    )


def manual_run_start_mark_command_text(
    *,
    back_forward_run: str,
    sell_next_action_run: str,
    buy_next_action_run: str,
    promotion_gate: str,
    queue_json: str,
    static_strategy_configs: list[str] | tuple[str, ...],
    static_candidate_labels: list[str] | tuple[str, ...],
) -> str:
    command = [
        "python3",
        "methods/swing_eval/analysis/mt5_manual_test_queue.py",
        "--mark-manual-run-start",
        "--back-forward-run",
        back_forward_run,
        "--sell-next-action-run",
        sell_next_action_run,
        "--buy-next-action-run",
        buy_next_action_run,
    ]
    if promotion_gate:
        command.extend(["--promotion-gate", promotion_gate])
    for config_path in static_strategy_configs:
        command.extend(["--include-static-config", str(config_path)])
    for label in static_candidate_labels:
        command.extend(["--include-static-candidate-label", str(label)])
    command.extend(
        [
            "--output-json",
            queue_json,
            "--output-md",
            str(Path(queue_json).with_suffix(".md")),
        ]
    )
    return shlex.join(command)


def operator_handoff(
    *,
    status: str,
    next_action: str,
    next_launch_step: dict[str, Any],
    step_summary: dict[str, Any],
    available_entries: list[dict[str, Any]],
    ready_entries: list[dict[str, Any]],
    waiting_entries: list[dict[str, Any]],
    completed_entries: list[dict[str, Any]],
    stale_entries: list[dict[str, Any]],
    queue_json: str,
    manual_run_start_mark_command: str = "",
) -> dict[str, Any]:
    no_launch_steps_remaining = bool(available_entries) and not next_launch_step and not stale_entries
    waiting_after_reports = no_launch_steps_remaining and bool(waiting_entries)
    if next_launch_step:
        state = "run_next_mt5_strategy_tester_step"
        progress_state = "mt5_step_launch_needed"
    elif waiting_after_reports:
        state = "run_collect_dry_run_to_confirm_agent_csv"
        progress_state = "reports_ready_waiting_collect_confirmation"
    elif ready_entries and not waiting_entries and not stale_entries:
        state = "run_collect_dry_run"
        progress_state = "collect_ready_all"
    elif completed_entries and not waiting_entries and not stale_entries:
        state = "collect_complete"
        progress_state = "manual_collect_complete"
    elif stale_entries:
        state = "refresh_stale_runner_artifacts"
        progress_state = "stale_runner_artifacts"
    elif not available_entries:
        state = "refresh_mt5_runner_artifacts"
        progress_state = "missing_manual_strategy_tester_plans"
    else:
        state = "inspect_manual_test_queue"
        progress_state = "inspect_manual_test_queue"
    dry_run_command = manual_collect_command_text(queue_json)
    execute_command = manual_collect_command_text(queue_json, execute=True)
    execute_and_refresh_analysis_command = manual_collect_command_text(
        queue_json,
        execute=True,
        refresh_strategy_tester_analysis=True,
    )
    execute_and_refresh_all_command = manual_collect_command_text(
        queue_json,
        execute=True,
        refresh_post_collect_analysis=True,
    )
    next_step_operator_summary = operator_step_summary(next_launch_step)
    next_step_collect_filter_summary = operator_collect_filter_summary(next_launch_step)
    next_step_quick_input = strategy_tester_quick_input(next_launch_step)
    next_queue_step = str(next_step_quick_input.get("queue_step") or "")
    return {
        "state": state,
        "progress_state": progress_state,
        "status": status,
        "next_action": next_action,
        "next_queue_step": next_queue_step,
        "next_mt5_step": next_launch_step,
        "quick_input": next_step_quick_input,
        "next_quick_input": next_step_quick_input,
        "next_step_operator_summary": next_step_operator_summary,
        "next_mt5_step_summary": next_step_operator_summary,
        "next_step_summary": next_step_operator_summary,
        "next_step_collect_filter_summary": next_step_collect_filter_summary,
        "step_report_ready_count": step_summary.get("step_report_ready_count", ""),
        "step_collect_ready_count": step_summary.get("step_collect_ready_count", ""),
        "step_waiting_report_count": step_summary.get("step_waiting_report_count", ""),
        "step_launch_needed_count": step_summary.get("step_launch_needed_count", ""),
        "step_report_ready_ids": step_summary.get("step_report_ready_ids", []),
        "step_collect_ready_ids": step_summary.get("step_collect_ready_ids", []),
        "step_waiting_report_ids": step_summary.get("step_waiting_report_ids", []),
        "step_launch_needed_ids": step_summary.get("step_launch_needed_ids", []),
        "ready_entry_ids": [str(entry.get("id", "")) for entry in ready_entries],
        "waiting_entry_ids": [str(entry.get("id", "")) for entry in waiting_entries],
        "completed_entry_ids": [str(entry.get("id", "")) for entry in completed_entries],
        "stale_entry_ids": [str(entry.get("id", "")) for entry in stale_entries],
        "collect_ready": bool(ready_entries) and not waiting_entries and not stale_entries,
        "collect_check_command_text": dry_run_command,
        "dry_run_command_text": dry_run_command,
        "collect_dry_run_command_text": dry_run_command,
        "manual_run_start_mark_command_text": manual_run_start_mark_command,
        "execute_command_text": execute_command,
        "collect_execute_command_text": execute_command,
        "execute_and_refresh_analysis_command_text": execute_and_refresh_analysis_command,
        "collect_execute_and_refresh_analysis_command_text": execute_and_refresh_analysis_command,
        "execute_and_refresh_all_command_text": execute_and_refresh_all_command,
        "collect_execute_and_refresh_all_command_text": execute_and_refresh_all_command,
        "execute_and_refresh_full_analysis_command_text": execute_and_refresh_all_command,
        "collect_execute_and_refresh_full_analysis_command_text": execute_and_refresh_all_command,
    }


def checklist_done_mark(item: dict[str, Any]) -> str:
    if truthy(item.get("step_report_ready")) or truthy(item.get("step_collect_ready")):
        return "[x]"
    return "[ ]"


def optimization_label_for_item(item: dict[str, Any]) -> str:
    label = str(item.get("optimization_label") or "")
    if label:
        return label
    optimization = str(item.get("optimization") or "")
    if optimization and optimization != "0":
        return optimization
    run_type = str(item.get("run_type") or "")
    if run_type.startswith("optimization"):
        return "Enabled"
    return "Disabled"


def operation_card_action(item: dict[str, Any]) -> str:
    if truthy(item.get("step_collect_ready")):
        return "collect_ready"
    if truthy(item.get("step_report_ready")):
        return "report_ready"
    if step_needs_launch(item):
        return "run_in_mt5"
    if str(item.get("step_report_status") or ""):
        return str(item.get("step_report_status"))
    return "inspect"


def queue_step_id(item: dict[str, Any]) -> str:
    return f"{item.get('queue_id', '')}/{item.get('step_label', '')}".strip("/")


def build_operation_cards(
    checklist: list[dict[str, Any]],
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entry_by_id = {str(entry.get("id", "")): entry for entry in entries}
    next_order = ""
    for item in checklist:
        if isinstance(item, dict) and step_needs_launch(item):
            next_order = item.get("order", "")
            break
    cards: list[dict[str, Any]] = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        queue_id = str(item.get("queue_id") or "")
        step_label = str(item.get("step_label") or "")
        entry = entry_by_id.get(queue_id, {})
        cards.append(
            {
                "order": item.get("order", ""),
                "is_next": item.get("order", "") == next_order,
                "action": operation_card_action(item),
                "purpose": strategy_tester_purpose(queue_id, step_label),
                "queue_id": queue_id,
                "step_label": step_label,
                "entry_title": item.get("entry_title", ""),
                "symbol": item.get("symbol", ""),
                "period": item.get("period", ""),
                "model": item.get("model", ""),
                "dates": item.get("dates", ""),
                "window_summary": item.get("window_summary", ""),
                "training_range": item.get("training_range", ""),
                "forward_range": item.get("forward_range", ""),
                "tester_window": item.get("tester_window", {}),
                "forward": item.get("forward", ""),
                "optimization": item.get("optimization", ""),
                "optimization_label": optimization_label_for_item(item),
                "optimization_enabled": item.get("optimization_enabled", ""),
                "run_type": item.get("run_type", ""),
                "expected_report_artifact": item.get("expected_report_artifact", ""),
                "report_expectation_note": item.get("report_expectation_note", ""),
                "inputs": item.get("inputs", ""),
                "report": item.get("report", ""),
                "start_after": item.get("manual_run_start_after", ""),
                "collect_after": entry.get("collect_modified_after", ""),
                "collect_status": entry.get("collect_status", ""),
                "collect_next_action": entry.get("collect_next_action", ""),
                "collect_command_text": entry.get("collect_only_command_text", ""),
                "step_fingerprint": item.get("step_fingerprint", ""),
                "step_config_fingerprint": item.get("step_config_fingerprint", ""),
                "step_run_fingerprint": item.get("step_run_fingerprint", ""),
                "fingerprint_scope": item.get("fingerprint_scope", ""),
                "source_step_fingerprint": item.get("source_step_fingerprint", ""),
                "source_step_config_fingerprint": item.get("source_step_config_fingerprint", ""),
                "source_step_run_fingerprint": item.get("source_step_run_fingerprint", ""),
                "queue_step_fingerprint": item.get("queue_step_fingerprint", ""),
                "queue_step_config_fingerprint": item.get("queue_step_config_fingerprint", ""),
                "queue_step_run_fingerprint": item.get("queue_step_run_fingerprint", ""),
                "expected_artifacts": item.get("expected_artifacts", {}),
                "step_report_status": item.get("step_report_status", ""),
                "step_blocking_reason": item.get("step_blocking_reason", ""),
                "launch_needed": item.get("launch_needed", ""),
                "launch_command_kind": item.get("launch_command_kind", ""),
            }
        )
    return cards


def manual_step_summary(checklist: list[dict[str, Any]]) -> dict[str, Any]:
    report_ready_count = 0
    collect_ready_count = 0
    waiting_report_count = 0
    launch_needed_count = 0
    next_launch_step: dict[str, Any] = {}
    report_ready_step_ids: list[str] = []
    collect_ready_step_ids: list[str] = []
    waiting_report_step_ids: list[str] = []
    launch_needed_step_ids: list[str] = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        if truthy(item.get("step_report_ready")):
            report_ready_count += 1
            report_ready_step_ids.append(queue_step_id(item))
        if truthy(item.get("step_collect_ready")):
            collect_ready_count += 1
            collect_ready_step_ids.append(queue_step_id(item))
        if str(item.get("step_report_status") or "") == "waiting_report":
            waiting_report_count += 1
            waiting_report_step_ids.append(queue_step_id(item))
        if step_needs_launch(item):
            launch_needed_count += 1
            launch_needed_step_ids.append(queue_step_id(item))
            if not next_launch_step:
                next_launch_step = compact_step(item)
    return {
        "step_report_ready_count": report_ready_count,
        "step_collect_ready_count": collect_ready_count,
        "step_waiting_report_count": waiting_report_count,
        "step_launch_needed_count": launch_needed_count,
        "step_report_ready_ids": report_ready_step_ids,
        "step_collect_ready_ids": collect_ready_step_ids,
        "step_waiting_report_ids": waiting_report_step_ids,
        "step_launch_needed_ids": launch_needed_step_ids,
        "next_launch_step": next_launch_step,
    }


def format_step_dates(step: dict[str, Any]) -> str:
    start = str(step.get("from_date") or "")
    end = str(step.get("to_date") or "")
    if not start and not end:
        return ""
    return f"{start} -> {end}"


def strategy_tester_purpose(queue_id: str, step_label: str) -> str:
    if queue_id == "back_forward" and step_label == "backtest":
        return "Backtest"
    if queue_id == "back_forward" and step_label == "forward":
        return "Forward Test"
    if queue_id == "score_weight_sell":
        return "SELL Score Sample"
    if queue_id == "score_weight_buy":
        return "BUY Score Sample"
    if queue_id.startswith("static_"):
        return step_label.replace("_", " ").title()
    return step_label or queue_id


def build_strategy_tester_targets(
    checklist: list[dict[str, Any]],
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entry_by_id = {str(entry.get("id", "")): entry for entry in entries}
    targets: list[dict[str, Any]] = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        queue_id = str(item.get("queue_id") or "")
        step_label = str(item.get("step_label") or "")
        entry = entry_by_id.get(queue_id, {})
        targets.append(
            {
                "order": item.get("order", ""),
                "purpose": strategy_tester_purpose(queue_id, step_label),
                "queue_id": queue_id,
                "step_label": step_label,
                "symbol": item.get("symbol", ""),
                "period": item.get("period", ""),
                "dates": item.get("dates", ""),
                "window_summary": item.get("window_summary", ""),
                "training_range": item.get("training_range", ""),
                "forward_range": item.get("forward_range", ""),
                "tester_window": item.get("tester_window", {}),
                "forward": item.get("forward", ""),
                "optimization": item.get("optimization", ""),
                "optimization_label": optimization_label_for_item(item),
                "optimization_enabled": item.get("optimization_enabled", ""),
                "run_type": item.get("run_type", ""),
                "expected_report_artifact": item.get("expected_report_artifact", ""),
                "report_expectation_note": item.get("report_expectation_note", ""),
                "inputs": item.get("inputs", ""),
                "report": item.get("report", ""),
                "start_after": item.get("manual_run_start_after", ""),
                "collect_modified_after": entry.get("collect_modified_after", ""),
                "collect_csv_count": entry.get("collect_csv_count", ""),
                "collect_status": entry.get("collect_status", ""),
                "collect_ready": entry.get("collect_ready", ""),
                "collect_next_action": entry.get("collect_next_action", ""),
                "step_report_status": item.get("step_report_status", ""),
                "step_report_ready": item.get("step_report_ready", ""),
                "step_collect_ready": item.get("step_collect_ready", ""),
                "step_blocking_reason": item.get("step_blocking_reason", ""),
                "selected_report": item.get("selected_report", ""),
                "launch_needed": item.get("launch_needed", ""),
                "auto_launch_kind": item.get("launch_command_kind", ""),
                "step_fingerprint": item.get("step_fingerprint", ""),
                "step_config_fingerprint": item.get("step_config_fingerprint", ""),
                "step_run_fingerprint": item.get("step_run_fingerprint", ""),
                "fingerprint_scope": item.get("fingerprint_scope", ""),
                "source_step_fingerprint": item.get("source_step_fingerprint", ""),
                "source_step_config_fingerprint": item.get("source_step_config_fingerprint", ""),
                "source_step_run_fingerprint": item.get("source_step_run_fingerprint", ""),
                "queue_step_fingerprint": item.get("queue_step_fingerprint", ""),
                "queue_step_config_fingerprint": item.get("queue_step_config_fingerprint", ""),
                "queue_step_run_fingerprint": item.get("queue_step_run_fingerprint", ""),
                "expected_artifacts": item.get("expected_artifacts", {}),
            }
        )
    return targets


def step_collect_state(entry: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
    if entry_collect_completed(entry):
        return {
            "step_report_status": str(entry.get("collect_status") or "already_collected"),
            "step_report_ready": True,
            "step_collect_ready": False,
            "step_blocking_reason": "",
            "selected_report": "",
            "launch_needed": False,
        }
    rows = entry.get("collect_readiness_steps") if isinstance(entry.get("collect_readiness_steps"), list) else []
    label = str(step.get("label") or "")
    report_name = str(step.get("report_name") or "")
    matched = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if label and str(row.get("label") or "") == label:
            matched = row
            break
        if report_name and str(row.get("report_name") or "") == report_name:
            matched = row
            break
    if matched:
        report_ready = matched.get("report_ready")
        return {
            "step_report_status": matched.get("report_status", ""),
            "step_report_ready": report_ready,
            "step_collect_ready": matched.get("collect_ready", ""),
            "step_blocking_reason": matched.get("blocking_reason", ""),
            "selected_report": matched.get("selected_report", ""),
            "launch_needed": report_ready is not True,
        }
    if entry.get("collect_ready") is True:
        return {
            "step_report_status": "entry_ready",
            "step_report_ready": True,
            "step_collect_ready": True,
            "step_blocking_reason": "",
            "selected_report": "",
            "launch_needed": False,
        }
    return {
        "step_report_status": "unknown",
        "step_report_ready": "",
        "step_collect_ready": "",
        "step_blocking_reason": "",
        "selected_report": "",
        "launch_needed": True,
    }


def mt5_profile_tester_config_path(config_path: object, *, mt5_root: str | Path | None = None) -> Path | None:
    config_text = str(config_path or "").strip()
    if not config_text:
        return None
    mt5 = Path(mt5_root).expanduser() if mt5_root else default_mt5_root()
    return mt5 / "MQL5" / "Profiles" / "Tester" / Path(config_text).name


def launch_command_for_step(
    step: dict[str, Any],
    *,
    runner_execute_command_text: str = "",
    mt5_root: str | Path | None = None,
    wine_path: str | Path | None = None,
) -> dict[str, Any]:
    config = mt5_profile_tester_config_path(step.get("config"), mt5_root=mt5_root)
    if config is None:
        return {
            "mt5_config": "",
            "command_kind": "",
            "launch_command": [],
            "launch_command_text": "",
            "launch_error": "missing_config",
        }
    direct_ready, direct_reason = step_static_config_matches(step)
    if not direct_ready:
        if runner_execute_command_text:
            return {
                "mt5_config": str(config),
                "command_kind": "runner_execute",
                "launch_command": [],
                "launch_command_text": runner_execute_command_text,
                "launch_error": "",
                "direct_config_reason": direct_reason,
            }
        return {
            "mt5_config": str(config),
            "command_kind": "",
            "launch_command": [],
            "launch_command_text": "",
            "launch_error": direct_reason,
            "direct_config_reason": direct_reason,
        }
    try:
        command = build_terminal_command(
            wine_path=wine_path or default_wine_path(),
            mt5_root=mt5_root or default_mt5_root(),
            config_path=config,
        )
    except (OSError, ValueError) as exc:
        return {
            "mt5_config": str(config),
            "command_kind": "",
            "launch_command": [],
            "launch_command_text": "",
            "launch_error": str(exc),
        }
    return {
        "mt5_config": str(config),
        "command_kind": "direct_config",
        "launch_command": command,
        "launch_command_text": shlex.join(command),
        "launch_error": "",
        "direct_config_reason": "static_config_matches_step",
    }


def step_static_config_matches(step: dict[str, Any]) -> tuple[bool, str]:
    config = Path(str(step.get("config") or "")).expanduser()
    if not config.exists():
        return False, "workspace_config_missing"
    try:
        metadata = tester_config_metadata(config.read_text(encoding="utf-8"))
    except OSError as exc:
        return False, f"workspace_config_unreadable:{exc}"
    expected = {
        "report": str(step.get("report_name") or ""),
        "from_date": str(step.get("from_date") or ""),
        "to_date": str(step.get("to_date") or ""),
        "forward_mode": str(step.get("forward_mode_effective") or ""),
    }
    for key, expected_value in expected.items():
        if expected_value and str(metadata.get(key) or "") != expected_value:
            return False, f"static_config_mismatch:{key}:{metadata.get(key, '')}->{expected_value}"
    return True, "static_config_matches_step"


def build_execution_checklist(
    entries: list[dict[str, Any]],
    *,
    mt5_root: str | Path | None = None,
    wine_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    checklist: list[dict[str, Any]] = []
    item_order = 1
    for entry in entries:
        steps = entry.get("steps") if isinstance(entry.get("steps"), list) else []
        for step in steps:
            if not isinstance(step, dict):
                continue
            launch = launch_command_for_step(
                step,
                runner_execute_command_text=str(entry.get("execute_command_text") or ""),
                mt5_root=mt5_root,
                wine_path=wine_path,
            )
            collect_state = step_collect_state(entry, step)
            item = {
                "order": item_order,
                "queue_id": entry.get("id", ""),
                "entry_title": entry.get("title", ""),
                "step_order": step.get("order", ""),
                "step_label": step.get("label", ""),
                "source_step_fingerprint": step.get("step_fingerprint", ""),
                "source_step_config_fingerprint": step.get("step_config_fingerprint", ""),
                "source_step_run_fingerprint": step.get("step_run_fingerprint", ""),
                "config": step.get("config", ""),
                "mt5_config": launch.get("mt5_config", ""),
                "expert": step.get("expert", ""),
                "symbol": step.get("symbol", ""),
                "period": step.get("period", ""),
                "model": step.get("model_label") or step.get("model", ""),
                "from_date": step.get("from_date", ""),
                "to_date": step.get("to_date", ""),
                "dates": format_step_dates(step),
                "window_summary": step.get("window_summary", ""),
                "training_range": step.get("training_range", ""),
                "forward_range": step.get("forward_range", ""),
                "tester_window": step.get("tester_window", {}),
                "forward": step.get("forward_label") or step.get("forward_mode_effective", ""),
                "forward_mode": step.get("forward_mode_effective", ""),
                "optimization": step.get("optimization", ""),
                "optimization_label": optimization_label_for_item(step),
                "optimization_enabled": step.get("optimization_enabled", ""),
                "run_type": step.get("run_type", ""),
                "expected_report_artifact": step.get("expected_report_artifact", ""),
                "report_expectation_note": step.get("report_expectation_note", ""),
                "pass_budget": step.get("pass_budget", {}),
                "pass_budget_available": step.get("pass_budget_available", ""),
                "optimized_input_count": step.get("optimized_input_count", ""),
                "estimated_full_factorial_passes": step.get(
                    "estimated_full_factorial_passes",
                    "",
                ),
                "inputs": step.get("expert_parameters", ""),
                "report": step.get("report_name", ""),
                **collect_state,
                "runner_generated_at": entry.get("runner_generated_at", ""),
                "manual_run_start_after": entry.get("manual_run_start_after", ""),
                "collect_modified_after": entry.get("collect_modified_after", ""),
                "launch_command_kind": launch.get("command_kind", ""),
                "launch_command": launch.get("launch_command", []),
                "launch_command_text": launch.get("launch_command_text", ""),
                "launch_error": launch.get("launch_error", ""),
                "direct_config_reason": launch.get("direct_config_reason", ""),
            }
            add_step_fingerprints(item)
            item["expected_artifacts"] = expected_artifacts_for_step(
                entry=entry,
                step=step,
                item=item,
            )
            checklist.append(item)
            item_order += 1
    return checklist


def format_operation_card_rows(cards: object) -> list[str]:
    if not isinstance(cards, list) or not cards:
        return ["| - |  |  |  |  |  |  |  |  |  |  |  |  |  |  |"]
    rows: list[str] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        next_mark = "next" if card.get("is_next") is True else ""
        rows.append(
            f"| {markdown_cell(next_mark)} | "
            f"{markdown_cell(card.get('order', ''))} | "
            f"{markdown_cell(card.get('action', ''))} | "
            f"{markdown_cell(card.get('purpose', ''))} | "
            f"{markdown_cell(card.get('queue_id', ''))}/{markdown_cell(card.get('step_label', ''))} | "
            f"{markdown_cell(card.get('symbol', ''))} | "
            f"{markdown_cell(card.get('period', ''))} | "
            f"{markdown_cell(card.get('dates', ''))} | "
            f"{markdown_cell(card.get('forward', ''))} | "
            f"{markdown_cell(card.get('window_summary', ''))} | "
            f"{markdown_cell(optimization_label_for_item(card))} | "
            f"{markdown_cell(card.get('inputs', ''))} | "
            f"{markdown_cell(card.get('report', ''))} | "
            f"{markdown_cell(card.get('collect_status', ''))} | "
            f"{markdown_cell(card.get('step_fingerprint', ''))} |"
        )
    return rows if rows else ["| - |  |  |  |  |  |  |  |  |  |  |  |  |  |"]


def format_markdown(payload: dict[str, Any]) -> str:
    queue_json = str(payload.get("queue_json") or DEFAULT_OUTPUT_JSON)
    next_step = payload.get("next_launch_step") if isinstance(payload.get("next_launch_step"), dict) else {}
    handoff = payload.get("operator_handoff") if isinstance(payload.get("operator_handoff"), dict) else {}
    quick_input = handoff.get("quick_input") if isinstance(handoff.get("quick_input"), dict) else {}
    operation_cards = (
        payload.get("operation_cards") if isinstance(payload.get("operation_cards"), list) else []
    )
    checklist = payload.get("execution_checklist") if isinstance(payload.get("execution_checklist"), list) else []
    collect_dry_run = str(handoff.get("dry_run_command_text") or manual_collect_command_text(queue_json))
    collect_execute = str(
        handoff.get("execute_command_text") or manual_collect_command_text(queue_json, execute=True)
    )
    collect_execute_and_refresh = str(
        handoff.get("execute_and_refresh_analysis_command_text")
        or manual_collect_command_text(
            queue_json,
            execute=True,
            refresh_strategy_tester_analysis=True,
        )
    )
    collect_execute_and_refresh_all = str(
        handoff.get("execute_and_refresh_all_command_text")
        or manual_collect_command_text(
            queue_json,
            execute=True,
            refresh_post_collect_analysis=True,
        )
    )
    mark_start_command = str(handoff.get("manual_run_start_mark_command_text") or "")
    lines = [
        "# MT5 Manual Strategy Tester Queue",
        "",
        f"- Generated at: {payload.get('generated_at', '')}",
        f"- Promotion gate: {payload.get('promotion_gate_generated_at', '')}",
        f"- Promotion decision: {payload.get('promotion_gate_decision', '')}",
        f"- Status: {payload.get('status', '')}",
        f"- Next action: {payload.get('next_action', '')}",
        f"- Entries: {payload.get('entry_count', '')}",
        f"- Total entries: {payload.get('total_entry_count', '')}",
        f"- Stale entries: {payload.get('stale_entry_count', '')}",
        f"- Steps: {payload.get('step_count', '')}",
        f"- Ready to collect: {payload.get('ready_to_collect_count', '')}",
        f"- Completed: {payload.get('completed_count', '')}",
        f"- Waiting: {payload.get('waiting_count', '')}",
        f"- Step reports ready: {payload.get('step_report_ready_count', '')}",
        f"- Step reports waiting: {payload.get('step_waiting_report_count', '')}",
        f"- Step launches needed: {payload.get('step_launch_needed_count', '')}",
        f"- Static strategy configs: {payload.get('static_strategy_config_count', 0)}",
        f"- Static candidate labels: {payload.get('static_candidate_label_count', 0)}",
        f"- Manual run start marked: {payload.get('manual_run_start_marked', False)}",
        f"- Manual run start marked this run: {payload.get('manual_run_start_marked_this_run', False)}",
        f"- Manual run start after override: {payload.get('manual_run_start_after_override', '')}",
        f"- Manual run start preserved: {payload.get('manual_run_start_preserved', False)}",
        f"- Manual run start state marked count: {payload.get('manual_run_start_state_marked_count', 0)}",
        f"- Manual run start effective after values: {', '.join(str(item) for item in payload.get('manual_run_start_effective_after_values', []))}",
        f"- All collect ready: {payload.get('all_collect_ready')}",
        f"- Blocking reasons: {', '.join(payload.get('blocking_reasons', []))}",
        "",
        "## MT5 Operator Handoff",
        "",
        f"- State: {handoff.get('state', '')}",
        f"- Progress state: {handoff.get('progress_state', '')}",
        f"- Next step summary: {markdown_cell(handoff.get('next_step_operator_summary', ''))}",
        f"- Collect filter: {markdown_cell(handoff.get('next_step_collect_filter_summary', ''))}",
        f"- Collect ready: {handoff.get('collect_ready', '')}",
        f"- Report-ready steps: {', '.join(str(item) for item in handoff.get('step_report_ready_ids', []))}",
        f"- Launch-needed steps: {', '.join(str(item) for item in handoff.get('step_launch_needed_ids', []))}",
        f"- Ready entries: {', '.join(str(item) for item in handoff.get('ready_entry_ids', []))}",
        f"- Waiting entries: {', '.join(str(item) for item in handoff.get('waiting_entry_ids', []))}",
        f"- Completed entries: {', '.join(str(item) for item in handoff.get('completed_entry_ids', []))}",
        f"- Stale entries: {', '.join(str(item) for item in handoff.get('stale_entry_ids', []))}",
        f"- Collect check command: `{markdown_cell(handoff.get('collect_check_command_text', collect_dry_run))}`",
        f"- Collect dry-run command: `{markdown_cell(collect_dry_run)}`",
        f"- Collect execute command: `{markdown_cell(collect_execute)}`",
        f"- Collect execute + analysis command: `{markdown_cell(collect_execute_and_refresh)}`",
        f"- Collect execute + full analysis command: `{markdown_cell(collect_execute_and_refresh_all)}`",
        f"- Mark manual run start command: `{markdown_cell(mark_start_command)}`",
        "",
    ]
    if next_step:
        lines.extend(
            [
                "## MT5 Quick Input",
                "",
                "| field | value |",
                "|---|---|",
                *format_quick_input_rows(quick_input),
                "",
            ]
        )
        lines.extend(
            [
                (
                    f"- Current step: `{markdown_cell(next_step.get('queue_id', ''))}/"
                    f"{markdown_cell(next_step.get('step_label', ''))}`"
                ),
                (
                    "- Strategy Tester settings: "
                    f"Symbol `{markdown_cell(next_step.get('symbol', ''))}`, "
                    f"Period `{markdown_cell(next_step.get('period', ''))}`, "
                    f"Dates `{markdown_cell(next_step.get('dates', ''))}`, "
                    f"Forward `{markdown_cell(next_step.get('forward', ''))}`, "
                    f"Optimization `{markdown_cell(optimization_label_for_item(next_step))}`"
                ),
                (
                    f"- Load Inputs: `{markdown_cell(next_step.get('inputs', ''))}`; "
                    f"save/export Report as `{markdown_cell(next_step.get('report', ''))}`"
                ),
                (
                    f"- Expected output: `{markdown_cell(next_step.get('run_type', ''))}` "
                    f"with `{markdown_cell(next_step.get('step_report_status', ''))}` currently pending"
                ),
                *manual_run_start_guidance_lines(payload, command=mark_start_command),
                "- After completing the MT5 steps, run the collect dry-run command below before executing collection.",
            ]
        )
    elif payload.get("all_collect_ready") is True:
        lines.extend(
            [
                "- All Strategy Tester entries are ready to collect.",
                "- Run the collect dry-run command below, then execute collection if the selected entries look correct.",
            ]
        )
    elif handoff.get("progress_state") == "reports_ready_waiting_collect_confirmation":
        lines.extend(
            [
                "- No launch-needed Strategy Tester step remains.",
                "- Run the collect dry-run command to confirm whether fresh Agent CSV/report files are now ready.",
            ]
        )
    else:
        lines.append("- No launch-needed Strategy Tester step remains; inspect queue and collect readiness below.")
    lines.extend(
        [
            "",
            "## MT5 Pass Budget",
            "",
            "| order | queue/step | optimization | inputs | available | optimized inputs | full-factorial passes | set file | optimized names | note |",
            "|---:|---|---|---|---:|---:|---:|---|---|---|",
            *format_pass_budget_rows(checklist),
        ]
    )
    lines.extend(
        [
            "",
            "## MT5 Operation Cards",
            "",
        "| next | order | action | purpose | queue/step | symbol | period | dates | forward | window | optimization | inputs | report | collect status | fingerprint |",
        "|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        *format_operation_card_rows(operation_cards),
        ]
    )
    lines.extend([
        "",
        "## Next Manual Step",
        "",
        "| order | queue/step | symbol | period | dates | forward | optimization | run type | status | launch kind | inputs | report | fingerprint |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---|---|",
    ])
    if next_step:
        lines.append(
            f"| {next_step.get('order', '')} | "
            f"{markdown_cell(next_step.get('queue_id', ''))}/{markdown_cell(next_step.get('step_label', ''))} | "
            f"{markdown_cell(next_step.get('symbol', ''))} | "
            f"{markdown_cell(next_step.get('period', ''))} | "
            f"{markdown_cell(next_step.get('dates', ''))} | "
            f"{markdown_cell(next_step.get('forward', ''))} | "
            f"{markdown_cell(optimization_label_for_item(next_step))} | "
            f"{markdown_cell(next_step.get('run_type', ''))} | "
            f"{markdown_cell(next_step.get('step_report_status', ''))} | "
            f"{markdown_cell(next_step.get('launch_command_kind', ''))} | "
            f"{markdown_cell(next_step.get('inputs', ''))} | "
            f"{markdown_cell(next_step.get('report', ''))} | "
            f"{markdown_cell(next_step.get('step_fingerprint', ''))} |"
        )
    else:
        next_message = "No launch-needed Strategy Tester step remains."
        if payload.get("all_collect_ready") is True:
            next_message = "All entries are collect-ready; run the collect commands."
        lines.append(f"| - | {markdown_cell(next_message)} |  |  |  |  |  |  |  |  |  |  |  |")
    lines.extend([
        "",
        "## MT5 Strategy Tester Targets",
        "",
        "| order | purpose | queue/step | symbol | period | dates | forward | optimization | run type | expected report | report note | inputs | report | start after | collect after | collect status | step report | launch needed | auto launch | fingerprint |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---:|---|---|",
    ])
    targets = (
        payload.get("strategy_tester_targets")
        if isinstance(payload.get("strategy_tester_targets"), list)
        else []
    )
    if targets:
        for target in targets:
            if not isinstance(target, dict):
                continue
            lines.append(
                f"| {target.get('order', '')} | {markdown_cell(target.get('purpose', ''))} | "
                f"{markdown_cell(target.get('queue_id', ''))}/{markdown_cell(target.get('step_label', ''))} | "
                f"{markdown_cell(target.get('symbol', ''))} | {markdown_cell(target.get('period', ''))} | "
                f"{markdown_cell(target.get('dates', ''))} | {markdown_cell(target.get('forward', ''))} | "
                f"{markdown_cell(optimization_label_for_item(target))} | "
                f"{markdown_cell(target.get('run_type', ''))} | "
                f"{markdown_cell(target.get('expected_report_artifact', ''))} | "
                f"{markdown_cell(target.get('report_expectation_note', ''))} | "
                f"{markdown_cell(target.get('inputs', ''))} | {markdown_cell(target.get('report', ''))} | "
                f"{markdown_cell(target.get('start_after', ''))} | "
                f"{markdown_cell(target.get('collect_modified_after', ''))} | "
                f"{markdown_cell(target.get('collect_status', ''))} | "
                f"{markdown_cell(target.get('step_report_status', ''))} | "
                f"{target.get('launch_needed', '')} | "
                f"{markdown_cell(target.get('auto_launch_kind', ''))} | "
                f"{markdown_cell(target.get('step_fingerprint', ''))} |"
            )
    else:
        lines.append("| - |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "## Queue",
            "",
            "| order | id | available | current | title | source | runner generated | gate generated | current gate | decision | current decision | action current | start after | steps | collect status | ready | next action | stale reason |",
            "|---:|---|---:|---:|---|---|---|---|---|---|---|---:|---|---:|---|---:|---|---|",
        ]
    )
    entries = payload.get("entries") if isinstance(payload.get("entries"), list) else []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        stale_reasons = entry.get("stale_reasons") if isinstance(entry.get("stale_reasons"), list) else []
        lines.append(
            f"| {entry.get('order', '')} | {markdown_cell(entry.get('id', ''))} | "
            f"{entry.get('available')} | {entry.get('current_for_execution', '')} | "
            f"{markdown_cell(entry.get('title', ''))} | {markdown_cell(entry.get('source_json', ''))} | "
            f"{markdown_cell(entry.get('runner_generated_at', ''))} | "
            f"{markdown_cell(entry.get('promotion_generated_at', ''))} | "
            f"{markdown_cell(entry.get('current_promotion_generated_at', ''))} | "
            f"{markdown_cell(entry.get('promotion_decision', ''))} | "
            f"{markdown_cell(entry.get('current_promotion_decision', ''))} | "
            f"{entry.get('selected_action_current', '')} | "
            f"{markdown_cell(entry.get('manual_run_start_after', ''))} | {entry.get('step_count', '')} | "
            f"{markdown_cell(entry.get('collect_status', ''))} | {entry.get('collect_ready')} | "
            f"{markdown_cell(entry.get('collect_next_action', ''))} | "
            f"{markdown_cell(', '.join(str(reason) for reason in stale_reasons))} |"
        )
    stale_entries = [
        entry for entry in entries if isinstance(entry, dict) and entry.get("stale_reasons")
    ]
    if stale_entries:
        lines.extend(
            [
                "",
                "## Stale Runner Refresh",
                "",
                "| id | reason | refresh command |",
                "|---|---|---|",
            ]
        )
        for entry in stale_entries:
            reasons = entry.get("stale_reasons") if isinstance(entry.get("stale_reasons"), list) else []
            lines.append(
                f"| {markdown_cell(entry.get('id', ''))} | "
                f"{markdown_cell(', '.join(str(reason) for reason in reasons))} | "
                f"`{markdown_cell(entry.get('refresh_command_text', ''))}` |"
            )
    lines.extend(
        [
            "",
            "## Strategy Tester Steps",
            "",
            "| queue | order | step | expert | symbol | period | model | dates | forward | optimization | run type | expected report | step report | launch needed | inputs | report | fingerprint |",
            "|---|---:|---|---|---|---|---|---|---|---|---|---|---|---:|---|---|---|",
        ]
    )
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("available") is not True:
            continue
        steps = entry.get("steps") if isinstance(entry.get("steps"), list) else []
        for step in steps:
            if not isinstance(step, dict):
                continue
            lines.append(
                f"| {markdown_cell(entry.get('id', ''))} | {step.get('order', '')} | "
                f"{markdown_cell(step.get('label', ''))} | {markdown_cell(step.get('expert', ''))} | "
                f"{markdown_cell(step.get('symbol', ''))} | {markdown_cell(step.get('period', ''))} | "
                f"{markdown_cell(step.get('model_label') or step.get('model', ''))} | "
                f"{markdown_cell(format_step_dates(step))} | "
                f"{markdown_cell(step.get('forward_label') or step.get('forward_mode_effective', ''))} | "
                f"{markdown_cell(optimization_label_for_item(step))} | "
                f"{markdown_cell(step.get('run_type', ''))} | "
                f"{markdown_cell(step.get('expected_report_artifact', ''))} | "
                f"{markdown_cell(next((item.get('step_report_status', '') for item in checklist if isinstance(item, dict) and item.get('queue_id') == entry.get('id') and item.get('step_label') == step.get('label')), ''))} | "
                f"{next((item.get('launch_needed', '') for item in checklist if isinstance(item, dict) and item.get('queue_id') == entry.get('id') and item.get('step_label') == step.get('label')), '')} | "
                f"{markdown_cell(step.get('expert_parameters', ''))} | {markdown_cell(step.get('report_name', ''))} | "
                f"{markdown_cell(next((item.get('step_fingerprint', '') for item in checklist if isinstance(item, dict) and item.get('queue_id') == entry.get('id') and item.get('step_label') == step.get('label')), ''))} |"
            )
    lines.extend(
        [
            "",
            "## Manual Execution Checklist",
            "",
            "| done | order | queue/step | symbol | period | model | dates | forward | optimization | run type | expected report | step report | launch needed | inputs | report | start after | fingerprint |",
            "|---|---:|---|---|---|---|---|---|---|---|---|---|---:|---|---|---|---|",
        ]
    )
    for item in checklist:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"| {checklist_done_mark(item)} | {item.get('order', '')} | "
            f"{markdown_cell(item.get('queue_id', ''))}/{markdown_cell(item.get('step_label', ''))} | "
            f"{markdown_cell(item.get('symbol', ''))} | "
            f"{markdown_cell(item.get('period', ''))} | "
            f"{markdown_cell(item.get('model', ''))} | "
            f"{markdown_cell(item.get('dates', ''))} | "
            f"{markdown_cell(item.get('forward', ''))} | "
            f"{markdown_cell(optimization_label_for_item(item))} | "
            f"{markdown_cell(item.get('run_type', ''))} | "
            f"{markdown_cell(item.get('expected_report_artifact', ''))} | "
            f"{markdown_cell(item.get('step_report_status', ''))} | "
            f"{item.get('launch_needed', '')} | "
            f"{markdown_cell(item.get('inputs', ''))} | "
            f"{markdown_cell(item.get('report', ''))} | "
            f"{markdown_cell(item.get('manual_run_start_after', ''))} | "
            f"{markdown_cell(item.get('step_fingerprint', ''))} |"
        )
    lines.extend(
        [
            "",
            "## Auto Launch Commands",
            "",
            "- Close the existing MT5 terminal before using direct /config commands. If MT5 is already open, use the manual checklist above. Steps that need runtime Report overrides use the runner execute command instead.",
            "",
            "| order | queue/step | launch needed | workspace config | MT5 config | command |",
            "|---:|---|---:|---|---|---|",
        ]
    )
    for item in checklist:
        if not isinstance(item, dict):
            continue
        command_text = str(item.get("launch_command_text") or "")
        if not command_text:
            command_text = f"launch unavailable: {item.get('launch_error', '')}"
        command_kind = str(item.get("launch_command_kind") or "")
        if command_kind == "runner_execute":
            command_text = f"runner execute: {command_text}"
        lines.append(
            f"| {item.get('order', '')} | "
            f"{markdown_cell(item.get('queue_id', ''))}/{markdown_cell(item.get('step_label', ''))} | "
            f"{item.get('launch_needed', '')} | "
            f"{markdown_cell(item.get('config', ''))} | "
            f"{markdown_cell(item.get('mt5_config', ''))} | "
            f"`{markdown_cell(command_text)}` |"
        )
    lines.extend(["", "## Collect Commands", ""])
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("available") is not True:
            continue
        lines.extend(
            [
                f"### {entry.get('id', '')}",
                "",
                f"- Start after: {entry.get('manual_run_start_after', '')}",
                f"- Runner generated: {entry.get('runner_generated_at', '')}",
                f"- Gate generated: {entry.get('promotion_generated_at', '')}",
                f"- Current gate: {entry.get('current_promotion_generated_at', '')}",
                f"- Gate decision: {entry.get('promotion_decision', '')}",
                f"- Current gate decision: {entry.get('current_promotion_decision', '')}",
                f"- Collect status: {entry.get('collect_status', '')}",
                f"- Collect reason: {entry.get('collect_reason', '')}",
                f"- Blocking reasons: {', '.join(str(item) for item in entry.get('collect_blocking_reasons', []))}",
                "",
                "```bash",
                str(entry.get("collect_only_command_text") or ""),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Collect Ready Entries",
            "",
            *manual_run_start_guidance_lines(payload, command=mark_start_command),
            "",
            "```bash",
            mark_start_command,
            "```",
            "",
            "- After MT5 Strategy Tester runs complete, dry-run the collector first. It refreshes source runner readiness and rewrites this queue before selecting ready entries.",
            "",
            "```bash",
            collect_dry_run,
            "```",
            "",
            "- If the dry-run shows the expected ready entries, execute the ready collect-only commands:",
            "",
            "```bash",
            collect_execute,
            "```",
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
    parser = argparse.ArgumentParser(description="Build a consolidated MT5 manual Strategy Tester queue.")
    parser.add_argument("--back-forward-run", default=DEFAULT_BACK_FORWARD_RUN)
    parser.add_argument("--sell-next-action-run", default=DEFAULT_SELL_NEXT_ACTION_RUN)
    parser.add_argument("--buy-next-action-run", default=DEFAULT_BUY_NEXT_ACTION_RUN)
    parser.add_argument("--promotion-gate", default="")
    parser.add_argument("--mt5-root", default=str(default_mt5_root()))
    parser.add_argument("--wine", default=str(default_wine_path()))
    parser.add_argument(
        "--include-optimization-configs",
        action="store_true",
        help="Append the default MT5 optimization and next-optimization Tester configs to the manual queue.",
    )
    parser.add_argument(
        "--include-static-config",
        action="append",
        default=[],
        help="Append an arbitrary static MT5 Tester .ini config to the manual queue. Can be repeated.",
    )
    parser.add_argument(
        "--include-static-candidate-label",
        action="append",
        default=[],
        choices=sorted(DEFAULT_STATIC_CANDIDATE_CONFIGS),
        help=(
            "Append a known MT5 candidate validation run with date/report/output overrides. "
            "Can be repeated."
        ),
    )
    parser.add_argument(
        "--mark-manual-run-start",
        action="store_true",
        help=(
            "Reset manual_run_start_after / collect_modified_after to now for the queue before "
            "starting a fresh manual MT5 Strategy Tester run."
        ),
    )
    parser.add_argument(
        "--manual-run-start-after",
        default="",
        help=(
            "Explicit TIME_FORMAT timestamp used with --mark-manual-run-start. "
            "Example: '2026.07.17 12:40'."
        ),
    )
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--print-full-report", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    promotion_gate = args.promotion_gate
    if not promotion_gate and (
        args.back_forward_run == DEFAULT_BACK_FORWARD_RUN
        and args.sell_next_action_run == DEFAULT_SELL_NEXT_ACTION_RUN
        and args.buy_next_action_run == DEFAULT_BUY_NEXT_ACTION_RUN
    ):
        promotion_gate = DEFAULT_PROMOTION_GATE
    static_configs = list(args.include_static_config or [])
    if args.include_optimization_configs:
        static_configs.extend(DEFAULT_STATIC_OPTIMIZATION_CONFIGS)
    existing_queue = load_json(args.output_json)
    generated_at = None
    manual_run_start_after = ""
    if args.mark_manual_run_start or args.manual_run_start_after:
        generated_at = datetime.now().strftime(TIME_FORMAT)
        manual_run_start_after = str(args.manual_run_start_after or generated_at)
    payload = build_queue(
        back_forward_run=args.back_forward_run,
        sell_next_action_run=args.sell_next_action_run,
        buy_next_action_run=args.buy_next_action_run,
        promotion_gate=promotion_gate,
        mt5_root=args.mt5_root,
        wine_path=args.wine,
        queue_json=args.output_json,
        generated_at=generated_at,
        static_strategy_configs=static_configs,
        static_candidate_labels=list(args.include_static_candidate_label or []),
        static_strategy_config_state=static_strategy_config_state_from_queue(existing_queue),
        manual_run_start_state=manual_run_start_state_from_queue(existing_queue),
        manual_run_start_after_override=manual_run_start_after,
    )
    payload["queue_json"] = args.output_json
    write_json(args.output_json, payload)
    write_text(args.output_md, format_markdown(payload))
    operation_cards = payload.get("operation_cards") if isinstance(payload.get("operation_cards"), list) else []
    next_operation_card = next(
        (card for card in operation_cards if isinstance(card, dict) and card.get("is_next") is True),
        {},
    )
    summary = {
        "ok": payload.get("ok"),
        "status": payload.get("status"),
        "next_action": payload.get("next_action"),
        "progress_state": (
            payload.get("operator_handoff", {}).get("progress_state")
            if isinstance(payload.get("operator_handoff"), dict)
            else ""
        ),
        "entry_count": payload.get("entry_count"),
        "step_count": payload.get("step_count"),
        "ready_to_collect_count": payload.get("ready_to_collect_count"),
        "completed_count": payload.get("completed_count"),
        "waiting_count": payload.get("waiting_count"),
        "step_report_ready_count": payload.get("step_report_ready_count"),
        "step_waiting_report_count": payload.get("step_waiting_report_count"),
        "step_launch_needed_count": payload.get("step_launch_needed_count"),
        "promotion_gate_generated_at": payload.get("promotion_gate_generated_at"),
        "promotion_gate_decision": payload.get("promotion_gate_decision"),
        "next_launch_step": payload.get("next_launch_step"),
        "manual_run_start_marked": payload.get("manual_run_start_marked"),
        "manual_run_start_marked_this_run": payload.get("manual_run_start_marked_this_run"),
        "manual_run_start_after_override": payload.get("manual_run_start_after_override"),
        "manual_run_start_preserved": payload.get("manual_run_start_preserved"),
        "manual_run_start_state_count": payload.get("manual_run_start_state_count"),
        "manual_run_start_state_marked_count": payload.get("manual_run_start_state_marked_count"),
        "manual_run_start_effective_after_values": payload.get(
            "manual_run_start_effective_after_values"
        ),
        "manual_run_start_mark_command_text": payload.get("manual_run_start_mark_command_text"),
        "static_strategy_config_count": len(payload.get("static_strategy_configs", [])),
        "static_candidate_label_count": len(payload.get("static_candidate_labels", [])),
        "operation_card_count": len(operation_cards),
        "next_operation_card": next_operation_card,
        "output_json": args.output_json,
        "output_md": args.output_md,
    }
    print(json.dumps(payload if args.print_full_report else summary, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
