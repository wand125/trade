from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from scripts.experiments.entry_ev_surface_artifact_readiness_diagnostics import (
    parent_summary,
)


class EntryEvSurfaceArtifactReadinessDiagnosticsTest(unittest.TestCase):
    def test_parent_summary_marks_ready_and_conversion_needed_artifacts(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            ready_dir = root / "ready"
            convert_dir = root / "convert"
            ready_dir.mkdir()
            convert_dir.mkdir()
            ready_metric = ready_dir / "selector_monthly_metrics.csv"
            convert_metric = convert_dir / "selector_monthly_metrics.csv"
            ready_metric.write_text("x\n", encoding="utf-8")
            convert_metric.write_text("x\n", encoding="utf-8")
            (ready_dir / "config.json").write_text(
                json.dumps(
                    {
                        "current_trades": "ready_trades.csv",
                        "family_predictions": {"f": "pred.parquet"},
                        "candidate": "cand",
                    }
                ),
                encoding="utf-8",
            )
            (convert_dir / "config.json").write_text(
                json.dumps({"scored_trades": "scored.csv"}),
                encoding="utf-8",
            )
            pd.DataFrame(
                {
                    "role": ["r"],
                    "family": ["f"],
                    "month": ["2025-01"],
                    "candidate": ["cand"],
                    "selector_variant": ["v"],
                    "entry_block_rule": ["rule"],
                    "entry_blocked": [False],
                    "entry_decision_timestamp": ["2025-01-01T00:00:00Z"],
                    "exit_decision_timestamp": ["2025-01-01T01:00:00Z"],
                }
            ).to_csv(ready_dir / "ready_trades.csv", index=False)
            pd.DataFrame(
                {
                    "role": ["r"],
                    "family": ["f"],
                    "month": ["2025-01"],
                    "candidate": ["cand"],
                    "entry_decision_timestamp": ["2025-01-01T00:00:00Z"],
                    "exit_decision_timestamp": ["2025-01-01T01:00:00Z"],
                }
            ).to_csv(convert_dir / "hold_extension_stateful_trades.csv", index=False)
            config_summary = pd.DataFrame(
                {
                    "metric_parent": ["ready_parent", "convert_parent"],
                    "metric_path": [str(ready_metric), str(convert_metric)],
                    "negative_month_count": [2, 3],
                    "support_sufficient_negative_count": [1, 2],
                    "support_limited_negative_count": [0, 1],
                    "min_month_pnl": [-1.0, -2.0],
                    "total_adjusted_pnl_sum": [10.0, 20.0],
                }
            )
            inventory = pd.DataFrame(
                {
                    "metric_parent": ["ready_parent", "convert_parent", "convert_parent"],
                    "metric_path": [str(ready_metric), str(convert_metric), str(convert_metric)],
                    "role": ["r", "r", "r"],
                    "family": ["f", "f", "f"],
                    "month": ["2025-01", "2025-01", "2025-02"],
                    "variant": ["v", "v", "v"],
                    "candidate": ["cand", "cand", "cand"],
                    "entry_block_rule": ["rule", "rule", "rule"],
                    "support_sufficient_negative_month": [True, True, True],
                    "month_pnl": [-1.0, -2.0, -3.0],
                    "trade_count": [1, 1, 1],
                    "long_trade_count": [1, 1, 1],
                    "short_trade_count": [0, 0, 0],
                    "extra_trades_needed": [0, 0, 0],
                }
            )

            summary = parent_summary(config_summary, inventory)

        ready = summary[summary["metric_parent"].eq("ready_parent")].iloc[0]
        convert = summary[summary["metric_parent"].eq("convert_parent")].iloc[0]
        self.assertTrue(bool(ready["surface_ready_without_conversion"]))
        self.assertFalse(bool(ready["needs_trade_schema_conversion"]))
        self.assertFalse(bool(convert["surface_ready_without_conversion"]))
        self.assertTrue(bool(convert["needs_trade_schema_conversion"]))
        self.assertTrue(bool(convert["needs_surface_config"]))
        self.assertIn("selector_variant", str(convert["trade_missing_required_columns_any"]))
        self.assertEqual(int(convert["support_sufficient_target_identity_count"]), 2)


if __name__ == "__main__":
    unittest.main()
