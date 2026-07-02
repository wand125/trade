from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_hold_extension_stateful_replay import (
    extension_veto_applies,
    horizon_model_used,
    parse_horizon_modes,
    replay_group,
    selector_compatible_monthly_metrics,
    summarize_selection,
    summarize_stateful,
    universe_mask,
)


def row(
    *,
    entry_minute: int,
    exit_minute: int,
    adjusted_pnl: float,
    pred_delta: float,
    horizon: int,
    fixed_pnl: float,
    isolated_large_loss: bool,
) -> dict[str, object]:
    start = pd.Timestamp("2025-01-01 00:00:00+00:00")
    entry_time = start + pd.Timedelta(minutes=entry_minute)
    exit_time = start + pd.Timedelta(minutes=exit_minute)
    return {
        "source": "unit",
        "role": "unit_role",
        "family": "unit_family",
        "variant": "base",
        "candidate": "q95",
        "month": "2025-01",
        "direction": "long",
        "entry_timestamp": entry_time,
        "exit_timestamp": exit_time,
        "entry_price": 100.0,
        "exit_price": 100.0 + adjusted_pnl,
        "raw_pnl": adjusted_pnl,
        "adjusted_pnl": adjusted_pnl,
        "holding_minutes": float(exit_minute - entry_minute),
        "exit_reason": "signal_close",
        "entry_decision_timestamp": entry_time - pd.Timedelta(minutes=1),
        "exit_decision_timestamp": exit_time - pd.Timedelta(minutes=1),
        "pred_hold_extension_best_delta": pred_delta,
        "pred_hold_extension_best_horizon_minutes": horizon,
        "actual_taken_fixed_60m_adjusted_pnl": fixed_pnl,
        "isolated_large_loss": isolated_large_loss,
    }


