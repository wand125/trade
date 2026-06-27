import argparse
import unittest

import pandas as pd

from trade_data.meta_model import (
    MetaModelConfig,
    add_meta_predictions,
    build_training_frame,
    filter_months,
    parse_csv_months,
    train_model,
)


def prediction_frame():
    return pd.DataFrame(
        {
            "long_best_adjusted_pnl": [10.0, 20.0, 5.0],
            "short_best_adjusted_pnl": [3.0, 4.0, 15.0],
            "pred_long_best_adjusted_pnl": [9.0, 18.0, 6.0],
            "pred_short_best_adjusted_pnl": [4.0, 5.0, 14.0],
            "pred_long_max_adverse_pnl": [-2.0, -3.0, -1.0],
            "pred_short_max_adverse_pnl": [-1.0, -2.0, -4.0],
            "pred_long_best_holding_minutes": [30.0, 60.0, 45.0],
            "pred_short_best_holding_minutes": [20.0, 40.0, 80.0],
            "pred_long_wait_regret": [1.0, 0.5, 2.0],
            "pred_short_wait_regret": [2.0, 1.0, 0.5],
            "pred_long_entry_local_rank": [0.8, 0.9, 0.4],
            "pred_short_entry_local_rank": [0.3, 0.4, 0.9],
            "pred_long_entry_urgency": [1.0, 2.0, -1.0],
            "pred_short_entry_urgency": [-1.0, 0.0, 2.0],
            "pred_long_profit_barrier_hit": [1, 1, 0],
            "pred_short_profit_barrier_hit": [0, 0, 1],
            "pred_long_wait_regret_quantile": [1, 0, 3],
            "pred_short_wait_regret_quantile": [3, 2, 0],
            "pred_long_entry_local_rank_bin": [4, 4, 1],
            "pred_short_entry_local_rank_bin": [1, 2, 4],
            "pred_best_adjusted_pnl_quantile": [2, 4, 3],
            "pred_side_score_quantile": [3, 4, 0],
            "pred_label": [1, 1, -1],
        }
    )


class MetaModelTests(unittest.TestCase):
    def test_parse_csv_months(self):
        self.assertEqual(parse_csv_months("2024-07,2024-09"), ["2024-07", "2024-09"])
        self.assertIsNone(parse_csv_months(None))

        with self.assertRaises(argparse.ArgumentTypeError):
            parse_csv_months("2024-13")

    def test_filter_months_uses_dataset_month(self):
        df = pd.DataFrame(
            {
                "dataset_month": ["2024-07", "2024-09", "2024-09"],
                "value": [1, 2, 3],
            }
        )

        filtered = filter_months(df, ["2024-09"], "test")

        self.assertEqual(filtered["value"].tolist(), [2, 3])

    def test_filter_months_rejects_missing_month(self):
        df = pd.DataFrame({"dataset_month": ["2024-07"], "value": [1]})

        with self.assertRaises(ValueError):
            filter_months(df, ["2024-09"], "test")

    def test_build_training_frame_expands_long_and_short_examples(self):
        frame = build_training_frame(prediction_frame())

        self.assertEqual(len(frame), 6)
        self.assertEqual(set(frame["side"].tolist()), {1.0, -1.0})
        self.assertIn("pred_side_ev", frame.columns)
        self.assertIn("target", frame.columns)

    def test_meta_model_adds_side_predictions(self):
        df = prediction_frame()
        frame = build_training_frame(df)
        config = MetaModelConfig(
            max_iter=2,
            learning_rate=0.1,
            max_leaf_nodes=3,
            min_samples_leaf=1,
            l2_regularization=0.0,
            random_seed=1,
            target_clip_quantile=1.0,
            entry_threshold=5.0,
        )

        model = train_model(frame, config)
        output = add_meta_predictions(df, model)

        self.assertIn("pred_meta_long_adjusted_pnl", output.columns)
        self.assertIn("pred_meta_short_adjusted_pnl", output.columns)
        self.assertFalse(output["pred_meta_long_adjusted_pnl"].isna().any())


if __name__ == "__main__":
    unittest.main()
