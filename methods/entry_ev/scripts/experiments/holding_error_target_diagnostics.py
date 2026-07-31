#!/usr/bin/env python3
"""Diagnose dense holding-error / exit-regret targets from enriched trade rows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


def parse_csv_paths(value: str) -> list[Path]:
    paths = [Path(part.strip()) for part in value.split(",") if part.strip()]
    if not paths:
        raise argparse.ArgumentTypeError("at least one path is required")
    return paths


def parse_csv_strings(value: str) -> list[str]:
    values = [part.strip() for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def expand_trade_paths(paths: list[Path]) -> list[Path]:
    expanded: list[Path] = []
    candidate_names = [
        "trade_delta_rows.csv",
        "combined_enriched_trades.csv",
        "enriched_trades.csv",
        "walkforward_selected_trades.csv",
        "selected_trades.csv",
    ]
    for path in paths:
        if path.is_file():
            expanded.append(path)
            continue
        found = False
        for name in candidate_names:
            candidate = path / name
            if candidate.exists():
                expanded.append(candidate)
                found = True
                break
        if found:
            continue
        if path.is_dir():
            children = [
                child / "trade_delta_rows.csv"
                for child in sorted(path.iterdir())
                if child.is_dir() and (child / "trade_delta_rows.csv").exists()
            ]
            if children:
                expanded.extend(children)
                continue
        expanded.append(path / "trade_delta_rows.csv")
    return expanded


def infer_source_label(path: Path) -> str:
    parent = path.parent.name
    if "risk5" in parent:
        return "risk5"
    if "risk0" in parent:
        return "risk0"
    return parent


def read_trade_rows(paths: list[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in expand_trade_paths(paths):
        if not path.exists():
            raise FileNotFoundError(f"trade rows not found: {path}")
        frame = pd.read_csv(path)
        if frame.empty:
            continue
        frame = frame.copy()
        frame["source_path"] = str(path)
        if "case_label" not in frame.columns:
            frame["case_label"] = infer_source_label(path)
        frames.append(frame)
    if not frames:
        raise ValueError("no non-empty trade rows found")
    return pd.concat(frames, ignore_index=True)


def first_existing_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    for column in candidates:
        if column in frame.columns:
            return column
    return None


def numeric_column(frame: pd.DataFrame, column: str | None, default: float = np.nan) -> pd.Series:
    if column is None or column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def bucket_series(series: pd.Series, bins: list[float], labels: list[str]) -> pd.Series:
    return pd.cut(
        pd.to_numeric(series, errors="coerce"),
        bins=bins,
        labels=labels,
        include_lowest=True,
    ).astype("string").fillna("__missing__")


def prepare_holding_error_frame(
    frame: pd.DataFrame,
    *,
    pnl_source: str,
    min_abs_regret: float,
    min_abs_gap_minutes: float,
) -> pd.DataFrame:
    if pnl_source not in {"auto", "base", "candidate"}:
        raise ValueError("pnl_source must be one of auto, base, candidate")
    output = frame.copy()
    if "month" not in output.columns:
        if "dataset_month" in output.columns:
            output["month"] = output["dataset_month"].astype(str)
        elif "entry_timestamp" in output.columns:
            output["month"] = pd.to_datetime(output["entry_timestamp"], utc=True).dt.strftime("%Y-%m")
        else:
            output["month"] = "__missing__"
    output["month"] = output["month"].astype(str)
    if "delta_status" not in output.columns:
        output["delta_status"] = "selected"

    if pnl_source == "base":
        pnl_column = "base_adjusted_pnl"
        holding_column = "base_holding_minutes"
    elif pnl_source == "candidate":
        pnl_column = "candidate_adjusted_pnl"
        holding_column = "candidate_holding_minutes"
    else:
        pnl_column = first_existing_column(output, ["adjusted_pnl", "base_adjusted_pnl", "candidate_adjusted_pnl"])
        holding_column = first_existing_column(output, ["holding_minutes", "base_holding_minutes", "candidate_holding_minutes"])

    output["analysis_adjusted_pnl"] = numeric_column(output, pnl_column)
    output["analysis_holding_minutes"] = numeric_column(output, holding_column)
    output = output[
        output["analysis_adjusted_pnl"].notna() & output["analysis_holding_minutes"].notna()
    ].copy()
    output["exit_regret"] = numeric_column(output, "exit_regret")
    output["holding_error_minutes"] = numeric_column(output, "holding_error_minutes")
    output["oracle_holding_gap_minutes"] = numeric_column(output, "oracle_holding_gap_minutes")
    output["pred_taken_best_holding_minutes"] = numeric_column(output, "pred_taken_best_holding_minutes")

    actual_holding_column = first_existing_column(
        output,
        ["actual_taken_best_holding_minutes", "actual_best_holding_minutes"],
    )
    output["actual_taken_best_holding_minutes"] = numeric_column(output, actual_holding_column)
    if output["holding_error_minutes"].isna().all():
        output["holding_error_minutes"] = (
            output["pred_taken_best_holding_minutes"] - output["analysis_holding_minutes"]
        )
    if output["oracle_holding_gap_minutes"].isna().all():
        output["oracle_holding_gap_minutes"] = (
            output["actual_taken_best_holding_minutes"] - output["analysis_holding_minutes"]
        )

    output["holding_error_abs"] = output["holding_error_minutes"].abs()
    output["oracle_gap_abs"] = output["oracle_holding_gap_minutes"].abs()
    output["pred_minus_oracle_holding_minutes"] = (
        output["pred_taken_best_holding_minutes"] - output["actual_taken_best_holding_minutes"]
    )
    missing_pred_minus_oracle = output["pred_minus_oracle_holding_minutes"].isna()
    output.loc[missing_pred_minus_oracle, "pred_minus_oracle_holding_minutes"] = (
        output.loc[missing_pred_minus_oracle, "holding_error_minutes"]
        - output.loc[missing_pred_minus_oracle, "oracle_holding_gap_minutes"]
    )
    output["exit_shortening_target"] = (
        output["oracle_holding_gap_minutes"].le(-min_abs_gap_minutes)
        & output["exit_regret"].ge(min_abs_regret)
    )
    output["hold_extension_target"] = (
        output["oracle_holding_gap_minutes"].ge(min_abs_gap_minutes)
        & output["exit_regret"].ge(min_abs_regret)
    )
    output["holding_mismatch_target"] = output["exit_shortening_target"] | output["hold_extension_target"]
    output["large_negative_pnl"] = output["analysis_adjusted_pnl"].le(-15.0)
    output["positive_pnl"] = output["analysis_adjusted_pnl"].gt(0.0)

    output["oracle_gap_bucket"] = bucket_series(
        output["oracle_holding_gap_minutes"],
        [-float("inf"), -240, -120, -30, 30, 120, 240, float("inf")],
        ["<=-240", "-240--120", "-120--30", "-30-30", "30-120", "120-240", ">240"],
    )
    output["holding_error_bucket"] = bucket_series(
        output["holding_error_minutes"],
        [-float("inf"), -240, -120, -30, 30, 120, 240, float("inf")],
        ["<=-240", "-240--120", "-120--30", "-30-30", "30-120", "120-240", ">240"],
    )
    output["exit_regret_bucket"] = bucket_series(
        output["exit_regret"],
        [-float("inf"), 0, 5, 10, 20, 40, float("inf")],
        ["<=0", "0-5", "5-10", "10-20", "20-40", ">40"],
    )
    return output


def summarize_holding_errors(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_columns)
    missing = sorted(set(group_columns) - set(frame.columns))
    if missing:
        raise ValueError(f"holding error frame missing columns: {', '.join(missing)}")
    working = frame.copy()
    for column in group_columns:
        working[column] = working[column].astype("string").fillna("__missing__")
    summary = (
        working.groupby(group_columns, dropna=False, observed=True)
        .agg(
            trade_count=("analysis_adjusted_pnl", "size"),
            total_adjusted_pnl=("analysis_adjusted_pnl", "sum"),
            avg_adjusted_pnl=("analysis_adjusted_pnl", "mean"),
            positive_rate=("positive_pnl", "mean"),
            large_negative_rate=("large_negative_pnl", "mean"),
            exit_regret_mean=("exit_regret", "mean"),
            exit_regret_sum=("exit_regret", "sum"),
            holding_error_mean=("holding_error_minutes", "mean"),
            holding_error_abs_mean=("holding_error_abs", "mean"),
            oracle_gap_mean=("oracle_holding_gap_minutes", "mean"),
            oracle_gap_abs_mean=("oracle_gap_abs", "mean"),
            pred_minus_oracle_holding_mean=("pred_minus_oracle_holding_minutes", "mean"),
            exit_shortening_rate=("exit_shortening_target", "mean"),
            hold_extension_rate=("hold_extension_target", "mean"),
            holding_mismatch_rate=("holding_mismatch_target", "mean"),
        )
        .reset_index()
    )
    return summary.sort_values(
        ["total_adjusted_pnl", "trade_count"],
        ascending=[True, False],
    ).reset_index(drop=True)


def walkforward_target_profiles(
    frame: pd.DataFrame,
    group_columns: list[str],
    *,
    min_prior_support: int,
) -> pd.DataFrame:
    months = sorted(frame["month"].astype(str).unique())
    rows: list[pd.DataFrame] = []
    for month in months:
        prior = frame[frame["month"].astype(str) < month].copy()
        holdout = frame[frame["month"].astype(str).eq(month)].copy()
        if prior.empty or holdout.empty:
            continue
        prior_summary = summarize_holding_errors(prior, group_columns).rename(
            columns={
                "trade_count": "prior_trade_count",
                "total_adjusted_pnl": "prior_total_adjusted_pnl",
                "avg_adjusted_pnl": "prior_avg_adjusted_pnl",
                "exit_shortening_rate": "prior_exit_shortening_rate",
                "hold_extension_rate": "prior_hold_extension_rate",
                "holding_mismatch_rate": "prior_holding_mismatch_rate",
                "exit_regret_mean": "prior_exit_regret_mean",
                "oracle_gap_mean": "prior_oracle_gap_mean",
            }
        )
        holdout_summary = summarize_holding_errors(holdout, group_columns).rename(
            columns={
                "trade_count": "holdout_trade_count",
                "total_adjusted_pnl": "holdout_total_adjusted_pnl",
                "avg_adjusted_pnl": "holdout_avg_adjusted_pnl",
                "exit_shortening_rate": "holdout_exit_shortening_rate",
                "hold_extension_rate": "holdout_hold_extension_rate",
                "holding_mismatch_rate": "holdout_holding_mismatch_rate",
                "exit_regret_mean": "holdout_exit_regret_mean",
                "oracle_gap_mean": "holdout_oracle_gap_mean",
            }
        )
        keep_prior = [
            *group_columns,
            "prior_trade_count",
            "prior_total_adjusted_pnl",
            "prior_avg_adjusted_pnl",
            "prior_exit_shortening_rate",
            "prior_hold_extension_rate",
            "prior_holding_mismatch_rate",
            "prior_exit_regret_mean",
            "prior_oracle_gap_mean",
        ]
        keep_holdout = [
            *group_columns,
            "holdout_trade_count",
            "holdout_total_adjusted_pnl",
            "holdout_avg_adjusted_pnl",
            "holdout_exit_shortening_rate",
            "holdout_hold_extension_rate",
            "holdout_holding_mismatch_rate",
            "holdout_exit_regret_mean",
            "holdout_oracle_gap_mean",
        ]
        joined = prior_summary[keep_prior].merge(
            holdout_summary[keep_holdout],
            on=group_columns,
            how="inner",
        )
        joined = joined[joined["prior_trade_count"].ge(min_prior_support)].copy()
        if joined.empty:
            continue
        joined["target_month"] = month
        joined["prior_loss_holdout_profit_flip"] = (
            joined["prior_avg_adjusted_pnl"].lt(0.0) & joined["holdout_avg_adjusted_pnl"].gt(0.0)
        )
        joined["prior_profit_holdout_loss_flip"] = (
            joined["prior_avg_adjusted_pnl"].gt(0.0) & joined["holdout_avg_adjusted_pnl"].lt(0.0)
        )
        joined["holdout_minus_prior_avg_pnl"] = (
            joined["holdout_avg_adjusted_pnl"] - joined["prior_avg_adjusted_pnl"]
        )
        rows.append(joined)
    if not rows:
        return pd.DataFrame(columns=["target_month", *group_columns])
    output = pd.concat(rows, ignore_index=True)
    return output.sort_values(
        ["prior_profit_holdout_loss_flip", "holdout_avg_adjusted_pnl", "prior_trade_count"],
        ascending=[False, True, False],
    ).reset_index(drop=True)


def correlation_summary(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "analysis_adjusted_pnl",
        "exit_regret",
        "holding_error_minutes",
        "holding_error_abs",
        "oracle_holding_gap_minutes",
        "oracle_gap_abs",
        "pred_minus_oracle_holding_minutes",
    ]
    available = [column for column in columns if column in frame.columns]
    if len(available) < 2:
        return pd.DataFrame()
    corr = frame[available].corr(numeric_only=True)
    rows = []
    for column in available:
        if column == "analysis_adjusted_pnl":
            continue
        rows.append(
            {
                "feature": column,
                "corr_adjusted_pnl": float(corr.loc[column, "analysis_adjusted_pnl"]),
                "corr_exit_regret": (
                    float(corr.loc[column, "exit_regret"])
                    if "exit_regret" in corr.columns and column != "exit_regret"
                    else np.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trade-rows", type=parse_csv_paths, required=True)
    parser.add_argument("--pnl-source", choices=["auto", "base", "candidate"], default="base")
    parser.add_argument("--case-label", default=None)
    parser.add_argument("--min-abs-regret", type=float, default=5.0)
    parser.add_argument("--min-abs-gap-minutes", type=float, default=30.0)
    parser.add_argument(
        "--walkforward-group-columns",
        type=parse_csv_strings,
        default=["case_label", "direction", "combined_regime", "session_regime"],
    )
    parser.add_argument("--min-prior-support", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="holding_error_target_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = make_run_dir(args.output_dir, args.label)
    rows = read_trade_rows(args.trade_rows)
    diagnostics = prepare_holding_error_frame(
        rows,
        pnl_source=args.pnl_source,
        min_abs_regret=args.min_abs_regret,
        min_abs_gap_minutes=args.min_abs_gap_minutes,
    )
    if args.case_label:
        diagnostics["case_label"] = args.case_label
    diagnostics.to_csv(run_dir / "holding_error_trade_rows.csv", index=False)

    group_sets = {
        "by_month": ["case_label", "month"],
        "by_direction": ["case_label", "direction"],
        "by_combined_regime": ["case_label", "direction", "combined_regime"],
        "by_session": ["case_label", "direction", "session_regime"],
        "by_context": ["case_label", "direction", "combined_regime", "session_regime"],
        "by_oracle_gap_bucket": ["case_label", "direction", "oracle_gap_bucket"],
        "by_holding_error_bucket": ["case_label", "direction", "holding_error_bucket"],
        "by_exit_regret_bucket": ["case_label", "direction", "exit_regret_bucket"],
    }
    summaries = {}
    for name, columns in group_sets.items():
        if all(column in diagnostics.columns for column in columns):
            summary = summarize_holding_errors(diagnostics, columns)
            summary.to_csv(run_dir / f"{name}.csv", index=False)
            summaries[name] = summary

    wf = walkforward_target_profiles(
        diagnostics,
        args.walkforward_group_columns,
        min_prior_support=args.min_prior_support,
    )
    wf.to_csv(run_dir / "walkforward_context_profiles.csv", index=False)
    corr = correlation_summary(diagnostics)
    corr.to_csv(run_dir / "correlation_summary.csv", index=False)

    metrics = {
        "mode": "holding_error_target_diagnostics",
        "trade_rows": [str(path) for path in args.trade_rows],
        "expanded_trade_paths": [str(path) for path in expand_trade_paths(args.trade_rows)],
        "pnl_source": args.pnl_source,
        "case_label": args.case_label,
        "min_abs_regret": args.min_abs_regret,
        "min_abs_gap_minutes": args.min_abs_gap_minutes,
        "rows": {
            "input_rows": int(len(rows)),
            "diagnostic_rows": int(len(diagnostics)),
            "walkforward_profiles": int(len(wf)),
        },
        "overall": {
            "total_adjusted_pnl": float(diagnostics["analysis_adjusted_pnl"].sum()),
            "avg_adjusted_pnl": float(diagnostics["analysis_adjusted_pnl"].mean()),
            "exit_shortening_rate": float(diagnostics["exit_shortening_target"].mean()),
            "hold_extension_rate": float(diagnostics["hold_extension_target"].mean()),
            "holding_mismatch_rate": float(diagnostics["holding_mismatch_target"].mean()),
            "exit_regret_mean": float(diagnostics["exit_regret"].mean()),
            "oracle_gap_mean": float(diagnostics["oracle_holding_gap_minutes"].mean()),
            "holding_error_mean": float(diagnostics["holding_error_minutes"].mean()),
        },
        "outputs": {
            "holding_error_trade_rows": str(run_dir / "holding_error_trade_rows.csv"),
            "walkforward_context_profiles": str(run_dir / "walkforward_context_profiles.csv"),
            "correlation_summary": str(run_dir / "correlation_summary.csv"),
            **{name: str(run_dir / f"{name}.csv") for name in summaries},
        },
    }
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2, default=json_default)
    print(json.dumps(metrics, ensure_ascii=False, indent=2, default=json_default))
    print("artifacts:", run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
