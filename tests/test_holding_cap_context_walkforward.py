import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "holding_cap_context_walkforward.py"
)
SPEC = importlib.util.spec_from_file_location("holding_cap_context_walkforward", SCRIPT_PATH)
holding_cap_context_walkforward = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(holding_cap_context_walkforward)


def make_examples() -> pd.DataFrame:
    rows = [
        ("risk0", "2025-01", "range_low_vol", "london", -2.0),
        ("risk0", "2025-01", "range_low_vol", "asia", 3.0),
        ("risk0", "2025-02", "range_low_vol", "london", -1.0),
        ("risk0", "2025-02", "range_low_vol", "asia", 2.0),
        ("risk0", "2025-03", "range_low_vol", "london", -5.0),
        ("risk0", "2025-03", "range_low_vol", "asia", 4.0),
        ("risk5", "2025-01", "range_low_vol", "london", 4.0),
        ("risk5", "2025-02", "range_low_vol", "london", 3.0),
        ("risk5", "2025-03", "range_low_vol", "london", -7.0),
    ]
    frame = pd.DataFrame(
        rows,
        columns=["case_label", "month", "combined_regime", "session_regime", "cap_value"],
    )
    frame["cap_beneficial"] = frame["cap_value"] > 0
    frame["cap_harmful"] = frame["cap_value"] < 0
    return frame


def make_pooled_examples() -> pd.DataFrame:
    return make_examples()[lambda frame: frame["case_label"].eq("risk0")].reset_index(drop=True)


class HoldingCapContextWalkforwardTests(unittest.TestCase):
    def test_walkforward_pooled_excludes_prior_harmful_context_only(self):
        month_summary, selected = holding_cap_context_walkforward.walkforward_context_exclusions(
            make_pooled_examples(),
            context_columns=["combined_regime", "session_regime"],
            scope_column=None,
            min_prior_support=2,
            min_prior_months=2,
            max_prior_mean=0.0,
            max_prior_sum=0.0,
        )

        march = month_summary[
            month_summary["target_month"].eq("2025-03")
            & month_summary["selection_scope"].eq("pooled")
        ].iloc[0]

        self.assertEqual(march["selected_contexts"], "range_low_vol:london")
        self.assertEqual(march["excluded_holdout_examples"], 1)
        self.assertEqual(march["base_cap_value_sum"], -1.0)
        self.assertEqual(march["kept_cap_value_sum"], 4.0)
        self.assertEqual(march["exclusion_delta"], 5.0)
        self.assertEqual(selected["context_id"].tolist(), ["range_low_vol:london"])

    def test_walkforward_by_case_keeps_scopes_separate(self):
        month_summary, selected = holding_cap_context_walkforward.walkforward_context_exclusions(
            make_examples(),
            context_columns=["combined_regime", "session_regime"],
            scope_column="case_label",
            min_prior_support=2,
            min_prior_months=2,
            max_prior_mean=0.0,
            max_prior_sum=0.0,
        )

        march = month_summary[month_summary["target_month"].eq("2025-03")]
        risk0 = march[march["scope"].eq("risk0")].iloc[0]
        risk5 = march[march["scope"].eq("risk5")].iloc[0]

        self.assertEqual(risk0["selected_contexts"], "range_low_vol:london")
        self.assertEqual(risk0["exclusion_delta"], 5.0)
        self.assertEqual(risk5["selected_contexts"], "")
        self.assertEqual(risk5["exclusion_delta"], 0.0)
        self.assertEqual(selected["scope"].tolist(), ["risk0"])


if __name__ == "__main__":
    unittest.main()
