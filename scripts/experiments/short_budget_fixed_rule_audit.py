#!/usr/bin/env python3
"""Audit a pre-registered short budget trigger across train-window choices."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_CANDIDATE_COLUMNS = ("short_gap_threshold", "context_entry_budget")
METRIC_DIRECTIONS = {
    "recent_short_pnl": "lt",
    "recent_total_pnl": "lt",
    "recent_worst_month_pnl": "lt",
    "recent_short_worst_month_pnl": "lt",
    "recent_short_losing_months": "ge",
    "recent_total_losing_months": "ge",
}


@dataclass(frozen=True)
class Candidate:
    short_gap_threshold: float
    context_entry_budget: float


@dataclass(frozen=True)
class Rule:
    primary: Candidate
    defensive: Candidate
    trigger_metric: str
    operator: str
    threshold: float


def parse_csv_ints(value: str) -> list[int]:
    values = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one integer is required")
    return values


def parse_candidate(value: str) -> Candidate:
    parts = [part.strip() for part in value.split(":")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("candidate must be formatted as short_gap:budget")
    try:
        return Candidate(float(parts[0]), float(parts[1]))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("candidate values must be numeric") from exc


def local_json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Candidate):
        return {
            "short_gap_threshold": value.short_gap_threshold,
            "context_entry_budget": value.context_entry_budget,
        }
    if isinstance(value, Rule):
        return {
            "primary": value.primary,
            "defensive": value.defensive,
            "trigger_metric": value.trigger_metric,
            "operator": value.operator,
            "threshold": value.threshold,
        }
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def normalize_summary(frame: pd.DataFrame) -> pd.DataFrame:
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
        *DEFAULT_CANDIDATE_COLUMNS,
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
        "short_adjusted_pnl",
        "long_adjusted_pnl",
        "active_trade_count",
        "active_trade_pnl",
        *DEFAULT_CANDIDATE_COLUMNS,
    ]:
        output[column] = pd.to_numeric(output[column], errors="raise")
    return output.sort_values(["month", *DEFAULT_CANDIDATE_COLUMNS]).reset_index(drop=True)


def candidate_mask(frame: pd.DataFrame, candidate: Candidate) -> pd.Series:
    return (
        frame["short_gap_threshold"].eq(candidate.short_gap_threshold)
        & frame["context_entry_budget"].eq(candidate.context_entry_budget)
    )


def candidate_label(candidate: Candidate) -> str:
    return (
        f"short_gap_threshold={candidate.short_gap_threshold:g}|"
        f"context_entry_budget={candidate.context_entry_budget:g}"
    )


def should_trigger(value: float, operator: str, threshold: float) -> bool:
    if operator == "lt":
        return value < threshold
    if operator == "le":
        return value <= threshold
    if operator == "gt":
        return value > threshold
    if operator == "ge":
        return value >= threshold
    raise ValueError(f"unknown operator: {operator}")


def metric_bundle(
    prior: pd.DataFrame,
    candidate: Candidate,
    recent_month_count: int,
) -> dict[str, float]:
    months = sorted(prior["month"].unique())
    recent_months = months[-recent_month_count:] if recent_month_count > 0 else months
    recent = prior[prior["month"].isin(recent_months) & candidate_mask(prior, candidate)]
    if recent.empty:
        raise ValueError(f"candidate not found in prior frame: {candidate_label(candidate)}")
    return {
        "recent_months": float(len(recent_months)),
        "recent_total_pnl": float(recent["total_adjusted_pnl"].sum()),
        "recent_short_pnl": float(recent["short_adjusted_pnl"].sum()),
        "recent_worst_month_pnl": float(recent["total_adjusted_pnl"].min()),
        "recent_short_worst_month_pnl": float(recent["short_adjusted_pnl"].min()),
        "recent_short_losing_months": float((recent["short_adjusted_pnl"] < 0).sum()),
        "recent_total_losing_months": float((recent["total_adjusted_pnl"] < 0).sum()),
    }


def target_row(frame: pd.DataFrame, month: str, candidate: Candidate) -> pd.Series:
    rows = frame[frame["month"].eq(month) & candidate_mask(frame, candidate)]
    if rows.empty:
        raise ValueError(f"candidate not found for target {month}: {candidate_label(candidate)}")
    return rows.iloc[0]


def fixed_rule_rows(
    frame: pd.DataFrame,
    *,
    rule: Rule,
    min_train_months: int,
    train_window_months: int,
    recent_month_count: int,
) -> pd.DataFrame:
    if min_train_months <= 0:
        raise ValueError("min_train_months must be positive")
    if train_window_months < 0:
        raise ValueError("train_window_months must be non-negative")
    data = normalize_summary(frame)
    months = sorted(data["month"].unique())
    rows: list[dict[str, Any]] = []
    for month_index, target_month in enumerate(months):
        prior_months = months[:month_index]
        if train_window_months:
            prior_months = prior_months[-train_window_months:]
        if len(prior_months) < min_train_months:
            continue
        prior = data[data["month"].isin(prior_months)]
        metrics = metric_bundle(prior, rule.primary, recent_month_count)
        trigger_value = metrics[rule.trigger_metric]
        triggered = should_trigger(trigger_value, rule.operator, rule.threshold)
        selected = rule.defensive if triggered else rule.primary

        candidate_rows = {
            "primary": target_row(data, target_month, rule.primary),
            "defensive": target_row(data, target_month, rule.defensive),
            "trigger": target_row(data, target_month, selected),
        }
        for policy_name, row in candidate_rows.items():
            rows.append(
                {
                    "policy_name": policy_name,
                    "target_month": target_month,
                    "prior_months": len(prior_months),
                    "prior_start_month": prior_months[0],
                    "prior_end_month": prior_months[-1],
                    "min_train_months": min_train_months,
                    "train_window_months": train_window_months,
                    "recent_month_count": recent_month_count,
                    "primary_candidate": candidate_label(rule.primary),
                    "defensive_candidate": candidate_label(rule.defensive),
                    "selected_candidate": (
                        candidate_label(selected)
                        if policy_name == "trigger"
                        else candidate_label(rule.primary if policy_name == "primary" else rule.defensive)
                    ),
                    "trigger_metric": rule.trigger_metric,
                    "trigger_operator": rule.operator,
                    "trigger_threshold": rule.threshold,
                    "trigger_value": trigger_value,
                    "triggered": triggered if policy_name == "trigger" else policy_name == "defensive",
                    **metrics,
                    "target_trade_count": row["trade_count"],
                    "target_total_pnl": row["total_adjusted_pnl"],
                    "target_max_drawdown": row["max_drawdown"],
                    "target_forced_exit_count": row["forced_exit_count"],
                    "target_short_pnl": row["short_adjusted_pnl"],
                    "target_long_pnl": row["long_adjusted_pnl"],
                    "target_active_trade_count": row["active_trade_count"],
                    "target_active_pnl": row["active_trade_pnl"],
                }
            )
    return pd.DataFrame(rows)


def format_string_set(values: pd.Series) -> str:
    return ";".join(sorted({str(value) for value in values}))


def summarize(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    return (
        rows.groupby(
            ["policy_name", "min_train_months", "train_window_months"],
            dropna=False,
        )
        .agg(
            target_months=("target_month", "nunique"),
            target_start_month=("target_month", "min"),
            target_end_month=("target_month", "max"),
            triggered_months=("triggered", "sum"),
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
        .sort_values(["min_train_months", "train_window_months", "policy_name"])
    )


def run_audit(args: argparse.Namespace) -> Path:
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = output_dir / args.label
    suffix = 0
    while run_dir.exists():
        suffix += 1
        run_dir = output_dir / f"{args.label}_{suffix}"
    run_dir.mkdir(parents=True)

    if args.operator == "auto":
        if args.trigger_metric not in METRIC_DIRECTIONS:
            raise ValueError(f"unknown trigger metric for auto operator: {args.trigger_metric}")
        operator = METRIC_DIRECTIONS[args.trigger_metric]
    else:
        operator = args.operator
    rule = Rule(
        primary=parse_candidate(args.primary_candidate),
        defensive=parse_candidate(args.defensive_candidate),
        trigger_metric=args.trigger_metric,
        operator=operator,
        threshold=args.trigger_threshold,
    )
    source = normalize_summary(pd.read_csv(args.summary_by_run))
    all_rows = []
    for min_train_months in args.min_train_months:
        for train_window_months in args.train_window_months:
            all_rows.append(
                fixed_rule_rows(
                    source,
                    rule=rule,
                    min_train_months=min_train_months,
                    train_window_months=train_window_months,
                    recent_month_count=args.recent_month_count,
                )
            )
    rows = pd.concat(all_rows, ignore_index=True, sort=False) if all_rows else pd.DataFrame()
    summary = summarize(rows)

    rows.to_csv(run_dir / "fixed_rule_months.csv", index=False)
    summary.to_csv(run_dir / "fixed_rule_summary.csv", index=False)
    source.to_csv(run_dir / "input_summary_by_run.csv", index=False)
    metadata = {
        "summary_by_run": str(args.summary_by_run),
        "rule": rule,
        "min_train_months": args.min_train_months,
        "train_window_months": args.train_window_months,
        "recent_month_count": args.recent_month_count,
    }
    (run_dir / "config.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    if summary.empty:
        print("no fixed-rule rows")
    else:
        print(summary.head(args.print_rows).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-by-run", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="short_budget_fixed_rule_audit")
    parser.add_argument("--primary-candidate", default="5:0")
    parser.add_argument("--defensive-candidate", default="0:0")
    parser.add_argument("--trigger-metric", default="recent_short_losing_months")
    parser.add_argument("--operator", default="auto", choices=["auto", "lt", "le", "gt", "ge"])
    parser.add_argument("--trigger-threshold", type=float, default=1.0)
    parser.add_argument("--min-train-months", type=parse_csv_ints, default=[4, 5, 6, 7, 8])
    parser.add_argument("--train-window-months", type=parse_csv_ints, default=[0])
    parser.add_argument("--recent-month-count", type=int, default=3)
    parser.add_argument("--print-rows", type=int, default=30)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_audit(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
