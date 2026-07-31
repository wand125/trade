from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT


FORWARD_DIAGNOSTIC_FIELDS = (
    "opened_at",
    "entry_server_hour",
    "m30_trend",
    "m15_trend",
    "m5_trend",
    "m30_slope",
    "m15_slope",
    "trend_alignment",
)
FORWARD_EXECUTION_FIELDS = (
    "entry",
    "sl",
    "deal_price",
    "stop_points",
    "spread_points",
    "latency_seconds",
    "hold_seconds",
)


def load_mt5_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def summarize_mt5_forward(
    rows: list[dict[str, str]],
    *,
    min_closed: int = 30,
    min_pf: float = 1.2,
    max_losing_streak_limit: int = 20,
    max_single_volume: float = 0.10,
    max_total_volume: float = 0.30,
    max_positions: int = 3,
    daily_loss_limit: float = 5000.0,
) -> dict[str, Any]:
    close_rows = [row for row in rows if str(row.get("event", "")).lower() == "close"]
    signal_rows = [row for row in rows if str(row.get("event", "")).lower() == "signal"]
    open_rows = [row for row in rows if str(row.get("event", "")).lower() == "open"]
    rejected_rows = [row for row in rows if str(row.get("event", "")).lower() == "reject"]
    button_rows = [row for row in rows if str(row.get("event", "")).lower() == "button"]

    overall = profit_summary(close_rows)
    execution = execution_summary(rows)
    reject = reject_summary(rejected_rows)
    detected_limits = detected_consecutive_loss_limits(rejected_rows)
    reject["detected_consecutive_loss_limits"] = detected_limits
    risk_exposure = risk_exposure_summary(
        rows,
        max_single_volume=max_single_volume,
        max_total_volume=max_total_volume,
        max_positions=max_positions,
        daily_loss_limit=daily_loss_limit,
        consecutive_loss_limit=max_losing_streak_limit,
    )
    csv_schema = csv_schema_diagnostics(rows, close_rows)
    summary = {
        "source_rows": len(rows),
        "signals": len(signal_rows),
        "opens": len(open_rows),
        "rejections": len(rejected_rows),
        "buttons": len(button_rows),
        "csv_schema": csv_schema,
        "signal": signal_summary(signal_rows),
        "reject": reject,
        "button": button_summary(button_rows),
        "overall": overall,
        "execution": execution,
        "risk_exposure": risk_exposure,
        "by_action": grouped_forward_summary(rows, "action"),
        "by_exit_reason": grouped_forward_summary(close_rows, "exit_reason"),
        "by_risk_reward": grouped_forward_summary(rows, "risk_reward"),
        "by_stop_points": grouped_forward_summary(rows, "action_stop_points_band"),
        "by_take_profit_points": grouped_forward_summary(rows, "action_take_profit_points_band"),
        "by_risk_reward_stop_points": grouped_forward_summary(rows, "action_rr_stop_points_band"),
        "by_risk_reward_take_profit_points": grouped_forward_summary(rows, "action_rr_take_profit_points_band"),
        "by_score_band": grouped_forward_summary(rows, "score_band"),
        "by_server_hour": grouped_forward_summary(rows, "server_hour"),
        "by_entry_server_hour": grouped_forward_summary(rows, "entry_server_hour"),
        "by_m30_trend": grouped_forward_summary(rows, "m30_trend"),
        "by_m15_trend": grouped_forward_summary(rows, "m15_trend"),
        "by_m5_trend": grouped_forward_summary(rows, "m5_trend"),
        "by_m30_slope": grouped_forward_summary(rows, "m30_slope"),
        "by_m15_slope": grouped_forward_summary(rows, "m15_slope"),
        "by_m30_m15_trend": grouped_forward_summary(rows, "m30_m15_trend"),
        "by_trend_alignment": grouped_forward_summary(rows, "trend_alignment"),
        "by_action_trend_alignment": grouped_forward_summary(rows, "action_trend_alignment"),
        "by_action_m30_m15_trend": grouped_forward_summary(rows, "action_m30_m15_trend"),
        "score_thresholds": score_threshold_summary(close_rows),
        "weak_sl_tp_segments": weak_sl_tp_segments(close_rows),
        "weak_time_segments": weak_time_segments(close_rows, min_closed=min_closed),
        "weak_trend_segments": weak_trend_segments(close_rows, min_closed=min_closed),
    }
    summary["side_score_diagnostics"] = side_score_diagnostics(summary["score_thresholds"], min_closed=min_closed)
    summary["checks"] = {
        "closed_samples": {
            "ok": overall["closed"] >= min_closed,
            "actual": overall["closed"],
            "required": min_closed,
        },
        "profit_factor": {
            "ok": overall["pf"] >= min_pf,
            "actual": overall["pf"],
            "required": min_pf,
        },
        "max_losing_streak": {
            "ok": overall["max_losing_streak"] <= max_losing_streak_limit,
            "actual": overall["max_losing_streak"],
            "required_max": max_losing_streak_limit,
        },
        "button_dry_run_only": {
            "ok": summary["button"]["unsafe"] == 0,
            "actual": summary["button"]["unsafe"],
            "required": 0,
        },
        "max_single_volume": {
            "ok": risk_exposure["max_single_volume"] <= max_single_volume + 1e-9,
            "actual": risk_exposure["max_single_volume"],
            "required_max": max_single_volume,
        },
        "max_concurrent_volume": {
            "ok": risk_exposure["max_concurrent_volume"] <= max_total_volume + 1e-9,
            "actual": risk_exposure["max_concurrent_volume"],
            "required_max": max_total_volume,
        },
        "max_concurrent_positions": {
            "ok": risk_exposure["max_concurrent_positions"] <= max_positions,
            "actual": risk_exposure["max_concurrent_positions"],
            "required_max": max_positions,
        },
        "daily_loss_stop_open_breaches": {
            "ok": risk_exposure["daily_loss_stop_open_breaches"] == 0,
            "actual": risk_exposure["daily_loss_stop_open_breaches"],
            "required": 0,
        },
        "consecutive_loss_stop_open_breaches": {
            "ok": risk_exposure["consecutive_loss_stop_open_breaches"] == 0,
            "actual": risk_exposure["consecutive_loss_stop_open_breaches"],
            "required": 0,
        },
    }
    summary["diagnostic_warnings"] = diagnostic_warnings(detected_limits, max_losing_streak_limit)
    summary["diagnostic_warnings"].extend(risk_exposure_warnings(risk_exposure))
    summary["diagnostic_warnings"].extend(csv_schema_warnings(csv_schema))
    summary["ready_for_demo_review"] = all(check["ok"] for check in summary["checks"].values())
    return summary


def button_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    messages = [str(row.get("message") or "").lower() for row in rows]
    actions = [str(row.get("action") or "").lower() for row in rows]
    safe_rows = sum(1 for message in messages if "dry-run" in message or "ignored" in message)
    return {
        "rows": len(rows),
        "dry_runs": sum(1 for message in messages if "dry-run" in message),
        "ignored": sum(1 for message in messages if "ignored" in message),
        "unsafe": len(rows) - safe_rows,
        "buy_clicks": actions.count("buy"),
        "sell_clicks": actions.count("sell"),
        "hold_or_other_clicks": sum(1 for action in actions if action not in {"buy", "sell"}),
    }


