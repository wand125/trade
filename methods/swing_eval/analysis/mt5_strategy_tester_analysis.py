from __future__ import annotations

import argparse
import json
import shlex
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT
from analysis.mt5_agent_csv_utils import summarize_csv_source_time


DEFAULT_OUTPUT_JSON = "runtime/latest_mt5_strategy_tester_analysis.json"
DEFAULT_OUTPUT_MD = "runtime/latest_mt5_strategy_tester_analysis.md"
DEFAULT_PROMOTION_GATE = "runtime/latest_promotion_gate.json"
DEFAULT_SPEC_COVERAGE = "runtime/latest_spec_coverage.json"
DEFAULT_BACK_FORWARD_RUN = "runtime/latest_mt5_back_forward_run.json"
DEFAULT_TESTER_STATUS = "runtime/latest_mt5_tester_status.json"
DEFAULT_MANUAL_TEST_QUEUE = "runtime/latest_mt5_manual_test_queue.json"
DEFAULT_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION = "runtime/latest_mt5_manual_test_queue_with_optimization.json"
DEFAULT_AGENT_CSV_ARCHIVE_ROOT = "runtime/mt5_agent_csv_archive"
MT5_BACK_FORWARD_SAMPLE_SHORTAGE_DEFAULT_FROM_DATE = "2025.01.01"
MT5_BACK_FORWARD_SAMPLE_SHORTAGE_DEFAULT_TO_DATE = "2025.12.31"
MT5_BACK_FORWARD_SAMPLE_SHORTAGE_MIN_EXTENDED_DAYS = 180
BACK_FORWARD_SAMPLE_SHORTAGE_STATES = {
    "back_forward_sample_shortage",
    "backtest_sample_shortage",
    "forward_sample_shortage",
}


@dataclass(frozen=True)
class OptimizationReportSpec:
    label: str
    side: str
    window: str
    path: str


DEFAULT_OPTIMIZATION_REPORTS: tuple[OptimizationReportSpec, ...] = (
    OptimizationReportSpec(
        "sell_short_window",
        "SELL",
        "short",
        "runtime/latest_mt5_optimization_report.json",
    ),
    OptimizationReportSpec(
        "sell_hour12_m30m15_2025",
        "SELL",
        "annual",
        "runtime/latest_mt5_sell_hour12_m30m15_validation_2025_optimization_report.json",
    ),
    OptimizationReportSpec(
        "sell_hour12_m30m15_calendar_2025",
        "SELL",
        "annual",
        "runtime/latest_mt5_sell_hour12_m30m15_calendar_validation_2025_optimization_report.json",
    ),
    OptimizationReportSpec(
        "sell_regime_entry_2025",
        "SELL",
        "annual",
        "runtime/latest_mt5_sell_regime_entry_refit_2025_optimization_report.json",
    ),
    OptimizationReportSpec(
        "buy_wide_stop_short",
        "BUY",
        "short",
        "runtime/latest_mt5_buy_wide_stop_validation_optimization_report.json",
    ),
    OptimizationReportSpec(
        "buy_hour03_wide_stop_2025",
        "BUY",
        "annual",
        "runtime/latest_mt5_buy_hour03_wide_stop_validation_2025_optimization_report.json",
    ),
    OptimizationReportSpec(
        "buy_hour03_wide_stop_calendar_2025",
        "BUY",
        "annual",
        "runtime/latest_mt5_buy_hour03_wide_stop_calendar_validation_2025_optimization_report.json",
    ),
    OptimizationReportSpec(
        "buy_strong_hours_m30m15_2025",
        "BUY",
        "annual",
        "runtime/latest_mt5_buy_strong_hours_m30m15_validation_2025_optimization_report.json",
    ),
)

SOURCE_TIME_REFRESH_LABEL_QUEUE_IDS: dict[str, tuple[str, ...]] = {
    "sell_short_window": ("static_optimization", "optimization"),
    "sell_hour12_m30m15_2025": (
        "static_sell_hour12_m30m15_2025",
        "sell_hour12_m30m15_2025",
    ),
    "sell_hour12_m30m15_calendar_2025": (
        "static_sell_hour12_m30m15_calendar_2025",
        "sell_hour12_m30m15_calendar_2025",
    ),
    "buy_wide_stop_short": (
        "static_buy_wide_stop_short",
        "buy_wide_stop_short",
    ),
    "buy_hour03_wide_stop_2025": (
        "static_buy_hour03_wide_stop_2025",
        "buy_hour03_wide_stop_2025",
    ),
    "buy_hour03_wide_stop_calendar_2025": (
        "static_buy_hour03_wide_stop_calendar_2025",
        "buy_hour03_wide_stop_calendar_2025",
    ),
}

SOURCE_TIME_REFRESH_STATIC_CANDIDATE_LABELS = {
    "sell_hour12_m30m15_2025",
    "sell_hour12_m30m15_calendar_2025",
}

BUY_DIAGNOSTIC_STATIC_CANDIDATE_LABELS = (
    "buy_wide_stop_short",
    "buy_hour03_wide_stop_2025",
    "buy_hour03_wide_stop_calendar_2025",
)

BUY_DIAGNOSTIC_STATUSES = {
    "aggregate_only",
    "below_promotion_threshold",
    "source_files_stale",
    "source_files_missing",
}


def workspace_path(workspace: Path, path: str | Path) -> Path:
    target = Path(path).expanduser()
    if target.is_absolute():
        return target
    return workspace / target


