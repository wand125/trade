import argparse
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_replacement_risk_delta_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_replacement_risk_delta_diagnostics",
    SCRIPT_PATH,
)
entry_ev_replacement_risk_delta_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_replacement_risk_delta_diagnostics
SPEC.loader.exec_module(entry_ev_replacement_risk_delta_diagnostics)


def delta_row(
    decision: str,
    direction: str,
    pnl: float,
    stateful_net: float,
    blocked_positive: float = 0.0,
) -> dict[str, object]:
    return {
        "family": "toy",
        "month": "2024-01",
        "candidate": "toy_candidate",
        "direction": direction,
        "entry_decision_timestamp": pd.Timestamp(decision, tz="UTC"),
        "delta_status": "only_candidate",
        "candidate_adjusted_pnl": pnl,
        "candidate_blocked_base_adjusted_pnl": blocked_positive,
        "candidate_blocked_base_positive_pnl": blocked_positive,
        "candidate_blocked_base_negative_pnl": 0.0,
        "candidate_stateful_net_adjusted_pnl": stateful_net,
    }


def enriched_row(
    decision: str,
    direction: str,
    conf_bucket: str,
    profit_hit: float,
) -> dict[str, object]:
    side_prefix = "long" if direction == "long" else "short"
    row = {
        "family": "toy",
        "month": "2024-01",
        "candidate": "toy_candidate",
        "direction": direction,
        "entry_decision_timestamp": pd.Timestamp(decision, tz="UTC"),
        "combined_regime": "range_normal_vol",
        "session_regime": "ny_overlap",
    }
    for side in ["long", "short"]:
        row[f"pred_exit_regret_confidence_exit_{side}_predicted_exit_regret_risk"] = 0.1
        row[f"pred_exit_regret_confidence_exit_{side}_exit_regret_prediction_support"] = 5
        row[f"pred_exit_regret_confidence_exit_{side}_exit_regret_prediction_source"] = "bucket"
        row[f"pred_exit_regret_confidence_exit_{side}_side_confidence_gap_bucket"] = "weak"
        row[f"pred_exit_regret_confidence_exit_{side}_loss_first_prob_bucket"] = "low"
        row[f"pred_exit_regret_confidence_exit_{side}_time_exit_prob_bucket"] = "very_low"
        row[f"pred_exit_regret_selector_confidenceexit_bucket_t0p4_{side}_forced_exit_blocked"] = False
        row[f"pred_exit_regret_selector_confidenceexit_bucket_t0p4_{side}_best_adjusted_pnl"] = 1.0
        row[f"pred_side_prior_pressure_{side}_predicted_ev_overestimate_risk"] = 0.2
        row[f"pred_side_prior_pressure_{side}_ev_overestimate_prediction_source"] = "bucket"
        row[f"pred_{side}_profit_barrier_hit"] = 1.0
        row[f"pred_{side}_fixed_720m_adjusted_pnl"] = 2.0
    row[
        f"pred_exit_regret_confidence_exit_{side_prefix}_side_confidence_gap_bucket"
    ] = conf_bucket
    row[f"pred_{side_prefix}_profit_barrier_hit"] = profit_hit
    return row


class EntryEvReplacementRiskDeltaDiagnosticsTests(unittest.TestCase):
    def test_build_replacement_risk_diagnostics_targets_stateful_harm(self):
        delta = pd.DataFrame(
            [
                delta_row("2024-01-02 00:00:00", "long", -10.0, -10.0),
                delta_row("2024-01-02 01:00:00", "short", 5.0, -7.0, 12.0),
                delta_row("2024-01-02 02:00:00", "long", 6.0, 6.0),
            ]
        )
        enriched = pd.DataFrame(
            [
                enriched_row("2024-01-02 00:00:00", "long", "nonpositive", 0.0),
                enriched_row("2024-01-02 01:00:00", "short", "strong", 0.0),
                enriched_row("2024-01-02 02:00:00", "long", "weak", 1.0),
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            delta_dir = tmp_path / "delta"
            enriched_dir = tmp_path / "enriched"
            delta_dir.mkdir()
            enriched_dir.mkdir()
            delta.to_csv(delta_dir / "trade_delta_rows.csv", index=False)
            enriched.to_csv(enriched_dir / "residual_enriched_trades.csv", index=False)
            args = argparse.Namespace(
                delta_run=[f"unit={delta_dir}"],
                enriched_trades=[f"unit={enriched_dir}"],
                exit_regret_prefix="pred_exit_regret_confidence_exit",
                selector_prefix="pred_exit_regret_selector_confidenceexit_bucket_t0p4",
                side_prior_prefix="pred_side_prior_pressure",
                output_dir=tmp_path,
                label="unit_replacement_risk",
            )
            run_dir = (
                entry_ev_replacement_risk_delta_diagnostics
                .build_replacement_risk_diagnostics(args)
            )
            rows = pd.read_csv(run_dir / "replacement_rows.csv")
            screen = pd.read_csv(run_dir / "screen_summary.csv")

        self.assertEqual(int(rows["replacement_harm_target"].sum()), 2)
        self.assertEqual(int(rows["positive_blocking_harm_target"].sum()), 1)
        conf_extreme = screen[screen["screen"].eq("conf_gap_extreme")].iloc[0]
        self.assertEqual(conf_extreme["flagged_rows"], 2)
        self.assertEqual(conf_extreme["flagged_harmful_rows"], 2)
        self.assertAlmostEqual(
            conf_extreme["approx_stateful_improvement_if_suppressed"],
            17.0,
        )


if __name__ == "__main__":
    unittest.main()