class EntryEvHoldExtensionStatefulReplayTest(unittest.TestCase):
    def test_replay_group_extends_and_skips_overlapped_base_trade(self) -> None:
        frame = pd.DataFrame(
            [
                row(
                    entry_minute=1,
                    exit_minute=2,
                    adjusted_pnl=-3.0,
                    pred_delta=6.0,
                    horizon=60,
                    fixed_pnl=8.0,
                    isolated_large_loss=True,
                ),
                row(
                    entry_minute=10,
                    exit_minute=11,
                    adjusted_pnl=5.0,
                    pred_delta=0.0,
                    horizon=0,
                    fixed_pnl=5.0,
                    isolated_large_loss=False,
                ),
                row(
                    entry_minute=70,
                    exit_minute=71,
                    adjusted_pnl=2.0,
                    pred_delta=0.0,
                    horizon=0,
                    fixed_pnl=2.0,
                    isolated_large_loss=False,
                ),
            ]
        )
        apply_mask = universe_mask(frame, "isolated_large_loss")

        trades, skipped = replay_group(
            frame,
            apply_mask=apply_mask,
            threshold=5.0,
            horizon_mode="predicted",
            require_model_used=False,
            extension_veto_rule="none",
            profit_multiplier=1.0,
            loss_multiplier=1.2,
        )

        self.assertEqual(len(trades), 2)
        self.assertEqual(len(skipped), 1)
        self.assertTrue(trades[0]["hold_extension_applied"])
        self.assertEqual(trades[0]["exit_reason"], "hold_extension_60m")
        self.assertAlmostEqual(trades[0]["adjusted_pnl"], 8.0)
        self.assertEqual(skipped[0]["adjusted_pnl"], 5.0)
        self.assertFalse(trades[1]["hold_extension_applied"])

    def test_summarize_selection_accounts_for_skipped_pnl(self) -> None:
        base = pd.DataFrame(
            [
                row(
                    entry_minute=1,
                    exit_minute=2,
                    adjusted_pnl=-3.0,
                    pred_delta=6.0,
                    horizon=60,
                    fixed_pnl=8.0,
                    isolated_large_loss=True,
                ),
                row(
                    entry_minute=10,
                    exit_minute=11,
                    adjusted_pnl=5.0,
                    pred_delta=0.0,
                    horizon=0,
                    fixed_pnl=5.0,
                    isolated_large_loss=False,
                ),
            ]
        )
        trades, skipped = replay_group(
            base,
            apply_mask=universe_mask(base, "isolated_large_loss"),
            threshold=5.0,
            horizon_mode="predicted",
            require_model_used=False,
            extension_veto_rule="none",
            profit_multiplier=1.0,
            loss_multiplier=1.2,
        )
        trade_frame = pd.DataFrame(trades)
        skipped_frame = pd.DataFrame(skipped)
        monthly = summarize_stateful(
            trade_frame,
            base=base,
            skipped=skipped_frame,
            group_columns=["source", "role", "family", "variant", "candidate", "month"],
        )
        monthly["apply_universe"] = "isolated_large_loss"
        monthly["threshold"] = 5.0

        selection = summarize_selection(monthly)

        self.assertAlmostEqual(selection["base_total_adjusted_pnl_sum"].iloc[0], 2.0)
        self.assertAlmostEqual(selection["total_adjusted_pnl_sum"].iloc[0], 8.0)
        self.assertAlmostEqual(selection["skipped_adjusted_pnl_sum"].iloc[0], 5.0)
        self.assertAlmostEqual(selection["pnl_delta_vs_base_sum"].iloc[0], 6.0)

    def test_selector_compatible_monthly_metrics_separates_threshold_variants(self) -> None:
        monthly = pd.DataFrame(
            {
                "variant": ["loss_exit30_cd15", "loss_exit30_cd15"],
                "apply_universe": ["isolated_large_loss", "isolated_large_loss"],
                "threshold": [5.0, 10.0],
                "horizon_mode": ["predicted", "720"],
            }
        )

        output = selector_compatible_monthly_metrics(monthly)

        self.assertEqual(
            output["variant"].tolist(),
            [
                "loss_exit30_cd15__holdext_isolated_large_loss_t5_hpredicted",
                "loss_exit30_cd15__holdext_isolated_large_loss_t10_h720",
            ],
        )

    def test_selector_compatible_monthly_metrics_defaults_missing_horizon_mode(self) -> None:
        monthly = pd.DataFrame(
            {
                "variant": ["loss_exit30_cd15"],
                "apply_universe": ["isolated_large_loss"],
                "threshold": [5.0],
            }
        )

        output = selector_compatible_monthly_metrics(monthly)

        self.assertEqual(
            output["variant"].tolist(),
            ["loss_exit30_cd15__holdext_isolated_large_loss_t5_hpredicted"],
        )

    def test_universe_mask_supports_side_suffix(self) -> None:
        frame = pd.DataFrame(
            [
                row(
                    entry_minute=1,
                    exit_minute=2,
                    adjusted_pnl=-3.0,
                    pred_delta=6.0,
                    horizon=60,
                    fixed_pnl=8.0,
                    isolated_large_loss=True,
                ),
                {
                    **row(
                        entry_minute=3,
                        exit_minute=4,
                        adjusted_pnl=-3.0,
                        pred_delta=6.0,
                        horizon=60,
                        fixed_pnl=8.0,
                        isolated_large_loss=True,
                    ),
                    "direction": "short",
                },
            ]
        )

        self.assertEqual(universe_mask(frame, "isolated_large_loss_long").tolist(), [True, False])
        self.assertEqual(universe_mask(frame, "isolated_large_loss_short").tolist(), [False, True])

    def test_parse_horizon_modes_accepts_predicted_and_fixed_minutes(self) -> None:
        self.assertEqual(parse_horizon_modes("predicted,720,240"), ["predicted", "720", "240"])

    def test_fixed_horizon_mode_uses_matching_prediction_score(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    **row(
                        entry_minute=1,
                        exit_minute=2,
                        adjusted_pnl=-3.0,
                        pred_delta=0.0,
                        horizon=60,
                        fixed_pnl=8.0,
                        isolated_large_loss=True,
                    ),
                    "pred_hold_extension_delta_720m": -4.0,
                    "actual_taken_fixed_720m_adjusted_pnl": 12.0,
                }
            ]
        )

        trades, skipped = replay_group(
            frame,
            apply_mask=universe_mask(frame, "isolated_large_loss_long"),
            threshold=-5.0,
            horizon_mode="720",
            require_model_used=False,
            extension_veto_rule="none",
            profit_multiplier=1.0,
            loss_multiplier=1.2,
        )

        self.assertFalse(skipped)
        self.assertTrue(trades[0]["hold_extension_applied"])
        self.assertEqual(trades[0]["hold_extension_horizon_mode"], "720")
        self.assertEqual(trades[0]["hold_extension_score_column"], "pred_hold_extension_delta_720m")
        self.assertAlmostEqual(trades[0]["hold_extension_pred_delta"], -4.0)
        self.assertAlmostEqual(trades[0]["adjusted_pnl"], 12.0)

    def test_require_model_used_blocks_fallback_extension(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    **row(
                        entry_minute=1,
                        exit_minute=2,
                        adjusted_pnl=-3.0,
                        pred_delta=0.0,
                        horizon=60,
                        fixed_pnl=8.0,
                        isolated_large_loss=True,
                    ),
                    "pred_hold_extension_delta_720m": 0.5,
                    "pred_hold_extension_model_used_720m": False,
                    "actual_taken_fixed_720m_adjusted_pnl": -12.0,
                }
            ]
        )

        trades, skipped = replay_group(
            frame,
            apply_mask=universe_mask(frame, "isolated_large_loss_long"),
            threshold=-5.0,
            horizon_mode="720",
            require_model_used=True,
            extension_veto_rule="none",
            profit_multiplier=1.0,
            loss_multiplier=1.2,
        )

        self.assertFalse(skipped)
        self.assertFalse(trades[0]["hold_extension_applied"])
        self.assertAlmostEqual(trades[0]["adjusted_pnl"], -3.0)

    def test_extension_veto_blocks_matching_extension_and_keeps_base_trade(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    **row(
                        entry_minute=1,
                        exit_minute=2,
                        adjusted_pnl=-3.0,
                        pred_delta=0.0,
                        horizon=60,
                        fixed_pnl=8.0,
                        isolated_large_loss=True,
                    ),
                    "combined_regime": "range_normal_vol",
                    "session_regime": "ny_overlap",
                    "pred_hold_extension_delta_720m": 10.0,
                    "actual_taken_fixed_720m_adjusted_pnl": 12.0,
                }
            ]
        )

        trades, skipped = replay_group(
            frame,
            apply_mask=universe_mask(frame, "isolated_large_loss_long"),
            threshold=-5.0,
            horizon_mode="720",
            require_model_used=False,
            extension_veto_rule="holdext_long_range_normal_ny",
            profit_multiplier=1.0,
            loss_multiplier=1.2,
        )

        self.assertFalse(skipped)
        self.assertFalse(trades[0]["hold_extension_applied"])
        self.assertTrue(trades[0]["hold_extension_vetoed"])
        self.assertEqual(trades[0]["hold_extension_veto_reason"], "holdext_long_range_normal_ny")
        self.assertAlmostEqual(trades[0]["adjusted_pnl"], -3.0)

    def test_extension_veto_nonmatching_context_allows_extension(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    **row(
                        entry_minute=1,
                        exit_minute=2,
                        adjusted_pnl=-3.0,
                        pred_delta=0.0,
                        horizon=60,
                        fixed_pnl=8.0,
                        isolated_large_loss=True,
                    ),
                    "combined_regime": "trend_normal_vol",
                    "session_regime": "ny_overlap",
                    "pred_hold_extension_delta_720m": 10.0,
                    "actual_taken_fixed_720m_adjusted_pnl": 12.0,
                }
            ]
        )

        trades, skipped = replay_group(
            frame,
            apply_mask=universe_mask(frame, "isolated_large_loss_long"),
            threshold=-5.0,
            horizon_mode="720",
            require_model_used=False,
            extension_veto_rule="holdext_long_range_normal_ny",
            profit_multiplier=1.0,
            loss_multiplier=1.2,
        )

        self.assertFalse(skipped)
        self.assertTrue(trades[0]["hold_extension_applied"])
        self.assertFalse(trades[0]["hold_extension_vetoed"])
        self.assertAlmostEqual(trades[0]["adjusted_pnl"], 12.0)

    def test_selector_compatible_monthly_metrics_includes_nondefault_veto(self) -> None:
        monthly = pd.DataFrame(
            {
                "variant": ["loss_exit30_cd15"],
                "apply_universe": ["isolated_large_loss_long"],
                "threshold": [-5.0],
                "horizon_mode": ["720"],
                "extension_veto_rule": ["holdext_long_range_normal_ny"],
            }
        )

        output = selector_compatible_monthly_metrics(monthly)

        self.assertEqual(
            output["variant"].tolist(),
            [
                (
                    "loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720"
                    "__veto_holdext_long_range_normal_ny"
                )
            ],
        )

    def test_horizon_model_used_parses_bool_like_values(self) -> None:
        self.assertTrue(horizon_model_used(pd.Series({"pred_hold_extension_model_used_720m": "true"}), 720))
        self.assertFalse(horizon_model_used(pd.Series({"pred_hold_extension_model_used_720m": "false"}), 720))
        self.assertFalse(horizon_model_used(pd.Series({}), 720))

    def test_extension_veto_applies_to_long_range_normal_ny_720(self) -> None:
        self.assertTrue(
            extension_veto_applies(
                pd.Series(
                    {
                        "direction": "long",
                        "combined_regime": "range_normal_vol",
                        "session_regime": "ny_overlap",
                    }
                ),
                720,
                "holdext_long_range_normal_ny",
            )
        )
        self.assertFalse(
            extension_veto_applies(
                pd.Series(
                    {
                        "direction": "short",
                        "combined_regime": "range_normal_vol",
                        "session_regime": "ny_overlap",
                    }
                ),
                720,
                "holdext_long_range_normal_ny",
            )
        )


if __name__ == "__main__":
    unittest.main()
