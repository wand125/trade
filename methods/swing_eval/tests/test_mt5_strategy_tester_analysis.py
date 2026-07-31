import json
import tempfile
import unittest
from pathlib import Path

from analysis.mt5_strategy_tester_analysis import (
    OptimizationReportSpec,
    back_forward_decision_summary,
    build_strategy_tester_analysis,
    format_markdown,
    summarize_optimization_report,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def optimization_payload(
    *,
    closed: int = 120,
    pf: float = 1.3,
    avg_r: float = 0.1,
    stable: int = 1,
    source_time: dict | None = None,
    files: list[dict] | None = None,
) -> dict:
    summary = {
        "generated_at": "2026.07.16 22:30",
        "overall": {
            "closed": closed,
            "wins": 40,
            "losses": 80,
            "win_rate": 0.3333,
            "pf": pf,
            "avg_price_r": avg_r,
            "net_profit": 12.34,
        },
        "tester_xml": {
            "back": {"rows": 10},
            "forward": {
                "rows": 10,
                "positive_forward_positive_back": stable,
                "positive_forward_negative_back": 0,
                "stable_top": [
                    {
                        "Pass": 7,
                        "Forward Result": 22.0,
                        "Back Result": 11.0,
                        "Profit Factor": 1.4,
                        "Trades": 42,
                    }
                ]
                if stable
                else [],
            },
        },
    }
    if source_time is not None:
        summary["source_time_diagnostics"] = source_time
        summary["source_time_coverage"] = {
            "close_rows": closed,
            "close_rows_with_server_time": closed,
            "close_rows_without_server_time": 0,
            "first_server_time": source_time.get("actual_first_server_time", ""),
            "last_server_time": source_time.get("actual_last_server_time", ""),
        }
    if files is not None:
        summary["files"] = files
    return {
        "ok": True,
        "summary": summary,
    }


class Mt5StrategyTesterAnalysisTests(unittest.TestCase):
    def test_summarize_optimization_report_classifies_candidate_and_aggregate_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            candidate = root / "runtime" / "candidate.json"
            aggregate = root / "runtime" / "aggregate.json"
            rejected = root / "runtime" / "rejected.json"
            mismatch = root / "runtime" / "mismatch.json"
            write_json(candidate, optimization_payload(stable=2))
            write_json(aggregate, optimization_payload(stable=0))
            write_json(rejected, optimization_payload(pf=0.95, avg_r=-0.02, stable=3))
            write_json(
                mismatch,
                optimization_payload(
                    stable=3,
                    source_time={
                        "expected_from_date": "2025.01.01",
                        "expected_to_date": "2025.12.31",
                        "actual_first_server_time": "2026.07.07 00:05:00",
                        "actual_last_server_time": "2026.07.07 00:10:00",
                        "actual_span_days": 0.0035,
                        "matches_expected_range": False,
                        "warnings": ["last close is after expected ToDate"],
                    },
                ),
            )

            self.assertEqual(
                summarize_optimization_report(
                    root,
                    OptimizationReportSpec("candidate", "SELL", "annual", "runtime/candidate.json"),
                )["status"],
                "candidate",
            )
            self.assertEqual(
                summarize_optimization_report(
                    root,
                    OptimizationReportSpec("aggregate", "BUY", "annual", "runtime/aggregate.json"),
                )["status"],
                "aggregate_only",
            )
            self.assertEqual(
                summarize_optimization_report(
                    root,
                    OptimizationReportSpec("rejected", "BUY", "annual", "runtime/rejected.json"),
                )["status"],
                "rejected",
            )
            mismatch_summary = summarize_optimization_report(
                root,
                OptimizationReportSpec("mismatch", "SELL", "annual", "runtime/mismatch.json"),
            )
            self.assertEqual(mismatch_summary["status"], "source_time_mismatch")
            self.assertEqual(mismatch_summary["source_time"]["status"], "mismatch")
            self.assertEqual(mismatch_summary["source_time"]["expected_from_date"], "2025.01.01")

    def test_source_files_stale_can_be_validated_from_agent_csv_archive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            agent = "Agent-127.0.0.1-3006"
            live_csv = root / "runtime" / "live" / agent / "MQL5" / "Files" / "swing_evaluation_trades.csv"
            archive_csv = (
                root
                / "runtime"
                / "mt5_agent_csv_archive"
                / "run_20260713_sell"
                / agent
                / "MQL5"
                / "Files"
                / "swing_evaluation_trades.csv"
            )
            archived_rows = (
                "event,server_time\n"
                "signal,\n"
                "close,2025.01.01 01:00:00\n"
                "close,2025.01.01 01:05:00\n"
            )
            archive_csv.parent.mkdir(parents=True, exist_ok=True)
            archive_csv.write_text(archived_rows, encoding="utf-8")
            live_csv.parent.mkdir(parents=True, exist_ok=True)
            live_csv.write_text("event,server_time\nclose,2026.01.01 00:00:00\n", encoding="utf-8")

            source_time = {
                "expected_from_date": "2025.01.01",
                "expected_to_date": "2025.12.31",
                "actual_first_server_time": "2025.01.01 01:00:00",
                "actual_last_server_time": "2025.01.01 01:05:00",
                "actual_span_days": 0.0035,
                "matches_expected_range": True,
                "warnings": [],
            }
            write_json(
                root / "runtime" / "sell_archived_source.json",
                optimization_payload(
                    closed=2,
                    stable=2,
                    source_time=source_time,
                    files=[
                        {
                            "path": str(live_csv.relative_to(root)),
                            "agent": agent,
                            "mtime": "2025.01.01 00:00",
                            "size": archive_csv.stat().st_size,
                            "rows": 3,
                            "closed": 2,
                            "source_time": {
                                "close_rows": 2,
                                "close_rows_with_server_time": 2,
                                "close_rows_without_server_time": 0,
                                "first_server_time": "2025.01.01 01:00:00",
                                "last_server_time": "2025.01.01 01:05:00",
                            },
                        }
                    ],
                ),
            )
            write_json(
                root / "runtime" / "buy_ok.json",
                optimization_payload(stable=2, source_time=source_time),
            )
            write_json(root / "runtime" / "latest_promotion_gate.json", {"ok": True, "decision": "ready"})
            write_json(
                root / "runtime" / "latest_mt5_back_forward_run.json",
                {"ok": True, "evidence_state": "executed_consistent"},
            )
            write_json(root / "runtime" / "latest_spec_coverage.json", {"ok": True, "not_complete_reasons": []})

            sell_summary = summarize_optimization_report(
                root,
                OptimizationReportSpec("sell_archived_source", "SELL", "annual", "runtime/sell_archived_source.json"),
            )
            self.assertEqual(sell_summary["status"], "candidate")
            self.assertEqual(sell_summary["source_time"]["status"], "ok")
            self.assertEqual(sell_summary["source_files"]["status"], "archived")
            self.assertEqual(sell_summary["source_files"]["archived"], 1)
            self.assertEqual(sell_summary["source_files"]["stale"], 0)
            self.assertEqual(sell_summary["source_files"]["original_stale"], 1)
            self.assertIn("run_20260713_sell", sell_summary["source_files"]["archive_examples"][0]["archive"])

            payload = build_strategy_tester_analysis(
                root,
                report_specs=[
                    OptimizationReportSpec(
                        "sell_archived_source",
                        "SELL",
                        "annual",
                        "runtime/sell_archived_source.json",
                    ),
                    OptimizationReportSpec("buy_ok", "BUY", "annual", "runtime/buy_ok.json"),
                ],
            )
            markdown = format_markdown(payload)

            self.assertEqual(payload["adoption"]["status"], "adoptable")
            self.assertEqual(payload["back_forward_decision"]["status"], "passed")
            self.assertTrue(payload["back_forward_decision"]["adoptable"])
            self.assertNotIn(
                "candidate_source_time_files_stale:sell_archived_source",
                payload["adoption"]["blockers"],
            )
            self.assertEqual(payload["source_time_refresh_plan"]["status"], "ok")
            self.assertNotIn("Optimization Source File Issues", markdown)

    def test_source_files_stale_blocks_adoption_until_report_is_refreshed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_csv = root / "runtime" / "agent-current.csv"
            live_csv.parent.mkdir(parents=True, exist_ok=True)
            live_csv.write_text("current optimized csv rows\n", encoding="utf-8")
            write_json(
                root / "runtime" / "sell_stale_source.json",
                optimization_payload(
                    stable=2,
                    files=[
                        {
                            "path": "runtime/agent-current.csv",
                            "size": 1,
                            "mtime": "2025.01.01 00:00:00",
                        }
                    ],
                ),
            )
            write_json(
                root / "runtime" / "buy_ok.json",
                optimization_payload(
                    stable=2,
                    source_time={
                        "expected_from_date": "2025.01.01",
                        "expected_to_date": "2025.12.31",
                        "actual_first_server_time": "2025.01.01 01:00:00",
                        "actual_last_server_time": "2025.12.31 22:00:00",
                        "actual_span_days": 364.9,
                        "matches_expected_range": True,
                        "warnings": [],
                    },
                    files=[
                        {
                            "path": "runtime/agent-current.csv",
                            "size": 1,
                            "mtime": "2025.01.01 00:00:00",
                        }
                    ],
                ),
            )
            write_json(
                root / "runtime" / "latest_promotion_gate.json",
                {"ok": True, "decision": "ready"},
            )
            write_json(
                root / "runtime" / "latest_mt5_back_forward_run.json",
                {"ok": True, "evidence_state": "executed_consistent"},
            )
            write_json(
                root / "runtime" / "latest_spec_coverage.json",
                {"ok": True, "not_complete_reasons": []},
            )

            sell_summary = summarize_optimization_report(
                root,
                OptimizationReportSpec("sell_stale_source", "SELL", "annual", "runtime/sell_stale_source.json"),
            )
            self.assertEqual(sell_summary["status"], "candidate")
            self.assertEqual(sell_summary["source_time"]["status"], "source_files_stale")
            self.assertEqual(sell_summary["source_files"]["status"], "stale")
            self.assertEqual(sell_summary["source_files"]["stale"], 1)
            buy_summary = summarize_optimization_report(
                root,
                OptimizationReportSpec("buy_ok", "BUY", "annual", "runtime/buy_ok.json"),
            )
            self.assertEqual(buy_summary["status"], "candidate")
            self.assertEqual(buy_summary["source_time"]["status"], "ok")
            self.assertEqual(buy_summary["source_files"]["status"], "stale")

            payload = build_strategy_tester_analysis(
                root,
                report_specs=[
                    OptimizationReportSpec("sell_stale_source", "SELL", "annual", "runtime/sell_stale_source.json"),
                    OptimizationReportSpec("buy_ok", "BUY", "annual", "runtime/buy_ok.json"),
                ],
            )
            markdown = format_markdown(payload)

            self.assertEqual(payload["adoption"]["status"], "not_ready")
            self.assertIn(
                "candidate_source_time_files_stale:sell_stale_source",
                payload["adoption"]["blockers"],
            )
            self.assertIn(
                "candidate_source_time_files_stale:buy_ok",
                payload["adoption"]["blockers"],
            )
            self.assertEqual(payload["source_time_refresh_plan"]["status"], "needs_refresh")
            self.assertEqual(payload["source_time_refresh_plan"]["issue_count"], 2)
            self.assertEqual(
                payload["source_time_refresh_plan"]["candidate_issue_labels"],
                ["sell_stale_source", "buy_ok"],
            )
            self.assertIn(
                "--include-optimization-configs",
                payload["source_time_refresh_plan"]["refresh_queue_command_text"],
            )
            self.assertIn("source_files_stale", markdown)
            self.assertIn("## Optimization Source File Issues", markdown)
            self.assertIn("## Source-Time Refresh Plan", markdown)
            self.assertIn("Refresh queue command", markdown)
            self.assertIn("runtime/agent-current.csv", markdown)
            self.assertIn("size 1->", markdown)
            self.assertIn("mtime 2025.01.01 00:00->", markdown)

    def test_source_time_refresh_plan_links_candidate_to_manual_queue_step(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_csv = root / "runtime" / "agent-current.csv"
            live_csv.parent.mkdir(parents=True, exist_ok=True)
            live_csv.write_text("current optimized csv rows\n", encoding="utf-8")
            write_json(
                root / "runtime" / "sell_hour12.json",
                optimization_payload(
                    stable=2,
                    files=[
                        {
                            "path": "runtime/agent-current.csv",
                            "size": 1,
                            "mtime": "2025.01.01 00:00:00",
                        }
                    ],
                ),
            )
            write_json(
                root / "runtime" / "latest_mt5_manual_test_queue_with_optimization.json",
                {
                    "ok": True,
                    "status": "waiting_for_manual_strategy_tester_results",
                    "next_action": "run_manual_strategy_tester_steps_and_wait_for_reports",
                    "operation_cards": [
                        {
                            "order": 3,
                            "queue_id": "static_sell_hour12_m30m15_2025",
                            "step_label": "sell_hour12_m30m15_2025",
                            "dates": "2025.01.01 -> 2025.12.31",
                            "forward": "1/4",
                            "optimization_label": "Fast genetic algorithm",
                            "inputs": "Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set",
                            "report": "Tester\\Swing_Evaluation_Trader_sell_hour12_m30m15_validation_2025",
                            "collect_command_text": (
                                "python3 methods/swing_eval/analysis/mt5_tester_run.py "
                                "--config methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_validation.ini "
                                "--collect-only --from-date 2025.01.01 --to-date 2025.12.31 --forward-mode 3"
                            ),
                        }
                    ],
                    "execution_checklist": [
                        {
                            "order": 3,
                            "queue_id": "static_sell_hour12_m30m15_2025",
                            "step_label": "sell_hour12_m30m15_2025",
                            "dates": "2025.01.01 -> 2025.12.31",
                            "forward": "1/4",
                            "optimization_label": "Fast genetic algorithm",
                            "inputs": "Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set",
                            "report": "Tester\\Swing_Evaluation_Trader_sell_hour12_m30m15_validation_2025",
                            "launch_command_kind": "runner_execute",
                            "launch_command_text": (
                                "python3 methods/swing_eval/analysis/mt5_tester_run.py "
                                "--config methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_validation.ini "
                                "--from-date 2025.01.01 --to-date 2025.12.31 --forward-mode 3"
                            ),
                        }
                    ],
                },
            )

            payload = build_strategy_tester_analysis(
                root,
                report_specs=[
                    OptimizationReportSpec(
                        "sell_hour12_m30m15_2025",
                        "SELL",
                        "annual",
                        "runtime/sell_hour12.json",
                    ),
                ],
            )
            plan = payload["source_time_refresh_plan"]
            entry = plan["entries"][0]
            markdown = format_markdown(payload)

            self.assertEqual(plan["status"], "needs_refresh")
            self.assertEqual(plan["candidate_issue_labels"], ["sell_hour12_m30m15_2025"])
            self.assertIn(
                "--include-static-candidate-label sell_hour12_m30m15_2025",
                plan["refresh_queue_command_text"],
            )
            self.assertEqual(entry["queue_id"], "static_sell_hour12_m30m15_2025")
            self.assertEqual(entry["step_label"], "sell_hour12_m30m15_2025")
            self.assertEqual(entry["launch_command_kind"], "runner_execute")
            self.assertIn("--collect-only --from-date 2025.01.01", entry["collect_command_text"])
            self.assertIn("static_sell_hour12_m30m15_2025/sell_hour12_m30m15_2025", markdown)

    def test_build_report_marks_plan_only_back_forward_as_not_ready(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_json(
                root / "runtime" / "latest_promotion_gate.json",
                {
                    "ok": True,
                    "generated_at": "2026.07.16 22:30",
                    "decision": "not_ready",
                    "failed_check_names": ["mt5_back_forward_run"],
                },
            )
            write_json(
                root / "runtime" / "latest_spec_coverage.json",
                {
                    "ok": True,
                    "generated_at": "2026.07.16 22:31",
                    "goal_completion_proven": False,
                    "not_complete_reason_count": 2,
                    "not_complete_reasons": [
                        "promotion_gate_not_ready:not_ready",
                        "mt5_back_forward_not_executed:plan_only",
                    ],
                    "next_actions": [
                        {
                            "id": "run_mt5_manual_test_queue",
                            "priority": 29,
                            "manual_steps": [
                                "Open runtime/latest_mt5_manual_test_queue.md and run MT5 Strategy Tester entries in order.",
                                "Bridge Recovery is not ready, but standalone Strategy Tester runs are allowed.",
                            ],
                        },
                        {
                            "id": "rerun_promotion_gate_after_evidence",
                            "priority": 90,
                            "manual_steps": [],
                            "next_action": "Rerun promotion gate after MT5 evidence is collected.",
                        },
                    ],
                },
            )
            write_json(
                root / "runtime" / "latest_mt5_back_forward_run.json",
                {
                    "ok": True,
                    "generated_at": "2026.07.16 22:32",
                    "mode": "both",
                    "dry_run": True,
                    "evidence_state": "plan_only",
                    "performance_comparison": {"available": False, "status": "missing_backtest_or_forward_report"},
                    "manual_strategy_tester": {
                        "available": True,
                        "manual_run_start_after": "2026.07.16 22:32",
                        "recommended_collect_only_command_text": (
                            "python3 methods/swing_eval/analysis/mt5_back_forward_run.py --mode both --collect-only"
                        ),
                    },
                    "manual_collect_readiness": {
                        "ready": False,
                        "status": "waiting_report",
                        "blocking_reasons": ["backtest:waiting_report"],
                    },
                },
            )
            write_json(
                root / "runtime" / "latest_mt5_tester_status.json",
                {
                    "generated_at": "2026.07.16 22:33",
                    "mt5_operator_handoff": {
                        "state": "run_next_mt5_strategy_tester_step",
                        "recommended_path": "manual_strategy_tester",
                        "terminal_running": True,
                        "next_mt5_step": {
                            "queue_id": "back_forward",
                            "step_label": "backtest",
                            "symbol": "XAUUSD-m",
                            "period": "M1",
                            "dates": "2026.06.30 -> 2026.07.08",
                            "forward": "Disabled",
                            "inputs": "Swing_Evaluation_Trader_backtest.set",
                            "report": "Tester\\Swing_Evaluation_Trader_backtest",
                        },
                        "bridge_required_for_standalone_tester": False,
                        "bridge_note": "Bridge Recovery is not required for standalone tester.",
                        "manual_collect_execute_and_refresh_analysis_command_text": (
                            "python3 methods/swing_eval/analysis/mt5_manual_collect.py --execute "
                            "--refresh-strategy-tester-analysis"
                        ),
                    },
                },
            )
            write_json(
                root / "runtime" / "latest_mt5_manual_test_queue.json",
                {
                    "ok": True,
                    "generated_at": "2026.07.16 22:34",
                    "status": "waiting_for_manual_strategy_tester_results",
                    "next_action": "run_manual_strategy_tester_steps_and_wait_for_reports",
                    "entry_count": 2,
                    "total_entry_count": 2,
                    "step_count": 2,
                    "ready_to_collect_count": 0,
                    "waiting_count": 2,
                    "step_report_ready_count": 0,
                    "step_waiting_report_count": 2,
                    "step_launch_needed_count": 2,
                    "next_launch_step": {
                        "queue_id": "back_forward",
                        "step_label": "backtest",
                        "symbol": "XAUUSD-m",
                        "period": "M1",
                        "dates": "2026.06.30 -> 2026.07.08",
                        "forward": "Disabled",
                        "inputs": "Swing_Evaluation_Trader_backtest.set",
                        "report": "Tester\\Swing_Evaluation_Trader_backtest",
                    },
                    "operator_handoff": {
                        "state": "run_next_mt5_strategy_tester_step",
                        "collect_ready": False,
                        "ready_entry_ids": [],
                        "waiting_entry_ids": ["back_forward"],
                        "dry_run_command_text": (
                            "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                            "--queue runtime/latest_mt5_manual_test_queue.json"
                        ),
                        "execute_command_text": (
                            "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                            "--queue runtime/latest_mt5_manual_test_queue.json --execute"
                        ),
                        "execute_and_refresh_analysis_command_text": (
                            "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                            "--queue runtime/latest_mt5_manual_test_queue.json --execute "
                            "--refresh-strategy-tester-analysis"
                        ),
                    },
                    "operation_cards": [
                        {
                            "order": 1,
                            "is_next": True,
                            "action": "run_in_mt5",
                            "purpose": "Backtest",
                            "queue_id": "back_forward",
                            "step_label": "backtest",
                            "forward": "Disabled",
                            "optimization": "0",
                            "optimization_label": "Disabled",
                            "inputs": "Swing_Evaluation_Trader_backtest.set",
                            "report": "Tester\\Swing_Evaluation_Trader_backtest",
                            "collect_status": "waiting_for_reports",
                        },
                        {
                            "order": 2,
                            "is_next": False,
                            "action": "run_in_mt5",
                            "purpose": "Forward Test",
                            "queue_id": "back_forward",
                            "step_label": "forward",
                            "forward": "1/4",
                            "optimization": "0",
                            "optimization_label": "Disabled",
                            "inputs": "Swing_Evaluation_Trader_forward_test.set",
                            "report": "Tester\\Swing_Evaluation_Trader_forward_test",
                            "collect_status": "waiting_for_reports",
                        },
                    ],
                    "execution_checklist": [
                        {
                            "order": 1,
                            "queue_id": "back_forward",
                            "step_label": "backtest",
                            "symbol": "XAUUSD-m",
                            "period": "M1",
                            "dates": "2026.06.30 -> 2026.07.08",
                            "forward": "Disabled",
                            "optimization": "0",
                            "optimization_label": "Disabled",
                            "inputs": "Swing_Evaluation_Trader_backtest.set",
                            "report": "Tester\\Swing_Evaluation_Trader_backtest",
                            "step_report_status": "waiting_report",
                        },
                        {
                            "order": 2,
                            "queue_id": "back_forward",
                            "step_label": "forward",
                            "symbol": "XAUUSD-m",
                            "period": "M1",
                            "dates": "2026.06.30 -> 2026.07.08",
                            "forward": "1/4",
                            "optimization": "0",
                            "optimization_label": "Disabled",
                            "inputs": "Swing_Evaluation_Trader_forward_test.set",
                            "report": "Tester\\Swing_Evaluation_Trader_forward_test",
                            "step_report_status": "waiting_report",
                        },
                    ],
                },
            )
            write_json(
                root / "runtime" / "latest_mt5_manual_test_queue_with_optimization.json",
                {
                    "ok": True,
                    "generated_at": "2026.07.16 22:35",
                    "status": "waiting_for_manual_strategy_tester_results",
                    "next_action": "run_manual_strategy_tester_steps_and_wait_for_reports",
                    "entry_count": 3,
                    "total_entry_count": 3,
                    "step_count": 3,
                    "ready_to_collect_count": 0,
                    "waiting_count": 3,
                    "step_report_ready_count": 0,
                    "step_waiting_report_count": 3,
                    "step_launch_needed_count": 3,
                    "static_strategy_config_count": 1,
                    "static_strategy_configs": [
                        "methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_optimization.ini"
                    ],
                    "static_candidate_label_count": 1,
                    "static_candidate_labels": ["sell_hour12_m30m15_2025"],
                    "next_launch_step": {
                        "queue_id": "back_forward",
                        "step_label": "backtest",
                        "symbol": "XAUUSD-m",
                        "period": "M1",
                        "dates": "2026.06.30 -> 2026.07.08",
                        "forward": "Disabled",
                        "inputs": "Swing_Evaluation_Trader_backtest.set",
                        "report": "Tester\\Swing_Evaluation_Trader_backtest",
                    },
                    "operator_handoff": {
                        "state": "run_next_mt5_strategy_tester_step",
                        "collect_ready": False,
                        "ready_entry_ids": [],
                        "waiting_entry_ids": ["back_forward", "static_optimization"],
                        "dry_run_command_text": (
                            "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                            "--queue runtime/latest_mt5_manual_test_queue_with_optimization.json"
                        ),
                        "execute_command_text": (
                            "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                            "--queue runtime/latest_mt5_manual_test_queue_with_optimization.json --execute"
                        ),
                        "execute_and_refresh_analysis_command_text": (
                            "python3 methods/swing_eval/analysis/mt5_manual_collect.py "
                            "--queue runtime/latest_mt5_manual_test_queue_with_optimization.json --execute "
                            "--refresh-strategy-tester-analysis"
                        ),
                    },
                    "operation_cards": [
                        {
                            "order": 1,
                            "is_next": True,
                            "action": "run_in_mt5",
                            "purpose": "Backtest",
                            "queue_id": "back_forward",
                            "step_label": "backtest",
                            "forward": "Disabled",
                            "optimization": "0",
                            "optimization_label": "Disabled",
                            "inputs": "Swing_Evaluation_Trader_backtest.set",
                            "report": "Tester\\Swing_Evaluation_Trader_backtest",
                            "collect_status": "waiting_for_reports",
                        },
                        {
                            "order": 2,
                            "is_next": False,
                            "action": "run_in_mt5",
                            "purpose": "Optimization",
                            "queue_id": "static_optimization",
                            "step_label": "optimization",
                            "forward": "1/4",
                            "optimization": "2",
                            "optimization_label": "Fast genetic algorithm",
                            "inputs": "Swing_Evaluation_Trader_optimization.set",
                            "report": "Tester\\Swing_Evaluation_Trader_optimization",
                            "collect_status": "waiting_for_reports",
                            "collect_command_text": (
                                "python3 methods/swing_eval/analysis/mt5_tester_run.py "
                                "--config methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_optimization.ini "
                                "--collect-only"
                            ),
                        },
                        {
                            "order": 3,
                            "is_next": False,
                            "action": "run_in_mt5",
                            "purpose": "Sell Hour12 M30M15 2025",
                            "queue_id": "static_sell_hour12_m30m15_2025",
                            "step_label": "sell_hour12_m30m15_2025",
                            "forward": "1/4",
                            "optimization": "2",
                            "optimization_label": "Fast genetic algorithm",
                            "inputs": "Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set",
                            "report": "Tester\\Swing_Evaluation_Trader_sell_hour12_m30m15_validation_2025",
                            "collect_status": "waiting_for_reports",
                            "collect_command_text": (
                                "python3 methods/swing_eval/analysis/mt5_tester_run.py "
                                "--config methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_validation.ini "
                                "--report-name 'Tester\\Swing_Evaluation_Trader_sell_hour12_m30m15_validation_2025' "
                                "--collect-only --from-date 2025.01.01 --to-date 2025.12.31 --forward-mode 3"
                            ),
                        },
                    ],
                    "execution_checklist": [
                        {
                            "order": 1,
                            "queue_id": "back_forward",
                            "step_label": "backtest",
                            "symbol": "XAUUSD-m",
                            "period": "M1",
                            "dates": "2026.06.30 -> 2026.07.08",
                            "forward": "Disabled",
                            "optimization": "0",
                            "optimization_label": "Disabled",
                            "inputs": "Swing_Evaluation_Trader_backtest.set",
                            "report": "Tester\\Swing_Evaluation_Trader_backtest",
                            "step_report_status": "waiting_report",
                        },
                        {
                            "order": 2,
                            "queue_id": "static_optimization",
                            "step_label": "optimization",
                            "symbol": "XAUUSD-m",
                            "period": "M1",
                            "dates": "2026.06.30 -> 2026.07.08",
                            "forward": "1/4",
                            "optimization": "2",
                            "optimization_label": "Fast genetic algorithm",
                            "inputs": "Swing_Evaluation_Trader_optimization.set",
                            "report": "Tester\\Swing_Evaluation_Trader_optimization",
                            "step_report_status": "waiting_report",
                            "launch_command_kind": "direct_config",
                            "launch_command_text": (
                                "'/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine' "
                                "'C:\\Program Files\\MetaTrader 5\\terminal64.exe' "
                                "'/config:C:\\Program Files\\MetaTrader 5\\MQL5\\Profiles\\Tester\\Swing_Evaluation_Trader_optimization.ini'"
                            ),
                            "direct_config_reason": "static_config_matches_step",
                        },
                        {
                            "order": 3,
                            "queue_id": "static_sell_hour12_m30m15_2025",
                            "step_label": "sell_hour12_m30m15_2025",
                            "symbol": "XAUUSD-m",
                            "period": "M1",
                            "dates": "2025.01.01 -> 2025.12.31",
                            "forward": "1/4",
                            "optimization": "2",
                            "optimization_label": "Fast genetic algorithm",
                            "inputs": "Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set",
                            "report": "Tester\\Swing_Evaluation_Trader_sell_hour12_m30m15_validation_2025",
                            "step_report_status": "waiting_report",
                            "launch_command_kind": "runner_execute",
                            "launch_command_text": (
                                "python3 methods/swing_eval/analysis/mt5_tester_run.py "
                                "--config methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_validation.ini "
                                "--report-name 'Tester\\Swing_Evaluation_Trader_sell_hour12_m30m15_validation_2025' "
                                "--from-date 2025.01.01 --to-date 2025.12.31 --forward-mode 3"
                            ),
                            "direct_config_reason": (
                                "static_config_mismatch:report:"
                                "Tester\\Swing_Evaluation_Trader_sell_hour12_m30m15_validation->"
                                "Tester\\Swing_Evaluation_Trader_sell_hour12_m30m15_validation_2025"
                            ),
                        },
                    ],
                },
            )
            write_json(
                root / "runtime" / "sell.json",
                optimization_payload(
                    stable=2,
                    source_time={
                        "expected_from_date": "2026.06.30",
                        "expected_to_date": "2026.07.08",
                        "actual_first_server_time": "2026.06.30 01:00:00",
                        "actual_last_server_time": "2026.07.07 23:59:00",
                        "actual_span_days": 7.96,
                        "matches_expected_range": True,
                        "warnings": [],
                    },
                ),
            )
            write_json(root / "runtime" / "buy.json", optimization_payload(stable=0))
            write_json(root / "runtime" / "sell_missing_source_time.json", optimization_payload(stable=2))

            payload = build_strategy_tester_analysis(
                root,
                report_specs=[
                    OptimizationReportSpec("sell_candidate", "SELL", "annual", "runtime/sell.json"),
                    OptimizationReportSpec(
                        "sell_missing_source_time",
                        "SELL",
                        "annual",
                        "runtime/sell_missing_source_time.json",
                    ),
                    OptimizationReportSpec("buy_aggregate", "BUY", "annual", "runtime/buy.json"),
                ],
            )
            markdown = format_markdown(payload)

            self.assertEqual(payload["adoption"]["status"], "not_ready")
            self.assertEqual(payload["back_forward_decision"]["status"], "run_manual_back_forward")
            self.assertFalse(payload["back_forward_decision"]["adoptable"])
            self.assertEqual(
                [artifact["label"] for artifact in payload["source_artifacts"]],
                [
                    "promotion_gate",
                    "spec_coverage",
                    "back_forward_run",
                    "tester_status",
                    "manual_test_queue",
                    "manual_test_queue_with_optimization",
                ],
            )
            self.assertEqual(payload["source_artifacts"][0]["path"], "runtime/latest_promotion_gate.json")
            self.assertTrue(payload["source_artifacts"][0]["exists"])
            self.assertIn("mt5_back_forward:plan_only", payload["adoption"]["blockers"])
            self.assertIn("buy_candidate_missing", payload["adoption"]["blockers"])
            self.assertIn(
                "buy_candidate_gap:needs_buy_diagnostic",
                payload["adoption"]["blockers"],
            )
            self.assertIn(
                "candidate_source_time_missing:sell_missing_source_time",
                payload["adoption"]["blockers"],
            )
            self.assertIn("methods/swing_eval/analysis/mt5_back_forward_run.py --mode both --collect-only", markdown)
            self.assertIn("--refresh-strategy-tester-analysis", markdown)
            self.assertIn(
                "Promotion Gate source: generated_at=2026.07.16 22:30, "
                "state=not_ready, path=runtime/latest_promotion_gate.json",
                markdown,
            )
            self.assertIn(
                "Spec Coverage source: generated_at=2026.07.16 22:31, "
                "state=not_complete:2, path=runtime/latest_spec_coverage.json",
                markdown,
            )
            self.assertIn(
                "Refresh analysis command: `python3 methods/swing_eval/analysis/mt5_strategy_tester_analysis.py "
                "--output-json runtime/latest_mt5_strategy_tester_analysis.json "
                "--output-md runtime/latest_mt5_strategy_tester_analysis.md`",
                markdown,
            )

            self.assertIn("## Source Artifacts", markdown)
            self.assertIn("promotion_gate", markdown)
            self.assertIn("runtime/latest_promotion_gate.json", markdown)
            self.assertIn("manual_test_queue_with_optimization", markdown)
            self.assertIn("## MT5 Manual Queue", markdown)
            self.assertIn("Handoff waiting entries: back_forward", markdown)
            self.assertIn("--queue runtime/latest_mt5_manual_test_queue.json --execute", markdown)
            self.assertIn("### Operation Cards", markdown)
            self.assertIn("Backtest", markdown)
            self.assertIn("Forward Test", markdown)
            self.assertIn("### Manual Execution Checklist", markdown)
            self.assertIn("Swing_Evaluation_Trader_forward_test.set", markdown)
            self.assertIn("## MT5 Manual Queue With Optimization", markdown)
            self.assertEqual(
                payload["manual_test_queue_with_optimization"]["static_strategy_config_count"],
                1,
            )
            self.assertEqual(
                payload["manual_test_queue_with_optimization"]["static_candidate_labels"],
                ["sell_hour12_m30m15_2025"],
            )
            self.assertIn(
                "Static configs: methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_optimization.ini",
                markdown,
            )
            self.assertIn("Static candidate labels: sell_hour12_m30m15_2025", markdown)
            self.assertIn("Handoff waiting entries: back_forward, static_optimization", markdown)
            self.assertIn("--queue runtime/latest_mt5_manual_test_queue_with_optimization.json --execute", markdown)
            self.assertIn("Fast genetic algorithm", markdown)
            self.assertIn("Swing_Evaluation_Trader_optimization.set", markdown)
            self.assertIn("### MT5 Launch Commands", markdown)
            self.assertIn("runner execute: python3 methods/swing_eval/analysis/mt5_tester_run.py", markdown)
            self.assertIn("--from-date 2025.01.01 --to-date 2025.12.31 --forward-mode 3", markdown)
            self.assertIn("static_config_mismatch:report:", markdown)
            self.assertIn("### Entry Collect Commands", markdown)
            self.assertIn("--collect-only --from-date 2025.01.01 --to-date 2025.12.31 --forward-mode 3", markdown)
            self.assertIn("sell_candidate", markdown)
            self.assertIn("candidate_source_time_missing:sell_missing_source_time", markdown)
            self.assertIn("source time", markdown)
            self.assertIn("2026.06.30 -> 2026.07.08", markdown)
            self.assertIn("2026.06.30 01:00:00 -> 2026.07.07 23:59:00", markdown)
            self.assertIn("buy_aggregate", markdown)
            self.assertIn("Back/Forward runner is still plan-only", markdown)
            self.assertIn("Decision status: run_manual_back_forward", markdown)
            self.assertIn("Decision next action: run_backtest_then_forward_in_mt5_strategy_tester", markdown)
            self.assertIn("## Coverage Next Actions", markdown)
            self.assertIn("run_mt5_manual_test_queue", markdown)
            self.assertIn("Open runtime/latest_mt5_manual_test_queue.md", markdown)
            self.assertIn("rerun_promotion_gate_after_evidence", markdown)

    def test_back_forward_collect_filter_prefers_manual_queue_start_time(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            old_command = (
                "python3 methods/swing_eval/analysis/mt5_back_forward_run.py --mode both --collect-only "
                "--run-id-prefix manual_check --csv-modified-after '2026.07.17 15:04'"
            )
            new_command = (
                "python3 methods/swing_eval/analysis/mt5_back_forward_run.py --mode both --collect-only "
                "--run-id-prefix manual_check --csv-modified-after '2026.07.17 16:05'"
            )
            write_json(
                root / "runtime" / "latest_promotion_gate.json",
                {"ok": True, "generated_at": "2026.07.17 16:00", "decision": "not_ready"},
            )
            write_json(
                root / "runtime" / "latest_spec_coverage.json",
                {
                    "ok": True,
                    "generated_at": "2026.07.17 16:00",
                    "goal_completion_proven": False,
                    "not_complete_reasons": ["mt5_back_forward_not_executed:plan_only"],
                    "next_actions": [],
                },
            )
            write_json(
                root / "runtime" / "latest_mt5_back_forward_run.json",
                {
                    "ok": True,
                    "generated_at": "2026.07.17 15:04",
                    "mode": "both",
                    "dry_run": True,
                    "evidence_state": "plan_only",
                    "performance_comparison": {
                        "available": False,
                        "status": "missing_backtest_or_forward_report",
                    },
                    "manual_strategy_tester": {
                        "available": True,
                        "manual_run_start_after": "2026.07.17 15:04",
                        "recommended_collect_only_command_text": old_command,
                    },
                    "manual_collect_readiness": {
                        "ready": False,
                        "status": "waiting_report",
                        "blocking_reasons": ["backtest:waiting_report"],
                    },
                },
            )
            write_json(root / "runtime" / "latest_mt5_tester_status.json", {"generated_at": "2026.07.17 16:00"})
            write_json(
                root / "runtime" / "latest_mt5_manual_test_queue.json",
                {
                    "ok": True,
                    "generated_at": "2026.07.17 16:06",
                    "status": "waiting_for_manual_strategy_tester_results",
                    "entries": [
                        {
                            "id": "back_forward",
                            "source_json": "runtime/latest_mt5_back_forward_run.json",
                            "manual_run_start_after": "2026.07.17 16:05",
                            "collect_modified_after": "2026.07.17 16:05",
                            "collect_only_command_text": new_command,
                        }
                    ],
                },
            )
            write_json(root / "runtime" / "latest_mt5_manual_test_queue_with_optimization.json", {"ok": True})
            write_json(root / "runtime" / "sell.json", optimization_payload(stable=2))

            payload = build_strategy_tester_analysis(
                root,
                report_specs=[
                    OptimizationReportSpec("sell_candidate", "SELL", "annual", "runtime/sell.json"),
                ],
            )
            markdown = format_markdown(payload)

        self.assertEqual(payload["back_forward_run"]["recommended_collect_only_command_text"], new_command)
        self.assertEqual(payload["back_forward_run"]["manual_run_start_after"], "2026.07.17 16:05")
        self.assertEqual(payload["back_forward_run"]["manual_collect_modified_after"], "2026.07.17 16:05")
        self.assertEqual(payload["back_forward_decision"]["collect_command_text"], new_command)
        self.assertIn("--csv-modified-after '2026.07.17 16:05'", markdown)
        self.assertNotIn("2026.07.17 15:04", payload["back_forward_decision"]["collect_command_text"])

    def test_back_forward_decision_blocks_forward_regression_after_execution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_json(root / "runtime" / "sell.json", optimization_payload(stable=2))
            write_json(root / "runtime" / "buy.json", optimization_payload(stable=2))
            write_json(
                root / "runtime" / "latest_promotion_gate.json",
                {"ok": True, "generated_at": "2026.07.16 22:30", "decision": "ready"},
            )
            write_json(
                root / "runtime" / "latest_spec_coverage.json",
                {"ok": True, "generated_at": "2026.07.16 22:31", "not_complete_reasons": []},
            )
            write_json(
                root / "runtime" / "latest_mt5_back_forward_run.json",
                {
                    "ok": True,
                    "generated_at": "2026.07.16 22:32",
                    "evidence_state": "executed_degraded",
                    "performance_comparison": {
                        "available": True,
                        "status": "forward_degraded_vs_backtest",
                        "thresholds": {
                            "min_closed": 30,
                            "break_even_pf": 1.0,
                            "break_even_avg_r": 0.0,
                            "degraded_pf_delta": -0.2,
                            "degraded_avg_r_delta": -0.05,
                        },
                        "rows": [
                            {
                                "dataset": "backtest",
                                "trades": 80,
                                "meets_min_closed": True,
                                "pf": 1.6,
                                "avg_r": 0.18,
                            },
                            {
                                "dataset": "forward",
                                "trades": 42,
                                "meets_min_closed": True,
                                "pf": 1.25,
                                "avg_r": 0.08,
                                "pf_delta_vs_backtest": -0.35,
                                "avg_r_delta_vs_backtest": -0.1,
                            },
                        ],
                    },
                },
            )

            payload = build_strategy_tester_analysis(
                root,
                report_specs=[
                    OptimizationReportSpec("sell_candidate", "SELL", "annual", "runtime/sell.json"),
                    OptimizationReportSpec("buy_candidate", "BUY", "annual", "runtime/buy.json"),
                ],
            )
            markdown = format_markdown(payload)

            self.assertEqual(payload["back_forward_decision"]["status"], "forward_regression")
            self.assertFalse(payload["back_forward_decision"]["adoptable"])
            self.assertEqual(
                payload["back_forward_decision"]["next_action"],
                "reject_or_refit_before_promotion",
            )
            self.assertEqual(payload["back_forward_decision"]["forward_pf_delta_vs_backtest"], -0.35)
            self.assertEqual(payload["adoption"]["status"], "not_ready")
            self.assertIn("mt5_back_forward:executed_degraded", payload["adoption"]["blockers"])
            self.assertIn(
                "mt5_back_forward_decision:forward_regression",
                payload["adoption"]["blockers"],
            )
            self.assertIn("Decision status: forward_regression", markdown)
            self.assertIn("Forward PF delta vs backtest: -0.35", markdown)

    def test_back_forward_decision_collect_ready_prefers_collect_action(self):
        decision = back_forward_decision_summary(
            {
                "exists": True,
                "evidence_state": "plan_only",
                "performance_status": "missing_backtest_or_forward_report",
                "manual_collect_ready": True,
                "manual_collect_status": "ready",
                "recommended_collect_only_command_text": "python3 methods/swing_eval/analysis/mt5_back_forward_run.py --collect-only",
            }
        )

        self.assertEqual(decision["status"], "collect_ready")
        self.assertEqual(decision["next_action"], "collect_manual_back_forward_results")
        self.assertFalse(decision["adoptable"])
        self.assertIn("--collect-only", decision["collect_command_text"])

    def test_adoption_reports_buy_candidate_gap_diagnostic_labels(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_json(root / "runtime" / "sell.json", optimization_payload(stable=2))
            write_json(root / "runtime" / "buy_wide.json", optimization_payload(stable=0))
            write_json(root / "runtime" / "buy_hour03.json", optimization_payload(stable=0))

            payload = build_strategy_tester_analysis(
                root,
                report_specs=[
                    OptimizationReportSpec("sell_candidate", "SELL", "annual", "runtime/sell.json"),
                    OptimizationReportSpec(
                        "buy_hour03_wide_stop_2025",
                        "BUY",
                        "annual",
                        "runtime/buy_hour03.json",
                    ),
                    OptimizationReportSpec(
                        "buy_wide_stop_short",
                        "BUY",
                        "short",
                        "runtime/buy_wide.json",
                    ),
                ],
            )
            markdown = format_markdown(payload)

            self.assertIn("buy_candidate_missing", payload["adoption"]["blockers"])
            self.assertIn(
                "buy_candidate_gap:needs_buy_diagnostic:buy_wide_stop_short,buy_hour03_wide_stop_2025",
                payload["adoption"]["blockers"],
            )
            self.assertIn(
                "buy_candidate_gap:needs_buy_diagnostic:buy_wide_stop_short,buy_hour03_wide_stop_2025",
                markdown,
            )

    def test_script_name_is_referenceable_for_coverage_docs(self):
        self.assertIn("mt5_strategy_tester_analysis.py", "methods/swing_eval/analysis/mt5_strategy_tester_analysis.py")


if __name__ == "__main__":
    unittest.main()
