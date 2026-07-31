#!/usr/bin/env python3
"""Attach side-prior-pressure EV-overestimate risk to prediction rows."""

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

from entry_ev_component_target_calibration import (  # noqa: E402
    bool_series,
    fit_bucket_rates,
)
from entry_ev_composite_target_decomposition import feature_pressure_score  # noqa: E402
from entry_ev_executable_ev_policy_inputs import add_executable_quantile_columns  # noqa: E402
from entry_ev_overestimate_context_diagnostics import bucketize_context  # noqa: E402
from entry_ev_overestimate_risk_selector import DEFAULT_TARGET  # noqa: E402
from entry_ev_scale_quantile_diagnostics import month_series, parse_scope_csv  # noqa: E402
from entry_ev_side_balance_downside_interaction import add_prior_downside_features  # noqa: E402


GROUP_COLUMNS = [
    "direction",
    "support_bucket",
    "pressure_bucket",
    "prior_support_bucket",
    "feature_pressure_bucket",
]
DEFAULT_SCORE_KIND_PREFIX = "side_prior_pressure"
DEFAULT_QUANTILE_SCOPES = "month,side_month,side_regime_session_month"


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


def parse_float_csv(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


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


def strength_label(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "s" + text.replace("-", "m").replace(".", "p")


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values), default).fillna(default).astype(float)


def normalize_component_targets(path: Path, *, target: str) -> pd.DataFrame:
    raw = pd.read_csv(path)
    for column in [
        "prior_downside_support_weight",
        "feature_pressure_score",
        "side_balance_signed_drift_for_trade",
        "prior_downside_risk_score",
    ]:
        if column not in raw.columns:
            raw[column] = 0.0
    frame = bucketize_context(raw)
    required = {"month", target, *GROUP_COLUMNS}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"component target frame missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["direction"] = output["direction"].astype(str).str.lower()
    for column in GROUP_COLUMNS:
        output[column] = (
            output[column]
            .fillna("missing")
            .astype(str)
            .str.strip()
            .replace({"": "missing", "nan": "missing", "None": "missing"})
        )
    output[target] = bool_series(output, target)
    return output


