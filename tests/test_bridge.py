import json
import tempfile
import unittest

from bridge.mt5_ai_bridge import (
    Settings,
    load_trade_command,
    normalize_signal,
    parse_signal_text,
    persist_state,
    save_snapshot,
    validate_snapshot,
)
from analysis.dry_run_command import command_from_signal


class BridgeTests(unittest.TestCase):
    def test_parse_signal_text_extracts_json(self):
        signal = parse_signal_text('prefix {"action":"hold","confidence":0.2} suffix')
        self.assertEqual(signal["action"], "hold")
        self.assertEqual(signal["confidence"], 0.2)

    def test_normalize_signal_forces_hold_on_bad_action(self):
        signal = normalize_signal(
            {
                "action": "maybe",
                "confidence": 2,
                "reason": "x",
                "stop_loss": 1,
                "take_profit": 2,
            }
        )
        self.assertEqual(signal["action"], "hold")
        self.assertEqual(signal["confidence"], 1.0)
        self.assertIsNone(signal["stop_loss"])
        self.assertIsNone(signal["take_profit"])

    def test_validate_snapshot_requires_bid_ask(self):
        with self.assertRaises(ValueError):
            validate_snapshot({"symbol": "XAUUSD", "timeframe": "M1", "bid": "bad", "ask": 1})

    def test_sample_request_shape(self):
        with open("src/bridge/sample_request.json", encoding="utf-8") as f:
            payload = json.load(f)
        validate_snapshot(payload)

    def test_save_snapshot_returns_local_hold_status(self):
        with open("src/bridge/sample_request.json", encoding="utf-8") as f:
            payload = json.load(f)
        signal = save_snapshot(payload)
        self.assertTrue(signal["ok"])
        self.assertEqual(signal["provider"], "local")
        self.assertEqual(signal["model"], "save-only")
        self.assertEqual(signal["action"], "hold")

    def test_persist_state_writes_snapshot_based_codex_files(self):
        with open("src/bridge/sample_request.json", encoding="utf-8") as f:
            payload = json.load(f)
        signal = save_snapshot(payload)
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = Settings(
                provider="mock",
                host="127.0.0.1",
                port=8765,
                token="",
                timeout_seconds=20,
                max_model_tokens=900,
                state_dir=tmpdir,
                openai_api_key="",
                openai_model="gpt-5.2",
                openai_base_url="https://api.openai.com/v1",
                anthropic_api_key="",
                anthropic_model="claude-sonnet-4-5",
                anthropic_base_url="https://api.anthropic.com",
                anthropic_version="2023-06-01",
            )
            persist_state(payload, signal, settings)
            with open(f"{tmpdir}/latest_snapshot.json", encoding="utf-8") as f:
                latest_snapshot = json.load(f)
            self.assertEqual(latest_snapshot["symbol"], payload["symbol"])
            self.assertEqual(latest_snapshot["bid"], payload["bid"])
            with open(f"{tmpdir}/latest_context.md", encoding="utf-8") as f:
                self.assertIn("XAUUSD", f.read())
            with open(f"{tmpdir}/latest_signal.json", encoding="utf-8") as f:
                latest_signal = json.load(f)
            self.assertEqual(latest_signal["provider"], "local")
            self.assertEqual(latest_signal["model"], "save-only")

    def test_bridge_loads_dry_run_command_created_from_signal(self):
        signal = {
            "mode": "manual_review",
            "action": "sell",
            "symbol": "XAUUSD-m",
            "score": 55.5,
            "risk_reward": 5,
            "current_entry_reference": 4106.83,
            "stop_loss": 4107.96,
            "take_profit": 4091.51,
            "valid_for_seconds": 120,
        }
        command = command_from_signal(signal, volume=0.01, expires_in_seconds=30)
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(f"{tmpdir}/trade_command.json", "w", encoding="utf-8") as f:
                json.dump(command, f)
            settings = Settings(
                provider="mock",
                host="127.0.0.1",
                port=8765,
                token="",
                timeout_seconds=20,
                max_model_tokens=900,
                state_dir=tmpdir,
                openai_api_key="",
                openai_model="gpt-5.2",
                openai_base_url="https://api.openai.com/v1",
                anthropic_api_key="",
                anthropic_model="claude-sonnet-4-5",
                anthropic_base_url="https://api.anthropic.com",
                anthropic_version="2023-06-01",
            )
            loaded = load_trade_command(settings)
        self.assertEqual(loaded["action"], "sell")
        self.assertTrue(loaded["dry_run"])
        self.assertEqual(loaded["status"], "pending")


if __name__ == "__main__":
    unittest.main()
