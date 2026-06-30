#!/usr/bin/env python3
"""Diagnose executable EV calibration from selected entry-EV trades."""

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
DEFAULT_EXEC_EV_THRESHOLDS = "0,5,10"


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
        floats.append(float(part))
    if not floats:
        raise argparse.ArgumentTypeError("at least one numeric value is required")
    return floats


def read_trade_frames(paths: list[Path]) -> pd.DataFrame:
    frames = [pd.read_csv(path) for path in paths]
    if not frames:
        raise ValueError("at least one trade CSV is required")
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
        "pred_taken_ev",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name} trades missing columns: {', '.join(missing)}")
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
        "pred_taken_ev",
        "exit_regret",
        "exit_capture_ratio",
        "exit_capture_shortfall",
        "prior_exit_capture_risk_score",
    ]:
        normalized[column] = numeric_series(normalized, column)
    for column in [
        "same_side_oracle_edge",
        "same_side_missed_loss",
        "low_exit_capture",
        "large_exit_regret",
        "exit_capture_failure",
        "direction_error",
        "no_edge_entry",
    ]:
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


def add_capture_ratio_columns(
    frame: pd.DataFrame,
    *,
    min_oracle_edge: float,
    min_capture_factor: float,
    max_capture_factor: float,
) -> pd.DataFrame:
    output = frame.copy()
    oracle = output["actual_taken_best_adjusted_pnl"].astype(float)
    adjusted = output["adjusted_pnl"].astype(float)
    edge = oracle > min_oracle_edge
    raw_ratio = adjusted / oracle.replace(0.0, np.nan)
    output["calibration_same_side_oracle_edge"] = edge
    output["capture_ratio_raw"] = np.where(edge, raw_ratio, np.nan)
    output["capture_ratio_clipped"] = pd.Series(
        np.where(edge, raw_ratio, np.nan),
        index=output.index,
    ).clip(lower=min_capture_factor, upper=max_capture_factor)
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


def build_context_capture_stats(
    prior: pd.DataFrame,
    *,
    target_month: str,
    min_prior_months: int,
    recent_month_count: int,
) -> tuple[pd.DataFrame, dict[str, float]]:
    target_period = pd.Period(target_month, freq="M")
    prior_periods = pd.PeriodIndex(prior["month"].astype(str), freq="M")
    mask = prior_periods < target_period
    if recent_month_count > 0:
        mask &= prior_periods >= (target_period - recent_month_count)
    frame = prior[mask].copy()
    if frame.empty or int(frame["month"].nunique()) < min_prior_months:
        return pd.DataFrame(), {}

    capture_rows = frame[frame["calibration_same_side_oracle_edge"].astype(bool)].copy()
    global_stats = {
        "target_month": target_month,
        "prior_global_trade_count": float(len(frame)),
        "prior_global_capture_count": float(len(capture_rows)),
        "prior_global_month_count": float(frame["month"].nunique()),
        "prior_global_capture_factor": float(capture_rows["capture_ratio_clipped"].mean())
        if len(capture_rows)
        else np.nan,
        "prior_global_adjusted_pnl_mean": float(frame["adjusted_pnl"].astype(float).mean()),
    }
    if capture_rows.empty:
        return pd.DataFrame(), global_stats

    grouped = (
        capture_rows.groupby(CONTEXT_COLUMNS, dropna=False)
        .agg(
            prior_context_capture_count=("capture_ratio_clipped", "size"),
            prior_context_month_count=("month", "nunique"),
            prior_context_capture_factor=("capture_ratio_clipped", "mean"),
            prior_context_capture_factor_median=("capture_ratio_clipped", "median"),
            prior_context_adjusted_pnl_mean=("adjusted_pnl", "mean"),
            prior_context_total_adjusted_pnl=("adjusted_pnl", "sum"),
            prior_context_exit_capture_failure_rate=("exit_capture_failure", "mean"),
            prior_context_same_side_missed_loss_rate=("same_side_missed_loss", "mean"),
            prior_context_large_exit_regret_rate=("large_exit_regret", "mean"),
        )
        .reset_index()
    )
    grouped["target_month"] = target_month
    return grouped, global_stats


