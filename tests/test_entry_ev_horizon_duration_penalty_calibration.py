from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_horizon_duration_penalty_calibration import (
    calibrate_penalty_weights,
    choose_row_horizons,
)


def base_choice_frame() -> pd.DataFrame:
    rows = []
    for month, actual_60, actual_720 in [
        ("2026-01", 3.0, -10.0),
        ("2026-02", 2.0, -8.0),
    ]:
        for horizon, pred_pnl, actual in [
            (60, 0.5, actual_60),
            (720, 4.0, actual_720),
        ]:
            rows.append(
                {
                    "row_scope": "available_candidates",
                    "prob_threshold": 0.5,
                    "ev_threshold": 0.0,
                    "tail_prob_threshold": 0.3,
                    "require_model_used": True,
                    "role": "r",
                    "family": "f",
                    "month": month,
                    "side": "long",
                    "decision_timestamp": pd.Timestamp(f"{month}-01T00:00:00Z"),
                    "hv_chosen_horizon_minutes": float(horizon),
                    "support_reduction_value": 1.0,
                    "repair_expected_pnl": pred_pnl,
                    "repair_tail_penalty": 0.1,
                    "repair_horizon_penalty": horizon / 60.0,
                    "actual_pnl_at_hv_chosen_horizon": actual,
                }
            )
    return pd.DataFrame(rows)


class EntryEvHorizonDurationPenaltyCalibrationTest(unittest.TestCase):
    def test_choose_row_horizons_uses_penalty_to_prefer_shorter_horizon(self) -> None:
        frame = base_choice_frame()
        jan = frame[frame["month"].eq("2026-01")]

        no_penalty = choose_row_horizons(jan, penalty_weight=0.0)
        strong_penalty = choose_row_horizons(jan, penalty_weight=0.5)

        self.assertEqual(int(no_penalty.iloc[0]["hv_chosen_horizon_minutes"]), 720)
        self.assertEqual(int(strong_penalty.iloc[0]["hv_chosen_horizon_minutes"]), 60)

    def test_calibrate_penalty_weights_uses_only_prior_months(self) -> None:
        frame = base_choice_frame()

        calibrated, metrics, choices = calibrate_penalty_weights(
            frame,
            penalty_weights=[0.0, 0.5],
            fallback_weight=0.0,
            min_prior_rows=1,
            min_prior_months=1,
        )

        jan_weight = calibrated[calibrated["month"].eq("2026-01")][
            "repair_horizon_penalty_weight_effective"
        ].unique()
        feb_weight = calibrated[calibrated["month"].eq("2026-02")][
            "repair_horizon_penalty_weight_effective"
        ].unique()

        self.assertEqual(jan_weight.tolist(), [0.0])
        self.assertEqual(feb_weight.tolist(), [0.5])
        self.assertEqual(len(metrics), 4)
        feb_choice = choices[choices["target_month"].eq("2026-02")].iloc[0]
        self.assertEqual(float(feb_choice["chosen_penalty_weight"]), 0.5)
        self.assertEqual(feb_choice["choice_reason"], "prior_best")


if __name__ == "__main__":
    unittest.main()
