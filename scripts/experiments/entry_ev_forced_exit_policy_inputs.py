#!/usr/bin/env python3
"""Attach forced-exit-loss risk estimates to prediction rows."""

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

from entry_ev_exit_shortening_target_diagnostics import (  # noqa: E402
    CALIBRATION_SPECS as EXIT_SHORTENING_CALIBRATION_SPECS,
    brier_score,
    bool_series,
    bucketize,
    numeric_series,
    rank_auc,
    text_series,
)
from entry_ev_executable_ev_policy_inputs import add_executable_quantile_columns  # noqa: E402
from entry_ev_scale_quantile_diagnostics import month_series, parse_scope_csv  # noqa: E402
from entry_ev_side_prior_pressure_policy_inputs import strength_label  # noqa: E402


DEFAULT_TARGET = "forced_exit_loss_target"
DEFAULT_RISK_NAME = "forced_exit_loss"
DEFAULT_RISK_SPECS = "exit_risk,ev_exit"
DEFAULT_SCORE_KIND_PREFIX = "forced_exit_loss"
DEFAULT_QUANTILE_SCOPES = "month,side_month,side_regime_session_month"

RISK_SPEC_LABELS = {
    "side_context": "sidectx",
    "confidence_exit": "confexit",
    "profit_exit": "profitexit",
    "exit_plan": "exitplan",
    "exit_risk": "exitrisk",
    "direction_exit": "direxit",
    "ev_exit": "evexit",
    "context_confidence": "ctxconf",
}

CALIBRATION_SPECS = {
    **EXIT_SHORTENING_CALIBRATION_SPECS,
    "confidence_exit": [
        "direction",
        "side_confidence_gap_bucket",
        "loss_first_prob_bucket",
        "time_exit_prob_bucket",
    ],
    "profit_exit": [
        "direction",
        "pred_profit_barrier_bucket",
        "loss_first_prob_bucket",
        "pred_exit_hold_bucket",
    ],
    "context_confidence": [
        "direction",
        "combined_regime",
        "session_regime",
        "side_confidence_gap_bucket",
    ],
}


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


def parse_risk_specs(value: str) -> list[str]:
    specs = parse_csv(value)
    unknown = sorted(set(specs) - set(CALIBRATION_SPECS))
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown risk specs: {','.join(unknown)}")
    if not specs:
        raise argparse.ArgumentTypeError("at least one risk spec is required")
    return specs


def source_mode_label(value: str) -> str:
    return value.replace("_or_", "or").replace("_", "")


def prediction_month_strings(predictions: pd.DataFrame) -> pd.Series:
    return month_series(predictions).astype(str).str.slice(0, 7)


def side_column(prefix: str, side: str, suffix: str) -> str:
    return f"{prefix}_{side}_{suffix}"


def bucket_from_risk(values: pd.Series) -> pd.Series:
    return bucketize(
        values,
        bins=[-0.001, 0.20, 0.45, 0.60, float("inf")],
        labels=["very_low", "medium", "high", "extreme"],
    )


def normalize_exit_targets(
    path: Path,
    *,
    target: str,
    risk_specs: list[str],
) -> pd.DataFrame:
    frame = pd.read_csv(path)
    group_columns = sorted({column for spec in risk_specs for column in CALIBRATION_SPECS[spec]})
    required = {"month", "direction", target, *group_columns}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"exit target frame missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["direction"] = output["direction"].astype(str).str.lower()
    output[target] = bool_series(output, target)
    for column in group_columns:
        output[column] = text_series(output, column)
    if "adjusted_pnl" in output.columns:
        output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl")
    return output


def required_prediction_columns(side: str, risk_prefix: str) -> list[str]:
    return [
        "combined_regime",
        "session_regime",
        side_column(risk_prefix, side, "predicted_ev_overestimate_risk"),
        side_column("pred_mlp", side, "exit_event_minutes"),
        side_column("pred", side, "best_holding_minutes"),
        side_column("pred", side, "exit_event_prob_0"),
        side_column("pred", side, "exit_event_prob_2"),
        side_column("pred", side, "profit_barrier_hit"),
        side_column("pred", side, "fixed_60m_adjusted_pnl"),
        side_column("pred", side, "fixed_720m_adjusted_pnl"),
    ]


