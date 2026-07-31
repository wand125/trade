from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT


DEFAULT_BRIDGE_STATUS = "runtime/latest_bridge_status.json"
DEFAULT_HISTORY_STATUS = "runtime/latest_history_status.json"
DEFAULT_OUTPUT_JSON = "runtime/latest_bridge_recovery_plan.json"
DEFAULT_OUTPUT_MD = "runtime/latest_bridge_recovery_plan.md"
BRIDGE_REQUIRED_FOR_STANDALONE_TESTER = False
STANDALONE_STRATEGY_TESTER_ALLOWED = True
STANDALONE_STRATEGY_TESTER_NOTE = (
    "Bridge Recovery is not required for standalone Swing_Evaluation_Trader Strategy Tester; "
    "Bridge issues only affect Bridge/GPT data refresh paths."
)
BRIDGE_STATUS_COMMAND = (
    "python3 methods/swing_eval/analysis/bridge_status.py --output-json runtime/latest_bridge_status.json "
    "--output-md runtime/latest_bridge_status.md"
)
HISTORY_STATUS_COMMAND = (
    "python3 methods/swing_eval/analysis/history_status.py --history runtime/latest_history_168h.json "
    "--done runtime/history_request.done.json --output-json runtime/latest_history_status.json "
    "--output-md runtime/latest_history_status.md"
)
HISTORY_REQUEST_COMMAND = "python3 src/bridge/request_history.py 168"
BRIDGE_RECOVERY_PLAN_COMMAND = (
    "python3 methods/swing_eval/analysis/bridge_recovery_plan.py --bridge-status runtime/latest_bridge_status.json "
    "--history-status runtime/latest_history_status.json "
    "--output-json runtime/latest_bridge_recovery_plan.json "
    "--output-md runtime/latest_bridge_recovery_plan.md"
)
BRIDGE_LOG_TAIL_COMMAND = "tail -200 runtime/bridge.log"
BRIDGE_PROCESS_INSPECT_COMMAND = "ps aux | rg '[m]t5_ai_bridge.py'"
DEFAULT_MAX_HISTORY_DATA_AGE_SECONDS = 12 * 60 * 60


