import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_side_balance_downside_selector.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_side_balance_downside_selector",
    SCRIPT_PATH,
)
entry_ev_side_balance_downside_selector = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_side_balance_downside_selector
SPEC.loader.exec_module(entry_ev_side_balance_downside_selector)


def trade(
    *,
    candidate,
    role,
    month,
    pnl,
    risk,
    interaction,
    prior_count=2,
    direction="long",
):
    return {
        "candidate": candidate,
        "role": role,
        "month": month,
        "direction": direction,
        "entry_decision_timestamp": f"{month}-05T00:00:00Z",
        "entry_timestamp": f"{month}-05T00:00:00Z",
        "adjusted_pnl": pnl,
        "combined_regime": "range",
        "session_regime": "asia",
        "pred_side_balance_long_share_drift": interaction / max(risk, 0.001),
        "pred_side_balance_long_scale": 1.0,
        "pred_side_balance_short_scale": 1.0,
        "prior_trade_count": prior_count,
        "prior_downside_support_weight": min(prior_count / 5.0, 1.0),
        "prior_downside_risk_score": risk,
        "side_balance_signed_drift_for_trade": interaction / max(risk, 0.001),
        "side_balance_abs_signed_drift_for_trade": abs(interaction / max(risk, 0.001)),
        "side_balance_selected_side_overrepresented": True,
        "side_balance_selected_side_underrepresented": False,
        "side_balance_downside_interaction_score": interaction,
    }


class EntryEvSideBalanceDownsideSelectorTests(unittest.TestCase):
    def test_candidate_summary_aggregates_feature_pressure(self):
        frame = pd.DataFrame(
            [
                trade(candidate="low", role="r1", month="2024-01", pnl=5, risk=0.1, interaction=0.001),
                trade(candidate="low", role="r2", month="2024-02", pnl=4, risk=0.1, interaction=0.001),
                trade(candidate="high", role="r1", month="2024-01", pnl=8, risk=0.4, interaction=0.02),
                trade(candidate="high", role="r2", month="2024-02", pnl=7, risk=0.4, interaction=0.02),
            ]
        )
        role_month = entry_ev_side_balance_downside_selector.summarize_role_months(
            frame,
            risk_threshold=0.2,
            interaction_threshold=0.005,
        )
        summary = entry_ev_side_balance_downside_selector.summarize_candidates(role_month)

        low = summary[summary["candidate"].eq("low")].iloc[0]
        high = summary[summary["candidate"].eq("high")].iloc[0]

        self.assertEqual(low["risk_high_share"], 0.0)
        self.assertEqual(high["risk_high_share"], 1.0)
        self.assertLess(low["feature_pressure_score"], high["feature_pressure_score"])

    def test_feature_gate_can_reject_high_pressure_candidate(self):
        frame = pd.DataFrame(
            [
                trade(candidate="low", role="r1", month="2024-01", pnl=5, risk=0.1, interaction=0.001),
                trade(candidate="low", role="r2", month="2024-02", pnl=4, risk=0.1, interaction=0.001),
                trade(candidate="high", role="r1", month="2024-01", pnl=8, risk=0.4, interaction=0.02),
                trade(candidate="high", role="r2", month="2024-02", pnl=7, risk=0.4, interaction=0.02),
            ]
        )
        role_month = entry_ev_side_balance_downside_selector.summarize_role_months(
            frame,
            risk_threshold=0.2,
            interaction_threshold=0.005,
        )
        summary = entry_ev_side_balance_downside_selector.summarize_candidates(role_month)
        gated = entry_ev_side_balance_downside_selector.apply_selector_gates(
            summary,
            min_roles=2,
            min_positive_roles=2,
            min_active_roles=2,
            min_total_pnl=0.0,
            min_role_total_pnl=0.0,
            min_month_pnl=0.0,
            min_role_trades=1,
            min_month_trades=1,
            max_drawdown=float("inf"),
            max_side_trade_share=float("inf"),
            max_risk_high_share=0.5,
            max_interaction_high_share=0.5,
            max_prior_zero_share=float("inf"),
            max_feature_pressure_score=float("inf"),
        )
        selection = entry_ev_side_balance_downside_selector.select_policy(gated)

        self.assertEqual(selection["selected"], "policy")
        self.assertEqual(selection["candidate"], "low")
        high = gated[gated["candidate"].eq("high")].iloc[0]
        self.assertIn("risk_high_share_high", high["blockers"])
        self.assertIn("interaction_high_share_high", high["blockers"])


if __name__ == "__main__":
    unittest.main()
