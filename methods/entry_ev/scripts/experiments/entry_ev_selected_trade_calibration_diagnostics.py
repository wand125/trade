#!/usr/bin/env python3
"""Diagnose chronological calibration residuals for selected entry-EV trades."""

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


SCORE_COLUMNS = {
    "pnl": "pred_supervised_pnl_ev",
    "factor": "pred_supervised_factor_ev",
}

DEFAULT_GROUP_SPECS = (
    "role;source;family;direction;combined_regime;session_regime;month;"
    "role,direction;role,month;direction,combined_regime;direction,session_regime;"
    "combined_regime,session_regime;direction,combined_regime,session_regime"
)

DEFAULT_BIN_COLUMNS = (
    "score,score_raw_ev,pred_taken_ev,selected_loss_first_prob,"
    "pred_side_confidence_gap,pred_taken_entry_local_rank,train_rows,train_months"
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


def parse_group_specs(value: str) -> list[list[str]]:
    specs: list[list[str]] = []
    for raw_spec in value.split(";"):
        columns = parse_csv(raw_spec)
        if columns:
            specs.append(columns)
    return specs


def read_prediction_frames(paths: list[Path]) -> pd.DataFrame:
    if not paths:
        raise ValueError("at least one --predictions path is required")
    frames = [pd.read_csv(path) for path in paths]
    return pd.concat(frames, ignore_index=True)


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values), default).fillna(default).astype(float)


def text_series(frame: pd.DataFrame, column: str, default: str = "missing") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="string")
    return (
        frame[column]
        .astype("string")
        .fillna(default)
        .str.strip()
        .replace({"": default, "nan": default, "None": default})
    )


def normalize_predictions(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"supervised_target_mode", "adjusted_pnl"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"prediction frame missing columns: {', '.join(missing)}")

    output = frame.copy()
    output["supervised_target_mode"] = output["supervised_target_mode"].astype(str)
    output = output[output["supervised_target_mode"].isin(SCORE_COLUMNS)].copy()
    if output.empty:
        raise ValueError("no supported supervised_target_mode rows found")

    for column in [
        "source",
        "role",
        "family",
        "variant",
        "candidate",
        "month",
        "direction",
        "combined_regime",
        "session_regime",
        "trend_regime",
        "volatility_regime",
        "gap_regime",
        "selector_variant",
    ]:
        output[column] = text_series(output, column)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["direction"] = output["direction"].astype(str).str.lower()

    for column in [
        "adjusted_pnl",
        "score_raw_ev",
        "pred_taken_ev",
        "selected_loss_first_prob",
        "pred_side_confidence_gap",
        "pred_taken_entry_local_rank",
        "holding_minutes",
    ]:
        output[column] = numeric_series(output, column)

    return output.reset_index(drop=True)


