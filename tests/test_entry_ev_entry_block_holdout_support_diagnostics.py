from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_entry_block_holdout_support_diagnostics import (
    blocked_trades,
    derive_base_variant,
    discovery_mask,
    summarize_by_role,
    summarize_holdout_support,
)


def overlay_row(
    *,
    role: str,
    family: str,
    pnl: float,
    blocked: bool,
    rule: str = "long_range_normal_ny_fixed60_pred_gt0",
    minute: int = 0,
) -> dict[str, object]:
    base_variant = "loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720"
    return {
        "source": "unit",
        "role": role,
        "family": family,
        "selector_variant": f"{base_variant}__entryblock_{rule}",
        "base_variant": base_variant,
        "candidate": "q95",
        "entry_block_rule": rule,
        "entry_blocked": blocked,
        "month": "2025-12",
        "entry_timestamp": f"2025-12-01 00:{minute:02d}:00+00:00",
        "direction": "long",
        "adjusted_pnl": pnl,
        "combined_regime": "range_normal_vol",
        "session_regime": "ny_overlap",
    }


class EntryEvEntryBlockHoldoutSupportDiagnosticsTest(unittest.TestCase):
    def test_derive_base_variant_strips_entryblock_suffix(self) -> None:
        self.assertEqual(
            derive_base_variant(
                "base__entryblock_long_range_normal_ny_fixed60_pred_gt0",
                "long_range_normal_ny_fixed60_pred_gt0",
            ),
            "base",
        )
        self.assertEqual(derive_base_variant("base", "none"), "base")

    def test_summarize_holdout_support_splits_discovery_and_holdout_effects(self) -> None:
        frame = pd.DataFrame(
            [
                overlay_row(role="refit2025_validation", family="refit2025", pnl=-5.0, blocked=True),
                overlay_row(role="refit2025_validation", family="refit2025", pnl=3.0, blocked=False),
                overlay_row(role="fresh2024_validation", family="fresh2024", pnl=2.0, blocked=True),
                overlay_row(role="fresh2024_validation", family="fresh2024", pnl=4.0, blocked=False),
            ]
        )
        discovery = discovery_mask(frame, roles=["refit2025_validation"], families=[], sources=[])

        summary = summarize_holdout_support(frame, discovery)
        rows = {
            row["scope"]: row
            for row in summary.to_dict(orient="records")
        }

        self.assertEqual(rows["discovery"]["blocked_trade_count"], 1)
        self.assertEqual(rows["discovery"]["blocked_loss_count"], 1)
        self.assertAlmostEqual(rows["discovery"]["pnl_delta_vs_input"], 5.0)
        self.assertEqual(rows["holdout"]["blocked_trade_count"], 1)
        self.assertEqual(rows["holdout"]["blocked_win_count"], 1)
        self.assertAlmostEqual(rows["holdout"]["pnl_delta_vs_input"], -2.0)
        self.assertEqual(rows["all"]["affected_role_count"], 2)

    def test_by_role_and_blocked_trades_keep_scope(self) -> None:
        frame = pd.DataFrame(
            [
                overlay_row(
                    role="refit2025_validation",
                    family="refit2025",
                    pnl=-5.0,
                    blocked=True,
                    minute=1,
                ),
                overlay_row(
                    role="fresh2024_validation",
                    family="fresh2024",
                    pnl=2.0,
                    blocked=True,
                    minute=2,
                ),
            ]
        )
        discovery = discovery_mask(frame, roles=["refit2025_validation"], families=[], sources=[])

        by_role = summarize_by_role(frame, discovery)
        self.assertEqual(set(by_role["scope"]), {"discovery", "holdout"})

        blocked = blocked_trades(frame, discovery)
        self.assertEqual(blocked["scope"].tolist(), ["discovery", "holdout"])


if __name__ == "__main__":
    unittest.main()
