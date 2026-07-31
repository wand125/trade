from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT
from analysis.mt5_compile_status import default_mt5_root
from analysis.mt5_tester_optimization_report import discover_tester_csvs, parse_modified_after
from analysis.mt5_tester_run import (
    tester_config_metadata,
    tester_html_report_paths,
    tester_report_expectation,
    tester_report_paths,
)


DEFAULT_PROMOTION_GATE = "runtime/latest_promotion_gate.json"
DEFAULT_OUTPUT_JSON = "runtime/latest_mt5_next_action_run.json"
DEFAULT_OUTPUT_MD = "runtime/latest_mt5_next_action_run.md"
DEFAULT_READY_STATUS = "runtime/latest_mt5_tester_status.json"
DEFAULT_READY_STATUS_MD = "runtime/latest_mt5_tester_status.md"
DEFAULT_BRIDGE_RECOVERY_PLAN = "runtime/latest_bridge_recovery_plan.json"
DEFAULT_READY_STATUS_MAX_AGE_SECONDS = 600
DEFAULT_TARGET = "first_mt5"
AUTO_MT5_TARGETS = {"", "auto", "auto_mt5", "first", "first_mt5"}
FORWARD_MODE_LABELS = {
    "0": "Disabled",
    "1": "1/2",
    "2": "1/3",
    "3": "1/4",
    "4": "Custom",
}
MODEL_LABELS = {
    "0": "Open prices only",
    "1": "1 minute OHLC",
    "2": "Every tick",
    "3": "Every tick based on real ticks",
    "4": "Every tick based on real ticks",
}
OPTIMIZATION_LABELS = {
    "0": "Disabled",
    "1": "Slow complete algorithm",
    "2": "Fast genetic algorithm",
}

EXECUTION_LABELS = (
    ("stable_candidate_refit_execution", "stable_candidate_refit"),
    ("stable_candidate_tester_execution", "stable_candidate_tester"),
    ("refit_execution", "refit"),
    ("validation_execution", "validation"),
    ("execution", "execution"),
    ("follow_up_execution", "follow_up"),
    ("score_weight_sample_collection", "score_weight_sample_collection"),
    ("score_weight_history_check", "score_weight_history_check"),
)

ARCHIVE_PREVIEW_KEYS = {
    "stable_candidate_refit_execution": "stable_candidate_refit_archive_preview",
    "stable_candidate_tester_execution": "stable_candidate_archive_preview",
    "refit_execution": "refit_archive_preview",
    "validation_execution": "validation_archive_preview",
    "follow_up_execution": "follow_up_archive_preview",
    "execution": "archive_preview",
    "score_weight_sample_collection": "score_weight_sample_collection_archive_preview",
}
RELATED_EXECUTION_KEYS = (
    "score_weight_search",
    "score_weight_set",
    "score_weight_history_check",
    "stable_candidate_set_execution",
    "collect_refresh",
)
ACTION_CONTEXT_KEYS = (
    "previous_refit",
    "stable_candidate_refit",
    "stable_candidate_refit_completed",
    "score_weight_set_result",
    "score_weight_follow_up",
    "upstream_chronological_rejection",
)


def load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    with source.open(encoding="utf-8") as f:
        payload = json.load(f)
    return payload if isinstance(payload, dict) else {}


def bridge_recovery_plan_summary(path: str | Path) -> dict[str, Any]:
    if not str(path):
        return {"exists": False, "path": ""}
    source = Path(path)
    payload = load_json(source)
    summary = {
        "exists": source.exists(),
        "path": str(source),
        "ok": payload.get("ok", ""),
        "status": payload.get("status", ""),
        "ready_for_mt5_validation": payload.get("ready_for_mt5_validation", ""),
        "blocking_reasons": payload.get("blocking_reasons", [])
        if isinstance(payload.get("blocking_reasons"), list)
        else [],
        "next_action": payload.get("next_action", ""),
        "generated_at": payload.get("generated_at", ""),
    }
    return summary


def bridge_recovery_blocks_mt5_validation(summary: dict[str, Any]) -> bool:
    return bool(summary.get("exists") is True and summary.get("ready_for_mt5_validation") is False)


def bridge_recovery_block_reason(summary: dict[str, Any]) -> str:
    status = str(summary.get("status") or "not_ready")
    next_action = str(summary.get("next_action") or "")
    suffix = f"; next_action={next_action}" if next_action else ""
    return f"Bridge Recovery is not ready for MT5 validation: {status}{suffix}"


def command_list(execution: object) -> list[str]:
    if not isinstance(execution, dict):
        return []
    command = execution.get("command")
    if not isinstance(command, list):
        return []
    return [str(item) for item in command]


def command_option_value(command: list[str], option: str) -> str:
    for index, item in enumerate(command):
        if item == option and index + 1 < len(command):
            return command[index + 1]
        prefix = f"{option}="
        if item.startswith(prefix):
            return item[len(prefix) :]
    return ""


def command_output_paths(command: list[str]) -> dict[str, str]:
    outputs = {
        "output_json": command_option_value(command, "--output-json"),
        "output_md": command_option_value(command, "--output-md"),
        "optimization_output_json": command_option_value(command, "--optimization-output-json"),
        "optimization_output_md": command_option_value(command, "--optimization-output-md"),
        "recommendation_output_json": command_option_value(command, "--recommendation-output-json"),
        "recommendation_output_md": command_option_value(command, "--recommendation-output-md"),
    }
    return {key: value for key, value in outputs.items() if value}


def command_without_option(command: list[str], option: str) -> list[str]:
    cleaned: list[str] = []
    skip_next = False
    prefix = f"{option}="
    for item in command:
        if skip_next:
            skip_next = False
            continue
        if item == option:
            skip_next = True
            continue
        if item.startswith(prefix):
            continue
        cleaned.append(item)
    return cleaned


def command_without_flag(command: list[str], flag: str) -> list[str]:
    return [item for item in command if item != flag]


def tester_collect_only_command(command: list[str]) -> list[str]:
    collect = list(command)
    for option in ("--agent-csv-archive-run-id",):
        collect = command_without_option(collect, option)
    for flag in ("--archive-agent-csvs-before-run", "--dry-run"):
        collect = command_without_flag(collect, flag)
    if "--collect-only" not in collect:
        collect.append("--collect-only")
    return collect


def label_from_mapping(value: Any, labels: dict[str, str]) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return labels.get(text, text)


def append_csv_modified_after(command: list[str], generated_at: str) -> list[str]:
    if "--csv-modified-after" in command or not generated_at:
        return list(command)
    return [*command, "--csv-modified-after", generated_at]


def manual_strategy_tester_plan(report: dict[str, Any], hints: dict[str, Any]) -> dict[str, Any]:
    primary = report.get("primary") if isinstance(report.get("primary"), dict) else {}
    command = command_list(primary)
    if execution_class(primary) != "mt5_tester_run" or not command:
        return {"available": False, "steps": []}
    config_path = command_option_value(command, "--config") or str(primary.get("config") or "")
    if not config_path:
        return {"available": False, "steps": []}
    config_file = Path(config_path).expanduser()
    metadata: dict[str, str] = {}
    if config_file.exists():
        metadata = tester_config_metadata(config_file.read_text(encoding="utf-8"))
    report_name = command_option_value(command, "--report-name") or str(primary.get("report_name") or metadata.get("report", ""))
    from_date = command_option_value(command, "--from-date") or metadata.get("from_date", "")
    to_date = command_option_value(command, "--to-date") or metadata.get("to_date", "")
    forward_mode = command_option_value(command, "--forward-mode") or metadata.get("forward_mode", "")
    report_expectation = tester_report_expectation(metadata.get("optimization", ""), forward_mode)
    generated_at = str(report.get("runner_generated_at") or "")
    collect_command = (
        [str(item) for item in hints.get("collect_only_command", [])]
        if isinstance(hints.get("collect_only_command"), list)
        else []
    )
    recommended_collect = append_csv_modified_after(collect_command, generated_at)
    step = {
        "order": 1,
        "label": str(primary.get("kind") or report.get("label") or "primary"),
        "config": config_path,
        "expert": metadata.get("expert", ""),
        "symbol": metadata.get("symbol", ""),
        "period": metadata.get("period", ""),
        "model": metadata.get("model", ""),
        "model_label": label_from_mapping(metadata.get("model", ""), MODEL_LABELS),
        "optimization": metadata.get("optimization", ""),
        "optimization_label": label_from_mapping(metadata.get("optimization", ""), OPTIMIZATION_LABELS),
        "optimization_enabled": metadata.get("optimization", "") not in ("", "0"),
        "from_date": from_date,
        "to_date": to_date,
        "forward_mode_base": metadata.get("forward_mode", ""),
        "forward_mode_override": command_option_value(command, "--forward-mode"),
        "forward_mode_effective": forward_mode,
        "forward_label": label_from_mapping(forward_mode, FORWARD_MODE_LABELS),
        "expert_parameters": metadata.get("expert_parameters", ""),
        "report_name": report_name,
        "output_json": command_option_value(command, "--output-json"),
        "optimization_output_json": command_option_value(command, "--optimization-output-json"),
        **report_expectation,
    }
    return {
        "available": True,
        "purpose": "Manual MT5 Strategy Tester path when MT5 is already open or /config launch is blocked.",
        "manual_run_start_after": generated_at,
        "recommended_collect_only_command": recommended_collect,
        "recommended_collect_only_command_text": shlex.join(recommended_collect) if recommended_collect else "",
        "collect_only_note": (
            "Run this Strategy Tester setup in MT5 first, then use this command. "
            "--csv-modified-after filters out older Agent CSV files."
        ),
        "steps": [step],
    }


def file_freshness(path: str | Path, *, modified_after_epoch: float | None) -> dict[str, Any]:
    source = Path(path)
    try:
        stat = source.stat()
    except OSError:
        return {"path": str(source), "exists": False, "fresh": False, "mtime": "", "mtime_epoch": None, "size": ""}
    fresh = modified_after_epoch is None or stat.st_mtime >= modified_after_epoch
    return {
        "path": str(source),
        "exists": True,
        "fresh": fresh,
        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime(TIME_FORMAT),
        "mtime_epoch": round(stat.st_mtime, 3),
        "size": stat.st_size,
    }


