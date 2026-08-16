from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


def read_deal_history(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("deals", [])
    if not isinstance(payload, list):
        raise ValueError("deal history must be a JSON list or an object containing a deals list")
    return [row for row in payload if isinstance(row, dict)]


def read_csv(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return [dict(row) for row in csv.DictReader(source)]


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def _timestamp(value: object) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    return None if pd.isna(parsed) else pd.Timestamp(parsed)


def _summary(values: Sequence[float]) -> dict[str, float | int | None]:
    if not values:
        return {"observations": 0, "mean": None, "median": None, "p90": None, "maximum": None}
    array = np.asarray(values, dtype="float64")
    return {
        "observations": int(len(array)),
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "p90": float(np.quantile(array, 0.90)),
        "maximum": float(array.max()),
    }


def _symbol_config(config: Mapping[str, object], symbol: str) -> Mapping[str, object]:
    symbols = config.get("symbols", config)
    if not isinstance(symbols, Mapping):
        return {}
    value = symbols.get(symbol, {})
    return value if isinstance(value, Mapping) else {}


def summarize_commission(
    deals: Iterable[Mapping[str, object]],
    *,
    config: Mapping[str, object],
) -> tuple[list[dict[str, object]], dict[str, int]]:
    buckets: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    timestamps: dict[str, list[pd.Timestamp]] = defaultdict(list)
    effective_conversions: dict[str, list[float]] = defaultdict(list)
    counts = {"input_rows": 0, "valid_rows": 0, "invalid_rows": 0, "unconfigured_rows": 0}
    for row in deals:
        counts["input_rows"] += 1
        symbol = str(row.get("symbol") or "").strip()
        volume = _number(row.get("volume"))
        commission = _number(row.get("commission"))
        entry = str(row.get("entry") or "").strip().lower()
        symbol_config = _symbol_config(config, symbol)
        contract_size = _number(symbol_config.get("contract_size_per_lot"))
        conversion = _number(row.get("account_currency_to_quote_rate"))
        if conversion is None:
            conversion = _number(symbol_config.get("account_currency_to_quote_rate"))
        if not symbol or volume is None or volume <= 0 or commission is None or entry not in {"in", "out"}:
            counts["invalid_rows"] += 1
            continue
        if contract_size is None or contract_size <= 0 or conversion is None or conversion <= 0:
            counts["unconfigured_rows"] += 1
            continue
        price_cost = abs(commission) * conversion / (volume * contract_size)
        buckets[symbol][entry].append(price_cost)
        effective_conversions[symbol].append(conversion)
        timestamp = _timestamp(row.get("time"))
        if timestamp is not None:
            timestamps[symbol].append(timestamp)
        counts["valid_rows"] += 1

    output: list[dict[str, object]] = []
    for symbol in sorted(buckets):
        incoming = buckets[symbol]["in"]
        outgoing = buckets[symbol]["out"]
        round_trip = None
        if incoming and outgoing:
            round_trip = float(np.mean(incoming) + np.mean(outgoing))
        times = timestamps[symbol]
        symbol_config = _symbol_config(config, symbol)
        configured_conversion = _number(symbol_config.get("account_currency_to_quote_rate"))
        output.append(
            {
                "symbol": symbol,
                "contract_size_per_lot": float(symbol_config["contract_size_per_lot"]),
                "configured_account_currency_to_quote_rate": configured_conversion,
                "row_level_conversion_rate_used": configured_conversion is None,
                "effective_conversion_rate_range": {
                    "minimum": min(effective_conversions[symbol]),
                    "maximum": max(effective_conversions[symbol]),
                },
                "start_timestamp": min(times).isoformat() if times else None,
                "end_timestamp": max(times).isoformat() if times else None,
                "entry_leg_commission_price": _summary(incoming),
                "exit_leg_commission_price": _summary(outgoing),
                "round_trip_commission_price_mean": round_trip,
                "round_trip_observed_both_legs": round_trip is not None,
            }
        )
    return output, counts


def summarize_slippage(rows: Iterable[Mapping[str, object]]) -> tuple[list[dict[str, object]], dict[str, int]]:
    buckets: dict[str, list[float]] = defaultdict(list)
    timestamps: dict[str, list[pd.Timestamp]] = defaultdict(list)
    counts = {"input_rows": 0, "valid_rows": 0, "invalid_rows": 0}
    for row in rows:
        counts["input_rows"] += 1
        if str(row.get("event") or "").strip().lower() != "open":
            continue
        symbol = str(row.get("symbol") or "").strip()
        action = str(row.get("action") or "").strip().lower()
        requested = _number(row.get("entry"))
        executed = _number(row.get("deal_price"))
        if not symbol or action not in {"buy", "sell"} or requested is None or executed is None:
            counts["invalid_rows"] += 1
            continue
        adverse = executed - requested if action == "buy" else requested - executed
        buckets[symbol].append(adverse)
        timestamp = _timestamp(row.get("server_time"))
        if timestamp is not None:
            timestamps[symbol].append(timestamp)
        counts["valid_rows"] += 1

    output: list[dict[str, object]] = []
    for symbol in sorted(buckets):
        times = timestamps[symbol]
        values = buckets[symbol]
        output.append(
            {
                "symbol": symbol,
                "start_timestamp": min(times).isoformat() if times else None,
                "end_timestamp": max(times).isoformat() if times else None,
                "entry_leg_adverse_slippage_price": _summary(values),
                "favorable_observations": sum(value < 0 for value in values),
                "adverse_observations": sum(value > 0 for value in values),
                "exit_leg_available": False,
            }
        )
    return output, counts


def build_report(
    *,
    deals: Iterable[Mapping[str, object]] = (),
    forward_rows: Iterable[Mapping[str, object]] = (),
    config: Mapping[str, object],
) -> dict[str, object]:
    commission, commission_quality = summarize_commission(deals, config=config)
    slippage, slippage_quality = summarize_slippage(forward_rows)
    commission_symbols = {str(row["symbol"]) for row in commission if row["round_trip_observed_both_legs"]}
    slippage_symbols = {str(row["symbol"]) for row in slippage}
    symbols = sorted(commission_symbols | slippage_symbols)
    return {
        "format_version": 1,
        "definitions": {
            "commission_price": "abs(commission in account currency) * account-to-quote rate / (lots * contract size)",
            "adverse_slippage_price": "buy: deal_price - requested entry; sell: requested entry - deal_price",
        },
        "input_quality": {"commission": commission_quality, "slippage": slippage_quality},
        "commission": commission,
        "slippage": slippage,
        "all_in_cost_authorized": False,
        "authorization_blockers": [
            value
            for value, blocked in (
                ("no_symbol_with_observed_round_trip_commission", not commission_symbols),
                ("no_symbol_with_entry_slippage", not slippage_symbols),
                ("exit_slippage_not_observed", True),
                ("spread_must_be_joined_from_independent_audit", True),
                ("fresh_prediction_edge_not_verified", True),
            )
            if blocked
        ],
        "symbols_with_partial_cost_evidence": symbols,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit MT5 commission and slippage without placing trades")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--deal-history", type=Path)
    parser.add_argument("--forward-csv", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.deal_history is None and args.forward_csv is None:
        raise ValueError("at least one of --deal-history or --forward-csv is required")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("config must be a JSON object")
    report = build_report(
        deals=read_deal_history(args.deal_history) if args.deal_history else (),
        forward_rows=read_csv(args.forward_csv) if args.forward_csv else (),
        config=config,
    )
    report["inputs"] = {
        "deal_history": str(args.deal_history) if args.deal_history else None,
        "forward_csv": str(args.forward_csv) if args.forward_csv else None,
        "config": str(args.config),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
