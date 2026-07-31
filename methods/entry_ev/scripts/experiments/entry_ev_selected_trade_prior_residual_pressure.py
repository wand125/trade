#!/usr/bin/env python3
"""Build prior-only residual pressure diagnostics for selected entry-EV trades."""

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
for path in (SRC, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402
from entry_ev_selected_trade_calibration_diagnostics import (  # noqa: E402
    add_mode_scores,
    normalize_predictions,
    parse_group_specs,
    read_prediction_frames,
)


DEFAULT_GROUP_SPECS = (
    "direction,session_regime;"
    "direction,combined_regime;"
    "combined_regime,session_regime;"
    "direction,combined_regime,session_regime"
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


def make_group_key(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    if not columns:
        return pd.Series("all", index=frame.index, dtype="string")
    return frame[columns].astype(str).agg("|".join, axis=1)


def _zero_prior_columns(frame: pd.DataFrame) -> None:
    for column in [
        "prior_trade_count",
        "prior_month_count",
        "prior_total_pnl",
        "prior_loss_count",
        "prior_large_loss_count",
        "prior_score_error_sum",
        "prior_abs_error_sum",
        "prior_overestimate_count",
        "prior_overestimate_sum",
    ]:
        frame[column] = 0.0


def _safe_rate(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    output = pd.Series(np.nan, index=numerator.index, dtype=float)
    mask = denominator.astype(float).gt(0.0)
    output.loc[mask] = numerator.loc[mask].astype(float) / denominator.loc[mask].astype(float)
    return output


def add_prior_stats_for_group_spec(
    frame: pd.DataFrame,
    *,
    group_columns: list[str],
    large_loss_threshold: float,
) -> pd.DataFrame:
    available = [column for column in group_columns if column in frame.columns]
    output = frame.copy()
    output["group_spec"] = ",".join(available) if available else "all"
    output["group_key"] = make_group_key(output, available)
    _zero_prior_columns(output)

    groupby_columns = ["supervised_target_mode", "group_key"]
    for _, group in output.groupby(groupby_columns, sort=False, dropna=False):
        months = sorted(group["month"].astype(str).unique())
        prior = {
            "trade_count": 0.0,
            "month_count": 0.0,
            "total_pnl": 0.0,
            "loss_count": 0.0,
            "large_loss_count": 0.0,
            "score_error_sum": 0.0,
            "abs_error_sum": 0.0,
            "overestimate_count": 0.0,
            "overestimate_sum": 0.0,
        }
        for month in months:
            idx = group.index[group["month"].astype(str).eq(month)]
            output.loc[idx, "prior_trade_count"] = prior["trade_count"]
            output.loc[idx, "prior_month_count"] = prior["month_count"]
            output.loc[idx, "prior_total_pnl"] = prior["total_pnl"]
            output.loc[idx, "prior_loss_count"] = prior["loss_count"]
            output.loc[idx, "prior_large_loss_count"] = prior["large_loss_count"]
            output.loc[idx, "prior_score_error_sum"] = prior["score_error_sum"]
            output.loc[idx, "prior_abs_error_sum"] = prior["abs_error_sum"]
            output.loc[idx, "prior_overestimate_count"] = prior["overestimate_count"]
            output.loc[idx, "prior_overestimate_sum"] = prior["overestimate_sum"]

            current = output.loc[idx]
            prior["trade_count"] += float(len(current))
            prior["month_count"] += 1.0
            prior["total_pnl"] += float(current["adjusted_pnl"].astype(float).sum())
            prior["loss_count"] += float(current["is_loss"].fillna(False).astype(bool).sum())
            prior["large_loss_count"] += float(
                current["is_large_loss"].fillna(False).astype(bool).sum()
            )
            prior["score_error_sum"] += float(current["score_error"].astype(float).sum())
            prior["abs_error_sum"] += float(current["abs_error"].astype(float).sum())
            prior["overestimate_count"] += float(
                current["is_overestimate"].fillna(False).astype(bool).sum()
            )
            prior["overestimate_sum"] += float(
                current["overestimate_amount"].astype(float).sum()
            )

    count = output["prior_trade_count"].astype(float)
    output["prior_avg_pnl"] = _safe_rate(output["prior_total_pnl"], count)
    output["prior_loss_rate"] = _safe_rate(output["prior_loss_count"], count)
    output["prior_large_loss_rate"] = _safe_rate(output["prior_large_loss_count"], count)
    output["prior_bias_mean"] = _safe_rate(output["prior_score_error_sum"], count)
    output["prior_mae_mean"] = _safe_rate(output["prior_abs_error_sum"], count)
    output["prior_overestimate_rate"] = _safe_rate(output["prior_overestimate_count"], count)
    output["prior_overestimate_mean"] = _safe_rate(output["prior_overestimate_sum"], count)

    positive_bias = output["prior_bias_mean"].fillna(0.0).clip(lower=0.0)
    negative_avg_pnl = (-output["prior_avg_pnl"].fillna(0.0)).clip(lower=0.0)
    large_loss_component = (
        output["prior_large_loss_rate"].fillna(0.0).clip(lower=0.0)
        * abs(float(large_loss_threshold))
    )
    output["prior_residual_pressure"] = (
        positive_bias + negative_avg_pnl + large_loss_component
    ) * np.log1p(count)
    return output


def build_prior_pressure_rows(
    frame: pd.DataFrame,
    *,
    group_specs: list[list[str]],
    large_loss_threshold: float,
) -> pd.DataFrame:
    rows = [
        add_prior_stats_for_group_spec(
            frame,
            group_columns=group_columns,
            large_loss_threshold=large_loss_threshold,
        )
        for group_columns in group_specs
    ]
    if not rows:
        raise ValueError("at least one group spec is required")
    return pd.concat(rows, ignore_index=True)


def build_rule_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    count = frame["prior_trade_count"].astype(float)
    bias = frame["prior_bias_mean"].fillna(0.0).astype(float)
    total = frame["prior_total_pnl"].fillna(0.0).astype(float)
    loss_rate = frame["prior_loss_rate"].fillna(0.0).astype(float)
    large_loss_rate = frame["prior_large_loss_rate"].fillna(0.0).astype(float)
    pressure = frame["prior_residual_pressure"].fillna(0.0).astype(float)
    return {
        "prior_count_ge3_total_neg": count.ge(3.0) & total.lt(0.0),
        "prior_count_ge3_bias_ge0p5": count.ge(3.0) & bias.ge(0.5),
        "prior_count_ge3_bias_ge1": count.ge(3.0) & bias.ge(1.0),
        "prior_count_ge3_lossrate_ge0p5": count.ge(3.0) & loss_rate.ge(0.5),
        "prior_count_ge3_largelossrate_ge0p2": count.ge(3.0) & large_loss_rate.ge(0.2),
        "prior_count_ge5_total_neg_bias_pos": count.ge(5.0) & total.lt(0.0) & bias.gt(0.0),
        "prior_count_ge5_lossrate_ge0p5_bias_pos": count.ge(5.0)
        & loss_rate.ge(0.5)
        & bias.gt(0.0),
        "prior_count_ge10_total_neg": count.ge(10.0) & total.lt(0.0),
        "prior_count_ge3_pressure_ge2": count.ge(3.0) & pressure.ge(2.0),
        "prior_count_ge5_pressure_ge4": count.ge(5.0) & pressure.ge(4.0),
    }


def summarize_rule_frame(frame: pd.DataFrame, mask: pd.Series) -> dict[str, Any]:
    flagged = frame[mask]
    losses = frame[frame["is_loss"].fillna(False).astype(bool)]
    large_losses = frame[frame["is_large_loss"].fillna(False).astype(bool)]
    flagged_losses = flagged[flagged["is_loss"].fillna(False).astype(bool)]
    flagged_large_losses = flagged[flagged["is_large_loss"].fillna(False).astype(bool)]
    total_pnl = float(frame["adjusted_pnl"].astype(float).sum()) if len(frame) else 0.0
    flagged_pnl = float(flagged["adjusted_pnl"].astype(float).sum()) if len(flagged) else 0.0
    return {
        "total_trade_count": int(len(frame)),
        "total_pnl": total_pnl,
        "loss_trade_count": int(len(losses)),
        "large_loss_trade_count": int(len(large_losses)),
        "flagged_trade_count": int(len(flagged)),
        "flagged_trade_share": float(len(flagged) / len(frame)) if len(frame) else 0.0,
        "flagged_pnl": flagged_pnl,
        "kept_pnl_if_removed": total_pnl - flagged_pnl,
        "block_delta_if_removed": -flagged_pnl,
        "flagged_loss_count": int(len(flagged_losses)),
        "flagged_loss_precision": float(len(flagged_losses) / len(flagged))
        if len(flagged)
        else 0.0,
        "loss_recall": float(len(flagged_losses) / len(losses)) if len(losses) else 0.0,
        "flagged_large_loss_count": int(len(flagged_large_losses)),
        "large_loss_recall": float(len(flagged_large_losses) / len(large_losses))
        if len(large_losses)
        else 0.0,
        "flagged_prior_count_mean": float(flagged["prior_trade_count"].mean())
        if len(flagged)
        else 0.0,
        "flagged_prior_pressure_mean": float(flagged["prior_residual_pressure"].mean())
        if len(flagged)
        else 0.0,
    }


def summarize_rules(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = ["supervised_target_mode", "group_spec"]
    for keys, group in frame.groupby(group_columns, dropna=False):
        mode, group_spec = keys
        masks = build_rule_masks(group)
        for rule_name, mask in masks.items():
            row: dict[str, Any] = {
                "supervised_target_mode": mode,
                "group_spec": group_spec,
                "rule": rule_name,
            }
            row.update(summarize_rule_frame(group, mask))
            rows.append(row)
    return pd.DataFrame(rows).sort_values(
        [
            "block_delta_if_removed",
            "flagged_large_loss_count",
            "flagged_trade_count",
        ],
        ascending=[False, False, False],
    )


def summarize_pressure_bins(frame: pd.DataFrame, *, bins: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in frame.groupby(["supervised_target_mode", "group_spec"], dropna=False):
        mode, group_spec = keys
        group = group.copy()
        valid = group["prior_residual_pressure"].replace([np.inf, -np.inf], np.nan).dropna()
        if valid.empty or valid.nunique() <= 1:
            group["pressure_bin"] = "q0"
        else:
            labels = pd.qcut(
                valid.rank(method="first"),
                q=min(bins, len(valid)),
                labels=False,
                duplicates="drop",
            )
            group["pressure_bin"] = "missing"
            group.loc[valid.index, "pressure_bin"] = labels.astype(int).map(
                lambda value: f"q{value}"
            )
        for bin_name, bin_group in group.groupby("pressure_bin", dropna=False):
            row: dict[str, Any] = {
                "supervised_target_mode": mode,
                "group_spec": group_spec,
                "pressure_bin": bin_name,
                "pressure_min": float(bin_group["prior_residual_pressure"].min()),
                "pressure_max": float(bin_group["prior_residual_pressure"].max()),
            }
            row.update(summarize_rule_frame(bin_group, pd.Series(True, index=bin_group.index)))
            rows.append(row)
    return pd.DataFrame(rows)


def worst_prior_context_rows(frame: pd.DataFrame, *, top_n: int) -> pd.DataFrame:
    columns = [
        "supervised_target_mode",
        "group_spec",
        "group_key",
        "month",
        "role",
        "direction",
        "combined_regime",
        "session_regime",
        "adjusted_pnl",
        "score",
        "score_error",
        "is_loss",
        "is_large_loss",
        "prior_trade_count",
        "prior_month_count",
        "prior_total_pnl",
        "prior_avg_pnl",
        "prior_bias_mean",
        "prior_loss_rate",
        "prior_large_loss_rate",
        "prior_residual_pressure",
    ]
    available = [column for column in columns if column in frame.columns]
    return frame.sort_values(
        ["prior_residual_pressure", "prior_trade_count", "adjusted_pnl"],
        ascending=[False, False, True],
    )[available].head(top_n)


def build_diagnostics(args: argparse.Namespace) -> Path:
    raw = read_prediction_frames(args.predictions)
    normalized = normalize_predictions(raw)
    scored = add_mode_scores(normalized, large_loss_threshold=args.large_loss_threshold)
    rows = build_prior_pressure_rows(
        scored,
        group_specs=parse_group_specs(args.group_specs),
        large_loss_threshold=args.large_loss_threshold,
    )
    rule_summary = summarize_rules(rows)
    pressure_bins = summarize_pressure_bins(rows, bins=args.bins)
    worst_rows = worst_prior_context_rows(rows, top_n=args.top_n)

    run_dir = make_run_dir(args.output_dir, args.label)
    rows.to_csv(run_dir / "selected_trade_prior_residual_pressure_rows.csv", index=False)
    rule_summary.to_csv(
        run_dir / "selected_trade_prior_residual_pressure_rule_summary.csv",
        index=False,
    )
    pressure_bins.to_csv(
        run_dir / "selected_trade_prior_residual_pressure_bin_summary.csv",
        index=False,
    )
    worst_rows.to_csv(
        run_dir / "selected_trade_prior_residual_pressure_worst_rows.csv",
        index=False,
    )
    config = {
        "predictions": args.predictions,
        "label": args.label,
        "group_specs": args.group_specs,
        "large_loss_threshold": args.large_loss_threshold,
        "bins": args.bins,
        "top_n": args.top_n,
        "row_count": int(len(rows)),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True, default=local_json_default),
        encoding="utf-8",
    )

    print(f"Wrote prior residual pressure diagnostics to {run_dir}")
    print("\nTop rule summary:")
    print(rule_summary.head(args.top_n).to_string(index=False))
    print("\nWorst prior context rows:")
    print(worst_rows.head(args.top_n).to_string(index=False))
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, action="append", required=True)
    parser.add_argument(
        "--label",
        default="entry_ev_selected_trade_prior_residual_pressure",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--group-specs", default=DEFAULT_GROUP_SPECS)
    parser.add_argument("--large-loss-threshold", type=float, default=-2.0)
    parser.add_argument("--bins", type=int, default=5)
    parser.add_argument("--top-n", type=int, default=40)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