def best_fresh_file(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fresh_rows = [row for row in rows if row.get("exists") is True and row.get("fresh") is True]
    if not fresh_rows:
        return {}
    return max(fresh_rows, key=lambda row: float(row.get("mtime_epoch") or 0.0))


def manual_collect_readiness(report: dict[str, Any], *, mt5_root: str | Path | None = None) -> dict[str, Any]:
    manual_plan = (
        report.get("manual_strategy_tester")
        if isinstance(report.get("manual_strategy_tester"), dict)
        else {}
    )
    collect_readiness = (
        report.get("manual_collect_readiness")
        if isinstance(report.get("manual_collect_readiness"), dict)
        else {}
    )
    steps = manual_plan.get("steps") if isinstance(manual_plan.get("steps"), list) else []
    if not manual_plan.get("available") or not steps:
        return {"available": False, "ready": False, "status": "not_available", "steps": []}

    mt5 = Path(mt5_root).expanduser() if mt5_root else default_mt5_root()
    tester_root = mt5 / "Tester"
    modified_after = str(manual_plan.get("manual_run_start_after") or report.get("runner_generated_at") or "")
    try:
        modified_after_epoch = parse_modified_after(modified_after)
    except ValueError as exc:
        return {
            "available": False,
            "ready": False,
            "status": "invalid_modified_after",
            "reason": str(exc),
            "blocking_reasons": ["invalid_modified_after"],
            "next_action": "fix_csv_modified_after",
            "mt5_root": str(mt5),
            "tester_root": str(tester_root),
            "modified_after": modified_after,
            "csv_count": 0,
            "steps": [],
        }

    primary = report.get("primary") if isinstance(report.get("primary"), dict) else {}
    command = command_list(primary)
    since_minutes_text = command_option_value(command, "--since-minutes")
    try:
        since_minutes = float(since_minutes_text) if since_minutes_text else 240.0
    except ValueError:
        since_minutes = 240.0
    min_closed_text = command_option_value(command, "--min-closed")
    try:
        min_closed = int(float(min_closed_text)) if min_closed_text else 0
    except ValueError:
        min_closed = 0

    csvs = discover_tester_csvs(
        [tester_root],
        since_minutes=since_minutes,
        modified_after_epoch=modified_after_epoch,
    )
    csv_files = []
    for path in csvs:
        row = file_freshness(path, modified_after_epoch=modified_after_epoch)
        row["agent"] = next((parent.name for parent in path.parents if parent.name.startswith("Agent-")), "")
        csv_files.append(row)

    step_rows: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        report_name = str(step.get("report_name") or "")
        back_xml, forward_xml = tester_report_paths(mt5, report_name)
        xml_rows = [
            file_freshness(back_xml, modified_after_epoch=modified_after_epoch),
            file_freshness(forward_xml, modified_after_epoch=modified_after_epoch),
        ]
        html_rows = [
            file_freshness(path, modified_after_epoch=modified_after_epoch)
            for path in tester_html_report_paths(mt5, report_name)
        ]
        xml_pair_ready = all(row.get("exists") is True and row.get("fresh") is True for row in xml_rows)
        html_ready = bool(best_fresh_file(html_rows))
        optimization_enabled = step.get("optimization_enabled") is True
        report_ready = xml_pair_ready or (not optimization_enabled and html_ready)
        if xml_pair_ready:
            report_status = "xml_pair_ready"
            selected_report = xml_rows[0].get("path", "")
        elif not optimization_enabled and html_ready:
            report_status = "single_test_html_ready"
            selected_report = best_fresh_file(html_rows).get("path", "")
        else:
            report_status = "waiting_report"
            selected_report = ""
        label = str(step.get("label") or "primary")
        step_rows.append(
            {
                "label": label,
                "report_name": report_name,
                "optimization_enabled": optimization_enabled,
                "report_ready": report_ready,
                "report_status": report_status,
                "selected_report": selected_report,
                "xml_reports": xml_rows,
                "html_reports": html_rows,
                "collect_ready": report_ready and bool(csv_files),
                "blocking_reason": "" if report_ready else f"{label}:waiting_report",
            }
        )

    reports_ready = bool(step_rows) and all(row.get("report_ready") is True for row in step_rows)
    csv_ready = bool(csv_files)
    blocking_reasons = [str(row.get("blocking_reason")) for row in step_rows if row.get("blocking_reason")]
    if not csv_ready:
        blocking_reasons.append("agent_csv_missing_or_stale")
    if not reports_ready:
        status = "waiting_for_reports"
    elif not csv_ready:
        status = "waiting_for_agent_csv"
    else:
        status = "ready_to_collect"
    if reports_ready and csv_ready:
        next_action = "run_collect_only_command"
        reason = "all_reports_and_agent_csv_fresh"
    elif not reports_ready and not csv_ready:
        next_action = "run_manual_strategy_tester_step_and_wait_for_agent_csv"
        reason = ", ".join(blocking_reasons)
    elif not reports_ready:
        next_action = "run_missing_manual_strategy_tester_step"
        reason = ", ".join(blocking_reasons)
    else:
        next_action = "wait_for_fresh_agent_csv_or_check_ea_file_output"
        reason = ", ".join(blocking_reasons)
    return {
        "available": bool(step_rows),
        "ready": reports_ready and csv_ready,
        "status": status,
        "reason": reason,
        "blocking_reasons": blocking_reasons,
        "next_action": next_action,
        "mt5_root": str(mt5),
        "tester_root": str(tester_root),
        "modified_after": modified_after,
        "modified_after_epoch": round(modified_after_epoch, 3) if modified_after_epoch is not None else None,
        "since_minutes": since_minutes,
        "min_closed": min_closed,
        "csv_count": len(csv_files),
        "csv_files": csv_files[:20],
        "steps": step_rows,
    }


def execution_hint_base_options(args: argparse.Namespace) -> list[str]:
    options: list[str] = []
    focus_side = str(getattr(args, "focus_side", "") or "").strip().lower()
    if focus_side:
        options.extend(["--focus-side", focus_side])
    if args.run_compile:
        options.append("--run-compile")
    if args.run_follow_up:
        options.append("--run-follow-up")
    if args.allow_non_tester_primary:
        options.append("--allow-non-tester-primary")
    if args.require_bridge_ready:
        options.append("--require-bridge-ready")
    if args.skip_archive_preview:
        options.append("--skip-archive-preview")
    return options


def attach_execution_hints(report: dict[str, Any], *, args: argparse.Namespace) -> dict[str, Any]:
    primary = report.get("primary") if isinstance(report.get("primary"), dict) else {}
    target = str(report.get("target") or args.target or DEFAULT_TARGET)
    runner_execute = [
        "python3",
        "analysis/mt5_next_action_run.py",
        "--target",
        target,
        "--execute",
        "--refresh-ready-status",
        *execution_hint_base_options(args),
        "--max-ready-status-age-seconds",
        str(args.max_ready_status_age_seconds),
        "--output-json",
        str(args.output_json),
        "--output-md",
        str(args.output_md),
    ]
    hints: dict[str, Any] = {
        "execute_command": runner_execute,
        "execute_command_text": shlex.join(runner_execute),
        "options_preserved": [
            "--run-compile",
            "--run-follow-up",
            "--allow-non-tester-primary",
            "--require-bridge-ready",
            "--skip-archive-preview",
        ],
    }
    report["bridge_recovery_required_for_mt5_validation"] = args.require_bridge_ready
    primary_command = command_list(primary)
    if execution_class(primary) == "mt5_tester_run" and primary_command:
        generated_at = str(report.get("runner_generated_at") or "")
        collect_only = append_csv_modified_after(tester_collect_only_command(primary_command), generated_at)
        hints.update(
            {
                "collect_only_command": collect_only,
                "collect_only_command_text": shlex.join(collect_only),
                "collect_only_note": (
                    "For manual MT5 Strategy Tester runs, use --csv-modified-after with the manual run start time "
                    "to filter out older Agent CSV files."
                ),
                "collect_only_removed_options": ["--agent-csv-archive-run-id"],
                "collect_only_removed_flags": ["--archive-agent-csvs-before-run", "--dry-run"],
            }
        )
    report["execution_hints"] = hints
    report["execute_command_text"] = hints.get("execute_command_text", "")
    report["collect_only_command_text"] = hints.get("collect_only_command_text", "")
    report["manual_strategy_tester"] = manual_strategy_tester_plan(report, hints)
    report["manual_collect_readiness"] = manual_collect_readiness(report)
    return report


def apply_bridge_recovery_guard(report: dict[str, Any], bridge_recovery: dict[str, Any]) -> dict[str, Any]:
    report["bridge_recovery_plan"] = bridge_recovery
    require_bridge_ready = report.get("bridge_recovery_required_for_mt5_validation") is True
    blocked = require_bridge_ready and bridge_recovery_blocks_mt5_validation(bridge_recovery)
    report["bridge_recovery_required_for_mt5_validation"] = require_bridge_ready
    report["mt5_validation_blocked_by_bridge"] = bool(
        blocked and report.get("primary_is_mt5_tester_run") is True
    )
    if not report["mt5_validation_blocked_by_bridge"]:
        return report

    collect_readiness = (
        report.get("manual_collect_readiness")
        if isinstance(report.get("manual_collect_readiness"), dict)
        else {}
    )
    collect_ready = collect_readiness.get("ready") is True
    report["bridge_recovery_block_reason"] = bridge_recovery_block_reason(bridge_recovery)
    hints = report.get("execution_hints") if isinstance(report.get("execution_hints"), dict) else {}
    hints["execute_command"] = []
    hints["execute_command_text"] = ""
    hints["execute_blocked_reason"] = report["bridge_recovery_block_reason"]
    if not collect_ready:
        hints["collect_only_command"] = []
        hints["collect_only_command_text"] = ""
        hints["collect_only_blocked_reason"] = "manual MT5 reports/Agent CSV are not ready for collect-only"
    report["execution_hints"] = hints
    report["execute_command_text"] = ""
    if not collect_ready:
        report["collect_only_command_text"] = ""

    manual_plan = (
        report.get("manual_strategy_tester")
        if isinstance(report.get("manual_strategy_tester"), dict)
        else {}
    )
    if manual_plan:
        manual_plan["available"] = False
        manual_plan["blocked_by_bridge_recovery"] = True
        manual_plan["blocked_reason"] = report["bridge_recovery_block_reason"]
        report["manual_strategy_tester"] = manual_plan
    return report


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


def planned_outputs_text(outputs: Any) -> str:
    if not isinstance(outputs, dict) or not outputs:
        return ""
    parts: list[str] = []
    for key, label in (
        ("primary", "primary"),
        ("archive_preview", "archive"),
        ("follow_up", "follow_up"),
        ("follow_up_archive_preview", "follow_up_archive"),
    ):
        item = outputs.get(key) if isinstance(outputs.get(key), dict) else {}
        output_json = item.get("output_json", "")
        if output_json:
            parts.append(f"{label}={output_json}")
    return ", ".join(parts)


def compact_list(values: Any) -> str:
    if isinstance(values, list):
        return ", ".join(str(value) for value in values)
    if values in (None, ""):
        return ""
    return str(values)


def format_manual_strategy_tester_rows(steps: Any) -> list[str]:
    if not isinstance(steps, list) or not steps:
        return ["| - |  |  |  |  |  |  |  |  |  |  |  |"]
    rows: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        dates = (
            f"{step.get('from_date', '')} -> {step.get('to_date', '')}"
            if step.get("from_date") or step.get("to_date")
            else ""
        )
        values = [
            step.get("order", ""),
            step.get("label", ""),
            step.get("expert", ""),
            step.get("symbol", ""),
            step.get("period", ""),
            step.get("model_label", "") or step.get("model", ""),
            dates,
            step.get("forward_label", "") or step.get("forward_mode_effective", ""),
            step.get("run_type", ""),
            step.get("expected_report_artifact", ""),
            step.get("expert_parameters", ""),
            step.get("report_name", ""),
        ]
        escaped = [str(value).replace("|", "\\|") for value in values]
        rows.append("| " + " | ".join(escaped) + " |")
    return rows if rows else ["| - |  |  |  |  |  |  |  |  |  |  |  |"]


def execution_summary(execution: dict[str, Any]) -> dict[str, Any]:
    outputs = execution.get("outputs") if isinstance(execution.get("outputs"), dict) else {}
    command = command_list(execution)
    summary: dict[str, Any] = execution_evidence_role(execution)
    summary.update(
        {
            "kind": execution.get("kind", ""),
            "focus_side": execution.get("focus_side", ""),
            "optimization_mode": execution.get("optimization_mode", ""),
            "config": execution.get("config", ""),
            "set": execution.get("set", ""),
            "template_set": execution.get("template_set", ""),
            "report_name": execution.get("report_name", ""),
            "agent_csv_archive_run_id": execution.get("agent_csv_archive_run_id", ""),
            "output_set": outputs.get("output_set", ""),
            "declared_outputs": dict(outputs),
            "note": execution.get("note", ""),
            "command": command,
            "command_text": execution.get("command_text", ""),
            "planned_outputs": command_output_paths(command),
        }
    )
    for key in (
        "timeout_seconds",
        "timeout_minutes",
        "timeout_note",
        "optimized_input_count",
        "estimated_full_factorial_passes",
        "optimized_inputs",
        "latest_executed_tester_xml_rows",
    ):
        if key in execution:
            summary[key] = execution.get(key)
    if "timeout_seconds" in execution:
        summary.update(timeout_deadline_from_now(execution.get("timeout_seconds")))
    return summary


def inline_follow_up_summary(execution: dict[str, Any]) -> dict[str, Any]:
    command = execution.get("follow_up_command")
    if not isinstance(command, list):
        return {}
    outputs = execution.get("outputs") if isinstance(execution.get("outputs"), dict) else {}
    command_list_value = [str(item) for item in command]
    return {
        "kind": "follow_up",
        "focus_side": execution.get("focus_side", ""),
        "optimization_mode": "",
        "config": "",
        "set": "",
        "template_set": "",
        "report_name": "",
        "agent_csv_archive_run_id": "",
        "output_set": outputs.get("forward_json") or outputs.get("output_set", ""),
        "declared_outputs": dict(outputs),
        "note": execution.get("note", ""),
        "command": command_list_value,
        "command_text": execution.get("follow_up_command_text", ""),
        "planned_outputs": command_output_paths(command_list_value),
    }


def execution_class(execution: dict[str, Any]) -> str:
    command_text = str(execution.get("command_text") or "")
    command = " ".join(command_list(execution))
    haystack = f"{command_text} {command}"
    if "analysis/mt5_tester_run.py" in haystack:
        return "mt5_tester_run"
    if "analysis/mt5_compile.py" in haystack:
        return "mt5_compile"
    if "analysis/mt5_agent_csv_archive.py" in haystack:
        return "mt5_agent_csv_archive"
    if "analysis/mt5_forward_collect.py" in haystack:
        return "mt5_forward_collect"
    if "analysis/mt5_optimization_recommend.py" in haystack:
        return "mt5_optimization_recommendation_refresh"
    return "other" if haystack.strip() else ""


def numeric_text_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def timeout_deadline_from_now(timeout_seconds: Any, *, now_epoch: float | None = None) -> dict[str, Any]:
    seconds = numeric_text_value(timeout_seconds)
    if seconds is None or seconds < 0:
        return {
            "timeout_start_reference_at": "",
            "timeout_deadline_if_started_now": "",
            "timeout_deadline_epoch_if_started_now": None,
        }
    start_epoch = time.time() if now_epoch is None else now_epoch
    deadline_epoch = start_epoch + seconds
    return {
        "timeout_start_reference_at": datetime.fromtimestamp(start_epoch).strftime(TIME_FORMAT),
        "timeout_deadline_if_started_now": datetime.fromtimestamp(deadline_epoch).strftime(TIME_FORMAT),
        "timeout_deadline_epoch_if_started_now": round(deadline_epoch, 3),
    }


def compact_number_text(value: Any) -> str:
    numeric = numeric_text_value(value)
    if numeric is None:
        return str(value)
    return str(int(numeric)) if numeric.is_integer() else str(numeric)


def recent_xml_rows_text(rows: Any) -> str:
    if not isinstance(rows, dict):
        return ""
    row_parts = [
        f"{key}={compact_number_text(rows.get(key))}"
        for key in ("back", "forward")
        if rows.get(key) is not None
    ]
    if not row_parts:
        return ""
    suffix_parts: list[str] = []
    ratios = rows.get("ratio_vs_full_factorial")
    if isinstance(ratios, dict):
        ratio_parts = []
        for key in ("back", "forward"):
            numeric = numeric_text_value(ratios.get(key))
            if numeric is not None:
                ratio_parts.append(f"{key}={numeric * 100:.1f}%")
        if ratio_parts:
            suffix_parts.append(f"ratio_vs_full_factorial={'/'.join(ratio_parts)}")
    source = str(rows.get("source") or "")
    if source:
        suffix_parts.append(f"source={source}")
    suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
    return f"{', '.join(row_parts)}{suffix}"


def execution_focus_side(execution: dict[str, Any]) -> str:
    focus_side = str(execution.get("focus_side") or "").strip().lower()
    if focus_side:
        return focus_side
    command = command_list(execution)
    return command_option_value(command, "--focus-side").strip().lower()


def focus_side_matches(focus_side: str, execution: dict[str, Any]) -> bool:
    normalized = focus_side.strip().lower()
    if not normalized:
        return True
    if normalized not in {"buy", "sell", "both"}:
        return False
    return execution_focus_side(execution) == normalized


def target_matches(target: str, *, key: str, label: str, execution: dict[str, Any], action: dict[str, Any]) -> bool:
    normalized = target.strip().lower()
    command_text = str(execution.get("command_text") or "")
    command = " ".join(command_list(execution))
    command_haystack = f"{command_text} {command}"
    if normalized in AUTO_MT5_TARGETS:
        return "analysis/mt5_tester_run.py" in command_haystack
    if normalized in {key.lower(), label.lower(), str(execution.get("kind", "")).lower()}:
        return True
    area = str(action.get("area") or "").lower()
    if normalized and normalized == area:
        return True
    return False


def follow_up_for_selection(evidence: dict[str, Any], *, primary_key: str, primary: dict[str, Any]) -> dict[str, Any]:
    if primary_key != "follow_up_execution":
        explicit = evidence.get("follow_up_execution") if isinstance(evidence.get("follow_up_execution"), dict) else {}
        if explicit:
            return execution_summary(explicit)
    return inline_follow_up_summary(primary)


def follow_up_archive_for_selection(evidence: dict[str, Any], *, primary_key: str) -> dict[str, Any]:
    if primary_key == "follow_up_execution":
        return {}
    archive = (
        evidence.get("follow_up_archive_preview")
        if isinstance(evidence.get("follow_up_archive_preview"), dict)
        else {}
    )
    return execution_summary(archive) if archive else {}


def action_context_summary(evidence: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for key in ACTION_CONTEXT_KEYS:
        value = evidence.get(key)
        if isinstance(value, dict) and value:
            context[key] = value
    return context


def related_execution_summaries(evidence: dict[str, Any], *, primary_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in RELATED_EXECUTION_KEYS:
        if key == primary_key:
            continue
        execution = evidence.get(key)
        if not isinstance(execution, dict) or not execution:
            continue
        summary = execution_summary(execution)
        if not summary.get("command"):
            continue
        rows.append({"key": key, "label": key, "execution": summary})
    return rows


def select_next_action_plan(
    gate: dict[str, Any],
    *,
    target: str = DEFAULT_TARGET,
    focus_side: str = "",
) -> dict[str, Any]:
    selected_target = target.strip() or DEFAULT_TARGET
    selected_focus_side = focus_side.strip().lower()
    auto_target = selected_target.lower() in AUTO_MT5_TARGETS
    actions = gate.get("next_actions") if isinstance(gate.get("next_actions"), list) else []
    for action in actions:
        if not isinstance(action, dict):
            continue
        evidence = action.get("evidence") if isinstance(action.get("evidence"), dict) else {}
        for key, label in EXECUTION_LABELS:
            execution = evidence.get(key) if isinstance(evidence.get(key), dict) else {}
            if not execution:
                continue
            if not target_matches(selected_target, key=key, label=label, execution=execution, action=action):
                continue
            if not focus_side_matches(selected_focus_side, execution):
                continue
            archive_key = ARCHIVE_PREVIEW_KEYS.get(key, "")
            archive_preview = evidence.get(archive_key) if archive_key and isinstance(evidence.get(archive_key), dict) else {}
            compile_execution = evidence.get("compile") if isinstance(evidence.get("compile"), dict) else {}
            refit = evidence.get("stable_candidate_refit") if isinstance(evidence.get("stable_candidate_refit"), dict) else {}
            primary = execution_summary(execution)
            primary_class = execution_class(primary)
            resolved_target = label if auto_target else selected_target
            return {
                "found": True,
                "target": resolved_target,
                "generated_at": gate.get("generated_at", ""),
                "promotion_generated_at": gate.get("generated_at", ""),
                "decision": gate.get("decision", ""),
                "promotion_decision": gate.get("decision", ""),
                "action": {
                    "priority": action.get("priority"),
                    "area": action.get("area", ""),
                    "action": action.get("action", ""),
                    "reason": action.get("reason", ""),
                },
                "execution_key": key,
                "label": label,
                "stable_candidate_refit": dict(refit),
                "primary": primary,
                "primary_execution_class": primary_class,
                "primary_is_mt5_tester_run": primary_class == "mt5_tester_run",
                "evidence_role": primary.get("evidence_role", ""),
                "diagnostic_only": primary.get("diagnostic_only", ""),
                "promotion_evidence": primary.get("promotion_evidence", ""),
                "evidence_note": primary.get("evidence_note", ""),
                "archive_preview": execution_summary(archive_preview) if archive_preview else {},
                "follow_up": follow_up_for_selection(evidence, primary_key=key, primary=execution),
                "follow_up_archive_preview": follow_up_archive_for_selection(evidence, primary_key=key),
                "compile": execution_summary(compile_execution) if compile_execution else {},
                "action_context": action_context_summary(evidence),
                "related_executions": related_execution_summaries(evidence, primary_key=key),
            }
    return {
        "found": False,
        "target": selected_target,
        "focus_side_filter": selected_focus_side,
        "generated_at": gate.get("generated_at", ""),
        "promotion_generated_at": gate.get("generated_at", ""),
        "decision": gate.get("decision", ""),
        "promotion_decision": gate.get("decision", ""),
        "reason": (
            f"No matching MT5 execution found for target={selected_target}"
            + (f", focus_side={selected_focus_side}" if selected_focus_side else "")
        ),
    }


def declared_outputs_text(outputs: Any) -> str:
    if not isinstance(outputs, dict) or not outputs:
        return ""
    return ", ".join(f"{key}={value}" for key, value in outputs.items() if value)


def compact_context_text(key: str, value: dict[str, Any]) -> str:
    if key == "score_weight_set_result":
        parts = [
            f"side={value.get('side')}",
            f"written={value.get('written')}",
            f"skipped={value.get('skipped')}",
            f"skip_reason={value.get('skip_reason')}",
            f"wf={value.get('walk_forward_status')}",
            f"output_set={value.get('output_set')}",
        ]
        return ", ".join(part for part in parts if not part.endswith("=None") and not part.endswith("="))
    if key == "score_weight_follow_up":
        parts = [
            f"status={value.get('status')}",
            f"sample_shortage={value.get('sample_shortage')}",
            f"regime={value.get('regime_dimension')}:{value.get('regime_group')}",
            f"regime_status={value.get('regime_status')}",
            (
                "walk_missing="
                f"{value.get('walk_forward_missing_test_weight_count')}/"
                f"{value.get('walk_forward_required_test_weight_count')}"
            ),
            (
                "walk_folds="
                f"{value.get('walk_forward_folds_with_weight_trades')}/"
                f"{value.get('walk_forward_required_folds_with_weight_trades')}"
            ),
            (
                "regime_missing="
                f"{value.get('regime_missing_test_weight_count')}/"
                f"{value.get('regime_required_test_weight_count')}"
            ),
            (
                "regime_folds="
                f"{value.get('regime_folds_with_weight_trades')}/"
                f"{value.get('regime_required_folds_with_weight_trades')}"
            ),
            f"recommendation={value.get('recommendation')}",
        ]
        return ", ".join(part for part in parts if "None" not in part and not part.endswith("=") and part != "regime=:")
    if key == "stable_candidate_refit":
        parts = [
            f"side={value.get('side')}",
            f"driver={value.get('driver')}",
            f"kind={value.get('kind')}",
            f"focus={value.get('focus_side')}",
            f"reason={value.get('reason')}",
        ]
        return ", ".join(part for part in parts if not part.endswith("=None") and not part.endswith("="))
    if key == "stable_candidate_refit_completed":
        parts = [f"kind={value.get('kind')}", f"side={value.get('side')}"]
        decision = value.get("decision") if isinstance(value.get("decision"), dict) else {}
        if isinstance(decision.get("reasons"), list) and decision.get("reasons"):
            parts.append("reason=" + "; ".join(str(item) for item in decision.get("reasons")[:3]))
        return ", ".join(part for part in parts if not part.endswith("=None") and not part.endswith("="))
    if key == "previous_refit":
        parts = [
            f"kind={value.get('kind')}",
            f"side={value.get('side')}",
            f"status={value.get('status')}",
            f"pf={value.get('pf')}",
            f"avg_price_r={value.get('avg_price_r')}",
        ]
        return ", ".join(part for part in parts if not part.endswith("=None") and not part.endswith("="))
    if key == "upstream_chronological_rejection":
        failed_splits = value.get("failed_splits") if isinstance(value.get("failed_splits"), list) else []
        split_names = [
            str(row.get("group"))
            for row in failed_splits
            if isinstance(row, dict) and row.get("group") not in (None, "")
        ][:4]
        parts = [
            "failed_splits=" + "/".join(split_names) if split_names else "",
            f"weak_time={len(value.get('weak_time_segments', [])) if isinstance(value.get('weak_time_segments'), list) else 0}",
            f"weak_trend={len(value.get('weak_trend_segments', [])) if isinstance(value.get('weak_trend_segments'), list) else 0}",
            f"weak_sl_tp={len(value.get('weak_sl_tp_segments', [])) if isinstance(value.get('weak_sl_tp_segments'), list) else 0}",
        ]
        return ", ".join(part for part in parts if part)
    return ", ".join(f"{item_key}={item_value}" for item_key, item_value in value.items())


def run_command(command: list[str]) -> dict[str, Any]:
    started = time.time()
    if not command:
        return {"ok": False, "returncode": None, "elapsed_seconds": 0.0, "reason": "missing command"}
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "elapsed_seconds": round(time.time() - started, 3),
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def refresh_ready_status(status_path: str | Path, status_md_path: str | Path = DEFAULT_READY_STATUS_MD) -> dict[str, Any]:
    command = [
        "python3",
        "analysis/mt5_tester_status.py",
        "--output-json",
        str(status_path),
    ]
    if status_md_path:
        command.extend(["--output-md", str(status_md_path)])
    result = run_command(command)
    status_payload: dict[str, Any] = {}
    output_json = Path(status_path)
    if output_json.exists():
        try:
            loaded = json.loads(output_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            loaded = {}
        if isinstance(loaded, dict):
            status_payload = loaded
    refresh_ok = result.get("returncode") == 0 or (
        result.get("returncode") == 2 and bool(status_payload)
    )
    return {
        **result,
        "ok": refresh_ok,
        "status_ok": status_payload.get("ok", ""),
        "status_operational_status": status_payload.get("operational_status", ""),
        "status_ready_for_tester_launch": status_payload.get("ready_for_tester_launch", ""),
        "status_next_action_execution_ready": (
            status_payload.get("next_action_execution", {}).get("ready", "")
            if isinstance(status_payload.get("next_action_execution"), dict)
            else ""
        ),
        "status_next_action_local_execution_ready": (
            status_payload.get("next_action_local_execution", {}).get("ready", "")
            if isinstance(status_payload.get("next_action_local_execution"), dict)
            else ""
        ),
        "command": command,
        "command_text": " ".join(command),
        "output_json": str(status_path),
        "output_md": str(status_md_path),
    }


def tester_run_artifact_summary(path: str) -> dict[str, Any]:
    if not path:
        return {}
    source = Path(path)
    summary: dict[str, Any] = {"path": path, "exists": source.exists()}
    if not source.exists():
        return summary
    payload = load_json(source)
    report_paths = payload.get("report_paths") if isinstance(payload.get("report_paths"), dict) else {}
    terminal_run = payload.get("terminal_run") if isinstance(payload.get("terminal_run"), dict) else {}
    risk_preset = payload.get("risk_preset") if isinstance(payload.get("risk_preset"), dict) else {}
    summary.update(
        {
            "generated_at": payload.get("generated_at", ""),
            "ok": payload.get("ok"),
            "blocked": payload.get("blocked"),
            "blocked_components": payload.get("blocked_components", {}),
            "terminal_failed": payload.get("terminal_failed"),
            "source_time_blocked": payload.get("source_time_blocked"),
            "report_fallback_blocked": payload.get("report_fallback_blocked"),
            "report_source": report_paths.get("source", ""),
            "agent_csv_archive_run_id": payload.get("agent_csv_archive_run_id", ""),
            "terminal_elapsed_seconds": terminal_run.get("elapsed_seconds", ""),
            "terminal_returncode": terminal_run.get("returncode", ""),
            "terminal_timeout": terminal_run.get("timeout", ""),
            "risk_preset_ok": risk_preset.get("ok", ""),
        }
    )
    return summary


def optimization_artifact_summary(path: str) -> dict[str, Any]:
    if not path:
        return {}
    source = Path(path)
    summary: dict[str, Any] = {"path": path, "exists": source.exists()}
    if not source.exists():
        return summary
    payload = load_json(source)
    report = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    overall = report.get("overall") if isinstance(report.get("overall"), dict) else {}
    single_test = (
        report.get("single_test_performance")
        if isinstance(report.get("single_test_performance"), dict)
        else {}
    )
    tester_xml = report.get("tester_xml") if isinstance(report.get("tester_xml"), dict) else {}
    back = tester_xml.get("back") if isinstance(tester_xml.get("back"), dict) else {}
    forward = tester_xml.get("forward") if isinstance(tester_xml.get("forward"), dict) else {}
    source_time = report.get("source_time_diagnostics") if isinstance(report.get("source_time_diagnostics"), dict) else {}
    summary.update(
        {
            "generated_at": report.get("generated_at", ""),
            "ok": report.get("ok", payload.get("ok")),
            "closed": single_test.get("closed", overall.get("closed")),
            "wins": single_test.get("wins", overall.get("wins")),
            "losses": single_test.get("losses", overall.get("losses")),
            "pf": single_test.get("pf", overall.get("pf")),
            "avg_price_r": overall.get("avg_price_r"),
            "expectancy_price_r": overall.get("expectancy_price_r"),
            "max_drawdown_price_r": overall.get("max_drawdown_price_r"),
            "net_profit": single_test.get("net_profit", overall.get("net_profit")),
            "single_test_source": single_test.get("source", ""),
            "single_test_expected_payoff": single_test.get("expected_payoff", ""),
            "single_test_max_losing_streak": single_test.get(
                "max_losing_streak",
                single_test.get("max_consecutive_loss_count", ""),
            ),
            "back_rows": back.get("rows"),
            "forward_rows": forward.get("rows"),
            "source_time_ok": source_time.get("ok", ""),
        }
    )
    return summary


def recommendation_artifact_summary(path: str) -> dict[str, Any]:
    if not path:
        return {}
    source = Path(path)
    summary: dict[str, Any] = {"path": path, "exists": source.exists()}
    if not source.exists():
        return summary
    payload = load_json(source)
    recommendation = payload.get("recommendation") if isinstance(payload.get("recommendation"), dict) else payload
    decision = recommendation.get("decision") if isinstance(recommendation.get("decision"), dict) else {}
    set_metadata = recommendation.get("set_metadata") if isinstance(recommendation.get("set_metadata"), dict) else {}
    summary.update(
        {
            "generated_at": recommendation.get("generated_at", payload.get("generated_at", "")),
            "ok": payload.get("ok", ""),
            "adoptable": decision.get("adoptable", ""),
            "reasons": decision.get("reasons", []),
            "next_set": set_metadata.get("path", ""),
            "skipped_write": set_metadata.get("skipped_write", ""),
            "skip_reason": set_metadata.get("skip_reason", ""),
        }
    )
    return summary


def forward_report_artifact_summary(path: str) -> dict[str, Any]:
    if not path:
        return {}
    source = Path(path)
    summary: dict[str, Any] = {"path": path, "exists": source.exists()}
    if not source.exists():
        return summary
    payload = load_json(source)
    report = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    overall = report.get("overall") if isinstance(report.get("overall"), dict) else {}
    checks = report.get("checks") if isinstance(report.get("checks"), dict) else {}
    summary.update(
        {
            "generated_at": payload.get("generated_at", ""),
            "ok": payload.get("ok"),
            "closed": overall.get("closed"),
            "pf": overall.get("pf"),
            "avg_price_r": overall.get("avg_price_r"),
            "ready_for_demo_review": report.get("ready_for_demo_review"),
            "risk_exposure_ok": (
                checks.get("risk_exposure", {}).get("ok")
                if isinstance(checks.get("risk_exposure"), dict)
                else ""
            ),
        }
    )
    return summary


def agent_csv_archive_artifact_summary(path: str) -> dict[str, Any]:
    if not path:
        return {}
    source = Path(path)
    summary: dict[str, Any] = {"path": path, "exists": source.exists()}
    if not source.exists():
        return summary
    payload = load_json(source)
    coverage = payload.get("source_time_coverage") if isinstance(payload.get("source_time_coverage"), dict) else {}
    summary.update(
        {
            "generated_at": payload.get("generated_at", ""),
            "ok": payload.get("ok"),
            "execute": payload.get("execute"),
            "count": payload.get("count"),
            "run_id": payload.get("run_id", ""),
            "planned_archive_dir": payload.get("planned_archive_dir", ""),
            "include_source_time": payload.get("include_source_time", ""),
            "close_rows": coverage.get("close_rows", ""),
            "close_rows_with_server_time": coverage.get("close_rows_with_server_time", ""),
            "first_server_time": coverage.get("first_server_time", ""),
            "last_server_time": coverage.get("last_server_time", ""),
            "span_days": coverage.get("span_days", ""),
        }
    )
    return summary


def generic_json_artifact_summary(path: str) -> dict[str, Any]:
    if not path:
        return {}
    source = Path(path)
    summary: dict[str, Any] = {"path": path, "exists": source.exists()}
    if not source.exists():
        return summary
    payload = load_json(source)
    summary.update({"generated_at": payload.get("generated_at", ""), "ok": payload.get("ok", "")})
    return summary


def execution_evidence_role(execution: dict[str, Any]) -> dict[str, Any]:
    kind = str(execution.get("kind") or "").lower()
    config = str(execution.get("config") or "").lower()
    set_path = str(execution.get("set") or "").lower()
    command = " ".join(command_list(execution)).lower()
    haystack = " ".join([kind, config, set_path, command])
    if kind == "score_weight_sample_collection" or "sample_collection" in haystack:
        return {
            "evidence_role": "diagnostic_sample_collection",
            "diagnostic_only": True,
            "promotion_evidence": False,
            "evidence_note": (
                "Diagnostic sample collection only; collect score-refit samples and do not use as "
                "promotion evidence."
            ),
        }
    return {}


def execution_artifact_summary(execution: dict[str, Any]) -> dict[str, Any]:
    outputs = execution.get("planned_outputs") if isinstance(execution.get("planned_outputs"), dict) else {}
    summary: dict[str, Any] = execution_evidence_role(execution)
    if outputs.get("output_json"):
        if execution_class(execution) == "mt5_agent_csv_archive":
            summary["agent_csv_archive"] = agent_csv_archive_artifact_summary(str(outputs.get("output_json")))
        elif execution_class(execution) == "mt5_optimization_recommendation_refresh":
            summary["recommendation"] = recommendation_artifact_summary(str(outputs.get("output_json")))
        elif execution_class(execution) == "mt5_forward_collect":
            summary["forward_report"] = forward_report_artifact_summary(str(outputs.get("output_json")))
        elif execution_class(execution) == "mt5_tester_run":
            summary["tester_run"] = tester_run_artifact_summary(str(outputs.get("output_json")))
        else:
            summary["output_json"] = generic_json_artifact_summary(str(outputs.get("output_json")))
    if outputs.get("optimization_output_json"):
        summary["optimization"] = optimization_artifact_summary(str(outputs.get("optimization_output_json")))
    if outputs.get("recommendation_output_json"):
        summary["recommendation"] = recommendation_artifact_summary(str(outputs.get("recommendation_output_json")))
    return summary


def recommendation_refresh_artifact_validation(execution: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    outputs = execution.get("planned_outputs") if isinstance(execution.get("planned_outputs"), dict) else {}
    recommendation = artifacts.get("recommendation") if isinstance(artifacts.get("recommendation"), dict) else {}
    reasons: list[str] = []
    if not outputs.get("output_json"):
        reasons.append("missing_recommendation_refresh_output_json_plan")
    if not recommendation:
        reasons.append("missing_recommendation_refresh_summary")
    else:
        if recommendation.get("exists") is not True:
            reasons.append("missing_recommendation_refresh_artifact")
        if recommendation.get("ok") is False:
            reasons.append("recommendation_refresh_artifact_not_ok")
        if recommendation.get("adoptable") == "":
            reasons.append("recommendation_refresh_decision_missing")
    return {
        "required": True,
        "ok": not reasons,
        "reasons": reasons,
        "output_json": outputs.get("output_json", ""),
        "execution_class": execution_class(execution),
        "adoptable": recommendation.get("adoptable", ""),
        "skipped_write": recommendation.get("skipped_write", ""),
        "skip_reason": recommendation.get("skip_reason", ""),
    }


def archive_preview_artifact_validation(execution: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    if not command_list(execution):
        return {"required": False, "ok": True, "reasons": []}
    outputs = execution.get("planned_outputs") if isinstance(execution.get("planned_outputs"), dict) else {}
    archive = artifacts.get("agent_csv_archive") if isinstance(artifacts.get("agent_csv_archive"), dict) else {}
    reasons: list[str] = []
    if execution_class(execution) != "mt5_agent_csv_archive":
        reasons.append("archive_preview_command_not_archive")
    if not outputs.get("output_json"):
        reasons.append("missing_archive_preview_output_json_plan")
    elif not archive:
        reasons.append("missing_archive_preview_summary")
    else:
        if archive.get("exists") is not True:
            reasons.append("missing_archive_preview_artifact")
        else:
            if archive.get("ok") is not True:
                reasons.append("archive_preview_artifact_not_ok")
            if archive.get("execute") is not False:
                reasons.append("archive_preview_not_preview_mode")
    return {
        "required": True,
        "ok": not reasons,
        "reasons": reasons,
        "output_json": outputs.get("output_json", ""),
        "execution_class": execution_class(execution),
    }


def add_archive_preview_command_failure(
    validation: dict[str, Any],
    result: dict[str, Any],
    reason: str = "archive_preview_command_failed",
) -> dict[str, Any]:
    if result.get("ok") is True:
        return validation
    reasons = validation.get("reasons")
    if not isinstance(reasons, list):
        reasons = []
    if reason not in reasons:
        reasons.append(reason)
    validation["reasons"] = reasons
    validation["ok"] = False
    return validation


def follow_up_artifact_validation(execution: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    if not command_list(execution):
        return {"required": False, "ok": True, "reasons": []}
    outputs = execution.get("planned_outputs") if isinstance(execution.get("planned_outputs"), dict) else {}
    klass = execution_class(execution)
    reasons: list[str] = []
    if klass == "mt5_forward_collect":
        forward = artifacts.get("forward_report") if isinstance(artifacts.get("forward_report"), dict) else {}
        if not outputs.get("output_json"):
            reasons.append("missing_follow_up_output_json_plan")
        if not forward:
            reasons.append("missing_follow_up_forward_report_summary")
        else:
            if forward.get("exists") is not True:
                reasons.append("missing_follow_up_forward_report_artifact")
            if forward.get("ok") is False:
                reasons.append("follow_up_forward_report_not_ok")
            closed = numeric_text_value(forward.get("closed"))
            if closed is None:
                reasons.append("follow_up_forward_report_closed_missing")
        return {
            "required": True,
            "ok": not reasons,
            "reasons": reasons,
            "output_json": outputs.get("output_json", ""),
            "execution_class": klass,
        }
    if outputs.get("output_json"):
        generic = artifacts.get("output_json") if isinstance(artifacts.get("output_json"), dict) else {}
        if not generic:
            reasons.append("missing_follow_up_output_json_summary")
        else:
            if generic.get("exists") is not True:
                reasons.append("missing_follow_up_output_json_artifact")
            if generic.get("ok") is False:
                reasons.append("follow_up_output_json_not_ok")
        return {
            "required": True,
            "ok": not reasons,
            "reasons": reasons,
            "output_json": outputs.get("output_json", ""),
            "execution_class": klass,
        }
    return {"required": False, "ok": True, "reasons": [], "execution_class": klass}


def primary_tester_artifact_validation(plan: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    if plan.get("primary_is_mt5_tester_run") is not True:
        return {"required": False, "ok": True, "reasons": []}
    primary = plan.get("primary") if isinstance(plan.get("primary"), dict) else {}
    outputs = primary.get("planned_outputs") if isinstance(primary.get("planned_outputs"), dict) else {}
    tester = artifacts.get("tester_run") if isinstance(artifacts.get("tester_run"), dict) else {}
    reasons: list[str] = []
    if not outputs.get("output_json"):
        reasons.append("missing_primary_output_json_plan")
    if not tester:
        reasons.append("missing_primary_tester_run_summary")
    else:
        if tester.get("exists") is not True:
            reasons.append("missing_primary_tester_run_artifact")
        if tester.get("ok") is not True:
            reasons.append("primary_tester_run_not_ok")
        if tester.get("blocked") is True:
            reasons.append("primary_tester_run_blocked")
        if tester.get("terminal_failed") is True:
            reasons.append("primary_tester_terminal_failed")
        if tester.get("source_time_blocked") is True:
            reasons.append("primary_tester_source_time_blocked")
        if tester.get("report_fallback_blocked") is True:
            reasons.append("primary_tester_report_fallback_blocked")
    return {
        "required": True,
        "ok": not reasons,
        "reasons": reasons,
        "output_json": outputs.get("output_json", ""),
    }


def primary_artifact_validation(plan: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    primary = plan.get("primary") if isinstance(plan.get("primary"), dict) else {}
    klass = execution_class(primary)
    if klass == "mt5_tester_run":
        return primary_tester_artifact_validation(plan, artifacts)
    if klass == "mt5_optimization_recommendation_refresh":
        return recommendation_refresh_artifact_validation(primary, artifacts)
    return {"required": False, "ok": True, "reasons": [], "execution_class": klass}


def primary_returncode_accepted(execution: dict[str, Any], result: dict[str, Any], validation: dict[str, Any]) -> bool:
    returncode = result.get("returncode")
    if returncode == 0:
        return True
    if execution_class(execution) == "mt5_optimization_recommendation_refresh":
        return returncode == 2 and validation.get("ok") is True
    return False


def primary_returncode_acceptance_reason(execution: dict[str, Any], result: dict[str, Any]) -> str:
    if execution_class(execution) == "mt5_optimization_recommendation_refresh" and result.get("returncode") == 2:
        return "recommendation_refresh_completed_not_adoptable"
    return ""


def comparable_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def ready_status_runner_values(status: dict[str, Any]) -> dict[str, Any]:
    runner = status.get("next_action_runner") if isinstance(status.get("next_action_runner"), dict) else {}
    primary_outputs = runner.get("primary_planned_outputs", {})
    archive_outputs = runner.get("archive_preview_planned_outputs", {})
    follow_up_outputs = runner.get("follow_up_planned_outputs", {})
    follow_up_archive_outputs = runner.get("follow_up_archive_preview_planned_outputs", {})
    return {
        "target": runner.get("target", ""),
        "promotion_generated_at": runner.get("promotion_generated_at")
        or runner.get("runner_promotion_generated_at", ""),
        "promotion_decision": runner.get("promotion_decision") or runner.get("runner_promotion_decision", ""),
        "execution_key": runner.get("execution_key", ""),
        "kind": runner.get("kind", ""),
        "focus_side": runner.get("focus_side", ""),
        "optimization_mode": runner.get("optimization_mode", ""),
        "config": runner.get("config", ""),
        "set": runner.get("set", ""),
        "output_set": runner.get("output_set", ""),
        "agent_csv_archive_run_id": runner.get("agent_csv_archive_run_id", ""),
        "command_text": runner.get("command_text", ""),
        "planned_outputs": runner.get(
            "planned_outputs",
            planned_outputs_bundle(
                primary_outputs,
                archive_outputs,
                follow_up_outputs,
                follow_up_archive_outputs,
            ),
        ),
        "primary_planned_outputs": primary_outputs,
        "archive_preview_planned_outputs": archive_outputs,
        "follow_up_planned_outputs": follow_up_outputs,
        "follow_up_archive_preview_planned_outputs": follow_up_archive_outputs,
        "evidence_role": runner.get("evidence_role", ""),
        "diagnostic_only": runner.get("diagnostic_only", ""),
        "promotion_evidence": runner.get("promotion_evidence", ""),
    }


def plan_runner_values(plan: dict[str, Any]) -> dict[str, Any]:
    primary = plan.get("primary") if isinstance(plan.get("primary"), dict) else {}
    archive_preview = plan.get("archive_preview") if isinstance(plan.get("archive_preview"), dict) else {}
    follow_up = plan.get("follow_up") if isinstance(plan.get("follow_up"), dict) else {}
    follow_up_archive_preview = (
        plan.get("follow_up_archive_preview")
        if isinstance(plan.get("follow_up_archive_preview"), dict)
        else {}
    )
    primary_outputs = primary.get("planned_outputs", {})
    archive_outputs = archive_preview.get("planned_outputs", {})
    follow_up_outputs = follow_up.get("planned_outputs", {})
    follow_up_archive_outputs = follow_up_archive_preview.get("planned_outputs", {})
    return {
        "target": plan.get("target", ""),
        "promotion_generated_at": plan.get("generated_at", ""),
        "promotion_decision": plan.get("decision", ""),
        "execution_key": plan.get("execution_key", ""),
        "kind": primary.get("kind", ""),
        "focus_side": primary.get("focus_side", ""),
        "optimization_mode": primary.get("optimization_mode", ""),
        "config": primary.get("config", ""),
        "set": primary.get("set", ""),
        "output_set": primary.get("output_set", ""),
        "agent_csv_archive_run_id": primary.get("agent_csv_archive_run_id", ""),
        "command_text": primary.get("command_text", ""),
        "planned_outputs": planned_outputs_bundle(
            primary_outputs,
            archive_outputs,
            follow_up_outputs,
            follow_up_archive_outputs,
        ),
        "primary_planned_outputs": primary_outputs,
        "archive_preview_planned_outputs": archive_outputs,
        "follow_up_planned_outputs": follow_up_outputs,
        "follow_up_archive_preview_planned_outputs": follow_up_archive_outputs,
        "evidence_role": primary.get("evidence_role", ""),
        "diagnostic_only": primary.get("diagnostic_only", ""),
        "promotion_evidence": primary.get("promotion_evidence", ""),
    }


def ready_status_preflight(
    plan: dict[str, Any],
    *,
    status_path: str | Path,
    max_age_seconds: int,
) -> dict[str, Any]:
    path = Path(status_path)
    result: dict[str, Any] = {
        "ok": False,
        "path": str(status_path),
        "exists": path.exists(),
        "age_seconds": None,
        "max_age_seconds": max_age_seconds,
        "reasons": [],
        "mismatches": [],
    }
    if not path.exists():
        result["reasons"].append("missing_ready_status")
        return result
    age_seconds = max(0.0, time.time() - path.stat().st_mtime)
    result["age_seconds"] = round(age_seconds, 1)
    if age_seconds > max_age_seconds:
        result["reasons"].append("ready_status_stale")
    status = load_json(path)
    if not status:
        result["reasons"].append("invalid_ready_status_json")
        return result
    readiness_key = (
        "next_action_execution"
        if plan.get("primary_is_mt5_tester_run") is True
        else "next_action_local_execution"
    )
    execution = (
        status.get(readiness_key)
        if isinstance(status.get(readiness_key), dict)
        else {}
    )
    runner = status.get("next_action_runner") if isinstance(status.get("next_action_runner"), dict) else {}
    result["status_generated_at"] = status.get("generated_at", "")
    result["readiness_key"] = readiness_key
    result["selected_execution_ready"] = execution.get("ready")
    result["selected_execution_status"] = execution.get("status", "")
    result["selected_execution_reasons"] = execution.get("reasons", [])
    result["next_action_execution_ready"] = execution.get("ready")
    result["next_action_execution_status"] = execution.get("status", "")
    result["next_action_execution_reasons"] = execution.get("reasons", [])
    if readiness_key == "next_action_local_execution":
        result["next_action_local_execution_ready"] = execution.get("ready")
        result["next_action_local_execution_status"] = execution.get("status", "")
        result["next_action_local_execution_reasons"] = execution.get("reasons", [])
    result["current_for_execution"] = runner.get("current_for_execution")
    if execution.get("ready") is not True:
        result["reasons"].append(f"{readiness_key}_not_ready")
    if runner.get("current_for_execution") is not True:
        stale_reason = str(runner.get("gate_stale_reason") or "")
        suffix = f":{stale_reason}" if stale_reason else ""
        result["reasons"].append(f"ready_status_runner_not_current{suffix}")

    status_values = ready_status_runner_values(status)
    plan_values = plan_runner_values(plan)
    mismatches = [
        key
        for key, value in plan_values.items()
        if comparable_text(value) != comparable_text(status_values.get(key, ""))
    ]
    result["mismatches"] = mismatches
    if mismatches:
        result["reasons"].append("ready_status_plan_mismatch")
    result["ok"] = not result["reasons"]
    return result


def execute_plan(
    plan: dict[str, Any],
    *,
    execute: bool,
    run_archive_preview: bool,
    run_compile: bool,
    run_follow_up: bool,
    allow_non_tester_primary: bool,
    ready_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = dict(plan)
    report["dry_run"] = not execute
    report["run_archive_preview"] = run_archive_preview
    report["run_compile"] = run_compile
    report["run_follow_up"] = run_follow_up
    report["allow_non_tester_primary"] = allow_non_tester_primary
    if ready_status is not None:
        report["ready_status"] = ready_status
    report["executions"] = {}
    if not plan.get("found"):
        report["ok"] = False
        return report
    if not execute and not run_archive_preview:
        report["ok"] = True
        return report
    if execute and plan.get("primary_is_mt5_tester_run") is not True and not allow_non_tester_primary:
        report["ok"] = False
        report["blocked_before_primary"] = "non_tester_primary"
        report["reason"] = (
            "selected primary command does not launch analysis/mt5_tester_run.py; "
            "rerun with --allow-non-tester-primary if this local follow-up is intentional"
        )
        return report
    if execute and ready_status is not None and ready_status.get("ok") is not True:
        report["ok"] = False
        report["blocked_before_primary"] = "ready_status_not_ready"
        readiness_key = str(ready_status.get("readiness_key") or "next_action_execution")
        if readiness_key == "next_action_local_execution":
            report["reason"] = "next_action_local_execution is not ready for this selected local next action"
        else:
            report["reason"] = "next_action_execution is not ready for this selected MT5 Tester plan"
        return report
    if run_archive_preview and command_list(plan.get("archive_preview")):
        archive_preview_execution = plan.get("archive_preview") if isinstance(plan.get("archive_preview"), dict) else {}
        report["executions"]["archive_preview"] = run_command(command_list(archive_preview_execution))
        archive_preview_artifacts = execution_artifact_summary(archive_preview_execution)
        report.setdefault("post_execution_artifacts", {})["archive_preview"] = archive_preview_artifacts
        archive_preview_validation = archive_preview_artifact_validation(
            archive_preview_execution,
            archive_preview_artifacts,
        )
        archive_preview_validation = add_archive_preview_command_failure(
            archive_preview_validation,
            report["executions"]["archive_preview"],
        )
        report.setdefault("post_execution_validation", {})["archive_preview"] = archive_preview_validation
        if report["executions"]["archive_preview"].get("ok") is not True:
            report["ok"] = False
            report["blocked_before_primary"] = "archive_preview_failed"
            report["reason"] = "Agent CSV archive preview failed before MT5 Tester primary launch"
            return report
        if archive_preview_validation.get("ok") is not True:
            report["ok"] = False
            report["blocked_before_primary"] = "archive_preview_artifact_not_ok"
            report["reason"] = "Agent CSV archive preview returned success, but expected preview artifact is not usable"
            return report
    if not execute:
        report["ok"] = True
        return report
    if run_compile and command_list(plan.get("compile")):
        report["executions"]["compile"] = run_command(command_list(plan.get("compile")))
        if report["executions"]["compile"].get("ok") is not True:
            report["ok"] = False
            report["blocked_before_primary"] = "compile_failed"
            return report
    primary_execution = plan.get("primary") if isinstance(plan.get("primary"), dict) else {}
    report["executions"]["primary"] = run_command(command_list(primary_execution))
    primary_artifacts = execution_artifact_summary(primary_execution)
    report.setdefault("post_execution_artifacts", {})["primary"] = primary_artifacts
    primary_validation = primary_artifact_validation(plan, primary_artifacts)
    report.setdefault("post_execution_validation", {})["primary"] = primary_validation
    primary_ok = primary_returncode_accepted(
        primary_execution,
        report["executions"]["primary"],
        primary_validation,
    )
    if primary_ok and report["executions"]["primary"].get("ok") is not True:
        report["executions"]["primary"]["accepted_returncode"] = True
        report["executions"]["primary"]["accepted_returncode_reason"] = primary_returncode_acceptance_reason(
            primary_execution,
            report["executions"]["primary"],
        )
    if not primary_ok:
        report["ok"] = False
        if run_follow_up:
            report["follow_up_skipped"] = "primary_failed"
        return report
    if primary_validation.get("ok") is not True:
        report["ok"] = False
        report["blocked_after_primary"] = "primary_tester_artifact_not_ok"
        report["reason"] = "primary MT5 Tester command returned success, but expected Tester output artifact is not usable"
        if run_follow_up:
            report["follow_up_skipped"] = "primary_artifact_not_ok"
        return report
    if run_follow_up:
        if run_archive_preview and command_list(plan.get("follow_up_archive_preview")):
            follow_up_archive_execution = (
                plan.get("follow_up_archive_preview")
                if isinstance(plan.get("follow_up_archive_preview"), dict)
                else {}
            )
            report["executions"]["follow_up_archive_preview"] = run_command(
                command_list(follow_up_archive_execution)
            )
            follow_up_archive_artifacts = execution_artifact_summary(follow_up_archive_execution)
            report.setdefault("post_execution_artifacts", {})[
                "follow_up_archive_preview"
            ] = follow_up_archive_artifacts
            follow_up_archive_validation = archive_preview_artifact_validation(
                follow_up_archive_execution,
                follow_up_archive_artifacts,
            )
            follow_up_archive_validation = add_archive_preview_command_failure(
                follow_up_archive_validation,
                report["executions"]["follow_up_archive_preview"],
                reason="follow_up_archive_preview_command_failed",
            )
            report.setdefault("post_execution_validation", {})[
                "follow_up_archive_preview"
            ] = follow_up_archive_validation
            if report["executions"]["follow_up_archive_preview"].get("ok") is not True:
                report["ok"] = False
                report["blocked_before_follow_up"] = "follow_up_archive_preview_failed"
                report["follow_up_skipped"] = "follow_up_archive_preview_failed"
                report["reason"] = "follow-up Agent CSV archive preview failed before follow-up launch"
                return report
            if follow_up_archive_validation.get("ok") is not True:
                report["ok"] = False
                report["blocked_before_follow_up"] = "follow_up_archive_preview_artifact_not_ok"
                report["follow_up_skipped"] = "follow_up_archive_preview_artifact_not_ok"
                report["reason"] = (
                    "follow-up Agent CSV archive preview returned success, "
                    "but expected preview artifact is not usable"
                )
                return report
        if command_list(plan.get("follow_up")):
            report["executions"]["follow_up"] = run_command(command_list(plan.get("follow_up")))
            follow_up_execution = plan.get("follow_up") if isinstance(plan.get("follow_up"), dict) else {}
            follow_up_artifacts = execution_artifact_summary(follow_up_execution)
            report.setdefault("post_execution_artifacts", {})["follow_up"] = follow_up_artifacts
            follow_up_validation = follow_up_artifact_validation(follow_up_execution, follow_up_artifacts)
            report.setdefault("post_execution_validation", {})["follow_up"] = follow_up_validation
            follow_up_ok = report["executions"]["follow_up"].get("ok") is True
            if not follow_up_ok:
                report["ok"] = False
                return report
            if follow_up_validation.get("ok") is not True:
                report["ok"] = False
                report["blocked_after_follow_up"] = "follow_up_artifact_not_ok"
                report["reason"] = "follow-up command returned success, but expected output artifact is not usable"
                return report
            report["ok"] = True
            return report
        report["follow_up_skipped"] = "missing_follow_up_command"
    report["ok"] = True
    return report


def format_markdown(report: dict[str, Any]) -> str:
    action = report.get("action") if isinstance(report.get("action"), dict) else {}
    primary = report.get("primary") if isinstance(report.get("primary"), dict) else {}
    archive = report.get("archive_preview") if isinstance(report.get("archive_preview"), dict) else {}
    follow_up = report.get("follow_up") if isinstance(report.get("follow_up"), dict) else {}
    follow_up_archive = (
        report.get("follow_up_archive_preview")
        if isinstance(report.get("follow_up_archive_preview"), dict)
        else {}
    )
    compile_execution = report.get("compile") if isinstance(report.get("compile"), dict) else {}
    action_context = report.get("action_context") if isinstance(report.get("action_context"), dict) else {}
    related_executions = (
        report.get("related_executions") if isinstance(report.get("related_executions"), list) else []
    )
    ready_status = report.get("ready_status") if isinstance(report.get("ready_status"), dict) else {}
    ready_status_refresh = (
        report.get("ready_status_refresh") if isinstance(report.get("ready_status_refresh"), dict) else {}
    )
    execution_hints = report.get("execution_hints") if isinstance(report.get("execution_hints"), dict) else {}
    manual_plan = (
        report.get("manual_strategy_tester")
        if isinstance(report.get("manual_strategy_tester"), dict)
        else {}
    )
    bridge_recovery = (
        report.get("bridge_recovery_plan")
        if isinstance(report.get("bridge_recovery_plan"), dict)
        else {}
    )
    collect_readiness = (
        report.get("manual_collect_readiness")
        if isinstance(report.get("manual_collect_readiness"), dict)
        else {}
    )
    lines = [
        "# MT5 Next Action Runner",
        "",
        f"- Generated at: {report.get('runner_generated_at', '')}",
        f"- OK: {report.get('ok')}",
        f"- Dry run: {report.get('dry_run')}",
        f"- Target: {report.get('target', '')}",
        f"- Found: {report.get('found')}",
        f"- Promotion generated at: {report.get('generated_at', '')}",
        f"- Promotion decision: {report.get('decision', '')}",
        f"- Current for execution: {report.get('current_for_execution', '')}",
        f"- Selected action current: {report.get('selected_action_current', '')}",
        f"- Gate stale reason: {report.get('gate_stale_reason', '')}",
        f"- Runner promotion generated at: {report.get('runner_promotion_generated_at', '')}",
        f"- Current promotion generated at: {report.get('current_promotion_generated_at', '')}",
        "",
        "## Selected Action",
        "",
        f"- Priority: {action.get('priority', '')}",
        f"- Area: {action.get('area', '')}",
        f"- Action: {action.get('action', '')}",
        f"- Reason: {action.get('reason', '')}",
        f"- Evidence key: {report.get('execution_key', '')}",
        f"- Label: {report.get('label', '')}",
        f"- Primary execution class: {report.get('primary_execution_class', '')}",
        f"- Primary is MT5 tester run: {report.get('primary_is_mt5_tester_run', '')}",
        f"- Evidence role: {report.get('evidence_role', '')}",
        f"- Diagnostic only: {report.get('diagnostic_only', '')}",
        f"- Promotion evidence: {report.get('promotion_evidence', '')}",
        f"- Allow non-tester primary: {report.get('allow_non_tester_primary', '')}",
        f"- Planned outputs: {planned_outputs_text(report.get('planned_outputs'))}",
    ]
    if bridge_recovery:
        lines.extend(
            [
                "",
                "## Bridge Recovery",
                "",
                f"- Exists: {bridge_recovery.get('exists')}",
                f"- Status: {bridge_recovery.get('status', '')}",
                f"- Ready for MT5 validation: {bridge_recovery.get('ready_for_mt5_validation', '')}",
                f"- Blocking reasons: {compact_list(bridge_recovery.get('blocking_reasons'))}",
                f"- Next action: {bridge_recovery.get('next_action', '')}",
                f"- Required for this standalone tester run: {report.get('bridge_recovery_required_for_mt5_validation', '')}",
            ]
        )
        if report.get("mt5_validation_blocked_by_bridge"):
            lines.append("- MT5 execution: blocked until Bridge Recovery is ready.")
        elif bridge_recovery_blocks_mt5_validation(bridge_recovery):
            lines.append("- MT5 execution: not blocked; Swing_Evaluation_Trader does not use the Bridge.")
    if execution_hints:
        lines.extend(
            [
                "",
                "## Execution Hints",
                "",
                f"- Execute with MT5 launch: {execution_hints.get('execute_command_text', '')}",
                f"- Collect manual MT5 results: {execution_hints.get('collect_only_command_text', '')}",
                f"- Manual collect note: {execution_hints.get('collect_only_note', '')}",
            ]
        )
    if manual_plan.get("available"):
        lines.extend(
            [
                "",
                "## Manual Strategy Tester Checklist",
                "",
                f"- Manual run start after: {manual_plan.get('manual_run_start_after', '')}",
                f"- Recommended collect-only: {manual_plan.get('recommended_collect_only_command_text', '')}",
                f"- Note: {manual_plan.get('collect_only_note', '')}",
                "",
                "| order | step | expert | symbol | period | model | dates | forward | run type | expected report | inputs | report |",
                "|---:|---|---|---|---|---|---|---|---|---|---|---|",
                *format_manual_strategy_tester_rows(manual_plan.get("steps")),
            ]
        )
    if collect_readiness.get("available") or collect_readiness:
        lines.extend(
            [
                "",
                "## Manual Collect Readiness",
                "",
                f"- Ready: {collect_readiness.get('ready')}",
                f"- Status: {collect_readiness.get('status', '')}",
                f"- Modified after: {collect_readiness.get('modified_after', '')}",
                f"- Since minutes: {collect_readiness.get('since_minutes', '')}",
                f"- Min closed: {collect_readiness.get('min_closed', '')}",
                f"- Agent CSV count: {collect_readiness.get('csv_count', '')}",
                f"- Tester root: {collect_readiness.get('tester_root', '')}",
                f"- Reason: {collect_readiness.get('reason', '')}",
                f"- Blocking reasons: {compact_list(collect_readiness.get('blocking_reasons'))}",
                f"- Next action: {collect_readiness.get('next_action', '')}",
                "",
                "| step | report status | report ready | collect ready | blocking reason | selected report |",
                "|---|---|---:|---:|---|---|",
            ]
        )
        readiness_steps = (
            collect_readiness.get("steps")
            if isinstance(collect_readiness.get("steps"), list)
            else []
        )
        if readiness_steps:
            for row in readiness_steps:
                if not isinstance(row, dict):
                    continue
                lines.append(
                    f"| {row.get('label', '')} | {row.get('report_status', '')} | "
                    f"{row.get('report_ready')} | {row.get('collect_ready')} | "
                    f"{row.get('blocking_reason', '')} | {row.get('selected_report', '')} |"
                )
        else:
            lines.append("| - |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "## Primary",
        ]
    )
    lines.extend(
        [
        "",
        f"- Kind: {primary.get('kind', '')}",
        f"- Focus side: {primary.get('focus_side', '')}",
        f"- Config: {primary.get('config', '')}",
        f"- Set: {primary.get('set', '')}",
        f"- Output set: {primary.get('output_set', '')}",
        f"- Archive run ID: {primary.get('agent_csv_archive_run_id', '')}",
        f"- Timeout: {primary.get('timeout_minutes', '')} min ({primary.get('timeout_seconds', '')} sec)",
        f"- Timeout start reference: {primary.get('timeout_start_reference_at', '')}",
        f"- Timeout deadline if started now: {primary.get('timeout_deadline_if_started_now', '')}",
        f"- Timeout note: {primary.get('timeout_note', '')}",
        f"- Optimization mode: {primary.get('optimization_mode', '')}",
        f"- Optimized input count: {primary.get('optimized_input_count', '')}",
        f"- Estimated full-factorial passes: {primary.get('estimated_full_factorial_passes', '')}",
        f"- Latest executed Tester XML rows: {recent_xml_rows_text(primary.get('latest_executed_tester_xml_rows'))}",
        f"- Declared outputs: {declared_outputs_text(primary.get('declared_outputs'))}",
        f"- Evidence role: {primary.get('evidence_role', '')}",
        f"- Diagnostic only: {primary.get('diagnostic_only', '')}",
        f"- Promotion evidence: {primary.get('promotion_evidence', '')}",
        f"- Evidence note: {primary.get('evidence_note', '')}",
        f"- Note: {primary.get('note', '')}",
        f"- Command: {primary.get('command_text', '')}",
        "",
        "## Follow Up",
        "",
        f"- Kind: {follow_up.get('kind', '')}",
        f"- Output set: {follow_up.get('output_set', '')}",
        f"- Declared outputs: {declared_outputs_text(follow_up.get('declared_outputs'))}",
        f"- Archive preview command: {follow_up_archive.get('command_text', '')}",
        f"- Command: {follow_up.get('command_text', '')}",
        ]
    )
    if action_context:
        lines.extend(["", "## Action Context", ""])
        for key, value in action_context.items():
            if isinstance(value, dict):
                lines.append(f"- {key}: {compact_context_text(key, value)}")
    if related_executions:
        lines.extend(["", "## Related Plans", ""])
        for row in related_executions:
            if not isinstance(row, dict):
                continue
            execution = row.get("execution") if isinstance(row.get("execution"), dict) else {}
            outputs = declared_outputs_text(execution.get("declared_outputs"))
            lines.append(
                f"- {row.get('label', row.get('key', ''))}: kind={execution.get('kind', '')} outputs={outputs}"
            )
            if execution.get("command_text"):
                lines.append(f"  command: {execution.get('command_text')}")
    lines.extend(
        [
            "",
            "## Preflight",
            "",
            f"- Ready status check OK: {ready_status.get('ok', '')}",
            f"- Ready status path: {ready_status.get('path', '')}",
            f"- Ready status age seconds: {ready_status.get('age_seconds', '')}",
            f"- Ready status readiness key: {ready_status.get('readiness_key', '')}",
            f"- Ready status selected execution: {ready_status.get('selected_execution_status', '')}",
            f"- Ready status reasons: {ready_status.get('reasons', [])}",
            f"- Ready status mismatches: {ready_status.get('mismatches', [])}",
            f"- Archive preview command: {archive.get('command_text', '')}",
            f"- Compile command: {compile_execution.get('command_text', '')}",
        ]
    )
    if ready_status_refresh:
        lines.extend(
            [
                "",
                "## Ready Status Refresh",
                "",
                f"- OK: {ready_status_refresh.get('ok')}",
                f"- Returncode: {ready_status_refresh.get('returncode')}",
                f"- Elapsed seconds: {ready_status_refresh.get('elapsed_seconds')}",
                f"- Output JSON: {ready_status_refresh.get('output_json', '')}",
                f"- Output Markdown: {ready_status_refresh.get('output_md', '')}",
                f"- Command: {ready_status_refresh.get('command_text', '')}",
            ]
        )
    executions = report.get("executions") if isinstance(report.get("executions"), dict) else {}
    if executions:
        lines.extend(["", "## Execution Results", ""])
        for name, result in executions.items():
            if not isinstance(result, dict):
                continue
            accepted = (
                f" accepted_returncode={result.get('accepted_returncode')} "
                f"reason={result.get('accepted_returncode_reason', '')}"
                if result.get("accepted_returncode")
                else ""
            )
            lines.append(
                f"- {name}: ok={result.get('ok')} returncode={result.get('returncode')} "
                f"elapsed={result.get('elapsed_seconds')}{accepted}"
            )
    artifacts = report.get("post_execution_artifacts") if isinstance(report.get("post_execution_artifacts"), dict) else {}
    if artifacts:
        lines.extend(["", "## Post Execution Artifacts", ""])
        for name, artifact in artifacts.items():
            if not isinstance(artifact, dict):
                continue
            if artifact.get("evidence_role"):
                lines.append(
                    f"- {name} evidence role: {artifact.get('evidence_role')} "
                    f"diagnostic_only={artifact.get('diagnostic_only')} "
                    f"promotion_evidence={artifact.get('promotion_evidence')}"
                )
                if artifact.get("evidence_note"):
                    lines.append(f"- {name} evidence note: {artifact.get('evidence_note')}")
            archive_csv = (
                artifact.get("agent_csv_archive") if isinstance(artifact.get("agent_csv_archive"), dict) else {}
            )
            tester = artifact.get("tester_run") if isinstance(artifact.get("tester_run"), dict) else {}
            forward = artifact.get("forward_report") if isinstance(artifact.get("forward_report"), dict) else {}
            optimization = artifact.get("optimization") if isinstance(artifact.get("optimization"), dict) else {}
            recommendation = (
                artifact.get("recommendation") if isinstance(artifact.get("recommendation"), dict) else {}
            )
            generic = artifact.get("output_json") if isinstance(artifact.get("output_json"), dict) else {}
            if archive_csv:
                lines.append(
                    f"- {name} agent csv archive: exists={archive_csv.get('exists', '')} "
                    f"ok={archive_csv.get('ok', '')} execute={archive_csv.get('execute', '')} "
                    f"count={archive_csv.get('count', '')} run_id={archive_csv.get('run_id', '')} "
                    f"source_rows={archive_csv.get('close_rows', '')}"
                )
            if tester:
                lines.append(
                    f"- {name} tester run: exists={tester.get('exists', '')} ok={tester.get('ok', '')} "
                    f"blocked={tester.get('blocked', '')} source_time_blocked={tester.get('source_time_blocked', '')} "
                    f"report_fallback_blocked={tester.get('report_fallback_blocked', '')} "
                    f"elapsed={tester.get('terminal_elapsed_seconds', '')}"
                )
            if forward:
                lines.append(
                    f"- {name} forward report: exists={forward.get('exists', '')} ok={forward.get('ok', '')} "
                    f"closed={forward.get('closed', '')} pf={forward.get('pf', '')} "
                    f"avg_price_r={forward.get('avg_price_r', '')}"
                )
            if generic:
                lines.append(
                    f"- {name} output json: exists={generic.get('exists', '')} "
                    f"ok={generic.get('ok', '')} generated_at={generic.get('generated_at', '')}"
                )
            if optimization:
                lines.append(
                    f"- {name} optimization: exists={optimization.get('exists', '')} "
                    f"closed={optimization.get('closed', '')} pf={optimization.get('pf', '')} "
                    f"avg_price_r={optimization.get('avg_price_r', '')} "
                    f"back_rows={optimization.get('back_rows', '')} forward_rows={optimization.get('forward_rows', '')}"
                )
            if recommendation:
                lines.append(
                    f"- {name} recommendation: exists={recommendation.get('exists', '')} "
                    f"adoptable={recommendation.get('adoptable', '')} "
                    f"next_set={recommendation.get('next_set', '')} "
                    f"skip_reason={recommendation.get('skip_reason', '')}"
                )
    validation = (
        report.get("post_execution_validation")
        if isinstance(report.get("post_execution_validation"), dict)
        else {}
    )
    if validation:
        lines.extend(["", "## Post Execution Validation", ""])
        for name, result in validation.items():
            if not isinstance(result, dict):
                continue
            lines.append(
                f"- {name}: required={result.get('required', '')} ok={result.get('ok', '')} "
                f"reasons={result.get('reasons', [])} output_json={result.get('output_json', '')}"
            )
    if report.get("reason"):
        lines.extend(["", "## Reason", "", f"- {report.get('reason')}"])
    return "\n".join(lines) + "\n"


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def enrich_report_summary_fields(report: dict[str, Any]) -> dict[str, Any]:
    primary = report.get("primary") if isinstance(report.get("primary"), dict) else {}
    archive_preview = report.get("archive_preview") if isinstance(report.get("archive_preview"), dict) else {}
    follow_up = report.get("follow_up") if isinstance(report.get("follow_up"), dict) else {}
    follow_up_archive_preview = (
        report.get("follow_up_archive_preview")
        if isinstance(report.get("follow_up_archive_preview"), dict)
        else {}
    )
    action_context = report.get("action_context") if isinstance(report.get("action_context"), dict) else {}
    related_executions = (
        report.get("related_executions") if isinstance(report.get("related_executions"), list) else []
    )
    related_execution_keys = [
        str(row.get("key"))
        for row in related_executions
        if isinstance(row, dict) and row.get("key") not in (None, "")
    ]
    executions = report.get("executions") if isinstance(report.get("executions"), dict) else {}
    post_validation = (
        report.get("post_execution_validation")
        if isinstance(report.get("post_execution_validation"), dict)
        else {}
    )
    primary_execution = executions.get("primary") if isinstance(executions.get("primary"), dict) else {}
    archive_preview_execution = (
        executions.get("archive_preview") if isinstance(executions.get("archive_preview"), dict) else {}
    )
    follow_up_execution = executions.get("follow_up") if isinstance(executions.get("follow_up"), dict) else {}
    follow_up_archive_preview_execution = (
        executions.get("follow_up_archive_preview")
        if isinstance(executions.get("follow_up_archive_preview"), dict)
        else {}
    )
    primary_validation = (
        post_validation.get("primary") if isinstance(post_validation.get("primary"), dict) else {}
    )
    archive_preview_validation = (
        post_validation.get("archive_preview")
        if isinstance(post_validation.get("archive_preview"), dict)
        else {}
    )
    follow_up_validation = (
        post_validation.get("follow_up") if isinstance(post_validation.get("follow_up"), dict) else {}
    )
    follow_up_archive_preview_validation = (
        post_validation.get("follow_up_archive_preview")
        if isinstance(post_validation.get("follow_up_archive_preview"), dict)
        else {}
    )
    promotion_generated_at = str(report.get("promotion_generated_at") or report.get("generated_at") or "")
    promotion_decision = str(report.get("promotion_decision") or report.get("decision") or "")
    found = report.get("found") is True
    report.update(
        {
            "runner_promotion_generated_at": promotion_generated_at,
            "current_promotion_generated_at": promotion_generated_at,
            "runner_promotion_decision": promotion_decision,
            "current_promotion_decision": promotion_decision,
            "selected_action_current": found,
            "current_for_execution": found,
            "gate_stale_reason": "" if found else "selected_action_not_found",
            "kind": primary.get("kind", ""),
            "focus_side": primary.get("focus_side", ""),
            "optimization_mode": primary.get("optimization_mode", ""),
            "config": primary.get("config", ""),
            "set": primary.get("set", ""),
            "output_set": primary.get("output_set", ""),
            "agent_csv_archive_run_id": primary.get("agent_csv_archive_run_id", ""),
            "command_text": primary.get("command_text", ""),
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
            "timeout_seconds": primary.get("timeout_seconds", ""),
            "timeout_minutes": primary.get("timeout_minutes", ""),
            "timeout_start_reference_at": primary.get("timeout_start_reference_at", ""),
            "timeout_deadline_if_started_now": primary.get("timeout_deadline_if_started_now", ""),
            "timeout_deadline_epoch_if_started_now": primary.get("timeout_deadline_epoch_if_started_now", ""),
            "timeout_note": primary.get("timeout_note", ""),
            "optimized_input_count": primary.get("optimized_input_count", ""),
            "estimated_full_factorial_passes": primary.get("estimated_full_factorial_passes", ""),
            "latest_executed_tester_xml_rows": primary.get("latest_executed_tester_xml_rows", ""),
            "action_context_keys": sorted(action_context.keys()),
            "related_execution_count": len(related_executions),
            "related_execution_keys": related_execution_keys,
            "primary_ok": primary_execution.get("ok", ""),
            "primary_returncode": primary_execution.get("returncode", ""),
            "primary_post_validation_ok": primary_validation.get("ok", ""),
            "primary_post_validation_reasons": primary_validation.get("reasons", []),
            "archive_preview_ok": archive_preview_execution.get("ok", ""),
            "archive_preview_returncode": archive_preview_execution.get("returncode", ""),
            "archive_preview_post_validation_ok": archive_preview_validation.get("ok", ""),
            "archive_preview_post_validation_reasons": archive_preview_validation.get("reasons", []),
            "follow_up_ok": follow_up_execution.get("ok", ""),
            "follow_up_returncode": follow_up_execution.get("returncode", ""),
            "follow_up_post_validation_ok": follow_up_validation.get("ok", ""),
            "follow_up_post_validation_reasons": follow_up_validation.get("reasons", []),
            "follow_up_archive_preview_ok": follow_up_archive_preview_execution.get("ok", ""),
            "follow_up_archive_preview_returncode": follow_up_archive_preview_execution.get("returncode", ""),
            "follow_up_archive_preview_post_validation_ok": follow_up_archive_preview_validation.get("ok", ""),
            "follow_up_archive_preview_post_validation_reasons": follow_up_archive_preview_validation.get(
                "reasons", []
            ),
        }
    )
    return report


def write_ready_status_refresh_plan(
    plan: dict[str, Any],
    *,
    args: argparse.Namespace,
) -> dict[str, Any]:
    report = execute_plan(
        plan,
        execute=False,
        run_archive_preview=False,
        run_compile=args.run_compile,
        run_follow_up=args.run_follow_up,
        allow_non_tester_primary=args.allow_non_tester_primary,
        ready_status=None,
    )
    report["runner_generated_at"] = datetime.now().strftime(TIME_FORMAT)
    report["promotion_gate_path"] = args.promotion_gate
    report["preflight_plan_for_ready_status_refresh"] = True
    enrich_report_summary_fields(report)
    attach_execution_hints(report, args=args)
    write_json(args.output_json, report)
    write_text(args.output_md, format_markdown(report))
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select and optionally execute an MT5 Promotion Gate next action.")
    parser.add_argument("--promotion-gate", default=DEFAULT_PROMOTION_GATE)
    parser.add_argument(
        "--target",
        default=DEFAULT_TARGET,
        help="Action target to select. Defaults to first_mt5, the first current MT5 Tester plan in Promotion Gate.",
    )
    parser.add_argument(
        "--focus-side",
        choices=("buy", "sell", "both"),
        default="",
        help="Optional side filter for actions that expose multiple BUY/SELL/BOTH tester plans.",
    )
    parser.add_argument("--execute", action="store_true", help="Actually run the selected primary command.")
    parser.add_argument("--ready-status", default=DEFAULT_READY_STATUS)
    parser.add_argument("--ready-status-md", default=DEFAULT_READY_STATUS_MD)
    parser.add_argument(
        "--refresh-ready-status",
        action="store_true",
        help="Refresh the ready-status artifact before execute preflight.",
    )
    parser.add_argument("--max-ready-status-age-seconds", type=int, default=DEFAULT_READY_STATUS_MAX_AGE_SECONDS)
    parser.add_argument(
        "--skip-ready-status-check",
        action="store_true",
        help="Diagnostic escape hatch: execute an MT5 Tester primary without requiring latest_mt5_tester_status readiness.",
    )
    parser.add_argument("--bridge-recovery-plan", default=DEFAULT_BRIDGE_RECOVERY_PLAN)
    parser.add_argument(
        "--require-bridge-ready",
        action="store_true",
        help=(
            "Require Bridge Recovery to be ready before launching MT5. "
            "By default Swing_Evaluation_Trader Strategy Tester runs are allowed because the EA is standalone."
        ),
    )
    parser.add_argument(
        "--run-archive-preview",
        action="store_true",
        help="Run only the Agent CSV archive preview during dry-run, without launching the MT5 primary.",
    )
    parser.add_argument("--skip-archive-preview", action="store_true")
    parser.add_argument("--run-compile", action="store_true", help="Run the compile plan before the primary command.")
    parser.add_argument("--run-follow-up", action="store_true", help="Run the selected follow-up command after primary succeeds.")
    parser.add_argument(
        "--allow-non-tester-primary",
        action="store_true",
        help="Allow --execute when the selected primary command is not analysis/mt5_tester_run.py.",
    )
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--print-full-report", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    gate = load_json(args.promotion_gate)
    plan = select_next_action_plan(gate, target=args.target, focus_side=args.focus_side)
    use_bridge_recovery = (
        args.bridge_recovery_plan != DEFAULT_BRIDGE_RECOVERY_PLAN
        or args.promotion_gate == DEFAULT_PROMOTION_GATE
    )
    bridge_recovery = bridge_recovery_plan_summary(args.bridge_recovery_plan if use_bridge_recovery else "")
    bridge_blocks_primary = (
        args.require_bridge_ready
        and
        bridge_recovery_blocks_mt5_validation(bridge_recovery)
        and plan.get("primary_is_mt5_tester_run") is True
    )
    run_archive_preview = (args.execute or args.run_archive_preview) and not args.skip_archive_preview
    ready_status = None
    ready_status_refresh = None
    requires_ready_status = plan.get("primary_is_mt5_tester_run") is True or args.allow_non_tester_primary
    if args.execute and bridge_blocks_primary:
        report = execute_plan(
            plan,
            execute=False,
            run_archive_preview=False,
            run_compile=args.run_compile,
            run_follow_up=args.run_follow_up,
            allow_non_tester_primary=args.allow_non_tester_primary,
            ready_status=None,
        )
        report["dry_run"] = False
        report["ok"] = False
        report["blocked_before_primary"] = "bridge_recovery_not_ready"
        report["reason"] = bridge_recovery_block_reason(bridge_recovery)
        report["runner_generated_at"] = datetime.now().strftime(TIME_FORMAT)
        report["promotion_gate_path"] = args.promotion_gate
        enrich_report_summary_fields(report)
        attach_execution_hints(report, args=args)
        apply_bridge_recovery_guard(report, bridge_recovery)
        write_json(args.output_json, report)
        write_text(args.output_md, format_markdown(report))
        print(json.dumps(report if args.print_full_report else {
            "ok": report.get("ok"),
            "dry_run": report.get("dry_run"),
            "runner_generated_at": report.get("runner_generated_at", ""),
            "promotion_generated_at": report.get("promotion_generated_at") or report.get("generated_at", ""),
            "promotion_decision": report.get("promotion_decision") or report.get("decision", ""),
            "target": report.get("target"),
            "found": report.get("found"),
            "blocked_before_primary": report.get("blocked_before_primary", ""),
            "reason": report.get("reason", ""),
            "bridge_recovery_plan_status": bridge_recovery.get("status", ""),
            "bridge_recovery_plan_ready_for_mt5_validation": bridge_recovery.get("ready_for_mt5_validation", ""),
            "output_json": args.output_json,
            "output_md": args.output_md,
        }, ensure_ascii=False, indent=2))
        return 2
    if args.execute and args.refresh_ready_status and not args.skip_ready_status_check and requires_ready_status:
        write_ready_status_refresh_plan(plan, args=args)
        ready_status_refresh = refresh_ready_status(args.ready_status, args.ready_status_md)
        if ready_status_refresh.get("ok") is not True:
            report = execute_plan(
                plan,
                execute=False,
                run_archive_preview=False,
                run_compile=args.run_compile,
                run_follow_up=args.run_follow_up,
                allow_non_tester_primary=args.allow_non_tester_primary,
                ready_status=None,
            )
            report["dry_run"] = False
            report["ok"] = False
            report["ready_status_refresh"] = ready_status_refresh
            report["blocked_before_primary"] = "ready_status_refresh_failed"
            report["reason"] = "latest MT5 tester status could not be refreshed before execute preflight"
            report["runner_generated_at"] = datetime.now().strftime(TIME_FORMAT)
            report["promotion_gate_path"] = args.promotion_gate
            enrich_report_summary_fields(report)
            attach_execution_hints(report, args=args)
            apply_bridge_recovery_guard(report, bridge_recovery)
            write_json(args.output_json, report)
            write_text(args.output_md, format_markdown(report))
            print(json.dumps(report if args.print_full_report else {
                "ok": report.get("ok"),
                "dry_run": report.get("dry_run"),
                "runner_generated_at": report.get("runner_generated_at", ""),
                "promotion_generated_at": report.get("promotion_generated_at") or report.get("generated_at", ""),
                "promotion_decision": report.get("promotion_decision") or report.get("decision", ""),
                "target": report.get("target"),
                "found": report.get("found"),
                "blocked_before_primary": report.get("blocked_before_primary", ""),
                "reason": report.get("reason", ""),
                "ready_status_refresh_ok": ready_status_refresh.get("ok"),
                "ready_status_refresh_returncode": ready_status_refresh.get("returncode"),
                "output_json": args.output_json,
                "output_md": args.output_md,
            }, ensure_ascii=False, indent=2))
            return 2
    if args.execute and not args.skip_ready_status_check and requires_ready_status:
        ready_status = ready_status_preflight(
            plan,
            status_path=args.ready_status,
            max_age_seconds=args.max_ready_status_age_seconds,
        )
    report = execute_plan(
        plan,
        execute=args.execute,
        run_archive_preview=run_archive_preview,
        run_compile=args.run_compile,
        run_follow_up=args.run_follow_up,
        allow_non_tester_primary=args.allow_non_tester_primary,
        ready_status=ready_status,
    )
    if ready_status_refresh is not None:
        report["ready_status_refresh"] = ready_status_refresh
    report["runner_generated_at"] = datetime.now().strftime(TIME_FORMAT)
    report["promotion_gate_path"] = args.promotion_gate
    enrich_report_summary_fields(report)
    attach_execution_hints(report, args=args)
    apply_bridge_recovery_guard(report, bridge_recovery)
    write_json(args.output_json, report)
    write_text(args.output_md, format_markdown(report))
    summary = {
        "ok": report.get("ok"),
        "dry_run": report.get("dry_run"),
        "runner_generated_at": report.get("runner_generated_at", ""),
        "promotion_generated_at": report.get("promotion_generated_at") or report.get("generated_at", ""),
        "promotion_decision": report.get("promotion_decision") or report.get("decision", ""),
        "target": report.get("target"),
        "found": report.get("found"),
        "kind": report.get("kind", ""),
        "config": report.get("config", ""),
        "timeout_seconds": report.get("timeout_seconds", ""),
        "timeout_minutes": report.get("timeout_minutes", ""),
        "timeout_start_reference_at": report.get("timeout_start_reference_at", ""),
        "timeout_deadline_if_started_now": report.get("timeout_deadline_if_started_now", ""),
        "timeout_deadline_epoch_if_started_now": report.get("timeout_deadline_epoch_if_started_now", ""),
        "estimated_full_factorial_passes": report.get("estimated_full_factorial_passes", ""),
        "action_context_keys": report.get("action_context_keys", []),
        "related_execution_count": report.get("related_execution_count", 0),
        "related_execution_keys": report.get("related_execution_keys", []),
        "primary_execution_class": report.get("primary_execution_class", ""),
        "primary_is_mt5_tester_run": report.get("primary_is_mt5_tester_run", ""),
        "evidence_role": report.get("evidence_role", ""),
        "diagnostic_only": report.get("diagnostic_only", ""),
        "promotion_evidence": report.get("promotion_evidence", ""),
        "ready_status_ok": (
            report.get("ready_status") if isinstance(report.get("ready_status"), dict) else {}
        ).get("ok", ""),
        "ready_status_readiness_key": (
            report.get("ready_status") if isinstance(report.get("ready_status"), dict) else {}
        ).get("readiness_key", ""),
        "archive_preview_ok": (
            (report.get("executions") if isinstance(report.get("executions"), dict) else {})
            .get("archive_preview", {})
            .get("ok", "")
        ),
        "archive_preview_post_validation_ok": (
            (report.get("post_execution_validation") if isinstance(report.get("post_execution_validation"), dict) else {})
            .get("archive_preview", {})
            .get("ok", "")
        ),
        "archive_preview_post_validation_reasons": (
            (report.get("post_execution_validation") if isinstance(report.get("post_execution_validation"), dict) else {})
            .get("archive_preview", {})
            .get("reasons", [])
        ),
        "blocked_before_primary": report.get("blocked_before_primary", ""),
        "blocked_before_follow_up": report.get("blocked_before_follow_up", ""),
        "blocked_after_primary": report.get("blocked_after_primary", ""),
        "blocked_after_follow_up": report.get("blocked_after_follow_up", ""),
        "primary_accepted_returncode": (
            (report.get("executions") if isinstance(report.get("executions"), dict) else {})
            .get("primary", {})
            .get("accepted_returncode", "")
        ),
        "primary_accepted_returncode_reason": (
            (report.get("executions") if isinstance(report.get("executions"), dict) else {})
            .get("primary", {})
            .get("accepted_returncode_reason", "")
        ),
        "primary_post_validation_ok": (
            (report.get("post_execution_validation") if isinstance(report.get("post_execution_validation"), dict) else {})
            .get("primary", {})
            .get("ok", "")
        ),
        "primary_post_validation_reasons": (
            (report.get("post_execution_validation") if isinstance(report.get("post_execution_validation"), dict) else {})
            .get("primary", {})
            .get("reasons", [])
        ),
        "follow_up_post_validation_ok": (
            (report.get("post_execution_validation") if isinstance(report.get("post_execution_validation"), dict) else {})
            .get("follow_up", {})
            .get("ok", "")
        ),
        "follow_up_post_validation_reasons": (
            (report.get("post_execution_validation") if isinstance(report.get("post_execution_validation"), dict) else {})
            .get("follow_up", {})
            .get("reasons", [])
        ),
        "follow_up_kind": (report.get("follow_up") if isinstance(report.get("follow_up"), dict) else {}).get(
            "kind",
            "",
        ),
        "output_json": args.output_json,
        "output_md": args.output_md,
    }
    print(json.dumps(report if args.print_full_report else summary, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
