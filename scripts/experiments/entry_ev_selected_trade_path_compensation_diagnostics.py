#!/usr/bin/env python3
"""Path-aware compensation diagnostics for selected entry-EV large-loss risk."""

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
for path in (SRC,):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


DEFAULT_THRESHOLDS = "0.20,0.30,0.40"
DEFAULT_QUANTILES = "0.90,0.95"
DEFAULT_CONTEXT_COLUMNS = "direction,combined_regime,session_regime"


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


def parse_float_csv(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


def read_frames(paths: list[Path]) -> pd.DataFrame:
    if not paths:
        raise ValueError("at least one --predictions path is required")
    return pd.concat([pd.read_csv(path) for path in paths], ignore_index=True)


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values), default).fillna(default).astype(float)


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


def normalize_predictions(
    frame: pd.DataFrame,
    *,
    target_modes: set[str],
    group_specs: set[str],
    feature_sets: set[str],
    context_columns: list[str],
) -> pd.DataFrame:
    required = {
        "supervised_target_mode",
        "group_spec",
        "large_loss_feature_set",
        "month",
        "adjusted_pnl",
        "is_large_loss",
        "pred_large_loss_prob",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"prediction frame missing columns: {', '.join(missing)}")

    output = frame.copy()
    output["supervised_target_mode"] = text_series(output, "supervised_target_mode")
    output["group_spec"] = text_series(output, "group_spec")
    output["large_loss_feature_set"] = text_series(output, "large_loss_feature_set")
    output["month"] = text_series(output, "month").str.slice(0, 7)

    if target_modes:
        output = output[output["supervised_target_mode"].isin(target_modes)].copy()
    if group_specs:
        output = output[output["group_spec"].isin(group_specs)].copy()
    if feature_sets:
        output = output[output["large_loss_feature_set"].isin(feature_sets)].copy()
    if output.empty:
        raise ValueError("no rows remain after filters")

    for column in [
        "role",
        "source",
        "family",
        "variant",
        "candidate",
        "direction",
        "combined_regime",
        "session_regime",
        "group_key",
        *context_columns,
    ]:
        output[column] = text_series(output, column)
    for column in ["adjusted_pnl", "pred_large_loss_prob", "score", "prior_residual_pressure"]:
        output[column] = numeric_series(output, column)
    output["is_loss"] = bool_series(output, "is_loss")
    output["is_large_loss"] = bool_series(output, "is_large_loss")
    return output.reset_index(drop=True)


def make_context_key(frame: pd.DataFrame, context_columns: list[str]) -> pd.Series:
    if not context_columns:
        return pd.Series("all", index=frame.index, dtype="string")
    available = [column for column in context_columns if column in frame.columns]
    if not available:
        return pd.Series("all", index=frame.index, dtype="string")
    return frame[available].astype(str).agg("|".join, axis=1)


def _sum_positive(values: pd.Series) -> float:
    numeric = values.astype(float)
    return float(numeric[numeric.gt(0.0)].sum())


def _sum_negative(values: pd.Series) -> float:
    numeric = values.astype(float)
    return float(numeric[numeric.lt(0.0)].sum())


