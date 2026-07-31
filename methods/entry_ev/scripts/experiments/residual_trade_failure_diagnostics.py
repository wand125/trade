#!/usr/bin/env python3
"""Summarize residual losing trade contexts from enriched diagnostic trades."""

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

from trade_data.backtest import json_default, make_run_dir, trade_exposure_diagnostic_summary  # noqa: E402


DEFAULT_GROUP_SPECS = {
    "context": ["month", "direction", "combined_regime", "session_regime"],
    "side_gap": [
        "month",
        "direction",
        "combined_regime",
        "session_regime",
        "pred_side_gap_bucket",
    ],
    "side_confidence": [
        "month",
        "direction",
        "combined_regime",
        "session_regime",
        "pred_side_confidence_bucket",
    ],
    "profit_barrier": [
        "month",
        "direction",
        "combined_regime",
        "session_regime",
        "profit_barrier_outcome",
    ],
    "pred_holding": [
        "month",
        "direction",
        "combined_regime",
        "session_regime",
        "pred_holding_bucket",
    ],
    "entry_hour": [
        "month",
        "direction",
        "combined_regime",
        "session_regime",
        "entry_hour",
    ],
}

SUMMARY_NUMERIC_COLUMNS = [
    "pred_taken_profit_barrier_hit",
    "actual_taken_profit_barrier_hit",
    "pred_side_gap",
    "pred_taken_ev",
    "pred_taken_best_holding_minutes",
    "holding_ratio_actual_vs_pred",
    "pred_taken_side_confidence",
    "pred_side_confidence_gap",
    "exit_regret",
    "best_side_regret",
    "ev_overestimate_vs_realized",
]


def local_json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    try:
        return json_default(value)
    except TypeError:
        pass
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def parse_csv_strings(value: str) -> list[str]:
    values = [part.strip() for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def normalize_trade_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"month", "direction", "adjusted_pnl"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"diagnostic trades missing required columns: {', '.join(missing)}")
    output = frame.copy()
    output["month"] = output["month"].astype(str)
    output["adjusted_pnl"] = pd.to_numeric(output["adjusted_pnl"], errors="coerce")
    if output["adjusted_pnl"].isna().any():
        raise ValueError("diagnostic trades contain non-numeric adjusted_pnl values")
    for column in ["direction", "combined_regime", "session_regime"]:
        if column not in output.columns:
            output[column] = "__missing__"
        output[column] = output[column].astype("string").fillna("__missing__")
    for column in SUMMARY_NUMERIC_COLUMNS:
        if column not in output.columns:
            output[column] = np.nan
        output[column] = pd.to_numeric(output[column], errors="coerce")
    if "entry_hour" in output.columns:
        output["entry_hour"] = pd.to_numeric(output["entry_hour"], errors="coerce").astype("Int64")
    return output


def month_summary(frame: pd.DataFrame) -> pd.DataFrame:
    working = normalize_trade_frame(frame)
    summary = (
        working.groupby("month", dropna=False)
        .agg(
            trade_count=("adjusted_pnl", "size"),
            total_adjusted_pnl=("adjusted_pnl", "sum"),
            avg_adjusted_pnl=("adjusted_pnl", "mean"),
            win_rate=("adjusted_pnl", lambda values: float((values > 0).mean())),
            loss_rate=("adjusted_pnl", lambda values: float((values <= 0).mean())),
        )
        .reset_index()
        .sort_values(["month"])
        .reset_index(drop=True)
    )
    return summary


def select_residual_months(
    frame: pd.DataFrame,
    *,
    explicit_months: list[str] | None = None,
    max_month_pnl: float = 0.0,
) -> list[str]:
    if explicit_months:
        return explicit_months
    summary = month_summary(frame)
    return summary.loc[summary["total_adjusted_pnl"] < max_month_pnl, "month"].astype(str).tolist()


def summarize_groups(
    frame: pd.DataFrame,
    group_columns: list[str],
    *,
    large_loss_threshold: float,
) -> pd.DataFrame:
    missing = [column for column in group_columns if column not in frame.columns]
    if missing:
        return pd.DataFrame()
    summary = trade_exposure_diagnostic_summary(
        frame,
        group_columns,
        large_loss_threshold=large_loss_threshold,
    )
    if "total_adjusted_pnl" in summary.columns:
        summary = summary.sort_values("total_adjusted_pnl", ascending=True).reset_index(drop=True)
    return summary


