#!/usr/bin/env python3
"""Diagnose entry-EV admission filters directly on prediction rows."""

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


SUMMARY_QUANTILES = (0.5, 0.9, 0.95, 0.99)
BASE_PRINT_COLUMNS = [
    "family",
    "month",
    "row_count",
    "valid_prediction_count",
    "selected_long_count",
    "selected_short_count",
    "selected_long_share",
    "long_ev_q95",
    "short_ev_q95",
    "long_ev_max",
    "short_ev_max",
    "long_holding_ok_count",
    "short_holding_ok_count",
]
CONFIG_PRINT_COLUMNS = [
    "family",
    "entry_threshold",
    "short_entry_threshold_offset",
    "min_entry_rank",
    "valid_prediction_count",
    "stateless_enter_count",
    "stateless_long_enter_count",
    "stateless_short_enter_count",
    "threshold_ok_count",
    "side_margin_ok_count",
    "rank_ok_count",
    "selected_holding_ok_count",
    "long_ev_above_long_threshold_count",
    "short_ev_above_short_threshold_count",
    "min_monthly_enter_count",
    "max_monthly_enter_count",
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


def parse_family_predictions(values: list[str]) -> dict[str, Path]:
    families: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError(
                "family predictions must use family=path"
            )
        family, path = value.split("=", 1)
        family = family.strip()
        if not family:
            raise argparse.ArgumentTypeError("family name must not be empty")
        families[family] = Path(path.strip())
    if not families:
        raise argparse.ArgumentTypeError("at least one family prediction is required")
    return families


def parse_float_csv(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def month_series(frame: pd.DataFrame) -> pd.Series:
    if "dataset_month" in frame.columns:
        return frame["dataset_month"].astype(str).str.slice(0, 7)
    if "month" in frame.columns:
        return frame["month"].astype(str).str.slice(0, 7)
    if "timestamp" in frame.columns:
        return pd.to_datetime(frame["timestamp"], utc=True).dt.strftime("%Y-%m")
    if "decision_timestamp" in frame.columns:
        return pd.to_datetime(frame["decision_timestamp"], utc=True).dt.strftime(
            "%Y-%m"
        )
    raise ValueError("prediction frame needs dataset_month, month, or timestamp")


def finite_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise ValueError(f"missing prediction column: {column}")
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values))


