#!/usr/bin/env python3
"""Evaluate direction-inversion risk as a selector/ranking feature."""

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

from trade_data.backtest import (  # noqa: E402
    enrich_trades_with_predictions,
    json_default,
    make_run_dir,
    prepare_analysis_predictions,
    read_trades_csv,
)


DEFAULT_EXTRA_COLUMNS = [
    "combined_regime",
    "session_regime",
    "pred_direction_inversion_long_predicted_direction_inversion_risk",
    "pred_direction_inversion_short_predicted_direction_inversion_risk",
    "pred_direction_inversion_long_direction_inversion_prediction_support",
    "pred_direction_inversion_short_direction_inversion_prediction_support",
    "pred_direction_inversion_long_direction_inversion_prediction_source",
    "pred_direction_inversion_short_direction_inversion_prediction_source",
    "pred_direction_inversion_long_selected_risk_bucket",
    "pred_direction_inversion_short_selected_risk_bucket",
    "pred_direction_inversion_long_selected_side_support_bucket",
    "pred_direction_inversion_short_selected_side_support_bucket",
    "pred_direction_inversion_long_selected_side_pressure_bucket",
    "pred_direction_inversion_short_selected_side_pressure_bucket",
    "pred_direction_inversion_bucket_s0p1_long_best_adjusted_pnl",
    "pred_direction_inversion_bucket_s0p1_short_best_adjusted_pnl",
    "pred_side_prior_pressure_s0p5_long_best_adjusted_pnl",
    "pred_side_prior_pressure_s0p5_short_best_adjusted_pnl",
]


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


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_policy_runs(values: list[str]) -> dict[str, Path]:
    runs: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError("policy runs must use name=path")
        name, path = value.split("=", 1)
        name = name.strip()
        if not name:
            raise argparse.ArgumentTypeError("policy run name must not be empty")
        runs[name] = Path(path.strip())
    if not runs:
        raise argparse.ArgumentTypeError("at least one policy run is required")
    return runs


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values), default).fillna(default).astype(float)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    values = frame[column]
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(values):
        return values.fillna(float(default)).astype(float).ne(0.0)
    normalized = values.astype(str).str.lower().str.strip()
    return normalized.isin({"true", "1", "yes", "y"})


def selected_side_value(
    frame: pd.DataFrame,
    *,
    long_column: str,
    short_column: str,
    default: float = 0.0,
) -> pd.Series:
    direction = frame["direction"].astype(str).str.lower()
    long_values = numeric_series(frame, long_column, default=default)
    short_values = numeric_series(frame, short_column, default=default)
    return pd.Series(np.where(direction.eq("long"), long_values, short_values), index=frame.index)


def selected_side_text(
    frame: pd.DataFrame,
    *,
    long_column: str,
    short_column: str,
    default: str = "missing",
) -> pd.Series:
    direction = frame["direction"].astype(str).str.lower()
    long_values = (
        frame[long_column].fillna(default).astype(str)
        if long_column in frame.columns
        else pd.Series(default, index=frame.index)
    )
    short_values = (
        frame[short_column].fillna(default).astype(str)
        if short_column in frame.columns
        else pd.Series(default, index=frame.index)
    )
    return pd.Series(np.where(direction.eq("long"), long_values, short_values), index=frame.index)


