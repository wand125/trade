#!/usr/bin/env python3
"""Diagnose prior context-side risk as a score instead of a hard block."""

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
        raise ValueError("at least one trade CSV is required")
    return pd.concat(frames, ignore_index=True)


def normalize_trade_frame(frame: pd.DataFrame, *, name: str) -> pd.DataFrame:
    required = {
        "month",
        "direction",
        "entry_decision_timestamp",
        "combined_regime",
        "session_regime",
        "adjusted_pnl",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name} trades missing columns: {', '.join(missing)}")
    normalized = frame.copy()
    normalized["month"] = normalized["month"].astype(str).str.slice(0, 7)
    normalized["entry_decision_timestamp"] = pd.to_datetime(
        normalized["entry_decision_timestamp"],
        utc=True,
    )
    normalized["adjusted_pnl"] = normalized["adjusted_pnl"].astype(float)
    normalized["direction"] = normalized["direction"].astype(str).str.lower()
    normalized["combined_regime"] = normalized["combined_regime"].astype(str)
    normalized["session_regime"] = normalized["session_regime"].astype(str)
    if "direction_error" not in normalized.columns:
        normalized["direction_error"] = False
    normalized["direction_error"] = normalized["direction_error"].fillna(False).astype(bool)
    if "exit_regret" not in normalized.columns:
        normalized["exit_regret"] = 0.0
    normalized["exit_regret"] = normalized["exit_regret"].fillna(0.0).astype(float)
    if "role" not in normalized.columns:
        normalized["role"] = ""
    if "candidate" not in normalized.columns:
        normalized["candidate"] = ""
    return normalized


def filter_frame(
    frame: pd.DataFrame,
    *,
    roles: set[str],
    candidates: set[str],
) -> pd.DataFrame:
    filtered = frame.copy()
    if roles:
        filtered = filtered[filtered["role"].astype(str).isin(roles)].copy()
    if candidates:
        filtered = filtered[filtered["candidate"].astype(str).isin(candidates)].copy()
    return filtered


def dedupe_prior_trades(prior: pd.DataFrame) -> pd.DataFrame:
    dedupe_columns = [
        "month",
        "entry_decision_timestamp",
        "direction",
        "combined_regime",
        "session_regime",
    ]
    return prior.drop_duplicates(subset=dedupe_columns).reset_index(drop=True)


