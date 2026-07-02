#!/usr/bin/env python3
"""Build prior-only executable-EV policy input columns for entry-EV backtests."""

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

from entry_ev_executable_ev_calibration_diagnostics import (  # noqa: E402
    add_capture_ratio_columns,
    build_all_capture_stats,
    dedupe_prior_trades,
)
from entry_ev_scale_quantile_diagnostics import (  # noqa: E402
    QUANTILE_COLUMN_SUFFIXES,
    add_scope_quantiles,
    build_distribution_summary,
    build_score_frame,
    month_series,
    parse_scope_csv,
    quantile_column_name,
    quantile_summary,
)


DEFAULT_CONTEXT_COLUMNS = ["direction", "combined_regime", "session_regime"]
DEFAULT_LONG_OUTPUT_COLUMN = "pred_executable_calibrated_long_best_adjusted_pnl"
DEFAULT_SHORT_OUTPUT_COLUMN = "pred_executable_calibrated_short_best_adjusted_pnl"


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


def read_trade_frames(paths: list[Path]) -> pd.DataFrame:
    frames = [pd.read_csv(path) for path in paths]
    if not frames:
        raise ValueError("at least one prior trade CSV is required")
    return pd.concat(frames, ignore_index=True)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    series = frame[column]
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(float(default)).astype(float).ne(0.0)
    normalized = series.astype(str).str.lower().str.strip()
    return normalized.isin({"true", "1", "yes", "y"})


def normalize_prior_trades(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "role",
        "candidate",
        "month",
        "direction",
        "entry_decision_timestamp",
        "combined_regime",
        "session_regime",
        "adjusted_pnl",
        "actual_taken_best_adjusted_pnl",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"prior trades missing columns: {', '.join(missing)}")
    normalized = frame.copy()
    normalized["role"] = normalized["role"].astype(str)
    normalized["candidate"] = normalized["candidate"].astype(str)
    normalized["month"] = normalized["month"].astype(str).str.slice(0, 7)
    normalized["direction"] = normalized["direction"].astype(str).str.lower()
    normalized["combined_regime"] = normalized["combined_regime"].astype(str)
    normalized["session_regime"] = normalized["session_regime"].astype(str)
    normalized["entry_decision_timestamp"] = pd.to_datetime(
        normalized["entry_decision_timestamp"],
        utc=True,
    )
    normalized["adjusted_pnl"] = pd.to_numeric(
        normalized["adjusted_pnl"],
        errors="coerce",
    ).fillna(0.0)
    normalized["actual_taken_best_adjusted_pnl"] = pd.to_numeric(
        normalized["actual_taken_best_adjusted_pnl"],
        errors="coerce",
    ).fillna(0.0)
    for column in [
        "exit_capture_failure",
        "same_side_missed_loss",
        "large_exit_regret",
    ]:
        normalized[column] = bool_series(normalized, column)
    return normalized


def filter_prior_trades(
    trades: pd.DataFrame,
    *,
    roles: set[str],
    candidates: set[str],
) -> pd.DataFrame:
    filtered = trades.copy()
    if roles:
        filtered = filtered[filtered["role"].isin(roles)].copy()
    if candidates:
        filtered = filtered[filtered["candidate"].isin(candidates)].copy()
    return filtered.reset_index(drop=True)


