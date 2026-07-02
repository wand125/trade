from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_downside_meta_risk_margin_policy_inputs import (
    add_downside_margin_columns,
    score_kind_for_weight,
    summarize_margin_effect,
)


class EntryEvDownsideMetaRiskMarginPolicyInputsTest(unittest.TestCase):
    def test_score_kind_for_weight_uses_stable_label(self) -> None:
        self.assertEqual(score_kind_for_weight("downside_margin", 2.5), "downside_margin_w2p5")

    def test_add_downside_margin_columns_subtracts_risk_and_adds_quantiles(self) -> None:
        frame = pd.DataFrame(
            {
                "dataset_month": ["2026-01", "2026-01", "2026-01"],
                "combined_regime": ["range", "range", "trend"],
                "session_regime": ["asia", "asia", "ny"],
                "raw_long": [10.0, 8.0, 7.0],
                "raw_short": [9.0, 11.0, 6.0],
                "down_long": [1.0, 0.0, 2.0],
                "down_short": [0.0, 3.0, 0.0],
                "rank_long": [0.1, 0.2, 0.3],
                "rank_short": [0.4, 0.5, 0.6],
            }
        )

        output = add_downside_margin_columns(
            frame,
            family="fam",
            score_kind_prefix="downside_margin",
            weights=[2.0],
            long_column="raw_long",
            short_column="raw_short",
            long_downside_column="down_long",
            short_downside_column="down_short",
            long_rank_column="rank_long",
            short_rank_column="rank_short",
            quantile_scopes=["month"],
            downside_floor=0.0,
        )

        self.assertEqual(
            output["pred_downside_margin_w2_long_best_adjusted_pnl"].tolist(),
            [8.0, 8.0, 3.0],
        )
        self.assertEqual(
            output["pred_downside_margin_w2_short_best_adjusted_pnl"].tolist(),
            [9.0, 5.0, 6.0],
        )
        self.assertIn("pred_downside_margin_w2_selected_score_pct_month", output.columns)
        self.assertIn("pred_downside_margin_w2_side_gap_pct_month", output.columns)
        self.assertIn("pred_downside_margin_w2_selected_entry_rank_pct_month", output.columns)

    def test_summarize_margin_effect_reports_side_switch_share(self) -> None:
        frame = pd.DataFrame(
            {
                "dataset_month": ["2026-01", "2026-01"],
                "raw_long": [10.0, 8.0],
                "raw_short": [9.0, 11.0],
                "pred_downside_margin_w2_long_best_adjusted_pnl": [8.0, 8.0],
                "pred_downside_margin_w2_short_best_adjusted_pnl": [9.0, 5.0],
            }
        )

        summary = summarize_margin_effect(
            {"fam": frame},
            score_kind_prefix="downside_margin",
            weights=[2.0],
            long_column="raw_long",
            short_column="raw_short",
        )

        self.assertEqual(summary.loc[0, "row_count"], 2)
        self.assertEqual(summary.loc[0, "side_switch_share"], 1.0)


if __name__ == "__main__":
    unittest.main()