def signal_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    actions = Counter(str(row.get("action") or "").lower() for row in rows)
    scores = [value for value in (number(row.get("score")) for row in rows) if value is not None]
    buy_scores = [value for value in (number(row.get("buy_score")) for row in rows) if value is not None]
    sell_scores = [value for value in (number(row.get("sell_score")) for row in rows) if value is not None]
    return {
        "rows": len(rows),
        "buy": actions.get("buy", 0),
        "sell": actions.get("sell", 0),
        "hold": actions.get("hold", 0),
        "other": sum(count for action, count in actions.items() if action not in {"buy", "sell", "hold"}),
        "tradable": actions.get("buy", 0) + actions.get("sell", 0),
        "avg_score": avg(scores, digits=2),
        "avg_buy_score": avg(buy_scores, digits=2),
        "avg_sell_score": avg(sell_scores, digits=2),
        "top_reasons": top_text_counts(rows, "reason"),
    }


def reject_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    actions = Counter(str(row.get("action") or "").lower() for row in rows)
    return {
        "rows": len(rows),
        "buy": actions.get("buy", 0),
        "sell": actions.get("sell", 0),
        "hold_or_other": sum(count for action, count in actions.items() if action not in {"buy", "sell"}),
        "top_messages": top_text_counts(rows, "message"),
        "top_reasons": top_text_counts(rows, "reason"),
    }


def detected_consecutive_loss_limits(rows: list[dict[str, str]]) -> list[dict[str, int]]:
    pattern = re.compile(r"consecutive loss (?:cooldown active|stop reached)\s+\d+\s+>=\s+(\d+)")
    counts: Counter[int] = Counter()
    for row in rows:
        match = pattern.search(str(row.get("message") or ""))
        if match:
            counts[int(match.group(1))] += 1
    return [{"limit": limit, "count": count} for limit, count in sorted(counts.items())]


def diagnostic_warnings(detected_limits: list[dict[str, int]], expected_losing_streak_limit: int) -> list[str]:
    if not detected_limits:
        return []
    limits = [int(item["limit"]) for item in detected_limits]
    minimum = min(limits)
    if expected_losing_streak_limit > 0 and minimum < expected_losing_streak_limit:
        return [
            "CSV appears to use consecutive loss limit "
            f"{minimum}, below expected {expected_losing_streak_limit}; "
            "recompile the EA and load the updated tester set."
        ]
    return []


def csv_schema_diagnostics(rows: list[dict[str, str]], close_rows: list[dict[str, str]]) -> dict[str, Any]:
    present_fields = set()
    for row in rows:
        present_fields.update(row.keys())
    field_counts, missing_fields, unavailable_fields = csv_schema_field_group(
        rows,
        close_rows,
        present_fields,
        FORWARD_DIAGNOSTIC_FIELDS,
    )
    execution_field_counts, missing_execution_fields, unavailable_execution_fields = csv_schema_field_group(
        rows,
        rows,
        present_fields,
        FORWARD_EXECUTION_FIELDS,
    )
    return {
        "required_fields": list(FORWARD_DIAGNOSTIC_FIELDS),
        "execution_required_fields": list(FORWARD_EXECUTION_FIELDS),
        "close_rows": len(close_rows),
        "missing_fields": missing_fields,
        "unavailable_fields": unavailable_fields,
        "missing_execution_fields": missing_execution_fields,
        "unavailable_execution_fields": unavailable_execution_fields,
        "field_counts": field_counts,
        "execution_field_counts": execution_field_counts,
        "entry_time_diagnostics_available": bool(close_rows)
        and "opened_at" not in unavailable_fields
        and "entry_server_hour" not in unavailable_fields,
        "trend_diagnostics_available": bool(close_rows)
        and "m30_trend" not in unavailable_fields
        and "m15_trend" not in unavailable_fields
        and "m5_trend" not in unavailable_fields
        and "m30_slope" not in unavailable_fields
        and "m15_slope" not in unavailable_fields
        and "trend_alignment" not in unavailable_fields,
        "execution_diagnostics_available": bool(close_rows)
        and not missing_execution_fields
        and not unavailable_execution_fields,
    }


def csv_schema_field_group(
    rows: list[dict[str, str]],
    availability_rows: list[dict[str, str]],
    present_fields: set[str],
    fields: tuple[str, ...],
) -> tuple[dict[str, dict[str, int]], list[str], list[str]]:
    field_counts: dict[str, dict[str, int]] = {}
    missing_fields: list[str] = []
    unavailable_fields: list[str] = []
    for field in fields:
        if field not in present_fields:
            missing_fields.append(field)
        informative = sum(1 for row in availability_rows if informative_csv_value(row.get(field)))
        non_empty = sum(1 for row in availability_rows if str(row.get(field) or "").strip())
        field_counts[field] = {
            "non_empty": non_empty,
            "informative": informative,
        }
        if rows and availability_rows and informative == 0:
            unavailable_fields.append(field)
    return field_counts, missing_fields, unavailable_fields


def informative_csv_value(value: object) -> bool:
    text = str(value or "").strip().lower()
    return bool(text) and text not in {"unknown", "nan", "none", "null"}


def csv_schema_warnings(schema: dict[str, Any]) -> list[str]:
    if not schema or int(schema.get("close_rows") or 0) <= 0:
        return []
    missing = schema.get("missing_fields")
    unavailable = schema.get("unavailable_fields")
    if isinstance(missing, list) and missing:
        return [
            "Forward CSV is missing diagnostic fields "
            f"{', '.join(str(item) for item in missing)}; "
            "rerun with the current EA before using entry-hour/trend diagnostics."
        ]
    if isinstance(unavailable, list) and unavailable:
        return [
            "Forward CSV has no informative values for diagnostic fields "
            f"{', '.join(str(item) for item in unavailable)}; "
            "rerun with the current EA before using entry-hour/trend diagnostics."
        ]
    missing_execution = schema.get("missing_execution_fields")
    unavailable_execution = schema.get("unavailable_execution_fields")
    if isinstance(missing_execution, list) and missing_execution:
        return [
            "Forward CSV is missing execution fields "
            f"{', '.join(str(item) for item in missing_execution)}; "
            "rerun with the current EA before using price-R, slippage, spread, or latency diagnostics."
        ]
    if isinstance(unavailable_execution, list) and unavailable_execution:
        return [
            "Forward CSV has no informative values for execution fields "
            f"{', '.join(str(item) for item in unavailable_execution)}; "
            "rerun with the current EA before using price-R, slippage, spread, or latency diagnostics."
        ]
    return []


