from __future__ import annotations

import argparse
import json
import shlex
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT
from analysis.mt5_back_forward_run import back_forward_evidence_state
from analysis.mt5_manual_test_queue import operator_collect_filter_summary, operator_step_summary
from analysis.mt5_next_action_run import EXECUTION_LABELS, command_option_value, execution_class, select_next_action_plan
from analysis.mt5_tester_optimization_report import estimate_set_passes
from analysis.mt5_tester_run import RISK_PRESET_REQUIRED_INPUTS, discover_running_terminal_processes


DEFAULT_OUTPUT_JSON = "runtime/latest_mt5_tester_status.json"
DEFAULT_OUTPUT_MD = "runtime/latest_mt5_tester_status.md"
DEFAULT_OPTIMIZATION_REPORT = "runtime/latest_mt5_optimization_report.json"
DEFAULT_NEXT_ACTION_RUN = "runtime/latest_mt5_next_action_run.json"
DEFAULT_BACK_FORWARD_RUN = "runtime/latest_mt5_back_forward_run.json"
DEFAULT_MANUAL_TEST_QUEUE = "runtime/latest_mt5_manual_test_queue.json"
DEFAULT_MANUAL_QUEUE_LAUNCH = "runtime/latest_mt5_manual_queue_launch.json"
DEFAULT_MANUAL_COLLECT_RUN = "runtime/latest_mt5_manual_collect_run.json"
DEFAULT_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION = "runtime/latest_mt5_manual_test_queue_with_optimization.json"
DEFAULT_MANUAL_QUEUE_LAUNCH_WITH_OPTIMIZATION = "runtime/latest_mt5_manual_queue_launch_with_optimization.json"
DEFAULT_MANUAL_COLLECT_WITH_OPTIMIZATION = "runtime/latest_mt5_manual_collect_with_optimization.json"
DEFAULT_MANUAL_OPERATOR_PACKET_WITH_OPTIMIZATION = (
    "runtime/latest_mt5_manual_operator_packet_with_optimization.json"
)
DEFAULT_MANUAL_AUTO_COLLECT_WATCH = "runtime/latest_mt5_manual_auto_collect_watch.json"
DEFAULT_STABLE_CANDIDATE_REPORT = "runtime/latest_mt5_stable_candidate_optimization_report.json"
DEFAULT_STABLE_CANDIDATE_RECOMMENDATION = "runtime/latest_mt5_stable_candidate_recommendation.json"
DEFAULT_STABLE_CANDIDATE_TESTER_RUN = "runtime/latest_mt5_tester_stable_candidate_run.json"
DEFAULT_BRIDGE_RECOVERY_PLAN = "runtime/latest_bridge_recovery_plan.json"
LEGACY_STATUS_WATCH_HEARTBEAT = "runtime/mt5_tester_status_watch_heartbeat.json"
DEFAULT_STATUS_WATCH_HEARTBEAT = "runtime/mt5_tester_status_watch_heartbeat_current.json"
DEFAULT_STATUS_WATCH_PID = "runtime/mt5_tester_status_watch_current.pid"
DEFAULT_MAX_ARTIFACT_AGE_SECONDS = 3600
DEFAULT_STATUS_WATCH_HEARTBEAT_MAX_AGE_SECONDS = 180
STATUS_WATCH_HEARTBEAT_IMPLEMENTATION_VERSION = 89
STATUS_WATCH_HEARTBEAT_REQUIRED_FIELDS = (
    "ok",
    "status_ok",
    "status",
    "pid_file_enabled",
    "pid_file_written",
    "heartbeat_enabled",
    "mt5_next_operator_action",
    "mt5_next_operator_mode",
    "mt5_next_operator_launch_state",
    "mt5_next_queue_step",
    "mt5_next_quick_input",
    "mt5_next_step_operator_summary",
    "mt5_next_step_summary",
    "mt5_next_step_collect_filter_summary",
    "mt5_next_manual_run_start_effective_after",
    "mt5_next_manual_run_start_effective_after_values",
    "mt5_auto_launch_command_available",
    "mt5_auto_launch_blocked",
    "mt5_auto_launch_blocked_reasons",
    "mt5_auto_launch_command_text",
    "mt5_auto_launch_note",
    "mt5_back_forward_quick_start_status",
    "mt5_back_forward_quick_start_quick_inputs",
    "mt5_back_forward_quick_start_current_quick_input",
    "mt5_back_forward_quick_start_collect_command_text",
    "mt5_strategy_operator_decision_status",
    "mt5_strategy_operator_decision_verdict",
    "mt5_strategy_operator_decision_primary_blocker",
    "mt5_strategy_operator_decision_next_action",
    "mt5_strategy_operator_decision_command_text",
    "mt5_collect_dry_run_command_text",
    "mt5_collect_execute_command_text",
    "mt5_collect_execute_and_refresh_analysis_command_text",
    "mt5_collect_execute_and_refresh_all_command_text",
    "mt5_collect_execute_and_refresh_full_analysis_command_text",
    "mt5_manual_queue_status",
    "mt5_manual_queue_progress_state",
    "mt5_manual_queue_waiting_count",
    "mt5_manual_queue_step_launch_needed_count",
    "manual_prerequisites_ready",
    "manual_prerequisites_reasons",
    "manual_prerequisites_compile_status_path",
    "manual_prerequisites_generated_at",
    "back_forward_plan_validation_ready",
    "back_forward_plan_validation_status",
    "back_forward_plan_validation_reasons",
    "mt5_operator_handoff_state",
    "mt5_operator_handoff_recommended_path",
    "mt5_operator_handoff_manual_strategy_tester_available",
    "mt5_operator_handoff_terminal_running",
    "mt5_operator_handoff_auto_launch_ready",
    "mt5_operator_handoff_auto_launch_status",
    "mt5_operator_handoff_auto_launch_blocked_by_running_terminal",
    "mt5_operator_handoff_auto_launch_blockers",
    "mt5_operator_handoff_manual_queue_status",
    "mt5_operator_handoff_manual_queue_next_action",
    "mt5_operator_handoff_manual_collect_status",
    "mt5_operator_handoff_manual_collect_next_action",
    "mt5_operator_handoff_next_mt5_step",
    "mt5_operator_handoff_quick_input",
    "mt5_operator_handoff_next_step_operator_summary",
    "mt5_operator_handoff_next_step_summary",
    "mt5_operator_handoff_next_step_collect_filter_summary",
    "mt5_operator_handoff_manual_collect_dry_run_command_text",
    "mt5_operator_handoff_manual_collect_execute_command_text",
    "mt5_operator_handoff_manual_collect_execute_and_refresh_analysis_command_text",
    "mt5_operator_handoff_manual_collect_execute_and_refresh_all_command_text",
    "mt5_operator_handoff_manual_collect_execute_and_refresh_full_analysis_command_text",
    "mt5_operator_handoff_bridge_required_for_standalone_tester",
    "mt5_operator_handoff_bridge_ready_for_mt5_validation",
    "mt5_operator_handoff_bridge_status",
    "mt5_operator_handoff_bridge_note",
    "bridge_recovery_plan_status",
    "bridge_recovery_plan_ready_for_mt5_validation",
    "bridge_recovery_plan_output_json",
    "bridge_recovery_plan_blocking_reasons",
    "bridge_recovery_plan_next_action",
    "bridge_recovery_plan_history_data_fresh",
    "bridge_recovery_plan_history_data_stale",
    "bridge_recovery_plan_history_status_server_time",
    "bridge_recovery_plan_history_status_server_time_age_seconds",
    "bridge_recovery_plan_history_status_m1_last_time",
    "bridge_recovery_plan_history_status_m1_last_time_age_seconds",
    "compile_all_tester_configs_synced",
    "manual_strategy_tester_available",
    "manual_strategy_tester_recommended",
    "manual_strategy_tester_status",
    "manual_strategy_tester_auto_launch_blocked_by_running_terminal",
    "manual_strategy_tester_auto_launch_blockers",
    "manual_strategy_tester_collect_only_command_text",
    "manual_strategy_tester_manual_run_start_after",
    "manual_strategy_tester_step_count",
    "manual_strategy_tester_steps",
    "manual_test_queue_exists",
    "manual_test_queue_status",
    "manual_test_queue_next_action",
    "manual_test_queue_progress_state",
    "manual_test_queue_entry_count",
    "manual_test_queue_total_entry_count",
    "manual_test_queue_stale_entry_count",
    "manual_test_queue_current_for_execution_count",
    "manual_test_queue_selected_action_present_count",
    "manual_test_queue_selected_action_current_count",
    "manual_test_queue_selected_action_stale_count",
    "manual_test_queue_current_promotion_generated_at_values",
    "manual_test_queue_current_promotion_decision_values",
    "manual_test_queue_gate_stale_reasons",
    "manual_test_queue_not_current_entry_ids",
    "manual_test_queue_manual_run_start_marked",
    "manual_test_queue_manual_run_start_marked_this_run",
    "manual_test_queue_manual_run_start_preserved",
    "manual_test_queue_manual_run_start_state_count",
    "manual_test_queue_manual_run_start_state_marked_count",
    "manual_test_queue_manual_run_start_effective_after_values",
    "manual_test_queue_manual_run_start_after_override",
    "manual_test_queue_step_count",
    "manual_test_queue_ready_to_collect_count",
    "manual_test_queue_waiting_count",
    "manual_test_queue_step_report_ready_count",
    "manual_test_queue_step_collect_ready_count",
    "manual_test_queue_step_waiting_report_count",
    "manual_test_queue_step_launch_needed_count",
    "manual_test_queue_step_report_ready_ids",
    "manual_test_queue_step_collect_ready_ids",
    "manual_test_queue_step_waiting_report_ids",
    "manual_test_queue_step_launch_needed_ids",
    "manual_test_queue_collect_check_command_text",
    "manual_test_queue_next_queue_step",
    "manual_test_queue_quick_input",
    "manual_test_queue_next_quick_input",
    "manual_test_queue_next_launch_step",
    "manual_test_queue_all_collect_ready",
    "manual_test_queue_blocking_reasons",
    "manual_test_queue_entries",
    "manual_test_queue_strategy_tester_targets",
    "manual_test_queue_operation_cards",
    "manual_test_queue_execution_checklist",
    "manual_test_queue_operator_handoff",
    "manual_test_queue_operator_handoff_quick_input",
    "manual_test_queue_next_step_operator_summary",
    "manual_test_queue_next_step_summary",
    "manual_test_queue_next_step_collect_filter_summary",
    "manual_queue_launch_exists",
    "manual_queue_launch_status",
    "manual_queue_launch_next_action",
    "manual_queue_launch_selected",
    "manual_queue_launch_selected_item",
    "manual_queue_launch_selected_matches_queue_handoff",
    "manual_queue_launch_queue_operator_handoff_state",
    "manual_queue_launch_queue_operator_handoff_next_mt5_step",
    "manual_queue_launch_queue_operator_handoff_quick_input",
    "manual_queue_launch_queue_operator_handoff_next_step_operator_summary",
    "manual_queue_launch_queue_operator_handoff_next_step_summary",
    "manual_queue_launch_queue_operator_handoff_next_step_collect_filter_summary",
    "manual_queue_launch_queue_operator_handoff_collect_ready",
    "manual_queue_launch_queue_operator_handoff_waiting_entry_ids",
    "manual_queue_launch_queue_operator_handoff_collect_dry_run_command_text",
    "manual_queue_launch_queue_operator_handoff_collect_execute_command_text",
    "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_analysis_command_text",
    "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_all_command_text",
    "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text",
    "manual_queue_launch_launch_command_kind",
    "manual_queue_launch_command_text",
    "manual_queue_launch_mark_manual_run_start",
    "manual_queue_launch_manual_run_start_mark_status",
    "manual_queue_launch_manual_run_start_mark_attempted",
    "manual_queue_launch_manual_run_start_after",
    "manual_queue_launch_blocked",
    "manual_queue_launch_blocked_reasons",
    "manual_queue_launch_running_terminal_count",
    "manual_queue_launch_refresh_enabled",
    "manual_queue_launch_refresh_returncode",
    "manual_queue_launch_refresh_status",
    "manual_queue_launch_refresh_queue_refresh_status",
    "manual_queue_launch_refresh_queue_refresh_ok",
    "manual_queue_launch_refresh_queue_refresh_source_count",
    "manual_queue_launch_refresh_selected",
    "manual_queue_launch_refresh_selected_queue_id",
    "manual_queue_launch_refresh_selected_step_label",
    "manual_queue_launch_refresh_blocked",
    "manual_queue_launch_refresh_blocked_reasons",
    "manual_collect_run_exists",
    "manual_collect_run_status",
    "manual_collect_run_execute",
    "manual_collect_run_dry_run",
    "manual_collect_run_selected_count",
    "manual_collect_run_waiting_count",
    "manual_collect_run_invalid_count",
    "manual_collect_run_queue_step_count",
    "manual_collect_run_queue_step_report_ready_count",
    "manual_collect_run_queue_step_collect_ready_count",
    "manual_collect_run_queue_step_waiting_report_count",
    "manual_collect_run_queue_step_launch_needed_count",
    "manual_collect_run_queue_refresh_status",
    "manual_collect_run_next_action",
    "manual_collect_run_handoff_state",
    "manual_collect_run_handoff_ready_ids",
    "manual_collect_run_handoff_waiting_ids",
    "manual_collect_run_handoff_invalid_ids",
    "manual_collect_run_handoff_next_mt5_step",
    "manual_collect_run_handoff_quick_input",
    "manual_collect_run_handoff_next_step_operator_summary",
    "manual_collect_run_handoff_next_step_summary",
    "manual_collect_run_handoff_next_step_collect_filter_summary",
    "manual_collect_run_handoff_dry_run_command_text",
    "manual_collect_run_handoff_execute_command_text",
    "manual_collect_run_step_completion_audit",
    "manual_collect_refresh_enabled",
    "manual_collect_refresh_returncode",
    "manual_collect_refresh_status",
    "manual_collect_refresh_queue_refresh_status",
    "manual_collect_refresh_queue_refresh_ok",
    "manual_collect_refresh_queue_refresh_source_count",
    "manual_collect_refresh_selected_count",
    "manual_collect_refresh_waiting_count",
    "manual_collect_refresh_invalid_count",
    "manual_auto_collect_watch_exists",
    "manual_auto_collect_watch_ok",
    "manual_auto_collect_watch_status",
    "manual_auto_collect_watch_next_action",
    "manual_auto_collect_watch_execute_ready",
    "manual_auto_collect_watch_ready_to_execute",
    "manual_auto_collect_watch_ready_for_collect_execute",
    "manual_auto_collect_watch_selected_count",
    "manual_auto_collect_watch_waiting_count",
    "manual_auto_collect_watch_invalid_count",
    "manual_auto_collect_watch_collect_dry_run_command_text",
    "manual_auto_collect_watch_collect_execute_command_text",
    "manual_auto_collect_watch_queue_launch_status",
    "manual_auto_collect_watch_queue_launch_blocked",
    "manual_auto_collect_watch_queue_launch_blocked_reasons",
    "manual_auto_collect_watch_operator_packet_next_queue_step",
    "manual_auto_collect_watch_operator_packet_auto_launch_command_text",
    "manual_auto_collect_watch_operator_packet_auto_launch_command_available",
    "manual_auto_collect_watch_operator_packet_auto_launch_blocked",
    "manual_auto_collect_watch_operator_packet_auto_launch_blocked_reasons",
    "manual_auto_collect_watch_operator_packet_auto_launch_note",
    "manual_auto_collect_watch_operator_packet_strategy_source_time_refresh_status",
    "manual_auto_collect_watch_operator_packet_strategy_source_time_issue_labels",
    "manual_auto_collect_watch_operator_packet_strategy_source_time_candidate_issue_labels",
    "manual_auto_collect_watch_operator_packet_strategy_source_time_refresh_analysis_command_text",
    "manual_auto_collect_watch_operator_packet_strategy_source_time_refresh_analysis_command_available",
    "manual_auto_collect_watch_operator_packet_strategy_buy_candidate_gap_status",
    "manual_auto_collect_watch_operator_packet_strategy_buy_candidate_gap_reason",
    "manual_auto_collect_watch_operator_packet_strategy_buy_candidate_gap_diagnostic_labels",
    "manual_auto_collect_watch_operator_packet_strategy_buy_candidate_gap_collect_refresh_command_text",
    "manual_auto_collect_watch_operator_packet_strategy_buy_candidate_gap_collect_refresh_command_available",
    "manual_auto_collect_watch_operator_packet_strategy_operator_decision_status",
    "manual_auto_collect_watch_operator_packet_strategy_operator_decision_verdict",
    "manual_auto_collect_watch_operator_packet_strategy_operator_decision_adoptable",
    "manual_auto_collect_watch_operator_packet_strategy_operator_decision_primary_blocker",
    "manual_auto_collect_watch_operator_packet_strategy_operator_decision_primary_reason",
    "manual_auto_collect_watch_operator_packet_strategy_operator_decision_next_action",
    "manual_auto_collect_watch_operator_packet_strategy_operator_decision_summary",
    "manual_auto_collect_watch_operator_packet_strategy_operator_decision_command_text",
    "manual_auto_collect_watch_operator_packet_strategy_operator_decision_follow_up_command_text",
    "manual_auto_collect_watch_execution_enabled",
    "manual_auto_collect_watch_execution_attempted",
    "manual_auto_collect_watch_execution_returncode",
    "manual_auto_collect_watch_execution_status",
    "manual_test_queue_with_optimization_exists",
    "manual_test_queue_with_optimization_status",
    "manual_test_queue_with_optimization_next_action",
    "manual_test_queue_with_optimization_progress_state",
    "manual_test_queue_with_optimization_entry_count",
    "manual_test_queue_with_optimization_total_entry_count",
    "manual_test_queue_with_optimization_stale_entry_count",
    "manual_test_queue_with_optimization_manual_run_start_marked",
    "manual_test_queue_with_optimization_manual_run_start_marked_this_run",
    "manual_test_queue_with_optimization_manual_run_start_preserved",
    "manual_test_queue_with_optimization_manual_run_start_state_count",
    "manual_test_queue_with_optimization_manual_run_start_state_marked_count",
    "manual_test_queue_with_optimization_manual_run_start_effective_after_values",
    "manual_test_queue_with_optimization_manual_run_start_after_override",
    "manual_test_queue_with_optimization_step_count",
    "manual_test_queue_with_optimization_ready_to_collect_count",
    "manual_test_queue_with_optimization_waiting_count",
    "manual_test_queue_with_optimization_step_report_ready_count",
    "manual_test_queue_with_optimization_step_collect_ready_count",
    "manual_test_queue_with_optimization_step_waiting_report_count",
    "manual_test_queue_with_optimization_step_launch_needed_count",
    "manual_test_queue_with_optimization_step_report_ready_ids",
    "manual_test_queue_with_optimization_step_collect_ready_ids",
    "manual_test_queue_with_optimization_step_waiting_report_ids",
    "manual_test_queue_with_optimization_step_launch_needed_ids",
    "manual_test_queue_with_optimization_collect_check_command_text",
    "manual_test_queue_with_optimization_next_queue_step",
    "manual_test_queue_with_optimization_quick_input",
    "manual_test_queue_with_optimization_next_quick_input",
    "manual_test_queue_with_optimization_next_launch_step",
    "manual_test_queue_with_optimization_all_collect_ready",
    "manual_test_queue_with_optimization_blocking_reasons",
    "manual_test_queue_with_optimization_static_strategy_config_count",
    "manual_test_queue_with_optimization_static_strategy_configs",
    "manual_test_queue_with_optimization_static_candidate_label_count",
    "manual_test_queue_with_optimization_static_candidate_labels",
    "manual_test_queue_with_optimization_entries",
    "manual_test_queue_with_optimization_strategy_tester_targets",
    "manual_test_queue_with_optimization_operation_cards",
    "manual_test_queue_with_optimization_execution_checklist",
    "manual_test_queue_with_optimization_operator_handoff",
    "manual_test_queue_with_optimization_operator_handoff_quick_input",
    "manual_test_queue_with_optimization_next_step_operator_summary",
    "manual_test_queue_with_optimization_next_step_summary",
    "manual_test_queue_with_optimization_next_step_collect_filter_summary",
    "manual_queue_launch_with_optimization_queue_operator_handoff_next_step_summary",
    "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text",
    "manual_operator_packet_with_optimization_next_operator_before_mt5_command_text",
    "manual_operator_packet_with_optimization_auto_launch_command_text",
    "manual_operator_packet_with_optimization_auto_launch_command_available",
    "manual_operator_packet_with_optimization_auto_launch_blocked",
    "manual_operator_packet_with_optimization_auto_launch_blocked_reasons",
    "manual_operator_packet_with_optimization_auto_launch_note",
    "manual_operator_packet_with_optimization_back_forward_quick_start_status",
    "manual_operator_packet_with_optimization_back_forward_quick_start_step_count",
    "manual_operator_packet_with_optimization_back_forward_quick_start_waiting_step_count",
    "manual_operator_packet_with_optimization_back_forward_quick_start_current_queue_step",
    "manual_operator_packet_with_optimization_back_forward_quick_start_current_purpose",
    "manual_operator_packet_with_optimization_back_forward_quick_start_steps",
    "manual_operator_packet_with_optimization_back_forward_quick_start_quick_inputs",
    "manual_operator_packet_with_optimization_back_forward_quick_start_current_quick_input",
    "manual_operator_packet_with_optimization_back_forward_quick_start_backtest_quick_input",
    "manual_operator_packet_with_optimization_back_forward_quick_start_forward_quick_input",
    "manual_operator_packet_with_optimization_back_forward_quick_start_collect_command_text",
    "manual_operator_packet_with_optimization_back_forward_quick_start_full_queue_collect_command_text",
    "manual_operator_packet_with_optimization_back_forward_quick_start_auto_launch_blocked",
    "manual_operator_packet_with_optimization_back_forward_quick_start_auto_launch_blocked_reasons",
    "manual_operator_packet_with_optimization_back_forward_completion_summary",
    "manual_operator_packet_with_optimization_back_forward_completion_manual_run_start_after",
    "manual_operator_packet_with_optimization_back_forward_completion_expected_step_count",
    "manual_operator_packet_with_optimization_back_forward_completion_waiting_step_count",
    "manual_operator_packet_with_optimization_back_forward_completion_collect_command_text",
    "manual_operator_packet_with_optimization_back_forward_completion_steps",
    "manual_operator_packet_with_optimization_back_forward_completion_decision_thresholds",
    "manual_operator_packet_with_optimization_next_operator_quick_input",
    "manual_operator_packet_with_optimization_next_step_quick_input",
    "manual_operator_packet_with_optimization_manual_run_start_marked",
    "manual_operator_packet_with_optimization_manual_run_start_marked_this_run",
    "manual_operator_packet_with_optimization_manual_run_start_preserved",
    "manual_operator_packet_with_optimization_manual_run_start_state_count",
    "manual_operator_packet_with_optimization_manual_run_start_state_marked_count",
    "manual_operator_packet_with_optimization_manual_run_start_effective_after",
    "manual_operator_packet_with_optimization_manual_run_start_effective_after_values",
    "manual_operator_packet_with_optimization_manual_run_start_after_override",
    "manual_operator_packet_with_optimization_next_step_operator_summary",
    "manual_operator_packet_with_optimization_next_step_summary",
    "manual_operator_packet_with_optimization_next_step_collect_filter_summary",
    "manual_operator_packet_with_optimization_strategy_back_forward_decision_status",
    "manual_operator_packet_with_optimization_strategy_back_forward_decision_adoptable",
    "manual_operator_packet_with_optimization_strategy_back_forward_decision_next_action",
    "manual_operator_packet_with_optimization_strategy_back_forward_decision_reason",
    "manual_operator_packet_with_optimization_strategy_back_forward_decision_collect_command_text",
    "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_command_text",
    "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_range_strategy",
    "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date",
    "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date",
    "manual_queue_launch_with_optimization_mark_manual_run_start",
    "manual_queue_launch_with_optimization_manual_run_start_mark_status",
    "manual_queue_launch_with_optimization_manual_run_start_mark_attempted",
    "manual_queue_launch_with_optimization_manual_run_start_after",
    "back_forward_run_evidence_state",
    "back_forward_run_run_id_prefix",
    "back_forward_run_manual_collect_only_command_text",
    "back_forward_run_manual_run_start_after",
    "back_forward_run_manual_collect_ready",
    "back_forward_run_manual_collect_status",
    "back_forward_run_manual_collect_csv_count",
    "back_forward_run_manual_collect_modified_after",
    "back_forward_run_manual_collect_reason",
    "back_forward_run_manual_collect_blocking_reasons",
    "back_forward_run_manual_collect_next_action",
    "back_forward_run_manual_step_count",
    "back_forward_run_manual_steps",
    "back_forward_run_mt5_strategy_tester_pack_available",
    "back_forward_run_mt5_strategy_tester_pack_ready_for_manual_mt5_run",
    "back_forward_run_mt5_strategy_tester_pack_status",
    "back_forward_run_mt5_strategy_tester_pack_next_action",
    "back_forward_run_mt5_strategy_tester_pack_is_back_forward_pair",
    "back_forward_run_mt5_strategy_tester_pack_manual_run_start_after",
    "back_forward_run_mt5_strategy_tester_pack_collect_command_text",
    "back_forward_run_mt5_strategy_tester_pack_collect_ready",
    "back_forward_run_mt5_strategy_tester_pack_collect_status",
    "back_forward_run_mt5_strategy_tester_pack_collect_reason",
    "back_forward_run_mt5_strategy_tester_pack_step_count",
    "back_forward_run_mt5_strategy_tester_pack_steps",
    "back_forward_run_manual_prerequisites_ready",
    "back_forward_run_manual_prerequisites_reasons",
    "back_forward_run_manual_prerequisites_compile_status_path",
    "back_forward_run_manual_prerequisites_generated_at",
    "back_forward_run_plan_validation_ready",
    "back_forward_run_plan_validation_status",
    "back_forward_run_plan_validation_reasons",
    "back_forward_run_execution_conditions",
    "back_forward_run_per_step_timeout_seconds",
    "back_forward_run_since_minutes",
    "back_forward_run_min_closed",
    "back_forward_run_from_date",
    "back_forward_run_to_date",
    "back_forward_run_forward_mode",
    "back_forward_run_effective_from_date",
    "back_forward_run_effective_to_date",
    "back_forward_run_effective_forward_mode",
    "back_forward_run_sync_expert_parameters_set",
    "back_forward_run_allow_running_terminal",
    "back_forward_run_allow_stale_compile",
    "back_forward_run_allow_invalid_risk_preset",
    "back_forward_run_ready_status_ok",
    "back_forward_run_ready_status_reasons",
    "back_forward_run_ready_status_mismatches",
    "back_forward_run_ready_status_checked_step_keys",
    "back_forward_run_ready_status_checked_command_options",
    "back_forward_run_ready_status_checked_command_flags",
    "back_forward_run_ready_status_checked_execution_conditions",
    "back_forward_run_ready_status_expected_execution_conditions",
    "back_forward_run_ready_status_status_execution_conditions",
    "back_forward_run_archive_preview_output_json",
    "back_forward_run_archive_preview_output_md",
    "back_forward_run_archive_preview_output_json_by_step",
    "back_forward_run_archive_preview_validation_ok_by_step",
    "back_forward_run_performance_comparison_available",
    "back_forward_run_performance_comparison_status",
    "back_forward_run_performance_comparison_rows",
    "back_forward_run_performance_comparison_thresholds",
    "promotion_failed_check_names",
    "promotion_mt5_back_forward_run_check_value",
    "next_action_run_action_reason",
    "next_action_run_primary_note",
    "next_action_run_execute_command_text",
    "next_action_run_collect_only_command_text",
    "next_action_run_collect_only_note",
    "next_action_run_manual_collect_only_command_text",
    "next_action_run_manual_run_start_after",
    "next_action_run_manual_collect_ready",
    "next_action_run_manual_collect_status",
    "next_action_run_manual_collect_csv_count",
    "next_action_run_manual_collect_modified_after",
    "next_action_run_manual_collect_reason",
    "next_action_run_manual_collect_blocking_reasons",
    "next_action_run_manual_collect_next_action",
    "next_action_run_manual_step_count",
    "next_action_run_manual_steps",
    "next_action_run_evidence_role",
    "next_action_run_diagnostic_only",
    "next_action_run_promotion_evidence",
    "next_action_run_action_context_keys",
    "next_action_run_related_execution_count",
    "next_action_run_related_execution_keys",
    "next_action_run_blocking_prior_action_count",
    "next_action_run_blocking_prior_actions",
    "next_action_run_blocking_prior_action_summary",
    "next_action_run_advisory_prior_action_count",
    "next_action_run_advisory_prior_actions",
    "next_action_run_advisory_prior_action_summary",
    "next_action_run_current_for_execution",
    "next_action_run_gate_stale_reason",
    "next_action_run_runner_promotion_generated_at",
    "next_action_run_current_promotion_generated_at",
    "next_action_run_planned_outputs",
    "next_action_run_primary_planned_outputs",
    "next_action_run_archive_preview_planned_outputs",
    "next_action_run_follow_up_planned_outputs",
    "next_action_run_follow_up_archive_preview_planned_outputs",
    "next_action_run_archive_preview_output_json",
    "next_action_run_archive_preview_output_md",
    "next_action_run_follow_up_archive_preview_output_json",
    "next_action_run_follow_up_archive_preview_output_md",
    "next_action_run_score_weight_follow_up_status",
    "next_action_run_score_weight_follow_up_regime_status",
    "next_action_run_score_weight_follow_up_sample_shortage",
    "next_action_run_score_weight_follow_up_walk_missing",
    "next_action_run_score_weight_follow_up_walk_required",
    "next_action_run_score_weight_follow_up_walk_folds",
    "next_action_run_score_weight_follow_up_walk_required_folds",
    "next_action_run_score_weight_follow_up_regime_missing",
    "next_action_run_score_weight_follow_up_regime_required",
    "next_action_run_score_weight_follow_up_regime_folds",
    "next_action_run_score_weight_follow_up_regime_required_folds",
    "next_action_run_score_weight_set_walk_forward_status",
    "next_action_run_score_weight_set_skip_reason",
    "next_action_execution_collect_only_hint",
    "stable_candidate_refit_completed_kind",
    "stable_candidate_refit_completed_status",
    "stable_candidate_refit_completed_reasons",
)
STATUS_WATCH_RESTART_HINT = (
    "python3 analysis/mt5_tester_status_watch.py "
    "--interval-seconds 60 "
    f"--heartbeat {DEFAULT_STATUS_WATCH_HEARTBEAT} "
    f"--pid-file {DEFAULT_STATUS_WATCH_PID} "
    f"--manual-test-queue {DEFAULT_MANUAL_TEST_QUEUE} "
    f"--manual-queue-launch {DEFAULT_MANUAL_QUEUE_LAUNCH} "
    f"--manual-collect-run {DEFAULT_MANUAL_COLLECT_RUN} "
    f"--manual-test-queue-with-optimization {DEFAULT_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION} "
    f"--manual-queue-launch-with-optimization {DEFAULT_MANUAL_QUEUE_LAUNCH_WITH_OPTIMIZATION} "
    f"--manual-collect-with-optimization {DEFAULT_MANUAL_COLLECT_WITH_OPTIMIZATION} "
    f"--manual-operator-packet-with-optimization {DEFAULT_MANUAL_OPERATOR_PACKET_WITH_OPTIMIZATION}"
)
NEXT_ACTION_EXECUTION_REQUIRED_FRESH_ARTIFACTS = ("promotion_gate", "compile_status", "next_action_run")
LOCAL_NEXT_ACTION_PRIMARY_CLASSES = ("mt5_optimization_recommendation_refresh",)
LOCAL_NEXT_ACTION_REQUIRED_FRESH_ARTIFACTS = {
    "mt5_optimization_recommendation_refresh": ("promotion_gate", "optimization_report", "next_action_run"),
}
BACK_FORWARD_HINT_OPTIONS = (
    "--timeout-seconds",
    "--since-minutes",
    "--min-closed",
    "--from-date",
    "--to-date",
    "--forward-mode",
)
BACK_FORWARD_HINT_FLAGS = (
    "--sync-expert-parameters-set",
    "--allow-running-terminal",
    "--allow-stale-compile",
    "--allow-invalid-risk-preset",
)
BACK_FORWARD_RUNNER_HINT_CONDITION_OPTIONS = {
    "per_step_timeout_seconds": "--timeout-seconds",
    "since_minutes": "--since-minutes",
    "min_closed": "--min-closed",
    "from_date": "--from-date",
    "to_date": "--to-date",
    "forward_mode": "--forward-mode",
    "max_ready_status_age_seconds": "--max-ready-status-age-seconds",
}
BACK_FORWARD_RUNNER_HINT_CONDITION_FLAGS = {
    "sync_expert_parameters_set": "--sync-expert-parameters-set",
    "allow_running_terminal": "--allow-running-terminal",
    "allow_stale_compile": "--allow-stale-compile",
    "allow_invalid_risk_preset": "--allow-invalid-risk-preset",
    "skip_archive_preview": "--skip-archive-preview",
}


def load_optional_json(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    source = Path(path)
    if not source.exists():
        return {}
    with source.open(encoding="utf-8") as f:
        payload = json.load(f)
    return payload if isinstance(payload, dict) else {}


def artifact_freshness_entry(path: str | Path | None, *, now_epoch: float, max_age_seconds: int) -> dict[str, Any]:
    if not path:
        return {
            "path": "",
            "exists": False,
            "modified_at": "",
            "age_seconds": None,
            "max_age_seconds": max_age_seconds,
            "fresh": False,
        }
    source = Path(path)
    if not source.exists():
        return {
            "path": str(path),
            "exists": False,
            "modified_at": "",
            "age_seconds": None,
            "max_age_seconds": max_age_seconds,
            "fresh": False,
        }
    modified_epoch = source.stat().st_mtime
    age_seconds = max(0.0, now_epoch - modified_epoch)
    return {
        "path": str(path),
        "exists": True,
        "modified_at": datetime.fromtimestamp(modified_epoch).strftime(TIME_FORMAT),
        "age_seconds": round(age_seconds, 1),
        "max_age_seconds": max_age_seconds,
        "fresh": age_seconds <= max_age_seconds,
    }


def artifact_freshness_summary(
    *,
    tester_run_path: str | Path,
    promotion_gate_path: str | Path | None,
    compile_status_path: str | Path | None,
    optimization_report_path: str | Path | None,
    next_action_run_path: str | Path | None = None,
    back_forward_run_path: str | Path | None = None,
    manual_test_queue_path: str | Path | None = None,
    manual_queue_launch_path: str | Path | None = None,
    manual_collect_run_path: str | Path | None = None,
    manual_test_queue_with_optimization_path: str | Path | None = None,
    manual_queue_launch_with_optimization_path: str | Path | None = None,
    manual_collect_with_optimization_path: str | Path | None = None,
    manual_operator_packet_with_optimization_path: str | Path | None = None,
    manual_auto_collect_watch_path: str | Path | None = None,
    stable_candidate_report_path: str | Path | None = None,
    stable_candidate_recommendation_path: str | Path | None = None,
    stable_candidate_tester_run_path: str | Path | None = None,
    bridge_recovery_plan_path: str | Path | None = None,
    max_age_seconds: int,
) -> dict[str, Any]:
    now_epoch = time.time()
    return {
        "max_age_seconds": max_age_seconds,
        "artifacts": {
            "tester_run": artifact_freshness_entry(
                tester_run_path, now_epoch=now_epoch, max_age_seconds=max_age_seconds
            ),
            "promotion_gate": artifact_freshness_entry(
                promotion_gate_path, now_epoch=now_epoch, max_age_seconds=max_age_seconds
            ),
            "compile_status": artifact_freshness_entry(
                compile_status_path, now_epoch=now_epoch, max_age_seconds=max_age_seconds
            ),
            "optimization_report": artifact_freshness_entry(
                optimization_report_path, now_epoch=now_epoch, max_age_seconds=max_age_seconds
            ),
            "next_action_run": artifact_freshness_entry(
                next_action_run_path, now_epoch=now_epoch, max_age_seconds=max_age_seconds
            ),
            "back_forward_run": artifact_freshness_entry(
                back_forward_run_path, now_epoch=now_epoch, max_age_seconds=max_age_seconds
            ),
            "manual_test_queue": artifact_freshness_entry(
                manual_test_queue_path, now_epoch=now_epoch, max_age_seconds=max_age_seconds
            ),
            "manual_queue_launch": artifact_freshness_entry(
                manual_queue_launch_path, now_epoch=now_epoch, max_age_seconds=max_age_seconds
            ),
            "manual_collect_run": artifact_freshness_entry(
                manual_collect_run_path, now_epoch=now_epoch, max_age_seconds=max_age_seconds
            ),
            "manual_test_queue_with_optimization": artifact_freshness_entry(
                manual_test_queue_with_optimization_path,
                now_epoch=now_epoch,
                max_age_seconds=max_age_seconds,
            ),
            "manual_queue_launch_with_optimization": artifact_freshness_entry(
                manual_queue_launch_with_optimization_path,
                now_epoch=now_epoch,
                max_age_seconds=max_age_seconds,
            ),
            "manual_collect_with_optimization": artifact_freshness_entry(
                manual_collect_with_optimization_path,
                now_epoch=now_epoch,
                max_age_seconds=max_age_seconds,
            ),
            "manual_operator_packet_with_optimization": artifact_freshness_entry(
                manual_operator_packet_with_optimization_path,
                now_epoch=now_epoch,
                max_age_seconds=max_age_seconds,
            ),
            "manual_auto_collect_watch": artifact_freshness_entry(
                manual_auto_collect_watch_path,
                now_epoch=now_epoch,
                max_age_seconds=max_age_seconds,
            ),
            "stable_candidate_report": artifact_freshness_entry(
                stable_candidate_report_path, now_epoch=now_epoch, max_age_seconds=max_age_seconds
            ),
            "stable_candidate_recommendation": artifact_freshness_entry(
                stable_candidate_recommendation_path, now_epoch=now_epoch, max_age_seconds=max_age_seconds
            ),
            "stable_candidate_tester_run": artifact_freshness_entry(
                stable_candidate_tester_run_path, now_epoch=now_epoch, max_age_seconds=max_age_seconds
            ),
            "bridge_recovery_plan": artifact_freshness_entry(
                bridge_recovery_plan_path, now_epoch=now_epoch, max_age_seconds=max_age_seconds
            ),
        },
    }


def bridge_recovery_plan_summary(
    payload: dict[str, Any],
    *,
    path: str | Path | None,
) -> dict[str, Any]:
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    last_ea_post = checks.get("last_ea_post") if isinstance(checks.get("last_ea_post"), dict) else {}
    last_snapshot_post = checks.get("last_snapshot_post") if isinstance(checks.get("last_snapshot_post"), dict) else {}
    return {
        "exists": bool(payload),
        "path": str(path) if path else "",
        "ok": payload.get("ok"),
        "status": payload.get("status", ""),
        "ready_for_mt5_validation": payload.get("ready_for_mt5_validation"),
        "blocking_reasons": payload.get("blocking_reasons")
        if isinstance(payload.get("blocking_reasons"), list)
        else [],
        "next_action": payload.get("next_action", ""),
        "generated_at": payload.get("generated_at", ""),
        "bridge_status_loaded": checks.get("bridge_status_loaded"),
        "operational_status": checks.get("operational_status", ""),
        "health_ok": checks.get("health_ok"),
        "config_ok": checks.get("config_ok"),
        "bridge_process_running": checks.get("bridge_process_running"),
        "mt5_terminal_running": checks.get("mt5_terminal_running"),
        "snapshot_fresh": checks.get("snapshot_fresh"),
        "snapshot_age_seconds": checks.get("snapshot_age_seconds"),
        "snapshot_server_time": checks.get("snapshot_server_time", ""),
        "history_request_pending": checks.get("history_request_pending"),
        "history_request_stale_pending": checks.get("history_request_stale_pending"),
        "history_request_pending_age_seconds": checks.get("history_request_pending_age_seconds"),
        "history_request_id": checks.get("history_request_id", ""),
        "history_done_id": checks.get("history_done_id", ""),
        "history_done_matches_request": checks.get("history_done_matches_request"),
        "history_status_ok": checks.get("history_status_ok"),
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
        "bridge_log_activity_status": checks.get("bridge_log_activity_status", ""),
        "last_ea_post_at": last_ea_post.get("timestamp", ""),
        "last_ea_post_age_seconds": last_ea_post.get("age_seconds"),
        "last_snapshot_post_at": last_snapshot_post.get("timestamp", ""),
        "last_snapshot_post_age_seconds": last_snapshot_post.get("age_seconds"),
        "manual_steps": payload.get("manual_steps") if isinstance(payload.get("manual_steps"), list) else [],
        "commands": payload.get("commands") if isinstance(payload.get("commands"), list) else [],
    }


def status_watch_heartbeat_summary(
    path: str | Path | None,
    *,
    now_epoch: float | None = None,
    max_age_seconds: int = DEFAULT_STATUS_WATCH_HEARTBEAT_MAX_AGE_SECONDS,
    required_fields: tuple[str, ...] = STATUS_WATCH_HEARTBEAT_REQUIRED_FIELDS,
    expected_implementation_version: int = STATUS_WATCH_HEARTBEAT_IMPLEMENTATION_VERSION,
) -> dict[str, Any]:
    if not path:
        return {
            "path": "",
            "exists": False,
            "status": "missing",
            "fresh": False,
            "compatible": False,
            "missing_required_fields": list(required_fields),
            "expected_implementation_version": expected_implementation_version,
            "implementation_version_mismatch": True,
            "max_age_seconds": max_age_seconds,
            "restart_hint": STATUS_WATCH_RESTART_HINT,
        }
    source = Path(path)
    if not source.exists():
        return {
            "path": str(path),
            "exists": False,
            "status": "missing",
            "modified_at": "",
            "age_seconds": None,
            "max_age_seconds": max_age_seconds,
            "fresh": False,
            "compatible": False,
            "missing_required_fields": list(required_fields),
            "expected_implementation_version": expected_implementation_version,
            "implementation_version_mismatch": True,
            "restart_hint": STATUS_WATCH_RESTART_HINT,
        }
    now_epoch = time.time() if now_epoch is None else now_epoch
    modified_epoch = source.stat().st_mtime
    age_seconds = max(0.0, now_epoch - modified_epoch)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    implementation_version = payload.get("implementation_version", "")
    implementation_version_mismatch = implementation_version != expected_implementation_version
    missing = [field for field in required_fields if field not in payload]
    fresh = age_seconds <= max_age_seconds
    compatible = not missing and not implementation_version_mismatch
    if not fresh:
        heartbeat_status = "stale"
    elif not compatible:
        heartbeat_status = "incompatible"
    else:
        heartbeat_status = "ok"
    return {
        "path": str(path),
        "exists": True,
        "status": heartbeat_status,
        "modified_at": datetime.fromtimestamp(modified_epoch).strftime(TIME_FORMAT),
        "age_seconds": round(age_seconds, 1),
        "max_age_seconds": max_age_seconds,
        "fresh": fresh,
        "compatible": compatible,
        "missing_required_fields": missing,
        "expected_implementation_version": expected_implementation_version,
        "implementation_version_mismatch": implementation_version_mismatch,
        "restart_hint": STATUS_WATCH_RESTART_HINT if heartbeat_status != "ok" else "",
        "schema_version": payload.get("schema_version", ""),
        "implementation_version": implementation_version,
        "ok": payload.get("ok", ""),
        "status_ok": payload.get("status_ok", ""),
        "watcher_pid": payload.get("watcher_pid", ""),
        "pid_file": payload.get("pid_file", ""),
        "pid_file_written": payload.get("pid_file_written", ""),
        "run_index": payload.get("run_index", ""),
        "max_runs": payload.get("max_runs", ""),
        "continuous": payload.get("continuous", ""),
        "started_at": payload.get("started_at", ""),
        "finished_at": payload.get("finished_at", ""),
        "finished_epoch": payload.get("finished_epoch", ""),
        "returncode": payload.get("returncode", ""),
        "operational_status": payload.get("operational_status", ""),
        "bridge_recovery_plan_status": payload.get("bridge_recovery_plan_status", ""),
        "bridge_recovery_plan_ready_for_mt5_validation": payload.get(
            "bridge_recovery_plan_ready_for_mt5_validation", ""
        ),
        "bridge_recovery_plan_output_json": payload.get("bridge_recovery_plan_output_json", ""),
        "bridge_recovery_plan_output_md": payload.get("bridge_recovery_plan_output_md", ""),
        "bridge_recovery_plan_generated_at": payload.get("bridge_recovery_plan_generated_at", ""),
        "bridge_recovery_plan_blocking_reasons": payload.get(
            "bridge_recovery_plan_blocking_reasons", []
        ),
        "bridge_recovery_plan_next_action": payload.get("bridge_recovery_plan_next_action", ""),
        "bridge_recovery_plan_last_ea_post_age_seconds": payload.get(
            "bridge_recovery_plan_last_ea_post_age_seconds", ""
        ),
        "bridge_recovery_plan_history_data_fresh": payload.get(
            "bridge_recovery_plan_history_data_fresh", ""
        ),
        "bridge_recovery_plan_history_data_stale": payload.get(
            "bridge_recovery_plan_history_data_stale", ""
        ),
        "bridge_recovery_plan_history_status_server_time": payload.get(
            "bridge_recovery_plan_history_status_server_time", ""
        ),
        "bridge_recovery_plan_history_status_server_time_age_seconds": payload.get(
            "bridge_recovery_plan_history_status_server_time_age_seconds", ""
        ),
        "bridge_recovery_plan_history_status_m1_last_time": payload.get(
            "bridge_recovery_plan_history_status_m1_last_time", ""
        ),
        "bridge_recovery_plan_history_status_m1_last_time_age_seconds": payload.get(
            "bridge_recovery_plan_history_status_m1_last_time_age_seconds", ""
        ),
        "compile_all_compiled_fresh": payload.get("compile_all_compiled_fresh", ""),
        "compile_all_tester_sets_synced": payload.get("compile_all_tester_sets_synced", ""),
        "compile_all_tester_configs_synced": payload.get("compile_all_tester_configs_synced", ""),
        "compile_all_required_tester_config_references_ready": payload.get(
            "compile_all_required_tester_config_references_ready",
            "",
        ),
        "compile_unsynced_tester_sets": payload.get("compile_unsynced_tester_sets", []),
        "compile_unsynced_tester_configs": payload.get("compile_unsynced_tester_configs", []),
        "compile_tester_config_reference_issues": payload.get("compile_tester_config_reference_issues", []),
        "ready_for_tester_launch": payload.get("ready_for_tester_launch", ""),
        "next_action_execution_ready": payload.get("next_action_execution_ready", ""),
        "mt5_next_operator_action": payload.get("mt5_next_operator_action", ""),
        "mt5_next_operator_mode": payload.get("mt5_next_operator_mode", ""),
        "mt5_next_operator_launch_state": payload.get(
            "mt5_next_operator_launch_state", ""
        ),
        "mt5_next_queue_step": payload.get("mt5_next_queue_step", ""),
        "mt5_next_quick_input": payload.get("mt5_next_quick_input", {}),
        "mt5_next_step_operator_summary": payload.get(
            "mt5_next_step_operator_summary", ""
        ),
        "mt5_next_step_collect_filter_summary": payload.get(
            "mt5_next_step_collect_filter_summary", ""
        ),
        "mt5_next_manual_run_start_effective_after": payload.get(
            "mt5_next_manual_run_start_effective_after", ""
        ),
        "mt5_next_manual_run_start_effective_after_values": payload.get(
            "mt5_next_manual_run_start_effective_after_values", []
        ),
        "mt5_auto_launch_command_available": payload.get(
            "mt5_auto_launch_command_available", ""
        ),
        "mt5_auto_launch_blocked": payload.get("mt5_auto_launch_blocked", ""),
        "mt5_auto_launch_blocked_reasons": payload.get(
            "mt5_auto_launch_blocked_reasons", []
        ),
        "mt5_auto_launch_command_text": payload.get("mt5_auto_launch_command_text", ""),
        "mt5_auto_launch_note": payload.get("mt5_auto_launch_note", ""),
        "mt5_back_forward_quick_start_status": payload.get(
            "mt5_back_forward_quick_start_status", ""
        ),
        "mt5_back_forward_quick_start_quick_inputs": payload.get(
            "mt5_back_forward_quick_start_quick_inputs", []
        ),
        "mt5_back_forward_quick_start_current_quick_input": payload.get(
            "mt5_back_forward_quick_start_current_quick_input", {}
        ),
        "mt5_back_forward_quick_start_collect_command_text": payload.get(
            "mt5_back_forward_quick_start_collect_command_text", ""
        ),
        "mt5_strategy_operator_decision_status": payload.get(
            "mt5_strategy_operator_decision_status", ""
        ),
        "mt5_strategy_operator_decision_verdict": payload.get(
            "mt5_strategy_operator_decision_verdict", ""
        ),
        "mt5_strategy_operator_decision_primary_blocker": payload.get(
            "mt5_strategy_operator_decision_primary_blocker", ""
        ),
        "mt5_strategy_operator_decision_next_action": payload.get(
            "mt5_strategy_operator_decision_next_action", ""
        ),
        "mt5_strategy_operator_decision_command_text": payload.get(
            "mt5_strategy_operator_decision_command_text", ""
        ),
        "mt5_collect_dry_run_command_text": payload.get(
            "mt5_collect_dry_run_command_text", ""
        ),
        "mt5_collect_execute_command_text": payload.get(
            "mt5_collect_execute_command_text", ""
        ),
        "mt5_manual_queue_status": payload.get("mt5_manual_queue_status", ""),
        "mt5_manual_queue_progress_state": payload.get(
            "mt5_manual_queue_progress_state", ""
        ),
        "mt5_manual_queue_waiting_count": payload.get(
            "mt5_manual_queue_waiting_count", ""
        ),
        "mt5_manual_queue_step_launch_needed_count": payload.get(
            "mt5_manual_queue_step_launch_needed_count", ""
        ),
        "mt5_operator_handoff_quick_input": payload.get("mt5_operator_handoff_quick_input", {}),
        "mt5_operator_handoff_manual_queue_progress_state": payload.get(
            "mt5_operator_handoff_manual_queue_progress_state", ""
        ),
        "mt5_operator_handoff_next_step_operator_summary": payload.get(
            "mt5_operator_handoff_next_step_operator_summary", ""
        ),
        "mt5_operator_handoff_next_step_collect_filter_summary": payload.get(
            "mt5_operator_handoff_next_step_collect_filter_summary", ""
        ),
        "manual_strategy_tester_available": payload.get("manual_strategy_tester_available", ""),
        "manual_strategy_tester_recommended": payload.get("manual_strategy_tester_recommended", ""),
        "manual_strategy_tester_status": payload.get("manual_strategy_tester_status", ""),
        "manual_strategy_tester_reasons": payload.get("manual_strategy_tester_reasons", []),
        "manual_strategy_tester_auto_launch_ready": payload.get("manual_strategy_tester_auto_launch_ready", ""),
        "manual_strategy_tester_auto_launch_status": payload.get("manual_strategy_tester_auto_launch_status", ""),
        "manual_strategy_tester_auto_launch_blockers": payload.get(
            "manual_strategy_tester_auto_launch_blockers", []
        ),
        "manual_strategy_tester_auto_launch_blocked_by_running_terminal": payload.get(
            "manual_strategy_tester_auto_launch_blocked_by_running_terminal", ""
        ),
        "manual_strategy_tester_terminal_running": payload.get("manual_strategy_tester_terminal_running", ""),
        "manual_strategy_tester_collect_only_command_text": payload.get(
            "manual_strategy_tester_collect_only_command_text", ""
        ),
        "manual_strategy_tester_collect_only_note": payload.get("manual_strategy_tester_collect_only_note", ""),
        "manual_strategy_tester_manual_run_start_after": payload.get(
            "manual_strategy_tester_manual_run_start_after", ""
        ),
        "manual_strategy_tester_step_count": payload.get("manual_strategy_tester_step_count", ""),
        "manual_strategy_tester_steps": payload.get("manual_strategy_tester_steps", []),
        "manual_strategy_tester_note": payload.get("manual_strategy_tester_note", ""),
        "manual_test_queue_exists": payload.get("manual_test_queue_exists", ""),
        "manual_test_queue_path": payload.get("manual_test_queue_path", ""),
        "manual_test_queue_generated_at": payload.get("manual_test_queue_generated_at", ""),
        "manual_test_queue_ok": payload.get("manual_test_queue_ok", ""),
        "manual_test_queue_status": payload.get("manual_test_queue_status", ""),
        "manual_test_queue_next_action": payload.get("manual_test_queue_next_action", ""),
        "manual_test_queue_progress_state": payload.get("manual_test_queue_progress_state", ""),
        "manual_test_queue_entry_count": payload.get("manual_test_queue_entry_count", ""),
        "manual_test_queue_total_entry_count": payload.get("manual_test_queue_total_entry_count", ""),
        "manual_test_queue_stale_entry_count": payload.get("manual_test_queue_stale_entry_count", ""),
        "manual_test_queue_current_for_execution_count": payload.get(
            "manual_test_queue_current_for_execution_count", ""
        ),
        "manual_test_queue_selected_action_present_count": payload.get(
            "manual_test_queue_selected_action_present_count", ""
        ),
        "manual_test_queue_selected_action_current_count": payload.get(
            "manual_test_queue_selected_action_current_count", ""
        ),
        "manual_test_queue_selected_action_stale_count": payload.get(
            "manual_test_queue_selected_action_stale_count", ""
        ),
        "manual_test_queue_current_promotion_generated_at_values": payload.get(
            "manual_test_queue_current_promotion_generated_at_values", []
        ),
        "manual_test_queue_current_promotion_decision_values": payload.get(
            "manual_test_queue_current_promotion_decision_values", []
        ),
        "manual_test_queue_gate_stale_reasons": payload.get("manual_test_queue_gate_stale_reasons", []),
        "manual_test_queue_not_current_entry_ids": payload.get("manual_test_queue_not_current_entry_ids", []),
        "manual_test_queue_manual_run_start_marked": payload.get(
            "manual_test_queue_manual_run_start_marked", ""
        ),
        "manual_test_queue_manual_run_start_marked_this_run": payload.get(
            "manual_test_queue_manual_run_start_marked_this_run", ""
        ),
        "manual_test_queue_manual_run_start_preserved": payload.get(
            "manual_test_queue_manual_run_start_preserved", ""
        ),
        "manual_test_queue_manual_run_start_state_count": payload.get(
            "manual_test_queue_manual_run_start_state_count", ""
        ),
        "manual_test_queue_manual_run_start_state_marked_count": payload.get(
            "manual_test_queue_manual_run_start_state_marked_count", ""
        ),
        "manual_test_queue_manual_run_start_effective_after_values": payload.get(
            "manual_test_queue_manual_run_start_effective_after_values", []
        ),
        "manual_test_queue_manual_run_start_after_override": payload.get(
            "manual_test_queue_manual_run_start_after_override", ""
        ),
        "manual_test_queue_step_count": payload.get("manual_test_queue_step_count", ""),
        "manual_test_queue_ready_to_collect_count": payload.get(
            "manual_test_queue_ready_to_collect_count", ""
        ),
        "manual_test_queue_waiting_count": payload.get("manual_test_queue_waiting_count", ""),
        "manual_test_queue_step_report_ready_count": payload.get(
            "manual_test_queue_step_report_ready_count", ""
        ),
        "manual_test_queue_step_collect_ready_count": payload.get(
            "manual_test_queue_step_collect_ready_count", ""
        ),
        "manual_test_queue_step_waiting_report_count": payload.get(
            "manual_test_queue_step_waiting_report_count", ""
        ),
        "manual_test_queue_step_launch_needed_count": payload.get(
            "manual_test_queue_step_launch_needed_count", ""
        ),
        "manual_test_queue_step_report_ready_ids": payload.get(
            "manual_test_queue_step_report_ready_ids", []
        ),
        "manual_test_queue_step_collect_ready_ids": payload.get(
            "manual_test_queue_step_collect_ready_ids", []
        ),
        "manual_test_queue_step_waiting_report_ids": payload.get(
            "manual_test_queue_step_waiting_report_ids", []
        ),
        "manual_test_queue_step_launch_needed_ids": payload.get(
            "manual_test_queue_step_launch_needed_ids", []
        ),
        "manual_test_queue_collect_check_command_text": payload.get(
            "manual_test_queue_collect_check_command_text", ""
        ),
        "manual_test_queue_next_queue_step": payload.get(
            "manual_test_queue_next_queue_step", ""
        ),
        "manual_test_queue_quick_input": payload.get("manual_test_queue_quick_input", {}),
        "manual_test_queue_next_quick_input": payload.get(
            "manual_test_queue_next_quick_input", {}
        ),
        "manual_test_queue_next_launch_step": payload.get("manual_test_queue_next_launch_step", {}),
        "manual_test_queue_all_collect_ready": payload.get("manual_test_queue_all_collect_ready", ""),
        "manual_test_queue_blocking_reasons": payload.get("manual_test_queue_blocking_reasons", []),
        "manual_test_queue_entries": payload.get("manual_test_queue_entries", []),
        "manual_test_queue_strategy_tester_targets": payload.get(
            "manual_test_queue_strategy_tester_targets", []
        ),
        "manual_test_queue_operation_cards": payload.get("manual_test_queue_operation_cards", []),
        "manual_test_queue_execution_checklist": payload.get("manual_test_queue_execution_checklist", []),
        "manual_test_queue_operator_handoff": payload.get("manual_test_queue_operator_handoff", {}),
        "manual_test_queue_operator_handoff_quick_input": payload.get(
            "manual_test_queue_operator_handoff_quick_input", {}
        ),
        "manual_test_queue_next_step_operator_summary": payload.get(
            "manual_test_queue_next_step_operator_summary", ""
        ),
        "manual_test_queue_next_step_collect_filter_summary": payload.get(
            "manual_test_queue_next_step_collect_filter_summary", ""
        ),
        "manual_queue_launch_exists": payload.get("manual_queue_launch_exists", ""),
        "manual_queue_launch_path": payload.get("manual_queue_launch_path", ""),
        "manual_queue_launch_generated_at": payload.get("manual_queue_launch_generated_at", ""),
        "manual_queue_launch_ok": payload.get("manual_queue_launch_ok", ""),
        "manual_queue_launch_status": payload.get("manual_queue_launch_status", ""),
        "manual_queue_launch_next_action": payload.get("manual_queue_launch_next_action", ""),
        "manual_queue_launch_queue_path": payload.get("manual_queue_launch_queue_path", ""),
        "manual_queue_launch_queue_status": payload.get("manual_queue_launch_queue_status", ""),
        "manual_queue_launch_queue_next_action": payload.get("manual_queue_launch_queue_next_action", ""),
        "manual_queue_launch_queue_operator_handoff_state": payload.get(
            "manual_queue_launch_queue_operator_handoff_state", ""
        ),
        "manual_queue_launch_queue_operator_handoff_next_mt5_step": payload.get(
            "manual_queue_launch_queue_operator_handoff_next_mt5_step", {}
        ),
        "manual_queue_launch_queue_operator_handoff_quick_input": payload.get(
            "manual_queue_launch_queue_operator_handoff_quick_input", {}
        ),
        "manual_queue_launch_queue_operator_handoff_collect_ready": payload.get(
            "manual_queue_launch_queue_operator_handoff_collect_ready", ""
        ),
        "manual_queue_launch_queue_operator_handoff_waiting_entry_ids": payload.get(
            "manual_queue_launch_queue_operator_handoff_waiting_entry_ids", []
        ),
        "manual_queue_launch_queue_operator_handoff_collect_dry_run_command_text": payload.get(
            "manual_queue_launch_queue_operator_handoff_collect_dry_run_command_text", ""
        ),
        "manual_queue_launch_queue_operator_handoff_collect_execute_command_text": payload.get(
            "manual_queue_launch_queue_operator_handoff_collect_execute_command_text", ""
        ),
        "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_analysis_command_text": payload.get(
            "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_analysis_command_text", ""
        ),
        "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_all_command_text": payload.get(
            "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_all_command_text", ""
        ),
        "manual_queue_launch_execute": payload.get("manual_queue_launch_execute", ""),
        "manual_queue_launch_detached": payload.get("manual_queue_launch_detached", ""),
        "manual_queue_launch_selected": payload.get("manual_queue_launch_selected", ""),
        "manual_queue_launch_selected_item": payload.get("manual_queue_launch_selected_item", {}),
        "manual_queue_launch_selected_matches_queue_handoff": payload.get(
            "manual_queue_launch_selected_matches_queue_handoff", ""
        ),
        "manual_queue_launch_launch_command_kind": payload.get("manual_queue_launch_launch_command_kind", ""),
        "manual_queue_launch_command_text": payload.get("manual_queue_launch_command_text", ""),
        "manual_queue_launch_mark_manual_run_start": payload.get(
            "manual_queue_launch_mark_manual_run_start", ""
        ),
        "manual_queue_launch_manual_run_start_mark_status": payload.get(
            "manual_queue_launch_manual_run_start_mark_status", ""
        ),
        "manual_queue_launch_manual_run_start_mark_attempted": payload.get(
            "manual_queue_launch_manual_run_start_mark_attempted", ""
        ),
        "manual_queue_launch_manual_run_start_after": payload.get(
            "manual_queue_launch_manual_run_start_after", ""
        ),
        "manual_queue_launch_blocked": payload.get("manual_queue_launch_blocked", ""),
        "manual_queue_launch_blocked_reasons": payload.get("manual_queue_launch_blocked_reasons", []),
        "manual_queue_launch_running_terminal_count": payload.get(
            "manual_queue_launch_running_terminal_count", ""
        ),
        "manual_queue_launch_process_pid": payload.get("manual_queue_launch_process_pid", ""),
        "manual_queue_launch_refresh_enabled": payload.get(
            "manual_queue_launch_refresh_enabled", ""
        ),
        "manual_queue_launch_refresh_command": payload.get("manual_queue_launch_refresh_command", []),
        "manual_queue_launch_refresh_returncode": payload.get(
            "manual_queue_launch_refresh_returncode", ""
        ),
        "manual_queue_launch_refresh_completed": payload.get(
            "manual_queue_launch_refresh_completed", ""
        ),
        "manual_queue_launch_refresh_status": payload.get("manual_queue_launch_refresh_status", ""),
        "manual_queue_launch_refresh_queue_refresh_status": payload.get(
            "manual_queue_launch_refresh_queue_refresh_status", ""
        ),
        "manual_queue_launch_refresh_queue_refresh_ok": payload.get(
            "manual_queue_launch_refresh_queue_refresh_ok", ""
        ),
        "manual_queue_launch_refresh_queue_refresh_source_count": payload.get(
            "manual_queue_launch_refresh_queue_refresh_source_count", ""
        ),
        "manual_queue_launch_refresh_selected": payload.get(
            "manual_queue_launch_refresh_selected", ""
        ),
        "manual_queue_launch_refresh_selected_queue_id": payload.get(
            "manual_queue_launch_refresh_selected_queue_id", ""
        ),
        "manual_queue_launch_refresh_selected_step_label": payload.get(
            "manual_queue_launch_refresh_selected_step_label", ""
        ),
        "manual_queue_launch_refresh_blocked": payload.get("manual_queue_launch_refresh_blocked", ""),
        "manual_queue_launch_refresh_blocked_reasons": payload.get(
            "manual_queue_launch_refresh_blocked_reasons", []
        ),
        "manual_queue_launch_refresh_output_json": payload.get(
            "manual_queue_launch_refresh_output_json", ""
        ),
        "manual_queue_launch_refresh_output_md": payload.get(
            "manual_queue_launch_refresh_output_md", ""
        ),
        "manual_queue_launch_refresh_stdout_tail": payload.get(
            "manual_queue_launch_refresh_stdout_tail", ""
        ),
        "manual_queue_launch_refresh_stderr_tail": payload.get(
            "manual_queue_launch_refresh_stderr_tail", ""
        ),
        "manual_collect_run_exists": payload.get("manual_collect_run_exists", ""),
        "manual_collect_run_path": payload.get("manual_collect_run_path", ""),
        "manual_collect_run_generated_at": payload.get("manual_collect_run_generated_at", ""),
        "manual_collect_run_ok": payload.get("manual_collect_run_ok", ""),
        "manual_collect_run_status": payload.get("manual_collect_run_status", ""),
        "manual_collect_run_next_action": payload.get("manual_collect_run_next_action", ""),
        "manual_collect_run_execute": payload.get("manual_collect_run_execute", ""),
        "manual_collect_run_dry_run": payload.get("manual_collect_run_dry_run", ""),
        "manual_collect_run_queue_path": payload.get("manual_collect_run_queue_path", ""),
        "manual_collect_run_queue_generated_at": payload.get("manual_collect_run_queue_generated_at", ""),
        "manual_collect_run_queue_status": payload.get("manual_collect_run_queue_status", ""),
        "manual_collect_run_queue_next_action": payload.get("manual_collect_run_queue_next_action", ""),
        "manual_collect_run_queue_step_count": payload.get("manual_collect_run_queue_step_count", ""),
        "manual_collect_run_queue_step_report_ready_count": payload.get(
            "manual_collect_run_queue_step_report_ready_count", ""
        ),
        "manual_collect_run_queue_step_collect_ready_count": payload.get(
            "manual_collect_run_queue_step_collect_ready_count", ""
        ),
        "manual_collect_run_queue_step_waiting_report_count": payload.get(
            "manual_collect_run_queue_step_waiting_report_count", ""
        ),
        "manual_collect_run_queue_step_launch_needed_count": payload.get(
            "manual_collect_run_queue_step_launch_needed_count", ""
        ),
        "manual_collect_run_entry_count": payload.get("manual_collect_run_entry_count", ""),
        "manual_collect_run_ready_entry_count": payload.get("manual_collect_run_ready_entry_count", ""),
        "manual_collect_run_selected_count": payload.get("manual_collect_run_selected_count", ""),
        "manual_collect_run_waiting_count": payload.get("manual_collect_run_waiting_count", ""),
        "manual_collect_run_invalid_count": payload.get("manual_collect_run_invalid_count", ""),
        "manual_collect_run_planned_count": payload.get("manual_collect_run_planned_count", ""),
        "manual_collect_run_skipped_count": payload.get("manual_collect_run_skipped_count", ""),
        "manual_collect_run_execution_count": payload.get("manual_collect_run_execution_count", ""),
        "manual_collect_run_queue_refresh_enabled": payload.get(
            "manual_collect_run_queue_refresh_enabled", ""
        ),
        "manual_collect_run_queue_refresh_ok": payload.get("manual_collect_run_queue_refresh_ok", ""),
        "manual_collect_run_queue_refresh_status": payload.get(
            "manual_collect_run_queue_refresh_status", ""
        ),
        "manual_collect_run_queue_refresh_source_count": payload.get(
            "manual_collect_run_queue_refresh_source_count", ""
        ),
        "manual_collect_run_handoff_state": payload.get("manual_collect_run_handoff_state", ""),
        "manual_collect_run_handoff_ready_ids": payload.get("manual_collect_run_handoff_ready_ids", []),
        "manual_collect_run_handoff_waiting_ids": payload.get("manual_collect_run_handoff_waiting_ids", []),
        "manual_collect_run_handoff_invalid_ids": payload.get("manual_collect_run_handoff_invalid_ids", []),
        "manual_collect_run_handoff_next_mt5_step": payload.get(
            "manual_collect_run_handoff_next_mt5_step", {}
        ),
        "manual_collect_run_handoff_quick_input": payload.get(
            "manual_collect_run_handoff_quick_input", {}
        ),
        "manual_collect_run_handoff_dry_run_command_text": payload.get(
            "manual_collect_run_handoff_dry_run_command_text", ""
        ),
        "manual_collect_run_handoff_execute_command_text": payload.get(
            "manual_collect_run_handoff_execute_command_text", ""
        ),
        "manual_collect_run_step_completion_audit": payload.get(
            "manual_collect_run_step_completion_audit", []
        ),
        "manual_collect_run_planned": payload.get("manual_collect_run_planned", []),
        "manual_collect_run_skipped": payload.get("manual_collect_run_skipped", []),
        "manual_collect_run_invalid": payload.get("manual_collect_run_invalid", []),
        "manual_collect_run_executions": payload.get("manual_collect_run_executions", []),
        "manual_collect_refresh_enabled": payload.get("manual_collect_refresh_enabled", ""),
        "manual_collect_refresh_command": payload.get("manual_collect_refresh_command", []),
        "manual_collect_refresh_returncode": payload.get("manual_collect_refresh_returncode", ""),
        "manual_collect_refresh_completed": payload.get("manual_collect_refresh_completed", ""),
        "manual_collect_refresh_status": payload.get("manual_collect_refresh_status", ""),
        "manual_collect_refresh_queue_refresh_status": payload.get(
            "manual_collect_refresh_queue_refresh_status", ""
        ),
        "manual_collect_refresh_queue_refresh_ok": payload.get(
            "manual_collect_refresh_queue_refresh_ok", ""
        ),
        "manual_collect_refresh_queue_refresh_source_count": payload.get(
            "manual_collect_refresh_queue_refresh_source_count", ""
        ),
        "manual_collect_refresh_selected_count": payload.get("manual_collect_refresh_selected_count", ""),
        "manual_collect_refresh_waiting_count": payload.get("manual_collect_refresh_waiting_count", ""),
        "manual_collect_refresh_invalid_count": payload.get("manual_collect_refresh_invalid_count", ""),
        "manual_collect_refresh_output_json": payload.get("manual_collect_refresh_output_json", ""),
        "manual_collect_refresh_output_md": payload.get("manual_collect_refresh_output_md", ""),
        "manual_collect_refresh_stdout_tail": payload.get("manual_collect_refresh_stdout_tail", ""),
        "manual_collect_refresh_stderr_tail": payload.get("manual_collect_refresh_stderr_tail", ""),
        "manual_auto_collect_watch_exists": payload.get("manual_auto_collect_watch_exists", ""),
        "manual_auto_collect_watch_ok": payload.get("manual_auto_collect_watch_ok", ""),
        "manual_auto_collect_watch_status": payload.get("manual_auto_collect_watch_status", ""),
        "manual_auto_collect_watch_next_action": payload.get(
            "manual_auto_collect_watch_next_action", ""
        ),
        "manual_auto_collect_watch_execute_ready": payload.get(
            "manual_auto_collect_watch_execute_ready", ""
        ),
        "manual_auto_collect_watch_ready_to_execute": payload.get(
            "manual_auto_collect_watch_ready_to_execute", ""
        ),
        "manual_auto_collect_watch_ready_for_collect_execute": payload.get(
            "manual_auto_collect_watch_ready_for_collect_execute", ""
        ),
        "manual_auto_collect_watch_selected_count": payload.get(
            "manual_auto_collect_watch_selected_count", ""
        ),
        "manual_auto_collect_watch_waiting_count": payload.get(
            "manual_auto_collect_watch_waiting_count", ""
        ),
        "manual_auto_collect_watch_invalid_count": payload.get(
            "manual_auto_collect_watch_invalid_count", ""
        ),
        "manual_auto_collect_watch_collect_dry_run_command_text": payload.get(
            "manual_auto_collect_watch_collect_dry_run_command_text", ""
        ),
        "manual_auto_collect_watch_collect_execute_command_text": payload.get(
            "manual_auto_collect_watch_collect_execute_command_text", ""
        ),
        "manual_auto_collect_watch_queue_launch_status": payload.get(
            "manual_auto_collect_watch_queue_launch_status", ""
        ),
        "manual_auto_collect_watch_queue_launch_blocked": payload.get(
            "manual_auto_collect_watch_queue_launch_blocked", ""
        ),
        "manual_auto_collect_watch_queue_launch_blocked_reasons": payload.get(
            "manual_auto_collect_watch_queue_launch_blocked_reasons", []
        ),
        "manual_auto_collect_watch_operator_packet_next_queue_step": payload.get(
            "manual_auto_collect_watch_operator_packet_next_queue_step", ""
        ),
        "manual_auto_collect_watch_operator_packet_auto_launch_command_text": payload.get(
            "manual_auto_collect_watch_operator_packet_auto_launch_command_text", ""
        ),
        "manual_auto_collect_watch_operator_packet_auto_launch_command_available": payload.get(
            "manual_auto_collect_watch_operator_packet_auto_launch_command_available", ""
        ),
        "manual_auto_collect_watch_operator_packet_auto_launch_blocked": payload.get(
            "manual_auto_collect_watch_operator_packet_auto_launch_blocked", ""
        ),
        "manual_auto_collect_watch_operator_packet_auto_launch_blocked_reasons": payload.get(
            "manual_auto_collect_watch_operator_packet_auto_launch_blocked_reasons", []
        ),
        "manual_auto_collect_watch_operator_packet_auto_launch_note": payload.get(
            "manual_auto_collect_watch_operator_packet_auto_launch_note", ""
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_status": (
            payload.get(
                "manual_auto_collect_watch_operator_packet_strategy_operator_decision_status",
                "",
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_verdict": (
            payload.get(
                "manual_auto_collect_watch_operator_packet_strategy_operator_decision_verdict",
                "",
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_adoptable": (
            payload.get(
                "manual_auto_collect_watch_operator_packet_strategy_operator_decision_adoptable",
                "",
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_primary_blocker": (
            payload.get(
                "manual_auto_collect_watch_operator_packet_strategy_operator_decision_primary_blocker",
                "",
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_primary_reason": (
            payload.get(
                "manual_auto_collect_watch_operator_packet_strategy_operator_decision_primary_reason",
                "",
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_next_action": (
            payload.get(
                "manual_auto_collect_watch_operator_packet_strategy_operator_decision_next_action",
                "",
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_summary": (
            payload.get(
                "manual_auto_collect_watch_operator_packet_strategy_operator_decision_summary",
                "",
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_command_text": (
            payload.get(
                "manual_auto_collect_watch_operator_packet_strategy_operator_decision_command_text",
                "",
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_follow_up_command_text": (
            payload.get(
                "manual_auto_collect_watch_operator_packet_strategy_operator_decision_follow_up_command_text",
                "",
            )
        ),
        "manual_auto_collect_watch_execution_enabled": payload.get(
            "manual_auto_collect_watch_execution_enabled", ""
        ),
        "manual_auto_collect_watch_execution_attempted": payload.get(
            "manual_auto_collect_watch_execution_attempted", ""
        ),
        "manual_auto_collect_watch_execution_returncode": payload.get(
            "manual_auto_collect_watch_execution_returncode", ""
        ),
        "manual_auto_collect_watch_execution_status": payload.get(
            "manual_auto_collect_watch_execution_status", ""
        ),
        "manual_test_queue_with_optimization_exists": payload.get(
            "manual_test_queue_with_optimization_exists", ""
        ),
        "manual_test_queue_with_optimization_status": payload.get(
            "manual_test_queue_with_optimization_status", ""
        ),
        "manual_test_queue_with_optimization_next_action": payload.get(
            "manual_test_queue_with_optimization_next_action", ""
        ),
        "manual_test_queue_with_optimization_progress_state": payload.get(
            "manual_test_queue_with_optimization_progress_state", ""
        ),
        "manual_test_queue_with_optimization_entry_count": payload.get(
            "manual_test_queue_with_optimization_entry_count", ""
        ),
        "manual_test_queue_with_optimization_total_entry_count": payload.get(
            "manual_test_queue_with_optimization_total_entry_count", ""
        ),
        "manual_test_queue_with_optimization_stale_entry_count": payload.get(
            "manual_test_queue_with_optimization_stale_entry_count", ""
        ),
        "manual_test_queue_with_optimization_manual_run_start_marked": payload.get(
            "manual_test_queue_with_optimization_manual_run_start_marked", ""
        ),
        "manual_test_queue_with_optimization_manual_run_start_marked_this_run": payload.get(
            "manual_test_queue_with_optimization_manual_run_start_marked_this_run", ""
        ),
        "manual_test_queue_with_optimization_manual_run_start_preserved": payload.get(
            "manual_test_queue_with_optimization_manual_run_start_preserved", ""
        ),
        "manual_test_queue_with_optimization_manual_run_start_state_count": payload.get(
            "manual_test_queue_with_optimization_manual_run_start_state_count", ""
        ),
        "manual_test_queue_with_optimization_manual_run_start_state_marked_count": payload.get(
            "manual_test_queue_with_optimization_manual_run_start_state_marked_count", ""
        ),
        "manual_test_queue_with_optimization_manual_run_start_effective_after_values": (
            payload.get(
                "manual_test_queue_with_optimization_manual_run_start_effective_after_values",
                [],
            )
        ),
        "manual_test_queue_with_optimization_manual_run_start_after_override": payload.get(
            "manual_test_queue_with_optimization_manual_run_start_after_override", ""
        ),
        "manual_test_queue_with_optimization_step_count": payload.get(
            "manual_test_queue_with_optimization_step_count", ""
        ),
        "manual_test_queue_with_optimization_ready_to_collect_count": payload.get(
            "manual_test_queue_with_optimization_ready_to_collect_count", ""
        ),
        "manual_test_queue_with_optimization_waiting_count": payload.get(
            "manual_test_queue_with_optimization_waiting_count", ""
        ),
        "manual_test_queue_with_optimization_step_report_ready_count": payload.get(
            "manual_test_queue_with_optimization_step_report_ready_count", ""
        ),
        "manual_test_queue_with_optimization_step_collect_ready_count": payload.get(
            "manual_test_queue_with_optimization_step_collect_ready_count", ""
        ),
        "manual_test_queue_with_optimization_step_waiting_report_count": payload.get(
            "manual_test_queue_with_optimization_step_waiting_report_count", ""
        ),
        "manual_test_queue_with_optimization_step_launch_needed_count": payload.get(
            "manual_test_queue_with_optimization_step_launch_needed_count", ""
        ),
        "manual_test_queue_with_optimization_step_report_ready_ids": payload.get(
            "manual_test_queue_with_optimization_step_report_ready_ids", []
        ),
        "manual_test_queue_with_optimization_step_collect_ready_ids": payload.get(
            "manual_test_queue_with_optimization_step_collect_ready_ids", []
        ),
        "manual_test_queue_with_optimization_step_waiting_report_ids": payload.get(
            "manual_test_queue_with_optimization_step_waiting_report_ids", []
        ),
        "manual_test_queue_with_optimization_step_launch_needed_ids": payload.get(
            "manual_test_queue_with_optimization_step_launch_needed_ids", []
        ),
        "manual_test_queue_with_optimization_collect_check_command_text": payload.get(
            "manual_test_queue_with_optimization_collect_check_command_text", ""
        ),
        "manual_test_queue_with_optimization_next_queue_step": payload.get(
            "manual_test_queue_with_optimization_next_queue_step", ""
        ),
        "manual_test_queue_with_optimization_quick_input": payload.get(
            "manual_test_queue_with_optimization_quick_input", {}
        ),
        "manual_test_queue_with_optimization_next_quick_input": payload.get(
            "manual_test_queue_with_optimization_next_quick_input", {}
        ),
        "manual_test_queue_with_optimization_next_launch_step": payload.get(
            "manual_test_queue_with_optimization_next_launch_step", {}
        ),
        "manual_test_queue_with_optimization_all_collect_ready": payload.get(
            "manual_test_queue_with_optimization_all_collect_ready", ""
        ),
        "manual_test_queue_with_optimization_blocking_reasons": payload.get(
            "manual_test_queue_with_optimization_blocking_reasons", []
        ),
        "manual_test_queue_with_optimization_static_strategy_config_count": payload.get(
            "manual_test_queue_with_optimization_static_strategy_config_count", ""
        ),
        "manual_test_queue_with_optimization_static_strategy_configs": payload.get(
            "manual_test_queue_with_optimization_static_strategy_configs", []
        ),
        "manual_test_queue_with_optimization_static_candidate_label_count": payload.get(
            "manual_test_queue_with_optimization_static_candidate_label_count", ""
        ),
        "manual_test_queue_with_optimization_static_candidate_labels": payload.get(
            "manual_test_queue_with_optimization_static_candidate_labels", []
        ),
        "manual_test_queue_with_optimization_entries": payload.get(
            "manual_test_queue_with_optimization_entries", []
        ),
        "manual_test_queue_with_optimization_strategy_tester_targets": payload.get(
            "manual_test_queue_with_optimization_strategy_tester_targets", []
        ),
        "manual_test_queue_with_optimization_operation_cards": payload.get(
            "manual_test_queue_with_optimization_operation_cards", []
        ),
        "manual_test_queue_with_optimization_execution_checklist": payload.get(
            "manual_test_queue_with_optimization_execution_checklist", []
        ),
        "manual_test_queue_with_optimization_operator_handoff": payload.get(
            "manual_test_queue_with_optimization_operator_handoff", {}
        ),
        "manual_test_queue_with_optimization_operator_handoff_quick_input": payload.get(
            "manual_test_queue_with_optimization_operator_handoff_quick_input", {}
        ),
        "manual_test_queue_with_optimization_next_step_operator_summary": payload.get(
            "manual_test_queue_with_optimization_next_step_operator_summary", ""
        ),
        "manual_test_queue_with_optimization_next_step_collect_filter_summary": payload.get(
            "manual_test_queue_with_optimization_next_step_collect_filter_summary", ""
        ),
        "manual_operator_packet_with_optimization_next_operator_before_mt5_command_text": (
            payload.get(
                "manual_operator_packet_with_optimization_next_operator_before_mt5_command_text",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_auto_launch_command_text": payload.get(
            "manual_operator_packet_with_optimization_auto_launch_command_text", ""
        ),
        "manual_operator_packet_with_optimization_auto_launch_command_available": payload.get(
            "manual_operator_packet_with_optimization_auto_launch_command_available", ""
        ),
        "manual_operator_packet_with_optimization_auto_launch_blocked": payload.get(
            "manual_operator_packet_with_optimization_auto_launch_blocked", ""
        ),
        "manual_operator_packet_with_optimization_auto_launch_blocked_reasons": payload.get(
            "manual_operator_packet_with_optimization_auto_launch_blocked_reasons", []
        ),
        "manual_operator_packet_with_optimization_auto_launch_note": payload.get(
            "manual_operator_packet_with_optimization_auto_launch_note", ""
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_status": payload.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_status",
            "",
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_step_count": payload.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_step_count",
            "",
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_waiting_step_count": payload.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_waiting_step_count",
            "",
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_current_queue_step": payload.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_current_queue_step",
            "",
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_current_purpose": payload.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_current_purpose",
            "",
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_steps": payload.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_steps",
            [],
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_quick_inputs": payload.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_quick_inputs",
            [],
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_current_quick_input": payload.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_current_quick_input",
            {},
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_backtest_quick_input": payload.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_backtest_quick_input",
            {},
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_forward_quick_input": payload.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_forward_quick_input",
            {},
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_collect_command_text": payload.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_collect_command_text",
            "",
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_full_queue_collect_command_text": payload.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_full_queue_collect_command_text",
            "",
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_auto_launch_blocked": payload.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_auto_launch_blocked",
            "",
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_auto_launch_blocked_reasons": payload.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_auto_launch_blocked_reasons",
            [],
        ),
        "manual_operator_packet_with_optimization_back_forward_completion_summary": payload.get(
            "manual_operator_packet_with_optimization_back_forward_completion_summary",
            "",
        ),
        "manual_operator_packet_with_optimization_back_forward_completion_manual_run_start_after": payload.get(
            "manual_operator_packet_with_optimization_back_forward_completion_manual_run_start_after",
            "",
        ),
        "manual_operator_packet_with_optimization_back_forward_completion_expected_step_count": payload.get(
            "manual_operator_packet_with_optimization_back_forward_completion_expected_step_count",
            "",
        ),
        "manual_operator_packet_with_optimization_back_forward_completion_waiting_step_count": payload.get(
            "manual_operator_packet_with_optimization_back_forward_completion_waiting_step_count",
            "",
        ),
        "manual_operator_packet_with_optimization_back_forward_completion_collect_command_text": payload.get(
            "manual_operator_packet_with_optimization_back_forward_completion_collect_command_text",
            "",
        ),
        "manual_operator_packet_with_optimization_back_forward_completion_steps": payload.get(
            "manual_operator_packet_with_optimization_back_forward_completion_steps",
            [],
        ),
        "manual_operator_packet_with_optimization_back_forward_completion_decision_thresholds": payload.get(
            "manual_operator_packet_with_optimization_back_forward_completion_decision_thresholds",
            {},
        ),
        "manual_operator_packet_with_optimization_next_operator_quick_input": payload.get(
            "manual_operator_packet_with_optimization_next_operator_quick_input",
            payload.get("manual_operator_packet_with_optimization_next_step_quick_input", {}),
        ),
        "manual_operator_packet_with_optimization_next_step_quick_input": payload.get(
            "manual_operator_packet_with_optimization_next_step_quick_input", {}
        ),
        "manual_operator_packet_with_optimization_manual_run_start_marked": payload.get(
            "manual_operator_packet_with_optimization_manual_run_start_marked", ""
        ),
        "manual_operator_packet_with_optimization_manual_run_start_marked_this_run": (
            payload.get(
                "manual_operator_packet_with_optimization_manual_run_start_marked_this_run",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_manual_run_start_preserved": payload.get(
            "manual_operator_packet_with_optimization_manual_run_start_preserved", ""
        ),
        "manual_operator_packet_with_optimization_manual_run_start_state_count": payload.get(
            "manual_operator_packet_with_optimization_manual_run_start_state_count", ""
        ),
        "manual_operator_packet_with_optimization_manual_run_start_state_marked_count": (
            payload.get(
                "manual_operator_packet_with_optimization_manual_run_start_state_marked_count",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_manual_run_start_effective_after": payload.get(
            "manual_operator_packet_with_optimization_manual_run_start_effective_after", ""
        ),
        "manual_operator_packet_with_optimization_manual_run_start_effective_after_values": (
            payload.get(
                "manual_operator_packet_with_optimization_manual_run_start_effective_after_values",
                [],
            )
        ),
        "manual_operator_packet_with_optimization_manual_run_start_after_override": payload.get(
            "manual_operator_packet_with_optimization_manual_run_start_after_override", ""
        ),
        "manual_operator_packet_with_optimization_next_step_operator_summary": payload.get(
            "manual_operator_packet_with_optimization_next_step_operator_summary", ""
        ),
        "manual_operator_packet_with_optimization_next_step_collect_filter_summary": payload.get(
            "manual_operator_packet_with_optimization_next_step_collect_filter_summary", ""
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_status": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_back_forward_decision_status",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_adoptable": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_back_forward_decision_adoptable",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_next_action": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_back_forward_decision_next_action",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_reason": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_back_forward_decision_reason",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_collect_command_text": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_back_forward_decision_collect_command_text",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_command_text": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_command_text",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_range_strategy": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_range_strategy",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_status": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_operator_decision_status",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_verdict": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_operator_decision_verdict",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_adoptable": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_operator_decision_adoptable",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_primary_blocker": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_operator_decision_primary_blocker",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_primary_reason": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_operator_decision_primary_reason",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_next_action": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_operator_decision_next_action",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_summary": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_operator_decision_summary",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_command_text": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_operator_decision_command_text",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_follow_up_command_text": (
            payload.get(
                "manual_operator_packet_with_optimization_strategy_operator_decision_follow_up_command_text",
                "",
            )
        ),
        "manual_queue_launch_with_optimization_status": payload.get(
            "manual_queue_launch_with_optimization_status", ""
        ),
        "manual_queue_launch_with_optimization_next_action": payload.get(
            "manual_queue_launch_with_optimization_next_action", ""
        ),
        "manual_queue_launch_with_optimization_selected": payload.get(
            "manual_queue_launch_with_optimization_selected", ""
        ),
        "manual_queue_launch_with_optimization_selected_item": payload.get(
            "manual_queue_launch_with_optimization_selected_item", {}
        ),
        "manual_queue_launch_with_optimization_selected_matches_queue_handoff": payload.get(
            "manual_queue_launch_with_optimization_selected_matches_queue_handoff", ""
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_state": payload.get(
            "manual_queue_launch_with_optimization_queue_operator_handoff_state", ""
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_next_mt5_step": payload.get(
            "manual_queue_launch_with_optimization_queue_operator_handoff_next_mt5_step", {}
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_collect_ready": payload.get(
            "manual_queue_launch_with_optimization_queue_operator_handoff_collect_ready", ""
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_waiting_entry_ids": payload.get(
            "manual_queue_launch_with_optimization_queue_operator_handoff_waiting_entry_ids", []
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_collect_dry_run_command_text": payload.get(
            "manual_queue_launch_with_optimization_queue_operator_handoff_collect_dry_run_command_text", ""
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_command_text": payload.get(
            "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_command_text", ""
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_analysis_command_text": payload.get(
            "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_analysis_command_text", ""
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_all_command_text": payload.get(
            "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_all_command_text", ""
        ),
        "manual_queue_launch_with_optimization_launch_command_kind": payload.get(
            "manual_queue_launch_with_optimization_launch_command_kind", ""
        ),
        "manual_queue_launch_with_optimization_mark_manual_run_start": payload.get(
            "manual_queue_launch_with_optimization_mark_manual_run_start", ""
        ),
        "manual_queue_launch_with_optimization_manual_run_start_mark_status": payload.get(
            "manual_queue_launch_with_optimization_manual_run_start_mark_status", ""
        ),
        "manual_queue_launch_with_optimization_manual_run_start_mark_attempted": payload.get(
            "manual_queue_launch_with_optimization_manual_run_start_mark_attempted", ""
        ),
        "manual_queue_launch_with_optimization_manual_run_start_after": payload.get(
            "manual_queue_launch_with_optimization_manual_run_start_after", ""
        ),
        "manual_queue_launch_with_optimization_blocked": payload.get(
            "manual_queue_launch_with_optimization_blocked", ""
        ),
        "manual_queue_launch_with_optimization_blocked_reasons": payload.get(
            "manual_queue_launch_with_optimization_blocked_reasons", []
        ),
        "manual_queue_launch_with_optimization_running_terminal_count": payload.get(
            "manual_queue_launch_with_optimization_running_terminal_count", ""
        ),
        "manual_collect_with_optimization_status": payload.get(
            "manual_collect_with_optimization_status", ""
        ),
        "manual_collect_with_optimization_next_action": payload.get(
            "manual_collect_with_optimization_next_action", ""
        ),
        "manual_collect_with_optimization_selected_count": payload.get(
            "manual_collect_with_optimization_selected_count", ""
        ),
        "manual_collect_with_optimization_waiting_count": payload.get(
            "manual_collect_with_optimization_waiting_count", ""
        ),
        "manual_collect_with_optimization_invalid_count": payload.get(
            "manual_collect_with_optimization_invalid_count", ""
        ),
        "manual_collect_with_optimization_queue_step_count": payload.get(
            "manual_collect_with_optimization_queue_step_count", ""
        ),
        "manual_collect_with_optimization_queue_step_waiting_report_count": payload.get(
            "manual_collect_with_optimization_queue_step_waiting_report_count", ""
        ),
        "manual_collect_with_optimization_queue_step_launch_needed_count": payload.get(
            "manual_collect_with_optimization_queue_step_launch_needed_count", ""
        ),
        "manual_collect_with_optimization_refresh_enabled": payload.get(
            "manual_collect_with_optimization_refresh_enabled", ""
        ),
        "manual_collect_with_optimization_refresh_returncode": payload.get(
            "manual_collect_with_optimization_refresh_returncode", ""
        ),
        "manual_collect_with_optimization_refresh_completed": payload.get(
            "manual_collect_with_optimization_refresh_completed", ""
        ),
        "manual_collect_with_optimization_refresh_status": payload.get(
            "manual_collect_with_optimization_refresh_status", ""
        ),
        "manual_collect_with_optimization_refresh_queue_refresh_status": payload.get(
            "manual_collect_with_optimization_refresh_queue_refresh_status", ""
        ),
        "manual_collect_with_optimization_refresh_queue_refresh_ok": payload.get(
            "manual_collect_with_optimization_refresh_queue_refresh_ok", ""
        ),
        "manual_collect_with_optimization_refresh_queue_refresh_source_count": payload.get(
            "manual_collect_with_optimization_refresh_queue_refresh_source_count", ""
        ),
        "manual_collect_with_optimization_refresh_selected_count": payload.get(
            "manual_collect_with_optimization_refresh_selected_count", ""
        ),
        "manual_collect_with_optimization_refresh_waiting_count": payload.get(
            "manual_collect_with_optimization_refresh_waiting_count", ""
        ),
        "manual_collect_with_optimization_refresh_invalid_count": payload.get(
            "manual_collect_with_optimization_refresh_invalid_count", ""
        ),
        "manual_queue_launch_with_optimization_refresh_enabled": payload.get(
            "manual_queue_launch_with_optimization_refresh_enabled", ""
        ),
        "manual_queue_launch_with_optimization_refresh_returncode": payload.get(
            "manual_queue_launch_with_optimization_refresh_returncode", ""
        ),
        "manual_queue_launch_with_optimization_refresh_completed": payload.get(
            "manual_queue_launch_with_optimization_refresh_completed", ""
        ),
        "manual_queue_launch_with_optimization_refresh_status": payload.get(
            "manual_queue_launch_with_optimization_refresh_status", ""
        ),
        "manual_queue_launch_with_optimization_refresh_queue_refresh_status": payload.get(
            "manual_queue_launch_with_optimization_refresh_queue_refresh_status", ""
        ),
        "manual_queue_launch_with_optimization_refresh_queue_refresh_ok": payload.get(
            "manual_queue_launch_with_optimization_refresh_queue_refresh_ok", ""
        ),
        "manual_queue_launch_with_optimization_refresh_queue_refresh_source_count": payload.get(
            "manual_queue_launch_with_optimization_refresh_queue_refresh_source_count", ""
        ),
        "manual_queue_launch_with_optimization_refresh_selected": payload.get(
            "manual_queue_launch_with_optimization_refresh_selected", ""
        ),
        "manual_queue_launch_with_optimization_refresh_selected_queue_id": payload.get(
            "manual_queue_launch_with_optimization_refresh_selected_queue_id", ""
        ),
        "manual_queue_launch_with_optimization_refresh_selected_step_label": payload.get(
            "manual_queue_launch_with_optimization_refresh_selected_step_label", ""
        ),
        "manual_queue_launch_with_optimization_refresh_blocked": payload.get(
            "manual_queue_launch_with_optimization_refresh_blocked", ""
        ),
        "manual_queue_launch_with_optimization_refresh_blocked_reasons": payload.get(
            "manual_queue_launch_with_optimization_refresh_blocked_reasons", []
        ),
        "next_action_run_action_reason": payload.get("next_action_run_action_reason", ""),
        "next_action_run_primary_note": payload.get("next_action_run_primary_note", ""),
        "next_action_run_execute_command_text": payload.get("next_action_run_execute_command_text", ""),
        "next_action_run_collect_only_command_text": payload.get(
            "next_action_run_collect_only_command_text",
            "",
        ),
        "next_action_run_collect_only_note": payload.get("next_action_run_collect_only_note", ""),
        "next_action_run_manual_collect_only_command_text": payload.get(
            "next_action_run_manual_collect_only_command_text", ""
        ),
        "next_action_run_manual_run_start_after": payload.get(
            "next_action_run_manual_run_start_after", ""
        ),
        "next_action_run_manual_collect_ready": payload.get(
            "next_action_run_manual_collect_ready", ""
        ),
        "next_action_run_manual_collect_status": payload.get(
            "next_action_run_manual_collect_status", ""
        ),
        "next_action_run_manual_collect_csv_count": payload.get(
            "next_action_run_manual_collect_csv_count", ""
        ),
        "next_action_run_manual_collect_modified_after": payload.get(
            "next_action_run_manual_collect_modified_after", ""
        ),
        "next_action_run_manual_collect_reason": payload.get(
            "next_action_run_manual_collect_reason", ""
        ),
        "next_action_run_manual_collect_blocking_reasons": payload.get(
            "next_action_run_manual_collect_blocking_reasons", []
        ),
        "next_action_run_manual_collect_next_action": payload.get(
            "next_action_run_manual_collect_next_action", ""
        ),
        "next_action_run_manual_step_count": payload.get("next_action_run_manual_step_count", ""),
        "next_action_run_manual_steps": payload.get("next_action_run_manual_steps", []),
        "next_action_run_evidence_role": payload.get("next_action_run_evidence_role", ""),
        "next_action_run_diagnostic_only": payload.get("next_action_run_diagnostic_only", ""),
        "next_action_run_promotion_evidence": payload.get("next_action_run_promotion_evidence", ""),
        "next_action_run_action_context_keys": payload.get("next_action_run_action_context_keys", []),
        "next_action_run_related_execution_count": payload.get(
            "next_action_run_related_execution_count", ""
        ),
        "next_action_run_related_execution_keys": payload.get("next_action_run_related_execution_keys", []),
        "next_action_run_blocking_prior_action_count": payload.get(
            "next_action_run_blocking_prior_action_count", ""
        ),
        "next_action_run_blocking_prior_actions": payload.get(
            "next_action_run_blocking_prior_actions", []
        ),
        "next_action_run_blocking_prior_action_summary": payload.get(
            "next_action_run_blocking_prior_action_summary", ""
        ),
        "next_action_run_advisory_prior_action_count": payload.get(
            "next_action_run_advisory_prior_action_count", ""
        ),
        "next_action_run_advisory_prior_actions": payload.get(
            "next_action_run_advisory_prior_actions", []
        ),
        "next_action_run_advisory_prior_action_summary": payload.get(
            "next_action_run_advisory_prior_action_summary", ""
        ),
        "next_action_run_current_for_execution": payload.get("next_action_run_current_for_execution", ""),
        "next_action_run_gate_stale_reason": payload.get("next_action_run_gate_stale_reason", ""),
        "next_action_run_target": payload.get("next_action_run_target", ""),
        "next_action_run_kind": payload.get("next_action_run_kind", ""),
        "next_action_run_focus_side": payload.get("next_action_run_focus_side", ""),
        "next_action_run_optimization_mode": payload.get("next_action_run_optimization_mode", ""),
        "next_action_run_config": payload.get("next_action_run_config", ""),
        "next_action_run_set": payload.get("next_action_run_set", ""),
        "next_action_run_output_set": payload.get("next_action_run_output_set", ""),
        "next_action_run_archive_run_id": payload.get("next_action_run_archive_run_id", ""),
        "next_action_run_timeout_seconds": payload.get("next_action_run_timeout_seconds", ""),
        "next_action_run_timeout_minutes": payload.get("next_action_run_timeout_minutes", ""),
        "next_action_run_timeout_note": payload.get("next_action_run_timeout_note", ""),
        "next_action_run_timeout_start_reference_at": payload.get(
            "next_action_run_timeout_start_reference_at", ""
        ),
        "next_action_run_timeout_deadline_if_started_now": payload.get(
            "next_action_run_timeout_deadline_if_started_now", ""
        ),
        "next_action_run_timeout_deadline_epoch_if_started_now": payload.get(
            "next_action_run_timeout_deadline_epoch_if_started_now"
        ),
        "next_action_run_optimized_input_count": payload.get("next_action_run_optimized_input_count", ""),
        "next_action_run_estimated_full_factorial_passes": payload.get(
            "next_action_run_estimated_full_factorial_passes", ""
        ),
        "next_action_run_latest_executed_tester_xml_rows": payload.get(
            "next_action_run_latest_executed_tester_xml_rows", ""
        ),
        "next_action_run_primary_execution_class": payload.get("next_action_run_primary_execution_class", ""),
        "next_action_run_primary_is_mt5_tester_run": payload.get("next_action_run_primary_is_mt5_tester_run", ""),
        "next_action_run_runner_promotion_generated_at": payload.get(
            "next_action_run_runner_promotion_generated_at", ""
        ),
        "next_action_run_current_promotion_generated_at": payload.get(
            "next_action_run_current_promotion_generated_at", ""
        ),
        "next_action_run_planned_outputs": (
            payload.get("next_action_run_planned_outputs")
            if isinstance(payload.get("next_action_run_planned_outputs"), dict)
            else planned_outputs_bundle(
                payload.get("next_action_run_primary_planned_outputs", {}),
                payload.get("next_action_run_archive_preview_planned_outputs", {}),
                payload.get("next_action_run_follow_up_planned_outputs", {}),
                payload.get("next_action_run_follow_up_archive_preview_planned_outputs", {}),
            )
        ),
        "next_action_run_primary_planned_outputs": payload.get(
            "next_action_run_primary_planned_outputs", {}
        ),
        "next_action_run_archive_preview_planned_outputs": payload.get(
            "next_action_run_archive_preview_planned_outputs", {}
        ),
        "next_action_run_follow_up_planned_outputs": payload.get(
            "next_action_run_follow_up_planned_outputs", {}
        ),
        "next_action_run_follow_up_archive_preview_planned_outputs": payload.get(
            "next_action_run_follow_up_archive_preview_planned_outputs", {}
        ),
        "next_action_run_archive_preview_output_json": payload.get(
            "next_action_run_archive_preview_output_json", ""
        ),
        "next_action_run_archive_preview_output_md": payload.get("next_action_run_archive_preview_output_md", ""),
        "next_action_run_follow_up_archive_preview_output_json": payload.get(
            "next_action_run_follow_up_archive_preview_output_json", ""
        ),
        "next_action_run_follow_up_archive_preview_output_md": payload.get(
            "next_action_run_follow_up_archive_preview_output_md", ""
        ),
        "next_action_run_score_weight_follow_up_status": payload.get(
            "next_action_run_score_weight_follow_up_status", ""
        ),
        "next_action_run_score_weight_follow_up_regime_status": payload.get(
            "next_action_run_score_weight_follow_up_regime_status", ""
        ),
        "next_action_run_score_weight_follow_up_sample_shortage": payload.get(
            "next_action_run_score_weight_follow_up_sample_shortage", ""
        ),
        "next_action_run_score_weight_follow_up_walk_missing": payload.get(
            "next_action_run_score_weight_follow_up_walk_missing", ""
        ),
        "next_action_run_score_weight_follow_up_walk_required": payload.get(
            "next_action_run_score_weight_follow_up_walk_required", ""
        ),
        "next_action_run_score_weight_follow_up_walk_folds": payload.get(
            "next_action_run_score_weight_follow_up_walk_folds", ""
        ),
        "next_action_run_score_weight_follow_up_walk_required_folds": payload.get(
            "next_action_run_score_weight_follow_up_walk_required_folds", ""
        ),
        "next_action_run_score_weight_follow_up_regime_missing": payload.get(
            "next_action_run_score_weight_follow_up_regime_missing", ""
        ),
        "next_action_run_score_weight_follow_up_regime_required": payload.get(
            "next_action_run_score_weight_follow_up_regime_required", ""
        ),
        "next_action_run_score_weight_follow_up_regime_folds": payload.get(
            "next_action_run_score_weight_follow_up_regime_folds", ""
        ),
        "next_action_run_score_weight_follow_up_regime_required_folds": payload.get(
            "next_action_run_score_weight_follow_up_regime_required_folds", ""
        ),
        "next_action_run_score_weight_set_walk_forward_status": payload.get(
            "next_action_run_score_weight_set_walk_forward_status", ""
        ),
        "next_action_run_score_weight_set_skip_reason": payload.get(
            "next_action_run_score_weight_set_skip_reason", ""
        ),
        "next_action_execution_collect_only_hint": payload.get(
            "next_action_execution_collect_only_hint",
            "",
        ),
        "stable_candidate_refit_completed_kind": payload.get("stable_candidate_refit_completed_kind", ""),
        "stable_candidate_refit_completed_status": payload.get("stable_candidate_refit_completed_status", ""),
        "stable_candidate_refit_completed_reasons": payload.get(
            "stable_candidate_refit_completed_reasons", []
        ),
        "back_forward_execution_ready": payload.get("back_forward_execution_ready", ""),
        "back_forward_run_evidence_state": payload.get("back_forward_run_evidence_state", ""),
        "back_forward_run_run_id_prefix": payload.get("back_forward_run_run_id_prefix", ""),
        "back_forward_run_manual_collect_only_command_text": payload.get(
            "back_forward_run_manual_collect_only_command_text", ""
        ),
        "back_forward_run_manual_run_start_after": payload.get(
            "back_forward_run_manual_run_start_after", ""
        ),
        "back_forward_run_manual_collect_ready": payload.get(
            "back_forward_run_manual_collect_ready", ""
        ),
        "back_forward_run_manual_collect_status": payload.get(
            "back_forward_run_manual_collect_status", ""
        ),
        "back_forward_run_manual_collect_csv_count": payload.get(
            "back_forward_run_manual_collect_csv_count", ""
        ),
        "back_forward_run_manual_collect_modified_after": payload.get(
            "back_forward_run_manual_collect_modified_after", ""
        ),
        "back_forward_run_manual_collect_reason": payload.get(
            "back_forward_run_manual_collect_reason", ""
        ),
        "back_forward_run_manual_collect_blocking_reasons": payload.get(
            "back_forward_run_manual_collect_blocking_reasons", []
        ),
        "back_forward_run_manual_collect_next_action": payload.get(
            "back_forward_run_manual_collect_next_action", ""
        ),
        "back_forward_run_manual_step_count": payload.get("back_forward_run_manual_step_count", ""),
        "back_forward_run_manual_steps": payload.get("back_forward_run_manual_steps", []),
        "back_forward_run_mt5_strategy_tester_pack_available": payload.get(
            "back_forward_run_mt5_strategy_tester_pack_available", ""
        ),
        "back_forward_run_mt5_strategy_tester_pack_ready_for_manual_mt5_run": payload.get(
            "back_forward_run_mt5_strategy_tester_pack_ready_for_manual_mt5_run", ""
        ),
        "back_forward_run_mt5_strategy_tester_pack_status": payload.get(
            "back_forward_run_mt5_strategy_tester_pack_status", ""
        ),
        "back_forward_run_mt5_strategy_tester_pack_next_action": payload.get(
            "back_forward_run_mt5_strategy_tester_pack_next_action", ""
        ),
        "back_forward_run_mt5_strategy_tester_pack_is_back_forward_pair": payload.get(
            "back_forward_run_mt5_strategy_tester_pack_is_back_forward_pair", ""
        ),
        "back_forward_run_mt5_strategy_tester_pack_manual_run_start_after": payload.get(
            "back_forward_run_mt5_strategy_tester_pack_manual_run_start_after", ""
        ),
        "back_forward_run_mt5_strategy_tester_pack_collect_command_text": payload.get(
            "back_forward_run_mt5_strategy_tester_pack_collect_command_text", ""
        ),
        "back_forward_run_mt5_strategy_tester_pack_collect_ready": payload.get(
            "back_forward_run_mt5_strategy_tester_pack_collect_ready", ""
        ),
        "back_forward_run_mt5_strategy_tester_pack_collect_status": payload.get(
            "back_forward_run_mt5_strategy_tester_pack_collect_status", ""
        ),
        "back_forward_run_mt5_strategy_tester_pack_collect_reason": payload.get(
            "back_forward_run_mt5_strategy_tester_pack_collect_reason", ""
        ),
        "back_forward_run_mt5_strategy_tester_pack_step_count": payload.get(
            "back_forward_run_mt5_strategy_tester_pack_step_count", ""
        ),
        "back_forward_run_mt5_strategy_tester_pack_steps": payload.get(
            "back_forward_run_mt5_strategy_tester_pack_steps", []
        ),
        "back_forward_run_manual_prerequisites_ready": payload.get(
            "back_forward_run_manual_prerequisites_ready", ""
        ),
        "back_forward_run_manual_prerequisites_reasons": payload.get(
            "back_forward_run_manual_prerequisites_reasons", []
        ),
        "back_forward_run_manual_prerequisites_compile_status_path": payload.get(
            "back_forward_run_manual_prerequisites_compile_status_path", ""
        ),
        "back_forward_run_manual_prerequisites_generated_at": payload.get(
            "back_forward_run_manual_prerequisites_generated_at", ""
        ),
        "back_forward_run_plan_validation_ready": payload.get(
            "back_forward_run_plan_validation_ready", ""
        ),
        "back_forward_run_plan_validation_status": payload.get(
            "back_forward_run_plan_validation_status", ""
        ),
        "back_forward_run_plan_validation_reasons": payload.get(
            "back_forward_run_plan_validation_reasons", []
        ),
        "back_forward_run_execution_conditions": payload.get("back_forward_run_execution_conditions", {}),
        "back_forward_run_per_step_timeout_seconds": payload.get(
            "back_forward_run_per_step_timeout_seconds", ""
        ),
        "back_forward_run_since_minutes": payload.get("back_forward_run_since_minutes", ""),
        "back_forward_run_min_closed": payload.get("back_forward_run_min_closed", ""),
        "back_forward_run_from_date": payload.get("back_forward_run_from_date", ""),
        "back_forward_run_to_date": payload.get("back_forward_run_to_date", ""),
        "back_forward_run_forward_mode": payload.get("back_forward_run_forward_mode", ""),
        "back_forward_run_effective_from_date": payload.get(
            "back_forward_run_effective_from_date", ""
        ),
        "back_forward_run_effective_to_date": payload.get(
            "back_forward_run_effective_to_date", ""
        ),
        "back_forward_run_effective_forward_mode": payload.get(
            "back_forward_run_effective_forward_mode", ""
        ),
        "back_forward_run_sync_expert_parameters_set": payload.get(
            "back_forward_run_sync_expert_parameters_set", ""
        ),
        "back_forward_run_allow_running_terminal": payload.get("back_forward_run_allow_running_terminal", ""),
        "back_forward_run_allow_stale_compile": payload.get("back_forward_run_allow_stale_compile", ""),
        "back_forward_run_allow_invalid_risk_preset": payload.get(
            "back_forward_run_allow_invalid_risk_preset", ""
        ),
        "back_forward_run_ready_status_ok": payload.get("back_forward_run_ready_status_ok", ""),
        "back_forward_run_ready_status_reasons": payload.get("back_forward_run_ready_status_reasons", []),
        "back_forward_run_ready_status_mismatches": payload.get(
            "back_forward_run_ready_status_mismatches", []
        ),
        "back_forward_run_ready_status_checked_step_keys": payload.get(
            "back_forward_run_ready_status_checked_step_keys", []
        ),
        "back_forward_run_ready_status_checked_command_options": payload.get(
            "back_forward_run_ready_status_checked_command_options", []
        ),
        "back_forward_run_ready_status_checked_command_flags": payload.get(
            "back_forward_run_ready_status_checked_command_flags", []
        ),
        "back_forward_run_ready_status_checked_execution_conditions": payload.get(
            "back_forward_run_ready_status_checked_execution_conditions", []
        ),
        "back_forward_run_ready_status_expected_execution_conditions": payload.get(
            "back_forward_run_ready_status_expected_execution_conditions", {}
        ),
        "back_forward_run_ready_status_status_execution_conditions": payload.get(
            "back_forward_run_ready_status_status_execution_conditions", {}
        ),
        "back_forward_run_archive_preview_output_json": payload.get(
            "back_forward_run_archive_preview_output_json", ""
        ),
        "back_forward_run_archive_preview_output_md": payload.get(
            "back_forward_run_archive_preview_output_md", ""
        ),
        "back_forward_run_archive_preview_output_json_by_step": payload.get(
            "back_forward_run_archive_preview_output_json_by_step", {}
        ),
        "back_forward_run_archive_preview_validation_ok_by_step": payload.get(
            "back_forward_run_archive_preview_validation_ok_by_step", {}
        ),
        "back_forward_run_performance_comparison_available": payload.get(
            "back_forward_run_performance_comparison_available", ""
        ),
        "back_forward_run_performance_comparison_status": payload.get(
            "back_forward_run_performance_comparison_status", ""
        ),
        "back_forward_run_performance_comparison_rows": payload.get(
            "back_forward_run_performance_comparison_rows", []
        ),
        "back_forward_run_performance_comparison_thresholds": payload.get(
            "back_forward_run_performance_comparison_thresholds", {}
        ),
    }


def effective_status_watch_heartbeat_path(path: str | Path | None) -> str | Path | None:
    if not path:
        return path
    requested = Path(path)
    current = Path(DEFAULT_STATUS_WATCH_HEARTBEAT)
    if requested == Path(LEGACY_STATUS_WATCH_HEARTBEAT) and current.exists():
        return DEFAULT_STATUS_WATCH_HEARTBEAT
    return path


def compile_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        return summary
    return payload


def promotion_gate_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {}
    actions = payload.get("next_actions") if isinstance(payload.get("next_actions"), list) else []
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    failed_rows = [row for row in checks if isinstance(row, dict) and row.get("passed") is not True]
    checks_by_name = {str(row.get("name")): row for row in checks if isinstance(row, dict)}
    failed = payload.get("failed")
    if failed is None and checks:
        failed = len(failed_rows)
    failed_names_source = payload.get("failed_check_names")
    if not isinstance(failed_names_source, list):
        failed_names_source = payload.get("failed_checks")
    if isinstance(failed_names_source, list):
        failed_check_names = [str(name) for name in failed_names_source]
    else:
        failed_check_names = [str(row.get("name")) for row in failed_rows if row.get("name")]
    stable_candidate_refit: dict[str, Any] = {}
    stable_candidate_refit_completed: dict[str, Any] = {}
    for action in actions:
        if not isinstance(action, dict):
            continue
        evidence = action.get("evidence") if isinstance(action.get("evidence"), dict) else {}
        refit = evidence.get("stable_candidate_refit") if isinstance(evidence.get("stable_candidate_refit"), dict) else {}
        completed = (
            evidence.get("stable_candidate_refit_completed")
            if isinstance(evidence.get("stable_candidate_refit_completed"), dict)
            else {}
        )
        execution = (
            evidence.get("stable_candidate_refit_execution")
            if isinstance(evidence.get("stable_candidate_refit_execution"), dict)
            else {}
        )
        archive = (
            evidence.get("stable_candidate_refit_archive_preview")
            if isinstance(evidence.get("stable_candidate_refit_archive_preview"), dict)
            else {}
        )
        if not refit and not execution and not completed:
            continue
        outputs = execution.get("outputs") if isinstance(execution.get("outputs"), dict) else {}
        stable_candidate_refit = {
            "priority": action.get("priority"),
            "area": action.get("area"),
            "action": action.get("action"),
            "side": refit.get("side", ""),
            "driver": refit.get("driver", ""),
            "kind": refit.get("kind") or execution.get("kind", ""),
            "focus_side": refit.get("focus_side") or execution.get("focus_side", ""),
            "reason": refit.get("reason", ""),
            "config": execution.get("config", ""),
            "set": execution.get("set", ""),
            "template_set": execution.get("template_set", ""),
            "report_name": execution.get("report_name", ""),
            "agent_csv_archive_run_id": execution.get("agent_csv_archive_run_id", ""),
            "output_set": outputs.get("output_set", ""),
            "command_text": execution.get("command_text", ""),
            "archive_preview_run_id": archive.get("run_id", ""),
            "archive_preview_include_source_time": archive.get("include_source_time", ""),
        }
        side_status = completed.get("side_status") if isinstance(completed.get("side_status"), dict) else {}
        decision = completed.get("decision") if isinstance(completed.get("decision"), dict) else {}
        set_metadata = completed.get("set_metadata") if isinstance(completed.get("set_metadata"), dict) else {}
        reasons = decision.get("reasons") if isinstance(decision.get("reasons"), list) else []
        stable_candidate_refit_completed = {
            "kind": completed.get("kind", ""),
            "side": completed.get("side", ""),
            "status": side_status.get("status", ""),
            "closed": side_status.get("closed", ""),
            "pf": side_status.get("pf", ""),
            "avg_price_r": side_status.get("avg_price_r", ""),
            "net_profit": side_status.get("net_profit", ""),
            "decision_adoptable": decision.get("adoptable", ""),
            "decision_reasons": reasons[:5],
            "next_search": completed.get("next_search") if isinstance(completed.get("next_search"), dict) else {},
            "set_metadata": set_metadata,
            "skip_reason": set_metadata.get("skip_reason", ""),
            "diagnostic_only": set_metadata.get("diagnostic_only", ""),
        } if completed else {}
        break
    return {
        "generated_at": payload.get("generated_at"),
        "decision": payload.get("decision"),
        "live_ready": payload.get("live_ready"),
        "failed": failed,
        "failed_check_names": failed_check_names,
        "mt5_back_forward_run_check": checks_by_name.get("mt5_back_forward_run", {}),
        "mt5_back_forward_run_ok_check": checks_by_name.get("mt5_back_forward_run_ok", {}),
        "mt5_back_forward_run_performance_check": checks_by_name.get(
            "mt5_back_forward_run_performance", {}
        ),
        "stable_candidate_refit": stable_candidate_refit,
        "stable_candidate_refit_completed": stable_candidate_refit_completed,
        "p1_actions": [
            {
                "area": action.get("area"),
                "action": action.get("action"),
            }
            for action in actions
            if isinstance(action, dict) and action.get("priority") == 1
        ],
    }


def optimization_report_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else None
    return summary if summary is not None else payload


def optimization_recommendation_summary(payload: dict[str, Any]) -> dict[str, Any]:
    recommendation = payload.get("recommendation") if isinstance(payload.get("recommendation"), dict) else None
    return recommendation if recommendation is not None else payload


def stable_candidate_summary(
    report_payload: dict[str, Any],
    recommendation_payload: dict[str, Any],
    tester_run_payload: dict[str, Any],
) -> dict[str, Any]:
    report = optimization_report_summary(report_payload)
    recommendation = optimization_recommendation_summary(recommendation_payload)
    if not report and not recommendation and not tester_run_payload:
        return {"exists": False}
    overall = report.get("overall") if isinstance(report.get("overall"), dict) else {}
    tester_xml = report.get("tester_xml") if isinstance(report.get("tester_xml"), dict) else {}
    forward_xml = tester_xml.get("forward") if isinstance(tester_xml.get("forward"), dict) else {}
    decision = recommendation.get("decision") if isinstance(recommendation.get("decision"), dict) else {}
    set_metadata = (
        recommendation.get("set_metadata") if isinstance(recommendation.get("set_metadata"), dict) else {}
    )
    terminal_run = tester_run_payload.get("terminal_run") if isinstance(tester_run_payload.get("terminal_run"), dict) else {}
    reasons = decision.get("reasons") if isinstance(decision.get("reasons"), list) else []
    return {
        "exists": True,
        "report_generated_at": report.get("generated_at"),
        "tester_generated_at": tester_run_payload.get("generated_at"),
        "tester_ok": tester_run_payload.get("ok") if tester_run_payload else "",
        "tester_blocked": tester_run_payload.get("blocked") if tester_run_payload else "",
        "tester_elapsed_seconds": terminal_run.get("elapsed_seconds", ""),
        "closed": overall.get("closed"),
        "pf": overall.get("pf"),
        "avg_price_r": overall.get("avg_price_r"),
        "net_profit": overall.get("net_profit"),
        "max_drawdown_price_r": overall.get("max_drawdown_price_r"),
        "positive_forward_positive_back": forward_xml.get("positive_forward_positive_back"),
        "positive_forward_negative_back": forward_xml.get("positive_forward_negative_back"),
        "recommendation_adoptable": decision.get("adoptable") if decision else "",
        "recommendation_reasons": reasons[:5],
        "next_set": set_metadata.get("path", ""),
        "next_set_skipped_write": set_metadata.get("skipped_write", ""),
        "next_set_skip_reason": set_metadata.get("skip_reason", ""),
    }


def priority_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def action_identity_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def next_action_runner_command_hint(target: Any, *, allow_non_tester_primary: bool = False) -> str:
    target_text = str(target or "").strip()
    target_args = f" --target {target_text}" if target_text else ""
    allow_args = " --allow-non-tester-primary" if allow_non_tester_primary else ""
    return (
        "python3 analysis/mt5_next_action_run.py"
        f"{target_args}"
        f" --execute{allow_args}"
        " --refresh-ready-status"
        " --output-json runtime/latest_mt5_next_action_run.json"
        " --output-md runtime/latest_mt5_next_action_run.md"
    )


def action_execution_summary(action: dict[str, Any]) -> dict[str, Any]:
    evidence = action.get("evidence") if isinstance(action.get("evidence"), dict) else {}
    execution: dict[str, Any] = {}
    execution_key = ""
    execution_label = ""
    for key, label in EXECUTION_LABELS:
        candidate = evidence.get(key) if isinstance(evidence.get(key), dict) else {}
        if candidate:
            execution = candidate
            execution_key = key
            execution_label = label
            break
    command = execution.get("command") if isinstance(execution.get("command"), list) else []
    command_text = execution.get("command_text", "")
    command_joined = " ".join(str(item) for item in command)
    primary_class = execution_class({"command": command, "command_text": command_text})
    runner_target = str(action.get("area") or "").strip() or str(action.get("action") or "").strip() or execution_label
    runner_execute_hint = ""
    if primary_class == "mt5_tester_run":
        runner_execute_hint = next_action_runner_command_hint(runner_target)
    elif primary_class in LOCAL_NEXT_ACTION_PRIMARY_CLASSES:
        runner_execute_hint = next_action_runner_command_hint(runner_target, allow_non_tester_primary=True)
    return {
        "priority": action.get("priority"),
        "area": action.get("area", ""),
        "action": action.get("action", ""),
        "reason": action.get("reason", ""),
        "execution_key": execution_key,
        "execution_label": execution_label,
        "execution_kind": execution.get("kind", ""),
        "command_text": command_text,
        "command_class": command_joined or str(command_text),
        "primary_execution_class": primary_class,
        "runner_target": runner_target,
        "runner_requires_allow_non_tester_primary": primary_class in LOCAL_NEXT_ACTION_PRIMARY_CLASSES,
        "runner_execute_hint": runner_execute_hint,
    }


def blocking_prior_action_summary_text(actions: Any) -> str:
    if not isinstance(actions, list):
        return ""
    parts: list[str] = []
    for row in actions:
        if not isinstance(row, dict):
            continue
        priority = row.get("priority", "")
        area = str(row.get("area") or "").strip()
        action = str(row.get("action") or "").strip()
        label = f"{area}:{action}" if area and action else area or action
        if not label:
            continue
        prefix = f"P{priority} " if priority not in ("", None) else ""
        parts.append(f"{prefix}{label}")
    return "; ".join(parts)


def selected_action_index(gate_payload: dict[str, Any], selected_action: dict[str, Any]) -> int | None:
    actions = gate_payload.get("next_actions") if isinstance(gate_payload.get("next_actions"), list) else []
    selected_priority = action_identity_text(selected_action.get("priority"))
    selected_area = action_identity_text(selected_action.get("area"))
    selected_name = action_identity_text(selected_action.get("action"))
    if not selected_area and not selected_name:
        return None
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        if (
            action_identity_text(action.get("priority")) == selected_priority
            and action_identity_text(action.get("area")) == selected_area
            and action_identity_text(action.get("action")) == selected_name
        ):
            return index
    return None


def higher_priority_actions(gate_payload: dict[str, Any], selected_action: Any) -> list[dict[str, Any]]:
    selected_action_dict = selected_action if isinstance(selected_action, dict) else {}
    selected_priority = selected_action_dict.get("priority") if selected_action_dict else selected_action
    selected = priority_number(selected_priority)
    if selected is None:
        return []
    selected_index = selected_action_index(gate_payload, selected_action_dict) if selected_action_dict else None
    actions = gate_payload.get("next_actions") if isinstance(gate_payload.get("next_actions"), list) else []
    rows: list[dict[str, Any]] = []
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        priority = priority_number(action.get("priority"))
        if priority is None:
            continue
        same_priority_predecessor = (
            selected_index is not None and priority == selected and index < selected_index
        )
        if priority > selected or (priority == selected and not same_priority_predecessor):
            continue
        rows.append(action_execution_summary(action))
    return rows


def is_bridge_prior_action(action_summary: dict[str, Any]) -> bool:
    area = str(action_summary.get("area") or "").strip().lower()
    action = str(action_summary.get("action") or "").strip().lower()
    execution_kind = str(action_summary.get("execution_kind") or "").strip().lower()
    primary_class = str(action_summary.get("primary_execution_class") or "").strip().lower()
    return (
        area == "bridge"
        or area.startswith("bridge_")
        or execution_kind.startswith("bridge_")
        or primary_class.startswith("bridge_")
        or ("bridge" in action and ("restore" in action or "recovery" in action))
    )


def bridge_prior_actions_are_advisory_for_runner(payload: dict[str, Any]) -> bool:
    if payload.get("bridge_recovery_required_for_mt5_validation") is True:
        return False
    primary_class = str(payload.get("primary_execution_class") or "").strip()
    return payload.get("primary_is_mt5_tester_run") is True or primary_class == "mt5_tester_run"


def split_blocking_and_advisory_prior_actions(
    payload: dict[str, Any],
    prior_actions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not bridge_prior_actions_are_advisory_for_runner(payload):
        return prior_actions, []
    blocking: list[dict[str, Any]] = []
    advisory: list[dict[str, Any]] = []
    for action in prior_actions:
        if is_bridge_prior_action(action):
            advisory.append(action)
        else:
            blocking.append(action)
    return blocking, advisory


def numeric_seconds(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        seconds = float(str(value))
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


def timeout_deadline_from_now(timeout_seconds: Any, *, now_epoch: float | None = None) -> dict[str, Any]:
    seconds = numeric_seconds(timeout_seconds)
    if seconds is None:
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


def next_action_runner_values_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
    primary = payload.get("primary") if isinstance(payload.get("primary"), dict) else {}
    archive_preview = payload.get("archive_preview") if isinstance(payload.get("archive_preview"), dict) else {}
    follow_up = payload.get("follow_up") if isinstance(payload.get("follow_up"), dict) else {}
    follow_up_archive_preview = (
        payload.get("follow_up_archive_preview")
        if isinstance(payload.get("follow_up_archive_preview"), dict)
        else {}
    )
    execution_hints = payload.get("execution_hints") if isinstance(payload.get("execution_hints"), dict) else {}
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


def next_action_runner_values_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
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


def next_action_gate_consistency(payload: dict[str, Any], gate_payload: dict[str, Any]) -> dict[str, Any]:
    runner_generated_at = payload.get("promotion_generated_at") or payload.get("generated_at", "")
    current_generated_at = gate_payload.get("generated_at", "") if gate_payload else ""
    runner_decision = payload.get("promotion_decision") or payload.get("decision", "")
    current_decision = gate_payload.get("decision", "") if gate_payload else ""
    generated_at_match = bool(runner_generated_at and current_generated_at and runner_generated_at == current_generated_at)
    decision_match = bool(runner_decision and current_decision and runner_decision == current_decision)
    target = str(payload.get("target") or "")
    selected_action_present = False
    selected_action_current = False
    mismatches: list[str] = []

    if gate_payload and target:
        current_plan = select_next_action_plan(gate_payload, target=target)
        selected_action_present = current_plan.get("found") is True
        if selected_action_present:
            runner_values = next_action_runner_values_from_payload(payload)
            current_values = next_action_runner_values_from_plan(current_plan)
            mismatches = [
                key
                for key, value in runner_values.items()
                if comparable_text(value) != comparable_text(current_values.get(key, ""))
            ]
            selected_action_current = not mismatches

    promotion_gate_current = bool(
        runner_generated_at
        and current_generated_at
        and decision_match
        and selected_action_present
        and selected_action_current
    )
    current_for_execution = promotion_gate_current
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
        "promotion_gate_current": promotion_gate_current,
        "promotion_gate_generated_at_match": generated_at_match,
        "promotion_gate_decision_match": decision_match,
        "runner_promotion_generated_at": runner_generated_at,
        "current_promotion_generated_at": current_generated_at,
        "runner_promotion_decision": runner_decision,
        "current_promotion_decision": current_decision,
        "selected_action_present": selected_action_present,
        "selected_action_current": selected_action_current,
        "current_for_execution": current_for_execution,
        "gate_stale_reason": stale_reason,
        "selected_action_mismatches": mismatches,
    }


def score_weight_context_summary(action_context: object) -> dict[str, Any]:
    if not isinstance(action_context, dict):
        return {}
    follow_up = (
        action_context.get("score_weight_follow_up")
        if isinstance(action_context.get("score_weight_follow_up"), dict)
        else {}
    )
    set_result = (
        action_context.get("score_weight_set_result")
        if isinstance(action_context.get("score_weight_set_result"), dict)
        else {}
    )
    top_candidate = (
        set_result.get("top_weight_candidate")
        if isinstance(set_result.get("top_weight_candidate"), dict)
        else {}
    )
    return {
        "score_weight_follow_up_status": follow_up.get("status", ""),
        "score_weight_follow_up_regime_status": follow_up.get("regime_status", ""),
        "score_weight_follow_up_regime_dimension": follow_up.get("regime_dimension", ""),
        "score_weight_follow_up_regime_group": follow_up.get("regime_group", ""),
        "score_weight_follow_up_sample_shortage": follow_up.get("sample_shortage", ""),
        "score_weight_follow_up_walk_missing": follow_up.get("walk_forward_missing_test_weight_count", ""),
        "score_weight_follow_up_walk_required": follow_up.get("walk_forward_required_test_weight_count", ""),
        "score_weight_follow_up_walk_folds": follow_up.get("walk_forward_folds_with_weight_trades", ""),
        "score_weight_follow_up_walk_required_folds": follow_up.get(
            "walk_forward_required_folds_with_weight_trades",
            "",
        ),
        "score_weight_follow_up_regime_missing": follow_up.get("regime_missing_test_weight_count", ""),
        "score_weight_follow_up_regime_required": follow_up.get("regime_required_test_weight_count", ""),
        "score_weight_follow_up_regime_folds": follow_up.get("regime_folds_with_weight_trades", ""),
        "score_weight_follow_up_regime_required_folds": follow_up.get(
            "regime_required_folds_with_weight_trades",
            "",
        ),
        "score_weight_follow_up_recommendation": follow_up.get("recommendation", ""),
        "score_weight_set_walk_forward_status": set_result.get("walk_forward_status", ""),
        "score_weight_set_written": set_result.get("written", ""),
        "score_weight_set_skip_reason": set_result.get("skip_reason", ""),
        "score_weight_set_top_candidate_threshold": top_candidate.get("threshold", ""),
        "score_weight_set_top_candidate_pf": top_candidate.get("pf", ""),
        "score_weight_set_top_candidate_count": top_candidate.get("count", ""),
        "score_weight_set_top_candidate_weights": top_candidate.get("weights", ""),
    }


def next_action_run_summary(payload: dict[str, Any], gate_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not payload:
        return {"exists": False}
    action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
    primary = payload.get("primary") if isinstance(payload.get("primary"), dict) else {}
    archive_preview = (
        payload.get("archive_preview") if isinstance(payload.get("archive_preview"), dict) else {}
    )
    follow_up = payload.get("follow_up") if isinstance(payload.get("follow_up"), dict) else {}
    follow_up_archive_preview = (
        payload.get("follow_up_archive_preview")
        if isinstance(payload.get("follow_up_archive_preview"), dict)
        else {}
    )
    execution_hints = payload.get("execution_hints") if isinstance(payload.get("execution_hints"), dict) else {}
    manual_plan = (
        payload.get("manual_strategy_tester")
        if isinstance(payload.get("manual_strategy_tester"), dict)
        else {}
    )
    manual_collect_readiness = (
        payload.get("manual_collect_readiness")
        if isinstance(payload.get("manual_collect_readiness"), dict)
        else {}
    )
    strategy_tester_pack = (
        payload.get("mt5_strategy_tester_pack")
        if isinstance(payload.get("mt5_strategy_tester_pack"), dict)
        else {}
    )
    strategy_tester_pack_steps = (
        strategy_tester_pack.get("steps")
        if isinstance(strategy_tester_pack.get("steps"), list)
        else []
    )
    execution_hints = (
        payload.get("execution_hints")
        if isinstance(payload.get("execution_hints"), dict)
        else {}
    )
    manual_steps = manual_plan.get("steps") if isinstance(manual_plan.get("steps"), list) else []
    post_artifacts = (
        payload.get("post_execution_artifacts")
        if isinstance(payload.get("post_execution_artifacts"), dict)
        else {}
    )
    post_validation = (
        payload.get("post_execution_validation")
        if isinstance(payload.get("post_execution_validation"), dict)
        else {}
    )
    primary_post = post_artifacts.get("primary") if isinstance(post_artifacts.get("primary"), dict) else {}
    archive_preview_post = (
        post_artifacts.get("archive_preview")
        if isinstance(post_artifacts.get("archive_preview"), dict)
        else {}
    )
    follow_up_post = post_artifacts.get("follow_up") if isinstance(post_artifacts.get("follow_up"), dict) else {}
    follow_up_archive_preview_post = (
        post_artifacts.get("follow_up_archive_preview")
        if isinstance(post_artifacts.get("follow_up_archive_preview"), dict)
        else {}
    )
    executions = payload.get("executions") if isinstance(payload.get("executions"), dict) else {}
    primary_execution = executions.get("primary") if isinstance(executions.get("primary"), dict) else {}
    follow_up_execution = executions.get("follow_up") if isinstance(executions.get("follow_up"), dict) else {}
    archive_execution = (
        executions.get("archive_preview") if isinstance(executions.get("archive_preview"), dict) else {}
    )
    follow_up_archive_execution = (
        executions.get("follow_up_archive_preview")
        if isinstance(executions.get("follow_up_archive_preview"), dict)
        else {}
    )
    compile_execution = executions.get("compile") if isinstance(executions.get("compile"), dict) else {}
    consistency = next_action_gate_consistency(payload, gate_payload or {})
    timeout_projection = timeout_deadline_from_now(primary.get("timeout_seconds", ""))
    all_prior_actions = higher_priority_actions(gate_payload or {}, action)
    prior_actions, advisory_prior_actions = split_blocking_and_advisory_prior_actions(
        payload,
        all_prior_actions,
    )
    action_context = payload.get("action_context", {})
    action_context_keys = (
        payload.get("action_context_keys")
        if isinstance(payload.get("action_context_keys"), list)
        else sorted(action_context.keys()) if isinstance(action_context, dict) else []
    )
    related_executions = payload.get("related_executions", [])
    related_execution_keys = (
        payload.get("related_execution_keys")
        if isinstance(payload.get("related_execution_keys"), list)
        else [
            row.get("key")
            for row in related_executions
            if isinstance(row, dict) and row.get("key") not in (None, "")
        ]
        if isinstance(related_executions, list)
        else []
    )
    return {
        "exists": True,
        "runner_generated_at": payload.get("runner_generated_at", ""),
        "ok": payload.get("ok"),
        "dry_run": payload.get("dry_run"),
        "target": payload.get("target", ""),
        "found": payload.get("found"),
        "promotion_generated_at": payload.get("promotion_generated_at") or payload.get("generated_at", ""),
        "promotion_decision": payload.get("promotion_decision") or payload.get("decision", ""),
        "execution_key": payload.get("execution_key", ""),
        "label": payload.get("label", ""),
        "action_priority": action.get("priority", ""),
        "action_area": action.get("area", ""),
        "action": action.get("action", ""),
        "action_reason": action.get("reason", ""),
        "blocking_prior_actions": prior_actions,
        "blocking_prior_action_count": len(prior_actions),
        "blocking_prior_action_summary": blocking_prior_action_summary_text(prior_actions),
        "advisory_prior_actions": advisory_prior_actions,
        "advisory_prior_action_count": len(advisory_prior_actions),
        "advisory_prior_action_summary": blocking_prior_action_summary_text(advisory_prior_actions),
        "kind": primary.get("kind", ""),
        "focus_side": primary.get("focus_side", ""),
        "optimization_mode": primary.get("optimization_mode", ""),
        "config": primary.get("config", ""),
        "set": primary.get("set", ""),
        "template_set": primary.get("template_set", ""),
        "report_name": primary.get("report_name", ""),
        "output_set": primary.get("output_set", ""),
        "agent_csv_archive_run_id": primary.get("agent_csv_archive_run_id", ""),
        "timeout_seconds": primary.get("timeout_seconds", ""),
        "timeout_minutes": primary.get("timeout_minutes", ""),
        "timeout_note": primary.get("timeout_note", ""),
        "primary_note": primary.get("note", ""),
        "execute_command_text": payload.get("execute_command_text")
        or execution_hints.get("execute_command_text", ""),
        "collect_only_command_text": payload.get("collect_only_command_text")
        or execution_hints.get("collect_only_command_text", ""),
        "collect_only_note": execution_hints.get("collect_only_note", ""),
        "manual_strategy_tester_available": manual_plan.get("available", bool(manual_steps)),
        "manual_collect_only_command_text": manual_plan.get(
            "recommended_collect_only_command_text", ""
        ),
        "manual_collect_only_command": manual_plan.get("recommended_collect_only_command", []),
        "manual_collect_only_note": manual_plan.get("collect_only_note", ""),
        "manual_run_start_after": manual_plan.get("manual_run_start_after", ""),
        "manual_collect_ready": manual_collect_readiness.get("ready", ""),
        "manual_collect_status": manual_collect_readiness.get("status", ""),
        "manual_collect_csv_count": manual_collect_readiness.get("csv_count", ""),
        "manual_collect_modified_after": manual_collect_readiness.get("modified_after", ""),
        "manual_collect_reason": manual_collect_readiness.get("reason", ""),
        "manual_collect_blocking_reasons": manual_collect_readiness.get("blocking_reasons", []),
        "manual_collect_next_action": manual_collect_readiness.get("next_action", ""),
        "manual_step_count": len(manual_steps),
        "manual_steps": manual_steps,
        "evidence_role": primary.get("evidence_role", ""),
        "diagnostic_only": primary.get("diagnostic_only", ""),
        "promotion_evidence": primary.get("promotion_evidence", ""),
        **timeout_projection,
        "optimized_input_count": primary.get("optimized_input_count", ""),
        "estimated_full_factorial_passes": primary.get("estimated_full_factorial_passes", ""),
        "latest_executed_tester_xml_rows": primary.get("latest_executed_tester_xml_rows", ""),
        "planned_outputs": planned_outputs_bundle(
            primary.get("planned_outputs", {}),
            archive_preview.get("planned_outputs", {}),
            follow_up.get("planned_outputs", {}),
            follow_up_archive_preview.get("planned_outputs", {}),
        ),
        "primary_planned_outputs": primary.get("planned_outputs", {}),
        "command_text": primary.get("command_text", ""),
        "action_context": action_context,
        "action_context_keys": action_context_keys,
        **score_weight_context_summary(action_context),
        "related_executions": related_executions,
        "related_execution_keys": related_execution_keys,
        "run_archive_preview": payload.get("run_archive_preview"),
        "archive_preview_planned_outputs": archive_preview.get("planned_outputs", {}),
        "run_compile": payload.get("run_compile"),
        "run_follow_up": payload.get("run_follow_up"),
        "allow_non_tester_primary": payload.get("allow_non_tester_primary"),
        "primary_execution_class": payload.get("primary_execution_class", ""),
        "primary_is_mt5_tester_run": payload.get("primary_is_mt5_tester_run", ""),
        "primary_executed": bool(primary_execution),
        "primary_ok": primary_execution.get("ok", ""),
        "primary_returncode": primary_execution.get("returncode", ""),
        "primary_elapsed_seconds": primary_execution.get("elapsed_seconds", ""),
        "follow_up_kind": follow_up.get("kind", ""),
        "follow_up_output_set": follow_up.get("output_set", ""),
        "follow_up_planned_outputs": follow_up.get("planned_outputs", {}),
        "follow_up_command_text": follow_up.get("command_text", ""),
        "follow_up_archive_preview_planned_outputs": follow_up_archive_preview.get("planned_outputs", {}),
        "follow_up_executed": bool(follow_up_execution),
        "follow_up_ok": follow_up_execution.get("ok", ""),
        "follow_up_returncode": follow_up_execution.get("returncode", ""),
        "follow_up_elapsed_seconds": follow_up_execution.get("elapsed_seconds", ""),
        "follow_up_archive_preview_ok": follow_up_archive_execution.get("ok", ""),
        "follow_up_archive_preview_returncode": follow_up_archive_execution.get("returncode", ""),
        "follow_up_skipped": payload.get("follow_up_skipped", ""),
        "archive_preview_ok": archive_execution.get("ok", ""),
        "archive_preview_returncode": archive_execution.get("returncode", ""),
        "compile_ok": compile_execution.get("ok", ""),
        "compile_returncode": compile_execution.get("returncode", ""),
        "blocked_before_primary": payload.get("blocked_before_primary", ""),
        "blocked_before_follow_up": payload.get("blocked_before_follow_up", ""),
        "blocked_after_primary": payload.get("blocked_after_primary", ""),
        "blocked_after_follow_up": payload.get("blocked_after_follow_up", ""),
        "reason": payload.get("reason", ""),
        "post_execution_artifacts": post_artifacts,
        "post_execution_validation": post_validation,
        "archive_preview_post_execution_artifacts": archive_preview_post,
        "primary_post_execution_artifacts": primary_post,
        "follow_up_archive_preview_post_execution_artifacts": follow_up_archive_preview_post,
        "follow_up_post_execution_artifacts": follow_up_post,
        **consistency,
    }


def back_forward_step_summary(step: object) -> dict[str, Any]:
    if not isinstance(step, dict):
        return {}
    outputs = step.get("outputs") if isinstance(step.get("outputs"), dict) else {}
    execution = step.get("execution") if isinstance(step.get("execution"), dict) else {}
    validation = (
        step.get("post_execution_validation")
        if isinstance(step.get("post_execution_validation"), dict)
        else {}
    )
    artifacts = (
        step.get("post_execution_artifacts")
        if isinstance(step.get("post_execution_artifacts"), dict)
        else {}
    )
    tester_artifact = artifacts.get("tester_run") if isinstance(artifacts.get("tester_run"), dict) else {}
    report_artifact = artifacts.get("report") if isinstance(artifacts.get("report"), dict) else {}
    preview = step.get("archive_preview") if isinstance(step.get("archive_preview"), dict) else {}
    preview_outputs = (
        preview.get("planned_outputs") if isinstance(preview.get("planned_outputs"), dict) else {}
    )
    preview_execution = (
        step.get("archive_preview_execution")
        if isinstance(step.get("archive_preview_execution"), dict)
        else {}
    )
    preview_validation = (
        step.get("archive_preview_validation")
        if isinstance(step.get("archive_preview_validation"), dict)
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
    command = step.get("command") if isinstance(step.get("command"), list) else []
    command_forward_mode = command_option_value([str(item) for item in command], "--forward-mode") if command else ""
    base_forward_mode = str(step.get("base_forward_mode") or step.get("forward_mode") or "")
    forward_mode_override = str(step.get("forward_mode_override") or command_forward_mode or "")
    effective_forward_mode = str(
        step.get("effective_forward_mode") or forward_mode_override or base_forward_mode
    )
    effective_from_date = str(
        step.get("effective_from_date") or step.get("from_date") or step.get("base_from_date") or ""
    )
    effective_to_date = str(
        step.get("effective_to_date") or step.get("to_date") or step.get("base_to_date") or ""
    )
    return {
        "label": step.get("label", ""),
        "config": step.get("config", ""),
        "expert": step.get("expert", ""),
        "expert_parameters": step.get("expert_parameters", ""),
        "forward_mode": step.get("forward_mode", ""),
        "base_forward_mode": base_forward_mode,
        "forward_mode_override": forward_mode_override,
        "effective_forward_mode": effective_forward_mode,
        "effective_from_date": effective_from_date,
        "effective_to_date": effective_to_date,
        "command_forward_mode": command_forward_mode,
        "base_from_date": step.get("base_from_date", ""),
        "base_to_date": step.get("base_to_date", ""),
        "report_name": step.get("report_name", ""),
        "archive_run_id": step.get("archive_run_id", ""),
        "run_json": outputs.get("run_json", ""),
        "run_md": outputs.get("run_md", ""),
        "report_json": outputs.get("report_json", ""),
        "report_md": outputs.get("report_md", ""),
        "archive_preview_json": preview_outputs.get("output_json", ""),
        "archive_preview_md": preview_outputs.get("output_md", ""),
        "archive_preview_command_text": preview.get("command_text", ""),
        "archive_preview_execution_ok": preview_execution.get("ok", ""),
        "archive_preview_execution_returncode": preview_execution.get("returncode", ""),
        "archive_preview_validation_required": preview_validation.get("required", ""),
        "archive_preview_validation_ok": preview_validation.get("ok", ""),
        "archive_preview_validation_reasons": preview_validation.get("reasons", []),
        "archive_preview_artifact_exists": preview_archive.get("exists", ""),
        "archive_preview_artifact_ok": preview_archive.get("ok", ""),
        "archive_preview_artifact_execute": preview_archive.get("execute", ""),
        "archive_preview_artifact_count": preview_archive.get("count", ""),
        "archive_preview_artifact_run_id": preview_archive.get("run_id", ""),
        "archive_preview_artifact_first_server_time": preview_archive.get("first_server_time", ""),
        "archive_preview_artifact_last_server_time": preview_archive.get("last_server_time", ""),
        "command": command,
        "command_text": step.get("command_text", ""),
        "execution_ok": execution.get("ok", ""),
        "execution_dry_run": execution.get("dry_run", ""),
        "execution_returncode": execution.get("returncode", ""),
        "execution_elapsed_seconds": execution.get("elapsed_seconds", ""),
        "post_execution_validation_required": validation.get("required", ""),
        "post_execution_validation_ok": validation.get("ok", ""),
        "post_execution_validation_reasons": validation.get("reasons", []),
        "tester_run_artifact_exists": tester_artifact.get("exists", ""),
        "tester_run_artifact_ok": tester_artifact.get("ok", ""),
        "tester_run_artifact_blocked": tester_artifact.get("blocked", ""),
        "report_artifact_exists": report_artifact.get("exists", ""),
        "report_artifact_ok": report_artifact.get("ok", ""),
        "report_artifact_closed": report_artifact.get("closed", ""),
        "report_artifact_pf": report_artifact.get("pf", ""),
    }


def command_flag_present(command: list[str], flag: str) -> bool:
    return flag in command


def infer_back_forward_execution_conditions(steps: list[dict[str, Any]]) -> dict[str, Any]:
    first_step = next((step for step in steps if isinstance(step, dict)), {})
    command = first_step.get("command") if isinstance(first_step.get("command"), list) else []
    command = [str(item) for item in command]
    if not command:
        return {}
    return {
        "per_step_timeout_seconds": command_option_value(command, "--timeout-seconds"),
        "since_minutes": command_option_value(command, "--since-minutes"),
        "min_closed": command_option_value(command, "--min-closed"),
        "from_date": command_option_value(command, "--from-date"),
        "to_date": command_option_value(command, "--to-date"),
        "forward_mode": command_option_value(command, "--forward-mode"),
        "sync_expert_parameters_set": command_flag_present(command, "--sync-expert-parameters-set"),
        "allow_running_terminal": command_flag_present(command, "--allow-running-terminal"),
        "allow_stale_compile": command_flag_present(command, "--allow-stale-compile"),
        "allow_invalid_risk_preset": command_flag_present(command, "--allow-invalid-risk-preset"),
        "checked_command_options": list(BACK_FORWARD_HINT_OPTIONS),
        "checked_command_flags": list(BACK_FORWARD_HINT_FLAGS),
    }


def back_forward_effective_condition(steps: list[dict[str, Any]], key: str) -> str:
    values: list[str] = []
    for step in steps:
        value = str(step.get(key) or "")
        if value and value not in values:
            values.append(value)
    return ",".join(values)


def back_forward_run_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {"exists": False}
    raw_steps = payload.get("steps") if isinstance(payload.get("steps"), list) else []
    steps = [row for row in (back_forward_step_summary(step) for step in raw_steps) if row]
    execution_conditions = (
        payload.get("execution_conditions") if isinstance(payload.get("execution_conditions"), dict) else {}
    )
    if not execution_conditions:
        execution_conditions = infer_back_forward_execution_conditions(steps)
    ready_status = payload.get("ready_status") if isinstance(payload.get("ready_status"), dict) else {}
    execution_window = (
        payload.get("execution_window") if isinstance(payload.get("execution_window"), dict) else {}
    )
    comparison = (
        payload.get("performance_comparison")
        if isinstance(payload.get("performance_comparison"), dict)
        else {}
    )
    manual_plan = (
        payload.get("manual_strategy_tester")
        if isinstance(payload.get("manual_strategy_tester"), dict)
        else {}
    )
    manual_steps = manual_plan.get("steps") if isinstance(manual_plan.get("steps"), list) else []
    manual_prerequisites = (
        payload.get("manual_prerequisites")
        if isinstance(payload.get("manual_prerequisites"), dict)
        else {}
    )
    plan_validation = (
        payload.get("back_forward_plan_validation")
        if isinstance(payload.get("back_forward_plan_validation"), dict)
        else {}
    )
    manual_collect_readiness = (
        payload.get("manual_collect_readiness")
        if isinstance(payload.get("manual_collect_readiness"), dict)
        else {}
    )
    strategy_tester_pack = (
        payload.get("mt5_strategy_tester_pack")
        if isinstance(payload.get("mt5_strategy_tester_pack"), dict)
        else {}
    )
    strategy_tester_pack_steps = (
        strategy_tester_pack.get("steps")
        if isinstance(strategy_tester_pack.get("steps"), list)
        else []
    )
    execution_hints = (
        payload.get("execution_hints")
        if isinstance(payload.get("execution_hints"), dict)
        else {}
    )
    evidence_state = str(payload.get("evidence_state") or "")
    if not evidence_state:
        evidence_state = back_forward_evidence_state(
            execute=payload.get("execute"),
            dry_run=payload.get("dry_run"),
            ok=payload.get("ok"),
            blocked_before_steps=payload.get("blocked_before_steps", ""),
            comparison=comparison,
        )
    return {
        "exists": True,
        "generated_at": payload.get("generated_at", ""),
        "ok": payload.get("ok"),
        "dry_run": payload.get("dry_run"),
        "execute": payload.get("execute"),
        "collect_only": payload.get("collect_only", ""),
        "launch_mt5": payload.get("launch_mt5", ""),
        "run_archive_preview": payload.get("run_archive_preview", ""),
        "evidence_state": evidence_state,
        "mode": payload.get("mode", ""),
        "run_id_prefix": payload.get("run_id_prefix", ""),
        "execution_hints": execution_hints,
        "execute_command_text": execution_hints.get("execute_command_text", ""),
        "manual_strategy_tester_available": manual_plan.get("available", bool(manual_steps)),
        "manual_collect_only_command_text": manual_plan.get(
            "recommended_collect_only_command_text", ""
        ),
        "manual_collect_only_command": manual_plan.get("recommended_collect_only_command", []),
        "manual_collect_only_note": manual_plan.get("collect_only_note", ""),
        "manual_run_start_after": manual_plan.get("manual_run_start_after", ""),
        "manual_collect_ready": manual_collect_readiness.get("ready", ""),
        "manual_collect_status": manual_collect_readiness.get("status", ""),
        "manual_collect_csv_count": manual_collect_readiness.get("csv_count", ""),
        "manual_collect_modified_after": manual_collect_readiness.get("modified_after", ""),
        "manual_collect_reason": manual_collect_readiness.get("reason", ""),
        "manual_collect_blocking_reasons": manual_collect_readiness.get("blocking_reasons", []),
        "manual_collect_next_action": manual_collect_readiness.get("next_action", ""),
        "manual_collect_steps": manual_collect_readiness.get("steps", []),
        "manual_step_count": len(manual_steps),
        "manual_steps": manual_steps,
        "mt5_strategy_tester_pack": strategy_tester_pack,
        "mt5_strategy_tester_pack_available": strategy_tester_pack.get(
            "available", bool(strategy_tester_pack_steps)
        ),
        "mt5_strategy_tester_pack_ready_for_manual_mt5_run": strategy_tester_pack.get(
            "ready_for_manual_mt5_run", ""
        ),
        "mt5_strategy_tester_pack_status": strategy_tester_pack.get("status", ""),
        "mt5_strategy_tester_pack_next_action": strategy_tester_pack.get("next_action", ""),
        "mt5_strategy_tester_pack_is_back_forward_pair": strategy_tester_pack.get(
            "is_back_forward_pair", ""
        ),
        "mt5_strategy_tester_pack_manual_run_start_after": strategy_tester_pack.get(
            "manual_run_start_after", ""
        ),
        "mt5_strategy_tester_pack_collect_command_text": strategy_tester_pack.get(
            "collect_command_text", ""
        ),
        "mt5_strategy_tester_pack_collect_ready": strategy_tester_pack.get("collect_ready", ""),
        "mt5_strategy_tester_pack_collect_status": strategy_tester_pack.get("collect_status", ""),
        "mt5_strategy_tester_pack_collect_reason": strategy_tester_pack.get("collect_reason", ""),
        "mt5_strategy_tester_pack_collect_note": strategy_tester_pack.get("collect_note", ""),
        "mt5_strategy_tester_pack_step_count": strategy_tester_pack.get(
            "step_count", len(strategy_tester_pack_steps)
        ),
        "mt5_strategy_tester_pack_steps": strategy_tester_pack_steps,
        "manual_prerequisites": manual_prerequisites,
        "manual_prerequisites_ready": manual_prerequisites.get("ready", ""),
        "manual_prerequisites_reasons": manual_prerequisites.get("reasons", []),
        "manual_prerequisites_compile_status_path": manual_prerequisites.get("path", ""),
        "manual_prerequisites_generated_at": manual_prerequisites.get("generated_at", ""),
        "back_forward_plan_validation": plan_validation,
        "back_forward_plan_validation_ready": plan_validation.get("ready", ""),
        "back_forward_plan_validation_status": plan_validation.get("status", ""),
        "back_forward_plan_validation_reasons": plan_validation.get("reasons", []),
        "execution_conditions": execution_conditions,
        "per_step_timeout_seconds": execution_conditions.get("per_step_timeout_seconds", ""),
        "since_minutes": execution_conditions.get("since_minutes", ""),
        "min_closed": execution_conditions.get("min_closed", ""),
        "from_date": execution_conditions.get("from_date", ""),
        "to_date": execution_conditions.get("to_date", ""),
        "forward_mode": execution_conditions.get("forward_mode", ""),
        "effective_from_date": back_forward_effective_condition(steps, "effective_from_date"),
        "effective_to_date": back_forward_effective_condition(steps, "effective_to_date"),
        "effective_forward_mode": back_forward_effective_condition(steps, "effective_forward_mode"),
        "sync_expert_parameters_set": execution_conditions.get("sync_expert_parameters_set", ""),
        "allow_running_terminal": execution_conditions.get("allow_running_terminal", ""),
        "allow_stale_compile": execution_conditions.get("allow_stale_compile", ""),
        "allow_invalid_risk_preset": execution_conditions.get("allow_invalid_risk_preset", ""),
        "refresh_ready_status": execution_conditions.get("refresh_ready_status", ""),
        "skip_ready_status_check": execution_conditions.get("skip_ready_status_check", ""),
        "skip_archive_preview": execution_conditions.get("skip_archive_preview", ""),
        "max_ready_status_age_seconds": execution_conditions.get("max_ready_status_age_seconds", ""),
        "blocked_before_steps": payload.get("blocked_before_steps", ""),
        "reason": payload.get("reason", ""),
        "execution_window_complete": execution_window.get("complete", ""),
        "total_timeout_seconds": execution_window.get("total_timeout_seconds", ""),
        "total_timeout_minutes": execution_window.get("total_timeout_minutes", ""),
        "timeout_start_reference_at": execution_window.get("timeout_start_reference_at", ""),
        "timeout_deadline_if_started_now": execution_window.get("timeout_deadline_if_started_now", ""),
        "timeout_deadline_epoch_if_started_now": execution_window.get("timeout_deadline_epoch_if_started_now", ""),
        "timeout_note": execution_window.get("note", ""),
        "timeout_steps": execution_window.get("steps", []),
        "ready_status_ok": ready_status.get("ok", ""),
        "ready_status_path": ready_status.get("path", ""),
        "ready_status_age_seconds": ready_status.get("age_seconds", ""),
        "ready_status_reasons": ready_status.get("reasons", []),
        "ready_status_mismatches": ready_status.get("mismatches", []),
        "ready_status_checked_step_keys": ready_status.get("checked_step_keys", []),
        "ready_status_checked_command_options": ready_status.get("checked_command_options", []),
        "ready_status_checked_command_flags": ready_status.get("checked_command_flags", []),
        "ready_status_checked_execution_conditions": ready_status.get("checked_execution_conditions", []),
        "ready_status_expected_execution_conditions": ready_status.get("expected_execution_conditions", {}),
        "ready_status_status_execution_conditions": ready_status.get("status_execution_conditions", {}),
        "step_count": len(steps),
        "step_labels": [step.get("label", "") for step in steps],
        "steps": steps,
        "performance_comparison": comparison,
        "performance_comparison_available": comparison.get("available", ""),
        "performance_comparison_status": comparison.get("status", ""),
        "performance_comparison_thresholds": comparison.get("thresholds", {}),
        "performance_comparison_rows": comparison.get("rows", []),
    }


def back_forward_execute_hint(back_forward_runner: dict[str, Any]) -> str:
    explicit_hint = str(back_forward_runner.get("execute_command_text") or "").strip()
    if explicit_hint:
        return explicit_hint
    mode = str(back_forward_runner.get("mode") or "both").strip() or "both"
    command = [
        "python3",
        "analysis/mt5_back_forward_run.py",
        "--mode",
        mode,
        "--execute",
        "--refresh-ready-status",
    ]
    run_id_prefix = str(back_forward_runner.get("run_id_prefix") or "").strip()
    if run_id_prefix:
        command.extend(["--run-id-prefix", run_id_prefix])
    steps = back_forward_runner.get("steps") if isinstance(back_forward_runner.get("steps"), list) else []
    first_step = next((step for step in steps if isinstance(step, dict)), {})
    source_command = first_step.get("command") if isinstance(first_step.get("command"), list) else []
    source_command = [str(item) for item in source_command]
    added_options: set[str] = set()
    for option in BACK_FORWARD_HINT_OPTIONS:
        value = command_option_value(source_command, option)
        if value:
            command.extend([option, value])
            added_options.add(option)
    added_flags: set[str] = set()
    for flag in BACK_FORWARD_HINT_FLAGS:
        if flag in source_command:
            command.append(flag)
            added_flags.add(flag)
    execution_conditions = (
        back_forward_runner.get("execution_conditions")
        if isinstance(back_forward_runner.get("execution_conditions"), dict)
        else {}
    )
    for key, option in BACK_FORWARD_RUNNER_HINT_CONDITION_OPTIONS.items():
        if option in added_options:
            continue
        value = execution_conditions.get(key, back_forward_runner.get(key, ""))
        if value not in (None, ""):
            command.extend([option, str(value)])
            added_options.add(option)
    for key, flag in BACK_FORWARD_RUNNER_HINT_CONDITION_FLAGS.items():
        if flag in added_flags:
            continue
        if execution_conditions.get(key, back_forward_runner.get(key)) is True:
            command.append(flag)
            added_flags.add(flag)
    return shlex.join(command)


def back_forward_execution_readiness(
    *,
    compile_status: dict[str, Any],
    running_processes: list[dict[str, Any]],
    artifact_freshness: dict[str, Any],
    back_forward_runner: dict[str, Any],
) -> dict[str, Any]:
    artifacts = (
        artifact_freshness.get("artifacts") if isinstance(artifact_freshness.get("artifacts"), dict) else {}
    )
    back_forward_freshness = (
        artifacts.get("back_forward_run") if isinstance(artifacts.get("back_forward_run"), dict) else {}
    )
    compile_freshness = (
        artifacts.get("compile_status") if isinstance(artifacts.get("compile_status"), dict) else {}
    )
    reasons: list[str] = []
    if running_processes:
        reasons.append("terminal_running")
    if compile_status.get("all_compiled_fresh") is not True:
        reasons.append("compile_not_fresh")
    if compile_status.get("all_tester_sets_synced") is False:
        reasons.append("tester_sets_not_synced")
    if compile_status.get("all_tester_configs_synced") is False:
        reasons.append("tester_configs_not_synced")
    if compile_freshness.get("fresh") is not True:
        reasons.append("required_artifact_stale_or_missing:compile_status")
    if back_forward_runner.get("exists") is not True:
        reasons.append("missing_back_forward_run")
    if back_forward_runner.get("ok") is not True:
        reasons.append("back_forward_runner_not_ok")
    if back_forward_runner.get("dry_run") is not True:
        reasons.append("back_forward_run_not_dry_run")
    if not back_forward_runner.get("steps"):
        reasons.append("back_forward_run_no_steps")
    if back_forward_freshness.get("fresh") is not True:
        reasons.append("required_artifact_stale_or_missing:back_forward_run")
    stale_required = []
    if compile_freshness.get("fresh") is not True:
        stale_required.append("compile_status")
    if back_forward_freshness.get("fresh") is not True:
        stale_required.append("back_forward_run")
    ready = not reasons
    return {
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "reasons": reasons,
        "required_fresh_artifacts": ["compile_status", "back_forward_run"],
        "stale_required_artifacts": stale_required,
        "compile_all_compiled_fresh": compile_status.get("all_compiled_fresh"),
        "compile_all_tester_sets_synced": compile_status.get("all_tester_sets_synced"),
        "compile_all_tester_configs_synced": compile_status.get("all_tester_configs_synced"),
        "terminal_running": bool(running_processes),
        "dry_run": back_forward_runner.get("dry_run"),
        "mode": back_forward_runner.get("mode", ""),
        "execute_hint": back_forward_execute_hint(back_forward_runner) if back_forward_runner.get("exists") else "",
    }


def manual_strategy_tester_readiness(
    *,
    back_forward_runner: dict[str, Any],
    back_forward_execution: dict[str, Any],
    running_processes: list[dict[str, Any]],
    manual_queue_launch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manual_steps = (
        back_forward_runner.get("manual_steps")
        if isinstance(back_forward_runner.get("manual_steps"), list)
        else []
    )
    collect_only_command = str(back_forward_runner.get("manual_collect_only_command_text") or "")
    reasons: list[str] = []
    if back_forward_runner.get("exists") is not True:
        reasons.append("missing_back_forward_run")
    if back_forward_runner.get("ok") is not True:
        reasons.append("back_forward_runner_not_ok")
    if back_forward_runner.get("manual_strategy_tester_available") is not True:
        reasons.append("manual_strategy_tester_plan_missing")
    if not manual_steps:
        reasons.append("manual_steps_missing")
    if not collect_only_command:
        reasons.append("manual_collect_only_command_missing")
    available = not reasons
    terminal_running = bool(running_processes)
    auto_blockers = (
        back_forward_execution.get("reasons")
        if isinstance(back_forward_execution.get("reasons"), list)
        else []
    )
    auto_launch_ready = back_forward_execution.get("ready", "")
    auto_launch_status = back_forward_execution.get("status", "")
    if isinstance(manual_queue_launch, dict):
        selected = (
            manual_queue_launch.get("selected_item")
            if isinstance(manual_queue_launch.get("selected_item"), dict)
            else {}
        )
        selected_queue_id = str(selected.get("queue_id") or "")
        launch_blockers = (
            manual_queue_launch.get("blocked_reasons")
            if isinstance(manual_queue_launch.get("blocked_reasons"), list)
            else []
        )
        if (
            manual_queue_launch.get("exists") is True
            and manual_queue_launch.get("selected") is True
            and selected_queue_id == "back_forward"
            and launch_blockers
        ):
            auto_blockers = launch_blockers
            auto_launch_ready = manual_queue_launch.get("ok", "")
            auto_launch_status = manual_queue_launch.get("status", "")
    auto_launch_blocked_by_running_terminal = (
        "terminal_running" in auto_blockers
        or "running_terminal_blocks_direct_config" in auto_blockers
        or terminal_running
    )
    note = ""
    if available and auto_launch_blocked_by_running_terminal:
        note = "MT5 is already open; run the listed Strategy Tester steps manually, then import results with collect-only."
    elif available:
        note = "Manual Strategy Tester path is available as an alternative to /config auto launch."
    return {
        "available": available,
        "status": "available" if available else "missing_plan",
        "reasons": reasons,
        "recommended": available and auto_launch_blocked_by_running_terminal,
        "auto_launch_ready": auto_launch_ready,
        "auto_launch_status": auto_launch_status,
        "auto_launch_blockers": auto_blockers,
        "auto_launch_blocked_by_running_terminal": auto_launch_blocked_by_running_terminal,
        "terminal_running": terminal_running,
        "collect_only_command_text": collect_only_command,
        "collect_only_note": back_forward_runner.get("manual_collect_only_note", ""),
        "manual_run_start_after": back_forward_runner.get("manual_run_start_after", ""),
        "manual_collect_ready": back_forward_runner.get("manual_collect_ready", ""),
        "manual_collect_status": back_forward_runner.get("manual_collect_status", ""),
        "manual_collect_csv_count": back_forward_runner.get("manual_collect_csv_count", ""),
        "manual_collect_modified_after": back_forward_runner.get("manual_collect_modified_after", ""),
        "manual_collect_reason": back_forward_runner.get("manual_collect_reason", ""),
        "manual_collect_blocking_reasons": back_forward_runner.get("manual_collect_blocking_reasons", []),
        "manual_collect_next_action": back_forward_runner.get("manual_collect_next_action", ""),
        "manual_collect_steps": back_forward_runner.get("manual_collect_steps", []),
        "manual_prerequisites_ready": back_forward_runner.get("manual_prerequisites_ready", ""),
        "manual_prerequisites_reasons": back_forward_runner.get("manual_prerequisites_reasons", []),
        "manual_prerequisites_compile_status_path": back_forward_runner.get(
            "manual_prerequisites_compile_status_path", ""
        ),
        "manual_prerequisites_generated_at": back_forward_runner.get("manual_prerequisites_generated_at", ""),
        "back_forward_plan_validation_ready": back_forward_runner.get(
            "back_forward_plan_validation_ready", ""
        ),
        "back_forward_plan_validation_status": back_forward_runner.get(
            "back_forward_plan_validation_status", ""
        ),
        "back_forward_plan_validation_reasons": back_forward_runner.get(
            "back_forward_plan_validation_reasons", []
        ),
        "step_count": len(manual_steps),
        "steps": manual_steps,
        "run_id_prefix": back_forward_runner.get("run_id_prefix", ""),
        "mode": back_forward_runner.get("mode", ""),
        "evidence_state": back_forward_runner.get("evidence_state", ""),
        "note": note,
    }


def manual_test_queue_summary(payload: dict[str, Any], *, path: str | Path | None) -> dict[str, Any]:
    if not payload:
        return {
            "exists": False,
            "path": str(path) if path else "",
            "ok": False,
            "status": "missing",
            "next_action": "refresh_mt5_manual_test_queue",
            "entry_count": 0,
            "total_entry_count": 0,
            "stale_entry_count": 0,
            "step_count": 0,
            "ready_to_collect_count": 0,
            "waiting_count": 0,
            "waiting_entry_count": 0,
            "manual_run_start_marked": False,
            "manual_run_start_marked_this_run": False,
            "manual_run_start_preserved": False,
            "manual_run_start_state_count": 0,
            "manual_run_start_state_marked_count": 0,
            "manual_run_start_effective_after_values": [],
            "manual_run_start_after_override": "",
            "step_report_ready_count": 0,
            "step_collect_ready_count": 0,
            "step_waiting_report_count": 0,
            "step_launch_needed_count": 0,
            "next_launch_step": {},
            "all_collect_ready": False,
            "blocking_reasons": ["manual_test_queue_missing"],
            "entries": [],
            "strategy_tester_targets": [],
            "operation_cards": [],
            "execution_checklist": [],
            "operator_handoff": {},
            "static_strategy_configs": [],
            "static_strategy_config_count": 0,
            "static_candidate_labels": [],
            "static_candidate_label_count": 0,
        }
    raw_entries = payload.get("entries") if isinstance(payload.get("entries"), list) else []
    entries: list[dict[str, Any]] = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        steps = entry.get("steps") if isinstance(entry.get("steps"), list) else []
        entries.append(
            {
                "order": entry.get("order", ""),
                "id": entry.get("id", ""),
                "title": entry.get("title", ""),
                "source_json": entry.get("source_json", ""),
                "available": entry.get("available", ""),
                "source_available": entry.get("source_available", ""),
                "current_for_execution": entry.get("current_for_execution", ""),
                "gate_stale_reason": entry.get("gate_stale_reason", ""),
                "stale_reasons": (
                    entry.get("stale_reasons") if isinstance(entry.get("stale_reasons"), list) else []
                ),
                "refresh_command_text": entry.get("refresh_command_text", ""),
                "runner_generated_at": entry.get("runner_generated_at") or entry.get("generated_at", ""),
                "promotion_generated_at": entry.get("promotion_generated_at", ""),
                "runner_promotion_generated_at": entry.get("runner_promotion_generated_at", ""),
                "current_promotion_generated_at": entry.get("current_promotion_generated_at", ""),
                "promotion_decision": entry.get("promotion_decision", ""),
                "current_promotion_decision": entry.get("current_promotion_decision", ""),
                "selected_action_present": entry.get("selected_action_present", ""),
                "selected_action_current": entry.get("selected_action_current", ""),
                "selected_action_mismatches": entry.get("selected_action_mismatches", []),
                "target": entry.get("target", ""),
                "kind": entry.get("kind", ""),
                "focus_side": entry.get("focus_side", ""),
                "manual_run_start_after": entry.get("manual_run_start_after", ""),
                "step_count": entry.get("step_count", len(steps)),
                "collect_ready": entry.get("collect_ready", ""),
                "collect_status": entry.get("collect_status", ""),
                "collect_reason": entry.get("collect_reason", ""),
                "collect_blocking_reasons": entry.get("collect_blocking_reasons", []),
                "collect_next_action": entry.get("collect_next_action", ""),
                "collect_csv_count": entry.get("collect_csv_count", ""),
                "collect_modified_after": entry.get("collect_modified_after", ""),
                "collect_only_command_text": entry.get("collect_only_command_text", ""),
                "steps": steps,
            }
        )
    raw_checklist = payload.get("execution_checklist") if isinstance(payload.get("execution_checklist"), list) else []
    execution_checklist = manual_test_queue_execution_checklist(raw_checklist, entries)
    raw_targets = (
        payload.get("strategy_tester_targets")
        if isinstance(payload.get("strategy_tester_targets"), list)
        else []
    )
    static_configs = (
        [str(item) for item in payload.get("static_strategy_configs")]
        if isinstance(payload.get("static_strategy_configs"), list)
        else []
    )
    static_candidate_labels = (
        [str(item) for item in payload.get("static_candidate_labels")]
        if isinstance(payload.get("static_candidate_labels"), list)
        else []
    )
    operator_handoff = (
        dict(payload.get("operator_handoff"))
        if isinstance(payload.get("operator_handoff"), dict)
        else {}
    )
    if not operator_handoff.get("progress_state"):
        handoff_state = str(operator_handoff.get("state") or "")
        if handoff_state == "run_next_mt5_strategy_tester_step":
            operator_handoff["progress_state"] = "mt5_step_launch_needed"
        elif handoff_state == "run_collect_dry_run_to_confirm_agent_csv":
            operator_handoff["progress_state"] = "reports_ready_waiting_collect_confirmation"
        elif handoff_state == "run_collect_dry_run":
            operator_handoff["progress_state"] = "collect_ready_all"
        elif handoff_state == "refresh_stale_runner_artifacts":
            operator_handoff["progress_state"] = "stale_runner_artifacts"
        elif handoff_state == "refresh_mt5_runner_artifacts":
            operator_handoff["progress_state"] = "missing_manual_strategy_tester_plans"
        elif (
            not payload.get("next_launch_step")
            and payload.get("waiting_count")
            and payload.get("step_launch_needed_count") == 0
        ):
            operator_handoff["progress_state"] = "reports_ready_waiting_collect_confirmation"
        else:
            operator_handoff["progress_state"] = handoff_state or ""
    return {
        "exists": True,
        "path": str(path) if path else "",
        "ok": payload.get("ok"),
        "generated_at": payload.get("generated_at", ""),
        "status": payload.get("status", ""),
        "next_action": payload.get("next_action", ""),
        "progress_state": operator_handoff.get("progress_state", ""),
        "entry_count": payload.get("entry_count", len(entries)),
        "total_entry_count": payload.get("total_entry_count", payload.get("entry_count", len(entries))),
        "stale_entry_count": payload.get(
            "stale_entry_count",
            sum(1 for entry in entries if entry.get("stale_reasons")),
        ),
        "step_count": payload.get(
            "step_count",
            sum(int(entry.get("step_count") or 0) for entry in entries),
        ),
        "ready_to_collect_count": payload.get("ready_to_collect_count", ""),
        "waiting_count": payload.get("waiting_count", ""),
        "waiting_entry_count": payload.get("waiting_entry_count", payload.get("waiting_count", "")),
        "manual_run_start_marked": payload.get("manual_run_start_marked", False),
        "manual_run_start_marked_this_run": payload.get(
            "manual_run_start_marked_this_run", False
        ),
        "manual_run_start_preserved": payload.get("manual_run_start_preserved", False),
        "manual_run_start_state_count": payload.get("manual_run_start_state_count", ""),
        "manual_run_start_state_marked_count": payload.get(
            "manual_run_start_state_marked_count", ""
        ),
        "manual_run_start_effective_after_values": (
            payload.get("manual_run_start_effective_after_values")
            if isinstance(payload.get("manual_run_start_effective_after_values"), list)
            else []
        ),
        "manual_run_start_after_override": payload.get("manual_run_start_after_override", ""),
        "step_report_ready_count": payload.get("step_report_ready_count", ""),
        "step_collect_ready_count": payload.get("step_collect_ready_count", ""),
        "step_waiting_report_count": payload.get("step_waiting_report_count", ""),
        "step_launch_needed_count": payload.get("step_launch_needed_count", ""),
        "step_report_ready_ids": payload.get(
            "step_report_ready_ids",
            operator_handoff.get("step_report_ready_ids", []),
        ),
        "step_collect_ready_ids": payload.get(
            "step_collect_ready_ids",
            operator_handoff.get("step_collect_ready_ids", []),
        ),
        "step_waiting_report_ids": payload.get(
            "step_waiting_report_ids",
            operator_handoff.get("step_waiting_report_ids", []),
        ),
        "step_launch_needed_ids": payload.get(
            "step_launch_needed_ids",
            operator_handoff.get("step_launch_needed_ids", []),
        ),
        "next_launch_step": (
            payload.get("next_launch_step") if isinstance(payload.get("next_launch_step"), dict) else {}
        ),
        "all_collect_ready": payload.get("all_collect_ready", ""),
        "blocking_reasons": (
            payload.get("blocking_reasons") if isinstance(payload.get("blocking_reasons"), list) else []
        ),
        "static_strategy_configs": static_configs,
        "static_strategy_config_count": len(static_configs),
        "static_candidate_labels": static_candidate_labels,
        "static_candidate_label_count": len(static_candidate_labels),
        "entries": entries,
        "strategy_tester_targets": manual_test_queue_strategy_targets(
            raw_targets,
            execution_checklist,
            entries,
        ),
        "operation_cards": (
            payload.get("operation_cards") if isinstance(payload.get("operation_cards"), list) else []
        ),
        "execution_checklist": execution_checklist,
        "operator_handoff": operator_handoff,
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


def manual_test_queue_entry_by_id(
    manual_queues: tuple[dict[str, Any], ...],
    entry_ids: tuple[str, ...],
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    wanted = {str(item) for item in entry_ids if str(item)}
    if not wanted:
        return {}
    for queue in manual_queues:
        entries = queue.get("entries") if isinstance(queue.get("entries"), list) else []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("id") or "") in wanted and manual_queue_entry_source_matches(
                entry, source_path
            ):
                return entry
    return {}


def manual_queue_entry_for_next_action(
    next_runner: dict[str, Any],
    manual_queues: tuple[dict[str, Any], ...],
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    target = str(next_runner.get("target") or "")
    kind = str(next_runner.get("kind") or "")
    if "score_weight" not in target and "score_weight" not in kind:
        return {}
    focus_side = str(next_runner.get("focus_side") or "").strip().lower()
    entry_ids: list[str] = []
    if focus_side in {"buy", "sell"}:
        entry_ids.append(f"score_weight_{focus_side}")
    entry_ids.extend(["score_weight_sell", "score_weight_buy"])
    return manual_test_queue_entry_by_id(manual_queues, tuple(entry_ids), source_path=source_path)


def apply_manual_queue_collect_command_overrides(
    *,
    back_forward_runner: dict[str, Any],
    next_action_runner: dict[str, Any],
    manual_queues: tuple[dict[str, Any], ...],
    back_forward_run_path: str | Path | None = None,
    next_action_run_path: str | Path | None = None,
) -> None:
    back_forward_entry = manual_test_queue_entry_by_id(
        manual_queues,
        ("back_forward",),
        source_path=back_forward_run_path,
    )
    if back_forward_entry:
        collect_command = str(back_forward_entry.get("collect_only_command_text") or "")
        manual_run_start_after = str(back_forward_entry.get("manual_run_start_after") or "")
        collect_modified_after = str(
            back_forward_entry.get("collect_modified_after") or manual_run_start_after
        )
        if collect_command:
            back_forward_runner["manual_collect_only_command_text"] = collect_command
            back_forward_runner["mt5_strategy_tester_pack_collect_command_text"] = collect_command
            execution_hints = back_forward_runner.get("execution_hints")
            if isinstance(execution_hints, dict):
                execution_hints["collect_only_command_text"] = collect_command
            pack = back_forward_runner.get("mt5_strategy_tester_pack")
            if isinstance(pack, dict):
                pack["collect_command_text"] = collect_command
        if manual_run_start_after:
            back_forward_runner["manual_run_start_after"] = manual_run_start_after
            back_forward_runner["mt5_strategy_tester_pack_manual_run_start_after"] = manual_run_start_after
            pack = back_forward_runner.get("mt5_strategy_tester_pack")
            if isinstance(pack, dict):
                pack["manual_run_start_after"] = manual_run_start_after
        if collect_modified_after:
            back_forward_runner["manual_collect_modified_after"] = collect_modified_after

    next_action_entry = manual_queue_entry_for_next_action(
        next_action_runner,
        manual_queues,
        source_path=next_action_run_path,
    )
    if next_action_entry:
        collect_command = str(next_action_entry.get("collect_only_command_text") or "")
        manual_run_start_after = str(next_action_entry.get("manual_run_start_after") or "")
        collect_modified_after = str(
            next_action_entry.get("collect_modified_after") or manual_run_start_after
        )
        if collect_command:
            next_action_runner["collect_only_command_text"] = collect_command
            next_action_runner["manual_collect_only_command_text"] = collect_command
        if manual_run_start_after:
            next_action_runner["manual_run_start_after"] = manual_run_start_after
        if collect_modified_after:
            next_action_runner["manual_collect_modified_after"] = collect_modified_after


def manual_queue_launch_summary(payload: dict[str, Any], *, path: str | Path | None) -> dict[str, Any]:
    if not payload:
        return {
            "exists": False,
            "path": str(path) if path else "",
            "ok": False,
            "status": "missing",
            "next_action": "run_mt5_manual_queue_launch_dry_run",
            "generated_at": "",
            "queue_path": "",
            "queue_status": "",
            "queue_next_action": "",
            "queue_entry_count": "",
            "queue_total_entry_count": "",
            "queue_stale_entry_count": "",
            "queue_completed_count": "",
            "queue_completed_entry_count": "",
            "queue_completed_entry_ids": [],
            "queue_step_count": "",
            "queue_ready_to_collect_count": "",
            "queue_waiting_count": "",
            "queue_step_report_ready_count": "",
            "queue_step_waiting_report_count": "",
            "queue_step_launch_needed_count": "",
            "queue_all_collect_ready": "",
            "queue_blocking_reasons": [],
            "queue_refresh": {
                "enabled": False,
                "ok": False,
                "status": "missing",
                "source_count": 0,
                "refreshed_sources": [],
            },
            "queue_operator_handoff_state": "",
            "queue_operator_handoff_next_mt5_step": {},
            "queue_operator_handoff_quick_input": {},
            "queue_operator_handoff_next_step_operator_summary": "",
            "queue_operator_handoff_next_step_summary": "",
            "queue_operator_handoff_next_step_collect_filter_summary": "",
            "queue_operator_handoff_collect_ready": "",
            "queue_operator_handoff_ready_entry_ids": [],
            "queue_operator_handoff_waiting_entry_ids": [],
            "queue_operator_handoff_completed_entry_ids": [],
            "queue_operator_handoff_stale_entry_ids": [],
            "queue_operator_handoff_collect_dry_run_command_text": "",
            "queue_operator_handoff_collect_execute_command_text": "",
            "queue_operator_handoff_collect_execute_and_refresh_analysis_command_text": "",
            "queue_operator_handoff_collect_execute_and_refresh_all_command_text": "",
            "queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text": "",
            "execute": False,
            "detached": "",
            "selected": False,
            "selected_order": "",
            "selected_queue_id": "",
            "selected_step_label": "",
            "selected_queue_step": "",
            "selected_item": {},
            "selected_step_fingerprint": "",
            "selected_step_config_fingerprint": "",
            "selected_step_run_fingerprint": "",
            "selected_expected_artifacts": {},
            "selected_expected_report_artifact": "",
            "selected_expected_report": "",
            "selected_matches_queue_handoff": "",
            "launch_command_kind": "",
            "mark_manual_run_start": "",
            "manual_run_start_mark": {},
            "manual_run_start_mark_status": "",
            "manual_run_start_mark_attempted": "",
            "manual_run_start_after": "",
            "command_text": "",
            "blocked": True,
            "blocked_reasons": ["manual_queue_launch_missing"],
            "running_terminal_count": "",
            "running_terminal_processes": [],
            "returncode": "",
            "process_pid": "",
        }
    selected_item = payload.get("selected_item") if isinstance(payload.get("selected_item"), dict) else {}
    queue_refresh = payload.get("queue_refresh") if isinstance(payload.get("queue_refresh"), dict) else {}
    refreshed_sources = (
        queue_refresh.get("refreshed_sources")
        if isinstance(queue_refresh.get("refreshed_sources"), list)
        else []
    )
    return {
        "exists": True,
        "path": str(path) if path else "",
        "ok": payload.get("ok"),
        "status": payload.get("status", ""),
        "next_action": payload.get("next_action", ""),
        "generated_at": payload.get("generated_at", ""),
        "queue_path": payload.get("queue_path", ""),
        "queue_status": payload.get("queue_status", ""),
        "queue_next_action": payload.get("queue_next_action", ""),
        "queue_entry_count": payload.get("queue_entry_count", ""),
        "queue_total_entry_count": payload.get("queue_total_entry_count", ""),
        "queue_stale_entry_count": payload.get("queue_stale_entry_count", ""),
        "queue_completed_count": payload.get("queue_completed_count", ""),
        "queue_completed_entry_count": payload.get("queue_completed_entry_count", ""),
        "queue_completed_entry_ids": (
            payload.get("queue_completed_entry_ids")
            if isinstance(payload.get("queue_completed_entry_ids"), list)
            else []
        ),
        "queue_step_count": payload.get("queue_step_count", ""),
        "queue_ready_to_collect_count": payload.get("queue_ready_to_collect_count", ""),
        "queue_waiting_count": payload.get("queue_waiting_count", ""),
        "queue_step_report_ready_count": payload.get("queue_step_report_ready_count", ""),
        "queue_step_waiting_report_count": payload.get("queue_step_waiting_report_count", ""),
        "queue_step_launch_needed_count": payload.get("queue_step_launch_needed_count", ""),
        "queue_all_collect_ready": payload.get("queue_all_collect_ready", ""),
        "queue_blocking_reasons": (
            payload.get("queue_blocking_reasons")
            if isinstance(payload.get("queue_blocking_reasons"), list)
            else []
        ),
        "queue_refresh": {
            "enabled": queue_refresh.get("enabled", ""),
            "ok": queue_refresh.get("ok", ""),
            "status": queue_refresh.get("status", ""),
            "source_count": len(refreshed_sources),
            "refreshed_sources": refreshed_sources,
        },
        "queue_operator_handoff_state": payload.get("queue_operator_handoff_state", ""),
        "queue_operator_handoff_next_mt5_step": (
            payload.get("queue_operator_handoff_next_mt5_step")
            if isinstance(payload.get("queue_operator_handoff_next_mt5_step"), dict)
            else {}
        ),
        "queue_operator_handoff_quick_input": (
            payload.get("queue_operator_handoff_quick_input")
            if isinstance(payload.get("queue_operator_handoff_quick_input"), dict)
            else {}
        ),
        "queue_operator_handoff_next_step_operator_summary": payload.get(
            "queue_operator_handoff_next_step_operator_summary", ""
        ),
        "queue_operator_handoff_next_step_summary": (
            payload.get("queue_operator_handoff_next_step_summary")
            or payload.get("queue_operator_handoff_next_step_operator_summary", "")
        ),
        "queue_operator_handoff_next_step_collect_filter_summary": payload.get(
            "queue_operator_handoff_next_step_collect_filter_summary", ""
        ),
        "queue_operator_handoff_collect_ready": payload.get(
            "queue_operator_handoff_collect_ready", ""
        ),
        "queue_operator_handoff_ready_entry_ids": (
            payload.get("queue_operator_handoff_ready_entry_ids")
            if isinstance(payload.get("queue_operator_handoff_ready_entry_ids"), list)
            else []
        ),
        "queue_operator_handoff_waiting_entry_ids": (
            payload.get("queue_operator_handoff_waiting_entry_ids")
            if isinstance(payload.get("queue_operator_handoff_waiting_entry_ids"), list)
            else []
        ),
        "queue_operator_handoff_completed_entry_ids": (
            payload.get("queue_operator_handoff_completed_entry_ids")
            if isinstance(payload.get("queue_operator_handoff_completed_entry_ids"), list)
            else []
        ),
        "queue_operator_handoff_stale_entry_ids": (
            payload.get("queue_operator_handoff_stale_entry_ids")
            if isinstance(payload.get("queue_operator_handoff_stale_entry_ids"), list)
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
        "queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text": (
            payload.get("queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text")
            or payload.get("queue_operator_handoff_collect_execute_and_refresh_all_command_text", "")
        ),
        "execute": payload.get("execute", ""),
        "detached": payload.get("detached", ""),
        "selected": payload.get("selected", ""),
        "selected_order": payload.get("selected_order", selected_item.get("order", "")),
        "selected_queue_id": payload.get("selected_queue_id", selected_item.get("queue_id", "")),
        "selected_step_label": payload.get("selected_step_label", selected_item.get("step_label", "")),
        "selected_queue_step": (
            payload.get("selected_queue_step")
            or "/".join(
                part
                for part in (
                    str(selected_item.get("queue_id") or ""),
                    str(selected_item.get("step_label") or ""),
                )
                if part
            )
        ),
        "selected_item": selected_item,
        "selected_step_fingerprint": payload.get("selected_step_fingerprint", ""),
        "selected_step_config_fingerprint": payload.get("selected_step_config_fingerprint", ""),
        "selected_step_run_fingerprint": payload.get("selected_step_run_fingerprint", ""),
        "selected_expected_artifacts": (
            payload.get("selected_expected_artifacts")
            if isinstance(payload.get("selected_expected_artifacts"), dict)
            else {}
        ),
        "selected_expected_report_artifact": payload.get("selected_expected_report_artifact", ""),
        "selected_expected_report": payload.get("selected_expected_report", ""),
        "selected_matches_queue_handoff": payload.get("selected_matches_queue_handoff", ""),
        "launch_command_kind": payload.get("launch_command_kind", ""),
        "mark_manual_run_start": payload.get("mark_manual_run_start", ""),
        "manual_run_start_mark": (
            payload.get("manual_run_start_mark")
            if isinstance(payload.get("manual_run_start_mark"), dict)
            else {}
        ),
        "manual_run_start_mark_status": payload.get("manual_run_start_mark_status", ""),
        "manual_run_start_mark_attempted": payload.get("manual_run_start_mark_attempted", ""),
        "manual_run_start_after": payload.get("manual_run_start_after", ""),
        "command_text": payload.get("command_text", ""),
        "blocked": payload.get("blocked", ""),
        "blocked_reasons": payload.get("blocked_reasons") if isinstance(payload.get("blocked_reasons"), list) else [],
        "running_terminal_count": payload.get("running_terminal_count", ""),
        "running_terminal_processes": (
            payload.get("running_terminal_processes")
            if isinstance(payload.get("running_terminal_processes"), list)
            else []
        ),
        "returncode": payload.get("returncode", ""),
        "process_pid": payload.get("process_pid", ""),
        "stdout_tail": payload.get("stdout_tail", ""),
        "stderr_tail": payload.get("stderr_tail", ""),
    }


def safe_count(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def manual_collect_run_next_action(summary: dict[str, Any]) -> str:
    if not summary.get("exists"):
        return "run_mt5_manual_collect_refresh_queue"
    if safe_count(summary.get("invalid_count")) > 0:
        return "fix_invalid_manual_collect_commands"
    if safe_count(summary.get("selected_count")) > 0 and not summary.get("execute"):
        return "run_mt5_manual_collect_with_execute"
    if safe_count(summary.get("waiting_count")) > 0:
        queue_next_action = str(summary.get("queue_next_action") or "")
        return queue_next_action or "run_manual_strategy_tester_steps_and_wait_for_reports"
    if summary.get("ok") is True:
        return "review_collected_mt5_reports"
    return "refresh_mt5_manual_collect_run"


def manual_collect_run_summary(payload: dict[str, Any], *, path: str | Path | None) -> dict[str, Any]:
    if not payload:
        summary = {
            "exists": False,
            "path": str(path) if path else "",
            "ok": False,
            "status": "missing",
            "generated_at": "",
            "queue_path": "",
            "queue_generated_at": "",
            "queue_status": "",
            "queue_next_action": "",
            "queue_step_count": 0,
            "queue_step_report_ready_count": 0,
            "queue_step_collect_ready_count": 0,
            "queue_step_waiting_report_count": 0,
            "queue_step_launch_needed_count": 0,
            "execute": False,
            "dry_run": True,
            "entry_count": 0,
            "ready_entry_count": 0,
            "selected_count": 0,
            "waiting_count": 0,
            "invalid_count": 0,
            "planned_count": 0,
            "skipped_count": 0,
            "execution_count": 0,
            "queue_refresh": {
                "enabled": False,
                "ok": False,
                "status": "missing",
                "source_count": 0,
                "refreshed_sources": [],
            },
            "operator_handoff": {},
            "blocking_reasons": [],
            "planned": [],
            "skipped": [],
            "invalid": [],
            "executions": [],
            "step_completion_audit": [],
        }
        summary["next_action"] = manual_collect_run_next_action(summary)
        return summary

    queue_refresh = payload.get("queue_refresh") if isinstance(payload.get("queue_refresh"), dict) else {}
    planned = payload.get("planned") if isinstance(payload.get("planned"), list) else []
    skipped = payload.get("skipped") if isinstance(payload.get("skipped"), list) else []
    invalid = payload.get("invalid") if isinstance(payload.get("invalid"), list) else []
    executions = payload.get("executions") if isinstance(payload.get("executions"), list) else []
    step_completion_audit = (
        payload.get("step_completion_audit")
        if isinstance(payload.get("step_completion_audit"), list)
        else []
    )
    refreshed_sources = (
        queue_refresh.get("refreshed_sources")
        if isinstance(queue_refresh.get("refreshed_sources"), list)
        else []
    )
    summary = {
        "exists": True,
        "path": str(path) if path else "",
        "ok": payload.get("ok"),
        "status": payload.get("status", ""),
        "generated_at": payload.get("generated_at", ""),
        "queue_path": payload.get("queue_path", ""),
        "queue_generated_at": payload.get("queue_generated_at", ""),
        "queue_status": payload.get("queue_status", ""),
        "queue_next_action": payload.get("queue_next_action", ""),
        "queue_step_count": payload.get("queue_step_count", ""),
        "queue_step_report_ready_count": payload.get("queue_step_report_ready_count", ""),
        "queue_step_collect_ready_count": payload.get("queue_step_collect_ready_count", ""),
        "queue_step_waiting_report_count": payload.get("queue_step_waiting_report_count", ""),
        "queue_step_launch_needed_count": payload.get("queue_step_launch_needed_count", ""),
        "source_next_action": payload.get("next_action", ""),
        "blocking_reasons": (
            payload.get("blocking_reasons") if isinstance(payload.get("blocking_reasons"), list) else []
        ),
        "execute": payload.get("execute", ""),
        "dry_run": payload.get("dry_run", ""),
        "entry_count": payload.get("entry_count", ""),
        "ready_entry_count": payload.get("ready_entry_count", ""),
        "selected_count": payload.get("selected_count", len(planned)),
        "waiting_count": payload.get("waiting_count", len(skipped)),
        "invalid_count": payload.get("invalid_count", len(invalid)),
        "planned_count": len(planned),
        "skipped_count": len(skipped),
        "execution_count": len(executions),
        "queue_refresh": {
            "enabled": queue_refresh.get("enabled", ""),
            "ok": queue_refresh.get("ok", ""),
            "status": queue_refresh.get("status", ""),
            "source_count": len(refreshed_sources),
            "refreshed_sources": refreshed_sources,
        },
        "operator_handoff": (
            payload.get("operator_handoff") if isinstance(payload.get("operator_handoff"), dict) else {}
        ),
        "planned": planned,
        "skipped": skipped,
        "invalid": invalid,
        "executions": executions,
        "step_completion_audit": step_completion_audit,
    }
    summary["next_action"] = str(payload.get("next_action") or manual_collect_run_next_action(summary))
    return summary


def manual_auto_collect_watch_summary(payload: dict[str, Any], *, path: str | Path | None) -> dict[str, Any]:
    if not payload:
        return {
            "exists": False,
            "path": str(path) if path else "",
            "ok": False,
            "status": "missing",
            "generated_at": "",
            "next_action": "start_mt5_manual_auto_collect_watch",
            "queue_path": "",
            "collect_output_json": "",
            "collect_output_md": "",
            "collect_dry_run_command_text": "",
            "collect_execute_command_text": "",
            "execute_ready": False,
            "ready_to_execute": False,
            "ready_for_collect_execute": False,
            "selected_count": 0,
            "waiting_count": 0,
            "invalid_count": 0,
            "queue_launch_status": "",
            "queue_launch_next_action": "",
            "queue_launch_blocked": "",
            "queue_launch_blocked_reasons": [],
            "operator_packet_status": "",
            "operator_packet_next_queue_step": "",
            "operator_packet_auto_launch_command_text": "",
            "operator_packet_auto_launch_command_available": False,
            "operator_packet_auto_launch_blocked": "",
            "operator_packet_auto_launch_blocked_reasons": [],
            "operator_packet_auto_launch_note": "",
            "operator_packet_strategy_source_time_refresh_status": "",
            "operator_packet_strategy_source_time_issue_labels": [],
            "operator_packet_strategy_source_time_candidate_issue_labels": [],
            "operator_packet_strategy_source_time_refresh_analysis_command_text": "",
            "operator_packet_strategy_source_time_refresh_analysis_command_available": False,
            "operator_packet_strategy_buy_candidate_gap_status": "",
            "operator_packet_strategy_buy_candidate_gap_reason": "",
            "operator_packet_strategy_buy_candidate_gap_diagnostic_labels": [],
            "operator_packet_strategy_buy_candidate_gap_collect_refresh_command_text": "",
            "operator_packet_strategy_buy_candidate_gap_collect_refresh_command_available": False,
            "operator_packet_strategy_operator_decision_status": "",
            "operator_packet_strategy_operator_decision_verdict": "",
            "operator_packet_strategy_operator_decision_adoptable": "",
            "operator_packet_strategy_operator_decision_primary_blocker": "",
            "operator_packet_strategy_operator_decision_primary_reason": "",
            "operator_packet_strategy_operator_decision_next_action": "",
            "operator_packet_strategy_operator_decision_summary": "",
            "operator_packet_strategy_operator_decision_command_text": "",
            "operator_packet_strategy_operator_decision_follow_up_command_text": "",
            "execution_enabled": False,
            "execution_attempted": False,
            "execution_returncode": "",
            "execution_status": "",
            "execution_selected_count": "",
            "execution_next_action": "",
        }
    queue_launch = (
        payload.get("queue_launch_refresh")
        if isinstance(payload.get("queue_launch_refresh"), dict)
        else payload.get("queue_launch")
        if isinstance(payload.get("queue_launch"), dict)
        else {}
    )
    operator_packet = (
        payload.get("operator_packet_refresh")
        if isinstance(payload.get("operator_packet_refresh"), dict)
        else payload.get("operator_packet")
        if isinstance(payload.get("operator_packet"), dict)
        else {}
    )
    execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
    return {
        "exists": True,
        "path": str(path) if path else "",
        "ok": payload.get("ok"),
        "status": payload.get("status", ""),
        "generated_at": payload.get("generated_at", ""),
        "next_action": payload.get("next_action", ""),
        "queue_path": payload.get("queue_path") or payload.get("queue", ""),
        "collect_output_json": payload.get("collect_output_json", ""),
        "collect_output_md": payload.get("collect_output_md", ""),
        "collect_dry_run_command_text": payload.get("collect_dry_run_command_text", ""),
        "collect_execute_command_text": payload.get("collect_execute_command_text", ""),
        "execute_ready": payload.get("execute_ready", ""),
        "ready_to_execute": payload.get("ready_to_execute", ""),
        "ready_for_collect_execute": payload.get("ready_for_collect_execute", ""),
        "selected_count": payload.get("selected_count", ""),
        "waiting_count": payload.get("waiting_count", ""),
        "invalid_count": payload.get("invalid_count", ""),
        "queue_launch_status": queue_launch.get("status", ""),
        "queue_launch_next_action": queue_launch.get("next_action", ""),
        "queue_launch_blocked": queue_launch.get("blocked", ""),
        "queue_launch_blocked_reasons": (
            queue_launch.get("blocked_reasons")
            if isinstance(queue_launch.get("blocked_reasons"), list)
            else []
        ),
        "operator_packet_status": operator_packet.get("status", ""),
        "operator_packet_next_queue_step": operator_packet.get("next_queue_step", ""),
        "operator_packet_auto_launch_command_text": (
            payload.get("operator_packet_auto_launch_command_text")
            or operator_packet.get("auto_launch_command_text", "")
        ),
        "operator_packet_auto_launch_command_available": (
            payload.get("operator_packet_auto_launch_command_available")
            if payload.get("operator_packet_auto_launch_command_available") not in (None, "")
            else operator_packet.get("auto_launch_command_available", "")
        ),
        "operator_packet_auto_launch_blocked": (
            payload.get("operator_packet_auto_launch_blocked")
            if payload.get("operator_packet_auto_launch_blocked") not in (None, "")
            else operator_packet.get("auto_launch_blocked", "")
        ),
        "operator_packet_auto_launch_blocked_reasons": (
            payload.get("operator_packet_auto_launch_blocked_reasons")
            if isinstance(payload.get("operator_packet_auto_launch_blocked_reasons"), list)
            else operator_packet.get("auto_launch_blocked_reasons", [])
            if isinstance(operator_packet.get("auto_launch_blocked_reasons"), list)
            else []
        ),
        "operator_packet_auto_launch_note": (
            payload.get("operator_packet_auto_launch_note")
            or operator_packet.get("auto_launch_note", "")
        ),
        "operator_packet_strategy_source_time_refresh_status": (
            payload.get("operator_packet_strategy_source_time_refresh_status")
            or operator_packet.get("strategy_source_time_refresh_status", "")
        ),
        "operator_packet_strategy_source_time_issue_labels": (
            payload.get("operator_packet_strategy_source_time_issue_labels")
            if isinstance(payload.get("operator_packet_strategy_source_time_issue_labels"), list)
            else operator_packet.get("strategy_source_time_issue_labels", [])
            if isinstance(operator_packet.get("strategy_source_time_issue_labels"), list)
            else []
        ),
        "operator_packet_strategy_source_time_candidate_issue_labels": (
            payload.get("operator_packet_strategy_source_time_candidate_issue_labels")
            if isinstance(
                payload.get("operator_packet_strategy_source_time_candidate_issue_labels"), list
            )
            else operator_packet.get("strategy_source_time_candidate_issue_labels", [])
            if isinstance(operator_packet.get("strategy_source_time_candidate_issue_labels"), list)
            else []
        ),
        "operator_packet_strategy_source_time_refresh_analysis_command_text": (
            payload.get("operator_packet_strategy_source_time_refresh_analysis_command_text")
            or operator_packet.get("strategy_source_time_refresh_analysis_command_text", "")
        ),
        "operator_packet_strategy_source_time_refresh_analysis_command_available": (
            payload.get(
                "operator_packet_strategy_source_time_refresh_analysis_command_available"
            )
            if payload.get(
                "operator_packet_strategy_source_time_refresh_analysis_command_available"
            )
            not in (None, "")
            else bool(operator_packet.get("strategy_source_time_refresh_analysis_command_text"))
        ),
        "operator_packet_strategy_buy_candidate_gap_status": (
            payload.get("operator_packet_strategy_buy_candidate_gap_status")
            or operator_packet.get("strategy_buy_candidate_gap_status", "")
        ),
        "operator_packet_strategy_buy_candidate_gap_reason": (
            payload.get("operator_packet_strategy_buy_candidate_gap_reason")
            or operator_packet.get("strategy_buy_candidate_gap_reason", "")
        ),
        "operator_packet_strategy_buy_candidate_gap_diagnostic_labels": (
            payload.get("operator_packet_strategy_buy_candidate_gap_diagnostic_labels")
            if isinstance(
                payload.get("operator_packet_strategy_buy_candidate_gap_diagnostic_labels"), list
            )
            else operator_packet.get("strategy_buy_candidate_gap_diagnostic_labels", [])
            if isinstance(operator_packet.get("strategy_buy_candidate_gap_diagnostic_labels"), list)
            else []
        ),
        "operator_packet_strategy_buy_candidate_gap_collect_refresh_command_text": (
            payload.get("operator_packet_strategy_buy_candidate_gap_collect_refresh_command_text")
            or operator_packet.get("strategy_buy_candidate_gap_collect_refresh_command_text", "")
        ),
        "operator_packet_strategy_buy_candidate_gap_collect_refresh_command_available": (
            payload.get(
                "operator_packet_strategy_buy_candidate_gap_collect_refresh_command_available"
            )
            if payload.get(
                "operator_packet_strategy_buy_candidate_gap_collect_refresh_command_available"
            )
            not in (None, "")
            else bool(operator_packet.get("strategy_buy_candidate_gap_collect_refresh_command_text"))
        ),
        "operator_packet_strategy_operator_decision_status": (
            payload.get("operator_packet_strategy_operator_decision_status")
            or operator_packet.get("strategy_operator_decision_status", "")
        ),
        "operator_packet_strategy_operator_decision_verdict": (
            payload.get("operator_packet_strategy_operator_decision_verdict")
            or operator_packet.get("strategy_operator_decision_verdict", "")
        ),
        "operator_packet_strategy_operator_decision_adoptable": (
            payload.get("operator_packet_strategy_operator_decision_adoptable")
            if payload.get("operator_packet_strategy_operator_decision_adoptable") not in (None, "")
            else operator_packet.get("strategy_operator_decision_adoptable", "")
        ),
        "operator_packet_strategy_operator_decision_primary_blocker": (
            payload.get("operator_packet_strategy_operator_decision_primary_blocker")
            or operator_packet.get("strategy_operator_decision_primary_blocker", "")
        ),
        "operator_packet_strategy_operator_decision_primary_reason": (
            payload.get("operator_packet_strategy_operator_decision_primary_reason")
            or operator_packet.get("strategy_operator_decision_primary_reason", "")
        ),
        "operator_packet_strategy_operator_decision_next_action": (
            payload.get("operator_packet_strategy_operator_decision_next_action")
            or operator_packet.get("strategy_operator_decision_next_action", "")
        ),
        "operator_packet_strategy_operator_decision_summary": (
            payload.get("operator_packet_strategy_operator_decision_summary")
            or operator_packet.get("strategy_operator_decision_summary", "")
        ),
        "operator_packet_strategy_operator_decision_command_text": (
            payload.get("operator_packet_strategy_operator_decision_command_text")
            or operator_packet.get("strategy_operator_decision_command_text", "")
        ),
        "operator_packet_strategy_operator_decision_follow_up_command_text": (
            payload.get("operator_packet_strategy_operator_decision_follow_up_command_text")
            or operator_packet.get("strategy_operator_decision_follow_up_command_text", "")
        ),
        "execution_enabled": execution.get("enabled", ""),
        "execution_attempted": execution.get("attempted", ""),
        "execution_returncode": execution.get("returncode", ""),
        "execution_status": execution.get("status", ""),
        "execution_selected_count": execution.get("selected_count", ""),
        "execution_next_action": execution.get("next_action", ""),
    }


def back_forward_quick_input_from_step(step: object) -> dict[str, Any]:
    if not isinstance(step, dict) or not step:
        return {}
    quick_input = step.get("quick_input")
    if isinstance(quick_input, dict) and quick_input:
        return quick_input
    if step.get("queue_step"):
        from_date = str(step.get("from_date") or "")
        to_date = str(step.get("to_date") or "")
        if not (from_date or to_date):
            from_date, to_date = split_quick_input_dates(step.get("dates"))
        return {
            "queue_step": step.get("queue_step", ""),
            "purpose": step.get("purpose", ""),
            "expert": step.get("expert", ""),
            "symbol": step.get("symbol", ""),
            "period": step.get("period", ""),
            "model": step.get("model", ""),
            "from_date": from_date,
            "to_date": to_date,
            "dates": step.get("dates", ""),
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
    return mt5_quick_input_from_step(step)


def manual_operator_packet_summary(payload: dict[str, Any], *, path: str | Path | None) -> dict[str, Any]:
    if not payload:
        return {
            "exists": False,
            "path": str(path) if path else "",
            "ok": False,
            "status": "missing",
            "generated_at": "",
            "queue_json": "",
            "queue_status": "",
            "queue_next_action": "",
            "progress_state": "",
            "next_queue_step": "",
            "next_operator_action": "",
            "next_operator_mode": "",
            "next_operator_instruction": "",
            "next_operator_command_text": "",
            "next_operator_before_mt5_command_text": "",
            "next_operator_follow_up_command_text": "",
            "next_operator_verification": "",
            "next_operator_launch_state": "",
            "auto_launch_command_text": "",
            "auto_launch_command_available": False,
            "auto_launch_blocked": "",
            "auto_launch_blocked_reasons": [],
            "auto_launch_note": "",
            "back_forward_quick_start_status": "",
            "back_forward_quick_start_step_count": 0,
            "back_forward_quick_start_waiting_step_count": 0,
            "back_forward_quick_start_current_queue_step": "",
            "back_forward_quick_start_current_purpose": "",
            "back_forward_quick_start_steps": [],
            "back_forward_quick_start_quick_inputs": [],
            "back_forward_quick_start_current_quick_input": {},
            "back_forward_quick_start_backtest_quick_input": {},
            "back_forward_quick_start_forward_quick_input": {},
            "back_forward_quick_start_collect_command_text": "",
            "back_forward_quick_start_full_queue_collect_command_text": "",
            "back_forward_quick_start_auto_launch_blocked": "",
            "back_forward_quick_start_auto_launch_blocked_reasons": [],
            "back_forward_completion_summary": "",
            "back_forward_completion_manual_run_start_after": "",
            "back_forward_completion_expected_step_count": 0,
            "back_forward_completion_waiting_step_count": 0,
            "back_forward_completion_collect_command_text": "",
            "back_forward_completion_steps": [],
            "back_forward_completion_decision_thresholds": {},
            "next_step_quick_input": {},
            "manual_run_start_marked": False,
            "manual_run_start_marked_this_run": False,
            "manual_run_start_preserved": False,
            "manual_run_start_state_count": 0,
            "manual_run_start_state_marked_count": 0,
            "manual_run_start_effective_after": "",
            "manual_run_start_effective_after_values": [],
            "manual_run_start_after_override": "",
            "next_step_operator_summary": "",
            "next_step_summary": "",
            "next_step_collect_filter_summary": "",
            "strategy_back_forward_decision_status": "",
            "strategy_back_forward_decision_adoptable": "",
            "strategy_back_forward_decision_next_action": "",
            "strategy_back_forward_decision_reason": "",
            "strategy_back_forward_decision_thresholds": {},
            "strategy_back_forward_decision_collect_command_text": "",
            "strategy_back_forward_decision_sample_shortage_recovery_command_text": "",
            "strategy_back_forward_decision_sample_shortage_recovery_range_strategy": "",
            "strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date": "",
            "strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date": "",
            "strategy_operator_decision_status": "",
            "strategy_operator_decision_verdict": "",
            "strategy_operator_decision_adoptable": "",
            "strategy_operator_decision_primary_blocker": "",
            "strategy_operator_decision_primary_reason": "",
            "strategy_operator_decision_next_action": "",
            "strategy_operator_decision_summary": "",
            "strategy_operator_decision_command_text": "",
            "strategy_operator_decision_follow_up_command_text": "",
            "ready_to_collect_count": 0,
            "waiting_count": 0,
            "step_count": 0,
            "static_strategy_config_count": 0,
            "static_candidate_label_count": 0,
            "static_strategy_configs": [],
            "static_candidate_labels": [],
            "mt5_run_sheet": {},
            "mt5_run_sheet_next_step": {},
            "mt5_run_sheet_back_forward_steps": [],
            "next_step": {},
            "launch_status": {},
            "after_mt5": {},
            "blocking_reasons": ["manual_operator_packet_missing"],
        }
    next_operator = (
        payload.get("next_operator_action")
        if isinstance(payload.get("next_operator_action"), dict)
        else {}
    )
    next_step = payload.get("next_step") if isinstance(payload.get("next_step"), dict) else {}
    launch_status = payload.get("launch_status") if isinstance(payload.get("launch_status"), dict) else {}
    after_mt5 = payload.get("after_mt5") if isinstance(payload.get("after_mt5"), dict) else {}
    strategy_analysis = (
        payload.get("strategy_analysis")
        if isinstance(payload.get("strategy_analysis"), dict)
        else {}
    )
    mt5_run_sheet = (
        payload.get("mt5_run_sheet") if isinstance(payload.get("mt5_run_sheet"), dict) else {}
    )
    mt5_run_sheet_commands = (
        mt5_run_sheet.get("commands")
        if isinstance(mt5_run_sheet.get("commands"), dict)
        else {}
    )
    back_forward_quick_start = (
        payload.get("back_forward_quick_start")
        if isinstance(payload.get("back_forward_quick_start"), dict)
        else {}
    )
    back_forward_completion = (
        back_forward_quick_start.get("completion_criteria")
        if isinstance(back_forward_quick_start.get("completion_criteria"), dict)
        else {}
    )
    back_forward_quick_start_current_step = (
        back_forward_quick_start.get("current_step")
        if isinstance(back_forward_quick_start.get("current_step"), dict)
        else {}
    )
    back_forward_quick_start_steps = (
        back_forward_quick_start.get("steps")
        if isinstance(back_forward_quick_start.get("steps"), list)
        else []
    )
    if not back_forward_quick_start_steps and isinstance(
        mt5_run_sheet.get("back_forward_steps"), list
    ):
        back_forward_quick_start_steps = mt5_run_sheet.get("back_forward_steps", [])
    back_forward_quick_start_quick_inputs = (
        back_forward_quick_start.get("quick_inputs")
        if isinstance(back_forward_quick_start.get("quick_inputs"), list)
        else [
            back_forward_quick_input_from_step(step)
            for step in back_forward_quick_start_steps
            if isinstance(step, dict)
        ]
    )
    back_forward_quick_start_current_quick_input = (
        back_forward_quick_start.get("current_quick_input")
        if isinstance(back_forward_quick_start.get("current_quick_input"), dict)
        else back_forward_quick_input_from_step(back_forward_quick_start_current_step)
    )
    back_forward_quick_start_backtest_quick_input = (
        back_forward_quick_start.get("backtest_quick_input")
        if isinstance(back_forward_quick_start.get("backtest_quick_input"), dict)
        else next(
            (
                quick
                for quick in back_forward_quick_start_quick_inputs
                if isinstance(quick, dict)
                and str(quick.get("queue_step") or "") == "back_forward/backtest"
            ),
            {},
        )
    )
    back_forward_quick_start_forward_quick_input = (
        back_forward_quick_start.get("forward_quick_input")
        if isinstance(back_forward_quick_start.get("forward_quick_input"), dict)
        else next(
            (
                quick
                for quick in back_forward_quick_start_quick_inputs
                if isinstance(quick, dict)
                and str(quick.get("queue_step") or "") == "back_forward/forward"
            ),
            {},
        )
    )
    quick_input = (
        next_step.get("quick_input") if isinstance(next_step.get("quick_input"), dict) else {}
    )
    if not quick_input:
        quick_input = mt5_quick_input_from_step(next_step)
    before_mt5_command = str(
        after_mt5.get("manual_run_start_mark_command_text")
        or payload.get("manual_run_start_mark_command_text")
        or ""
    )
    manual_run_start_effective_after_values = (
        payload.get("manual_run_start_effective_after_values")
        if isinstance(payload.get("manual_run_start_effective_after_values"), list)
        else []
    )
    manual_run_start_effective_after = str(
        payload.get("manual_run_start_effective_after")
        or "; ".join(str(item) for item in manual_run_start_effective_after_values if str(item))
        or payload.get("manual_run_start_after_override")
        or ""
    )
    auto_launch_command_text = str(
        payload.get("auto_launch_command_text")
        or mt5_run_sheet_commands.get("auto_launch")
        or ""
    )
    return {
        "exists": True,
        "path": str(path) if path else "",
        "ok": payload.get("ok"),
        "status": payload.get("status", ""),
        "generated_at": payload.get("generated_at", ""),
        "queue_json": payload.get("queue_json", ""),
        "queue_status": payload.get("queue_status", ""),
        "queue_next_action": payload.get("queue_next_action", ""),
        "progress_state": payload.get("progress_state", ""),
        "next_queue_step": (
            next_operator.get("queue_step")
            or payload.get("next_queue_step", "")
            or next_step.get("queue_step", "")
        ),
        "next_operator_action": (
            payload.get("next_operator_action_name") or next_operator.get("action", "")
        ),
        "next_operator_mode": payload.get("next_operator_mode") or next_operator.get("mode", ""),
        "next_operator_instruction": (
            payload.get("next_operator_instruction") or next_operator.get("instruction", "")
        ),
        "next_operator_command_text": (
            payload.get("next_operator_command_text") or next_operator.get("command_text", "")
        ),
        "next_operator_before_mt5_command_text": before_mt5_command,
        "next_operator_follow_up_command_text": (
            payload.get("next_operator_follow_up_command_text")
            or next_operator.get("follow_up_command_text", "")
        ),
        "next_operator_verification": (
            payload.get("next_operator_verification") or next_operator.get("verification", "")
        ),
        "next_operator_launch_state": (
            payload.get("next_operator_launch_state")
            or next_operator.get("launch_state")
            or launch_status.get("auto_launch_state", "")
        ),
        "auto_launch_command_text": auto_launch_command_text,
        "auto_launch_command_available": bool(
            payload.get("auto_launch_command_available")
            or auto_launch_command_text
        ),
        "auto_launch_blocked": mt5_run_sheet_commands.get("auto_launch_blocked", ""),
        "auto_launch_blocked_reasons": (
            mt5_run_sheet_commands.get("auto_launch_blocked_reasons")
            if isinstance(mt5_run_sheet_commands.get("auto_launch_blocked_reasons"), list)
            else []
        ),
        "auto_launch_note": mt5_run_sheet_commands.get("auto_launch_note", ""),
        "back_forward_quick_start_status": back_forward_quick_start.get("status", ""),
        "back_forward_quick_start_step_count": back_forward_quick_start.get("step_count", ""),
        "back_forward_quick_start_waiting_step_count": back_forward_quick_start.get(
            "waiting_step_count",
            "",
        ),
        "back_forward_quick_start_current_queue_step": back_forward_quick_start_current_step.get(
            "queue_step",
            "",
        ),
        "back_forward_quick_start_current_purpose": back_forward_quick_start_current_step.get(
            "purpose",
            "",
        ),
        "back_forward_quick_start_steps": back_forward_quick_start_steps,
        "back_forward_quick_start_quick_inputs": back_forward_quick_start_quick_inputs,
        "back_forward_quick_start_current_quick_input": (
            back_forward_quick_start_current_quick_input
        ),
        "back_forward_quick_start_backtest_quick_input": (
            back_forward_quick_start_backtest_quick_input
        ),
        "back_forward_quick_start_forward_quick_input": (
            back_forward_quick_start_forward_quick_input
        ),
        "back_forward_quick_start_collect_command_text": back_forward_quick_start.get(
            "collect_command_text",
            "",
        ),
        "back_forward_quick_start_full_queue_collect_command_text": back_forward_quick_start.get(
            "full_queue_collect_command_text",
            "",
        ),
        "back_forward_quick_start_auto_launch_blocked": back_forward_quick_start.get(
            "auto_launch_blocked",
            "",
        ),
        "back_forward_quick_start_auto_launch_blocked_reasons": (
            back_forward_quick_start.get("auto_launch_blocked_reasons")
            if isinstance(back_forward_quick_start.get("auto_launch_blocked_reasons"), list)
            else []
        ),
        "back_forward_completion_summary": back_forward_completion.get("summary", ""),
        "back_forward_completion_manual_run_start_after": back_forward_completion.get(
            "manual_run_start_after",
            "",
        ),
        "back_forward_completion_expected_step_count": back_forward_completion.get(
            "expected_step_count",
            "",
        ),
        "back_forward_completion_waiting_step_count": back_forward_completion.get(
            "waiting_step_count",
            "",
        ),
        "back_forward_completion_collect_command_text": back_forward_completion.get(
            "collect_command_text",
            "",
        ),
        "back_forward_completion_steps": (
            back_forward_completion.get("steps")
            if isinstance(back_forward_completion.get("steps"), list)
            else []
        ),
        "back_forward_completion_decision_thresholds": (
            back_forward_completion.get("decision_thresholds")
            if isinstance(back_forward_completion.get("decision_thresholds"), dict)
            else {}
        ),
        "next_step_quick_input": quick_input,
        "manual_run_start_marked": payload.get("manual_run_start_marked", False),
        "manual_run_start_marked_this_run": payload.get(
            "manual_run_start_marked_this_run", False
        ),
        "manual_run_start_preserved": payload.get("manual_run_start_preserved", False),
        "manual_run_start_state_count": payload.get("manual_run_start_state_count", ""),
        "manual_run_start_state_marked_count": payload.get(
            "manual_run_start_state_marked_count", ""
        ),
        "manual_run_start_effective_after": manual_run_start_effective_after,
        "manual_run_start_effective_after_values": manual_run_start_effective_after_values,
        "manual_run_start_after_override": payload.get("manual_run_start_after_override", ""),
        "next_step_operator_summary": (
            next_step.get("summary") or operator_step_summary(next_step)
        ),
        "next_step_summary": (
            payload.get("next_step_summary")
            or next_step.get("summary")
            or operator_step_summary(next_step)
        ),
        "next_step_collect_filter_summary": (
            next_step.get("collect_filter") or operator_collect_filter_summary(next_step)
        ),
        "strategy_back_forward_decision_status": strategy_analysis.get(
            "back_forward_decision_status", ""
        ),
        "strategy_back_forward_decision_adoptable": strategy_analysis.get(
            "back_forward_decision_adoptable", ""
        ),
        "strategy_back_forward_decision_next_action": strategy_analysis.get(
            "back_forward_decision_next_action", ""
        ),
        "strategy_back_forward_decision_reason": strategy_analysis.get(
            "back_forward_decision_reason", ""
        ),
        "strategy_back_forward_decision_thresholds": (
            strategy_analysis.get("back_forward_decision_thresholds")
            if isinstance(strategy_analysis.get("back_forward_decision_thresholds"), dict)
            else {}
        ),
        "strategy_back_forward_decision_collect_command_text": strategy_analysis.get(
            "back_forward_decision_collect_command_text", ""
        ),
        "strategy_back_forward_decision_sample_shortage_recovery_command_text": strategy_analysis.get(
            "back_forward_decision_sample_shortage_recovery_command_text", ""
        ),
        "strategy_back_forward_decision_sample_shortage_recovery_range_strategy": strategy_analysis.get(
            "back_forward_decision_sample_shortage_recovery_range_strategy", ""
        ),
        "strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date": strategy_analysis.get(
            "back_forward_decision_sample_shortage_recovery_suggested_from_date", ""
        ),
        "strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date": strategy_analysis.get(
            "back_forward_decision_sample_shortage_recovery_suggested_to_date", ""
        ),
        "strategy_operator_decision_status": strategy_analysis.get("operator_decision_status", ""),
        "strategy_operator_decision_verdict": strategy_analysis.get("operator_decision_verdict", ""),
        "strategy_operator_decision_adoptable": strategy_analysis.get(
            "operator_decision_adoptable", ""
        ),
        "strategy_operator_decision_primary_blocker": strategy_analysis.get(
            "operator_decision_primary_blocker", ""
        ),
        "strategy_operator_decision_primary_reason": strategy_analysis.get(
            "operator_decision_primary_reason", ""
        ),
        "strategy_operator_decision_next_action": strategy_analysis.get(
            "operator_decision_next_action", ""
        ),
        "strategy_operator_decision_summary": strategy_analysis.get(
            "operator_decision_summary", ""
        ),
        "strategy_operator_decision_command_text": strategy_analysis.get(
            "operator_decision_command_text", ""
        ),
        "strategy_operator_decision_follow_up_command_text": strategy_analysis.get(
            "operator_decision_follow_up_command_text", ""
        ),
        "ready_to_collect_count": payload.get(
            "ready_to_collect_count",
            next_operator.get("ready_to_collect_count", 0),
        ),
        "waiting_count": payload.get("waiting_count", next_operator.get("waiting_count", 0)),
        "step_count": payload.get("step_count", ""),
        "static_strategy_config_count": payload.get("static_strategy_config_count", ""),
        "static_candidate_label_count": payload.get("static_candidate_label_count", ""),
        "static_strategy_configs": (
            payload.get("static_strategy_configs")
            if isinstance(payload.get("static_strategy_configs"), list)
            else []
        ),
        "static_candidate_labels": (
            payload.get("static_candidate_labels")
            if isinstance(payload.get("static_candidate_labels"), list)
            else []
        ),
        "mt5_run_sheet": mt5_run_sheet,
        "mt5_run_sheet_next_step": (
            mt5_run_sheet.get("next_step")
            if isinstance(mt5_run_sheet.get("next_step"), dict)
            else {}
        ),
        "mt5_run_sheet_back_forward_steps": (
            mt5_run_sheet.get("back_forward_steps")
            if isinstance(mt5_run_sheet.get("back_forward_steps"), list)
            else []
        ),
        "next_step": next_step,
        "launch_status": launch_status,
        "after_mt5": after_mt5,
        "blocking_reasons": (
            payload.get("blocking_reasons") if isinstance(payload.get("blocking_reasons"), list) else []
        ),
    }


def mt5_operator_handoff_summary(
    *,
    manual_strategy_tester: dict[str, Any],
    manual_test_queue: dict[str, Any],
    manual_queue_launch: dict[str, Any],
    manual_collect_run: dict[str, Any],
    bridge_recovery: dict[str, Any],
) -> dict[str, Any]:
    collect_handoff = (
        manual_collect_run.get("operator_handoff")
        if isinstance(manual_collect_run.get("operator_handoff"), dict)
        else {}
    )
    collect_next_step = (
        collect_handoff.get("next_mt5_step")
        if isinstance(collect_handoff.get("next_mt5_step"), dict)
        else {}
    )
    queue_next_step = (
        manual_test_queue.get("next_launch_step")
        if isinstance(manual_test_queue.get("next_launch_step"), dict)
        else {}
    )
    launch_selected_step = (
        manual_queue_launch.get("selected_item")
        if isinstance(manual_queue_launch.get("selected_item"), dict)
        else {}
    )
    next_step = collect_next_step or queue_next_step or launch_selected_step
    queue_handoff = (
        manual_test_queue.get("operator_handoff")
        if isinstance(manual_test_queue.get("operator_handoff"), dict)
        else {}
    )
    queue_handoff_state = str(queue_handoff.get("state") or "")
    queue_progress_state = str(queue_handoff.get("progress_state") or "")
    quick_input = (
        queue_handoff.get("quick_input")
        if isinstance(queue_handoff.get("quick_input"), dict)
        else {}
    )
    if not quick_input:
        quick_input = mt5_quick_input_from_step(next_step)
    next_step_operator_summary = (
        queue_handoff.get("next_step_summary")
        or queue_handoff.get("next_step_operator_summary")
        or collect_handoff.get("next_step_summary")
        or collect_handoff.get("next_step_operator_summary")
        or operator_step_summary(next_step)
    )
    next_step_collect_filter_summary = (
        queue_handoff.get("next_step_collect_filter_summary")
        or collect_handoff.get("next_step_collect_filter_summary")
        or operator_collect_filter_summary(next_step)
    )
    manual_available = bool(
        manual_strategy_tester.get("available")
        or manual_test_queue.get("exists")
        or next_step
    )
    ready_to_collect = safe_count(manual_collect_run.get("selected_count")) > 0
    waiting_for_mt5 = safe_count(manual_collect_run.get("waiting_count")) > 0 or bool(next_step)
    if ready_to_collect:
        state = "collect_ready_results"
        recommended_path = "run_manual_collect_execute"
    elif queue_handoff_state == "run_collect_dry_run_to_confirm_agent_csv":
        state = "run_collect_dry_run_to_confirm_agent_csv"
        recommended_path = "manual_collect_dry_run"
    elif waiting_for_mt5 and next_step:
        state = "run_next_mt5_strategy_tester_step"
        recommended_path = "manual_strategy_tester"
    elif waiting_for_mt5:
        state = queue_handoff_state or "waiting_for_manual_strategy_tester_results"
        recommended_path = "review_manual_queue"
    elif manual_available:
        state = "manual_strategy_tester_available"
        recommended_path = "review_manual_queue"
    else:
        state = "manual_strategy_tester_not_ready"
        recommended_path = "refresh_back_forward_and_manual_queue"
    bridge_ready = bridge_recovery.get("ready_for_mt5_validation")
    bridge_note = ""
    if bridge_ready is False:
        bridge_note = (
            "Bridge Recovery is not required for standalone Swing_Evaluation_Trader Strategy Tester; "
            "Bridge issues only affect Bridge/GPT data refresh paths."
        )
    launch_blockers = (
        manual_queue_launch.get("blocked_reasons")
        if manual_queue_launch.get("exists") is True
        and manual_queue_launch.get("selected") is True
        and isinstance(manual_queue_launch.get("blocked_reasons"), list)
        else manual_strategy_tester.get("auto_launch_blockers", [])
    )
    if not launch_blockers and isinstance(manual_strategy_tester.get("auto_launch_blockers"), list):
        launch_blockers = manual_strategy_tester.get("auto_launch_blockers", [])
    launch_status = (
        manual_queue_launch.get("status")
        if manual_queue_launch.get("exists") is True and manual_queue_launch.get("selected") is True
        else manual_strategy_tester.get("auto_launch_status", "")
    )
    launch_ready = (
        manual_queue_launch.get("ok")
        if manual_queue_launch.get("exists") is True and manual_queue_launch.get("selected") is True
        else manual_strategy_tester.get("auto_launch_ready", "")
    )
    launch_blocked_by_running_terminal = (
        "running_terminal_blocks_direct_config" in launch_blockers
        or "terminal_running" in launch_blockers
        or bool(manual_strategy_tester.get("auto_launch_blocked_by_running_terminal"))
    )
    if launch_blocked_by_running_terminal and not launch_blockers:
        launch_blockers = ["running_terminal_blocks_direct_config"]
    return {
        "state": state,
        "recommended_path": recommended_path,
        "manual_strategy_tester_available": manual_available,
        "terminal_running": manual_strategy_tester.get("terminal_running", ""),
        "auto_launch_ready": launch_ready,
        "auto_launch_status": launch_status,
        "auto_launch_blocked_by_running_terminal": launch_blocked_by_running_terminal,
        "auto_launch_blockers": launch_blockers,
        "manual_queue_status": manual_test_queue.get("status", ""),
        "manual_queue_next_action": manual_test_queue.get("next_action", ""),
        "manual_queue_progress_state": queue_progress_state,
        "manual_queue_step_report_ready_ids": manual_test_queue.get("step_report_ready_ids", []),
        "manual_queue_step_collect_ready_ids": manual_test_queue.get("step_collect_ready_ids", []),
        "manual_queue_step_waiting_report_ids": manual_test_queue.get("step_waiting_report_ids", []),
        "manual_queue_step_launch_needed_ids": manual_test_queue.get("step_launch_needed_ids", []),
        "manual_queue_collect_check_command_text": queue_handoff.get("collect_check_command_text", ""),
        "manual_collect_status": manual_collect_run.get("status", ""),
        "manual_collect_next_action": manual_collect_run.get("next_action", ""),
        "next_step_operator_summary": next_step_operator_summary,
        "next_step_summary": next_step_operator_summary,
        "next_step_collect_filter_summary": next_step_collect_filter_summary,
        "manual_collect_dry_run_command_text": collect_handoff.get("dry_run_command_text", ""),
        "manual_collect_execute_command_text": collect_handoff.get("execute_command_text", "")
        or manual_strategy_tester.get("collect_only_command_text", ""),
        "manual_collect_execute_and_refresh_analysis_command_text": collect_handoff.get(
            "execute_and_refresh_analysis_command_text", ""
        ),
        "manual_collect_execute_and_refresh_all_command_text": collect_handoff.get(
            "execute_and_refresh_all_command_text", ""
        ),
        "manual_collect_execute_and_refresh_full_analysis_command_text": (
            collect_handoff.get("execute_and_refresh_full_analysis_command_text")
            or collect_handoff.get("execute_and_refresh_all_command_text", "")
        ),
        "next_mt5_step": next_step,
        "quick_input": quick_input,
        "bridge_required_for_standalone_tester": False,
        "bridge_ready_for_mt5_validation": bridge_ready,
        "bridge_status": bridge_recovery.get("status", ""),
        "bridge_note": bridge_note,
    }


def display_next_action_for_operator_handoff(
    *,
    default_next_action: str,
    handoff: dict[str, Any],
) -> str:
    if not isinstance(handoff, dict):
        return default_next_action
    next_step = handoff.get("next_mt5_step") if isinstance(handoff.get("next_mt5_step"), dict) else {}
    queue_id = str(next_step.get("queue_id") or "")
    step_label = str(next_step.get("step_label") or "")
    queue_step = f"{queue_id}/{step_label}".strip("/")
    recommended_path = str(handoff.get("recommended_path") or "")
    state = str(handoff.get("state") or "")
    latest_run_ok_action = default_next_action == "Promotion Gate can evaluate the latest MT5 Tester evidence."
    terminal_close_action = "Close the existing MT5 terminal64.exe" in default_next_action
    if (
        (latest_run_ok_action or terminal_close_action)
        and (recommended_path == "run_manual_collect_execute" or state == "collect_ready_results")
    ):
        return "Collect ready manual Strategy Tester results, then refresh MT5 analysis."
    if latest_run_ok_action and recommended_path == "manual_strategy_tester":
        if queue_step:
            return f"Run the next MT5 manual Strategy Tester step ({queue_step}), then collect results."
        return "Run the next MT5 manual Strategy Tester step, then collect results."
    if not terminal_close_action:
        return default_next_action
    if recommended_path != "manual_strategy_tester":
        return default_next_action
    if not (queue_id or step_label):
        return default_next_action
    return (
        "Use the MT5 Operator Handoff manual Strategy Tester step"
        f" ({queue_step}); close MT5 only if you want /config auto launch."
    )


def executed_rows_from_budget(summary: dict[str, Any], budget: dict[str, Any]) -> dict[str, Any]:
    rows = budget.get("executed_tester_xml_rows")
    if isinstance(rows, dict):
        return dict(rows)
    tester_xml = summary.get("tester_xml") if isinstance(summary.get("tester_xml"), dict) else {}
    back = tester_xml.get("back") if isinstance(tester_xml.get("back"), dict) else {}
    forward = tester_xml.get("forward") if isinstance(tester_xml.get("forward"), dict) else {}
    inferred = {
        key: value
        for key, value in {
            "back": back.get("rows"),
            "forward": forward.get("rows"),
        }.items()
        if value is not None
    }
    return inferred


def numeric_pass_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def compact_number_text(value: Any) -> str:
    numeric = numeric_pass_value(value)
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
            numeric = numeric_pass_value(ratios.get(key))
            if numeric is not None:
                ratio_parts.append(f"{key}={numeric * 100:.1f}%")
        if ratio_parts:
            suffix_parts.append(f"ratio_vs_full_factorial={'/'.join(ratio_parts)}")
    source = str(rows.get("source") or "")
    if source:
        suffix_parts.append(f"source={source}")
    suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
    return f"{', '.join(row_parts)}{suffix}"


def ratio_mapping_text(ratios: Any) -> str:
    if not isinstance(ratios, dict):
        return ""
    parts = []
    for key in ("back", "forward"):
        numeric = numeric_pass_value(ratios.get(key))
        if numeric is not None:
            parts.append(f"{key}={numeric * 100:.1f}%")
    return ", ".join(parts)


def format_check_summary(row: Any) -> str:
    if not isinstance(row, dict) or not row:
        return ""
    value = row.get("value", "")
    if isinstance(value, dict | list):
        value_text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        value_text = str(value)
    return (
        f"passed={row.get('passed', '')} "
        f"value={value_text} "
        f"requirement={row.get('requirement', '')}"
    )


def read_set_text(path: Path) -> str:
    last_error: UnicodeError | None = None
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return path.read_text(encoding="utf-8")


def refresh_budget_from_current_set(budget: dict[str, Any]) -> dict[str, Any]:
    refreshed = dict(budget)
    set_file = refreshed.get("set_file")
    if not set_file:
        refreshed["set_file_reestimated"] = False
        return refreshed
    path = Path(str(set_file)).expanduser()
    if not path.exists():
        refreshed["set_file_reestimated"] = False
        refreshed["set_file_exists"] = False
        return refreshed
    try:
        estimate = estimate_set_passes(read_set_text(path))
    except (OSError, UnicodeError, ValueError) as exc:
        refreshed["set_file_reestimated"] = False
        refreshed["set_file_exists"] = True
        refreshed["set_file_reestimate_error"] = str(exc)
        return refreshed
    refreshed.update(estimate)
    refreshed["set_file_exists"] = True
    refreshed["set_file_reestimated"] = True
    return refreshed


def pass_budget_summary(
    tester_run_payload: dict[str, Any],
    optimization_report_payload: dict[str, Any],
) -> dict[str, Any]:
    run_optimization = (
        tester_run_payload.get("optimization_summary")
        if isinstance(tester_run_payload.get("optimization_summary"), dict)
        else {}
    )
    candidates = [
        ("latest_run", tester_run_payload),
        ("latest_run.optimization_summary", run_optimization),
        ("optimization_report", optimization_report_summary(optimization_report_payload)),
    ]
    for source, summary in candidates:
        if not isinstance(summary, dict):
            continue
        budget = summary.get("optimization_pass_budget")
        if not isinstance(budget, dict):
            continue
        budget = refresh_budget_from_current_set(budget)
        full_factorial = budget.get("estimated_full_factorial_passes")
        rows = executed_rows_from_budget(summary, budget)
        ratios: dict[str, float] = {}
        full_factorial_number = numeric_pass_value(full_factorial)
        numeric_rows = {
            key: value
            for key, value in ((key, numeric_pass_value(value)) for key, value in rows.items())
            if value is not None
        }
        if full_factorial_number and full_factorial_number > 0:
            for key, value in rows.items():
                numeric_value = numeric_pass_value(value)
                if numeric_value is not None:
                    ratios[key] = round(numeric_value / full_factorial_number, 4)
        max_executed = max(numeric_rows.values()) if numeric_rows else None
        progress_ratio = None
        remaining_upper_bound = None
        complete_if_exhaustive = None
        if full_factorial_number and full_factorial_number > 0 and max_executed is not None:
            progress_ratio = round(max_executed / full_factorial_number, 4)
            remaining_upper_bound = max(full_factorial_number - max_executed, 0.0)
            complete_if_exhaustive = max_executed >= full_factorial_number
        optimized_inputs = budget.get("optimized_inputs") if isinstance(budget.get("optimized_inputs"), list) else []
        return {
            "available": budget.get("available", True),
            "source": source,
            "generated_at": summary.get("generated_at"),
            "set_file": budget.get("set_file"),
            "set_file_exists": budget.get("set_file_exists"),
            "set_file_reestimated": budget.get("set_file_reestimated"),
            "set_file_reestimate_error": budget.get("set_file_reestimate_error", ""),
            "optimized_input_count": budget.get("optimized_input_count"),
            "estimated_full_factorial_passes": full_factorial,
            "executed_tester_xml_rows": rows,
            "ratio_vs_full_factorial": ratios,
            "max_executed_tester_xml_rows": int(max_executed) if max_executed is not None and max_executed.is_integer() else max_executed,
            "full_factorial_progress_ratio": progress_ratio,
            "full_factorial_remaining_upper_bound": (
                int(remaining_upper_bound)
                if remaining_upper_bound is not None and remaining_upper_bound.is_integer()
                else remaining_upper_bound
            ),
            "full_factorial_complete_if_exhaustive": complete_if_exhaustive,
            "optimized_input_names": [
                item.get("name") for item in optimized_inputs if isinstance(item, dict) and item.get("name")
            ],
            "progress_note": (
                "Full-factorial progress is an upper-bound reference; MT5 genetic optimization may execute fewer "
                "passes, and Tester XML rows are post-run evidence rather than live progress."
            ),
            "note": budget.get("note", ""),
        }
    return {"available": False}


def latest_run_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {"exists": False}
    report_paths = payload.get("report_paths") if isinstance(payload.get("report_paths"), dict) else {}
    blocked_components = (
        payload.get("blocked_components") if isinstance(payload.get("blocked_components"), dict) else {}
    )
    risk_preset = payload.get("risk_preset") if isinstance(payload.get("risk_preset"), dict) else {}
    risk_preset_inputs = risk_preset.get("inputs") if isinstance(risk_preset.get("inputs"), dict) else {}
    missing_risk_preset_inputs = [
        name for name in RISK_PRESET_REQUIRED_INPUTS if name not in risk_preset_inputs
    ]
    risk_preset_schema_required = (
        payload.get("ok") is True
        and payload.get("collect_only") is False
        and payload.get("dry_run") is False
    )
    risk_preset_schema_current = (
        isinstance(payload.get("risk_preset"), dict)
        and risk_preset.get("ok") is not False
        and not missing_risk_preset_inputs
    )
    if not risk_preset_schema_required:
        risk_preset_schema_status = "not_required"
    elif not isinstance(payload.get("risk_preset"), dict):
        risk_preset_schema_status = "missing_preset"
    elif risk_preset_schema_current:
        risk_preset_schema_status = "current"
    else:
        risk_preset_schema_status = "missing_inputs"
    compile_status = payload.get("compile_status") if isinstance(payload.get("compile_status"), dict) else {}
    terminal_run = payload.get("terminal_run") if isinstance(payload.get("terminal_run"), dict) else {}
    return {
        "exists": True,
        "generated_at": payload.get("generated_at"),
        "ok": payload.get("ok"),
        "blocked": payload.get("blocked"),
        "blocked_components": blocked_components,
        "terminal_failed": payload.get("terminal_failed"),
        "report_fallback_blocked": payload.get("report_fallback_blocked"),
        "source_time_blocked": payload.get("source_time_blocked"),
        "report_source": report_paths.get("source"),
        "agent_csv_archive_run_id": payload.get("agent_csv_archive_run_id"),
        "risk_preset_ok": risk_preset.get("ok"),
        "risk_preset_schema_required": risk_preset_schema_required,
        "risk_preset_schema_status": risk_preset_schema_status,
        "risk_preset_schema_current": risk_preset_schema_current,
        "risk_preset_schema_missing_inputs": missing_risk_preset_inputs,
        "risk_preset_inputs": risk_preset_inputs,
        "tester_set_sync_blocked": payload.get("tester_set_sync_blocked"),
        "target_tester_set_sync": (
            payload.get("target_tester_set_sync")
            if isinstance(payload.get("target_tester_set_sync"), dict)
            else {}
        ),
        "compiled_fresh": compile_status.get("all_compiled_fresh"),
        "tester_sets_synced": compile_status.get("all_tester_sets_synced"),
        "tester_configs_synced": compile_status.get("all_tester_configs_synced"),
        "terminal_started_at": terminal_run.get("started_at", ""),
        "terminal_deadline_at": terminal_run.get("deadline_at", ""),
        "terminal_elapsed_seconds": terminal_run.get("elapsed_seconds", ""),
        "terminal_returncode": terminal_run.get("returncode", ""),
        "terminal_timeout": terminal_run.get("timeout", ""),
    }


def operational_status(
    *,
    latest_run: dict[str, Any],
    compile_status: dict[str, Any],
    running_processes: list[dict[str, Any]],
) -> tuple[str, bool, str]:
    if running_processes:
        return (
            "blocked_running_terminal",
            False,
            "Close the existing MT5 terminal64.exe before launching Strategy Tester via /config.",
        )
    if compile_status and compile_status.get("all_compiled_fresh") is False:
        return (
            "blocked_compile_stale",
            False,
            "Run analysis/mt5_compile.py before launching Strategy Tester.",
        )
    if compile_status and compile_status.get("all_tester_sets_synced") is False:
        return (
            "blocked_tester_set_not_synced",
            False,
            "Sync MT5 MQL5/Profiles/Tester .set files before launching Strategy Tester.",
        )
    if compile_status and compile_status.get("all_tester_configs_synced") is False:
        return (
            "blocked_tester_config_not_synced",
            False,
            "Sync MT5 MQL5/Profiles/Tester .ini files before launching Strategy Tester.",
        )
    if not latest_run.get("exists"):
        return (
            "missing_latest_run",
            False,
            "Run analysis/mt5_tester_run.py to create the latest tester evidence.",
        )
    components = latest_run.get("blocked_components") if isinstance(latest_run.get("blocked_components"), dict) else {}
    if latest_run.get("ok") is True:
        if latest_run.get("risk_preset_schema_required") is True and latest_run.get("risk_preset_schema_current") is not True:
            return (
                "blocked_risk_preset_schema",
                False,
                "Rerun MT5 Tester with the current runner so risk_preset includes all required safety inputs.",
            )
        return ("latest_run_ok", True, "Promotion Gate can evaluate the latest MT5 Tester evidence.")
    if latest_run.get("terminal_failed") is True:
        return ("terminal_failed", False, "Check terminal stability and rerun MT5 Tester.")
    if latest_run.get("source_time_blocked") is True:
        return ("source_time_blocked", False, "Archive stale Agent CSVs and rerun for the expected Tester dates.")
    if latest_run.get("report_fallback_blocked") is True:
        return ("report_fallback_blocked", False, "Rerun with the requested Tester report name and avoid fallback XML.")
    if latest_run.get("blocked") is True:
        if components.get("compile_stale") is True:
            return ("blocked_compile_stale", False, "Run analysis/mt5_compile.py before rerunning MT5 Tester.")
        if components.get("risk_preset_invalid") is True:
            return ("blocked_risk_preset", False, "Fix the Tester .set risk preset before rerunning.")
        if components.get("tester_set_not_synced") is True:
            return (
                "blocked_tester_set_not_synced",
                False,
                "Sync the ExpertParameters .set into MT5 MQL5/Profiles/Tester before rerunning.",
            )
        if components.get("agent_csv_archive_failed") is True:
            return ("blocked_agent_csv_archive", False, "Fix Agent CSV archive path or permissions before rerunning.")
        if components.get("terminal_already_running") is True:
            return (
                "ready_to_rerun_after_terminal_closed",
                True,
                "Rerun MT5 Tester; the previous run was blocked by a terminal that is no longer detected.",
            )
        return ("blocked_runner", False, "Resolve the runner blocked_components before rerunning.")
    return ("latest_run_not_ready", False, "Review latest_mt5_tester_run.md and rerun MT5 Tester.")


def next_action_execution_readiness(
    *,
    operational_status_value: str,
    operational_ready: bool,
    compile_status: dict[str, Any],
    running_processes: list[dict[str, Any]],
    artifact_freshness: dict[str, Any],
    next_runner: dict[str, Any],
) -> dict[str, Any]:
    artifacts = (
        artifact_freshness.get("artifacts") if isinstance(artifact_freshness.get("artifacts"), dict) else {}
    )
    stale_required_artifacts = [
        name
        for name in NEXT_ACTION_EXECUTION_REQUIRED_FRESH_ARTIFACTS
        if not isinstance(artifacts.get(name), dict) or artifacts[name].get("fresh") is not True
    ]
    reasons: list[str] = []
    if running_processes:
        reasons.append("terminal_running")
    if operational_ready is not True:
        reasons.append(f"operational_not_ready:{operational_status_value}")
    if compile_status.get("all_compiled_fresh") is not True:
        reasons.append("compile_not_fresh")
    if compile_status.get("all_tester_sets_synced") is False:
        reasons.append("tester_sets_not_synced")
    if compile_status.get("all_tester_configs_synced") is False:
        reasons.append("tester_configs_not_synced")
    for name in stale_required_artifacts:
        reasons.append(f"required_artifact_stale_or_missing:{name}")
    if next_runner.get("exists") is not True:
        reasons.append("missing_next_action_run")
    if next_runner.get("ok") is not True:
        reasons.append("next_action_runner_not_ok")
    if next_runner.get("dry_run") is not True:
        reasons.append("next_action_run_not_dry_run")
    if next_runner.get("found") is not True:
        reasons.append("next_action_not_found")
    if next_runner.get("current_for_execution") is not True:
        stale_reason = str(next_runner.get("gate_stale_reason") or "")
        suffix = f":{stale_reason}" if stale_reason else ""
        reasons.append(f"next_action_runner_not_current{suffix}")
    blocking_prior_actions = (
        next_runner.get("blocking_prior_actions")
        if isinstance(next_runner.get("blocking_prior_actions"), list)
        else []
    )
    if blocking_prior_actions:
        labels = [
            f"{row.get('priority')}:{row.get('area')}:{row.get('action')}"
            for row in blocking_prior_actions
            if isinstance(row, dict)
        ]
        suffix = ",".join(labels[:3])
        reasons.append(f"higher_priority_actions_pending:{suffix}")
    primary_class = str(next_runner.get("primary_execution_class") or "")
    if primary_class != "mt5_tester_run":
        reasons.append(f"primary_execution_class_not_mt5_tester_run:{primary_class or 'missing'}")
    if next_runner.get("primary_is_mt5_tester_run") is not True:
        reasons.append("primary_not_mt5_tester_run")
    blocked_before_primary = str(next_runner.get("blocked_before_primary") or "")
    if blocked_before_primary:
        reasons.append(f"blocked_before_primary:{blocked_before_primary}")
    if next_runner.get("primary_executed") is True:
        reasons.append("primary_already_executed")

    ready = not reasons
    return {
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "reasons": reasons,
        "required_fresh_artifacts": list(NEXT_ACTION_EXECUTION_REQUIRED_FRESH_ARTIFACTS),
        "stale_required_artifacts": stale_required_artifacts,
        "operational_status": operational_status_value,
        "ready_for_tester_launch": operational_ready,
        "compile_all_tester_sets_synced": compile_status.get("all_tester_sets_synced"),
        "compile_all_tester_configs_synced": compile_status.get("all_tester_configs_synced"),
        "compile_all_compiled_fresh": compile_status.get("all_compiled_fresh"),
        "terminal_running": bool(running_processes),
        "current_for_execution": next_runner.get("current_for_execution"),
        "blocking_prior_actions": blocking_prior_actions,
        "primary_execution_class": next_runner.get("primary_execution_class", ""),
        "primary_is_mt5_tester_run": next_runner.get("primary_is_mt5_tester_run", ""),
        "primary_executed": next_runner.get("primary_executed"),
        "dry_run": next_runner.get("dry_run"),
        "runner_execute_hint": next_action_execute_hint(next_runner) if next_runner.get("exists") else "",
        "collect_only_hint": next_action_collect_only_hint(next_runner) if next_runner.get("exists") else "",
    }


def stale_required_artifact_names(
    artifact_freshness: dict[str, Any],
    required_artifacts: tuple[str, ...] | list[str],
) -> list[str]:
    artifacts = (
        artifact_freshness.get("artifacts") if isinstance(artifact_freshness.get("artifacts"), dict) else {}
    )
    return [
        name
        for name in required_artifacts
        if not isinstance(artifacts.get(name), dict) or artifacts[name].get("fresh") is not True
    ]


def optimization_report_current_with_latest_tester_run(
    *,
    tester_run_payload: dict[str, Any],
    optimization_report_payload: dict[str, Any],
) -> dict[str, Any]:
    report = optimization_report_summary(optimization_report_payload)
    tester_summary = (
        tester_run_payload.get("optimization_summary")
        if isinstance(tester_run_payload.get("optimization_summary"), dict)
        else {}
    )
    reasons: list[str] = []
    if not report:
        reasons.append("missing_optimization_report")
    if not tester_run_payload:
        reasons.append("missing_tester_run")
    if tester_run_payload.get("ok") is not True:
        reasons.append("tester_run_not_ok")
    if tester_run_payload.get("blocked") is True:
        reasons.append("tester_run_blocked")
    if tester_run_payload.get("source_time_blocked") is True:
        reasons.append("tester_run_source_time_blocked")
    if tester_run_payload.get("report_fallback_blocked") is True:
        reasons.append("tester_run_report_fallback_blocked")
    if not tester_summary:
        reasons.append("missing_tester_run_optimization_summary")

    report_overall = report.get("overall") if isinstance(report.get("overall"), dict) else {}
    tester_overall = tester_summary.get("overall") if isinstance(tester_summary.get("overall"), dict) else {}
    for key in ("generated_at",):
        if comparable_text(report.get(key)) != comparable_text(tester_summary.get(key)):
            reasons.append(f"optimization_report_{key}_mismatch")
    for key in ("closed", "pf", "avg_price_r", "net_profit"):
        if comparable_text(report_overall.get(key)) != comparable_text(tester_overall.get(key)):
            reasons.append(f"optimization_report_overall_{key}_mismatch")

    report_source_time = (
        report.get("source_time_diagnostics") if isinstance(report.get("source_time_diagnostics"), dict) else {}
    )
    tester_source_time = (
        tester_summary.get("source_time_diagnostics")
        if isinstance(tester_summary.get("source_time_diagnostics"), dict)
        else {}
    )
    if comparable_text(report_source_time.get("matches_expected_range")) != comparable_text(
        tester_source_time.get("matches_expected_range")
    ):
        reasons.append("optimization_report_source_time_match_mismatch")
    if report_source_time.get("matches_expected_range") is not True:
        reasons.append("optimization_report_source_time_not_matching_expected_range")

    current = not reasons
    return {
        "current": current,
        "status": "current_with_latest_tester_run" if current else "not_current",
        "reasons": reasons,
        "report_generated_at": report.get("generated_at", ""),
        "tester_generated_at": tester_run_payload.get("generated_at", ""),
        "tester_optimization_generated_at": tester_summary.get("generated_at", ""),
        "report_closed": report_overall.get("closed", ""),
        "tester_optimization_closed": tester_overall.get("closed", ""),
        "report_pf": report_overall.get("pf", ""),
        "tester_optimization_pf": tester_overall.get("pf", ""),
        "source_time_matches_expected_range": report_source_time.get("matches_expected_range", ""),
    }


def local_next_action_execute_hint(next_runner: dict[str, Any]) -> str:
    return next_action_runner_command_hint(next_runner.get("target"), allow_non_tester_primary=True)


def next_action_execute_hint(next_runner: dict[str, Any]) -> str:
    return str(next_runner.get("execute_command_text") or next_action_runner_command_hint(next_runner.get("target")))


def next_action_collect_only_hint(next_runner: dict[str, Any]) -> str:
    return str(next_runner.get("collect_only_command_text") or "")


def next_action_local_execution_readiness(
    *,
    artifact_freshness: dict[str, Any],
    next_runner: dict[str, Any],
    tester_run_payload: dict[str, Any],
    optimization_report_payload: dict[str, Any],
) -> dict[str, Any]:
    primary_class = str(next_runner.get("primary_execution_class") or "")
    required_artifacts = list(LOCAL_NEXT_ACTION_REQUIRED_FRESH_ARTIFACTS.get(primary_class, ()))
    stale_required_artifacts = stale_required_artifact_names(artifact_freshness, required_artifacts)
    optimization_report_evidence = optimization_report_current_with_latest_tester_run(
        tester_run_payload=tester_run_payload,
        optimization_report_payload=optimization_report_payload,
    )
    if (
        primary_class == "mt5_optimization_recommendation_refresh"
        and "optimization_report" in stale_required_artifacts
        and optimization_report_evidence.get("current") is True
    ):
        stale_required_artifacts = [name for name in stale_required_artifacts if name != "optimization_report"]
    reasons: list[str] = []

    if next_runner.get("exists") is not True:
        reasons.append("missing_next_action_run")
    if next_runner.get("ok") is not True:
        reasons.append("next_action_runner_not_ok")
    if next_runner.get("dry_run") is not True:
        reasons.append("next_action_run_not_dry_run")
    if next_runner.get("found") is not True:
        reasons.append("next_action_not_found")
    if next_runner.get("current_for_execution") is not True:
        stale_reason = str(next_runner.get("gate_stale_reason") or "")
        suffix = f":{stale_reason}" if stale_reason else ""
        reasons.append(f"next_action_runner_not_current{suffix}")
    for name in stale_required_artifacts:
        reasons.append(f"required_artifact_stale_or_missing:{name}")

    blocking_prior_actions = (
        next_runner.get("blocking_prior_actions")
        if isinstance(next_runner.get("blocking_prior_actions"), list)
        else []
    )
    if blocking_prior_actions:
        labels = [
            f"{row.get('priority')}:{row.get('area')}:{row.get('action')}"
            for row in blocking_prior_actions
            if isinstance(row, dict)
        ]
        suffix = ",".join(labels[:3])
        reasons.append(f"higher_priority_actions_pending:{suffix}")

    if primary_class not in LOCAL_NEXT_ACTION_PRIMARY_CLASSES:
        reasons.append(f"primary_execution_class_not_local:{primary_class or 'missing'}")
        if next_runner.get("primary_is_mt5_tester_run") is True:
            reasons.append("primary_is_mt5_tester_run")
        status = "not_applicable" if next_runner.get("exists") is True else "blocked"
        return {
            "ready": False,
            "status": status,
            "reasons": reasons,
            "required_fresh_artifacts": required_artifacts,
            "stale_required_artifacts": stale_required_artifacts,
            "primary_execution_class": primary_class,
            "primary_is_mt5_tester_run": next_runner.get("primary_is_mt5_tester_run", ""),
            "current_for_execution": next_runner.get("current_for_execution"),
            "primary_executed": next_runner.get("primary_executed"),
            "requires_allow_non_tester_primary": False,
            "runner_execute_hint": "",
            "primary_command": next_runner.get("command_text", ""),
            "optimization_report_evidence": optimization_report_evidence,
        }

    if next_runner.get("primary_is_mt5_tester_run") is True:
        reasons.append("primary_is_mt5_tester_run")
    blocked_before_primary = str(next_runner.get("blocked_before_primary") or "")
    if blocked_before_primary:
        reasons.append(f"blocked_before_primary:{blocked_before_primary}")
    if next_runner.get("primary_executed") is True:
        reasons.append("primary_already_executed")

    ready = not reasons
    return {
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "reasons": reasons,
        "required_fresh_artifacts": required_artifacts,
        "stale_required_artifacts": stale_required_artifacts,
        "primary_execution_class": primary_class,
        "primary_is_mt5_tester_run": next_runner.get("primary_is_mt5_tester_run", ""),
        "current_for_execution": next_runner.get("current_for_execution"),
        "primary_executed": next_runner.get("primary_executed"),
        "requires_allow_non_tester_primary": True,
        "runner_execute_hint": local_next_action_execute_hint(next_runner),
        "primary_command": next_runner.get("command_text", ""),
        "optimization_report_evidence": optimization_report_evidence,
    }


def mt5_tester_status(
    *,
    tester_run_path: str | Path = "runtime/latest_mt5_tester_run.json",
    promotion_gate_path: str | Path | None = "runtime/latest_promotion_gate.json",
    compile_status_path: str | Path | None = "runtime/latest_mt5_compile_status.json",
    optimization_report_path: str | Path | None = None,
    next_action_run_path: str | Path | None = DEFAULT_NEXT_ACTION_RUN,
    back_forward_run_path: str | Path | None = DEFAULT_BACK_FORWARD_RUN,
    manual_test_queue_path: str | Path | None = DEFAULT_MANUAL_TEST_QUEUE,
    manual_queue_launch_path: str | Path | None = DEFAULT_MANUAL_QUEUE_LAUNCH,
    manual_collect_run_path: str | Path | None = DEFAULT_MANUAL_COLLECT_RUN,
    manual_test_queue_with_optimization_path: str | Path | None = DEFAULT_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION,
    manual_queue_launch_with_optimization_path: str | Path | None = DEFAULT_MANUAL_QUEUE_LAUNCH_WITH_OPTIMIZATION,
    manual_collect_with_optimization_path: str | Path | None = DEFAULT_MANUAL_COLLECT_WITH_OPTIMIZATION,
    manual_operator_packet_with_optimization_path: str | Path | None = DEFAULT_MANUAL_OPERATOR_PACKET_WITH_OPTIMIZATION,
    manual_auto_collect_watch_path: str | Path | None = DEFAULT_MANUAL_AUTO_COLLECT_WATCH,
    stable_candidate_report_path: str | Path | None = DEFAULT_STABLE_CANDIDATE_REPORT,
    stable_candidate_recommendation_path: str | Path | None = DEFAULT_STABLE_CANDIDATE_RECOMMENDATION,
    stable_candidate_tester_run_path: str | Path | None = DEFAULT_STABLE_CANDIDATE_TESTER_RUN,
    bridge_recovery_plan_path: str | Path | None = DEFAULT_BRIDGE_RECOVERY_PLAN,
    status_watch_heartbeat_path: str | Path | None = DEFAULT_STATUS_WATCH_HEARTBEAT,
    status_watch_heartbeat_max_age_seconds: int = DEFAULT_STATUS_WATCH_HEARTBEAT_MAX_AGE_SECONDS,
    detect_running_terminal: bool = True,
    max_artifact_age_seconds: int = DEFAULT_MAX_ARTIFACT_AGE_SECONDS,
) -> dict[str, Any]:
    effective_status_watch_path = effective_status_watch_heartbeat_path(status_watch_heartbeat_path)
    tester_run_payload = load_optional_json(tester_run_path)
    gate_payload = load_optional_json(promotion_gate_path)
    compile_payload = compile_summary(load_optional_json(compile_status_path))
    optimization_report_payload = optimization_report_summary(load_optional_json(optimization_report_path))
    next_action_run_payload = load_optional_json(next_action_run_path)
    back_forward_run_payload = load_optional_json(back_forward_run_path)
    manual_test_queue_payload = load_optional_json(manual_test_queue_path)
    manual_queue_launch_payload = load_optional_json(manual_queue_launch_path)
    manual_collect_run_payload = load_optional_json(manual_collect_run_path)
    manual_test_queue_with_optimization_payload = load_optional_json(manual_test_queue_with_optimization_path)
    manual_queue_launch_with_optimization_payload = load_optional_json(manual_queue_launch_with_optimization_path)
    manual_collect_with_optimization_payload = load_optional_json(manual_collect_with_optimization_path)
    manual_operator_packet_with_optimization_payload = load_optional_json(
        manual_operator_packet_with_optimization_path
    )
    manual_auto_collect_watch_payload = load_optional_json(manual_auto_collect_watch_path)
    stable_report_payload = load_optional_json(stable_candidate_report_path)
    stable_recommendation_payload = load_optional_json(stable_candidate_recommendation_path)
    stable_tester_run_payload = load_optional_json(stable_candidate_tester_run_path)
    bridge_recovery_payload = load_optional_json(bridge_recovery_plan_path)
    running_processes = discover_running_terminal_processes() if detect_running_terminal else []
    latest_run = latest_run_summary(tester_run_payload)
    status, ready, next_action = operational_status(
        latest_run=latest_run,
        compile_status=compile_payload,
        running_processes=running_processes,
    )
    artifact_freshness = artifact_freshness_summary(
        tester_run_path=tester_run_path,
        promotion_gate_path=promotion_gate_path,
        compile_status_path=compile_status_path,
        optimization_report_path=optimization_report_path,
        next_action_run_path=next_action_run_path,
        back_forward_run_path=back_forward_run_path,
        manual_test_queue_path=manual_test_queue_path,
        manual_queue_launch_path=manual_queue_launch_path,
        manual_collect_run_path=manual_collect_run_path,
        manual_test_queue_with_optimization_path=manual_test_queue_with_optimization_path,
        manual_queue_launch_with_optimization_path=manual_queue_launch_with_optimization_path,
        manual_collect_with_optimization_path=manual_collect_with_optimization_path,
        manual_operator_packet_with_optimization_path=manual_operator_packet_with_optimization_path,
        manual_auto_collect_watch_path=manual_auto_collect_watch_path,
        stable_candidate_report_path=stable_candidate_report_path,
        stable_candidate_recommendation_path=stable_candidate_recommendation_path,
        stable_candidate_tester_run_path=stable_candidate_tester_run_path,
        bridge_recovery_plan_path=bridge_recovery_plan_path,
        max_age_seconds=max_artifact_age_seconds,
    )
    next_action_runner = next_action_run_summary(next_action_run_payload, gate_payload)
    back_forward_runner = back_forward_run_summary(back_forward_run_payload)
    manual_test_queue = manual_test_queue_summary(
        manual_test_queue_payload,
        path=manual_test_queue_path,
    )
    manual_test_queue_with_optimization = manual_test_queue_summary(
        manual_test_queue_with_optimization_payload,
        path=manual_test_queue_with_optimization_path,
    )
    apply_manual_queue_collect_command_overrides(
        back_forward_runner=back_forward_runner,
        next_action_runner=next_action_runner,
        manual_queues=(manual_test_queue, manual_test_queue_with_optimization),
        back_forward_run_path=back_forward_run_path,
        next_action_run_path=next_action_run_path,
    )
    next_action_execution = next_action_execution_readiness(
        operational_status_value=status,
        operational_ready=ready,
        compile_status=compile_payload,
        running_processes=running_processes,
        artifact_freshness=artifact_freshness,
        next_runner=next_action_runner,
    )
    next_action_local_execution = next_action_local_execution_readiness(
        artifact_freshness=artifact_freshness,
        next_runner=next_action_runner,
        tester_run_payload=tester_run_payload,
        optimization_report_payload=optimization_report_payload,
    )
    back_forward_execution = back_forward_execution_readiness(
        compile_status=compile_payload,
        running_processes=running_processes,
        artifact_freshness=artifact_freshness,
        back_forward_runner=back_forward_runner,
    )
    manual_queue_launch = manual_queue_launch_summary(
        manual_queue_launch_payload,
        path=manual_queue_launch_path,
    )
    manual_strategy_tester = manual_strategy_tester_readiness(
        back_forward_runner=back_forward_runner,
        back_forward_execution=back_forward_execution,
        running_processes=running_processes,
        manual_queue_launch=manual_queue_launch,
    )
    manual_collect_run = manual_collect_run_summary(
        manual_collect_run_payload,
        path=manual_collect_run_path,
    )
    manual_queue_launch_with_optimization = manual_queue_launch_summary(
        manual_queue_launch_with_optimization_payload,
        path=manual_queue_launch_with_optimization_path,
    )
    manual_collect_with_optimization = manual_collect_run_summary(
        manual_collect_with_optimization_payload,
        path=manual_collect_with_optimization_path,
    )
    manual_operator_packet_with_optimization = manual_operator_packet_summary(
        manual_operator_packet_with_optimization_payload,
        path=manual_operator_packet_with_optimization_path,
    )
    manual_auto_collect_watch = manual_auto_collect_watch_summary(
        manual_auto_collect_watch_payload,
        path=manual_auto_collect_watch_path,
    )
    bridge_recovery = bridge_recovery_plan_summary(
        bridge_recovery_payload,
        path=bridge_recovery_plan_path,
    )
    mt5_operator_handoff = mt5_operator_handoff_summary(
        manual_strategy_tester=manual_strategy_tester,
        manual_test_queue=manual_test_queue,
        manual_queue_launch=manual_queue_launch,
        manual_collect_run=manual_collect_run,
        bridge_recovery=bridge_recovery,
    )
    display_next_action = display_next_action_for_operator_handoff(
        default_next_action=next_action,
        handoff=mt5_operator_handoff,
    )
    status_watch_heartbeat = status_watch_heartbeat_summary(
        effective_status_watch_path,
        max_age_seconds=status_watch_heartbeat_max_age_seconds,
    )
    status_payload = {
        "ok": ready,
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "operational_status": status,
        "ready_for_tester_launch": ready,
        "next_action": display_next_action,
        "paths": {
            "tester_run": str(tester_run_path),
            "promotion_gate": str(promotion_gate_path) if promotion_gate_path else "",
            "compile_status": str(compile_status_path) if compile_status_path else "",
            "optimization_report": str(optimization_report_path) if optimization_report_path else "",
            "next_action_run": str(next_action_run_path) if next_action_run_path else "",
            "back_forward_run": str(back_forward_run_path) if back_forward_run_path else "",
            "manual_test_queue": str(manual_test_queue_path) if manual_test_queue_path else "",
            "manual_queue_launch": str(manual_queue_launch_path) if manual_queue_launch_path else "",
            "manual_collect_run": str(manual_collect_run_path) if manual_collect_run_path else "",
            "manual_test_queue_with_optimization": (
                str(manual_test_queue_with_optimization_path)
                if manual_test_queue_with_optimization_path
                else ""
            ),
            "manual_queue_launch_with_optimization": (
                str(manual_queue_launch_with_optimization_path)
                if manual_queue_launch_with_optimization_path
                else ""
            ),
            "manual_collect_with_optimization": (
                str(manual_collect_with_optimization_path)
                if manual_collect_with_optimization_path
                else ""
            ),
            "manual_operator_packet_with_optimization": (
                str(manual_operator_packet_with_optimization_path)
                if manual_operator_packet_with_optimization_path
                else ""
            ),
            "manual_auto_collect_watch": (
                str(manual_auto_collect_watch_path) if manual_auto_collect_watch_path else ""
            ),
            "stable_candidate_report": str(stable_candidate_report_path) if stable_candidate_report_path else "",
            "stable_candidate_recommendation": (
                str(stable_candidate_recommendation_path) if stable_candidate_recommendation_path else ""
            ),
            "stable_candidate_tester_run": (
                str(stable_candidate_tester_run_path) if stable_candidate_tester_run_path else ""
            ),
            "bridge_recovery_plan": str(bridge_recovery_plan_path) if bridge_recovery_plan_path else "",
            "status_watch_heartbeat": str(effective_status_watch_path) if effective_status_watch_path else "",
        },
        "current_terminal": {
            "detection_enabled": detect_running_terminal,
            "running": bool(running_processes),
            "count": len(running_processes),
            "processes": running_processes,
        },
        "artifact_freshness": artifact_freshness,
        "latest_run": latest_run,
        "pass_budget": pass_budget_summary(tester_run_payload, optimization_report_payload),
        "next_action_runner": next_action_runner,
        "next_action_execution": next_action_execution,
        "next_action_local_execution": next_action_local_execution,
        "back_forward_runner": back_forward_runner,
        "back_forward_execution": back_forward_execution,
        "manual_strategy_tester": manual_strategy_tester,
        "manual_test_queue": manual_test_queue,
        "manual_queue_launch": manual_queue_launch,
        "manual_collect_run": manual_collect_run,
        "manual_test_queue_with_optimization": manual_test_queue_with_optimization,
        "manual_queue_launch_with_optimization": manual_queue_launch_with_optimization,
        "manual_collect_with_optimization": manual_collect_with_optimization,
        "manual_operator_packet_with_optimization": manual_operator_packet_with_optimization,
        "manual_auto_collect_watch": manual_auto_collect_watch,
        "mt5_operator_handoff": mt5_operator_handoff,
        "bridge_recovery_plan": bridge_recovery,
        "status_watch_heartbeat": status_watch_heartbeat,
        "stable_candidate": stable_candidate_summary(
            stable_report_payload,
            stable_recommendation_payload,
            stable_tester_run_payload,
        ),
        "compile_status": {
            "generated_at": compile_payload.get("generated_at"),
            "all_sources_synced": compile_payload.get("all_sources_synced"),
            "all_compiled_fresh": compile_payload.get("all_compiled_fresh"),
            "all_tester_sets_synced": compile_payload.get("all_tester_sets_synced"),
            "all_tester_configs_synced": compile_payload.get("all_tester_configs_synced"),
            "all_required_tester_config_references_ready": compile_payload.get(
                "all_required_tester_config_references_ready"
            ),
            "unsynced_tester_sets": [
                {
                    "name": row.get("name"),
                    "status": row.get("status"),
                    "synced": row.get("synced"),
                }
                for row in (
                    compile_payload.get("tester_sets")
                    if isinstance(compile_payload.get("tester_sets"), list)
                    else []
                )
                if isinstance(row, dict) and row.get("synced") is not True
            ],
            "unsynced_tester_configs": [
                {
                    "name": row.get("name"),
                    "status": row.get("status"),
                    "synced": row.get("synced"),
                }
                for row in (
                    compile_payload.get("tester_configs")
                    if isinstance(compile_payload.get("tester_configs"), list)
                    else []
                )
                if isinstance(row, dict) and row.get("synced") is not True
            ],
            "tester_config_reference_issues": [
                {
                    "name": row.get("name"),
                    "expert_parameters": row.get("expert_parameters"),
                    "status": row.get("status"),
                    "ready": row.get("ready"),
                    "generated_set_missing": row.get("generated_set_missing"),
                }
                for row in (
                    compile_payload.get("tester_config_references")
                    if isinstance(compile_payload.get("tester_config_references"), list)
                    else []
                )
                if isinstance(row, dict) and row.get("ready") is not True
            ],
        },
        "promotion_gate": promotion_gate_summary(gate_payload),
    }
    status_payload["operator_summary"] = mt5_tester_status_operator_summary(status_payload)
    status_payload.update(mt5_tester_status_top_level_back_forward_aliases(status_payload))
    status_payload.update(mt5_tester_status_top_level_operator_aliases(status_payload["operator_summary"]))
    return status_payload


def first_present(*values: Any) -> Any:
    for value in values:
        if value not in ("", None, [], {}):
            return value
    return ""


def queue_step_from_mt5_step(step: object) -> str:
    if not isinstance(step, dict) or not step:
        return ""
    queue_id = str(step.get("queue_id") or "")
    step_label = str(step.get("step_label") or "")
    return f"{queue_id}/{step_label}".strip("/")


def mt5_tester_status_top_level_back_forward_aliases(status: dict[str, Any]) -> dict[str, Any]:
    """Expose manual Back/Forward readiness checks without nested JSON traversal."""
    runner = (
        status.get("back_forward_runner")
        if isinstance(status.get("back_forward_runner"), dict)
        else {}
    )
    manual_strategy = (
        status.get("manual_strategy_tester")
        if isinstance(status.get("manual_strategy_tester"), dict)
        else {}
    )
    prerequisites_ready = first_present(
        runner.get("manual_prerequisites_ready"),
        manual_strategy.get("manual_prerequisites_ready"),
    )
    prerequisites_reasons = runner.get("manual_prerequisites_reasons")
    if prerequisites_reasons in ("", None):
        prerequisites_reasons = manual_strategy.get("manual_prerequisites_reasons", [])
    prerequisites_path = first_present(
        runner.get("manual_prerequisites_compile_status_path"),
        manual_strategy.get("manual_prerequisites_compile_status_path"),
    )
    prerequisites_generated_at = first_present(
        runner.get("manual_prerequisites_generated_at"),
        manual_strategy.get("manual_prerequisites_generated_at"),
    )
    validation_ready = first_present(
        runner.get("back_forward_plan_validation_ready"),
        manual_strategy.get("back_forward_plan_validation_ready"),
    )
    validation_status = first_present(
        runner.get("back_forward_plan_validation_status"),
        manual_strategy.get("back_forward_plan_validation_status"),
    )
    validation_reasons = runner.get("back_forward_plan_validation_reasons")
    if validation_reasons in ("", None):
        validation_reasons = manual_strategy.get("back_forward_plan_validation_reasons", [])
    return {
        "manual_prerequisites_ready": prerequisites_ready,
        "manual_prerequisites_reasons": prerequisites_reasons,
        "manual_prerequisites_compile_status_path": prerequisites_path,
        "manual_prerequisites_generated_at": prerequisites_generated_at,
        "back_forward_plan_validation_ready": validation_ready,
        "back_forward_plan_validation_status": validation_status,
        "back_forward_plan_validation_reasons": validation_reasons,
        "back_forward_run_manual_prerequisites_ready": prerequisites_ready,
        "back_forward_run_manual_prerequisites_reasons": prerequisites_reasons,
        "back_forward_run_manual_prerequisites_compile_status_path": prerequisites_path,
        "back_forward_run_manual_prerequisites_generated_at": prerequisites_generated_at,
        "back_forward_run_plan_validation_ready": validation_ready,
        "back_forward_run_plan_validation_status": validation_status,
        "back_forward_run_plan_validation_reasons": validation_reasons,
    }


def mt5_tester_status_top_level_operator_aliases(
    operator_summary: dict[str, Any],
) -> dict[str, Any]:
    """Expose the next MT5 operation without requiring nested summary parsing."""
    aliases = {
        "mt5_next_operator_action": operator_summary.get(
            "manual_operator_packet_with_optimization_next_operator_action", ""
        ),
        "mt5_next_operator_mode": operator_summary.get(
            "manual_operator_packet_with_optimization_next_operator_mode", ""
        ),
        "mt5_next_operator_launch_state": operator_summary.get(
            "manual_operator_packet_with_optimization_next_operator_launch_state", ""
        ),
        "mt5_next_queue_step": first_present(
            operator_summary.get("manual_operator_packet_with_optimization_next_queue_step"),
            operator_summary.get("manual_test_queue_quick_input", {}).get("queue_step")
            if isinstance(operator_summary.get("manual_test_queue_quick_input"), dict)
            else "",
        ),
        "mt5_next_quick_input": first_present(
            operator_summary.get(
                "manual_operator_packet_with_optimization_next_operator_quick_input"
            ),
            operator_summary.get("manual_operator_packet_with_optimization_next_step_quick_input"),
            operator_summary.get("mt5_operator_handoff_quick_input"),
            operator_summary.get("manual_test_queue_quick_input"),
        ),
        "mt5_next_step_operator_summary": first_present(
            operator_summary.get("manual_operator_packet_with_optimization_next_step_operator_summary"),
            operator_summary.get("manual_operator_packet_with_optimization_next_step_summary"),
            operator_summary.get("mt5_operator_handoff_next_step_summary"),
            operator_summary.get("mt5_operator_handoff_next_step_operator_summary"),
            operator_summary.get(
                "manual_queue_launch_with_optimization_queue_operator_handoff_next_step_summary"
            ),
            operator_summary.get(
                "manual_queue_launch_with_optimization_queue_operator_handoff_next_step_operator_summary"
            ),
            operator_summary.get("manual_test_queue_next_step_summary"),
            operator_summary.get("manual_test_queue_next_step_operator_summary"),
        ),
        "mt5_next_step_summary": first_present(
            operator_summary.get("manual_operator_packet_with_optimization_next_step_summary"),
            operator_summary.get("manual_operator_packet_with_optimization_next_step_operator_summary"),
            operator_summary.get("mt5_operator_handoff_next_step_summary"),
            operator_summary.get("mt5_operator_handoff_next_step_operator_summary"),
            operator_summary.get(
                "manual_queue_launch_with_optimization_queue_operator_handoff_next_step_summary"
            ),
            operator_summary.get(
                "manual_queue_launch_with_optimization_queue_operator_handoff_next_step_operator_summary"
            ),
            operator_summary.get("manual_test_queue_next_step_summary"),
            operator_summary.get("manual_test_queue_next_step_operator_summary"),
        ),
        "mt5_next_step_collect_filter_summary": first_present(
            operator_summary.get(
                "manual_operator_packet_with_optimization_next_step_collect_filter_summary"
            ),
            operator_summary.get("mt5_operator_handoff_next_step_collect_filter_summary"),
            operator_summary.get("manual_test_queue_next_step_collect_filter_summary"),
        ),
        "mt5_next_manual_run_start_effective_after": first_present(
            operator_summary.get(
                "manual_operator_packet_with_optimization_manual_run_start_effective_after"
            ),
            operator_summary.get("manual_strategy_tester_manual_run_start_after"),
        ),
        "mt5_next_manual_run_start_effective_after_values": operator_summary.get(
            "manual_operator_packet_with_optimization_manual_run_start_effective_after_values",
            [],
        ),
        "mt5_auto_launch_command_available": operator_summary.get(
            "manual_operator_packet_with_optimization_auto_launch_command_available", ""
        ),
        "mt5_auto_launch_blocked": operator_summary.get(
            "manual_operator_packet_with_optimization_auto_launch_blocked", ""
        ),
        "mt5_auto_launch_blocked_reasons": operator_summary.get(
            "manual_operator_packet_with_optimization_auto_launch_blocked_reasons", []
        ),
        "mt5_auto_launch_command_text": operator_summary.get(
            "manual_operator_packet_with_optimization_auto_launch_command_text", ""
        ),
        "mt5_auto_launch_note": operator_summary.get(
            "manual_operator_packet_with_optimization_auto_launch_note", ""
        ),
        "mt5_back_forward_quick_start_status": operator_summary.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_status", ""
        ),
        "mt5_back_forward_quick_start_quick_inputs": operator_summary.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_quick_inputs",
            [],
        ),
        "mt5_back_forward_quick_start_current_quick_input": operator_summary.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_current_quick_input",
            {},
        ),
        "mt5_back_forward_quick_start_collect_command_text": operator_summary.get(
            "manual_operator_packet_with_optimization_back_forward_quick_start_collect_command_text",
            "",
        ),
        "mt5_back_forward_completion_summary": operator_summary.get(
            "manual_operator_packet_with_optimization_back_forward_completion_summary",
            "",
        ),
        "mt5_back_forward_completion_manual_run_start_after": operator_summary.get(
            "manual_operator_packet_with_optimization_back_forward_completion_manual_run_start_after",
            "",
        ),
        "mt5_back_forward_completion_expected_step_count": operator_summary.get(
            "manual_operator_packet_with_optimization_back_forward_completion_expected_step_count",
            "",
        ),
        "mt5_back_forward_completion_waiting_step_count": operator_summary.get(
            "manual_operator_packet_with_optimization_back_forward_completion_waiting_step_count",
            "",
        ),
        "mt5_back_forward_completion_collect_command_text": operator_summary.get(
            "manual_operator_packet_with_optimization_back_forward_completion_collect_command_text",
            "",
        ),
        "mt5_back_forward_completion_steps": operator_summary.get(
            "manual_operator_packet_with_optimization_back_forward_completion_steps",
            [],
        ),
        "mt5_back_forward_completion_decision_thresholds": operator_summary.get(
            "manual_operator_packet_with_optimization_back_forward_completion_decision_thresholds",
            {},
        ),
        "mt5_strategy_operator_decision_status": operator_summary.get(
            "manual_operator_packet_with_optimization_strategy_operator_decision_status", ""
        ),
        "mt5_strategy_operator_decision_verdict": operator_summary.get(
            "manual_operator_packet_with_optimization_strategy_operator_decision_verdict", ""
        ),
        "mt5_strategy_operator_decision_primary_blocker": operator_summary.get(
            "manual_operator_packet_with_optimization_strategy_operator_decision_primary_blocker",
            "",
        ),
        "mt5_strategy_operator_decision_next_action": operator_summary.get(
            "manual_operator_packet_with_optimization_strategy_operator_decision_next_action", ""
        ),
        "mt5_strategy_operator_decision_command_text": operator_summary.get(
            "manual_operator_packet_with_optimization_strategy_operator_decision_command_text", ""
        ),
        "mt5_collect_dry_run_command_text": first_present(
            operator_summary.get("manual_auto_collect_watch_collect_dry_run_command_text"),
            operator_summary.get(
                "manual_queue_launch_queue_operator_handoff_collect_dry_run_command_text"
            ),
            operator_summary.get("manual_test_queue_collect_check_command_text"),
        ),
        "mt5_collect_execute_command_text": first_present(
            operator_summary.get("manual_auto_collect_watch_collect_execute_command_text"),
            operator_summary.get(
                "manual_queue_launch_queue_operator_handoff_collect_execute_command_text"
            ),
        ),
        "mt5_collect_execute_and_refresh_analysis_command_text": first_present(
            operator_summary.get(
                "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_analysis_command_text"
            ),
            operator_summary.get(
                "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_analysis_command_text"
            ),
            operator_summary.get(
                "manual_collect_with_optimization_handoff_execute_and_refresh_analysis_command_text"
            ),
            operator_summary.get(
                "manual_collect_run_handoff_execute_and_refresh_analysis_command_text"
            ),
        ),
        "mt5_collect_execute_and_refresh_all_command_text": first_present(
            operator_summary.get(
                "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text"
            ),
            operator_summary.get(
                "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_all_command_text"
            ),
            operator_summary.get(
                "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text"
            ),
            operator_summary.get(
                "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_all_command_text"
            ),
            operator_summary.get(
                "manual_collect_with_optimization_handoff_execute_and_refresh_full_analysis_command_text"
            ),
            operator_summary.get(
                "manual_collect_with_optimization_handoff_execute_and_refresh_all_command_text"
            ),
            operator_summary.get(
                "manual_collect_run_handoff_execute_and_refresh_full_analysis_command_text"
            ),
            operator_summary.get("manual_collect_run_handoff_execute_and_refresh_all_command_text"),
            operator_summary.get(
                "manual_operator_packet_with_optimization_back_forward_quick_start_full_queue_collect_command_text"
            ),
        ),
        "mt5_collect_execute_and_refresh_full_analysis_command_text": first_present(
            operator_summary.get(
                "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text"
            ),
            operator_summary.get(
                "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_all_command_text"
            ),
            operator_summary.get(
                "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text"
            ),
            operator_summary.get(
                "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_all_command_text"
            ),
            operator_summary.get(
                "manual_collect_with_optimization_handoff_execute_and_refresh_full_analysis_command_text"
            ),
            operator_summary.get(
                "manual_collect_with_optimization_handoff_execute_and_refresh_all_command_text"
            ),
            operator_summary.get(
                "manual_collect_run_handoff_execute_and_refresh_full_analysis_command_text"
            ),
            operator_summary.get("manual_collect_run_handoff_execute_and_refresh_all_command_text"),
            operator_summary.get(
                "manual_operator_packet_with_optimization_back_forward_quick_start_full_queue_collect_command_text"
            ),
            operator_summary.get(
                "manual_operator_packet_with_optimization_next_operator_follow_up_command_text"
            ),
        ),
        "mt5_manual_queue_status": first_present(
            operator_summary.get("manual_test_queue_with_optimization_status"),
            operator_summary.get("manual_test_queue_status"),
        ),
        "mt5_manual_queue_progress_state": first_present(
            operator_summary.get("manual_test_queue_with_optimization_progress_state"),
            operator_summary.get("manual_test_queue_progress_state"),
        ),
        "mt5_manual_queue_waiting_count": first_present(
            operator_summary.get("manual_test_queue_with_optimization_waiting_count"),
            operator_summary.get("manual_test_queue_waiting_count"),
        ),
        "mt5_manual_queue_step_launch_needed_count": first_present(
            operator_summary.get("manual_test_queue_with_optimization_step_launch_needed_count"),
            operator_summary.get("manual_test_queue_step_launch_needed_count"),
        ),
        "manual_test_queue_next_queue_step": operator_summary.get(
            "manual_test_queue_next_queue_step", ""
        ),
        "manual_test_queue_quick_input": operator_summary.get(
            "manual_test_queue_quick_input", {}
        ),
        "manual_test_queue_next_quick_input": operator_summary.get(
            "manual_test_queue_next_quick_input", {}
        ),
        "manual_test_queue_with_optimization_next_queue_step": operator_summary.get(
            "manual_test_queue_with_optimization_next_queue_step", ""
        ),
        "manual_test_queue_with_optimization_quick_input": operator_summary.get(
            "manual_test_queue_with_optimization_quick_input", {}
        ),
        "manual_test_queue_with_optimization_next_quick_input": operator_summary.get(
            "manual_test_queue_with_optimization_next_quick_input", {}
        ),
        "manual_operator_packet_with_optimization_next_operator_quick_input": (
            operator_summary.get(
                "manual_operator_packet_with_optimization_next_operator_quick_input",
                {},
            )
        ),
    }
    handoff_defaults = {
        "mt5_operator_handoff_state": "",
        "mt5_operator_handoff_recommended_path": "",
        "mt5_operator_handoff_manual_strategy_tester_available": "",
        "mt5_operator_handoff_terminal_running": "",
        "mt5_operator_handoff_auto_launch_ready": "",
        "mt5_operator_handoff_auto_launch_status": "",
        "mt5_operator_handoff_auto_launch_blocked_by_running_terminal": "",
        "mt5_operator_handoff_auto_launch_blockers": [],
        "mt5_operator_handoff_manual_queue_status": "",
        "mt5_operator_handoff_manual_queue_next_action": "",
        "mt5_operator_handoff_manual_queue_progress_state": "",
        "mt5_operator_handoff_manual_collect_status": "",
        "mt5_operator_handoff_manual_collect_next_action": "",
        "mt5_operator_handoff_next_mt5_step": {},
        "mt5_operator_handoff_quick_input": {},
        "mt5_operator_handoff_next_step_operator_summary": "",
        "mt5_operator_handoff_next_step_summary": "",
        "mt5_operator_handoff_next_step_collect_filter_summary": "",
        "mt5_operator_handoff_manual_collect_dry_run_command_text": "",
        "mt5_operator_handoff_manual_collect_execute_command_text": "",
        "mt5_operator_handoff_manual_collect_execute_and_refresh_analysis_command_text": "",
        "mt5_operator_handoff_manual_collect_execute_and_refresh_all_command_text": "",
        "mt5_operator_handoff_manual_collect_execute_and_refresh_full_analysis_command_text": "",
        "mt5_operator_handoff_bridge_required_for_standalone_tester": "",
        "mt5_operator_handoff_bridge_ready_for_mt5_validation": "",
        "mt5_operator_handoff_bridge_status": "",
        "mt5_operator_handoff_bridge_note": "",
    }
    aliases.update(
        {
            key: operator_summary.get(key, default)
            for key, default in handoff_defaults.items()
        }
    )
    return aliases


def mt5_tester_status_operator_summary(
    status: dict[str, Any],
    *,
    output_json: str = "",
    output_md: str = "",
) -> dict[str, Any]:
    next_runner = (
        status.get("next_action_runner")
        if isinstance(status.get("next_action_runner"), dict)
        else {}
    )
    manual_queue = status["manual_test_queue"]
    manual_queue_with_optimization = (
        status.get("manual_test_queue_with_optimization")
        if isinstance(status.get("manual_test_queue_with_optimization"), dict)
        else {}
    )
    manual_queue_launch_with_optimization = (
        status.get("manual_queue_launch_with_optimization")
        if isinstance(status.get("manual_queue_launch_with_optimization"), dict)
        else {}
    )
    manual_collect_with_optimization = (
        status.get("manual_collect_with_optimization")
        if isinstance(status.get("manual_collect_with_optimization"), dict)
        else {}
    )
    manual_operator_packet_with_optimization = (
        status.get("manual_operator_packet_with_optimization")
        if isinstance(status.get("manual_operator_packet_with_optimization"), dict)
        else {}
    )
    manual_operator_packet_with_optimization_next_operator = (
        manual_operator_packet_with_optimization.get("next_operator_action")
        if isinstance(
            manual_operator_packet_with_optimization.get("next_operator_action"),
            dict,
        )
        else {}
    )
    manual_auto_collect_watch = (
        status.get("manual_auto_collect_watch")
        if isinstance(status.get("manual_auto_collect_watch"), dict)
        else {}
    )
    manual_queue_handoff = (
        manual_queue.get("operator_handoff") if isinstance(manual_queue.get("operator_handoff"), dict) else {}
    )
    manual_queue_with_optimization_handoff = (
        manual_queue_with_optimization.get("operator_handoff")
        if isinstance(manual_queue_with_optimization.get("operator_handoff"), dict)
        else {}
    )
    mt5_operator_handoff = (
        status.get("mt5_operator_handoff") if isinstance(status.get("mt5_operator_handoff"), dict) else {}
    )
    manual_queue_next_step = manual_queue.get("next_launch_step")
    if not isinstance(manual_queue_next_step, dict) or not manual_queue_next_step:
        manual_queue_next_step = (
            manual_queue_handoff.get("next_mt5_step")
            if isinstance(manual_queue_handoff.get("next_mt5_step"), dict)
            else {}
        )
    manual_queue_with_optimization_next_step = manual_queue_with_optimization.get(
        "next_launch_step"
    )
    if (
        not isinstance(manual_queue_with_optimization_next_step, dict)
        or not manual_queue_with_optimization_next_step
    ):
        manual_queue_with_optimization_next_step = (
            manual_queue_with_optimization_handoff.get("next_mt5_step")
            if isinstance(manual_queue_with_optimization_handoff.get("next_mt5_step"), dict)
            else {}
        )
    manual_queue_quick_input = first_present(
        manual_queue.get("next_quick_input"),
        manual_queue.get("quick_input"),
        manual_queue_handoff.get("next_quick_input"),
        manual_queue_handoff.get("quick_input"),
        mt5_quick_input_from_step(manual_queue_next_step),
    )
    manual_queue_next_queue_step = first_present(
        manual_queue.get("next_queue_step"),
        manual_queue_handoff.get("next_queue_step"),
        manual_queue_quick_input.get("queue_step") if isinstance(manual_queue_quick_input, dict) else "",
        queue_step_from_mt5_step(manual_queue_next_step),
    )
    manual_queue_with_optimization_quick_input = first_present(
        manual_queue_with_optimization.get("next_quick_input"),
        manual_queue_with_optimization.get("quick_input"),
        manual_queue_with_optimization_handoff.get("next_quick_input"),
        manual_queue_with_optimization_handoff.get("quick_input"),
        mt5_quick_input_from_step(manual_queue_with_optimization_next_step),
    )
    manual_queue_with_optimization_next_queue_step = first_present(
        manual_queue_with_optimization.get("next_queue_step"),
        manual_queue_with_optimization_handoff.get("next_queue_step"),
        (
            manual_queue_with_optimization_quick_input.get("queue_step")
            if isinstance(manual_queue_with_optimization_quick_input, dict)
            else ""
        ),
        queue_step_from_mt5_step(manual_queue_with_optimization_next_step),
    )
    quick_input = (
        mt5_operator_handoff.get("quick_input")
        if isinstance(mt5_operator_handoff.get("quick_input"), dict)
        else manual_queue_quick_input
        if isinstance(manual_queue_quick_input, dict)
        else {}
    )
    return {
        "ok": status["ok"],
        "operational_status": status["operational_status"],
        "ready_for_tester_launch": status["ready_for_tester_launch"],
        "next_action_execution_ready": status["next_action_execution"]["ready"],
        "next_action_execution_status": status["next_action_execution"]["status"],
        "back_forward_execution_ready": status["back_forward_execution"]["ready"],
        "back_forward_execution_status": status["back_forward_execution"]["status"],
        "manual_strategy_tester_available": status["manual_strategy_tester"].get("available", ""),
        "manual_strategy_tester_recommended": status["manual_strategy_tester"].get("recommended", ""),
        "manual_strategy_tester_status": status["manual_strategy_tester"].get("status", ""),
        "manual_strategy_tester_manual_run_start_after": status["manual_strategy_tester"].get(
            "manual_run_start_after", ""
        ),
        "manual_strategy_tester_step_count": status["manual_strategy_tester"].get("step_count", ""),
        "manual_strategy_tester_collect_only_command_text": status["manual_strategy_tester"].get(
            "collect_only_command_text", ""
        ),
        "manual_strategy_tester_collect_ready": status["manual_strategy_tester"].get(
            "manual_collect_ready", ""
        ),
        "manual_strategy_tester_collect_status": status["manual_strategy_tester"].get(
            "manual_collect_status", ""
        ),
        "manual_strategy_tester_collect_next_action": status["manual_strategy_tester"].get(
            "manual_collect_next_action", ""
        ),
        "manual_test_queue_status": manual_queue.get("status", ""),
        "manual_test_queue_next_action": manual_queue.get("next_action", ""),
        "manual_test_queue_progress_state": manual_queue_handoff.get("progress_state", ""),
        "manual_test_queue_entry_count": manual_queue.get("entry_count", ""),
        "manual_test_queue_total_entry_count": manual_queue.get("total_entry_count", ""),
        "manual_test_queue_stale_entry_count": manual_queue.get("stale_entry_count", ""),
        "manual_test_queue_manual_run_start_marked": manual_queue.get(
            "manual_run_start_marked", ""
        ),
        "manual_test_queue_manual_run_start_marked_this_run": manual_queue.get(
            "manual_run_start_marked_this_run", ""
        ),
        "manual_test_queue_manual_run_start_preserved": manual_queue.get(
            "manual_run_start_preserved", ""
        ),
        "manual_test_queue_manual_run_start_state_count": manual_queue.get(
            "manual_run_start_state_count", ""
        ),
        "manual_test_queue_manual_run_start_state_marked_count": manual_queue.get(
            "manual_run_start_state_marked_count", ""
        ),
        "manual_test_queue_manual_run_start_effective_after_values": manual_queue.get(
            "manual_run_start_effective_after_values", []
        ),
        "manual_test_queue_manual_run_start_after_override": manual_queue.get(
            "manual_run_start_after_override", ""
        ),
        "manual_test_queue_step_count": manual_queue.get("step_count", ""),
        "manual_test_queue_waiting_count": manual_queue.get("waiting_count", ""),
        "manual_test_queue_step_report_ready_count": manual_queue.get(
            "step_report_ready_count", ""
        ),
        "manual_test_queue_step_collect_ready_count": manual_queue.get(
            "step_collect_ready_count", ""
        ),
        "manual_test_queue_step_waiting_report_count": manual_queue.get(
            "step_waiting_report_count", ""
        ),
        "manual_test_queue_step_launch_needed_count": manual_queue.get(
            "step_launch_needed_count", ""
        ),
        "manual_test_queue_step_report_ready_ids": manual_queue.get(
            "step_report_ready_ids", []
        ),
        "manual_test_queue_step_collect_ready_ids": manual_queue.get(
            "step_collect_ready_ids", []
        ),
        "manual_test_queue_step_waiting_report_ids": manual_queue.get(
            "step_waiting_report_ids", []
        ),
        "manual_test_queue_step_launch_needed_ids": manual_queue.get(
            "step_launch_needed_ids", []
        ),
        "manual_test_queue_collect_check_command_text": manual_queue_handoff.get(
            "collect_check_command_text", ""
        ),
        "manual_test_queue_next_queue_step": manual_queue_next_queue_step,
        "manual_test_queue_quick_input": manual_queue_quick_input,
        "manual_test_queue_next_quick_input": manual_queue_quick_input,
        "manual_test_queue_next_launch_step": manual_queue_next_step,
        "manual_test_queue_next_step_operator_summary": manual_queue_handoff.get(
            "next_step_operator_summary", ""
        ),
        "manual_test_queue_next_step_summary": (
            manual_queue_handoff.get("next_step_summary")
            or manual_queue_handoff.get("next_step_operator_summary", "")
        ),
        "manual_test_queue_next_step_collect_filter_summary": manual_queue_handoff.get(
            "next_step_collect_filter_summary", ""
        ),
        "mt5_operator_handoff_state": mt5_operator_handoff.get("state", ""),
        "mt5_operator_handoff_recommended_path": mt5_operator_handoff.get(
            "recommended_path", ""
        ),
        "mt5_operator_handoff_manual_strategy_tester_available": mt5_operator_handoff.get(
            "manual_strategy_tester_available", ""
        ),
        "mt5_operator_handoff_terminal_running": mt5_operator_handoff.get(
            "terminal_running", ""
        ),
        "mt5_operator_handoff_auto_launch_ready": mt5_operator_handoff.get(
            "auto_launch_ready", ""
        ),
        "mt5_operator_handoff_auto_launch_status": mt5_operator_handoff.get(
            "auto_launch_status", ""
        ),
        "mt5_operator_handoff_auto_launch_blocked_by_running_terminal": mt5_operator_handoff.get(
            "auto_launch_blocked_by_running_terminal", ""
        ),
        "mt5_operator_handoff_auto_launch_blockers": mt5_operator_handoff.get(
            "auto_launch_blockers", []
        ),
        "mt5_operator_handoff_manual_queue_status": mt5_operator_handoff.get(
            "manual_queue_status", ""
        ),
        "mt5_operator_handoff_manual_queue_next_action": mt5_operator_handoff.get(
            "manual_queue_next_action", ""
        ),
        "mt5_operator_handoff_quick_input": quick_input,
        "mt5_operator_handoff_manual_queue_progress_state": mt5_operator_handoff.get(
            "manual_queue_progress_state", ""
        ),
        "mt5_operator_handoff_manual_collect_status": mt5_operator_handoff.get(
            "manual_collect_status", ""
        ),
        "mt5_operator_handoff_manual_collect_next_action": mt5_operator_handoff.get(
            "manual_collect_next_action", ""
        ),
        "mt5_operator_handoff_next_mt5_step": mt5_operator_handoff.get(
            "next_mt5_step", {}
        ),
        "mt5_operator_handoff_next_step_operator_summary": mt5_operator_handoff.get(
            "next_step_operator_summary", ""
        ),
        "mt5_operator_handoff_next_step_summary": (
            mt5_operator_handoff.get("next_step_summary")
            or mt5_operator_handoff.get("next_step_operator_summary", "")
        ),
        "mt5_operator_handoff_next_step_collect_filter_summary": mt5_operator_handoff.get(
            "next_step_collect_filter_summary", ""
        ),
        "mt5_operator_handoff_manual_collect_dry_run_command_text": mt5_operator_handoff.get(
            "manual_collect_dry_run_command_text", ""
        ),
        "mt5_operator_handoff_manual_collect_execute_command_text": mt5_operator_handoff.get(
            "manual_collect_execute_command_text", ""
        ),
        "mt5_operator_handoff_manual_collect_execute_and_refresh_analysis_command_text": mt5_operator_handoff.get(
            "manual_collect_execute_and_refresh_analysis_command_text", ""
        ),
        "mt5_operator_handoff_manual_collect_execute_and_refresh_all_command_text": mt5_operator_handoff.get(
            "manual_collect_execute_and_refresh_all_command_text", ""
        ),
        "mt5_operator_handoff_manual_collect_execute_and_refresh_full_analysis_command_text": (
            mt5_operator_handoff.get("manual_collect_execute_and_refresh_full_analysis_command_text")
            or mt5_operator_handoff.get("manual_collect_execute_and_refresh_all_command_text", "")
        ),
        "mt5_operator_handoff_bridge_required_for_standalone_tester": mt5_operator_handoff.get(
            "bridge_required_for_standalone_tester", ""
        ),
        "mt5_operator_handoff_bridge_ready_for_mt5_validation": mt5_operator_handoff.get(
            "bridge_ready_for_mt5_validation", ""
        ),
        "mt5_operator_handoff_bridge_status": mt5_operator_handoff.get(
            "bridge_status", ""
        ),
        "mt5_operator_handoff_bridge_note": mt5_operator_handoff.get("bridge_note", ""),
        "manual_queue_launch_status": status["manual_queue_launch"].get("status", ""),
        "manual_queue_launch_next_action": status["manual_queue_launch"].get("next_action", ""),
        "manual_queue_launch_queue_refresh_status": (
            status["manual_queue_launch"].get("queue_refresh")
            if isinstance(status["manual_queue_launch"].get("queue_refresh"), dict)
            else {}
        ).get("status", ""),
        "manual_queue_launch_queue_refresh_ok": (
            status["manual_queue_launch"].get("queue_refresh")
            if isinstance(status["manual_queue_launch"].get("queue_refresh"), dict)
            else {}
        ).get("ok", ""),
        "manual_queue_launch_queue_refresh_enabled": (
            status["manual_queue_launch"].get("queue_refresh")
            if isinstance(status["manual_queue_launch"].get("queue_refresh"), dict)
            else {}
        ).get("enabled", ""),
        "manual_queue_launch_queue_refresh_source_count": (
            status["manual_queue_launch"].get("queue_refresh")
            if isinstance(status["manual_queue_launch"].get("queue_refresh"), dict)
            else {}
        ).get("source_count", ""),
        "manual_queue_launch_queue_entry_count": status["manual_queue_launch"].get(
            "queue_entry_count", ""
        ),
        "manual_queue_launch_queue_total_entry_count": status["manual_queue_launch"].get(
            "queue_total_entry_count", ""
        ),
        "manual_queue_launch_queue_step_count": status["manual_queue_launch"].get(
            "queue_step_count", ""
        ),
        "manual_queue_launch_queue_waiting_count": status["manual_queue_launch"].get(
            "queue_waiting_count", ""
        ),
        "manual_queue_launch_queue_operator_handoff_state": status["manual_queue_launch"].get(
            "queue_operator_handoff_state", ""
        ),
        "manual_queue_launch_queue_operator_handoff_next_mt5_step": status["manual_queue_launch"].get(
            "queue_operator_handoff_next_mt5_step", {}
        ),
        "manual_queue_launch_queue_operator_handoff_quick_input": status["manual_queue_launch"].get(
            "queue_operator_handoff_quick_input", {}
        ),
        "manual_queue_launch_queue_operator_handoff_collect_ready": status["manual_queue_launch"].get(
            "queue_operator_handoff_collect_ready", ""
        ),
        "manual_queue_launch_queue_operator_handoff_waiting_entry_ids": status["manual_queue_launch"].get(
            "queue_operator_handoff_waiting_entry_ids", []
        ),
        "manual_queue_launch_queue_operator_handoff_collect_dry_run_command_text": status[
            "manual_queue_launch"
        ].get("queue_operator_handoff_collect_dry_run_command_text", ""),
        "manual_queue_launch_queue_operator_handoff_collect_execute_command_text": status[
            "manual_queue_launch"
        ].get("queue_operator_handoff_collect_execute_command_text", ""),
        "manual_queue_launch_detached": status["manual_queue_launch"].get("detached", ""),
        "manual_queue_launch_process_pid": status["manual_queue_launch"].get("process_pid", ""),
        "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_analysis_command_text": status[
            "manual_queue_launch"
        ].get("queue_operator_handoff_collect_execute_and_refresh_analysis_command_text", ""),
        "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_all_command_text": status[
            "manual_queue_launch"
        ].get("queue_operator_handoff_collect_execute_and_refresh_all_command_text", ""),
        "manual_collect_execute_and_refresh_analysis_command_text": mt5_operator_handoff.get(
            "manual_collect_execute_and_refresh_analysis_command_text", ""
        ),
        "manual_collect_execute_and_refresh_all_command_text": mt5_operator_handoff.get(
            "manual_collect_execute_and_refresh_all_command_text", ""
        ),
        "manual_queue_launch_selected": status["manual_queue_launch"].get("selected", ""),
        "manual_queue_launch_selected_matches_queue_handoff": status["manual_queue_launch"].get(
            "selected_matches_queue_handoff", ""
        ),
        "manual_queue_launch_selected_step_fingerprint": status["manual_queue_launch"].get(
            "selected_step_fingerprint", ""
        ),
        "manual_queue_launch_selected_expected_report": status["manual_queue_launch"].get(
            "selected_expected_report", ""
        ),
        "manual_queue_launch_selected_expected_report_artifact": status["manual_queue_launch"].get(
            "selected_expected_report_artifact", ""
        ),
        "manual_queue_launch_launch_command_kind": status["manual_queue_launch"].get(
            "launch_command_kind", ""
        ),
        "manual_queue_launch_manual_run_start_mark_status": status["manual_queue_launch"].get(
            "manual_run_start_mark_status", ""
        ),
        "manual_queue_launch_manual_run_start_mark_attempted": status["manual_queue_launch"].get(
            "manual_run_start_mark_attempted", ""
        ),
        "manual_queue_launch_manual_run_start_after": status["manual_queue_launch"].get(
            "manual_run_start_after", ""
        ),
        "manual_queue_launch_blocked": status["manual_queue_launch"].get("blocked", ""),
        "manual_queue_launch_blocked_reasons": status["manual_queue_launch"].get("blocked_reasons", []),
        "manual_queue_launch_running_terminal_count": status["manual_queue_launch"].get(
            "running_terminal_count", ""
        ),
        "manual_collect_run_status": status["manual_collect_run"].get("status", ""),
        "manual_collect_run_next_action": status["manual_collect_run"].get("next_action", ""),
        "manual_collect_run_selected_count": status["manual_collect_run"].get("selected_count", ""),
        "manual_collect_run_waiting_count": status["manual_collect_run"].get("waiting_count", ""),
        "manual_collect_run_invalid_count": status["manual_collect_run"].get("invalid_count", ""),
        "manual_collect_run_queue_step_count": status["manual_collect_run"].get("queue_step_count", ""),
        "manual_collect_run_queue_step_report_ready_count": status["manual_collect_run"].get(
            "queue_step_report_ready_count", ""
        ),
        "manual_collect_run_queue_step_waiting_report_count": status["manual_collect_run"].get(
            "queue_step_waiting_report_count", ""
        ),
        "manual_collect_run_queue_step_launch_needed_count": status["manual_collect_run"].get(
            "queue_step_launch_needed_count", ""
        ),
        "manual_test_queue_with_optimization_status": manual_queue_with_optimization.get("status", ""),
        "manual_test_queue_with_optimization_next_action": manual_queue_with_optimization.get(
            "next_action", ""
        ),
        "manual_test_queue_with_optimization_progress_state": (
            manual_queue_with_optimization.get("progress_state", "")
        ),
        "manual_test_queue_with_optimization_entry_count": manual_queue_with_optimization.get(
            "entry_count", ""
        ),
        "manual_test_queue_with_optimization_total_entry_count": (
            manual_queue_with_optimization.get("total_entry_count", "")
        ),
        "manual_test_queue_with_optimization_stale_entry_count": (
            manual_queue_with_optimization.get("stale_entry_count", "")
        ),
        "manual_test_queue_with_optimization_manual_run_start_marked": (
            manual_queue_with_optimization.get("manual_run_start_marked", "")
        ),
        "manual_test_queue_with_optimization_manual_run_start_marked_this_run": (
            manual_queue_with_optimization.get("manual_run_start_marked_this_run", "")
        ),
        "manual_test_queue_with_optimization_manual_run_start_preserved": (
            manual_queue_with_optimization.get("manual_run_start_preserved", "")
        ),
        "manual_test_queue_with_optimization_manual_run_start_state_count": (
            manual_queue_with_optimization.get("manual_run_start_state_count", "")
        ),
        "manual_test_queue_with_optimization_manual_run_start_state_marked_count": (
            manual_queue_with_optimization.get("manual_run_start_state_marked_count", "")
        ),
        "manual_test_queue_with_optimization_manual_run_start_effective_after_values": (
            manual_queue_with_optimization.get("manual_run_start_effective_after_values", [])
        ),
        "manual_test_queue_with_optimization_manual_run_start_after_override": (
            manual_queue_with_optimization.get("manual_run_start_after_override", "")
        ),
        "manual_test_queue_with_optimization_step_count": manual_queue_with_optimization.get(
            "step_count", ""
        ),
        "manual_test_queue_with_optimization_ready_to_collect_count": (
            manual_queue_with_optimization.get("ready_to_collect_count", "")
        ),
        "manual_test_queue_with_optimization_waiting_count": manual_queue_with_optimization.get(
            "waiting_count", ""
        ),
        "manual_test_queue_with_optimization_step_report_ready_count": (
            manual_queue_with_optimization.get("step_report_ready_count", "")
        ),
        "manual_test_queue_with_optimization_step_collect_ready_count": (
            manual_queue_with_optimization.get("step_collect_ready_count", "")
        ),
        "manual_test_queue_with_optimization_step_waiting_report_count": (
            manual_queue_with_optimization.get("step_waiting_report_count", "")
        ),
        "manual_test_queue_with_optimization_step_launch_needed_count": (
            manual_queue_with_optimization.get("step_launch_needed_count", "")
        ),
        "manual_test_queue_with_optimization_step_report_ready_ids": (
            manual_queue_with_optimization.get("step_report_ready_ids", [])
        ),
        "manual_test_queue_with_optimization_step_collect_ready_ids": (
            manual_queue_with_optimization.get("step_collect_ready_ids", [])
        ),
        "manual_test_queue_with_optimization_step_waiting_report_ids": (
            manual_queue_with_optimization.get("step_waiting_report_ids", [])
        ),
        "manual_test_queue_with_optimization_step_launch_needed_ids": (
            manual_queue_with_optimization.get("step_launch_needed_ids", [])
        ),
        "manual_test_queue_with_optimization_collect_check_command_text": (
            manual_queue_with_optimization_handoff.get("collect_check_command_text", "")
        ),
        "manual_test_queue_with_optimization_next_queue_step": (
            manual_queue_with_optimization_next_queue_step
        ),
        "manual_test_queue_with_optimization_quick_input": (
            manual_queue_with_optimization_quick_input
        ),
        "manual_test_queue_with_optimization_next_quick_input": (
            manual_queue_with_optimization_quick_input
        ),
        "manual_test_queue_with_optimization_static_strategy_config_count": (
            manual_queue_with_optimization.get("static_strategy_config_count", "")
        ),
        "manual_test_queue_with_optimization_static_strategy_configs": (
            manual_queue_with_optimization.get("static_strategy_configs", [])
        ),
        "manual_test_queue_with_optimization_static_candidate_label_count": (
            manual_queue_with_optimization.get("static_candidate_label_count", "")
        ),
        "manual_test_queue_with_optimization_static_candidate_labels": (
            manual_queue_with_optimization.get("static_candidate_labels", [])
        ),
        "manual_test_queue_with_optimization_next_launch_step": (
            manual_queue_with_optimization_next_step
        ),
        "manual_test_queue_with_optimization_operator_handoff": (
            manual_queue_with_optimization_handoff
        ),
        "manual_test_queue_with_optimization_operator_handoff_quick_input": (
            manual_queue_with_optimization_handoff.get("quick_input", {})
        ),
        "manual_test_queue_with_optimization_next_step_operator_summary": (
            manual_queue_with_optimization_handoff.get("next_step_operator_summary", "")
        ),
        "manual_test_queue_with_optimization_next_step_summary": first_present(
            manual_queue_with_optimization_handoff.get("next_step_summary"),
            manual_queue_with_optimization_handoff.get("next_step_operator_summary"),
        ),
        "manual_test_queue_with_optimization_next_step_collect_filter_summary": (
            manual_queue_with_optimization_handoff.get("next_step_collect_filter_summary", "")
        ),
        "manual_queue_launch_with_optimization_status": manual_queue_launch_with_optimization.get(
            "status", ""
        ),
        "manual_queue_launch_with_optimization_queue_entry_count": (
            manual_queue_launch_with_optimization.get("queue_entry_count", "")
        ),
        "manual_queue_launch_with_optimization_queue_total_entry_count": (
            manual_queue_launch_with_optimization.get("queue_total_entry_count", "")
        ),
        "manual_queue_launch_with_optimization_queue_step_count": (
            manual_queue_launch_with_optimization.get("queue_step_count", "")
        ),
        "manual_queue_launch_with_optimization_queue_waiting_count": (
            manual_queue_launch_with_optimization.get("queue_waiting_count", "")
        ),
        "manual_queue_launch_with_optimization_launch_command_kind": (
            manual_queue_launch_with_optimization.get("launch_command_kind", "")
        ),
        "manual_queue_launch_with_optimization_manual_run_start_mark_status": (
            manual_queue_launch_with_optimization.get("manual_run_start_mark_status", "")
        ),
        "manual_queue_launch_with_optimization_manual_run_start_mark_attempted": (
            manual_queue_launch_with_optimization.get("manual_run_start_mark_attempted", "")
        ),
        "manual_queue_launch_with_optimization_manual_run_start_after": (
            manual_queue_launch_with_optimization.get("manual_run_start_after", "")
        ),
        "manual_queue_launch_with_optimization_blocked_reasons": manual_queue_launch_with_optimization.get(
            "blocked_reasons", []
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_state": (
            manual_queue_launch_with_optimization.get("queue_operator_handoff_state", "")
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_next_mt5_step": (
            manual_queue_launch_with_optimization.get("queue_operator_handoff_next_mt5_step", {})
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_next_step_operator_summary": (
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_next_step_operator_summary", ""
            )
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_next_step_summary": (
            manual_queue_launch_with_optimization.get("queue_operator_handoff_next_step_summary")
            or manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_next_step_operator_summary", ""
            )
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_next_step_collect_filter_summary": (
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_next_step_collect_filter_summary", ""
            )
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_collect_ready": (
            manual_queue_launch_with_optimization.get("queue_operator_handoff_collect_ready", "")
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_waiting_entry_ids": (
            manual_queue_launch_with_optimization.get("queue_operator_handoff_waiting_entry_ids", [])
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_collect_dry_run_command_text": (
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_collect_dry_run_command_text", ""
            )
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_command_text": (
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_collect_execute_command_text", ""
            )
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_analysis_command_text": (
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_collect_execute_and_refresh_analysis_command_text",
                "",
            )
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_all_command_text": (
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_collect_execute_and_refresh_all_command_text",
                "",
            )
        ),
        "manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text": (
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text"
            )
            or manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_collect_execute_and_refresh_all_command_text",
                "",
            )
        ),
        "manual_collect_with_optimization_status": manual_collect_with_optimization.get("status", ""),
        "manual_collect_with_optimization_selected_count": manual_collect_with_optimization.get(
            "selected_count", ""
        ),
        "manual_collect_with_optimization_waiting_count": manual_collect_with_optimization.get(
            "waiting_count", ""
        ),
        "manual_auto_collect_watch_exists": manual_auto_collect_watch.get("exists", ""),
        "manual_auto_collect_watch_ok": manual_auto_collect_watch.get("ok", ""),
        "manual_auto_collect_watch_status": manual_auto_collect_watch.get("status", ""),
        "manual_auto_collect_watch_generated_at": manual_auto_collect_watch.get("generated_at", ""),
        "manual_auto_collect_watch_next_action": manual_auto_collect_watch.get("next_action", ""),
        "manual_auto_collect_watch_execute_ready": manual_auto_collect_watch.get("execute_ready", ""),
        "manual_auto_collect_watch_ready_to_execute": manual_auto_collect_watch.get(
            "ready_to_execute", ""
        ),
        "manual_auto_collect_watch_ready_for_collect_execute": manual_auto_collect_watch.get(
            "ready_for_collect_execute", ""
        ),
        "manual_auto_collect_watch_selected_count": manual_auto_collect_watch.get(
            "selected_count", ""
        ),
        "manual_auto_collect_watch_waiting_count": manual_auto_collect_watch.get(
            "waiting_count", ""
        ),
        "manual_auto_collect_watch_invalid_count": manual_auto_collect_watch.get(
            "invalid_count", ""
        ),
        "manual_auto_collect_watch_collect_dry_run_command_text": manual_auto_collect_watch.get(
            "collect_dry_run_command_text", ""
        ),
        "manual_auto_collect_watch_collect_execute_command_text": manual_auto_collect_watch.get(
            "collect_execute_command_text", ""
        ),
        "manual_auto_collect_watch_queue_launch_status": manual_auto_collect_watch.get(
            "queue_launch_status", ""
        ),
        "manual_auto_collect_watch_queue_launch_blocked": manual_auto_collect_watch.get(
            "queue_launch_blocked", ""
        ),
        "manual_auto_collect_watch_queue_launch_blocked_reasons": manual_auto_collect_watch.get(
            "queue_launch_blocked_reasons", []
        ),
        "manual_auto_collect_watch_operator_packet_next_queue_step": manual_auto_collect_watch.get(
            "operator_packet_next_queue_step", ""
        ),
        "manual_auto_collect_watch_operator_packet_auto_launch_command_text": (
            manual_auto_collect_watch.get("operator_packet_auto_launch_command_text", "")
        ),
        "manual_auto_collect_watch_operator_packet_auto_launch_command_available": (
            manual_auto_collect_watch.get("operator_packet_auto_launch_command_available", "")
        ),
        "manual_auto_collect_watch_operator_packet_auto_launch_blocked": (
            manual_auto_collect_watch.get("operator_packet_auto_launch_blocked", "")
        ),
        "manual_auto_collect_watch_operator_packet_auto_launch_blocked_reasons": (
            manual_auto_collect_watch.get("operator_packet_auto_launch_blocked_reasons", [])
        ),
        "manual_auto_collect_watch_operator_packet_auto_launch_note": (
            manual_auto_collect_watch.get("operator_packet_auto_launch_note", "")
        ),
        "manual_auto_collect_watch_operator_packet_strategy_source_time_refresh_status": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_source_time_refresh_status", ""
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_source_time_issue_labels": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_source_time_issue_labels", []
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_source_time_candidate_issue_labels": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_source_time_candidate_issue_labels", []
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_source_time_refresh_analysis_command_text": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_source_time_refresh_analysis_command_text", ""
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_source_time_refresh_analysis_command_available": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_source_time_refresh_analysis_command_available", ""
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_buy_candidate_gap_status": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_buy_candidate_gap_status", ""
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_buy_candidate_gap_reason": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_buy_candidate_gap_reason", ""
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_buy_candidate_gap_diagnostic_labels": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_buy_candidate_gap_diagnostic_labels", []
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_buy_candidate_gap_collect_refresh_command_text": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_buy_candidate_gap_collect_refresh_command_text", ""
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_buy_candidate_gap_collect_refresh_command_available": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_buy_candidate_gap_collect_refresh_command_available", ""
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_status": (
            manual_auto_collect_watch.get("operator_packet_strategy_operator_decision_status", "")
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_verdict": (
            manual_auto_collect_watch.get("operator_packet_strategy_operator_decision_verdict", "")
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_adoptable": (
            manual_auto_collect_watch.get("operator_packet_strategy_operator_decision_adoptable", "")
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_primary_blocker": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_operator_decision_primary_blocker", ""
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_primary_reason": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_operator_decision_primary_reason", ""
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_next_action": (
            manual_auto_collect_watch.get("operator_packet_strategy_operator_decision_next_action", "")
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_summary": (
            manual_auto_collect_watch.get("operator_packet_strategy_operator_decision_summary", "")
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_command_text": (
            manual_auto_collect_watch.get("operator_packet_strategy_operator_decision_command_text", "")
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_follow_up_command_text": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_operator_decision_follow_up_command_text", ""
            )
        ),
        "manual_auto_collect_watch_execution_enabled": manual_auto_collect_watch.get(
            "execution_enabled", ""
        ),
        "manual_auto_collect_watch_execution_attempted": manual_auto_collect_watch.get(
            "execution_attempted", ""
        ),
        "manual_auto_collect_watch_execution_returncode": manual_auto_collect_watch.get(
            "execution_returncode", ""
        ),
        "manual_auto_collect_watch_execution_status": manual_auto_collect_watch.get(
            "execution_status", ""
        ),
        "manual_operator_packet_with_optimization_status": manual_operator_packet_with_optimization.get(
            "status", ""
        ),
        "manual_operator_packet_with_optimization_next_queue_step": manual_operator_packet_with_optimization.get(
            "next_queue_step", ""
        ),
        "manual_operator_packet_with_optimization_next_operator_action": first_present(
            manual_operator_packet_with_optimization.get("next_operator_action_name"),
            manual_operator_packet_with_optimization_next_operator.get("action"),
            manual_operator_packet_with_optimization.get("next_operator_action"),
        ),
        "manual_operator_packet_with_optimization_next_operator_mode": manual_operator_packet_with_optimization.get(
            "next_operator_mode", ""
        ),
        "manual_operator_packet_with_optimization_next_operator_instruction": manual_operator_packet_with_optimization.get(
            "next_operator_instruction", ""
        ),
        "manual_operator_packet_with_optimization_next_operator_command_text": manual_operator_packet_with_optimization.get(
            "next_operator_command_text", ""
        ),
        "manual_operator_packet_with_optimization_next_operator_before_mt5_command_text": manual_operator_packet_with_optimization.get(
            "next_operator_before_mt5_command_text", ""
        ),
        "manual_operator_packet_with_optimization_next_operator_follow_up_command_text": manual_operator_packet_with_optimization.get(
            "next_operator_follow_up_command_text", ""
        ),
        "manual_operator_packet_with_optimization_next_operator_verification": manual_operator_packet_with_optimization.get(
            "next_operator_verification", ""
        ),
        "manual_operator_packet_with_optimization_next_operator_launch_state": manual_operator_packet_with_optimization.get(
            "next_operator_launch_state", ""
        ),
        "manual_operator_packet_with_optimization_auto_launch_command_text": (
            manual_operator_packet_with_optimization.get("auto_launch_command_text", "")
        ),
        "manual_operator_packet_with_optimization_auto_launch_command_available": (
            manual_operator_packet_with_optimization.get("auto_launch_command_available", "")
        ),
        "manual_operator_packet_with_optimization_auto_launch_blocked": (
            manual_operator_packet_with_optimization.get("auto_launch_blocked", "")
        ),
        "manual_operator_packet_with_optimization_auto_launch_blocked_reasons": (
            manual_operator_packet_with_optimization.get("auto_launch_blocked_reasons", [])
        ),
        "manual_operator_packet_with_optimization_auto_launch_note": (
            manual_operator_packet_with_optimization.get("auto_launch_note", "")
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_status": (
            manual_operator_packet_with_optimization.get("back_forward_quick_start_status", "")
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_step_count": (
            manual_operator_packet_with_optimization.get("back_forward_quick_start_step_count", "")
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_waiting_step_count": (
            manual_operator_packet_with_optimization.get(
                "back_forward_quick_start_waiting_step_count",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_current_queue_step": (
            manual_operator_packet_with_optimization.get(
                "back_forward_quick_start_current_queue_step",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_current_purpose": (
            manual_operator_packet_with_optimization.get(
                "back_forward_quick_start_current_purpose",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_steps": (
            manual_operator_packet_with_optimization.get(
                "back_forward_quick_start_steps",
                [],
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_quick_inputs": (
            manual_operator_packet_with_optimization.get(
                "back_forward_quick_start_quick_inputs",
                [],
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_current_quick_input": (
            manual_operator_packet_with_optimization.get(
                "back_forward_quick_start_current_quick_input",
                {},
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_backtest_quick_input": (
            manual_operator_packet_with_optimization.get(
                "back_forward_quick_start_backtest_quick_input",
                {},
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_forward_quick_input": (
            manual_operator_packet_with_optimization.get(
                "back_forward_quick_start_forward_quick_input",
                {},
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_collect_command_text": (
            manual_operator_packet_with_optimization.get(
                "back_forward_quick_start_collect_command_text",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_full_queue_collect_command_text": (
            manual_operator_packet_with_optimization.get(
                "back_forward_quick_start_full_queue_collect_command_text",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_auto_launch_blocked": (
            manual_operator_packet_with_optimization.get(
                "back_forward_quick_start_auto_launch_blocked",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_quick_start_auto_launch_blocked_reasons": (
            manual_operator_packet_with_optimization.get(
                "back_forward_quick_start_auto_launch_blocked_reasons",
                [],
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_completion_summary": (
            manual_operator_packet_with_optimization.get(
                "back_forward_completion_summary",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_completion_manual_run_start_after": (
            manual_operator_packet_with_optimization.get(
                "back_forward_completion_manual_run_start_after",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_completion_expected_step_count": (
            manual_operator_packet_with_optimization.get(
                "back_forward_completion_expected_step_count",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_completion_waiting_step_count": (
            manual_operator_packet_with_optimization.get(
                "back_forward_completion_waiting_step_count",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_completion_collect_command_text": (
            manual_operator_packet_with_optimization.get(
                "back_forward_completion_collect_command_text",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_completion_steps": (
            manual_operator_packet_with_optimization.get(
                "back_forward_completion_steps",
                [],
            )
        ),
        "manual_operator_packet_with_optimization_back_forward_completion_decision_thresholds": (
            manual_operator_packet_with_optimization.get(
                "back_forward_completion_decision_thresholds",
                {},
            )
        ),
        "manual_operator_packet_with_optimization_next_operator_quick_input": (
            manual_operator_packet_with_optimization.get("next_operator_quick_input")
            if isinstance(
                manual_operator_packet_with_optimization.get("next_operator_quick_input"),
                dict,
            )
            else manual_operator_packet_with_optimization_next_operator.get("quick_input")
            if isinstance(
                manual_operator_packet_with_optimization_next_operator.get("quick_input"),
                dict,
            )
            else manual_operator_packet_with_optimization.get("next_step_quick_input", {})
        ),
        "manual_operator_packet_with_optimization_next_step_quick_input": manual_operator_packet_with_optimization.get(
            "next_step_quick_input", {}
        ),
        "manual_operator_packet_with_optimization_manual_run_start_marked": (
            manual_operator_packet_with_optimization.get("manual_run_start_marked", "")
        ),
        "manual_operator_packet_with_optimization_manual_run_start_marked_this_run": (
            manual_operator_packet_with_optimization.get("manual_run_start_marked_this_run", "")
        ),
        "manual_operator_packet_with_optimization_manual_run_start_preserved": (
            manual_operator_packet_with_optimization.get("manual_run_start_preserved", "")
        ),
        "manual_operator_packet_with_optimization_manual_run_start_state_count": (
            manual_operator_packet_with_optimization.get("manual_run_start_state_count", "")
        ),
        "manual_operator_packet_with_optimization_manual_run_start_state_marked_count": (
            manual_operator_packet_with_optimization.get(
                "manual_run_start_state_marked_count", ""
            )
        ),
        "manual_operator_packet_with_optimization_manual_run_start_effective_after": (
            manual_operator_packet_with_optimization.get("manual_run_start_effective_after", "")
        ),
        "manual_operator_packet_with_optimization_manual_run_start_effective_after_values": (
            manual_operator_packet_with_optimization.get(
                "manual_run_start_effective_after_values", []
            )
        ),
        "manual_operator_packet_with_optimization_manual_run_start_after_override": (
            manual_operator_packet_with_optimization.get("manual_run_start_after_override", "")
        ),
        "manual_operator_packet_with_optimization_next_step_operator_summary": manual_operator_packet_with_optimization.get(
            "next_step_operator_summary", ""
        ),
        "manual_operator_packet_with_optimization_next_step_summary": (
            manual_operator_packet_with_optimization.get("next_step_summary")
            or manual_operator_packet_with_optimization.get("next_step_operator_summary", "")
        ),
        "manual_operator_packet_with_optimization_next_step_collect_filter_summary": manual_operator_packet_with_optimization.get(
            "next_step_collect_filter_summary", ""
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_status": manual_operator_packet_with_optimization.get(
            "strategy_back_forward_decision_status", ""
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_adoptable": manual_operator_packet_with_optimization.get(
            "strategy_back_forward_decision_adoptable", ""
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_next_action": manual_operator_packet_with_optimization.get(
            "strategy_back_forward_decision_next_action", ""
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_reason": manual_operator_packet_with_optimization.get(
            "strategy_back_forward_decision_reason", ""
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_collect_command_text": manual_operator_packet_with_optimization.get(
            "strategy_back_forward_decision_collect_command_text", ""
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_command_text": manual_operator_packet_with_optimization.get(
            "strategy_back_forward_decision_sample_shortage_recovery_command_text", ""
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_range_strategy": manual_operator_packet_with_optimization.get(
            "strategy_back_forward_decision_sample_shortage_recovery_range_strategy", ""
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date": manual_operator_packet_with_optimization.get(
            "strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date", ""
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date": manual_operator_packet_with_optimization.get(
            "strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date", ""
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_status": manual_operator_packet_with_optimization.get(
            "strategy_operator_decision_status", ""
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_verdict": manual_operator_packet_with_optimization.get(
            "strategy_operator_decision_verdict", ""
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_adoptable": manual_operator_packet_with_optimization.get(
            "strategy_operator_decision_adoptable", ""
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_primary_blocker": manual_operator_packet_with_optimization.get(
            "strategy_operator_decision_primary_blocker", ""
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_primary_reason": manual_operator_packet_with_optimization.get(
            "strategy_operator_decision_primary_reason", ""
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_next_action": manual_operator_packet_with_optimization.get(
            "strategy_operator_decision_next_action", ""
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_summary": manual_operator_packet_with_optimization.get(
            "strategy_operator_decision_summary", ""
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_command_text": manual_operator_packet_with_optimization.get(
            "strategy_operator_decision_command_text", ""
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_follow_up_command_text": manual_operator_packet_with_optimization.get(
            "strategy_operator_decision_follow_up_command_text", ""
        ),
        "next_action_run_target": next_runner.get("target", ""),
        "next_action_run_kind": next_runner.get("kind", ""),
        "next_action_run_focus_side": next_runner.get("focus_side", ""),
        "next_action_run_optimization_mode": next_runner.get("optimization_mode", ""),
        "next_action_run_config": next_runner.get("config", ""),
        "next_action_run_set": next_runner.get("set", ""),
        "next_action_run_output_set": next_runner.get("output_set", ""),
        "next_action_run_archive_run_id": next_runner.get("agent_csv_archive_run_id", ""),
        "next_action_run_current_for_execution": next_runner.get("current_for_execution", ""),
        "next_action_run_gate_stale_reason": next_runner.get("gate_stale_reason", ""),
        "next_action_run_primary_execution_class": next_runner.get("primary_execution_class", ""),
        "next_action_run_primary_is_mt5_tester_run": next_runner.get(
            "primary_is_mt5_tester_run", ""
        ),
        "next_action_run_blocking_prior_action_count": next_runner.get(
            "blocking_prior_action_count", ""
        ),
        "next_action_run_blocking_prior_actions": next_runner.get(
            "blocking_prior_actions", []
        ),
        "next_action_run_blocking_prior_action_summary": next_runner.get(
            "blocking_prior_action_summary", ""
        ),
        "next_action_run_advisory_prior_action_count": next_runner.get(
            "advisory_prior_action_count", ""
        ),
        "next_action_run_advisory_prior_actions": next_runner.get(
            "advisory_prior_actions", []
        ),
        "next_action_run_advisory_prior_action_summary": next_runner.get(
            "advisory_prior_action_summary", ""
        ),
        "next_action_run_timeout_seconds": next_runner.get("timeout_seconds", ""),
        "next_action_run_timeout_minutes": next_runner.get("timeout_minutes", ""),
        "next_action_run_timeout_note": next_runner.get("timeout_note", ""),
        "next_action_run_timeout_deadline_if_started_now": next_runner.get(
            "timeout_deadline_if_started_now", ""
        ),
        "next_action_run_optimized_input_count": next_runner.get("optimized_input_count", ""),
        "next_action_run_estimated_full_factorial_passes": next_runner.get(
            "estimated_full_factorial_passes", ""
        ),
        "next_action_run_latest_executed_tester_xml_rows": next_runner.get(
            "latest_executed_tester_xml_rows", ""
        ),
        "next_action_run_primary_planned_outputs": next_runner.get(
            "primary_planned_outputs", {}
        ),
        "next_action_run_planned_outputs": next_runner.get("planned_outputs", {}),
        "next_action_run_execute_command_text": next_runner.get("execute_command_text", ""),
        "next_action_run_collect_only_command_text": next_runner.get(
            "collect_only_command_text", ""
        ),
        "next_action_run_manual_strategy_tester_available": next_runner.get(
            "manual_strategy_tester_available", ""
        ),
        "next_action_run_manual_step_count": next_runner.get("manual_step_count", ""),
        "back_forward_run_mt5_strategy_tester_pack_available": status["back_forward_runner"].get(
            "mt5_strategy_tester_pack_available", ""
        ),
        "back_forward_run_mt5_strategy_tester_pack_ready_for_manual_mt5_run": status[
            "back_forward_runner"
        ].get("mt5_strategy_tester_pack_ready_for_manual_mt5_run", ""),
        "back_forward_run_mt5_strategy_tester_pack_next_action": status["back_forward_runner"].get(
            "mt5_strategy_tester_pack_next_action", ""
        ),
        "next_action": status["next_action"],
        "output_json": output_json,
        "output_md": output_md,
    }


def markdown_process_rows(processes: object) -> list[str]:
    if not isinstance(processes, list) or not processes:
        return ["| - |  |"]
    rows: list[str] = []
    for item in processes:
        if not isinstance(item, dict):
            continue
        command = str(item.get("command", "")).replace("|", "\\|")
        rows.append(f"| {item.get('pid', '')} | {command} |")
    return rows if rows else ["| - |  |"]


def compact_list_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)


def auto_launch_blockers_text(
    value: Any,
    *,
    blocked_by_running_terminal: bool = False,
) -> str:
    if isinstance(value, (list, tuple)):
        blockers = [str(item) for item in value if item not in (None, "")]
    elif value in (None, ""):
        blockers = []
    else:
        blockers = [str(value)]
    if blocked_by_running_terminal:
        normalized = [
            "running_terminal_blocks_direct_config" if item == "terminal_running" else item
            for item in blockers
        ]
        if "running_terminal_blocks_direct_config" not in normalized:
            normalized.append("running_terminal_blocks_direct_config")
        blockers = normalized
    return ", ".join(blockers)


def compact_mapping_text(value: Any) -> str:
    if not isinstance(value, dict):
        return compact_list_text(value)
    return ", ".join(f"{key}={item}" for key, item in sorted(value.items()))


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def format_manual_operator_packet_lines(
    packet: dict[str, Any],
    auto_collect_watch: dict[str, Any] | None = None,
) -> list[str]:
    if not packet:
        packet = {}
    if not isinstance(auto_collect_watch, dict):
        auto_collect_watch = {}
    lines = [
        "## MT5 Next Operator Action",
        "",
        f"- Exists: {packet.get('exists', '')}",
        f"- Source: {packet.get('path', '')}",
        f"- Status: {packet.get('status', '')}",
        f"- Queue step: {packet.get('next_queue_step', '')}",
        f"- Action: {packet.get('next_operator_action', '')}",
        f"- Mode: {packet.get('next_operator_mode', '')}",
        f"- Launch state: {packet.get('next_operator_launch_state', '')}",
        f"- Instruction: {packet.get('next_operator_instruction', '')}",
    ]
    command_text = str(packet.get("next_operator_command_text") or "")
    before_mt5 = str(packet.get("next_operator_before_mt5_command_text") or "")
    follow_up = str(packet.get("next_operator_follow_up_command_text") or "")
    if command_text:
        lines.append(f"- Command: `{markdown_cell(command_text)}`")
    if before_mt5:
        if packet.get("manual_run_start_marked"):
            effective_after = compact_list_text(
                packet.get("manual_run_start_effective_after_values")
            )
            note = "- Before MT5 run: manual run start is already marked"
            if effective_after:
                note += f" for {effective_after}"
            note += "; rerun the command only when starting a fresh MT5 batch."
            lines.append(note)
            lines.append(f"- Fresh MT5 batch mark command: `{markdown_cell(before_mt5)}`")
        else:
            lines.append(f"- Before MT5 run: `{markdown_cell(before_mt5)}`")
    if follow_up:
        lines.append(f"- Follow-up: `{markdown_cell(follow_up)}`")
    auto_launch_blocked = packet.get("auto_launch_blocked", "")
    auto_launch_blocked_reasons = packet.get("auto_launch_blocked_reasons")
    auto_launch_note = str(packet.get("auto_launch_note") or "")
    auto_launch_command = str(packet.get("auto_launch_command_text") or "")
    if auto_launch_blocked != "" or auto_launch_blocked_reasons:
        lines.append(f"- Auto launch blocked: {auto_launch_blocked}")
    if auto_launch_blocked_reasons:
        lines.append(
            f"- Auto launch blockers: {compact_list_text(auto_launch_blocked_reasons)}"
        )
    if auto_launch_note:
        lines.append(f"- Auto launch note: {auto_launch_note}")
    if auto_launch_command:
        command_label = "Auto launch command after closing MT5" if auto_launch_blocked else "Auto launch command"
        lines.append(f"- {command_label}: `{markdown_cell(auto_launch_command)}`")
    quick_start_status = str(packet.get("back_forward_quick_start_status") or "")
    if quick_start_status:
        lines.append(
            "- Back/Forward quick start: "
            f"status={quick_start_status}, "
            f"steps={packet.get('back_forward_quick_start_step_count', '')}, "
            f"waiting={packet.get('back_forward_quick_start_waiting_step_count', '')}, "
            f"current={packet.get('back_forward_quick_start_current_queue_step', '')}"
        )
        quick_start_collect = str(
            packet.get("back_forward_quick_start_collect_command_text") or ""
        )
        if quick_start_collect:
            lines.append(
                "- Back/Forward quick collect: "
                f"`{markdown_cell(quick_start_collect)}`"
            )
    completion_summary = str(packet.get("back_forward_completion_summary") or "")
    if completion_summary:
        lines.append(f"- Back/Forward completion: {completion_summary}")
        completion_collect = str(
            packet.get("back_forward_completion_collect_command_text") or ""
        )
        if completion_collect and completion_collect != str(
            packet.get("back_forward_quick_start_collect_command_text") or ""
        ):
            lines.append(
                "- Back/Forward completion collect: "
                f"`{markdown_cell(completion_collect)}`"
            )
    lines.append(
        "- Manual run start: "
        f"marked={packet.get('manual_run_start_marked', '')}, "
        f"this_run={packet.get('manual_run_start_marked_this_run', '')}, "
        f"preserved={packet.get('manual_run_start_preserved', '')}, "
        f"effective_after={compact_list_text(packet.get('manual_run_start_effective_after_values'))}"
    )
    verification = str(packet.get("next_operator_verification") or "")
    if verification:
        lines.append(f"- Verification: {verification}")
    operator_decision_verdict = str(packet.get("strategy_operator_decision_verdict") or "")
    if operator_decision_verdict:
        lines.append(
            "- Strategy operator decision: "
            f"verdict={operator_decision_verdict}, "
            f"status={packet.get('strategy_operator_decision_status', '')}, "
            f"adoptable={packet.get('strategy_operator_decision_adoptable', '')}, "
            f"blocker={packet.get('strategy_operator_decision_primary_blocker', '')}, "
            f"next={packet.get('strategy_operator_decision_next_action', '')}"
        )
    operator_decision_summary = str(packet.get("strategy_operator_decision_summary") or "")
    if operator_decision_summary:
        lines.append(f"- Strategy operator summary: {operator_decision_summary}")
    operator_decision_reason = str(packet.get("strategy_operator_decision_primary_reason") or "")
    if operator_decision_reason:
        lines.append(f"- Strategy operator reason: {operator_decision_reason}")
    operator_decision_command = str(packet.get("strategy_operator_decision_command_text") or "")
    if operator_decision_command:
        lines.append(f"- Strategy operator command: `{markdown_cell(operator_decision_command)}`")
    decision_status = str(packet.get("strategy_back_forward_decision_status") or "")
    if decision_status:
        lines.append(
            "- Strategy Back/Forward decision: "
            f"status={decision_status}, "
            f"adoptable={packet.get('strategy_back_forward_decision_adoptable', '')}, "
            f"next={packet.get('strategy_back_forward_decision_next_action', '')}"
        )
    decision_reason = str(packet.get("strategy_back_forward_decision_reason") or "")
    if decision_reason:
        lines.append(f"- Strategy Back/Forward reason: {decision_reason}")
    thresholds = packet.get("strategy_back_forward_decision_thresholds")
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
            lines.append("- Strategy Back/Forward thresholds: " + ", ".join(threshold_parts))
    decision_collect = str(packet.get("strategy_back_forward_decision_collect_command_text") or "")
    if decision_collect:
        lines.append(f"- Strategy Back/Forward collect: `{markdown_cell(decision_collect)}`")
    recovery_command = str(
        packet.get("strategy_back_forward_decision_sample_shortage_recovery_command_text") or ""
    )
    if recovery_command:
        lines.append(
            "- Strategy Back/Forward sample shortage recovery: "
            f"range_strategy={packet.get('strategy_back_forward_decision_sample_shortage_recovery_range_strategy', '')}, "
            f"suggested={packet.get('strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date', '')}"
            f"..{packet.get('strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date', '')}"
        )
        lines.append(f"- Strategy Back/Forward extended run: `{markdown_cell(recovery_command)}`")
    if auto_collect_watch:
        lines.append(
            "- Auto collect watcher: "
            f"status={auto_collect_watch.get('status', '')}, "
            f"execute_ready={auto_collect_watch.get('execute_ready', '')}, "
            f"ready_to_execute={auto_collect_watch.get('ready_to_execute', '')}, "
            f"selected={auto_collect_watch.get('selected_count', '')}, "
            f"waiting={auto_collect_watch.get('waiting_count', '')}"
        )
    packet_quick_input = packet.get("next_step_quick_input")
    if isinstance(packet_quick_input, dict) and packet_quick_input:
        lines.append(f"- Packet quick input: {compact_quick_input_text(packet_quick_input)}")
    run_sheet_next = packet.get("mt5_run_sheet_next_step")
    if isinstance(run_sheet_next, dict) and run_sheet_next:
        lines.append(
            "- MT5 run sheet next: "
            f"{run_sheet_next.get('queue_step', '')}; "
            f"{run_sheet_next.get('expert', '')}; "
            f"{run_sheet_next.get('symbol', '')}; "
            f"{run_sheet_next.get('period', '')}; "
            f"{run_sheet_next.get('dates', '')}; "
            f"Forward={run_sheet_next.get('forward', '')}; "
            f"Optimization={run_sheet_next.get('optimization', '')}; "
            f"Inputs={run_sheet_next.get('inputs', '')}; "
            f"Report={run_sheet_next.get('report', '')}"
        )
    back_forward_steps = packet.get("mt5_run_sheet_back_forward_steps")
    if isinstance(back_forward_steps, list) and back_forward_steps:
        lines.append(
            "- MT5 run sheet back/forward steps: "
            + ", ".join(
                str(step.get("queue_step", ""))
                for step in back_forward_steps
                if isinstance(step, dict)
            )
        )
    packet_step_summary = str(packet.get("next_step_operator_summary") or "")
    if packet_step_summary:
        lines.append(f"- Packet next step: {packet_step_summary}")
    packet_collect_filter = str(packet.get("next_step_collect_filter_summary") or "")
    if packet_collect_filter:
        lines.append(f"- Packet collect filter: {packet_collect_filter}")
    lines.extend(
        [
            (
                "- Queue: "
                f"status={packet.get('queue_status', '')}, "
                f"next_action={packet.get('queue_next_action', '')}, "
                f"progress={packet.get('progress_state', '')}"
            ),
            (
                "- Counts: "
                f"ready_to_collect={packet.get('ready_to_collect_count', '')}, "
                f"waiting={packet.get('waiting_count', '')}, "
                f"steps={packet.get('step_count', '')}"
            ),
            "",
        ]
    )
    return lines


def format_manual_auto_collect_watch_lines(watch: dict[str, Any]) -> list[str]:
    if not watch:
        watch = {}
    return [
        "## MT5 Manual Auto Collect Watch",
        "",
        f"- Exists: {watch.get('exists', '')}",
        f"- OK: {watch.get('ok', '')}",
        f"- Generated at: {watch.get('generated_at', '')}",
        f"- Path: {watch.get('path', '')}",
        f"- Status: {watch.get('status', '')}",
        f"- Next action: {watch.get('next_action', '')}",
        f"- Execute ready: {watch.get('execute_ready', '')}",
        f"- Ready to execute: {watch.get('ready_to_execute', '')}",
        f"- Ready for collect execute: {watch.get('ready_for_collect_execute', '')}",
        (
            "- Counts: "
            f"selected={watch.get('selected_count', '')}, "
            f"waiting={watch.get('waiting_count', '')}, "
            f"invalid={watch.get('invalid_count', '')}"
        ),
        f"- Queue: {watch.get('queue_path', '')}",
        f"- Collect output JSON: {watch.get('collect_output_json', '')}",
        f"- Collect dry-run: {watch.get('collect_dry_run_command_text', '')}",
        f"- Collect execute: {watch.get('collect_execute_command_text', '')}",
        (
            "- Queue launch: "
            f"status={watch.get('queue_launch_status', '')}, "
            f"next_action={watch.get('queue_launch_next_action', '')}, "
            f"blocked={watch.get('queue_launch_blocked', '')}, "
            f"blockers={compact_list_text(watch.get('queue_launch_blocked_reasons'))}"
        ),
        (
            "- Operator packet: "
            f"status={watch.get('operator_packet_status', '')}, "
            f"next_step={watch.get('operator_packet_next_queue_step', '')}"
        ),
        (
            "- Operator packet auto launch: "
            f"available={watch.get('operator_packet_auto_launch_command_available', '')}, "
            f"blocked={watch.get('operator_packet_auto_launch_blocked', '')}, "
            f"blockers={compact_list_text(watch.get('operator_packet_auto_launch_blocked_reasons'))}"
        ),
        (
            "- Operator packet auto launch note: "
            f"{watch.get('operator_packet_auto_launch_note', '')}"
        ),
        (
            "- Operator packet auto launch command after closing MT5: "
            f"{watch.get('operator_packet_auto_launch_command_text', '')}"
        ),
        (
            "- Operator decision: "
            f"verdict={watch.get('operator_packet_strategy_operator_decision_verdict', '')}, "
            f"status={watch.get('operator_packet_strategy_operator_decision_status', '')}, "
            f"adoptable={watch.get('operator_packet_strategy_operator_decision_adoptable', '')}, "
            f"blocker={watch.get('operator_packet_strategy_operator_decision_primary_blocker', '')}, "
            f"next={watch.get('operator_packet_strategy_operator_decision_next_action', '')}"
        ),
        (
            "- Operator decision command: "
            f"{watch.get('operator_packet_strategy_operator_decision_command_text', '')}"
        ),
        (
            "- Execution: "
            f"enabled={watch.get('execution_enabled', '')}, "
            f"attempted={watch.get('execution_attempted', '')}, "
            f"returncode={watch.get('execution_returncode', '')}, "
            f"status={watch.get('execution_status', '')}, "
            f"selected={watch.get('execution_selected_count', '')}, "
            f"next_action={watch.get('execution_next_action', '')}"
        ),
        "",
    ]


def markdown_empty_row(column_count: int, first: str = "-") -> str:
    cells = [first] + [""] * max(0, column_count - 1)
    return "| " + " | ".join(cells) + " |"


def format_pass_rows(pass_budget: object) -> list[str]:
    if not isinstance(pass_budget, dict) or pass_budget.get("available") is not True:
        return ["| available | False |"]
    rows = [
        ("available", pass_budget.get("available")),
        ("source", pass_budget.get("source", "")),
        ("generated_at", pass_budget.get("generated_at", "")),
        ("set_file", pass_budget.get("set_file", "")),
        ("set_file_exists", pass_budget.get("set_file_exists", "")),
        ("set_file_reestimated", pass_budget.get("set_file_reestimated", "")),
        ("optimized_input_count", pass_budget.get("optimized_input_count", "")),
        ("estimated_full_factorial_passes", pass_budget.get("estimated_full_factorial_passes", "")),
        ("executed_tester_xml_rows", recent_xml_rows_text(pass_budget.get("executed_tester_xml_rows", {}))),
        ("ratio_vs_full_factorial", ratio_mapping_text(pass_budget.get("ratio_vs_full_factorial", {}))),
        ("max_executed_tester_xml_rows", pass_budget.get("max_executed_tester_xml_rows", "")),
        ("full_factorial_progress_ratio", pass_budget.get("full_factorial_progress_ratio", "")),
        ("full_factorial_remaining_upper_bound", pass_budget.get("full_factorial_remaining_upper_bound", "")),
        ("full_factorial_complete_if_exhaustive", pass_budget.get("full_factorial_complete_if_exhaustive", "")),
        ("optimized_input_names", ", ".join(pass_budget.get("optimized_input_names", []))),
        ("progress_note", pass_budget.get("progress_note", "")),
        ("note", pass_budget.get("note", "")),
    ]
    rendered = []
    for key, value in rows:
        escaped = str(value).replace("|", "\\|")
        rendered.append(f"| {key} | {escaped} |")
    return rendered


def format_artifact_freshness_rows(freshness: object) -> list[str]:
    if not isinstance(freshness, dict):
        return ["| - | False |  |  |  |"]
    artifacts = freshness.get("artifacts") if isinstance(freshness.get("artifacts"), dict) else {}
    rows: list[str] = []
    for name in (
        "tester_run",
        "promotion_gate",
        "compile_status",
        "optimization_report",
        "next_action_run",
        "back_forward_run",
        "manual_test_queue",
        "manual_queue_launch",
        "manual_collect_run",
        "bridge_recovery_plan",
        "stable_candidate_report",
        "stable_candidate_recommendation",
        "stable_candidate_tester_run",
    ):
        item = artifacts.get(name)
        if not isinstance(item, dict):
            rows.append(f"| {name} | False |  |  |  |")
            continue
        path = str(item.get("path", "")).replace("|", "\\|")
        rows.append(
            f"| {name} | {item.get('exists')} | {item.get('fresh')} | "
            f"{item.get('age_seconds', '')} | {path} |"
        )
    return rows


def format_back_forward_step_rows(steps: object) -> list[str]:
    if not isinstance(steps, list) or not steps:
        return ["| - |  |  |  |  |  |  |  |  |  |  |  |  |  |  |"]
    rows: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        forward_mode = str(step.get("forward_mode", ""))
        effective_forward_mode = str(step.get("effective_forward_mode", "") or forward_mode)
        forward_mode_text = (
            f"{forward_mode}->{effective_forward_mode}"
            if effective_forward_mode and forward_mode and effective_forward_mode != forward_mode
            else forward_mode or effective_forward_mode
        )
        rows.append(
            f"| {step.get('label', '')} | {step.get('config', '')} | "
            f"{step.get('expert_parameters', '')} | {forward_mode_text} | "
            f"{step.get('report_name', '')} | "
            f"{step.get('run_json', '')} | {step.get('report_json', '')} | "
            f"{step.get('archive_preview_json', '')} | "
            f"{step.get('archive_preview_execution_ok', '')} | "
            f"{step.get('archive_preview_validation_ok', '')} | "
            f"{step.get('archive_preview_artifact_count', '')} | "
            f"{step.get('execution_ok', '')} | {step.get('execution_returncode', '')} | "
            f"{step.get('post_execution_validation_required', '')} | "
            f"{step.get('post_execution_validation_ok', '')} | "
            f"{compact_list_text(step.get('post_execution_validation_reasons'))} |"
        )
    return rows if rows else ["| - |  |  |  |  |  |  |  |  |  |  |  |  |  |  |"]


def format_manual_strategy_tester_rows(steps: object) -> list[str]:
    if not isinstance(steps, list) or not steps:
        return ["| - |  |  |  |  |  |  |  |  |  |  |  |  |  |  |"]
    rows: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        order = str(step.get("order", "")).replace("|", "\\|")
        label_value = str(step.get("label") or "")
        if not label_value:
            queue_id = str(step.get("queue_id") or "")
            step_label = str(step.get("step_label") or "")
            label_value = f"{queue_id}:{step_label}".strip(":")
        label = label_value.replace("|", "\\|")
        expert = str(step.get("expert", "")).replace("|", "\\|")
        symbol = str(step.get("symbol", "")).replace("|", "\\|")
        period = str(step.get("period", "")).replace("|", "\\|")
        model = str(step.get("model_label", "") or step.get("model", "")).replace("|", "\\|")
        dates = (
            f"{step.get('from_date', '')} -> {step.get('to_date', '')}"
            if step.get("from_date") or step.get("to_date")
            else str(step.get("dates") or "")
        ).replace("|", "\\|")
        forward = str(step.get("forward_label", "") or step.get("forward_mode_effective", "") or step.get("forward", "")).replace(
            "|", "\\|"
        )
        window = str(step.get("window_summary", "")).replace("|", "\\|")
        optimization = optimization_label_for_item(step).replace("|", "\\|")
        run_type = str(step.get("run_type", "")).replace("|", "\\|")
        expected_report = str(step.get("expected_report_artifact", "")).replace("|", "\\|")
        inputs = str(step.get("expert_parameters", "") or step.get("inputs", "")).replace("|", "\\|")
        report = str(step.get("report_name", "") or step.get("report", "")).replace("|", "\\|")
        fingerprint = str(step.get("step_fingerprint", "")).replace("|", "\\|")
        rows.append(
            f"| {order} | {label} | {expert} | {symbol} | {period} | {model} | "
            f"{dates} | {forward} | {window} | {optimization} | {run_type} | {expected_report} | {inputs} | {report} | "
            f"{fingerprint} |"
        )
    return rows if rows else ["| - |  |  |  |  |  |  |  |  |  |  |  |  |  |  |"]


def format_mt5_strategy_tester_pack_rows(steps: object) -> list[str]:
    if not isinstance(steps, list) or not steps:
        return ["| - |  |  |  |  |  |  |  |  |  |  |  |  |  |"]
    rows: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        rows.append(
            f"| {markdown_cell(step.get('order', ''))} | "
            f"{markdown_cell(step.get('purpose', ''))} | "
            f"{markdown_cell(step.get('step', ''))} | "
            f"{markdown_cell(step.get('expert', ''))} | "
            f"{markdown_cell(step.get('symbol', ''))} | "
            f"{markdown_cell(step.get('period', ''))} | "
            f"{markdown_cell(step.get('dates', ''))} | "
            f"{markdown_cell(step.get('forward', ''))} | "
            f"{markdown_cell(step.get('window_summary', ''))} | "
            f"{markdown_cell(optimization_label_for_item(step))} | "
            f"{markdown_cell(step.get('inputs', ''))} | "
            f"{markdown_cell(step.get('report', ''))} | "
            f"{markdown_cell(step.get('expected_report', ''))} | "
            f"{markdown_cell(step.get('step_fingerprint', ''))} |"
        )
    return rows if rows else ["| - |  |  |  |  |  |  |  |  |  |  |  |  |"]


def format_manual_test_queue_entry_rows(entries: object) -> list[str]:
    if not isinstance(entries, list) or not entries:
        return [markdown_empty_row(20)]
    rows: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        rows.append(
            f"| {entry.get('order', '')} | {markdown_cell(entry.get('id', ''))} | "
            f"{markdown_cell(entry.get('title', ''))} | "
            f"{entry.get('available', '')} | "
            f"{entry.get('current_for_execution', '')} | "
            f"{markdown_cell(entry.get('runner_generated_at', ''))} | "
            f"{markdown_cell(entry.get('promotion_generated_at', ''))} | "
            f"{markdown_cell(entry.get('current_promotion_generated_at', ''))} | "
            f"{markdown_cell(entry.get('promotion_decision', ''))} | "
            f"{markdown_cell(entry.get('current_promotion_decision', ''))} | "
            f"{entry.get('selected_action_current', '')} | "
            f"{markdown_cell(entry.get('gate_stale_reason', ''))} | "
            f"{markdown_cell(compact_list_text(entry.get('stale_reasons')))} | "
            f"{markdown_cell(entry.get('manual_run_start_after', ''))} | "
            f"{entry.get('step_count', '')} | {entry.get('collect_ready', '')} | "
            f"{markdown_cell(entry.get('collect_status', ''))} | "
            f"{markdown_cell(entry.get('collect_reason', ''))} | "
            f"{markdown_cell(entry.get('collect_next_action', ''))} | "
            f"{markdown_cell(entry.get('source_json', ''))} |"
        )
    return rows if rows else [markdown_empty_row(20)]


def format_manual_test_queue_stale_refresh_rows(entries: object) -> list[str]:
    if not isinstance(entries, list) or not entries:
        return [markdown_empty_row(4)]
    rows: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("stale_reasons"):
            continue
        rows.append(
            f"| {markdown_cell(entry.get('id', ''))} | "
            f"{markdown_cell(entry.get('source_json', ''))} | "
            f"{markdown_cell(compact_list_text(entry.get('stale_reasons')))} | "
            f"`{markdown_cell(entry.get('refresh_command_text', ''))}` |"
        )
    return rows if rows else [markdown_empty_row(4)]


def format_manual_test_queue_target_rows(targets: object) -> list[str]:
    if not isinstance(targets, list) or not targets:
        return [markdown_empty_row(20)]
    rows: list[str] = []
    for target in targets:
        if not isinstance(target, dict):
            continue
        rows.append(
            f"| {markdown_cell(target.get('order', ''))} | "
            f"{markdown_cell(target.get('purpose', ''))} | "
            f"{markdown_cell(target.get('queue_id', ''))}/{markdown_cell(target.get('step_label', ''))} | "
            f"{markdown_cell(target.get('symbol', ''))} | "
            f"{markdown_cell(target.get('period', ''))} | "
            f"{markdown_cell(target.get('dates', ''))} | "
            f"{markdown_cell(target.get('forward', ''))} | "
            f"{markdown_cell(optimization_label_for_item(target))} | "
            f"{markdown_cell(target.get('run_type', ''))} | "
            f"{markdown_cell(target.get('expected_report_artifact', ''))} | "
            f"{markdown_cell(target.get('report_expectation_note', ''))} | "
            f"{markdown_cell(target.get('inputs', ''))} | "
            f"{markdown_cell(target.get('report', ''))} | "
            f"{markdown_cell(target.get('start_after', ''))} | "
            f"{markdown_cell(target.get('collect_modified_after', ''))} | "
            f"{markdown_cell(target.get('collect_status', ''))} | "
            f"{markdown_cell(target.get('step_report_status', ''))} | "
            f"{markdown_cell(target.get('launch_needed', ''))} | "
            f"{markdown_cell(target.get('auto_launch_kind', ''))} | "
            f"{markdown_cell(target.get('step_fingerprint', ''))} |"
        )
    return rows if rows else [markdown_empty_row(20)]


def format_manual_test_queue_operation_card_rows(cards: object) -> list[str]:
    if not isinstance(cards, list) or not cards:
        return [markdown_empty_row(14)]
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
            f"{markdown_cell(optimization_label_for_item(card))} | "
            f"{markdown_cell(card.get('inputs', ''))} | "
            f"{markdown_cell(card.get('report', ''))} | "
            f"{markdown_cell(card.get('collect_status', ''))} | "
            f"{markdown_cell(card.get('step_fingerprint', ''))} |"
        )
    return rows if rows else [markdown_empty_row(14)]


def format_manual_test_queue_next_step_row(step: object) -> str:
    if not isinstance(step, dict) or not step:
        return "| - | No launch-needed Strategy Tester step remains. |  |  |  |  |  |  |  |  |  |  |  |"
    return (
        f"| {markdown_cell(step.get('order', ''))} | "
        f"{markdown_cell(step.get('queue_id', ''))}/{markdown_cell(step.get('step_label', ''))} | "
        f"{markdown_cell(step.get('symbol', ''))} | "
        f"{markdown_cell(step.get('period', ''))} | "
        f"{markdown_cell(step.get('dates', ''))} | "
        f"{markdown_cell(step.get('forward', ''))} | "
        f"{markdown_cell(optimization_label_for_item(step))} | "
        f"{markdown_cell(step.get('run_type', ''))} | "
        f"{markdown_cell(step.get('step_report_status', ''))} | "
        f"{markdown_cell(step.get('launch_command_kind', ''))} | "
        f"{markdown_cell(step.get('inputs', ''))} | "
        f"{markdown_cell(step.get('report', ''))} | "
        f"{markdown_cell(step.get('step_fingerprint', ''))} |"
    )


def manual_test_queue_entry_executable(entry: dict[str, Any]) -> bool:
    return not (
        entry.get("available") is False
        or entry.get("current_for_execution") is False
        or bool(entry.get("stale_reasons"))
    )


def manual_test_queue_steps(entries: object) -> list[dict[str, Any]]:
    if not isinstance(entries, list):
        return []
    steps: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if not manual_test_queue_entry_executable(entry):
            continue
        entry_steps = entry.get("steps") if isinstance(entry.get("steps"), list) else []
        for step in entry_steps:
            if not isinstance(step, dict):
                continue
            steps.append({**step, "label": f"{entry.get('id', '')}:{step.get('label', '')}"})
    return steps


def manual_test_queue_strategy_purpose(queue_id: str, step_label: str) -> str:
    if queue_id == "back_forward" and step_label == "backtest":
        return "Backtest"
    if queue_id == "back_forward" and step_label == "forward":
        return "Forward Test"
    if queue_id == "score_weight_sell":
        return "SELL Score Sample"
    if queue_id == "score_weight_buy":
        return "BUY Score Sample"
    return step_label or queue_id


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


def manual_test_queue_strategy_targets(
    targets: object,
    checklist: object,
    entries: object,
) -> list[dict[str, Any]]:
    if isinstance(targets, list) and targets:
        rows: list[dict[str, Any]] = []
        for target in targets:
            if not isinstance(target, dict):
                continue
            rows.append(
                {
                    "order": target.get("order", ""),
                    "purpose": target.get("purpose", ""),
                    "queue_id": target.get("queue_id", ""),
                    "step_label": target.get("step_label", ""),
                    "symbol": target.get("symbol", ""),
                    "period": target.get("period", ""),
                    "dates": target.get("dates", ""),
                    "forward": target.get("forward", ""),
                    "optimization": target.get("optimization", ""),
                    "optimization_label": optimization_label_for_item(target),
                    "optimization_enabled": target.get("optimization_enabled", ""),
                    "run_type": target.get("run_type", ""),
                    "expected_report_artifact": target.get("expected_report_artifact", ""),
                    "report_expectation_note": target.get("report_expectation_note", ""),
                    "inputs": target.get("inputs", ""),
                    "report": target.get("report", ""),
                    "start_after": target.get("start_after", ""),
                    "collect_modified_after": target.get("collect_modified_after", ""),
                    "collect_csv_count": target.get("collect_csv_count", ""),
                    "collect_status": target.get("collect_status", ""),
                    "collect_next_action": target.get("collect_next_action", ""),
                    "step_report_status": target.get("step_report_status", ""),
                    "step_report_ready": target.get("step_report_ready", ""),
                    "step_collect_ready": target.get("step_collect_ready", ""),
                    "step_blocking_reason": target.get("step_blocking_reason", ""),
                    "selected_report": target.get("selected_report", ""),
                    "launch_needed": target.get("launch_needed", ""),
                    "auto_launch_kind": target.get("auto_launch_kind", ""),
                    "step_fingerprint": target.get("step_fingerprint", ""),
                    "step_config_fingerprint": target.get("step_config_fingerprint", ""),
                    "step_run_fingerprint": target.get("step_run_fingerprint", ""),
                    "expected_artifacts": (
                        target.get("expected_artifacts")
                        if isinstance(target.get("expected_artifacts"), dict)
                        else {}
                    ),
                }
            )
        if rows:
            return rows
    entry_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(entries, list):
        entry_by_id = {
            str(entry.get("id", "")): entry for entry in entries if isinstance(entry, dict)
        }
    if not isinstance(checklist, list):
        return []
    rows = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        queue_id = str(item.get("queue_id") or "")
        step_label = str(item.get("step_label") or "")
        entry = entry_by_id.get(queue_id, {})
        rows.append(
            {
                "order": item.get("order", ""),
                "purpose": manual_test_queue_strategy_purpose(queue_id, step_label),
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
                "expected_report_artifact": item.get("expected_report_artifact", ""),
                "report_expectation_note": item.get("report_expectation_note", ""),
                "inputs": item.get("inputs", ""),
                "report": item.get("report", ""),
                "start_after": item.get("manual_run_start_after", ""),
                "collect_modified_after": entry.get("collect_modified_after", ""),
                "collect_csv_count": entry.get("collect_csv_count", ""),
                "collect_status": entry.get("collect_status", ""),
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
                "expected_artifacts": (
                    item.get("expected_artifacts")
                    if isinstance(item.get("expected_artifacts"), dict)
                    else {}
                ),
            }
        )
    return rows


def manual_test_queue_execution_checklist(
    checklist: object,
    entries: object,
) -> list[dict[str, Any]]:
    entry_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(entries, list):
        entry_by_id = {
            str(entry.get("id", "")): entry for entry in entries if isinstance(entry, dict)
        }
    if isinstance(checklist, list) and checklist:
        rows: list[dict[str, Any]] = []
        for item in checklist:
            if not isinstance(item, dict):
                continue
            entry = entry_by_id.get(str(item.get("queue_id", "")))
            if entry is not None and not manual_test_queue_entry_executable(entry):
                continue
            rows.append(
                {
                    "order": item.get("order", ""),
                    "queue_id": item.get("queue_id", ""),
                    "step_label": item.get("step_label", ""),
                    "config": item.get("config", ""),
                    "mt5_config": item.get("mt5_config", ""),
                    "expert": item.get("expert", ""),
                    "symbol": item.get("symbol", ""),
                    "period": item.get("period", ""),
                    "model": item.get("model", ""),
                    "dates": item.get("dates", ""),
                    "forward": item.get("forward", ""),
                    "optimization": item.get("optimization", ""),
                    "optimization_label": optimization_label_for_item(item),
                    "optimization_enabled": item.get("optimization_enabled", ""),
                    "run_type": item.get("run_type", ""),
                    "expected_report_artifact": item.get("expected_report_artifact", ""),
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
                    "collect_modified_after": item.get("collect_modified_after", ""),
                    "step_fingerprint": item.get("step_fingerprint", ""),
                    "step_config_fingerprint": item.get("step_config_fingerprint", ""),
                    "step_run_fingerprint": item.get("step_run_fingerprint", ""),
                    "expected_artifacts": (
                        item.get("expected_artifacts")
                        if isinstance(item.get("expected_artifacts"), dict)
                        else {}
                    ),
                    "launch_command_kind": item.get("launch_command_kind", ""),
                    "launch_command_text": item.get("launch_command_text", ""),
                    "launch_error": item.get("launch_error", ""),
                    "direct_config_reason": item.get("direct_config_reason", ""),
                }
            )
        if rows:
            return rows
    if not isinstance(entries, list):
        return []
    rows = []
    order = 1
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if not manual_test_queue_entry_executable(entry):
            continue
        entry_steps = entry.get("steps") if isinstance(entry.get("steps"), list) else []
        for step in entry_steps:
            if not isinstance(step, dict):
                continue
            dates = (
                f"{step.get('from_date', '')} -> {step.get('to_date', '')}"
                if step.get("from_date") or step.get("to_date")
                else ""
            )
            rows.append(
                {
                    "order": order,
                    "queue_id": entry.get("id", ""),
                    "step_label": step.get("label", ""),
                    "config": step.get("config", ""),
                    "mt5_config": "",
                    "expert": step.get("expert", ""),
                    "symbol": step.get("symbol", ""),
                    "period": step.get("period", ""),
                    "model": step.get("model_label") or step.get("model", ""),
                    "dates": dates,
                    "forward": step.get("forward_label") or step.get("forward_mode_effective", ""),
                    "optimization": step.get("optimization", ""),
                    "optimization_label": optimization_label_for_item(step),
                    "optimization_enabled": step.get("optimization_enabled", ""),
                    "run_type": step.get("run_type", ""),
                    "expected_report_artifact": step.get("expected_report_artifact", ""),
                    "report_expectation_note": step.get("report_expectation_note", ""),
                    "step_report_status": "",
                    "step_report_ready": "",
                    "step_collect_ready": "",
                    "step_blocking_reason": "",
                    "selected_report": "",
                    "launch_needed": "",
                    "inputs": step.get("expert_parameters", ""),
                    "report": step.get("report_name", ""),
                    "manual_run_start_after": entry.get("manual_run_start_after", ""),
                    "collect_modified_after": entry.get("collect_modified_after", ""),
                    "step_fingerprint": step.get("step_fingerprint", ""),
                    "step_config_fingerprint": step.get("step_config_fingerprint", ""),
                    "step_run_fingerprint": step.get("step_run_fingerprint", ""),
                    "expected_artifacts": (
                        step.get("expected_artifacts")
                        if isinstance(step.get("expected_artifacts"), dict)
                        else {}
                    ),
                    "launch_command_kind": "",
                    "launch_command_text": "",
                    "launch_error": "",
                    "direct_config_reason": "",
                }
            )
            order += 1
    return rows


def format_manual_test_queue_checklist_rows(checklist: object) -> list[str]:
    if not isinstance(checklist, list) or not checklist:
        return ["| - |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |"]
    rows: list[str] = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        done = "[x]" if manual_test_queue_checklist_item_done(item) else "[ ]"
        rows.append(
            f"| {done} | {markdown_cell(item.get('order', ''))} | "
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
            f"{markdown_cell(item.get('launch_needed', ''))} | "
            f"{markdown_cell(item.get('inputs', ''))} | "
            f"{markdown_cell(item.get('report', ''))} | "
            f"{markdown_cell(item.get('manual_run_start_after', ''))} | "
            f"{markdown_cell(item.get('step_fingerprint', ''))} |"
        )
    return rows if rows else ["| - |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |"]


def manual_test_queue_checklist_item_done(item: dict[str, Any]) -> bool:
    return boolish_true(item.get("step_report_ready")) or boolish_true(item.get("step_collect_ready"))


def boolish_true(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


MT5_QUICK_INPUT_FIELDS = (
    ("purpose", "Purpose"),
    ("queue_step", "Queue step"),
    ("expert", "Expert"),
    ("symbol", "Symbol"),
    ("period", "Period"),
    ("model", "Model"),
    ("from_date", "From"),
    ("to_date", "To"),
    ("forward", "Forward"),
    ("forward_mode", "ForwardMode"),
    ("optimization_label", "Optimization"),
    ("inputs", "Inputs"),
    ("report", "Report"),
    ("expected_report_artifact", "Expected output"),
    ("manual_run_start_after", "Start after"),
    ("step_fingerprint", "Run fingerprint"),
    ("launch_kind", "Launch kind"),
)


def split_quick_input_dates(dates: object) -> tuple[str, str]:
    text = str(dates or "").strip()
    if "->" not in text:
        return "", ""
    start, end = text.split("->", 1)
    return start.strip(), end.strip()


def mt5_quick_input_from_step(step: object) -> dict[str, Any]:
    if not isinstance(step, dict) or not step:
        return {}
    queue_id = str(step.get("queue_id") or "")
    step_label = str(step.get("step_label") or "")
    from_date = str(step.get("from_date") or "")
    to_date = str(step.get("to_date") or "")
    if not (from_date or to_date):
        from_date, to_date = split_quick_input_dates(step.get("dates"))
    return {
        "purpose": step.get("purpose", ""),
        "queue_step": f"{queue_id}/{step_label}".strip("/"),
        "expert": step.get("expert", ""),
        "symbol": step.get("symbol", ""),
        "period": step.get("period", ""),
        "model": step.get("model", ""),
        "from_date": from_date,
        "to_date": to_date,
        "dates": step.get("dates", ""),
        "forward": step.get("forward", ""),
        "forward_mode": step.get("forward_mode", ""),
        "optimization_label": optimization_label_for_item(step),
        "inputs": step.get("inputs", ""),
        "report": step.get("report", ""),
        "expected_report_artifact": step.get("expected_report_artifact", ""),
        "manual_run_start_after": step.get("manual_run_start_after", ""),
        "step_fingerprint": step.get("step_fingerprint", ""),
        "step_config_fingerprint": step.get("step_config_fingerprint", ""),
        "step_run_fingerprint": step.get("step_run_fingerprint", ""),
        "launch_kind": step.get("launch_command_kind", ""),
    }


def format_mt5_quick_input_rows(quick_input: object) -> list[str]:
    if not isinstance(quick_input, dict) or not quick_input:
        return ["| - |  |"]
    rows: list[str] = []
    for key, label in MT5_QUICK_INPUT_FIELDS:
        value = quick_input.get(key, "")
        if value in (None, "") and key == "forward_mode":
            continue
        rows.append(f"| {markdown_cell(label)} | {markdown_cell(value)} |")
    return rows if rows else ["| - |  |"]


def compact_quick_input_text(quick_input: object) -> str:
    if not isinstance(quick_input, dict) or not quick_input:
        return ""
    parts = []
    for key, label in (
        ("queue_step", "step"),
        ("purpose", "purpose"),
        ("expert", "expert"),
        ("symbol", "symbol"),
        ("period", "period"),
        ("dates", "dates"),
        ("forward", "forward"),
        ("inputs", "inputs"),
        ("report", "report"),
    ):
        value = quick_input.get(key, "")
        if key == "dates" and value in ("", None):
            from_date = quick_input.get("from_date", "")
            to_date = quick_input.get("to_date", "")
            value = f"{from_date} -> {to_date}" if from_date or to_date else ""
        if value not in ("", None, [], {}):
            parts.append(f"{label}={value}")
    return ", ".join(parts)


def format_manual_test_queue_launch_rows(checklist: object) -> list[str]:
    if not isinstance(checklist, list) or not checklist:
        return ["| - |  |  |  |  |  |  |"]
    rows: list[str] = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        command_text = str(item.get("launch_command_text") or "")
        if command_text and item.get("launch_command_kind") == "runner_execute":
            command_text = f"runner execute: {command_text}"
        if not command_text:
            command_text = f"launch unavailable: {item.get('launch_error', '')}"
        rows.append(
            f"| {markdown_cell(item.get('order', ''))} | "
            f"{markdown_cell(item.get('queue_id', ''))}/{markdown_cell(item.get('step_label', ''))} | "
            f"{markdown_cell(item.get('launch_needed', ''))} | "
            f"{markdown_cell(item.get('launch_command_kind', ''))} | "
            f"{markdown_cell(item.get('config', ''))} | "
            f"{markdown_cell(item.get('mt5_config', ''))} | "
            f"`{markdown_cell(command_text)}` |"
        )
    return rows if rows else ["| - |  |  |  |  |  |  |"]


def format_status_watch_manual_queue_checklist_lines(checklist: object) -> list[str]:
    if not isinstance(checklist, list) or not checklist:
        return ["- Watch manual test queue checklist: "]
    lines: list[str] = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        lines.append(
            "- Watch manual test queue checklist "
            f"{item.get('order', '')}: "
            f"{item.get('queue_id', '')}/{item.get('step_label', '')}, "
            f"{item.get('symbol', '')} {item.get('period', '')}, "
            f"forward={item.get('forward', '')}, "
            f"step_report={item.get('step_report_status', '')}, "
            f"launch_needed={item.get('launch_needed', '')}, "
            f"inputs={item.get('inputs', '')}, "
            f"report={item.get('report', '')}, "
            f"start_after={item.get('manual_run_start_after', '')}"
        )
    return lines if lines else ["- Watch manual test queue checklist: "]


def format_status_watch_manual_queue_target_lines(targets: object) -> list[str]:
    if not isinstance(targets, list) or not targets:
        return ["- Watch manual test queue targets: "]
    lines: list[str] = []
    for target in targets:
        if not isinstance(target, dict):
            continue
        lines.append(
            "- Watch manual test queue target "
            f"{target.get('order', '')}: "
            f"{target.get('purpose', '')}, "
            f"{target.get('queue_id', '')}/{target.get('step_label', '')}, "
            f"forward={target.get('forward', '')}, "
            f"step_report={target.get('step_report_status', '')}, "
            f"launch_needed={target.get('launch_needed', '')}, "
            f"inputs={target.get('inputs', '')}, "
            f"report={target.get('report', '')}, "
            f"collect_status={target.get('collect_status', '')}, "
            f"auto_launch={target.get('auto_launch_kind', '')}"
        )
    return lines if lines else ["- Watch manual test queue targets: "]


def format_status_watch_manual_queue_operation_card_lines(cards: object) -> list[str]:
    if not isinstance(cards, list) or not cards:
        return ["- Watch manual test queue operation cards: "]
    lines: list[str] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        next_mark = "next" if card.get("is_next") is True else ""
        lines.append(
            "- Watch manual test queue operation card "
            f"{card.get('order', '')}: "
            f"{next_mark}, "
            f"action={card.get('action', '')}, "
            f"purpose={card.get('purpose', '')}, "
            f"{card.get('queue_id', '')}/{card.get('step_label', '')}, "
            f"forward={card.get('forward', '')}, "
            f"inputs={card.get('inputs', '')}, "
            f"report={card.get('report', '')}, "
            f"collect_status={card.get('collect_status', '')}"
        )
    return lines if lines else ["- Watch manual test queue operation cards: "]


def format_manual_collect_run_rows(entries: object, *, kind: str) -> list[str]:
    if not isinstance(entries, list) or not entries:
        if kind == "execution":
            return ["| - |  |  |  |  |  |"]
        return ["| - |  |  |  |  |  |  |  |"]
    rows: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if kind == "execution":
            rows.append(
                f"| {markdown_cell(entry.get('id', ''))} | "
                f"{markdown_cell(entry.get('status', ''))} | "
                f"{markdown_cell(entry.get('returncode', ''))} | "
                f"{markdown_cell(entry.get('output_json', ''))} | "
                f"{markdown_cell(entry.get('output_md', ''))} | "
                f"{markdown_cell(entry.get('reason', ''))} |"
            )
            continue
        rows.append(
            f"| {markdown_cell(entry.get('id', ''))} | "
            f"{markdown_cell(entry.get('title', ''))} | "
            f"{markdown_cell(entry.get('runner_generated_at', ''))} | "
            f"{markdown_cell(entry.get('promotion_generated_at', ''))} | "
            f"{markdown_cell(entry.get('promotion_decision', ''))} | "
            f"{markdown_cell(entry.get('collect_status', ''))} | "
            f"{markdown_cell(entry.get('collect_modified_after', ''))} | "
            f"{markdown_cell(entry.get('skip_reason', ''))} | "
            f"{markdown_cell(entry.get('collect_reason', ''))} |"
        )
    if rows:
        return rows
    if kind == "execution":
        return ["| - |  |  |  |  |  |"]
    return ["| - |  |  |  |  |  |  |  |"]


def format_manual_collect_step_audit_rows(entries: object) -> list[str]:
    if not isinstance(entries, list) or not entries:
        return ["| - |  |  |  |  |  |  |  |  |  |  |  |"]
    rows: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        rows.append(
            f"| {markdown_cell(entry.get('order', ''))} | "
            f"{markdown_cell(entry.get('queue_step', ''))} | "
            f"{markdown_cell(entry.get('purpose', ''))} | "
            f"{markdown_cell(entry.get('status', ''))} | "
            f"{markdown_cell(entry.get('report_ready', ''))} | "
            f"{markdown_cell(entry.get('collect_ready', ''))} | "
            f"{markdown_cell(entry.get('launch_needed', ''))} | "
            f"{markdown_cell(entry.get('expected_report_artifact', ''))} | "
            f"{markdown_cell(entry.get('report', ''))} | "
            f"{markdown_cell(entry.get('agent_csv_modified_after', ''))} | "
            f"{markdown_cell(entry.get('step_fingerprint', ''))} | "
            f"{markdown_cell(entry.get('blocking_reason', ''))} |"
        )
    return rows if rows else ["| - |  |  |  |  |  |  |  |  |  |  |  |"]


def format_manual_collect_handoff(summary: dict[str, Any]) -> list[str]:
    handoff = (
        summary.get("operator_handoff")
        if isinstance(summary.get("operator_handoff"), dict)
        else {}
    )
    if not handoff:
        return []
    next_step = (
        handoff.get("next_mt5_step")
        if isinstance(handoff.get("next_mt5_step"), dict)
        else {}
    )
    lines = [
        "### MT5 Manual Collect Handoff",
        "",
        f"- State: {handoff.get('state', '')}",
        f"- Ready entries: {compact_list_text(handoff.get('ready_ids'))}",
        f"- Waiting entries: {compact_list_text(handoff.get('waiting_ids'))}",
        f"- Invalid entries: {compact_list_text(handoff.get('invalid_ids'))}",
        (
            f"- Step progress: steps={handoff.get('queue_step_count', '')}, "
            f"report_ready={handoff.get('queue_step_report_ready_count', '')}, "
            f"waiting={handoff.get('queue_step_waiting_report_count', '')}, "
            f"launch_needed={handoff.get('queue_step_launch_needed_count', '')}"
        ),
        f"- Dry-run command: {handoff.get('dry_run_command_text', '')}",
        f"- Execute command: {handoff.get('execute_command_text', '')}",
    ]
    if next_step:
        lines.extend(
            [
                (
                    f"- Next MT5 step: {next_step.get('queue_id', '')}/"
                    f"{next_step.get('step_label', '')}"
                ),
                (
                    "- Strategy Tester settings: "
                    f"Symbol={next_step.get('symbol', '')}, "
                    f"Period={next_step.get('period', '')}, "
                    f"Dates={next_step.get('dates', '')}, "
                    f"Forward={next_step.get('forward', '')}"
                ),
                (
                    f"- Inputs={next_step.get('inputs', '')}, "
                    f"Report={next_step.get('report', '')}, "
                    f"Expected={next_step.get('expected_report_artifact', '')}"
                ),
                f"- Report condition: {next_step.get('step_report_status', '')}",
            ]
        )
    return lines + [""]


def format_mt5_operator_handoff_lines(handoff: object) -> list[str]:
    if not isinstance(handoff, dict) or not handoff:
        return []
    next_step = (
        handoff.get("next_mt5_step")
        if isinstance(handoff.get("next_mt5_step"), dict)
        else {}
    )
    quick_input = (
        handoff.get("quick_input")
        if isinstance(handoff.get("quick_input"), dict)
        else mt5_quick_input_from_step(next_step)
    )
    lines = [
        "## MT5 Operator Handoff",
        "",
        f"- State: {handoff.get('state', '')}",
        f"- Recommended path: {handoff.get('recommended_path', '')}",
        f"- Manual Strategy Tester available: {handoff.get('manual_strategy_tester_available', '')}",
        f"- Terminal running: {handoff.get('terminal_running', '')}",
        f"- Auto launch ready: {handoff.get('auto_launch_ready', '')}",
        f"- Auto launch status: {handoff.get('auto_launch_status', '')}",
        f"- Auto launch blocked by running terminal: {handoff.get('auto_launch_blocked_by_running_terminal', '')}",
        (
            "- Auto launch blockers: "
            f"{auto_launch_blockers_text(
                handoff.get('auto_launch_blockers'),
                blocked_by_running_terminal=bool(
                    handoff.get('auto_launch_blocked_by_running_terminal')
                ),
            )}"
        ),
        (
            f"- Manual queue: status={handoff.get('manual_queue_status', '')}, "
            f"progress={handoff.get('manual_queue_progress_state', '')}, "
            f"next_action={handoff.get('manual_queue_next_action', '')}"
        ),
        (
            "- Manual queue steps: "
            f"report_ready={compact_list_text(handoff.get('manual_queue_step_report_ready_ids'))}, "
            f"collect_ready={compact_list_text(handoff.get('manual_queue_step_collect_ready_ids'))}, "
            f"waiting_report={compact_list_text(handoff.get('manual_queue_step_waiting_report_ids'))}, "
            f"launch_needed={compact_list_text(handoff.get('manual_queue_step_launch_needed_ids'))}"
        ),
        f"- Manual collect check: {handoff.get('manual_queue_collect_check_command_text', '')}",
        f"- Manual collect: status={handoff.get('manual_collect_status', '')}, next_action={handoff.get('manual_collect_next_action', '')}",
        f"- Next step summary: {handoff.get('next_step_operator_summary', '')}",
        f"- Collect filter: {handoff.get('next_step_collect_filter_summary', '')}",
    ]
    if next_step:
        lines.extend(
            [
                (
                    f"- Next MT5 step: {next_step.get('queue_id', '')}/"
                    f"{next_step.get('step_label', '')}"
                ),
                (
                    "- Strategy Tester settings: "
                    f"Symbol={next_step.get('symbol', '')}, "
                    f"Period={next_step.get('period', '')}, "
                    f"Dates={next_step.get('dates', '')}, "
                    f"Forward={next_step.get('forward', '')}"
                ),
                (
                    f"- Inputs={next_step.get('inputs', '')}, "
                    f"Report={next_step.get('report', '')}, "
                    f"Expected={next_step.get('expected_report_artifact', '')}"
                ),
            ]
        )
    if quick_input:
        lines.extend(
            [
                "### MT5 Quick Input",
                "",
                "| field | value |",
                "|---|---|",
                *format_mt5_quick_input_rows(quick_input),
                "",
            ]
        )
    collect_dry_run = str(handoff.get("manual_collect_dry_run_command_text") or "")
    collect_execute = str(handoff.get("manual_collect_execute_command_text") or "")
    collect_execute_and_refresh = str(
        handoff.get("manual_collect_execute_and_refresh_analysis_command_text") or ""
    )
    collect_execute_and_refresh_all = str(
        handoff.get("manual_collect_execute_and_refresh_all_command_text") or ""
    )
    if collect_dry_run:
        lines.append(f"- Collect dry-run command: {collect_dry_run}")
    if collect_execute:
        lines.append(f"- Collect execute command: {collect_execute}")
    if collect_execute_and_refresh:
        lines.append(f"- Collect execute + analysis command: {collect_execute_and_refresh}")
    if collect_execute_and_refresh_all:
        lines.append(f"- Collect execute + full analysis command: {collect_execute_and_refresh_all}")
    lines.extend(
        [
            f"- Bridge required for standalone tester: {handoff.get('bridge_required_for_standalone_tester', '')}",
            f"- Bridge ready for MT5 validation: {handoff.get('bridge_ready_for_mt5_validation', '')}",
            f"- Bridge status: {handoff.get('bridge_status', '')}",
        ]
    )
    if handoff.get("bridge_note"):
        lines.append(f"- Bridge note: {handoff.get('bridge_note', '')}")
    return lines + [""]


def format_back_forward_prerequisite_rows(prerequisites: object) -> list[str]:
    if not isinstance(prerequisites, dict) or not prerequisites:
        return ["| - |  |  |  |  |  |"]
    rendered: list[str] = []
    for group_name in ("experts", "tester_configs", "tester_sets", "tester_config_references"):
        rows = prerequisites.get(group_name)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            display_name = str(row.get("name", "")).replace("|", "\\|")
            if group_name == "tester_config_references" and row.get("expert_parameters"):
                expert_parameters = str(row.get("expert_parameters", "")).replace("|", "\\|")
                display_name = f"{display_name} -> {expert_parameters}"
            synced_or_source = row.get("synced", row.get("source_synced", ""))
            rendered.append(
                f"| {row.get('kind', group_name)} | {display_name} | {row.get('status', '')} | "
                f"{row.get('ready', '')} | {synced_or_source} | {row.get('compiled_fresh', '')} |"
            )
    return rendered if rendered else ["| - |  |  |  |  |  |"]


def format_back_forward_comparison_rows(comparison: object) -> list[str]:
    if not isinstance(comparison, dict):
        return ["| - |  |  |  |  |  |  |  |  |  |  |  |  |"]
    rows = comparison.get("rows") if isinstance(comparison.get("rows"), list) else []
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


def format_post_execution_artifact_lines(label: str, artifact: object) -> list[str]:
    if not isinstance(artifact, dict) or not artifact:
        return []
    archive_csv = (
        artifact.get("agent_csv_archive") if isinstance(artifact.get("agent_csv_archive"), dict) else {}
    )
    tester = artifact.get("tester_run") if isinstance(artifact.get("tester_run"), dict) else {}
    forward = artifact.get("forward_report") if isinstance(artifact.get("forward_report"), dict) else {}
    optimization = artifact.get("optimization") if isinstance(artifact.get("optimization"), dict) else {}
    recommendation = artifact.get("recommendation") if isinstance(artifact.get("recommendation"), dict) else {}
    lines: list[str] = []
    if artifact.get("evidence_role"):
        lines.append(
            f"- {label} post evidence role: {artifact.get('evidence_role')} "
            f"diagnostic_only={artifact.get('diagnostic_only', '')} "
            f"promotion_evidence={artifact.get('promotion_evidence', '')}"
        )
        if artifact.get("evidence_note"):
            lines.append(f"- {label} post evidence note: {artifact.get('evidence_note')}")
    if archive_csv:
        lines.append(
            f"- {label} post Agent CSV archive: exists={archive_csv.get('exists', '')} "
            f"ok={archive_csv.get('ok', '')} execute={archive_csv.get('execute', '')} "
            f"count={archive_csv.get('count', '')} run_id={archive_csv.get('run_id', '')} "
            f"source_rows={archive_csv.get('close_rows', '')}"
        )
    if tester:
        lines.append(
            f"- {label} post tester run: exists={tester.get('exists', '')} ok={tester.get('ok', '')} "
            f"blocked={tester.get('blocked', '')} source_time_blocked={tester.get('source_time_blocked', '')} "
            f"report_fallback_blocked={tester.get('report_fallback_blocked', '')} "
            f"elapsed={tester.get('terminal_elapsed_seconds', '')}"
        )
    if forward:
        lines.append(
            f"- {label} post forward report: exists={forward.get('exists', '')} ok={forward.get('ok', '')} "
            f"closed={forward.get('closed', '')} pf={forward.get('pf', '')} "
            f"avg_price_r={forward.get('avg_price_r', '')} ready_for_demo_review={forward.get('ready_for_demo_review', '')}"
        )
    if optimization:
        lines.append(
            f"- {label} post optimization: exists={optimization.get('exists', '')} "
            f"closed={optimization.get('closed', '')} pf={optimization.get('pf', '')} "
            f"avg_price_r={optimization.get('avg_price_r', '')} "
            f"back_rows={optimization.get('back_rows', '')} forward_rows={optimization.get('forward_rows', '')}"
        )
    if recommendation:
        lines.append(
            f"- {label} post recommendation: exists={recommendation.get('exists', '')} "
            f"adoptable={recommendation.get('adoptable', '')} "
            f"next_set={recommendation.get('next_set', '')} skip_reason={recommendation.get('skip_reason', '')}"
        )
    return lines


def format_post_execution_validation_lines(validation: object) -> list[str]:
    if not isinstance(validation, dict) or not validation:
        return []
    lines: list[str] = []
    for name, result in validation.items():
        if not isinstance(result, dict):
            continue
        lines.append(
            f"- {name} post validation: required={result.get('required', '')} "
            f"ok={result.get('ok', '')} reasons={compact_list_text(result.get('reasons'))} "
            f"output_json={result.get('output_json', '')}"
        )
    return lines


def format_planned_output_lines(label: str, outputs: object) -> list[str]:
    if not isinstance(outputs, dict) or not outputs:
        return []
    labels = {
        "output_json": "output JSON",
        "output_md": "output Markdown",
        "optimization_output_json": "optimization output JSON",
        "recommendation_output_json": "recommendation output JSON",
    }
    lines: list[str] = []
    for key, display in labels.items():
        value = str(outputs.get(key) or "")
        if value:
            lines.append(f"- {label} {display}: {value}")
    return lines


def format_planned_output_bundle_lines(label: str, outputs: object) -> list[str]:
    if not isinstance(outputs, dict) or not outputs:
        return []
    parts: list[str] = []
    for key, display in (
        ("primary", "primary"),
        ("archive_preview", "archive"),
        ("follow_up", "follow_up"),
        ("follow_up_archive_preview", "follow_up_archive"),
    ):
        item = outputs.get(key) if isinstance(outputs.get(key), dict) else {}
        output_json = str(item.get("output_json") or "")
        if output_json:
            parts.append(f"{display}={output_json}")
    return [f"- {label}: {', '.join(parts)}"] if parts else []


def format_status_watch_back_forward_lines(status_watch: object) -> list[str]:
    if not isinstance(status_watch, dict) or not status_watch:
        return []
    lines: list[str] = []
    run_id_prefix = str(status_watch.get("back_forward_run_run_id_prefix") or "")
    if run_id_prefix:
        lines.append(f"- Watch Back/Forward run ID prefix: {run_id_prefix}")
    manual_collect = str(status_watch.get("back_forward_run_manual_collect_only_command_text") or "")
    if manual_collect:
        lines.append(f"- Watch Back/Forward manual collect-only: {manual_collect}")
    manual_start = str(status_watch.get("back_forward_run_manual_run_start_after") or "")
    manual_step_count = status_watch.get("back_forward_run_manual_step_count")
    manual_parts: list[str] = []
    if manual_start:
        manual_parts.append(f"start_after={manual_start}")
    if manual_step_count != "" and manual_step_count is not None:
        manual_parts.append(f"steps={manual_step_count}")
    if manual_parts:
        lines.append("- Watch Back/Forward manual tester: " + ", ".join(manual_parts))
    quick_start_parts: list[str] = []
    for key, label in (
        ("back_forward_run_mt5_strategy_tester_pack_available", "available"),
        ("back_forward_run_mt5_strategy_tester_pack_ready_for_manual_mt5_run", "ready"),
        ("back_forward_run_mt5_strategy_tester_pack_status", "status"),
        ("back_forward_run_mt5_strategy_tester_pack_next_action", "next_action"),
        ("back_forward_run_mt5_strategy_tester_pack_is_back_forward_pair", "pair"),
        ("back_forward_run_mt5_strategy_tester_pack_manual_run_start_after", "start_after"),
        ("back_forward_run_mt5_strategy_tester_pack_collect_status", "collect_status"),
        ("back_forward_run_mt5_strategy_tester_pack_step_count", "steps"),
    ):
        value = status_watch.get(key)
        if value != "" and value is not None:
            quick_start_parts.append(f"{label}={value}")
    if quick_start_parts:
        lines.append("- Watch Back/Forward MT5 Quick Start: " + ", ".join(quick_start_parts))
    quick_start_collect = str(
        status_watch.get("back_forward_run_mt5_strategy_tester_pack_collect_command_text") or ""
    )
    if quick_start_collect:
        lines.append(f"- Watch Back/Forward MT5 Quick Start collect: {quick_start_collect}")
    quick_start_reason = str(status_watch.get("back_forward_run_mt5_strategy_tester_pack_collect_reason") or "")
    if quick_start_reason:
        lines.append(f"- Watch Back/Forward MT5 Quick Start collect reason: {quick_start_reason}")
    collect_parts: list[str] = []
    for key, label in (
        ("back_forward_run_manual_collect_ready", "ready"),
        ("back_forward_run_manual_collect_status", "status"),
        ("back_forward_run_manual_collect_csv_count", "csv"),
        ("back_forward_run_manual_collect_modified_after", "modified_after"),
        ("back_forward_run_manual_collect_next_action", "next_action"),
    ):
        value = status_watch.get(key)
        if value != "" and value is not None:
            collect_parts.append(f"{label}={value}")
    reason = str(status_watch.get("back_forward_run_manual_collect_reason") or "")
    if reason:
        collect_parts.append(f"reason={reason}")
    blocking_reasons = status_watch.get("back_forward_run_manual_collect_blocking_reasons")
    if blocking_reasons:
        collect_parts.append(f"blocking={compact_list_text(blocking_reasons)}")
    if collect_parts:
        lines.append("- Watch Back/Forward manual collect readiness: " + ", ".join(collect_parts))
    prerequisite_parts: list[str] = []
    prerequisites_ready = status_watch.get("back_forward_run_manual_prerequisites_ready")
    prerequisites_path = str(
        status_watch.get("back_forward_run_manual_prerequisites_compile_status_path") or ""
    )
    prerequisites_generated_at = str(
        status_watch.get("back_forward_run_manual_prerequisites_generated_at") or ""
    )
    prerequisites_reasons = status_watch.get("back_forward_run_manual_prerequisites_reasons")
    if prerequisites_ready != "" and prerequisites_ready is not None:
        prerequisite_parts.append(f"ready={prerequisites_ready}")
    if prerequisites_path:
        prerequisite_parts.append(f"compile_status={prerequisites_path}")
    if prerequisites_generated_at:
        prerequisite_parts.append(f"generated_at={prerequisites_generated_at}")
    if prerequisites_reasons:
        prerequisite_parts.append(f"reasons={compact_list_text(prerequisites_reasons)}")
    if prerequisite_parts:
        lines.append("- Watch Back/Forward manual prerequisites: " + ", ".join(prerequisite_parts))
    condition_parts: list[str] = []
    for key in (
        "back_forward_run_per_step_timeout_seconds",
        "back_forward_run_since_minutes",
        "back_forward_run_min_closed",
        "back_forward_run_from_date",
        "back_forward_run_to_date",
        "back_forward_run_forward_mode",
        "back_forward_run_effective_from_date",
        "back_forward_run_effective_to_date",
        "back_forward_run_effective_forward_mode",
        "back_forward_run_sync_expert_parameters_set",
        "back_forward_run_allow_running_terminal",
        "back_forward_run_allow_stale_compile",
        "back_forward_run_allow_invalid_risk_preset",
    ):
        value = status_watch.get(key)
        if value != "" and value is not None:
            condition_parts.append(f"{key.removeprefix('back_forward_run_')}={value}")
    if condition_parts:
        lines.append("- Watch Back/Forward conditions: " + ", ".join(condition_parts))
    comparison_parts: list[str] = []
    available = status_watch.get("back_forward_run_performance_comparison_available")
    if available != "" and available is not None:
        comparison_parts.append(f"available={available}")
    comparison_status = status_watch.get("back_forward_run_performance_comparison_status")
    if comparison_status:
        comparison_parts.append(f"status={comparison_status}")
    rows = status_watch.get("back_forward_run_performance_comparison_rows")
    if isinstance(rows, list):
        comparison_parts.append(f"rows={len(rows)}")
    elif rows != "" and rows is not None:
        comparison_parts.append(f"rows={rows}")
    if comparison_parts:
        lines.append("- Watch Back/Forward performance comparison: " + ", ".join(comparison_parts))
    thresholds = status_watch.get("back_forward_run_performance_comparison_thresholds")
    if isinstance(thresholds, dict) and thresholds:
        lines.append(f"- Watch Back/Forward comparison thresholds: {compact_mapping_text(thresholds)}")

    ready_parts: list[str] = []
    ready_ok = status_watch.get("back_forward_run_ready_status_ok")
    if ready_ok != "" and ready_ok is not None:
        ready_parts.append(f"ok={ready_ok}")
    reasons = status_watch.get("back_forward_run_ready_status_reasons")
    if reasons:
        ready_parts.append(f"reasons={compact_list_text(reasons)}")
    mismatches = status_watch.get("back_forward_run_ready_status_mismatches")
    if mismatches:
        ready_parts.append(f"mismatches={compact_list_text(mismatches)}")
    if ready_parts:
        lines.append("- Watch Back/Forward ready status: " + ", ".join(ready_parts))

    checked_parts: list[str] = []
    checked_step_keys = status_watch.get("back_forward_run_ready_status_checked_step_keys")
    if checked_step_keys:
        checked_parts.append(f"step_keys={compact_list_text(checked_step_keys)}")
    checked_options = status_watch.get("back_forward_run_ready_status_checked_command_options")
    if checked_options:
        checked_parts.append(f"command_options={compact_list_text(checked_options)}")
    checked_flags = status_watch.get("back_forward_run_ready_status_checked_command_flags")
    if checked_flags:
        checked_parts.append(f"command_flags={compact_list_text(checked_flags)}")
    if checked_parts:
        lines.append("- Watch Back/Forward checked plan: " + ", ".join(checked_parts))

    preflight_parts: list[str] = []
    checked = status_watch.get("back_forward_run_ready_status_checked_execution_conditions")
    if checked:
        preflight_parts.append(f"checked_execution_conditions={compact_list_text(checked)}")
    expected = status_watch.get("back_forward_run_ready_status_expected_execution_conditions")
    if isinstance(expected, dict) and expected:
        preflight_parts.append(f"expected_execution_conditions={compact_mapping_text(expected)}")
    current = status_watch.get("back_forward_run_ready_status_status_execution_conditions")
    if isinstance(current, dict) and current:
        preflight_parts.append(f"status_execution_conditions={compact_mapping_text(current)}")
    if preflight_parts:
        lines.append("- Watch Back/Forward preflight: " + ", ".join(preflight_parts))

    archive_json = str(status_watch.get("back_forward_run_archive_preview_output_json") or "")
    archive_md = str(status_watch.get("back_forward_run_archive_preview_output_md") or "")
    if archive_json:
        lines.append(f"- Watch Back/Forward archive preview output JSON: {archive_json}")
    if archive_md:
        lines.append(f"- Watch Back/Forward archive preview output Markdown: {archive_md}")
    by_step = status_watch.get("back_forward_run_archive_preview_output_json_by_step")
    if isinstance(by_step, dict) and by_step:
        present_by_step = {key: value for key, value in by_step.items() if value != "" and value is not None}
        if present_by_step:
            lines.append(f"- Watch Back/Forward archive preview by step: {compact_mapping_text(present_by_step)}")
    validation = status_watch.get("back_forward_run_archive_preview_validation_ok_by_step")
    if isinstance(validation, dict) and validation:
        present_validation = {
            key: value for key, value in validation.items() if value != "" and value is not None
        }
        if present_validation:
            lines.append(
                f"- Watch Back/Forward archive preview validation: {compact_mapping_text(present_validation)}"
            )
    return lines


def format_related_execution_lines(rows: object) -> list[str]:
    if not isinstance(rows, list) or not rows:
        return []
    lines = ["", "Related next-action plans:", "", "| key | kind | command |", "|---|---|---|"]
    for row in rows:
        if not isinstance(row, dict):
            continue
        execution = row.get("execution") if isinstance(row.get("execution"), dict) else {}
        lines.append(
            f"| {row.get('key', row.get('label', ''))} | {execution.get('kind', '')} | "
            f"{execution.get('command_text', '')} |"
        )
    return lines


def format_prior_action_lines(actions: object, *, title: str) -> list[str]:
    if not isinstance(actions, list) or not actions:
        return []
    lines = [
        "",
        title,
        "",
        "| priority | area | action | execution | runner execute hint | command |",
        "|---:|---|---|---|---|---|",
    ]
    for row in actions:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {row.get('priority', '')} | {row.get('area', '')} | "
            f"{row.get('action', '')} | {row.get('execution_kind', '')} | "
            f"{row.get('runner_execute_hint', '')} | "
            f"{row.get('command_text', '')} |"
        )
    return lines


def format_blocking_prior_action_lines(actions: object) -> list[str]:
    return format_prior_action_lines(actions, title="Blocking prior actions:")


def format_advisory_prior_action_lines(actions: object) -> list[str]:
    return format_prior_action_lines(actions, title="Advisory prior actions:")


def format_markdown(status: dict[str, Any]) -> str:
    current = status.get("current_terminal") if isinstance(status.get("current_terminal"), dict) else {}
    latest = status.get("latest_run") if isinstance(status.get("latest_run"), dict) else {}
    pass_budget = status.get("pass_budget") if isinstance(status.get("pass_budget"), dict) else {}
    artifact_freshness = (
        status.get("artifact_freshness") if isinstance(status.get("artifact_freshness"), dict) else {}
    )
    status_watch = (
        status.get("status_watch_heartbeat")
        if isinstance(status.get("status_watch_heartbeat"), dict)
        else {}
    )
    compile_status = status.get("compile_status") if isinstance(status.get("compile_status"), dict) else {}
    gate = status.get("promotion_gate") if isinstance(status.get("promotion_gate"), dict) else {}
    next_runner = status.get("next_action_runner") if isinstance(status.get("next_action_runner"), dict) else {}
    next_execution = (
        status.get("next_action_execution") if isinstance(status.get("next_action_execution"), dict) else {}
    )
    next_local_execution = (
        status.get("next_action_local_execution")
        if isinstance(status.get("next_action_local_execution"), dict)
        else {}
    )
    back_forward_runner = (
        status.get("back_forward_runner") if isinstance(status.get("back_forward_runner"), dict) else {}
    )
    back_forward_execution = (
        status.get("back_forward_execution") if isinstance(status.get("back_forward_execution"), dict) else {}
    )
    manual_strategy_tester = (
        status.get("manual_strategy_tester")
        if isinstance(status.get("manual_strategy_tester"), dict)
        else {}
    )
    manual_test_queue = (
        status.get("manual_test_queue")
        if isinstance(status.get("manual_test_queue"), dict)
        else {}
    )
    manual_queue_launch = (
        status.get("manual_queue_launch")
        if isinstance(status.get("manual_queue_launch"), dict)
        else {}
    )
    manual_collect_run = (
        status.get("manual_collect_run")
        if isinstance(status.get("manual_collect_run"), dict)
        else {}
    )
    manual_test_queue_with_optimization = (
        status.get("manual_test_queue_with_optimization")
        if isinstance(status.get("manual_test_queue_with_optimization"), dict)
        else {}
    )
    manual_queue_launch_with_optimization = (
        status.get("manual_queue_launch_with_optimization")
        if isinstance(status.get("manual_queue_launch_with_optimization"), dict)
        else {}
    )
    manual_collect_with_optimization = (
        status.get("manual_collect_with_optimization")
        if isinstance(status.get("manual_collect_with_optimization"), dict)
        else {}
    )
    manual_operator_packet_with_optimization = (
        status.get("manual_operator_packet_with_optimization")
        if isinstance(status.get("manual_operator_packet_with_optimization"), dict)
        else {}
    )
    manual_auto_collect_watch = (
        status.get("manual_auto_collect_watch")
        if isinstance(status.get("manual_auto_collect_watch"), dict)
        else {}
    )
    mt5_operator_handoff = (
        status.get("mt5_operator_handoff")
        if isinstance(status.get("mt5_operator_handoff"), dict)
        else {}
    )
    manual_test_queue_handoff = (
        manual_test_queue.get("operator_handoff")
        if isinstance(manual_test_queue.get("operator_handoff"), dict)
        else {}
    )
    bridge_recovery = (
        status.get("bridge_recovery_plan")
        if isinstance(status.get("bridge_recovery_plan"), dict)
        else {}
    )
    local_optimization_evidence = (
        next_local_execution.get("optimization_report_evidence")
        if isinstance(next_local_execution.get("optimization_report_evidence"), dict)
        else {}
    )
    stable = status.get("stable_candidate") if isinstance(status.get("stable_candidate"), dict) else {}
    stable_refit = (
        gate.get("stable_candidate_refit") if isinstance(gate.get("stable_candidate_refit"), dict) else {}
    )
    stable_refit_completed = (
        gate.get("stable_candidate_refit_completed")
        if isinstance(gate.get("stable_candidate_refit_completed"), dict)
        else {}
    )
    p1_actions = gate.get("p1_actions") if isinstance(gate.get("p1_actions"), list) else []
    primary_post_lines = format_post_execution_artifact_lines(
        "Primary", next_runner.get("primary_post_execution_artifacts")
    )
    archive_preview_post_lines = format_post_execution_artifact_lines(
        "Archive preview", next_runner.get("archive_preview_post_execution_artifacts")
    )
    follow_up_post_lines = format_post_execution_artifact_lines(
        "Follow-up", next_runner.get("follow_up_post_execution_artifacts")
    )
    follow_up_archive_preview_post_lines = format_post_execution_artifact_lines(
        "Follow-up archive preview",
        next_runner.get("follow_up_archive_preview_post_execution_artifacts"),
    )
    post_validation_lines = format_post_execution_validation_lines(next_runner.get("post_execution_validation"))
    archive_output_lines = format_planned_output_lines("Archive preview", next_runner.get("archive_preview_planned_outputs"))
    primary_output_lines = format_planned_output_lines("Primary", next_runner.get("primary_planned_outputs"))
    follow_up_archive_output_lines = format_planned_output_lines(
        "Follow-up archive preview",
        next_runner.get("follow_up_archive_preview_planned_outputs"),
    )
    follow_up_output_lines = format_planned_output_lines("Follow-up", next_runner.get("follow_up_planned_outputs"))
    status_watch_planned_output_bundle_lines = format_planned_output_bundle_lines(
        "Watch planned outputs",
        status_watch.get("next_action_run_planned_outputs"),
    )
    status_watch_primary_output_lines = format_planned_output_lines(
        "Watch primary",
        status_watch.get("next_action_run_primary_planned_outputs"),
    )
    status_watch_archive_output_lines = format_planned_output_lines(
        "Watch archive preview",
        status_watch.get("next_action_run_archive_preview_planned_outputs"),
    )
    status_watch_follow_up_output_lines = format_planned_output_lines(
        "Watch follow-up",
        status_watch.get("next_action_run_follow_up_planned_outputs"),
    )
    status_watch_follow_up_archive_output_lines = format_planned_output_lines(
        "Watch follow-up archive preview",
        status_watch.get("next_action_run_follow_up_archive_preview_planned_outputs"),
    )
    status_watch_back_forward_lines = format_status_watch_back_forward_lines(status_watch)
    blocking_prior_action_lines = format_blocking_prior_action_lines(next_runner.get("blocking_prior_actions"))
    advisory_prior_action_lines = format_advisory_prior_action_lines(next_runner.get("advisory_prior_actions"))
    related_execution_lines = format_related_execution_lines(next_runner.get("related_executions"))
    lines = [
        "# MT5 Tester Status",
        "",
        f"- Generated at: {status.get('generated_at')}",
        f"- Operational status: {status.get('operational_status')}",
        f"- Ready for tester launch: {status.get('ready_for_tester_launch')}",
        f"- Next action: {status.get('next_action')}",
        "",
        *format_manual_operator_packet_lines(
            manual_operator_packet_with_optimization,
            manual_auto_collect_watch,
        ),
        *format_manual_auto_collect_watch_lines(manual_auto_collect_watch),
        *format_mt5_operator_handoff_lines(mt5_operator_handoff),
        "## Current Terminal",
        "",
        f"- Detection enabled: {current.get('detection_enabled')}",
        f"- Running: {current.get('running')}",
        f"- Count: {current.get('count')}",
        "",
        "| pid | command |",
        "|---:|---|",
        *markdown_process_rows(current.get("processes")),
        "",
        "## Manual Strategy Tester",
        "",
        f"- Available: {manual_strategy_tester.get('available', '')}",
        f"- Status: {manual_strategy_tester.get('status', '')}",
        f"- Recommended: {manual_strategy_tester.get('recommended', '')}",
        f"- Terminal running: {manual_strategy_tester.get('terminal_running', '')}",
        f"- Auto launch ready: {manual_strategy_tester.get('auto_launch_ready', '')}",
        f"- Auto launch status: {manual_strategy_tester.get('auto_launch_status', '')}",
        f"- Auto launch blocked by running terminal: {manual_strategy_tester.get('auto_launch_blocked_by_running_terminal', '')}",
        (
            "- Auto launch blockers: "
            f"{auto_launch_blockers_text(
                manual_strategy_tester.get('auto_launch_blockers'),
                blocked_by_running_terminal=bool(
                    manual_strategy_tester.get('auto_launch_blocked_by_running_terminal')
                ),
            )}"
        ),
        f"- Reasons: {compact_list_text(manual_strategy_tester.get('reasons'))}",
        f"- Run ID prefix: {manual_strategy_tester.get('run_id_prefix', '')}",
        f"- Mode: {manual_strategy_tester.get('mode', '')}",
        f"- Evidence state: {manual_strategy_tester.get('evidence_state', '')}",
        f"- Manual run start after: {manual_strategy_tester.get('manual_run_start_after', '')}",
        f"- Collect-only command: {manual_strategy_tester.get('collect_only_command_text', '')}",
        f"- Collect-only note: {manual_strategy_tester.get('collect_only_note', '')}",
        f"- Collect readiness: ready={manual_strategy_tester.get('manual_collect_ready', '')}, "
        f"status={manual_strategy_tester.get('manual_collect_status', '')}, "
        f"csv={manual_strategy_tester.get('manual_collect_csv_count', '')}, "
        f"modified_after={manual_strategy_tester.get('manual_collect_modified_after', '')}",
        f"- Collect reason: {manual_strategy_tester.get('manual_collect_reason', '')}",
        f"- Collect blocking reasons: {compact_list_text(manual_strategy_tester.get('manual_collect_blocking_reasons'))}",
        f"- Collect next action: {manual_strategy_tester.get('manual_collect_next_action', '')}",
        f"- Manual prerequisites ready: {manual_strategy_tester.get('manual_prerequisites_ready', '')}",
        f"- Manual prerequisites reasons: {compact_list_text(manual_strategy_tester.get('manual_prerequisites_reasons'))}",
        f"- Manual prerequisites compile status: {manual_strategy_tester.get('manual_prerequisites_compile_status_path', '')}",
        f"- Manual prerequisites generated at: {manual_strategy_tester.get('manual_prerequisites_generated_at', '')}",
        f"- Back/Forward plan validation ready: {manual_strategy_tester.get('back_forward_plan_validation_ready', '')}",
        f"- Back/Forward plan validation status: {manual_strategy_tester.get('back_forward_plan_validation_status', '')}",
        f"- Back/Forward plan validation reasons: {compact_list_text(manual_strategy_tester.get('back_forward_plan_validation_reasons'))}",
        f"- Step count: {manual_strategy_tester.get('step_count', '')}",
        f"- Note: {manual_strategy_tester.get('note', '')}",
        "",
        "| order | step | expert | symbol | period | model | dates | forward | window | optimization | run type | expected report | inputs | report | fingerprint |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        *format_manual_strategy_tester_rows(manual_strategy_tester.get("steps")),
        "",
        "## MT5 Manual Test Queue",
        "",
        f"- Exists: {manual_test_queue.get('exists', '')}",
        f"- OK: {manual_test_queue.get('ok', '')}",
        f"- Generated at: {manual_test_queue.get('generated_at', '')}",
        f"- Path: {manual_test_queue.get('path', '')}",
        f"- Status: {manual_test_queue.get('status', '')}",
        f"- Next action: {manual_test_queue.get('next_action', '')}",
        f"- Progress state: {manual_test_queue.get('progress_state', '')}",
        f"- Entries: {manual_test_queue.get('entry_count', '')}",
        f"- Total entries: {manual_test_queue.get('total_entry_count', '')}",
        f"- Stale entries: {manual_test_queue.get('stale_entry_count', '')}",
        (
            "- Manual run start: "
            f"marked={manual_test_queue.get('manual_run_start_marked', '')}, "
            f"this_run={manual_test_queue.get('manual_run_start_marked_this_run', '')}, "
            f"preserved={manual_test_queue.get('manual_run_start_preserved', '')}, "
            f"state={manual_test_queue.get('manual_run_start_state_marked_count', '')}/"
            f"{manual_test_queue.get('manual_run_start_state_count', '')}, "
            f"effective_after={compact_list_text(manual_test_queue.get('manual_run_start_effective_after_values'))}"
        ),
        f"- Manual run start after override: {manual_test_queue.get('manual_run_start_after_override', '')}",
        f"- Steps: {manual_test_queue.get('step_count', '')}",
        f"- Ready to collect: {manual_test_queue.get('ready_to_collect_count', '')}",
        f"- Waiting: {manual_test_queue.get('waiting_count', '')}",
        f"- Step reports ready: {manual_test_queue.get('step_report_ready_count', '')}",
        f"- Step collect ready: {manual_test_queue.get('step_collect_ready_count', '')}",
        f"- Step reports waiting: {manual_test_queue.get('step_waiting_report_count', '')}",
        f"- Step launches needed: {manual_test_queue.get('step_launch_needed_count', '')}",
        f"- Step reports ready IDs: {compact_list_text(manual_test_queue.get('step_report_ready_ids'))}",
        f"- Step collect ready IDs: {compact_list_text(manual_test_queue.get('step_collect_ready_ids'))}",
        f"- Step reports waiting IDs: {compact_list_text(manual_test_queue.get('step_waiting_report_ids'))}",
        f"- Step launches needed IDs: {compact_list_text(manual_test_queue.get('step_launch_needed_ids'))}",
        f"- Collect check command: {manual_test_queue_handoff.get('collect_check_command_text', '')}",
        f"- All collect ready: {manual_test_queue.get('all_collect_ready', '')}",
        f"- Blocking reasons: {compact_list_text(manual_test_queue.get('blocking_reasons'))}",
        "",
        "### MT5 Operation Cards",
        "",
        "| next | order | action | purpose | queue/step | symbol | period | dates | forward | optimization | inputs | report | collect status | fingerprint |",
        "|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|",
        *format_manual_test_queue_operation_card_rows(manual_test_queue.get("operation_cards")),
        "",
        "### Next Manual Step",
        "",
        "| order | queue/step | symbol | period | dates | forward | optimization | run type | status | launch kind | inputs | report | fingerprint |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---|---|",
        format_manual_test_queue_next_step_row(manual_test_queue.get("next_launch_step")),
        "",
        "### MT5 Strategy Tester Targets",
        "",
        "| order | purpose | queue/step | symbol | period | dates | forward | optimization | run type | expected report | report note | inputs | report | start after | collect after | collect status | step report | launch needed | auto launch | fingerprint |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---:|---|---|",
        *format_manual_test_queue_target_rows(manual_test_queue.get("strategy_tester_targets")),
        "",
        "| order | id | title | available | current | runner generated | gate generated | current gate | decision | current decision | action current | stale gate | stale reason | start after | steps | ready | collect status | reason | next action | source |",
        "|---:|---|---|---:|---:|---|---|---|---|---|---:|---|---|---|---:|---:|---|---|---|---|",
        *format_manual_test_queue_entry_rows(manual_test_queue.get("entries")),
        "",
        "### Stale Runner Refresh",
        "",
        "| id | source | stale reason | refresh command |",
        "|---|---|---|---|",
        *format_manual_test_queue_stale_refresh_rows(manual_test_queue.get("entries")),
        "",
        "| order | step | expert | symbol | period | model | dates | forward | window | optimization | run type | expected report | inputs | report | fingerprint |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        *format_manual_strategy_tester_rows(
            manual_test_queue.get("execution_checklist")
            or manual_test_queue_steps(manual_test_queue.get("entries"))
        ),
        "",
        "| done | order | queue/step | symbol | period | model | dates | forward | optimization | run type | expected report | step report | launch needed | inputs | report | start after | fingerprint |",
        "|---|---:|---|---|---|---|---|---|---|---|---|---|---:|---|---|---|---|",
        *format_manual_test_queue_checklist_rows(manual_test_queue.get("execution_checklist")),
        "",
        "### MT5 Manual Queue Auto Launch Commands",
        "",
        "| order | queue/step | launch needed | kind | workspace config | MT5 config | command |",
        "|---:|---|---:|---|---|---|---|",
        *format_manual_test_queue_launch_rows(manual_test_queue.get("execution_checklist")),
        "",
        "## MT5 Manual Queue Launch",
        "",
        f"- Exists: {manual_queue_launch.get('exists', '')}",
        f"- OK: {manual_queue_launch.get('ok', '')}",
        f"- Generated at: {manual_queue_launch.get('generated_at', '')}",
        f"- Path: {manual_queue_launch.get('path', '')}",
        f"- Status: {manual_queue_launch.get('status', '')}",
        f"- Next action: {manual_queue_launch.get('next_action', '')}",
        f"- Queue: {manual_queue_launch.get('queue_path', '')}",
        f"- Queue status: {manual_queue_launch.get('queue_status', '')}",
        f"- Queue next action: {manual_queue_launch.get('queue_next_action', '')}",
        (
            "- Queue progress: "
            f"entries={manual_queue_launch.get('queue_entry_count', '')}/"
            f"{manual_queue_launch.get('queue_total_entry_count', '')}, "
            f"steps={manual_queue_launch.get('queue_step_count', '')}, "
            f"ready={manual_queue_launch.get('queue_ready_to_collect_count', '')}, "
            f"waiting={manual_queue_launch.get('queue_waiting_count', '')}, "
            f"step_ready={manual_queue_launch.get('queue_step_report_ready_count', '')}, "
            f"step_waiting={manual_queue_launch.get('queue_step_waiting_report_count', '')}, "
            f"launch_needed={manual_queue_launch.get('queue_step_launch_needed_count', '')}"
        ),
        (
            "- Queue refresh: "
            f"enabled={(manual_queue_launch.get('queue_refresh') if isinstance(manual_queue_launch.get('queue_refresh'), dict) else {}).get('enabled', '')}, "
            f"ok={(manual_queue_launch.get('queue_refresh') if isinstance(manual_queue_launch.get('queue_refresh'), dict) else {}).get('ok', '')}, "
            f"status={(manual_queue_launch.get('queue_refresh') if isinstance(manual_queue_launch.get('queue_refresh'), dict) else {}).get('status', '')}, "
            f"sources={(manual_queue_launch.get('queue_refresh') if isinstance(manual_queue_launch.get('queue_refresh'), dict) else {}).get('source_count', '')}"
        ),
        f"- Queue handoff state: {manual_queue_launch.get('queue_operator_handoff_state', '')}",
        (
            "- Queue handoff next step: "
            f"{(manual_queue_launch.get('queue_operator_handoff_next_mt5_step') if isinstance(manual_queue_launch.get('queue_operator_handoff_next_mt5_step'), dict) else {}).get('queue_id', '')}/"
            f"{(manual_queue_launch.get('queue_operator_handoff_next_mt5_step') if isinstance(manual_queue_launch.get('queue_operator_handoff_next_mt5_step'), dict) else {}).get('step_label', '')}, "
            f"forward={(manual_queue_launch.get('queue_operator_handoff_next_mt5_step') if isinstance(manual_queue_launch.get('queue_operator_handoff_next_mt5_step'), dict) else {}).get('forward', '')}, "
            "optimization="
            f"{optimization_label_for_item(manual_queue_launch.get('queue_operator_handoff_next_mt5_step') if isinstance(manual_queue_launch.get('queue_operator_handoff_next_mt5_step'), dict) else {})}, "
            f"report={(manual_queue_launch.get('queue_operator_handoff_next_mt5_step') if isinstance(manual_queue_launch.get('queue_operator_handoff_next_mt5_step'), dict) else {}).get('report', '')}"
        ),
        f"- Queue handoff collect ready: {manual_queue_launch.get('queue_operator_handoff_collect_ready', '')}",
        f"- Queue handoff waiting entries: {compact_list_text(manual_queue_launch.get('queue_operator_handoff_waiting_entry_ids'))}",
        f"- Queue handoff collect dry-run: {manual_queue_launch.get('queue_operator_handoff_collect_dry_run_command_text', '')}",
        f"- Queue handoff collect execute: {manual_queue_launch.get('queue_operator_handoff_collect_execute_command_text', '')}",
        (
            "- Queue handoff collect execute + analysis: "
            f"{manual_queue_launch.get('queue_operator_handoff_collect_execute_and_refresh_analysis_command_text', '')}"
        ),
        (
            "- Queue handoff collect execute + full analysis: "
            f"{manual_queue_launch.get('queue_operator_handoff_collect_execute_and_refresh_all_command_text', '')}"
        ),
        f"- Execute: {manual_queue_launch.get('execute', '')}",
        f"- Selected: {manual_queue_launch.get('selected', '')}",
        f"- Selected fingerprint: {manual_queue_launch.get('selected_step_fingerprint', '')}",
        f"- Selected expected report: {manual_queue_launch.get('selected_expected_report', '')}",
        f"- Selected matches queue handoff: {manual_queue_launch.get('selected_matches_queue_handoff', '')}",
        f"- Launch kind: {manual_queue_launch.get('launch_command_kind', '')}",
        f"- Mark manual run start: {manual_queue_launch.get('manual_run_start_mark_status', '')}",
        f"- Manual run start after: {manual_queue_launch.get('manual_run_start_after', '')}",
        f"- Blocked: {manual_queue_launch.get('blocked', '')}",
        f"- Blocked reasons: {compact_list_text(manual_queue_launch.get('blocked_reasons'))}",
        f"- Running terminal count: {manual_queue_launch.get('running_terminal_count', '')}",
        f"- Returncode: {manual_queue_launch.get('returncode', '')}",
        "",
        "| order | queue/step | symbol | period | model | dates | forward | optimization | run type | expected report | inputs | report | fingerprint |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---|---|",
        (
            f"| {markdown_cell((manual_queue_launch.get('selected_item') if isinstance(manual_queue_launch.get('selected_item'), dict) else {}).get('order', ''))} | "
            f"{markdown_cell((manual_queue_launch.get('selected_item') if isinstance(manual_queue_launch.get('selected_item'), dict) else {}).get('queue_id', ''))}/"
            f"{markdown_cell((manual_queue_launch.get('selected_item') if isinstance(manual_queue_launch.get('selected_item'), dict) else {}).get('step_label', ''))} | "
            f"{markdown_cell((manual_queue_launch.get('selected_item') if isinstance(manual_queue_launch.get('selected_item'), dict) else {}).get('symbol', ''))} | "
            f"{markdown_cell((manual_queue_launch.get('selected_item') if isinstance(manual_queue_launch.get('selected_item'), dict) else {}).get('period', ''))} | "
            f"{markdown_cell((manual_queue_launch.get('selected_item') if isinstance(manual_queue_launch.get('selected_item'), dict) else {}).get('model', ''))} | "
            f"{markdown_cell((manual_queue_launch.get('selected_item') if isinstance(manual_queue_launch.get('selected_item'), dict) else {}).get('dates', ''))} | "
            f"{markdown_cell((manual_queue_launch.get('selected_item') if isinstance(manual_queue_launch.get('selected_item'), dict) else {}).get('forward', ''))} | "
            f"{markdown_cell(optimization_label_for_item(manual_queue_launch.get('selected_item') if isinstance(manual_queue_launch.get('selected_item'), dict) else {}))} | "
            f"{markdown_cell((manual_queue_launch.get('selected_item') if isinstance(manual_queue_launch.get('selected_item'), dict) else {}).get('run_type', ''))} | "
            f"{markdown_cell((manual_queue_launch.get('selected_item') if isinstance(manual_queue_launch.get('selected_item'), dict) else {}).get('expected_report_artifact', ''))} | "
            f"{markdown_cell((manual_queue_launch.get('selected_item') if isinstance(manual_queue_launch.get('selected_item'), dict) else {}).get('inputs', ''))} | "
            f"{markdown_cell((manual_queue_launch.get('selected_item') if isinstance(manual_queue_launch.get('selected_item'), dict) else {}).get('report', ''))} | "
            f"{markdown_cell((manual_queue_launch.get('selected_item') if isinstance(manual_queue_launch.get('selected_item'), dict) else {}).get('step_fingerprint', ''))} |"
        ),
        "",
        "```bash",
        str(manual_queue_launch.get("command_text") or ""),
        "```",
        "",
        "| pid | command |",
        "|---:|---|",
        *markdown_process_rows(manual_queue_launch.get("running_terminal_processes")),
        "",
        "## MT5 Manual Collect Run",
        "",
        f"- Exists: {manual_collect_run.get('exists', '')}",
        f"- OK: {manual_collect_run.get('ok', '')}",
        f"- Generated at: {manual_collect_run.get('generated_at', '')}",
        f"- Path: {manual_collect_run.get('path', '')}",
        f"- Status: {manual_collect_run.get('status', '')}",
        f"- Next action: {manual_collect_run.get('next_action', '')}",
        f"- Blocking reasons: {compact_list_text(manual_collect_run.get('blocking_reasons'))}",
        f"- Execute: {manual_collect_run.get('execute', '')}",
        f"- Dry run: {manual_collect_run.get('dry_run', '')}",
        f"- Queue: {manual_collect_run.get('queue_path', '')}",
        f"- Queue status: {manual_collect_run.get('queue_status', '')}",
        f"- Queue next action: {manual_collect_run.get('queue_next_action', '')}",
        f"- Queue steps: {manual_collect_run.get('queue_step_count', '')}",
        f"- Queue step reports ready: {manual_collect_run.get('queue_step_report_ready_count', '')}",
        f"- Queue step reports waiting: {manual_collect_run.get('queue_step_waiting_report_count', '')}",
        f"- Queue step launches needed: {manual_collect_run.get('queue_step_launch_needed_count', '')}",
        f"- Entries: {manual_collect_run.get('entry_count', '')}",
        f"- Ready entries: {manual_collect_run.get('ready_entry_count', '')}",
        f"- Selected: {manual_collect_run.get('selected_count', '')}",
        f"- Waiting: {manual_collect_run.get('waiting_count', '')}",
        f"- Invalid: {manual_collect_run.get('invalid_count', '')}",
        (
            "- Queue refresh: "
            f"enabled={(manual_collect_run.get('queue_refresh') if isinstance(manual_collect_run.get('queue_refresh'), dict) else {}).get('enabled', '')}, "
            f"ok={(manual_collect_run.get('queue_refresh') if isinstance(manual_collect_run.get('queue_refresh'), dict) else {}).get('ok', '')}, "
            f"status={(manual_collect_run.get('queue_refresh') if isinstance(manual_collect_run.get('queue_refresh'), dict) else {}).get('status', '')}, "
            f"sources={(manual_collect_run.get('queue_refresh') if isinstance(manual_collect_run.get('queue_refresh'), dict) else {}).get('source_count', '')}"
        ),
        "",
        *format_manual_collect_handoff(manual_collect_run),
        "### MT5 Manual Collect Step Completion Audit",
        "",
        "| order | queue/step | purpose | status | report ready | collect ready | launch needed | expected | report | modified after | fingerprint | reason |",
        "|---:|---|---|---|---:|---:|---:|---|---|---|---|---|",
        *format_manual_collect_step_audit_rows(manual_collect_run.get("step_completion_audit")),
        "",
        "| id | title | runner generated | gate generated | decision | collect status | modified after | skip reason | reason |",
        "|---|---|---|---|---|---|---|---|---|",
        *format_manual_collect_run_rows(manual_collect_run.get("skipped"), kind="skipped"),
        "",
        "| id | title | runner generated | gate generated | decision | collect status | modified after | skip reason | reason |",
        "|---|---|---|---|---|---|---|---|---|",
        *format_manual_collect_run_rows(manual_collect_run.get("planned"), kind="planned"),
        "",
        "| id | status | returncode | output json | output md | reason |",
        "|---|---|---|---|---|---|",
        *format_manual_collect_run_rows(manual_collect_run.get("executions"), kind="execution"),
        "",
        "## MT5 Manual Test Queue With Optimization",
        "",
        f"- Exists: {manual_test_queue_with_optimization.get('exists', '')}",
        f"- OK: {manual_test_queue_with_optimization.get('ok', '')}",
        f"- Generated at: {manual_test_queue_with_optimization.get('generated_at', '')}",
        f"- Path: {manual_test_queue_with_optimization.get('path', '')}",
        f"- Status: {manual_test_queue_with_optimization.get('status', '')}",
        f"- Next action: {manual_test_queue_with_optimization.get('next_action', '')}",
        f"- Progress state: {manual_test_queue_with_optimization.get('progress_state', '')}",
        f"- Entries: {manual_test_queue_with_optimization.get('entry_count', '')}",
        f"- Total entries: {manual_test_queue_with_optimization.get('total_entry_count', '')}",
        f"- Stale entries: {manual_test_queue_with_optimization.get('stale_entry_count', '')}",
        (
            "- Manual run start: "
            f"marked={manual_test_queue_with_optimization.get('manual_run_start_marked', '')}, "
            f"this_run={manual_test_queue_with_optimization.get('manual_run_start_marked_this_run', '')}, "
            f"preserved={manual_test_queue_with_optimization.get('manual_run_start_preserved', '')}, "
            f"state={manual_test_queue_with_optimization.get('manual_run_start_state_marked_count', '')}/"
            f"{manual_test_queue_with_optimization.get('manual_run_start_state_count', '')}, "
            f"effective_after={compact_list_text(manual_test_queue_with_optimization.get('manual_run_start_effective_after_values'))}"
        ),
        (
            "- Manual run start after override: "
            f"{manual_test_queue_with_optimization.get('manual_run_start_after_override', '')}"
        ),
        f"- Steps: {manual_test_queue_with_optimization.get('step_count', '')}",
        f"- Ready to collect: {manual_test_queue_with_optimization.get('ready_to_collect_count', '')}",
        f"- Waiting: {manual_test_queue_with_optimization.get('waiting_count', '')}",
        f"- Step reports ready: {manual_test_queue_with_optimization.get('step_report_ready_count', '')}",
        f"- Step collect ready: {manual_test_queue_with_optimization.get('step_collect_ready_count', '')}",
        f"- Step reports waiting: {manual_test_queue_with_optimization.get('step_waiting_report_count', '')}",
        f"- Step launches needed: {manual_test_queue_with_optimization.get('step_launch_needed_count', '')}",
        (
            "- Step reports ready IDs: "
            f"{compact_list_text(manual_test_queue_with_optimization.get('step_report_ready_ids'))}"
        ),
        (
            "- Step collect ready IDs: "
            f"{compact_list_text(manual_test_queue_with_optimization.get('step_collect_ready_ids'))}"
        ),
        (
            "- Step reports waiting IDs: "
            f"{compact_list_text(manual_test_queue_with_optimization.get('step_waiting_report_ids'))}"
        ),
        (
            "- Step launches needed IDs: "
            f"{compact_list_text(manual_test_queue_with_optimization.get('step_launch_needed_ids'))}"
        ),
        (
            "- Static configs: "
            f"{compact_list_text(manual_test_queue_with_optimization.get('static_strategy_configs'))}"
        ),
        (
            "- Static candidate labels: "
            f"{compact_list_text(manual_test_queue_with_optimization.get('static_candidate_labels'))}"
        ),
        f"- Blocking reasons: {compact_list_text(manual_test_queue_with_optimization.get('blocking_reasons'))}",
        "",
        "### Optimization Next Manual Step",
        "",
        "| order | queue/step | symbol | period | dates | forward | optimization | run type | status | launch kind | inputs | report | fingerprint |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---|---|",
        format_manual_test_queue_next_step_row(
            manual_test_queue_with_optimization.get("next_launch_step")
        ),
        "",
        "### Optimization Strategy Tester Targets",
        "",
        "| order | purpose | queue/step | symbol | period | dates | forward | optimization | run type | expected report | report note | inputs | report | start after | collect after | collect status | step report | launch needed | auto launch | fingerprint |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---:|---|---|",
        *format_manual_test_queue_target_rows(
            manual_test_queue_with_optimization.get("strategy_tester_targets")
        ),
        "",
        "## MT5 Manual Queue Launch With Optimization",
        "",
        f"- Exists: {manual_queue_launch_with_optimization.get('exists', '')}",
        f"- OK: {manual_queue_launch_with_optimization.get('ok', '')}",
        f"- Generated at: {manual_queue_launch_with_optimization.get('generated_at', '')}",
        f"- Path: {manual_queue_launch_with_optimization.get('path', '')}",
        f"- Status: {manual_queue_launch_with_optimization.get('status', '')}",
        f"- Next action: {manual_queue_launch_with_optimization.get('next_action', '')}",
        f"- Queue: {manual_queue_launch_with_optimization.get('queue_path', '')}",
        f"- Queue status: {manual_queue_launch_with_optimization.get('queue_status', '')}",
        (
            "- Queue progress: "
            f"entries={manual_queue_launch_with_optimization.get('queue_entry_count', '')}/"
            f"{manual_queue_launch_with_optimization.get('queue_total_entry_count', '')}, "
            f"steps={manual_queue_launch_with_optimization.get('queue_step_count', '')}, "
            f"ready={manual_queue_launch_with_optimization.get('queue_ready_to_collect_count', '')}, "
            f"waiting={manual_queue_launch_with_optimization.get('queue_waiting_count', '')}, "
            f"step_ready={manual_queue_launch_with_optimization.get('queue_step_report_ready_count', '')}, "
            f"step_waiting={manual_queue_launch_with_optimization.get('queue_step_waiting_report_count', '')}, "
            f"launch_needed={manual_queue_launch_with_optimization.get('queue_step_launch_needed_count', '')}"
        ),
        f"- Selected: {manual_queue_launch_with_optimization.get('selected', '')}",
        f"- Launch kind: {manual_queue_launch_with_optimization.get('launch_command_kind', '')}",
        (
            "- Mark manual run start: "
            f"{manual_queue_launch_with_optimization.get('manual_run_start_mark_status', '')}"
        ),
        (
            "- Manual run start after: "
            f"{manual_queue_launch_with_optimization.get('manual_run_start_after', '')}"
        ),
        f"- Blocked: {manual_queue_launch_with_optimization.get('blocked', '')}",
        f"- Blocked reasons: {compact_list_text(manual_queue_launch_with_optimization.get('blocked_reasons'))}",
        f"- Running terminal count: {manual_queue_launch_with_optimization.get('running_terminal_count', '')}",
        f"- Queue handoff collect execute: {manual_queue_launch_with_optimization.get('queue_operator_handoff_collect_execute_command_text', '')}",
        (
            "- Queue handoff collect execute + analysis: "
            f"{manual_queue_launch_with_optimization.get('queue_operator_handoff_collect_execute_and_refresh_analysis_command_text', '')}"
        ),
        (
            "- Queue handoff collect execute + full analysis: "
            f"{manual_queue_launch_with_optimization.get('queue_operator_handoff_collect_execute_and_refresh_all_command_text', '')}"
        ),
        "",
        "```bash",
        str(manual_queue_launch_with_optimization.get("command_text") or ""),
        "```",
        "",
        "## MT5 Manual Collect With Optimization",
        "",
        f"- Exists: {manual_collect_with_optimization.get('exists', '')}",
        f"- OK: {manual_collect_with_optimization.get('ok', '')}",
        f"- Generated at: {manual_collect_with_optimization.get('generated_at', '')}",
        f"- Path: {manual_collect_with_optimization.get('path', '')}",
        f"- Status: {manual_collect_with_optimization.get('status', '')}",
        f"- Next action: {manual_collect_with_optimization.get('next_action', '')}",
        f"- Blocking reasons: {compact_list_text(manual_collect_with_optimization.get('blocking_reasons'))}",
        f"- Queue: {manual_collect_with_optimization.get('queue_path', '')}",
        f"- Queue status: {manual_collect_with_optimization.get('queue_status', '')}",
        f"- Queue step reports ready: {manual_collect_with_optimization.get('queue_step_report_ready_count', '')}",
        f"- Queue step reports waiting: {manual_collect_with_optimization.get('queue_step_waiting_report_count', '')}",
        f"- Queue step launches needed: {manual_collect_with_optimization.get('queue_step_launch_needed_count', '')}",
        f"- Selected: {manual_collect_with_optimization.get('selected_count', '')}",
        f"- Waiting: {manual_collect_with_optimization.get('waiting_count', '')}",
        f"- Invalid: {manual_collect_with_optimization.get('invalid_count', '')}",
        "",
        "## Bridge Recovery",
        "",
        f"- Exists: {bridge_recovery.get('exists', '')}",
        f"- Status: {bridge_recovery.get('status', '')}",
        f"- Ready for MT5 validation: {bridge_recovery.get('ready_for_mt5_validation', '')}",
        f"- Generated at: {bridge_recovery.get('generated_at', '')}",
        f"- Output: {bridge_recovery.get('path', '')}",
        f"- Blocking reasons: {compact_list_text(bridge_recovery.get('blocking_reasons'))}",
        f"- Next action: {bridge_recovery.get('next_action', '')}",
        f"- Operational status: {bridge_recovery.get('operational_status', '')}",
        f"- Bridge process running: {bridge_recovery.get('bridge_process_running', '')}",
        f"- MT5 terminal running: {bridge_recovery.get('mt5_terminal_running', '')}",
        f"- Snapshot fresh: {bridge_recovery.get('snapshot_fresh', '')} age_seconds={bridge_recovery.get('snapshot_age_seconds', '')}",
        f"- History pending: {bridge_recovery.get('history_request_pending', '')} stale={bridge_recovery.get('history_request_stale_pending', '')}",
        f"- History request/done: request={bridge_recovery.get('history_request_id', '')} done={bridge_recovery.get('history_done_id', '')} match={bridge_recovery.get('history_done_matches_request', '')}",
        f"- History data fresh: {bridge_recovery.get('history_data_fresh', '')} stale={bridge_recovery.get('history_data_stale', '')} max_age_seconds={bridge_recovery.get('history_data_max_age_seconds', '')} server_time={bridge_recovery.get('history_status_server_time', '')} server_time_age_seconds={bridge_recovery.get('history_status_server_time_age_seconds', '')} m1_last_time={bridge_recovery.get('history_status_m1_last_time', '')} m1_last_time_age_seconds={bridge_recovery.get('history_status_m1_last_time_age_seconds', '')}",
        f"- Bridge log activity: {bridge_recovery.get('bridge_log_activity_status', '')}",
        f"- Last EA POST: {bridge_recovery.get('last_ea_post_at', '')} age_seconds={bridge_recovery.get('last_ea_post_age_seconds', '')}",
        "",
        "## Artifact Freshness",
        "",
        f"- Max age seconds: {artifact_freshness.get('max_age_seconds', '')}",
        "",
        "| artifact | exists | fresh | age_seconds | path |",
        "|---|---:|---:|---:|---|",
        *format_artifact_freshness_rows(artifact_freshness),
        "",
        "## MT5 Status Watcher",
        "",
        f"- Heartbeat path: {status_watch.get('path', '')}",
        f"- Status: {status_watch.get('status', '')}",
        f"- Exists: {status_watch.get('exists', '')}",
        f"- Fresh: {status_watch.get('fresh', '')}",
        f"- Compatible: {status_watch.get('compatible', '')}",
        f"- Missing required fields: {compact_list_text(status_watch.get('missing_required_fields'))}",
        f"- Age seconds: {status_watch.get('age_seconds', '')} / {status_watch.get('max_age_seconds', '')}",
        f"- Schema version: {status_watch.get('schema_version', '')}",
        f"- Implementation version: {status_watch.get('implementation_version', '')}",
        f"- Expected implementation version: {status_watch.get('expected_implementation_version', '')}",
        f"- Implementation version mismatch: {status_watch.get('implementation_version_mismatch', '')}",
        f"- Watcher PID: {status_watch.get('watcher_pid', '')}",
        f"- PID file: {status_watch.get('pid_file', '')}",
        f"- PID file written: {status_watch.get('pid_file_written', '')}",
        f"- Continuous: {status_watch.get('continuous', '')}",
        f"- Run index: {status_watch.get('run_index', '')}",
        f"- Finished at: {status_watch.get('finished_at', '')}",
        f"- Returncode: {status_watch.get('returncode', '')}",
        f"- Watch Bridge recovery: status={status_watch.get('bridge_recovery_plan_status', '')}, "
        f"ready_for_mt5_validation={status_watch.get('bridge_recovery_plan_ready_for_mt5_validation', '')}, "
        f"last_ea_post_age_seconds={status_watch.get('bridge_recovery_plan_last_ea_post_age_seconds', '')}, "
        f"history_data_fresh={status_watch.get('bridge_recovery_plan_history_data_fresh', '')}, "
        f"history_data_stale={status_watch.get('bridge_recovery_plan_history_data_stale', '')}, "
        f"history_server_time={status_watch.get('bridge_recovery_plan_history_status_server_time', '')}, "
        f"next_action={status_watch.get('bridge_recovery_plan_next_action', '')}, "
        f"blocking={compact_list_text(status_watch.get('bridge_recovery_plan_blocking_reasons'))}",
        f"- Watch Bridge recovery output: {status_watch.get('bridge_recovery_plan_output_json', '')}",
        f"- Watch compile tester configs synced: {status_watch.get('compile_all_tester_configs_synced', '')}",
        f"- Watch tester config references ready: {status_watch.get('compile_all_required_tester_config_references_ready', '')}",
        f"- Watch MT5 operator next step: {status_watch.get('mt5_operator_handoff_next_step_operator_summary', '')}",
        f"- Watch MT5 operator collect filter: {status_watch.get('mt5_operator_handoff_next_step_collect_filter_summary', '')}",
        f"- Watch MT5 operator quick input: {compact_quick_input_text(status_watch.get('mt5_operator_handoff_quick_input'))}",
        f"- Watch manual Strategy Tester available: {status_watch.get('manual_strategy_tester_available', '')}",
        f"- Watch manual Strategy Tester recommended: {status_watch.get('manual_strategy_tester_recommended', '')}",
        f"- Watch manual Strategy Tester status: {status_watch.get('manual_strategy_tester_status', '')}",
        f"- Watch manual Strategy Tester start after: {status_watch.get('manual_strategy_tester_manual_run_start_after', '')}",
        f"- Watch manual Strategy Tester collect-only: {status_watch.get('manual_strategy_tester_collect_only_command_text', '')}",
        f"- Watch manual Strategy Tester blockers: {compact_list_text(status_watch.get('manual_strategy_tester_auto_launch_blockers'))}",
        f"- Watch manual Strategy Tester note: {status_watch.get('manual_strategy_tester_note', '')}",
        f"- Watch manual test queue: status={status_watch.get('manual_test_queue_status', '')}, "
        f"next_action={status_watch.get('manual_test_queue_next_action', '')}, "
        f"entries={status_watch.get('manual_test_queue_entry_count', '')}, "
        f"total={status_watch.get('manual_test_queue_total_entry_count', '')}, "
        f"stale={status_watch.get('manual_test_queue_stale_entry_count', '')}, "
        f"steps={status_watch.get('manual_test_queue_step_count', '')}, "
        f"waiting={status_watch.get('manual_test_queue_waiting_count', '')}, "
        f"ready={status_watch.get('manual_test_queue_ready_to_collect_count', '')}, "
        f"step_waiting={status_watch.get('manual_test_queue_step_waiting_report_count', '')}, "
        f"step_launch_needed={status_watch.get('manual_test_queue_step_launch_needed_count', '')}",
        f"- Watch manual test queue current gate: current_for_execution="
        f"{status_watch.get('manual_test_queue_current_for_execution_count', '')}, "
        f"selected_action_current={status_watch.get('manual_test_queue_selected_action_current_count', '')}, "
        f"selected_action_stale={status_watch.get('manual_test_queue_selected_action_stale_count', '')}, "
        f"current_gate={compact_list_text(status_watch.get('manual_test_queue_current_promotion_generated_at_values'))}, "
        f"current_decision={compact_list_text(status_watch.get('manual_test_queue_current_promotion_decision_values'))}, "
        f"gate_stale={compact_list_text(status_watch.get('manual_test_queue_gate_stale_reasons'))}, "
        f"not_current={compact_list_text(status_watch.get('manual_test_queue_not_current_entry_ids'))}",
        (
            "- Watch manual test queue run start: "
            f"marked={status_watch.get('manual_test_queue_manual_run_start_marked', '')}, "
            f"this_run={status_watch.get('manual_test_queue_manual_run_start_marked_this_run', '')}, "
            f"preserved={status_watch.get('manual_test_queue_manual_run_start_preserved', '')}, "
            f"effective_after={compact_list_text(status_watch.get('manual_test_queue_manual_run_start_effective_after_values'))}"
        ),
        f"- Watch manual test queue blockers: {compact_list_text(status_watch.get('manual_test_queue_blocking_reasons'))}",
        f"- Watch manual test queue next step: {status_watch.get('manual_test_queue_next_step_operator_summary', '')}",
        f"- Watch manual test queue collect filter: {status_watch.get('manual_test_queue_next_step_collect_filter_summary', '')}",
        f"- Watch manual test queue quick input: {compact_quick_input_text(status_watch.get('manual_test_queue_operator_handoff_quick_input'))}",
        *format_status_watch_manual_queue_target_lines(
            status_watch.get("manual_test_queue_strategy_tester_targets")
        ),
        *format_status_watch_manual_queue_operation_card_lines(
            status_watch.get("manual_test_queue_operation_cards")
        ),
        *format_status_watch_manual_queue_checklist_lines(
            status_watch.get("manual_test_queue_execution_checklist")
        ),
        (
            f"- Watch manual queue launch: status={status_watch.get('manual_queue_launch_status', '')}, "
            f"next_action={status_watch.get('manual_queue_launch_next_action', '')}, "
            f"selected={status_watch.get('manual_queue_launch_selected', '')}, "
            f"kind={status_watch.get('manual_queue_launch_launch_command_kind', '')}, "
            f"blocked={status_watch.get('manual_queue_launch_blocked', '')}, "
            f"running_terminal_count={status_watch.get('manual_queue_launch_running_terminal_count', '')}"
        ),
        f"- Watch manual queue launch refresh: enabled={status_watch.get('manual_queue_launch_refresh_enabled', '')}, "
        f"returncode={status_watch.get('manual_queue_launch_refresh_returncode', '')}, "
        f"completed={status_watch.get('manual_queue_launch_refresh_completed', '')}, "
        f"status={status_watch.get('manual_queue_launch_refresh_status', '')}, "
        f"queue_refresh={status_watch.get('manual_queue_launch_refresh_queue_refresh_status', '')}, "
        f"queue_refresh_sources={status_watch.get('manual_queue_launch_refresh_queue_refresh_source_count', '')}, "
        f"selected={status_watch.get('manual_queue_launch_refresh_selected_queue_id', '')}/"
        f"{status_watch.get('manual_queue_launch_refresh_selected_step_label', '')}, "
        f"blocked={status_watch.get('manual_queue_launch_refresh_blocked', '')}, "
        f"blockers={compact_list_text(status_watch.get('manual_queue_launch_refresh_blocked_reasons'))}",
        f"- Watch manual queue launch blockers: {compact_list_text(status_watch.get('manual_queue_launch_blocked_reasons'))}",
        (
            f"- Watch manual queue launch selected: "
            f"{(status_watch.get('manual_queue_launch_selected_item') if isinstance(status_watch.get('manual_queue_launch_selected_item'), dict) else {}).get('queue_id', '')}/"
            f"{(status_watch.get('manual_queue_launch_selected_item') if isinstance(status_watch.get('manual_queue_launch_selected_item'), dict) else {}).get('step_label', '')}, "
            f"forward={(status_watch.get('manual_queue_launch_selected_item') if isinstance(status_watch.get('manual_queue_launch_selected_item'), dict) else {}).get('forward', '')}, "
            f"report={(status_watch.get('manual_queue_launch_selected_item') if isinstance(status_watch.get('manual_queue_launch_selected_item'), dict) else {}).get('report', '')}, "
            f"fingerprint={(status_watch.get('manual_queue_launch_selected_item') if isinstance(status_watch.get('manual_queue_launch_selected_item'), dict) else {}).get('step_fingerprint', '')}"
        ),
        f"- Watch manual queue launch quick input: {compact_quick_input_text(status_watch.get('manual_queue_launch_queue_operator_handoff_quick_input'))}",
        f"- Watch manual queue launch command: {status_watch.get('manual_queue_launch_command_text', '')}",
        f"- Watch manual collect run: status={status_watch.get('manual_collect_run_status', '')}, "
        f"next_action={status_watch.get('manual_collect_run_next_action', '')}, "
        f"selected={status_watch.get('manual_collect_run_selected_count', '')}, "
        f"waiting={status_watch.get('manual_collect_run_waiting_count', '')}, "
        f"invalid={status_watch.get('manual_collect_run_invalid_count', '')}, "
        f"execute={status_watch.get('manual_collect_run_execute', '')}, "
        f"dry_run={status_watch.get('manual_collect_run_dry_run', '')}",
        f"- Watch manual collect queue refresh: status={status_watch.get('manual_collect_run_queue_refresh_status', '')}, "
        f"enabled={status_watch.get('manual_collect_run_queue_refresh_enabled', '')}, "
        f"sources={status_watch.get('manual_collect_run_queue_refresh_source_count', '')}",
        (
            f"- Watch manual collect queue progress: steps={status_watch.get('manual_collect_run_queue_step_count', '')}, "
            f"report_ready={status_watch.get('manual_collect_run_queue_step_report_ready_count', '')}, "
            f"waiting={status_watch.get('manual_collect_run_queue_step_waiting_report_count', '')}, "
            f"launch_needed={status_watch.get('manual_collect_run_queue_step_launch_needed_count', '')}"
        ),
        (
            f"- Watch manual collect handoff: state={status_watch.get('manual_collect_run_handoff_state', '')}, "
            f"ready={compact_list_text(status_watch.get('manual_collect_run_handoff_ready_ids'))}, "
            f"waiting={compact_list_text(status_watch.get('manual_collect_run_handoff_waiting_ids'))}, "
            f"invalid={compact_list_text(status_watch.get('manual_collect_run_handoff_invalid_ids'))}"
        ),
        (
            f"- Watch manual collect next MT5 step: "
            f"{(status_watch.get('manual_collect_run_handoff_next_mt5_step') if isinstance(status_watch.get('manual_collect_run_handoff_next_mt5_step'), dict) else {}).get('queue_id', '')}/"
            f"{(status_watch.get('manual_collect_run_handoff_next_mt5_step') if isinstance(status_watch.get('manual_collect_run_handoff_next_mt5_step'), dict) else {}).get('step_label', '')}, "
            f"forward={(status_watch.get('manual_collect_run_handoff_next_mt5_step') if isinstance(status_watch.get('manual_collect_run_handoff_next_mt5_step'), dict) else {}).get('forward', '')}, "
            f"inputs={(status_watch.get('manual_collect_run_handoff_next_mt5_step') if isinstance(status_watch.get('manual_collect_run_handoff_next_mt5_step'), dict) else {}).get('inputs', '')}, "
            f"report={(status_watch.get('manual_collect_run_handoff_next_mt5_step') if isinstance(status_watch.get('manual_collect_run_handoff_next_mt5_step'), dict) else {}).get('report', '')}"
        ),
        f"- Watch manual collect quick input: {compact_quick_input_text(status_watch.get('manual_collect_run_handoff_quick_input'))}",
        f"- Watch manual collect dry-run command: {status_watch.get('manual_collect_run_handoff_dry_run_command_text', '')}",
        f"- Watch manual collect execute command: {status_watch.get('manual_collect_run_handoff_execute_command_text', '')}",
        f"- Watch manual collect refresh: enabled={status_watch.get('manual_collect_refresh_enabled', '')}, "
        f"returncode={status_watch.get('manual_collect_refresh_returncode', '')}, "
        f"completed={status_watch.get('manual_collect_refresh_completed', '')}, "
        f"status={status_watch.get('manual_collect_refresh_status', '')}, "
        f"queue_refresh={status_watch.get('manual_collect_refresh_queue_refresh_status', '')}, "
        f"queue_refresh_ok={status_watch.get('manual_collect_refresh_queue_refresh_ok', '')}, "
        f"queue_refresh_sources={status_watch.get('manual_collect_refresh_queue_refresh_source_count', '')}, "
        f"selected={status_watch.get('manual_collect_refresh_selected_count', '')}, "
        f"waiting={status_watch.get('manual_collect_refresh_waiting_count', '')}, "
        f"invalid={status_watch.get('manual_collect_refresh_invalid_count', '')}",
        f"- Watch manual auto collect: status={status_watch.get('manual_auto_collect_watch_status', '')}, "
        f"next_action={status_watch.get('manual_auto_collect_watch_next_action', '')}, "
        f"execute_ready={status_watch.get('manual_auto_collect_watch_execute_ready', '')}, "
        f"ready_to_execute={status_watch.get('manual_auto_collect_watch_ready_to_execute', '')}, "
        f"ready_for_collect_execute={status_watch.get('manual_auto_collect_watch_ready_for_collect_execute', '')}, "
        f"selected={status_watch.get('manual_auto_collect_watch_selected_count', '')}, "
        f"waiting={status_watch.get('manual_auto_collect_watch_waiting_count', '')}, "
        f"invalid={status_watch.get('manual_auto_collect_watch_invalid_count', '')}, "
        f"queue_launch={status_watch.get('manual_auto_collect_watch_queue_launch_status', '')}, "
        f"queue_launch_blocked={status_watch.get('manual_auto_collect_watch_queue_launch_blocked', '')}, "
        f"next_queue_step={status_watch.get('manual_auto_collect_watch_operator_packet_next_queue_step', '')}, "
        f"execution={status_watch.get('manual_auto_collect_watch_execution_status', '')}",
        f"- Watch manual auto collect operator decision: "
        f"verdict={status_watch.get('manual_auto_collect_watch_operator_packet_strategy_operator_decision_verdict', '')}, "
        f"status={status_watch.get('manual_auto_collect_watch_operator_packet_strategy_operator_decision_status', '')}, "
        f"adoptable={status_watch.get('manual_auto_collect_watch_operator_packet_strategy_operator_decision_adoptable', '')}, "
        f"blocker={status_watch.get('manual_auto_collect_watch_operator_packet_strategy_operator_decision_primary_blocker', '')}, "
        f"next={status_watch.get('manual_auto_collect_watch_operator_packet_strategy_operator_decision_next_action', '')}",
        (
            "- Watch manual auto collect operator command: "
            f"{status_watch.get('manual_auto_collect_watch_operator_packet_strategy_operator_decision_command_text', '')}"
        ),
        f"- Watch optimization queue: status={status_watch.get('manual_test_queue_with_optimization_status', '')}, "
        f"next_action={status_watch.get('manual_test_queue_with_optimization_next_action', '')}, "
        f"progress={status_watch.get('manual_test_queue_with_optimization_progress_state', '')}, "
        f"entries={status_watch.get('manual_test_queue_with_optimization_entry_count', '')}, "
        f"steps={status_watch.get('manual_test_queue_with_optimization_step_count', '')}, "
        f"ready={status_watch.get('manual_test_queue_with_optimization_ready_to_collect_count', '')}, "
        f"waiting={status_watch.get('manual_test_queue_with_optimization_waiting_count', '')}, "
        f"step_ready={status_watch.get('manual_test_queue_with_optimization_step_report_ready_count', '')}, "
        f"step_collect_ready={status_watch.get('manual_test_queue_with_optimization_step_collect_ready_count', '')}, "
        f"step_waiting={status_watch.get('manual_test_queue_with_optimization_step_waiting_report_count', '')}, "
        f"launch_needed={status_watch.get('manual_test_queue_with_optimization_step_launch_needed_count', '')}",
        (
            "- Watch optimization queue step IDs: "
            f"report_ready={compact_list_text(status_watch.get('manual_test_queue_with_optimization_step_report_ready_ids'))}, "
            f"collect_ready={compact_list_text(status_watch.get('manual_test_queue_with_optimization_step_collect_ready_ids'))}, "
            f"waiting_report={compact_list_text(status_watch.get('manual_test_queue_with_optimization_step_waiting_report_ids'))}, "
            f"launch_needed={compact_list_text(status_watch.get('manual_test_queue_with_optimization_step_launch_needed_ids'))}"
        ),
        (
            "- Watch optimization queue collect check: "
            f"{status_watch.get('manual_test_queue_with_optimization_collect_check_command_text', '')}"
        ),
        (
            "- Watch optimization queue run start: "
            f"marked={status_watch.get('manual_test_queue_with_optimization_manual_run_start_marked', '')}, "
            f"this_run={status_watch.get('manual_test_queue_with_optimization_manual_run_start_marked_this_run', '')}, "
            f"preserved={status_watch.get('manual_test_queue_with_optimization_manual_run_start_preserved', '')}, "
            f"effective_after={compact_list_text(status_watch.get('manual_test_queue_with_optimization_manual_run_start_effective_after_values'))}"
        ),
        f"- Watch optimization queue launch: status={status_watch.get('manual_queue_launch_with_optimization_status', '')}, "
        f"next_action={status_watch.get('manual_queue_launch_with_optimization_next_action', '')}, "
        f"selected={status_watch.get('manual_queue_launch_with_optimization_selected', '')}, "
        f"kind={status_watch.get('manual_queue_launch_with_optimization_launch_command_kind', '')}, "
        f"blocked={status_watch.get('manual_queue_launch_with_optimization_blocked', '')}, "
        f"blockers={compact_list_text(status_watch.get('manual_queue_launch_with_optimization_blocked_reasons'))}",
        f"- Watch optimization queue launch refresh: enabled={status_watch.get('manual_queue_launch_with_optimization_refresh_enabled', '')}, "
        f"returncode={status_watch.get('manual_queue_launch_with_optimization_refresh_returncode', '')}, "
        f"completed={status_watch.get('manual_queue_launch_with_optimization_refresh_completed', '')}, "
        f"status={status_watch.get('manual_queue_launch_with_optimization_refresh_status', '')}, "
        f"queue_refresh={status_watch.get('manual_queue_launch_with_optimization_refresh_queue_refresh_status', '')}, "
        f"queue_refresh_ok={status_watch.get('manual_queue_launch_with_optimization_refresh_queue_refresh_ok', '')}, "
        f"selected={status_watch.get('manual_queue_launch_with_optimization_refresh_selected_queue_id', '')}/"
        f"{status_watch.get('manual_queue_launch_with_optimization_refresh_selected_step_label', '')}, "
        f"blocked={status_watch.get('manual_queue_launch_with_optimization_refresh_blocked', '')}, "
        f"blockers={compact_list_text(status_watch.get('manual_queue_launch_with_optimization_refresh_blocked_reasons'))}",
        f"- Watch optimization collect: status={status_watch.get('manual_collect_with_optimization_status', '')}, "
        f"next_action={status_watch.get('manual_collect_with_optimization_next_action', '')}, "
        f"selected={status_watch.get('manual_collect_with_optimization_selected_count', '')}, "
        f"waiting={status_watch.get('manual_collect_with_optimization_waiting_count', '')}, "
        f"invalid={status_watch.get('manual_collect_with_optimization_invalid_count', '')}, "
        f"steps={status_watch.get('manual_collect_with_optimization_queue_step_count', '')}, "
        f"step_waiting={status_watch.get('manual_collect_with_optimization_queue_step_waiting_report_count', '')}, "
        f"step_launch_needed={status_watch.get('manual_collect_with_optimization_queue_step_launch_needed_count', '')}",
        f"- Watch optimization collect refresh: enabled={status_watch.get('manual_collect_with_optimization_refresh_enabled', '')}, "
        f"returncode={status_watch.get('manual_collect_with_optimization_refresh_returncode', '')}, "
        f"completed={status_watch.get('manual_collect_with_optimization_refresh_completed', '')}, "
        f"status={status_watch.get('manual_collect_with_optimization_refresh_status', '')}, "
        f"queue_refresh={status_watch.get('manual_collect_with_optimization_refresh_queue_refresh_status', '')}, "
        f"queue_refresh_ok={status_watch.get('manual_collect_with_optimization_refresh_queue_refresh_ok', '')}, "
        f"queue_refresh_sources={status_watch.get('manual_collect_with_optimization_refresh_queue_refresh_source_count', '')}, "
        f"selected={status_watch.get('manual_collect_with_optimization_refresh_selected_count', '')}, "
        f"waiting={status_watch.get('manual_collect_with_optimization_refresh_waiting_count', '')}, "
        f"invalid={status_watch.get('manual_collect_with_optimization_refresh_invalid_count', '')}",
        f"- Watch next action target: {status_watch.get('next_action_run_target', '')}",
        f"- Watch next action config: {status_watch.get('next_action_run_config', '')}",
        f"- Watch next action timeout: {status_watch.get('next_action_run_timeout_minutes', '')} min ({status_watch.get('next_action_run_timeout_seconds', '')} sec)",
        f"- Watch next action deadline if started now: {status_watch.get('next_action_run_timeout_deadline_if_started_now', '')}",
        f"- Watch next action passes: {status_watch.get('next_action_run_estimated_full_factorial_passes', '')}",
        f"- Watch next action execute command: {status_watch.get('next_action_run_execute_command_text', '')}",
        f"- Watch next action collect-only command: {status_watch.get('next_action_run_collect_only_command_text', '')}",
        f"- Watch next action manual collect-only: {status_watch.get('next_action_run_manual_collect_only_command_text', '')}",
        f"- Watch next action manual tester: start_after={status_watch.get('next_action_run_manual_run_start_after', '')}, steps={status_watch.get('next_action_run_manual_step_count', '')}",
        f"- Watch next action manual collect readiness: ready={status_watch.get('next_action_run_manual_collect_ready', '')}, "
        f"status={status_watch.get('next_action_run_manual_collect_status', '')}, "
        f"csv={status_watch.get('next_action_run_manual_collect_csv_count', '')}, "
        f"modified_after={status_watch.get('next_action_run_manual_collect_modified_after', '')}, "
        f"next_action={status_watch.get('next_action_run_manual_collect_next_action', '')}, "
        f"reason={status_watch.get('next_action_run_manual_collect_reason', '')}, "
        f"blocking={compact_list_text(status_watch.get('next_action_run_manual_collect_blocking_reasons'))}",
        f"- Watch action context keys: {compact_list_text(status_watch.get('next_action_run_action_context_keys'))}",
        f"- Watch related execution count: {status_watch.get('next_action_run_related_execution_count', '')}",
        f"- Watch related execution keys: {compact_list_text(status_watch.get('next_action_run_related_execution_keys'))}",
        f"- Watch blocking prior action count: {status_watch.get('next_action_run_blocking_prior_action_count', '')}",
        f"- Watch advisory prior action count: {status_watch.get('next_action_run_advisory_prior_action_count', '')}",
        (
            "- Watch score weight follow-up: "
            f"status={status_watch.get('next_action_run_score_weight_follow_up_status', '')}, "
            f"regime_status={status_watch.get('next_action_run_score_weight_follow_up_regime_status', '')}, "
            f"sample_shortage={status_watch.get('next_action_run_score_weight_follow_up_sample_shortage', '')}, "
            f"walk_missing={status_watch.get('next_action_run_score_weight_follow_up_walk_missing', '')}/"
            f"{status_watch.get('next_action_run_score_weight_follow_up_walk_required', '')}, "
            f"regime_missing={status_watch.get('next_action_run_score_weight_follow_up_regime_missing', '')}/"
            f"{status_watch.get('next_action_run_score_weight_follow_up_regime_required', '')}"
        ),
        (
            "- Watch score weight set: "
            f"walk_forward={status_watch.get('next_action_run_score_weight_set_walk_forward_status', '')}, "
            f"skip_reason={status_watch.get('next_action_run_score_weight_set_skip_reason', '')}"
        ),
        *status_watch_planned_output_bundle_lines,
        *status_watch_primary_output_lines,
        *status_watch_archive_output_lines,
        *status_watch_follow_up_output_lines,
        *status_watch_follow_up_archive_output_lines,
        f"- Back/Forward evidence state: {status_watch.get('back_forward_run_evidence_state', '')}",
        *status_watch_back_forward_lines,
        f"- Restart hint: {status_watch.get('restart_hint', '')}",
        "",
        "## Latest Tester Run",
        "",
        f"- Exists: {latest.get('exists')}",
        f"- Generated at: {latest.get('generated_at', '')}",
        f"- OK: {latest.get('ok', '')}",
        f"- Blocked: {latest.get('blocked', '')}",
        f"- Blocked components: {latest.get('blocked_components', {})}",
        f"- Terminal failed: {latest.get('terminal_failed', '')}",
        f"- Terminal started at: {latest.get('terminal_started_at', '')}",
        f"- Terminal deadline at: {latest.get('terminal_deadline_at', '')}",
        f"- Terminal elapsed seconds: {latest.get('terminal_elapsed_seconds', '')}",
        f"- Terminal returncode: {latest.get('terminal_returncode', '')}",
        f"- Terminal timeout: {latest.get('terminal_timeout', '')}",
        f"- Report source: {latest.get('report_source', '')}",
        f"- Source time blocked: {latest.get('source_time_blocked', '')}",
        f"- Agent CSV archive run ID: {latest.get('agent_csv_archive_run_id', '')}",
        f"- Risk preset OK: {latest.get('risk_preset_ok', '')}",
        f"- Risk preset schema required: {latest.get('risk_preset_schema_required', '')}",
        f"- Risk preset schema status: {latest.get('risk_preset_schema_status', '')}",
        f"- Risk preset schema current: {latest.get('risk_preset_schema_current', '')}",
        f"- Risk preset schema missing inputs: {compact_list_text(latest.get('risk_preset_schema_missing_inputs'))}",
        f"- Target tester set synced: {(latest.get('target_tester_set_sync') if isinstance(latest.get('target_tester_set_sync'), dict) else {}).get('synced', '')}",
        f"- Target tester set status: {(latest.get('target_tester_set_sync') if isinstance(latest.get('target_tester_set_sync'), dict) else {}).get('status', '')}",
        f"- Compiled fresh: {latest.get('compiled_fresh', '')}",
        f"- Tester sets synced: {latest.get('tester_sets_synced', '')}",
        "",
        "## Pass Budget",
        "",
        "| key | value |",
        "|---|---|",
        *format_pass_rows(pass_budget),
        "",
        "## MT5 Next Action Runner",
        "",
        f"- Exists: {next_runner.get('exists')}",
        f"- Runner generated at: {next_runner.get('runner_generated_at', '')}",
        f"- Runner promotion generated at: {next_runner.get('runner_promotion_generated_at', '')}",
        f"- Current promotion generated at: {next_runner.get('current_promotion_generated_at', '')}",
        f"- Promotion gate current: {next_runner.get('promotion_gate_current', '')}",
        f"- Promotion gate generated_at match: {next_runner.get('promotion_gate_generated_at_match', '')}",
        f"- Promotion gate decision match: {next_runner.get('promotion_gate_decision_match', '')}",
        f"- Selected action present: {next_runner.get('selected_action_present', '')}",
        f"- Selected action current: {next_runner.get('selected_action_current', '')}",
        f"- Current for execution: {next_runner.get('current_for_execution', '')}",
        f"- Gate stale reason: {next_runner.get('gate_stale_reason', '')}",
        f"- Selected action mismatches: {compact_list_text(next_runner.get('selected_action_mismatches'))}",
        f"- Blocking prior action count: {next_runner.get('blocking_prior_action_count', '')}",
        f"- Advisory prior action count: {next_runner.get('advisory_prior_action_count', '')}",
        f"- OK: {next_runner.get('ok', '')}",
        f"- Dry run: {next_runner.get('dry_run', '')}",
        f"- Target: {next_runner.get('target', '')}",
        f"- Found: {next_runner.get('found', '')}",
        f"- Action reason: {next_runner.get('action_reason', '')}",
        f"- Action context keys: {compact_list_text(next_runner.get('action_context_keys'))}",
        f"- Related execution keys: {compact_list_text(next_runner.get('related_execution_keys'))}",
        *blocking_prior_action_lines,
        *advisory_prior_action_lines,
        f"- Kind: {next_runner.get('kind', '')}",
        f"- Focus side: {next_runner.get('focus_side', '')}",
        f"- Optimization mode: {next_runner.get('optimization_mode', '')}",
        f"- Config: {next_runner.get('config', '')}",
        f"- Set: {next_runner.get('set', '')}",
        f"- Output set: {next_runner.get('output_set', '')}",
        *primary_output_lines,
        f"- Archive run ID: {next_runner.get('agent_csv_archive_run_id', '')}",
        f"- Timeout: {next_runner.get('timeout_minutes', '')} min ({next_runner.get('timeout_seconds', '')} sec)",
        f"- Timeout start reference: {next_runner.get('timeout_start_reference_at', '')}",
        f"- Timeout deadline if started now: {next_runner.get('timeout_deadline_if_started_now', '')}",
        f"- Timeout note: {next_runner.get('timeout_note', '')}",
        f"- Primary note: {next_runner.get('primary_note', '')}",
        f"- Runner execute command: {next_runner.get('execute_command_text', '')}",
        f"- Manual collect-only command: {next_runner.get('collect_only_command_text', '')}",
        f"- Manual collect note: {next_runner.get('collect_only_note', '')}",
        f"- Manual Strategy Tester available: {next_runner.get('manual_strategy_tester_available', '')}",
        f"- Manual Strategy Tester start after: {next_runner.get('manual_run_start_after', '')}",
        f"- Manual Strategy Tester collect-only: {next_runner.get('manual_collect_only_command_text', '')}",
        f"- Manual Strategy Tester note: {next_runner.get('manual_collect_only_note', '')}",
        f"- Manual collect readiness: ready={next_runner.get('manual_collect_ready', '')}, "
        f"status={next_runner.get('manual_collect_status', '')}, "
        f"csv={next_runner.get('manual_collect_csv_count', '')}, "
        f"modified_after={next_runner.get('manual_collect_modified_after', '')}",
        f"- Manual collect reason: {next_runner.get('manual_collect_reason', '')}",
        f"- Manual collect blocking reasons: {compact_list_text(next_runner.get('manual_collect_blocking_reasons'))}",
        f"- Manual collect next action: {next_runner.get('manual_collect_next_action', '')}",
        f"- Evidence role: {next_runner.get('evidence_role', '')}",
        f"- Diagnostic only: {next_runner.get('diagnostic_only', '')}",
        f"- Promotion evidence: {next_runner.get('promotion_evidence', '')}",
        f"- Score weight follow-up status: {next_runner.get('score_weight_follow_up_status', '')}",
        f"- Score weight follow-up regime: {next_runner.get('score_weight_follow_up_regime_dimension', '')} {next_runner.get('score_weight_follow_up_regime_group', '')} / {next_runner.get('score_weight_follow_up_regime_status', '')}",
        f"- Score weight sample shortage: {next_runner.get('score_weight_follow_up_sample_shortage', '')}",
        f"- Score weight walk-forward shortage: {next_runner.get('score_weight_follow_up_walk_missing', '')}/{next_runner.get('score_weight_follow_up_walk_required', '')}, folds {next_runner.get('score_weight_follow_up_walk_folds', '')}/{next_runner.get('score_weight_follow_up_walk_required_folds', '')}",
        f"- Score weight regime shortage: {next_runner.get('score_weight_follow_up_regime_missing', '')}/{next_runner.get('score_weight_follow_up_regime_required', '')}, folds {next_runner.get('score_weight_follow_up_regime_folds', '')}/{next_runner.get('score_weight_follow_up_regime_required_folds', '')}",
        f"- Score weight set walk-forward: {next_runner.get('score_weight_set_walk_forward_status', '')}",
        f"- Score weight set skip reason: {next_runner.get('score_weight_set_skip_reason', '')}",
        f"- Score weight top candidate: threshold={next_runner.get('score_weight_set_top_candidate_threshold', '')}, pf={next_runner.get('score_weight_set_top_candidate_pf', '')}, count={next_runner.get('score_weight_set_top_candidate_count', '')}, weights={next_runner.get('score_weight_set_top_candidate_weights', '')}",
        f"- Score weight recommendation: {next_runner.get('score_weight_follow_up_recommendation', '')}",
        f"- Optimized input count: {next_runner.get('optimized_input_count', '')}",
        f"- Estimated full-factorial passes: {next_runner.get('estimated_full_factorial_passes', '')}",
        f"- Latest executed Tester XML rows: {recent_xml_rows_text(next_runner.get('latest_executed_tester_xml_rows'))}",
        "",
        "| order | step | expert | symbol | period | model | dates | forward | window | optimization | run type | expected report | inputs | report | fingerprint |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        *format_manual_strategy_tester_rows(next_runner.get("manual_steps")),
        "",
        f"- Primary execution class: {next_runner.get('primary_execution_class', '')}",
        f"- Primary is MT5 tester run: {next_runner.get('primary_is_mt5_tester_run', '')}",
        f"- Allow non-tester primary: {next_runner.get('allow_non_tester_primary', '')}",
        f"- Run archive preview: {next_runner.get('run_archive_preview', '')}",
        *archive_output_lines,
        f"- Archive preview OK: {next_runner.get('archive_preview_ok', '')}",
        f"- Archive preview returncode: {next_runner.get('archive_preview_returncode', '')}",
        f"- Primary executed: {next_runner.get('primary_executed', '')}",
        f"- Primary OK: {next_runner.get('primary_ok', '')}",
        f"- Primary returncode: {next_runner.get('primary_returncode', '')}",
        f"- Run follow-up: {next_runner.get('run_follow_up', '')}",
        f"- Follow-up kind: {next_runner.get('follow_up_kind', '')}",
        f"- Follow-up output: {next_runner.get('follow_up_output_set', '')}",
        *follow_up_output_lines,
        *follow_up_archive_output_lines,
        f"- Follow-up archive preview OK: {next_runner.get('follow_up_archive_preview_ok', '')}",
        f"- Follow-up archive preview returncode: {next_runner.get('follow_up_archive_preview_returncode', '')}",
        f"- Follow-up executed: {next_runner.get('follow_up_executed', '')}",
        f"- Follow-up OK: {next_runner.get('follow_up_ok', '')}",
        f"- Follow-up returncode: {next_runner.get('follow_up_returncode', '')}",
        f"- Follow-up skipped: {next_runner.get('follow_up_skipped', '')}",
        *related_execution_lines,
        *archive_preview_post_lines,
        *primary_post_lines,
        *follow_up_archive_preview_post_lines,
        *follow_up_post_lines,
        *post_validation_lines,
        f"- Blocked before primary: {next_runner.get('blocked_before_primary', '')}",
        f"- Blocked before follow-up: {next_runner.get('blocked_before_follow_up', '')}",
        f"- Blocked after primary: {next_runner.get('blocked_after_primary', '')}",
        f"- Blocked after follow-up: {next_runner.get('blocked_after_follow_up', '')}",
        f"- Reason: {next_runner.get('reason', '')}",
        f"- Next action execution ready: {next_execution.get('ready', '')}",
        f"- Next action execution status: {next_execution.get('status', '')}",
        f"- Next action execution blockers: {compact_list_text(next_execution.get('reasons'))}",
        f"- Required fresh artifacts: {', '.join(next_execution.get('required_fresh_artifacts', []))}",
        f"- Stale required artifacts: {compact_list_text(next_execution.get('stale_required_artifacts'))}",
        f"- Runner execute hint: {next_execution.get('runner_execute_hint', '')}",
        f"- Runner collect-only hint: {next_execution.get('collect_only_hint', '')}",
        f"- Next local execution ready: {next_local_execution.get('ready', '')}",
        f"- Next local execution status: {next_local_execution.get('status', '')}",
        f"- Next local execution blockers: {compact_list_text(next_local_execution.get('reasons'))}",
        f"- Local required fresh artifacts: {', '.join(next_local_execution.get('required_fresh_artifacts', []))}",
        f"- Local stale required artifacts: {compact_list_text(next_local_execution.get('stale_required_artifacts'))}",
        f"- Local optimization report current: {local_optimization_evidence.get('current', '')}",
        f"- Local optimization report status: {local_optimization_evidence.get('status', '')}",
        f"- Local optimization report reasons: {compact_list_text(local_optimization_evidence.get('reasons'))}",
        f"- Local optimization report generated at: {local_optimization_evidence.get('report_generated_at', '')}",
        f"- Local tester optimization generated at: {local_optimization_evidence.get('tester_optimization_generated_at', '')}",
        f"- Local runner execute hint: {next_local_execution.get('runner_execute_hint', '')}",
        f"- Command: {next_runner.get('command_text', '')}",
        f"- Follow-up command: {next_runner.get('follow_up_command_text', '')}",
        "",
        "## MT5 Back/Forward Runner",
        "",
        f"- Exists: {back_forward_runner.get('exists')}",
        f"- Generated at: {back_forward_runner.get('generated_at', '')}",
        f"- OK: {back_forward_runner.get('ok', '')}",
        f"- Dry run: {back_forward_runner.get('dry_run', '')}",
        f"- Execute: {back_forward_runner.get('execute', '')}",
        f"- Collect only: {back_forward_runner.get('collect_only', '')}",
        f"- Launch MT5: {back_forward_runner.get('launch_mt5', '')}",
        f"- Run archive preview: {back_forward_runner.get('run_archive_preview', '')}",
        f"- Evidence state: {back_forward_runner.get('evidence_state', '')}",
        f"- Mode: {back_forward_runner.get('mode', '')}",
        f"- Run ID prefix: {back_forward_runner.get('run_id_prefix', '')}",
        f"- Manual Strategy Tester available: {back_forward_runner.get('manual_strategy_tester_available', '')}",
        f"- Manual run start after: {back_forward_runner.get('manual_run_start_after', '')}",
        f"- Manual collect-only command: {back_forward_runner.get('manual_collect_only_command_text', '')}",
        f"- Manual collect-only note: {back_forward_runner.get('manual_collect_only_note', '')}",
        f"- Manual collect readiness: ready={back_forward_runner.get('manual_collect_ready', '')}, "
        f"status={back_forward_runner.get('manual_collect_status', '')}, "
        f"csv={back_forward_runner.get('manual_collect_csv_count', '')}, "
        f"modified_after={back_forward_runner.get('manual_collect_modified_after', '')}",
        f"- Manual collect reason: {back_forward_runner.get('manual_collect_reason', '')}",
        f"- Manual collect blocking reasons: {compact_list_text(back_forward_runner.get('manual_collect_blocking_reasons'))}",
        f"- Manual collect next action: {back_forward_runner.get('manual_collect_next_action', '')}",
        f"- Manual step count: {back_forward_runner.get('manual_step_count', '')}",
        f"- MT5 Quick Start available: {back_forward_runner.get('mt5_strategy_tester_pack_available', '')}",
        f"- MT5 Quick Start ready: {back_forward_runner.get('mt5_strategy_tester_pack_ready_for_manual_mt5_run', '')}",
        f"- MT5 Quick Start status: {back_forward_runner.get('mt5_strategy_tester_pack_status', '')}",
        f"- MT5 Quick Start next action: {back_forward_runner.get('mt5_strategy_tester_pack_next_action', '')}",
        f"- MT5 Quick Start pair: {back_forward_runner.get('mt5_strategy_tester_pack_is_back_forward_pair', '')}",
        f"- MT5 Quick Start start after: {back_forward_runner.get('mt5_strategy_tester_pack_manual_run_start_after', '')}",
        f"- MT5 Quick Start collect ready: {back_forward_runner.get('mt5_strategy_tester_pack_collect_ready', '')}",
        f"- MT5 Quick Start collect status: {back_forward_runner.get('mt5_strategy_tester_pack_collect_status', '')}",
        f"- MT5 Quick Start collect reason: {back_forward_runner.get('mt5_strategy_tester_pack_collect_reason', '')}",
        f"- MT5 Quick Start collect command: {back_forward_runner.get('mt5_strategy_tester_pack_collect_command_text', '')}",
        f"- MT5 Quick Start collect note: {back_forward_runner.get('mt5_strategy_tester_pack_collect_note', '')}",
        f"- MT5 Quick Start step count: {back_forward_runner.get('mt5_strategy_tester_pack_step_count', '')}",
        f"- Manual prerequisites ready: {back_forward_runner.get('manual_prerequisites_ready', '')}",
        f"- Manual prerequisites reasons: {compact_list_text(back_forward_runner.get('manual_prerequisites_reasons'))}",
        f"- Manual prerequisites compile status: {back_forward_runner.get('manual_prerequisites_compile_status_path', '')}",
        f"- Manual prerequisites generated at: {back_forward_runner.get('manual_prerequisites_generated_at', '')}",
        f"- Back/Forward plan validation ready: {back_forward_runner.get('back_forward_plan_validation_ready', '')}",
        f"- Back/Forward plan validation status: {back_forward_runner.get('back_forward_plan_validation_status', '')}",
        f"- Back/Forward plan validation reasons: {compact_list_text(back_forward_runner.get('back_forward_plan_validation_reasons'))}",
        f"- Per-step timeout seconds: {back_forward_runner.get('per_step_timeout_seconds', '')}",
        f"- Since minutes: {back_forward_runner.get('since_minutes', '')}",
        f"- Min closed: {back_forward_runner.get('min_closed', '')}",
        f"- Date override: {back_forward_runner.get('from_date', '')} -> {back_forward_runner.get('to_date', '')}",
        f"- Forward mode override: {back_forward_runner.get('forward_mode', '')}",
        f"- Effective dates: {back_forward_runner.get('effective_from_date', '')} -> {back_forward_runner.get('effective_to_date', '')}",
        f"- Effective forward mode: {back_forward_runner.get('effective_forward_mode', '')}",
        f"- Sync ExpertParameters set: {back_forward_runner.get('sync_expert_parameters_set', '')}",
        f"- Allow running terminal: {back_forward_runner.get('allow_running_terminal', '')}",
        f"- Allow stale compile: {back_forward_runner.get('allow_stale_compile', '')}",
        f"- Allow invalid risk preset: {back_forward_runner.get('allow_invalid_risk_preset', '')}",
        f"- Total timeout: {back_forward_runner.get('total_timeout_minutes', '')} min ({back_forward_runner.get('total_timeout_seconds', '')} sec)",
        f"- Execution window complete: {back_forward_runner.get('execution_window_complete', '')}",
        f"- Timeout start reference: {back_forward_runner.get('timeout_start_reference_at', '')}",
        f"- Timeout deadline if started now: {back_forward_runner.get('timeout_deadline_if_started_now', '')}",
        f"- Timeout note: {back_forward_runner.get('timeout_note', '')}",
        f"- Blocked before steps: {back_forward_runner.get('blocked_before_steps', '')}",
        f"- Reason: {back_forward_runner.get('reason', '')}",
        f"- Ready status OK: {back_forward_runner.get('ready_status_ok', '')}",
        f"- Ready status path: {back_forward_runner.get('ready_status_path', '')}",
        f"- Ready status age seconds: {back_forward_runner.get('ready_status_age_seconds', '')}",
        f"- Ready status reasons: {compact_list_text(back_forward_runner.get('ready_status_reasons'))}",
        f"- Ready status mismatches: {compact_list_text(back_forward_runner.get('ready_status_mismatches'))}",
        f"- Ready status checked step keys: {compact_list_text(back_forward_runner.get('ready_status_checked_step_keys'))}",
        f"- Ready status checked options: {compact_list_text(back_forward_runner.get('ready_status_checked_command_options'))}",
        f"- Ready status checked flags: {compact_list_text(back_forward_runner.get('ready_status_checked_command_flags'))}",
        f"- Ready status checked execution conditions: {compact_list_text(back_forward_runner.get('ready_status_checked_execution_conditions'))}",
        f"- Ready status expected execution conditions: {compact_mapping_text(back_forward_runner.get('ready_status_expected_execution_conditions'))}",
        f"- Ready status status execution conditions: {compact_mapping_text(back_forward_runner.get('ready_status_status_execution_conditions'))}",
        f"- Step count: {back_forward_runner.get('step_count', '')}",
        f"- Execution ready: {back_forward_execution.get('ready', '')}",
        f"- Execution status: {back_forward_execution.get('status', '')}",
        f"- Execution blockers: {compact_list_text(back_forward_execution.get('reasons'))}",
        f"- Required fresh artifacts: {', '.join(back_forward_execution.get('required_fresh_artifacts', []))}",
        f"- Stale required artifacts: {compact_list_text(back_forward_execution.get('stale_required_artifacts'))}",
        f"- Execute hint: {back_forward_execution.get('execute_hint', '')}",
        f"- Performance comparison available: {back_forward_runner.get('performance_comparison_available', '')}",
        f"- Performance comparison status: {back_forward_runner.get('performance_comparison_status', '')}",
        f"- Performance comparison thresholds: {compact_mapping_text(back_forward_runner.get('performance_comparison_thresholds'))}",
        "",
        "| order | step | expert | symbol | period | model | dates | forward | window | optimization | run type | expected report | inputs | report | fingerprint |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        *format_manual_strategy_tester_rows(back_forward_runner.get("manual_steps")),
        "",
        "| order | purpose | step | expert | symbol | period | dates | forward | window | optimization | inputs | report | expected | fingerprint |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        *format_mt5_strategy_tester_pack_rows(
            back_forward_runner.get("mt5_strategy_tester_pack_steps")
        ),
        "",
        "| kind | name | status | ready | synced/source | compiled fresh |",
        "|---|---|---|---:|---:|---:|",
        *format_back_forward_prerequisite_rows(back_forward_runner.get("manual_prerequisites")),
        "",
        "| dataset | trades | min ok | pf | avg_r | expectancy_r | max_dd_r | net_profit | trades delta | pf delta | avg_r delta | max_dd delta | net delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        *format_back_forward_comparison_rows(back_forward_runner.get("performance_comparison")),
        "",
        "| step | config | set | forward | report | run_json | report_json | archive_preview_json | preview ok | preview artifact ok | preview count | ok | returncode | artifact required | artifact ok | artifact reasons |",
        "|---|---|---|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
        *format_back_forward_step_rows(back_forward_runner.get("steps")),
        "",
        "## Stable Candidate",
        "",
        f"- Exists: {stable.get('exists')}",
        f"- Report generated at: {stable.get('report_generated_at', '')}",
        f"- Tester generated at: {stable.get('tester_generated_at', '')}",
        f"- Tester OK: {stable.get('tester_ok', '')}",
        f"- Tester blocked: {stable.get('tester_blocked', '')}",
        f"- Tester elapsed seconds: {stable.get('tester_elapsed_seconds', '')}",
        f"- Closed: {stable.get('closed', '')}",
        f"- PF: {stable.get('pf', '')}",
        f"- Avg price R: {stable.get('avg_price_r', '')}",
        f"- Max drawdown price R: {stable.get('max_drawdown_price_r', '')}",
        f"- Positive forward / positive back: {stable.get('positive_forward_positive_back', '')}",
        f"- Positive forward / negative back: {stable.get('positive_forward_negative_back', '')}",
        f"- Recommendation adoptable: {stable.get('recommendation_adoptable', '')}",
        f"- Recommendation reasons: {compact_list_text(stable.get('recommendation_reasons'))}",
        f"- Next set: {stable.get('next_set', '')}",
        f"- Next set skipped write: {stable.get('next_set_skipped_write', '')}",
        f"- Next set skip reason: {stable.get('next_set_skip_reason', '')}",
        f"- Gate refit side: {stable_refit.get('side', '')}",
        f"- Gate refit driver: {stable_refit.get('driver', '')}",
        f"- Gate refit kind: {stable_refit.get('kind', '')}",
        f"- Gate refit config: {stable_refit.get('config', '')}",
        f"- Gate refit set: {stable_refit.get('set', '')}",
        f"- Gate refit output set: {stable_refit.get('output_set', '')}",
        f"- Gate refit archive run ID: {stable_refit.get('agent_csv_archive_run_id', '')}",
        f"- Gate refit reason: {stable_refit.get('reason', '')}",
        f"- Gate refit completed kind: {stable_refit_completed.get('kind', '')}",
        f"- Gate refit completed side: {stable_refit_completed.get('side', '')}",
        f"- Gate refit completed status: {stable_refit_completed.get('status', '')}",
        f"- Gate refit completed PF: {stable_refit_completed.get('pf', '')}",
        f"- Gate refit completed avg price R: {stable_refit_completed.get('avg_price_r', '')}",
        f"- Gate refit completed reasons: {compact_list_text(stable_refit_completed.get('decision_reasons'))}",
        f"- Gate refit completed skip reason: {stable_refit_completed.get('skip_reason', '')}",
        "",
        "## Compile Status",
        "",
        f"- Generated at: {compile_status.get('generated_at', '')}",
        f"- Sources synced: {compile_status.get('all_sources_synced', '')}",
        f"- Compiled fresh: {compile_status.get('all_compiled_fresh', '')}",
        f"- Tester sets synced: {compile_status.get('all_tester_sets_synced', '')}",
        f"- Tester configs synced: {compile_status.get('all_tester_configs_synced', '')}",
        f"- Required tester config references ready: {compile_status.get('all_required_tester_config_references_ready', '')}",
        f"- Unsynced tester sets: {compact_list_text([row.get('name') for row in compile_status.get('unsynced_tester_sets', [])] if isinstance(compile_status.get('unsynced_tester_sets'), list) else [])}",
        f"- Unsynced tester configs: {compact_list_text([row.get('name') for row in compile_status.get('unsynced_tester_configs', [])] if isinstance(compile_status.get('unsynced_tester_configs'), list) else [])}",
        f"- Tester config reference issues: {compact_list_text([str(row.get('name', '')) + ':' + str(row.get('status', '')) for row in compile_status.get('tester_config_reference_issues', [])] if isinstance(compile_status.get('tester_config_reference_issues'), list) else [])}",
        "",
        "## Promotion Gate",
        "",
        f"- Generated at: {gate.get('generated_at', '')}",
        f"- Decision: {gate.get('decision', '')}",
        f"- Live ready: {gate.get('live_ready', '')}",
        f"- Failed checks: {gate.get('failed', '')}",
        f"- Failed check names: {', '.join(gate.get('failed_check_names', [])) if isinstance(gate.get('failed_check_names'), list) else ''}",
        f"- MT5 Back/Forward Gate check: {format_check_summary(gate.get('mt5_back_forward_run_check'))}",
        f"- MT5 Back/Forward performance check: {format_check_summary(gate.get('mt5_back_forward_run_performance_check'))}",
        "",
        "| priority | area | action |",
        "|---:|---|---|",
    ]
    if p1_actions:
        for action in p1_actions:
            if not isinstance(action, dict):
                continue
            lines.append(f"| 1 | {action.get('area', '')} | {action.get('action', '')} |")
    else:
        lines.append("| - |  |  |")
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
    parser = argparse.ArgumentParser(description="Summarize current MT5 Tester readiness and latest runner evidence.")
    parser.add_argument("--tester-run", default="runtime/latest_mt5_tester_run.json")
    parser.add_argument("--promotion-gate", default="runtime/latest_promotion_gate.json")
    parser.add_argument("--compile-status", default="runtime/latest_mt5_compile_status.json")
    parser.add_argument("--optimization-report", default=DEFAULT_OPTIMIZATION_REPORT)
    parser.add_argument("--next-action-run", default=DEFAULT_NEXT_ACTION_RUN)
    parser.add_argument("--back-forward-run", default=DEFAULT_BACK_FORWARD_RUN)
    parser.add_argument("--manual-test-queue", default=DEFAULT_MANUAL_TEST_QUEUE)
    parser.add_argument("--manual-queue-launch", default=DEFAULT_MANUAL_QUEUE_LAUNCH)
    parser.add_argument("--manual-collect-run", default=DEFAULT_MANUAL_COLLECT_RUN)
    parser.add_argument(
        "--manual-test-queue-with-optimization",
        default=DEFAULT_MANUAL_TEST_QUEUE_WITH_OPTIMIZATION,
    )
    parser.add_argument(
        "--manual-queue-launch-with-optimization",
        default=DEFAULT_MANUAL_QUEUE_LAUNCH_WITH_OPTIMIZATION,
    )
    parser.add_argument(
        "--manual-collect-with-optimization",
        default=DEFAULT_MANUAL_COLLECT_WITH_OPTIMIZATION,
    )
    parser.add_argument(
        "--manual-operator-packet-with-optimization",
        default=DEFAULT_MANUAL_OPERATOR_PACKET_WITH_OPTIMIZATION,
    )
    parser.add_argument("--manual-auto-collect-watch", default=DEFAULT_MANUAL_AUTO_COLLECT_WATCH)
    parser.add_argument("--stable-candidate-report", default=DEFAULT_STABLE_CANDIDATE_REPORT)
    parser.add_argument("--stable-candidate-recommendation", default=DEFAULT_STABLE_CANDIDATE_RECOMMENDATION)
    parser.add_argument("--stable-candidate-tester-run", default=DEFAULT_STABLE_CANDIDATE_TESTER_RUN)
    parser.add_argument("--bridge-recovery-plan", default=DEFAULT_BRIDGE_RECOVERY_PLAN)
    parser.add_argument("--status-watch-heartbeat", default=DEFAULT_STATUS_WATCH_HEARTBEAT)
    parser.add_argument(
        "--status-watch-heartbeat-max-age-seconds",
        type=int,
        default=DEFAULT_STATUS_WATCH_HEARTBEAT_MAX_AGE_SECONDS,
    )
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--max-artifact-age-seconds", type=int, default=DEFAULT_MAX_ARTIFACT_AGE_SECONDS)
    parser.add_argument("--no-detect-running-terminal", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    status = mt5_tester_status(
        tester_run_path=args.tester_run,
        promotion_gate_path=args.promotion_gate,
        compile_status_path=args.compile_status,
        optimization_report_path=args.optimization_report,
        next_action_run_path=args.next_action_run,
        back_forward_run_path=args.back_forward_run,
        manual_test_queue_path=args.manual_test_queue,
        manual_queue_launch_path=args.manual_queue_launch,
        manual_collect_run_path=args.manual_collect_run,
        manual_test_queue_with_optimization_path=args.manual_test_queue_with_optimization,
        manual_queue_launch_with_optimization_path=args.manual_queue_launch_with_optimization,
        manual_collect_with_optimization_path=args.manual_collect_with_optimization,
        manual_operator_packet_with_optimization_path=args.manual_operator_packet_with_optimization,
        manual_auto_collect_watch_path=args.manual_auto_collect_watch,
        stable_candidate_report_path=args.stable_candidate_report,
        stable_candidate_recommendation_path=args.stable_candidate_recommendation,
        stable_candidate_tester_run_path=args.stable_candidate_tester_run,
        bridge_recovery_plan_path=args.bridge_recovery_plan,
        status_watch_heartbeat_path=args.status_watch_heartbeat,
        status_watch_heartbeat_max_age_seconds=args.status_watch_heartbeat_max_age_seconds,
        detect_running_terminal=not args.no_detect_running_terminal,
        max_artifact_age_seconds=args.max_artifact_age_seconds,
    )
    status["operator_summary"] = mt5_tester_status_operator_summary(
        status,
        output_json=args.output_json,
        output_md=args.output_md,
    )
    write_json(args.output_json, status)
    write_text(args.output_md, format_markdown(status))
    print(json.dumps(status["operator_summary"], ensure_ascii=False, indent=2))
    return 0 if status["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