def run_diagnostics(
    *,
    trades_path: Path,
    output_dir: Path,
    label: str,
    months: list[str] | None = None,
    max_month_pnl: float = 0.0,
    large_loss_threshold: float = -15.0,
    top_n: int = 20,
) -> Path:
    trades = normalize_trade_frame(pd.read_csv(trades_path))
    selected_months = select_residual_months(
        trades,
        explicit_months=months,
        max_month_pnl=max_month_pnl,
    )
    residual = trades[trades["month"].isin(selected_months)].copy()
    run_dir = make_run_dir(output_dir, label)

    all_month_summary = month_summary(trades)
    all_month_summary.to_csv(run_dir / "month_summary.csv", index=False)
    residual.to_csv(run_dir / "residual_trades.csv", index=False)

    summaries: dict[str, pd.DataFrame] = {}
    for name, columns in DEFAULT_GROUP_SPECS.items():
        summary = summarize_groups(
            residual,
            columns,
            large_loss_threshold=large_loss_threshold,
        )
        if summary.empty:
            continue
        summaries[name] = summary
        summary.to_csv(run_dir / f"residual_by_{name}.csv", index=False)

    side_summary = summarize_groups(
        residual,
        ["direction"],
        large_loss_threshold=large_loss_threshold,
    )
    if not side_summary.empty:
        side_summary.to_csv(run_dir / "residual_by_direction.csv", index=False)

    metrics = {
        "trades_path": trades_path,
        "selected_months": selected_months,
        "row_count": int(len(trades)),
        "residual_row_count": int(len(residual)),
        "total_adjusted_pnl": float(trades["adjusted_pnl"].sum()),
        "residual_total_adjusted_pnl": float(residual["adjusted_pnl"].sum()),
        "large_loss_threshold": large_loss_threshold,
        "top_n": top_n,
    }
    (run_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "trades_path": trades_path,
                "output_dir": output_dir,
                "label": label,
                "months": months,
                "max_month_pnl": max_month_pnl,
                "large_loss_threshold": large_loss_threshold,
                "top_n": top_n,
            },
            ensure_ascii=False,
            indent=2,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"residual months: {', '.join(selected_months) if selected_months else '(none)'}")
    print(f"residual rows: {len(residual)} / {len(trades)}")
    if not side_summary.empty:
        print("residual by direction:")
        print(side_summary.head(top_n).to_string(index=False))
    if "context" in summaries:
        display_columns = [
            "month",
            "direction",
            "combined_regime",
            "session_regime",
            "trade_count",
            "total_adjusted_pnl",
            "avg_adjusted_pnl",
            "direction_error_rate",
            "ev_overestimate_vs_realized_mean",
            "exit_regret_mean",
            "pred_side_gap_mean",
            "pred_taken_side_confidence_mean",
            "actual_profit_barrier_hit_rate",
            "predicted_profit_barrier_hit_rate",
        ]
        existing = [column for column in display_columns if column in summaries["context"].columns]
        print("worst residual contexts:")
        print(summaries["context"].loc[:, existing].head(top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize residual losing contexts from diagnostic_trades.csv.",
    )
    parser.add_argument("--trades", type=Path, required=True, help="diagnostic_trades.csv path")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="residual_trade_failure_diagnostics")
    parser.add_argument(
        "--months",
        type=parse_csv_strings,
        help="optional comma-separated months; defaults to months with total PnL below --max-month-pnl",
    )
    parser.add_argument("--max-month-pnl", type=float, default=0.0)
    parser.add_argument("--large-loss-threshold", type=float, default=-15.0)
    parser.add_argument("--top-n", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_diagnostics(
        trades_path=args.trades,
        output_dir=args.output_dir,
        label=args.label,
        months=args.months,
        max_month_pnl=args.max_month_pnl,
        large_loss_threshold=args.large_loss_threshold,
        top_n=args.top_n,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