def risk_exposure_summary(
    rows: list[dict[str, str]],
    *,
    max_single_volume: float,
    max_total_volume: float,
    max_positions: int,
    daily_loss_limit: float,
    consecutive_loss_limit: int,
) -> dict[str, Any]:
    active: dict[str, float] = {}
    max_single_seen = 0.0
    max_concurrent_volume = 0.0
    max_concurrent_positions = 0
    daily_values: list[float] = []
    consecutive_values: list[int] = []
    daily_breach_opens = 0
    consecutive_breach_opens = 0
    daily_stop_rejections = 0
    consecutive_stop_rejections = 0
    lot_limit_rejections = 0
    session_resets = 0
    preclosed_close_indices: set[int] = set()
    previous_time: datetime | None = None
    previous_closed_trades: int | None = None

    for index, row in enumerate(rows):
        current_time = server_datetime(row)
        closed_trades_value = number(row.get("closed_trades"))
        closed_trades = int(closed_trades_value) if closed_trades_value is not None else None
        if (
            (current_time is not None and previous_time is not None and current_time < previous_time)
            or (
                closed_trades is not None
                and previous_closed_trades is not None
                and closed_trades < previous_closed_trades
            )
        ):
            active.clear()
            session_resets += 1
        event = str(row.get("event") or "").lower()
        message = str(row.get("message") or "").lower()
        volume = max(0.0, number(row.get("volume")) or 0.0)
        daily_net = number(row.get("daily_net_profit"))
        consecutive_losses = number(row.get("consecutive_losses"))
        if daily_net is not None:
            daily_values.append(daily_net)
        if consecutive_losses is not None:
            consecutive_values.append(int(consecutive_losses))

        if event == "reject":
            if "daily loss stop reached" in message:
                daily_stop_rejections += 1
            if "consecutive loss cooldown active" in message or "consecutive loss stop reached" in message:
                consecutive_stop_rejections += 1
            if (
                "lot outside configured limits" in message
                or "max positions reached" in message
                or "max total lot reached" in message
            ):
                lot_limit_rejections += 1
            if current_time is not None:
                previous_time = current_time
            if closed_trades is not None:
                previous_closed_trades = closed_trades
            continue

        if event == "open":
            preclose_same_timestamp_positions(rows, index, current_time, active, preclosed_close_indices)
            max_single_seen = max(max_single_seen, volume)
            if daily_loss_limit > 0 and daily_net is not None and daily_net <= -abs(daily_loss_limit):
                daily_breach_opens += 1
            if (
                consecutive_loss_limit > 0
                and consecutive_losses is not None
                and int(consecutive_losses) >= consecutive_loss_limit
            ):
                consecutive_breach_opens += 1
            active[position_key(row, index)] = volume
            max_concurrent_positions = max(max_concurrent_positions, len(active))
            max_concurrent_volume = max(max_concurrent_volume, sum(active.values()))
            if current_time is not None:
                previous_time = current_time
            if closed_trades is not None:
                previous_closed_trades = closed_trades
            continue

        if event == "close":
            key = position_key(row, index)
            if key in active:
                active.pop(key, None)
            elif active and index not in preclosed_close_indices:
                active.pop(next(iter(active)))

        if current_time is not None:
            previous_time = current_time
        if closed_trades is not None:
            previous_closed_trades = closed_trades

    return {
        "max_single_volume": round(max_single_seen, 2),
        "max_concurrent_volume": round(max_concurrent_volume, 2),
        "max_concurrent_positions": max_concurrent_positions,
        "open_positions_at_end": len(active),
        "open_volume_at_end": round(sum(active.values()), 2),
        "session_resets": session_resets,
        "max_single_volume_limit": max_single_volume,
        "max_total_volume_limit": max_total_volume,
        "max_positions_limit": max_positions,
        "min_daily_net_profit": round(min(daily_values), 2) if daily_values else 0.0,
        "daily_loss_limit": daily_loss_limit,
        "max_observed_consecutive_losses": max(consecutive_values) if consecutive_values else 0,
        "consecutive_loss_limit": consecutive_loss_limit,
        "daily_loss_stop_open_breaches": daily_breach_opens,
        "consecutive_loss_stop_open_breaches": consecutive_breach_opens,
        "daily_loss_stop_rejections": daily_stop_rejections,
        "consecutive_loss_stop_rejections": consecutive_stop_rejections,
        "lot_limit_rejections": lot_limit_rejections,
    }


def preclose_same_timestamp_positions(
    rows: list[dict[str, str]],
    open_index: int,
    current_time: datetime | None,
    active: dict[str, float],
    preclosed_close_indices: set[int],
) -> None:
    if current_time is None or not active:
        return
    for lookahead in range(open_index + 1, len(rows)):
        row = rows[lookahead]
        next_time = server_datetime(row)
        if next_time != current_time:
            break
        if str(row.get("event") or "").lower() != "close":
            continue
        key = position_key(row, lookahead)
        if key not in active:
            continue
        active.pop(key, None)
        preclosed_close_indices.add(lookahead)


def position_key(row: dict[str, str], index: int) -> str:
    for key in ("position_id", "order", "deal"):
        value = str(row.get(key) or "").strip()
        if value and value != "0":
            return f"{key}:{value}"
    opened_at = str(row.get("opened_at") or "").strip()
    action = str(row.get("action") or "").strip()
    if opened_at or action:
        return f"fallback:{action}:{opened_at}:{index}"
    return f"row:{index}"


def risk_exposure_warnings(risk: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if int(risk.get("daily_loss_stop_open_breaches") or 0) > 0:
        warnings.append("Open rows were observed after daily loss stop conditions; verify EA daily loss stop settings.")
    if int(risk.get("consecutive_loss_stop_open_breaches") or 0) > 0:
        warnings.append("Open rows were observed after consecutive-loss stop conditions; verify EA cooldown settings.")
    if float(risk.get("max_single_volume") or 0.0) > float(risk.get("max_single_volume_limit") or 0.0) + 1e-9:
        warnings.append("Observed single order volume exceeds the configured safety baseline.")
    if float(risk.get("max_concurrent_volume") or 0.0) > float(risk.get("max_total_volume_limit") or 0.0) + 1e-9:
        warnings.append("Observed concurrent volume exceeds the configured total lot cap.")
    if int(risk.get("max_concurrent_positions") or 0) > int(risk.get("max_positions_limit") or 0):
        warnings.append("Observed concurrent position count exceeds the configured cap.")
    return warnings


def top_text_counts(rows: list[dict[str, str]], key: str, *, limit: int = 5) -> list[dict[str, object]]:
    values = Counter(clean_text(row.get(key)) for row in rows)
    values.pop("", None)
    return [{"text": text, "count": count} for text, count in values.most_common(limit)]


def clean_text(value: object) -> str:
    return str(value or "").strip()


def profit_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: str(row.get("server_time", "")))
    values = [number(row.get("net_profit")) or 0.0 for row in ordered]
    r_values = [value for value in (price_r_multiple(row) for row in ordered) if value is not None]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    breakeven = [value for value in values if value == 0]
    gross_profit = sum(wins)
    gross_loss = -sum(losses)
    closed = len(values)
    avg_price_r = round(sum(r_values) / len(r_values), 4) if r_values else 0.0
    return {
        "closed": closed,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(breakeven),
        "win_rate": round(len(wins) / closed, 4) if closed else 0.0,
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "net_profit": round(sum(values), 2),
        "avg_net": round(sum(values) / closed, 2) if closed else 0.0,
        "pf": round(gross_profit / gross_loss, 4) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0),
        "max_losing_streak": max_losing_streak(ordered),
        "avg_price_r": avg_price_r,
        "price_r_count": len(r_values),
        "max_drawdown_price_r": round(max_drawdown(r_values), 4),
        "expectancy_price_r": avg_price_r,
    }


def execution_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    open_rows = [row for row in rows if str(row.get("event", "")).lower() == "open"]
    close_rows = [row for row in rows if str(row.get("event", "")).lower() == "close"]
    slippages = [value for value in (slippage_points(row) for row in open_rows) if value is not None]
    spreads = [value for value in (number(row.get("spread_points")) for row in rows) if value is not None]
    latencies = [value for value in (number(row.get("latency_seconds")) for row in open_rows) if value is not None]
    hold_times = [value for value in (number(row.get("hold_seconds")) for row in close_rows) if value is not None]
    r_values = [value for value in (price_r_multiple(row) for row in close_rows) if value is not None]
    exit_reasons = [exit_reason(row) for row in close_rows]
    return {
        "open_rows": len(open_rows),
        "close_rows": len(close_rows),
        "tp_closes": exit_reasons.count("tp"),
        "sl_closes": exit_reasons.count("sl"),
        "early_or_manual_closes": sum(1 for reason in exit_reasons if reason.startswith("early_") or reason == "breakeven"),
        "avg_latency_seconds": avg(latencies),
        "max_latency_seconds": round(max(latencies), 2) if latencies else 0.0,
        "avg_hold_seconds": avg(hold_times),
        "max_hold_seconds": round(max(hold_times), 2) if hold_times else 0.0,
        "avg_slippage_points": avg(slippages),
        "max_abs_slippage_points": round(max((abs(value) for value in slippages), default=0.0), 2),
        "avg_spread_points": avg(spreads),
        "max_spread_points": round(max(spreads), 2) if spreads else 0.0,
        "avg_price_r": avg(r_values, digits=4),
        "price_r_count": len(r_values),
    }


