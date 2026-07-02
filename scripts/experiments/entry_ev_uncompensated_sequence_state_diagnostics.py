#!/usr/bin/env python3
"""Sequence-state diagnostics for uncompensated selected-trade loss targets."""

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


DEFAULT_THRESHOLDS = "0.10,0.20,0.30,0.40"
DEFAULT_QUANTILES = "0.90,0.95"
DEFAULT_GROUP_SPECS = (
    "prev_result_bucket;"
    "next_result_bucket;"
    "month_trade_count_bucket;"
    "direction,session_regime;"
    "direction,combined_regime;"
    "prev_result_bucket,next_result_bucket;"
    "prev_result_bucket,post_exit_gap_bucket;"
    "month_trade_count_bucket,prev_result_bucket"
)

MODEL_COLUMNS = [
    "supervised_target_mode",
    "large_loss_feature_set",
    "uncompensated_feature_set",
]

PATH_COLUMNS = ["source", "role", "family", "variant", "candidate", "month"]


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
    return [part.strip() for part in str(value).split(",") if part.strip()]


def parse_semicolon(value: str) -> list[str]:
    return [part.strip() for part in str(value).split(";") if part.strip()]


def parse_group_specs(value: str) -> list[list[str]]:
    return [parse_csv(part) for part in parse_semicolon(value)]


