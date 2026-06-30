#!/usr/bin/env python3
"""Prior-only trigger diagnostics for switching to a defensive short budget."""

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
    "recent_pred_short_bias_mean": "ge",
    "recent_pred_short_bias_max": "ge",
    "recent_pred_short_share_mean": "ge",
    "recent_actual_short_share_mean": "lt",
    "recent_pred_match_rate_mean": "lt",
    "recent_pred_side_score_mean": "lt",
}
DEFAULT_THRESHOLDS = {
    "recent_short_pnl": (-100.0, -50.0, 0.0, 50.0, 100.0, 150.0),
    "recent_total_pnl": (-100.0, -50.0, 0.0, 50.0, 100.0, 150.0),
    "recent_worst_month_pnl": (-200.0, -100.0, -50.0, 0.0, 50.0),
    "recent_short_worst_month_pnl": (-200.0, -100.0, -50.0, 0.0, 50.0),
    "recent_short_losing_months": (1.0, 2.0, 3.0),
    "recent_total_losing_months": (1.0, 2.0, 3.0),
    "recent_pred_short_bias_mean": (0.15, 0.18, 0.20, 0.22, 0.25, 0.30, 0.35, 0.40),
    "recent_pred_short_bias_max": (0.20, 0.25, 0.30, 0.35, 0.40),
    "recent_pred_short_share_mean": (0.55, 0.60, 0.65, 0.70, 0.75),
    "recent_actual_short_share_mean": (0.30, 0.35, 0.40, 0.45),
    "recent_pred_match_rate_mean": (0.45, 0.48, 0.50, 0.52, 0.55),
    "recent_pred_side_score_mean": (-5.0, -4.0, -3.0, -2.0, -1.0, 0.0),
}
PREDICTION_SUMMARY_COLUMNS = {
    "pred_ev_short_share",
    "actual_label_short_share",
    "pred_short_minus_actual_label_short_share",
    "pred_ev_matches_nonflat_label_rate",
    "pred_side_score_mean",
}


@dataclass(frozen=True)
class Candidate:
    short_gap_threshold: float
    context_entry_budget: float


@dataclass(frozen=True)
class RuleSpec:
    name: str
    primary: Candidate
    defensive: Candidate
    trigger_metric: str
    operator: str
    threshold: float