def slippage_points(row: dict[str, str]) -> float | None:
    entry = number(row.get("entry"))
    deal_price = number(row.get("deal_price"))
    point = inferred_point(row)
    action = str(row.get("action") or "").lower()
    if entry is None or deal_price is None or point is None or point <= 0:
        return None
    if action == "sell":
        return round((entry - deal_price) / point, 2)
    return round((deal_price - entry) / point, 2)


def price_r_multiple(row: dict[str, str]) -> float | None:
    action = str(row.get("action") or "").lower()
    entry = number(row.get("entry"))
    sl = number(row.get("sl"))
    deal_price = number(row.get("deal_price"))
    if action not in {"buy", "sell"} or entry is None or sl is None or deal_price is None:
        return None
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    if action == "buy":
        return round((deal_price - entry) / risk, 6)
    return round((entry - deal_price) / risk, 6)


def exit_reason(row: dict[str, str]) -> str:
    action = str(row.get("action") or "").lower()
    deal_price = number(row.get("deal_price"))
    sl = number(row.get("sl"))
    tp = number(row.get("tp"))
    if action not in {"buy", "sell"} or deal_price is None:
        return "unknown"

    point = inferred_point(row) or 0.0
    tolerance = max(point * 2.0, 0.0)
    if tp is not None and abs(deal_price - tp) <= tolerance:
        return "tp"
    if sl is not None and abs(deal_price - sl) <= tolerance:
        return "sl"

    value = number(row.get("net_profit"))
    if value is None:
        value = price_r_multiple(row)
    if value is None:
        return "other"
    if value > 0:
        return "early_profit"
    if value < 0:
        return "early_loss"
    return "breakeven"


def inferred_point(row: dict[str, str]) -> float | None:
    stop_points = number(row.get("stop_points"))
    entry = number(row.get("entry"))
    sl = number(row.get("sl"))
    if stop_points is None or stop_points <= 0 or entry is None or sl is None:
        return None
    return abs(entry - sl) / stop_points


def avg(values: list[float], *, digits: int = 2) -> float:
    return round(sum(values) / len(values), digits) if values else 0.0


