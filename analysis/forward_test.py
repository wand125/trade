from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.dry_run_command import load_json, load_optional_json
from analysis.market_data import Bar, TIME_FORMAT, load_history


def record_from_signal(signal: dict[str, Any], *, recorded_at: datetime | None = None) -> dict[str, object]:
    action = str(signal.get("action", "")).lower()
    if action not in {"buy", "sell"}:
        return {
            "id": signal_record_id(signal),
            "status": "ignored",
            "ignore_reason": f"signal action is not tradable: {action or '(missing)'}",
            "recorded_at": (recorded_at or datetime.now()).strftime(TIME_FORMAT),
            "source_signal": compact_signal(signal),
        }

    entry = number(signal.get("current_entry_reference"))
    sl = number(signal.get("stop_loss"))
    tp = number(signal.get("take_profit"))
    if entry is None:
        low = number(signal.get("entry_low"))
        high = number(signal.get("entry_high"))
        if low is not None and high is not None:
            entry = (low + high) / 2.0
    if entry is None or sl is None or tp is None:
        return {
            "id": signal_record_id(signal),
            "status": "ignored",
            "ignore_reason": "signal requires entry reference, stop_loss, and take_profit",
            "recorded_at": (recorded_at or datetime.now()).strftime(TIME_FORMAT),
            "source_signal": compact_signal(signal),
        }

    return {
        "id": signal_record_id(signal),
        "status": "open",
        "recorded_at": (recorded_at or datetime.now()).strftime(TIME_FORMAT),
        "symbol": str(signal.get("symbol") or "XAUUSD-m"),
        "action": action,
        "entry_reference": entry,
        "sl": sl,
        "tp": tp,
        "risk": abs(entry - sl),
        "risk_reward": number(signal.get("risk_reward")),
        "score": number(signal.get("score")),
        "pattern": signal.get("pattern"),
        "signal_generated_at": signal.get("generated_at"),
        "history_server_time": signal.get("history_server_time"),
        "latest_bar_time": signal.get("latest_bar_time"),
        "candidate_time": signal.get("candidate_time"),
        "reason": signal.get("reason"),
        "source_signal": compact_signal(signal),
    }


def evaluate_records(
    records: list[dict[str, Any]],
    bars: list[Bar],
    *,
    max_hold_minutes: int = 60,
) -> list[dict[str, object]]:
    return [evaluate_record(record, bars, max_hold_minutes=max_hold_minutes) for record in records]


def evaluate_record(record: dict[str, Any], bars: list[Bar], *, max_hold_minutes: int) -> dict[str, object]:
    if record.get("status") not in {"open", "closed"}:
        return dict(record)
    if record.get("status") == "closed":
        return dict(record)

    start = parse_time(str(record.get("latest_bar_time") or record.get("candidate_time") or ""))
    if start is None:
        updated = dict(record)
        updated["status"] = "invalid"
        updated["outcome"] = "missing_start_time"
        return updated

    future = [bar for bar in bars if bar.time > start]
    if not future:
        return dict(record)

    action = str(record.get("action", "")).lower()
    entry = number(record.get("entry_reference")) or 0.0
    sl = number(record.get("sl")) or 0.0
    tp = number(record.get("tp")) or 0.0
    risk = abs(entry - sl)
    if risk <= 0 or action not in {"buy", "sell"}:
        updated = dict(record)
        updated["status"] = "invalid"
        updated["outcome"] = "invalid_risk_or_action"
        return updated

    deadline = start + timedelta(minutes=max_hold_minutes)
    last_seen: Bar | None = None
    for bar in future:
        if bar.time > deadline:
            break
        last_seen = bar
        if action == "buy":
            hit_sl = bar.low <= sl
            hit_tp = bar.high >= tp
        else:
            hit_sl = bar.high >= sl
            hit_tp = bar.low <= tp
        if hit_sl and hit_tp:
            return closed_record(record, "loss", -1.0, bar, sl, "ambiguous_sl_first")
        if hit_sl:
            return closed_record(record, "loss", -1.0, bar, sl, "sl")
        if hit_tp:
            rr = abs(tp - entry) / risk
            return closed_record(record, "win", rr, bar, tp, "tp")

    if last_seen is None:
        return dict(record)
    if last_seen.time < deadline:
        return dict(record)
    if action == "buy":
        r_multiple = (last_seen.close - entry) / risk
    else:
        r_multiple = (entry - last_seen.close) / risk
    return closed_record(record, "timeout", r_multiple, last_seen, last_seen.close, "max_hold")


