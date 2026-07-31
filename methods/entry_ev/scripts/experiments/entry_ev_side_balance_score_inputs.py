#!/usr/bin/env python3
"""Apply prior-only side-balance score penalties to entry-EV prediction files."""

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
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402

from entry_ev_dense_executable_capture_model import side_target_column  # noqa: E402
from entry_ev_executable_ev_policy_inputs import (  # noqa: E402
    add_executable_quantile_columns,
)
from entry_ev_scale_quantile_diagnostics import month_series  # noqa: E402


DEFAULT_LONG_OUTPUT_COLUMN = "pred_side_balanced_dense_executable_long_best_adjusted_pnl"
DEFAULT_SHORT_OUTPUT_COLUMN = "pred_side_balanced_dense_executable_short_best_adjusted_pnl"
DEFAULT_SCORE_KIND = "side_balanced_dense_executable"
DEFAULT_QUANTILE_SCOPES = "month,side_month,side_regime_session_month"
CONTEXT_COLUMNS = ["combined_regime", "session_regime"]


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


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def numeric_or_nan(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values))


def required_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise ValueError(f"predictions missing required column: {column}")
    return numeric_or_nan(frame, column)


def prediction_balance_rows(
    predictions: pd.DataFrame,
    *,
    family: str,
    long_column: str,
    short_column: str,
    target_mode: str,
    min_target_edge: float,
) -> pd.DataFrame:
    long_score = required_numeric(predictions, long_column)
    short_score = required_numeric(predictions, short_column)
    target_long = required_numeric(predictions, side_target_column("long", target_mode))
    target_short = required_numeric(predictions, side_target_column("short", target_mode))
    target_score = np.maximum(target_long, target_short)
    target_valid = target_score > min_target_edge
    target_long_side = target_long >= target_short
    pred_long_side = long_score >= short_score

    return pd.DataFrame(
        {
            "family": family,
            "_row_id": np.arange(len(predictions), dtype=int),
            "month": month_series(predictions).astype(str).str.slice(0, 7),
            "combined_regime": predictions.get(
                "combined_regime",
                pd.Series("__missing__", index=predictions.index),
            )
            .astype(str)
            .fillna("__missing__")
            .to_numpy(),
            "session_regime": predictions.get(
                "session_regime",
                pd.Series("__missing__", index=predictions.index),
            )
            .astype(str)
            .fillna("__missing__")
            .to_numpy(),
            "pred_long_side": pred_long_side.astype(float).to_numpy(),
            "target_long_side": target_long_side.astype(float).to_numpy(),
            "target_valid": target_valid.astype(bool).to_numpy(),
        }
    )


