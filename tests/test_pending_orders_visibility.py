"""P40: 未約定注文の可視化(EA→ブリッジ→watcher)のテスト。

- ブリッジが account.orders を latest_account.md の「## Pending Orders」節に書き出す
- watcher がその節をパースし、注文の出現/消滅を検知できる
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "bridge"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "methods" / "manual" / "scripts"))

from mt5_ai_bridge import format_account_context  # noqa: E402
from runtime_watch import read_account  # noqa: E402


SNAPSHOT = {
    "symbol": "USDJPY-m",
    "server_time": "2026.08.12 06:00:00",
    "bid": 159.30,
    "ask": 159.313,
    "account": {
        "login": 9181575,
        "currency": "JPY",
        "balance": 374232.0,
        "equity": 374232.0,
        "margin": 0.0,
        "free_margin": 374232.0,
        "margin_level": 0.0,
        "positions": [],
        "orders": [
            {
                "ticket": 91234567,
                "symbol": "XAUUSD-m",
                "type": "sell_limit",
                "volume": 0.1,
                "price": 4420.0,
                "sl": 4430.0,
                "tp": 4400.0,
                "magic": 0,
                "comment": "",
                "setup_time": "2026.08.12 05:50:00",
                "expiration": "",
            }
        ],
        "deals": [],
    },
}


def test_bridge_writes_pending_orders_section():
    text = format_account_context(SNAPSHOT)
    assert "## Pending Orders" in text
    assert "ticket 91234567 XAUUSD-m sell_limit 0.1 @ 4420.0 SL 4430.0 TP 4400.0" in text
    assert "expires GTC" in text  # expiration空はGTC表記


def test_bridge_writes_none_when_no_orders():
    snap = dict(SNAPSHOT, account=dict(SNAPSHOT["account"], orders=[]))
    text = format_account_context(snap)
    idx = text.index("## Pending Orders")
    section = text[idx:text.index("## Recent Deals")]
    assert "- None" in section


def test_watcher_parses_orders(tmp_path):
    text = format_account_context(SNAPSHOT)
    p = tmp_path / "latest_account.md"
    p.write_text(text, encoding="utf-8")
    acct = read_account(p)
    assert "91234567" in acct["orders"]
    o = acct["orders"]["91234567"]
    assert o["symbol"] == "XAUUSD-m"
    assert o["type"] == "sell_limit"
    assert o["price"] == "4420.0"
    # ポジション解析が壊れていないこと
    assert acct["positions"] == 0


def test_watcher_orders_empty(tmp_path):
    snap = dict(SNAPSHOT, account=dict(SNAPSHOT["account"], orders=[]))
    p = tmp_path / "latest_account.md"
    p.write_text(format_account_context(snap), encoding="utf-8")
    acct = read_account(p)
    assert acct["orders"] == {}