def load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.exists():
        return None, "missing"
    try:
        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as exc:
        return None, f"invalid_json:{exc}"
    if not isinstance(payload, dict):
        return None, "invalid_payload"
    return payload, ""


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_report_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in (TIME_FORMAT, "%Y.%m.%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def compact_path(workspace: Path, path: Path) -> str:
    try:
        return str(path.relative_to(workspace))
    except ValueError:
        return str(path)


def agent_name_from_path(path: Path) -> str:
    return next((parent.name for parent in path.parents if parent.name.startswith("Agent-")), "")


def source_time_matches_reported(expected: Any, actual: dict[str, Any]) -> bool:
    if not isinstance(expected, dict) or not expected:
        return False
    checks = (
        "close_rows",
        "close_rows_with_server_time",
        "close_rows_without_server_time",
        "first_server_time",
        "last_server_time",
    )
    for key in checks:
        if key not in expected:
            continue
        expected_value = expected.get(key)
        actual_value = actual.get(key)
        if key.endswith("_rows") or key == "close_rows":
            if as_int(expected_value) != as_int(actual_value):
                return False
        elif str(expected_value or "") != str(actual_value or ""):
            return False
    return True


def build_source_file_archive_index(
    workspace: Path,
    files: list[Any],
) -> dict[tuple[str, str, int], list[Path]]:
    archive_root = workspace_path(workspace, DEFAULT_AGENT_CSV_ARCHIVE_ROOT)
    if not archive_root.exists():
        return {}
    filenames = {
        Path(str(item.get("path") or "")).name
        for item in files
        if isinstance(item, dict) and str(item.get("path") or "")
    }
    if not filenames:
        return {}

    index: dict[tuple[str, str, int], list[Path]] = {}
    for filename in filenames:
        for candidate in archive_root.rglob(filename):
            if not candidate.is_file():
                continue
            agent = agent_name_from_path(candidate)
            if not agent:
                continue
            key = (agent, candidate.name, candidate.stat().st_size)
            index.setdefault(key, []).append(candidate)
    return index


def matching_archived_source_file(
    workspace: Path,
    item: dict[str, Any],
    path: Path,
    recorded_size: int | None,
    recorded_mtime: datetime | None,
    archive_index: dict[tuple[str, str, int], list[Path]],
) -> dict[str, Any] | None:
    if recorded_size is None:
        return None
    agent = str(item.get("agent") or "") or agent_name_from_path(path)
    if not agent:
        return None
    key = (agent, path.name, recorded_size)
    candidates = archive_index.get(key, [])
    expected_source_time = item.get("source_time") if isinstance(item.get("source_time"), dict) else {}
    for archive_path in sorted(candidates, key=lambda candidate: str(candidate)):
        archive_stat = archive_path.stat()
        archive_mtime = datetime.fromtimestamp(archive_stat.st_mtime)
        if expected_source_time:
            actual_source_time = summarize_csv_source_time(archive_path)
            recorded_rows = as_int(item.get("rows"))
            if recorded_rows is not None and as_int(actual_source_time.get("rows")) != recorded_rows:
                continue
            if not source_time_matches_reported(expected_source_time, actual_source_time):
                continue
        elif (
            recorded_mtime is not None
            and archive_mtime.strftime(TIME_FORMAT) != recorded_mtime.strftime(TIME_FORMAT)
        ):
            continue
        return {
            "path": compact_path(workspace, archive_path),
            "agent": agent,
            "size": archive_stat.st_size,
            "mtime": archive_mtime.strftime(TIME_FORMAT),
            "source_time_checked": bool(expected_source_time),
        }
    return None


def top_stable_pass(tester_xml: dict[str, Any]) -> dict[str, Any]:
    forward = tester_xml.get("forward") if isinstance(tester_xml.get("forward"), dict) else {}
    stable_top = forward.get("stable_top") if isinstance(forward.get("stable_top"), list) else []
    if stable_top and isinstance(stable_top[0], dict):
        row = stable_top[0]
        return {
            "pass": row.get("Pass"),
            "forward_result": row.get("Forward Result"),
            "back_result": row.get("Back Result"),
            "profit_factor": row.get("Profit Factor"),
            "trades": row.get("Trades"),
        }
    return {}


def tester_xml_summary(tester_xml: Any) -> dict[str, Any]:
    if not isinstance(tester_xml, dict):
        return {
            "back_rows": 0,
            "forward_rows": 0,
            "stable_forward_positive_back_positive": 0,
            "forward_positive_back_negative": 0,
            "top_stable_pass": {},
        }
    back = tester_xml.get("back") if isinstance(tester_xml.get("back"), dict) else {}
    forward = tester_xml.get("forward") if isinstance(tester_xml.get("forward"), dict) else {}
    return {
        "back_rows": as_int(back.get("rows")) or 0,
        "forward_rows": as_int(forward.get("rows")) or 0,
        "stable_forward_positive_back_positive": as_int(forward.get("positive_forward_positive_back")) or 0,
        "forward_positive_back_negative": as_int(forward.get("positive_forward_negative_back")) or 0,
        "top_stable_pass": top_stable_pass(tester_xml),
    }


def source_file_state(workspace: Path, summary: dict[str, Any]) -> dict[str, Any]:
    files = summary.get("files") if isinstance(summary.get("files"), list) else []
    archive_index = build_source_file_archive_index(workspace, files)
    checked = 0
    missing = 0
    stale = 0
    archived = 0
    original_missing = 0
    original_stale = 0
    examples: list[dict[str, Any]] = []
    archive_examples: list[dict[str, Any]] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        path_text = str(item.get("path") or "")
        if not path_text:
            continue
        checked += 1
        path = workspace_path(workspace, path_text)
        recorded_size = as_int(item.get("size"))
        recorded_mtime = parse_report_time(item.get("mtime"))
        if not path.exists():
            original_missing += 1
            archive_match = matching_archived_source_file(
                workspace,
                item,
                path,
                recorded_size,
                recorded_mtime,
                archive_index,
            )
            if archive_match:
                archived += 1
                if len(archive_examples) < 3:
                    archive_examples.append(
                        {
                            "path": path_text,
                            "archive": archive_match["path"],
                            "reason": "missing_original",
                        }
                    )
                continue
            missing += 1
            if len(examples) < 3:
                examples.append({"path": path_text, "reason": "missing"})
            continue
        stat = path.stat()
        current_mtime = datetime.fromtimestamp(stat.st_mtime)
        reasons: list[str] = []
        if recorded_size is not None and stat.st_size != recorded_size:
            reasons.append(f"size {recorded_size}->{stat.st_size}")
        if recorded_mtime is not None and current_mtime.strftime(TIME_FORMAT) != recorded_mtime.strftime(TIME_FORMAT):
            reasons.append(
                "mtime "
                f"{recorded_mtime.strftime(TIME_FORMAT)}->{current_mtime.strftime(TIME_FORMAT)}"
            )
        if reasons:
            original_stale += 1
            archive_match = matching_archived_source_file(
                workspace,
                item,
                path,
                recorded_size,
                recorded_mtime,
                archive_index,
            )
            if archive_match:
                archived += 1
                if len(archive_examples) < 3:
                    archive_examples.append(
                        {
                            "path": compact_path(workspace, path),
                            "archive": archive_match["path"],
                            "reason": "; ".join(reasons),
                        }
                    )
                continue
            stale += 1
            if len(examples) < 3:
                examples.append(
                    {
                        "path": compact_path(workspace, path),
                        "reason": "; ".join(reasons),
                    }
                )
    if checked == 0:
        status = "not_reported"
    elif stale or missing:
        status = "stale" if stale else "missing"
    elif archived:
        status = "archived"
    else:
        status = "current"
    return {
        "status": status,
        "checked": checked,
        "missing": missing,
        "stale": stale,
        "archived": archived,
        "original_missing": original_missing,
        "original_stale": original_stale,
        "examples": examples,
        "archive_examples": archive_examples,
    }


def source_time_summary(summary: dict[str, Any], *, file_state: dict[str, Any] | None = None) -> dict[str, Any]:
    diagnostics = (
        summary.get("source_time_diagnostics")
        if isinstance(summary.get("source_time_diagnostics"), dict)
        else {}
    )
    coverage = (
        summary.get("source_time_coverage")
        if isinstance(summary.get("source_time_coverage"), dict)
        else {}
    )
    file_state = file_state if isinstance(file_state, dict) else {}
    if not diagnostics:
        status = "missing"
        if file_state.get("status") in {"stale", "missing"}:
            status = "source_files_" + str(file_state.get("status"))
    elif diagnostics.get("matches_expected_range") is False:
        status = "mismatch"
    elif diagnostics.get("matches_expected_range") is True:
        status = "ok"
    else:
        status = "not_checked"
    expected_from = diagnostics.get("expected_from_date", "") if diagnostics else ""
    expected_to = diagnostics.get("expected_to_date", "") if diagnostics else ""
    actual_first = diagnostics.get("actual_first_server_time", "") if diagnostics else coverage.get("first_server_time", "")
    actual_last = diagnostics.get("actual_last_server_time", "") if diagnostics else coverage.get("last_server_time", "")
    warnings = diagnostics.get("warnings") if isinstance(diagnostics.get("warnings"), list) else []
    return {
        "status": status,
        "expected_from_date": expected_from,
        "expected_to_date": expected_to,
        "actual_first_server_time": actual_first,
        "actual_last_server_time": actual_last,
        "actual_span_days": as_float(diagnostics.get("actual_span_days")) if diagnostics else as_float(coverage.get("span_days")),
        "close_rows": as_int(coverage.get("close_rows")),
        "close_rows_with_server_time": as_int(coverage.get("close_rows_with_server_time")),
        "close_rows_without_server_time": as_int(coverage.get("close_rows_without_server_time")),
        "warnings": warnings,
        "source_file_status": file_state.get("status", ""),
        "source_file_checked": as_int(file_state.get("checked")),
        "source_file_stale": as_int(file_state.get("stale")),
        "source_file_missing": as_int(file_state.get("missing")),
        "source_file_archived": as_int(file_state.get("archived")),
        "source_file_examples": file_state.get("examples", []) if isinstance(file_state.get("examples"), list) else [],
        "source_file_archive_examples": file_state.get("archive_examples", [])
        if isinstance(file_state.get("archive_examples"), list)
        else [],
    }


def classify_optimization_report(
    *,
    ok: bool,
    load_error: str,
    closed: int | None,
    pf: float | None,
    avg_price_r: float | None,
    stable_passes: int,
    min_pf: float,
    min_avg_r: float,
    min_stable_passes: int,
    source_time_status: str = "",
) -> str:
    if load_error:
        return load_error
    if not ok:
        return "invalid"
    if source_time_status == "mismatch":
        return "source_time_mismatch"
    if closed is None or closed <= 0:
        return "no_trades"
    if pf is None or avg_price_r is None:
        return "incomplete_metrics"
    if pf < 1.0 or avg_price_r < 0:
        return "rejected"
    if pf >= min_pf and avg_price_r >= min_avg_r and stable_passes >= min_stable_passes:
        return "candidate"
    if pf >= min_pf and avg_price_r >= min_avg_r:
        return "aggregate_only"
    return "below_promotion_threshold"


def summarize_optimization_report(
    workspace: Path,
    spec: OptimizationReportSpec,
    *,
    min_pf: float = 1.2,
    min_avg_r: float = 0.0,
    min_stable_passes: int = 1,
) -> dict[str, Any]:
    path = workspace_path(workspace, spec.path)
    payload, load_error = load_json(path)
    if payload is None:
        return {
            "label": spec.label,
            "side": spec.side,
            "window": spec.window,
            "path": compact_path(workspace, path),
            "status": load_error,
            "ok": False,
            "load_error": load_error,
        }

    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    overall = summary.get("overall") if isinstance(summary.get("overall"), dict) else {}
    xml = tester_xml_summary(summary.get("tester_xml"))
    closed = as_int(overall.get("closed"))
    pf = as_float(overall.get("pf"))
    avg_price_r = as_float(overall.get("avg_price_r"))
    source_files = source_file_state(workspace, summary)
    source_time = source_time_summary(summary, file_state=source_files)
    status = classify_optimization_report(
        ok=payload.get("ok") is not False,
        load_error="",
        closed=closed,
        pf=pf,
        avg_price_r=avg_price_r,
        stable_passes=int(xml["stable_forward_positive_back_positive"]),
        source_time_status=str(source_time.get("status", "")),
        min_pf=min_pf,
        min_avg_r=min_avg_r,
        min_stable_passes=min_stable_passes,
    )
    return {
        "label": spec.label,
        "side": spec.side,
        "window": spec.window,
        "path": compact_path(workspace, path),
        "status": status,
        "ok": payload.get("ok") is not False,
        "generated_at": summary.get("generated_at") or payload.get("generated_at", ""),
        "metrics": {
            "closed": closed,
            "wins": as_int(overall.get("wins")),
            "losses": as_int(overall.get("losses")),
            "win_rate": as_float(overall.get("win_rate")),
            "pf": pf,
            "avg_price_r": avg_price_r,
            "net_profit": as_float(overall.get("net_profit")),
            "max_drawdown_price_r": as_float(overall.get("max_drawdown_price_r")),
            "tp_rate": as_float(overall.get("tp_rate")),
            "sl_rate": as_float(overall.get("sl_rate")),
        },
        "tester_xml": xml,
        "source_time": source_time,
        "source_files": source_files,
    }


def summarize_promotion_gate(workspace: Path, path: str) -> dict[str, Any]:
    payload, load_error = load_json(workspace_path(workspace, path))
    if payload is None:
        return {"exists": False, "path": path, "status": load_error}
    failed = payload.get("failed_check_names") or payload.get("failed_checks") or []
    return {
        "exists": True,
        "path": path,
        "ok": payload.get("ok") is not False,
        "generated_at": payload.get("generated_at", ""),
        "decision": payload.get("decision", ""),
        "live_ready": bool(payload.get("live_ready")),
        "check_count": as_int(payload.get("check_count")),
        "failed": as_int(payload.get("failed")),
        "failed_check_names": failed if isinstance(failed, list) else [],
    }


def summarize_spec_coverage(workspace: Path, path: str) -> dict[str, Any]:
    payload, load_error = load_json(workspace_path(workspace, path))
    if payload is None:
        return {"exists": False, "path": path, "status": load_error, "not_complete_reasons": []}
    reasons = payload.get("not_complete_reasons")
    next_actions = payload.get("next_actions")
    return {
        "exists": True,
        "path": path,
        "generated_at": payload.get("generated_at", ""),
        "goal_completion_proven": bool(payload.get("goal_completion_proven")),
        "not_complete_reason_count": as_int(payload.get("not_complete_reason_count")),
        "not_complete_reasons": reasons if isinstance(reasons, list) else [],
        "next_actions": next_actions if isinstance(next_actions, list) else [],
    }


def summarize_back_forward_run(workspace: Path, path: str) -> dict[str, Any]:
    payload, load_error = load_json(workspace_path(workspace, path))
    if payload is None:
        return {"exists": False, "path": path, "status": load_error}
    manual = payload.get("manual_strategy_tester") if isinstance(payload.get("manual_strategy_tester"), dict) else {}
    comparison = payload.get("performance_comparison")
    if not isinstance(comparison, dict):
        comparison = {}
    readiness = payload.get("manual_collect_readiness")
    if not isinstance(readiness, dict):
        readiness = {}
    return {
        "exists": True,
        "path": path,
        "ok": payload.get("ok") is not False,
        "generated_at": payload.get("generated_at", ""),
        "mode": payload.get("mode", ""),
        "run_id_prefix": payload.get("run_id_prefix", ""),
        "execution_conditions": (
            payload.get("execution_conditions")
            if isinstance(payload.get("execution_conditions"), dict)
            else {}
        ),
        "execute": bool(payload.get("execute")),
        "collect_only": bool(payload.get("collect_only")),
        "dry_run": bool(payload.get("dry_run")),
        "evidence_state": payload.get("evidence_state", ""),
        "performance_status": comparison.get("status", ""),
        "performance_available": bool(comparison.get("available")),
        "performance_reason": comparison.get("reason", ""),
        "performance_thresholds": comparison.get("thresholds")
        if isinstance(comparison.get("thresholds"), dict)
        else {},
        "performance_rows": comparison.get("rows") if isinstance(comparison.get("rows"), list) else [],
        "manual_strategy_tester_available": bool(manual.get("available")),
        "manual_run_start_after": manual.get("manual_run_start_after", ""),
        "recommended_collect_only_command_text": manual.get("recommended_collect_only_command_text", ""),
        "manual_collect_status": readiness.get("status", ""),
        "manual_collect_ready": bool(readiness.get("ready")),
        "manual_collect_blocking_reasons": readiness.get("blocking_reasons")
        if isinstance(readiness.get("blocking_reasons"), list)
        else [],
        "steps": manual.get("steps") if isinstance(manual.get("steps"), list) else [],
    }


def manual_queue_entry_source_matches(entry: dict[str, Any], source_path: str | Path | None) -> bool:
    source_json = str(entry.get("source_json") or "")
    if not source_json or not source_path:
        return True
    source_path_text = str(source_path)
    if source_json == source_path_text:
        return True
    try:
        return Path(source_json).resolve() == Path(source_path_text).resolve()
    except OSError:
        return False


def manual_queue_entry(
    manual_queues: tuple[dict[str, Any], ...],
    entry_id: str,
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    for queue in manual_queues:
        entries = queue.get("entries") if isinstance(queue.get("entries"), list) else []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("id") or "") != entry_id:
                continue
            if manual_queue_entry_source_matches(entry, source_path):
                return entry
    return {}


def apply_back_forward_manual_queue_collect_filter(
    back_forward: dict[str, Any],
    manual_queues: tuple[dict[str, Any], ...],
    *,
    back_forward_run_path: str | Path | None = None,
) -> None:
    entry = manual_queue_entry(manual_queues, "back_forward", source_path=back_forward_run_path)
    if not entry:
        return
    collect_command = str(entry.get("collect_only_command_text") or "")
    manual_run_start_after = str(entry.get("manual_run_start_after") or "")
    collect_modified_after = str(entry.get("collect_modified_after") or manual_run_start_after)
    if collect_command:
        back_forward["recommended_collect_only_command_text"] = collect_command
    if manual_run_start_after:
        back_forward["manual_run_start_after"] = manual_run_start_after
    if collect_modified_after:
        back_forward["manual_collect_modified_after"] = collect_modified_after


def performance_row(rows: Any, dataset: str) -> dict[str, Any]:
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if isinstance(row, dict) and str(row.get("dataset") or "") == dataset:
            return row
    return {}


def parse_mt5_date(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y.%m.%d")
    except ValueError:
        return None


def back_forward_extended_window_dates(conditions: dict[str, Any]) -> tuple[str, str, int | None, str]:
    from_date = str(conditions.get("from_date") or "")
    to_date = str(conditions.get("to_date") or "")
    start = parse_mt5_date(from_date)
    end = parse_mt5_date(to_date)
    if start and end:
        days = max((end - start).days, 0)
        if days >= MT5_BACK_FORWARD_SAMPLE_SHORTAGE_MIN_EXTENDED_DAYS:
            return from_date, to_date, days, "reuse_existing_extended_window"
        return (
            MT5_BACK_FORWARD_SAMPLE_SHORTAGE_DEFAULT_FROM_DATE,
            MT5_BACK_FORWARD_SAMPLE_SHORTAGE_DEFAULT_TO_DATE,
            days,
            "extend_to_default_full_year",
        )
    return (
        MT5_BACK_FORWARD_SAMPLE_SHORTAGE_DEFAULT_FROM_DATE,
        MT5_BACK_FORWARD_SAMPLE_SHORTAGE_DEFAULT_TO_DATE,
        None,
        "extend_to_default_full_year",
    )


def back_forward_extended_window_command(
    back_forward: dict[str, Any],
    *,
    from_date: str,
    to_date: str,
) -> str:
    conditions = (
        back_forward.get("execution_conditions")
        if isinstance(back_forward.get("execution_conditions"), dict)
        else {}
    )
    command = [
        "python3",
        "methods/swing_eval/analysis/mt5_back_forward_run.py",
        "--mode",
        str(back_forward.get("mode") or "both"),
        "--execute",
        "--refresh-ready-status",
        "--run-id-prefix",
        f"{str(back_forward.get('run_id_prefix') or 'mt5_back_forward')}_extended_window",
        "--from-date",
        from_date,
        "--to-date",
        to_date,
    ]
    for option, key in (
        ("--timeout-seconds", "per_step_timeout_seconds"),
        ("--since-minutes", "since_minutes"),
        ("--min-closed", "min_closed"),
        ("--forward-mode", "forward_mode"),
    ):
        value = conditions.get(key)
        if value not in (None, ""):
            command.extend([option, str(value)])
    for flag, key in (
        ("--sync-expert-parameters-set", "sync_expert_parameters_set"),
        ("--allow-running-terminal", "allow_running_terminal"),
        ("--allow-stale-compile", "allow_stale_compile"),
        ("--allow-invalid-risk-preset", "allow_invalid_risk_preset"),
        ("--require-bridge-ready", "require_bridge_ready"),
        ("--skip-archive-preview", "skip_archive_preview"),
    ):
        if conditions.get(key) is True:
            command.append(flag)
    max_ready_status_age = conditions.get("max_ready_status_age_seconds")
    if max_ready_status_age not in (None, ""):
        command.extend(["--max-ready-status-age-seconds", str(max_ready_status_age)])
    return shlex.join(command)


def back_forward_sample_shortage_recovery(back_forward: dict[str, Any]) -> dict[str, Any]:
    conditions = (
        back_forward.get("execution_conditions")
        if isinstance(back_forward.get("execution_conditions"), dict)
        else {}
    )
    from_date, to_date, current_days, range_strategy = back_forward_extended_window_dates(conditions)
    current_from = str(conditions.get("from_date") or "")
    current_to = str(conditions.get("to_date") or "")
    return {
        "kind": "mt5_back_forward_sample_shortage_recovery",
        "strategy": "extend_date_range_before_judging_performance",
        "range_strategy": range_strategy,
        "current_from_date": current_from,
        "current_to_date": current_to,
        "current_range_days": current_days,
        "suggested_from_date": from_date,
        "suggested_to_date": to_date,
        "min_extended_days": MT5_BACK_FORWARD_SAMPLE_SHORTAGE_MIN_EXTENDED_DAYS,
        "command_text": back_forward_extended_window_command(
            back_forward,
            from_date=from_date,
            to_date=to_date,
        ),
    }


def back_forward_decision_summary(back_forward: dict[str, Any]) -> dict[str, Any]:
    exists = back_forward.get("exists") is True
    evidence_state = str(back_forward.get("evidence_state") or "")
    performance_status = str(back_forward.get("performance_status") or "")
    rows = back_forward.get("performance_rows") if isinstance(back_forward.get("performance_rows"), list) else []
    thresholds = (
        back_forward.get("performance_thresholds")
        if isinstance(back_forward.get("performance_thresholds"), dict)
        else {}
    )
    backtest_row = performance_row(rows, "backtest")
    forward_row = performance_row(rows, "forward")
    manual_ready = back_forward.get("manual_collect_ready") is True
    manual_status = str(back_forward.get("manual_collect_status") or "")

    if not exists:
        status = "missing_back_forward_run"
        next_action = "refresh_mt5_back_forward_run"
        reason = "Back/Forward runner artifact is missing."
        adoptable = False
    elif evidence_state == "executed_consistent":
        status = "passed"
        next_action = "use_back_forward_evidence_for_promotion_gate"
        reason = "Backtest and Forward evidence are consistent enough for this gate."
        adoptable = True
    elif evidence_state == "plan_only":
        if manual_ready:
            status = "collect_ready"
            next_action = "collect_manual_back_forward_results"
            reason = "Back/Forward reports look ready; collect them before judging promotion evidence."
        else:
            status = "run_manual_back_forward"
            next_action = "run_backtest_then_forward_in_mt5_strategy_tester"
            reason = "Back/Forward runner is still a plan; MT5 Strategy Tester reports are not collected yet."
        adoptable = False
    elif evidence_state in {"executed_degraded", "executed_below_break_even"}:
        if performance_status == "forward_below_break_even":
            status = "forward_below_break_even"
            next_action = "reject_or_refit_before_promotion"
            reason = "Forward result is below break-even PF or average R."
        else:
            status = "forward_regression"
            next_action = "reject_or_refit_before_promotion"
            reason = "Forward result degraded versus the backtest beyond the allowed threshold."
        adoptable = False
    elif evidence_state == "executed_sample_shortage":
        status = "sample_shortage"
        next_action = "extend_back_forward_window_or_collect_more_closed_trades"
        reason = "Back/Forward reports exist, but one or both sides do not meet the minimum closed-trade count."
        adoptable = False
    elif evidence_state in {"executed_missing_comparison", "executed_comparison_issue"}:
        status = performance_status or "comparison_issue"
        next_action = "refresh_or_recollect_back_forward_reports"
        reason = back_forward.get("performance_reason") or "Back/Forward comparison is incomplete or inconsistent."
        adoptable = False
    elif evidence_state in {"executed_blocked", "executed_failed"}:
        status = evidence_state
        next_action = "fix_back_forward_runner_execution"
        reason = "Back/Forward runner execution did not produce usable evidence."
        adoptable = False
    elif performance_status in {
        "back_forward_sample_shortage",
        "backtest_sample_shortage",
        "forward_sample_shortage",
    }:
        status = "sample_shortage"
        next_action = "extend_back_forward_window_or_collect_more_closed_trades"
        reason = "Back/Forward comparison is sample-short."
        adoptable = False
    elif performance_status in {"forward_degraded_vs_backtest", "forward_below_break_even"}:
        status = (
            "forward_below_break_even"
            if performance_status == "forward_below_break_even"
            else "forward_regression"
        )
        next_action = "reject_or_refit_before_promotion"
        reason = (
            "Forward result is below break-even."
            if performance_status == "forward_below_break_even"
            else "Forward result degraded versus backtest."
        )
        adoptable = False
    else:
        status = evidence_state or performance_status or "unknown"
        next_action = "inspect_back_forward_evidence"
        reason = "Back/Forward evidence is not in a recognized adoptable state."
        adoptable = False

    sample_shortage_recovery = (
        back_forward_sample_shortage_recovery(back_forward)
        if status == "sample_shortage" or performance_status in BACK_FORWARD_SAMPLE_SHORTAGE_STATES
        else {}
    )
    return {
        "status": status,
        "adoptable": adoptable,
        "evidence_state": evidence_state,
        "performance_status": performance_status,
        "performance_available": back_forward.get("performance_available"),
        "manual_collect_ready": manual_ready,
        "manual_collect_status": manual_status,
        "next_action": next_action,
        "reason": reason,
        "thresholds": thresholds,
        "backtest": backtest_row,
        "forward": forward_row,
        "backtest_trades": backtest_row.get("trades", ""),
        "forward_trades": forward_row.get("trades", ""),
        "forward_pf": forward_row.get("pf", ""),
        "forward_avg_r": forward_row.get("avg_r", ""),
        "forward_pf_delta_vs_backtest": forward_row.get("pf_delta_vs_backtest", ""),
        "forward_avg_r_delta_vs_backtest": forward_row.get("avg_r_delta_vs_backtest", ""),
        "collect_command_text": back_forward.get("recommended_collect_only_command_text", ""),
        "sample_shortage_recovery": sample_shortage_recovery,
        "sample_shortage_recovery_command_text": sample_shortage_recovery.get("command_text", "")
        if sample_shortage_recovery
        else "",
        "sample_shortage_recovery_range_strategy": sample_shortage_recovery.get("range_strategy", "")
        if sample_shortage_recovery
        else "",
        "sample_shortage_recovery_suggested_from_date": sample_shortage_recovery.get(
            "suggested_from_date", ""
        )
        if sample_shortage_recovery
        else "",
        "sample_shortage_recovery_suggested_to_date": sample_shortage_recovery.get(
            "suggested_to_date", ""
        )
        if sample_shortage_recovery
        else "",
    }


def summarize_tester_status(workspace: Path, path: str) -> dict[str, Any]:
    payload, load_error = load_json(workspace_path(workspace, path))
    if payload is None:
        return {"exists": False, "path": path, "status": load_error}
    handoff = payload.get("mt5_operator_handoff")
    if not isinstance(handoff, dict):
        handoff = {}
    step = handoff.get("next_mt5_step") if isinstance(handoff.get("next_mt5_step"), dict) else {}
    return {
        "exists": True,
        "path": path,
        "generated_at": payload.get("generated_at", ""),
        "operational_status": payload.get("operational_status", ""),
        "handoff_state": handoff.get("state", ""),
        "recommended_path": handoff.get("recommended_path", ""),
        "terminal_running": bool(handoff.get("terminal_running")),
        "auto_launch_status": handoff.get("auto_launch_status", ""),
        "auto_launch_blockers": handoff.get("auto_launch_blockers")
        if isinstance(handoff.get("auto_launch_blockers"), list)
        else [],
        "manual_queue_status": handoff.get("manual_queue_status", ""),
        "manual_collect_status": handoff.get("manual_collect_status", ""),
        "manual_collect_execute_command_text": handoff.get("manual_collect_execute_command_text", ""),
        "manual_collect_execute_and_refresh_analysis_command_text": handoff.get(
            "manual_collect_execute_and_refresh_analysis_command_text", ""
        ),
        "next_mt5_step": step,
        "bridge_required_for_standalone_tester": bool(handoff.get("bridge_required_for_standalone_tester")),
        "bridge_note": handoff.get("bridge_note", ""),
    }


def summarize_manual_test_queue(workspace: Path, path: str) -> dict[str, Any]:
    payload, load_error = load_json(workspace_path(workspace, path))
    if payload is None:
        return {"exists": False, "path": path, "status": load_error}
    handoff = payload.get("operator_handoff") if isinstance(payload.get("operator_handoff"), dict) else {}
    static_strategy_configs = (
        [str(item) for item in payload.get("static_strategy_configs")]
        if isinstance(payload.get("static_strategy_configs"), list)
        else []
    )
    static_candidate_labels = (
        [str(item) for item in payload.get("static_candidate_labels")]
        if isinstance(payload.get("static_candidate_labels"), list)
        else []
    )
    raw_entries = payload.get("entries") if isinstance(payload.get("entries"), list) else []
    entries = [
        {
            "id": entry.get("id", ""),
            "source_json": entry.get("source_json", ""),
            "manual_run_start_after": entry.get("manual_run_start_after", ""),
            "collect_modified_after": entry.get("collect_modified_after", ""),
            "collect_only_command_text": entry.get("collect_only_command_text", ""),
        }
        for entry in raw_entries
        if isinstance(entry, dict)
    ]
    return {
        "exists": True,
        "path": path,
        "ok": payload.get("ok") is not False,
        "generated_at": payload.get("generated_at", ""),
        "status": payload.get("status", ""),
        "next_action": payload.get("next_action", ""),
        "entry_count": as_int(payload.get("entry_count")),
        "total_entry_count": as_int(payload.get("total_entry_count")),
        "step_count": as_int(payload.get("step_count")),
        "ready_to_collect_count": as_int(payload.get("ready_to_collect_count")),
        "waiting_count": as_int(payload.get("waiting_count")),
        "static_strategy_config_count": as_int(
            payload.get("static_strategy_config_count")
        )
        if payload.get("static_strategy_config_count") not in (None, "")
        else len(static_strategy_configs),
        "static_strategy_configs": static_strategy_configs,
        "static_candidate_label_count": as_int(
            payload.get("static_candidate_label_count")
        )
        if payload.get("static_candidate_label_count") not in (None, "")
        else len(static_candidate_labels),
        "static_candidate_labels": static_candidate_labels,
        "step_report_ready_count": as_int(payload.get("step_report_ready_count")),
        "step_waiting_report_count": as_int(payload.get("step_waiting_report_count")),
        "step_launch_needed_count": as_int(payload.get("step_launch_needed_count")),
        "next_launch_step": payload.get("next_launch_step")
        if isinstance(payload.get("next_launch_step"), dict)
        else {},
        "operator_handoff": handoff,
        "strategy_tester_targets": payload.get("strategy_tester_targets")
        if isinstance(payload.get("strategy_tester_targets"), list)
        else [],
        "operation_cards": payload.get("operation_cards") if isinstance(payload.get("operation_cards"), list) else [],
        "execution_checklist": payload.get("execution_checklist")
        if isinstance(payload.get("execution_checklist"), list)
        else [],
        "entries": entries,
    }


def summarize_source_artifact(workspace: Path, label: str, summary: dict[str, Any]) -> dict[str, Any]:
    path_text = str(summary.get("path") or "")
    path = workspace_path(workspace, path_text) if path_text else None
    exists = bool(path and path.exists())
    mtime_age_seconds: float | None = None
    if path and exists:
        mtime_age_seconds = max(0.0, time.time() - path.stat().st_mtime)
    state = (
        summary.get("decision")
        or summary.get("evidence_state")
        or summary.get("operational_status")
        or summary.get("status")
        or ""
    )
    if not state and "goal_completion_proven" in summary:
        if summary.get("goal_completion_proven"):
            state = "goal_completion_proven"
        else:
            count = summary.get("not_complete_reason_count")
            state = f"not_complete:{count}" if count not in (None, "") else "not_complete"
    return {
        "label": label,
        "path": path_text,
        "exists": exists,
        "generated_at": summary.get("generated_at", ""),
        "state": state,
        "mtime_age_seconds": round(mtime_age_seconds, 1) if mtime_age_seconds is not None else "",
    }


def summarize_source_artifacts(
    workspace: Path,
    *,
    promotion_gate: dict[str, Any],
    spec_coverage: dict[str, Any],
    back_forward: dict[str, Any],
    tester_status: dict[str, Any],
    manual_test_queue: dict[str, Any],
    manual_test_queue_with_optimization: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        summarize_source_artifact(workspace, "promotion_gate", promotion_gate),
        summarize_source_artifact(workspace, "spec_coverage", spec_coverage),
        summarize_source_artifact(workspace, "back_forward_run", back_forward),
        summarize_source_artifact(workspace, "tester_status", tester_status),
        summarize_source_artifact(workspace, "manual_test_queue", manual_test_queue),
        summarize_source_artifact(
            workspace,
            "manual_test_queue_with_optimization",
            manual_test_queue_with_optimization,
        ),
    ]


def source_time_issue_reason(row: dict[str, Any]) -> str:
    source_files = row.get("source_files") if isinstance(row.get("source_files"), dict) else {}
    source_time = row.get("source_time") if isinstance(row.get("source_time"), dict) else {}
    source_file_status = str(source_files.get("status") or "")
    source_time_status = str(source_time.get("status") or "")
    if source_file_status in {"stale", "missing"}:
        return f"source_files_{source_file_status}"
    if source_time_status in {
        "mismatch",
        "missing",
        "source_files_stale",
        "source_files_missing",
    }:
        return source_time_status
    return ""


def queue_step_keys_for_label(label: str) -> tuple[str, ...]:
    keys = [label]
    keys.extend(SOURCE_TIME_REFRESH_LABEL_QUEUE_IDS.get(label, ()))
    keys.append("static_" + label)
    return tuple(dict.fromkeys(key for key in keys if key))


def find_manual_queue_item(manual_queue: dict[str, Any], label: str, key: str) -> dict[str, Any]:
    lookup_keys = set(queue_step_keys_for_label(label))
    values = manual_queue.get(key) if isinstance(manual_queue.get(key), list) else []
    for item in values:
        if not isinstance(item, dict):
            continue
        item_keys = {
            str(item.get("queue_id") or ""),
            str(item.get("step_label") or ""),
        }
        if item_keys & lookup_keys:
            return item
    return {}


def source_time_refresh_queue_command(issue_labels: list[str]) -> str:
    command = [
        "python3 methods/swing_eval/analysis/mt5_manual_test_queue.py",
        "--include-optimization-configs",
    ]
    for label in issue_labels:
        if label in SOURCE_TIME_REFRESH_STATIC_CANDIDATE_LABELS:
            command.extend(["--include-static-candidate-label", label])
    command.extend(
        [
            "--output-json",
            DEFAULT_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION,
            "--output-md",
            "runtime/latest_mt5_manual_test_queue_with_optimization.md",
        ]
    )
    return " ".join(command)


def buy_diagnostic_queue_command(labels: list[str]) -> str:
    command = [
        "python3 methods/swing_eval/analysis/mt5_manual_test_queue.py",
        "--include-optimization-configs",
    ]
    for label in sorted(SOURCE_TIME_REFRESH_STATIC_CANDIDATE_LABELS):
        command.extend(["--include-static-candidate-label", label])
    for label in labels:
        if label in BUY_DIAGNOSTIC_STATIC_CANDIDATE_LABELS:
            command.extend(["--include-static-candidate-label", label])
    command.extend(
        [
            "--output-json",
            DEFAULT_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION,
            "--output-md",
            "runtime/latest_mt5_manual_test_queue_with_optimization.md",
        ]
    )
    return " ".join(command)


def buy_diagnostic_priority(row: dict[str, Any]) -> tuple[int, float, float, int]:
    label_order = {
        "buy_wide_stop_short": 0,
        "buy_hour03_wide_stop_2025": 1,
        "buy_hour03_wide_stop_calendar_2025": 2,
    }
    metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
    stable = row.get("tester_xml") if isinstance(row.get("tester_xml"), dict) else {}
    return (
        label_order.get(str(row.get("label") or ""), 99),
        -(as_float(metrics.get("pf")) or 0.0),
        -(as_float(metrics.get("avg_price_r")) or 0.0),
        -(as_int(stable.get("stable_forward_positive_back_positive")) or 0),
    )


def build_buy_candidate_gap_plan(
    optimization_reports: list[dict[str, Any]],
    manual_queue_with_optimization: dict[str, Any],
) -> dict[str, Any]:
    buy_candidates = [
        row
        for row in optimization_reports
        if str(row.get("side") or "").upper() == "BUY" and row.get("status") == "candidate"
    ]
    if buy_candidates:
        return {
            "status": "ok",
            "reason": "",
            "candidate_labels": [row.get("label") for row in buy_candidates],
            "diagnostic_labels": [],
            "entries": [],
            "refresh_queue_command_text": "",
        }

    diagnostics = [
        row
        for row in optimization_reports
        if str(row.get("side") or "").upper() == "BUY"
        and str(row.get("label") or "") in BUY_DIAGNOSTIC_STATIC_CANDIDATE_LABELS
        and row.get("status") in BUY_DIAGNOSTIC_STATUSES
    ]
    diagnostics.sort(key=buy_diagnostic_priority)
    labels = [str(row.get("label") or "") for row in diagnostics if row.get("label")]
    entries: list[dict[str, Any]] = []
    for row in diagnostics:
        label = str(row.get("label") or "")
        operation_card = find_manual_queue_item(
            manual_queue_with_optimization,
            label,
            "operation_cards",
        )
        checklist_item = find_manual_queue_item(
            manual_queue_with_optimization,
            label,
            "execution_checklist",
        )
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        tester_xml = row.get("tester_xml") if isinstance(row.get("tester_xml"), dict) else {}
        source_files = row.get("source_files") if isinstance(row.get("source_files"), dict) else {}
        source_time = row.get("source_time") if isinstance(row.get("source_time"), dict) else {}
        entries.append(
            {
                "label": label,
                "status": row.get("status", ""),
                "window": row.get("window", ""),
                "pf": metrics.get("pf", ""),
                "avg_price_r": metrics.get("avg_price_r", ""),
                "closed": metrics.get("closed", ""),
                "stable_forward_back_positive": tester_xml.get(
                    "stable_forward_positive_back_positive",
                    "",
                ),
                "queue_id": operation_card.get("queue_id")
                or checklist_item.get("queue_id")
                or next(iter(queue_step_keys_for_label(label)), ""),
                "step_label": operation_card.get("step_label") or checklist_item.get("step_label") or label,
                "dates": operation_card.get("dates") or checklist_item.get("dates", ""),
                "forward": operation_card.get("forward") or checklist_item.get("forward", ""),
                "inputs": operation_card.get("inputs") or checklist_item.get("inputs", ""),
                "report": operation_card.get("report") or checklist_item.get("report", ""),
                "launch_command_kind": checklist_item.get("launch_command_kind", ""),
                "launch_command_text": checklist_item.get("launch_command_text", ""),
                "collect_command_text": operation_card.get("collect_command_text", ""),
                "manual_queue_matched": bool(operation_card or checklist_item),
                "source_time_status": source_time.get("status", ""),
                "source_file_status": source_files.get("status", ""),
                "source_file_checked": source_files.get("checked", ""),
                "source_file_stale": source_files.get("stale", ""),
                "source_file_missing": source_files.get("missing", ""),
                "source_file_archived": source_files.get("archived", ""),
                "source_file_examples": (
                    source_files.get("examples")
                    if isinstance(source_files.get("examples"), list)
                    else []
                ),
            }
        )

    status = "needs_buy_diagnostic" if labels else "no_buy_diagnostic_available"
    reason = (
        "BUY candidate is missing; queue positive or near-threshold BUY diagnostics in MT5 Strategy Tester."
        if labels
        else "BUY candidate is missing and no configured BUY diagnostic labels were found."
    )
    return {
        "status": status,
        "reason": reason,
        "candidate_labels": [],
        "diagnostic_labels": labels,
        "entries": entries,
        "refresh_queue_command_text": buy_diagnostic_queue_command(labels) if labels else "",
        "dry_run_launch_command_text": (
            "python3 methods/swing_eval/analysis/mt5_manual_queue_launch.py "
            f"--queue {DEFAULT_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
            "--output-json runtime/latest_mt5_manual_queue_launch_with_optimization.json "
            "--output-md runtime/latest_mt5_manual_queue_launch_with_optimization.md"
        )
        if labels
        else "",
        "collect_execute_and_refresh_command_text": (
            "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
            f"--queue {DEFAULT_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
            "--execute --refresh-post-collect-analysis "
            "--output-json runtime/latest_mt5_manual_collect_with_optimization.json "
            "--output-md runtime/latest_mt5_manual_collect_with_optimization.md"
        )
        if labels
        else "",
    }


def build_source_time_refresh_plan(
    optimization_reports: list[dict[str, Any]],
    manual_queue_with_optimization: dict[str, Any],
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    issue_labels: list[str] = []
    candidate_issue_labels: list[str] = []

    for row in optimization_reports:
        if not isinstance(row, dict):
            continue
        issue = source_time_issue_reason(row)
        if not issue:
            continue
        if row.get("status") != "candidate":
            continue
        label = str(row.get("label") or "")
        if label:
            issue_labels.append(label)
        if label:
            candidate_issue_labels.append(label)

        operation_card = find_manual_queue_item(
            manual_queue_with_optimization,
            label,
            "operation_cards",
        )
        checklist_item = find_manual_queue_item(
            manual_queue_with_optimization,
            label,
            "execution_checklist",
        )
        queue_id = (
            operation_card.get("queue_id")
            or checklist_item.get("queue_id")
            or next(iter(queue_step_keys_for_label(label)), "")
        )
        step_label = operation_card.get("step_label") or checklist_item.get("step_label") or label
        source_files = row.get("source_files") if isinstance(row.get("source_files"), dict) else {}
        source_time = row.get("source_time") if isinstance(row.get("source_time"), dict) else {}
        entries.append(
            {
                "label": label,
                "side": row.get("side", ""),
                "window": row.get("window", ""),
                "report_status": row.get("status", ""),
                "candidate": row.get("status") == "candidate",
                "issue": issue,
                "source_time_status": source_time.get("status", ""),
                "source_file_status": source_files.get("status", ""),
                "source_file_checked": source_files.get("checked", ""),
                "source_file_stale": source_files.get("stale", ""),
                "source_file_missing": source_files.get("missing", ""),
                "source_file_examples": source_files.get("examples", [])
                if isinstance(source_files.get("examples"), list)
                else [],
                "queue_id": queue_id,
                "step_label": step_label,
                "order": operation_card.get("order") or checklist_item.get("order", ""),
                "dates": operation_card.get("dates") or checklist_item.get("dates", ""),
                "forward": operation_card.get("forward") or checklist_item.get("forward", ""),
                "optimization_label": operation_card.get("optimization_label")
                or checklist_item.get("optimization_label")
                or operation_card.get("optimization")
                or checklist_item.get("optimization", ""),
                "inputs": operation_card.get("inputs") or checklist_item.get("inputs", ""),
                "report": operation_card.get("report") or checklist_item.get("report", ""),
                "launch_command_kind": checklist_item.get("launch_command_kind", ""),
                "launch_command_text": checklist_item.get("launch_command_text", ""),
                "collect_command_text": operation_card.get("collect_command_text", ""),
                "manual_queue_matched": bool(operation_card or checklist_item),
            }
        )

    unique_issue_labels = list(dict.fromkeys(issue_labels))
    unique_candidate_issue_labels = list(dict.fromkeys(candidate_issue_labels))
    status = "needs_refresh" if entries else "ok"
    return {
        "status": status,
        "issue_count": len(entries),
        "candidate_issue_count": len(unique_candidate_issue_labels),
        "issue_labels": unique_issue_labels,
        "candidate_issue_labels": unique_candidate_issue_labels,
        "manual_queue_path": DEFAULT_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION,
        "manual_queue_status": manual_queue_with_optimization.get("status", ""),
        "manual_queue_next_action": manual_queue_with_optimization.get("next_action", ""),
        "refresh_queue_command_text": source_time_refresh_queue_command(unique_issue_labels)
        if entries
        else "",
        "dry_run_launch_command_text": (
            "python3 methods/swing_eval/analysis/mt5_manual_queue_launch.py "
            f"--queue {DEFAULT_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
            "--output-json runtime/latest_mt5_manual_queue_launch_with_optimization.json "
            "--output-md runtime/latest_mt5_manual_queue_launch_with_optimization.md"
        )
        if entries
        else "",
        "collect_execute_and_refresh_command_text": (
            "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
            f"--queue {DEFAULT_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
            "--execute --refresh-post-collect-analysis "
            "--output-json runtime/latest_mt5_manual_collect_with_optimization.json "
            "--output-md runtime/latest_mt5_manual_collect_with_optimization.md"
        )
        if entries
        else "",
        "refresh_analysis_command_text": (
            "python3 methods/swing_eval/analysis/mt5_strategy_tester_analysis.py "
            "--output-json runtime/latest_mt5_strategy_tester_analysis.json "
            "--output-md runtime/latest_mt5_strategy_tester_analysis.md"
        )
        if entries
        else "",
        "entries": entries,
    }


def buy_candidate_gap_blocker(optimization_reports: list[dict[str, Any]]) -> str:
    diagnostics = [
        row
        for row in optimization_reports
        if str(row.get("side") or "").upper() == "BUY"
        and str(row.get("label") or "") in BUY_DIAGNOSTIC_STATIC_CANDIDATE_LABELS
        and row.get("status") in BUY_DIAGNOSTIC_STATUSES
    ]
    diagnostics.sort(key=buy_diagnostic_priority)
    labels = [str(row.get("label") or "") for row in diagnostics if row.get("label")]
    if labels:
        return "buy_candidate_gap:needs_buy_diagnostic:" + ",".join(labels)
    return "buy_candidate_gap:needs_buy_diagnostic"


def adoption_summary(
    promotion_gate: dict[str, Any],
    back_forward: dict[str, Any],
    back_forward_decision: dict[str, Any],
    optimization_reports: list[dict[str, Any]],
    spec_coverage: dict[str, Any],
) -> dict[str, Any]:
    candidates = [row for row in optimization_reports if row.get("status") == "candidate"]
    aggregate_only = [row for row in optimization_reports if row.get("status") == "aggregate_only"]
    candidate_sides = sorted({str(row.get("side", "")).upper() for row in candidates})
    blockers: list[str] = []

    decision = str(promotion_gate.get("decision") or "")
    if decision not in ("ready", "live_ready"):
        blockers.append(f"promotion_gate:{decision or 'missing'}")
    evidence_state = str(back_forward.get("evidence_state") or "")
    if back_forward_decision.get("adoptable") is not True:
        blockers.append(f"mt5_back_forward:{evidence_state or back_forward.get('status', 'missing')}")
        decision_status = str(back_forward_decision.get("status") or "")
        if decision_status and decision_status not in {evidence_state, "passed"}:
            blockers.append(f"mt5_back_forward_decision:{decision_status}")
    if "BUY" not in candidate_sides:
        blockers.append("buy_candidate_missing")
        blockers.append(buy_candidate_gap_blocker(optimization_reports))
    if "SELL" not in candidate_sides:
        blockers.append("sell_candidate_missing")
    for row in candidates:
        source_time = row.get("source_time") if isinstance(row.get("source_time"), dict) else {}
        source_files = row.get("source_files") if isinstance(row.get("source_files"), dict) else {}
        source_time_status = str(source_time.get("status") or "")
        source_file_status = str(source_files.get("status") or "")
        label = str(row.get("label") or "unknown")
        if source_file_status in {"stale", "missing"}:
            blockers.append(f"candidate_source_time_files_{source_file_status}:{label}")
        if source_time_status == "mismatch":
            blockers.append(f"candidate_source_time_mismatch:{label}")
        elif source_time_status in {"source_files_stale", "source_files_missing"}:
            blockers.append(f"candidate_source_time_files_{source_time_status.removeprefix('source_files_')}:{label}")
        elif source_time_status == "missing" and str(row.get("window") or "").lower() in {
            "annual",
            "yearly",
            "out_of_year",
            "out-of-year",
        }:
            blockers.append(f"candidate_source_time_missing:{label}")
    for reason in spec_coverage.get("not_complete_reasons", []):
        if isinstance(reason, str) and (
            "mt5_back_forward" in reason
            or "promotion_gate_not_ready" in reason
            or "score_weight" in reason
            or "mt5_strategy_buy_candidate_gap" in reason
        ):
            blockers.append(reason)

    status = "adoptable" if not blockers else "not_ready"
    return {
        "status": status,
        "candidate_labels": [row.get("label") for row in candidates],
        "aggregate_only_labels": [row.get("label") for row in aggregate_only],
        "candidate_sides": candidate_sides,
        "blockers": list(dict.fromkeys(blockers)),
    }


def operator_decision_summary(
    *,
    adoption: dict[str, Any],
    back_forward_decision: dict[str, Any],
    source_time_refresh_plan: dict[str, Any],
    buy_candidate_gap_plan: dict[str, Any],
) -> dict[str, Any]:
    blockers = (
        adoption.get("blockers") if isinstance(adoption.get("blockers"), list) else []
    )
    back_status = str(back_forward_decision.get("status") or "")
    source_time_status = str(source_time_refresh_plan.get("status") or "")
    buy_gap_status = str(buy_candidate_gap_plan.get("status") or "")

    base = {
        "adoptable": False,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "back_forward_status": back_status,
        "source_time_refresh_status": source_time_status,
        "buy_candidate_gap_status": buy_gap_status,
        "command_text": "",
        "follow_up_command_text": "",
    }
    if adoption.get("status") == "adoptable" and not blockers:
        return {
            **base,
            "status": "adoptable",
            "verdict": "ADOPTABLE",
            "adoptable": True,
            "primary_blocker": "",
            "primary_reason": "Promotion, Back/Forward, BUY/SELL candidate, and source-time evidence are ready.",
            "next_action": "use_strategy_tester_evidence_for_promotion_gate",
            "summary": "Adoptable based on current Strategy Tester analysis evidence.",
        }

    if back_status == "collect_ready":
        return {
            **base,
            "status": "collect_ready",
            "verdict": "COLLECT_RESULTS",
            "primary_blocker": "mt5_back_forward_collect_ready",
            "primary_reason": str(back_forward_decision.get("reason") or ""),
            "next_action": str(back_forward_decision.get("next_action") or ""),
            "command_text": str(back_forward_decision.get("collect_command_text") or ""),
            "summary": "Back/Forward reports appear ready; collect MT5 results before judging adoption.",
        }
    if back_status == "run_manual_back_forward":
        return {
            **base,
            "status": "not_ready",
            "verdict": "RUN_BACK_FORWARD",
            "primary_blocker": "mt5_back_forward_not_executed",
            "primary_reason": str(back_forward_decision.get("reason") or ""),
            "next_action": str(back_forward_decision.get("next_action") or ""),
            "command_text": str(back_forward_decision.get("collect_command_text") or ""),
            "summary": "Not adoptable yet: run Backtest and Forward in MT5 Strategy Tester, then collect results.",
        }
    if back_status == "sample_shortage":
        return {
            **base,
            "status": "sample_shortage",
            "verdict": "EXTEND_BACK_FORWARD_WINDOW",
            "primary_blocker": "mt5_back_forward_sample_shortage",
            "primary_reason": str(back_forward_decision.get("reason") or ""),
            "next_action": str(back_forward_decision.get("next_action") or ""),
            "command_text": str(
                back_forward_decision.get("sample_shortage_recovery_command_text")
                or back_forward_decision.get("collect_command_text")
                or ""
            ),
            "summary": "Back/Forward evidence is sample-short; extend the test window before adoption.",
        }
    if back_status in {"forward_regression", "forward_below_break_even"}:
        return {
            **base,
            "status": "reject_or_refit",
            "verdict": "REJECT_OR_REFIT",
            "primary_blocker": f"mt5_back_forward_{back_status}",
            "primary_reason": str(back_forward_decision.get("reason") or ""),
            "next_action": str(back_forward_decision.get("next_action") or ""),
            "command_text": "",
            "summary": "Do not adopt: Forward evidence degraded or fell below break-even.",
        }
    if source_time_status == "needs_refresh":
        return {
            **base,
            "status": "not_ready",
            "verdict": "REFRESH_SOURCE_TIME",
            "primary_blocker": "candidate_source_time_needs_refresh",
            "primary_reason": "Candidate Strategy Tester evidence has stale, missing, or mismatched source-time files.",
            "next_action": "refresh_mt5_strategy_source_time_evidence",
            "command_text": str(
                source_time_refresh_plan.get("collect_execute_and_refresh_command_text")
                or source_time_refresh_plan.get("refresh_queue_command_text")
                or ""
            ),
            "follow_up_command_text": str(
                source_time_refresh_plan.get("refresh_analysis_command_text") or ""
            ),
            "summary": "Not adoptable yet: refresh candidate source-time evidence before trusting MT5 reports.",
        }
    if buy_gap_status == "needs_buy_diagnostic":
        return {
            **base,
            "status": "not_ready",
            "verdict": "RUN_BUY_DIAGNOSTIC",
            "primary_blocker": "buy_candidate_gap",
            "primary_reason": str(
                buy_candidate_gap_plan.get("reason") or "BUY candidate evidence is missing."
            ),
            "next_action": "refresh_mt5_buy_candidate_gap_evidence",
            "command_text": str(
                buy_candidate_gap_plan.get("collect_execute_and_refresh_command_text")
                or buy_candidate_gap_plan.get("refresh_queue_command_text")
                or ""
            ),
            "summary": "Not adoptable yet: collect BUY diagnostic evidence so SELL-only edge is not promoted.",
        }

    primary = str(blockers[0]) if blockers else "adoption_not_ready"
    return {
        **base,
        "status": "not_ready",
        "verdict": "NOT_READY",
        "primary_blocker": primary,
        "primary_reason": "Strategy Tester analysis still has adoption blockers.",
        "next_action": "resolve_strategy_tester_adoption_blockers",
        "summary": "Not adoptable yet: resolve remaining Strategy Tester analysis blockers.",
    }


def build_strategy_tester_analysis(
    workspace: Path,
    *,
    report_specs: list[OptimizationReportSpec] | None = None,
    min_pf: float = 1.2,
    min_avg_r: float = 0.0,
    min_stable_passes: int = 1,
    promotion_gate_path: str = DEFAULT_PROMOTION_GATE,
    spec_coverage_path: str = DEFAULT_SPEC_COVERAGE,
    back_forward_run_path: str = DEFAULT_BACK_FORWARD_RUN,
    tester_status_path: str = DEFAULT_TESTER_STATUS,
    manual_test_queue_path: str = DEFAULT_MANUAL_TEST_QUEUE,
    manual_test_queue_with_optimization_path: str = DEFAULT_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION,
) -> dict[str, Any]:
    specs = report_specs if report_specs is not None else list(DEFAULT_OPTIMIZATION_REPORTS)
    promotion_gate = summarize_promotion_gate(workspace, promotion_gate_path)
    spec_coverage = summarize_spec_coverage(workspace, spec_coverage_path)
    back_forward = summarize_back_forward_run(workspace, back_forward_run_path)
    tester_status = summarize_tester_status(workspace, tester_status_path)
    manual_test_queue = summarize_manual_test_queue(workspace, manual_test_queue_path)
    manual_test_queue_with_optimization = summarize_manual_test_queue(
        workspace,
        manual_test_queue_with_optimization_path,
    )
    apply_back_forward_manual_queue_collect_filter(
        back_forward,
        (manual_test_queue, manual_test_queue_with_optimization),
        back_forward_run_path=back_forward_run_path,
    )
    optimization_reports = [
        summarize_optimization_report(
            workspace,
            spec,
            min_pf=min_pf,
            min_avg_r=min_avg_r,
            min_stable_passes=min_stable_passes,
        )
        for spec in specs
    ]
    back_forward_decision = back_forward_decision_summary(back_forward)
    source_artifacts = summarize_source_artifacts(
        workspace,
        promotion_gate=promotion_gate,
        spec_coverage=spec_coverage,
        back_forward=back_forward,
        tester_status=tester_status,
        manual_test_queue=manual_test_queue,
        manual_test_queue_with_optimization=manual_test_queue_with_optimization,
    )
    adoption = adoption_summary(
        promotion_gate,
        back_forward,
        back_forward_decision,
        optimization_reports,
        spec_coverage,
    )
    source_time_refresh_plan = build_source_time_refresh_plan(
        optimization_reports,
        manual_test_queue_with_optimization,
    )
    buy_candidate_gap_plan = build_buy_candidate_gap_plan(
        optimization_reports,
        manual_test_queue_with_optimization,
    )
    operator_decision = operator_decision_summary(
        adoption=adoption,
        back_forward_decision=back_forward_decision,
        source_time_refresh_plan=source_time_refresh_plan,
        buy_candidate_gap_plan=buy_candidate_gap_plan,
    )
    summary_aliases = {
        "status": adoption.get("status", ""),
        "adoption_status": adoption.get("status", ""),
        "adoption_blockers": adoption.get("blockers", []),
        "adoption_blocker_count": len(adoption.get("blockers", [])),
        "operator_decision_status": operator_decision.get("status", ""),
        "operator_decision_verdict": operator_decision.get("verdict", ""),
        "operator_decision_adoptable": operator_decision.get("adoptable", ""),
        "operator_decision_primary_blocker": operator_decision.get("primary_blocker", ""),
        "operator_decision_next_action": operator_decision.get("next_action", ""),
        "operator_decision_command_text": operator_decision.get("command_text", ""),
        "candidate_labels": adoption.get("candidate_labels", []),
        "aggregate_only_labels": adoption.get("aggregate_only_labels", []),
        "candidate_sides": adoption.get("candidate_sides", []),
        "promotion_decision": promotion_gate.get("decision", ""),
        "promotion_generated_at": promotion_gate.get("generated_at", ""),
        "spec_coverage_generated_at": spec_coverage.get("generated_at", ""),
        "spec_coverage_not_complete_reason_count": spec_coverage.get(
            "not_complete_reason_count",
            "",
        ),
        "back_forward_evidence_state": back_forward.get("evidence_state", ""),
        "back_forward_performance_status": back_forward.get("performance_status", ""),
        "manual_collect_ready": back_forward.get("manual_collect_ready", ""),
        "manual_collect_status": back_forward.get("manual_collect_status", ""),
        "back_forward_decision_status": back_forward_decision.get("status", ""),
        "back_forward_decision_adoptable": back_forward_decision.get("adoptable", ""),
        "back_forward_decision_next_action": back_forward_decision.get("next_action", ""),
        "back_forward_decision_reason": back_forward_decision.get("reason", ""),
        "back_forward_decision_collect_command_text": back_forward_decision.get(
            "collect_command_text",
            "",
        ),
        "back_forward_decision_sample_shortage_recovery_command_text": (
            back_forward_decision.get("sample_shortage_recovery_command_text", "")
        ),
        "back_forward_decision_sample_shortage_recovery_range_strategy": (
            back_forward_decision.get("sample_shortage_recovery_range_strategy", "")
        ),
        "back_forward_decision_sample_shortage_recovery_suggested_from_date": (
            back_forward_decision.get("sample_shortage_recovery_suggested_from_date", "")
        ),
        "back_forward_decision_sample_shortage_recovery_suggested_to_date": (
            back_forward_decision.get("sample_shortage_recovery_suggested_to_date", "")
        ),
        "source_time_refresh_status": source_time_refresh_plan.get("status", ""),
        "source_time_issue_labels": source_time_refresh_plan.get("issue_labels", []),
        "source_time_candidate_issue_labels": source_time_refresh_plan.get(
            "candidate_issue_labels",
            [],
        ),
        "source_time_refresh_queue_command_text": source_time_refresh_plan.get(
            "refresh_queue_command_text",
            "",
        ),
        "source_time_collect_refresh_command_text": source_time_refresh_plan.get(
            "collect_execute_and_refresh_command_text",
            "",
        ),
        "source_time_refresh_analysis_command_text": source_time_refresh_plan.get(
            "refresh_analysis_command_text",
            "",
        ),
        "buy_candidate_gap_status": buy_candidate_gap_plan.get("status", ""),
        "buy_candidate_gap_diagnostic_labels": buy_candidate_gap_plan.get(
            "diagnostic_labels",
            [],
        ),
        "buy_candidate_gap_refresh_queue_command_text": buy_candidate_gap_plan.get(
            "refresh_queue_command_text",
            "",
        ),
        "buy_candidate_gap_collect_refresh_command_text": buy_candidate_gap_plan.get(
            "collect_execute_and_refresh_command_text",
            "",
        ),
    }
    return {
        "ok": True,
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        **summary_aliases,
        "workspace_root": str(workspace),
        "thresholds": {
            "min_pf": min_pf,
            "min_avg_r": min_avg_r,
            "min_stable_passes": min_stable_passes,
        },
        "promotion_gate": promotion_gate,
        "spec_coverage": spec_coverage,
        "back_forward_run": back_forward,
        "back_forward_decision": back_forward_decision,
        "tester_status": tester_status,
        "manual_test_queue": manual_test_queue,
        "manual_test_queue_with_optimization": manual_test_queue_with_optimization,
        "source_artifacts": source_artifacts,
        "optimization_report_specs": [asdict(spec) for spec in specs],
        "optimization_reports": optimization_reports,
        "source_time_refresh_plan": source_time_refresh_plan,
        "buy_candidate_gap_plan": buy_candidate_gap_plan,
        "operator_decision": operator_decision,
        "adoption": adoption,
    }


def fmt(value: Any, digits: int = 2) -> str:
    number = as_float(value)
    if number is None:
        return "-"
    return f"{number:.{digits}f}"


def fmt_int(value: Any) -> str:
    number = as_int(value)
    if number is None:
        return "-"
    return str(number)


def md_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|") or "-"


def truncate_text(value: Any, *, max_chars: int = 180) -> str:
    text = str(value if value is not None else "").replace("\n", " ").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def format_next_step(step: dict[str, Any]) -> str:
    if not step:
        return "-"
    fields = [
        f"{step.get('queue_id', '-')}/{step.get('step_label', '-')}",
        f"{step.get('symbol', '-')}",
        f"{step.get('period', '-')}",
        f"{step.get('dates', '-')}",
        f"Forward={step.get('forward', '-')}",
        f"Inputs={step.get('inputs', '-')}",
        f"Report={step.get('report', '-')}",
    ]
    return ", ".join(fields)


def format_queue_step(row: dict[str, Any]) -> str:
    return f"{row.get('queue_id', '-')}/{row.get('step_label', '-')}"


def format_operation_card_rows(cards: Any) -> list[str]:
    if not isinstance(cards, list) or not cards:
        return ["| - | - | - | - | - | - | - | - | - | - |"]
    rows: list[str] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        rows.append(
            "| "
            + " | ".join(
                [
                    "next" if card.get("is_next") else "",
                    fmt_int(card.get("order")),
                    md_cell(card.get("action")),
                    md_cell(card.get("purpose")),
                    md_cell(format_queue_step(card)),
                    md_cell(card.get("forward")),
                    md_cell(card.get("optimization_label") or card.get("optimization")),
                    md_cell(card.get("inputs")),
                    md_cell(card.get("report")),
                    md_cell(card.get("collect_status")),
                ]
            )
            + " |"
        )
    return rows or ["| - | - | - | - | - | - | - | - | - | - |"]


def format_checklist_rows(checklist: Any) -> list[str]:
    if not isinstance(checklist, list) or not checklist:
        return ["| [ ] | - | - | - | - | - | - | - | - | - | - |"]
    rows: list[str] = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        rows.append(
            "| "
            + " | ".join(
                [
                    "[ ]",
                    fmt_int(item.get("order")),
                    md_cell(format_queue_step(item)),
                    md_cell(item.get("symbol")),
                    md_cell(item.get("period")),
                    md_cell(item.get("dates")),
                    md_cell(item.get("forward")),
                    md_cell(item.get("optimization_label") or item.get("optimization")),
                    md_cell(item.get("inputs")),
                    md_cell(item.get("report")),
                    md_cell(item.get("step_report_status")),
                ]
            )
            + " |"
        )
    return rows or ["| [ ] | - | - | - | - | - | - | - | - | - | - |"]


def format_launch_command_rows(checklist: Any) -> list[str]:
    if not isinstance(checklist, list) or not checklist:
        return ["| - | - | - | - | - |"]
    rows: list[str] = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        command = str(item.get("launch_command_text") or "")
        reason = str(item.get("direct_config_reason") or item.get("launch_error") or "")
        kind = str(item.get("launch_command_kind") or "")
        if not command:
            command = f"launch unavailable: {item.get('launch_error', '')}".strip()
        if kind == "runner_execute":
            command = f"runner execute: {command}"
        rows.append(
            "| "
            + " | ".join(
                [
                    fmt_int(item.get("order")),
                    md_cell(format_queue_step(item)),
                    md_cell(kind or "-"),
                    md_cell(reason or "-"),
                    f"`{md_cell(command)}`",
                ]
            )
            + " |"
        )
    return rows or ["| - | - | - | - | - |"]


def format_collect_command_rows(cards: Any) -> list[str]:
    if not isinstance(cards, list) or not cards:
        return ["| - | - | - | - |"]
    rows: list[str] = []
    seen: set[str] = set()
    for card in cards:
        if not isinstance(card, dict):
            continue
        queue_id = str(card.get("queue_id") or "")
        if not queue_id or queue_id in seen:
            continue
        seen.add(queue_id)
        command = str(card.get("collect_command_text") or "")
        if not command:
            command = "-"
        rows.append(
            "| "
            + " | ".join(
                [
                    fmt_int(card.get("order")),
                    md_cell(queue_id),
                    md_cell(card.get("collect_status")),
                    f"`{md_cell(command)}`" if command != "-" else "-",
                ]
            )
            + " |"
        )
    return rows or ["| - | - | - | - |"]


def compact_sequence(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "-"
    return ", ".join(str(item) for item in value)


def format_handoff_lines(handoff: Any) -> list[str]:
    if not isinstance(handoff, dict) or not handoff:
        return ["- Handoff: -"]

    lines = [
        f"- Handoff state: {handoff.get('state', '-')}",
        f"- Handoff collect ready: {handoff.get('collect_ready', '-')}",
        f"- Handoff ready entries: {compact_sequence(handoff.get('ready_entry_ids'))}",
        f"- Handoff waiting entries: {compact_sequence(handoff.get('waiting_entry_ids'))}",
    ]
    command_fields = [
        ("Collect dry-run command", "dry_run_command_text"),
        ("Collect execute command", "execute_command_text"),
        ("Collect execute + analysis command", "execute_and_refresh_analysis_command_text"),
        ("Collect execute + full analysis command", "execute_and_refresh_all_command_text"),
    ]
    for label, key in command_fields:
        command = handoff.get(key)
        if command:
            lines.append(f"- {label}: `{command}`")
    return lines


def format_manual_queue_section(title: str, manual_queue: dict[str, Any]) -> list[str]:
    if not manual_queue.get("exists"):
        return [
            "",
            f"## {title}",
            "",
            f"- Queue status: {manual_queue.get('status', 'missing')}",
        ]
    static_configs = manual_queue.get("static_strategy_configs")
    if not isinstance(static_configs, list):
        static_configs = []
    static_candidate_labels = manual_queue.get("static_candidate_labels")
    if not isinstance(static_candidate_labels, list):
        static_candidate_labels = []
    summary_lines = [
        "",
        f"## {title}",
        "",
        f"- Queue generated at: {manual_queue.get('generated_at', '-')}",
        f"- Queue status: {manual_queue.get('status', '-')}",
        f"- Queue next action: {manual_queue.get('next_action', '-')}",
        (
            "- Entries/steps: "
            f"{fmt_int(manual_queue.get('entry_count'))}/"
            f"{fmt_int(manual_queue.get('step_count'))}, "
            f"waiting={fmt_int(manual_queue.get('waiting_count'))}, "
            f"ready={fmt_int(manual_queue.get('ready_to_collect_count'))}"
        ),
        f"- Queue next MT5 step: {format_next_step(manual_queue.get('next_launch_step', {}))}",
        *format_handoff_lines(manual_queue.get("operator_handoff")),
    ]
    if static_configs:
        summary_lines.append(f"- Static configs: {compact_sequence(static_configs)}")
    if static_candidate_labels:
        summary_lines.append(
            f"- Static candidate labels: {compact_sequence(static_candidate_labels)}"
        )
    return [
        *summary_lines,
        "",
        "### Operation Cards",
        "",
        "| next | order | action | purpose | queue/step | forward | optimization | inputs | report | collect status |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
        *format_operation_card_rows(manual_queue.get("operation_cards")),
        "",
        "### Manual Execution Checklist",
        "",
        "| done | order | queue/step | symbol | period | dates | forward | optimization | inputs | report | report status |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *format_checklist_rows(manual_queue.get("execution_checklist")),
        "",
        "### MT5 Launch Commands",
        "",
        "- `direct_config` runs MT5 with the prepared Tester config. `runner_execute` must be run as the shown Python command because it applies runtime date/report overrides before collection.",
        "",
        "| order | queue/step | kind | reason | command |",
        "| ---: | --- | --- | --- | --- |",
        *format_launch_command_rows(manual_queue.get("execution_checklist")),
        "",
        "### Entry Collect Commands",
        "",
        "| first order | entry | collect status | command |",
        "| ---: | --- | --- | --- |",
        *format_collect_command_rows(manual_queue.get("operation_cards")),
    ]


def format_coverage_next_action_rows(actions: Any) -> list[str]:
    if not isinstance(actions, list) or not actions:
        return ["| - | - | - | - |"]

    rows: list[str] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        manual_steps = action.get("manual_steps") if isinstance(action.get("manual_steps"), list) else []
        first_step = manual_steps[0] if manual_steps else action.get("next_action") or action.get("reason") or ""
        rows.append(
            "| "
            + " | ".join(
                [
                    fmt_int(action.get("priority")),
                    md_cell(action.get("id") or action.get("title") or "-"),
                    md_cell(truncate_text(first_step)),
                    fmt_int(len(manual_steps)),
                ]
            )
            + " |"
        )
    return rows or ["| - | - | - | - |"]


def format_source_artifact_rows(artifacts: Any) -> list[str]:
    if not isinstance(artifacts, list) or not artifacts:
        return ["| - | - | - | - | - | - |"]

    rows: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        rows.append(
            "| "
            + " | ".join(
                [
                    md_cell(artifact.get("label")),
                    md_cell(artifact.get("path")),
                    md_cell(artifact.get("generated_at")),
                    md_cell(artifact.get("state")),
                    md_cell(artifact.get("exists")),
                    md_cell(artifact.get("mtime_age_seconds")),
                ]
            )
            + " |"
        )
    return rows or ["| - | - | - | - | - | - |"]


def source_artifact_by_label(payload: dict[str, Any], label: str) -> dict[str, Any]:
    artifacts = payload.get("source_artifacts") if isinstance(payload.get("source_artifacts"), list) else []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        if str(artifact.get("label") or "") == label:
            return artifact
    return {}


def format_source_artifact_summary(artifact: dict[str, Any]) -> str:
    if not artifact:
        return "-"
    return (
        f"generated_at={artifact.get('generated_at', '-')}, "
        f"state={artifact.get('state', '-')}, "
        f"path={artifact.get('path', '-')}"
    )


def format_source_time_range(source_time: Any, *, expected: bool) -> str:
    if not isinstance(source_time, dict):
        return "-"
    if expected:
        start = source_time.get("expected_from_date") or ""
        end = source_time.get("expected_to_date") or ""
    else:
        start = source_time.get("actual_first_server_time") or ""
        end = source_time.get("actual_last_server_time") or ""
    if not start and not end:
        return "-"
    return f"{start} -> {end}"


def format_source_file_examples(source_files: Any) -> str:
    if not isinstance(source_files, dict):
        return "-"
    examples = source_files.get("examples")
    if not isinstance(examples, list) or not examples:
        return "-"
    parts: list[str] = []
    for example in examples[:3]:
        if not isinstance(example, dict):
            continue
        path = str(example.get("path") or "-")
        reason = str(example.get("reason") or "-")
        parts.append(f"{path}: {reason}")
    return "; ".join(parts) if parts else "-"


def format_source_file_issue_rows(reports: Any) -> list[str]:
    if not isinstance(reports, list):
        return []
    rows: list[str] = []
    for report in reports:
        if not isinstance(report, dict):
            continue
        source_files = report.get("source_files") if isinstance(report.get("source_files"), dict) else {}
        status = str(source_files.get("status") or "")
        if status in {"", "current", "archived", "not_reported"}:
            continue
        rows.append(
            "| "
            + " | ".join(
                [
                    md_cell(report.get("label")),
                    md_cell(report.get("side")),
                    md_cell(report.get("window")),
                    md_cell(status),
                    fmt_int(source_files.get("checked")),
                    fmt_int(source_files.get("stale")),
                    fmt_int(source_files.get("missing")),
                    md_cell(format_source_file_examples(source_files)),
                ]
            )
            + " |"
        )
    return rows


def format_source_time_refresh_rows(plan: Any) -> list[str]:
    if not isinstance(plan, dict):
        return ["| - | - | - | - | - | - | - | - | - | - |"]
    entries = plan.get("entries") if isinstance(plan.get("entries"), list) else []
    if not entries:
        return ["| - | - | - | - | - | - | - | - | - | - |"]
    rows: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        queue_step = f"{entry.get('queue_id', '-')}/{entry.get('step_label', '-')}"
        source_files = (
            f"{entry.get('source_file_status', '-')}, "
            f"checked={fmt_int(entry.get('source_file_checked'))}, "
            f"stale={fmt_int(entry.get('source_file_stale'))}, "
            f"missing={fmt_int(entry.get('source_file_missing'))}"
        )
        collect = str(entry.get("collect_command_text") or "")
        launch_kind = str(entry.get("launch_command_kind") or "-")
        rows.append(
            "| "
            + " | ".join(
                [
                    md_cell(entry.get("label")),
                    md_cell(entry.get("candidate")),
                    md_cell(entry.get("issue")),
                    md_cell(source_files),
                    md_cell(queue_step),
                    md_cell(entry.get("dates")),
                    md_cell(entry.get("forward")),
                    md_cell(entry.get("inputs")),
                    md_cell(entry.get("report")),
                    md_cell(launch_kind if collect else f"{launch_kind}; collect pending"),
                ]
            )
            + " |"
        )
    return rows or ["| - | - | - | - | - | - | - | - | - | - |"]


def format_buy_candidate_gap_rows(plan: Any) -> list[str]:
    if not isinstance(plan, dict):
        return ["| - | - | - | - | - | - | - | - | - | - | - | - | - |"]
    entries = plan.get("entries") if isinstance(plan.get("entries"), list) else []
    if not entries:
        return ["| - | - | - | - | - | - | - | - | - | - | - | - | - |"]
    rows: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        queue_step = f"{entry.get('queue_id', '-')}/{entry.get('step_label', '-')}"
        source_files = (
            f"{entry.get('source_file_status', '-')}, "
            f"{fmt_int(entry.get('source_file_checked'))}/"
            f"{fmt_int(entry.get('source_file_stale'))}/"
            f"{fmt_int(entry.get('source_file_missing'))}"
        )
        rows.append(
            "| "
            + " | ".join(
                [
                    md_cell(entry.get("label")),
                    md_cell(entry.get("status")),
                    md_cell(entry.get("window")),
                    fmt_int(entry.get("closed")),
                    fmt(entry.get("pf"), 2),
                    fmt(entry.get("avg_price_r"), 3),
                    fmt_int(entry.get("stable_forward_back_positive")),
                    md_cell(entry.get("source_time_status")),
                    md_cell(source_files),
                    md_cell(queue_step),
                    md_cell(entry.get("dates")),
                    md_cell(entry.get("inputs")),
                    md_cell(entry.get("report")),
                ]
            )
            + " |"
        )
    return rows or ["| - | - | - | - | - | - | - | - | - | - | - | - | - |"]


def format_metric_pair(back_forward_decision: Any, key: str) -> str:
    if not isinstance(back_forward_decision, dict):
        return "-"
    backtest = back_forward_decision.get("backtest")
    forward = back_forward_decision.get("forward")
    if not isinstance(backtest, dict):
        backtest = {}
    if not isinstance(forward, dict):
        forward = {}
    left = backtest.get(key, "")
    right = forward.get(key, "")
    if left in (None, "") and right in (None, ""):
        return "-"
    return f"{left if left not in (None, '') else '-'} / {right if right not in (None, '') else '-'}"


def format_back_forward_thresholds(back_forward_decision: Any) -> str:
    if not isinstance(back_forward_decision, dict):
        return "-"
    thresholds = back_forward_decision.get("thresholds")
    if not isinstance(thresholds, dict) or not thresholds:
        return "-"
    parts = []
    for key in ("min_closed", "break_even_pf", "break_even_avg_r", "degraded_pf_delta", "degraded_avg_r_delta"):
        if key in thresholds:
            parts.append(f"{key}={thresholds.get(key)}")
    return ", ".join(parts) if parts else "-"


def format_markdown(payload: dict[str, Any]) -> str:
    promotion = payload.get("promotion_gate", {})
    back_forward = payload.get("back_forward_run", {})
    back_forward_decision = payload.get("back_forward_decision", {})
    tester_status = payload.get("tester_status", {})
    manual_queue = payload.get("manual_test_queue", {})
    manual_queue_with_optimization = payload.get("manual_test_queue_with_optimization", {})
    adoption = payload.get("adoption", {})
    operator_decision = (
        payload.get("operator_decision")
        if isinstance(payload.get("operator_decision"), dict)
        else {}
    )
    promotion_artifact = source_artifact_by_label(payload, "promotion_gate")
    spec_coverage_artifact = source_artifact_by_label(payload, "spec_coverage")

    lines = [
        "# MT5 Strategy Tester Analysis",
        "",
        f"- Generated at: {payload.get('generated_at', '-')}",
        f"- Promotion decision: {promotion.get('decision', '-')}",
        f"- Promotion Gate source: {format_source_artifact_summary(promotion_artifact)}",
        f"- Spec Coverage source: {format_source_artifact_summary(spec_coverage_artifact)}",
        f"- Adoption status: {adoption.get('status', '-')}",
        f"- Back/Forward evidence: {back_forward.get('evidence_state', '-')} / {back_forward.get('performance_status', '-')}",
        f"- Operator handoff: {tester_status.get('handoff_state', '-')} / {tester_status.get('recommended_path', '-')}",
        f"- Next MT5 step: {format_next_step(tester_status.get('next_mt5_step', {}))}",
        (
            "- Refresh analysis command: "
            "`python3 methods/swing_eval/analysis/mt5_strategy_tester_analysis.py "
            "--output-json runtime/latest_mt5_strategy_tester_analysis.json "
            "--output-md runtime/latest_mt5_strategy_tester_analysis.md`"
        ),
        "",
        "## Operator Decision",
        "",
        f"- Verdict: {operator_decision.get('verdict', '-')}",
        f"- Status: {operator_decision.get('status', '-')}",
        f"- Adoptable: {operator_decision.get('adoptable', '-')}",
        f"- Primary blocker: {operator_decision.get('primary_blocker', '-')}",
        f"- Reason: {operator_decision.get('primary_reason', '-')}",
        f"- Next action: {operator_decision.get('next_action', '-')}",
        f"- Summary: {operator_decision.get('summary', '-')}",
    ]
    if operator_decision.get("command_text"):
        lines.append(f"- Command: `{operator_decision.get('command_text')}`")
    if operator_decision.get("follow_up_command_text"):
        lines.append(f"- Follow-up: `{operator_decision.get('follow_up_command_text')}`")
    lines.extend(
        [
            "",
        "## Source Artifacts",
        "",
        "| label | path | generated | state | exists | mtime age sec |",
        "| --- | --- | --- | --- | --- | ---: |",
        *format_source_artifact_rows(payload.get("source_artifacts")),
        "",
        "## Optimization Evidence",
        "",
        "| label | side | window | status | source time | expected | actual | closed | PF | avg R | net | XML back | XML forward | stable F+/B+ | F+/B- | source |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in payload.get("optimization_reports", []):
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        xml = row.get("tester_xml") if isinstance(row.get("tester_xml"), dict) else {}
        source_time = row.get("source_time") if isinstance(row.get("source_time"), dict) else {}
        lines.append(
            "| "
            + " | ".join(
                [
                    md_cell(row.get("label")),
                    md_cell(row.get("side")),
                    md_cell(row.get("window")),
                    md_cell(row.get("status")),
                    md_cell(source_time.get("status")),
                    md_cell(format_source_time_range(source_time, expected=True)),
                    md_cell(format_source_time_range(source_time, expected=False)),
                    fmt_int(metrics.get("closed")),
                    fmt(metrics.get("pf"), 2),
                    fmt(metrics.get("avg_price_r"), 3),
                    fmt(metrics.get("net_profit"), 2),
                    fmt_int(xml.get("back_rows")),
                    fmt_int(xml.get("forward_rows")),
                    fmt_int(xml.get("stable_forward_positive_back_positive")),
                    fmt_int(xml.get("forward_positive_back_negative")),
                    md_cell(row.get("path")),
                ]
            )
            + " |"
        )

    source_file_issue_rows = format_source_file_issue_rows(payload.get("optimization_reports"))
    if source_file_issue_rows:
        lines.extend(
            [
                "",
                "## Optimization Source File Issues",
                "",
                "| label | side | window | source file status | checked | stale | missing | examples |",
                "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
                *source_file_issue_rows,
            ]
        )

    source_time_refresh_plan = payload.get("source_time_refresh_plan")
    if isinstance(source_time_refresh_plan, dict) and source_time_refresh_plan.get("status") == "needs_refresh":
        lines.extend(
            [
                "",
                "## Source-Time Refresh Plan",
                "",
                f"- Status: {source_time_refresh_plan.get('status', '-')}",
                f"- Issue labels: {compact_sequence(source_time_refresh_plan.get('issue_labels'))}",
                (
                    "- Candidate issue labels: "
                    + compact_sequence(source_time_refresh_plan.get("candidate_issue_labels"))
                ),
                (
                    "- Refresh queue command: "
                    f"`{source_time_refresh_plan.get('refresh_queue_command_text', '-')}`"
                ),
                (
                    "- Dry-run launch command: "
                    f"`{source_time_refresh_plan.get('dry_run_launch_command_text', '-')}`"
                ),
                (
                    "- Collect + refresh command: "
                    f"`{source_time_refresh_plan.get('collect_execute_and_refresh_command_text', '-')}`"
                ),
                (
                    "- Refresh analysis command: "
                    f"`{source_time_refresh_plan.get('refresh_analysis_command_text', '-')}`"
                ),
                "",
                "| label | candidate | issue | source files | queue/step | dates | forward | inputs | report | launch/collect |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                *format_source_time_refresh_rows(source_time_refresh_plan),
            ]
        )

    buy_gap_plan = payload.get("buy_candidate_gap_plan")
    if isinstance(buy_gap_plan, dict) and buy_gap_plan.get("status") == "needs_buy_diagnostic":
        lines.extend(
            [
                "",
                "## BUY Candidate Gap Plan",
                "",
                f"- Status: {buy_gap_plan.get('status', '-')}",
                f"- Reason: {buy_gap_plan.get('reason', '-')}",
                f"- Diagnostic labels: {compact_sequence(buy_gap_plan.get('diagnostic_labels'))}",
                (
                    "- Refresh queue command: "
                    f"`{buy_gap_plan.get('refresh_queue_command_text', '-')}`"
                ),
                (
                    "- Dry-run launch command: "
                    f"`{buy_gap_plan.get('dry_run_launch_command_text', '-')}`"
                ),
                (
                    "- Collect + refresh command: "
                    f"`{buy_gap_plan.get('collect_execute_and_refresh_command_text', '-')}`"
                ),
                "",
                "| label | status | window | closed | PF | avg R | stable F+/B+ | source time | source files checked/stale/missing | queue/step | dates | inputs | report |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- |",
                *format_buy_candidate_gap_rows(buy_gap_plan),
            ]
        )

    lines.extend(
        [
            "",
            "## Back/Forward",
            "",
            f"- Evidence state: {back_forward.get('evidence_state', '-')}",
            f"- Performance status: {back_forward.get('performance_status', '-')}",
            f"- Decision status: {back_forward_decision.get('status', '-')}",
            f"- Decision adoptable: {back_forward_decision.get('adoptable', '-')}",
            f"- Decision next action: {back_forward_decision.get('next_action', '-')}",
            f"- Decision reason: {back_forward_decision.get('reason', '-')}",
            f"- Thresholds: {format_back_forward_thresholds(back_forward_decision)}",
            f"- Trades back/forward: {format_metric_pair(back_forward_decision, 'trades')}",
            f"- PF back/forward: {format_metric_pair(back_forward_decision, 'pf')}",
            f"- Avg R back/forward: {format_metric_pair(back_forward_decision, 'avg_r')}",
            f"- Forward PF delta vs backtest: {back_forward_decision.get('forward_pf_delta_vs_backtest', '-')}",
            f"- Forward Avg R delta vs backtest: {back_forward_decision.get('forward_avg_r_delta_vs_backtest', '-')}",
            f"- Manual collect status: {back_forward.get('manual_collect_status', '-')}",
            f"- Manual collect ready: {back_forward.get('manual_collect_ready', False)}",
        ]
    )
    sample_shortage_recovery = (
        back_forward_decision.get("sample_shortage_recovery")
        if isinstance(back_forward_decision.get("sample_shortage_recovery"), dict)
        else {}
    )
    if sample_shortage_recovery:
        lines.extend(
            [
                (
                    "- Sample shortage recovery: "
                    f"strategy={sample_shortage_recovery.get('strategy', '-')}, "
                    f"range={sample_shortage_recovery.get('current_from_date', '')}"
                    f"..{sample_shortage_recovery.get('current_to_date', '')} -> "
                    f"{sample_shortage_recovery.get('suggested_from_date', '')}"
                    f"..{sample_shortage_recovery.get('suggested_to_date', '')}, "
                    f"range_strategy={sample_shortage_recovery.get('range_strategy', '-')}"
                ),
                (
                    "- Extended Back/Forward command: "
                    f"`{sample_shortage_recovery.get('command_text', '-')}`"
                ),
            ]
        )
    collect_command = back_forward.get("recommended_collect_only_command_text")
    if collect_command:
        lines.append(f"- Collect-only command: `{collect_command}`")
    status_collect_command = tester_status.get("manual_collect_execute_command_text")
    if status_collect_command:
        lines.append(f"- Queue collect command: `{status_collect_command}`")
    status_collect_analysis_command = tester_status.get(
        "manual_collect_execute_and_refresh_analysis_command_text"
    )
    if status_collect_analysis_command:
        lines.append(f"- Queue collect + analysis command: `{status_collect_analysis_command}`")
    blockers = back_forward.get("manual_collect_blocking_reasons")
    if blockers:
        lines.append(f"- Manual collect blockers: {', '.join(str(item) for item in blockers)}")

    lines.extend(format_manual_queue_section("MT5 Manual Queue", manual_queue))
    lines.extend(
        format_manual_queue_section(
            "MT5 Manual Queue With Optimization",
            manual_queue_with_optimization,
        )
    )

    lines.extend(["", "## Interpretation", ""])
    if adoption.get("candidate_labels"):
        lines.append(f"- Candidate reports: {', '.join(str(item) for item in adoption['candidate_labels'])}")
    if adoption.get("aggregate_only_labels"):
        lines.append(
            "- Aggregate-only reports: "
            + ", ".join(str(item) for item in adoption["aggregate_only_labels"])
            + " (PF/avg R is positive, but stable back/forward pass evidence is insufficient.)"
        )
    if adoption.get("blockers"):
        lines.append("- Adoption blockers: " + ", ".join(str(item) for item in adoption["blockers"]))
    else:
        lines.append("- No adoption blockers detected by this report.")
    if back_forward.get("evidence_state") == "plan_only":
        lines.append("- Back/Forward runner is still plan-only; run Backtest and Forward in MT5, then collect results.")
    if tester_status.get("bridge_required_for_standalone_tester") is False and tester_status.get("bridge_note"):
        lines.append(f"- {tester_status.get('bridge_note')}")

    reasons = payload.get("spec_coverage", {}).get("not_complete_reasons", [])
    lines.extend(["", "## Coverage Blockers", ""])
    if reasons:
        for reason in reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- None")

    next_actions = payload.get("spec_coverage", {}).get("next_actions", [])
    lines.extend(
        [
            "",
            "## Coverage Next Actions",
            "",
            "| priority | id | first manual step | steps |",
            "| ---: | --- | --- | ---: |",
            *format_coverage_next_action_rows(next_actions),
        ]
    )

    return "\n".join(lines) + "\n"


def parse_report_spec(text: str) -> OptimizationReportSpec:
    parts = [part.strip() for part in text.split(",", 3)]
    if len(parts) != 4 or not all(parts):
        raise argparse.ArgumentTypeError("report must be label,side,window,path")
    return OptimizationReportSpec(parts[0], parts[1].upper(), parts[2], parts[3])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize MT5 Strategy Tester Back/Forward and Optimization evidence."
    )
    parser.add_argument("--workspace", default=".", help="Workspace root.")
    parser.add_argument("--promotion-gate", default=DEFAULT_PROMOTION_GATE)
    parser.add_argument("--spec-coverage", default=DEFAULT_SPEC_COVERAGE)
    parser.add_argument("--back-forward-run", default=DEFAULT_BACK_FORWARD_RUN)
    parser.add_argument("--tester-status", default=DEFAULT_TESTER_STATUS)
    parser.add_argument("--manual-test-queue", default=DEFAULT_MANUAL_TEST_QUEUE)
    parser.add_argument(
        "--manual-test-queue-with-optimization",
        default=DEFAULT_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION,
    )
    parser.add_argument(
        "--report",
        action="append",
        type=parse_report_spec,
        help="Optimization report as label,side,window,path. May be repeated.",
    )
    parser.add_argument("--min-pf", type=float, default=1.2)
    parser.add_argument("--min-avg-r", type=float, default=0.0)
    parser.add_argument("--min-stable-passes", type=int, default=1)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace = Path(args.workspace).expanduser().resolve()
    payload = build_strategy_tester_analysis(
        workspace,
        report_specs=args.report,
        min_pf=args.min_pf,
        min_avg_r=args.min_avg_r,
        min_stable_passes=args.min_stable_passes,
        promotion_gate_path=args.promotion_gate,
        spec_coverage_path=args.spec_coverage,
        back_forward_run_path=args.back_forward_run,
        tester_status_path=args.tester_status,
        manual_test_queue_path=args.manual_test_queue,
        manual_test_queue_with_optimization_path=args.manual_test_queue_with_optimization,
    )

    output_json = workspace_path(workspace, args.output_json)
    output_md = workspace_path(workspace, args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    with output_json.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    output_md.write_text(format_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "output_json": compact_path(workspace, output_json),
                "output_md": compact_path(workspace, output_md),
                "adoption_status": payload["adoption"]["status"],
                "candidate_labels": payload["adoption"]["candidate_labels"],
                "blockers": payload["adoption"]["blockers"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
