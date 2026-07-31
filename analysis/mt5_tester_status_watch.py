from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


HEARTBEAT_SCHEMA_VERSION = 2
HEARTBEAT_IMPLEMENTATION_VERSION = 89
DEFAULT_PID_FILE = "runtime/mt5_tester_status_watch_current.pid"
DEFAULT_HEARTBEAT = "runtime/mt5_tester_status_watch_heartbeat_current.json"
HEARTBEAT_SNAPSHOT_REQUIRED_KEYS = (
    "generated_at",
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


def planned_outputs_bundle(
    primary: object,
    archive_preview: object,
    follow_up: object,
    follow_up_archive_preview: object,
) -> dict[str, dict[str, object]]:
    return {
        "primary": primary if isinstance(primary, dict) else {},
        "archive_preview": archive_preview if isinstance(archive_preview, dict) else {},
        "follow_up": follow_up if isinstance(follow_up, dict) else {},
        "follow_up_archive_preview": (
            follow_up_archive_preview if isinstance(follow_up_archive_preview, dict) else {}
        ),
    }


def unique_non_empty(values: object) -> list[object]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    result: list[object] = []
    for value in values:
        if value in (None, ""):
            continue
        if isinstance(value, (dict, list)):
            marker = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            marker = str(value)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result


def manual_queue_current_gate_summary(entries: object) -> dict[str, object]:
    if not isinstance(entries, list):
        entries = []
    current_for_execution_count = 0
    selected_action_present_count = 0
    selected_action_current_count = 0
    selected_action_stale_count = 0
    not_current_entry_ids: list[object] = []
    current_gate_values: list[object] = []
    current_decision_values: list[object] = []
    gate_stale_reasons: list[object] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("id") or entry.get("queue_id") or entry.get("target") or ""
        current_for_execution = entry.get("current_for_execution")
        selected_action_present = entry.get("selected_action_present")
        selected_action_current = entry.get("selected_action_current")
        if current_for_execution is True:
            current_for_execution_count += 1
        elif current_for_execution is False and entry_id:
            not_current_entry_ids.append(entry_id)
        if selected_action_present is True:
            selected_action_present_count += 1
            if selected_action_current is False:
                selected_action_stale_count += 1
        if selected_action_current is True:
            selected_action_current_count += 1
        elif selected_action_current is False and entry_id and entry_id not in not_current_entry_ids:
            not_current_entry_ids.append(entry_id)
        current_gate_values.append(entry.get("current_promotion_generated_at", ""))
        current_decision_values.append(entry.get("current_promotion_decision", ""))
        gate_stale_reasons.append(entry.get("gate_stale_reason", ""))
    return {
        "manual_test_queue_current_for_execution_count": current_for_execution_count,
        "manual_test_queue_selected_action_present_count": selected_action_present_count,
        "manual_test_queue_selected_action_current_count": selected_action_current_count,
        "manual_test_queue_selected_action_stale_count": selected_action_stale_count,
        "manual_test_queue_current_promotion_generated_at_values": unique_non_empty(current_gate_values),
        "manual_test_queue_current_promotion_decision_values": unique_non_empty(current_decision_values),
        "manual_test_queue_gate_stale_reasons": unique_non_empty(gate_stale_reasons),
        "manual_test_queue_not_current_entry_ids": unique_non_empty(not_current_entry_ids),
    }


def prefixed_manual_queue_current_gate_summary(prefix: str, entries: object) -> dict[str, object]:
    return {
        key.replace("manual_test_queue", prefix, 1): value
        for key, value in manual_queue_current_gate_summary(entries).items()
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Periodically refresh MT5 Tester status files.")
    parser.add_argument("--tester-run", default="runtime/latest_mt5_tester_run.json")
    parser.add_argument("--promotion-gate", default="runtime/latest_promotion_gate.json")
    parser.add_argument("--compile-status", default="runtime/latest_mt5_compile_status.json")
    parser.add_argument("--optimization-report", default="runtime/latest_mt5_optimization_report.json")
    parser.add_argument("--next-action-run", default="runtime/latest_mt5_next_action_run.json")
    parser.add_argument("--back-forward-run", default="runtime/latest_mt5_back_forward_run.json")
    parser.add_argument("--manual-test-queue", default="runtime/latest_mt5_manual_test_queue.json")
    parser.add_argument("--manual-queue-launch", default="runtime/latest_mt5_manual_queue_launch.json")
    parser.add_argument("--manual-collect-run", default="runtime/latest_mt5_manual_collect_run.json")
    parser.add_argument(
        "--manual-test-queue-with-optimization",
        default="runtime/latest_mt5_manual_test_queue_with_optimization.json",
    )
    parser.add_argument(
        "--manual-queue-launch-with-optimization",
        default="runtime/latest_mt5_manual_queue_launch_with_optimization.json",
    )
    parser.add_argument(
        "--manual-collect-with-optimization",
        default="runtime/latest_mt5_manual_collect_with_optimization.json",
    )
    parser.add_argument(
        "--manual-operator-packet-with-optimization",
        default="runtime/latest_mt5_manual_operator_packet_with_optimization.json",
    )
    parser.add_argument(
        "--skip-manual-collect-refresh",
        action="store_true",
        help="Do not run the safe manual collect dry-run before refreshing MT5 tester status.",
    )
    parser.add_argument(
        "--skip-manual-queue-launch-refresh",
        action="store_true",
        help="Do not refresh the safe manual queue launch dry-run before refreshing MT5 tester status.",
    )
    parser.add_argument("--stable-candidate-report", default="runtime/latest_mt5_stable_candidate_optimization_report.json")
    parser.add_argument("--stable-candidate-recommendation", default="runtime/latest_mt5_stable_candidate_recommendation.json")
    parser.add_argument("--stable-candidate-tester-run", default="runtime/latest_mt5_tester_stable_candidate_run.json")
    parser.add_argument("--bridge-recovery-plan", default="runtime/latest_bridge_recovery_plan.json")
    parser.add_argument("--output-json", default="runtime/latest_mt5_tester_status.json")
    parser.add_argument("--output-md", default="runtime/latest_mt5_tester_status.md")
    parser.add_argument("--max-artifact-age-seconds", type=int, default=3600)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--max-runs", type=int, default=0, help="Stop after this many refreshes. 0 means run forever.")
    parser.add_argument(
        "--pid-file",
        default="",
        help=(
            "PID file path. Defaults to the shared daemon PID only for --max-runs 0; "
            "one-shot runs do not overwrite it unless this is explicit."
        ),
    )
    parser.add_argument(
        "--skip-pid-file-write",
        action="store_true",
        help="Do not overwrite the pid file. Useful for one-shot heartbeat refreshes while a daemon watcher is running.",
    )
    parser.add_argument(
        "--heartbeat",
        default="",
        help=(
            "Heartbeat path. Defaults to the shared daemon heartbeat only for --max-runs 0; "
            "one-shot runs do not overwrite it unless this is explicit."
        ),
    )
    return parser.parse_args(argv)


def first_present(*values: object) -> object:
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


def load_status_snapshot(path: str) -> dict[str, object]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    current = payload.get("current_terminal") if isinstance(payload.get("current_terminal"), dict) else {}
    bridge_recovery = (
        payload.get("bridge_recovery_plan")
        if isinstance(payload.get("bridge_recovery_plan"), dict)
        else {}
    )
    gate = payload.get("promotion_gate") if isinstance(payload.get("promotion_gate"), dict) else {}
    gate_back_forward_check = (
        gate.get("mt5_back_forward_run_check")
        if isinstance(gate.get("mt5_back_forward_run_check"), dict)
        else {}
    )
    gate_back_forward_ok_check = (
        gate.get("mt5_back_forward_run_ok_check")
        if isinstance(gate.get("mt5_back_forward_run_ok_check"), dict)
        else {}
    )
    gate_back_forward_performance_check = (
        gate.get("mt5_back_forward_run_performance_check")
        if isinstance(gate.get("mt5_back_forward_run_performance_check"), dict)
        else {}
    )
    latest = payload.get("latest_run") if isinstance(payload.get("latest_run"), dict) else {}
    compile_status = payload.get("compile_status") if isinstance(payload.get("compile_status"), dict) else {}
    pass_budget = payload.get("pass_budget") if isinstance(payload.get("pass_budget"), dict) else {}
    next_runner = payload.get("next_action_runner") if isinstance(payload.get("next_action_runner"), dict) else {}
    next_action_context = (
        next_runner.get("action_context") if isinstance(next_runner.get("action_context"), dict) else {}
    )
    score_weight_follow_up = (
        next_action_context.get("score_weight_follow_up")
        if isinstance(next_action_context.get("score_weight_follow_up"), dict)
        else {}
    )
    score_weight_set_result = (
        next_action_context.get("score_weight_set_result")
        if isinstance(next_action_context.get("score_weight_set_result"), dict)
        else {}
    )
    next_related_executions = (
        next_runner.get("related_executions") if isinstance(next_runner.get("related_executions"), list) else []
    )
    next_related_execution_rows = [
        {
            "key": str(row.get("key") or row.get("label") or ""),
            "kind": str((row.get("execution") if isinstance(row.get("execution"), dict) else {}).get("kind") or ""),
            "command_text": str(
                (row.get("execution") if isinstance(row.get("execution"), dict) else {}).get("command_text") or ""
            ),
        }
        for row in next_related_executions
        if isinstance(row, dict)
    ]
    next_action_context_keys = (
        next_runner.get("action_context_keys")
        if isinstance(next_runner.get("action_context_keys"), list)
        else sorted(next_action_context.keys())
    )
    next_related_execution_keys = (
        next_runner.get("related_execution_keys")
        if isinstance(next_runner.get("related_execution_keys"), list)
        else [row["key"] for row in next_related_execution_rows]
    )
    primary_outputs = (
        next_runner.get("primary_planned_outputs")
        if isinstance(next_runner.get("primary_planned_outputs"), dict)
        else {}
    )
    archive_outputs = (
        next_runner.get("archive_preview_planned_outputs")
        if isinstance(next_runner.get("archive_preview_planned_outputs"), dict)
        else {}
    )
    follow_up_outputs = (
        next_runner.get("follow_up_planned_outputs")
        if isinstance(next_runner.get("follow_up_planned_outputs"), dict)
        else {}
    )
    follow_up_archive_outputs = (
        next_runner.get("follow_up_archive_preview_planned_outputs")
        if isinstance(next_runner.get("follow_up_archive_preview_planned_outputs"), dict)
        else {}
    )
    archive_post = (
        next_runner.get("archive_preview_post_execution_artifacts")
        if isinstance(next_runner.get("archive_preview_post_execution_artifacts"), dict)
        else {}
    )
    archive_post_agent_csv = (
        archive_post.get("agent_csv_archive")
        if isinstance(archive_post.get("agent_csv_archive"), dict)
        else {}
    )
    primary_post = (
        next_runner.get("primary_post_execution_artifacts")
        if isinstance(next_runner.get("primary_post_execution_artifacts"), dict)
        else {}
    )
    primary_post_tester = (
        primary_post.get("tester_run") if isinstance(primary_post.get("tester_run"), dict) else {}
    )
    primary_post_optimization = (
        primary_post.get("optimization") if isinstance(primary_post.get("optimization"), dict) else {}
    )
    primary_post_recommendation = (
        primary_post.get("recommendation") if isinstance(primary_post.get("recommendation"), dict) else {}
    )
    follow_up_post = (
        next_runner.get("follow_up_post_execution_artifacts")
        if isinstance(next_runner.get("follow_up_post_execution_artifacts"), dict)
        else {}
    )
    follow_up_post_tester = (
        follow_up_post.get("tester_run") if isinstance(follow_up_post.get("tester_run"), dict) else {}
    )
    follow_up_post_forward = (
        follow_up_post.get("forward_report") if isinstance(follow_up_post.get("forward_report"), dict) else {}
    )
    follow_up_archive_post = (
        next_runner.get("follow_up_archive_preview_post_execution_artifacts")
        if isinstance(next_runner.get("follow_up_archive_preview_post_execution_artifacts"), dict)
        else {}
    )
    follow_up_archive_post_agent_csv = (
        follow_up_archive_post.get("agent_csv_archive")
        if isinstance(follow_up_archive_post.get("agent_csv_archive"), dict)
        else {}
    )
    post_validation = (
        next_runner.get("post_execution_validation")
        if isinstance(next_runner.get("post_execution_validation"), dict)
        else {}
    )
    primary_post_validation = (
        post_validation.get("primary") if isinstance(post_validation.get("primary"), dict) else {}
    )
    archive_post_validation = (
        post_validation.get("archive_preview")
        if isinstance(post_validation.get("archive_preview"), dict)
        else {}
    )
    follow_up_post_validation = (
        post_validation.get("follow_up") if isinstance(post_validation.get("follow_up"), dict) else {}
    )
    follow_up_archive_post_validation = (
        post_validation.get("follow_up_archive_preview")
        if isinstance(post_validation.get("follow_up_archive_preview"), dict)
        else {}
    )
    next_execution = (
        payload.get("next_action_execution") if isinstance(payload.get("next_action_execution"), dict) else {}
    )
    next_local_execution = (
        payload.get("next_action_local_execution")
        if isinstance(payload.get("next_action_local_execution"), dict)
        else {}
    )
    back_forward_runner = (
        payload.get("back_forward_runner") if isinstance(payload.get("back_forward_runner"), dict) else {}
    )
    back_forward_steps = (
        back_forward_runner.get("steps")
        if isinstance(back_forward_runner.get("steps"), list)
        else []
    )
    back_forward_strategy_pack = (
        back_forward_runner.get("mt5_strategy_tester_pack")
        if isinstance(back_forward_runner.get("mt5_strategy_tester_pack"), dict)
        else {}
    )
    back_forward_strategy_pack_steps = (
        back_forward_strategy_pack.get("steps")
        if isinstance(back_forward_strategy_pack.get("steps"), list)
        else back_forward_runner.get("mt5_strategy_tester_pack_steps", [])
        if isinstance(back_forward_runner.get("mt5_strategy_tester_pack_steps"), list)
        else []
    )
    back_forward_archive_preview_json_by_step = {
        str(step.get("label", "")): str(step.get("archive_preview_json", ""))
        for step in back_forward_steps
        if isinstance(step, dict) and str(step.get("label", ""))
    }
    back_forward_archive_preview_md_by_step = {
        str(step.get("label", "")): str(step.get("archive_preview_md", ""))
        for step in back_forward_steps
        if isinstance(step, dict) and str(step.get("label", ""))
    }
    back_forward_archive_preview_execution_ok_by_step = {
        str(step.get("label", "")): step.get("archive_preview_execution_ok", "")
        for step in back_forward_steps
        if isinstance(step, dict) and str(step.get("label", ""))
    }
    back_forward_archive_preview_validation_ok_by_step = {
        str(step.get("label", "")): step.get("archive_preview_validation_ok", "")
        for step in back_forward_steps
        if isinstance(step, dict) and str(step.get("label", ""))
    }
    back_forward_archive_preview_artifact_count_by_step = {
        str(step.get("label", "")): step.get("archive_preview_artifact_count", "")
        for step in back_forward_steps
        if isinstance(step, dict) and str(step.get("label", ""))
    }
    back_forward_archive_preview_first_json = next(
        (value for value in back_forward_archive_preview_json_by_step.values() if value),
        "",
    )
    back_forward_archive_preview_first_md = next(
        (value for value in back_forward_archive_preview_md_by_step.values() if value),
        "",
    )
    back_forward_execution = (
        payload.get("back_forward_execution") if isinstance(payload.get("back_forward_execution"), dict) else {}
    )
    manual_strategy_tester = (
        payload.get("manual_strategy_tester")
        if isinstance(payload.get("manual_strategy_tester"), dict)
        else {}
    )
    manual_test_queue = (
        payload.get("manual_test_queue")
        if isinstance(payload.get("manual_test_queue"), dict)
        else {}
    )
    manual_test_queue_handoff = (
        manual_test_queue.get("operator_handoff")
        if isinstance(manual_test_queue.get("operator_handoff"), dict)
        else {}
    )
    manual_queue_launch = (
        payload.get("manual_queue_launch")
        if isinstance(payload.get("manual_queue_launch"), dict)
        else {}
    )
    manual_collect_run = (
        payload.get("manual_collect_run")
        if isinstance(payload.get("manual_collect_run"), dict)
        else {}
    )
    manual_test_queue_with_optimization = (
        payload.get("manual_test_queue_with_optimization")
        if isinstance(payload.get("manual_test_queue_with_optimization"), dict)
        else {}
    )
    manual_test_queue_with_optimization_handoff = (
        manual_test_queue_with_optimization.get("operator_handoff")
        if isinstance(manual_test_queue_with_optimization.get("operator_handoff"), dict)
        else {}
    )
    manual_queue_launch_with_optimization = (
        payload.get("manual_queue_launch_with_optimization")
        if isinstance(payload.get("manual_queue_launch_with_optimization"), dict)
        else {}
    )
    manual_collect_with_optimization = (
        payload.get("manual_collect_with_optimization")
        if isinstance(payload.get("manual_collect_with_optimization"), dict)
        else {}
    )
    manual_auto_collect_watch = (
        payload.get("manual_auto_collect_watch")
        if isinstance(payload.get("manual_auto_collect_watch"), dict)
        else {}
    )
    manual_auto_collect_queue_launch = (
        manual_auto_collect_watch.get("queue_launch_refresh")
        if isinstance(manual_auto_collect_watch.get("queue_launch_refresh"), dict)
        else manual_auto_collect_watch.get("queue_launch")
        if isinstance(manual_auto_collect_watch.get("queue_launch"), dict)
        else {}
    )
    manual_auto_collect_operator_packet = (
        manual_auto_collect_watch.get("operator_packet_refresh")
        if isinstance(manual_auto_collect_watch.get("operator_packet_refresh"), dict)
        else manual_auto_collect_watch.get("operator_packet")
        if isinstance(manual_auto_collect_watch.get("operator_packet"), dict)
        else {}
    )
    manual_auto_collect_execution = (
        manual_auto_collect_watch.get("execution")
        if isinstance(manual_auto_collect_watch.get("execution"), dict)
        else {}
    )
    manual_operator_packet_with_optimization = (
        payload.get("manual_operator_packet_with_optimization")
        if isinstance(payload.get("manual_operator_packet_with_optimization"), dict)
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
    manual_collect_queue_refresh = (
        manual_collect_run.get("queue_refresh")
        if isinstance(manual_collect_run.get("queue_refresh"), dict)
        else {}
    )
    manual_collect_handoff = (
        manual_collect_run.get("operator_handoff")
        if isinstance(manual_collect_run.get("operator_handoff"), dict)
        else {}
    )
    manual_collect_with_optimization_handoff = (
        manual_collect_with_optimization.get("operator_handoff")
        if isinstance(manual_collect_with_optimization.get("operator_handoff"), dict)
        else {}
    )
    mt5_operator_handoff = (
        payload.get("mt5_operator_handoff")
        if isinstance(payload.get("mt5_operator_handoff"), dict)
        else {}
    )
    local_optimization_evidence = (
        next_local_execution.get("optimization_report_evidence")
        if isinstance(next_local_execution.get("optimization_report_evidence"), dict)
        else {}
    )
    stable = payload.get("stable_candidate") if isinstance(payload.get("stable_candidate"), dict) else {}
    stable_refit = gate.get("stable_candidate_refit") if isinstance(gate.get("stable_candidate_refit"), dict) else {}
    stable_refit_completed = (
        gate.get("stable_candidate_refit_completed")
        if isinstance(gate.get("stable_candidate_refit_completed"), dict)
        else {}
    )
    artifact_freshness = (
        payload.get("artifact_freshness") if isinstance(payload.get("artifact_freshness"), dict) else {}
    )
    artifacts = (
        artifact_freshness.get("artifacts") if isinstance(artifact_freshness.get("artifacts"), dict) else {}
    )
    stale_artifacts = [
        name
        for name, item in artifacts.items()
        if isinstance(item, dict) and item.get("fresh") is not True
    ]
    manual_test_queue_entries = manual_test_queue.get("entries", [])
    manual_queue_gate_summary = manual_queue_current_gate_summary(manual_test_queue_entries)
    manual_test_queue_with_optimization_entries = manual_test_queue_with_optimization.get("entries", [])
    manual_queue_with_optimization_gate_summary = prefixed_manual_queue_current_gate_summary(
        "manual_test_queue_with_optimization",
        manual_test_queue_with_optimization_entries,
    )
    manual_test_queue_quick_input = first_present(
        manual_test_queue.get("next_quick_input"),
        manual_test_queue.get("quick_input"),
        manual_test_queue_handoff.get("next_quick_input"),
        manual_test_queue_handoff.get("quick_input"),
    )
    manual_test_queue_next_launch_step = (
        manual_test_queue.get("next_launch_step")
        if isinstance(manual_test_queue.get("next_launch_step"), dict)
        else {}
    )
    manual_test_queue_next_queue_step = first_present(
        manual_test_queue.get("next_queue_step"),
        manual_test_queue_handoff.get("next_queue_step"),
        (
            manual_test_queue_quick_input.get("queue_step")
            if isinstance(manual_test_queue_quick_input, dict)
            else ""
        ),
        queue_step_from_mt5_step(manual_test_queue_next_launch_step),
        queue_step_from_mt5_step(manual_test_queue_handoff.get("next_mt5_step")),
    )
    manual_test_queue_with_optimization_quick_input = first_present(
        manual_test_queue_with_optimization.get("next_quick_input"),
        manual_test_queue_with_optimization.get("quick_input"),
        manual_test_queue_with_optimization_handoff.get("next_quick_input"),
        manual_test_queue_with_optimization_handoff.get("quick_input"),
    )
    manual_test_queue_with_optimization_next_launch_step = (
        manual_test_queue_with_optimization.get("next_launch_step")
        if isinstance(manual_test_queue_with_optimization.get("next_launch_step"), dict)
        else {}
    )
    manual_test_queue_with_optimization_next_queue_step = first_present(
        manual_test_queue_with_optimization.get("next_queue_step"),
        manual_test_queue_with_optimization_handoff.get("next_queue_step"),
        (
            manual_test_queue_with_optimization_quick_input.get("queue_step")
            if isinstance(manual_test_queue_with_optimization_quick_input, dict)
            else ""
        ),
        queue_step_from_mt5_step(manual_test_queue_with_optimization_next_launch_step),
        queue_step_from_mt5_step(
            manual_test_queue_with_optimization_handoff.get("next_mt5_step")
        ),
    )
    return {
        "status_ok": payload.get("ok"),
        "operational_status": payload.get("operational_status", ""),
        "ready_for_tester_launch": payload.get("ready_for_tester_launch"),
        "next_action": payload.get("next_action", ""),
        "bridge_recovery_plan_exists": bridge_recovery.get("exists"),
        "bridge_recovery_plan_output_json": bridge_recovery.get("path", ""),
        "bridge_recovery_plan_ok": bridge_recovery.get("ok"),
        "bridge_recovery_plan_status": bridge_recovery.get("status", ""),
        "bridge_recovery_plan_ready_for_mt5_validation": bridge_recovery.get("ready_for_mt5_validation"),
        "bridge_recovery_plan_generated_at": bridge_recovery.get("generated_at", ""),
        "bridge_recovery_plan_blocking_reasons": bridge_recovery.get("blocking_reasons", []),
        "bridge_recovery_plan_next_action": bridge_recovery.get("next_action", ""),
        "bridge_recovery_plan_operational_status": bridge_recovery.get("operational_status", ""),
        "bridge_recovery_plan_bridge_process_running": bridge_recovery.get("bridge_process_running"),
        "bridge_recovery_plan_mt5_terminal_running": bridge_recovery.get("mt5_terminal_running"),
        "bridge_recovery_plan_snapshot_fresh": bridge_recovery.get("snapshot_fresh"),
        "bridge_recovery_plan_history_request_stale_pending": bridge_recovery.get(
            "history_request_stale_pending"
        ),
        "bridge_recovery_plan_history_done_matches_request": bridge_recovery.get("history_done_matches_request"),
        "bridge_recovery_plan_last_ea_post_age_seconds": bridge_recovery.get("last_ea_post_age_seconds"),
        "bridge_recovery_plan_history_data_fresh": bridge_recovery.get("history_data_fresh"),
        "bridge_recovery_plan_history_data_stale": bridge_recovery.get("history_data_stale"),
        "bridge_recovery_plan_history_status_server_time": bridge_recovery.get(
            "history_status_server_time", ""
        ),
        "bridge_recovery_plan_history_status_server_time_age_seconds": bridge_recovery.get(
            "history_status_server_time_age_seconds", ""
        ),
        "bridge_recovery_plan_history_status_m1_last_time": bridge_recovery.get(
            "history_status_m1_last_time", ""
        ),
        "bridge_recovery_plan_history_status_m1_last_time_age_seconds": bridge_recovery.get(
            "history_status_m1_last_time_age_seconds", ""
        ),
        "artifact_freshness": artifact_freshness,
        "artifact_stale": stale_artifacts,
        "current_terminal_running": current.get("running"),
        "current_terminal_count": current.get("count"),
        "compile_all_compiled_fresh": compile_status.get("all_compiled_fresh"),
        "compile_all_tester_sets_synced": compile_status.get("all_tester_sets_synced"),
        "compile_all_tester_configs_synced": compile_status.get("all_tester_configs_synced"),
        "compile_all_required_tester_config_references_ready": compile_status.get(
            "all_required_tester_config_references_ready"
        ),
        "compile_unsynced_tester_sets": compile_status.get("unsynced_tester_sets", []),
        "compile_unsynced_tester_configs": compile_status.get("unsynced_tester_configs", []),
        "compile_tester_config_reference_issues": compile_status.get("tester_config_reference_issues", []),
        "risk_preset_schema_required": latest.get("risk_preset_schema_required"),
        "risk_preset_schema_status": latest.get("risk_preset_schema_status", ""),
        "risk_preset_schema_current": latest.get("risk_preset_schema_current"),
        "risk_preset_schema_missing_inputs": latest.get("risk_preset_schema_missing_inputs", []),
        "mt5_operator_handoff_state": mt5_operator_handoff.get("state", ""),
        "mt5_operator_handoff_recommended_path": mt5_operator_handoff.get("recommended_path", ""),
        "mt5_operator_handoff_manual_strategy_tester_available": mt5_operator_handoff.get(
            "manual_strategy_tester_available", ""
        ),
        "mt5_operator_handoff_terminal_running": mt5_operator_handoff.get("terminal_running", ""),
        "mt5_operator_handoff_auto_launch_ready": mt5_operator_handoff.get("auto_launch_ready", ""),
        "mt5_operator_handoff_auto_launch_status": mt5_operator_handoff.get("auto_launch_status", ""),
        "mt5_operator_handoff_auto_launch_blocked_by_running_terminal": mt5_operator_handoff.get(
            "auto_launch_blocked_by_running_terminal", ""
        ),
        "mt5_operator_handoff_auto_launch_blockers": mt5_operator_handoff.get("auto_launch_blockers", []),
        "mt5_operator_handoff_manual_queue_status": mt5_operator_handoff.get("manual_queue_status", ""),
        "mt5_operator_handoff_manual_queue_next_action": mt5_operator_handoff.get(
            "manual_queue_next_action", ""
        ),
        "mt5_operator_handoff_manual_collect_status": mt5_operator_handoff.get(
            "manual_collect_status", ""
        ),
        "mt5_operator_handoff_manual_collect_next_action": mt5_operator_handoff.get(
            "manual_collect_next_action", ""
        ),
        "mt5_operator_handoff_next_mt5_step": mt5_operator_handoff.get("next_mt5_step", {}),
        "mt5_operator_handoff_quick_input": mt5_operator_handoff.get("quick_input", {}),
        "mt5_operator_handoff_next_step_operator_summary": mt5_operator_handoff.get(
            "next_step_operator_summary", ""
        ),
        "mt5_operator_handoff_next_step_summary": first_present(
            mt5_operator_handoff.get("next_step_summary"),
            mt5_operator_handoff.get("next_step_operator_summary"),
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
            first_present(
                mt5_operator_handoff.get(
                    "manual_collect_execute_and_refresh_full_analysis_command_text"
                ),
                mt5_operator_handoff.get(
                    "manual_collect_execute_and_refresh_all_command_text"
                ),
            )
        ),
        "mt5_operator_handoff_bridge_required_for_standalone_tester": mt5_operator_handoff.get(
            "bridge_required_for_standalone_tester", ""
        ),
        "mt5_operator_handoff_bridge_ready_for_mt5_validation": mt5_operator_handoff.get(
            "bridge_ready_for_mt5_validation", ""
        ),
        "mt5_operator_handoff_bridge_status": mt5_operator_handoff.get("bridge_status", ""),
        "mt5_operator_handoff_bridge_note": mt5_operator_handoff.get("bridge_note", ""),
        "manual_strategy_tester_available": manual_strategy_tester.get("available"),
        "manual_strategy_tester_recommended": manual_strategy_tester.get("recommended"),
        "manual_strategy_tester_status": manual_strategy_tester.get("status", ""),
        "manual_strategy_tester_reasons": manual_strategy_tester.get("reasons", []),
        "manual_strategy_tester_auto_launch_ready": manual_strategy_tester.get("auto_launch_ready", ""),
        "manual_strategy_tester_auto_launch_status": manual_strategy_tester.get("auto_launch_status", ""),
        "manual_strategy_tester_auto_launch_blockers": manual_strategy_tester.get("auto_launch_blockers", []),
        "manual_strategy_tester_auto_launch_blocked_by_running_terminal": manual_strategy_tester.get(
            "auto_launch_blocked_by_running_terminal"
        ),
        "manual_strategy_tester_terminal_running": manual_strategy_tester.get("terminal_running"),
        "manual_strategy_tester_collect_only_command_text": manual_strategy_tester.get(
            "collect_only_command_text", ""
        ),
        "manual_strategy_tester_collect_only_note": manual_strategy_tester.get("collect_only_note", ""),
        "manual_strategy_tester_manual_run_start_after": manual_strategy_tester.get(
            "manual_run_start_after", ""
        ),
        "manual_strategy_tester_step_count": manual_strategy_tester.get("step_count", ""),
        "manual_strategy_tester_steps": manual_strategy_tester.get("steps", []),
        "manual_strategy_tester_note": manual_strategy_tester.get("note", ""),
        "manual_test_queue_exists": manual_test_queue.get("exists"),
        "manual_test_queue_path": manual_test_queue.get("path", ""),
        "manual_test_queue_generated_at": manual_test_queue.get("generated_at", ""),
        "manual_test_queue_ok": manual_test_queue.get("ok"),
        "manual_test_queue_status": manual_test_queue.get("status", ""),
        "manual_test_queue_next_action": manual_test_queue.get("next_action", ""),
        "manual_test_queue_progress_state": manual_test_queue_handoff.get("progress_state", ""),
        "manual_test_queue_entry_count": manual_test_queue.get("entry_count", ""),
        "manual_test_queue_total_entry_count": manual_test_queue.get("total_entry_count", ""),
        "manual_test_queue_stale_entry_count": manual_test_queue.get("stale_entry_count", ""),
        "manual_test_queue_manual_run_start_marked": manual_test_queue.get(
            "manual_run_start_marked", ""
        ),
        "manual_test_queue_manual_run_start_marked_this_run": manual_test_queue.get(
            "manual_run_start_marked_this_run", ""
        ),
        "manual_test_queue_manual_run_start_preserved": manual_test_queue.get(
            "manual_run_start_preserved", ""
        ),
        "manual_test_queue_manual_run_start_state_count": manual_test_queue.get(
            "manual_run_start_state_count", ""
        ),
        "manual_test_queue_manual_run_start_state_marked_count": manual_test_queue.get(
            "manual_run_start_state_marked_count", ""
        ),
        "manual_test_queue_manual_run_start_effective_after_values": manual_test_queue.get(
            "manual_run_start_effective_after_values", []
        ),
        "manual_test_queue_manual_run_start_after_override": manual_test_queue.get(
            "manual_run_start_after_override", ""
        ),
        "manual_test_queue_step_count": manual_test_queue.get("step_count", ""),
        "manual_test_queue_ready_to_collect_count": manual_test_queue.get("ready_to_collect_count", ""),
        "manual_test_queue_waiting_count": manual_test_queue.get("waiting_count", ""),
        "manual_test_queue_step_report_ready_count": manual_test_queue.get("step_report_ready_count", ""),
        "manual_test_queue_step_collect_ready_count": manual_test_queue.get(
            "step_collect_ready_count", ""
        ),
        "manual_test_queue_step_waiting_report_count": manual_test_queue.get(
            "step_waiting_report_count", ""
        ),
        "manual_test_queue_step_launch_needed_count": manual_test_queue.get(
            "step_launch_needed_count", ""
        ),
        "manual_test_queue_step_report_ready_ids": manual_test_queue.get(
            "step_report_ready_ids", []
        ),
        "manual_test_queue_step_collect_ready_ids": manual_test_queue.get(
            "step_collect_ready_ids", []
        ),
        "manual_test_queue_step_waiting_report_ids": manual_test_queue.get(
            "step_waiting_report_ids", []
        ),
        "manual_test_queue_step_launch_needed_ids": manual_test_queue.get(
            "step_launch_needed_ids", []
        ),
        "manual_test_queue_collect_check_command_text": manual_test_queue_handoff.get(
            "collect_check_command_text", ""
        ),
        "manual_test_queue_next_queue_step": manual_test_queue_next_queue_step,
        "manual_test_queue_quick_input": manual_test_queue_quick_input,
        "manual_test_queue_next_quick_input": manual_test_queue_quick_input,
        "manual_test_queue_next_launch_step": manual_test_queue.get("next_launch_step", {}),
        "manual_test_queue_all_collect_ready": manual_test_queue.get("all_collect_ready", ""),
        "manual_test_queue_blocking_reasons": manual_test_queue.get("blocking_reasons", []),
        **manual_queue_gate_summary,
        "manual_test_queue_entries": manual_test_queue_entries,
        "manual_test_queue_strategy_tester_targets": manual_test_queue.get(
            "strategy_tester_targets", []
        ),
        "manual_test_queue_operation_cards": manual_test_queue.get("operation_cards", []),
        "manual_test_queue_execution_checklist": manual_test_queue.get("execution_checklist", []),
        "manual_test_queue_operator_handoff": manual_test_queue_handoff,
        "manual_test_queue_operator_handoff_quick_input": manual_test_queue_handoff.get("quick_input", {}),
        "manual_test_queue_next_step_operator_summary": manual_test_queue_handoff.get(
            "next_step_operator_summary", ""
        ),
        "manual_test_queue_next_step_summary": first_present(
            manual_test_queue_handoff.get("next_step_summary"),
            manual_test_queue_handoff.get("next_step_operator_summary"),
        ),
        "manual_test_queue_next_step_collect_filter_summary": manual_test_queue_handoff.get(
            "next_step_collect_filter_summary", ""
        ),
        "manual_queue_launch_exists": manual_queue_launch.get("exists"),
        "manual_queue_launch_path": manual_queue_launch.get("path", ""),
        "manual_queue_launch_generated_at": manual_queue_launch.get("generated_at", ""),
        "manual_queue_launch_ok": manual_queue_launch.get("ok"),
        "manual_queue_launch_status": manual_queue_launch.get("status", ""),
        "manual_queue_launch_next_action": manual_queue_launch.get("next_action", ""),
        "manual_queue_launch_queue_path": manual_queue_launch.get("queue_path", ""),
        "manual_queue_launch_queue_status": manual_queue_launch.get("queue_status", ""),
        "manual_queue_launch_queue_next_action": manual_queue_launch.get("queue_next_action", ""),
        "manual_queue_launch_queue_entry_count": manual_queue_launch.get("queue_entry_count", ""),
        "manual_queue_launch_queue_total_entry_count": manual_queue_launch.get(
            "queue_total_entry_count", ""
        ),
        "manual_queue_launch_queue_step_count": manual_queue_launch.get("queue_step_count", ""),
        "manual_queue_launch_queue_waiting_count": manual_queue_launch.get(
            "queue_waiting_count", ""
        ),
        "manual_queue_launch_queue_operator_handoff_state": manual_queue_launch.get(
            "queue_operator_handoff_state", ""
        ),
        "manual_queue_launch_queue_operator_handoff_next_mt5_step": manual_queue_launch.get(
            "queue_operator_handoff_next_mt5_step", {}
        ),
        "manual_queue_launch_queue_operator_handoff_quick_input": manual_queue_launch.get(
            "queue_operator_handoff_quick_input", {}
        ),
        "manual_queue_launch_queue_operator_handoff_next_step_operator_summary": manual_queue_launch.get(
            "queue_operator_handoff_next_step_operator_summary", ""
        ),
        "manual_queue_launch_queue_operator_handoff_next_step_summary": first_present(
            manual_queue_launch.get("queue_operator_handoff_next_step_summary"),
            manual_queue_launch.get("queue_operator_handoff_next_step_operator_summary"),
        ),
        "manual_queue_launch_queue_operator_handoff_next_step_collect_filter_summary": manual_queue_launch.get(
            "queue_operator_handoff_next_step_collect_filter_summary", ""
        ),
        "manual_queue_launch_queue_operator_handoff_collect_ready": manual_queue_launch.get(
            "queue_operator_handoff_collect_ready", ""
        ),
        "manual_queue_launch_queue_operator_handoff_waiting_entry_ids": manual_queue_launch.get(
            "queue_operator_handoff_waiting_entry_ids", []
        ),
        "manual_queue_launch_queue_operator_handoff_collect_dry_run_command_text": manual_queue_launch.get(
            "queue_operator_handoff_collect_dry_run_command_text", ""
        ),
        "manual_queue_launch_queue_operator_handoff_collect_execute_command_text": manual_queue_launch.get(
            "queue_operator_handoff_collect_execute_command_text", ""
        ),
        "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_analysis_command_text": manual_queue_launch.get(
            "queue_operator_handoff_collect_execute_and_refresh_analysis_command_text", ""
        ),
        "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_all_command_text": manual_queue_launch.get(
            "queue_operator_handoff_collect_execute_and_refresh_all_command_text", ""
        ),
        "manual_queue_launch_queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text": (
            first_present(
                manual_queue_launch.get(
                    "queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text"
                ),
                manual_queue_launch.get(
                    "queue_operator_handoff_collect_execute_and_refresh_all_command_text"
                ),
            )
        ),
        "manual_queue_launch_execute": manual_queue_launch.get("execute", ""),
        "manual_queue_launch_detached": manual_queue_launch.get("detached", ""),
        "manual_queue_launch_selected": manual_queue_launch.get("selected", ""),
        "manual_queue_launch_selected_item": manual_queue_launch.get("selected_item", {}),
        "manual_queue_launch_selected_matches_queue_handoff": manual_queue_launch.get(
            "selected_matches_queue_handoff", ""
        ),
        "manual_queue_launch_launch_command_kind": manual_queue_launch.get("launch_command_kind", ""),
        "manual_queue_launch_command_text": manual_queue_launch.get("command_text", ""),
        "manual_queue_launch_mark_manual_run_start": manual_queue_launch.get("mark_manual_run_start", ""),
        "manual_queue_launch_manual_run_start_mark_status": manual_queue_launch.get(
            "manual_run_start_mark_status", ""
        ),
        "manual_queue_launch_manual_run_start_mark_attempted": manual_queue_launch.get(
            "manual_run_start_mark_attempted", ""
        ),
        "manual_queue_launch_manual_run_start_after": manual_queue_launch.get("manual_run_start_after", ""),
        "manual_queue_launch_blocked": manual_queue_launch.get("blocked", ""),
        "manual_queue_launch_blocked_reasons": manual_queue_launch.get("blocked_reasons", []),
        "manual_queue_launch_running_terminal_count": manual_queue_launch.get("running_terminal_count", ""),
        "manual_queue_launch_process_pid": manual_queue_launch.get("process_pid", ""),
        "manual_collect_run_exists": manual_collect_run.get("exists"),
        "manual_collect_run_path": manual_collect_run.get("path", ""),
        "manual_collect_run_generated_at": manual_collect_run.get("generated_at", ""),
        "manual_collect_run_ok": manual_collect_run.get("ok"),
        "manual_collect_run_status": manual_collect_run.get("status", ""),
        "manual_collect_run_next_action": manual_collect_run.get("next_action", ""),
        "manual_collect_run_execute": manual_collect_run.get("execute", ""),
        "manual_collect_run_dry_run": manual_collect_run.get("dry_run", ""),
        "manual_collect_run_queue_path": manual_collect_run.get("queue_path", ""),
        "manual_collect_run_queue_generated_at": manual_collect_run.get("queue_generated_at", ""),
        "manual_collect_run_queue_status": manual_collect_run.get("queue_status", ""),
        "manual_collect_run_queue_next_action": manual_collect_run.get("queue_next_action", ""),
        "manual_collect_run_queue_step_count": manual_collect_run.get("queue_step_count", ""),
        "manual_collect_run_queue_step_report_ready_count": manual_collect_run.get(
            "queue_step_report_ready_count", ""
        ),
        "manual_collect_run_queue_step_collect_ready_count": manual_collect_run.get(
            "queue_step_collect_ready_count", ""
        ),
        "manual_collect_run_queue_step_waiting_report_count": manual_collect_run.get(
            "queue_step_waiting_report_count", ""
        ),
        "manual_collect_run_queue_step_launch_needed_count": manual_collect_run.get(
            "queue_step_launch_needed_count", ""
        ),
        "manual_collect_run_entry_count": manual_collect_run.get("entry_count", ""),
        "manual_collect_run_ready_entry_count": manual_collect_run.get("ready_entry_count", ""),
        "manual_collect_run_selected_count": manual_collect_run.get("selected_count", ""),
        "manual_collect_run_waiting_count": manual_collect_run.get("waiting_count", ""),
        "manual_collect_run_invalid_count": manual_collect_run.get("invalid_count", ""),
        "manual_collect_run_planned_count": manual_collect_run.get("planned_count", ""),
        "manual_collect_run_skipped_count": manual_collect_run.get("skipped_count", ""),
        "manual_collect_run_execution_count": manual_collect_run.get("execution_count", ""),
        "manual_collect_run_queue_refresh_enabled": manual_collect_queue_refresh.get("enabled", ""),
        "manual_collect_run_queue_refresh_ok": manual_collect_queue_refresh.get("ok", ""),
        "manual_collect_run_queue_refresh_status": manual_collect_queue_refresh.get("status", ""),
        "manual_collect_run_queue_refresh_source_count": manual_collect_queue_refresh.get("source_count", ""),
        "manual_collect_run_handoff_state": manual_collect_handoff.get("state", ""),
        "manual_collect_run_handoff_ready_ids": manual_collect_handoff.get("ready_ids", []),
        "manual_collect_run_handoff_waiting_ids": manual_collect_handoff.get("waiting_ids", []),
        "manual_collect_run_handoff_invalid_ids": manual_collect_handoff.get("invalid_ids", []),
        "manual_collect_run_handoff_next_mt5_step": manual_collect_handoff.get("next_mt5_step", {}),
        "manual_collect_run_handoff_quick_input": manual_collect_handoff.get("quick_input", {}),
        "manual_collect_run_handoff_next_step_operator_summary": manual_collect_handoff.get(
            "next_step_operator_summary", ""
        ),
        "manual_collect_run_handoff_next_step_summary": first_present(
            manual_collect_handoff.get("next_step_summary"),
            manual_collect_handoff.get("next_step_operator_summary"),
        ),
        "manual_collect_run_handoff_next_step_collect_filter_summary": manual_collect_handoff.get(
            "next_step_collect_filter_summary", ""
        ),
        "manual_collect_run_handoff_dry_run_command_text": manual_collect_handoff.get(
            "dry_run_command_text", ""
        ),
        "manual_collect_run_handoff_execute_command_text": manual_collect_handoff.get(
            "execute_command_text", ""
        ),
        "manual_collect_run_step_completion_audit": manual_collect_run.get(
            "step_completion_audit", []
        ),
        "manual_collect_run_planned": manual_collect_run.get("planned", []),
        "manual_collect_run_skipped": manual_collect_run.get("skipped", []),
        "manual_collect_run_invalid": manual_collect_run.get("invalid", []),
        "manual_collect_run_executions": manual_collect_run.get("executions", []),
        "manual_auto_collect_watch_exists": manual_auto_collect_watch.get("exists", ""),
        "manual_auto_collect_watch_path": manual_auto_collect_watch.get("path", ""),
        "manual_auto_collect_watch_generated_at": manual_auto_collect_watch.get("generated_at", ""),
        "manual_auto_collect_watch_ok": manual_auto_collect_watch.get("ok", ""),
        "manual_auto_collect_watch_status": manual_auto_collect_watch.get("status", ""),
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
            "queue_launch_status", manual_auto_collect_queue_launch.get("status", "")
        ),
        "manual_auto_collect_watch_queue_launch_blocked": manual_auto_collect_watch.get(
            "queue_launch_blocked", manual_auto_collect_queue_launch.get("blocked", "")
        ),
        "manual_auto_collect_watch_queue_launch_blocked_reasons": manual_auto_collect_watch.get(
            "queue_launch_blocked_reasons",
            manual_auto_collect_queue_launch.get("blocked_reasons", []),
        ),
        "manual_auto_collect_watch_operator_packet_next_queue_step": manual_auto_collect_watch.get(
            "operator_packet_next_queue_step",
            manual_auto_collect_operator_packet.get("next_queue_step", ""),
        ),
        "manual_auto_collect_watch_operator_packet_auto_launch_command_text": manual_auto_collect_watch.get(
            "operator_packet_auto_launch_command_text",
            manual_auto_collect_operator_packet.get("auto_launch_command_text", ""),
        ),
        "manual_auto_collect_watch_operator_packet_auto_launch_command_available": manual_auto_collect_watch.get(
            "operator_packet_auto_launch_command_available",
            manual_auto_collect_operator_packet.get("auto_launch_command_available", ""),
        ),
        "manual_auto_collect_watch_operator_packet_auto_launch_blocked": manual_auto_collect_watch.get(
            "operator_packet_auto_launch_blocked",
            manual_auto_collect_operator_packet.get("auto_launch_blocked", ""),
        ),
        "manual_auto_collect_watch_operator_packet_auto_launch_blocked_reasons": manual_auto_collect_watch.get(
            "operator_packet_auto_launch_blocked_reasons",
            manual_auto_collect_operator_packet.get("auto_launch_blocked_reasons", []),
        ),
        "manual_auto_collect_watch_operator_packet_auto_launch_note": manual_auto_collect_watch.get(
            "operator_packet_auto_launch_note",
            manual_auto_collect_operator_packet.get("auto_launch_note", ""),
        ),
        "manual_auto_collect_watch_operator_packet_strategy_source_time_refresh_status": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_source_time_refresh_status",
                manual_auto_collect_operator_packet.get("strategy_source_time_refresh_status", ""),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_source_time_issue_labels": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_source_time_issue_labels",
                manual_auto_collect_operator_packet.get("strategy_source_time_issue_labels", []),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_source_time_candidate_issue_labels": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_source_time_candidate_issue_labels",
                manual_auto_collect_operator_packet.get(
                    "strategy_source_time_candidate_issue_labels", []
                ),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_source_time_refresh_analysis_command_text": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_source_time_refresh_analysis_command_text",
                manual_auto_collect_operator_packet.get(
                    "strategy_source_time_refresh_analysis_command_text", ""
                ),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_source_time_refresh_analysis_command_available": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_source_time_refresh_analysis_command_available",
                bool(
                    manual_auto_collect_operator_packet.get(
                        "strategy_source_time_refresh_analysis_command_text"
                    )
                ),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_buy_candidate_gap_status": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_buy_candidate_gap_status",
                manual_auto_collect_operator_packet.get("strategy_buy_candidate_gap_status", ""),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_buy_candidate_gap_reason": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_buy_candidate_gap_reason",
                manual_auto_collect_operator_packet.get("strategy_buy_candidate_gap_reason", ""),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_buy_candidate_gap_diagnostic_labels": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_buy_candidate_gap_diagnostic_labels",
                manual_auto_collect_operator_packet.get(
                    "strategy_buy_candidate_gap_diagnostic_labels", []
                ),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_buy_candidate_gap_collect_refresh_command_text": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_buy_candidate_gap_collect_refresh_command_text",
                manual_auto_collect_operator_packet.get(
                    "strategy_buy_candidate_gap_collect_refresh_command_text", ""
                ),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_buy_candidate_gap_collect_refresh_command_available": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_buy_candidate_gap_collect_refresh_command_available",
                bool(
                    manual_auto_collect_operator_packet.get(
                        "strategy_buy_candidate_gap_collect_refresh_command_text"
                    )
                ),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_status": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_operator_decision_status",
                manual_auto_collect_operator_packet.get("strategy_operator_decision_status", ""),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_verdict": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_operator_decision_verdict",
                manual_auto_collect_operator_packet.get("strategy_operator_decision_verdict", ""),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_adoptable": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_operator_decision_adoptable",
                manual_auto_collect_operator_packet.get("strategy_operator_decision_adoptable", ""),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_primary_blocker": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_operator_decision_primary_blocker",
                manual_auto_collect_operator_packet.get(
                    "strategy_operator_decision_primary_blocker", ""
                ),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_primary_reason": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_operator_decision_primary_reason",
                manual_auto_collect_operator_packet.get(
                    "strategy_operator_decision_primary_reason", ""
                ),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_next_action": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_operator_decision_next_action",
                manual_auto_collect_operator_packet.get("strategy_operator_decision_next_action", ""),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_summary": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_operator_decision_summary",
                manual_auto_collect_operator_packet.get("strategy_operator_decision_summary", ""),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_command_text": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_operator_decision_command_text",
                manual_auto_collect_operator_packet.get("strategy_operator_decision_command_text", ""),
            )
        ),
        "manual_auto_collect_watch_operator_packet_strategy_operator_decision_follow_up_command_text": (
            manual_auto_collect_watch.get(
                "operator_packet_strategy_operator_decision_follow_up_command_text",
                manual_auto_collect_operator_packet.get(
                    "strategy_operator_decision_follow_up_command_text", ""
                ),
            )
        ),
        "manual_auto_collect_watch_execution_enabled": manual_auto_collect_watch.get(
            "execution_enabled", manual_auto_collect_execution.get("enabled", "")
        ),
        "manual_auto_collect_watch_execution_attempted": manual_auto_collect_watch.get(
            "execution_attempted", manual_auto_collect_execution.get("attempted", "")
        ),
        "manual_auto_collect_watch_execution_returncode": manual_auto_collect_watch.get(
            "execution_returncode", manual_auto_collect_execution.get("returncode", "")
        ),
        "manual_auto_collect_watch_execution_status": manual_auto_collect_watch.get(
            "execution_status", manual_auto_collect_execution.get("status", "")
        ),
        "manual_test_queue_with_optimization_exists": manual_test_queue_with_optimization.get("exists"),
        "manual_test_queue_with_optimization_path": manual_test_queue_with_optimization.get("path", ""),
        "manual_test_queue_with_optimization_generated_at": manual_test_queue_with_optimization.get(
            "generated_at", ""
        ),
        "manual_test_queue_with_optimization_ok": manual_test_queue_with_optimization.get("ok"),
        "manual_test_queue_with_optimization_status": manual_test_queue_with_optimization.get("status", ""),
        "manual_test_queue_with_optimization_next_action": manual_test_queue_with_optimization.get(
            "next_action", ""
        ),
        "manual_test_queue_with_optimization_progress_state": (
            manual_test_queue_with_optimization_handoff.get("progress_state", "")
        ),
        "manual_test_queue_with_optimization_entry_count": manual_test_queue_with_optimization.get(
            "entry_count", ""
        ),
        "manual_test_queue_with_optimization_total_entry_count": manual_test_queue_with_optimization.get(
            "total_entry_count", ""
        ),
        "manual_test_queue_with_optimization_stale_entry_count": manual_test_queue_with_optimization.get(
            "stale_entry_count", ""
        ),
        "manual_test_queue_with_optimization_manual_run_start_marked": (
            manual_test_queue_with_optimization.get("manual_run_start_marked", "")
        ),
        "manual_test_queue_with_optimization_manual_run_start_marked_this_run": (
            manual_test_queue_with_optimization.get("manual_run_start_marked_this_run", "")
        ),
        "manual_test_queue_with_optimization_manual_run_start_preserved": (
            manual_test_queue_with_optimization.get("manual_run_start_preserved", "")
        ),
        "manual_test_queue_with_optimization_manual_run_start_state_count": (
            manual_test_queue_with_optimization.get("manual_run_start_state_count", "")
        ),
        "manual_test_queue_with_optimization_manual_run_start_state_marked_count": (
            manual_test_queue_with_optimization.get("manual_run_start_state_marked_count", "")
        ),
        "manual_test_queue_with_optimization_manual_run_start_effective_after_values": (
            manual_test_queue_with_optimization.get("manual_run_start_effective_after_values", [])
        ),
        "manual_test_queue_with_optimization_manual_run_start_after_override": (
            manual_test_queue_with_optimization.get("manual_run_start_after_override", "")
        ),
        "manual_test_queue_with_optimization_step_count": manual_test_queue_with_optimization.get(
            "step_count", ""
        ),
        "manual_test_queue_with_optimization_ready_to_collect_count": (
            manual_test_queue_with_optimization.get("ready_to_collect_count", "")
        ),
        "manual_test_queue_with_optimization_waiting_count": manual_test_queue_with_optimization.get(
            "waiting_count", ""
        ),
        "manual_test_queue_with_optimization_step_report_ready_count": (
            manual_test_queue_with_optimization.get("step_report_ready_count", "")
        ),
        "manual_test_queue_with_optimization_step_collect_ready_count": (
            manual_test_queue_with_optimization.get("step_collect_ready_count", "")
        ),
        "manual_test_queue_with_optimization_step_waiting_report_count": (
            manual_test_queue_with_optimization.get("step_waiting_report_count", "")
        ),
        "manual_test_queue_with_optimization_step_launch_needed_count": (
            manual_test_queue_with_optimization.get("step_launch_needed_count", "")
        ),
        "manual_test_queue_with_optimization_step_report_ready_ids": (
            manual_test_queue_with_optimization.get("step_report_ready_ids", [])
        ),
        "manual_test_queue_with_optimization_step_collect_ready_ids": (
            manual_test_queue_with_optimization.get("step_collect_ready_ids", [])
        ),
        "manual_test_queue_with_optimization_step_waiting_report_ids": (
            manual_test_queue_with_optimization.get("step_waiting_report_ids", [])
        ),
        "manual_test_queue_with_optimization_step_launch_needed_ids": (
            manual_test_queue_with_optimization.get("step_launch_needed_ids", [])
        ),
        "manual_test_queue_with_optimization_collect_check_command_text": (
            manual_test_queue_with_optimization_handoff.get("collect_check_command_text", "")
        ),
        "manual_test_queue_with_optimization_next_queue_step": (
            manual_test_queue_with_optimization_next_queue_step
        ),
        "manual_test_queue_with_optimization_quick_input": (
            manual_test_queue_with_optimization_quick_input
        ),
        "manual_test_queue_with_optimization_next_quick_input": (
            manual_test_queue_with_optimization_quick_input
        ),
        "manual_test_queue_with_optimization_next_launch_step": (
            manual_test_queue_with_optimization.get("next_launch_step", {})
        ),
        "manual_test_queue_with_optimization_all_collect_ready": (
            manual_test_queue_with_optimization.get("all_collect_ready", "")
        ),
        "manual_test_queue_with_optimization_blocking_reasons": (
            manual_test_queue_with_optimization.get("blocking_reasons", [])
        ),
        "manual_test_queue_with_optimization_static_strategy_config_count": (
            manual_test_queue_with_optimization.get("static_strategy_config_count", "")
        ),
        "manual_test_queue_with_optimization_static_strategy_configs": (
            manual_test_queue_with_optimization.get("static_strategy_configs", [])
        ),
        "manual_test_queue_with_optimization_static_candidate_label_count": (
            manual_test_queue_with_optimization.get("static_candidate_label_count", "")
        ),
        "manual_test_queue_with_optimization_static_candidate_labels": (
            manual_test_queue_with_optimization.get("static_candidate_labels", [])
        ),
        **manual_queue_with_optimization_gate_summary,
        "manual_test_queue_with_optimization_entries": manual_test_queue_with_optimization_entries,
        "manual_test_queue_with_optimization_strategy_tester_targets": (
            manual_test_queue_with_optimization.get("strategy_tester_targets", [])
        ),
        "manual_test_queue_with_optimization_operation_cards": (
            manual_test_queue_with_optimization.get("operation_cards", [])
        ),
        "manual_test_queue_with_optimization_execution_checklist": (
            manual_test_queue_with_optimization.get("execution_checklist", [])
        ),
        "manual_test_queue_with_optimization_operator_handoff": (
            manual_test_queue_with_optimization_handoff
        ),
        "manual_test_queue_with_optimization_operator_handoff_quick_input": (
            manual_test_queue_with_optimization_handoff.get("quick_input", {})
        ),
        "manual_test_queue_with_optimization_next_step_operator_summary": (
            manual_test_queue_with_optimization_handoff.get("next_step_operator_summary", "")
        ),
        "manual_test_queue_with_optimization_next_step_summary": first_present(
            manual_test_queue_with_optimization_handoff.get("next_step_summary"),
            manual_test_queue_with_optimization_handoff.get("next_step_operator_summary"),
        ),
        "manual_test_queue_with_optimization_next_step_collect_filter_summary": (
            manual_test_queue_with_optimization_handoff.get("next_step_collect_filter_summary", "")
        ),
        "manual_queue_launch_with_optimization_exists": (
            manual_queue_launch_with_optimization.get("exists")
        ),
        "manual_queue_launch_with_optimization_path": (
            manual_queue_launch_with_optimization.get("path", "")
        ),
        "manual_queue_launch_with_optimization_generated_at": (
            manual_queue_launch_with_optimization.get("generated_at", "")
        ),
        "manual_queue_launch_with_optimization_ok": manual_queue_launch_with_optimization.get("ok"),
        "manual_queue_launch_with_optimization_status": (
            manual_queue_launch_with_optimization.get("status", "")
        ),
        "manual_queue_launch_with_optimization_next_action": (
            manual_queue_launch_with_optimization.get("next_action", "")
        ),
        "manual_queue_launch_with_optimization_queue_path": (
            manual_queue_launch_with_optimization.get("queue_path", "")
        ),
        "manual_queue_launch_with_optimization_queue_status": (
            manual_queue_launch_with_optimization.get("queue_status", "")
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
        "manual_queue_launch_with_optimization_selected": (
            manual_queue_launch_with_optimization.get("selected", "")
        ),
        "manual_queue_launch_with_optimization_selected_item": (
            manual_queue_launch_with_optimization.get("selected_item", {})
        ),
        "manual_queue_launch_with_optimization_selected_matches_queue_handoff": (
            manual_queue_launch_with_optimization.get("selected_matches_queue_handoff", "")
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
            first_present(
                manual_queue_launch_with_optimization.get(
                    "queue_operator_handoff_next_step_summary"
                ),
                manual_queue_launch_with_optimization.get(
                    "queue_operator_handoff_next_step_operator_summary"
                ),
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
            first_present(
                manual_queue_launch_with_optimization.get(
                    "queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text"
                ),
                manual_queue_launch_with_optimization.get(
                    "queue_operator_handoff_collect_execute_and_refresh_all_command_text"
                ),
            )
        ),
        "manual_queue_launch_with_optimization_launch_command_kind": (
            manual_queue_launch_with_optimization.get("launch_command_kind", "")
        ),
        "manual_queue_launch_with_optimization_command_text": (
            manual_queue_launch_with_optimization.get("command_text", "")
        ),
        "manual_queue_launch_with_optimization_mark_manual_run_start": (
            manual_queue_launch_with_optimization.get("mark_manual_run_start", "")
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
        "manual_queue_launch_with_optimization_blocked": (
            manual_queue_launch_with_optimization.get("blocked", "")
        ),
        "manual_queue_launch_with_optimization_blocked_reasons": (
            manual_queue_launch_with_optimization.get("blocked_reasons", [])
        ),
        "manual_queue_launch_with_optimization_running_terminal_count": (
            manual_queue_launch_with_optimization.get("running_terminal_count", "")
        ),
        "manual_collect_with_optimization_exists": manual_collect_with_optimization.get("exists"),
        "manual_collect_with_optimization_path": manual_collect_with_optimization.get("path", ""),
        "manual_collect_with_optimization_generated_at": manual_collect_with_optimization.get(
            "generated_at", ""
        ),
        "manual_collect_with_optimization_ok": manual_collect_with_optimization.get("ok"),
        "manual_collect_with_optimization_status": manual_collect_with_optimization.get("status", ""),
        "manual_collect_with_optimization_next_action": manual_collect_with_optimization.get(
            "next_action", ""
        ),
        "manual_collect_with_optimization_queue_path": manual_collect_with_optimization.get(
            "queue_path", ""
        ),
        "manual_collect_with_optimization_queue_status": manual_collect_with_optimization.get(
            "queue_status", ""
        ),
        "manual_collect_with_optimization_queue_step_count": manual_collect_with_optimization.get(
            "queue_step_count", ""
        ),
        "manual_collect_with_optimization_queue_step_report_ready_count": (
            manual_collect_with_optimization.get("queue_step_report_ready_count", "")
        ),
        "manual_collect_with_optimization_queue_step_waiting_report_count": (
            manual_collect_with_optimization.get("queue_step_waiting_report_count", "")
        ),
        "manual_collect_with_optimization_queue_step_launch_needed_count": (
            manual_collect_with_optimization.get("queue_step_launch_needed_count", "")
        ),
        "manual_collect_with_optimization_selected_count": manual_collect_with_optimization.get(
            "selected_count", ""
        ),
        "manual_collect_with_optimization_waiting_count": manual_collect_with_optimization.get(
            "waiting_count", ""
        ),
        "manual_collect_with_optimization_invalid_count": manual_collect_with_optimization.get(
            "invalid_count", ""
        ),
        "manual_collect_with_optimization_handoff_state": (
            manual_collect_with_optimization_handoff.get("state", "")
        ),
        "manual_collect_with_optimization_handoff_next_mt5_step": (
            manual_collect_with_optimization_handoff.get("next_mt5_step", {})
        ),
        "mt5_next_operator_action": manual_operator_packet_with_optimization.get(
            "next_operator_action", ""
        ),
        "mt5_next_operator_mode": manual_operator_packet_with_optimization.get(
            "next_operator_mode", ""
        ),
        "mt5_next_operator_launch_state": manual_operator_packet_with_optimization.get(
            "next_operator_launch_state", ""
        ),
        "mt5_next_queue_step": first_present(
            manual_operator_packet_with_optimization.get("next_queue_step"),
            manual_auto_collect_operator_packet.get("next_queue_step"),
            manual_test_queue_with_optimization_handoff.get("quick_input", {}).get("queue_step")
            if isinstance(manual_test_queue_with_optimization_handoff.get("quick_input"), dict)
            else "",
            manual_test_queue_handoff.get("quick_input", {}).get("queue_step")
            if isinstance(manual_test_queue_handoff.get("quick_input"), dict)
            else "",
        ),
        "mt5_next_quick_input": first_present(
            manual_operator_packet_with_optimization.get("next_step_quick_input"),
            manual_test_queue_with_optimization_handoff.get("quick_input"),
            mt5_operator_handoff.get("quick_input"),
            manual_test_queue_handoff.get("quick_input"),
        ),
        "mt5_next_step_operator_summary": first_present(
            manual_operator_packet_with_optimization.get("next_step_operator_summary"),
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_next_step_operator_summary"
            ),
            manual_test_queue_with_optimization_handoff.get("next_step_operator_summary"),
            mt5_operator_handoff.get("next_step_operator_summary"),
            manual_test_queue_handoff.get("next_step_operator_summary"),
        ),
        "mt5_next_step_summary": first_present(
            manual_operator_packet_with_optimization.get("next_step_summary"),
            manual_queue_launch_with_optimization.get("queue_operator_handoff_next_step_summary"),
            manual_test_queue_with_optimization_handoff.get("next_step_summary"),
            mt5_operator_handoff.get("next_step_summary"),
            manual_queue_launch.get("queue_operator_handoff_next_step_summary"),
            manual_test_queue_handoff.get("next_step_summary"),
            manual_operator_packet_with_optimization.get("next_step_operator_summary"),
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_next_step_operator_summary"
            ),
            manual_test_queue_with_optimization_handoff.get("next_step_operator_summary"),
            mt5_operator_handoff.get("next_step_operator_summary"),
            manual_test_queue_handoff.get("next_step_operator_summary"),
        ),
        "mt5_next_step_collect_filter_summary": first_present(
            manual_operator_packet_with_optimization.get("next_step_collect_filter_summary"),
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_next_step_collect_filter_summary"
            ),
            manual_test_queue_with_optimization_handoff.get("next_step_collect_filter_summary"),
            mt5_operator_handoff.get("next_step_collect_filter_summary"),
            manual_test_queue_handoff.get("next_step_collect_filter_summary"),
        ),
        "mt5_next_manual_run_start_effective_after": first_present(
            manual_operator_packet_with_optimization.get("manual_run_start_effective_after"),
            manual_queue_launch_with_optimization.get("manual_run_start_after"),
            manual_test_queue_with_optimization.get("manual_run_start_after_override"),
            manual_strategy_tester.get("manual_run_start_after"),
        ),
        "mt5_next_manual_run_start_effective_after_values": (
            manual_operator_packet_with_optimization.get(
                "manual_run_start_effective_after_values", []
            )
        ),
        "mt5_auto_launch_command_available": manual_operator_packet_with_optimization.get(
            "auto_launch_command_available", ""
        ),
        "mt5_auto_launch_blocked": manual_operator_packet_with_optimization.get(
            "auto_launch_blocked", ""
        ),
        "mt5_auto_launch_blocked_reasons": manual_operator_packet_with_optimization.get(
            "auto_launch_blocked_reasons", []
        ),
        "mt5_auto_launch_command_text": manual_operator_packet_with_optimization.get(
            "auto_launch_command_text", ""
        ),
        "mt5_auto_launch_note": manual_operator_packet_with_optimization.get(
            "auto_launch_note", ""
        ),
        "mt5_back_forward_quick_start_status": manual_operator_packet_with_optimization.get(
            "back_forward_quick_start_status",
            payload.get(
                "manual_operator_packet_with_optimization_back_forward_quick_start_status",
                "",
            ),
        ),
        "mt5_back_forward_quick_start_quick_inputs": (
            manual_operator_packet_with_optimization.get(
                "back_forward_quick_start_quick_inputs",
                payload.get(
                    "manual_operator_packet_with_optimization_back_forward_quick_start_quick_inputs",
                    [],
                ),
            )
        ),
        "mt5_back_forward_quick_start_current_quick_input": (
            manual_operator_packet_with_optimization.get(
                "back_forward_quick_start_current_quick_input",
                payload.get(
                    "manual_operator_packet_with_optimization_back_forward_quick_start_current_quick_input",
                    {},
                ),
            )
        ),
        "mt5_back_forward_quick_start_collect_command_text": (
            manual_operator_packet_with_optimization.get(
                "back_forward_quick_start_collect_command_text",
                "",
            )
        ),
        "mt5_strategy_operator_decision_status": first_present(
            manual_operator_packet_with_optimization.get("strategy_operator_decision_status"),
            manual_auto_collect_operator_packet.get("strategy_operator_decision_status"),
        ),
        "mt5_strategy_operator_decision_verdict": first_present(
            manual_operator_packet_with_optimization.get("strategy_operator_decision_verdict"),
            manual_auto_collect_operator_packet.get("strategy_operator_decision_verdict"),
        ),
        "mt5_strategy_operator_decision_primary_blocker": first_present(
            manual_operator_packet_with_optimization.get(
                "strategy_operator_decision_primary_blocker"
            ),
            manual_auto_collect_operator_packet.get("strategy_operator_decision_primary_blocker"),
        ),
        "mt5_strategy_operator_decision_next_action": first_present(
            manual_operator_packet_with_optimization.get("strategy_operator_decision_next_action"),
            manual_auto_collect_operator_packet.get("strategy_operator_decision_next_action"),
        ),
        "mt5_strategy_operator_decision_command_text": first_present(
            manual_operator_packet_with_optimization.get(
                "strategy_operator_decision_command_text"
            ),
            manual_auto_collect_operator_packet.get("strategy_operator_decision_command_text"),
        ),
        "mt5_collect_dry_run_command_text": first_present(
            manual_auto_collect_watch.get("collect_dry_run_command_text"),
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_collect_dry_run_command_text"
            ),
            manual_queue_launch.get("queue_operator_handoff_collect_dry_run_command_text"),
            manual_collect_with_optimization_handoff.get("dry_run_command_text"),
            manual_collect_handoff.get("dry_run_command_text"),
            manual_test_queue_with_optimization.get("collect_check_command_text"),
            manual_test_queue.get("collect_check_command_text"),
        ),
        "mt5_collect_execute_command_text": first_present(
            manual_auto_collect_watch.get("collect_execute_command_text"),
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_collect_execute_command_text"
            ),
            manual_queue_launch.get("queue_operator_handoff_collect_execute_command_text"),
            manual_collect_with_optimization_handoff.get("execute_command_text"),
            manual_collect_handoff.get("execute_command_text"),
        ),
        "mt5_collect_execute_and_refresh_analysis_command_text": first_present(
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_collect_execute_and_refresh_analysis_command_text"
            ),
            manual_queue_launch.get(
                "queue_operator_handoff_collect_execute_and_refresh_analysis_command_text"
            ),
            manual_collect_with_optimization_handoff.get(
                "execute_and_refresh_analysis_command_text"
            ),
            manual_collect_handoff.get("execute_and_refresh_analysis_command_text"),
        ),
        "mt5_collect_execute_and_refresh_all_command_text": first_present(
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text"
            ),
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_collect_execute_and_refresh_all_command_text"
            ),
            manual_queue_launch.get(
                "queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text"
            ),
            manual_queue_launch.get(
                "queue_operator_handoff_collect_execute_and_refresh_all_command_text"
            ),
            manual_collect_with_optimization_handoff.get(
                "execute_and_refresh_full_analysis_command_text"
            ),
            manual_collect_with_optimization_handoff.get(
                "execute_and_refresh_all_command_text"
            ),
            manual_collect_handoff.get("execute_and_refresh_full_analysis_command_text"),
            manual_collect_handoff.get("execute_and_refresh_all_command_text"),
        ),
        "mt5_collect_execute_and_refresh_full_analysis_command_text": first_present(
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text"
            ),
            manual_queue_launch_with_optimization.get(
                "queue_operator_handoff_collect_execute_and_refresh_all_command_text"
            ),
            manual_queue_launch.get(
                "queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text"
            ),
            manual_queue_launch.get(
                "queue_operator_handoff_collect_execute_and_refresh_all_command_text"
            ),
            manual_collect_with_optimization_handoff.get(
                "execute_and_refresh_full_analysis_command_text"
            ),
            manual_collect_with_optimization_handoff.get(
                "execute_and_refresh_all_command_text"
            ),
            manual_collect_handoff.get("execute_and_refresh_full_analysis_command_text"),
            manual_collect_handoff.get("execute_and_refresh_all_command_text"),
        ),
        "mt5_manual_queue_status": first_present(
            manual_test_queue_with_optimization.get("status"),
            manual_test_queue.get("status"),
        ),
        "mt5_manual_queue_progress_state": first_present(
            manual_test_queue_with_optimization.get("progress_state"),
            manual_test_queue.get("progress_state"),
        ),
        "mt5_manual_queue_waiting_count": first_present(
            manual_test_queue_with_optimization.get("waiting_count"),
            manual_test_queue.get("waiting_count"),
        ),
        "mt5_manual_queue_step_launch_needed_count": first_present(
            manual_test_queue_with_optimization.get("step_launch_needed_count"),
            manual_test_queue.get("step_launch_needed_count"),
        ),
        "manual_operator_packet_with_optimization_exists": manual_operator_packet_with_optimization.get(
            "exists"
        ),
        "manual_operator_packet_with_optimization_path": manual_operator_packet_with_optimization.get(
            "path", ""
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
        "manual_operator_packet_with_optimization_next_step_quick_input": (
            manual_operator_packet_with_optimization.get("next_step_quick_input", {})
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
            manual_operator_packet_with_optimization.get("manual_run_start_state_marked_count", "")
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
        "manual_operator_packet_with_optimization_next_step_operator_summary": (
            manual_operator_packet_with_optimization.get("next_step_operator_summary", "")
        ),
        "manual_operator_packet_with_optimization_next_step_summary": first_present(
            manual_operator_packet_with_optimization.get("next_step_summary"),
            manual_operator_packet_with_optimization.get("next_step_operator_summary"),
        ),
        "manual_operator_packet_with_optimization_next_step_collect_filter_summary": (
            manual_operator_packet_with_optimization.get("next_step_collect_filter_summary", "")
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_status": (
            manual_operator_packet_with_optimization.get(
                "strategy_back_forward_decision_status", ""
            )
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_adoptable": (
            manual_operator_packet_with_optimization.get(
                "strategy_back_forward_decision_adoptable", ""
            )
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_next_action": (
            manual_operator_packet_with_optimization.get(
                "strategy_back_forward_decision_next_action", ""
            )
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_reason": (
            manual_operator_packet_with_optimization.get(
                "strategy_back_forward_decision_reason", ""
            )
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_collect_command_text": (
            manual_operator_packet_with_optimization.get(
                "strategy_back_forward_decision_collect_command_text", ""
            )
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_command_text": (
            manual_operator_packet_with_optimization.get(
                "strategy_back_forward_decision_sample_shortage_recovery_command_text",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_range_strategy": (
            manual_operator_packet_with_optimization.get(
                "strategy_back_forward_decision_sample_shortage_recovery_range_strategy",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date": (
            manual_operator_packet_with_optimization.get(
                "strategy_back_forward_decision_sample_shortage_recovery_suggested_from_date",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date": (
            manual_operator_packet_with_optimization.get(
                "strategy_back_forward_decision_sample_shortage_recovery_suggested_to_date",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_status": (
            manual_operator_packet_with_optimization.get(
                "strategy_operator_decision_status",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_verdict": (
            manual_operator_packet_with_optimization.get(
                "strategy_operator_decision_verdict",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_adoptable": (
            manual_operator_packet_with_optimization.get(
                "strategy_operator_decision_adoptable",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_primary_blocker": (
            manual_operator_packet_with_optimization.get(
                "strategy_operator_decision_primary_blocker",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_primary_reason": (
            manual_operator_packet_with_optimization.get(
                "strategy_operator_decision_primary_reason",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_next_action": (
            manual_operator_packet_with_optimization.get(
                "strategy_operator_decision_next_action",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_summary": (
            manual_operator_packet_with_optimization.get(
                "strategy_operator_decision_summary",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_command_text": (
            manual_operator_packet_with_optimization.get(
                "strategy_operator_decision_command_text",
                "",
            )
        ),
        "manual_operator_packet_with_optimization_strategy_operator_decision_follow_up_command_text": (
            manual_operator_packet_with_optimization.get(
                "strategy_operator_decision_follow_up_command_text",
                "",
            )
        ),
        "pass_budget_available": pass_budget.get("available"),
        "pass_budget_source": pass_budget.get("source", ""),
        "pass_budget_set_file": pass_budget.get("set_file", ""),
        "pass_budget_set_file_exists": pass_budget.get("set_file_exists"),
        "pass_budget_set_file_reestimated": pass_budget.get("set_file_reestimated"),
        "pass_budget_optimized_input_count": pass_budget.get("optimized_input_count"),
        "pass_budget_full_factorial": pass_budget.get("estimated_full_factorial_passes"),
        "pass_budget_executed_tester_xml_rows": pass_budget.get("executed_tester_xml_rows", {}),
        "pass_budget_ratio_vs_full_factorial": pass_budget.get("ratio_vs_full_factorial", {}),
        "pass_budget_max_executed_tester_xml_rows": pass_budget.get("max_executed_tester_xml_rows"),
        "pass_budget_full_factorial_progress_ratio": pass_budget.get("full_factorial_progress_ratio"),
        "pass_budget_full_factorial_remaining_upper_bound": pass_budget.get("full_factorial_remaining_upper_bound"),
        "pass_budget_full_factorial_complete_if_exhaustive": pass_budget.get("full_factorial_complete_if_exhaustive"),
        "next_action_run_exists": next_runner.get("exists"),
        "next_action_run_ok": next_runner.get("ok"),
        "next_action_run_dry_run": next_runner.get("dry_run"),
        "next_action_run_found": next_runner.get("found"),
        "next_action_run_target": next_runner.get("target", ""),
        "next_action_run_promotion_gate_current": next_runner.get("promotion_gate_current"),
        "next_action_run_promotion_gate_generated_at_match": next_runner.get("promotion_gate_generated_at_match"),
        "next_action_run_promotion_gate_decision_match": next_runner.get("promotion_gate_decision_match"),
        "next_action_run_runner_promotion_generated_at": next_runner.get("runner_promotion_generated_at", ""),
        "next_action_run_current_promotion_generated_at": next_runner.get("current_promotion_generated_at", ""),
        "next_action_run_selected_action_present": next_runner.get("selected_action_present"),
        "next_action_run_selected_action_current": next_runner.get("selected_action_current"),
        "next_action_run_current_for_execution": next_runner.get("current_for_execution"),
        "next_action_run_gate_stale_reason": next_runner.get("gate_stale_reason", ""),
        "next_action_run_selected_action_mismatches": next_runner.get("selected_action_mismatches", []),
        "next_action_run_blocking_prior_actions": next_runner.get("blocking_prior_actions", []),
        "next_action_run_blocking_prior_action_count": next_runner.get("blocking_prior_action_count", 0),
        "next_action_run_blocking_prior_action_summary": next_runner.get(
            "blocking_prior_action_summary", ""
        ),
        "next_action_run_advisory_prior_actions": next_runner.get("advisory_prior_actions", []),
        "next_action_run_advisory_prior_action_count": next_runner.get("advisory_prior_action_count", 0),
        "next_action_run_advisory_prior_action_summary": next_runner.get(
            "advisory_prior_action_summary", ""
        ),
        "next_action_run_action_reason": next_runner.get("action_reason", ""),
        "next_action_run_primary_note": next_runner.get("primary_note", ""),
        "next_action_run_execute_command_text": next_runner.get("execute_command_text", ""),
        "next_action_run_collect_only_command_text": next_runner.get("collect_only_command_text", ""),
        "next_action_run_collect_only_note": next_runner.get("collect_only_note", ""),
        "next_action_run_manual_collect_only_command_text": next_runner.get(
            "manual_collect_only_command_text", ""
        ),
        "next_action_run_manual_run_start_after": next_runner.get("manual_run_start_after", ""),
        "next_action_run_manual_collect_ready": next_runner.get("manual_collect_ready", ""),
        "next_action_run_manual_collect_status": next_runner.get("manual_collect_status", ""),
        "next_action_run_manual_collect_csv_count": next_runner.get("manual_collect_csv_count", ""),
        "next_action_run_manual_collect_modified_after": next_runner.get(
            "manual_collect_modified_after", ""
        ),
        "next_action_run_manual_collect_reason": next_runner.get("manual_collect_reason", ""),
        "next_action_run_manual_collect_blocking_reasons": next_runner.get(
            "manual_collect_blocking_reasons", []
        ),
        "next_action_run_manual_collect_next_action": next_runner.get(
            "manual_collect_next_action", ""
        ),
        "next_action_run_manual_step_count": next_runner.get("manual_step_count", ""),
        "next_action_run_manual_steps": next_runner.get("manual_steps", []),
        "next_action_run_evidence_role": next_runner.get("evidence_role", ""),
        "next_action_run_diagnostic_only": next_runner.get("diagnostic_only", ""),
        "next_action_run_promotion_evidence": next_runner.get("promotion_evidence", ""),
        "next_action_run_action_context_keys": next_action_context_keys,
        "next_action_run_related_execution_count": (
            len(next_related_execution_rows)
            if next_related_execution_rows
            else len(next_related_execution_keys)
        ),
        "next_action_run_related_execution_keys": next_related_execution_keys,
        "next_action_run_related_executions": next_related_execution_rows,
        "next_action_run_kind": next_runner.get("kind", ""),
        "next_action_run_focus_side": next_runner.get("focus_side", ""),
        "next_action_run_optimization_mode": next_runner.get("optimization_mode", ""),
        "next_action_run_config": next_runner.get("config", ""),
        "next_action_run_set": next_runner.get("set", ""),
        "next_action_run_output_set": next_runner.get("output_set", ""),
        "next_action_run_planned_outputs": planned_outputs_bundle(
            primary_outputs,
            archive_outputs,
            follow_up_outputs,
            follow_up_archive_outputs,
        ),
        "next_action_run_primary_planned_outputs": primary_outputs,
        "next_action_run_archive_preview_planned_outputs": archive_outputs,
        "next_action_run_follow_up_planned_outputs": follow_up_outputs,
        "next_action_run_follow_up_archive_preview_planned_outputs": follow_up_archive_outputs,
        "next_action_run_primary_output_json": primary_outputs.get("output_json", ""),
        "next_action_run_primary_output_md": primary_outputs.get("output_md", ""),
        "next_action_run_primary_optimization_output_json": primary_outputs.get("optimization_output_json", ""),
        "next_action_run_primary_recommendation_output_json": primary_outputs.get(
            "recommendation_output_json", ""
        ),
        "next_action_run_archive_preview_output_json": archive_outputs.get("output_json", ""),
        "next_action_run_archive_preview_output_md": archive_outputs.get("output_md", ""),
        "next_action_run_archive_run_id": next_runner.get("agent_csv_archive_run_id", ""),
        "next_action_run_timeout_seconds": next_runner.get("timeout_seconds", ""),
        "next_action_run_timeout_minutes": next_runner.get("timeout_minutes", ""),
        "next_action_run_timeout_note": next_runner.get("timeout_note", ""),
        "next_action_run_timeout_start_reference_at": next_runner.get("timeout_start_reference_at", ""),
        "next_action_run_timeout_deadline_if_started_now": next_runner.get("timeout_deadline_if_started_now", ""),
        "next_action_run_timeout_deadline_epoch_if_started_now": next_runner.get(
            "timeout_deadline_epoch_if_started_now"
        ),
        "next_action_run_optimized_input_count": next_runner.get("optimized_input_count", ""),
        "next_action_run_estimated_full_factorial_passes": next_runner.get("estimated_full_factorial_passes", ""),
        "next_action_run_latest_executed_tester_xml_rows": next_runner.get("latest_executed_tester_xml_rows", ""),
        "next_action_run_primary_execution_class": next_runner.get("primary_execution_class", ""),
        "next_action_run_primary_is_mt5_tester_run": next_runner.get("primary_is_mt5_tester_run", ""),
        "next_action_run_allow_non_tester_primary": next_runner.get("allow_non_tester_primary"),
        "next_action_run_run_archive_preview": next_runner.get("run_archive_preview"),
        "next_action_run_archive_preview_ok": next_runner.get("archive_preview_ok", ""),
        "next_action_run_archive_preview_returncode": next_runner.get("archive_preview_returncode", ""),
        "next_action_run_primary_executed": next_runner.get("primary_executed"),
        "next_action_run_primary_ok": next_runner.get("primary_ok", ""),
        "next_action_run_primary_returncode": next_runner.get("primary_returncode", ""),
        "next_action_run_run_follow_up": next_runner.get("run_follow_up"),
        "next_action_run_follow_up_kind": next_runner.get("follow_up_kind", ""),
        "next_action_run_follow_up_output": next_runner.get("follow_up_output_set", ""),
        "next_action_run_follow_up_output_json": follow_up_outputs.get("output_json", ""),
        "next_action_run_follow_up_output_md": follow_up_outputs.get("output_md", ""),
        "next_action_run_follow_up_archive_preview_output_json": follow_up_archive_outputs.get("output_json", ""),
        "next_action_run_follow_up_archive_preview_output_md": follow_up_archive_outputs.get("output_md", ""),
        "next_action_run_score_weight_follow_up_status": (
            next_runner.get("score_weight_follow_up_status", score_weight_follow_up.get("status", ""))
        ),
        "next_action_run_score_weight_follow_up_regime_status": (
            next_runner.get(
                "score_weight_follow_up_regime_status",
                score_weight_follow_up.get("regime_status", ""),
            )
        ),
        "next_action_run_score_weight_follow_up_sample_shortage": (
            next_runner.get(
                "score_weight_follow_up_sample_shortage",
                score_weight_follow_up.get("sample_shortage", ""),
            )
        ),
        "next_action_run_score_weight_follow_up_walk_missing": (
            next_runner.get(
                "score_weight_follow_up_walk_missing",
                score_weight_follow_up.get("walk_forward_missing_test_weight_count", ""),
            )
        ),
        "next_action_run_score_weight_follow_up_walk_required": (
            next_runner.get(
                "score_weight_follow_up_walk_required",
                score_weight_follow_up.get("walk_forward_required_test_weight_count", ""),
            )
        ),
        "next_action_run_score_weight_follow_up_walk_folds": (
            next_runner.get(
                "score_weight_follow_up_walk_folds",
                score_weight_follow_up.get("walk_forward_folds_with_weight_trades", ""),
            )
        ),
        "next_action_run_score_weight_follow_up_walk_required_folds": (
            next_runner.get(
                "score_weight_follow_up_walk_required_folds",
                score_weight_follow_up.get("walk_forward_required_folds_with_weight_trades", ""),
            )
        ),
        "next_action_run_score_weight_follow_up_regime_missing": (
            next_runner.get(
                "score_weight_follow_up_regime_missing",
                score_weight_follow_up.get("regime_missing_test_weight_count", ""),
            )
        ),
        "next_action_run_score_weight_follow_up_regime_required": (
            next_runner.get(
                "score_weight_follow_up_regime_required",
                score_weight_follow_up.get("regime_required_test_weight_count", ""),
            )
        ),
        "next_action_run_score_weight_follow_up_regime_folds": (
            next_runner.get(
                "score_weight_follow_up_regime_folds",
                score_weight_follow_up.get("regime_folds_with_weight_trades", ""),
            )
        ),
        "next_action_run_score_weight_follow_up_regime_required_folds": (
            next_runner.get(
                "score_weight_follow_up_regime_required_folds",
                score_weight_follow_up.get("regime_required_folds_with_weight_trades", ""),
            )
        ),
        "next_action_run_score_weight_set_walk_forward_status": (
            next_runner.get(
                "score_weight_set_walk_forward_status",
                score_weight_set_result.get("walk_forward_status", ""),
            )
        ),
        "next_action_run_score_weight_set_skip_reason": (
            next_runner.get("score_weight_set_skip_reason", score_weight_set_result.get("skip_reason", ""))
        ),
        "next_action_run_follow_up_executed": next_runner.get("follow_up_executed"),
        "next_action_run_follow_up_ok": next_runner.get("follow_up_ok", ""),
        "next_action_run_follow_up_returncode": next_runner.get("follow_up_returncode", ""),
        "next_action_run_follow_up_skipped": next_runner.get("follow_up_skipped", ""),
        "next_action_run_archive_preview_post_exists": archive_post_agent_csv.get("exists"),
        "next_action_run_archive_preview_post_ok": archive_post_agent_csv.get("ok"),
        "next_action_run_archive_preview_post_execute": archive_post_agent_csv.get("execute"),
        "next_action_run_archive_preview_post_count": archive_post_agent_csv.get("count"),
        "next_action_run_archive_preview_post_run_id": archive_post_agent_csv.get("run_id", ""),
        "next_action_run_archive_preview_post_close_rows": archive_post_agent_csv.get("close_rows", ""),
        "next_action_run_archive_preview_post_validation_required": archive_post_validation.get("required"),
        "next_action_run_archive_preview_post_validation_ok": archive_post_validation.get("ok"),
        "next_action_run_archive_preview_post_validation_reasons": archive_post_validation.get("reasons", []),
        "next_action_run_archive_preview_post_validation_output_json": archive_post_validation.get("output_json", ""),
        "next_action_run_primary_post_tester_exists": primary_post_tester.get("exists"),
        "next_action_run_primary_post_tester_ok": primary_post_tester.get("ok"),
        "next_action_run_primary_post_tester_blocked": primary_post_tester.get("blocked"),
        "next_action_run_primary_post_tester_source_time_blocked": primary_post_tester.get("source_time_blocked"),
        "next_action_run_primary_post_tester_report_fallback_blocked": primary_post_tester.get(
            "report_fallback_blocked"
        ),
        "next_action_run_primary_post_tester_elapsed_seconds": primary_post_tester.get(
            "terminal_elapsed_seconds", ""
        ),
        "next_action_run_primary_post_optimization_exists": primary_post_optimization.get("exists"),
        "next_action_run_primary_post_optimization_closed": primary_post_optimization.get("closed"),
        "next_action_run_primary_post_optimization_pf": primary_post_optimization.get("pf"),
        "next_action_run_primary_post_optimization_avg_price_r": primary_post_optimization.get("avg_price_r"),
        "next_action_run_primary_post_optimization_back_rows": primary_post_optimization.get("back_rows"),
        "next_action_run_primary_post_optimization_forward_rows": primary_post_optimization.get("forward_rows"),
        "next_action_run_primary_post_recommendation_exists": primary_post_recommendation.get("exists"),
        "next_action_run_primary_post_recommendation_adoptable": primary_post_recommendation.get("adoptable"),
        "next_action_run_primary_post_recommendation_next_set": primary_post_recommendation.get("next_set", ""),
        "next_action_run_primary_post_recommendation_skip_reason": primary_post_recommendation.get(
            "skip_reason", ""
        ),
        "next_action_run_primary_post_validation_required": primary_post_validation.get("required"),
        "next_action_run_primary_post_validation_ok": primary_post_validation.get("ok"),
        "next_action_run_primary_post_validation_reasons": primary_post_validation.get("reasons", []),
        "next_action_run_primary_post_validation_output_json": primary_post_validation.get("output_json", ""),
        "next_action_run_follow_up_post_tester_exists": follow_up_post_tester.get("exists"),
        "next_action_run_follow_up_post_tester_ok": follow_up_post_tester.get("ok"),
        "next_action_run_follow_up_post_tester_blocked": follow_up_post_tester.get("blocked"),
        "next_action_run_follow_up_post_forward_exists": follow_up_post_forward.get("exists"),
        "next_action_run_follow_up_post_forward_ok": follow_up_post_forward.get("ok"),
        "next_action_run_follow_up_post_forward_closed": follow_up_post_forward.get("closed"),
        "next_action_run_follow_up_post_forward_pf": follow_up_post_forward.get("pf"),
        "next_action_run_follow_up_post_forward_ready_for_demo_review": follow_up_post_forward.get(
            "ready_for_demo_review"
        ),
        "next_action_run_follow_up_archive_preview_post_exists": follow_up_archive_post_agent_csv.get("exists"),
        "next_action_run_follow_up_archive_preview_post_ok": follow_up_archive_post_agent_csv.get("ok"),
        "next_action_run_follow_up_archive_preview_post_execute": follow_up_archive_post_agent_csv.get("execute"),
        "next_action_run_follow_up_archive_preview_post_count": follow_up_archive_post_agent_csv.get("count"),
        "next_action_run_follow_up_archive_preview_post_run_id": follow_up_archive_post_agent_csv.get("run_id", ""),
        "next_action_run_follow_up_post_validation_required": follow_up_post_validation.get("required"),
        "next_action_run_follow_up_post_validation_ok": follow_up_post_validation.get("ok"),
        "next_action_run_follow_up_post_validation_reasons": follow_up_post_validation.get("reasons", []),
        "next_action_run_follow_up_post_validation_output_json": follow_up_post_validation.get("output_json", ""),
        "next_action_run_follow_up_archive_preview_post_validation_required": (
            follow_up_archive_post_validation.get("required")
        ),
        "next_action_run_follow_up_archive_preview_post_validation_ok": follow_up_archive_post_validation.get("ok"),
        "next_action_run_follow_up_archive_preview_post_validation_reasons": (
            follow_up_archive_post_validation.get("reasons", [])
        ),
        "next_action_run_follow_up_archive_preview_post_validation_output_json": (
            follow_up_archive_post_validation.get("output_json", "")
        ),
        "next_action_run_blocked_before_primary": next_runner.get("blocked_before_primary", ""),
        "next_action_run_blocked_before_follow_up": next_runner.get("blocked_before_follow_up", ""),
        "next_action_run_blocked_after_primary": next_runner.get("blocked_after_primary", ""),
        "next_action_run_blocked_after_follow_up": next_runner.get("blocked_after_follow_up", ""),
        "next_action_run_reason": next_runner.get("reason", ""),
        "next_action_execution_ready": next_execution.get("ready"),
        "next_action_execution_status": next_execution.get("status", ""),
        "next_action_execution_reasons": next_execution.get("reasons", []),
        "next_action_execution_required_fresh_artifacts": next_execution.get("required_fresh_artifacts", []),
        "next_action_execution_stale_required_artifacts": next_execution.get("stale_required_artifacts", []),
        "next_action_execution_runner_execute_hint": next_execution.get("runner_execute_hint", ""),
        "next_action_execution_collect_only_hint": next_execution.get("collect_only_hint", ""),
        "next_action_local_execution_ready": next_local_execution.get("ready"),
        "next_action_local_execution_status": next_local_execution.get("status", ""),
        "next_action_local_execution_reasons": next_local_execution.get("reasons", []),
        "next_action_local_execution_required_fresh_artifacts": (
            next_local_execution.get("required_fresh_artifacts", [])
        ),
        "next_action_local_execution_stale_required_artifacts": (
            next_local_execution.get("stale_required_artifacts", [])
        ),
        "next_action_local_execution_requires_allow_non_tester_primary": (
            next_local_execution.get("requires_allow_non_tester_primary")
        ),
        "next_action_local_execution_runner_execute_hint": next_local_execution.get("runner_execute_hint", ""),
        "next_action_local_execution_primary_command": next_local_execution.get("primary_command", ""),
        "next_action_local_execution_optimization_report_current": local_optimization_evidence.get("current"),
        "next_action_local_execution_optimization_report_status": local_optimization_evidence.get("status", ""),
        "next_action_local_execution_optimization_report_reasons": local_optimization_evidence.get("reasons", []),
        "next_action_local_execution_optimization_report_generated_at": (
            local_optimization_evidence.get("report_generated_at", "")
        ),
        "next_action_local_execution_tester_optimization_generated_at": (
            local_optimization_evidence.get("tester_optimization_generated_at", "")
        ),
        "back_forward_run_exists": back_forward_runner.get("exists"),
        "back_forward_run_ok": back_forward_runner.get("ok"),
        "back_forward_run_dry_run": back_forward_runner.get("dry_run"),
        "back_forward_run_execute": back_forward_runner.get("execute"),
        "back_forward_run_collect_only": back_forward_runner.get("collect_only", ""),
        "back_forward_run_launch_mt5": back_forward_runner.get("launch_mt5", ""),
        "back_forward_run_run_archive_preview": back_forward_runner.get("run_archive_preview", ""),
        "back_forward_run_evidence_state": back_forward_runner.get("evidence_state", ""),
        "back_forward_run_run_id_prefix": back_forward_runner.get("run_id_prefix", ""),
        "back_forward_run_mode": back_forward_runner.get("mode", ""),
        "back_forward_run_generated_at": back_forward_runner.get("generated_at", ""),
        "back_forward_run_manual_collect_only_command_text": back_forward_runner.get(
            "manual_collect_only_command_text", ""
        ),
        "back_forward_run_manual_run_start_after": back_forward_runner.get(
            "manual_run_start_after", ""
        ),
        "back_forward_run_manual_collect_ready": back_forward_runner.get("manual_collect_ready", ""),
        "back_forward_run_manual_collect_status": back_forward_runner.get("manual_collect_status", ""),
        "back_forward_run_manual_collect_csv_count": back_forward_runner.get("manual_collect_csv_count", ""),
        "back_forward_run_manual_collect_modified_after": back_forward_runner.get(
            "manual_collect_modified_after", ""
        ),
        "back_forward_run_manual_collect_reason": back_forward_runner.get(
            "manual_collect_reason", ""
        ),
        "back_forward_run_manual_collect_blocking_reasons": back_forward_runner.get(
            "manual_collect_blocking_reasons", []
        ),
        "back_forward_run_manual_collect_next_action": back_forward_runner.get(
            "manual_collect_next_action", ""
        ),
        "back_forward_run_manual_step_count": back_forward_runner.get("manual_step_count", ""),
        "back_forward_run_manual_steps": back_forward_runner.get("manual_steps", []),
        "back_forward_run_mt5_strategy_tester_pack_available": back_forward_runner.get(
            "mt5_strategy_tester_pack_available",
            back_forward_strategy_pack.get("available", bool(back_forward_strategy_pack_steps)),
        ),
        "back_forward_run_mt5_strategy_tester_pack_ready_for_manual_mt5_run": back_forward_runner.get(
            "mt5_strategy_tester_pack_ready_for_manual_mt5_run",
            back_forward_strategy_pack.get("ready_for_manual_mt5_run", ""),
        ),
        "back_forward_run_mt5_strategy_tester_pack_status": back_forward_runner.get(
            "mt5_strategy_tester_pack_status",
            back_forward_strategy_pack.get("status", ""),
        ),
        "back_forward_run_mt5_strategy_tester_pack_next_action": back_forward_runner.get(
            "mt5_strategy_tester_pack_next_action",
            back_forward_strategy_pack.get("next_action", ""),
        ),
        "back_forward_run_mt5_strategy_tester_pack_is_back_forward_pair": back_forward_runner.get(
            "mt5_strategy_tester_pack_is_back_forward_pair",
            back_forward_strategy_pack.get("is_back_forward_pair", ""),
        ),
        "back_forward_run_mt5_strategy_tester_pack_manual_run_start_after": back_forward_runner.get(
            "mt5_strategy_tester_pack_manual_run_start_after",
            back_forward_strategy_pack.get("manual_run_start_after", ""),
        ),
        "back_forward_run_mt5_strategy_tester_pack_collect_command_text": back_forward_runner.get(
            "mt5_strategy_tester_pack_collect_command_text",
            back_forward_strategy_pack.get("collect_command_text", ""),
        ),
        "back_forward_run_mt5_strategy_tester_pack_collect_ready": back_forward_runner.get(
            "mt5_strategy_tester_pack_collect_ready",
            back_forward_strategy_pack.get("collect_ready", ""),
        ),
        "back_forward_run_mt5_strategy_tester_pack_collect_status": back_forward_runner.get(
            "mt5_strategy_tester_pack_collect_status",
            back_forward_strategy_pack.get("collect_status", ""),
        ),
        "back_forward_run_mt5_strategy_tester_pack_collect_reason": back_forward_runner.get(
            "mt5_strategy_tester_pack_collect_reason",
            back_forward_strategy_pack.get("collect_reason", ""),
        ),
        "back_forward_run_mt5_strategy_tester_pack_step_count": back_forward_runner.get(
            "mt5_strategy_tester_pack_step_count",
            back_forward_strategy_pack.get("step_count", len(back_forward_strategy_pack_steps)),
        ),
        "back_forward_run_mt5_strategy_tester_pack_steps": back_forward_strategy_pack_steps,
        "manual_prerequisites_ready": back_forward_runner.get(
            "manual_prerequisites_ready", ""
        ),
        "manual_prerequisites_reasons": back_forward_runner.get(
            "manual_prerequisites_reasons", []
        ),
        "manual_prerequisites_compile_status_path": back_forward_runner.get(
            "manual_prerequisites_compile_status_path", ""
        ),
        "manual_prerequisites_generated_at": back_forward_runner.get(
            "manual_prerequisites_generated_at", ""
        ),
        "back_forward_plan_validation_ready": back_forward_runner.get(
            "back_forward_plan_validation_ready", ""
        ),
        "back_forward_plan_validation_status": back_forward_runner.get(
            "back_forward_plan_validation_status", ""
        ),
        "back_forward_plan_validation_reasons": back_forward_runner.get(
            "back_forward_plan_validation_reasons", []
        ),
        "back_forward_run_manual_prerequisites_ready": back_forward_runner.get(
            "manual_prerequisites_ready", ""
        ),
        "back_forward_run_manual_prerequisites_reasons": back_forward_runner.get(
            "manual_prerequisites_reasons", []
        ),
        "back_forward_run_manual_prerequisites_compile_status_path": back_forward_runner.get(
            "manual_prerequisites_compile_status_path", ""
        ),
        "back_forward_run_manual_prerequisites_generated_at": back_forward_runner.get(
            "manual_prerequisites_generated_at", ""
        ),
        "back_forward_run_plan_validation_ready": back_forward_runner.get(
            "back_forward_plan_validation_ready", ""
        ),
        "back_forward_run_plan_validation_status": back_forward_runner.get(
            "back_forward_plan_validation_status", ""
        ),
        "back_forward_run_plan_validation_reasons": back_forward_runner.get(
            "back_forward_plan_validation_reasons", []
        ),
        "back_forward_run_execution_conditions": back_forward_runner.get("execution_conditions", {}),
        "back_forward_run_per_step_timeout_seconds": back_forward_runner.get("per_step_timeout_seconds", ""),
        "back_forward_run_since_minutes": back_forward_runner.get("since_minutes", ""),
        "back_forward_run_min_closed": back_forward_runner.get("min_closed", ""),
        "back_forward_run_from_date": back_forward_runner.get("from_date", ""),
        "back_forward_run_to_date": back_forward_runner.get("to_date", ""),
        "back_forward_run_forward_mode": back_forward_runner.get("forward_mode", ""),
        "back_forward_run_effective_from_date": back_forward_runner.get("effective_from_date", ""),
        "back_forward_run_effective_to_date": back_forward_runner.get("effective_to_date", ""),
        "back_forward_run_effective_forward_mode": back_forward_runner.get(
            "effective_forward_mode", ""
        ),
        "back_forward_run_sync_expert_parameters_set": back_forward_runner.get(
            "sync_expert_parameters_set", ""
        ),
        "back_forward_run_allow_running_terminal": back_forward_runner.get("allow_running_terminal", ""),
        "back_forward_run_allow_stale_compile": back_forward_runner.get("allow_stale_compile", ""),
        "back_forward_run_allow_invalid_risk_preset": back_forward_runner.get(
            "allow_invalid_risk_preset", ""
        ),
        "back_forward_run_archive_preview_output_json": back_forward_archive_preview_first_json,
        "back_forward_run_archive_preview_output_md": back_forward_archive_preview_first_md,
        "back_forward_run_archive_preview_output_json_by_step": back_forward_archive_preview_json_by_step,
        "back_forward_run_archive_preview_output_md_by_step": back_forward_archive_preview_md_by_step,
        "back_forward_run_archive_preview_execution_ok_by_step": (
            back_forward_archive_preview_execution_ok_by_step
        ),
        "back_forward_run_archive_preview_validation_ok_by_step": (
            back_forward_archive_preview_validation_ok_by_step
        ),
        "back_forward_run_archive_preview_artifact_count_by_step": (
            back_forward_archive_preview_artifact_count_by_step
        ),
        "back_forward_run_execution_window_complete": back_forward_runner.get("execution_window_complete", ""),
        "back_forward_run_total_timeout_seconds": back_forward_runner.get("total_timeout_seconds", ""),
        "back_forward_run_total_timeout_minutes": back_forward_runner.get("total_timeout_minutes", ""),
        "back_forward_run_timeout_start_reference_at": back_forward_runner.get("timeout_start_reference_at", ""),
        "back_forward_run_timeout_deadline_if_started_now": (
            back_forward_runner.get("timeout_deadline_if_started_now", "")
        ),
        "back_forward_run_timeout_deadline_epoch_if_started_now": (
            back_forward_runner.get("timeout_deadline_epoch_if_started_now", "")
        ),
        "back_forward_run_timeout_note": back_forward_runner.get("timeout_note", ""),
        "back_forward_run_timeout_steps": back_forward_runner.get("timeout_steps", []),
        "back_forward_run_blocked_before_steps": back_forward_runner.get("blocked_before_steps", ""),
        "back_forward_run_reason": back_forward_runner.get("reason", ""),
        "back_forward_run_ready_status_ok": back_forward_runner.get("ready_status_ok", ""),
        "back_forward_run_ready_status_reasons": back_forward_runner.get("ready_status_reasons", []),
        "back_forward_run_ready_status_mismatches": back_forward_runner.get("ready_status_mismatches", []),
        "back_forward_run_ready_status_checked_step_keys": (
            back_forward_runner.get("ready_status_checked_step_keys", [])
        ),
        "back_forward_run_ready_status_checked_command_options": (
            back_forward_runner.get("ready_status_checked_command_options", [])
        ),
        "back_forward_run_ready_status_checked_command_flags": (
            back_forward_runner.get("ready_status_checked_command_flags", [])
        ),
        "back_forward_run_ready_status_checked_execution_conditions": (
            back_forward_runner.get("ready_status_checked_execution_conditions", [])
        ),
        "back_forward_run_ready_status_expected_execution_conditions": (
            back_forward_runner.get("ready_status_expected_execution_conditions", {})
        ),
        "back_forward_run_ready_status_status_execution_conditions": (
            back_forward_runner.get("ready_status_status_execution_conditions", {})
        ),
        "back_forward_run_step_count": back_forward_runner.get("step_count", ""),
        "back_forward_run_step_labels": back_forward_runner.get("step_labels", []),
        "back_forward_run_steps": back_forward_runner.get("steps", []),
        "back_forward_run_performance_comparison_available": back_forward_runner.get(
            "performance_comparison_available", ""
        ),
        "back_forward_run_performance_comparison_status": back_forward_runner.get(
            "performance_comparison_status", ""
        ),
        "back_forward_run_performance_comparison_thresholds": back_forward_runner.get(
            "performance_comparison_thresholds", {}
        ),
        "back_forward_run_performance_comparison_rows": back_forward_runner.get(
            "performance_comparison_rows", []
        ),
        "back_forward_execution_ready": back_forward_execution.get("ready"),
        "back_forward_execution_status": back_forward_execution.get("status", ""),
        "back_forward_execution_reasons": back_forward_execution.get("reasons", []),
        "back_forward_execution_execute_hint": back_forward_execution.get("execute_hint", ""),
        "stable_candidate_exists": stable.get("exists"),
        "stable_candidate_tester_ok": stable.get("tester_ok"),
        "stable_candidate_closed": stable.get("closed"),
        "stable_candidate_pf": stable.get("pf"),
        "stable_candidate_avg_price_r": stable.get("avg_price_r"),
        "stable_candidate_recommendation_adoptable": stable.get("recommendation_adoptable"),
        "stable_candidate_recommendation_reasons": stable.get("recommendation_reasons", []),
        "stable_candidate_refit_kind": stable_refit.get("kind", ""),
        "stable_candidate_refit_side": stable_refit.get("side", ""),
        "stable_candidate_refit_driver": stable_refit.get("driver", ""),
        "stable_candidate_refit_config": stable_refit.get("config", ""),
        "stable_candidate_refit_set": stable_refit.get("set", ""),
        "stable_candidate_refit_output_set": stable_refit.get("output_set", ""),
        "stable_candidate_refit_archive_run_id": stable_refit.get("agent_csv_archive_run_id", ""),
        "stable_candidate_refit_reason": stable_refit.get("reason", ""),
        "stable_candidate_refit_completed_kind": stable_refit_completed.get("kind", ""),
        "stable_candidate_refit_completed_side": stable_refit_completed.get("side", ""),
        "stable_candidate_refit_completed_status": stable_refit_completed.get("status", ""),
        "stable_candidate_refit_completed_closed": stable_refit_completed.get("closed", ""),
        "stable_candidate_refit_completed_pf": stable_refit_completed.get("pf", ""),
        "stable_candidate_refit_completed_avg_price_r": stable_refit_completed.get("avg_price_r", ""),
        "stable_candidate_refit_completed_reasons": stable_refit_completed.get("decision_reasons", []),
        "stable_candidate_refit_completed_skip_reason": stable_refit_completed.get("skip_reason", ""),
        "promotion_decision": gate.get("decision", ""),
        "promotion_failed_checks": gate.get("failed", ""),
        "promotion_failed_check_names": gate.get("failed_check_names", []),
        "promotion_mt5_back_forward_run_check": gate_back_forward_check,
        "promotion_mt5_back_forward_run_check_passed": gate_back_forward_check.get("passed", ""),
        "promotion_mt5_back_forward_run_check_value": gate_back_forward_check.get("value", ""),
        "promotion_mt5_back_forward_run_ok_check": gate_back_forward_ok_check,
        "promotion_mt5_back_forward_run_ok_check_passed": gate_back_forward_ok_check.get("passed", ""),
        "promotion_mt5_back_forward_run_performance_check": gate_back_forward_performance_check,
        "promotion_mt5_back_forward_run_performance_check_passed": (
            gate_back_forward_performance_check.get("passed", "")
        ),
        "promotion_mt5_back_forward_run_performance_check_value": (
            gate_back_forward_performance_check.get("value", "")
        ),
    }


def parse_json_stdout(stdout: str) -> dict[str, object]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def manual_collect_output_md_path(output_json: str) -> str:
    return str(Path(output_json).with_suffix(".md"))


def manual_queue_launch_output_md_path(output_json: str) -> str:
    return str(Path(output_json).with_suffix(".md"))


def placeholder_heartbeat_value(field: str) -> object:
    list_tokens = (
        "_actions",
        "_audit",
        "_blockers",
        "_blocking",
        "_checklist",
        "_checks",
        "_entries",
        "_executions",
        "_flags",
        "_keys",
        "_mismatches",
        "_options",
        "_outputs",
        "_planned",
        "_reasons",
        "_skipped",
        "_steps",
    )
    if any(token in field for token in list_tokens):
        return []
    return ""


def ensure_required_heartbeat_fields(payload: dict[str, object]) -> dict[str, object]:
    for field in HEARTBEAT_SNAPSHOT_REQUIRED_KEYS:
        payload.setdefault(field, placeholder_heartbeat_value(field))
    return payload


def write_heartbeat(path: str | Path, heartbeat: dict[str, object]) -> None:
    if not str(path):
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(heartbeat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def heartbeat_runtime_status(*, status_refresh_phase: str, returncode: int | str) -> str:
    if status_refresh_phase == "pre_status_refresh":
        return "refreshing"
    if returncode in (0, 2, "0", "2"):
        return "ok"
    return "error"


def base_heartbeat(
    args: argparse.Namespace,
    *,
    run_index: int,
    started_epoch: float,
    started_at: str,
    finished_epoch: float | None = None,
    returncode: int | str = "",
    stdout_tail: str = "",
    stderr_tail: str = "",
    status_refresh_phase: str = "",
) -> dict[str, object]:
    effective_finished_epoch = time.time() if finished_epoch is None else finished_epoch
    runtime_status = heartbeat_runtime_status(
        status_refresh_phase=status_refresh_phase,
        returncode=returncode,
    )
    finished_at = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    heartbeat: dict[str, object] = {
        "schema_version": HEARTBEAT_SCHEMA_VERSION,
        "implementation_version": HEARTBEAT_IMPLEMENTATION_VERSION,
        "ok": runtime_status != "error",
        "status": runtime_status,
        "snapshot_required_keys": list(HEARTBEAT_SNAPSHOT_REQUIRED_KEYS),
        "generated_at": finished_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "started_epoch": round(started_epoch, 3),
        "finished_epoch": round(effective_finished_epoch, 3),
        "elapsed_seconds": round(effective_finished_epoch - started_epoch, 3),
        "returncode": returncode,
        "stdout_tail": stdout_tail[-2000:],
        "stderr_tail": stderr_tail[-2000:],
        "output_json": args.output_json,
        "output_md": args.output_md,
        "next_run_in_seconds": args.interval_seconds,
        "watcher_pid": os.getpid(),
        "pid_file": args.pid_file,
        "pid_file_enabled": bool(args.pid_file),
        "pid_file_written": bool(args.pid_file) and not args.skip_pid_file_write,
        "heartbeat": args.heartbeat,
        "heartbeat_enabled": bool(args.heartbeat),
        "run_index": run_index,
        "max_runs": args.max_runs,
        "continuous": args.max_runs == 0,
        "status_refresh_phase": status_refresh_phase,
    }
    return heartbeat


def write_pre_status_heartbeat(
    args: argparse.Namespace,
    *,
    run_index: int,
    started_epoch: float,
    started_at: str,
    manual_collect_refresh: dict[str, object],
    manual_queue_launch_refresh: dict[str, object],
    manual_collect_with_optimization_refresh: dict[str, object],
    manual_queue_launch_with_optimization_refresh: dict[str, object],
) -> None:
    heartbeat = base_heartbeat(
        args,
        run_index=run_index,
        started_epoch=started_epoch,
        started_at=started_at,
        status_refresh_phase="pre_status_refresh",
    )
    heartbeat.update(manual_collect_refresh)
    heartbeat.update(manual_queue_launch_refresh)
    heartbeat.update(manual_collect_with_optimization_refresh)
    heartbeat.update(manual_queue_launch_with_optimization_refresh)
    heartbeat.update(load_status_snapshot(args.output_json))
    write_heartbeat(args.heartbeat, ensure_required_heartbeat_fields(heartbeat))


def refresh_manual_collect_queue_once(
    args: argparse.Namespace,
    *,
    queue_path: str,
    output_json: str,
    prefix: str,
) -> dict[str, object]:
    if args.skip_manual_collect_refresh:
        return {
            f"{prefix}_enabled": False,
            f"{prefix}_command": [],
            f"{prefix}_returncode": "",
            f"{prefix}_completed": False,
            f"{prefix}_status": "skipped",
            f"{prefix}_queue_refresh_status": "",
            f"{prefix}_queue_refresh_ok": "",
            f"{prefix}_queue_refresh_source_count": "",
            f"{prefix}_selected_count": "",
            f"{prefix}_waiting_count": "",
            f"{prefix}_invalid_count": "",
            f"{prefix}_output_json": output_json,
            f"{prefix}_output_md": manual_collect_output_md_path(output_json),
            f"{prefix}_stdout_tail": "",
            f"{prefix}_stderr_tail": "",
        }
    output_md = manual_collect_output_md_path(output_json)
    command = [
        sys.executable,
        "analysis/mt5_manual_collect.py",
        "--queue",
        queue_path,
        "--output-json",
        output_json,
        "--output-md",
        output_md,
    ]
    result = subprocess.run(command, text=True, capture_output=True)
    summary = parse_json_stdout(result.stdout or "")
    return {
        f"{prefix}_enabled": True,
        f"{prefix}_command": command,
        f"{prefix}_returncode": result.returncode,
        f"{prefix}_completed": result.returncode in (0, 2),
        f"{prefix}_status": summary.get("status", ""),
        f"{prefix}_queue_refresh_status": summary.get("queue_refresh_status", ""),
        f"{prefix}_queue_refresh_ok": summary.get("queue_refresh_ok", ""),
        f"{prefix}_queue_refresh_source_count": summary.get("queue_refresh_source_count", ""),
        f"{prefix}_selected_count": summary.get("selected_count", ""),
        f"{prefix}_waiting_count": summary.get("waiting_count", ""),
        f"{prefix}_invalid_count": summary.get("invalid_count", ""),
        f"{prefix}_output_json": output_json,
        f"{prefix}_output_md": output_md,
        f"{prefix}_stdout_tail": (result.stdout or "")[-2000:],
        f"{prefix}_stderr_tail": (result.stderr or "")[-2000:],
    }


def refresh_manual_collect_once(args: argparse.Namespace) -> dict[str, object]:
    return refresh_manual_collect_queue_once(
        args,
        queue_path=args.manual_test_queue,
        output_json=args.manual_collect_run,
        prefix="manual_collect_refresh",
    )


def refresh_manual_collect_with_optimization_once(args: argparse.Namespace) -> dict[str, object]:
    return refresh_manual_collect_queue_once(
        args,
        queue_path=args.manual_test_queue_with_optimization,
        output_json=args.manual_collect_with_optimization,
        prefix="manual_collect_with_optimization_refresh",
    )


def refresh_manual_queue_launch_queue_once(
    args: argparse.Namespace,
    *,
    queue_path: str,
    output_json: str,
    prefix: str,
) -> dict[str, object]:
    output_md = manual_queue_launch_output_md_path(output_json)
    existing_launch: dict[str, object] = {}
    existing_launch_path = Path(output_json)
    if existing_launch_path.exists():
        try:
            loaded = json.loads(existing_launch_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            loaded = {}
        if isinstance(loaded, dict):
            existing_launch = loaded
    detached = existing_launch.get("detached") is True
    if args.skip_manual_queue_launch_refresh:
        return {
            f"{prefix}_enabled": False,
            f"{prefix}_command": [],
            f"{prefix}_returncode": "",
            f"{prefix}_completed": False,
            f"{prefix}_status": "skipped",
            f"{prefix}_queue_refresh_status": "",
            f"{prefix}_queue_refresh_ok": "",
            f"{prefix}_queue_refresh_source_count": "",
            f"{prefix}_queue_entry_count": "",
            f"{prefix}_queue_total_entry_count": "",
            f"{prefix}_queue_step_count": "",
            f"{prefix}_queue_waiting_count": "",
            f"{prefix}_selected": "",
            f"{prefix}_selected_queue_id": "",
            f"{prefix}_selected_step_label": "",
            f"{prefix}_detached": detached,
            f"{prefix}_blocked": "",
            f"{prefix}_blocked_reasons": [],
            f"{prefix}_output_json": output_json,
            f"{prefix}_output_md": output_md,
            f"{prefix}_stdout_tail": "",
            f"{prefix}_stderr_tail": "",
        }
    command = [
        sys.executable,
        "analysis/mt5_manual_queue_launch.py",
        "--queue",
        queue_path,
        "--refresh-queue",
        "--output-json",
        output_json,
        "--output-md",
        output_md,
    ]
    if detached:
        command.append("--detached")
    result = subprocess.run(command, text=True, capture_output=True)
    summary = parse_json_stdout(result.stdout or "")
    next_step = summary.get("queue_operator_handoff_next_mt5_step")
    if not isinstance(next_step, dict):
        next_step = {}
    return {
        f"{prefix}_enabled": True,
        f"{prefix}_command": command,
        f"{prefix}_returncode": result.returncode,
        f"{prefix}_completed": result.returncode in (0, 2),
        f"{prefix}_status": summary.get("status", ""),
        f"{prefix}_queue_refresh_status": summary.get("queue_refresh_status", ""),
        f"{prefix}_queue_refresh_ok": summary.get("queue_refresh_ok", ""),
        f"{prefix}_queue_refresh_source_count": summary.get("queue_refresh_source_count", ""),
        f"{prefix}_queue_entry_count": summary.get("queue_entry_count", ""),
        f"{prefix}_queue_total_entry_count": summary.get("queue_total_entry_count", ""),
        f"{prefix}_queue_step_count": summary.get("queue_step_count", ""),
        f"{prefix}_queue_waiting_count": summary.get("queue_waiting_count", ""),
        f"{prefix}_selected": summary.get("selected", ""),
        f"{prefix}_selected_queue_id": next_step.get("queue_id", ""),
        f"{prefix}_selected_step_label": next_step.get("step_label", ""),
        f"{prefix}_detached": summary.get("detached", detached),
        f"{prefix}_blocked": summary.get("blocked", ""),
        f"{prefix}_blocked_reasons": summary.get("blocked_reasons", []),
        f"{prefix}_output_json": output_json,
        f"{prefix}_output_md": output_md,
        f"{prefix}_stdout_tail": (result.stdout or "")[-2000:],
        f"{prefix}_stderr_tail": (result.stderr or "")[-2000:],
    }


def refresh_manual_queue_launch_once(args: argparse.Namespace) -> dict[str, object]:
    return refresh_manual_queue_launch_queue_once(
        args,
        queue_path=args.manual_test_queue,
        output_json=args.manual_queue_launch,
        prefix="manual_queue_launch_refresh",
    )


def refresh_manual_queue_launch_with_optimization_once(args: argparse.Namespace) -> dict[str, object]:
    return refresh_manual_queue_launch_queue_once(
        args,
        queue_path=args.manual_test_queue_with_optimization,
        output_json=args.manual_queue_launch_with_optimization,
        prefix="manual_queue_launch_with_optimization_refresh",
    )


def refresh_status_once(args: argparse.Namespace, *, run_index: int = 1) -> dict[str, object]:
    started_epoch = time.time()
    started_at = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    manual_collect_refresh = refresh_manual_collect_once(args)
    manual_queue_launch_refresh = refresh_manual_queue_launch_once(args)
    manual_collect_with_optimization_refresh = refresh_manual_collect_with_optimization_once(args)
    manual_queue_launch_with_optimization_refresh = refresh_manual_queue_launch_with_optimization_once(args)
    write_pre_status_heartbeat(
        args,
        run_index=run_index,
        started_epoch=started_epoch,
        started_at=started_at,
        manual_collect_refresh=manual_collect_refresh,
        manual_queue_launch_refresh=manual_queue_launch_refresh,
        manual_collect_with_optimization_refresh=manual_collect_with_optimization_refresh,
        manual_queue_launch_with_optimization_refresh=manual_queue_launch_with_optimization_refresh,
    )
    command = [
        sys.executable,
        "analysis/mt5_tester_status.py",
        "--tester-run",
        args.tester_run,
        "--promotion-gate",
        args.promotion_gate,
        "--compile-status",
        args.compile_status,
        "--optimization-report",
        args.optimization_report,
        "--next-action-run",
        args.next_action_run,
        "--back-forward-run",
        args.back_forward_run,
        "--manual-test-queue",
        args.manual_test_queue,
        "--manual-queue-launch",
        args.manual_queue_launch,
        "--manual-collect-run",
        args.manual_collect_run,
        "--manual-test-queue-with-optimization",
        args.manual_test_queue_with_optimization,
        "--manual-queue-launch-with-optimization",
        args.manual_queue_launch_with_optimization,
        "--manual-collect-with-optimization",
        args.manual_collect_with_optimization,
        "--manual-operator-packet-with-optimization",
        args.manual_operator_packet_with_optimization,
        "--stable-candidate-report",
        args.stable_candidate_report,
        "--stable-candidate-recommendation",
        args.stable_candidate_recommendation,
        "--stable-candidate-tester-run",
        args.stable_candidate_tester_run,
        "--bridge-recovery-plan",
        args.bridge_recovery_plan,
        "--status-watch-heartbeat",
        args.heartbeat,
        "--output-json",
        args.output_json,
        "--output-md",
        args.output_md,
        "--max-artifact-age-seconds",
        str(args.max_artifact_age_seconds),
    ]
    result = subprocess.run(command, text=True, capture_output=True)
    finished_epoch = time.time()
    heartbeat = base_heartbeat(
        args,
        run_index=run_index,
        started_epoch=started_epoch,
        started_at=started_at,
        finished_epoch=finished_epoch,
        returncode=result.returncode,
        stdout_tail=result.stdout,
        stderr_tail=result.stderr,
        status_refresh_phase="post_status_refresh",
    )
    heartbeat.update(manual_collect_refresh)
    heartbeat.update(manual_queue_launch_refresh)
    heartbeat.update(manual_collect_with_optimization_refresh)
    heartbeat.update(manual_queue_launch_with_optimization_refresh)
    heartbeat.update(load_status_snapshot(args.output_json))
    write_heartbeat(args.heartbeat, ensure_required_heartbeat_fields(heartbeat))

    sync_result = subprocess.run(command, text=True, capture_output=True)
    sync_finished_epoch = time.time()
    heartbeat = base_heartbeat(
        args,
        run_index=run_index,
        started_epoch=started_epoch,
        started_at=started_at,
        finished_epoch=sync_finished_epoch,
        returncode=sync_result.returncode,
        stdout_tail=sync_result.stdout,
        stderr_tail=sync_result.stderr,
        status_refresh_phase="synced_status_refresh",
    )
    heartbeat["initial_status_returncode"] = result.returncode
    heartbeat["initial_status_stdout_tail"] = result.stdout[-2000:]
    heartbeat["initial_status_stderr_tail"] = result.stderr[-2000:]
    heartbeat.update(manual_collect_refresh)
    heartbeat.update(manual_queue_launch_refresh)
    heartbeat.update(manual_collect_with_optimization_refresh)
    heartbeat.update(manual_queue_launch_with_optimization_refresh)
    heartbeat.update(load_status_snapshot(args.output_json))
    write_heartbeat(args.heartbeat, ensure_required_heartbeat_fields(heartbeat))
    return heartbeat


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.interval_seconds < 5:
        raise SystemExit("--interval-seconds must be >= 5")

    continuous = args.max_runs == 0
    args.heartbeat = args.heartbeat or (DEFAULT_HEARTBEAT if continuous else "")
    args.pid_file = args.pid_file or (DEFAULT_PID_FILE if continuous else "")
    pid_file_written = bool(args.pid_file) and not args.skip_pid_file_write

    if pid_file_written:
        Path(args.pid_file).parent.mkdir(parents=True, exist_ok=True)
        Path(args.pid_file).write_text(str(os.getpid()) + "\n", encoding="utf-8")

    runs = 0
    while True:
        refresh_status_once(args, run_index=runs + 1)
        runs += 1
        if args.max_runs > 0 and runs >= args.max_runs:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
