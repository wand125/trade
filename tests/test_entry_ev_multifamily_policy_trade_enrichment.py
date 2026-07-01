import argparse
import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_multifamily_policy_trade_enrichment.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_multifamily_policy_trade_enrichment",
    SCRIPT_PATH,
)
entry_ev_multifamily_policy_trade_enrichment = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_multifamily_policy_trade_enrichment
SPEC.loader.exec_module(entry_ev_multifamily_policy_trade_enrichment)


def trade_row(decision_time: str, direction: str, pnl: float) -> dict[str, object]:
    entry_decision = pd.Timestamp(decision_time, tz="UTC")
    entry = entry_decision + pd.Timedelta(minutes=1)
    exit_time = entry + pd.Timedelta(minutes=60)
    return {
        "direction": direction,
        "entry_timestamp": entry,
        "exit_timestamp": exit_time,
        "entry_price": 100.0,
        "exit_price": 100.0 + pnl,
        "raw_pnl": pnl,
        "adjusted_pnl": pnl,
        "holding_minutes": 60.0,
        "exit_reason": "signal_close",
        "entry_decision_timestamp": entry_decision,
        "exit_decision_timestamp": exit_time - pd.Timedelta(minutes=1),
    }


def prediction_frame(
    *,
    decision_time: str,
    regime: str,
    long_ev_risk: float,
    short_ev_risk: float,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "decision_timestamp": pd.to_datetime([decision_time], utc=True),
            "dataset_month": ["2024-01"],
            "trend_regime": ["range"],
            "volatility_regime": ["normal_vol"],
            "session_regime": ["asia"],
            "gap_regime": ["flat_gap"],
            "combined_regime": [regime],
            "long_best_adjusted_pnl": [20.0],
            "short_best_adjusted_pnl": [15.0],
            "long_best_holding_minutes": [30.0],
            "short_best_holding_minutes": [45.0],
            "long_max_adverse_pnl": [-2.0],
            "short_max_adverse_pnl": [-3.0],
            "long_profit_barrier_hit": [1.0],
            "short_profit_barrier_hit": [1.0],
            "long_wait_regret": [0.0],
            "short_wait_regret": [0.0],
            "long_entry_local_rank": [0.8],
            "short_entry_local_rank": [0.7],
            "pred_side_prior_pressure_s0p5_long_best_adjusted_pnl": [12.0],
            "pred_side_prior_pressure_s0p5_short_best_adjusted_pnl": [8.0],
            "pred_long_best_holding_minutes": [35.0],
            "pred_short_best_holding_minutes": [40.0],
            "pred_long_max_adverse_pnl": [-1.0],
            "pred_short_max_adverse_pnl": [-1.0],
            "pred_long_wait_regret": [0.0],
            "pred_short_wait_regret": [0.0],
            "pred_long_entry_local_rank": [0.8],
            "pred_short_entry_local_rank": [0.7],
            "pred_long_profit_barrier_hit": [1.0],
            "pred_short_profit_barrier_hit": [1.0],
            "pred_best_side_prob_1": [0.6],
            "pred_best_side_prob_-1": [0.4],
            "pred_side_prior_pressure_long_predicted_ev_overestimate_risk": [long_ev_risk],
            "pred_side_prior_pressure_short_predicted_ev_overestimate_risk": [short_ev_risk],
            "pred_side_prior_pressure_long_ev_overestimate_prediction_source": ["bucket"],
            "pred_side_prior_pressure_short_ev_overestimate_prediction_source": ["bucket"],
            "pred_mlp_long_exit_event_minutes": [35.0],
            "pred_mlp_short_exit_event_minutes": [40.0],
            "pred_long_exit_event_prob_0": [0.1],
            "pred_short_exit_event_prob_0": [0.2],
            "pred_long_exit_event_prob_2": [0.3],
            "pred_short_exit_event_prob_2": [0.4],
            "pred_long_fixed_60m_adjusted_pnl": [5.0],
            "pred_short_fixed_60m_adjusted_pnl": [6.0],
            "pred_long_fixed_240m_adjusted_pnl": [7.0],
            "pred_short_fixed_240m_adjusted_pnl": [8.0],
            "pred_long_fixed_720m_adjusted_pnl": [9.0],
            "pred_short_fixed_720m_adjusted_pnl": [10.0],
        }
    )


class EntryEvMultifamilyPolicyTradeEnrichmentTests(unittest.TestCase):
    def test_build_enrichment_joins_each_trade_with_its_family_predictions(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            decision_time = "2024-01-01 00:00:00Z"
            fam_a_path = tmp_path / "fam_a.parquet"
            fam_b_path = tmp_path / "fam_b.parquet"
            prediction_frame(
                decision_time=decision_time,
                regime="family_a_regime",
                long_ev_risk=0.20,
                short_ev_risk=0.30,
            ).to_parquet(fam_a_path, index=False)
            prediction_frame(
                decision_time=decision_time,
                regime="family_b_regime",
                long_ev_risk=0.70,
                short_ev_risk=0.80,
            ).to_parquet(fam_b_path, index=False)

            run_dir = tmp_path / "policy"
            run_dir.mkdir()
            pd.DataFrame(
                [
                    {
                        "family": "fam_a",
                        "role": "cal",
                        "month": "2024-01",
                        "candidate": "candidate_a",
                    },
                    {
                        "family": "fam_b",
                        "role": "fresh",
                        "month": "2024-01",
                        "candidate": "candidate_b",
                    },
                ]
            ).to_csv(run_dir / "monthly_policy_metrics.csv", index=False)
            trade_dir_a = run_dir / "trades" / "fam_a" / "candidate_a"
            trade_dir_b = run_dir / "trades" / "fam_b" / "candidate_b"
            trade_dir_a.mkdir(parents=True)
            trade_dir_b.mkdir(parents=True)
            pd.DataFrame([trade_row(decision_time, "long", 3.0)]).to_csv(
                trade_dir_a / "2024-01.csv",
                index=False,
            )
            pd.DataFrame([trade_row(decision_time, "short", 4.0)]).to_csv(
                trade_dir_b / "2024-01.csv",
                index=False,
            )

            args = argparse.Namespace(
                policy_run=[f"validation={run_dir}"],
                family_predictions=[f"fam_a={fam_a_path}", f"fam_b={fam_b_path}"],
                long_column="pred_side_prior_pressure_s0p5_long_best_adjusted_pnl",
                short_column="pred_side_prior_pressure_s0p5_short_best_adjusted_pnl",
                extra_columns="",
                output_dir=tmp_path,
                label="unit_multifamily_enrichment",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                output_dir = entry_ev_multifamily_policy_trade_enrichment.build_enrichment(args)
            enriched = pd.read_csv(output_dir / "residual_enriched_trades.csv")
            matches = pd.read_csv(output_dir / "prediction_match_summary.csv")

        first = enriched[enriched["family"].eq("fam_a")].iloc[0]
        second = enriched[enriched["family"].eq("fam_b")].iloc[0]
        self.assertEqual(first["combined_regime"], "family_a_regime")
        self.assertEqual(second["combined_regime"], "family_b_regime")
        self.assertAlmostEqual(first["selected_ev_overestimate_risk"], 0.20)
        self.assertAlmostEqual(second["selected_ev_overestimate_risk"], 0.80)
        self.assertTrue(matches["matched_prediction_share"].eq(1.0).all())


if __name__ == "__main__":
    unittest.main()