def read_monthly_metrics(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "monthly_policy_metrics.csv"
    frame = pd.read_csv(path)
    required = {"family", "role", "month", "candidate"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    return frame


def trade_path(run_dir: Path, row: pd.Series) -> Path:
    return run_dir / "trades" / str(row["family"]) / str(row["candidate"]) / f"{row['month']}.csv"


def read_policy_run_trades(
    *,
    run_name: str,
    run_dir: Path,
    predictions: pd.DataFrame,
    long_column: str,
    short_column: str,
    extra_prediction_columns: list[str],
) -> pd.DataFrame:
    analysis_predictions = prepare_analysis_predictions(
        predictions,
        long_column,
        short_column,
        extra_prediction_columns,
    )
    monthly = read_monthly_metrics(run_dir)
    frames: list[pd.DataFrame] = []
    missing_paths: list[Path] = []
    for _, row in monthly.iterrows():
        path = trade_path(run_dir, row)
        if not path.exists():
            missing_paths.append(path)
            continue
        trades = read_trades_csv(path)
        if trades.empty:
            continue
        enriched = enrich_trades_with_predictions(
            trades,
            analysis_predictions,
            extra_prediction_columns,
        )
        enriched.insert(0, "run_name", run_name)
        enriched.insert(1, "family", str(row["family"]))
        enriched.insert(2, "role", str(row["role"]))
        enriched.insert(3, "month", str(row["month"]))
        enriched.insert(4, "candidate", str(row["candidate"]))
        frames.append(enriched)
    if missing_paths:
        preview = ", ".join(str(path) for path in missing_paths[:5])
        suffix = "" if len(missing_paths) <= 5 else f" ... ({len(missing_paths)} missing)"
        raise FileNotFoundError(f"missing trade files: {preview}{suffix}")
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def add_selected_direction_features(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["selected_direction_inversion_risk"] = selected_side_value(
        output,
        long_column="pred_direction_inversion_long_predicted_direction_inversion_risk",
        short_column="pred_direction_inversion_short_predicted_direction_inversion_risk",
        default=np.nan,
    )
    output["selected_direction_inversion_support"] = selected_side_value(
        output,
        long_column="pred_direction_inversion_long_direction_inversion_prediction_support",
        short_column="pred_direction_inversion_short_direction_inversion_prediction_support",
    )
    output["selected_direction_inversion_source"] = selected_side_text(
        output,
        long_column="pred_direction_inversion_long_direction_inversion_prediction_source",
        short_column="pred_direction_inversion_short_direction_inversion_prediction_source",
    )
    output["selected_direction_inversion_risk_bucket"] = selected_side_text(
        output,
        long_column="pred_direction_inversion_long_selected_risk_bucket",
        short_column="pred_direction_inversion_short_selected_risk_bucket",
    )
    output["selected_direction_inversion_support_bucket"] = selected_side_text(
        output,
        long_column="pred_direction_inversion_long_selected_side_support_bucket",
        short_column="pred_direction_inversion_short_selected_side_support_bucket",
    )
    output["selected_direction_inversion_pressure_bucket"] = selected_side_text(
        output,
        long_column="pred_direction_inversion_long_selected_side_pressure_bucket",
        short_column="pred_direction_inversion_short_selected_side_pressure_bucket",
    )
    output["selected_direction_inversion_s0p1_score"] = selected_side_value(
        output,
        long_column="pred_direction_inversion_bucket_s0p1_long_best_adjusted_pnl",
        short_column="pred_direction_inversion_bucket_s0p1_short_best_adjusted_pnl",
        default=np.nan,
    )
    output["selected_side_prior_s0p5_score"] = selected_side_value(
        output,
        long_column="pred_side_prior_pressure_s0p5_long_best_adjusted_pnl",
        short_column="pred_side_prior_pressure_s0p5_short_best_adjusted_pnl",
        default=np.nan,
    )
    output["selected_direction_score_delta"] = (
        output["selected_direction_inversion_s0p1_score"] - output["selected_side_prior_s0p5_score"]
    )
    return output


def cumulative_max_drawdown(values: pd.Series) -> float:
    cumulative = values.astype(float).cumsum()
    if cumulative.empty:
        return 0.0
    return float((cumulative.cummax() - cumulative).max())


def weighted_average(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & np.isfinite(values.astype(float)) & weights.astype(float).gt(0.0)
    if not bool(valid.any()):
        return float("nan")
    return float(np.average(values.astype(float)[valid], weights=weights.astype(float)[valid]))


def summarize_slice(frame: pd.DataFrame, *, risk_threshold: float) -> dict[str, Any]:
    if frame.empty:
        return {"trade_count": 0, "total_pnl": 0.0, "max_drawdown": 0.0}
    ordered = frame.sort_values("entry_decision_timestamp")
    pnl = numeric_series(ordered, "adjusted_pnl")
    direction = ordered["direction"].astype(str).str.lower()
    risk = numeric_series(ordered, "selected_direction_inversion_risk", default=np.nan)
    source = ordered["selected_direction_inversion_source"].astype(str)
    bucket = source.eq("bucket")
    global_fallback = source.eq("global")
    no_prior = source.eq("no_prior")
    high_bucket = bucket & risk.ge(risk_threshold)
    high_global = global_fallback & risk.ge(risk_threshold)
    direction_error = bool_series(ordered, "direction_error")
    trade_count = int(len(ordered))
    long_count = int(direction.eq("long").sum())
    short_count = int(direction.eq("short").sum())
    return {
        "trade_count": trade_count,
        "total_pnl": float(pnl.sum()),
        "avg_pnl": float(pnl.mean()),
        "win_rate": float(pnl.gt(0.0).mean()),
        "max_drawdown": cumulative_max_drawdown(pnl),
        "long_trade_count": long_count,
        "short_trade_count": short_count,
        "max_side_trade_share": float(max(long_count, short_count) / trade_count)
        if trade_count
        else 0.0,
        "direction_error_rate": float(direction_error.mean()),
        "direction_error_pnl": float(pnl.where(direction_error, 0.0).sum()),
        "bucket_prediction_share": float(bucket.mean()),
        "global_prediction_share": float(global_fallback.mean()),
        "no_prior_share": float(no_prior.mean()),
        "direction_risk_mean": float(risk.dropna().mean()) if risk.notna().any() else float("nan"),
        "bucket_direction_risk_mean": float(risk[bucket].dropna().mean())
        if bool(bucket.any())
        else float("nan"),
        "bucket_high_risk_share": float(high_bucket.mean()),
        "bucket_high_risk_pnl": float(pnl.where(high_bucket, 0.0).sum()),
        "bucket_high_direction_error_rate": float(direction_error[high_bucket].mean())
        if bool(high_bucket.any())
        else float("nan"),
        "global_high_risk_share": float(high_global.mean()),
        "global_high_risk_pnl": float(pnl.where(high_global, 0.0).sum()),
        "mean_prediction_support": float(
            numeric_series(ordered, "selected_direction_inversion_support").mean()
        ),
        "selected_direction_score_delta_mean": float(
            numeric_series(ordered, "selected_direction_score_delta", default=np.nan).dropna().mean()
        )
        if numeric_series(ordered, "selected_direction_score_delta", default=np.nan)
        .notna()
        .any()
        else float("nan"),
    }


def summarize_by(frame: pd.DataFrame, columns: list[str], *, risk_threshold: float) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in frame.groupby(columns, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(columns, keys, strict=True))
        row.update(summarize_slice(group, risk_threshold=risk_threshold))
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        [*columns, "total_pnl"],
        ascending=[True] * len(columns) + [True],
    ).reset_index(drop=True)


def candidate_summary(role_month: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (run_name, candidate), group in role_month.groupby(["run_name", "candidate"], dropna=False):
        role_totals = group.groupby("role")["total_pnl"].sum()
        role_trades = group.groupby("role")["trade_count"].sum()
        weights = group["trade_count"].astype(float)
        trade_count = int(group["trade_count"].sum())
        long_count = int(group["long_trade_count"].sum())
        short_count = int(group["short_trade_count"].sum())
        rows.append(
            {
                "run_name": run_name,
                "candidate": candidate,
                "role_count": int(group["role"].nunique()),
                "month_count": int(group["month"].nunique()),
                "active_role_count": int((role_trades > 0).sum()),
                "positive_role_count": int((role_totals > 0).sum()),
                "active_months": int(group["trade_count"].gt(0).sum()),
                "total_pnl": float(group["total_pnl"].sum()),
                "min_role_total_pnl": float(role_totals.min()) if len(role_totals) else 0.0,
                "min_month_pnl": float(group["total_pnl"].min()) if len(group) else 0.0,
                "trade_count": trade_count,
                "min_role_trades": int(role_trades.min()) if len(role_trades) else 0,
                "min_month_trades": int(group["trade_count"].min()) if len(group) else 0,
                "max_drawdown": float(group["max_drawdown"].max()) if len(group) else 0.0,
                "long_trade_count": long_count,
                "short_trade_count": short_count,
                "max_side_trade_share": float(max(long_count, short_count) / trade_count)
                if trade_count
                else 0.0,
                "direction_error_rate": weighted_average(group["direction_error_rate"], weights),
                "direction_error_pnl": float(group["direction_error_pnl"].sum()),
                "bucket_prediction_share": weighted_average(group["bucket_prediction_share"], weights),
                "global_prediction_share": weighted_average(group["global_prediction_share"], weights),
                "no_prior_share": weighted_average(group["no_prior_share"], weights),
                "direction_risk_mean": weighted_average(group["direction_risk_mean"], weights),
                "bucket_direction_risk_mean": weighted_average(
                    group["bucket_direction_risk_mean"],
                    weights,
                ),
                "bucket_high_risk_share": weighted_average(group["bucket_high_risk_share"], weights),
                "bucket_high_risk_pnl": float(group["bucket_high_risk_pnl"].sum()),
                "bucket_high_direction_error_rate": weighted_average(
                    group["bucket_high_direction_error_rate"],
                    weights,
                ),
                "global_high_risk_share": weighted_average(group["global_high_risk_share"], weights),
                "global_high_risk_pnl": float(group["global_high_risk_pnl"].sum()),
                "mean_prediction_support": weighted_average(group["mean_prediction_support"], weights),
                "selected_direction_score_delta_mean": weighted_average(
                    group["selected_direction_score_delta_mean"],
                    weights,
                ),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["min_role_total_pnl", "total_pnl", "bucket_high_risk_share"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def candidate_blockers(
    row: pd.Series,
    *,
    min_total_pnl: float,
    min_role_total_pnl: float,
    min_month_pnl: float,
    min_trades: int,
    max_drawdown: float,
    max_bucket_high_risk_share: float,
    max_global_prediction_share: float,
    min_bucket_prediction_share: float,
) -> list[str]:
    checks = [
        ("total_pnl_below_floor", row["total_pnl"] >= min_total_pnl),
        ("role_total_pnl_below_floor", row["min_role_total_pnl"] >= min_role_total_pnl),
        ("month_pnl_below_floor", row["min_month_pnl"] >= min_month_pnl),
        ("trades_low", row["trade_count"] >= min_trades),
        ("drawdown_high", row["max_drawdown"] <= max_drawdown),
        ("bucket_high_risk_share_high", row["bucket_high_risk_share"] <= max_bucket_high_risk_share),
        ("global_prediction_share_high", row["global_prediction_share"] <= max_global_prediction_share),
        ("bucket_prediction_share_low", row["bucket_prediction_share"] >= min_bucket_prediction_share),
    ]
    return [label for label, ok in checks if not bool(ok)]


def apply_selector_gates(
    summary: pd.DataFrame,
    *,
    min_total_pnl: float,
    min_role_total_pnl: float,
    min_month_pnl: float,
    min_trades: int,
    max_drawdown: float,
    max_bucket_high_risk_share: float,
    max_global_prediction_share: float,
    min_bucket_prediction_share: float,
) -> pd.DataFrame:
    result = summary.copy()
    blockers: list[str] = []
    eligible: list[bool] = []
    for _, row in result.iterrows():
        row_blockers = candidate_blockers(
            row,
            min_total_pnl=min_total_pnl,
            min_role_total_pnl=min_role_total_pnl,
            min_month_pnl=min_month_pnl,
            min_trades=min_trades,
            max_drawdown=max_drawdown,
            max_bucket_high_risk_share=max_bucket_high_risk_share,
            max_global_prediction_share=max_global_prediction_share,
            min_bucket_prediction_share=min_bucket_prediction_share,
        )
        blockers.append(";".join(row_blockers))
        eligible.append(not row_blockers)
    result["eligible"] = eligible
    result["blockers"] = blockers
    return result.sort_values(
        [
            "eligible",
            "min_role_total_pnl",
            "total_pnl",
            "bucket_high_risk_share",
            "global_prediction_share",
        ],
        ascending=[False, False, False, True, True],
    ).reset_index(drop=True)


def pointwise_screen_effects(frame: pd.DataFrame, *, risk_threshold: float) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (run_name, candidate), group in frame.groupby(["run_name", "candidate"], dropna=False):
        pnl = numeric_series(group, "adjusted_pnl")
        source = group["selected_direction_inversion_source"].astype(str)
        risk = numeric_series(group, "selected_direction_inversion_risk", default=np.nan)
        bucket_high = source.eq("bucket") & risk.ge(risk_threshold)
        global_high = source.eq("global") & risk.ge(risk_threshold)
        for mode, remove_mask in [
            ("bucket_high", bucket_high),
            ("global_high", global_high),
            ("bucket_or_global_high", bucket_high | global_high),
        ]:
            kept = group[~remove_mask]
            removed = group[remove_mask]
            kept_role = kept.groupby("role")["adjusted_pnl"].sum()
            kept_month = kept.groupby("month")["adjusted_pnl"].sum()
            rows.append(
                {
                    "run_name": run_name,
                    "candidate": candidate,
                    "screen_mode": mode,
                    "original_trades": int(len(group)),
                    "original_total_pnl": float(pnl.sum()),
                    "removed_trades": int(len(removed)),
                    "removed_pnl": float(removed["adjusted_pnl"].astype(float).sum())
                    if len(removed)
                    else 0.0,
                    "kept_trades": int(len(kept)),
                    "kept_total_pnl": float(kept["adjusted_pnl"].astype(float).sum())
                    if len(kept)
                    else 0.0,
                    "kept_min_role_pnl": float(kept_role.min()) if len(kept_role) else 0.0,
                    "kept_min_month_pnl": float(kept_month.min()) if len(kept_month) else 0.0,
                }
            )
    return pd.DataFrame(rows)


def blocker_summary(gated: pd.DataFrame) -> pd.DataFrame:
    counts: dict[str, int] = {}
    for blockers in gated["blockers"].fillna("").astype(str):
        for blocker in [part for part in blockers.split(";") if part]:
            counts[blocker] = counts.get(blocker, 0) + 1
    return pd.DataFrame(
        [{"blocker": blocker, "candidate_count": count} for blocker, count in counts.items()]
    ).sort_values(["candidate_count", "blocker"], ascending=[False, True])


def build_diagnostics(args: argparse.Namespace) -> Path:
    policy_runs = parse_policy_runs(args.policy_run)
    predictions = pd.read_parquet(args.predictions)
    extra_columns = list(dict.fromkeys([*DEFAULT_EXTRA_COLUMNS, *parse_csv(args.extra_columns)]))
    frames = []
    for run_name, run_dir in policy_runs.items():
        trades = read_policy_run_trades(
            run_name=run_name,
            run_dir=run_dir,
            predictions=predictions,
            long_column=args.long_column,
            short_column=args.short_column,
            extra_prediction_columns=extra_columns,
        )
        frames.append(trades)
    combined = add_selected_direction_features(pd.concat(frames, ignore_index=True))
    role_month = summarize_by(
        combined,
        ["run_name", "candidate", "role", "month"],
        risk_threshold=args.risk_threshold,
    )
    summary = candidate_summary(role_month)
    gated = apply_selector_gates(
        summary,
        min_total_pnl=args.min_total_pnl,
        min_role_total_pnl=args.min_role_total_pnl,
        min_month_pnl=args.min_month_pnl,
        min_trades=args.min_trades,
        max_drawdown=args.max_drawdown,
        max_bucket_high_risk_share=args.max_bucket_high_risk_share,
        max_global_prediction_share=args.max_global_prediction_share,
        min_bucket_prediction_share=args.min_bucket_prediction_share,
    )
    context = summarize_by(
        combined,
        ["run_name", "candidate", "direction", "combined_regime", "session_regime"],
        risk_threshold=args.risk_threshold,
    )
    pointwise = pointwise_screen_effects(combined, risk_threshold=args.risk_threshold)
    run_dir = make_run_dir(args.output_dir, args.label)
    combined.to_csv(run_dir / "direction_inversion_enriched_trades.csv", index=False)
    role_month.to_csv(run_dir / "role_month_direction_inversion_summary.csv", index=False)
    summary.to_csv(run_dir / "candidate_direction_inversion_summary.csv", index=False)
    gated.to_csv(run_dir / "candidate_direction_inversion_selection.csv", index=False)
    blocker_summary(gated).to_csv(run_dir / "blocker_summary.csv", index=False)
    context.to_csv(run_dir / "context_direction_inversion_summary.csv", index=False)
    pointwise.to_csv(run_dir / "pointwise_direction_inversion_screen_effects.csv", index=False)
    config = {
        "policy_runs": policy_runs,
        "predictions": args.predictions,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "risk_threshold": args.risk_threshold,
        "min_total_pnl": args.min_total_pnl,
        "min_role_total_pnl": args.min_role_total_pnl,
        "min_month_pnl": args.min_month_pnl,
        "min_trades": args.min_trades,
        "max_drawdown": args.max_drawdown,
        "max_bucket_high_risk_share": args.max_bucket_high_risk_share,
        "max_global_prediction_share": args.max_global_prediction_share,
        "min_bucket_prediction_share": args.min_bucket_prediction_share,
        "extra_columns": extra_columns,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    print("Candidate direction inversion summary:")
    print(summary.to_string(index=False))
    print("\nSelection:")
    print(gated.to_string(index=False))
    print("\nPointwise screen effects:")
    print(pointwise.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-run", action="append", required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument(
        "--long-column",
        default="pred_direction_inversion_bucket_s0p1_long_best_adjusted_pnl",
    )
    parser.add_argument(
        "--short-column",
        default="pred_direction_inversion_bucket_s0p1_short_best_adjusted_pnl",
    )
    parser.add_argument("--extra-columns", default="")
    parser.add_argument("--risk-threshold", type=float, default=0.60)
    parser.add_argument("--min-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-role-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-month-pnl", type=float, default=0.0)
    parser.add_argument("--min-trades", type=int, default=10)
    parser.add_argument("--max-drawdown", type=float, default=float("inf"))
    parser.add_argument("--max-bucket-high-risk-share", type=float, default=1.0)
    parser.add_argument("--max-global-prediction-share", type=float, default=1.0)
    parser.add_argument("--min-bucket-prediction-share", type=float, default=0.0)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_direction_inversion_selector_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
