#!/usr/bin/env python3
"""Compare side/context calibration specs for EV-overestimate risk."""

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
    chronological_month_predictions,
    normalize_targets,
    role_holdout_predictions,
    summarize_prediction_metrics,
)
from entry_ev_overestimate_context_diagnostics import bucketize_context  # noqa: E402
from entry_ev_overestimate_risk_selector import DEFAULT_TARGET  # noqa: E402


DEFAULT_MODEL_SPECS = (
    "base=support_bucket,pressure_bucket;"
    "side=direction,support_bucket,pressure_bucket;"
    "side_drift=direction,support_bucket,pressure_bucket,side_drift_bucket;"
    "side_prior_pressure=direction,support_bucket,pressure_bucket,"
    "prior_support_bucket,feature_pressure_bucket;"
    "full_context=direction,support_bucket,pressure_bucket,prior_support_bucket,"
    "feature_pressure_bucket,side_drift_bucket"
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


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_float_csv(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


def parse_model_specs(value: str) -> list[tuple[str, list[str]]]:
    specs: list[tuple[str, list[str]]] = []
    seen: set[str] = set()
    for raw_spec in [part.strip() for part in value.split(";") if part.strip()]:
        if "=" not in raw_spec:
            raise argparse.ArgumentTypeError("model specs must use name=col1,col2")
        name, columns_value = raw_spec.split("=", 1)
        name = name.strip()
        columns = parse_csv(columns_value)
        if not name:
            raise argparse.ArgumentTypeError("model spec name must not be empty")
        if name in seen:
            raise argparse.ArgumentTypeError(f"duplicate model spec: {name}")
        if not columns:
            raise argparse.ArgumentTypeError(f"model spec has no columns: {name}")
        seen.add(name)
        specs.append((name, columns))
    if not specs:
        raise argparse.ArgumentTypeError("at least one model spec is required")
    return specs


def prepare_frame(path: Path, *, target: str, specs: list[tuple[str, list[str]]]) -> pd.DataFrame:
    raw = pd.read_csv(path)
    contextual = bucketize_context(raw)
    group_columns = sorted({column for _, columns in specs for column in columns})
    missing = sorted(set(group_columns) - set(contextual.columns))
    if missing:
        raise ValueError(f"component target frame missing spec columns: {', '.join(missing)}")
    return normalize_targets(
        contextual,
        targets=[target],
        group_columns=group_columns,
    )


def cumulative_max_drawdown(values: pd.Series) -> float:
    cumulative = values.astype(float).cumsum()
    if cumulative.empty:
        return 0.0
    return float((cumulative.cummax() - cumulative).max())


def weighted_average(values: pd.Series, weights: pd.Series) -> float:
    values = pd.to_numeric(values, errors="coerce")
    weights = pd.to_numeric(weights, errors="coerce").fillna(0.0)
    valid = values.notna() & np.isfinite(values) & weights.gt(0.0)
    if not bool(valid.any()):
        return float("nan")
    return float(np.average(values[valid], weights=weights[valid]))


def summarize_role_months(
    predictions: pd.DataFrame,
    *,
    target: str,
    risk_threshold: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in predictions.groupby(
        ["calibration_spec", "candidate", "role", "month"],
        dropna=False,
    ):
        spec, candidate, role, month = keys
        ordered = group.sort_values("entry_decision_timestamp")
        pnl = pd.to_numeric(ordered["adjusted_pnl"], errors="coerce").fillna(0.0)
        target_values = ordered[target].astype(bool)
        risk = pd.to_numeric(ordered["predicted_target_rate"], errors="coerce")
        available = risk.notna() & np.isfinite(risk)
        high_risk = available & risk.ge(risk_threshold)
        source = ordered["prediction_source"].astype(str)
        direction = ordered["direction"].astype(str).str.lower()
        rows.append(
            {
                "calibration_spec": spec,
                "candidate": candidate,
                "role": role,
                "month": month,
                "trade_count": int(len(ordered)),
                "total_pnl": float(pnl.sum()),
                "avg_pnl": float(pnl.mean()) if len(ordered) else 0.0,
                "win_rate": float(pnl.gt(0.0).mean()) if len(ordered) else 0.0,
                "max_drawdown": cumulative_max_drawdown(pnl),
                "long_trade_count": int(direction.eq("long").sum()),
                "short_trade_count": int(direction.eq("short").sum()),
                "target_rate": float(target_values.mean()) if len(ordered) else 0.0,
                "target_true_pnl": float(pnl.where(target_values, 0.0).sum()),
                "target_false_pnl": float(pnl.where(~target_values, 0.0).sum()),
                "prediction_count": int(available.sum()),
                "prediction_coverage": float(available.mean()) if len(ordered) else 0.0,
                "predicted_risk_mean": (
                    float(risk[available].mean()) if bool(available.any()) else float("nan")
                ),
                "predicted_risk_p90": (
                    float(risk[available].quantile(0.90))
                    if bool(available.any())
                    else float("nan")
                ),
                "high_risk_count": int(high_risk.sum()),
                "high_risk_share": float(high_risk.mean()) if len(ordered) else 0.0,
                "high_risk_pnl": float(pnl.where(high_risk, 0.0).sum()),
                "no_prior_share": float(source.eq("no_prior").mean()) if len(ordered) else 0.0,
                "bucket_prediction_share": (
                    float(source.eq("bucket").mean()) if len(ordered) else 0.0
                ),
                "global_prediction_share": (
                    float(source.eq("global").mean()) if len(ordered) else 0.0
                ),
                "mean_prediction_support": float(
                    pd.to_numeric(ordered["prediction_support"], errors="coerce")
                    .fillna(0.0)
                    .mean()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["calibration_spec", "candidate", "role", "month"],
    ).reset_index(drop=True)


def summarize_candidates(role_month: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in role_month.groupby(["calibration_spec", "candidate"], dropna=False):
        spec, candidate = keys
        role_totals = group.groupby("role")["total_pnl"].sum()
        role_trades = group.groupby("role")["trade_count"].sum()
        weights = group["trade_count"].astype(float)
        trade_count = int(weights.sum())
        long_count = int(group["long_trade_count"].sum())
        short_count = int(group["short_trade_count"].sum())
        target_count = float((group["target_rate"] * weights).sum())
        rows.append(
            {
                "calibration_spec": spec,
                "candidate": candidate,
                "role_count": int(group["role"].nunique()),
                "month_count": int(group["month"].nunique()),
                "active_role_count": int((role_trades > 0).sum()),
                "positive_role_count": int((role_totals > 0).sum()),
                "active_months": int(group["trade_count"].gt(0).sum()),
                "total_pnl": float(group["total_pnl"].sum()),
                "min_role_total_pnl": float(role_totals.min()) if len(role_totals) else 0.0,
                "min_month_pnl": float(group["total_pnl"].min()) if len(group) else 0.0,
                "trade_count": trade_count,
                "min_role_trades": int(role_trades.min()) if len(role_trades) else 0,
                "min_month_trades": int(group["trade_count"].min()) if len(group) else 0,
                "max_drawdown": float(group["max_drawdown"].max()) if len(group) else 0.0,
                "long_trade_count": long_count,
                "short_trade_count": short_count,
                "max_side_trade_share": (
                    float(max(long_count, short_count) / trade_count) if trade_count else 0.0
                ),
                "target_rate": float(target_count / trade_count) if trade_count else 0.0,
                "target_true_pnl": float(group["target_true_pnl"].sum()),
                "target_false_pnl": float(group["target_false_pnl"].sum()),
                "prediction_coverage": weighted_average(group["prediction_coverage"], weights),
                "predicted_risk_mean": weighted_average(group["predicted_risk_mean"], weights),
                "predicted_risk_p90_max": float(group["predicted_risk_p90"].max()),
                "high_risk_share": weighted_average(group["high_risk_share"], weights),
                "high_risk_pnl": float(group["high_risk_pnl"].sum()),
                "no_prior_share": weighted_average(group["no_prior_share"], weights),
                "bucket_prediction_share": weighted_average(
                    group["bucket_prediction_share"],
                    weights,
                ),
                "global_prediction_share": weighted_average(
                    group["global_prediction_share"],
                    weights,
                ),
                "mean_prediction_support": weighted_average(
                    group["mean_prediction_support"],
                    weights,
                ),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        [
            "calibration_spec",
            "min_role_total_pnl",
            "total_pnl",
            "predicted_risk_mean",
        ],
        ascending=[True, False, False, True],
    ).reset_index(drop=True)


def pointwise_screen_effects(
    predictions: pd.DataFrame,
    *,
    target: str,
    thresholds: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in predictions.groupby(["calibration_spec", "candidate"], dropna=False):
        spec, candidate = keys
        pnl = pd.to_numeric(group["adjusted_pnl"], errors="coerce").fillna(0.0)
        base_role = group.groupby("role")["adjusted_pnl"].sum()
        base_month = group.groupby("month")["adjusted_pnl"].sum()
        target_values = group[target].astype(bool)
        risk = pd.to_numeric(group["predicted_target_rate"], errors="coerce")
        available = risk.notna() & np.isfinite(risk)
        no_prior = group["prediction_source"].astype(str).eq("no_prior")
        base = {
            "calibration_spec": spec,
            "candidate": candidate,
            "original_trades": int(len(group)),
            "original_total_pnl": float(pnl.sum()),
            "original_min_role_pnl": float(base_role.min()) if len(base_role) else 0.0,
            "original_min_month_pnl": float(base_month.min()) if len(base_month) else 0.0,
            "original_target_rate": float(target_values.mean()) if len(group) else 0.0,
        }
        for threshold in thresholds:
            high_risk = available & risk.ge(threshold)
            for mode, remove_mask in [
                ("predicted_high_only", high_risk),
                ("predicted_high_or_no_prior", high_risk | no_prior),
            ]:
                kept = group[~remove_mask]
                removed = group[remove_mask]
                kept_role = zero_filled_group_totals(group, kept, ["role"])
                kept_month = zero_filled_group_totals(group, kept, ["month"])
                row = dict(base)
                row.update(
                    {
                        "risk_threshold": threshold,
                        "screen_mode": mode,
                        "removed_trades": int(len(removed)),
                        "removed_pnl": float(removed["adjusted_pnl"].sum())
                        if len(removed)
                        else 0.0,
                        "removed_target_rate": float(removed[target].astype(bool).mean())
                        if len(removed)
                        else 0.0,
                        "kept_trades": int(len(kept)),
                        "kept_total_pnl": float(kept["adjusted_pnl"].sum())
                        if len(kept)
                        else 0.0,
                        "kept_min_role_pnl": float(kept_role.min()) if len(kept_role) else 0.0,
                        "kept_min_month_pnl": (
                            float(kept_month.min()) if len(kept_month) else 0.0
                        ),
                        "kept_target_rate": float(kept[target].astype(bool).mean())
                        if len(kept)
                        else 0.0,
                    }
                )
                rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["calibration_spec", "candidate", "risk_threshold", "screen_mode"],
    ).reset_index(drop=True)


def zero_filled_group_totals(
    original: pd.DataFrame,
    kept: pd.DataFrame,
    group_columns: list[str],
) -> pd.Series:
    keys = original[group_columns].drop_duplicates().reset_index(drop=True)
    if keys.empty:
        return pd.Series(dtype=float)
    if kept.empty:
        return pd.Series(0.0, index=range(len(keys)), dtype=float)
    totals = (
        kept.groupby(group_columns, dropna=False)["adjusted_pnl"]
        .sum()
        .reset_index(name="screened_pnl")
    )
    merged = keys.merge(totals, how="left", on=group_columns)
    return pd.to_numeric(merged["screened_pnl"], errors="coerce").fillna(0.0)


def build_calibration_sweep(args: argparse.Namespace) -> Path:
    specs = parse_model_specs(args.model_specs)
    validation_roles = parse_csv(args.validation_roles)
    thresholds = parse_float_csv(args.pointwise_thresholds)
    if not validation_roles:
        raise ValueError("--validation-roles must not be empty")
    frame = prepare_frame(args.component_targets, target=args.target, specs=specs)

    prediction_frames: list[pd.DataFrame] = []
    metric_frames: list[pd.DataFrame] = []
    metric_summary_frames: list[pd.DataFrame] = []

    for spec_name, group_columns in specs:
        chrono_predictions, chrono_metrics = chronological_month_predictions(
            frame,
            targets=[args.target],
            group_columns=group_columns,
            prior_strength=args.prior_strength,
            min_group_support=args.min_group_support,
        )
        role_predictions, role_metrics = role_holdout_predictions(
            frame,
            targets=[args.target],
            group_columns=group_columns,
            prior_strength=args.prior_strength,
            min_group_support=args.min_group_support,
        )
        for predicted, fold_type in [
            (chrono_predictions, "chronological_month"),
            (role_predictions, "role_holdout"),
        ]:
            predicted["calibration_spec"] = spec_name
            predicted["fold_type"] = fold_type
            predicted["group_columns"] = ",".join(group_columns)
            prediction_frames.append(predicted)
        for metrics, fold_type in [
            (chrono_metrics, "chronological_month"),
            (role_metrics, "role_holdout"),
        ]:
            metrics["calibration_spec"] = spec_name
            metrics["fold_type"] = fold_type
            metrics["group_columns"] = ",".join(group_columns)
            metric_frames.append(metrics)
            summary = summarize_prediction_metrics(metrics, fold_type=fold_type)
            summary["calibration_spec"] = spec_name
            summary["group_columns"] = ",".join(group_columns)
            metric_summary_frames.append(summary)

    predictions = pd.concat(prediction_frames, ignore_index=True)
    metrics = pd.concat(metric_frames, ignore_index=True)
    metric_summary = pd.concat(metric_summary_frames, ignore_index=True)
    metric_summary = metric_summary.sort_values(
        ["fold_type", "mean_auc", "brier", "bucket_prediction_share"],
        ascending=[True, False, True, False],
    ).reset_index(drop=True)

    validation_predictions = predictions[
        predictions["fold_type"].eq("chronological_month")
        & predictions["role"].isin(validation_roles)
    ].copy()
    role_month = summarize_role_months(
        validation_predictions,
        target=args.target,
        risk_threshold=args.risk_threshold,
    )
    candidate_summary = summarize_candidates(role_month)
    pointwise = pointwise_screen_effects(
        validation_predictions,
        target=args.target,
        thresholds=thresholds,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    pd.DataFrame(
        [
            {
                "calibration_spec": spec_name,
                "group_columns": ",".join(group_columns),
                "group_column_count": len(group_columns),
            }
            for spec_name, group_columns in specs
        ]
    ).to_csv(run_dir / "calibration_specs.csv", index=False)
    metric_summary.to_csv(run_dir / "context_calibration_metric_summary.csv", index=False)
    metrics.to_csv(run_dir / "context_calibration_fold_metrics.csv", index=False)
    predictions.to_csv(run_dir / "context_calibration_predictions.csv", index=False)
    role_month.to_csv(run_dir / "validation_role_month_context_risk.csv", index=False)
    candidate_summary.to_csv(run_dir / "validation_candidate_context_risk_summary.csv", index=False)
    pointwise.to_csv(run_dir / "validation_pointwise_context_screen_effects.csv", index=False)
    config = {
        "component_targets": args.component_targets,
        "target": args.target,
        "model_specs": [
            {"name": spec_name, "group_columns": group_columns}
            for spec_name, group_columns in specs
        ],
        "validation_roles": validation_roles,
        "prior_strength": args.prior_strength,
        "min_group_support": args.min_group_support,
        "risk_threshold": args.risk_threshold,
        "pointwise_thresholds": thresholds,
        "selection_uses_future_or_fixed_roles": False,
        "note": (
            "validation summaries use chronological_month predictions only; "
            "pointwise screens do not model one-position replacement"
        ),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Context calibration metric summary:")
    print(
        metric_summary[
            [
                "calibration_spec",
                "fold_type",
                "row_count",
                "predicted_count",
                "target_rate",
                "predicted_mean",
                "brier",
                "mean_auc",
                "bucket_prediction_share",
                "global_prediction_share",
            ]
        ].to_string(index=False)
    )
    print("\nValidation candidate context risk summary:")
    print(
        candidate_summary[
            [
                "calibration_spec",
                "candidate",
                "total_pnl",
                "min_role_total_pnl",
                "min_month_pnl",
                "trade_count",
                "predicted_risk_mean",
                "high_risk_share",
                "high_risk_pnl",
                "bucket_prediction_share",
                "global_prediction_share",
                "no_prior_share",
            ]
        ].to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component-targets", type=Path, required=True)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--model-specs", default=DEFAULT_MODEL_SPECS)
    parser.add_argument("--validation-roles", required=True)
    parser.add_argument("--prior-strength", type=float, default=5.0)
    parser.add_argument("--min-group-support", type=int, default=3)
    parser.add_argument("--risk-threshold", type=float, default=0.50)
    parser.add_argument("--pointwise-thresholds", default="0.45,0.50,0.55,0.60,0.65")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_context_calibration_sweep")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_calibration_sweep(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
