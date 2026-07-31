from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_trade_set_delta_diagnostics import (
    compare_blocked_sets,
    compare_rule_trade_sets,
    read_trade_set,
)


class EntryEvTradeSetDeltaDiagnosticsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.key_columns = [
            "role",
            "family",
            "candidate",
            "direction",
            "entry_decision_timestamp",
        ]
        self.context_columns = [
            "role",
            "family",
            "month",
            "direction",
            "combined_regime",
            "session_regime",
            "entry_block_rule",
        ]

    def test_compare_rule_trade_sets_splits_added_removed_and_changed(self) -> None:
        left = pd.DataFrame(
            {
                "role": ["r", "r", "r"],
                "family": ["f", "f", "f"],
                "candidate": ["c", "c", "c"],
                "direction": ["long", "long", "short"],
                "entry_decision_timestamp": pd.to_datetime(
                    ["2026-01-01T00:00Z", "2026-01-02T00:00Z", "2026-01-03T00:00Z"],
                    utc=True,
                ),
                "month": ["2026-01", "2026-01", "2026-01"],
                "combined_regime": ["range", "range", "down"],
                "session_regime": ["ny", "ny", "asia"],
                "entry_block_rule": ["none", "none", "none"],
                "entry_blocked": [False, False, False],
                "adjusted_pnl": [1.0, -2.0, 3.0],
            }
        )
        right = pd.DataFrame(
            {
                "role": ["r", "r", "r"],
                "family": ["f", "f", "f"],
                "candidate": ["c", "c", "c"],
                "direction": ["long", "short", "long"],
                "entry_decision_timestamp": pd.to_datetime(
                    ["2026-01-01T00:00Z", "2026-01-03T00:00Z", "2026-01-04T00:00Z"],
                    utc=True,
                ),
                "month": ["2026-01", "2026-01", "2026-01"],
                "combined_regime": ["range", "down", "up"],
                "session_regime": ["ny", "asia", "london"],
                "entry_block_rule": ["none", "none", "none"],
                "entry_blocked": [False, False, False],
                "adjusted_pnl": [1.5, 3.0, 4.0],
            }
        )

        delta, summary = compare_rule_trade_sets(
            left,
            right,
            key_columns=self.key_columns,
            context_columns=self.context_columns,
            rule="none",
        )

        self.assertEqual(summary["added_count"], 1)
        self.assertEqual(summary["removed_count"], 1)
        self.assertEqual(summary["common_changed_count"], 1)
        self.assertEqual(summary["common_same_count"], 1)
        self.assertAlmostEqual(summary["delta_pnl"], 6.5)
        by_status = delta.groupby("change_status")["delta_adjusted_pnl"].sum().to_dict()
        self.assertAlmostEqual(by_status["added"], 4.0)
        self.assertAlmostEqual(by_status["removed"], 2.0)
        self.assertAlmostEqual(by_status["common_changed"], 0.5)

    def test_compare_blocked_sets_tracks_removed_blocked_rows(self) -> None:
        left = pd.DataFrame(
            {
                "role": ["r", "r"],
                "family": ["f", "f"],
                "candidate": ["c", "c"],
                "direction": ["long", "short"],
                "entry_decision_timestamp": pd.to_datetime(
                    ["2026-01-01T00:00Z", "2026-01-02T00:00Z"],
                    utc=True,
                ),
                "month": ["2026-01", "2026-01"],
                "combined_regime": ["range", "down"],
                "session_regime": ["ny", "asia"],
                "entry_block_rule": ["rule", "rule"],
                "entry_blocked": [True, True],
                "adjusted_pnl": [-2.0, -3.0],
            }
        )
        right = left.iloc[[0]].copy()

        blocked = compare_blocked_sets(
            left,
            right,
            key_columns=self.key_columns,
            context_columns=self.context_columns,
            rule="rule",
        )

        self.assertEqual(blocked["blocked_status"].tolist(), ["blocked_common", "blocked_removed"])
        removed = blocked[blocked["blocked_status"].eq("blocked_removed")].iloc[0]
        self.assertEqual(removed["left_blocked_pnl"], -3.0)
        self.assertEqual(removed["right_blocked_pnl"], 0.0)

    def test_read_trade_set_filters_selector_and_rule(self) -> None:
        with self.subTest("filters rows"):
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "entry_block_overlay_trades.csv"
                pd.DataFrame(
                    {
                        "role": ["r", "r"],
                        "family": ["f", "f"],
                        "candidate": ["c", "c"],
                        "direction": ["long", "long"],
                        "entry_decision_timestamp": [
                            "2026-01-01T00:00Z",
                            "2026-01-02T00:00Z",
                        ],
                        "entry_block_rule": ["keep", "drop"],
                        "selector_variant": ["abc_target", "abc_target"],
                        "entry_blocked": [False, False],
                        "adjusted_pnl": [1.0, 2.0],
                    }
                ).to_csv(path, index=False)

                output = read_trade_set(
                    Path(tmp),
                    label="x",
                    key_columns=self.key_columns,
                    entry_block_rules=["keep"],
                    selector_variant_contains="target",
                )

                self.assertEqual(len(output), 1)
                self.assertEqual(output["entry_block_rule"].iloc[0], "keep")


if __name__ == "__main__":
    unittest.main()
