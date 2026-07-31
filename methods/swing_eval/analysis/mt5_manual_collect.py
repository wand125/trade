from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT
from analysis.mt5_back_forward_run import manual_collect_readiness as back_forward_manual_collect_readiness
from analysis.mt5_compile_status import default_mt5_root
from analysis.mt5_manual_test_queue import (
    DEFAULT_BACK_FORWARD_RUN,
    DEFAULT_BUY_NEXT_ACTION_RUN,
    DEFAULT_COLLECT_OUTPUT_JSON_WITH_OPTIMIZATION,
    DEFAULT_COLLECT_OUTPUT_MD_WITH_OPTIMIZATION,
    DEFAULT_OUTPUT_JSON_WITH_OPTIMIZATION,
    DEFAULT_PROMOTION_GATE,
    DEFAULT_SELL_NEXT_ACTION_RUN,
    build_queue as build_manual_test_queue,
    format_markdown as format_manual_test_queue_markdown,
    manual_run_start_state_from_queue,
    operator_collect_filter_summary,
    operator_step_summary,
    static_strategy_config_state_from_queue,
)
from analysis.mt5_next_action_run import manual_collect_readiness as next_action_manual_collect_readiness
from analysis.mt5_strategy_tester_analysis import (
    DEFAULT_OUTPUT_JSON as DEFAULT_STRATEGY_TESTER_ANALYSIS_OUTPUT_JSON,
    DEFAULT_OUTPUT_MD as DEFAULT_STRATEGY_TESTER_ANALYSIS_OUTPUT_MD,
    build_strategy_tester_analysis,
    format_markdown as format_strategy_tester_analysis_markdown,
)
from analysis.promotion_gate import (
    evaluate_promotion_gate,
    write_report as write_promotion_gate_report,
)
from analysis.spec_coverage import (
    DEFAULT_OUTPUT_JSON as DEFAULT_SPEC_COVERAGE_OUTPUT_JSON,
    DEFAULT_OUTPUT_MD as DEFAULT_SPEC_COVERAGE_OUTPUT_MD,
    build_spec_coverage,
    write_json as write_spec_coverage_json,
    write_markdown as write_spec_coverage_markdown,
)


DEFAULT_QUEUE = "runtime/latest_mt5_manual_test_queue.json"
DEFAULT_OUTPUT_JSON = "runtime/latest_mt5_manual_collect_run.json"
DEFAULT_OUTPUT_MD = "runtime/latest_mt5_manual_collect_run.md"
ALLOWED_COLLECT_SCRIPTS = {
    "methods/swing_eval/analysis/mt5_back_forward_run.py",
    "methods/swing_eval/analysis/mt5_tester_run.py",
}
QUEUE_SOURCE_IDS = {
    "back_forward": DEFAULT_BACK_FORWARD_RUN,
    "score_weight_sell": DEFAULT_SELL_NEXT_ACTION_RUN,
    "score_weight_buy": DEFAULT_BUY_NEXT_ACTION_RUN,
}
COMPLETED_COLLECT_STATUSES = {"already_collected", "collect_executed"}


