from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.backtest import run_backtest
from analysis.dry_run_audit import build_audit
from analysis.dry_run_command import load_optional_json
from analysis.economic_calendar import load_economic_calendar, parse_currencies
from analysis.forward_test import read_records, summarize_forward
from analysis.market_data import TIME_FORMAT, load_history
from analysis.mt5_back_forward_run import back_forward_evidence_state, execution_condition_values_match
from analysis.mt5_optimization_recommend import estimate_set_passes
from analysis.mt5_tester_optimization_report import default_tester_root
from analysis.mt5_tester_run import RISK_PRESET_REQUIRED_INPUTS, validate_tester_risk_preset
from analysis.reports import summarize
from analysis.rr_experiment import DEFAULT_RR_VALUES, parse_rr_values, select_variable_rr_candidates
from analysis.candidate_generator import generate_candidates
from analysis.diagnostics import DEFAULT_THRESHOLDS, threshold_diagnostics


DEFAULT_WATCH_HEARTBEAT_MAX_AGE_SECONDS = 180.0
HISTORY_EXPECTED_BARS_PER_HOUR = {
    "M1": 60,
    "M5": 12,
    "M15": 4,
    "M30": 2,
}
HISTORY_MIN_TIMEFRAME_COVERAGE_RATIO = 0.98
MT5_BACK_FORWARD_SAMPLE_SHORTAGE_DEFAULT_FROM_DATE = "2025.01.01"
MT5_BACK_FORWARD_SAMPLE_SHORTAGE_DEFAULT_TO_DATE = "2025.12.31"
MT5_BACK_FORWARD_SAMPLE_SHORTAGE_MIN_EXTENDED_DAYS = 180
MT5_STRATEGY_TESTER_ANALYSIS_REFRESH_COMMAND_TEXT = (
    "python3 methods/swing_eval/analysis/mt5_strategy_tester_analysis.py "
    "--output-json runtime/latest_mt5_strategy_tester_analysis.json "
    "--output-md runtime/latest_mt5_strategy_tester_analysis.md"
)

MT5_BACK_FORWARD_WATCHER_CONDITION_KEYS = (
    "back_forward_run_execution_conditions",
    "back_forward_run_per_step_timeout_seconds",
    "back_forward_run_since_minutes",
    "back_forward_run_min_closed",
    "back_forward_run_from_date",
    "back_forward_run_to_date",
    "back_forward_run_forward_mode",
    "back_forward_run_sync_expert_parameters_set",
    "back_forward_run_allow_running_terminal",
    "back_forward_run_allow_stale_compile",
    "back_forward_run_allow_invalid_risk_preset",
)

MT5_BACK_FORWARD_WATCHER_PREFLIGHT_KEYS = (
    "back_forward_run_ready_status_ok",
    "back_forward_run_ready_status_reasons",
    "back_forward_run_ready_status_mismatches",
    "back_forward_run_ready_status_checked_step_keys",
    "back_forward_run_ready_status_checked_command_options",
    "back_forward_run_ready_status_checked_command_flags",
    "back_forward_run_ready_status_checked_execution_conditions",
    "back_forward_run_ready_status_expected_execution_conditions",
    "back_forward_run_ready_status_status_execution_conditions",
)

MT5_STATUS_WATCH_OPERATOR_ALIAS_KEYS = (
    "mt5_next_operator_action",
    "mt5_next_operator_mode",
    "mt5_next_operator_launch_state",
    "mt5_next_queue_step",
    "mt5_next_quick_input",
    "mt5_next_step_operator_summary",
    "mt5_next_step_collect_filter_summary",
    "mt5_next_manual_run_start_effective_after",
    "mt5_next_manual_run_start_effective_after_values",
    "mt5_auto_launch_command_available",
    "mt5_auto_launch_blocked",
    "mt5_auto_launch_blocked_reasons",
    "mt5_auto_launch_command_text",
    "mt5_auto_launch_note",
    "mt5_back_forward_quick_start_status",
    "mt5_back_forward_quick_start_collect_command_text",
    "mt5_strategy_operator_decision_status",
    "mt5_strategy_operator_decision_verdict",
    "mt5_strategy_operator_decision_primary_blocker",
    "mt5_strategy_operator_decision_next_action",
    "mt5_strategy_operator_decision_command_text",
    "mt5_collect_dry_run_command_text",
    "mt5_collect_execute_command_text",
    "mt5_manual_queue_status",
    "mt5_manual_queue_progress_state",
    "mt5_manual_queue_waiting_count",
    "mt5_manual_queue_step_launch_needed_count",
)


MT5_FORWARD_RISK_CHECK_NAMES = {
    "mt5_forward_risk_exposure",
    "mt5_forward_max_single_volume",
    "mt5_forward_max_concurrent_volume",
    "mt5_forward_max_concurrent_positions",
    "mt5_forward_daily_loss_stop_open_breaches",
    "mt5_forward_consecutive_loss_stop_open_breaches",
}
MT5_FORWARD_BUTTON_CHECK_NAMES = {
    "mt5_forward_button_dry_run_only",
}
MT5_FORWARD_SCHEMA_CHECK_NAMES = {
    "mt5_forward_csv_schema",
    "mt5_forward_entry_time_diagnostics",
    "mt5_forward_trend_diagnostics",
    "mt5_forward_execution_diagnostics",
}
MT5_FORWARD_SL_TP_CHECK_NAMES = {
    "mt5_forward_sl_tp_diagnostics",
}
MT5_FORWARD_DIAGNOSTIC_CHECK_NAMES = {
    "mt5_forward_diagnostic_warnings_clear",
}


def promotion_failed_check_names(checks: object) -> list[str]:
    if not isinstance(checks, list):
        return []
    return [
        str(check.get("name"))
        for check in checks
        if isinstance(check, dict) and check.get("passed") is not True
    ]


def promotion_check_summary(checks: object) -> dict[str, object]:
    check_rows = checks if isinstance(checks, list) else []
    failed_names = promotion_failed_check_names(check_rows)
    return {
        "check_count": len(check_rows),
        "failed": len(failed_names),
        "failed_checks": failed_names,
        "failed_check_names": failed_names,
    }


def mt5_strategy_tester_analysis_freshness(
    payload: object,
    *,
    current_promotion_generated_at: object = "",
) -> dict[str, object]:
    if not isinstance(payload, dict) or not payload:
        return {}
    promotion = payload.get("promotion_gate") if isinstance(payload.get("promotion_gate"), dict) else {}
    embedded_generated_at = str(promotion.get("generated_at") or "")
    embedded_decision = str(promotion.get("decision") or "")
    current_generated_at = str(current_promotion_generated_at or "")
    if embedded_generated_at and current_generated_at:
        current = embedded_generated_at == current_generated_at
        status = "current" if current else "stale"
    else:
        current = ""
        status = "unknown"
    return {
        "status": status,
        "current": current,
        "analysis_generated_at": payload.get("generated_at", ""),
        "embedded_promotion_generated_at": embedded_generated_at,
        "embedded_promotion_decision": embedded_decision,
        "current_promotion_generated_at": current_generated_at,
        "refresh_command_text": (
            MT5_STRATEGY_TESTER_ANALYSIS_REFRESH_COMMAND_TEXT
            if status in {"stale", "unknown"}
            else ""
        ),
    }


def evaluate_promotion_gate(
    *,
    history_path: str | Path = "runtime/latest_history_168h.json",
    calendar_path: str | Path | None = "runtime/economic_calendar.json",
    calendar_input_utc_offset: float | None = None,
    calendar_server_utc_offset: float | None = None,
    signal_path: str | Path = "runtime/latest_signal.json",
    command_path: str | Path = "runtime/trade_command.json",
    trade_result_path: str | Path = "runtime/latest_trade_result.json",
    forward_ledger_path: str | Path = "runtime/forward_tests.jsonl",
    forward_status_path: str | Path | None = "runtime/latest_forward_test_status.json",
    forward_status_watch_heartbeat_path: str | Path | None = "runtime/forward_status_watch_heartbeat.json",
    forward_test_watch_heartbeat_path: str | Path | None = "runtime/forward_test_watch_heartbeat.json",
    bridge_status_path: str | Path | None = "runtime/latest_bridge_status.json",
    mt5_forward_report_path: str | Path | None = "runtime/latest_mt5_forward_report.json",
    mt5_optimization_report_path: str | Path | None = "runtime/latest_mt5_optimization_report.json",
    mt5_optimization_recommendation_path: str | Path | None = "runtime/latest_mt5_optimization_recommendation.json",
    mt5_tester_run_report_path: str | Path | None = "runtime/latest_mt5_tester_run.json",
    mt5_tester_status_path: str | Path | None = "runtime/latest_mt5_tester_status.json",
    mt5_back_forward_run_path: str | Path | None = "runtime/latest_mt5_back_forward_run.json",
    mt5_strategy_tester_analysis_path: str | Path | None = (
        "runtime/latest_mt5_strategy_tester_analysis.json"
    ),
    mt5_stable_candidate_report_path: str | Path | None = (
        "runtime/latest_mt5_stable_candidate_optimization_report.json"
    ),
    mt5_stable_candidate_recommendation_path: str | Path | None = (
        "runtime/latest_mt5_stable_candidate_recommendation.json"
    ),
    mt5_stable_candidate_tester_run_report_path: str | Path | None = (
        "runtime/latest_mt5_tester_stable_candidate_run.json"
    ),
    mt5_buy_refit_recommendation_path: str | Path | None = "runtime/latest_mt5_buy_refit_recommendation.json",
    mt5_buy_entry_refit_recommendation_path: str | Path | None = "runtime/latest_mt5_buy_entry_refit_recommendation.json",
    mt5_sell_entry_refit_recommendation_path: str | Path | None = "runtime/latest_mt5_sell_entry_refit_recommendation.json",
    mt5_sell_regime_entry_refit_recommendation_path: str | Path | None = (
        "runtime/latest_mt5_sell_regime_entry_refit_recommendation.json"
    ),
    mt5_buy_hour03_validation_recommendation_path: str | Path | None = (
        "runtime/latest_mt5_buy_hour03_validation_recommendation.json"
    ),
    mt5_buy_hour03_wide_stop_validation_recommendation_path: str | Path | None = (
        "runtime/latest_mt5_buy_hour03_wide_stop_validation_recommendation.json"
    ),
    mt5_buy_hour03_wide_stop_calendar_validation_recommendation_path: str | Path | None = (
        "runtime/latest_mt5_buy_hour03_wide_stop_calendar_validation_recommendation.json"
    ),
    mt5_yearly_optimization_report_path: str | Path | None = "runtime/latest_mt5_2025_optimization_report.json",
    mt5_compile_status_path: str | Path | None = "runtime/latest_mt5_compile_status.json",
    winrate_fit_report_path: str | Path | None = "runtime/latest_winrate_fit.json",
    score_weight_search_report_path: str | Path | None = "runtime/latest_score_weight_search.json",
    score_weight_search_buy_report_path: str | Path | None = "runtime/latest_score_weight_search_168h_buy_rr4.json",
    score_weight_search_sell_report_path: str | Path | None = "runtime/latest_score_weight_search_168h_sell_rr4.json",
    score_weight_set_buy_report_path: str | Path | None = "runtime/latest_score_weight_set_168h_buy_rr4.json",
    score_weight_set_sell_report_path: str | Path | None = "runtime/latest_score_weight_set_168h_sell_rr4.json",
    risk_shape_weight_search_report_path: str | Path | None = "runtime/latest_risk_shape_weight_search.json",
    strategy: str = "side_ladder",
    rr_values: list[float] | None = None,
    fixed_rr: float = 4.0,
    min_score: float = 50.0,
    max_hold_minutes: int = 60,
    min_history_hours: int = 168,
    min_candidates: int = 100,
    min_avg_r: float = 0.0,
    min_pf: float = 1.2,
    max_drawdown_r: float = 0.0,
    min_expectancy_r: float | None = None,
    min_score_quality_threshold: float = 70.0,
    min_score_quality_count: int = 20,
    min_score_quality_avg_r: float = 0.0,
    min_score_quality_pf: float = 1.2,
    max_score_quality_avg_r_drop: float = 0.25,
    max_losing_streak_allowed: int = 20,
    min_side_count: int = 30,
    min_side_pf: float = 1.0,
    min_side_avg_r: float = 0.0,
    max_side_total_r_share: float = 0.85,
    require_dry_run_passed: bool = True,
    max_dry_run_age_seconds: int = 3600,
    min_dry_run_command_score: float = 50.0,
    require_forward: bool = True,
    min_forward_closed: int = 30,
    min_forward_avg_r: float = 0.0,
    min_forward_pf: float = 1.2,
    max_forward_drawdown_r: float = 0.0,
    min_forward_expectancy_r: float | None = None,
    min_forward_side_closed: int = 10,
    min_forward_side_pf: float = 1.0,
    min_forward_side_avg_r: float = 0.0,
    require_mt5_forward: bool = False,
    min_mt5_forward_closed: int = 30,
    min_mt5_forward_pf: float = 1.2,
    max_mt5_forward_losing_streak: int = 20,
    max_mt5_forward_drawdown_price_r: float = 0.0,
    min_mt5_forward_expectancy_price_r: float | None = None,
    min_mt5_forward_side_closed: int = 10,
    min_mt5_forward_side_pf: float = 1.0,
    min_mt5_forward_side_avg_price_r: float = 0.0,
    require_mt5_optimization: bool = False,
    min_mt5_optimization_closed: int = 100,
    min_mt5_optimization_pf: float = 1.2,
    max_mt5_optimization_drawdown_price_r: float = 0.0,
    min_mt5_optimization_expectancy_price_r: float | None = None,
    min_mt5_optimization_side_closed: int = 30,
    min_mt5_optimization_side_pf: float = 1.0,
    min_mt5_optimization_side_avg_price_r: float = 0.0,
    min_mt5_optimization_forward_pf: float = 1.2,
    min_mt5_optimization_forward_trades: int = 30,
    min_mt5_optimization_positive_forward_back: int = 1,
    require_mt5_yearly_optimization: bool = False,
    min_mt5_yearly_optimization_closed: int = 100,
    min_mt5_yearly_optimization_pf: float = 1.2,
    min_mt5_yearly_optimization_avg_price_r: float = 0.0,
    max_mt5_yearly_optimization_drawdown_price_r: float = 0.0,
    min_mt5_yearly_optimization_expectancy_price_r: float | None = None,
    min_mt5_yearly_optimization_positive_forward_back: int = 1,
    require_mt5_compile: bool = False,
    require_winrate_fit: bool = False,
    include_blackout_times: bool = False,
    news_before_minutes: int = 10,
    news_after_minutes: int = 10,
    news_min_impact: str = "high",
    news_currencies: tuple[str, ...] | list[str] | None = ("USD", "XAU", "ALL"),
) -> dict[str, object]:
    history = load_history(history_path)
    calendar_events = load_economic_calendar(
        calendar_path,
        input_utc_offset_hours=calendar_input_utc_offset,
        server_utc_offset_hours=calendar_server_utc_offset,
    )
    candidates = select_candidates_for_gate(
        history,
        strategy=strategy,
        rr_values=rr_values or list(DEFAULT_RR_VALUES),
        fixed_rr=fixed_rr,
        min_score=min_score,
        include_blackout_times=include_blackout_times,
        calendar_events=calendar_events,
        news_before_minutes=news_before_minutes,
        news_after_minutes=news_after_minutes,
        news_min_impact=news_min_impact,
        news_currencies=news_currencies,
    )
    results = run_backtest(
        candidates,
        history.bars("M1"),
        max_hold_minutes=max_hold_minutes,
        spread_price=history.spread_points * history.point,
    )
    summary = summarize(candidates, results)
    summary["thresholds"] = threshold_diagnostics(candidates, results, thresholds=DEFAULT_THRESHOLDS)
    score_calibration = score_calibration_diagnostics(
        summary,
        min_threshold=min_score_quality_threshold,
        min_count=min_score_quality_count,
    )
    audit = build_audit(
        signal=load_optional_json(signal_path),
        command=load_optional_json(command_path),
        trade_result=load_optional_json(trade_result_path),
        max_age_seconds=max_dry_run_age_seconds,
    )
    forward_records = read_records(forward_ledger_path)
    forward_summary = summarize_forward(forward_records)
    forward_status_summary = load_optional_json(forward_status_path) or {}
    forward_status_watch_heartbeat = load_watch_heartbeat(forward_status_watch_heartbeat_path)
    forward_test_watch_heartbeat = load_watch_heartbeat(forward_test_watch_heartbeat_path)
    bridge_status_summary = extract_bridge_status_summary(load_optional_json(bridge_status_path))
    mt5_forward_summary = extract_mt5_forward_summary(load_optional_json(mt5_forward_report_path))
    mt5_optimization_summary = extract_mt5_optimization_summary(load_optional_json(mt5_optimization_report_path))
    mt5_optimization_recommendation = extract_mt5_optimization_recommendation(
        load_optional_json(mt5_optimization_recommendation_path)
    )
    mt5_tester_run_summary = extract_mt5_tester_run_summary(load_optional_json(mt5_tester_run_report_path))
    mt5_tester_status_summary = extract_mt5_tester_status_summary(load_optional_json(mt5_tester_status_path))
    mt5_back_forward_run_summary = extract_mt5_back_forward_run_summary(load_optional_json(mt5_back_forward_run_path))
    mt5_strategy_tester_analysis = load_optional_json(mt5_strategy_tester_analysis_path) or {}
    mt5_stable_candidate_summary = extract_mt5_optimization_summary(
        load_optional_json(mt5_stable_candidate_report_path)
    )
    mt5_stable_candidate_recommendation = extract_mt5_optimization_recommendation(
        load_optional_json(mt5_stable_candidate_recommendation_path)
    )
    mt5_stable_candidate_tester_run_summary = extract_mt5_tester_run_summary(
        load_optional_json(mt5_stable_candidate_tester_run_report_path)
    )
    mt5_buy_refit_recommendation = extract_mt5_optimization_recommendation(
        load_optional_json(mt5_buy_refit_recommendation_path)
    )
    mt5_buy_entry_refit_recommendation = extract_mt5_optimization_recommendation(
        load_optional_json(mt5_buy_entry_refit_recommendation_path)
    )
    mt5_sell_entry_refit_recommendation = extract_mt5_optimization_recommendation(
        load_optional_json(mt5_sell_entry_refit_recommendation_path)
    )
    mt5_sell_regime_entry_refit_recommendation = extract_mt5_optimization_recommendation(
        load_optional_json(mt5_sell_regime_entry_refit_recommendation_path)
    )
    mt5_buy_hour03_validation_recommendation = extract_mt5_optimization_recommendation(
        load_optional_json(mt5_buy_hour03_validation_recommendation_path)
    )
    mt5_buy_hour03_wide_stop_validation_recommendation = extract_mt5_optimization_recommendation(
        load_optional_json(mt5_buy_hour03_wide_stop_validation_recommendation_path)
    )
    mt5_buy_hour03_wide_stop_calendar_validation_recommendation = extract_mt5_optimization_recommendation(
        load_optional_json(mt5_buy_hour03_wide_stop_calendar_validation_recommendation_path)
    )
    mt5_yearly_optimization_summary = extract_mt5_optimization_summary(
        load_optional_json(mt5_yearly_optimization_report_path)
    )
    mt5_compile_summary = extract_mt5_compile_summary(load_optional_json(mt5_compile_status_path))
    winrate_fit_summary = extract_winrate_fit_summary(load_optional_json(winrate_fit_report_path))
    score_weight_search_summary = extract_score_weight_search_summary(load_optional_json(score_weight_search_report_path))
    score_weight_search_by_side = {
        side: summary
        for side, summary in (
            ("buy", extract_score_weight_search_summary(load_optional_json(score_weight_search_buy_report_path))),
            ("sell", extract_score_weight_search_summary(load_optional_json(score_weight_search_sell_report_path))),
        )
        if summary
    }
    score_weight_set_by_side = {
        side: summary
        for side, summary in (
            ("buy", extract_score_weight_set_summary(load_optional_json(score_weight_set_buy_report_path))),
            ("sell", extract_score_weight_set_summary(load_optional_json(score_weight_set_sell_report_path))),
        )
        if summary
    }
    risk_shape_weight_search_summary = extract_score_weight_search_summary(
        load_optional_json(risk_shape_weight_search_report_path)
    )
    checks = promotion_checks(
        history_hours=history.history_hours,
        history_timeframes={
            timeframe: len(history.bars(timeframe))
            for timeframe in HISTORY_EXPECTED_BARS_PER_HOUR
        },
        summary=summary,
        audit=audit,
        forward_summary=forward_summary,
        mt5_forward_summary=mt5_forward_summary,
        mt5_optimization_summary=mt5_optimization_summary,
        mt5_optimization_recommendation_summary=mt5_optimization_recommendation,
        mt5_tester_run_summary=mt5_tester_run_summary,
        mt5_tester_status_summary=mt5_tester_status_summary,
        mt5_back_forward_run_summary=mt5_back_forward_run_summary,
        bridge_status_summary=bridge_status_summary,
        mt5_compile_summary=mt5_compile_summary,
        min_history_hours=min_history_hours,
        min_candidates=min_candidates,
        min_avg_r=min_avg_r,
        min_pf=min_pf,
        max_drawdown_r=max_drawdown_r,
        min_expectancy_r=min_expectancy_r,
        min_score_quality_threshold=min_score_quality_threshold,
        min_score_quality_count=min_score_quality_count,
        min_score_quality_avg_r=min_score_quality_avg_r,
        min_score_quality_pf=min_score_quality_pf,
        max_score_quality_avg_r_drop=max_score_quality_avg_r_drop,
        max_losing_streak_allowed=max_losing_streak_allowed,
        min_side_count=min_side_count,
        min_side_pf=min_side_pf,
        min_side_avg_r=min_side_avg_r,
        max_side_total_r_share=max_side_total_r_share,
        require_dry_run_passed=require_dry_run_passed,
        max_dry_run_age_seconds=max_dry_run_age_seconds,
        min_dry_run_command_score=min_score,
        require_forward=require_forward,
        min_forward_closed=min_forward_closed,
        min_forward_avg_r=min_forward_avg_r,
        min_forward_pf=min_forward_pf,
        max_forward_drawdown_r=max_forward_drawdown_r,
        min_forward_expectancy_r=min_forward_expectancy_r,
        min_forward_side_closed=min_forward_side_closed,
        min_forward_side_pf=min_forward_side_pf,
        min_forward_side_avg_r=min_forward_side_avg_r,
        require_mt5_forward=require_mt5_forward,
        min_mt5_forward_closed=min_mt5_forward_closed,
        min_mt5_forward_pf=min_mt5_forward_pf,
        max_mt5_forward_losing_streak=max_mt5_forward_losing_streak,
        max_mt5_forward_drawdown_price_r=max_mt5_forward_drawdown_price_r,
        min_mt5_forward_expectancy_price_r=min_mt5_forward_expectancy_price_r,
        min_mt5_forward_side_closed=min_mt5_forward_side_closed,
        min_mt5_forward_side_pf=min_mt5_forward_side_pf,
        min_mt5_forward_side_avg_price_r=min_mt5_forward_side_avg_price_r,
        require_mt5_optimization=require_mt5_optimization,
        min_mt5_optimization_closed=min_mt5_optimization_closed,
        min_mt5_optimization_pf=min_mt5_optimization_pf,
        max_mt5_optimization_drawdown_price_r=max_mt5_optimization_drawdown_price_r,
        min_mt5_optimization_expectancy_price_r=min_mt5_optimization_expectancy_price_r,
        min_mt5_optimization_side_closed=min_mt5_optimization_side_closed,
        min_mt5_optimization_side_pf=min_mt5_optimization_side_pf,
        min_mt5_optimization_side_avg_price_r=min_mt5_optimization_side_avg_price_r,
        min_mt5_optimization_forward_pf=min_mt5_optimization_forward_pf,
        min_mt5_optimization_forward_trades=min_mt5_optimization_forward_trades,
        min_mt5_optimization_positive_forward_back=min_mt5_optimization_positive_forward_back,
        mt5_yearly_optimization_summary=mt5_yearly_optimization_summary,
        require_mt5_yearly_optimization=require_mt5_yearly_optimization,
        min_mt5_yearly_optimization_closed=min_mt5_yearly_optimization_closed,
        min_mt5_yearly_optimization_pf=min_mt5_yearly_optimization_pf,
        min_mt5_yearly_optimization_avg_price_r=min_mt5_yearly_optimization_avg_price_r,
        max_mt5_yearly_optimization_drawdown_price_r=max_mt5_yearly_optimization_drawdown_price_r,
        min_mt5_yearly_optimization_expectancy_price_r=min_mt5_yearly_optimization_expectancy_price_r,
        min_mt5_yearly_optimization_positive_forward_back=min_mt5_yearly_optimization_positive_forward_back,
        require_mt5_compile=require_mt5_compile,
        winrate_fit_summary=winrate_fit_summary,
        require_winrate_fit=require_winrate_fit,
    )
    live_ready = all(bool(check["passed"]) for check in checks)
    check_summary = promotion_check_summary(checks)
    generated_at = datetime.now().strftime(TIME_FORMAT)
    report: dict[str, object] = {
        "ok": True,
        "generated_at": generated_at,
        "live_ready": live_ready,
        "decision": "ready_for_next_phase" if live_ready else "not_ready",
        "check_count": check_summary["check_count"],
        "failed": check_summary["failed"],
        "failed_checks": check_summary["failed_checks"],
        "failed_check_names": check_summary["failed_check_names"],
        "strategy": {
            "history": str(history_path),
            "strategy": strategy,
            "rr_values": rr_values or list(DEFAULT_RR_VALUES),
            "fixed_rr": fixed_rr,
            "min_score": min_score,
            "max_hold_minutes": max_hold_minutes,
            "include_blackout_times": include_blackout_times,
            "calendar_events": len(calendar_events),
            "forward_ledger": str(forward_ledger_path),
            "forward_status": str(forward_status_path) if forward_status_path else "",
            "forward_status_watch_heartbeat": str(forward_status_watch_heartbeat_path)
            if forward_status_watch_heartbeat_path
            else "",
            "forward_test_watch_heartbeat": str(forward_test_watch_heartbeat_path)
            if forward_test_watch_heartbeat_path
            else "",
            "bridge_status": str(bridge_status_path) if bridge_status_path else "",
            "mt5_forward_report": str(mt5_forward_report_path) if mt5_forward_report_path else "",
            "mt5_optimization_report": str(mt5_optimization_report_path) if mt5_optimization_report_path else "",
            "mt5_optimization_recommendation": str(mt5_optimization_recommendation_path)
            if mt5_optimization_recommendation_path
            else "",
            "mt5_tester_run_report": str(mt5_tester_run_report_path) if mt5_tester_run_report_path else "",
            "mt5_tester_status": str(mt5_tester_status_path) if mt5_tester_status_path else "",
            "mt5_back_forward_run": str(mt5_back_forward_run_path) if mt5_back_forward_run_path else "",
            "mt5_strategy_tester_analysis": str(mt5_strategy_tester_analysis_path)
            if mt5_strategy_tester_analysis_path
            else "",
            "mt5_stable_candidate_report": str(mt5_stable_candidate_report_path)
            if mt5_stable_candidate_report_path
            else "",
            "mt5_stable_candidate_recommendation": str(mt5_stable_candidate_recommendation_path)
            if mt5_stable_candidate_recommendation_path
            else "",
            "mt5_stable_candidate_tester_run_report": str(mt5_stable_candidate_tester_run_report_path)
            if mt5_stable_candidate_tester_run_report_path
            else "",
            "mt5_buy_refit_recommendation": str(mt5_buy_refit_recommendation_path)
            if mt5_buy_refit_recommendation_path
            else "",
            "mt5_buy_entry_refit_recommendation": str(mt5_buy_entry_refit_recommendation_path)
            if mt5_buy_entry_refit_recommendation_path
            else "",
            "mt5_sell_entry_refit_recommendation": str(mt5_sell_entry_refit_recommendation_path)
            if mt5_sell_entry_refit_recommendation_path
            else "",
            "mt5_sell_regime_entry_refit_recommendation": str(mt5_sell_regime_entry_refit_recommendation_path)
            if mt5_sell_regime_entry_refit_recommendation_path
            else "",
            "mt5_buy_hour03_validation_recommendation": str(mt5_buy_hour03_validation_recommendation_path)
            if mt5_buy_hour03_validation_recommendation_path
            else "",
            "mt5_buy_hour03_wide_stop_validation_recommendation": str(
                mt5_buy_hour03_wide_stop_validation_recommendation_path
            )
            if mt5_buy_hour03_wide_stop_validation_recommendation_path
            else "",
            "mt5_buy_hour03_wide_stop_calendar_validation_recommendation": str(
                mt5_buy_hour03_wide_stop_calendar_validation_recommendation_path
            )
            if mt5_buy_hour03_wide_stop_calendar_validation_recommendation_path
            else "",
            "mt5_yearly_optimization_report": str(mt5_yearly_optimization_report_path) if mt5_yearly_optimization_report_path else "",
            "mt5_compile_status": str(mt5_compile_status_path) if mt5_compile_status_path else "",
            "winrate_fit_report": str(winrate_fit_report_path) if winrate_fit_report_path else "",
            "score_weight_search_report": str(score_weight_search_report_path) if score_weight_search_report_path else "",
            "score_weight_search_buy_report": str(score_weight_search_buy_report_path)
            if score_weight_search_buy_report_path
            else "",
            "score_weight_search_sell_report": str(score_weight_search_sell_report_path)
            if score_weight_search_sell_report_path
            else "",
            "score_weight_set_buy_report": str(score_weight_set_buy_report_path)
            if score_weight_set_buy_report_path
            else "",
            "score_weight_set_sell_report": str(score_weight_set_sell_report_path)
            if score_weight_set_sell_report_path
            else "",
            "risk_shape_weight_search_report": str(risk_shape_weight_search_report_path)
            if risk_shape_weight_search_report_path
            else "",
        },
        "checks": checks,
        "summary": summary,
        "score_calibration": score_calibration,
        "dry_run_audit": audit,
        "forward_test": forward_summary,
        "forward_status": forward_status_summary,
        "forward_status_watch_heartbeat": forward_status_watch_heartbeat,
        "forward_test_watch_heartbeat": forward_test_watch_heartbeat,
        "bridge_status": bridge_status_summary,
        "mt5_forward_test": mt5_forward_summary,
        "mt5_optimization": mt5_optimization_summary,
        "mt5_optimization_recommendation": mt5_optimization_recommendation,
        "mt5_tester_run": mt5_tester_run_summary,
        "mt5_tester_status": mt5_tester_status_summary,
        "mt5_back_forward_run": mt5_back_forward_run_summary,
        "mt5_strategy_tester_analysis": (
            mt5_strategy_tester_analysis
            if isinstance(mt5_strategy_tester_analysis, dict)
            else {}
        ),
        "mt5_strategy_tester_analysis_freshness": mt5_strategy_tester_analysis_freshness(
            mt5_strategy_tester_analysis,
            current_promotion_generated_at=generated_at,
        ),
        "mt5_stable_candidate": mt5_stable_candidate_summary,
        "mt5_stable_candidate_recommendation": mt5_stable_candidate_recommendation,
        "mt5_stable_candidate_tester_run": mt5_stable_candidate_tester_run_summary,
        "mt5_buy_refit_recommendation": mt5_buy_refit_recommendation,
        "mt5_buy_entry_refit_recommendation": mt5_buy_entry_refit_recommendation,
        "mt5_sell_entry_refit_recommendation": mt5_sell_entry_refit_recommendation,
        "mt5_sell_regime_entry_refit_recommendation": mt5_sell_regime_entry_refit_recommendation,
        "mt5_buy_hour03_validation_recommendation": mt5_buy_hour03_validation_recommendation,
        "mt5_buy_hour03_wide_stop_validation_recommendation": mt5_buy_hour03_wide_stop_validation_recommendation,
        "mt5_buy_hour03_wide_stop_calendar_validation_recommendation": (
            mt5_buy_hour03_wide_stop_calendar_validation_recommendation
        ),
        "mt5_yearly_optimization": mt5_yearly_optimization_summary,
        "mt5_compile_status": mt5_compile_summary,
        "winrate_fit": winrate_fit_summary,
        "score_weight_search": score_weight_search_summary,
        "score_weight_search_by_side": score_weight_search_by_side,
        "score_weight_set_by_side": score_weight_set_by_side,
        "risk_shape_weight_search": risk_shape_weight_search_summary,
    }
    report["performance_comparison"] = performance_comparison_rows(
        summary=summary,
        forward_summary=forward_summary,
        mt5_forward_summary=mt5_forward_summary,
        mt5_optimization_summary=mt5_optimization_summary,
        mt5_yearly_optimization_summary=mt5_yearly_optimization_summary,
    )
    report["next_actions"] = build_promotion_next_actions(report)
    return report


def load_watch_heartbeat(path: str | Path | None) -> dict[str, object]:
    payload = load_optional_json(path) or {}
    if not isinstance(payload, dict) or not payload:
        return {}
    enriched = dict(payload)
    if not path:
        return enriched
    source = Path(path)
    try:
        age_seconds = max(datetime.now().timestamp() - source.stat().st_mtime, 0.0)
    except OSError:
        return enriched
    next_run_seconds = number(enriched.get("next_run_in_seconds"))
    max_age_seconds = max(
        DEFAULT_WATCH_HEARTBEAT_MAX_AGE_SECONDS,
        next_run_seconds * 3 if next_run_seconds > 0 else 0.0,
    )
    enriched["heartbeat_age_seconds"] = round(age_seconds, 1)
    enriched["heartbeat_max_age_seconds"] = round(max_age_seconds, 1)
    enriched["heartbeat_fresh"] = age_seconds <= max_age_seconds
    return enriched


def extract_mt5_forward_summary(report: dict[str, Any] | None) -> dict[str, object]:
    return unwrap_summary_payload(report)


def extract_mt5_back_forward_run_summary(report: dict[str, Any] | None) -> dict[str, object]:
    if not isinstance(report, dict):
        return {}
    comparison = (
        report.get("performance_comparison")
        if isinstance(report.get("performance_comparison"), dict)
        else {}
    )
    rows = comparison.get("rows") if isinstance(comparison.get("rows"), list) else []
    thresholds = comparison.get("thresholds") if isinstance(comparison.get("thresholds"), dict) else {}
    steps = report.get("steps") if isinstance(report.get("steps"), list) else []
    execution_conditions = (
        report.get("execution_conditions") if isinstance(report.get("execution_conditions"), dict) else {}
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
    return {
        "ok": report.get("ok"),
        "generated_at": report.get("generated_at", ""),
        "mode": report.get("mode", ""),
        "execute": report.get("execute"),
        "dry_run": report.get("dry_run"),
        "collect_only": report.get("collect_only", ""),
        "launch_mt5": report.get("launch_mt5", ""),
        "evidence_state": evidence_state,
        "run_id_prefix": report.get("run_id_prefix", ""),
        "execution_conditions": dict(execution_conditions),
        "blocked_before_steps": report.get("blocked_before_steps", ""),
        "reason": report.get("reason", ""),
        "performance_comparison_available": comparison.get("available", False),
        "performance_comparison_status": comparison.get("status", ""),
        "performance_comparison_reason": comparison.get("reason", ""),
        "performance_comparison_rows": [row for row in rows if isinstance(row, dict)],
        "performance_comparison_thresholds": dict(thresholds),
        "step_count": len([step for step in steps if isinstance(step, dict)]),
        "step_labels": [
            str(step.get("label", ""))
            for step in steps
            if isinstance(step, dict) and str(step.get("label", "")).strip()
        ],
    }


def extract_mt5_tester_status_summary(report: dict[str, Any] | None) -> dict[str, object]:
    if not isinstance(report, dict):
        return {}
    status_watch = (
        report.get("status_watch_heartbeat")
        if isinstance(report.get("status_watch_heartbeat"), dict)
        else {}
    )
    next_action_runner = (
        report.get("next_action_runner") if isinstance(report.get("next_action_runner"), dict) else {}
    )
    manual_test_queue = (
        report.get("manual_test_queue") if isinstance(report.get("manual_test_queue"), dict) else {}
    )
    operator_summary = (
        report.get("operator_summary") if isinstance(report.get("operator_summary"), dict) else {}
    )
    return {
        "generated_at": report.get("generated_at", ""),
        "operational_status": report.get("operational_status", ""),
        "ready_for_tester_launch": report.get("ready_for_tester_launch", ""),
        "next_action_execution_ready": (
            report.get("next_action_execution", {}).get("ready")
            if isinstance(report.get("next_action_execution"), dict)
            else ""
        ),
        "back_forward_execution_ready": (
            report.get("back_forward_execution", {}).get("ready")
            if isinstance(report.get("back_forward_execution"), dict)
            else ""
        ),
        "status_watch_heartbeat": dict(status_watch),
        "next_action_runner": dict(next_action_runner),
        "manual_test_queue": dict(manual_test_queue),
        "operator_summary": dict(operator_summary),
    }


def extract_bridge_status_summary(report: dict[str, Any] | None) -> dict[str, object]:
    if not isinstance(report, dict):
        return {}
    health = report.get("health") if isinstance(report.get("health"), dict) else {}
    config = report.get("config") if isinstance(report.get("config"), dict) else {}
    config_payload = config.get("payload") if isinstance(config.get("payload"), dict) else {}
    process = report.get("process") if isinstance(report.get("process"), dict) else {}
    mt5_terminal = report.get("mt5_terminal") if isinstance(report.get("mt5_terminal"), dict) else {}
    ea_attention = report.get("ea_attention") if isinstance(report.get("ea_attention"), dict) else {}
    snapshot = report.get("latest_snapshot") if isinstance(report.get("latest_snapshot"), dict) else {}
    history_request = report.get("history_request") if isinstance(report.get("history_request"), dict) else {}
    request = history_request.get("request") if isinstance(history_request.get("request"), dict) else {}
    done = history_request.get("done") if isinstance(history_request.get("done"), dict) else {}
    bridge_log = report.get("bridge_log") if isinstance(report.get("bridge_log"), dict) else {}
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
        "ok": report.get("ok"),
        "generated_at": report.get("generated_at", ""),
        "operational_status": report.get("operational_status", ""),
        "next_action": report.get("next_action", ""),
        "health_ok": health.get("ok"),
        "config_ok": config.get("ok"),
        "config_history_hours": config_payload.get("history_hours"),
        "config_history_request_id": config_payload.get("history_request_id", ""),
        "process_running": process.get("running"),
        "process_match_count": process.get("match_count"),
        "mt5_terminal_running": mt5_terminal.get("running"),
        "mt5_terminal_match_count": mt5_terminal.get("match_count"),
        "ea_attention_required": ea_attention.get("required"),
        "ea_attention_reason": ea_attention.get("reason", ""),
        "ea_liveness_signal": ea_attention.get("ea_liveness_signal", ""),
        "config_get_recent": ea_attention.get("config_get_recent", ""),
        "ea_post_recent": ea_attention.get("ea_post_recent", ""),
        "config_get_recent_but_ea_post_stale": ea_attention.get(
            "config_get_recent_but_ea_post_stale", ""
        ),
        "snapshot_fresh": snapshot.get("fresh"),
        "snapshot_age_seconds": snapshot.get("age_seconds"),
        "snapshot_server_time": snapshot.get("server_time", ""),
        "history_request_pending": history_request.get("pending"),
        "history_request_stale_pending": history_request.get("stale_pending"),
        "history_request_pending_age_seconds": history_request.get("pending_age_seconds"),
        "history_request_id": request.get("id", ""),
        "history_done_id": done.get("id", ""),
        "history_done_matches_request": history_request.get("done_matches_request"),
        "bridge_log_activity_status": activity.get("status", ""),
        "bridge_log_ea_liveness_signal": activity.get("ea_liveness_signal", ""),
        "bridge_log_config_get_recent": activity.get("config_get_recent", ""),
        "bridge_log_ea_post_recent": activity.get("ea_post_recent", ""),
        "bridge_log_config_get_recent_but_ea_post_stale": activity.get(
            "config_get_recent_but_ea_post_stale", ""
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


def extract_winrate_fit_summary(report: dict[str, Any] | None) -> dict[str, object]:
    if not isinstance(report, dict):
        return {}
    summary: dict[str, object] = {}
    adoption = report.get("adoption_decision")
    if isinstance(adoption, dict):
        summary["adoption_decision"] = adoption
    rows = report.get("summary_rows")
    if "adoption_decision" not in summary and isinstance(rows, list):
        adoption = next((row for row in rows if isinstance(row, dict) and row.get("dataset") == "adoption_decision"), None)
        if isinstance(adoption, dict):
            summary["adoption_decision"] = adoption
    if "adoption_decision" not in summary and report.get("dataset") == "adoption_decision":
        summary["adoption_decision"] = report
    walk_rows = report.get("walk_rows")
    if isinstance(walk_rows, list):
        summary["walk_rows"] = walk_rows
    if summary:
        return summary
    return report


def extract_score_weight_search_summary(report: dict[str, Any] | None) -> dict[str, object]:
    if not isinstance(report, dict):
        return {}
    top = report.get("top_weight_candidate")
    rows = report.get("search_rows")
    baseline_rows = report.get("baseline_rows")
    walk_forward = report.get("walk_forward")
    regime_search = report.get("regime_search")
    summary: dict[str, object] = {
        "ok": report.get("ok"),
        "generated_at": report.get("generated_at", ""),
        "settings": report.get("settings") if isinstance(report.get("settings"), dict) else {},
        "candidate_count": report.get("candidate_count", 0),
        "result_count": report.get("result_count", 0),
        "search_row_count": report.get("search_row_count", 0),
        "baseline_row_count": report.get("baseline_row_count", 0),
        "top_weight_candidate": top if isinstance(top, dict) else {},
        "search_rows": rows[:10] if isinstance(rows, list) else [],
        "baseline_rows": baseline_rows if isinstance(baseline_rows, list) else [],
        "walk_forward": walk_forward if isinstance(walk_forward, dict) else {"enabled": False},
        "regime_search": compact_score_weight_regime_search(regime_search),
    }
    summary["diagnostics"] = score_weight_search_diagnostics(summary)
    return summary


def extract_score_weight_set_summary(report: dict[str, Any] | None) -> dict[str, object]:
    if not isinstance(report, dict):
        return {}
    follow_up = report.get("follow_up") if isinstance(report.get("follow_up"), dict) else {}
    return {
        "ok": report.get("ok"),
        "generated_at": report.get("generated_at", ""),
        "source_generated_at": report.get("source_generated_at", ""),
        "focus_side": report.get("focus_side", ""),
        "can_write": report.get("can_write"),
        "written": report.get("written"),
        "skipped_write": report.get("skipped_write"),
        "skip_reason": report.get("skip_reason", ""),
        "allow_failed_walk_forward": report.get("allow_failed_walk_forward"),
        "walk_forward_status": report.get("walk_forward_status", ""),
        "output_set": report.get("output_set", ""),
        "template_set": report.get("template_set", ""),
        "top_weight_candidate": compact_score_weight_candidate(report.get("top_weight_candidate")),
        "follow_up": follow_up,
    }


def score_weight_search_diagnostics(summary: dict[str, object]) -> dict[str, object]:
    top = summary.get("top_weight_candidate")
    if not isinstance(top, dict) or not top:
        return {"status": "missing_top_candidate", "recommendation": "run weight_search.py before score adoption"}
    settings = summary.get("settings") if isinstance(summary.get("settings"), dict) else {}
    min_count = int(number(settings.get("min_count"))) if numeric_value_present(settings.get("min_count")) else 20
    top_count = int(number(top.get("count")))
    baseline_rows = [row for row in summary.get("baseline_rows", []) if isinstance(row, dict)]
    if top_count < min_count:
        return {
            "status": "sample_shortage",
            "top": compact_score_weight_candidate(top),
            "min_count": min_count,
            "recommendation": "collect more candidates before using the fitted weight candidate",
        }
    required_baseline_count = max(top_count, min_count)
    sufficient_baselines = [row for row in baseline_rows if number(row.get("count")) >= required_baseline_count]
    fallback_used = False
    if not sufficient_baselines:
        sufficient_baselines = [row for row in baseline_rows if number(row.get("count")) >= min_count]
        fallback_used = True
    if not sufficient_baselines:
        return {
            "status": "no_count_sufficient_baseline",
            "top": compact_score_weight_candidate(top),
            "min_count": min_count,
            "required_baseline_count": required_baseline_count,
            "recommendation": "rerun the baseline threshold diagnostics with enough samples before adoption",
        }
    baseline = max(
        sufficient_baselines,
        key=lambda row: (
            number(row.get("avg_r")),
            number(row.get("pf")),
            number(row.get("total_r")),
        ),
    )
    deltas = {
        "count": top_count - int(number(baseline.get("count"))),
        "avg_r": round(number(top.get("avg_r")) - number(baseline.get("avg_r")), 4),
        "pf": round(number(top.get("pf")) - number(baseline.get("pf")), 4),
        "total_r": round(number(top.get("total_r")) - number(baseline.get("total_r")), 4),
        "max_drawdown_r": round(number(top.get("max_drawdown_r")) - number(baseline.get("max_drawdown_r")), 4),
    }
    improved = deltas["avg_r"] > 0 and deltas["pf"] > 0
    dd_tradeoff = deltas["max_drawdown_r"] > 0
    walk_forward = summary.get("walk_forward") if isinstance(summary.get("walk_forward"), dict) else {}
    walk_aggregate = walk_forward.get("aggregate") if isinstance(walk_forward, dict) else {}
    walk_status = walk_aggregate.get("status") if isinstance(walk_aggregate, dict) else ""
    if walk_status and walk_status != "walk_forward_candidate_passed":
        status = "walk_forward_not_passed"
    elif improved and not dd_tradeoff:
        status = "improved_vs_count_sufficient_baseline"
    elif improved:
        status = "improved_with_drawdown_tradeoff"
    else:
        status = "not_improved_vs_count_sufficient_baseline"
    if walk_status == "walk_forward_candidate_passed":
        recommendation = "walk-forward candidate only; continue with MT5 optimization and yearly validation before adoption"
    elif walk_status:
        recommendation = "do not adopt this weighting; walk-forward validation did not pass"
    elif improved:
        recommendation = "diagnostic only; validate this weighting with walk-forward, MT5 optimization, and yearly evidence before adoption"
    else:
        recommendation = "do not adopt this weighting; continue score refit or collect more samples"
    return {
        "status": status,
        "top": compact_score_weight_candidate(top),
        "baseline": compact_score_weight_baseline(baseline),
        "deltas": deltas,
        "walk_forward": compact_score_weight_walk_forward(walk_forward),
        "min_count": min_count,
        "required_baseline_count": required_baseline_count,
        "fallback_baseline_used": fallback_used,
        "recommendation": recommendation,
    }


def extract_mt5_optimization_summary(report: dict[str, Any] | None) -> dict[str, object]:
    return unwrap_summary_payload(report)


def extract_mt5_optimization_recommendation(report: dict[str, Any] | None) -> dict[str, object]:
    if not isinstance(report, dict):
        return {}
    recommendation = report.get("recommendation")
    if isinstance(recommendation, dict):
        return recommendation
    return unwrap_summary_payload(report)


def extract_mt5_tester_run_summary(report: dict[str, Any] | None) -> dict[str, object]:
    if not isinstance(report, dict):
        return {}
    return report


def extract_mt5_compile_summary(report: dict[str, Any] | None) -> dict[str, object]:
    return unwrap_summary_payload(report)


def unwrap_summary_payload(report: dict[str, Any] | None) -> dict[str, object]:
    if not isinstance(report, dict):
        return {}
    current: dict[str, Any] = report
    for _ in range(4):
        summary = current.get("summary")
        if not isinstance(summary, dict):
            break
        current = summary
    return current


def select_candidates_for_gate(
    history,
    *,
    strategy: str,
    rr_values: list[float],
    fixed_rr: float,
    min_score: float,
    include_blackout_times: bool,
    calendar_events,
    news_before_minutes: int,
    news_after_minutes: int,
    news_min_impact: str,
    news_currencies,
):
    common = {
        "min_score": None,
        "score_profile": "side",
        "exclude_blackout_times": not include_blackout_times,
        "blackout_events": calendar_events,
        "news_before_minutes": news_before_minutes,
        "news_after_minutes": news_after_minutes,
        "news_min_impact": news_min_impact,
        "news_currencies": news_currencies,
    }
    if strategy == "fixed":
        selected = generate_candidates(history, risk_reward=fixed_rr, **common)
    else:
        candidate_sets = {
            rr: generate_candidates(history, risk_reward=rr, **common)
            for rr in sorted(set(rr_values))
        }
        selected = select_variable_rr_candidates(candidate_sets, strategy)
    return [candidate for candidate in selected if candidate.score >= min_score]


def history_timeframe_checks(
    history_timeframes: dict[str, int] | None,
    *,
    history_hours: int,
    min_history_hours: int,
    min_coverage_ratio: float = HISTORY_MIN_TIMEFRAME_COVERAGE_RATIO,
) -> list[dict[str, object]]:
    if history_timeframes is None:
        return []
    expected_hours = max(int(min_history_hours or 0), 0)
    counts: dict[str, int] = {}
    expected: dict[str, int] = {}
    coverage: dict[str, float] = {}
    missing: list[str] = []
    for timeframe, per_hour in HISTORY_EXPECTED_BARS_PER_HOUR.items():
        count = int(history_timeframes.get(timeframe) or 0)
        required = expected_hours * per_hour
        ratio = (count / required) if required else 0.0
        counts[timeframe] = count
        expected[timeframe] = required
        coverage[timeframe] = round(ratio, 4) if required else 0.0
        if required and ratio < min_coverage_ratio:
            missing.append(timeframe)
    value = {
        "history_hours": history_hours,
        "min_history_hours": min_history_hours,
        "analysis_bar_source": "timeframes.M1.bars",
        "counts": counts,
        "expected": expected,
        "coverage_ratio": coverage,
        "missing_timeframes": missing,
        "min_coverage_ratio": min_coverage_ratio,
    }
    return [
        check(
            "history_timeframes_complete",
            not missing,
            value,
            f"all M1/M5/M15/M30 bars >= {min_coverage_ratio:.0%} of {min_history_hours}h expected counts",
        )
    ]


def promotion_checks(
    *,
    history_hours: int,
    history_timeframes: dict[str, int] | None = None,
    summary: dict[str, object],
    audit: dict[str, object],
    forward_summary: dict[str, object],
    mt5_forward_summary: dict[str, object] | None = None,
    mt5_optimization_summary: dict[str, object] | None = None,
    mt5_optimization_recommendation_summary: dict[str, object] | None = None,
    mt5_tester_run_summary: dict[str, object] | None = None,
    mt5_tester_status_summary: dict[str, object] | None = None,
    mt5_back_forward_run_summary: dict[str, object] | None = None,
    bridge_status_summary: dict[str, object] | None = None,
    mt5_compile_summary: dict[str, object] | None = None,
    min_history_hours: int,
    min_candidates: int,
    min_avg_r: float,
    min_pf: float,
    max_losing_streak_allowed: int,
    min_side_count: int,
    min_side_pf: float,
    require_dry_run_passed: bool,
    max_dry_run_age_seconds: int,
    require_forward: bool,
    min_forward_closed: int,
    min_forward_avg_r: float,
    min_forward_pf: float,
    min_dry_run_command_score: float = 50.0,
    max_forward_drawdown_r: float = 0.0,
    min_forward_expectancy_r: float | None = None,
    min_forward_side_closed: int = 10,
    min_forward_side_pf: float = 1.0,
    min_forward_side_avg_r: float = 0.0,
    require_mt5_forward: bool = False,
    min_mt5_forward_closed: int = 30,
    min_mt5_forward_pf: float = 1.2,
    max_mt5_forward_losing_streak: int = 20,
    max_mt5_forward_drawdown_price_r: float = 0.0,
    min_mt5_forward_expectancy_price_r: float | None = None,
    min_mt5_forward_side_closed: int = 10,
    min_mt5_forward_side_pf: float = 1.0,
    min_mt5_forward_side_avg_price_r: float = 0.0,
    require_mt5_optimization: bool = False,
    min_mt5_optimization_closed: int = 100,
    min_mt5_optimization_pf: float = 1.2,
    max_mt5_optimization_drawdown_price_r: float = 0.0,
    min_mt5_optimization_expectancy_price_r: float | None = None,
    min_mt5_optimization_side_closed: int = 30,
    min_mt5_optimization_side_pf: float = 1.0,
    min_mt5_optimization_side_avg_price_r: float = 0.0,
    min_mt5_optimization_forward_pf: float = 1.2,
    min_mt5_optimization_forward_trades: int = 30,
    min_mt5_optimization_positive_forward_back: int = 1,
    mt5_yearly_optimization_summary: dict[str, object] | None = None,
    require_mt5_yearly_optimization: bool = False,
    min_mt5_yearly_optimization_closed: int = 100,
    min_mt5_yearly_optimization_pf: float = 1.2,
    min_mt5_yearly_optimization_avg_price_r: float = 0.0,
    max_mt5_yearly_optimization_drawdown_price_r: float = 0.0,
    min_mt5_yearly_optimization_expectancy_price_r: float | None = None,
    min_mt5_yearly_optimization_positive_forward_back: int = 1,
    require_mt5_compile: bool = False,
    winrate_fit_summary: dict[str, object] | None = None,
    require_winrate_fit: bool = False,
    min_side_avg_r: float = 0.0,
    max_side_total_r_share: float = 0.85,
    min_score_quality_threshold: float = 70.0,
    min_score_quality_count: int = 20,
    min_score_quality_avg_r: float = 0.0,
    min_score_quality_pf: float = 1.2,
    max_score_quality_avg_r_drop: float = 0.25,
    max_drawdown_r: float = 0.0,
    min_expectancy_r: float | None = None,
) -> list[dict[str, object]]:
    overall = dict(summary.get("overall", {}))
    side_rows = list(summary.get("side", []))
    checks = [
        check("history_hours", history_hours >= min_history_hours, history_hours, f">= {min_history_hours}"),
        check("candidate_count", number(overall.get("count")) >= min_candidates, overall.get("count"), f">= {min_candidates}"),
        check("avg_r_positive", number(overall.get("avg_r")) > min_avg_r, overall.get("avg_r"), f"> {min_avg_r}"),
        check("pf_minimum", number(overall.get("pf")) >= min_pf, overall.get("pf"), f">= {min_pf}"),
        check(
            "max_losing_streak",
            number(overall.get("max_losing_streak")) <= max_losing_streak_allowed,
            overall.get("max_losing_streak"),
            f"<= {max_losing_streak_allowed}",
        ),
    ]
    checks.extend(
        history_timeframe_checks(
            history_timeframes,
            history_hours=history_hours,
            min_history_hours=min_history_hours,
        )
    )
    if bridge_status_summary:
        checks.append(
            check(
                "bridge_status_ready",
                bridge_status_summary.get("operational_status") == "ready",
                {
                    "operational_status": bridge_status_summary.get("operational_status", ""),
                    "snapshot_fresh": bridge_status_summary.get("snapshot_fresh"),
                    "history_request_pending": bridge_status_summary.get("history_request_pending"),
                    "history_request_stale_pending": bridge_status_summary.get("history_request_stale_pending"),
                    "config_history_request_id": bridge_status_summary.get("config_history_request_id", ""),
                    "ea_liveness_signal": bridge_status_summary.get("ea_liveness_signal", "")
                    or bridge_status_summary.get("bridge_log_ea_liveness_signal", ""),
                    "config_get_recent_but_ea_post_stale": bridge_status_summary.get(
                        "config_get_recent_but_ea_post_stale", ""
                    )
                    if bridge_status_summary.get("config_get_recent_but_ea_post_stale", "") not in (None, "")
                    else bridge_status_summary.get("bridge_log_config_get_recent_but_ea_post_stale", ""),
                },
                "operational_status=ready",
            )
        )
    checks.extend(
        optional_risk_stat_checks(
            "backtest",
            overall,
            drawdown_key="max_drawdown_r",
            max_drawdown=max_drawdown_r,
            expectancy_key="expectancy_r",
            min_expectancy=min_expectancy_r,
        )
    )
    checks.extend(
        score_quality_checks(
            summary,
            min_threshold=min_score_quality_threshold,
            min_count=min_score_quality_count,
            min_avg_r=min_score_quality_avg_r,
            min_pf=min_score_quality_pf,
            max_avg_r_drop=max_score_quality_avg_r_drop,
        )
    )
    checks.extend(
        side_checks(
            side_rows,
            min_side_count=min_side_count,
            min_side_pf=min_side_pf,
            min_side_avg_r=min_side_avg_r,
            max_side_total_r_share=max_side_total_r_share,
        )
    )
    if require_dry_run_passed:
        checks.extend(
            [
                check(
                    "dry_run_passed",
                    audit.get("outcome") == "ea_dry_run_passed" and audit.get("dry_run_only") is True,
                    {"outcome": audit.get("outcome"), "dry_run_only": audit.get("dry_run_only")},
                    "ea_dry_run_passed and dry_run_only=true",
                ),
                check(
                    "dry_run_fresh",
                    isinstance(audit.get("freshness"), dict) and audit["freshness"].get("fresh") is True,
                    audit.get("freshness"),
                    f"command/result age <= {max_dry_run_age_seconds}s",
                ),
                check(
                    "dry_run_signal_command_match",
                    audit.get("signal_command_match") is True,
                    audit.get("signal_command"),
                    "latest signal matches audited command",
                ),
                check(
                    "dry_run_risk_gate_allowed",
                    isinstance(audit.get("risk_gate"), dict) and audit["risk_gate"].get("allowed") is True,
                    audit.get("risk_gate", "missing"),
                    "risk_gate.allowed = true",
                ),
            ]
        )
        checks.extend(dry_run_command_safety_checks(audit, min_score=min_dry_run_command_score))
    else:
        checks.append(check("dry_run_passed", True, "not_required", "not_required"))
    if require_forward:
        checks.extend(
            [
                check(
                    "forward_closed_count",
                    number(forward_summary.get("closed")) >= min_forward_closed,
                    forward_summary.get("closed", 0),
                    f">= {min_forward_closed}",
                ),
                check(
                    "forward_avg_r",
                    number(forward_summary.get("avg_r")) > min_forward_avg_r,
                    forward_summary.get("avg_r", 0),
                    f"> {min_forward_avg_r}",
                ),
                check(
                    "forward_pf",
                    number(forward_summary.get("pf")) >= min_forward_pf,
                    forward_summary.get("pf", 0),
                    f">= {min_forward_pf}",
                ),
            ]
        )
        checks.extend(
            optional_risk_stat_checks(
                "forward",
                forward_summary,
                drawdown_key="max_drawdown_r",
                max_drawdown=max_forward_drawdown_r,
                expectancy_key="expectancy_r",
                min_expectancy=min_forward_expectancy_r,
            )
        )
        checks.extend(
            forward_side_checks(
                forward_summary,
                min_side_closed=min_forward_side_closed,
                min_side_pf=min_forward_side_pf,
                min_side_avg_r=min_forward_side_avg_r,
            )
        )
    else:
        checks.append(check("forward_test", True, "not_required", "not_required"))
    mt5_forward_summary = mt5_forward_summary or {}
    if require_mt5_forward or mt5_forward_summary:
        overall = mt5_forward_overall(mt5_forward_summary)
        checks.extend(
            [
                check(
                    "mt5_forward_closed_count",
                    number(overall.get("closed")) >= min_mt5_forward_closed,
                    overall.get("closed", 0),
                    f">= {min_mt5_forward_closed}",
                ),
                check(
                    "mt5_forward_pf",
                    number(overall.get("pf")) >= min_mt5_forward_pf,
                    overall.get("pf", 0),
                    f">= {min_mt5_forward_pf}",
                ),
                check(
                    "mt5_forward_max_losing_streak",
                    number(overall.get("max_losing_streak")) <= max_mt5_forward_losing_streak,
                    overall.get("max_losing_streak", 0),
                    f"<= {max_mt5_forward_losing_streak}",
                ),
            ]
        )
        checks.extend(
            optional_risk_stat_checks(
                "mt5_forward",
                overall,
                drawdown_key="max_drawdown_price_r",
                max_drawdown=max_mt5_forward_drawdown_price_r,
                expectancy_key="expectancy_price_r",
                min_expectancy=min_mt5_forward_expectancy_price_r,
            )
        )
        if require_mt5_forward or isinstance(mt5_forward_summary.get("by_action"), list):
            checks.extend(
                mt5_forward_side_checks(
                    mt5_forward_summary,
                    min_side_closed=min_mt5_forward_side_closed,
                    min_side_pf=min_mt5_forward_side_pf,
                    min_side_avg_price_r=min_mt5_forward_side_avg_price_r,
                    max_side_total_r_share=max_side_total_r_share,
                )
            )
        if require_mt5_forward or isinstance(mt5_forward_summary.get("button"), dict):
            checks.append(mt5_forward_button_safety_check(mt5_forward_summary, required=require_mt5_forward))
        if require_mt5_forward or isinstance(mt5_forward_summary.get("risk_exposure"), dict):
            checks.extend(mt5_forward_risk_exposure_checks(mt5_forward_summary, required=require_mt5_forward))
        if require_mt5_forward or isinstance(mt5_forward_summary.get("csv_schema"), dict):
            checks.extend(mt5_forward_csv_schema_checks(mt5_forward_summary, required=require_mt5_forward))
        if require_mt5_forward or any(
            isinstance(mt5_forward_summary.get(key), list)
            for key in (
                "by_stop_points",
                "by_take_profit_points",
                "by_risk_reward_stop_points",
                "by_risk_reward_take_profit_points",
                "weak_sl_tp_segments",
            )
        ):
            checks.extend(mt5_forward_sl_tp_diagnostic_checks(mt5_forward_summary, required=require_mt5_forward))
        if require_mt5_forward or isinstance(mt5_forward_summary.get("diagnostic_warnings"), list):
            checks.extend(mt5_forward_diagnostic_warning_checks(mt5_forward_summary, required=require_mt5_forward))
        if isinstance(mt5_forward_summary.get("side_score_diagnostics"), list):
            checks.extend(mt5_forward_side_score_checks(mt5_forward_summary))
    else:
        checks.append(check("mt5_forward_test", True, "not_required", "not_required"))
    mt5_back_forward_run_summary = mt5_back_forward_run_summary or {}
    if mt5_back_forward_run_summary:
        checks.extend(mt5_back_forward_run_checks(mt5_back_forward_run_summary))
    mt5_tester_status_summary = mt5_tester_status_summary or {}
    if mt5_tester_status_summary:
        checks.extend(
            mt5_status_watch_checks(
                mt5_tester_status_summary,
                mt5_back_forward_run_summary=mt5_back_forward_run_summary,
            )
        )
    mt5_optimization_summary = mt5_optimization_summary or {}
    if require_mt5_optimization or mt5_optimization_summary:
        checks.extend(
            mt5_optimization_checks(
                mt5_optimization_summary,
                required=require_mt5_optimization,
                min_closed=min_mt5_optimization_closed,
                min_pf=min_mt5_optimization_pf,
                max_drawdown_price_r=max_mt5_optimization_drawdown_price_r,
                min_expectancy_price_r=min_mt5_optimization_expectancy_price_r,
                min_side_closed=min_mt5_optimization_side_closed,
                min_side_pf=min_mt5_optimization_side_pf,
                min_side_avg_price_r=min_mt5_optimization_side_avg_price_r,
                min_forward_pf=min_mt5_optimization_forward_pf,
                min_forward_trades=min_mt5_optimization_forward_trades,
                min_positive_forward_back=min_mt5_optimization_positive_forward_back,
                max_side_total_r_share=max_side_total_r_share,
            )
        )
    else:
        checks.append(check("mt5_optimization", True, "not_required", "not_required"))
    mt5_optimization_recommendation_summary = mt5_optimization_recommendation_summary or {}
    if mt5_optimization_recommendation_summary:
        checks.extend(mt5_optimization_recommendation_checks(mt5_optimization_recommendation_summary))
    mt5_tester_run_summary = mt5_tester_run_summary or {}
    if mt5_tester_run_summary:
        checks.extend(mt5_tester_run_checks(mt5_tester_run_summary))
    mt5_yearly_optimization_summary = mt5_yearly_optimization_summary or {}
    if require_mt5_yearly_optimization or mt5_yearly_optimization_summary:
        checks.extend(
            mt5_yearly_optimization_checks(
                mt5_yearly_optimization_summary,
                required=require_mt5_yearly_optimization,
                min_closed=min_mt5_yearly_optimization_closed,
                min_pf=min_mt5_yearly_optimization_pf,
                min_avg_price_r=min_mt5_yearly_optimization_avg_price_r,
                max_drawdown_price_r=max_mt5_yearly_optimization_drawdown_price_r,
                min_expectancy_price_r=min_mt5_yearly_optimization_expectancy_price_r,
                min_positive_forward_back=min_mt5_yearly_optimization_positive_forward_back,
                max_side_total_r_share=max_side_total_r_share,
            )
        )
    else:
        checks.append(check("mt5_yearly_optimization", True, "not_required", "not_required"))
    mt5_compile_summary = mt5_compile_summary or {}
    if require_mt5_compile or mt5_compile_summary:
        checks.extend(mt5_compile_checks(mt5_compile_summary, required=require_mt5_compile))
    else:
        checks.append(check("mt5_compile_status", True, "not_required", "not_required"))
    winrate_fit_summary = winrate_fit_summary or {}
    if require_winrate_fit or winrate_fit_summary:
        checks.extend(winrate_fit_checks(winrate_fit_summary, required=require_winrate_fit))
    else:
        checks.append(check("winrate_fit", True, "not_required", "not_required"))
    return checks


def mt5_forward_overall(summary: dict[str, object]) -> dict[str, object]:
    overall = summary.get("overall")
    return dict(overall) if isinstance(overall, dict) else {}


def mt5_back_forward_run_checks(summary: dict[str, object]) -> list[dict[str, object]]:
    if not isinstance(summary, dict) or not summary:
        return []
    executed = summary.get("execute") is True and summary.get("dry_run") is not True
    evidence_state = str(summary.get("evidence_state") or "")
    if not evidence_state:
        comparison = {
            "available": summary.get("performance_comparison_available"),
            "status": summary.get("performance_comparison_status", ""),
            "reason": summary.get("performance_comparison_reason", ""),
            "rows": summary.get("performance_comparison_rows", []),
        }
        evidence_state = back_forward_evidence_state(
            execute=summary.get("execute"),
            dry_run=summary.get("dry_run"),
            ok=summary.get("ok"),
            blocked_before_steps=summary.get("blocked_before_steps", ""),
            comparison=comparison,
        )
    if not executed:
        return [
            check(
                "mt5_back_forward_run",
                False,
                {
                    "execute": summary.get("execute"),
                    "dry_run": summary.get("dry_run"),
                    "evidence_state": evidence_state,
                },
                "execute=true before using Back/Forward Runner as promotion evidence",
            )
        ]

    blocked = str(summary.get("blocked_before_steps") or "")
    ok_value = {
        "ok": summary.get("ok"),
        "blocked_before_steps": blocked,
        "reason": summary.get("reason", ""),
        "evidence_state": evidence_state,
    }
    comparison_available = summary.get("performance_comparison_available") is True
    comparison_status = str(summary.get("performance_comparison_status") or "")
    comparison_rows = (
        summary.get("performance_comparison_rows")
        if isinstance(summary.get("performance_comparison_rows"), list)
        else []
    )
    comparison_thresholds = (
        summary.get("performance_comparison_thresholds")
        if isinstance(summary.get("performance_comparison_thresholds"), dict)
        else {}
    )
    backtest_row = next(
        (
            row
            for row in comparison_rows
            if isinstance(row, dict) and str(row.get("dataset") or "").lower() == "backtest"
        ),
        {},
    )
    forward_row = next(
        (
            row
            for row in comparison_rows
            if isinstance(row, dict) and str(row.get("dataset") or "").lower() == "forward"
        ),
        {},
    )
    sample_shortage = "sample_shortage" in comparison_status
    comparison_value = {
        "available": comparison_available,
        "status": comparison_status,
        "evidence_state": evidence_state,
        "reason": summary.get("performance_comparison_reason", ""),
        "rows": len(comparison_rows),
        "thresholds": comparison_thresholds,
        "min_closed": comparison_thresholds.get("min_closed", ""),
        "sample_shortage": sample_shortage,
        "backtest_trades": backtest_row.get("trades") if isinstance(backtest_row, dict) else None,
        "forward_trades": forward_row.get("trades") if isinstance(forward_row, dict) else None,
        "backtest_meets_min_closed": backtest_row.get("meets_min_closed") if isinstance(backtest_row, dict) else None,
        "forward_meets_min_closed": forward_row.get("meets_min_closed") if isinstance(forward_row, dict) else None,
    }
    return [
        check(
            "mt5_back_forward_run_ok",
            summary.get("ok") is True and not blocked,
            ok_value,
            "ok=true and blocked_before_steps empty",
        ),
        check(
            "mt5_back_forward_run_performance",
            comparison_available and comparison_status == "forward_consistent_with_backtest",
            comparison_value,
            "performance_comparison.status = forward_consistent_with_backtest",
        ),
    ]


def mt5_status_watch_back_forward_current_check(
    watcher: dict[str, object],
    mt5_back_forward_run_summary: dict[str, object],
) -> dict[str, object] | None:
    expected = (
        mt5_back_forward_run_summary.get("execution_conditions")
        if isinstance(mt5_back_forward_run_summary.get("execution_conditions"), dict)
        else {}
    )
    if not expected:
        return None
    actual = (
        watcher.get("back_forward_run_execution_conditions")
        if isinstance(watcher.get("back_forward_run_execution_conditions"), dict)
        else {}
    )
    expected_run_id_prefix = str(mt5_back_forward_run_summary.get("run_id_prefix") or "")
    watcher_run_id_prefix = str(watcher.get("back_forward_run_run_id_prefix") or "")
    mismatches = []
    if watcher_run_id_prefix != expected_run_id_prefix:
        mismatches.append(f"run_id_prefix:{watcher_run_id_prefix}->{expected_run_id_prefix}")
    for key, expected_value in expected.items():
        actual_value = actual.get(key, "")
        if not execution_condition_values_match(actual_value, expected_value):
            mismatches.append(f"{key}:{actual_value}->{expected_value}")
    value = {
        "status": watcher.get("status", ""),
        "mismatches": mismatches,
        "expected_execution_conditions": dict(expected),
        "watcher_execution_conditions": dict(actual),
        "watcher_run_id_prefix": watcher_run_id_prefix,
        "expected_run_id_prefix": expected_run_id_prefix,
        "watcher_forward_mode": watcher.get("back_forward_run_forward_mode", ""),
        "expected_forward_mode": expected.get("forward_mode", ""),
        "watcher_generated_at": watcher.get("finished_at", ""),
    }
    return check(
        "mt5_status_watch_back_forward_current",
        watcher.get("status") == "ok" and not mismatches,
        value,
        "status watcher Back/Forward run_id_prefix and execution_conditions match latest mt5_back_forward_run",
    )


NEXT_ACTION_WATCHER_CURRENT_FIELDS = (
    ("target", "next_action_run_target", "target"),
    ("kind", "next_action_run_kind", "kind"),
    ("focus_side", "next_action_run_focus_side", "focus_side"),
    ("optimization_mode", "next_action_run_optimization_mode", "optimization_mode"),
    ("config", "next_action_run_config", "config"),
    ("set", "next_action_run_set", "set"),
    ("output_set", "next_action_run_output_set", "output_set"),
    ("archive_run_id", "next_action_run_archive_run_id", "agent_csv_archive_run_id"),
    ("planned_outputs", "next_action_run_planned_outputs", "planned_outputs"),
    ("primary_planned_outputs", "next_action_run_primary_planned_outputs", "primary_planned_outputs"),
    (
        "archive_preview_planned_outputs",
        "next_action_run_archive_preview_planned_outputs",
        "archive_preview_planned_outputs",
    ),
    ("follow_up_planned_outputs", "next_action_run_follow_up_planned_outputs", "follow_up_planned_outputs"),
    (
        "follow_up_archive_preview_planned_outputs",
        "next_action_run_follow_up_archive_preview_planned_outputs",
        "follow_up_archive_preview_planned_outputs",
    ),
)


def mt5_status_watch_next_action_current_check(
    watcher: dict[str, object],
    next_action_runner: dict[str, object],
) -> dict[str, object] | None:
    if not isinstance(next_action_runner, dict) or not next_action_runner:
        return None
    mismatches = []
    expected_values = {}
    watcher_values = {}
    for label, watcher_key, expected_key in NEXT_ACTION_WATCHER_CURRENT_FIELDS:
        default = {} if label.endswith("planned_outputs") else ""
        expected_value = next_action_runner.get(expected_key, default)
        actual_value = watcher.get(watcher_key, default)
        expected_values[label] = expected_value
        watcher_values[label] = actual_value
        if not execution_condition_values_match(actual_value, expected_value):
            mismatches.append(label)
    watcher_values["runner_promotion_generated_at"] = watcher.get(
        "next_action_run_runner_promotion_generated_at", ""
    )
    expected_values["runner_promotion_generated_at"] = next_action_runner.get(
        "runner_promotion_generated_at", ""
    )
    value = {
        "status": watcher.get("status", ""),
        "mismatches": mismatches,
        "watcher": watcher_values,
        "expected": expected_values,
        "watcher_finished_at": watcher.get("finished_at", ""),
    }
    return check(
        "mt5_status_watch_next_action_current",
        watcher.get("status") == "ok" and not mismatches,
        value,
        "status watcher Next Action Runner fields and planned outputs match latest next_action_runner",
    )


def mt5_status_watch_checks(
    summary: dict[str, object],
    mt5_back_forward_run_summary: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    if not isinstance(summary, dict) or not summary:
        return []
    watcher = (
        summary.get("status_watch_heartbeat")
        if isinstance(summary.get("status_watch_heartbeat"), dict)
        else {}
    )
    if not watcher:
        return []
    value = {
        "status": watcher.get("status", ""),
        "fresh": watcher.get("fresh", ""),
        "compatible": watcher.get("compatible", ""),
        "missing_required_fields": watcher.get("missing_required_fields", []),
        "implementation_version": watcher.get("implementation_version", ""),
        "expected_implementation_version": watcher.get("expected_implementation_version", ""),
        "implementation_version_mismatch": watcher.get("implementation_version_mismatch", ""),
        "watcher_pid": watcher.get("watcher_pid", ""),
        "next_action_run_current_for_execution": watcher.get("next_action_run_current_for_execution", ""),
        "next_action_run_gate_stale_reason": watcher.get("next_action_run_gate_stale_reason", ""),
        "next_action_run_runner_promotion_generated_at": watcher.get(
            "next_action_run_runner_promotion_generated_at", ""
        ),
        "next_action_run_current_promotion_generated_at": watcher.get(
            "next_action_run_current_promotion_generated_at", ""
        ),
        "next_action_run_planned_outputs": watcher.get("next_action_run_planned_outputs", {}),
        "next_action_run_primary_planned_outputs": watcher.get(
            "next_action_run_primary_planned_outputs", {}
        ),
        "next_action_run_archive_preview_planned_outputs": watcher.get(
            "next_action_run_archive_preview_planned_outputs", {}
        ),
        "next_action_run_follow_up_planned_outputs": watcher.get(
            "next_action_run_follow_up_planned_outputs", {}
        ),
        "next_action_run_follow_up_archive_preview_planned_outputs": watcher.get(
            "next_action_run_follow_up_archive_preview_planned_outputs", {}
        ),
        "next_action_run_blocking_prior_action_count": watcher.get(
            "next_action_run_blocking_prior_action_count", ""
        ),
        "next_action_run_blocking_prior_actions": watcher.get(
            "next_action_run_blocking_prior_actions", []
        ),
        "next_action_run_blocking_prior_action_summary": watcher.get(
            "next_action_run_blocking_prior_action_summary", ""
        ),
        "next_action_run_archive_preview_output_json": watcher.get(
            "next_action_run_archive_preview_output_json", ""
        ),
        "next_action_run_archive_preview_output_md": watcher.get("next_action_run_archive_preview_output_md", ""),
        "next_action_run_follow_up_archive_preview_output_json": watcher.get(
            "next_action_run_follow_up_archive_preview_output_json", ""
        ),
        "next_action_run_follow_up_archive_preview_output_md": watcher.get(
            "next_action_run_follow_up_archive_preview_output_md", ""
        ),
        "back_forward_run_archive_preview_output_json": watcher.get(
            "back_forward_run_archive_preview_output_json", ""
        ),
        "back_forward_run_archive_preview_output_md": watcher.get(
            "back_forward_run_archive_preview_output_md", ""
        ),
        "back_forward_run_archive_preview_output_json_by_step": watcher.get(
            "back_forward_run_archive_preview_output_json_by_step", {}
        ),
        "back_forward_run_archive_preview_validation_ok_by_step": watcher.get(
            "back_forward_run_archive_preview_validation_ok_by_step", {}
        ),
        "back_forward_run_performance_comparison_available": watcher.get(
            "back_forward_run_performance_comparison_available", ""
        ),
        "back_forward_run_performance_comparison_status": watcher.get(
            "back_forward_run_performance_comparison_status", ""
        ),
        "back_forward_run_performance_comparison_rows": watcher.get(
            "back_forward_run_performance_comparison_rows", []
        ),
        "back_forward_run_performance_comparison_thresholds": watcher.get(
            "back_forward_run_performance_comparison_thresholds", {}
        ),
        "back_forward_run_run_id_prefix": watcher.get("back_forward_run_run_id_prefix", ""),
        "manual_test_queue_exists": watcher.get("manual_test_queue_exists", ""),
        "manual_test_queue_status": watcher.get("manual_test_queue_status", ""),
        "manual_test_queue_next_action": watcher.get("manual_test_queue_next_action", ""),
        "manual_test_queue_entry_count": watcher.get("manual_test_queue_entry_count", ""),
        "manual_test_queue_total_entry_count": watcher.get("manual_test_queue_total_entry_count", ""),
        "manual_test_queue_stale_entry_count": watcher.get("manual_test_queue_stale_entry_count", ""),
        "manual_test_queue_current_for_execution_count": watcher.get(
            "manual_test_queue_current_for_execution_count", ""
        ),
        "manual_test_queue_selected_action_present_count": watcher.get(
            "manual_test_queue_selected_action_present_count", ""
        ),
        "manual_test_queue_selected_action_current_count": watcher.get(
            "manual_test_queue_selected_action_current_count", ""
        ),
        "manual_test_queue_selected_action_stale_count": watcher.get(
            "manual_test_queue_selected_action_stale_count", ""
        ),
        "manual_test_queue_current_promotion_generated_at_values": watcher.get(
            "manual_test_queue_current_promotion_generated_at_values", []
        ),
        "manual_test_queue_current_promotion_decision_values": watcher.get(
            "manual_test_queue_current_promotion_decision_values", []
        ),
        "manual_test_queue_gate_stale_reasons": watcher.get("manual_test_queue_gate_stale_reasons", []),
        "manual_test_queue_not_current_entry_ids": watcher.get("manual_test_queue_not_current_entry_ids", []),
        "manual_test_queue_step_count": watcher.get("manual_test_queue_step_count", ""),
        "manual_test_queue_waiting_count": watcher.get("manual_test_queue_waiting_count", ""),
        "manual_test_queue_ready_to_collect_count": watcher.get(
            "manual_test_queue_ready_to_collect_count", ""
        ),
        "manual_test_queue_step_report_ready_count": watcher.get(
            "manual_test_queue_step_report_ready_count", ""
        ),
        "manual_test_queue_step_waiting_report_count": watcher.get(
            "manual_test_queue_step_waiting_report_count", ""
        ),
        "manual_test_queue_step_launch_needed_count": watcher.get(
            "manual_test_queue_step_launch_needed_count", ""
        ),
        "manual_test_queue_next_launch_step": (
            watcher.get("manual_test_queue_next_launch_step")
            if isinstance(watcher.get("manual_test_queue_next_launch_step"), dict)
            else {}
        ),
        "manual_test_queue_all_collect_ready": watcher.get("manual_test_queue_all_collect_ready", ""),
        "manual_test_queue_blocking_reasons": watcher.get("manual_test_queue_blocking_reasons", []),
        "manual_test_queue_entries": watcher.get("manual_test_queue_entries", []),
        "manual_test_queue_strategy_tester_targets": watcher.get(
            "manual_test_queue_strategy_tester_targets", []
        ),
        "manual_test_queue_operation_cards": watcher.get("manual_test_queue_operation_cards", []),
        "manual_test_queue_execution_checklist": watcher.get("manual_test_queue_execution_checklist", []),
        "restart_hint": watcher.get("restart_hint", ""),
    }
    for key in MT5_STATUS_WATCH_OPERATOR_ALIAS_KEYS:
        default: object
        if key.endswith("_reasons") or key.endswith("_values"):
            default = []
        elif key.endswith("_quick_input"):
            default = {}
        else:
            default = ""
        value[key] = watcher.get(key, default)
    for key in MT5_BACK_FORWARD_WATCHER_CONDITION_KEYS:
        value[key] = watcher.get(key, {} if key == "back_forward_run_execution_conditions" else "")
    for key in MT5_BACK_FORWARD_WATCHER_PREFLIGHT_KEYS:
        value[key] = watcher.get(key, [] if key.endswith("_checked_execution_conditions") else {})
    checks = [
        check(
            "mt5_status_watch_heartbeat",
            watcher.get("status") == "ok",
            value,
            "status_watch_heartbeat.status = ok",
        )
    ]
    current_check = mt5_status_watch_back_forward_current_check(
        watcher,
        mt5_back_forward_run_summary or {},
    )
    if current_check:
        checks.append(current_check)
    next_action_current_check = mt5_status_watch_next_action_current_check(
        watcher,
        summary.get("next_action_runner") if isinstance(summary.get("next_action_runner"), dict) else {},
    )
    if next_action_current_check:
        checks.append(next_action_current_check)
    return checks


def performance_comparison_rows(
    *,
    summary: dict[str, object],
    forward_summary: dict[str, object],
    mt5_forward_summary: dict[str, object],
    mt5_optimization_summary: dict[str, object],
    mt5_yearly_optimization_summary: dict[str, object],
) -> list[dict[str, object]]:
    baseline = backtest_performance_metrics(summary)
    rows = [
        comparison_row("backtest", baseline, baseline),
        comparison_row("python_forward", forward_performance_metrics(forward_summary), baseline),
        comparison_row("mt5_forward", mt5_performance_metrics(mt5_forward_overall(mt5_forward_summary)), baseline),
        comparison_row("mt5_optimization", mt5_performance_metrics(mt5_optimization_overall(mt5_optimization_summary)), baseline),
        comparison_row(
            "mt5_yearly_optimization",
            mt5_performance_metrics(mt5_optimization_overall(mt5_yearly_optimization_summary)),
            baseline,
        ),
    ]
    return [row for row in rows if row_has_performance_metrics(row)]


def backtest_performance_metrics(summary: dict[str, object]) -> dict[str, object]:
    overall = summary.get("overall") if isinstance(summary, dict) else {}
    overall = overall if isinstance(overall, dict) else {}
    return {
        "trades": optional_number(overall.get("count")),
        "pf": optional_number(overall.get("pf")),
        "avg_r": optional_number(overall.get("avg_r")),
        "expectancy_r": optional_number(overall.get("expectancy_r")),
        "max_drawdown_r": optional_number(overall.get("max_drawdown_r")),
    }


def forward_performance_metrics(summary: dict[str, object]) -> dict[str, object]:
    summary = summary if isinstance(summary, dict) else {}
    return {
        "trades": optional_number(summary.get("closed")),
        "pf": optional_number(summary.get("pf")),
        "avg_r": optional_number(summary.get("avg_r")),
        "expectancy_r": optional_number(summary.get("expectancy_r")),
        "max_drawdown_r": optional_number(summary.get("max_drawdown_r")),
    }


def mt5_performance_metrics(overall: dict[str, object]) -> dict[str, object]:
    overall = overall if isinstance(overall, dict) else {}
    return {
        "trades": optional_number(overall.get("closed")),
        "pf": optional_number(overall.get("pf")),
        "avg_r": optional_number(overall.get("avg_price_r")),
        "expectancy_r": optional_number(overall.get("expectancy_price_r")),
        "max_drawdown_r": optional_number(overall.get("max_drawdown_price_r")),
    }


def comparison_row(label: str, metrics: dict[str, object], baseline: dict[str, object]) -> dict[str, object]:
    row = {
        "dataset": label,
        "trades": rounded_optional(metrics.get("trades"), digits=0),
        "pf": rounded_optional(metrics.get("pf")),
        "avg_r": rounded_optional(metrics.get("avg_r")),
        "expectancy_r": rounded_optional(metrics.get("expectancy_r")),
        "max_drawdown_r": rounded_optional(metrics.get("max_drawdown_r")),
        "pf_delta_vs_backtest": delta(metrics.get("pf"), baseline.get("pf")),
        "avg_r_delta_vs_backtest": delta(metrics.get("avg_r"), baseline.get("avg_r")),
        "expectancy_r_delta_vs_backtest": delta(metrics.get("expectancy_r"), baseline.get("expectancy_r")),
        "max_drawdown_r_delta_vs_backtest": delta(metrics.get("max_drawdown_r"), baseline.get("max_drawdown_r")),
    }
    return row


def row_has_performance_metrics(row: dict[str, object]) -> bool:
    return any(row.get(key) is not None for key in ("trades", "pf", "avg_r", "expectancy_r", "max_drawdown_r"))


def optional_number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def rounded_optional(value: object, *, digits: int = 4) -> float | int | None:
    numeric = optional_number(value)
    if numeric is None:
        return None
    if digits == 0:
        return int(round(numeric))
    return round(numeric, digits)


def delta(value: object, baseline: object) -> float | None:
    numeric = optional_number(value)
    base = optional_number(baseline)
    if numeric is None or base is None:
        return None
    return round(numeric - base, 4)


def score_quality_checks(
    summary: dict[str, object],
    *,
    min_threshold: float,
    min_count: int,
    min_avg_r: float,
    min_pf: float,
    max_avg_r_drop: float,
) -> list[dict[str, object]]:
    rows = summary.get("thresholds") if isinstance(summary, dict) else None
    if not isinstance(rows, list):
        return [
            check("score_upper_threshold_sample", False, "missing", f"thresholds with count >= {min_count}"),
            check("score_upper_threshold_avg_r", False, "missing", f"> {min_avg_r}"),
            check("score_upper_threshold_pf", False, "missing", f">= {min_pf}"),
            check("score_threshold_avg_r_not_degrading", False, "missing", f"drop <= {max_avg_r_drop}"),
        ]

    eligible = [
        row
        for row in rows
        if isinstance(row, dict)
        and number(row.get("threshold")) >= min_threshold
        and number(row.get("count")) >= min_count
    ]
    selected = min(eligible, key=lambda row: number(row.get("threshold")), default=None)
    checks = [
        check(
            "score_upper_threshold_sample",
            selected is not None,
            {"threshold": selected.get("threshold"), "count": selected.get("count")} if isinstance(selected, dict) else 0,
            f"threshold >= {min_threshold} and count >= {min_count}",
        )
    ]
    if isinstance(selected, dict):
        checks.append(
            check(
                "score_upper_threshold_avg_r",
                number(selected.get("avg_r")) > min_avg_r,
                {"threshold": selected.get("threshold"), "avg_r": selected.get("avg_r")},
                f"> {min_avg_r}",
            )
        )
        checks.append(
            check(
                "score_upper_threshold_pf",
                number(selected.get("pf")) >= min_pf,
                {"threshold": selected.get("threshold"), "pf": selected.get("pf")},
                f">= {min_pf}",
            )
        )
    else:
        checks.append(check("score_upper_threshold_avg_r", False, "no eligible threshold", f"> {min_avg_r}"))
        checks.append(check("score_upper_threshold_pf", False, "no eligible threshold", f">= {min_pf}"))
    checks.append(score_threshold_degradation_check(eligible, max_avg_r_drop=max_avg_r_drop))
    return checks


def score_calibration_diagnostics(
    summary: dict[str, object],
    *,
    min_threshold: float,
    min_count: int,
) -> dict[str, object]:
    diagnostic: dict[str, object] = {
        "required_threshold": min_threshold,
        "required_count": min_count,
    }
    rows = summary.get("thresholds") if isinstance(summary, dict) else None
    if not isinstance(rows, list):
        return {
            **diagnostic,
            "status": "missing_thresholds",
            "recommendation": "Regenerate threshold diagnostics before score calibration.",
        }

    normalized = sorted(
        [row for row in rows if isinstance(row, dict)],
        key=lambda row: number(row.get("threshold")),
    )
    required_rows = [row for row in normalized if number(row.get("threshold")) >= min_threshold]
    required_row = min(required_rows, key=lambda row: number(row.get("threshold")), default=None)
    required_count = int(number(required_row.get("count"))) if isinstance(required_row, dict) else 0
    sampled_rows = [row for row in normalized if number(row.get("count")) > 0]
    sufficient_rows = [row for row in normalized if number(row.get("count")) >= min_count]
    eligible_rows = [row for row in sufficient_rows if number(row.get("threshold")) >= min_threshold]
    highest_sampled = max(sampled_rows, key=lambda row: number(row.get("threshold")), default=None)
    highest_sufficient = max(sufficient_rows, key=lambda row: number(row.get("threshold")), default=None)
    selected = min(eligible_rows, key=lambda row: number(row.get("threshold")), default=None)
    highest_sampled_count = int(number(highest_sampled.get("count"))) if isinstance(highest_sampled, dict) else 0
    highest_sampled_threshold = number(highest_sampled.get("threshold")) if isinstance(highest_sampled, dict) else 0.0
    highest_sufficient_threshold = (
        number(highest_sufficient.get("threshold")) if isinstance(highest_sufficient, dict) else 0.0
    )

    status = "ready"
    if selected is None:
        if highest_sufficient is not None:
            status = "sample_shortage_above_required_threshold"
        elif highest_sampled is not None:
            status = "sample_shortage"
        else:
            status = "no_scored_candidates"

    points_from_required = round(max(min_threshold - highest_sampled_threshold, 0.0), 4)
    usable_points_from_required = round(max(min_threshold - highest_sufficient_threshold, 0.0), 4)
    missing_at_required = max(min_count - required_count, 0)
    missing_at_highest_sampled = max(min_count - highest_sampled_count, 0)
    diagnostic.update(
        {
            "status": status,
            "selected_threshold": compact_threshold_row(selected),
            "highest_sampled_threshold": compact_threshold_row(highest_sampled),
            "highest_sufficient_threshold": compact_threshold_row(highest_sufficient),
            "required_threshold_count": required_count,
            "sample_shortage_at_required_threshold": missing_at_required,
            "sample_shortage_at_highest_sampled_threshold": missing_at_highest_sampled,
            "points_from_required_threshold": points_from_required,
            "usable_points_from_required_threshold": usable_points_from_required,
            "recommendation": score_calibration_recommendation(
                status=status,
                min_threshold=min_threshold,
                min_count=min_count,
                highest_sampled=highest_sampled,
                highest_sufficient=highest_sufficient,
                missing_at_required=missing_at_required,
            ),
        }
    )
    return diagnostic


def score_calibration_recommendation(
    *,
    status: str,
    min_threshold: float,
    min_count: int,
    highest_sampled: dict[str, object] | None,
    highest_sufficient: dict[str, object] | None,
    missing_at_required: int,
) -> str:
    if status == "ready":
        return f"Score gate has at least {min_count} samples at or above {min_threshold}."
    if status == "no_scored_candidates":
        return "No scored candidates are available; collect history or lower pre-filtering before calibrating score."
    sampled_text = (
        f"highest sampled score >= {highest_sampled.get('threshold')} has count {highest_sampled.get('count')}"
        if isinstance(highest_sampled, dict)
        else "no sampled score threshold"
    )
    sufficient_text = (
        f"highest count-sufficient score >= {highest_sufficient.get('threshold')} has count {highest_sufficient.get('count')}"
        if isinstance(highest_sufficient, dict)
        else f"no threshold has {min_count} samples"
    )
    return (
        f"{sampled_text}; {sufficient_text}. "
        f"Need {missing_at_required} more samples at score >= {min_threshold}, or recalibrate score scale."
    )


def score_threshold_degradation_check(rows: list[dict[str, object]], *, max_avg_r_drop: float) -> dict[str, object]:
    ordered = sorted(rows, key=lambda row: number(row.get("threshold")))
    worst_drop = 0.0
    worst_pair: dict[str, object] | str = "not_available"
    previous: dict[str, object] | None = None
    for row in ordered:
        if previous is not None:
            drop = number(previous.get("avg_r")) - number(row.get("avg_r"))
            if drop > worst_drop:
                worst_drop = drop
                worst_pair = {
                    "from_threshold": previous.get("threshold"),
                    "from_avg_r": previous.get("avg_r"),
                    "to_threshold": row.get("threshold"),
                    "to_avg_r": row.get("avg_r"),
                    "drop": round(drop, 4),
                }
        previous = row
    return check(
        "score_threshold_avg_r_not_degrading",
        worst_drop <= max_avg_r_drop,
        worst_pair,
        f"drop <= {max_avg_r_drop}",
    )


def forward_side_checks(
    summary: dict[str, object],
    *,
    min_side_closed: int,
    min_side_pf: float,
    min_side_avg_r: float,
) -> list[dict[str, object]]:
    side_rows = summary.get("by_action") if isinstance(summary, dict) else None
    if not isinstance(side_rows, list):
        return [
            check(
                "forward_side_breakdown",
                False,
                "missing",
                "by_action rows for buy and sell are required",
            )
        ]
    rows_by_side = {str(row.get("group")): row for row in side_rows if isinstance(row, dict)}
    checks: list[dict[str, object]] = []
    for side in ("buy", "sell"):
        row = rows_by_side.get(side, {})
        closed = number(row.get("closed"))
        pf = number(row.get("pf"))
        avg_r = number(row.get("avg_r"))
        checks.append(
            check(
                f"forward_{side}_closed_count",
                closed >= min_side_closed,
                row.get("closed", 0),
                f">= {min_side_closed}",
            )
        )
        if closed >= min_side_closed:
            checks.append(check(f"forward_{side}_pf", pf >= min_side_pf, row.get("pf", 0), f">= {min_side_pf}"))
            checks.append(check(f"forward_{side}_avg_r", avg_r >= min_side_avg_r, row.get("avg_r", 0), f">= {min_side_avg_r}"))
        else:
            checks.append(
                check(
                    f"forward_{side}_pf",
                    False,
                    row.get("pf", 0),
                    f">= {min_side_pf} with closed >= {min_side_closed}",
                )
            )
            checks.append(
                check(
                    f"forward_{side}_avg_r",
                    False,
                    row.get("avg_r", 0),
                    f">= {min_side_avg_r} with closed >= {min_side_closed}",
                )
            )
    return checks


def dry_run_command_safety_checks(audit: dict[str, object], *, min_score: float) -> list[dict[str, object]]:
    signal = audit.get("signal") if isinstance(audit.get("signal"), dict) else {}
    command = audit.get("command") if isinstance(audit.get("command"), dict) else {}
    signal_action = str(signal.get("action") or "").lower()
    command_status = str(command.get("status") or "").lower()
    if signal_action not in {"buy", "sell"}:
        lot_policy = command.get("lot_policy") if isinstance(command.get("lot_policy"), dict) else {}
        value = {
            "signal_action": signal_action or "missing",
            "command_status": command_status or "missing",
            "reason": command.get("reason"),
            "lot_policy": lot_policy if lot_policy else "missing",
        }
        return [
            check(
                "dry_run_command_sl_tp_present",
                True,
                value,
                "not required for non-tradable signal command",
            ),
            check(
                "dry_run_command_score_floor",
                True,
                value,
                "not required for non-tradable signal command",
            ),
            check(
                "dry_run_command_spread_limit_present",
                True,
                value,
                "not required for non-tradable signal command",
            ),
            check(
                "dry_run_command_lot_policy_present",
                lot_policy_has_required_limits(lot_policy),
                value,
                "lot_policy includes base_volume=0.1 and max_total_volume=0.3",
            ),
        ]
    if not command.get("present"):
        missing = {"signal_action": signal_action, "command_status": "missing"}
        return [
            check("dry_run_command_sl_tp_present", False, missing, "tradable dry-run command includes SL and TP"),
            check("dry_run_command_score_floor", False, missing, f"source signal score >= {min_score}"),
            check("dry_run_command_spread_limit_present", False, missing, "max_spread_points is configured"),
            check(
                "dry_run_command_lot_policy_present",
                False,
                missing,
                "lot_policy includes base_volume=0.1 and max_total_volume=0.3",
            ),
        ]
    lot_policy = command.get("lot_policy") if isinstance(command.get("lot_policy"), dict) else {}
    sl_tp_value = {
        "status": command_status,
        "action": command.get("action"),
        "sl": command.get("sl"),
        "tp": command.get("tp"),
        "reason": command.get("reason"),
    }
    score_value = {
        "status": command_status,
        "source_score": command.get("source_score"),
        "source_mode": command.get("source_mode"),
    }
    spread_value = {
        "status": command_status,
        "max_spread_points": command.get("max_spread_points"),
    }
    lot_policy_value = {
        "status": command_status,
        "lot_policy": lot_policy if lot_policy else "missing",
    }
    return [
        check(
            "dry_run_command_sl_tp_present",
            numeric_value_present(command.get("sl")) and numeric_value_present(command.get("tp")),
            sl_tp_value,
            "tradable dry-run command includes numeric SL and TP",
        ),
        check(
            "dry_run_command_score_floor",
            numeric_value_present(command.get("source_score")) and number(command.get("source_score")) >= min_score,
            score_value,
            f"source signal score >= {min_score}",
        ),
        check(
            "dry_run_command_spread_limit_present",
            numeric_value_present(command.get("max_spread_points")) and number(command.get("max_spread_points")) > 0,
            spread_value,
            "max_spread_points is configured and > 0",
        ),
        check(
            "dry_run_command_lot_policy_present",
            lot_policy_has_required_limits(lot_policy),
            lot_policy_value,
            "lot_policy includes base_volume=0.1 and max_total_volume=0.3",
        ),
    ]


def lot_policy_has_required_limits(lot_policy: object) -> bool:
    if not isinstance(lot_policy, dict):
        return False
    return (
        numeric_value_present(lot_policy.get("base_volume"))
        and abs(number(lot_policy.get("base_volume")) - 0.1) <= 1e-9
        and numeric_value_present(lot_policy.get("max_total_volume"))
        and abs(number(lot_policy.get("max_total_volume")) - 0.3) <= 1e-9
    )


def mt5_forward_side_checks(
    summary: dict[str, object],
    *,
    min_side_closed: int,
    min_side_pf: float,
    min_side_avg_price_r: float,
    max_side_total_r_share: float = 0.85,
) -> list[dict[str, object]]:
    side_rows = summary.get("by_action") if isinstance(summary, dict) else None
    if not isinstance(side_rows, list):
        return [
            check(
                "mt5_forward_side_breakdown",
                False,
                "missing",
                "by_action rows for buy and sell are required",
            )
        ]
    rows_by_side = {str(row.get("group")): row for row in side_rows if isinstance(row, dict)}
    checks: list[dict[str, object]] = []
    for side in ("buy", "sell"):
        row = rows_by_side.get(side, {})
        closed = number(row.get("closed"))
        pf = number(row.get("pf"))
        avg_price_r = number(row.get("avg_price_r"))
        checks.append(
            check(
                f"mt5_forward_{side}_closed_count",
                closed >= min_side_closed,
                row.get("closed", 0),
                f">= {min_side_closed}",
            )
        )
        if closed >= min_side_closed:
            checks.append(check(f"mt5_forward_{side}_pf", pf >= min_side_pf, row.get("pf", 0), f">= {min_side_pf}"))
            checks.append(
                check(
                    f"mt5_forward_{side}_avg_price_r",
                    avg_price_r >= min_side_avg_price_r,
                    row.get("avg_price_r", 0),
                    f">= {min_side_avg_price_r}",
                )
            )
        else:
            checks.append(
                check(
                    f"mt5_forward_{side}_pf",
                    False,
                    row.get("pf", 0),
                    f">= {min_side_pf} with closed >= {min_side_closed}",
                )
            )
            checks.append(
                check(
                    f"mt5_forward_{side}_avg_price_r",
                    False,
                    row.get("avg_price_r", 0),
                    f">= {min_side_avg_price_r} with closed >= {min_side_closed}",
                )
            )
    checks.append(
        mt5_side_total_price_r_balance_check(
            rows_by_side,
            name="mt5_forward_side_total_price_r_balance",
            max_side_total_r_share=max_side_total_r_share,
        )
    )
    return checks


def mt5_side_total_price_r_balance_check(
    rows_by_side: dict[str, dict[str, object]],
    *,
    name: str,
    max_side_total_r_share: float,
) -> dict[str, object]:
    shares = mt5_side_total_price_r_shares(rows_by_side)
    if not shares:
        return check(name, True, "not_available", f"max positive side price-R share <= {max_side_total_r_share}")
    max_share = max(shares.values())
    return check(
        name,
        max_share <= max_side_total_r_share,
        {side: round(share, 4) for side, share in shares.items()},
        f"max positive side price-R share <= {max_side_total_r_share}",
    )


def mt5_side_total_price_r_shares(rows_by_side: dict[str, dict[str, object]]) -> dict[str, float]:
    positive_totals: dict[str, float] = {}
    for side in ("buy", "sell"):
        row = rows_by_side.get(side, {})
        total_price_r = mt5_side_total_price_r(row)
        if total_price_r is not None and total_price_r > 0:
            positive_totals[side] = total_price_r
    denominator = sum(positive_totals.values())
    if denominator <= 0:
        return {}
    return {side: total_price_r / denominator for side, total_price_r in positive_totals.items()}


def mt5_side_total_price_r(row: dict[str, object]) -> float | None:
    if not numeric_value_present(row.get("avg_price_r")):
        return None
    count_value = row.get("price_r_count") if numeric_value_present(row.get("price_r_count")) else row.get("closed")
    if not numeric_value_present(count_value):
        return None
    return number(row.get("avg_price_r")) * number(count_value)


def side_balance_weak_side(check_row: dict[str, object], *, default: str = "both") -> str:
    value = check_row.get("value")
    if not isinstance(value, dict):
        return default if default in {"buy", "sell"} else "sell"
    buy_share = value.get("buy")
    sell_share = value.get("sell")
    if numeric_value_present(buy_share) and numeric_value_present(sell_share):
        return "buy" if number(buy_share) < number(sell_share) else "sell"
    if numeric_value_present(buy_share) and not numeric_value_present(sell_share):
        return "sell"
    if numeric_value_present(sell_share) and not numeric_value_present(buy_share):
        return "buy"
    return default if default in {"buy", "sell"} else "sell"


def mt5_forward_button_safety_check(summary: dict[str, object], *, required: bool) -> dict[str, object]:
    button = summary.get("button") if isinstance(summary, dict) else None
    if not isinstance(button, dict):
        return check(
            "mt5_forward_button_dry_run_only",
            not required,
            "missing",
            "button unsafe count = 0",
        )
    unsafe = number(button.get("unsafe"))
    return check(
        "mt5_forward_button_dry_run_only",
        unsafe == 0,
        button.get("unsafe", 0),
        "button unsafe count = 0",
    )


def mt5_forward_risk_exposure_checks(summary: dict[str, object], *, required: bool) -> list[dict[str, object]]:
    risk = summary.get("risk_exposure") if isinstance(summary, dict) else None
    source_checks = summary.get("checks") if isinstance(summary, dict) else None
    if not isinstance(risk, dict) or not isinstance(source_checks, dict):
        return [
            check(
                "mt5_forward_risk_exposure",
                not required,
                "missing_not_required" if not required else "missing",
                "risk_exposure and MT5 forward safety checks are required",
            )
        ]
    mapping = {
        "max_single_volume": "mt5_forward_max_single_volume",
        "max_concurrent_volume": "mt5_forward_max_concurrent_volume",
        "max_concurrent_positions": "mt5_forward_max_concurrent_positions",
        "daily_loss_stop_open_breaches": "mt5_forward_daily_loss_stop_open_breaches",
        "consecutive_loss_stop_open_breaches": "mt5_forward_consecutive_loss_stop_open_breaches",
    }
    checks: list[dict[str, object]] = []
    for source_name, gate_name in mapping.items():
        source = source_checks.get(source_name)
        if not isinstance(source, dict):
            checks.append(check(gate_name, False, "missing", "MT5 forward report check is required"))
            continue
        checks.append(
            check(
                gate_name,
                source.get("ok") is True,
                source.get("actual", "missing"),
                source.get("required", source.get("required_max", "required")),
            )
        )
    return checks


def mt5_forward_csv_schema_checks(summary: dict[str, object], *, required: bool) -> list[dict[str, object]]:
    schema = summary.get("csv_schema") if isinstance(summary, dict) else None
    if not isinstance(schema, dict):
        if not required:
            return []
        return [
            check(
                "mt5_forward_csv_schema",
                False,
                "missing",
                "csv_schema diagnostics are required",
            )
        ]
    return [
        check(
            "mt5_forward_entry_time_diagnostics",
            schema.get("entry_time_diagnostics_available") is True,
            {
                "available": schema.get("entry_time_diagnostics_available"),
                "missing_fields": schema.get("missing_fields", []),
                "unavailable_fields": schema.get("unavailable_fields", []),
            },
            "entry-time diagnostics available",
        ),
        check(
            "mt5_forward_trend_diagnostics",
            schema.get("trend_diagnostics_available") is True,
            {
                "available": schema.get("trend_diagnostics_available"),
                "missing_fields": schema.get("missing_fields", []),
                "unavailable_fields": schema.get("unavailable_fields", []),
            },
            "trend diagnostics available",
        ),
        check(
            "mt5_forward_execution_diagnostics",
            schema.get("execution_diagnostics_available") is True,
            {
                "available": schema.get("execution_diagnostics_available"),
                "missing_execution_fields": schema.get("missing_execution_fields", []),
                "unavailable_execution_fields": schema.get("unavailable_execution_fields", []),
            },
            "execution diagnostics available for price-R, slippage, spread, and latency",
        ),
    ]


def mt5_forward_sl_tp_diagnostic_checks(summary: dict[str, object], *, required: bool) -> list[dict[str, object]]:
    keys = (
        "by_stop_points",
        "by_take_profit_points",
        "by_risk_reward_stop_points",
        "by_risk_reward_take_profit_points",
        "weak_sl_tp_segments",
    )
    return [
        mt5_optimization_diagnostic_key_check(
            "mt5_forward_sl_tp_diagnostics",
            summary,
            required=required,
            keys=keys,
            requirement="MT5 Forward SL/TP Diagnostics including RR x SL and RR x TP breakdowns are present",
            optional_hint="--require-mt5-forward is set",
        )
    ]


def mt5_forward_diagnostic_warning_checks(summary: dict[str, object], *, required: bool) -> list[dict[str, object]]:
    warnings = summary.get("diagnostic_warnings") if isinstance(summary, dict) else None
    if not isinstance(warnings, list):
        if not required:
            return []
        return [
            check(
                "mt5_forward_diagnostic_warnings_clear",
                False,
                "missing",
                "diagnostic_warnings list is required",
            )
        ]
    return [
        check(
            "mt5_forward_diagnostic_warnings_clear",
            len(warnings) == 0,
            warnings[:5],
            "diagnostic_warnings empty",
        )
    ]


def mt5_forward_side_score_checks(summary: dict[str, object]) -> list[dict[str, object]]:
    return mt5_side_score_checks(summary, prefix="mt5_forward")


def mt5_side_score_checks(summary: dict[str, object], *, prefix: str) -> list[dict[str, object]]:
    rows = summary.get("side_score_diagnostics") if isinstance(summary, dict) else None
    if not isinstance(rows, list):
        return []
    checks: list[dict[str, object]] = []
    for side in ("buy", "sell"):
        side_rows = [row for row in rows if isinstance(row, dict) and str(row.get("side")) == side]
        if not side_rows:
            continue
        row = side_rows[0]
        status = str(row.get("status") or "")
        checks.append(
            check(
                f"{prefix}_{side}_score_not_inverted",
                status != "score_inversion",
                {
                    "status": status,
                    "base_pf": row.get("base_pf"),
                    "high_pf": row.get("high_pf"),
                    "recommendation": row.get("recommendation"),
                },
                "status != score_inversion",
            )
        )
    return checks


def mt5_optimization_checks(
    summary: dict[str, object],
    *,
    required: bool,
    min_closed: int,
    min_pf: float,
    min_side_closed: int,
    min_side_pf: float,
    min_side_avg_price_r: float,
    min_forward_pf: float,
    min_forward_trades: int,
    min_positive_forward_back: int,
    max_drawdown_price_r: float = 0.0,
    min_expectancy_price_r: float | None = None,
    max_side_total_r_share: float = 0.85,
) -> list[dict[str, object]]:
    if not summary:
        return [
            check(
                "mt5_optimization_report",
                not required,
                "missing",
                "latest_mt5_optimization_report.json summary is required",
            )
        ]

    overall = mt5_optimization_overall(summary)
    checks = [
        check(
            "mt5_optimization_closed_count",
            number(overall.get("closed")) >= min_closed,
            overall.get("closed", 0),
            f">= {min_closed}",
        ),
        check(
            "mt5_optimization_pf",
            number(overall.get("pf")) >= min_pf,
            overall.get("pf", 0),
            f">= {min_pf}",
        ),
    ]
    checks.extend(
        optional_risk_stat_checks(
            "mt5_optimization",
            overall,
            drawdown_key="max_drawdown_price_r",
            max_drawdown=max_drawdown_price_r,
            expectancy_key="expectancy_price_r",
            min_expectancy=min_expectancy_price_r,
        )
    )
    if required or isinstance(summary.get("by_action"), list):
        checks.extend(
            mt5_optimization_side_checks(
                summary,
                min_side_closed=min_side_closed,
                min_side_pf=min_side_pf,
                min_side_avg_price_r=min_side_avg_price_r,
                max_side_total_r_share=max_side_total_r_share,
            )
        )
    checks.extend(
        mt5_optimization_tester_xml_checks(
            summary,
            required=required,
            min_forward_pf=min_forward_pf,
            min_forward_trades=min_forward_trades,
            min_positive_forward_back=min_positive_forward_back,
        )
    )
    checks.extend(mt5_optimization_pass_budget_checks(summary, prefix="mt5_optimization"))
    checks.extend(mt5_optimization_source_time_checks(summary, prefix="mt5_optimization"))
    checks.extend(mt5_optimization_sl_tp_diagnostic_checks(summary, required=required))
    checks.extend(mt5_optimization_chronological_checks(summary, required=required))
    checks.extend(mt5_optimization_regime_diagnostic_checks(summary, required=required))
    if isinstance(summary.get("side_score_diagnostics"), list):
        checks.extend(mt5_side_score_checks(summary, prefix="mt5_optimization"))
    elif required:
        checks.append(
            check(
                "mt5_optimization_score_diagnostics",
                False,
                "missing",
                "side_score_diagnostics rows are required",
            )
        )
    return checks


def mt5_optimization_recommendation_checks(recommendation: dict[str, object]) -> list[dict[str, object]]:
    decision = recommendation.get("decision") if isinstance(recommendation, dict) else None
    set_metadata = recommendation.get("set_metadata") if isinstance(recommendation, dict) else None
    adoptable = mt5_recommendation_adoptable(decision)
    if isinstance(decision, dict):
        decision_value: object = {
            "adoptable": decision.get("adoptable"),
            "reasons": decision.get("reasons", [])[:5] if isinstance(decision.get("reasons"), list) else [],
        }
    else:
        decision_value = decision if decision is not None else "missing"
    next_set_value: object
    next_set_ready = False
    if isinstance(set_metadata, dict):
        next_set_ready = set_metadata.get("diagnostic_only") is not True and set_metadata.get("skipped_write") is not True
        next_set_value = {
            "path": set_metadata.get("path"),
            "focus_side": set_metadata.get("focus_side"),
            "diagnostic_only": set_metadata.get("diagnostic_only"),
            "skipped_write": set_metadata.get("skipped_write"),
            "skip_reason": set_metadata.get("skip_reason", ""),
        }
    else:
        next_set_value = "missing"
    return [
        check(
            "mt5_optimization_recommendation_adoptable",
            adoptable,
            decision_value,
            "recommendation decision adoptable=true",
        ),
        check(
            "mt5_optimization_recommendation_next_set_written",
            next_set_ready,
            next_set_value,
            "set_metadata diagnostic_only=false and skipped_write=false",
        ),
    ]


def mt5_tester_run_checks(summary: dict[str, object]) -> list[dict[str, object]]:
    if not isinstance(summary, dict) or not summary:
        return []
    ok_present = "ok" in summary
    run_ok = summary.get("ok") is not False
    missing_present = "agent_csv_archive_missing" in summary
    missing = summary.get("agent_csv_archive_missing") is True
    source_time_present = "source_time_blocked" in summary
    source_time_blocked = summary.get("source_time_blocked") is True
    report_paths_raw = summary.get("report_paths")
    report_paths = report_paths_raw if isinstance(report_paths_raw, dict) else {}
    report_paths_present = isinstance(report_paths_raw, dict)
    report_source = str(report_paths.get("source", "") or "")
    normal_run = summary.get("collect_only") is False and summary.get("dry_run") is False
    normal_unblocked_run = normal_run and summary.get("blocked") is not True
    launched_normal_run = (
        normal_run
        and summary.get("blocked") is not True
        and summary.get("terminal_failed") is not True
    )
    archive_payload_raw = summary.get("agent_csv_archive")
    archive_payload = archive_payload_raw if isinstance(archive_payload_raw, dict) else {}
    archive_payload_present = isinstance(archive_payload_raw, dict)
    archive_requested = summary.get("archive_agent_csvs_before_run") is True or archive_payload.get("requested") is True
    archive_payload_ok = archive_payload.get("ok") is not False
    archived_count = int(number(archive_payload.get("count"))) if numeric_value_present(archive_payload.get("count")) else 0
    archive_source_time_coverage = (
        archive_payload.get("source_time_coverage")
        if isinstance(archive_payload.get("source_time_coverage"), dict)
        else {}
    )
    archive_source_time_required = normal_unblocked_run and archive_requested and archived_count > 0
    archive_source_time_present = bool(archive_source_time_coverage) and numeric_value_present(
        archive_source_time_coverage.get("close_rows")
    )
    archive_ok = (
        ((not normal_unblocked_run) or (not missing_present) or not missing)
        and ((not archive_requested and not archive_payload_present) or archive_payload_ok)
        and ((not archive_source_time_required) or archive_source_time_present)
    )
    runner_report_fallback_blocked = summary.get("report_fallback_blocked") is True
    report_paths_ok = (
        not runner_report_fallback_blocked
        and ((not report_paths_present) or (not launched_normal_run) or report_source == "requested_report")
    )
    terminal_run_raw = summary.get("terminal_run")
    terminal_run = terminal_run_raw if isinstance(terminal_run_raw, dict) else {}
    terminal_present = isinstance(terminal_run_raw, dict)
    runner_terminal_failed = summary.get("terminal_failed") is True
    terminal_dry_run = terminal_run.get("dry_run") is True
    terminal_timeout = terminal_run.get("timeout") is True
    terminal_returncode = terminal_run.get("returncode")
    terminal_returncode_ok = terminal_returncode in (0, "0")
    terminal_ok = (
        not runner_terminal_failed
        and ((not terminal_present) or terminal_dry_run or (not terminal_timeout and terminal_returncode_ok))
    )
    blocked_components_raw = summary.get("blocked_components")
    blocked_components = blocked_components_raw if isinstance(blocked_components_raw, dict) else {}
    risk_preset_raw = summary.get("risk_preset")
    risk_preset = risk_preset_raw if isinstance(risk_preset_raw, dict) else {}
    risk_preset_inputs = risk_preset.get("inputs") if isinstance(risk_preset.get("inputs"), dict) else {}
    missing_risk_preset_inputs = [
        name for name in RISK_PRESET_REQUIRED_INPUTS if name not in risk_preset_inputs
    ]
    risk_preset_schema_required = summary.get("ok") is True and normal_run
    risk_preset_schema_ok = (
        not risk_preset_schema_required
        or (
            isinstance(risk_preset_raw, dict)
            and risk_preset.get("ok") is not False
            and not missing_risk_preset_inputs
        )
    )
    value = {
        "generated_at": summary.get("generated_at", ""),
        "ok": summary.get("ok"),
        "blocked": summary.get("blocked", "not_reported"),
        "blocked_components": blocked_components if blocked_components else "not_reported",
        "compile_blocked": summary.get("compile_blocked", "not_reported"),
        "risk_preset_blocked": summary.get("risk_preset_blocked", "not_reported"),
        "tester_set_sync_blocked": summary.get("tester_set_sync_blocked", "not_reported"),
        "target_tester_set_sync": (
            summary.get("target_tester_set_sync")
            if isinstance(summary.get("target_tester_set_sync"), dict)
            else "not_reported"
        ),
        "agent_csv_archive_blocked": summary.get("agent_csv_archive_blocked", "not_reported"),
        "running_terminal_blocked": summary.get("running_terminal_blocked", "not_reported"),
        "running_terminal_detection_enabled": summary.get("running_terminal_detection_enabled", "not_reported"),
        "running_terminal_processes": summary.get("running_terminal_processes", "not_reported"),
        "collect_only": summary.get("collect_only"),
        "dry_run": summary.get("dry_run"),
        "archive_agent_csvs_before_run": summary.get("archive_agent_csvs_before_run"),
        "agent_csv_archive_required": summary.get("agent_csv_archive_required"),
        "agent_csv_archive_missing": summary.get("agent_csv_archive_missing", "not_reported"),
        "agent_csv_archive_run_id": summary.get("agent_csv_archive_run_id", ""),
        "agent_csv_archive_payload_present": archive_payload_present,
        "agent_csv_archive_ok": archive_payload.get("ok", "not_reported") if archive_payload_present else "not_reported",
        "agent_csv_archive_count": archive_payload.get("count", "not_reported") if archive_payload_present else "not_reported",
        "agent_csv_archive_source_time": archive_source_time_coverage if archive_source_time_coverage else "not_reported",
        "source_time_blocked": summary.get("source_time_blocked", "not_reported"),
        "report_source": report_source if report_paths_present else "not_reported",
        "report_fallback_blocked": summary.get("report_fallback_blocked", "not_reported"),
        "requested_back_xml": report_paths.get("requested_back_xml", "") if report_paths_present else "",
        "requested_forward_xml": report_paths.get("requested_forward_xml", "") if report_paths_present else "",
        "used_back_xml": report_paths.get("used_back_xml", "") if report_paths_present else "",
        "used_forward_xml": report_paths.get("used_forward_xml", "") if report_paths_present else "",
        "terminal_failed": summary.get("terminal_failed", "not_reported"),
        "terminal_present": terminal_present,
        "terminal_dry_run": terminal_run.get("dry_run", "not_reported") if terminal_present else "not_reported",
        "terminal_returncode": terminal_run.get("returncode", "not_reported") if terminal_present else "not_reported",
        "terminal_timeout": terminal_run.get("timeout", "not_reported") if terminal_present else "not_reported",
        "terminal_started_at": terminal_run.get("started_at", "") if terminal_present else "",
        "terminal_deadline_at": terminal_run.get("deadline_at", "") if terminal_present else "",
        "terminal_elapsed_seconds": terminal_run.get("elapsed_seconds", "") if terminal_present else "",
        "risk_preset": {
            "set_file": risk_preset.get("set_file", ""),
            "mode": risk_preset.get("mode", ""),
            "ok": risk_preset.get("ok", "not_reported"),
            "inputs": risk_preset.get("inputs", {}) if isinstance(risk_preset.get("inputs"), dict) else {},
            "errors": risk_preset.get("errors", []) if isinstance(risk_preset.get("errors"), list) else [],
        }
        if risk_preset
        else "not_reported",
        "risk_preset_schema_required": risk_preset_schema_required,
        "risk_preset_schema_missing_inputs": missing_risk_preset_inputs,
        "warnings": summary.get("warnings", [])[:5] if isinstance(summary.get("warnings"), list) else [],
    }
    return [
        check(
            "mt5_tester_run_ok",
            (not ok_present) or run_ok,
            value,
            "latest mt5_tester_run ok must not be false",
        ),
        check(
            "mt5_tester_run_agent_csv_archive",
            archive_ok,
            value,
            "normal mt5_tester_run launches must archive successfully and keep archived CSV source_time evidence",
        ),
        check(
            "mt5_tester_run_source_time",
            (not source_time_present) or not source_time_blocked,
            value,
            "mt5_tester_run source_time_blocked must be false",
        ),
        check(
            "mt5_tester_run_risk_preset_schema",
            risk_preset_schema_ok,
            value,
            "normal ok mt5_tester_run risk_preset must include current required safety inputs",
        ),
        check(
            "mt5_tester_run_report_paths",
            report_paths_ok,
            value,
            "normal mt5_tester_run must use the requested Tester report XML pair",
        ),
        check(
            "mt5_tester_run_terminal",
            terminal_ok,
            value,
            "terminal_run timeout=false and returncode=0",
        ),
    ]


def mt5_recommendation_adoptable(decision: object) -> bool:
    if isinstance(decision, dict):
        if "adoptable" in decision:
            return decision.get("adoptable") is True
        status = str(decision.get("status") or "").strip().lower()
    else:
        status = str(decision or "").strip().lower()
    return status in {"ready", "adopted", "adoptable", "pass", "passed", "ready_for_next_phase"}


def mt5_optimization_overall(summary: dict[str, object]) -> dict[str, object]:
    overall = summary.get("overall")
    return dict(overall) if isinstance(overall, dict) else {}


def mt5_optimization_side_checks(
    summary: dict[str, object],
    *,
    min_side_closed: int,
    min_side_pf: float,
    min_side_avg_price_r: float,
    max_side_total_r_share: float = 0.85,
) -> list[dict[str, object]]:
    side_rows = summary.get("by_action") if isinstance(summary, dict) else None
    if not isinstance(side_rows, list):
        return [
            check(
                "mt5_optimization_side_breakdown",
                False,
                "missing",
                "by_action rows for buy and sell are required",
            )
        ]
    rows_by_side = {str(row.get("group")): row for row in side_rows if isinstance(row, dict)}
    checks: list[dict[str, object]] = []
    for side in ("buy", "sell"):
        row = rows_by_side.get(side, {})
        closed = number(row.get("closed"))
        pf = number(row.get("pf"))
        avg_price_r = number(row.get("avg_price_r"))
        checks.append(
            check(
                f"mt5_optimization_{side}_closed_count",
                closed >= min_side_closed,
                row.get("closed", 0),
                f">= {min_side_closed}",
            )
        )
        if closed >= min_side_closed:
            checks.append(check(f"mt5_optimization_{side}_pf", pf >= min_side_pf, row.get("pf", 0), f">= {min_side_pf}"))
            checks.append(
                check(
                    f"mt5_optimization_{side}_avg_price_r",
                    avg_price_r >= min_side_avg_price_r,
                    row.get("avg_price_r", 0),
                    f">= {min_side_avg_price_r}",
                )
            )
        else:
            checks.append(
                check(
                    f"mt5_optimization_{side}_pf",
                    False,
                    row.get("pf", 0),
                    f">= {min_side_pf} with closed >= {min_side_closed}",
                )
            )
            checks.append(
                check(
                    f"mt5_optimization_{side}_avg_price_r",
                    False,
                    row.get("avg_price_r", 0),
                    f">= {min_side_avg_price_r} with closed >= {min_side_closed}",
                )
            )
    checks.append(
        mt5_side_total_price_r_balance_check(
            rows_by_side,
            name="mt5_optimization_side_total_price_r_balance",
            max_side_total_r_share=max_side_total_r_share,
        )
    )
    return checks


def mt5_optimization_tester_xml_checks(
    summary: dict[str, object],
    *,
    required: bool,
    min_forward_pf: float,
    min_forward_trades: int,
    min_positive_forward_back: int,
) -> list[dict[str, object]]:
    tester_xml = summary.get("tester_xml") if isinstance(summary, dict) else None
    if not isinstance(tester_xml, dict):
        return [
            check(
                "mt5_optimization_tester_xml",
                not required,
                "missing",
                "Tester Optimization XML summary is required",
            )
        ]
    forward = tester_xml.get("forward")
    if not isinstance(forward, dict):
        return [
            check(
                "mt5_optimization_tester_forward_xml",
                not required,
                "missing",
                "Tester forward XML summary is required",
            )
        ]

    positive_forward_back = number(forward.get("positive_forward_positive_back"))
    top = forward_top_pass(forward)
    checks = [
        check(
            "mt5_optimization_positive_forward_back",
            positive_forward_back >= min_positive_forward_back,
            forward.get("positive_forward_positive_back", 0),
            f">= {min_positive_forward_back}",
        ),
        check(
            "mt5_optimization_top_forward_pf",
            number(top.get("Profit Factor")) >= min_forward_pf,
            top.get("Profit Factor", 0),
            f">= {min_forward_pf}",
        ),
        check(
            "mt5_optimization_top_forward_trades",
            number(top.get("Trades")) >= min_forward_trades,
            top.get("Trades", 0),
            f">= {min_forward_trades}",
        ),
        check(
            "mt5_optimization_top_forward_back_result",
            number(top.get("Back Result")) > 0.0,
            top.get("Back Result", 0),
            "> 0",
        ),
    ]
    return checks


def forward_top_pass(forward_summary: dict[str, object]) -> dict[str, object]:
    rows = forward_summary.get("top")
    if not isinstance(rows, list):
        return {}
    best = max(
        (row for row in rows if isinstance(row, dict)),
        key=lambda row: number(row.get("Forward Result")),
        default={},
    )
    return dict(best)


def stable_forward_top_pass(forward_summary: dict[str, object]) -> dict[str, object]:
    rows = forward_summary.get("stable_top")
    if not isinstance(rows, list):
        return {}
    best = max(
        (row for row in rows if isinstance(row, dict)),
        key=lambda row: number(row.get("Forward Result")),
        default={},
    )
    return dict(best)


def compact_tester_passes(rows: object, *, limit: int) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        return []
    keys = (
        "Pass",
        "Forward Result",
        "Back Result",
        "Profit Factor",
        "Trades",
        "InpBuyRiskReward",
        "InpSellRiskReward",
        "InpMinScore",
        "InpSwingDepth",
        "InpSwingAtrBand",
        "InpStopBufferPoints",
        "InpUseFittedBuyEntryFilter",
        "InpUseFittedBuyCalendarFilter",
        "InpUseFittedSellFilter",
        "InpUseFittedSellTrendFilter",
        "InpUseSellM30M15DownGate",
        "InpUseFittedSellTimeFilter",
        "InpUseFittedSellCalendarFilter",
        "InpUseFittedSellEntryFilter",
    )
    compacted: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        compacted.append({key: row.get(key) for key in keys if key in row})
        if len(compacted) >= limit:
            break
    return compacted


def mt5_optimization_chronological_checks(
    summary: dict[str, object],
    *,
    required: bool,
) -> list[dict[str, object]]:
    rows = summary.get("chronological_splits") if isinstance(summary, dict) else None
    if not isinstance(rows, list):
        if not required:
            return [
                check(
                    "mt5_optimization_chronological_splits",
                    True,
                    "missing_not_required",
                    "chronological_splits optional unless --require-mt5-optimization is set",
                )
            ]
        return [
            check(
                "mt5_optimization_chronological_splits",
                False,
                "missing",
                "chronological_splits rows are required",
            )
        ]
    failed = failed_chronological_splits(rows)
    return [
        check(
            "mt5_optimization_chronological_splits",
            len(failed) == 0,
            compact_segments(failed, limit=6),
            "failed chronological splits = 0",
        )
    ]


def mt5_optimization_sl_tp_diagnostic_checks(
    summary: dict[str, object],
    *,
    required: bool,
    prefix: str = "mt5_optimization",
) -> list[dict[str, object]]:
    keys = (
        "by_stop_points",
        "by_take_profit_points",
        "by_risk_reward_stop_points",
        "by_risk_reward_take_profit_points",
        "best_segments",
        "weak_segments",
    )
    return [
        mt5_optimization_diagnostic_key_check(
            f"{prefix}_sl_tp_diagnostics",
            summary,
            required=required,
            keys=keys,
            requirement="SL/TP Diagnostics including RR x SL and RR x TP breakdowns are present",
        )
    ]


def failed_chronological_splits(rows: object) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        return []
    failed: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        diagnosis = str(row.get("diagnosis") or "").strip()
        if diagnosis or number(row.get("pf")) < 1.0 or number(row.get("avg_price_r")) < 0.0:
            failed.append(dict(row))
    return failed


def mt5_optimization_regime_diagnostic_checks(
    summary: dict[str, object],
    *,
    required: bool,
    prefix: str = "mt5_optimization",
) -> list[dict[str, object]]:
    time_keys = (
        "by_quarter",
        "by_month",
        "by_weekday",
        "by_server_hour",
        "by_entry_server_hour",
        "by_action_risk_reward_month",
        "best_time_segments",
        "weak_time_segments",
    )
    trend_keys = (
        "by_m30_trend",
        "by_m15_trend",
        "by_m5_trend",
        "by_m30_slope",
        "by_m15_slope",
        "by_m30_m15_trend",
        "by_trend_alignment",
        "by_action_trend_alignment",
        "by_action_m30_m15_trend",
        "best_trend_segments",
        "weak_trend_segments",
    )
    return [
        mt5_optimization_diagnostic_key_check(
            f"{prefix}_time_regime_diagnostics",
            summary,
            required=required,
            keys=time_keys,
            informative_keys=("by_entry_server_hour",),
            requirement="Temporal Diagnostics including entry-hour and weak_time_segments are present",
        ),
        mt5_optimization_diagnostic_key_check(
            f"{prefix}_trend_regime_diagnostics",
            summary,
            required=required,
            keys=trend_keys,
            informative_keys=(
                "by_m30_trend",
                "by_m15_trend",
                "by_m5_trend",
                "by_m30_slope",
                "by_m15_slope",
                "by_m30_m15_trend",
                "by_trend_alignment",
                "by_action_trend_alignment",
                "by_action_m30_m15_trend",
            ),
            requirement="Trend Regime Diagnostics including M30/M15/M5, slope, and weak_trend_segments are present",
        ),
    ]


def mt5_optimization_diagnostic_key_check(
    name: str,
    summary: dict[str, object],
    *,
    required: bool,
    keys: tuple[str, ...],
    informative_keys: tuple[str, ...] = (),
    requirement: str,
    optional_hint: str = "--require-mt5-optimization is set",
) -> dict[str, object]:
    requirement_scope = f"{requirement}; required" if required else f"{requirement}; optional unless {optional_hint}"
    missing = [key for key in keys if not isinstance(summary.get(key), list)]
    if missing:
        return check(
            name,
            not required,
            "missing_not_required" if not required else {"missing": missing},
            requirement_scope,
        )
    counts = {key: len(summary.get(key, [])) for key in keys}
    unavailable = [
        key
        for key in informative_keys
        if not mt5_optimization_diagnostic_rows_informative(summary.get(key))
    ]
    if unavailable:
        value: object = {
            "counts": counts,
            "unavailable": unavailable,
        }
        return check(
            name,
            not required,
            value if required else {"optional_unavailable": unavailable, "counts": counts},
            f"{requirement_scope}; informative non-unknown groups are required",
        )
    return check(name, True, counts, requirement)


def mt5_optimization_diagnostic_rows_informative(rows: object) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    for row in rows:
        if not isinstance(row, dict):
            continue
        group = str(row.get("group") or "").strip().lower()
        if group and group != "unknown" and "unknown" not in group:
            return True
    return False


def mt5_yearly_optimization_checks(
    summary: dict[str, object],
    *,
    required: bool,
    min_closed: int,
    min_pf: float,
    min_avg_price_r: float,
    min_positive_forward_back: int,
    max_drawdown_price_r: float = 0.0,
    min_expectancy_price_r: float | None = None,
    max_side_total_r_share: float = 0.85,
) -> list[dict[str, object]]:
    if not summary:
        return [
            check(
                "mt5_yearly_optimization_report",
                not required,
                "missing",
                "yearly/out-of-year MT5 optimization report is required",
            )
        ]

    overall = mt5_optimization_overall(summary)
    checks = [
        check(
            "mt5_yearly_optimization_closed_count",
            number(overall.get("closed")) >= min_closed,
            overall.get("closed", 0),
            f">= {min_closed}",
        ),
        check(
            "mt5_yearly_optimization_pf",
            number(overall.get("pf")) >= min_pf,
            overall.get("pf", 0),
            f">= {min_pf}",
        ),
        check(
            "mt5_yearly_optimization_avg_price_r",
            number(overall.get("avg_price_r")) >= min_avg_price_r,
            overall.get("avg_price_r", 0),
            f">= {min_avg_price_r}",
        ),
    ]
    checks.extend(
        optional_risk_stat_checks(
            "mt5_yearly_optimization",
            overall,
            drawdown_key="max_drawdown_price_r",
            max_drawdown=max_drawdown_price_r,
            expectancy_key="expectancy_price_r",
            min_expectancy=min_expectancy_price_r,
        )
    )
    tester_xml = summary.get("tester_xml") if isinstance(summary, dict) else None
    forward = tester_xml.get("forward") if isinstance(tester_xml, dict) else None
    if not isinstance(forward, dict):
        checks.append(
            check(
                "mt5_yearly_optimization_positive_forward_back",
                False,
                "missing",
                f">= {min_positive_forward_back}",
            )
        )
    else:
        checks.append(
            check(
                "mt5_yearly_optimization_positive_forward_back",
                number(forward.get("positive_forward_positive_back")) >= min_positive_forward_back,
                forward.get("positive_forward_positive_back", 0),
                f">= {min_positive_forward_back}",
            )
    )
    checks.extend(mt5_optimization_pass_budget_checks(summary, prefix="mt5_yearly_optimization"))
    yearly_side_rows = summary.get("by_action") if isinstance(summary, dict) else None
    if isinstance(yearly_side_rows, list):
        rows_by_side = {str(row.get("group")): row for row in yearly_side_rows if isinstance(row, dict)}
        checks.append(
            mt5_side_total_price_r_balance_check(
                rows_by_side,
                name="mt5_yearly_optimization_side_total_price_r_balance",
                max_side_total_r_share=max_side_total_r_share,
            )
        )
    checks.extend(
        mt5_optimization_source_time_checks(
            summary,
            prefix="mt5_yearly_optimization",
            require_expected_range=True,
        )
    )
    checks.extend(
        mt5_optimization_sl_tp_diagnostic_checks(
            summary,
            required=True,
            prefix="mt5_yearly_optimization",
        )
    )
    checks.extend(mt5_yearly_optimization_chronological_checks(summary, required=required))
    checks.extend(
        mt5_optimization_regime_diagnostic_checks(
            summary,
            required=True,
            prefix="mt5_yearly_optimization",
        )
    )
    if isinstance(summary.get("side_score_diagnostics"), list):
        checks.extend(mt5_side_score_checks(summary, prefix="mt5_yearly_optimization"))
    elif required:
        checks.append(
            check(
                "mt5_yearly_optimization_score_diagnostics",
                False,
                "missing",
                "yearly side_score_diagnostics rows are required",
            )
        )
    return checks


def mt5_optimization_pass_budget_checks(summary: dict[str, object], *, prefix: str) -> list[dict[str, object]]:
    budget = summary.get("optimization_pass_budget") if isinstance(summary, dict) else None
    if not isinstance(budget, dict):
        return [
            check(
                f"{prefix}_pass_budget",
                False,
                "missing",
                "optimization_pass_budget with set_file and full-factorial pass count is required",
            ),
            check(
                f"{prefix}_executed_tester_xml_rows",
                False,
                "missing",
                "executed_tester_xml_rows back/forward counts are required",
            ),
        ]
    available = budget.get("available") is True
    pass_count = budget.get("estimated_full_factorial_passes")
    optimized_count = budget.get("optimized_input_count")
    executed_rows = budget.get("executed_tester_xml_rows")
    pass_budget_ok = (
        available
        and bool(str(budget.get("set_file") or "").strip())
        and numeric_value_present(pass_count)
        and number(pass_count) >= 1
        and numeric_value_present(optimized_count)
    )
    rows_ok = (
        isinstance(executed_rows, dict)
        and numeric_value_present(executed_rows.get("back"))
        and numeric_value_present(executed_rows.get("forward"))
    )
    return [
        check(
            f"{prefix}_pass_budget",
            pass_budget_ok,
            {
                "set_file": budget.get("set_file"),
                "available": budget.get("available"),
                "optimized_input_count": optimized_count,
                "estimated_full_factorial_passes": pass_count,
                "reason": budget.get("reason"),
            },
            "set_file available, optimized_input_count present, full_factorial >= 1",
        ),
        check(
            f"{prefix}_executed_tester_xml_rows",
            rows_ok,
            executed_rows if isinstance(executed_rows, dict) else "missing",
            "executed_tester_xml_rows.back and .forward are present",
        ),
    ]


def mt5_optimization_source_time_checks(
    summary: dict[str, object],
    *,
    prefix: str,
    require_expected_range: bool = False,
) -> list[dict[str, object]]:
    diagnostics = summary.get("source_time_diagnostics") if isinstance(summary, dict) else None
    coverage = summary.get("source_time_coverage") if isinstance(summary, dict) else None
    name = f"{prefix}_source_time_range"
    if not isinstance(diagnostics, dict):
        if require_expected_range:
            return [
                check(
                    name,
                    False,
                    "missing",
                    "source_time_diagnostics with expected_from_date/to_date is required",
                )
            ]
        return [
            check(
                name,
                True,
                "missing_not_configured",
                "source_time_diagnostics optional unless expected_from_date/to_date are present",
            )
        ]

    expected_from = str(diagnostics.get("expected_from_date") or "").strip()
    expected_to = str(diagnostics.get("expected_to_date") or "").strip()
    expected_present = bool(expected_from or expected_to)
    value = {
        "expected_from_date": expected_from,
        "expected_to_date": expected_to,
        "actual_first_server_time": diagnostics.get("actual_first_server_time"),
        "actual_last_server_time": diagnostics.get("actual_last_server_time"),
        "matches_expected_range": diagnostics.get("matches_expected_range"),
        "warnings": diagnostics.get("warnings") if isinstance(diagnostics.get("warnings"), list) else [],
    }
    if isinstance(coverage, dict):
        value["close_rows_with_server_time"] = coverage.get("close_rows_with_server_time")
        value["close_rows_without_server_time"] = coverage.get("close_rows_without_server_time")

    if not expected_present:
        if require_expected_range:
            return [
                check(
                    name,
                    False,
                    value,
                    "expected_from_date/to_date are required for source time validation",
                )
            ]
        return [
            check(
                name,
                True,
                value,
                "expected_from_date/to_date not configured; source time range recorded for evidence",
            )
        ]

    return [
        check(
            name,
            diagnostics.get("matches_expected_range") is True,
            value,
            "close server_time first/last must be inside expected Tester FromDate/ToDate",
        )
    ]


def mt5_yearly_optimization_chronological_checks(
    summary: dict[str, object],
    *,
    required: bool,
) -> list[dict[str, object]]:
    rows = summary.get("chronological_splits") if isinstance(summary, dict) else None
    if not isinstance(rows, list):
        return [
            check(
                "mt5_yearly_optimization_chronological_splits",
                False,
                "missing",
                "yearly chronological_splits rows are required when yearly report is evaluated",
            )
        ]
    failed = failed_chronological_splits(rows)
    return [
        check(
            "mt5_yearly_optimization_chronological_splits",
            len(failed) == 0,
            compact_segments(failed, limit=6),
            "failed yearly chronological splits = 0",
        )
    ]


def winrate_fit_checks(summary: dict[str, object], *, required: bool) -> list[dict[str, object]]:
    adoption = summary.get("adoption_decision") if isinstance(summary, dict) else None
    if not isinstance(adoption, dict):
        return [
            check(
                "winrate_fit_adoption_decision",
                not required,
                "missing",
                "adoption_decision.adopted = true",
            )
        ]
    return [
        check(
            "winrate_fit_adoption_decision",
            adoption.get("adopted") is True,
            {
                "adopted": adoption.get("adopted"),
                "reasons": adoption.get("reasons"),
                "rules": adoption.get("rules"),
            },
            "adoption_decision.adopted = true",
        ),
        winrate_fit_walk_forward_check(summary, adoption),
    ]


def winrate_fit_walk_forward_check(
    summary: dict[str, object],
    adoption: dict[str, object],
) -> dict[str, object]:
    rows = summary.get("walk_rows") if isinstance(summary, dict) else None
    if not isinstance(rows, list):
        return check(
            "winrate_fit_walk_forward",
            False,
            "missing",
            "walk-forward aggregate is required",
        )
    aggregate = next(
        (row for row in rows if isinstance(row, dict) and str(row.get("fold")) == "aggregate"),
        None,
    )
    if not isinstance(aggregate, dict):
        return check(
            "winrate_fit_walk_forward",
            False,
            "missing aggregate",
            "walk-forward aggregate is required",
        )
    min_count = int(number(adoption.get("min_test_count"))) if numeric_value_present(adoption.get("min_test_count")) else 1
    min_avg_r = number(adoption.get("min_test_avg_r")) if numeric_value_present(adoption.get("min_test_avg_r")) else 0.0
    min_pf = number(adoption.get("min_test_pf")) if numeric_value_present(adoption.get("min_test_pf")) else 1.0
    total_count = number(aggregate.get("total_test_fitted_count"))
    mean_avg_r = number(aggregate.get("mean_test_fitted_avg_r"))
    mean_pf = number(aggregate.get("mean_test_fitted_pf"))
    value = {
        "folds": aggregate.get("folds"),
        "folds_with_trades": aggregate.get("folds_with_trades"),
        "min_test_fitted_count": aggregate.get("min_test_fitted_count"),
        "total_test_fitted_count": aggregate.get("total_test_fitted_count"),
        "mean_test_fitted_avg_r": aggregate.get("mean_test_fitted_avg_r"),
        "median_test_fitted_avg_r": aggregate.get("median_test_fitted_avg_r"),
        "mean_test_fitted_pf": aggregate.get("mean_test_fitted_pf"),
        "median_test_fitted_pf": aggregate.get("median_test_fitted_pf"),
        "min_required_count": min_count,
        "min_required_avg_r": min_avg_r,
        "min_required_pf": min_pf,
    }
    return check(
        "winrate_fit_walk_forward",
        total_count >= min_count and mean_avg_r >= min_avg_r and mean_pf >= min_pf,
        value,
        f"walk-forward total_test_fitted_count >= {min_count}, mean_test_fitted_avg_r >= {min_avg_r}, and mean_test_fitted_pf >= {min_pf}",
    )


def mt5_compile_checks(summary: dict[str, object], *, required: bool) -> list[dict[str, object]]:
    if not summary:
        return [
            check(
                "mt5_compile_status_report",
                not required,
                "missing",
                "latest_mt5_compile_status.json summary is required",
            )
        ]
    items = compile_item_values(summary)
    return [
        check(
            "mt5_compile_sources_synced",
            summary.get("all_sources_synced") is True,
            items,
            "workspace .mq5 and MT5 .mq5 hashes match",
        ),
        check(
            "mt5_compile_binaries_fresh",
            summary.get("all_compiled_fresh") is True,
            items,
            ".ex5 mtime >= newest .mq5 mtime",
        ),
        *(
            [
                check(
                    "mt5_compile_tester_sets_synced",
                    summary.get("all_tester_sets_synced") is True,
                    tester_set_values(summary),
                    "workspace methods/swing_eval/mt5/TesterSets/*.set and MT5 MQL5/Profiles/Tester/*.set hashes match",
                )
            ]
            if "all_tester_sets_synced" in summary or "tester_sets" in summary
            else []
        ),
        *(
            [
                check(
                    "mt5_compile_tester_configs_synced",
                    summary.get("all_tester_configs_synced") is True,
                    tester_config_values(summary),
                    "workspace methods/swing_eval/mt5/TesterConfigs/*.ini and MT5 MQL5/Profiles/Tester/*.ini hashes match",
                )
            ]
            if "all_tester_configs_synced" in summary or "tester_configs" in summary
            else []
        ),
        *(
            [
                check(
                    "mt5_compile_tester_config_references_ready",
                    summary.get("all_required_tester_config_references_ready") is True,
                    tester_config_reference_values(summary),
                    "Tester config ExpertParameters references resolve to synced required .set files",
                )
            ]
            if "all_required_tester_config_references_ready" in summary
            or "tester_config_references" in summary
            else []
        ),
    ]


def compile_item_values(summary: dict[str, object]) -> list[dict[str, object]]:
    rows = summary.get("items")
    if not isinstance(rows, list):
        return []
    values: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        mt5_source = row.get("mt5_source") if isinstance(row.get("mt5_source"), dict) else {}
        binary = row.get("mt5_binary") if isinstance(row.get("mt5_binary"), dict) else {}
        values.append(
            {
                "kind": row.get("kind"),
                "name": row.get("name"),
                "status": row.get("status"),
                "source_synced": row.get("source_synced"),
                "compiled_fresh": row.get("compiled_fresh"),
                "source_mtime": mt5_source.get("mtime") if isinstance(mt5_source, dict) else "",
                "binary_mtime": binary.get("mtime") if isinstance(binary, dict) else "",
                "stale_seconds": row.get("stale_seconds"),
            }
        )
    return values


def tester_set_values(summary: dict[str, object]) -> list[dict[str, object]]:
    rows = summary.get("tester_sets")
    if not isinstance(rows, list):
        return []
    values: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        workspace_set = row.get("workspace_set") if isinstance(row.get("workspace_set"), dict) else {}
        mt5_set = row.get("mt5_set") if isinstance(row.get("mt5_set"), dict) else {}
        if row.get("synced") is True:
            continue
        values.append(
            {
                "name": row.get("name"),
                "status": row.get("status"),
                "synced": row.get("synced"),
                "workspace_mtime": workspace_set.get("mtime") if isinstance(workspace_set, dict) else "",
                "mt5_mtime": mt5_set.get("mtime") if isinstance(mt5_set, dict) else "",
                "workspace_path": workspace_set.get("path") if isinstance(workspace_set, dict) else "",
                "mt5_path": mt5_set.get("path") if isinstance(mt5_set, dict) else "",
            }
        )
    return values


def tester_config_values(summary: dict[str, object]) -> list[dict[str, object]]:
    rows = summary.get("tester_configs")
    if not isinstance(rows, list):
        return []
    values: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        workspace_config = row.get("workspace_config") if isinstance(row.get("workspace_config"), dict) else {}
        mt5_config = row.get("mt5_config") if isinstance(row.get("mt5_config"), dict) else {}
        if row.get("synced") is True:
            continue
        values.append(
            {
                "name": row.get("name"),
                "status": row.get("status"),
                "synced": row.get("synced"),
                "workspace_mtime": workspace_config.get("mtime") if isinstance(workspace_config, dict) else "",
                "mt5_mtime": mt5_config.get("mtime") if isinstance(mt5_config, dict) else "",
                "workspace_path": workspace_config.get("path") if isinstance(workspace_config, dict) else "",
                "mt5_path": mt5_config.get("path") if isinstance(mt5_config, dict) else "",
            }
        )
    return values


def tester_config_reference_values(summary: dict[str, object]) -> list[dict[str, object]]:
    rows = summary.get("tester_config_references")
    if not isinstance(rows, list):
        return []
    values: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("ready") is True or row.get("generated_set_missing") is True:
            continue
        workspace_set = row.get("workspace_set") if isinstance(row.get("workspace_set"), dict) else {}
        mt5_set = row.get("mt5_set") if isinstance(row.get("mt5_set"), dict) else {}
        values.append(
            {
                "name": row.get("name"),
                "expert_parameters": row.get("expert_parameters"),
                "status": row.get("status"),
                "ready": row.get("ready"),
                "generated_set_missing": row.get("generated_set_missing"),
                "workspace_path": workspace_set.get("path") if isinstance(workspace_set, dict) else "",
                "mt5_path": mt5_set.get("path") if isinstance(mt5_set, dict) else "",
            }
        )
    return values


def side_checks(
    side_rows: list[dict[str, object]],
    *,
    min_side_count: int,
    min_side_pf: float,
    min_side_avg_r: float = 0.0,
    max_side_total_r_share: float = 0.85,
) -> list[dict[str, object]]:
    rows_by_side = {str(row.get("group")): row for row in side_rows}
    checks: list[dict[str, object]] = []
    for side in ("buy", "sell"):
        row = rows_by_side.get(side, {})
        count = number(row.get("count"))
        pf = number(row.get("pf"))
        avg_r = number(row.get("avg_r"))
        checks.append(check(f"{side}_count", count >= min_side_count, row.get("count", 0), f">= {min_side_count}"))
        if count >= min_side_count:
            checks.append(check(f"{side}_pf", pf >= min_side_pf, row.get("pf", 0), f">= {min_side_pf}"))
            checks.append(check(f"{side}_avg_r", avg_r >= min_side_avg_r, row.get("avg_r", 0), f">= {min_side_avg_r}"))
        else:
            checks.append(check(f"{side}_pf", False, row.get("pf", 0), f">= {min_side_pf} with count >= {min_side_count}"))
            checks.append(check(f"{side}_avg_r", False, row.get("avg_r", 0), f">= {min_side_avg_r} with count >= {min_side_count}"))
    checks.append(side_total_r_balance_check(rows_by_side, max_side_total_r_share=max_side_total_r_share))
    return checks


def side_total_r_balance_check(rows_by_side: dict[str, dict[str, object]], *, max_side_total_r_share: float) -> dict[str, object]:
    shares = side_total_r_shares(rows_by_side)
    if not shares:
        return check("side_total_r_balance", True, "not_available", f"max positive side share <= {max_side_total_r_share}")
    max_share = max(shares.values())
    return check(
        "side_total_r_balance",
        max_share <= max_side_total_r_share,
        {side: round(share, 4) for side, share in shares.items()},
        f"max positive side share <= {max_side_total_r_share}",
    )


def side_total_r_shares(rows_by_side: dict[str, dict[str, object]]) -> dict[str, float]:
    positive_totals: dict[str, float] = {}
    for side in ("buy", "sell"):
        row = rows_by_side.get(side, {})
        if "total_r" not in row:
            continue
        total_r = number(row.get("total_r"))
        if total_r > 0:
            positive_totals[side] = total_r
    denominator = sum(positive_totals.values())
    if denominator <= 0:
        return {}
    return {side: total_r / denominator for side, total_r in positive_totals.items()}


def optional_risk_stat_checks(
    prefix: str,
    row: dict[str, object],
    *,
    drawdown_key: str,
    max_drawdown: float,
    expectancy_key: str,
    min_expectancy: float | None,
) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    if max_drawdown > 0:
        checks.append(numeric_max_check(f"{prefix}_{drawdown_key}", row.get(drawdown_key), max_drawdown))
    if min_expectancy is not None:
        checks.append(numeric_min_check(f"{prefix}_{expectancy_key}", row.get(expectancy_key), min_expectancy))
    return checks


def numeric_max_check(name: str, value: object, maximum: float) -> dict[str, object]:
    return check(name, numeric_value_present(value) and number(value) <= maximum, value_or_missing(value), f"<= {maximum}")


def numeric_min_check(name: str, value: object, minimum: float) -> dict[str, object]:
    return check(name, numeric_value_present(value) and number(value) >= minimum, value_or_missing(value), f">= {minimum}")


def numeric_value_present(value: object) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def value_or_missing(value: object) -> object:
    return value if numeric_value_present(value) else "missing"


def check(name: str, passed: bool, value: object, requirement: object) -> dict[str, object]:
    return {
        "name": name,
        "passed": bool(passed),
        "value": value,
        "requirement": requirement,
    }


def mt5_stable_candidate_result_summary(
    summary: dict[str, object],
    recommendation: dict[str, object],
    tester_run: dict[str, object],
) -> dict[str, object]:
    if not summary and not recommendation and not tester_run:
        return {}
    overall = mt5_optimization_overall(summary) if isinstance(summary, dict) else {}
    closed = number(overall.get("closed"))
    budget = summary.get("optimization_pass_budget") if isinstance(summary, dict) else {}
    executed_rows = budget.get("executed_tester_xml_rows") if isinstance(budget, dict) else {}
    has_executed_rows = (
        isinstance(executed_rows, dict)
        and (number(executed_rows.get("back")) > 0 or number(executed_rows.get("forward")) > 0)
    )
    if closed <= 0 and not has_executed_rows:
        return {}
    decision = recommendation.get("decision") if isinstance(recommendation.get("decision"), dict) else {}
    reasons = decision.get("reasons") if isinstance(decision, dict) else []
    tester_ok: object = tester_run.get("ok") if isinstance(tester_run, dict) and "ok" in tester_run else "not_reported"
    return {
        "closed": overall.get("closed"),
        "pf": overall.get("pf"),
        "avg_price_r": overall.get("avg_price_r"),
        "net_profit": overall.get("net_profit"),
        "max_drawdown_price_r": overall.get("max_drawdown_price_r"),
        "expectancy_price_r": overall.get("expectancy_price_r"),
        "tester_ok": tester_ok,
        "tester_generated_at": tester_run.get("generated_at", "") if isinstance(tester_run, dict) else "",
        "recommendation_adoptable": decision.get("adoptable") if isinstance(decision, dict) else None,
        "recommendation_reasons": reasons[:5] if isinstance(reasons, list) else [],
        "executed_tester_xml_rows": executed_rows if isinstance(executed_rows, dict) else {},
    }


def mt5_stable_candidate_failure_context(
    summary: dict[str, object],
    recommendation: dict[str, object],
) -> dict[str, object]:
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(recommendation, dict):
        recommendation = {}

    chronological = recommendation.get("chronological") if isinstance(recommendation.get("chronological"), dict) else {}
    failure_context = (
        chronological.get("failure_context")
        if isinstance(chronological, dict) and isinstance(chronological.get("failure_context"), dict)
        else {}
    )
    failed_splits = chronological.get("failed_splits") if isinstance(chronological, dict) else None
    if not isinstance(failed_splits, list):
        failed_splits = []
        split_rows = summary.get("chronological_splits")
        if isinstance(split_rows, list):
            for row in split_rows:
                if not isinstance(row, dict):
                    continue
                has_failure_diagnosis = bool(str(row.get("diagnosis") or "").strip())
                if has_failure_diagnosis or number(row.get("pf")) < 1.0 or number(row.get("avg_price_r")) < 0.0:
                    failed_splits.append(row)

    sources = {
        "chronological_failures": failed_splits,
        "weak_time_segments": failure_context.get("weak_time_segments")
        if isinstance(failure_context.get("weak_time_segments"), list)
        else summary.get("weak_time_segments"),
        "weak_trend_segments": failure_context.get("weak_trend_segments")
        if isinstance(failure_context.get("weak_trend_segments"), list)
        else summary.get("weak_trend_segments"),
        "weak_sl_tp_segments": failure_context.get("weak_sl_tp_segments")
        if isinstance(failure_context.get("weak_sl_tp_segments"), list)
        else summary.get("weak_segments"),
    }
    context: dict[str, object] = {}
    for key, rows in sources.items():
        compacted = compact_segments(rows, limit=3)
        if compacted:
            context[key] = compacted
    return context


def mt5_stable_candidate_refit_target(
    failure_context: dict[str, object],
    recommendation: dict[str, object],
    *,
    fallback_side: str = "auto",
) -> dict[str, object]:
    if not isinstance(failure_context, dict) or not failure_context:
        return {}
    set_metadata = (
        recommendation.get("set_metadata") if isinstance(recommendation.get("set_metadata"), dict) else {}
    )
    side = str(set_metadata.get("focus_side") or fallback_side or "").lower()
    if side not in {"buy", "sell"}:
        counts: dict[str, int] = {}
        for key in ("weak_time_segments", "weak_trend_segments", "weak_sl_tp_segments"):
            rows = failure_context.get(key)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                row_side = segment_group_side(row)
                if row_side:
                    counts[row_side] = counts.get(row_side, 0) + 1
        if counts:
            side = max(sorted(counts), key=lambda key: counts[key])
    if side not in {"buy", "sell"}:
        return {}

    driver = ""
    if failure_context.get("weak_time_segments") or failure_context.get("weak_trend_segments"):
        driver = "regime"
        reason = "stable candidate has weak time/trend regime segments"
        kind, focus_side = mt5_regime_refit_target(side)
    elif failure_context.get("weak_sl_tp_segments"):
        driver = "entry_sl_tp"
        reason = "stable candidate has weak SL/TP segments"
        kind, focus_side = ("buy_entry_refit", "buy") if side == "buy" else ("sell_entry_refit", "sell")
    else:
        return {}
    if kind == "next_optimization" or focus_side not in {"buy", "sell"}:
        return {}

    return {
        "side": side,
        "driver": driver,
        "kind": kind,
        "focus_side": focus_side,
        "reason": reason,
    }


def build_promotion_next_actions(report: dict[str, object]) -> list[dict[str, object]]:
    checks = report.get("checks")
    check_rows = [row for row in checks if isinstance(row, dict)] if isinstance(checks, list) else []
    checks_by_name = {str(row.get("name")): row for row in check_rows}
    failed = {str(row.get("name")): row for row in check_rows if row.get("passed") is not True}
    mt5_optimization = report.get("mt5_optimization") if isinstance(report.get("mt5_optimization"), dict) else {}
    mt5_yearly_optimization = (
        report.get("mt5_yearly_optimization") if isinstance(report.get("mt5_yearly_optimization"), dict) else {}
    )
    mt5_optimization_recommendation = (
        report.get("mt5_optimization_recommendation")
        if isinstance(report.get("mt5_optimization_recommendation"), dict)
        else {}
    )
    mt5_stable_candidate = (
        report.get("mt5_stable_candidate") if isinstance(report.get("mt5_stable_candidate"), dict) else {}
    )
    mt5_stable_candidate_recommendation = (
        report.get("mt5_stable_candidate_recommendation")
        if isinstance(report.get("mt5_stable_candidate_recommendation"), dict)
        else {}
    )
    mt5_stable_candidate_tester_run = (
        report.get("mt5_stable_candidate_tester_run")
        if isinstance(report.get("mt5_stable_candidate_tester_run"), dict)
        else {}
    )
    mt5_tester_run = report.get("mt5_tester_run") if isinstance(report.get("mt5_tester_run"), dict) else {}
    mt5_tester_status = (
        report.get("mt5_tester_status") if isinstance(report.get("mt5_tester_status"), dict) else {}
    )
    bridge_status = report.get("bridge_status") if isinstance(report.get("bridge_status"), dict) else {}
    mt5_buy_refit_recommendation = (
        report.get("mt5_buy_refit_recommendation")
        if isinstance(report.get("mt5_buy_refit_recommendation"), dict)
        else {}
    )
    mt5_buy_entry_refit_recommendation = (
        report.get("mt5_buy_entry_refit_recommendation")
        if isinstance(report.get("mt5_buy_entry_refit_recommendation"), dict)
        else {}
    )
    mt5_sell_entry_refit_recommendation = (
        report.get("mt5_sell_entry_refit_recommendation")
        if isinstance(report.get("mt5_sell_entry_refit_recommendation"), dict)
        else {}
    )
    mt5_sell_regime_entry_refit_recommendation = (
        report.get("mt5_sell_regime_entry_refit_recommendation")
        if isinstance(report.get("mt5_sell_regime_entry_refit_recommendation"), dict)
        else {}
    )
    mt5_buy_hour03_validation_recommendation = (
        report.get("mt5_buy_hour03_validation_recommendation")
        if isinstance(report.get("mt5_buy_hour03_validation_recommendation"), dict)
        else {}
    )
    mt5_buy_hour03_wide_stop_validation_recommendation = (
        report.get("mt5_buy_hour03_wide_stop_validation_recommendation")
        if isinstance(report.get("mt5_buy_hour03_wide_stop_validation_recommendation"), dict)
        else {}
    )
    mt5_buy_hour03_wide_stop_calendar_validation_recommendation = (
        report.get("mt5_buy_hour03_wide_stop_calendar_validation_recommendation")
        if isinstance(report.get("mt5_buy_hour03_wide_stop_calendar_validation_recommendation"), dict)
        else {}
    )
    mt5_forward = report.get("mt5_forward_test") if isinstance(report.get("mt5_forward_test"), dict) else {}
    mt5_back_forward = (
        report.get("mt5_back_forward_run") if isinstance(report.get("mt5_back_forward_run"), dict) else {}
    )
    forward = report.get("forward_test") if isinstance(report.get("forward_test"), dict) else {}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    score_weight_search = report.get("score_weight_search") if isinstance(report.get("score_weight_search"), dict) else {}
    score_weight_search_by_side = (
        report.get("score_weight_search_by_side")
        if isinstance(report.get("score_weight_search_by_side"), dict)
        else {}
    )
    score_weight_set_by_side = (
        report.get("score_weight_set_by_side") if isinstance(report.get("score_weight_set_by_side"), dict) else {}
    )
    risk_shape_weight_search = (
        report.get("risk_shape_weight_search") if isinstance(report.get("risk_shape_weight_search"), dict) else {}
    )
    score_calibration = report.get("score_calibration")
    if not isinstance(score_calibration, dict):
        score_calibration = score_calibration_diagnostics(summary, min_threshold=70.0, min_count=20)
    latest_execution_pass_sources = {
        "runtime/latest_mt5_optimization_report.json": mt5_optimization,
        "runtime/latest_mt5_2025_optimization_report.json": mt5_yearly_optimization,
    }
    actions: list[dict[str, object]] = []

    def archive_preview_from_execution(execution: object) -> dict[str, object] | None:
        if not isinstance(execution, dict):
            return None
        run_id = str(execution.get("agent_csv_archive_run_id") or "")
        command_text = str(execution.get("command_text") or "")
        if not run_id or "--archive-agent-csvs-before-run" not in command_text:
            return None
        return mt5_agent_csv_archive_preview_execution_plan(run_id=run_id)

    def mt5_tester_execution_requires_compile(execution: object) -> bool:
        if not isinstance(execution, dict):
            return False
        command_text = str(execution.get("command_text") or "")
        return "methods/swing_eval/analysis/mt5_tester_run.py" in command_text and "--collect-only" not in command_text

    def latest_tester_finished_at() -> str:
        terminal = mt5_tester_run.get("terminal_run") if isinstance(mt5_tester_run.get("terminal_run"), dict) else {}
        return str(terminal.get("finished_at") or mt5_tester_run.get("generated_at") or "")

    def add_short_optimization_modified_before_guard(execution: dict[str, object]) -> dict[str, object]:
        if execution.get("kind") != "mt5_optimization_report_refresh":
            return execution
        command = execution.get("command") if isinstance(execution.get("command"), list) else []
        if "--modified-before" in command:
            return execution
        modified_before = latest_tester_finished_at()
        if not modified_before:
            return execution
        updated = dict(execution)
        updated_command = [str(item) for item in command]
        updated_command.extend(["--modified-before", modified_before])
        updated["command"] = updated_command
        updated["command_text"] = command_text(updated_command)
        updated["modified_before"] = modified_before
        return updated

    def evidence_with_mt5_archive_previews(evidence: object) -> object:
        if not isinstance(evidence, dict):
            return evidence
        updated = dict(evidence)
        for execution_key in (
            "execution",
            "follow_up_execution",
            "refit_execution",
            "validation_execution",
            "collect_refresh",
            "stable_candidate_set_execution",
            "stable_candidate_tester_execution",
            "stable_candidate_refit_execution",
        ):
            execution = updated.get(execution_key)
            if not isinstance(execution, dict):
                continue
            execution = dict(execution)
            execution = add_short_optimization_modified_before_guard(execution)
            attach_latest_executed_tester_xml_rows(execution, latest_execution_pass_sources)
            updated[execution_key] = execution
        if not isinstance(updated.get("compile"), dict):
            if any(
                mt5_tester_execution_requires_compile(updated.get(execution_key))
                for execution_key in (
                    "execution",
                    "follow_up_execution",
                    "refit_execution",
                    "validation_execution",
                    "stable_candidate_tester_execution",
                    "stable_candidate_refit_execution",
                )
            ):
                updated["compile"] = mt5_compile_execution_plan()
        for execution_key, preview_key in (
            ("execution", "archive_preview"),
            ("follow_up_execution", "follow_up_archive_preview"),
            ("refit_execution", "refit_archive_preview"),
            ("validation_execution", "validation_archive_preview"),
            ("stable_candidate_tester_execution", "stable_candidate_archive_preview"),
            ("stable_candidate_refit_execution", "stable_candidate_refit_archive_preview"),
        ):
            existing_preview = updated.get(preview_key)
            if isinstance(existing_preview, dict):
                if (
                    archive_preview_from_execution(updated.get(execution_key)) is not None
                    and existing_preview.get("include_source_time") is not True
                ):
                    run_id = str(existing_preview.get("run_id") or "")
                    if run_id:
                        updated[preview_key] = mt5_agent_csv_archive_preview_execution_plan(run_id=run_id)
                continue
            preview = archive_preview_from_execution(updated.get(execution_key))
            if preview is not None:
                updated[preview_key] = preview
        return updated

    def add(priority: int, area: str, action: str, reason: str, evidence: object = None) -> None:
        actions.append(
            {
                "priority": priority,
                "area": area,
                "action": action,
                "reason": reason,
                "evidence": evidence_with_mt5_archive_previews(evidence) if evidence is not None else {},
            }
        )

    if "bridge_status_ready" in failed:
        add(
            1,
            "bridge",
            "restore_mt5_ai_bridge_ea_posting_before_history_refresh",
            "MT5 AI Bridge evidence is not ready; fix Bridge/EA posting before relying on stale history or rerunning history-dependent gates.",
            {
                "failed_check": failed.get("bridge_status_ready"),
                "bridge_status": bridge_status,
                "execution": {
                    "kind": "bridge_status_refresh",
                    "command_text": (
                        "python3 methods/swing_eval/analysis/bridge_status.py "
                        "--output-json runtime/latest_bridge_status.json "
                        "--output-md runtime/latest_bridge_status.md"
                    ),
                    "watch_command_text": (
                        "python3 methods/swing_eval/analysis/bridge_status_watch.py --interval-seconds 60 "
                        "--heartbeat runtime/bridge_status_watch_heartbeat.json "
                        "--pid-file runtime/bridge_status_watch.pid"
                    ),
                    "recovery_plan_command_text": (
                        "python3 methods/swing_eval/analysis/bridge_recovery_plan.py "
                        "--bridge-status runtime/latest_bridge_status.json "
                        "--history-status runtime/latest_history_status.json "
                        "--output-json runtime/latest_bridge_recovery_plan.json "
                        "--output-md runtime/latest_bridge_recovery_plan.md"
                    ),
                    "outputs": {
                        "bridge_status_json": "runtime/latest_bridge_status.json",
                        "bridge_status_md": "runtime/latest_bridge_status.md",
                        "bridge_recovery_plan_json": "runtime/latest_bridge_recovery_plan.json",
                        "bridge_recovery_plan_md": "runtime/latest_bridge_recovery_plan.md",
                        "heartbeat": "runtime/bridge_status_watch_heartbeat.json",
                    },
                },
            },
        )

    def tester_archive_run_id(kind: str, focus_side: str) -> str:
        return promotion_archive_run_id(report, "mt5_tester", kind, focus_side)

    def recommendation_blocks_next_optimization_set() -> bool:
        if not mt5_optimization_recommendation:
            return False
        decision = (
            mt5_optimization_recommendation.get("decision")
            if isinstance(mt5_optimization_recommendation.get("decision"), dict)
            else {}
        )
        set_metadata = (
            mt5_optimization_recommendation.get("set_metadata")
            if isinstance(mt5_optimization_recommendation.get("set_metadata"), dict)
            else {}
        )
        return (
            decision.get("adoptable") is False
            or set_metadata.get("diagnostic_only") is True
            or set_metadata.get("skipped_write") is True
        )

    def stable_candidate_refit_execution_if_ready() -> dict[str, object]:
        if not recommendation_blocks_next_optimization_set():
            return {}
        stable_candidate_result = mt5_stable_candidate_result_summary(
            mt5_stable_candidate,
            mt5_stable_candidate_recommendation,
            mt5_stable_candidate_tester_run,
        )
        if not stable_candidate_result:
            return {}
        stable_failure_context = mt5_stable_candidate_failure_context(
            mt5_stable_candidate,
            mt5_stable_candidate_recommendation,
        )
        if not stable_failure_context:
            return {}
        set_metadata = (
            mt5_optimization_recommendation.get("set_metadata")
            if isinstance(mt5_optimization_recommendation.get("set_metadata"), dict)
            else {}
        )
        focus_side = str(set_metadata.get("focus_side") or "auto") if isinstance(set_metadata, dict) else "auto"
        stable_refit_target = mt5_stable_candidate_refit_target(
            stable_failure_context,
            mt5_stable_candidate_recommendation,
            fallback_side=focus_side,
        )
        if not stable_refit_target:
            return {}
        refit_kind = str(stable_refit_target.get("kind") or "")
        refit_focus_side = str(stable_refit_target.get("focus_side") or "")
        if not refit_kind or not refit_focus_side:
            return {}
        completed_refit = completed_refit_summary(refit_kind, refit_focus_side)
        if completed_refit:
            return {}
        return mt5_tester_execution_plan(
            refit_kind,
            focus_side=refit_focus_side,
            archive_run_id=tester_archive_run_id(refit_kind, refit_focus_side),
        )

    def completed_unadoptable_side_refit(recommendation: dict[str, object], side: str) -> bool:
        if not recommendation:
            return False
        decision = recommendation.get("decision") if isinstance(recommendation.get("decision"), dict) else {}
        set_metadata = (
            recommendation.get("set_metadata") if isinstance(recommendation.get("set_metadata"), dict) else {}
        )
        side_status = (
            recommendation.get("side_status") if isinstance(recommendation.get("side_status"), dict) else {}
        )
        side_row = side_status.get(side) if isinstance(side_status.get(side), dict) else {}
        focus_side = str(set_metadata.get("focus_side") or "")
        closed = number(side_row.get("closed") if side_row else decision.get("overall_closed"))
        if focus_side and focus_side != side:
            return False
        if closed <= 0:
            return False
        return (
            decision.get("adoptable") is False
            or set_metadata.get("skipped_write") is True
            or side_row.get("status") in {"refit_required", "score_refit_required"}
        )

    def refit_recommendation_for_kind(kind: str) -> dict[str, object]:
        if kind == "sell_entry_refit":
            return mt5_sell_entry_refit_recommendation
        if kind == "sell_regime_entry_refit":
            return mt5_sell_regime_entry_refit_recommendation
        if kind == "buy_entry_refit":
            return mt5_buy_entry_refit_recommendation
        if kind == "buy_refit":
            return mt5_buy_refit_recommendation
        return {}

    def completed_refit_summary(kind: str, side: str) -> dict[str, object]:
        recommendation = refit_recommendation_for_kind(kind)
        if not completed_unadoptable_side_refit(recommendation, side):
            return {}
        decision = recommendation.get("decision") if isinstance(recommendation.get("decision"), dict) else {}
        side_status = recommendation.get("side_status") if isinstance(recommendation.get("side_status"), dict) else {}
        next_search = recommendation.get("next_search") if isinstance(recommendation.get("next_search"), dict) else {}
        time_regime = recommendation.get("time_regime") if isinstance(recommendation.get("time_regime"), dict) else {}
        trend_regime = recommendation.get("trend_regime") if isinstance(recommendation.get("trend_regime"), dict) else {}
        chronological = recommendation.get("chronological") if isinstance(recommendation.get("chronological"), dict) else {}
        set_metadata = recommendation.get("set_metadata") if isinstance(recommendation.get("set_metadata"), dict) else {}
        return {
            "kind": kind,
            "side": side,
            "decision": decision,
            "side_status": side_status.get(side) if isinstance(side_status.get(side), dict) else {},
            "next_search": next_search.get(side) if isinstance(next_search.get(side), dict) else {},
            "set_metadata": set_metadata,
            "best_time_segments": compact_segments(time_regime.get("best_segments"), limit=4),
            "weak_time_segments": compact_segments(time_regime.get("weak_segments"), limit=4),
            "best_trend_segments": compact_segments(trend_regime.get("best_segments"), limit=4),
            "weak_trend_segments": compact_segments(trend_regime.get("weak_segments"), limit=4),
            "failed_chronological_splits": compact_segments(
                chronological.get("failed_splits"),
                limit=4,
            ),
        }

    def buy_refit_follow_up_kind() -> str:
        if completed_unadoptable_side_refit(mt5_buy_hour03_wide_stop_calendar_validation_recommendation, "buy"):
            return "buy_hour03_calendar_rejected"
        if completed_unadoptable_side_refit(mt5_buy_hour03_wide_stop_validation_recommendation, "buy"):
            return "buy_hour03_wide_stop_calendar_validation"
        if completed_unadoptable_side_refit(mt5_buy_hour03_validation_recommendation, "buy"):
            return "buy_hour03_wide_stop_validation"
        if completed_unadoptable_side_refit(mt5_buy_entry_refit_recommendation, "buy"):
            return "buy_hour03_validation"
        if completed_unadoptable_side_refit(mt5_buy_refit_recommendation, "buy"):
            return "buy_entry_refit"
        return "buy_refit"

    def buy_refit_follow_up_evidence() -> dict[str, object]:
        if completed_unadoptable_side_refit(mt5_buy_hour03_wide_stop_calendar_validation_recommendation, "buy"):
            decision = mt5_buy_hour03_wide_stop_calendar_validation_recommendation.get("decision")
            side_status = mt5_buy_hour03_wide_stop_calendar_validation_recommendation.get("side_status")
            next_search = mt5_buy_hour03_wide_stop_calendar_validation_recommendation.get("next_search")
            time_regime = mt5_buy_hour03_wide_stop_calendar_validation_recommendation.get("time_regime")
            trend_regime = mt5_buy_hour03_wide_stop_calendar_validation_recommendation.get("trend_regime")
            chronological = mt5_buy_hour03_wide_stop_calendar_validation_recommendation.get("chronological")
            return {
                "previous_refit": {
                    "kind": "buy_hour03_wide_stop_calendar_validation",
                    "decision": decision if isinstance(decision, dict) else {},
                    "buy_status": side_status.get("buy") if isinstance(side_status, dict) else {},
                    "next_search": next_search.get("buy") if isinstance(next_search, dict) else {},
                    "best_time_segments": compact_segments(
                        time_regime.get("best_segments") if isinstance(time_regime, dict) else None,
                        limit=4,
                    ),
                    "weak_time_segments": compact_segments(
                        time_regime.get("weak_segments") if isinstance(time_regime, dict) else None,
                        limit=4,
                    ),
                    "best_trend_segments": compact_segments(
                        trend_regime.get("best_segments") if isinstance(trend_regime, dict) else None,
                        limit=4,
                    ),
                    "weak_trend_segments": compact_segments(
                        trend_regime.get("weak_segments") if isinstance(trend_regime, dict) else None,
                        limit=4,
                    ),
                    "failed_chronological_splits": compact_segments(
                        chronological.get("failed_splits") if isinstance(chronological, dict) else None,
                        limit=4,
                    ),
                },
                "next_gate": "do_not_promote_buy_calendar_branch",
            }
        if completed_unadoptable_side_refit(mt5_buy_hour03_wide_stop_validation_recommendation, "buy"):
            decision = mt5_buy_hour03_wide_stop_validation_recommendation.get("decision")
            side_status = mt5_buy_hour03_wide_stop_validation_recommendation.get("side_status")
            next_search = mt5_buy_hour03_wide_stop_validation_recommendation.get("next_search")
            time_regime = mt5_buy_hour03_wide_stop_validation_recommendation.get("time_regime")
            trend_regime = mt5_buy_hour03_wide_stop_validation_recommendation.get("trend_regime")
            chronological = mt5_buy_hour03_wide_stop_validation_recommendation.get("chronological")
            return {
                "previous_refit": {
                    "kind": "buy_hour03_wide_stop_validation",
                    "decision": decision if isinstance(decision, dict) else {},
                    "buy_status": side_status.get("buy") if isinstance(side_status, dict) else {},
                    "next_search": next_search.get("buy") if isinstance(next_search, dict) else {},
                    "best_time_segments": compact_segments(
                        time_regime.get("best_segments") if isinstance(time_regime, dict) else None,
                        limit=4,
                    ),
                    "weak_time_segments": compact_segments(
                        time_regime.get("weak_segments") if isinstance(time_regime, dict) else None,
                        limit=4,
                    ),
                    "best_trend_segments": compact_segments(
                        trend_regime.get("best_segments") if isinstance(trend_regime, dict) else None,
                        limit=4,
                    ),
                    "weak_trend_segments": compact_segments(
                        trend_regime.get("weak_segments") if isinstance(trend_regime, dict) else None,
                        limit=4,
                    ),
                    "failed_chronological_splits": compact_segments(
                        chronological.get("failed_splits") if isinstance(chronological, dict) else None,
                        limit=4,
                    ),
                }
            }
        if completed_unadoptable_side_refit(mt5_buy_hour03_validation_recommendation, "buy"):
            decision = mt5_buy_hour03_validation_recommendation.get("decision")
            side_status = mt5_buy_hour03_validation_recommendation.get("side_status")
            next_search = mt5_buy_hour03_validation_recommendation.get("next_search")
            time_regime = mt5_buy_hour03_validation_recommendation.get("time_regime")
            trend_regime = mt5_buy_hour03_validation_recommendation.get("trend_regime")
            chronological = mt5_buy_hour03_validation_recommendation.get("chronological")
            return {
                "previous_refit": {
                    "kind": "buy_hour03_validation",
                    "decision": decision if isinstance(decision, dict) else {},
                    "buy_status": side_status.get("buy") if isinstance(side_status, dict) else {},
                    "next_search": next_search.get("buy") if isinstance(next_search, dict) else {},
                    "best_time_segments": compact_segments(
                        time_regime.get("best_segments") if isinstance(time_regime, dict) else None,
                        limit=4,
                    ),
                    "best_trend_segments": compact_segments(
                        trend_regime.get("best_segments") if isinstance(trend_regime, dict) else None,
                        limit=4,
                    ),
                    "weak_trend_segments": compact_segments(
                        trend_regime.get("weak_segments") if isinstance(trend_regime, dict) else None,
                        limit=4,
                    ),
                    "failed_chronological_splits": compact_segments(
                        chronological.get("failed_splits") if isinstance(chronological, dict) else None,
                        limit=4,
                    ),
                }
            }
        if completed_unadoptable_side_refit(mt5_buy_entry_refit_recommendation, "buy"):
            decision = mt5_buy_entry_refit_recommendation.get("decision")
            side_status = mt5_buy_entry_refit_recommendation.get("side_status")
            next_search = mt5_buy_entry_refit_recommendation.get("next_search")
            time_regime = mt5_buy_entry_refit_recommendation.get("time_regime")
            return {
                "previous_refit": {
                    "kind": "buy_entry_refit",
                    "decision": decision if isinstance(decision, dict) else {},
                    "buy_status": side_status.get("buy") if isinstance(side_status, dict) else {},
                    "next_search": next_search.get("buy") if isinstance(next_search, dict) else {},
                    "best_time_segments": compact_segments(
                        time_regime.get("best_segments") if isinstance(time_regime, dict) else None,
                        limit=6,
                    ),
                }
            }
        if not completed_unadoptable_side_refit(mt5_buy_refit_recommendation, "buy"):
            return {}
        decision = mt5_buy_refit_recommendation.get("decision")
        side_status = mt5_buy_refit_recommendation.get("side_status")
        next_search = mt5_buy_refit_recommendation.get("next_search")
        return {
            "previous_refit": {
                "kind": "buy_refit",
                "decision": decision if isinstance(decision, dict) else {},
                "buy_status": side_status.get("buy") if isinstance(side_status, dict) else {},
                "next_search": next_search.get("buy") if isinstance(next_search, dict) else {},
            }
        }

    def tester_plan(kind: str, focus_side: str, archive_run_id: str | None = None) -> dict[str, object]:
        if kind == "next_optimization" and recommendation_blocks_next_optimization_set():
            stable_refit_execution = stable_candidate_refit_execution_if_ready()
            if stable_refit_execution:
                return stable_refit_execution
            return mt5_optimization_report_refresh_execution_plan(
                kind="mt5_optimization_recommendation_refresh",
            )
        return mt5_tester_execution_plan(
            kind,
            focus_side=focus_side,
            archive_run_id=archive_run_id or tester_archive_run_id(kind, focus_side),
        )

    def score_refit_plan(side: str) -> dict[str, object]:
        kind, focus_side = mt5_score_refit_target(side)
        if kind == "next_optimization" and recommendation_blocks_next_optimization_set():
            return mt5_optimization_report_refresh_execution_plan(
                kind="mt5_optimization_recommendation_refresh",
            )
        return mt5_score_refit_execution_plan(
            side,
            archive_run_id=tester_archive_run_id(kind, focus_side),
        )

    def score_weight_search_plan(side: str) -> dict[str, object]:
        return score_weight_search_execution_plan(side)

    def score_weight_set_plan(side: str) -> dict[str, object]:
        return score_weight_set_execution_plan(side)

    def score_weight_search_result(side: str) -> dict[str, object]:
        if not isinstance(score_weight_search_by_side, dict):
            return {}
        if side in {"buy", "sell"}:
            value = score_weight_search_by_side.get(side)
            return compact_score_weight_search(value) if isinstance(value, dict) else {}
        values = [
            compact_score_weight_search(value)
            for value in score_weight_search_by_side.values()
            if isinstance(value, dict)
        ]
        if len(values) == 1:
            return values[0]
        return {"sides": values} if values else {}

    def score_weight_set_result(side: str) -> dict[str, object]:
        if not isinstance(score_weight_set_by_side, dict):
            return {}
        value = score_weight_set_by_side.get(side)
        return compact_score_weight_set_result(value) if isinstance(value, dict) else {}

    def score_weight_follow_up(side: str) -> dict[str, object]:
        search_result = score_weight_search_result(side)
        set_result = score_weight_set_result(side)
        diagnostics = search_result.get("diagnostics") if isinstance(search_result.get("diagnostics"), dict) else {}
        walk = search_result.get("walk_forward") if isinstance(search_result.get("walk_forward"), dict) else {}
        regime = search_result.get("regime_search") if isinstance(search_result.get("regime_search"), dict) else {}
        best_regime = (
            regime.get("best_regime_candidate")
            if isinstance(regime.get("best_regime_candidate"), dict)
            else {}
        )
        walk_aggregate = walk.get("aggregate") if isinstance(walk.get("aggregate"), dict) else {}
        status = str(
            set_result.get("skip_reason")
            or diagnostics.get("status")
            or walk.get("status")
            or best_regime.get("wf_status")
            or ""
        )
        if not status:
            return {}
        sample_shortage = (
            "sample_shortage" in status
            or "sample_shortage" in str(walk.get("status") or "")
            or "sample_shortage" in str(best_regime.get("wf_status") or "")
        )
        recommendation = (
            "collect more score-refit samples with sample_collection.set, then rerun side-specific weight_search "
            "with regime-search before converting to an MT5 validation set"
            if sample_shortage
            else "do not rerun the same score-weight set conversion until the side-specific walk-forward result changes"
        )
        return {
            "kind": "score_weight_follow_up",
            "focus_side": side if side in {"buy", "sell"} else "both",
            "status": status,
            "set_written": set_result.get("written"),
            "set_skip_reason": set_result.get("skip_reason"),
            "walk_forward_status": set_result.get("walk_forward_status") or walk.get("status"),
            "regime_status": best_regime.get("wf_status") if best_regime else "",
            "regime_dimension": best_regime.get("dimension") if best_regime else "",
            "regime_group": best_regime.get("group") if best_regime else "",
            "walk_forward_missing_test_weight_count": walk_aggregate.get("missing_test_weight_count"),
            "walk_forward_required_test_weight_count": walk_aggregate.get("required_test_weight_count"),
            "walk_forward_total_test_weight_count": walk_aggregate.get("total_test_weight_count"),
            "walk_forward_folds_with_weight_trades": walk_aggregate.get("folds_with_weight_trades"),
            "walk_forward_required_folds_with_weight_trades": walk_aggregate.get(
                "required_folds_with_weight_trades"
            ),
            "walk_forward_missing_folds_with_weight_trades": walk_aggregate.get(
                "missing_folds_with_weight_trades"
            ),
            "walk_forward_min_test_weight_count": walk_aggregate.get("min_test_weight_count"),
            "walk_forward_min_test_weight_fold": walk_aggregate.get("min_test_weight_fold"),
            "regime_missing_test_weight_count": best_regime.get("wf_missing_weight_count") if best_regime else None,
            "regime_required_test_weight_count": best_regime.get("wf_required_weight_count") if best_regime else None,
            "regime_total_test_weight_count": best_regime.get("wf_weight_count") if best_regime else None,
            "regime_folds_with_weight_trades": best_regime.get("wf_folds_with_weight") if best_regime else None,
            "regime_required_folds_with_weight_trades": (
                best_regime.get("wf_required_folds_with_weight") if best_regime else None
            ),
            "regime_missing_folds_with_weight_trades": (
                best_regime.get("wf_missing_folds_with_weight") if best_regime else None
            ),
            "regime_min_test_weight_count": best_regime.get("wf_min_weight_count") if best_regime else None,
            "regime_min_test_weight_fold": best_regime.get("wf_min_weight_fold") if best_regime else None,
            "sample_shortage": sample_shortage,
            "recommendation": recommendation,
        }

    def score_weight_follow_up_evidence(side: str) -> dict[str, object]:
        follow_up = score_weight_follow_up(side)
        if not follow_up:
            return {}
        focus_side = side if side in {"buy", "sell"} else "both"
        evidence: dict[str, object] = {
            "score_weight_set_result": score_weight_set_result(side),
            "score_weight_follow_up": follow_up,
        }
        if follow_up.get("sample_shortage") is True:
            archive_run_id = promotion_archive_run_id(
                report,
                "score_weight_sample_collection",
                "sample_collection",
                focus_side,
            )
            evidence["score_weight_history_check"] = score_weight_history_check_execution_plan()
            evidence["score_weight_sample_collection"] = score_weight_sample_collection_execution_plan(
                focus_side=focus_side,
                archive_run_id=archive_run_id,
            )
            evidence["score_weight_sample_collection_archive_preview"] = (
                mt5_agent_csv_archive_preview_execution_plan(run_id=archive_run_id)
            )
        return evidence

    def mt5_optimization_chronological_failure_context() -> dict[str, object]:
        chronological_failure = failed.get("mt5_optimization_chronological_splits")
        if not isinstance(chronological_failure, dict) or chronological_failure.get("value") == "missing":
            return {}
        return {
            "failed_check": chronological_failure,
            "failed_splits": compact_segments(
                failed_chronological_splits(mt5_optimization.get("chronological_splits")),
                limit=6,
            ),
            "weak_time_segments": compact_segments(mt5_optimization.get("weak_time_segments"), limit=6),
            "weak_trend_segments": compact_segments(mt5_optimization.get("weak_trend_segments"), limit=6),
            "weak_sl_tp_segments": compact_segments(mt5_optimization.get("weak_segments"), limit=6),
        }

    def regime_refit_plan(side: str) -> dict[str, object]:
        kind, focus_side = mt5_regime_refit_target(side)
        if kind == "next_optimization" and recommendation_blocks_next_optimization_set():
            return mt5_optimization_report_refresh_execution_plan(
                kind="mt5_optimization_recommendation_refresh",
            )
        return mt5_regime_refit_execution_plan(
            side,
            archive_run_id=tester_archive_run_id(kind, focus_side),
        )

    def yearly_refit_plan(side: str) -> dict[str, object]:
        kind, focus_side = mt5_yearly_refit_target(side)
        if kind == "next_optimization" and recommendation_blocks_next_optimization_set():
            return mt5_optimization_report_refresh_execution_plan(
                kind="mt5_optimization_recommendation_refresh",
            )
        return mt5_yearly_refit_execution_plan(
            side,
            archive_run_id=tester_archive_run_id(kind, focus_side),
        )

    def yearly_validation_plan(focus_side: str) -> dict[str, object]:
        if recommendation_blocks_next_optimization_set():
            stable_refit_execution = stable_candidate_refit_execution_if_ready()
            if stable_refit_execution:
                return stable_refit_execution
            return mt5_optimization_report_refresh_execution_plan(
                kind="mt5_optimization_recommendation_refresh",
            )
        return mt5_yearly_validation_execution_plan(
            focus_side=focus_side,
            archive_run_id=promotion_archive_run_id(
                report,
                "mt5_yearly_validation",
                "next_optimization_2025",
                focus_side,
            ),
        )

    def strategy_forward_plan() -> dict[str, object]:
        return mt5_strategy_forward_execution_plan(
            archive_run_id=promotion_archive_run_id(report, "mt5_forward", "strategy_forward", "both"),
        )

    def mt5_forward_performance_plan() -> dict[str, object]:
        if recommendation_blocks_next_optimization_set():
            return mt5_optimization_report_refresh_execution_plan(
                kind="mt5_optimization_recommendation_refresh",
            )
        return strategy_forward_plan()

    def mt5_back_forward_run_execution_plan(
        *,
        condition_overrides: dict[str, object] | None = None,
        run_id_suffix: str = "",
    ) -> dict[str, object]:
        mode = str(mt5_back_forward.get("mode") or "both").strip() or "both"
        execution_conditions = (
            mt5_back_forward.get("execution_conditions")
            if isinstance(mt5_back_forward.get("execution_conditions"), dict)
            else {}
        )
        execution_conditions = {**execution_conditions, **(condition_overrides or {})}
        command = [
            "python3",
            "methods/swing_eval/analysis/mt5_back_forward_run.py",
            "--mode",
            mode,
            "--execute",
            "--refresh-ready-status",
        ]
        run_id_prefix = str(mt5_back_forward.get("run_id_prefix") or "").strip()
        if run_id_prefix and run_id_suffix:
            run_id_prefix = f"{run_id_prefix}_{run_id_suffix}"
        elif run_id_suffix:
            run_id_prefix = run_id_suffix
        if run_id_prefix:
            command.extend(["--run-id-prefix", run_id_prefix])
        for key, option in (
            ("per_step_timeout_seconds", "--timeout-seconds"),
            ("since_minutes", "--since-minutes"),
            ("min_closed", "--min-closed"),
            ("from_date", "--from-date"),
            ("to_date", "--to-date"),
            ("forward_mode", "--forward-mode"),
            ("max_ready_status_age_seconds", "--max-ready-status-age-seconds"),
        ):
            value = execution_conditions.get(key)
            if value not in (None, ""):
                command.extend([option, str(value)])
        for key, flag in (
            ("sync_expert_parameters_set", "--sync-expert-parameters-set"),
            ("allow_running_terminal", "--allow-running-terminal"),
            ("allow_stale_compile", "--allow-stale-compile"),
            ("allow_invalid_risk_preset", "--allow-invalid-risk-preset"),
            ("skip_ready_status_check", "--skip-ready-status-check"),
            ("skip_archive_preview", "--skip-archive-preview"),
        ):
            if execution_conditions.get(key) is True:
                command.append(flag)
        return {
            "kind": "mt5_back_forward_run",
            "mode": mode,
            "run_id_prefix": run_id_prefix,
            "execution_conditions": dict(execution_conditions),
            "command": command,
            "command_text": command_text(command),
            "outputs": {
                "json": "runtime/latest_mt5_back_forward_run.json",
                "md": "runtime/latest_mt5_back_forward_run.md",
            },
        }

    def mt5_back_forward_sample_shortage_recovery_plan(
        sample_shortage_value: dict[str, object],
    ) -> dict[str, object]:
        base_conditions = (
            mt5_back_forward.get("execution_conditions")
            if isinstance(mt5_back_forward.get("execution_conditions"), dict)
            else {}
        )
        current_from = str(base_conditions.get("from_date") or "").strip()
        current_to = str(base_conditions.get("to_date") or "").strip()
        current_range_days = mt5_date_range_days(current_from, current_to)
        if (
            current_from
            and current_to
            and current_range_days is not None
            and current_range_days >= MT5_BACK_FORWARD_SAMPLE_SHORTAGE_MIN_EXTENDED_DAYS
        ):
            range_strategy = "reuse_existing_extended_date_range"
            suggested_from = current_from
            suggested_to = current_to
        else:
            range_strategy = "extend_to_default_full_year"
            suggested_from = MT5_BACK_FORWARD_SAMPLE_SHORTAGE_DEFAULT_FROM_DATE
            suggested_to = MT5_BACK_FORWARD_SAMPLE_SHORTAGE_DEFAULT_TO_DATE
        overrides = {"from_date": suggested_from, "to_date": suggested_to}
        execution = mt5_back_forward_run_execution_plan(
            condition_overrides=overrides,
            run_id_suffix="extended_window",
        )
        return {
            "kind": "mt5_back_forward_sample_shortage_recovery",
            "strategy": "extend_date_range_before_judging_performance",
            "status": sample_shortage_value.get("status", ""),
            "min_closed": sample_shortage_value.get("min_closed", ""),
            "backtest_trades": sample_shortage_value.get("backtest_trades", ""),
            "forward_trades": sample_shortage_value.get("forward_trades", ""),
            "current_from_date": current_from,
            "current_to_date": current_to,
            "current_range_days": current_range_days,
            "range_strategy": range_strategy,
            "suggested_from_date": suggested_from,
            "suggested_to_date": suggested_to,
            "min_extended_days": MT5_BACK_FORWARD_SAMPLE_SHORTAGE_MIN_EXTENDED_DAYS,
            "execution": execution,
        }

    def mt5_status_watch_restart_execution_plan() -> dict[str, object]:
        watcher = (
            mt5_tester_status.get("status_watch_heartbeat")
            if isinstance(mt5_tester_status.get("status_watch_heartbeat"), dict)
            else {}
        )
        command = [
            "python3",
            "methods/swing_eval/analysis/mt5_tester_status_watch.py",
            "--interval-seconds",
            "60",
            "--heartbeat",
            "runtime/mt5_tester_status_watch_heartbeat_current.json",
            "--pid-file",
            "runtime/mt5_tester_status_watch_current.pid",
            "--manual-test-queue",
            "runtime/latest_mt5_manual_test_queue.json",
            "--manual-queue-launch",
            "runtime/latest_mt5_manual_queue_launch.json",
            "--manual-collect-run",
            "runtime/latest_mt5_manual_collect_run.json",
        ]
        return {
            "kind": "mt5_status_watch_restart",
            "command": command,
            "command_text": command_text(command),
            "current_status": watcher.get("status", ""),
            "current_watcher_pid": watcher.get("watcher_pid", ""),
            "requires_stop_existing_watcher": watcher.get("continuous") is True,
            "note": "Uses the current-schema heartbeat path so an older watcher on the legacy heartbeat can be left running while this is validated.",
            "outputs": {
                "heartbeat": "runtime/mt5_tester_status_watch_heartbeat_current.json",
                "status_json": "runtime/latest_mt5_tester_status.json",
                "status_md": "runtime/latest_mt5_tester_status.md",
            },
        }

    completed_sell_regime_refit = completed_refit_summary("sell_regime_entry_refit", "sell")
    completed_sell_score_weight_follow_up = (
        score_weight_follow_up_evidence("sell") if completed_sell_regime_refit else {}
    )
    deferred_sell_chronological_context = (
        mt5_optimization_chronological_failure_context()
        if completed_sell_regime_refit
        and recommendation_blocks_next_optimization_set()
        and isinstance(completed_sell_score_weight_follow_up.get("score_weight_sample_collection"), dict)
        else {}
    )
    if completed_sell_regime_refit:
        sell_score_refit_evidence = {
            "previous_refit": completed_sell_regime_refit,
            "score_weight_search": score_weight_search_plan("sell"),
            "score_weight_search_result": score_weight_search_result("sell"),
            "score_weight_set": score_weight_set_plan("sell"),
            **completed_sell_score_weight_follow_up,
        }
        if deferred_sell_chronological_context:
            sell_score_refit_evidence["upstream_chronological_rejection"] = deferred_sell_chronological_context
        add(
            1,
            "sell_score_refit",
            "refit_sell_score_function_after_regime_entry_refit",
            "SELL regime-entry refit completed but remains diagnostic-only or score-inverted; refit the SELL score function before rerunning the same MT5 refit.",
            sell_score_refit_evidence,
        )

    if any(name.startswith("mt5_compile_") for name in failed):
        add(
            1,
            "mt5_compile",
            "compile_current_sources_before_testing",
            "MT5 source/binary freshness failed; Tester results cannot be trusted until the deployed .ex5 is current.",
            {
                "failed_checks": failed_subset(failed, "mt5_compile_"),
                "execution": mt5_compile_execution_plan(),
            },
        )

    if "mt5_optimization_source_time_range" in failed:
        source_time_focus_side = mt5_optimization_focus_side(mt5_optimization)
        source_time_archive_run_id = promotion_archive_run_id(
            report,
            "mt5_optimization_source_time",
            "next_optimization",
            source_time_focus_side,
        )
        add(
            1,
            "mt5_optimization_source_time",
            "rerun_or_recollect_mt5_optimization_for_expected_tester_dates",
            "MT5 optimization Agent CSV server_time range does not match the expected Tester FromDate/ToDate; the report may be mixing stale Agent CSVs from another run.",
            {
                "failed_check": failed.get("mt5_optimization_source_time_range"),
                "execution": tester_plan(
                    "next_optimization",
                    source_time_focus_side,
                    archive_run_id=source_time_archive_run_id,
                ),
                "collect_refresh": mt5_optimization_report_refresh_execution_plan(),
            },
        )

    if "mt5_tester_run_agent_csv_archive" in failed:
        archive_focus_side = mt5_optimization_focus_side(mt5_optimization)
        archive_run_id = promotion_archive_run_id(
            report,
            "mt5_tester_run_archive",
            "next_optimization",
            archive_focus_side,
        )
        add(
            1,
            "mt5_tester_run_archive",
            "rerun_mt5_tester_with_agent_csv_archive",
            "Latest MT5 Tester run lacks valid Agent CSV archive evidence; preview source_time coverage, then rerun with --archive-agent-csvs-before-run to avoid stale CSV date ranges.",
            {
                "failed_check": failed.get("mt5_tester_run_agent_csv_archive"),
                "execution": tester_plan(
                    "next_optimization",
                    archive_focus_side,
                    archive_run_id=archive_run_id,
                ),
            },
        )

    if "mt5_tester_run_ok" in failed:
        tester_run_focus_side = mt5_optimization_focus_side(mt5_optimization)
        tester_run_archive_run_id = promotion_archive_run_id(
            report,
            "mt5_tester_run_ok",
            "next_optimization",
            tester_run_focus_side,
        )
        evidence: dict[str, object] = {
            "failed_check": failed.get("mt5_tester_run_ok"),
            "execution": tester_plan(
                "next_optimization",
                tester_run_focus_side,
                archive_run_id=tester_run_archive_run_id,
            ),
        }
        failed_value = failed.get("mt5_tester_run_ok", {}).get("value") if isinstance(failed.get("mt5_tester_run_ok"), dict) else {}
        if isinstance(failed_value, dict) and failed_value.get("blocked") is True:
            blocked_components = (
                failed_value.get("blocked_components") if isinstance(failed_value.get("blocked_components"), dict) else {}
            )
            compile_blocked = failed_value.get("compile_blocked") is True or blocked_components.get("compile_stale") is True
            risk_preset_blocked = (
                failed_value.get("risk_preset_blocked") is True
                or blocked_components.get("risk_preset_invalid") is True
            )
            archive_blocked = (
                failed_value.get("agent_csv_archive_blocked") is True
                or blocked_components.get("agent_csv_archive_failed") is True
            )
            terminal_blocked = (
                failed_value.get("running_terminal_blocked") is True
                or blocked_components.get("terminal_already_running") is True
            )
            tester_set_sync_blocked = (
                failed_value.get("tester_set_sync_blocked") is True
                or blocked_components.get("tester_set_not_synced") is True
            )
            if compile_blocked or not blocked_components:
                evidence["compile"] = mt5_compile_execution_plan()
            if risk_preset_blocked:
                evidence["risk_preset_fix"] = mt5_risk_preset_fix_plan(failed_value)
            if tester_set_sync_blocked:
                execution = evidence.get("execution") if isinstance(evidence.get("execution"), dict) else {}
                command = execution.get("command") if isinstance(execution.get("command"), list) else []
                sync_command = [str(item) for item in command]
                if sync_command and "--sync-expert-parameters-set" not in sync_command:
                    sync_command.append("--sync-expert-parameters-set")
                evidence["sync_set"] = {
                    "target_tester_set_sync": failed_value.get("target_tester_set_sync", {}),
                    "command": sync_command,
                    "command_text": command_text(sync_command) if sync_command else "",
                    "note": "Sync the ExpertParameters .set into MT5 MQL5/Profiles/Tester before launching Strategy Tester.",
                }
            if archive_blocked:
                evidence["archive_failure"] = {
                    "agent_csv_archive_ok": failed_value.get("agent_csv_archive_ok", "not_reported"),
                    "agent_csv_archive_count": failed_value.get("agent_csv_archive_count", "not_reported"),
                    "agent_csv_archive_run_id": failed_value.get("agent_csv_archive_run_id", ""),
                    "note": "Fix archive permissions or run-id/path issues before launching MT5 Tester again.",
                }
            if terminal_blocked:
                evidence["terminal_blocker"] = {
                    "running_terminal_blocked": failed_value.get("running_terminal_blocked", "not_reported"),
                    "detection_enabled": failed_value.get("running_terminal_detection_enabled", "not_reported"),
                    "processes": failed_value.get("running_terminal_processes", []),
                    "note": "Close the existing MT5 terminal64.exe before launching terminal64.exe /config. Use --allow-running-terminal only for diagnostics.",
                }
        add(
            1,
            "mt5_tester_run",
            "resolve_latest_mt5_tester_run_failure",
            "Latest MT5 Tester runner reported ok=false; resolve compile, risk preset, archive, or terminal blockers before using child optimization outputs.",
            evidence,
        )

    if "mt5_tester_run_source_time" in failed:
        tester_source_time_focus_side = mt5_optimization_focus_side(mt5_optimization)
        tester_source_time_archive_run_id = promotion_archive_run_id(
            report,
            "mt5_tester_run_source_time",
            "next_optimization",
            tester_source_time_focus_side,
        )
        add(
            1,
            "mt5_tester_run_source_time",
            "rerun_mt5_tester_after_source_time_block",
            "Latest MT5 Tester runner blocked recommendation because collected Agent CSV server_time did not match the expected Tester dates.",
            {
                "failed_check": failed.get("mt5_tester_run_source_time"),
                "execution": tester_plan(
                    "next_optimization",
                    tester_source_time_focus_side,
                    archive_run_id=tester_source_time_archive_run_id,
                ),
                "collect_refresh": mt5_optimization_report_refresh_execution_plan(),
            },
        )

    if "mt5_tester_run_terminal" in failed:
        tester_terminal_focus_side = mt5_optimization_focus_side(mt5_optimization)
        tester_terminal_archive_run_id = promotion_archive_run_id(
            report,
            "mt5_tester_run_terminal",
            "next_optimization",
            tester_terminal_focus_side,
        )
        add(
            1,
            "mt5_tester_run_terminal",
            "rerun_mt5_tester_after_terminal_failure",
            "Latest MT5 Tester terminal run timed out or returned a non-zero code; rerun after checking terminal stability.",
            {
                "failed_check": failed.get("mt5_tester_run_terminal"),
                "execution": tester_plan(
                    "next_optimization",
                    tester_terminal_focus_side,
                    archive_run_id=tester_terminal_archive_run_id,
                ),
            },
        )

    if "mt5_tester_run_risk_preset_schema" in failed:
        tester_risk_schema_focus_side = mt5_optimization_focus_side(mt5_optimization)
        tester_risk_schema_archive_run_id = promotion_archive_run_id(
            report,
            "mt5_tester_run_risk_preset_schema",
            "next_optimization",
            tester_risk_schema_focus_side,
        )
        add(
            1,
            "mt5_tester_run_risk_preset",
            "rerun_mt5_tester_with_current_risk_preset_schema",
            "Latest MT5 Tester run was produced by an older or incomplete risk preset summary; rerun with the current runner before using it as promotion evidence.",
            {
                "failed_check": failed.get("mt5_tester_run_risk_preset_schema"),
                "execution": tester_plan(
                    "next_optimization",
                    tester_risk_schema_focus_side,
                    archive_run_id=tester_risk_schema_archive_run_id,
                ),
            },
        )

    if "mt5_tester_run_report_paths" in failed:
        tester_report_focus_side = mt5_optimization_focus_side(mt5_optimization)
        tester_report_archive_run_id = promotion_archive_run_id(
            report,
            "mt5_tester_run_report_paths",
            "next_optimization",
            tester_report_focus_side,
        )
        add(
            1,
            "mt5_tester_run_report_paths",
            "rerun_mt5_tester_for_requested_report",
            "Latest MT5 Tester runner used a fallback XML pair instead of the requested Report output; rerun so the requested Tester report is generated before collecting results.",
            {
                "failed_check": failed.get("mt5_tester_run_report_paths"),
                "execution": tester_plan(
                    "next_optimization",
                    tester_report_focus_side,
                    archive_run_id=tester_report_archive_run_id,
                ),
            },
        )

    if "mt5_optimization_top_forward_back_result" in failed:
        top_forward = {}
        stable_forward = {}
        stable_rows: list[dict[str, object]] = []
        stable_candidate_result = mt5_stable_candidate_result_summary(
            mt5_stable_candidate,
            mt5_stable_candidate_recommendation,
            mt5_stable_candidate_tester_run,
        )
        tester_xml = mt5_optimization.get("tester_xml") if isinstance(mt5_optimization, dict) else {}
        if isinstance(tester_xml, dict) and isinstance(tester_xml.get("forward"), dict):
            forward_xml = tester_xml["forward"]
            top_forward = forward_top_pass(forward_xml)
            stable_forward = stable_forward_top_pass(forward_xml)
            stable_rows = compact_tester_passes(forward_xml.get("stable_top"), limit=4)
        if stable_forward and not stable_candidate_result:
            stable_focus_side = mt5_optimization_focus_side(mt5_optimization)
            stable_archive_run_id = tester_archive_run_id("stable_candidate", stable_focus_side)
            add(
                1,
                "mt5_optimization_stable",
                "use_stable_back_forward_passes_for_next_search",
                "Top forward pass is likely overfit, but stable back/forward passes exist; constrain the next .set to stable pass parameters.",
                {
                    "failed_check": failed.get("mt5_optimization_top_forward_back_result"),
                    "top_forward": top_forward,
                    "top_stable_forward": stable_forward,
                    "stable_forward_passes": stable_rows,
                    "execution": mt5_stable_candidate_set_execution_plan(
                        focus_side=stable_focus_side,
                    ),
                    "stable_candidate_set_execution": mt5_stable_candidate_set_execution_plan(
                        focus_side=stable_focus_side,
                    ),
                    "stable_candidate_tester_execution": tester_plan(
                        "stable_candidate",
                        stable_focus_side,
                        archive_run_id=stable_archive_run_id,
                    ),
                },
            )
        elif not stable_forward:
            add(
                1,
                "mt5_optimization",
                "reject_forward_only_winners_and_search_stable_back_forward_passes",
                "Top forward pass is profitable in forward but loses on back data, so it is likely overfit.",
                {
                    "failed_check": failed.get("mt5_optimization_top_forward_back_result"),
                    "top_forward": top_forward,
                    "execution": tester_plan("next_optimization", "sell"),
                },
            )

    if "mt5_optimization_positive_forward_back" in failed:
        add(
            1,
            "mt5_optimization_stability",
            "search_stable_back_forward_passes_before_promotion",
            "MT5 optimization has too few positive-forward/positive-back passes; search stable regimes before promotion.",
            {
                "failed_check": failed.get("mt5_optimization_positive_forward_back"),
                "weak_time_segments": compact_segments(mt5_optimization.get("weak_time_segments"), limit=6),
                "weak_trend_segments": compact_segments(mt5_optimization.get("weak_trend_segments"), limit=6),
                "execution": regime_refit_plan(mt5_optimization_focus_side(mt5_optimization)),
            },
        )

    if "mt5_optimization_chronological_splits" in failed and not deferred_sell_chronological_context:
        chronological_failure = failed.get("mt5_optimization_chronological_splits")
        if isinstance(chronological_failure, dict) and chronological_failure.get("value") == "missing":
            add(
                1,
                "mt5_optimization",
                "regenerate_mt5_optimization_report_with_chronological_splits",
                "MT5 optimization report lacks chronological_splits; regenerate it from Agent CSV before promotion.",
                {
                    "failed_check": chronological_failure,
                    "execution": mt5_optimization_report_refresh_execution_plan(),
                },
            )
        else:
            yearly_execution = yearly_validation_plan(mt5_optimization_focus_side(mt5_optimization))
            evidence: dict[str, object] = {
                "failed_check": chronological_failure,
                "failed_splits": compact_segments(
                    failed_chronological_splits(mt5_optimization.get("chronological_splits")),
                    limit=6,
                ),
                "weak_time_segments": compact_segments(mt5_optimization.get("weak_time_segments"), limit=6),
                "weak_trend_segments": compact_segments(mt5_optimization.get("weak_trend_segments"), limit=6),
                "weak_sl_tp_segments": compact_segments(mt5_optimization.get("weak_segments"), limit=6),
                "execution": yearly_execution,
            }
            yearly_archive_run_id = str(yearly_execution.get("agent_csv_archive_run_id") or "")
            if yearly_archive_run_id:
                evidence["archive_preview"] = mt5_agent_csv_archive_preview_execution_plan(
                    run_id=yearly_archive_run_id
                )
            add(
                1,
                "mt5_optimization",
                "reject_chronologically_unstable_optimization",
                "MT5 optimization edge does not persist across chronological splits, so it should be treated as period-fit.",
                evidence,
            )

    regime_diagnostic_failures = {
        name: row
        for name, row in failed.items()
        if name
        in {
            "mt5_optimization_time_regime_diagnostics",
            "mt5_optimization_trend_regime_diagnostics",
        }
    }
    if regime_diagnostic_failures:
        add(
            1,
            "mt5_optimization_diagnostics",
            "regenerate_mt5_optimization_report_with_time_and_trend_diagnostics",
            "MT5 optimization report lacks required time/trend regime diagnostics; regenerate it from current Agent CSV before promotion.",
            {
                "failed_checks": regime_diagnostic_failures,
                "execution": mt5_optimization_report_refresh_execution_plan(),
            },
        )

    if "mt5_optimization_sl_tp_diagnostics" in failed:
        add(
            1,
            "mt5_optimization_diagnostics",
            "regenerate_mt5_optimization_report_with_sl_tp_diagnostics",
            "MT5 optimization report lacks required SL/TP diagnostics, including RR x TP; regenerate it from current Agent CSV before promotion.",
            {
                "failed_check": failed.get("mt5_optimization_sl_tp_diagnostics"),
                "execution": mt5_optimization_report_refresh_execution_plan(),
            },
        )

    mt5_optimization_pass_budget_failures = {
        name: row
        for name, row in failed.items()
        if name in {"mt5_optimization_pass_budget", "mt5_optimization_executed_tester_xml_rows"}
    }
    if mt5_optimization_pass_budget_failures:
        add(
            1,
            "mt5_optimization_evidence",
            "regenerate_mt5_optimization_report_with_pass_budget",
            "MT5 optimization report lacks pass budget or executed XML row evidence; regenerate it with the tested .set and Tester XML paths before promotion.",
            {
                "failed_checks": mt5_optimization_pass_budget_failures,
                "execution": mt5_optimization_report_refresh_execution_plan(),
            },
        )

    buy_optimization_failures = {
        name: row
        for name, row in failed.items()
        if name.startswith("mt5_optimization_buy_") and not name.endswith("_score_not_inverted")
    }
    if buy_optimization_failures:
        refit_kind = buy_refit_follow_up_kind()
        extra_evidence = buy_refit_follow_up_evidence()
        if refit_kind == "buy_hour03_calendar_rejected":
            action_name = "reject_buy_hour03_calendar_candidate_before_promotion"
            action_reason = (
                "BUY hour03 calendar validation has already failed promotion evidence; do not repeat this "
                "diagnostic branch or promote it without a new rule family."
            )
        elif refit_kind == "buy_hour03_wide_stop_calendar_validation":
            action_name = "run_buy_hour03_wide_stop_calendar_validation_after_failed_wide_stop"
            action_reason = (
                "BUY hour03 wide-stop is strong in the short window but still lacks positive forward/back passes; "
                "validate the calendar-filter split before promotion."
            )
        elif refit_kind == "buy_hour03_wide_stop_validation":
            action_name = "run_buy_hour03_wide_stop_validation_after_failed_hour03_validation"
            action_reason = (
                "BUY hour03 validation is promising but still diagnostic-only or unstable; validate the stricter "
                "03:00 server-hour, M30/M15-up, wide-stop BUY subset before promotion."
            )
        elif refit_kind == "buy_hour03_validation":
            action_name = "run_buy_hour03_validation_after_failed_entry_refit"
            action_reason = (
                "BUY entry refit remains unadoptable, but strong time regimes exist; validate the 03:00-04:00 "
                "server-hour BUY subset before two-sided promotion."
            )
        elif refit_kind == "buy_entry_refit":
            action_name = "run_buy_entry_refit_after_failed_buy_refit"
            action_reason = (
                "BUY refit has already failed; narrow the next search to entry-quality filters before two-sided promotion."
            )
        else:
            action_name = "run_buy_side_refit_or_buy_only_optimization"
            action_reason = (
                "BUY does not have enough valid MT5 optimization evidence or has negative edge; it must be fitted "
                "separately before two-sided promotion."
            )
        evidence = {
            "failed_checks": buy_optimization_failures,
            **extra_evidence,
        }
        if refit_kind != "buy_hour03_calendar_rejected":
            evidence["execution"] = tester_plan(refit_kind, "buy")
        add(2, "buy_refit", action_name, action_reason, evidence)

    optimization_balance_failure = failed.get("mt5_optimization_side_total_price_r_balance")
    if isinstance(optimization_balance_failure, dict):
        weak_side = side_balance_weak_side(optimization_balance_failure, default=mt5_optimization_focus_side(mt5_optimization))
        refit_kind = buy_refit_follow_up_kind() if weak_side == "buy" else "sell_regime_entry_refit"
        extra_evidence = buy_refit_follow_up_evidence() if weak_side == "buy" else {}
        action_name = "refit_weak_side_before_two_sided_promotion"
        action_reason = (
            "MT5 optimization positive price-R is concentrated in one side; refit the weak side before treating the candidate as two-sided."
        )
        if weak_side == "buy" and refit_kind == "buy_hour03_calendar_rejected":
            action_name = "reject_weak_buy_calendar_candidate_before_two_sided_promotion"
            action_reason = (
                "BUY calendar diagnostics have already failed promotion evidence; do not use this BUY branch "
                "as the weak-side fix for two-sided promotion."
            )
        evidence = {
            "failed_check": optimization_balance_failure,
            "failed_checks": {
                "mt5_optimization_side_total_price_r_balance": optimization_balance_failure,
            },
            "side_shares": optimization_balance_failure.get("value"),
            "weak_side": weak_side,
            **extra_evidence,
        }
        if not (weak_side == "buy" and refit_kind == "buy_hour03_calendar_rejected"):
            evidence["execution"] = tester_plan(refit_kind, weak_side)
        add(
            2,
            "mt5_optimization_balance",
            action_name,
            action_reason,
            evidence,
        )

    mt5_optimization_score_inversion_failures = {
        name: row
        for name, row in failed.items()
        if name.startswith("mt5_optimization_") and name.endswith("_score_not_inverted")
    }
    if mt5_optimization_score_inversion_failures:
        score_inversion_side = mt5_score_inversion_focus_side(mt5_optimization_score_inversion_failures)
        add(
            2,
            "mt5_optimization_score",
            "refit_mt5_side_score_function_before_optimization_promotion",
            "MT5 optimization score threshold is inverted for a side; refit side-specific scoring before promotion.",
            {
                "failed_checks": mt5_optimization_score_inversion_failures,
                "side_score_diagnostics": compact_side_score_diagnostics(
                    mt5_optimization.get("side_score_diagnostics") if isinstance(mt5_optimization, dict) else None,
                    limit=4,
                ),
                "execution": score_refit_plan(score_inversion_side),
                "score_weight_search": score_weight_search_plan(score_inversion_side),
                "score_weight_search_result": score_weight_search_result(score_inversion_side),
                "score_weight_set": score_weight_set_plan(score_inversion_side),
                **score_weight_follow_up_evidence(score_inversion_side),
            },
        )

    mt5_recommendation_failures = failed_subset(failed, "mt5_optimization_recommendation_")
    if mt5_recommendation_failures:
        set_metadata = (
            mt5_optimization_recommendation.get("set_metadata")
            if isinstance(mt5_optimization_recommendation.get("set_metadata"), dict)
            else {}
        )
        decision = (
            mt5_optimization_recommendation.get("decision")
            if isinstance(mt5_optimization_recommendation.get("decision"), dict)
            else {}
        )
        score_refit_sides = set_metadata.get("score_refit_sides") if isinstance(set_metadata, dict) else []
        score_refit_side = str(score_refit_sides[0]) if isinstance(score_refit_sides, list) and score_refit_sides else "auto"
        evidence: dict[str, object] = {
            "failed_checks": mt5_recommendation_failures,
            "decision": {
                "adoptable": decision.get("adoptable") if isinstance(decision, dict) else None,
                "reasons": decision.get("reasons", [])[:5]
                if isinstance(decision, dict) and isinstance(decision.get("reasons"), list)
                else [],
            },
            "set_metadata": set_metadata,
            "execution": mt5_optimization_report_refresh_execution_plan(
                kind="mt5_optimization_recommendation_refresh",
            ),
        }
        focus_side = str(set_metadata.get("focus_side") or "auto") if isinstance(set_metadata, dict) else "auto"
        stable_hint_coverage = set_metadata.get("stable_hint_coverage") if isinstance(set_metadata, dict) else []
        has_stable_hints = isinstance(stable_hint_coverage, list) and any(
            isinstance(row, dict) and row.get("applied") is True for row in stable_hint_coverage
        )
        stable_candidate_result = mt5_stable_candidate_result_summary(
            mt5_stable_candidate,
            mt5_stable_candidate_recommendation,
            mt5_stable_candidate_tester_run,
        )
        if stable_candidate_result:
            evidence["stable_candidate_result"] = stable_candidate_result
            stable_failure_context = mt5_stable_candidate_failure_context(
                mt5_stable_candidate,
                mt5_stable_candidate_recommendation,
            )
            if stable_failure_context:
                evidence["stable_candidate_failure_context"] = stable_failure_context
                stable_refit_target = mt5_stable_candidate_refit_target(
                    stable_failure_context,
                    mt5_stable_candidate_recommendation,
                    fallback_side=focus_side,
                )
                if stable_refit_target:
                    refit_kind = str(stable_refit_target.get("kind") or "")
                    refit_focus_side = str(stable_refit_target.get("focus_side") or "")
                    evidence["stable_candidate_refit"] = stable_refit_target
                    completed_refit = completed_refit_summary(refit_kind, refit_focus_side)
                    if completed_refit:
                        evidence["stable_candidate_refit_completed"] = completed_refit
                    else:
                        evidence["stable_candidate_refit_execution"] = tester_plan(
                            refit_kind,
                            refit_focus_side,
                            archive_run_id=tester_archive_run_id(refit_kind, refit_focus_side),
                        )
        elif (
            has_stable_hints
            and isinstance(set_metadata, dict)
            and set_metadata.get("diagnostic_only") is not True
            and focus_side in {"buy", "sell", "both"}
        ):
            stable_archive_run_id = tester_archive_run_id("stable_candidate", focus_side)
            evidence["stable_candidate_set_execution"] = mt5_stable_candidate_set_execution_plan(
                focus_side=focus_side,
            )
            evidence["stable_candidate_tester_execution"] = tester_plan(
                "stable_candidate",
                focus_side,
                archive_run_id=stable_archive_run_id,
            )
        if isinstance(score_refit_sides, list) and score_refit_sides:
            evidence["refit_execution"] = score_refit_plan(score_refit_side)
        add(
            2,
            "mt5_optimization_recommendation",
            "resolve_recommendation_before_using_next_set",
            "Latest MT5 optimization recommendation is not adoptable or skipped writing the next set; do not treat the existing focused .set as current.",
            evidence,
        )

    if "mt5_optimization_pf" in failed:
        sl_tp_focus_side = "sell"
        best_segments_source = mt5_optimization.get("best_segments")
        weak_segments_source = mt5_optimization.get("weak_segments")
        optimization_metric_failures = {
            name: row
            for name, row in failed.items()
            if name
            in {
                "mt5_optimization_closed_count",
                "mt5_optimization_pf",
                "mt5_optimization_buy_closed_count",
                "mt5_optimization_buy_pf",
                "mt5_optimization_buy_avg_price_r",
                "mt5_optimization_sell_closed_count",
                "mt5_optimization_sell_pf",
                "mt5_optimization_sell_avg_price_r",
            }
        }
        add(
            2,
            "sell_sl_tp",
            "narrow_sell_rr_sl_tp_search",
            "Optimization PF is below the promotion threshold; continue focused SELL search around profitable SL/TP bands and exclude weak TP bands.",
            {
                "failed_check": failed.get("mt5_optimization_pf"),
                "failed_checks": optimization_metric_failures,
                "focus_side": sl_tp_focus_side,
                "best_segments": compact_segments_for_side(best_segments_source, side=sl_tp_focus_side, limit=6),
                "weak_segments": compact_segments_for_side(weak_segments_source, side=sl_tp_focus_side, limit=6),
                "segment_side_summary": {
                    "focus_side": sl_tp_focus_side,
                    "best_counts": segment_side_counts(best_segments_source),
                    "weak_counts": segment_side_counts(weak_segments_source),
                },
                "execution": tester_plan("next_optimization", "sell"),
                "follow_up_execution": tester_plan("sell_entry_refit", "sell"),
            },
        )

    risk_shape_failures = {
        name: row
        for name, row in failed.items()
        if "max_drawdown" in name or "expectancy_" in name
    }
    if risk_shape_failures:
        add(
            2,
            "risk_shape",
            "reduce_drawdown_or_refit_expectancy_before_promotion",
            "Risk-shape gate failed; reduce drawdown concentration or refit the candidate until expectancy clears the configured threshold.",
            {
                "failed_checks": risk_shape_failures,
                "backtest_overall": summary.get("overall") if isinstance(summary, dict) else {},
                "forward_overall": forward if isinstance(forward, dict) else {},
                "mt5_forward_overall": mt5_forward_overall(mt5_forward) if isinstance(mt5_forward, dict) else {},
                "mt5_optimization_overall": mt5_optimization_overall(mt5_optimization)
                if isinstance(mt5_optimization, dict)
                else {},
                "mt5_yearly_optimization_overall": mt5_optimization_overall(mt5_yearly_optimization)
                if isinstance(mt5_yearly_optimization, dict)
                else {},
                "weight_search": compact_score_weight_search(risk_shape_weight_search) if risk_shape_weight_search else {},
                "execution": risk_shape_execution_plan(),
            },
        )

    mt5_yearly_failures = failed_subset(failed, "mt5_yearly_optimization_")
    if mt5_yearly_failures or "mt5_yearly_optimization_report" in failed:
        yearly_focus_side = mt5_optimization_focus_side(mt5_yearly_optimization or mt5_optimization)
        yearly_execution = yearly_validation_plan(yearly_focus_side)
        buy_calendar_rejected = (
            yearly_focus_side == "buy"
            and completed_unadoptable_side_refit(
                mt5_buy_hour03_wide_stop_calendar_validation_recommendation,
                "buy",
            )
        )
        yearly_evidence: dict[str, object] = {
            "failed_checks": {
                **mt5_yearly_failures,
                **(
                    {"mt5_yearly_optimization_report": failed["mt5_yearly_optimization_report"]}
                    if "mt5_yearly_optimization_report" in failed
                    else {}
                ),
            },
            "overall": mt5_optimization_overall(mt5_yearly_optimization)
            if isinstance(mt5_yearly_optimization, dict)
            else {},
            "weak_time_segments": compact_segments(
                mt5_yearly_optimization.get("weak_time_segments") if isinstance(mt5_yearly_optimization, dict) else None,
                limit=6,
            ),
            "weak_trend_segments": compact_segments(
                mt5_yearly_optimization.get("weak_trend_segments") if isinstance(mt5_yearly_optimization, dict) else None,
                limit=6,
            ),
            "weak_sl_tp_segments": compact_segments(
                mt5_yearly_optimization.get("weak_segments") if isinstance(mt5_yearly_optimization, dict) else None,
                limit=6,
            ),
            "chronological_failures": compact_segments(
                failed_chronological_splits(
                    mt5_yearly_optimization.get("chronological_splits")
                    if isinstance(mt5_yearly_optimization, dict)
                    else None
                ),
                limit=6,
            ),
            "source_time_file_filter": (
                mt5_yearly_optimization.get("source_time_file_filter")
                if isinstance(mt5_yearly_optimization, dict)
                else {}
            ),
            "execution": yearly_execution,
        }
        if buy_calendar_rejected:
            yearly_evidence["refit_blocked"] = {
                "reason": "buy_hour03_wide_stop_calendar_validation_not_adoptable",
                **buy_refit_follow_up_evidence(),
            }
        else:
            yearly_evidence["refit_execution"] = yearly_refit_plan(yearly_focus_side)
        yearly_archive_run_id = str(yearly_execution.get("agent_csv_archive_run_id") or "")
        if yearly_archive_run_id:
            yearly_evidence["archive_preview"] = mt5_agent_csv_archive_preview_execution_plan(
                run_id=yearly_archive_run_id
            )
        if mt5_yearly_collect_refresh_required(mt5_yearly_failures):
            yearly_evidence["collect_refresh"] = (
                mt5_optimization_report_refresh_execution_plan(
                    kind="mt5_optimization_recommendation_refresh",
                )
                if recommendation_blocks_next_optimization_set()
                else mt5_yearly_optimization_report_refresh_execution_plan()
            )
        add(
            2,
            "mt5_yearly_validation",
            "run_or_refit_yearly_out_of_year_validation",
            "Short-window optimization is not enough; the candidate must survive yearly/out-of-year PF, average R, stable pass, and chronological checks before promotion.",
            yearly_evidence,
        )

    mt5_yearly_score_inversion_failures = {
        name: row
        for name, row in failed.items()
        if name.startswith("mt5_yearly_optimization_") and name.endswith("_score_not_inverted")
    }
    if mt5_yearly_score_inversion_failures:
        score_inversion_side = mt5_score_inversion_focus_side(mt5_yearly_score_inversion_failures)
        add(
            2,
            "mt5_yearly_score",
            "refit_mt5_side_score_function_before_yearly_promotion",
            "Yearly/out-of-year score threshold is inverted for a side; refit side-specific scoring before treating the yearly result as promotable.",
            {
                "failed_checks": mt5_yearly_score_inversion_failures,
                "side_score_diagnostics": compact_side_score_diagnostics(
                    mt5_yearly_optimization.get("side_score_diagnostics")
                    if isinstance(mt5_yearly_optimization, dict)
                    else None,
                    limit=4,
                ),
                "execution": score_refit_plan(score_inversion_side),
                "score_weight_search": score_weight_search_plan(score_inversion_side),
                "score_weight_search_result": score_weight_search_result(score_inversion_side),
                "score_weight_set": score_weight_set_plan(score_inversion_side),
                "validation_execution": yearly_validation_plan(score_inversion_side),
                **score_weight_follow_up_evidence(score_inversion_side),
            },
        )

    mt5_forward_score_inversion_failures = {
        name: row
        for name, row in failed.items()
        if name.startswith("mt5_forward_") and name.endswith("_score_not_inverted")
    }
    if mt5_forward_score_inversion_failures:
        score_inversion_side = mt5_score_inversion_focus_side(mt5_forward_score_inversion_failures)
        add(
            3,
            "mt5_forward_score",
            "refit_mt5_side_score_function_before_forward_promotion",
            "MT5 forward score threshold is inverted for a side; refit side-specific scoring before promotion.",
            {
                "failed_checks": mt5_forward_score_inversion_failures,
                "side_score_diagnostics": compact_side_score_diagnostics(
                    mt5_forward.get("side_score_diagnostics") if isinstance(mt5_forward, dict) else None,
                    limit=4,
                ),
                "execution": score_refit_plan(score_inversion_side),
                "score_weight_search": score_weight_search_plan(score_inversion_side),
                "score_weight_search_result": score_weight_search_result(score_inversion_side),
                "score_weight_set": score_weight_set_plan(score_inversion_side),
                **score_weight_follow_up_evidence(score_inversion_side),
            },
        )

    mt5_forward_signal_evidence = compact_mt5_forward_signal(mt5_forward.get("signal")) if isinstance(mt5_forward, dict) else {}
    mt5_forward_reject_evidence = compact_mt5_forward_reject(mt5_forward.get("reject")) if isinstance(mt5_forward, dict) else {}
    mt5_forward_button_evidence = compact_mt5_forward_button(mt5_forward.get("button")) if isinstance(mt5_forward, dict) else {}
    mt5_forward_risk_evidence = (
        compact_mt5_forward_risk_exposure(mt5_forward.get("risk_exposure")) if isinstance(mt5_forward, dict) else {}
    )
    mt5_forward_sl_tp_evidence = compact_mt5_forward_sl_tp_diagnostics(mt5_forward) if isinstance(mt5_forward, dict) else {}

    mt5_forward_button_failures = {
        name: row for name, row in failed.items() if name in MT5_FORWARD_BUTTON_CHECK_NAMES
    }
    if mt5_forward_button_failures:
        add(
            3,
            "mt5_forward_button",
            "disable_chart_button_trading_before_forward_promotion",
            "MT5 forward contains chart-button rows that were not dry-run/ignored; do not use it as promotion evidence until button trading is disabled and Forward is rerun.",
            {
                "failed_checks": mt5_forward_button_failures,
                "button": mt5_forward_button_evidence,
                "signal": mt5_forward_signal_evidence,
                "reject": mt5_forward_reject_evidence,
                "risk_exposure": mt5_forward_risk_evidence,
                "sl_tp_diagnostics": mt5_forward_sl_tp_evidence,
                "compile": mt5_compile_execution_plan(),
                "risk_preset_fix": mt5_forward_button_safety_fix_plan(
                    mt5_forward.get("button") if isinstance(mt5_forward, dict) else {}
                ),
                "execution": strategy_forward_plan(),
            },
        )

    mt5_forward_risk_failures = {
        name: row for name, row in failed.items() if name in MT5_FORWARD_RISK_CHECK_NAMES
    }
    if mt5_forward_risk_failures:
        add(
            3,
            "mt5_forward_risk",
            "fix_mt5_forward_lot_position_and_stop_limits_before_promotion",
            "MT5 forward safety limits failed; do not promote until lot size, total exposure, position count, and loss-stop enforcement stay within configured limits.",
            {
                "failed_checks": mt5_forward_risk_failures,
                "risk_exposure": mt5_forward.get("risk_exposure") if isinstance(mt5_forward, dict) else {},
                "signal": mt5_forward_signal_evidence,
                "reject": mt5_forward_reject_evidence,
                "source_checks": mt5_forward.get("checks") if isinstance(mt5_forward, dict) else {},
                "sl_tp_diagnostics": mt5_forward_sl_tp_evidence,
                "compile": mt5_compile_execution_plan(),
                "execution": strategy_forward_plan(),
            },
        )

    mt5_forward_schema_failures = {
        name: row for name, row in failed.items() if name in MT5_FORWARD_SCHEMA_CHECK_NAMES
    }
    if mt5_forward_schema_failures:
        add(
            3,
            "mt5_forward_schema",
            "rerun_forward_with_current_ea_for_entry_trend_diagnostics",
            "MT5 forward CSV lacks entry-time, trend, or execution diagnostics; rerun Strategy Tester with the current EA before using regime or execution diagnostics.",
            {
                "failed_checks": mt5_forward_schema_failures,
                "csv_schema": mt5_forward.get("csv_schema") if isinstance(mt5_forward, dict) else {},
                "diagnostic_warnings": mt5_forward.get("diagnostic_warnings") if isinstance(mt5_forward, dict) else [],
                "signal": mt5_forward_signal_evidence,
                "reject": mt5_forward_reject_evidence,
                "risk_exposure": mt5_forward_risk_evidence,
                "sl_tp_diagnostics": mt5_forward_sl_tp_evidence,
                "compile": mt5_compile_execution_plan(),
                "execution": strategy_forward_plan(),
            },
        )

    mt5_forward_sl_tp_failures = {
        name: row for name, row in failed.items() if name in MT5_FORWARD_SL_TP_CHECK_NAMES
    }
    if mt5_forward_sl_tp_failures:
        add(
            3,
            "mt5_forward_diagnostics",
            "regenerate_mt5_forward_report_with_sl_tp_diagnostics",
            "MT5 forward report lacks required SL/TP diagnostics, including RR x TP; regenerate the report from current Forward CSV before promotion.",
            {
                "failed_checks": mt5_forward_sl_tp_failures,
                "signal": mt5_forward_signal_evidence,
                "reject": mt5_forward_reject_evidence,
                "risk_exposure": mt5_forward_risk_evidence,
                "sl_tp_diagnostics": mt5_forward_sl_tp_evidence,
                "execution": strategy_forward_plan(),
            },
        )

    mt5_forward_diagnostic_failures = {
        name: row for name, row in failed.items() if name in MT5_FORWARD_DIAGNOSTIC_CHECK_NAMES
    }
    if mt5_forward_diagnostic_failures:
        detected_loss_limits = (
            mt5_forward.get("reject", {}).get("detected_consecutive_loss_limits")
            if isinstance(mt5_forward, dict) and isinstance(mt5_forward.get("reject"), dict)
            else []
        )
        diagnostic_evidence: dict[str, object] = {
            "failed_checks": mt5_forward_diagnostic_failures,
            "diagnostic_warnings": mt5_forward.get("diagnostic_warnings") if isinstance(mt5_forward, dict) else [],
            "detected_consecutive_loss_limits": detected_loss_limits,
            "csv_schema": mt5_forward.get("csv_schema") if isinstance(mt5_forward, dict) else {},
            "signal": mt5_forward_signal_evidence,
            "reject": mt5_forward_reject_evidence,
            "risk_exposure": mt5_forward_risk_evidence,
            "sl_tp_diagnostics": mt5_forward_sl_tp_evidence,
            "compile": mt5_compile_execution_plan(),
            "execution": strategy_forward_plan(),
        }
        risk_preset_fix = mt5_forward_old_loss_limit_fix_plan(detected_loss_limits)
        if risk_preset_fix is not None:
            diagnostic_evidence["risk_preset_fix"] = risk_preset_fix
        add(
            3,
            "mt5_forward_diagnostics",
            "resolve_mt5_forward_diagnostic_warnings_before_promotion",
            "MT5 forward diagnostic warnings are present; fix stale EA/set/schema issues and rerun forward before promotion.",
            diagnostic_evidence,
        )

    mt5_forward_failures = {
        name: row
        for name, row in failed.items()
        if name.startswith("mt5_forward_")
        and not name.endswith("_score_not_inverted")
        and name not in MT5_FORWARD_BUTTON_CHECK_NAMES
        and name not in MT5_FORWARD_RISK_CHECK_NAMES
        and name not in MT5_FORWARD_SCHEMA_CHECK_NAMES
        and name not in MT5_FORWARD_SL_TP_CHECK_NAMES
        and name not in MT5_FORWARD_DIAGNOSTIC_CHECK_NAMES
    }
    if mt5_forward_failures:
        forward_candidate_blocked = recommendation_blocks_next_optimization_set()
        add(
            3,
            "mt5_forward",
            "resolve_recommendation_before_forward_performance_rerun"
            if forward_candidate_blocked
            else "rerun_forward_with_candidate_set_after_optimization",
            "Latest candidate set is not adoptable or not written; refresh the MT5 optimization recommendation before treating forward performance as candidate evidence."
            if forward_candidate_blocked
            else "MT5 forward evidence is weak; do not promote until the candidate .set survives forward with PF, losing streak, and side checks.",
            {
                "failed_checks": mt5_forward_failures,
                "overall": mt5_forward_overall(mt5_forward) if isinstance(mt5_forward, dict) else {},
                "signal": mt5_forward_signal_evidence,
                "reject": mt5_forward_reject_evidence,
                "risk_exposure": mt5_forward_risk_evidence,
                "sl_tp_diagnostics": mt5_forward_sl_tp_evidence,
                "execution": mt5_forward_performance_plan(),
            },
        )

    mt5_back_forward_failures = failed_subset(failed, "mt5_back_forward_run_")
    if "mt5_back_forward_run" in failed:
        mt5_back_forward_failures["mt5_back_forward_run"] = failed["mt5_back_forward_run"]
    if mt5_back_forward_failures:
        plan_only = "mt5_back_forward_run" in mt5_back_forward_failures
        performance_check = mt5_back_forward_failures.get("mt5_back_forward_run_performance")
        performance_value = (
            performance_check.get("value")
            if isinstance(performance_check, dict) and isinstance(performance_check.get("value"), dict)
            else {}
        )
        comparison_status = str(performance_value.get("status") or mt5_back_forward.get("performance_comparison_status") or "")
        sample_shortage = "sample_shortage" in comparison_status or performance_value.get("sample_shortage") is True
        add(
            2,
            "mt5_back_forward",
            "run_mt5_back_forward_runner_before_promotion"
            if plan_only
            else "collect_more_mt5_back_forward_samples_before_promotion"
            if sample_shortage
            else "reject_candidate_after_mt5_back_forward_drift",
            "MT5 Back/Forward Runner is still plan-only; execute the MT5 backtest/forward pair before treating it as promotion evidence."
            if plan_only
            else "MT5 Back/Forward Runner closed-trade count is below the min_closed threshold; extend the test window or loosen diagnostic gates before judging performance."
            if sample_shortage
            else "MT5 Back/Forward Runner evidence is not consistent; do not promote this candidate until backtest and forward results are stable.",
            {
                "failed_checks": mt5_back_forward_failures,
                "runner": mt5_back_forward,
                "sample_shortage": {
                    "status": comparison_status,
                    "min_closed": performance_value.get("min_closed", ""),
                    "backtest_trades": performance_value.get("backtest_trades", ""),
                    "forward_trades": performance_value.get("forward_trades", ""),
                    "backtest_meets_min_closed": performance_value.get("backtest_meets_min_closed", ""),
                    "forward_meets_min_closed": performance_value.get("forward_meets_min_closed", ""),
                }
                if sample_shortage
                else {},
                "sample_shortage_recovery": mt5_back_forward_sample_shortage_recovery_plan(performance_value)
                if sample_shortage
                else {},
                "execution": mt5_back_forward_run_execution_plan(),
            },
        )

    mt5_status_watch_failures = failed_subset(failed, "mt5_status_watch_")
    if mt5_status_watch_failures:
        watcher = (
            mt5_tester_status.get("status_watch_heartbeat")
            if isinstance(mt5_tester_status.get("status_watch_heartbeat"), dict)
            else {}
        )
        add(
            2,
            "mt5_status_watch",
            "restart_mt5_status_watch_with_current_schema",
            "MT5 status watcher heartbeat is stale, incompatible, or not current for the latest Next Action or Back/Forward plan; restart the watcher before relying on heartbeat-only monitoring.",
            {
                "failed_checks": mt5_status_watch_failures,
                "status_watch_heartbeat": watcher,
                "execution": mt5_status_watch_restart_execution_plan(),
            },
        )

    score_sample_failure = failed.get("score_upper_threshold_sample")
    score_quality_failures = {
        name: row
        for name, row in failed.items()
        if (
            name.startswith("score_upper_threshold_")
            or name.startswith("score_threshold_")
        )
        and name != "score_upper_threshold_sample"
    }
    if score_sample_failure:
        add(
            3,
            "score_calibration",
            "calibrate_score_scale_or_collect_high_score_samples",
            "High-score gate has too few samples; recalibrate the score scale or collect enough high-score candidates before treating score as a promotion signal.",
            {
                "failed_check": score_sample_failure,
                "quality_failed_checks": score_quality_failures,
                "thresholds": compact_thresholds(summary.get("thresholds") if isinstance(summary, dict) else None),
                "calibration": score_calibration,
                "weight_search": compact_score_weight_search(score_weight_search),
                "execution": score_calibration_execution_plan(),
            },
        )

    if score_quality_failures and not score_sample_failure:
        add(
            3,
            "score_quality",
            "refit_score_so_higher_thresholds_improve_expectancy",
            "Score quality gate failed despite enough high-score samples; refit the evaluation function so higher scores improve expectancy.",
            {
                "failed_checks": score_quality_failures,
                "thresholds": compact_thresholds(summary.get("thresholds") if isinstance(summary, dict) else None),
                "weight_search": compact_score_weight_search(score_weight_search),
                "execution": score_calibration_execution_plan(),
            },
        )

    if any(name.startswith("forward_") for name in failed) and python_forward_waiting_for_tradable_signal(report):
        add(
            4,
            "python_forward",
            "wait_for_tradable_signal_before_forward_record",
            "Python forward ledger has no tradable signal to record right now; keep the watcher running and wait for a BUY/SELL signal.",
            {
                "failed_checks": failed_subset(failed, "forward_"),
                "forward_status": report.get("forward_status"),
                "forward_status_watch_heartbeat": report.get("forward_status_watch_heartbeat"),
                "forward_test_watch_heartbeat": report.get("forward_test_watch_heartbeat"),
                "execution": python_forward_execution_plan(),
            },
        )

    elif any(name.startswith("forward_") for name in failed):
        add(
            4,
            "python_forward",
            "collect_forward_ledger_samples",
            "Python forward ledger has insufficient or weak closed samples; keep forward_test_watch running before using it as promotion evidence.",
            {
                "failed_checks": failed_subset(failed, "forward_"),
                "forward_status_watch_heartbeat": report.get("forward_status_watch_heartbeat"),
                "forward_test_watch_heartbeat": report.get("forward_test_watch_heartbeat"),
                "execution": python_forward_execution_plan(),
            },
        )

    winrate_fit_failures = failed_subset(failed, "winrate_fit_")
    if winrate_fit_failures:
        add(
            4,
            "winrate_fit",
            "run_walk_forward_fit_and_require_adoption",
            "A fitted rule has not passed train/validation/test and walk-forward adoption checks.",
            {
                "failed_checks": winrate_fit_failures,
                "winrate_fit": report.get("winrate_fit"),
                "execution": winrate_fit_execution_plan(),
            },
        )

    dry_run_risk_gate_failure = failed.get("dry_run_risk_gate_allowed")
    if dry_run_risk_gate_failure:
        risk_gate_value = dry_run_risk_gate_failure.get("value") if isinstance(dry_run_risk_gate_failure, dict) else None
        if isinstance(risk_gate_value, dict) and risk_gate_value.get("allowed") is False:
            add(
                5,
                "dry_run_risk_gate",
                "resolve_risk_gate_block_before_refreshing_dry_run",
                "Risk gate rejected the dry-run command; reduce exposure or wait for the risk block to clear before using dry-run as promotion evidence.",
                {
                    "failed_check": dry_run_risk_gate_failure,
                    "risk_gate": risk_gate_value,
                    "execution": dry_run_refresh_execution_plan(),
                },
            )
        else:
            add(
                5,
                "dry_run_risk_gate",
                "refresh_dry_run_with_embedded_risk_gate_snapshot",
                "Dry-run evidence lacks embedded risk_gate.allowed=true; regenerate dry-run command with current risk gate metadata before promotion.",
                {
                    "failed_check": dry_run_risk_gate_failure,
                    "execution": dry_run_refresh_execution_plan(),
                },
            )

    dry_run_waiting_for_signal = dry_run_passed_waiting_for_tradable_signal(report, failed.get("dry_run_passed"))
    if dry_run_waiting_for_signal:
        dry_run_wait_failures = {
            name: failed[name]
            for name in (
                "dry_run_passed",
                "dry_run_fresh",
                "dry_run_signal_command_match",
                "dry_run_command_sl_tp_present",
                "dry_run_command_score_floor",
                "dry_run_command_spread_limit_present",
                "dry_run_command_lot_policy_present",
            )
            if name in failed
        }
        execution = dry_run_refresh_execution_plan()
        execution["note"] = "Run this only after latest_signal.action becomes BUY or SELL; current HOLD rejection is not promotion evidence."
        add(
            5,
            "dry_run",
            "wait_for_tradable_signal_before_dry_run",
            "Latest signal is non-tradable and was correctly rejected before EA polling; wait for a BUY/SELL signal before using EA dry-run evidence.",
            {
                "failed_checks": dry_run_wait_failures,
                "dry_run_audit": report.get("dry_run_audit"),
                "execution": execution,
            },
        )

    dry_run_refresh_failures = {
        name: failed[name]
        for name in (
            "dry_run_passed",
            "dry_run_fresh",
            "dry_run_signal_command_match",
            "dry_run_command_sl_tp_present",
            "dry_run_command_score_floor",
            "dry_run_command_spread_limit_present",
            "dry_run_command_lot_policy_present",
        )
        if name in failed and not dry_run_waiting_for_signal and not dry_run_risk_gate_failure
    }
    if dry_run_refresh_failures:
        add(
            5,
            "dry_run",
            "refresh_dry_run_with_current_signal",
            "Dry-run evidence is missing, stale, or inconsistent with the latest signal; it cannot support promotion.",
            {
                "failed_checks": dry_run_refresh_failures,
                "execution": dry_run_refresh_execution_plan(),
            },
        )

    backtest_sample_failures = {
        name: failed[name]
        for name in ("candidate_count", "history_hours", "history_timeframes_complete")
        if name in failed
    }
    if backtest_sample_failures:
        add(
            5,
            "backtest_sample",
            "increase_candidate_sample_or_history_before_gate",
            "Backtest candidate count or history coverage is below the minimum gate and cannot support robust adoption.",
            {
                "failed_check": failed.get("candidate_count"),
                "failed_checks": backtest_sample_failures,
                "history_check": checks_by_name.get("history_hours"),
                "history_timeframes_check": checks_by_name.get("history_timeframes_complete"),
                "execution": backtest_sample_execution_plan(),
            },
        )

    if not actions:
        add(
            99,
            "promotion",
            "no_blocking_next_action",
            "All configured promotion checks passed.",
            {},
        )

    return sorted(actions, key=lambda row: (int(row.get("priority") or 99), str(row.get("area") or "")))


def dry_run_passed_waiting_for_tradable_signal(
    report: dict[str, object],
    failed_check: dict[str, object] | None,
) -> bool:
    if not failed_check:
        return False
    audit = report.get("dry_run_audit") if isinstance(report.get("dry_run_audit"), dict) else {}
    if audit.get("outcome") != "blocked_before_ea" or audit.get("dry_run_only") is not True:
        return False
    signal = audit.get("signal") if isinstance(audit.get("signal"), dict) else {}
    command = audit.get("command") if isinstance(audit.get("command"), dict) else {}
    signal_command = audit.get("signal_command") if isinstance(audit.get("signal_command"), dict) else {}
    risk_gate = audit.get("risk_gate") if isinstance(audit.get("risk_gate"), dict) else {}
    signal_action = str(signal.get("action", "")).lower()
    command_status = str(command.get("status", "")).lower()
    return (
        signal_action not in {"buy", "sell"}
        and command_status == "rejected"
        and audit.get("signal_command_match") is True
        and signal_command.get("matched") is True
        and risk_gate.get("allowed") is True
    )


def python_forward_waiting_for_tradable_signal(report: dict[str, object]) -> bool:
    status = report.get("forward_status") if isinstance(report.get("forward_status"), dict) else {}
    signal = status.get("signal") if isinstance(status.get("signal"), dict) else {}
    return (
        status.get("operational_status") == "waiting_for_tradable_signal"
        and signal.get("recordability") == "ignored"
        and str(signal.get("action", "")).lower() not in {"buy", "sell"}
    )


PROMOTION_ARCHIVE_RUN_ID_SOURCE_KEYS = (
    "summary",
    "mt5_forward_test",
    "mt5_optimization",
    "mt5_optimization_recommendation",
    "mt5_tester_run",
    "mt5_stable_candidate",
    "mt5_stable_candidate_recommendation",
    "mt5_stable_candidate_tester_run",
    "mt5_buy_refit_recommendation",
    "mt5_buy_entry_refit_recommendation",
    "mt5_sell_entry_refit_recommendation",
    "mt5_sell_regime_entry_refit_recommendation",
    "mt5_buy_hour03_validation_recommendation",
    "mt5_buy_hour03_wide_stop_validation_recommendation",
    "mt5_buy_hour03_wide_stop_calendar_validation_recommendation",
    "mt5_yearly_optimization",
    "score_weight_search",
    "score_weight_search_by_side",
    "score_weight_set_by_side",
    "risk_shape_weight_search",
    "winrate_fit",
)

PROMOTION_ARCHIVE_RUN_ID_SOURCE_KEYS_BY_AREA = {
    "score_weight_sample_collection": (
        "mt5_optimization_recommendation",
        "mt5_buy_refit_recommendation",
        "mt5_buy_entry_refit_recommendation",
        "mt5_sell_entry_refit_recommendation",
        "mt5_sell_regime_entry_refit_recommendation",
        "mt5_buy_hour03_validation_recommendation",
        "mt5_buy_hour03_wide_stop_validation_recommendation",
        "mt5_buy_hour03_wide_stop_calendar_validation_recommendation",
        "score_weight_search",
        "score_weight_search_by_side",
        "score_weight_set_by_side",
        "risk_shape_weight_search",
        "winrate_fit",
    ),
}


def nested_report_times(value: object) -> list[datetime]:
    times: list[datetime] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"generated_at", "source_generated_at", "runner_generated_at"}:
                parsed = parse_report_time(item)
                if parsed is not None:
                    times.append(parsed)
                continue
            times.extend(nested_report_times(item))
    elif isinstance(value, list):
        for item in value:
            times.extend(nested_report_times(item))
    return times


def promotion_archive_run_id_source_keys(area: str) -> tuple[str, ...]:
    return PROMOTION_ARCHIVE_RUN_ID_SOURCE_KEYS_BY_AREA.get(area, PROMOTION_ARCHIVE_RUN_ID_SOURCE_KEYS)


def promotion_archive_source_time(report: dict[str, object], *, area: str = "") -> datetime | None:
    times: list[datetime] = []
    for key in promotion_archive_run_id_source_keys(area):
        if key in report:
            times.extend(nested_report_times(report.get(key)))
    return max(times) if times else None


def promotion_archive_run_id(report: dict[str, object], area: str, kind: str, focus_side: str = "") -> str:
    generated = promotion_archive_source_time(report, area=area) or parse_report_time(report.get("generated_at")) or datetime.now()
    raw = f"promotion_{generated.strftime('%Y%m%d_%H%M')}_{area}_{kind}_{focus_side}".strip("_")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    return "".join(char if char in allowed else "_" for char in raw)


def attach_latest_executed_tester_xml_rows(
    execution: dict[str, object],
    sources_by_output_json: dict[str, dict[str, object]],
) -> None:
    if execution.get("latest_executed_tester_xml_rows") is not None:
        return
    if not execution_supports_tester_xml_rows(execution):
        return
    outputs = execution.get("outputs")
    output_json = ""
    if isinstance(outputs, dict):
        output_json = str(outputs.get("optimization_json") or "")
    candidate_sources: list[tuple[str, dict[str, object]]] = []
    exact_summary = sources_by_output_json.get(output_json)
    if isinstance(exact_summary, dict) and exact_summary:
        candidate_sources.append((output_json, exact_summary))

    optimization_mode = str(execution.get("optimization_mode") or "").lower()
    if optimization_mode != "single":
        for source_json, source_summary in sources_by_output_json.items():
            if source_json == output_json:
                continue
            if isinstance(source_summary, dict) and source_summary:
                candidate_sources.append((source_json, source_summary))

    full_factorial = number(execution.get("estimated_full_factorial_passes"))
    for source_json, summary in candidate_sources:
        budget = summary.get("optimization_pass_budget")
        if not isinstance(budget, dict):
            continue
        rows = budget.get("executed_tester_xml_rows")
        if not isinstance(rows, dict):
            continue
        visible_rows: dict[str, object] = {}
        for key in ("back", "forward"):
            value = rows.get(key)
            if numeric_value_present(value):
                visible_rows[key] = int(number(value)) if float(number(value)).is_integer() else number(value)
        if not visible_rows:
            continue
        if source_json:
            visible_rows["source"] = source_json
        if full_factorial > 0:
            ratios: dict[str, float] = {}
            for key in ("back", "forward"):
                if key in visible_rows and numeric_value_present(visible_rows[key]):
                    ratios[key] = round(number(visible_rows[key]) / full_factorial, 4)
            if ratios:
                visible_rows["ratio_vs_full_factorial"] = ratios
        execution["latest_executed_tester_xml_rows"] = visible_rows
        return


def execution_supports_tester_xml_rows(execution: dict[str, object]) -> bool:
    if execution.get("estimated_full_factorial_passes") is not None:
        return True
    outputs = execution.get("outputs")
    if isinstance(outputs, dict) and (outputs.get("optimization_json") or outputs.get("recommendation_json")):
        return True
    command = str(execution.get("command_text") or "")
    return "methods/swing_eval/analysis/mt5_tester_run.py" in command or "methods/swing_eval/analysis/mt5_tester_optimization_report.py" in command


def failed_subset(failed: dict[str, dict[str, object]], prefix: str) -> dict[str, dict[str, object]]:
    return {name: row for name, row in failed.items() if name.startswith(prefix)}


def mt5_tester_execution_plan(
    kind: str,
    *,
    focus_side: str,
    archive_run_id: str | None = None,
) -> dict[str, object]:
    archive_run_id = archive_run_id or promotion_archive_run_id({}, "mt5_tester", kind, focus_side)
    presets: dict[str, dict[str, str]] = {
        "next_optimization": {
            "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_next_optimization.ini",
            "set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set",
            "report_name": r"Tester\Swing_Evaluation_Trader_next_optimization",
            "output_json": "runtime/latest_mt5_tester_run.json",
            "output_md": "runtime/latest_mt5_tester_run.md",
            "optimization_output_json": "runtime/latest_mt5_optimization_report.json",
            "optimization_output_md": "runtime/latest_mt5_optimization_report.md",
            "recommendation_output_json": "runtime/latest_mt5_optimization_recommendation.json",
            "recommendation_output_md": "runtime/latest_mt5_optimization_recommendation.md",
            "output_set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set",
        },
        "stable_candidate": {
            "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_stable_candidate.ini",
            "set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_stable_candidate_next.set",
            "template_set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_stable_candidate_next.set",
            "report_name": r"Tester\Swing_Evaluation_Trader_stable_candidate",
            "output_json": "runtime/latest_mt5_tester_stable_candidate_run.json",
            "output_md": "runtime/latest_mt5_tester_stable_candidate_run.md",
            "optimization_output_json": "runtime/latest_mt5_stable_candidate_optimization_report.json",
            "optimization_output_md": "runtime/latest_mt5_stable_candidate_optimization_report.md",
            "recommendation_output_json": "runtime/latest_mt5_stable_candidate_recommendation.json",
            "recommendation_output_md": "runtime/latest_mt5_stable_candidate_recommendation.md",
            "output_set": "runtime/Swing_Evaluation_Trader_stable_candidate_followup.set",
            "sync_expert_parameters_set": "true",
        },
        "buy_refit": {
            "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_refit.ini",
            "set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_refit.set",
            "template_set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_refit.set",
            "report_name": r"Tester\Swing_Evaluation_Trader_buy_refit",
            "output_json": "runtime/latest_mt5_tester_buy_refit_run.json",
            "output_md": "runtime/latest_mt5_tester_buy_refit_run.md",
            "optimization_output_json": "runtime/latest_mt5_buy_refit_optimization_report.json",
            "optimization_output_md": "runtime/latest_mt5_buy_refit_optimization_report.md",
            "recommendation_output_json": "runtime/latest_mt5_buy_refit_recommendation.json",
            "recommendation_output_md": "runtime/latest_mt5_buy_refit_recommendation.md",
            "output_set": "runtime/Swing_Evaluation_Trader_buy_refit_next.set",
        },
        "buy_entry_refit": {
            "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_entry_refit.ini",
            "set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_entry_refit.set",
            "template_set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_entry_refit.set",
            "report_name": r"Tester\Swing_Evaluation_Trader_buy_entry_refit",
            "output_json": "runtime/latest_mt5_tester_buy_entry_refit_run.json",
            "output_md": "runtime/latest_mt5_tester_buy_entry_refit_run.md",
            "optimization_output_json": "runtime/latest_mt5_buy_entry_refit_optimization_report.json",
            "optimization_output_md": "runtime/latest_mt5_buy_entry_refit_optimization_report.md",
            "recommendation_output_json": "runtime/latest_mt5_buy_entry_refit_recommendation.json",
            "recommendation_output_md": "runtime/latest_mt5_buy_entry_refit_recommendation.md",
            "output_set": "runtime/Swing_Evaluation_Trader_buy_entry_refit_next.set",
        },
        "buy_hour03_validation": {
            "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_validation.ini",
            "set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_validation.set",
            "template_set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_validation.set",
            "report_name": r"Tester\Swing_Evaluation_Trader_buy_hour03_validation",
            "output_json": "runtime/latest_mt5_tester_buy_hour03_validation_run.json",
            "output_md": "runtime/latest_mt5_tester_buy_hour03_validation_run.md",
            "optimization_output_json": "runtime/latest_mt5_buy_hour03_validation_optimization_report.json",
            "optimization_output_md": "runtime/latest_mt5_buy_hour03_validation_optimization_report.md",
            "recommendation_output_json": "runtime/latest_mt5_buy_hour03_validation_recommendation.json",
            "recommendation_output_md": "runtime/latest_mt5_buy_hour03_validation_recommendation.md",
            "output_set": "runtime/Swing_Evaluation_Trader_buy_hour03_validation_next.set",
        },
        "buy_hour03_wide_stop_validation": {
            "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.ini",
            "set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set",
            "template_set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set",
            "report_name": r"Tester\Swing_Evaluation_Trader_buy_hour03_wide_stop_validation",
            "output_json": "runtime/latest_mt5_tester_buy_hour03_wide_stop_validation_run.json",
            "output_md": "runtime/latest_mt5_tester_buy_hour03_wide_stop_validation_run.md",
            "optimization_output_json": "runtime/latest_mt5_buy_hour03_wide_stop_validation_optimization_report.json",
            "optimization_output_md": "runtime/latest_mt5_buy_hour03_wide_stop_validation_optimization_report.md",
            "recommendation_output_json": "runtime/latest_mt5_buy_hour03_wide_stop_validation_recommendation.json",
            "recommendation_output_md": "runtime/latest_mt5_buy_hour03_wide_stop_validation_recommendation.md",
            "output_set": "runtime/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation_next.set",
        },
        "buy_hour03_wide_stop_calendar_validation": {
            "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.ini",
            "set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set",
            "template_set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set",
            "report_name": r"Tester\Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation",
            "output_json": "runtime/latest_mt5_tester_buy_hour03_wide_stop_calendar_validation_run.json",
            "output_md": "runtime/latest_mt5_tester_buy_hour03_wide_stop_calendar_validation_run.md",
            "optimization_output_json": "runtime/latest_mt5_buy_hour03_wide_stop_calendar_validation_optimization_report.json",
            "optimization_output_md": "runtime/latest_mt5_buy_hour03_wide_stop_calendar_validation_optimization_report.md",
            "recommendation_output_json": "runtime/latest_mt5_buy_hour03_wide_stop_calendar_validation_recommendation.json",
            "recommendation_output_md": "runtime/latest_mt5_buy_hour03_wide_stop_calendar_validation_recommendation.md",
            "output_set": "runtime/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation_next.set",
        },
        "sell_entry_refit": {
            "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_entry_refit.ini",
            "set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sell_entry_refit.set",
            "template_set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sell_entry_refit.set",
            "report_name": r"Tester\Swing_Evaluation_Trader_sell_entry_refit",
            "output_json": "runtime/latest_mt5_tester_sell_entry_refit_run.json",
            "output_md": "runtime/latest_mt5_tester_sell_entry_refit_run.md",
            "optimization_output_json": "runtime/latest_mt5_sell_entry_refit_optimization_report.json",
            "optimization_output_md": "runtime/latest_mt5_sell_entry_refit_optimization_report.md",
            "recommendation_output_json": "runtime/latest_mt5_sell_entry_refit_recommendation.json",
            "recommendation_output_md": "runtime/latest_mt5_sell_entry_refit_recommendation.md",
            "output_set": "runtime/Swing_Evaluation_Trader_sell_entry_refit_next.set",
        },
        "sell_regime_entry_refit": {
            "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_regime_entry_refit.ini",
            "set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sell_regime_entry_refit.set",
            "template_set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sell_regime_entry_refit.set",
            "report_name": r"Tester\Swing_Evaluation_Trader_sell_regime_entry_refit",
            "output_json": "runtime/latest_mt5_tester_sell_regime_entry_refit_run.json",
            "output_md": "runtime/latest_mt5_tester_sell_regime_entry_refit_run.md",
            "optimization_output_json": "runtime/latest_mt5_sell_regime_entry_refit_optimization_report.json",
            "optimization_output_md": "runtime/latest_mt5_sell_regime_entry_refit_optimization_report.md",
            "recommendation_output_json": "runtime/latest_mt5_sell_regime_entry_refit_recommendation.json",
            "recommendation_output_md": "runtime/latest_mt5_sell_regime_entry_refit_recommendation.md",
            "output_set": "runtime/Swing_Evaluation_Trader_sell_regime_entry_refit_next.set",
        },
    }
    preset = presets.get(kind, {})
    set_estimate: dict[str, object] = {}
    set_path = preset.get("set", "")
    if set_path and Path(set_path).exists():
        set_estimate = estimate_set_passes(Path(set_path).read_text(encoding="utf-8"))
    timeout_seconds = 7200
    command = [
        "python3",
        "methods/swing_eval/analysis/mt5_tester_run.py",
        "--config",
        preset.get("config", ""),
        "--report-name",
        preset.get("report_name", ""),
        "--timeout-seconds",
        str(timeout_seconds),
        "--since-minutes",
        "240",
        "--archive-agent-csvs-before-run",
    ]
    if archive_run_id:
        command.extend(["--agent-csv-archive-run-id", archive_run_id])
    command.extend([
        "--min-closed",
        "100",
        "--min-segment-closed",
        "500",
        "--min-segment-pf",
        "1.2",
        "--focus-side",
        focus_side,
        "--output-json",
        preset.get("output_json", ""),
        "--output-md",
        preset.get("output_md", ""),
        "--optimization-output-json",
        preset.get("optimization_output_json", ""),
        "--optimization-output-md",
        preset.get("optimization_output_md", ""),
        "--recommendation-output-json",
        preset.get("recommendation_output_json", ""),
        "--recommendation-output-md",
        preset.get("recommendation_output_md", ""),
    ])
    if preset.get("template_set"):
        command.extend(["--template-set", preset.get("template_set", "")])
    command.extend(["--output-set", preset.get("output_set", "")])
    if preset.get("sync_expert_parameters_set") == "true":
        command.append("--sync-expert-parameters-set")
    plan = {
        "kind": kind,
        "focus_side": focus_side,
        "optimization_mode": "genetic",
        "config": preset.get("config", ""),
        "set": preset.get("set", ""),
        "template_set": preset.get("template_set", ""),
        "sync_expert_parameters_set": preset.get("sync_expert_parameters_set") == "true",
        "report_name": preset.get("report_name", ""),
        "agent_csv_archive_run_id": archive_run_id or "",
        "outputs": {
            "run_json": preset.get("output_json", ""),
            "run_md": preset.get("output_md", ""),
            "optimization_json": preset.get("optimization_output_json", ""),
            "optimization_md": preset.get("optimization_output_md", ""),
            "recommendation_json": preset.get("recommendation_output_json", ""),
            "recommendation_md": preset.get("recommendation_output_md", ""),
            "output_set": preset.get("output_set", ""),
        },
        "command": command,
        "command_text": command_text(command),
    }
    attach_execution_timeout(
        plan,
        timeout_seconds,
        note="Maximum terminal runtime; MT5 genetic optimization may finish earlier than the full-factorial pass count.",
    )
    if set_estimate:
        plan["optimized_input_count"] = set_estimate.get("optimized_input_count")
        plan["estimated_full_factorial_passes"] = set_estimate.get("estimated_full_factorial_passes")
        plan["optimized_inputs"] = set_estimate.get("optimized_inputs")
    return plan


def mt5_strategy_forward_execution_plan(*, archive_run_id: str | None = None) -> dict[str, object]:
    archive_run_id = archive_run_id or promotion_archive_run_id({}, "mt5_forward", "strategy_forward", "both")
    set_path = "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_forward_test.set"
    config_path = "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_forward_test.ini"
    report_name = r"Tester\Swing_Evaluation_Trader_forward_test"
    set_estimate: dict[str, object] = {}
    if Path(set_path).exists():
        set_estimate = estimate_set_passes(Path(set_path).read_text(encoding="utf-8"))
    timeout_seconds = 7200
    tester_command = [
        "python3",
        "methods/swing_eval/analysis/mt5_tester_run.py",
        "--config",
        config_path,
        "--report-name",
        report_name,
        "--timeout-seconds",
        str(timeout_seconds),
        "--since-minutes",
        "240",
        "--archive-agent-csvs-before-run",
        "--agent-csv-archive-run-id",
        archive_run_id,
        "--min-closed",
        "30",
        "--no-recommendation",
        "--output-json",
        "runtime/latest_mt5_tester_forward_test_run.json",
        "--output-md",
        "runtime/latest_mt5_tester_forward_test_run.md",
        "--optimization-output-json",
        "runtime/latest_mt5_forward_strategy_report.json",
        "--optimization-output-md",
        "runtime/latest_mt5_forward_strategy_report.md",
    ]
    collect_command = [
        "python3",
        "methods/swing_eval/analysis/mt5_forward_collect.py",
        "--destination",
        "runtime/mt5_forward/swing_evaluation_trades.csv",
        "--output-json",
        "runtime/latest_mt5_forward_report.json",
        "--output-md",
        "runtime/latest_mt5_forward_report.md",
        "--collect-status-json",
        "runtime/latest_mt5_forward_collect.json",
        "--min-closed",
        "30",
        "--min-pf",
        "1.2",
        "--max-losing-streak",
        "20",
    ]
    plan: dict[str, object] = {
        "kind": "strategy_forward",
        "focus_side": "both",
        "optimization_mode": "single",
        "config": config_path,
        "set": set_path,
        "report_name": report_name,
        "agent_csv_archive_run_id": archive_run_id,
        "outputs": {
            "run_json": "runtime/latest_mt5_tester_forward_test_run.json",
            "run_md": "runtime/latest_mt5_tester_forward_test_run.md",
            "optimization_json": "runtime/latest_mt5_forward_strategy_report.json",
            "optimization_md": "runtime/latest_mt5_forward_strategy_report.md",
            "forward_json": "runtime/latest_mt5_forward_report.json",
            "forward_md": "runtime/latest_mt5_forward_report.md",
            "collect_status_json": "runtime/latest_mt5_forward_collect.json",
        },
        "command": tester_command,
        "command_text": command_text(tester_command),
        "follow_up_command": collect_command,
        "follow_up_command_text": command_text(collect_command),
    }
    attach_execution_timeout(
        plan,
        timeout_seconds,
        note="Maximum terminal runtime for the Strategy Tester forward run.",
    )
    if set_estimate:
        plan["optimized_input_count"] = set_estimate.get("optimized_input_count")
        plan["estimated_full_factorial_passes"] = set_estimate.get("estimated_full_factorial_passes")
        plan["optimized_inputs"] = set_estimate.get("optimized_inputs")
    return plan


def mt5_score_inversion_focus_side(failures: dict[str, dict[str, object]]) -> str:
    sides: list[str] = []
    for name in failures:
        if (
            name.startswith("mt5_forward_buy_")
            or name.startswith("mt5_optimization_buy_")
            or name.startswith("mt5_yearly_optimization_buy_")
        ):
            sides.append("buy")
        if (
            name.startswith("mt5_forward_sell_")
            or name.startswith("mt5_optimization_sell_")
            or name.startswith("mt5_yearly_optimization_sell_")
        ):
            sides.append("sell")
    unique = sorted(set(sides))
    if len(unique) == 1:
        return unique[0]
    return "both"


def mt5_score_refit_target(side: str) -> tuple[str, str]:
    if side == "buy":
        return "buy_refit", "buy"
    if side == "sell":
        return "next_optimization", "sell"
    return "next_optimization", "both"


def mt5_score_refit_execution_plan(side: str, *, archive_run_id: str | None = None) -> dict[str, object]:
    kind, focus_side = mt5_score_refit_target(side)
    return mt5_tester_execution_plan(kind, focus_side=focus_side, archive_run_id=archive_run_id)


def mt5_regime_refit_target(side: str) -> tuple[str, str]:
    if side == "buy":
        return "buy_entry_refit", "buy"
    if side == "sell":
        return "sell_regime_entry_refit", "sell"
    return "next_optimization", "both"


def mt5_regime_refit_execution_plan(side: str, *, archive_run_id: str | None = None) -> dict[str, object]:
    kind, focus_side = mt5_regime_refit_target(side)
    return mt5_tester_execution_plan(kind, focus_side=focus_side, archive_run_id=archive_run_id)


def mt5_yearly_refit_target(side: str) -> tuple[str, str]:
    if side == "buy":
        return "buy_hour03_wide_stop_calendar_validation", "buy"
    if side == "sell":
        return "sell_regime_entry_refit", "sell"
    return "next_optimization", "both"


def mt5_yearly_refit_execution_plan(side: str, *, archive_run_id: str | None = None) -> dict[str, object]:
    kind, focus_side = mt5_yearly_refit_target(side)
    return mt5_tester_execution_plan(kind, focus_side=focus_side, archive_run_id=archive_run_id)


def mt5_compile_execution_plan() -> dict[str, object]:
    command = [
        "python3",
        "methods/swing_eval/analysis/mt5_compile.py",
        "--timeout-seconds",
        "90",
        "--output-json",
        "runtime/latest_mt5_compile_run.json",
        "--output-md",
        "runtime/latest_mt5_compile_run.md",
        "--status-output-json",
        "runtime/latest_mt5_compile_status.json",
        "--status-output-md",
        "runtime/latest_mt5_compile_status.md",
    ]
    return {
        "kind": "mt5_compile",
        "command": command,
        "command_text": command_text(command),
        "outputs": {
            "compile_run_json": "runtime/latest_mt5_compile_run.json",
            "compile_run_md": "runtime/latest_mt5_compile_run.md",
            "compile_status_json": "runtime/latest_mt5_compile_status.json",
            "compile_status_md": "runtime/latest_mt5_compile_status.md",
        },
    }


def mt5_risk_preset_fix_plan(failed_value: dict[str, object]) -> dict[str, object]:
    preset = failed_value.get("risk_preset") if isinstance(failed_value.get("risk_preset"), dict) else {}
    set_file = str(preset.get("set_file") or "")
    command_text = (
        "manual: fix MT5 risk preset"
        + (f" in {set_file}" if set_file else "")
        + " (InpUseConsecutiveLossStop=true, InpConsecutiveLossLimit>=20, "
        "InpConsecutiveLossCooldownMinutes>=120, InpRequireStrategyTester=true, "
        "InpChartButtonDryRunOnly=true, "
        "InpAllowChartButtonTrading=false)"
    )
    return {
        "kind": "mt5_risk_preset_fix",
        "command_text": command_text,
        "set_file": set_file,
        "mode": preset.get("mode", ""),
        "ok": preset.get("ok", "not_reported"),
        "inputs": preset.get("inputs", {}) if isinstance(preset.get("inputs"), dict) else {},
        "errors": preset.get("errors", []) if isinstance(preset.get("errors"), list) else [],
        "required_inputs": {
            "InpUseDailyLossStop": "true for forward/optimization",
            "InpDailyLossLimit": "> 0",
            "InpUseConsecutiveLossStop": "true for forward/optimization",
            "InpConsecutiveLossLimit": ">= 20",
            "InpConsecutiveLossCooldownMinutes": ">= 120",
            "InpRequireStrategyTester": "true",
            "InpChartButtonDryRunOnly": "true",
            "InpAllowChartButtonTrading": "false",
        },
        "note": "Fix or regenerate the referenced .set before rerun; --allow-invalid-risk-preset is diagnostic-only and must not be used for promotion evidence.",
    }


def mt5_forward_old_loss_limit_fix_plan(detected_limits: object) -> dict[str, object] | None:
    if not isinstance(detected_limits, list):
        return None
    old_limits: list[dict[str, object]] = []
    for item in detected_limits:
        if not isinstance(item, dict):
            continue
        limit = number(item.get("limit"))
        if limit <= 0 or limit >= 20:
            continue
        old_limits.append(
            {
                "limit": int(limit) if float(limit).is_integer() else limit,
                "count": item.get("count", 0),
            }
        )
    if not old_limits:
        return None
    set_file = "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_forward_test.set"
    preset = validate_tester_risk_preset(set_file, expert_parameters=Path(set_file).name)
    return {
        "kind": "mt5_risk_preset_fix",
        "command_text": (
            "manual: load "
            f"{set_file} in Strategy Tester and confirm "
            "InpUseConsecutiveLossStop=true, InpConsecutiveLossLimit>=20, "
            "InpConsecutiveLossCooldownMinutes>=120, InpRequireStrategyTester=true, "
            "InpChartButtonDryRunOnly=true, "
            "InpAllowChartButtonTrading=false"
        ),
        "set_file": set_file,
        "mode": "forward_or_optimization",
        "ok": preset.get("ok", "not_reported"),
        "inputs": preset.get("inputs", {}) if isinstance(preset.get("inputs"), dict) else {},
        "errors": preset.get("errors", []) if isinstance(preset.get("errors"), list) else [],
        "detected_consecutive_loss_limits": old_limits,
        "required_inputs": {
            "InpUseDailyLossStop": "true for forward/optimization",
            "InpDailyLossLimit": "> 0",
            "InpUseConsecutiveLossStop": "true for forward/optimization",
            "InpConsecutiveLossLimit": ">= 20",
            "InpConsecutiveLossCooldownMinutes": ">= 120",
            "InpRequireStrategyTester": "true",
            "InpChartButtonDryRunOnly": "true",
            "InpAllowChartButtonTrading": "false",
        },
        "note": "Forward CSV shows an older consecutive-loss limit; rerun Strategy Tester only after loading the current forward_test.set.",
    }


def mt5_forward_button_safety_fix_plan(button: object) -> dict[str, object]:
    set_file = "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_forward_test.set"
    preset = validate_tester_risk_preset(set_file, expert_parameters=Path(set_file).name)
    return {
        "kind": "mt5_risk_preset_fix",
        "command_text": (
            "manual: load "
            f"{set_file} in Strategy Tester and confirm "
            "InpRequireStrategyTester=true, InpChartButtonDryRunOnly=true, "
            "and InpAllowChartButtonTrading=false before rerunning MT5 Forward"
        ),
        "set_file": set_file,
        "mode": "forward_or_optimization",
        "ok": preset.get("ok", "not_reported"),
        "inputs": preset.get("inputs", {}) if isinstance(preset.get("inputs"), dict) else {},
        "errors": preset.get("errors", []) if isinstance(preset.get("errors"), list) else [],
        "button": compact_mt5_forward_button(button),
        "required_inputs": {
            "InpRequireStrategyTester": "true",
            "InpChartButtonDryRunOnly": "true",
            "InpAllowChartButtonTrading": "false",
        },
        "note": "Forward CSV contains unsafe chart-button rows; promotion evidence must use dry-run-only buttons or no button orders.",
    }


def command_text(command: list[object]) -> str:
    return shlex.join(str(part) for part in command)


def mt5_optimization_report_refresh_execution_plan(
    *,
    kind: str = "mt5_optimization_report_refresh",
    expected_from_date: str = "2026.06.30",
    expected_to_date: str = "2026.07.08",
    report_stem: str = "Swing_Evaluation_Trader_next_optimization",
    optimization_json: str = "runtime/latest_mt5_optimization_report.json",
    optimization_md: str = "runtime/latest_mt5_optimization_report.md",
    recommendation_json: str = "runtime/latest_mt5_optimization_recommendation.json",
    recommendation_md: str = "runtime/latest_mt5_optimization_recommendation.md",
    output_set: str = "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set",
) -> dict[str, object]:
    set_path = "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set"
    set_estimate: dict[str, object] = {}
    if Path(set_path).exists():
        set_estimate = estimate_set_passes(Path(set_path).read_text(encoding="utf-8"))
    tester_xml = default_tester_root() / f"{report_stem}.xml"
    tester_forward_xml = default_tester_root() / f"{report_stem}.forward.xml"
    report_command = [
        "python3",
        "methods/swing_eval/analysis/mt5_tester_optimization_report.py",
        "--since-minutes",
        "240",
        "--min-closed",
        "100",
        "--weak-pf",
        "1.0",
        "--set-file",
        set_path,
        "--tester-xml",
        str(tester_xml),
        "--tester-forward-xml",
        str(tester_forward_xml),
        "--expected-from-date",
        expected_from_date,
        "--expected-to-date",
        expected_to_date,
        "--fail-on-source-time-mismatch",
        "--drop-source-time-mismatch-files",
        "--output-json",
        optimization_json,
        "--output-md",
        optimization_md,
    ]
    recommend_command = [
        "python3",
        "methods/swing_eval/analysis/mt5_optimization_recommend.py",
        "--input",
        optimization_json,
        "--min-segment-closed",
        "500",
        "--min-segment-pf",
        "1.2",
        "--output-json",
        recommendation_json,
        "--output-md",
        recommendation_md,
        "--output-set",
        output_set,
    ]
    recommendation_only = kind == "mt5_optimization_recommendation_refresh"
    command = recommend_command if recommendation_only else report_command
    plan: dict[str, object] = {
        "kind": kind,
        "optimization_mode": "recommendation_from_existing_report" if recommendation_only else "collect",
        "set": set_path,
        "tester_xml": str(tester_xml),
        "tester_forward_xml": str(tester_forward_xml),
        "command": command,
        "command_text": command_text(command),
        "outputs": {
            "optimization_json": optimization_json,
            "optimization_md": optimization_md,
            "recommendation_json": recommendation_json,
            "recommendation_md": recommendation_md,
            "output_set": output_set,
        },
    }
    if recommendation_only:
        plan["input_optimization_json"] = optimization_json
        plan["note"] = (
            "Refreshes recommendation from the existing Optimization report; do not recollect Agent CSV after "
            "a Strategy Test run because the latest Agent CSV may be forward-test evidence, not optimization evidence."
        )
    else:
        plan["follow_up_command"] = recommend_command
        plan["follow_up_command_text"] = command_text(recommend_command)
    if set_estimate:
        plan["optimized_input_count"] = set_estimate.get("optimized_input_count")
        plan["estimated_full_factorial_passes"] = set_estimate.get("estimated_full_factorial_passes")
        plan["optimized_inputs"] = set_estimate.get("optimized_inputs")
    return plan


def mt5_stable_candidate_set_execution_plan(*, focus_side: str = "auto") -> dict[str, object]:
    output_set = "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_stable_candidate_next.set"
    recommendation_json = "runtime/latest_mt5_stable_candidate_recommendation.json"
    recommendation_md = "runtime/latest_mt5_stable_candidate_recommendation.md"
    command = [
        "python3",
        "methods/swing_eval/analysis/mt5_optimization_recommend.py",
        "--input",
        "runtime/latest_mt5_optimization_report.json",
        "--min-segment-closed",
        "500",
        "--min-segment-pf",
        "1.2",
        "--output-json",
        recommendation_json,
        "--output-md",
        recommendation_md,
        "--output-set",
        output_set,
        "--allow-non-adoptable-output-set",
    ]
    if focus_side in {"buy", "sell", "both"}:
        command.extend(["--focus-side", focus_side])
    return {
        "kind": "mt5_stable_candidate_set",
        "focus_side": focus_side,
        "optimization_mode": "stable_candidate_from_existing_report",
        "set": output_set,
        "template_set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_optimization.set",
        "command": command,
        "command_text": command_text(command),
        "outputs": {
            "recommendation_json": recommendation_json,
            "recommendation_md": recommendation_md,
            "output_set": output_set,
        },
        "note": (
            "Writes a separate exploratory stable-candidate set for MT5 validation. "
            "This is not a promoted next_optimization set."
        ),
    }


def mt5_yearly_optimization_report_refresh_execution_plan() -> dict[str, object]:
    return mt5_optimization_report_refresh_execution_plan(
        kind="mt5_yearly_optimization_report_refresh",
        expected_from_date="2025.01.01",
        expected_to_date="2025.12.31",
        report_stem="Swing_Evaluation_Trader_next_optimization_2025",
        optimization_json="runtime/latest_mt5_2025_optimization_report.json",
        optimization_md="runtime/latest_mt5_2025_optimization_report.md",
        recommendation_json="runtime/latest_mt5_2025_recommendation.json",
        recommendation_md="runtime/latest_mt5_2025_recommendation.md",
        output_set="runtime/Swing_Evaluation_Trader_2025_next.set",
    )


MT5_YEARLY_REFRESH_CHECK_NAMES = {
    "mt5_yearly_optimization_source_time_range",
    "mt5_yearly_optimization_chronological_splits",
    "mt5_yearly_optimization_time_regime_diagnostics",
    "mt5_yearly_optimization_trend_regime_diagnostics",
    "mt5_yearly_optimization_pass_budget",
    "mt5_yearly_optimization_executed_tester_xml_rows",
}


def safe_artifact_suffix(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value)
    return safe.strip("_") or "preview"


def mt5_agent_csv_archive_preview_output_paths(run_id: str) -> tuple[str, str]:
    suffix = safe_artifact_suffix(run_id)
    return (
        f"runtime/latest_mt5_agent_csv_archive_{suffix}.json",
        f"runtime/latest_mt5_agent_csv_archive_{suffix}.md",
    )


def mt5_agent_csv_archive_preview_execution_plan(*, run_id: str) -> dict[str, object]:
    output_json, output_md = mt5_agent_csv_archive_preview_output_paths(run_id)
    return mt5_agent_csv_archive_execution_plan(
        execute=False,
        run_id=run_id,
        include_source_time=True,
        output_json=output_json,
        output_md=output_md,
    )


def mt5_yearly_collect_refresh_required(failures: dict[str, dict[str, object]]) -> bool:
    return any(name in MT5_YEARLY_REFRESH_CHECK_NAMES for name in failures)


def mt5_agent_csv_archive_execution_plan(
    *,
    execute: bool,
    run_id: str | None = None,
    include_source_time: bool = False,
    output_json: str | None = None,
    output_md: str | None = None,
) -> dict[str, object]:
    output_json = output_json or "runtime/latest_mt5_agent_csv_archive.json"
    output_md = output_md or "runtime/latest_mt5_agent_csv_archive.md"
    command = [
        "python3",
        "methods/swing_eval/analysis/mt5_agent_csv_archive.py",
        "--output-json",
        output_json,
        "--output-md",
        output_md,
    ]
    if run_id:
        command.extend(["--run-id", run_id])
    if include_source_time:
        command.append("--include-source-time")
    if execute:
        command.append("--execute")
    return {
        "kind": "mt5_agent_csv_archive",
        "execute": execute,
        "run_id": run_id or "",
        "include_source_time": include_source_time,
        "command": command,
        "command_text": command_text(command),
        "outputs": {
            "json": output_json,
            "md": output_md,
            "archive_root": "runtime/mt5_agent_csv_archive",
        },
    }


def mt5_yearly_validation_execution_plan(
    *,
    focus_side: str,
    archive_run_id: str | None = None,
) -> dict[str, object]:
    archive_run_id = archive_run_id or promotion_archive_run_id(
        {},
        "mt5_yearly_validation",
        "next_optimization_2025",
        focus_side,
    )
    set_path = "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set"
    set_estimate: dict[str, object] = {}
    if Path(set_path).exists():
        set_estimate = estimate_set_passes(Path(set_path).read_text(encoding="utf-8"))
    timeout_seconds = 10800
    command = [
        "python3",
        "methods/swing_eval/analysis/mt5_tester_run.py",
        "--config",
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_next_optimization.ini",
        "--report-name",
        r"Tester\Swing_Evaluation_Trader_next_optimization_2025",
        "--from-date",
        "2025.01.01",
        "--to-date",
        "2025.12.31",
        "--forward-mode",
        "3",
        "--timeout-seconds",
        str(timeout_seconds),
        "--since-minutes",
        "240",
        "--archive-agent-csvs-before-run",
        "--agent-csv-archive-run-id",
        archive_run_id,
        "--sync-expert-parameters-set",
        "--min-closed",
        "100",
        "--min-segment-closed",
        "500",
        "--min-segment-pf",
        "1.2",
        "--focus-side",
        focus_side,
        "--output-json",
        "runtime/latest_mt5_tester_2025_run.json",
        "--output-md",
        "runtime/latest_mt5_tester_2025_run.md",
        "--optimization-output-json",
        "runtime/latest_mt5_2025_optimization_report.json",
        "--optimization-output-md",
        "runtime/latest_mt5_2025_optimization_report.md",
        "--recommendation-output-json",
        "runtime/latest_mt5_2025_recommendation.json",
        "--recommendation-output-md",
        "runtime/latest_mt5_2025_recommendation.md",
        "--output-set",
        "runtime/Swing_Evaluation_Trader_2025_next.set",
    ]
    plan: dict[str, object] = {
        "kind": "mt5_yearly_validation",
        "focus_side": focus_side,
        "optimization_mode": "genetic",
        "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_next_optimization.ini",
        "set": set_path,
        "report_name": r"Tester\Swing_Evaluation_Trader_next_optimization_2025",
        "agent_csv_archive_run_id": archive_run_id,
        "command": command,
        "command_text": command_text(command),
        "outputs": {
            "run_json": "runtime/latest_mt5_tester_2025_run.json",
            "run_md": "runtime/latest_mt5_tester_2025_run.md",
            "optimization_json": "runtime/latest_mt5_2025_optimization_report.json",
            "optimization_md": "runtime/latest_mt5_2025_optimization_report.md",
            "recommendation_json": "runtime/latest_mt5_2025_recommendation.json",
            "recommendation_md": "runtime/latest_mt5_2025_recommendation.md",
            "output_set": "runtime/Swing_Evaluation_Trader_2025_next.set",
        },
    }
    attach_execution_timeout(
        plan,
        timeout_seconds,
        note="Maximum terminal runtime for yearly/out-of-year validation; MT5 may finish earlier under genetic optimization.",
    )
    if set_estimate:
        plan["optimized_input_count"] = set_estimate.get("optimized_input_count")
        plan["estimated_full_factorial_passes"] = set_estimate.get("estimated_full_factorial_passes")
        plan["optimized_inputs"] = set_estimate.get("optimized_inputs")
    return plan


def attach_execution_timeout(plan: dict[str, object], timeout_seconds: int, *, note: str) -> None:
    plan["timeout_seconds"] = timeout_seconds
    plan["timeout_minutes"] = round(timeout_seconds / 60.0, 2)
    plan["timeout_note"] = note


def mt5_optimization_focus_side(summary: dict[str, object]) -> str:
    rows = summary.get("by_action") if isinstance(summary, dict) else None
    if not isinstance(rows, list):
        return "both"
    sides = [
        str(row.get("group"))
        for row in rows
        if isinstance(row, dict) and str(row.get("group")) in {"buy", "sell"} and number(row.get("closed")) > 0
    ]
    unique = sorted(set(sides))
    if len(unique) == 1:
        return unique[0]
    return "both"


def winrate_fit_execution_plan() -> dict[str, object]:
    command = [
        "python3",
        "methods/swing_eval/analysis/winrate_fit.py",
        "--history",
        "runtime/latest_history_168h.json",
        "--output",
        "reports/winrate_fit.xlsx",
        "--output-json",
        "runtime/latest_winrate_fit.json",
        "--rr",
        "4",
        "--side",
        "both",
        "--min-score",
        "50",
        "--purge-records",
        "5",
        "--embargo-minutes",
        "60",
        "--min-count",
        "20",
        "--min-test-count",
        "5",
        "--min-test-avg-r",
        "0.0",
        "--min-test-pf",
        "1.0",
        "--validation-folds",
        "3",
        "--wf-folds",
        "4",
        "--wf-train-window",
        "40",
        "--wf-test-window",
        "12",
        "--calendar",
        "runtime/economic_calendar.json",
        "--calendar-input-utc-offset",
        "9",
        "--calendar-server-utc-offset",
        "3",
    ]
    return {
        "kind": "winrate_fit_walk_forward",
        "command": command,
        "command_text": command_text(command),
        "outputs": {
            "fit_xlsx": "reports/winrate_fit.xlsx",
            "fit_json": "runtime/latest_winrate_fit.json",
        },
    }


def dry_run_refresh_execution_plan() -> dict[str, object]:
    command = [
        "python3",
        "methods/swing_eval/analysis/dry_run_command.py",
        "--signal",
        "runtime/latest_signal.json",
        "--output",
        "runtime/trade_command.json",
        "--volume",
        "0.1",
        "--expires-in-seconds",
        "30",
        "--account",
        "runtime/latest_account.json",
        "--deal-history",
        "runtime/latest_deal_history.json",
        "--calendar",
        "runtime/economic_calendar.json",
        "--calendar-input-utc-offset",
        "9",
        "--calendar-server-utc-offset",
        "3",
        "--max-open-positions",
        "3",
        "--max-total-volume",
        "0.3",
        "--daily-loss-limit",
        "5000",
        "--consecutive-loss-limit",
        "20",
        "--consecutive-loss-cooldown-minutes",
        "120",
        "--replace",
        "--write-rejections",
    ]
    audit_command = [
        "python3",
        "methods/swing_eval/analysis/dry_run_audit.py",
        "--signal",
        "runtime/latest_signal.json",
        "--command",
        "runtime/trade_command.json",
        "--trade-result",
        "runtime/latest_trade_result.json",
        "--max-age-seconds",
        "3600",
        "--output-json",
        "runtime/latest_dry_run_audit.json",
        "--output-md",
        "runtime/latest_dry_run_audit.md",
    ]
    return {
        "kind": "dry_run_refresh",
        "command": command,
        "command_text": command_text(command),
        "follow_up_command": audit_command,
        "follow_up_command_text": command_text(audit_command),
        "outputs": {
            "command_json": "runtime/trade_command.json",
            "audit_json": "runtime/latest_dry_run_audit.json",
            "audit_md": "runtime/latest_dry_run_audit.md",
        },
    }


def python_forward_execution_plan() -> dict[str, object]:
    command = [
        "python3",
        "methods/swing_eval/analysis/forward_test_watch.py",
        "--signal",
        "runtime/latest_signal.json",
        "--ledger",
        "runtime/forward_tests.jsonl",
        "--history",
        "runtime/latest_history_168h.json",
        "--summary-json",
        "runtime/latest_forward_test.json",
        "--summary-md",
        "runtime/latest_forward_test.md",
        "--status-json",
        "runtime/latest_forward_test_status.json",
        "--status-md",
        "runtime/latest_forward_test_status.md",
        "--heartbeat",
        "runtime/forward_test_watch_heartbeat.json",
        "--max-hold-minutes",
        "60",
        "--interval-seconds",
        "60",
        "--max-runs",
        "1",
    ]
    return {
        "kind": "python_forward_watch",
        "command": command,
        "command_text": command_text(command),
        "outputs": {
            "ledger": "runtime/forward_tests.jsonl",
            "summary_json": "runtime/latest_forward_test.json",
            "summary_md": "runtime/latest_forward_test.md",
            "status_json": "runtime/latest_forward_test_status.json",
            "status_md": "runtime/latest_forward_test_status.md",
            "heartbeat": "runtime/forward_test_watch_heartbeat.json",
        },
    }


def score_calibration_execution_plan() -> dict[str, object]:
    command = [
        "python3",
        "methods/swing_eval/analysis/backtest.py",
        "--history",
        "runtime/latest_history_168h.json",
        "--rr",
        "4",
        "--min-score",
        "40",
        "--max-hold-minutes",
        "60",
        "--calendar",
        "runtime/economic_calendar.json",
        "--calendar-input-utc-offset",
        "9",
        "--calendar-server-utc-offset",
        "3",
        "--output",
        "reports/signal_score_backtest_168h_min40.xlsx",
    ]
    fit_command = [
        "python3",
        "methods/swing_eval/analysis/weight_search.py",
        "--history",
        "runtime/latest_history_168h.json",
        "--rr",
        "4",
        "--side",
        "both",
        "--min-count",
        "20",
        "--max-hold-minutes",
        "60",
        "--calendar",
        "runtime/economic_calendar.json",
        "--calendar-input-utc-offset",
        "9",
        "--calendar-server-utc-offset",
        "3",
        "--output",
        "reports/score_weight_search_168h_both_rr4.xlsx",
        "--output-json",
        "runtime/latest_score_weight_search.json",
        "--output-md",
        "runtime/latest_score_weight_search.md",
        "--walk-forward",
        "--wf-folds",
        "4",
        "--wf-train-window",
        "240",
        "--wf-test-window",
        "60",
        "--wf-embargo-records",
        "5",
        "--regime-search",
        "entry_hour,m30_m15_trend,m30_trend,m15_trend,htf_alignment",
        "--regime-min-count",
        "20",
        "--regime-top-per-group",
        "1",
    ]
    return {
        "kind": "score_calibration",
        "command": command,
        "command_text": command_text(command),
        "follow_up_command": fit_command,
        "follow_up_command_text": command_text(fit_command),
        "outputs": {
            "backtest_xlsx": "reports/signal_score_backtest_168h_min40.xlsx",
            "weight_search_xlsx": "reports/score_weight_search_168h_both_rr4.xlsx",
            "weight_search_json": "runtime/latest_score_weight_search.json",
            "weight_search_md": "runtime/latest_score_weight_search.md",
        },
    }


def score_weight_search_execution_plan(side: str) -> dict[str, object]:
    focus_side = side if side in {"buy", "sell", "both"} else "both"
    output_stem = f"score_weight_search_168h_{focus_side}_rr4"
    command = [
        "python3",
        "methods/swing_eval/analysis/weight_search.py",
        "--history",
        "runtime/latest_history_168h.json",
        "--rr",
        "4",
        "--side",
        focus_side,
        "--min-count",
        "20",
        "--max-hold-minutes",
        "60",
        "--calendar",
        "runtime/economic_calendar.json",
        "--calendar-input-utc-offset",
        "9",
        "--calendar-server-utc-offset",
        "3",
        "--output",
        f"reports/{output_stem}.xlsx",
        "--output-json",
        f"runtime/latest_{output_stem}.json",
        "--output-md",
        f"runtime/latest_{output_stem}.md",
        "--walk-forward",
        "--wf-folds",
        "4",
        "--wf-train-window",
        "240",
        "--wf-test-window",
        "60",
        "--wf-embargo-records",
        "5",
        "--regime-search",
        "entry_hour,m30_m15_trend,m30_trend,m15_trend,htf_alignment",
        "--regime-min-count",
        "20",
        "--regime-top-per-group",
        "1",
    ]
    return {
        "kind": "score_weight_search",
        "focus_side": focus_side,
        "mode": "side_specific",
        "command": command,
        "command_text": command_text(command),
        "outputs": {
            "weight_search_xlsx": f"reports/{output_stem}.xlsx",
            "weight_search_json": f"runtime/latest_{output_stem}.json",
            "weight_search_md": f"runtime/latest_{output_stem}.md",
        },
        "note": "Side-specific score weight search is diagnostic only; validate with MT5 optimization and yearly checks before applying weights.",
    }


def score_weight_set_execution_plan(side: str) -> dict[str, object]:
    focus_side = side if side in {"buy", "sell", "both"} else "both"
    input_stem = f"score_weight_search_168h_{focus_side}_rr4"
    output_stem = f"score_weight_set_168h_{focus_side}_rr4"
    if focus_side == "sell":
        template_set = "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sell_regime_entry_refit.set"
        output_set = "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sell_score_weight_refit.set"
    elif focus_side == "buy":
        template_set = "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_refit.set"
        output_set = "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_score_weight_refit.set"
    else:
        template_set = "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_optimization.set"
        output_set = "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_score_weight_refit.set"
    command = [
        "python3",
        "methods/swing_eval/analysis/score_weight_set.py",
        "--weight-search-json",
        f"runtime/latest_{input_stem}.json",
        "--template-set",
        template_set,
        "--output-set",
        output_set,
        "--side",
        focus_side,
        "--output-json",
        f"runtime/latest_{output_stem}.json",
        "--output-md",
        f"runtime/latest_{output_stem}.md",
    ]
    return {
        "kind": "score_weight_set",
        "focus_side": focus_side,
        "mode": "mt5_validation_set_from_weight_search",
        "set": output_set,
        "template_set": template_set,
        "command": command,
        "command_text": command_text(command),
        "outputs": {
            "output_set": output_set,
            "json": f"runtime/latest_{output_stem}.json",
            "md": f"runtime/latest_{output_stem}.md",
        },
        "note": (
            "Writes the MT5 validation .set only when weight_search walk-forward status is "
            "walk_forward_candidate_passed. Failed candidates remain diagnostic and must not be sent to MT5 as adoption evidence."
        ),
    }


def score_weight_history_check_execution_plan() -> dict[str, object]:
    command = [
        "python3",
        "methods/swing_eval/analysis/history_status.py",
        "--history",
        "runtime/latest_history_168h.json",
        "--done",
        "runtime/history_request.done.json",
        "--output-json",
        "runtime/latest_history_status.json",
        "--output-md",
        "runtime/latest_history_status.md",
    ]
    return {
        "kind": "score_weight_history_check",
        "command": command,
        "command_text": command_text(command),
        "outputs": {
            "json": "runtime/latest_history_status.json",
            "md": "runtime/latest_history_status.md",
        },
        "note": "Check whether the 168h MT5 history snapshot is complete before collecting more score-refit samples.",
    }


def score_weight_sample_collection_execution_plan(
    *,
    focus_side: str,
    archive_run_id: str | None = None,
) -> dict[str, object]:
    normalized_focus_side = focus_side if focus_side in {"buy", "sell", "both"} else "both"
    archive_run_id = archive_run_id or promotion_archive_run_id(
        {},
        "score_weight_sample_collection",
        "sample_collection",
        normalized_focus_side,
    )
    timeout_seconds = 7200
    report_name = f"Tester\\Swing_Evaluation_Trader_sample_collection_{normalized_focus_side}"
    run_json = f"runtime/latest_mt5_tester_sample_collection_{normalized_focus_side}_run.json"
    run_md = f"runtime/latest_mt5_tester_sample_collection_{normalized_focus_side}_run.md"
    optimization_json = f"runtime/latest_mt5_sample_collection_{normalized_focus_side}_report.json"
    optimization_md = f"runtime/latest_mt5_sample_collection_{normalized_focus_side}_report.md"
    command = [
        "python3",
        "methods/swing_eval/analysis/mt5_tester_run.py",
        "--config",
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sample_collection.ini",
        "--report-name",
        report_name,
        "--timeout-seconds",
        str(timeout_seconds),
        "--since-minutes",
        "240",
        "--archive-agent-csvs-before-run",
        "--agent-csv-archive-run-id",
        archive_run_id,
        "--sync-expert-parameters-set",
        "--min-closed",
        "100",
        "--focus-side",
        normalized_focus_side,
        "--no-recommendation",
        "--output-json",
        run_json,
        "--output-md",
        run_md,
        "--optimization-output-json",
        optimization_json,
        "--optimization-output-md",
        optimization_md,
    ]
    plan: dict[str, object] = {
        "kind": "score_weight_sample_collection",
        "focus_side": normalized_focus_side,
        "optimization_mode": "single",
        "config": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sample_collection.ini",
        "set": "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sample_collection.set",
        "report_name": report_name,
        "agent_csv_archive_run_id": archive_run_id,
        "outputs": {
            "run_json": run_json,
            "run_md": run_md,
            "optimization_json": optimization_json,
            "optimization_md": optimization_md,
        },
        "command": command,
        "command_text": command_text(command),
        "note": (
            "Diagnostic sample collection only. It uses sample_collection.set with tester safety stops disabled "
            "to avoid early cooldown, and must not be treated as forward/live promotion evidence."
        ),
    }
    attach_execution_timeout(
        plan,
        timeout_seconds,
        note="Maximum terminal runtime for diagnostic sample collection; this is not promotion evidence.",
    )
    if Path(str(plan["set"])).exists():
        estimate = estimate_set_passes(Path(str(plan["set"])).read_text(encoding="utf-8"))
        if estimate:
            plan["optimized_input_count"] = estimate.get("optimized_input_count")
            plan["estimated_full_factorial_passes"] = estimate.get("estimated_full_factorial_passes")
            plan["optimized_inputs"] = estimate.get("optimized_inputs")
    return plan


def risk_shape_execution_plan() -> dict[str, object]:
    command = [
        "python3",
        "methods/swing_eval/analysis/backtest.py",
        "--history",
        "runtime/latest_history_168h.json",
        "--rr",
        "4",
        "--min-score",
        "40",
        "--max-hold-minutes",
        "60",
        "--calendar",
        "runtime/economic_calendar.json",
        "--calendar-input-utc-offset",
        "9",
        "--calendar-server-utc-offset",
        "3",
        "--output",
        "reports/risk_shape_backtest_168h_min40.xlsx",
    ]
    fit_command = [
        "python3",
        "methods/swing_eval/analysis/weight_search.py",
        "--history",
        "runtime/latest_history_168h.json",
        "--rr",
        "4",
        "--side",
        "both",
        "--min-count",
        "20",
        "--max-hold-minutes",
        "60",
        "--calendar",
        "runtime/economic_calendar.json",
        "--calendar-input-utc-offset",
        "9",
        "--calendar-server-utc-offset",
        "3",
        "--output",
        "reports/risk_shape_weight_search_168h_both_rr4.xlsx",
        "--output-json",
        "runtime/latest_risk_shape_weight_search.json",
        "--output-md",
        "runtime/latest_risk_shape_weight_search.md",
        "--walk-forward",
        "--wf-folds",
        "4",
        "--wf-train-window",
        "240",
        "--wf-test-window",
        "60",
        "--wf-embargo-records",
        "5",
    ]
    return {
        "kind": "risk_shape_refit",
        "command": command,
        "command_text": command_text(command),
        "follow_up_command": fit_command,
        "follow_up_command_text": command_text(fit_command),
        "note": "Use the outputs to reduce drawdown concentration or refit expectancy before re-running promotion.",
        "outputs": {
            "backtest_xlsx": "reports/risk_shape_backtest_168h_min40.xlsx",
            "weight_search_xlsx": "reports/risk_shape_weight_search_168h_both_rr4.xlsx",
            "weight_search_json": "runtime/latest_risk_shape_weight_search.json",
            "weight_search_md": "runtime/latest_risk_shape_weight_search.md",
        },
    }


def backtest_sample_execution_plan() -> dict[str, object]:
    command = ["python3", "src/bridge/request_history.py", "168"]
    status_command = [
        "python3",
        "methods/swing_eval/analysis/history_status.py",
        "--history",
        "runtime/latest_history_168h.json",
        "--done",
        "runtime/history_request.done.json",
        "--output-json",
        "runtime/latest_history_status.json",
        "--output-md",
        "runtime/latest_history_status.md",
    ]
    backtest_command = [
        "python3",
        "methods/swing_eval/analysis/backtest.py",
        "--history",
        "runtime/latest_history_168h.json",
        "--rr",
        "4",
        "--min-score",
        "40",
        "--max-hold-minutes",
        "60",
        "--calendar",
        "runtime/economic_calendar.json",
        "--calendar-input-utc-offset",
        "9",
        "--calendar-server-utc-offset",
        "3",
        "--output",
        "reports/signal_score_backtest_168h_min40.xlsx",
    ]
    return {
        "kind": "backtest_sample_refresh",
        "command": command,
        "command_text": command_text(command),
        "status_command": status_command,
        "status_command_text": command_text(status_command),
        "follow_up_command": backtest_command,
        "follow_up_command_text": command_text(backtest_command),
        "note": "Wait for the next MT5 EA history post, verify latest_history_status, then run the follow-up backtest.",
        "outputs": {
            "history_request": "runtime/history_request.json",
            "history_done": "runtime/history_request.done.json",
            "history_status_json": "runtime/latest_history_status.json",
            "history_status_md": "runtime/latest_history_status.md",
            "backtest_xlsx": "reports/signal_score_backtest_168h_min40.xlsx",
        },
    }


def compact_segments(rows: object, *, limit: int) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        return []
    compacted: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        compacted.append(
            {
                "group": row.get("group"),
                "start_time": row.get("start_time"),
                "end_time": row.get("end_time"),
                "closed": row.get("closed"),
                "pf": row.get("pf"),
                "avg_price_r": row.get("avg_price_r"),
                "net_profit": row.get("net_profit"),
                "tp_rate": row.get("tp_rate"),
                "sl_rate": row.get("sl_rate"),
                "early_loss_rate": row.get("early_loss_rate"),
                "diagnosis": row.get("diagnosis", ""),
            }
        )
        if len(compacted) >= limit:
            break
    return compacted


def compact_text_count_rows(rows: object, *, limit: int) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        return []
    compacted: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        compacted.append({"text": text, "count": row.get("count")})
        if len(compacted) >= limit:
            break
    return compacted


def compact_mt5_forward_signal(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {
        "rows": value.get("rows"),
        "buy": value.get("buy"),
        "sell": value.get("sell"),
        "hold": value.get("hold"),
        "tradable": value.get("tradable"),
        "other": value.get("other"),
        "avg_score": value.get("avg_score"),
        "avg_buy_score": value.get("avg_buy_score"),
        "avg_sell_score": value.get("avg_sell_score"),
        "top_reasons": compact_text_count_rows(value.get("top_reasons"), limit=3),
    }


def compact_mt5_forward_reject(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {
        "rows": value.get("rows"),
        "buy": value.get("buy"),
        "sell": value.get("sell"),
        "hold_or_other": value.get("hold_or_other"),
        "top_messages": compact_text_count_rows(value.get("top_messages"), limit=3),
        "detected_consecutive_loss_limits": value.get("detected_consecutive_loss_limits"),
    }


def compact_mt5_forward_button(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    keys = (
        "rows",
        "dry_runs",
        "ignored",
        "unsafe",
        "buy_clicks",
        "sell_clicks",
        "hold_or_other_clicks",
    )
    return {key: value.get(key) for key in keys if value.get(key) is not None}


def compact_mt5_forward_risk_exposure(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    keys = (
        "max_single_volume",
        "max_single_volume_limit",
        "max_concurrent_volume",
        "max_total_volume_limit",
        "max_concurrent_positions",
        "max_positions_limit",
        "open_positions_at_end",
        "open_volume_at_end",
        "daily_loss_stop_rejections",
        "consecutive_loss_stop_rejections",
        "lot_limit_rejections",
    )
    return {key: value.get(key) for key in keys if value.get(key) is not None}


def compact_mt5_forward_sl_tp_diagnostics(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    sources = (
        ("sl", "by_stop_points"),
        ("tp", "by_take_profit_points"),
        ("rr_sl", "by_risk_reward_stop_points"),
        ("rr_tp", "by_risk_reward_take_profit_points"),
        ("weak", "weak_sl_tp_segments"),
    )
    diagnostics: dict[str, object] = {}
    missing: list[str] = []
    for label, key in sources:
        rows = value.get(key)
        if isinstance(rows, list):
            diagnostics[label] = len(rows)
        else:
            missing.append(key)
    if missing:
        diagnostics["missing"] = missing
    diagnostics["weak_segments"] = compact_segments(value.get("weak_sl_tp_segments"), limit=4)
    return diagnostics


def segment_group_side(row: dict[str, object]) -> str | None:
    group = str(row.get("group") or "").strip().lower()
    for side in ("buy", "sell"):
        if group == side or group.startswith(f"{side} "):
            return side
    return None


def compact_segments_for_side(rows: object, *, side: str, limit: int) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        return []
    side_key = side.strip().lower()
    return compact_segments(
        [row for row in rows if isinstance(row, dict) and segment_group_side(row) == side_key],
        limit=limit,
    )


def segment_side_counts(rows: object) -> dict[str, int]:
    if not isinstance(rows, list):
        return {}
    counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        side = segment_group_side(row) or "unknown"
        counts[side] = counts.get(side, 0) + 1
    return counts


def compact_thresholds(rows: object, *, limit: int = 8) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        return []
    compacted: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        compacted.append(compact_threshold_row(row))
        if len(compacted) >= limit:
            break
    return compacted


def compact_threshold_row(row: object) -> dict[str, object]:
    if not isinstance(row, dict):
        return {}
    return {
        "threshold": row.get("threshold"),
        "count": row.get("count"),
        "avg_r": row.get("avg_r"),
        "pf": row.get("pf"),
        "total_r": row.get("total_r"),
    }


def compact_score_weight_search(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    top = value.get("top_weight_candidate")
    diagnostics = value.get("diagnostics")
    if not isinstance(diagnostics, dict):
        diagnostics = score_weight_search_diagnostics(value)
    return {
        "generated_at": value.get("generated_at", ""),
        "candidate_count": value.get("candidate_count", 0),
        "result_count": value.get("result_count", 0),
        "search_row_count": value.get("search_row_count", 0),
        "top_weight_candidate": compact_score_weight_candidate(top),
        "diagnostics": compact_score_weight_diagnostics(diagnostics),
        "walk_forward": compact_score_weight_walk_forward(value.get("walk_forward")),
        "regime_search": compact_score_weight_regime_search(value.get("regime_search")),
    }


def compact_score_weight_set_result(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    follow_up = value.get("follow_up") if isinstance(value.get("follow_up"), dict) else {}
    return {
        "generated_at": value.get("generated_at", ""),
        "source_generated_at": value.get("source_generated_at", ""),
        "focus_side": value.get("focus_side", ""),
        "can_write": value.get("can_write"),
        "written": value.get("written"),
        "skipped_write": value.get("skipped_write"),
        "skip_reason": value.get("skip_reason", ""),
        "allow_failed_walk_forward": value.get("allow_failed_walk_forward"),
        "walk_forward_status": value.get("walk_forward_status", ""),
        "output_set": value.get("output_set", ""),
        "template_set": value.get("template_set", ""),
        "top_weight_candidate": compact_score_weight_candidate(value.get("top_weight_candidate")),
        "follow_up": follow_up,
    }


def compact_score_weight_candidate(row: object) -> dict[str, object]:
    if not isinstance(row, dict):
        return {}
    return {
        "side": row.get("side"),
        "threshold": row.get("threshold"),
        "weights": row.get("weights"),
        "count": row.get("count"),
        "win_rate": row.get("win_rate"),
        "avg_r": row.get("avg_r"),
        "pf": row.get("pf"),
        "total_r": row.get("total_r"),
        "max_losing_streak": row.get("max_losing_streak"),
        "max_drawdown_r": row.get("max_drawdown_r"),
    }


def compact_score_weight_baseline(row: object) -> dict[str, object]:
    if not isinstance(row, dict):
        return {}
    return {
        "threshold": row.get("threshold"),
        "count": row.get("count"),
        "win_rate": row.get("win_rate"),
        "avg_r": row.get("avg_r"),
        "pf": row.get("pf"),
        "total_r": row.get("total_r"),
        "max_losing_streak": row.get("max_losing_streak"),
        "max_drawdown_r": row.get("max_drawdown_r"),
    }


def compact_score_weight_diagnostics(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {
        "status": value.get("status"),
        "baseline": compact_score_weight_baseline(value.get("baseline")),
        "deltas": value.get("deltas") if isinstance(value.get("deltas"), dict) else {},
        "walk_forward": compact_score_weight_walk_forward(value.get("walk_forward")),
        "min_count": value.get("min_count"),
        "required_baseline_count": value.get("required_baseline_count"),
        "fallback_baseline_used": value.get("fallback_baseline_used"),
        "recommendation": value.get("recommendation", ""),
    }


def compact_score_weight_walk_forward(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    aggregate = value.get("aggregate") if isinstance(value.get("aggregate"), dict) else {}
    settings = value.get("settings") if isinstance(value.get("settings"), dict) else {}
    return {
        "enabled": value.get("enabled") is True,
        "settings": settings,
        "aggregate": {
            "status": aggregate.get("status"),
            "folds": aggregate.get("folds"),
            "folds_with_weight_trades": aggregate.get("folds_with_weight_trades"),
            "required_folds_with_weight_trades": aggregate.get("required_folds_with_weight_trades"),
            "total_test_weight_count": aggregate.get("total_test_weight_count"),
            "required_test_weight_count": aggregate.get("required_test_weight_count"),
            "missing_test_weight_count": aggregate.get("missing_test_weight_count"),
            "total_test_baseline_count": aggregate.get("total_test_baseline_count"),
            "missing_folds_with_weight_trades": aggregate.get("missing_folds_with_weight_trades"),
            "folds_without_weight_trades": aggregate.get("folds_without_weight_trades"),
            "min_test_weight_count": aggregate.get("min_test_weight_count"),
            "min_test_weight_fold": aggregate.get("min_test_weight_fold"),
            "total_test_weight_r": aggregate.get("total_test_weight_r"),
            "total_test_baseline_r": aggregate.get("total_test_baseline_r"),
            "mean_test_weight_avg_r": aggregate.get("mean_test_weight_avg_r"),
            "mean_test_baseline_avg_r": aggregate.get("mean_test_baseline_avg_r"),
            "mean_test_weight_pf": aggregate.get("mean_test_weight_pf"),
            "mean_test_baseline_pf": aggregate.get("mean_test_baseline_pf"),
            "delta_mean_avg_r": aggregate.get("delta_mean_avg_r"),
            "delta_mean_pf": aggregate.get("delta_mean_pf"),
            "delta_total_r": aggregate.get("delta_total_r"),
            "min_count": aggregate.get("min_count"),
            "recommendation": aggregate.get("recommendation"),
        },
    }


def compact_score_weight_regime_search(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {"enabled": False}
    best = value.get("best_regime_candidate")
    rows = value.get("rows")
    return {
        "enabled": value.get("enabled") is True,
        "row_count": value.get("row_count", 0),
        "skipped_group_count": value.get("skipped_group_count", 0),
        "best_regime_candidate": compact_score_weight_regime_row(best),
        "rows": [compact_score_weight_regime_row(row) for row in rows[:10]] if isinstance(rows, list) else [],
    }


def compact_score_weight_regime_row(row: object) -> dict[str, object]:
    if not isinstance(row, dict):
        return {}
    walk = row.get("walk_forward") if isinstance(row.get("walk_forward"), dict) else {}
    aggregate = walk.get("aggregate") if isinstance(walk.get("aggregate"), dict) else {}
    return {
        "dimension": row.get("dimension"),
        "group": row.get("group"),
        "threshold": row.get("threshold"),
        "weights": row.get("weights"),
        "count": row.get("count"),
        "avg_r": row.get("avg_r"),
        "pf": row.get("pf"),
        "total_r": row.get("total_r"),
        "max_drawdown_r": row.get("max_drawdown_r"),
        "wf_status": aggregate.get("status", row.get("wf_status")),
        "wf_weight_count": aggregate.get("total_test_weight_count", row.get("wf_weight_count")),
        "wf_required_weight_count": aggregate.get("required_test_weight_count", row.get("wf_required_weight_count")),
        "wf_missing_weight_count": aggregate.get("missing_test_weight_count", row.get("wf_missing_weight_count")),
        "wf_baseline_count": aggregate.get("total_test_baseline_count", row.get("wf_baseline_count")),
        "wf_folds_with_weight": aggregate.get("folds_with_weight_trades", row.get("wf_folds_with_weight")),
        "wf_required_folds_with_weight": aggregate.get(
            "required_folds_with_weight_trades",
            row.get("wf_required_folds_with_weight"),
        ),
        "wf_missing_folds_with_weight": aggregate.get(
            "missing_folds_with_weight_trades",
            row.get("wf_missing_folds_with_weight"),
        ),
        "wf_min_weight_count": aggregate.get("min_test_weight_count", row.get("wf_min_weight_count")),
        "wf_min_weight_fold": aggregate.get("min_test_weight_fold", row.get("wf_min_weight_fold")),
        "wf_mean_avg_r": aggregate.get("mean_test_weight_avg_r", row.get("wf_mean_avg_r")),
        "wf_baseline_avg_r": aggregate.get("mean_test_baseline_avg_r", row.get("wf_baseline_avg_r")),
        "wf_mean_pf": aggregate.get("mean_test_weight_pf", row.get("wf_mean_pf")),
        "wf_baseline_pf": aggregate.get("mean_test_baseline_pf", row.get("wf_baseline_pf")),
        "wf_delta_total_r": aggregate.get("delta_total_r", row.get("wf_delta_total_r")),
    }


def compact_side_score_diagnostics(rows: object, *, limit: int) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        return []
    compacted: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        compacted.append(
            {
                "side": row.get("side"),
                "status": row.get("status"),
                "base_pf": row.get("base_pf"),
                "best_pf_threshold": row.get("best_pf_threshold"),
                "best_pf": row.get("best_pf"),
                "high_threshold": row.get("high_threshold"),
                "high_pf": row.get("high_pf"),
                "recommendation": row.get("recommendation"),
            }
        )
        if len(compacted) >= limit:
            break
    return compacted


def append_segment_lines(
    lines: list[str],
    rows: object,
    *,
    limit: int,
    include_diagnosis: bool,
) -> None:
    if not isinstance(rows, list) or not rows:
        lines.append("- None")
        return
    appended = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        period = ""
        if row.get("start_time") or row.get("end_time"):
            period = f", period={row.get('start_time', '')}..{row.get('end_time', '')}"
        text = (
            f"- {row.get('group')}: closed={row.get('closed')}, pf={row.get('pf')}, "
            f"avg_price_r={row.get('avg_price_r')}, net_profit={row.get('net_profit')}, "
            f"tp_rate={row.get('tp_rate')}, sl_rate={row.get('sl_rate')}, "
            f"early_loss_rate={row.get('early_loss_rate')}{period}"
        )
        if include_diagnosis and row.get("diagnosis"):
            text += f", diagnosis={row.get('diagnosis')}"
        lines.append(text)
        appended += 1
        if appended >= limit:
            break
    if appended == 0:
        lines.append("- None")


def append_side_score_lines(lines: list[str], rows: object, *, limit: int) -> None:
    compacted = compact_side_score_diagnostics(rows, limit=limit)
    if not compacted:
        lines.append("- None")
        return
    for row in compacted:
        lines.append(
            f"- {row.get('side')}: status={row.get('status')}, base_pf={row.get('base_pf')}, "
            f"best_score>={row.get('best_pf_threshold')}, best_pf={row.get('best_pf')}, "
            f"high_score>={row.get('high_threshold')}, high_pf={row.get('high_pf')}, "
            f"recommendation={row.get('recommendation')}"
        )


def append_text_count_lines(lines: list[str], rows: object, *, limit: int) -> None:
    if not isinstance(rows, list) or not rows:
        lines.append("- None")
        return
    appended = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(f"- {row.get('text')}: {row.get('count')}")
        appended += 1
        if appended >= limit:
            break
    if appended == 0:
        lines.append("- None")


def format_warning_list(value: object) -> str:
    if not isinstance(value, list) or not value:
        return "None"
    rendered = [str(item) for item in value if str(item).strip()]
    return "; ".join(rendered) if rendered else "None"


def format_list_value(value: object) -> str:
    if not isinstance(value, list) or not value:
        return "None"
    rendered = [str(item) for item in value if str(item).strip()]
    return ", ".join(rendered) if rendered else "None"


def format_semicolon_list(value: object) -> str:
    if not isinstance(value, list) or not value:
        return "None"
    rendered = [str(item) for item in value if str(item).strip()]
    return "; ".join(rendered) if rendered else "None"


def format_detected_loss_limits(value: object) -> str:
    if not isinstance(value, list) or not value:
        return "None"
    rendered = []
    for item in value:
        if not isinstance(item, dict):
            continue
        rendered.append(f"{item.get('limit')}: {item.get('count')}")
    return ", ".join(rendered) if rendered else "None"


def format_mapping_value(value: object, *, separator: str = "=") -> str:
    if not isinstance(value, dict) or not value:
        return "None"
    rendered = [f"{key}{separator}{item}" for key, item in value.items() if str(key).strip()]
    return ", ".join(rendered) if rendered else "None"


def append_mt5_strategy_tester_analysis_lines(
    lines: list[str],
    payload: object,
    *,
    current_promotion_generated_at: object = "",
) -> None:
    if not isinstance(payload, dict) or not payload:
        return
    adoption = payload.get("adoption") if isinstance(payload.get("adoption"), dict) else {}
    embedded_promotion = (
        payload.get("promotion_gate") if isinstance(payload.get("promotion_gate"), dict) else {}
    )
    plan = (
        payload.get("source_time_refresh_plan")
        if isinstance(payload.get("source_time_refresh_plan"), dict)
        else {}
    )
    lines.extend(
        [
            "",
            "## MT5 Strategy Tester Analysis",
            f"- Generated at: {payload.get('generated_at', '')}",
            (
                "- Adoption: "
                f"status={adoption.get('status', '')}, "
                f"candidates={format_list_value(adoption.get('candidate_labels'))}, "
                f"aggregate_only={format_list_value(adoption.get('aggregate_only_labels'))}"
            ),
        ]
    )
    embedded_generated_at = str(embedded_promotion.get("generated_at") or "")
    embedded_decision = str(embedded_promotion.get("decision") or "")
    current_generated_at = str(current_promotion_generated_at or "")
    if embedded_generated_at or embedded_decision:
        lines.append(
            "- Embedded Promotion Gate: "
            f"generated_at={embedded_generated_at}, decision={embedded_decision}"
        )
        if current_generated_at:
            freshness = "current" if embedded_generated_at == current_generated_at else "stale"
            freshness_line = (
                "- Embedded Promotion Gate freshness: "
                f"{freshness}, current={current_generated_at}"
            )
            if freshness == "stale":
                freshness_line += (
                    f", refresh=`{MT5_STRATEGY_TESTER_ANALYSIS_REFRESH_COMMAND_TEXT}`"
                )
            lines.append(freshness_line)
    blockers = adoption.get("blockers") if isinstance(adoption.get("blockers"), list) else []
    if blockers:
        lines.append(f"- Adoption blockers: {format_list_value(blockers)}")
    if plan:
        lines.extend(
            [
                (
                    "- Source-time refresh: "
                    f"status={plan.get('status', '')}, "
                    f"issues={plan.get('issue_count', '')}, "
                    f"candidate_issues={plan.get('candidate_issue_count', '')}"
                ),
                f"- Source-time issue labels: {format_list_value(plan.get('issue_labels'))}",
                (
                    "- Source-time candidate issue labels: "
                    f"{format_list_value(plan.get('candidate_issue_labels'))}"
                ),
            ]
        )
        command_fields = [
            ("Refresh queue", "refresh_queue_command_text"),
            ("Dry-run launch", "dry_run_launch_command_text"),
            ("Collect + refresh", "collect_execute_and_refresh_command_text"),
            ("Refresh analysis", "refresh_analysis_command_text"),
        ]
        for label, key in command_fields:
            command = plan.get(key)
            if command:
                lines.append(f"- {label}: `{command}`")
        entries = plan.get("entries") if isinstance(plan.get("entries"), list) else []
        for entry in entries[:8]:
            if not isinstance(entry, dict):
                continue
            queue_step = f"{entry.get('queue_id', '')}/{entry.get('step_label', '')}"
            parts = [
                f"label={entry.get('label', '')}",
                f"candidate={entry.get('candidate', '')}",
                f"issue={entry.get('issue', '')}",
                f"step={queue_step}",
                f"dates={entry.get('dates', '')}",
                f"forward={entry.get('forward', '')}",
                f"inputs={entry.get('inputs', '')}",
                f"report={entry.get('report', '')}",
                f"launch={entry.get('launch_command_kind', '')}",
            ]
            collect_command = entry.get("collect_command_text")
            if collect_command:
                parts.append(f"collect={collect_command}")
            lines.append("- Source-time refresh entry: " + ", ".join(parts))


def append_risk_preset_fix_execution_lines(lines: list[str], execution: dict[str, object]) -> None:
    if execution.get("kind") != "mt5_risk_preset_fix":
        return
    if "ok" in execution:
        lines.append(f"  risk_preset_ok: {execution.get('ok')}")
    detected_limits = execution.get("detected_consecutive_loss_limits")
    if isinstance(detected_limits, list) and detected_limits:
        lines.append(f"  detected_loss_limits: {format_detected_loss_limits(detected_limits)}")
    inputs = execution.get("inputs")
    if isinstance(inputs, dict) and inputs:
        lines.append(f"  current_inputs: {format_mapping_value(inputs)}")
    errors = execution.get("errors")
    if isinstance(errors, list) and errors:
        lines.append(f"  errors: {format_semicolon_list(errors)}")
    elif "errors" in execution:
        lines.append("  errors: None")
    required_inputs = execution.get("required_inputs")
    if isinstance(required_inputs, dict) and required_inputs:
        lines.append(f"  required_inputs: {format_mapping_value(required_inputs, separator=' ')}")


def append_score_calibration_execution_lines(
    lines: list[str],
    action: dict[str, object],
    execution: dict[str, object],
) -> None:
    if execution.get("kind") != "score_calibration":
        return
    evidence = action.get("evidence")
    if not isinstance(evidence, dict):
        return
    calibration = evidence.get("calibration") if isinstance(evidence, dict) else None
    if isinstance(calibration, dict) and calibration:
        required_threshold = calibration.get("required_threshold")
        required_count = calibration.get("required_count")
        required_threshold_count = calibration.get("required_threshold_count")
        missing = calibration.get("sample_shortage_at_required_threshold")
        gap_parts = [
            f"status={calibration.get('status')}",
            f"required>={required_threshold}",
            f"count={required_threshold_count}/{required_count}",
            f"missing={missing}",
        ]
        if calibration.get("points_from_required_threshold") is not None:
            gap_parts.append(f"points_from_required={calibration.get('points_from_required_threshold')}")
        lines.append(f"  score_gap: {', '.join(gap_parts)}")
        highest_sampled = format_threshold_row(calibration.get("highest_sampled_threshold"))
        if highest_sampled != "None":
            lines.append(f"  highest_sampled: {highest_sampled}")
        highest_sufficient = format_threshold_row(calibration.get("highest_sufficient_threshold"))
        if highest_sufficient != "None":
            lines.append(f"  highest_sufficient: {highest_sufficient}")
        recommendation = calibration.get("recommendation")
        if recommendation:
            lines.append(f"  calibration_recommendation: {recommendation}")
    quality_failed_checks = evidence.get("quality_failed_checks")
    if not isinstance(quality_failed_checks, dict):
        quality_failed_checks = evidence.get("failed_checks")
    quality_gap = format_score_quality_gap(quality_failed_checks)
    if quality_gap:
        lines.append(f"  score_quality_gap: {quality_gap}")
    weight_search = evidence.get("weight_search")
    if isinstance(weight_search, dict) and weight_search:
        candidate = weight_search.get("top_weight_candidate")
        rendered = format_score_weight_candidate(candidate)
        if rendered != "None":
            lines.append(f"  weight_search_top: {rendered}")
        diagnostics = format_score_weight_diagnostics(weight_search.get("diagnostics"))
        if diagnostics != "None":
            lines.append(f"  weight_search_delta: {diagnostics}")


def format_score_quality_gap(failed_checks: object) -> str:
    if not isinstance(failed_checks, dict):
        return ""
    parts: list[str] = []
    for check_name, label in (
        ("score_upper_threshold_avg_r", "upper_avg_r"),
        ("score_upper_threshold_pf", "upper_pf"),
        ("score_threshold_avg_r_not_degrading", "avg_r_degradation"),
    ):
        row = failed_checks.get(check_name)
        if not isinstance(row, dict):
            continue
        value = row.get("value")
        requirement = row.get("requirement")
        if check_name == "score_upper_threshold_avg_r" and isinstance(value, dict):
            rendered = (
                f"threshold={format_number_like(value.get('threshold'))} "
                f"avg_r={format_number_like(value.get('avg_r'))}/{requirement}"
            )
        elif check_name == "score_upper_threshold_pf" and isinstance(value, dict):
            rendered = (
                f"threshold={format_number_like(value.get('threshold'))} "
                f"pf={format_number_like(value.get('pf'))}/{requirement}"
            )
        elif check_name == "score_threshold_avg_r_not_degrading" and isinstance(value, dict):
            rendered = (
                f"{format_number_like(value.get('from_threshold'))}->{format_number_like(value.get('to_threshold'))} "
                f"drop={format_number_like(value.get('drop'))}/{requirement}"
            )
        else:
            rendered = f"{format_number_like(value)}/{requirement}"
        parts.append(f"{label}={rendered}")
    return "; ".join(parts)


def requirement_minimum_number(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    for comparator in (">=", ">"):
        if comparator in text:
            text = text.split(comparator, 1)[1]
            break
    token: list[str] = []
    started = False
    for char in text:
        if char.isdigit() or char in ".-":
            token.append(char)
            started = True
        elif started:
            break
    if not token:
        return None
    try:
        return float("".join(token))
    except ValueError:
        return None


def format_number_like(value: object) -> str:
    if isinstance(value, bool) or value is None:
        return str(value)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if numeric.is_integer():
        return str(int(numeric))
    return str(round(numeric, 4))


def format_agent_csv_source_time_coverage(coverage: object) -> str:
    if not isinstance(coverage, dict) or not coverage:
        return "not_reported"
    parts: list[str] = []
    if coverage.get("close_rows") is not None:
        parts.append(f"close={format_number_like(coverage.get('close_rows'))}")
    if coverage.get("close_rows_with_server_time") is not None:
        parts.append(f"with_server_time={format_number_like(coverage.get('close_rows_with_server_time'))}")
    if coverage.get("close_rows_without_server_time") is not None:
        parts.append(f"without_server_time={format_number_like(coverage.get('close_rows_without_server_time'))}")
    first_server_time = str(coverage.get("first_server_time") or "")
    last_server_time = str(coverage.get("last_server_time") or "")
    if first_server_time or last_server_time:
        parts.append(f"range={first_server_time}..{last_server_time}")
    if coverage.get("span_days") is not None:
        parts.append(f"span_days={format_number_like(coverage.get('span_days'))}")
    return ", ".join(parts) if parts else "not_reported"


def append_backtest_sample_execution_lines(
    lines: list[str],
    action: dict[str, object],
    execution: dict[str, object],
) -> None:
    if execution.get("kind") != "backtest_sample_refresh":
        return
    evidence = action.get("evidence")
    if not isinstance(evidence, dict):
        return
    failed_check = evidence.get("failed_check")
    if isinstance(failed_check, dict):
        current = failed_check.get("value")
        requirement = failed_check.get("requirement")
        required = requirement_minimum_number(requirement)
        parts = []
        if required is not None:
            parts.append(f"count={format_number_like(current)}/{format_number_like(required)}")
            parts.append(f"missing={format_number_like(max(required - number(current), 0.0))}")
        else:
            parts.append(f"count={format_number_like(current)}")
            parts.append(f"requirement={requirement}")
        lines.append(f"  candidate_gap: {', '.join(parts)}")
    history_check = evidence.get("history_check")
    if isinstance(history_check, dict):
        status = "PASS" if history_check.get("passed") is True else "FAIL"
        lines.append(
            f"  history_check: {status}, value={format_number_like(history_check.get('value'))}, "
            f"requirement={history_check.get('requirement')}"
        )
    history_timeframes_check = evidence.get("history_timeframes_check")
    if isinstance(history_timeframes_check, dict):
        status = "PASS" if history_timeframes_check.get("passed") is True else "FAIL"
        value = history_timeframes_check.get("value") if isinstance(history_timeframes_check.get("value"), dict) else {}
        counts = value.get("counts") if isinstance(value.get("counts"), dict) else {}
        expected = value.get("expected") if isinstance(value.get("expected"), dict) else {}
        missing = value.get("missing_timeframes") if isinstance(value.get("missing_timeframes"), list) else []
        count_parts = [
            f"{timeframe}={format_number_like(counts.get(timeframe))}/{format_number_like(expected.get(timeframe))}"
            for timeframe in HISTORY_EXPECTED_BARS_PER_HOUR
        ]
        lines.append(
            f"  history_timeframes_check: {status}, {', '.join(count_parts)}, "
            f"missing={format_list_value(missing) if missing else 'none'}"
        )


def append_python_forward_wait_execution_lines(
    lines: list[str],
    action: dict[str, object],
    execution: dict[str, object],
) -> None:
    if execution.get("kind") != "python_forward_watch":
        return
    if action.get("action") != "wait_for_tradable_signal_before_forward_record":
        return
    evidence = action.get("evidence")
    forward_status = evidence.get("forward_status") if isinstance(evidence, dict) else None
    if not isinstance(forward_status, dict):
        return
    signal = forward_status.get("signal") if isinstance(forward_status.get("signal"), dict) else {}
    summary = forward_status.get("summary") if isinstance(forward_status.get("summary"), dict) else {}
    preview = signal.get("preview") if isinstance(signal.get("preview"), dict) else {}
    parts = [
        f"status={forward_status.get('operational_status')}",
        f"signal_action={signal.get('action')}",
        f"recordability={signal.get('recordability')}",
        f"closed={format_number_like(summary.get('closed'))}",
        f"open={format_number_like(summary.get('open'))}",
    ]
    ignore_reason = preview.get("ignore_reason")
    if ignore_reason:
        parts.append(f"reason={ignore_reason}")
    lines.append(f"  forward_wait: {', '.join(parts)}")
    heartbeat = evidence.get("forward_test_watch_heartbeat") if isinstance(evidence, dict) else None
    if isinstance(heartbeat, dict) and heartbeat:
        signal_payload = heartbeat.get("signal") if isinstance(heartbeat.get("signal"), dict) else {}
        counts = heartbeat.get("counts") if isinstance(heartbeat.get("counts"), dict) else {}
        watch_parts = [
            f"continuous={heartbeat.get('continuous')}",
        ]
        if "pid_file_written" in heartbeat:
            watch_parts.append(f"pid_file_written={heartbeat.get('pid_file_written')}")
        if "heartbeat_fresh" in heartbeat:
            watch_parts.append(f"fresh={heartbeat.get('heartbeat_fresh')}")
        if "heartbeat_age_seconds" in heartbeat or "heartbeat_max_age_seconds" in heartbeat:
            watch_parts.append(
                "age="
                f"{format_number_like(heartbeat.get('heartbeat_age_seconds'))}/"
                f"{format_number_like(heartbeat.get('heartbeat_max_age_seconds'))}s"
            )
        watch_parts.extend(
            [
                f"pid={heartbeat.get('watcher_pid')}",
                f"run_index={heartbeat.get('run_index')}",
                f"record={heartbeat.get('record_result')}",
                f"eval={heartbeat.get('evaluation_result')}",
                f"signal_action={signal_payload.get('action')}",
                f"closed={format_number_like(counts.get('closed'))}",
                f"open={format_number_like(counts.get('open'))}",
            ]
        )
        lines.append(f"  forward_watch: {', '.join(watch_parts)}")
    status_heartbeat = evidence.get("forward_status_watch_heartbeat") if isinstance(evidence, dict) else None
    if isinstance(status_heartbeat, dict) and status_heartbeat:
        status_parts = [
            f"continuous={status_heartbeat.get('continuous')}",
        ]
        if "pid_file_written" in status_heartbeat:
            status_parts.append(f"pid_file_written={status_heartbeat.get('pid_file_written')}")
        if "heartbeat_fresh" in status_heartbeat:
            status_parts.append(f"fresh={status_heartbeat.get('heartbeat_fresh')}")
        if "heartbeat_age_seconds" in status_heartbeat or "heartbeat_max_age_seconds" in status_heartbeat:
            status_parts.append(
                "age="
                f"{format_number_like(status_heartbeat.get('heartbeat_age_seconds'))}/"
                f"{format_number_like(status_heartbeat.get('heartbeat_max_age_seconds'))}s"
            )
        status_parts.extend(
            [
                f"pid={status_heartbeat.get('watcher_pid')}",
                f"run_index={status_heartbeat.get('run_index')}",
                f"status={status_heartbeat.get('operational_status')}",
                f"signal_action={status_heartbeat.get('signal_action')}",
                f"closed={format_number_like(status_heartbeat.get('closed'))}",
                f"open={format_number_like(status_heartbeat.get('open'))}",
                f"pf={format_number_like(status_heartbeat.get('pf'))}",
            ]
        )
        lines.append(f"  forward_status_watch: {', '.join(status_parts)}")


def append_dry_run_wait_execution_lines(
    lines: list[str],
    action: dict[str, object],
    execution: dict[str, object],
) -> None:
    if execution.get("kind") != "dry_run_refresh":
        return
    if action.get("action") != "wait_for_tradable_signal_before_dry_run":
        return
    evidence = action.get("evidence")
    if not isinstance(evidence, dict):
        return
    audit = evidence.get("dry_run_audit")
    if not isinstance(audit, dict):
        return
    signal = audit.get("signal") if isinstance(audit.get("signal"), dict) else {}
    command = audit.get("command") if isinstance(audit.get("command"), dict) else {}
    signal_command = audit.get("signal_command") if isinstance(audit.get("signal_command"), dict) else {}
    risk_gate = audit.get("risk_gate") if isinstance(audit.get("risk_gate"), dict) else {}
    parts = [
        f"outcome={audit.get('outcome')}",
        f"signal_action={signal.get('action')}",
        f"command_status={command.get('status')}",
        f"match_reason={signal_command.get('reason')}",
        f"risk_gate_allowed={risk_gate.get('allowed')}",
    ]
    failed_checks = evidence.get("failed_checks")
    if isinstance(failed_checks, dict) and failed_checks:
        parts.append(f"failed_checks={format_list_value(list(failed_checks.keys()))}")
    lines.append(f"  dry_run_wait: {', '.join(parts)}")
    freshness_check = failed_checks.get("dry_run_fresh") if isinstance(failed_checks, dict) else None
    freshness = freshness_check.get("value") if isinstance(freshness_check, dict) else None
    if isinstance(freshness, dict):
        max_age = freshness.get("max_age_seconds")
        freshness_parts = [
            f"fresh={freshness.get('fresh')}",
            f"command_fresh={freshness.get('command_fresh')}",
        ]
        if freshness.get("command_age_seconds") is not None or max_age is not None:
            freshness_parts.insert(
                1,
                f"command_age={format_number_like(freshness.get('command_age_seconds'))}/{format_number_like(max_age)}s",
            )
        if "result_required" in freshness:
            freshness_parts.append(f"result_required={freshness.get('result_required')}")
        if freshness.get("result_age_seconds") is not None:
            freshness_parts.append(
                f"result_age={format_number_like(freshness.get('result_age_seconds'))}/{format_number_like(max_age)}s"
            )
        if "result_fresh" in freshness:
            freshness_parts.append(f"result_fresh={freshness.get('result_fresh')}")
        lines.append(f"  dry_run_freshness: {', '.join(freshness_parts)}")


def append_dry_run_safety_execution_lines(
    lines: list[str],
    action: dict[str, object],
    execution: dict[str, object],
) -> None:
    if execution.get("kind") != "dry_run_refresh":
        return
    evidence = action.get("evidence")
    failed_checks = evidence.get("failed_checks") if isinstance(evidence, dict) else None
    if not isinstance(failed_checks, dict):
        return
    parts = []
    for check_name, label in (
        ("dry_run_command_sl_tp_present", "sl_tp"),
        ("dry_run_command_score_floor", "score"),
        ("dry_run_command_spread_limit_present", "spread"),
        ("dry_run_command_lot_policy_present", "lot_policy"),
    ):
        row = failed_checks.get(check_name)
        if not isinstance(row, dict):
            continue
        value = row.get("value")
        value_text = format_mapping_value(value) if isinstance(value, dict) else format_number_like(value)
        parts.append(f"{label}={value_text}/{row.get('requirement')}")
    if parts:
        lines.append(f"  dry_run_command_safety: {'; '.join(parts)}")


def is_mt5_tester_run_execution(execution: dict[str, object]) -> bool:
    return "methods/swing_eval/analysis/mt5_tester_run.py" in str(execution.get("command_text") or "")


def append_optimization_recommendation_execution_lines(
    lines: list[str],
    actions: list[dict[str, object]],
    execution: dict[str, object],
) -> None:
    if not (
        is_mt5_tester_run_execution(execution)
        or execution.get("kind")
        in {
            "mt5_optimization_recommendation_refresh",
            "mt5_optimization_report_refresh",
            "mt5_yearly_optimization_report_refresh",
        }
    ):
        return
    for action in actions:
        if action.get("area") != "mt5_optimization_recommendation":
            continue
        evidence = action.get("evidence")
        if not isinstance(evidence, dict):
            continue
        decision = evidence.get("decision") if isinstance(evidence.get("decision"), dict) else {}
        set_metadata = evidence.get("set_metadata") if isinstance(evidence.get("set_metadata"), dict) else {}
        score_refit_sides = set_metadata.get("score_refit_sides")
        parts = [
            f"adoptable={decision.get('adoptable')}",
            f"diagnostic_only={set_metadata.get('diagnostic_only')}",
            f"skipped_write={set_metadata.get('skipped_write')}",
            f"skip_reason={set_metadata.get('skip_reason')}",
            f"focus={set_metadata.get('focus_side')}",
        ]
        if isinstance(score_refit_sides, list) and score_refit_sides:
            parts.append(f"score_refit_sides={format_list_value(score_refit_sides)}")
        lines.append(f"  recommendation_block: {', '.join(parts)}")
        if set_metadata:
            pass_parts = [
                f"optimized_inputs={set_metadata.get('optimized_input_count')}",
                f"full_factorial={set_metadata.get('estimated_full_factorial_passes')}",
                f"written={set_metadata.get('skipped_write') is False}",
            ]
            lines.append(f"  recommendation_set_passes: {', '.join(pass_parts)}")
            coverage_summary = stable_hint_coverage_summary(set_metadata.get("stable_hint_coverage"))
            if coverage_summary != "None":
                lines.append(f"  recommendation_stable_hints: {coverage_summary}")
        reasons = decision.get("reasons")
        if isinstance(reasons, list) and reasons:
            lines.append(f"  recommendation_reason: {format_semicolon_list(reasons[:5])}")
        stable_result = evidence.get("stable_candidate_result")
        if isinstance(stable_result, dict) and stable_result:
            result_parts = [
                f"closed={stable_result.get('closed')}",
                f"pf={stable_result.get('pf')}",
                f"avg_price_r={stable_result.get('avg_price_r')}",
                f"max_dd_price_r={stable_result.get('max_drawdown_price_r')}",
                f"tester_ok={stable_result.get('tester_ok')}",
                f"adoptable={stable_result.get('recommendation_adoptable')}",
            ]
            lines.append(f"  stable_candidate_result: {', '.join(result_parts)}")
            stable_reasons = stable_result.get("recommendation_reasons")
            if isinstance(stable_reasons, list) and stable_reasons:
                lines.append(f"  stable_candidate_reason: {format_semicolon_list(stable_reasons[:5])}")
            stable_context = evidence.get("stable_candidate_failure_context")
            if isinstance(stable_context, dict):
                for context_key, label in (
                    ("chronological_failures", "chronological_failure"),
                    ("weak_time_segments", "weak_time"),
                    ("weak_trend_segments", "weak_trend"),
                    ("weak_sl_tp_segments", "weak_sl_tp"),
                ):
                    rows = stable_context.get(context_key)
                    if isinstance(rows, list) and rows:
                        lines.append(f"  stable_candidate_{label}: {format_segment_brief_rows(rows, limit=3)}")
            stable_refit = evidence.get("stable_candidate_refit")
            if isinstance(stable_refit, dict) and stable_refit:
                refit_parts = [
                    f"side={stable_refit.get('side')}",
                    f"driver={stable_refit.get('driver')}",
                    f"kind={stable_refit.get('kind')}",
                    f"focus={stable_refit.get('focus_side')}",
                ]
                if stable_refit.get("reason"):
                    refit_parts.append(f"reason={stable_refit.get('reason')}")
                lines.append(f"  stable_candidate_refit: {', '.join(refit_parts)}")
            completed_refit = evidence.get("stable_candidate_refit_completed")
            if isinstance(completed_refit, dict) and completed_refit:
                completed_parts = [
                    f"kind={completed_refit.get('kind')}",
                    f"side={completed_refit.get('side')}",
                ]
                side_status = completed_refit.get("side_status")
                if isinstance(side_status, dict) and side_status:
                    completed_parts.append(f"status={side_status.get('status')}")
                    completed_parts.append(f"pf={side_status.get('pf')}")
                    completed_parts.append(f"avg_price_r={side_status.get('avg_price_r')}")
                decision = completed_refit.get("decision")
                if isinstance(decision, dict) and isinstance(decision.get("reasons"), list):
                    completed_parts.append(f"reason={format_semicolon_list(decision.get('reasons')[:3])}")
                lines.append(f"  stable_candidate_refit_completed: {', '.join(completed_parts)}")
        return


def stable_hint_coverage_summary(value: object) -> str:
    rows = value if isinstance(value, list) else []
    if not rows:
        return "None"
    applied = 0
    skipped: dict[str, int] = {}
    parameters: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        parameter = str(row.get("parameter") or "")
        if parameter:
            parameters.append(parameter)
        if row.get("applied") is True:
            applied += 1
        else:
            reason = str(row.get("skip_reason") or "unknown")
            skipped[reason] = skipped.get(reason, 0) + 1
    parts = [
        f"applied={applied}",
        f"skipped={sum(skipped.values())}",
    ]
    if skipped:
        parts.append("skip_reasons=" + format_semicolon_list([f"{key}:{count}" for key, count in sorted(skipped.items())]))
    if parameters:
        parts.append("parameters=" + format_list_value(parameters[:8]))
    return ", ".join(parts)


def append_side_score_issue_execution_lines(
    lines: list[str],
    actions: list[dict[str, object]],
    execution: dict[str, object],
) -> None:
    if not is_mt5_tester_run_execution(execution):
        return
    for action in actions:
        area = action.get("area")
        if area not in {"mt5_optimization_score", "mt5_forward_score", "mt5_yearly_score"}:
            continue
        evidence = action.get("evidence")
        diagnostics = evidence.get("side_score_diagnostics") if isinstance(evidence, dict) else None
        compacted = compact_side_score_diagnostics(diagnostics, limit=4)
        issue_rows = [row for row in compacted if row.get("status") == "score_inversion"] or compacted[:1]
        for row in issue_rows:
            lines.append(
                f"  side_score_issue: {area} {row.get('side')} status={row.get('status')}, "
                f"base_pf={row.get('base_pf')}, best_score>={row.get('best_pf_threshold')}, "
                f"best_pf={row.get('best_pf')}, high_score>={row.get('high_threshold')}, "
                f"high_pf={row.get('high_pf')}, recommendation={row.get('recommendation')}"
            )
        result = evidence.get("score_weight_search_result") if isinstance(evidence, dict) else None
        if isinstance(result, dict) and result:
            append_side_weight_search_result_lines(lines, result)
        set_result = evidence.get("score_weight_set_result") if isinstance(evidence, dict) else None
        if isinstance(set_result, dict) and set_result:
            rendered = format_score_weight_set_result(set_result)
            if rendered != "None":
                lines.append(f"  score_weight_set_result: {rendered}")
        follow_up = evidence.get("score_weight_follow_up") if isinstance(evidence, dict) else None
        if isinstance(follow_up, dict) and follow_up:
            rendered = format_score_weight_follow_up(follow_up)
            if rendered != "None":
                lines.append(f"  score_weight_follow_up: {rendered}")


def append_score_weight_follow_up_execution_lines(
    lines: list[str],
    actions: list[dict[str, object]],
    execution: dict[str, object],
) -> None:
    if not isinstance(execution, dict) or execution.get("kind") != "score_weight_set":
        return
    for action in actions:
        evidence = action.get("evidence") if isinstance(action.get("evidence"), dict) else {}
        set_result = evidence.get("score_weight_set_result")
        if isinstance(set_result, dict) and set_result:
            rendered = format_score_weight_set_result(set_result)
            if rendered != "None":
                lines.append(f"  score_weight_set_result: {rendered}")
        follow_up = evidence.get("score_weight_follow_up")
        if isinstance(follow_up, dict) and follow_up:
            rendered = format_score_weight_follow_up(follow_up)
            if rendered != "None":
                lines.append(f"  score_weight_follow_up: {rendered}")


def append_side_weight_search_result_lines(lines: list[str], result: dict[str, object]) -> None:
    if isinstance(result.get("sides"), list):
        for item in result.get("sides", []):
            if isinstance(item, dict):
                append_side_weight_search_result_lines(lines, item)
        return
    candidate = result.get("top_weight_candidate")
    rendered = format_score_weight_candidate(candidate)
    if rendered != "None":
        lines.append(f"  side_weight_search_top: {rendered}")
    diagnostics = format_score_weight_diagnostics(result.get("diagnostics"))
    if diagnostics != "None":
        lines.append(f"  side_weight_search_delta: {diagnostics}")
    walk = format_score_weight_walk_forward(result.get("walk_forward"))
    if walk != "None":
        lines.append(f"  side_weight_search_walk: {walk}")
    regime = format_score_weight_regime_search(result.get("regime_search"))
    if regime != "None":
        lines.append(f"  side_weight_regime_top: {regime}")


def append_terminal_blocker_execution_lines(
    lines: list[str],
    action: dict[str, object],
    execution: dict[str, object],
) -> None:
    if not is_mt5_tester_run_execution(execution):
        return
    evidence = action.get("evidence") if isinstance(action.get("evidence"), dict) else {}
    blocker = evidence.get("terminal_blocker") if isinstance(evidence, dict) else None
    if not isinstance(blocker, dict):
        return
    processes = blocker.get("processes") if isinstance(blocker.get("processes"), list) else []
    process_texts: list[str] = []
    for item in processes[:3]:
        if not isinstance(item, dict):
            continue
        pid = item.get("pid", "")
        command = str(item.get("command", ""))
        process_texts.append(f"{pid}:{command}" if command else str(pid))
    parts = [
        f"blocked={blocker.get('running_terminal_blocked')}",
        f"detection_enabled={blocker.get('detection_enabled')}",
        f"processes={format_list_value(process_texts) if process_texts else 'none'}",
    ]
    lines.append(f"  terminal_blocker: {', '.join(parts)}")
    if blocker.get("note"):
        lines.append(f"  terminal_blocker_note: {blocker.get('note')}")


def append_yearly_validation_execution_lines(
    lines: list[str],
    action: dict[str, object],
    execution: dict[str, object],
) -> None:
    if action.get("area") != "mt5_yearly_validation":
        return
    if execution.get("kind") not in {
        "mt5_yearly_validation",
        "mt5_yearly_optimization_report_refresh",
        "mt5_optimization_recommendation_refresh",
    }:
        return
    evidence = action.get("evidence")
    if not isinstance(evidence, dict):
        return
    overall = evidence.get("overall") if isinstance(evidence.get("overall"), dict) else {}
    if overall:
        parts = []
        for key in ("closed", "pf", "avg_price_r", "net_profit"):
            if overall.get(key) is not None:
                parts.append(f"{key}={format_number_like(overall.get(key))}")
        if parts:
            lines.append(f"  yearly_overall: {', '.join(parts)}")
    failed_checks = evidence.get("failed_checks")
    if not isinstance(failed_checks, dict):
        return
    metric_names = [
        ("mt5_yearly_optimization_pf", "pf"),
        ("mt5_yearly_optimization_avg_price_r", "avg_price_r"),
        ("mt5_yearly_optimization_positive_forward_back", "positive_forward_back"),
    ]
    metric_parts = []
    for check_name, label in metric_names:
        row = failed_checks.get(check_name)
        if isinstance(row, dict):
            metric_parts.append(f"{label}={format_number_like(row.get('value'))}/{row.get('requirement')}")
    if metric_parts:
        lines.append(f"  yearly_metric_gap: {'; '.join(metric_parts)}")
    balance = failed_checks.get("mt5_yearly_optimization_side_total_price_r_balance")
    if isinstance(balance, dict):
        lines.append(
            "  yearly_side_balance: "
            f"{format_mapping_value(balance.get('value'))}/{balance.get('requirement')}"
        )
    source_filter = evidence.get("source_time_file_filter")
    if isinstance(source_filter, dict) and source_filter:
        dropped = source_filter.get("dropped_files")
        dropped_count = len(dropped) if isinstance(dropped, list) else 0
        lines.append(
            "  yearly_source_time_file_filter: "
            f"kept={format_number_like(source_filter.get('kept_files'))}/"
            f"{format_number_like(source_filter.get('input_files'))}, dropped={format_number_like(dropped_count)}"
        )
        if isinstance(dropped, list) and dropped:
            first = dropped[0] if isinstance(dropped[0], dict) else {}
            source_time = first.get("source_time") if isinstance(first.get("source_time"), dict) else {}
            lines.append(
                "  yearly_source_time_dropped: "
                f"{first.get('path')}, "
                f"{source_time.get('first_server_time', '')}..{source_time.get('last_server_time', '')}, "
                f"reason={first.get('reason', '')}"
            )
    missing_parts = []
    source_time = failed_checks.get("mt5_yearly_optimization_source_time_range")
    if isinstance(source_time, dict):
        source_value = source_time.get("value")
        if source_value == "missing":
            missing_parts.append("source_time_range=missing")
        elif isinstance(source_value, dict):
            missing_parts.append(
                "source_time_range="
                f"expected {source_value.get('expected_from_date')}..{source_value.get('expected_to_date')}, "
                f"actual {source_value.get('actual_first_server_time')}..{source_value.get('actual_last_server_time')}"
            )
        else:
            missing_parts.append(f"source_time_range={source_value}")
    chronological = failed_checks.get("mt5_yearly_optimization_chronological_splits")
    if isinstance(chronological, dict):
        chronological_value = chronological.get("value")
        if chronological_value == "missing":
            missing_parts.append("chronological_splits=missing")
    for check_name, label in (
        ("mt5_yearly_optimization_sl_tp_diagnostics", "sl_tp"),
        ("mt5_yearly_optimization_time_regime_diagnostics", "time_regime"),
        ("mt5_yearly_optimization_trend_regime_diagnostics", "trend_regime"),
    ):
        row = failed_checks.get(check_name)
        if not isinstance(row, dict):
            continue
        value = row.get("value")
        if value == "missing":
            missing_parts.append(f"{label}=missing")
        elif isinstance(value, dict) and isinstance(value.get("missing"), list):
            missing_parts.append(f"{label}={format_list_value(value.get('missing')[:8])}")
        elif isinstance(value, dict) and isinstance(value.get("unavailable"), list):
            missing_parts.append(f"{label}_unavailable={format_list_value(value.get('unavailable')[:8])}")
    if missing_parts:
        lines.append(f"  yearly_missing_evidence: {'; '.join(missing_parts)}")
    chronological_failures = evidence.get("chronological_failures")
    if isinstance(chronological_failures, list) and chronological_failures:
        appended = 0
        for row in chronological_failures:
            if not isinstance(row, dict):
                continue
            lines.append(f"  yearly_chronological_failure: {format_segment_brief(row)}")
            appended += 1
            if appended >= 4:
                break
    for key, label in (
        ("weak_time_segments", "weak_time"),
        ("weak_trend_segments", "weak_trend"),
        ("weak_sl_tp_segments", "weak_sl_tp"),
    ):
        rows = evidence.get(key)
        if isinstance(rows, list) and rows:
            lines.append(f"  yearly_{label}: {format_segment_brief_rows(rows, limit=3)}")


def format_text_count_rows(rows: object, *, limit: int = 3) -> str:
    compacted = compact_text_count_rows(rows, limit=limit)
    if not compacted:
        return "None"
    return "; ".join(f"{row.get('text')}: {format_number_like(row.get('count'))}" for row in compacted)


def append_mt5_forward_signal_flow_line(lines: list[str], signal: dict[str, object]) -> None:
    parts = [
        f"rows={format_number_like(signal.get('rows'))}",
        f"buy/sell/hold={format_number_like(signal.get('buy'))}/{format_number_like(signal.get('sell'))}/{format_number_like(signal.get('hold'))}",
        f"tradable/other={format_number_like(signal.get('tradable'))}/{format_number_like(signal.get('other'))}",
    ]
    if signal.get("avg_score") is not None:
        parts.append(f"avg_score={format_number_like(signal.get('avg_score'))}")
    if signal.get("avg_buy_score") is not None or signal.get("avg_sell_score") is not None:
        parts.append(
            f"avg_buy/sell={format_number_like(signal.get('avg_buy_score'))}/{format_number_like(signal.get('avg_sell_score'))}"
        )
    lines.append(f"  mt5_forward_signal_flow: {', '.join(parts)}")
    top_reasons = format_text_count_rows(signal.get("top_reasons"), limit=3)
    if top_reasons != "None":
        lines.append(f"  mt5_forward_signal_top: {top_reasons}")


def append_mt5_forward_reject_flow_line(lines: list[str], reject: dict[str, object]) -> None:
    parts = [
        f"rows={format_number_like(reject.get('rows'))}",
        f"buy/sell/other={format_number_like(reject.get('buy'))}/{format_number_like(reject.get('sell'))}/{format_number_like(reject.get('hold_or_other'))}",
    ]
    detected = format_detected_loss_limits(reject.get("detected_consecutive_loss_limits"))
    if detected != "None":
        parts.append(f"detected_loss_limits={detected}")
    lines.append(f"  mt5_forward_reject_flow: {', '.join(parts)}")
    top_messages = format_text_count_rows(reject.get("top_messages"), limit=3)
    if top_messages != "None":
        lines.append(f"  mt5_forward_reject_top: {top_messages}")


def append_mt5_forward_button_line(lines: list[str], button: dict[str, object]) -> None:
    parts = [
        f"rows={format_number_like(button.get('rows'))}",
        f"dry_run/ignored={format_number_like(button.get('dry_runs'))}/{format_number_like(button.get('ignored'))}",
        f"unsafe={format_number_like(button.get('unsafe'))}",
        f"buy/sell/wait={format_number_like(button.get('buy_clicks'))}/{format_number_like(button.get('sell_clicks'))}/{format_number_like(button.get('hold_or_other_clicks'))}",
    ]
    lines.append(f"  mt5_forward_button: {', '.join(parts)}")


def append_mt5_forward_risk_exposure_line(lines: list[str], risk: dict[str, object]) -> None:
    parts = []
    if risk.get("max_single_volume") is not None or risk.get("max_single_volume_limit") is not None:
        parts.append(
            "single="
            f"{format_number_like(risk.get('max_single_volume'))}/{format_number_like(risk.get('max_single_volume_limit'))}"
        )
    if risk.get("max_concurrent_volume") is not None or risk.get("max_total_volume_limit") is not None:
        parts.append(
            "concurrent="
            f"{format_number_like(risk.get('max_concurrent_volume'))}/{format_number_like(risk.get('max_total_volume_limit'))}"
        )
    if risk.get("max_concurrent_positions") is not None or risk.get("max_positions_limit") is not None:
        parts.append(
            "positions="
            f"{format_number_like(risk.get('max_concurrent_positions'))}/{format_number_like(risk.get('max_positions_limit'))}"
        )
    if risk.get("open_positions_at_end") is not None or risk.get("open_volume_at_end") is not None:
        parts.append(
            "open_end="
            f"{format_number_like(risk.get('open_positions_at_end'))}/{format_number_like(risk.get('open_volume_at_end'))}"
        )
    if risk.get("daily_loss_stop_rejections") is not None or risk.get("consecutive_loss_stop_rejections") is not None:
        parts.append(
            "stop_rejections="
            f"{format_number_like(risk.get('daily_loss_stop_rejections'))}/{format_number_like(risk.get('consecutive_loss_stop_rejections'))}"
        )
    if risk.get("lot_limit_rejections") is not None:
        parts.append(f"lot_rejections={format_number_like(risk.get('lot_limit_rejections'))}")
    if parts:
        lines.append(f"  mt5_forward_risk_exposure: {', '.join(parts)}")


def format_mt5_forward_sl_tp_counts(diagnostics: object) -> str:
    if not isinstance(diagnostics, dict) or not diagnostics:
        return "None"
    parts = []
    for key, label in (
        ("sl", "sl"),
        ("tp", "tp"),
        ("rr_sl", "rr_sl"),
        ("rr_tp", "rr_tp"),
        ("weak", "weak"),
    ):
        if diagnostics.get(key) is not None:
            parts.append(f"{label}={format_number_like(diagnostics.get(key))}")
    missing = diagnostics.get("missing")
    if isinstance(missing, list) and missing:
        parts.append(f"missing={format_list_value(missing)}")
    return ", ".join(parts) if parts else "None"


def append_mt5_forward_sl_tp_line(lines: list[str], diagnostics: dict[str, object]) -> None:
    count_line = format_mt5_forward_sl_tp_counts(diagnostics)
    if count_line != "None":
        lines.append(f"  mt5_forward_sl_tp: {count_line}")
    weak_segments = diagnostics.get("weak_segments")
    if isinstance(weak_segments, list):
        for row in weak_segments[:2]:
            if isinstance(row, dict):
                lines.append(f"  mt5_forward_weak_sl_tp: {format_segment_brief(row)}")


def append_mt5_forward_execution_lines(
    lines: list[str],
    actions: list[dict[str, object]],
    execution: dict[str, object],
) -> None:
    if execution.get("kind") not in {"strategy_forward", "mt5_optimization_recommendation_refresh"}:
        return
    if execution.get("kind") == "strategy_forward" and not is_mt5_tester_run_execution(execution):
        return
    seen_warnings: set[str] = set()
    seen_detected_limits: set[str] = set()
    seen_schema_gaps: set[str] = set()
    signal_flow_appended = False
    reject_flow_appended = False
    button_appended = False
    risk_exposure_appended = False
    sl_tp_appended = False
    for action in actions:
        area = action.get("area")
        evidence = action.get("evidence")
        if not isinstance(evidence, dict):
            continue
        if area == "mt5_forward":
            overall = evidence.get("overall") if isinstance(evidence.get("overall"), dict) else {}
            failed_checks = evidence.get("failed_checks")
            if not isinstance(failed_checks, dict):
                failed_checks = {}
            parts = []
            if overall.get("closed") is not None:
                parts.append(f"closed={format_number_like(overall.get('closed'))}")
            for check_name, label in (
                ("mt5_forward_pf", "pf"),
                ("mt5_forward_max_losing_streak", "max_losing_streak"),
            ):
                row = failed_checks.get(check_name)
                if isinstance(row, dict):
                    parts.append(f"{label}={format_number_like(row.get('value'))}/{row.get('requirement')}")
            if parts:
                lines.append(f"  mt5_forward_gap: {', '.join(parts)}")
            side_parts = []
            for side in ("buy", "sell"):
                side_metrics = []
                for suffix, label in (
                    ("closed_count", "closed"),
                    ("pf", "pf"),
                    ("avg_price_r", "avg_price_r"),
                ):
                    row = failed_checks.get(f"mt5_forward_{side}_{suffix}")
                    if isinstance(row, dict):
                        side_metrics.append(f"{label}={format_number_like(row.get('value'))}/{row.get('requirement')}")
                if side_metrics:
                    side_parts.append(f"{side} {' '.join(side_metrics)}")
            if side_parts:
                lines.append(f"  mt5_forward_side_gap: {'; '.join(side_parts)}")
            balance = failed_checks.get("mt5_forward_side_total_price_r_balance")
            if isinstance(balance, dict):
                lines.append(
                    "  mt5_forward_side_balance: "
                    f"{format_mapping_value(balance.get('value'))}/{balance.get('requirement')}"
                )
        if area in {
            "mt5_forward",
            "mt5_forward_button",
            "mt5_forward_diagnostics",
            "mt5_forward_schema",
            "mt5_forward_risk",
        }:
            signal = evidence.get("signal")
            if not signal_flow_appended and isinstance(signal, dict) and signal:
                append_mt5_forward_signal_flow_line(lines, signal)
                signal_flow_appended = True
            reject = evidence.get("reject")
            if not reject_flow_appended and isinstance(reject, dict) and reject:
                append_mt5_forward_reject_flow_line(lines, reject)
                reject_flow_appended = True
            button = evidence.get("button")
            if not button_appended and isinstance(button, dict) and button:
                append_mt5_forward_button_line(lines, button)
                button_appended = True
            risk = evidence.get("risk_exposure")
            if not risk_exposure_appended and isinstance(risk, dict) and risk:
                append_mt5_forward_risk_exposure_line(lines, risk)
                risk_exposure_appended = True
            sl_tp = evidence.get("sl_tp_diagnostics")
            if not sl_tp_appended and isinstance(sl_tp, dict) and sl_tp:
                append_mt5_forward_sl_tp_line(lines, sl_tp)
                sl_tp_appended = True
        if area in {"mt5_forward_diagnostics", "mt5_forward_schema"}:
            failed_checks = evidence.get("failed_checks")
            if isinstance(failed_checks, dict):
                sl_tp = failed_checks.get("mt5_forward_sl_tp_diagnostics")
                if isinstance(sl_tp, dict):
                    value = sl_tp.get("value")
                    if isinstance(value, dict) and isinstance(value.get("missing"), list):
                        lines.append(
                            f"  mt5_forward_sl_tp_gap: missing={format_list_value(value.get('missing'))}"
                        )
                    else:
                        lines.append(
                            f"  mt5_forward_sl_tp_gap: value={value}, requirement={sl_tp.get('requirement')}"
                        )
            warnings = evidence.get("diagnostic_warnings")
            if isinstance(warnings, list) and warnings:
                for warning in warnings[:3]:
                    warning_text = str(warning)
                    if warning_text not in seen_warnings:
                        lines.append(f"  mt5_forward_warning: {warning_text}")
                        seen_warnings.add(warning_text)
            detected_limits = evidence.get("detected_consecutive_loss_limits")
            if isinstance(detected_limits, list) and detected_limits:
                detected_text = format_detected_loss_limits(detected_limits)
                if detected_text not in seen_detected_limits:
                    lines.append(f"  mt5_forward_detected_loss_limits: {detected_text}")
                    seen_detected_limits.add(detected_text)
            schema = evidence.get("csv_schema")
            if isinstance(schema, dict) and schema:
                missing_fields = schema.get("missing_fields")
                unavailable_fields = schema.get("unavailable_fields")
                missing_execution_fields = schema.get("missing_execution_fields")
                schema_parts = [
                    f"entry_time={schema.get('entry_time_diagnostics_available')}",
                    f"trend={schema.get('trend_diagnostics_available')}",
                    f"execution={schema.get('execution_diagnostics_available')}",
                ]
                if isinstance(missing_fields, list) and missing_fields:
                    schema_parts.append(f"missing={format_list_value(missing_fields[:8])}")
                if isinstance(unavailable_fields, list) and unavailable_fields:
                    schema_parts.append(f"unavailable={format_list_value(unavailable_fields[:8])}")
                if isinstance(missing_execution_fields, list) and missing_execution_fields:
                    schema_parts.append(f"missing_execution={format_list_value(missing_execution_fields[:8])}")
                schema_text = ", ".join(schema_parts)
                if schema_text not in seen_schema_gaps:
                    lines.append(f"  mt5_forward_schema_gap: {schema_text}")
                    seen_schema_gaps.add(schema_text)


def append_mt5_back_forward_execution_lines(
    lines: list[str],
    actions: list[dict[str, object]],
    execution: dict[str, object],
) -> None:
    if execution.get("kind") != "mt5_back_forward_run":
        return
    for action in actions:
        if action.get("area") != "mt5_back_forward":
            continue
        evidence = action.get("evidence")
        if not isinstance(evidence, dict):
            continue
        failed_checks = evidence.get("failed_checks") if isinstance(evidence.get("failed_checks"), dict) else {}
        runner = evidence.get("runner") if isinstance(evidence.get("runner"), dict) else {}
        status = runner.get("performance_comparison_status")
        reason = runner.get("performance_comparison_reason")
        available = runner.get("performance_comparison_available")
        lines.append(
            "  mt5_back_forward_gap: "
            f"state={runner.get('evidence_state', '')}, status={status}, available={available}, reason={reason}"
        )
        if failed_checks:
            lines.append(f"  mt5_back_forward_failed_checks: {format_list_value(list(failed_checks.keys()))}")
        sample_shortage = (
            evidence.get("sample_shortage") if isinstance(evidence.get("sample_shortage"), dict) else {}
        )
        if sample_shortage:
            lines.append(
                "  mt5_back_forward_sample_shortage: "
                f"status={sample_shortage.get('status', '')}, "
                f"min_closed={format_number_like(sample_shortage.get('min_closed'))}, "
                f"backtest_trades={format_number_like(sample_shortage.get('backtest_trades'))}, "
                f"forward_trades={format_number_like(sample_shortage.get('forward_trades'))}, "
                f"backtest_ok={sample_shortage.get('backtest_meets_min_closed', '')}, "
                f"forward_ok={sample_shortage.get('forward_meets_min_closed', '')}"
            )
            recovery = (
                evidence.get("sample_shortage_recovery")
                if isinstance(evidence.get("sample_shortage_recovery"), dict)
                else {}
            )
            recovery_execution = (
                recovery.get("execution")
                if isinstance(recovery.get("execution"), dict)
                else {}
            )
            if recovery:
                lines.append(
                    "  mt5_back_forward_recovery: "
                    f"strategy={recovery.get('strategy', '')}, "
                    f"range_strategy={recovery.get('range_strategy', '')}, "
                    f"current={recovery.get('current_from_date', '')}..{recovery.get('current_to_date', '')}, "
                    f"current_days={format_number_like(recovery.get('current_range_days'))}, "
                    f"from={recovery.get('suggested_from_date', '')}, "
                    f"to={recovery.get('suggested_to_date', '')}, "
                    f"command={recovery_execution.get('command_text', '')}"
                )
        conditions = (
            execution.get("execution_conditions") if isinstance(execution.get("execution_conditions"), dict) else {}
        )
        if conditions:
            condition_parts = []
            for key, label in (
                ("per_step_timeout_seconds", "timeout"),
                ("since_minutes", "since"),
                ("min_closed", "min_closed"),
                ("forward_mode", "forward_mode"),
                ("from_date", "from"),
                ("to_date", "to"),
            ):
                value = conditions.get(key)
                if value not in (None, ""):
                    condition_parts.append(f"{label}={format_number_like(value)}")
            if condition_parts:
                lines.append(f"  mt5_back_forward_conditions: {', '.join(condition_parts)}")
        rows = runner.get("performance_comparison_rows") if isinstance(runner.get("performance_comparison_rows"), list) else []
        forward_row = next(
            (
                row
                for row in rows
                if isinstance(row, dict) and str(row.get("dataset") or "").lower() == "forward"
            ),
            None,
        )
        if isinstance(forward_row, dict):
            parts = []
            for key, label in (
                ("trades", "trades"),
                ("pf", "pf"),
                ("pf_delta_vs_backtest", "pf_delta"),
                ("avg_r", "avg_r"),
                ("avg_r_delta_vs_backtest", "avg_r_delta"),
                ("net_profit_delta_vs_backtest", "net_delta"),
            ):
                if forward_row.get(key) is not None:
                    parts.append(f"{label}={format_number_like(forward_row.get(key))}")
            if parts:
                lines.append(f"  mt5_back_forward_forward: {', '.join(parts)}")
        return


def manual_queue_launch_text(item: dict[str, object]) -> str:
    command_text = str(item.get("launch_command_text") or "")
    if command_text and item.get("launch_command_kind") == "runner_execute":
        command_text = f"runner execute: {command_text}"
    if not command_text and item.get("launch_error"):
        command_text = f"launch unavailable: {item.get('launch_error', '')}"
    return command_text


def mt5_quick_input_text(quick_input: object) -> str:
    if not isinstance(quick_input, dict) or not quick_input:
        return ""
    parts = []
    for key, label in (
        ("queue_step", "step"),
        ("purpose", "purpose"),
        ("expert", "expert"),
        ("symbol", "symbol"),
        ("period", "period"),
        ("model", "model"),
        ("dates", "dates"),
        ("forward", "forward"),
        ("forward_mode", "forward_mode"),
        ("optimization_label", "optimization"),
        ("inputs", "inputs"),
        ("report", "report"),
        ("expected_report_artifact", "expected"),
        ("launch_kind", "launch_kind"),
        ("manual_run_start_after", "start_after"),
    ):
        value = quick_input.get(key)
        if key == "dates" and value in ("", None):
            from_date = quick_input.get("from_date", "")
            to_date = quick_input.get("to_date", "")
            value = f"{from_date} -> {to_date}" if from_date or to_date else ""
        if value not in ("", None, [], {}):
            parts.append(f"{label}={value}")
    return ", ".join(parts)


def append_mt5_status_watch_manual_queue_operator_handoff_lines(
    lines: list[str],
    watcher: dict[str, object],
    *,
    prefix: str,
    label_prefix: str,
) -> None:
    handoff = watcher.get("manual_test_queue_operator_handoff")
    if not isinstance(handoff, dict) or not handoff:
        return
    parts = []
    for key, label in (
        ("state", "state"),
        ("status", "status"),
        ("next_action", "next_action"),
        ("collect_ready", "collect_ready"),
    ):
        value = handoff.get(key)
        if value != "" and value is not None:
            parts.append(f"{label}={value}")
    for key, label in (
        ("ready_entry_ids", "ready"),
        ("waiting_entry_ids", "waiting"),
        ("stale_entry_ids", "stale"),
    ):
        value = handoff.get(key)
        if value:
            parts.append(f"{label}={format_list_value(value)}")
    if parts:
        lines.append(f"{prefix}{label_prefix}manual_queue_handoff: {', '.join(parts)}")
    quick_input = handoff.get("quick_input")
    if not isinstance(quick_input, dict) or not quick_input:
        quick_input = watcher.get("manual_test_queue_operator_handoff_quick_input")
    quick_text = mt5_quick_input_text(quick_input)
    if quick_text:
        lines.append(f"{prefix}{label_prefix}manual_queue_handoff_quick_input: {quick_text}")
    next_step = handoff.get("next_mt5_step")
    if isinstance(next_step, dict) and next_step:
        dates = next_step.get("dates") or f"{next_step.get('from_date', '')}->{next_step.get('to_date', '')}"
        lines.append(
            f"{prefix}{label_prefix}manual_queue_handoff_next_step: "
            f"{next_step.get('queue_id', '')}/{next_step.get('step_label', '')}, "
            f"symbol={next_step.get('symbol', '')}, "
            f"period={next_step.get('period', '')}, "
            f"dates={dates}, "
            f"forward={next_step.get('forward', '')}, "
            f"run_type={next_step.get('run_type', '')}, "
            f"inputs={next_step.get('inputs', '')}, "
            f"report={next_step.get('report', '')}"
        )
    dry_run = str(handoff.get("dry_run_command_text") or "")
    execute = str(handoff.get("execute_command_text") or "")
    execute_and_refresh = str(handoff.get("execute_and_refresh_analysis_command_text") or "")
    if dry_run or execute or execute_and_refresh:
        lines.append(
            f"{prefix}{label_prefix}manual_queue_handoff_collect: "
            f"dry_run={dry_run}, execute={execute}, "
            f"execute_and_refresh_analysis={execute_and_refresh}"
        )


def append_mt5_status_watch_manual_queue_launch_handoff_lines(
    lines: list[str],
    watcher: dict[str, object],
    *,
    prefix: str,
    label_prefix: str,
) -> None:
    has_launch_handoff = any(
        watcher.get(key) not in ("", None, [], {})
        for key in (
            "manual_queue_launch_status",
            "manual_queue_launch_selected_item",
            "manual_queue_launch_selected_matches_queue_handoff",
            "manual_queue_launch_queue_operator_handoff_state",
            "manual_queue_launch_queue_operator_handoff_next_mt5_step",
            "manual_queue_launch_queue_operator_handoff_collect_ready",
            "manual_queue_launch_queue_operator_handoff_waiting_entry_ids",
            "manual_queue_launch_queue_operator_handoff_collect_execute_command_text",
        )
    )
    if not has_launch_handoff:
        return
    parts = []
    for key, label in (
        ("manual_queue_launch_status", "status"),
        ("manual_queue_launch_next_action", "next_action"),
        ("manual_queue_launch_launch_command_kind", "launch_kind"),
        ("manual_queue_launch_selected_matches_queue_handoff", "selected_matches"),
        ("manual_queue_launch_queue_operator_handoff_state", "state"),
        ("manual_queue_launch_queue_operator_handoff_collect_ready", "collect_ready"),
        ("manual_queue_launch_running_terminal_count", "running_terminal_count"),
    ):
        value = watcher.get(key)
        if value != "" and value is not None:
            parts.append(f"{label}={value}")
    for key, label in (
        ("manual_queue_launch_queue_operator_handoff_ready_entry_ids", "ready"),
        ("manual_queue_launch_queue_operator_handoff_waiting_entry_ids", "waiting"),
        ("manual_queue_launch_queue_operator_handoff_stale_entry_ids", "stale"),
        ("manual_queue_launch_blocked_reasons", "blocked"),
    ):
        value = watcher.get(key)
        if value:
            parts.append(f"{label}={format_list_value(value)}")
    if parts:
        lines.append(f"{prefix}{label_prefix}manual_queue_launch_handoff: {', '.join(parts)}")
    quick_text = mt5_quick_input_text(
        watcher.get("manual_queue_launch_queue_operator_handoff_quick_input")
    )
    if quick_text:
        lines.append(f"{prefix}{label_prefix}manual_queue_launch_handoff_quick_input: {quick_text}")
    next_step = watcher.get("manual_queue_launch_queue_operator_handoff_next_mt5_step")
    if not isinstance(next_step, dict) or not next_step:
        next_step = watcher.get("manual_queue_launch_selected_item")
    if isinstance(next_step, dict) and next_step:
        dates = next_step.get("dates") or f"{next_step.get('from_date', '')}->{next_step.get('to_date', '')}"
        lines.append(
            f"{prefix}{label_prefix}manual_queue_launch_handoff_next_step: "
            f"{next_step.get('queue_id', '')}/{next_step.get('step_label', '')}, "
            f"symbol={next_step.get('symbol', '')}, "
            f"period={next_step.get('period', '')}, "
            f"dates={dates}, "
            f"forward={next_step.get('forward', '')}, "
            f"inputs={next_step.get('inputs', '')}, "
            f"report={next_step.get('report', '')}"
        )
    dry_run = str(watcher.get("manual_queue_launch_queue_operator_handoff_collect_dry_run_command_text") or "")
    execute = str(watcher.get("manual_queue_launch_queue_operator_handoff_collect_execute_command_text") or "")
    execute_and_refresh = str(
        watcher.get(
            "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_analysis_command_text"
        )
        or ""
    )
    execute_and_refresh_all = str(
        watcher.get(
            "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_all_command_text"
        )
        or ""
    )
    if dry_run or execute or execute_and_refresh or execute_and_refresh_all:
        lines.append(
            f"{prefix}{label_prefix}manual_queue_launch_handoff_collect: "
            f"dry_run={dry_run}, execute={execute}, "
            f"execute_and_refresh_analysis={execute_and_refresh}, "
            f"execute_and_refresh_all={execute_and_refresh_all}"
        )


def append_mt5_status_watch_operator_alias_lines(
    lines: list[str],
    watcher: dict[str, object],
    *,
    prefix: str,
    label_prefix: str,
) -> None:
    action_parts = []
    for key, label in (
        ("mt5_next_operator_action", "action"),
        ("mt5_next_operator_mode", "mode"),
        ("mt5_next_operator_launch_state", "launch_state"),
        ("mt5_next_queue_step", "queue_step"),
        ("mt5_next_manual_run_start_effective_after", "manual_start_after"),
    ):
        value = watcher.get(key)
        if value not in ("", None, [], {}):
            action_parts.append(f"{label}={value}")
    if action_parts:
        lines.append(f"{prefix}{label_prefix}operator_next: {', '.join(action_parts)}")
    quick_text = mt5_quick_input_text(watcher.get("mt5_next_quick_input"))
    if quick_text:
        lines.append(f"{prefix}{label_prefix}operator_quick_input: {quick_text}")
    if watcher.get("mt5_next_step_operator_summary"):
        lines.append(
            f"{prefix}{label_prefix}operator_step_summary: "
            f"{watcher.get('mt5_next_step_operator_summary')}"
        )
    if watcher.get("mt5_next_step_collect_filter_summary"):
        lines.append(
            f"{prefix}{label_prefix}operator_collect_filter: "
            f"{watcher.get('mt5_next_step_collect_filter_summary')}"
        )
    auto_parts = []
    for key, label in (
        ("mt5_auto_launch_command_available", "available"),
        ("mt5_auto_launch_blocked", "blocked"),
    ):
        value = watcher.get(key)
        if value not in ("", None, [], {}):
            auto_parts.append(f"{label}={value}")
    blocked_reasons = watcher.get("mt5_auto_launch_blocked_reasons")
    if blocked_reasons:
        auto_parts.append(f"blockers={format_list_value(blocked_reasons)}")
    if watcher.get("mt5_auto_launch_command_text"):
        auto_parts.append(f"command={watcher.get('mt5_auto_launch_command_text')}")
    if auto_parts:
        lines.append(f"{prefix}{label_prefix}operator_auto_launch: {', '.join(auto_parts)}")
    decision_parts = []
    for key, label in (
        ("mt5_strategy_operator_decision_status", "status"),
        ("mt5_strategy_operator_decision_verdict", "verdict"),
        ("mt5_strategy_operator_decision_primary_blocker", "blocker"),
        ("mt5_strategy_operator_decision_next_action", "next_action"),
    ):
        value = watcher.get(key)
        if value not in ("", None, [], {}):
            decision_parts.append(f"{label}={value}")
    if watcher.get("mt5_strategy_operator_decision_command_text"):
        decision_parts.append(f"command={watcher.get('mt5_strategy_operator_decision_command_text')}")
    if decision_parts:
        lines.append(f"{prefix}{label_prefix}operator_decision: {', '.join(decision_parts)}")
    collect_parts = []
    if watcher.get("mt5_collect_dry_run_command_text"):
        collect_parts.append(f"dry_run={watcher.get('mt5_collect_dry_run_command_text')}")
    if watcher.get("mt5_collect_execute_command_text"):
        collect_parts.append(f"execute={watcher.get('mt5_collect_execute_command_text')}")
    if collect_parts:
        lines.append(f"{prefix}{label_prefix}operator_collect: {', '.join(collect_parts)}")
    queue_parts = []
    for key, label in (
        ("mt5_manual_queue_status", "status"),
        ("mt5_manual_queue_progress_state", "progress"),
        ("mt5_manual_queue_waiting_count", "waiting"),
        ("mt5_manual_queue_step_launch_needed_count", "launch_needed"),
    ):
        value = watcher.get(key)
        if value not in ("", None, [], {}):
            queue_parts.append(f"{label}={value}")
    if queue_parts:
        lines.append(f"{prefix}{label_prefix}operator_queue_alias: {', '.join(queue_parts)}")


def append_mt5_status_watch_manual_queue_lines(
    lines: list[str],
    watcher: dict[str, object],
    *,
    prefix: str = "  ",
    label_prefix: str = "mt5_status_watch_",
) -> None:
    append_mt5_status_watch_operator_alias_lines(
        lines,
        watcher,
        prefix=prefix,
        label_prefix=label_prefix,
    )
    manual_queue_parts = []
    for key, label in (
        ("manual_test_queue_status", "status"),
        ("manual_test_queue_next_action", "next_action"),
        ("manual_test_queue_entry_count", "entries"),
        ("manual_test_queue_total_entry_count", "total"),
        ("manual_test_queue_stale_entry_count", "stale"),
        ("manual_test_queue_current_for_execution_count", "current_exec"),
        ("manual_test_queue_selected_action_current_count", "action_current"),
        ("manual_test_queue_selected_action_stale_count", "action_stale"),
        ("manual_test_queue_step_count", "steps"),
        ("manual_test_queue_waiting_count", "waiting"),
        ("manual_test_queue_ready_to_collect_count", "ready"),
        ("manual_test_queue_step_report_ready_count", "step_ready"),
        ("manual_test_queue_step_waiting_report_count", "step_waiting"),
        ("manual_test_queue_step_launch_needed_count", "step_launch_needed"),
        ("manual_test_queue_all_collect_ready", "all_ready"),
    ):
        value = watcher.get(key)
        if value != "" and value is not None:
            manual_queue_parts.append(f"{label}={value}")
    manual_queue_blocking = watcher.get("manual_test_queue_blocking_reasons")
    if manual_queue_blocking:
        manual_queue_parts.append(f"blocking={format_list_value(manual_queue_blocking)}")
    manual_queue_current_gate = watcher.get("manual_test_queue_current_promotion_generated_at_values")
    if manual_queue_current_gate:
        manual_queue_parts.append(f"current_gate={format_list_value(manual_queue_current_gate)}")
    manual_queue_current_decisions = watcher.get("manual_test_queue_current_promotion_decision_values")
    if manual_queue_current_decisions:
        manual_queue_parts.append(f"current_decision={format_list_value(manual_queue_current_decisions)}")
    manual_queue_gate_stale = watcher.get("manual_test_queue_gate_stale_reasons")
    if manual_queue_gate_stale:
        manual_queue_parts.append(f"gate_stale={format_list_value(manual_queue_gate_stale)}")
    manual_queue_not_current = watcher.get("manual_test_queue_not_current_entry_ids")
    if manual_queue_not_current:
        manual_queue_parts.append(f"not_current={format_list_value(manual_queue_not_current)}")
    if manual_queue_parts:
        lines.append(f"{prefix}{label_prefix}manual_queue: {', '.join(manual_queue_parts)}")
    append_mt5_status_watch_manual_queue_operator_handoff_lines(
        lines,
        watcher,
        prefix=prefix,
        label_prefix=label_prefix,
    )
    append_mt5_status_watch_manual_queue_launch_handoff_lines(
        lines,
        watcher,
        prefix=prefix,
        label_prefix=label_prefix,
    )
    next_launch_step = watcher.get("manual_test_queue_next_launch_step")
    if isinstance(next_launch_step, dict) and next_launch_step:
        lines.append(
            f"{prefix}{label_prefix}manual_queue_next_step: "
            f"{next_launch_step.get('order', '')} "
            f"{next_launch_step.get('queue_id', '')}/{next_launch_step.get('step_label', '')}, "
            f"symbol={next_launch_step.get('symbol', '')}, "
            f"period={next_launch_step.get('period', '')}, "
            f"forward={next_launch_step.get('forward', '')}, "
            f"run_type={next_launch_step.get('run_type', '')}, "
            f"step_report={next_launch_step.get('step_report_status', '')}, "
            f"launch_kind={next_launch_step.get('launch_command_kind', '')}, "
            f"inputs={next_launch_step.get('inputs', '')}, "
            f"report={next_launch_step.get('report', '')}"
        )
    entries = watcher.get("manual_test_queue_entries")
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            stale_reasons = entry.get("stale_reasons")
            has_stale_reasons = bool(stale_reasons)
            gate_stale_reason = str(entry.get("gate_stale_reason") or "")
            refresh_command = str(entry.get("refresh_command_text") or "")
            current_for_execution = entry.get("current_for_execution", "")
            if not (
                has_stale_reasons
                or gate_stale_reason
                or refresh_command
                or current_for_execution is False
            ):
                continue
            runner_gate = entry.get("runner_promotion_generated_at") or entry.get("promotion_generated_at", "")
            lines.append(
                f"{prefix}{label_prefix}manual_queue_stale_entry "
                f"{entry.get('id', '')}: "
                f"current={current_for_execution}, "
                f"gate_stale={gate_stale_reason}, "
                f"runner_generated={entry.get('runner_generated_at', '')}, "
                f"gate_generated={runner_gate}, "
                f"current_gate={entry.get('current_promotion_generated_at', '')}, "
                f"decision={entry.get('promotion_decision', '')}, "
                f"reason={format_list_value(stale_reasons) if has_stale_reasons else gate_stale_reason}, "
                f"refresh={refresh_command}"
            )
    targets = watcher.get("manual_test_queue_strategy_tester_targets")
    if isinstance(targets, list):
        for item in targets:
            if not isinstance(item, dict):
                continue
            dates = item.get("dates") or f"{item.get('from_date', '')}->{item.get('to_date', '')}"
            start_after = item.get("start_after") or item.get("manual_run_start_after", "")
            lines.append(
                f"{prefix}{label_prefix}manual_queue_target "
                f"{item.get('order', '')}: "
                f"{item.get('purpose', '')}, "
                f"{item.get('queue_id', '')}/{item.get('step_label', '')}, "
                f"symbol={item.get('symbol', '')}, "
                f"period={item.get('period', '')}, "
                f"dates={dates}, "
                f"forward={item.get('forward', '')}, "
                f"run_type={item.get('run_type', '')}, "
                f"expected_report={item.get('expected_report_artifact', '')}, "
                f"report_note={item.get('report_expectation_note', '')}, "
                f"inputs={item.get('inputs', '')}, "
                f"report={item.get('report', '')}, "
                f"start_after={start_after}, "
                f"collect_after={item.get('collect_modified_after', '')}, "
                f"collect_status={item.get('collect_status', '')}, "
                f"step_report={item.get('step_report_status', '')}, "
                f"launch_needed={item.get('launch_needed', '')}, "
                f"auto_launch={item.get('auto_launch_kind', '')}"
            )
    cards = watcher.get("manual_test_queue_operation_cards")
    if isinstance(cards, list):
        for item in cards:
            if not isinstance(item, dict):
                continue
            next_mark = "next" if item.get("is_next") is True else ""
            lines.append(
                f"{prefix}{label_prefix}manual_queue_operation_card "
                f"{item.get('order', '')}: "
                f"{next_mark}, "
                f"action={item.get('action', '')}, "
                f"purpose={item.get('purpose', '')}, "
                f"{item.get('queue_id', '')}/{item.get('step_label', '')}, "
                f"forward={item.get('forward', '')}, "
                f"inputs={item.get('inputs', '')}, "
                f"report={item.get('report', '')}, "
                f"collect_status={item.get('collect_status', '')}"
            )
    checklist = watcher.get("manual_test_queue_execution_checklist")
    if not isinstance(checklist, list):
        return
    for item in checklist:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"{prefix}{label_prefix}manual_queue_checklist "
            f"{item.get('order', '')}: "
            f"{item.get('queue_id', '')}/{item.get('step_label', '')}, "
            f"symbol={item.get('symbol', '')}, "
            f"period={item.get('period', '')}, "
            f"forward={item.get('forward', '')}, "
            f"run_type={item.get('run_type', '')}, "
            f"expected_report={item.get('expected_report_artifact', '')}, "
            f"report_note={item.get('report_expectation_note', '')}, "
            f"step_report={item.get('step_report_status', '')}, "
            f"launch_needed={item.get('launch_needed', '')}, "
            f"inputs={item.get('inputs', '')}, "
            f"report={item.get('report', '')}, "
            f"start_after={item.get('manual_run_start_after', '')}"
        )
    for item in checklist:
        if not isinstance(item, dict):
            continue
        launch_text = manual_queue_launch_text(item)
        if not launch_text and not item.get("mt5_config"):
            continue
        lines.append(
            f"{prefix}{label_prefix}manual_queue_launch "
            f"{item.get('order', '')}: "
            f"{item.get('queue_id', '')}/{item.get('step_label', '')}, "
            f"kind={item.get('launch_command_kind', '')}, "
            f"workspace_config={item.get('config', '')}, "
            f"mt5_config={item.get('mt5_config', '')}, "
            f"command={launch_text}"
        )


def append_mt5_operator_summary_lines(
    lines: list[str],
    operator_summary: dict[str, object],
    *,
    prefix: str = "- ",
) -> None:
    parts = []
    for key, label in (
        ("operational_status", "status"),
        ("ready_for_tester_launch", "ready"),
        ("manual_test_queue_status", "manual_queue_status"),
        ("manual_test_queue_next_action", "queue_action"),
        ("manual_test_queue_entry_count", "entries"),
        ("manual_test_queue_step_count", "steps"),
        ("manual_test_queue_waiting_count", "waiting"),
        ("manual_test_queue_step_report_ready_count", "step_ready"),
        ("manual_test_queue_step_launch_needed_count", "launch_needed"),
        ("manual_strategy_tester_recommended", "manual_tester"),
        ("manual_queue_launch_status", "launch_status"),
        ("manual_queue_launch_next_action", "launch_action"),
        ("manual_queue_launch_launch_command_kind", "launch_kind"),
        ("manual_collect_run_status", "collect_status"),
        ("manual_collect_run_selected_count", "collect_selected"),
        ("manual_collect_run_waiting_count", "collect_waiting"),
    ):
        value = operator_summary.get(key)
        if value != "" and value is not None:
            parts.append(f"{label}={value}")
    blocked_reasons = operator_summary.get("manual_queue_launch_blocked_reasons")
    if blocked_reasons:
        parts.append(f"blocked={format_list_value(blocked_reasons)}")
    if parts:
        lines.append(f"{prefix}operator_summary: {', '.join(parts)}")

    quick_input = operator_summary.get("mt5_operator_handoff_quick_input")
    if not isinstance(quick_input, dict) or not quick_input:
        quick_input = operator_summary.get("manual_test_queue_quick_input")
    if not isinstance(quick_input, dict) or not quick_input:
        quick_input = operator_summary.get("manual_queue_launch_queue_operator_handoff_quick_input")
    quick_text = mt5_quick_input_text(quick_input)
    if quick_text:
        lines.append(f"{prefix}operator_summary_quick_input: {quick_text}")

    next_action_parts = []
    for key, label in (
        ("next_action_run_target", "target"),
        ("next_action_run_kind", "kind"),
        ("next_action_run_focus_side", "side"),
        ("next_action_run_optimization_mode", "mode"),
        ("next_action_run_config", "config"),
        ("next_action_run_set", "set"),
        ("next_action_run_current_for_execution", "current"),
        ("next_action_run_primary_execution_class", "primary"),
        ("next_action_run_timeout_minutes", "timeout_min"),
        ("next_action_run_timeout_deadline_if_started_now", "deadline_if_started_now"),
        ("next_action_run_optimized_input_count", "optimized_inputs"),
        ("next_action_run_estimated_full_factorial_passes", "passes"),
    ):
        value = operator_summary.get(key)
        if value != "" and value is not None:
            next_action_parts.append(f"{label}={value}")
    primary_outputs = operator_summary.get("next_action_run_primary_planned_outputs")
    if isinstance(primary_outputs, dict):
        output_json = primary_outputs.get("output_json")
        optimization_json = primary_outputs.get("optimization_output_json")
        recommendation_json = primary_outputs.get("recommendation_output_json")
        if output_json:
            next_action_parts.append(f"output_json={output_json}")
        if optimization_json:
            next_action_parts.append(f"optimization_json={optimization_json}")
        if recommendation_json:
            next_action_parts.append(f"recommendation_json={recommendation_json}")
    recent_rows = operator_summary.get("next_action_run_latest_executed_tester_xml_rows")
    if isinstance(recent_rows, dict):
        row_parts = []
        if recent_rows.get("back") is not None:
            row_parts.append(f"back={recent_rows.get('back')}")
        if recent_rows.get("forward") is not None:
            row_parts.append(f"forward={recent_rows.get('forward')}")
        if row_parts:
            suffix_parts = []
            ratio_text = recent_xml_row_ratio_text(recent_rows.get("ratio_vs_full_factorial"))
            if ratio_text:
                suffix_parts.append(f"ratio_vs_full_factorial={ratio_text}")
            source_text = str(recent_rows.get("source") or "")
            if source_text:
                suffix_parts.append(f"source={source_text}")
            suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
            next_action_parts.append(f"xml_rows={'; '.join(row_parts)}{suffix}")
    if next_action_parts:
        lines.append(f"{prefix}operator_summary_next_action_run: {', '.join(next_action_parts)}")

    execute_hint = str(operator_summary.get("next_action_run_execute_command_text") or "")
    collect_only_hint = str(operator_summary.get("next_action_run_collect_only_command_text") or "")
    if execute_hint or collect_only_hint:
        lines.append(
            f"{prefix}operator_summary_next_action_commands: "
            f"execute={execute_hint}, collect_only={collect_only_hint}"
        )

    next_step = operator_summary.get("manual_test_queue_next_launch_step")
    if not isinstance(next_step, dict) or not next_step:
        next_step = operator_summary.get("manual_queue_launch_queue_operator_handoff_next_mt5_step")
    if isinstance(next_step, dict) and next_step:
        dates = next_step.get("dates") or f"{next_step.get('from_date', '')}->{next_step.get('to_date', '')}"
        order = next_step.get("order", "")
        order_text = f"{order} " if order != "" and order is not None else ""
        lines.append(
            f"{prefix}operator_summary_next_step: "
            f"{order_text}{next_step.get('queue_id', '')}/{next_step.get('step_label', '')}, "
            f"symbol={next_step.get('symbol', '')}, "
            f"period={next_step.get('period', '')}, "
            f"dates={dates}, "
            f"forward={next_step.get('forward', '')}, "
            f"run_type={next_step.get('run_type', '')}, "
            f"inputs={next_step.get('inputs', '')}, "
            f"report={next_step.get('report', '')}"
        )

    dry_run = str(
        operator_summary.get("manual_queue_launch_queue_operator_handoff_collect_dry_run_command_text") or ""
    )
    execute = str(
        operator_summary.get("manual_queue_launch_queue_operator_handoff_collect_execute_command_text") or ""
    )
    execute_and_refresh = str(
        operator_summary.get(
            "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_analysis_command_text"
        )
        or operator_summary.get("manual_collect_execute_and_refresh_analysis_command_text")
        or ""
    )
    execute_and_refresh_all = str(
        operator_summary.get(
            "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_all_command_text"
        )
        or operator_summary.get("manual_collect_execute_and_refresh_all_command_text")
        or ""
    )
    if dry_run or execute or execute_and_refresh or execute_and_refresh_all:
        lines.append(
            f"{prefix}operator_summary_collect: dry_run={dry_run}, execute={execute}, "
            f"execute_and_refresh_analysis={execute_and_refresh}, "
            f"execute_and_refresh_all={execute_and_refresh_all}"
        )

    optimization_parts = []
    for key, label in (
        ("manual_test_queue_with_optimization_status", "queue_status"),
        ("manual_test_queue_with_optimization_next_action", "queue_action"),
        ("manual_test_queue_with_optimization_entry_count", "entries"),
        ("manual_test_queue_with_optimization_step_count", "steps"),
        ("manual_test_queue_with_optimization_waiting_count", "waiting"),
        ("manual_queue_launch_with_optimization_status", "launch_status"),
        ("manual_collect_with_optimization_status", "collect_status"),
        ("manual_collect_with_optimization_selected_count", "collect_selected"),
        ("manual_collect_with_optimization_waiting_count", "collect_waiting"),
    ):
        value = operator_summary.get(key)
        if value != "" and value is not None:
            optimization_parts.append(f"{label}={value}")
    optimization_blocked = operator_summary.get("manual_queue_launch_with_optimization_blocked_reasons")
    if optimization_blocked:
        optimization_parts.append(f"blocked={format_list_value(optimization_blocked)}")
    if optimization_parts:
        lines.append(f"{prefix}operator_summary_optimization: {', '.join(optimization_parts)}")

    optimization_next_step = operator_summary.get("manual_test_queue_with_optimization_next_launch_step")
    if not isinstance(optimization_next_step, dict) or not optimization_next_step:
        optimization_next_step = operator_summary.get(
            "manual_queue_launch_with_optimization_queue_operator_handoff_next_mt5_step"
        )
    if isinstance(optimization_next_step, dict) and optimization_next_step:
        dates = optimization_next_step.get("dates") or (
            f"{optimization_next_step.get('from_date', '')}->{optimization_next_step.get('to_date', '')}"
        )
        order = optimization_next_step.get("order", "")
        order_text = f"{order} " if order != "" and order is not None else ""
        lines.append(
            f"{prefix}operator_summary_optimization_next_step: "
            f"{order_text}{optimization_next_step.get('queue_id', '')}/"
            f"{optimization_next_step.get('step_label', '')}, "
            f"symbol={optimization_next_step.get('symbol', '')}, "
            f"period={optimization_next_step.get('period', '')}, "
            f"dates={dates}, "
            f"forward={optimization_next_step.get('forward', '')}, "
            f"run_type={optimization_next_step.get('run_type', '')}, "
            f"inputs={optimization_next_step.get('inputs', '')}, "
            f"report={optimization_next_step.get('report', '')}"
        )

    optimization_dry_run = str(
        operator_summary.get(
            "manual_queue_launch_with_optimization_queue_operator_handoff_collect_dry_run_command_text"
        )
        or ""
    )
    optimization_execute = str(
        operator_summary.get(
            "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_command_text"
        )
        or ""
    )
    optimization_execute_and_refresh = str(
        operator_summary.get(
            "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_analysis_command_text"
        )
        or ""
    )
    optimization_execute_and_refresh_all = str(
        operator_summary.get(
            "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_all_command_text"
        )
        or ""
    )
    if (
        optimization_dry_run
        or optimization_execute
        or optimization_execute_and_refresh
        or optimization_execute_and_refresh_all
    ):
        lines.append(
            f"{prefix}operator_summary_optimization_collect: "
            f"dry_run={optimization_dry_run}, execute={optimization_execute}, "
            f"execute_and_refresh_analysis={optimization_execute_and_refresh}, "
            f"execute_and_refresh_all={optimization_execute_and_refresh_all}"
        )


def append_mt5_status_watch_execution_lines(
    lines: list[str],
    actions: list[dict[str, object]],
    execution: dict[str, object],
) -> None:
    if execution.get("kind") != "mt5_status_watch_restart":
        return
    for action in actions:
        if action.get("area") != "mt5_status_watch":
            continue
        evidence = action.get("evidence")
        if not isinstance(evidence, dict):
            continue
        watcher = (
            evidence.get("status_watch_heartbeat")
            if isinstance(evidence.get("status_watch_heartbeat"), dict)
            else {}
        )
        lines.append(
            "  mt5_status_watch: "
            f"status={watcher.get('status', '')}, fresh={watcher.get('fresh', '')}, "
            f"compatible={watcher.get('compatible', '')}, pid={watcher.get('watcher_pid', '')}"
        )
        schema_parts = []
        if watcher.get("implementation_version") != "":
            schema_parts.append(f"implementation_version={watcher.get('implementation_version')}")
        if watcher.get("expected_implementation_version") != "":
            schema_parts.append(f"expected={watcher.get('expected_implementation_version')}")
        if watcher.get("implementation_version_mismatch") != "":
            schema_parts.append(f"mismatch={watcher.get('implementation_version_mismatch')}")
        if schema_parts:
            lines.append(f"  mt5_status_watch_schema: {', '.join(schema_parts)}")
        append_mt5_status_watch_manual_queue_lines(lines, watcher)
        runner_parts = []
        if watcher.get("next_action_run_current_for_execution") != "":
            runner_parts.append(f"current_for_execution={watcher.get('next_action_run_current_for_execution')}")
        if watcher.get("next_action_run_gate_stale_reason"):
            runner_parts.append(f"gate_stale_reason={watcher.get('next_action_run_gate_stale_reason')}")
        if watcher.get("next_action_run_runner_promotion_generated_at"):
            runner_parts.append(f"runner_gate={watcher.get('next_action_run_runner_promotion_generated_at')}")
        if watcher.get("next_action_run_current_promotion_generated_at"):
            runner_parts.append(f"current_gate={watcher.get('next_action_run_current_promotion_generated_at')}")
        if watcher.get("next_action_run_blocking_prior_action_count") != "":
            runner_parts.append(
                f"blocking_prior={watcher.get('next_action_run_blocking_prior_action_count')}"
            )
        if watcher.get("next_action_run_blocking_prior_action_summary"):
            runner_parts.append(
                f"blocking_prior_summary={watcher.get('next_action_run_blocking_prior_action_summary')}"
            )
        if runner_parts:
            lines.append(f"  mt5_status_watch_runner: {', '.join(runner_parts)}")
        blocking_prior_actions = (
            watcher.get("next_action_run_blocking_prior_actions")
            if isinstance(watcher.get("next_action_run_blocking_prior_actions"), list)
            else []
        )
        for index, row in enumerate(blocking_prior_actions[:3], start=1):
            if not isinstance(row, dict):
                continue
            lines.append(
                "  mt5_status_watch_blocking_prior_action: "
                f"{index}. P{row.get('priority', '')} {row.get('area', '')}:{row.get('action', '')}, "
                f"command={row.get('command_text', '')}"
            )
        archive_json = watcher.get("next_action_run_archive_preview_output_json")
        follow_up_archive_json = watcher.get("next_action_run_follow_up_archive_preview_output_json")
        archive_parts = []
        if archive_json:
            archive_parts.append(f"archive_json={archive_json}")
        if follow_up_archive_json:
            archive_parts.append(f"follow_up_archive_json={follow_up_archive_json}")
        if archive_parts:
            lines.append(f"  mt5_status_watch_archive_outputs: {', '.join(archive_parts)}")
        planned_output_parts = []
        for label, key in (
            ("primary", "next_action_run_primary_planned_outputs"),
            ("archive", "next_action_run_archive_preview_planned_outputs"),
            ("follow_up", "next_action_run_follow_up_planned_outputs"),
            ("follow_up_archive", "next_action_run_follow_up_archive_preview_planned_outputs"),
        ):
            outputs = watcher.get(key) if isinstance(watcher.get(key), dict) else {}
            output_json = outputs.get("output_json", "")
            if output_json:
                planned_output_parts.append(f"{label}={output_json}")
        if planned_output_parts:
            lines.append(f"  mt5_status_watch_planned_outputs: {', '.join(planned_output_parts)}")
        back_forward_archive_json = watcher.get("back_forward_run_archive_preview_output_json")
        back_forward_by_step = (
            watcher.get("back_forward_run_archive_preview_output_json_by_step")
            if isinstance(watcher.get("back_forward_run_archive_preview_output_json_by_step"), dict)
            else {}
        )
        back_forward_preview_parts = []
        if back_forward_archive_json:
            back_forward_preview_parts.append(f"archive_json={back_forward_archive_json}")
        for label, output_json in back_forward_by_step.items():
            if output_json:
                back_forward_preview_parts.append(f"{label}={output_json}")
        if back_forward_preview_parts:
            lines.append(
                "  mt5_status_watch_back_forward_archive_outputs: "
                + ", ".join(str(part) for part in back_forward_preview_parts)
            )
        condition_parts = []
        for key in MT5_BACK_FORWARD_WATCHER_CONDITION_KEYS:
            if key == "back_forward_run_execution_conditions":
                continue
            value = watcher.get(key)
            if value != "" and value is not None:
                condition_parts.append(f"{key.removeprefix('back_forward_run_')}={value}")
        if condition_parts:
            lines.append("  mt5_status_watch_back_forward_conditions: " + ", ".join(condition_parts))
        comparison_parts = []
        comparison_available = watcher.get("back_forward_run_performance_comparison_available")
        if comparison_available != "" and comparison_available is not None:
            comparison_parts.append(f"available={comparison_available}")
        comparison_status = watcher.get("back_forward_run_performance_comparison_status")
        if comparison_status:
            comparison_parts.append(f"status={comparison_status}")
        comparison_rows = watcher.get("back_forward_run_performance_comparison_rows")
        if isinstance(comparison_rows, list):
            comparison_parts.append(f"rows={len(comparison_rows)}")
        elif comparison_rows != "" and comparison_rows is not None:
            comparison_parts.append(f"rows={comparison_rows}")
        if comparison_parts:
            lines.append("  mt5_status_watch_back_forward_comparison: " + ", ".join(comparison_parts))
        thresholds = watcher.get("back_forward_run_performance_comparison_thresholds")
        if isinstance(thresholds, dict) and thresholds:
            lines.append(
                "  mt5_status_watch_back_forward_thresholds: "
                + ", ".join(f"{key}={value}" for key, value in thresholds.items())
            )
        failed_checks = evidence.get("failed_checks") if isinstance(evidence.get("failed_checks"), dict) else {}
        next_current_check = (
            failed_checks.get("mt5_status_watch_next_action_current")
            if isinstance(failed_checks.get("mt5_status_watch_next_action_current"), dict)
            else {}
        )
        next_current_value = next_current_check.get("value") if isinstance(next_current_check.get("value"), dict) else {}
        next_current_mismatches = (
            next_current_value.get("mismatches") if isinstance(next_current_value, dict) else []
        )
        if next_current_mismatches:
            watcher_values = (
                next_current_value.get("watcher") if isinstance(next_current_value.get("watcher"), dict) else {}
            )
            expected_values = (
                next_current_value.get("expected") if isinstance(next_current_value.get("expected"), dict) else {}
            )
            lines.append(
                "  mt5_status_watch_next_action_current: "
                f"mismatches={format_list_value(next_current_mismatches)}, "
                f"watcher_target={watcher_values.get('target', '')}, "
                f"expected_target={expected_values.get('target', '')}, "
                f"watcher_config={watcher_values.get('config', '')}, "
                f"expected_config={expected_values.get('config', '')}, "
                f"watcher_runner_gate={watcher_values.get('runner_promotion_generated_at', '')}, "
                f"expected_runner_gate={expected_values.get('runner_promotion_generated_at', '')}, "
                f"watcher_archive_run_id={watcher_values.get('archive_run_id', '')}, "
                f"expected_archive_run_id={expected_values.get('archive_run_id', '')}"
            )
        current_check = (
            failed_checks.get("mt5_status_watch_back_forward_current")
            if isinstance(failed_checks.get("mt5_status_watch_back_forward_current"), dict)
            else {}
        )
        current_value = current_check.get("value") if isinstance(current_check.get("value"), dict) else {}
        current_mismatches = current_value.get("mismatches") if isinstance(current_value, dict) else []
        if current_mismatches:
            lines.append(
                "  mt5_status_watch_back_forward_current: "
                f"mismatches={format_list_value(current_mismatches)}, "
                f"watcher_run_id_prefix={current_value.get('watcher_run_id_prefix', '')}, "
                f"expected_run_id_prefix={current_value.get('expected_run_id_prefix', '')}, "
                f"watcher_forward_mode={current_value.get('watcher_forward_mode', '')}, "
                f"expected_forward_mode={current_value.get('expected_forward_mode', '')}"
            )
        preflight_parts = []
        ready_ok = watcher.get("back_forward_run_ready_status_ok")
        if ready_ok != "" and ready_ok is not None:
            preflight_parts.append(f"ok={ready_ok}")
        ready_reasons = watcher.get("back_forward_run_ready_status_reasons")
        if ready_reasons:
            preflight_parts.append(f"reasons={format_list_value(ready_reasons)}")
        ready_mismatches = watcher.get("back_forward_run_ready_status_mismatches")
        if ready_mismatches:
            preflight_parts.append(f"mismatches={format_list_value(ready_mismatches)}")
        checked_step_keys = watcher.get("back_forward_run_ready_status_checked_step_keys")
        if checked_step_keys:
            preflight_parts.append(f"checked_step_keys={format_list_value(checked_step_keys)}")
        checked_options = watcher.get("back_forward_run_ready_status_checked_command_options")
        if checked_options:
            preflight_parts.append(f"checked_options={format_list_value(checked_options)}")
        checked_flags = watcher.get("back_forward_run_ready_status_checked_command_flags")
        if checked_flags:
            preflight_parts.append(f"checked_flags={format_list_value(checked_flags)}")
        checked_conditions = watcher.get("back_forward_run_ready_status_checked_execution_conditions")
        if checked_conditions:
            preflight_parts.append(f"checked_execution_conditions={format_list_value(checked_conditions)}")
        expected_conditions = watcher.get("back_forward_run_ready_status_expected_execution_conditions")
        if isinstance(expected_conditions, dict) and expected_conditions:
            preflight_parts.append(f"expected_execution_conditions={expected_conditions}")
        status_conditions = watcher.get("back_forward_run_ready_status_status_execution_conditions")
        if isinstance(status_conditions, dict) and status_conditions:
            preflight_parts.append(f"status_execution_conditions={status_conditions}")
        if preflight_parts:
            lines.append("  mt5_status_watch_back_forward_preflight: " + ", ".join(preflight_parts))
        missing = watcher.get("missing_required_fields")
        if isinstance(missing, list) and missing:
            lines.append(f"  mt5_status_watch_missing: {format_list_value(missing)}")
        restart_hint = watcher.get("restart_hint")
        if restart_hint:
            lines.append(f"  mt5_status_watch_restart_hint: {restart_hint}")
        return


def append_winrate_fit_execution_lines(
    lines: list[str],
    action: dict[str, object],
    execution: dict[str, object],
) -> None:
    if execution.get("kind") != "winrate_fit_walk_forward":
        return
    if action.get("area") != "winrate_fit":
        return
    evidence = action.get("evidence")
    failed_checks = evidence.get("failed_checks") if isinstance(evidence, dict) else None
    if not isinstance(failed_checks, dict):
        return
    adoption = failed_checks.get("winrate_fit_adoption_decision")
    if not isinstance(adoption, dict) and isinstance(evidence, dict):
        winrate_fit = evidence.get("winrate_fit")
        adoption_value = winrate_fit.get("adoption_decision") if isinstance(winrate_fit, dict) else None
        if isinstance(adoption_value, dict):
            adoption = {
                "value": {
                    "adopted": adoption_value.get("adopted"),
                    "reasons": adoption_value.get("reasons"),
                    "rules": adoption_value.get("rules"),
                },
                "requirement": "adoption_decision.adopted = true",
            }
    if isinstance(adoption, dict):
        value = adoption.get("value")
        if isinstance(value, dict):
            parts = [
                f"adopted={value.get('adopted')}",
                f"rules={value.get('rules')}",
                f"reasons={value.get('reasons')}",
            ]
            lines.append(f"  winrate_adoption: {', '.join(parts)}")
        else:
            lines.append(f"  winrate_adoption: value={value}, requirement={adoption.get('requirement')}")
    walk = failed_checks.get("winrate_fit_walk_forward")
    if not isinstance(walk, dict):
        return
    value = walk.get("value")
    if not isinstance(value, dict):
        lines.append(f"  winrate_walk_gap: value={value}, requirement={walk.get('requirement')}")
        return
    total_count = number(value.get("total_test_fitted_count"))
    required_count = number(value.get("min_required_count"))
    missing_count = max(required_count - total_count, 0.0)
    parts = [
        f"folds={format_number_like(value.get('folds'))}",
        f"folds_with_trades={format_number_like(value.get('folds_with_trades'))}",
        f"fitted_count={format_number_like(total_count)}/{format_number_like(required_count)}",
        f"missing={format_number_like(missing_count)}",
        f"min_fold_count={format_number_like(value.get('min_test_fitted_count'))}",
        f"mean_avg_r={format_number_like(value.get('mean_test_fitted_avg_r'))}/>= {format_number_like(value.get('min_required_avg_r'))}",
        f"mean_pf={format_number_like(value.get('mean_test_fitted_pf'))}/>= {format_number_like(value.get('min_required_pf'))}",
    ]
    lines.append(f"  winrate_walk_gap: {', '.join(parts)}")


def split_risk_shape_check_name(name: str) -> tuple[str, str]:
    prefixes = (
        ("mt5_yearly_optimization_", "mt5_yearly_optimization"),
        ("mt5_optimization_", "mt5_optimization"),
        ("mt5_forward_", "mt5_forward"),
        ("forward_", "python_forward"),
        ("backtest_", "backtest"),
    )
    for prefix, label in prefixes:
        if name.startswith(prefix):
            return label, name[len(prefix) :]
    return "unknown", name


def append_risk_shape_execution_lines(
    lines: list[str],
    action: dict[str, object],
    execution: dict[str, object],
) -> None:
    if execution.get("kind") != "risk_shape_refit":
        return
    if action.get("area") != "risk_shape":
        return
    evidence = action.get("evidence")
    failed_checks = evidence.get("failed_checks") if isinstance(evidence, dict) else None
    if not isinstance(failed_checks, dict):
        return
    grouped: dict[str, list[str]] = {}
    for check_name, row in failed_checks.items():
        if not isinstance(row, dict):
            continue
        dataset, metric = split_risk_shape_check_name(str(check_name))
        grouped.setdefault(dataset, []).append(
            f"{metric}={format_number_like(row.get('value'))}/{row.get('requirement')}"
        )
    for dataset in (
        "backtest",
        "python_forward",
        "mt5_forward",
        "mt5_optimization",
        "mt5_yearly_optimization",
        "unknown",
    ):
        parts = grouped.get(dataset)
        if parts:
            lines.append(f"  risk_shape_gap: {dataset} {' '.join(parts)}")
    weight_search = evidence.get("weight_search") if isinstance(evidence, dict) else None
    if isinstance(weight_search, dict) and weight_search:
        candidate = format_score_weight_candidate(weight_search.get("top_weight_candidate"))
        if candidate != "None":
            lines.append(f"  risk_shape_weight_top: {candidate}")
        diagnostics = format_score_weight_diagnostics(weight_search.get("diagnostics"))
        if diagnostics != "None":
            lines.append(f"  risk_shape_weight_delta: {diagnostics}")


def append_source_time_gap_execution_lines(
    lines: list[str],
    action: dict[str, object],
    execution: dict[str, object],
) -> None:
    if execution.get("kind") == "mt5_agent_csv_archive":
        return
    evidence = action.get("evidence")
    failed_check = evidence.get("failed_check") if isinstance(evidence, dict) else None
    if not isinstance(failed_check, dict):
        return
    if "source_time_range" not in str(failed_check.get("name") or ""):
        return
    value = failed_check.get("value")
    if not isinstance(value, dict):
        lines.append(f"  source_time_gap: value={value}, requirement={failed_check.get('requirement')}")
        return
    expected_from = value.get("expected_from_date")
    expected_to = value.get("expected_to_date")
    actual_first = value.get("actual_first_server_time")
    actual_last = value.get("actual_last_server_time")
    parts = [
        f"expected={expected_from}..{expected_to}",
        f"actual={actual_first}..{actual_last}",
        f"matches={value.get('matches_expected_range')}",
    ]
    if value.get("close_rows_with_server_time") is not None:
        parts.append(f"with_server_time={format_number_like(value.get('close_rows_with_server_time'))}")
    if value.get("close_rows_without_server_time") is not None:
        parts.append(f"without_server_time={format_number_like(value.get('close_rows_without_server_time'))}")
    lines.append(f"  source_time_gap: {', '.join(parts)}")
    warnings = value.get("warnings")
    if isinstance(warnings, list) and warnings:
        lines.append(f"  source_time_warnings: {format_warning_list(warnings)}")


def format_segment_brief(row: dict[str, object]) -> str:
    period = ""
    if row.get("start_time") or row.get("end_time"):
        period = f", period={row.get('start_time', '')}..{row.get('end_time', '')}"
    diagnosis = f", diagnosis={row.get('diagnosis')}" if row.get("diagnosis") else ""
    return (
        f"{row.get('group')}: closed={row.get('closed')}, pf={row.get('pf')}, "
        f"avg_price_r={row.get('avg_price_r')}, net_profit={row.get('net_profit')}"
        f"{period}{diagnosis}"
    )


def format_segment_brief_rows(rows: object, *, limit: int = 3) -> str:
    if not isinstance(rows, list) or not rows:
        return "None"
    parts = []
    for row in rows:
        if isinstance(row, dict):
            parts.append(format_segment_brief(row))
        if len(parts) >= limit:
            break
    return "; ".join(parts) if parts else "None"


def append_chronological_failure_execution_lines(
    lines: list[str],
    action: dict[str, object],
    execution: dict[str, object],
) -> None:
    if action.get("action") != "reject_chronologically_unstable_optimization":
        return
    if execution.get("kind") not in {"mt5_yearly_validation", "mt5_optimization_recommendation_refresh"}:
        return
    evidence = action.get("evidence")
    failed_splits = evidence.get("failed_splits") if isinstance(evidence, dict) else None
    if not isinstance(failed_splits, list) or not failed_splits:
        return
    appended = 0
    for row in failed_splits:
        if not isinstance(row, dict):
            continue
        lines.append(f"  chronological_failure: {format_segment_brief(row)}")
        appended += 1
        if appended >= 4:
            break
    for key, label in (
        ("weak_time_segments", "weak_time"),
        ("weak_trend_segments", "weak_trend"),
        ("weak_sl_tp_segments", "weak_sl_tp"),
    ):
        rows = evidence.get(key) if isinstance(evidence, dict) else None
        if isinstance(rows, list) and rows:
            lines.append(f"  chronological_{label}: {format_segment_brief_rows(rows, limit=3)}")


def format_tester_pass_brief(row: dict[str, object]) -> str:
    return (
        f"pass={row.get('Pass')}, forward={row.get('Forward Result')}, back={row.get('Back Result')}, "
        f"pf={row.get('Profit Factor')}, trades={row.get('Trades')}, "
        f"buy_rr={row.get('InpBuyRiskReward')}, sell_rr={row.get('InpSellRiskReward')}, "
        f"score={row.get('InpMinScore')}, depth={row.get('InpSwingDepth')}, "
        f"atr_band={row.get('InpSwingAtrBand')}, stop_buffer={row.get('InpStopBufferPoints')}"
    )


def append_stable_pass_execution_lines(
    lines: list[str],
    action: dict[str, object],
    execution: dict[str, object],
) -> None:
    if action.get("action") != "use_stable_back_forward_passes_for_next_search":
        return
    if execution.get("kind") == "mt5_agent_csv_archive":
        return
    evidence = action.get("evidence")
    if not isinstance(evidence, dict):
        return
    top_forward = evidence.get("top_forward")
    if isinstance(top_forward, dict) and top_forward:
        lines.append(f"  forward_only_top: {format_tester_pass_brief(top_forward)}")
    stable_rows = evidence.get("stable_forward_passes")
    if isinstance(stable_rows, list) and stable_rows:
        appended = 0
        for row in stable_rows:
            if not isinstance(row, dict):
                continue
            lines.append(f"  stable_pass_hint: {format_tester_pass_brief(row)}")
            appended += 1
            if appended >= 4:
                break
    else:
        top_stable = evidence.get("top_stable_forward")
        if isinstance(top_stable, dict) and top_stable:
            lines.append(f"  stable_pass_hint: {format_tester_pass_brief(top_stable)}")


def append_mt5_optimization_gap_execution_lines(
    lines: list[str],
    actions: list[dict[str, object]],
    execution: dict[str, object],
) -> None:
    if execution.get("kind") not in {
        "next_optimization",
        "buy_refit",
        "buy_entry_refit",
        "buy_hour03_validation",
        "buy_hour03_wide_stop_validation",
        "buy_hour03_wide_stop_calendar_validation",
        "sell_regime_entry_refit",
        "mt5_optimization_report_refresh",
        "mt5_optimization_recommendation_refresh",
    }:
        return
    for action in actions:
        evidence = action.get("evidence")
        failed_checks = evidence.get("failed_checks") if isinstance(evidence, dict) else None
        if not isinstance(failed_checks, dict):
            continue
        overall_parts = []
        for check_name, label in (
            ("mt5_optimization_closed_count", "closed"),
            ("mt5_optimization_pf", "pf"),
        ):
            row = failed_checks.get(check_name)
            if isinstance(row, dict):
                overall_parts.append(f"{label}={format_number_like(row.get('value'))}/{row.get('requirement')}")
        if overall_parts:
            lines.append(f"  mt5_optimization_gap: {', '.join(overall_parts)}")
        side_parts = []
        for side in ("buy", "sell"):
            side_metrics = []
            for suffix, label in (
                ("closed_count", "closed"),
                ("pf", "pf"),
                ("avg_price_r", "avg_price_r"),
            ):
                row = failed_checks.get(f"mt5_optimization_{side}_{suffix}")
                if isinstance(row, dict):
                    side_metrics.append(f"{label}={format_number_like(row.get('value'))}/{row.get('requirement')}")
            if side_metrics:
                side_parts.append(f"{side} {' '.join(side_metrics)}")
        if side_parts:
            lines.append(f"  mt5_optimization_side_gap: {'; '.join(side_parts)}")
        balance = failed_checks.get("mt5_optimization_side_total_price_r_balance")
        balance_appended = False
        if isinstance(balance, dict):
            lines.append(
                "  mt5_optimization_side_balance: "
                f"{format_mapping_value(balance.get('value'))}/{balance.get('requirement')}"
            )
            balance_appended = True
        if overall_parts or side_parts or balance_appended:
            return


def append_sl_tp_segment_execution_lines(
    lines: list[str],
    actions: list[dict[str, object]],
    execution: dict[str, object],
) -> None:
    if execution.get("kind") != "next_optimization":
        return
    for action in actions:
        if action.get("area") != "sell_sl_tp":
            continue
        evidence = action.get("evidence")
        if not isinstance(evidence, dict):
            continue
        appended_counts = {"best": 0, "weak": 0}
        for evidence_key, label in (("best_segments", "sl_tp_best"), ("weak_segments", "sl_tp_weak")):
            segments = evidence.get(evidence_key)
            if not isinstance(segments, list):
                continue
            appended = 0
            for row in segments:
                if not isinstance(row, dict):
                    continue
                lines.append(f"  {label}: {format_segment_brief(row)}")
                appended += 1
                if appended >= 3:
                    break
            if evidence_key == "best_segments":
                appended_counts["best"] = appended
            else:
                appended_counts["weak"] = appended
        missing_labels = [label for label, count in appended_counts.items() if count == 0]
        if missing_labels:
            summary = evidence.get("segment_side_summary")
            summary = summary if isinstance(summary, dict) else {}
            focus_side = evidence.get("focus_side") or execution.get("focus_side")
            parts = [
                f"focus={focus_side}",
                f"missing={format_list_value(missing_labels)}",
                f"best_counts={format_mapping_value(summary.get('best_counts'))}",
                f"weak_counts={format_mapping_value(summary.get('weak_counts'))}",
                "action=rerun focused side optimization or regenerate side-specific SL/TP segments",
            ]
            lines.append(f"  sl_tp_segment_gap: {', '.join(parts)}")
        return


def append_performance_comparison_lines(lines: list[str], rows: object) -> None:
    if not isinstance(rows, list) or not rows:
        lines.append("| None |  |  |  |  |  |  |  |  |  |")
        return
    appended = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {dataset} | {trades} | {pf} | {pf_delta} | {avg_r} | {avg_r_delta} | "
            "{expectancy_r} | {expectancy_delta} | {max_dd_r} | {max_dd_delta} |".format(
                dataset=row.get("dataset", ""),
                trades=format_optional_cell(row.get("trades")),
                pf=format_optional_cell(row.get("pf")),
                pf_delta=format_optional_cell(row.get("pf_delta_vs_backtest")),
                avg_r=format_optional_cell(row.get("avg_r")),
                avg_r_delta=format_optional_cell(row.get("avg_r_delta_vs_backtest")),
                expectancy_r=format_optional_cell(row.get("expectancy_r")),
                expectancy_delta=format_optional_cell(row.get("expectancy_r_delta_vs_backtest")),
                max_dd_r=format_optional_cell(row.get("max_drawdown_r")),
                max_dd_delta=format_optional_cell(row.get("max_drawdown_r_delta_vs_backtest")),
            )
        )
        appended += 1
    if appended == 0:
        lines.append("| None |  |  |  |  |  |  |  |  |  |")


def append_mt5_back_forward_comparison_lines(lines: list[str], rows: object) -> None:
    if not isinstance(rows, list) or not rows:
        lines.append("| None |  |  |  |  |  |  |  |  |  |  |  |  |")
        return
    appended = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {dataset} | {trades} | {min_ok} | {pf} | {avg_r} | {expectancy_r} | {max_dd_r} | {net_profit} | "
            "{trades_delta} | {pf_delta} | {avg_r_delta} | {max_dd_delta} | {net_delta} |".format(
                dataset=row.get("dataset", ""),
                trades=format_optional_cell(row.get("trades")),
                min_ok=format_optional_cell(row.get("meets_min_closed")),
                pf=format_optional_cell(row.get("pf")),
                avg_r=format_optional_cell(row.get("avg_r")),
                expectancy_r=format_optional_cell(row.get("expectancy_r")),
                max_dd_r=format_optional_cell(row.get("max_drawdown_r")),
                net_profit=format_optional_cell(row.get("net_profit")),
                trades_delta=format_optional_cell(row.get("trades_delta_vs_backtest")),
                pf_delta=format_optional_cell(row.get("pf_delta_vs_backtest")),
                avg_r_delta=format_optional_cell(row.get("avg_r_delta_vs_backtest")),
                max_dd_delta=format_optional_cell(row.get("max_drawdown_r_delta_vs_backtest")),
                net_delta=format_optional_cell(row.get("net_profit_delta_vs_backtest")),
            )
        )
        appended += 1
    if appended == 0:
        lines.append("| None |  |  |  |  |  |  |  |  |  |  |  |  |")


def format_optional_cell(value: object) -> str:
    return "" if value is None else str(value)


def append_tester_pass_lines(lines: list[str], rows: object, *, limit: int) -> None:
    compacted = compact_tester_passes(rows, limit=limit)
    if not compacted:
        lines.append("- None")
        return
    for row in compacted:
        lines.append(
            f"- pass={row.get('Pass')}, forward={row.get('Forward Result')}, back={row.get('Back Result')}, "
            f"pf={row.get('Profit Factor')}, trades={row.get('Trades')}, "
            f"buy_rr={row.get('InpBuyRiskReward')}, sell_rr={row.get('InpSellRiskReward')}, "
            f"score={row.get('InpMinScore')}, depth={row.get('InpSwingDepth')}, "
            f"atr_band={row.get('InpSwingAtrBand')}, stop_buffer={row.get('InpStopBufferPoints')}"
        )


def append_optimization_pass_budget_lines(lines: list[str], summary: object) -> None:
    if not isinstance(summary, dict):
        return
    budget = summary.get("optimization_pass_budget")
    if not isinstance(budget, dict):
        return
    if budget.get("set_file"):
        lines.append(f"- Set file: {budget.get('set_file')}")
    if not budget.get("available", True):
        lines.append(f"- Pass budget: unavailable ({budget.get('reason', 'unknown')})")
        return
    if budget.get("optimized_input_count") is not None or budget.get("estimated_full_factorial_passes") is not None:
        lines.append(
            f"- Pass budget: optimized_inputs={budget.get('optimized_input_count')}, "
            f"full_factorial={budget.get('estimated_full_factorial_passes')}"
        )
    executed_rows = budget.get("executed_tester_xml_rows")
    if isinstance(executed_rows, dict):
        lines.append(
            f"- Executed Tester XML rows: back {executed_rows.get('back', '')} / "
            f"forward {executed_rows.get('forward', '')}"
        )
    if budget.get("note"):
        lines.append(f"- Pass note: {budget.get('note')}")


def append_optimization_recommendation_lines(lines: list[str], recommendation: object) -> None:
    if not isinstance(recommendation, dict) or not recommendation:
        return
    set_metadata = recommendation.get("set_metadata")
    if not isinstance(set_metadata, dict):
        set_metadata = {}
    decision = recommendation.get("decision")
    if isinstance(decision, dict):
        status = decision.get("status")
        if status is None and "adoptable" in decision:
            status = "ready" if decision.get("adoptable") else "not_ready"
        lines.append(f"- Recommendation decision: {status if status is not None else ''}")
        reasons = decision.get("reasons")
        if isinstance(reasons, list) and reasons:
            lines.append(f"- Recommendation reasons: {format_semicolon_list(reasons[:8])}")
    elif decision is not None:
        lines.append(f"- Recommendation decision: {decision}")
    if not set_metadata:
        return
    lines.extend(
        [
            f"- Next set path: {set_metadata.get('path', '')}",
            f"- Next set focus side: {set_metadata.get('focus_side', '')}",
            f"- Next set diagnostic only: {set_metadata.get('diagnostic_only', '')}",
            f"- Next set skipped write: {set_metadata.get('skipped_write', '')}",
        ]
    )
    if set_metadata.get("skip_reason"):
        lines.append(f"- Next set skip reason: {set_metadata.get('skip_reason')}")
    if set_metadata.get("optimized_input_count") is not None or set_metadata.get("estimated_full_factorial_passes") is not None:
        lines.append(
            f"- Next set pass budget: optimized_inputs={set_metadata.get('optimized_input_count')}, "
            f"full_factorial={set_metadata.get('estimated_full_factorial_passes')}"
        )
    coverage_summary = stable_hint_coverage_summary(set_metadata.get("stable_hint_coverage"))
    if coverage_summary != "None":
        lines.append(f"- Next set stable hint coverage: {coverage_summary}")
    score_refit_sides = set_metadata.get("score_refit_sides")
    if isinstance(score_refit_sides, list) and score_refit_sides:
        lines.append(f"- Next set score refit sides: {format_list_value(score_refit_sides)}")
    artifact_exclusions = set_metadata.get("stable_hint_artifact_exclusions")
    if isinstance(artifact_exclusions, list) and artifact_exclusions:
        lines.append(f"- Stable hint artifact exclusions: {format_artifact_exclusions(artifact_exclusions)}")


def format_artifact_exclusions(value: object) -> str:
    if not isinstance(value, list):
        return "None"
    rendered: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        parameter = item.get("parameter")
        if not parameter:
            continue
        rendered.append(f"{parameter}={item.get('value')}")
    return ", ".join(rendered) if rendered else "None"


def execution_dedupe_key(execution: dict[str, object]) -> str:
    rendered_fields = {
        "command_text": execution.get("command_text"),
        "status_command_text": execution.get("status_command_text"),
        "follow_up_command_text": execution.get("follow_up_command_text"),
        "outputs": execution.get("outputs") if isinstance(execution.get("outputs"), dict) else {},
        "optimized_input_count": execution.get("optimized_input_count"),
        "estimated_full_factorial_passes": execution.get("estimated_full_factorial_passes"),
        "optimization_mode": execution.get("optimization_mode", "genetic"),
        "timeout_seconds": execution.get("timeout_seconds"),
        "timeout_minutes": execution.get("timeout_minutes"),
        "timeout_note": execution.get("timeout_note"),
        "latest_executed_tester_xml_rows": execution.get("latest_executed_tester_xml_rows"),
        "note": execution.get("note"),
    }
    return json.dumps(rendered_fields, sort_keys=True, ensure_ascii=False, default=str)


def action_area_text(action: dict[str, object], label: str) -> str:
    area = action.get("area")
    return f"{area} {label}" if label else str(area)


def format_priority_text(priorities: object) -> str:
    if not isinstance(priorities, list):
        return "P?"
    values: list[str] = []
    for priority in priorities:
        if priority is None:
            continue
        text = str(priority)
        if text not in values:
            values.append(text)
    if not values:
        return "P?"
    return "/".join(f"P{value}" for value in values)


def merge_execution_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    merged_rows: list[dict[str, object]] = []
    by_key: dict[str, dict[str, object]] = {}
    for row in rows:
        execution = row.get("execution")
        action = row.get("action")
        if not isinstance(execution, dict) or not isinstance(action, dict):
            continue
        key = execution_dedupe_key(execution)
        area_text = str(row.get("area_text") or "")
        existing = by_key.get(key)
        if existing is not None:
            actions = existing.setdefault("actions", [])
            if isinstance(actions, list) and action not in actions:
                actions.append(action)
            area_texts = existing.setdefault("area_texts", [])
            if isinstance(area_texts, list) and area_text and area_text not in area_texts:
                area_texts.append(area_text)
            priorities = existing.setdefault("priorities", [])
            priority = action.get("priority")
            if isinstance(priorities, list) and priority not in priorities:
                priorities.append(priority)
            continue
        merged = dict(row)
        merged["area_texts"] = [area_text] if area_text else []
        merged["priorities"] = [action.get("priority")]
        merged["actions"] = [action]
        by_key[key] = merged
        merged_rows.append(merged)
    return merged_rows


def execution_row_actions(row: dict[str, object]) -> list[dict[str, object]]:
    actions = row.get("actions")
    if isinstance(actions, list):
        return [action for action in actions if isinstance(action, dict)]
    action = row.get("action")
    return [action] if isinstance(action, dict) else []


def parse_report_time(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in (TIME_FORMAT, "%Y.%m.%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_mt5_date(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y.%m.%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def mt5_date_range_days(from_date: object, to_date: object) -> int | None:
    parsed_from = parse_mt5_date(from_date)
    parsed_to = parse_mt5_date(to_date)
    if parsed_from is None or parsed_to is None or parsed_to < parsed_from:
        return None
    return (parsed_to - parsed_from).days


def timeout_deadline_text(generated_at: object, timeout_seconds: object) -> str:
    base_time = parse_report_time(generated_at)
    if base_time is None or timeout_seconds is None or isinstance(timeout_seconds, bool):
        return ""
    try:
        seconds = int(float(timeout_seconds))
    except (TypeError, ValueError):
        return ""
    if seconds <= 0:
        return ""
    return (base_time + timedelta(seconds=seconds)).strftime(TIME_FORMAT)


def append_next_action_execution_lines(lines: list[str], actions: object, *, generated_at: object = None) -> None:
    if not isinstance(actions, list):
        return
    rows: list[dict[str, object]] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        evidence = action.get("evidence")
        if not isinstance(evidence, dict):
            continue
        execution = evidence.get("execution")
        if isinstance(execution, dict):
            rows.append(
                {
                    "action": action,
                    "execution": execution,
                    "label": "",
                    "area_text": action_area_text(action, ""),
                }
            )
        for key, label in (
            ("archive_preview", "archive_preview"),
            ("compile", "compile"),
            ("risk_preset_fix", "risk_preset_fix"),
            ("refit_execution", "refit"),
            ("refit_archive_preview", "refit_archive_preview"),
            ("validation_execution", "validation"),
            ("validation_archive_preview", "validation_archive_preview"),
            ("follow_up_execution", "follow_up"),
            ("follow_up_archive_preview", "follow_up_archive_preview"),
            ("stable_candidate_set_execution", "stable_candidate_set"),
            ("stable_candidate_tester_execution", "stable_candidate_tester"),
            ("stable_candidate_archive_preview", "stable_candidate_archive_preview"),
            ("stable_candidate_refit_execution", "stable_candidate_refit"),
            ("stable_candidate_refit_archive_preview", "stable_candidate_refit_archive_preview"),
            ("score_weight_search", "score_weight_search"),
            ("score_weight_set", "score_weight_set"),
            ("score_weight_history_check", "score_weight_history_check"),
            ("score_weight_sample_collection", "score_weight_sample_collection"),
            ("score_weight_sample_collection_archive_preview", "score_weight_sample_collection_archive_preview"),
            ("collect_refresh", "collect_refresh"),
            ("sync_set", "sync_set"),
        ):
            extra_execution = evidence.get(key)
            if isinstance(extra_execution, dict):
                rows.append(
                    {
                        "action": action,
                        "execution": extra_execution,
                        "label": label,
                        "area_text": action_area_text(action, label),
                    }
                )
    rows = merge_execution_rows(rows)
    if not rows:
        return
    lines.extend(["", "## Next Action Execution Plans"])
    for row in rows:
        execution = row["execution"]
        outputs = execution.get("outputs") if isinstance(execution, dict) else {}
        priority_text = format_priority_text(row.get("priorities"))
        area_texts = row.get("area_texts")
        if isinstance(area_texts, list) and area_texts:
            area_text = ", ".join(str(item) for item in area_texts)
        else:
            area_text = str(row.get("area_text") or "")
        lines.append(f"- {priority_text} {area_text}: {execution.get('command_text')}")
        row_actions = execution_row_actions(row)
        plan_items = [
            ("kind", execution.get("kind")),
            ("focus", execution.get("focus_side")),
            ("config", execution.get("config")),
            ("set", execution.get("set")),
            ("set_file", execution.get("set_file")),
            ("template_set", execution.get("template_set")),
            ("sync_set", execution.get("sync_expert_parameters_set")),
            ("tester_xml", execution.get("tester_xml")),
            ("tester_forward_xml", execution.get("tester_forward_xml")),
            ("mode", execution.get("mode")),
            ("report", execution.get("report_name")),
            ("run_id_prefix", execution.get("run_id_prefix")),
            ("archive_run_id", execution.get("agent_csv_archive_run_id") or execution.get("run_id")),
            ("include_source_time", execution.get("include_source_time")),
        ]
        visible_plan_items = [f"{name}={value}" for name, value in plan_items if value]
        if visible_plan_items:
            lines.append(f"  plan: {', '.join(visible_plan_items)}")
        append_risk_preset_fix_execution_lines(lines, execution)
        action = row.get("action") if isinstance(row.get("action"), dict) else {}
        append_score_calibration_execution_lines(lines, action, execution)
        append_backtest_sample_execution_lines(lines, action, execution)
        append_python_forward_wait_execution_lines(lines, action, execution)
        append_dry_run_wait_execution_lines(lines, action, execution)
        append_dry_run_safety_execution_lines(lines, action, execution)
        append_source_time_gap_execution_lines(lines, action, execution)
        for row_action in row_actions:
            append_chronological_failure_execution_lines(lines, row_action, execution)
        append_stable_pass_execution_lines(lines, action, execution)
        append_mt5_optimization_gap_execution_lines(lines, row_actions, execution)
        append_optimization_recommendation_execution_lines(lines, row_actions, execution)
        append_terminal_blocker_execution_lines(lines, action, execution)
        append_side_score_issue_execution_lines(lines, row_actions, execution)
        append_score_weight_follow_up_execution_lines(lines, row_actions, execution)
        append_sl_tp_segment_execution_lines(lines, row_actions, execution)
        for row_action in row_actions:
            append_yearly_validation_execution_lines(lines, row_action, execution)
        append_mt5_forward_execution_lines(lines, row_actions, execution)
        append_mt5_back_forward_execution_lines(lines, row_actions, execution)
        append_mt5_status_watch_execution_lines(lines, row_actions, execution)
        append_winrate_fit_execution_lines(lines, action, execution)
        append_risk_shape_execution_lines(lines, action, execution)
        if isinstance(outputs, dict):
            output_items = [
                ("run", outputs.get("run_json")),
                ("optimization", outputs.get("optimization_json")),
                ("recommendation", outputs.get("recommendation_json")),
                ("set", outputs.get("output_set")),
                ("command", outputs.get("command_json")),
                ("audit", outputs.get("audit_json")),
                ("ledger", outputs.get("ledger")),
                ("summary", outputs.get("summary_json")),
                ("status", outputs.get("status_json")),
                ("heartbeat", outputs.get("heartbeat")),
                ("compile_run", outputs.get("compile_run_json")),
                ("compile_status", outputs.get("compile_status_json")),
                ("backtest", outputs.get("backtest_xlsx") or outputs.get("backtest_md")),
                ("weight_search", outputs.get("weight_search_xlsx")),
                ("weight_search_json", outputs.get("weight_search_json")),
                ("weight_search_md", outputs.get("weight_search_md")),
                ("history_request", outputs.get("history_request")),
                ("history_done", outputs.get("history_done")),
                ("history_status", outputs.get("history_status_json")),
                ("bridge_recovery_plan", outputs.get("bridge_recovery_plan_json")),
                ("winrate_fit", outputs.get("fit_json")),
                ("winrate_xlsx", outputs.get("fit_xlsx")),
                ("json", outputs.get("json")),
                ("md", outputs.get("md")),
                ("archive_root", outputs.get("archive_root")),
            ]
            visible_outputs = [f"{name}={value}" for name, value in output_items if value]
            if visible_outputs:
                lines.append(f"  outputs: {', '.join(visible_outputs)}")
            if outputs.get("forward_json") or outputs.get("collect_status_json"):
                lines.append(
                    f"  forward_outputs: report={outputs.get('forward_json')}, "
                    f"collect_status={outputs.get('collect_status_json')}"
                )
        if execution.get("estimated_full_factorial_passes") is not None:
            lines.append(
                f"  passes: optimized_inputs={execution.get('optimized_input_count')}, "
                f"full_factorial={execution.get('estimated_full_factorial_passes')}, "
                f"mode={execution.get('optimization_mode', 'genetic')}"
            )
        recent_rows = execution.get("latest_executed_tester_xml_rows")
        if isinstance(recent_rows, dict):
            row_parts = []
            if recent_rows.get("back") is not None:
                row_parts.append(f"back={recent_rows.get('back')}")
            if recent_rows.get("forward") is not None:
                row_parts.append(f"forward={recent_rows.get('forward')}")
            ratio_text = recent_xml_row_ratio_text(recent_rows.get("ratio_vs_full_factorial"))
            source_text = str(recent_rows.get("source") or "")
            if row_parts:
                suffix_parts = []
                if ratio_text:
                    suffix_parts.append(f"ratio_vs_full_factorial={ratio_text}")
                if source_text:
                    suffix_parts.append(f"source={source_text}")
                suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
                lines.append(f"  recent_xml_rows: {', '.join(row_parts)}{suffix}")
        if execution.get("timeout_seconds") is not None:
            timeout_minutes = execution.get("timeout_minutes")
            lines.append(f"  timeout: {timeout_minutes:g} min ({execution.get('timeout_seconds')} sec)")
            deadline = timeout_deadline_text(generated_at, execution.get("timeout_seconds"))
            if deadline:
                lines.append(f"  timeout_deadline_if_started_at_generated: {deadline}")
            if execution.get("timeout_note"):
                lines.append(f"  timeout_note: {execution.get('timeout_note')}")
        follow_up = execution.get("follow_up_command_text")
        status_check = execution.get("status_command_text")
        recovery_plan = execution.get("recovery_plan_command_text")
        if status_check:
            lines.append(f"  status_check: {status_check}")
        if recovery_plan:
            lines.append(f"  recovery_plan: {recovery_plan}")
        if follow_up:
            lines.append(f"  follow_up: {follow_up}")
        if execution.get("note"):
            lines.append(f"  note: {execution.get('note')}")


def recent_xml_row_ratio_text(ratios: object) -> str:
    if not isinstance(ratios, dict):
        return ""
    parts = []
    for key in ("back", "forward"):
        value = ratios.get(key)
        if numeric_value_present(value):
            parts.append(f"{key}={number(value) * 100:.1f}%")
    return "/".join(parts)


def format_threshold_row(row: object) -> str:
    if not isinstance(row, dict) or not row:
        return "None"
    return (
        f">= {row.get('threshold')}: count={row.get('count')}, "
        f"avg_r={row.get('avg_r')}, pf={row.get('pf')}, total_r={row.get('total_r')}"
    )


def format_score_weight_candidate(row: object) -> str:
    if not isinstance(row, dict) or not row:
        return "None"
    return (
        f"side={row.get('side')}, threshold={row.get('threshold')}, "
        f"weights={row.get('weights')}, count={row.get('count')}, "
        f"avg_r={row.get('avg_r')}, pf={row.get('pf')}, total_r={row.get('total_r')}, "
        f"max_dd_r={row.get('max_drawdown_r')}"
    )


def format_score_weight_baseline(row: object) -> str:
    if not isinstance(row, dict) or not row:
        return "None"
    return (
        f">= {row.get('threshold')}: count={row.get('count')}, "
        f"avg_r={row.get('avg_r')}, pf={row.get('pf')}, total_r={row.get('total_r')}, "
        f"max_dd_r={row.get('max_drawdown_r')}"
    )


def format_score_weight_diagnostics(row: object) -> str:
    if not isinstance(row, dict) or not row:
        return "None"
    baseline = format_score_weight_baseline(row.get("baseline"))
    deltas = row.get("deltas") if isinstance(row.get("deltas"), dict) else {}
    delta_text = (
        f"delta_count={deltas.get('count')}, delta_avg_r={deltas.get('avg_r')}, "
        f"delta_pf={deltas.get('pf')}, delta_total_r={deltas.get('total_r')}, "
        f"delta_max_dd_r={deltas.get('max_drawdown_r')}"
        if deltas
        else "delta=None"
    )
    return (
        f"status={row.get('status')}, baseline={baseline}, {delta_text}, "
        f"walk_forward={format_score_weight_walk_forward(row.get('walk_forward'))}, "
        f"recommendation={row.get('recommendation')}"
    )


def format_score_weight_walk_forward(row: object) -> str:
    if not isinstance(row, dict) or not row:
        return "not_run"
    if row.get("enabled") is not True:
        return "not_run"
    aggregate = row.get("aggregate") if isinstance(row.get("aggregate"), dict) else {}
    if not aggregate:
        return "enabled_no_aggregate"
    parts = [
        f"status={aggregate.get('status')}, folds={aggregate.get('folds')}, "
        f"weight_count={aggregate.get('total_test_weight_count')}, "
        f"baseline_count={aggregate.get('total_test_baseline_count')}, "
        f"mean_avg_r={aggregate.get('mean_test_weight_avg_r')}/{aggregate.get('mean_test_baseline_avg_r')}, "
        f"mean_pf={aggregate.get('mean_test_weight_pf')}/{aggregate.get('mean_test_baseline_pf')}, "
        f"delta_avg_r={aggregate.get('delta_mean_avg_r')}, delta_pf={aggregate.get('delta_mean_pf')}",
    ]
    if (
        "total_test_weight_r" in aggregate
        or "total_test_baseline_r" in aggregate
        or "delta_total_r" in aggregate
    ):
        parts.append(
            f"total_r={aggregate.get('total_test_weight_r')}/{aggregate.get('total_test_baseline_r')}, "
            f"delta_total_r={aggregate.get('delta_total_r')}"
        )
    if "min_count" in aggregate:
        parts.append(f"min_count={aggregate.get('min_count')}")
    if (
        aggregate.get("missing_test_weight_count") is not None
        or aggregate.get("missing_folds_with_weight_trades") is not None
        or aggregate.get("required_folds_with_weight_trades") is not None
    ):
        parts.append(
            f"missing={aggregate.get('missing_test_weight_count')}, "
            f"folds_with_trades={aggregate.get('folds_with_weight_trades')}/"
            f"{aggregate.get('required_folds_with_weight_trades')}, "
            f"missing_folds={aggregate.get('missing_folds_with_weight_trades')}"
        )
    if aggregate.get("min_test_weight_count") is not None or aggregate.get("min_test_weight_fold") is not None:
        parts.append(
            f"min_fold={aggregate.get('min_test_weight_fold')}:"
            f"{aggregate.get('min_test_weight_count')}"
        )
    return ", ".join(parts)


def format_score_weight_regime_search(row: object) -> str:
    if not isinstance(row, dict) or not row or row.get("enabled") is not True:
        return "None"
    best = row.get("best_regime_candidate") if isinstance(row.get("best_regime_candidate"), dict) else {}
    if not best:
        return f"enabled, rows={row.get('row_count')}, no eligible regime candidate"
    return (
        f"{best.get('dimension')}={best.get('group')}, threshold={best.get('threshold')}, "
        f"weights={best.get('weights')}, count={best.get('count')}, avg_r={best.get('avg_r')}, "
        f"pf={best.get('pf')}, total_r={best.get('total_r')}, wf={best.get('wf_status')}, "
        f"wf_avg_r={best.get('wf_mean_avg_r')}/{best.get('wf_baseline_avg_r')}, "
        f"wf_pf={best.get('wf_mean_pf')}/{best.get('wf_baseline_pf')}, "
        f"wf_delta_total_r={best.get('wf_delta_total_r')}, "
        f"wf_missing={best.get('wf_missing_weight_count')}, "
        f"wf_folds={best.get('wf_folds_with_weight')}/{best.get('wf_required_folds_with_weight')}"
    )


def format_score_weight_set_result(row: object) -> str:
    if not isinstance(row, dict) or not row:
        return "None"
    follow_up = row.get("follow_up") if isinstance(row.get("follow_up"), dict) else {}
    follow_up_text = ""
    if follow_up:
        follow_up_text = (
            f", follow_up={follow_up.get('status')}, "
            f"next_action={follow_up.get('next_action')}"
        )
    return (
        f"side={row.get('focus_side')}, written={row.get('written')}, "
        f"skipped={row.get('skipped_write')}, skip_reason={row.get('skip_reason')}, "
        f"wf={row.get('walk_forward_status')}, output_set={row.get('output_set')}"
        f"{follow_up_text}"
    )


def format_score_weight_follow_up(row: object) -> str:
    if not isinstance(row, dict) or not row:
        return "None"
    parts = [
        f"status={row.get('status')}",
        f"sample_shortage={row.get('sample_shortage')}",
    ]
    if row.get("regime_dimension") or row.get("regime_group"):
        parts.append(f"regime={row.get('regime_dimension')}:{row.get('regime_group')}")
        parts.append(f"regime_status={row.get('regime_status')}")
    if row.get("walk_forward_missing_test_weight_count") is not None:
        parts.append(
            "walk_missing="
            f"{row.get('walk_forward_missing_test_weight_count')}/"
            f"{row.get('walk_forward_required_test_weight_count')}"
        )
        parts.append(
            "walk_folds="
            f"{row.get('walk_forward_folds_with_weight_trades')}/"
            f"{row.get('walk_forward_required_folds_with_weight_trades')}"
        )
    if row.get("regime_missing_test_weight_count") is not None:
        parts.append(
            "regime_missing="
            f"{row.get('regime_missing_test_weight_count')}/"
            f"{row.get('regime_required_test_weight_count')}"
        )
        parts.append(
            "regime_folds="
            f"{row.get('regime_folds_with_weight_trades')}/"
            f"{row.get('regime_required_folds_with_weight_trades')}"
        )
    if row.get("recommendation"):
        parts.append(f"recommendation={row.get('recommendation')}")
    return ", ".join(parts)


def number(value: object) -> float:
    if value is None or isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def format_promotion_markdown(report: dict[str, object]) -> str:
    checks = report.get("checks", [])
    next_actions = report.get("next_actions")
    if not isinstance(next_actions, list):
        next_actions = build_promotion_next_actions(report)
    summary = report.get("summary", {})
    forward = report.get("forward_test", {})
    mt5_forward = report.get("mt5_forward_test", {})
    mt5_optimization = report.get("mt5_optimization", {})
    mt5_optimization_recommendation = report.get("mt5_optimization_recommendation", {})
    mt5_tester_status = report.get("mt5_tester_status", {})
    mt5_tester_run = report.get("mt5_tester_run", {})
    mt5_back_forward_run = report.get("mt5_back_forward_run", {})
    mt5_strategy_tester_analysis = report.get("mt5_strategy_tester_analysis", {})
    mt5_stable_candidate = report.get("mt5_stable_candidate", {})
    mt5_stable_candidate_recommendation = report.get("mt5_stable_candidate_recommendation", {})
    mt5_stable_candidate_tester_run = report.get("mt5_stable_candidate_tester_run", {})
    mt5_yearly_optimization = report.get("mt5_yearly_optimization", {})
    mt5_compile = report.get("mt5_compile_status", {})
    winrate_fit = report.get("winrate_fit", {})
    score_weight_search = report.get("score_weight_search", {})
    score_weight_search_by_side = report.get("score_weight_search_by_side", {})
    overall = summary.get("overall", {}) if isinstance(summary, dict) else {}
    side_rows = summary.get("side", []) if isinstance(summary, dict) else []
    threshold_rows = summary.get("thresholds", []) if isinstance(summary, dict) else []
    score_calibration = report.get("score_calibration", {})
    forward_status = report.get("forward_status", {})
    bridge_status = report.get("bridge_status", {})
    forward_side_rows = forward.get("by_action", []) if isinstance(forward, dict) else []
    mt5_overall = mt5_forward_overall(mt5_forward) if isinstance(mt5_forward, dict) else {}
    mt5_side_rows = mt5_forward.get("by_action", []) if isinstance(mt5_forward, dict) else []
    mt5_side_score_rows = mt5_forward.get("side_score_diagnostics", []) if isinstance(mt5_forward, dict) else []
    mt5_risk_exposure = mt5_forward.get("risk_exposure", {}) if isinstance(mt5_forward, dict) else {}
    mt5_forward_source_checks = mt5_forward.get("checks", {}) if isinstance(mt5_forward, dict) else {}
    mt5_forward_signal = mt5_forward.get("signal", {}) if isinstance(mt5_forward, dict) else {}
    mt5_forward_reject = mt5_forward.get("reject", {}) if isinstance(mt5_forward, dict) else {}
    mt5_forward_warnings = mt5_forward.get("diagnostic_warnings", []) if isinstance(mt5_forward, dict) else []
    mt5_forward_csv_schema = mt5_forward.get("csv_schema", {}) if isinstance(mt5_forward, dict) else {}
    mt5_forward_sl_tp = compact_mt5_forward_sl_tp_diagnostics(mt5_forward) if isinstance(mt5_forward, dict) else {}
    mt5_optimization_overall_row = mt5_optimization_overall(mt5_optimization) if isinstance(mt5_optimization, dict) else {}
    mt5_optimization_side_rows = mt5_optimization.get("by_action", []) if isinstance(mt5_optimization, dict) else []
    mt5_optimization_side_score_rows = (
        mt5_optimization.get("side_score_diagnostics", []) if isinstance(mt5_optimization, dict) else []
    )
    mt5_optimization_best_segments = mt5_optimization.get("best_segments", []) if isinstance(mt5_optimization, dict) else []
    mt5_optimization_weak_segments = mt5_optimization.get("weak_segments", []) if isinstance(mt5_optimization, dict) else []
    mt5_optimization_chronological_splits = (
        mt5_optimization.get("chronological_splits", []) if isinstance(mt5_optimization, dict) else []
    )
    mt5_optimization_xml = mt5_optimization.get("tester_xml", {}) if isinstance(mt5_optimization, dict) else {}
    mt5_optimization_forward_xml = (
        mt5_optimization_xml.get("forward", {}) if isinstance(mt5_optimization_xml, dict) else {}
    )
    mt5_tester = mt5_tester_run if isinstance(mt5_tester_run, dict) else {}
    mt5_tester_report_paths_raw = mt5_tester.get("report_paths") if isinstance(mt5_tester, dict) else {}
    mt5_tester_report_paths = (
        mt5_tester_report_paths_raw if isinstance(mt5_tester_report_paths_raw, dict) else {}
    )
    mt5_tester_terminal_raw = mt5_tester.get("terminal_run") if isinstance(mt5_tester, dict) else {}
    mt5_tester_terminal = mt5_tester_terminal_raw if isinstance(mt5_tester_terminal_raw, dict) else {}
    mt5_tester_archive_raw = mt5_tester.get("agent_csv_archive") if isinstance(mt5_tester, dict) else {}
    mt5_tester_archive = mt5_tester_archive_raw if isinstance(mt5_tester_archive_raw, dict) else {}
    mt5_tester_archive_source_time = (
        mt5_tester_archive.get("source_time_coverage")
        if isinstance(mt5_tester_archive.get("source_time_coverage"), dict)
        else {}
    )
    mt5_back_forward = mt5_back_forward_run if isinstance(mt5_back_forward_run, dict) else {}
    mt5_back_forward_rows = (
        mt5_back_forward.get("performance_comparison_rows")
        if isinstance(mt5_back_forward.get("performance_comparison_rows"), list)
        else []
    )
    mt5_stable_candidate_row = (
        mt5_optimization_overall(mt5_stable_candidate) if isinstance(mt5_stable_candidate, dict) else {}
    )
    mt5_stable_candidate_xml = (
        mt5_stable_candidate.get("tester_xml", {}) if isinstance(mt5_stable_candidate, dict) else {}
    )
    mt5_stable_candidate_forward_xml = (
        mt5_stable_candidate_xml.get("forward", {}) if isinstance(mt5_stable_candidate_xml, dict) else {}
    )
    mt5_stable_candidate_chronological_splits = (
        mt5_stable_candidate.get("chronological_splits", []) if isinstance(mt5_stable_candidate, dict) else []
    )
    mt5_stable_candidate_side_score_rows = (
        mt5_stable_candidate.get("side_score_diagnostics", []) if isinstance(mt5_stable_candidate, dict) else []
    )
    mt5_stable_candidate_tester = (
        mt5_stable_candidate_tester_run if isinstance(mt5_stable_candidate_tester_run, dict) else {}
    )
    mt5_stable_candidate_tester_terminal_raw = (
        mt5_stable_candidate_tester.get("terminal_run") if isinstance(mt5_stable_candidate_tester, dict) else {}
    )
    mt5_stable_candidate_tester_terminal = (
        mt5_stable_candidate_tester_terminal_raw
        if isinstance(mt5_stable_candidate_tester_terminal_raw, dict)
        else {}
    )
    mt5_yearly_overall_row = (
        mt5_optimization_overall(mt5_yearly_optimization) if isinstance(mt5_yearly_optimization, dict) else {}
    )
    mt5_yearly_xml = (
        mt5_yearly_optimization.get("tester_xml", {}) if isinstance(mt5_yearly_optimization, dict) else {}
    )
    mt5_yearly_forward_xml = mt5_yearly_xml.get("forward", {}) if isinstance(mt5_yearly_xml, dict) else {}
    mt5_yearly_chronological_splits = (
        mt5_yearly_optimization.get("chronological_splits", []) if isinstance(mt5_yearly_optimization, dict) else []
    )
    mt5_yearly_side_score_rows = (
        mt5_yearly_optimization.get("side_score_diagnostics", []) if isinstance(mt5_yearly_optimization, dict) else []
    )
    performance_comparison = report.get("performance_comparison")
    if not isinstance(performance_comparison, list):
        performance_comparison = performance_comparison_rows(
            summary=summary if isinstance(summary, dict) else {},
            forward_summary=forward if isinstance(forward, dict) else {},
            mt5_forward_summary=mt5_forward if isinstance(mt5_forward, dict) else {},
            mt5_optimization_summary=mt5_optimization if isinstance(mt5_optimization, dict) else {},
            mt5_yearly_optimization_summary=mt5_yearly_optimization if isinstance(mt5_yearly_optimization, dict) else {},
        )
    mt5_compile_items = mt5_compile.get("items", []) if isinstance(mt5_compile, dict) else []
    mt5_tester_sets = mt5_compile.get("tester_sets", []) if isinstance(mt5_compile, dict) else []
    fit_adoption = winrate_fit.get("adoption_decision", {}) if isinstance(winrate_fit, dict) else {}

    mt5_risk = mt5_risk_exposure if isinstance(mt5_risk_exposure, dict) else {}
    mt5_risk_checks = mt5_forward_source_checks if isinstance(mt5_forward_source_checks, dict) else {}

    def mt5_risk_limit(check_name: str, fallback_key: str) -> object:
        source = mt5_risk_checks.get(check_name)
        if isinstance(source, dict):
            return source.get("required_max", source.get("required", ""))
        return mt5_risk.get(fallback_key, "")

    lines = [
        "# Promotion Gate",
        "",
        f"- Decision: {report.get('decision')}",
        f"- Live ready: {report.get('live_ready')}",
        f"- Generated at: {report.get('generated_at')}",
        "",
        "## Next Actions",
    ]
    if isinstance(next_actions, list):
        for action in next_actions:
            if not isinstance(action, dict):
                continue
            lines.append(
                f"- P{action.get('priority')} {action.get('area')}: {action.get('action')} - {action.get('reason')}"
            )
    append_next_action_execution_lines(lines, next_actions, generated_at=report.get("generated_at"))
    mt5_operator_summary = (
        mt5_tester_status.get("operator_summary")
        if isinstance(mt5_tester_status, dict)
        and isinstance(mt5_tester_status.get("operator_summary"), dict)
        else {}
    )
    if mt5_operator_summary:
        lines.extend(["", "## MT5 Operator Summary"])
        append_mt5_operator_summary_lines(lines, mt5_operator_summary, prefix="- ")
    append_mt5_strategy_tester_analysis_lines(
        lines,
        mt5_strategy_tester_analysis,
        current_promotion_generated_at=report.get("generated_at"),
    )
    mt5_status_watch = (
        mt5_tester_status.get("status_watch_heartbeat")
        if isinstance(mt5_tester_status, dict)
        and isinstance(mt5_tester_status.get("status_watch_heartbeat"), dict)
        else {}
    )
    if mt5_status_watch.get("manual_test_queue_exists") or mt5_status_watch.get(
        "manual_test_queue_execution_checklist"
    ):
        lines.extend(["", "## MT5 Manual Queue From Watcher"])
        append_mt5_status_watch_manual_queue_lines(
            lines,
            mt5_status_watch,
            prefix="- ",
            label_prefix="",
        )
    lines.extend(
        [
            "",
            "## Bridge Status",
            f"- Operational status: {bridge_status.get('operational_status', '') if isinstance(bridge_status, dict) else ''}",
            f"- OK: {bridge_status.get('ok', '') if isinstance(bridge_status, dict) else ''}",
            f"- Health/config: {bridge_status.get('health_ok', '') if isinstance(bridge_status, dict) else ''} / {bridge_status.get('config_ok', '') if isinstance(bridge_status, dict) else ''}",
            f"- Config history request: hours={bridge_status.get('config_history_hours', '') if isinstance(bridge_status, dict) else ''}, id={bridge_status.get('config_history_request_id', '') if isinstance(bridge_status, dict) else ''}",
            f"- Snapshot: fresh={bridge_status.get('snapshot_fresh', '') if isinstance(bridge_status, dict) else ''}, age_seconds={bridge_status.get('snapshot_age_seconds', '') if isinstance(bridge_status, dict) else ''}, server_time={bridge_status.get('snapshot_server_time', '') if isinstance(bridge_status, dict) else ''}",
            f"- History request: pending={bridge_status.get('history_request_pending', '') if isinstance(bridge_status, dict) else ''}, stale_pending={bridge_status.get('history_request_stale_pending', '') if isinstance(bridge_status, dict) else ''}, pending_age_seconds={bridge_status.get('history_request_pending_age_seconds', '') if isinstance(bridge_status, dict) else ''}",
            f"- Bridge log activity: status={bridge_status.get('bridge_log_activity_status', '') if isinstance(bridge_status, dict) else ''}, ea_post_count={bridge_status.get('bridge_log_ea_post_count', '') if isinstance(bridge_status, dict) else ''}, last_ea_post={bridge_status.get('bridge_log_last_ea_post_at', '') if isinstance(bridge_status, dict) else ''}, ea_post_age_seconds={bridge_status.get('bridge_log_last_ea_post_age_seconds', '') if isinstance(bridge_status, dict) else ''}, last_snapshot_post={bridge_status.get('bridge_log_last_snapshot_post_at', '') if isinstance(bridge_status, dict) else ''}, snapshot_post_age_seconds={bridge_status.get('bridge_log_last_snapshot_post_age_seconds', '') if isinstance(bridge_status, dict) else ''}",
            f"- Bridge EA liveness: signal={bridge_status.get('ea_liveness_signal', '') or bridge_status.get('bridge_log_ea_liveness_signal', '') if isinstance(bridge_status, dict) else ''}, config_get_recent={bridge_status.get('config_get_recent', '') if isinstance(bridge_status, dict) else ''}, ea_post_recent={bridge_status.get('ea_post_recent', '') if isinstance(bridge_status, dict) else ''}, config_get_recent_but_ea_post_stale={bridge_status.get('config_get_recent_but_ea_post_stale', '') if isinstance(bridge_status, dict) else ''}",
            f"- Bridge config GET: last_config_get={bridge_status.get('bridge_log_last_config_get_at', '') if isinstance(bridge_status, dict) else ''}, config_get_age_seconds={bridge_status.get('bridge_log_last_config_get_age_seconds', '') if isinstance(bridge_status, dict) else ''}; GET /config may be produced by status checks, use EA POST freshness for EA liveness.",
            f"- Bridge EA attention: required={bridge_status.get('ea_attention_required', '') if isinstance(bridge_status, dict) else ''}, reason={bridge_status.get('ea_attention_reason', '') if isinstance(bridge_status, dict) else ''}, mt5_terminal_running={bridge_status.get('mt5_terminal_running', '') if isinstance(bridge_status, dict) else ''}, terminal_match_count={bridge_status.get('mt5_terminal_match_count', '') if isinstance(bridge_status, dict) else ''}",
            f"- Next action: {bridge_status.get('next_action', '') if isinstance(bridge_status, dict) else ''}",
            "",
            "## Overall Backtest",
            f"- Count: {overall.get('count') if isinstance(overall, dict) else ''}",
            f"- Avg R: {overall.get('avg_r') if isinstance(overall, dict) else ''}",
            f"- PF: {overall.get('pf') if isinstance(overall, dict) else ''}",
            f"- Max losing streak: {overall.get('max_losing_streak') if isinstance(overall, dict) else ''}",
            f"- Max drawdown R: {overall.get('max_drawdown_r') if isinstance(overall, dict) else ''}",
            f"- Expectancy R: {overall.get('expectancy_r') if isinstance(overall, dict) else ''}",
            "",
            "## Score Thresholds",
        ]
    )
    if isinstance(threshold_rows, list):
        for row in threshold_rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- >= {row.get('threshold')}: count={row.get('count')}, avg_r={row.get('avg_r')}, "
                f"pf={row.get('pf')}, total_r={row.get('total_r')}"
            )
    if isinstance(score_calibration, dict) and score_calibration:
        lines.extend(
            [
                "",
                "## Score Calibration",
                f"- Status: {score_calibration.get('status')}",
                f"- Required: score >= {score_calibration.get('required_threshold')} with count >= {score_calibration.get('required_count')}",
                f"- Highest sampled: {format_threshold_row(score_calibration.get('highest_sampled_threshold'))}",
                f"- Highest sufficient: {format_threshold_row(score_calibration.get('highest_sufficient_threshold'))}",
                f"- Required count: {score_calibration.get('required_threshold_count')}",
                f"- Missing at required: {score_calibration.get('sample_shortage_at_required_threshold')}",
                f"- Points from required: {score_calibration.get('points_from_required_threshold')}",
                f"- Recommendation: {score_calibration.get('recommendation')}",
            ]
        )
    if isinstance(score_weight_search, dict) and score_weight_search:
        lines.extend(
            [
                "",
                "## Score Weight Search",
                f"- Generated at: {score_weight_search.get('generated_at')}",
                f"- Candidate/result count: {score_weight_search.get('candidate_count')} / {score_weight_search.get('result_count')}",
                f"- Search rows: {score_weight_search.get('search_row_count')}",
                f"- Top: {format_score_weight_candidate(score_weight_search.get('top_weight_candidate'))}",
                f"- Delta: {format_score_weight_diagnostics(score_weight_search.get('diagnostics'))}",
                f"- Walk-forward: {format_score_weight_walk_forward(score_weight_search.get('walk_forward'))}",
                f"- Regime top: {format_score_weight_regime_search(score_weight_search.get('regime_search'))}",
            ]
        )
    if isinstance(score_weight_search_by_side, dict) and score_weight_search_by_side:
        lines.extend(["", "## Side Score Weight Search"])
        for side in ("buy", "sell"):
            side_search = score_weight_search_by_side.get(side)
            if not isinstance(side_search, dict) or not side_search:
                continue
            side_label = side.upper()
            lines.extend(
                [
                    f"- {side_label} generated at: {side_search.get('generated_at')}",
                    f"- {side_label} candidate/result count: {side_search.get('candidate_count')} / {side_search.get('result_count')}",
                    f"- {side_label} search rows: {side_search.get('search_row_count')}",
                    f"- {side_label} top: {format_score_weight_candidate(side_search.get('top_weight_candidate'))}",
                    f"- {side_label} delta: {format_score_weight_diagnostics(side_search.get('diagnostics'))}",
                    f"- {side_label} walk-forward: {format_score_weight_walk_forward(side_search.get('walk_forward'))}",
                    f"- {side_label} regime top: {format_score_weight_regime_search(side_search.get('regime_search'))}",
                ]
            )
    lines.extend(
        [
            "",
            "## Side Backtest",
        ]
    )
    if isinstance(side_rows, list):
        for row in side_rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- {row.get('group')}: count={row.get('count')}, avg_r={row.get('avg_r')}, "
                f"pf={row.get('pf')}, total_r={row.get('total_r')}"
            )
    lines.extend(
        [
            "",
            "## Forward Test",
            f"- Closed/Open: {forward.get('closed') if isinstance(forward, dict) else ''} / {forward.get('open') if isinstance(forward, dict) else ''}",
            f"- Avg R: {forward.get('avg_r') if isinstance(forward, dict) else ''}",
            f"- PF: {forward.get('pf') if isinstance(forward, dict) else ''}",
            f"- Max drawdown R: {forward.get('max_drawdown_r') if isinstance(forward, dict) else ''}",
            f"- Expectancy R: {forward.get('expectancy_r') if isinstance(forward, dict) else ''}",
            f"- Operational status: {forward_status.get('operational_status') if isinstance(forward_status, dict) else ''}",
            f"- Latest signal action: {forward_status.get('signal', {}).get('action') if isinstance(forward_status, dict) and isinstance(forward_status.get('signal'), dict) else ''}",
            f"- Latest signal recordability: {forward_status.get('signal', {}).get('recordability') if isinstance(forward_status, dict) and isinstance(forward_status.get('signal'), dict) else ''}",
            "",
            "## Forward By Side",
        ]
    )
    if isinstance(forward_side_rows, list):
        for row in forward_side_rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- {row.get('group')}: closed={row.get('closed')}, avg_r={row.get('avg_r')}, "
                f"pf={row.get('pf')}, total_r={row.get('total_r')}"
            )
    lines.extend(
        [
            "",
            "## MT5 Forward Test",
            f"- Closed: {mt5_overall.get('closed')}",
            f"- Net profit: {mt5_overall.get('net_profit')}",
            f"- PF: {mt5_overall.get('pf')}",
            f"- Max losing streak: {mt5_overall.get('max_losing_streak')}",
            f"- Max drawdown price R: {mt5_overall.get('max_drawdown_price_r')}",
            f"- Expectancy price R: {mt5_overall.get('expectancy_price_r')}",
            "",
            "## Backtest Vs Forward Drift",
            "",
            "| dataset | trades | pf | pf_delta | avg_r | avg_r_delta | expectancy_r | expectancy_delta | max_dd_r | max_dd_delta |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    append_performance_comparison_lines(lines, performance_comparison)
    lines.extend(
        [
            "",
            "## MT5 Back/Forward Runner Drift",
            f"- Generated at: {mt5_back_forward.get('generated_at', '')}",
            f"- OK: {mt5_back_forward.get('ok', '')}",
            f"- Mode: {mt5_back_forward.get('mode', '')}",
            f"- Execute: {mt5_back_forward.get('execute', '')}",
            f"- Dry run: {mt5_back_forward.get('dry_run', '')}",
            f"- Collect only: {mt5_back_forward.get('collect_only', '')}",
            f"- Launch MT5: {mt5_back_forward.get('launch_mt5', '')}",
            f"- Evidence state: {mt5_back_forward.get('evidence_state', '')}",
            f"- Step labels: {format_list_value(mt5_back_forward.get('step_labels'))}",
            f"- Comparison available: {mt5_back_forward.get('performance_comparison_available', '')}",
            f"- Comparison status: {mt5_back_forward.get('performance_comparison_status', '')}",
            f"- Comparison reason: {mt5_back_forward.get('performance_comparison_reason', '')}",
            f"- Blocked before steps: {mt5_back_forward.get('blocked_before_steps', '')}",
            f"- Reason: {mt5_back_forward.get('reason', '')}",
            "",
            "| dataset | trades | min ok | pf | avg_r | expectancy_r | max_dd_r | net_profit | trades delta | pf delta | avg_r delta | max_dd delta | net delta |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    append_mt5_back_forward_comparison_lines(lines, mt5_back_forward_rows)
    lines.extend(
        [
            "",
            "## MT5 Forward Diagnostic Warnings",
            f"- {format_warning_list(mt5_forward_warnings)}",
            "",
            "## MT5 Forward CSV Schema",
            f"- Entry-time diagnostics available: {mt5_forward_csv_schema.get('entry_time_diagnostics_available') if isinstance(mt5_forward_csv_schema, dict) else ''}",
            f"- Trend diagnostics available: {mt5_forward_csv_schema.get('trend_diagnostics_available') if isinstance(mt5_forward_csv_schema, dict) else ''}",
            f"- Execution diagnostics available: {mt5_forward_csv_schema.get('execution_diagnostics_available') if isinstance(mt5_forward_csv_schema, dict) else ''}",
            f"- Missing fields: {format_list_value(mt5_forward_csv_schema.get('missing_fields') if isinstance(mt5_forward_csv_schema, dict) else None)}",
            f"- Unavailable fields: {format_list_value(mt5_forward_csv_schema.get('unavailable_fields') if isinstance(mt5_forward_csv_schema, dict) else None)}",
            f"- Missing execution fields: {format_list_value(mt5_forward_csv_schema.get('missing_execution_fields') if isinstance(mt5_forward_csv_schema, dict) else None)}",
            f"- Unavailable execution fields: {format_list_value(mt5_forward_csv_schema.get('unavailable_execution_fields') if isinstance(mt5_forward_csv_schema, dict) else None)}",
            "",
            "## MT5 Forward SL/TP Diagnostics",
            f"- Row counts: {format_mt5_forward_sl_tp_counts(mt5_forward_sl_tp)}",
            f"- Weak segments: {format_segment_brief_rows(mt5_forward_sl_tp.get('weak_segments') if isinstance(mt5_forward_sl_tp, dict) else None, limit=3)}",
            "",
            "## MT5 Forward Risk Exposure",
            f"- Max single volume: {mt5_risk.get('max_single_volume')} / limit {mt5_risk_limit('max_single_volume', 'max_single_volume_limit')}",
            f"- Max concurrent volume: {mt5_risk.get('max_concurrent_volume')} / limit {mt5_risk_limit('max_concurrent_volume', 'max_total_volume_limit')}",
            f"- Max concurrent positions: {mt5_risk.get('max_concurrent_positions')} / limit {mt5_risk_limit('max_concurrent_positions', 'max_positions_limit')}",
            f"- Open positions at end: {mt5_risk.get('open_positions_at_end')}",
            f"- Open volume at end: {mt5_risk.get('open_volume_at_end')}",
            f"- Session resets: {mt5_risk.get('session_resets')}",
            f"- Stop-breach opens daily/consecutive: {mt5_risk.get('daily_loss_stop_open_breaches')} / {mt5_risk.get('consecutive_loss_stop_open_breaches')}",
            f"- Stop rejections daily/consecutive: {mt5_risk.get('daily_loss_stop_rejections')} / {mt5_risk.get('consecutive_loss_stop_rejections')}",
            f"- Lot limit rejections: {mt5_risk.get('lot_limit_rejections')}",
            "",
            "## MT5 Forward Signal Diagnostics",
            f"- Signal rows: {mt5_forward_signal.get('rows') if isinstance(mt5_forward_signal, dict) else ''}",
            f"- Signal buy/sell/hold: {mt5_forward_signal.get('buy') if isinstance(mt5_forward_signal, dict) else ''} / {mt5_forward_signal.get('sell') if isinstance(mt5_forward_signal, dict) else ''} / {mt5_forward_signal.get('hold') if isinstance(mt5_forward_signal, dict) else ''}",
            f"- Signal tradable/other: {mt5_forward_signal.get('tradable') if isinstance(mt5_forward_signal, dict) else ''} / {mt5_forward_signal.get('other') if isinstance(mt5_forward_signal, dict) else ''}",
            f"- Signal avg score: {mt5_forward_signal.get('avg_score') if isinstance(mt5_forward_signal, dict) else ''}",
            f"- Signal avg buy/sell score: {mt5_forward_signal.get('avg_buy_score') if isinstance(mt5_forward_signal, dict) else ''} / {mt5_forward_signal.get('avg_sell_score') if isinstance(mt5_forward_signal, dict) else ''}",
            "- Top signal reasons:",
        ]
    )
    append_text_count_lines(
        lines,
        mt5_forward_signal.get("top_reasons") if isinstance(mt5_forward_signal, dict) else None,
        limit=5,
    )
    lines.extend(
        [
            f"- Reject rows: {mt5_forward_reject.get('rows') if isinstance(mt5_forward_reject, dict) else ''}",
            f"- Reject buy/sell/other: {mt5_forward_reject.get('buy') if isinstance(mt5_forward_reject, dict) else ''} / {mt5_forward_reject.get('sell') if isinstance(mt5_forward_reject, dict) else ''} / {mt5_forward_reject.get('hold_or_other') if isinstance(mt5_forward_reject, dict) else ''}",
            f"- Detected consecutive loss limits: {format_detected_loss_limits(mt5_forward_reject.get('detected_consecutive_loss_limits') if isinstance(mt5_forward_reject, dict) else None)}",
            "- Top rejection messages:",
        ]
    )
    append_text_count_lines(
        lines,
        mt5_forward_reject.get("top_messages") if isinstance(mt5_forward_reject, dict) else None,
        limit=5,
    )
    lines.extend(
        [
            "",
            "## MT5 Tester Run",
            f"- Generated at: {mt5_tester.get('generated_at', '')}",
            f"- OK: {mt5_tester.get('ok', '')}",
            f"- Blocked: {mt5_tester.get('blocked', '')}",
            f"- Collect only: {mt5_tester.get('collect_only', '')}",
            f"- Dry run: {mt5_tester.get('dry_run', '')}",
            f"- Agent CSV archive required: {mt5_tester.get('agent_csv_archive_required', 'not_reported')}",
            f"- Agent CSV archive missing: {mt5_tester.get('agent_csv_archive_missing', 'not_reported')}",
            f"- Agent CSV archive run ID: {mt5_tester.get('agent_csv_archive_run_id', '')}",
            f"- Agent CSV archive OK: {mt5_tester_archive.get('ok', 'not_reported') if mt5_tester_archive else 'not_reported'}",
            f"- Agent CSV archive count: {mt5_tester_archive.get('count', 'not_reported') if mt5_tester_archive else 'not_reported'}",
            f"- Agent CSV archive source time: {format_agent_csv_source_time_coverage(mt5_tester_archive_source_time)}",
            f"- Source time blocked: {mt5_tester.get('source_time_blocked', '')}",
            f"- Report source: {mt5_tester_report_paths.get('source', '')}",
            f"- Report fallback blocked: {mt5_tester.get('report_fallback_blocked', '')}",
            f"- Requested back XML: {mt5_tester_report_paths.get('requested_back_xml', '')}",
            f"- Used back XML: {mt5_tester_report_paths.get('used_back_xml', '')}",
            f"- Terminal failed: {mt5_tester.get('terminal_failed', '')}",
            f"- Terminal returncode: {mt5_tester_terminal.get('returncode', '')}",
            f"- Terminal timeout: {mt5_tester_terminal.get('timeout', '')}",
            f"- Terminal deadline at: {mt5_tester_terminal.get('deadline_at', '')}",
            f"- Terminal elapsed seconds: {mt5_tester_terminal.get('elapsed_seconds', '')}",
        ]
    )
    lines.extend(
        [
            "",
            "## MT5 Optimization",
            f"- Closed: {mt5_optimization_overall_row.get('closed')}",
            f"- Net profit: {mt5_optimization_overall_row.get('net_profit')}",
            f"- PF: {mt5_optimization_overall_row.get('pf')}",
            f"- Max drawdown price R: {mt5_optimization_overall_row.get('max_drawdown_price_r')}",
            f"- Expectancy price R: {mt5_optimization_overall_row.get('expectancy_price_r')}",
        ]
    )
    append_optimization_pass_budget_lines(lines, mt5_optimization)
    lines.extend(
        [
            f"- Positive forward / positive back: {mt5_optimization_forward_xml.get('positive_forward_positive_back') if isinstance(mt5_optimization_forward_xml, dict) else ''}",
            f"- Positive forward / negative back: {mt5_optimization_forward_xml.get('positive_forward_negative_back') if isinstance(mt5_optimization_forward_xml, dict) else ''}",
            "",
            "## MT5 Optimization Recommendation",
        ]
    )
    append_optimization_recommendation_lines(lines, mt5_optimization_recommendation)
    lines.extend(
        [
            "",
            "## MT5 Optimization By Side",
        ]
    )
    if isinstance(mt5_optimization_side_rows, list):
        for row in mt5_optimization_side_rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- {row.get('group')}: closed={row.get('closed')}, avg_price_r={row.get('avg_price_r')}, "
                f"pf={row.get('pf')}, net_profit={row.get('net_profit')}"
            )
    lines.extend(
        [
            "",
            "## MT5 Optimization Side Score Diagnostics",
        ]
    )
    append_side_score_lines(lines, mt5_optimization_side_score_rows, limit=8)
    lines.extend(
        [
            "",
            "## MT5 Optimization Best Segments",
        ]
    )
    append_segment_lines(lines, mt5_optimization_best_segments, limit=8, include_diagnosis=False)
    lines.extend(
        [
            "",
            "## MT5 Optimization Weak Segments",
        ]
    )
    append_segment_lines(lines, mt5_optimization_weak_segments, limit=8, include_diagnosis=True)
    lines.extend(
        [
            "",
            "## MT5 Optimization Chronological Splits",
        ]
    )
    append_segment_lines(lines, mt5_optimization_chronological_splits, limit=8, include_diagnosis=True)
    lines.extend(
        [
            "",
            "## MT5 Optimization Stable Forward",
        ]
    )
    if isinstance(mt5_optimization_forward_xml, dict):
        append_tester_pass_lines(lines, mt5_optimization_forward_xml.get("stable_top", []), limit=8)
    lines.extend(
        [
            "",
            "## MT5 Optimization Forward-Only",
        ]
    )
    if isinstance(mt5_optimization_forward_xml, dict):
        append_tester_pass_lines(lines, mt5_optimization_forward_xml.get("forward_only_top", []), limit=8)
    lines.extend(
        [
            "",
            "## MT5 Optimization Top Forward",
        ]
    )
    if isinstance(mt5_optimization_forward_xml, dict):
        append_tester_pass_lines(lines, mt5_optimization_forward_xml.get("top", []), limit=10)
    lines.extend(
        [
            "",
            "## MT5 Stable Candidate",
            f"- Closed: {mt5_stable_candidate_row.get('closed')}",
            f"- Net profit: {mt5_stable_candidate_row.get('net_profit')}",
            f"- PF: {mt5_stable_candidate_row.get('pf')}",
            f"- Avg price R: {mt5_stable_candidate_row.get('avg_price_r')}",
            f"- Max drawdown price R: {mt5_stable_candidate_row.get('max_drawdown_price_r')}",
            f"- Expectancy price R: {mt5_stable_candidate_row.get('expectancy_price_r')}",
            f"- Tester OK: {mt5_stable_candidate_tester.get('ok', '')}",
            f"- Tester blocked: {mt5_stable_candidate_tester.get('blocked', '')}",
            f"- Tester elapsed seconds: {mt5_stable_candidate_tester_terminal.get('elapsed_seconds', '')}",
            f"- Positive forward / positive back: {mt5_stable_candidate_forward_xml.get('positive_forward_positive_back') if isinstance(mt5_stable_candidate_forward_xml, dict) else ''}",
            f"- Positive forward / negative back: {mt5_stable_candidate_forward_xml.get('positive_forward_negative_back') if isinstance(mt5_stable_candidate_forward_xml, dict) else ''}",
        ]
    )
    append_optimization_pass_budget_lines(lines, mt5_stable_candidate)
    lines.extend(
        [
            "",
            "## MT5 Stable Candidate Recommendation",
        ]
    )
    append_optimization_recommendation_lines(lines, mt5_stable_candidate_recommendation)
    lines.extend(
        [
            "",
            "## MT5 Stable Candidate Chronological Splits",
        ]
    )
    append_segment_lines(lines, mt5_stable_candidate_chronological_splits, limit=8, include_diagnosis=True)
    lines.extend(
        [
            "",
            "## MT5 Stable Candidate Side Score Diagnostics",
        ]
    )
    append_side_score_lines(lines, mt5_stable_candidate_side_score_rows, limit=8)
    lines.extend(
        [
            "",
            "## MT5 Yearly Optimization",
            f"- Closed: {mt5_yearly_overall_row.get('closed')}",
            f"- Net profit: {mt5_yearly_overall_row.get('net_profit')}",
            f"- PF: {mt5_yearly_overall_row.get('pf')}",
            f"- Avg price R: {mt5_yearly_overall_row.get('avg_price_r')}",
            f"- Max drawdown price R: {mt5_yearly_overall_row.get('max_drawdown_price_r')}",
            f"- Expectancy price R: {mt5_yearly_overall_row.get('expectancy_price_r')}",
        ]
    )
    append_optimization_pass_budget_lines(lines, mt5_yearly_optimization)
    lines.extend(
        [
            f"- Positive forward / positive back: {mt5_yearly_forward_xml.get('positive_forward_positive_back') if isinstance(mt5_yearly_forward_xml, dict) else ''}",
            f"- Positive forward / negative back: {mt5_yearly_forward_xml.get('positive_forward_negative_back') if isinstance(mt5_yearly_forward_xml, dict) else ''}",
            "",
            "## MT5 Yearly Chronological Splits",
        ]
    )
    append_segment_lines(lines, mt5_yearly_chronological_splits, limit=8, include_diagnosis=True)
    lines.extend(
        [
            "",
            "## MT5 Yearly Side Score Diagnostics",
        ]
    )
    append_side_score_lines(lines, mt5_yearly_side_score_rows, limit=8)
    lines.extend(
        [
            "",
            "## MT5 Compile Status",
            f"- Sources synced: {mt5_compile.get('all_sources_synced') if isinstance(mt5_compile, dict) else ''}",
            f"- Compiled fresh: {mt5_compile.get('all_compiled_fresh') if isinstance(mt5_compile, dict) else ''}",
            f"- Tester sets synced: {mt5_compile.get('all_tester_sets_synced') if isinstance(mt5_compile, dict) else ''}",
            f"- Tester configs synced: {mt5_compile.get('all_tester_configs_synced') if isinstance(mt5_compile, dict) else ''}",
        ]
    )
    if isinstance(mt5_compile_items, list):
        for row in mt5_compile_items:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- {row.get('kind')} {row.get('name')}: status={row.get('status')}, "
                f"source_synced={row.get('source_synced')}, compiled_fresh={row.get('compiled_fresh')}, "
                f"stale_seconds={row.get('stale_seconds')}"
            )
    if isinstance(mt5_tester_sets, list):
        for row in mt5_tester_sets:
            if not isinstance(row, dict) or row.get("synced") is True:
                continue
            lines.append(
                f"- tester_set {row.get('name')}: status={row.get('status')}, synced={row.get('synced')}"
            )
    lines.extend(
        [
            "",
            "## Winrate Fit",
            f"- Adopted: {fit_adoption.get('adopted') if isinstance(fit_adoption, dict) else ''}",
            f"- Reasons: {fit_adoption.get('reasons') if isinstance(fit_adoption, dict) else ''}",
            f"- Rules: {fit_adoption.get('rules') if isinstance(fit_adoption, dict) else ''}",
            "",
            "## MT5 Forward By Side",
        ]
    )
    if isinstance(mt5_side_rows, list):
        for row in mt5_side_rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- {row.get('group')}: closed={row.get('closed')}, avg_price_r={row.get('avg_price_r')}, "
                f"pf={row.get('pf')}, avg_hold_s={row.get('avg_hold_seconds')}, "
                f"avg_slip_pt={row.get('avg_slippage_points')}"
            )
    lines.extend(
        [
            "",
            "## MT5 Forward Side Score Diagnostics",
        ]
    )
    append_side_score_lines(lines, mt5_side_score_rows, limit=8)
    lines.extend(
        [
            "",
            "## Checks",
        ]
    )
    if isinstance(checks, list):
        for item in checks:
            if not isinstance(item, dict):
                continue
            mark = "PASS" if item.get("passed") else "FAIL"
            lines.append(f"- {mark} {item.get('name')}: {item.get('value')} / {item.get('requirement')}")
    return "\n".join(lines) + "\n"


def write_report(json_path: str | Path, md_path: str | Path, report: dict[str, object]) -> None:
    output_json = Path(json_path)
    output_md = Path(md_path)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(format_promotion_markdown(report), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate whether the strategy is ready to promote beyond dry-run.")
    parser.add_argument("--history", default="runtime/latest_history_168h.json")
    parser.add_argument("--calendar", default="runtime/economic_calendar.json")
    parser.add_argument("--calendar-input-utc-offset", type=float, default=None, help="UTC offset of naive calendar times, e.g. 9 for JST. Omit when calendar is already MT5 server time.")
    parser.add_argument("--calendar-server-utc-offset", type=float, default=None, help="MT5 server UTC offset used when converting calendar times.")
    parser.add_argument("--signal", default="runtime/latest_signal.json")
    parser.add_argument("--command", default="runtime/trade_command.json")
    parser.add_argument("--trade-result", default="runtime/latest_trade_result.json")
    parser.add_argument("--forward-ledger", default="runtime/forward_tests.jsonl")
    parser.add_argument("--forward-status", default="runtime/latest_forward_test_status.json")
    parser.add_argument("--forward-status-watch-heartbeat", default="runtime/forward_status_watch_heartbeat.json")
    parser.add_argument("--forward-test-watch-heartbeat", default="runtime/forward_test_watch_heartbeat.json")
    parser.add_argument("--bridge-status", default="runtime/latest_bridge_status.json")
    parser.add_argument("--mt5-forward-report", default="runtime/latest_mt5_forward_report.json")
    parser.add_argument("--mt5-optimization-report", default="runtime/latest_mt5_optimization_report.json")
    parser.add_argument(
        "--mt5-optimization-recommendation",
        default="runtime/latest_mt5_optimization_recommendation.json",
    )
    parser.add_argument("--mt5-tester-run-report", default="runtime/latest_mt5_tester_run.json")
    parser.add_argument("--mt5-tester-status", default="runtime/latest_mt5_tester_status.json")
    parser.add_argument("--mt5-back-forward-run", default="runtime/latest_mt5_back_forward_run.json")
    parser.add_argument(
        "--mt5-strategy-tester-analysis",
        default="runtime/latest_mt5_strategy_tester_analysis.json",
    )
    parser.add_argument(
        "--mt5-stable-candidate-report",
        default="runtime/latest_mt5_stable_candidate_optimization_report.json",
    )
    parser.add_argument(
        "--mt5-stable-candidate-recommendation",
        default="runtime/latest_mt5_stable_candidate_recommendation.json",
    )
    parser.add_argument(
        "--mt5-stable-candidate-tester-run-report",
        default="runtime/latest_mt5_tester_stable_candidate_run.json",
    )
    parser.add_argument(
        "--mt5-buy-refit-recommendation",
        default="runtime/latest_mt5_buy_refit_recommendation.json",
    )
    parser.add_argument(
        "--mt5-buy-entry-refit-recommendation",
        default="runtime/latest_mt5_buy_entry_refit_recommendation.json",
    )
    parser.add_argument(
        "--mt5-sell-entry-refit-recommendation",
        default="runtime/latest_mt5_sell_entry_refit_recommendation.json",
    )
    parser.add_argument(
        "--mt5-sell-regime-entry-refit-recommendation",
        default="runtime/latest_mt5_sell_regime_entry_refit_recommendation.json",
    )
    parser.add_argument(
        "--mt5-buy-hour03-validation-recommendation",
        default="runtime/latest_mt5_buy_hour03_validation_recommendation.json",
    )
    parser.add_argument(
        "--mt5-buy-hour03-wide-stop-validation-recommendation",
        default="runtime/latest_mt5_buy_hour03_wide_stop_validation_recommendation.json",
    )
    parser.add_argument(
        "--mt5-buy-hour03-wide-stop-calendar-validation-recommendation",
        default="runtime/latest_mt5_buy_hour03_wide_stop_calendar_validation_recommendation.json",
    )
    parser.add_argument("--mt5-yearly-optimization-report", default="runtime/latest_mt5_2025_optimization_report.json")
    parser.add_argument("--mt5-compile-status", default="runtime/latest_mt5_compile_status.json")
    parser.add_argument("--winrate-fit-report", default="runtime/latest_winrate_fit.json")
    parser.add_argument("--score-weight-search-report", default="runtime/latest_score_weight_search.json")
    parser.add_argument("--score-weight-search-buy-report", default="runtime/latest_score_weight_search_168h_buy_rr4.json")
    parser.add_argument("--score-weight-search-sell-report", default="runtime/latest_score_weight_search_168h_sell_rr4.json")
    parser.add_argument("--score-weight-set-buy-report", default="runtime/latest_score_weight_set_168h_buy_rr4.json")
    parser.add_argument("--score-weight-set-sell-report", default="runtime/latest_score_weight_set_168h_sell_rr4.json")
    parser.add_argument("--risk-shape-weight-search-report", default="runtime/latest_risk_shape_weight_search.json")
    parser.add_argument("--output-json", default="runtime/latest_promotion_gate.json")
    parser.add_argument("--output-md", default="runtime/latest_promotion_gate.md")
    parser.add_argument("--strategy", choices=("fixed", "setup_ladder", "space_ladder", "side_ladder"), default="side_ladder")
    parser.add_argument("--rr-values", type=parse_rr_values, default=list(DEFAULT_RR_VALUES))
    parser.add_argument("--fixed-rr", type=float, default=4.0)
    parser.add_argument("--min-score", type=float, default=50.0)
    parser.add_argument("--max-hold-minutes", type=int, default=60)
    parser.add_argument("--min-history-hours", type=int, default=168)
    parser.add_argument("--min-candidates", type=int, default=100)
    parser.add_argument("--min-avg-r", type=float, default=0.0)
    parser.add_argument("--min-pf", type=float, default=1.2)
    parser.add_argument("--max-drawdown-r", type=float, default=0.0, help="Disabled when <= 0.")
    parser.add_argument("--min-expectancy-r", type=float, default=None)
    parser.add_argument("--min-score-quality-threshold", type=float, default=70.0)
    parser.add_argument("--min-score-quality-count", type=int, default=20)
    parser.add_argument("--min-score-quality-avg-r", type=float, default=0.0)
    parser.add_argument("--min-score-quality-pf", type=float, default=1.2)
    parser.add_argument("--max-score-quality-avg-r-drop", type=float, default=0.25)
    parser.add_argument("--max-losing-streak", type=int, default=20)
    parser.add_argument("--min-side-count", type=int, default=30)
    parser.add_argument("--min-side-pf", type=float, default=1.0)
    parser.add_argument("--min-side-avg-r", type=float, default=0.0)
    parser.add_argument("--max-side-total-r-share", type=float, default=0.85)
    parser.add_argument("--allow-missing-dry-run", action="store_true")
    parser.add_argument("--max-dry-run-age-seconds", type=int, default=3600)
    parser.add_argument("--allow-missing-forward", action="store_true")
    parser.add_argument("--min-forward-closed", type=int, default=30)
    parser.add_argument("--min-forward-avg-r", type=float, default=0.0)
    parser.add_argument("--min-forward-pf", type=float, default=1.2)
    parser.add_argument("--max-forward-drawdown-r", type=float, default=0.0, help="Disabled when <= 0.")
    parser.add_argument("--min-forward-expectancy-r", type=float, default=None)
    parser.add_argument("--min-forward-side-closed", type=int, default=10)
    parser.add_argument("--min-forward-side-pf", type=float, default=1.0)
    parser.add_argument("--min-forward-side-avg-r", type=float, default=0.0)
    parser.add_argument("--require-mt5-forward", action="store_true")
    parser.add_argument("--min-mt5-forward-closed", type=int, default=30)
    parser.add_argument("--min-mt5-forward-pf", type=float, default=1.2)
    parser.add_argument("--max-mt5-forward-losing-streak", type=int, default=20)
    parser.add_argument("--max-mt5-forward-drawdown-price-r", type=float, default=0.0, help="Disabled when <= 0.")
    parser.add_argument("--min-mt5-forward-expectancy-price-r", type=float, default=None)
    parser.add_argument("--min-mt5-forward-side-closed", type=int, default=10)
    parser.add_argument("--min-mt5-forward-side-pf", type=float, default=1.0)
    parser.add_argument("--min-mt5-forward-side-avg-price-r", type=float, default=0.0)
    parser.add_argument("--require-mt5-optimization", action="store_true")
    parser.add_argument("--min-mt5-optimization-closed", type=int, default=100)
    parser.add_argument("--min-mt5-optimization-pf", type=float, default=1.2)
    parser.add_argument("--max-mt5-optimization-drawdown-price-r", type=float, default=0.0, help="Disabled when <= 0.")
    parser.add_argument("--min-mt5-optimization-expectancy-price-r", type=float, default=None)
    parser.add_argument("--min-mt5-optimization-side-closed", type=int, default=30)
    parser.add_argument("--min-mt5-optimization-side-pf", type=float, default=1.0)
    parser.add_argument("--min-mt5-optimization-side-avg-price-r", type=float, default=0.0)
    parser.add_argument("--min-mt5-optimization-forward-pf", type=float, default=1.2)
    parser.add_argument("--min-mt5-optimization-forward-trades", type=int, default=30)
    parser.add_argument("--min-mt5-optimization-positive-forward-back", type=int, default=1)
    parser.add_argument("--require-mt5-yearly-optimization", action="store_true")
    parser.add_argument("--min-mt5-yearly-optimization-closed", type=int, default=100)
    parser.add_argument("--min-mt5-yearly-optimization-pf", type=float, default=1.2)
    parser.add_argument("--min-mt5-yearly-optimization-avg-price-r", type=float, default=0.0)
    parser.add_argument("--max-mt5-yearly-optimization-drawdown-price-r", type=float, default=0.0, help="Disabled when <= 0.")
    parser.add_argument("--min-mt5-yearly-optimization-expectancy-price-r", type=float, default=None)
    parser.add_argument("--min-mt5-yearly-optimization-positive-forward-back", type=int, default=1)
    parser.add_argument("--require-mt5-compile", action="store_true")
    parser.add_argument("--require-winrate-fit", action="store_true")
    parser.add_argument("--include-blackout-times", action="store_true")
    parser.add_argument("--news-before-minutes", type=int, default=10)
    parser.add_argument("--news-after-minutes", type=int, default=10)
    parser.add_argument("--news-min-impact", default="high", choices=("low", "medium", "high"))
    parser.add_argument("--news-currencies", default="USD,XAU,ALL")
    parser.add_argument("--print-full-report", action="store_true", help="Print the full Promotion Gate JSON to stdout.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = evaluate_promotion_gate(
        history_path=args.history,
        calendar_path=args.calendar,
        calendar_input_utc_offset=args.calendar_input_utc_offset,
        calendar_server_utc_offset=args.calendar_server_utc_offset,
        signal_path=args.signal,
        command_path=args.command,
        trade_result_path=args.trade_result,
        forward_ledger_path=args.forward_ledger,
        forward_status_path=args.forward_status,
        forward_status_watch_heartbeat_path=args.forward_status_watch_heartbeat,
        forward_test_watch_heartbeat_path=args.forward_test_watch_heartbeat,
        bridge_status_path=args.bridge_status,
        mt5_forward_report_path=args.mt5_forward_report,
        mt5_optimization_report_path=args.mt5_optimization_report,
        mt5_optimization_recommendation_path=args.mt5_optimization_recommendation,
        mt5_tester_run_report_path=args.mt5_tester_run_report,
        mt5_tester_status_path=args.mt5_tester_status,
        mt5_back_forward_run_path=args.mt5_back_forward_run,
        mt5_strategy_tester_analysis_path=args.mt5_strategy_tester_analysis,
        mt5_stable_candidate_report_path=args.mt5_stable_candidate_report,
        mt5_stable_candidate_recommendation_path=args.mt5_stable_candidate_recommendation,
        mt5_stable_candidate_tester_run_report_path=args.mt5_stable_candidate_tester_run_report,
        mt5_buy_refit_recommendation_path=args.mt5_buy_refit_recommendation,
        mt5_buy_entry_refit_recommendation_path=args.mt5_buy_entry_refit_recommendation,
        mt5_sell_entry_refit_recommendation_path=args.mt5_sell_entry_refit_recommendation,
        mt5_sell_regime_entry_refit_recommendation_path=args.mt5_sell_regime_entry_refit_recommendation,
        mt5_buy_hour03_validation_recommendation_path=args.mt5_buy_hour03_validation_recommendation,
        mt5_buy_hour03_wide_stop_validation_recommendation_path=(
            args.mt5_buy_hour03_wide_stop_validation_recommendation
        ),
        mt5_buy_hour03_wide_stop_calendar_validation_recommendation_path=(
            args.mt5_buy_hour03_wide_stop_calendar_validation_recommendation
        ),
        mt5_yearly_optimization_report_path=args.mt5_yearly_optimization_report,
        mt5_compile_status_path=args.mt5_compile_status,
        winrate_fit_report_path=args.winrate_fit_report,
        score_weight_search_report_path=args.score_weight_search_report,
        score_weight_search_buy_report_path=args.score_weight_search_buy_report,
        score_weight_search_sell_report_path=args.score_weight_search_sell_report,
        score_weight_set_buy_report_path=args.score_weight_set_buy_report,
        score_weight_set_sell_report_path=args.score_weight_set_sell_report,
        risk_shape_weight_search_report_path=args.risk_shape_weight_search_report,
        strategy=args.strategy,
        rr_values=args.rr_values,
        fixed_rr=args.fixed_rr,
        min_score=args.min_score,
        max_hold_minutes=args.max_hold_minutes,
        min_history_hours=args.min_history_hours,
        min_candidates=args.min_candidates,
        min_avg_r=args.min_avg_r,
        min_pf=args.min_pf,
        max_drawdown_r=args.max_drawdown_r,
        min_expectancy_r=args.min_expectancy_r,
        min_score_quality_threshold=args.min_score_quality_threshold,
        min_score_quality_count=args.min_score_quality_count,
        min_score_quality_avg_r=args.min_score_quality_avg_r,
        min_score_quality_pf=args.min_score_quality_pf,
        max_score_quality_avg_r_drop=args.max_score_quality_avg_r_drop,
        max_losing_streak_allowed=args.max_losing_streak,
        min_side_count=args.min_side_count,
        min_side_pf=args.min_side_pf,
        min_side_avg_r=args.min_side_avg_r,
        max_side_total_r_share=args.max_side_total_r_share,
        require_dry_run_passed=not args.allow_missing_dry_run,
        max_dry_run_age_seconds=args.max_dry_run_age_seconds,
        require_forward=not args.allow_missing_forward,
        min_forward_closed=args.min_forward_closed,
        min_forward_avg_r=args.min_forward_avg_r,
        min_forward_pf=args.min_forward_pf,
        max_forward_drawdown_r=args.max_forward_drawdown_r,
        min_forward_expectancy_r=args.min_forward_expectancy_r,
        min_forward_side_closed=args.min_forward_side_closed,
        min_forward_side_pf=args.min_forward_side_pf,
        min_forward_side_avg_r=args.min_forward_side_avg_r,
        require_mt5_forward=args.require_mt5_forward,
        min_mt5_forward_closed=args.min_mt5_forward_closed,
        min_mt5_forward_pf=args.min_mt5_forward_pf,
        max_mt5_forward_losing_streak=args.max_mt5_forward_losing_streak,
        max_mt5_forward_drawdown_price_r=args.max_mt5_forward_drawdown_price_r,
        min_mt5_forward_expectancy_price_r=args.min_mt5_forward_expectancy_price_r,
        min_mt5_forward_side_closed=args.min_mt5_forward_side_closed,
        min_mt5_forward_side_pf=args.min_mt5_forward_side_pf,
        min_mt5_forward_side_avg_price_r=args.min_mt5_forward_side_avg_price_r,
        require_mt5_optimization=args.require_mt5_optimization,
        min_mt5_optimization_closed=args.min_mt5_optimization_closed,
        min_mt5_optimization_pf=args.min_mt5_optimization_pf,
        max_mt5_optimization_drawdown_price_r=args.max_mt5_optimization_drawdown_price_r,
        min_mt5_optimization_expectancy_price_r=args.min_mt5_optimization_expectancy_price_r,
        min_mt5_optimization_side_closed=args.min_mt5_optimization_side_closed,
        min_mt5_optimization_side_pf=args.min_mt5_optimization_side_pf,
        min_mt5_optimization_side_avg_price_r=args.min_mt5_optimization_side_avg_price_r,
        min_mt5_optimization_forward_pf=args.min_mt5_optimization_forward_pf,
        min_mt5_optimization_forward_trades=args.min_mt5_optimization_forward_trades,
        min_mt5_optimization_positive_forward_back=args.min_mt5_optimization_positive_forward_back,
        require_mt5_yearly_optimization=args.require_mt5_yearly_optimization,
        min_mt5_yearly_optimization_closed=args.min_mt5_yearly_optimization_closed,
        min_mt5_yearly_optimization_pf=args.min_mt5_yearly_optimization_pf,
        min_mt5_yearly_optimization_avg_price_r=args.min_mt5_yearly_optimization_avg_price_r,
        max_mt5_yearly_optimization_drawdown_price_r=args.max_mt5_yearly_optimization_drawdown_price_r,
        min_mt5_yearly_optimization_expectancy_price_r=args.min_mt5_yearly_optimization_expectancy_price_r,
        min_mt5_yearly_optimization_positive_forward_back=args.min_mt5_yearly_optimization_positive_forward_back,
        require_mt5_compile=args.require_mt5_compile,
        require_winrate_fit=args.require_winrate_fit,
        include_blackout_times=args.include_blackout_times,
        news_before_minutes=args.news_before_minutes,
        news_after_minutes=args.news_after_minutes,
        news_min_impact=args.news_min_impact,
        news_currencies=parse_currencies(args.news_currencies),
    )
    write_report(args.output_json, args.output_md, report)
    if args.print_full_report:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                promotion_cli_summary(report, output_json=args.output_json, output_md=args.output_md),
                ensure_ascii=False,
                indent=2,
            )
        )
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_md}")
    return 0 if report["live_ready"] else 2


def promotion_cli_summary(
    report: dict[str, object], *, output_json: str | Path, output_md: str | Path
) -> dict[str, object]:
    checks = report.get("checks") if isinstance(report.get("checks"), list) else []
    failed_names = promotion_failed_check_names(checks)
    next_actions = report.get("next_actions") if isinstance(report.get("next_actions"), list) else []
    return {
        "ok": report.get("ok"),
        "decision": report.get("decision"),
        "live_ready": report.get("live_ready"),
        "generated_at": report.get("generated_at"),
        "checks": len(checks),
        "failed": len(failed_names),
        "failed_checks": failed_names[:12],
        "next_actions": [
            {
                "priority": action.get("priority"),
                "area": action.get("area"),
                "action": action.get("action"),
            }
            for action in next_actions[:12]
            if isinstance(action, dict)
        ],
        "output_json": str(output_json),
        "output_md": str(output_md),
    }


if __name__ == "__main__":
    raise SystemExit(main())