def side_share_stats(frame: pd.DataFrame, *, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        columns = [
            *group_columns,
            "prior_count",
            "prior_month_count",
            "prior_pred_long_share",
            "prior_target_long_share",
            "prior_long_share_drift",
        ]
        return pd.DataFrame(columns=columns)
    if not group_columns:
        return pd.DataFrame(
            [
                {
                    "prior_count": int(len(frame)),
                    "prior_month_count": int(frame["month"].nunique()),
                    "prior_pred_long_share": float(frame["pred_long_side"].mean()),
                    "prior_target_long_share": float(frame["target_long_side"].mean()),
                    "prior_long_share_drift": float(
                        frame["pred_long_side"].mean()
                        - frame["target_long_side"].mean()
                    ),
                }
            ]
        )
    grouped = (
        frame.groupby(group_columns, dropna=False)
        .agg(
            prior_count=("pred_long_side", "size"),
            prior_month_count=("month", "nunique"),
            prior_pred_long_share=("pred_long_side", "mean"),
            prior_target_long_share=("target_long_side", "mean"),
        )
        .reset_index()
    )
    grouped["prior_long_share_drift"] = (
        grouped["prior_pred_long_share"] - grouped["prior_target_long_share"]
    )
    return grouped


def build_prior_stats(
    rows: pd.DataFrame,
    *,
    target_months: list[str],
    min_prior_months: int,
    recent_month_count: int,
    context_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    global_frames: list[pd.DataFrame] = []
    context_frames: list[pd.DataFrame] = []
    valid_rows = rows[rows["target_valid"].astype(bool)].copy()
    valid_periods = pd.PeriodIndex(valid_rows["month"].astype(str), freq="M")

    for month in target_months:
        target_period = pd.Period(month, freq="M")
        mask = valid_periods < target_period
        if recent_month_count > 0:
            mask &= valid_periods >= (target_period - recent_month_count)
        prior = valid_rows[mask].copy()
        if prior.empty or int(prior["month"].nunique()) < min_prior_months:
            continue

        global_stats = side_share_stats(prior, group_columns=[]).assign(target_month=month)
        global_frames.append(global_stats)
        if context_columns:
            context_stats = side_share_stats(prior, group_columns=context_columns)
            context_stats["target_month"] = month
            context_frames.append(context_stats)

    global_frame = (
        pd.concat(global_frames, ignore_index=True) if global_frames else pd.DataFrame()
    )
    context_frame = (
        pd.concat(context_frames, ignore_index=True) if context_frames else pd.DataFrame()
    )
    return global_frame, context_frame


def balance_lookup(
    predictions: pd.DataFrame,
    *,
    global_stats: pd.DataFrame,
    context_stats: pd.DataFrame,
    context_columns: list[str],
    support_scale: float,
    penalty_strength: float,
    min_side_scale: float,
) -> pd.DataFrame:
    if support_scale <= 0:
        raise ValueError("support_scale must be positive")
    if not 0 < min_side_scale <= 1:
        raise ValueError("min_side_scale must be in (0, 1]")
    lookup = pd.DataFrame(
        {
            "_row_id": np.arange(len(predictions), dtype=int),
            "target_month": month_series(predictions).astype(str).str.slice(0, 7),
        }
    )
    for column in context_columns:
        lookup[column] = predictions.get(
            column,
            pd.Series("__missing__", index=predictions.index),
        ).astype(str).fillna("__missing__").to_numpy()

    if global_stats.empty:
        merged = lookup.copy()
    else:
        merged = lookup.merge(global_stats, how="left", on="target_month")
    if context_columns and not context_stats.empty:
        merged = merged.merge(
            context_stats,
            how="left",
            on=["target_month", *context_columns],
            suffixes=("_global", "_context"),
        )
    merged = merged.sort_values("_row_id").reset_index(drop=True)

    for prefix in ["global", "context"]:
        if f"prior_count_{prefix}" not in merged.columns:
            merged[f"prior_count_{prefix}"] = np.nan
        if f"prior_long_share_drift_{prefix}" not in merged.columns:
            merged[f"prior_long_share_drift_{prefix}"] = np.nan
        if f"prior_pred_long_share_{prefix}" not in merged.columns:
            merged[f"prior_pred_long_share_{prefix}"] = np.nan
        if f"prior_target_long_share_{prefix}" not in merged.columns:
            merged[f"prior_target_long_share_{prefix}"] = np.nan

    if "prior_count" in merged.columns:
        global_count = pd.to_numeric(merged["prior_count"], errors="coerce").fillna(0.0)
        global_drift = pd.to_numeric(
            merged["prior_long_share_drift"],
            errors="coerce",
        ).fillna(0.0)
        global_pred_share = pd.to_numeric(
            merged["prior_pred_long_share"],
            errors="coerce",
        )
        global_target_share = pd.to_numeric(
            merged["prior_target_long_share"],
            errors="coerce",
        )
    else:
        global_count = pd.to_numeric(
            merged["prior_count_global"],
            errors="coerce",
        ).fillna(0.0)
        global_drift = pd.to_numeric(
            merged["prior_long_share_drift_global"],
            errors="coerce",
        ).fillna(0.0)
        global_pred_share = pd.to_numeric(
            merged["prior_pred_long_share_global"],
            errors="coerce",
        )
        global_target_share = pd.to_numeric(
            merged["prior_target_long_share_global"],
            errors="coerce",
        )

    context_count = pd.to_numeric(
        merged["prior_count_context"],
        errors="coerce",
    ).fillna(0.0)
    context_drift = pd.to_numeric(
        merged["prior_long_share_drift_context"],
        errors="coerce",
    ).fillna(global_drift)
    support_weight = np.clip(context_count / support_scale, 0.0, 1.0)
    drift = (1.0 - support_weight) * global_drift + support_weight * context_drift

    long_scale = (1.0 - penalty_strength * drift.clip(lower=0.0)).clip(
        lower=min_side_scale,
        upper=1.0,
    )
    short_scale = (1.0 - penalty_strength * (-drift).clip(lower=0.0)).clip(
        lower=min_side_scale,
        upper=1.0,
    )

    return pd.DataFrame(
        {
            "pred_side_balance_prior_count": global_count.astype(float),
            "pred_side_balance_context_count": context_count.astype(float),
            "pred_side_balance_context_support_weight": support_weight.astype(float),
            "pred_side_balance_prior_pred_long_share": global_pred_share.astype(float),
            "pred_side_balance_prior_target_long_share": global_target_share.astype(float),
            "pred_side_balance_long_share_drift": drift.astype(float),
            "pred_side_balance_long_scale": long_scale.astype(float),
            "pred_side_balance_short_scale": short_scale.astype(float),
        },
        index=predictions.index,
    )


def add_side_balance_scores(
    family_frames: dict[str, pd.DataFrame],
    *,
    rows: pd.DataFrame,
    target_mode: str,
    long_column: str,
    short_column: str,
    long_output_column: str,
    short_output_column: str,
    score_kind: str,
    long_rank_column: str,
    short_rank_column: str,
    quantile_scopes: list[str],
    min_prior_months: int,
    recent_month_count: int,
    context_columns: list[str],
    support_scale: float,
    penalty_strength: float,
    min_side_scale: float,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    target_months = sorted(rows["month"].dropna().astype(str).unique())
    global_stats, context_stats = build_prior_stats(
        rows,
        target_months=target_months,
        min_prior_months=min_prior_months,
        recent_month_count=recent_month_count,
        context_columns=context_columns,
    )
    outputs: dict[str, pd.DataFrame] = {}
    for family, predictions in family_frames.items():
        output = predictions.copy()
        lookup = balance_lookup(
            output,
            global_stats=global_stats,
            context_stats=context_stats,
            context_columns=context_columns,
            support_scale=support_scale,
            penalty_strength=penalty_strength,
            min_side_scale=min_side_scale,
        )
        for column in lookup.columns:
            output[column] = lookup[column].to_numpy()
        output[long_output_column] = (
            pd.to_numeric(output[long_column], errors="coerce")
            * output["pred_side_balance_long_scale"]
        )
        output[short_output_column] = (
            pd.to_numeric(output[short_column], errors="coerce")
            * output["pred_side_balance_short_scale"]
        )
        output = add_executable_quantile_columns(
            output,
            family=family,
            score_kind=score_kind,
            long_output_column=long_output_column,
            short_output_column=short_output_column,
            long_rank_column=long_rank_column,
            short_rank_column=short_rank_column,
            quantile_scopes=quantile_scopes,
        )
        outputs[family] = output
    return outputs, global_stats, context_stats


def summarize_effect(
    outputs: dict[str, pd.DataFrame],
    *,
    long_column: str,
    short_column: str,
    long_output_column: str,
    short_output_column: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for family, frame in outputs.items():
        months = month_series(frame).astype(str).str.slice(0, 7)
        base_long = pd.to_numeric(frame[long_column], errors="coerce")
        base_short = pd.to_numeric(frame[short_column], errors="coerce")
        balanced_long = pd.to_numeric(frame[long_output_column], errors="coerce")
        balanced_short = pd.to_numeric(frame[short_output_column], errors="coerce")
        base_side = np.where(base_long >= base_short, 1, -1)
        balanced_side = np.where(balanced_long >= balanced_short, 1, -1)
        summary = pd.DataFrame(
            {
                "month": months,
                "base_side": base_side,
                "balanced_side": balanced_side,
                "base_score": np.where(base_side == 1, base_long, base_short),
                "balanced_score": np.where(
                    balanced_side == 1,
                    balanced_long,
                    balanced_short,
                ),
                "long_scale": frame["pred_side_balance_long_scale"].astype(float),
                "short_scale": frame["pred_side_balance_short_scale"].astype(float),
                "drift": frame["pred_side_balance_long_share_drift"].astype(float),
                "prior_count": frame["pred_side_balance_prior_count"].astype(float),
            }
        )
        for month, group in summary.groupby("month", dropna=False):
            rows.append(
                {
                    "family": family,
                    "month": month,
                    "row_count": int(len(group)),
                    "base_selected_long_share": float(group["base_side"].eq(1).mean()),
                    "balanced_selected_long_share": float(
                        group["balanced_side"].eq(1).mean()
                    ),
                    "side_switch_share": float(
                        (group["base_side"] != group["balanced_side"]).mean()
                    ),
                    "base_score_q95": float(group["base_score"].quantile(0.95)),
                    "balanced_score_q95": float(group["balanced_score"].quantile(0.95)),
                    "long_scale_mean": float(group["long_scale"].mean()),
                    "short_scale_mean": float(group["short_scale"].mean()),
                    "drift_mean": float(group["drift"].mean()),
                    "prior_count_mean": float(group["prior_count"].mean()),
                }
            )
    return pd.DataFrame(rows).sort_values(["family", "month"]).reset_index(drop=True)


def run_side_balance(args: argparse.Namespace) -> Path:
    family_paths = parse_family_predictions(args.family_predictions)
    quantile_scopes = parse_csv(args.quantile_scopes)
    context_columns = parse_csv(args.context_columns)
    run_dir = make_run_dir(args.output_dir, args.label)
    prediction_dir = run_dir / "enriched_predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)

    family_frames: dict[str, pd.DataFrame] = {}
    row_frames: list[pd.DataFrame] = []
    for family, path in family_paths.items():
        frame = pd.read_parquet(path)
        family_frames[family] = frame
        row_frames.append(
            prediction_balance_rows(
                frame,
                family=family,
                long_column=args.long_column,
                short_column=args.short_column,
                target_mode=args.target_mode,
                min_target_edge=args.min_target_edge,
            )
        )
    rows = pd.concat(row_frames, ignore_index=True)
    outputs, global_stats, context_stats = add_side_balance_scores(
        family_frames,
        rows=rows,
        target_mode=args.target_mode,
        long_column=args.long_column,
        short_column=args.short_column,
        long_output_column=args.long_output_column,
        short_output_column=args.short_output_column,
        score_kind=args.score_kind,
        long_rank_column=args.long_rank_column,
        short_rank_column=args.short_rank_column,
        quantile_scopes=quantile_scopes,
        min_prior_months=args.min_prior_months,
        recent_month_count=args.recent_month_count,
        context_columns=context_columns,
        support_scale=args.support_scale,
        penalty_strength=args.penalty_strength,
        min_side_scale=args.min_side_scale,
    )

    output_paths: dict[str, Path] = {}
    for family, frame in outputs.items():
        path = prediction_dir / f"{family}_predictions_side_balanced.parquet"
        frame.to_parquet(path, index=False)
        output_paths[family] = path

    global_stats.to_csv(run_dir / "side_balance_global_stats.csv", index=False)
    context_stats.to_csv(run_dir / "side_balance_context_stats.csv", index=False)
    effect = summarize_effect(
        outputs,
        long_column=args.long_column,
        short_column=args.short_column,
        long_output_column=args.long_output_column,
        short_output_column=args.short_output_column,
    )
    effect.to_csv(run_dir / "prediction_side_balance_effect_summary.csv", index=False)

    config = {
        "family_predictions": family_paths,
        "output_paths": output_paths,
        "target_mode": args.target_mode,
        "score_kind": args.score_kind,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_output_column": args.long_output_column,
        "short_output_column": args.short_output_column,
        "long_rank_column": args.long_rank_column,
        "short_rank_column": args.short_rank_column,
        "quantile_scopes": quantile_scopes,
        "min_target_edge": args.min_target_edge,
        "min_prior_months": args.min_prior_months,
        "recent_month_count": args.recent_month_count,
        "context_columns": context_columns,
        "support_scale": args.support_scale,
        "penalty_strength": args.penalty_strength,
        "min_side_scale": args.min_side_scale,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Side-balance prediction effect:")
    print(
        effect[
            [
                "family",
                "month",
                "base_selected_long_share",
                "balanced_selected_long_share",
                "side_switch_share",
                "base_score_q95",
                "balanced_score_q95",
                "long_scale_mean",
                "short_scale_mean",
                "drift_mean",
            ]
        ].to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--target-mode", default="fixed_720m")
    parser.add_argument("--score-kind", default=DEFAULT_SCORE_KIND)
    parser.add_argument("--long-column", default="pred_dense_executable_long_best_adjusted_pnl")
    parser.add_argument("--short-column", default="pred_dense_executable_short_best_adjusted_pnl")
    parser.add_argument("--long-output-column", default=DEFAULT_LONG_OUTPUT_COLUMN)
    parser.add_argument("--short-output-column", default=DEFAULT_SHORT_OUTPUT_COLUMN)
    parser.add_argument("--long-rank-column", default="pred_long_entry_local_rank")
    parser.add_argument("--short-rank-column", default="pred_short_entry_local_rank")
    parser.add_argument("--quantile-scopes", default=DEFAULT_QUANTILE_SCOPES)
    parser.add_argument("--context-columns", default="combined_regime,session_regime")
    parser.add_argument("--min-target-edge", type=float, default=0.0)
    parser.add_argument("--min-prior-months", type=int, default=1)
    parser.add_argument("--recent-month-count", type=int, default=0)
    parser.add_argument("--support-scale", type=float, default=5000.0)
    parser.add_argument("--penalty-strength", type=float, default=1.0)
    parser.add_argument("--min-side-scale", type=float, default=0.2)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_side_balance_score_inputs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_side_balance(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