def side_capture_lookup(
    predictions: pd.DataFrame,
    *,
    side: str,
    context_stats: pd.DataFrame,
    global_stats: pd.DataFrame,
    context_columns: list[str],
    support_scale: float,
    default_capture_factor: float,
    min_capture_factor: float,
    max_capture_factor: float,
    capture_shrink_strength: float,
) -> pd.DataFrame:
    if support_scale <= 0:
        raise ValueError("support_scale must be positive")
    if min_capture_factor > max_capture_factor:
        raise ValueError("min_capture_factor must be <= max_capture_factor")
    if not 0.0 <= capture_shrink_strength <= 1.0:
        raise ValueError("capture_shrink_strength must be between 0 and 1")

    lookup_data: dict[str, Any] = {
        "_row_id": np.arange(len(predictions)),
        "target_month": month_series(predictions).astype(str),
    }
    for column in context_columns:
        if column == "direction":
            lookup_data[column] = side
        elif column in predictions.columns:
            lookup_data[column] = (
                predictions[column].astype(str).fillna("__missing__").to_numpy()
            )
        else:
            raise ValueError(f"predictions missing context column: {column}")
    lookup = pd.DataFrame(lookup_data)
    if global_stats.empty:
        merged = lookup.copy()
    else:
        merged = lookup.merge(global_stats, how="left", on="target_month")
    if not context_stats.empty and context_columns:
        merged = merged.merge(
            context_stats,
            how="left",
            on=["target_month", *context_columns],
        )
    merged = merged.sort_values("_row_id").reset_index(drop=True)

    numeric_defaults = {
        "prior_global_trade_count": 0.0,
        "prior_global_capture_count": 0.0,
        "prior_global_month_count": 0.0,
        "prior_global_capture_factor": np.nan,
        "prior_context_capture_count": 0.0,
        "prior_context_month_count": 0.0,
        "prior_context_capture_factor": np.nan,
    }
    for column, default in numeric_defaults.items():
        if column not in merged.columns:
            merged[column] = default
        merged[column] = pd.to_numeric(merged[column], errors="coerce")
        if not np.isnan(default):
            merged[column] = merged[column].fillna(default)

    global_factor = (
        merged["prior_global_capture_factor"]
        .fillna(default_capture_factor)
        .clip(lower=min_capture_factor, upper=max_capture_factor)
    )
    context_factor = (
        merged["prior_context_capture_factor"]
        .fillna(global_factor)
        .clip(lower=min_capture_factor, upper=max_capture_factor)
    )
    support_weight = np.clip(
        merged["prior_context_capture_count"].astype(float) / support_scale,
        0.0,
        1.0,
    )
    capture_factor = (
        (1.0 - support_weight) * global_factor + support_weight * context_factor
    ).clip(lower=min_capture_factor, upper=max_capture_factor)
    capture_factor = 1.0 - capture_shrink_strength * (1.0 - capture_factor)
    capture_factor = capture_factor.clip(lower=min_capture_factor, upper=max_capture_factor)

    return pd.DataFrame(
        {
            f"pred_executable_{side}_capture_factor": capture_factor,
            f"pred_executable_{side}_global_capture_factor": global_factor,
            f"pred_executable_{side}_context_capture_factor": context_factor,
            f"pred_executable_{side}_capture_support_weight": support_weight,
            f"pred_executable_{side}_context_capture_count": merged[
                "prior_context_capture_count"
            ].astype(float),
            f"pred_executable_{side}_global_capture_count": merged[
                "prior_global_capture_count"
            ].astype(float),
            f"pred_executable_{side}_global_month_count": merged[
                "prior_global_month_count"
            ].astype(float),
        },
        index=predictions.index,
    )