def build_prior_context_stats(
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
    frame["_loss"] = frame["adjusted_pnl"].astype(float) < 0
    frame["_loss_pnl"] = frame["adjusted_pnl"].astype(float).where(frame["_loss"], 0.0)
    grouped = (
        frame.groupby(CONTEXT_COLUMNS, dropna=False)
        .agg(
            prior_trade_count=("adjusted_pnl", "size"),
            prior_month_count=("month", "nunique"),
            prior_total_adjusted_pnl=("adjusted_pnl", "sum"),
            prior_loss_adjusted_pnl=("_loss_pnl", "sum"),
            prior_loss_count=("_loss", "sum"),
            prior_direction_error_count=("direction_error", "sum"),
            prior_exit_regret_sum=("exit_regret", "sum"),
        )
        .reset_index()
    )
    grouped["target_month"] = target_month
    grouped["prior_avg_adjusted_pnl"] = np.where(
        grouped["prior_trade_count"] > 0,
        grouped["prior_total_adjusted_pnl"] / grouped["prior_trade_count"],
        0.0,
    )
    grouped["prior_loss_rate"] = np.where(
        grouped["prior_trade_count"] > 0,
        grouped["prior_loss_count"] / grouped["prior_trade_count"],
        0.0,
    )
    grouped["prior_direction_error_rate"] = np.where(
        grouped["prior_trade_count"] > 0,
        grouped["prior_direction_error_count"] / grouped["prior_trade_count"],
        0.0,
    )
    grouped["prior_exit_regret_mean"] = np.where(
        grouped["prior_trade_count"] > 0,
        grouped["prior_exit_regret_sum"] / grouped["prior_trade_count"],
        0.0,
    )
    return grouped


def build_all_prior_context_stats(
    prior: pd.DataFrame,
    target_months: list[str],
    *,
    min_prior_months: int,
    recent_month_count: int,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for month in target_months:
        stats = build_prior_context_stats(
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


def add_prior_context_risk(
    target: pd.DataFrame,
    prior: pd.DataFrame,
    *,
    min_prior_months: int,
    recent_month_count: int,
    support_scale: float,
    pnl_scale: float,
) -> pd.DataFrame:
    target = target.copy()
    target_months = sorted(target["month"].astype(str).unique().tolist())
    stats = build_all_prior_context_stats(
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
        "prior_trade_count": 0.0,
        "prior_month_count": 0.0,
        "prior_total_adjusted_pnl": 0.0,
        "prior_loss_adjusted_pnl": 0.0,
        "prior_loss_count": 0.0,
        "prior_direction_error_count": 0.0,
        "prior_exit_regret_sum": 0.0,
        "prior_avg_adjusted_pnl": 0.0,
        "prior_loss_rate": 0.0,
        "prior_direction_error_rate": 0.0,
        "prior_exit_regret_mean": 0.0,
    }
    for column, default in numeric_defaults.items():
        if column not in enriched.columns:
            enriched[column] = default
        enriched[column] = enriched[column].fillna(default).astype(float)
    enriched["prior_has_context"] = enriched["prior_trade_count"] > 0
    support_weight = np.clip(enriched["prior_trade_count"] / support_scale, 0.0, 1.0)
    pnl_component = np.clip(-enriched["prior_avg_adjusted_pnl"] / pnl_scale, 0.0, 1.0)
    enriched["prior_context_support_weight"] = support_weight
    enriched["prior_context_pnl_risk_component"] = pnl_component
    enriched["prior_context_risk_score"] = support_weight * (
        0.45 * enriched["prior_direction_error_rate"]
        + 0.35 * enriched["prior_loss_rate"]
        + 0.20 * pnl_component
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
    enriched["prior_context_risk_bucket"] = pd.cut(
        enriched["prior_context_risk_score"].astype(float),
        bins=edges,
        labels=labels,
        include_lowest=True,
    ).astype(str)
    enriched.loc[
        ~enriched["prior_has_context"].astype(bool),
        "prior_context_risk_bucket",
    ] = "no_prior"
    return enriched


def bool_mean(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    return float(series.fillna(False).astype(bool).mean())


def summarize_trade_groups(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_columns)
    working = frame.copy()
    working["_loss"] = working["adjusted_pnl"].astype(float) < 0
    working["_loss_pnl"] = working["adjusted_pnl"].astype(float).where(working["_loss"], 0.0)
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
                "avg_adjusted_pnl": float(group["adjusted_pnl"].astype(float).mean()),
                "win_rate": float((group["adjusted_pnl"].astype(float) > 0).mean()),
                "prior_has_context_rate": bool_mean(group["prior_has_context"]),
                "prior_context_risk_score_mean": float(
                    group["prior_context_risk_score"].astype(float).mean()
                ),
                "prior_trade_count_mean": float(group["prior_trade_count"].astype(float).mean()),
                "prior_total_adjusted_pnl_mean": float(
                    group["prior_total_adjusted_pnl"].astype(float).mean()
                ),
                "prior_direction_error_rate_mean": float(
                    group["prior_direction_error_rate"].astype(float).mean()
                ),
                "prior_loss_rate_mean": float(group["prior_loss_rate"].astype(float).mean()),
                "prior_avg_adjusted_pnl_mean": float(
                    group["prior_avg_adjusted_pnl"].astype(float).mean()
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["total_adjusted_pnl", "trade_count"],
        ascending=[True, False],
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
        for threshold in thresholds:
            flagged = group[group["prior_context_risk_score"].astype(float) >= threshold]
            flagged_pnl = float(flagged["adjusted_pnl"].astype(float).sum())
            row = {
                **group_prefix,
                "flag": f"risk_score_gte_{threshold:.2f}",
                "threshold": float(threshold),
                "total_trade_count": total_trade_count,
                "total_adjusted_pnl": total_pnl,
                "flagged_trade_count": int(len(flagged)),
                "flagged_adjusted_pnl": flagged_pnl,
                "kept_adjusted_pnl_if_blocked": float(total_pnl - flagged_pnl),
                "block_delta_if_removed": float(-flagged_pnl),
            }
            row["flagged_trade_share"] = (
                float(row["flagged_trade_count"] / total_trade_count)
                if total_trade_count
                else 0.0
            )
            rows.append(row)

        hard_flag = (
            (group["prior_trade_count"].astype(float) >= 1)
            & (group["prior_direction_error_rate"].astype(float) >= 1.0)
            & (group["prior_total_adjusted_pnl"].astype(float) < 0)
        )
        flagged = group[hard_flag]
        flagged_pnl = float(flagged["adjusted_pnl"].astype(float).sum())
        rows.append(
            {
                **group_prefix,
                "flag": "direction_error_1_and_prior_pnl_negative",
                "threshold": np.nan,
                "total_trade_count": total_trade_count,
                "total_adjusted_pnl": total_pnl,
                "flagged_trade_count": int(len(flagged)),
                "flagged_adjusted_pnl": flagged_pnl,
                "kept_adjusted_pnl_if_blocked": float(total_pnl - flagged_pnl),
                "block_delta_if_removed": float(-flagged_pnl),
                "flagged_trade_share": (
                    float(len(flagged) / total_trade_count) if total_trade_count else 0.0
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["block_delta_if_removed", "flagged_trade_count"],
        ascending=[False, False],
    )


def build_diagnostics(args: argparse.Namespace) -> Path:
    target = normalize_trade_frame(
        read_trade_frames(args.target_enriched_trades),
        name="target",
    )
    prior_paths = args.prior_enriched_trades or args.target_enriched_trades
    prior = normalize_trade_frame(
        read_trade_frames(prior_paths),
        name="prior",
    )
    target = filter_frame(
        target,
        roles=set(parse_optional_csv(args.target_roles)),
        candidates=set(parse_optional_csv(args.candidates)),
    )
    prior = filter_frame(
        prior,
        roles=set(parse_optional_csv(args.prior_roles)),
        candidates=set(parse_optional_csv(args.candidates)),
    )
    if target.empty:
        raise ValueError("no target trades remain after filters")
    if args.dedupe_prior:
        prior = dedupe_prior_trades(prior)

    enriched = add_prior_context_risk(
        target,
        prior,
        min_prior_months=args.min_prior_months,
        recent_month_count=args.recent_month_count,
        support_scale=args.support_scale,
        pnl_scale=args.pnl_scale,
    )
    enriched = add_risk_bucket(enriched, parse_float_csv(args.risk_buckets))
    thresholds = parse_float_csv(args.risk_thresholds)

    run_dir = make_run_dir(args.output_dir, args.label)
    enriched.to_csv(run_dir / "enriched_prior_context_risk_trades.csv", index=False)

    bucket_summary = summarize_trade_groups(
        enriched,
        ["role", "candidate", "prior_context_risk_bucket"],
    )
    bucket_summary.to_csv(run_dir / "risk_bucket_summary.csv", index=False)

    role_candidate_summary = summarize_trade_groups(enriched, ["role", "candidate"])
    role_candidate_summary.to_csv(run_dir / "role_candidate_risk_summary.csv", index=False)

    month_summary = summarize_trade_groups(enriched, ["role", "candidate", "month"])
    month_summary.to_csv(run_dir / "month_risk_summary.csv", index=False)

    threshold_summary = summarize_thresholds(
        enriched,
        ["role", "candidate"],
        thresholds,
    )
    threshold_summary.to_csv(run_dir / "risk_threshold_summary.csv", index=False)

    overall_threshold_summary = summarize_thresholds(enriched, [], thresholds)
    overall_threshold_summary.to_csv(run_dir / "overall_risk_threshold_summary.csv", index=False)

    context_summary = summarize_trade_groups(
        enriched,
        ["direction", "combined_regime", "session_regime"],
    )
    context_summary.to_csv(run_dir / "context_risk_summary.csv", index=False)

    config = {
        "target_enriched_trades": args.target_enriched_trades,
        "prior_enriched_trades": prior_paths,
        "target_roles": args.target_roles,
        "prior_roles": args.prior_roles,
        "candidates": args.candidates,
        "dedupe_prior": args.dedupe_prior,
        "min_prior_months": args.min_prior_months,
        "recent_month_count": args.recent_month_count,
        "support_scale": args.support_scale,
        "pnl_scale": args.pnl_scale,
        "risk_thresholds": thresholds,
        "risk_buckets": parse_float_csv(args.risk_buckets),
        "target_trade_count": int(len(target)),
        "prior_trade_count": int(len(prior)),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Overall risk threshold summary:")
    print(overall_threshold_summary.to_string(index=False))
    print("\nTop risk bucket rows:")
    print(bucket_summary.head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-enriched-trades", type=Path, action="append", required=True)
    parser.add_argument("--prior-enriched-trades", type=Path, action="append", default=[])
    parser.add_argument("--target-roles", default="")
    parser.add_argument("--prior-roles", default="")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--dedupe-prior", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--min-prior-months", type=int, default=1)
    parser.add_argument("--recent-month-count", type=int, default=0)
    parser.add_argument("--support-scale", type=float, default=4.0)
    parser.add_argument("--pnl-scale", type=float, default=10.0)
    parser.add_argument("--risk-thresholds", default=DEFAULT_RISK_THRESHOLDS)
    parser.add_argument("--risk-buckets", default=DEFAULT_RISK_BUCKETS)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    parser.add_argument("--label", default="entry_ev_prior_context_risk_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
