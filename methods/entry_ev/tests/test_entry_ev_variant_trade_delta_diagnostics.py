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
    / "entry_ev_variant_trade_delta_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_variant_trade_delta_diagnostics",
    SCRIPT_PATH,
)
entry_ev_variant_trade_delta_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_variant_trade_delta_diagnostics
SPEC.loader.exec_module(entry_ev_variant_trade_delta_diagnostics)


def trade_row(decision: str, direction: str, pnl: float) -> dict[str, object]:
    entry_decision = pd.Timestamp(decision, tz="UTC")
    entry = entry_decision + pd.Timedelta(minutes=1)
    exit_time = entry + pd.Timedelta(minutes=30)
    return {
        "direction": direction,
        "entry_timestamp": entry,
        "exit_timestamp": exit_time,
        "entry_price": 2000.0,
        "exit_price": 2000.0 + pnl,
        "raw_pnl": pnl,
        "adjusted_pnl": pnl,
        "holding_minutes": 30.0,
        "exit_reason": "time_exit",
        "entry_decision_timestamp": entry_decision,
        "exit_decision_timestamp": exit_time - pd.Timedelta(minutes=1),
    }


def write_variant_run(
    root: Path,
    *,
    base_trades: pd.DataFrame,
    candidate_trades: pd.DataFrame,
) -> None:
    candidate = "q95_sg95_rank90_floor5_side_regime_session_month"
    rows = []
    for variant, trades in [("base", base_trades), ("loss_exit30", candidate_trades)]:
        rows.append(
            {
                "family": "toy",
                "role": "toy_validation",
                "month": "2024-01",
                "candidate": candidate,
                "variant": variant,
                "trade_count": int(len(trades)),
                "total_adjusted_pnl": float(trades["adjusted_pnl"].sum())
                if not trades.empty
                else 0.0,
            }
        )
        trade_dir = root / "trades" / "toy" / variant / candidate
        trade_dir.mkdir(parents=True)
        trades.to_csv(trade_dir / "2024-01.csv", index=False)
    pd.DataFrame(rows).to_csv(root / "monthly_exit_timing_metrics.csv", index=False)


class EntryEvVariantTradeDeltaDiagnosticsTests(unittest.TestCase):
    def test_run_variant_delta_summarizes_variant_trade_changes(self):
        candidate = "q95_sg95_rank90_floor5_side_regime_session_month"
        base_trades = pd.DataFrame(
            [
                trade_row("2024-01-01 00:00:00", "long", 10.0),
                trade_row("2024-01-01 01:00:00", "short", -20.0),
            ]
        )
        candidate_trades = pd.DataFrame(
            [
                trade_row("2024-01-01 00:00:00", "long", 8.0),
                trade_row("2024-01-01 02:00:00", "long", 5.0),
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_root = tmp_path / "variant_run"
            run_root.mkdir()
            write_variant_run(
                run_root,
                base_trades=base_trades,
                candidate_trades=candidate_trades,
            )
            args = argparse.Namespace(
                run_dir=run_root,
                base_variant="base",
                candidate_variant="loss_exit30",
                candidates=candidate,
                families="",
                months="",
                stateful_example_target="stateful_net",
                output_dir=tmp_path,
                label="unit_variant_delta",
            )
            run_dir = entry_ev_variant_trade_delta_diagnostics.run_variant_delta(args)
            rows = pd.read_csv(run_dir / "trade_delta_rows.csv")
            summary = pd.read_csv(run_dir / "group_by_candidate.csv")

        self.assertEqual(set(rows["delta_status"]), {"common", "only_base", "only_candidate"})
        self.assertEqual(summary["base_trade_count"].iloc[0], 2)
        self.assertEqual(summary["candidate_trade_count"].iloc[0], 2)
        self.assertAlmostEqual(summary["base_adjusted_pnl"].iloc[0], -10.0)
        self.assertAlmostEqual(summary["candidate_adjusted_pnl"].iloc[0], 13.0)
        self.assertAlmostEqual(summary["pnl_delta"].iloc[0], 23.0)
        self.assertAlmostEqual(summary["removed_negative_pnl"].iloc[0], -20.0)
        self.assertAlmostEqual(summary["added_positive_pnl"].iloc[0], 5.0)


if __name__ == "__main__":
    unittest.main()
