#!/usr/bin/env python3
"""Build exit-capture targets and prior context risk diagnostics for entry-EV trades."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


CONTEXT_COLUMNS = ["direction", "combined_regime", "session_regime"]
DEFAULT_RISK_THRESHOLDS = "0.25,0.50,0.75"
DEFAULT_RISK_BUCKETS = "-inf,0,0.25,0.50,0.75,inf"


def local_json_default(value: Any) -> Any:
    try:
        return json_default(value)
    except TypeError:
        pass
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def parse_optional_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_float_csv(value: str) -> list[float]:
    floats: list[float] = []
    for part in parse_optional_csv(value):
        if part.lower() in {"inf", "+inf"}:
            floats.append(float("inf"))
        elif part.lower() == "-inf":
            floats.append(float("-inf"))
        else:
            floats.append(float(part))
    if not floats:
        raise argparse.ArgumentTypeError("at least one numeric value is required")
    return floats


def read_trade_frames(paths: list[Path]) -> pd.DataFrame:
    frames = [pd.read_csv(path) for path in paths]
    if not frames:
        raise ValueError("at least one enriched trade CSV is required")
    return pd.concat(frames, ignore_index=True)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    series = frame[column]
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(float(default)).astype(float).ne(0.0)
    normalized = series.astype(str).str.lower().str.strip()
    return normalized.isin({"true", "1", "yes", "y"})


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def normalize_trade_frame(frame: pd.DataFrame, *, name: str) -> pd.DataFrame:
    required = {
        "role",
        "candidate",
        "month",
        "direction",
        "entry_decision_timestamp",
        "combined_regime",
        "session_regime",
        "adjusted_pnl",
        "actual_taken_best_adjusted_pnl",
        "exit_regret",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name} enriched trades missing columns: {', '.join(missing)}")

    normalized = frame.copy()
    normalized["role"] = normalized["role"].astype(str)
    normalized["candidate"] = normalized["candidate"].astype(str)
    normalized["month"] = normalized["month"].astype(str).str.slice(0, 7)
    normalized["direction"] = normalized["direction"].astype(str).str.lower()
    normalized["combined_regime"] = normalized["combined_regime"].astype(str)
    normalized["session_regime"] = normalized["session_regime"].astype(str)
    normalized["entry_decision_timestamp"] = pd.to_datetime(
        normalized["entry_decision_timestamp"],
        utc=True,
    )
    for column in [
        "adjusted_pnl",
        "actual_taken_best_adjusted_pnl",
        "actual_best_adjusted_pnl",
        "exit_regret",
        "best_side_regret",
        "pred_taken_ev",
        "ev_overestimate_vs_realized",
        "ev_overestimate_vs_oracle",
        "holding_minutes",
        "actual_taken_best_holding_minutes",
    ]:
        normalized[column] = numeric_series(normalized, column)
    for column in ["direction_error", "no_edge_entry", "predicted_side_error"]:
        normalized[column] = bool_series(normalized, column)
    return normalized


def filter_frame(
    frame: pd.DataFrame,
    *,
    roles: set[str],
    candidates: set[str],
    months: set[str],
) -> pd.DataFrame:
    filtered = frame.copy()
    if roles:
        filtered = filtered[filtered["role"].isin(roles)].copy()
    if candidates:
        filtered = filtered[filtered["candidate"].isin(candidates)].copy()
    if months:
        filtered = filtered[filtered["month"].isin(months)].copy()
    return filtered


def add_exit_capture_targets(
    frame: pd.DataFrame,
    *,
    min_oracle_edge: float,
    low_capture_threshold: float,
    large_exit_regret_threshold: float,
) -> pd.DataFrame:
    output = frame.copy()
    adjusted = output["adjusted_pnl"].astype(float)
    oracle = output["actual_taken_best_adjusted_pnl"].astype(float)
    exit_regret = output["exit_regret"].astype(float)

    output["same_side_oracle_edge"] = oracle > min_oracle_edge
    output["same_side_missed_loss"] = (adjusted < 0.0) & output["same_side_oracle_edge"]
    output["exit_capture_ratio"] = np.where(
        output["same_side_oracle_edge"],
        adjusted / oracle.replace(0.0, np.nan),
        np.nan,
    )
    output["exit_capture_shortfall"] = np.where(
        output["same_side_oracle_edge"],
        np.maximum(oracle - adjusted, 0.0),
        0.0,
    )
    output["low_exit_capture"] = (
        output["same_side_oracle_edge"]
        & (pd.Series(output["exit_capture_ratio"], index=output.index) < low_capture_threshold)
    )
    output["large_exit_regret"] = exit_regret >= large_exit_regret_threshold
    output["exit_capture_failure"] = (
        output["same_side_missed_loss"]
        | output["low_exit_capture"]
        | output["large_exit_regret"]
    )
    output["realized_positive"] = adjusted > 0.0
    return output


def dedupe_prior_trades(prior: pd.DataFrame) -> pd.DataFrame:
    dedupe_columns = [
        "month",
        "entry_decision_timestamp",
        "direction",
        "combined_regime",
        "session_regime",
    ]
    return prior.drop_duplicates(subset=dedupe_columns).reset_index(drop=True)


def build_prior_exit_capture_stats(
    prior: pd.DataFrame,
    *,
    target_month: str,
    min_prior_months: int,
    recent_month_count: int,
) -> pd.DataFrame:
    if prior.empty:
        return pd.DataFrame()
    target_period = pd.Period(target_month, freq="M")
    prior_periods = pd.PeriodIndex(prior["month"].astype(str), freq="M")
    mask = prior_periods < target_period
    if recent_month_count > 0:
        mask &= prior_periods >= (target_period - recent_month_count)
    frame = prior[mask].copy()
    if frame.empty:
        return pd.DataFrame()
    if int(frame["month"].nunique()) < min_prior_months:
        return pd.DataFrame()
    frame["_loss_pnl"] = frame["adjusted_pnl"].astype(float).where(
        frame["adjusted_pnl"].astype(float) < 0.0,
        0.0,
    )
    frame["_oracle_capture_ratio_for_mean"] = pd.to_numeric(
        frame["exit_capture_ratio"],
        errors="coerce",
    ).where(frame["same_side_oracle_edge"].astype(bool))
    grouped = (
        frame.groupby(CONTEXT_COLUMNS, dropna=False)
        .agg(
            prior_exit_trade_count=("adjusted_pnl", "size"),
            prior_exit_month_count=("month", "nunique"),
            prior_exit_total_adjusted_pnl=("adjusted_pnl", "sum"),
            prior_exit_loss_adjusted_pnl=("_loss_pnl", "sum"),
            prior_same_side_oracle_count=("same_side_oracle_edge", "sum"),
            prior_same_side_missed_loss_count=("same_side_missed_loss", "sum"),
            prior_low_exit_capture_count=("low_exit_capture", "sum"),
            prior_large_exit_regret_count=("large_exit_regret", "sum"),
            prior_exit_capture_failure_count=("exit_capture_failure", "sum"),
            prior_exit_regret_sum=("exit_regret", "sum"),
            prior_exit_capture_shortfall_sum=("exit_capture_shortfall", "sum"),
            prior_exit_capture_ratio_mean=("_oracle_capture_ratio_for_mean", "mean"),
        )
        .reset_index()
    )
    grouped["target_month"] = target_month
    grouped["prior_exit_avg_adjusted_pnl"] = np.where(
        grouped["prior_exit_trade_count"] > 0,
        grouped["prior_exit_total_adjusted_pnl"] / grouped["prior_exit_trade_count"],
        0.0,
    )
    grouped["prior_exit_regret_mean"] = np.where(
        grouped["prior_exit_trade_count"] > 0,
        grouped["prior_exit_regret_sum"] / grouped["prior_exit_trade_count"],
        0.0,
    )
    grouped["prior_exit_capture_shortfall_mean"] = np.where(
        grouped["prior_exit_trade_count"] > 0,
        grouped["prior_exit_capture_shortfall_sum"] / grouped["prior_exit_trade_count"],
        0.0,
    )
    for column in [
        "same_side_oracle",
        "same_side_missed_loss",
        "low_exit_capture",
        "large_exit_regret",
        "exit_capture_failure",
    ]:
        count_column = f"prior_{column}_count"
        rate_column = f"prior_{column}_rate"
        if count_column in grouped.columns:
            grouped[rate_column] = np.where(
                grouped["prior_exit_trade_count"] > 0,
                grouped[count_column] / grouped["prior_exit_trade_count"],
                0.0,
            )
    grouped["prior_exit_capture_ratio_mean"] = grouped[
        "prior_exit_capture_ratio_mean"
    ].fillna(0.0)
    return grouped


def build_all_prior_exit_capture_stats(
    prior: pd.DataFrame,
    target_months: list[str],
    *,
    min_prior_months: int,
    recent_month_count: int,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for month in target_months:
        stats = build_prior_exit_capture_stats(
            prior,
            target_month=month,
            min_prior_months=min_prior_months,
            recent_month_count=recent_month_count,
        )
        if not stats.empty:
            frames.append(stats)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def add_prior_exit_capture_risk(
    target: pd.DataFrame,
    prior: pd.DataFrame,
    *,
    min_prior_months: int,
    recent_month_count: int,
    support_scale: float,
    regret_scale: float,
) -> pd.DataFrame:
    target = target.copy()
    target_months = sorted(target["month"].astype(str).unique().tolist())
    stats = build_all_prior_exit_capture_stats(
        prior,
        target_months,
        min_prior_months=min_prior_months,
        recent_month_count=recent_month_count,
    )
    if stats.empty:
        enriched = target
    else:
        enriched = target.merge(
            stats,
            how="left",
            left_on=["month", *CONTEXT_COLUMNS],
            right_on=["target_month", *CONTEXT_COLUMNS],
        )
    numeric_defaults = {
        "prior_exit_trade_count": 0.0,
        "prior_exit_month_count": 0.0,
        "prior_exit_total_adjusted_pnl": 0.0,
        "prior_exit_loss_adjusted_pnl": 0.0,
        "prior_same_side_oracle_count": 0.0,
        "prior_same_side_missed_loss_count": 0.0,
        "prior_low_exit_capture_count": 0.0,
        "prior_large_exit_regret_count": 0.0,
        "prior_exit_capture_failure_count": 0.0,
        "prior_exit_regret_sum": 0.0,
        "prior_exit_capture_shortfall_sum": 0.0,
        "prior_exit_capture_ratio_mean": 0.0,
        "prior_exit_avg_adjusted_pnl": 0.0,
        "prior_exit_regret_mean": 0.0,
        "prior_exit_capture_shortfall_mean": 0.0,
        "prior_same_side_oracle_rate": 0.0,
        "prior_same_side_missed_loss_rate": 0.0,
        "prior_low_exit_capture_rate": 0.0,
        "prior_large_exit_regret_rate": 0.0,
        "prior_exit_capture_failure_rate": 0.0,
    }
    for column, default in numeric_defaults.items():
        if column not in enriched.columns:
            enriched[column] = default
        enriched[column] = enriched[column].fillna(default).astype(float)
    enriched["prior_exit_has_context"] = enriched["prior_exit_trade_count"] > 0
    support_weight = np.clip(enriched["prior_exit_trade_count"] / support_scale, 0.0, 1.0)
    regret_component = np.clip(enriched["prior_exit_regret_mean"] / regret_scale, 0.0, 1.0)
    shortfall_component = np.clip(
        enriched["prior_exit_capture_shortfall_mean"] / regret_scale,
        0.0,
        1.0,
    )
    enriched["prior_exit_capture_support_weight"] = support_weight
    enriched["prior_exit_regret_risk_component"] = regret_component
    enriched["prior_exit_shortfall_risk_component"] = shortfall_component
    enriched["prior_exit_capture_risk_score"] = support_weight * (
        0.30 * enriched["prior_exit_capture_failure_rate"]
        + 0.25 * enriched["prior_low_exit_capture_rate"]
        + 0.20 * enriched["prior_same_side_missed_loss_rate"]
        + 0.15 * enriched["prior_large_exit_regret_rate"]
        + 0.10 * np.maximum(regret_component, shortfall_component)
    )
    return enriched


def add_risk_bucket(frame: pd.DataFrame, edges: list[float]) -> pd.DataFrame:
    if len(edges) < 2:
        raise ValueError("risk bucket edges must contain at least two values")
    enriched = frame.copy()
    labels: list[str] = []
    for left, right in zip(edges[:-1], edges[1:]):
        left_text = "-inf" if np.isneginf(left) else f"{left:.2f}"
        right_text = "inf" if np.isposinf(right) else f"{right:.2f}"
        labels.append(f"({left_text},{right_text}]")
    enriched["prior_exit_capture_risk_bucket"] = pd.cut(
        enriched["prior_exit_capture_risk_score"].astype(float),
        bins=edges,
        labels=labels,
        include_lowest=True,
    ).astype(str)
    enriched.loc[
        ~enriched["prior_exit_has_context"].astype(bool),
        "prior_exit_capture_risk_bucket",
    ] = "no_prior"
    return enriched


def bool_mean(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    return float(series.fillna(False).astype(bool).mean())


def numeric_mean(series: pd.Series) -> float:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() == 0:
        return 0.0
    return float(numeric.mean())


def summarize_trade_groups(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_columns)
    working = frame.copy()
    adjusted = working["adjusted_pnl"].astype(float)
    working["_loss_pnl"] = adjusted.where(adjusted < 0.0, 0.0)
    rows: list[dict[str, Any]] = []
    for key, group in working.groupby(group_columns, dropna=False, observed=True):
        if not isinstance(key, tuple):
            key = (key,)
        row = dict(zip(group_columns, key))
        trade_count = int(len(group))
        row.update(
            {
                "trade_count": trade_count,
                "total_adjusted_pnl": float(group["adjusted_pnl"].astype(float).sum()),
                "loss_adjusted_pnl": float(group["_loss_pnl"].astype(float).sum()),
                "win_rate": float((group["adjusted_pnl"].astype(float) > 0.0).mean()),
                "same_side_oracle_edge_rate": bool_mean(group["same_side_oracle_edge"]),
                "same_side_missed_loss_count": int(group["same_side_missed_loss"].sum()),
                "same_side_missed_loss_rate": bool_mean(group["same_side_missed_loss"]),
                "low_exit_capture_count": int(group["low_exit_capture"].sum()),
                "low_exit_capture_rate": bool_mean(group["low_exit_capture"]),
                "large_exit_regret_count": int(group["large_exit_regret"].sum()),
                "large_exit_regret_rate": bool_mean(group["large_exit_regret"]),
                "exit_capture_failure_count": int(group["exit_capture_failure"].sum()),
                "exit_capture_failure_rate": bool_mean(group["exit_capture_failure"]),
                "exit_regret_sum": float(group["exit_regret"].astype(float).sum()),
                "exit_capture_shortfall_sum": float(
                    group["exit_capture_shortfall"].astype(float).sum()
                ),
                "exit_capture_ratio_mean": numeric_mean(group["exit_capture_ratio"]),
                "direction_error_rate": bool_mean(group["direction_error"]),
                "no_edge_rate": bool_mean(group["no_edge_entry"]),
                "prior_exit_has_context_rate": bool_mean(group["prior_exit_has_context"]),
                "prior_exit_capture_risk_score_mean": float(
                    group["prior_exit_capture_risk_score"].astype(float).mean()
                ),
                "prior_exit_trade_count_mean": float(
                    group["prior_exit_trade_count"].astype(float).mean()
                ),
                "prior_exit_capture_failure_rate_mean": float(
                    group["prior_exit_capture_failure_rate"].astype(float).mean()
                ),
                "prior_low_exit_capture_rate_mean": float(
                    group["prior_low_exit_capture_rate"].astype(float).mean()
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["total_adjusted_pnl", "exit_capture_failure_count", "trade_count"],
        ascending=[True, False, False],
    )


def summarize_thresholds(
    frame: pd.DataFrame,
    group_columns: list[str],
    thresholds: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped = [((), frame)] if not group_columns else frame.groupby(group_columns, dropna=False)
    for key, group in grouped:
        if group_columns and not isinstance(key, tuple):
            key = (key,)
        group_prefix = dict(zip(group_columns, key)) if group_columns else {}
        total_pnl = float(group["adjusted_pnl"].astype(float).sum())
        total_trade_count = int(len(group))
        total_failures = int(group["exit_capture_failure"].sum())
        for threshold in thresholds:
            flagged = group[group["prior_exit_capture_risk_score"].astype(float) >= threshold]
            flagged_pnl = float(flagged["adjusted_pnl"].astype(float).sum())
            flagged_count = int(len(flagged))
            flagged_failures = int(flagged["exit_capture_failure"].sum())
            row = {
                **group_prefix,
                "flag": f"prior_exit_capture_risk_gte_{threshold:.2f}",
                "threshold": float(threshold),
                "total_trade_count": total_trade_count,
                "total_adjusted_pnl": total_pnl,
                "total_exit_capture_failure_count": total_failures,
                "flagged_trade_count": flagged_count,
                "flagged_adjusted_pnl": flagged_pnl,
                "flagged_exit_capture_failure_count": flagged_failures,
                "flagged_same_side_missed_loss_count": int(
                    flagged["same_side_missed_loss"].sum()
                ),
                "flagged_low_exit_capture_count": int(flagged["low_exit_capture"].sum()),
                "flagged_large_exit_regret_count": int(flagged["large_exit_regret"].sum()),
                "flagged_exit_regret_sum": float(
                    flagged["exit_regret"].astype(float).sum()
                ),
                "flagged_exit_capture_shortfall_sum": float(
                    flagged["exit_capture_shortfall"].astype(float).sum()
                ),
                "kept_adjusted_pnl_if_removed": float(total_pnl - flagged_pnl),
                "block_delta_if_removed": float(-flagged_pnl),
                "flagged_trade_share": (
                    float(flagged_count / total_trade_count) if total_trade_count else 0.0
                ),
                "flagged_failure_precision": (
                    float(flagged_failures / flagged_count) if flagged_count else 0.0
                ),
                "failure_recall": (
                    float(flagged_failures / total_failures) if total_failures else 0.0
                ),
            }
            rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["block_delta_if_removed", "flagged_exit_capture_failure_count"],
        ascending=[False, False],
    )


def build_diagnostics(args: argparse.Namespace) -> Path:
    target = normalize_trade_frame(
        read_trade_frames(args.target_enriched_trades),
        name="target",
    )
    prior_paths = args.prior_enriched_trades or args.target_enriched_trades
    prior = normalize_trade_frame(read_trade_frames(prior_paths), name="prior")
    target = filter_frame(
        target,
        roles=set(parse_optional_csv(args.target_roles)),
        candidates=set(parse_optional_csv(args.candidates)),
        months=set(parse_optional_csv(args.months)),
    )
    prior = filter_frame(
        prior,
        roles=set(parse_optional_csv(args.prior_roles)),
        candidates=set(parse_optional_csv(args.candidates)),
        months=set(),
    )
    if target.empty:
        raise ValueError("no target trades remain after filters")
    target = add_exit_capture_targets(
        target,
        min_oracle_edge=args.min_oracle_edge,
        low_capture_threshold=args.low_capture_threshold,
        large_exit_regret_threshold=args.large_exit_regret_threshold,
    )
    prior = add_exit_capture_targets(
        prior,
        min_oracle_edge=args.min_oracle_edge,
        low_capture_threshold=args.low_capture_threshold,
        large_exit_regret_threshold=args.large_exit_regret_threshold,
    )
    if args.dedupe_prior:
        prior = dedupe_prior_trades(prior)

    enriched = add_prior_exit_capture_risk(
        target,
        prior,
        min_prior_months=args.min_prior_months,
        recent_month_count=args.recent_month_count,
        support_scale=args.support_scale,
        regret_scale=args.regret_scale,
    )
    enriched = add_risk_bucket(enriched, parse_float_csv(args.risk_buckets))
    thresholds = parse_float_csv(args.risk_thresholds)

    run_dir = make_run_dir(args.output_dir, args.label)
    enriched.to_csv(run_dir / "enriched_exit_capture_targets.csv", index=False)

    role_candidate = summarize_trade_groups(enriched, ["role", "candidate"])
    role_candidate.to_csv(run_dir / "role_candidate_exit_capture_target_summary.csv", index=False)

    role_month = summarize_trade_groups(enriched, ["role", "candidate", "month"])
    role_month.to_csv(run_dir / "role_month_exit_capture_target_summary.csv", index=False)

    context = summarize_trade_groups(
        enriched,
        ["role", "candidate", "direction", "combined_regime", "session_regime"],
    )
    context.to_csv(run_dir / "context_exit_capture_target_summary.csv", index=False)
    context.head(args.top_n).to_csv(run_dir / "top_negative_exit_capture_contexts.csv", index=False)

    bucket_summary = summarize_trade_groups(
        enriched,
        ["role", "candidate", "prior_exit_capture_risk_bucket"],
    )
    bucket_summary.to_csv(run_dir / "risk_bucket_exit_capture_summary.csv", index=False)

    threshold_summary = summarize_thresholds(enriched, ["role", "candidate"], thresholds)
    threshold_summary.to_csv(run_dir / "risk_threshold_exit_capture_summary.csv", index=False)

    overall_threshold_summary = summarize_thresholds(enriched, [], thresholds)
    overall_threshold_summary.to_csv(
        run_dir / "overall_risk_threshold_exit_capture_summary.csv",
        index=False,
    )

    config = {
        "target_enriched_trades": args.target_enriched_trades,
        "prior_enriched_trades": prior_paths,
        "target_roles": args.target_roles,
        "prior_roles": args.prior_roles,
        "candidates": args.candidates,
        "months": args.months,
        "dedupe_prior": args.dedupe_prior,
        "min_oracle_edge": args.min_oracle_edge,
        "low_capture_threshold": args.low_capture_threshold,
        "large_exit_regret_threshold": args.large_exit_regret_threshold,
        "min_prior_months": args.min_prior_months,
        "recent_month_count": args.recent_month_count,
        "support_scale": args.support_scale,
        "regret_scale": args.regret_scale,
        "risk_thresholds": thresholds,
        "risk_buckets": parse_float_csv(args.risk_buckets),
        "target_trade_count": int(len(target)),
        "prior_trade_count": int(len(prior)),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Overall prior exit-capture risk thresholds:")
    print(
        overall_threshold_summary[
            [
                "flag",
                "flagged_trade_count",
                "flagged_adjusted_pnl",
                "block_delta_if_removed",
                "flagged_exit_capture_failure_count",
                "flagged_failure_precision",
                "failure_recall",
            ]
        ].to_string(index=False)
    )
    print("\nWorst role/month rows:")
    print(
        role_month[
            [
                "role",
                "candidate",
                "month",
                "trade_count",
                "total_adjusted_pnl",
                "exit_capture_failure_count",
                "same_side_missed_loss_count",
                "large_exit_regret_count",
                "prior_exit_capture_risk_score_mean",
            ]
        ].head(args.top_n).to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-enriched-trades", type=Path, action="append", required=True)
    parser.add_argument("--prior-enriched-trades", type=Path, action="append", default=[])
    parser.add_argument("--target-roles", default="")
    parser.add_argument("--prior-roles", default="")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--months", default="")
    parser.add_argument("--dedupe-prior", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--min-oracle-edge", type=float, default=0.0)
    parser.add_argument("--low-capture-threshold", type=float, default=0.25)
    parser.add_argument("--large-exit-regret-threshold", type=float, default=10.0)
    parser.add_argument("--min-prior-months", type=int, default=1)
    parser.add_argument("--recent-month-count", type=int, default=0)
    parser.add_argument("--support-scale", type=float, default=4.0)
    parser.add_argument("--regret-scale", type=float, default=20.0)
    parser.add_argument("--risk-thresholds", default=DEFAULT_RISK_THRESHOLDS)
    parser.add_argument("--risk-buckets", default=DEFAULT_RISK_BUCKETS)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    parser.add_argument("--label", default="entry_ev_exit_capture_target_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
