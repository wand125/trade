import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_executable_ev_policy_inputs.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_executable_ev_policy_inputs",
    SCRIPT_PATH,
)
entry_ev_executable_ev_policy_inputs = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_executable_ev_policy_inputs
SPEC.loader.exec_module(entry_ev_executable_ev_policy_inputs)


class EntryEvExecutableEvPolicyInputsTests(unittest.TestCase):
    def prediction_frame(self):
        return pd.DataFrame(
            {
                "dataset_month": ["2024-03", "2024-04"],
                "decision_timestamp": [
                    "2024-03-10T00:00:00Z",
                    "2024-04-10T00:00:00Z",
                ],
                "combined_regime": ["range", "range"],
                "session_regime": ["asia", "asia"],
                "pred_calibrated_long_best_adjusted_pnl": [10.0, 10.0],
                "pred_calibrated_short_best_adjusted_pnl": [8.0, 8.0],
                "pred_long_entry_local_rank": [0.8, 0.9],
                "pred_short_entry_local_rank": [0.4, 0.5],
            }
        )

    def prior_frame(self):
        return pd.DataFrame(
            {
                "role": ["cal", "fresh", "future"],
                "candidate": ["q95", "q95", "q95"],
                "month": ["2024-02", "2024-03", "2024-04"],
                "direction": ["long", "long", "long"],
                "entry_decision_timestamp": [
                    "2024-02-10T00:00:00Z",
                    "2024-03-10T00:00:00Z",
                    "2024-04-10T00:00:00Z",
                ],
                "combined_regime": ["range", "range", "range"],
                "session_regime": ["asia", "asia", "asia"],
                "adjusted_pnl": [5.0, -5.0, 10.0],
                "actual_taken_best_adjusted_pnl": [10.0, 10.0, 10.0],
            }
        )

    def normalized_prior(self):
        prior = entry_ev_executable_ev_policy_inputs.normalize_prior_trades(
            self.prior_frame()
        )
        return entry_ev_executable_ev_policy_inputs.add_capture_ratio_columns(
            prior,
            min_oracle_edge=0.0,
            min_capture_factor=0.0,
            max_capture_factor=1.0,
        )

    def test_add_executable_ev_scores_uses_only_prior_months(self):
        enriched, _context, _global = (
            entry_ev_executable_ev_policy_inputs.add_executable_ev_scores(
                self.prediction_frame(),
                self.normalized_prior(),
                long_column="pred_calibrated_long_best_adjusted_pnl",
                short_column="pred_calibrated_short_best_adjusted_pnl",
                long_output_column="long_exec",
                short_output_column="short_exec",
                min_prior_months=1,
                recent_month_count=0,
                support_scale=1.0,
                default_capture_factor=1.0,
                min_capture_factor=0.0,
                max_capture_factor=1.0,
            )
        )

        march = enriched[enriched["dataset_month"].eq("2024-03")].iloc[0]
        april = enriched[enriched["dataset_month"].eq("2024-04")].iloc[0]

        self.assertAlmostEqual(march["pred_executable_long_capture_factor"], 0.5)
        self.assertAlmostEqual(march["long_exec"], 5.0)
        self.assertAlmostEqual(march["pred_executable_short_capture_factor"], 0.5)
        self.assertAlmostEqual(march["short_exec"], 4.0)
        self.assertAlmostEqual(april["pred_executable_long_capture_factor"], 0.25)
        self.assertAlmostEqual(april["long_exec"], 2.5)

    def test_add_executable_ev_scores_can_condition_on_family(self):
        predictions = self.prediction_frame()
        predictions["family"] = ["fam_a", "fam_b"]
        prior = pd.DataFrame(
            {
                "family": ["fam_a", "fam_b"],
                "role": ["cal", "cal"],
                "candidate": ["q95", "q95"],
                "month": ["2024-02", "2024-02"],
                "direction": ["long", "long"],
                "entry_decision_timestamp": [
                    "2024-02-10T00:00:00Z",
                    "2024-02-11T00:00:00Z",
                ],
                "combined_regime": ["range", "range"],
                "session_regime": ["asia", "asia"],
                "adjusted_pnl": [2.0, 8.0],
                "actual_taken_best_adjusted_pnl": [10.0, 10.0],
            }
        )
        normalized = entry_ev_executable_ev_policy_inputs.normalize_prior_trades(prior)
        normalized = entry_ev_executable_ev_policy_inputs.add_capture_ratio_columns(
            normalized,
            min_oracle_edge=0.0,
            min_capture_factor=0.0,
            max_capture_factor=1.0,
        )

        enriched, _context, _global = (
            entry_ev_executable_ev_policy_inputs.add_executable_ev_scores(
                predictions,
                normalized,
                long_column="pred_calibrated_long_best_adjusted_pnl",
                short_column="pred_calibrated_short_best_adjusted_pnl",
                long_output_column="long_exec",
                short_output_column="short_exec",
                min_prior_months=1,
                recent_month_count=0,
                support_scale=1.0,
                default_capture_factor=1.0,
                min_capture_factor=0.0,
                max_capture_factor=1.0,
                context_columns=["family", "direction", "combined_regime", "session_regime"],
            )
        )

        fam_a = enriched[enriched["family"].eq("fam_a")].iloc[0]
        fam_b = enriched[enriched["family"].eq("fam_b")].iloc[0]
        self.assertAlmostEqual(fam_a["pred_executable_long_capture_factor"], 0.2)
        self.assertAlmostEqual(fam_b["pred_executable_long_capture_factor"], 0.8)

    def test_add_executable_ev_scores_can_apply_partial_shrink(self):
        predictions = self.prediction_frame().iloc[:1].copy()
        prior = pd.DataFrame(
            {
                "role": ["cal"],
                "candidate": ["q95"],
                "month": ["2024-02"],
                "direction": ["long"],
                "entry_decision_timestamp": ["2024-02-10T00:00:00Z"],
                "combined_regime": ["range"],
                "session_regime": ["asia"],
                "adjusted_pnl": [2.0],
                "actual_taken_best_adjusted_pnl": [10.0],
            }
        )
        normalized = entry_ev_executable_ev_policy_inputs.normalize_prior_trades(prior)
        normalized = entry_ev_executable_ev_policy_inputs.add_capture_ratio_columns(
            normalized,
            min_oracle_edge=0.0,
            min_capture_factor=0.0,
            max_capture_factor=1.0,
        )

        enriched, _context, _global = (
            entry_ev_executable_ev_policy_inputs.add_executable_ev_scores(
                predictions,
                normalized,
                long_column="pred_calibrated_long_best_adjusted_pnl",
                short_column="pred_calibrated_short_best_adjusted_pnl",
                long_output_column="long_exec",
                short_output_column="short_exec",
                min_prior_months=1,
                recent_month_count=0,
                support_scale=1.0,
                default_capture_factor=1.0,
                min_capture_factor=0.0,
                max_capture_factor=1.0,
                capture_shrink_strength=0.5,
            )
        )

        self.assertAlmostEqual(enriched["pred_executable_long_capture_factor"].iloc[0], 0.6)
        self.assertAlmostEqual(enriched["long_exec"].iloc[0], 6.0)

    def test_add_executable_quantile_columns_writes_score_kind_columns(self):
        enriched, _context, _global = (
            entry_ev_executable_ev_policy_inputs.add_executable_ev_scores(
                self.prediction_frame(),
                self.normalized_prior(),
                long_column="pred_calibrated_long_best_adjusted_pnl",
                short_column="pred_calibrated_short_best_adjusted_pnl",
                long_output_column="long_exec",
                short_output_column="short_exec",
                min_prior_months=1,
                recent_month_count=0,
                support_scale=1.0,
                default_capture_factor=1.0,
                min_capture_factor=0.0,
                max_capture_factor=1.0,
            )
        )
        with_quantiles = (
            entry_ev_executable_ev_policy_inputs.add_executable_quantile_columns(
                enriched,
                family="example",
                score_kind="executable",
                long_output_column="long_exec",
                short_output_column="short_exec",
                long_rank_column="pred_long_entry_local_rank",
                short_rank_column="pred_short_entry_local_rank",
                quantile_scopes=["month"],
            )
        )

        self.assertIn("pred_executable_selected_score_pct_month", with_quantiles.columns)
        self.assertIn("pred_executable_side_gap_pct_month", with_quantiles.columns)
        self.assertIn(
            "pred_executable_selected_entry_rank_pct_month",
            with_quantiles.columns,
        )
        self.assertEqual(
            with_quantiles["pred_executable_quantile_scope_count_month"].tolist(),
            [1, 1],
        )


if __name__ == "__main__":
    unittest.main()
