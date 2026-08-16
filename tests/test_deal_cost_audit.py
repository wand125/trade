import json
import tempfile
import unittest
from pathlib import Path

from trade_data.deal_cost_audit import build_report, main


class DealCostAuditTests(unittest.TestCase):
    def test_commission_requires_conversion_and_both_legs_for_round_trip(self):
        deals = [
            {"time": "2026-08-01", "symbol": "XAUUSD-m", "entry": "in", "volume": 0.1, "commission": -35},
            {"time": "2026-08-02", "symbol": "XAUUSD-m", "entry": "out", "volume": 0.1, "commission": -35},
            {"time": "2026-08-02", "symbol": "NO_CONFIG", "entry": "out", "volume": 0.1, "commission": -1},
        ]
        report = build_report(
            deals=deals,
            config={"symbols": {"XAUUSD-m": {"contract_size_per_lot": 100, "account_currency_to_quote_rate": 0.01}}},
        )
        row = report["commission"][0]
        self.assertAlmostEqual(row["entry_leg_commission_price"]["mean"], 0.035)
        self.assertAlmostEqual(row["round_trip_commission_price_mean"], 0.07)
        self.assertTrue(row["round_trip_observed_both_legs"])
        self.assertEqual(report["input_quality"]["commission"]["unconfigured_rows"], 1)

    def test_slippage_is_direction_aware_and_does_not_claim_exit_leg(self):
        rows = [
            {"event": "open", "symbol": "XAUUSD-m", "action": "buy", "entry": 100, "deal_price": 100.2},
            {"event": "open", "symbol": "XAUUSD-m", "action": "sell", "entry": 100, "deal_price": 99.9},
            {"event": "close", "symbol": "XAUUSD-m", "action": "buy", "entry": 100, "deal_price": 101},
        ]
        report = build_report(forward_rows=rows, config={})
        row = report["slippage"][0]
        self.assertAlmostEqual(row["entry_leg_adverse_slippage_price"]["mean"], 0.15)
        self.assertFalse(row["exit_leg_available"])
        self.assertFalse(report["all_in_cost_authorized"])
        self.assertIn("exit_slippage_not_observed", report["authorization_blockers"])

    def test_invalid_or_partial_data_never_fabricates_cost(self):
        report = build_report(
            deals=[{"symbol": "X", "entry": "in", "volume": 0, "commission": -1}],
            forward_rows=[{"event": "open", "symbol": "X", "action": "buy", "entry": "", "deal_price": 1}],
            config={"X": {"contract_size_per_lot": 100, "account_currency_to_quote_rate": 1}},
        )
        self.assertEqual(report["commission"], [])
        self.assertEqual(report["slippage"], [])
        self.assertIn("no_symbol_with_observed_round_trip_commission", report["authorization_blockers"])

    def test_cli_reads_bridge_json_and_forward_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            deals = root / "deals.json"
            forward = root / "forward.csv"
            config = root / "config.json"
            output = root / "report.json"
            deals.write_text(
                json.dumps({"deals": [
                    {"symbol": "EURUSD-m", "entry": "in", "volume": 1, "commission": -3.5},
                    {"symbol": "EURUSD-m", "entry": "out", "volume": 1, "commission": -3.5},
                ]}),
                encoding="utf-8",
            )
            forward.write_text("event,symbol,action,entry,deal_price\nopen,EURUSD-m,buy,1.1,1.1001\n", encoding="utf-8")
            config.write_text(
                json.dumps({"symbols": {"EURUSD-m": {"contract_size_per_lot": 100000, "account_currency_to_quote_rate": 1}}}),
                encoding="utf-8",
            )
            self.assertEqual(main(["--deal-history", str(deals), "--forward-csv", str(forward), "--config", str(config), "--output", str(output)]), 0)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertAlmostEqual(report["commission"][0]["round_trip_commission_price_mean"], 0.00007)
            self.assertEqual(report["slippage"][0]["entry_leg_adverse_slippage_price"]["observations"], 1)


if __name__ == "__main__":
    unittest.main()
