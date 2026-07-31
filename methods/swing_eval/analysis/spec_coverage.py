from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT
from analysis.mt5_manual_test_queue import (
    operator_collect_filter_summary,
    operator_step_summary,
)


DEFAULT_SPEC_PATH = "methods/swing_eval/docs/swing-evaluation-trading-system-spec.md"
DEFAULT_OUTPUT_JSON = "runtime/latest_spec_coverage.json"
DEFAULT_OUTPUT_MD = "runtime/latest_spec_coverage.md"
DEFAULT_MAX_ARTIFACT_AGE_SECONDS = 24 * 60 * 60
DEFAULT_MAX_HISTORY_REQUEST_PENDING_SECONDS = 180
DEFAULT_MAX_BRIDGE_SNAPSHOT_AGE_SECONDS = 5 * 60
DEFAULT_MAX_HISTORY_DATA_AGE_SECONDS = 12 * 60 * 60
DEFAULT_MT5_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION = (
    "runtime/latest_mt5_manual_test_queue_with_optimization.json"
)
DEFAULT_MT5_MANUAL_QUEUE_LAUNCH_WITH_OPTIMIZATION = (
    "runtime/latest_mt5_manual_queue_launch_with_optimization.json"
)
DEFAULT_MT5_MANUAL_COLLECT_WITH_OPTIMIZATION = (
    "runtime/latest_mt5_manual_collect_with_optimization.json"
)
DEFAULT_MT5_MANUAL_OPERATOR_PACKET_WITH_OPTIMIZATION = (
    "runtime/latest_mt5_manual_operator_packet_with_optimization.json"
)
DEFAULT_MT5_MANUAL_AUTO_COLLECT_WATCH = "runtime/latest_mt5_manual_auto_collect_watch.json"
DEFAULT_BRIDGE_RECOVERY_PLAN = "runtime/latest_bridge_recovery_plan.json"
DEFAULT_MT5_STRATEGY_TESTER_ANALYSIS = "runtime/latest_mt5_strategy_tester_analysis.json"
DEFAULT_MT5_OPTIMIZATION_STATIC_CONFIGS = {
    "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_optimization.ini",
    "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_next_optimization.ini",
}
MT5_STRATEGY_TESTER_ANALYSIS_REFRESH_COMMAND_TEXT = (
    "python3 methods/swing_eval/analysis/mt5_strategy_tester_analysis.py "
    f"--output-json {DEFAULT_MT5_STRATEGY_TESTER_ANALYSIS} "
    "--output-md runtime/latest_mt5_strategy_tester_analysis.md"
)
MT5_STRATEGY_TESTER_LABEL_CONFIGS: dict[str, str] = {
    "sell_short_window": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_optimization.ini",
    "sell_hour12_m30m15_2025": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_validation.ini",
    "sell_hour12_m30m15_calendar_2025": (
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.ini"
    ),
    "sell_regime_entry_2025": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_regime_entry_refit.ini",
    "buy_wide_stop_short": "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_wide_stop_validation.ini",
    "buy_hour03_wide_stop_2025": (
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.ini"
    ),
    "buy_hour03_wide_stop_calendar_2025": (
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.ini"
    ),
    "buy_strong_hours_m30m15_2025": (
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.ini"
    ),
}
MT5_STRATEGY_TESTER_STATIC_CANDIDATE_LABELS = {
    "sell_hour12_m30m15_2025",
    "sell_hour12_m30m15_calendar_2025",
    "buy_wide_stop_short",
    "buy_hour03_wide_stop_2025",
    "buy_hour03_wide_stop_calendar_2025",
}
MT5_BACK_FORWARD_SAMPLE_SHORTAGE_DEFAULT_FROM_DATE = "2025.01.01"
MT5_BACK_FORWARD_SAMPLE_SHORTAGE_DEFAULT_TO_DATE = "2025.12.31"
MT5_BACK_FORWARD_SAMPLE_SHORTAGE_MIN_EXTENDED_DAYS = 180

COMPONENT_HEADING_RE = re.compile(r"^### `([^`]+\.py)`\s*$")
PHASE_HEADING_RE = re.compile(r"^### (Phase [^:]+: .+)\s*$")

RUNTIME_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("history", "runtime/latest_history_168h.json"),
    ("history_status", "runtime/latest_history_status.json"),
    ("bridge_status", "runtime/latest_bridge_status.json"),
    ("bridge_recovery_plan", "runtime/latest_bridge_recovery_plan.json"),
    ("bridge_status_watch", "runtime/bridge_status_watch_heartbeat.json"),
    ("runtime_watchers", "runtime/latest_runtime_watchers.json"),
    ("promotion_gate", "runtime/latest_promotion_gate.json"),
    ("mt5_compile_status", "runtime/latest_mt5_compile_status.json"),
    ("mt5_tester_status", "runtime/latest_mt5_tester_status.json"),
    ("mt5_next_action_run", "runtime/latest_mt5_next_action_run.json"),
    ("mt5_next_action_run_buy", "runtime/latest_mt5_next_action_run_buy.json"),
    ("mt5_back_forward_run", "runtime/latest_mt5_back_forward_run.json"),
    ("mt5_manual_test_queue", "runtime/latest_mt5_manual_test_queue.json"),
    ("mt5_manual_queue_launch", "runtime/latest_mt5_manual_queue_launch.json"),
    ("mt5_manual_collect_run", "runtime/latest_mt5_manual_collect_run.json"),
    ("score_weight_search_buy_rr4", "runtime/latest_score_weight_search_168h_buy_rr4.json"),
    ("score_weight_set_buy_rr4", "runtime/latest_score_weight_set_168h_buy_rr4.json"),
    ("score_weight_search_sell_rr4", "runtime/latest_score_weight_search_168h_sell_rr4.json"),
    ("score_weight_set_sell_rr4", "runtime/latest_score_weight_set_168h_sell_rr4.json"),
    ("rr_strategy_experiment", "runtime/latest_rr_strategy_experiment.json"),
    ("winrate_fit", "runtime/latest_winrate_fit.json"),
    ("risk_shape_weight_search", "runtime/latest_risk_shape_weight_search.json"),
)

OPTIONAL_RUNTIME_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("mt5_manual_test_queue_with_optimization", DEFAULT_MT5_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION),
    ("mt5_manual_queue_launch_with_optimization", DEFAULT_MT5_MANUAL_QUEUE_LAUNCH_WITH_OPTIMIZATION),
    ("mt5_manual_collect_with_optimization", DEFAULT_MT5_MANUAL_COLLECT_WITH_OPTIMIZATION),
    (
        "mt5_manual_operator_packet_with_optimization",
        DEFAULT_MT5_MANUAL_OPERATOR_PACKET_WITH_OPTIMIZATION,
    ),
    ("mt5_manual_auto_collect_watch", DEFAULT_MT5_MANUAL_AUTO_COLLECT_WATCH),
    ("mt5_strategy_tester_analysis", DEFAULT_MT5_STRATEGY_TESTER_ANALYSIS),
)

PROMOTION_GATE_EVIDENCE_DEPENDENCIES: tuple[str, ...] = (
    "history",
    "history_status",
    "mt5_compile_status",
    "mt5_tester_status",
    "mt5_manual_test_queue",
    "mt5_manual_collect_run",
    "mt5_back_forward_run",
    "score_weight_search_buy_rr4",
    "score_weight_set_buy_rr4",
    "score_weight_search_sell_rr4",
    "score_weight_set_sell_rr4",
    "rr_strategy_experiment",
    "winrate_fit",
    "risk_shape_weight_search",
)
STRATEGY_TESTER_ANALYSIS_STABLE_DEPENDENCIES: tuple[tuple[str, str], ...] = (
    ("promotion_gate", "promotion_gate"),
    ("back_forward_run", "mt5_back_forward_run"),
)

MANUAL_QUEUE_PROMOTION_READY_STATUSES = {
    "ready_to_collect_all",
}
MANUAL_COLLECT_PROMOTION_READY_STATUSES = {
    "ready_for_collect_execute",
    "ready_to_execute_collect",
    "collect_executed",
}

MQL5_ARTIFACTS: tuple[tuple[str, str, str], ...] = (
    ("predictor_indicator", "methods/swing_eval/mt5/Indicators/Swing_Evaluation_Predictor.mq5", "Phase 5.5"),
    ("standalone_trader_ea", "methods/swing_eval/mt5/Experts/Swing_Evaluation_Trader.mq5", "Phase 6/7"),
    ("bridge_advisor_ea", "methods/swing_eval/mt5/Experts/AI_Bridge_Advisor.mq5", "Phase 1/6"),
    ("backtest_config", "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_backtest.ini", "MT5 Back/Forward"),
    ("forward_config", "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_forward_test.ini", "MT5 Back/Forward"),
    ("strategy_test_config", "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_strategy_test.ini", "MT5 Forward"),
    ("sample_collection_config", "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sample_collection.ini", "Score Weight"),
    ("optimization_config", "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_optimization.ini", "MT5 Optimization"),
    ("next_optimization_config", "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_next_optimization.ini", "MT5 Optimization"),
    ("stable_candidate_config", "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_stable_candidate.ini", "MT5 Optimization"),
    ("buy_refit_config", "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_refit.ini", "BUY Refit"),
    ("buy_entry_refit_config", "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_entry_refit.ini", "BUY Refit"),
    (
        "buy_hour03_validation_config",
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_validation.ini",
        "BUY Validation",
    ),
    (
        "buy_strong_hours_validation_config",
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_strong_hours_validation.ini",
        "BUY Validation",
    ),
    (
        "buy_strong_hours_m30m15_validation_config",
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.ini",
        "BUY Validation",
    ),
    (
        "buy_wide_stop_validation_config",
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_wide_stop_validation.ini",
        "BUY Validation",
    ),
    (
        "buy_hour03_wide_stop_validation_config",
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.ini",
        "BUY Validation",
    ),
    (
        "buy_hour03_wide_stop_calendar_validation_config",
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.ini",
        "BUY Validation",
    ),
    (
        "buy_score_weight_refit_config",
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_score_weight_refit.ini",
        "Score Weight",
    ),
    ("sell_entry_refit_config", "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_entry_refit.ini", "SELL Refit"),
    (
        "sell_regime_entry_refit_config",
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_regime_entry_refit.ini",
        "SELL Refit",
    ),
    (
        "sell_score_weight_refit_config",
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_score_weight_refit.ini",
        "Score Weight",
    ),
    (
        "sell_hour12_validation_config",
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_validation.ini",
        "SELL Validation",
    ),
    (
        "sell_hour12_m30m15_validation_config",
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_validation.ini",
        "SELL Validation",
    ),
    (
        "sell_hour12_m30m15_calendar_validation_config",
        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.ini",
        "SELL Validation",
    ),
    ("backtest_set", "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_backtest.set", "MT5 Back/Forward"),
    ("forward_set", "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_forward_test.set", "MT5 Back/Forward"),
    ("sample_collection_set", "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sample_collection.set", "Score Weight"),
    ("optimization_set", "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_optimization.set", "MT5 Optimization"),
    ("next_optimization_set", "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set", "MT5 Optimization"),
    (
        "stable_candidate_set",
        "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_stable_candidate_next.set",
        "MT5 Optimization",
    ),
    ("buy_refit_set", "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_refit.set", "BUY Refit"),
    ("buy_entry_refit_set", "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_entry_refit.set", "BUY Refit"),
    (
        "buy_hour03_validation_set",
        "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_validation.set",
        "BUY Validation",
    ),
    (
        "buy_strong_hours_validation_set",
        "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_strong_hours_validation.set",
        "BUY Validation",
    ),
    (
        "buy_strong_hours_m30m15_validation_set",
        "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.set",
        "BUY Validation",
    ),
    (
        "buy_wide_stop_validation_set",
        "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_wide_stop_validation.set",
        "BUY Validation",
    ),
    (
        "buy_hour03_wide_stop_validation_set",
        "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set",
        "BUY Validation",
    ),
    (
        "buy_hour03_wide_stop_calendar_validation_set",
        "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set",
        "BUY Validation",
    ),
    ("sell_entry_refit_set", "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sell_entry_refit.set", "SELL Refit"),
    (
        "sell_regime_entry_refit_set",
        "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sell_regime_entry_refit.set",
        "SELL Refit",
    ),
    (
        "sell_hour12_validation_set",
        "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sell_hour12_validation.set",
        "SELL Validation",
    ),
    (
        "sell_hour12_m30m15_validation_set",
        "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set",
        "SELL Validation",
    ),
    (
        "sell_hour12_m30m15_calendar_validation_set",
        "methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.set",
        "SELL Validation",
    ),
)

MQL5_MARKER_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "predictor_indicator": (
        "StringUpperCopy(eval.action)",
        "B %.1f/S %.1f M30 %s M15 %s",
        "Updated %s Spr %dpt Valid %s",
        "E %.2f   RR %.1f",
        "SL %.2f TP %.2f",
        "WAIT: SCORE LOW",
        "WAIT: SPREAD",
        "WAIT: NO DOMINANCE",
        "DRY-RUN ENTRY",
        "DRY-RUN SL",
        "DRY-RUN TP",
    ),
    "standalone_trader_ea": (
        "input bool InpSignalOnly",
        "input bool InpEnableTrading",
        "input bool InpAllowLiveTrading",
        "input bool InpRequireStrategyTester",
        "input bool InpUseDailyLossStop",
        "input int InpConsecutiveLossLimit",
        "input int InpConsecutiveLossCooldownMinutes",
        "input bool InpChartButtonDryRunOnly",
        "input bool InpAllowChartButtonTrading",
        "InpTesterMinClosedTrades",
        "InpTesterMinProfitFactor",
    ),
    "bridge_advisor_ea": (
        "input bool InpSaveOnlyMode",
        "input bool InpPollCodexTradeCommands",
        "input bool InpEnableTrading",
        "input bool InpAllowCodexTrading",
        "input double InpCodexMaxLot",
        "input bool InpCodexRequireSlTp",
        "/trade_command",
    ),
    "backtest_config": (
        "Expert=Swing_Evaluation_Trader.ex5",
        "ExpertParameters=Swing_Evaluation_Trader_backtest.set",
        "Symbol=XAUUSD-m",
        "Period=M1",
        "Model=4",
        "Optimization=0",
        "ForwardMode=0",
    ),
    "forward_config": (
        "Expert=Swing_Evaluation_Trader.ex5",
        "ExpertParameters=Swing_Evaluation_Trader_forward_test.set",
        "Symbol=XAUUSD-m",
        "Period=M1",
        "Model=4",
        "Optimization=0",
        "ForwardMode=3",
    ),
    "sample_collection_config": (
        "Expert=Swing_Evaluation_Trader.ex5",
        "ExpertParameters=Swing_Evaluation_Trader_sample_collection.set",
        "Symbol=XAUUSD-m",
        "Period=M1",
        "Model=4",
        "Optimization=0",
        "ForwardMode=3",
    ),
    "backtest_set": (
        "InpSignalOnly=false||false||0||true||N",
        "InpEnableTrading=true||false||0||true||N",
        "InpAllowLiveTrading=true||false||0||true||N",
        "InpRequireStrategyTester=true||false||0||true||N",
        "InpLot=0.10||0.10||0.01||0.30||N",
        "InpMaxTotalLot=0.30||0.30||0.10||0.50||N",
        "InpUseDailyLossStop=true||false||0||true||N",
        "InpUseConsecutiveLossStop=true||false||0||true||N",
        "InpConsecutiveLossLimit=20||20||1||30||N",
        "InpConsecutiveLossCooldownMinutes=120||120||30||360||N",
        "InpChartButtonDryRunOnly=true||false||0||true||N",
        "InpAllowChartButtonTrading=false||false||0||true||N",
    ),
    "forward_set": (
        "InpSignalOnly=false||false||0||true||N",
        "InpEnableTrading=true||false||0||true||N",
        "InpAllowLiveTrading=true||false||0||true||N",
        "InpRequireStrategyTester=true||false||0||true||N",
        "InpLot=0.10||0.10||0.01||0.30||N",
        "InpMaxTotalLot=0.30||0.30||0.10||0.50||N",
        "InpUseDailyLossStop=true||false||0||true||N",
        "InpUseConsecutiveLossStop=true||false||0||true||N",
        "InpConsecutiveLossLimit=20||20||1||30||N",
        "InpConsecutiveLossCooldownMinutes=120||120||30||360||N",
        "InpChartButtonDryRunOnly=true||false||0||true||N",
        "InpAllowChartButtonTrading=false||false||0||true||N",
    ),
    "sample_collection_set": (
        "InpSignalOnly=false||false||0||true||N",
        "InpEnableTrading=true||false||0||true||N",
        "InpAllowLiveTrading=true||false||0||true||N",
        "InpRequireStrategyTester=true||false||0||true||N",
        "InpLot=0.10||0.10||0.01||0.30||N",
        "InpMaxTotalLot=0.30||0.30||0.10||0.50||N",
        "InpUseDailyLossStop=false||false||0||true||N",
        "InpUseConsecutiveLossStop=false||false||0||true||N",
        "InpConsecutiveLossLimit=20||20||1||30||N",
        "InpConsecutiveLossCooldownMinutes=120||120||30||360||N",
        "InpChartButtonDryRunOnly=true||false||0||true||N",
        "InpAllowChartButtonTrading=false||false||0||true||N",
    ),
}


def unique_markers(markers: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for marker in markers:
        if marker in seen:
            continue
        seen.add(marker)
        result.append(marker)
    return tuple(result)


def unique_non_empty_status_values(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in (None, ""):
            continue
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def expected_tester_config_parameters(relative_path: str) -> dict[str, str]:
    path = Path(relative_path)
    if path.suffix.lower() != ".ini" or "TesterConfigs" not in path.parts:
        return {}
    stem = path.stem
    if stem == "Swing_Evaluation_Trader_strategy_test":
        expert_parameters = "Swing_Evaluation_Trader_forward_test.set"
    elif stem == "Swing_Evaluation_Trader_stable_candidate":
        expert_parameters = "Swing_Evaluation_Trader_stable_candidate_next.set"
    else:
        expert_parameters = f"{stem}.set"
    single_test_stems = {
        "Swing_Evaluation_Trader_backtest",
        "Swing_Evaluation_Trader_forward_test",
        "Swing_Evaluation_Trader_strategy_test",
        "Swing_Evaluation_Trader_sample_collection",
    }
    return {
        "Expert": "Swing_Evaluation_Trader.ex5",
        "ExpertParameters": expert_parameters,
        "Symbol": "XAUUSD-m",
        "Period": "M1",
        "Model": "4",
        "Optimization": "0" if stem in single_test_stems else "2",
        "ForwardMode": "0" if stem == "Swing_Evaluation_Trader_backtest" else "3",
    }


def derived_mql5_artifact_markers(relative_path: str) -> tuple[str, ...]:
    path = Path(relative_path)
    if path.suffix.lower() == ".ini" and "TesterConfigs" in path.parts:
        parameters = expected_tester_config_parameters(relative_path)
        return tuple(f"{key}={value}" for key, value in parameters.items())
    if path.suffix.lower() == ".set" and "TesterSets" in path.parts:
        markers = [
            "InpSignalOnly=false||",
            "InpEnableTrading=true||",
            "InpAllowLiveTrading=true||",
            "InpRequireStrategyTester=true||",
            "InpDailyLossLimit=5000.0||",
            "InpConsecutiveLossLimit=20||",
            "InpConsecutiveLossCooldownMinutes=120||",
            "InpChartButtonDryRunOnly=true||",
            "InpAllowChartButtonTrading=false||",
        ]
        if path.name != "Swing_Evaluation_Trader_sample_collection.set":
            markers.extend(
                [
                    "InpUseDailyLossStop=true||",
                    "InpUseConsecutiveLossStop=true||",
                ]
            )
        return tuple(markers)
    return ()


def mql5_artifact_required_markers(name: str, relative_path: str) -> tuple[str, ...]:
    return unique_markers(
        [
            *MQL5_MARKER_REQUIREMENTS.get(name, ()),
            *derived_mql5_artifact_markers(relative_path),
        ]
    )

PROMOTION_READY_DECISIONS = {"ready", "pass", "passed", "approved", "promote"}
BACK_FORWARD_COMPLETE_STATES = {
    "executed_consistent",
    "executed_passed",
    "executed_usable",
    "executed_ok",
}
BACK_FORWARD_SAMPLE_SHORTAGE_STATES = {
    "back_forward_sample_shortage",
    "backtest_sample_shortage",
    "forward_sample_shortage",
}
BACK_FORWARD_REASON_PREFIXES = (
    "mt5_back_forward_not_executed:",
    "mt5_back_forward_executed_sample_shortage:",
    "mt5_back_forward_executed_not_adoptable:",
    "mt5_back_forward_decision:",
)
COMMAND_HINT_KEYS = (
    "command_text",
    "execute_command_text",
    "collect_only_command_text",
    "collect_only_note",
    "manual_collect_only_command_text",
    "execute_and_refresh_analysis_command_text",
    "execute_and_refresh_all_command_text",
    "manual_collect_execute_and_refresh_analysis_command_text",
    "manual_collect_execute_and_refresh_all_command_text",
    "execute_hint",
)


def load_json_if_present(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def generated_at_from_payload(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("summary"), dict):
        return str(payload["summary"].get("generated_at") or payload.get("generated_at") or "")
    return str(payload.get("runner_generated_at") or payload.get("generated_at") or "")


def extract_command_hints(payload: dict[str, Any]) -> dict[str, str]:
    hints: dict[str, str] = {}
    for key in COMMAND_HINT_KEYS:
        value = payload.get(key)
        if value not in (None, ""):
            hints[key] = str(value)
    return hints


def manual_strategy_tester_summary(payload: dict[str, Any]) -> dict[str, Any]:
    manual_plan = (
        payload.get("manual_strategy_tester")
        if isinstance(payload.get("manual_strategy_tester"), dict)
        else {}
    )
    steps = manual_plan.get("steps") if isinstance(manual_plan.get("steps"), list) else []
    if not manual_plan and not steps:
        return {}
    return {
        "manual_strategy_tester_available": manual_plan.get("available", bool(steps)),
        "manual_collect_only_command_text": manual_plan.get("recommended_collect_only_command_text", ""),
        "manual_run_start_after": manual_plan.get("manual_run_start_after", ""),
        "manual_step_count": len(steps),
        "manual_steps": steps,
    }


def mt5_strategy_tester_pack_summary(payload: dict[str, Any]) -> dict[str, Any]:
    pack = (
        payload.get("mt5_strategy_tester_pack")
        if isinstance(payload.get("mt5_strategy_tester_pack"), dict)
        else {}
    )
    steps = pack.get("steps") if isinstance(pack.get("steps"), list) else []
    if not pack and not steps:
        return {}
    return {
        "mt5_strategy_tester_pack": pack,
        "mt5_strategy_tester_pack_available": pack.get("available", bool(steps)),
        "mt5_strategy_tester_pack_ready_for_manual_mt5_run": pack.get(
            "ready_for_manual_mt5_run", ""
        ),
        "mt5_strategy_tester_pack_status": pack.get("status", ""),
        "mt5_strategy_tester_pack_next_action": pack.get("next_action", ""),
        "mt5_strategy_tester_pack_is_back_forward_pair": pack.get("is_back_forward_pair", ""),
        "mt5_strategy_tester_pack_manual_run_start_after": pack.get("manual_run_start_after", ""),
        "mt5_strategy_tester_pack_collect_command_text": pack.get("collect_command_text", ""),
        "mt5_strategy_tester_pack_collect_ready": pack.get("collect_ready", ""),
        "mt5_strategy_tester_pack_collect_status": pack.get("collect_status", ""),
        "mt5_strategy_tester_pack_collect_reason": pack.get("collect_reason", ""),
        "mt5_strategy_tester_pack_collect_note": pack.get("collect_note", ""),
        "mt5_strategy_tester_pack_step_count": pack.get("step_count", len(steps)),
        "mt5_strategy_tester_pack_steps": steps,
    }


def mt5_operator_handoff_summary(payload: dict[str, Any]) -> dict[str, Any]:
    handoff = (
        payload.get("mt5_operator_handoff")
        if isinstance(payload.get("mt5_operator_handoff"), dict)
        else {}
    )
    if not handoff:
        return {}
    next_step = (
        handoff.get("next_mt5_step")
        if isinstance(handoff.get("next_mt5_step"), dict)
        else {}
    )
    quick_input = (
        handoff.get("quick_input")
        if isinstance(handoff.get("quick_input"), dict)
        else {}
    )
    return {
        "mt5_operator_handoff_state": handoff.get("state", ""),
        "mt5_operator_handoff_recommended_path": handoff.get("recommended_path", ""),
        "mt5_operator_handoff_manual_strategy_tester_available": handoff.get(
            "manual_strategy_tester_available", ""
        ),
        "mt5_operator_handoff_terminal_running": handoff.get("terminal_running", ""),
        "mt5_operator_handoff_auto_launch_blocked_by_running_terminal": handoff.get(
            "auto_launch_blocked_by_running_terminal", ""
        ),
        "mt5_operator_handoff_auto_launch_blockers": handoff.get("auto_launch_blockers", []),
        "mt5_operator_handoff_next_queue_id": next_step.get("queue_id", ""),
        "mt5_operator_handoff_next_step_label": next_step.get("step_label", ""),
        "mt5_operator_handoff_next_forward": next_step.get("forward", ""),
        "mt5_operator_handoff_next_inputs": next_step.get("inputs", ""),
        "mt5_operator_handoff_next_report": next_step.get("report", ""),
        "mt5_operator_handoff_next_step_operator_summary": (
            handoff.get("next_step_operator_summary") or operator_step_summary(next_step)
        ),
        "mt5_operator_handoff_next_step_summary": (
            handoff.get("next_step_summary")
            or handoff.get("next_step_operator_summary")
            or operator_step_summary(next_step)
        ),
        "mt5_operator_handoff_next_step_collect_filter_summary": (
            handoff.get("next_step_collect_filter_summary")
            or operator_collect_filter_summary(next_step)
        ),
        **quick_input_summary_fields(
            "mt5_operator_handoff_quick",
            quick_input,
            fallback=next_step,
        ),
        "mt5_operator_handoff_collect_execute_command_text": handoff.get(
            "manual_collect_execute_command_text", ""
        ),
        "mt5_operator_handoff_collect_execute_and_refresh_analysis_command_text": handoff.get(
            "manual_collect_execute_and_refresh_analysis_command_text", ""
        ),
        "mt5_operator_handoff_collect_execute_and_refresh_all_command_text": handoff.get(
            "manual_collect_execute_and_refresh_all_command_text", ""
        ),
        "mt5_operator_handoff_collect_execute_and_refresh_full_analysis_command_text": (
            handoff.get("manual_collect_execute_and_refresh_full_analysis_command_text")
            or handoff.get("manual_collect_execute_and_refresh_all_command_text", "")
        ),
        "mt5_operator_handoff_bridge_required_for_standalone_tester": handoff.get(
            "bridge_required_for_standalone_tester", ""
        ),
        "mt5_operator_handoff_bridge_ready_for_mt5_validation": handoff.get(
            "bridge_ready_for_mt5_validation", ""
        ),
        "mt5_operator_handoff_bridge_status": handoff.get("bridge_status", ""),
    }


def split_queue_step(queue_step: str) -> tuple[str, str]:
    if "/" not in queue_step:
        return "", queue_step
    queue_id, step_label = queue_step.split("/", 1)
    return queue_id, step_label


def value_present(value: Any) -> bool:
    return value not in ("", None, [], {})


def first_present(*values: Any) -> Any:
    for value in values:
        if value_present(value):
            return value
    return ""


def mt5_operator_summary_fields(payload: dict[str, Any]) -> dict[str, Any]:
    summary = (
        payload.get("operator_summary")
        if isinstance(payload.get("operator_summary"), dict)
        else {}
    )
    top_level_quick_input = (
        payload.get("mt5_next_quick_input")
        if isinstance(payload.get("mt5_next_quick_input"), dict)
        else {}
    )
    has_top_level_alias = any(
        value_present(payload.get(key))
        for key in (
            "mt5_next_operator_action",
            "mt5_next_queue_step",
            "mt5_next_step_operator_summary",
            "mt5_next_step_collect_filter_summary",
            "mt5_collect_dry_run_command_text",
            "mt5_collect_execute_command_text",
        )
    )
    if not summary and not has_top_level_alias and not top_level_quick_input:
        return {}
    next_step = (
        summary.get("manual_test_queue_next_launch_step")
        if isinstance(summary.get("manual_test_queue_next_launch_step"), dict)
        else {}
    )
    if not next_step:
        next_step = (
            summary.get("manual_queue_launch_queue_operator_handoff_next_mt5_step")
            if isinstance(summary.get("manual_queue_launch_queue_operator_handoff_next_mt5_step"), dict)
            else {}
        )
    if not next_step and top_level_quick_input:
        queue_step = str(
            payload.get("mt5_next_queue_step")
            or top_level_quick_input.get("queue_step")
            or ""
        )
        queue_id, step_label = split_queue_step(queue_step)
        next_step = {
            "queue_id": queue_id,
            "step_label": step_label,
            "purpose": top_level_quick_input.get("purpose", ""),
            "expert": top_level_quick_input.get("expert", ""),
            "symbol": top_level_quick_input.get("symbol", ""),
            "period": top_level_quick_input.get("period", ""),
            "model": top_level_quick_input.get("model", ""),
            "from_date": top_level_quick_input.get("from_date", ""),
            "to_date": top_level_quick_input.get("to_date", ""),
            "dates": top_level_quick_input.get("dates", ""),
            "forward": top_level_quick_input.get("forward", ""),
            "forward_mode": top_level_quick_input.get("forward_mode", ""),
            "optimization_label": top_level_quick_input.get("optimization_label", ""),
            "inputs": top_level_quick_input.get("inputs", ""),
            "report": top_level_quick_input.get("report", ""),
            "expected_report_artifact": top_level_quick_input.get(
                "expected_report_artifact", ""
            ),
            "expected_artifacts": top_level_quick_input.get("expected_artifacts", {}),
            "step_fingerprint": top_level_quick_input.get("step_fingerprint", ""),
            "step_config_fingerprint": top_level_quick_input.get(
                "step_config_fingerprint", ""
            ),
            "step_run_fingerprint": top_level_quick_input.get("step_run_fingerprint", ""),
            "launch_command_kind": top_level_quick_input.get("launch_kind", ""),
            "manual_run_start_after": (
                payload.get("mt5_next_manual_run_start_effective_after")
                or top_level_quick_input.get("manual_run_start_after", "")
            ),
        }
    quick_input = (
        top_level_quick_input
        if top_level_quick_input
        else summary.get("mt5_operator_handoff_quick_input")
        if isinstance(summary.get("mt5_operator_handoff_quick_input"), dict)
        else summary.get("manual_test_queue_quick_input")
        if isinstance(summary.get("manual_test_queue_quick_input"), dict)
        else {}
    )
    next_step_fingerprint = (
        next_step.get("step_fingerprint")
        or quick_input.get("step_fingerprint", "")
        or summary.get("manual_queue_launch_selected_step_fingerprint", "")
    )
    next_step_config_fingerprint = (
        next_step.get("step_config_fingerprint")
        or quick_input.get("step_config_fingerprint", "")
        or summary.get("manual_queue_launch_selected_step_config_fingerprint", "")
    )
    next_step_run_fingerprint = (
        next_step.get("step_run_fingerprint")
        or quick_input.get("step_run_fingerprint", "")
        or summary.get("manual_queue_launch_selected_step_run_fingerprint", "")
    )
    return {
        "mt5_operator_summary_next_operator_action": first_present(
            summary.get(
                "manual_operator_packet_with_optimization_next_operator_action", ""
            ),
            payload.get("mt5_next_operator_action"),
        ),
        "mt5_operator_summary_next_operator_mode": first_present(
            summary.get("manual_operator_packet_with_optimization_next_operator_mode", ""),
            payload.get("mt5_next_operator_mode"),
        ),
        "mt5_operator_summary_next_operator_launch_state": first_present(
            summary.get(
                "manual_operator_packet_with_optimization_next_operator_launch_state", ""
            ),
            payload.get("mt5_next_operator_launch_state"),
        ),
        "mt5_operator_summary_manual_queue_status": first_present(
            summary.get("manual_test_queue_status", ""),
            payload.get("mt5_manual_queue_status"),
        ),
        "mt5_operator_summary_manual_queue_next_action": summary.get("manual_test_queue_next_action", ""),
        "mt5_operator_summary_manual_queue_progress_state": first_present(
            summary.get("manual_test_queue_progress_state", ""),
            payload.get("mt5_manual_queue_progress_state"),
        ),
        "mt5_operator_summary_manual_queue_entries": summary.get("manual_test_queue_entry_count", ""),
        "mt5_operator_summary_manual_queue_steps": summary.get("manual_test_queue_step_count", ""),
        "mt5_operator_summary_manual_queue_waiting": first_present(
            summary.get("manual_test_queue_waiting_count", ""),
            payload.get("mt5_manual_queue_waiting_count"),
        ),
        "mt5_operator_summary_manual_queue_step_ready": summary.get(
            "manual_test_queue_step_report_ready_count", ""
        ),
        "mt5_operator_summary_manual_queue_step_collect_ready": summary.get(
            "manual_test_queue_step_collect_ready_count", ""
        ),
        "mt5_operator_summary_manual_queue_step_waiting": summary.get(
            "manual_test_queue_step_waiting_report_count", ""
        ),
        "mt5_operator_summary_manual_queue_launch_needed": first_present(
            summary.get("manual_test_queue_step_launch_needed_count", ""),
            payload.get("mt5_manual_queue_step_launch_needed_count", ""),
        ),
        "mt5_operator_summary_manual_queue_step_report_ready_ids": summary.get(
            "manual_test_queue_step_report_ready_ids", []
        ),
        "mt5_operator_summary_manual_queue_step_collect_ready_ids": summary.get(
            "manual_test_queue_step_collect_ready_ids", []
        ),
        "mt5_operator_summary_manual_queue_step_waiting_report_ids": summary.get(
            "manual_test_queue_step_waiting_report_ids", []
        ),
        "mt5_operator_summary_manual_queue_step_launch_needed_ids": summary.get(
            "manual_test_queue_step_launch_needed_ids", []
        ),
        "mt5_operator_summary_manual_queue_collect_check_command_text": summary.get(
            "manual_test_queue_collect_check_command_text", ""
        ),
        "mt5_operator_summary_launch_status": summary.get("manual_queue_launch_status", ""),
        "mt5_operator_summary_launch_next_action": summary.get("manual_queue_launch_next_action", ""),
        "mt5_operator_summary_launch_kind": summary.get("manual_queue_launch_launch_command_kind", ""),
        "mt5_operator_summary_launch_blocked_reasons": summary.get(
            "manual_queue_launch_blocked_reasons", []
        ),
        "mt5_operator_summary_collect_status": summary.get("manual_collect_run_status", ""),
        "mt5_operator_summary_collect_next_action": summary.get("manual_collect_run_next_action", ""),
        "mt5_operator_summary_collect_selected": summary.get("manual_collect_run_selected_count", ""),
        "mt5_operator_summary_collect_waiting": summary.get("manual_collect_run_waiting_count", ""),
        "mt5_operator_summary_next_queue_id": next_step.get("queue_id", ""),
        "mt5_operator_summary_next_step_label": next_step.get("step_label", ""),
        "mt5_operator_summary_next_symbol": next_step.get("symbol", ""),
        "mt5_operator_summary_next_period": next_step.get("period", ""),
        "mt5_operator_summary_next_dates": next_step.get("dates", ""),
        "mt5_operator_summary_next_forward": next_step.get("forward", ""),
        "mt5_operator_summary_next_inputs": next_step.get("inputs", ""),
        "mt5_operator_summary_next_report": next_step.get("report", ""),
        "mt5_operator_summary_next_step_fingerprint": next_step_fingerprint,
        "mt5_operator_summary_next_step_config_fingerprint": next_step_config_fingerprint,
        "mt5_operator_summary_next_step_run_fingerprint": next_step_run_fingerprint,
        "mt5_operator_summary_next_expected_report_artifact": next_step.get(
            "expected_report_artifact", ""
        ),
        "mt5_operator_summary_next_expected_artifacts": (
            next_step.get("expected_artifacts")
            if isinstance(next_step.get("expected_artifacts"), dict)
            else {}
        ),
        "mt5_operator_summary_next_step_operator_summary": (
            payload.get("mt5_next_step_summary")
            or payload.get("mt5_next_step_operator_summary")
            or summary.get("mt5_operator_handoff_next_step_summary")
            or summary.get("mt5_operator_handoff_next_step_operator_summary")
            or summary.get("manual_test_queue_next_step_summary")
            or summary.get("manual_test_queue_next_step_operator_summary")
            or summary.get("manual_queue_launch_with_optimization_queue_operator_handoff_next_step_summary")
            or summary.get("manual_queue_launch_queue_operator_handoff_next_step_operator_summary")
            or summary.get("manual_collect_run_handoff_next_step_operator_summary")
            or operator_step_summary(next_step)
        ),
        "mt5_operator_summary_next_step_summary": (
            payload.get("mt5_next_step_summary")
            or payload.get("mt5_next_step_operator_summary")
            or summary.get("mt5_operator_handoff_next_step_summary")
            or summary.get("mt5_operator_handoff_next_step_operator_summary")
            or summary.get("manual_test_queue_next_step_summary")
            or summary.get("manual_test_queue_next_step_operator_summary")
            or summary.get("manual_queue_launch_with_optimization_queue_operator_handoff_next_step_summary")
            or summary.get("manual_queue_launch_queue_operator_handoff_next_step_operator_summary")
            or summary.get("manual_collect_run_handoff_next_step_operator_summary")
            or operator_step_summary(next_step)
        ),
        "mt5_operator_summary_next_step_collect_filter_summary": (
            payload.get("mt5_next_step_collect_filter_summary")
            or summary.get("mt5_operator_handoff_next_step_collect_filter_summary")
            or summary.get("manual_test_queue_next_step_collect_filter_summary")
            or summary.get(
                "manual_queue_launch_queue_operator_handoff_next_step_collect_filter_summary"
            )
            or summary.get("manual_collect_run_handoff_next_step_collect_filter_summary")
            or operator_collect_filter_summary(next_step)
        ),
        "mt5_operator_summary_launch_selected_step_fingerprint": summary.get(
            "manual_queue_launch_selected_step_fingerprint", ""
        ),
        "mt5_operator_summary_launch_selected_expected_report": summary.get(
            "manual_queue_launch_selected_expected_report", ""
        ),
        "mt5_operator_summary_launch_selected_expected_report_artifact": summary.get(
            "manual_queue_launch_selected_expected_report_artifact", ""
        ),
        "mt5_operator_summary_operator_packet_back_forward_quick_start_status": first_present(
            summary.get(
                "manual_operator_packet_with_optimization_back_forward_quick_start_status",
                "",
            ),
            payload.get("mt5_back_forward_quick_start_status", ""),
        ),
        "mt5_operator_summary_operator_packet_back_forward_quick_start_step_count": summary.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_step_count",
            "",
        ),
        "mt5_operator_summary_operator_packet_back_forward_quick_start_waiting_step_count": summary.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_waiting_step_count",
            "",
        ),
        "mt5_operator_summary_operator_packet_back_forward_quick_start_current_queue_step": summary.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_current_queue_step",
            "",
        ),
        "mt5_operator_summary_operator_packet_back_forward_quick_start_collect_command_text": first_present(
            summary.get(
                "manual_operator_packet_with_optimization_back_forward_quick_start_collect_command_text",
                "",
            ),
            payload.get("mt5_back_forward_quick_start_collect_command_text", ""),
        ),
        **quick_input_summary_fields(
            "mt5_operator_summary_quick",
            quick_input,
            fallback=next_step,
        ),
        "mt5_operator_summary_collect_execute_command_text": first_present(
            summary.get(
                "manual_queue_launch_queue_operator_handoff_collect_execute_command_text",
                "",
            ),
            payload.get("mt5_collect_execute_command_text", ""),
        ),
        "mt5_operator_summary_collect_dry_run_command_text": first_present(
            summary.get(
                "manual_queue_launch_queue_operator_handoff_collect_dry_run_command_text",
                "",
            ),
            payload.get("mt5_collect_dry_run_command_text"),
        ),
        "mt5_operator_summary_next_manual_run_start_effective_after": first_present(
            summary.get(
                "manual_operator_packet_with_optimization_manual_run_start_effective_after",
                "",
            ),
            payload.get("mt5_next_manual_run_start_effective_after"),
        ),
        "mt5_operator_summary_auto_launch_command_available": first_present(
            summary.get(
                "manual_operator_packet_with_optimization_auto_launch_command_available",
                "",
            ),
            payload.get("mt5_auto_launch_command_available"),
        ),
        "mt5_operator_summary_auto_launch_blocked": first_present(
            summary.get("manual_operator_packet_with_optimization_auto_launch_blocked", ""),
            payload.get("mt5_auto_launch_blocked"),
        ),
        "mt5_operator_summary_auto_launch_blocked_reasons": first_present(
            summary.get(
                "manual_operator_packet_with_optimization_auto_launch_blocked_reasons",
                [],
            ),
            payload.get("mt5_auto_launch_blocked_reasons"),
        ),
        "mt5_operator_summary_strategy_operator_decision_verdict": first_present(
            summary.get(
                "manual_operator_packet_with_optimization_strategy_operator_decision_verdict",
                "",
            ),
            payload.get("mt5_strategy_operator_decision_verdict"),
        ),
        "mt5_operator_summary_strategy_operator_decision_primary_blocker": first_present(
            summary.get(
                "manual_operator_packet_with_optimization_strategy_operator_decision_primary_blocker",
                "",
            ),
            payload.get("mt5_strategy_operator_decision_primary_blocker"),
        ),
        "mt5_operator_summary_strategy_operator_decision_command_text": first_present(
            summary.get(
                "manual_operator_packet_with_optimization_strategy_operator_decision_command_text",
                "",
            ),
            payload.get("mt5_strategy_operator_decision_command_text"),
        ),
        "mt5_operator_summary_collect_execute_and_refresh_analysis_command_text": (
            payload.get("mt5_collect_execute_and_refresh_analysis_command_text", "")
            or payload.get("mt5_collect_execute_and_refresh_command_text", "")
            or summary.get("manual_auto_collect_watch_collect_execute_and_refresh_analysis_command_text", "")
            or summary.get("manual_collect_execute_and_refresh_analysis_command_text", "")
            or summary.get(
                "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_analysis_command_text",
                "",
            )
        ),
        "mt5_operator_summary_collect_execute_and_refresh_all_command_text": (
            payload.get("mt5_collect_execute_and_refresh_full_analysis_command_text", "")
            or payload.get("mt5_collect_execute_and_refresh_all_command_text", "")
            or summary.get("manual_collect_execute_and_refresh_all_command_text", "")
            or summary.get(
                "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text",
                "",
            )
            or summary.get(
                "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_all_command_text",
                "",
            )
        ),
        "mt5_operator_summary_collect_execute_and_refresh_full_analysis_command_text": (
            payload.get("mt5_collect_execute_and_refresh_full_analysis_command_text", "")
            or payload.get("mt5_collect_execute_and_refresh_all_command_text", "")
            or summary.get("manual_collect_execute_and_refresh_full_analysis_command_text", "")
            or summary.get("manual_collect_execute_and_refresh_all_command_text", "")
            or summary.get(
                "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text",
                "",
            )
            or summary.get(
                "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_all_command_text",
                "",
            )
        ),
        "mt5_operator_summary_next_action_run_target": summary.get("next_action_run_target", ""),
        "mt5_operator_summary_next_action_run_kind": summary.get("next_action_run_kind", ""),
        "mt5_operator_summary_next_action_run_focus_side": summary.get(
            "next_action_run_focus_side", ""
        ),
        "mt5_operator_summary_next_action_run_optimization_mode": summary.get(
            "next_action_run_optimization_mode", ""
        ),
        "mt5_operator_summary_next_action_run_config": summary.get(
            "next_action_run_config", ""
        ),
        "mt5_operator_summary_next_action_run_set": summary.get("next_action_run_set", ""),
        "mt5_operator_summary_next_action_run_output_set": summary.get(
            "next_action_run_output_set", ""
        ),
        "mt5_operator_summary_next_action_run_current_for_execution": summary.get(
            "next_action_run_current_for_execution", ""
        ),
        "mt5_operator_summary_next_action_run_primary_execution_class": summary.get(
            "next_action_run_primary_execution_class", ""
        ),
        "mt5_operator_summary_next_action_run_primary_is_mt5_tester_run": summary.get(
            "next_action_run_primary_is_mt5_tester_run", ""
        ),
        "mt5_operator_summary_next_action_run_blocking_prior_action_count": summary.get(
            "next_action_run_blocking_prior_action_count", ""
        ),
        "mt5_operator_summary_next_action_run_timeout_seconds": summary.get(
            "next_action_run_timeout_seconds", ""
        ),
        "mt5_operator_summary_next_action_run_timeout_minutes": summary.get(
            "next_action_run_timeout_minutes", ""
        ),
        "mt5_operator_summary_next_action_run_timeout_note": summary.get(
            "next_action_run_timeout_note", ""
        ),
        "mt5_operator_summary_next_action_run_timeout_deadline_if_started_now": summary.get(
            "next_action_run_timeout_deadline_if_started_now", ""
        ),
        "mt5_operator_summary_next_action_run_optimized_input_count": summary.get(
            "next_action_run_optimized_input_count", ""
        ),
        "mt5_operator_summary_next_action_run_estimated_full_factorial_passes": summary.get(
            "next_action_run_estimated_full_factorial_passes", ""
        ),
        "mt5_operator_summary_next_action_run_latest_executed_tester_xml_rows": summary.get(
            "next_action_run_latest_executed_tester_xml_rows", ""
        ),
        "mt5_operator_summary_next_action_run_primary_planned_outputs": summary.get(
            "next_action_run_primary_planned_outputs", {}
        ),
        "mt5_operator_summary_next_action_run_execute_command_text": summary.get(
            "next_action_run_execute_command_text", ""
        ),
        "mt5_operator_summary_next_action_run_collect_only_command_text": summary.get(
            "next_action_run_collect_only_command_text", ""
        ),
    }


def manual_collect_readiness_summary(payload: dict[str, Any]) -> dict[str, Any]:
    readiness = (
        payload.get("manual_collect_readiness")
        if isinstance(payload.get("manual_collect_readiness"), dict)
        else {}
    )
    if not readiness:
        return {}
    return {
        "manual_collect_ready": readiness.get("ready", ""),
        "manual_collect_status": readiness.get("status", ""),
        "manual_collect_csv_count": readiness.get("csv_count", ""),
        "manual_collect_modified_after": readiness.get("modified_after", ""),
        "manual_collect_reason": readiness.get("reason", ""),
        "manual_collect_blocking_reasons": readiness.get("blocking_reasons", []),
        "manual_collect_next_action": readiness.get("next_action", ""),
        "manual_collect_steps": readiness.get("steps", []),
    }


def manual_test_queue_entry_summaries(entries: object) -> list[dict[str, Any]]:
    if not isinstance(entries, list):
        return []
    summaries: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("available") is not True:
            continue
        summaries.append(
            {
                "id": entry.get("id", ""),
                "title": entry.get("title", ""),
                "source_json": entry.get("source_json", ""),
                "runner_generated_at": entry.get("runner_generated_at") or entry.get("generated_at", ""),
                "promotion_generated_at": entry.get("promotion_generated_at", ""),
                "current_promotion_generated_at": entry.get("current_promotion_generated_at", ""),
                "promotion_decision": entry.get("promotion_decision", ""),
                "current_promotion_decision": entry.get("current_promotion_decision", ""),
                "selected_action_current": entry.get("selected_action_current", ""),
                "current_for_execution": entry.get("current_for_execution", ""),
                "step_count": entry.get("step_count", ""),
                "collect_ready": entry.get("collect_ready", ""),
                "collect_status": entry.get("collect_status", ""),
                "collect_next_action": entry.get("collect_next_action", ""),
                "manual_run_start_after": entry.get("manual_run_start_after", ""),
                "collect_modified_after": entry.get("collect_modified_after", ""),
                "collect_only_command_text": entry.get("collect_only_command_text", ""),
            }
        )
    return summaries


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


def manual_queue_entries_from_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for queue_name in ("mt5_manual_test_queue", "mt5_manual_test_queue_with_optimization"):
        queue = artifact_by_name(artifacts, queue_name)
        queue_entries = (
            queue.get("manual_queue_entries")
            if isinstance(queue.get("manual_queue_entries"), list)
            else []
        )
        for entry in queue_entries:
            if isinstance(entry, dict):
                entries.append(entry)
    return entries


def manual_queue_entry_by_id(
    artifacts: list[dict[str, Any]],
    entry_ids: tuple[str, ...],
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    wanted = {str(item) for item in entry_ids if str(item)}
    if not wanted:
        return {}
    for entry in manual_queue_entries_from_artifacts(artifacts):
        if str(entry.get("id") or "") not in wanted:
            continue
        if manual_queue_entry_source_matches(entry, source_path):
            return entry
    return {}


def manual_queue_entry_for_next_action_summary(
    runner: dict[str, Any],
    artifacts: list[dict[str, Any]],
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    target = str(runner.get("target") or "")
    if "score_weight" not in target:
        return {}
    focus_side = str(runner.get("focus_side") or "").strip().lower()
    entry_ids: list[str] = []
    if focus_side in {"buy", "sell"}:
        entry_ids.append(f"score_weight_{focus_side}")
    entry_ids.extend(["score_weight_sell", "score_weight_buy"])
    return manual_queue_entry_by_id(artifacts, tuple(entry_ids), source_path=source_path)


def apply_manual_queue_collect_override_to_back_forward(
    back_forward: dict[str, Any],
    entry: dict[str, Any],
) -> None:
    collect_command = str(entry.get("collect_only_command_text") or "")
    manual_run_start_after = str(entry.get("manual_run_start_after") or "")
    collect_modified_after = str(entry.get("collect_modified_after") or manual_run_start_after)
    if collect_command:
        back_forward["manual_collect_only_command_text"] = collect_command
        back_forward["mt5_strategy_tester_pack_collect_command_text"] = collect_command
        execution_hints = back_forward.get("execution_hints")
        if isinstance(execution_hints, dict):
            execution_hints["collect_only_command_text"] = collect_command
        pack = back_forward.get("mt5_strategy_tester_pack")
        if isinstance(pack, dict):
            pack["collect_command_text"] = collect_command
    if manual_run_start_after:
        back_forward["manual_run_start_after"] = manual_run_start_after
        back_forward["mt5_strategy_tester_pack_manual_run_start_after"] = manual_run_start_after
        pack = back_forward.get("mt5_strategy_tester_pack")
        if isinstance(pack, dict):
            pack["manual_run_start_after"] = manual_run_start_after
    if collect_modified_after:
        back_forward["manual_collect_modified_after"] = collect_modified_after


def apply_manual_queue_collect_override_to_next_action(
    runner: dict[str, Any],
    entry: dict[str, Any],
) -> None:
    collect_command = str(entry.get("collect_only_command_text") or "")
    manual_run_start_after = str(entry.get("manual_run_start_after") or "")
    collect_modified_after = str(entry.get("collect_modified_after") or manual_run_start_after)
    if collect_command:
        runner["collect_only_command_text"] = collect_command
        runner["manual_collect_only_command_text"] = collect_command
        execution_hints = runner.get("execution_hints")
        if isinstance(execution_hints, dict):
            execution_hints["collect_only_command_text"] = collect_command
        nested_runner = runner.get("next_action_runner")
        if isinstance(nested_runner, dict):
            nested_runner["collect_only_command_text"] = collect_command
            nested_runner["manual_collect_only_command_text"] = collect_command
    if manual_run_start_after:
        runner["manual_run_start_after"] = manual_run_start_after
        nested_runner = runner.get("next_action_runner")
        if isinstance(nested_runner, dict):
            nested_runner["manual_run_start_after"] = manual_run_start_after
    if collect_modified_after:
        runner["manual_collect_modified_after"] = collect_modified_after
        nested_runner = runner.get("next_action_runner")
        if isinstance(nested_runner, dict):
            nested_runner["manual_collect_modified_after"] = collect_modified_after


def apply_manual_queue_collect_overrides_to_runtime_artifacts(
    artifacts: list[dict[str, Any]],
) -> None:
    back_forward = artifact_by_name(artifacts, "mt5_back_forward_run")
    back_forward_entry = manual_queue_entry_by_id(
        artifacts,
        ("back_forward",),
        source_path=back_forward.get("path") or "runtime/latest_mt5_back_forward_run.json",
    )
    if back_forward and back_forward_entry:
        apply_manual_queue_collect_override_to_back_forward(back_forward, back_forward_entry)
    for artifact_name in ("mt5_next_action_run", "mt5_next_action_run_buy"):
        runner = artifact_by_name(artifacts, artifact_name)
        if not runner:
            continue
        entry = manual_queue_entry_for_next_action_summary(
            runner,
            artifacts,
            source_path=runner.get("path"),
        )
        if entry:
            apply_manual_queue_collect_override_to_next_action(runner, entry)


def manual_test_queue_current_gate_summary(entries: object) -> dict[str, Any]:
    if not isinstance(entries, list):
        return {
            "manual_queue_current_for_execution_count": 0,
            "manual_queue_selected_action_current_count": 0,
            "manual_queue_selected_action_stale_count": 0,
            "manual_queue_current_promotion_generated_at_values": [],
            "manual_queue_current_promotion_decision_values": [],
            "manual_queue_gate_stale_reasons": [],
            "manual_queue_not_current_entry_ids": [],
        }
    current_for_execution_count = 0
    selected_action_current_count = 0
    selected_action_stale_count = 0
    current_gate_values: list[str] = []
    current_decision_values: list[str] = []
    gate_stale_reasons: list[str] = []
    not_current_entry_ids: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id") or entry.get("queue_id") or entry.get("target") or "")
        if entry.get("current_for_execution") is True:
            current_for_execution_count += 1
        elif entry.get("current_for_execution") is False and entry_id:
            not_current_entry_ids.append(entry_id)
        if entry.get("selected_action_current") is True:
            selected_action_current_count += 1
        elif entry.get("selected_action_current") is False:
            selected_action_stale_count += 1
            if entry_id:
                not_current_entry_ids.append(entry_id)
        current_gate_values.append(str(entry.get("current_promotion_generated_at") or ""))
        current_decision_values.append(str(entry.get("current_promotion_decision") or ""))
        gate_stale_reasons.append(str(entry.get("gate_stale_reason") or ""))
    return {
        "manual_queue_current_for_execution_count": current_for_execution_count,
        "manual_queue_selected_action_current_count": selected_action_current_count,
        "manual_queue_selected_action_stale_count": selected_action_stale_count,
        "manual_queue_current_promotion_generated_at_values": unique_non_empty_status_values(
            current_gate_values
        ),
        "manual_queue_current_promotion_decision_values": unique_non_empty_status_values(
            current_decision_values
        ),
        "manual_queue_gate_stale_reasons": unique_non_empty_status_values(gate_stale_reasons),
        "manual_queue_not_current_entry_ids": unique_non_empty_status_values(not_current_entry_ids),
    }


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


def quick_input_summary_fields(
    prefix: str,
    quick_input: dict[str, Any],
    *,
    fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = quick_input if isinstance(quick_input, dict) else {}
    fallback_source = fallback if isinstance(fallback, dict) else {}
    expected_artifacts = source.get("expected_artifacts")
    if not isinstance(expected_artifacts, dict):
        expected_artifacts = fallback_source.get("expected_artifacts")
    if not isinstance(expected_artifacts, dict):
        expected_artifacts = {}
    return {
        f"{prefix}_input": source,
        f"{prefix}_queue_step": source.get("queue_step", ""),
        f"{prefix}_purpose": source.get("purpose", ""),
        f"{prefix}_step_fingerprint": source.get(
            "step_fingerprint",
            fallback_source.get("step_fingerprint", ""),
        ),
        f"{prefix}_step_config_fingerprint": source.get(
            "step_config_fingerprint",
            fallback_source.get("step_config_fingerprint", ""),
        ),
        f"{prefix}_step_run_fingerprint": source.get(
            "step_run_fingerprint",
            fallback_source.get("step_run_fingerprint", ""),
        ),
        f"{prefix}_expert": source.get("expert", fallback_source.get("expert", "")),
        f"{prefix}_symbol": source.get("symbol", fallback_source.get("symbol", "")),
        f"{prefix}_period": source.get("period", fallback_source.get("period", "")),
        f"{prefix}_model": source.get("model", fallback_source.get("model", "")),
        f"{prefix}_from_date": source.get("from_date", fallback_source.get("from_date", "")),
        f"{prefix}_to_date": source.get("to_date", fallback_source.get("to_date", "")),
        f"{prefix}_dates": source.get("dates", fallback_source.get("dates", "")),
        f"{prefix}_forward": source.get("forward", fallback_source.get("forward", "")),
        f"{prefix}_forward_mode": source.get(
            "forward_mode",
            fallback_source.get("forward_mode", ""),
        ),
        f"{prefix}_optimization_label": source.get(
            "optimization_label",
            optimization_label_for_item(fallback_source),
        ),
        f"{prefix}_inputs": source.get("inputs", fallback_source.get("inputs", "")),
        f"{prefix}_report": source.get("report", fallback_source.get("report", "")),
        f"{prefix}_expected_report_artifact": source.get(
            "expected_report_artifact",
            fallback_source.get("expected_report_artifact", ""),
        ),
        f"{prefix}_expected_artifacts": expected_artifacts,
        f"{prefix}_launch_kind": source.get(
            "launch_kind",
            fallback_source.get("launch_command_kind", ""),
        ),
        f"{prefix}_manual_run_start_after": source.get(
            "manual_run_start_after",
            fallback_source.get("manual_run_start_after", ""),
        ),
    }


def manual_test_queue_operator_handoff_summary(payload: dict[str, Any]) -> dict[str, Any]:
    handoff = (
        payload.get("operator_handoff")
        if isinstance(payload.get("operator_handoff"), dict)
        else {}
    )
    if not handoff:
        return {}
    next_step = (
        handoff.get("next_mt5_step")
        if isinstance(handoff.get("next_mt5_step"), dict)
        else {}
    )
    quick_input = (
        handoff.get("quick_input")
        if isinstance(handoff.get("quick_input"), dict)
        else {}
    )
    return {
        "manual_queue_operator_handoff_state": handoff.get("state", ""),
        "manual_queue_operator_handoff_progress_state": handoff.get("progress_state", ""),
        "manual_queue_operator_handoff_status": handoff.get("status", ""),
        "manual_queue_operator_handoff_next_action": handoff.get("next_action", ""),
        "manual_queue_operator_handoff_step_report_ready_count": handoff.get(
            "step_report_ready_count", ""
        ),
        "manual_queue_operator_handoff_step_collect_ready_count": handoff.get(
            "step_collect_ready_count", ""
        ),
        "manual_queue_operator_handoff_step_waiting_report_count": handoff.get(
            "step_waiting_report_count", ""
        ),
        "manual_queue_operator_handoff_step_launch_needed_count": handoff.get(
            "step_launch_needed_count", ""
        ),
        "manual_queue_operator_handoff_step_report_ready_ids": handoff.get(
            "step_report_ready_ids", []
        ),
        "manual_queue_operator_handoff_step_collect_ready_ids": handoff.get(
            "step_collect_ready_ids", []
        ),
        "manual_queue_operator_handoff_step_waiting_report_ids": handoff.get(
            "step_waiting_report_ids", []
        ),
        "manual_queue_operator_handoff_step_launch_needed_ids": handoff.get(
            "step_launch_needed_ids", []
        ),
        "manual_queue_operator_handoff_collect_ready": handoff.get("collect_ready", ""),
        "manual_queue_operator_handoff_ready_entry_ids": handoff.get("ready_entry_ids", []),
        "manual_queue_operator_handoff_waiting_entry_ids": handoff.get("waiting_entry_ids", []),
        "manual_queue_operator_handoff_stale_entry_ids": handoff.get("stale_entry_ids", []),
        "manual_queue_operator_handoff_next_queue_id": next_step.get("queue_id", ""),
        "manual_queue_operator_handoff_next_step_label": next_step.get("step_label", ""),
        "manual_queue_operator_handoff_next_symbol": next_step.get("symbol", ""),
        "manual_queue_operator_handoff_next_period": next_step.get("period", ""),
        "manual_queue_operator_handoff_next_model": next_step.get("model", ""),
        "manual_queue_operator_handoff_next_dates": next_step.get("dates", ""),
        "manual_queue_operator_handoff_next_forward": next_step.get("forward", ""),
        "manual_queue_operator_handoff_next_optimization": next_step.get("optimization", ""),
        "manual_queue_operator_handoff_next_optimization_label": optimization_label_for_item(next_step),
        "manual_queue_operator_handoff_next_optimization_enabled": next_step.get(
            "optimization_enabled", ""
        ),
        "manual_queue_operator_handoff_next_run_type": next_step.get("run_type", ""),
        "manual_queue_operator_handoff_next_expected_report_artifact": next_step.get(
            "expected_report_artifact", ""
        ),
        "manual_queue_operator_handoff_next_inputs": next_step.get("inputs", ""),
        "manual_queue_operator_handoff_next_report": next_step.get("report", ""),
        "manual_queue_operator_handoff_next_step_operator_summary": (
            handoff.get("next_step_operator_summary") or operator_step_summary(next_step)
        ),
        "manual_queue_operator_handoff_next_step_summary": (
            handoff.get("next_step_summary")
            or handoff.get("next_step_operator_summary")
            or operator_step_summary(next_step)
        ),
        "manual_queue_operator_handoff_next_step_collect_filter_summary": (
            handoff.get("next_step_collect_filter_summary")
            or operator_collect_filter_summary(next_step)
        ),
        "manual_queue_operator_handoff_next_launch_needed": next_step.get("launch_needed", ""),
        "manual_queue_operator_handoff_next_launch_command_kind": next_step.get(
            "launch_command_kind", ""
        ),
        **quick_input_summary_fields(
            "manual_queue_operator_handoff_quick",
            quick_input,
            fallback=next_step,
        ),
        "manual_queue_operator_handoff_dry_run_command_text": handoff.get(
            "dry_run_command_text", ""
        ),
        "manual_queue_operator_handoff_collect_check_command_text": handoff.get(
            "collect_check_command_text", ""
        ),
        "manual_queue_operator_handoff_execute_command_text": handoff.get(
            "execute_command_text", ""
        ),
        "manual_queue_operator_handoff_execute_and_refresh_analysis_command_text": handoff.get(
            "execute_and_refresh_analysis_command_text", ""
        ),
        "manual_queue_operator_handoff_execute_and_refresh_all_command_text": handoff.get(
            "execute_and_refresh_all_command_text", ""
        ),
        "manual_queue_operator_handoff_execute_and_refresh_full_analysis_command_text": (
            handoff.get("execute_and_refresh_full_analysis_command_text")
            or handoff.get("execute_and_refresh_all_command_text", "")
        ),
    }


def manual_test_queue_operation_card_summary(payload: dict[str, Any]) -> dict[str, Any]:
    cards = payload.get("operation_cards") if isinstance(payload.get("operation_cards"), list) else []
    if not cards:
        return {"manual_queue_operation_card_count": 0}
    next_card = next(
        (card for card in cards if isinstance(card, dict) and card.get("is_next") is True),
        {},
    )
    if not isinstance(next_card, dict):
        next_card = {}
    return {
        "manual_queue_operation_card_count": len([card for card in cards if isinstance(card, dict)]),
        "manual_queue_next_operation_action": next_card.get("action", ""),
        "manual_queue_next_operation_purpose": next_card.get("purpose", ""),
        "manual_queue_next_operation_queue_id": next_card.get("queue_id", ""),
        "manual_queue_next_operation_step_label": next_card.get("step_label", ""),
        "manual_queue_next_operation_forward": next_card.get("forward", ""),
        "manual_queue_next_operation_optimization": next_card.get("optimization", ""),
        "manual_queue_next_operation_optimization_label": optimization_label_for_item(next_card),
        "manual_queue_next_operation_optimization_enabled": next_card.get(
            "optimization_enabled", ""
        ),
        "manual_queue_next_operation_inputs": next_card.get("inputs", ""),
        "manual_queue_next_operation_report": next_card.get("report", ""),
        "manual_queue_next_operation_collect_status": next_card.get("collect_status", ""),
    }


def bridge_recovery_operation_card_summary(payload: dict[str, Any]) -> dict[str, Any]:
    cards = payload.get("operation_cards") if isinstance(payload.get("operation_cards"), list) else []
    card_dicts = [card for card in cards if isinstance(card, dict)]
    if not card_dicts:
        return {"bridge_recovery_operation_card_count": 0}
    next_card = next((card for card in card_dicts if card.get("is_next") is True), {})
    if not isinstance(next_card, dict):
        next_card = {}
    verification_commands = []
    raw_commands = next_card.get("verification_commands")
    if isinstance(raw_commands, list):
        for command in raw_commands:
            if not isinstance(command, dict):
                continue
            label = str(command.get("label") or "")
            command_text = str(command.get("command") or "")
            if label or command_text:
                verification_commands.append(
                    {"label": label, "command": command_text}
                )
    return {
        "bridge_recovery_operation_card_count": len(card_dicts),
        "bridge_recovery_next_operation_action": next_card.get("action", ""),
        "bridge_recovery_next_operation_area": next_card.get("area", ""),
        "bridge_recovery_next_operation_purpose": next_card.get("purpose", ""),
        "bridge_recovery_next_operation_target": next_card.get("target", ""),
        "bridge_recovery_next_operation_verification": next_card.get("verification", ""),
        "bridge_recovery_next_operation_verification_commands": verification_commands,
    }


def bridge_recovery_operator_summary_fields(payload: dict[str, Any]) -> dict[str, Any]:
    summary = (
        payload.get("operator_summary")
        if isinstance(payload.get("operator_summary"), dict)
        else {}
    )
    if not summary:
        return {}
    return {
        "bridge_operator_summary_status": summary.get("status", ""),
        "bridge_operator_summary_ready_for_mt5_validation": summary.get(
            "ready_for_mt5_validation", ""
        ),
        "bridge_operator_summary_blocking_reasons": summary.get("blocking_reasons", []),
        "bridge_operator_summary_next_action": summary.get("next_action", ""),
        "bridge_operator_summary_next_operation_action": summary.get("next_operation_action", ""),
        "bridge_operator_summary_next_operation_area": summary.get("next_operation_area", ""),
        "bridge_operator_summary_next_operation_purpose": summary.get("next_operation_purpose", ""),
        "bridge_operator_summary_next_operation_target": summary.get("next_operation_target", ""),
        "bridge_operator_summary_next_operation_operator_step": summary.get(
            "next_operation_operator_step", ""
        ),
        "bridge_operator_summary_next_operation_verification": summary.get(
            "next_operation_verification", ""
        ),
        "bridge_operator_summary_next_operation_verification_commands": summary.get(
            "next_operation_verification_commands", []
        ),
        "bridge_operator_summary_mt5_terminal_running": summary.get("mt5_terminal_running", ""),
        "bridge_operator_summary_mt5_terminal_match_count": summary.get(
            "mt5_terminal_match_count", ""
        ),
        "bridge_operator_summary_bridge_log_activity_status": summary.get(
            "bridge_log_activity_status", ""
        ),
        "bridge_operator_summary_ea_liveness_signal": summary.get("ea_liveness_signal", ""),
        "bridge_operator_summary_config_get_recent": summary.get("config_get_recent", ""),
        "bridge_operator_summary_ea_post_recent": summary.get("ea_post_recent", ""),
        "bridge_operator_summary_config_get_recent_but_ea_post_stale": summary.get(
            "config_get_recent_but_ea_post_stale", ""
        ),
        "bridge_operator_summary_last_ea_post_age_seconds": summary.get(
            "last_ea_post_age_seconds", ""
        ),
        "bridge_operator_summary_snapshot_fresh": summary.get("snapshot_fresh", ""),
        "bridge_operator_summary_snapshot_age_seconds": summary.get("snapshot_age_seconds", ""),
        "bridge_operator_summary_history_request_pending": summary.get(
            "history_request_pending", ""
        ),
        "bridge_operator_summary_history_request_stale_pending": summary.get(
            "history_request_stale_pending", ""
        ),
        "bridge_operator_summary_history_request_id": summary.get("history_request_id", ""),
        "bridge_operator_summary_history_done_id": summary.get("history_done_id", ""),
        "bridge_operator_summary_history_done_matches_request": summary.get(
            "history_done_matches_request", ""
        ),
        "bridge_operator_summary_history_data_fresh": summary.get("history_data_fresh", ""),
        "bridge_operator_summary_history_data_stale": summary.get("history_data_stale", ""),
        "bridge_operator_summary_history_data_max_age_seconds": summary.get(
            "history_data_max_age_seconds", ""
        ),
        "bridge_operator_summary_history_status_server_time": summary.get(
            "history_status_server_time", ""
        ),
        "bridge_operator_summary_history_status_server_time_age_seconds": summary.get(
            "history_status_server_time_age_seconds", ""
        ),
        "bridge_operator_summary_history_status_m1_last_time": summary.get(
            "history_status_m1_last_time", ""
        ),
        "bridge_operator_summary_history_status_m1_last_time_age_seconds": summary.get(
            "history_status_m1_last_time_age_seconds", ""
        ),
    }


def mt5_strategy_tester_analysis_fields(payload: dict[str, Any]) -> dict[str, Any]:
    generated_at = str(payload.get("generated_at") or "")
    adoption = payload.get("adoption") if isinstance(payload.get("adoption"), dict) else {}
    back_forward_decision = (
        payload.get("back_forward_decision")
        if isinstance(payload.get("back_forward_decision"), dict)
        else {}
    )
    back_forward_decision_thresholds = (
        back_forward_decision.get("thresholds")
        if isinstance(back_forward_decision.get("thresholds"), dict)
        else {}
    )
    back_forward = (
        payload.get("back_forward_run")
        if isinstance(payload.get("back_forward_run"), dict)
        else {}
    )
    promotion = (
        payload.get("promotion_gate")
        if isinstance(payload.get("promotion_gate"), dict)
        else {}
    )
    tester_status = (
        payload.get("tester_status")
        if isinstance(payload.get("tester_status"), dict)
        else {}
    )
    next_step = (
        tester_status.get("next_mt5_step")
        if isinstance(tester_status.get("next_mt5_step"), dict)
        else {}
    )
    reports = payload.get("optimization_reports")
    report_rows = [row for row in reports if isinstance(row, dict)] if isinstance(reports, list) else []
    status_counts: dict[str, int] = {}
    side_candidate_counts: dict[str, int] = {}
    source_time_status_counts: dict[str, int] = {}
    source_file_status_counts: dict[str, int] = {}
    source_file_issue_labels: list[str] = []
    source_file_issue_candidate_labels: list[str] = []
    for row in report_rows:
        status = str(row.get("status") or "")
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1
        source_time = row.get("source_time") if isinstance(row.get("source_time"), dict) else {}
        source_time_status = str(source_time.get("status") or "")
        if source_time_status:
            source_time_status_counts[source_time_status] = (
                source_time_status_counts.get(source_time_status, 0) + 1
            )
        source_files = row.get("source_files") if isinstance(row.get("source_files"), dict) else {}
        source_file_status = str(source_files.get("status") or "")
        if source_file_status:
            source_file_status_counts[source_file_status] = (
                source_file_status_counts.get(source_file_status, 0) + 1
            )
        label = str(row.get("label") or "")
        if source_file_status in {"stale", "missing"} and label:
            source_file_issue_labels.append(label)
            if status == "candidate":
                source_file_issue_candidate_labels.append(label)
        if status == "candidate":
            side = str(row.get("side") or "")
            if side:
                side_candidate_counts[side] = side_candidate_counts.get(side, 0) + 1
    candidate_labels = (
        adoption.get("candidate_labels") if isinstance(adoption.get("candidate_labels"), list) else []
    )
    aggregate_only_labels = (
        adoption.get("aggregate_only_labels")
        if isinstance(adoption.get("aggregate_only_labels"), list)
        else []
    )
    blockers = adoption.get("blockers") if isinstance(adoption.get("blockers"), list) else []
    source_time_refresh_plan = (
        payload.get("source_time_refresh_plan")
        if isinstance(payload.get("source_time_refresh_plan"), dict)
        else {}
    )
    buy_candidate_gap_plan = (
        payload.get("buy_candidate_gap_plan")
        if isinstance(payload.get("buy_candidate_gap_plan"), dict)
        else {}
    )
    source_artifacts = payload.get("source_artifacts")
    source_artifact_rows = (
        [row for row in source_artifacts if isinstance(row, dict)]
        if isinstance(source_artifacts, list)
        else []
    )
    source_artifact_summaries: list[dict[str, Any]] = []
    source_artifact_generated_at_by_label: dict[str, str] = {}
    source_artifact_state_by_label: dict[str, str] = {}
    source_artifact_path_by_label: dict[str, str] = {}
    for row in source_artifact_rows:
        label = str(row.get("label") or "")
        if not label:
            continue
        generated_at_value = str(row.get("generated_at") or "")
        state_value = str(row.get("state") or "")
        path_value = str(row.get("path") or "")
        summary_row: dict[str, Any] = {
            "label": label,
            "path": path_value,
            "exists": row.get("exists", ""),
            "generated_at": generated_at_value,
            "state": state_value,
        }
        if row.get("mtime_age_seconds") not in (None, ""):
            summary_row["mtime_age_seconds"] = row.get("mtime_age_seconds")
        source_artifact_summaries.append(summary_row)
        source_artifact_generated_at_by_label[label] = generated_at_value
        source_artifact_state_by_label[label] = state_value
        source_artifact_path_by_label[label] = path_value
    promotion_source = next(
        (
            row
            for row in source_artifact_rows
            if str(row.get("label") or "") == "promotion_gate"
        ),
        {},
    )
    embedded_promotion_generated_at = str(promotion.get("generated_at") or "")
    promotion_source_generated_at = str(promotion_source.get("generated_at") or "")
    embedded_promotion_fresh = (
        embedded_promotion_generated_at == promotion_source_generated_at
        if embedded_promotion_generated_at and promotion_source_generated_at
        else ""
    )
    embedded_promotion_freshness_status = (
        "current"
        if embedded_promotion_fresh is True
        else "stale"
        if embedded_promotion_fresh is False
        else "unknown"
    )
    return {
        "strategy_tester_analysis_generated_at": generated_at,
        "strategy_tester_analysis_status": adoption.get("status", ""),
        "strategy_tester_analysis_candidate_count": len(candidate_labels),
        "strategy_tester_analysis_aggregate_only_count": len(aggregate_only_labels),
        "strategy_tester_analysis_candidate_labels": candidate_labels,
        "strategy_tester_analysis_aggregate_only_labels": aggregate_only_labels,
        "strategy_tester_analysis_blockers": blockers,
        "strategy_tester_analysis_report_status_counts": status_counts,
        "strategy_tester_analysis_side_candidate_counts": side_candidate_counts,
        "strategy_tester_analysis_source_time_status_counts": source_time_status_counts,
        "strategy_tester_analysis_source_file_status_counts": source_file_status_counts,
        "strategy_tester_analysis_source_file_issue_labels": source_file_issue_labels,
        "strategy_tester_analysis_source_file_issue_candidate_labels": source_file_issue_candidate_labels,
        "strategy_tester_analysis_source_artifacts": source_artifact_summaries,
        "strategy_tester_analysis_source_artifact_generated_at_by_label": (
            source_artifact_generated_at_by_label
        ),
        "strategy_tester_analysis_source_artifact_state_by_label": (
            source_artifact_state_by_label
        ),
        "strategy_tester_analysis_source_artifact_path_by_label": (
            source_artifact_path_by_label
        ),
        "strategy_tester_analysis_source_time_refresh_status": source_time_refresh_plan.get("status", ""),
        "strategy_tester_analysis_source_time_refresh_issue_count": source_time_refresh_plan.get(
            "issue_count", ""
        ),
        "strategy_tester_analysis_source_time_refresh_candidate_issue_count": source_time_refresh_plan.get(
            "candidate_issue_count", ""
        ),
        "strategy_tester_analysis_source_time_refresh_issue_labels": (
            source_time_refresh_plan.get("issue_labels")
            if isinstance(source_time_refresh_plan.get("issue_labels"), list)
            else []
        ),
        "strategy_tester_analysis_source_time_refresh_candidate_issue_labels": (
            source_time_refresh_plan.get("candidate_issue_labels")
            if isinstance(source_time_refresh_plan.get("candidate_issue_labels"), list)
            else []
        ),
        "strategy_tester_analysis_source_time_refresh_queue_command_text": source_time_refresh_plan.get(
            "refresh_queue_command_text", ""
        ),
        "strategy_tester_analysis_source_time_refresh_collect_command_text": source_time_refresh_plan.get(
            "collect_execute_and_refresh_command_text", ""
        ),
        "strategy_tester_analysis_buy_candidate_gap_status": buy_candidate_gap_plan.get(
            "status", ""
        ),
        "strategy_tester_analysis_buy_candidate_gap_diagnostic_labels": (
            buy_candidate_gap_plan.get("diagnostic_labels")
            if isinstance(buy_candidate_gap_plan.get("diagnostic_labels"), list)
            else []
        ),
        "strategy_tester_analysis_buy_candidate_gap_refresh_queue_command_text": (
            buy_candidate_gap_plan.get("refresh_queue_command_text", "")
        ),
        "strategy_tester_analysis_promotion_decision": promotion.get("decision", ""),
        "strategy_tester_analysis_embedded_promotion_generated_at": embedded_promotion_generated_at,
        "strategy_tester_analysis_embedded_promotion_decision": promotion.get("decision", ""),
        "strategy_tester_analysis_promotion_source_generated_at": promotion_source_generated_at,
        "strategy_tester_analysis_promotion_source_state": promotion_source.get("state", ""),
        "strategy_tester_analysis_promotion_source_path": promotion_source.get("path", ""),
        "strategy_tester_analysis_embedded_promotion_freshness_status": (
            embedded_promotion_freshness_status
        ),
        "strategy_tester_analysis_embedded_promotion_fresh": embedded_promotion_fresh,
        "strategy_tester_analysis_refresh_analysis_command_text": (
            MT5_STRATEGY_TESTER_ANALYSIS_REFRESH_COMMAND_TEXT
        ),
        "strategy_tester_analysis_back_forward_evidence_state": back_forward.get(
            "evidence_state", ""
        ),
        "strategy_tester_analysis_back_forward_performance_status": back_forward.get(
            "performance_status", ""
        ),
        "strategy_tester_analysis_back_forward_decision_status": back_forward_decision.get(
            "status", ""
        ),
        "strategy_tester_analysis_back_forward_decision_adoptable": back_forward_decision.get(
            "adoptable", ""
        ),
        "strategy_tester_analysis_back_forward_decision_next_action": back_forward_decision.get(
            "next_action", ""
        ),
        "strategy_tester_analysis_back_forward_decision_reason": back_forward_decision.get(
            "reason", ""
        ),
        "strategy_tester_analysis_back_forward_decision_thresholds": (
            back_forward_decision_thresholds
        ),
        "strategy_tester_analysis_back_forward_decision_backtest_trades": (
            back_forward_decision.get("backtest_trades", "")
        ),
        "strategy_tester_analysis_back_forward_decision_forward_trades": (
            back_forward_decision.get("forward_trades", "")
        ),
        "strategy_tester_analysis_back_forward_decision_forward_pf": (
            back_forward_decision.get("forward_pf", "")
        ),
        "strategy_tester_analysis_back_forward_decision_forward_avg_r": (
            back_forward_decision.get("forward_avg_r", "")
        ),
        "strategy_tester_analysis_back_forward_decision_forward_pf_delta_vs_backtest": (
            back_forward_decision.get("forward_pf_delta_vs_backtest", "")
        ),
        "strategy_tester_analysis_back_forward_decision_forward_avg_r_delta_vs_backtest": (
            back_forward_decision.get("forward_avg_r_delta_vs_backtest", "")
        ),
        "strategy_tester_analysis_back_forward_decision_sample_shortage_recovery_command_text": (
            back_forward_decision.get("sample_shortage_recovery_command_text", "")
        ),
        "strategy_tester_analysis_back_forward_decision_sample_shortage_recovery_range_strategy": (
            back_forward_decision.get("sample_shortage_recovery_range_strategy", "")
        ),
        "strategy_tester_analysis_back_forward_decision_sample_shortage_recovery_suggested_from_date": (
            back_forward_decision.get("sample_shortage_recovery_suggested_from_date", "")
        ),
        "strategy_tester_analysis_back_forward_decision_sample_shortage_recovery_suggested_to_date": (
            back_forward_decision.get("sample_shortage_recovery_suggested_to_date", "")
        ),
        "strategy_tester_analysis_manual_collect_status": back_forward.get(
            "manual_collect_status", ""
        ),
        "strategy_tester_analysis_manual_collect_ready": back_forward.get(
            "manual_collect_ready", ""
        ),
        "strategy_tester_analysis_next_queue_id": next_step.get("queue_id", ""),
        "strategy_tester_analysis_next_step_label": next_step.get("step_label", ""),
        "strategy_tester_analysis_next_inputs": next_step.get("inputs", ""),
        "strategy_tester_analysis_next_report": next_step.get("report", ""),
        "strategy_tester_analysis_collect_only_command_text": back_forward.get(
            "recommended_collect_only_command_text", ""
        )
        or back_forward_decision.get("collect_command_text", ""),
    }


def manual_queue_launch_handoff_summary(payload: dict[str, Any]) -> dict[str, Any]:
    next_step = (
        payload.get("queue_operator_handoff_next_mt5_step")
        if isinstance(payload.get("queue_operator_handoff_next_mt5_step"), dict)
        else {}
    )
    selected_item = payload.get("selected_item") if isinstance(payload.get("selected_item"), dict) else {}
    selected_expected_artifacts = payload.get("selected_expected_artifacts")
    if not isinstance(selected_expected_artifacts, dict):
        selected_expected_artifacts = selected_item.get("expected_artifacts")
    if not isinstance(selected_expected_artifacts, dict):
        selected_expected_artifacts = {}
    if not next_step and not any(
        key in payload
        for key in (
            "queue_operator_handoff_state",
            "queue_operator_handoff_waiting_entry_ids",
            "selected_matches_queue_handoff",
            "selected_step_fingerprint",
        )
    ):
        return {}
    next_step_for_summary = dict(next_step)
    if selected_expected_artifacts and not isinstance(
        next_step_for_summary.get("expected_artifacts"), dict
    ):
        next_step_for_summary["expected_artifacts"] = selected_expected_artifacts
    return {
        "queue_entry_count": payload.get("queue_entry_count", ""),
        "queue_total_entry_count": payload.get("queue_total_entry_count", ""),
        "queue_step_count": payload.get("queue_step_count", ""),
        "queue_ready_to_collect_count": payload.get("queue_ready_to_collect_count", ""),
        "queue_waiting_count": payload.get("queue_waiting_count", ""),
        "queue_step_report_ready_count": payload.get("queue_step_report_ready_count", ""),
        "queue_step_waiting_report_count": payload.get("queue_step_waiting_report_count", ""),
        "queue_step_launch_needed_count": payload.get("queue_step_launch_needed_count", ""),
        "queue_operator_handoff_next_queue_id": next_step.get("queue_id", ""),
        "queue_operator_handoff_next_step_label": next_step.get("step_label", ""),
        "queue_operator_handoff_next_symbol": next_step.get("symbol", ""),
        "queue_operator_handoff_next_period": next_step.get("period", ""),
        "queue_operator_handoff_next_model": next_step.get("model", ""),
        "queue_operator_handoff_next_dates": next_step.get("dates", ""),
        "queue_operator_handoff_next_forward": next_step.get("forward", ""),
        "queue_operator_handoff_next_inputs": next_step.get("inputs", ""),
        "queue_operator_handoff_next_report": next_step.get("report", ""),
        "queue_operator_handoff_next_step_operator_summary": (
            payload.get("queue_operator_handoff_next_step_operator_summary")
            or operator_step_summary(next_step_for_summary)
        ),
        "queue_operator_handoff_next_step_summary": (
            payload.get("queue_operator_handoff_next_step_summary")
            or payload.get("queue_operator_handoff_next_step_operator_summary")
            or operator_step_summary(next_step_for_summary)
        ),
        "queue_operator_handoff_next_step_collect_filter_summary": (
            payload.get("queue_operator_handoff_next_step_collect_filter_summary")
            or operator_collect_filter_summary(next_step_for_summary)
        ),
        "queue_operator_handoff_next_step_fingerprint": next_step.get("step_fingerprint", ""),
        "queue_operator_handoff_next_step_config_fingerprint": next_step.get(
            "step_config_fingerprint", ""
        ),
        "queue_operator_handoff_next_step_run_fingerprint": next_step.get(
            "step_run_fingerprint", ""
        ),
        "queue_operator_handoff_next_expected_report_artifact": next_step.get(
            "expected_report_artifact", ""
        ),
        "queue_operator_handoff_next_expected_artifacts": (
            next_step.get("expected_artifacts")
            if isinstance(next_step.get("expected_artifacts"), dict)
            else {}
        ),
        "queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text": (
            payload.get("queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text")
            or payload.get("queue_operator_handoff_collect_execute_and_refresh_all_command_text", "")
        ),
        "selected_step_fingerprint": (
            payload.get("selected_step_fingerprint")
            or selected_item.get("step_fingerprint", "")
        ),
        "selected_step_config_fingerprint": (
            payload.get("selected_step_config_fingerprint")
            or selected_item.get("step_config_fingerprint", "")
        ),
        "selected_step_run_fingerprint": (
            payload.get("selected_step_run_fingerprint")
            or selected_item.get("step_run_fingerprint", "")
        ),
        "selected_expected_report": (
            payload.get("selected_expected_report") or selected_item.get("report", "")
        ),
        "selected_expected_report_artifact": (
            payload.get("selected_expected_report_artifact")
            or selected_item.get("expected_report_artifact", "")
        ),
        "selected_expected_artifacts": selected_expected_artifacts,
        "queue_operator_handoff_waiting_entry_ids": (
            payload.get("queue_operator_handoff_waiting_entry_ids")
            if isinstance(payload.get("queue_operator_handoff_waiting_entry_ids"), list)
            else []
        ),
        "queue_operator_handoff_collect_dry_run_command_text": payload.get(
            "queue_operator_handoff_collect_dry_run_command_text", ""
        ),
        "queue_operator_handoff_collect_execute_command_text": payload.get(
            "queue_operator_handoff_collect_execute_command_text", ""
        ),
        "queue_operator_handoff_collect_execute_and_refresh_analysis_command_text": payload.get(
            "queue_operator_handoff_collect_execute_and_refresh_analysis_command_text", ""
        ),
        "queue_operator_handoff_collect_execute_and_refresh_all_command_text": payload.get(
            "queue_operator_handoff_collect_execute_and_refresh_all_command_text", ""
        ),
    }


def manual_collect_entry_summaries(entries: object) -> list[dict[str, Any]]:
    if not isinstance(entries, list):
        return []
    summaries: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        summaries.append(
            {
                "id": entry.get("id", ""),
                "title": entry.get("title", ""),
                "runner_generated_at": entry.get("runner_generated_at", ""),
                "promotion_generated_at": entry.get("promotion_generated_at", ""),
                "promotion_decision": entry.get("promotion_decision", ""),
                "ready": entry.get("ready", ""),
                "collect_status": entry.get("collect_status", ""),
                "skip_reason": entry.get("skip_reason", ""),
                "audit_step_count": entry.get("audit_step_count", ""),
                "step_fingerprints": (
                    entry.get("step_fingerprints")
                    if isinstance(entry.get("step_fingerprints"), list)
                    else []
                ),
                "step_config_fingerprints": (
                    entry.get("step_config_fingerprints")
                    if isinstance(entry.get("step_config_fingerprints"), list)
                    else []
                ),
                "step_run_fingerprints": (
                    entry.get("step_run_fingerprints")
                    if isinstance(entry.get("step_run_fingerprints"), list)
                    else []
                ),
                "expected_reports": (
                    entry.get("expected_reports")
                    if isinstance(entry.get("expected_reports"), list)
                    else []
                ),
                "expected_artifacts_by_step": (
                    entry.get("expected_artifacts_by_step")
                    if isinstance(entry.get("expected_artifacts_by_step"), list)
                    else []
                ),
            }
        )
    return summaries


def manual_collect_step_completion_summaries(entries: object) -> list[dict[str, Any]]:
    if not isinstance(entries, list):
        return []
    summaries: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        summaries.append(
            {
                "order": entry.get("order", ""),
                "queue_step": entry.get("queue_step", ""),
                "purpose": entry.get("purpose", ""),
                "status": entry.get("status", ""),
                "report_ready": entry.get("report_ready", ""),
                "collect_ready": entry.get("collect_ready", ""),
                "launch_needed": entry.get("launch_needed", ""),
                "expected_report_artifact": entry.get("expected_report_artifact", ""),
                "report": entry.get("report", ""),
                "agent_csv_modified_after": entry.get("agent_csv_modified_after", ""),
                "step_fingerprint": entry.get("step_fingerprint", ""),
                "blocking_reason": entry.get("blocking_reason", ""),
            }
        )
    return summaries


def manual_test_queue_stale_entry_summaries(entries: object) -> list[dict[str, Any]]:
    if not isinstance(entries, list):
        return []
    summaries: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        stale_reasons = entry.get("stale_reasons") if isinstance(entry.get("stale_reasons"), list) else []
        if not stale_reasons and entry.get("current_for_execution") is not False:
            continue
        summaries.append(
            {
                "id": entry.get("id", ""),
                "title": entry.get("title", ""),
                "source_json": entry.get("source_json", ""),
                "available": entry.get("available", ""),
                "current_for_execution": entry.get("current_for_execution", ""),
                "gate_stale_reason": entry.get("gate_stale_reason", ""),
                "stale_reasons": stale_reasons,
                "refresh_command_text": entry.get("refresh_command_text", ""),
                "runner_generated_at": entry.get("runner_generated_at") or entry.get("generated_at", ""),
                "promotion_generated_at": entry.get("promotion_generated_at", ""),
                "current_promotion_generated_at": entry.get("current_promotion_generated_at", ""),
                "promotion_decision": entry.get("promotion_decision", ""),
                "current_promotion_decision": entry.get("current_promotion_decision", ""),
                "selected_action_current": entry.get("selected_action_current", ""),
            }
        )
    return summaries


def manual_test_queue_checklist_summaries(checklist: object) -> list[dict[str, Any]]:
    if not isinstance(checklist, list):
        return []
    summaries: list[dict[str, Any]] = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        summaries.append(
            {
                "order": item.get("order", ""),
                "queue_id": item.get("queue_id", ""),
                "step_label": item.get("step_label", ""),
                "symbol": item.get("symbol", ""),
                "period": item.get("period", ""),
                "model": item.get("model", ""),
                "dates": item.get("dates", ""),
                "forward": item.get("forward", ""),
                "optimization": item.get("optimization", ""),
                "optimization_label": optimization_label_for_item(item),
                "optimization_enabled": item.get("optimization_enabled", ""),
                "run_type": item.get("run_type", ""),
                "step_fingerprint": item.get("step_fingerprint", ""),
                "step_config_fingerprint": item.get("step_config_fingerprint", ""),
                "step_run_fingerprint": item.get("step_run_fingerprint", ""),
                "expected_report_artifact": item.get("expected_report_artifact", ""),
                "expected_artifacts": (
                    item.get("expected_artifacts")
                    if isinstance(item.get("expected_artifacts"), dict)
                    else {}
                ),
                "report_expectation_note": item.get("report_expectation_note", ""),
                "step_report_status": item.get("step_report_status", ""),
                "step_report_ready": item.get("step_report_ready", ""),
                "step_collect_ready": item.get("step_collect_ready", ""),
                "step_blocking_reason": item.get("step_blocking_reason", ""),
                "selected_report": item.get("selected_report", ""),
                "launch_needed": item.get("launch_needed", ""),
                "inputs": item.get("inputs", ""),
                "report": item.get("report", ""),
                "manual_run_start_after": item.get("manual_run_start_after", ""),
                "config": item.get("config", ""),
                "mt5_config": item.get("mt5_config", ""),
                "launch_command_kind": item.get("launch_command_kind", ""),
                "launch_command_text": item.get("launch_command_text", ""),
                "launch_error": item.get("launch_error", ""),
                "direct_config_reason": item.get("direct_config_reason", ""),
            }
        )
    return summaries


def manual_test_queue_target_summaries(
    targets: object,
    checklist: object,
) -> list[dict[str, Any]]:
    if isinstance(targets, list) and targets:
        summaries: list[dict[str, Any]] = []
        for item in targets:
            if not isinstance(item, dict):
                continue
            summaries.append(
                {
                    "order": item.get("order", ""),
                    "purpose": item.get("purpose", ""),
                    "queue_id": item.get("queue_id", ""),
                    "step_label": item.get("step_label", ""),
                    "symbol": item.get("symbol", ""),
                    "period": item.get("period", ""),
                    "dates": item.get("dates", ""),
                    "forward": item.get("forward", ""),
                    "optimization": item.get("optimization", ""),
                    "optimization_label": optimization_label_for_item(item),
                    "optimization_enabled": item.get("optimization_enabled", ""),
                    "run_type": item.get("run_type", ""),
                    "step_fingerprint": item.get("step_fingerprint", ""),
                    "step_config_fingerprint": item.get("step_config_fingerprint", ""),
                    "step_run_fingerprint": item.get("step_run_fingerprint", ""),
                    "expected_report_artifact": item.get("expected_report_artifact", ""),
                    "expected_artifacts": (
                        item.get("expected_artifacts")
                        if isinstance(item.get("expected_artifacts"), dict)
                        else {}
                    ),
                    "report_expectation_note": item.get("report_expectation_note", ""),
                    "inputs": item.get("inputs", ""),
                    "report": item.get("report", ""),
                    "start_after": item.get("start_after", ""),
                    "collect_modified_after": item.get("collect_modified_after", ""),
                    "collect_csv_count": item.get("collect_csv_count", ""),
                    "collect_status": item.get("collect_status", ""),
                    "collect_next_action": item.get("collect_next_action", ""),
                    "step_report_status": item.get("step_report_status", ""),
                    "step_report_ready": item.get("step_report_ready", ""),
                    "step_collect_ready": item.get("step_collect_ready", ""),
                    "step_blocking_reason": item.get("step_blocking_reason", ""),
                    "selected_report": item.get("selected_report", ""),
                    "launch_needed": item.get("launch_needed", ""),
                    "auto_launch_kind": item.get("auto_launch_kind", ""),
                }
            )
        if summaries:
            return summaries
    if not isinstance(checklist, list):
        return []
    summaries = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        queue_id = str(item.get("queue_id") or "")
        step_label = str(item.get("step_label") or "")
        if queue_id == "back_forward" and step_label == "backtest":
            purpose = "Backtest"
        elif queue_id == "back_forward" and step_label == "forward":
            purpose = "Forward Test"
        elif queue_id == "score_weight_sell":
            purpose = "SELL Score Sample"
        elif queue_id == "score_weight_buy":
            purpose = "BUY Score Sample"
        else:
            purpose = step_label or queue_id
        summaries.append(
            {
                "order": item.get("order", ""),
                "purpose": purpose,
                "queue_id": queue_id,
                "step_label": step_label,
                "symbol": item.get("symbol", ""),
                "period": item.get("period", ""),
                "dates": item.get("dates", ""),
                "forward": item.get("forward", ""),
                "optimization": item.get("optimization", ""),
                "optimization_label": optimization_label_for_item(item),
                "optimization_enabled": item.get("optimization_enabled", ""),
                "run_type": item.get("run_type", ""),
                "step_fingerprint": item.get("step_fingerprint", ""),
                "step_config_fingerprint": item.get("step_config_fingerprint", ""),
                "step_run_fingerprint": item.get("step_run_fingerprint", ""),
                "expected_report_artifact": item.get("expected_report_artifact", ""),
                "expected_artifacts": (
                    item.get("expected_artifacts")
                    if isinstance(item.get("expected_artifacts"), dict)
                    else {}
                ),
                "report_expectation_note": item.get("report_expectation_note", ""),
                "inputs": item.get("inputs", ""),
                "report": item.get("report", ""),
                "start_after": item.get("manual_run_start_after", ""),
                "collect_modified_after": "",
                "collect_csv_count": "",
                "collect_status": "",
                "collect_next_action": "",
                "step_report_status": item.get("step_report_status", ""),
                "step_report_ready": item.get("step_report_ready", ""),
                "step_collect_ready": item.get("step_collect_ready", ""),
                "step_blocking_reason": item.get("step_blocking_reason", ""),
                "selected_report": item.get("selected_report", ""),
                "launch_needed": item.get("launch_needed", ""),
                "auto_launch_kind": item.get("launch_command_kind", ""),
            }
        )
    return summaries


def next_action_runner_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or not payload:
        return {}
    return {
        **extract_command_hints(payload),
        **manual_strategy_tester_summary(payload),
        **manual_collect_readiness_summary(payload),
        "generated_at": payload.get("generated_at", ""),
        "promotion_generated_at": payload.get("promotion_generated_at", ""),
        "decision": payload.get("promotion_decision") or payload.get("decision", ""),
        "runner_generated_at": payload.get("runner_generated_at", ""),
        "current_for_execution": payload.get("current_for_execution", ""),
        "gate_stale_reason": payload.get("gate_stale_reason", ""),
        "runner_promotion_generated_at": payload.get("promotion_generated_at")
        or payload.get("runner_promotion_generated_at", ""),
        "current_promotion_generated_at": payload.get("current_promotion_generated_at", ""),
        "selected_action_current": payload.get("selected_action_current", ""),
        "target": payload.get("target", ""),
        "focus_side": payload.get("focus_side", ""),
        "config": payload.get("config", ""),
        "set": payload.get("set", ""),
    }


def side_runner_stale_reasons(side_runner: dict[str, Any], gate: dict[str, Any]) -> list[str]:
    if not side_runner:
        return []
    reasons: list[str] = []
    if side_runner.get("current_for_execution") is False:
        stale_reason = str(side_runner.get("gate_stale_reason") or "not_current")
        reasons.append(f"current_for_execution_false:{stale_reason}")
    gate_generated_at = str(gate.get("generated_at") or "")
    runner_current_gate = str(side_runner.get("current_promotion_generated_at") or "")
    runner_promotion_generated_at = str(
        runner_current_gate
        or side_runner.get("promotion_generated_at")
        or side_runner.get("runner_promotion_generated_at")
        or side_runner.get("generated_at")
        or ""
    )
    if gate_generated_at:
        if not runner_promotion_generated_at:
            reasons.append("missing_runner_promotion_generated_at")
        elif runner_promotion_generated_at != gate_generated_at:
            reasons.append("promotion_gate_generated_at_mismatch")
    gate_decision = str(gate.get("decision") or "")
    runner_decision = str(side_runner.get("promotion_decision") or side_runner.get("decision") or "")
    if gate_decision:
        if not runner_decision:
            reasons.append("missing_runner_promotion_decision")
        elif runner_decision != gate_decision:
            reasons.append("promotion_gate_decision_mismatch")
    return reasons


def next_action_runner_artifact_stale_reasons(artifact: dict[str, Any], gate: dict[str, Any]) -> list[str]:
    if artifact.get("exists") is not True:
        return []
    if not str(artifact.get("target") or ""):
        return []
    return side_runner_stale_reasons(artifact, gate)


def blocking_prior_action_summaries(actions: Any) -> list[dict[str, Any]]:
    if not isinstance(actions, list):
        return []
    rows: list[dict[str, Any]] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        rows.append(
            {
                "priority": action.get("priority", ""),
                "area": action.get("area", ""),
                "action": action.get("action", ""),
                "reason": action.get("reason", ""),
                "execution_kind": action.get("execution_kind", ""),
                "command_text": action.get("command_text", ""),
                "runner_execute_hint": action.get("runner_execute_hint", ""),
                "runner_requires_allow_non_tester_primary": action.get(
                    "runner_requires_allow_non_tester_primary", ""
                ),
                "primary_execution_class": action.get("primary_execution_class", ""),
            }
        )
    return rows


def blocking_prior_action_text(actions: Any) -> str:
    rows = blocking_prior_action_summaries(actions)
    parts: list[str] = []
    for row in rows:
        priority = row.get("priority", "")
        area = row.get("area", "")
        action = row.get("action", "")
        parts.append(f"P{priority} {area}:{action}")
    return "; ".join(parts)


def file_age_summary(path: Path, *, now_epoch: float) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "path": str(path),
            "modified_at": "",
            "mtime_epoch": None,
            "age_seconds": None,
        }
    mtime_epoch = path.stat().st_mtime
    age_seconds = max(0.0, now_epoch - mtime_epoch)
    return {
        "exists": True,
        "path": str(path),
        "modified_at": datetime.fromtimestamp(mtime_epoch).strftime(TIME_FORMAT),
        "mtime_epoch": round(mtime_epoch, 3),
        "age_seconds": round(age_seconds, 1),
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


def history_data_freshness(
    payload: dict[str, Any],
    *,
    now_epoch: float,
    max_age_seconds: int = DEFAULT_MAX_HISTORY_DATA_AGE_SECONDS,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    timeframes = payload.get("timeframes") if isinstance(payload.get("timeframes"), dict) else {}
    m1 = timeframes.get("M1") if isinstance(timeframes.get("M1"), dict) else {}
    server_time = str(payload.get("server_time") or "")
    m1_last_time = str(m1.get("last_time") or "")
    rows: list[tuple[str, str]] = [
        ("history_server_time", server_time),
        ("history_m1_last_time", m1_last_time),
    ]
    summary: dict[str, Any] = {"max_history_data_age_seconds": max_age_seconds}
    freshness_values: list[bool] = []
    for key, text in rows:
        summary[key] = text
        epoch = parse_mt5_time_epoch(text)
        age_key = key + "_age_seconds"
        fresh_key = key + "_fresh"
        if epoch is None:
            summary[age_key] = ""
            summary[fresh_key] = ""
            continue
        age_seconds = max(0.0, now_epoch - epoch)
        fresh = age_seconds <= max_age_seconds
        summary[age_key] = round(age_seconds, 1)
        summary[fresh_key] = fresh
        freshness_values.append(fresh)
    if freshness_values:
        summary["history_data_fresh"] = all(freshness_values)
    else:
        summary["history_data_fresh"] = ""
    return summary


def history_request_state(
    workspace: Path,
    *,
    now_epoch: float,
    max_pending_seconds: int = DEFAULT_MAX_HISTORY_REQUEST_PENDING_SECONDS,
    max_snapshot_age_seconds: int = DEFAULT_MAX_BRIDGE_SNAPSHOT_AGE_SECONDS,
) -> dict[str, Any]:
    request_path = workspace / "runtime" / "history_request.json"
    done_path = workspace / "runtime" / "history_request.done.json"
    snapshot_path = workspace / "runtime" / "latest_snapshot.json"
    request_payload = load_json_if_present(request_path)
    done_payload = load_json_if_present(done_path)
    snapshot_payload = load_json_if_present(snapshot_path)
    request_file = file_age_summary(request_path, now_epoch=now_epoch)
    done_file = file_age_summary(done_path, now_epoch=now_epoch)
    snapshot_file = file_age_summary(snapshot_path, now_epoch=now_epoch)
    request_id = str(request_payload.get("id") or "")
    done_id = str(done_payload.get("id") or "")
    request_status = str(request_payload.get("status") or "")
    done_matches_request = bool(request_id and done_id and request_id == done_id)
    pending = bool(request_file["exists"] and request_status == "pending" and not done_matches_request)
    request_age_seconds = request_file.get("age_seconds")
    stale_pending = bool(
        pending
        and request_age_seconds is not None
        and float(request_age_seconds) > max_pending_seconds
    )
    snapshot_age_seconds = snapshot_file.get("age_seconds")
    snapshot_fresh = bool(
        snapshot_file["exists"]
        and snapshot_age_seconds is not None
        and float(snapshot_age_seconds) <= max_snapshot_age_seconds
    )
    if stale_pending:
        state = "stale_pending"
    elif pending:
        state = "pending"
    elif done_matches_request:
        state = "matched"
    else:
        state = "idle"
    return {
        "request": {
            **request_file,
            "id": request_id,
            "hours": request_payload.get("hours"),
            "status": request_status,
            "requested_at": request_payload.get("requested_at"),
        },
        "done": {
            **done_file,
            "id": done_id,
            "hours": done_payload.get("hours"),
            "source_server_time": done_payload.get("source_server_time", ""),
        },
        "bridge_snapshot": {
            **snapshot_file,
            "server_time": snapshot_payload.get("server_time", ""),
            "symbol": snapshot_payload.get("symbol", ""),
            "history_request_id": snapshot_payload.get("history_request_id", ""),
            "history_hours": snapshot_payload.get("history_hours", ""),
            "fresh": snapshot_fresh,
            "max_age_seconds": max_snapshot_age_seconds,
        },
        "done_matches_request": done_matches_request,
        "pending": pending,
        "stale_pending": stale_pending,
        "pending_age_seconds": request_age_seconds if pending else None,
        "max_pending_seconds": max_pending_seconds,
        "state": state,
    }


def parse_spec_components(spec_text: str) -> list[dict[str, Any]]:
    components: list[dict[str, Any]] = []
    for line_number, line in enumerate(spec_text.splitlines(), start=1):
        match = COMPONENT_HEADING_RE.match(line.strip())
        if not match:
            continue
        filename = match.group(1)
        components.append(
            {
                "name": filename,
                "line": line_number,
                "expected_path": f"methods/swing_eval/analysis/{filename}",
            }
        )
    return components


def parse_phase_completion_conditions(spec_text: str) -> list[dict[str, Any]]:
    phases: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    collecting = False
    for line_number, raw_line in enumerate(spec_text.splitlines(), start=1):
        stripped = raw_line.strip()
        match = PHASE_HEADING_RE.match(stripped)
        if match:
            if current is not None:
                phases.append(current)
            current = {"name": match.group(1), "line": line_number, "completion_conditions": []}
            collecting = False
            continue
        if current is None:
            continue
        if stripped.startswith("完了条件"):
            collecting = True
            continue
        if collecting and stripped.startswith("### "):
            phases.append(current)
            current = None
            collecting = False
            continue
        if collecting and stripped.startswith("- "):
            current["completion_conditions"].append(stripped[2:].strip())
    if current is not None:
        phases.append(current)
    return phases


PHASE_REASON_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Phase 1": (
        "history",
        "bridge",
        "latest_snapshot",
    ),
    "Phase 2": (
        "swing_points",
    ),
    "Phase 3": (
        "candidate_generator",
        "features",
        "scoring",
    ),
    "Phase 4": (
        "backtest",
        "score_weight",
        "winrate",
        "mt5_back_forward",
        "mt5_strategy",
        "mt5_optimization",
    ),
    "Phase 5.5": (
        "predictor",
        "indicator",
        "Swing_Evaluation_Predictor",
    ),
    "Phase 5": (
        "signal",
        "dry_run",
        "forward",
        "promotion_gate",
    ),
    "Phase 6": (
        "dry_run",
        "risk_gate",
        "trade_command",
        "forward",
        "bridge",
        "promotion_gate",
    ),
    "Phase 7": (
        "mt5_forward",
        "mt5_tester",
        "mt5_strategy",
        "promotion_gate",
        "risk",
    ),
}


def phase_prefix(phase_name: str) -> str:
    for prefix in sorted(PHASE_REASON_KEYWORDS, key=len, reverse=True):
        if phase_name.startswith(prefix):
            return prefix
    return ""


def build_phase_statuses(phases: list[dict[str, Any]], reasons: list[str]) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for phase in phases:
        if not isinstance(phase, dict):
            continue
        name = str(phase.get("name") or "")
        prefix = phase_prefix(name)
        keywords = PHASE_REASON_KEYWORDS.get(prefix, ())
        blockers = [
            reason
            for reason in reasons
            if any(keyword in str(reason) for keyword in keywords)
        ]
        conditions = phase.get("completion_conditions")
        condition_count = len(conditions) if isinstance(conditions, list) else 0
        statuses.append(
            {
                "name": name,
                "line": phase.get("line", ""),
                "condition_count": condition_count,
                "status": "blocked" if blockers else "no_current_blockers",
                "blocking_reason_count": len(blockers),
                "blocking_reasons": blockers,
            }
        )
    return statuses


def action_reasons(action: dict[str, Any]) -> list[str]:
    reasons = action.get("reasons")
    if not isinstance(reasons, list):
        return []
    return [str(reason) for reason in reasons if str(reason)]


def reasons_overlap(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    return left.startswith(f"{right}:") or right.startswith(f"{left}:")


def related_next_actions_for_phase(
    blockers: list[str],
    next_actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    related: list[dict[str, Any]] = []
    seen: set[str] = set()
    for action in next_actions:
        if not isinstance(action, dict):
            continue
        action_id = str(action.get("id") or "")
        if not action_id or action_id in seen:
            continue
        action_reason_values = action_reasons(action)
        if not any(
            reasons_overlap(blocker, action_reason)
            for blocker in blockers
            for action_reason in action_reason_values
        ):
            continue
        seen.add(action_id)
        related.append(
            {
                "id": action_id,
                "priority": action.get("priority", ""),
                "area": action.get("area", ""),
                "summary": action.get("summary", ""),
            }
        )
    return related


def build_phase_current_blockers(
    phase_statuses: list[dict[str, Any]],
    next_actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for phase in phase_statuses:
        if not isinstance(phase, dict) or phase.get("status") != "blocked":
            continue
        blocking_reasons = (
            phase.get("blocking_reasons") if isinstance(phase.get("blocking_reasons"), list) else []
        )
        blocking_reason_texts = [str(reason) for reason in blocking_reasons]
        related_actions = related_next_actions_for_phase(blocking_reason_texts, next_actions)
        primary_next_action = related_actions[0] if related_actions else {}
        blockers.append(
            {
                "name": phase.get("name", ""),
                "line": phase.get("line", ""),
                "condition_count": phase.get("condition_count", ""),
                "status": phase.get("status", ""),
                "blocking_reason_count": phase.get("blocking_reason_count", len(blocking_reason_texts)),
                "primary_reason": blocking_reason_texts[0] if blocking_reason_texts else "",
                "blocking_reasons": blocking_reason_texts,
                "primary_next_action_id": primary_next_action.get("id", ""),
                "primary_next_action_priority": primary_next_action.get("priority", ""),
                "primary_next_action_area": primary_next_action.get("area", ""),
                "primary_next_action_summary": primary_next_action.get("summary", ""),
                "primary_next_action": primary_next_action,
                "related_next_action_count": len(related_actions),
                "related_next_action_ids": [action.get("id", "") for action in related_actions],
                "related_next_actions": related_actions,
            }
        )
    return blockers


def test_reference_count(workspace: Path, component_name: str) -> int:
    needle = component_name.removesuffix(".py")
    count = 0
    for test_file in sorted((workspace / "methods" / "swing_eval" / "tests").glob("test_*.py")):
        try:
            count += test_file.read_text(encoding="utf-8").count(needle)
        except OSError:
            continue
    return count


def path_reference_count(workspace: Path, relative_path: str) -> int:
    path = Path(relative_path)
    needles = {path.name, path.stem}
    count = 0
    for test_file in sorted((workspace / "methods" / "swing_eval" / "tests").glob("test_*.py")):
        try:
            text = test_file.read_text(encoding="utf-8")
        except OSError:
            continue
        count += sum(text.count(needle) for needle in needles)
    return count


def marker_summary(path: Path, markers: tuple[str, ...]) -> dict[str, Any]:
    if not markers:
        return {"required_markers": [], "missing_markers": [], "markers_ok": True}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {
            "required_markers": list(markers),
            "missing_markers": list(markers),
            "markers_ok": False,
        }
    missing = [marker for marker in markers if marker not in text]
    return {
        "required_markers": list(markers),
        "missing_markers": missing,
        "markers_ok": not missing,
    }


def file_mtime_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"modified_at": "", "mtime_epoch": None}
    mtime_epoch = path.stat().st_mtime
    return {
        "modified_at": datetime.fromtimestamp(mtime_epoch).strftime(TIME_FORMAT),
        "mtime_epoch": round(mtime_epoch, 3),
    }


def copy_present_fields(
    summary: dict[str, Any],
    prefix: str,
    source: dict[str, Any],
    fields: tuple[str, ...],
) -> None:
    for field in fields:
        if field in source:
            summary[f"{prefix}_{field}"] = source.get(field)


def score_weight_walk_summary_fields(
    summary: dict[str, Any],
    prefix: str,
    aggregate: dict[str, Any],
) -> None:
    copy_present_fields(
        summary,
        prefix,
        aggregate,
        (
            "status",
            "folds",
            "folds_with_weight_trades",
            "required_folds_with_weight_trades",
            "missing_folds_with_weight_trades",
            "total_test_weight_count",
            "required_test_weight_count",
            "missing_test_weight_count",
            "min_test_weight_count",
            "min_test_weight_fold",
            "mean_test_weight_avg_r",
            "mean_test_weight_pf",
            "delta_total_r",
            "recommendation",
        ),
    )


def score_weight_candidate_summary_fields(
    summary: dict[str, Any],
    prefix: str,
    candidate: dict[str, Any],
) -> None:
    copy_present_fields(
        summary,
        prefix,
        candidate,
        ("dimension", "group", "threshold", "weights", "count", "avg_r", "pf", "total_r"),
    )


def component_coverage(workspace: Path, components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for component in components:
        path = workspace / str(component["expected_path"])
        rows.append(
            {
                **component,
                "exists": path.exists(),
                "test_reference_count": test_reference_count(workspace, str(component["name"])),
            }
        )
    return rows


def mql5_artifact_coverage(workspace: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, relative_path, phase in MQL5_ARTIFACTS:
        path = workspace / relative_path
        markers = mql5_artifact_required_markers(name, relative_path)
        rows.append(
            {
                "name": name,
                "path": relative_path,
                "phase": phase,
                "exists": path.exists(),
                "test_reference_count": path_reference_count(workspace, relative_path),
                **file_mtime_summary(path),
                **marker_summary(path, markers),
            }
        )
    return rows


def runtime_watcher_row_summary(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    heartbeat = row.get("heartbeat_summary") if isinstance(row.get("heartbeat_summary"), dict) else {}
    schema = row.get("heartbeat_schema") if isinstance(row.get("heartbeat_schema"), dict) else {}
    mode = row.get("heartbeat_mode") if isinstance(row.get("heartbeat_mode"), dict) else {}
    missing_required_fields = (
        schema.get("missing_required_fields")
        if isinstance(schema.get("missing_required_fields"), list)
        else []
    )
    mode_issues = mode.get("issues") if isinstance(mode.get("issues"), list) else []
    return {
        "name": row.get("name", ""),
        "status": row.get("status", ""),
        "error": row.get("error", ""),
        "heartbeat": row.get("heartbeat", ""),
        "heartbeat_status": heartbeat.get("status", ""),
        "heartbeat_fresh": heartbeat.get("fresh", ""),
        "heartbeat_age_seconds": heartbeat.get("age_seconds", ""),
        "heartbeat_execute_ready": heartbeat.get("execute_ready", ""),
        "log_file": row.get("log_file", ""),
        "start_command_text": row.get("start_command_text", ""),
        "restart_command_text": row.get("restart_command_text", ""),
        "tail_log_command_text": row.get("tail_log_command_text", ""),
        "watcher_command_text": row.get("command_text", ""),
        "implementation_version": heartbeat.get("implementation_version", ""),
        "expected_implementation_version": schema.get("expected_implementation_version", ""),
        "schema_ok": schema.get("ok", ""),
        "missing_required_field_count": len(missing_required_fields),
        "missing_required_fields": [str(item) for item in missing_required_fields],
        "mode_ok": mode.get("ok", ""),
        "mode_actual_execute_ready": mode.get("actual_execute_ready", ""),
        "mode_expected_execute_ready": mode.get("expected_execute_ready", ""),
        "mode_issues": [str(item) for item in mode_issues],
    }


def runtime_watcher_row_summaries(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [
        summary
        for summary in (runtime_watcher_row_summary(row) for row in rows)
        if summary
    ]


def runtime_watcher_mode_mismatch_details(rows: list[dict[str, Any]]) -> list[str]:
    details: list[str] = []
    for row in rows:
        if row.get("mode_ok") is not False and row.get("status") != "running_heartbeat_mode_mismatch":
            continue
        issues = row.get("mode_issues") if isinstance(row.get("mode_issues"), list) else []
        issue_text = ",".join(str(item) for item in issues)
        details.append(
            f"{row.get('name', '')}:actual={row.get('mode_actual_execute_ready', '')}"
            f",expected={row.get('mode_expected_execute_ready', '')}"
            f",issues={issue_text}"
        )
    return details


def artifact_summary(
    workspace: Path,
    name: str,
    relative_path: str,
    *,
    now_epoch: float,
    max_age_seconds: int,
    max_history_data_age_seconds: int = DEFAULT_MAX_HISTORY_DATA_AGE_SECONDS,
) -> dict[str, Any]:
    path = workspace / relative_path
    payload = load_json_if_present(path)
    summary: dict[str, Any] = {
        "name": name,
        "path": relative_path,
        "exists": path.exists(),
        "generated_at": generated_at_from_payload(payload),
        "max_age_seconds": max_age_seconds,
    }
    if path.exists():
        mtime_epoch = path.stat().st_mtime
        age_seconds = max(0.0, now_epoch - mtime_epoch)
        summary.update(
            {
                "modified_at": datetime.fromtimestamp(mtime_epoch).strftime(TIME_FORMAT),
                "mtime_epoch": round(mtime_epoch, 3),
                "age_seconds": round(age_seconds, 1),
                "fresh": age_seconds <= max_age_seconds,
            }
        )
    else:
        summary.update(
            {
                "modified_at": "",
                "mtime_epoch": None,
                "age_seconds": None,
                "fresh": False,
            }
        )
    if not payload:
        return summary
    if name == "runtime_watchers":
        watcher_summaries = runtime_watcher_row_summaries(payload.get("watchers"))
        stale_summaries = runtime_watcher_row_summaries(payload.get("stale_watchers"))
        summary["runtime_watcher_summaries"] = watcher_summaries
        summary["runtime_watcher_stale_summaries"] = stale_summaries
        summary["runtime_watcher_action_required_summaries"] = (
            runtime_watcher_row_summaries(payload.get("action_required_watchers"))
        )
        mode_mismatch_summaries = [
            row
            for row in watcher_summaries
            if row.get("mode_ok") is False
            or row.get("status") == "running_heartbeat_mode_mismatch"
        ]
        summary["runtime_watcher_mode_mismatch_summaries"] = mode_mismatch_summaries
        summary["runtime_watcher_mode_mismatch_details"] = runtime_watcher_mode_mismatch_details(
            mode_mismatch_summaries
        )
    if name in {"history", "history_status"}:
        summary.update(
            history_data_freshness(
                payload,
                now_epoch=now_epoch,
                max_age_seconds=max_history_data_age_seconds,
            )
        )
    for key in (
        "ok",
        "status_ok",
        "status",
        "decision",
        "operational_status",
        "next_action",
        "ready_for_mt5_validation",
        "blocking_reasons",
        "returncode",
        "continuous",
        "run_index",
        "pid_file_written",
        "implementation_version",
        "watcher_count",
        "stale_watcher_count",
        "action_required_watcher_count",
        "max_heartbeat_age_seconds",
        "mt5_manual_auto_collect_execute_ready",
        "runtime_watcher_mode_mismatch_details",
        "recovery_plan_status",
        "recovery_plan_ready_for_mt5_validation",
        "recovery_plan_bridge_required_for_standalone_tester",
        "recovery_plan_standalone_strategy_tester_allowed",
        "recovery_plan_standalone_strategy_tester_note",
        "recovery_plan_next_action",
        "recovery_plan_operator_summary_status",
        "recovery_plan_operator_summary_ready_for_mt5_validation",
        "recovery_plan_operator_summary_bridge_required_for_standalone_tester",
        "recovery_plan_operator_summary_standalone_strategy_tester_allowed",
        "recovery_plan_operator_summary_standalone_strategy_tester_note",
        "recovery_plan_operator_summary_blocking_reasons",
        "recovery_plan_operator_summary_next_action",
        "recovery_plan_operator_summary_next_operation_action",
        "recovery_plan_operator_summary_next_operation_area",
        "recovery_plan_operator_summary_next_operation_target",
        "recovery_plan_operator_summary_next_operation_operator_step",
        "recovery_plan_operator_summary_next_operation_verification",
        "recovery_plan_operator_summary_mt5_terminal_running",
        "recovery_plan_operator_summary_bridge_log_activity_status",
        "recovery_plan_operator_summary_ea_liveness_signal",
        "recovery_plan_operator_summary_config_get_recent",
        "recovery_plan_operator_summary_ea_post_recent",
        "recovery_plan_operator_summary_config_get_recent_but_ea_post_stale",
        "recovery_plan_operator_summary_last_ea_post_age_seconds",
        "recovery_plan_operator_summary_snapshot_fresh",
        "recovery_plan_operator_summary_history_request_id",
        "recovery_plan_operator_summary_history_done_id",
        "recovery_plan_operator_summary_history_done_matches_request",
        "recovery_plan_operator_summary_history_data_fresh",
        "recovery_plan_operator_summary_history_data_stale",
        "recovery_plan_operator_summary_history_status_server_time",
        "recovery_plan_operator_summary_history_status_server_time_age_seconds",
        "recovery_plan_operator_summary_history_status_m1_last_time",
        "recovery_plan_operator_summary_history_status_m1_last_time_age_seconds",
        "ready_for_tester_launch",
        "target",
        "focus_side",
        "runner_generated_at",
        "promotion_generated_at",
        "promotion_decision",
        "runner_promotion_generated_at",
        "current_for_execution",
        "current_promotion_generated_at",
        "selected_action_current",
        "gate_stale_reason",
        "run_id_prefix",
        "blocking_prior_action_count",
        "dry_run",
        "execute",
        "collect_only",
        "mode",
        "evidence_state",
        "execute_ready",
        "ready_to_execute",
        "ready_for_collect_execute",
        "skipped_write",
        "skip_reason",
        "written",
        "can_write",
        "walk_forward_status",
        "bridge_log_activity_status",
        "bridge_log_ea_liveness_signal",
        "bridge_log_config_get_recent",
        "bridge_log_ea_post_recent",
        "bridge_log_config_get_recent_but_ea_post_stale",
        "bridge_log_ea_post_count",
        "bridge_log_last_ea_post_at",
        "bridge_log_last_ea_post_age_seconds",
        "bridge_log_last_snapshot_post_at",
        "bridge_log_last_snapshot_post_age_seconds",
        "bridge_log_last_config_get_at",
        "bridge_log_last_config_get_age_seconds",
        "mt5_terminal_running",
        "mt5_terminal_match_count",
        "ea_attention_required",
        "ea_attention_reason",
        "ea_liveness_signal",
        "config_get_recent",
        "ea_post_recent",
        "config_get_recent_but_ea_post_stale",
        "watcher_count",
        "action_required_watcher_count",
        "stale_watcher_count",
        "max_heartbeat_age_seconds",
        "entry_count",
        "total_entry_count",
        "stale_entry_count",
        "step_count",
        "ready_entry_count",
        "ready_to_collect_count",
        "selected_count",
        "waiting_count",
        "invalid_count",
        "all_collect_ready",
        "queue_status",
        "queue_next_action",
        "queue_generated_at",
        "state",
        "progress_state",
        "next_queue_step",
        "next_report",
        "next_inputs",
        "queue_step_count",
        "queue_step_report_ready_count",
        "queue_step_collect_ready_count",
        "queue_step_waiting_report_count",
        "queue_step_launch_needed_count",
            "queue_operator_handoff_state",
            "queue_operator_handoff_collect_ready",
            "queue_operator_handoff_waiting_entry_ids",
            "queue_operator_handoff_next_queue_id",
        "queue_operator_handoff_next_step_label",
        "queue_operator_handoff_next_forward",
        "queue_operator_handoff_next_inputs",
        "queue_operator_handoff_next_report",
        "queue_operator_handoff_next_step_fingerprint",
        "queue_operator_handoff_next_step_config_fingerprint",
        "queue_operator_handoff_next_step_run_fingerprint",
        "queue_operator_handoff_next_expected_report_artifact",
        "selected_step_fingerprint",
        "selected_step_config_fingerprint",
        "selected_step_run_fingerprint",
        "selected_expected_report",
        "selected_expected_report_artifact",
            "selected_matches_queue_handoff",
        "selected",
        "launch_command_kind",
        "command_text",
        "mark_manual_run_start",
        "manual_run_start_mark_status",
        "manual_run_start_mark_attempted",
        "manual_run_start_after",
        "manual_run_start_marked",
        "manual_run_start_marked_this_run",
        "manual_run_start_after_override",
        "manual_run_start_preserved",
        "manual_run_start_state_count",
        "manual_run_start_state_marked_count",
        "manual_run_start_effective_after_values",
        "blocked",
        "running_terminal_count",
    ):
        if key in payload:
            summary[key] = payload.get(key)
    static_configs = payload.get("static_strategy_configs")
    if isinstance(static_configs, list):
        summary["static_strategy_config_count"] = len(static_configs)
        summary["static_strategy_configs"] = [str(item) for item in static_configs]
    static_candidate_labels = payload.get("static_candidate_labels")
    if isinstance(static_candidate_labels, list):
        summary["static_candidate_label_count"] = len(static_candidate_labels)
        summary["static_candidate_labels"] = [str(item) for item in static_candidate_labels]
    if name == "mt5_manual_operator_packet_with_optimization":
        next_operator_action = (
            payload.get("next_operator_action")
            if isinstance(payload.get("next_operator_action"), dict)
            else {}
        )
        summary["next_operator_action"] = next_operator_action.get("action", "")
        summary["next_operator_mode"] = next_operator_action.get("mode", "")
        summary["next_operator_instruction"] = next_operator_action.get("instruction", "")
        summary["next_operator_command_text"] = next_operator_action.get("command_text", "")
        summary["next_operator_follow_up_command_text"] = next_operator_action.get(
            "follow_up_command_text",
            "",
        )
        quick_start = (
            payload.get("back_forward_quick_start")
            if isinstance(payload.get("back_forward_quick_start"), dict)
            else {}
        )
        quick_start_current = (
            quick_start.get("current_step")
            if isinstance(quick_start.get("current_step"), dict)
            else {}
        )
        summary["back_forward_quick_start_status"] = quick_start.get("status", "")
        summary["back_forward_quick_start_step_count"] = quick_start.get("step_count", "")
        summary["back_forward_quick_start_waiting_step_count"] = quick_start.get(
            "waiting_step_count",
            "",
        )
        summary["back_forward_quick_start_current_queue_step"] = quick_start_current.get(
            "queue_step",
            "",
        )
        summary["back_forward_quick_start_current_purpose"] = quick_start_current.get(
            "purpose",
            "",
        )
        summary["back_forward_quick_start_collect_command_text"] = quick_start.get(
            "collect_command_text",
            "",
        )
        summary["back_forward_quick_start_full_queue_collect_command_text"] = quick_start.get(
            "full_queue_collect_command_text",
            "",
        )
        summary["back_forward_quick_start_auto_launch_blocked"] = quick_start.get(
            "auto_launch_blocked",
            "",
        )
        summary["back_forward_quick_start_auto_launch_blocked_reasons"] = (
            quick_start.get("auto_launch_blocked_reasons")
            if isinstance(quick_start.get("auto_launch_blocked_reasons"), list)
            else []
        )
    if isinstance(payload.get("blocked_reasons"), list):
        summary["blocked_reasons"] = payload.get("blocked_reasons", [])
        summary.setdefault("blocking_reasons", payload.get("blocked_reasons", []))
    if isinstance(payload.get("selected_item"), dict):
        selected_item = payload["selected_item"]
        summary["selected_queue_id"] = payload.get(
            "selected_queue_id",
            selected_item.get("queue_id", ""),
        )
        summary["selected_step_label"] = payload.get(
            "selected_step_label",
            selected_item.get("step_label", ""),
        )
        summary["selected_step_order"] = payload.get(
            "selected_order",
            selected_item.get("order", ""),
        )
        summary["selected_report"] = selected_item.get("report", "")
        summary["selected_forward"] = selected_item.get("forward", "")
    for key in (
        "queue_completed_count",
        "queue_completed_entry_count",
        "queue_completed_entry_ids",
    ):
        if key in payload:
            summary[key] = payload.get(key)
    if isinstance(payload.get("queue_refresh"), dict):
        queue_refresh = payload["queue_refresh"]
        summary["queue_refresh_status"] = queue_refresh.get("status", "")
        summary["queue_refresh_ok"] = queue_refresh.get("ok", "")
        summary["queue_refresh_enabled"] = queue_refresh.get("enabled", "")
        summary["queue_refresh_source_count"] = len(
            queue_refresh.get("refreshed_sources")
            if isinstance(queue_refresh.get("refreshed_sources"), list)
            else []
        )
    follow_up = payload.get("follow_up") if isinstance(payload.get("follow_up"), dict) else {}
    if follow_up:
        summary["score_weight_set_follow_up_status"] = follow_up.get("status", "")
        summary["score_weight_set_follow_up_next_action"] = follow_up.get("next_action", "")
        summary["score_weight_set_follow_up_reason"] = follow_up.get("reason", "")
        summary["score_weight_set_do_not_repeat_conversion"] = follow_up.get(
            "do_not_repeat_set_conversion", ""
        )
        for key in (
            "failure_mode",
            "sample_shortage",
            "walk_forward_status",
            "walk_forward_delta_total_r",
            "walk_forward_delta_mean_avg_r",
            "walk_forward_delta_mean_pf",
            "walk_forward_total_test_weight_r",
            "walk_forward_total_test_baseline_r",
            "walk_forward_mean_test_weight_avg_r",
            "walk_forward_mean_test_baseline_avg_r",
            "walk_forward_mean_test_weight_pf",
            "walk_forward_mean_test_baseline_pf",
            "walk_forward_total_test_weight_count",
            "walk_forward_required_test_weight_count",
            "walk_forward_missing_test_weight_count",
            "walk_forward_folds",
            "walk_forward_folds_with_weight_trades",
            "walk_forward_required_folds_with_weight_trades",
            "walk_forward_missing_folds_with_weight_trades",
            "top_candidate_threshold",
            "top_candidate_weights",
            "top_candidate_count",
            "top_candidate_avg_r",
            "top_candidate_pf",
            "top_candidate_total_r",
            "regime_status",
            "regime_dimension",
            "regime_group",
            "regime_sample_shortage",
            "regime_missing_test_weight_count",
            "regime_required_test_weight_count",
            "regime_folds_with_weight_trades",
            "regime_required_folds_with_weight_trades",
            "regime_missing_folds_with_weight_trades",
        ):
            summary[f"score_weight_set_follow_up_{key}"] = follow_up.get(key, "")
        summary["score_weight_set_follow_up_history_status_command"] = follow_up.get(
            "history_status_command", ""
        )
        summary["score_weight_set_follow_up_sample_collection_command"] = follow_up.get(
            "sample_collection_command", ""
        )
        summary["score_weight_set_follow_up_collect_command"] = follow_up.get("collect_command", "")
    if isinstance(payload.get("blocking_reasons"), list):
        summary["blocking_reasons"] = payload.get("blocking_reasons", [])
    if isinstance(payload.get("performance_comparison"), dict):
        comparison = payload["performance_comparison"]
        summary["performance_comparison_available"] = comparison.get("available", "")
        summary["performance_comparison_status"] = comparison.get("status", "")
        summary["performance_comparison_reason"] = comparison.get("reason", "")
        summary["performance_comparison_rows"] = back_forward_comparison_row_summaries(
            comparison.get("rows")
        )
        summary["performance_comparison_thresholds"] = (
            comparison.get("thresholds")
            if isinstance(comparison.get("thresholds"), dict)
            else {}
        )
    if isinstance(payload.get("back_forward_plan_validation"), dict):
        validation = payload["back_forward_plan_validation"]
        summary["back_forward_plan_validation_ready"] = validation.get("ready", "")
        summary["back_forward_plan_validation_status"] = validation.get("status", "")
        summary["back_forward_plan_validation_reasons"] = validation.get("reasons", [])
    if name == "promotion_gate":
        embedded_back_forward = (
            payload.get("mt5_back_forward_run")
            if isinstance(payload.get("mt5_back_forward_run"), dict)
            else {}
        )
        for key in (
            "generated_at",
            "run_id_prefix",
            "evidence_state",
            "mode",
            "execute",
            "dry_run",
            "collect_only",
            "step_count",
        ):
            if key in embedded_back_forward:
                summary[f"promotion_mt5_back_forward_run_{key}"] = embedded_back_forward.get(key)
    if name in {"mt5_manual_test_queue", "mt5_manual_test_queue_with_optimization"}:
        summary.update(manual_test_queue_operator_handoff_summary(payload))
        summary.update(manual_test_queue_operation_card_summary(payload))
        summary.update(manual_test_queue_current_gate_summary(payload.get("entries")))
        handoff = (
            payload.get("operator_handoff")
            if isinstance(payload.get("operator_handoff"), dict)
            else {}
        )
        summary["manual_queue_progress_state"] = (
            payload.get("progress_state") or handoff.get("progress_state", "")
        )
        summary["manual_queue_step_report_ready_count"] = payload.get("step_report_ready_count", "")
        summary["manual_queue_step_collect_ready_count"] = payload.get("step_collect_ready_count", "")
        summary["manual_queue_step_waiting_report_count"] = payload.get("step_waiting_report_count", "")
        summary["manual_queue_step_launch_needed_count"] = payload.get("step_launch_needed_count", "")
        summary["manual_queue_step_report_ready_ids"] = payload.get("step_report_ready_ids", [])
        summary["manual_queue_step_collect_ready_ids"] = payload.get("step_collect_ready_ids", [])
        summary["manual_queue_step_waiting_report_ids"] = payload.get("step_waiting_report_ids", [])
        summary["manual_queue_step_launch_needed_ids"] = payload.get("step_launch_needed_ids", [])
        summary["manual_queue_next_launch_step"] = (
            payload.get("next_launch_step") if isinstance(payload.get("next_launch_step"), dict) else {}
        )
        summary["manual_queue_entries"] = manual_test_queue_entry_summaries(payload.get("entries"))
        summary["manual_queue_stale_entries"] = manual_test_queue_stale_entry_summaries(
            payload.get("entries")
        )
        summary["manual_queue_strategy_tester_targets"] = manual_test_queue_target_summaries(
            payload.get("strategy_tester_targets"),
            payload.get("execution_checklist"),
        )
        summary["manual_queue_execution_checklist"] = manual_test_queue_checklist_summaries(
            payload.get("execution_checklist")
        )
    if name in {"mt5_manual_queue_launch", "mt5_manual_queue_launch_with_optimization"}:
        summary.update(manual_queue_launch_handoff_summary(payload))
    if name == "mt5_manual_auto_collect_watch":
        for key in (
            "collect_dry_run_command_text",
            "collect_execute_command_text",
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
            "operator_packet_auto_launch_command_text",
            "operator_packet_auto_launch_command_available",
            "operator_packet_auto_launch_blocked",
            "operator_packet_auto_launch_blocked_reasons",
            "operator_packet_auto_launch_note",
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
            "operator_packet_manual_run_start_mark_command_text",
            "operator_packet_manual_run_start_mark_command_available",
            "operator_packet_bridge_verification_commands",
            "operator_packet_bridge_verification_command_count",
            "operator_packet_bridge_verification_command_labels",
        ):
            if key in payload:
                summary[f"auto_collect_{key}"] = payload.get(key)
        for nested_key, prefix in (
            ("dry_run", "auto_collect_dry_run"),
            ("queue_launch_refresh", "auto_collect_queue_launch_refresh"),
            ("operator_packet_refresh", "operator_packet_refresh"),
            ("execution", "auto_collect_execution"),
        ):
            nested = payload.get(nested_key) if isinstance(payload.get(nested_key), dict) else {}
            if not nested:
                continue
            for key in (
                "enabled",
                "attempted",
                "completed",
                "ok",
                "returncode",
                "status",
                "next_action",
                "selected_count",
                "ready_entry_count",
                "waiting_count",
                "invalid_count",
                "queue_refresh_status",
                "queue_refresh_ok",
                "blocked",
                "blocked_reasons",
                "launch_command_kind",
                "running_terminal_count",
                "selected_matches_queue_handoff",
                "next_queue_step",
                "next_operator_action",
                "next_operator_mode",
                "next_operator_instruction",
                "next_operator_command_text",
                "next_operator_before_mt5_command_text",
                "next_operator_follow_up_command_text",
                "auto_launch_command_text",
                "auto_launch_command_available",
                "auto_launch_blocked",
                "auto_launch_blocked_reasons",
                "auto_launch_note",
                "manual_run_start_mark_command_text",
                "step_count",
                "static_strategy_config_count",
                "static_candidate_label_count",
                "launch_state",
                "bridge_status",
                "bridge_ready_for_mt5_validation",
                "standalone_strategy_tester_allowed",
                "bridge_verification_commands",
                "bridge_verification_command_count",
                "bridge_verification_command_labels",
                "strategy_status",
                "strategy_back_forward_decision_status",
                "strategy_back_forward_decision_adoptable",
                "strategy_back_forward_decision_next_action",
                "strategy_back_forward_decision_collect_command_text",
                "strategy_back_forward_decision_sample_shortage_recovery_command_text",
                "strategy_back_forward_decision_sample_shortage_recovery_range_strategy",
                "strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date",
                "strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date",
                "strategy_operator_decision_status",
                "strategy_operator_decision_verdict",
                "strategy_operator_decision_adoptable",
                "strategy_operator_decision_primary_blocker",
                "strategy_operator_decision_primary_reason",
                "strategy_operator_decision_next_action",
                "strategy_operator_decision_summary",
                "strategy_operator_decision_command_text",
                "strategy_operator_decision_follow_up_command_text",
                "strategy_source_time_refresh_status",
                "strategy_source_time_issue_labels",
                "strategy_source_time_candidate_issue_labels",
                "strategy_source_time_refresh_analysis_command_text",
                "strategy_buy_candidate_gap_status",
                "strategy_buy_candidate_gap_reason",
                "strategy_buy_candidate_gap_diagnostic_labels",
                "strategy_buy_candidate_gap_collect_refresh_command_text",
                "output_json",
                "output_md",
            ):
                if key in nested:
                    summary[f"{prefix}_{key}"] = nested.get(key)
            for key in (
                "static_strategy_configs",
                "static_candidate_labels",
                "strategy_source_time_issue_labels",
                "strategy_source_time_candidate_issue_labels",
                "strategy_buy_candidate_gap_diagnostic_labels",
            ):
                values = nested.get(key)
                if isinstance(values, list):
                    summary[f"{prefix}_{key}"] = [str(item) for item in values]
    if name == "bridge_recovery_plan":
        summary.update(bridge_recovery_operator_summary_fields(payload))
        summary.update(bridge_recovery_operation_card_summary(payload))
    if name == "mt5_strategy_tester_analysis":
        summary.update(mt5_strategy_tester_analysis_fields(payload))
    if name == "mt5_manual_collect_run":
        summary["manual_collect_run_planned"] = manual_collect_entry_summaries(payload.get("planned"))
        summary["manual_collect_run_skipped"] = manual_collect_entry_summaries(payload.get("skipped"))
        summary["manual_collect_run_invalid"] = manual_collect_entry_summaries(payload.get("invalid"))
        summary["manual_collect_run_step_completion_audit"] = manual_collect_step_completion_summaries(
            payload.get("step_completion_audit")
        )
    if name == "rr_strategy_experiment":
        summary_rows = payload.get("summary_rows") if isinstance(payload.get("summary_rows"), list) else []
        audit_rows = payload.get("adoption_audit") if isinstance(payload.get("adoption_audit"), list) else []
        strategy_rows = [row for row in summary_rows if isinstance(row, dict)]
        adoption_rows = [row for row in audit_rows if isinstance(row, dict)]
        candidate_rows = [row for row in adoption_rows if row.get("status") == "candidate"]
        rejected_rows = [row for row in adoption_rows if row.get("status") == "rejected"]
        best_row = strategy_rows[0] if strategy_rows else {}
        best_candidate_row = (
            max(candidate_rows, key=lambda row: optional_float(row.get("balance_score")) or -999999.0)
            if candidate_rows
            else {}
        )
        summary["rr_strategy_count"] = len(strategy_rows)
        summary["rr_adoption_audit_count"] = len(adoption_rows)
        summary["rr_adoption_candidate_count"] = len(candidate_rows)
        summary["rr_adoption_rejected_count"] = len(rejected_rows)
        summary["rr_best_strategy"] = best_row.get("strategy", "")
        summary["rr_best_policy"] = best_row.get("policy", "")
        summary["rr_best_avg_r"] = best_row.get("avg_r", "")
        summary["rr_best_pf"] = best_row.get("pf", "")
        summary["rr_best_total_r"] = best_row.get("total_r", "")
        summary["rr_candidate_strategy"] = best_candidate_row.get("strategy", "")
        summary["rr_candidate_balance_score"] = best_candidate_row.get("balance_score", "")
        summary["rr_rejected_strategies"] = [
            str(row.get("strategy", ""))
            for row in rejected_rows
            if row.get("strategy")
        ]
        summary["rr_rejection_reasons"] = sorted(
            {
                str(reason)
                for row in rejected_rows
                for reason in (row.get("reasons") if isinstance(row.get("reasons"), list) else [])
                if reason
            }
        )
    if isinstance(payload.get("adoption_decision"), dict):
        adoption = payload["adoption_decision"]
        summary["winrate_adopted"] = adoption.get("adopted")
        summary["winrate_rules"] = adoption.get("rules", "")
        summary["winrate_reasons"] = adoption.get("reasons", "")
    if isinstance(payload.get("walk_rows"), list):
        walk_rows = [row for row in payload["walk_rows"] if isinstance(row, dict)]
        fitted_counts = [optional_int(row.get("test_fitted_count")) for row in walk_rows]
        fitted_counts = [count for count in fitted_counts if count is not None]
        fitted_pf_values: list[float] = []
        fitted_avg_r_values: list[float] = []
        for row in walk_rows:
            try:
                fitted_pf_values.append(float(row.get("test_fitted_pf")))
            except (TypeError, ValueError):
                pass
            try:
                fitted_avg_r_values.append(float(row.get("test_fitted_avg_r")))
            except (TypeError, ValueError):
                pass
        summary["winrate_walk_fold_count"] = len(walk_rows)
        summary["winrate_walk_total_fitted_count"] = sum(fitted_counts)
        if fitted_pf_values:
            summary["winrate_walk_mean_fitted_pf"] = round(sum(fitted_pf_values) / len(fitted_pf_values), 4)
        if fitted_avg_r_values:
            summary["winrate_walk_mean_fitted_avg_r"] = round(
                sum(fitted_avg_r_values) / len(fitted_avg_r_values),
                4,
            )
    walk_forward = payload.get("walk_forward") if isinstance(payload.get("walk_forward"), dict) else {}
    walk_forward_aggregate = (
        walk_forward.get("aggregate") if isinstance(walk_forward.get("aggregate"), dict) else {}
    )
    is_score_weight_search = name.startswith("score_weight_search_")
    if walk_forward_aggregate:
        summary["walk_forward_aggregate_status"] = walk_forward_aggregate.get("status", "")
        summary["walk_forward_aggregate_recommendation"] = walk_forward_aggregate.get("recommendation", "")
    if is_score_weight_search and walk_forward_aggregate:
        score_weight_walk_summary_fields(summary, "score_weight_walk", walk_forward_aggregate)
    if is_score_weight_search and isinstance(payload.get("top_weight_candidate"), dict):
        score_weight_candidate_summary_fields(
            summary,
            "score_weight_top",
            payload["top_weight_candidate"],
        )
    if is_score_weight_search:
        regime_search = payload.get("regime_search") if isinstance(payload.get("regime_search"), dict) else {}
        best_regime = (
            regime_search.get("best_regime_candidate")
            if isinstance(regime_search.get("best_regime_candidate"), dict)
            else {}
        )
        if best_regime:
            score_weight_candidate_summary_fields(summary, "score_weight_regime", best_regime)
            regime_walk = (
                best_regime.get("walk_forward")
                if isinstance(best_regime.get("walk_forward"), dict)
                else {}
            )
            regime_walk_aggregate = (
                regime_walk.get("aggregate")
                if isinstance(regime_walk.get("aggregate"), dict)
                else {}
            )
            if regime_walk_aggregate:
                score_weight_walk_summary_fields(
                    summary,
                    "score_weight_regime_walk",
                    regime_walk_aggregate,
                )
    if isinstance(payload.get("summary"), dict):
        nested = payload["summary"]
        for key in (
            "all_sources_synced",
            "all_compiled_fresh",
            "all_tester_sets_synced",
            "all_tester_configs_synced",
            "all_required_tester_config_references_ready",
        ):
            if key in nested:
                summary[key] = nested.get(key)
    if isinstance(payload.get("status_watch_heartbeat"), dict):
        watch = payload["status_watch_heartbeat"]
        summary["status_watch_compatible"] = watch.get("compatible")
        summary["status_watch_implementation_version"] = watch.get("implementation_version")
        for quick_key, prefix in (
            ("mt5_operator_handoff_quick_input", "status_watch_mt5_operator_quick"),
            ("manual_test_queue_operator_handoff_quick_input", "status_watch_manual_queue_quick"),
            (
                "manual_queue_launch_queue_operator_handoff_quick_input",
                "status_watch_manual_queue_launch_quick",
            ),
            ("manual_collect_run_handoff_quick_input", "status_watch_manual_collect_quick"),
        ):
            quick_input = watch.get(quick_key)
            if isinstance(quick_input, dict):
                summary["status_watch_" + quick_key] = quick_input
                summary.update(quick_input_summary_fields(prefix, quick_input))
        for key in (
            "manual_test_queue_progress_state",
            "manual_test_queue_step_collect_ready_count",
            "manual_test_queue_step_report_ready_ids",
            "manual_test_queue_step_collect_ready_ids",
            "manual_test_queue_step_waiting_report_ids",
            "manual_test_queue_step_launch_needed_ids",
            "manual_test_queue_collect_check_command_text",
            "manual_queue_launch_refresh_enabled",
            "manual_queue_launch_refresh_returncode",
            "manual_queue_launch_refresh_completed",
            "manual_queue_launch_refresh_status",
            "manual_queue_launch_refresh_queue_refresh_status",
            "manual_queue_launch_refresh_queue_refresh_ok",
            "manual_queue_launch_refresh_queue_refresh_source_count",
            "manual_queue_launch_refresh_selected",
            "manual_queue_launch_refresh_selected_queue_id",
            "manual_queue_launch_refresh_selected_step_label",
            "manual_queue_launch_refresh_blocked",
            "manual_queue_launch_refresh_blocked_reasons",
            "manual_collect_refresh_enabled",
            "manual_collect_refresh_returncode",
            "manual_collect_refresh_completed",
            "manual_collect_refresh_status",
            "manual_collect_refresh_queue_refresh_status",
            "manual_collect_refresh_queue_refresh_ok",
            "manual_collect_refresh_queue_refresh_source_count",
            "manual_collect_refresh_selected_count",
            "manual_collect_refresh_waiting_count",
            "manual_collect_refresh_invalid_count",
            "manual_collect_run_queue_step_count",
            "manual_collect_run_queue_step_report_ready_count",
            "manual_collect_run_queue_step_collect_ready_count",
            "manual_collect_run_queue_step_waiting_report_count",
            "manual_collect_run_queue_step_launch_needed_count",
            "manual_collect_run_step_completion_audit",
            "manual_test_queue_with_optimization_status",
            "manual_test_queue_with_optimization_next_action",
            "manual_test_queue_with_optimization_entry_count",
            "manual_test_queue_with_optimization_step_count",
            "manual_test_queue_with_optimization_waiting_count",
            "manual_queue_launch_with_optimization_status",
            "manual_queue_launch_with_optimization_next_action",
            "manual_queue_launch_with_optimization_selected",
            "manual_queue_launch_with_optimization_selected_item",
            "manual_queue_launch_with_optimization_selected_matches_queue_handoff",
            "manual_queue_launch_with_optimization_queue_operator_handoff_state",
            "manual_queue_launch_with_optimization_queue_operator_handoff_next_mt5_step",
            "manual_queue_launch_with_optimization_queue_operator_handoff_collect_ready",
            "manual_queue_launch_with_optimization_queue_operator_handoff_waiting_entry_ids",
            "manual_queue_launch_with_optimization_queue_operator_handoff_collect_dry_run_command_text",
            "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_command_text",
            "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_analysis_command_text",
            "manual_queue_launch_with_optimization_launch_command_kind",
            "manual_queue_launch_with_optimization_blocked",
            "manual_queue_launch_with_optimization_blocked_reasons",
            "manual_queue_launch_with_optimization_running_terminal_count",
            "manual_collect_with_optimization_status",
            "manual_collect_with_optimization_next_action",
            "manual_collect_with_optimization_selected_count",
            "manual_collect_with_optimization_waiting_count",
            "manual_collect_with_optimization_invalid_count",
            "manual_collect_with_optimization_queue_step_count",
            "manual_collect_with_optimization_queue_step_waiting_report_count",
            "manual_collect_with_optimization_queue_step_launch_needed_count",
            "manual_collect_with_optimization_refresh_enabled",
            "manual_collect_with_optimization_refresh_returncode",
            "manual_collect_with_optimization_refresh_completed",
            "manual_collect_with_optimization_refresh_status",
            "manual_collect_with_optimization_refresh_queue_refresh_status",
            "manual_collect_with_optimization_refresh_queue_refresh_ok",
            "manual_collect_with_optimization_refresh_queue_refresh_source_count",
            "manual_collect_with_optimization_refresh_selected_count",
            "manual_collect_with_optimization_refresh_waiting_count",
            "manual_collect_with_optimization_refresh_invalid_count",
            "manual_queue_launch_with_optimization_refresh_enabled",
            "manual_queue_launch_with_optimization_refresh_returncode",
            "manual_queue_launch_with_optimization_refresh_completed",
            "manual_queue_launch_with_optimization_refresh_status",
            "manual_queue_launch_with_optimization_refresh_queue_refresh_status",
            "manual_queue_launch_with_optimization_refresh_queue_refresh_ok",
            "manual_queue_launch_with_optimization_refresh_queue_refresh_source_count",
            "manual_queue_launch_with_optimization_refresh_selected",
            "manual_queue_launch_with_optimization_refresh_selected_queue_id",
            "manual_queue_launch_with_optimization_refresh_selected_step_label",
            "manual_queue_launch_with_optimization_refresh_blocked",
            "manual_queue_launch_with_optimization_refresh_blocked_reasons",
        ):
            if key in watch:
                summary["status_watch_" + key] = watch.get(key)
    if isinstance(payload.get("execution_hints"), dict):
        summary["execution_hints"] = extract_command_hints(payload["execution_hints"])
    summary.update(mt5_operator_summary_fields(payload))
    summary.update(mt5_operator_handoff_summary(payload))
    summary.update(manual_strategy_tester_summary(payload))
    summary.update(mt5_strategy_tester_pack_summary(payload))
    summary.update(manual_collect_readiness_summary(payload))
    if isinstance(payload.get("manual_prerequisites"), dict):
        prerequisites = payload["manual_prerequisites"]
        summary["manual_prerequisites_ready"] = prerequisites.get("ready")
        summary["manual_prerequisites_reasons"] = prerequisites.get("reasons", [])
        summary["manual_prerequisites_compile_status_path"] = prerequisites.get("path", "")
        summary["manual_prerequisites_generated_at"] = prerequisites.get("generated_at", "")
    if isinstance(payload.get("next_action_runner"), dict):
        runner = payload["next_action_runner"]
        blocking_prior_actions = blocking_prior_action_summaries(runner.get("blocking_prior_actions"))
        advisory_prior_actions = blocking_prior_action_summaries(runner.get("advisory_prior_actions"))
        summary["next_action_runner"] = {
            **extract_command_hints(runner),
            "target": runner.get("target", ""),
            "focus_side": runner.get("focus_side", ""),
            "config": runner.get("config", ""),
            "set": runner.get("set", ""),
            "manual_strategy_tester_available": runner.get("manual_strategy_tester_available", ""),
            "manual_collect_only_command_text": runner.get("manual_collect_only_command_text", ""),
            "manual_run_start_after": runner.get("manual_run_start_after", ""),
            "manual_collect_ready": runner.get("manual_collect_ready", ""),
            "manual_collect_status": runner.get("manual_collect_status", ""),
            "manual_collect_csv_count": runner.get("manual_collect_csv_count", ""),
            "manual_collect_modified_after": runner.get("manual_collect_modified_after", ""),
            "manual_collect_reason": runner.get("manual_collect_reason", ""),
            "manual_collect_blocking_reasons": runner.get("manual_collect_blocking_reasons", []),
            "manual_collect_next_action": runner.get("manual_collect_next_action", ""),
            "manual_step_count": runner.get("manual_step_count", ""),
            "manual_steps": runner.get("manual_steps", []),
        }
        summary["next_action_runner_current_for_execution"] = runner.get("current_for_execution")
        summary["next_action_runner_gate_stale_reason"] = runner.get("gate_stale_reason", "")
        summary["next_action_runner_runner_promotion_generated_at"] = runner.get(
            "runner_promotion_generated_at", ""
        )
        summary["next_action_runner_current_promotion_generated_at"] = runner.get(
            "current_promotion_generated_at", ""
        )
        summary["next_action_runner_selected_action_current"] = runner.get("selected_action_current", "")
        summary["next_action_runner_blocking_prior_action_count"] = runner.get("blocking_prior_action_count", "")
        summary["next_action_runner_blocking_prior_actions"] = blocking_prior_actions
        summary["next_action_runner_blocking_prior_action_summary"] = blocking_prior_action_text(
            blocking_prior_actions
        )
        summary["next_action_runner_advisory_prior_action_count"] = runner.get("advisory_prior_action_count", "")
        summary["next_action_runner_advisory_prior_actions"] = advisory_prior_actions
        summary["next_action_runner_advisory_prior_action_summary"] = blocking_prior_action_text(
            advisory_prior_actions
        )
    if isinstance(payload.get("back_forward_execution"), dict):
        execution = payload["back_forward_execution"]
        summary["back_forward_execution_ready"] = execution.get("ready")
        summary["back_forward_execution_status"] = execution.get("status")
        summary["back_forward_execution_reasons"] = execution.get("reasons", [])
        if execution.get("execute_hint"):
            summary["back_forward_execute_hint"] = str(execution.get("execute_hint"))
    if isinstance(payload.get("latest_snapshot"), dict):
        snapshot = payload["latest_snapshot"]
        summary["latest_snapshot_fresh"] = snapshot.get("fresh")
        summary["latest_snapshot_age_seconds"] = snapshot.get("age_seconds")
        summary["latest_snapshot_server_time"] = snapshot.get("server_time", "")
    if isinstance(payload.get("history_request"), dict):
        request = payload["history_request"]
        summary["history_request_pending"] = request.get("pending")
        summary["history_request_stale_pending"] = request.get("stale_pending")
    if isinstance(payload.get("bridge_log"), dict):
        bridge_log = payload["bridge_log"]
        activity = bridge_log.get("activity") if isinstance(bridge_log.get("activity"), dict) else {}
        last_ea_post = activity.get("last_ea_post") if isinstance(activity.get("last_ea_post"), dict) else {}
        last_snapshot_post = (
            activity.get("last_snapshot_post") if isinstance(activity.get("last_snapshot_post"), dict) else {}
        )
        last_config_get = activity.get("last_config_get") if isinstance(activity.get("last_config_get"), dict) else {}
        summary["bridge_log_activity_status"] = activity.get("status", "")
        summary["bridge_log_ea_liveness_signal"] = activity.get("ea_liveness_signal", "")
        summary["bridge_log_config_get_recent"] = activity.get("config_get_recent", "")
        summary["bridge_log_ea_post_recent"] = activity.get("ea_post_recent", "")
        summary["bridge_log_config_get_recent_but_ea_post_stale"] = activity.get(
            "config_get_recent_but_ea_post_stale", ""
        )
        summary["bridge_log_ea_post_count"] = activity.get("ea_post_count")
        summary["bridge_log_last_ea_post_at"] = last_ea_post.get("timestamp", "")
        summary["bridge_log_last_ea_post_age_seconds"] = last_ea_post.get("age_seconds")
        summary["bridge_log_last_snapshot_post_at"] = last_snapshot_post.get("timestamp", "")
        summary["bridge_log_last_snapshot_post_age_seconds"] = last_snapshot_post.get("age_seconds")
        summary["bridge_log_last_config_get_at"] = last_config_get.get("timestamp", "")
        summary["bridge_log_last_config_get_age_seconds"] = last_config_get.get("age_seconds")
    if isinstance(payload.get("mt5_terminal"), dict):
        mt5_terminal = payload["mt5_terminal"]
        summary["mt5_terminal_running"] = mt5_terminal.get("running")
        summary["mt5_terminal_match_count"] = mt5_terminal.get("match_count")
    if isinstance(payload.get("ea_attention"), dict):
        ea_attention = payload["ea_attention"]
        summary["ea_attention_required"] = ea_attention.get("required")
        summary["ea_attention_reason"] = ea_attention.get("reason", "")
        summary["ea_liveness_signal"] = ea_attention.get("ea_liveness_signal", "")
        summary["config_get_recent"] = ea_attention.get("config_get_recent", "")
        summary["ea_post_recent"] = ea_attention.get("ea_post_recent", "")
        summary["config_get_recent_but_ea_post_stale"] = ea_attention.get(
            "config_get_recent_but_ea_post_stale", ""
        )
    return summary


def runtime_coverage(
    workspace: Path,
    *,
    now_epoch: float,
    max_artifact_age_seconds: int,
    max_history_data_age_seconds: int = DEFAULT_MAX_HISTORY_DATA_AGE_SECONDS,
) -> list[dict[str, Any]]:
    required = [
        artifact_summary(
            workspace,
            name,
            path,
            now_epoch=now_epoch,
            max_age_seconds=max_artifact_age_seconds,
            max_history_data_age_seconds=max_history_data_age_seconds,
        )
        for name, path in RUNTIME_ARTIFACTS
    ]
    optional = [
        artifact_summary(
            workspace,
            name,
            path,
            now_epoch=now_epoch,
            max_age_seconds=max_artifact_age_seconds,
            max_history_data_age_seconds=max_history_data_age_seconds,
        )
        for name, path in OPTIONAL_RUNTIME_ARTIFACTS
        if (workspace / path).exists()
    ]
    artifacts = required + optional
    apply_manual_queue_collect_overrides_to_runtime_artifacts(artifacts)
    return artifacts


def artifact_by_name(artifacts: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next((item for item in artifacts if item.get("name") == name), {})


def artifact_mtime_epoch(artifact: dict[str, Any]) -> float | None:
    value = artifact.get("mtime_epoch")
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def promotion_gate_stale_dependency_names(artifacts: list[dict[str, Any]]) -> list[str]:
    gate = artifact_by_name(artifacts, "promotion_gate")
    gate_mtime = artifact_mtime_epoch(gate)
    if gate.get("exists") is not True or gate_mtime is None:
        return []
    stale_dependencies: list[str] = []
    for dependency_name in PROMOTION_GATE_EVIDENCE_DEPENDENCIES:
        dependency = artifact_by_name(artifacts, dependency_name)
        dependency_mtime = artifact_mtime_epoch(dependency)
        if dependency.get("exists") is True and dependency_mtime is not None and dependency_mtime > gate_mtime:
            if not dependency_relevant_for_promotion_gate(dependency_name, dependency):
                continue
            if dependency_current_for_promotion_gate(dependency_name, dependency, gate):
                continue
            stale_dependencies.append(dependency_name)
    return stale_dependencies


def strategy_tester_analysis_stale_dependency_names(artifacts: list[dict[str, Any]]) -> list[str]:
    analysis = artifact_by_name(artifacts, "mt5_strategy_tester_analysis")
    if analysis.get("exists") is not True:
        return []
    source_generated_at_by_label = (
        analysis.get("strategy_tester_analysis_source_artifact_generated_at_by_label")
        if isinstance(
            analysis.get("strategy_tester_analysis_source_artifact_generated_at_by_label"),
            dict,
        )
        else {}
    )
    stale_dependencies: list[str] = []
    for source_label, artifact_name in STRATEGY_TESTER_ANALYSIS_STABLE_DEPENDENCIES:
        dependency = artifact_by_name(artifacts, artifact_name)
        if dependency.get("exists") is not True:
            continue
        current_generated_at = str(dependency.get("generated_at") or "")
        if not current_generated_at:
            continue
        embedded_generated_at = str(source_generated_at_by_label.get(source_label) or "")
        if embedded_generated_at != current_generated_at:
            stale_dependencies.append(source_label)
    return stale_dependencies


def positive_int_field(row: dict[str, Any], field: str) -> bool:
    value = optional_int(row.get(field))
    return value is not None and value > 0


def dependency_relevant_for_promotion_gate(
    dependency_name: str,
    dependency: dict[str, Any],
) -> bool:
    if dependency_name == "mt5_manual_test_queue":
        return manual_test_queue_relevant_for_promotion_gate(dependency)
    if dependency_name == "mt5_manual_collect_run":
        return manual_collect_run_relevant_for_promotion_gate(dependency)
    return True


def manual_test_queue_relevant_for_promotion_gate(dependency: dict[str, Any]) -> bool:
    status = str(dependency.get("status") or "")
    if status in MANUAL_QUEUE_PROMOTION_READY_STATUSES:
        return True
    if dependency.get("all_collect_ready") is True:
        return True
    return any(
        positive_int_field(dependency, field)
        for field in (
            "ready_to_collect_count",
            "ready_entry_count",
            "step_report_ready_count",
            "step_collect_ready_count",
            "manual_queue_step_report_ready_count",
        )
    )


def manual_collect_run_relevant_for_promotion_gate(dependency: dict[str, Any]) -> bool:
    status = str(dependency.get("status") or "")
    if status in MANUAL_COLLECT_PROMOTION_READY_STATUSES:
        return True
    if isinstance(dependency.get("manual_collect_run_planned"), list) and dependency["manual_collect_run_planned"]:
        return True
    return any(
        positive_int_field(dependency, field)
        for field in (
            "ready_entry_count",
            "selected_count",
            "execution_count",
        )
    )


def dependency_current_for_promotion_gate(
    dependency_name: str,
    dependency: dict[str, Any],
    gate: dict[str, Any],
) -> bool:
    gate_generated_at = str(gate.get("generated_at") or "")
    if not gate_generated_at:
        return False
    if dependency_name == "mt5_tester_status":
        return (
            dependency.get("next_action_runner_current_for_execution") is True
            and str(dependency.get("next_action_runner_current_promotion_generated_at") or "") == gate_generated_at
        )
    if dependency_name == "mt5_back_forward_run":
        return mt5_back_forward_run_current_for_promotion_gate(dependency, gate)
    if dependency_name == "mt5_manual_test_queue":
        return manual_test_queue_current_for_promotion_gate(dependency, gate_generated_at)
    if dependency_name == "mt5_manual_collect_run":
        return manual_collect_run_current_for_promotion_gate(dependency, gate_generated_at)
    return False


def mt5_back_forward_run_current_for_promotion_gate(
    dependency: dict[str, Any],
    gate: dict[str, Any],
) -> bool:
    required_pairs = (
        ("generated_at", "promotion_mt5_back_forward_run_generated_at"),
        ("run_id_prefix", "promotion_mt5_back_forward_run_run_id_prefix"),
        ("evidence_state", "promotion_mt5_back_forward_run_evidence_state"),
        ("mode", "promotion_mt5_back_forward_run_mode"),
    )
    for dependency_key, gate_key in required_pairs:
        dependency_value = str(dependency.get(dependency_key) or "")
        gate_value = str(gate.get(gate_key) or "")
        if not dependency_value or not gate_value or dependency_value != gate_value:
            return False
    optional_pairs = (
        ("execute", "promotion_mt5_back_forward_run_execute"),
        ("dry_run", "promotion_mt5_back_forward_run_dry_run"),
        ("collect_only", "promotion_mt5_back_forward_run_collect_only"),
        ("step_count", "promotion_mt5_back_forward_run_step_count"),
    )
    for dependency_key, gate_key in optional_pairs:
        if dependency_key not in dependency or gate_key not in gate:
            continue
        if str(dependency.get(dependency_key)) != str(gate.get(gate_key)):
            return False
    return True


def gate_aligned_manual_rows(rows: Any, gate_generated_at: str) -> tuple[bool, bool]:
    if not isinstance(rows, list):
        return False, False
    saw_gate_row = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_gate = str(
            row.get("current_promotion_generated_at")
            or row.get("promotion_generated_at")
            or ""
        )
        current_for_execution = row.get("current_for_execution")
        if not row_gate and current_for_execution in ("", None):
            continue
        saw_gate_row = True
        if current_for_execution is False:
            return True, False
        if row_gate != gate_generated_at:
            return True, False
    return saw_gate_row, True


def manual_test_queue_current_for_promotion_gate(
    dependency: dict[str, Any],
    gate_generated_at: str,
) -> bool:
    if str(dependency.get("status") or "") == "stale_runner_artifacts":
        return False
    stale_entry_count = optional_int(dependency.get("stale_entry_count"))
    if stale_entry_count is not None and stale_entry_count > 0:
        return False
    saw_gate_row, aligned = gate_aligned_manual_rows(
        dependency.get("manual_queue_entries"),
        gate_generated_at,
    )
    return saw_gate_row and aligned


def manual_collect_run_current_for_promotion_gate(
    dependency: dict[str, Any],
    gate_generated_at: str,
) -> bool:
    if str(dependency.get("queue_status") or "") == "stale_runner_artifacts":
        return False
    if dependency.get("queue_refresh_ok") is False:
        return False
    rows: list[dict[str, Any]] = []
    for key in ("manual_collect_run_planned", "manual_collect_run_skipped", "manual_collect_run_invalid"):
        value = dependency.get(key)
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    saw_gate_row, aligned = gate_aligned_manual_rows(rows, gate_generated_at)
    return saw_gate_row and aligned


def mt5_status_manual_strategy_tester_handoff_active(status: dict[str, Any]) -> bool:
    if str(status.get("operational_status") or "") != "blocked_running_terminal":
        return False
    if status.get("mt5_operator_handoff_recommended_path") != "manual_strategy_tester":
        return False
    if status.get("mt5_operator_handoff_manual_strategy_tester_available") is False:
        return False
    return bool(
        str(status.get("mt5_operator_handoff_next_queue_id") or "")
        or str(status.get("mt5_operator_handoff_next_step_label") or "")
    )


def mql5_artifacts_newer_than_compile_status(
    artifacts: list[dict[str, Any]],
    mql5_artifacts: list[dict[str, Any]],
) -> list[str]:
    compile_status = artifact_by_name(artifacts, "mt5_compile_status")
    compile_mtime = artifact_mtime_epoch(compile_status)
    if compile_status.get("exists") is not True or compile_mtime is None:
        return []
    newer: list[str] = []
    for row in mql5_artifacts:
        row_mtime = artifact_mtime_epoch(row)
        if row.get("exists") is True and row_mtime is not None and row_mtime > compile_mtime:
            newer.append(str(row.get("name") or row.get("path") or "unknown"))
    return newer


def reason_values(reasons: list[str], prefix: str) -> list[str]:
    values: list[str] = []
    marker = prefix + ":"
    for reason in reasons:
        if not reason.startswith(marker):
            continue
        tail = reason[len(marker) :]
        values.extend(part for part in tail.split(",") if part)
    return values


def reason_present(reasons: list[str], prefix: str) -> bool:
    marker = prefix + ":"
    return any(reason == prefix or reason.startswith(marker) for reason in reasons)


def back_forward_incomplete_reason(evidence_state: str) -> str:
    state = evidence_state or "unknown"
    if state == "executed_sample_shortage":
        return f"mt5_back_forward_executed_sample_shortage:{state}"
    if state.startswith("executed_"):
        return f"mt5_back_forward_executed_not_adoptable:{state}"
    return f"mt5_back_forward_not_executed:{state}"


def is_back_forward_reason(reason: str) -> bool:
    return reason.startswith(BACK_FORWARD_REASON_PREFIXES)


def history_refresh_reasons(reasons: list[str]) -> list[str]:
    history_names = {"history", "history_status"}
    filtered: list[str] = []
    for reason in reasons:
        if reason.startswith("history_request_"):
            filtered.append(reason)
            continue
        if reason.startswith("history_data_stale:"):
            filtered.append(reason)
            continue
        stale_values = [
            value
            for value in reason_values([reason], "stale_runtime_artifacts")
            if value in history_names
        ]
        if stale_values:
            filtered.append("stale_runtime_artifacts:" + ",".join(stale_values))
            continue
        missing_values = [
            value
            for value in reason_values([reason], "missing_runtime_artifacts")
            if "latest_history" in value or "latest_history_status" in value
        ]
        if missing_values:
            filtered.append("missing_runtime_artifacts:" + ",".join(missing_values))
    return filtered


def fit_quality_refresh_reasons(reasons: list[str]) -> list[str]:
    fit_names = {"winrate_fit", "risk_shape_weight_search"}
    filtered: list[str] = []
    for reason in reasons:
        stale_values = [
            value
            for value in reason_values([reason], "stale_runtime_artifacts")
            if value in fit_names
        ]
        if stale_values:
            filtered.append("stale_runtime_artifacts:" + ",".join(stale_values))
            continue
        missing_values = [
            value
            for value in reason_values([reason], "missing_runtime_artifacts")
            if "latest_winrate_fit" in value or "latest_risk_shape_weight_search" in value
        ]
        if missing_values:
            filtered.append("missing_runtime_artifacts:" + ",".join(missing_values))
    return filtered


def command_step(label: str, command: str) -> dict[str, str]:
    return {"label": label, "command": command}


def mt5_tester_status_refresh_command() -> str:
    return (
        "python3 methods/swing_eval/analysis/mt5_tester_status.py "
        "--back-forward-run runtime/latest_mt5_back_forward_run.json "
        "--manual-test-queue runtime/latest_mt5_manual_test_queue.json "
        "--manual-queue-launch runtime/latest_mt5_manual_queue_launch.json "
        "--manual-collect-run runtime/latest_mt5_manual_collect_run.json "
        f"--manual-test-queue-with-optimization {DEFAULT_MT5_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
        f"--manual-queue-launch-with-optimization {DEFAULT_MT5_MANUAL_QUEUE_LAUNCH_WITH_OPTIMIZATION} "
        f"--manual-collect-with-optimization {DEFAULT_MT5_MANUAL_COLLECT_WITH_OPTIMIZATION} "
        f"--manual-operator-packet-with-optimization {DEFAULT_MT5_MANUAL_OPERATOR_PACKET_WITH_OPTIMIZATION} "
        "--bridge-recovery-plan runtime/latest_bridge_recovery_plan.json "
        "--output-json runtime/latest_mt5_tester_status.json "
        "--output-md runtime/latest_mt5_tester_status.md"
    )


def add_next_action(actions: list[dict[str, Any]], action: dict[str, Any]) -> None:
    action_id = action.get("id")
    if action_id and any(existing.get("id") == action_id for existing in actions):
        return
    actions.append(action)


def present_value(value: Any) -> bool:
    return value not in (None, "")


def score_weight_part(source: dict[str, Any], key: str, label: str) -> str:
    value = source.get(key)
    return f"{label}={value}" if present_value(value) else ""


def append_score_weight_line(manual_steps: list[str], label: str, parts: list[str]) -> None:
    filtered = [part for part in parts if part]
    if filtered:
        manual_steps.append(f"{label}: " + ", ".join(filtered))


def append_score_sample_collection_mt5_details(
    manual_steps: list[str],
    source: dict[str, Any],
    step: dict[str, Any],
) -> None:
    if not step:
        return
    dates = str(step.get("dates") or "")
    if not dates and (step.get("from_date") or step.get("to_date")):
        dates = f"{step.get('from_date', '')} -> {step.get('to_date', '')}"
    start_after = str(
        source.get("manual_run_start_after")
        or step.get("manual_run_start_after")
        or source.get("manual_collect_modified_after")
        or ""
    )
    report_name = str(step.get("report_name") or step.get("report") or "")
    expected_report_artifact = str(
        step.get("expected_report_artifact")
        or step.get("expected_report")
        or "HTML report + Agent CSV"
    )
    input_parts: list[str] = []
    for value, label in (
        (step.get("expert") or "", "Expert"),
        (step.get("symbol") or "", "Symbol"),
        (step.get("period") or "", "Period"),
        (step.get("model_label") or step.get("model") or "", "Model"),
        (dates, "Dates"),
        (step.get("forward_label") or step.get("forward") or "", "Forward"),
        (
            step.get("optimization_label")
            or step.get("optimization")
            or "",
            "Optimization",
        ),
        (step.get("run_type") or "", "Run type"),
        (step.get("config") or "", "Config"),
        (step.get("expert_parameters") or step.get("inputs") or "", "Inputs"),
        (report_name, "Report"),
        (step.get("output_json") or step.get("run_json") or "", "OutputJSON"),
        (
            step.get("optimization_output_json")
            or step.get("report_json")
            or "",
            "ReportJSON",
        ),
    ):
        if value not in ("", None):
            input_parts.append(f"{label}={value}")
    if input_parts:
        manual_steps.append("MT5 step inputs: " + ", ".join(str(part) for part in input_parts))
    expected_artifacts = (
        step.get("expected_artifacts") if isinstance(step.get("expected_artifacts"), dict) else {}
    )
    collect_filter = operator_collect_filter_summary(
        {
            **step,
            "report": report_name,
            "expected_report_artifact": expected_report_artifact,
            "manual_run_start_after": start_after,
            "expected_artifacts": {
                "report": expected_artifacts.get("report") or report_name,
                "expected_report_artifact": (
                    expected_artifacts.get("expected_report_artifact")
                    or expected_report_artifact
                ),
                "agent_csv": expected_artifacts.get("agent_csv")
                or "swing_evaluation_trades.csv",
                "agent_csv_modified_after": (
                    expected_artifacts.get("agent_csv_modified_after") or start_after
                ),
                "run_json": (
                    expected_artifacts.get("run_json")
                    or step.get("output_json")
                    or step.get("run_json")
                    or ""
                ),
                "report_json": (
                    expected_artifacts.get("report_json")
                    or step.get("optimization_output_json")
                    or step.get("report_json")
                    or ""
                ),
            },
        }
    )
    if collect_filter:
        manual_steps.append("MT5 collect filter: " + collect_filter)


def append_score_weight_failure_steps(
    manual_steps: list[str],
    *,
    score_search: dict[str, Any],
    score_set: dict[str, Any],
) -> None:
    append_score_weight_line(
        manual_steps,
        "Score weight walk-forward",
        [
            score_weight_part(score_search, "score_weight_walk_status", "status")
            or score_weight_part(score_search, "walk_forward_aggregate_status", "status"),
            score_weight_part(score_search, "score_weight_walk_folds", "folds"),
            (
                f"test_weight={score_search.get('score_weight_walk_total_test_weight_count')}/"
                f"{score_search.get('score_weight_walk_required_test_weight_count')}"
                if present_value(score_search.get("score_weight_walk_total_test_weight_count"))
                or present_value(score_search.get("score_weight_walk_required_test_weight_count"))
                else ""
            ),
            score_weight_part(score_search, "score_weight_walk_missing_test_weight_count", "missing"),
            (
                f"folds_with_trades={score_search.get('score_weight_walk_folds_with_weight_trades')}/"
                f"{score_search.get('score_weight_walk_required_folds_with_weight_trades')}"
                if present_value(score_search.get("score_weight_walk_folds_with_weight_trades"))
                or present_value(score_search.get("score_weight_walk_required_folds_with_weight_trades"))
                else ""
            ),
            score_weight_part(score_search, "score_weight_walk_missing_folds_with_weight_trades", "missing_folds"),
            (
                f"min_fold={score_search.get('score_weight_walk_min_test_weight_fold')} "
                f"count={score_search.get('score_weight_walk_min_test_weight_count')}"
                if present_value(score_search.get("score_weight_walk_min_test_weight_fold"))
                or present_value(score_search.get("score_weight_walk_min_test_weight_count"))
                else ""
            ),
            score_weight_part(score_search, "score_weight_walk_mean_test_weight_avg_r", "mean_avg_r"),
            score_weight_part(score_search, "score_weight_walk_mean_test_weight_pf", "mean_pf"),
            score_weight_part(score_search, "score_weight_walk_delta_total_r", "delta_total_r"),
        ],
    )
    recommendation = (
        score_search.get("score_weight_walk_recommendation")
        or score_search.get("walk_forward_aggregate_recommendation")
    )
    if recommendation:
        manual_steps.append("Score weight recommendation: " + str(recommendation))
    append_score_weight_line(
        manual_steps,
        "Score weight top candidate",
        [
            score_weight_part(score_search, "score_weight_top_threshold", "threshold"),
            score_weight_part(score_search, "score_weight_top_weights", "weights"),
            score_weight_part(score_search, "score_weight_top_count", "count"),
            score_weight_part(score_search, "score_weight_top_avg_r", "avg_r"),
            score_weight_part(score_search, "score_weight_top_pf", "pf"),
            score_weight_part(score_search, "score_weight_top_total_r", "total_r"),
        ],
    )
    regime_prefix = ""
    if present_value(score_search.get("score_weight_regime_dimension")):
        regime_prefix = str(score_search.get("score_weight_regime_dimension"))
        if present_value(score_search.get("score_weight_regime_group")):
            regime_prefix += "=" + str(score_search.get("score_weight_regime_group"))
    append_score_weight_line(
        manual_steps,
        "Score weight regime candidate",
        [
            regime_prefix,
            score_weight_part(score_search, "score_weight_regime_threshold", "threshold"),
            score_weight_part(score_search, "score_weight_regime_weights", "weights"),
            score_weight_part(score_search, "score_weight_regime_count", "count"),
            score_weight_part(score_search, "score_weight_regime_avg_r", "avg_r"),
            score_weight_part(score_search, "score_weight_regime_pf", "pf"),
            score_weight_part(score_search, "score_weight_regime_total_r", "total_r"),
            score_weight_part(score_search, "score_weight_regime_walk_status", "walk_forward"),
            score_weight_part(score_search, "score_weight_regime_walk_missing_test_weight_count", "missing"),
        ],
    )
    append_score_weight_line(
        manual_steps,
        "Score weight set",
        [
            score_weight_part(score_set, "can_write", "can_write"),
            score_weight_part(score_set, "written", "written"),
            score_weight_part(score_set, "skipped_write", "skipped"),
            score_weight_part(score_set, "skip_reason", "skip_reason"),
            score_weight_part(score_set, "walk_forward_status", "walk_forward"),
        ],
    )
    append_score_weight_line(
        manual_steps,
        "Score weight follow-up",
        [
            score_weight_part(score_set, "score_weight_set_follow_up_status", "status"),
            score_weight_part(score_set, "score_weight_set_follow_up_next_action", "next_action"),
            score_weight_part(score_set, "score_weight_set_do_not_repeat_conversion", "do_not_repeat_set_conversion"),
            score_weight_part(score_set, "score_weight_set_follow_up_failure_mode", "failure_mode"),
            score_weight_part(score_set, "score_weight_set_follow_up_sample_shortage", "sample_shortage"),
            score_weight_part(
                score_set,
                "score_weight_set_follow_up_walk_forward_status",
                "walk_forward",
            ),
            score_weight_part(
                score_set,
                "score_weight_set_follow_up_walk_forward_delta_total_r",
                "delta_total_r",
            ),
            score_weight_part(
                score_set,
                "score_weight_set_follow_up_walk_forward_delta_mean_avg_r",
                "delta_mean_avg_r",
            ),
            score_weight_part(
                score_set,
                "score_weight_set_follow_up_walk_forward_delta_mean_pf",
                "delta_mean_pf",
            ),
            score_weight_part(
                score_set,
                "score_weight_set_follow_up_walk_forward_folds_with_weight_trades",
                "folds",
            ),
            score_weight_part(
                score_set,
                "score_weight_set_follow_up_walk_forward_required_folds_with_weight_trades",
                "required_folds",
            ),
            score_weight_part(
                score_set,
                "score_weight_set_follow_up_regime_status",
                "regime",
            ),
            score_weight_part(
                score_set,
                "score_weight_set_follow_up_regime_sample_shortage",
                "regime_shortage",
            ),
        ],
    )
    if score_set.get("score_weight_set_follow_up_reason"):
        manual_steps.append(
            "Score weight follow-up reason: "
            + str(score_set.get("score_weight_set_follow_up_reason"))
        )


def back_forward_comparison_row_summaries(rows: object) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    keys = (
        "dataset",
        "trades",
        "min_closed",
        "meets_min_closed",
        "pf",
        "avg_r",
        "expectancy_r",
        "max_drawdown_r",
        "net_profit",
        "trades_delta_vs_backtest",
        "pf_delta_vs_backtest",
        "avg_r_delta_vs_backtest",
        "expectancy_r_delta_vs_backtest",
        "max_drawdown_r_delta_vs_backtest",
        "net_profit_delta_vs_backtest",
    )
    summaries: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        summaries.append({key: row.get(key, "") for key in keys if key in row})
    return summaries


def back_forward_comparison_row_by_dataset(back_forward: dict[str, Any], dataset: str) -> dict[str, Any]:
    rows = back_forward.get("performance_comparison_rows")
    if not isinstance(rows, list):
        return {}
    return next(
        (
            row
            for row in rows
            if isinstance(row, dict) and str(row.get("dataset") or "") == dataset
        ),
        {},
    )


def back_forward_row_parts(row: dict[str, Any], *, include_deltas: bool = False) -> list[str]:
    parts = [
        score_weight_part(row, "trades", "trades"),
        score_weight_part(row, "meets_min_closed", "min_ok"),
        score_weight_part(row, "pf", "pf"),
        score_weight_part(row, "avg_r", "avg_r"),
        score_weight_part(row, "expectancy_r", "expectancy_r"),
        score_weight_part(row, "max_drawdown_r", "max_dd_r"),
        score_weight_part(row, "net_profit", "net_profit"),
    ]
    if include_deltas:
        parts.extend(
            [
                score_weight_part(row, "trades_delta_vs_backtest", "trades_delta"),
                score_weight_part(row, "pf_delta_vs_backtest", "pf_delta"),
                score_weight_part(row, "avg_r_delta_vs_backtest", "avg_r_delta"),
                score_weight_part(row, "net_profit_delta_vs_backtest", "net_profit_delta"),
            ]
        )
    return [part for part in parts if part]


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


def back_forward_extended_window_command(back_forward: dict[str, Any]) -> str:
    conditions = (
        back_forward.get("execution_conditions")
        if isinstance(back_forward.get("execution_conditions"), dict)
        else {}
    )
    mode = str(back_forward.get("mode") or "both")
    run_id_prefix = str(back_forward.get("run_id_prefix") or "mt5_back_forward")
    from_date, to_date, _, _ = back_forward_extended_window_dates(conditions)
    command = [
        "python3",
        "methods/swing_eval/analysis/mt5_back_forward_run.py",
        "--mode",
        mode,
        "--execute",
        "--refresh-ready-status",
        "--run-id-prefix",
        f"{run_id_prefix}_extended_window",
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


def append_back_forward_performance_steps(manual_steps: list[str], back_forward: dict[str, Any]) -> None:
    if back_forward.get("performance_comparison_available") is not True:
        return
    status = str(back_forward.get("performance_comparison_status") or "")
    thresholds = (
        back_forward.get("performance_comparison_thresholds")
        if isinstance(back_forward.get("performance_comparison_thresholds"), dict)
        else {}
    )
    min_closed = thresholds.get("min_closed", "")
    manual_steps.append(
        "Back/Forward comparison: "
        f"status={status}, min_closed={min_closed}, evidence_state={back_forward.get('evidence_state', '')}"
    )
    backtest_row = back_forward_comparison_row_by_dataset(back_forward, "backtest")
    if backtest_row:
        manual_steps.append("Back/Forward backtest: " + ", ".join(back_forward_row_parts(backtest_row)))
    forward_row = back_forward_comparison_row_by_dataset(back_forward, "forward")
    if forward_row:
        manual_steps.append(
            "Back/Forward forward: "
            + ", ".join(back_forward_row_parts(forward_row, include_deltas=True))
        )
    if status in BACK_FORWARD_SAMPLE_SHORTAGE_STATES:
        conditions = (
            back_forward.get("execution_conditions")
            if isinstance(back_forward.get("execution_conditions"), dict)
            else {}
        )
        from_date, to_date, current_days, range_strategy = back_forward_extended_window_dates(conditions)
        current_from = str(conditions.get("from_date") or "")
        current_to = str(conditions.get("to_date") or "")
        manual_steps.append(
            "Back/Forward sample shortage: "
            f"status={status}, min_closed={min_closed}, "
            f"backtest_trades={backtest_row.get('trades', '')}, "
            f"forward_trades={forward_row.get('trades', '')}"
        )
        manual_steps.append(
            "Back/Forward sample shortage recovery: "
            f"range_strategy={range_strategy}, current={current_from}..{current_to}, "
            f"current_days={'' if current_days is None else current_days}, "
            f"suggested={from_date}..{to_date}"
        )
    elif status in {"forward_degraded_vs_backtest", "forward_below_break_even"}:
        manual_steps.append(
            "Back/Forward promotion decision: reject current candidate until refit or revalidation improves forward drift."
        )


def append_strategy_back_forward_decision_steps(
    manual_steps: list[str],
    strategy_analysis: dict[str, Any],
) -> None:
    status = str(strategy_analysis.get("strategy_tester_analysis_back_forward_decision_status") or "")
    if not status:
        return
    parts = [f"status={status}"]
    for key, label in (
        ("strategy_tester_analysis_back_forward_decision_adoptable", "adoptable"),
        ("strategy_tester_analysis_back_forward_decision_next_action", "next_action"),
        ("strategy_tester_analysis_back_forward_evidence_state", "evidence_state"),
        ("strategy_tester_analysis_back_forward_performance_status", "performance_status"),
        ("strategy_tester_analysis_manual_collect_ready", "collect_ready"),
        ("strategy_tester_analysis_manual_collect_status", "collect_status"),
    ):
        value = strategy_analysis.get(key)
        if value not in (None, ""):
            parts.append(f"{label}={value}")
    manual_steps.append("Strategy analysis Back/Forward decision: " + ", ".join(parts))
    reason = str(strategy_analysis.get("strategy_tester_analysis_back_forward_decision_reason") or "")
    if reason:
        manual_steps.append("Strategy analysis Back/Forward reason: " + reason)
    thresholds = strategy_analysis.get("strategy_tester_analysis_back_forward_decision_thresholds")
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
            manual_steps.append("Strategy analysis Back/Forward thresholds: " + ", ".join(threshold_parts))
    metric_parts = []
    for key, label in (
        ("strategy_tester_analysis_back_forward_decision_backtest_trades", "backtest_trades"),
        ("strategy_tester_analysis_back_forward_decision_forward_trades", "forward_trades"),
        ("strategy_tester_analysis_back_forward_decision_forward_pf", "forward_pf"),
        ("strategy_tester_analysis_back_forward_decision_forward_avg_r", "forward_avg_r"),
        (
            "strategy_tester_analysis_back_forward_decision_forward_pf_delta_vs_backtest",
            "forward_pf_delta",
        ),
        (
            "strategy_tester_analysis_back_forward_decision_forward_avg_r_delta_vs_backtest",
            "forward_avg_r_delta",
        ),
    ):
        value = strategy_analysis.get(key)
        if value not in (None, ""):
            metric_parts.append(f"{label}={value}")
    if metric_parts:
        manual_steps.append("Strategy analysis Back/Forward metrics: " + ", ".join(metric_parts))


def bridge_activity_manual_steps(bridge: dict[str, Any]) -> list[str]:
    status = str(bridge.get("bridge_log_activity_status") or "")
    steps: list[str] = []
    if status:
        steps.append(f"Bridge log activity status: {status}")
    if bridge.get("mt5_terminal_running") is not None:
        steps.append(
            "MT5 terminal running: "
            f"{bridge.get('mt5_terminal_running')} "
            f"match_count={bridge.get('mt5_terminal_match_count', '')}"
        )
    if bridge.get("ea_attention_reason"):
        steps.append(f"EA attention reason: {bridge.get('ea_attention_reason')}")
    liveness_signal = str(
        bridge.get("ea_liveness_signal")
        or bridge.get("bridge_log_ea_liveness_signal")
        or ""
    )
    if liveness_signal:
        steps.append(f"EA liveness signal: {liveness_signal}")
    if bridge.get("config_get_recent_but_ea_post_stale") not in (None, ""):
        steps.append(
            "Config GET recent but EA POST stale: "
            f"{bridge.get('config_get_recent_but_ea_post_stale')}"
        )
    elif bridge.get("bridge_log_config_get_recent_but_ea_post_stale") not in (None, ""):
        steps.append(
            "Config GET recent but EA POST stale: "
            f"{bridge.get('bridge_log_config_get_recent_but_ea_post_stale')}"
        )
    last_ea_post = str(bridge.get("bridge_log_last_ea_post_at") or "")
    ea_post_age = bridge.get("bridge_log_last_ea_post_age_seconds")
    if last_ea_post:
        steps.append(f"Last EA POST: {last_ea_post} age_seconds={ea_post_age}")
    last_snapshot_post = str(bridge.get("bridge_log_last_snapshot_post_at") or "")
    snapshot_post_age = bridge.get("bridge_log_last_snapshot_post_age_seconds")
    if last_snapshot_post and last_snapshot_post != last_ea_post:
        steps.append(f"Last snapshot POST: {last_snapshot_post} age_seconds={snapshot_post_age}")
    last_config_get = str(bridge.get("bridge_log_last_config_get_at") or "")
    config_get_age = bridge.get("bridge_log_last_config_get_age_seconds")
    if last_config_get:
        steps.append(
            f"Last config GET: {last_config_get} age_seconds={config_get_age}. "
            "GET /config may be produced by status checks; use EA POST freshness for EA liveness."
        )
    return steps


def append_manual_collect_readiness_steps(manual_steps: list[str], source: dict[str, Any], *, label: str = "Manual collect") -> None:
    collect_parts: list[str] = []
    for key, display in (
        ("manual_collect_ready", "ready"),
        ("manual_collect_status", "status"),
        ("manual_collect_csv_count", "csv"),
        ("manual_collect_modified_after", "modified_after"),
    ):
        value = source.get(key)
        if value not in (None, ""):
            collect_parts.append(f"{display}={value}")
    if collect_parts:
        manual_steps.append(f"{label} readiness: " + ", ".join(collect_parts))
    if source.get("manual_collect_reason"):
        manual_steps.append(f"{label} reason: " + str(source.get("manual_collect_reason")))
    blocking_reasons = source.get("manual_collect_blocking_reasons")
    if isinstance(blocking_reasons, list) and blocking_reasons:
        manual_steps.append(f"{label} blocking reasons: " + "; ".join(str(reason) for reason in blocking_reasons))
    if source.get("manual_collect_next_action"):
        manual_steps.append(f"{label} next action: " + str(source.get("manual_collect_next_action")))


def append_bridge_recovery_steps(manual_steps: list[str], bridge_recovery: dict[str, Any]) -> None:
    if not isinstance(bridge_recovery, dict):
        return
    bridge_recovery_status = str(bridge_recovery.get("status") or "")
    if bridge_recovery_status:
        manual_steps.append(f"Bridge recovery status: {bridge_recovery_status}")
    bridge_recovery_blocking_reasons = (
        bridge_recovery.get("blocking_reasons")
        if isinstance(bridge_recovery.get("blocking_reasons"), list)
        else []
    )
    if bridge_recovery_blocking_reasons:
        manual_steps.append(
            "Bridge recovery blocking reasons: "
            + "; ".join(str(reason) for reason in bridge_recovery_blocking_reasons)
        )
    if bridge_recovery.get("next_action"):
        manual_steps.append("Bridge recovery next action: " + str(bridge_recovery.get("next_action")))
    bridge_operator_action = str(bridge_recovery.get("bridge_operator_summary_next_operation_action") or "")
    bridge_operator_area = str(bridge_recovery.get("bridge_operator_summary_next_operation_area") or "")
    bridge_operator_target = str(bridge_recovery.get("bridge_operator_summary_next_operation_target") or "")
    bridge_operator_step = str(bridge_recovery.get("bridge_operator_summary_next_operation_operator_step") or "")
    bridge_operator_verification = str(
        bridge_recovery.get("bridge_operator_summary_next_operation_verification") or ""
    )
    if bridge_operator_action or bridge_operator_step:
        manual_steps.append(
            "Bridge operator summary: "
            f"action={bridge_operator_action}, "
            f"area={bridge_operator_area}, "
            f"target={bridge_operator_target}, "
            f"step={bridge_operator_step}, "
            f"verification={bridge_operator_verification}"
        )
    bridge_operation_action = str(bridge_recovery.get("bridge_recovery_next_operation_action") or "")
    bridge_operation_purpose = str(bridge_recovery.get("bridge_recovery_next_operation_purpose") or "")
    bridge_operation_area = str(bridge_recovery.get("bridge_recovery_next_operation_area") or "")
    bridge_operation_target = str(bridge_recovery.get("bridge_recovery_next_operation_target") or "")
    bridge_operation_verification = str(
        bridge_recovery.get("bridge_recovery_next_operation_verification") or ""
    )
    if bridge_operation_action or bridge_operation_purpose:
        manual_steps.append(
            "Bridge recovery operation card: "
            f"action={bridge_operation_action}, "
            f"purpose={bridge_operation_purpose}, "
            f"area={bridge_operation_area}, "
            f"target={bridge_operation_target}, "
            f"verification={bridge_operation_verification}"
        )
    verification_commands = (
        bridge_recovery.get("bridge_operator_summary_next_operation_verification_commands")
        if isinstance(bridge_recovery.get("bridge_operator_summary_next_operation_verification_commands"), list)
        else bridge_recovery.get("bridge_recovery_next_operation_verification_commands")
        if isinstance(bridge_recovery.get("bridge_recovery_next_operation_verification_commands"), list)
        else []
    )
    if verification_commands:
        command_parts = []
        for command in verification_commands:
            if isinstance(command, dict):
                label = str(command.get("label") or "")
                command_text = str(command.get("command") or "")
                command_parts.append(f"{label}: {command_text}" if label else command_text)
        if command_parts:
            manual_steps.append("Bridge recovery verification commands: " + "; ".join(command_parts))


def bridge_recovery_blocks_mt5_validation(bridge_recovery: dict[str, Any]) -> bool:
    return bool(
        isinstance(bridge_recovery, dict)
        and bridge_recovery.get("exists") is True
        and bridge_recovery.get("ready_for_mt5_validation") is False
    )


def bridge_recovery_refresh_commands(label_suffix: str) -> list[dict[str, str]]:
    return [
        command_step(
            f"refresh_bridge_status_{label_suffix}",
            "python3 methods/swing_eval/analysis/bridge_status.py --output-json runtime/latest_bridge_status.json "
            "--output-md runtime/latest_bridge_status.md",
        ),
        command_step(
            f"refresh_bridge_recovery_plan_{label_suffix}",
            "python3 methods/swing_eval/analysis/bridge_recovery_plan.py --bridge-status runtime/latest_bridge_status.json "
            "--history-status runtime/latest_history_status.json "
            "--output-json runtime/latest_bridge_recovery_plan.json "
            "--output-md runtime/latest_bridge_recovery_plan.md",
        ),
    ]


def append_bridge_standalone_tester_note(manual_steps: list[str], bridge_recovery: dict[str, Any]) -> None:
    manual_steps.append(
        "Bridge Recovery is not ready, but standalone Swing_Evaluation_Trader Strategy Tester runs are allowed."
    )
    append_bridge_recovery_steps(manual_steps, bridge_recovery)


def append_back_forward_manual_readiness(manual_steps: list[str], back_forward: dict[str, Any]) -> None:
    if back_forward.get("exists") is not True:
        return
    pack = (
        back_forward.get("mt5_strategy_tester_pack")
        if isinstance(back_forward.get("mt5_strategy_tester_pack"), dict)
        else {}
    )
    pack_status = str(back_forward.get("mt5_strategy_tester_pack_status") or pack.get("status") or "")
    pack_next_action = str(
        back_forward.get("mt5_strategy_tester_pack_next_action") or pack.get("next_action") or ""
    )
    pack_start_after = str(
        back_forward.get("mt5_strategy_tester_pack_manual_run_start_after")
        or pack.get("manual_run_start_after")
        or ""
    )
    pack_step_count = back_forward.get(
        "mt5_strategy_tester_pack_step_count",
        pack.get("step_count", ""),
    )
    if pack_status or pack_next_action or pack_start_after or pack_step_count not in ("", None):
        parts: list[str] = []
        if pack_status:
            parts.append(f"status={pack_status}")
        if pack_next_action:
            parts.append(f"next_action={pack_next_action}")
        if pack_start_after:
            parts.append(f"start_after={pack_start_after}")
        if pack_step_count not in ("", None):
            parts.append(f"steps={pack_step_count}")
        manual_steps.append("Back/Forward MT5 Quick Start: " + ", ".join(parts))
    pack_collect_command = str(
        back_forward.get("mt5_strategy_tester_pack_collect_command_text")
        or pack.get("collect_command_text")
        or ""
    )
    if pack_collect_command:
        manual_steps.append("Back/Forward MT5 Quick Start collect command: " + pack_collect_command)
    pack_collect_reason = str(
        back_forward.get("mt5_strategy_tester_pack_collect_reason")
        or pack.get("collect_reason")
        or ""
    )
    if pack_collect_reason:
        manual_steps.append("Back/Forward MT5 Quick Start collect reason: " + pack_collect_reason)
    pack_steps = (
        back_forward.get("mt5_strategy_tester_pack_steps")
        if isinstance(back_forward.get("mt5_strategy_tester_pack_steps"), list)
        else pack.get("steps")
        if isinstance(pack.get("steps"), list)
        else []
    )
    for row in pack_steps:
        if not isinstance(row, dict):
            continue
        fingerprint = str(row.get("step_fingerprint") or "")
        if not fingerprint:
            continue
        order = row.get("order", "")
        purpose = row.get("purpose", "")
        step_label = row.get("step") or row.get("label", "")
        manual_steps.append(
            "Back/Forward MT5 Quick Start step: "
            f"{order} {purpose}/{step_label}, "
            f"fingerprint={fingerprint}, "
            f"report={row.get('report', '')}, "
            f"expected={row.get('expected_report', '')}"
        )
        input_parts: list[str] = []
        dates = str(row.get("dates") or "")
        if not dates and (row.get("from_date") or row.get("to_date")):
            dates = f"{row.get('from_date', '')} -> {row.get('to_date', '')}"
        for value, label in (
            (row.get("expert") or "", "Expert"),
            (row.get("symbol") or "", "Symbol"),
            (row.get("period") or "", "Period"),
            (row.get("model_label") or row.get("model") or "", "Model"),
            (dates, "Dates"),
            (row.get("forward") or row.get("forward_label") or "", "Forward"),
            (
                row.get("optimization_label")
                or row.get("optimization")
                or "",
                "Optimization",
            ),
            (row.get("run_type") or "", "Run type"),
            (row.get("config") or "", "Config"),
            (row.get("inputs") or row.get("expert_parameters") or "", "Inputs"),
            (row.get("run_json") or "", "RunJSON"),
            (row.get("report_json") or "", "ReportJSON"),
        ):
            if value not in ("", None):
                input_parts.append(f"{label}={value}")
        if input_parts:
            manual_steps.append(
                "Back/Forward MT5 Quick Start step inputs: "
                f"{order} {purpose}/{step_label}, "
                + ", ".join(str(part) for part in input_parts)
            )
        expected_artifacts = (
            row.get("expected_artifacts")
            if isinstance(row.get("expected_artifacts"), dict)
            else {}
        )
        if expected_artifacts or row.get("manual_run_start_after"):
            collect_filter = operator_collect_filter_summary(
                {
                    **row,
                    "expected_report_artifact": (
                        row.get("expected_report_artifact")
                        or row.get("expected_report")
                        or ""
                    ),
                }
            )
            if collect_filter:
                manual_steps.append(
                    "Back/Forward MT5 Quick Start collect filter: "
                    f"{order} {purpose}/{step_label}, "
                    + collect_filter
                )
    prerequisites_ready = back_forward.get("manual_prerequisites_ready")
    prerequisite_reasons = (
        back_forward.get("manual_prerequisites_reasons")
        if isinstance(back_forward.get("manual_prerequisites_reasons"), list)
        else []
    )
    compile_status_path = str(back_forward.get("manual_prerequisites_compile_status_path") or "")
    prerequisites_generated_at = str(back_forward.get("manual_prerequisites_generated_at") or "")
    if prerequisites_ready not in ("", None) or prerequisite_reasons or compile_status_path:
        parts = [f"ready={prerequisites_ready}"]
        if compile_status_path:
            parts.append(f"compile_status={compile_status_path}")
        if prerequisites_generated_at:
            parts.append(f"generated_at={prerequisites_generated_at}")
        manual_steps.append("Back/Forward manual prerequisites: " + ", ".join(parts))
    if prerequisite_reasons:
        manual_steps.append(
            "Back/Forward manual prerequisite reasons: "
            + "; ".join(str(reason) for reason in prerequisite_reasons)
        )

    validation_ready = back_forward.get("back_forward_plan_validation_ready")
    validation_status = str(back_forward.get("back_forward_plan_validation_status") or "")
    validation_reasons = (
        back_forward.get("back_forward_plan_validation_reasons")
        if isinstance(back_forward.get("back_forward_plan_validation_reasons"), list)
        else []
    )
    if validation_ready not in ("", None) or validation_status or validation_reasons:
        parts = [f"ready={validation_ready}"]
        if validation_status:
            parts.append(f"status={validation_status}")
        manual_steps.append("Back/Forward plan validation: " + ", ".join(parts))
    if validation_reasons:
        manual_steps.append(
            "Back/Forward plan validation reasons: "
            + "; ".join(str(reason) for reason in validation_reasons)
        )


def append_source_time_optimization_queue_steps(
    manual_steps: list[str],
    *,
    queue: dict[str, Any],
    launch: dict[str, Any],
    collect: dict[str, Any],
) -> None:
    if queue.get("exists") is True:
        waiting_entries = queue.get("manual_queue_operator_handoff_waiting_entry_ids")
        manual_steps.append(
            "Optimization source-time queue: "
            f"path={queue.get('path', '')}, "
            f"status={queue.get('status', '')}, "
            f"next_action={queue.get('next_action', '')}, "
            f"entries={queue.get('entry_count', '')}, "
            f"steps={queue.get('step_count', '')}, "
            f"waiting={queue.get('waiting_count', '')}, "
            f"ready={queue.get('ready_to_collect_count', '')}, "
            f"waiting_entries={compact_status_value(waiting_entries or [])}"
        )
        queue_progress = str(queue.get("manual_queue_progress_state") or "")
        if queue_progress or any(
            queue.get(key) not in ("", None)
            for key in (
                "manual_queue_step_report_ready_count",
                "manual_queue_step_collect_ready_count",
                "manual_queue_step_waiting_report_count",
                "manual_queue_step_launch_needed_count",
            )
        ):
            manual_steps.append(
                "Optimization source-time queue progress: "
                f"progress={queue_progress}, "
                f"report_ready={queue.get('manual_queue_step_report_ready_count', '')}, "
                f"collect_ready={queue.get('manual_queue_step_collect_ready_count', '')}, "
                f"waiting_report={queue.get('manual_queue_step_waiting_report_count', '')}, "
                f"launch_needed={queue.get('manual_queue_step_launch_needed_count', '')}"
            )
        if any(
            queue.get(key)
            for key in (
                "manual_queue_step_report_ready_ids",
                "manual_queue_step_collect_ready_ids",
                "manual_queue_step_waiting_report_ids",
                "manual_queue_step_launch_needed_ids",
            )
        ):
            manual_steps.append(
                "Optimization source-time queue step IDs: "
                f"report_ready={compact_status_value(queue.get('manual_queue_step_report_ready_ids', []))}, "
                f"collect_ready={compact_status_value(queue.get('manual_queue_step_collect_ready_ids', []))}, "
                "waiting_report="
                f"{compact_status_value(queue.get('manual_queue_step_waiting_report_ids', []))}, "
                "launch_needed="
                f"{compact_status_value(queue.get('manual_queue_step_launch_needed_ids', []))}"
            )
    next_queue = str(
        queue.get("manual_queue_operator_handoff_next_queue_id")
        or launch.get("queue_operator_handoff_next_queue_id")
        or ""
    )
    next_step = str(
        queue.get("manual_queue_operator_handoff_next_step_label")
        or launch.get("queue_operator_handoff_next_step_label")
        or ""
    )
    if next_queue or next_step:
        manual_steps.append(
            "Optimization source-time queue next MT5 step: "
            f"{next_queue}/{next_step}, "
            f"Symbol={queue.get('manual_queue_operator_handoff_next_symbol') or launch.get('queue_operator_handoff_next_symbol', '')}, "
            f"Period={queue.get('manual_queue_operator_handoff_next_period') or launch.get('queue_operator_handoff_next_period', '')}, "
            f"Forward={queue.get('manual_queue_operator_handoff_next_forward') or launch.get('queue_operator_handoff_next_forward', '')}, "
            "Optimization="
            f"{queue.get('manual_queue_operator_handoff_next_optimization_label') or ''}, "
            f"Run type={queue.get('manual_queue_operator_handoff_next_run_type') or ''}, "
            f"Inputs={queue.get('manual_queue_operator_handoff_next_inputs') or launch.get('queue_operator_handoff_next_inputs', '')}, "
            f"Report={queue.get('manual_queue_operator_handoff_next_report') or launch.get('queue_operator_handoff_next_report', '')}"
        )
    next_step_summary = str(
        queue.get("manual_queue_operator_handoff_next_step_operator_summary")
        or launch.get("queue_operator_handoff_next_step_operator_summary")
        or ""
    )
    if next_step_summary:
        manual_steps.append("Optimization source-time next step summary: " + next_step_summary)
    collect_filter = str(
        queue.get("manual_queue_operator_handoff_next_step_collect_filter_summary")
        or launch.get("queue_operator_handoff_next_step_collect_filter_summary")
        or ""
    )
    if collect_filter:
        manual_steps.append("Optimization source-time collect filter: " + collect_filter)
    collect_full_command = str(
        queue.get("manual_queue_operator_handoff_execute_and_refresh_all_command_text")
        or launch.get("queue_operator_handoff_collect_execute_and_refresh_all_command_text")
        or ""
    )
    if collect_full_command:
        manual_steps.append("Optimization source-time collect + full analysis: " + collect_full_command)
    if launch.get("exists") is True:
        manual_steps.append(
            "Optimization source-time launch status: "
            f"status={launch.get('status', '')}, "
            f"next_action={launch.get('next_action', '')}, "
            f"selected={launch.get('selected_queue_id') or launch.get('queue_operator_handoff_next_queue_id', '')}/"
            f"{launch.get('selected_step_label') or launch.get('queue_operator_handoff_next_step_label', '')}, "
            f"kind={launch.get('launch_command_kind', '')}, "
            f"blocked={launch.get('blocked', '')}, "
            f"blockers={compact_status_value(launch.get('blocked_reasons') or launch.get('blocking_reasons') or [])}"
        )
    if collect.get("exists") is True:
        manual_steps.append(
            "Optimization source-time collect status: "
            f"status={collect.get('status', '')}, "
            f"next_action={collect.get('next_action', '')}, "
            f"selected={collect.get('selected_count', '')}, "
            f"ready={collect.get('ready_entry_count', '')}, "
            f"waiting={collect.get('waiting_count', '')}, "
            f"invalid={collect.get('invalid_count', '')}, "
            f"queue_steps={collect.get('queue_step_count', '')}, "
            f"step_waiting={collect.get('queue_step_waiting_report_count', '')}, "
            f"step_launch_needed={collect.get('queue_step_launch_needed_count', '')}"
        )


def mt5_strategy_source_time_refresh_reasons(reasons: list[str]) -> list[str]:
    return [
        reason
        for reason in reasons
        if reason.startswith("mt5_strategy_candidate_source_time_missing:")
        or reason.startswith("mt5_strategy_candidate_source_time_mismatch:")
        or reason.startswith("mt5_strategy_candidate_source_time_files_stale:")
        or reason.startswith("mt5_strategy_candidate_source_time_files_missing:")
    ]


def mt5_strategy_buy_candidate_gap_reasons(reasons: list[str]) -> list[str]:
    return [
        reason
        for reason in reasons
        if reason.startswith("mt5_strategy_buy_candidate_gap:")
    ]


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


def mt5_strategy_source_time_candidate_labels(reasons: list[str]) -> list[str]:
    labels: list[str] = []
    for prefix in (
        "mt5_strategy_candidate_source_time_missing",
        "mt5_strategy_candidate_source_time_mismatch",
        "mt5_strategy_candidate_source_time_files_stale",
        "mt5_strategy_candidate_source_time_files_missing",
    ):
        labels.extend(reason_values(reasons, prefix))
    return unique_texts(labels)


def mt5_strategy_source_time_static_configs(reasons: list[str]) -> list[str]:
    configs: list[str] = []
    for label in mt5_strategy_source_time_candidate_labels(reasons):
        config = MT5_STRATEGY_TESTER_LABEL_CONFIGS.get(label)
        if (
            config
            and label not in MT5_STRATEGY_TESTER_STATIC_CANDIDATE_LABELS
            and config not in DEFAULT_MT5_OPTIMIZATION_STATIC_CONFIGS
        ):
            configs.append(config)
    return unique_texts(configs)


def include_static_config_args(configs: list[str]) -> str:
    if not configs:
        return ""
    return "".join(f" --include-static-config {shlex.quote(config)}" for config in configs)


def mt5_strategy_source_time_static_candidate_labels(reasons: list[str]) -> list[str]:
    labels = [
        label
        for label in mt5_strategy_source_time_candidate_labels(reasons)
        if label in MT5_STRATEGY_TESTER_STATIC_CANDIDATE_LABELS
    ]
    return unique_texts(labels)


def mt5_strategy_buy_gap_static_candidate_labels(
    strategy_analysis: dict[str, Any],
) -> list[str]:
    if not strategy_analysis.get("exists"):
        return []
    status = str(strategy_analysis.get("strategy_tester_analysis_buy_candidate_gap_status") or "")
    labels = strategy_analysis.get("strategy_tester_analysis_buy_candidate_gap_diagnostic_labels")
    if status != "needs_buy_diagnostic" or not isinstance(labels, list):
        return []
    return unique_texts(
        [
            str(label)
            for label in labels
            if str(label) in MT5_STRATEGY_TESTER_STATIC_CANDIDATE_LABELS
        ]
    )


def include_static_candidate_label_args(labels: list[str]) -> str:
    if not labels:
        return ""
    return "".join(
        f" --include-static-candidate-label {shlex.quote(label)}" for label in labels
    )


def build_spec_next_actions(
    *,
    workspace: Path,
    artifacts: list[dict[str, Any]],
    reasons: list[str],
    history_request: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    history_request = history_request if isinstance(history_request, dict) else {}
    bridge = artifact_by_name(artifacts, "bridge_status")
    bridge_recovery = artifact_by_name(artifacts, "bridge_recovery_plan")
    mt5_validation_blocked_by_bridge = bridge_recovery_blocks_mt5_validation(bridge_recovery)
    gate = artifact_by_name(artifacts, "promotion_gate")
    stale_artifacts = set(reason_values(reasons, "stale_runtime_artifacts"))
    missing_artifact_paths = set(reason_values(reasons, "missing_runtime_artifacts"))
    history_stale_or_missing = bool(
        {"history", "history_status"} & stale_artifacts
        or any("latest_history" in path or "latest_history_status" in path for path in missing_artifact_paths)
        or reason_present(reasons, "history_data_stale")
    )
    manual_test_queue_stale_or_missing = bool(
        "mt5_manual_test_queue" in stale_artifacts
        or any("latest_mt5_manual_test_queue" in path for path in missing_artifact_paths)
    )
    manual_collect_stale_or_missing = bool(
        "mt5_manual_collect_run" in stale_artifacts
        or any("latest_mt5_manual_collect_run" in path for path in missing_artifact_paths)
    )
    winrate_fit_stale_or_missing = bool(
        "winrate_fit" in stale_artifacts
        or "runtime/latest_winrate_fit.json" in missing_artifact_paths
    )
    risk_shape_stale_or_missing = bool(
        "risk_shape_weight_search" in stale_artifacts
        or "runtime/latest_risk_shape_weight_search.json" in missing_artifact_paths
    )
    next_action_runner_artifact_names = {"mt5_next_action_run", "mt5_next_action_run_buy"}
    next_action_runner_artifact_paths = {
        "runtime/latest_mt5_next_action_run.json",
        "runtime/latest_mt5_next_action_run_buy.json",
    }
    next_action_runner_stale_names = sorted(stale_artifacts & next_action_runner_artifact_names)
    next_action_runner_missing_paths = sorted(missing_artifact_paths & next_action_runner_artifact_paths)
    next_action_runner_not_current_reasons = [
        reason
        for reason in reasons
        if reason.startswith("mt5_next_action_runner_artifact_not_current:")
    ]
    next_action_runner_not_current_names = sorted(
        {
            reason.split(":", 2)[1]
            for reason in next_action_runner_not_current_reasons
            if len(reason.split(":", 2)) >= 3
        }
    )
    manual_queue_artifact = artifact_by_name(artifacts, "mt5_manual_test_queue")
    source_time_static_configs = mt5_strategy_source_time_static_configs(reasons)
    source_time_static_config_args = include_static_config_args(source_time_static_configs)
    strategy_analysis_artifact = artifact_by_name(artifacts, "mt5_strategy_tester_analysis")
    source_time_static_candidate_labels = unique_texts(
        mt5_strategy_source_time_static_candidate_labels(reasons)
        + mt5_strategy_buy_gap_static_candidate_labels(strategy_analysis_artifact)
    )
    source_time_static_candidate_label_args = include_static_candidate_label_args(
        source_time_static_candidate_labels
    )
    refresh_manual_test_queue_with_optimization_command = (
        "python3 methods/swing_eval/analysis/mt5_manual_test_queue.py "
        "--include-optimization-configs"
        f"{source_time_static_config_args}"
        f"{source_time_static_candidate_label_args} "
        f"--output-json {DEFAULT_MT5_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
        "--output-md runtime/latest_mt5_manual_test_queue_with_optimization.md"
    )
    refresh_manual_operator_packet_with_optimization_command = (
        "python3 methods/swing_eval/analysis/mt5_manual_operator_packet.py "
        f"--queue {DEFAULT_MT5_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
        f"--queue-launch-json {DEFAULT_MT5_MANUAL_QUEUE_LAUNCH_WITH_OPTIMIZATION} "
        f"--bridge-recovery-plan-json {DEFAULT_BRIDGE_RECOVERY_PLAN} "
        f"--strategy-analysis-json {DEFAULT_MT5_STRATEGY_TESTER_ANALYSIS} "
        f"--output-json {DEFAULT_MT5_MANUAL_OPERATOR_PACKET_WITH_OPTIMIZATION} "
        "--output-md runtime/latest_mt5_manual_operator_packet_with_optimization.md"
    )
    watch_manual_auto_collect_with_optimization_command = (
        "python3 methods/swing_eval/analysis/mt5_manual_auto_collect_watch.py "
        f"--queue {DEFAULT_MT5_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
        f"--collect-output-json {DEFAULT_MT5_MANUAL_COLLECT_WITH_OPTIMIZATION} "
        "--collect-output-md runtime/latest_mt5_manual_collect_with_optimization.md "
        f"--queue-launch-json {DEFAULT_MT5_MANUAL_QUEUE_LAUNCH_WITH_OPTIMIZATION} "
        "--queue-launch-md runtime/latest_mt5_manual_queue_launch_with_optimization.md "
        f"--operator-packet-json {DEFAULT_MT5_MANUAL_OPERATOR_PACKET_WITH_OPTIMIZATION} "
        "--operator-packet-md runtime/latest_mt5_manual_operator_packet_with_optimization.md "
        f"--bridge-recovery-plan-json {DEFAULT_BRIDGE_RECOVERY_PLAN} "
        f"--strategy-analysis-json {DEFAULT_MT5_STRATEGY_TESTER_ANALYSIS} "
        f"--output-json {DEFAULT_MT5_MANUAL_AUTO_COLLECT_WATCH} "
        "--output-md runtime/latest_mt5_manual_auto_collect_watch.md "
        "--max-runs 1"
    )
    execute_ready_manual_auto_collect_with_optimization_command = (
        watch_manual_auto_collect_with_optimization_command + " --execute-ready"
    )
    strategy_analysis_stale_dependencies = reason_values(
        reasons,
        "mt5_strategy_tester_analysis_stale_vs_dependencies",
    )
    if strategy_analysis_stale_dependencies:
        source_generated_at_by_label = (
            strategy_analysis_artifact.get(
                "strategy_tester_analysis_source_artifact_generated_at_by_label"
            )
            if isinstance(
                strategy_analysis_artifact.get(
                    "strategy_tester_analysis_source_artifact_generated_at_by_label"
                ),
                dict,
            )
            else {}
        )
        dependency_generated_at_by_label = {
            source_label: str(
                artifact_by_name(artifacts, artifact_name).get("generated_at") or ""
            )
            for source_label, artifact_name in STRATEGY_TESTER_ANALYSIS_STABLE_DEPENDENCIES
        }
        manual_steps = [
            "Refresh Strategy Tester Analysis before judging MT5 adoption; it was built from older source artifacts.",
            "Stale source labels: " + ", ".join(strategy_analysis_stale_dependencies),
        ]
        for label in strategy_analysis_stale_dependencies:
            manual_steps.append(
                "Source freshness: "
                f"{label} analysis={source_generated_at_by_label.get(label, '')} "
                f"current={dependency_generated_at_by_label.get(label, '')}"
            )
        add_next_action(
            actions,
            {
                "id": "refresh_mt5_strategy_tester_analysis",
                "priority": 28,
                "area": "mt5_strategy_tester_analysis",
                "summary": "Refresh MT5 Strategy Tester Analysis after source evidence changed.",
                "reasons": [
                    reason
                    for reason in reasons
                    if reason.startswith("mt5_strategy_tester_analysis_stale_vs_dependencies:")
                ],
                "commands": [
                    command_step(
                        "refresh_strategy_tester_analysis",
                        MT5_STRATEGY_TESTER_ANALYSIS_REFRESH_COMMAND_TEXT,
                    ),
                    command_step(
                        "refresh_spec_coverage_after_strategy_analysis",
                        "python3 methods/swing_eval/analysis/spec_coverage.py "
                        f"--output-json {DEFAULT_OUTPUT_JSON} "
                        f"--output-md {DEFAULT_OUTPUT_MD}",
                    ),
                ],
                "manual_steps": manual_steps,
            },
        )
    manual_queue_stale_runner = reason_present(reasons, "mt5_manual_test_queue_stale_runner_artifacts")
    manual_queue_stale_entries = (
        manual_queue_artifact.get("manual_queue_stale_entries")
        if isinstance(manual_queue_artifact.get("manual_queue_stale_entries"), list)
        else []
    )
    mql5_reasons = [
        reason
        for reason in reasons
        if reason.startswith("missing_mql5_artifacts:")
        or reason.startswith("mql5_artifact_test_reference_missing:")
        or reason.startswith("mql5_artifact_markers_missing:")
    ]
    if mql5_reasons:
        missing_paths = reason_values(reasons, "missing_mql5_artifacts")
        unreferenced_paths = reason_values(reasons, "mql5_artifact_test_reference_missing")
        marker_gaps = reason_values(reasons, "mql5_artifact_markers_missing")
        manual_steps: list[str] = []
        if missing_paths:
            manual_steps.append("Restore or create missing MQL5 artifacts: " + ", ".join(missing_paths))
        if unreferenced_paths:
            manual_steps.append("Add focused tests or test references for MQL5 artifacts: " + ", ".join(unreferenced_paths))
        if marker_gaps:
            manual_steps.append(
                "Fix MQL5 artifact marker gaps before MT5 execution: " + "; ".join(marker_gaps)
            )
        add_next_action(
            actions,
            {
                "id": "fix_mql5_artifact_coverage",
                "priority": 8,
                "area": "mql5_artifacts",
                "summary": "Fix missing or unsafe MQL5 files before running MT5 Strategy Tester.",
                "reasons": mql5_reasons,
                "commands": [
                    command_step(
                        "refresh_compile_status",
                        "python3 methods/swing_eval/analysis/mt5_compile_status.py --output-json runtime/latest_mt5_compile_status.json "
                        "--output-md runtime/latest_mt5_compile_status.md",
                    ),
                    command_step(
                        "rerun_spec_coverage",
                        "python3 methods/swing_eval/analysis/spec_coverage.py --output-json runtime/latest_spec_coverage.json "
                        "--output-md runtime/latest_spec_coverage.md",
                    ),
                ],
                "manual_steps": manual_steps,
            },
        )

    compile_reasons = [
        reason
        for reason in reasons
        if reason.startswith("mt5_compile_status_not_ready:")
        or reason.startswith("mt5_compile_status_stale_vs_mql5_artifacts:")
    ]
    if compile_reasons:
        stale_mql5_artifacts = reason_values(reasons, "mt5_compile_status_stale_vs_mql5_artifacts")
        not_ready_fields = reason_values(reasons, "mt5_compile_status_not_ready")
        manual_steps = [
            "Refresh MT5 compile status before Strategy Tester execution.",
            "Confirm Sources synced, Compiled fresh, Tester sets synced, Tester configs synced, and required ExpertParameters sets ready.",
        ]
        if not_ready_fields:
            manual_steps.append("Compile status failed fields: " + ", ".join(not_ready_fields))
        if stale_mql5_artifacts:
            manual_steps.append("MQL5 artifacts newer than compile status: " + ", ".join(stale_mql5_artifacts))
        add_next_action(
            actions,
            {
                "id": "refresh_mt5_compile_status",
                "priority": 18,
                "area": "mt5_compile",
                "summary": "Refresh MT5 compile/config/set readiness before launching Strategy Tester.",
                "reasons": compile_reasons,
                "commands": [
                    command_step(
                        "compile_and_refresh_status",
                        "python3 methods/swing_eval/analysis/mt5_compile.py --timeout-seconds 90 "
                        "--output-json runtime/latest_mt5_compile_run.json "
                        "--output-md runtime/latest_mt5_compile_run.md "
                        "--status-output-json runtime/latest_mt5_compile_status.json "
                        "--status-output-md runtime/latest_mt5_compile_status.md",
                    ),
                    command_step(
                        "refresh_compile_status",
                        "python3 methods/swing_eval/analysis/mt5_compile_status.py --output-json runtime/latest_mt5_compile_status.json "
                        "--output-md runtime/latest_mt5_compile_status.md",
                    ),
                ],
                "manual_steps": manual_steps,
            },
        )

    if history_stale_or_missing:
        commands: list[dict[str, str]] = []
        manual_steps = []
        request = history_request.get("request") if isinstance(history_request.get("request"), dict) else {}
        history_data_reasons = [
            reason for reason in reasons if reason.startswith("history_data_stale:")
        ]
        if history_data_reasons:
            manual_steps.append(
                "Existing 168h history has complete bars but its server_time/M1 last bar is stale; "
                "request fresh MT5 history before using it as promotion evidence."
            )
        if history_request.get("pending") is True:
            manual_steps.append(
                "A 168h history request is already pending; wait for the MT5 EA bridge to write "
                "runtime/latest_history_168h.json and runtime/history_request.done.json."
            )
            if request.get("id"):
                manual_steps.append(f"Pending request id: {request.get('id')}")
            if history_request.get("stale_pending") is True:
                manual_steps.append(
                    "The pending request is stale; check that the MT5 AI Bridge server is running and that the EA is attached to a live chart."
                )
                snapshot = (
                    history_request.get("bridge_snapshot")
                    if isinstance(history_request.get("bridge_snapshot"), dict)
                    else {}
                )
                if snapshot.get("fresh") is False:
                    manual_steps.append(
                        "latest_snapshot.json is stale, so the src/bridge/EA connection is probably not posting current snapshots."
                    )
                manual_steps.extend(bridge_activity_manual_steps(bridge))
                append_bridge_recovery_steps(manual_steps, artifact_by_name(artifacts, "bridge_recovery_plan"))
        elif (workspace / "src" / "bridge" / "request_history.py").exists():
            commands.append(command_step("request_history", "python3 src/bridge/request_history.py 168"))
        if history_request.get("stale_pending") is True:
            commands.append(command_step("inspect_bridge_log", "tail -200 runtime/bridge.log"))
            commands.append(command_step("inspect_bridge_process", "ps aux | rg '[m]t5_ai_bridge.py'"))
            commands.append(
                command_step(
                    "refresh_bridge_status_before_history",
                    "python3 methods/swing_eval/analysis/bridge_status.py --output-json runtime/latest_bridge_status.json "
                    "--output-md runtime/latest_bridge_status.md",
                )
            )
            commands.append(
                command_step(
                    "refresh_bridge_recovery_plan_before_history",
                    "python3 methods/swing_eval/analysis/bridge_recovery_plan.py --bridge-status runtime/latest_bridge_status.json "
                    "--history-status runtime/latest_history_status.json "
                    "--output-json runtime/latest_bridge_recovery_plan.json "
                    "--output-md runtime/latest_bridge_recovery_plan.md",
                )
            )
        commands.append(
            command_step(
                "after_ea_post_refresh_history_status"
                if history_request.get("pending") is True
                else "refresh_history_status",
                "python3 methods/swing_eval/analysis/history_status.py --history runtime/latest_history_168h.json "
                "--done runtime/history_request.done.json --output-json runtime/latest_history_status.json "
                "--output-md runtime/latest_history_status.md",
            )
        )
        add_next_action(
            actions,
            {
                "id": "refresh_history",
                "priority": 10,
                "area": "history",
                "summary": "Refresh 168h MT5 history and history_status before judging promotion evidence.",
                "reasons": history_refresh_reasons(reasons),
                "commands": commands,
                "manual_steps": manual_steps
                or ["Wait for the MT5 EA bridge to write runtime/latest_history_168h.json after the request command."],
                "history_request_state": history_request.get("state", ""),
            },
        )

    bridge_not_ready_reasons = [
        reason
        for reason in reasons
        if reason == "bridge_status_missing" or reason.startswith("bridge_status_not_ready:")
    ]
    bridge_activity_reasons = [
        reason
        for reason in reasons
        if reason.startswith("bridge_ea_post_activity:") or reason.startswith("bridge_snapshot_stale:")
    ]
    bridge_watch_activity_missing = "bridge_status_watch_missing_activity" in reasons
    if bridge_not_ready_reasons or bridge_activity_reasons or bridge_watch_activity_missing:
        bridge_status = str(bridge.get("operational_status") or "")
        manual_steps = []
        if bridge_status == "ea_not_posting":
            manual_steps.append(
                "Bridge HTTP is reachable but latest_snapshot is stale; attach or restart the MT5 EA on a live chart so it polls /config and posts snapshots/history chunks."
            )
            manual_steps.extend(bridge_activity_manual_steps(bridge))
        elif bridge_status == "bridge_unreachable":
            manual_steps.append("Start or restart python3 src/bridge/mt5_ai_bridge.py, then check /health and /config.")
        elif bridge_status == "bridge_process_not_found":
            manual_steps.append("Start python3 src/bridge/mt5_ai_bridge.py before waiting for EA history responses.")
        elif bridge_activity_reasons:
            manual_steps.append(
                "Bridge log shows stale or missing EA POST/snapshot activity; restore EA posting before refreshing history or MT5 evidence."
            )
            manual_steps.extend(bridge_activity_manual_steps(bridge))
        if bridge_watch_activity_missing:
            manual_steps.append(
                "Restart bridge_status_watch.py so heartbeat includes Bridge log EA POST activity fields."
            )
        append_bridge_recovery_steps(manual_steps, bridge_recovery)
        bridge_priority = 5 if bridge_not_ready_reasons or bridge_activity_reasons else 15
        commands = [
            command_step("inspect_bridge_log", "tail -200 runtime/bridge.log"),
            command_step("inspect_bridge_process", "ps aux | rg '[m]t5_ai_bridge.py'"),
            command_step(
                "refresh_bridge_status",
                "python3 methods/swing_eval/analysis/bridge_status.py --output-json runtime/latest_bridge_status.json "
                "--output-md runtime/latest_bridge_status.md",
            ),
            command_step(
                "bridge_recovery_plan",
                "python3 methods/swing_eval/analysis/bridge_recovery_plan.py --bridge-status runtime/latest_bridge_status.json "
                "--history-status runtime/latest_history_status.json "
                "--output-json runtime/latest_bridge_recovery_plan.json "
                "--output-md runtime/latest_bridge_recovery_plan.md",
            )
        ]
        if bridge_watch_activity_missing:
            commands.append(
                command_step(
                    "restart_bridge_status_watch",
                    "python3 methods/swing_eval/analysis/bridge_status_watch.py --interval-seconds 60 "
                    "--heartbeat runtime/bridge_status_watch_heartbeat.json "
                    "--pid-file runtime/bridge_status_watch.pid "
                    "--output-json runtime/latest_bridge_status.json "
                    "--output-md runtime/latest_bridge_status.md",
                )
            )
        add_next_action(
            actions,
            {
                "id": "refresh_bridge_status",
                "priority": bridge_priority,
                "area": "bridge",
                "summary": "Refresh MT5 AI Bridge health and restore EA snapshot/history posting.",
                "reasons": bridge_not_ready_reasons
                + bridge_activity_reasons
                + (["bridge_status_watch_missing_activity"] if bridge_watch_activity_missing else []),
                "commands": commands,
                "manual_steps": manual_steps,
            },
        )

    runtime_watchers_reasons = [
        reason
        for reason in reasons
        if reason.startswith("runtime_watchers_not_ready:")
        or reason.startswith("runtime_watchers_stale_heartbeats:")
        or reason.startswith("runtime_watchers_action_required:")
        or "runtime_watchers" in reason_values([reason], "stale_runtime_artifacts")
        or any("latest_runtime_watchers" in value for value in reason_values([reason], "missing_runtime_artifacts"))
    ]
    if runtime_watchers_reasons:
        runtime_watchers = artifact_by_name(artifacts, "runtime_watchers")
        manual_steps = [
            "Refresh runtime watcher summary before relying on long-running Bridge/MT5/forward monitors."
        ]
        stale_count = runtime_watchers.get("stale_watcher_count")
        if stale_count not in (None, ""):
            manual_steps.append(f"Stale watcher count: {stale_count}")
        action_required_count = runtime_watchers.get("action_required_watcher_count")
        if action_required_count not in (None, ""):
            manual_steps.append(f"Action required watcher count: {action_required_count}")
        if runtime_watchers.get("max_heartbeat_age_seconds") not in (None, ""):
            manual_steps.append(f"Max heartbeat age seconds: {runtime_watchers.get('max_heartbeat_age_seconds')}")
        stale_summaries = (
            runtime_watchers.get("runtime_watcher_stale_summaries")
            if isinstance(runtime_watchers.get("runtime_watcher_stale_summaries"), list)
            else runtime_watcher_row_summaries(runtime_watchers.get("stale_watchers"))
        )
        action_required_summaries = (
            runtime_watchers.get("runtime_watcher_action_required_summaries")
            if isinstance(runtime_watchers.get("runtime_watcher_action_required_summaries"), list)
            else runtime_watcher_row_summaries(runtime_watchers.get("action_required_watchers"))
        )
        affected_watchers: list[dict[str, Any]] = []
        seen_affected_watcher_names: set[str] = set()
        for watcher_summary in list(stale_summaries) + list(action_required_summaries):
            name = str(watcher_summary.get("name") or "")
            if name in seen_affected_watcher_names:
                continue
            seen_affected_watcher_names.add(name)
            affected_watchers.append(watcher_summary)
            detail_parts = [
                f"status={watcher_summary.get('status', '')}",
                f"heartbeat={watcher_summary.get('heartbeat_status', '')}",
                f"fresh={watcher_summary.get('heartbeat_fresh', '')}",
                f"age={watcher_summary.get('heartbeat_age_seconds', '')}",
                f"schema_ok={watcher_summary.get('schema_ok', '')}",
                f"missing_keys={watcher_summary.get('missing_required_field_count', '')}",
            ]
            if watcher_summary.get("mode_ok") not in (None, ""):
                detail_parts.append(f"mode_ok={watcher_summary.get('mode_ok', '')}")
            if watcher_summary.get("heartbeat_execute_ready") not in (None, ""):
                detail_parts.append(
                    f"heartbeat_execute_ready={watcher_summary.get('heartbeat_execute_ready', '')}"
                )
            if watcher_summary.get("mode_actual_execute_ready") not in (None, ""):
                detail_parts.append(
                    f"actual_execute_ready={watcher_summary.get('mode_actual_execute_ready', '')}"
                )
            if watcher_summary.get("mode_expected_execute_ready") not in (None, ""):
                detail_parts.append(
                    f"expected_execute_ready={watcher_summary.get('mode_expected_execute_ready', '')}"
                )
            mode_issues = (
                watcher_summary.get("mode_issues")
                if isinstance(watcher_summary.get("mode_issues"), list)
                else []
            )
            if mode_issues:
                detail_parts.append(
                    "mode_issues=" + ";".join(str(item) for item in mode_issues)
                )
            error = str(watcher_summary.get("error") or "")
            if error:
                detail_parts.append(f"error={error}")
            restart_command = str(watcher_summary.get("restart_command_text") or "")
            if restart_command:
                detail_parts.append(f"restart={restart_command}")
            tail_log_command = str(watcher_summary.get("tail_log_command_text") or "")
            if tail_log_command:
                detail_parts.append(f"log={tail_log_command}")
            manual_steps.append(
                "Runtime watcher detail: "
                + (name or "(unknown)")
                + " "
                + ", ".join(detail_parts)
            )
        manual_steps.append("If stale, missing, or action-required watcher state persists, rerun with --restart.")
        commands = [
            command_step(
                "refresh_runtime_watchers",
                "python3 methods/swing_eval/analysis/runtime_watchers.py --interval-seconds 60 "
                "--output-json runtime/latest_runtime_watchers.json "
                "--output-md runtime/latest_runtime_watchers.md",
            ),
            command_step(
                "restart_runtime_watchers_if_stale",
                "python3 methods/swing_eval/analysis/runtime_watchers.py --interval-seconds 60 --restart "
                "--output-json runtime/latest_runtime_watchers.json "
                "--output-md runtime/latest_runtime_watchers.md",
            ),
        ]
        for watcher_summary in affected_watchers:
            watcher_name = str(watcher_summary.get("name") or "watcher")
            label_suffix = re.sub(r"[^A-Za-z0-9_]+", "_", watcher_name).strip("_") or "watcher"
            restart_command = str(watcher_summary.get("restart_command_text") or "")
            if restart_command:
                commands.append(command_step(f"restart_{label_suffix}", restart_command))
            tail_log_command = str(watcher_summary.get("tail_log_command_text") or "")
            if tail_log_command:
                commands.append(command_step(f"tail_log_{label_suffix}", tail_log_command))
        add_next_action(
            actions,
            {
                "id": "refresh_runtime_watchers",
                "priority": 16,
                "area": "runtime_watchers",
                "summary": "Refresh runtime watcher summary and restart stale watcher processes if needed.",
                "reasons": runtime_watchers_reasons,
                "commands": commands,
                "manual_steps": manual_steps,
            },
        )

    if winrate_fit_stale_or_missing or risk_shape_stale_or_missing:
        winrate_fit = artifact_by_name(artifacts, "winrate_fit")
        risk_shape = artifact_by_name(artifacts, "risk_shape_weight_search")
        commands: list[dict[str, str]] = []
        manual_steps: list[str] = []
        if winrate_fit_stale_or_missing:
            if winrate_fit.get("exists") is True and winrate_fit.get("fresh") is False:
                manual_steps.append(
                    f"winrate_fit is stale: age_seconds={winrate_fit.get('age_seconds', '')}, "
                    f"rules={winrate_fit.get('winrate_rules', '')}"
                )
            else:
                manual_steps.append("winrate_fit artifact is missing; regenerate runtime/latest_winrate_fit.json.")
            commands.append(
                command_step(
                    "refresh_winrate_fit",
                    "python3 methods/swing_eval/analysis/winrate_fit.py --history runtime/latest_history_168h.json "
                    "--rr 4 --side buy --min-score 50 --validation-folds 3 --wf-folds 4 "
                    "--purge-records 1 --embargo-records 1 --embargo-minutes 60 "
                    "--min-test-count 5 --min-test-avg-r 0 --min-test-pf 1.0 "
                    "--calendar runtime/economic_calendar.json "
                    "--output reports/winrate_fit_168h_buy_rr4.xlsx "
                    "--output-json runtime/latest_winrate_fit.json",
                )
            )
        if risk_shape_stale_or_missing:
            if risk_shape.get("exists") is True and risk_shape.get("fresh") is False:
                manual_steps.append(
                    f"risk_shape_weight_search is stale: age_seconds={risk_shape.get('age_seconds', '')}, "
                    f"walk_forward={risk_shape.get('walk_forward_aggregate_status', '')}"
                )
            else:
                manual_steps.append(
                    "risk_shape_weight_search artifact is missing; regenerate DD/expectancy refit evidence."
                )
            commands.extend(
                [
                    command_step(
                        "refresh_risk_shape_backtest",
                        "python3 methods/swing_eval/analysis/backtest.py --history runtime/latest_history_168h.json "
                        "--rr 4 --side both --min-score 40 --max-hold-minutes 60 "
                        "--calendar runtime/economic_calendar.json "
                        "--calendar-input-utc-offset 9 --calendar-server-utc-offset 3 "
                        "--output reports/risk_shape_backtest_168h_min40.xlsx",
                    ),
                    command_step(
                        "refresh_risk_shape_weight_search",
                        "python3 methods/swing_eval/analysis/weight_search.py --history runtime/latest_history_168h.json "
                        "--rr 4 --side both --min-count 20 --max-hold-minutes 60 "
                        "--calendar runtime/economic_calendar.json "
                        "--calendar-input-utc-offset 9 --calendar-server-utc-offset 3 "
                        "--output reports/risk_shape_weight_search_168h_both_rr4.xlsx "
                        "--output-json runtime/latest_risk_shape_weight_search.json "
                        "--output-md runtime/latest_risk_shape_weight_search.md "
                        "--walk-forward --wf-folds 4 --wf-train-window 240 "
                        "--wf-test-window 60 --wf-embargo-records 5",
                    ),
                ]
            )
        if history_stale_or_missing:
            manual_steps.append(
                "History artifact is stale or pending; run this after refresh_history if current fit evidence is required."
            )
        commands.append(
            command_step(
                "refresh_promotion_gate_after_fit_artifacts",
                "python3 methods/swing_eval/analysis/promotion_gate.py --output-json runtime/latest_promotion_gate.json "
                "--output-md runtime/latest_promotion_gate.md",
            )
        )
        add_next_action(
            actions,
            {
                "id": "refresh_fit_quality_artifacts",
                "priority": 22,
                "area": "fit_artifacts",
                "summary": "Refresh stale or missing winrate/risk-shape fit evidence before promotion.",
                "reasons": fit_quality_refresh_reasons(reasons),
                "commands": commands,
                "manual_steps": manual_steps,
            },
        )

    status = artifact_by_name(artifacts, "mt5_tester_status")
    status_not_ready = reason_present(reasons, "mt5_tester_status_not_ready")
    status_watch_not_compatible = "mt5_status_watch_not_compatible" in reasons
    if status_not_ready or status_watch_not_compatible:
        operational_status = str(status.get("operational_status") or "")
        manual_steps: list[str] = []
        if operational_status == "blocked_running_terminal":
            handoff_path = str(status.get("mt5_operator_handoff_recommended_path") or "")
            handoff_queue = str(status.get("mt5_operator_handoff_next_queue_id") or "")
            handoff_step = str(status.get("mt5_operator_handoff_next_step_label") or "")
            if handoff_path == "manual_strategy_tester" and (handoff_queue or handoff_step):
                manual_steps.append(
                    "MT5 is already open; keep it open when using the manual Strategy Tester path."
                )
                manual_steps.append(
                    "Follow runtime/latest_mt5_tester_status.md MT5 Operator Handoff or "
                    "the run_mt5_manual_test_queue action before closing MT5."
                )
                manual_steps.append(
                    f"Manual Strategy Tester next step: {handoff_queue}/{handoff_step}"
                )
                manual_steps.append("Close the terminal only if you want /config auto launch instead.")
            else:
                manual_steps.append("Close the currently running MT5 terminal before /config auto launch.")
        if status_watch_not_compatible:
            manual_steps.append("Restart the status watcher if heartbeat compatibility remains false.")
        add_next_action(
            actions,
            {
                "id": "refresh_mt5_tester_status",
                "priority": 20,
                "area": "mt5_status",
                "summary": "Refresh MT5 tester readiness and clear terminal/watcher blockers before launching tests.",
                "reasons": [
                    reason
                    for reason in reasons
                    if reason.startswith("mt5_tester_status_not_ready:") or reason == "mt5_status_watch_not_compatible"
                ],
                "commands": [
                    command_step(
                        "refresh_status",
                        mt5_tester_status_refresh_command(),
                    )
                ],
                "manual_steps": manual_steps,
            },
        )

    if (
        next_action_runner_stale_names
        or next_action_runner_missing_paths
        or next_action_runner_not_current_names
        or manual_queue_stale_runner
    ):
        commands = []
        manual_steps = [
            "Regenerate stale or missing MT5 Next Action Runner artifacts before using Strategy Tester checklists.",
        ]
        for artifact_name in next_action_runner_not_current_names:
            artifact = artifact_by_name(artifacts, artifact_name)
            artifact_reason_text = "; ".join(
                reason.split(":", 2)[2]
                for reason in next_action_runner_not_current_reasons
                if len(reason.split(":", 2)) >= 3 and reason.split(":", 2)[1] == artifact_name
            )
            manual_steps.append(
                f"MT5 Next Action Runner artifact is stale: {artifact_name}, "
                f"target={artifact.get('target', '')}, focus={artifact.get('focus_side', '')}, "
                f"current={artifact.get('current_for_execution', '')}, "
                f"runner_generated={artifact.get('runner_generated_at', '')}, "
                f"gate_generated={artifact.get('promotion_generated_at', '')}, "
                f"current_gate={artifact.get('current_promotion_generated_at', '')}, "
                f"latest_gate={gate.get('generated_at', '')}, "
                f"reason={artifact_reason_text}"
            )
        if manual_queue_stale_runner:
            manual_steps.append(
                "Manual queue contains stale runner artifacts; refresh side runners before rerunning MT5 Strategy Tester."
            )
            for entry in manual_queue_stale_entries:
                if not isinstance(entry, dict):
                    continue
                stale_reasons = entry.get("stale_reasons") if isinstance(entry.get("stale_reasons"), list) else []
                stale_reason_text = "; ".join(str(reason) for reason in stale_reasons)
                command_text = str(entry.get("refresh_command_text") or "")
                manual_steps.append(
                    f"Stale {entry.get('id', '')}: current={entry.get('current_for_execution', '')}, "
                    f"gate_stale={entry.get('gate_stale_reason', '')}, "
                    f"runner_generated={entry.get('runner_generated_at', '')}, "
                    f"gate_generated={entry.get('promotion_generated_at', '')}, "
                    f"current_gate={entry.get('current_promotion_generated_at', '')}, "
                    f"reason={stale_reason_text}, refresh={command_text}"
                )
                if command_text:
                    command_label = "refresh_stale_" + str(entry.get("id") or "runner").replace(" ", "_")
                    commands.append(command_step(command_label, command_text))
        if "mt5_next_action_run" in next_action_runner_stale_names or (
            "runtime/latest_mt5_next_action_run.json" in next_action_runner_missing_paths
            or "mt5_next_action_run" in next_action_runner_not_current_names
        ):
            commands.append(
                command_step(
                    "refresh_next_action_runner",
                    "python3 methods/swing_eval/analysis/mt5_next_action_run.py "
                    "--output-json runtime/latest_mt5_next_action_run.json "
                    "--output-md runtime/latest_mt5_next_action_run.md",
                )
            )
            manual_steps.append("Refresh canonical runner: runtime/latest_mt5_next_action_run.json")
        if "mt5_next_action_run_buy" in next_action_runner_stale_names or (
            "runtime/latest_mt5_next_action_run_buy.json" in next_action_runner_missing_paths
            or "mt5_next_action_run_buy" in next_action_runner_not_current_names
        ):
            commands.append(
                command_step(
                    "refresh_buy_next_action_runner",
                    "python3 methods/swing_eval/analysis/mt5_next_action_run.py --target score_weight_sample_collection "
                    "--focus-side buy "
                    "--output-json runtime/latest_mt5_next_action_run_buy.json "
                    "--output-md runtime/latest_mt5_next_action_run_buy.md",
                )
            )
            manual_steps.append("Refresh BUY sample runner: runtime/latest_mt5_next_action_run_buy.json")
        if manual_queue_stale_runner and not any(
            str(command.get("label", "")).startswith("refresh_stale_")
            or command.get("label") in {"refresh_next_action_runner", "refresh_buy_next_action_runner"}
            for command in commands
        ):
            commands.append(
                command_step(
                    "refresh_next_action_runner",
                    "python3 methods/swing_eval/analysis/mt5_next_action_run.py "
                    "--output-json runtime/latest_mt5_next_action_run.json "
                    "--output-md runtime/latest_mt5_next_action_run.md",
                )
            )
            commands.append(
                command_step(
                    "refresh_buy_next_action_runner",
                    "python3 methods/swing_eval/analysis/mt5_next_action_run.py --target score_weight_sample_collection "
                    "--focus-side buy "
                    "--output-json runtime/latest_mt5_next_action_run_buy.json "
                    "--output-md runtime/latest_mt5_next_action_run_buy.md",
                )
            )
            manual_steps.append(
                "No side-specific stale refresh command was embedded; refresh canonical and BUY runners before rebuilding the queue."
            )
        manual_steps.append(
            "After refreshing runner artifacts, regenerate runtime/latest_mt5_manual_test_queue.json so the combined queue uses current collect-only timestamps."
        )
        commands.append(
            command_step(
                "refresh_manual_test_queue_after_runner_artifacts",
                "python3 methods/swing_eval/analysis/mt5_manual_test_queue.py "
                "--output-json runtime/latest_mt5_manual_test_queue.json "
                "--output-md runtime/latest_mt5_manual_test_queue.md",
            )
        )
        commands.append(
            command_step(
                "refresh_mt5_tester_status_after_runner_artifacts",
                mt5_tester_status_refresh_command(),
            )
        )
        add_next_action(
            actions,
            {
                "id": "refresh_mt5_next_action_runner_artifacts",
                "priority": 24,
                "area": "mt5_next_action",
                "summary": "Refresh missing or stale MT5 Next Action Runner artifacts before manual Strategy Tester use.",
                "reasons": [
                    reason
                    for reason in reasons
                    if next_action_runner_artifact_names & set(reason_values([reason], "stale_runtime_artifacts"))
                    or next_action_runner_artifact_paths & set(reason_values([reason], "missing_runtime_artifacts"))
                    or reason.startswith("mt5_next_action_runner_artifact_not_current:")
                ],
                "commands": commands,
                "manual_steps": manual_steps,
            },
        )

    if reason_present(reasons, "mt5_next_action_runner_not_current"):
        stale_reason = str(status.get("next_action_runner_gate_stale_reason") or "")
        manual_steps = ["Regenerate the MT5 Next Action Runner from the latest Promotion Gate before launching MT5."]
        if stale_reason:
            manual_steps.append(f"Gate stale reason: {stale_reason}")
        add_next_action(
            actions,
            {
                "id": "refresh_mt5_next_action_runner",
                "priority": 25,
                "area": "mt5_next_action",
                "summary": "Refresh the MT5 Next Action Runner so it matches the current Promotion Gate.",
                "reasons": [
                    reason for reason in reasons if reason.startswith("mt5_next_action_runner_not_current:")
                ],
                "commands": [
                    command_step(
                        "refresh_next_action_runner",
                        "python3 methods/swing_eval/analysis/mt5_next_action_run.py "
                        "--output-json runtime/latest_mt5_next_action_run.json "
                        "--output-md runtime/latest_mt5_next_action_run.md",
                    )
                ],
                "manual_steps": manual_steps,
            },
        )

    if reason_present(reasons, "mt5_next_action_runner_blocked_by_prior_actions"):
        blocking_count = optional_int(status.get("next_action_runner_blocking_prior_action_count"))
        manual_steps = ["Resolve higher-priority Promotion Gate actions before launching the MT5 Next Action Runner."]
        if (
            str(status.get("mt5_operator_handoff_recommended_path") or "") == "manual_strategy_tester"
            and str(status.get("mt5_operator_handoff_next_queue_id") or "")
        ):
            manual_steps.append(
                "This blocker applies to the selected MT5 Next Action Runner; "
                "the standalone manual Strategy Tester queue can still be run from run_mt5_manual_test_queue."
            )
        runner = status.get("next_action_runner") if isinstance(status.get("next_action_runner"), dict) else {}
        runner_fields = (
            ("target", "target"),
            ("focus", "focus_side"),
            ("config", "config"),
            ("set", "set"),
            ("manual_available", "manual_strategy_tester_available"),
            ("collect_ready", "manual_collect_ready"),
            ("collect_status", "manual_collect_status"),
            ("collect_next", "manual_collect_next_action"),
            ("collect_after", "manual_collect_modified_after"),
            ("run_start_after", "manual_run_start_after"),
        )
        runner_details = [
            f"{label}={runner.get(key)}"
            for label, key in runner_fields
            if runner.get(key) not in ("", None, [], {})
        ]
        if runner_details:
            manual_steps.append("Selected MT5 runner: " + ", ".join(runner_details))
        runner_execute_hint = str(runner.get("execute_command_text") or runner.get("command_text") or "")
        if runner_execute_hint:
            manual_steps.append("Selected MT5 runner execute hint: " + runner_execute_hint)
        runner_collect_hint = str(
            runner.get("manual_collect_only_command_text")
            or runner.get("collect_only_command_text")
            or ""
        )
        if runner_collect_hint:
            manual_steps.append("Selected MT5 runner collect hint: " + runner_collect_hint)
        if blocking_count is not None:
            manual_steps.append(f"Blocking prior action count: {blocking_count}")
        blocking_prior_actions = (
            status.get("next_action_runner_blocking_prior_actions")
            if isinstance(status.get("next_action_runner_blocking_prior_actions"), list)
            else []
        )
        prior_commands: list[dict[str, str]] = []
        for index, prior_action in enumerate(blocking_prior_actions[:5], start=1):
            if not isinstance(prior_action, dict):
                continue
            details = (
                f"P{prior_action.get('priority', '')} "
                f"{prior_action.get('area', '')}:{prior_action.get('action', '')}"
            )
            reason = str(prior_action.get("reason") or "")
            if reason:
                details += f" - {reason}"
            manual_steps.append("Blocking prior action: " + details)
            detail_fields = (
                ("priority", "priority"),
                ("area", "area"),
                ("action", "action"),
                ("kind", "execution_kind"),
                ("primary_class", "primary_execution_class"),
                ("allow_non_tester_primary", "runner_requires_allow_non_tester_primary"),
                ("runner_hint", "runner_execute_hint"),
            )
            detail_parts = [
                f"{label}={prior_action.get(key)}"
                for label, key in detail_fields
                if prior_action.get(key) not in ("", None, [], {})
            ]
            if detail_parts:
                manual_steps.append(f"Blocking prior detail {index}: " + ", ".join(detail_parts))
            command_text = str(prior_action.get("command_text") or "")
            if command_text:
                manual_steps.append("Blocking prior command: " + command_text)
                prior_commands.append(
                    command_step(f"run_blocking_prior_action_{len(prior_commands) + 1}", command_text)
                )
            runner_prior_hint = str(prior_action.get("runner_execute_hint") or "")
            if runner_prior_hint and runner_prior_hint != command_text:
                manual_steps.append(f"Blocking prior runner hint {index}: " + runner_prior_hint)
                prior_commands.append(
                    command_step(f"run_blocking_prior_runner_hint_{index}", runner_prior_hint)
                )
        add_next_action(
            actions,
            {
                "id": "resolve_mt5_next_action_prior_actions",
                "priority": 26,
                "area": "mt5_next_action",
                "summary": "Clear higher-priority Promotion Gate actions before running the current MT5 Next Action Runner.",
                "reasons": [
                    reason
                    for reason in reasons
                    if reason.startswith("mt5_next_action_runner_blocked_by_prior_actions:")
                ],
                "commands": prior_commands
                + [
                    command_step(
                        "refresh_promotion_gate",
                        "python3 methods/swing_eval/analysis/promotion_gate.py --output-json runtime/latest_promotion_gate.json "
                        "--output-md runtime/latest_promotion_gate.md",
                    ),
                    command_step(
                        "refresh_mt5_tester_status",
                        mt5_tester_status_refresh_command(),
                    ),
                ],
                "manual_steps": manual_steps,
            },
        )

    if manual_test_queue_stale_or_missing:
        add_next_action(
            actions,
            {
                "id": "refresh_mt5_manual_test_queue",
                "priority": 28,
                "area": "mt5_manual_queue",
                "summary": "Refresh the consolidated MT5 manual Strategy Tester queue.",
                "reasons": [
                    reason
                    for reason in reasons
                    if reason == "stale_runtime_artifacts:mt5_manual_test_queue"
                    or "latest_mt5_manual_test_queue" in reason
                ],
                "commands": [
                    command_step(
                        "refresh_manual_test_queue",
                        "python3 methods/swing_eval/analysis/mt5_manual_test_queue.py "
                        "--output-json runtime/latest_mt5_manual_test_queue.json "
                        "--output-md runtime/latest_mt5_manual_test_queue.md",
                    )
                ],
                "manual_steps": [
                    "Regenerate the MT5 manual queue before using MT5 Strategy Tester checklists.",
                    "This queue combines Back/Forward, SELL sample collection, and BUY sample collection steps.",
                ],
            },
        )

    manual_queue = artifact_by_name(artifacts, "mt5_manual_test_queue")
    manual_queue_with_optimization = artifact_by_name(artifacts, "mt5_manual_test_queue_with_optimization")
    manual_queue_launch = artifact_by_name(artifacts, "mt5_manual_queue_launch")
    manual_queue_launch_with_optimization = artifact_by_name(
        artifacts,
        "mt5_manual_queue_launch_with_optimization",
    )
    manual_collect = artifact_by_name(artifacts, "mt5_manual_collect_run")
    manual_collect_with_optimization = artifact_by_name(
        artifacts,
        "mt5_manual_collect_with_optimization",
    )
    back_forward_for_manual_queue = artifact_by_name(artifacts, "mt5_back_forward_run")
    manual_queue_status = str(manual_queue.get("status") or "")
    manual_queue_related_reasons = [
        reason
        for reason in reasons
        if is_back_forward_reason(reason)
        or reason.startswith("score_weight_search_")
        or reason.startswith("score_weight_set_")
        or "mt5_manual_collect_run" in reason_values([reason], "stale_runtime_artifacts")
        or "runtime/latest_mt5_manual_collect_run.json" in reason_values([reason], "missing_runtime_artifacts")
    ]
    if (
        manual_queue.get("exists") is True
        and not manual_test_queue_stale_or_missing
        and manual_queue_status in {"waiting_for_manual_strategy_tester_results", "ready_to_collect_all"}
        and (manual_queue_related_reasons or manual_collect_stale_or_missing)
    ):
        queue_entries = (
            manual_queue.get("manual_queue_entries")
            if isinstance(manual_queue.get("manual_queue_entries"), list)
            else []
        )
        queue_stale_entries = (
            manual_queue.get("manual_queue_stale_entries")
            if isinstance(manual_queue.get("manual_queue_stale_entries"), list)
            else []
        )
        queue_checklist = (
            manual_queue.get("manual_queue_execution_checklist")
            if isinstance(manual_queue.get("manual_queue_execution_checklist"), list)
            else []
        )
        queue_targets = (
            manual_queue.get("manual_queue_strategy_tester_targets")
            if isinstance(manual_queue.get("manual_queue_strategy_tester_targets"), list)
            else []
        )
        waiting_for_manual_runs = manual_queue_status == "waiting_for_manual_strategy_tester_results"
        if manual_queue_status == "ready_to_collect_all":
            manual_steps = [
                "Run the collect-only commands for completed MT5 Strategy Tester entries.",
            ]
        else:
            manual_steps = [
                "Open runtime/latest_mt5_manual_test_queue.md and run MT5 Strategy Tester entries in order.",
            ]
        if mt5_validation_blocked_by_bridge and waiting_for_manual_runs:
            append_bridge_standalone_tester_note(manual_steps, bridge_recovery)
        operator_summary_queue = str(status.get("mt5_operator_summary_next_queue_id") or "")
        operator_summary_step = str(status.get("mt5_operator_summary_next_step_label") or "")
        if (
            str(status.get("mt5_operator_summary_manual_queue_status") or "")
            or operator_summary_queue
            or operator_summary_step
        ):
            manual_steps.append(
                "MT5 operator summary: "
                f"queue_status={status.get('mt5_operator_summary_manual_queue_status', '')}, "
                f"queue_action={status.get('mt5_operator_summary_manual_queue_next_action', '')}, "
                f"next={operator_summary_queue}/{operator_summary_step}, "
                f"symbol={status.get('mt5_operator_summary_next_symbol', '')}, "
                f"period={status.get('mt5_operator_summary_next_period', '')}, "
                f"dates={status.get('mt5_operator_summary_next_dates', '')}, "
                f"forward={status.get('mt5_operator_summary_next_forward', '')}, "
                f"inputs={status.get('mt5_operator_summary_next_inputs', '')}, "
                f"report={status.get('mt5_operator_summary_next_report', '')}, "
                f"launch_status={status.get('mt5_operator_summary_launch_status', '')}, "
                f"collect_status={status.get('mt5_operator_summary_collect_status', '')}"
            )
            operator_summary_progress = str(
                status.get("mt5_operator_summary_manual_queue_progress_state") or ""
            )
            operator_summary_step_values = [
                status.get("mt5_operator_summary_manual_queue_step_ready", ""),
                status.get("mt5_operator_summary_manual_queue_step_collect_ready", ""),
                status.get("mt5_operator_summary_manual_queue_step_waiting", ""),
                status.get("mt5_operator_summary_manual_queue_launch_needed", ""),
            ]
            if operator_summary_progress or any(value not in ("", None) for value in operator_summary_step_values):
                manual_steps.append(
                    "MT5 operator queue progress: "
                    f"progress={operator_summary_progress}, "
                    f"step_ready={status.get('mt5_operator_summary_manual_queue_step_ready', '')}, "
                    "step_collect_ready="
                    f"{status.get('mt5_operator_summary_manual_queue_step_collect_ready', '')}, "
                    f"step_waiting={status.get('mt5_operator_summary_manual_queue_step_waiting', '')}, "
                    f"step_launch_needed={status.get('mt5_operator_summary_manual_queue_launch_needed', '')}"
                )
            operator_summary_collect_check = str(
                status.get("mt5_operator_summary_manual_queue_collect_check_command_text") or ""
            )
            if operator_summary_collect_check:
                manual_steps.append(
                    "MT5 operator collect check: " + operator_summary_collect_check
                )
            operator_summary_fingerprint = str(
                status.get("mt5_operator_summary_next_step_fingerprint")
                or status.get("mt5_operator_summary_launch_selected_step_fingerprint")
                or ""
            )
            if operator_summary_fingerprint:
                manual_steps.append(
                    "MT5 operator summary fingerprint: " + operator_summary_fingerprint
                )
            operator_summary_expected_report_artifact = str(
                status.get("mt5_operator_summary_next_expected_report_artifact")
                or status.get("mt5_operator_summary_launch_selected_expected_report_artifact")
                or ""
            )
            if operator_summary_expected_report_artifact:
                manual_steps.append(
                    "MT5 operator expected report artifact: "
                    + operator_summary_expected_report_artifact
                )
            operator_summary_next_step_summary = str(
                status.get("mt5_operator_summary_next_step_operator_summary") or ""
            )
            if operator_summary_next_step_summary:
                manual_steps.append(
                    "MT5 operator next step summary: " + operator_summary_next_step_summary
                )
            operator_summary_collect_filter_summary = str(
                status.get("mt5_operator_summary_next_step_collect_filter_summary") or ""
            )
            if operator_summary_collect_filter_summary:
                manual_steps.append(
                    "MT5 operator collect filter: " + operator_summary_collect_filter_summary
                )
            operator_next_action = str(
                status.get("mt5_operator_summary_next_operator_action") or ""
            )
            operator_next_mode = str(
                status.get("mt5_operator_summary_next_operator_mode") or ""
            )
            operator_next_launch_state = str(
                status.get("mt5_operator_summary_next_operator_launch_state") or ""
            )
            operator_next_manual_start = str(
                status.get("mt5_operator_summary_next_manual_run_start_effective_after")
                or ""
            )
            if (
                operator_next_action
                or operator_next_mode
                or operator_next_launch_state
                or operator_next_manual_start
            ):
                manual_steps.append(
                    "MT5 operator next action: "
                    f"action={operator_next_action}, "
                    f"mode={operator_next_mode}, "
                    f"launch_state={operator_next_launch_state}, "
                    f"manual_start_after={operator_next_manual_start}"
                )
            auto_launch_available = status.get(
                "mt5_operator_summary_auto_launch_command_available"
            )
            auto_launch_blocked = status.get("mt5_operator_summary_auto_launch_blocked")
            auto_launch_blockers = status.get(
                "mt5_operator_summary_auto_launch_blocked_reasons"
            )
            if (
                auto_launch_available not in ("", None)
                or auto_launch_blocked not in ("", None)
                or auto_launch_blockers
            ):
                manual_steps.append(
                    "MT5 operator auto launch: "
                    f"available={auto_launch_available}, "
                    f"blocked={auto_launch_blocked}, "
                    f"blockers={compact_status_value(auto_launch_blockers or [])}"
                )
            strategy_verdict = str(
                status.get("mt5_operator_summary_strategy_operator_decision_verdict") or ""
            )
            strategy_blocker = str(
                status.get(
                    "mt5_operator_summary_strategy_operator_decision_primary_blocker"
                )
                or ""
            )
            if strategy_verdict or strategy_blocker:
                manual_steps.append(
                    "MT5 operator strategy decision: "
                    f"verdict={strategy_verdict}, blocker={strategy_blocker}"
                )
            strategy_command = str(
                status.get("mt5_operator_summary_strategy_operator_decision_command_text")
                or ""
            )
            if strategy_command:
                manual_steps.append("MT5 operator strategy command: " + strategy_command)
        operator_next_action_target = str(
            status.get("mt5_operator_summary_next_action_run_target") or ""
        )
        operator_next_action_kind = str(
            status.get("mt5_operator_summary_next_action_run_kind") or ""
        )
        if operator_next_action_target or operator_next_action_kind:
            primary_outputs = status.get(
                "mt5_operator_summary_next_action_run_primary_planned_outputs"
            )
            if not isinstance(primary_outputs, dict):
                primary_outputs = {}
            manual_steps.append(
                "MT5 operator next action run: "
                f"target={operator_next_action_target}, "
                f"kind={operator_next_action_kind}, "
                f"side={status.get('mt5_operator_summary_next_action_run_focus_side', '')}, "
                f"mode={status.get('mt5_operator_summary_next_action_run_optimization_mode', '')}, "
                f"config={status.get('mt5_operator_summary_next_action_run_config', '')}, "
                f"set={status.get('mt5_operator_summary_next_action_run_set', '')}, "
                f"current={status.get('mt5_operator_summary_next_action_run_current_for_execution', '')}, "
                f"primary={status.get('mt5_operator_summary_next_action_run_primary_execution_class', '')}, "
                f"timeout_min={status.get('mt5_operator_summary_next_action_run_timeout_minutes', '')}, "
                f"deadline_if_started_now={status.get('mt5_operator_summary_next_action_run_timeout_deadline_if_started_now', '')}, "
                f"passes={status.get('mt5_operator_summary_next_action_run_estimated_full_factorial_passes', '')}, "
                f"output_json={primary_outputs.get('output_json', '')}, "
                f"optimization_json={primary_outputs.get('optimization_output_json', '')}"
            )
        operator_summary_blockers = status.get("mt5_operator_summary_launch_blocked_reasons")
        if isinstance(operator_summary_blockers, list) and operator_summary_blockers:
            manual_steps.append(
                "MT5 operator launch blockers: "
                + "; ".join(str(reason) for reason in operator_summary_blockers)
            )
        operator_summary_collect_execute = str(
            status.get("mt5_operator_summary_collect_execute_command_text") or ""
        )
        if operator_summary_collect_execute:
            manual_steps.append("MT5 operator collect execute: " + operator_summary_collect_execute)
        operator_summary_collect_execute_and_refresh = str(
            status.get("mt5_operator_summary_collect_execute_and_refresh_analysis_command_text") or ""
        )
        if operator_summary_collect_execute_and_refresh:
            manual_steps.append(
                "MT5 operator collect execute + analysis: "
                + operator_summary_collect_execute_and_refresh
            )
        append_back_forward_manual_readiness(manual_steps, back_forward_for_manual_queue)
        manual_steps.extend(
            [
                f"Queue status: {manual_queue_status}",
                f"Queue next action: {manual_queue.get('next_action', '')}",
                (
                    "Queue counts: "
                    f"entries={manual_queue.get('entry_count', '')}, "
                    f"total={manual_queue.get('total_entry_count', '')}, "
                    f"stale={manual_queue.get('stale_entry_count', '')}, "
                    f"steps={manual_queue.get('step_count', '')}, "
                    f"waiting={manual_queue.get('waiting_count', '')}, "
                    f"ready={manual_queue.get('ready_to_collect_count', '')}, "
                    f"step_waiting={manual_queue.get('manual_queue_step_waiting_report_count', '')}, "
                    f"step_launch_needed={manual_queue.get('manual_queue_step_launch_needed_count', '')}"
                ),
            ]
        )
        queue_progress = str(manual_queue.get("manual_queue_progress_state") or "")
        queue_step_progress_values = [
            manual_queue.get("manual_queue_step_report_ready_count", ""),
            manual_queue.get("manual_queue_step_collect_ready_count", ""),
            manual_queue.get("manual_queue_step_waiting_report_count", ""),
            manual_queue.get("manual_queue_step_launch_needed_count", ""),
        ]
        if queue_progress or any(value not in ("", None) for value in queue_step_progress_values):
            manual_steps.append(
                "Queue progress: "
                f"progress={queue_progress}, "
                f"report_ready={manual_queue.get('manual_queue_step_report_ready_count', '')}, "
                f"collect_ready={manual_queue.get('manual_queue_step_collect_ready_count', '')}, "
                f"waiting_report={manual_queue.get('manual_queue_step_waiting_report_count', '')}, "
                f"launch_needed={manual_queue.get('manual_queue_step_launch_needed_count', '')}"
            )
        queue_step_id_values = [
            manual_queue.get("manual_queue_step_report_ready_ids"),
            manual_queue.get("manual_queue_step_collect_ready_ids"),
            manual_queue.get("manual_queue_step_waiting_report_ids"),
            manual_queue.get("manual_queue_step_launch_needed_ids"),
        ]
        if any(value for value in queue_step_id_values):
            manual_steps.append(
                "Queue step IDs: "
                f"report_ready={compact_status_value(manual_queue.get('manual_queue_step_report_ready_ids', []))}, "
                f"collect_ready={compact_status_value(manual_queue.get('manual_queue_step_collect_ready_ids', []))}, "
                "waiting_report="
                f"{compact_status_value(manual_queue.get('manual_queue_step_waiting_report_ids', []))}, "
                "launch_needed="
                f"{compact_status_value(manual_queue.get('manual_queue_step_launch_needed_ids', []))}"
            )
        current_gate_values = manual_queue.get("manual_queue_current_promotion_generated_at_values")
        current_decisions = manual_queue.get("manual_queue_current_promotion_decision_values")
        gate_stale_reasons = manual_queue.get("manual_queue_gate_stale_reasons")
        not_current_ids = manual_queue.get("manual_queue_not_current_entry_ids")
        has_current_gate_evidence = any(
            value
            for value in (
                current_gate_values,
                current_decisions,
                gate_stale_reasons,
                not_current_ids,
            )
        )
        has_current_gate_evidence = has_current_gate_evidence or any(
            manual_queue.get(key) not in (None, "", 0)
            for key in (
                "manual_queue_current_for_execution_count",
                "manual_queue_selected_action_current_count",
                "manual_queue_selected_action_stale_count",
            )
        )
        current_gate_parts = []
        for key, label in (
            ("manual_queue_current_for_execution_count", "current_for_execution"),
            ("manual_queue_selected_action_current_count", "selected_action_current"),
            ("manual_queue_selected_action_stale_count", "selected_action_stale"),
        ):
            value = manual_queue.get(key)
            if has_current_gate_evidence and value not in (None, ""):
                current_gate_parts.append(f"{label}={value}")
        if current_gate_values:
            current_gate_parts.append(f"current_gate={compact_status_value(current_gate_values)}")
        if current_decisions:
            current_gate_parts.append(f"current_decision={compact_status_value(current_decisions)}")
        if gate_stale_reasons:
            current_gate_parts.append(f"gate_stale={compact_status_value(gate_stale_reasons)}")
        if not_current_ids:
            current_gate_parts.append(f"not_current={compact_status_value(not_current_ids)}")
        if current_gate_parts:
            manual_steps.append("Queue current Gate: " + ", ".join(current_gate_parts))
        handoff_state = str(manual_queue.get("manual_queue_operator_handoff_state") or "")
        handoff_progress = str(manual_queue.get("manual_queue_operator_handoff_progress_state") or "")
        handoff_status = str(manual_queue.get("manual_queue_operator_handoff_status") or "")
        handoff_next_action = str(manual_queue.get("manual_queue_operator_handoff_next_action") or "")
        handoff_next_queue = str(manual_queue.get("manual_queue_operator_handoff_next_queue_id") or "")
        handoff_next_step = str(manual_queue.get("manual_queue_operator_handoff_next_step_label") or "")
        if handoff_state or handoff_next_queue or handoff_next_step:
            manual_steps.append(
                "Manual queue handoff: "
                f"state={handoff_state}, "
                f"status={handoff_status}, "
                f"next_action={handoff_next_action}, "
                f"collect_ready={manual_queue.get('manual_queue_operator_handoff_collect_ready', '')}, "
                "ready="
                f"{compact_status_value(manual_queue.get('manual_queue_operator_handoff_ready_entry_ids', []))}, "
                "waiting="
                f"{compact_status_value(manual_queue.get('manual_queue_operator_handoff_waiting_entry_ids', []))}, "
                "stale="
                f"{compact_status_value(manual_queue.get('manual_queue_operator_handoff_stale_entry_ids', []))}"
            )
        handoff_step_progress_values = [
            manual_queue.get("manual_queue_operator_handoff_step_report_ready_count", ""),
            manual_queue.get("manual_queue_operator_handoff_step_collect_ready_count", ""),
            manual_queue.get("manual_queue_operator_handoff_step_waiting_report_count", ""),
            manual_queue.get("manual_queue_operator_handoff_step_launch_needed_count", ""),
        ]
        if handoff_progress or any(value not in ("", None) for value in handoff_step_progress_values):
            manual_steps.append(
                "Manual queue handoff progress: "
                f"progress={handoff_progress}, "
                "report_ready="
                f"{manual_queue.get('manual_queue_operator_handoff_step_report_ready_count', '')}, "
                "collect_ready="
                f"{manual_queue.get('manual_queue_operator_handoff_step_collect_ready_count', '')}, "
                "waiting_report="
                f"{manual_queue.get('manual_queue_operator_handoff_step_waiting_report_count', '')}, "
                "launch_needed="
                f"{manual_queue.get('manual_queue_operator_handoff_step_launch_needed_count', '')}"
            )
        handoff_step_id_values = [
            manual_queue.get("manual_queue_operator_handoff_step_report_ready_ids"),
            manual_queue.get("manual_queue_operator_handoff_step_collect_ready_ids"),
            manual_queue.get("manual_queue_operator_handoff_step_waiting_report_ids"),
            manual_queue.get("manual_queue_operator_handoff_step_launch_needed_ids"),
        ]
        if any(value for value in handoff_step_id_values):
            manual_steps.append(
                "Manual queue handoff step IDs: "
                "report_ready="
                f"{compact_status_value(manual_queue.get('manual_queue_operator_handoff_step_report_ready_ids', []))}, "
                "collect_ready="
                f"{compact_status_value(manual_queue.get('manual_queue_operator_handoff_step_collect_ready_ids', []))}, "
                "waiting_report="
                f"{compact_status_value(manual_queue.get('manual_queue_operator_handoff_step_waiting_report_ids', []))}, "
                "launch_needed="
                f"{compact_status_value(manual_queue.get('manual_queue_operator_handoff_step_launch_needed_ids', []))}"
            )
        if handoff_next_queue or handoff_next_step:
            manual_steps.append(
                "Handoff next MT5 step: "
                f"{handoff_next_queue}/{handoff_next_step}, "
                f"Symbol={manual_queue.get('manual_queue_operator_handoff_next_symbol', '')}, "
                f"Period={manual_queue.get('manual_queue_operator_handoff_next_period', '')}, "
                f"Model={manual_queue.get('manual_queue_operator_handoff_next_model', '')}, "
                f"Dates={manual_queue.get('manual_queue_operator_handoff_next_dates', '')}, "
                f"Forward={manual_queue.get('manual_queue_operator_handoff_next_forward', '')}, "
                "Optimization="
                f"{manual_queue.get('manual_queue_operator_handoff_next_optimization_label') or optimization_label_for_item({'optimization': manual_queue.get('manual_queue_operator_handoff_next_optimization', ''), 'run_type': manual_queue.get('manual_queue_operator_handoff_next_run_type', '')})}, "
                f"Run type={manual_queue.get('manual_queue_operator_handoff_next_run_type', '')}, "
                "Expected report="
                f"{manual_queue.get('manual_queue_operator_handoff_next_expected_report_artifact', '')}, "
                f"Launch needed={manual_queue.get('manual_queue_operator_handoff_next_launch_needed', '')}, "
                "Launch kind="
                f"{manual_queue.get('manual_queue_operator_handoff_next_launch_command_kind', '')}, "
                f"Inputs={manual_queue.get('manual_queue_operator_handoff_next_inputs', '')}, "
                f"Report={manual_queue.get('manual_queue_operator_handoff_next_report', '')}"
            )
        handoff_next_step_summary = str(
            manual_queue.get("manual_queue_operator_handoff_next_step_operator_summary") or ""
        )
        if handoff_next_step_summary:
            manual_steps.append("Handoff next step summary: " + handoff_next_step_summary)
        handoff_collect_filter_summary = str(
            manual_queue.get("manual_queue_operator_handoff_next_step_collect_filter_summary") or ""
        )
        if handoff_collect_filter_summary:
            manual_steps.append("Handoff collect filter: " + handoff_collect_filter_summary)
        handoff_dry_run_command = str(
            manual_queue.get("manual_queue_operator_handoff_dry_run_command_text") or ""
        )
        handoff_collect_check_command = str(
            manual_queue.get("manual_queue_operator_handoff_collect_check_command_text") or ""
        )
        handoff_execute_command = str(
            manual_queue.get("manual_queue_operator_handoff_execute_command_text") or ""
        )
        handoff_execute_and_refresh_command = str(
            manual_queue.get("manual_queue_operator_handoff_execute_and_refresh_analysis_command_text") or ""
        )
        handoff_execute_and_refresh_all_command = str(
            manual_queue.get("manual_queue_operator_handoff_execute_and_refresh_all_command_text") or ""
        )
        if handoff_dry_run_command:
            manual_steps.append("Handoff collect dry-run: " + handoff_dry_run_command)
        if handoff_collect_check_command:
            manual_steps.append("Handoff collect check: " + handoff_collect_check_command)
        if handoff_execute_command:
            manual_steps.append("Handoff collect execute: " + handoff_execute_command)
        if handoff_execute_and_refresh_command:
            manual_steps.append(
                "Handoff collect execute + analysis: " + handoff_execute_and_refresh_command
            )
        if handoff_execute_and_refresh_all_command:
            manual_steps.append(
                "Handoff collect execute + full analysis: " + handoff_execute_and_refresh_all_command
            )
        next_operation_queue = str(manual_queue.get("manual_queue_next_operation_queue_id") or "")
        next_operation_step = str(manual_queue.get("manual_queue_next_operation_step_label") or "")
        if next_operation_queue or next_operation_step:
            manual_steps.append(
                "Next operation card: "
                f"action={manual_queue.get('manual_queue_next_operation_action', '')}, "
                f"purpose={manual_queue.get('manual_queue_next_operation_purpose', '')}, "
                f"{next_operation_queue}/{next_operation_step}, "
                f"forward={manual_queue.get('manual_queue_next_operation_forward', '')}, "
                f"optimization={manual_queue.get('manual_queue_next_operation_optimization_label', '')}, "
                f"inputs={manual_queue.get('manual_queue_next_operation_inputs', '')}, "
                f"report={manual_queue.get('manual_queue_next_operation_report', '')}, "
                f"collect_status={manual_queue.get('manual_queue_next_operation_collect_status', '')}"
            )
        next_launch_step = (
            manual_queue.get("manual_queue_next_launch_step")
            if isinstance(manual_queue.get("manual_queue_next_launch_step"), dict)
            else {}
        )
        if next_launch_step:
            manual_steps.append(
                "Next manual Strategy Tester step: "
                f"{next_launch_step.get('order', '')} "
                f"{next_launch_step.get('queue_id', '')}/{next_launch_step.get('step_label', '')}, "
                f"Symbol={next_launch_step.get('symbol', '')}, "
                f"Period={next_launch_step.get('period', '')}, "
                f"Forward={next_launch_step.get('forward', '')}, "
                f"Optimization={optimization_label_for_item(next_launch_step)}, "
                f"Run type={next_launch_step.get('run_type', '')}, "
                f"Step report={next_launch_step.get('step_report_status', '')}, "
                f"Launch kind={next_launch_step.get('launch_command_kind', '')}, "
                f"Inputs={next_launch_step.get('inputs', '')}, "
                f"Report={next_launch_step.get('report', '')}"
            )
        if manual_queue_with_optimization.get("exists") is True:
            static_configs = manual_queue_with_optimization.get("static_strategy_configs")
            static_config_text = (
                compact_status_value(static_configs)
                if isinstance(static_configs, list)
                else ""
            )
            manual_steps.append(
                "Optimization-inclusive queue: "
                f"path={manual_queue_with_optimization.get('path', '')}, "
                f"status={manual_queue_with_optimization.get('status', '')}, "
                f"next_action={manual_queue_with_optimization.get('next_action', '')}, "
                f"entries={manual_queue_with_optimization.get('entry_count', '')}, "
                f"steps={manual_queue_with_optimization.get('step_count', '')}, "
                f"waiting={manual_queue_with_optimization.get('waiting_count', '')}, "
                f"ready={manual_queue_with_optimization.get('ready_to_collect_count', '')}, "
                f"static_configs={static_config_text}"
            )
            optimization_next_step = (
                manual_queue_with_optimization.get("manual_queue_next_launch_step")
                if isinstance(manual_queue_with_optimization.get("manual_queue_next_launch_step"), dict)
                else {}
            )
            if optimization_next_step:
                manual_steps.append(
                    "Optimization queue next MT5 step: "
                    f"{optimization_next_step.get('order', '')} "
                    f"{optimization_next_step.get('queue_id', '')}/"
                    f"{optimization_next_step.get('step_label', '')}, "
                    f"Forward={optimization_next_step.get('forward', '')}, "
                    f"Optimization={optimization_label_for_item(optimization_next_step)}, "
                    f"Run type={optimization_next_step.get('run_type', '')}, "
                    "Expected report="
                    f"{optimization_next_step.get('expected_report_artifact', '')}, "
                    f"Inputs={optimization_next_step.get('inputs', '')}, "
                    f"Report={optimization_next_step.get('report', '')}"
                )
            optimization_targets = (
                manual_queue_with_optimization.get("manual_queue_strategy_tester_targets")
                if isinstance(manual_queue_with_optimization.get("manual_queue_strategy_tester_targets"), list)
                else []
            )
            static_targets = [
                item
                for item in optimization_targets
                if isinstance(item, dict)
                and (
                    str(item.get("queue_id") or "").startswith("static_")
                    or str(item.get("run_type") or "") == "optimization_forward"
                )
            ]
            if static_targets:
                manual_steps.append("Optimization Strategy Tester targets:")
                for item in static_targets:
                    manual_steps.append(
                        f"Optimization target {item.get('order', '')}: "
                        f"{item.get('queue_id', '')}/{item.get('step_label', '')}, "
                        f"Forward={item.get('forward', '')}, "
                        f"Optimization={optimization_label_for_item(item)}, "
                        f"Run type={item.get('run_type', '')}, "
                        f"Expected report={item.get('expected_report_artifact', '')}, "
                        f"Inputs={item.get('inputs', '')}, "
                        f"Report={item.get('report', '')}, "
                        f"Auto launch={item.get('auto_launch_kind', '')}"
                    )
            if manual_queue_launch_with_optimization.get("exists") is True:
                selected_queue_id = str(
                    manual_queue_launch_with_optimization.get("selected_queue_id") or ""
                )
                selected_step_label = str(
                    manual_queue_launch_with_optimization.get("selected_step_label") or ""
                )
                selected_text = "/".join(
                    item for item in (selected_queue_id, selected_step_label) if item
                )
                if not selected_text:
                    selected_text = str(manual_queue_launch_with_optimization.get("selected") or "")
                manual_steps.append(
                    "Optimization queue launch dry-run: "
                    f"status={manual_queue_launch_with_optimization.get('status', '')}, "
                    f"next_action={manual_queue_launch_with_optimization.get('next_action', '')}, "
                    f"selected={selected_text}, "
                    f"kind={manual_queue_launch_with_optimization.get('launch_command_kind', '')}, "
                    f"blocked={manual_queue_launch_with_optimization.get('blocked', '')}, "
                    "running_terminal_count="
                    f"{manual_queue_launch_with_optimization.get('running_terminal_count', '')}"
                )
                launch_blockers = (
                    manual_queue_launch_with_optimization.get("blocked_reasons")
                    if isinstance(manual_queue_launch_with_optimization.get("blocked_reasons"), list)
                    else manual_queue_launch_with_optimization.get("blocking_reasons")
                )
                if isinstance(launch_blockers, list) and launch_blockers:
                    manual_steps.append(
                        "Optimization queue launch blockers: "
                        + "; ".join(str(reason) for reason in launch_blockers)
                    )
                launch_collect_execute = str(
                    manual_queue_launch_with_optimization.get(
                        "queue_operator_handoff_collect_execute_command_text"
                    )
                    or ""
                )
                if launch_collect_execute:
                    manual_steps.append(
                        "Optimization queue launch handoff collect execute: "
                        + launch_collect_execute
                    )
                launch_collect_execute_and_refresh = str(
                    manual_queue_launch_with_optimization.get(
                        "queue_operator_handoff_collect_execute_and_refresh_analysis_command_text"
                    )
                    or ""
                )
                if launch_collect_execute_and_refresh:
                    manual_steps.append(
                        "Optimization queue launch handoff collect execute + analysis: "
                        + launch_collect_execute_and_refresh
                    )
            if manual_collect_with_optimization.get("exists") is True:
                manual_steps.append(
                    "Optimization queue collect status: "
                    f"{manual_collect_with_optimization.get('status', '')}, "
                    f"next_action={manual_collect_with_optimization.get('next_action', '')}, "
                    f"selected={manual_collect_with_optimization.get('selected_count', '')}, "
                    f"ready={manual_collect_with_optimization.get('ready_entry_count', '')}, "
                    f"waiting={manual_collect_with_optimization.get('waiting_count', '')}, "
                    f"invalid={manual_collect_with_optimization.get('invalid_count', '')}, "
                    f"queue_refresh={manual_collect_with_optimization.get('queue_refresh_status', '')}, "
                    f"queue_refresh_ok={manual_collect_with_optimization.get('queue_refresh_ok', '')}"
                )
                collect_blockers = manual_collect_with_optimization.get("blocking_reasons")
                if isinstance(collect_blockers, list) and collect_blockers:
                    manual_steps.append(
                        "Optimization queue collect blockers: "
                        + "; ".join(str(reason) for reason in collect_blockers)
                    )
            watch_optimization_launch_selected_queue = str(
                status.get("status_watch_manual_queue_launch_with_optimization_refresh_selected_queue_id")
                or ""
            )
            watch_optimization_launch_selected_step = str(
                status.get("status_watch_manual_queue_launch_with_optimization_refresh_selected_step_label")
                or ""
            )
            watch_optimization_launch_has_evidence = any(
                status.get(key) not in (None, "")
                for key in (
                    "status_watch_manual_queue_launch_with_optimization_refresh_enabled",
                    "status_watch_manual_queue_launch_with_optimization_refresh_returncode",
                    "status_watch_manual_queue_launch_with_optimization_refresh_status",
                    "status_watch_manual_queue_launch_with_optimization_refresh_queue_refresh_status",
                    "status_watch_manual_queue_launch_with_optimization_refresh_selected_queue_id",
                    "status_watch_manual_queue_launch_with_optimization_refresh_selected_step_label",
                )
            )
            if watch_optimization_launch_has_evidence:
                manual_steps.append(
                    "Status watcher optimization queue launch refresh: "
                    f"enabled={status.get('status_watch_manual_queue_launch_with_optimization_refresh_enabled', '')}, "
                    f"returncode={status.get('status_watch_manual_queue_launch_with_optimization_refresh_returncode', '')}, "
                    f"completed={status.get('status_watch_manual_queue_launch_with_optimization_refresh_completed', '')}, "
                    f"status={status.get('status_watch_manual_queue_launch_with_optimization_refresh_status', '')}, "
                    "queue_refresh="
                    f"{status.get('status_watch_manual_queue_launch_with_optimization_refresh_queue_refresh_status', '')}, "
                    "queue_refresh_ok="
                    f"{status.get('status_watch_manual_queue_launch_with_optimization_refresh_queue_refresh_ok', '')}, "
                    "queue_refresh_sources="
                    f"{status.get('status_watch_manual_queue_launch_with_optimization_refresh_queue_refresh_source_count', '')}, "
                    f"selected={watch_optimization_launch_selected_queue}/{watch_optimization_launch_selected_step}, "
                    f"blocked={status.get('status_watch_manual_queue_launch_with_optimization_refresh_blocked', '')}, "
                    "blockers="
                    f"{compact_status_value(status.get('status_watch_manual_queue_launch_with_optimization_refresh_blocked_reasons', []))}"
                )
            watch_optimization_collect_has_evidence = any(
                status.get(key) not in (None, "")
                for key in (
                    "status_watch_manual_collect_with_optimization_refresh_enabled",
                    "status_watch_manual_collect_with_optimization_refresh_returncode",
                    "status_watch_manual_collect_with_optimization_refresh_status",
                    "status_watch_manual_collect_with_optimization_refresh_queue_refresh_status",
                    "status_watch_manual_collect_with_optimization_refresh_selected_count",
                    "status_watch_manual_collect_with_optimization_refresh_waiting_count",
                    "status_watch_manual_collect_with_optimization_refresh_invalid_count",
                )
            )
            if watch_optimization_collect_has_evidence:
                manual_steps.append(
                    "Status watcher optimization collect refresh: "
                    f"enabled={status.get('status_watch_manual_collect_with_optimization_refresh_enabled', '')}, "
                    f"returncode={status.get('status_watch_manual_collect_with_optimization_refresh_returncode', '')}, "
                    f"completed={status.get('status_watch_manual_collect_with_optimization_refresh_completed', '')}, "
                    f"status={status.get('status_watch_manual_collect_with_optimization_refresh_status', '')}, "
                    "queue_refresh="
                    f"{status.get('status_watch_manual_collect_with_optimization_refresh_queue_refresh_status', '')}, "
                    "queue_refresh_ok="
                    f"{status.get('status_watch_manual_collect_with_optimization_refresh_queue_refresh_ok', '')}, "
                    "queue_refresh_sources="
                    f"{status.get('status_watch_manual_collect_with_optimization_refresh_queue_refresh_source_count', '')}, "
                    f"selected={status.get('status_watch_manual_collect_with_optimization_refresh_selected_count', '')}, "
                    f"waiting={status.get('status_watch_manual_collect_with_optimization_refresh_waiting_count', '')}, "
                    f"invalid={status.get('status_watch_manual_collect_with_optimization_refresh_invalid_count', '')}"
                )
        else:
            manual_steps.append(
                "Optimization-inclusive queue is not generated yet; run "
                "refresh_manual_test_queue_with_optimization to add Optimization and Next Optimization "
                "Strategy Tester configs after Back/Forward/SELL/BUY."
            )
        if queue_stale_entries:
            manual_steps.append("Stale runner refresh:")
            for entry in queue_stale_entries:
                if not isinstance(entry, dict):
                    continue
                stale_reasons = entry.get("stale_reasons") if isinstance(entry.get("stale_reasons"), list) else []
                stale_reason_text = "; ".join(str(reason) for reason in stale_reasons)
                manual_steps.append(
                    f"Stale {entry.get('id', '')}: current={entry.get('current_for_execution', '')}, "
                    f"gate_stale={entry.get('gate_stale_reason', '')}, "
                    f"runner_generated={entry.get('runner_generated_at', '')}, "
                    f"gate_generated={entry.get('promotion_generated_at', '')}, "
                    f"current_gate={entry.get('current_promotion_generated_at', '')}, "
                    f"reason={stale_reason_text}, "
                    f"refresh={entry.get('refresh_command_text', '')}"
                )
        blocking_reasons = manual_queue.get("blocking_reasons")
        if isinstance(blocking_reasons, list) and blocking_reasons:
            manual_steps.append(
                "Queue blocking reasons: " + "; ".join(str(reason) for reason in blocking_reasons)
            )
        if manual_collect.get("exists") is True:
            manual_steps.extend(
                [
                    (
                        "Manual collect status: "
                        f"{manual_collect.get('status', '')}, "
                        f"next_action={manual_collect.get('next_action', '')}"
                    ),
                    (
                        "Manual collect counts: "
                        f"selected={manual_collect.get('selected_count', '')}, "
                        f"ready={manual_collect.get('ready_entry_count', '')}, "
                        f"waiting={manual_collect.get('waiting_count', '')}, "
                        f"invalid={manual_collect.get('invalid_count', '')}, "
                        f"queue_refresh={manual_collect.get('queue_refresh_status', '')}, "
                        f"queue_refresh_ok={manual_collect.get('queue_refresh_ok', '')}, "
                        f"steps={manual_collect.get('queue_step_count', '')}, "
                        f"step_ready={manual_collect.get('queue_step_report_ready_count', '')}, "
                        f"step_waiting={manual_collect.get('queue_step_waiting_report_count', '')}, "
                        f"step_launch_needed={manual_collect.get('queue_step_launch_needed_count', '')}"
                    ),
                ]
            )
            collect_blocking_reasons = manual_collect.get("blocking_reasons")
            if isinstance(collect_blocking_reasons, list) and collect_blocking_reasons:
                manual_steps.append(
                    "Manual collect blocking reasons: "
                    + "; ".join(str(reason) for reason in collect_blocking_reasons)
                )
        elif manual_collect_stale_or_missing:
            manual_steps.append(
                "Manual collect run is missing or stale; run dry_run_manual_queue_collect_ready before executing collect-only commands."
            )
        watch_collect_refresh_has_evidence = any(
            status.get(key) not in (None, "")
            for key in (
                "status_watch_manual_collect_refresh_enabled",
                "status_watch_manual_collect_refresh_returncode",
                "status_watch_manual_collect_refresh_status",
                "status_watch_manual_collect_refresh_queue_refresh_status",
                "status_watch_manual_collect_refresh_selected_count",
                "status_watch_manual_collect_refresh_waiting_count",
                "status_watch_manual_collect_refresh_invalid_count",
            )
        )
        if watch_collect_refresh_has_evidence:
            manual_steps.append(
                "Status watcher manual collect refresh: "
                f"enabled={status.get('status_watch_manual_collect_refresh_enabled', '')}, "
                f"returncode={status.get('status_watch_manual_collect_refresh_returncode', '')}, "
                f"completed={status.get('status_watch_manual_collect_refresh_completed', '')}, "
                f"status={status.get('status_watch_manual_collect_refresh_status', '')}, "
                f"queue_refresh={status.get('status_watch_manual_collect_refresh_queue_refresh_status', '')}, "
                f"queue_refresh_ok={status.get('status_watch_manual_collect_refresh_queue_refresh_ok', '')}, "
                f"queue_refresh_sources={status.get('status_watch_manual_collect_refresh_queue_refresh_source_count', '')}, "
                f"selected={status.get('status_watch_manual_collect_refresh_selected_count', '')}, "
                f"waiting={status.get('status_watch_manual_collect_refresh_waiting_count', '')}, "
                f"invalid={status.get('status_watch_manual_collect_refresh_invalid_count', '')}"
            )
        watch_collect_progress_has_evidence = any(
            status.get(key) not in (None, "")
            for key in (
                "status_watch_manual_collect_run_queue_step_count",
                "status_watch_manual_collect_run_queue_step_report_ready_count",
                "status_watch_manual_collect_run_queue_step_waiting_report_count",
                "status_watch_manual_collect_run_queue_step_launch_needed_count",
            )
        )
        if watch_collect_progress_has_evidence:
            manual_steps.append(
                "Status watcher manual collect progress: "
                f"steps={status.get('status_watch_manual_collect_run_queue_step_count', '')}, "
                f"step_ready={status.get('status_watch_manual_collect_run_queue_step_report_ready_count', '')}, "
                f"step_waiting={status.get('status_watch_manual_collect_run_queue_step_waiting_report_count', '')}, "
                f"step_launch_needed={status.get('status_watch_manual_collect_run_queue_step_launch_needed_count', '')}"
            )
        watch_launch_refresh_status = str(
            status.get("status_watch_manual_queue_launch_refresh_status") or ""
        )
        watch_launch_refresh_selected_queue = str(
            status.get("status_watch_manual_queue_launch_refresh_selected_queue_id") or ""
        )
        watch_launch_refresh_selected_step = str(
            status.get("status_watch_manual_queue_launch_refresh_selected_step_label") or ""
        )
        watch_launch_refresh_has_evidence = any(
            status.get(key) not in (None, "")
            for key in (
                "status_watch_manual_queue_launch_refresh_enabled",
                "status_watch_manual_queue_launch_refresh_returncode",
                "status_watch_manual_queue_launch_refresh_status",
                "status_watch_manual_queue_launch_refresh_queue_refresh_status",
                "status_watch_manual_queue_launch_refresh_selected_queue_id",
                "status_watch_manual_queue_launch_refresh_selected_step_label",
            )
        )
        if watch_launch_refresh_has_evidence:
            manual_steps.append(
                "Status watcher manual queue launch refresh: "
                f"enabled={status.get('status_watch_manual_queue_launch_refresh_enabled', '')}, "
                f"returncode={status.get('status_watch_manual_queue_launch_refresh_returncode', '')}, "
                f"completed={status.get('status_watch_manual_queue_launch_refresh_completed', '')}, "
                f"status={watch_launch_refresh_status}, "
                f"queue_refresh={status.get('status_watch_manual_queue_launch_refresh_queue_refresh_status', '')}, "
                f"queue_refresh_ok={status.get('status_watch_manual_queue_launch_refresh_queue_refresh_ok', '')}, "
                f"queue_refresh_sources={status.get('status_watch_manual_queue_launch_refresh_queue_refresh_source_count', '')}, "
                f"selected={watch_launch_refresh_selected_queue}/{watch_launch_refresh_selected_step}, "
                f"blocked={status.get('status_watch_manual_queue_launch_refresh_blocked', '')}, "
                "blockers="
                f"{compact_status_value(status.get('status_watch_manual_queue_launch_refresh_blocked_reasons', []))}"
            )
        if manual_queue_launch.get("exists") is True:
            selected_queue_id = str(manual_queue_launch.get("selected_queue_id") or "")
            selected_step_label = str(manual_queue_launch.get("selected_step_label") or "")
            selected_text = "/".join(item for item in (selected_queue_id, selected_step_label) if item)
            if not selected_text:
                selected_text = str(manual_queue_launch.get("selected") or "")
            manual_steps.append(
                "Manual queue launch dry-run: "
                f"status={manual_queue_launch.get('status', '')}, "
                f"next_action={manual_queue_launch.get('next_action', '')}, "
                f"selected={selected_text}, "
                f"kind={manual_queue_launch.get('launch_command_kind', '')}, "
                f"blocked={manual_queue_launch.get('blocked', '')}, "
                f"running_terminal_count={manual_queue_launch.get('running_terminal_count', '')}"
            )
            launch_selected_fingerprint = str(
                manual_queue_launch.get("selected_step_fingerprint") or ""
            )
            if launch_selected_fingerprint:
                manual_steps.append(
                    "Manual queue launch selected fingerprint: "
                    + launch_selected_fingerprint
                )
            launch_selected_expected_report = str(
                manual_queue_launch.get("selected_expected_report") or ""
            )
            if launch_selected_expected_report:
                manual_steps.append(
                    "Manual queue launch selected expected report: "
                    + launch_selected_expected_report
                )
            launch_blocking_reasons = (
                manual_queue_launch.get("blocked_reasons")
                if isinstance(manual_queue_launch.get("blocked_reasons"), list)
                else manual_queue_launch.get("blocking_reasons")
            )
            if isinstance(launch_blocking_reasons, list) and launch_blocking_reasons:
                manual_steps.append(
                    "Manual queue launch blockers: "
                    + "; ".join(str(reason) for reason in launch_blocking_reasons)
                )
            launch_command_text = str(manual_queue_launch.get("command_text") or "")
            if launch_command_text:
                manual_steps.append("Manual queue launch command: " + launch_command_text)
            launch_handoff_state = str(manual_queue_launch.get("queue_operator_handoff_state") or "")
            launch_handoff_next_queue = str(
                manual_queue_launch.get("queue_operator_handoff_next_queue_id") or ""
            )
            launch_handoff_next_step = str(
                manual_queue_launch.get("queue_operator_handoff_next_step_label") or ""
            )
            if launch_handoff_state or launch_handoff_next_queue or launch_handoff_next_step:
                launch_handoff_fingerprint = str(
                    manual_queue_launch.get("queue_operator_handoff_next_step_fingerprint") or ""
                )
                launch_handoff_fingerprint_text = (
                    f"fingerprint={launch_handoff_fingerprint}, "
                    if launch_handoff_fingerprint
                    else ""
                )
                manual_steps.append(
                    "Manual queue launch handoff: "
                    f"state={launch_handoff_state}, "
                    "selected_matches="
                    f"{manual_queue_launch.get('selected_matches_queue_handoff', '')}, "
                    f"next={launch_handoff_next_queue}/{launch_handoff_next_step}, "
                    f"{launch_handoff_fingerprint_text}"
                    f"forward={manual_queue_launch.get('queue_operator_handoff_next_forward', '')}, "
                    f"report={manual_queue_launch.get('queue_operator_handoff_next_report', '')}, "
                    f"collect_ready={manual_queue_launch.get('queue_operator_handoff_collect_ready', '')}, "
                    "waiting="
                    f"{compact_status_value(manual_queue_launch.get('queue_operator_handoff_waiting_entry_ids', []))}"
                )
            launch_handoff_collect_execute = str(
                manual_queue_launch.get("queue_operator_handoff_collect_execute_command_text") or ""
            )
            if launch_handoff_collect_execute:
                manual_steps.append(
                    "Manual queue launch handoff collect execute: "
                    + launch_handoff_collect_execute
                )
            launch_handoff_collect_execute_and_refresh = str(
                manual_queue_launch.get(
                    "queue_operator_handoff_collect_execute_and_refresh_analysis_command_text"
                )
                or ""
            )
            if launch_handoff_collect_execute_and_refresh:
                manual_steps.append(
                    "Manual queue launch handoff collect execute + analysis: "
                    + launch_handoff_collect_execute_and_refresh
                )
            launch_handoff_collect_execute_and_refresh_all = str(
                manual_queue_launch.get(
                    "queue_operator_handoff_collect_execute_and_refresh_all_command_text"
                )
                or ""
            )
            if launch_handoff_collect_execute_and_refresh_all:
                manual_steps.append(
                    "Manual queue launch handoff collect execute + full analysis: "
                    + launch_handoff_collect_execute_and_refresh_all
                )
        if queue_targets:
            manual_steps.append("Manual Strategy Tester targets:")
            for item in queue_targets:
                if not isinstance(item, dict):
                    continue
                manual_steps.append(
                    f"Target {item.get('order', '')}: "
                    f"{item.get('purpose', '')}, "
                    f"{item.get('queue_id', '')}/{item.get('step_label', '')}, "
                    f"Symbol={item.get('symbol', '')}, Period={item.get('period', '')}, "
                    f"Dates={item.get('dates', '')}, Forward={item.get('forward', '')}, "
                    f"Optimization={optimization_label_for_item(item)}, "
                    f"Run type={item.get('run_type', '')}, "
                    f"Expected report={item.get('expected_report_artifact', '')}, "
                    f"Report note={item.get('report_expectation_note', '')}, "
                    f"Inputs={item.get('inputs', '')}, Report={item.get('report', '')}, "
                    f"Start after={item.get('start_after', '')}, "
                    f"Collect after={item.get('collect_modified_after', '')}, "
                    f"Collect={item.get('collect_status', '')}, "
                    f"Step report={item.get('step_report_status', '')}, "
                    f"Launch needed={item.get('launch_needed', '')}, "
                    f"Auto launch={item.get('auto_launch_kind', '')}"
                )
        if queue_checklist:
            manual_steps.append("Manual execution checklist:")
            for item in queue_checklist:
                if not isinstance(item, dict):
                    continue
                manual_steps.append(
                    f"Checklist {item.get('order', '')}: "
                    f"{item.get('queue_id', '')}/{item.get('step_label', '')}, "
                    f"Symbol={item.get('symbol', '')}, Period={item.get('period', '')}, "
                    f"Model={item.get('model', '')}, Dates={item.get('dates', '')}, "
                    f"Forward={item.get('forward', '')}, "
                    f"Optimization={optimization_label_for_item(item)}, "
                    f"Run type={item.get('run_type', '')}, "
                    f"Expected report={item.get('expected_report_artifact', '')}, "
                    f"Report note={item.get('report_expectation_note', '')}, "
                    f"Step report={item.get('step_report_status', '')}, "
                    f"Launch needed={item.get('launch_needed', '')}, "
                    f"Inputs={item.get('inputs', '')}, "
                    f"Report={item.get('report', '')}, Start after={item.get('manual_run_start_after', '')}"
                )
            launch_items = [
                item
                for item in queue_checklist
                if isinstance(item, dict)
                and (
                    item.get("launch_command_text")
                    or item.get("launch_error")
                    or item.get("mt5_config")
                )
            ]
            if launch_items:
                manual_steps.append("Manual queue auto launch commands:")
                for item in launch_items:
                    command_text = str(item.get("launch_command_text") or "")
                    kind = str(item.get("launch_command_kind") or "")
                    if command_text and kind == "runner_execute":
                        command_text = f"runner execute: {command_text}"
                    if not command_text:
                        command_text = f"launch unavailable: {item.get('launch_error', '')}"
                    manual_steps.append(
                        f"Launch {item.get('order', '')}: "
                        f"{item.get('queue_id', '')}/{item.get('step_label', '')}, "
                        f"kind={kind}, workspace_config={item.get('config', '')}, "
                        f"mt5_config={item.get('mt5_config', '')}, command={command_text}"
                    )
        commands = []
        commands.append(
            command_step(
                "refresh_manual_test_queue",
                "python3 methods/swing_eval/analysis/mt5_manual_test_queue.py "
                "--output-json runtime/latest_mt5_manual_test_queue.json "
                "--output-md runtime/latest_mt5_manual_test_queue.md",
            )
        )
        commands.append(
            command_step(
                "refresh_manual_test_queue_with_optimization",
                refresh_manual_test_queue_with_optimization_command,
            )
        )
        commands.append(
            command_step(
                "refresh_manual_operator_packet_with_optimization",
                refresh_manual_operator_packet_with_optimization_command,
            )
        )
        if waiting_for_manual_runs:
            commands.append(
                command_step(
                    "dry_run_manual_queue_launch_next",
                    "python3 methods/swing_eval/analysis/mt5_manual_queue_launch.py "
                    "--queue runtime/latest_mt5_manual_test_queue.json "
                    "--output-json runtime/latest_mt5_manual_queue_launch.json "
                    "--output-md runtime/latest_mt5_manual_queue_launch.md",
                )
            )
            commands.append(
                command_step(
                    "dry_run_manual_queue_launch_next_with_optimization",
                    "python3 methods/swing_eval/analysis/mt5_manual_queue_launch.py "
                    f"--queue {DEFAULT_MT5_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
                    f"--output-json {DEFAULT_MT5_MANUAL_QUEUE_LAUNCH_WITH_OPTIMIZATION} "
                    "--output-md runtime/latest_mt5_manual_queue_launch_with_optimization.md",
                )
            )
        commands.append(
            command_step(
                "dry_run_manual_queue_collect_ready",
                handoff_dry_run_command
                or (
                    "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                    "--queue runtime/latest_mt5_manual_test_queue.json "
                    "--output-json runtime/latest_mt5_manual_collect_run.json "
                    "--output-md runtime/latest_mt5_manual_collect_run.md"
                ),
            )
        )
        commands.append(
            command_step(
                "dry_run_manual_queue_collect_ready_with_optimization",
                "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                f"--queue {DEFAULT_MT5_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
                f"--output-json {DEFAULT_MT5_MANUAL_COLLECT_WITH_OPTIMIZATION} "
                "--output-md runtime/latest_mt5_manual_collect_with_optimization.md",
            )
        )
        commands.append(
            command_step(
                "watch_manual_auto_collect_with_optimization_once",
                watch_manual_auto_collect_with_optimization_command,
            )
        )
        commands.append(
            command_step(
                "execute_ready_manual_auto_collect_with_optimization_once",
                execute_ready_manual_auto_collect_with_optimization_command,
            )
        )
        if manual_queue_status == "ready_to_collect_all":
            commands.append(
                command_step(
                    "execute_manual_queue_collect_ready",
                    handoff_execute_command
                    or (
                        "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                        "--queue runtime/latest_mt5_manual_test_queue.json "
                        "--execute "
                        "--output-json runtime/latest_mt5_manual_collect_run.json "
                        "--output-md runtime/latest_mt5_manual_collect_run.md"
                    ),
                )
            )
            commands.append(
                command_step(
                    "execute_manual_queue_collect_ready_and_refresh_analysis",
                    handoff_execute_and_refresh_command
                    or (
                        "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                        "--queue runtime/latest_mt5_manual_test_queue.json "
                        "--execute "
                        "--refresh-strategy-tester-analysis "
                        "--output-json runtime/latest_mt5_manual_collect_run.json "
                        "--output-md runtime/latest_mt5_manual_collect_run.md"
                    ),
                )
            )
            commands.append(
                command_step(
                    "execute_manual_queue_collect_ready_and_refresh_full_analysis",
                    handoff_execute_and_refresh_all_command
                    or (
                        "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                        "--queue runtime/latest_mt5_manual_test_queue.json "
                        "--execute "
                        "--refresh-post-collect-analysis "
                        "--output-json runtime/latest_mt5_manual_collect_run.json "
                        "--output-md runtime/latest_mt5_manual_collect_run.md"
                    ),
                )
            )
        if str(manual_queue_with_optimization.get("status") or "") == "ready_to_collect_all":
            commands.append(
                command_step(
                    "execute_manual_queue_collect_ready_with_optimization",
                    "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                    f"--queue {DEFAULT_MT5_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
                    "--execute "
                    f"--output-json {DEFAULT_MT5_MANUAL_COLLECT_WITH_OPTIMIZATION} "
                    "--output-md runtime/latest_mt5_manual_collect_with_optimization.md",
                )
            )
        for entry in queue_entries:
            if not isinstance(entry, dict):
                continue
            entry_id = str(entry.get("id") or "entry")
            entry_step = (
                f"Queue entry {entry_id}: status={entry.get('collect_status', '')}, "
                f"ready={entry.get('collect_ready', '')}, steps={entry.get('step_count', '')}, "
                f"modified_after={entry.get('collect_modified_after', '')}, "
                f"runner_generated={entry.get('runner_generated_at', '')}, "
                f"gate_generated={entry.get('promotion_generated_at', '')}, "
                f"decision={entry.get('promotion_decision', '')}"
            )
            extra_parts = []
            if entry.get("current_promotion_generated_at") not in (None, ""):
                extra_parts.append(f"current_gate={entry.get('current_promotion_generated_at', '')}")
            if entry.get("current_promotion_decision") not in (None, ""):
                extra_parts.append(f"current_decision={entry.get('current_promotion_decision', '')}")
            if entry.get("selected_action_current") not in (None, ""):
                extra_parts.append(f"action_current={entry.get('selected_action_current', '')}")
            if extra_parts:
                entry_step += ", " + ", ".join(extra_parts)
            manual_steps.append(entry_step)
            collect_command = str(entry.get("collect_only_command_text") or "")
            if entry.get("collect_ready") is True and collect_command:
                commands.append(command_step(f"collect_{entry_id}", collect_command))
        commands.append(
            command_step(
                "refresh_mt5_tester_status_after_manual_queue",
                mt5_tester_status_refresh_command(),
            )
        )
        add_next_action(
            actions,
            {
                "id": "run_mt5_manual_test_queue",
                "priority": 29,
                "area": "mt5_manual_queue",
                "summary": "Use the consolidated manual Strategy Tester queue for Back/Forward and BUY/SELL sample collection.",
                "reasons": manual_queue_related_reasons,
                "commands": commands,
                "manual_steps": manual_steps,
            },
        )

    back_forward = artifact_by_name(artifacts, "mt5_back_forward_run")
    strategy_analysis_for_back_forward = artifact_by_name(artifacts, "mt5_strategy_tester_analysis")
    back_forward_prerequisites_not_ready = reason_present(
        reasons,
        "mt5_back_forward_manual_prerequisites_not_ready",
    )
    back_forward_plan_validation_not_ready = reason_present(
        reasons,
        "mt5_back_forward_plan_validation_not_ready",
    )
    if back_forward_prerequisites_not_ready or back_forward_plan_validation_not_ready:
        prerequisite_reasons = back_forward.get("manual_prerequisites_reasons")
        if not isinstance(prerequisite_reasons, list):
            prerequisite_reasons = []
        validation_reasons = back_forward.get("back_forward_plan_validation_reasons")
        if not isinstance(validation_reasons, list):
            validation_reasons = []
        compile_status_path = str(
            back_forward.get("manual_prerequisites_compile_status_path")
            or "runtime/latest_mt5_compile_status.json"
        )
        manual_steps = [
            "Refresh compile status, re-sync/compile MT5 artifacts, and regenerate the Back/Forward plan before running Strategy Tester.",
        ]
        if prerequisite_reasons:
            manual_steps.append("Prerequisite reasons: " + "; ".join(str(reason) for reason in prerequisite_reasons))
        if validation_reasons:
            manual_steps.append("Back/Forward plan validation reasons: " + "; ".join(str(reason) for reason in validation_reasons))
        validation_status = str(back_forward.get("back_forward_plan_validation_status") or "")
        if validation_status:
            manual_steps.append(f"Back/Forward plan validation status: {validation_status}")
        if compile_status_path:
            manual_steps.append(f"Compile status path: {compile_status_path}")
        add_next_action(
            actions,
            {
                "id": "refresh_mt5_back_forward_prerequisites",
                "priority": 25,
                "area": "mt5_back_forward",
                "summary": "Refresh compile/config/set readiness and Back/Forward plan validation before MT5 execution.",
                "reasons": [
                    reason
                    for reason in reasons
                    if reason.startswith("mt5_back_forward_manual_prerequisites_not_ready:")
                    or reason.startswith("mt5_back_forward_plan_validation_not_ready:")
                ],
                "commands": [
                    command_step(
                        "refresh_compile_status",
                        "python3 methods/swing_eval/analysis/mt5_compile_status.py "
                        "--output-json runtime/latest_mt5_compile_status.json "
                        "--output-md runtime/latest_mt5_compile_status.md",
                    ),
                    command_step(
                        "refresh_back_forward_plan",
                        "python3 methods/swing_eval/analysis/mt5_back_forward_run.py --mode both "
                        "--timeout-seconds 3600 --since-minutes 240 --min-closed 30",
                    ),
                ],
                "manual_steps": manual_steps,
            },
        )
    back_forward_decision_requires_action = reason_present(reasons, "mt5_back_forward_decision")
    back_forward_execution_requires_action = (
        reason_present(reasons, "mt5_back_forward_not_executed")
        or reason_present(reasons, "mt5_back_forward_executed_sample_shortage")
        or reason_present(reasons, "mt5_back_forward_executed_not_adoptable")
    )
    if back_forward_execution_requires_action or back_forward_decision_requires_action:
        hints = back_forward.get("execution_hints") if isinstance(back_forward.get("execution_hints"), dict) else {}
        pack = (
            back_forward.get("mt5_strategy_tester_pack")
            if isinstance(back_forward.get("mt5_strategy_tester_pack"), dict)
            else {}
        )
        execute_command = (
            hints.get("execute_command_text")
            or back_forward.get("back_forward_execute_hint")
            or "python3 methods/swing_eval/analysis/mt5_back_forward_run.py --mode both --execute --refresh-ready-status "
            "--timeout-seconds 3600 --since-minutes 240 --min-closed 30"
        )
        collect_only_command = (
            back_forward.get("mt5_strategy_tester_pack_collect_command_text")
            or pack.get("collect_command_text")
            or back_forward.get("manual_collect_only_command_text")
            or hints.get("collect_only_command_text")
            or strategy_analysis_for_back_forward.get("strategy_tester_analysis_collect_only_command_text")
            or "python3 methods/swing_eval/analysis/mt5_back_forward_run.py --mode both --collect-only "
            "--timeout-seconds 3600 --since-minutes 240 --min-closed 30"
        )
        back_forward_collect_ready = back_forward.get("manual_collect_ready") is True
        decision_next_action = str(
            strategy_analysis_for_back_forward.get(
                "strategy_tester_analysis_back_forward_decision_next_action"
            )
            or ""
        )
        decision_status = str(
            strategy_analysis_for_back_forward.get(
                "strategy_tester_analysis_back_forward_decision_status"
            )
            or ""
        )
        decision_review_only = decision_next_action == "reject_or_refit_before_promotion"
        manual_steps = []
        manual_steps.append(
            "Use collect-only after manual MT5 Strategy Tester runs; add --csv-modified-after when old Agent CSV may remain."
        )
        append_strategy_back_forward_decision_steps(manual_steps, strategy_analysis_for_back_forward)
        if decision_review_only:
            manual_steps.append(
                "Do not promote this Strategy Tester candidate as-is; refit or adjust the candidate before running another promotion gate."
            )
        if mt5_validation_blocked_by_bridge and not back_forward_collect_ready:
            append_bridge_standalone_tester_note(manual_steps, bridge_recovery)
        if back_forward_prerequisites_not_ready:
            manual_steps.insert(0, "Clear manual Strategy Tester prerequisites before running or collecting results.")
        append_back_forward_manual_readiness(manual_steps, back_forward)
        collect_parts: list[str] = []
        for key, label in (
            ("manual_collect_ready", "ready"),
            ("manual_collect_status", "status"),
            ("manual_collect_csv_count", "csv"),
            ("manual_collect_modified_after", "modified_after"),
        ):
            value = back_forward.get(key)
            if value not in (None, ""):
                collect_parts.append(f"{label}={value}")
        if collect_parts:
            manual_steps.append("Manual Collect Readiness: " + ", ".join(collect_parts))
        if back_forward.get("manual_collect_reason"):
            manual_steps.append("Manual collect reason: " + str(back_forward.get("manual_collect_reason")))
        blocking_reasons = back_forward.get("manual_collect_blocking_reasons")
        if isinstance(blocking_reasons, list) and blocking_reasons:
            manual_steps.append("Manual collect blocking reasons: " + "; ".join(str(reason) for reason in blocking_reasons))
        if back_forward.get("manual_collect_next_action"):
            manual_steps.append("Manual collect next action: " + str(back_forward.get("manual_collect_next_action")))
        append_back_forward_performance_steps(manual_steps, back_forward)
        commands = []
        if decision_review_only:
            commands.append(
                command_step(
                    "refresh_strategy_tester_analysis",
                    MT5_STRATEGY_TESTER_ANALYSIS_REFRESH_COMMAND_TEXT,
                )
            )
        elif back_forward_collect_ready or decision_status == "collect_ready":
            commands.append(command_step("collect_manual_results", str(collect_only_command)))
        else:
            commands.extend(
                [
                    command_step("execute_with_mt5_launch", str(execute_command)),
                    command_step("collect_manual_results", str(collect_only_command)),
                ]
            )
        if not decision_review_only:
            commands.append(
                command_step(
                    "refresh_strategy_tester_analysis",
                    MT5_STRATEGY_TESTER_ANALYSIS_REFRESH_COMMAND_TEXT,
                )
            )
        if (
            back_forward.get("performance_comparison_available") is True
            and str(back_forward.get("performance_comparison_status") or "") in BACK_FORWARD_SAMPLE_SHORTAGE_STATES
        ):
            commands.append(
                command_step(
                    "run_extended_window_back_forward",
                    back_forward_extended_window_command(back_forward),
                )
            )
        add_next_action(
            actions,
            {
                "id": "run_or_collect_mt5_back_forward",
                "priority": 30,
                "area": "mt5_back_forward",
                "summary": "Run MT5 backtest/forward test, or import manual Strategy Tester results with collect-only.",
                "reasons": [
                    reason
                    for reason in reasons
                    if is_back_forward_reason(reason)
                ],
                "commands": commands,
                "manual_steps": manual_steps,
            },
        )

    source_time_refresh_reasons = mt5_strategy_source_time_refresh_reasons(reasons)
    if source_time_refresh_reasons:
        missing_labels = reason_values(reasons, "mt5_strategy_candidate_source_time_missing")
        mismatch_labels = reason_values(reasons, "mt5_strategy_candidate_source_time_mismatch")
        stale_file_labels = reason_values(reasons, "mt5_strategy_candidate_source_time_files_stale")
        missing_file_labels = reason_values(reasons, "mt5_strategy_candidate_source_time_files_missing")
        strategy_analysis = artifact_by_name(artifacts, "mt5_strategy_tester_analysis")
        source_time_counts = (
            strategy_analysis.get("strategy_tester_analysis_source_time_status_counts")
            if isinstance(strategy_analysis.get("strategy_tester_analysis_source_time_status_counts"), dict)
            else {}
        )
        source_file_counts = (
            strategy_analysis.get("strategy_tester_analysis_source_file_status_counts")
            if isinstance(strategy_analysis.get("strategy_tester_analysis_source_file_status_counts"), dict)
            else {}
        )
        source_file_issue_labels = (
            strategy_analysis.get("strategy_tester_analysis_source_file_issue_labels")
            if isinstance(strategy_analysis.get("strategy_tester_analysis_source_file_issue_labels"), list)
            else []
        )
        source_file_issue_candidate_labels = (
            strategy_analysis.get("strategy_tester_analysis_source_file_issue_candidate_labels")
            if isinstance(
                strategy_analysis.get("strategy_tester_analysis_source_file_issue_candidate_labels"),
                list,
            )
            else []
        )
        source_time_refresh_issue_labels = (
            strategy_analysis.get("strategy_tester_analysis_source_time_refresh_issue_labels")
            if isinstance(
                strategy_analysis.get("strategy_tester_analysis_source_time_refresh_issue_labels"),
                list,
            )
            else []
        )
        source_time_refresh_candidate_issue_labels = (
            strategy_analysis.get(
                "strategy_tester_analysis_source_time_refresh_candidate_issue_labels"
            )
            if isinstance(
                strategy_analysis.get(
                    "strategy_tester_analysis_source_time_refresh_candidate_issue_labels"
                ),
                list,
            )
            else []
        )
        manual_steps = [
            "Do not adopt candidate MT5 optimization reports until source-time diagnostics cover the expected test range.",
            "Open runtime/latest_mt5_strategy_tester_analysis.md and check the Optimization Evidence source time columns.",
            "For source-file stale/missing cases, check the Optimization Source File Issues table for Agent CSV size/mtime drift.",
            "Regenerate or rerun the optimization-inclusive manual Strategy Tester queue, then collect with --refresh-post-collect-analysis.",
        ]
        if missing_labels:
            manual_steps.append("Missing source-time candidate labels: " + ", ".join(missing_labels))
        if mismatch_labels:
            manual_steps.append("Mismatched source-time candidate labels: " + ", ".join(mismatch_labels))
        if stale_file_labels:
            manual_steps.append("Stale source-file candidate labels: " + ", ".join(stale_file_labels))
        if missing_file_labels:
            manual_steps.append("Missing source-file candidate labels: " + ", ".join(missing_file_labels))
        if source_time_static_configs:
            manual_steps.append(
                "Additional static Strategy Tester configs for source-file refresh: "
                + ", ".join(source_time_static_configs)
            )
        if source_time_static_candidate_labels:
            manual_steps.append(
                "Additional Strategy Tester candidate labels for source-file refresh: "
                + ", ".join(source_time_static_candidate_labels)
            )
            manual_steps.append(
                "Static candidate labels use their queue-defined Dates/Forward settings; "
                "annual labels use runner_execute date overrides such as "
                "2025.01.01 -> 2025.12.31, ForwardMode=3."
            )
        if source_time_counts:
            manual_steps.append(
                "Current source-time status counts: "
                + ", ".join(f"{key}={value}" for key, value in sorted(source_time_counts.items()))
            )
        if source_file_counts:
            manual_steps.append(
                "Current source-file status counts: "
                + ", ".join(f"{key}={value}" for key, value in sorted(source_file_counts.items()))
            )
        if source_file_issue_candidate_labels:
            manual_steps.append(
                "Candidate reports with source-file issues: "
                + ", ".join(str(label) for label in source_file_issue_candidate_labels)
            )
        if source_file_issue_labels:
            manual_steps.append(
                "All reports with source-file issues: "
                + ", ".join(str(label) for label in source_file_issue_labels)
            )
        if source_time_refresh_issue_labels:
            manual_steps.append(
                "Strategy Tester Analysis source-time refresh plan labels: "
                + ", ".join(str(label) for label in source_time_refresh_issue_labels)
            )
        if source_time_refresh_candidate_issue_labels:
            manual_steps.append(
                "Strategy Tester Analysis candidate refresh plan labels: "
                + ", ".join(str(label) for label in source_time_refresh_candidate_issue_labels)
            )
        buy_gap_labels = mt5_strategy_buy_gap_static_candidate_labels(strategy_analysis)
        if buy_gap_labels:
            manual_steps.append(
                "BUY Candidate Gap diagnostic labels: "
                + ", ".join(str(label) for label in buy_gap_labels)
            )
        buy_gap_refresh_queue_command = str(
            strategy_analysis.get(
                "strategy_tester_analysis_buy_candidate_gap_refresh_queue_command_text"
            )
            or ""
        )
        if buy_gap_refresh_queue_command:
            manual_steps.append(
                "BUY Candidate Gap refresh queue command: " + buy_gap_refresh_queue_command
            )
        if source_time_static_candidate_labels or source_time_static_configs:
            manual_steps.append(
                "Coverage combined refresh queue command: "
                + refresh_manual_test_queue_with_optimization_command
            )
        append_source_time_optimization_queue_steps(
            manual_steps,
            queue=manual_queue_with_optimization,
            launch=manual_queue_launch_with_optimization,
            collect=manual_collect_with_optimization,
        )
        refresh_queue_command = str(
            strategy_analysis.get("strategy_tester_analysis_source_time_refresh_queue_command_text")
            or ""
        )
        if refresh_queue_command:
            manual_steps.append(
                "Strategy Tester Analysis source-time-only refresh queue command: "
                + refresh_queue_command
            )
        refresh_collect_command = str(
            strategy_analysis.get("strategy_tester_analysis_source_time_refresh_collect_command_text")
            or ""
        )
        if refresh_collect_command:
            manual_steps.append("Strategy Tester Analysis collect + refresh command: " + refresh_collect_command)
        add_next_action(
            actions,
            {
                "id": "refresh_mt5_strategy_source_time_evidence",
                "priority": 32,
                "area": "mt5_optimization",
                "summary": "Refresh MT5 optimization evidence with expected source-time diagnostics before adoption.",
                "reasons": source_time_refresh_reasons,
                "commands": [
                    command_step(
                        "refresh_manual_test_queue_with_optimization",
                        refresh_manual_test_queue_with_optimization_command,
                    ),
                    command_step(
                        "refresh_manual_operator_packet_with_optimization",
                        refresh_manual_operator_packet_with_optimization_command,
                    ),
                    command_step(
                        "dry_run_manual_queue_launch_next_with_optimization",
                        "python3 methods/swing_eval/analysis/mt5_manual_queue_launch.py "
                        f"--queue {DEFAULT_MT5_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
                        f"--output-json {DEFAULT_MT5_MANUAL_QUEUE_LAUNCH_WITH_OPTIMIZATION} "
                        "--output-md runtime/latest_mt5_manual_queue_launch_with_optimization.md",
                    ),
                    command_step(
                        "dry_run_manual_queue_collect_ready_with_optimization",
                        "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                        f"--queue {DEFAULT_MT5_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
                        f"--output-json {DEFAULT_MT5_MANUAL_COLLECT_WITH_OPTIMIZATION} "
                        "--output-md runtime/latest_mt5_manual_collect_with_optimization.md",
                    ),
                    command_step(
                        "watch_manual_auto_collect_with_optimization_once",
                        watch_manual_auto_collect_with_optimization_command,
                    ),
                    command_step(
                        "execute_ready_manual_auto_collect_with_optimization_once",
                        execute_ready_manual_auto_collect_with_optimization_command,
                    ),
                    command_step(
                        "execute_collect_with_optimization_and_refresh_full_analysis",
                        "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                        f"--queue {DEFAULT_MT5_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
                        "--execute --refresh-post-collect-analysis "
                        f"--output-json {DEFAULT_MT5_MANUAL_COLLECT_WITH_OPTIMIZATION} "
                        "--output-md runtime/latest_mt5_manual_collect_with_optimization.md",
                    ),
                    command_step(
                        "execute_collect_with_optimization_and_refresh_analysis",
                        "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                        f"--queue {DEFAULT_MT5_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
                        "--execute --refresh-strategy-tester-analysis "
                        f"--output-json {DEFAULT_MT5_MANUAL_COLLECT_WITH_OPTIMIZATION} "
                        "--output-md runtime/latest_mt5_manual_collect_with_optimization.md",
                    ),
                    command_step(
                        "refresh_strategy_tester_analysis",
                        "python3 methods/swing_eval/analysis/mt5_strategy_tester_analysis.py "
                        "--output-json runtime/latest_mt5_strategy_tester_analysis.json "
                        "--output-md runtime/latest_mt5_strategy_tester_analysis.md",
                    ),
                    command_step(
                        "refresh_spec_coverage_after_source_time",
                        "python3 methods/swing_eval/analysis/spec_coverage.py --output-json runtime/latest_spec_coverage.json "
                        "--output-md runtime/latest_spec_coverage.md",
                    ),
                ],
                "manual_steps": manual_steps,
            },
        )

    buy_candidate_gap_reasons = mt5_strategy_buy_candidate_gap_reasons(reasons)
    if buy_candidate_gap_reasons:
        strategy_analysis = artifact_by_name(artifacts, "mt5_strategy_tester_analysis")
        buy_gap_labels = mt5_strategy_buy_gap_static_candidate_labels(strategy_analysis)
        buy_gap_status = str(
            strategy_analysis.get("strategy_tester_analysis_buy_candidate_gap_status") or ""
        )
        buy_gap_refresh_queue_command = str(
            strategy_analysis.get(
                "strategy_tester_analysis_buy_candidate_gap_refresh_queue_command_text"
            )
            or ""
        )
        manual_steps = [
            "BUY side has no adopted MT5 optimization candidate yet; keep BUY diagnostics separate from SELL adoption evidence.",
            f"BUY candidate gap status: {buy_gap_status or 'unknown'}",
        ]
        if buy_gap_labels:
            manual_steps.append("BUY diagnostic labels: " + ", ".join(buy_gap_labels))
        else:
            manual_steps.append("BUY diagnostic labels are missing; refresh Strategy Tester Analysis before rerunning the queue.")
        manual_steps.append(
            "Refresh the optimization-inclusive queue, run the BUY diagnostic rows in MT5 Strategy Tester, then collect with full analysis refresh."
        )
        if buy_gap_refresh_queue_command:
            manual_steps.append("Strategy Tester Analysis BUY refresh queue command: " + buy_gap_refresh_queue_command)
        manual_steps.append(
            "Coverage combined refresh queue command: "
            + refresh_manual_test_queue_with_optimization_command
        )
        if manual_queue_with_optimization.get("exists"):
            manual_steps.append(
                "BUY diagnostic queue state: "
                f"status={manual_queue_with_optimization.get('status', '')}, "
                f"entries={manual_queue_with_optimization.get('entry_count', '')}, "
                f"steps={manual_queue_with_optimization.get('step_count', '')}, "
                f"waiting={manual_queue_with_optimization.get('waiting_count', '')}, "
                f"ready={manual_queue_with_optimization.get('ready_to_collect_count', '')}, "
                "next="
                f"{manual_queue_with_optimization.get('manual_queue_operator_handoff_next_queue_id', '')}/"
                f"{manual_queue_with_optimization.get('manual_queue_operator_handoff_next_step_label', '')}"
            )
        if manual_queue_launch_with_optimization.get("exists"):
            manual_steps.append(
                "BUY diagnostic launch state: "
                f"status={manual_queue_launch_with_optimization.get('status', '')}, "
                f"next_action={manual_queue_launch_with_optimization.get('next_action', '')}, "
                f"selected={manual_queue_launch_with_optimization.get('selected_queue_id', '')}/"
                f"{manual_queue_launch_with_optimization.get('selected_step_label', '')}, "
                f"blocked={manual_queue_launch_with_optimization.get('blocked', '')}, "
                "blockers="
                f"{compact_status_value(manual_queue_launch_with_optimization.get('blocked_reasons', []))}"
            )
        if manual_collect_with_optimization.get("exists"):
            manual_steps.append(
                "BUY diagnostic collect state: "
                f"status={manual_collect_with_optimization.get('status', '')}, "
                f"selected={manual_collect_with_optimization.get('selected_count', '')}, "
                f"ready={manual_collect_with_optimization.get('ready_entry_count', '')}, "
                f"waiting={manual_collect_with_optimization.get('waiting_count', '')}, "
                f"invalid={manual_collect_with_optimization.get('invalid_count', '')}"
            )
        add_next_action(
            actions,
            {
                "id": "refresh_mt5_buy_candidate_gap_evidence",
                "priority": 33,
                "area": "mt5_optimization",
                "summary": "Run BUY-side MT5 diagnostic candidates so adoption is not SELL-only.",
                "reasons": buy_candidate_gap_reasons,
                "commands": [
                    command_step(
                        "refresh_manual_test_queue_with_optimization",
                        refresh_manual_test_queue_with_optimization_command,
                    ),
                    command_step(
                        "refresh_manual_operator_packet_with_optimization",
                        refresh_manual_operator_packet_with_optimization_command,
                    ),
                    command_step(
                        "dry_run_manual_queue_launch_next_with_optimization",
                        "python3 methods/swing_eval/analysis/mt5_manual_queue_launch.py "
                        f"--queue {DEFAULT_MT5_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
                        f"--output-json {DEFAULT_MT5_MANUAL_QUEUE_LAUNCH_WITH_OPTIMIZATION} "
                        "--output-md runtime/latest_mt5_manual_queue_launch_with_optimization.md",
                    ),
                    command_step(
                        "dry_run_manual_queue_collect_ready_with_optimization",
                        "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                        f"--queue {DEFAULT_MT5_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
                        f"--output-json {DEFAULT_MT5_MANUAL_COLLECT_WITH_OPTIMIZATION} "
                        "--output-md runtime/latest_mt5_manual_collect_with_optimization.md",
                    ),
                    command_step(
                        "watch_manual_auto_collect_with_optimization_once",
                        watch_manual_auto_collect_with_optimization_command,
                    ),
                    command_step(
                        "execute_ready_manual_auto_collect_with_optimization_once",
                        execute_ready_manual_auto_collect_with_optimization_command,
                    ),
                    command_step(
                        "execute_collect_with_optimization_and_refresh_full_analysis",
                        "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                        f"--queue {DEFAULT_MT5_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
                        "--execute --refresh-post-collect-analysis "
                        f"--output-json {DEFAULT_MT5_MANUAL_COLLECT_WITH_OPTIMIZATION} "
                        "--output-md runtime/latest_mt5_manual_collect_with_optimization.md",
                    ),
                    command_step(
                        "refresh_strategy_tester_analysis",
                        "python3 methods/swing_eval/analysis/mt5_strategy_tester_analysis.py "
                        "--output-json runtime/latest_mt5_strategy_tester_analysis.json "
                        "--output-md runtime/latest_mt5_strategy_tester_analysis.md",
                    ),
                    command_step(
                        "refresh_spec_coverage_after_buy_gap",
                        "python3 methods/swing_eval/analysis/spec_coverage.py --output-json runtime/latest_spec_coverage.json "
                        "--output-md runtime/latest_spec_coverage.md",
                    ),
                ],
                "manual_steps": manual_steps,
            },
        )

    next_action_run = artifact_by_name(artifacts, "mt5_next_action_run")
    runner = status.get("next_action_runner") if isinstance(status.get("next_action_runner"), dict) else {}
    if not runner and isinstance(next_action_run.get("execution_hints"), dict):
        runner = {
            **next_action_run["execution_hints"],
            "target": next_action_run.get("target", ""),
            "focus_side": next_action_run.get("focus_side", ""),
            "manual_collect_only_command_text": next_action_run.get("manual_collect_only_command_text", ""),
            "manual_run_start_after": next_action_run.get("manual_run_start_after", ""),
            "manual_step_count": next_action_run.get("manual_step_count", ""),
            "manual_steps": next_action_run.get("manual_steps", []),
        }
    runner_entry = manual_queue_entry_for_next_action_summary(runner, artifacts)
    if runner_entry:
        apply_manual_queue_collect_override_to_next_action(runner, runner_entry)
    for side in ("buy", "sell"):
        score_reasons = [
            reason
            for reason in reasons
            if reason.startswith(f"score_weight_search_{side}_rr4_")
            or reason.startswith(f"score_weight_set_{side}_rr4_")
        ]
        if not score_reasons:
            continue
        focus_side = str(runner.get("focus_side") or "")
        target = str(runner.get("target") or "")
        commands: list[dict[str, str]] = []
        manual_steps: list[str] = []
        side_stale_reasons: list[str] = []
        sample_collection_source: dict[str, Any] = {}
        score_search = artifact_by_name(artifacts, f"score_weight_search_{side}_rr4")
        score_set = artifact_by_name(artifacts, f"score_weight_set_{side}_rr4")
        history_status_command = str(
            score_set.get("score_weight_set_follow_up_history_status_command") or ""
        )
        if history_status_command:
            commands.append(
                command_step("check_history_status_before_score_weight_sample_collection", history_status_command)
            )
        if target == "score_weight_sample_collection" and focus_side == side:
            sample_collection_source = runner
            if runner.get("execute_command_text"):
                commands.append(command_step("execute_sample_collection", str(runner["execute_command_text"])))
            collect_command = runner.get("manual_collect_only_command_text") or runner.get("collect_only_command_text")
            if collect_command:
                commands.append(command_step("collect_manual_sample_collection", str(collect_command)))
            manual_steps.append(
                "Use runtime/latest_mt5_next_action_run.md Manual Strategy Tester Checklist before collect-only."
            )
            if runner.get("manual_run_start_after"):
                manual_steps.append(f"Manual run start after: {runner.get('manual_run_start_after')}")
            steps = runner.get("manual_steps") if isinstance(runner.get("manual_steps"), list) else []
            if steps:
                step = steps[0] if isinstance(steps[0], dict) else {}
                if step:
                    manual_steps.append(
                        "MT5 step: "
                        f"Expert={step.get('expert', '')}, Symbol={step.get('symbol', '')}, "
                        f"Period={step.get('period', '')}, Forward={step.get('forward_label', '')}, "
                        f"Inputs={step.get('expert_parameters', '')}, Report={step.get('report_name', '')}"
                    )
                    append_score_sample_collection_mt5_details(manual_steps, runner, step)
            append_manual_collect_readiness_steps(manual_steps, runner)
            summary = f"Collect {side.upper()} score-weight diagnostic samples on MT5 before re-running score fit."
        else:
            side_runner_json = f"runtime/latest_mt5_next_action_run_{side}.json"
            side_runner_md = f"runtime/latest_mt5_next_action_run_{side}.md"
            side_runner = next_action_runner_summary(load_json_if_present(workspace / side_runner_json))
            side_runner_entry = manual_queue_entry_for_next_action_summary(
                side_runner,
                artifacts,
                source_path=side_runner_json,
            )
            if side_runner_entry:
                apply_manual_queue_collect_override_to_next_action(side_runner, side_runner_entry)
            side_target = str(side_runner.get("target") or "")
            side_focus = str(side_runner.get("focus_side") or "")
            side_stale_reasons = side_runner_stale_reasons(side_runner, gate)
            if side_target == "score_weight_sample_collection" and side_focus == side and not side_stale_reasons:
                sample_collection_source = side_runner
                if side_runner.get("execute_command_text"):
                    commands.append(
                        command_step("execute_side_sample_collection", str(side_runner["execute_command_text"]))
                    )
                collect_command = (
                    side_runner.get("manual_collect_only_command_text")
                    or side_runner.get("collect_only_command_text")
                )
                if collect_command:
                    commands.append(command_step("collect_manual_side_sample_collection", str(collect_command)))
                manual_steps.append(
                    f"Use {side_runner_md} Manual Strategy Tester Checklist before collect-only."
                )
                if side_runner.get("manual_run_start_after"):
                    manual_steps.append(f"Manual run start after: {side_runner.get('manual_run_start_after')}")
                steps = side_runner.get("manual_steps") if isinstance(side_runner.get("manual_steps"), list) else []
                if steps:
                    step = steps[0] if isinstance(steps[0], dict) else {}
                    if step:
                        manual_steps.append(
                            "MT5 step: "
                            f"Expert={step.get('expert', '')}, Symbol={step.get('symbol', '')}, "
                            f"Period={step.get('period', '')}, Forward={step.get('forward_label', '')}, "
                            f"Inputs={step.get('expert_parameters', '')}, Report={step.get('report_name', '')}"
                        )
                        append_score_sample_collection_mt5_details(manual_steps, side_runner, step)
                append_manual_collect_readiness_steps(manual_steps, side_runner)
                summary = f"Collect {side.upper()} score-weight diagnostic samples on MT5 before re-running score fit."
            else:
                commands.append(
                    command_step(
                        "refresh_next_action_runner",
                        "python3 methods/swing_eval/analysis/mt5_next_action_run.py --target score_weight_sample_collection "
                        f"--focus-side {side} "
                        f"--output-json {side_runner_json} "
                        f"--output-md {side_runner_md}",
                    )
                )
                summary = f"Prepare the {side.upper()} score-weight sample-collection runner and manual MT5 checklist."
                if side_stale_reasons:
                    manual_steps.append(
                        f"Side-specific {side.upper()} sample-collection runner is stale: "
                        + "; ".join(side_stale_reasons)
                    )
                    if side_runner.get("generated_at"):
                        manual_steps.append(f"Runner promotion generated at: {side_runner.get('generated_at')}")
                    if gate.get("generated_at"):
                        manual_steps.append(f"Current Promotion Gate generated at: {gate.get('generated_at')}")
                    manual_steps.append(
                        f"Regenerate {side_runner_md} from the current Promotion Gate before using its MT5 checklist."
                    )
                elif target == "score_weight_sample_collection" and focus_side:
                    manual_steps.append(
                        f"Current canonical sample-collection runner is focused on {focus_side.upper()}; "
                        f"use the side-specific output {side_runner_md} to inspect {side.upper()} without overwriting it."
                    )
                    if mt5_validation_blocked_by_bridge:
                        append_bridge_standalone_tester_note(manual_steps, bridge_recovery)
                else:
                    manual_steps.append(
                        f"Run the refresh command to generate {side_runner_md}, then follow its Manual Strategy Tester Checklist."
                    )
                    if mt5_validation_blocked_by_bridge:
                        append_bridge_standalone_tester_note(manual_steps, bridge_recovery)
        append_score_weight_failure_steps(
            manual_steps,
            score_search=score_search,
            score_set=score_set,
        )
        if sample_collection_source and mt5_validation_blocked_by_bridge:
            append_bridge_standalone_tester_note(manual_steps, bridge_recovery)
        add_next_action(
            actions,
            {
                "id": f"score_weight_follow_up_{side}",
                "priority": 40 if side == "sell" else 45,
                "area": "score_weight",
                "side": side,
                "summary": summary,
                "reasons": score_reasons
                + (
                    [f"side_next_action_runner_{side}_stale:{','.join(side_stale_reasons)}"]
                    if side_stale_reasons
                    else []
                ),
                "commands": commands,
                "manual_steps": manual_steps,
            },
        )

    promotion_gate_stale_dependencies = reason_values(reasons, "promotion_gate_stale_vs_dependencies")
    if reason_present(reasons, "promotion_gate_not_ready") or promotion_gate_stale_dependencies:
        manual_steps: list[str] = []
        if promotion_gate_stale_dependencies:
            manual_steps.append(
                "Promotion Gate is older than evidence artifacts: "
                + ", ".join(promotion_gate_stale_dependencies)
            )
        add_next_action(
            actions,
            {
                "id": "rerun_promotion_gate_after_evidence",
                "priority": 90,
                "area": "promotion_gate",
                "summary": "Re-run Promotion Gate after history, MT5 back/forward, and score-weight evidence are refreshed.",
                "reasons": [
                    reason
                    for reason in reasons
                    if reason.startswith("promotion_gate_not_ready:")
                    or reason.startswith("promotion_gate_stale_vs_dependencies:")
                ],
                "commands": [
                    command_step(
                        "refresh_promotion_gate",
                        "python3 methods/swing_eval/analysis/promotion_gate.py --output-json runtime/latest_promotion_gate.json "
                        "--output-md runtime/latest_promotion_gate.md",
                    )
                ],
                "manual_steps": manual_steps,
            },
        )

    return sorted(actions, key=lambda item: (int(item.get("priority") or 0), str(item.get("id") or "")))


def completion_reasons(
    *,
    components: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    mql5_artifacts: list[dict[str, Any]] | None = None,
) -> list[str]:
    reasons: list[str] = []
    mql5_rows = mql5_artifacts or []
    missing_components = [row["expected_path"] for row in components if row.get("exists") is not True]
    unreferenced_components = [
        row["expected_path"]
        for row in components
        if row.get("exists") is True and int(row.get("test_reference_count") or 0) <= 0
    ]
    missing_artifacts = [row["path"] for row in artifacts if row.get("exists") is not True]
    missing_mql5_artifacts = [row["path"] for row in mql5_rows if row.get("exists") is not True]
    unreferenced_mql5_artifacts = [
        row["path"]
        for row in mql5_rows
        if row.get("exists") is True and int(row.get("test_reference_count") or 0) <= 0
    ]
    if missing_components:
        reasons.append("missing_spec_components:" + ",".join(missing_components))
    if unreferenced_components:
        reasons.append("component_test_reference_missing:" + ",".join(unreferenced_components))
    if missing_mql5_artifacts:
        reasons.append("missing_mql5_artifacts:" + ",".join(missing_mql5_artifacts))
    if unreferenced_mql5_artifacts:
        reasons.append("mql5_artifact_test_reference_missing:" + ",".join(unreferenced_mql5_artifacts))
    for row in mql5_rows:
        missing_markers = row.get("missing_markers") if isinstance(row.get("missing_markers"), list) else []
        if row.get("exists") is True and missing_markers:
            reasons.append(
                f"mql5_artifact_markers_missing:{row.get('name', '')}="
                + ",".join(str(marker) for marker in missing_markers)
            )
    if missing_artifacts:
        reasons.append("missing_runtime_artifacts:" + ",".join(missing_artifacts))
    stale_artifacts = [row["name"] for row in artifacts if row.get("exists") is True and row.get("fresh") is False]
    if stale_artifacts:
        reasons.append("stale_runtime_artifacts:" + ",".join(stale_artifacts))
    history_status = artifact_by_name(artifacts, "history_status")
    history_artifact = artifact_by_name(artifacts, "history")
    history_data_source = history_status if history_status.get("exists") is True else history_artifact
    if history_data_source.get("exists") is True and history_data_source.get("history_data_fresh") is False:
        details: list[str] = []
        if history_data_source.get("history_server_time"):
            details.append(
                f"server_time_age_seconds={history_data_source.get('history_server_time_age_seconds')}"
            )
        if history_data_source.get("history_m1_last_time"):
            details.append(
                f"m1_last_time_age_seconds={history_data_source.get('history_m1_last_time_age_seconds')}"
            )
        suffix = ";".join(details) if details else "time_unknown"
        reasons.append(f"history_data_stale:{history_data_source.get('name', 'history')}:{suffix}")
    compile_status = artifact_by_name(artifacts, "mt5_compile_status")
    if compile_status.get("exists") is True:
        for key in (
            "all_sources_synced",
            "all_compiled_fresh",
            "all_tester_sets_synced",
            "all_tester_configs_synced",
            "all_required_tester_config_references_ready",
        ):
            if compile_status.get(key) is False:
                reasons.append(f"mt5_compile_status_not_ready:{key}")
    newer_mql5_artifacts = mql5_artifacts_newer_than_compile_status(artifacts, mql5_rows)
    if newer_mql5_artifacts:
        reasons.append("mt5_compile_status_stale_vs_mql5_artifacts:" + ",".join(newer_mql5_artifacts))
    promotion_gate_stale_dependencies = promotion_gate_stale_dependency_names(artifacts)
    if promotion_gate_stale_dependencies:
        reasons.append("promotion_gate_stale_vs_dependencies:" + ",".join(promotion_gate_stale_dependencies))
    strategy_tester_analysis_stale_dependencies = strategy_tester_analysis_stale_dependency_names(artifacts)
    if strategy_tester_analysis_stale_dependencies:
        reasons.append(
            "mt5_strategy_tester_analysis_stale_vs_dependencies:"
            + ",".join(strategy_tester_analysis_stale_dependencies)
        )

    bridge = artifact_by_name(artifacts, "bridge_status")
    bridge_watch = artifact_by_name(artifacts, "bridge_status_watch")
    runtime_watchers = artifact_by_name(artifacts, "runtime_watchers")
    if runtime_watchers.get("exists") is True:
        if runtime_watchers.get("ok") is False:
            reasons.append("runtime_watchers_not_ready:ok_false")
        stale_watcher_count = optional_int(runtime_watchers.get("stale_watcher_count"))
        if stale_watcher_count and stale_watcher_count > 0:
            reasons.append(f"runtime_watchers_stale_heartbeats:{stale_watcher_count}")
        action_required_watcher_count = optional_int(runtime_watchers.get("action_required_watcher_count"))
        if action_required_watcher_count and action_required_watcher_count > 0:
            reasons.append(f"runtime_watchers_action_required:{action_required_watcher_count}")
    bridge_status = str(bridge.get("operational_status") or "")
    if bridge.get("exists") is not True:
        reasons.append("bridge_status_missing")
    elif bridge_status and bridge_status != "ready":
        reasons.append(f"bridge_status_not_ready:{bridge_status}")
    if bridge_watch.get("exists") is True and not bridge_watch.get("bridge_log_activity_status"):
        reasons.append("bridge_status_watch_missing_activity")
    bridge_activity = str(bridge.get("bridge_log_activity_status") or "")
    if bridge_activity in {
        "log_empty",
        "no_ea_post_seen",
        "ea_post_seen_no_snapshot_post",
        "ea_post_recent_snapshot_stale",
        "ea_post_stale",
    }:
        age = bridge.get("bridge_log_last_ea_post_age_seconds")
        if age in (None, ""):
            reasons.append(f"bridge_ea_post_activity:{bridge_activity}")
        else:
            reasons.append(f"bridge_ea_post_activity:{bridge_activity}:{age}s")

    gate = artifact_by_name(artifacts, "promotion_gate")
    decision = str(gate.get("decision") or "").lower()
    if decision not in PROMOTION_READY_DECISIONS:
        reasons.append(f"promotion_gate_not_ready:{gate.get('decision', '')}")

    status = artifact_by_name(artifacts, "mt5_tester_status")
    if (
        status.get("operational_status") not in ("ready", "ok", "latest_run_ok")
        and status.get("ready_for_tester_launch") is not True
        and not mt5_status_manual_strategy_tester_handoff_active(status)
    ):
        reasons.append(f"mt5_tester_status_not_ready:{status.get('operational_status', '')}")
    if status.get("status_watch_compatible") is not True:
        reasons.append("mt5_status_watch_not_compatible")
    if status.get("next_action_runner_current_for_execution") is False:
        stale_reason = str(status.get("next_action_runner_gate_stale_reason") or "not_current")
        reasons.append(f"mt5_next_action_runner_not_current:{stale_reason}")
    blocking_prior_action_count = optional_int(status.get("next_action_runner_blocking_prior_action_count"))
    if blocking_prior_action_count is not None and blocking_prior_action_count > 0:
        reasons.append(f"mt5_next_action_runner_blocked_by_prior_actions:{blocking_prior_action_count}")
    for artifact_name in ("mt5_next_action_run", "mt5_next_action_run_buy"):
        runner_artifact = artifact_by_name(artifacts, artifact_name)
        runner_stale_reasons = next_action_runner_artifact_stale_reasons(runner_artifact, gate)
        if runner_stale_reasons:
            reasons.append(
                f"mt5_next_action_runner_artifact_not_current:{artifact_name}:"
                + ";".join(runner_stale_reasons)
            )

    manual_queue = artifact_by_name(artifacts, "mt5_manual_test_queue")
    manual_queue_status = str(manual_queue.get("status") or "")
    manual_queue_stale_count = optional_int(manual_queue.get("stale_entry_count")) or 0
    if manual_queue_status == "stale_runner_artifacts" or manual_queue_stale_count > 0:
        reasons.append(
            "mt5_manual_test_queue_stale_runner_artifacts:"
            f"{manual_queue_status or 'unknown'}:{manual_queue_stale_count}"
        )

    back_forward = artifact_by_name(artifacts, "mt5_back_forward_run")
    evidence_state = str(back_forward.get("evidence_state") or "")
    if evidence_state not in BACK_FORWARD_COMPLETE_STATES:
        reasons.append(back_forward_incomplete_reason(evidence_state))
    if back_forward.get("manual_prerequisites_ready") is False:
        prerequisite_reasons = back_forward.get("manual_prerequisites_reasons")
        if isinstance(prerequisite_reasons, list) and prerequisite_reasons:
            reason_text = ";".join(str(reason) for reason in prerequisite_reasons)
        else:
            reason_text = "unknown"
        reasons.append(f"mt5_back_forward_manual_prerequisites_not_ready:{reason_text}")
    if back_forward.get("back_forward_plan_validation_ready") is False:
        validation_reasons = back_forward.get("back_forward_plan_validation_reasons")
        if isinstance(validation_reasons, list) and validation_reasons:
            reason_text = ";".join(str(reason) for reason in validation_reasons)
        else:
            reason_text = str(back_forward.get("back_forward_plan_validation_status") or "unknown")
        reasons.append(f"mt5_back_forward_plan_validation_not_ready:{reason_text}")

    strategy_analysis = artifact_by_name(artifacts, "mt5_strategy_tester_analysis")
    strategy_blockers = (
        strategy_analysis.get("strategy_tester_analysis_blockers")
        if isinstance(strategy_analysis.get("strategy_tester_analysis_blockers"), list)
        else []
    )
    source_time_missing = [
        str(blocker).split(":", 1)[1]
        for blocker in strategy_blockers
        if str(blocker).startswith("candidate_source_time_missing:")
    ]
    source_time_mismatch = [
        str(blocker).split(":", 1)[1]
        for blocker in strategy_blockers
        if str(blocker).startswith("candidate_source_time_mismatch:")
    ]
    source_time_files_stale = [
        str(blocker).split(":", 1)[1]
        for blocker in strategy_blockers
        if str(blocker).startswith("candidate_source_time_files_stale:")
    ]
    source_time_files_missing = [
        str(blocker).split(":", 1)[1]
        for blocker in strategy_blockers
        if str(blocker).startswith("candidate_source_time_files_missing:")
    ]
    if source_time_missing:
        reasons.append("mt5_strategy_candidate_source_time_missing:" + ",".join(source_time_missing))
    if source_time_mismatch:
        reasons.append("mt5_strategy_candidate_source_time_mismatch:" + ",".join(source_time_mismatch))
    if source_time_files_stale:
        reasons.append("mt5_strategy_candidate_source_time_files_stale:" + ",".join(source_time_files_stale))
    if source_time_files_missing:
        reasons.append("mt5_strategy_candidate_source_time_files_missing:" + ",".join(source_time_files_missing))
    buy_candidate_gap_status = str(
        strategy_analysis.get("strategy_tester_analysis_buy_candidate_gap_status") or ""
    )
    if buy_candidate_gap_status == "needs_buy_diagnostic":
        buy_gap_labels = strategy_analysis.get(
            "strategy_tester_analysis_buy_candidate_gap_diagnostic_labels"
        )
        label_suffix = ""
        if isinstance(buy_gap_labels, list) and buy_gap_labels:
            label_suffix = ":" + ",".join(str(label) for label in buy_gap_labels)
        reasons.append(f"mt5_strategy_buy_candidate_gap:{buy_candidate_gap_status}{label_suffix}")
    back_forward_decision_status = str(
        strategy_analysis.get("strategy_tester_analysis_back_forward_decision_status") or ""
    )
    back_forward_decision_adoptable = strategy_analysis.get(
        "strategy_tester_analysis_back_forward_decision_adoptable"
    )
    if back_forward_decision_status and back_forward_decision_adoptable is False:
        reason = f"mt5_back_forward_decision:{back_forward_decision_status}"
        if reason not in reasons:
            reasons.append(reason)

    for side in ("buy", "sell"):
        score_search_name = f"score_weight_search_{side}_rr4"
        score_search = artifact_by_name(artifacts, score_search_name)
        score_search_status = str(score_search.get("walk_forward_aggregate_status") or "")
        if score_search_status and score_search_status != "walk_forward_candidate_passed":
            reasons.append(f"{score_search_name}_walk_forward_not_passed:{score_search_status}")

        score_set_name = f"score_weight_set_{side}_rr4"
        score_set = artifact_by_name(artifacts, score_set_name)
        if score_set.get("ok") is False or score_set.get("exists") is not True:
            reasons.append(f"{score_set_name}_not_usable")
        elif score_set.get("skipped_write") is True or score_set.get("written") is False:
            reasons.append(
                f"{score_set_name}_not_written:"
                f"{score_set.get('skip_reason') or score_set.get('walk_forward_status') or 'unknown'}"
            )
        elif score_set.get("walk_forward_status") and score_set.get("walk_forward_status") != "walk_forward_candidate_passed":
            reasons.append(f"{score_set_name}_walk_forward_not_passed:{score_set.get('walk_forward_status')}")

    return reasons


def build_spec_coverage(
    *,
    workspace_root: str | Path = ".",
    spec_path: str | Path = DEFAULT_SPEC_PATH,
    max_artifact_age_seconds: int = DEFAULT_MAX_ARTIFACT_AGE_SECONDS,
    max_history_request_pending_seconds: int = DEFAULT_MAX_HISTORY_REQUEST_PENDING_SECONDS,
    max_bridge_snapshot_age_seconds: int = DEFAULT_MAX_BRIDGE_SNAPSHOT_AGE_SECONDS,
    max_history_data_age_seconds: int = DEFAULT_MAX_HISTORY_DATA_AGE_SECONDS,
    now_epoch: float | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    spec = Path(spec_path)
    source = spec if spec.is_absolute() else workspace / spec
    effective_now = time.time() if now_epoch is None else now_epoch
    spec_text = source.read_text(encoding="utf-8")
    components = component_coverage(workspace, parse_spec_components(spec_text))
    mql5_artifacts = mql5_artifact_coverage(workspace)
    phases = parse_phase_completion_conditions(spec_text)
    artifacts = runtime_coverage(
        workspace,
        now_epoch=effective_now,
        max_artifact_age_seconds=max_artifact_age_seconds,
        max_history_data_age_seconds=max_history_data_age_seconds,
    )
    history_request = history_request_state(
        workspace,
        now_epoch=effective_now,
        max_pending_seconds=max_history_request_pending_seconds,
        max_snapshot_age_seconds=max_bridge_snapshot_age_seconds,
    )
    reasons = completion_reasons(components=components, artifacts=artifacts, mql5_artifacts=mql5_artifacts)
    if history_request.get("stale_pending") is True:
        reasons.append(f"history_request_stale_pending:{history_request.get('pending_age_seconds')}s")
    snapshot = history_request.get("bridge_snapshot") if isinstance(history_request.get("bridge_snapshot"), dict) else {}
    if snapshot.get("exists") is True and snapshot.get("fresh") is False:
        reasons.append(f"bridge_snapshot_stale:{snapshot.get('age_seconds')}s")
    next_actions = build_spec_next_actions(
        workspace=workspace,
        artifacts=artifacts,
        reasons=reasons,
        history_request=history_request,
    )
    phase_statuses = build_phase_statuses(phases, reasons)
    phase_current_blockers = build_phase_current_blockers(phase_statuses, next_actions)
    first_phase_blocker = (
        phase_current_blockers[0]
        if phase_current_blockers and isinstance(phase_current_blockers[0], dict)
        else {}
    )
    missing_components = [row for row in components if row.get("exists") is not True]
    unreferenced_components = [
        row for row in components if row.get("exists") is True and int(row.get("test_reference_count") or 0) <= 0
    ]
    missing_mql5_artifacts = [row for row in mql5_artifacts if row.get("exists") is not True]
    unreferenced_mql5_artifacts = [
        row
        for row in mql5_artifacts
        if row.get("exists") is True and int(row.get("test_reference_count") or 0) <= 0
    ]
    mql5_marker_gaps = [
        row
        for row in mql5_artifacts
        if row.get("exists") is True and row.get("markers_ok") is not True
    ]
    return {
        "ok": True,
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "workspace_root": str(workspace),
        "spec_path": str(source),
        "component_count": len(components),
        "missing_component_count": len(missing_components),
        "unreferenced_component_count": len(unreferenced_components),
        "phase_count": len(phases),
        "runtime_artifact_count": len(artifacts),
        "mql5_artifact_count": len(mql5_artifacts),
        "missing_mql5_artifact_count": len(missing_mql5_artifacts),
        "unreferenced_mql5_artifact_count": len(unreferenced_mql5_artifacts),
        "mql5_artifact_marker_gap_count": len(mql5_marker_gaps),
        "max_artifact_age_seconds": max_artifact_age_seconds,
        "max_history_request_pending_seconds": max_history_request_pending_seconds,
        "max_bridge_snapshot_age_seconds": max_bridge_snapshot_age_seconds,
        "max_history_data_age_seconds": max_history_data_age_seconds,
        "goal_completion_proven": not reasons,
        "not_complete_reason_count": len(reasons),
        "not_complete_reasons": reasons,
        "next_action_count": len(next_actions),
        "next_actions": next_actions,
        "phase_statuses": phase_statuses,
        "blocked_phase_count": len(phase_current_blockers),
        "first_blocked_phase": first_phase_blocker.get("name", ""),
        "first_blocked_phase_primary_reason": first_phase_blocker.get("primary_reason", ""),
        "first_blocked_phase_primary_next_action": first_phase_blocker.get(
            "primary_next_action_id", ""
        ),
        "phase_current_blockers": phase_current_blockers,
        "history_request": history_request,
        "components": components,
        "phases": phases,
        "runtime_artifacts": artifacts,
        "mql5_artifacts": mql5_artifacts,
    }


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def compact_status_value(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Swing Evaluation Spec Coverage",
        "",
        f"- Generated at: {payload.get('generated_at', '')}",
        f"- Spec: {payload.get('spec_path', '')}",
        f"- Components: {payload.get('component_count')} total, {payload.get('missing_component_count')} missing, {payload.get('unreferenced_component_count')} without test references",
        f"- MQL5 artifacts: {payload.get('mql5_artifact_count')} total, {payload.get('missing_mql5_artifact_count')} missing, {payload.get('unreferenced_mql5_artifact_count')} without test references, {payload.get('mql5_artifact_marker_gap_count')} marker gaps",
        f"- Runtime artifacts: {payload.get('runtime_artifact_count')}",
        f"- Max artifact age seconds: {payload.get('max_artifact_age_seconds')}",
        f"- Max history request pending seconds: {payload.get('max_history_request_pending_seconds')}",
        f"- Max bridge snapshot age seconds: {payload.get('max_bridge_snapshot_age_seconds')}",
        f"- Max history data age seconds: {payload.get('max_history_data_age_seconds')}",
        f"- Goal completion proven: {payload.get('goal_completion_proven')}",
        f"- Not complete reason count: {payload.get('not_complete_reason_count', len(payload.get('not_complete_reasons', [])) if isinstance(payload.get('not_complete_reasons'), list) else 0)}",
        f"- Next action count: {payload.get('next_action_count', len(payload.get('next_actions', [])) if isinstance(payload.get('next_actions'), list) else 0)}",
        f"- Blocked phase count: {payload.get('blocked_phase_count', '')}",
        f"- First blocked phase: {payload.get('first_blocked_phase', '')}",
        f"- First blocked phase primary reason: {payload.get('first_blocked_phase_primary_reason', '')}",
        f"- First blocked phase primary next action: {payload.get('first_blocked_phase_primary_next_action', '')}",
        "",
        "## Not Complete Reasons",
        "",
    ]
    reasons = payload.get("not_complete_reasons") if isinstance(payload.get("not_complete_reasons"), list) else []
    if reasons:
        lines.extend(f"- {reason}" for reason in reasons)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Next Actions",
            "",
            "| priority | id | area | summary | commands | manual |",
            "|---:|---|---|---|---|---|",
        ]
    )
    next_actions = payload.get("next_actions") if isinstance(payload.get("next_actions"), list) else []
    if next_actions:
        for action in next_actions:
            if not isinstance(action, dict):
                continue
            commands = action.get("commands") if isinstance(action.get("commands"), list) else []
            command_text = "<br>".join(
                f"{command.get('label', '')}: `{command.get('command', '')}`"
                for command in commands
                if isinstance(command, dict)
            )
            manual_steps = action.get("manual_steps") if isinstance(action.get("manual_steps"), list) else []
            manual_text = "<br>".join(str(step) for step in manual_steps)
            lines.append(
                f"| {action.get('priority', '')} | {markdown_cell(action.get('id', ''))} | "
                f"{markdown_cell(action.get('area', ''))} | {markdown_cell(action.get('summary', ''))} | "
                f"{markdown_cell(command_text)} | {markdown_cell(manual_text)} |"
            )
    else:
        lines.append("|  | none |  | No action required. |  |  |")
    history_request = payload.get("history_request") if isinstance(payload.get("history_request"), dict) else {}
    request = history_request.get("request") if isinstance(history_request.get("request"), dict) else {}
    done = history_request.get("done") if isinstance(history_request.get("done"), dict) else {}
    snapshot = (
        history_request.get("bridge_snapshot")
        if isinstance(history_request.get("bridge_snapshot"), dict)
        else {}
    )
    bridge = artifact_by_name(
        [row for row in payload.get("runtime_artifacts", []) if isinstance(row, dict)],
        "bridge_status",
    )
    history_status = artifact_by_name(
        [row for row in payload.get("runtime_artifacts", []) if isinstance(row, dict)],
        "history_status",
    )
    lines.extend(
        [
            "",
            "## History Request",
            "",
            f"- State: {history_request.get('state', '')}",
            f"- Pending: {history_request.get('pending')}",
            f"- Stale pending: {history_request.get('stale_pending')}",
            f"- Pending age seconds: {history_request.get('pending_age_seconds')}",
            f"- Max pending seconds: {history_request.get('max_pending_seconds')}",
            f"- Done matches request: {history_request.get('done_matches_request')}",
            f"- Request: exists={request.get('exists')}, id={request.get('id', '')}, hours={request.get('hours', '')}, status={request.get('status', '')}, modified={request.get('modified_at', '')}",
            f"- Done: exists={done.get('exists')}, id={done.get('id', '')}, hours={done.get('hours', '')}, source_server_time={done.get('source_server_time', '')}, modified={done.get('modified_at', '')}",
            f"- Latest snapshot: exists={snapshot.get('exists')}, fresh={snapshot.get('fresh')}, age_seconds={snapshot.get('age_seconds')}, server_time={snapshot.get('server_time', '')}, modified={snapshot.get('modified_at', '')}",
            f"- History data freshness: fresh={history_status.get('history_data_fresh', '')}, max_age_seconds={history_status.get('max_history_data_age_seconds', '')}, server_time={history_status.get('history_server_time', '')}, server_time_age_seconds={history_status.get('history_server_time_age_seconds', '')}, m1_last_time={history_status.get('history_m1_last_time', '')}, m1_last_time_age_seconds={history_status.get('history_m1_last_time_age_seconds', '')}",
            f"- Bridge log activity: status={bridge.get('bridge_log_activity_status', '')}, ea_post_count={bridge.get('bridge_log_ea_post_count', '')}, last_ea_post={bridge.get('bridge_log_last_ea_post_at', '')}, ea_post_age_seconds={bridge.get('bridge_log_last_ea_post_age_seconds', '')}, last_snapshot_post={bridge.get('bridge_log_last_snapshot_post_at', '')}, snapshot_post_age_seconds={bridge.get('bridge_log_last_snapshot_post_age_seconds', '')}, last_config_get={bridge.get('bridge_log_last_config_get_at', '')}, config_get_age_seconds={bridge.get('bridge_log_last_config_get_age_seconds', '')}",
            f"- Bridge EA attention: required={bridge.get('ea_attention_required', '')}, reason={bridge.get('ea_attention_reason', '')}, mt5_terminal_running={bridge.get('mt5_terminal_running', '')}, terminal_match_count={bridge.get('mt5_terminal_match_count', '')}",
        ]
    )
    lines.extend(
        [
            "",
            "## Components",
            "",
            "| component | exists | test refs | spec line | path |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for row in payload.get("components", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {row.get('name', '')} | {row.get('exists')} | {row.get('test_reference_count', '')} | "
            f"{row.get('line', '')} | {row.get('expected_path', '')} |"
        )
    lines.extend(
        [
            "",
            "## MQL5 Artifacts",
            "",
            "| artifact | exists | test refs | markers | phase | path |",
            "|---|---:|---:|---|---|---|",
        ]
    )
    for row in payload.get("mql5_artifacts", []):
        if not isinstance(row, dict):
            continue
        missing_markers = row.get("missing_markers") if isinstance(row.get("missing_markers"), list) else []
        marker_text = "ok" if row.get("markers_ok") is True else "missing: " + ", ".join(str(item) for item in missing_markers)
        lines.append(
            f"| {row.get('name', '')} | {row.get('exists')} | "
            f"{row.get('test_reference_count', '')} | {markdown_cell(marker_text)} | "
            f"{row.get('phase', '')} | {row.get('path', '')} |"
        )
    lines.extend(
        [
            "",
            "## Runtime Artifacts",
            "",
            "| artifact | exists | fresh | age_seconds | generated | status | path |",
            "|---|---:|---:|---:|---|---|---|",
        ]
    )
    for row in payload.get("runtime_artifacts", []):
        if not isinstance(row, dict):
            continue
        status_parts = []
        for key in (
            "history_data_fresh",
            "max_history_data_age_seconds",
            "history_server_time",
            "history_server_time_age_seconds",
            "history_m1_last_time",
            "history_m1_last_time_age_seconds",
            "ok",
            "status",
            "decision",
            "operational_status",
            "next_action",
            "next_operator_action",
            "next_operator_mode",
            "next_operator_instruction",
            "next_operator_command_text",
            "next_operator_follow_up_command_text",
            "blocking_reasons",
            "blocked",
            "blocked_reasons",
            "selected",
            "selected_queue_id",
            "selected_step_label",
            "selected_step_order",
            "selected_report",
            "selected_forward",
            "selected_step_fingerprint",
            "selected_step_config_fingerprint",
            "selected_step_run_fingerprint",
            "selected_expected_report",
            "selected_expected_report_artifact",
            "launch_command_kind",
            "mark_manual_run_start",
            "manual_run_start_mark_status",
            "manual_run_start_mark_attempted",
            "manual_run_start_after",
            "running_terminal_count",
            "queue_entry_count",
            "queue_total_entry_count",
            "queue_completed_count",
            "queue_completed_entry_count",
            "queue_completed_entry_ids",
            "queue_step_count",
            "queue_ready_to_collect_count",
            "queue_waiting_count",
            "queue_step_report_ready_count",
            "queue_step_waiting_report_count",
            "queue_step_launch_needed_count",
            "ready_for_tester_launch",
            "mt5_operator_summary_manual_queue_status",
            "mt5_operator_summary_manual_queue_next_action",
            "mt5_operator_summary_manual_queue_entries",
            "mt5_operator_summary_manual_queue_steps",
            "mt5_operator_summary_manual_queue_waiting",
            "mt5_operator_summary_manual_queue_step_ready",
            "mt5_operator_summary_manual_queue_launch_needed",
            "mt5_operator_summary_launch_status",
            "mt5_operator_summary_launch_next_action",
            "mt5_operator_summary_launch_kind",
            "mt5_operator_summary_launch_blocked_reasons",
            "mt5_operator_summary_collect_status",
            "mt5_operator_summary_collect_next_action",
            "mt5_operator_summary_collect_selected",
            "mt5_operator_summary_collect_waiting",
            "mt5_operator_summary_next_queue_id",
            "mt5_operator_summary_next_step_label",
            "mt5_operator_summary_next_symbol",
            "mt5_operator_summary_next_period",
            "mt5_operator_summary_next_dates",
            "mt5_operator_summary_next_forward",
            "mt5_operator_summary_next_inputs",
            "mt5_operator_summary_next_report",
            "mt5_operator_summary_next_step_fingerprint",
            "mt5_operator_summary_next_step_config_fingerprint",
            "mt5_operator_summary_next_step_run_fingerprint",
            "mt5_operator_summary_next_expected_report_artifact",
            "mt5_operator_summary_next_step_operator_summary",
            "mt5_operator_summary_next_step_summary",
            "mt5_operator_summary_next_step_collect_filter_summary",
            "mt5_operator_summary_launch_selected_step_fingerprint",
            "mt5_operator_summary_launch_selected_expected_report",
            "mt5_operator_summary_launch_selected_expected_report_artifact",
            "mt5_operator_summary_collect_execute_command_text",
            "mt5_operator_summary_collect_execute_and_refresh_analysis_command_text",
            "mt5_operator_summary_next_action_run_target",
            "mt5_operator_summary_next_action_run_kind",
            "mt5_operator_summary_next_action_run_focus_side",
            "mt5_operator_summary_next_action_run_optimization_mode",
            "mt5_operator_summary_next_action_run_config",
            "mt5_operator_summary_next_action_run_set",
            "mt5_operator_summary_next_action_run_output_set",
            "mt5_operator_summary_next_action_run_current_for_execution",
            "mt5_operator_summary_next_action_run_primary_execution_class",
            "mt5_operator_summary_next_action_run_primary_is_mt5_tester_run",
            "mt5_operator_summary_next_action_run_blocking_prior_action_count",
            "mt5_operator_summary_next_action_run_timeout_seconds",
            "mt5_operator_summary_next_action_run_timeout_minutes",
            "mt5_operator_summary_next_action_run_timeout_note",
            "mt5_operator_summary_next_action_run_timeout_deadline_if_started_now",
            "mt5_operator_summary_next_action_run_optimized_input_count",
            "mt5_operator_summary_next_action_run_estimated_full_factorial_passes",
            "mt5_operator_summary_next_action_run_latest_executed_tester_xml_rows",
            "mt5_operator_summary_next_action_run_primary_planned_outputs",
            "mt5_operator_summary_next_action_run_execute_command_text",
            "mt5_operator_summary_next_action_run_collect_only_command_text",
            "mt5_operator_handoff_state",
            "mt5_operator_handoff_recommended_path",
            "mt5_operator_handoff_manual_strategy_tester_available",
            "mt5_operator_handoff_terminal_running",
            "mt5_operator_handoff_auto_launch_blocked_by_running_terminal",
            "mt5_operator_handoff_auto_launch_blockers",
            "mt5_operator_handoff_next_queue_id",
            "mt5_operator_handoff_next_step_label",
            "mt5_operator_handoff_next_forward",
            "mt5_operator_handoff_next_inputs",
            "mt5_operator_handoff_next_report",
            "mt5_operator_handoff_next_step_operator_summary",
            "mt5_operator_handoff_next_step_summary",
            "mt5_operator_handoff_next_step_collect_filter_summary",
            "mt5_operator_handoff_collect_execute_command_text",
            "mt5_operator_handoff_collect_execute_and_refresh_analysis_command_text",
            "mt5_operator_handoff_collect_execute_and_refresh_full_analysis_command_text",
            "mt5_operator_handoff_bridge_required_for_standalone_tester",
            "mt5_operator_handoff_bridge_ready_for_mt5_validation",
            "mt5_operator_handoff_bridge_status",
            "evidence_state",
            "mt5_strategy_tester_pack_available",
            "mt5_strategy_tester_pack_ready_for_manual_mt5_run",
            "mt5_strategy_tester_pack_status",
            "mt5_strategy_tester_pack_next_action",
            "mt5_strategy_tester_pack_is_back_forward_pair",
            "mt5_strategy_tester_pack_manual_run_start_after",
            "mt5_strategy_tester_pack_collect_ready",
            "mt5_strategy_tester_pack_collect_status",
            "mt5_strategy_tester_pack_step_count",
            "back_forward_plan_validation_ready",
            "back_forward_plan_validation_status",
            "performance_comparison_available",
            "performance_comparison_status",
            "status_watch_compatible",
            "implementation_version",
            "watcher_count",
            "stale_watcher_count",
            "action_required_watcher_count",
            "max_heartbeat_age_seconds",
            "mt5_manual_auto_collect_execute_ready",
            "runtime_watcher_mode_mismatch_details",
            "execute_ready",
            "ready_to_execute",
            "ready_for_collect_execute",
            "selected_count",
            "waiting_count",
            "invalid_count",
            "auto_collect_collect_dry_run_command_text",
            "auto_collect_collect_execute_command_text",
            "auto_collect_dry_run_status",
            "auto_collect_dry_run_selected_count",
            "auto_collect_dry_run_waiting_count",
            "auto_collect_dry_run_invalid_count",
            "auto_collect_queue_launch_refresh_status",
            "auto_collect_queue_launch_refresh_next_action",
            "auto_collect_queue_launch_refresh_blocked",
            "auto_collect_queue_launch_refresh_blocked_reasons",
            "auto_collect_queue_launch_refresh_launch_command_kind",
            "auto_collect_queue_launch_refresh_running_terminal_count",
            "operator_packet_refresh_status",
            "operator_packet_refresh_next_queue_step",
            "operator_packet_refresh_next_operator_action",
            "operator_packet_refresh_next_operator_mode",
            "operator_packet_refresh_next_operator_instruction",
            "operator_packet_refresh_next_operator_command_text",
            "operator_packet_refresh_next_operator_before_mt5_command_text",
            "operator_packet_refresh_next_operator_follow_up_command_text",
            "operator_packet_refresh_auto_launch_command_text",
            "operator_packet_refresh_auto_launch_command_available",
            "operator_packet_refresh_auto_launch_blocked",
            "operator_packet_refresh_auto_launch_blocked_reasons",
            "operator_packet_refresh_auto_launch_note",
            "operator_packet_refresh_manual_run_start_mark_command_text",
            "back_forward_quick_start_status",
            "back_forward_quick_start_step_count",
            "back_forward_quick_start_waiting_step_count",
            "back_forward_quick_start_current_queue_step",
            "back_forward_quick_start_collect_command_text",
            "back_forward_quick_start_auto_launch_blocked",
            "mt5_operator_summary_operator_packet_back_forward_quick_start_status",
            "mt5_operator_summary_operator_packet_back_forward_quick_start_step_count",
            "mt5_operator_summary_operator_packet_back_forward_quick_start_waiting_step_count",
            "mt5_operator_summary_operator_packet_back_forward_quick_start_current_queue_step",
            "mt5_operator_summary_operator_packet_back_forward_quick_start_collect_command_text",
            "auto_collect_operator_packet_manual_run_start_mark_command_text",
            "auto_collect_operator_packet_manual_run_start_mark_command_available",
            "auto_collect_operator_packet_auto_launch_command_text",
            "auto_collect_operator_packet_auto_launch_command_available",
            "auto_collect_operator_packet_auto_launch_blocked",
            "auto_collect_operator_packet_auto_launch_blocked_reasons",
            "auto_collect_operator_packet_auto_launch_note",
            "operator_packet_refresh_step_count",
            "operator_packet_refresh_static_strategy_config_count",
            "operator_packet_refresh_static_strategy_configs",
            "operator_packet_refresh_static_candidate_label_count",
            "operator_packet_refresh_static_candidate_labels",
            "operator_packet_refresh_launch_state",
            "operator_packet_refresh_bridge_status",
            "operator_packet_refresh_bridge_ready_for_mt5_validation",
            "operator_packet_refresh_standalone_strategy_tester_allowed",
            "operator_packet_refresh_bridge_verification_command_count",
            "operator_packet_refresh_bridge_verification_command_labels",
            "operator_packet_refresh_bridge_verification_commands",
            "auto_collect_operator_packet_bridge_verification_command_count",
            "auto_collect_operator_packet_bridge_verification_command_labels",
            "auto_collect_operator_packet_bridge_verification_commands",
            "operator_packet_refresh_strategy_status",
            "operator_packet_refresh_strategy_back_forward_decision_status",
            "operator_packet_refresh_strategy_back_forward_decision_adoptable",
            "operator_packet_refresh_strategy_back_forward_decision_next_action",
            "operator_packet_refresh_strategy_back_forward_decision_collect_command_text",
            "operator_packet_refresh_strategy_back_forward_decision_sample_shortage_recovery_command_text",
            "operator_packet_refresh_strategy_back_forward_decision_sample_shortage_recovery_range_strategy",
            "operator_packet_refresh_strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date",
            "operator_packet_refresh_strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date",
            "operator_packet_refresh_strategy_operator_decision_status",
            "operator_packet_refresh_strategy_operator_decision_verdict",
            "operator_packet_refresh_strategy_operator_decision_adoptable",
            "operator_packet_refresh_strategy_operator_decision_primary_blocker",
            "operator_packet_refresh_strategy_operator_decision_primary_reason",
            "operator_packet_refresh_strategy_operator_decision_next_action",
            "operator_packet_refresh_strategy_operator_decision_summary",
            "operator_packet_refresh_strategy_operator_decision_command_text",
            "operator_packet_refresh_strategy_operator_decision_follow_up_command_text",
            "auto_collect_operator_packet_strategy_back_forward_decision_status",
            "auto_collect_operator_packet_strategy_back_forward_decision_next_action",
            "auto_collect_operator_packet_strategy_back_forward_decision_collect_command_text",
            "auto_collect_operator_packet_strategy_back_forward_decision_sample_shortage_recovery_command_text",
            "auto_collect_operator_packet_strategy_back_forward_decision_sample_shortage_recovery_range_strategy",
            "auto_collect_operator_packet_strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date",
            "auto_collect_operator_packet_strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date",
            "auto_collect_operator_packet_strategy_operator_decision_status",
            "auto_collect_operator_packet_strategy_operator_decision_verdict",
            "auto_collect_operator_packet_strategy_operator_decision_adoptable",
            "auto_collect_operator_packet_strategy_operator_decision_primary_blocker",
            "auto_collect_operator_packet_strategy_operator_decision_primary_reason",
            "auto_collect_operator_packet_strategy_operator_decision_next_action",
            "auto_collect_operator_packet_strategy_operator_decision_summary",
            "auto_collect_operator_packet_strategy_operator_decision_command_text",
            "auto_collect_operator_packet_strategy_operator_decision_follow_up_command_text",
            "operator_packet_refresh_strategy_source_time_refresh_status",
            "operator_packet_refresh_strategy_source_time_issue_labels",
            "operator_packet_refresh_strategy_source_time_candidate_issue_labels",
            "auto_collect_operator_packet_strategy_source_time_refresh_status",
            "auto_collect_operator_packet_strategy_source_time_issue_labels",
            "auto_collect_operator_packet_strategy_source_time_candidate_issue_labels",
            "operator_packet_refresh_strategy_buy_candidate_gap_status",
            "operator_packet_refresh_strategy_buy_candidate_gap_reason",
            "operator_packet_refresh_strategy_buy_candidate_gap_diagnostic_labels",
            "auto_collect_operator_packet_strategy_buy_candidate_gap_status",
            "auto_collect_operator_packet_strategy_buy_candidate_gap_reason",
            "auto_collect_operator_packet_strategy_buy_candidate_gap_diagnostic_labels",
            "auto_collect_execution_status",
            "auto_collect_execution_selected_count",
            "auto_collect_execution_waiting_count",
            "auto_collect_execution_invalid_count",
            "status_watch_manual_queue_launch_refresh_enabled",
            "status_watch_manual_queue_launch_refresh_returncode",
            "status_watch_manual_queue_launch_refresh_completed",
            "status_watch_manual_queue_launch_refresh_status",
            "status_watch_manual_queue_launch_refresh_queue_refresh_status",
            "status_watch_manual_queue_launch_refresh_queue_refresh_ok",
            "status_watch_manual_queue_launch_refresh_queue_refresh_source_count",
            "status_watch_manual_queue_launch_refresh_selected",
            "status_watch_manual_queue_launch_refresh_selected_queue_id",
            "status_watch_manual_queue_launch_refresh_selected_step_label",
            "status_watch_manual_queue_launch_refresh_blocked",
            "status_watch_manual_queue_launch_refresh_blocked_reasons",
            "status_watch_manual_collect_refresh_enabled",
            "status_watch_manual_collect_refresh_returncode",
            "status_watch_manual_collect_refresh_completed",
            "status_watch_manual_collect_refresh_status",
            "status_watch_manual_collect_refresh_queue_refresh_status",
            "status_watch_manual_collect_refresh_queue_refresh_ok",
            "status_watch_manual_collect_refresh_queue_refresh_source_count",
            "status_watch_manual_collect_refresh_selected_count",
            "status_watch_manual_collect_refresh_waiting_count",
            "status_watch_manual_collect_refresh_invalid_count",
            "status_watch_manual_collect_run_queue_step_count",
            "status_watch_manual_collect_run_queue_step_report_ready_count",
            "status_watch_manual_collect_run_queue_step_collect_ready_count",
            "status_watch_manual_collect_run_queue_step_waiting_report_count",
            "status_watch_manual_collect_run_queue_step_launch_needed_count",
            "status_watch_manual_collect_run_step_completion_audit",
            "recovery_plan_status",
            "recovery_plan_ready_for_mt5_validation",
            "recovery_plan_bridge_required_for_standalone_tester",
            "recovery_plan_standalone_strategy_tester_allowed",
            "recovery_plan_standalone_strategy_tester_note",
            "recovery_plan_next_action",
            "recovery_plan_operator_summary_status",
            "recovery_plan_operator_summary_ready_for_mt5_validation",
            "recovery_plan_operator_summary_bridge_required_for_standalone_tester",
            "recovery_plan_operator_summary_standalone_strategy_tester_allowed",
            "recovery_plan_operator_summary_standalone_strategy_tester_note",
            "recovery_plan_operator_summary_blocking_reasons",
            "recovery_plan_operator_summary_next_action",
            "recovery_plan_operator_summary_next_operation_action",
            "recovery_plan_operator_summary_next_operation_area",
            "recovery_plan_operator_summary_next_operation_target",
            "recovery_plan_operator_summary_next_operation_operator_step",
            "recovery_plan_operator_summary_next_operation_verification",
            "recovery_plan_operator_summary_mt5_terminal_running",
            "recovery_plan_operator_summary_bridge_log_activity_status",
            "recovery_plan_operator_summary_last_ea_post_age_seconds",
            "recovery_plan_operator_summary_snapshot_fresh",
            "recovery_plan_operator_summary_history_request_id",
            "recovery_plan_operator_summary_history_done_id",
            "recovery_plan_operator_summary_history_done_matches_request",
            "recovery_plan_operator_summary_history_data_fresh",
            "recovery_plan_operator_summary_history_data_stale",
            "recovery_plan_operator_summary_history_status_server_time",
            "recovery_plan_operator_summary_history_status_server_time_age_seconds",
            "recovery_plan_operator_summary_history_status_m1_last_time",
            "recovery_plan_operator_summary_history_status_m1_last_time_age_seconds",
            "next_action_runner_current_for_execution",
            "next_action_runner_gate_stale_reason",
            "next_action_runner_runner_promotion_generated_at",
            "next_action_runner_current_promotion_generated_at",
            "next_action_runner_selected_action_current",
            "next_action_runner_blocking_prior_action_count",
            "next_action_runner_blocking_prior_action_summary",
            "next_action_runner_advisory_prior_action_count",
            "next_action_runner_advisory_prior_action_summary",
            "latest_snapshot_fresh",
            "latest_snapshot_age_seconds",
            "snapshot_fresh",
            "snapshot_age_seconds",
            "history_request_pending",
            "history_request_stale_pending",
            "manual_prerequisites_ready",
            "manual_prerequisites_reasons",
            "all_sources_synced",
            "all_compiled_fresh",
            "all_tester_sets_synced",
            "all_tester_configs_synced",
            "all_required_tester_config_references_ready",
            "bridge_log_activity_status",
            "bridge_log_last_ea_post_at",
            "bridge_log_last_ea_post_age_seconds",
            "bridge_log_last_snapshot_post_at",
            "bridge_log_last_snapshot_post_age_seconds",
            "bridge_operator_summary_status",
            "bridge_operator_summary_ready_for_mt5_validation",
            "bridge_operator_summary_blocking_reasons",
            "bridge_operator_summary_next_action",
            "bridge_operator_summary_next_operation_action",
            "bridge_operator_summary_next_operation_area",
            "bridge_operator_summary_next_operation_purpose",
            "bridge_operator_summary_next_operation_target",
            "bridge_operator_summary_next_operation_operator_step",
            "bridge_operator_summary_next_operation_verification",
            "bridge_operator_summary_mt5_terminal_running",
            "bridge_operator_summary_mt5_terminal_match_count",
            "bridge_operator_summary_bridge_log_activity_status",
            "bridge_operator_summary_last_ea_post_age_seconds",
            "bridge_operator_summary_snapshot_fresh",
            "bridge_operator_summary_snapshot_age_seconds",
            "bridge_operator_summary_history_request_pending",
            "bridge_operator_summary_history_request_stale_pending",
            "bridge_operator_summary_history_request_id",
            "bridge_operator_summary_history_done_id",
            "bridge_operator_summary_history_done_matches_request",
            "bridge_operator_summary_history_data_fresh",
            "bridge_operator_summary_history_data_stale",
            "bridge_operator_summary_history_status_server_time",
            "bridge_operator_summary_history_status_server_time_age_seconds",
            "bridge_operator_summary_history_status_m1_last_time",
            "bridge_operator_summary_history_status_m1_last_time_age_seconds",
            "bridge_recovery_operation_card_count",
            "bridge_recovery_next_operation_action",
            "bridge_recovery_next_operation_area",
            "bridge_recovery_next_operation_purpose",
            "bridge_recovery_next_operation_target",
            "bridge_recovery_next_operation_verification",
            "walk_forward_aggregate_status",
            "walk_forward_status",
            "score_weight_walk_status",
            "score_weight_walk_total_test_weight_count",
            "score_weight_walk_required_test_weight_count",
            "score_weight_walk_missing_test_weight_count",
            "score_weight_walk_delta_total_r",
            "score_weight_top_threshold",
            "score_weight_top_pf",
            "score_weight_top_total_r",
            "score_weight_regime_dimension",
            "score_weight_regime_group",
            "score_weight_regime_walk_status",
            "score_weight_regime_walk_missing_test_weight_count",
            "winrate_adopted",
            "winrate_rules",
            "winrate_walk_fold_count",
            "winrate_walk_total_fitted_count",
            "winrate_walk_mean_fitted_pf",
            "winrate_walk_mean_fitted_avg_r",
            "skipped_write",
            "skip_reason",
            "written",
            "score_weight_set_follow_up_status",
            "score_weight_set_follow_up_next_action",
            "score_weight_set_follow_up_reason",
            "score_weight_set_do_not_repeat_conversion",
            "score_weight_set_follow_up_failure_mode",
            "score_weight_set_follow_up_sample_shortage",
            "score_weight_set_follow_up_walk_forward_status",
            "score_weight_set_follow_up_walk_forward_delta_total_r",
            "score_weight_set_follow_up_walk_forward_delta_mean_avg_r",
            "score_weight_set_follow_up_walk_forward_delta_mean_pf",
            "score_weight_set_follow_up_walk_forward_total_test_weight_r",
            "score_weight_set_follow_up_walk_forward_total_test_baseline_r",
            "score_weight_set_follow_up_walk_forward_mean_test_weight_avg_r",
            "score_weight_set_follow_up_walk_forward_mean_test_baseline_avg_r",
            "score_weight_set_follow_up_walk_forward_mean_test_weight_pf",
            "score_weight_set_follow_up_walk_forward_mean_test_baseline_pf",
            "score_weight_set_follow_up_walk_forward_total_test_weight_count",
            "score_weight_set_follow_up_walk_forward_required_test_weight_count",
            "score_weight_set_follow_up_walk_forward_missing_test_weight_count",
            "score_weight_set_follow_up_walk_forward_folds",
            "score_weight_set_follow_up_walk_forward_folds_with_weight_trades",
            "score_weight_set_follow_up_walk_forward_required_folds_with_weight_trades",
            "score_weight_set_follow_up_walk_forward_missing_folds_with_weight_trades",
            "score_weight_set_follow_up_top_candidate_threshold",
            "score_weight_set_follow_up_top_candidate_weights",
            "score_weight_set_follow_up_top_candidate_count",
            "score_weight_set_follow_up_top_candidate_avg_r",
            "score_weight_set_follow_up_top_candidate_pf",
            "score_weight_set_follow_up_top_candidate_total_r",
            "score_weight_set_follow_up_regime_status",
            "score_weight_set_follow_up_regime_dimension",
            "score_weight_set_follow_up_regime_group",
            "score_weight_set_follow_up_regime_sample_shortage",
            "score_weight_set_follow_up_regime_missing_test_weight_count",
            "score_weight_set_follow_up_regime_required_test_weight_count",
            "score_weight_set_follow_up_regime_folds_with_weight_trades",
            "score_weight_set_follow_up_regime_required_folds_with_weight_trades",
            "score_weight_set_follow_up_regime_missing_folds_with_weight_trades",
            "score_weight_set_follow_up_history_status_command",
            "score_weight_set_follow_up_sample_collection_command",
            "score_weight_set_follow_up_collect_command",
            "rr_strategy_count",
            "rr_adoption_audit_count",
            "rr_adoption_candidate_count",
            "rr_adoption_rejected_count",
            "rr_best_strategy",
            "rr_best_policy",
            "rr_best_avg_r",
            "rr_best_pf",
            "rr_best_total_r",
            "rr_candidate_strategy",
            "rr_candidate_balance_score",
            "rr_rejected_strategies",
            "rr_rejection_reasons",
            "strategy_tester_analysis_generated_at",
            "strategy_tester_analysis_status",
            "strategy_tester_analysis_candidate_count",
            "strategy_tester_analysis_aggregate_only_count",
            "strategy_tester_analysis_candidate_labels",
            "strategy_tester_analysis_aggregate_only_labels",
            "strategy_tester_analysis_blockers",
            "strategy_tester_analysis_report_status_counts",
            "strategy_tester_analysis_side_candidate_counts",
            "strategy_tester_analysis_source_artifacts",
            "strategy_tester_analysis_source_artifact_generated_at_by_label",
            "strategy_tester_analysis_source_artifact_state_by_label",
            "strategy_tester_analysis_source_artifact_path_by_label",
            "strategy_tester_analysis_buy_candidate_gap_status",
            "strategy_tester_analysis_buy_candidate_gap_diagnostic_labels",
            "strategy_tester_analysis_buy_candidate_gap_refresh_queue_command_text",
            "strategy_tester_analysis_promotion_decision",
            "strategy_tester_analysis_embedded_promotion_generated_at",
            "strategy_tester_analysis_embedded_promotion_decision",
            "strategy_tester_analysis_promotion_source_generated_at",
            "strategy_tester_analysis_promotion_source_state",
            "strategy_tester_analysis_embedded_promotion_freshness_status",
            "strategy_tester_analysis_refresh_analysis_command_text",
            "strategy_tester_analysis_back_forward_evidence_state",
            "strategy_tester_analysis_back_forward_performance_status",
            "strategy_tester_analysis_back_forward_decision_status",
            "strategy_tester_analysis_back_forward_decision_adoptable",
            "strategy_tester_analysis_back_forward_decision_next_action",
            "strategy_tester_analysis_back_forward_decision_reason",
            "strategy_tester_analysis_back_forward_decision_thresholds",
            "strategy_tester_analysis_back_forward_decision_backtest_trades",
            "strategy_tester_analysis_back_forward_decision_forward_trades",
            "strategy_tester_analysis_back_forward_decision_forward_pf",
            "strategy_tester_analysis_back_forward_decision_forward_avg_r",
            "strategy_tester_analysis_back_forward_decision_forward_pf_delta_vs_backtest",
            "strategy_tester_analysis_back_forward_decision_forward_avg_r_delta_vs_backtest",
            "strategy_tester_analysis_manual_collect_status",
            "strategy_tester_analysis_manual_collect_ready",
            "strategy_tester_analysis_next_queue_id",
            "strategy_tester_analysis_next_step_label",
            "strategy_tester_analysis_next_inputs",
            "strategy_tester_analysis_next_report",
            "strategy_tester_analysis_collect_only_command_text",
            "entry_count",
            "total_entry_count",
            "stale_entry_count",
            "static_strategy_config_count",
            "static_strategy_configs",
            "static_candidate_label_count",
            "static_candidate_labels",
            "step_count",
            "ready_entry_count",
            "ready_to_collect_count",
            "selected_count",
            "waiting_count",
            "invalid_count",
            "all_collect_ready",
            "manual_queue_operator_handoff_state",
            "manual_queue_operator_handoff_status",
            "manual_queue_operator_handoff_next_action",
            "manual_queue_operator_handoff_collect_ready",
            "manual_queue_operator_handoff_ready_entry_ids",
            "manual_queue_operator_handoff_waiting_entry_ids",
            "manual_queue_operator_handoff_stale_entry_ids",
            "manual_queue_operator_handoff_next_queue_id",
            "manual_queue_operator_handoff_next_step_label",
            "manual_queue_operator_handoff_next_symbol",
            "manual_queue_operator_handoff_next_period",
            "manual_queue_operator_handoff_next_model",
            "manual_queue_operator_handoff_next_dates",
            "manual_queue_operator_handoff_next_forward",
            "manual_queue_operator_handoff_next_optimization_label",
            "manual_queue_operator_handoff_next_run_type",
            "manual_queue_operator_handoff_next_expected_report_artifact",
            "manual_queue_operator_handoff_next_inputs",
            "manual_queue_operator_handoff_next_report",
            "manual_queue_operator_handoff_next_step_operator_summary",
            "manual_queue_operator_handoff_next_step_summary",
            "manual_queue_operator_handoff_next_step_collect_filter_summary",
            "manual_queue_operator_handoff_next_launch_needed",
            "manual_queue_operator_handoff_next_launch_command_kind",
            "manual_queue_operator_handoff_quick_queue_step",
            "manual_queue_operator_handoff_quick_purpose",
            "manual_queue_operator_handoff_quick_expert",
            "manual_queue_operator_handoff_quick_symbol",
            "manual_queue_operator_handoff_quick_period",
            "manual_queue_operator_handoff_quick_dates",
            "manual_queue_operator_handoff_quick_forward",
            "manual_queue_operator_handoff_quick_optimization_label",
            "manual_queue_operator_handoff_quick_inputs",
            "manual_queue_operator_handoff_quick_report",
            "manual_queue_operator_handoff_execute_command_text",
            "manual_queue_operator_handoff_execute_and_refresh_analysis_command_text",
            "manual_queue_operator_handoff_execute_and_refresh_full_analysis_command_text",
            "manual_queue_operation_card_count",
            "manual_queue_next_operation_action",
            "manual_queue_next_operation_purpose",
            "manual_queue_next_operation_queue_id",
            "manual_queue_next_operation_step_label",
            "manual_queue_next_operation_forward",
            "manual_queue_next_operation_optimization_label",
            "manual_queue_next_operation_inputs",
            "manual_queue_next_operation_report",
            "manual_queue_next_operation_collect_status",
            "queue_status",
            "queue_next_action",
            "queue_generated_at",
            "state",
            "progress_state",
            "next_queue_step",
            "next_report",
            "next_inputs",
            "queue_operator_handoff_state",
            "queue_operator_handoff_collect_ready",
            "queue_operator_handoff_waiting_entry_ids",
            "queue_operator_handoff_next_queue_id",
            "queue_operator_handoff_next_step_label",
            "queue_operator_handoff_next_forward",
            "queue_operator_handoff_next_inputs",
            "queue_operator_handoff_next_report",
            "queue_operator_handoff_next_step_operator_summary",
            "queue_operator_handoff_next_step_summary",
            "queue_operator_handoff_next_step_collect_filter_summary",
            "queue_operator_handoff_collect_execute_command_text",
            "queue_operator_handoff_collect_execute_and_refresh_analysis_command_text",
            "queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text",
            "selected_matches_queue_handoff",
            "queue_refresh_status",
            "queue_refresh_ok",
            "queue_refresh_enabled",
            "queue_refresh_source_count",
        ):
            if key in row:
                status_parts.append(f"{key}={compact_status_value(row.get(key))}")
        lines.append(
            f"| {row.get('name', '')} | {row.get('exists')} | {row.get('fresh')} | "
            f"{row.get('age_seconds', '')} | {row.get('generated_at', '')} | "
            f"{', '.join(status_parts)} | {row.get('path', '')} |"
        )
    lines.extend(
        [
            "",
            "## Phase Completion Conditions",
            "",
            "| phase | conditions | spec line |",
            "|---|---:|---:|",
        ]
    )
    for row in payload.get("phases", []):
        if not isinstance(row, dict):
            continue
        conditions = row.get("completion_conditions")
        count = len(conditions) if isinstance(conditions, list) else 0
        lines.append(f"| {row.get('name', '')} | {count} | {row.get('line', '')} |")
    lines.extend(
        [
            "",
            "## Phase Current Blockers",
            "",
            "| phase | status | blockers | primary next action | related next actions | reasons |",
            "|---|---|---:|---|---|---|",
        ]
    )
    phase_blockers = (
        payload.get("phase_current_blockers")
        if isinstance(payload.get("phase_current_blockers"), list)
        else []
    )
    phase_rows = phase_blockers or (
        payload.get("phase_statuses") if isinstance(payload.get("phase_statuses"), list) else []
    )
    if phase_rows:
        for row in phase_rows:
            if not isinstance(row, dict):
                continue
            reasons = row.get("blocking_reasons") if isinstance(row.get("blocking_reasons"), list) else []
            related_actions = (
                row.get("related_next_action_ids")
                if isinstance(row.get("related_next_action_ids"), list)
                else []
            )
            primary_next_action = str(row.get("primary_next_action_id") or "")
            primary_priority = row.get("primary_next_action_priority", "")
            primary_summary = str(row.get("primary_next_action_summary") or "")
            if primary_next_action and primary_priority != "":
                primary_next_action = f"P{primary_priority} {primary_next_action}"
            if primary_summary:
                primary_next_action = (
                    f"{primary_next_action}: {primary_summary}"
                    if primary_next_action
                    else primary_summary
                )
            lines.append(
                f"| {markdown_cell(row.get('name', ''))} | {markdown_cell(row.get('status', ''))} | "
                f"{row.get('blocking_reason_count', '')} | "
                f"{markdown_cell(primary_next_action)} | "
                f"{markdown_cell('; '.join(str(action_id) for action_id in related_actions))} | "
                f"{markdown_cell('; '.join(str(reason) for reason in reasons))} |"
            )
    else:
        lines.append("| - | - | - | - | - | - |")
    return "\n".join(lines) + "\n"


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_markdown(payload), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize implementation and runtime evidence against the swing trading spec.")
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--spec", default=DEFAULT_SPEC_PATH)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--max-artifact-age-seconds", type=int, default=DEFAULT_MAX_ARTIFACT_AGE_SECONDS)
    parser.add_argument("--max-history-request-pending-seconds", type=int, default=DEFAULT_MAX_HISTORY_REQUEST_PENDING_SECONDS)
    parser.add_argument("--max-bridge-snapshot-age-seconds", type=int, default=DEFAULT_MAX_BRIDGE_SNAPSHOT_AGE_SECONDS)
    parser.add_argument("--max-history-data-age-seconds", type=int, default=DEFAULT_MAX_HISTORY_DATA_AGE_SECONDS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_spec_coverage(
        workspace_root=args.workspace_root,
        spec_path=args.spec,
        max_artifact_age_seconds=args.max_artifact_age_seconds,
        max_history_request_pending_seconds=args.max_history_request_pending_seconds,
        max_bridge_snapshot_age_seconds=args.max_bridge_snapshot_age_seconds,
        max_history_data_age_seconds=args.max_history_data_age_seconds,
    )
    write_json(args.output_json, payload)
    write_markdown(args.output_md, payload)
    print(
        json.dumps(
            {
                "ok": payload["ok"],
                "goal_completion_proven": payload["goal_completion_proven"],
                "component_count": payload["component_count"],
                "missing_component_count": payload["missing_component_count"],
                "runtime_artifact_count": payload["runtime_artifact_count"],
                "max_artifact_age_seconds": payload["max_artifact_age_seconds"],
                "max_history_request_pending_seconds": payload["max_history_request_pending_seconds"],
                "max_bridge_snapshot_age_seconds": payload["max_bridge_snapshot_age_seconds"],
                "max_history_data_age_seconds": payload["max_history_data_age_seconds"],
                "not_complete_reason_count": payload["not_complete_reason_count"],
                "not_complete_reasons": payload["not_complete_reasons"],
                "next_action_count": payload["next_action_count"],
                "blocked_phase_count": payload["blocked_phase_count"],
                "first_blocked_phase": payload.get("first_blocked_phase", ""),
                "first_blocked_phase_primary_reason": payload.get(
                    "first_blocked_phase_primary_reason", ""
                ),
                "first_blocked_phase_primary_next_action": payload.get(
                    "first_blocked_phase_primary_next_action", ""
                ),
                "output_json": args.output_json,
                "output_md": args.output_md,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if payload["goal_completion_proven"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
