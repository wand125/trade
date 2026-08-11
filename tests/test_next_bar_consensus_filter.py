import unittest

import numpy as np
import pandas as pd

from trade_data.next_bar_consensus_filter import (
    ComponentConsensusFilterConfig,
    apply_component_consensus_filter,
)


def consensus_frame() -> pd.DataFrame:
    timestamp = pd.date_range("2020-01-01", periods=4, freq="15min", tz="UTC")
    return pd.DataFrame(
        {
            "fold": ["test2020"] * 4,
            "timestamp": timestamp,
            "decision_timestamp": timestamp,
            "target_timestamp": timestamp + pd.Timedelta(minutes=15),
            "target_up": [1, 0, 1, 0],
            "reference_probability_up": [0.54, 0.46, 0.55, 0.45],
            "reference_predicted_up": [1, 0, 1, 0],
            "reference_correct": [True, True, True, True],
            "reference_candidate_probability_up": [0.60, 0.40, 0.60, 0.60],
            "shape_candidate_probability_up": [0.60, 0.40, 0.40, 0.60],
            "profile_candidate_probability_up": [0.60, 0.60, 0.40, 0.40],
        }
    )


class NextBarConsensusFilterTests(unittest.TestCase):
    def test_majority_and_unanimous_support_are_exact_and_direction_preserving(self):
        source = consensus_frame()
        majority = apply_component_consensus_filter(
            source, ComponentConsensusFilterConfig(minimum_support=2)
        )
        unanimous = apply_component_consensus_filter(
            source, ComponentConsensusFilterConfig(minimum_support=3)
        )
        self.assertEqual(majority["consensus_support_count"].tolist(), [3, 2, 1, 1])
        self.assertEqual(
            majority["component_consensus_selected"].tolist(),
            [True, True, False, False],
        )
        self.assertEqual(
            unanimous["component_consensus_selected"].tolist(),
            [True, False, False, False],
        )
        for frame in (majority, unanimous):
            self.assertTrue(
                frame["probability_up"].ge(0.5).astype("int8").equals(
                    frame["predicted_up"].astype("int8")
                )
            )
            np.testing.assert_allclose(
                frame["probability_up"] + frame["probability_down"], 1
            )
            np.testing.assert_allclose(
                frame["confidence"],
                np.maximum(frame["probability_up"], frame["probability_down"]),
            )
            self.assertTrue(frame["correct"].equals(frame["reference_correct"]))

    def test_target_changes_do_not_change_consensus_or_probability(self):
        source = consensus_frame()
        original = apply_component_consensus_filter(
            source, ComponentConsensusFilterConfig(minimum_support=2)
        )
        changed = source.copy()
        changed["target_up"] = 1 - changed["target_up"]
        changed["reference_correct"] = changed["reference_predicted_up"].eq(
            changed["target_up"]
        )
        modified = apply_component_consensus_filter(
            changed, ComponentConsensusFilterConfig(minimum_support=2)
        )
        self.assertTrue(
            original["component_consensus_selected"].equals(
                modified["component_consensus_selected"]
            )
        )
        np.testing.assert_allclose(
            original["probability_up"], modified["probability_up"]
        )

    def test_invalid_support_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "minimum_support"):
            apply_component_consensus_filter(
                consensus_frame(),
                ComponentConsensusFilterConfig(minimum_support=1),
            )


if __name__ == "__main__":
    unittest.main()