def parse_csv_strings(value: str) -> list[str]:
    values = [part.strip() for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def parse_candidate(value: str) -> Candidate:
    parts = [part.strip() for part in value.split(":")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("candidate must be formatted as short_gap:budget")
    try:
        return Candidate(float(parts[0]), float(parts[1]))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("candidate values must be numeric") from exc


def parse_candidates(value: str) -> list[Candidate]:
    return [parse_candidate(part) for part in parse_csv_strings(value)]


def parse_thresholds(value: str) -> tuple[float, ...]:
    try:
        return tuple(float(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("thresholds must be numeric") from exc


def parse_csv_paths(value: str) -> list[Path]:
    return [Path(part) for part in parse_csv_strings(value)]


def local_json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Candidate):
        return {
            "short_gap_threshold": value.short_gap_threshold,
            "context_entry_budget": value.context_entry_budget,
        }
    if isinstance(value, RuleSpec):
        return {
            "name": value.name,
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
    numeric_columns = [
        "trade_count",
        "total_adjusted_pnl",
        "max_drawdown",
        "forced_exit_count",
        "short_adjusted_pnl",
        "long_adjusted_pnl",
        "active_trade_count",
        "active_trade_pnl",
        *DEFAULT_CANDIDATE_COLUMNS,
    ]
    for column in numeric_columns:
        output[column] = pd.to_numeric(output[column], errors="raise")
    return output.sort_values(["month", *DEFAULT_CANDIDATE_COLUMNS]).reset_index(drop=True)


def normalize_prediction_summary(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    if "month" not in output.columns:
        if "dataset_month" not in output.columns:
            raise ValueError("prediction summary missing month or dataset_month")
        output = output.rename(columns={"dataset_month": "month"})
    missing = sorted(PREDICTION_SUMMARY_COLUMNS - set(output.columns))
    if missing:
        raise ValueError(
            "prediction summary missing columns: " + ", ".join(missing)
        )
    output["month"] = output["month"].astype(str)
    for column in PREDICTION_SUMMARY_COLUMNS:
        output[column] = pd.to_numeric(output[column], errors="raise")
    return output.sort_values("month").reset_index(drop=True)


def read_prediction_summaries(paths: list[Path]) -> pd.DataFrame | None:
    if not paths:
        return None
    frames = []
    for path in paths:
        frames.append(normalize_prediction_summary(pd.read_csv(path)))
    output = pd.concat(frames, ignore_index=True, sort=False)
    return (
        output.drop_duplicates("month", keep="last")
        .sort_values("month")
        .reset_index(drop=True)
    )


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


def prediction_metric_bundle(
    prediction_summary: pd.DataFrame | None,
    recent_months: list[str],
) -> dict[str, float]:
    if prediction_summary is None:
        return {}
    recent = prediction_summary[prediction_summary["month"].isin(recent_months)]
    if recent.empty:
        raise ValueError("prediction summary has no rows for recent prior months")
    return {
        "recent_pred_short_bias_mean": float(
            recent["pred_short_minus_actual_label_short_share"].mean()
        ),
        "recent_pred_short_bias_max": float(
            recent["pred_short_minus_actual_label_short_share"].max()
        ),
        "recent_pred_short_share_mean": float(recent["pred_ev_short_share"].mean()),
        "recent_actual_short_share_mean": float(
            recent["actual_label_short_share"].mean()
        ),
        "recent_pred_match_rate_mean": float(
            recent["pred_ev_matches_nonflat_label_rate"].mean()
        ),
        "recent_pred_side_score_mean": float(recent["pred_side_score_mean"].mean()),
    }


def metric_bundle(
    prior: pd.DataFrame,
    candidate: Candidate,
    recent_month_count: int,
    prediction_summary: pd.DataFrame | None = None,
) -> dict[str, float]:
    months = sorted(prior["month"].unique())
    recent_months = months[-recent_month_count:] if recent_month_count > 0 else months
    recent = prior[prior["month"].isin(recent_months) & candidate_mask(prior, candidate)]
    if recent.empty:
        raise ValueError(f"candidate not found in recent prior frame: {candidate_label(candidate)}")
    output = {
        "recent_months": float(len(recent_months)),
        "recent_total_pnl": float(recent["total_adjusted_pnl"].sum()),
        "recent_short_pnl": float(recent["short_adjusted_pnl"].sum()),
        "recent_worst_month_pnl": float(recent["total_adjusted_pnl"].min()),
        "recent_short_worst_month_pnl": float(recent["short_adjusted_pnl"].min()),
        "recent_short_losing_months": float((recent["short_adjusted_pnl"] < 0).sum()),
        "recent_total_losing_months": float((recent["total_adjusted_pnl"] < 0).sum()),
    }
    output.update(prediction_metric_bundle(prediction_summary, recent_months))
    return output


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


def make_rule_specs(
    *,
    primary_candidates: list[Candidate],
    defensive_candidate: Candidate,
    metrics: list[str],
    threshold_overrides: dict[str, tuple[float, ...]] | None = None,
) -> list[RuleSpec]:
    rules: list[RuleSpec] = []
    for primary in primary_candidates:
        primary_name = candidate_label(primary).replace("|", "_")
        rules.append(
            RuleSpec(
                name=f"always_primary_{primary_name}",
                primary=primary,
                defensive=primary,
                trigger_metric="recent_short_pnl",
                operator="lt",
                threshold=-float("inf"),
            )
        )
        rules.append(
            RuleSpec(
                name=f"always_defensive_from_{primary_name}",
                primary=primary,
                defensive=defensive_candidate,
                trigger_metric="recent_short_pnl",
                operator="lt",
                threshold=float("inf"),
            )
        )
        for metric in metrics:
            if metric not in METRIC_DIRECTIONS:
                raise ValueError(f"unknown trigger metric: {metric}")
            thresholds = (
                threshold_overrides.get(metric)
                if threshold_overrides is not None and metric in threshold_overrides
                else DEFAULT_THRESHOLDS[metric]
            )
            operator = METRIC_DIRECTIONS[metric]
            for threshold in thresholds:
                rules.append(
                    RuleSpec(
                        name=(
                            f"{primary_name}_{metric}_{operator}_{threshold:g}_"
                            f"to_{candidate_label(defensive_candidate).replace('|', '_')}"
                        ),
                        primary=primary,
                        defensive=defensive_candidate,
                        trigger_metric=metric,
                        operator=operator,
                        threshold=float(threshold),
                    )
                )
    return rules


def walkforward_trigger_selection(
    frame: pd.DataFrame,
    *,
    rules: list[RuleSpec],
    min_train_months: int,
    train_window_months: int,
    recent_month_count: int,
    prediction_summary: pd.DataFrame | None = None,
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
        target_rows = data[data["month"] == target_month]
        for rule in rules:
            metrics = metric_bundle(
                prior,
                rule.primary,
                recent_month_count,
                prediction_summary=prediction_summary,
            )
            trigger_value = metrics[rule.trigger_metric]
            triggered = should_trigger(trigger_value, rule.operator, rule.threshold)
            selected = rule.defensive if triggered else rule.primary
            target = target_rows[candidate_mask(target_rows, selected)]
            if target.empty:
                continue
            target_row = target.iloc[0]
            rows.append(
                {
                    "selection_name": rule.name,
                    "target_month": target_month,
                    "prior_months": len(prior_months),
                    "prior_start_month": prior_months[0],
                    "prior_end_month": prior_months[-1],
                    "primary_candidate": candidate_label(rule.primary),
                    "defensive_candidate": candidate_label(rule.defensive),
                    "selected_candidate": candidate_label(selected),
                    "selected_short_gap_threshold": selected.short_gap_threshold,
                    "selected_context_entry_budget": selected.context_entry_budget,
                    "trigger_metric": rule.trigger_metric,
                    "trigger_operator": rule.operator,
                    "trigger_threshold": rule.threshold,
                    "trigger_value": trigger_value,
                    "triggered": triggered,
                    **metrics,
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


def format_string_set(values: pd.Series) -> str:
    return ";".join(sorted({str(value) for value in values}))


def summarize_walkforward(selection: pd.DataFrame) -> pd.DataFrame:
    if selection.empty:
        return pd.DataFrame()
    return (
        selection.groupby("selection_name", dropna=False)
        .agg(
            target_months=("target_month", "nunique"),
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
            primary_candidate=("primary_candidate", "first"),
            defensive_candidate=("defensive_candidate", "first"),
            trigger_metric=("trigger_metric", "first"),
            trigger_operator=("trigger_operator", "first"),
            trigger_threshold=("trigger_threshold", "first"),
            selected_candidates=("selected_candidate", format_string_set),
        )
        .reset_index()
        .sort_values(["total_pnl", "worst_month_pnl"], ascending=[False, False])
    )


def parse_threshold_overrides(values: list[str]) -> dict[str, tuple[float, ...]]:
    overrides: dict[str, tuple[float, ...]] = {}
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError("threshold override must be metric=v1,v2")
        metric, raw_thresholds = value.split("=", 1)
        metric = metric.strip()
        if metric not in METRIC_DIRECTIONS:
            raise argparse.ArgumentTypeError(f"unknown metric in override: {metric}")
        overrides[metric] = parse_thresholds(raw_thresholds)
    return overrides


def run_selection(args: argparse.Namespace) -> Path:
    source = normalize_summary(pd.read_csv(args.summary_by_run))
    prediction_summary = read_prediction_summaries(args.prediction_month_summaries)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = output_dir / args.label
    suffix = 0
    while run_dir.exists():
        suffix += 1
        run_dir = output_dir / f"{args.label}_{suffix}"
    run_dir.mkdir(parents=True)

    primary_candidates = parse_candidates(args.primary_candidates)
    defensive_candidate = parse_candidate(args.defensive_candidate)
    metrics = parse_csv_strings(args.trigger_metrics)
    threshold_overrides = parse_threshold_overrides(args.threshold_override)
    rules = make_rule_specs(
        primary_candidates=primary_candidates,
        defensive_candidate=defensive_candidate,
        metrics=metrics,
        threshold_overrides=threshold_overrides,
    )
    selection = walkforward_trigger_selection(
        source,
        rules=rules,
        min_train_months=args.min_train_months,
        train_window_months=args.train_window_months,
        recent_month_count=args.recent_month_count,
        prediction_summary=prediction_summary,
    )
    summary = summarize_walkforward(selection)
    selection.to_csv(run_dir / "walkforward_selection.csv", index=False)
    summary.to_csv(run_dir / "walkforward_summary.csv", index=False)
    source.to_csv(run_dir / "input_summary_by_run.csv", index=False)
    metadata = {
        "summary_by_run": str(args.summary_by_run),
        "primary_candidates": primary_candidates,
        "defensive_candidate": defensive_candidate,
        "trigger_metrics": metrics,
        "threshold_overrides": threshold_overrides,
        "prediction_month_summaries": [
            str(path) for path in args.prediction_month_summaries
        ],
        "min_train_months": args.min_train_months,
        "train_window_months": args.train_window_months,
        "recent_month_count": args.recent_month_count,
        "rules": rules,
    }
    (run_dir / "config.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    if summary.empty:
        print("no walk-forward selection rows")
    else:
        print(summary.head(args.print_rows).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-by-run", type=Path, required=True)
    parser.add_argument(
        "--prediction-month-summaries",
        type=parse_csv_paths,
        default=[],
        help="Optional comma-separated prediction_month_summary.csv paths",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="short_budget_drift_trigger_selection")
    parser.add_argument("--primary-candidates", default="5:0,5:1,0:1")
    parser.add_argument("--defensive-candidate", default="0:0")
    parser.add_argument(
        "--trigger-metrics",
        default=(
            "recent_short_pnl,recent_total_pnl,recent_worst_month_pnl,"
            "recent_short_worst_month_pnl,recent_short_losing_months,"
            "recent_total_losing_months"
        ),
    )
    parser.add_argument(
        "--threshold-override",
        action="append",
        default=[],
        help="Override default metric thresholds as metric=v1,v2",
    )
    parser.add_argument("--min-train-months", type=int, default=4)
    parser.add_argument("--train-window-months", type=int, default=0)
    parser.add_argument("--recent-month-count", type=int, default=3)
    parser.add_argument("--print-rows", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_selection(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
