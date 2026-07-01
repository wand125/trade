import argparse
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_common_loss_target_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_common_loss_target_diagnostics",
    SCRIPT_PATH,
)
entry_ev_common_loss_target_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_common_loss_target_diagnostics
SPEC.loader.exec_module(entry_ev_common_loss_target_diagnostics)


def row(
    *,
    variant: str,
    status: str,
    key: str,
    candidate: str,
    decision: str,
    pnl: float,
    risk: float,
    direction_error: bool,
) -> dict[str, object]:
    return {
        "variant": variant,
        "month": "2025-03",
        "candidate": candidate,
        "direction": "long" if "long" in key else "short",
        "entry_decision_timestamp": decision,
        "replacement_status": status,
        "_trade_key": key,
        "adjusted_pnl": pnl,
        "combined_regime": "range_normal_vol",
        "session_regime": "ny_overlap",
        "selected_side_support_bucket": "high",
        "selected_side_pressure_bucket": "low",
        "selected_side_prior_support_bucket": "high",
        "selected_side_feature_pressure_bucket": "low",
        "selected_side_prediction_source": "bucket",
        "selected_side_prior_pressure_risk": risk,
        "selected_side_score_delta": -1.5,
        "selected_side_base_score": 10.0,
        "selected_side_side_prior_score": 8.5,
        "selected_side_prior_downside_risk": 0.1,
        "selected_side_feature_pressure": 0.2,
        "selected_side_signed_drift": 0.05,
        "pred_taken_ev": 12.0,
        "pred_opposite_ev": 4.0,
        "pred_side_confidence_gap": 0.25,
        "pred_taken_best_holding_minutes": 180.0,
        "pred_taken_entry_local_rank": 0.9,
        "pred_taken_wait_regret": 1.0,
        "actual_taken_best_adjusted_pnl": 30.0,
        "exit_regret": 35.0,
        "best_side_regret": 10.0,
        "ev_overestimate_vs_realized": 22.0,
        "ev_overestimate_vs_oracle": 5.0,
        "direction_error": direction_error,
        "no_edge_entry": False,
    }


class EntryEvCommonLossTargetDiagnosticsTests(unittest.TestCase):
    def test_common_entry_targets_pair_base_and_candidate(self):
        combined = pd.DataFrame(
            [
                row(
                    variant="base",
                    status="common",
                    key="c1|2025-03|long|2025-03-01",
                    candidate="c1",
                    decision="2025-03-01T00:00:00Z",
                    pnl=5.0,
                    risk=0.1,
                    direction_error=False,
                ),
                row(
                    variant="side_prior",
                    status="common",
                    key="c1|2025-03|long|2025-03-01",
                    candidate="c1",
                    decision="2025-03-01T00:00:00Z",
                    pnl=-25.0,
                    risk=0.1,
                    direction_error=True,
                ),
            ]
        )
        normalized = entry_ev_common_loss_target_diagnostics.normalize_combined_trades(combined)
        targets = entry_ev_common_loss_target_diagnostics.build_common_entry_targets(
            normalized,
            base_label="base",
            candidate_label="side_prior",
            large_loss_threshold=-20.0,
            degradation_threshold=-5.0,
            low_risk_threshold=0.25,
            large_exit_regret_threshold=20.0,
            low_exit_capture_threshold=0.25,
            min_oracle_edge=5.0,
        )

        self.assertEqual(len(targets), 1)
        first = targets.iloc[0]
        self.assertAlmostEqual(first["base_adjusted_pnl"], 5.0)
        self.assertAlmostEqual(first["candidate_adjusted_pnl"], -25.0)
        self.assertAlmostEqual(first["same_entry_exit_delta"], -30.0)
        self.assertTrue(bool(first["common_large_loss_target"]))
        self.assertTrue(bool(first["common_degraded_target"]))
        self.assertTrue(bool(first["direction_side_inversion_target"]))
        self.assertTrue(bool(first["exit_capture_failure_target"]))
        self.assertTrue(bool(first["common_low_risk_large_loss_target"]))

    def test_build_diagnostics_writes_outputs(self):
        combined = pd.DataFrame(
            [
                row(
                    variant="base",
                    status="common",
                    key="c1|2025-03|long|2025-03-01",
                    candidate="c1",
                    decision="2025-03-01T00:00:00Z",
                    pnl=5.0,
                    risk=0.1,
                    direction_error=False,
                ),
                row(
                    variant="side_prior",
                    status="common",
                    key="c1|2025-03|long|2025-03-01",
                    candidate="c1",
                    decision="2025-03-01T00:00:00Z",
                    pnl=-25.0,
                    risk=0.1,
                    direction_error=True,
                ),
                row(
                    variant="side_prior",
                    status="only_side_prior",
                    key="c1|2025-03|short|2025-03-02",
                    candidate="c1",
                    decision="2025-03-02T00:00:00Z",
                    pnl=8.0,
                    risk=0.4,
                    direction_error=False,
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            combined_path = tmp_path / "combined.csv"
            combined.to_csv(combined_path, index=False)
            args = argparse.Namespace(
                combined_trades=combined_path,
                base_label="base",
                candidate_label="side_prior",
                large_loss_threshold=-20.0,
                degradation_threshold=-5.0,
                low_risk_threshold=0.25,
                large_exit_regret_threshold=20.0,
                low_exit_capture_threshold=0.25,
                min_oracle_edge=5.0,
                prior_strength=5.0,
                min_group_support=1,
                output_dir=tmp_path,
                label="unit_common_loss_targets",
            )

            run_dir = entry_ev_common_loss_target_diagnostics.build_diagnostics(args)
            common = pd.read_csv(run_dir / "common_entry_targets.csv")
            replacement = pd.read_csv(run_dir / "replacement_targets.csv")
            summary = pd.read_csv(run_dir / "common_target_summary.csv")

            self.assertEqual(len(common), 1)
            self.assertEqual(len(replacement), 1)
            self.assertIn("common_large_loss_target", set(summary["target"]))


if __name__ == "__main__":
    unittest.main()
