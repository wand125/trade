#!/usr/bin/env python3
"""Prior-only selection diagnostics for short entry budget guard candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


OBJECTIVES = (
    "active_total",
    "short_total",
    "active_stability",
    "short_stability",
    "recent_active_stability",
    "defensive_score",
    "defensive_budget",
)
DEFAULT_CANDIDATE_COLUMNS = ("short_gap_threshold", "context_entry_budget")


def parse_csv_strings(value: str) -> list[str]:
    values = [part.strip() for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def local_json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def normalize_summary(
    frame: pd.DataFrame,
    candidate_columns: tuple[str, ...] = DEFAULT_CANDIDATE_COLUMNS,
) -> pd.DataFrame:
    required = {
        "month",
        "trade_count",
        "total_adjusted_pnl",
        "max_drawdown",
        "forced_exit_count",
        "short_adjusted_pnl",
        "long_adjusted_pnl",
        "active_trade_count",
        "active_trade_pnl",
        *candidate_columns,
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"summary missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["month"] = output["month"].astype(str)
    numeric_columns = [
        "trade_count",
        "total_adjusted_pnl",
        "max_drawdown",
        "forced_exit_count",
        "short_adjusted_pnl",
        "long_adjusted_pnl",
        "active_trade_count",
        "active_trade_pnl",
        *candidate_columns,
    ]
    if "inactive_trade_pnl" in output.columns:
        numeric_columns.append("inactive_trade_pnl")
    else:
        output["inactive_trade_pnl"] = np.nan
    for column in numeric_columns:
        output[column] = pd.to_numeric(output[column], errors="raise")
    return output.sort_values(["month", *candidate_columns]).reset_index(drop=True)


def aggregate_candidate(
    frame: pd.DataFrame,
    *,
    candidate_columns: tuple[str, ...],
    recent_months: list[str] | None = None,
) -> pd.DataFrame:
    grouped = (
        frame.groupby(list(candidate_columns), dropna=False)
        .agg(
            validation_months=("month", "nunique"),
            validation_trades=("trade_count", "sum"),
            validation_total_pnl=("total_adjusted_pnl", "sum"),
            validation_worst_month_pnl=("total_adjusted_pnl", "min"),
            validation_max_monthly_drawdown=("max_drawdown", "max"),
            validation_forced_exits=("forced_exit_count", "sum"),
            validation_short_pnl=("short_adjusted_pnl", "sum"),
            validation_short_worst_month=("short_adjusted_pnl", "min"),
            validation_short_losing_months=(
                "short_adjusted_pnl",
                lambda values: int((pd.Series(values) < 0).sum()),
            ),
            validation_long_pnl=("long_adjusted_pnl", "sum"),
            validation_active_pnl=("active_trade_pnl", "sum"),
            validation_active_worst_month=("active_trade_pnl", "min"),
            validation_active_losing_months=(
                "active_trade_pnl",
                lambda values: int((pd.Series(values) < 0).sum()),
            ),
            validation_active_trade_count=("active_trade_count", "sum"),
        )
        .reset_index()
    )
    if recent_months:
        recent = frame[frame["month"].isin(recent_months)]
        if recent.empty:
            grouped["recent_months"] = 0
            grouped["recent_active_pnl"] = np.nan
            grouped["recent_active_worst_month"] = np.nan
            grouped["recent_active_losing_months"] = np.nan
            grouped["recent_short_pnl"] = np.nan
            grouped["recent_short_losing_months"] = np.nan
        else:
            recent_grouped = (
                recent.groupby(list(candidate_columns), dropna=False)
                .agg(
                    recent_months=("month", "nunique"),
                    recent_active_pnl=("active_trade_pnl", "sum"),
                    recent_active_worst_month=("active_trade_pnl", "min"),
                    recent_active_losing_months=(
                        "active_trade_pnl",
                        lambda values: int((pd.Series(values) < 0).sum()),
                    ),
                    recent_short_pnl=("short_adjusted_pnl", "sum"),
                    recent_short_losing_months=(
                        "short_adjusted_pnl",
                        lambda values: int((pd.Series(values) < 0).sum()),
                    ),
                )
                .reset_index()
            )
            grouped = grouped.merge(recent_grouped, on=list(candidate_columns), how="left")
    else:
        grouped["recent_months"] = 0
        grouped["recent_active_pnl"] = np.nan
        grouped["recent_active_worst_month"] = np.nan
        grouped["recent_active_losing_months"] = np.nan
        grouped["recent_short_pnl"] = np.nan
        grouped["recent_short_losing_months"] = np.nan
    return grouped


def candidate_match(
    frame: pd.DataFrame,
    selected: pd.Series,
    candidate_columns: tuple[str, ...],
) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for column in candidate_columns:
        mask &= frame[column] == selected[column]
    return mask


def format_float_label(value: float) -> str:
    if value == float("inf"):
        return "inf"
    if value == -float("inf"):
        return "ninf"
    return ("%g" % value).replace("-", "m").replace(".", "p")


def format_candidate(row: pd.Series, candidate_columns: tuple[str, ...]) -> str:
    return "|".join(
        f"{column}={format_float_label(float(row[column]))}"
        for column in candidate_columns
    )


def format_string_set(values: pd.Series) -> str:
    return ";".join(sorted({str(value) for value in values}))


def select_candidate(
    prior: pd.DataFrame,
    *,
    objective: str,
    candidate_columns: tuple[str, ...],
    recent_month_count: int,
    active_loss_count_weight: float,
    short_loss_count_weight: float,
    worst_weight: float,
    drawdown_weight: float,
) -> pd.Series:
    if objective not in OBJECTIVES:
        raise ValueError(f"unknown objective: {objective}")
    months = sorted(prior["month"].unique())
    recent_months = months[-recent_month_count:] if recent_month_count > 0 else []
    candidates = aggregate_candidate(
        prior,
        candidate_columns=candidate_columns,
        recent_months=recent_months,
    )
    if candidates.empty:
        raise ValueError("cannot select candidate from empty prior frame")
    ranking = candidates.copy()
    if objective == "active_total":
        ranking = ranking.sort_values(
            ["validation_active_pnl", "validation_short_pnl", "validation_total_pnl"],
            ascending=[False, False, False],
        )
    elif objective == "short_total":
        ranking = ranking.sort_values(
            ["validation_short_pnl", "validation_active_pnl", "validation_total_pnl"],
            ascending=[False, False, False],
        )
    elif objective == "active_stability":
        ranking = ranking.sort_values(
            [
                "validation_active_losing_months",
                "validation_active_worst_month",
                "validation_active_pnl",
                "validation_total_pnl",
            ],
            ascending=[True, False, False, False],
        )
    elif objective == "short_stability":
        ranking = ranking.sort_values(
            [
                "validation_short_losing_months",
                "validation_short_worst_month",
                "validation_short_pnl",
                "validation_total_pnl",
            ],
            ascending=[True, False, False, False],
        )
    elif objective == "recent_active_stability":
        ranking = ranking.sort_values(
            [
                "recent_active_losing_months",
                "recent_active_worst_month",
                "recent_active_pnl",
                "validation_active_losing_months",
                "validation_active_pnl",
            ],
            ascending=[True, False, False, True, False],
        )
    elif objective == "defensive_budget":
        if "context_entry_budget" not in ranking.columns:
            raise ValueError("defensive_budget objective requires context_entry_budget")
        ranking = ranking.sort_values(
            [
                "context_entry_budget",
                "validation_worst_month_pnl",
                "validation_total_pnl",
                "validation_short_worst_month",
            ],
            ascending=[True, False, False, False],
        )
    else:
        ranking["selection_score"] = (
            ranking["validation_total_pnl"]
            + ranking["validation_short_pnl"]
            + ranking["validation_active_pnl"]
            + worst_weight * ranking["validation_worst_month_pnl"]
            - drawdown_weight * ranking["validation_max_monthly_drawdown"]
            - active_loss_count_weight * ranking["validation_active_losing_months"]
            - short_loss_count_weight * ranking["validation_short_losing_months"]
        )
        ranking = ranking.sort_values(
            ["selection_score", "validation_worst_month_pnl", "validation_total_pnl"],
            ascending=[False, False, False],
        )
    return ranking.iloc[0]


def walkforward_selection(
    frame: pd.DataFrame,
    *,
    objectives: list[str],
    min_train_months: int,
    train_window_months: int,
    candidate_columns: tuple[str, ...],
    recent_month_count: int,
    active_loss_count_weight: float,
    short_loss_count_weight: float,
    worst_weight: float,
    drawdown_weight: float,
) -> pd.DataFrame:
    if min_train_months <= 0:
        raise ValueError("min_train_months must be positive")
    if train_window_months < 0:
        raise ValueError("train_window_months must be non-negative")
    data = normalize_summary(frame, candidate_columns)
    months = sorted(data["month"].unique())
    rows: list[dict[str, Any]] = []
    for month_index, target_month in enumerate(months):
        prior_months = months[:month_index]
        if train_window_months:
            prior_months = prior_months[-train_window_months:]
        if len(prior_months) < min_train_months:
            continue
        prior = data[data["month"].isin(prior_months)]
        target_rows = data[data["month"] == target_month].copy()
        for objective in objectives:
            selected = select_candidate(
                prior,
                objective=objective,
                candidate_columns=candidate_columns,
                recent_month_count=recent_month_count,
                active_loss_count_weight=active_loss_count_weight,
                short_loss_count_weight=short_loss_count_weight,
                worst_weight=worst_weight,
                drawdown_weight=drawdown_weight,
            )
            target = target_rows[candidate_match(target_rows, selected, candidate_columns)]
            if target.empty:
                continue
            target_row = target.iloc[0]
            selected_candidate_values = {
                f"selected_{column}": selected[column]
                for column in candidate_columns
            }
            rows.append(
                {
                    "selection_name": objective,
                    "objective": objective,
                    "target_month": target_month,
                    "prior_months": len(prior_months),
                    "prior_start_month": prior_months[0],
                    "prior_end_month": prior_months[-1],
                    "selected_candidate": format_candidate(selected, candidate_columns),
                    **selected_candidate_values,
                    "validation_total_pnl": selected["validation_total_pnl"],
                    "validation_worst_month_pnl": selected["validation_worst_month_pnl"],
                    "validation_max_monthly_drawdown": selected[
                        "validation_max_monthly_drawdown"
                    ],
                    "validation_short_pnl": selected["validation_short_pnl"],
                    "validation_short_worst_month": selected[
                        "validation_short_worst_month"
                    ],
                    "validation_short_losing_months": selected[
                        "validation_short_losing_months"
                    ],
                    "validation_active_pnl": selected["validation_active_pnl"],
                    "validation_active_worst_month": selected[
                        "validation_active_worst_month"
                    ],
                    "validation_active_losing_months": selected[
                        "validation_active_losing_months"
                    ],
                    "recent_active_pnl": selected["recent_active_pnl"],
                    "recent_active_losing_months": selected[
                        "recent_active_losing_months"
                    ],
                    "target_trade_count": target_row["trade_count"],
                    "target_total_pnl": target_row["total_adjusted_pnl"],
                    "target_max_drawdown": target_row["max_drawdown"],
                    "target_forced_exit_count": target_row["forced_exit_count"],
                    "target_short_pnl": target_row["short_adjusted_pnl"],
                    "target_long_pnl": target_row["long_adjusted_pnl"],
                    "target_active_trade_count": target_row["active_trade_count"],
                    "target_active_pnl": target_row["active_trade_pnl"],
                }
            )
    return pd.DataFrame(rows)


def summarize_walkforward(selection: pd.DataFrame) -> pd.DataFrame:
    if selection.empty:
        return pd.DataFrame()
    return (
        selection.groupby("selection_name", dropna=False)
        .agg(
            objective=("objective", "first"),
            target_months=("target_month", "nunique"),
            trades=("target_trade_count", "sum"),
            total_pnl=("target_total_pnl", "sum"),
            worst_month_pnl=("target_total_pnl", "min"),
            max_monthly_drawdown=("target_max_drawdown", "max"),
            forced_exits=("target_forced_exit_count", "sum"),
            short_pnl=("target_short_pnl", "sum"),
            long_pnl=("target_long_pnl", "sum"),
            active_trade_count=("target_active_trade_count", "sum"),
            active_pnl=("target_active_pnl", "sum"),
            selected_candidates=("selected_candidate", format_string_set),
        )
        .reset_index()
        .sort_values(["total_pnl", "worst_month_pnl"], ascending=[False, False])
    )


def run_selection(args: argparse.Namespace) -> Path:
    candidate_columns = tuple(parse_csv_strings(args.candidate_columns))
    source = normalize_summary(pd.read_csv(args.summary_by_run), candidate_columns)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = output_dir / args.label
    suffix = 0
    while run_dir.exists():
        suffix += 1
        run_dir = output_dir / f"{args.label}_{suffix}"
    run_dir.mkdir(parents=True)
    objectives = parse_csv_strings(args.objectives)
    selection = walkforward_selection(
        source,
        objectives=objectives,
        min_train_months=args.min_train_months,
        train_window_months=args.train_window_months,
        candidate_columns=candidate_columns,
        recent_month_count=args.recent_month_count,
        active_loss_count_weight=args.active_loss_count_weight,
        short_loss_count_weight=args.short_loss_count_weight,
        worst_weight=args.worst_weight,
        drawdown_weight=args.drawdown_weight,
    )
    summary = summarize_walkforward(selection)
    selection.to_csv(run_dir / "walkforward_selection.csv", index=False)
    summary.to_csv(run_dir / "walkforward_summary.csv", index=False)
    source.to_csv(run_dir / "input_summary_by_run.csv", index=False)
    metadata = {
        "summary_by_run": str(args.summary_by_run),
        "candidate_columns": candidate_columns,
        "objectives": objectives,
        "min_train_months": args.min_train_months,
        "train_window_months": args.train_window_months,
        "recent_month_count": args.recent_month_count,
        "active_loss_count_weight": args.active_loss_count_weight,
        "short_loss_count_weight": args.short_loss_count_weight,
        "worst_weight": args.worst_weight,
        "drawdown_weight": args.drawdown_weight,
    }
    (run_dir / "config.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    if summary.empty:
        print("no walk-forward selection rows")
    else:
        print(summary.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-by-run", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="short_budget_guard_selection")
    parser.add_argument("--candidate-columns", default="short_gap_threshold,context_entry_budget")
    parser.add_argument(
        "--objectives",
        default=(
            "active_total,short_total,active_stability,short_stability,"
            "recent_active_stability,defensive_score,defensive_budget"
        ),
    )
    parser.add_argument("--min-train-months", type=int, default=4)
    parser.add_argument("--train-window-months", type=int, default=0)
    parser.add_argument("--recent-month-count", type=int, default=3)
    parser.add_argument("--active-loss-count-weight", type=float, default=25.0)
    parser.add_argument("--short-loss-count-weight", type=float, default=10.0)
    parser.add_argument("--worst-weight", type=float, default=1.0)
    parser.add_argument("--drawdown-weight", type=float, default=0.25)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_selection(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
