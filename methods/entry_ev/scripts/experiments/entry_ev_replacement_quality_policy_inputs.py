#!/usr/bin/env python3
"""Attach replacement-positive-quality estimates and combined risk scores."""

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

from entry_ev_common_loss_target_diagnostics import (  # noqa: E402
    brier_score,
    rank_auc,
)
from entry_ev_executable_ev_policy_inputs import add_executable_quantile_columns  # noqa: E402
from entry_ev_scale_quantile_diagnostics import month_series, parse_scope_csv  # noqa: E402
from entry_ev_side_prior_pressure_policy_inputs import strength_label  # noqa: E402


DEFAULT_TARGET = "replacement_positive_quality_target"
DEFAULT_QUALITY_SPEC = "risk_pressure"
DEFAULT_SCORE_KIND_PREFIX = "replacement_quality_combo"
DEFAULT_QUANTILE_SCOPES = "month,side_month,side_regime_session_month"

QUALITY_GROUP_SPECS: dict[str, list[str]] = {
    "risk_pressure": [
        "direction",
        "selected_risk_bucket",
        "selected_side_support_bucket",
        "selected_side_pressure_bucket",
    ],
    "side_context": ["direction", "combined_regime", "session_regime"],
    "side_context_risk": [
        "direction",
        "combined_regime",
        "session_regime",
        "selected_risk_bucket",
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


def source_mode_label(value: str) -> str:
    return value.replace("_or_", "or")


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
    normalized = series.astype(str).str.lower().str.strip()
    return normalized.isin({"true", "1", "yes", "y"})


def text_series(frame: pd.DataFrame, column: str, default: str = "missing") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index)
    return (
        frame[column]
        .fillna(default)
        .astype(str)
        .str.strip()
        .replace({"": default, "nan": default, "None": default})
    )


def selected_risk_bucket(risk: pd.Series) -> pd.Series:
    return (
        pd.cut(
            pd.to_numeric(risk, errors="coerce"),
            bins=[-0.001, 0.20, 0.45, 0.60, float("inf")],
            labels=["very_low", "medium", "high", "extreme"],
        )
        .astype(str)
        .replace({"nan": "missing"})
    )


def side_column(prefix: str, side: str, suffix: str) -> str:
    return f"{prefix}_{side}_{suffix}"


def prediction_month_strings(predictions: pd.DataFrame) -> pd.Series:
    return month_series(predictions).astype(str).str.slice(0, 7)


def normalize_replacement_targets(path: Path, *, target: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {
        "month",
        target,
        "replacement_adjusted_pnl",
        *set().union(*QUALITY_GROUP_SPECS.values()),
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"replacement target frame missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["direction"] = output["direction"].astype(str).str.lower()
    for column in sorted(set().union(*QUALITY_GROUP_SPECS.values())):
        output[column] = text_series(output, column)
    output[target] = bool_series(output, target)
    output["replacement_adjusted_pnl"] = numeric_series(
        output,
        "replacement_adjusted_pnl",
        default=np.nan,
    )
    return output


def build_side_rows(
    predictions: pd.DataFrame,
    *,
    side: str,
    risk_prefix: str,
) -> pd.DataFrame:
    risk_column = side_column(risk_prefix, side, "predicted_ev_overestimate_risk")
    support_column = side_column(risk_prefix, side, "support_bucket")
    pressure_column = side_column(risk_prefix, side, "pressure_bucket")
    required = ["combined_regime", "session_regime", risk_column, support_column, pressure_column]
    missing = [column for column in required if column not in predictions.columns]
    if missing:
        raise ValueError(f"predictions missing columns: {', '.join(missing)}")
    risk = numeric_series(predictions, risk_column, default=np.nan)
    return pd.DataFrame(
        {
            "_row_id": np.arange(len(predictions), dtype=int),
            "month": prediction_month_strings(predictions),
            "direction": side,
            "combined_regime": text_series(predictions, "combined_regime"),
            "session_regime": text_series(predictions, "session_regime"),
            "selected_risk_bucket": selected_risk_bucket(risk),
            "selected_side_support_bucket": text_series(predictions, support_column),
            "selected_side_pressure_bucket": text_series(predictions, pressure_column),
            "source_ev_overestimate_risk": risk,
        }
    )


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


def apply_replacement_quality(
    side_rows: pd.DataFrame,
    targets: pd.DataFrame,
    *,
    target: str,
    group_columns: list[str],
    prior_strength: float,
    min_group_support: int,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
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
            output["predicted_replacement_quality"] = np.nan
            output["replacement_quality_prediction_support"] = 0
            output["replacement_quality_prediction_source"] = "no_prior"
        elif table.empty:
            output["predicted_replacement_quality"] = global_rate
            output["replacement_quality_prediction_support"] = 0
            output["replacement_quality_prediction_source"] = "global"
        else:
            merged = output.merge(table, how="left", on=group_columns)
            bucket_hit = merged["predicted_target_rate"].notna()
            merged["predicted_replacement_quality"] = merged["predicted_target_rate"].where(
                bucket_hit,
                global_rate,
            )
            merged["replacement_quality_prediction_support"] = pd.to_numeric(
                merged["prediction_support"],
                errors="coerce",
            ).fillna(0.0).astype(int)
            merged["replacement_quality_prediction_source"] = np.where(
                bucket_hit,
                "bucket",
                "global",
            )
            output = merged.drop(columns=["predicted_target_rate", "prediction_support"])
        frames.append(output)
    return pd.concat(frames, ignore_index=True).sort_values("_row_id").reset_index(drop=True)


def add_side_replacement_quality_columns(
    predictions: pd.DataFrame,
    *,
    targets: pd.DataFrame,
    target: str,
    quality_spec: str,
    risk_prefix: str,
    prior_strength: float,
    min_group_support: int,
) -> pd.DataFrame:
    if quality_spec not in QUALITY_GROUP_SPECS:
        raise ValueError(f"unknown quality spec: {quality_spec}")
    output = predictions.copy()
    group_columns = QUALITY_GROUP_SPECS[quality_spec]
    for side in ["long", "short"]:
        side_rows = build_side_rows(output, side=side, risk_prefix=risk_prefix)
        quality = apply_replacement_quality(
            side_rows,
            targets,
            target=target,
            group_columns=group_columns,
            prior_strength=prior_strength,
            min_group_support=min_group_support,
        )
        quality = quality.sort_values("_row_id").reset_index(drop=True)
        for column in [
            "selected_risk_bucket",
            "selected_side_support_bucket",
            "selected_side_pressure_bucket",
            "source_ev_overestimate_risk",
            "predicted_replacement_quality",
            "replacement_quality_prediction_support",
            "replacement_quality_prediction_source",
        ]:
            output[f"pred_replacement_quality_{quality_spec}_{side}_{column}"] = (
                quality[column].to_numpy()
            )
    return output


def mask_by_source_mode(source: pd.Series, mode: str) -> pd.Series:
    source = source.astype(str)
    if mode == "bucket":
        return source.eq("bucket")
    if mode == "bucket_or_global":
        return source.isin(["bucket", "global"])
    raise ValueError(f"unknown source mode: {mode}")


def source_filtered_probability(
    frame: pd.DataFrame,
    *,
    value_column: str,
    source_column: str,
    mode: str,
    default: float,
) -> pd.Series:
    values = numeric_series(frame, value_column, default=np.nan).clip(0.0, 1.0)
    source = text_series(frame, source_column, default="no_prior")
    allowed = mask_by_source_mode(source, mode)
    return values.where(allowed, default).fillna(default).clip(0.0, 1.0)


def add_combined_adjusted_scores(
    predictions: pd.DataFrame,
    *,
    family: str,
    quality_spec: str,
    score_kind_prefix: str,
    long_column: str,
    short_column: str,
    long_rank_column: str,
    short_rank_column: str,
    penalty_strengths: list[float],
    direction_source_modes: list[str],
    quality_source_modes: list[str],
    no_prior_direction_risk: float,
    no_prior_replacement_quality: float,
    min_score_scale: float,
    quantile_scopes: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = predictions.copy()
    summary_rows: list[dict[str, Any]] = []
    long_base = numeric_series(output, long_column)
    short_base = numeric_series(output, short_column)
    for direction_mode in direction_source_modes:
        for quality_mode in quality_source_modes:
            for strength in penalty_strengths:
                label = strength_label(strength)
                dir_label = source_mode_label(direction_mode)
                quality_label = source_mode_label(quality_mode)
                score_kind = f"{score_kind_prefix}_dr{dir_label}_q{quality_label}_{label}"
                long_dir_risk = source_filtered_probability(
                    output,
                    value_column="pred_direction_inversion_long_predicted_direction_inversion_risk",
                    source_column="pred_direction_inversion_long_direction_inversion_prediction_source",
                    mode=direction_mode,
                    default=no_prior_direction_risk,
                )
                short_dir_risk = source_filtered_probability(
                    output,
                    value_column="pred_direction_inversion_short_predicted_direction_inversion_risk",
                    source_column="pred_direction_inversion_short_direction_inversion_prediction_source",
                    mode=direction_mode,
                    default=no_prior_direction_risk,
                )
                long_quality = source_filtered_probability(
                    output,
                    value_column=(
                        f"pred_replacement_quality_{quality_spec}_long_"
                        "predicted_replacement_quality"
                    ),
                    source_column=(
                        f"pred_replacement_quality_{quality_spec}_long_"
                        "replacement_quality_prediction_source"
                    ),
                    mode=quality_mode,
                    default=no_prior_replacement_quality,
                )
                short_quality = source_filtered_probability(
                    output,
                    value_column=(
                        f"pred_replacement_quality_{quality_spec}_short_"
                        "predicted_replacement_quality"
                    ),
                    source_column=(
                        f"pred_replacement_quality_{quality_spec}_short_"
                        "replacement_quality_prediction_source"
                    ),
                    mode=quality_mode,
                    default=no_prior_replacement_quality,
                )
                long_penalty = long_dir_risk * (1.0 - long_quality)
                short_penalty = short_dir_risk * (1.0 - short_quality)
                long_scale = (1.0 - strength * long_penalty).clip(
                    lower=min_score_scale,
                    upper=1.0,
                )
                short_scale = (1.0 - strength * short_penalty).clip(
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
                summary_rows.append(
                    {
                        "family": family,
                        "score_kind": score_kind,
                        "penalty_strength": strength,
                        "direction_source_mode": direction_mode,
                        "quality_source_mode": quality_mode,
                        "long_scale_mean": float(long_scale.mean()),
                        "short_scale_mean": float(short_scale.mean()),
                        "long_penalty_mean": float(long_penalty.mean()),
                        "short_penalty_mean": float(short_penalty.mean()),
                        "long_direction_risk_mean": float(long_dir_risk.mean()),
                        "short_direction_risk_mean": float(short_dir_risk.mean()),
                        "long_replacement_quality_mean": float(long_quality.mean()),
                        "short_replacement_quality_mean": float(short_quality.mean()),
                        "long_low_quality_mean": float((1.0 - long_quality).mean()),
                        "short_low_quality_mean": float((1.0 - short_quality).mean()),
                    }
                )
    return output, pd.DataFrame(summary_rows)


def replacement_quality_distribution(
    enriched: pd.DataFrame,
    *,
    family: str,
    quality_spec: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for side in ["long", "short"]:
        quality = numeric_series(
            enriched,
            f"pred_replacement_quality_{quality_spec}_{side}_predicted_replacement_quality",
            default=np.nan,
        )
        source = text_series(
            enriched,
            f"pred_replacement_quality_{quality_spec}_{side}_replacement_quality_prediction_source",
            default="no_prior",
        )
        rows.append(
            {
                "family": family,
                "quality_spec": quality_spec,
                "side": side,
                "row_count": int(len(enriched)),
                "quality_predicted_count": int(quality.notna().sum()),
                "quality_mean": float(quality.dropna().mean())
                if quality.notna().any()
                else float("nan"),
                "quality_p10": float(quality.dropna().quantile(0.10))
                if quality.notna().any()
                else float("nan"),
                "quality_p50": float(quality.dropna().quantile(0.50))
                if quality.notna().any()
                else float("nan"),
                "bucket_share": float(source.eq("bucket").mean()),
                "global_share": float(source.eq("global").mean()),
                "no_prior_share": float(source.eq("no_prior").mean()),
            }
        )
    return rows


def target_calibration_summary(
    targets: pd.DataFrame,
    *,
    target: str,
    prior_strength: float,
    min_group_support: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    month_values = targets["month"].astype(str)
    periods = pd.PeriodIndex(month_values, freq="M")
    for spec_name, group_columns in QUALITY_GROUP_SPECS.items():
        for month in sorted(month_values.unique()):
            train = targets[periods < pd.Period(month, freq="M")].copy()
            test = targets[month_values.eq(month)].copy()
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
            predicted = apply_replacement_quality(
                test.assign(_row_id=np.arange(len(test), dtype=int)),
                targets,
                target=target,
                group_columns=group_columns,
                prior_strength=prior_strength,
                min_group_support=min_group_support,
            )
            scores = numeric_series(predicted, "predicted_replacement_quality", default=np.nan)
            target_values = bool_series(predicted, target)
            rows.append(
                {
                    "quality_spec": spec_name,
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
                        predicted["replacement_quality_prediction_source"].astype(str).eq("bucket").mean()
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
    for spec_name, group in calibration.groupby("quality_spec", dropna=False):
        weights = pd.to_numeric(group["row_count"], errors="coerce").fillna(0.0)
        rows.append(
            {
                "quality_spec": spec_name,
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
                if float(weights.sum()) > 0
                else float("nan"),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["mean_auc", "bucket_prediction_share"],
        ascending=[False, False],
    ).reset_index(drop=True)


def build_policy_inputs(args: argparse.Namespace) -> Path:
    family_predictions = parse_family_predictions(args.family_predictions)
    penalty_strengths = parse_float_csv(args.penalty_strengths)
    direction_source_modes = parse_csv(args.direction_source_modes)
    quality_source_modes = parse_csv(args.quality_source_modes)
    quantile_scopes = parse_scope_csv(args.quantile_scopes)
    if not penalty_strengths:
        raise ValueError("--penalty-strengths must not be empty")
    targets = normalize_replacement_targets(args.replacement_targets, target=args.target)
    run_dir = make_run_dir(args.output_dir, args.label)
    enriched_dir = run_dir / "enriched_predictions"
    enriched_dir.mkdir(parents=True, exist_ok=True)

    summary_frames: list[pd.DataFrame] = []
    distribution_rows: list[dict[str, Any]] = []
    for family, prediction_path in family_predictions.items():
        predictions = pd.read_parquet(prediction_path)
        enriched = add_side_replacement_quality_columns(
            predictions,
            targets=targets,
            target=args.target,
            quality_spec=args.quality_spec,
            risk_prefix=args.risk_prefix,
            prior_strength=args.prior_strength,
            min_group_support=args.min_group_support,
        )
        enriched, family_summary = add_combined_adjusted_scores(
            enriched,
            family=family,
            quality_spec=args.quality_spec,
            score_kind_prefix=args.score_kind_prefix,
            long_column=args.long_column,
            short_column=args.short_column,
            long_rank_column=args.long_rank_column,
            short_rank_column=args.short_rank_column,
            penalty_strengths=penalty_strengths,
            direction_source_modes=direction_source_modes,
            quality_source_modes=quality_source_modes,
            no_prior_direction_risk=args.no_prior_direction_risk,
            no_prior_replacement_quality=args.no_prior_replacement_quality,
            min_score_scale=args.min_score_scale,
            quantile_scopes=quantile_scopes,
        )
        summary_frames.append(family_summary)
        distribution_rows.extend(
            replacement_quality_distribution(
                enriched,
                family=family,
                quality_spec=args.quality_spec,
            )
        )
        output_path = enriched_dir / f"{family}_predictions_replacement_quality.parquet"
        enriched.to_parquet(output_path, index=False)

    score_summary = pd.concat(summary_frames, ignore_index=True)
    quality_distribution = pd.DataFrame(distribution_rows)
    calibration = target_calibration_summary(
        targets,
        target=args.target,
        prior_strength=args.prior_strength,
        min_group_support=args.min_group_support,
    )
    calibration_overall = target_calibration_overall(calibration)
    score_summary.to_csv(run_dir / "score_adjustment_summary.csv", index=False)
    quality_distribution.to_csv(run_dir / "replacement_quality_distribution.csv", index=False)
    calibration.to_csv(run_dir / "replacement_quality_target_calibration.csv", index=False)
    calibration_overall.to_csv(
        run_dir / "replacement_quality_target_calibration_overall.csv",
        index=False,
    )
    config = {
        "family_predictions": family_predictions,
        "replacement_targets": args.replacement_targets,
        "target": args.target,
        "quality_spec": args.quality_spec,
        "quality_group_columns": QUALITY_GROUP_SPECS[args.quality_spec],
        "risk_prefix": args.risk_prefix,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_rank_column": args.long_rank_column,
        "short_rank_column": args.short_rank_column,
        "score_kind_prefix": args.score_kind_prefix,
        "penalty_strengths": penalty_strengths,
        "direction_source_modes": direction_source_modes,
        "quality_source_modes": quality_source_modes,
        "no_prior_direction_risk": args.no_prior_direction_risk,
        "no_prior_replacement_quality": args.no_prior_replacement_quality,
        "min_score_scale": args.min_score_scale,
        "prior_strength": args.prior_strength,
        "min_group_support": args.min_group_support,
        "quantile_scopes": quantile_scopes,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    print("Replacement quality distribution:")
    print(quality_distribution.to_string(index=False))
    print("\nScore adjustment summary:")
    print(score_summary.to_string(index=False))
    print("\nTarget calibration overall:")
    print(calibration_overall.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--replacement-targets", type=Path, required=True)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument(
        "--quality-spec",
        default=DEFAULT_QUALITY_SPEC,
        choices=sorted(QUALITY_GROUP_SPECS),
    )
    parser.add_argument("--risk-prefix", default="pred_side_prior_pressure")
    parser.add_argument(
        "--long-column",
        default="pred_side_prior_pressure_s0p5_long_best_adjusted_pnl",
    )
    parser.add_argument(
        "--short-column",
        default="pred_side_prior_pressure_s0p5_short_best_adjusted_pnl",
    )
    parser.add_argument("--long-rank-column", default="pred_long_entry_local_rank")
    parser.add_argument("--short-rank-column", default="pred_short_entry_local_rank")
    parser.add_argument("--score-kind-prefix", default=DEFAULT_SCORE_KIND_PREFIX)
    parser.add_argument("--penalty-strengths", default="0.25,0.5,1.0")
    parser.add_argument("--direction-source-modes", default="bucket,bucket_or_global")
    parser.add_argument("--quality-source-modes", default="bucket,bucket_or_global")
    parser.add_argument("--no-prior-direction-risk", type=float, default=0.0)
    parser.add_argument("--no-prior-replacement-quality", type=float, default=1.0)
    parser.add_argument("--min-score-scale", type=float, default=0.0)
    parser.add_argument("--prior-strength", type=float, default=5.0)
    parser.add_argument("--min-group-support", type=int, default=2)
    parser.add_argument("--quantile-scopes", default=DEFAULT_QUANTILE_SCOPES)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_replacement_quality_policy_inputs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_policy_inputs(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
