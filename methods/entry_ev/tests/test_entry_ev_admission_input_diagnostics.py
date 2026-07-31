import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_admission_input_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_admission_input_diagnostics",
    SCRIPT_PATH,
)
entry_ev_admission_input_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(entry_ev_admission_input_diagnostics)


class EntryEvAdmissionInputDiagnosticsTests(unittest.TestCase):
    def prediction_frame(self):
        return pd.DataFrame(
            {
                "dataset_month": ["2024-01", "2024-01", "2024-01"],
                "pred_calibrated_long_best_adjusted_pnl": [12.0, 8.0, 13.0],
                "pred_calibrated_short_best_adjusted_pnl": [6.0, 20.0, 7.0],
                "pred_long_entry_local_rank": [0.7, 0.4, 0.8],
                "pred_short_entry_local_rank": [0.3, 0.9, 0.8],
                "pred_mlp_long_exit_event_minutes": [60.0, 60.0, 10.0],
                "pred_mlp_short_exit_event_minutes": [60.0, 60.0, 60.0],
            }
        )

    def test_add_base_columns_selects_side_and_holding(self):
        base = entry_ev_admission_input_diagnostics.add_base_columns(
            self.prediction_frame(),
            family="example",
            long_column="pred_calibrated_long_best_adjusted_pnl",
            short_column="pred_calibrated_short_best_adjusted_pnl",
            long_rank_column="pred_long_entry_local_rank",
            short_rank_column="pred_short_entry_local_rank",
            long_holding_column="pred_mlp_long_exit_event_minutes",
            short_holding_column="pred_mlp_short_exit_event_minutes",
            min_valid_predicted_hold_minutes=30.0,
        )

        self.assertEqual(base["selected_side"].tolist(), [1, -1, 1])
        self.assertEqual(base["selected_holding_ok"].tolist(), [True, True, False])

    def test_config_summary_counts_each_filter_stage(self):
        base = entry_ev_admission_input_diagnostics.add_base_columns(
            self.prediction_frame(),
            family="example",
            long_column="pred_calibrated_long_best_adjusted_pnl",
            short_column="pred_calibrated_short_best_adjusted_pnl",
            long_rank_column="pred_long_entry_local_rank",
            short_rank_column="pred_short_entry_local_rank",
            long_holding_column="pred_mlp_long_exit_event_minutes",
            short_holding_column="pred_mlp_short_exit_event_minutes",
            min_valid_predicted_hold_minutes=30.0,
        )

        summary = entry_ev_admission_input_diagnostics.summarize_config_group(
            base,
            entry_threshold=10.0,
            short_entry_threshold_offset=9.0,
            min_entry_rank=0.5,
            side_margin=5.0,
        )

        self.assertEqual(summary["valid_prediction_count"], 3)
        self.assertEqual(summary["threshold_ok_count"], 3)
        self.assertEqual(summary["selected_holding_ok_count"], 2)
        self.assertEqual(summary["rank_ok_count"], 3)
        self.assertEqual(summary["side_margin_ok_count"], 3)
        self.assertEqual(summary["stateless_enter_count"], 2)
        self.assertEqual(summary["stateless_long_enter_count"], 1)
        self.assertEqual(summary["stateless_short_enter_count"], 1)

    def test_aggregate_config_summary_sums_months(self):
        base = entry_ev_admission_input_diagnostics.add_base_columns(
            self.prediction_frame(),
            family="example",
            long_column="pred_calibrated_long_best_adjusted_pnl",
            short_column="pred_calibrated_short_best_adjusted_pnl",
            long_rank_column="pred_long_entry_local_rank",
            short_rank_column="pred_short_entry_local_rank",
            long_holding_column="pred_mlp_long_exit_event_minutes",
            short_holding_column="pred_mlp_short_exit_event_minutes",
            min_valid_predicted_hold_minutes=30.0,
        )
        _, config = entry_ev_admission_input_diagnostics.build_diagnostics(
            {"example": base},
            entry_thresholds=[10.0],
            short_entry_threshold_offsets=[9.0],
            min_entry_ranks=[0.5],
            side_margin=5.0,
        )

        summary = entry_ev_admission_input_diagnostics.aggregate_config_summary(config)

        self.assertEqual(int(summary.loc[0, "stateless_enter_count"]), 2)
        self.assertEqual(summary.loc[0, "months"], "2024-01")


if __name__ == "__main__":
    unittest.main()