def parse_float_csv(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    series = frame[column]
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(float(default)).astype(float).ne(0.0)
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


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


def make_group_key(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    if not columns:
        return pd.Series("all", index=frame.index, dtype="string")
    available = [column for column in columns if column in frame.columns]
    if not available:
        return pd.Series("missing", index=frame.index, dtype="string")
    return frame[available].astype(str).agg("|".join, axis=1)


def normalize_predictions(
    frame: pd.DataFrame,
    *,
    target_modes: set[str],
    large_loss_feature_sets: set[str],
    uncompensated_feature_sets: set[str],
) -> pd.DataFrame:
    required = {
        *MODEL_COLUMNS,
        *PATH_COLUMNS,
        "direction",
        "entry_decision_timestamp",
        "exit_decision_timestamp",
        "adjusted_pnl",
        "uncompensated_loss_target",
        "pred_uncompensated_loss_prob",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"prediction frame missing columns: {', '.join(missing)}")

    output = frame.copy()
    for column in [*MODEL_COLUMNS, *PATH_COLUMNS, "direction", "combined_regime", "session_regime", "context_key"]:
        output[column] = text_series(output, column)
    output["month"] = output["month"].astype("string").str.slice(0, 7)
    if target_modes:
        output = output[output["supervised_target_mode"].isin(target_modes)].copy()
    if large_loss_feature_sets:
        output = output[output["large_loss_feature_set"].isin(large_loss_feature_sets)].copy()
    if uncompensated_feature_sets:
        output = output[
            output["uncompensated_feature_set"].isin(uncompensated_feature_sets)
        ].copy()
    if output.empty:
        raise ValueError("no rows remain after filters")

    for column in ["entry_decision_timestamp", "exit_decision_timestamp"]:
        output[column] = pd.to_datetime(output[column], utc=True, errors="coerce")
    for column in [
        "adjusted_pnl",
        "holding_minutes",
        "pred_uncompensated_loss_prob",
        "pred_large_loss_prob",
        "score",
        "prior_residual_pressure",
        "context_month_total_pnl",
    ]:
        output[column] = numeric_series(output, column)
    output["is_loss"] = bool_series(output, "is_loss")
    output["is_large_loss"] = bool_series(output, "is_large_loss")
    output["uncompensated_loss_target"] = bool_series(
        output,
        "uncompensated_loss_target",
    )
    return output.reset_index(drop=True)


def _bucket_count(values: pd.Series) -> pd.Series:
    return (
        pd.cut(
            values.astype(float),
            bins=[0, 1, 2, 5, 10, np.inf],
            labels=["1", "2", "3-5", "6-10", ">10"],
            include_lowest=True,
        )
        .astype("string")
        .fillna("missing")
    )


def _bucket_gap(values: pd.Series) -> pd.Series:
    return (
        pd.cut(
            values.astype(float),
            bins=[-np.inf, 15, 30, 60, 120, 240, 1440, np.inf],
            labels=["<=15", "15-30", "30-60", "60-120", "120-240", "240-1440", ">1440"],
        )
        .astype("string")
        .fillna("edge")
    )


def add_sequence_state(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    for column in ["entry_decision_timestamp", "exit_decision_timestamp"]:
        output[column] = pd.to_datetime(output[column], utc=True, errors="coerce")
    output["adjusted_pnl"] = pd.to_numeric(output["adjusted_pnl"], errors="coerce").fillna(0.0)
    output["uncompensated_loss_target"] = bool_series(
        output,
        "uncompensated_loss_target",
    )
    group_columns = [*MODEL_COLUMNS, *PATH_COLUMNS]
    output = output.sort_values([*group_columns, "entry_decision_timestamp"]).reset_index(
        drop=True
    )
    grouped = output.groupby(group_columns, dropna=False)

    output["trade_index_in_month"] = grouped.cumcount() + 1
    output["month_trade_count"] = grouped["adjusted_pnl"].transform("size")
    output["month_trade_count_bucket"] = _bucket_count(output["month_trade_count"])

    output["prev_adjusted_pnl"] = grouped["adjusted_pnl"].shift(1)
    output["next_adjusted_pnl"] = grouped["adjusted_pnl"].shift(-1)
    output["prev_direction"] = grouped["direction"].shift(1)
    output["next_direction"] = grouped["direction"].shift(-1)
    output["prev_context_key"] = grouped["context_key"].shift(1)
    output["next_context_key"] = grouped["context_key"].shift(-1)
    output["prev_exit_decision_timestamp"] = grouped["exit_decision_timestamp"].shift(1)
    output["next_entry_decision_timestamp"] = grouped["entry_decision_timestamp"].shift(-1)

    output["decision_minutes_since_prev_exit"] = (
        output["entry_decision_timestamp"] - output["prev_exit_decision_timestamp"]
    ).dt.total_seconds() / 60.0
    output["decision_minutes_until_next_entry"] = (
        output["next_entry_decision_timestamp"] - output["exit_decision_timestamp"]
    ).dt.total_seconds() / 60.0
    output["post_exit_gap_bucket"] = _bucket_gap(output["decision_minutes_since_prev_exit"])
    output["next_entry_gap_bucket"] = _bucket_gap(output["decision_minutes_until_next_entry"])

    output["same_side_as_prev"] = output["direction"].eq(output["prev_direction"]).fillna(False)
    output["same_side_as_next"] = output["direction"].eq(output["next_direction"]).fillna(False)
    output["same_context_as_prev"] = (
        output["context_key"].eq(output["prev_context_key"]).fillna(False)
    )
    output["same_context_as_next"] = (
        output["context_key"].eq(output["next_context_key"]).fillna(False)
    )
    output["prev_was_target"] = (
        grouped["uncompensated_loss_target"].shift(1).fillna(False).astype(bool)
    )
    output["next_is_target"] = (
        grouped["uncompensated_loss_target"].shift(-1).fillna(False).astype(bool)
    )

    output["prev_result_bucket"] = np.select(
        [
            output["prev_adjusted_pnl"].isna(),
            output["prev_adjusted_pnl"].lt(0.0),
            output["prev_adjusted_pnl"].ge(0.0),
        ],
        ["first", "prev_loss", "prev_win"],
        default="unknown",
    )
    output["next_result_bucket"] = np.select(
        [
            output["next_adjusted_pnl"].isna(),
            output["next_adjusted_pnl"].lt(0.0),
            output["next_adjusted_pnl"].ge(0.0),
        ],
        ["last", "next_loss", "next_win"],
        default="unknown",
    )
    output["prev_target_bucket"] = np.select(
        [
            output["prev_adjusted_pnl"].isna(),
            output["prev_was_target"].astype(bool),
            ~output["prev_was_target"].astype(bool),
        ],
        ["first", "prev_target", "prev_non_target"],
        default="unknown",
    )
    output["next_target_bucket"] = np.select(
        [
            output["next_adjusted_pnl"].isna(),
            output["next_is_target"].astype(bool),
            ~output["next_is_target"].astype(bool),
        ],
        ["last", "next_target", "next_non_target"],
        default="unknown",
    )
    return output


def summarize_frame(frame: pd.DataFrame) -> dict[str, Any]:
    pnl = frame["adjusted_pnl"].astype(float)
    targets = frame[frame["uncompensated_loss_target"].astype(bool)]
    losses = frame[pnl.lt(0.0)]
    large_losses = frame[frame["is_large_loss"].astype(bool)]
    return {
        "row_count": int(len(frame)),
        "total_pnl": float(pnl.sum()) if len(frame) else 0.0,
        "avg_pnl": float(pnl.mean()) if len(frame) else 0.0,
        "loss_count": int(len(losses)),
        "large_loss_count": int(len(large_losses)),
        "target_count": int(len(targets)),
        "target_rate": float(len(targets) / len(frame)) if len(frame) else 0.0,
        "target_pnl": float(targets["adjusted_pnl"].sum()) if len(targets) else 0.0,
        "win_pnl": float(pnl[pnl.gt(0.0)].sum()) if len(frame) else 0.0,
        "loss_pnl": float(pnl[pnl.lt(0.0)].sum()) if len(frame) else 0.0,
        "pred_uncomp_mean": float(frame["pred_uncompensated_loss_prob"].mean())
        if len(frame)
        else 0.0,
        "pred_large_loss_mean": float(frame["pred_large_loss_prob"].mean())
        if len(frame)
        else 0.0,
        "next_win_count": int(frame["next_adjusted_pnl"].fillna(0.0).gt(0.0).sum()),
        "next_win_pnl": float(
            frame.loc[frame["next_adjusted_pnl"].fillna(0.0).gt(0.0), "next_adjusted_pnl"].sum()
        )
        if len(frame)
        else 0.0,
    }


def sequence_state_summary(
    frame: pd.DataFrame,
    *,
    group_specs: list[list[str]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for group_spec in group_specs:
        output = frame.copy()
        output["sequence_group_spec"] = ",".join(group_spec) if group_spec else "all"
        output["sequence_group_key"] = make_group_key(output, group_spec)
        group_columns = [*MODEL_COLUMNS, "sequence_group_spec", "sequence_group_key"]
        for keys, group in output.groupby(group_columns, dropna=False):
            row = dict(zip(group_columns, keys))
            row.update(summarize_frame(group))
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["target_count", "target_pnl", "row_count"],
        ascending=[False, True, False],
    )


def summarize_flagged(frame: pd.DataFrame, mask: pd.Series) -> dict[str, Any]:
    flagged = frame[mask]
    targets = frame[frame["uncompensated_loss_target"].astype(bool)]
    flagged_targets = flagged[flagged["uncompensated_loss_target"].astype(bool)]
    total = summarize_frame(frame)
    flagged_pnl = float(flagged["adjusted_pnl"].sum()) if len(flagged) else 0.0
    next_win = flagged[flagged["next_adjusted_pnl"].fillna(0.0).gt(0.0)]
    prev_win = flagged[flagged["prev_adjusted_pnl"].fillna(0.0).gt(0.0)]
    return {
        "total_trade_count": total["row_count"],
        "total_pnl": total["total_pnl"],
        "target_count": total["target_count"],
        "flagged_trade_count": int(len(flagged)),
        "flagged_trade_share": float(len(flagged) / len(frame)) if len(frame) else 0.0,
        "flagged_pnl": flagged_pnl,
        "kept_pnl_if_removed": total["total_pnl"] - flagged_pnl,
        "block_delta_if_removed": -flagged_pnl,
        "flagged_target_count": int(len(flagged_targets)),
        "target_recall": float(len(flagged_targets) / len(targets)) if len(targets) else 0.0,
        "flagged_target_precision": float(len(flagged_targets) / len(flagged))
        if len(flagged)
        else 0.0,
        "flagged_next_win_count": int(len(next_win)),
        "flagged_next_win_pnl": float(next_win["next_adjusted_pnl"].sum())
        if len(next_win)
        else 0.0,
        "flagged_prev_win_count": int(len(prev_win)),
        "flagged_prev_win_pnl": float(prev_win["prev_adjusted_pnl"].sum())
        if len(prev_win)
        else 0.0,
        "flagged_same_context_next_count": int(
            flagged["same_context_as_next"].astype(bool).sum()
        )
        if len(flagged)
        else 0,
        "flagged_next_target_count": int(flagged["next_is_target"].astype(bool).sum())
        if len(flagged)
        else 0,
        "flagged_pred_uncomp_mean": float(flagged["pred_uncompensated_loss_prob"].mean())
        if len(flagged)
        else 0.0,
    }


def risk_threshold_summary(
    frame: pd.DataFrame,
    *,
    thresholds: list[float],
    quantiles: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in frame.groupby(MODEL_COLUMNS, dropna=False):
        pred = group["pred_uncompensated_loss_prob"].astype(float)
        threshold_items = [(f"prob_ge_{value:g}", value) for value in thresholds]
        for quantile in quantiles:
            threshold_items.append((f"top_q{int(quantile * 100)}", float(pred.quantile(quantile))))
        for label, threshold in threshold_items:
            row = dict(zip(MODEL_COLUMNS, keys))
            row["threshold_label"] = label
            row["threshold"] = threshold
            row.update(summarize_flagged(group, pred.ge(threshold)))
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["block_delta_if_removed", "flagged_target_count", "flagged_trade_count"],
        ascending=[False, False, False],
    )


def target_rows(frame: pd.DataFrame, *, top_n: int) -> pd.DataFrame:
    columns = [
        *MODEL_COLUMNS,
        *PATH_COLUMNS,
        "trade_index_in_month",
        "month_trade_count",
        "prev_result_bucket",
        "next_result_bucket",
        "post_exit_gap_bucket",
        "next_entry_gap_bucket",
        "direction",
        "combined_regime",
        "session_regime",
        "adjusted_pnl",
        "pred_uncompensated_loss_prob",
        "pred_large_loss_prob",
        "context_month_total_pnl",
        "prev_adjusted_pnl",
        "next_adjusted_pnl",
        "decision_minutes_since_prev_exit",
        "decision_minutes_until_next_entry",
    ]
    available = [column for column in columns if column in frame.columns]
    return (
        frame[frame["uncompensated_loss_target"].astype(bool)]
        .sort_values(["pred_uncompensated_loss_prob", "adjusted_pnl"], ascending=[False, True])
        [available]
        .head(top_n)
    )


def high_risk_rows(frame: pd.DataFrame, *, top_n: int) -> pd.DataFrame:
    columns = [
        *MODEL_COLUMNS,
        *PATH_COLUMNS,
        "trade_index_in_month",
        "month_trade_count",
        "prev_result_bucket",
        "next_result_bucket",
        "direction",
        "combined_regime",
        "session_regime",
        "adjusted_pnl",
        "uncompensated_loss_target",
        "pred_uncompensated_loss_prob",
        "pred_large_loss_prob",
        "context_month_total_pnl",
        "prev_adjusted_pnl",
        "next_adjusted_pnl",
    ]
    available = [column for column in columns if column in frame.columns]
    return frame.sort_values(
        ["pred_uncompensated_loss_prob", "adjusted_pnl"],
        ascending=[False, True],
    )[available].head(top_n)


def build_diagnostics(args: argparse.Namespace) -> Path:
    raw = pd.concat([pd.read_csv(path) for path in args.predictions], ignore_index=True)
    normalized = normalize_predictions(
        raw,
        target_modes=set(parse_csv(args.target_modes)),
        large_loss_feature_sets=set(parse_csv(args.large_loss_feature_sets)),
        uncompensated_feature_sets=set(parse_csv(args.uncompensated_feature_sets)),
    )
    enriched = add_sequence_state(normalized)
    state_summary = sequence_state_summary(
        enriched,
        group_specs=parse_group_specs(args.group_specs),
    )
    threshold_summary = risk_threshold_summary(
        enriched,
        thresholds=parse_float_csv(args.thresholds),
        quantiles=parse_float_csv(args.quantiles),
    )
    targets = target_rows(enriched, top_n=args.top_n)
    high_risk = high_risk_rows(enriched, top_n=args.top_n)

    run_dir = make_run_dir(args.output_dir, args.label)
    enriched.to_csv(run_dir / "uncompensated_sequence_state_rows.csv", index=False)
    state_summary.to_csv(run_dir / "uncompensated_sequence_state_summary.csv", index=False)
    threshold_summary.to_csv(
        run_dir / "uncompensated_sequence_risk_threshold_summary.csv",
        index=False,
    )
    targets.to_csv(run_dir / "uncompensated_sequence_target_rows.csv", index=False)
    high_risk.to_csv(run_dir / "uncompensated_sequence_high_risk_rows.csv", index=False)
    config = {
        "predictions": args.predictions,
        "target_modes": args.target_modes,
        "large_loss_feature_sets": args.large_loss_feature_sets,
        "uncompensated_feature_sets": args.uncompensated_feature_sets,
        "group_specs": args.group_specs,
        "thresholds": args.thresholds,
        "quantiles": args.quantiles,
        "note": "next_* columns are path diagnostics only and are not execution-time features",
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True, default=local_json_default),
        encoding="utf-8",
    )

    print(f"Wrote uncompensated sequence-state diagnostics to {run_dir}")
    print("\nTop sequence state summary:")
    print(state_summary.head(args.top_n).to_string(index=False))
    print("\nTop threshold summary:")
    print(threshold_summary.head(args.top_n).to_string(index=False))
    print("\nTop target rows:")
    print(targets.head(args.top_n).to_string(index=False))
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, action="append", required=True)
    parser.add_argument("--label", default="entry_ev_uncompensated_sequence_state")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--target-modes", default="factor,pnl")
    parser.add_argument("--large-loss-feature-sets", default="base,base_prior")
    parser.add_argument("--uncompensated-feature-sets", default="base,base_prior,base_risk,base_prior_risk")
    parser.add_argument("--group-specs", default=DEFAULT_GROUP_SPECS)
    parser.add_argument("--thresholds", default=DEFAULT_THRESHOLDS)
    parser.add_argument("--quantiles", default=DEFAULT_QUANTILES)
    parser.add_argument("--top-n", type=int, default=40)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
