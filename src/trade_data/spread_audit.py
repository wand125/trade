from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


def _timestamp(value: object) -> pd.Timestamp | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and np.isfinite(value):
        unit = "ms" if abs(float(value)) >= 1e11 else "s"
        parsed = pd.to_datetime(value, unit=unit, utc=True, errors="coerce")
    else:
        parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed)


def read_event_jsonl(path: Path) -> tuple[list[dict[str, object]], int]:
    rows: list[dict[str, object]] = []
    malformed = 0
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(value, dict):
                malformed += 1
                continue
            rows.append(value)
    return rows, malformed


def normalize_spread_events(
    events: Iterable[Mapping[str, object]],
) -> tuple[pd.DataFrame, dict[str, int]]:
    normalized: list[dict[str, object]] = []
    counts = {"input_rows": 0, "invalid_rows": 0}
    for event in events:
        counts["input_rows"] += 1
        timestamp = None
        for key in ("received_at", "server_time", "timestamp"):
            timestamp = _timestamp(event.get(key))
            if timestamp is not None:
                break
        symbol = str(event.get("symbol") or "").strip()
        try:
            bid = float(event.get("bid"))
            ask = float(event.get("ask"))
        except (TypeError, ValueError):
            counts["invalid_rows"] += 1
            continue
        if (
            timestamp is None
            or not symbol
            or not np.isfinite(bid)
            or not np.isfinite(ask)
            or bid <= 0
            or ask < bid
        ):
            counts["invalid_rows"] += 1
            continue
        normalized.append(
            {
                "timestamp": timestamp,
                "symbol": symbol,
                "bid": bid,
                "ask": ask,
                "spread_price": ask - bid,
            }
        )
    frame = pd.DataFrame(
        normalized,
        columns=["timestamp", "symbol", "bid", "ask", "spread_price"],
    )
    if len(frame):
        frame = frame.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
    counts["valid_rows"] = int(len(frame))
    return frame, counts


def summarize_spreads(
    frame: pd.DataFrame,
    *,
    cost_ceilings: Mapping[str, float] | None = None,
    min_observations: int = 5_000,
    min_unique_days: int = 5,
) -> list[dict[str, object]]:
    if min_observations <= 0 or min_unique_days <= 0:
        raise ValueError("sufficiency thresholds must be positive")
    ceilings = dict(cost_ceilings or {})
    output: list[dict[str, object]] = []
    for symbol, group in frame.groupby("symbol", sort=True):
        spread = group["spread_price"].astype("float64")
        unique_days = int(group["timestamp"].dt.floor("D").nunique())
        unique_hours = int(group["timestamp"].dt.floor("h").nunique())
        sufficient = len(group) >= min_observations and unique_days >= min_unique_days
        minimum = float(spread.min())
        median = float(spread.median())
        p90 = float(spread.quantile(0.90))
        ceiling = ceilings.get(str(symbol))
        if ceiling is not None:
            ceiling = float(ceiling)
            if not np.isfinite(ceiling) or ceiling <= 0:
                raise ValueError(f"cost ceiling for {symbol} must be positive")
        spread_only_pass = bool(sufficient and ceiling is not None and p90 <= ceiling)
        output.append(
            {
                "symbol": str(symbol),
                "observations": int(len(group)),
                "start_timestamp": group["timestamp"].min().isoformat(),
                "end_timestamp": group["timestamp"].max().isoformat(),
                "unique_days": unique_days,
                "unique_hours": unique_hours,
                "minimum_spread_price": minimum,
                "median_spread_price": median,
                "p90_spread_price": p90,
                "maximum_spread_price": float(spread.max()),
                "cost_ceiling_price": ceiling,
                "median_to_ceiling_ratio": median / ceiling if ceiling else None,
                "p90_to_ceiling_ratio": p90 / ceiling if ceiling else None,
                "data_sufficient": bool(sufficient),
                "spread_only_p90_gate_passed": spread_only_pass,
                "all_in_cost_authorized": False,
                "authorization_blockers": [
                    value
                    for value, blocked in (
                        ("insufficient_observations_or_days", not sufficient),
                        ("cost_ceiling_unavailable", ceiling is None),
                        ("p90_spread_above_cost_ceiling", ceiling is not None and p90 > ceiling),
                        ("commission_not_included", True),
                        ("slippage_not_included", True),
                        ("fresh_prediction_edge_not_verified", True),
                    )
                    if blocked
                ],
            }
        )
    return output


def build_report(
    events: Iterable[Mapping[str, object]],
    *,
    malformed_json_rows: int = 0,
    cost_ceilings: Mapping[str, float] | None = None,
    min_observations: int = 5_000,
    min_unique_days: int = 5,
) -> dict[str, object]:
    frame, counts = normalize_spread_events(events)
    counts["malformed_json_rows"] = int(malformed_json_rows)
    return {
        "format_version": 1,
        "spread_definition": "ask - bid in symbol price units",
        "sufficiency": {
            "minimum_observations": int(min_observations),
            "minimum_unique_utc_days": int(min_unique_days),
        },
        "input_quality": counts,
        "symbols": summarize_spreads(
            frame,
            cost_ceilings=cost_ceilings,
            min_observations=min_observations,
            min_unique_days=min_unique_days,
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize observed bid/ask spreads by symbol")
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cost-ceilings", type=Path)
    parser.add_argument("--min-observations", type=int, default=5_000)
    parser.add_argument("--min-unique-days", type=int, default=5)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    events, malformed = read_event_jsonl(args.events)
    ceilings: dict[str, float] = {}
    if args.cost_ceilings:
        loaded = json.loads(args.cost_ceilings.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("cost ceilings must be a JSON object keyed by symbol")
        ceilings = {str(key): float(value) for key, value in loaded.items()}
    report = build_report(
        events,
        malformed_json_rows=malformed,
        cost_ceilings=ceilings,
        min_observations=args.min_observations,
        min_unique_days=args.min_unique_days,
    )
    report["input"] = str(args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