def build_side_rows(
    predictions: pd.DataFrame,
    *,
    side: str,
    risk_prefix: str,
) -> pd.DataFrame:
    missing = [column for column in required_prediction_columns(side, risk_prefix) if column not in predictions.columns]
    if missing:
        raise ValueError(f"predictions missing columns: {', '.join(missing)}")
    risk = numeric_series(
        predictions,
        side_column(risk_prefix, side, "predicted_ev_overestimate_risk"),
        default=np.nan,
    )
    direction_bucket_column = f"pred_direction_inversion_{side}_selected_risk_bucket"
    if direction_bucket_column in predictions.columns:
        direction_risk_bucket = text_series(predictions, direction_bucket_column)
    else:
        direction_risk_bucket = bucket_from_risk(risk)
    pred_mlp_hold = numeric_series(
        predictions,
        side_column("pred_mlp", side, "exit_event_minutes"),
        default=np.nan,
    )
    pred_taken_hold = numeric_series(
        predictions,
        side_column("pred", side, "best_holding_minutes"),
        default=np.nan,
    )
    pred_fixed_60 = numeric_series(
        predictions,
        side_column("pred", side, "fixed_60m_adjusted_pnl"),
        default=np.nan,
    )
    pred_fixed_720 = numeric_series(
        predictions,
        side_column("pred", side, "fixed_720m_adjusted_pnl"),
        default=np.nan,
    )
    predicted_barrier = numeric_series(
        predictions,
        side_column("pred", side, "profit_barrier_hit"),
        default=np.nan,
    )
    if side == "long":
        side_confidence = numeric_series(predictions, "pred_best_side_prob_1", default=np.nan)
        opposite_confidence = numeric_series(predictions, "pred_best_side_prob_-1", default=np.nan)
    else:
        side_confidence = numeric_series(predictions, "pred_best_side_prob_-1", default=np.nan)
        opposite_confidence = numeric_series(predictions, "pred_best_side_prob_1", default=np.nan)
    side_confidence_gap = side_confidence - opposite_confidence
    rows = pd.DataFrame(
        {
            "_row_id": np.arange(len(predictions), dtype=int),
            "month": prediction_month_strings(predictions),
            "direction": side,
            "combined_regime": text_series(predictions, "combined_regime"),
            "session_regime": text_series(predictions, "session_regime"),
            "side_confidence_gap_bucket": bucketize(
                side_confidence_gap,
                bins=[-float("inf"), -0.05, 0.0, 0.10, 0.25, float("inf")],
                labels=["opposite_favored", "nonpositive", "weak", "medium", "strong"],
            ),
            "selected_direction_risk_bucket": direction_risk_bucket,
            "selected_ev_overestimate_bucket": bucketize(
                risk,
                bins=[-0.001, 0.25, 0.50, 0.75, 1.0],
                labels=["low", "medium", "high", "extreme"],
            ),
            "pred_exit_hold_bucket": bucketize(
                pred_mlp_hold,
                bins=[-0.001, 60.0, 240.0, 720.0, 1440.0, float("inf")],
                labels=["lt60", "60_240", "240_720", "720_1440", "gt1440"],
            ),
            "pred_taken_hold_bucket": bucketize(
                pred_taken_hold,
                bins=[-0.001, 60.0, 240.0, 720.0, 1440.0, float("inf")],
                labels=["lt60", "60_240", "240_720", "720_1440", "gt1440"],
            ),
            "pred_hold_gap_bucket": bucketize(
                pred_mlp_hold - pred_taken_hold,
                bins=[-float("inf"), -240.0, -60.0, 60.0, 240.0, float("inf")],
                labels=[
                    "mlp_much_shorter",
                    "mlp_shorter",
                    "aligned",
                    "mlp_longer",
                    "mlp_much_longer",
                ],
            ),
            "time_exit_prob_bucket": bucketize(
                numeric_series(
                    predictions,
                    side_column("pred", side, "exit_event_prob_0"),
                    default=np.nan,
                ),
                bins=[-0.001, 0.20, 0.40, 0.60, 0.80, 1.0],
                labels=["very_low", "low", "medium", "high", "very_high"],
            ),
            "loss_first_prob_bucket": bucketize(
                numeric_series(
                    predictions,
                    side_column("pred", side, "exit_event_prob_2"),
                    default=np.nan,
                ),
                bins=[-0.001, 0.20, 0.40, 0.60, 0.80, 1.0],
                labels=["very_low", "low", "medium", "high", "very_high"],
            ),
            "pred_profit_barrier_bucket": np.where(
                predicted_barrier.ge(0.5),
                "pred_hit",
                "pred_miss",
            ),
            "pred_fixed_slope_bucket": bucketize(
                pred_fixed_720 - pred_fixed_60,
                bins=[-float("inf"), -20.0, -5.0, 5.0, 20.0, float("inf")],
                labels=["strong_decay", "decay", "flat", "improve", "strong_improve"],
            ),
            "pred_720_bucket": bucketize(
                pred_fixed_720,
                bins=[-float("inf"), 0.0, 5.0, 15.0, 30.0, float("inf")],
                labels=["nonpositive", "low", "medium", "high", "extreme"],
            ),
        }
    )
    rows.loc[predicted_barrier.isna(), "pred_profit_barrier_bucket"] = "missing"
    return rows


