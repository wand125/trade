import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "experiments" / "holding_risk_overlay.py"
SPEC = importlib.util.spec_from_file_location("holding_risk_overlay", SCRIPT_PATH)
holding_risk_overlay = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(holding_risk_overlay)


class HoldingRiskOverlayTests(unittest.TestCase):
    def test_month_specific_exclusion_prevents_cap_only_for_matching_context(self):
        frame = pd.DataFrame(
            {
                "dataset_month": ["2025-03", "2025-03"],
                "combined_regime": ["range_low_vol", "range_low_vol"],
                "session_regime": ["london", "asia"],
                "pred_mlp_long_exit_event_minutes": [100.0, 100.0],
                "pred_mlp_short_exit_event_minutes": [100.0, 100.0],
                "pred_trade_failure_pred_hit_actual_miss_long_prob": [1.0, 1.0],
                "pred_trade_failure_pred_hit_actual_miss_short_prob": [1.0, 1.0],
                "pred_trade_overestimate_high_q75_long_prob": [1.0, 1.0],
                "pred_trade_overestimate_high_q75_short_prob": [1.0, 1.0],
            }
        )

        output, summary = holding_risk_overlay.add_holding_cap_columns(
            frame,
            threshold_frame=frame,
            threshold_quantiles=[0.0],
            caps=[60.0],
            side_modes=["short_only"],
            include_combined_regimes=[],
            exclude_combined_regimes=[],
            include_combined_session_pairs=[],
            exclude_combined_session_pairs=[],
            exclude_combined_session_pairs_by_month=[("2025-03", "range_low_vol", "london")],
        )

        short_column = "pred_mlp_short_exit_event_minutes_predhit_q75_short_only_q0_cap60"
        long_column = "pred_mlp_long_exit_event_minutes_predhit_q75_short_only_q0_cap60"
        self.assertEqual(output[short_column].tolist(), [100.0, 60.0])
        self.assertEqual(output[long_column].tolist(), [100.0, 100.0])
        self.assertEqual(summary.loc[summary["side"].eq("short"), "active_rows"].iloc[0], 1)


if __name__ == "__main__":
    unittest.main()