def load_json_if_present(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def nested_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def nested_bool(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is True


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": event.get("timestamp", ""),
        "age_seconds": event.get("age_seconds"),
        "method": event.get("method", ""),
        "path": event.get("path", ""),
        "status_code": event.get("status_code"),
    }


def parse_mt5_time_epoch(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y.%m.%d %H:%M:%S", TIME_FORMAT):
        try:
            return datetime.strptime(text, fmt).timestamp()
        except ValueError:
            continue
    return None


def history_data_freshness_checks(
    history_status: dict[str, Any],
    *,
    now_epoch: float,
    max_age_seconds: int,
) -> dict[str, Any]:
    if not history_status:
        return {
            "history_data_fresh": "",
            "history_data_stale": "",
            "history_data_max_age_seconds": max_age_seconds,
            "history_status_m1_last_time": "",
            "history_status_server_time_age_seconds": "",
            "history_status_m1_last_time_age_seconds": "",
        }
    timeframes = history_status.get("timeframes") if isinstance(history_status.get("timeframes"), dict) else {}
    m1 = timeframes.get("M1") if isinstance(timeframes.get("M1"), dict) else {}
    values = {
        "history_status_server_time": str(history_status.get("server_time") or ""),
        "history_status_m1_last_time": str(m1.get("last_time") or ""),
    }
    result: dict[str, Any] = {
        **values,
        "history_data_max_age_seconds": max_age_seconds,
    }
    freshness_values: list[bool] = []
    for key, text in values.items():
        epoch = parse_mt5_time_epoch(text)
        age_key = key + "_age_seconds"
        fresh_key = key + "_fresh"
        if epoch is None:
            result[age_key] = ""
            result[fresh_key] = ""
            continue
        age_seconds = max(0.0, now_epoch - epoch)
        fresh = age_seconds <= max_age_seconds
        result[age_key] = round(age_seconds, 1)
        result[fresh_key] = fresh
        freshness_values.append(fresh)
    if freshness_values:
        result["history_data_fresh"] = all(freshness_values)
        result["history_data_stale"] = not result["history_data_fresh"]
    else:
        result["history_data_fresh"] = ""
        result["history_data_stale"] = ""
    return result


def bridge_checks(
    bridge_status: dict[str, Any],
    history_status: dict[str, Any],
    *,
    now_epoch: float,
    max_history_data_age_seconds: int = DEFAULT_MAX_HISTORY_DATA_AGE_SECONDS,
) -> dict[str, Any]:
    health = nested_dict(bridge_status, "health")
    config = nested_dict(bridge_status, "config")
    process = nested_dict(bridge_status, "process")
    terminal = nested_dict(bridge_status, "mt5_terminal")
    snapshot = nested_dict(bridge_status, "latest_snapshot")
    history_request = nested_dict(bridge_status, "history_request")
    bridge_log = nested_dict(bridge_status, "bridge_log")
    activity = nested_dict(bridge_log, "activity")
    request = nested_dict(history_request, "request")
    done = nested_dict(history_request, "done")
    return {
        "bridge_status_loaded": bool(bridge_status),
        "bridge_ok": bridge_status.get("ok") is True,
        "operational_status": bridge_status.get("operational_status", ""),
        "health_ok": health.get("ok") is True,
        "config_ok": config.get("ok") is True,
        "bridge_process_running": process.get("running") is True,
        "mt5_terminal_running": terminal.get("running") is True,
        "mt5_terminal_match_count": terminal.get("match_count", 0),
        "snapshot_fresh": snapshot.get("fresh") is True,
        "snapshot_age_seconds": snapshot.get("age_seconds"),
        "snapshot_server_time": snapshot.get("server_time", ""),
        "history_request_pending": history_request.get("pending") is True,
        "history_request_stale_pending": history_request.get("stale_pending") is True,
        "history_request_pending_age_seconds": history_request.get("pending_age_seconds"),
        "history_request_id": request.get("id", ""),
        "history_done_id": done.get("id", ""),
        "history_done_matches_request": history_request.get("done_matches_request") is True,
        "history_status_loaded": bool(history_status),
        "history_status_ok": history_status.get("ok") is True,
        "history_status_server_time": history_status.get("server_time", ""),
        **history_data_freshness_checks(
            history_status,
            now_epoch=now_epoch,
            max_age_seconds=max_history_data_age_seconds,
        ),
        "bridge_log_activity_status": activity.get("status", ""),
        "ea_liveness_signal": activity.get("ea_liveness_signal", ""),
        "config_get_recent": activity.get("config_get_recent", ""),
        "ea_post_recent": activity.get("ea_post_recent", ""),
        "config_get_recent_but_ea_post_stale": activity.get(
            "config_get_recent_but_ea_post_stale",
            "",
        ),
        "last_ea_post": compact_event(nested_dict(activity, "last_ea_post")),
        "last_snapshot_post": compact_event(nested_dict(activity, "last_snapshot_post")),
        "last_config_get": compact_event(nested_dict(activity, "last_config_get")),
        "config_get_note": activity.get(
            "config_get_note",
            "GET /config can be produced by status checks; use EA POST freshness for EA liveness.",
        ),
    }


def recovery_status(checks: dict[str, Any]) -> str:
    if not checks.get("bridge_status_loaded"):
        return "needs_bridge_status"
    if not checks.get("health_ok") or not checks.get("config_ok"):
        return "needs_bridge_http"
    if not checks.get("bridge_process_running"):
        return "needs_bridge_process"
    operational_status = str(checks.get("operational_status") or "")
    if operational_status == "ea_not_posting" or not checks.get("snapshot_fresh"):
        return "needs_ea_restart"
    if checks.get("history_request_stale_pending"):
        return "needs_ea_restart"
    if checks.get("history_request_pending") and not checks.get("history_done_matches_request"):
        return "needs_history_wait"
    if not checks.get("history_status_ok"):
        return "needs_history_status_refresh"
    if checks.get("history_data_stale") is True:
        return "needs_history_refresh"
    if operational_status == "ready":
        return "ready"
    return "unknown"


def recovery_blocking_reasons(status: str, checks: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not checks.get("bridge_status_loaded"):
        reasons.append("bridge_status_missing")
    if checks.get("health_ok") is not True:
        reasons.append("bridge_health_not_ok")
    if checks.get("config_ok") is not True:
        reasons.append("bridge_config_not_ok")
    if checks.get("bridge_process_running") is not True:
        reasons.append("bridge_process_not_running")
    operational_status = str(checks.get("operational_status") or "")
    if operational_status and operational_status != "ready":
        reasons.append(f"operational_status:{operational_status}")
    if status == "needs_ea_restart" and checks.get("mt5_terminal_running") is not True:
        reasons.append("mt5_terminal_not_running")
    if checks.get("snapshot_fresh") is not True:
        reasons.append("snapshot_not_fresh")
    activity_status = str(checks.get("bridge_log_activity_status") or "")
    if activity_status and activity_status != "ea_snapshot_post_recent":
        reasons.append(f"bridge_log_activity:{activity_status}")
    if checks.get("history_request_stale_pending"):
        reasons.append("history_request_stale_pending")
    elif checks.get("history_request_pending") and not checks.get("history_done_matches_request"):
        reasons.append("history_request_pending_without_matching_done")
    if status == "needs_history_status_refresh" or checks.get("history_status_ok") is not True:
        reasons.append("history_status_not_ok")
    if checks.get("history_data_stale") is True:
        reasons.append("history_data_stale")
    return list(dict.fromkeys(reasons))


def recovery_next_action(status: str, checks: dict[str, Any]) -> str:
    if status == "needs_bridge_status":
        return "refresh_bridge_status"
    if status == "needs_bridge_http":
        return "restart_bridge_http_and_verify_health_config"
    if status == "needs_bridge_process":
        return "start_mt5_ai_bridge_process"
    if status == "needs_ea_restart":
        if checks.get("mt5_terminal_running"):
            return "restart_ai_bridge_advisor_and_wait_for_snapshot_post"
        return "open_mt5_attach_ai_bridge_advisor_and_wait_for_snapshot_post"
    if status == "needs_history_wait":
        return "wait_for_matching_history_request_done"
    if status == "needs_history_status_refresh":
        return "refresh_history_status"
    if status == "needs_history_refresh":
        return "request_fresh_168h_history_and_wait_for_matching_done"
    if status == "ready":
        return "proceed_to_mt5_back_forward_validation"
    return "inspect_bridge_status_and_bridge_log"


def command_step(label: str, command: str) -> dict[str, str]:
    return {"label": label, "command": command}


def manual_step(label: str, detail: str) -> dict[str, str]:
    return {"label": label, "detail": detail}


def verification_commands_for_status(status: str) -> list[dict[str, str]]:
    commands = [
        command_step("inspect_bridge_log", BRIDGE_LOG_TAIL_COMMAND),
        command_step("refresh_bridge_status", BRIDGE_STATUS_COMMAND),
        command_step("refresh_bridge_recovery_plan", BRIDGE_RECOVERY_PLAN_COMMAND),
    ]
    if status in {
        "needs_ea_restart",
        "needs_history_wait",
        "ready",
        "needs_history_status_refresh",
        "needs_history_refresh",
    }:
        commands.append(command_step("refresh_history_status", HISTORY_STATUS_COMMAND))
    if status in {"needs_bridge_http", "needs_bridge_process", "unknown"}:
        commands.insert(1, command_step("inspect_bridge_process", BRIDGE_PROCESS_INSPECT_COMMAND))
    return commands


def build_recovery_actions(status: str, checks: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    commands = [
        command_step("refresh_bridge_status", BRIDGE_STATUS_COMMAND),
        command_step("refresh_history_status", HISTORY_STATUS_COMMAND),
        command_step("refresh_bridge_recovery_plan", BRIDGE_RECOVERY_PLAN_COMMAND),
    ]
    steps: list[dict[str, str]] = []
    if status == "needs_bridge_status":
        steps.append(manual_step("status", "Run bridge_status.py first so this plan can read current Bridge evidence."))
    elif status == "needs_bridge_http":
        steps.append(manual_step("bridge", "Start or restart python3 src/bridge/mt5_ai_bridge.py, then verify /health and /config."))
    elif status == "needs_bridge_process":
        steps.append(manual_step("bridge", "Start python3 src/bridge/mt5_ai_bridge.py before waiting for MT5 EA history responses."))
    elif status == "needs_ea_restart":
        if checks.get("mt5_terminal_running"):
            steps.append(
                manual_step(
                    "mt5_ea",
                    "MT5 is running; attach or restart AI_Bridge_Advisor on a live XAUUSD-m chart.",
                )
            )
        else:
            steps.append(manual_step("mt5_terminal", "Open MT5 and attach AI_Bridge_Advisor to a live XAUUSD-m chart."))
        steps.extend(
            [
                manual_step("auto_trading", "Confirm Algo Trading is enabled and the EA smile/status is active."),
                manual_step("webrequest", "Confirm MT5 WebRequest permits http://127.0.0.1:8765 and EA inputs point at the same URL/token."),
                manual_step("wait", "Wait until bridge.log shows a fresh POST /snapshot; GET /config alone is not enough."),
            ]
        )
        if checks.get("history_request_stale_pending"):
            steps.append(
                manual_step(
                    "history_pending",
                    "Do not repeat the same history request yet; after EA POST returns, wait for matching history_request.done.json.",
                )
            )
        if checks.get("history_data_stale") is True:
            steps.append(
                manual_step(
                    "history_data",
                    "Existing 168h history has complete bars but stale server_time/M1 last bar; refresh history after EA POST returns.",
                )
            )
    elif status == "needs_history_wait":
        steps.append(manual_step("history_wait", "EA appears reachable; wait for history_request.done.json to match the pending request id."))
    elif status == "needs_history_status_refresh":
        steps.append(manual_step("history_status", "Refresh history_status.py and confirm M1/M5/M15/M30 coverage before MT5 validation."))
    elif status == "needs_history_refresh":
        steps.append(
            manual_step(
                "history_refresh",
                "Request fresh 168h MT5 history, wait for matching history_request.done.json, then refresh history_status.py.",
            )
        )
    elif status == "ready":
        steps.append(manual_step("ready", "Bridge/EA/history status is ready; MT5 Strategy Tester evidence can be refreshed or collected."))
    else:
        steps.append(manual_step("inspect", "Inspect latest_bridge_status.json and bridge.log; status is not one of the known recovery cases."))

    if status == "needs_history_refresh":
        commands.append(command_step("request_history", HISTORY_REQUEST_COMMAND))
    if status in {"ready", "needs_history_status_refresh", "needs_history_refresh"}:
        commands.append(
            command_step(
                "mt5_back_forward_plan",
                "python3 methods/swing_eval/analysis/mt5_back_forward_run.py --mode both --run-archive-preview "
                "--output-json runtime/latest_mt5_back_forward_run.json --output-md runtime/latest_mt5_back_forward_run.md",
            )
        )
    return steps, commands


def build_operation_cards(status: str, checks: dict[str, Any], next_action: str) -> list[dict[str, Any]]:
    base = {
        "order": 1,
        "is_next": True,
        "action": next_action,
        "status": status,
        "mt5_terminal_running": checks.get("mt5_terminal_running"),
        "mt5_terminal_match_count": checks.get("mt5_terminal_match_count", 0),
        "history_request_id": checks.get("history_request_id", ""),
        "history_done_id": checks.get("history_done_id", ""),
        "history_done_matches_request": checks.get("history_done_matches_request"),
        "history_data_fresh": checks.get("history_data_fresh"),
        "history_data_stale": checks.get("history_data_stale"),
        "history_data_max_age_seconds": checks.get("history_data_max_age_seconds"),
        "history_status_server_time": checks.get("history_status_server_time", ""),
        "history_status_server_time_age_seconds": checks.get("history_status_server_time_age_seconds", ""),
        "history_status_m1_last_time": checks.get("history_status_m1_last_time", ""),
        "history_status_m1_last_time_age_seconds": checks.get("history_status_m1_last_time_age_seconds", ""),
        "verification_commands": verification_commands_for_status(status),
    }
    if status == "needs_bridge_status":
        return [
            {
                **base,
                "area": "bridge_status",
                "purpose": "Refresh Bridge status evidence",
                "target": "runtime/latest_bridge_status.json",
                "operator_step": "Run bridge_status.py so recovery status can be classified.",
                "verification": "latest_bridge_status.json exists and recovery plan can read it.",
            }
        ]
    if status == "needs_bridge_http":
        return [
            {
                **base,
                "area": "bridge_http",
                "purpose": "Restore Bridge HTTP health/config",
                "target": "src/bridge/mt5_ai_bridge.py",
                "operator_step": "Restart the Bridge HTTP process until /health and /config are OK.",
                "verification": "Bridge /health and /config return OK.",
            }
        ]
    if status == "needs_bridge_process":
        return [
            {
                **base,
                "area": "bridge_process",
                "purpose": "Start MT5 AI Bridge process",
                "target": "src/bridge/mt5_ai_bridge.py",
                "operator_step": "Start python3 src/bridge/mt5_ai_bridge.py.",
                "verification": "Bridge process is running and /health responds.",
            }
        ]
    if status == "needs_ea_restart":
        return [
            {
                **base,
                "area": "mt5_ea",
                "purpose": "Restore MT5 EA snapshot/history posting",
                "target": "AI_Bridge_Advisor",
                "chart": "live XAUUSD-m chart",
                "operator_step": (
                    "Attach or restart AI_Bridge_Advisor on a live XAUUSD-m chart; "
                    "enable Algo Trading and confirm WebRequest/Bridge URL settings."
                ),
                "verification": "bridge.log shows a fresh POST /snapshot; GET /config alone is not enough.",
                "last_ea_post": nested_dict(checks, "last_ea_post"),
                "last_snapshot_post": nested_dict(checks, "last_snapshot_post"),
                "history_request_pending": checks.get("history_request_pending"),
                "history_request_stale_pending": checks.get("history_request_stale_pending"),
            }
        ]
    if status == "needs_history_wait":
        return [
            {
                **base,
                "area": "history",
                "purpose": "Wait for matching history request completion",
                "target": "runtime/history_request.done.json",
                "operator_step": "Wait until history_request.done.json matches the pending request id.",
                "verification": "history_done_matches_request=true.",
            }
        ]
    if status == "needs_history_status_refresh":
        return [
            {
                **base,
                "area": "history_status",
                "purpose": "Refresh history status",
                "target": "runtime/latest_history_status.json",
                "operator_step": "Run history_status.py and confirm M1/M5/M15/M30 coverage.",
                "verification": "latest_history_status.json ok=true.",
            }
        ]
    if status == "needs_history_refresh":
        return [
            {
                **base,
                "area": "history",
                "purpose": "Refresh stale 168h MT5 history data",
                "target": "runtime/latest_history_168h.json",
                "operator_step": "Request fresh 168h MT5 history and wait for matching history_request.done.json.",
                "verification": "history_status server_time/M1 last bar are fresh.",
            }
        ]
    if status == "ready":
        return [
            {
                **base,
                "area": "mt5_validation",
                "purpose": "Proceed to MT5 Back/Forward validation",
                "target": "Swing_Evaluation_Trader Strategy Tester",
                "operator_step": "Refresh or collect MT5 Back/Forward validation evidence.",
                "verification": "MT5 Back/Forward plan or collected reports are current.",
            }
        ]
    return [
        {
            **base,
            "area": "bridge_inspection",
            "purpose": "Inspect unknown Bridge recovery state",
            "target": "runtime/latest_bridge_status.md and runtime/bridge.log",
            "operator_step": "Inspect Bridge status and bridge.log manually.",
            "verification": "Recovery status is classified into a known state.",
        }
    ]


def bridge_operator_summary(
    *,
    ok: bool,
    status: str,
    ready_for_mt5_validation: bool,
    blocking_reasons: list[str],
    next_action: str,
    checks: dict[str, Any],
    operation_cards: list[dict[str, Any]],
) -> dict[str, Any]:
    next_card = next(
        (card for card in operation_cards if isinstance(card, dict) and card.get("is_next") is True),
        {},
    )
    if not isinstance(next_card, dict):
        next_card = {}
    verification_commands = (
        next_card.get("verification_commands")
        if isinstance(next_card.get("verification_commands"), list)
        else []
    )
    return {
        "ok": ok,
        "status": status,
        "ready_for_mt5_validation": ready_for_mt5_validation,
        "bridge_required_for_standalone_tester": BRIDGE_REQUIRED_FOR_STANDALONE_TESTER,
        "standalone_strategy_tester_allowed": STANDALONE_STRATEGY_TESTER_ALLOWED,
        "standalone_strategy_tester_note": STANDALONE_STRATEGY_TESTER_NOTE,
        "blocking_reasons": list(blocking_reasons),
        "next_action": next_action,
        "next_operation_action": next_card.get("action", ""),
        "next_operation_area": next_card.get("area", ""),
        "next_operation_purpose": next_card.get("purpose", ""),
        "next_operation_target": next_card.get("target", ""),
        "next_operation_operator_step": next_card.get("operator_step", ""),
        "next_operation_verification": next_card.get("verification", ""),
        "next_operation_verification_commands": [
            command
            for command in verification_commands
            if isinstance(command, dict)
        ],
        "mt5_terminal_running": checks.get("mt5_terminal_running"),
        "mt5_terminal_match_count": checks.get("mt5_terminal_match_count", 0),
        "bridge_log_activity_status": checks.get("bridge_log_activity_status", ""),
        "ea_liveness_signal": checks.get("ea_liveness_signal", ""),
        "config_get_recent": checks.get("config_get_recent", ""),
        "ea_post_recent": checks.get("ea_post_recent", ""),
        "config_get_recent_but_ea_post_stale": checks.get(
            "config_get_recent_but_ea_post_stale",
            "",
        ),
        "last_ea_post": nested_dict(checks, "last_ea_post"),
        "last_ea_post_age_seconds": nested_dict(checks, "last_ea_post").get("age_seconds"),
        "last_snapshot_post": nested_dict(checks, "last_snapshot_post"),
        "last_snapshot_post_age_seconds": nested_dict(checks, "last_snapshot_post").get("age_seconds"),
        "snapshot_fresh": checks.get("snapshot_fresh"),
        "snapshot_age_seconds": checks.get("snapshot_age_seconds"),
        "history_request_pending": checks.get("history_request_pending"),
        "history_request_stale_pending": checks.get("history_request_stale_pending"),
        "history_request_id": checks.get("history_request_id", ""),
        "history_done_id": checks.get("history_done_id", ""),
        "history_done_matches_request": checks.get("history_done_matches_request"),
        "history_data_fresh": checks.get("history_data_fresh"),
        "history_data_stale": checks.get("history_data_stale"),
        "history_data_max_age_seconds": checks.get("history_data_max_age_seconds"),
        "history_status_server_time": checks.get("history_status_server_time", ""),
        "history_status_server_time_age_seconds": checks.get(
            "history_status_server_time_age_seconds", ""
        ),
        "history_status_m1_last_time": checks.get("history_status_m1_last_time", ""),
        "history_status_m1_last_time_age_seconds": checks.get(
            "history_status_m1_last_time_age_seconds", ""
        ),
    }


def build_bridge_recovery_plan(
    *,
    bridge_status_path: str | Path = DEFAULT_BRIDGE_STATUS,
    history_status_path: str | Path = DEFAULT_HISTORY_STATUS,
    now: datetime | None = None,
    max_history_data_age_seconds: int = DEFAULT_MAX_HISTORY_DATA_AGE_SECONDS,
) -> dict[str, Any]:
    bridge_status = load_json_if_present(bridge_status_path)
    history_status = load_json_if_present(history_status_path)
    effective_now = now or datetime.now()
    checks = bridge_checks(
        bridge_status,
        history_status,
        now_epoch=effective_now.timestamp(),
        max_history_data_age_seconds=max_history_data_age_seconds,
    )
    status = recovery_status(checks)
    blocking_reasons = recovery_blocking_reasons(status, checks)
    next_action = recovery_next_action(status, checks)
    manual_steps, commands = build_recovery_actions(status, checks)
    operation_cards = build_operation_cards(status, checks, next_action)
    ready_for_mt5_validation = status == "ready"
    ok = ready_for_mt5_validation
    operator_summary = bridge_operator_summary(
        ok=ok,
        status=status,
        ready_for_mt5_validation=ready_for_mt5_validation,
        blocking_reasons=blocking_reasons,
        next_action=next_action,
        checks=checks,
        operation_cards=operation_cards,
    )
    return {
        "ok": ok,
        "generated_at": effective_now.strftime(TIME_FORMAT),
        "status": status,
        "ready_for_mt5_validation": ready_for_mt5_validation,
        "bridge_required_for_standalone_tester": BRIDGE_REQUIRED_FOR_STANDALONE_TESTER,
        "standalone_strategy_tester_allowed": STANDALONE_STRATEGY_TESTER_ALLOWED,
        "standalone_strategy_tester_note": STANDALONE_STRATEGY_TESTER_NOTE,
        "blocking_reasons": blocking_reasons,
        "next_action": next_action,
        "operator_summary": operator_summary,
        "source_files": {
            "bridge_status": str(bridge_status_path),
            "history_status": str(history_status_path),
        },
        "checks": checks,
        "manual_steps": manual_steps,
        "commands": commands,
        "operation_cards": operation_cards,
    }


def format_event(event: dict[str, Any]) -> str:
    if not event.get("timestamp"):
        return "not seen"
    return (
        f"{event.get('timestamp')} age={event.get('age_seconds')} "
        f"{event.get('method')} {event.get('path')} status={event.get('status_code')}"
    )


def operator_handoff_lines(plan: dict[str, Any], checks: dict[str, Any]) -> list[str]:
    status = str(plan.get("status") or "")
    next_action = str(plan.get("next_action") or "")
    lines = [
        "## Bridge Operator Handoff",
        "",
        f"- Current action: `{next_action}`",
        (
            "- MT5 terminal: "
            f"running={checks.get('mt5_terminal_running')} "
            f"matches={checks.get('mt5_terminal_match_count')}"
        ),
        (
            "- Standalone tester: allowed; Bridge Recovery is not required for "
            "`Swing_Evaluation_Trader` Backtest/Forward Test."
        ),
    ]
    if status == "needs_ea_restart":
        lines.extend(
            [
                (
                    "- EA POST: "
                    f"activity `{checks.get('bridge_log_activity_status', '')}`, "
                    f"last `{format_event(nested_dict(checks, 'last_ea_post'))}`"
                ),
                (
                    "- In MT5: attach/restart `AI_Bridge_Advisor` on a live "
                    "`XAUUSD-m` chart; enable Algo Trading; confirm WebRequest "
                    "`http://127.0.0.1:8765`."
                ),
                "- Wait for a fresh `POST /snapshot`; `GET /config` alone is not enough.",
            ]
        )
        if checks.get("history_request_pending"):
            lines.append(
                "- History request: "
                f"pending `{checks.get('history_request_id', '')}`, "
                f"done `{checks.get('history_done_id', '')}`, "
                f"match={checks.get('history_done_matches_request')}; "
                "wait for matching `history_request.done.json` after EA POST returns."
            )
        if checks.get("history_data_stale") is True:
            lines.append(
                "- History data: stale "
                f"server_time `{checks.get('history_status_server_time', '')}` "
                f"age={checks.get('history_status_server_time_age_seconds')}s, "
                f"M1 last `{checks.get('history_status_m1_last_time', '')}` "
                f"age={checks.get('history_status_m1_last_time_age_seconds')}s."
            )
    elif status == "needs_bridge_process":
        lines.append("- Start `python3 src/bridge/mt5_ai_bridge.py`, then refresh Bridge status.")
    elif status == "needs_bridge_http":
        lines.append("- Restart the Bridge HTTP process until `/health` and `/config` are both OK.")
    elif status == "needs_history_wait":
        lines.append(
            "- EA appears reachable; wait until `history_request.done.json` matches "
            f"`{checks.get('history_request_id', '')}`."
        )
    elif status == "needs_history_refresh":
        lines.append(
            "- History data is stale; request fresh 168h MT5 history, wait for matching done file, then refresh status."
        )
    elif status == "ready":
        lines.append("- Bridge, EA posting, and history status are ready for MT5 validation.")
    else:
        lines.append("- Inspect `runtime/latest_bridge_status.md` and `runtime/bridge.log`.")
    return lines + [""]


def format_operation_card_lines(plan: dict[str, Any]) -> list[str]:
    cards = plan.get("operation_cards") if isinstance(plan.get("operation_cards"), list) else []
    lines = ["## Bridge Recovery Operation Cards", ""]
    if not cards:
        return lines + ["- None", ""]
    for card in cards:
        if not isinstance(card, dict):
            continue
        next_mark = "next" if card.get("is_next") else ""
        details = [
            f"action={card.get('action', '')}",
            f"purpose={card.get('purpose', '')}",
            f"area={card.get('area', '')}",
            f"target={card.get('target', '')}",
            f"verification={card.get('verification', '')}",
        ]
        if card.get("history_request_id") or card.get("history_done_id"):
            details.append(
                "history="
                f"{card.get('history_request_id', '')}->{card.get('history_done_id', '')} "
                f"match={card.get('history_done_matches_request')}"
            )
        if card.get("history_data_stale") is True:
            details.append(
                "history_data=stale "
                f"server_age={card.get('history_status_server_time_age_seconds')} "
                f"m1_age={card.get('history_status_m1_last_time_age_seconds')}"
            )
        lines.append(
            "- Bridge recovery operation card "
            f"{card.get('order', '')}: {next_mark}, " + ", ".join(details)
        )
        if card.get("operator_step"):
            lines.append(f"  - Operator step: {card.get('operator_step')}")
        commands = card.get("verification_commands") if isinstance(card.get("verification_commands"), list) else []
        for command in commands:
            if isinstance(command, dict):
                lines.append(
                    f"  - Verification command {command.get('label', '')}: `{command.get('command', '')}`"
                )
    return lines + [""]


def format_markdown(plan: dict[str, Any]) -> str:
    checks = nested_dict(plan, "checks")
    blocking_reasons = plan.get("blocking_reasons")
    blocking_reasons_text = (
        ", ".join(str(reason) for reason in blocking_reasons)
        if isinstance(blocking_reasons, list)
        else ""
    )
    lines = [
        "# MT5 Bridge Recovery Plan",
        "",
        f"- Generated at: {plan.get('generated_at', '')}",
        f"- OK: {plan.get('ok')}",
        f"- Status: {plan.get('status', '')}",
        f"- Ready for MT5 validation: {plan.get('ready_for_mt5_validation')}",
        f"- Bridge required for standalone tester: {plan.get('bridge_required_for_standalone_tester')}",
        f"- Standalone Strategy Tester allowed: {plan.get('standalone_strategy_tester_allowed')}",
        f"- Standalone Strategy Tester note: {plan.get('standalone_strategy_tester_note', '')}",
        f"- Blocking reasons: {blocking_reasons_text}",
        f"- Next action: {plan.get('next_action', '')}",
        "",
        *operator_handoff_lines(plan, checks),
        *format_operation_card_lines(plan),
        "## Checks",
        "",
        f"- Bridge status loaded: {checks.get('bridge_status_loaded')}",
        f"- Operational status: {checks.get('operational_status', '')}",
        f"- Health OK: {checks.get('health_ok')}",
        f"- Config OK: {checks.get('config_ok')}",
        f"- Bridge process running: {checks.get('bridge_process_running')}",
        f"- MT5 terminal running: {checks.get('mt5_terminal_running')} ({checks.get('mt5_terminal_match_count')})",
        f"- Snapshot fresh: {checks.get('snapshot_fresh')} age_seconds={checks.get('snapshot_age_seconds')} server_time={checks.get('snapshot_server_time', '')}",
        f"- History pending: {checks.get('history_request_pending')} stale={checks.get('history_request_stale_pending')} age_seconds={checks.get('history_request_pending_age_seconds')}",
        f"- History request/done: request={checks.get('history_request_id', '')} done={checks.get('history_done_id', '')} match={checks.get('history_done_matches_request')}",
        f"- History status OK: {checks.get('history_status_ok')} server_time={checks.get('history_status_server_time', '')}",
        f"- History data fresh: {checks.get('history_data_fresh')} stale={checks.get('history_data_stale')} max_age_seconds={checks.get('history_data_max_age_seconds')} server_time_age_seconds={checks.get('history_status_server_time_age_seconds')} m1_last_time={checks.get('history_status_m1_last_time', '')} m1_last_time_age_seconds={checks.get('history_status_m1_last_time_age_seconds')}",
        f"- Bridge log activity: {checks.get('bridge_log_activity_status', '')}",
        f"- EA liveness signal: {checks.get('ea_liveness_signal', '')}",
        f"- Config GET recent: {checks.get('config_get_recent', '')}",
        f"- EA POST recent: {checks.get('ea_post_recent', '')}",
        f"- Config GET recent but EA POST stale: {checks.get('config_get_recent_but_ea_post_stale', '')}",
        f"- Last EA POST: {format_event(nested_dict(checks, 'last_ea_post'))}",
        f"- Last snapshot POST: {format_event(nested_dict(checks, 'last_snapshot_post'))}",
        f"- Last config GET: {format_event(nested_dict(checks, 'last_config_get'))}",
        f"- Config GET note: {checks.get('config_get_note', '')}",
        "",
        "## Manual Steps",
        "",
    ]
    steps = plan.get("manual_steps") if isinstance(plan.get("manual_steps"), list) else []
    if steps:
        lines.extend(f"- {step.get('label', '')}: {step.get('detail', '')}" for step in steps if isinstance(step, dict))
    else:
        lines.append("- None")
    lines.extend(["", "## Commands", ""])
    commands = plan.get("commands") if isinstance(plan.get("commands"), list) else []
    if commands:
        for command in commands:
            if isinstance(command, dict):
                lines.append(f"- {command.get('label', '')}: `{command.get('command', '')}`")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a concrete recovery plan from MT5 AI Bridge status artifacts.")
    parser.add_argument("--bridge-status", default=DEFAULT_BRIDGE_STATUS)
    parser.add_argument("--history-status", default=DEFAULT_HISTORY_STATUS)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--max-history-data-age-seconds", type=int, default=DEFAULT_MAX_HISTORY_DATA_AGE_SECONDS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan = build_bridge_recovery_plan(
        bridge_status_path=args.bridge_status,
        history_status_path=args.history_status,
        max_history_data_age_seconds=args.max_history_data_age_seconds,
    )
    write_json(args.output_json, plan)
    write_text(args.output_md, format_markdown(plan))
    print(
        json.dumps(
            {
                "ok": plan["ok"],
                "status": plan["status"],
                "ready_for_mt5_validation": plan["ready_for_mt5_validation"],
                "bridge_required_for_standalone_tester": plan.get("bridge_required_for_standalone_tester"),
                "standalone_strategy_tester_allowed": plan.get("standalone_strategy_tester_allowed"),
                "standalone_strategy_tester_note": plan.get("standalone_strategy_tester_note", ""),
                "blocking_reasons": plan["blocking_reasons"],
                "next_action": plan["next_action"],
                "operator_summary": plan.get("operator_summary", {}),
                "output_json": args.output_json,
                "output_md": args.output_md,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if plan["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
