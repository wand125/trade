import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_validation_inventory.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_validation_inventory",
    SCRIPT_PATH,
)
entry_ev_validation_inventory = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(entry_ev_validation_inventory)


def make_frame(entries, offsets, ranks, month="2024-03"):
    rows = []
    for entry in entries:
        for offset in offsets:
            for rank in ranks:
                rows.append(
                    {
                        "policy": "timed_ev",
                        "entry_threshold": entry,
                        "short_entry_threshold_offset": offset,
                        "side_margin": 5.0,
                        "risk_penalty": 0.0,
                        "min_entry_rank": rank,
                        "period_start": f"{month}-01T00:00:00+00:00",
                        "total_adjusted_pnl": 1.0,
                        "trade_count": 1,
                    }
                )
    return pd.DataFrame(rows)


class EntryEvValidationInventoryTests(unittest.TestCase):
    def test_classifies_full_rank_grid(self):
        frame = make_frame(
            entries=[8, 10, 12, 14],
            offsets=[3, 6, 9],
            ranks=[0.0, 0.5, 0.6, 0.7, 0.8, 0.9],
        )

        row = entry_ev_validation_inventory.build_inventory_row(
            Path(
                "data/reports/backtests/"
                "20260630_entry_evcal_rank_fresh0304_calibrated/"
                "run_2024-03/metrics.csv"
            ),
            frame,
        )

        self.assertEqual(row["grid_class"], "full_rank_grid")
        self.assertEqual(row["role_hint"], "validation_candidate")
        self.assertEqual(row["protocol_hint"], "fresh2024_rank_validation")
        self.assertEqual(row["month"], "2024-03")

    def test_classifies_partial_rank_grid(self):
        frame = make_frame(
            entries=[10, 12, 14],
            offsets=[6, 9],
            ranks=[0.0, 0.5, 0.6],
            month="2024-05",
        )

        row = entry_ev_validation_inventory.build_inventory_row(
            Path(
                "data/reports/backtests/"
                "20260630_entry_evcal_rank_test_2024_05_12_calibrated/"
                "run_2024-05/metrics.csv"
            ),
            frame,
        )

        self.assertEqual(row["grid_class"], "partial_rank_grid")
        self.assertEqual(row["role_hint"], "fixed_test_or_holdout")

    def test_classifies_nonrank_grid(self):
        frame = make_frame(
            entries=[0, 2, 4, 6, 8, 10, 12],
            offsets=[0, 3, 6],
            ranks=[0.0],
            month="2024-01",
        )

        row = entry_ev_validation_inventory.build_inventory_row(
            Path(
                "data/reports/backtests/"
                "20260630_entry_evcal_validation_calibrated/"
                "run_2024-01/metrics.csv"
            ),
            frame,
        )

        self.assertEqual(row["grid_class"], "nonrank_grid")
        self.assertEqual(row["role_hint"], "calibration_validation_nonrank")

    def test_reference_key_matches_use_common_policy_axes(self):
        frame = make_frame(
            entries=[8, 10],
            offsets=[3],
            ranks=[0.0],
        )
        reference = make_frame(
            entries=[10],
            offsets=[3],
            ranks=[0.0],
        )
        key_columns = [
            "policy",
            "entry_threshold",
            "short_entry_threshold_offset",
            "side_margin",
            "risk_penalty",
            "min_entry_rank",
        ]
        reference_keys = entry_ev_validation_inventory.comparable_keys(
            reference,
            key_columns,
        )

        row = entry_ev_validation_inventory.build_inventory_row(
            Path(
                "data/reports/backtests/"
                "20260630_entry_evcal_rank_fresh0304_calibrated/"
                "run_2024-03/metrics.csv"
            ),
            frame,
            reference_keys=reference_keys,
            reference_key_columns=key_columns,
        )

        self.assertEqual(row["candidate_key_count"], 2)
        self.assertEqual(row["reference_key_match_count"], 1)

    def test_summary_marks_full_rank_validation_reusable(self):
        frame = pd.DataFrame(
            [
                {
                    "family_root": "fresh",
                    "role_hint": "validation_candidate",
                    "protocol_hint": "fresh2024_rank_validation",
                    "grid_class": "full_rank_grid",
                    "month": "2024-03",
                    "row_count": 72,
                    "trade_count_sum": 10,
                    "total_adjusted_pnl_sum": 1.0,
                    "candidate_key_count": 72,
                    "reference_key_match_count": 72,
                    "reference_key_match_ratio": 1.0,
                }
            ]
        )

        summary = entry_ev_validation_inventory.summarize_inventory(frame)

        self.assertEqual(
            summary.loc[0, "admission_reuse_status"],
            "usable_full_rank_validation_window",
        )


if __name__ == "__main__":
    unittest.main()
