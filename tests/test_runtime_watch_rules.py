"""委任条件ルール(runtime_watch の DELEGATION_MET 判定)のテスト。

作戦16(2026-08-11)の実バーを縮約した系列で、
- 形成中バーの除外(confirmed_bars)
- 状態判定(直近N本のみ、履歴では発火しない)
- バックテスト(発火点の列挙)
を検証する。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "methods" / "manual" / "scripts"))

from runtime_watch import backtest_rule, confirmed_bars, eval_rule  # noqa: E402


def _bar(t: str, close: float) -> dict:
    return {"time": t, "open": close, "high": close, "low": close, "close": close}


# 作戦16 実測の縮約(M5終値): チョップ→帯試し→拒絶
BARS = [
    _bar("2026.08.11 16:10", 4393.85),
    _bar("2026.08.11 16:15", 4394.33),
    _bar("2026.08.11 16:20", 4397.89),
    _bar("2026.08.11 16:25", 4399.45),
    _bar("2026.08.11 16:30", 4392.28),
    _bar("2026.08.11 16:35", 4399.67),
    _bar("2026.08.11 16:40", 4399.82),
    _bar("2026.08.11 16:45", 4394.91),
    _bar("2026.08.11 16:50", 4387.11),
    _bar("2026.08.11 16:55", 4389.38),  # 形成中とみなされるケースあり
]

RULE = {"id": "t", "symbol": "XAUUSD-m", "timeframe": "M5",
        "op": "below", "threshold": 4395.0, "count": 2}


def _snap(bars, server_time):
    return {"server_time": server_time, "timeframes": {"M5": {"bars": bars}}}


def test_confirmed_bars_drops_forming_bar():
    # サーバー時刻 16:58 → 16:55 の足(17:00確定)は形成中
    conf = confirmed_bars(BARS, "2026.08.11 16:58:00", 5)
    assert [b["time"][-5:] for b in conf][-1] == "16:50"
    # 17:00 を過ぎれば確定扱い
    conf2 = confirmed_bars(BARS, "2026.08.11 17:00:01", 5)
    assert [b["time"][-5:] for b in conf2][-1] == "16:55"


def test_state_based_no_fire_on_history():
    # 16:10/16:15 は過去に<4395が2本並んだが、直近(16:45/16:50)を見る状態判定。
    # サーバー16:42 時点: 直近確定2本は 16:30(4392.28)/16:35(4399.67) → 未成立
    ok, _ = eval_rule(RULE, _snap(BARS[:7], "2026.08.11 16:42:00"))
    assert not ok
    # サーバー16:58 時点: 直近確定2本は 16:45/16:50 → 成立
    ok2, detail = eval_rule(RULE, _snap(BARS, "2026.08.11 16:58:00"))
    assert ok2
    assert "16:45" in detail and "16:50" in detail


def test_backtest_lists_all_edges():
    lines = backtest_rule(RULE, _snap(BARS, "2026.08.11 17:00:01"))
    fires = [l for l in lines if l.startswith("発火")]
    # 16:15(チョップ中)と 16:50(拒絶)の2回発火が見える = 誤検知の事前確認に使える
    assert len(fires) == 2
    assert "16:15" in fires[0]
    assert "16:50" in fires[1]


def test_above_rule():
    rule = dict(RULE, op="above", threshold=4399.0)
    # 16:35/16:40 がともに >4399
    ok, _ = eval_rule(rule, _snap(BARS[:7], "2026.08.11 16:47:00"))
    assert ok
