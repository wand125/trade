#!/usr/bin/env python3
"""Diagnose entry-EV quantile policy trades by validation role and context."""

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


DEFAULT_EXTRA_PREDICTION_COLUMNS = (
    "pred_calibrated_selected_score_pct_month",
    "pred_calibrated_selected_score_pct_side_month",
    "pred_calibrated_selected_score_pct_side_regime_session_month",
    "pred_calibrated_side_gap_pct_month",
    "pred_calibrated_side_gap_pct_side_month",
    "pred_calibrated_side_gap_pct_side_regime_session_month",
    "pred_calibrated_selected_entry_rank_pct_month",
    "pred_calibrated_selected_entry_rank_pct_side_month",
    "pred_calibrated_selected_entry_rank_pct_side_regime_session_month",
    "pred_mlp_long_exit_event_minutes",
    "pred_mlp_short_exit_event_minutes",
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


def parse_optional_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


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


def bool_mean(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    return float(series.fillna(False).astype(bool).mean())


def summarize_trade_groups(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_columns)
    working = frame.copy()
    adjusted = working["adjusted_pnl"].astype(float)
    working["_win"] = adjusted > 0
    working["_loss"] = adjusted < 0
    working["_loss_adjusted_pnl"] = adjusted.where(adjusted < 0, 0.0)
    working["_long"] = working["direction"].astype(str).str.lower().eq("long")
    working["_short"] = working["direction"].astype(str).str.lower().eq("short")
    for column in [
        "no_edge_entry",
        "direction_error",
        "predicted_side_error",
        "actual_taken_profit_barrier_hit",
        "pred_taken_profit_barrier_hit",
        "matched_prediction",
    ]:
        if column not in working.columns:
            working[column] = np.nan

    rows: list[dict[str, Any]] = []
    for key, group in working.groupby(group_columns, dropna=False, observed=True):
        if not isinstance(key, tuple):
            key = (key,)
        row = dict(zip(group_columns, key))
        trade_count = int(len(group))
        long_count = int(group["_long"].sum())
        short_count = int(group["_short"].sum())
        row.update(
            {
                "trade_count": trade_count,
                "total_adjusted_pnl": float(group["adjusted_pnl"].astype(float).sum()),
                "loss_adjusted_pnl": float(group["_loss_adjusted_pnl"].sum()),
                "avg_adjusted_pnl": float(group["adjusted_pnl"].astype(float).mean()),
                "win_rate": bool_mean(group["_win"]),
                "long_trade_count": long_count,
                "short_trade_count": short_count,
                "long_trade_share": float(long_count / trade_count) if trade_count else 0.0,
                "short_trade_share": float(short_count / trade_count) if trade_count else 0.0,
                "no_edge_rate": bool_mean(group["no_edge_entry"]),
                "direction_error_rate": bool_mean(group["direction_error"]),
                "predicted_side_error_rate": bool_mean(group["predicted_side_error"]),
                "matched_prediction_rate": bool_mean(group["matched_prediction"]),
                "actual_profit_barrier_hit_rate": float(
                    group["actual_taken_profit_barrier_hit"].astype(float).mean()
                ),
                "predicted_profit_barrier_hit_mean": float(
                    group["pred_taken_profit_barrier_hit"].astype(float).mean()
                ),
                "pred_taken_ev_mean": float(group["pred_taken_ev"].astype(float).mean()),
                "actual_taken_best_adjusted_pnl_mean": float(
                    group["actual_taken_best_adjusted_pnl"].astype(float).mean()
                ),
                "ev_overestimate_vs_oracle_mean": float(
                    group["ev_overestimate_vs_oracle"].astype(float).mean()
                ),
                "ev_overestimate_vs_realized_mean": float(
                    group["ev_overestimate_vs_realized"].astype(float).mean()
                ),
                "exit_regret_sum": float(group["exit_regret"].astype(float).sum()),
                "best_side_regret_sum": float(group["best_side_regret"].astype(float).sum()),
                "avg_holding_minutes": float(group["holding_minutes"].astype(float).mean()),
            }
        )
        row["max_side_trade_share"] = max(row["long_trade_share"], row["short_trade_share"])
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["total_adjusted_pnl", "trade_count"],
        ascending=[True, False],
    )


def summarize_candidate_role_spread(role_candidate_summary: pd.DataFrame) -> pd.DataFrame:
    if role_candidate_summary.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for candidate, group in role_candidate_summary.groupby("candidate", dropna=False):
        totals = group["total_adjusted_pnl"].astype(float)
        worst_row = group.sort_values("total_adjusted_pnl", ascending=True).iloc[0]
        rows.append(
            {
                "candidate": candidate,
                "role_count": int(group["role"].nunique()),
                "positive_role_count": int((totals > 0).sum()),
                "negative_role_count": int((totals < 0).sum()),
                "total_adjusted_pnl_sum": float(totals.sum()),
                "role_total_pnl_min": float(totals.min()),
                "role_total_pnl_max": float(totals.max()),
                "role_total_pnl_spread": float(totals.max() - totals.min()),
                "worst_role": str(worst_row["role"]),
                "worst_role_trade_count": int(worst_row["trade_count"]),
                "worst_role_no_edge_rate": float(worst_row["no_edge_rate"]),
                "worst_role_ev_overestimate_vs_oracle_mean": float(
                    worst_row["ev_overestimate_vs_oracle_mean"]
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["role_total_pnl_min", "total_adjusted_pnl_sum"],
        ascending=[False, False],
    )


def build_diagnostics(args: argparse.Namespace) -> Path:
    family_predictions = parse_family_predictions(args.family_predictions)
    extra_prediction_columns = [
        *DEFAULT_EXTRA_PREDICTION_COLUMNS,
        *parse_optional_csv(args.extra_prediction_columns),
    ]
    monthly = pd.read_csv(args.monthly_metrics)
    if args.candidates:
        candidates = set(parse_optional_csv(args.candidates))
        monthly = monthly[monthly["candidate"].astype(str).isin(candidates)].copy()
    if args.roles:
        roles = set(parse_optional_csv(args.roles))
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

    run_dir = make_run_dir(args.output_dir, args.label)
    monthly.to_csv(run_dir / "input_monthly_metrics.csv", index=False)
    enriched.to_csv(run_dir / "enriched_trades.csv", index=False)

    role_candidate = summarize_trade_groups(enriched, ["role", "candidate"])
    role_candidate.to_csv(run_dir / "role_candidate_trade_summary.csv", index=False)

    role_month = summarize_trade_groups(enriched, ["role", "candidate", "month"])
    role_month.to_csv(run_dir / "role_month_trade_summary.csv", index=False)

    role_context = summarize_trade_groups(
        enriched,
        ["role", "candidate", "direction", "combined_regime", "session_regime"],
    )
    role_context.to_csv(run_dir / "role_context_trade_summary.csv", index=False)
    role_context.head(args.top_n).to_csv(run_dir / "top_negative_contexts.csv", index=False)

    candidate_spread = summarize_candidate_role_spread(role_candidate)
    candidate_spread.to_csv(run_dir / "candidate_role_spread.csv", index=False)

    config = {
        "monthly_metrics": args.monthly_metrics,
        "trade_root": args.trade_root,
        "family_predictions": family_predictions,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "extra_prediction_columns": extra_prediction_columns,
        "candidates": args.candidates,
        "roles": args.roles,
        "top_n": args.top_n,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Candidate role spread:")
    print(candidate_spread.head(args.top_n).to_string(index=False))
    print("\nWorst contexts:")
    print(
        role_context[
            [
                "role",
                "candidate",
                "direction",
                "combined_regime",
                "session_regime",
                "trade_count",
                "total_adjusted_pnl",
                "no_edge_rate",
                "direction_error_rate",
                "ev_overestimate_vs_oracle_mean",
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
    parser.add_argument("--long-column", default="pred_calibrated_long_best_adjusted_pnl")
    parser.add_argument("--short-column", default="pred_calibrated_short_best_adjusted_pnl")
    parser.add_argument("--extra-prediction-columns", default="")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--roles", default="")
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    parser.add_argument("--label", default="entry_ev_quantile_trade_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
