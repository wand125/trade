#!/usr/bin/env python3
"""Token-free runtime watcher for the manual trading method.

Polls runtime/ state written by the MT5 bridge and prints one line per
meaningful transition (edge-triggered). Designed to run under a session
Monitor: stdout lines wake Claude; quiet markets produce no output.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--state-dir", default="runtime")
    p.add_argument("--interval", type=int, default=30)
    p.add_argument(
        "--levels",
        default="",
        help="Comma list of SYMBOL:price entries, e.g. 'USDJPY-m:157.15,USDJPY-m:157.75'",
    )
    p.add_argument("--stale-seconds", type=int, default=300)
    p.add_argument("--level-cooldown", type=int, default=900,
                   help="Seconds to suppress repeat alerts for the same level (default 900)")
    p.add_argument("--digest-minutes", type=int, default=0,
                   help="Emit a compact state digest every N minutes (0=off)")
    p.add_argument(
        "--events",
        default="",
        help="Semicolon list of 'YYYY-MM-DDTHH:MM|label' (local time) to warn about at T-60min and T-10min",
    )
    p.add_argument(
        "--rules",
        default="",
        help="Path to a JSON list of delegation conditions, evaluated on confirmed bars "
             "(e.g. runtime/delegation_rules.json). Emits DELEGATION_MET on false->true edges.",
    )
    p.add_argument(
        "--rules-test",
        action="store_true",
        help="One-shot: replay --rules against the bars in current snapshots, print every "
             "firing point, then exit. Use to verify a condition BEFORE delegating it.",
    )
    return p.parse_args()


TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}


def _parse_server_ts(text: str) -> float | None:
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M"):
        try:
            return time.mktime(time.strptime(text, fmt))
        except (TypeError, ValueError):
            continue
    return None


def confirmed_bars(bars: list, server_time: str, tf_minutes: int) -> list:
    """確定済みバーのみ返す(形成中の最終バーを、サーバー時刻との比較で落とす)。"""
    server_ts = _parse_server_ts(server_time or "")
    if server_ts is None:
        return bars[:-1]  # サーバー時刻が読めなければ最終バーを形成中とみなす
    out = []
    for b in bars:
        ts = _parse_server_ts(b.get("time", ""))
        if ts is not None and ts + tf_minutes * 60 <= server_ts:
            out.append(b)
    return out


def eval_rule(rule: dict, snapshot: dict) -> tuple[bool, str]:
    """1ルールを評価し (成立しているか, 判定詳細) を返す。状態判定(直近N本のみ)。"""
    tf_name = rule.get("timeframe", "M5")
    tfs = snapshot.get("timeframes") or {}
    tf = tfs.get(tf_name)
    bars = tf.get("bars") if isinstance(tf, dict) else tf
    if not isinstance(bars, list) or not bars:
        return False, "no bars"
    conf = confirmed_bars(bars, snapshot.get("server_time", ""), TF_MINUTES.get(tf_name, 5))
    n = int(rule.get("count", 2))
    if len(conf) < n:
        return False, f"confirmed bars {len(conf)} < {n}"
    closes = [b.get("close") for b in conf[-n:]]
    times = [b.get("time", "")[-5:] for b in conf[-n:]]
    thr = float(rule["threshold"])
    if any(not isinstance(c, (int, float)) for c in closes):
        return False, "bad closes"
    if rule.get("op") == "above":
        ok = all(c > thr for c in closes)
    else:
        ok = all(c < thr for c in closes)
    detail = " ".join(f"{t}={c:g}" for t, c in zip(times, closes))
    return ok, detail


def load_rules(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [r for r in data if isinstance(r, dict) and r.get("id") and r.get("symbol")] \
            if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError, ValueError):
        return []


def read_json(path: Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def read_account(path: Path) -> dict:
    out = {"balance": None, "equity": None, "positions": None, "tickets": {}, "prices": {}}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    in_positions = False
    positions = 0
    for line in text.splitlines():
        if line.startswith("- Balance:"):
            out["balance"] = float(line.split(":")[1].strip())
        elif line.startswith("- Equity:"):
            out["equity"] = float(line.split(":")[1].strip())
        elif line.startswith("## Open Positions"):
            in_positions = True
        elif line.startswith("## ") and in_positions:
            in_positions = False
        elif in_positions and line.startswith("- ") and "None" not in line:
            positions += 1
            fields = line[2:].split()
            info = {}
            for i, token in enumerate(fields):
                if token in ("ticket", "current", "SL", "TP") and i + 1 < len(fields):
                    info[token] = fields[i + 1]
            ticket = info.get("ticket")
            if ticket:
                out["tickets"][ticket] = {
                    "symbol": fields[2] if len(fields) > 2 else "",
                    "current": _to_float(info.get("current")),
                    "sl": _to_float(info.get("SL")),
                    "tp": _to_float(info.get("TP")),
                }
    out["positions"] = positions
    # 保有玉の current 価格は銘柄別に取れるため、単一銘柄しか載らない
    # latest_snapshot.json の穴(交互更新で片方が盲目になる)を埋める。
    for info in out["tickets"].values():
        symbol, price = info.get("symbol"), info.get("current")
        if symbol and price is not None:
            out["prices"][symbol] = price
    return out


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def emit(msg: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    print(f"{stamp} {msg}", flush=True)


def backtest_rule(rule: dict, snapshot: dict) -> list[str]:
    """ルールをスナップショット内の確定バー全体に対して再生し、発火点(false->true縁)を列挙する。
    委任条件を渡す前の検証(誤検知チェック)に使う。"""
    tf_name = rule.get("timeframe", "M5")
    tfs = snapshot.get("timeframes") or {}
    tf = tfs.get(tf_name)
    bars = tf.get("bars") if isinstance(tf, dict) else tf
    if not isinstance(bars, list) or not bars:
        return ["no bars"]
    conf = confirmed_bars(bars, snapshot.get("server_time", ""), TF_MINUTES.get(tf_name, 5))
    n = int(rule.get("count", 2))
    thr = float(rule["threshold"])
    above = rule.get("op") == "above"
    fired: list[str] = []
    prev = False
    for i in range(n, len(conf) + 1):
        closes = [b.get("close") for b in conf[i - n:i]]
        if any(not isinstance(c, (int, float)) for c in closes):
            continue
        ok = all(c > thr for c in closes) if above else all(c < thr for c in closes)
        if ok and not prev:
            t = conf[i - 1].get("time", "?")
            detail = " ".join(f"{b.get('time','')[-5:]}={b.get('close'):g}" for b in conf[i - n:i])
            fired.append(f"発火 {t} 足の確定時点: {detail}")
        elif not ok and prev:
            t = conf[i - 1].get("time", "?")
            fired.append(f"解除 {t}")
        prev = ok
    if not fired:
        fired.append("この期間に発火なし")
    fired.append(f"(検証範囲: {conf[0].get('time','?')} 〜 {conf[-1].get('time','?')}、確定{len(conf)}本、現在の状態: {'成立' if prev else '未成立'})")
    return fired


def run_rules_test(state_dir: Path, rules_path: Path) -> None:
    rules = load_rules(rules_path)
    if not rules:
        print(f"no valid rules in {rules_path}")
        return
    for rule in rules:
        sym = rule["symbol"]
        snap = read_json(state_dir / f"latest_snapshot_{sym}.json")
        op_txt = "超" if rule.get("op") == "above" else "未満"
        print(f"--- rule {rule['id']}: {sym} {rule.get('timeframe','M5')}終値{rule.get('count',2)}本連続 "
              f"{rule['threshold']}{op_txt} {rule.get('note','')}")
        for line in backtest_rule(rule, snap):
            print("  " + line)


def main() -> None:
    args = parse_args()
    state_dir = Path(args.state_dir)
    if args.rules_test:
        if not args.rules:
            print("--rules-test requires --rules <path>")
            sys.exit(1)
        run_rules_test(state_dir, Path(args.rules))
        return
    rules_path = Path(args.rules) if args.rules else None
    rules: list[dict] = []
    rules_mtime: float = 0.0
    rule_state: dict[str, bool] = {}
    levels: list[tuple[str, float]] = []
    if args.levels:
        for entry in args.levels.split(","):
            sym, _, val = entry.partition(":")
            if val:
                levels.append((sym.strip(), float(val)))

    events: list[tuple[float, str]] = []
    if args.events:
        for entry in args.events.split(";"):
            ts, _, label = entry.partition("|")
            if label:
                events.append((time.mktime(time.strptime(ts.strip(), "%Y-%m-%dT%H:%M")), label.strip()))
    warned: set[tuple[str, int]] = set()
    level_last_fired: dict[tuple[str, float], float] = {}

    last_price: dict[str, float] = {}
    last_seen: dict[str, float] = {}
    symbol_stale: set[str] = set()
    watch_symbols = sorted({sym for sym, _ in levels})
    last_balance: float | None = None
    last_positions: int | None = None
    last_tickets: dict | None = None
    stale_reported = False
    last_digest = time.time()
    # ダイジェスト区間ごとの値動き。現在値だけでは動いているか止まっているかが分からない。
    digest_range: dict[str, list[float]] = {}

    while True:
        now = time.time()
        if args.digest_minutes and now - last_digest >= args.digest_minutes * 60:
            parts = []
            for s_, p_ in sorted(last_price.items()):
                rng = digest_range.get(s_)
                if rng:
                    lo, hi, first = rng
                    width = hi - lo
                    change = p_ - first
                    unit = 100 if p_ < 1000 else 1  # USDJPYはpips、金はドル
                    parts.append(
                        f"{s_}:{p_:g}({change * unit:+.1f}/幅{width * unit:.1f})"
                    )
                else:
                    parts.append(f"{s_}:{p_:g}")
            line = "[watch] DIGEST " + (" | ".join(parts) if parts else "no data")
            if last_positions is not None:
                line += f" | pos {last_positions}"
            if last_balance is not None:
                line += f" | bal {last_balance:,.0f}"
            emit(line)
            last_digest = now
            digest_range = {}
        for ev_ts, label in events:
            remaining = ev_ts - now
            for lead_min in (60, 10):
                key = (label, lead_min)
                if key not in warned and 0 < remaining <= lead_min * 60:
                    emit(f"[watch] EVENT_WARN {label} まで約{int(remaining/60)}分")
                    warned.add(key)
        # 委任条件ルール: ファイル変更を検知して再読込し、確定バーの状態判定で
        # false->true の縁のみ DELEGATION_MET を出す(過去に成立して戻った履歴では発火しない)。
        if rules_path is not None and rules_path.exists():
            m = rules_path.stat().st_mtime
            if m != rules_mtime:
                rules = load_rules(rules_path)
                rules_mtime = m
                emit(f"[watch] RULES_LOADED {len(rules)}件: " + ", ".join(r["id"] for r in rules))
        for rule in rules:
            rsnap = read_json(state_dir / f"latest_snapshot_{rule['symbol']}.json")
            ok, detail = eval_rule(rule, rsnap)
            rid = rule["id"]
            prev_ok = rule_state.get(rid, False)
            if ok and not prev_ok:
                emit(f"[watch] DELEGATION_MET {rid} {rule['symbol']} "
                     f"{rule.get('timeframe','M5')}終値{rule.get('count',2)}本が"
                     f"{rule['threshold']}{'超' if rule.get('op')=='above' else '未満'}: "
                     f"{detail} ({rule.get('note','')})")
            elif not ok and prev_ok:
                emit(f"[watch] DELEGATION_CLEARED {rid} 条件が解消: {detail}")
            rule_state[rid] = ok

        snap = read_json(state_dir / "latest_snapshot.json")
        acct = read_account(state_dir / "latest_account.md")

        # 銘柄別スナップショットがあれば、そちらを各銘柄の一次情報にする
        # (共有ファイルは各EAが交互に上書きするため片方が失われる)。
        per_symbol: dict[str, tuple[float, float]] = {}
        for wsym in watch_symbols:
            path = state_dir / f"latest_snapshot_{wsym.replace('/', '')}.json"
            if not path.exists():
                continue
            d = read_json(path)
            bid = d.get("bid")
            if isinstance(bid, (int, float)):
                per_symbol[wsym] = (bid, path.stat().st_mtime)

        mtime = (state_dir / "latest_snapshot.json").stat().st_mtime if (state_dir / "latest_snapshot.json").exists() else 0
        age = time.time() - mtime
        if age > args.stale_seconds and not stale_reported:
            emit(f"[watch] DATA_STALE snapshotが{int(age)}秒更新されていない(MT5/EA/ブリッジ停止の可能性)")
            stale_reported = True
        elif age <= args.stale_seconds and stale_reported:
            emit("[watch] DATA_RESUMED snapshot更新が再開")
            stale_reported = False

        for wsym in watch_symbols:
            # 銘柄別ファイルがあれば、その更新時刻が正確な鮮度になる
            if wsym in per_symbol:
                last_seen[wsym] = per_symbol[wsym][1]
            seen = last_seen.get(wsym)
            if seen is not None and now - seen > args.stale_seconds and wsym not in symbol_stale:
                emit(f"[watch] SYMBOL_STALE {wsym} のsnapshotが{int((now-seen)/60)}分更新されていない(EAがpassive/停止の可能性。価格・水準監視は盲目)")
                symbol_stale.add(wsym)
            elif seen is not None and now - seen <= args.stale_seconds and wsym in symbol_stale:
                emit(f"[watch] SYMBOL_RESUMED {wsym} の更新が再開")
                symbol_stale.discard(wsym)

        # スナップショットは1銘柄ずつしか載らないので、保有玉の current 価格も
        # 価格源として併用する(保有中の銘柄が交互更新で盲目にならないように)。
        observed = dict(acct.get("prices") or {})
        sym = snap.get("symbol")
        bid = snap.get("bid")
        if sym and isinstance(bid, (int, float)):
            observed[sym] = bid
        # 銘柄別ファイルが最優先(共有ファイルの上書き合戦の影響を受けない)
        for psym, (pbid, _) in per_symbol.items():
            observed[psym] = pbid

        for osym, price in observed.items():
            last_seen[osym] = now
            prev = last_price.get(osym)
            if prev is not None:
                for lsym, level in levels:
                    if lsym != osym:
                        continue
                    crossed_up = prev < level <= price
                    crossed_down = prev > level >= price
                    if not (crossed_up or crossed_down):
                        continue
                    key = (lsym, level)
                    if now - level_last_fired.get(key, 0) < args.level_cooldown:
                        continue
                    level_last_fired[key] = now
                    if crossed_up:
                        emit(f"[watch] LEVEL_UP {osym} が {level} を上抜け(価格 {price})")
                    else:
                        emit(f"[watch] LEVEL_DOWN {osym} が {level} を下抜け(価格 {price})")
            last_price[osym] = price
            rng = digest_range.get(osym)
            if rng is None:
                digest_range[osym] = [price, price, price]  # lo, hi, 区間開始値
            else:
                rng[0] = min(rng[0], price)
                rng[1] = max(rng[1], price)

        bal = acct.get("balance")
        if bal is not None:
            if last_balance is not None and abs(bal - last_balance) > 0.5:
                emit(f"[watch] BALANCE 残高が {last_balance:,.0f} -> {bal:,.0f} に変化(入金/決済)")
            last_balance = bal

        pos = acct.get("positions")
        if pos is not None:
            if last_positions is not None and pos != last_positions:
                emit(f"[watch] POSITIONS ポジション数が {last_positions} -> {pos} に変化")
            last_positions = pos

        tickets = acct.get("tickets") or {}
        if last_tickets is not None:
            for t, info in tickets.items():
                if t not in last_tickets:
                    emit(f"[watch] FILLED ticket {t} {info['symbol']} 約定を検知"
                         f"(current {info['current']} SL {info['sl']} TP {info['tp']})")
            for t, info in last_tickets.items():
                if t not in tickets:
                    emit(f"[watch] CLOSED ticket {t} {info['symbol']} が消滅(決済)")
                elif tickets[t]["sl"] != info["sl"] or tickets[t]["tp"] != info["tp"]:
                    emit(f"[watch] SLTP_CHANGED ticket {t} {info['symbol']} "
                         f"SL {info['sl']}->{tickets[t]['sl']} TP {info['tp']}->{tickets[t]['tp']}")
        last_tickets = tickets

        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
