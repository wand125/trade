from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_candidate_episode_support_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_candidate_episode_support_diagnostics",
    SCRIPT_PATH,
)
entry_ev_candidate_episode_support_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_candidate_episode_support_diagnostics
SPEC.loader.exec_module(entry_ev_candidate_episode_support_diagnostics)


class EntryEvCandidateEpisodeSupportDiagnosticsTest(unittest.TestCase):
    def test_episode_rows_split_on_gap(self):
        rows = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(
                    [
                        "2025-01-01 00:00:00+00:00",
                        "2025-01-01 00:01:00+00:00",
                        "2025-01-01 00:05:00+00:00",
                    ],
                    utc=True,
                ),
                "month": ["2025-01", "2025-01", "2025-01"],
                "side": ["short", "short", "short"],
            }
        )

        episodes = entry_ev_candidate_episode_support_diagnostics.episode_rows(
            rows,
            family="toy",
            candidate="q",
            episode_gap_minutes=1.0,
        )

        self.assertEqual(episodes["row_count"].tolist(), [2, 1])
        self.assertEqual(episodes["duration_minutes"].tolist(), [1.0, 0.0])

    def test_summarize_family_counts_active_months(self):
        episodes = pd.DataFrame(
            {
                "family": ["toy", "toy"],
                "candidate": ["q", "q"],
                "month": ["2025-01", "2025-02"],
                "side": ["short", "long"],
                "row_count": [2, 3],
                "start": pd.to_datetime(
                    ["2025-01-01 00:00:00+00:00", "2025-02-01 00:00:00+00:00"],
                    utc=True,
                ),
                "end": pd.to_datetime(
                    ["2025-01-01 00:01:00+00:00", "2025-02-01 00:02:00+00:00"],
                    utc=True,
                ),
            }
        )

        summary = entry_ev_candidate_episode_support_diagnostics.summarize_family(
            episodes
        )

        self.assertEqual(summary["candidate_rows"].iloc[0], 5)
        self.assertEqual(summary["episode_count"].iloc[0], 2)
        self.assertEqual(summary["active_months"].iloc[0], 2)
        self.assertEqual(summary["long_episodes"].iloc[0], 1)
        self.assertEqual(summary["short_episodes"].iloc[0], 1)


if __name__ == "__main__":
    unittest.main()