def load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json_file(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text_file(path: str | Path, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def short_text(value: str, *, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:]


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def normalized_script_path(value: str) -> str:
    path = value.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def command_option_value(command: list[str], option: str) -> str:
    prefix = option + "="
    for index, item in enumerate(command):
        if item == option:
            if index + 1 < len(command):
                return str(command[index + 1])
            return ""
        if item.startswith(prefix):
            return str(item[len(prefix) :])
    return ""


def validate_collect_command(command_text: str, *, required_modified_after: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "command": [],
        "command_text": command_text,
        "reason": "",
    }
    if not command_text.strip():
        result["reason"] = "missing_collect_command"
        return result
    try:
        command = shlex.split(command_text)
    except ValueError as exc:
        result["reason"] = f"invalid_shell_words:{exc}"
        return result
    result["command"] = command
    if len(command) < 3:
        result["reason"] = "collect_command_too_short"
        return result
    python_name = Path(command[0]).name
    if not python_name.startswith("python"):
        result["reason"] = "collect_command_not_python"
        return result
    script = normalized_script_path(command[1])
    if script not in ALLOWED_COLLECT_SCRIPTS:
        result["reason"] = "collect_command_script_not_allowed"
        return result
    if "--collect-only" not in command:
        result["reason"] = "collect_command_missing_collect_only"
        return result
    if "--execute" in command:
        result["reason"] = "collect_command_contains_execute"
        return result
    if required_modified_after:
        modified_after = command_option_value(command, "--csv-modified-after")
        if not modified_after:
            result["reason"] = "collect_command_missing_csv_modified_after"
            return result
        if modified_after != required_modified_after:
            result["reason"] = "collect_command_csv_modified_after_mismatch"
            result["expected_csv_modified_after"] = required_modified_after
            result["actual_csv_modified_after"] = modified_after
            return result
    result["ok"] = True
    return result


def unique_nonempty_texts(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "")
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def collect_status_completed(status: Any) -> bool:
    return str(status or "") in COMPLETED_COLLECT_STATUSES


def entry_collect_completed(entry: dict[str, Any]) -> bool:
    return collect_status_completed(entry.get("collect_status"))


def parse_generated_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for pattern in ("%Y.%m.%d %H:%M:%S", TIME_FORMAT):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    return None


def time_text_at_or_after(value: Any, threshold: Any) -> bool:
    threshold_text = str(threshold or "").strip()
    value_text = str(value or "").strip()
    if not threshold_text:
        return True
    if not value_text:
        return False
    value_time = parse_generated_time(value_text)
    threshold_time = parse_generated_time(threshold_text)
    if value_time is not None and threshold_time is not None:
        return value_time >= threshold_time
    return value_text >= threshold_text


def back_forward_collect_already_executed(payload: dict[str, Any], *, modified_after: str) -> bool:
    evidence_state = str(payload.get("evidence_state") or "")
    generated_at = str(payload.get("generated_at") or payload.get("runner_generated_at") or "")
    return (
        payload.get("ok") is True
        and payload.get("collect_only") is True
        and payload.get("execute") is True
        and evidence_state.startswith("executed_")
        and time_text_at_or_after(generated_at, modified_after)
    )


def already_collected_readiness(
    readiness: dict[str, Any],
    *,
    payload: dict[str, Any],
    modified_after: str,
) -> dict[str, Any]:
    generated_at = str(payload.get("generated_at") or payload.get("runner_generated_at") or "")
    result = dict(readiness)
    result.update(
        {
            "ready": False,
            "status": "already_collected",
            "reason": "manual_collect_already_executed",
            "blocking_reasons": [],
            "next_action": "run_next_manual_strategy_tester_step",
            "modified_after": modified_after,
            "collected_at": generated_at,
            "collected_evidence_state": payload.get("evidence_state", ""),
        }
    )
    completed_steps: list[dict[str, Any]] = []
    for step in (result.get("steps", []) if isinstance(result.get("steps"), list) else []):
        if not isinstance(step, dict):
            continue
        completed = dict(step)
        completed["collect_ready"] = False
        completed["blocking_reason"] = ""
        completed["report_status"] = "already_collected"
        completed_steps.append(completed)
    if completed_steps:
        result["steps"] = completed_steps
    return result


def checklist_items(queue: dict[str, Any]) -> list[dict[str, Any]]:
    items = queue.get("execution_checklist") if isinstance(queue.get("execution_checklist"), list) else []
    return [item for item in items if isinstance(item, dict)]


def entry_checklist_items(queue: dict[str, Any], entry: dict[str, Any]) -> list[dict[str, Any]]:
    entry_id = str(entry.get("id") or "")
    if not entry_id:
        return []
    return [item for item in checklist_items(queue) if str(item.get("queue_id") or "") == entry_id]


def step_label_for_audit(step: dict[str, Any]) -> str:
    return str(step.get("step_label") or step.get("label") or "")


def compact_expected_artifact(step: dict[str, Any], *, entry_id: str = "") -> dict[str, Any]:
    expected = step.get("expected_artifacts") if isinstance(step.get("expected_artifacts"), dict) else {}
    queue_id = str(step.get("queue_id") or entry_id)
    label = step_label_for_audit(step)
    return {
        "queue_step": f"{queue_id}/{label}".strip("/"),
        "step_label": label,
        "step_fingerprint": step.get("step_fingerprint", ""),
        "step_config_fingerprint": step.get("step_config_fingerprint", ""),
        "step_run_fingerprint": step.get("step_run_fingerprint", ""),
        "fingerprint_scope": step.get("fingerprint_scope", ""),
        "source_step_fingerprint": step.get("source_step_fingerprint", ""),
        "source_step_config_fingerprint": step.get("source_step_config_fingerprint", ""),
        "source_step_run_fingerprint": step.get("source_step_run_fingerprint", ""),
        "queue_step_fingerprint": step.get("queue_step_fingerprint", ""),
        "queue_step_config_fingerprint": step.get("queue_step_config_fingerprint", ""),
        "queue_step_run_fingerprint": step.get("queue_step_run_fingerprint", ""),
        "expected_report_artifact": step.get("expected_report_artifact")
        or expected.get("expected_report_artifact", ""),
        "report": step.get("report") or step.get("report_name") or expected.get("report", ""),
        "agent_csv": expected.get("agent_csv", ""),
        "agent_csv_modified_after": expected.get("agent_csv_modified_after", ""),
        "run_json": step.get("run_json") or expected.get("run_json", ""),
        "report_json": step.get("report_json") or expected.get("report_json", ""),
        "collect_status": step.get("step_report_status", ""),
        "collect_ready": step.get("step_collect_ready", ""),
    }


def entry_collect_audit(queue: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    entry_id = str(entry.get("id") or "")
    steps = entry_checklist_items(queue, entry)
    if not steps:
        raw_steps = entry.get("steps") if isinstance(entry.get("steps"), list) else []
        steps = [step for step in raw_steps if isinstance(step, dict)]
    expected_artifacts_by_step = [
        compact_expected_artifact(step, entry_id=entry_id)
        for step in steps
    ]
    return {
        "audit_step_count": len(steps),
        "step_fingerprints": unique_nonempty_texts(
            [step.get("step_fingerprint", "") for step in steps]
        ),
        "step_config_fingerprints": unique_nonempty_texts(
            [step.get("step_config_fingerprint", "") for step in steps]
        ),
        "step_run_fingerprints": unique_nonempty_texts(
            [step.get("step_run_fingerprint", "") for step in steps]
        ),
        "fingerprint_scopes": unique_nonempty_texts(
            [step.get("fingerprint_scope", "") for step in steps]
        ),
        "source_step_fingerprints": unique_nonempty_texts(
            [step.get("source_step_fingerprint", "") for step in steps]
        ),
        "queue_step_fingerprints": unique_nonempty_texts(
            [step.get("queue_step_fingerprint", "") for step in steps]
        ),
        "expected_reports": unique_nonempty_texts(
            [item.get("report", "") for item in expected_artifacts_by_step]
        ),
        "expected_artifacts_by_step": expected_artifacts_by_step,
    }


def step_completion_status(step: dict[str, Any]) -> str:
    if step.get("step_collect_ready") is True:
        return "collect_ready"
    if step.get("step_report_ready") is True:
        return "report_ready_waiting_agent_csv"
    report_status = str(step.get("step_report_status") or "")
    if report_status:
        return report_status
    if step.get("launch_needed") is True:
        return "waiting_for_mt5_run"
    return "unknown"


def step_purpose(queue: dict[str, Any], step: dict[str, Any]) -> str:
    existing = str(step.get("purpose") or "")
    if existing:
        return existing
    queue_id = str(step.get("queue_id") or "")
    label = step_label_for_audit(step)
    for key in ("operation_cards", "strategy_tester_targets"):
        rows = queue.get(key) if isinstance(queue.get(key), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("queue_id") or "") != queue_id:
                continue
            if str(row.get("step_label") or "") != label:
                continue
            purpose = str(row.get("purpose") or "")
            if purpose:
                return purpose
    if label == "backtest":
        return "Backtest"
    if label == "forward":
        return "Forward Test"
    if label == "score_weight_sample_collection":
        if queue_id.endswith("sell"):
            return "SELL Score Sample"
        if queue_id.endswith("buy"):
            return "BUY Score Sample"
        return "Score Sample"
    return label


def step_completion_audit(queue: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step in checklist_items(queue):
        queue_id = str(step.get("queue_id") or "")
        label = step_label_for_audit(step)
        expected = compact_expected_artifact(step)
        rows.append(
            {
                "order": step.get("order", ""),
                "queue_step": f"{queue_id}/{label}".strip("/"),
                "purpose": step_purpose(queue, step),
                "status": step_completion_status(step),
                "report_ready": step.get("step_report_ready", ""),
                "collect_ready": step.get("step_collect_ready", ""),
                "launch_needed": step.get("launch_needed", ""),
                "blocking_reason": step.get("step_blocking_reason", ""),
                "expected_report_artifact": expected.get("expected_report_artifact", ""),
                "report": expected.get("report", ""),
                "agent_csv": expected.get("agent_csv", ""),
                "agent_csv_modified_after": expected.get("agent_csv_modified_after", ""),
                "step_fingerprint": expected.get("step_fingerprint", ""),
                "collect_filter_summary": operator_collect_filter_summary(step),
            }
        )
    return rows


def queue_entries(queue: dict[str, Any]) -> list[dict[str, Any]]:
    entries = queue.get("entries") if isinstance(queue.get("entries"), list) else []
    return [entry for entry in entries if isinstance(entry, dict) and entry.get("available") is True]


def queue_source_paths(queue: dict[str, Any]) -> dict[str, str]:
    entries = queue.get("entries") if isinstance(queue.get("entries"), list) else []
    paths: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id") or "")
        source = str(entry.get("source_json") or "")
        if entry_id in QUEUE_SOURCE_IDS and source:
            paths[entry_id] = source
    return paths


def refreshed_back_forward_payload(
    payload: dict[str, Any],
    *,
    manual_run_start_after: str = "",
) -> dict[str, Any]:
    manual_plan = (
        payload.get("manual_strategy_tester")
        if isinstance(payload.get("manual_strategy_tester"), dict)
        else {}
    )
    current_readiness = (
        payload.get("manual_collect_readiness")
        if isinstance(payload.get("manual_collect_readiness"), dict)
        else {}
    )
    steps = manual_plan.get("steps") if isinstance(manual_plan.get("steps"), list) else []
    modified_after = str(
        manual_run_start_after
        or current_readiness.get("modified_after")
        or manual_plan.get("manual_run_start_after")
        or payload.get("generated_at")
        or ""
    )
    readiness = back_forward_manual_collect_readiness(
        steps=steps,
        mt5_root=str(current_readiness.get("mt5_root") or default_mt5_root()),
        modified_after=modified_after,
        since_minutes=float(current_readiness.get("since_minutes") or 240.0),
        min_closed=int(current_readiness.get("min_closed") or 0),
    )
    if back_forward_collect_already_executed(payload, modified_after=modified_after):
        readiness = already_collected_readiness(
            readiness,
            payload=payload,
            modified_after=modified_after,
        )
    refreshed = dict(payload)
    if manual_run_start_after:
        refreshed_plan = dict(manual_plan)
        refreshed_plan["manual_run_start_after"] = modified_after
        refreshed["manual_strategy_tester"] = refreshed_plan
    refreshed["manual_collect_readiness"] = readiness
    if readiness != current_readiness:
        refreshed["manual_collect_readiness_refreshed_at"] = datetime.now().strftime(TIME_FORMAT)
    return refreshed


def refreshed_next_action_payload(
    payload: dict[str, Any],
    *,
    manual_run_start_after: str = "",
) -> dict[str, Any]:
    current_readiness = (
        payload.get("manual_collect_readiness")
        if isinstance(payload.get("manual_collect_readiness"), dict)
        else {}
    )
    refreshed = dict(payload)
    if manual_run_start_after:
        manual_plan = (
            refreshed.get("manual_strategy_tester")
            if isinstance(refreshed.get("manual_strategy_tester"), dict)
            else {}
        )
        refreshed_plan = dict(manual_plan)
        refreshed_plan["manual_run_start_after"] = manual_run_start_after
        refreshed["manual_strategy_tester"] = refreshed_plan
    refreshed["manual_collect_readiness"] = next_action_manual_collect_readiness(refreshed)
    if refreshed["manual_collect_readiness"] != current_readiness:
        refreshed["manual_collect_readiness_refreshed_at"] = datetime.now().strftime(TIME_FORMAT)
    return refreshed


def refresh_queue_from_sources(
    queue: dict[str, Any],
    *,
    queue_path: str,
    promotion_gate: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    paths = queue_source_paths(queue)
    required_ids = set(QUEUE_SOURCE_IDS)
    missing_ids = sorted(required_ids - set(paths))
    if missing_ids:
        return queue, {
            "enabled": True,
            "ok": False,
            "status": "missing_source_paths",
            "missing_ids": missing_ids,
            "source_count": 0,
            "refreshed_sources": [],
        }

    manual_run_state = manual_run_start_state_from_queue(queue)
    refreshed_sources: list[dict[str, Any]] = []
    for entry_id, source_path in paths.items():
        state = manual_run_state.get(entry_id) or manual_run_state.get(source_path) or {}
        manual_run_start_after = (
            str(state.get("manual_run_start_after") or "")
            if isinstance(state, dict) and state.get("marked") is True
            else ""
        )
        payload = load_json(source_path)
        if not payload:
            refreshed_sources.append(
                {"id": entry_id, "path": source_path, "ok": False, "status": "missing_or_invalid_source"}
            )
            continue
        if entry_id == "back_forward":
            refreshed = refreshed_back_forward_payload(
                payload,
                manual_run_start_after=manual_run_start_after,
            )
        else:
            refreshed = refreshed_next_action_payload(
                payload,
                manual_run_start_after=manual_run_start_after,
            )
        source_changed = refreshed != payload
        if source_changed:
            write_json_file(source_path, refreshed)
        readiness = refreshed.get("manual_collect_readiness")
        readiness = readiness if isinstance(readiness, dict) else {}
        refreshed_sources.append(
            {
                "id": entry_id,
                "path": source_path,
                "ok": True,
                "changed": source_changed,
                "ready": readiness.get("ready", False),
                "status": readiness.get("status", ""),
                "modified_after": readiness.get("modified_after", ""),
            }
        )

    resolved_promotion_gate = promotion_gate or str(queue.get("promotion_gate_path") or "")
    if not resolved_promotion_gate and queue_path == DEFAULT_QUEUE:
        resolved_promotion_gate = DEFAULT_PROMOTION_GATE
    static_configs = (
        queue.get("static_strategy_configs")
        if isinstance(queue.get("static_strategy_configs"), list)
        else []
    )
    static_candidate_labels = (
        queue.get("static_candidate_labels")
        if isinstance(queue.get("static_candidate_labels"), list)
        else []
    )
    refreshed_queue = build_manual_test_queue(
        back_forward_run=paths.get("back_forward", DEFAULT_BACK_FORWARD_RUN),
        sell_next_action_run=paths.get("score_weight_sell", DEFAULT_SELL_NEXT_ACTION_RUN),
        buy_next_action_run=paths.get("score_weight_buy", DEFAULT_BUY_NEXT_ACTION_RUN),
        promotion_gate=resolved_promotion_gate,
        queue_json=queue_path,
        static_strategy_configs=[str(item) for item in static_configs],
        static_candidate_labels=[str(item) for item in static_candidate_labels],
        static_strategy_config_state=static_strategy_config_state_from_queue(queue),
        manual_run_start_state=manual_run_state,
    )
    refreshed_queue["queue_json"] = queue_path
    write_json_file(queue_path, refreshed_queue)
    queue_md_path = str(Path(queue_path).with_suffix(".md"))
    write_text_file(queue_md_path, format_manual_test_queue_markdown(refreshed_queue))
    refreshed_entries = (
        refreshed_queue.get("entries")
        if isinstance(refreshed_queue.get("entries"), list)
        else []
    )
    refreshed_entry_ids = [
        str(entry.get("id") or "")
        for entry in refreshed_entries
        if isinstance(entry, dict) and entry.get("id")
    ]
    static_entry_ids = [
        entry_id for entry_id in refreshed_entry_ids if entry_id.startswith("static_")
    ]
    return refreshed_queue, {
        "enabled": True,
        "ok": all(item.get("ok") is True for item in refreshed_sources),
        "status": "refreshed",
        "promotion_gate_path": resolved_promotion_gate,
        "promotion_gate_generated_at": refreshed_queue.get("promotion_gate_generated_at", ""),
        "queue_md_path": queue_md_path,
        "missing_ids": [],
        "source_count": len(refreshed_sources),
        "queue_entry_count": len(refreshed_entry_ids),
        "queue_step_count": refreshed_queue.get("step_count", ""),
        "static_entry_count": len(static_entry_ids),
        "static_entry_ids": static_entry_ids,
        "refreshed_sources": refreshed_sources,
    }


def build_collect_plan(queue: dict[str, Any], *, queue_path: str) -> dict[str, Any]:
    entries = queue_entries(queue)
    planned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for entry in entries:
        audit = entry_collect_audit(queue, entry)
        row = {
            "id": entry.get("id", ""),
            "title": entry.get("title", ""),
            "runner_generated_at": entry.get("runner_generated_at") or entry.get("generated_at", ""),
            "promotion_generated_at": entry.get("promotion_generated_at", ""),
            "current_promotion_generated_at": entry.get("current_promotion_generated_at", ""),
            "promotion_decision": entry.get("promotion_decision", ""),
            "current_promotion_decision": entry.get("current_promotion_decision", ""),
            "selected_action_current": entry.get("selected_action_current", ""),
            "ready": entry.get("collect_ready") is True,
            "collect_status": entry.get("collect_status", ""),
            "collect_reason": entry.get("collect_reason", ""),
            "collect_modified_after": entry.get("collect_modified_after", ""),
            "command_text": entry.get("collect_only_command_text", ""),
            **audit,
        }
        if entry_collect_completed(entry):
            row["skip_reason"] = "already_collected"
            row["blocking_reasons"] = []
            completed.append(row)
            continue
        if entry.get("collect_ready") is not True:
            row["skip_reason"] = "not_ready"
            row["blocking_reasons"] = entry.get("collect_blocking_reasons", [])
            skipped.append(row)
            continue
        validation = validate_collect_command(
            str(entry.get("collect_only_command_text") or ""),
            required_modified_after=str(entry.get("collect_modified_after") or ""),
        )
        row["validation"] = validation
        row["command"] = validation.get("command", [])
        if validation.get("ok") is not True:
            row["skip_reason"] = "invalid_collect_command"
            row["reason"] = validation.get("reason", "")
            invalid.append(row)
            continue
        planned.append(row)
    return {
        "queue_path": queue_path,
        "queue_generated_at": queue.get("generated_at", ""),
        "queue_status": queue.get("status", ""),
        "queue_next_action": queue.get("next_action", ""),
        "entry_count": len(entries),
        "ready_entry_count": sum(1 for entry in entries if entry.get("collect_ready") is True),
        "completed_count": len(completed),
        "completed_entry_count": len(completed),
        "completed_entry_ids": [str(row.get("id") or "") for row in completed],
        "selected_count": len(planned),
        "waiting_count": len(skipped),
        "invalid_count": len(invalid),
        "planned": planned,
        "skipped": skipped,
        "completed": completed,
        "invalid": invalid,
    }


def queue_step_progress(queue: dict[str, Any]) -> dict[str, Any]:
    checklist = queue.get("execution_checklist") if isinstance(queue.get("execution_checklist"), list) else []
    checklist_items = [item for item in checklist if isinstance(item, dict)]
    return {
        "queue_step_count": queue.get("step_count", len(checklist_items)),
        "queue_step_report_ready_count": queue.get(
            "step_report_ready_count",
            sum(1 for item in checklist_items if item.get("step_report_ready") is True),
        ),
        "queue_step_collect_ready_count": queue.get(
            "step_collect_ready_count",
            sum(1 for item in checklist_items if item.get("step_collect_ready") is True),
        ),
        "queue_step_waiting_report_count": queue.get(
            "step_waiting_report_count",
            sum(1 for item in checklist_items if item.get("step_report_status") == "waiting_report"),
        ),
        "queue_step_launch_needed_count": queue.get(
            "step_launch_needed_count",
            sum(1 for item in checklist_items if item.get("launch_needed") is True),
        ),
    }


def first_waiting_mt5_step(queue: dict[str, Any]) -> dict[str, Any]:
    next_step = queue.get("next_launch_step")
    checklist = queue.get("execution_checklist") if isinstance(queue.get("execution_checklist"), list) else []
    if isinstance(next_step, dict) and next_step:
        queue_id = str(next_step.get("queue_id") or "")
        step_label = str(next_step.get("step_label") or "")
        for item in checklist:
            if not isinstance(item, dict):
                continue
            if str(item.get("queue_id") or "") == queue_id and str(item.get("step_label") or "") == step_label:
                merged = dict(item)
                merged.update({key: value for key, value in next_step.items() if value not in ("", None)})
                return merged
        return next_step
    for item in checklist:
        if not isinstance(item, dict):
            continue
        if item.get("launch_needed") is True or str(item.get("step_report_status") or "") == "waiting_report":
            return item
    return {}


def compact_mt5_step(step: dict[str, Any]) -> dict[str, Any]:
    if not step:
        return {}
    return {
        "order": step.get("order", ""),
        "queue_id": step.get("queue_id", ""),
        "step_label": step.get("step_label", ""),
        "purpose": step.get("purpose", ""),
        "expert": step.get("expert", ""),
        "symbol": step.get("symbol", ""),
        "period": step.get("period", ""),
        "model": step.get("model", ""),
        "from_date": step.get("from_date", ""),
        "to_date": step.get("to_date", ""),
        "dates": step.get("dates", ""),
        "forward": step.get("forward", ""),
        "forward_mode": step.get("forward_mode", ""),
        "optimization": step.get("optimization", ""),
        "optimization_label": step.get("optimization_label", ""),
        "run_type": step.get("run_type", ""),
        "expected_report_artifact": step.get("expected_report_artifact", ""),
        "step_fingerprint": step.get("step_fingerprint", ""),
        "step_config_fingerprint": step.get("step_config_fingerprint", ""),
        "step_run_fingerprint": step.get("step_run_fingerprint", ""),
        "fingerprint_scope": step.get("fingerprint_scope", ""),
        "source_step_fingerprint": step.get("source_step_fingerprint", ""),
        "source_step_config_fingerprint": step.get("source_step_config_fingerprint", ""),
        "source_step_run_fingerprint": step.get("source_step_run_fingerprint", ""),
        "queue_step_fingerprint": step.get("queue_step_fingerprint", ""),
        "queue_step_config_fingerprint": step.get("queue_step_config_fingerprint", ""),
        "queue_step_run_fingerprint": step.get("queue_step_run_fingerprint", ""),
        "expected_artifacts": (
            step.get("expected_artifacts") if isinstance(step.get("expected_artifacts"), dict) else {}
        ),
        "inputs": step.get("inputs", ""),
        "report": step.get("report", ""),
        "step_report_status": step.get("step_report_status", ""),
        "step_blocking_reason": step.get("step_blocking_reason", ""),
        "launch_command_kind": step.get("launch_command_kind", ""),
    }


def quick_input_from_step(step: dict[str, Any]) -> dict[str, Any]:
    if not step:
        return {}
    queue_id = str(step.get("queue_id") or "")
    step_label = str(step.get("step_label") or "")
    return {
        "queue_step": f"{queue_id}/{step_label}".strip("/"),
        "purpose": step.get("purpose", ""),
        "expert": step.get("expert", ""),
        "symbol": step.get("symbol", ""),
        "period": step.get("period", ""),
        "model": step.get("model", ""),
        "from_date": step.get("from_date", ""),
        "to_date": step.get("to_date", ""),
        "dates": step.get("dates", ""),
        "forward": step.get("forward", ""),
        "forward_mode": step.get("forward_mode", ""),
        "optimization": step.get("optimization", ""),
        "optimization_label": step.get("optimization_label", ""),
        "inputs": step.get("inputs", ""),
        "report": step.get("report", ""),
        "run_type": step.get("run_type", ""),
        "expected_report_artifact": step.get("expected_report_artifact", ""),
        "step_fingerprint": step.get("step_fingerprint", ""),
        "step_config_fingerprint": step.get("step_config_fingerprint", ""),
        "step_run_fingerprint": step.get("step_run_fingerprint", ""),
        "fingerprint_scope": step.get("fingerprint_scope", ""),
        "source_step_fingerprint": step.get("source_step_fingerprint", ""),
        "source_step_config_fingerprint": step.get("source_step_config_fingerprint", ""),
        "source_step_run_fingerprint": step.get("source_step_run_fingerprint", ""),
        "queue_step_fingerprint": step.get("queue_step_fingerprint", ""),
        "queue_step_config_fingerprint": step.get("queue_step_config_fingerprint", ""),
        "queue_step_run_fingerprint": step.get("queue_step_run_fingerprint", ""),
        "launch_kind": step.get("launch_command_kind", ""),
        "manual_run_start_after": step.get("manual_run_start_after", ""),
    }


def manual_collect_command_text(
    *,
    queue_path: str,
    execute: bool,
    refresh_strategy_tester_analysis: bool = False,
    refresh_post_collect_analysis: bool = False,
) -> str:
    if Path(queue_path).name == Path(DEFAULT_OUTPUT_JSON_WITH_OPTIMIZATION).name:
        output_json = DEFAULT_COLLECT_OUTPUT_JSON_WITH_OPTIMIZATION
        output_md = DEFAULT_COLLECT_OUTPUT_MD_WITH_OPTIMIZATION
    else:
        output_json = DEFAULT_OUTPUT_JSON
        output_md = DEFAULT_OUTPUT_MD
    command = [
        "python3",
        "methods/swing_eval/analysis/mt5_manual_collect.py",
        "--queue",
        queue_path,
    ]
    if execute:
        command.append("--execute")
    if refresh_strategy_tester_analysis:
        command.append("--refresh-strategy-tester-analysis")
    if refresh_post_collect_analysis:
        command.append("--refresh-post-collect-analysis")
    command.extend(["--output-json", output_json, "--output-md", output_md])
    return shlex.join(command)


def build_operator_handoff(
    *,
    queue: dict[str, Any],
    plan: dict[str, Any],
    status: str,
    queue_path: str,
    execute: bool,
) -> dict[str, Any]:
    ready_ids = [str(row.get("id") or "") for row in plan.get("planned", []) if isinstance(row, dict)]
    waiting_ids = [str(row.get("id") or "") for row in plan.get("skipped", []) if isinstance(row, dict)]
    completed_ids = [str(row.get("id") or "") for row in plan.get("completed", []) if isinstance(row, dict)]
    invalid_ids = [str(row.get("id") or "") for row in plan.get("invalid", []) if isinstance(row, dict)]
    if status == "collect_executed":
        state = "collect_executed"
    elif status == "collect_failed":
        state = "collect_failed"
    elif ready_ids and not execute:
        state = "ready_to_execute_collect"
    elif ready_ids:
        state = "collect_ready"
    elif waiting_ids:
        state = "waiting_for_mt5_reports"
    elif invalid_ids:
        state = "invalid_collect_commands"
    elif completed_ids:
        state = "collect_complete"
    else:
        state = status or "unknown"
    queue_handoff = queue.get("operator_handoff") if isinstance(queue.get("operator_handoff"), dict) else {}
    next_step = compact_mt5_step(first_waiting_mt5_step(queue))
    next_step_quick_input = quick_input_from_step(next_step)
    queue_quick_input = (
        queue_handoff.get("quick_input")
        if isinstance(queue_handoff.get("quick_input"), dict)
        else {}
    )
    quick_input = dict(next_step_quick_input)
    quick_input.update(
        {
            key: value
            for key, value in queue_quick_input.items()
            if value not in ("", None, [])
        }
    )
    return {
        "state": state,
        "queue_path": queue_path,
        "queue_status": plan.get("queue_status", ""),
        "queue_next_action": plan.get("queue_next_action", ""),
        **queue_step_progress(queue),
        "ready_ids": ready_ids,
        "waiting_ids": waiting_ids,
        "completed_ids": completed_ids,
        "invalid_ids": invalid_ids,
        "selected_count": plan.get("selected_count", 0),
        "waiting_count": plan.get("waiting_count", 0),
        "completed_count": plan.get("completed_count", 0),
        "invalid_count": plan.get("invalid_count", 0),
        "next_mt5_step": next_step,
        "quick_input": quick_input,
        "next_step_operator_summary": (
            queue_handoff.get("next_step_operator_summary")
            or operator_step_summary(next_step)
        ),
        "next_step_collect_filter_summary": (
            queue_handoff.get("next_step_collect_filter_summary")
            or operator_collect_filter_summary(next_step)
        ),
        "dry_run_command_text": manual_collect_command_text(queue_path=queue_path, execute=False),
        "execute_command_text": manual_collect_command_text(queue_path=queue_path, execute=True),
        "execute_and_refresh_analysis_command_text": manual_collect_command_text(
            queue_path=queue_path,
            execute=True,
            refresh_strategy_tester_analysis=True,
        ),
        "execute_and_refresh_all_command_text": manual_collect_command_text(
            queue_path=queue_path,
            execute=True,
            refresh_post_collect_analysis=True,
        ),
    }


def run_collect_commands(plan: dict[str, Any]) -> list[dict[str, Any]]:
    executions: list[dict[str, Any]] = []
    for row in plan.get("planned", []):
        if not isinstance(row, dict):
            continue
        command = [str(item) for item in row.get("command", [])]
        started_at = datetime.now().strftime(TIME_FORMAT)
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        executions.append(
            {
                "id": row.get("id", ""),
                "title": row.get("title", ""),
                "command": command,
                "command_text": shlex.join(command),
                "started_at": started_at,
                "returncode": completed.returncode,
                "ok": completed.returncode == 0,
                "stdout_tail": short_text(completed.stdout or ""),
                "stderr_tail": short_text(completed.stderr or ""),
            }
        )
    return executions


def unique_texts(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def collect_blocking_reasons(
    *,
    status: str,
    plan: dict[str, Any],
    queue_refresh: dict[str, Any],
    executions: list[dict[str, Any]],
) -> list[str]:
    reasons: list[Any] = []
    if queue_refresh.get("enabled") is True and queue_refresh.get("ok") is False:
        reasons.append("queue_refresh_failed:" + str(queue_refresh.get("status") or "unknown"))
        reasons.extend(queue_refresh.get("missing_ids") if isinstance(queue_refresh.get("missing_ids"), list) else [])
    for row in plan.get("skipped", []):
        if not isinstance(row, dict):
            continue
        blocking = row.get("blocking_reasons")
        if isinstance(blocking, list):
            reasons.extend(blocking)
        elif row.get("collect_reason"):
            reasons.append(row.get("collect_reason"))
    for row in plan.get("invalid", []):
        if not isinstance(row, dict):
            continue
        reasons.append(
            "invalid_collect_command:"
            + str(row.get("id") or "unknown")
            + ":"
            + str(row.get("reason") or "unknown")
        )
    if status == "collect_failed":
        for row in executions:
            if not isinstance(row, dict) or row.get("ok") is True:
                continue
            reasons.append(
                "collect_failed:"
                + str(row.get("id") or "unknown")
                + ":returncode="
                + str(row.get("returncode", ""))
            )
    return unique_texts(reasons)


def collect_next_action(
    *,
    status: str,
    plan: dict[str, Any],
    queue_refresh: dict[str, Any],
    execute: bool,
) -> str:
    if status == "missing_or_invalid_queue":
        return "refresh_mt5_manual_test_queue"
    if queue_refresh.get("enabled") is True and queue_refresh.get("ok") is False:
        return "refresh_mt5_manual_test_queue_sources"
    if status == "blocked_invalid_collect_command":
        return "fix_invalid_manual_collect_commands"
    if status == "waiting_for_ready_collect_entries":
        return str(plan.get("queue_next_action") or "run_manual_strategy_tester_steps_and_wait_for_reports")
    if status == "collect_failed":
        return "inspect_manual_collect_execution_errors"
    if status == "collect_executed":
        return "refresh_mt5_tester_status_after_collect"
    if status == "collect_complete":
        return "refresh_mt5_tester_status_after_collect"
    if status == "ready_for_collect_execute" and not execute:
        return "run_mt5_manual_collect_with_execute"
    return "refresh_mt5_manual_collect_run"


def refresh_strategy_tester_analysis_report(
    *,
    workspace: str | Path = ".",
    output_json: str | Path = DEFAULT_STRATEGY_TESTER_ANALYSIS_OUTPUT_JSON,
    output_md: str | Path = DEFAULT_STRATEGY_TESTER_ANALYSIS_OUTPUT_MD,
) -> dict[str, Any]:
    root = Path(workspace).expanduser().resolve()
    try:
        payload = build_strategy_tester_analysis(root)
        write_json(output_json, payload)
        write_text(output_md, format_strategy_tester_analysis_markdown(payload))
    except Exception as exc:  # pragma: no cover - defensive reporting for operator handoff
        return {
            "enabled": True,
            "ok": False,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "output_json": str(output_json),
            "output_md": str(output_md),
        }
    return {
        "enabled": True,
        "ok": True,
        "status": "refreshed",
        "output_json": str(output_json),
        "output_md": str(output_md),
        "adoption_status": payload.get("adoption", {}).get("status", "")
        if isinstance(payload.get("adoption"), dict)
        else "",
        "candidate_labels": payload.get("adoption", {}).get("candidate_labels", [])
        if isinstance(payload.get("adoption"), dict)
        else [],
        "blockers": payload.get("adoption", {}).get("blockers", [])
        if isinstance(payload.get("adoption"), dict)
        else [],
    }


def refresh_promotion_gate_report(
    *,
    output_json: str | Path = "runtime/latest_promotion_gate.json",
    output_md: str | Path = "runtime/latest_promotion_gate.md",
) -> dict[str, Any]:
    try:
        payload = evaluate_promotion_gate()
        write_promotion_gate_report(output_json, output_md, payload)
    except Exception as exc:  # pragma: no cover - defensive reporting for operator handoff
        return {
            "enabled": True,
            "ok": False,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "output_json": str(output_json),
            "output_md": str(output_md),
        }
    return {
        "enabled": True,
        "ok": True,
        "status": "refreshed",
        "output_json": str(output_json),
        "output_md": str(output_md),
        "decision": payload.get("decision", ""),
        "live_ready": payload.get("live_ready", ""),
        "failed": payload.get("failed", ""),
        "failed_check_names": payload.get("failed_check_names", []),
    }


def refresh_spec_coverage_report(
    *,
    workspace: str | Path = ".",
    output_json: str | Path = DEFAULT_SPEC_COVERAGE_OUTPUT_JSON,
    output_md: str | Path = DEFAULT_SPEC_COVERAGE_OUTPUT_MD,
) -> dict[str, Any]:
    try:
        payload = build_spec_coverage(workspace_root=workspace)
        write_spec_coverage_json(output_json, payload)
        write_spec_coverage_markdown(output_md, payload)
    except Exception as exc:  # pragma: no cover - defensive reporting for operator handoff
        return {
            "enabled": True,
            "ok": False,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "output_json": str(output_json),
            "output_md": str(output_md),
        }
    return {
        "enabled": True,
        "ok": True,
        "status": "refreshed",
        "output_json": str(output_json),
        "output_md": str(output_md),
        "goal_completion_proven": payload.get("goal_completion_proven", ""),
        "not_complete_reason_count": payload.get("not_complete_reason_count", ""),
        "not_complete_reasons": payload.get("not_complete_reasons", []),
        "next_action_count": payload.get("next_action_count", ""),
    }


def format_row_fingerprints(row: dict[str, Any]) -> str:
    fingerprints = row.get("step_fingerprints") if isinstance(row.get("step_fingerprints"), list) else []
    return ", ".join(str(item) for item in fingerprints)


def format_row_expected_reports(row: dict[str, Any]) -> str:
    reports = row.get("expected_reports") if isinstance(row.get("expected_reports"), list) else []
    return ", ".join(str(item) for item in reports)


def build_report(
    *,
    queue_path: str,
    queue: dict[str, Any],
    execute: bool,
    refresh_queue: bool = False,
    promotion_gate: str = "",
) -> dict[str, Any]:
    queue_refresh = {"enabled": refresh_queue, "ok": "", "status": "not_requested", "refreshed_sources": []}
    if queue and refresh_queue:
        queue, queue_refresh = refresh_queue_from_sources(
            queue,
            queue_path=queue_path,
            promotion_gate=promotion_gate,
        )
    if not queue:
        empty_progress = queue_step_progress({})
        status = "missing_or_invalid_queue"
        empty_plan = {
            "queue_path": queue_path,
            "queue_generated_at": "",
            "queue_status": "",
            "queue_next_action": "",
            "entry_count": 0,
            "ready_entry_count": 0,
            "completed_count": 0,
            "completed_entry_count": 0,
            "completed_entry_ids": [],
            "selected_count": 0,
            "waiting_count": 0,
            "invalid_count": 0,
            "planned": [],
            "skipped": [],
            "completed": [],
            "invalid": [],
            **empty_progress,
        }
        return {
            "ok": False,
            "generated_at": datetime.now().strftime(TIME_FORMAT),
            "queue_path": queue_path,
            "execute": execute,
            "dry_run": not execute,
            "queue_refresh": queue_refresh,
            "status": status,
            "next_action": collect_next_action(
                status=status,
                plan=empty_plan,
                queue_refresh=queue_refresh,
                execute=execute,
            ),
            "reason": "queue_json_missing_or_invalid",
            "blocking_reasons": ["queue_json_missing_or_invalid"],
            "operator_handoff": build_operator_handoff(
                queue={},
                plan=empty_plan,
                status=status,
                queue_path=queue_path,
                execute=execute,
            ),
            "step_completion_audit": [],
            **empty_plan,
            "executions": [],
        }
    plan = build_collect_plan(queue, queue_path=queue_path)
    progress = queue_step_progress(queue)
    queue_refresh_failed = queue_refresh.get("enabled") is True and queue_refresh.get("ok") is False
    executions = (
        run_collect_commands(plan)
        if execute and not plan.get("invalid") and not queue_refresh_failed
        else []
    )
    execution_failed = any(item.get("ok") is not True for item in executions)
    if queue_refresh_failed:
        status = "blocked_queue_refresh_failed"
    elif plan.get("invalid_count"):
        status = "blocked_invalid_collect_command"
    elif plan.get("selected_count") == 0 and plan.get("waiting_count") == 0 and plan.get("completed_count"):
        status = "collect_complete"
    elif plan.get("selected_count") == 0:
        status = "waiting_for_ready_collect_entries"
    elif execute and execution_failed:
        status = "collect_failed"
    elif execute:
        status = "collect_executed"
    else:
        status = "ready_for_collect_execute"
    ok = (
        (
            plan.get("selected_count", 0) > 0
            or status == "collect_complete"
        )
        and plan.get("invalid_count", 0) == 0
        and not queue_refresh_failed
        and (not execute or not execution_failed)
    )
    blocking_reasons = collect_blocking_reasons(
        status=status,
        plan=plan,
        queue_refresh=queue_refresh,
        executions=executions,
    )
    return {
        "ok": ok,
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "queue_path": queue_path,
        "execute": execute,
        "dry_run": not execute,
        "status": status,
        "next_action": collect_next_action(
            status=status,
            plan=plan,
            queue_refresh=queue_refresh,
            execute=execute,
        ),
        "blocking_reasons": blocking_reasons,
        "queue_refresh": queue_refresh,
        "operator_handoff": build_operator_handoff(
            queue=queue,
            plan=plan,
            status=status,
            queue_path=queue_path,
            execute=execute,
        ),
        "step_completion_audit": step_completion_audit(queue),
        **plan,
        **progress,
        "executions": executions,
    }


def format_markdown(report: dict[str, Any]) -> str:
    handoff = report.get("operator_handoff") if isinstance(report.get("operator_handoff"), dict) else {}
    next_step = handoff.get("next_mt5_step") if isinstance(handoff.get("next_mt5_step"), dict) else {}
    strategy_refresh = (
        report.get("strategy_tester_analysis_refresh")
        if isinstance(report.get("strategy_tester_analysis_refresh"), dict)
        else {}
    )
    promotion_refresh = (
        report.get("promotion_gate_refresh")
        if isinstance(report.get("promotion_gate_refresh"), dict)
        else {}
    )
    spec_refresh = (
        report.get("spec_coverage_refresh")
        if isinstance(report.get("spec_coverage_refresh"), dict)
        else {}
    )
    lines = [
        "# MT5 Manual Collect Run",
        "",
        f"- Generated at: {report.get('generated_at', '')}",
        f"- OK: {report.get('ok')}",
        f"- Status: {report.get('status', '')}",
        f"- Next action: {report.get('next_action', '')}",
        f"- Queue: {report.get('queue_path', '')}",
        f"- Queue refresh: {(report.get('queue_refresh') if isinstance(report.get('queue_refresh'), dict) else {}).get('status', '')}",
        f"- Queue status: {report.get('queue_status', '')}",
        f"- Queue steps: {report.get('queue_step_count', '')}",
        f"- Queue step reports ready: {report.get('queue_step_report_ready_count', '')}",
        f"- Queue step reports waiting: {report.get('queue_step_waiting_report_count', '')}",
        f"- Queue step launches needed: {report.get('queue_step_launch_needed_count', '')}",
        f"- Execute: {report.get('execute')}",
        f"- Selected: {report.get('selected_count', 0)}",
        f"- Completed: {report.get('completed_count', 0)}",
        f"- Waiting: {report.get('waiting_count', 0)}",
        f"- Invalid: {report.get('invalid_count', 0)}",
        f"- Blocking reasons: {', '.join(str(item) for item in report.get('blocking_reasons', [])) if isinstance(report.get('blocking_reasons'), list) else ''}",
        "",
        "## MT5 Collect Handoff",
        "",
        f"- State: {handoff.get('state', '')}",
        f"- Ready entries: {', '.join(str(item) for item in handoff.get('ready_ids', [])) if isinstance(handoff.get('ready_ids'), list) else ''}",
        f"- Waiting entries: {', '.join(str(item) for item in handoff.get('waiting_ids', [])) if isinstance(handoff.get('waiting_ids'), list) else ''}",
        f"- Completed entries: {', '.join(str(item) for item in handoff.get('completed_ids', [])) if isinstance(handoff.get('completed_ids'), list) else ''}",
        f"- Invalid entries: {', '.join(str(item) for item in handoff.get('invalid_ids', [])) if isinstance(handoff.get('invalid_ids'), list) else ''}",
        (
            f"- Step progress: steps={handoff.get('queue_step_count', '')}, "
            f"report_ready={handoff.get('queue_step_report_ready_count', '')}, "
            f"waiting={handoff.get('queue_step_waiting_report_count', '')}, "
            f"launch_needed={handoff.get('queue_step_launch_needed_count', '')}"
        ),
        f"- Next step summary: `{markdown_cell(handoff.get('next_step_operator_summary', ''))}`",
        f"- Collect filter: `{markdown_cell(handoff.get('next_step_collect_filter_summary', ''))}`",
        f"- Dry-run command: `{markdown_cell(handoff.get('dry_run_command_text', ''))}`",
        f"- Execute command: `{markdown_cell(handoff.get('execute_command_text', ''))}`",
        f"- Execute + analysis command: `{markdown_cell(handoff.get('execute_and_refresh_analysis_command_text', ''))}`",
        f"- Execute + full analysis command: `{markdown_cell(handoff.get('execute_and_refresh_all_command_text', ''))}`",
    ]
    if next_step:
        lines.extend(
            [
                (
                    f"- Next MT5 step: `{markdown_cell(next_step.get('queue_id', ''))}/"
                    f"{markdown_cell(next_step.get('step_label', ''))}`"
                ),
                (
                    "- Strategy Tester settings: "
                    f"Symbol `{markdown_cell(next_step.get('symbol', ''))}`, "
                    f"Period `{markdown_cell(next_step.get('period', ''))}`, "
                    f"Dates `{markdown_cell(next_step.get('dates', ''))}`, "
                    f"Forward `{markdown_cell(next_step.get('forward', ''))}`"
                ),
                (
                    f"- Load Inputs: `{markdown_cell(next_step.get('inputs', ''))}`; "
                    f"Report: `{markdown_cell(next_step.get('report', ''))}`"
                ),
                (
                    f"- Report condition: `{markdown_cell(next_step.get('step_report_status', ''))}`; "
                    f"Expected: `{markdown_cell(next_step.get('expected_report_artifact', ''))}`"
                ),
                (
                    f"- Run fingerprint: `{markdown_cell(next_step.get('step_fingerprint', ''))}`; "
                    f"Config fingerprint: `{markdown_cell(next_step.get('step_config_fingerprint', ''))}`"
                ),
            ]
        )
        source_fingerprint = str(next_step.get("source_step_fingerprint") or "")
        queue_fingerprint = str(next_step.get("queue_step_fingerprint") or "")
        if source_fingerprint or queue_fingerprint:
            lines.append(
                f"- Fingerprint audit: scope `{markdown_cell(next_step.get('fingerprint_scope', ''))}`, "
                f"source `{markdown_cell(source_fingerprint)}`, queue `{markdown_cell(queue_fingerprint)}`"
            )
    step_audit = (
        report.get("step_completion_audit")
        if isinstance(report.get("step_completion_audit"), list)
        else []
    )
    if step_audit:
        lines.extend(
            [
                "",
                "## Step Completion Audit",
                "",
                "| order | queue/step | purpose | status | report ready | collect ready | launch needed | expected | report | modified after | fingerprint | reason |",
                "|---:|---|---|---|---:|---:|---:|---|---|---|---|---|",
            ]
        )
        for row in step_audit:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"| {markdown_cell(row.get('order', ''))} | "
                f"{markdown_cell(row.get('queue_step', ''))} | "
                f"{markdown_cell(row.get('purpose', ''))} | "
                f"{markdown_cell(row.get('status', ''))} | "
                f"{row.get('report_ready', '')} | "
                f"{row.get('collect_ready', '')} | "
                f"{row.get('launch_needed', '')} | "
                f"{markdown_cell(row.get('expected_report_artifact', ''))} | "
                f"{markdown_cell(row.get('report', ''))} | "
                f"{markdown_cell(row.get('agent_csv_modified_after', ''))} | "
                f"{markdown_cell(row.get('step_fingerprint', ''))} | "
                f"{markdown_cell(row.get('blocking_reason', ''))} |"
            )
    if promotion_refresh and promotion_refresh.get("enabled") is not False:
        lines.extend(
            [
                "",
                "## Promotion Gate Refresh",
                "",
                f"- Enabled: {promotion_refresh.get('enabled')}",
                f"- OK: {promotion_refresh.get('ok', '')}",
                f"- Status: {promotion_refresh.get('status', '')}",
                f"- Output JSON: `{markdown_cell(promotion_refresh.get('output_json', ''))}`",
                f"- Output Markdown: `{markdown_cell(promotion_refresh.get('output_md', ''))}`",
                f"- Decision: {promotion_refresh.get('decision', '')}",
                f"- Live ready: {promotion_refresh.get('live_ready', '')}",
                f"- Failed: {promotion_refresh.get('failed', '')}",
                f"- Failed checks: {', '.join(str(item) for item in promotion_refresh.get('failed_check_names', [])) if isinstance(promotion_refresh.get('failed_check_names'), list) else ''}",
                f"- Reason: {promotion_refresh.get('reason', '')}",
            ]
        )
    if strategy_refresh and strategy_refresh.get("enabled") is not False:
        lines.extend(
            [
                "",
                "## Strategy Tester Analysis Refresh",
                "",
                f"- Enabled: {strategy_refresh.get('enabled')}",
                f"- OK: {strategy_refresh.get('ok', '')}",
                f"- Status: {strategy_refresh.get('status', '')}",
                f"- Output JSON: `{markdown_cell(strategy_refresh.get('output_json', ''))}`",
                f"- Output Markdown: `{markdown_cell(strategy_refresh.get('output_md', ''))}`",
                f"- Adoption status: {strategy_refresh.get('adoption_status', '')}",
                f"- Candidate labels: {', '.join(str(item) for item in strategy_refresh.get('candidate_labels', [])) if isinstance(strategy_refresh.get('candidate_labels'), list) else ''}",
                f"- Blockers: {', '.join(str(item) for item in strategy_refresh.get('blockers', [])) if isinstance(strategy_refresh.get('blockers'), list) else ''}",
                f"- Reason: {strategy_refresh.get('reason', '')}",
            ]
        )
    if spec_refresh and spec_refresh.get("enabled") is not False:
        lines.extend(
            [
                "",
                "## Spec Coverage Refresh",
                "",
                f"- Enabled: {spec_refresh.get('enabled')}",
                f"- OK: {spec_refresh.get('ok', '')}",
                f"- Status: {spec_refresh.get('status', '')}",
                f"- Output JSON: `{markdown_cell(spec_refresh.get('output_json', ''))}`",
                f"- Output Markdown: `{markdown_cell(spec_refresh.get('output_md', ''))}`",
                f"- Goal completion proven: {spec_refresh.get('goal_completion_proven', '')}",
                f"- Not complete reason count: {spec_refresh.get('not_complete_reason_count', '')}",
                f"- Next action count: {spec_refresh.get('next_action_count', '')}",
                f"- Reasons: {', '.join(str(item) for item in spec_refresh.get('not_complete_reasons', [])) if isinstance(spec_refresh.get('not_complete_reasons'), list) else ''}",
                f"- Reason: {spec_refresh.get('reason', '')}",
            ]
        )
    lines.extend(
        [
            "",
            "## Planned",
            "",
            "| id | ready | runner generated | gate generated | current gate | decision | current decision | action current | fingerprints | expected reports | modified after | command |",
            "|---|---:|---|---|---|---|---|---:|---|---|---|---|",
        ]
    )
    for row in report.get("planned", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {markdown_cell(row.get('id', ''))} | {row.get('ready')} | "
            f"{markdown_cell(row.get('runner_generated_at', ''))} | "
            f"{markdown_cell(row.get('promotion_generated_at', ''))} | "
            f"{markdown_cell(row.get('current_promotion_generated_at', ''))} | "
            f"{markdown_cell(row.get('promotion_decision', ''))} | "
            f"{markdown_cell(row.get('current_promotion_decision', ''))} | "
            f"{row.get('selected_action_current', '')} | "
            f"{markdown_cell(format_row_fingerprints(row))} | "
            f"{markdown_cell(format_row_expected_reports(row))} | "
            f"{markdown_cell(row.get('collect_modified_after', ''))} | "
            f"{markdown_cell(row.get('command_text', ''))} |"
        )
    refresh = report.get("queue_refresh") if isinstance(report.get("queue_refresh"), dict) else {}
    if refresh:
        lines.extend(
            [
                "",
                "## Queue Refresh",
                "",
                (
                    f"- Dynamic runner sources: {refresh.get('source_count', '')}; "
                    f"Queue entries: {refresh.get('queue_entry_count', '')}; "
                    f"Queue steps: {refresh.get('queue_step_count', '')}; "
                    f"Static entries: {refresh.get('static_entry_count', '')}"
                ),
                (
                    "- Static entry ids: "
                    + (
                        ", ".join(str(item) for item in refresh.get("static_entry_ids", []))
                        if isinstance(refresh.get("static_entry_ids"), list)
                        else ""
                    )
                ),
                "",
                "| id | source | ok | changed | ready | status | modified after |",
                "|---|---|---:|---:|---:|---|---|",
            ]
        )
        for row in refresh.get("refreshed_sources", []):
            if not isinstance(row, dict):
                continue
            lines.append(
                f"| {markdown_cell(row.get('id', ''))} | "
                f"{markdown_cell(row.get('path', ''))} | "
                f"{row.get('ok')} | "
                f"{row.get('changed', '')} | "
                f"{row.get('ready', '')} | "
                f"{markdown_cell(row.get('status', ''))} | "
                f"{markdown_cell(row.get('modified_after', ''))} |"
            )
    completed_rows = report.get("completed") if isinstance(report.get("completed"), list) else []
    if completed_rows:
        lines.extend(
            [
                "",
                "## Completed",
                "",
                "| id | status | runner generated | evidence | modified after |",
                "|---|---|---|---|---|",
            ]
        )
        for row in completed_rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"| {markdown_cell(row.get('id', ''))} | "
                f"{markdown_cell(row.get('collect_status', ''))} | "
                f"{markdown_cell(row.get('runner_generated_at', ''))} | "
                f"{markdown_cell(row.get('collect_reason', ''))} | "
                f"{markdown_cell(row.get('collect_modified_after', ''))} |"
            )
    lines.extend(
        [
            "",
            "## Skipped",
            "",
            "| id | status | runner generated | gate generated | current gate | decision | current decision | action current | fingerprints | expected reports | reason |",
            "|---|---|---|---|---|---|---|---:|---|---|---|",
        ]
    )
    for row in report.get("skipped", []):
        if not isinstance(row, dict):
            continue
        reasons = row.get("blocking_reasons")
        reason_text = "; ".join(str(item) for item in reasons) if isinstance(reasons, list) else row.get("collect_reason", "")
        lines.append(
            f"| {markdown_cell(row.get('id', ''))} | {markdown_cell(row.get('collect_status', ''))} | "
            f"{markdown_cell(row.get('runner_generated_at', ''))} | "
            f"{markdown_cell(row.get('promotion_generated_at', ''))} | "
            f"{markdown_cell(row.get('current_promotion_generated_at', ''))} | "
            f"{markdown_cell(row.get('promotion_decision', ''))} | "
            f"{markdown_cell(row.get('current_promotion_decision', ''))} | "
            f"{row.get('selected_action_current', '')} | "
            f"{markdown_cell(format_row_fingerprints(row))} | "
            f"{markdown_cell(format_row_expected_reports(row))} | "
            f"{markdown_cell(reason_text)} |"
        )
    lines.extend(
        [
            "",
            "## Invalid",
            "",
            "| id | runner generated | gate generated | current gate | decision | current decision | action current | fingerprints | reason | command |",
            "|---|---|---|---|---|---|---:|---|---|---|",
        ]
    )
    for row in report.get("invalid", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {markdown_cell(row.get('id', ''))} | "
            f"{markdown_cell(row.get('runner_generated_at', ''))} | "
            f"{markdown_cell(row.get('promotion_generated_at', ''))} | "
            f"{markdown_cell(row.get('current_promotion_generated_at', ''))} | "
            f"{markdown_cell(row.get('promotion_decision', ''))} | "
            f"{markdown_cell(row.get('current_promotion_decision', ''))} | "
            f"{row.get('selected_action_current', '')} | "
            f"{markdown_cell(format_row_fingerprints(row))} | "
            f"{markdown_cell(row.get('reason', ''))} | "
            f"{markdown_cell(row.get('command_text', ''))} |"
        )
    if report.get("executions"):
        lines.extend(["", "## Executions", "", "| id | ok | returncode |", "|---|---:|---:|"])
        for row in report.get("executions", []):
            if not isinstance(row, dict):
                continue
            lines.append(
                f"| {markdown_cell(row.get('id', ''))} | {row.get('ok')} | {row.get('returncode', '')} |"
            )
    return "\n".join(lines).rstrip() + "\n"


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect ready entries from the MT5 manual Strategy Tester queue.")
    parser.add_argument("--queue", default=DEFAULT_QUEUE)
    parser.add_argument(
        "--refresh-queue",
        dest="refresh_queue",
        action="store_true",
        default=True,
        help="Refresh source runner readiness and rewrite the queue before selecting ready entries.",
    )
    parser.add_argument(
        "--no-refresh-queue",
        dest="refresh_queue",
        action="store_false",
        help="Use the queue JSON as-is without recomputing readiness.",
    )
    parser.add_argument("--execute", action="store_true", help="Run ready collect-only commands. Default is dry-run.")
    parser.add_argument(
        "--promotion-gate",
        default="",
        help="Promotion Gate JSON used when refreshing the manual queue. Defaults to latest_promotion_gate for the default queue.",
    )
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument(
        "--refresh-strategy-tester-analysis",
        action="store_true",
        help="After a successful --execute collect, refresh the MT5 Strategy Tester analysis report.",
    )
    parser.add_argument(
        "--refresh-promotion-gate",
        action="store_true",
        help="After a successful --execute collect, refresh Promotion Gate before downstream analysis.",
    )
    parser.add_argument(
        "--refresh-spec-coverage",
        action="store_true",
        help="After a successful --execute collect, refresh Spec Coverage after downstream analysis.",
    )
    parser.add_argument(
        "--refresh-post-collect-analysis",
        action="store_true",
        help="After a successful --execute collect, refresh Promotion Gate, Strategy Tester Analysis, and Spec Coverage.",
    )
    parser.add_argument(
        "--strategy-tester-analysis-output-json",
        default=DEFAULT_STRATEGY_TESTER_ANALYSIS_OUTPUT_JSON,
    )
    parser.add_argument(
        "--strategy-tester-analysis-output-md",
        default=DEFAULT_STRATEGY_TESTER_ANALYSIS_OUTPUT_MD,
    )
    parser.add_argument("--promotion-gate-output-json", default="runtime/latest_promotion_gate.json")
    parser.add_argument("--promotion-gate-output-md", default="runtime/latest_promotion_gate.md")
    parser.add_argument("--spec-coverage-output-json", default=DEFAULT_SPEC_COVERAGE_OUTPUT_JSON)
    parser.add_argument("--spec-coverage-output-md", default=DEFAULT_SPEC_COVERAGE_OUTPUT_MD)
    parser.add_argument("--print-full-report", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        queue_path=args.queue,
        queue=load_json(args.queue),
        execute=args.execute,
        refresh_queue=args.refresh_queue,
        promotion_gate=args.promotion_gate,
    )
    refresh_promotion_gate = bool(args.refresh_promotion_gate or args.refresh_post_collect_analysis)
    refresh_strategy_tester_analysis = bool(
        args.refresh_strategy_tester_analysis or args.refresh_post_collect_analysis
    )
    refresh_spec_coverage = bool(args.refresh_spec_coverage or args.refresh_post_collect_analysis)
    if refresh_promotion_gate:
        if report.get("status") == "collect_executed":
            report["promotion_gate_refresh"] = refresh_promotion_gate_report(
                output_json=args.promotion_gate_output_json,
                output_md=args.promotion_gate_output_md,
            )
        else:
            report["promotion_gate_refresh"] = {
                "enabled": True,
                "ok": False,
                "status": "skipped",
                "reason": "manual_collect_status_is_" + str(report.get("status") or "unknown"),
                "output_json": args.promotion_gate_output_json,
                "output_md": args.promotion_gate_output_md,
            }
    else:
        report["promotion_gate_refresh"] = {"enabled": False, "status": "not_requested"}
    if refresh_strategy_tester_analysis:
        if report.get("status") == "collect_executed":
            report["strategy_tester_analysis_refresh"] = refresh_strategy_tester_analysis_report(
                output_json=args.strategy_tester_analysis_output_json,
                output_md=args.strategy_tester_analysis_output_md,
            )
        else:
            report["strategy_tester_analysis_refresh"] = {
                "enabled": True,
                "ok": False,
                "status": "skipped",
                "reason": "manual_collect_status_is_" + str(report.get("status") or "unknown"),
                "output_json": args.strategy_tester_analysis_output_json,
                "output_md": args.strategy_tester_analysis_output_md,
            }
    else:
        report["strategy_tester_analysis_refresh"] = {"enabled": False, "status": "not_requested"}
    if refresh_spec_coverage:
        if report.get("status") == "collect_executed":
            report["spec_coverage_refresh"] = refresh_spec_coverage_report(
                output_json=args.spec_coverage_output_json,
                output_md=args.spec_coverage_output_md,
            )
        else:
            report["spec_coverage_refresh"] = {
                "enabled": True,
                "ok": False,
                "status": "skipped",
                "reason": "manual_collect_status_is_" + str(report.get("status") or "unknown"),
                "output_json": args.spec_coverage_output_json,
                "output_md": args.spec_coverage_output_md,
            }
    else:
        report["spec_coverage_refresh"] = {"enabled": False, "status": "not_requested"}
    write_json(args.output_json, report)
    write_text(args.output_md, format_markdown(report))
    summary = {
        "ok": report.get("ok"),
        "status": report.get("status"),
        "execute": report.get("execute"),
        "next_action": report.get("next_action", ""),
        "queue_refresh_status": (
            report.get("queue_refresh") if isinstance(report.get("queue_refresh"), dict) else {}
        ).get("status", ""),
        "queue_refresh_ok": (
            report.get("queue_refresh") if isinstance(report.get("queue_refresh"), dict) else {}
        ).get("ok", ""),
        "queue_refresh_source_count": (
            report.get("queue_refresh") if isinstance(report.get("queue_refresh"), dict) else {}
        ).get("source_count", ""),
        "selected_count": report.get("selected_count", 0),
        "completed_count": report.get("completed_count", 0),
        "waiting_count": report.get("waiting_count", 0),
        "invalid_count": report.get("invalid_count", 0),
        "strategy_tester_analysis_refresh_status": (
            report.get("strategy_tester_analysis_refresh")
            if isinstance(report.get("strategy_tester_analysis_refresh"), dict)
            else {}
        ).get("status", ""),
        "strategy_tester_analysis_refresh_ok": (
            report.get("strategy_tester_analysis_refresh")
            if isinstance(report.get("strategy_tester_analysis_refresh"), dict)
            else {}
        ).get("ok", ""),
        "promotion_gate_refresh_status": (
            report.get("promotion_gate_refresh")
            if isinstance(report.get("promotion_gate_refresh"), dict)
            else {}
        ).get("status", ""),
        "promotion_gate_refresh_ok": (
            report.get("promotion_gate_refresh")
            if isinstance(report.get("promotion_gate_refresh"), dict)
            else {}
        ).get("ok", ""),
        "spec_coverage_refresh_status": (
            report.get("spec_coverage_refresh")
            if isinstance(report.get("spec_coverage_refresh"), dict)
            else {}
        ).get("status", ""),
        "spec_coverage_refresh_ok": (
            report.get("spec_coverage_refresh")
            if isinstance(report.get("spec_coverage_refresh"), dict)
            else {}
        ).get("ok", ""),
        "output_json": args.output_json,
        "output_md": args.output_md,
    }
    print(json.dumps(report if args.print_full_report else summary, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
