#!/usr/bin/env python3
"""Diagnose side-balance drift as a selected-trade feature, not a direct score."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

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


DEFAULT_SIDE_BALANCE_COLUMNS = (
    "pred_side_balance_prior_count",
    "pred_side_balance_context_count",
    "pred_side_balance_context_support_weight",
    "pred_side_balance_prior_pred_long_share",
    "pred_side_balance_prior_target_long_share",
    "pred_side_balance_long_share_drift",
    "pred_side_balance_long_scale",
    "pred_side_balance_short_scale",
)


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


def parse_float_csv(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


def parse_family_predictions(values: list[str]) -> dict[str, Path]:
    families: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError("family predictions must use family=path")
        family, path = value.split("=", 1)
        family = family.strip()
        if not family:
            raise argparse.ArgumentTypeError("family name must not be empty")
        families[family] = Path(path.strip())
    if not families:
        raise argparse.ArgumentTypeError("at least one family prediction is required")
    return families


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def bool_mean(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    if pd.api.types.is_bool_dtype(series):
        return float(series.fillna(False).astype(bool).mean())
    if pd.api.types.is_numeric_dtype(series):
        return float(series.fillna(0.0).astype(float).ne(0.0).mean())
    normalized = series.astype(str).str.lower().str.strip()
    return float(normalized.isin({"true", "1", "yes", "y"}).mean())


def read_prediction_frames(
    family_predictions: dict[str, Path],
    *,
    long_column: str,
    short_column: str,
    extra_prediction_columns: Iterable[str],
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for family, path in family_predictions.items():
        predictions = pd.read_parquet(path)
        frames[family] = prepare_analysis_predictions(
            predictions,
            long_column,
            short_column,
            extra_prediction_columns,
        )
    return frames


def trade_path_for_row(trade_root: Path, row: pd.Series) -> Path:
    return trade_root / str(row["family"]) / str(row["candidate"]) / f"{row['month']}.csv"


def read_enriched_trades(
    *,
    monthly_metrics: pd.DataFrame,
    trade_root: Path,
    predictions_by_family: dict[str, pd.DataFrame],
    extra_prediction_columns: Iterable[str],
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    missing_paths: list[Path] = []
    for row in monthly_metrics.itertuples(index=False):
        row_series = pd.Series(row._asdict())
        path = trade_path_for_row(trade_root, row_series)
        if not path.exists():
            missing_paths.append(path)
            continue
        trades = read_trades_csv(path)
        if trades.empty:
            continue
        predictions = predictions_by_family[str(row_series["family"])]
        enriched = enrich_trades_with_predictions(
            trades,
            predictions,
            extra_prediction_columns,
        )
        enriched.insert(0, "candidate", str(row_series["candidate"]))
        enriched.insert(0, "month", str(row_series["month"]))
        enriched.insert(0, "role", str(row_series["role"]))
        enriched.insert(0, "family", str(row_series["family"]))
        frames.append(enriched)
    if missing_paths:
        preview = ", ".join(str(path) for path in missing_paths[:5])
        suffix = "" if len(missing_paths) <= 5 else f" ... ({len(missing_paths)} missing)"
        raise FileNotFoundError(f"missing trade CSVs under --trade-root: {preview}{suffix}")
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def add_side_balance_trade_features(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    direction = output["direction"].astype(str).str.lower()
    drift = numeric_series(output, "pred_side_balance_long_share_drift")
    long_scale = numeric_series(output, "pred_side_balance_long_scale", default=1.0)
    short_scale = numeric_series(output, "pred_side_balance_short_scale", default=1.0)
    taken_scale = pd.Series(
        np.where(direction.eq("long"), long_scale, short_scale),
        index=output.index,
        dtype=float,
    )
    signed_for_trade = pd.Series(
        np.where(direction.eq("long"), drift, -drift),
        index=output.index,
        dtype=float,
    )
    output["side_balance_abs_drift"] = drift.abs()
    output["side_balance_signed_drift_for_trade"] = signed_for_trade
    output["side_balance_selected_side_overrepresented"] = signed_for_trade > 0.0
    output["side_balance_selected_side_underrepresented"] = signed_for_trade < 0.0
    output["side_balance_taken_scale"] = taken_scale
    output["side_balance_taken_penalty"] = (1.0 - taken_scale).clip(lower=0.0)
    return output


def summarize_trade_slice(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "trade_count": 0,
            "total_adjusted_pnl": 0.0,
            "loss_adjusted_pnl": 0.0,
            "win_adjusted_pnl": 0.0,
            "max_side_trade_share": 0.0,
        }
    direction = frame["direction"].astype(str).str.lower()
    adjusted = frame["adjusted_pnl"].astype(float)
    trade_count = int(len(frame))
    long_count = int(direction.eq("long").sum())
    short_count = int(direction.eq("short").sum())
    return {
        "trade_count": trade_count,
        "total_adjusted_pnl": float(adjusted.sum()),
        "loss_adjusted_pnl": float(adjusted.where(adjusted < 0.0, 0.0).sum()),
        "win_adjusted_pnl": float(adjusted.where(adjusted > 0.0, 0.0).sum()),
        "avg_adjusted_pnl": float(adjusted.mean()),
        "win_rate": float((adjusted > 0.0).mean()),
        "long_trade_count": long_count,
        "short_trade_count": short_count,
        "max_side_trade_share": float(max(long_count, short_count) / trade_count),
        "drift_mean": float(numeric_series(frame, "pred_side_balance_long_share_drift").mean()),
        "abs_drift_mean": float(frame["side_balance_abs_drift"].astype(float).mean()),
        "signed_drift_for_trade_mean": float(
            frame["side_balance_signed_drift_for_trade"].astype(float).mean()
        ),
        "selected_side_overrepresented_share": float(
            frame["side_balance_selected_side_overrepresented"].astype(bool).mean()
        ),
        "selected_side_underrepresented_share": float(
            frame["side_balance_selected_side_underrepresented"].astype(bool).mean()
        ),
        "taken_scale_mean": float(frame["side_balance_taken_scale"].astype(float).mean()),
        "taken_penalty_mean": float(frame["side_balance_taken_penalty"].astype(float).mean()),
        "prior_count_mean": float(
            numeric_series(frame, "pred_side_balance_prior_count").mean()
        ),
        "context_count_mean": float(
            numeric_series(frame, "pred_side_balance_context_count").mean()
        ),
        "context_support_weight_mean": float(
            numeric_series(frame, "pred_side_balance_context_support_weight").mean()
        ),
        "direction_error_rate": bool_mean(frame.get("direction_error", pd.Series(index=frame.index))),
        "no_edge_rate": bool_mean(frame.get("no_edge_entry", pd.Series(index=frame.index))),
    }


def summarize_groups(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_columns)
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(group_columns, dropna=False, observed=True):
        if not isinstance(key, tuple):
            key = (key,)
        row = dict(zip(group_columns, key))
        row.update(summarize_trade_slice(group))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["total_adjusted_pnl", "trade_count"],
        ascending=[True, False],
    ).reset_index(drop=True)


def summarize_candidate_path(frame: pd.DataFrame) -> dict[str, Any]:
    base = summarize_trade_slice(frame)
    if frame.empty:
        base.update(
            {
                "role_count": 0,
                "active_role_count": 0,
                "positive_role_count": 0,
                "min_role_total_pnl": 0.0,
                "month_count": 0,
                "active_months": 0,
                "min_month_pnl": 0.0,
            }
        )
        return base
    role_totals = frame.groupby("role", dropna=False)["adjusted_pnl"].sum()
    month_totals = frame.groupby(["role", "month"], dropna=False)["adjusted_pnl"].sum()
    base.update(
        {
            "role_count": int(role_totals.shape[0]),
            "active_role_count": int((role_totals != 0.0).sum()),
            "positive_role_count": int((role_totals > 0.0).sum()),
            "min_role_total_pnl": float(role_totals.min()),
            "month_count": int(month_totals.shape[0]),
            "active_months": int((month_totals != 0.0).sum()),
            "min_month_pnl": float(month_totals.min()),
        }
    )
    return base


def screen_masks(frame: pd.DataFrame, threshold: float) -> dict[str, pd.Series]:
    abs_drift = frame["side_balance_abs_drift"].astype(float)
    signed = frame["side_balance_signed_drift_for_trade"].astype(float)
    return {
        "selected_overrepresented": (signed >= threshold) & (threshold > 0.0),
        "selected_underrepresented": (signed <= -threshold) & (threshold > 0.0),
        "abs_drift_high": abs_drift >= threshold,
    }


def summarize_screen_effects(frame: pd.DataFrame, thresholds: list[float]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for candidate, candidate_frame in frame.groupby("candidate", dropna=False):
        original = summarize_candidate_path(candidate_frame)
        for threshold in thresholds:
            for screen_name, mask in screen_masks(candidate_frame, threshold).items():
                removed = candidate_frame[mask]
                kept = candidate_frame[~mask]
                removed_summary = summarize_trade_slice(removed)
                kept_summary = summarize_candidate_path(kept)
                rows.append(
                    {
                        "candidate": candidate,
                        "screen": screen_name,
                        "threshold": threshold,
                        "original_total_pnl": original["total_adjusted_pnl"],
                        "original_min_role_total_pnl": original["min_role_total_pnl"],
                        "original_min_month_pnl": original["min_month_pnl"],
                        "original_trade_count": original["trade_count"],
                        "removed_trade_count": removed_summary["trade_count"],
                        "removed_total_pnl": removed_summary["total_adjusted_pnl"],
                        "removed_loss_pnl": removed_summary["loss_adjusted_pnl"],
                        "removed_win_pnl": removed_summary["win_adjusted_pnl"],
                        "kept_total_pnl": kept_summary["total_adjusted_pnl"],
                        "kept_min_role_total_pnl": kept_summary["min_role_total_pnl"],
                        "kept_min_month_pnl": kept_summary["min_month_pnl"],
                        "kept_trade_count": kept_summary["trade_count"],
                        "kept_max_side_trade_share": kept_summary["max_side_trade_share"],
                        "pointwise_delta_if_removed": (
                            kept_summary["total_adjusted_pnl"]
                            - original["total_adjusted_pnl"]
                        ),
                    }
                )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        [
            "pointwise_delta_if_removed",
            "kept_min_role_total_pnl",
            "kept_total_pnl",
            "removed_trade_count",
        ],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def build_diagnostics(args: argparse.Namespace) -> Path:
    family_predictions = parse_family_predictions(args.family_predictions)
    extra_prediction_columns = [
        *DEFAULT_SIDE_BALANCE_COLUMNS,
        *parse_csv(args.extra_prediction_columns),
    ]
    monthly = pd.read_csv(args.monthly_metrics)
    if args.candidates:
        candidates = set(parse_csv(args.candidates))
        monthly = monthly[monthly["candidate"].astype(str).isin(candidates)].copy()
    if args.roles:
        roles = set(parse_csv(args.roles))
        monthly = monthly[monthly["role"].astype(str).isin(roles)].copy()
    if monthly.empty:
        raise ValueError("no monthly metrics remain after filters")

    predictions_by_family = read_prediction_frames(
        family_predictions,
        long_column=args.long_column,
        short_column=args.short_column,
        extra_prediction_columns=extra_prediction_columns,
    )
    enriched = read_enriched_trades(
        monthly_metrics=monthly,
        trade_root=args.trade_root,
        predictions_by_family=predictions_by_family,
        extra_prediction_columns=extra_prediction_columns,
    )
    enriched = add_side_balance_trade_features(enriched)

    run_dir = make_run_dir(args.output_dir, args.label)
    monthly.to_csv(run_dir / "input_monthly_metrics.csv", index=False)
    enriched.to_csv(run_dir / "enriched_side_balance_trades.csv", index=False)

    role_candidate = summarize_groups(enriched, ["role", "candidate"])
    role_candidate.to_csv(run_dir / "role_candidate_side_balance_summary.csv", index=False)
    role_month = summarize_groups(enriched, ["role", "candidate", "month"])
    role_month.to_csv(run_dir / "role_month_side_balance_summary.csv", index=False)
    role_context = summarize_groups(
        enriched,
        ["role", "candidate", "direction", "combined_regime", "session_regime"],
    )
    role_context.to_csv(run_dir / "role_context_side_balance_summary.csv", index=False)
    role_context.head(args.top_n).to_csv(run_dir / "top_negative_side_balance_contexts.csv", index=False)

    screen_effects = summarize_screen_effects(enriched, parse_float_csv(args.thresholds))
    screen_effects.to_csv(run_dir / "side_balance_screen_effects.csv", index=False)

    config = {
        "monthly_metrics": args.monthly_metrics,
        "trade_root": args.trade_root,
        "family_predictions": family_predictions,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "extra_prediction_columns": extra_prediction_columns,
        "candidates": args.candidates,
        "roles": args.roles,
        "thresholds": parse_float_csv(args.thresholds),
        "top_n": args.top_n,
        "note": "screen effects are pointwise diagnostics and do not model stateful replacements",
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Side-balance role/candidate summary:")
    print(
        role_candidate[
            [
                "role",
                "candidate",
                "trade_count",
                "total_adjusted_pnl",
                "abs_drift_mean",
                "selected_side_overrepresented_share",
                "taken_penalty_mean",
            ]
        ]
        .head(args.top_n)
        .to_string(index=False)
    )
    print("\nPointwise side-balance screens:")
    print(
        screen_effects[
            [
                "candidate",
                "screen",
                "threshold",
                "removed_trade_count",
                "removed_total_pnl",
                "kept_total_pnl",
                "kept_min_role_total_pnl",
                "pointwise_delta_if_removed",
            ]
        ]
        .head(args.top_n)
        .to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monthly-metrics", type=Path, required=True)
    parser.add_argument("--trade-root", type=Path, required=True)
    parser.add_argument(
        "--family-predictions",
        action="append",
        required=True,
        help="family=prediction parquet; can be repeated",
    )
    parser.add_argument(
        "--long-column",
        default="pred_side_balanced_dense_executable_long_best_adjusted_pnl",
    )
    parser.add_argument(
        "--short-column",
        default="pred_side_balanced_dense_executable_short_best_adjusted_pnl",
    )
    parser.add_argument("--extra-prediction-columns", default="")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--roles", default="")
    parser.add_argument("--thresholds", default="0.02,0.05,0.10")
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_side_balance_feature_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