def closed_record(
    record: dict[str, Any],
    outcome: str,
    r_multiple: float,
    bar: Bar,
    exit_price: float,
    exit_reason: str,
) -> dict[str, object]:
    updated = dict(record)
    updated.update(
        {
            "status": "closed",
            "outcome": outcome,
            "r_multiple": round(r_multiple, 6),
            "exit_time": bar.time_text,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
        }
    )
    return updated


def summarize_forward(records: list[dict[str, Any]]) -> dict[str, object]:
    summary = forward_stats(records)
    summary.update(
        {
            "by_action": grouped_forward_summary(records, "action"),
            "by_risk_reward": grouped_forward_summary(records, "risk_reward"),
            "by_pattern": grouped_forward_summary(records, "pattern"),
        }
    )
    return summary


def forward_stats(records: list[dict[str, Any]]) -> dict[str, object]:
    closed = [record for record in records if record.get("status") == "closed"]
    open_records = [record for record in records if record.get("status") == "open"]
    ignored = [record for record in records if record.get("status") == "ignored"]
    wins = [record for record in closed if record.get("outcome") == "win"]
    losses = [record for record in closed if record.get("outcome") == "loss"]
    timeouts = [record for record in closed if record.get("outcome") == "timeout"]
    values = [number(record.get("r_multiple")) or 0.0 for record in closed]
    ordered_values = [
        number(record.get("r_multiple")) or 0.0
        for record in sorted(closed, key=lambda item: str(item.get("exit_time") or item.get("latest_bar_time") or ""))
    ]
    gross_profit = sum(value for value in values if value > 0)
    gross_loss = -sum(value for value in values if value < 0)
    avg_r = round(sum(values) / len(values), 4) if values else 0.0
    return {
        "records": len(records),
        "closed": len(closed),
        "open": len(open_records),
        "ignored": len(ignored),
        "wins": len(wins),
        "losses": len(losses),
        "timeouts": len(timeouts),
        "win_rate": round(len(wins) / len(closed), 4) if closed else 0.0,
        "avg_r": avg_r,
        "pf": round(gross_profit / gross_loss, 4) if gross_loss > 0 else 0.0,
        "total_r": round(sum(values), 4),
        "max_losing_streak": max_losing_streak(closed),
        "max_drawdown_r": round(max_drawdown(ordered_values), 4),
        "expectancy_r": avg_r,
    }


def grouped_forward_summary(records: list[dict[str, Any]], key: str) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        group = forward_group_value(record, key)
        if group == "":
            continue
        grouped.setdefault(group, []).append(record)
    return [{"group": group, **forward_stats(group_records)} for group, group_records in sorted(grouped.items())]


def forward_group_value(record: dict[str, Any], key: str) -> str:
    if key == "risk_reward":
        value = number(record.get(key))
        return f"{value:g}" if value is not None else ""
    return str(record.get(key) or "")


def max_losing_streak(records: list[dict[str, Any]]) -> int:
    streak = 0
    maximum = 0
    for record in sorted(records, key=lambda item: str(item.get("exit_time") or item.get("latest_bar_time") or "")):
        if record.get("outcome") == "loss":
            streak += 1
            maximum = max(maximum, streak)
        elif record.get("outcome") == "win":
            streak = 0
    return maximum


