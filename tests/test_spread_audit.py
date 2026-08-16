import unittest
import json
import tempfile
from pathlib import Path

from trade_data.spread_audit import build_report, main, normalize_spread_events


class SpreadAuditTests(unittest.TestCase):
    def test_normalization_rejects_invalid_quotes_and_accepts_epoch_or_iso_time(self):
        events = [
            {"received_at": "2026-08-01T00:00:00Z", "symbol": "EURUSD-m", "bid": 1.1, "ask": 1.1001},
            {"received_at": 1_775_001_600, "symbol": "EURUSD-m", "bid": "1.2", "ask": "1.2002"},
            {"received_at": "bad", "symbol": "EURUSD-m", "bid": 1.1, "ask": 1.2},
            {"received_at": "2026-08-01T00:00:00Z", "symbol": "EURUSD-m", "bid": 1.2, "ask": 1.1},
            {"received_at": "2026-08-01T00:00:00Z", "symbol": "", "bid": 1.1, "ask": 1.2},
        ]
        frame, counts = normalize_spread_events(events)
        self.assertEqual(counts, {"input_rows": 5, "invalid_rows": 3, "valid_rows": 2})
        self.assertEqual(len(frame), 2)
        self.assertTrue(frame["spread_price"].gt(0).all())

    def test_report_groups_symbols_and_applies_p90_sufficiency_gate(self):
        events = []
        for day in range(5):
            for sample in range(2):
                events.append(
                    {
                        "received_at": f"2026-08-0{day + 1}T0{sample}:00:00Z",
                        "symbol": "PASS-m",
                        "bid": 100.0,
                        "ask": 100.01,
                    }
                )
        for day in range(4):
            events.append(
                {
                    "received_at": f"2026-08-0{day + 1}T00:00:00Z",
                    "symbol": "THIN-m",
                    "bid": 200.0,
                    "ask": 200.02,
                }
            )
        report = build_report(
            events,
            cost_ceilings={"PASS-m": 0.02, "THIN-m": 0.03},
            min_observations=10,
            min_unique_days=5,
        )
        by_symbol = {row["symbol"]: row for row in report["symbols"]}
        self.assertTrue(by_symbol["PASS-m"]["data_sufficient"])
        self.assertTrue(by_symbol["PASS-m"]["spread_only_p90_gate_passed"])
        self.assertFalse(by_symbol["PASS-m"]["all_in_cost_authorized"])
        self.assertIn("commission_not_included", by_symbol["PASS-m"]["authorization_blockers"])
        self.assertFalse(by_symbol["THIN-m"]["data_sufficient"])
        self.assertFalse(by_symbol["THIN-m"]["spread_only_p90_gate_passed"])

    def test_report_blocks_p90_above_ceiling_even_when_median_is_below(self):
        events = [
            {
                "received_at": f"2026-08-{day + 1:02d}T00:00:00Z",
                "symbol": "SPIKY-m",
                "bid": 1.0,
                "ask": 1.01 if day < 4 else 1.10,
            }
            for day in range(5)
        ]
        report = build_report(
            events,
            cost_ceilings={"SPIKY-m": 0.05},
            min_observations=5,
            min_unique_days=5,
        )
        row = report["symbols"][0]
        self.assertLess(row["median_spread_price"], row["cost_ceiling_price"])
        self.assertGreater(row["p90_spread_price"], row["cost_ceiling_price"])
        self.assertFalse(row["spread_only_p90_gate_passed"])
        self.assertIn("p90_spread_above_cost_ceiling", row["authorization_blockers"])

    def test_cli_records_malformed_rows_and_never_authorizes_spread_only_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.jsonl"
            output = root / "report.json"
            ceilings = root / "ceilings.json"
            events.write_text(
                '{"received_at":"2026-08-01T00:00:00Z","symbol":"EURUSD-m","bid":1.1,"ask":1.1001}\nnot-json\n',
                encoding="utf-8",
            )
            ceilings.write_text('{"EURUSD-m":0.001}\n', encoding="utf-8")
            self.assertEqual(
                main(
                    [
                        "--events",
                        str(events),
                        "--output",
                        str(output),
                        "--cost-ceilings",
                        str(ceilings),
                        "--min-observations",
                        "1",
                        "--min-unique-days",
                        "1",
                    ]
                ),
                0,
            )
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["input_quality"]["malformed_json_rows"], 1)
            self.assertTrue(report["symbols"][0]["spread_only_p90_gate_passed"])
            self.assertFalse(report["symbols"][0]["all_in_cost_authorized"])


if __name__ == "__main__":
    unittest.main()
