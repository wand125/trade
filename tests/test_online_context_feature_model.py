from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "online_context_feature_model.py"
)
SPEC = importlib.util.spec_from_file_location("online_context_feature_model", SCRIPT_PATH)
online_context_feature_model = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = online_context_feature_model
SPEC.loader.exec_module(online_context_feature_model)


class OnlineContextFeatureModelTests(unittest.TestCase):
    def test_run_experiment_scores_only_future_months(self):
        rows = []
        for month_index, month in enumerate(["2025-01", "2025-02", "2025-03", "2025-04"]):
            for trade_index in range(6):
                direction = "long" if trade_index % 2 == 0 else "short"
                loss_trade = trade_index in {1, 4}
                adjusted_pnl = -20.0 if loss_trade else 8.0 + month_index
                rows.append(
                    {
                        "direction": direction,
                        "entry_decision_timestamp": f"{month}-{trade_index + 1:02d}T00:00:00Z",
                        "adjusted_pnl": adjusted_pnl,
                        "entry_month": month,
                        "entry_margin": 12.0 - trade_index,
                        "pred_taken_score": 20.0 - trade_index,
                        "pred_opposite_score": float(trade_index),
                        "pred_taken_score_gap": 20.0 - (2 * trade_index),
                        "pred_best_side_prob_1": 0.60,
                        "pred_best_side_prob_-1": 0.40,
                        "combined_regime": "range_normal_vol",
                        "session_regime": "london",
                        "prior_context_pnl": -30.0 if loss_trade else 15.0,
                        "prior_context_trade_count": trade_index,
                        "prior_context_win_rate": 0.25 if loss_trade else 0.75,
                        "prior_side_month_pnl": -20.0 if loss_trade else 20.0,
                        "prior_side_month_trade_count": trade_index,
                        "minutes_since_context_last_exit": 30.0 * trade_index,
                        "prior_context_active_loss_breach_20": loss_trade,
                        "prior_context_ever_breached_20": loss_trade,
                        "minutes_since_context_breach_20": 10.0 if loss_trade else None,
                        "prior_side_month_active_loss_breach_20": loss_trade,
                        "prior_side_month_ever_breached_20": loss_trade,
                        "prior_context_active_loss_breach_40": False,
                        "prior_context_ever_breached_40": False,
                        "minutes_since_context_breach_40": None,
                        "prior_side_month_active_loss_breach_40": False,
                        "prior_side_month_ever_breached_40": False,
                        "prior_context_active_loss_breach_60": False,
                        "prior_context_ever_breached_60": False,
                        "minutes_since_context_breach_60": None,
                        "prior_side_month_active_loss_breach_60": False,
                        "prior_side_month_ever_breached_60": False,
                        "prior_context_pnl_bucket": "-60..-20" if loss_trade else "0..60",
                        "prior_context_trade_count_bucket": "4+" if trade_index >= 4 else "2-3",
                        "entry_margin_bucket": "5..10",
                        "minutes_since_breach20_bucket": "<=60" if loss_trade else "none",
                        "source_run": f"run_{month}",
                    }
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            trades_path = root / "trades.csv"
            pd.DataFrame(rows).to_csv(trades_path, index=False)

            with redirect_stdout(io.StringIO()):
                run_dir = online_context_feature_model.run_experiment(
                    trades_path=trades_path,
                    output_dir=root,
                    label="feature_model_test",
                    min_train_months=2,
                    large_loss_threshold=-15.0,
                    risk_quantiles=(0.5,),
                    max_iter=5,
                    learning_rate=0.1,
                    max_leaf_nodes=3,
                    min_samples_leaf=1,
                    l2_regularization=0.0,
                    random_seed=7,
                )

            scored = pd.read_csv(run_dir / "oof_predictions.csv")
            self.assertEqual(set(scored["entry_month"].astype(str)), {"2025-03", "2025-04"})
            self.assertEqual(set(scored["feature_set"]), {"base", "context"})
            self.assertIn("pred_large_loss_risk", scored.columns)

            folds = pd.read_csv(run_dir / "fold_summary.csv")
            march_folds = folds[folds["target_month"].eq("2025-03")]
            self.assertTrue((march_folds["train_month_count"] == 2).all())
            april_folds = folds[folds["target_month"].eq("2025-04")]
            self.assertTrue((april_folds["train_month_count"] == 3).all())

            filters = pd.read_csv(run_dir / "risk_filter_summary.csv")
            self.assertFalse(filters.empty)
            self.assertIn("delta_vs_baseline", filters.columns)


if __name__ == "__main__":
    unittest.main()