def max_drawdown(values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    maximum = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        maximum = max(maximum, peak - equity)
    return maximum


def append_record(path: str | Path, record: dict[str, object], *, include_ignored: bool = False) -> str:
    if record.get("status") == "ignored" and not include_ignored:
        return "ignored_not_written"
    records = read_records(path)
    if any(existing.get("id") == record.get("id") for existing in records):
        return "duplicate_not_written"
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return "written"


def read_records(path: str | Path) -> list[dict[str, Any]]:
    ledger = Path(path)
    if not ledger.exists():
        return []
    records: list[dict[str, Any]] = []
    with ledger.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
    return records


def write_records(path: str | Path, records: list[dict[str, object]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_summary(path: str | Path, summary: dict[str, object], records: list[dict[str, object]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ok": True, "generated_at": datetime.now().strftime(TIME_FORMAT), "summary": summary, "records": records}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def forward_status(
    *,
    signal: dict[str, Any] | None,
    records: list[dict[str, Any]],
    ledger_path: str | Path = "runtime/forward_tests.jsonl",
) -> dict[str, object]:
    summary = summarize_forward(records)
    preview = record_from_signal(signal) if isinstance(signal, dict) else None
    signal_status = signal_recordability(preview)
    open_records = int(summary.get("open") or 0)
    if open_records > 0:
        operational_status = "open_records_pending_evaluation"
    elif signal_status == "recordable":
        operational_status = "ready_to_record"
    else:
        operational_status = "waiting_for_tradable_signal"
    return {
        "ok": True,
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "operational_status": operational_status,
        "ledger": {
            "path": str(ledger_path),
            "exists": Path(ledger_path).exists(),
            "records": len(records),
            "last_record": summarize_record(records[-1]) if records else None,
        },
        "signal": {
            "present": isinstance(signal, dict),
            "recordability": signal_status,
            "preview": summarize_record(preview) if isinstance(preview, dict) else None,
            "action": signal.get("action") if isinstance(signal, dict) else None,
            "mode": signal.get("mode") if isinstance(signal, dict) else None,
            "score": signal.get("score") if isinstance(signal, dict) else None,
            "reason": signal.get("reason") if isinstance(signal, dict) else None,
            "generated_at": signal.get("generated_at") if isinstance(signal, dict) else None,
            "valid_for_seconds": signal.get("valid_for_seconds") if isinstance(signal, dict) else None,
        },
        "summary": summary,
    }


def signal_recordability(preview: dict[str, Any] | None) -> str:
    if not isinstance(preview, dict):
        return "missing_signal"
    if preview.get("status") == "open":
        return "recordable"
    if preview.get("status") == "ignored":
        return "ignored"
    return str(preview.get("status") or "unknown")


def summarize_record(record: dict[str, Any] | None) -> dict[str, object] | None:
    if not isinstance(record, dict):
        return None
    keys = (
        "id",
        "status",
        "action",
        "symbol",
        "score",
        "risk_reward",
        "candidate_time",
        "latest_bar_time",
        "recorded_at",
        "outcome",
        "r_multiple",
        "exit_time",
        "exit_reason",
        "ignore_reason",
    )
    return {key: record.get(key) for key in keys if key in record}


def format_markdown(summary: dict[str, object]) -> str:
    lines = [
        "# Forward Test",
        "",
        f"- Records: {summary.get('records')}",
        f"- Closed/Open/Ignored: {summary.get('closed')} / {summary.get('open')} / {summary.get('ignored')}",
        f"- Wins/Losses/Timeouts: {summary.get('wins')} / {summary.get('losses')} / {summary.get('timeouts')}",
        f"- Win rate: {summary.get('win_rate')}",
        f"- Avg R: {summary.get('avg_r')}",
        f"- PF: {summary.get('pf')}",
        f"- Max losing streak: {summary.get('max_losing_streak')}",
        f"- Max drawdown R: {summary.get('max_drawdown_r')}",
        f"- Expectancy R: {summary.get('expectancy_r')}",
    ]
    lines.extend(["", "## By Action", ""])
    append_summary_table(lines, summary.get("by_action"))
    lines.extend(["", "## By Risk Reward", ""])
    append_summary_table(lines, summary.get("by_risk_reward"))
    lines.extend(["", "## By Pattern", ""])
    append_summary_table(lines, summary.get("by_pattern"))
    return "\n".join(lines) + "\n"


def format_status_markdown(status: dict[str, object]) -> str:
    ledger = status.get("ledger", {})
    signal = status.get("signal", {})
    summary = status.get("summary", {})
    lines = [
        "# Forward Test Status",
        "",
        f"- Operational status: {status.get('operational_status')}",
        f"- Generated at: {status.get('generated_at')}",
        f"- Ledger exists: {ledger.get('exists') if isinstance(ledger, dict) else ''}",
        f"- Ledger records: {ledger.get('records') if isinstance(ledger, dict) else ''}",
        f"- Closed/Open/Ignored: {summary.get('closed') if isinstance(summary, dict) else ''} / {summary.get('open') if isinstance(summary, dict) else ''} / {summary.get('ignored') if isinstance(summary, dict) else ''}",
        "",
        "## Latest Signal",
        f"- Present: {signal.get('present') if isinstance(signal, dict) else ''}",
        f"- Recordability: {signal.get('recordability') if isinstance(signal, dict) else ''}",
        f"- Action: {signal.get('action') if isinstance(signal, dict) else ''}",
        f"- Score: {signal.get('score') if isinstance(signal, dict) else ''}",
        f"- Reason: {signal.get('reason') if isinstance(signal, dict) else ''}",
    ]
    return "\n".join(lines) + "\n"


def append_summary_table(lines: list[str], rows: object) -> None:
    if not isinstance(rows, list) or not rows:
        lines.append("_No rows._")
        return
    headers = [
        "group",
        "closed",
        "open",
        "ignored",
        "wins",
        "losses",
        "win_rate",
        "avg_r",
        "pf",
        "total_r",
        "max_losing_streak",
        "max_drawdown_r",
        "expectancy_r",
    ]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")


def signal_record_id(signal: dict[str, Any]) -> str:
    basis = "|".join(
        str(signal.get(key, ""))
        for key in ("symbol", "action", "candidate_time", "latest_bar_time", "current_entry_reference", "stop_loss", "take_profit", "score")
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:20]


def compact_signal(signal: dict[str, Any]) -> dict[str, object]:
    names = (
        "mode",
        "action",
        "symbol",
        "generated_at",
        "history_server_time",
        "latest_bar_time",
        "candidate_time",
        "current_entry_reference",
        "stop_loss",
        "take_profit",
        "risk_reward",
        "score",
        "pattern",
        "reason",
    )
    return {name: signal.get(name) for name in names if name in signal}


def parse_time(value: str) -> datetime | None:
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record and evaluate forward-test signals.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    record = subparsers.add_parser("record", help="Append the latest tradable signal to the forward-test ledger.")
    record.add_argument("--signal", default="runtime/latest_signal.json")
    record.add_argument("--ledger", default="runtime/forward_tests.jsonl")
    record.add_argument("--include-ignored", action="store_true")

    status = subparsers.add_parser("status", help="Report whether forward testing is waiting, recordable, or has open records.")
    status.add_argument("--signal", default="runtime/latest_signal.json")
    status.add_argument("--ledger", default="runtime/forward_tests.jsonl")
    status.add_argument("--output-json", default="runtime/latest_forward_test_status.json")
    status.add_argument("--output-md", default="runtime/latest_forward_test_status.md")

    evaluate = subparsers.add_parser("evaluate", help="Evaluate open forward-test records with current history.")
    evaluate.add_argument("--ledger", default="runtime/forward_tests.jsonl")
    evaluate.add_argument("--history", default="runtime/latest_history_168h.json")
    evaluate.add_argument("--max-hold-minutes", type=int, default=60)
    evaluate.add_argument("--output-ledger", default="")
    evaluate.add_argument("--summary-json", default="runtime/latest_forward_test.json")
    evaluate.add_argument("--summary-md", default="runtime/latest_forward_test.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "record":
        signal = load_json(args.signal)
        record = record_from_signal(signal)
        result = append_record(args.ledger, record, include_ignored=args.include_ignored)
        print(json.dumps({"result": result, "record": record}, ensure_ascii=False, indent=2))
        return 0 if result in {"written", "duplicate_not_written", "ignored_not_written"} else 2

    if args.command == "status":
        signal = load_optional_json(args.signal)
        records = read_records(args.ledger)
        status = forward_status(signal=signal, records=records, ledger_path=args.ledger)
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_json).write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_md).write_text(format_status_markdown(status), encoding="utf-8")
        print(json.dumps(status, ensure_ascii=False, indent=2))
        print(f"wrote {args.output_json}")
        print(f"wrote {args.output_md}")
        return 0

    history = load_history(args.history)
    records = read_records(args.ledger)
    evaluated = evaluate_records(records, history.bars("M1"), max_hold_minutes=args.max_hold_minutes)
    output_ledger = args.output_ledger or args.ledger
    write_records(output_ledger, evaluated)
    summary = summarize_forward(evaluated)
    write_summary(args.summary_json, summary, evaluated)
    Path(args.summary_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary_md).write_text(format_markdown(summary), encoding="utf-8")
    print(json.dumps({"summary": summary}, ensure_ascii=False, indent=2))
    print(f"wrote {output_ledger}")
    print(f"wrote {args.summary_json}")
    print(f"wrote {args.summary_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