def fit_bucket_rates(
    train: pd.DataFrame,
    *,
    target: str,
    group_columns: list[str],
    prior_strength: float,
    min_group_support: int,
) -> tuple[float, dict[tuple[str, ...], tuple[int, float]]]:
    if train.empty:
        return float("nan"), {}
    target_values = bool_series(train, target)
    global_rate = float(target_values.mean())
    rates: dict[tuple[str, ...], tuple[int, float]] = {}
    for keys, group in train.groupby(group_columns, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        count = int(len(group))
        target_sum = int(bool_series(group, target).sum())
        if count >= min_group_support:
            rate = (target_sum + prior_strength * global_rate) / (count + prior_strength)
            rates[tuple(str(key) for key in keys)] = (count, float(rate))
    return global_rate, rates


def rate_table_for_month(
    targets: pd.DataFrame,
    *,
    target: str,
    group_columns: list[str],
    month: str,
    prior_strength: float,
    min_group_support: int,
) -> tuple[float, pd.DataFrame]:
    periods = pd.PeriodIndex(targets["month"].astype(str), freq="M")
    train = targets[periods < pd.Period(month, freq="M")].copy()
    global_rate, rates = fit_bucket_rates(
        train,
        target=target,
        group_columns=group_columns,
        prior_strength=prior_strength,
        min_group_support=min_group_support,
    )
    rows: list[dict[str, Any]] = []
    for key, (support, rate) in rates.items():
        row = dict(zip(group_columns, key, strict=True))
        row["prediction_support"] = support
        row["predicted_target_rate"] = rate
        rows.append(row)
    return global_rate, pd.DataFrame(rows)


def apply_forced_exit_risk(
    side_rows: pd.DataFrame,
    targets: pd.DataFrame,
    *,
    target: str,
    risk_spec: str,
    risk_name: str,
    prior_strength: float,
    min_group_support: int,
) -> pd.DataFrame:
    group_columns = CALIBRATION_SPECS[risk_spec]
    frames: list[pd.DataFrame] = []
    risk_column = f"predicted_{risk_name}_risk"
    support_column = f"{risk_name}_prediction_support"
    source_column = f"{risk_name}_prediction_source"
    for month, group in side_rows.groupby("month", dropna=False, sort=True):
        global_rate, table = rate_table_for_month(
            targets,
            target=target,
            group_columns=group_columns,
            month=str(month),
            prior_strength=prior_strength,
            min_group_support=min_group_support,
        )
        output = group.copy()
        if not np.isfinite(global_rate):
            output[risk_column] = np.nan
            output[support_column] = 0
            output[source_column] = "no_prior"
        elif table.empty:
            output[risk_column] = global_rate
            output[support_column] = 0
            output[source_column] = "global"
        else:
            merged = output.merge(table, how="left", on=group_columns)
            bucket_hit = merged["predicted_target_rate"].notna()
            merged[risk_column] = merged["predicted_target_rate"].where(
                bucket_hit,
                global_rate,
            )
            merged[support_column] = pd.to_numeric(
                merged["prediction_support"],
                errors="coerce",
            ).fillna(0.0).astype(int)
            merged[source_column] = np.where(bucket_hit, "bucket", "global")
            output = merged.drop(columns=["predicted_target_rate", "prediction_support"])
        frames.append(output)
    return pd.concat(frames, ignore_index=True).sort_values("_row_id").reset_index(drop=True)


def add_side_forced_exit_columns(
    predictions: pd.DataFrame,
    *,
    targets: pd.DataFrame,
    target: str,
    risk_specs: list[str],
    risk_name: str,
    risk_prefix: str,
    prior_strength: float,
    min_group_support: int,
) -> pd.DataFrame:
    output = predictions.copy()
    for risk_spec in risk_specs:
        for side in ["long", "short"]:
            side_rows = build_side_rows(output, side=side, risk_prefix=risk_prefix)
            risk = apply_forced_exit_risk(
                side_rows,
                targets,
                target=target,
                risk_spec=risk_spec,
                risk_name=risk_name,
                prior_strength=prior_strength,
                min_group_support=min_group_support,
            )
            risk = risk.sort_values("_row_id").reset_index(drop=True)
            for column in [
                *CALIBRATION_SPECS[risk_spec],
                f"predicted_{risk_name}_risk",
                f"{risk_name}_prediction_support",
                f"{risk_name}_prediction_source",
            ]:
                output[f"pred_{risk_name}_{risk_spec}_{side}_{column}"] = risk[
                    column
                ].to_numpy()
    return output


def source_mask(source: pd.Series, mode: str) -> pd.Series:
    source = source.astype(str)
    if mode == "bucket":
        return source.eq("bucket")
    if mode == "bucket_or_global":
        return source.isin(["bucket", "global"])
    raise ValueError(f"unknown source mode: {mode}")


def source_filtered_risk(
    frame: pd.DataFrame,
    *,
    value_column: str,
    source_column: str,
    mode: str,
    default: float,
) -> pd.Series:
    values = numeric_series(frame, value_column, default=np.nan).clip(0.0, 1.0)
    source = text_series(frame, source_column, default="no_prior")
    allowed = source_mask(source, mode)
    return values.where(allowed, default).fillna(default).clip(0.0, 1.0)


def score_kind_name(
    *,
    prefix: str,
    risk_spec: str,
    source_mode: str,
    strength: float,
) -> str:
    spec_label = RISK_SPEC_LABELS.get(risk_spec, risk_spec.replace("_", ""))
    return f"{prefix}_{spec_label}_{source_mode_label(source_mode)}_{strength_label(strength)}"


def add_forced_exit_adjusted_scores(
    predictions: pd.DataFrame,
    *,
    family: str,
    risk_specs: list[str],
    risk_name: str,
    score_kind_prefix: str,
    long_column: str,
    short_column: str,
    long_rank_column: str,
    short_rank_column: str,
    penalty_strengths: list[float],
    source_modes: list[str],
    no_prior_risk: float,
    min_score_scale: float,
    quantile_scopes: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = predictions.copy()
    long_base = numeric_series(output, long_column)
    short_base = numeric_series(output, short_column)
    rows: list[dict[str, Any]] = []
    for risk_spec in risk_specs:
        for source_mode in source_modes:
            for strength in penalty_strengths:
                score_kind = score_kind_name(
                    prefix=score_kind_prefix,
                    risk_spec=risk_spec,
                    source_mode=source_mode,
                    strength=strength,
                )
                long_risk = source_filtered_risk(
                    output,
                    value_column=f"pred_{risk_name}_{risk_spec}_long_predicted_{risk_name}_risk",
                    source_column=f"pred_{risk_name}_{risk_spec}_long_{risk_name}_prediction_source",
                    mode=source_mode,
                    default=no_prior_risk,
                )
                short_risk = source_filtered_risk(
                    output,
                    value_column=f"pred_{risk_name}_{risk_spec}_short_predicted_{risk_name}_risk",
                    source_column=f"pred_{risk_name}_{risk_spec}_short_{risk_name}_prediction_source",
                    mode=source_mode,
                    default=no_prior_risk,
                )
                long_scale = (1.0 - strength * long_risk).clip(
                    lower=min_score_scale,
                    upper=1.0,
                )
                short_scale = (1.0 - strength * short_risk).clip(
                    lower=min_score_scale,
                    upper=1.0,
                )
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
                rows.append(
                    {
                        "family": family,
                        "score_kind": score_kind,
                        "risk_spec": risk_spec,
                        "source_mode": source_mode,
                        "penalty_strength": strength,
                        "long_scale_mean": float(long_scale.mean()),
                        "short_scale_mean": float(short_scale.mean()),
                        "long_risk_mean": float(long_risk.mean()),
                        "short_risk_mean": float(short_risk.mean()),
                        "long_bucket_share": float(
                            text_series(
                                output,
                                f"pred_{risk_name}_{risk_spec}_long_{risk_name}_prediction_source",
                            ).eq("bucket").mean()
                        ),
                        "short_bucket_share": float(
                            text_series(
                                output,
                                f"pred_{risk_name}_{risk_spec}_short_{risk_name}_prediction_source",
                            ).eq("bucket").mean()
                        ),
                    }
                )
    return output, pd.DataFrame(rows)


def risk_distribution(
    enriched: pd.DataFrame,
    *,
    family: str,
    risk_specs: list[str],
    risk_name: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for risk_spec in risk_specs:
        for side in ["long", "short"]:
            risk = numeric_series(
                enriched,
                f"pred_{risk_name}_{risk_spec}_{side}_predicted_{risk_name}_risk",
                default=np.nan,
            )
            source = text_series(
                enriched,
                f"pred_{risk_name}_{risk_spec}_{side}_{risk_name}_prediction_source",
                default="no_prior",
            )
            rows.append(
                {
                    "family": family,
                    "risk_spec": risk_spec,
                    "side": side,
                    "row_count": int(len(enriched)),
                    "risk_predicted_count": int(risk.notna().sum()),
                    "risk_mean": float(risk.dropna().mean())
                    if risk.notna().any()
                    else float("nan"),
                    "risk_p50": float(risk.dropna().quantile(0.50))
                    if risk.notna().any()
                    else float("nan"),
                    "risk_p90": float(risk.dropna().quantile(0.90))
                    if risk.notna().any()
                    else float("nan"),
                    "bucket_share": float(source.eq("bucket").mean()),
                    "global_share": float(source.eq("global").mean()),
                    "no_prior_share": float(source.eq("no_prior").mean()),
                }
            )
    return pd.DataFrame(rows)


def target_calibration_summary(
    targets: pd.DataFrame,
    *,
    target: str,
    risk_specs: list[str],
    risk_name: str,
    prior_strength: float,
    min_group_support: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    periods = pd.PeriodIndex(targets["month"].astype(str), freq="M")
    for risk_spec in risk_specs:
        group_columns = CALIBRATION_SPECS[risk_spec]
        for month in sorted(targets["month"].astype(str).unique()):
            train = targets[periods < pd.Period(month, freq="M")].copy()
            test = targets[targets["month"].astype(str).eq(month)].copy()
            if test.empty:
                continue
            global_rate, table = rate_table_for_month(
                targets,
                target=target,
                group_columns=group_columns,
                month=month,
                prior_strength=prior_strength,
                min_group_support=min_group_support,
            )
            predicted = apply_forced_exit_risk(
                test.assign(_row_id=np.arange(len(test), dtype=int)),
                targets,
                target=target,
                risk_spec=risk_spec,
                risk_name=risk_name,
                prior_strength=prior_strength,
                min_group_support=min_group_support,
            )
            scores = numeric_series(predicted, f"predicted_{risk_name}_risk", default=np.nan)
            target_values = bool_series(predicted, target)
            rows.append(
                {
                    "risk_spec": risk_spec,
                    "month": month,
                    "train_rows": int(len(train)),
                    "bucket_count": int(len(table)),
                    "row_count": int(len(test)),
                    "target_count": int(target_values.sum()),
                    "target_rate": float(target_values.mean()),
                    "global_rate": global_rate,
                    "predicted_mean": float(scores.dropna().mean())
                    if scores.notna().any()
                    else float("nan"),
                    "bucket_prediction_share": float(
                        predicted[f"{risk_name}_prediction_source"].astype(str).eq("bucket").mean()
                    ),
                    "auc": rank_auc(target_values, scores),
                    "brier": brier_score(target_values, scores),
                }
            )
    return pd.DataFrame(rows)


def target_calibration_overall(calibration: pd.DataFrame) -> pd.DataFrame:
    if calibration.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for risk_spec, group in calibration.groupby("risk_spec", dropna=False):
        weights = pd.to_numeric(group["row_count"], errors="coerce").fillna(0.0)
        rows.append(
            {
                "risk_spec": risk_spec,
                "fold_count": int(len(group)),
                "row_count": int(weights.sum()),
                "target_rate": float(group["target_count"].sum() / max(weights.sum(), 1.0)),
                "mean_auc": float(group["auc"].dropna().mean())
                if bool(group["auc"].notna().any())
                else float("nan"),
                "mean_brier": float(group["brier"].dropna().mean())
                if bool(group["brier"].notna().any())
                else float("nan"),
                "bucket_prediction_share": float(
                    np.average(group["bucket_prediction_share"], weights=weights)
                )
                if float(weights.sum()) > 0.0
                else float("nan"),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["mean_auc", "bucket_prediction_share"],
        ascending=[False, False],
    ).reset_index(drop=True)


def build_policy_inputs(args: argparse.Namespace) -> Path:
    family_predictions = parse_family_predictions(args.family_predictions)
    risk_specs = parse_risk_specs(args.risk_specs)
    source_modes = parse_csv(args.source_modes)
    penalty_strengths = parse_float_csv(args.penalty_strengths)
    quantile_scopes = parse_scope_csv(args.quantile_scopes)
    if not source_modes:
        raise ValueError("--source-modes must not be empty")
    if not penalty_strengths:
        raise ValueError("--penalty-strengths must not be empty")
    targets = normalize_exit_targets(
        args.exit_targets,
        target=args.target,
        risk_specs=risk_specs,
    )
    run_dir = make_run_dir(args.output_dir, args.label)
    enriched_dir = run_dir / "enriched_predictions"
    enriched_dir.mkdir(parents=True, exist_ok=True)

    summary_frames: list[pd.DataFrame] = []
    distribution_frames: list[pd.DataFrame] = []
    for family, prediction_path in family_predictions.items():
        predictions = pd.read_parquet(prediction_path)
        enriched = add_side_forced_exit_columns(
            predictions,
            targets=targets,
            target=args.target,
            risk_specs=risk_specs,
            risk_name=args.risk_name,
            risk_prefix=args.risk_prefix,
            prior_strength=args.prior_strength,
            min_group_support=args.min_group_support,
        )
        enriched, score_summary = add_forced_exit_adjusted_scores(
            enriched,
            family=family,
            risk_specs=risk_specs,
            risk_name=args.risk_name,
            score_kind_prefix=args.score_kind_prefix,
            long_column=args.long_column,
            short_column=args.short_column,
            long_rank_column=args.long_rank_column,
            short_rank_column=args.short_rank_column,
            penalty_strengths=penalty_strengths,
            source_modes=source_modes,
            no_prior_risk=args.no_prior_risk,
            min_score_scale=args.min_score_scale,
            quantile_scopes=quantile_scopes,
        )
        summary_frames.append(score_summary)
        distribution_frames.append(
            risk_distribution(
                enriched,
                family=family,
                risk_specs=risk_specs,
                risk_name=args.risk_name,
            )
        )
        output_path = enriched_dir / f"{family}_predictions_forced_exit.parquet"
        enriched.to_parquet(output_path, index=False)

    score_summary = pd.concat(summary_frames, ignore_index=True)
    distribution = pd.concat(distribution_frames, ignore_index=True)
    calibration = target_calibration_summary(
        targets,
        target=args.target,
        risk_specs=risk_specs,
        risk_name=args.risk_name,
        prior_strength=args.prior_strength,
        min_group_support=args.min_group_support,
    )
    calibration_overall = target_calibration_overall(calibration)
    score_summary.to_csv(run_dir / "score_adjustment_summary.csv", index=False)
    distribution.to_csv(run_dir / "forced_exit_risk_distribution.csv", index=False)
    calibration.to_csv(run_dir / "forced_exit_target_calibration.csv", index=False)
    calibration_overall.to_csv(
        run_dir / "forced_exit_target_calibration_overall.csv",
        index=False,
    )
    config = {
        "family_predictions": family_predictions,
        "exit_targets": args.exit_targets,
        "target": args.target,
        "risk_name": args.risk_name,
        "risk_specs": risk_specs,
        "risk_group_columns": {spec: CALIBRATION_SPECS[spec] for spec in risk_specs},
        "risk_prefix": args.risk_prefix,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_rank_column": args.long_rank_column,
        "short_rank_column": args.short_rank_column,
        "score_kind_prefix": args.score_kind_prefix,
        "source_modes": source_modes,
        "penalty_strengths": penalty_strengths,
        "no_prior_risk": args.no_prior_risk,
        "min_score_scale": args.min_score_scale,
        "prior_strength": args.prior_strength,
        "min_group_support": args.min_group_support,
        "quantile_scopes": quantile_scopes,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    print("Forced-exit risk distribution:")
    print(distribution.to_string(index=False))
    print("\nScore adjustment summary:")
    print(score_summary.to_string(index=False))
    print("\nTarget calibration overall:")
    print(calibration_overall.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--exit-targets", type=Path, required=True)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--risk-name", default=DEFAULT_RISK_NAME)
    parser.add_argument("--risk-specs", default=DEFAULT_RISK_SPECS)
    parser.add_argument("--risk-prefix", default="pred_side_prior_pressure")
    parser.add_argument(
        "--long-column",
        default="pred_direction_inversion_bucket_s0p1_long_best_adjusted_pnl",
    )
    parser.add_argument(
        "--short-column",
        default="pred_direction_inversion_bucket_s0p1_short_best_adjusted_pnl",
    )
    parser.add_argument("--long-rank-column", default="pred_long_entry_local_rank")
    parser.add_argument("--short-rank-column", default="pred_short_entry_local_rank")
    parser.add_argument("--score-kind-prefix", default=DEFAULT_SCORE_KIND_PREFIX)
    parser.add_argument("--source-modes", default="bucket,bucket_or_global")
    parser.add_argument("--penalty-strengths", default="0.25,0.5,1.0")
    parser.add_argument("--no-prior-risk", type=float, default=0.0)
    parser.add_argument("--min-score-scale", type=float, default=0.0)
    parser.add_argument("--prior-strength", type=float, default=5.0)
    parser.add_argument("--min-group-support", type=int, default=2)
    parser.add_argument("--quantile-scopes", default=DEFAULT_QUANTILE_SCOPES)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_forced_exit_policy_inputs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_policy_inputs(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
