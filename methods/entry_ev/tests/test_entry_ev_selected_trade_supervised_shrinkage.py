import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_selected_trade_supervised_shrinkage.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_selected_trade_supervised_shrinkage",
    SCRIPT_PATH,
)
entry_ev_selected_trade_supervised_shrinkage = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_selected_trade_supervised_shrinkage
SPEC.loader.exec_module(entry_ev_selected_trade_supervised_shrinkage)


class EntryEvSelectedTradeSupervisedShrinkageTests(unittest.TestCase):
    def trade_frame(self):
        return pd.DataFrame(
            {
                "family": ["fam", "fam", "fam"],
                "role": ["cal", "fresh", "refit"],
                "month": ["2024-01", "2024-02", "2024-03"],
                "candidate": ["q95", "q95", "q95"],
                "selector_variant": ["v1", "v1", "v2"],
                "direction": ["long", "long", "short"],
                "entry_decision_timestamp": [
                    "2024-01-10T00:00:00Z",
                    "2024-02-10T00:00:00Z",
                    "2024-03-10T00:00:00Z",
                ],
                "adjusted_pnl": [2.0, 4.0, -3.0],
                "pred_taken_ev": [10.0, 10.0, 10.0],
                "pred_side_confidence_gap": [0.1, 0.2, 0.3],
                "entry_blocked": [False, True, False],
                "combined_regime": ["range", "range", "down"],
                "session_regime": ["asia", "asia", "london"],
            }
        )

    def test_chronological_predictions_use_prior_months_only(self):
        frame = entry_ev_selected_trade_supervised_shrinkage.normalize_trade_frame(
            self.trade_frame(),
            candidates=set(),
            selector_variants=set(),
            roles=set(),
            months=set(),
            exclude_entry_blocked=False,
        )
        scored, folds = entry_ev_selected_trade_supervised_shrinkage.chronological_predictions(
            frame,
            target_modes=["pnl", "factor"],
            numeric_features=["pred_taken_ev", "pred_side_confidence_gap"],
            categorical_features=["direction", "combined_regime", "session_regime"],
            min_train_months=1,
            min_train_rows=1,
            max_train_rows=0,
            max_iter=5,
            learning_rate=0.1,
            max_leaf_nodes=3,
            min_samples_leaf=20,
            l2_regularization=0.0,
            random_seed=1,
            default_pnl=0.0,
            default_factor=0.0,
            min_factor=-1.0,
            max_factor=1.0,
        )

        feb_pnl = scored[
            scored["supervised_target_mode"].eq("pnl")
            & scored["month"].eq("2024-02")
        ].iloc[0]
        feb_factor = scored[
            scored["supervised_target_mode"].eq("factor")
            & scored["month"].eq("2024-02")
        ].iloc[0]
        jan_pnl = scored[
            scored["supervised_target_mode"].eq("pnl")
            & scored["month"].eq("2024-01")
        ].iloc[0]
        feb_fold = folds[folds["target_mode"].eq("pnl") & folds["fold"].eq("2024-02")].iloc[0]

        self.assertEqual(jan_pnl["pred_supervised_pnl_ev"], 0.0)
        self.assertEqual(feb_pnl["pred_supervised_pnl_ev"], 2.0)
        self.assertEqual(feb_factor["pred_supervised_factor_ev"], 2.0)
        self.assertEqual(feb_fold["train_rows"], 1)
        self.assertEqual(feb_fold["train_months"], 1)

    def test_normalize_trade_frame_filters_selector_variant_and_entry_blocked(self):
        frame = entry_ev_selected_trade_supervised_shrinkage.normalize_trade_frame(
            self.trade_frame(),
            candidates={"q95"},
            selector_variants={"v1"},
            roles=set(),
            months=set(),
            exclude_entry_blocked=True,
        )

        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.iloc[0]["selector_variant"], "v1")
        self.assertEqual(frame.iloc[0]["month"], "2024-01")

    def test_threshold_summary_reports_removed_pnl(self):
        frame = pd.DataFrame(
            {
                "supervised_target_mode": ["pnl", "pnl", "pnl"],
                "adjusted_pnl": [-5.0, 3.0, -2.0],
                "score": [-1.0, 4.0, 2.0],
            }
        )

        summary = entry_ev_selected_trade_supervised_shrinkage.threshold_summary(
            frame,
            score_columns=["score"],
            thresholds=[0.0, 3.0],
            group_columns=["supervised_target_mode"],
        )
        zero = summary[summary["threshold"].eq(0.0)].iloc[0]
        three = summary[summary["threshold"].eq(3.0)].iloc[0]

        self.assertEqual(zero["flagged_trade_count"], 1)
        self.assertEqual(zero["flagged_pnl"], -5.0)
        self.assertEqual(zero["kept_pnl_if_removed"], 1.0)
        self.assertEqual(three["flagged_trade_count"], 2)
        self.assertEqual(three["flagged_loss_precision"], 1.0)


if __name__ == "__main__":
    unittest.main()
