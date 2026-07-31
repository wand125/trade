from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT
from analysis.mt5_next_action_run import (
    archive_preview_artifact_validation,
    command_option_value,
    execution_artifact_summary,
    optimization_artifact_summary,
    tester_run_artifact_summary,
)
from analysis.mt5_compile_status import default_mt5_root
from analysis.mt5_tester_optimization_report import discover_tester_csvs, parse_modified_after
from analysis.mt5_tester_run import (
    tester_config_metadata,
    tester_html_report_paths,
    tester_report_expectation,
    tester_report_paths,
)


DEFAULT_OUTPUT_JSON = "runtime/latest_mt5_back_forward_run.json"
DEFAULT_OUTPUT_MD = "runtime/latest_mt5_back_forward_run.md"
DEFAULT_READY_STATUS = "runtime/latest_mt5_tester_status.json"
DEFAULT_READY_STATUS_MD = "runtime/latest_mt5_tester_status.md"
DEFAULT_COMPILE_STATUS = "runtime/latest_mt5_compile_status.json"
DEFAULT_BRIDGE_RECOVERY_PLAN = "runtime/latest_bridge_recovery_plan.json"
DEFAULT_READY_STATUS_MAX_AGE_SECONDS = 600
FORWARD_MODE_LABELS = {
    "0": "Disabled",
    "1": "1/2",
    "2": "1/3",
    "3": "1/4",
    "4": "Custom",
}
FORWARD_MODE_FRACTIONS = {
    "1": 1.0 / 2.0,
    "2": 1.0 / 3.0,
    "3": 1.0 / 4.0,
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
PREFLIGHT_COMMAND_OPTIONS = (
    "--timeout-seconds",
    "--since-minutes",
    "--min-closed",
    "--from-date",
    "--to-date",
    "--forward-mode",
    "--agent-csv-archive-run-id",
)
PREFLIGHT_COMMAND_FLAGS = (
    "--sync-expert-parameters-set",
    "--allow-running-terminal",
    "--allow-stale-compile",
    "--allow-invalid-risk-preset",
)
PREFLIGHT_EXECUTION_CONDITION_KEYS = (
    "per_step_timeout_seconds",
    "since_minutes",
    "min_closed",
    "from_date",
    "to_date",
    "forward_mode",
    "sync_expert_parameters_set",
    "allow_running_terminal",
    "allow_stale_compile",
    "allow_invalid_risk_preset",
    "require_bridge_ready",
    "skip_archive_preview",
    "max_ready_status_age_seconds",
)
PREFLIGHT_OUTPUT_KEYS = (
    "run_json",
    "run_md",
    "report_json",
    "report_md",
)
PREFLIGHT_STEP_KEYS = (
    "expert",
    "expert_parameters",
    "forward_mode",
    "base_from_date",
    "base_to_date",
    "archive_run_id",
)
RUNNER_HINT_OPTIONS = (
    "--timeout-seconds",
    "--since-minutes",
    "--min-closed",
    "--from-date",
    "--to-date",
    "--forward-mode",
)
RUNNER_HINT_FLAGS = (
    "--sync-expert-parameters-set",
    "--allow-running-terminal",
    "--allow-stale-compile",
    "--allow-invalid-risk-preset",
    "--require-bridge-ready",
    "--skip-archive-preview",
)

RUN_PLANS: dict[str, dict[str, str]] = {
    "backtest": {
        "label": "backtest",
        "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_backtest.ini",
        "report_name": "Tester\\Swing_Evaluation_Trader_backtest",
        "run_json": "runtime/latest_mt5_tester_backtest_run.json",
        "run_md": "runtime/latest_mt5_tester_backtest_run.md",
        "report_json": "runtime/latest_mt5_backtest_report.json",
        "report_md": "runtime/latest_mt5_backtest_report.md",
    },
    "forward": {
        "label": "forward",
        "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_forward_test.ini",
        "report_name": "Tester\\Swing_Evaluation_Trader_forward_test",
        "run_json": "runtime/latest_mt5_tester_forward_test_run.json",
        "run_md": "runtime/latest_mt5_tester_forward_test_run.md",
        "report_json": "runtime/latest_mt5_forward_strategy_report.json",
        "report_md": "runtime/latest_mt5_forward_strategy_report.md",
    },
}

STEP_CONFIG_FINGERPRINT_FIELDS = (
    "label",
    "config",
    "expert",
    "symbol",
    "period",
    "model",
    "from_date",
    "to_date",
    "forward_label",
    "forward_mode_effective",
    "optimization",
    "optimization_label",
    "expert_parameters",
    "report_name",
    "run_type",
)
STEP_RUN_FINGERPRINT_FIELDS = (
    *STEP_CONFIG_FINGERPRINT_FIELDS,
    "manual_run_start_after",
)


def fingerprint_payload(item: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: item.get(field, "") for field in fields}


def stable_fingerprint(item: dict[str, Any], fields: tuple[str, ...]) -> str:
    payload = fingerprint_payload(item, fields)
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def add_step_fingerprints(item: dict[str, Any]) -> dict[str, Any]:
    item["step_config_fingerprint"] = stable_fingerprint(item, STEP_CONFIG_FINGERPRINT_FIELDS)
    item["step_run_fingerprint"] = stable_fingerprint(item, STEP_RUN_FINGERPRINT_FIELDS)
    item["step_fingerprint"] = item["step_run_fingerprint"]
    return item


def bridge_recovery_plan_summary(path: str | Path) -> dict[str, Any]:
    if not str(path):
        return {"exists": False, "path": ""}
    source = Path(path)
    payload = load_json(source)
    return {
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


def bridge_recovery_blocks_mt5_validation(summary: dict[str, Any]) -> bool:
    return bool(summary.get("exists") is True and summary.get("ready_for_mt5_validation") is False)


def bridge_recovery_block_reason(summary: dict[str, Any]) -> str:
    status = str(summary.get("status") or "not_ready")
    next_action = str(summary.get("next_action") or "")
    suffix = f"; next_action={next_action}" if next_action else ""
    return f"Bridge Recovery is not ready for MT5 validation: {status}{suffix}"


def effective_bridge_recovery_plan_path(
    bridge_recovery_plan: str | Path,
    output_json: str | Path,
) -> str:
    explicit = str(bridge_recovery_plan or "")
    if explicit:
        return explicit
    if str(output_json) != DEFAULT_OUTPUT_JSON:
        return ""
    default_path = Path(DEFAULT_BRIDGE_RECOVERY_PLAN)
    return str(default_path) if default_path.exists() else ""


def tester_config_plan_metadata(config_path: str | Path) -> dict[str, str]:
    source = Path(config_path)
    try:
        metadata = tester_config_metadata(source.read_text(encoding="utf-8"))
    except OSError:
        return {
            "expert": "",
            "expert_parameters": "",
            "forward_mode": "",
            "base_from_date": "",
            "base_to_date": "",
        }
    return {
        "expert": metadata.get("expert", ""),
        "expert_parameters": metadata.get("expert_parameters", ""),
        "symbol": metadata.get("symbol", ""),
        "period": metadata.get("period", ""),
        "model": metadata.get("model", ""),
        "execution_mode": metadata.get("execution_mode", ""),
        "optimization": metadata.get("optimization", ""),
        "optimization_criterion": metadata.get("optimization_criterion", ""),
        "forward_mode": metadata.get("forward_mode", ""),
        "forward_date": metadata.get("forward_date", ""),
        "base_from_date": metadata.get("from_date", ""),
        "base_to_date": metadata.get("to_date", ""),
        "report": metadata.get("report", ""),
    }


def selected_labels(mode: str) -> list[str]:
    if mode == "both":
        return ["backtest", "forward"]
    return [mode]


def safe_artifact_suffix(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value)
    return safe.strip("_") or "preview"


def archive_preview_output_paths(archive_run_id: str) -> tuple[str, str]:
    suffix = safe_artifact_suffix(archive_run_id)
    return (
        f"runtime/latest_mt5_agent_csv_archive_{suffix}.json",
        f"runtime/latest_mt5_agent_csv_archive_{suffix}.md",
    )


def build_archive_preview_plan(archive_run_id: str) -> dict[str, Any]:
    output_json, output_md = archive_preview_output_paths(archive_run_id)
    command = [
        "python3",
        "methods/swing_eval/analysis/mt5_agent_csv_archive.py",
        "--output-json",
        output_json,
        "--output-md",
        output_md,
        "--run-id",
        archive_run_id,
        "--include-source-time",
    ]
    return {
        "kind": "mt5_agent_csv_archive",
        "execute": False,
        "run_id": archive_run_id,
        "include_source_time": True,
        "command": command,
        "command_text": shlex.join(command),
        "planned_outputs": {
            "output_json": output_json,
            "output_md": output_md,
        },
    }


def build_tester_command(
    plan: dict[str, str],
    *,
    execute: bool,
    collect_only: bool = False,
    timeout_seconds: int,
    since_minutes: float,
    min_closed: int,
    run_id_prefix: str,
    from_date: str = "",
    to_date: str = "",
    forward_mode: str = "",
    sync_expert_parameters_set: bool = False,
    allow_running_terminal: bool = False,
    allow_stale_compile: bool = False,
    allow_invalid_risk_preset: bool = False,
    csv_modified_after: str = "",
    mt5_root: str = "",
) -> list[str]:
    archive_run_id = f"{run_id_prefix}_{plan['label']}"
    command = [
        "python3",
        "methods/swing_eval/analysis/mt5_tester_run.py",
        "--config",
        plan["config"],
        "--report-name",
        plan["report_name"],
        "--timeout-seconds",
        str(timeout_seconds),
        "--since-minutes",
        str(since_minutes),
        "--min-closed",
        str(min_closed),
        "--no-recommendation",
        "--output-json",
        plan["run_json"],
        "--output-md",
        plan["run_md"],
        "--optimization-output-json",
        plan["report_json"],
        "--optimization-output-md",
        plan["report_md"],
    ]
    if not collect_only:
        command.extend(["--archive-agent-csvs-before-run", "--agent-csv-archive-run-id", archive_run_id])
    if collect_only:
        command.append("--collect-only")
    elif not execute:
        command.append("--dry-run")
    if csv_modified_after:
        command.extend(["--csv-modified-after", csv_modified_after])
    if mt5_root:
        command.extend(["--mt5-root", mt5_root])
    if from_date:
        command.extend(["--from-date", from_date])
    if to_date:
        command.extend(["--to-date", to_date])
    if forward_mode:
        command.extend(["--forward-mode", forward_mode])
    if sync_expert_parameters_set:
        command.append("--sync-expert-parameters-set")
    if allow_running_terminal:
        command.append("--allow-running-terminal")
    if allow_stale_compile:
        command.append("--allow-stale-compile")
    if allow_invalid_risk_preset:
        command.append("--allow-invalid-risk-preset")
    return command


def step_forward_mode_override(label: str, requested_forward_mode: str) -> str:
    if str(label or "") == "backtest":
        return ""
    return requested_forward_mode


def step_effective_forward_mode(label: str, base_forward_mode: str, requested_forward_mode: str) -> str:
    override = step_forward_mode_override(label, requested_forward_mode)
    if override:
        return override
    if str(label or "") == "backtest":
        return "0"
    return base_forward_mode


def parse_tester_date(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for pattern in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    return None


def format_tester_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.hour == 0 and value.minute == 0 and value.second == 0 and value.microsecond == 0:
        return value.strftime("%Y.%m.%d")
    return value.strftime("%Y.%m.%d %H:%M")


def tester_range_text(start: str, end: str) -> str:
    if start and end:
        return f"{start} -> {end}"
    if start:
        return f"{start} ->"
    if end:
        return f"-> {end}"
    return ""


def forward_window_summary(
    *,
    from_date: str,
    to_date: str,
    forward_mode: str,
    forward_date: str = "",
) -> dict[str, Any]:
    mode = str(forward_mode or "")
    label = label_from_mapping(mode, FORWARD_MODE_LABELS)
    start = parse_tester_date(from_date)
    end = parse_tester_date(to_date)
    enabled = mode not in {"", "0"}
    base_range = tester_range_text(from_date, to_date)
    if not enabled:
        return {
            "enabled": False,
            "status": "disabled",
            "method": "no_forward_split",
            "forward_mode": mode,
            "forward_label": label,
            "from_date": from_date,
            "to_date": to_date,
            "training_from": from_date,
            "training_to": to_date,
            "forward_from": "",
            "forward_to": "",
            "training_range": base_range,
            "forward_range": "",
            "summary": f"backtest/full range {base_range}" if base_range else "backtest/full range",
            "note": "ForwardMode is disabled; the whole Tester range is treated as backtest.",
        }
    if start is None or end is None or end <= start:
        return {
            "enabled": True,
            "status": "invalid_date_range",
            "method": "unknown",
            "forward_mode": mode,
            "forward_label": label,
            "from_date": from_date,
            "to_date": to_date,
            "training_from": from_date,
            "training_to": "",
            "forward_from": "",
            "forward_to": to_date,
            "training_range": "",
            "forward_range": "",
            "summary": f"forward {label}; invalid date range {base_range}".strip(),
            "note": "Cannot estimate the MT5 forward split because FromDate/ToDate are invalid.",
        }
    split: datetime | None = None
    method = ""
    fraction = FORWARD_MODE_FRACTIONS.get(mode)
    if fraction is not None:
        split = end - timedelta(seconds=(end - start).total_seconds() * fraction)
        method = f"last_{label.replace('/', '_')}"
    elif mode == "4":
        split = parse_tester_date(forward_date)
        method = "custom_forward_date"
    if split is None or split <= start or split >= end:
        return {
            "enabled": True,
            "status": "custom_forward_date_missing" if mode == "4" else "unknown_forward_split",
            "method": method or "unknown",
            "forward_mode": mode,
            "forward_label": label,
            "forward_fraction": fraction,
            "forward_date": forward_date,
            "from_date": from_date,
            "to_date": to_date,
            "training_from": from_date,
            "training_to": "",
            "forward_from": "",
            "forward_to": to_date,
            "training_range": "",
            "forward_range": "",
            "summary": f"forward {label}; split not estimated for {base_range}".strip(),
            "note": "Set ForwardDate for Custom mode or use 1/2, 1/3, or 1/4 to estimate the split.",
        }
    split_text = format_tester_datetime(split)
    training_range = tester_range_text(from_date, split_text)
    forward_range = tester_range_text(split_text, to_date)
    return {
        "enabled": True,
        "status": "estimated",
        "method": method,
        "forward_mode": mode,
        "forward_label": label,
        "forward_fraction": fraction,
        "forward_date": forward_date,
        "from_date": from_date,
        "to_date": to_date,
        "training_from": from_date,
        "training_to": split_text,
        "forward_from": split_text,
        "forward_to": to_date,
        "training_range": training_range,
        "forward_range": forward_range,
        "summary": f"train {training_range}; forward {forward_range} ({label})",
        "note": "Estimated from Tester FromDate/ToDate and ForwardMode; verify against MT5 report/server_time after collection.",
    }


def build_plan(
    *,
    mode: str,
    execute: bool,
    collect_only: bool = False,
    timeout_seconds: int,
    since_minutes: float,
    min_closed: int,
    run_id_prefix: str,
    from_date: str = "",
    to_date: str = "",
    forward_mode: str = "",
    sync_expert_parameters_set: bool = False,
    allow_running_terminal: bool = False,
    allow_stale_compile: bool = False,
    allow_invalid_risk_preset: bool = False,
    csv_modified_after: str = "",
    mt5_root: str = "",
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for label in selected_labels(mode):
        plan = RUN_PLANS[label]
        archive_run_id = f"{run_id_prefix}_{label}"
        config_metadata = tester_config_plan_metadata(plan["config"])
        base_forward_mode = str(config_metadata.get("forward_mode", ""))
        step_forward_override = step_forward_mode_override(label, forward_mode)
        effective_forward_mode = step_effective_forward_mode(label, base_forward_mode, forward_mode)
        effective_from_date = from_date or str(config_metadata.get("base_from_date", ""))
        effective_to_date = to_date or str(config_metadata.get("base_to_date", ""))
        tester_window = forward_window_summary(
            from_date=effective_from_date,
            to_date=effective_to_date,
            forward_mode=effective_forward_mode,
            forward_date=str(config_metadata.get("forward_date", "")),
        )
        command = build_tester_command(
            plan,
            execute=execute,
            collect_only=collect_only,
            timeout_seconds=timeout_seconds,
            since_minutes=since_minutes,
            min_closed=min_closed,
            run_id_prefix=run_id_prefix,
            from_date=from_date,
            to_date=to_date,
            forward_mode=step_forward_override,
            sync_expert_parameters_set=sync_expert_parameters_set,
            allow_running_terminal=allow_running_terminal,
            allow_stale_compile=allow_stale_compile,
            allow_invalid_risk_preset=allow_invalid_risk_preset,
            csv_modified_after=csv_modified_after,
            mt5_root=mt5_root,
        )
        steps.append(
            {
                "label": label,
                "config": plan["config"],
                **config_metadata,
                "base_forward_mode": base_forward_mode,
                "forward_mode_override": step_forward_override,
                "requested_forward_mode": forward_mode,
                "effective_forward_mode": effective_forward_mode,
                "effective_from_date": effective_from_date,
                "effective_to_date": effective_to_date,
                "tester_window": tester_window,
                "window_summary": tester_window.get("summary", ""),
                "training_range": tester_window.get("training_range", ""),
                "forward_range": tester_window.get("forward_range", ""),
                "report_name": plan["report_name"],
                "archive_run_id": archive_run_id,
                "archive_preview": build_archive_preview_plan(archive_run_id),
                "outputs": {
                    "run_json": plan["run_json"],
                    "run_md": plan["run_md"],
                    "report_json": plan["report_json"],
                    "report_md": plan["report_md"],
                },
                "command": command,
                "command_text": shlex.join(command),
            }
        )
    return steps


def run_command(command: list[str]) -> dict[str, Any]:
    started = time.time()
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "elapsed_seconds": round(time.time() - started, 3),
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def refresh_ready_status(
    status_path: str | Path,
    status_md_path: str | Path = DEFAULT_READY_STATUS_MD,
    *,
    back_forward_run_path: str | Path | None = None,
) -> dict[str, Any]:
    command = [
        "python3",
        "methods/swing_eval/analysis/mt5_tester_status.py",
        "--output-json",
        str(status_path),
    ]
    if status_md_path:
        command.extend(["--output-md", str(status_md_path)])
    if back_forward_run_path:
        command.extend(["--back-forward-run", str(back_forward_run_path)])
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
        "status_back_forward_execution_ready": (
            status_payload.get("back_forward_execution", {}).get("ready", "")
            if isinstance(status_payload.get("back_forward_execution"), dict)
            else ""
        ),
        "command": command,
        "command_text": shlex.join(command),
        "output_json": str(status_path),
        "output_md": str(status_md_path),
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


def plan_config_by_label(steps: list[dict[str, Any]]) -> dict[str, str]:
    return {str(step.get("label", "")): str(step.get("config", "")) for step in steps if isinstance(step, dict)}


def plan_value_by_label(steps: list[dict[str, Any]], key: str) -> dict[str, str]:
    return {str(step.get("label", "")): str(step.get(key, "")) for step in steps if isinstance(step, dict)}


def step_output_value(step: dict[str, Any], key: str) -> str:
    outputs = step.get("outputs") if isinstance(step.get("outputs"), dict) else {}
    return str(outputs.get(key) or step.get(key) or "")


def plan_output_by_label(steps: list[dict[str, Any]], key: str) -> dict[str, str]:
    return {str(step.get("label", "")): step_output_value(step, key) for step in steps if isinstance(step, dict)}


def step_command(step: dict[str, Any]) -> list[str]:
    command = step.get("command")
    return [str(item) for item in command] if isinstance(command, list) else []


def command_flag_present(command: list[str], flag: str) -> bool:
    return flag in command


def command_signature_by_label(steps: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    signatures: dict[str, dict[str, Any]] = {}
    for step in steps:
        if not isinstance(step, dict):
            continue
        label = str(step.get("label", ""))
        command = step_command(step)
        signatures[label] = {
            "command_present": bool(command),
            "options": {option: command_option_value(command, option) for option in PREFLIGHT_COMMAND_OPTIONS},
            "flags": {flag: command_flag_present(command, flag) for flag in PREFLIGHT_COMMAND_FLAGS},
        }
    return signatures


def execution_condition_values_match(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if left in (None, "") and right in (None, ""):
        return True
    try:
        return float(str(left)) == float(str(right))
    except (TypeError, ValueError):
        pass
    if isinstance(left, (dict, list)) or isinstance(right, (dict, list)):
        return json.dumps(left, sort_keys=True, ensure_ascii=False) == json.dumps(
            right, sort_keys=True, ensure_ascii=False
        )
    return str(left) == str(right)


def numeric_seconds(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        seconds = float(str(value))
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


def execution_window_summary(steps: list[dict[str, Any]], *, now_epoch: float | None = None) -> dict[str, Any]:
    step_timeouts: list[dict[str, Any]] = []
    total_seconds = 0.0
    complete = True
    for step in steps:
        if not isinstance(step, dict):
            continue
        command = step_command(step)
        seconds = numeric_seconds(command_option_value(command, "--timeout-seconds"))
        if seconds is None:
            complete = False
        else:
            total_seconds += seconds
        step_timeouts.append(
            {
                "label": step.get("label", ""),
                "timeout_seconds": seconds,
                "timeout_minutes": round(seconds / 60.0, 3) if seconds is not None else None,
            }
        )
    start_epoch = time.time() if now_epoch is None else now_epoch
    deadline_epoch = start_epoch + total_seconds if complete else None
    return {
        "available": bool(step_timeouts),
        "complete": complete,
        "step_count": len(step_timeouts),
        "steps": step_timeouts,
        "total_timeout_seconds": int(total_seconds) if total_seconds.is_integer() else round(total_seconds, 3),
        "total_timeout_minutes": round(total_seconds / 60.0, 3),
        "timeout_start_reference_at": datetime.fromtimestamp(start_epoch).strftime(TIME_FORMAT),
        "timeout_deadline_if_started_now": (
            datetime.fromtimestamp(deadline_epoch).strftime(TIME_FORMAT) if deadline_epoch is not None else ""
        ),
        "timeout_deadline_epoch_if_started_now": round(deadline_epoch, 3) if deadline_epoch is not None else None,
        "note": "Sequential upper bound from each step --timeout-seconds; MT5 may finish earlier.",
    }


def execution_conditions_summary(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "per_step_timeout_seconds": args.timeout_seconds,
        "since_minutes": args.since_minutes,
        "min_closed": args.min_closed,
        "collect_only": args.collect_only,
        "csv_modified_after": args.csv_modified_after,
        "from_date": args.from_date,
        "to_date": args.to_date,
        "forward_mode": args.forward_mode,
        "sync_expert_parameters_set": args.sync_expert_parameters_set,
        "allow_running_terminal": args.allow_running_terminal,
        "allow_stale_compile": args.allow_stale_compile,
        "allow_invalid_risk_preset": args.allow_invalid_risk_preset,
        "require_bridge_ready": args.require_bridge_ready,
        "refresh_ready_status": args.refresh_ready_status,
        "skip_ready_status_check": args.skip_ready_status_check,
        "skip_archive_preview": args.skip_archive_preview,
        "max_ready_status_age_seconds": args.max_ready_status_age_seconds,
        "checked_command_options": list(PREFLIGHT_COMMAND_OPTIONS),
        "checked_command_flags": list(PREFLIGHT_COMMAND_FLAGS),
    }


def runner_hint_base_options(args: argparse.Namespace) -> list[str]:
    options: list[str] = []
    values = {
        "--timeout-seconds": args.timeout_seconds,
        "--since-minutes": args.since_minutes,
        "--min-closed": args.min_closed,
        "--from-date": args.from_date,
        "--to-date": args.to_date,
        "--forward-mode": args.forward_mode,
    }
    for option in RUNNER_HINT_OPTIONS:
        value = values.get(option, "")
        if value not in (None, ""):
            options.extend([option, str(value)])
    if getattr(args, "mt5_root", ""):
        options.extend(["--mt5-root", str(args.mt5_root)])
    for flag, enabled in (
        ("--sync-expert-parameters-set", args.sync_expert_parameters_set),
        ("--allow-running-terminal", args.allow_running_terminal),
        ("--allow-stale-compile", args.allow_stale_compile),
        ("--allow-invalid-risk-preset", args.allow_invalid_risk_preset),
        ("--require-bridge-ready", args.require_bridge_ready),
        ("--skip-archive-preview", args.skip_archive_preview),
    ):
        if enabled:
            options.append(flag)
    if args.compile_status != DEFAULT_COMPILE_STATUS:
        options.extend(["--compile-status", args.compile_status])
    if getattr(args, "bridge_recovery_plan", ""):
        options.extend(["--bridge-recovery-plan", str(args.bridge_recovery_plan)])
    return options


def runner_execution_hints(
    args: argparse.Namespace,
    *,
    run_id_prefix: str,
    csv_modified_after: str = "",
) -> dict[str, Any]:
    base = ["python3", "methods/swing_eval/analysis/mt5_back_forward_run.py", "--mode", args.mode]
    run_id = ["--run-id-prefix", run_id_prefix] if run_id_prefix else []
    options = runner_hint_base_options(args)
    execute = [
        *base,
        "--execute",
        "--refresh-ready-status",
        *run_id,
        *options,
        "--max-ready-status-age-seconds",
        str(args.max_ready_status_age_seconds),
    ]
    collect_only = [
        *base,
        "--collect-only",
        *run_id,
        *options,
    ]
    modified_after = str(args.csv_modified_after or csv_modified_after or "")
    if modified_after:
        collect_only.extend(["--csv-modified-after", modified_after])
    return {
        "execute_command": execute,
        "execute_command_text": shlex.join(execute),
        "collect_only_command": collect_only,
        "collect_only_command_text": shlex.join(collect_only),
        "collect_only_note": (
            "For manual MT5 Strategy Tester runs, use --csv-modified-after with the manual run start time "
            "to filter out older Agent CSV files."
        ),
        "options_preserved": [
            *RUNNER_HINT_OPTIONS,
            *(["--mt5-root"] if getattr(args, "mt5_root", "") else []),
        ],
        "flags_preserved": list(RUNNER_HINT_FLAGS),
    }


def label_from_mapping(value: Any, labels: dict[str, str]) -> str:
    text = str(value or "")
    if not text:
        return ""
    return labels.get(text, text)


def append_csv_modified_after(command: list[str], generated_at: str) -> list[str]:
    if "--csv-modified-after" in command or not generated_at:
        return list(command)
    return [*command, "--csv-modified-after", generated_at]


def manual_strategy_tester_step(
    step: dict[str, Any],
    *,
    order: int,
    manual_run_start_after: str = "",
) -> dict[str, Any]:
    model = str(step.get("model") or "")
    optimization = str(step.get("optimization") or "")
    forward_mode = str(step.get("effective_forward_mode") or step.get("forward_mode") or "")
    from_date = str(step.get("effective_from_date") or step.get("base_from_date") or "")
    to_date = str(step.get("effective_to_date") or step.get("base_to_date") or "")
    report_expectation = tester_report_expectation(optimization, forward_mode)
    tester_window = (
        step.get("tester_window")
        if isinstance(step.get("tester_window"), dict) and step.get("tester_window")
        else forward_window_summary(
            from_date=from_date,
            to_date=to_date,
            forward_mode=forward_mode,
            forward_date=str(step.get("forward_date", "")),
        )
    )
    row = {
        "order": order,
        "label": step.get("label", ""),
        "config": step.get("config", ""),
        "expert": step.get("expert", ""),
        "symbol": step.get("symbol", ""),
        "period": step.get("period", ""),
        "model": model,
        "model_label": label_from_mapping(model, MODEL_LABELS),
        "optimization": optimization,
        "optimization_label": label_from_mapping(optimization, OPTIMIZATION_LABELS),
        "optimization_enabled": optimization not in ("", "0"),
        "from_date": from_date,
        "to_date": to_date,
        "forward_mode_base": step.get("base_forward_mode", step.get("forward_mode", "")),
        "forward_mode_override": step.get("forward_mode_override", ""),
        "forward_mode_effective": forward_mode,
        "forward_label": label_from_mapping(forward_mode, FORWARD_MODE_LABELS),
        "tester_window": tester_window,
        "window_summary": step.get("window_summary", "") or tester_window.get("summary", ""),
        "training_range": step.get("training_range", "") or tester_window.get("training_range", ""),
        "forward_range": step.get("forward_range", "") or tester_window.get("forward_range", ""),
        "expert_parameters": step.get("expert_parameters", ""),
        "report_name": step.get("report_name", ""),
        "run_json": step_output_value(step, "run_json"),
        "report_json": step_output_value(step, "report_json"),
        "manual_run_start_after": manual_run_start_after,
        **report_expectation,
    }
    row["expected_artifacts"] = {
        "report": row.get("report_name", ""),
        "expected_report_artifact": row.get("expected_report_artifact", ""),
        "agent_csv": "swing_evaluation_trades.csv",
        "agent_csv_modified_after": manual_run_start_after,
        "run_json": row.get("run_json", ""),
        "report_json": row.get("report_json", ""),
    }
    return add_step_fingerprints(row)


def build_manual_strategy_tester_plan(
    args: argparse.Namespace,
    *,
    run_id_prefix: str,
    steps: list[dict[str, Any]],
    generated_at: str,
    execution_hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hints = execution_hints if isinstance(execution_hints, dict) else runner_execution_hints(args, run_id_prefix=run_id_prefix)
    collect_command = [str(item) for item in hints.get("collect_only_command", [])] if isinstance(hints.get("collect_only_command"), list) else []
    manual_run_start_after = str(args.csv_modified_after or generated_at)
    recommended_collect = append_csv_modified_after(collect_command, manual_run_start_after)
    manual_steps = [
        manual_strategy_tester_step(
            step,
            order=index + 1,
            manual_run_start_after=manual_run_start_after,
        )
        for index, step in enumerate(steps)
        if isinstance(step, dict)
    ]
    return {
        "available": bool(manual_steps),
        "purpose": "Manual MT5 Strategy Tester path when MT5 is already open or /config launch is blocked.",
        "manual_run_start_after": manual_run_start_after,
        "run_id_prefix": run_id_prefix,
        "recommended_collect_only_command": recommended_collect,
        "recommended_collect_only_command_text": shlex.join(recommended_collect) if recommended_collect else "",
        "collect_only_note": (
            "Run Backtest and Forward steps in MT5 first, then use this command. "
            "--csv-modified-after filters out older Agent CSV files."
        ),
        "steps": manual_steps,
    }


def mt5_strategy_tester_step_purpose(label: object) -> str:
    text = str(label or "")
    if text == "backtest":
        return "Backtest"
    if text == "forward":
        return "Forward Test"
    return text


def compact_mt5_strategy_tester_step(row: dict[str, Any]) -> dict[str, Any]:
    run_type = str(row.get("run_type") or "")
    if run_type == "single_strategy_test":
        mt5_screen_mode = "Single Strategy Test"
    elif run_type == "single_strategy_test_forward_profile":
        mt5_screen_mode = "Single Strategy Test + Forward profile"
    elif run_type == "optimization_forward":
        mt5_screen_mode = "Optimization Forward"
    elif run_type == "optimization":
        mt5_screen_mode = "Optimization"
    else:
        mt5_screen_mode = run_type
    return {
        "order": row.get("order", ""),
        "purpose": mt5_strategy_tester_step_purpose(row.get("label", "")),
        "step": row.get("label", ""),
        "expert": row.get("expert", ""),
        "symbol": row.get("symbol", ""),
        "period": row.get("period", ""),
        "model": row.get("model_label", row.get("model", "")),
        "dates": f"{row.get('from_date', '')} -> {row.get('to_date', '')}",
        "forward": row.get("forward_label", ""),
        "optimization": row.get("optimization_label", ""),
        "run_type": run_type,
        "mt5_screen_mode": mt5_screen_mode,
        "step_fingerprint": row.get("step_fingerprint", ""),
        "step_config_fingerprint": row.get("step_config_fingerprint", ""),
        "step_run_fingerprint": row.get("step_run_fingerprint", ""),
        "expected_report": row.get("expected_report_artifact", ""),
        "report_note": row.get("report_expectation_note", ""),
        "expected_artifacts": (
            row.get("expected_artifacts") if isinstance(row.get("expected_artifacts"), dict) else {}
        ),
        "inputs": row.get("expert_parameters", ""),
        "report": row.get("report_name", ""),
        "manual_run_start_after": row.get("manual_run_start_after", ""),
        "tester_window": row.get("tester_window", {}) if isinstance(row.get("tester_window"), dict) else {},
        "window_summary": row.get("window_summary", ""),
        "training_range": row.get("training_range", ""),
        "forward_range": row.get("forward_range", ""),
    }


def build_mt5_strategy_tester_pack(
    *,
    manual_plan: dict[str, Any],
    manual_prerequisites: dict[str, Any],
    plan_validation: dict[str, Any],
    collect_readiness: dict[str, Any],
) -> dict[str, Any]:
    manual_steps = manual_plan.get("steps") if isinstance(manual_plan.get("steps"), list) else []
    steps = [
        compact_mt5_strategy_tester_step(row)
        for row in manual_steps
        if isinstance(row, dict)
    ]
    labels = [str(row.get("step") or "") for row in steps]
    available = bool(manual_plan.get("available") and steps)
    prerequisites_ready = manual_prerequisites.get("ready") is True
    plan_ready = plan_validation.get("ready") is True
    collect_ready = collect_readiness.get("ready") is True
    ready_for_manual_run = available and prerequisites_ready and plan_ready and not collect_ready
    if not available:
        status = "missing_manual_strategy_tester_plan"
        next_action = "refresh_mt5_back_forward_run"
    elif not prerequisites_ready:
        status = "manual_prerequisites_not_ready"
        next_action = "refresh_mt5_compile_status_and_sync_tester_files"
    elif not plan_ready:
        status = "back_forward_plan_not_ready"
        next_action = "fix_back_forward_plan_validation"
    elif collect_ready:
        status = "ready_to_collect"
        next_action = "run_collect_only_command"
    else:
        status = "ready_for_mt5_strategy_tester"
        next_action = "run_backtest_then_forward_in_mt5_strategy_tester"
    return {
        "available": available,
        "ready_for_manual_mt5_run": ready_for_manual_run,
        "status": status,
        "next_action": next_action,
        "is_back_forward_pair": labels == ["backtest", "forward"],
        "manual_run_start_after": manual_plan.get("manual_run_start_after", ""),
        "collect_command_text": manual_plan.get("recommended_collect_only_command_text", ""),
        "collect_note": manual_plan.get("collect_only_note", ""),
        "collect_ready": collect_ready,
        "collect_status": collect_readiness.get("status", ""),
        "collect_reason": collect_readiness.get("reason", ""),
        "step_count": len(steps),
        "steps": steps,
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


def manual_collect_readiness(
    *,
    steps: list[dict[str, Any]],
    mt5_root: str | Path,
    modified_after: str,
    since_minutes: float,
    min_closed: int,
) -> dict[str, Any]:
    mt5 = Path(mt5_root).expanduser()
    tester_root = mt5 / "Tester"
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
            "since_minutes": since_minutes,
            "min_closed": min_closed,
            "csv_count": 0,
            "steps": [],
        }

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
        optimization = str(step.get("optimization") or "").strip().lower()
        optimization_enabled = optimization not in {"", "0", "false", "no"}
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
        step_rows.append(
            {
                "label": step.get("label", ""),
                "report_name": report_name,
                "optimization_enabled": optimization_enabled,
                "report_ready": report_ready,
                "report_status": report_status,
                "selected_report": selected_report,
                "xml_reports": xml_rows,
                "html_reports": html_rows,
                "collect_ready": report_ready and bool(csv_files),
                "blocking_reason": "" if report_ready else f"{step.get('label', '')}:waiting_report",
            }
        )

    reports_ready = bool(step_rows) and all(row.get("report_ready") is True for row in step_rows)
    csv_ready = bool(csv_files)
    blocking_reasons: list[str] = [
        str(row.get("blocking_reason"))
        for row in step_rows
        if row.get("blocking_reason")
    ]
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
        next_action = "run_manual_strategy_tester_steps_and_wait_for_agent_csv"
        reason = ", ".join(blocking_reasons)
    elif not reports_ready:
        next_action = "run_missing_manual_strategy_tester_steps"
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


def row_by_name(rows: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        if name:
            indexed[name] = row
    return indexed


def required_manual_prerequisite_names(steps: list[dict[str, Any]]) -> dict[str, list[str]]:
    experts: set[str] = set()
    configs: set[str] = set()
    sets: set[str] = set()
    for step in steps:
        if not isinstance(step, dict):
            continue
        expert = str(step.get("expert") or "")
        if expert:
            experts.add(Path(expert).stem)
        config = str(step.get("config") or "")
        if config:
            configs.add(Path(config).name)
        expert_parameters = str(step.get("expert_parameters") or "")
        if expert_parameters:
            sets.add(Path(expert_parameters).name)
    return {
        "experts": sorted(experts),
        "tester_configs": sorted(configs),
        "tester_sets": sorted(sets),
    }


def compile_status_summary_from_file(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {"exists": False, "path": str(path), "summary": {}, "error": "missing_compile_status"}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"exists": True, "path": str(path), "summary": {}, "error": "invalid_compile_status_json"}
    summary = payload.get("summary") if isinstance(payload, dict) and isinstance(payload.get("summary"), dict) else {}
    if not summary:
        return {"exists": True, "path": str(path), "summary": {}, "error": "missing_compile_status_summary"}
    return {"exists": True, "path": str(path), "summary": summary, "error": ""}


def manual_prerequisite_row(
    rows_by_name: dict[str, dict[str, Any]],
    name: str,
    *,
    kind: str,
    ready_keys: tuple[str, ...],
) -> dict[str, Any]:
    row = rows_by_name.get(name)
    if not row:
        return {"kind": kind, "name": name, "status": "missing_from_compile_status", "ready": False}
    ready = True
    for key in ready_keys:
        if row.get(key) is not True:
            ready = False
            break
    status = str(row.get("status") or ("ready" if ready else "not_ready"))
    if status != "ready":
        ready = False
    return {
        "kind": kind,
        "name": name,
        "status": status,
        "ready": ready,
        **{key: row.get(key) for key in ready_keys},
    }


def manual_strategy_tester_prerequisites(
    steps: list[dict[str, Any]],
    *,
    compile_status_path: str | Path = DEFAULT_COMPILE_STATUS,
) -> dict[str, Any]:
    loaded = compile_status_summary_from_file(compile_status_path)
    required = required_manual_prerequisite_names(steps)
    reasons: list[str] = []
    if loaded.get("error"):
        reasons.append(str(loaded["error"]))
    summary = loaded.get("summary") if isinstance(loaded.get("summary"), dict) else {}

    item_rows = row_by_name(summary.get("items"))
    set_rows = row_by_name(summary.get("tester_sets"))
    config_rows = row_by_name(summary.get("tester_configs"))
    reference_rows = row_by_name(summary.get("tester_config_references"))

    experts = [
        manual_prerequisite_row(
            item_rows,
            name,
            kind="expert",
            ready_keys=("source_synced", "compiled_fresh"),
        )
        for name in required["experts"]
    ]
    tester_sets = [
        manual_prerequisite_row(
            set_rows,
            name,
            kind="tester_set",
            ready_keys=("synced",),
        )
        for name in required["tester_sets"]
    ]
    tester_configs = [
        manual_prerequisite_row(
            config_rows,
            name,
            kind="tester_config",
            ready_keys=("synced",),
        )
        for name in required["tester_configs"]
    ]
    tester_config_references: list[dict[str, Any]] = []
    for config_name in required["tester_configs"]:
        row = reference_rows.get(config_name)
        if not row:
            tester_config_references.append(
                {
                    "kind": "tester_config_reference",
                    "name": config_name,
                    "expert_parameters": "",
                    "status": "missing_from_compile_status",
                    "ready": False,
                    "synced": False,
                }
            )
            continue
        status = str(row.get("status") or "")
        ready = row.get("ready") is True and row.get("synced") is True and status == "ready"
        tester_config_references.append(
            {
                "kind": "tester_config_reference",
                "name": config_name,
                "expert_parameters": row.get("expert_parameters", ""),
                "status": status,
                "ready": ready,
                "synced": row.get("synced"),
                "generated_set_missing": row.get("generated_set_missing"),
            }
        )

    for group in (experts, tester_sets, tester_configs, tester_config_references):
        for row in group:
            if row.get("ready") is not True:
                reasons.append(f"{row.get('kind')}:{row.get('name')}:{row.get('status')}")

    ready = bool(steps) and not reasons
    return {
        "path": loaded.get("path", str(compile_status_path)),
        "exists": loaded.get("exists", False),
        "generated_at": summary.get("generated_at", ""),
        "ready": ready,
        "reasons": reasons,
        "required": required,
        "experts": experts,
        "tester_sets": tester_sets,
        "tester_configs": tester_configs,
        "tester_config_references": tester_config_references,
    }


def step_by_label(steps: list[dict[str, Any]], label: str) -> dict[str, Any]:
    return next(
        (
            step
            for step in steps
            if isinstance(step, dict) and str(step.get("label") or "") == label
        ),
        {},
    )


def add_plan_validation_check(
    checks: list[dict[str, Any]],
    reasons: list[str],
    *,
    name: str,
    passed: bool,
    requirement: str,
    value: Any,
    reason: str,
) -> None:
    checks.append(
        {
            "name": name,
            "passed": passed,
            "requirement": requirement,
            "value": value,
            "reason": "" if passed else reason,
        }
    )
    if not passed:
        reasons.append(reason)


def comparable_step_value(step: dict[str, Any], key: str) -> str:
    if key == "from_date":
        return str(step.get("effective_from_date") or step.get("base_from_date") or "")
    if key == "to_date":
        return str(step.get("effective_to_date") or step.get("base_to_date") or "")
    return str(step.get(key) or "")


def back_forward_plan_validation(steps: list[dict[str, Any]], *, mode: str) -> dict[str, Any]:
    labels = [str(step.get("label") or "") for step in steps if isinstance(step, dict)]
    backtest = step_by_label(steps, "backtest")
    forward = step_by_label(steps, "forward")
    checks: list[dict[str, Any]] = []
    reasons: list[str] = []

    add_plan_validation_check(
        checks,
        reasons,
        name="selected_pair",
        passed=mode == "both" and labels == ["backtest", "forward"],
        requirement="mode=both with backtest then forward steps",
        value={"mode": mode, "labels": labels},
        reason="selected_steps_not_back_forward_pair",
    )
    add_plan_validation_check(
        checks,
        reasons,
        name="backtest_forward_modes",
        passed=str(backtest.get("effective_forward_mode") or backtest.get("forward_mode") or "") == "0"
        and str(forward.get("effective_forward_mode") or forward.get("forward_mode") or "") not in {"", "0"},
        requirement="backtest ForwardMode=0 and forward ForwardMode non-zero",
        value={
            "backtest": str(backtest.get("effective_forward_mode") or backtest.get("forward_mode") or ""),
            "forward": str(forward.get("effective_forward_mode") or forward.get("forward_mode") or ""),
        },
        reason="invalid_forward_mode_pair",
    )
    add_plan_validation_check(
        checks,
        reasons,
        name="optimization_disabled",
        passed=bool(backtest)
        and bool(forward)
        and str(backtest.get("optimization") or "") == "0"
        and str(forward.get("optimization") or "") == "0",
        requirement="Optimization=0 for both comparison runs",
        value={
            "backtest": str(backtest.get("optimization") or ""),
            "forward": str(forward.get("optimization") or ""),
        },
        reason="optimization_enabled_for_comparison_run",
    )
    add_plan_validation_check(
        checks,
        reasons,
        name="real_ticks_model",
        passed=bool(backtest)
        and bool(forward)
        and str(backtest.get("model") or "") in {"3", "4"}
        and str(forward.get("model") or "") in {"3", "4"},
        requirement="Every tick based on real ticks model",
        value={
            "backtest": str(backtest.get("model") or ""),
            "forward": str(forward.get("model") or ""),
        },
        reason="non_real_ticks_model",
    )
    for key in ("expert", "symbol", "period", "model", "execution_mode", "from_date", "to_date"):
        backtest_value = comparable_step_value(backtest, key)
        forward_value = comparable_step_value(forward, key)
        add_plan_validation_check(
            checks,
            reasons,
            name=f"same_{key}",
            passed=bool(backtest_value) and backtest_value == forward_value,
            requirement=f"same {key} for backtest and forward",
            value={"backtest": backtest_value, "forward": forward_value},
            reason=f"mismatched_{key}",
        )
    distinct_fields = (
        ("config", "distinct_configs"),
        ("expert_parameters", "distinct_expert_parameters"),
        ("report_name", "distinct_reports"),
    )
    for key, name in distinct_fields:
        backtest_value = str(backtest.get(key) or "")
        forward_value = str(forward.get(key) or "")
        add_plan_validation_check(
            checks,
            reasons,
            name=name,
            passed=bool(backtest_value) and bool(forward_value) and backtest_value != forward_value,
            requirement=f"distinct {key} so artifacts are not overwritten",
            value={"backtest": backtest_value, "forward": forward_value},
            reason=f"not_distinct_{key}",
        )
    for key in ("run_json", "report_json"):
        backtest_value = step_output_value(backtest, key)
        forward_value = step_output_value(forward, key)
        add_plan_validation_check(
            checks,
            reasons,
            name=f"distinct_{key}",
            passed=bool(backtest_value) and bool(forward_value) and backtest_value != forward_value,
            requirement=f"distinct {key} output paths",
            value={"backtest": backtest_value, "forward": forward_value},
            reason=f"not_distinct_{key}",
        )

    status = "ready_for_back_forward_comparison" if not reasons else "invalid_back_forward_plan"
    return {
        "available": bool(steps),
        "ready": not reasons,
        "ready_for_back_forward_comparison": not reasons,
        "status": status,
        "mode": mode,
        "labels": labels,
        "reasons": reasons,
        "checks": checks,
    }


def ready_status_preflight(
    steps: list[dict[str, Any]],
    *,
    mode: str,
    status_path: str | Path,
    max_age_seconds: int,
    expected_execution_conditions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = Path(status_path)
    reasons: list[str] = []
    mismatches: list[str] = []
    now_epoch = time.time()
    if not source.exists():
        return {
            "ok": False,
            "path": str(status_path),
            "exists": False,
            "age_seconds": None,
            "max_age_seconds": max_age_seconds,
            "reasons": ["missing_ready_status"],
            "mismatches": [],
        }

    age_seconds = max(0.0, now_epoch - source.stat().st_mtime)
    if age_seconds > max_age_seconds:
        reasons.append("ready_status_stale")

    try:
        status = load_json(source)
    except (OSError, json.JSONDecodeError):
        return {
            "ok": False,
            "path": str(status_path),
            "exists": True,
            "age_seconds": round(age_seconds, 1),
            "max_age_seconds": max_age_seconds,
            "reasons": reasons + ["invalid_ready_status_json"],
            "mismatches": [],
        }

    runner = status.get("back_forward_runner") if isinstance(status.get("back_forward_runner"), dict) else {}
    execution = status.get("back_forward_execution") if isinstance(status.get("back_forward_execution"), dict) else {}
    selected_execution_reasons = execution.get("reasons") if isinstance(execution.get("reasons"), list) else []

    if execution.get("ready") is not True:
        reasons.append("back_forward_execution_not_ready")
    if runner.get("exists") is not True:
        reasons.append("back_forward_runner_missing")
    if runner.get("ok") is not True:
        reasons.append("back_forward_runner_not_ok")
    if runner.get("dry_run") is not True:
        reasons.append("back_forward_run_not_dry_run")

    status_mode = str(runner.get("mode") or "")
    if status_mode != mode:
        mismatches.append(f"mode:{status_mode}->{mode}")

    current_labels = [str(step.get("label", "")) for step in steps]
    status_labels = runner.get("step_labels") if isinstance(runner.get("step_labels"), list) else []
    status_labels = [str(label) for label in status_labels]
    if status_labels != current_labels:
        mismatches.append(f"step_labels:{status_labels}->{current_labels}")

    current_configs = plan_config_by_label(steps)
    status_steps = runner.get("steps") if isinstance(runner.get("steps"), list) else []
    status_configs = plan_config_by_label([step for step in status_steps if isinstance(step, dict)])
    for label, config in current_configs.items():
        if status_configs.get(label) != config:
            mismatches.append(f"config:{label}:{status_configs.get(label, '')}->{config}")

    for key in PREFLIGHT_STEP_KEYS:
        current_values = plan_value_by_label(steps, key)
        status_values = plan_value_by_label([step for step in status_steps if isinstance(step, dict)], key)
        for label, value in current_values.items():
            if status_values.get(label) != value:
                mismatches.append(f"{key}:{label}:{status_values.get(label, '')}->{value}")

    current_reports = plan_value_by_label(steps, "report_name")
    status_reports = plan_value_by_label([step for step in status_steps if isinstance(step, dict)], "report_name")
    for label, report_name in current_reports.items():
        if status_reports.get(label) != report_name:
            mismatches.append(f"report_name:{label}:{status_reports.get(label, '')}->{report_name}")

    for output_key in PREFLIGHT_OUTPUT_KEYS:
        current_outputs = plan_output_by_label(steps, output_key)
        status_outputs = plan_output_by_label(
            [step for step in status_steps if isinstance(step, dict)],
            output_key,
        )
        for label, output_path in current_outputs.items():
            if status_outputs.get(label) != output_path:
                mismatches.append(f"output:{label}:{output_key}:{status_outputs.get(label, '')}->{output_path}")

    current_commands = command_signature_by_label(steps)
    status_commands = command_signature_by_label([step for step in status_steps if isinstance(step, dict)])
    for label, current_signature in current_commands.items():
        status_signature = status_commands.get(label, {})
        if status_signature.get("command_present") is not True:
            mismatches.append(f"command:{label}:missing")
            continue
        current_options = current_signature.get("options") if isinstance(current_signature.get("options"), dict) else {}
        status_options = status_signature.get("options") if isinstance(status_signature.get("options"), dict) else {}
        for option in PREFLIGHT_COMMAND_OPTIONS:
            if str(status_options.get(option, "")) != str(current_options.get(option, "")):
                mismatches.append(
                    f"command_option:{label}:{option}:{status_options.get(option, '')}->{current_options.get(option, '')}"
                )
        current_flags = current_signature.get("flags") if isinstance(current_signature.get("flags"), dict) else {}
        status_flags = status_signature.get("flags") if isinstance(status_signature.get("flags"), dict) else {}
        for flag in PREFLIGHT_COMMAND_FLAGS:
            if bool(status_flags.get(flag)) != bool(current_flags.get(flag)):
                mismatches.append(
                    f"command_flag:{label}:{flag}:{status_flags.get(flag, False)}->{current_flags.get(flag, False)}"
                )

    status_execution_conditions = (
        runner.get("execution_conditions") if isinstance(runner.get("execution_conditions"), dict) else {}
    )
    if expected_execution_conditions:
        if not status_execution_conditions:
            mismatches.append("execution_conditions:missing")
        else:
            for key in PREFLIGHT_EXECUTION_CONDITION_KEYS:
                status_value = status_execution_conditions.get(key, "")
                expected_value = expected_execution_conditions.get(key, "")
                if not execution_condition_values_match(status_value, expected_value):
                    mismatches.append(f"execution_condition:{key}:{status_value}->{expected_value}")

    if mismatches:
        reasons.append("ready_status_plan_mismatch")

    ok = not reasons
    return {
        "ok": ok,
        "path": str(status_path),
        "exists": True,
        "age_seconds": round(age_seconds, 1),
        "max_age_seconds": max_age_seconds,
        "reasons": reasons,
        "mismatches": mismatches,
        "generated_at": status.get("generated_at", ""),
        "back_forward_runner_mode": status_mode,
        "back_forward_runner_step_labels": status_labels,
        "checked_outputs": list(PREFLIGHT_OUTPUT_KEYS),
        "checked_step_keys": list(PREFLIGHT_STEP_KEYS),
        "checked_command_options": list(PREFLIGHT_COMMAND_OPTIONS),
        "checked_command_flags": list(PREFLIGHT_COMMAND_FLAGS),
        "checked_execution_conditions": list(PREFLIGHT_EXECUTION_CONDITION_KEYS),
        "status_execution_conditions": status_execution_conditions,
        "expected_execution_conditions": {
            key: expected_execution_conditions.get(key, "")
            for key in PREFLIGHT_EXECUTION_CONDITION_KEYS
        }
        if expected_execution_conditions
        else {},
        "back_forward_execution_ready": execution.get("ready"),
        "back_forward_execution_status": execution.get("status", ""),
        "back_forward_execution_reasons": selected_execution_reasons,
        "back_forward_execution_execute_hint": execution.get("execute_hint", ""),
    }


def mark_steps_skipped(steps: list[dict[str, Any]], *, reason: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for step in steps:
        result = dict(step)
        result["execution"] = {
            "ok": False,
            "skipped": True,
            "skip_reason": reason,
            "returncode": None,
            "elapsed_seconds": 0.0,
        }
        result["post_execution_validation"] = {"required": False, "ok": True, "reasons": []}
        results.append(result)
    return results


def mark_steps_skipped_preserving_preview(steps: list[dict[str, Any]], *, reason: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for step in steps:
        result = dict(step)
        result["execution"] = {
            "ok": False,
            "skipped": True,
            "skip_reason": reason,
            "returncode": None,
            "elapsed_seconds": 0.0,
        }
        result["post_execution_validation"] = {"required": False, "ok": True, "reasons": []}
        results.append(result)
    return results


def step_artifact_summary(step: dict[str, Any]) -> dict[str, Any]:
    outputs = step.get("outputs") if isinstance(step.get("outputs"), dict) else {}
    summary: dict[str, Any] = {}
    if outputs.get("run_json"):
        summary["tester_run"] = tester_run_artifact_summary(str(outputs.get("run_json")))
    if outputs.get("report_json"):
        summary["report"] = optimization_artifact_summary(str(outputs.get("report_json")))
    return summary


def archive_preview_execution(step: dict[str, Any]) -> dict[str, Any]:
    preview = step.get("archive_preview") if isinstance(step.get("archive_preview"), dict) else {}
    command = preview.get("command") if isinstance(preview.get("command"), list) else []
    return run_command([str(item) for item in command])


def attach_archive_preview_result(step: dict[str, Any]) -> dict[str, Any]:
    result = dict(step)
    preview = result.get("archive_preview") if isinstance(result.get("archive_preview"), dict) else {}
    preview_execution = archive_preview_execution(result)
    result["archive_preview_execution"] = preview_execution
    artifacts = execution_artifact_summary(preview)
    result["archive_preview_artifacts"] = artifacts
    validation = archive_preview_artifact_validation(preview, artifacts)
    if preview_execution.get("ok") is not True:
        reasons = list(validation.get("reasons") if isinstance(validation.get("reasons"), list) else [])
        if "archive_preview_command_failed" not in reasons:
            reasons.insert(0, "archive_preview_command_failed")
        validation = {**validation, "ok": False, "reasons": reasons}
    result["archive_preview_validation"] = validation
    return result


def archive_preview_ok(step: dict[str, Any]) -> bool:
    execution = (
        step.get("archive_preview_execution")
        if isinstance(step.get("archive_preview_execution"), dict)
        else {}
    )
    validation = (
        step.get("archive_preview_validation")
        if isinstance(step.get("archive_preview_validation"), dict)
        else {}
    )
    return execution.get("ok") is True and validation.get("ok") is True


def run_archive_previews(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [attach_archive_preview_result(step) for step in steps]


def archive_preview_blocked_steps(steps: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(step, dict)
        and isinstance(step.get("execution"), dict)
        and step["execution"].get("skip_reason") == "archive_preview_not_ok"
        for step in steps
    )


def step_artifact_validation(step: dict[str, Any], artifacts: dict[str, Any], *, execute: bool) -> dict[str, Any]:
    if not execute:
        return {"required": False, "ok": True, "reasons": []}
    execution = step.get("execution") if isinstance(step.get("execution"), dict) else {}
    if execution.get("skipped") is True:
        return {"required": False, "ok": True, "reasons": []}
    outputs = step.get("outputs") if isinstance(step.get("outputs"), dict) else {}
    tester = artifacts.get("tester_run") if isinstance(artifacts.get("tester_run"), dict) else {}
    report = artifacts.get("report") if isinstance(artifacts.get("report"), dict) else {}
    reasons: list[str] = []
    if not outputs.get("run_json"):
        reasons.append("missing_tester_run_json_plan")
    elif not tester:
        reasons.append("missing_tester_run_summary")
    else:
        if tester.get("exists") is not True:
            reasons.append("missing_tester_run_artifact")
        if tester.get("ok") is not True:
            reasons.append("tester_run_not_ok")
        if tester.get("blocked") is True:
            reasons.append("tester_run_blocked")
        if tester.get("terminal_failed") is True:
            reasons.append("tester_terminal_failed")
        if tester.get("source_time_blocked") is True:
            reasons.append("tester_source_time_blocked")
        if tester.get("report_fallback_blocked") is True:
            reasons.append("tester_report_fallback_blocked")
    if not outputs.get("report_json"):
        reasons.append("missing_report_json_plan")
    elif not report:
        reasons.append("missing_report_summary")
    else:
        if report.get("exists") is not True:
            reasons.append("missing_report_artifact")
        if report.get("ok") is False:
            reasons.append("report_not_ok")
    return {
        "required": True,
        "ok": not reasons,
        "reasons": reasons,
        "run_json": outputs.get("run_json", ""),
        "report_json": outputs.get("report_json", ""),
    }


def step_ok(step: dict[str, Any]) -> bool:
    execution = step.get("execution") if isinstance(step.get("execution"), dict) else {}
    validation = (
        step.get("post_execution_validation")
        if isinstance(step.get("post_execution_validation"), dict)
        else {}
    )
    if execution.get("ok") is not True:
        return False
    if validation.get("required") is True and validation.get("ok") is not True:
        return False
    return True


def optional_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def rounded_optional(value: Any, *, digits: int = 4) -> float | int | None:
    numeric = optional_number(value)
    if numeric is None:
        return None
    if digits == 0:
        return int(round(numeric))
    return round(numeric, digits)


def delta(value: Any, baseline: Any) -> float | None:
    numeric = optional_number(value)
    base = optional_number(baseline)
    if numeric is None or base is None:
        return None
    return round(numeric - base, 4)


def report_metrics(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "trades": optional_number(report.get("closed")),
        "pf": optional_number(report.get("pf")),
        "avg_r": optional_number(report.get("avg_price_r")),
        "expectancy_r": optional_number(report.get("expectancy_price_r")),
        "max_drawdown_r": optional_number(report.get("max_drawdown_price_r")),
        "net_profit": optional_number(report.get("net_profit")),
    }


def comparison_row(
    label: str,
    metrics: dict[str, Any],
    baseline: dict[str, Any],
    *,
    min_closed: int = 0,
) -> dict[str, Any]:
    trades = optional_number(metrics.get("trades"))
    meets_min_closed = trades is not None and trades >= min_closed if min_closed > 0 else True
    return {
        "dataset": label,
        "trades": rounded_optional(trades, digits=0),
        "min_closed": min_closed,
        "meets_min_closed": meets_min_closed,
        "pf": rounded_optional(metrics.get("pf")),
        "avg_r": rounded_optional(metrics.get("avg_r")),
        "expectancy_r": rounded_optional(metrics.get("expectancy_r")),
        "max_drawdown_r": rounded_optional(metrics.get("max_drawdown_r")),
        "net_profit": rounded_optional(metrics.get("net_profit"), digits=2),
        "trades_delta_vs_backtest": delta(metrics.get("trades"), baseline.get("trades")),
        "pf_delta_vs_backtest": delta(metrics.get("pf"), baseline.get("pf")),
        "avg_r_delta_vs_backtest": delta(metrics.get("avg_r"), baseline.get("avg_r")),
        "expectancy_r_delta_vs_backtest": delta(metrics.get("expectancy_r"), baseline.get("expectancy_r")),
        "max_drawdown_r_delta_vs_backtest": delta(metrics.get("max_drawdown_r"), baseline.get("max_drawdown_r")),
        "net_profit_delta_vs_backtest": delta(metrics.get("net_profit"), baseline.get("net_profit")),
    }


def row_has_metrics(row: dict[str, Any]) -> bool:
    return any(
        row.get(key) is not None
        for key in ("trades", "pf", "avg_r", "expectancy_r", "max_drawdown_r", "net_profit")
    )


def forward_drift_status(
    backtest_row: dict[str, Any],
    forward_row: dict[str, Any],
    *,
    min_closed: int = 0,
) -> str:
    if min_closed > 0:
        backtest_trades = optional_number(backtest_row.get("trades"))
        forward_trades = optional_number(forward_row.get("trades"))
        backtest_short = backtest_trades is None or backtest_trades < min_closed
        forward_short = forward_trades is None or forward_trades < min_closed
        if backtest_short and forward_short:
            return "back_forward_sample_shortage"
        if backtest_short:
            return "backtest_sample_shortage"
        if forward_short:
            return "forward_sample_shortage"
    pf = optional_number(forward_row.get("pf"))
    avg_r = optional_number(forward_row.get("avg_r"))
    pf_delta = optional_number(forward_row.get("pf_delta_vs_backtest"))
    avg_delta = optional_number(forward_row.get("avg_r_delta_vs_backtest"))
    if pf is None or avg_r is None:
        return "forward_missing_core_metrics"
    if pf < 1.0 or avg_r < 0:
        return "forward_below_break_even"
    if (pf_delta is not None and pf_delta < -0.2) or (avg_delta is not None and avg_delta < -0.05):
        return "forward_degraded_vs_backtest"
    return "forward_consistent_with_backtest"


def back_forward_performance_thresholds(*, min_closed: int = 0) -> dict[str, Any]:
    return {
        "min_closed": min_closed,
        "break_even_pf": 1.0,
        "break_even_avg_r": 0.0,
        "degraded_pf_delta": -0.2,
        "degraded_avg_r_delta": -0.05,
    }


def back_forward_performance_comparison(
    steps: list[dict[str, Any]],
    *,
    min_closed: int = 0,
) -> dict[str, Any]:
    reports: dict[str, dict[str, Any]] = {}
    for step in steps:
        if not isinstance(step, dict):
            continue
        label = str(step.get("label", ""))
        artifacts = (
            step.get("post_execution_artifacts")
            if isinstance(step.get("post_execution_artifacts"), dict)
            else {}
        )
        report = artifacts.get("report") if isinstance(artifacts.get("report"), dict) else {}
        if report.get("exists") is True:
            reports[label] = report
    if "backtest" not in reports or "forward" not in reports:
        return {
            "available": False,
            "status": "missing_backtest_or_forward_report",
            "reason": "Backtest and forward report artifacts are both required after execute.",
            "rows": [],
            "thresholds": back_forward_performance_thresholds(min_closed=min_closed),
        }
    baseline = report_metrics(reports["backtest"])
    forward = report_metrics(reports["forward"])
    rows = [
        comparison_row("backtest", baseline, baseline, min_closed=min_closed),
        comparison_row("forward", forward, baseline, min_closed=min_closed),
    ]
    rows = [row for row in rows if row_has_metrics(row)]
    backtest_row = next((row for row in rows if row.get("dataset") == "backtest"), {})
    forward_row = next((row for row in rows if row.get("dataset") == "forward"), {})
    return {
        "available": bool(rows),
        "status": forward_drift_status(backtest_row, forward_row, min_closed=min_closed)
        if forward_row
        else "missing_forward_metrics",
        "baseline": "backtest",
        "rows": rows,
        "thresholds": back_forward_performance_thresholds(min_closed=min_closed),
    }


def back_forward_evidence_state(
    *,
    execute: Any,
    dry_run: Any,
    ok: Any,
    blocked_before_steps: Any,
    comparison: dict[str, Any] | None,
) -> str:
    if execute is not True or dry_run is True:
        return "plan_only"
    if str(blocked_before_steps or ""):
        return "executed_blocked"
    if ok is not True:
        return "executed_failed"
    comparison = comparison if isinstance(comparison, dict) else {}
    if comparison.get("available") is not True:
        return "executed_missing_comparison"
    status = str(comparison.get("status") or "")
    if status == "forward_consistent_with_backtest":
        return "executed_consistent"
    if status == "forward_degraded_vs_backtest":
        return "executed_degraded"
    if status == "forward_below_break_even":
        return "executed_below_break_even"
    if status in {"back_forward_sample_shortage", "backtest_sample_shortage", "forward_sample_shortage"}:
        return "executed_sample_shortage"
    return "executed_comparison_issue"


def run_plan(steps: list[dict[str, Any]], *, execute: bool, run_archive_preview: bool = True) -> list[dict[str, Any]]:
    if run_archive_preview:
        previewed_steps = run_archive_previews(steps)
        if not all(archive_preview_ok(step) for step in previewed_steps):
            if execute:
                return mark_steps_skipped_preserving_preview(previewed_steps, reason="archive_preview_not_ok")
            steps = previewed_steps
        else:
            steps = previewed_steps
    results: list[dict[str, Any]] = []
    for step in steps:
        result = dict(step)
        if execute:
            result["execution"] = run_command([str(item) for item in step["command"]])
            artifacts = step_artifact_summary(result)
            result["post_execution_artifacts"] = artifacts
            result["post_execution_validation"] = step_artifact_validation(
                result,
                artifacts,
                execute=True,
            )
        else:
            result["execution"] = {"ok": True, "dry_run": True, "returncode": None, "elapsed_seconds": 0.0}
            result["post_execution_validation"] = {"required": False, "ok": True, "reasons": []}
        results.append(result)
    return results


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compact_list_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def format_performance_comparison_rows(comparison: dict[str, Any]) -> list[str]:
    rows = comparison.get("rows") if isinstance(comparison.get("rows"), list) else []
    if not rows:
        return ["| - |  |  |  |  |  |  |  |  |  |  |  |  |"]
    rendered: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rendered.append(
            f"| {row.get('dataset', '')} | {row.get('trades', '')} | {row.get('meets_min_closed', '')} | {row.get('pf', '')} | "
            f"{row.get('avg_r', '')} | {row.get('expectancy_r', '')} | "
            f"{row.get('max_drawdown_r', '')} | {row.get('net_profit', '')} | "
            f"{row.get('trades_delta_vs_backtest', '')} | {row.get('pf_delta_vs_backtest', '')} | "
            f"{row.get('avg_r_delta_vs_backtest', '')} | "
            f"{row.get('max_drawdown_r_delta_vs_backtest', '')} | "
            f"{row.get('net_profit_delta_vs_backtest', '')} |"
        )
    return rendered if rendered else ["| - |  |  |  |  |  |  |  |  |  |  |  |  |"]


def format_markdown(report: dict[str, Any]) -> str:
    execution_window = (
        report.get("execution_window") if isinstance(report.get("execution_window"), dict) else {}
    )
    execution_conditions = (
        report.get("execution_conditions") if isinstance(report.get("execution_conditions"), dict) else {}
    )
    execution_hints = report.get("execution_hints") if isinstance(report.get("execution_hints"), dict) else {}
    bridge_recovery = (
        report.get("bridge_recovery_plan")
        if isinstance(report.get("bridge_recovery_plan"), dict)
        else {}
    )
    comparison = (
        report.get("performance_comparison")
        if isinstance(report.get("performance_comparison"), dict)
        else {}
    )
    evidence_state = str(report.get("evidence_state") or "")
    if not evidence_state:
        evidence_state = back_forward_evidence_state(
            execute=report.get("execute"),
            dry_run=report.get("dry_run"),
            ok=report.get("ok"),
            blocked_before_steps=report.get("blocked_before_steps", ""),
            comparison=comparison,
        )
    lines = [
        "# MT5 Back/Forward Runner",
        "",
        f"- Generated at: {report.get('generated_at', '')}",
        f"- OK: {report.get('ok')}",
        f"- Dry run: {report.get('dry_run')}",
        f"- Collect only: {report.get('collect_only', '')}",
        f"- Launch MT5: {report.get('launch_mt5', '')}",
        f"- Mode: {report.get('mode', '')}",
        f"- Execute: {report.get('execute')}",
        f"- Run archive preview: {report.get('run_archive_preview', '')}",
        f"- Evidence state: {evidence_state}",
    ]
    if execution_window:
        lines.extend(
            [
                f"- Total timeout: {execution_window.get('total_timeout_minutes', '')} min "
                f"({execution_window.get('total_timeout_seconds', '')} sec)",
                f"- Timeout start reference: {execution_window.get('timeout_start_reference_at', '')}",
                f"- Timeout deadline if started now: {execution_window.get('timeout_deadline_if_started_now', '')}",
                f"- Timeout note: {execution_window.get('note', '')}",
            ]
        )
    if execution_conditions:
        flag_parts = [
            f"{name}={execution_conditions.get(name)}"
            for name in (
                "sync_expert_parameters_set",
                "allow_running_terminal",
                "allow_stale_compile",
                "allow_invalid_risk_preset",
            )
        ]
        lines.extend(
            [
                "- Per-step timeout seconds: "
                f"{execution_conditions.get('per_step_timeout_seconds', '')}",
                f"- Since minutes: {execution_conditions.get('since_minutes', '')}",
                f"- Min closed: {execution_conditions.get('min_closed', '')}",
                f"- CSV modified after: {execution_conditions.get('csv_modified_after', '')}",
                f"- Date override: {execution_conditions.get('from_date', '')} -> "
                f"{execution_conditions.get('to_date', '')}",
                f"- Forward mode override: {execution_conditions.get('forward_mode', '')}",
                f"- Execution flags: {', '.join(flag_parts)}",
                f"- Refresh ready status: {execution_conditions.get('refresh_ready_status', '')}",
                f"- Skip ready status check: {execution_conditions.get('skip_ready_status_check', '')}",
                f"- Skip archive preview: {execution_conditions.get('skip_archive_preview', '')}",
                f"- Max ready status age seconds: {execution_conditions.get('max_ready_status_age_seconds', '')}",
            ]
        )
    if bridge_recovery:
        lines.extend(
            [
                "",
                "## Bridge Recovery",
                "",
                f"- Exists: {bridge_recovery.get('exists')}",
                f"- Status: {bridge_recovery.get('status', '')}",
                f"- Ready for MT5 validation: {bridge_recovery.get('ready_for_mt5_validation', '')}",
                f"- Blocking reasons: {compact_list_text(bridge_recovery.get('blocking_reasons'))}",
                f"- Next action: {bridge_recovery.get('next_action', '')}",
                f"- Required for this standalone tester run: {report.get('bridge_recovery_required_for_mt5_validation', '')}",
            ]
        )
        if report.get("mt5_validation_blocked_by_bridge"):
            lines.append("- MT5 execution: blocked until Bridge Recovery is ready.")
        elif bridge_recovery_blocks_mt5_validation(bridge_recovery):
            lines.append("- MT5 execution: not blocked; Swing_Evaluation_Trader does not use the Bridge.")
    tester_pack = (
        report.get("mt5_strategy_tester_pack")
        if isinstance(report.get("mt5_strategy_tester_pack"), dict)
        else {}
    )
    tester_pack_steps = tester_pack.get("steps") if isinstance(tester_pack.get("steps"), list) else []
    if tester_pack:
        lines.extend(
            [
                "",
                "## MT5 Strategy Tester Quick Start",
                "",
                f"- Available: {tester_pack.get('available')}",
                f"- Ready for manual MT5 run: {tester_pack.get('ready_for_manual_mt5_run')}",
                f"- Status: {tester_pack.get('status', '')}",
                f"- Next action: {tester_pack.get('next_action', '')}",
                f"- Back/Forward pair: {tester_pack.get('is_back_forward_pair')}",
                f"- Manual run start after: {tester_pack.get('manual_run_start_after', '')}",
                f"- Collect status: {tester_pack.get('collect_status', '')}",
                f"- Collect command: {tester_pack.get('collect_command_text', '')}",
                "",
                "| order | purpose | expert | symbol | period | model | dates | forward | window | optimization | MT5 mode | run type | inputs | report | expected | report note | fingerprint |",
                "|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        if tester_pack_steps:
            for row in tester_pack_steps:
                if not isinstance(row, dict):
                    continue
                lines.append(
                    f"| {row.get('order', '')} | {markdown_cell(row.get('purpose', ''))} | "
                    f"{markdown_cell(row.get('expert', ''))} | {markdown_cell(row.get('symbol', ''))} | "
                    f"{markdown_cell(row.get('period', ''))} | {markdown_cell(row.get('model', ''))} | "
                    f"{markdown_cell(row.get('dates', ''))} | {markdown_cell(row.get('forward', ''))} | "
                    f"{markdown_cell(row.get('window_summary', ''))} | "
                    f"{markdown_cell(row.get('optimization', ''))} | "
                    f"{markdown_cell(row.get('mt5_screen_mode', ''))} | "
                    f"{markdown_cell(row.get('run_type', ''))} | "
                    f"{markdown_cell(row.get('inputs', ''))} | "
                    f"{markdown_cell(row.get('report', ''))} | "
                    f"{markdown_cell(row.get('expected_report', ''))} | "
                    f"{markdown_cell(row.get('report_note', ''))} | "
                    f"{markdown_cell(row.get('step_fingerprint', ''))} |"
                )
        else:
            lines.append("| - |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |")
    if execution_hints:
        lines.extend(
            [
                "",
                "## Execution Hints",
                "",
                f"- Execute with MT5 launch: {execution_hints.get('execute_command_text', '')}",
                f"- Collect manual MT5 results: {execution_hints.get('collect_only_command_text', '')}",
                f"- Manual collect note: {execution_hints.get('collect_only_note', '')}",
                f"- Preserved options: {compact_list_text(execution_hints.get('options_preserved'))}",
                f"- Preserved flags: {compact_list_text(execution_hints.get('flags_preserved'))}",
            ]
        )
    manual_plan = report.get("manual_strategy_tester") if isinstance(report.get("manual_strategy_tester"), dict) else {}
    manual_steps = manual_plan.get("steps") if isinstance(manual_plan.get("steps"), list) else []
    if manual_plan and not report.get("mt5_validation_blocked_by_bridge"):
        lines.extend(
            [
                "",
                "## Manual Strategy Tester Checklist",
                "",
                f"- Purpose: {manual_plan.get('purpose', '')}",
                f"- Manual run start after: {manual_plan.get('manual_run_start_after', '')}",
                f"- Recommended collect-only: {manual_plan.get('recommended_collect_only_command_text', '')}",
                f"- Collect note: {manual_plan.get('collect_only_note', '')}",
                "",
                "| order | step | expert | symbol | period | model | dates | forward | window | optimization | run type | expected report | inputs | report | fingerprint |",
                "|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for row in manual_steps:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"| {row.get('order', '')} | {row.get('label', '')} | {row.get('expert', '')} | "
                f"{row.get('symbol', '')} | {row.get('period', '')} | {row.get('model_label', '')} | "
                f"{row.get('from_date', '')} -> {row.get('to_date', '')} | "
                f"{row.get('forward_label', '')} | {markdown_cell(row.get('window_summary', ''))} | "
                f"{row.get('optimization_label', '')} | "
                f"{row.get('run_type', '')} | "
                f"{row.get('expected_report_artifact', '')} | {row.get('expert_parameters', '')} | "
                f"{row.get('report_name', '')} | {row.get('step_fingerprint', '')} |"
            )
    collect_readiness = (
        report.get("manual_collect_readiness")
        if isinstance(report.get("manual_collect_readiness"), dict)
        else {}
    )
    if collect_readiness:
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
                f"- Blocking reasons: {compact_list_text(collect_readiness.get('blocking_reasons'))}",
                f"- Next action: {collect_readiness.get('next_action', '')}",
                "",
                "| step | report status | report ready | collect ready | blocking reason | selected report |",
                "|---|---|---:|---:|---|---|",
            ]
        )
        readiness_steps = collect_readiness.get("steps") if isinstance(collect_readiness.get("steps"), list) else []
        if readiness_steps:
            for row in readiness_steps:
                if not isinstance(row, dict):
                    continue
                lines.append(
                    f"| {row.get('label', '')} | {row.get('report_status', '')} | "
                    f"{row.get('report_ready')} | {row.get('collect_ready')} | "
                    f"{row.get('blocking_reason', '')} | "
                    f"{row.get('selected_report', '')} |"
                )
        else:
            lines.append("| - |  |  |  |  |  |")
    manual_prerequisites = (
        report.get("manual_prerequisites")
        if isinstance(report.get("manual_prerequisites"), dict)
        else {}
    )
    if manual_prerequisites:
        lines.extend(
            [
                "",
                "## Manual Strategy Tester Prerequisites",
                "",
                f"- Ready: {manual_prerequisites.get('ready')}",
                f"- Compile status: {manual_prerequisites.get('path', '')}",
                f"- Exists: {manual_prerequisites.get('exists')}",
                f"- Generated at: {manual_prerequisites.get('generated_at', '')}",
                f"- Reasons: {compact_list_text(manual_prerequisites.get('reasons'))}",
                "",
                "| kind | name | status | ready | synced/source | compiled fresh |",
                "|---|---|---|---:|---:|---:|",
            ]
        )
        for group_name in ("experts", "tester_configs", "tester_sets", "tester_config_references"):
            rows = manual_prerequisites.get(group_name)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                synced_or_source = row.get("synced", row.get("source_synced", ""))
                compiled_fresh = row.get("compiled_fresh", "")
                display_name = str(row.get("name", ""))
                if row.get("expert_parameters") and group_name == "tester_config_references":
                    display_name = f"{display_name} -> {row.get('expert_parameters')}"
                lines.append(
                    f"| {row.get('kind', group_name)} | {display_name} | {row.get('status', '')} | "
                    f"{row.get('ready')} | {synced_or_source} | {compiled_fresh} |"
                )
    plan_validation = (
        report.get("back_forward_plan_validation")
        if isinstance(report.get("back_forward_plan_validation"), dict)
        else {}
    )
    if plan_validation:
        lines.extend(
            [
                "",
                "## Back/Forward Plan Validation",
                "",
                f"- Ready: {plan_validation.get('ready')}",
                f"- Status: {plan_validation.get('status', '')}",
                f"- Reasons: {compact_list_text(plan_validation.get('reasons'))}",
                "",
                "| check | passed | requirement | value | reason |",
                "|---|---:|---|---|---|",
            ]
        )
        checks = plan_validation.get("checks") if isinstance(plan_validation.get("checks"), list) else []
        if checks:
            for row in checks:
                if not isinstance(row, dict):
                    continue
                value = row.get("value")
                value_text = (
                    json.dumps(value, ensure_ascii=False, sort_keys=True)
                    if isinstance(value, (dict, list))
                    else str(value)
                )
                lines.append(
                    f"| {row.get('name', '')} | {row.get('passed')} | "
                    f"{row.get('requirement', '')} | {value_text} | {row.get('reason', '')} |"
                )
        else:
            lines.append("| - |  |  |  |  |")
    if report.get("blocked_before_steps"):
        lines.extend(
            [
                f"- Blocked before steps: {report.get('blocked_before_steps', '')}",
                f"- Reason: {report.get('reason', '')}",
            ]
        )
    ready_status = report.get("ready_status") if isinstance(report.get("ready_status"), dict) else {}
    if ready_status:
        lines.extend(
            [
                "",
                "## Ready Status",
                "",
                f"- OK: {ready_status.get('ok')}",
                f"- Path: {ready_status.get('path', '')}",
                f"- Exists: {ready_status.get('exists')}",
                f"- Age seconds: {ready_status.get('age_seconds')}",
                f"- Max age seconds: {ready_status.get('max_age_seconds')}",
                f"- Generated at: {ready_status.get('generated_at', '')}",
                f"- Execution ready: {ready_status.get('back_forward_execution_ready')}",
                f"- Execution status: {ready_status.get('back_forward_execution_status', '')}",
                f"- Execution reasons: {compact_list_text(ready_status.get('back_forward_execution_reasons'))}",
                f"- Preflight reasons: {compact_list_text(ready_status.get('reasons'))}",
                f"- Mismatches: {compact_list_text(ready_status.get('mismatches'))}",
                f"- Checked execution conditions: {compact_list_text(ready_status.get('checked_execution_conditions'))}",
            ]
        )
    ready_status_refresh = (
        report.get("ready_status_refresh") if isinstance(report.get("ready_status_refresh"), dict) else {}
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
    comparison = (
        report.get("performance_comparison")
        if isinstance(report.get("performance_comparison"), dict)
        else {}
    )
    if comparison:
        thresholds = (
            comparison.get("thresholds")
            if isinstance(comparison.get("thresholds"), dict)
            else {}
        )
        lines.extend(
            [
                "",
                "## Backtest Vs Forward Drift",
                "",
                f"- Available: {comparison.get('available')}",
                f"- Status: {comparison.get('status', '')}",
                f"- Reason: {comparison.get('reason', '')}",
                f"- Min closed threshold: {thresholds.get('min_closed', '')}",
                "",
                "| dataset | trades | min ok | pf | avg_r | expectancy_r | max_dd_r | net_profit | trades delta | pf delta | avg_r delta | max_dd delta | net delta |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
                *format_performance_comparison_rows(comparison),
            ]
        )
    lines.extend(["", "## Steps", ""])
    for step in report.get("steps", []):
        if not isinstance(step, dict):
            continue
        execution = step.get("execution") if isinstance(step.get("execution"), dict) else {}
        outputs = step.get("outputs") if isinstance(step.get("outputs"), dict) else {}
        preview = step.get("archive_preview") if isinstance(step.get("archive_preview"), dict) else {}
        preview_outputs = (
            preview.get("planned_outputs") if isinstance(preview.get("planned_outputs"), dict) else {}
        )
        preview_execution = (
            step.get("archive_preview_execution")
            if isinstance(step.get("archive_preview_execution"), dict)
            else {}
        )
        preview_artifacts = (
            step.get("archive_preview_artifacts")
            if isinstance(step.get("archive_preview_artifacts"), dict)
            else {}
        )
        preview_archive = (
            preview_artifacts.get("agent_csv_archive")
            if isinstance(preview_artifacts.get("agent_csv_archive"), dict)
            else {}
        )
        preview_validation = (
            step.get("archive_preview_validation")
            if isinstance(step.get("archive_preview_validation"), dict)
            else {}
        )
        step_command_text = "" if report.get("mt5_validation_blocked_by_bridge") else step.get("command_text", "")
        lines.extend(
            [
                f"### {step.get('label', '')}",
                "",
                f"- Config: {step.get('config', '')}",
                f"- Expert: {step.get('expert', '')}",
                f"- ExpertParameters: {step.get('expert_parameters', '')}",
                f"- ForwardMode: {step.get('forward_mode', '')}",
                *(
                    [
                        f"- Effective ForwardMode: {step.get('effective_forward_mode', '')} "
                        f"(override: {step.get('forward_mode_override', '')})"
                    ]
                    if step.get("forward_mode_override")
                    else []
                ),
                f"- Tester window: {step.get('window_summary', '')}",
                f"- Tester window note: {(step.get('tester_window') if isinstance(step.get('tester_window'), dict) else {}).get('note', '')}",
                f"- Base dates: {step.get('base_from_date', '')} -> {step.get('base_to_date', '')}",
                f"- Report: {step.get('report_name', '')}",
                f"- Archive run ID: {step.get('archive_run_id', '')}",
                f"- Archive preview JSON: {preview_outputs.get('output_json', '')}",
                f"- Archive preview MD: {preview_outputs.get('output_md', '')}",
                f"- Archive preview command: {preview.get('command_text', '')}",
                f"- Run JSON: {outputs.get('run_json', '')}",
                f"- Report JSON: {outputs.get('report_json', '')}",
                f"- Command: {step_command_text}",
                f"- Result: ok={execution.get('ok')} returncode={execution.get('returncode')} elapsed={execution.get('elapsed_seconds')}",
            ]
        )
        if preview_execution:
            lines.append(
                f"- Archive preview result: ok={preview_execution.get('ok')} "
                f"returncode={preview_execution.get('returncode')} "
                f"elapsed={preview_execution.get('elapsed_seconds')}"
            )
        if preview_archive:
            lines.append(
                f"- Archive preview artifact: exists={preview_archive.get('exists')} "
                f"ok={preview_archive.get('ok')} execute={preview_archive.get('execute')} "
                f"count={preview_archive.get('count')} run_id={preview_archive.get('run_id', '')} "
                f"source_time={preview_archive.get('first_server_time', '')}/{preview_archive.get('last_server_time', '')}"
            )
        if preview_validation:
            lines.append(
                f"- Archive preview validation: required={preview_validation.get('required')} "
                f"ok={preview_validation.get('ok')} reasons={compact_list_text(preview_validation.get('reasons'))}"
            )
        artifacts = (
            step.get("post_execution_artifacts")
            if isinstance(step.get("post_execution_artifacts"), dict)
            else {}
        )
        tester = artifacts.get("tester_run") if isinstance(artifacts.get("tester_run"), dict) else {}
        report_artifact = artifacts.get("report") if isinstance(artifacts.get("report"), dict) else {}
        validation = (
            step.get("post_execution_validation")
            if isinstance(step.get("post_execution_validation"), dict)
            else {}
        )
        if tester:
            lines.append(
                f"- Tester run artifact: exists={tester.get('exists')} ok={tester.get('ok')} "
                f"blocked={tester.get('blocked')} source_time_blocked={tester.get('source_time_blocked')} "
                f"report_fallback_blocked={tester.get('report_fallback_blocked')}"
            )
        if report_artifact:
            lines.append(
                f"- Report artifact: exists={report_artifact.get('exists')} ok={report_artifact.get('ok')} "
                f"closed={report_artifact.get('closed')} pf={report_artifact.get('pf')} "
                f"avg_price_r={report_artifact.get('avg_price_r')} "
                f"single_source={report_artifact.get('single_test_source', '')} "
                f"max_losing_streak={report_artifact.get('single_test_max_losing_streak', '')}"
            )
        if validation:
            lines.append(
                f"- Post execution validation: required={validation.get('required')} "
                f"ok={validation.get('ok')} reasons={compact_list_text(validation.get('reasons'))}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_run_report(
    args: argparse.Namespace,
    *,
    run_id_prefix: str,
    steps: list[dict[str, Any]],
    results: list[dict[str, Any]],
    execute: bool,
    ready_status: dict[str, Any] | None = None,
    ready_status_refresh: dict[str, Any] | None = None,
    blocked_before_steps: str = "",
    reason: str = "",
    preflight_plan_for_ready_status_refresh: bool = False,
) -> dict[str, Any]:
    run_archive_preview = (execute or args.run_archive_preview) and not args.skip_archive_preview
    collect_only = bool(args.collect_only)
    generated_at = datetime.now().strftime(TIME_FORMAT)
    execution_hints = runner_execution_hints(
        args,
        run_id_prefix=run_id_prefix,
        csv_modified_after=generated_at,
    )
    manual_plan = build_manual_strategy_tester_plan(
        args,
        run_id_prefix=run_id_prefix,
        steps=steps,
        generated_at=generated_at,
        execution_hints=execution_hints,
    )
    collect_readiness = manual_collect_readiness(
        steps=steps,
        mt5_root=getattr(args, "mt5_root", "") or default_mt5_root(),
        modified_after=str(args.csv_modified_after or manual_plan.get("manual_run_start_after", "") or generated_at),
        since_minutes=float(args.since_minutes),
        min_closed=int(args.min_closed),
    )
    manual_prerequisites = manual_strategy_tester_prerequisites(
        steps,
        compile_status_path=args.compile_status,
    )
    plan_validation = back_forward_plan_validation(
        steps,
        mode=args.mode,
    )
    report = {
        "ok": all(step_ok(step) for step in results if isinstance(step, dict)),
        "generated_at": generated_at,
        "mode": args.mode,
        "execute": execute,
        "collect_only": collect_only,
        "launch_mt5": bool(execute and not collect_only),
        "dry_run": not execute,
        "run_archive_preview": run_archive_preview,
        "run_id_prefix": run_id_prefix,
        "preflight_plan_for_ready_status_refresh": preflight_plan_for_ready_status_refresh,
        "execution_conditions": execution_conditions_summary(args),
        "execution_hints": execution_hints,
        "manual_strategy_tester": manual_plan,
        "manual_collect_readiness": collect_readiness,
        "manual_prerequisites": manual_prerequisites,
        "back_forward_plan_validation": plan_validation,
        "mt5_strategy_tester_pack": build_mt5_strategy_tester_pack(
            manual_plan=manual_plan,
            manual_prerequisites=manual_prerequisites,
            plan_validation=plan_validation,
            collect_readiness=collect_readiness,
        ),
        "execution_window": execution_window_summary(steps),
        "ready_status": ready_status or {},
        "ready_status_refresh": ready_status_refresh or {},
        "blocked_before_steps": blocked_before_steps,
        "reason": reason,
        "steps": results,
    }
    report["performance_comparison"] = back_forward_performance_comparison(
        results,
        min_closed=int(args.min_closed),
    )
    report["evidence_state"] = back_forward_evidence_state(
        execute=report.get("execute"),
        dry_run=report.get("dry_run"),
        ok=report.get("ok"),
        blocked_before_steps=report.get("blocked_before_steps"),
        comparison=report.get("performance_comparison"),
    )
    return report


def apply_bridge_recovery_guard(report: dict[str, Any], bridge_recovery: dict[str, Any]) -> dict[str, Any]:
    report["bridge_recovery_plan"] = bridge_recovery
    execution_conditions = (
        report.get("execution_conditions")
        if isinstance(report.get("execution_conditions"), dict)
        else {}
    )
    require_bridge_ready = execution_conditions.get("require_bridge_ready") is True
    blocked = require_bridge_ready and bridge_recovery_blocks_mt5_validation(bridge_recovery)
    collect_readiness = (
        report.get("manual_collect_readiness")
        if isinstance(report.get("manual_collect_readiness"), dict)
        else {}
    )
    collect_ready = collect_readiness.get("ready") is True
    launch_candidate = report.get("collect_only") is not True
    report["bridge_recovery_required_for_mt5_validation"] = require_bridge_ready
    report["mt5_validation_blocked_by_bridge"] = bool(blocked and launch_candidate)
    if not report["mt5_validation_blocked_by_bridge"]:
        return report

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
    tester_pack = (
        report.get("mt5_strategy_tester_pack")
        if isinstance(report.get("mt5_strategy_tester_pack"), dict)
        else {}
    )
    if tester_pack:
        tester_pack["available"] = False
        tester_pack["ready_for_manual_mt5_run"] = False
        tester_pack["status"] = "blocked_by_bridge_recovery"
        tester_pack["next_action"] = str(bridge_recovery.get("next_action") or "restore_bridge_recovery")
        tester_pack["blocked_reason"] = report["bridge_recovery_block_reason"]
        report["mt5_strategy_tester_pack"] = tester_pack
    return report


def write_report(output_json: str | Path, output_md: str | Path, report: dict[str, Any]) -> None:
    write_json(output_json, report)
    Path(output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(output_md).write_text(format_markdown(report), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or dry-run MT5 Strategy Tester backtest/forward test presets.",
    )
    parser.add_argument("--mode", choices=("backtest", "forward", "both"), default="both")
    parser.add_argument("--execute", action="store_true", help="Launch MT5. Without this, only write a dry-run plan.")
    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="Collect existing MT5 Tester XML/CSV outputs after a manual Strategy Tester run without launching MT5.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    parser.add_argument("--since-minutes", type=float, default=240.0)
    parser.add_argument("--min-closed", type=int, default=30)
    parser.add_argument(
        "--csv-modified-after",
        default="",
        help="Only include EA CSV files modified at or after this local time (YYYY.MM.DD HH:MM) or epoch seconds.",
    )
    parser.add_argument("--run-id-prefix", default="")
    parser.add_argument(
        "--mt5-root",
        default="",
        help="MT5 installation root. Empty uses the default Wine MT5 root from mt5_compile_status.",
    )
    parser.add_argument("--from-date", default="", help="Override Tester FromDate, e.g. 2026.06.30.")
    parser.add_argument("--to-date", default="", help="Override Tester ToDate, e.g. 2026.07.08.")
    parser.add_argument("--forward-mode", default="", help="Override Tester ForwardMode.")
    parser.add_argument("--sync-expert-parameters-set", action="store_true")
    parser.add_argument("--allow-running-terminal", action="store_true")
    parser.add_argument("--allow-stale-compile", action="store_true")
    parser.add_argument("--allow-invalid-risk-preset", action="store_true")
    parser.add_argument("--ready-status", default=DEFAULT_READY_STATUS)
    parser.add_argument("--ready-status-md", default=DEFAULT_READY_STATUS_MD)
    parser.add_argument(
        "--compile-status",
        default=DEFAULT_COMPILE_STATUS,
        help="Compile status JSON used to show manual Strategy Tester prerequisites.",
    )
    parser.add_argument("--bridge-recovery-plan", default="")
    parser.add_argument(
        "--require-bridge-ready",
        action="store_true",
        help=(
            "Require Bridge Recovery to be ready before launching MT5. "
            "By default Swing_Evaluation_Trader Strategy Tester runs are allowed because the EA is standalone."
        ),
    )
    parser.add_argument(
        "--refresh-ready-status",
        action="store_true",
        help="Refresh the ready-status artifact before execute preflight.",
    )
    parser.add_argument("--max-ready-status-age-seconds", type=int, default=DEFAULT_READY_STATUS_MAX_AGE_SECONDS)
    parser.add_argument("--skip-ready-status-check", action="store_true")
    parser.add_argument(
        "--skip-archive-preview",
        action="store_true",
        help="Skip MT5 Agent CSV archive preview before launching tester steps.",
    )
    parser.add_argument(
        "--run-archive-preview",
        action="store_true",
        help="Run MT5 Agent CSV archive preview even in dry-run mode for manual Strategy Tester checks.",
    )
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.execute and args.collect_only:
        print("error: --execute and --collect-only are mutually exclusive", file=sys.stderr)
        return 2
    run_id_prefix = args.run_id_prefix or f"run_{datetime.now().strftime('%Y%m%d_%H%M')}_mt5_strategy"
    bridge_recovery_plan_path = effective_bridge_recovery_plan_path(args.bridge_recovery_plan, args.output_json)
    args.bridge_recovery_plan = bridge_recovery_plan_path
    bridge_recovery = bridge_recovery_plan_summary(bridge_recovery_plan_path)
    bridge_blocks_mt5 = args.require_bridge_ready and bridge_recovery_blocks_mt5_validation(bridge_recovery)
    run_steps = bool(args.execute or args.collect_only)
    steps = build_plan(
        mode=args.mode,
        execute=run_steps,
        collect_only=args.collect_only,
        timeout_seconds=args.timeout_seconds,
        since_minutes=args.since_minutes,
        min_closed=args.min_closed,
        run_id_prefix=run_id_prefix,
        from_date=args.from_date,
        to_date=args.to_date,
        forward_mode=args.forward_mode,
        sync_expert_parameters_set=args.sync_expert_parameters_set,
        allow_running_terminal=args.allow_running_terminal,
        allow_stale_compile=args.allow_stale_compile,
        allow_invalid_risk_preset=args.allow_invalid_risk_preset,
        csv_modified_after=args.csv_modified_after,
        mt5_root=args.mt5_root,
    )
    ready_status: dict[str, Any] = {}
    ready_status_refresh: dict[str, Any] = {}
    blocked_before_steps = ""
    reason = ""
    plan_validation = back_forward_plan_validation(steps, mode=args.mode)
    if run_steps and args.mode == "both" and plan_validation.get("ready") is not True:
        blocked_before_steps = "back_forward_plan_validation_not_ready"
        validation_reasons = plan_validation.get("reasons")
        reason_text = (
            "; ".join(str(item) for item in validation_reasons)
            if isinstance(validation_reasons, list) and validation_reasons
            else str(plan_validation.get("status") or "invalid_back_forward_plan")
        )
        reason = f"Back/Forward plan validation failed: {reason_text}"
        results = mark_steps_skipped(steps, reason=blocked_before_steps)
    elif args.execute and not args.collect_only and bridge_blocks_mt5:
        blocked_before_steps = "bridge_recovery_not_ready"
        reason = bridge_recovery_block_reason(bridge_recovery)
        results = mark_steps_skipped(steps, reason=blocked_before_steps)
    elif args.execute and args.refresh_ready_status and not args.skip_ready_status_check:
        preflight_steps = build_plan(
            mode=args.mode,
            execute=False,
            collect_only=False,
            timeout_seconds=args.timeout_seconds,
            since_minutes=args.since_minutes,
            min_closed=args.min_closed,
            run_id_prefix=run_id_prefix,
            from_date=args.from_date,
            to_date=args.to_date,
            forward_mode=args.forward_mode,
            sync_expert_parameters_set=args.sync_expert_parameters_set,
            allow_running_terminal=args.allow_running_terminal,
            allow_stale_compile=args.allow_stale_compile,
            allow_invalid_risk_preset=args.allow_invalid_risk_preset,
            csv_modified_after=args.csv_modified_after,
            mt5_root=args.mt5_root,
        )
        preflight_results = run_plan(preflight_steps, execute=False, run_archive_preview=False)
        preflight_report = build_run_report(
            args,
            run_id_prefix=run_id_prefix,
            steps=preflight_steps,
            results=preflight_results,
            execute=False,
            preflight_plan_for_ready_status_refresh=True,
        )
        write_report(args.output_json, args.output_md, preflight_report)
        ready_status_refresh = refresh_ready_status(
            args.ready_status,
            args.ready_status_md,
            back_forward_run_path=args.output_json,
        )
        if ready_status_refresh.get("ok") is not True:
            blocked_before_steps = "ready_status_refresh_failed"
            reason = "latest MT5 tester status could not be refreshed before execute preflight"
            results = mark_steps_skipped(steps, reason=blocked_before_steps)
    if not blocked_before_steps and args.execute and not args.skip_ready_status_check:
        expected_conditions = execution_conditions_summary(args)
        ready_status = ready_status_preflight(
            steps,
            mode=args.mode,
            status_path=args.ready_status,
            max_age_seconds=args.max_ready_status_age_seconds,
            expected_execution_conditions=expected_conditions,
        )
        if ready_status.get("ok") is not True:
            blocked_before_steps = "ready_status_not_ready"
            reason = "back_forward_execution is not ready for this selected back/forward plan"
            results = mark_steps_skipped(steps, reason=blocked_before_steps)
        else:
            results = run_plan(
                steps,
                execute=run_steps,
                run_archive_preview=(run_steps or args.run_archive_preview) and not args.skip_archive_preview,
            )
    elif not blocked_before_steps:
        results = run_plan(
            steps,
            execute=run_steps,
            run_archive_preview=(run_steps or args.run_archive_preview) and not args.skip_archive_preview,
        )
    if not blocked_before_steps and args.execute and archive_preview_blocked_steps(results):
        blocked_before_steps = "archive_preview_not_ok"
        reason = "MT5 Agent CSV archive preview failed before launching tester steps"
    report = build_run_report(
        args,
        run_id_prefix=run_id_prefix,
        steps=steps,
        results=results,
        execute=run_steps,
        ready_status=ready_status,
        ready_status_refresh=ready_status_refresh,
        blocked_before_steps=blocked_before_steps,
        reason=reason,
    )
    apply_bridge_recovery_guard(report, bridge_recovery)
    write_report(args.output_json, args.output_md, report)
    blocked_suffix = f" blocked={blocked_before_steps}" if blocked_before_steps else ""
    ok = report.get("ok") is True
    print(
        f"ok={ok} dry_run={not run_steps} collect_only={args.collect_only} "
        f"mode={args.mode}{blocked_suffix} output={args.output_json}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
