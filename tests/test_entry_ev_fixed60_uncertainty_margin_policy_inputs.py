from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_fixed60_uncertainty_margin_policy_inputs import (
    add_fixed60_uncertainty_margin_columns,
    build_prior_table_for_group_spec,
    copy_side_gap_quantiles,
    normalize_trade_rows,
    score_kind_for_margin,
)


class EntryEvFixed60UncertaintyMarginPolicyInputsTest(unittest.TestCase):
    def test_score_kind_for_margin_uses_group_and_weight_label(self) -> None:
        self.assertEqual(
            score_kind_for_margin(
                "fixed60_uncertainty_margin",
                ["family", "direction", "combined_regime", "session_regime"],
                0.5,
            ),
            "fixed60_uncertainty_margin_famdirregsess_w0p5",
        )

    def test_build_prior_table_uses_only_previous_months(self) -> None:
        trades = normalize_trade_rows(
            pd.DataFrame(
                {
                    "month": ["2026-01", "2026-01", "2026-02"],
                    "family": ["fam", "fam", "fam"],
                    "direction": ["long", "long", "long"],
                    "combined_regime": ["range", "range", "range"],
                    "session_regime": ["ny", "ny", "ny"],
                    "adjusted_pnl": [-1.0, 2.0, -3.0],
                    "fixed_pred_pnl": [1.0, 2.0, 1.0],
                    "fixed_actual_pnl": [-1.0, 1.0, -1.0],
                }
            )
        )

        prior = build_prior_table_for_group_spec(
            trades,
            group_columns=["family", "direction", "combined_regime", "session_regime"],
            months=["2026-01", "2026-02", "2026-03"],
        )

        jan = prior[prior["month"].eq("2026-01")].iloc[0]
        feb = prior[prior["month"].eq("2026-02")].iloc[0]
        mar = prior[prior["month"].eq("2026-03")].iloc[0]
        self.assertEqual(jan["prior_trade_count"], 0.0)
        self.assertEqual(feb["prior_trade_count"], 2.0)
        self.assertEqual(feb["prior_fixed_false_positive_rate"], 0.5)
        self.assertEqual(mar["prior_trade_count"], 3.0)
        self.assertAlmostEqual(mar["prior_fixed_false_positive_rate"], 2.0 / 3.0)

    def test_add_margin_columns_subtracts_supported_prior_risk(self) -> None:
        predictions = pd.DataFrame(
            {
                "dataset_month": ["2026-02", "2026-02"],
                "combined_regime": ["range", "range"],
                "session_regime": ["ny", "ny"],
                "raw_long": [10.0, 9.0],
                "raw_short": [8.0, 8.0],
                "pred_long_fixed_60m_adjusted_pnl": [4.0, -2.0],
                "pred_short_fixed_60m_adjusted_pnl": [3.0, 3.0],
                "pred_long_entry_local_rank": [0.1, 0.2],
                "pred_short_entry_local_rank": [0.3, 0.4],
            }
        )
        trades = normalize_trade_rows(
            pd.DataFrame(
                {
                    "month": ["2026-01", "2026-01"],
                    "family": ["fam", "fam"],
                    "direction": ["long", "long"],
                    "combined_regime": ["range", "range"],
                    "session_regime": ["ny", "ny"],
                    "adjusted_pnl": [-1.0, 1.0],
                    "fixed_pred_pnl": [1.0, 1.0],
                    "fixed_actual_pnl": [-1.0, 1.0],
                }
            )
        )

        output, summary = add_fixed60_uncertainty_margin_columns(
            predictions,
            family="fam",
            trade_rows=trades,
            group_specs=[["family", "direction", "combined_regime", "session_regime"]],
            score_kind_prefix="fixed60_uncertainty_margin",
            weights=[1.0],
            long_column="raw_long",
            short_column="raw_short",
            long_fixed_pred_column="pred_long_fixed_60m_adjusted_pnl",
            short_fixed_pred_column="pred_short_fixed_60m_adjusted_pnl",
            long_rank_column="pred_long_entry_local_rank",
            short_rank_column="pred_short_entry_local_rank",
            quantile_scopes=["month"],
            min_prior_trades=2.0,
            risk_mode="fp_rate_times_positive_fixed_pred",
            default_risk=0.0,
        )

        score_kind = "fixed60_uncertainty_margin_famdirregsess_w1"
        self.assertEqual(
            output[f"pred_{score_kind}_long_best_adjusted_pnl"].tolist(),
            [8.0, 9.0],
        )
        self.assertEqual(
            output[f"pred_{score_kind}_short_best_adjusted_pnl"].tolist(),
            [8.0, 8.0],
        )
        self.assertIn(f"pred_{score_kind}_selected_score_pct_month", output.columns)
        self.assertEqual(summary.loc[0, "score_kind"], score_kind)
        self.assertAlmostEqual(summary.loc[0, "long_risk_q95"], 1.9)

    def test_copy_side_gap_quantiles_uses_source_score_kind(self) -> None:
        frame = pd.DataFrame(
            {
                "pred_source_side_gap_pct_month": [0.1, 0.9],
                "pred_target_side_gap_pct_month": [0.4, 0.5],
            }
        )

        output = copy_side_gap_quantiles(
            frame,
            source_score_kind="source",
            target_score_kind="target",
            quantile_scopes=["month"],
        )

        self.assertEqual(output["pred_target_side_gap_pct_month"].tolist(), [0.1, 0.9])


if __name__ == "__main__":
    unittest.main()