def build_all_capture_stats(
    prior: pd.DataFrame,
    target_months: list[str],
    *,
    min_prior_months: int,
    recent_month_count: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    context_frames: list[pd.DataFrame] = []
    global_rows: list[dict[str, float]] = []
    for month in target_months:
        context_stats, global_stats = build_context_capture_stats(
            prior,
            target_month=month,
            min_prior_months=min_prior_months,
            recent_month_count=recent_month_count,
        )
        if not context_stats.empty:
            context_frames.append(context_stats)
        if global_stats:
            global_rows.append(global_stats)
    context = pd.concat(context_frames, ignore_index=True) if context_frames else pd.DataFrame()
    global_frame = pd.DataFrame(global_rows)
    return context, global_frame


def add_executable_ev_calibration(
    target: pd.DataFrame,
    prior: pd.DataFrame,
    *,
    min_prior_months: int,
    recent_month_count: int,
    support_scale: float,
    default_capture_factor: float,
    min_capture_factor: float,
    max_capture_factor: float,
) -> pd.DataFrame:
    target = target.copy()
    target_months = sorted(target["month"].astype(str).unique().tolist())
    context_stats, global_stats = build_all_capture_stats(
        prior,
        target_months,
        min_prior_months=min_prior_months,
        recent_month_count=recent_month_count,
    )
    enriched = target
    if not global_stats.empty:
        enriched = enriched.merge(
            global_stats,
            how="left",
            left_on="month",
            right_on="target_month",
        )
    if not context_stats.empty:
        enriched = enriched.merge(
            context_stats,
            how="left",
            left_on=["month", *CONTEXT_COLUMNS],
            right_on=["target_month", *CONTEXT_COLUMNS],
            suffixes=("", "_context"),
        )
    numeric_defaults = {
        "prior_global_trade_count": 0.0,
        "prior_global_capture_count": 0.0,
        "prior_global_month_count": 0.0,
        "prior_global_capture_factor": np.nan,
        "prior_global_adjusted_pnl_mean": 0.0,
        "prior_context_capture_count": 0.0,
        "prior_context_month_count": 0.0,
        "prior_context_capture_factor": np.nan,
        "prior_context_capture_factor_median": np.nan,
        "prior_context_adjusted_pnl_mean": 0.0,
        "prior_context_total_adjusted_pnl": 0.0,
        "prior_context_exit_capture_failure_rate": 0.0,
        "prior_context_same_side_missed_loss_rate": 0.0,
        "prior_context_large_exit_regret_rate": 0.0,
    }
    for column, default in numeric_defaults.items():
        if column not in enriched.columns:
            enriched[column] = default
        enriched[column] = pd.to_numeric(enriched[column], errors="coerce")
        if not np.isnan(default):
            enriched[column] = enriched[column].fillna(default)

    global_factor = enriched["prior_global_capture_factor"].fillna(default_capture_factor)
    global_factor = global_factor.clip(lower=min_capture_factor, upper=max_capture_factor)
    context_factor = enriched["prior_context_capture_factor"].fillna(global_factor)
    context_factor = context_factor.clip(lower=min_capture_factor, upper=max_capture_factor)
    support_weight = np.clip(enriched["prior_context_capture_count"] / support_scale, 0.0, 1.0)
    capture_factor = ((1.0 - support_weight) * global_factor) + (support_weight * context_factor)
    capture_factor = capture_factor.clip(lower=min_capture_factor, upper=max_capture_factor)

    enriched["prior_capture_support_weight"] = support_weight
    enriched["global_executable_capture_factor"] = global_factor
    enriched["context_executable_capture_factor"] = context_factor
    enriched["executable_capture_factor"] = capture_factor
    enriched["pred_raw_executable_ev"] = enriched["pred_taken_ev"].astype(float)
    enriched["pred_capture_calibrated_ev"] = (
        enriched["pred_taken_ev"].astype(float) * enriched["executable_capture_factor"]
    )
    enriched["raw_ev_error_vs_realized"] = (
        enriched["pred_raw_executable_ev"] - enriched["adjusted_pnl"].astype(float)
    )
    enriched["capture_calibrated_ev_error_vs_realized"] = (
        enriched["pred_capture_calibrated_ev"] - enriched["adjusted_pnl"].astype(float)
    )
    enriched["raw_ev_abs_error"] = enriched["raw_ev_error_vs_realized"].abs()
    enriched["capture_calibrated_ev_abs_error"] = enriched[
        "capture_calibrated_ev_error_vs_realized"
    ].abs()
    enriched["raw_ev_squared_error"] = enriched["raw_ev_error_vs_realized"] ** 2
    enriched["capture_calibrated_ev_squared_error"] = (
        enriched["capture_calibrated_ev_error_vs_realized"] ** 2
    )
    return enriched


def safe_corr(frame: pd.DataFrame, x: str, y: str, *, method: str) -> float:
    if len(frame) < 2:
        return 0.0
    series_x = pd.to_numeric(frame[x], errors="coerce")
    series_y = pd.to_numeric(frame[y], errors="coerce")
    valid = series_x.notna() & series_y.notna()
    if int(valid.sum()) < 2:
        return 0.0
    value = series_x[valid].corr(series_y[valid], method=method)
    if pd.isna(value):
        return 0.0
    return float(value)


def summarize_calibration_groups(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_columns)
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(group_columns, dropna=False, observed=True):
        if not isinstance(key, tuple):
            key = (key,)
        row = dict(zip(group_columns, key))
        row.update(
            {
                "trade_count": int(len(group)),
                "total_adjusted_pnl": float(group["adjusted_pnl"].astype(float).sum()),
                "avg_adjusted_pnl": float(group["adjusted_pnl"].astype(float).mean()),
                "raw_ev_mean": float(group["pred_raw_executable_ev"].astype(float).mean()),
                "capture_calibrated_ev_mean": float(
                    group["pred_capture_calibrated_ev"].astype(float).mean()
                ),
                "raw_ev_bias": float(group["raw_ev_error_vs_realized"].mean()),
                "capture_calibrated_ev_bias": float(
                    group["capture_calibrated_ev_error_vs_realized"].mean()
                ),
                "raw_ev_mae": float(group["raw_ev_abs_error"].mean()),
                "capture_calibrated_ev_mae": float(
                    group["capture_calibrated_ev_abs_error"].mean()
                ),
                "raw_ev_rmse": float(np.sqrt(group["raw_ev_squared_error"].mean())),
                "capture_calibrated_ev_rmse": float(
                    np.sqrt(group["capture_calibrated_ev_squared_error"].mean())
                ),
                "raw_ev_spearman": safe_corr(
                    group,
                    "pred_raw_executable_ev",
                    "adjusted_pnl",
                    method="spearman",
                ),
                "capture_calibrated_ev_spearman": safe_corr(
                    group,
                    "pred_capture_calibrated_ev",
                    "adjusted_pnl",
                    method="spearman",
                ),
                "capture_factor_mean": float(group["executable_capture_factor"].mean()),
                "context_support_mean": float(group["prior_capture_support_weight"].mean()),
                "same_side_missed_loss_rate": float(
                    group["same_side_missed_loss"].fillna(False).astype(bool).mean()
                ),
                "exit_capture_failure_rate": float(
                    group["exit_capture_failure"].fillna(False).astype(bool).mean()
                ),
            }
        )
        row["mae_delta_raw_minus_calibrated"] = (
            row["raw_ev_mae"] - row["capture_calibrated_ev_mae"]
        )
        row["rmse_delta_raw_minus_calibrated"] = (
            row["raw_ev_rmse"] - row["capture_calibrated_ev_rmse"]
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["mae_delta_raw_minus_calibrated", "total_adjusted_pnl"],
        ascending=[False, True],
    )


def summarize_thresholds(
    frame: pd.DataFrame,
    group_columns: list[str],
    thresholds: list[float],
    *,
    score_column: str,
    score_label: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped = [((), frame)] if not group_columns else frame.groupby(group_columns, dropna=False)
    for key, group in grouped:
        if group_columns and not isinstance(key, tuple):
            key = (key,)
        prefix = dict(zip(group_columns, key)) if group_columns else {}
        total_pnl = float(group["adjusted_pnl"].astype(float).sum())
        total_count = int(len(group))
        total_failure_count = int(group["exit_capture_failure"].fillna(False).astype(bool).sum())
        for threshold in thresholds:
            flagged = group[group[score_column].astype(float) < threshold]
            flagged_pnl = float(flagged["adjusted_pnl"].astype(float).sum())
            flagged_count = int(len(flagged))
            flagged_failure_count = int(
                flagged["exit_capture_failure"].fillna(False).astype(bool).sum()
            )
            rows.append(
                {
                    **prefix,
                    "score": score_label,
                    "threshold": float(threshold),
                    "rule": f"{score_label}_lt_{threshold:g}",
                    "total_trade_count": total_count,
                    "total_adjusted_pnl": total_pnl,
                    "total_exit_capture_failure_count": total_failure_count,
                    "flagged_trade_count": flagged_count,
                    "flagged_adjusted_pnl": flagged_pnl,
                    "kept_adjusted_pnl_if_removed": float(total_pnl - flagged_pnl),
                    "block_delta_if_removed": float(-flagged_pnl),
                    "flagged_trade_share": (
                        float(flagged_count / total_count) if total_count else 0.0
                    ),
                    "flagged_exit_capture_failure_count": flagged_failure_count,
                    "flagged_failure_precision": (
                        float(flagged_failure_count / flagged_count) if flagged_count else 0.0
                    ),
                    "failure_recall": (
                        float(flagged_failure_count / total_failure_count)
                        if total_failure_count
                        else 0.0
                    ),
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["block_delta_if_removed", "flagged_exit_capture_failure_count"],
        ascending=[False, False],
    )


def build_diagnostics(args: argparse.Namespace) -> Path:
    target = normalize_trade_frame(read_trade_frames(args.target_trades), name="target")
    prior_paths = args.prior_trades or args.target_trades
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
    target = add_capture_ratio_columns(
        target,
        min_oracle_edge=args.min_oracle_edge,
        min_capture_factor=args.min_capture_factor,
        max_capture_factor=args.max_capture_factor,
    )
    prior = add_capture_ratio_columns(
        prior,
        min_oracle_edge=args.min_oracle_edge,
        min_capture_factor=args.min_capture_factor,
        max_capture_factor=args.max_capture_factor,
    )
    if args.dedupe_prior:
        prior = dedupe_prior_trades(prior)

    enriched = add_executable_ev_calibration(
        target,
        prior,
        min_prior_months=args.min_prior_months,
        recent_month_count=args.recent_month_count,
        support_scale=args.support_scale,
        default_capture_factor=args.default_capture_factor,
        min_capture_factor=args.min_capture_factor,
        max_capture_factor=args.max_capture_factor,
    )
    thresholds = parse_float_csv(args.executable_ev_thresholds)

    run_dir = make_run_dir(args.output_dir, args.label)
    enriched.to_csv(run_dir / "enriched_executable_ev_calibration.csv", index=False)

    role_candidate = summarize_calibration_groups(enriched, ["role", "candidate"])
    role_candidate.to_csv(run_dir / "role_candidate_executable_ev_summary.csv", index=False)

    role_month = summarize_calibration_groups(enriched, ["role", "candidate", "month"])
    role_month.to_csv(run_dir / "role_month_executable_ev_summary.csv", index=False)

    context = summarize_calibration_groups(
        enriched,
        ["role", "candidate", "direction", "combined_regime", "session_regime"],
    )
    context.to_csv(run_dir / "context_executable_ev_summary.csv", index=False)
    context.head(args.top_n).to_csv(run_dir / "top_calibration_improvement_contexts.csv", index=False)

    threshold_frames = []
    for score_column, score_label in [
        ("pred_raw_executable_ev", "raw_ev"),
        ("pred_capture_calibrated_ev", "capture_calibrated_ev"),
    ]:
        threshold_frames.append(
            summarize_thresholds(
                enriched,
                ["role", "candidate"],
                thresholds,
                score_column=score_column,
                score_label=score_label,
            )
        )
    threshold_summary = pd.concat(threshold_frames, ignore_index=True)
    threshold_summary.to_csv(run_dir / "score_threshold_summary.csv", index=False)

    overall_threshold_frames = []
    for score_column, score_label in [
        ("pred_raw_executable_ev", "raw_ev"),
        ("pred_capture_calibrated_ev", "capture_calibrated_ev"),
    ]:
        overall_threshold_frames.append(
            summarize_thresholds(
                enriched,
                [],
                thresholds,
                score_column=score_column,
                score_label=score_label,
            )
        )
    overall_threshold_summary = pd.concat(overall_threshold_frames, ignore_index=True)
    overall_threshold_summary.to_csv(run_dir / "overall_score_threshold_summary.csv", index=False)

    config = {
        "target_trades": args.target_trades,
        "prior_trades": prior_paths,
        "target_roles": args.target_roles,
        "prior_roles": args.prior_roles,
        "candidates": args.candidates,
        "months": args.months,
        "dedupe_prior": args.dedupe_prior,
        "min_oracle_edge": args.min_oracle_edge,
        "min_prior_months": args.min_prior_months,
        "recent_month_count": args.recent_month_count,
        "support_scale": args.support_scale,
        "default_capture_factor": args.default_capture_factor,
        "min_capture_factor": args.min_capture_factor,
        "max_capture_factor": args.max_capture_factor,
        "executable_ev_thresholds": thresholds,
        "target_trade_count": int(len(target)),
        "prior_trade_count": int(len(prior)),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Role/candidate executable EV calibration:")
    print(
        role_candidate[
            [
                "role",
                "candidate",
                "trade_count",
                "total_adjusted_pnl",
                "raw_ev_mae",
                "capture_calibrated_ev_mae",
                "mae_delta_raw_minus_calibrated",
                "raw_ev_bias",
                "capture_calibrated_ev_bias",
                "capture_factor_mean",
            ]
        ].to_string(index=False)
    )
    print("\nOverall threshold summary:")
    print(
        overall_threshold_summary[
            [
                "score",
                "threshold",
                "flagged_trade_count",
                "flagged_adjusted_pnl",
                "block_delta_if_removed",
                "flagged_failure_precision",
                "failure_recall",
            ]
        ].to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-trades", type=Path, action="append", required=True)
    parser.add_argument("--prior-trades", type=Path, action="append", default=[])
    parser.add_argument("--target-roles", default="")
    parser.add_argument("--prior-roles", default="")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--months", default="")
    parser.add_argument("--dedupe-prior", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--min-oracle-edge", type=float, default=0.0)
    parser.add_argument("--min-prior-months", type=int, default=1)
    parser.add_argument("--recent-month-count", type=int, default=0)
    parser.add_argument("--support-scale", type=float, default=4.0)
    parser.add_argument("--default-capture-factor", type=float, default=1.0)
    parser.add_argument("--min-capture-factor", type=float, default=-1.0)
    parser.add_argument("--max-capture-factor", type=float, default=1.0)
    parser.add_argument("--executable-ev-thresholds", default=DEFAULT_EXEC_EV_THRESHOLDS)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    parser.add_argument("--label", default="entry_ev_executable_ev_calibration_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
