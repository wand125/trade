#!/usr/bin/env python3
"""Attach chronological side/regime tail-risk estimates to prediction rows."""

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


DEFAULT_TARGET = "direction_side_inversion_target"
DEFAULT_GROUP_SPECS = "direction_regime"
DEFAULT_SCORE_KIND_PREFIX = "side_regime_tail"
DEFAULT_QUANTILE_SCOPES = "month,side_month,side_regime_session_month"

GROUP_SPECS: dict[str, list[str]] = {
    "direction_regime": ["direction", "combined_regime"],
    "side_context": ["direction", "combined_regime", "session_regime"],
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


def parse_group_specs(value: str) -> list[str]:
    specs = parse_csv(value)
    invalid = sorted(spec for spec in specs if spec not in GROUP_SPECS)
    if invalid:
        raise argparse.ArgumentTypeError(f"unknown group specs: {','.join(invalid)}")
    if not specs:
        raise argparse.ArgumentTypeError("at least one group spec is required")
    return specs


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


def prediction_month_strings(predictions: pd.DataFrame) -> pd.Series:
    return month_series(predictions).astype(str).str.slice(0, 7)


def normalize_targets(path: Path, *, target: str, group_specs: list[str]) -> pd.DataFrame:
    frame = pd.read_csv(path)
    group_columns = sorted(set().union(*(GROUP_SPECS[spec] for spec in group_specs)))
    required = {"month", target, *group_columns}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"target frame missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["direction"] = output["direction"].astype(str).str.lower()
    for column in group_columns:
        output[column] = text_series(output, column)
    output[target] = bool_series(output, target)
    if "candidate_adjusted_pnl" in output.columns:
        output["candidate_adjusted_pnl"] = numeric_series(
            output,
            "candidate_adjusted_pnl",
            default=np.nan,
        )
    return output


def build_side_rows(predictions: pd.DataFrame, *, side: str) -> pd.DataFrame:
    required = ["combined_regime", "session_regime"]
    missing = [column for column in required if column not in predictions.columns]
    if missing:
        raise ValueError(f"predictions missing columns: {', '.join(missing)}")
    return pd.DataFrame(
        {
            "_row_id": np.arange(len(predictions), dtype=int),
            "month": prediction_month_strings(predictions),
            "direction": side,
            "combined_regime": text_series(predictions, "combined_regime"),
            "session_regime": text_series(predictions, "session_regime"),
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


def apply_tail_risk(
    rows: pd.DataFrame,
    targets: pd.DataFrame,
    *,
    target: str,
    group_columns: list[str],
    prior_strength: float,
    min_group_support: int,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for month, group in rows.groupby("month", dropna=False, sort=True):
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
            output["predicted_tail_risk"] = np.nan
            output["tail_prediction_support"] = 0
            output["tail_prediction_source"] = "no_prior"
        elif table.empty:
            output["predicted_tail_risk"] = global_rate
            output["tail_prediction_support"] = 0
            output["tail_prediction_source"] = "global"
        else:
            merged = output.merge(table, how="left", on=group_columns)
            bucket_hit = merged["predicted_target_rate"].notna()
            merged["predicted_tail_risk"] = merged["predicted_target_rate"].where(
                bucket_hit,
                global_rate,
            )
            merged["tail_prediction_support"] = pd.to_numeric(
                merged["prediction_support"],
                errors="coerce",
            ).fillna(0.0).astype(int)
            merged["tail_prediction_source"] = np.where(bucket_hit, "bucket", "global")
            output = merged.drop(columns=["predicted_target_rate", "prediction_support"])
        frames.append(output)
    return pd.concat(frames, ignore_index=True).sort_values("_row_id").reset_index(drop=True)


def add_side_tail_columns(
    predictions: pd.DataFrame,
    *,
    targets: pd.DataFrame,
    target: str,
    group_spec: str,
    score_kind_prefix: str,
    prior_strength: float,
    min_group_support: int,
) -> pd.DataFrame:
    group_columns = GROUP_SPECS[group_spec]
    output = predictions.copy()
    column_prefix = f"pred_{score_kind_prefix}_{group_spec}"
    for side in ["long", "short"]:
        side_rows = build_side_rows(output, side=side)
        side_rows = apply_tail_risk(
            side_rows,
            targets,
            target=target,
            group_columns=group_columns,
            prior_strength=prior_strength,
            min_group_support=min_group_support,
        )
        side_rows = side_rows.sort_values("_row_id").reset_index(drop=True)
        for column in [
            "predicted_tail_risk",
            "tail_prediction_support",
            "tail_prediction_source",
        ]:
            output[f"{column_prefix}_{side}_{column}"] = side_rows[column].to_numpy()
    return output


def add_tail_adjusted_scores(
    predictions: pd.DataFrame,
    *,
    family: str,
    group_specs: list[str],
    score_kind_prefix: str,
    side_gap_source_score_kind: str,
    long_column: str,
    short_column: str,
    long_rank_column: str,
    short_rank_column: str,
    penalty_strengths: list[float],
    no_prior_risk: float,
    min_score_scale: float,
    use_global_risk: bool,
    quantile_scopes: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = predictions.copy()
    summary_rows: list[dict[str, Any]] = []
    long_base = numeric_series(output, long_column)
    short_base = numeric_series(output, short_column)
    for group_spec in group_specs:
        column_prefix = f"pred_{score_kind_prefix}_{group_spec}"
        for strength in penalty_strengths:
            label = strength_label(strength)
            score_kind = f"{score_kind_prefix}_{group_spec}_{label}"
            long_raw_risk = numeric_series(
                output,
                f"{column_prefix}_long_predicted_tail_risk",
                default=np.nan,
            )
            short_raw_risk = numeric_series(
                output,
                f"{column_prefix}_short_predicted_tail_risk",
                default=np.nan,
            )
            long_source = output[f"{column_prefix}_long_tail_prediction_source"].astype(str)
            short_source = output[f"{column_prefix}_short_tail_prediction_source"].astype(str)
            if use_global_risk:
                long_risk = long_raw_risk.fillna(no_prior_risk)
                short_risk = short_raw_risk.fillna(no_prior_risk)
                long_risk = long_risk.where(~long_source.eq("no_prior"), no_prior_risk)
                short_risk = short_risk.where(~short_source.eq("no_prior"), no_prior_risk)
            else:
                long_risk = long_raw_risk.where(long_source.eq("bucket"), no_prior_risk)
                short_risk = short_raw_risk.where(short_source.eq("bucket"), no_prior_risk)
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
            if side_gap_source_score_kind:
                for scope_name in quantile_scopes:
                    source_column = (
                        f"pred_{side_gap_source_score_kind}_side_gap_pct_{scope_name}"
                    )
                    target_column = f"pred_{score_kind}_side_gap_pct_{scope_name}"
                    if source_column not in output.columns:
                        raise ValueError(
                            f"predictions missing side-gap source column: {source_column}"
                        )
                    output[target_column] = output[source_column].to_numpy()
            summary_rows.append(
                {
                    "family": family,
                    "group_spec": group_spec,
                    "score_kind": score_kind,
                    "penalty_strength": strength,
                    "target_source_mode": "bucket_or_global" if use_global_risk else "bucket",
                    "side_gap_source_score_kind": side_gap_source_score_kind,
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


def risk_distribution(
    enriched: pd.DataFrame,
    *,
    family: str,
    group_specs: list[str],
    score_kind_prefix: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group_spec in group_specs:
        column_prefix = f"pred_{score_kind_prefix}_{group_spec}"
        for side in ["long", "short"]:
            risk = numeric_series(
                enriched,
                f"{column_prefix}_{side}_predicted_tail_risk",
                default=np.nan,
            )
            source = enriched[f"{column_prefix}_{side}_tail_prediction_source"].astype(str)
            support = numeric_series(
                enriched,
                f"{column_prefix}_{side}_tail_prediction_support",
            )
            rows.append(
                {
                    "family": family,
                    "group_spec": group_spec,
                    "side": side,
                    "row_count": int(len(enriched)),
                    "risk_predicted_count": int(risk.notna().sum()),
                    "risk_mean": float(risk.dropna().mean()) if risk.notna().any() else float("nan"),
                    "risk_p50": float(risk.dropna().quantile(0.50))
                    if risk.notna().any()
                    else float("nan"),
                    "risk_p90": float(risk.dropna().quantile(0.90))
                    if risk.notna().any()
                    else float("nan"),
                    "support_mean": float(support.mean()),
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
    group_specs: list[str],
    prior_strength: float,
    min_group_support: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    periods = pd.PeriodIndex(targets["month"].astype(str), freq="M")
    for group_spec in group_specs:
        group_columns = GROUP_SPECS[group_spec]
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
            predicted = apply_tail_risk(
                test.assign(_row_id=np.arange(len(test), dtype=int)),
                targets,
                target=target,
                group_columns=group_columns,
                prior_strength=prior_strength,
                min_group_support=min_group_support,
            )
            scores = numeric_series(predicted, "predicted_tail_risk", default=np.nan)
            target_values = bool_series(predicted, target)
            source = predicted["tail_prediction_source"].astype(str)
            rows.append(
                {
                    "group_spec": group_spec,
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
                    "bucket_share": float(source.eq("bucket").mean()),
                    "global_share": float(source.eq("global").mean()),
                    "no_prior_share": float(source.eq("no_prior").mean()),
                    "auc": rank_auc(target_values, scores),
                    "brier": brier_score(target_values, scores),
                }
            )
    return pd.DataFrame(rows)


def build_policy_inputs(args: argparse.Namespace) -> Path:
    family_predictions = parse_family_predictions(args.family_predictions)
    group_specs = parse_group_specs(args.group_specs)
    penalty_strengths = parse_float_csv(args.penalty_strengths)
    if not penalty_strengths:
        raise ValueError("--penalty-strengths must not be empty")
    quantile_scopes = parse_scope_csv(args.quantile_scopes)
    targets = normalize_targets(args.targets, target=args.target, group_specs=group_specs)
    run_dir = make_run_dir(args.output_dir, args.label)
    enriched_dir = run_dir / "enriched_predictions"
    enriched_dir.mkdir(parents=True, exist_ok=True)

    summary_frames: list[pd.DataFrame] = []
    distribution_rows: list[dict[str, Any]] = []
    for family, prediction_path in family_predictions.items():
        predictions = pd.read_parquet(prediction_path)
        enriched = predictions.copy()
        for group_spec in group_specs:
            enriched = add_side_tail_columns(
                enriched,
                targets=targets,
                target=args.target,
                group_spec=group_spec,
                score_kind_prefix=args.score_kind_prefix,
                prior_strength=args.prior_strength,
                min_group_support=args.min_group_support,
            )
        enriched, family_summary = add_tail_adjusted_scores(
            enriched,
            family=family,
            group_specs=group_specs,
            score_kind_prefix=args.score_kind_prefix,
            side_gap_source_score_kind=args.side_gap_source_score_kind,
            long_column=args.long_column,
            short_column=args.short_column,
            long_rank_column=args.long_rank_column,
            short_rank_column=args.short_rank_column,
            penalty_strengths=penalty_strengths,
            no_prior_risk=args.no_prior_risk,
            min_score_scale=args.min_score_scale,
            use_global_risk=args.use_global_risk,
            quantile_scopes=quantile_scopes,
        )
        summary_frames.append(family_summary)
        distribution_rows.extend(
            risk_distribution(
                enriched,
                family=family,
                group_specs=group_specs,
                score_kind_prefix=args.score_kind_prefix,
            )
        )
        output_path = enriched_dir / f"{family}_predictions_side_regime_tail.parquet"
        enriched.to_parquet(output_path, index=False)

    score_summary = pd.concat(summary_frames, ignore_index=True)
    risk_summary = pd.DataFrame(distribution_rows)
    calibration = target_calibration_summary(
        targets,
        target=args.target,
        group_specs=group_specs,
        prior_strength=args.prior_strength,
        min_group_support=args.min_group_support,
    )
    score_summary.to_csv(run_dir / "score_adjustment_summary.csv", index=False)
    risk_summary.to_csv(run_dir / "side_regime_tail_risk_distribution.csv", index=False)
    calibration.to_csv(run_dir / "side_regime_tail_target_calibration.csv", index=False)
    config = {
        "family_predictions": family_predictions,
        "targets": args.targets,
        "target": args.target,
        "group_specs": group_specs,
        "group_columns": {spec: GROUP_SPECS[spec] for spec in group_specs},
        "score_kind_prefix": args.score_kind_prefix,
        "side_gap_source_score_kind": args.side_gap_source_score_kind,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_rank_column": args.long_rank_column,
        "short_rank_column": args.short_rank_column,
        "penalty_strengths": penalty_strengths,
        "no_prior_risk": args.no_prior_risk,
        "min_score_scale": args.min_score_scale,
        "use_global_risk": args.use_global_risk,
        "prior_strength": args.prior_strength,
        "min_group_support": args.min_group_support,
        "quantile_scopes": quantile_scopes,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    print("Side/regime tail-risk distribution:")
    print(risk_summary.to_string(index=False))
    print("\nScore adjustment summary:")
    print(score_summary.to_string(index=False))
    print("\nTarget calibration:")
    print(calibration.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--group-specs", default=DEFAULT_GROUP_SPECS)
    parser.add_argument("--score-kind-prefix", default=DEFAULT_SCORE_KIND_PREFIX)
    parser.add_argument(
        "--side-gap-source-score-kind",
        default="",
        help=(
            "Optional source score kind whose side_gap_pct_* columns are copied to the "
            "new score kind. Use this to preserve pre-block side-gap gates."
        ),
    )
    parser.add_argument("--long-column", default="pred_calibrated_long_best_adjusted_pnl")
    parser.add_argument("--short-column", default="pred_calibrated_short_best_adjusted_pnl")
    parser.add_argument("--long-rank-column", default="pred_long_entry_local_rank")
    parser.add_argument("--short-rank-column", default="pred_short_entry_local_rank")
    parser.add_argument("--penalty-strengths", default="0.1")
    parser.add_argument("--no-prior-risk", type=float, default=0.0)
    parser.add_argument("--min-score-scale", type=float, default=0.0)
    parser.add_argument(
        "--use-global-risk",
        action="store_true",
        help="Also apply global fallback risk. Default uses bucket-supported risk only.",
    )
    parser.add_argument("--prior-strength", type=float, default=5.0)
    parser.add_argument("--min-group-support", type=int, default=1)
    parser.add_argument("--quantile-scopes", default=DEFAULT_QUANTILE_SCOPES)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_side_regime_tail_policy_inputs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_policy_inputs(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
