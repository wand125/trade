from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from trade_data.backtest import read_ohlcv
from trade_data.next_bar_overlay import read_prediction_sets


@dataclass(frozen=True)
class EntryDelayConfig:
    timestamp_column: str = "entry_timestamp"
    exit_timestamp_column: str = "exit_timestamp"
    side_column: str = "direction"
    entry_price_column: str = "candidate_entry_price"
    exit_price_column: str = "candidate_exit_price"
    raw_pnl_column: str = "candidate_raw_pnl"
    adjusted_pnl_column: str = "candidate_adjusted_pnl"
    present_column: str | None = "candidate_present"
    group_column: str | None = "candidate_run_dir"
    confidence_threshold: float = 0.53
    max_delay_minutes: int = 15
    additional_costs: tuple[float, ...] = (0.0, 0.05, 0.10)
    confirmation_start: str = "2025-03-01"
    min_delayed_rows: int = 30


def _normalize_side(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.lower()
        .replace({"long": "up", "short": "down", "buy": "up", "sell": "down"})
    )


def _prepare_inputs(
    trades: pd.DataFrame,
    predictions: pd.DataFrame,
    m1: pd.DataFrame,
    config: EntryDelayConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    required = {
        config.timestamp_column,
        config.exit_timestamp_column,
        config.side_column,
        config.entry_price_column,
        config.exit_price_column,
        config.raw_pnl_column,
        config.adjusted_pnl_column,
    }
    if config.present_column:
        required.add(config.present_column)
    if config.group_column:
        required.add(config.group_column)
    missing = sorted(required - set(trades.columns))
    if missing:
        raise ValueError(f"trade rows are missing: {', '.join(missing)}")
    frame = trades.copy()
    if config.present_column:
        frame = frame.loc[frame[config.present_column].astype(bool)].copy()
    for column in (config.timestamp_column, config.exit_timestamp_column):
        frame[column] = pd.to_datetime(frame[column], utc=True).astype(
            "datetime64[ns, UTC]"
        )
    frame = frame.sort_values(config.timestamp_column).reset_index(drop=True)
    frame["normalized_side"] = _normalize_side(frame[config.side_column])
    if not frame["normalized_side"].isin(["up", "down"]).all():
        raise ValueError("side values must be up/down, long/short, or buy/sell")

    prediction_frame = predictions.copy()
    for column in ("decision_timestamp", "target_timestamp"):
        prediction_frame[column] = pd.to_datetime(
            prediction_frame[column], utc=True
        ).astype("datetime64[ns, UTC]")
    prediction_frame = prediction_frame.sort_values("decision_timestamp").reset_index(
        drop=True
    )

    price_frame = m1[["timestamp", "open"]].copy()
    price_frame["timestamp"] = pd.to_datetime(
        price_frame["timestamp"], utc=True
    ).astype("datetime64[ns, UTC]")
    price_frame = price_frame.drop_duplicates("timestamp").set_index("timestamp").sort_index()
    return frame, prediction_frame, price_frame["open"].astype("float64")


def _active_prediction(
    predictions: pd.DataFrame, timestamp: pd.Timestamp
) -> pd.Series | None:
    positions = predictions["decision_timestamp"].searchsorted(timestamp, side="right")
    if positions == 0:
        return None
    row = predictions.iloc[positions - 1]
    if timestamp >= row["target_timestamp"]:
        return None
    return row


def _first_release_time(
    predictions: pd.DataFrame,
    start: pd.Timestamp,
    deadline: pd.Timestamp,
    side: str,
    confidence_threshold: float,
    high_confidence_only: bool,
) -> pd.Timestamp | None:
    initial = _active_prediction(predictions, start)
    if initial is None:
        return start
    aligned = str(initial["predicted_direction"]).lower() == side
    high = float(initial["confidence"]) >= confidence_threshold
    should_wait = (not aligned) and (high or not high_confidence_only)
    if not should_wait:
        return start

    future = predictions.loc[
        predictions["decision_timestamp"].gt(start)
        & predictions["decision_timestamp"].le(deadline)
    ]
    for _, row in future.iterrows():
        candidate_time = row["decision_timestamp"]
        candidate_aligned = str(row["predicted_direction"]).lower() == side
        candidate_high = float(row["confidence"]) >= confidence_threshold
        still_blocked = (not candidate_aligned) and (
            candidate_high or not high_confidence_only
        )
        if not still_blocked:
            return candidate_time
    return None


def replay_entry_delay(
    trades: pd.DataFrame,
    predictions: pd.DataFrame,
    m1: pd.DataFrame,
    config: EntryDelayConfig,
    *,
    high_confidence_only: bool,
    timeout_action: str,
) -> pd.DataFrame:
    if timeout_action not in {"skip", "enter"}:
        raise ValueError("timeout_action must be skip or enter")
    frame, prediction_frame, opens = _prepare_inputs(
        trades, predictions, m1, config
    )
    rows: list[dict[str, object]] = []
    for index, trade in frame.iterrows():
        start = trade[config.timestamp_column]
        exit_timestamp = trade[config.exit_timestamp_column]
        deadline = min(
            start + pd.Timedelta(minutes=config.max_delay_minutes),
            exit_timestamp,
        )
        release = _first_release_time(
            prediction_frame,
            start,
            deadline,
            str(trade["normalized_side"]),
            config.confidence_threshold,
            high_confidence_only,
        )
        timed_out = release is None
        if timed_out and timeout_action == "enter":
            release = deadline
        selected = release is not None and release < exit_timestamp
        reason = "unchanged"
        if timed_out and timeout_action == "skip":
            reason = "timeout_skip"
        elif release is not None and release > start:
            reason = "timeout_enter" if timed_out else "delayed_release"
        if selected and release not in opens.index:
            position = opens.index.searchsorted(release, side="left")
            if position >= len(opens.index) or opens.index[position] >= exit_timestamp:
                selected = False
                reason = "missing_delayed_price"
            else:
                release = opens.index[position]

        output = trade.to_dict()
        output["source_row"] = int(index)
        output["delay_selected"] = bool(selected)
        output["delay_reason"] = reason
        output["delayed_entry_timestamp"] = release if selected else pd.NaT
        output["delay_minutes"] = (
            float((release - start).total_seconds() / 60) if selected else np.nan
        )
        if not selected:
            output["delayed_entry_price"] = np.nan
            output["delayed_raw_pnl"] = 0.0
            output["delayed_adjusted_pnl"] = 0.0
            output["entry_price_improvement"] = np.nan
            rows.append(output)
            continue

        original_open_position = opens.index.searchsorted(start, side="left")
        if original_open_position >= len(opens.index):
            raise ValueError(f"no M1 price at or after {start}")
        original_market_open = float(opens.iloc[original_open_position])
        delayed_market_open = float(opens.loc[release])
        execution_offset = float(trade[config.entry_price_column]) - original_market_open
        delayed_entry_price = delayed_market_open + execution_offset
        sign = 1.0 if trade["normalized_side"] == "up" else -1.0
        delayed_raw = sign * (
            float(trade[config.exit_price_column]) - delayed_entry_price
        )
        original_adjustment = float(trade[config.adjusted_pnl_column]) - float(
            trade[config.raw_pnl_column]
        )
        delayed_adjusted = delayed_raw + original_adjustment
        output["delayed_entry_price"] = delayed_entry_price
        output["delayed_raw_pnl"] = delayed_raw
        output["delayed_adjusted_pnl"] = delayed_adjusted
        output["entry_price_improvement"] = sign * (
            float(trade[config.entry_price_column]) - delayed_entry_price
        )
        rows.append(output)
    replayed = pd.DataFrame(rows)
    return _apply_one_position(replayed, config)


def _apply_one_position(
    frame: pd.DataFrame, config: EntryDelayConfig
) -> pd.DataFrame:
    output = frame.copy()
    output["stateful_selected"] = output["delay_selected"].astype(bool)
    output["stateful_conflict"] = False
    if config.group_column:
        groups = output.groupby(config.group_column, sort=False, dropna=False)
    else:
        groups = [("all", output)]
    for _, group in groups:
        last_exit: pd.Timestamp | None = None
        for index in group.sort_values("delayed_entry_timestamp", na_position="last").index:
            if not bool(output.at[index, "delay_selected"]):
                continue
            entry = output.at[index, "delayed_entry_timestamp"]
            if last_exit is not None and entry < last_exit:
                output.at[index, "stateful_selected"] = False
                output.at[index, "stateful_conflict"] = True
                output.at[index, "delayed_adjusted_pnl"] = 0.0
                output.at[index, "delayed_raw_pnl"] = 0.0
                continue
            last_exit = output.at[index, config.exit_timestamp_column]
    return output.sort_values(config.timestamp_column).reset_index(drop=True)


def _max_drawdown(pnl: pd.Series) -> float:
    if pnl.empty:
        return 0.0
    equity = pnl.cumsum()
    return float((equity.cummax() - equity).max())


def summarize_replay(frame: pd.DataFrame, config: EntryDelayConfig) -> dict[str, object]:
    selected = frame["stateful_selected"].astype(bool)
    pnl = frame["delayed_adjusted_pnl"].astype("float64")
    baseline = frame[config.adjusted_pnl_column].astype("float64")
    month = (
        frame["month"].astype(str)
        if "month" in frame.columns
        else frame[config.timestamp_column].dt.strftime("%Y-%m")
    )
    monthly = pd.DataFrame({"month": month, "pnl": pnl}).groupby("month")["pnl"].sum()
    baseline_monthly = pd.DataFrame(
        {"month": month, "pnl": baseline}
    ).groupby("month")["pnl"].sum()
    delayed = selected & frame["delay_minutes"].gt(0)
    result = {
        "input_rows": len(frame),
        "selected_rows": int(selected.sum()),
        "coverage": float(selected.mean()) if len(frame) else 0.0,
        "delayed_rows": int(delayed.sum()),
        "timeout_skips": int(frame["delay_reason"].eq("timeout_skip").sum()),
        "stateful_conflicts": int(frame["stateful_conflict"].sum()),
        "mean_delay_minutes": float(frame.loc[delayed, "delay_minutes"].mean())
        if delayed.any()
        else 0.0,
        "mean_entry_price_improvement": float(
            frame.loc[delayed, "entry_price_improvement"].mean()
        )
        if delayed.any()
        else 0.0,
        "baseline_total_pnl": float(baseline.sum()),
        "total_pnl": float(pnl.sum()),
        "pnl_delta": float(pnl.sum() - baseline.sum()),
        "mean_pnl": float(pnl.loc[selected].mean()) if selected.any() else None,
        "win_rate": float((pnl.loc[selected] > 0).mean()) if selected.any() else None,
        "positive_months": int((monthly > 0).sum()),
        "months": len(monthly),
        "worst_month_pnl": float(monthly.min()),
        "baseline_worst_month_pnl": float(baseline_monthly.min()),
        "max_drawdown": _max_drawdown(pnl),
        "additional_cost_sensitivity": [],
        "monthly_pnl": {str(key): float(value) for key, value in monthly.items()},
    }
    confirmation_start = pd.Timestamp(config.confirmation_start, tz="UTC")
    period_masks = {
        "development": frame[config.timestamp_column] < confirmation_start,
        "confirmation": frame[config.timestamp_column] >= confirmation_start,
    }
    period_summaries = {}
    for name, mask in period_masks.items():
        period_pnl = pnl.loc[mask]
        period_baseline = baseline.loc[mask]
        period_selected = selected.loc[mask]
        period_month = month.loc[mask]
        period_monthly = pd.DataFrame(
            {"month": period_month, "pnl": period_pnl}
        ).groupby("month")["pnl"].sum()
        period_summaries[name] = {
            "input_rows": int(mask.sum()),
            "selected_rows": int(period_selected.sum()),
            "delayed_rows": int((delayed & mask).sum()),
            "baseline_total_pnl": float(period_baseline.sum()),
            "total_pnl": float(period_pnl.sum()),
            "pnl_delta": float(period_pnl.sum() - period_baseline.sum()),
            "positive_months": int((period_monthly > 0).sum()),
            "months": int(len(period_monthly)),
            "worst_month_pnl": float(period_monthly.min())
            if len(period_monthly)
            else None,
        }
    result["period_summaries"] = period_summaries
    for cost in config.additional_costs:
        net = pnl - delayed.astype(float) * cost
        result["additional_cost_sensitivity"].append(
            {
                "additional_delayed_entry_cost": float(cost),
                "total_pnl": float(net.sum()),
                "pnl_delta": float(net.sum() - baseline.sum()),
                "mean_selected_pnl": float(net.loc[selected].mean())
                if selected.any()
                else None,
            }
        )
    admission_checks = {
        "minimum_delayed_support": int(delayed.sum()) >= config.min_delayed_rows,
        "positive_development_delta": period_summaries["development"]["pnl_delta"]
        > 1e-9,
        "positive_confirmation_delta": period_summaries["confirmation"]["pnl_delta"]
        > 1e-9,
        "worst_month_not_degraded": float(monthly.min())
        >= float(baseline_monthly.min()) - 1e-9,
    }
    result["admission"] = {
        **admission_checks,
        "accepted": all(admission_checks.values()),
    }
    return result


def evaluate_entry_delay_policies(
    trades: pd.DataFrame,
    predictions: pd.DataFrame,
    m1: pd.DataFrame,
    config: EntryDelayConfig,
) -> tuple[dict[str, object], pd.DataFrame]:
    policy_specs = {
        "wait_any_opposed_skip": (False, "skip"),
        "wait_any_opposed_timeout": (False, "enter"),
        "wait_high_conf_opposed_skip": (True, "skip"),
        "wait_high_conf_opposed_timeout": (True, "enter"),
    }
    reports = {}
    rows = []
    for name, (high_only, timeout_action) in policy_specs.items():
        replayed = replay_entry_delay(
            trades,
            predictions,
            m1,
            config,
            high_confidence_only=high_only,
            timeout_action=timeout_action,
        )
        replayed["delay_policy"] = name
        rows.append(replayed)
        reports[name] = summarize_replay(replayed, config)
    return reports, pd.concat(rows, ignore_index=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay M1/M5 next-bar predictions as a short entry-delay overlay."
    )
    parser.add_argument("--input", type=Path, required=True, help="UTC M1 OHLC parquet")
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--predictions-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeframe", type=int, choices=(1, 5), required=True)
    parser.add_argument("--confidence-threshold", type=float, required=True)
    parser.add_argument("--max-delay-minutes", type=int, default=15)
    parser.add_argument("--additional-costs", default="0,0.05,0.10")
    parser.add_argument("--confirmation-start", default="2025-03-01")
    parser.add_argument("--min-delayed-rows", type=int, default=30)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    additional_costs = tuple(float(value) for value in args.additional_costs.split(","))
    config = EntryDelayConfig(
        confidence_threshold=args.confidence_threshold,
        max_delay_minutes=args.max_delay_minutes,
        additional_costs=additional_costs,
        confirmation_start=args.confirmation_start,
        min_delayed_rows=args.min_delayed_rows,
    )
    trades = pd.read_csv(args.trades)
    predictions = read_prediction_sets(args.predictions_dir, args.timeframe)
    m1 = read_ohlcv(args.input)
    policies, rows = evaluate_entry_delay_policies(trades, predictions, m1, config)
    output = {
        "created_at": datetime.now(UTC).isoformat(),
        "config": asdict(config),
        "timeframe": f"M{args.timeframe}",
        "source_trades": str(args.trades),
        "source_predictions": [str(path) for path in args.predictions_dir],
        "execution_assumption": (
            "preserve original entry-vs-M1-open offset and original exit; "
            "no replacement candidates"
        ),
        "policies": policies,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows.to_parquet(args.output_dir / "entry_delay_rows.parquet", index=False)
    (args.output_dir / "metrics.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