def normalize_prior_trades(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {
        "month",
        "direction",
        "combined_regime",
        "session_regime",
        "adjusted_pnl",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"prior trades missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["direction"] = output["direction"].astype(str).str.lower()
    output["combined_regime"] = output["combined_regime"].astype(str)
    output["session_regime"] = output["session_regime"].astype(str)
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl")
    output["exit_regret"] = numeric_series(output, "exit_regret")
    output["direction_error"] = bool_series(output, "direction_error") if "direction_error" in output else False
    output["no_edge_entry"] = bool_series(output, "no_edge_entry") if "no_edge_entry" in output else False
    return output


def prediction_month_strings(predictions: pd.DataFrame) -> pd.Series:
    return month_series(predictions).astype(str).str.slice(0, 7)


def build_side_rows(predictions: pd.DataFrame, *, side: str) -> pd.DataFrame:
    if side not in {"long", "short"}:
        raise ValueError(f"unknown side: {side}")
    required = {"combined_regime", "session_regime", "pred_side_balance_long_share_drift"}
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise ValueError(f"predictions missing columns: {', '.join(missing)}")
    drift = numeric_series(predictions, "pred_side_balance_long_share_drift")
    signed_drift = drift if side == "long" else -drift
    return pd.DataFrame(
        {
            "_row_id": np.arange(len(predictions), dtype=int),
            "month": prediction_month_strings(predictions),
            "direction": side,
            "combined_regime": predictions["combined_regime"].astype(str).to_numpy(),
            "session_regime": predictions["session_regime"].astype(str).to_numpy(),
            "side_balance_signed_drift_for_trade": signed_drift.to_numpy(),
        }
    )


def add_side_prior_pressure_buckets(
    side_rows: pd.DataFrame,
    prior_trades: pd.DataFrame,
    *,
    min_prior_months: int,
    recent_month_count: int,
    support_scale: float,
    pnl_scale: float,
    large_exit_regret_threshold: float,
    risk_threshold: float,
    interaction_threshold: float,
    min_prior_support_weight: float,
) -> pd.DataFrame:
    enriched = add_prior_downside_features(
        side_rows,
        prior_trades,
        min_prior_months=min_prior_months,
        recent_month_count=recent_month_count,
        support_scale=support_scale,
        pnl_scale=pnl_scale,
        large_exit_regret_threshold=large_exit_regret_threshold,
    )
    prior_zero = enriched["prior_trade_count"].astype(float).le(0.0)
    missing_support = prior_zero | enriched["prior_downside_support_weight"].astype(float).le(0.0)
    low_support = enriched["prior_downside_support_weight"].astype(float) < min_prior_support_weight
    risk_high = enriched["prior_downside_risk_score"].astype(float) >= risk_threshold
    interaction = (
        enriched["side_balance_signed_drift_for_trade"].astype(float).abs()
        * enriched["prior_downside_risk_score"].astype(float)
    )
    interaction_high = interaction >= interaction_threshold
    pressure = feature_pressure_score(
        risk_high=risk_high,
        interaction_high=interaction_high,
        risk_score=enriched["prior_downside_risk_score"].astype(float),
        prior_zero=prior_zero,
    )
    enriched["side_balance_downside_interaction_score"] = interaction
    enriched["feature_pressure_score"] = pressure
    enriched["support_bucket"] = np.select(
        [
            missing_support,
            low_support,
            enriched["prior_downside_support_weight"].astype(float) < 0.50,
        ],
        ["missing", "low", "medium"],
        default="high",
    )
    enriched["pressure_bucket"] = pd.cut(
        enriched["feature_pressure_score"].astype(float),
        bins=[-0.001, 0.15, 0.35, 0.60, float("inf")],
        labels=["low", "medium", "high", "extreme"],
    ).astype(str)
    enriched["prior_support_bucket"] = pd.cut(
        enriched["prior_downside_support_weight"].astype(float),
        bins=[-np.inf, 0.0, 0.2, 0.5, np.inf],
        labels=["missing", "low", "medium", "high"],
        right=True,
    ).astype(str)
    enriched["feature_pressure_bucket"] = pd.cut(
        enriched["feature_pressure_score"].astype(float),
        bins=[-np.inf, 0.25, 0.5, 0.7, np.inf],
        labels=["low", "medium", "high", "extreme"],
        right=False,
    ).astype(str)
    return enriched


def rate_table_for_month(
    component: pd.DataFrame,
    *,
    target: str,
    month: str,
    prior_strength: float,
    min_group_support: int,
) -> tuple[float, pd.DataFrame]:
    periods = pd.PeriodIndex(component["month"].astype(str), freq="M")
    train = component[periods < pd.Period(month, freq="M")].copy()
    global_rate, rates = fit_bucket_rates(
        train,
        target=target,
        group_columns=GROUP_COLUMNS,
        prior_strength=prior_strength,
        min_group_support=min_group_support,
    )
    rows: list[dict[str, Any]] = []
    for key, (support, rate) in rates.items():
        row = dict(zip(GROUP_COLUMNS, key, strict=True))
        row["prediction_support"] = support
        row["predicted_target_rate"] = rate
        rows.append(row)
    return global_rate, pd.DataFrame(rows)


def apply_ev_overestimate_risk(
    side_rows: pd.DataFrame,
    component: pd.DataFrame,
    *,
    target: str,
    prior_strength: float,
    min_group_support: int,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for month, group in side_rows.groupby("month", dropna=False, sort=True):
        global_rate, table = rate_table_for_month(
            component,
            target=target,
            month=str(month),
            prior_strength=prior_strength,
            min_group_support=min_group_support,
        )
        output = group.copy()
        if not np.isfinite(global_rate):
            output["predicted_ev_overestimate_risk"] = np.nan
            output["ev_overestimate_prediction_support"] = 0
            output["ev_overestimate_prediction_source"] = "no_prior"
        elif table.empty:
            output["predicted_ev_overestimate_risk"] = global_rate
            output["ev_overestimate_prediction_support"] = 0
            output["ev_overestimate_prediction_source"] = "global"
        else:
            merged = output.merge(table, how="left", on=GROUP_COLUMNS)
            bucket_hit = merged["predicted_target_rate"].notna()
            merged["predicted_ev_overestimate_risk"] = merged[
                "predicted_target_rate"
            ].where(bucket_hit, global_rate)
            merged["ev_overestimate_prediction_support"] = pd.to_numeric(
                merged["prediction_support"],
                errors="coerce",
            ).fillna(0.0).astype(int)
            merged["ev_overestimate_prediction_source"] = np.where(
                bucket_hit,
                "bucket",
                "global",
            )
            output = merged.drop(columns=["predicted_target_rate", "prediction_support"])
        frames.append(output)
    return pd.concat(frames, ignore_index=True).sort_values("_row_id").reset_index(drop=True)


def add_side_risk_columns(
    predictions: pd.DataFrame,
    *,
    component: pd.DataFrame,
    prior_trades: pd.DataFrame,
    target: str,
    prior_strength: float,
    min_group_support: int,
    min_prior_months: int,
    recent_month_count: int,
    support_scale: float,
    pnl_scale: float,
    large_exit_regret_threshold: float,
    risk_threshold: float,
    interaction_threshold: float,
    min_prior_support_weight: float,
) -> pd.DataFrame:
    output = predictions.copy()
    for side in ["long", "short"]:
        side_rows = build_side_rows(output, side=side)
        side_rows = add_side_prior_pressure_buckets(
            side_rows,
            prior_trades,
            min_prior_months=min_prior_months,
            recent_month_count=recent_month_count,
            support_scale=support_scale,
            pnl_scale=pnl_scale,
            large_exit_regret_threshold=large_exit_regret_threshold,
            risk_threshold=risk_threshold,
            interaction_threshold=interaction_threshold,
            min_prior_support_weight=min_prior_support_weight,
        )
        side_rows = apply_ev_overestimate_risk(
            side_rows,
            component,
            target=target,
            prior_strength=prior_strength,
            min_group_support=min_group_support,
        )
        side_rows = side_rows.sort_values("_row_id").reset_index(drop=True)
        for column in [
            "prior_downside_support_weight",
            "prior_downside_risk_score",
            "side_balance_signed_drift_for_trade",
            "side_balance_downside_interaction_score",
            "feature_pressure_score",
            "support_bucket",
            "pressure_bucket",
            "prior_support_bucket",
            "feature_pressure_bucket",
            "predicted_ev_overestimate_risk",
            "ev_overestimate_prediction_support",
            "ev_overestimate_prediction_source",
        ]:
            output[f"pred_side_prior_pressure_{side}_{column}"] = side_rows[column].to_numpy()
    return output


def add_risk_adjusted_scores(
    predictions: pd.DataFrame,
    *,
    family: str,
    score_kind_prefix: str,
    long_column: str,
    short_column: str,
    long_rank_column: str,
    short_rank_column: str,
    penalty_strengths: list[float],
    no_prior_risk: float,
    min_score_scale: float,
    quantile_scopes: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = predictions.copy()
    summary_rows: list[dict[str, Any]] = []
    long_base = numeric_series(output, long_column)
    short_base = numeric_series(output, short_column)
    for strength in penalty_strengths:
        label = strength_label(strength)
        score_kind = f"{score_kind_prefix}_{label}"
        long_risk = numeric_series(
            output,
            "pred_side_prior_pressure_long_predicted_ev_overestimate_risk",
            default=no_prior_risk,
        )
        short_risk = numeric_series(
            output,
            "pred_side_prior_pressure_short_predicted_ev_overestimate_risk",
            default=no_prior_risk,
        )
        long_source = output[
            "pred_side_prior_pressure_long_ev_overestimate_prediction_source"
        ].astype(str)
        short_source = output[
            "pred_side_prior_pressure_short_ev_overestimate_prediction_source"
        ].astype(str)
        long_risk = long_risk.where(~long_source.eq("no_prior"), no_prior_risk)
        short_risk = short_risk.where(~short_source.eq("no_prior"), no_prior_risk)
        long_scale = (1.0 - strength * long_risk).clip(lower=min_score_scale, upper=1.0)
        short_scale = (1.0 - strength * short_risk).clip(lower=min_score_scale, upper=1.0)
        long_output_column = f"pred_{score_kind}_long_best_adjusted_pnl"
        short_output_column = f"pred_{score_kind}_short_best_adjusted_pnl"
        output[long_output_column] = long_base * long_scale
        output[short_output_column] = short_base * short_scale
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
        summary_rows.append(
            {
                "family": family,
                "score_kind": score_kind,
                "penalty_strength": strength,
                "long_scale_mean": float(long_scale.mean()),
                "short_scale_mean": float(short_scale.mean()),
                "long_risk_mean": float(long_risk.mean()),
                "short_risk_mean": float(short_risk.mean()),
                "long_bucket_share": float(long_source.eq("bucket").mean()),
                "short_bucket_share": float(short_source.eq("bucket").mean()),
                "long_global_share": float(long_source.eq("global").mean()),
                "short_global_share": float(short_source.eq("global").mean()),
                "long_no_prior_share": float(long_source.eq("no_prior").mean()),
                "short_no_prior_share": float(short_source.eq("no_prior").mean()),
            }
        )
    return output, pd.DataFrame(summary_rows)


def build_policy_inputs(args: argparse.Namespace) -> Path:
    family_predictions = parse_family_predictions(args.family_predictions)
    penalty_strengths = parse_float_csv(args.penalty_strengths)
    if not penalty_strengths:
        raise ValueError("--penalty-strengths must not be empty")
    quantile_scopes = parse_scope_csv(args.quantile_scopes)
    component = normalize_component_targets(args.component_targets, target=args.target)
    prior_trades = normalize_prior_trades(args.prior_trades)
    run_dir = make_run_dir(args.output_dir, args.label)
    enriched_dir = run_dir / "enriched_predictions"
    enriched_dir.mkdir(parents=True, exist_ok=True)

    summary_frames: list[pd.DataFrame] = []
    distribution_rows: list[dict[str, Any]] = []
    for family, prediction_path in family_predictions.items():
        predictions = pd.read_parquet(prediction_path)
        enriched = add_side_risk_columns(
            predictions,
            component=component,
            prior_trades=prior_trades,
            target=args.target,
            prior_strength=args.prior_strength,
            min_group_support=args.min_group_support,
            min_prior_months=args.min_prior_months,
            recent_month_count=args.recent_month_count,
            support_scale=args.support_scale,
            pnl_scale=args.pnl_scale,
            large_exit_regret_threshold=args.large_exit_regret_threshold,
            risk_threshold=args.risk_threshold,
            interaction_threshold=args.interaction_threshold,
            min_prior_support_weight=args.min_prior_support_weight,
        )
        enriched, family_summary = add_risk_adjusted_scores(
            enriched,
            family=family,
            score_kind_prefix=args.score_kind_prefix,
            long_column=args.long_column,
            short_column=args.short_column,
            long_rank_column=args.long_rank_column,
            short_rank_column=args.short_rank_column,
            penalty_strengths=penalty_strengths,
            no_prior_risk=args.no_prior_risk,
            min_score_scale=args.min_score_scale,
            quantile_scopes=quantile_scopes,
        )
        summary_frames.append(family_summary)
        for side in ["long", "short"]:
            risk = numeric_series(
                enriched,
                f"pred_side_prior_pressure_{side}_predicted_ev_overestimate_risk",
                default=np.nan,
            )
            source = enriched[f"pred_side_prior_pressure_{side}_ev_overestimate_prediction_source"].astype(str)
            distribution_rows.append(
                {
                    "family": family,
                    "side": side,
                    "row_count": int(len(enriched)),
                    "risk_predicted_count": int(risk.notna().sum()),
                    "risk_mean": float(risk.dropna().mean()) if risk.notna().any() else float("nan"),
                    "risk_p50": float(risk.dropna().quantile(0.50)) if risk.notna().any() else float("nan"),
                    "risk_p90": float(risk.dropna().quantile(0.90)) if risk.notna().any() else float("nan"),
                    "bucket_share": float(source.eq("bucket").mean()),
                    "global_share": float(source.eq("global").mean()),
                    "no_prior_share": float(source.eq("no_prior").mean()),
                }
            )
        output_path = enriched_dir / f"{family}_predictions_side_prior_pressure.parquet"
        enriched.to_parquet(output_path, index=False)

    score_summary = pd.concat(summary_frames, ignore_index=True)
    risk_distribution = pd.DataFrame(distribution_rows)
    score_summary.to_csv(run_dir / "score_adjustment_summary.csv", index=False)
    risk_distribution.to_csv(run_dir / "side_prior_pressure_risk_distribution.csv", index=False)
    config = {
        "family_predictions": family_predictions,
        "component_targets": args.component_targets,
        "prior_trades": args.prior_trades,
        "target": args.target,
        "group_columns": GROUP_COLUMNS,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_rank_column": args.long_rank_column,
        "short_rank_column": args.short_rank_column,
        "score_kind_prefix": args.score_kind_prefix,
        "penalty_strengths": penalty_strengths,
        "no_prior_risk": args.no_prior_risk,
        "min_score_scale": args.min_score_scale,
        "prior_strength": args.prior_strength,
        "min_group_support": args.min_group_support,
        "min_prior_months": args.min_prior_months,
        "recent_month_count": args.recent_month_count,
        "support_scale": args.support_scale,
        "pnl_scale": args.pnl_scale,
        "large_exit_regret_threshold": args.large_exit_regret_threshold,
        "risk_threshold": args.risk_threshold,
        "interaction_threshold": args.interaction_threshold,
        "min_prior_support_weight": args.min_prior_support_weight,
        "quantile_scopes": quantile_scopes,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    print("Side-prior-pressure risk distribution:")
    print(risk_distribution.to_string(index=False))
    print("\nScore adjustment summary:")
    print(score_summary.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--component-targets", type=Path, required=True)
    parser.add_argument("--prior-trades", type=Path, required=True)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--long-column", default="pred_side_balanced_dense_executable_long_best_adjusted_pnl")
    parser.add_argument("--short-column", default="pred_side_balanced_dense_executable_short_best_adjusted_pnl")
    parser.add_argument("--long-rank-column", default="pred_long_entry_local_rank")
    parser.add_argument("--short-rank-column", default="pred_short_entry_local_rank")
    parser.add_argument("--score-kind-prefix", default=DEFAULT_SCORE_KIND_PREFIX)
    parser.add_argument("--penalty-strengths", default="0.5,1.0")
    parser.add_argument("--no-prior-risk", type=float, default=0.0)
    parser.add_argument("--min-score-scale", type=float, default=0.0)
    parser.add_argument("--prior-strength", type=float, default=5.0)
    parser.add_argument("--min-group-support", type=int, default=3)
    parser.add_argument("--min-prior-months", type=int, default=1)
    parser.add_argument("--recent-month-count", type=int, default=0)
    parser.add_argument("--support-scale", type=float, default=10.0)
    parser.add_argument("--pnl-scale", type=float, default=20.0)
    parser.add_argument("--large-exit-regret-threshold", type=float, default=10.0)
    parser.add_argument("--risk-threshold", type=float, default=0.20)
    parser.add_argument("--interaction-threshold", type=float, default=0.005)
    parser.add_argument("--min-prior-support-weight", type=float, default=0.10)
    parser.add_argument("--quantile-scopes", default=DEFAULT_QUANTILE_SCOPES)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_side_prior_pressure_policy_inputs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_policy_inputs(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
