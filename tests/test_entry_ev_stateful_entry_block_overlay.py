from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_stateful_entry_block_overlay import (
    attach_features,
    entry_block_mask,
    summarize_overlay,
)


def stateful_row(
    *,
    direction: str,
    entry_minute: int,
    pnl: float,
    month: str = "2025-12",
    hold_extension_applied: bool = False,
    holding_minutes: float = 1.0,
) -> dict[str, object]:
    start = pd.Timestamp("2025-12-01 00:00:00+00:00")
    entry_time = start + pd.Timedelta(minutes=entry_minute)
    return {
        "source": "unit",
        "role": "unit_role",
        "family": "unit_family",
        "variant": "loss_exit30_cd15",
        "candidate": "q95",
        "month": month,
        "apply_universe": "isolated_large_loss_long",
        "threshold": -5.0,
        "horizon_mode": "720",
        "direction": direction,
        "entry_timestamp": entry_time,
        "entry_decision_timestamp": entry_time - pd.Timedelta(minutes=1),
        "exit_timestamp": entry_time + pd.Timedelta(minutes=holding_minutes),
        "adjusted_pnl": pnl,
        "holding_minutes": holding_minutes,
        "hold_extension_applied": hold_extension_applied,
    }


def feature_row(
    *,
    direction: str,
    entry_minute: int,
    session: str,
    combined: str,
    loss_first: float,
    side_gap: float,
    entry_rank: float,
) -> dict[str, object]:
    row = stateful_row(direction=direction, entry_minute=entry_minute, pnl=0.0)
    return {
        key: row[key]
        for key in [
            "source",
            "role",
            "family",
            "variant",
            "candidate",
            "month",
            "direction",
            "entry_timestamp",
        ]
    } | {
        "session_regime": session,
        "combined_regime": combined,
        "volatility_regime": "high_vol" if "high_vol" in combined else "low_vol",
        "entry_hour": 23,
        "selected_loss_first_prob": loss_first,
        "pred_side_confidence_gap": side_gap,
        "pred_taken_entry_local_rank": entry_rank,
    }


class EntryEvStatefulEntryBlockOverlayTest(unittest.TestCase):
    def test_entry_block_mask_supports_focus_rule(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "direction": "short",
                    "session_regime": "rollover",
                    "combined_regime": "down_high_vol",
                    "volatility_regime": "high_vol",
                    "entry_hour": 23,
                    "selected_loss_first_prob": 0.44,
                    "pred_side_confidence_gap": -0.01,
                    "pred_taken_entry_local_rank": 0.4,
                },
                {
                    "direction": "short",
                    "session_regime": "rollover",
                    "combined_regime": "range_high_vol",
                    "volatility_regime": "high_vol",
                    "entry_hour": 23,
                    "selected_loss_first_prob": 0.2,
                    "pred_side_confidence_gap": 0.1,
                    "pred_taken_entry_local_rank": 0.7,
                },
            ]
        )

        self.assertEqual(
            entry_block_mask(frame, "short_rollover_sidegap_neg_lossprob_ge0p4").tolist(),
            [True, False],
        )

    def test_entry_block_mask_supports_residual_floor_rules(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "direction": "short",
                    "session_regime": "london",
                    "combined_regime": "range_low_vol",
                    "volatility_regime": "low_vol",
                    "selected_loss_first_prob": 0.4,
                    "pred_side_confidence_gap": 0.1,
                    "pred_taken_entry_local_rank": 0.5,
                    "entry_hour": 9,
                    "holding_minutes": 1.0,
                    "hold_extension_applied": False,
                },
                {
                    "direction": "long",
                    "session_regime": "ny_overlap",
                    "combined_regime": "range_normal_vol",
                    "volatility_regime": "normal_vol",
                    "selected_loss_first_prob": 0.2,
                    "pred_side_confidence_gap": 0.1,
                    "pred_taken_entry_local_rank": 0.5,
                    "entry_hour": 15,
                    "holding_minutes": 720.0,
                    "hold_extension_applied": True,
                },
                {
                    "direction": "long",
                    "session_regime": "ny_overlap",
                    "combined_regime": "range_normal_vol",
                    "volatility_regime": "normal_vol",
                    "selected_loss_first_prob": 0.2,
                    "pred_side_confidence_gap": 0.1,
                    "pred_taken_entry_local_rank": 0.5,
                    "entry_hour": 15,
                    "holding_minutes": 1.0,
                    "hold_extension_applied": False,
                },
                {
                    "direction": "short",
                    "session_regime": "rollover",
                    "combined_regime": "down_high_vol",
                    "volatility_regime": "high_vol",
                    "selected_loss_first_prob": 0.44,
                    "pred_side_confidence_gap": 0.1,
                    "pred_taken_entry_local_rank": 0.5,
                    "entry_hour": 23,
                    "holding_minutes": 1.0,
                    "hold_extension_applied": False,
                },
            ]
        )

        self.assertEqual(
            entry_block_mask(frame, "short_london_midloss_sidegap_pos").tolist(),
            [True, False, False, False],
        )
        self.assertEqual(
            entry_block_mask(frame, "holdext_long_range_normal_ny").tolist(),
            [False, True, False, False],
        )
        self.assertEqual(
            entry_block_mask(frame, "short_london_midloss_or_holdext_range_ny").tolist(),
            [True, True, False, False],
        )
        self.assertEqual(
            entry_block_mask(
                frame,
                "short_rollover_or_london_midloss_or_holdext_range_ny",
            ).tolist(),
            [True, True, False, True],
        )

    def test_summarize_overlay_blocks_matching_trade(self) -> None:
        stateful = pd.DataFrame(
            [
                stateful_row(direction="short", entry_minute=1, pnl=-4.0),
                stateful_row(direction="long", entry_minute=5, pnl=1.0),
            ]
        )
        features = pd.DataFrame(
            [
                feature_row(
                    direction="short",
                    entry_minute=1,
                    session="rollover",
                    combined="down_high_vol",
                    loss_first=0.44,
                    side_gap=-0.01,
                    entry_rank=0.4,
                ),
                feature_row(
                    direction="long",
                    entry_minute=5,
                    session="asia",
                    combined="range_high_vol",
                    loss_first=0.1,
                    side_gap=0.1,
                    entry_rank=0.8,
                ),
            ]
        )
        annotated = attach_features(stateful, features)

        trades, monthly = summarize_overlay(
            annotated,
            ["short_rollover_lossprob_ge0p4"],
        )

        self.assertEqual(trades["entry_blocked"].tolist(), [True, False])
        self.assertEqual(int(monthly["blocked_trade_count"].iloc[0]), 1)
        self.assertAlmostEqual(monthly["blocked_adjusted_pnl"].iloc[0], -4.0)
        self.assertAlmostEqual(monthly["total_adjusted_pnl"].iloc[0], 1.0)
        self.assertIn("__entryblock_short_rollover_lossprob_ge0p4", monthly["variant"].iloc[0])


if __name__ == "__main__":
    unittest.main()
