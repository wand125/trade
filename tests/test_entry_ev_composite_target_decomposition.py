import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_composite_target_decomposition.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_composite_target_decomposition",
    SCRIPT_PATH,
)
entry_ev_composite_target_decomposition = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_composite_target_decomposition
SPEC.loader.exec_module(entry_ev_composite_target_decomposition)


def trade(
    *,
    candidate="c1",
    role="fresh",
    month="2024-03",
    pnl=5.0,
    best=10.0,
    prior_count=4,
    support=0.8,
    risk=0.1,
    interaction=0.001,
    direction_error=False,
    exit_regret=2.0,
    ev_overestimate=0.0,
):
    return {
        "candidate": candidate,
        "role": role,
        "month": month,
        "direction": "long",
        "entry_decision_timestamp": f"{month}-05T00:00:00Z",
        "adjusted_pnl": pnl,
        "actual_taken_best_adjusted_pnl": best,
        "pred_taken_ev": pnl + ev_overestimate,
        "ev_overestimate_vs_realized": ev_overestimate,
        "exit_regret": exit_regret,
        "prior_trade_count": prior_count,
        "prior_month_count": 1,
        "prior_downside_support_weight": support,
        "prior_downside_risk_score": risk,
        "side_balance_downside_interaction_score": interaction,
        "side_balance_signed_drift_for_trade": interaction / max(risk, 0.001),
        "side_balance_abs_signed_drift_for_trade": abs(interaction / max(risk, 0.001)),
        "side_balance_selected_side_overrepresented": False,
        "side_balance_selected_side_underrepresented": True,
        "direction_error": direction_error,
        "no_edge_entry": False,
    }


class EntryEvCompositeTargetDecompositionTests(unittest.TestCase):
    def test_component_targets_separate_features_from_realized_labels(self):
        frame = pd.DataFrame(
            [
                trade(
                    candidate="bad",
                    pnl=-2.0,
                    best=20.0,
                    prior_count=0,
                    support=0.0,
                    risk=0.4,
                    interaction=0.02,
                    direction_error=True,
                    exit_regret=15.0,
                    ev_overestimate=14.0,
                ),
                trade(candidate="good", pnl=8.0, best=10.0),
            ]
        )
        enriched = entry_ev_composite_target_decomposition.add_component_features_and_targets(
            frame,
            risk_threshold=0.2,
            interaction_threshold=0.005,
            min_prior_support_weight=0.1,
            large_exit_regret_threshold=10.0,
            low_exit_capture_threshold=0.5,
            min_oracle_edge=5.0,
            ev_overestimate_threshold=10.0,
        )

        bad = enriched[enriched["candidate"].eq("bad")].iloc[0]
        good = enriched[enriched["candidate"].eq("good")].iloc[0]

        self.assertTrue(bool(bad["missing_prior_support_feature"]))
        self.assertTrue(bool(bad["direction_side_inversion_target"]))
        self.assertTrue(bool(bad["large_exit_regret_target"]))
        self.assertTrue(bool(bad["low_exit_capture_target"]))
        self.assertTrue(bool(bad["executable_ev_overestimate_target"]))
        self.assertTrue(bool(bad["composite_failure_target"]))
        self.assertEqual(bad["support_bucket"], "missing")
        self.assertEqual(bad["pressure_bucket"], "extreme")

        self.assertFalse(bool(good["missing_prior_support_feature"]))
        self.assertFalse(bool(good["direction_side_inversion_target"]))
        self.assertFalse(bool(good["exit_capture_failure_target"]))
        self.assertFalse(bool(good["executable_ev_overestimate_target"]))
        self.assertFalse(bool(good["realized_loss_target"]))

    def test_summaries_report_target_rates_and_overlap(self):
        frame = pd.DataFrame(
            [
                trade(candidate="c1", role="fresh", pnl=-2.0, best=3.0, direction_error=True),
                trade(candidate="c1", role="fresh", pnl=6.0, exit_regret=12.0),
                trade(candidate="c2", role="refit", pnl=7.0),
            ]
        )
        enriched = entry_ev_composite_target_decomposition.add_component_features_and_targets(
            frame,
            risk_threshold=0.2,
            interaction_threshold=0.005,
            min_prior_support_weight=0.1,
            large_exit_regret_threshold=10.0,
            low_exit_capture_threshold=0.5,
            min_oracle_edge=5.0,
            ev_overestimate_threshold=10.0,
        )
        candidate_summary = entry_ev_composite_target_decomposition.summarize_by_columns(
            enriched,
            ["candidate"],
        )
        overlap = entry_ev_composite_target_decomposition.summarize_target_overlap(enriched)

        c1 = candidate_summary[candidate_summary["candidate"].eq("c1")].iloc[0]
        self.assertEqual(c1["trade_count"], 2)
        self.assertAlmostEqual(c1["direction_side_inversion_target_rate"], 0.5)
        self.assertAlmostEqual(c1["exit_capture_failure_target_rate"], 0.5)
        self.assertIn(
            "direction_side_inversion",
            "\n".join(overlap["target_overlap_key"].astype(str).tolist()),
        )


if __name__ == "__main__":
    unittest.main()
