import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_side_balance_downside_composite_selector.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_side_balance_downside_composite_selector",
    SCRIPT_PATH,
)
entry_ev_side_balance_downside_composite_selector = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_side_balance_downside_composite_selector
SPEC.loader.exec_module(entry_ev_side_balance_downside_composite_selector)


def trade(
    *,
    candidate,
    role,
    pnl,
    month="2024-01",
    risk=0.05,
    interaction=0.001,
    prior_count=5,
    support=1.0,
    direction_error=False,
    no_edge=False,
    exit_regret=1.0,
    pred_ev=4.0,
    ev_overestimate=0.0,
):
    return {
        "candidate": candidate,
        "role": role,
        "month": month,
        "direction": "long",
        "entry_decision_timestamp": f"{month}-05T00:00:00Z",
        "adjusted_pnl": pnl,
        "prior_trade_count": prior_count,
        "prior_downside_support_weight": support,
        "prior_downside_risk_score": risk,
        "side_balance_downside_interaction_score": interaction,
        "side_balance_abs_signed_drift_for_trade": abs(interaction / max(risk, 0.001)),
        "side_balance_signed_drift_for_trade": interaction / max(risk, 0.001),
        "direction_error": direction_error,
        "no_edge_entry": no_edge,
        "exit_regret": exit_regret,
        "pred_taken_ev": pred_ev,
        "ev_overestimate_vs_realized": ev_overestimate,
    }


class EntryEvSideBalanceDownsideCompositeSelectorTests(unittest.TestCase):
    def test_missing_required_role_is_unknown_high_risk(self):
        frame = pd.DataFrame(
            [
                trade(candidate="thin", role="cal", pnl=5.0),
                trade(candidate="thin", role="refit", pnl=4.0),
            ]
        )
        summary, role_summary = (
            entry_ev_side_balance_downside_composite_selector.summarize_required_roles(
                frame,
                required_roles=["cal", "fresh", "refit"],
                risk_threshold=0.2,
                interaction_threshold=0.005,
                large_exit_regret_threshold=10.0,
                ev_overestimate_scale=15.0,
            )
        )

        row = summary.iloc[0]
        fresh = role_summary[role_summary["role"].eq("fresh")].iloc[0]

        self.assertEqual(row["active_required_role_count"], 2)
        self.assertIn("fresh", row["missing_required_roles"])
        self.assertFalse(bool(fresh["role_present"]))
        self.assertEqual(fresh["role_composite_preflight_risk_score"], 1.0)
        self.assertEqual(row["max_required_role_composite_preflight_risk_score"], 1.0)

    def test_composite_gates_reject_direction_exit_failure(self):
        rows = []
        for role in ["cal", "fresh", "refit"]:
            rows.append(trade(candidate="robust", role=role, pnl=5.0))
            rows.append(
                trade(
                    candidate="bad_exit",
                    role=role,
                    pnl=8.0,
                    risk=0.4,
                    interaction=0.02,
                    direction_error=True,
                    exit_regret=20.0,
                    ev_overestimate=18.0,
                )
            )
        frame = pd.DataFrame(rows)
        summary, _ = entry_ev_side_balance_downside_composite_selector.summarize_required_roles(
            frame,
            required_roles=["cal", "fresh", "refit"],
            risk_threshold=0.2,
            interaction_threshold=0.005,
            large_exit_regret_threshold=10.0,
            ev_overestimate_scale=15.0,
        )
        gated = entry_ev_side_balance_downside_composite_selector.apply_composite_gates(
            summary,
            required_role_count=3,
            min_active_required_roles=3,
            min_required_role_trades=1,
            min_total_pnl=0.0,
            min_required_role_total_pnl=0.0,
            min_required_month_pnl=0.0,
            max_side_trade_share=float("inf"),
            max_required_role_prior_zero_share=0.75,
            min_required_role_prior_support_mean=0.0,
            max_required_role_feature_pressure_score=0.50,
            max_required_role_composite_preflight_risk_score=0.50,
            max_required_role_direction_error_rate=0.75,
            max_required_role_large_exit_regret_rate=0.75,
            max_required_role_ev_overestimate_component=1.0,
        )
        selection = entry_ev_side_balance_downside_composite_selector.select_policy(gated)

        self.assertEqual(selection["selected"], "policy")
        self.assertEqual(selection["candidate"], "robust")
        bad = gated[gated["candidate"].eq("bad_exit")].iloc[0]
        self.assertIn("required_role_composite_risk_high", bad["blockers"])
        self.assertIn("required_role_direction_error_high", bad["blockers"])
        self.assertIn("required_role_exit_regret_high", bad["blockers"])


if __name__ == "__main__":
    unittest.main()
