#!/usr/bin/env python3
"""Evaluate rolling threshold selection for context drawdown guard results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SELECTION_OBJECTIVES = ("total", "worst", "risk_adjusted", "risk_budget")
DEFAULT_CANDIDATE_COLUMNS = ("context_drawdown_guard_loss_threshold",)


def parse_csv_floats(value: str) -> list[float]:
    values = [float(part.strip()) for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one numeric value is required")
    return values


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
        *candidate_columns,
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"summary missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["month"] = output["month"].astype(str)
    for column in [
        "trade_count",
        "total_adjusted_pnl",
        "max_drawdown",
        "forced_exit_count",
        *candidate_columns,
    ]:
        output[column] = pd.to_numeric(output[column], errors="raise")
    if "short_adjusted_pnl" not in output.columns:
        output["short_adjusted_pnl"] = np.nan
    if "long_adjusted_pnl" not in output.columns:
        output["long_adjusted_pnl"] = np.nan
    output["short_adjusted_pnl"] = pd.to_numeric(output["short_adjusted_pnl"], errors="coerce")
    output["long_adjusted_pnl"] = pd.to_numeric(output["long_adjusted_pnl"], errors="coerce")
    return output.sort_values(["month", *candidate_columns]).reset_index(drop=True)


def aggregate_by_candidate(
    frame: pd.DataFrame,
    candidate_columns: tuple[str, ...] = DEFAULT_CANDIDATE_COLUMNS,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    return (
        frame.groupby(list(candidate_columns), dropna=False)
        .agg(
            validation_months=("month", "nunique"),
            validation_trades=("trade_count", "sum"),
            validation_total_pnl=("total_adjusted_pnl", "sum"),
            validation_worst_month_pnl=("total_adjusted_pnl", "min"),
            validation_max_monthly_drawdown=("max_drawdown", "max"),
            validation_forced_exits=("forced_exit_count", "sum"),
            validation_short_pnl=("short_adjusted_pnl", "sum"),
            validation_long_pnl=("long_adjusted_pnl", "sum"),
        )
        .reset_index()
    )


def aggregate_by_threshold(frame: pd.DataFrame) -> pd.DataFrame:
    return aggregate_by_candidate(frame, DEFAULT_CANDIDATE_COLUMNS)


def candidate_match(frame: pd.DataFrame, selected: pd.Series, candidate_columns: tuple[str, ...]) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for column in candidate_columns:
        mask &= frame[column] == selected[column]
    return mask


def format_candidate(selected: pd.Series, candidate_columns: tuple[str, ...]) -> str:
    parts = []
    for column in candidate_columns:
        parts.append(f"{column}={format_float_label(float(selected[column]))}")
    return "|".join(parts)


def select_threshold(
    prior: pd.DataFrame,
    *,
    objective: str,
    worst_weight: float = 1.0,
    drawdown_weight: float = 0.0,
    min_validation_worst_month_pnl: float = -float("inf"),
    max_validation_drawdown: float = float("inf"),
    candidate_columns: tuple[str, ...] = DEFAULT_CANDIDATE_COLUMNS,
) -> pd.Series:
    if objective not in SELECTION_OBJECTIVES:
        raise ValueError(f"unknown objective: {objective}")
    candidates = aggregate_by_candidate(prior, candidate_columns)
    if candidates.empty:
        raise ValueError("cannot select candidate from empty prior frame")

    candidates["eligible"] = (
        (candidates["validation_worst_month_pnl"] >= min_validation_worst_month_pnl)
        & (candidates["validation_max_monthly_drawdown"] <= max_validation_drawdown)
    )
    ranking = candidates[candidates["eligible"]].copy()
    if ranking.empty:
        ranking = candidates.copy()
        ranking["eligible"] = False

    if objective == "total":
        ranking = ranking.sort_values(
            ["validation_total_pnl", "validation_worst_month_pnl"],
            ascending=[False, False],
        )
    elif objective == "worst":
        ranking = ranking.sort_values(
            ["validation_worst_month_pnl", "validation_total_pnl"],
            ascending=[False, False],
        )
    else:
        ranking["selection_score"] = (
            ranking["validation_total_pnl"]
            + worst_weight * ranking["validation_worst_month_pnl"]
            - drawdown_weight * ranking["validation_max_monthly_drawdown"]
        )
        if objective == "risk_budget":
            ranking = ranking.sort_values(
                ["selection_score", "validation_total_pnl", "validation_worst_month_pnl"],
                ascending=[False, False, False],
            )
        else:
            ranking = ranking.sort_values(
                ["selection_score", "validation_total_pnl"],
                ascending=[False, False],
            )
    return ranking.iloc[0]


def walkforward_selection(
    frame: pd.DataFrame,
    *,
    objectives: list[str],
    min_train_months: int,
    train_window_months: int = 0,
    candidate_columns: tuple[str, ...] = DEFAULT_CANDIDATE_COLUMNS,
    worst_weights: list[float] | None = None,
    drawdown_weights: list[float] | None = None,
    min_validation_worst_month_pnls: list[float] | None = None,
    max_validation_drawdowns: list[float] | None = None,
) -> pd.DataFrame:
    if min_train_months <= 0:
        raise ValueError("min_train_months must be positive")
    if train_window_months < 0:
        raise ValueError("train_window_months must be non-negative")

    data = normalize_summary(frame, candidate_columns)
    months = sorted(data["month"].unique())
    worst_weights = worst_weights or [1.0]
    drawdown_weights = drawdown_weights or [0.0]
    min_validation_worst_month_pnls = min_validation_worst_month_pnls or [-float("inf")]
    max_validation_drawdowns = max_validation_drawdowns or [float("inf")]
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
            if objective in {"total", "worst"}:
                parameter_grid = [(1.0, 0.0, -float("inf"), float("inf"))]
            elif objective == "risk_adjusted":
                parameter_grid = [
                    (worst_weight, drawdown_weight, -float("inf"), float("inf"))
                    for worst_weight in worst_weights
                    for drawdown_weight in drawdown_weights
                ]
            else:
                parameter_grid = [
                    (
                        worst_weight,
                        drawdown_weight,
                        min_worst,
                        max_drawdown,
                    )
                    for worst_weight in worst_weights
                    for drawdown_weight in drawdown_weights
                    for min_worst in min_validation_worst_month_pnls
                    for max_drawdown in max_validation_drawdowns
                ]
            for worst_weight, drawdown_weight, min_worst, max_drawdown in parameter_grid:
                selected = select_threshold(
                    prior,
                    objective=objective,
                    worst_weight=worst_weight,
                    drawdown_weight=drawdown_weight,
                    min_validation_worst_month_pnl=min_worst,
                    max_validation_drawdown=max_drawdown,
                    candidate_columns=candidate_columns,
                )
                target = target_rows[candidate_match(target_rows, selected, candidate_columns)]
                if target.empty:
                    continue
                target_row = target.iloc[0]
                selected_candidate_values = {
                    f"selected_{column}": selected[column]
                    for column in candidate_columns
                }
                if "context_drawdown_guard_loss_threshold" in candidate_columns:
                    selected_threshold = selected[
                        "context_drawdown_guard_loss_threshold"
                    ]
                else:
                    selected_threshold = np.nan
                rows.append(
                    {
                        "selection_name": selection_name(
                            objective,
                            worst_weight,
                            drawdown_weight,
                            min_worst,
                            max_drawdown,
                        ),
                        "objective": objective,
                        "target_month": target_month,
                        "prior_months": len(prior_months),
                        "prior_start_month": prior_months[0],
                        "prior_end_month": prior_months[-1],
                        "selected_candidate": format_candidate(selected, candidate_columns),
                        "selected_threshold": selected_threshold,
                        **selected_candidate_values,
                        "selected_eligible": bool(selected.get("eligible", True)),
                        "validation_total_pnl": selected["validation_total_pnl"],
                        "validation_worst_month_pnl": selected[
                            "validation_worst_month_pnl"
                        ],
                        "validation_max_monthly_drawdown": selected[
                            "validation_max_monthly_drawdown"
                        ],
                        "target_trade_count": target_row["trade_count"],
                        "target_total_pnl": target_row["total_adjusted_pnl"],
                        "target_max_drawdown": target_row["max_drawdown"],
                        "target_forced_exit_count": target_row["forced_exit_count"],
                        "target_short_pnl": target_row["short_adjusted_pnl"],
                        "target_long_pnl": target_row["long_adjusted_pnl"],
                    }
                )
    return pd.DataFrame(rows)


def selection_name(
    objective: str,
    worst_weight: float,
    drawdown_weight: float,
    min_worst: float,
    max_drawdown: float,
) -> str:
    if objective in {"total", "worst"}:
        return objective
    parts = [objective, f"ww{format_float_label(worst_weight)}"]
    if drawdown_weight:
        parts.append(f"dw{format_float_label(drawdown_weight)}")
    if np.isfinite(min_worst):
        parts.append(f"minw{format_float_label(min_worst)}")
    if np.isfinite(max_drawdown):
        parts.append(f"maxdd{format_float_label(max_drawdown)}")
    return "_".join(parts)


def format_float_label(value: float) -> str:
    if value == float("inf"):
        return "inf"
    if value == -float("inf"):
        return "ninf"
    return ("%g" % value).replace("-", "m").replace(".", "p")


def threshold_sort_key(value: float) -> tuple[int, float]:
    if value == -float("inf"):
        return (0, 0.0)
    if value == float("inf"):
        return (2, 0.0)
    return (1, value)


def format_threshold_set(values: pd.Series) -> str:
    thresholds = sorted({float(value) for value in values}, key=threshold_sort_key)
    return ",".join(format_float_label(value) for value in thresholds)


def format_string_set(values: pd.Series) -> str:
    return ";".join(sorted({str(value) for value in values}))


def summarize_walkforward(selection: pd.DataFrame) -> pd.DataFrame:
    if selection.empty:
        return pd.DataFrame()
    selection = selection.copy()
    if "selected_candidate" not in selection.columns:
        selection["selected_candidate"] = selection["selected_threshold"].map(
            lambda value: (
                "context_drawdown_guard_loss_threshold="
                + format_float_label(float(value))
            )
        )
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
            selected_thresholds=(
                "selected_threshold",
                format_threshold_set,
            ),
            selected_candidates=(
                "selected_candidate",
                format_string_set,
            ),
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

    selection = walkforward_selection(
        source,
        objectives=parse_csv_strings(args.objectives),
        min_train_months=args.min_train_months,
        train_window_months=args.train_window_months,
        candidate_columns=candidate_columns,
        worst_weights=parse_csv_floats(args.worst_weights),
        drawdown_weights=parse_csv_floats(args.drawdown_weights),
        min_validation_worst_month_pnls=parse_csv_floats(args.min_validation_worst_month_pnls),
        max_validation_drawdowns=parse_csv_floats(args.max_validation_drawdowns),
    )
    summary = summarize_walkforward(selection)
    selection.to_csv(run_dir / "walkforward_selection.csv", index=False)
    summary.to_csv(run_dir / "walkforward_summary.csv", index=False)
    source.to_csv(run_dir / "input_summary_by_run.csv", index=False)
    metadata = {
        "summary_by_run": args.summary_by_run,
        "objectives": parse_csv_strings(args.objectives),
        "candidate_columns": candidate_columns,
        "min_train_months": args.min_train_months,
        "train_window_months": args.train_window_months,
        "worst_weights": parse_csv_floats(args.worst_weights),
        "drawdown_weights": parse_csv_floats(args.drawdown_weights),
        "min_validation_worst_month_pnls": parse_csv_floats(
            args.min_validation_worst_month_pnls
        ),
        "max_validation_drawdowns": parse_csv_floats(args.max_validation_drawdowns),
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
    parser = argparse.ArgumentParser(
        description="Run prior-only threshold selection diagnostics for drawdown guard outputs.",
    )
    parser.add_argument("--summary-by-run", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="context_drawdown_guard_selection")
    parser.add_argument(
        "--candidate-columns",
        default="context_drawdown_guard_loss_threshold",
        help="comma-separated numeric columns that define a selectable candidate",
    )
    parser.add_argument("--objectives", default="total,worst,risk_adjusted,risk_budget")
    parser.add_argument("--min-train-months", type=int, default=8)
    parser.add_argument(
        "--train-window-months",
        type=int,
        default=0,
        help="0 uses all prior months; otherwise use a trailing window",
    )
    parser.add_argument("--worst-weights", default="1,2,4")
    parser.add_argument("--drawdown-weights", default="0")
    parser.add_argument("--min-validation-worst-month-pnls", default="-inf,-150,-120")
    parser.add_argument("--max-validation-drawdowns", default="inf")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_selection(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
