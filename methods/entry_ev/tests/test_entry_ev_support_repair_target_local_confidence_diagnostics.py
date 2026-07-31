from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_support_repair_target_local_confidence_diagnostics import (
    build_rule_specs,
    filter_targets,
    normalize_horizon_rows,
    rule_surface,
)


class EntryEvSupportRepairTargetLocalConfidenceDiagnosticsTest(unittest.TestCase):
    def test_filter_targets_uses_role_month_side_and_row_scope(self) -> None:
        rows = normalize_horizon_rows(
            pd.DataFrame(
                {
                    "family": ["f1", "f1", "f2"],
                    "role": ["r1", "r1", "r2"],
                    "month": ["2026-01", "2026-01", "2026-02"],
                    "side": ["long", "short", "long"],
                    "needed_side": ["long", "short", "long"],
                    "row_scope": ["available_candidates", "greedy_selected", "available_candidates"],
                    "selection_bucket": ["x", "y", "z"],
                    "decision_timestamp": [
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T00:05:00Z",
                        "2026-02-01T00:00:00Z",
                    ],
                    "horizon_minutes": [60, 60, 60],
                    "actual_pnl": [1.0, 2.0, 3.0],
                    "pred_executable_prob": [0.5, 0.5, 0.5],
                    "pred_pnl": [1.0, 1.0, 1.0],
                    "pred_tail_loss_prob": [0.1, 0.1, 0.1],
                    "pred_model_used": [False, True, True],
                }
            )
        )

        filtered = filter_targets(
            rows,
            targets=[("r1", "2026-01", "long")],
            row_scopes=["available_candidates"],
        )

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]["target_key"], "r1|2026-01|long")
        self.assertTrue(bool(filtered.iloc[0]["fallback_non_model_label"]))

    def test_rule_surface_summarizes_observable_rules(self) -> None:
        frame = normalize_horizon_rows(
            pd.DataFrame(
                {
                    "family": ["f1", "f1", "f1", "f1"],
                    "role": ["r1", "r1", "r1", "r1"],
                    "month": ["2026-01"] * 4,
                    "side": ["long"] * 4,
                    "needed_side": ["long"] * 4,
                    "row_scope": ["available_candidates"] * 4,
                    "selection_bucket": ["x"] * 4,
                    "decision_timestamp": [
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T00:05:00Z",
                        "2026-01-01T00:10:00Z",
                        "2026-01-01T00:15:00Z",
                    ],
                    "horizon_minutes": [60, 60, 240, 240],
                    "actual_pnl": [-2.0, 3.0, 5.0, -6.0],
                    "pred_executable_prob": [0.4, 0.8, 0.7, 0.2],
                    "pred_pnl": [-1.0, 2.0, -0.5, -3.0],
                    "pred_tail_loss_prob": [0.4, 0.2, 0.1, 0.8],
                    "pred_model_used": [False, False, False, False],
                    "entry_hour": [0, 0, 1, 1],
                }
            )
        )
        specs = build_rule_specs(
            frame,
            numeric_features=["pred_executable_prob", "pred_tail_loss_prob"],
            high_features=["pred_executable_prob"],
            low_features=["pred_tail_loss_prob"],
            max_thresholds_per_feature=3,
        )

        surface = rule_surface(frame, specs)

        self.assertIn("horizon_eq_240", set(surface["rule"]))
        best = surface.iloc[0]
        self.assertGreaterEqual(float(best["selected_actual_sum"]), 5.0)
        self.assertNotIn("actual", str(best["rule"]))


if __name__ == "__main__":
    unittest.main()
