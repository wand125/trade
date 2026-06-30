import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_overestimate_risk_selector.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_overestimate_risk_selector",
    SCRIPT_PATH,
)
entry_ev_overestimate_risk_selector = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_overestimate_risk_selector
SPEC.loader.exec_module(entry_ev_overestimate_risk_selector)


TARGET = "executable_ev_overestimate_target"


def row(
    candidate,
    role,
    month,
    pnl,
    target,
    support="high",
    pressure="low",
    direction="long",
):
    return {
        "candidate": candidate,
        "role": role,
        "month": month,
        "direction": direction,
        "entry_decision_timestamp": f"{month}-01T00:00:00Z",
        "adjusted_pnl": pnl,
        "support_bucket": support,
        "pressure_bucket": pressure,
        TARGET: target,
    }


class EntryEvOverestimateRiskSelectorTests(unittest.TestCase):
    def normalized_frame(self):
        return entry_ev_overestimate_risk_selector.read_component_frame(
            self.write_frame(
                pd.DataFrame(
                    [
                        row("good", "cal", "2024-01", 5.0, False),
                        row("good", "fresh", "2024-02", 6.0, False),
                        row("bad", "cal", "2024-01", 4.0, True),
                        row("bad", "fresh", "2024-02", -5.0, True),
                    ]
                )
            ),
            target=TARGET,
            group_columns=["support_bucket", "pressure_bucket"],
        )

    def write_frame(self, frame):
        path = Path("/tmp/test_entry_ev_overestimate_risk_selector.csv")
        frame.to_csv(path, index=False)
        return path

    def test_chronological_risk_uses_only_prior_months(self):
        frame = self.normalized_frame()
        risk = entry_ev_overestimate_risk_selector.build_chronological_ev_risk(
            frame,
            target=TARGET,
            group_columns=["support_bucket", "pressure_bucket"],
            prior_strength=0.0,
            min_group_support=1,
        )

        jan = risk[risk["month"].eq("2024-01")]
        feb = risk[risk["month"].eq("2024-02")]

        self.assertTrue(jan["ev_overestimate_prediction_source"].eq("no_prior").all())
        self.assertTrue(feb["ev_overestimate_prediction_source"].eq("bucket").all())
        self.assertAlmostEqual(float(feb["predicted_ev_overestimate_risk"].iloc[0]), 0.5)

    def test_selector_blocks_high_risk_and_low_coverage(self):
        frame = self.normalized_frame()
        risk = entry_ev_overestimate_risk_selector.build_chronological_ev_risk(
            frame,
            target=TARGET,
            group_columns=["support_bucket", "pressure_bucket"],
            prior_strength=0.0,
            min_group_support=1,
        )
        role_month = entry_ev_overestimate_risk_selector.summarize_role_months(
            risk,
            target=TARGET,
            risk_threshold=0.25,
        )
        summary = entry_ev_overestimate_risk_selector.summarize_candidates(role_month)
        gated = entry_ev_overestimate_risk_selector.apply_selector_gates(
            summary,
            min_roles=2,
            min_positive_roles=1,
            min_active_roles=2,
            min_total_pnl=-10.0,
            min_role_total_pnl=-10.0,
            min_month_pnl=-10.0,
            min_role_trades=1,
            min_month_trades=1,
            max_drawdown=float("inf"),
            max_side_trade_share=float("inf"),
            max_risk_mean=0.25,
            max_high_risk_share=0.25,
            max_no_prior_share=0.25,
            min_prediction_coverage=0.75,
        )
        good = gated[gated["candidate"].eq("good")].iloc[0]

        self.assertIn("no_prior_share_high", good["blockers"])
        self.assertIn("prediction_coverage_low", good["blockers"])

    def test_pointwise_screen_can_remove_high_risk_rows(self):
        frame = self.normalized_frame()
        risk = entry_ev_overestimate_risk_selector.build_chronological_ev_risk(
            frame,
            target=TARGET,
            group_columns=["support_bucket", "pressure_bucket"],
            prior_strength=0.0,
            min_group_support=1,
        )
        effects = entry_ev_overestimate_risk_selector.pointwise_screen_effects(
            risk,
            target=TARGET,
            thresholds=[0.25],
        )
        bad_high = effects[
            effects["candidate"].eq("bad")
            & effects["screen_mode"].eq("predicted_high_only")
        ].iloc[0]

        self.assertEqual(bad_high["removed_trades"], 1)
        self.assertAlmostEqual(bad_high["removed_pnl"], -5.0)
        self.assertAlmostEqual(bad_high["kept_total_pnl"], 4.0)


if __name__ == "__main__":
    unittest.main()
