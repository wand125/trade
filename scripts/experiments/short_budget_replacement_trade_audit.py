#!/usr/bin/env python3
"""Audit candidate-only replacement trades from model-trade-delta output."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_WINDOWS = ("late_2025_08_12:2025-08:2025-12", "late_2025_09_12:2025-09:2025-12")
TOP_LOSS_COLUMNS = [
    "candidate",
    "window",
    "month",
    "entry_decision_timestamp",
    "candidate_entry_timestamp",
    "candidate_exit_timestamp",
    "direction",
    "delta_status",
    "candidate_adjusted_pnl",
    "candidate_holding_minutes",
    "candidate_exit_reason",
    "combined_regime",
    "session_regime",
    "predicted_best_side",
    "actual_best_side",
    "actual_taken_best_adjusted_pnl",
    "pred_taken_ev",
    "pred_best_ev",
    "pred_taken_profit_barrier_hit",
    "pred_taken_side_confidence",
    "pred_side_confidence_gap",
    "direction_error",
    "actual_side_matches_trade",
    "exit_regret",
    "best_side_regret",
    "ev_overestimate_vs_realized",
    "candidate_blocked_base_count",
    "candidate_blocked_base_adjusted_pnl",
    "candidate_stateful_net_adjusted_pnl",
]


@dataclass(frozen=True)
class NamedPath:
    name: str
    path: Path


@dataclass(frozen=True)
class MonthWindow:
    name: str
    start_month: str
    end_month: str


def parse_named_path(value: str) -> NamedPath:
    if "=" not in value:
        raise argparse.ArgumentTypeError("delta run must be formatted as name=path")
    name, path_text = value.split("=", 1)
    name = name.strip()
    path_text = path_text.strip()
    if not name:
        raise argparse.ArgumentTypeError("delta run name is empty")
    if not path_text:
        raise argparse.ArgumentTypeError("delta run path is empty")
    return NamedPath(name=name, path=Path(path_text))


def parse_window(value: str) -> MonthWindow:
    parts = [part.strip() for part in value.split(":")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("window must be formatted as name:start_month:end_month")
    if not all(parts):
        raise argparse.ArgumentTypeError("window parts must be non-empty")
    return MonthWindow(name=parts[0], start_month=parts[1], end_month=parts[2])


def local_json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, NamedPath):
        return {"name": value.name, "path": value.path}
    if isinstance(value, MonthWindow):
        return {
            "name": value.name,
            "start_month": value.start_month,
            "end_month": value.end_month,
        }
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def delta_csv_path(path: Path) -> Path:
    if path.is_dir():
        return path / "trade_delta_rows.csv"
    return path


def load_delta(named_path: NamedPath) -> pd.DataFrame:
    source = delta_csv_path(named_path.path)
    if not source.exists():
        raise FileNotFoundError(f"trade delta csv not found: {source}")
    frame = pd.read_csv(source)
    required = {"month", "direction", "delta_status", "candidate_adjusted_pnl"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{source} missing columns: {', '.join(missing)}")
    frame = frame.copy()
    frame["candidate"] = named_path.name
    frame["source_path"] = str(source)
    frame["month"] = frame["month"].astype(str)
    frame["direction"] = frame["direction"].astype(str)
    frame["delta_status"] = frame["delta_status"].astype(str)
    frame["candidate_adjusted_pnl"] = pd.to_numeric(
        frame["candidate_adjusted_pnl"],
        errors="coerce",
    )
    return frame


def normalize_for_summary(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    for column in [
        "candidate_holding_minutes",
        "actual_taken_best_adjusted_pnl",
        "pred_taken_ev",
        "pred_best_ev",
        "pred_taken_side_confidence",
        "pred_side_confidence_gap",
        "exit_regret",
        "best_side_regret",
        "ev_overestimate_vs_realized",
        "candidate_blocked_base_count",
        "candidate_blocked_base_adjusted_pnl",
        "candidate_stateful_net_adjusted_pnl",
    ]:
        if column in output.columns:
            output[column] = pd.to_numeric(output[column], errors="coerce")
    for column in ["is_loss", "is_win", "is_forced_exit", "direction_error", "actual_side_matches_trade"]:
        if column in output.columns:
            output[column] = to_bool_series(output[column])
    for column in ["combined_regime", "session_regime", "candidate_exit_reason"]:
        if column in output.columns:
            output[column] = output[column].fillna("unknown").astype(str)
    return output


def to_bool_series(series: pd.Series) -> pd.Series:
    def convert(value: Any) -> bool:
        if pd.isna(value):
            return False
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "t", "yes", "y"}
        return bool(value)

    return series.map(convert).astype(bool)


def replacement_rows(
    frame: pd.DataFrame,
    *,
    window: MonthWindow,
    direction: str,
    delta_status: str,
) -> pd.DataFrame:
    data = normalize_for_summary(frame)
    mask = (
        data["month"].ge(window.start_month)
        & data["month"].le(window.end_month)
        & data["direction"].eq(direction)
        & data["delta_status"].eq(delta_status)
    )
    rows = data.loc[mask].copy()
    rows["window"] = window.name
    rows["window_start_month"] = window.start_month
    rows["window_end_month"] = window.end_month
    return rows


def bool_sum(series: pd.Series) -> int:
    return int(to_bool_series(series).sum())


def numeric_sum(series: pd.Series) -> float:
    return float(pd.to_numeric(series, errors="coerce").sum())


def numeric_mean(series: pd.Series) -> float:
    return float(pd.to_numeric(series, errors="coerce").mean())


def win_rate(series: pd.Series) -> float:
    total = len(series)
    if total == 0:
        return float("nan")
    return bool_sum(series) / total


def summarize_rows(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    data = rows.copy()
    for column in ["is_win", "is_loss", "is_forced_exit"]:
        if column not in data.columns:
            data[column] = False
    for column in [
        "candidate_holding_minutes",
        "pred_taken_ev",
        "actual_taken_best_adjusted_pnl",
        "pred_side_confidence_gap",
        "ev_overestimate_vs_realized",
        "candidate_blocked_base_count",
        "candidate_blocked_base_adjusted_pnl",
        "candidate_stateful_net_adjusted_pnl",
    ]:
        if column not in data.columns:
            data[column] = np.nan
    return (
        data.groupby(["candidate", "window"], dropna=False)
        .agg(
            rows=("candidate_adjusted_pnl", "size"),
            total_pnl=("candidate_adjusted_pnl", "sum"),
            loss_count=("is_loss", bool_sum),
            win_count=("is_win", bool_sum),
            win_rate=("is_win", win_rate),
            forced_exit_count=("is_forced_exit", bool_sum),
            mean_pnl=("candidate_adjusted_pnl", "mean"),
            median_pnl=("candidate_adjusted_pnl", "median"),
            worst_trade_pnl=("candidate_adjusted_pnl", "min"),
            best_trade_pnl=("candidate_adjusted_pnl", "max"),
            mean_holding_minutes=("candidate_holding_minutes", "mean"),
            mean_pred_taken_ev=("pred_taken_ev", "mean"),
            mean_actual_taken_best_pnl=("actual_taken_best_adjusted_pnl", "mean"),
            mean_side_confidence_gap=("pred_side_confidence_gap", "mean"),
            mean_ev_overestimate_vs_realized=("ev_overestimate_vs_realized", "mean"),
            mean_blocked_base_count=("candidate_blocked_base_count", "mean"),
            blocked_base_pnl=("candidate_blocked_base_adjusted_pnl", "sum"),
            stateful_net_pnl=("candidate_stateful_net_adjusted_pnl", "sum"),
        )
        .reset_index()
        .sort_values(["candidate", "window"])
    )


def grouped_summary(rows: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    data = rows.copy()
    for column in group_columns:
        if column not in data.columns:
            data[column] = "unknown"
        data[column] = data[column].fillna("unknown").astype(str)
    for column in ["is_loss", "is_win", "is_forced_exit", "ev_overestimate_vs_realized", "pred_taken_ev"]:
        if column not in data.columns:
            data[column] = np.nan if column not in {"is_loss", "is_win", "is_forced_exit"} else False
    summary = (
        data.groupby(["candidate", "window", *group_columns], dropna=False)
        .agg(
            rows=("candidate_adjusted_pnl", "size"),
            total_pnl=("candidate_adjusted_pnl", "sum"),
            loss_count=("is_loss", bool_sum),
            win_count=("is_win", bool_sum),
            forced_exit_count=("is_forced_exit", bool_sum),
            mean_pnl=("candidate_adjusted_pnl", "mean"),
            worst_trade_pnl=("candidate_adjusted_pnl", "min"),
            mean_pred_taken_ev=("pred_taken_ev", numeric_mean),
            mean_ev_overestimate_vs_realized=("ev_overestimate_vs_realized", numeric_mean),
        )
        .reset_index()
    )
    return summary.sort_values(["candidate", "window", "total_pnl", "rows"])


def top_losses(rows: pd.DataFrame, top_n: int) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    columns = [column for column in TOP_LOSS_COLUMNS if column in rows.columns]
    return rows.sort_values("candidate_adjusted_pnl", ascending=True)[columns].head(top_n)


def run_audit(args: argparse.Namespace) -> Path:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = args.output_dir / args.label
    suffix = 0
    while run_dir.exists():
        suffix += 1
        run_dir = args.output_dir / f"{args.label}_{suffix}"
    run_dir.mkdir(parents=True)

    windows = args.windows
    loaded = [load_delta(delta_run) for delta_run in args.delta_runs]
    all_rows = []
    for frame in loaded:
        for window in windows:
            all_rows.append(
                replacement_rows(
                    frame,
                    window=window,
                    direction=args.direction,
                    delta_status=args.delta_status,
                )
            )
    rows = pd.concat(all_rows, ignore_index=True, sort=False) if all_rows else pd.DataFrame()

    overview = summarize_rows(rows)
    by_month = grouped_summary(rows, ["month"])
    by_regime_session = grouped_summary(rows, ["combined_regime", "session_regime"])
    by_exit_reason = grouped_summary(rows, ["candidate_exit_reason"])
    losses = top_losses(rows, args.top_n)

    rows.to_csv(run_dir / "replacement_rows.csv", index=False)
    overview.to_csv(run_dir / "replacement_summary.csv", index=False)
    by_month.to_csv(run_dir / "replacement_by_month.csv", index=False)
    by_regime_session.to_csv(run_dir / "replacement_by_regime_session.csv", index=False)
    by_exit_reason.to_csv(run_dir / "replacement_by_exit_reason.csv", index=False)
    losses.to_csv(run_dir / "replacement_top_losses.csv", index=False)
    metadata = {
        "delta_runs": args.delta_runs,
        "windows": windows,
        "direction": args.direction,
        "delta_status": args.delta_status,
        "top_n": args.top_n,
    }
    (run_dir / "config.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    if overview.empty:
        print("no replacement rows")
    else:
        print(overview.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delta-run", dest="delta_runs", action="append", type=parse_named_path, required=True)
    parser.add_argument("--window", dest="windows", action="append", type=parse_window)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="short_budget_replacement_trade_audit")
    parser.add_argument("--direction", default="short")
    parser.add_argument("--delta-status", default="only_candidate")
    parser.add_argument("--top-n", type=int, default=30)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.windows is None:
        args.windows = [parse_window(value) for value in DEFAULT_WINDOWS]
    run_audit(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