def add_mode_scores(
    frame: pd.DataFrame,
    *,
    large_loss_threshold: float,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for mode, score_column in SCORE_COLUMNS.items():
        subset = frame[frame["supervised_target_mode"].eq(mode)].copy()
        if subset.empty:
            continue
        if score_column not in subset.columns:
            raise ValueError(f"missing score column for {mode}: {score_column}")
        subset["score"] = numeric_series(subset, score_column, default=np.nan)
        subset["raw_score"] = numeric_series(subset, "score_raw_ev", default=np.nan)
        subset["train_rows"] = numeric_series(
            subset,
            f"pred_supervised_{mode}_train_rows",
            default=0.0,
        )
        subset["train_months"] = numeric_series(
            subset,
            f"pred_supervised_{mode}_train_months",
            default=0.0,
        )
        model_used_column = f"pred_supervised_{mode}_model_used"
        if model_used_column in subset.columns:
            subset["model_used"] = (
                subset[model_used_column]
                .astype(str)
                .str.lower()
                .str.strip()
                .isin({"true", "1", "yes", "y"})
            )
        else:
            subset["model_used"] = False
        subset["score_error"] = subset["score"] - subset["adjusted_pnl"]
        subset["raw_score_error"] = subset["raw_score"] - subset["adjusted_pnl"]
        subset["abs_error"] = subset["score_error"].abs()
        subset["squared_error"] = subset["score_error"] ** 2
        subset["raw_abs_error"] = subset["raw_score_error"].abs()
        subset["is_loss"] = subset["adjusted_pnl"] < 0.0
        subset["is_large_loss"] = subset["adjusted_pnl"] <= large_loss_threshold
        subset["is_overestimate"] = subset["score_error"] > 0.0
        subset["overestimate_amount"] = subset["score_error"].clip(lower=0.0)
        subset["underestimate_amount"] = (-subset["score_error"]).clip(lower=0.0)
        subset["raw_overestimate_amount"] = subset["raw_score_error"].clip(lower=0.0)
        rows.append(subset)
    if not rows:
        raise ValueError("no score rows were built")
    return pd.concat(rows, ignore_index=True)


def safe_spearman(frame: pd.DataFrame) -> float:
    if len(frame) < 2:
        return float("nan")
    if frame["score"].nunique(dropna=True) < 2 or frame["adjusted_pnl"].nunique(dropna=True) < 2:
        return float("nan")
    return float(frame["score"].corr(frame["adjusted_pnl"], method="spearman"))


def summarize_frame(frame: pd.DataFrame) -> dict[str, Any]:
    valid = frame[np.isfinite(frame["score"]) & np.isfinite(frame["adjusted_pnl"])]
    losses = valid[valid["is_loss"]]
    large_losses = valid[valid["is_large_loss"]]
    rmse = float(np.sqrt(valid["squared_error"].mean())) if len(valid) else float("nan")
    raw_rmse = (
        float(np.sqrt((valid["raw_score_error"] ** 2).mean()))
        if len(valid)
        else float("nan")
    )
    return {
        "trade_count": int(len(valid)),
        "total_pnl": float(valid["adjusted_pnl"].sum()) if len(valid) else 0.0,
        "mean_actual": float(valid["adjusted_pnl"].mean()) if len(valid) else float("nan"),
        "mean_score": float(valid["score"].mean()) if len(valid) else float("nan"),
        "bias": float(valid["score_error"].mean()) if len(valid) else float("nan"),
        "mae": float(valid["abs_error"].mean()) if len(valid) else float("nan"),
        "rmse": rmse,
        "raw_bias": float(valid["raw_score_error"].mean()) if len(valid) else float("nan"),
        "raw_mae": float(valid["raw_abs_error"].mean()) if len(valid) else float("nan"),
        "raw_rmse": raw_rmse,
        "spearman": safe_spearman(valid),
        "loss_count": int(len(losses)),
        "loss_rate": float(len(losses) / len(valid)) if len(valid) else float("nan"),
        "loss_pnl": float(losses["adjusted_pnl"].sum()) if len(losses) else 0.0,
        "large_loss_count": int(len(large_losses)),
        "large_loss_pnl": float(large_losses["adjusted_pnl"].sum()) if len(large_losses) else 0.0,
        "overestimate_count": int(valid["is_overestimate"].sum()) if len(valid) else 0,
        "overestimate_rate": float(valid["is_overestimate"].mean()) if len(valid) else float("nan"),
        "overestimate_sum": float(valid["overestimate_amount"].sum()) if len(valid) else 0.0,
        "underestimate_sum": float(valid["underestimate_amount"].sum()) if len(valid) else 0.0,
        "raw_overestimate_sum": float(valid["raw_overestimate_amount"].sum()) if len(valid) else 0.0,
        "model_used_rate": float(valid["model_used"].mean()) if len(valid) else float("nan"),
        "train_rows_mean": float(valid["train_rows"].mean()) if len(valid) else float("nan"),
        "train_months_mean": float(valid["train_months"].mean()) if len(valid) else float("nan"),
    }


def summarize_groups(
    frame: pd.DataFrame,
    group_specs: list[list[str]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for columns in group_specs:
        available = [column for column in columns if column in frame.columns]
        if not available:
            continue
        group_spec = ",".join(available)
        for keys, group in frame.groupby(["supervised_target_mode", *available], dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            row: dict[str, Any] = {
                "supervised_target_mode": keys[0],
                "group_spec": group_spec,
                "group_key": "|".join(str(value) for value in keys[1:]),
            }
            for column, value in zip(available, keys[1:]):
                row[column] = value
            row.update(summarize_frame(group))
            rows.append(row)
    return pd.DataFrame(rows)


def add_quantile_bin(
    frame: pd.DataFrame,
    column: str,
    *,
    bins: int,
) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce")
    output = pd.Series("missing", index=frame.index, dtype="object")
    valid = values[np.isfinite(values)]
    if valid.empty:
        return output
    if valid.nunique(dropna=True) <= 1:
        output.loc[valid.index] = "q0"
        return output
    ranked = valid.rank(method="first")
    labels = pd.qcut(ranked, q=min(bins, len(valid)), labels=False, duplicates="drop")
    output.loc[valid.index] = labels.astype(int).map(lambda value: f"q{value}")
    return output


def add_support_bin(frame: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce")
    if column == "train_months":
        bins = [-np.inf, 0, 2, 4, 8, 12, np.inf]
        labels = ["0", "1-2", "3-4", "5-8", "9-12", "13+"]
    else:
        bins = [-np.inf, 0, 30, 60, 120, 240, np.inf]
        labels = ["0", "1-30", "31-60", "61-120", "121-240", "241+"]
    output = pd.cut(values.fillna(0.0), bins=bins, labels=labels, include_lowest=True)
    return output.astype(str)


def summarize_bins(
    frame: pd.DataFrame,
    *,
    columns: list[str],
    bins: int,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for mode, mode_frame in frame.groupby("supervised_target_mode", dropna=False):
        mode_frame = mode_frame.copy()
        for column in columns:
            if column not in mode_frame.columns:
                continue
            bin_column = f"{column}_bin"
            if column in {"train_rows", "train_months"}:
                mode_frame[bin_column] = add_support_bin(mode_frame, column)
            else:
                mode_frame[bin_column] = add_quantile_bin(mode_frame, column, bins=bins)
            summary = summarize_groups(mode_frame, [[bin_column]])
            if summary.empty:
                continue
            value_ranges = (
                mode_frame.groupby(bin_column, dropna=False)[column]
                .agg(value_min="min", value_max="max")
                .reset_index()
            )
            summary = summary.merge(
                value_ranges,
                left_on="group_key",
                right_on=bin_column,
                how="left",
            )
            summary.insert(1, "bin_source", column)
            summary = summary[summary["supervised_target_mode"].eq(mode)].copy()
            rows.append(summary)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def score_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for mode, group in frame.groupby("supervised_target_mode", dropna=False):
        row: dict[str, Any] = {"supervised_target_mode": mode}
        row.update(summarize_frame(group))
        rows.append(row)
    return pd.DataFrame(rows)


def worst_groups(
    group_summary: pd.DataFrame,
    *,
    min_trades: int,
    top_n: int,
) -> pd.DataFrame:
    if group_summary.empty:
        return group_summary
    eligible = group_summary[group_summary["trade_count"].ge(min_trades)].copy()
    if eligible.empty:
        return eligible
    eligible["positive_bias"] = eligible["bias"].clip(lower=0.0)
    eligible["overestimate_pressure"] = eligible["positive_bias"] * np.sqrt(
        eligible["trade_count"].astype(float)
    )
    eligible["negative_pnl_pressure"] = (-eligible["total_pnl"]).clip(lower=0.0)
    return eligible.sort_values(
        [
            "negative_pnl_pressure",
            "overestimate_pressure",
            "mae",
            "trade_count",
        ],
        ascending=[False, False, False, False],
    ).head(top_n)


def build_diagnostics(args: argparse.Namespace) -> Path:
    raw = read_prediction_frames(args.predictions)
    normalized = normalize_predictions(raw)
    enriched = add_mode_scores(normalized, large_loss_threshold=args.large_loss_threshold)
    group_specs = parse_group_specs(args.group_specs)
    bin_columns = parse_csv(args.bin_columns)

    run_dir = make_run_dir(args.output_dir, args.label)
    enriched.to_csv(run_dir / "selected_trade_calibration_diagnostics_predictions.csv", index=False)
    score = score_summary(enriched)
    groups = summarize_groups(enriched, group_specs)
    bins = summarize_bins(enriched, columns=bin_columns, bins=args.bins)
    worst = worst_groups(groups, min_trades=args.min_group_trades, top_n=args.top_n)
    score.to_csv(run_dir / "selected_trade_calibration_diagnostics_score_summary.csv", index=False)
    groups.to_csv(run_dir / "selected_trade_calibration_diagnostics_group_summary.csv", index=False)
    bins.to_csv(run_dir / "selected_trade_calibration_diagnostics_bin_summary.csv", index=False)
    worst.to_csv(run_dir / "selected_trade_calibration_diagnostics_worst_groups.csv", index=False)

    config = {
        "predictions": args.predictions,
        "label": args.label,
        "group_specs": args.group_specs,
        "bin_columns": args.bin_columns,
        "bins": args.bins,
        "large_loss_threshold": args.large_loss_threshold,
        "min_group_trades": args.min_group_trades,
        "top_n": args.top_n,
        "row_count": int(len(enriched)),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True, default=local_json_default),
        encoding="utf-8",
    )

    print(f"Wrote calibration diagnostics to {run_dir}")
    print("\nScore summary:")
    print(score.to_string(index=False))
    print("\nWorst groups:")
    print(worst.head(args.top_n).to_string(index=False))
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, action="append", required=True)
    parser.add_argument(
        "--label",
        default="entry_ev_selected_trade_calibration_diagnostics",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--group-specs", default=DEFAULT_GROUP_SPECS)
    parser.add_argument("--bin-columns", default=DEFAULT_BIN_COLUMNS)
    parser.add_argument("--bins", type=int, default=5)
    parser.add_argument("--large-loss-threshold", type=float, default=-2.0)
    parser.add_argument("--min-group-trades", type=int, default=3)
    parser.add_argument("--top-n", type=int, default=40)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