def add_context_month_stats(
    frame: pd.DataFrame,
    *,
    context_columns: list[str],
    large_win_threshold: float,
) -> pd.DataFrame:
    output = frame.copy()
    output["context_key"] = make_context_key(output, context_columns)
    group_columns = [
        "supervised_target_mode",
        "group_spec",
        "large_loss_feature_set",
        "month",
        "context_key",
    ]
    agg = (
        output.groupby(group_columns, dropna=False)
        .agg(
            context_month_trade_count=("adjusted_pnl", "size"),
            context_month_total_pnl=("adjusted_pnl", "sum"),
            context_month_win_count=("adjusted_pnl", lambda values: int((values > 0).sum())),
            context_month_loss_count=("adjusted_pnl", lambda values: int((values < 0).sum())),
            context_month_large_loss_count=(
                "is_large_loss",
                lambda values: int(values.astype(bool).sum()),
            ),
            context_month_win_pnl=("adjusted_pnl", _sum_positive),
            context_month_loss_pnl=("adjusted_pnl", _sum_negative),
            context_month_max_win=("adjusted_pnl", "max"),
            context_month_min_pnl=("adjusted_pnl", "min"),
            context_month_pred_risk_mean=("pred_large_loss_prob", "mean"),
            context_month_pred_risk_max=("pred_large_loss_prob", "max"),
        )
        .reset_index()
    )
    output = output.merge(agg, on=group_columns, how="left", validate="many_to_one")
    output["context_month_id"] = output[group_columns].astype(str).agg("||".join, axis=1)
    output["context_month_net_positive"] = output["context_month_total_pnl"].gt(0.0)
    output["context_month_has_large_win"] = output["context_month_max_win"].ge(
        float(large_win_threshold)
    )
    output["large_loss_compensated_by_context"] = output["is_large_loss"] & output[
        "context_month_net_positive"
    ]
    output["large_loss_compensated_with_large_win"] = (
        output["large_loss_compensated_by_context"]
        & output["context_month_has_large_win"]
    )
    output["large_loss_uncompensated_by_context"] = output["is_large_loss"] & ~output[
        "context_month_net_positive"
    ]
    return output


def context_month_summary(frame: pd.DataFrame) -> pd.DataFrame:
    group_columns = [
        "supervised_target_mode",
        "group_spec",
        "large_loss_feature_set",
        "month",
        "context_key",
    ]
    rows = (
        frame.groupby(group_columns, dropna=False)
        .agg(
            trade_count=("adjusted_pnl", "size"),
            total_pnl=("adjusted_pnl", "sum"),
            win_count=("adjusted_pnl", lambda values: int((values > 0).sum())),
            loss_count=("adjusted_pnl", lambda values: int((values < 0).sum())),
            large_loss_count=("is_large_loss", lambda values: int(values.astype(bool).sum())),
            compensated_large_loss_count=(
                "large_loss_compensated_by_context",
                lambda values: int(values.astype(bool).sum()),
            ),
            uncompensated_large_loss_count=(
                "large_loss_uncompensated_by_context",
                lambda values: int(values.astype(bool).sum()),
            ),
            win_pnl=("adjusted_pnl", _sum_positive),
            loss_pnl=("adjusted_pnl", _sum_negative),
            max_win=("adjusted_pnl", "max"),
            min_pnl=("adjusted_pnl", "min"),
            pred_risk_mean=("pred_large_loss_prob", "mean"),
            pred_risk_max=("pred_large_loss_prob", "max"),
            has_large_win=("context_month_has_large_win", "first"),
        )
        .reset_index()
    )
    rows["net_positive"] = rows["total_pnl"].gt(0.0)
    return rows.sort_values(
        ["large_loss_count", "total_pnl", "pred_risk_max"],
        ascending=[False, True, False],
    )