def add_executable_ev_scores(
    predictions: pd.DataFrame,
    prior: pd.DataFrame,
    *,
    long_column: str,
    short_column: str,
    long_output_column: str,
    short_output_column: str,
    min_prior_months: int,
    recent_month_count: int,
    support_scale: float,
    default_capture_factor: float,
    min_capture_factor: float,
    max_capture_factor: float,
    capture_shrink_strength: float = 1.0,
    context_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    context_columns = context_columns or DEFAULT_CONTEXT_COLUMNS
    missing = sorted({long_column, short_column} - set(predictions.columns))
    if missing:
        raise ValueError(f"predictions missing columns: {', '.join(missing)}")
    missing_context = sorted(
        column
        for column in context_columns
        if column != "direction" and column not in predictions.columns
    )
    if missing_context:
        raise ValueError(f"predictions missing context columns: {', '.join(missing_context)}")

    output = predictions.copy()
    target_months = sorted(month_series(output).dropna().astype(str).unique().tolist())
    context_stats, global_stats = build_all_capture_stats(
        prior,
        target_months,
        min_prior_months=min_prior_months,
        recent_month_count=recent_month_count,
        context_columns=context_columns,
    )

    long_lookup = side_capture_lookup(
        output,
        side="long",
        context_stats=context_stats,
        global_stats=global_stats,
        context_columns=context_columns,
        support_scale=support_scale,
        default_capture_factor=default_capture_factor,
        min_capture_factor=min_capture_factor,
        max_capture_factor=max_capture_factor,
        capture_shrink_strength=capture_shrink_strength,
    )
    short_lookup = side_capture_lookup(
        output,
        side="short",
        context_stats=context_stats,
        global_stats=global_stats,
        context_columns=context_columns,
        support_scale=support_scale,
        default_capture_factor=default_capture_factor,
        min_capture_factor=min_capture_factor,
        max_capture_factor=max_capture_factor,
        capture_shrink_strength=capture_shrink_strength,
    )
    for column in long_lookup.columns:
        output[column] = long_lookup[column].to_numpy()
    for column in short_lookup.columns:
        output[column] = short_lookup[column].to_numpy()

    output[long_output_column] = (
        pd.to_numeric(output[long_column], errors="coerce")
        * output["pred_executable_long_capture_factor"]
    )
    output[short_output_column] = (
        pd.to_numeric(output[short_column], errors="coerce")
        * output["pred_executable_short_capture_factor"]
    )
    return output, context_stats, global_stats


def add_executable_quantile_columns(
    predictions: pd.DataFrame,
    *,
    family: str,
    score_kind: str,
    long_output_column: str,
    short_output_column: str,
    long_rank_column: str,
    short_rank_column: str,
    quantile_scopes: list[str],
) -> pd.DataFrame:
    result = predictions.copy()
    score_frame = build_score_frame(
        result,
        family=family,
        score_kind=score_kind,
        long_score_column=long_output_column,
        short_score_column=short_output_column,
        long_rank_column=long_rank_column,
        short_rank_column=short_rank_column,
    )
    for scope_name in quantile_scopes:
        scoped = add_scope_quantiles(score_frame, scope_name=scope_name)
        for source_column in QUANTILE_COLUMN_SUFFIXES:
            result[
                quantile_column_name(
                    score_kind=score_kind,
                    source_column=source_column,
                    scope_name=scope_name,
                )
            ] = scoped[f"{source_column}_pct"].to_numpy()
        result[f"pred_{score_kind}_quantile_scope_count_{scope_name}"] = scoped[
            "selected_score_scope_count"
        ].to_numpy()
    return result


def summarize_prediction_effect(
    predictions: pd.DataFrame,
    *,
    family: str,
    base_long_column: str,
    base_short_column: str,
    executable_long_column: str,
    executable_short_column: str,
) -> pd.DataFrame:
    frame = pd.DataFrame(index=predictions.index)
    frame["family"] = family
    frame["month"] = month_series(predictions)
    base_long = pd.to_numeric(predictions[base_long_column], errors="coerce")
    base_short = pd.to_numeric(predictions[base_short_column], errors="coerce")
    exec_long = pd.to_numeric(predictions[executable_long_column], errors="coerce")
    exec_short = pd.to_numeric(predictions[executable_short_column], errors="coerce")
    frame["base_valid"] = base_long.notna() & base_short.notna()
    frame["executable_valid"] = exec_long.notna() & exec_short.notna()
    frame["base_selected_side"] = np.where(base_long >= base_short, 1, -1)
    frame["executable_selected_side"] = np.where(exec_long >= exec_short, 1, -1)
    frame.loc[~frame["base_valid"], "base_selected_side"] = 0
    frame.loc[~frame["executable_valid"], "executable_selected_side"] = 0
    frame["base_selected_score"] = np.where(
        frame["base_selected_side"].eq(1),
        base_long,
        base_short,
    )
    frame["executable_selected_score"] = np.where(
        frame["executable_selected_side"].eq(1),
        exec_long,
        exec_short,
    )
    frame["base_side_gap"] = (base_long - base_short).abs()
    frame["executable_side_gap"] = (exec_long - exec_short).abs()
    frame["side_switch"] = (
        frame["base_valid"]
        & frame["executable_valid"]
        & (frame["base_selected_side"] != frame["executable_selected_side"])
    )
    for side in ["long", "short"]:
        for suffix in [
            "capture_factor",
            "context_capture_count",
            "global_capture_count",
            "global_month_count",
        ]:
            frame[f"{side}_{suffix}"] = pd.to_numeric(
                predictions[f"pred_executable_{side}_{suffix}"],
                errors="coerce",
            )

    rows: list[dict[str, Any]] = []
    for (month,), group in frame.groupby(["month"], dropna=False):
        base_valid = group["base_valid"].fillna(False)
        exec_valid = group["executable_valid"].fillna(False)
        row: dict[str, Any] = {
            "family": family,
            "month": month,
            "row_count": int(len(group)),
            "base_valid_count": int(base_valid.sum()),
            "executable_valid_count": int(exec_valid.sum()),
            "base_selected_long_share": float(
                (base_valid & group["base_selected_side"].eq(1)).sum() / base_valid.sum()
            )
            if base_valid.sum()
            else 0.0,
            "executable_selected_long_share": float(
                (exec_valid & group["executable_selected_side"].eq(1)).sum()
                / exec_valid.sum()
            )
            if exec_valid.sum()
            else 0.0,
            "side_switch_share": float(group["side_switch"].sum() / exec_valid.sum())
            if exec_valid.sum()
            else 0.0,
            "long_capture_factor_mean": float(group["long_capture_factor"].mean()),
            "short_capture_factor_mean": float(group["short_capture_factor"].mean()),
            "long_context_capture_count_mean": float(
                group["long_context_capture_count"].mean()
            ),
            "short_context_capture_count_mean": float(
                group["short_context_capture_count"].mean()
            ),
            "global_capture_count_mean": float(
                group[["long_global_capture_count", "short_global_capture_count"]]
                .mean(axis=1)
                .mean()
            ),
        }
        row.update(quantile_summary(group.loc[base_valid, "base_selected_score"], "base_score"))
        row.update(
            quantile_summary(
                group.loc[exec_valid, "executable_selected_score"],
                "executable_score",
            )
        )
        row.update(
            quantile_summary(
                group.loc[exec_valid, "executable_side_gap"],
                "executable_side_gap",
            )
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["family", "month"]).reset_index(drop=True)


def build_policy_inputs(args: argparse.Namespace) -> Path:
    families = parse_family_predictions(args.family_predictions)
    quantile_scopes = parse_scope_csv(args.quantile_scopes)
    context_columns = parse_csv(args.context_columns) or DEFAULT_CONTEXT_COLUMNS
    prior = normalize_prior_trades(read_trade_frames(args.prior_trades))
    prior = filter_prior_trades(
        prior,
        roles=set(parse_csv(args.prior_roles)),
        candidates=set(parse_csv(args.prior_candidates)),
    )
    if prior.empty:
        raise ValueError("no prior trades remain after filters")
    missing_prior_context = sorted(column for column in context_columns if column not in prior.columns)
    if missing_prior_context:
        raise ValueError(f"prior trades missing context columns: {', '.join(missing_prior_context)}")
    prior = add_capture_ratio_columns(
        prior,
        min_oracle_edge=args.min_oracle_edge,
        min_capture_factor=args.min_capture_factor,
        max_capture_factor=args.max_capture_factor,
    )
    if args.dedupe_prior:
        prior = dedupe_prior_trades(prior, context_columns=context_columns)

    run_dir = make_run_dir(args.output_dir, args.label)
    enriched_dir = run_dir / "enriched_predictions"
    enriched_dir.mkdir(parents=True, exist_ok=True)

    all_context_stats: list[pd.DataFrame] = []
    all_global_stats: list[pd.DataFrame] = []
    effect_summaries: list[pd.DataFrame] = []
    score_frames: list[pd.DataFrame] = []
    family_outputs: dict[str, str] = {}

    for family, path in families.items():
        raw = pd.read_parquet(path)
        if "family" not in raw.columns:
            raw = raw.copy()
            raw["family"] = family
        enriched, context_stats, global_stats = add_executable_ev_scores(
            raw,
            prior,
            long_column=args.long_column,
            short_column=args.short_column,
            long_output_column=args.long_output_column,
            short_output_column=args.short_output_column,
            min_prior_months=args.min_prior_months,
            recent_month_count=args.recent_month_count,
            support_scale=args.support_scale,
            default_capture_factor=args.default_capture_factor,
            min_capture_factor=args.min_capture_factor,
            max_capture_factor=args.max_capture_factor,
            capture_shrink_strength=args.capture_shrink_strength,
            context_columns=context_columns,
        )
        enriched = add_executable_quantile_columns(
            enriched,
            family=family,
            score_kind=args.score_kind,
            long_output_column=args.long_output_column,
            short_output_column=args.short_output_column,
            long_rank_column=args.long_rank_column,
            short_rank_column=args.short_rank_column,
            quantile_scopes=quantile_scopes,
        )
        output_path = enriched_dir / f"{family}_predictions_executable_ev.parquet"
        enriched.to_parquet(output_path)
        family_outputs[family] = str(output_path)

        if not context_stats.empty:
            context_frame = context_stats.copy()
            family_label_column = (
                "prediction_family" if "family" in context_frame.columns else "family"
            )
            context_frame.insert(0, family_label_column, family)
            all_context_stats.append(context_frame)
        if not global_stats.empty:
            global_frame = global_stats.copy()
            global_frame.insert(0, "family", family)
            all_global_stats.append(global_frame)
        effect_summaries.append(
            summarize_prediction_effect(
                enriched,
                family=family,
                base_long_column=args.long_column,
                base_short_column=args.short_column,
                executable_long_column=args.long_output_column,
                executable_short_column=args.short_output_column,
            )
        )
        score_frames.append(
            build_score_frame(
                enriched,
                family=family,
                score_kind=args.score_kind,
                long_score_column=args.long_output_column,
                short_score_column=args.short_output_column,
                long_rank_column=args.long_rank_column,
                short_rank_column=args.short_rank_column,
            )
        )

    effect_summary = pd.concat(effect_summaries, ignore_index=True)
    effect_summary.to_csv(run_dir / "prediction_executable_ev_effect_summary.csv", index=False)
    if all_context_stats:
        pd.concat(all_context_stats, ignore_index=True).to_csv(
            run_dir / "context_capture_stats.csv",
            index=False,
        )
    if all_global_stats:
        pd.concat(all_global_stats, ignore_index=True).to_csv(
            run_dir / "global_capture_stats.csv",
            index=False,
        )
    base_distribution, group_distribution = build_distribution_summary(score_frames)
    base_distribution.to_csv(run_dir / "executable_score_distribution_summary.csv", index=False)
    group_distribution.to_csv(
        run_dir / "executable_group_distribution_summary.csv",
        index=False,
    )

    config = {
        "family_predictions": {family: str(path) for family, path in families.items()},
        "family_outputs": family_outputs,
        "prior_trades": args.prior_trades,
        "prior_roles": parse_csv(args.prior_roles),
        "prior_candidates": parse_csv(args.prior_candidates),
        "dedupe_prior": args.dedupe_prior,
        "context_columns": context_columns,
        "score_kind": args.score_kind,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_output_column": args.long_output_column,
        "short_output_column": args.short_output_column,
        "long_rank_column": args.long_rank_column,
        "short_rank_column": args.short_rank_column,
        "quantile_scopes": quantile_scopes,
        "min_oracle_edge": args.min_oracle_edge,
        "min_prior_months": args.min_prior_months,
        "recent_month_count": args.recent_month_count,
        "support_scale": args.support_scale,
        "default_capture_factor": args.default_capture_factor,
        "min_capture_factor": args.min_capture_factor,
        "max_capture_factor": args.max_capture_factor,
        "capture_shrink_strength": args.capture_shrink_strength,
        "prior_trade_count": int(len(prior)),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Executable EV prediction effect:")
    print(
        effect_summary[
            [
                "family",
                "month",
                "row_count",
                "base_selected_long_share",
                "executable_selected_long_share",
                "side_switch_share",
                "base_score_q95",
                "executable_score_q95",
                "long_capture_factor_mean",
                "short_capture_factor_mean",
            ]
        ].to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--prior-trades", type=Path, action="append", required=True)
    parser.add_argument("--prior-roles", default="")
    parser.add_argument("--prior-candidates", default="")
    parser.add_argument("--dedupe-prior", action="store_true")
    parser.add_argument(
        "--context-columns",
        default=",".join(DEFAULT_CONTEXT_COLUMNS),
        help="comma-separated prior context columns used to condition capture stats",
    )
    parser.add_argument("--score-kind", default="executable")
    parser.add_argument("--long-column", default="pred_calibrated_long_best_adjusted_pnl")
    parser.add_argument("--short-column", default="pred_calibrated_short_best_adjusted_pnl")
    parser.add_argument("--long-output-column", default=DEFAULT_LONG_OUTPUT_COLUMN)
    parser.add_argument("--short-output-column", default=DEFAULT_SHORT_OUTPUT_COLUMN)
    parser.add_argument("--long-rank-column", default="pred_long_entry_local_rank")
    parser.add_argument("--short-rank-column", default="pred_short_entry_local_rank")
    parser.add_argument(
        "--quantile-scopes",
        default="month,side_month,side_regime_session_month",
    )
    parser.add_argument("--min-oracle-edge", type=float, default=0.0)
    parser.add_argument("--min-prior-months", type=int, default=1)
    parser.add_argument("--recent-month-count", type=int, default=0)
    parser.add_argument("--support-scale", type=float, default=4.0)
    parser.add_argument("--default-capture-factor", type=float, default=1.0)
    parser.add_argument("--min-capture-factor", type=float, default=0.0)
    parser.add_argument("--max-capture-factor", type=float, default=1.0)
    parser.add_argument("--capture-shrink-strength", type=float, default=1.0)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_executable_ev_policy_inputs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_policy_inputs(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