def grouped_forward_summary(rows: list[dict[str, str]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        group = group_value(row, key)
        grouped[group].append(row)
    results = []
    for group, group_rows in sorted(grouped.items(), key=lambda item: group_sort_key(item[0])):
        close_rows = [row for row in group_rows if str(row.get("event", "")).lower() == "close"]
        if not close_rows:
            continue
        execution = execution_summary(group_rows)
        results.append(
            {
                "group": group,
                **profit_summary(close_rows),
                "avg_latency_seconds": execution["avg_latency_seconds"],
                "avg_hold_seconds": execution["avg_hold_seconds"],
                "avg_slippage_points": execution["avg_slippage_points"],
                "avg_spread_points": execution["avg_spread_points"],
                "tp_closes": execution["tp_closes"],
                "sl_closes": execution["sl_closes"],
                "early_or_manual_closes": execution["early_or_manual_closes"],
            }
        )
    return results


def weak_sl_tp_segments(
    close_rows: list[dict[str, str]],
    *,
    min_closed: int = 100,
    limit: int = 12,
) -> list[dict[str, Any]]:
    dimensions = (
        ("action_rr", "action_risk_reward"),
        ("action_sl", "action_stop_points_band"),
        ("action_tp", "action_take_profit_points_band"),
        ("action_rr_sl", "action_rr_stop_points_band"),
        ("action_rr_tp", "action_rr_take_profit_points_band"),
    )
    rows: list[dict[str, Any]] = []
    for dimension, key in dimensions:
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in close_rows:
            grouped[group_value(row, key)].append(row)
        for group, group_rows in grouped.items():
            if len(group_rows) < min_closed:
                continue
            profit = profit_summary(group_rows)
            execution = execution_summary(group_rows)
            if profit["pf"] >= 1.0 and profit["avg_price_r"] >= 0.0:
                continue
            closed = max(int(profit["closed"]), 1)
            exit_counts = exit_reason_counts(group_rows)
            rows.append(
                {
                    "dimension": dimension,
                    "group": group,
                    **profit,
                    "tp_closes": execution["tp_closes"],
                    "sl_closes": execution["sl_closes"],
                    "early_loss_closes": exit_counts.get("early_loss", 0),
                    "early_profit_closes": exit_counts.get("early_profit", 0),
                    "tp_rate": round(execution["tp_closes"] / closed, 4),
                    "sl_rate": round(execution["sl_closes"] / closed, 4),
                    "early_loss_rate": round(exit_counts.get("early_loss", 0) / closed, 4),
                    "diagnosis": sl_tp_segment_diagnosis(group_rows),
                }
            )
    rows.sort(key=lambda row: (float(row.get("pf") or 0.0), float(row.get("net_profit") or 0.0), -int(row.get("closed") or 0)))
    return rows[:limit]


def weak_time_segments(
    close_rows: list[dict[str, str]],
    *,
    min_closed: int,
    limit: int = 12,
) -> list[dict[str, Any]]:
    dimensions = (
        ("server_hour", "server_hour"),
        ("entry_server_hour", "entry_server_hour"),
        ("server_weekday", "server_weekday"),
        ("server_month", "server_month"),
        ("action_rr_month", "action_risk_reward_month"),
    )
    return weak_regime_segments(
        close_rows,
        dimensions=dimensions,
        min_closed=min_closed,
        limit=limit,
        diagnosis_fn=time_segment_diagnosis,
    )


def weak_trend_segments(
    close_rows: list[dict[str, str]],
    *,
    min_closed: int,
    limit: int = 12,
) -> list[dict[str, Any]]:
    dimensions = (
        ("m30_trend", "m30_trend"),
        ("m15_trend", "m15_trend"),
        ("m5_trend", "m5_trend"),
        ("m30_slope", "m30_slope"),
        ("m15_slope", "m15_slope"),
        ("m30_m15_trend", "m30_m15_trend"),
        ("trend_alignment", "trend_alignment"),
        ("action_trend_alignment", "action_trend_alignment"),
        ("action_m30_m15_trend", "action_m30_m15_trend"),
    )
    return weak_regime_segments(
        close_rows,
        dimensions=dimensions,
        min_closed=min_closed,
        limit=limit,
        diagnosis_fn=trend_segment_diagnosis,
    )


def weak_regime_segments(
    close_rows: list[dict[str, str]],
    *,
    dimensions: tuple[tuple[str, str], ...],
    min_closed: int,
    limit: int,
    diagnosis_fn,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dimension, key in dimensions:
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in close_rows:
            grouped[group_value(row, key)].append(row)
        for group, group_rows in grouped.items():
            if len(group_rows) < min_closed:
                continue
            profit = profit_summary(group_rows)
            if profit["pf"] >= 1.0 and profit["avg_price_r"] >= 0.0:
                continue
            payload = {"dimension": dimension, "group": group, **profit}
            payload["diagnosis"] = diagnosis_fn(payload)
            rows.append(payload)
    rows.sort(key=lambda row: (float(row.get("pf") or 0.0), float(row.get("net_profit") or 0.0), -int(row.get("closed") or 0)))
    return rows[:limit]


def time_segment_diagnosis(row: dict[str, Any]) -> str:
    dimension = str(row.get("dimension") or "")
    group = str(row.get("group") or "")
    pf = float(row.get("pf") or 0.0)
    avg_r = float(row.get("avg_price_r") or 0.0)
    closed = int(row.get("closed") or 0)
    if dimension == "action_rr_month":
        return f"RR/month regime failed: {group}; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"
    if dimension == "entry_server_hour":
        return f"entry-hour regime failed: {group}; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"
    if dimension == "server_hour":
        return f"hour-of-day regime failed: {group}; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"
    if dimension == "server_weekday":
        return f"weekday regime failed: {group}; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"
    if dimension == "server_month":
        return f"time regime failed: {group}; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"
    return f"time segment failed: {group}; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"


def trend_segment_diagnosis(row: dict[str, Any]) -> str:
    group = str(row.get("group") or "")
    pf = float(row.get("pf") or 0.0)
    avg_r = float(row.get("avg_price_r") or 0.0)
    closed = int(row.get("closed") or 0)
    if "unknown" in group:
        return f"trend regime unavailable in CSV; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"
    return f"trend regime failed: {group}; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"


def exit_reason_counts(rows: list[dict[str, str]]) -> Counter[str]:
    return Counter(exit_reason(row) for row in rows)


def sl_tp_segment_diagnosis(rows: list[dict[str, str]]) -> str:
    closed = len(rows)
    if closed <= 0:
        return "no closed trades"
    counts = exit_reason_counts(rows)
    tp_rate = counts.get("tp", 0) / closed
    sl_rate = counts.get("sl", 0) / closed
    early_loss_rate = counts.get("early_loss", 0) / closed
    loss_exit_rate = sl_rate + early_loss_rate
    avg_stop = avg([value for value in (number(row.get("stop_points")) for row in rows) if value is not None])
    avg_tp = avg([value for value in (take_profit_points(row) for row in rows) if value is not None])

    if tp_rate < 0.08 and loss_exit_rate >= 0.80:
        return f"TP capture too low; SL/early losses dominate; avg SL {avg_stop}pt avg TP {avg_tp}pt"
    if early_loss_rate > sl_rate and early_loss_rate >= 0.45:
        return f"early losses dominate before planned TP; avg SL {avg_stop}pt avg TP {avg_tp}pt"
    if sl_rate >= 0.35:
        return f"planned SL hit too often; avg SL {avg_stop}pt avg TP {avg_tp}pt"
    if avg_tp > 0.0 and avg_stop > 0.0 and avg_tp / avg_stop >= 4.5 and tp_rate < 0.12:
        return f"TP line likely too far for setup; avg SL {avg_stop}pt avg TP {avg_tp}pt"
    return f"negative edge; avg SL {avg_stop}pt avg TP {avg_tp}pt"


def score_threshold_summary(
    close_rows: list[dict[str, str]],
    *,
    thresholds: tuple[int, ...] = (50, 60, 70, 80, 90, 100, 110),
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for side in ("all", "buy", "sell"):
        side_rows = close_rows if side == "all" else [row for row in close_rows if str(row.get("action") or "").lower() == side]
        for threshold in thresholds:
            rows = [row for row in side_rows if (number(row.get("score")) or 0.0) >= threshold]
            results.append(
                {
                    "side": side,
                    "threshold": threshold,
                    **profit_summary(rows),
                }
            )
    return results


def side_score_diagnostics(threshold_rows: list[dict[str, Any]], *, min_closed: int = 30) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for side in ("buy", "sell"):
        rows = [row for row in threshold_rows if row.get("side") == side and int(row.get("closed") or 0) >= min_closed]
        if not rows:
            diagnostics.append(
                {
                    "side": side,
                    "status": "insufficient_samples",
                    "base_threshold": "",
                    "base_pf": 0.0,
                    "best_pf_threshold": "",
                    "best_pf": 0.0,
                    "high_threshold": "",
                    "high_pf": 0.0,
                    "pf_delta_best_vs_base": 0.0,
                    "pf_delta_high_vs_base": 0.0,
                    "avg_r_delta_high_vs_base": 0.0,
                    "recommendation": "collect more closed samples",
                }
            )
            continue

        rows = sorted(rows, key=lambda row: int(row.get("threshold") or 0))
        base = rows[0]
        best = max(rows, key=lambda row: (float(row.get("pf") or 0.0), float(row.get("avg_price_r") or 0.0)))
        high = rows[-1]

        base_pf = float(base.get("pf") or 0.0)
        best_pf = float(best.get("pf") or 0.0)
        high_pf = float(high.get("pf") or 0.0)
        base_avg_r = float(base.get("avg_price_r") or 0.0)
        high_avg_r = float(high.get("avg_price_r") or 0.0)
        pf_delta_best = round(best_pf - base_pf, 4)
        pf_delta_high = round(high_pf - base_pf, 4)
        avg_r_delta_high = round(high_avg_r - base_avg_r, 4)

        if high_pf < base_pf - 0.10 and (high_avg_r < base_avg_r - 0.05 or high_pf < best_pf - 0.10):
            status = "score_inversion"
            recommendation = "refit side-specific scoring; avoid high-score gate for this side"
        elif best_pf >= 1.0 and pf_delta_best > 0:
            status = "candidate_gate"
            recommendation = f"candidate gate: {side} score >= {best.get('threshold')}"
        elif pf_delta_best > 0.05:
            status = "weak_improvement"
            recommendation = f"watch {side} score >= {best.get('threshold')}, but do not promote yet"
        else:
            status = "no_edge"
            recommendation = "score threshold does not create a tradable edge"

        diagnostics.append(
            {
                "side": side,
                "status": status,
                "base_threshold": base.get("threshold"),
                "base_pf": base_pf,
                "best_pf_threshold": best.get("threshold"),
                "best_pf": best_pf,
                "high_threshold": high.get("threshold"),
                "high_pf": high_pf,
                "pf_delta_best_vs_base": pf_delta_best,
                "pf_delta_high_vs_base": pf_delta_high,
                "avg_r_delta_high_vs_base": avg_r_delta_high,
                "recommendation": recommendation,
            }
        )
    return diagnostics


def group_value(row: dict[str, str], key: str) -> str:
    if key == "score_band":
        return score_band(number(row.get("score")) or 0.0)
    if key == "exit_reason":
        return exit_reason(row)
    if key == "server_month":
        return server_month(row)
    if key == "server_quarter":
        return server_quarter(row)
    if key == "server_weekday":
        return server_weekday(row)
    if key == "server_hour":
        return server_hour(row)
    if key == "entry_server_hour":
        return entry_server_hour(row)
    if key == "m30_trend":
        return trend_value(row, "m30_trend")
    if key == "m15_trend":
        return trend_value(row, "m15_trend")
    if key == "m5_trend":
        return trend_value(row, "m5_trend")
    if key == "m30_slope":
        return trend_value(row, "m30_slope")
    if key == "m15_slope":
        return trend_value(row, "m15_slope")
    if key == "m30_m15_trend":
        return f"M30 {trend_value(row, 'm30_trend')} M15 {trend_value(row, 'm15_trend')}"
    if key == "trend_alignment":
        return trend_value(row, "trend_alignment")
    if key == "action_trend_alignment":
        return f"{trade_action(row)} {trend_value(row, 'trend_alignment')}"
    if key == "action_m30_m15_trend":
        return f"{trade_action(row)} M30 {trend_value(row, 'm30_trend')} M15 {trend_value(row, 'm15_trend')}"
    if key == "action_risk_reward":
        return f"{trade_action(row)} RR {risk_reward_value(row)}"
    if key == "action_risk_reward_month":
        return f"{trade_action(row)} RR {risk_reward_value(row)} {server_month(row)}"
    if key == "action_stop_points_band":
        return f"{trade_action(row)} SL {point_band(number(row.get('stop_points')), step=50)}"
    if key == "action_take_profit_points_band":
        return f"{trade_action(row)} TP {point_band(take_profit_points(row), step=100)}"
    if key == "action_rr_stop_points_band":
        return f"{trade_action(row)} RR {risk_reward_value(row)} SL {point_band(number(row.get('stop_points')), step=50)}"
    if key == "action_rr_take_profit_points_band":
        return f"{trade_action(row)} RR {risk_reward_value(row)} TP {point_band(take_profit_points(row), step=100)}"
    return str(row.get(key) or "")


def trend_value(row: dict[str, str], key: str) -> str:
    text = str(row.get(key) or "").strip().lower()
    return text if text else "unknown"


def parse_datetime_text(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def server_datetime(row: dict[str, str]) -> datetime | None:
    return parse_datetime_text(row.get("server_time"))


def entry_datetime(row: dict[str, str]) -> datetime | None:
    return parse_datetime_text(row.get("opened_at"))


def server_month(row: dict[str, str]) -> str:
    moment = server_datetime(row)
    return moment.strftime("%Y-%m") if moment else "unknown"


def server_quarter(row: dict[str, str]) -> str:
    moment = server_datetime(row)
    if moment is None:
        return "unknown"
    quarter = (moment.month - 1) // 3 + 1
    return f"{moment.year}-Q{quarter}"


def server_weekday(row: dict[str, str]) -> str:
    moment = server_datetime(row)
    return moment.strftime("%a") if moment else "unknown"


def server_hour(row: dict[str, str]) -> str:
    moment = server_datetime(row)
    if moment is None:
        return "unknown"
    return f"{moment.hour:02d}:00-{(moment.hour + 1) % 24:02d}:00"


def entry_server_hour(row: dict[str, str]) -> str:
    direct = str(row.get("entry_server_hour") or "").strip()
    if direct:
        return direct
    moment = entry_datetime(row)
    if moment is None:
        return "unknown"
    return f"{moment.hour:02d}:00-{(moment.hour + 1) % 24:02d}:00"


def trade_action(row: dict[str, str]) -> str:
    action = str(row.get("action") or "").lower()
    return action if action in {"buy", "sell"} else "other"


def risk_reward_value(row: dict[str, str]) -> str:
    value = number(row.get("risk_reward"))
    return f"{value:.2f}" if value is not None else "unknown"


def take_profit_points(row: dict[str, str]) -> float | None:
    entry = number(row.get("entry"))
    tp = number(row.get("tp"))
    point = inferred_point(row)
    if entry is None or tp is None or point is None or point <= 0:
        return None
    return abs(tp - entry) / point


def point_band(value: float | None, *, step: int) -> str:
    if value is None:
        return "unknown"
    lower = int(max(value, 0.0) // step * step)
    return f"{lower}-{lower + step}pt"


def group_sort_key(value: str) -> tuple[Any, ...]:
    text = str(value)
    numbers = tuple(float(match) for match in re.findall(r"-?\d+(?:\.\d+)?", text))
    side_order = 0 if text.startswith("buy") else 1 if text.startswith("sell") else 2
    return (side_order, numbers, text)


def max_losing_streak(rows: list[dict[str, str]]) -> int:
    streak = 0
    maximum = 0
    for row in rows:
        value = number(row.get("net_profit")) or 0.0
        if value < 0:
            streak += 1
            maximum = max(maximum, streak)
        elif value > 0:
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


def score_band(score: float) -> str:
    lower = int(score // 10 * 10)
    return f"{lower}-{lower + 10}"


def number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def write_json(path: str | Path, summary: dict[str, Any], rows: list[dict[str, str]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": True,
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "summary": summary,
        "rows_count": len(rows),
        "rows_sample": row_sample(rows),
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def row_sample(rows: list[dict[str, str]], *, sample_size: int = 3) -> list[dict[str, str]]:
    if len(rows) <= sample_size * 2:
        return rows
    return rows[:sample_size] + rows[-sample_size:]


def format_markdown(summary: dict[str, Any]) -> str:
    overall = summary["overall"]
    checks = summary["checks"]
    risk = summary.get("risk_exposure", {})
    lines = [
        "# MT5 Forward Report",
        "",
        f"- Source rows: {summary.get('source_rows')}",
        f"- Signals/Open/Rejections: {summary.get('signals')} / {summary.get('opens')} / {summary.get('rejections')}",
        f"- Signal buy/sell/hold: {summary.get('signal', {}).get('buy')} / {summary.get('signal', {}).get('sell')} / {summary.get('signal', {}).get('hold')}",
        f"- Signal avg score: {summary.get('signal', {}).get('avg_score')}",
        f"- Buttons dry-run/ignored: {summary.get('button', {}).get('dry_runs')} / {summary.get('button', {}).get('ignored')}",
        f"- Button unsafe: {summary.get('button', {}).get('unsafe')}",
        f"- Button buy/sell/wait: {summary.get('button', {}).get('buy_clicks')} / {summary.get('button', {}).get('sell_clicks')} / {summary.get('button', {}).get('hold_or_other_clicks')}",
        f"- Closed: {overall.get('closed')}",
        f"- Wins/Losses/Breakeven: {overall.get('wins')} / {overall.get('losses')} / {overall.get('breakeven')}",
        f"- Win rate: {overall.get('win_rate')}",
        f"- Net profit: {overall.get('net_profit')}",
        f"- PF: {overall.get('pf')}",
        f"- Max losing streak: {overall.get('max_losing_streak')}",
        f"- Avg price R: {overall.get('avg_price_r')}",
        f"- Max drawdown price R: {overall.get('max_drawdown_price_r')}",
        f"- Expectancy price R: {overall.get('expectancy_price_r')}",
        f"- Ready for demo review: {summary.get('ready_for_demo_review')}",
        f"- Max single/concurrent lot: {risk.get('max_single_volume') if isinstance(risk, dict) else ''} / {risk.get('max_concurrent_volume') if isinstance(risk, dict) else ''}",
        f"- Max concurrent positions: {risk.get('max_concurrent_positions') if isinstance(risk, dict) else ''}",
        "",
        "## Diagnostic Warnings",
        "",
    ]
    warnings = summary.get("diagnostic_warnings")
    if isinstance(warnings, list) and warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- None.")
    schema = summary.get("csv_schema") if isinstance(summary.get("csv_schema"), dict) else {}
    lines.extend(
        [
            "",
            "## CSV Schema Diagnostics",
            "",
            f"- Close rows: {schema.get('close_rows', '')}",
            f"- Entry-time diagnostics available: {schema.get('entry_time_diagnostics_available', '')}",
            f"- Trend diagnostics available: {schema.get('trend_diagnostics_available', '')}",
            f"- Execution diagnostics available: {schema.get('execution_diagnostics_available', '')}",
            f"- Missing fields: {', '.join(map(str, schema.get('missing_fields', []))) if isinstance(schema.get('missing_fields'), list) and schema.get('missing_fields') else 'None'}",
            f"- Unavailable fields: {', '.join(map(str, schema.get('unavailable_fields', []))) if isinstance(schema.get('unavailable_fields'), list) and schema.get('unavailable_fields') else 'None'}",
            f"- Missing execution fields: {', '.join(map(str, schema.get('missing_execution_fields', []))) if isinstance(schema.get('missing_execution_fields'), list) and schema.get('missing_execution_fields') else 'None'}",
            f"- Unavailable execution fields: {', '.join(map(str, schema.get('unavailable_execution_fields', []))) if isinstance(schema.get('unavailable_execution_fields'), list) and schema.get('unavailable_execution_fields') else 'None'}",
        ]
    )
    lines.extend(
        [
            "",
            "## Execution",
            "",
            f"- Avg latency seconds: {summary.get('execution', {}).get('avg_latency_seconds')}",
            f"- Max latency seconds: {summary.get('execution', {}).get('max_latency_seconds')}",
            f"- Avg hold seconds: {summary.get('execution', {}).get('avg_hold_seconds')}",
            f"- Max hold seconds: {summary.get('execution', {}).get('max_hold_seconds')}",
            f"- TP/SL/Early closes: {summary.get('execution', {}).get('tp_closes')} / {summary.get('execution', {}).get('sl_closes')} / {summary.get('execution', {}).get('early_or_manual_closes')}",
            f"- Avg slippage points: {summary.get('execution', {}).get('avg_slippage_points')}",
            f"- Max abs slippage points: {summary.get('execution', {}).get('max_abs_slippage_points')}",
            f"- Avg spread points: {summary.get('execution', {}).get('avg_spread_points')}",
            f"- Max spread points: {summary.get('execution', {}).get('max_spread_points')}",
            "",
            "## Risk Exposure",
            "",
            f"- Max single volume: {risk.get('max_single_volume') if isinstance(risk, dict) else ''} / limit {risk.get('max_single_volume_limit') if isinstance(risk, dict) else ''}",
            f"- Max concurrent volume: {risk.get('max_concurrent_volume') if isinstance(risk, dict) else ''} / limit {risk.get('max_total_volume_limit') if isinstance(risk, dict) else ''}",
            f"- Max concurrent positions: {risk.get('max_concurrent_positions') if isinstance(risk, dict) else ''} / limit {risk.get('max_positions_limit') if isinstance(risk, dict) else ''}",
            f"- Min daily net profit: {risk.get('min_daily_net_profit') if isinstance(risk, dict) else ''} / daily loss limit {risk.get('daily_loss_limit') if isinstance(risk, dict) else ''}",
            f"- Max observed consecutive losses: {risk.get('max_observed_consecutive_losses') if isinstance(risk, dict) else ''} / limit {risk.get('consecutive_loss_limit') if isinstance(risk, dict) else ''}",
            f"- Stop-breach opens daily/consecutive: {risk.get('daily_loss_stop_open_breaches') if isinstance(risk, dict) else ''} / {risk.get('consecutive_loss_stop_open_breaches') if isinstance(risk, dict) else ''}",
            f"- Stop/lot rejections daily/consecutive/lot: {risk.get('daily_loss_stop_rejections') if isinstance(risk, dict) else ''} / {risk.get('consecutive_loss_stop_rejections') if isinstance(risk, dict) else ''} / {risk.get('lot_limit_rejections') if isinstance(risk, dict) else ''}",
            f"- Session resets / open at end: {risk.get('session_resets') if isinstance(risk, dict) else ''} / {risk.get('open_positions_at_end') if isinstance(risk, dict) else ''}",
            "",
            "## Checks",
            "",
            "| check | ok | actual | required |",
            "|---|---:|---:|---:|",
        ]
    )
    for name, check in checks.items():
        required = check.get("required", check.get("required_max", ""))
        lines.append(f"| {name} | {check.get('ok')} | {check.get('actual')} | {required} |")
    lines.extend(["", "## Signal Diagnostics", ""])
    signal = summary.get("signal", {})
    reject = summary.get("reject", {})
    if isinstance(signal, dict):
        lines.extend(
            [
                f"- Rows: {signal.get('rows')}",
                f"- Tradable/Hold/Other: {signal.get('tradable')} / {signal.get('hold')} / {signal.get('other')}",
                f"- Avg BUY/SELL score: {signal.get('avg_buy_score')} / {signal.get('avg_sell_score')}",
                "- Top signal reasons:",
            ]
        )
        append_text_count_list(lines, signal.get("top_reasons"))
    if isinstance(reject, dict):
        lines.extend(
            [
                "- Top rejection messages:",
            ]
        )
        append_text_count_list(lines, reject.get("top_messages"))
        limits = reject.get("detected_consecutive_loss_limits")
        lines.append("- Detected consecutive loss limits:")
        if isinstance(limits, list) and limits:
            for item in limits:
                if isinstance(item, dict):
                    lines.append(f"  - {item.get('limit')}: {item.get('count')}")
        else:
            lines.append("  - _None._")
    lines.extend(["", "## By Action", ""])
    append_table(lines, summary["by_action"])
    lines.extend(["", "## By Exit Reason", ""])
    append_table(lines, summary["by_exit_reason"])
    lines.extend(["", "## By Risk Reward", ""])
    append_table(lines, summary["by_risk_reward"])
    lines.extend(["", "## By SL Points", ""])
    append_table(lines, summary.get("by_stop_points", []))
    lines.extend(["", "## By TP Points", ""])
    append_table(lines, summary.get("by_take_profit_points", []))
    lines.extend(["", "## By Risk Reward And SL Points", ""])
    append_table(lines, summary.get("by_risk_reward_stop_points", []))
    lines.extend(["", "## By Risk Reward And TP Points", ""])
    append_table(lines, summary.get("by_risk_reward_take_profit_points", []))
    lines.extend(["", "## By Server Hour", ""])
    append_table(lines, summary.get("by_server_hour", []))
    lines.extend(["", "## By Entry Server Hour", ""])
    append_table(lines, summary.get("by_entry_server_hour", []))
    lines.extend(["", "## By M30 Trend", ""])
    append_table(lines, summary.get("by_m30_trend", []))
    lines.extend(["", "## By M15 Trend", ""])
    append_table(lines, summary.get("by_m15_trend", []))
    lines.extend(["", "## By M5 Trend", ""])
    append_table(lines, summary.get("by_m5_trend", []))
    lines.extend(["", "## By M30 Slope", ""])
    append_table(lines, summary.get("by_m30_slope", []))
    lines.extend(["", "## By M15 Slope", ""])
    append_table(lines, summary.get("by_m15_slope", []))
    lines.extend(["", "## By M30/M15 Trend", ""])
    append_table(lines, summary.get("by_m30_m15_trend", []))
    lines.extend(["", "## By Trend Alignment", ""])
    append_table(lines, summary.get("by_trend_alignment", []))
    lines.extend(["", "## By Action And Trend Alignment", ""])
    append_table(lines, summary.get("by_action_trend_alignment", []))
    lines.extend(["", "## By Action And M30/M15 Trend", ""])
    append_table(lines, summary.get("by_action_m30_m15_trend", []))
    lines.extend(["", "## Weak SL/TP Segments", ""])
    append_weak_sl_tp_segments(lines, summary.get("weak_sl_tp_segments", []))
    lines.extend(["", "## Weak Time Segments", ""])
    append_weak_regime_segments(lines, summary.get("weak_time_segments", []))
    lines.extend(["", "## Weak Trend Segments", ""])
    append_weak_regime_segments(lines, summary.get("weak_trend_segments", []))
    lines.extend(["", "## By Score Band", ""])
    append_table(lines, summary["by_score_band"])
    lines.extend(["", "## Score Thresholds", ""])
    append_score_threshold_table(lines, summary.get("score_thresholds", []))
    lines.extend(["", "## Side Score Diagnostics", ""])
    append_side_score_diagnostics(lines, summary.get("side_score_diagnostics", []))
    return "\n".join(lines) + "\n"


def append_text_count_list(lines: list[str], rows: object) -> None:
    if not isinstance(rows, list) or not rows:
        lines.append("  - _None._")
        return
    for row in rows:
        if isinstance(row, dict):
            lines.append(f"  - {row.get('text')}: {row.get('count')}")


def append_table(lines: list[str], rows: list[dict[str, Any]]) -> None:
    if not rows:
        lines.append("_No closed rows._")
        return
    lines.append(
        "| group | closed | wins | losses | win_rate | net_profit | pf | avg_price_r | "
        "max_dd_r | expectancy_r | avg_hold_s | avg_slip_pt | avg_spread_pt | tp/sl/early | max_losing_streak |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        display = {
            "avg_hold_seconds": 0.0,
            "avg_slippage_points": 0.0,
            "avg_spread_points": 0.0,
            "tp_closes": 0,
            "sl_closes": 0,
            "early_or_manual_closes": 0,
            **row,
        }
        lines.append(
            "| {group} | {closed} | {wins} | {losses} | {win_rate} | {net_profit} | {pf} | "
            "{avg_price_r} | {max_drawdown_price_r} | {expectancy_price_r} | "
            "{avg_hold_seconds} | {avg_slippage_points} | {avg_spread_points} | "
            "{tp_closes}/{sl_closes}/{early_or_manual_closes} | {max_losing_streak} |".format(
                **display,
            )
        )


def append_score_threshold_table(lines: list[str], rows: object) -> None:
    if not isinstance(rows, list) or not rows:
        lines.append("_No threshold rows._")
        return
    lines.append(
        "| side | score >= | closed | win_rate | net_profit | pf | avg_price_r | "
        "max_dd_r | expectancy_r | max_losing_streak |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {side} | {threshold} | {closed} | {win_rate} | {net_profit} | {pf} | {avg_price_r} | "
            "{max_drawdown_price_r} | {expectancy_price_r} | {max_losing_streak} |".format(
                side=row.get("side"),
                threshold=row.get("threshold"),
                closed=row.get("closed"),
                win_rate=row.get("win_rate"),
                net_profit=row.get("net_profit"),
                pf=row.get("pf"),
                avg_price_r=row.get("avg_price_r"),
                max_drawdown_price_r=row.get("max_drawdown_price_r"),
                expectancy_price_r=row.get("expectancy_price_r"),
                max_losing_streak=row.get("max_losing_streak"),
            )
        )


def append_weak_sl_tp_segments(lines: list[str], rows: object) -> None:
    if not isinstance(rows, list) or not rows:
        lines.append("_No weak SL/TP segments._")
        return
    lines.append(
        "| dimension | group | closed | win_rate | net_profit | pf | avg_price_r | "
        "tp/sl/early_loss | tp_rate | diagnosis |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {dimension} | {group} | {closed} | {win_rate} | {net_profit} | {pf} | {avg_price_r} | "
            "{tp_closes}/{sl_closes}/{early_loss_closes} | {tp_rate} | {diagnosis} |".format(
                dimension=row.get("dimension"),
                group=row.get("group"),
                closed=row.get("closed"),
                win_rate=row.get("win_rate"),
                net_profit=row.get("net_profit"),
                pf=row.get("pf"),
                avg_price_r=row.get("avg_price_r"),
                tp_closes=row.get("tp_closes"),
                sl_closes=row.get("sl_closes"),
                early_loss_closes=row.get("early_loss_closes"),
                tp_rate=row.get("tp_rate"),
                diagnosis=row.get("diagnosis"),
            )
        )


def append_weak_regime_segments(lines: list[str], rows: object) -> None:
    if not isinstance(rows, list) or not rows:
        lines.append("_No weak regime segments._")
        return
    lines.append("| dimension | group | closed | win_rate | net_profit | pf | avg_price_r | max_losing_streak | diagnosis |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---|")
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {dimension} | {group} | {closed} | {win_rate} | {net_profit} | {pf} | {avg_price_r} | {max_losing_streak} | {diagnosis} |".format(
                dimension=row.get("dimension"),
                group=row.get("group"),
                closed=row.get("closed"),
                win_rate=row.get("win_rate"),
                net_profit=row.get("net_profit"),
                pf=row.get("pf"),
                avg_price_r=row.get("avg_price_r"),
                max_losing_streak=row.get("max_losing_streak"),
                diagnosis=row.get("diagnosis"),
            )
        )


def append_side_score_diagnostics(lines: list[str], rows: object) -> None:
    if not isinstance(rows, list) or not rows:
        lines.append("_No side score diagnostics._")
        return
    lines.append("| side | status | base PF | best score >= | best PF | high score >= | high PF | recommendation |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---|")
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {side} | {status} | {base_pf} | {best_pf_threshold} | {best_pf} | {high_threshold} | {high_pf} | {recommendation} |".format(
                side=row.get("side"),
                status=row.get("status"),
                base_pf=row.get("base_pf"),
                best_pf_threshold=row.get("best_pf_threshold"),
                best_pf=row.get("best_pf"),
                high_threshold=row.get("high_threshold"),
                high_pf=row.get("high_pf"),
                recommendation=row.get("recommendation"),
            )
        )


def write_markdown(path: str | Path, summary: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_markdown(summary), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize Swing_Evaluation_Trader MT5 forward-test CSV logs.")
    parser.add_argument("--input", default="runtime/mt5_forward/swing_evaluation_trades.csv")
    parser.add_argument("--output-json", default="runtime/latest_mt5_forward_report.json")
    parser.add_argument("--output-md", default="runtime/latest_mt5_forward_report.md")
    parser.add_argument("--print-full-summary", action="store_true", help="Print the full report summary to stdout.")
    parser.add_argument("--min-closed", type=int, default=30)
    parser.add_argument("--min-pf", type=float, default=1.2)
    parser.add_argument("--max-losing-streak", type=int, default=20)
    parser.add_argument("--max-single-volume", type=float, default=0.10)
    parser.add_argument("--max-total-volume", type=float, default=0.30)
    parser.add_argument("--max-positions", type=int, default=3)
    parser.add_argument("--daily-loss-limit", type=float, default=5000.0)
    return parser.parse_args(argv)


def cli_summary(
    summary: dict[str, Any],
    *,
    rows_count: int,
    output_json: str | Path,
    output_md: str | Path,
) -> dict[str, Any]:
    overall = summary.get("overall") if isinstance(summary.get("overall"), dict) else {}
    signal = summary.get("signal") if isinstance(summary.get("signal"), dict) else {}
    reject = summary.get("reject") if isinstance(summary.get("reject"), dict) else {}
    checks = summary.get("checks") if isinstance(summary.get("checks"), dict) else {}
    warnings = summary.get("diagnostic_warnings") if isinstance(summary.get("diagnostic_warnings"), list) else []
    failed_checks = [
        name
        for name, check in checks.items()
        if isinstance(check, dict) and not bool(check.get("ok"))
    ]
    return {
        "ok": True,
        "rows_count": rows_count,
        "output_json": str(output_json),
        "output_md": str(output_md),
        "closed": overall.get("closed", 0),
        "pf": overall.get("pf", 0.0),
        "avg_price_r": overall.get("avg_price_r", 0.0),
        "max_losing_streak": overall.get("max_losing_streak", 0),
        "signals": {
            "buy": signal.get("buy", 0),
            "sell": signal.get("sell", 0),
            "hold": signal.get("hold", 0),
            "tradable": signal.get("tradable", 0),
        },
        "rejections": reject.get("rows", 0),
        "ready_for_demo_review": bool(summary.get("ready_for_demo_review")),
        "warnings": len(warnings),
        "failed_checks": failed_checks,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = load_mt5_csv(args.input)
    summary = summarize_mt5_forward(
        rows,
        min_closed=args.min_closed,
        min_pf=args.min_pf,
        max_losing_streak_limit=args.max_losing_streak,
        max_single_volume=args.max_single_volume,
        max_total_volume=args.max_total_volume,
        max_positions=args.max_positions,
        daily_loss_limit=args.daily_loss_limit,
    )
    write_json(args.output_json, summary, rows)
    write_markdown(args.output_md, summary)
    if args.print_full_summary:
        payload = {"ok": True, "output_json": args.output_json, "output_md": args.output_md, "summary": summary}
    else:
        payload = cli_summary(summary, rows_count=len(rows), output_json=args.output_json, output_md=args.output_md)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