def quantile_summary(values: pd.Series, prefix: str) -> dict[str, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {
            f"{prefix}_q{int(q * 100):02d}": np.nan for q in SUMMARY_QUANTILES
        } | {f"{prefix}_max": np.nan, f"{prefix}_mean": np.nan}
    result = {
        f"{prefix}_q{int(q * 100):02d}": float(clean.quantile(q))
        for q in SUMMARY_QUANTILES
    }
    result[f"{prefix}_max"] = float(clean.max())
    result[f"{prefix}_mean"] = float(clean.mean())
    return result


def add_base_columns(
    frame: pd.DataFrame,
    *,
    family: str,
    long_column: str,
    short_column: str,
    long_rank_column: str,
    short_rank_column: str,
    long_holding_column: str,
    short_holding_column: str,
    min_valid_predicted_hold_minutes: float,
) -> pd.DataFrame:
    result = frame.copy()
    result["family"] = family
    result["month"] = month_series(result)
    result["long_ev"] = finite_numeric(result, long_column)
    result["short_ev"] = finite_numeric(result, short_column)
    result["long_rank"] = finite_numeric(result, long_rank_column)
    result["short_rank"] = finite_numeric(result, short_rank_column)
    result["long_holding"] = finite_numeric(result, long_holding_column)
    result["short_holding"] = finite_numeric(result, short_holding_column)
    result["valid_prediction"] = result["long_ev"].notna() & result["short_ev"].notna()
    result["selected_side"] = np.where(result["long_ev"] >= result["short_ev"], 1, -1)
    result.loc[~result["valid_prediction"], "selected_side"] = 0
    result["selected_score"] = np.where(
        result["selected_side"].eq(1),
        result["long_ev"],
        result["short_ev"],
    )
    result["selected_rank"] = np.where(
        result["selected_side"].eq(1),
        result["long_rank"],
        result["short_rank"],
    )
    result["selected_holding"] = np.where(
        result["selected_side"].eq(1),
        result["long_holding"],
        result["short_holding"],
    )
    result["side_gap"] = (result["long_ev"] - result["short_ev"]).abs()
    result["long_holding_ok"] = result["long_holding"].notna() & (
        result["long_holding"] >= min_valid_predicted_hold_minutes
    )
    result["short_holding_ok"] = result["short_holding"].notna() & (
        result["short_holding"] >= min_valid_predicted_hold_minutes
    )
    result["selected_holding_ok"] = np.where(
        result["selected_side"].eq(1),
        result["long_holding_ok"],
        result["short_holding_ok"],
    )
    return result


def summarize_base_group(group: pd.DataFrame) -> dict[str, object]:
    row_count = int(len(group))
    valid = group["valid_prediction"].fillna(False)
    long_selected = group["selected_side"].eq(1)
    short_selected = group["selected_side"].eq(-1)
    result: dict[str, object] = {
        "row_count": row_count,
        "valid_prediction_count": int(valid.sum()),
        "selected_long_count": int((valid & long_selected).sum()),
        "selected_short_count": int((valid & short_selected).sum()),
        "selected_long_share": float((valid & long_selected).sum() / valid.sum())
        if valid.sum()
        else 0.0,
        "long_holding_ok_count": int(group["long_holding_ok"].fillna(False).sum()),
        "short_holding_ok_count": int(group["short_holding_ok"].fillna(False).sum()),
    }
    for column, prefix in [
        ("long_ev", "long_ev"),
        ("short_ev", "short_ev"),
        ("side_gap", "side_gap"),
        ("long_rank", "long_rank"),
        ("short_rank", "short_rank"),
        ("long_holding", "long_holding"),
        ("short_holding", "short_holding"),
    ]:
        result.update(quantile_summary(group[column], prefix))
    return result


def summarize_config_group(
    group: pd.DataFrame,
    *,
    entry_threshold: float,
    short_entry_threshold_offset: float,
    min_entry_rank: float,
    side_margin: float,
) -> dict[str, object]:
    long_threshold = entry_threshold
    short_threshold = entry_threshold + short_entry_threshold_offset
    selected_threshold = np.where(
        group["selected_side"].eq(1),
        long_threshold,
        short_threshold,
    )
    valid = group["valid_prediction"].fillna(False)
    side_margin_ok = group["side_gap"] >= side_margin
    selected_holding_ok = group["selected_holding_ok"].fillna(False)
    rank_ok = (
        pd.Series(True, index=group.index)
        if min_entry_rank <= 0
        else group["selected_rank"].notna() & (group["selected_rank"] >= min_entry_rank)
    )
    threshold_ok = group["selected_score"] > selected_threshold
    stateless_enter = (
        valid & side_margin_ok & selected_holding_ok & rank_ok & threshold_ok
    )
    long_threshold_ok = group["long_ev"] > long_threshold
    short_threshold_ok = group["short_ev"] > short_threshold
    result: dict[str, object] = {
        "entry_threshold": entry_threshold,
        "short_entry_threshold_offset": short_entry_threshold_offset,
        "short_threshold": short_threshold,
        "min_entry_rank": min_entry_rank,
        "side_margin": side_margin,
        "valid_prediction_count": int(valid.sum()),
        "selected_holding_ok_count": int((valid & selected_holding_ok).sum()),
        "side_margin_ok_count": int((valid & side_margin_ok).sum()),
        "rank_ok_count": int((valid & rank_ok).sum()),
        "threshold_ok_count": int((valid & threshold_ok).sum()),
        "long_ev_above_long_threshold_count": int((valid & long_threshold_ok).sum()),
        "short_ev_above_short_threshold_count": int((valid & short_threshold_ok).sum()),
        "stateless_enter_count": int(stateless_enter.sum()),
        "stateless_long_enter_count": int(
            (stateless_enter & group["selected_side"].eq(1)).sum()
        ),
        "stateless_short_enter_count": int(
            (stateless_enter & group["selected_side"].eq(-1)).sum()
        ),
        "stateless_enter_share": float(stateless_enter.sum() / valid.sum())
        if valid.sum()
        else 0.0,
    }
    enter_scores = group.loc[stateless_enter, "selected_score"]
    enter_ranks = group.loc[stateless_enter, "selected_rank"]
    result.update(quantile_summary(enter_scores, "enter_selected_score"))
    result.update(quantile_summary(enter_ranks, "enter_selected_rank"))
    return result


def build_diagnostics(
    family_frames: dict[str, pd.DataFrame],
    *,
    entry_thresholds: list[float],
    short_entry_threshold_offsets: list[float],
    min_entry_ranks: list[float],
    side_margin: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    base_rows: list[dict[str, object]] = []
    config_rows: list[dict[str, object]] = []
    for family, frame in family_frames.items():
        for month, group in frame.groupby("month", dropna=False):
            base_rows.append(
                {
                    "family": family,
                    "month": month,
                    **summarize_base_group(group),
                }
            )
            for entry_threshold in entry_thresholds:
                for short_offset in short_entry_threshold_offsets:
                    for min_rank in min_entry_ranks:
                        config_rows.append(
                            {
                                "family": family,
                                "month": month,
                                **summarize_config_group(
                                    group,
                                    entry_threshold=entry_threshold,
                                    short_entry_threshold_offset=short_offset,
                                    min_entry_rank=min_rank,
                                    side_margin=side_margin,
                                ),
                            }
                        )
    base = pd.DataFrame(base_rows).sort_values(["family", "month"]).reset_index(drop=True)
    config = pd.DataFrame(config_rows).sort_values(
        [
            "family",
            "month",
            "entry_threshold",
            "short_entry_threshold_offset",
            "min_entry_rank",
        ]
    ).reset_index(drop=True)
    return base, config


def aggregate_config_summary(config: pd.DataFrame) -> pd.DataFrame:
    grouped = config.groupby(
        ["family", "entry_threshold", "short_entry_threshold_offset", "min_entry_rank"],
        dropna=False,
    )
    rows: list[dict[str, object]] = []
    for keys, group in grouped:
        family, entry_threshold, short_offset, min_rank = keys
        rows.append(
            {
                "family": family,
                "entry_threshold": entry_threshold,
                "short_entry_threshold_offset": short_offset,
                "min_entry_rank": min_rank,
                "months": ",".join(sorted(group["month"].astype(str).unique())),
                "month_count": int(group["month"].nunique()),
                "valid_prediction_count": int(group["valid_prediction_count"].sum()),
                "stateless_enter_count": int(group["stateless_enter_count"].sum()),
                "stateless_long_enter_count": int(
                    group["stateless_long_enter_count"].sum()
                ),
                "stateless_short_enter_count": int(
                    group["stateless_short_enter_count"].sum()
                ),
                "stateless_enter_share": float(
                    group["stateless_enter_count"].sum()
                    / group["valid_prediction_count"].sum()
                )
                if group["valid_prediction_count"].sum()
                else 0.0,
                "min_monthly_enter_count": int(group["stateless_enter_count"].min()),
                "max_monthly_enter_count": int(group["stateless_enter_count"].max()),
                "threshold_ok_count": int(group["threshold_ok_count"].sum()),
                "side_margin_ok_count": int(group["side_margin_ok_count"].sum()),
                "rank_ok_count": int(group["rank_ok_count"].sum()),
                "selected_holding_ok_count": int(
                    group["selected_holding_ok_count"].sum()
                ),
                "short_ev_above_short_threshold_count": int(
                    group["short_ev_above_short_threshold_count"].sum()
                ),
                "long_ev_above_long_threshold_count": int(
                    group["long_ev_above_long_threshold_count"].sum()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["family", "stateless_enter_count"],
        ascending=[True, False],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--entry-thresholds", default="8,10,12,14")
    parser.add_argument("--short-entry-threshold-offsets", default="3,6,9")
    parser.add_argument("--min-entry-ranks", default="0,0.5,0.6,0.7,0.8,0.9")
    parser.add_argument("--side-margin", type=float, default=5.0)
    parser.add_argument("--min-valid-predicted-hold-minutes", type=float, default=30.0)
    parser.add_argument(
        "--long-column",
        default="pred_calibrated_long_best_adjusted_pnl",
    )
    parser.add_argument(
        "--short-column",
        default="pred_calibrated_short_best_adjusted_pnl",
    )
    parser.add_argument("--long-rank-column", default="pred_long_entry_local_rank")
    parser.add_argument("--short-rank-column", default="pred_short_entry_local_rank")
    parser.add_argument(
        "--long-holding-column",
        default="pred_mlp_long_exit_event_minutes",
    )
    parser.add_argument(
        "--short-holding-column",
        default="pred_mlp_short_exit_event_minutes",
    )
    parser.add_argument("--label", default="entry_ev_admission_input_diagnostics")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    families = parse_family_predictions(args.family_predictions)
    family_frames: dict[str, pd.DataFrame] = {}
    for family, path in families.items():
        raw = pd.read_parquet(path)
        family_frames[family] = add_base_columns(
            raw,
            family=family,
            long_column=args.long_column,
            short_column=args.short_column,
            long_rank_column=args.long_rank_column,
            short_rank_column=args.short_rank_column,
            long_holding_column=args.long_holding_column,
            short_holding_column=args.short_holding_column,
            min_valid_predicted_hold_minutes=args.min_valid_predicted_hold_minutes,
        )
    base, config = build_diagnostics(
        family_frames,
        entry_thresholds=parse_float_csv(args.entry_thresholds),
        short_entry_threshold_offsets=parse_float_csv(args.short_entry_threshold_offsets),
        min_entry_ranks=parse_float_csv(args.min_entry_ranks),
        side_margin=args.side_margin,
    )
    family_config = aggregate_config_summary(config)

    run_dir = make_run_dir(args.output_dir, args.label)
    base.to_csv(run_dir / "monthly_base_summary.csv", index=False)
    config.to_csv(run_dir / "monthly_config_summary.csv", index=False)
    family_config.to_csv(run_dir / "family_config_summary.csv", index=False)
    manifest = {
        "mode": "entry_ev_admission_input_diagnostics",
        "families": {family: str(path) for family, path in families.items()},
        "entry_thresholds": parse_float_csv(args.entry_thresholds),
        "short_entry_threshold_offsets": parse_float_csv(
            args.short_entry_threshold_offsets
        ),
        "min_entry_ranks": parse_float_csv(args.min_entry_ranks),
        "side_margin": args.side_margin,
        "min_valid_predicted_hold_minutes": args.min_valid_predicted_hold_minutes,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_rank_column": args.long_rank_column,
        "short_rank_column": args.short_rank_column,
        "long_holding_column": args.long_holding_column,
        "short_holding_column": args.short_holding_column,
    }
    (run_dir / "diagnostics.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    print(f"artifacts: {run_dir}")
    print(base[BASE_PRINT_COLUMNS].to_string(index=False))
    print(family_config[CONFIG_PRINT_COLUMNS].head(20).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
