#!/usr/bin/env python3
"""Build fixed60 prior-uncertainty soft-margin score columns."""

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

from entry_ev_executable_ev_policy_inputs import (  # noqa: E402
    add_executable_quantile_columns,
)
from entry_ev_scale_quantile_diagnostics import month_series, parse_scope_csv  # noqa: E402
from entry_ev_supervised_shrinkage_policy_inputs import (  # noqa: E402
    parse_csv,
    parse_family_predictions,
)


DEFAULT_GROUP_SPECS = (
    "direction,combined_regime,session_regime;"
    "family,direction,combined_regime,session_regime"
)
DEFAULT_WEIGHTS = "0.5,1,2,5"
DEFAULT_SCORE_KIND_PREFIX = "fixed60_uncertainty_margin"
DEFAULT_QUANTILE_SCOPES = "month,side_month,side_regime_session_month"
DEFAULT_RISK_MODE = "fp_rate_times_positive_fixed_pred"

PRIOR_VALUE_COLUMNS = [
    "prior_trade_count",
    "prior_month_count",
    "prior_adjusted_pnl_sum",
    "prior_adjusted_loss_count",
    "prior_fixed_pred_positive_count",
    "prior_fixed_actual_negative_count",
    "prior_fixed_false_positive_count",
    "prior_adjusted_pnl_mean",
    "prior_adjusted_loss_rate",
    "prior_fixed_false_positive_trade_rate",
    "prior_fixed_false_positive_rate",
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


def parse_float_csv(value: str) -> list[float]:
    values = [float(part) for part in parse_csv(value)]
    if not values:
        raise argparse.ArgumentTypeError("at least one weight is required")
    return values


def parse_group_specs(value: str) -> list[list[str]]:
    specs = [parse_csv(part) for part in value.split(";")]
    specs = [spec for spec in specs if spec]
    if not specs:
        raise argparse.ArgumentTypeError("at least one group spec is required")
    return specs


def group_spec_label(group_columns: list[str]) -> str:
    aliases = {
        "family": "fam",
        "role": "role",
        "direction": "dir",
        "combined_regime": "reg",
        "session_regime": "sess",
    }
    return "".join(aliases.get(column, column.replace("_", "")) for column in group_columns)


def weight_label(value: float) -> str:
    return f"{value:g}".replace("-", "neg").replace(".", "p")


def score_kind_for_margin(prefix: str, group_columns: list[str], weight: float) -> str:
    return f"{prefix}_{group_spec_label(group_columns)}_w{weight_label(weight)}"


def margin_output_columns(score_kind: str) -> tuple[str, str]:
    return (
        f"pred_{score_kind}_long_best_adjusted_pnl",
        f"pred_{score_kind}_short_best_adjusted_pnl",
    )


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    values = frame[column]
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(values):
        return values.fillna(float(default)).astype(float).ne(0.0)
    return values.astype(str).str.lower().str.strip().isin({"true", "1", "yes", "y"})


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


def make_group_key(frame: pd.DataFrame, group_columns: list[str]) -> pd.Series:
    if not group_columns:
        return pd.Series("all", index=frame.index, dtype="string")
    return frame[group_columns].astype(str).agg("|".join, axis=1)


def read_trade_rows(paths: list[Path]) -> pd.DataFrame:
    if not paths:
        raise ValueError("at least one --trade-rows path is required")
    return pd.concat([pd.read_csv(path) for path in paths], ignore_index=True)


def normalize_trade_rows(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"month", "direction", "adjusted_pnl"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"trade rows missing columns: {', '.join(missing)}")
    output = frame.copy()
    for column in [
        "family",
        "role",
        "direction",
        "combined_regime",
        "session_regime",
    ]:
        output[column] = text_series(output, column)
    output["direction"] = output["direction"].astype(str).str.lower()
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl", default=0.0)
    output["is_loss"] = bool_series(output, "is_loss") | output["adjusted_pnl"].lt(0.0)
    if "fixed_false_positive" in output.columns:
        output["fixed_false_positive"] = bool_series(output, "fixed_false_positive")
    else:
        required_fixed = {"fixed_pred_pnl", "fixed_actual_pnl"}
        missing_fixed = sorted(required_fixed - set(output.columns))
        if missing_fixed:
            raise ValueError(
                "trade rows need fixed_false_positive or fixed_pred_pnl/fixed_actual_pnl"
            )
        output["fixed_false_positive"] = numeric_series(output, "fixed_pred_pnl").gt(
            0.0
        ) & numeric_series(output, "fixed_actual_pnl").lt(0.0)
    if "fixed_pred_positive" in output.columns:
        output["fixed_pred_positive"] = bool_series(output, "fixed_pred_positive")
    elif "fixed_pred_pnl" in output.columns:
        output["fixed_pred_positive"] = numeric_series(output, "fixed_pred_pnl").gt(0.0)
    else:
        output["fixed_pred_positive"] = output["fixed_false_positive"].astype(bool)
    if "fixed_actual_negative" in output.columns:
        output["fixed_actual_negative"] = bool_series(output, "fixed_actual_negative")
    elif "fixed_actual_pnl" in output.columns:
        output["fixed_actual_negative"] = numeric_series(output, "fixed_actual_pnl").lt(0.0)
    else:
        output["fixed_actual_negative"] = output["fixed_false_positive"].astype(bool)
    return output.reset_index(drop=True)


def initialize_prior_row(
    *,
    group_spec: str,
    group_key: str,
    month: str,
    prior: dict[str, float],
) -> dict[str, Any]:
    count = prior["trade_count"]
    pred_positive = prior["fixed_pred_positive_count"]
    return {
        "group_spec": group_spec,
        "group_key": group_key,
        "month": month,
        "prior_trade_count": count,
        "prior_month_count": prior["month_count"],
        "prior_adjusted_pnl_sum": prior["adjusted_pnl_sum"],
        "prior_adjusted_loss_count": prior["adjusted_loss_count"],
        "prior_fixed_pred_positive_count": pred_positive,
        "prior_fixed_actual_negative_count": prior["fixed_actual_negative_count"],
        "prior_fixed_false_positive_count": prior["fixed_false_positive_count"],
        "prior_adjusted_pnl_mean": prior["adjusted_pnl_sum"] / count
        if count > 0
        else np.nan,
        "prior_adjusted_loss_rate": prior["adjusted_loss_count"] / count
        if count > 0
        else np.nan,
        "prior_fixed_false_positive_trade_rate": (
            prior["fixed_false_positive_count"] / count if count > 0 else np.nan
        ),
        "prior_fixed_false_positive_rate": (
            prior["fixed_false_positive_count"] / pred_positive
            if pred_positive > 0
            else np.nan
        ),
    }


def build_prior_table_for_group_spec(
    trades: pd.DataFrame,
    *,
    group_columns: list[str],
    months: list[str],
) -> pd.DataFrame:
    missing = sorted(set(group_columns) - set(trades.columns))
    if missing:
        raise ValueError(f"trade rows missing group columns: {', '.join(missing)}")
    working = trades.copy()
    group_spec = ",".join(group_columns) if group_columns else "all"
    working["group_key"] = make_group_key(working, group_columns)
    all_months = sorted(set(months) | set(working["month"].astype(str).unique()))
    rows: list[dict[str, Any]] = []
    for group_key, group in working.groupby("group_key", dropna=False, sort=False):
        prior = {
            "trade_count": 0.0,
            "month_count": 0.0,
            "adjusted_pnl_sum": 0.0,
            "adjusted_loss_count": 0.0,
            "fixed_pred_positive_count": 0.0,
            "fixed_actual_negative_count": 0.0,
            "fixed_false_positive_count": 0.0,
        }
        for month in all_months:
            if month in months:
                rows.append(
                    initialize_prior_row(
                        group_spec=group_spec,
                        group_key=str(group_key),
                        month=month,
                        prior=prior,
                    )
                )
            current = group[group["month"].astype(str).eq(month)]
            if current.empty:
                continue
            prior["trade_count"] += float(len(current))
            prior["month_count"] += 1.0
            prior["adjusted_pnl_sum"] += float(current["adjusted_pnl"].sum())
            prior["adjusted_loss_count"] += float(current["is_loss"].astype(bool).sum())
            prior["fixed_pred_positive_count"] += float(
                current["fixed_pred_positive"].astype(bool).sum()
            )
            prior["fixed_actual_negative_count"] += float(
                current["fixed_actual_negative"].astype(bool).sum()
            )
            prior["fixed_false_positive_count"] += float(
                current["fixed_false_positive"].astype(bool).sum()
            )
    if not rows:
        return pd.DataFrame(columns=["group_spec", "group_key", "month", *PRIOR_VALUE_COLUMNS])
    return pd.DataFrame(rows)


def prepare_predictions(predictions: pd.DataFrame, *, family: str) -> pd.DataFrame:
    output = predictions.copy()
    output["family"] = text_series(output, "family", default=family)
    output["family"] = output["family"].mask(output["family"].eq("missing"), family)
    for column in ["combined_regime", "session_regime"]:
        output[column] = text_series(output, column)
    output["_fixed60_uncertainty_month"] = month_series(output).astype(str).str.slice(0, 7)
    return output


def side_prior_lookup(
    predictions: pd.DataFrame,
    *,
    side: str,
    prior_table: pd.DataFrame,
    group_columns: list[str],
    default: float,
) -> pd.DataFrame:
    lookup = pd.DataFrame({"_row_id": np.arange(len(predictions))})
    lookup["month"] = predictions["_fixed60_uncertainty_month"].astype(str).to_numpy()
    for column in group_columns:
        if column == "direction":
            lookup[column] = side
        elif column in predictions.columns:
            lookup[column] = predictions[column].astype(str).to_numpy()
        else:
            raise ValueError(f"predictions missing group column: {column}")
    lookup["group_key"] = make_group_key(lookup, group_columns)
    merged = lookup.merge(
        prior_table,
        how="left",
        on=["month", "group_key"],
        suffixes=("", "_prior"),
    ).sort_values("_row_id")
    for column in PRIOR_VALUE_COLUMNS:
        if column not in merged.columns:
            merged[column] = default
        merged[column] = numeric_series(merged, column, default=default)
    return merged.reset_index(drop=True)


def uncertainty_risk_input(
    *,
    prior: pd.DataFrame,
    fixed_pred: pd.Series,
    min_prior_trades: float,
    risk_mode: str,
    default_risk: float,
) -> pd.Series:
    supported = prior["prior_trade_count"].astype(float).ge(min_prior_trades)
    fp_rate = prior["prior_fixed_false_positive_rate"].astype(float).where(
        np.isfinite(prior["prior_fixed_false_positive_rate"].astype(float)),
        default_risk,
    )
    fp_rate = fp_rate.clip(lower=0.0, upper=1.0).where(supported, default_risk)
    if risk_mode == "fp_rate":
        return fp_rate
    if risk_mode == "fp_rate_times_positive_fixed_pred":
        return fp_rate * fixed_pred.clip(lower=0.0)
    raise ValueError(f"unknown risk mode: {risk_mode}")


def add_fixed60_uncertainty_margin_columns(
    predictions: pd.DataFrame,
    *,
    family: str,
    trade_rows: pd.DataFrame,
    group_specs: list[list[str]],
    score_kind_prefix: str,
    weights: list[float],
    long_column: str,
    short_column: str,
    long_fixed_pred_column: str,
    short_fixed_pred_column: str,
    long_rank_column: str,
    short_rank_column: str,
    quantile_scopes: list[str],
    min_prior_trades: float,
    risk_mode: str,
    default_risk: float,
    side_gap_source_score_kind: str = "",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing = sorted(
        {
            long_column,
            short_column,
            long_fixed_pred_column,
            short_fixed_pred_column,
            long_rank_column,
            short_rank_column,
        }
        - set(predictions.columns)
    )
    if missing:
        raise ValueError(f"{family} predictions missing columns: {', '.join(missing)}")
    if any(weight < 0.0 for weight in weights):
        raise ValueError("weights must be non-negative")

    output = prepare_predictions(predictions, family=family)
    months = sorted(output["_fixed60_uncertainty_month"].astype(str).unique())
    long_base = numeric_series(output, long_column)
    short_base = numeric_series(output, short_column)
    long_fixed_pred = numeric_series(output, long_fixed_pred_column, default=0.0)
    short_fixed_pred = numeric_series(output, short_fixed_pred_column, default=0.0)
    summary_rows: list[dict[str, Any]] = []

    for group_columns in group_specs:
        prior_table = build_prior_table_for_group_spec(
            trade_rows,
            group_columns=group_columns,
            months=months,
        )
        label = group_spec_label(group_columns)
        long_prior = side_prior_lookup(
            output,
            side="long",
            prior_table=prior_table,
            group_columns=group_columns,
            default=0.0,
        )
        short_prior = side_prior_lookup(
            output,
            side="short",
            prior_table=prior_table,
            group_columns=group_columns,
            default=0.0,
        )
        long_risk = uncertainty_risk_input(
            prior=long_prior,
            fixed_pred=long_fixed_pred,
            min_prior_trades=min_prior_trades,
            risk_mode=risk_mode,
            default_risk=default_risk,
        )
        short_risk = uncertainty_risk_input(
            prior=short_prior,
            fixed_pred=short_fixed_pred,
            min_prior_trades=min_prior_trades,
            risk_mode=risk_mode,
            default_risk=default_risk,
        )
        output[f"pred_{score_kind_prefix}_{label}_long_uncertainty_input"] = long_risk
        output[f"pred_{score_kind_prefix}_{label}_short_uncertainty_input"] = short_risk
        output[f"pred_{score_kind_prefix}_{label}_long_prior_trade_count"] = long_prior[
            "prior_trade_count"
        ].to_numpy()
        output[f"pred_{score_kind_prefix}_{label}_short_prior_trade_count"] = short_prior[
            "prior_trade_count"
        ].to_numpy()
        output[f"pred_{score_kind_prefix}_{label}_long_prior_fp_rate"] = long_prior[
            "prior_fixed_false_positive_rate"
        ].to_numpy()
        output[f"pred_{score_kind_prefix}_{label}_short_prior_fp_rate"] = short_prior[
            "prior_fixed_false_positive_rate"
        ].to_numpy()

        for weight in weights:
            score_kind = score_kind_for_margin(score_kind_prefix, group_columns, weight)
            long_output_column, short_output_column = margin_output_columns(score_kind)
            output[long_output_column] = long_base - weight * long_risk
            output[short_output_column] = short_base - weight * short_risk
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
            if side_gap_source_score_kind:
                output = copy_side_gap_quantiles(
                    output,
                    source_score_kind=side_gap_source_score_kind,
                    target_score_kind=score_kind,
                    quantile_scopes=quantile_scopes,
                )
            summary_rows.append(
                summarize_margin_effect_for_score(
                    output,
                    family=family,
                    group_spec=",".join(group_columns),
                    score_kind=score_kind,
                    weight=weight,
                    long_column=long_column,
                    short_column=short_column,
                    long_output_column=long_output_column,
                    short_output_column=short_output_column,
                    long_risk=long_risk,
                    short_risk=short_risk,
                )
            )

    return output.drop(columns=["_fixed60_uncertainty_month"]), pd.DataFrame(summary_rows)


def copy_side_gap_quantiles(
    frame: pd.DataFrame,
    *,
    source_score_kind: str,
    target_score_kind: str,
    quantile_scopes: list[str],
) -> pd.DataFrame:
    output = frame.copy()
    for scope_name in quantile_scopes:
        source = f"pred_{source_score_kind}_side_gap_pct_{scope_name}"
        target = f"pred_{target_score_kind}_side_gap_pct_{scope_name}"
        if source not in output.columns:
            raise ValueError(f"missing side-gap source column: {source}")
        output[target] = output[source].to_numpy()
    return output


def summarize_margin_effect_for_score(
    frame: pd.DataFrame,
    *,
    family: str,
    group_spec: str,
    score_kind: str,
    weight: float,
    long_column: str,
    short_column: str,
    long_output_column: str,
    short_output_column: str,
    long_risk: pd.Series,
    short_risk: pd.Series,
) -> dict[str, Any]:
    base_long = numeric_series(frame, long_column)
    base_short = numeric_series(frame, short_column)
    margin_long = numeric_series(frame, long_output_column)
    margin_short = numeric_series(frame, short_output_column)
    base_side = np.where(base_long >= base_short, "long", "short")
    margin_side = np.where(margin_long >= margin_short, "long", "short")
    base_score = np.where(base_side == "long", base_long, base_short)
    margin_score = np.where(margin_side == "long", margin_long, margin_short)
    return {
        "family": family,
        "group_spec": group_spec,
        "weight": float(weight),
        "score_kind": score_kind,
        "row_count": int(len(frame)),
        "side_switch_share": float((base_side != margin_side).mean()) if len(frame) else 0.0,
        "base_score_mean": float(np.nanmean(base_score)) if len(frame) else 0.0,
        "margin_score_mean": float(np.nanmean(margin_score)) if len(frame) else 0.0,
        "score_delta_mean": float(np.nanmean(margin_score - base_score))
        if len(frame)
        else 0.0,
        "base_score_q95": float(np.nanquantile(base_score, 0.95)) if len(frame) else 0.0,
        "margin_score_q95": float(np.nanquantile(margin_score, 0.95))
        if len(frame)
        else 0.0,
        "long_risk_mean": float(long_risk.mean()) if len(long_risk) else 0.0,
        "short_risk_mean": float(short_risk.mean()) if len(short_risk) else 0.0,
        "long_risk_q95": float(long_risk.quantile(0.95)) if len(long_risk) else 0.0,
        "short_risk_q95": float(short_risk.quantile(0.95)) if len(short_risk) else 0.0,
        "long_risk_positive_share": float(long_risk.gt(0.0).mean())
        if len(long_risk)
        else 0.0,
        "short_risk_positive_share": float(short_risk.gt(0.0).mean())
        if len(short_risk)
        else 0.0,
    }


def run_margin_input_generation(args: argparse.Namespace) -> Path:
    family_paths = parse_family_predictions(args.family_predictions)
    trade_rows = normalize_trade_rows(read_trade_rows(args.trade_rows))
    group_specs = parse_group_specs(args.group_specs)
    weights = parse_float_csv(args.weights)
    quantile_scopes = parse_scope_csv(args.quantile_scopes)

    run_dir = make_run_dir(args.output_dir, args.label)
    prediction_dir = run_dir / "enriched_predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    output_paths: dict[str, Path] = {}
    summaries: list[pd.DataFrame] = []

    for family, path in family_paths.items():
        predictions = pd.read_parquet(path)
        enriched, summary = add_fixed60_uncertainty_margin_columns(
            predictions,
            family=family,
            trade_rows=trade_rows,
            group_specs=group_specs,
            score_kind_prefix=args.score_kind_prefix,
            weights=weights,
            long_column=args.long_column,
            short_column=args.short_column,
            long_fixed_pred_column=args.long_fixed_pred_column,
            short_fixed_pred_column=args.short_fixed_pred_column,
            long_rank_column=args.long_rank_column,
            short_rank_column=args.short_rank_column,
            quantile_scopes=quantile_scopes,
            min_prior_trades=args.min_prior_trades,
            risk_mode=args.risk_mode,
            default_risk=args.default_risk,
            side_gap_source_score_kind=args.side_gap_source_score_kind,
        )
        output_path = (
            prediction_dir / f"{family}_predictions_fixed60_uncertainty_margin.parquet"
        )
        enriched.to_parquet(output_path, index=False)
        output_paths[family] = output_path
        summaries.append(summary)

    effect_summary = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    effect_summary.to_csv(
        run_dir / "prediction_fixed60_uncertainty_margin_effect_summary.csv",
        index=False,
    )
    config = {
        "family_predictions": family_paths,
        "trade_rows": args.trade_rows,
        "output_paths": output_paths,
        "group_specs": group_specs,
        "weights": weights,
        "score_kind_prefix": args.score_kind_prefix,
        "score_kinds": [
            score_kind_for_margin(args.score_kind_prefix, group_columns, weight)
            for group_columns in group_specs
            for weight in weights
        ],
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_fixed_pred_column": args.long_fixed_pred_column,
        "short_fixed_pred_column": args.short_fixed_pred_column,
        "long_rank_column": args.long_rank_column,
        "short_rank_column": args.short_rank_column,
        "quantile_scopes": quantile_scopes,
        "min_prior_trades": args.min_prior_trades,
        "risk_mode": args.risk_mode,
        "default_risk": args.default_risk,
        "side_gap_source_score_kind": args.side_gap_source_score_kind,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Fixed60 uncertainty margin effect summary:")
    if effect_summary.empty:
        print("(empty)")
    else:
        print(
            effect_summary[
                [
                    "family",
                    "group_spec",
                    "weight",
                    "side_switch_share",
                    "score_delta_mean",
                    "long_risk_q95",
                    "short_risk_q95",
                ]
            ].to_string(index=False)
        )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--trade-rows", type=Path, action="append", required=True)
    parser.add_argument("--group-specs", default=DEFAULT_GROUP_SPECS)
    parser.add_argument("--weights", default=DEFAULT_WEIGHTS)
    parser.add_argument("--score-kind-prefix", default=DEFAULT_SCORE_KIND_PREFIX)
    parser.add_argument("--long-column", required=True)
    parser.add_argument("--short-column", required=True)
    parser.add_argument(
        "--long-fixed-pred-column",
        default="pred_long_fixed_60m_adjusted_pnl",
    )
    parser.add_argument(
        "--short-fixed-pred-column",
        default="pred_short_fixed_60m_adjusted_pnl",
    )
    parser.add_argument("--long-rank-column", default="pred_long_entry_local_rank")
    parser.add_argument("--short-rank-column", default="pred_short_entry_local_rank")
    parser.add_argument("--quantile-scopes", default=DEFAULT_QUANTILE_SCOPES)
    parser.add_argument("--min-prior-trades", type=float, default=5.0)
    parser.add_argument(
        "--risk-mode",
        choices=["fp_rate", "fp_rate_times_positive_fixed_pred"],
        default=DEFAULT_RISK_MODE,
    )
    parser.add_argument("--default-risk", type=float, default=0.0)
    parser.add_argument("--side-gap-source-score-kind", default="")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument(
        "--label",
        default="entry_ev_fixed60_uncertainty_margin_policy_inputs",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_margin_input_generation(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