def large_loss_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = ["supervised_target_mode", "group_spec", "large_loss_feature_set"]
    for keys, group in frame.groupby(group_columns, dropna=False):
        mode, group_spec, feature_set = keys
        large_losses = group[group["is_large_loss"].astype(bool)]
        compensated = large_losses[large_losses["large_loss_compensated_by_context"]]
        uncompensated = large_losses[large_losses["large_loss_uncompensated_by_context"]]
        large_loss_contexts = large_losses.drop_duplicates("context_month_id")
        positive_contexts = large_loss_contexts[
            large_loss_contexts["context_month_net_positive"]
        ]
        rows.append(
            {
                "supervised_target_mode": mode,
                "group_spec": group_spec,
                "feature_set": feature_set,
                "trade_count": int(len(group)),
                "total_pnl": float(group["adjusted_pnl"].sum()),
                "loss_count": int(group["is_loss"].astype(bool).sum()),
                "large_loss_count": int(len(large_losses)),
                "large_loss_pnl": float(large_losses["adjusted_pnl"].sum()),
                "compensated_large_loss_count": int(len(compensated)),
                "compensated_large_loss_share": float(len(compensated) / len(large_losses))
                if len(large_losses)
                else 0.0,
                "compensated_large_loss_pnl": float(compensated["adjusted_pnl"].sum()),
                "uncompensated_large_loss_count": int(len(uncompensated)),
                "uncompensated_large_loss_pnl": float(uncompensated["adjusted_pnl"].sum()),
                "large_loss_context_month_count": int(len(large_loss_contexts)),
                "large_loss_positive_context_month_count": int(len(positive_contexts)),
                "large_loss_positive_context_month_share": float(
                    len(positive_contexts) / len(large_loss_contexts)
                )
                if len(large_loss_contexts)
                else 0.0,
                "large_loss_context_month_total_pnl": float(
                    large_loss_contexts["context_month_total_pnl"].sum()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["compensated_large_loss_share", "total_pnl"],
        ascending=[False, False],
    )


def summarize_flagged(frame: pd.DataFrame, mask: pd.Series) -> dict[str, Any]:
    flagged = frame[mask]
    total_pnl = float(frame["adjusted_pnl"].sum()) if len(frame) else 0.0
    flagged_pnl = float(flagged["adjusted_pnl"].sum()) if len(flagged) else 0.0
    large_losses = frame[frame["is_large_loss"].astype(bool)]
    flagged_large_losses = flagged[flagged["is_large_loss"].astype(bool)]
    flagged_contexts = flagged.drop_duplicates("context_month_id")
    positive_contexts = flagged_contexts[
        flagged_contexts["context_month_net_positive"]
    ]
    negative_contexts = flagged_contexts[
        ~flagged_contexts["context_month_net_positive"]
    ]
    compensated_large = flagged_large_losses[
        flagged_large_losses["large_loss_compensated_by_context"]
    ]
    uncompensated_large = flagged_large_losses[
        flagged_large_losses["large_loss_uncompensated_by_context"]
    ]
    return {
        "total_trade_count": int(len(frame)),
        "total_pnl": total_pnl,
        "large_loss_count": int(len(large_losses)),
        "flagged_trade_count": int(len(flagged)),
        "flagged_trade_share": float(len(flagged) / len(frame)) if len(frame) else 0.0,
        "flagged_pnl": flagged_pnl,
        "kept_pnl_if_removed": total_pnl - flagged_pnl,
        "block_delta_if_removed": -flagged_pnl,
        "flagged_large_loss_count": int(len(flagged_large_losses)),
        "large_loss_recall": float(len(flagged_large_losses) / len(large_losses))
        if len(large_losses)
        else 0.0,
        "flagged_compensated_large_loss_count": int(len(compensated_large)),
        "flagged_uncompensated_large_loss_count": int(len(uncompensated_large)),
        "flagged_compensated_large_loss_share": float(
            len(compensated_large) / len(flagged_large_losses)
        )
        if len(flagged_large_losses)
        else 0.0,
        "flagged_context_month_count": int(len(flagged_contexts)),
        "flagged_positive_context_month_count": int(len(positive_contexts)),
        "flagged_negative_context_month_count": int(len(negative_contexts)),
        "flagged_positive_context_month_share": float(
            len(positive_contexts) / len(flagged_contexts)
        )
        if len(flagged_contexts)
        else 0.0,
        "flagged_context_month_total_pnl": float(
            flagged_contexts["context_month_total_pnl"].sum()
        )
        if len(flagged_contexts)
        else 0.0,
        "flagged_positive_context_month_total_pnl": float(
            positive_contexts["context_month_total_pnl"].sum()
        )
        if len(positive_contexts)
        else 0.0,
        "flagged_negative_context_month_total_pnl": float(
            negative_contexts["context_month_total_pnl"].sum()
        )
        if len(negative_contexts)
        else 0.0,
        "flagged_large_win_context_month_count": int(
            flagged_contexts["context_month_has_large_win"].astype(bool).sum()
        )
        if len(flagged_contexts)
        else 0,
        "flagged_pred_mean": float(flagged["pred_large_loss_prob"].mean())
        if len(flagged)
        else 0.0,
    }


def threshold_summary(
    frame: pd.DataFrame,
    *,
    thresholds: list[float],
    quantiles: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = ["supervised_target_mode", "group_spec", "large_loss_feature_set"]
    for keys, group in frame.groupby(group_columns, dropna=False):
        mode, group_spec, feature_set = keys
        pred = group["pred_large_loss_prob"].astype(float)
        threshold_items = [(f"prob_ge_{value:g}", value) for value in thresholds]
        for quantile in quantiles:
            threshold_items.append((f"top_q{int(quantile * 100)}", float(pred.quantile(quantile))))
        for label, threshold in threshold_items:
            mask = pred.ge(threshold)
            row: dict[str, Any] = {
                "supervised_target_mode": mode,
                "group_spec": group_spec,
                "feature_set": feature_set,
                "threshold_label": label,
                "threshold": threshold,
            }
            row.update(summarize_flagged(group, mask))
            rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["block_delta_if_removed", "flagged_large_loss_count", "flagged_trade_count"],
        ascending=[False, False, False],
    )


def worst_rows(frame: pd.DataFrame, *, top_n: int) -> pd.DataFrame:
    columns = [
        "supervised_target_mode",
        "group_spec",
        "large_loss_feature_set",
        "month",
        "role",
        "direction",
        "combined_regime",
        "session_regime",
        "context_key",
        "adjusted_pnl",
        "is_large_loss",
        "pred_large_loss_prob",
        "context_month_trade_count",
        "context_month_total_pnl",
        "context_month_win_pnl",
        "context_month_loss_pnl",
        "context_month_max_win",
        "context_month_net_positive",
        "large_loss_compensated_by_context",
        "score",
        "prior_residual_pressure",
    ]
    available = [column for column in columns if column in frame.columns]
    return frame.sort_values(
        ["pred_large_loss_prob", "adjusted_pnl"],
        ascending=[False, True],
    )[available].head(top_n)


def build_diagnostics(args: argparse.Namespace) -> Path:
    context_columns = parse_csv(args.context_columns)
    raw = read_frames(args.predictions)
    normalized = normalize_predictions(
        raw,
        target_modes=set(parse_csv(args.target_modes)),
        group_specs=set(parse_semicolon(args.group_specs)),
        feature_sets=set(parse_csv(args.feature_sets)),
        context_columns=context_columns,
    )
    enriched = add_context_month_stats(
        normalized,
        context_columns=context_columns,
        large_win_threshold=args.large_win_threshold,
    )
    context_summary = context_month_summary(enriched)
    loss_summary = large_loss_summary(enriched)
    risk_summary = threshold_summary(
        enriched,
        thresholds=parse_float_csv(args.thresholds),
        quantiles=parse_float_csv(args.quantiles),
    )
    worst = worst_rows(enriched, top_n=args.top_n)

    run_dir = make_run_dir(args.output_dir, args.label)
    enriched.to_csv(run_dir / "selected_trade_path_compensation_rows.csv", index=False)
    context_summary.to_csv(run_dir / "path_compensation_context_month_summary.csv", index=False)
    loss_summary.to_csv(run_dir / "path_compensation_large_loss_summary.csv", index=False)
    risk_summary.to_csv(run_dir / "path_compensation_risk_threshold_summary.csv", index=False)
    worst.to_csv(run_dir / "path_compensation_worst_rows.csv", index=False)
    config = {
        "predictions": args.predictions,
        "target_modes": args.target_modes,
        "group_specs": args.group_specs,
        "feature_sets": args.feature_sets,
        "context_columns": context_columns,
        "large_win_threshold": args.large_win_threshold,
        "thresholds": args.thresholds,
        "quantiles": args.quantiles,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True, default=local_json_default),
        encoding="utf-8",
    )

    print(f"Wrote path compensation diagnostics to {run_dir}")
    print("\nLarge-loss compensation summary:")
    print(loss_summary.to_string(index=False))
    print("\nTop risk threshold summary:")
    print(risk_summary.head(args.top_n).to_string(index=False))
    print("\nTop predicted risk rows:")
    print(worst.head(args.top_n).to_string(index=False))
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, action="append", required=True)
    parser.add_argument("--label", default="entry_ev_selected_trade_path_compensation")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--target-modes", default="factor,pnl")
    parser.add_argument("--group-specs", default="direction,combined_regime,session_regime")
    parser.add_argument("--feature-sets", default="base,base_prior")
    parser.add_argument("--context-columns", default=DEFAULT_CONTEXT_COLUMNS)
    parser.add_argument("--large-win-threshold", type=float, default=5.0)
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
